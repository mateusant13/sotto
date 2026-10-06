"""Run sotto_worker.py LIVE for N seconds with NO console window on the owner's
desktop, capture stdout JSONL + stderr, and report the real exit code.

Why this wrapper exists (AGENTS.md hard rule): two lanes have already shown the
owner a stray python console. Launching the worker directly from a tool call
risks the same thing, so the worker is spawned from here with
CREATE_NO_WINDOW and both output streams redirected to files.

Usage: py -3 _main/run-live-hidden.py <out.jsonl> <seconds> [extra worker args...]
Prints a summary; the raw JSONL is on disk for inspection.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.normpath(os.path.join(HERE, "..", "worker", "sotto_worker.py"))

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


def main() -> int:
    out_path = sys.argv[1]
    secs = sys.argv[2]
    extra = sys.argv[3:]

    out = open(out_path, "wb")
    errf = open(out_path + ".err", "wb")
    t0 = time.time()
    proc = subprocess.Popen(
        [sys.executable, WORKER, "--max-seconds", secs, *extra],
        stdout=out,
        stderr=errf,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        cwd=os.path.dirname(WORKER),
    )
    rc = proc.wait(timeout=300)
    out.close()
    errf.close()

    statuses, captions = [], []
    with open(out_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") == "caption":
                captions.append(o.get("text", ""))
            else:
                statuses.append(o)

    print(json.dumps({
        "cmd": f"{sys.executable} sotto_worker.py --max-seconds {secs} {' '.join(extra)}",
        "wall_s": round(time.time() - t0, 1),
        "EXIT_CODE": rc,
        "captions": len(captions),
        "caption_words": " | ".join(c.strip() for c in captions if c.strip()),
    }, ensure_ascii=False))
    for o in statuses:
        if o.get("state") in ("device", "capture-started", "device-rotated",
                              "device-exhausted", "silent-device", "done", "error"):
            print(json.dumps(o, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
