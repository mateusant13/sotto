"""stub_asr.py -- the GATE-ONLY ASR child for THE ENGINE PROCESS (lane A).

It is a STUB and says so in every word it prints.  Its job is to look exactly
like the real ASR side on the wire (src/asr/transcribe.py --json, measured
2026-10-09) while being controllable, so the gate can make that side STALL or
DIE and then prove what the Engine's capture side did while it did not happen.

Wire shape: stdout carries one JSON object per line, each with a "type" field
-- "segment" per event and exactly ONE "done" object at the end.  Anything else
is counted as noise by asr_worker.parse_asr_stream, never fatal.

    stub_asr.py WAV [--stall S] [--rc N] [--text T]

    --stall S   sleep S seconds before saying anything (the capture must not wait)
    --rc N      exit N without a single "done" (the capture must not care)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser(prog="stub_asr.py",
                                 description="STUB ASR child for the engine gate")
    ap.add_argument("wav", help="the clip to pretend to transcribe (bytes never read)")
    ap.add_argument("--stall", type=float, default=0.0,
                    help="sleep this many seconds before ANY output")
    ap.add_argument("--rc", type=int, default=0, help="exit with this code, silently")
    ap.add_argument("--text", default="STUB TRANSCRIPT")
    a = ap.parse_args()

    sys.stderr.write("STUB-ASR pid=%d wav=%s stall=%.1f rc=%d (NOT the real "
                     "asr.transcribe)\n" % (os.getpid(), a.wav, a.stall, a.rc))
    sys.stderr.flush()

    if a.stall > 0:
        # The stall is the whole point: a capture side that waits for ASR
        # stops HERE, and the gate would then measure a stalled capture.
        time.sleep(a.stall)
    if a.rc != 0:
        sys.stderr.write("STUB-ASR refusing to produce a transcript, exit %d\n" % a.rc)
        sys.stderr.flush()
        return a.rc

    segs = [{"i": 0, "start": 0.0, "end": 1.0,
             "text": "%s (stub, not the real ASR)" % a.text},
            {"i": 1, "start": 1.0, "end": 2.0,
             "text": "%s dois (stub, not the real ASR)" % a.text}]
    for s in segs:
        sys.stdout.write(json.dumps(dict({"type": "segment"}, **s)) + "\n")
        sys.stdout.flush()
    sys.stdout.write(json.dumps({"type": "done",
                                 "text": " ".join(s["text"] for s in segs),
                                 "n_segments": len(segs),
                                 "infer_s": 0.01,
                                 "provider": "stub_asr.py (STUB)"}) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
