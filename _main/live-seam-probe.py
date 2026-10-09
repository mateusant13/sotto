"""Does the LIVE path ever pass `continues=True`? MEASURED, not read.

Runs the REAL live loop (`main()` -> `asr_thread` -> `drain`/`finalise`/`rerun`) with
the tap replaced by a file, and spies on `LineFormer.push` and on `emit` to record,
for every fragment the live path pushes:

    text, continues, the line before, the line after

No audio device is opened: `SOTTO_FILE_TAP` swaps the device ladder for the file tap
(`file_tap_candidate`, `sotto_worker.py:3331-3341`), and the tap delivers blocks on a
wall-clock schedule exactly as a device callback would.

Answers the question the coordinating agent asked FIRST: if the live path never passes
`continues=True`, the batch fix cannot touch it. The count is printed, not asserted.
"""

from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(os.path.dirname(HERE), "worker")
sys.path.insert(0, WORKER)

WAV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "en-us-sample.wav")
SECONDS = sys.argv[2] if len(sys.argv) > 2 else "12"
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "_live-seam-probe.json")

os.environ["SOTTO_FILE_TAP"] = WAV
os.environ.pop("SOTTO_METER_HZ", None)

import sotto_worker as W  # noqa: E402

PUSHES: list = []
EVENTS: list = []
CONT = {"true": 0, "false": 0}

_orig_push = W.LineFormer.push
_orig_cont = W.chunk_is_continuation
_orig_emit = W.emit


def spy_cont(vocab, ids):
    out = _orig_cont(vocab, ids)
    CONT["true" if out else "false"] += 1
    return out


def spy_push(self, text, start=None, end=None, continues=False, **kw):
    before = self.line()
    events = _orig_push(self, text, start, end, continues=continues)
    PUSHES.append({
        "text": text,
        "continues": bool(continues),
        "line_before": before,
        "line_after": self.line(),
        "closed": [e.get("text") for e in (events or []) if e.get("final")],
    })
    return events


def spy_emit(**ev):
    if ev.get("type") == "caption":
        EVENTS.append({k: v for k, v in ev.items()})
    return _orig_emit(**ev)


W.LineFormer.push = spy_push
W.chunk_is_continuation = spy_cont
W.emit = spy_emit

# ── `--neg-arm`: the PRE-FIX live path ───────────────────────────────────────
# `join_fragments` restored to the shipped body — the exact function the owner's
# worker (pid 29008, spawned 08:01:56, before the fix) is still running in memory.
# If the live path is where the defect lives, THIS is the colour that shows it.
NEG = "--neg-arm" in sys.argv
if NEG:
    def pre_fix_join(frags):
        return " ".join(t for t, _c in frags if t).strip()

    W.join_fragments = pre_fix_join
    sys.stderr.write("NEG-ARM: join_fragments reverted to the pre-fix body "
                     '(" ".join(...)) — the code the owner\'s running worker holds\n')

sys.argv = ["sotto_worker.py", "--max-seconds", SECONDS, "--stats-interval", "4"]
rc = 0
try:
    W.main()
except SystemExit as exc:
    rc = int(exc.code or 0)
finally:
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"wav": WAV, "rc": rc, "cont": CONT, "pushes": PUSHES,
                   "captions": EVENTS}, fh, ensure_ascii=False, indent=1)
    sys.stderr.write(
        f"live-seam-probe: wav={os.path.basename(WAV)} rc={rc} "
        f"pushes={len(PUSHES)} continues_true={CONT['true']} "
        f"continues_false={CONT['false']} captions={len(EVENTS)}\n"
    )
