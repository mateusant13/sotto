"""Run the SHIPPED worker against whatever is rendering, with NO console window.

The child is `python.exe` (NOT pythonw) because the worker writes its JSONL to
stdout, and pythonw gives the child `sys.stdout = None` when the handle is not a
console -- so pythonw would throw the captions away. To keep the owner's desktop
clean the child is spawned with CREATE_NO_WINDOW (the repo's documented pattern:
measured 3/3 hwnd=0 vs 3/3 hwnd!=0 for a plain console spawn), and THIS driver is
launched under pythonw, so no window is created anywhere.

Writes: <out>.jsonl (worker stdout), <out>.err (worker stderr), <out>.summary.

    pythonw.exe _main/audio-escope-worker-run.py <out-prefix> <seconds> [worker args...]
"""
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.normpath(os.path.join(HERE, "..", "worker", "sotto_worker.py"))
PYEXE = r"C:\Program Files\Python311\python.exe"
CREATE_NO_WINDOW = 0x08000000

out_prefix = sys.argv[1]
secs = sys.argv[2]
extra = sys.argv[3:]

jsonl_path = out_prefix + ".jsonl"
err_path = out_prefix + ".err"
summary_path = out_prefix + ".summary"

t0 = time.time()
with open(jsonl_path, "wb") as out, open(err_path, "wb") as errf:
    proc = subprocess.Popen(
        [PYEXE, WORKER, "--max-seconds", secs, *extra],
        stdout=out,
        stderr=errf,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        cwd=os.path.dirname(WORKER),
    )
    rc = proc.wait(timeout=400)

statuses, captions = [], []
with io.open(jsonl_path, encoding="utf-8", errors="replace") as f:
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

lines = []
lines.append(json.dumps({
    "cmd": f"{PYEXE} sotto_worker.py --max-seconds {secs} {' '.join(extra)}",
    "wall_s": round(time.time() - t0, 1),
    "EXIT_CODE": rc,
    "captions": len(captions),
    "caption_text": " | ".join(c.strip() for c in captions if c.strip()),
}, ensure_ascii=False))
for o in statuses:
    if o.get("state") in ("device", "capture-started", "device-rotated", "device-exhausted",
                          "silent-device", "no-speech-in-capture", "music-only-capture",
                          "done", "error"):
        lines.append(json.dumps(o, ensure_ascii=False))

# the final WORKER_STATS / device_outcome lines live on stderr
with io.open(err_path, encoding="utf-8", errors="replace") as f:
    for line in f:
        if ("WORKER_STATS" in line or "device_outcome" in line
                or line.startswith("done") or "tap_ledger" in line):
            lines.append(line.rstrip())

with io.open(summary_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
