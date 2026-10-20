"""Is `use_vad` LIVE in onnxruntime-genai 0.17.1, or an inert option?

The VAD-on/VAD-off selftest arms produced byte-identical transcripts, which has
TWO possible causes and they are not the same claim:
  (a) VAD ran and simply never met its own trigger on this clip (silence 3360 ms
      inside a 13.4 s continuous read has nowhere to fire), or
  (b) the option is not consumed at all by this genai build.

`get_option` is the instrument: it reads back what the processor holds. Then the
discriminator is a DIGITAL-SILENCE chunk (0.0 everywhere), which (a) predicts is
gated/dropped by a live VAD and (b) predicts is passed through unchanged by an
inert one.

THE GATE ALSO JUDGES THE WORKER, because the option being LIVE is only half of
the claim: the shipped `worker/sotto_worker.py` must HANDLE the `None` that a
gated chunk returns. Unhandled, it raised `TypeError: 'NoneType' object is not
subscriptable` and the whole worker EXITED 1 on the first pause longer than
3.36 s. That half is a STATIC check on the file, and it is what the negative
arm mutates.

NEGATIVE ARM. `--neg-arm` runs the STATIC checks against MUTANTS: a COPY of
`worker/sotto_worker.py` with the VAD gate removed, and a COPY of
`worker/config.json` with `use_vad` turned off. The mutants are TEXTUAL, on an
EXACT anchor; before an anchor is used it is COUNTED in the file. An anchor that
is missing (the oracle is stale) or that appears more than once (the mutation
would hit the wrong place) is DECORATIVE: it proves nothing, so the oracle
refuses to count it, says so, and exits 2. A mutant that was applied but left a
check green is reported as SURVIVED -- the gate is blind there.

EXIT CODES
  normal run   0 = PASS ("VERDICT: PASS"), 1 = FAIL
  --neg-arm    1 = PASS BY DESIGN (the negative arm is SUPPOSED to find the
                 defect; the battery's :expectred recorder asks for exactly that),
                 0 = a mutant was NOT caught, 2 = setup error (a decorative
                 mutant).

usage: py -3 _main/vad-option-probe.py [--neg-arm]
"""
import atexit
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG = os.path.join(ROOT, "worker", "config.json")
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_SETUP = 2

# THE VAD GATE, verbatim, as worker/sotto_worker.py writes it. It must occur
# EXACTLY ONCE: the anchor is the block, and the block is what the mutant
# removes.
GUARD_LINES = [
    "        if feats is None:",
    "            if account:",
    "                self.vad_gated_chunks += 1",
    "                self.n_chunks += 1",
    "                self.audio_s += len(pcm_chunk) / TARGET_SR",
    "                self.wall += time.time() - t_start",
    '            return "", 0',
]
GUARD_REPLACEMENT = (
    '        raise TypeError("the mutant removed the VAD gate: '
    "'NoneType' object is not subscriptable\")"
)

# THE MUTANTS: each is a file this oracle judges, an EXACT anchor in it, and the
# replacement. The anchor is matched with the FILE's own EOL.
MUTANTS = [
    {
        "tag": "M1 the worker stops handling the None a live VAD returns",
        "file": "worker/sotto_worker.py",
        "kind": "worker",
        "anchor_lines": GUARD_LINES,
        "replacement_lines": [GUARD_REPLACEMENT],
    },
    {
        "tag": "M2 the shipped config turns use_vad off",
        "file": "worker/config.json",
        "kind": "config",
        "anchor_lines": ['    "use_vad": true,'],
        "replacement_lines": ['    "use_vad": false,'],
    },
]


def find_anchor(text, lines):
    """(anchor, hits): the block as THIS file writes it, and how many times it is
    there. The EOL is the file's own; a one-line anchor is the same string in
    both EOLs, so it is only counted once."""
    anchor = None
    hits = 0
    seen = set()
    for eol in ("\r\n", "\n"):
        candidate = eol.join(lines)
        if candidate in seen:
            continue
        seen.add(candidate)
        n = text.count(candidate)
        if n:
            hits += n
            if anchor is None:
                anchor = candidate
    return anchor, hits


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def check_config(cfg):
    """The SHIPPED setting: `use_vad` is ON, and the model it names is there."""
    fails = []
    vad = cfg.get("model", {}).get("use_vad")
    if vad is not True:
        fails.append("worker/config.json does not ship use_vad=true (it is %r)" % (vad,))
    d = cfg.get("model", {}).get("dir")
    if not d or not os.path.isdir(os.path.join(ROOT, "worker", d)):
        fails.append("the model directory named by worker/config.json is not there: %r" % (d,))
    return fails


def check_worker_gate(path):
    """The worker must HANDLE the `None` that a live VAD returns."""
    fails = []
    text = read_text(path)
    anchor, hits = find_anchor(text, GUARD_LINES)
    if hits != 1:
        fails.append("the VAD gate in %s appears %d time(s) -- %s"
                     % (os.path.basename(path), hits,
                        "the oracle is stale" if hits == 0 else "the anchor is AMBIGUOUS"))
        return fails
    if 'return "", 0' not in anchor:
        fails.append("the VAD gate does not return an empty caption")
    if "self.vad_gated_chunks += 1" not in anchor:
        fails.append("the VAD gate does not count the gated chunk")
    if "self.audio_s += len(pcm_chunk) / TARGET_SR" not in anchor:
        fails.append("the VAD gate does not advance the clock: a gated chunk is real elapsed audio")
    return fails


# ── the runtime arms: is the option consumed at all? ─────────────────────────

def run_runtime(p, model_dir):
    """The two arms, on the real model. Returns (fails, summary)."""
    import numpy as np
    import onnxruntime_genai as og

    with open(os.path.join(model_dir, "genai_config.json"), "r", encoding="utf-8") as fh:
        chunk_samples = json.load(fh)["model"]["chunk_samples"]
    p("model_dir      :", os.path.basename(model_dir))
    p("chunk_samples  :", chunk_samples)

    chunk = chunk_samples
    silence = np.zeros(chunk, dtype=np.float32)
    # Speech-like: a 440 Hz tone at full scale, the same shape the inject probe used.
    t = np.arange(chunk, dtype=np.float32) / 16000.0
    tone = (0.98 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

    def drain(proc, x):
        out = proc.process(x)
        if out is None:
            return None
        af = out["audio_features"]
        af = af.as_numpy() if hasattr(af, "as_numpy") else np.asarray(af)
        return af

    def run(use_vad, label):
        model = og.Model(model_dir)
        proc = model.create_streaming_processor()
        proc.set_option("use_vad", "1" if use_vad else "0")
        p(f"--- arm {label}: requested use_vad={'1' if use_vad else '0'} ---")
        for key in ("use_vad", "vad", "silence_duration_ms", "prefix_padding_ms", "threshold"):
            try:
                p("    get_option(%r) = %r" % (key, proc.get_option(key)))
            except Exception as exc:                                # noqa: BLE001
                p("    get_option(%r) raised %s: %s" % (key, type(exc).__name__, exc))
        # warm with one speech chunk so the VAD has a "speech" context, then silence
        warm = [drain(proc, tone) for _ in range(3)]
        sil = [drain(proc, silence) for _ in range(12)]
        shape = lambda a: None if a is None else tuple(a.shape)
        zero = lambda a: None if a is None else float(np.abs(a).max())
        p("    warm tone   ->", [shape(a) for a in warm], "peaks", [zero(a) for a in warm])
        p("    silence x12 ->",
          [(shape(a), None if a is None else round(zero(a), 6)) for a in sil])
        return sil

    a = run(False, "off")
    b = run(True, "on")

    same_shapes = [None if x is None else tuple(x.shape) for x in a] == [
        None if x is None else tuple(x.shape) for x in b]
    none_counts = {"off": sum(1 for x in a if x is None), "on": sum(1 for x in b if x is None)}
    p("silence SHAPES identical off vs on :", same_shapes)
    p("silence None counts                :", none_counts)

    fails = []
    if none_counts["off"] != 0:
        fails.append("with use_vad=0 the digital silence was gated %d time(s) -- the option "
                     "is not the discriminator the claim assumes" % none_counts["off"])
    if none_counts["on"] == 0:
        fails.append("with use_vad=1 the digital silence was NEVER gated -- the option is INERT")
    if same_shapes:
        fails.append("the two arms produced the same shapes -- the option changes nothing")
    return fails, none_counts


# ── the negative arm ─────────────────────────────────────────────────────────

def neg_arm(p):
    tmpdir = tempfile.mkdtemp(prefix="sotto-vad-neg-", dir=os.environ.get("TMPDIR") or None)
    atexit.register(shutil.rmtree, tmpdir, True)
    caught = 0
    decorative = 0
    for idx, m in enumerate(MUTANTS):
        src = os.path.join(ROOT, m["file"])
        if not os.path.isfile(src):
            decorative += 1
            p("  RED   mutant %-64s FILE MISSING -- DECORATIVE, not counted" % m["tag"])
            continue
        text = read_text(src)
        anchor, hits = find_anchor(text, m["anchor_lines"])
        if hits != 1:
            decorative += 1
            p("  RED   mutant %-64s ANCHOR %s (%d hit(s)) -- DECORATIVE, not counted"
              % (m["tag"], "MISSING" if hits == 0 else "AMBIGUOUS", hits))
            continue
        eol = "\r\n" if "\r\n" in anchor else "\n"
        replacement = eol.join(m["replacement_lines"])
        mutated = text.replace(anchor, replacement, 1)
        if mutated == text:
            decorative += 1
            p("  RED   mutant %-64s ANCHOR applied to NOTHING -- DECORATIVE, not counted" % m["tag"])
            continue
        copy = os.path.join(tmpdir, "mutant-%d-%s" % (idx, os.path.basename(m["file"])))
        with open(copy, "w", encoding="utf-8", newline="") as fh:
            fh.write(mutated)
        try:
            if m["kind"] == "worker":
                fails = check_worker_gate(copy)
            else:
                with open(copy, "r", encoding="utf-8") as fh:
                    fails = check_config(json.load(fh))
        except Exception as exc:                                    # noqa: BLE001
            p("  RED   mutant %-64s did not even run (%s: %s) -- NOT counted"
              % (m["tag"], type(exc).__name__, str(exc)[:80]))
            decorative += 1
            continue
        if fails:
            caught += 1
            p("  GREEN mutant %-64s caught by: %s" % (m["tag"], "; ".join(fails[:2])))
        else:
            p("  RED   mutant %-64s SURVIVED -- the gate is blind here" % m["tag"])

    control = check_worker_gate(WORKER)
    with open(CONFIG, "r", encoding="utf-8") as fh:
        control += check_config(json.load(fh))
    p("  CONTROL (the live files) :", "GREEN, as required" if not control else "; ".join(control))
    total = len(MUTANTS)
    ok = (caught == total and decorative == 0 and not control)
    p("")
    p("NEG-ARM " + ("PASS" if ok else "FAIL")
      + " -- mutants %d/%d caught, %d decorative" % (caught, total, decorative))
    if decorative:
        # A decorative mutant is worse than no mutant at all: the oracle cannot say
        # NO about a file whose anchor it did not find. Setup error.
        return EXIT_SETUP
    if not ok:
        return 0
    # rc=1 BY DESIGN: the negative arm is SUPPOSED to find the defect, so "found it"
    # is a non-zero exit -- the battery's :expectred recorder asks for exactly that.
    return 1


def main():
    neg = "--neg-arm" in sys.argv
    p = print

    if neg:
        return neg_arm(p)

    with open(CONFIG, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    model_dir = os.path.join(ROOT, "worker", cfg["model"]["dir"])

    fails = check_config(cfg)
    fails += check_worker_gate(WORKER)
    if fails:
        p("SETUP ERROR: the static checks failed before the runtime arms:")
        for f in fails:
            p("  " + f)
        p("")
        p("VERDICT: FAIL -- the shipped setting or the worker's VAD gate is not there")
        return EXIT_FAIL

    runtime_fails, counts = run_runtime(p, model_dir)
    fails += runtime_fails

    p("")
    p("VERDICT: " + ("PASS" if not fails else "FAIL")
      + " -- use_vad is LIVE (silence gated %d/12 with it on, %d/12 with it off) and the "
      "worker handles the gated chunk" % (counts["on"], counts["off"]))
    for f in fails:
        p("  wrong: " + f)
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
