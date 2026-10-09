# -*- coding: utf-8 -*-
"""OFF vs ON, same argv, same input, on the OWNER'S own 90 s capture.

WHAT IS BEING COMPARED. Three arms, staged by `_denoise-arms-setup.py`:

    A  off-worker  + use_denoise:false     (live revision minus this lane's code)
    B  on-worker   + use_denoise:false     (live revision, byte-identical copy)
    C  on-worker   + use_denoise:true      (live revision + the remover live)

    A vs B  does ADDING this lane change anything when the key is false?
    B vs C  what does the remover DO to the owner's audio, and what does it cost?

A vs B is the claim that has to survive: if the key is false, the only
difference in the whole JSONL stream may be the one added `state="denoise"`
status line. Deleting that one line has to leave the two streams byte-identical,
and every counter has to match. Anything else is a regression that would ship
next to a running app.

B vs C is NOT a quality claim. There is no reference transcription of this
audio, so nothing here can say the text got better, and this script does not
pretend to. It reports what the gate did to the waveform (from
`worker/denoise.py`'s own instrument, same class, same defaults), what the model
decoded, and what the switch cost.

WHY EVERY ARM RUNS AS A SCRIPT AND NEVER BY IMPORTING. `_main/file-arm-ab.py`
measured it: driving `W.selftest(...)` in-process and running
`worker/sotto_worker.py --selftest` gave DIFFERENT decodes of the same file
(frames 528 vs 524). Importing the module and calling its functions is not the
same subject as executing it. So each arm is a separate `python <script>
--selftest ...` process, and the cost numbers come from OUTSIDE the process
(psutil) as well as from its own `selftest-done`.

WHY THE RUNS ARE INTERLEAVED. On this box the same arm has given RTF 0.1534 and
0.0798 on two passes -- a factor of 1.9 from machine load alone. Comparing arm A
once against arm C once would measure the load. So the arms are interleaved and
each one runs TWICE: the spread inside an arm is the noise floor, and a
difference smaller than that spread is reported as a difference of zero.

NO PIPES. Each arm's stdout and stderr go to FILES. This box refuses named
pipes between processes under the confined modes, and a redirected file is also
what lets one arm's JSONL be compared to another's byte for byte afterwards.

NO WINDOW. CREATE_NO_WINDOW|DETACHED_PROCESS on every spawn -- a console left on
the owner's screen is a failure, not a cosmetic detail.

USAGE
    py -3 _main/denoise-file-ab.py                       # 6 runs, gate default (off)
    py -3 _main/denoise-file-ab.py --passes 1            # 3 runs
    py -3 _main/denoise-file-ab.py --gate-on             # 6 runs with SOTTO_GATE=1
    py -3 _main/denoise-file-ab.py --arms A B            # subset
    py -3 _main/denoise-file-ab.py --neg-arm             # the streams are forced to differ
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FROZEN = os.path.join(HERE, "denoise-frozen")
RUNS = os.path.join(HERE, "denoise-runs")

MODEL = os.path.join(REPO, "worker", "models", "nemotron-3.5-asr-streaming-0.6b-int8")
CFG_FALSE = os.path.join(FROZEN, "config-false.json")
CFG_TRUE = os.path.join(FROZEN, "config-true.json")
ARMS = {
    "A": (os.path.join(FROZEN, "off", "sotto_worker.py"), CFG_FALSE, "off-worker  use_denoise:false"),
    "B": (os.path.join(FROZEN, "on", "sotto_worker.py"), CFG_FALSE, "on-worker   use_denoise:false"),
    "C": (os.path.join(FROZEN, "on", "sotto_worker.py"), CFG_TRUE, "on-worker   use_denoise:true "),
}
# Every one of these would otherwise leak in from whatever launched this script
# and silently change the subject. They are removed from every arm alike.
LEAKY = ("SOTTO_GATE", "SOTTO_AUDIO_FILE", "SOTTO_LANG_ID", "SOTTO_AUDIO_DEVICE",
         "SOTTO_FILE_TAP", "SOTTO_DEVICE", "SOTTO_NO_WORKER", "SOTTO_MODEL",
         "SOTTO_CONFIG", "SOTTO_PROVIDERS", "SOTTO_METER_HZ")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


# This box's console codec is cp1252 and cannot encode the box-drawing characters
# used to label each section; without this the report itself dies at the first
# separator and every run before it looks like a failure.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_one(arm, audio, threads, gate_on, tag, neg_arm):
    script, config, label = ARMS[arm]
    env = dict(os.environ)
    for k in LEAKY:
        env.pop(k, None)
    if gate_on:
        env["SOTTO_GATE"] = "1"
    # Same argv for every arm: the ONLY differences are the script path (A vs B)
    # and --config (B vs C). Absolute paths throughout, because the arms sit in
    # different directories from the real worker/.
    argv = [sys.executable, script, "--selftest", "--audio", audio,
            "--model", MODEL, "--config", config, "--threads", str(threads)]
    out_path = os.path.join(RUNS, "%s-%s.jsonl" % (arm, tag))
    err_path = os.path.join(RUNS, "%s-%s.err" % (arm, tag))
    peak_rss = 0
    cpu_s = 0.0
    t0 = time.time()
    with open(out_path, "wb") as fo, open(err_path, "wb") as fe:
        proc = subprocess.Popen(
            argv, cwd=os.path.dirname(script), env=env,
            stdout=fo, stderr=fe, stdin=subprocess.DEVNULL,
            creationflags=0x08000000 | 0x00000008,
        )
        # Sample RSS/CPU from OUTSIDE, at our own cadence: the worker's own
        # peak_rss_mb is its reading of itself, which is useful but is not an
        # independent measurement of what the switch cost.
        try:
            import psutil
            ps = psutil.Process(proc.pid)
            while proc.poll() is None:
                try:
                    peak_rss = max(peak_rss, ps.memory_info().rss)
                    ct = ps.cpu_times()
                    cpu_s = max(cpu_s, ct.user + ct.system)
                except Exception:
                    pass
                time.sleep(0.05)
        except ImportError:
            proc.wait()
    rc = proc.returncode
    wall = time.time() - t0
    res = parse(out_path, err_path)
    res.update(arm=arm, label=label, tag=tag, rc=rc, wall=round(wall, 2),
               outer_rss_mb=round(peak_rss / 1048576.0, 1), outer_cpu_s=round(cpu_s, 2),
               cores=round(cpu_s / wall, 2) if wall else None,
               script=script, config=config, out_path=out_path, err_path=err_path,
               raw=open(out_path, "rb").read())
    print("  %-2s %-4s rc=%-3s wall=%6.2fs  tokens=%-5s frames=%-5s vad=%-4s music=%-4s "
          "rss=%6.1fMB cores=%-5s  text=%d chars"
          % (arm, tag, rc, res["wall"], res.get("tokens"), res.get("frames"),
             res.get("vad_gated_chunks"), res.get("music_gated_chunks"),
             res["outer_rss_mb"], res["cores"], len(res.get("done_text") or "")))
    if neg_arm and arm == "B":
        # THE CONTROL. One caption's text is changed in B's stream ONLY. If the
        # A-vs-B comparison is any kind of real gate, this run MUST report a
        # difference and end AB-VERDICT FAIL. A gate that cannot go red on a
        # stream it should reject is not a gate -- so the control injects a
        # change of the kind this lane could plausibly have caused, which is a
        # caption that differs, not a line that disappears.
        old = b'"text": "Foca das miss'
        idx = res["raw"].find(old)
        if idx >= 0:
            at = res["raw"].index(b'"text": "', idx) + len(b'"text": "')
            endq = res["raw"].index(b'"', at)
            mutated = res["raw"][:at] + b"FALSO-controle" + res["raw"][endq:]
        else:
            mutated = res["raw"] + b'{"type":"status","state":"injected-control"}\n'
        res["raw"] = mutated
        with open(out_path, "wb") as fh:
            fh.write(mutated)
        res["neg_arm_applied"] = True
    return res


def parse(out_path, err_path):
    res = {"lines": [], "done": None, "denoise": None, "gate": None, "start": None}
    finals, partials = [], []
    with open(out_path, "rb") as fh:
        for raw in fh.read().decode("utf-8", "replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except ValueError:
                res["lines"].append({"type": "UNPARSEABLE", "raw": raw[:200]})
                continue
            res["lines"].append(obj)
            st = obj.get("state")
            if st == "selftest-done":
                res["done"] = obj
            elif st == "denoise":
                res["denoise"] = obj
            elif st == "gate":
                res["gate"] = obj
            elif st == "selftest-start":
                res["start"] = obj
            if obj.get("final") is True:
                finals.append(obj.get("text") or "")
            elif obj.get("final") is False and obj.get("text"):
                partials.append(obj.get("text") or "")
    d = res["done"] or {}
    res["done_text"] = d.get("text")
    res["tokens"] = d.get("tokens")
    res["frames"] = d.get("frames")
    res["vad_gated_chunks"] = d.get("vad_gated_chunks")
    res["music_gated_chunks"] = d.get("music_gated_chunks")
    res["empty_chunks"] = d.get("empty_chunks")
    res["blank_frac"] = d.get("blank_frac")
    res["rtf"] = d.get("rtf")
    res["infer_wall_s"] = d.get("infer_wall_s")
    res["inner_rss_mb"] = d.get("peak_rss_mb")
    res["audio_s"] = d.get("audio_s")
    res["final_text"] = " ".join(finals)
    res["partial_text"] = " ".join(partials)
    res["n_final"] = len(finals)
    res["n_partial"] = len(partials)
    err = open(err_path, "rb").read().decode("utf-8", "replace")
    res["err_tail"] = err.strip().splitlines()[-8:]
    return res


def nospace(s):
    return "".join((s or "").split())


# Fields that are INHERENTLY non-deterministic between two processes even when
# the code and the input are byte-identical: the pid, wall-clock timings and
# resident-memory readings. Everything else -- every caption's text/start/end,
# every counter (tokens/frames/vad/music/empty), every provider list -- is
# SUPPOSED to be byte-stable, and a difference in any of them is a real change.
# The mask is an ALLOWLIST of keys to ignore, and the report prints every key it
# masked so the reader can see the residual variance is exactly these.
RUN_TO_RUN_KEYS = frozenset((
    "pid", "load_s", "rss_mb", "peak_rss_mb", "cuda_dirs_ms", "provider_probe_ms",
    "infer_wall_s", "rtf", "wall_s", "elapsed_s", "duration_s",
))


def _mask(obj):
    if isinstance(obj, dict):
        return {k: ("<var>" if k in RUN_TO_RUN_KEYS else _mask(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mask(v) for v in obj]
    return obj


def records(raw):
    """Parsed JSONL records, with the denoise status line removed, as dicts."""
    out = []
    for ln in raw.decode("utf-8", "replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except ValueError:
            o = {"__unparseable__": ln[:120]}
        if o.get("state") == "denoise" and o.get("type") == "status":
            continue
        out.append(o)
    return out


def field_diff(a_recs, b_recs):
    """Structural diff of the two record streams, position by position.

    Returns (equal, detail) where detail lists the differing (index, key, av, bv).
    A length mismatch is reported too -- it is the signature of a dropped or
    added line that is NOT the denoise status (which was already removed).
    """
    if len(a_recs) != len(b_recs):
        return False, [{"index": "len", "a": len(a_recs), "b": len(b_recs)}]
    diffs = []
    for i, (a, b) in enumerate(zip(a_recs, b_recs)):
        am, bm = _mask(a), _mask(b)
        keys = set(am) | set(bm)
        for k in sorted(keys):
            if am.get(k) != bm.get(k):
                diffs.append({"index": i, "state": a.get("state") or a.get("type"),
                              "key": k, "a": am.get(k), "b": bm.get(k)})
    return (not diffs), diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default=os.path.join(HERE, "live-sample-cable-input-90s.wav"))
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--arms", nargs="*", default=["A", "B", "C"])
    ap.add_argument("--gate-on", action="store_true")
    ap.add_argument("--neg-arm", action="store_true",
                    help="append a line to every stream: the comparison must catch it")
    ap.add_argument("--json-out", default=os.path.join(RUNS, "summary.json"))
    a = ap.parse_args()

    for p in (a.audio, CFG_FALSE, CFG_TRUE):
        if not os.path.exists(p):
            print("ABORT: %s does not exist" % p)
            return 2
    os.makedirs(RUNS, exist_ok=True)
    print("audio   %s  %d B" % (a.audio, os.path.getsize(a.audio)))
    print("arms    %s   passes=%d  threads=%d  SOTTO_GATE=%s"
          % (a.arms, a.passes, a.threads, "1" if a.gate_on else "unset (file arm default: off)"))
    print("models  %s" % MODEL)

    runs = []
    order = []
    for p in range(1, a.passes + 1):
        for arm in a.arms:          # interleaved: A B C A B C
            tag = "p%d" % p
            order.append(arm)
            runs.append(run_one(arm, a.audio, a.threads, a.gate_on, tag, a.neg_arm))
    print("order   %s" % " ".join(order))

    problems = []
    by = {}
    for r in runs:
        by.setdefault(r["arm"], []).append(r)
        if r["rc"] != 0:
            problems.append("arm %s %s exited %s" % (r["arm"], r["tag"], r["rc"]))
        if r["done"] is None:
            problems.append("arm %s %s never emitted selftest-done" % (r["arm"], r["tag"]))
        for bad in r["lines"]:
            if bad.get("type") == "UNPARSEABLE":
                problems.append("arm %s %s emitted a non-JSON stdout line: %s"
                                % (r["arm"], r["tag"], bad["raw"]))

    # ── determinism control: same arm, same argv, twice ─────────────────────
    print("\n── determinism control (same arm twice, same argv) ──")
    for arm in a.arms:
        rs = by.get(arm) or []
        if len(rs) < 2:
            continue
        same_text = len({r["done_text"] for r in rs}) == 1
        same_cnt = len({(r["tokens"], r["frames"], r["vad_gated_chunks"], r["music_gated_chunks"])
                        for r in rs}) == 1
        rtfs = [r["rtf"] for r in rs if r["rtf"] is not None]
        spread = (max(rtfs) - min(rtfs)) / min(rtfs) if len(rtfs) > 1 and min(rtfs) else None
        print("  %-2s text_identical=%-5s counters_identical=%-5s rtf=%s  spread=%s"
              % (arm, same_text, same_cnt, rtfs, ("%.0f%%" % (spread * 100)) if spread is not None else "-"))
        if not same_text:
            problems.append("arm %s is not deterministic in its text" % arm)
        if not same_cnt:
            problems.append("arm %s is not deterministic in its counters" % arm)

    # ── A vs B: the additive claim ──────────────────────────────────────────
    print("\n── A vs B: does adding this lane move anything with the key false? ──")
    print("     (inherently-variable keys masked on both sides: %s)" % ", ".join(sorted(RUN_TO_RUN_KEYS)))
    if "A" in by and "B" in by:
        for pa, pb in zip(by["A"], by["B"]):
            ra, rb = records(pa["raw"]), records(pb["raw"])
            n_dn = sum(1 for o in pb["lines"] if o.get("state") == "denoise")
            ident, detail = field_diff(ra, rb)
            print("  %s/%s records=%d/%d  denoise_lines_in_B=%d  structurally_identical=%s"
                  % (pa["tag"], pb["tag"], len(ra), len(rb), n_dn, ident))
            if not ident:
                for d in detail[:12]:
                    print("     DIFF %s" % d)
                problems.append("A and B differ beyond the denoise status line (%s): %s"
                                % (pa["tag"], detail[:5]))
            if n_dn != 1:
                problems.append("B emitted %d denoise lines, expected exactly 1" % n_dn)
            for k in ("tokens", "frames", "vad_gated_chunks", "music_gated_chunks",
                      "empty_chunks", "blank_frac", "n_final", "n_partial"):
                if pa[k] != pb[k]:
                    problems.append("A/B %s differ on %s: %r vs %r" % (pa["tag"], k, pa[k], pb[k]))
            if pa["done_text"] != pb["done_text"]:
                problems.append("A/B %s text differs" % pa["tag"])
            if pa["done_text"] is not None and pa["final_text"] != pa["done_text"].strip():
                print("     note: A final-caption join != done.text (whitespace only: %s)"
                      % (nospace(pa["final_text"]) == nospace(pa["done_text"])))

    # ── B vs C: what the remover did ────────────────────────────────────────
    print("\n── B vs C: what the remover does, and what it costs ──")
    if "B" in by and "C" in by:
        for pb, pc in zip(by["B"], by["C"]):
            dc = pc["denoise"] or {}
            db = pb["denoise"] or {}
            print("  %s  B denoise=%s (%s) | C denoise=%s (%s) frame=%s hop=%s latency_ms=%s "
                  "min_gain_db=%s noise_bias=%s"
                  % (pc["tag"], db.get("denoise"), db.get("reason"), dc.get("denoise"),
                     dc.get("reason"), dc.get("frame"), dc.get("hop"), dc.get("latency_ms"),
                     dc.get("min_gain_db"), dc.get("noise_bias")))
            print("     C: tokens %s->%s  frames %s->%s  vad_gated %s->%s  music_gated %s->%s "
                  "empty %s->%s  blanks_frac %s->%s"
                  % (pb["tokens"], pc["tokens"], pb["frames"], pc["frames"],
                     pb["vad_gated_chunks"], pc["vad_gated_chunks"],
                     pb["music_gated_chunks"], pc["music_gated_chunks"],
                     pb["empty_chunks"], pc["empty_chunks"],
                     pb["blank_frac"], pc["blank_frac"]))
            print("     cost  rtf %s -> %s   infer_wall_s %s -> %s   rss(inner) %s -> %s   "
                  "rss(outer) %s -> %s   cores %s -> %s"
                  % (pb["rtf"], pc["rtf"], pb["infer_wall_s"], pc["infer_wall_s"],
                     pb["inner_rss_mb"], pc["inner_rss_mb"],
                     pb["outer_rss_mb"], pc["outer_rss_mb"], pb["cores"], pc["cores"]))
            for k in ("music_gated_chunks",):
                if pb[k] != pc[k]:
                    print("     NOTE %s moved %s->%s" % (k, pb[k], pc[k]))
            t_same = nospace(pb["done_text"]) == nospace(pc["done_text"])
            t_raw = pb["done_text"] == pc["done_text"]
            print("     text identical=%s   identical_without_spaces=%s" % (t_raw, t_same))
            print("     B text: %r" % (pb["done_text"] or "")[:400])
            print("     C text: %r" % (pc["done_text"] or "")[:400])

    summary = {
        "audio": a.audio, "audio_bytes": os.path.getsize(a.audio),
        "threads": a.threads, "passes": a.passes, "gate_on": a.gate_on,
        "order": order, "problems": problems,
        "runs": [{k: v for k, v in r.items() if k != "raw"} for r in runs],
        "stream_sha256": {r["arm"] + r["tag"]: sha_bytes(r["raw"]) for r in runs},
        "masked_run_to_run_keys": sorted(RUN_TO_RUN_KEYS),
        "ab_structural_diff": {
            ("A" + ra_["tag"] + "|B" + rb_["tag"]): field_diff(records(ra_["raw"]), records(rb_["raw"]))[1]
            for ra_, rb_ in zip(by.get("A", []), by.get("B", []))
        },
    }
    with open(a.json_out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False, default=str)
    print("\nsummary %s  %d B" % (a.json_out, os.path.getsize(a.json_out)))

    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  - %s" % p)
        if a.neg_arm:
            # In --neg-arm the A/B difference IS the injected control, so a FAIL
            # here is the CORRECT outcome. Saying only "FAIL" would leave the
            # reader unable to tell a working control from a broken gate.
            ab_problems = [p for p in problems if "A and B differ" in p]
            if ab_problems and len(problems) == len(ab_problems):
                print("NEG-ARM VERDICT PASS -- the comparison CAUGHT the injected "
                      "difference in B (%s)" % ab_problems[0][:120])
                return 0
        print("AB-VERDICT FAIL")
        return 1
    if a.neg_arm:
        print("NEG-ARM VERDICT FAIL -- the control was injected and the comparison "
              "still passed: the A/B gate cannot detect a difference")
        return 1
    print("AB-VERDICT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())