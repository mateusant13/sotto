"""ORACLE for the LIVE capture DELIVERY RATE of `worker/sotto_worker.py`.

THE HOLE THIS CLOSES (ticket #610, docs/audit/oracles.md §3)
------------------------------------------------------------
Eleven oracles read the worker's JSONL/`WORKER_STATS` and **none** asserted the
audio delivery rate. The strongest block assertion anywhere was `blocks >= 20`
(`_main/device-silence-oracle.py`), i.e. an implicit rate floor of 0.10 — a tap
that delivered 35 % of the audio passed every one of them, and `queue_drops` had
**no reader at all**. The number was already printed; nothing compared it to
anything.

THE ASSERTION
-------------
    audio_s / wall_s >= 0.95     AND     queue_drops == 0

`audio_s` and `queue_drops` are the counters `worker/sotto_worker.py` already
prints in its `WORKER_STATS` line (the `stats_line()` format string, and the
`on_block()` counters it reports). The oracle reads them; it does not compute a
new quantity from the raw audio.

MEASUREMENT LAW (paid for twice today, 2026-10-06 — `_main/_diary-src.md`)
-------------------------------------------------------------------------
`wall_s` is counted **from the moment the STREAM OPENED**, never from process
start. The startup (model load + device open) is several seconds; dividing
`audio_s` by the full process wall produces a FALSE duty of ~0.37 where the truth
is 1.00. Concretely, `t_open` is the arrival time of the worker's own
`{"state":"capture-started"}` (live arm) or `{"state":"selftest-start"}` (file
arm), and `t_end` is the arrival time of `{"state":"done"}` /
`{"state":"selftest-done"}`. Every ratio this oracle prints carries its numerator
AND its denominator on the same line.

ARMS
----
* default (no flag)      — a LIVE run, capture from the device. This is the arm
                           that can go RED: with the pre-fix WASAPI poll
                           (`wasapi_loopback.py` period = block_ms/1000/4 = 25 ms
                           against a 22 ms ring) it measured duty 0.815; after the
                           fix (period = min(0.005, …)) it measures ~1.00.
* `--wav PATH`           — the CONTROL, the file arm: `SOTTO_AUDIO_FILE=<wav>`.
                           It opens no device and takes the np.interp resample
                           path (the sample is 22050 Hz), and it must stay GREEN.
* `--mutant pump|drop`   — a LIVE run whose worker is a COPY patched back to the
                           defect. `pump` = the old 25 ms poll; `drop` = `on_block`
                           discards 2 of 3 blocks before the queue. Both MUST go
                           RED; that is what makes the green non-vacuous.

`--selftest` runs the control arm for real, asserts it is GREEN under the shipped
threshold, and asserts the SAME numbers go RED when the threshold is inverted —
so the threshold is shown to participate in the verdict instead of being hard
coded green. It also runs three synthetic fixtures (green / lossy / queue-dropped)
through the identical evaluator.

Exit codes: 0 PASS, 1 FAIL, 2 setup error, 4 UNMEASURED (no single stream was
opened, so the arm proves nothing — never reported as a pass).

No window: the worker child is spawned with CREATE_NO_WINDOW alone (0x08000000),
never | DETACHED_PROCESS (that yields 0 bytes, rc 0). The oracle itself is meant
to be launched with pythonw, output redirected to a file.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER_DIR = os.path.join(REPO, "worker")
WORKER = os.path.join(WORKER_DIR, "sotto_worker.py")
CONFIG = os.path.join(WORKER_DIR, "config.json")
WAV = os.path.join(HERE, "pt-br-sample.wav")
RUNS = os.path.join(WORKER_DIR, "runs")
MUTANT_DIR = os.path.join(RUNS, "_delivery-rate-mutant")
LOG = os.path.join(HERE, "delivery-rate-oracle.log")

CREATE_NO_WINDOW = 0x08000000
THRESHOLD = 0.95
LIVE_SECONDS = 15.0          # window; equal to the tap window below so the run
TAP_WINDOW = 15.0            # cannot rotate to a second device mid-measurement
TIMEOUT_S = 180.0
TARGET_SR = 16000

STATS_RE = re.compile(r"^WORKER_STATS tag=(\S+)\s+(.*)$")

_logf = None


def log(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    if _logf:
        _logf.write(line + "\n")
        _logf.flush()


def parse_kv(s):
    out = {}
    for tok in s.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
    return out


def python_exe():
    """pythonw.exe if it sits beside the interpreter (no console at all)."""
    exe = sys.executable or ""
    cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return cand if os.path.exists(cand) else exe


def run_worker(argv, env_extra=None, timeout=TIMEOUT_S):
    """Spawn the worker, timestamp its own lifecycle events as their lines ARRIVE.

    Returns a raw dict of observations. The arrival timestamps are the whole point:
    the worker's lines carry no clock, so 'when did the stream open' is only
    knowable by the reader.
    """
    env = dict(os.environ)
    env.pop("SOTTO_AUDIO_FILE", None)  # never inherit a file arm into a live arm
    if env_extra:
        env.update(env_extra)
    p = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO,
        env=env,
        creationflags=CREATE_NO_WINDOW,
    )
    stats = []          # (t, tag, counters)
    stderr_lines = []

    def drain_err():
        try:
            for raw in iter(p.stderr.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                stderr_lines.append(line)
                m = STATS_RE.match(line)
                if m:
                    stats.append((time.monotonic(), m.group(1), parse_kv(m.group(2))))
        except Exception:
            pass

    th = threading.Thread(target=drain_err, daemon=True)
    th.start()

    killer = threading.Timer(timeout, lambda: p.kill())
    killer.daemon = True
    killer.start()

    t_open = t_end = None
    streams = rotations = 0
    done = None
    capture_evt = None
    raw_lines = 0
    try:
        for raw in iter(p.stdout.readline, b""):
            t = time.monotonic()
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            raw_lines += 1
            st = obj.get("state")
            if st == "capture-started":
                streams += 1
                if capture_evt is None:
                    capture_evt = obj
                if t_open is None:
                    t_open = t
            elif st == "selftest-start":
                streams += 1
                if t_open is None:
                    t_open = t
            elif st == "device-rotated":
                rotations += 1
            elif st in ("done", "selftest-done"):
                done = obj
                t_end = t
    finally:
        killer.cancel()
        rc = p.wait()
        th.join(10)

    return {
        "rc": rc,
        "t_open": t_open,
        "t_end": t_end,
        "capture": capture_evt,
        "streams": streams,
        "rotations": rotations,
        "done": done,
        "stats": stats,
        "stderr": stderr_lines,
        "raw_lines": raw_lines,
    }


def build_record(arm, obs, note=""):
    rec = {
        "arm": arm,
        "note": note,
        "rc": obs["rc"],
        "streams": obs["streams"],
        "rotations": obs["rotations"],
        "wall_s": None,
        "audio_s": None,
        "captured_s": None,
        "blocks": None,
        "block_samples": None,
        "queue_drops": 0,
        "queue_source": "n/a",
        "stats_done_agree": None,
        "open_event": None,
        "end_event": None,
        "rate": None,
        "block": None,
        "captured_s_by_blocks": None,
    }
    finale = None
    for t, tag, c in obs["stats"]:
        if tag == "final":
            finale = c
    done = obs["done"] or {}
    live = arm.startswith("live")
    rec["open_event"] = "capture-started" if live else "selftest-start"
    rec["end_event"] = "done" if live else "selftest-done"

    if obs["t_open"] is None or obs["t_end"] is None:
        rec["note"] = (rec["note"] + " ").strip() + "no open/end event seen"
        return rec
    rec["wall_s"] = obs["t_end"] - obs["t_open"]
    cap = obs.get("capture") or {}
    rec["rate"] = int(cap.get("rate") or TARGET_SR)
    rec["block"] = cap.get("block")

    if live:
        # Counters per the brief: the worker's own WORKER_STATS line.
        src = finale
        rec["queue_source"] = "WORKER_STATS.tag=final"
        if src is None:
            src = done
            rec["queue_source"] = "done (no tag=final seen)"
        rec["audio_s"] = float(src.get("audio_s", done.get("audio_s")))
        rec["queue_drops"] = int(float(src.get("queue_drops", 0)))
        if "blocks" in src:
            rec["blocks"] = int(float(src["blocks"]))
        if "block_samples" in src:
            rec["block_samples"] = int(float(src["block_samples"]))
        # Cross-check the two emitters of the SAME variable (stderr stats_line and
        # the stdout `done` payload). Disagreement means one of my two readers is
        # wrong, which is itself a finding.
        if finale is not None and "audio_s" in done:
            rec["stats_done_agree"] = abs(float(finale["audio_s"]) - float(done["audio_s"])) <= 0.011
    else:
        rec["audio_s"] = float(done.get("audio_s"))
        # The file arm has no queue: selftest() calls run_chunk() synchronously, so
        # there is no queue to overflow and no queue_drops counter to read.
        rec["queue_source"] = "n/a (file arm has no queue)"
    if rec["block_samples"] is not None:
        # The tap delivers at the endpoint's NATIVE rate (48 kHz for a WASAPI
        # loopback), not at TARGET_SR — so captured seconds must divide by the
        # rate the run itself declared, or the ratio is a fiction.
        rec["captured_s"] = rec["block_samples"] / float(rec["rate"])
        if rec["blocks"] and rec["block"]:
            # Second, independent denominator for the same numerator: N blocks of
            # `block` frames is N*block/rate seconds of audio handed over.
            rec["captured_s_by_blocks"] = rec["blocks"] * rec["block"] / float(rec["rate"])
    return rec


def evaluate(rec, threshold=THRESHOLD, invert=False):
    """The one verdict function. `invert` flips ONLY the threshold comparison, so
    `--selftest` can prove the threshold is load-bearing."""
    reasons = []
    if rec["wall_s"] is None or rec["audio_s"] is None:
        return False, ["UNMEASURED: " + rec["note"]], None
    duty = rec["audio_s"] / rec["wall_s"] if rec["wall_s"] > 0 else float("nan")
    ok = (duty <= threshold) if invert else (duty >= threshold)
    if not ok:
        reasons.append(
            f"duty {duty:.4f} {'<=' if invert else '>='} {threshold} is false"
        )
    if not invert:
        if rec["queue_drops"] != 0:
            reasons.append(f"queue_drops {rec['queue_drops']} != 0")
        if rec["streams"] != 1:
            reasons.append(
                f"streams={rec['streams']} (the measurement window is not a single "
                f"stream; {rec['rotations']} rotation(s)) — arm proves nothing"
            )
    return (not reasons), reasons, duty


def report(rec, threshold=THRESHOLD, invert=False):
    ok, reasons, duty = evaluate(rec, threshold, invert)
    tag = "PASS" if ok else "RED "
    n = rec["audio_s"]
    d = rec["wall_s"]
    if duty is None:
        log(f"[{tag}] ARM={rec['arm']:18} {reasons[0]}")
        return ok, duty
    log(
        f"[{tag}] ARM={rec['arm']:18} duty = numerator audio_s={n:.2f} / "
        f"denominator wall_s={d:.2f} = {duty:.4f}  (threshold {threshold}"
        f"{', INVERTED' if invert else ''})  queue_drops={rec['queue_drops']} "
        f"[{rec['queue_source']}]"
    )
    if rec.get("captured_s") is not None:
        cd = rec["captured_s"] / d
        log(
            f"        tap: numerator block_samples/{rec['rate']}={rec['captured_s']:.2f} / "
            f"denominator wall_s={d:.2f} = {cd:.4f}  "
            f"({rec['blocks']} blocks x {rec['block']} frames @{rec['rate']} = "
            f"{rec.get('captured_s_by_blocks'):.2f} s; informational: what the tap handed over)"
        )
    if rec["stats_done_agree"] is not None:
        log(f"        WORKER_STATS.final vs done agree on audio_s: {rec['stats_done_agree']}")
    log(
        f"        open=({rec['open_event']}) end=({rec['end_event']}) "
        f"streams={rec['streams']} rotations={rec['rotations']} rc={rec['rc']}"
    )
    for r in reasons:
        log(f"        REASON: {r}")
    return ok, duty


# ── mutant builder (the arms that MUST be RED) ───────────────────────────────

PUMP_OLD = "        period = max(0.005, self.block_ms / 1000.0 / 4.0)"
PUMP_NEW = "        period = min(0.005, max(0.001, self.block_ms / 1000.0 / 20.0))"
DROP_ANCHOR = (
    '        counters["sumsq"] += float((block.astype("float64") ** 2).sum())\n'
    "        try:\n"
    "            audio_q.put_nowait(block)"
)
DROP_PATCH = (
    '        counters["sumsq"] += float((block.astype("float64") ** 2).sum())\n'
    "        if counters[\"blocks\"] % 3:\n"          # keep only 1 of every 3 blocks
    "            return\n"
    "        try:\n"
    "            audio_q.put_nowait(block)"
)


def build_mutant(spec):
    """Copy the worker + its two local modules, patch the COPY, return its path.

    Never edits the shipped file. `--model`/`--config` are passed absolute because
    the copy's HERE is the mutant dir, not worker/.
    """
    if os.path.isdir(MUTANT_DIR):
        shutil.rmtree(MUTANT_DIR)
    os.makedirs(MUTANT_DIR)
    for name in ("sotto_worker.py", "wasapi_loopback.py", "lang_prompt.py"):
        shutil.copyfile(os.path.join(WORKER_DIR, name), os.path.join(MUTANT_DIR, name))
    if spec == "pump":
        path = os.path.join(MUTANT_DIR, "wasapi_loopback.py")
        old, new = PUMP_NEW, PUMP_OLD
    elif spec == "drop":
        path = os.path.join(MUTANT_DIR, "sotto_worker.py")
        old, new = DROP_ANCHOR, DROP_PATCH
    else:
        raise SystemExit(f"unknown mutant {spec!r} (use pump|drop)")
    src = io.open(path, encoding="utf-8").read()
    if src.count(old) != 1:
        raise SystemExit(
            f"mutant {spec}: anchor occurs {src.count(old)} times in {path} — "
            f"the tree changed; the oracle refuses to patch blind"
        )
    patched = src.replace(old, new, 1)
    if patched == src:
        raise SystemExit(f"mutant {spec}: patch was a NO-OP in {path} — refusing to run it")
    io.open(path, "w", encoding="utf-8").write(patched)
    return os.path.join(MUTANT_DIR, "sotto_worker.py")


def model_dir_abs():
    with io.open(CONFIG, encoding="utf-8") as f:
        d = json.load(f)["model"]["dir"]
    return d if os.path.isabs(d) else os.path.join(WORKER_DIR, d)


# ── arms ─────────────────────────────────────────────────────────────────────

def arm_live(mutant=None):
    arm = "live" if not mutant else f"live-{mutant}-mutant"
    script = WORKER
    note = "capture from the device, fixed pump"
    if mutant:
        script = build_mutant(mutant)
        note = f"LIVE run of a patched COPY ({mutant})"
    argv = [
        python_exe(),
        script,
        "--config", CONFIG,
        "--max-seconds", str(LIVE_SECONDS),
        "--tap-window", str(TAP_WINDOW),
        "--stats-interval", "0",
    ]
    if mutant:
        argv += ["--model", model_dir_abs()]
    obs = run_worker(argv)
    return build_record(arm, obs, note)


def arm_wav(path=WAV):
    obs = run_worker([python_exe(), WORKER, "--config", CONFIG], {"SOTTO_AUDIO_FILE": path})
    return build_record("wav-control", obs, f"SOTTO_AUDIO_FILE={os.path.basename(path)}")


# ── selftest ─────────────────────────────────────────────────────────────────

def synthetic(arm, audio_s, wall_s, drops, streams=1):
    return {
        "arm": arm, "note": "", "rc": 0, "streams": streams, "rotations": 0,
        "wall_s": wall_s, "audio_s": audio_s, "captured_s": None, "blocks": None,
        "block_samples": None, "queue_drops": drops,
        "queue_source": "synthetic", "stats_done_agree": None,
        "open_event": "synthetic", "end_event": "synthetic",
    }


def selftest(threshold):
    """The gate must be able to go RED, and the threshold must be load-bearing."""
    ok_all = True
    log("== selftest: fixtures through the SAME evaluator ==")
    cases = [
        ("fix-green", synthetic("fixture-green", 14.63, 14.83, 0), True),
        ("fix-lossy", synthetic("fixture-lossy", 4.90, 14.83, 0), False),
        ("fix-mdrops", synthetic("fixture-drops", 14.63, 14.83, 7), False),
    ]
    for label, rec, want in cases:
        got, _ = report(rec, threshold)
        verdict = "ok" if got == want else "WRONG"
        if got != want:
            ok_all = False
        log(f"  {label}: expected {'GREEN' if want else 'RED'} got {'GREEN' if got else 'RED'} -> {verdict}")

    log("")
    log("== selftest: the CONTROL arm (real run), then the same numbers inverted ==")
    rec = arm_wav()
    green, _ = report(rec, threshold)
    red, _ = report(rec, threshold, invert=True)
    if not green:
        ok_all = False
        log("  WRONG: the control arm is not GREEN under the shipped threshold")
    if red:
        ok_all = False
        log("  WRONG: the control arm did not go RED when the threshold was inverted")
    if green and not red:
        log("  ok: control GREEN under the shipped rule, RED when the threshold is inverted")
    log(f"  (control duty={rec['audio_s']}/{rec['wall_s']})")
    log("")
    log("SELFTEST:", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


def main():
    global _logf
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wav", nargs="?", const=WAV, default=None,
                    help="CONTROL arm: transcribe this file, no device (default %(const)s)")
    ap.add_argument("--mutant", choices=["pump", "drop"], default=None,
                    help="LIVE arm with a patched COPY: pump = pre-fix 25 ms poll; drop = on_block drops 2 of 3")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--invert-threshold", action="store_true",
                    help="flip the comparison, to show the threshold participates")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--all", action="store_true", help="live + wav + both mutants")
    args = ap.parse_args()

    _logf = io.open(LOG, "w", encoding="utf-8")
    log(f"# delivery-rate-oracle  {time.strftime('%Y-%m-%dT%H:%M:%S')}  "
        f"threshold={args.threshold}  invert={args.invert_threshold}")
    log(f"# worker={WORKER}")
    log("")

    if args.selftest:
        return selftest(args.threshold)

    recs = []
    if args.all:
        recs = [arm_live(), arm_wav(), arm_live("pump"), arm_live("drop")]
    elif args.mutant:
        recs = [arm_live(args.mutant)]
    elif args.wav is not None:
        recs = [arm_wav(args.wav)]
    else:
        recs = [arm_live()]

    worst = 0
    for rec in recs:
        ok, _ = report(rec, args.threshold, invert=args.invert_threshold)
        if not ok:
            worst = 1
    log("")
    log("VERDICT:", "PASS" if worst == 0 else "RED")
    return worst


if __name__ == "__main__":
    sys.exit(main())
