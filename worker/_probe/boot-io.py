"""Boot cost of the REAL worker process: seconds AND bytes read, to `model-loaded`.

    python worker/_probe/boot-io.py [--providers auto] [--extra-args ...]

The owner's log shows 65 s to 206 s to `model-loaded`, and the same boot is 6 s
on an idle box: the difference is DISK. So a change that only reports warm
seconds cannot prove it helps him. This probe reports both:

  * `wall_to_model_loaded_s` — wall clock, spawn -> the `model-loaded` event
  * `read_mb` / `read_ops`     — the child's own file-read volume, from Windows'
    per-process I/O counters (`psutil.Process.io_counters`, i.e.
    `GetProcessIoCounters`), which is the number that grows when the disk is busy

Read-only with respect to audio: the worker is run as `--selftest` (file source,
no audio device), exactly like `worker/README.md`'s self-test.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.dirname(HERE)
SCRIPT = os.path.join(WORKER, "sotto_worker.py")


def main():
    args = sys.argv[1:]
    script = SCRIPT
    if "--script" in args:
        i = args.index("--script")
        script = args[i + 1]
        args = args[:i] + args[i + 2:]
    extra = args
    argv = [sys.executable, script, "--selftest", "--stats-interval", "0"] + extra
    t0 = time.time()
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=WORKER, text=True, encoding="utf-8", errors="replace",
                            bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW)
    import psutil

    ps = psutil.Process(proc.pid)
    boot = {}
    loaded_at = None
    first_caption_at = None
    lines = 0
    prof = None
    loaded = None
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        lines += 1
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        state = ev.get("state")
        if ev.get("type") == "status" and state == "model-loaded":
            loaded_at = time.time() - t0
            loaded = {k: v for k, v in ev.items() if k in ("load_s", "load_phases_s",
                                                           "boot_prof_s", "providers",
                                                           "rss_mb", "peak_rss_mb")}
        elif first_caption_at is None and ev.get("type") in ("caption", "partial", "line"):
            first_caption_at = time.time() - t0
    try:
        io = ps.io_counters()
        io_read = io.read_bytes
        io_ops = io.read_count
    except Exception:
        io_read = io_ops = -1
    proc.wait(timeout=600)
    err = [l for l in proc.stderr.read().splitlines() if l.startswith("WORKER_BOOT_PROF")]
    prof = err[-1] if err else None
    print("RESULT wall_to_model_loaded_s=%.2f" % (loaded_at if loaded_at else -1))
    print("RESULT first_caption_s=%.2f" % (first_caption_at if first_caption_at else -1))
    print("RESULT read_mb=%.1f read_ops=%d" % (io_read / 1e6, io_ops))
    print("RESULT stdout_lines=%d rc=%s" % (lines, proc.returncode))
    if loaded:
        print("RESULT load_s=%s" % loaded.get("load_s"))
        print("RESULT load_phases_s=%s" % json.dumps(loaded.get("load_phases_s")))
        print("RESULT boot_prof_s=%s" % json.dumps(loaded.get("boot_prof_s")))
    if prof:
        print("RESULT " + prof)
    boot = 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
