"""Measure launch -> first caption for the Sotto panel.

Launches the REAL shell exactly as the owner's own run did (the receipt in
`_main/receipt-append.md` records the same command), with two changes that are
about SAFETY, not about measurement:

  * `--hotkey=Control+Alt+Shift+F9` — `main.js:553-554` FORCE-SHOWS the panel
    when the hotkey fails to register, and the owner's recorded run hit exactly
    that (`HOTKEY_REGISTER_FAILED ... PANEL_SHOWN reason=hotkey-failed`). A
    free accelerator means the hotkey registers, so no window is ever shown.
  * `creationflags = CREATE_NO_WINDOW | DETACHED_PROCESS` — no console window,
    which is the stray-python-console defect the owner already saw once.

The number printed is wall-clock seconds from `Popen` to the first
`CAPTION_APPLIED` line, read back from the child's own log. It is a MEASUREMENT
of this machine on this day, not a target.
"""

import io
import json
import os
import subprocess
import time

LOG = r"H:\sotto\app\_legacy-electron\panel-run-readiness.log"
ELECTRON = r"H:\sotto\app\node_modules\electron\dist\electron.exe"
CWD = r"H:\sotto\app"

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
TIMEOUT_S = 90


def main() -> int:
    try:
        os.remove(LOG)
    except OSError:
        pass

    handle = io.open(LOG, "w", encoding="utf-8", errors="replace")
    started = time.time()
    child = subprocess.Popen(
        [
            ELECTRON,
            ".",
            "--with-worker",
            # A free accelerator, so main.js never force-shows the panel.
            "--hotkey=Control+Alt+Shift+F9",
        ],
        cwd=CWD,
        stdout=handle,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
    )

    first_status = None
    first_caption = None
    first_provisional = None
    deadline = started + TIMEOUT_S

    while time.time() < deadline:
        time.sleep(0.15)
        try:
            with io.open(LOG, "r", encoding="utf-8", errors="replace") as fh:
                data = fh.read()
        except OSError:
            continue

        if first_status is None and "BRIDGE_STATUS" in data:
            first_status = round(time.time() - started, 2)
        if first_provisional is None and "RECEIVER_READY" in data:
            first_provisional = round(time.time() - started, 2)
        if first_caption is None and "CAPTION_APPLIED" in data:
            first_caption = round(time.time() - started, 2)
            break

    print(
        json.dumps(
            {
                "pid": child.pid,
                "launch_to_RECEIVER_READY_s": first_provisional,
                "launch_to_first_BRIDGE_STATUS_s": first_status,
                "launch_to_first_CAPTION_APPLIED_s": first_caption,
                "timed_out_after_s": first_caption is None,
                "log": LOG,
            },
            indent=2,
        )
    )

    child.terminate()
    try:
        child.wait(timeout=10)
    except Exception:
        child.kill()
    handle.close()
    return 0 if first_caption is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
