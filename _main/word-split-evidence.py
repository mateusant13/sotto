"""Run the three model-based word-split evidence arms, sequentially, window-free.

WHY (lane SottoWordSplit): this process is started with `pythonw.exe`, and it
spawns every child with `CREATE_NO_WINDOW` — the house rule — because the owner
has the app running and a stray console has been reported twice. Each arm is a
separate process so each pays its own model load and leaves its own stream state
alone:

  1. `word-split-trace.py`        -> the RAW per-chunk detok text + token ids
  2. `worker/sotto_worker.py --selftest --audio …`  -> the AFTER captions, from
     the REAL entry point (the same command the file arm always used)
  3. `word-split-before-run.py`   -> the BEFORE captions, same path with the one
     `join_fragments` line reverted

No audio device is opened by any of them.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WAV = os.path.join(HERE, "pt-br-sample.wav")
CREATE_NO_WINDOW = 0x08000000


def main():
    # Under `pythonw.exe` sys.stdout/sys.stderr are None, so the progress log is
    # a FILE: a `print(file=sys.stderr)` here killed this launcher after the
    # first arm and produced no error anywhere (measured 2026-10-07).
    log = open(os.path.join(HERE, "_wordsplit-evidence.log"), "w", encoding="utf-8")

    def say(msg):
        log.write(msg + "\n")
        log.flush()

    py = os.path.join(os.path.dirname(sys.executable), "python.exe")
    if not os.path.exists(py):
        py = sys.executable
    arms = [
        ("trace", [py, os.path.join(HERE, "word-split-trace.py"),
                   "--wav", WAV, "--out", os.path.join(HERE, "word-split-trace.json")]),
        ("after", [py, os.path.join(REPO, "worker", "sotto_worker.py"),
                   "--selftest", "--audio", WAV]),
        ("before", [py, os.path.join(HERE, "word-split-before-run.py"),
                    "--wav", WAV, "--out", os.path.join(HERE, "_wordsplit-before.jsonl")]),
    ]
    outs = {"trace": "_wordsplit-trace.log", "after": "_wordsplit-after.jsonl",
            "before": "_wordsplit-before.log"}
    for name, cmd in arms:
        t0 = time.time()
        with open(os.path.join(HERE, outs[name]), "wb") as fo, \
                open(os.path.join(HERE, outs[name] + ".err"), "wb") as fe:
            rc = subprocess.call(cmd, stdout=fo, stderr=fe,
                                 creationflags=CREATE_NO_WINDOW, cwd=REPO)
        say(f"ARM {name}: rc={rc} wall={time.time() - t0:.1f}s")
        if rc != 0:
            say(f"ARM {name} FAILED rc={rc}")
            log.close()
            return rc
    say("ALL ARMS OK")
    log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
