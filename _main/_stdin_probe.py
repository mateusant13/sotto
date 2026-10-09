"""Throwaway: what do REAL client verbs get back from the stdin channel?"""
import json, subprocess, sys, threading, time

EXE = r"H:\sotto-wt\e2e\_main\build\aireplay-capture.exe"

# The verbs a real ShadowPlay-style client sends. ping is the only one the
# source admits; the rest are what a product needs.
CMDS = ["ping", "start", "stop", "record", "cut", "capture.start",
        "capture.stop", "clip.save", "begin", "end", "hotkey"]

p = subprocess.Popen([EXE, "--run", "--seconds", "3", "--cut-at", "1",
                      "--out", r"H:\sotto-wt\e2e\_main\build\stdinprobe.mp4"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True, bufsize=1)

replies = []
def reader():
    for line in p.stdout:
        replies.append(line.rstrip("\n"))
t = threading.Thread(target=reader, daemon=True); t.start()

for c in CMDS:
    p.stdin.write(json.dumps({"cmd": c}) + "\n"); p.stdin.flush()
    time.sleep(0.05)

time.sleep(1.0)
print("=== after 1.0 s of client commands, is capture already running? ===")
print(f"    process alive      : {p.poll() is None}")
print(f"    replies so far     : {len(replies)}")

p.stdin.close()
try:
    p.wait(timeout=90)
except subprocess.TimeoutExpired:
    p.kill(); p.wait()
t.join(timeout=2)

print(f"    process rc         : {p.returncode}")
print("\n=== replies, in order ===")
for i, (c, r) in enumerate(zip(CMDS, replies), 1):
    print(f"  {i:2d}. cmd={c:<15s} -> {r}")
print(f"\ntotal replies={len(replies)} for {len(CMDS)} commands")
import pathlib
clip = pathlib.Path(r"H:\sotto-wt\e2e\_main\build\stdinprobe.mp4")
print(f"clip exists={clip.exists()} bytes={clip.stat().st_size if clip.exists() else 0}")
print("\n=== remaining process output ===")
for r in replies[len(CMDS):]:
    print("  " + r)