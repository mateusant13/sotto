"""Lane-3 probe: the worker's `done.verdict` table, asserted with NO model and NO device.

WHAT THIS PROVES (F3, and the F13 default it shares a code path with)

  1. `worker.sotto_worker` imports WITHOUT running `main()` — the module carries an
     `if __name__ == "__main__":` guard and importing it writes nothing to stdout
     or stderr (checked first, before the import, by reading the source).
  2. `decide_verdict(counters, outcome, ran_but_silent) -> str` has the FROZEN
     signature the gate lane writes against, is PURE (its counters argument comes
     back unchanged and the answer is repeatable), and returns `captions-emitted`
     ONLY when `captions > 0`.
  3. Every verdict word that existed before the F3 cure is still returned by its
     OWN counters, in the same order: `ran_but_silent` first, then the device
     ladder's outcome, then the stage counters one by one.
  4. `captions == 0` with an ALIVE tap and no no-audio evidence returns the new
     honest word `captions-zero` — the shape the unconditional `else` used to call
     `captions-emitted` — and so does the chunk-exception shape, which reaches the
     same counters (an `error` status was emitted, `stop` was set, no caption can
     follow).
  5. A SWEEP over the counter grid: no combination with `captions == 0` returns
     `captions-emitted`, and no combination returns a word outside the frozen
     vocabulary.
  6. F13, in a CHILD process (`main()` with a config that has no `model.lang_id`
     and a model dir that does not exist, so the run stops at the `model` stage):
     an ABSENT key resolves to the model's own auto slot (`source=default:auto`,
     lang_id 101) instead of the host locale; an EXPLICIT `"os"` still resolves to
     the host locale; a config that NAMES the key logs `source=config:…`. No model
     is loaded and no audio device is opened (the run returns 2 before either).

WHAT THIS CANNOT PROVE (named falsifier, in the receipt)

  Nothing here exercises `run_chunk`, so the PER-FRAME `max_symbols_per_step`
  ceiling (F11), the fresh front end (F12), the label bound and the text cap (F17)
  are unmeasured here: they need the real ONNX graphs. The falsifier for the front
  end is a probe that re-decodes ONE segment through the OLD pass (live `asr.sp`)
  and the NEW pass (`fresh_processor()`) and diffs the two texts; for the ceiling it
  is a synthetic frame whose joint logits keep returning a non-blank.
"""

import contextlib
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# This probe's own output IS the receipt (`_main/_lane3-verdict.log`). Python
# encodes a redirected stdout with the HOST locale (cp1252 here), so the em
# dashes below would land as bytes that are not valid UTF-8 and the log could not
# be read back. Force UTF-8, exactly like the worker does.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKER_PY = os.path.join(REPO, "worker", "sotto_worker.py")
CREATE_NO_WINDOW = 0x08000000

# The FROZEN vocabulary: every word the chain could return when this lane started,
# plus the one word this lane adds. A word outside this set means the chain was
# rewritten, which is the thing this probe exists to catch.
PRE_EXISTING_WORDS = {
    "silent-device",
    "all-candidate-taps-flat",
    "no-callback-blocks",
    "silent-capture",
    "resample-produced-nothing",
    "buffer-never-reached-chunk-size",
    "captions-all-music-gated",
    "captured-signal-has-no-speech",
    "captions-emitted",
}
NEW_WORD = "captions-zero"
VOCABULARY = PRE_EXISTING_WORDS | {NEW_WORD}

_fails = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        _fails.append(name)
    return ok


def ct(**over):
    """A live-run counter mapping, healthy by default (tap alive, audio arrived)."""
    base = {
        "blocks": 100,
        "block_samples": 160000,
        "nonzero_blocks": 100,
        "peak": 0.1,
        "sumsq": 0.0,
        "resampled_samples": 160000,
        "chunks": 10,
        "captions": 0,
        "queue_drops": 0,
        "reruns": 0,
        "rerun_wall_s": 0.0,
        "vad_gated_chunks": 0,
        "music_gated_chunks": 0,
    }
    base.update(over)
    return base


# ── ARM 0: the main() guard is checked BEFORE the import ─────────────────────
src = open(WORKER_PY, encoding="utf-8").read()
check(
    "0. worker/sotto_worker.py carries the __main__ guard (checked before import)",
    '\nif __name__ == "__main__":' in src,
)

_out, _err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(_out), contextlib.redirect_stderr(_err):
    import worker.sotto_worker as sw  # noqa: E402  (import must be side-effect free)

check(
    "0b. importing worker.sotto_worker runs no main(): no stdout, no stderr",
    _out.getvalue() == "" and _err.getvalue() == "",
    f"stdout={_out.getvalue()!r} stderr={_err.getvalue()!r}",
)

# ── ARM A: the frozen signature ──────────────────────────────────────────────
sig = inspect.signature(sw.decide_verdict)
check(
    "A. decide_verdict(counters, outcome, ran_but_silent) -> str is frozen",
    list(sig.parameters) == ["counters", "outcome", "ran_but_silent"]
    and str(sig.return_annotation) == "str",
    str(sig),
)

# ── ARM B: every word, from its own counters, in the chain's own order ───────
ARMS = [
    # (expected word, counters, outcome, ran_but_silent, what the arm is)
    ("captions-emitted", ct(captions=3), "run-ended", False, "3 captions, healthy run"),
    # captions > 0 with a stage counter ALSO at zero: the pre-existing ORDER must
    # hold, the stage word wins (predicates unchanged, not reordered).
    ("no-callback-blocks", ct(captions=3, blocks=0), "run-ended", False, "captions>0 but blocks==0"),
    ("silent-device", ct(captions=0), "flat", True, "ran_but_silent, outcome=flat"),
    # ORDER: the MEASURED silent-device fact must beat the ladder's weaker word.
    ("silent-device", ct(captions=0), "all-flat", True, "silent-device beats all-flat"),
    ("all-candidate-taps-flat", ct(captions=0), "all-flat", False, "ladder exhausted"),
    ("all-candidate-taps-flat", ct(captions=0), "open-failed", False, "every open failed"),
    ("no-callback-blocks", ct(blocks=0, nonzero_blocks=0, resampled_samples=0, chunks=0),
     "run-ended", False, "no PortAudio callback at all"),
    ("silent-capture", ct(nonzero_blocks=0, resampled_samples=0, chunks=0),
     "run-ended", False, "callbacks fired, every block digital silence"),
    ("resample-produced-nothing", ct(resampled_samples=0, chunks=0),
     "run-ended", False, "the 16 kHz conversion ate the audio"),
    ("buffer-never-reached-chunk-size", ct(chunks=0), "run-ended", False, "buffer never filled a chunk"),
    ("captions-all-music-gated", ct(music_gated_chunks=10), "run-ended", False,
     "our speech/music gate withheld every chunk"),
    ("captured-signal-has-no-speech", ct(vad_gated_chunks=3), "run-ended", False,
     "the shipped VAD withheld chunks"),
    # ── the F3 arm: the tap is ALIVE (blocks, signal, resample, chunks all real),
    # both gates quiet, and the run produced NO caption. This is what used to be
    # `captions-emitted` through the unconditional `else`.
    (NEW_WORD, ct(), "run-ended", False, "alive tap, no caption (the old else)"),
    (NEW_WORD, ct(), "flat", False, "alive tap, no caption, last candidate flat"),
    # The chunk-exception shape reaches THESE counters: `asr_thread` emitted
    # `state="error"`, set `stop` and returned, so no caption can follow and no
    # no-audio predicate is true.
    (NEW_WORD, ct(captions=0, chunks=7, nonzero_blocks=100), "run-ended", False,
     "chunk exception: error emitted, stop set, no caption"),
]
for word, counters, outcome, rbs, what in ARMS:
    got = sw.decide_verdict(counters, outcome, rbs)
    check(f"B. {word:<30} <- {what}", got == word, f"outcome={outcome} ran_but_silent={rbs} got={got!r}")

# ── ARM C: purity, and captions>0 is REQUIRED for the healthy word ───────────
counters = ct(captions=2)
before = json.dumps(counters, sort_keys=True)
first = sw.decide_verdict(counters, "run-ended", False)
second = sw.decide_verdict(counters, "run-ended", False)
check("C. decide_verdict is pure: counters unchanged, same answer twice",
      json.dumps(counters, sort_keys=True) == before and first == second and first == "captions-emitted",
      f"{first!r} / {second!r}")

# ── ARM D: the SWEEP — no captions==0 combination may claim success ──────────
seen = set()
zero_claims = []
combos = 0
for blocks in (0, 100):
    for nonzero in (0, 100):
        for resampled in (0, 100):
            for chunks in (0, 10):
                for gated in (0, 5):
                    for pair_gated in (False, True):
                        for outcome in ("all-flat", "open-failed", "flat", "run-ended"):
                            for rbs in (False, True):
                                music = chunks if pair_gated else 0
                                c = ct(blocks=blocks, nonzero_blocks=nonzero,
                                       resampled_samples=resampled, chunks=chunks,
                                       captions=0, vad_gated_chunks=gated,
                                       music_gated_chunks=music)
                                v = sw.decide_verdict(c, outcome, rbs)
                                seen.add(v)
                                combos += 1
                                if v == "captions-emitted":
                                    zero_claims.append(
                                        (blocks, nonzero, resampled, chunks, gated, music, outcome, rbs))
check("D1. no captions==0 combination returns captions-emitted",
      not zero_claims, f"{len(zero_claims)} offenders: {zero_claims[:3]}")
check("D2. the sweep invents no word outside the frozen vocabulary",
      seen <= VOCABULARY, f"extra={sorted(seen - VOCABULARY)}")
# `captions-emitted` is the ONLY frozen word this sweep may not reach, because the
# sweep holds `captions` at 0 and that word now requires captions > 0 — which is
# the whole F3 cure, asserted as a negative.
check("D3. with captions==0 the sweep reaches every word EXCEPT captions-emitted",
      VOCABULARY - seen == {"captions-emitted"},
      f"missing={sorted(VOCABULARY - seen)} extra={sorted(seen - VOCABULARY)}")
# …and the ARM table above must cover the WHOLE vocabulary, or a word could exist
# that nothing here ever produces.
check("D4. every frozen word is returned by at least one arm of the ARM table",
      {a[0] for a in ARMS} == VOCABULARY,
      f"missing={sorted(VOCABULARY - {a[0] for a in ARMS})}")
print(f"     sweep: {combos} combinations, words seen: {sorted(seen)}")


# ── ARM E: F13 — the language default, in a CHILD process ────────────────────
# `main()` is run with a config file that has no `model.lang_id` and a model dir
# that does not exist. The run emits `boot`/`lang`, then the `model` error and
# returns 2 — before any model session and before any audio device. stdout goes to
# a FILE (never a pipe: a piped child is refused by this session's sandbox) and the
# child is `pythonw.exe`, whose whole point is that it owns no console window —
# this probe must not put one on the owner's screen. Measured inside this sandbox:
# a `python.exe` child with `creationflags=CREATE_NO_WINDOW` dies at DLL init
# (`rc=0xC0000142`), so the house rule is satisfied by the interpreter instead.
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
if not os.path.isfile(PYW):
    PYW = sys.executable


def run_worker_arm(argv):
    """-> (rc, list of parsed stdout JSON objects). Child output goes to a file."""
    tmp = tempfile.mkdtemp(prefix="lane3-probe-")
    out_path = os.path.join(tmp, "child.log")
    with open(out_path, "w", encoding="utf-8", errors="replace") as fh:
        rc = subprocess.run(
            [PYW, WORKER_PY, *argv],
            cwd=REPO, stdout=fh, stderr=subprocess.STDOUT,
            env={**os.environ, "SOTTO_LANG_ID": ""},
        ).returncode
    lines = []
    with open(out_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                lines.append(json.loads(line))
            except ValueError:
                pass
    return rc, lines


def lang_line(lines):
    for obj in lines:
        if obj.get("state") == "boot" and obj.get("stage") == "lang":
            return obj
    return None


NO_CFG = os.path.join(REPO, "_main", "_lane3-probe-no-such-config.json")  # never created
NO_MODEL = os.path.join(REPO, "_main", "_lane3-probe-no-such-model")      # never created
rc, lines = run_worker_arm(["--config", NO_CFG, "--model", NO_MODEL, "--providers", "cpu"])
lang = lang_line(lines)
check("E1. absent model.lang_id -> the model's auto slot, source=default:auto",
      rc == 2 and lang is not None and lang.get("lang_id") == 101
      and lang.get("source") == "default:auto",
      f"rc={rc} lang={lang}")
print(f"     E1 child: {json.dumps(lang, ensure_ascii=False) if lang else None}")

rc, lines = run_worker_arm(["--config", NO_CFG, "--model", NO_MODEL, "--providers", "cpu",
                            "--lang-id", "os"])
lang = lang_line(lines)
check("E2. an EXPLICIT 'os' still resolves to the host locale (accepted, not removed)",
      rc == 2 and lang is not None and lang.get("source") == "cli:os-locale",
      f"rc={rc} lang={lang}")
print(f"     E2 child: {json.dumps(lang, ensure_ascii=False) if lang else None}")

rc, lines = run_worker_arm(["--config", os.path.join(REPO, "worker", "config.json"),
                            "--model", NO_MODEL, "--providers", "cpu"])
lang = lang_line(lines)
check("E3. a config that NAMES the key logs source=config:… (the shipped file)",
      rc == 2 and lang is not None and str(lang.get("source", "")).startswith("config:"),
      f"rc={rc} lang={lang}")
print(f"     E3 child: {json.dumps(lang, ensure_ascii=False) if lang else None}")

rc, lines = run_worker_arm(["--config", NO_CFG, "--model", NO_MODEL, "--providers", "cpu"])
non_boot = [o for o in lines if o.get("state") != "boot"]
check("E4. the E arm never reached the model load or a device (rc 2 at stage=model)",
      rc == 2 and len(non_boot) == 1 and non_boot[0].get("stage") == "model",
      f"rc={rc} tail={non_boot}")

# ── the config knob F17 adds ────────────────────────────────────────────────
cfg = json.load(open(os.path.join(REPO, "worker", "config.json"), encoding="utf-8"))
check("F. worker/config.json carries output.done_text_max_chars = 20000",
      cfg.get("output", {}).get("done_text_max_chars") == 20000,
      f"value={cfg.get('output', {}).get('done_text_max_chars')!r}")

# ── the static F11/F12/F17 surfaces the model-free arms cannot run ───────────
check("G. StreamAsr owns fresh_processor/reset_frontend (F12)",
      "def fresh_processor(self)" in src and "def reset_frontend(self)" in src
      and src.count("asr.reset_frontend()") >= 1)

print()
print("VERDICT " + ("PASS" if not _fails else "FAIL " + ", ".join(_fails)))
sys.exit(0 if not _fails else 1)
