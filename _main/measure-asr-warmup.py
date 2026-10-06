"""Measure the ASR half of warm-up: process start -> first caption emitted.

The end-to-end number the owner asked for is launch -> first caption, and that
is `_main/measure-readiness.py`. It is reported separately because it needs a
LIVE audio tap, and this machine had none at measurement time (every candidate
device came back flat — `BRIDGE_STATUS state="device-exhausted"` in
`app/electron/panel-run-readiness.log`). This script measures the part that
does NOT depend on audio, so the boot cost is a real number rather than a
guess:

    python process start -> first `{"type":"caption"...}` line on stdout

`--selftest` needs no audio device. The worker prints the JSONL caption stream
on stdout, so the first caption line is the signal.

NO WINDOW: this runs under `pythonw.exe`, which has no console subsystem, so
no console window can be allocated at any point. That is the defect the owner
already saw once from a lane's test.
"""

import json
import subprocess
import sys
import time

WORKER = r"H:\sotto\worker\sotto_worker.py"
TIMEOUT_S = 180


def main() -> int:
    started = time.time()
    proc = subprocess.Popen(
        [sys.executable, WORKER, "--selftest"],
        cwd=r"H:\sotto\worker",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        # Belt and braces: even if this were launched from a console, the child
        # is not allowed one.
        creationflags=0x08000000,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    first_caption_s = None
    first_caption_text = None
    model_loaded_s = None
    deadline = started + TIMEOUT_S

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        elapsed = round(time.time() - started, 2)
        try:
            msg = json.loads(line)
        except ValueError:
            continue

        kind = str(msg.get("type", ""))
        state = str(msg.get("state", ""))
        if model_loaded_s is None and state in ("model-loaded", "model_loaded"):
            model_loaded_s = elapsed
        if first_caption_s is None and kind == "caption":
            first_caption_s = elapsed
            first_caption_text = msg.get("text")
            break
        if time.time() > deadline:
            break

    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        proc.kill()

    print(
        json.dumps(
            {
                "asr_process_start_to_first_caption_s": first_caption_s,
                "asr_process_start_to_model_loaded_s": model_loaded_s,
                "first_caption_text": first_caption_text,
                "measured": first_caption_s is not None,
                "note": "ASR half only; needs no audio device. The end-to-end "
                "launch->first-caption number is in measure-readiness.py and "
                "was NOT obtained on this machine (no live audio tap).",
            },
            indent=2,
        )
    )
    return 0 if first_caption_s is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
