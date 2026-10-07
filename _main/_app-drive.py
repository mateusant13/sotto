"""Drive the OWNER'S APP for the SottoFlatEndpointNaApp measurement.

Reads/writes nothing but its own logs; kills ONLY processes whose command line
names sotto_webview.py (the app) and the worker it owns. Every spawn uses
CREATE_NO_WINDOW so nothing appears on the owner's desktop.

Usage:
    py -3 _main/_app-drive.py census
    py -3 _main/_app-drive.py kill
    py -3 _main/_app-drive.py launch [probe_seconds] [log_path]
    py -3 _main/_app-drive.py play <seconds> [device_substring]
    py -3 _main/_app-drive.py wait-exit <seconds>
"""
import ctypes
import json
import os
import subprocess
import sys
import time

ROOT = r"H:\sotto"
WEBVIEW = os.path.join(ROOT, "app", "webview")
CREATE_NO_WINDOW = 0x08000000
DETACHED = 0x00000008
PYW = r"C:\Program Files\Python311\pythonw.exe"
PY = r"C:\Program Files\Python311\python.exe"


def _ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                        "-ExecutionPolicy", "Bypass", "-Command", cmd],
                       capture_output=True)
    return r.stdout.decode("cp850", "replace"), r.stderr.decode("cp850", "replace")


def census():
    cmd = ("Get-CimInstance Win32_Process | "
           "Where-Object { $_.CommandLine -like '*sotto_webview.py*' -or "
           "$_.CommandLine -like '*sotto_worker.py*' -or "
           "$_.CommandLine -like '*_join-play.py*' } | "
           "ForEach-Object { \"{0}|{1}|{2}|{3}\" -f $_.ProcessId,$_.Name,"
           "$_.CreationDate.ToString('HH:mm:ss'),$_.CommandLine }")
    out, err = _ps(cmd)
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        p = line.split("|", 3)
        rows.append(p)
        print("  PID=%-7s %-11s start=%s  %s" % (p[0], p[1], p[2], p[3][:150]))
    return rows


def kill_app():
    rows = census()
    killed = []
    for p in rows:
        if "sotto_webview.py" in p[3]:
            r = subprocess.run(["taskkill", "/F", "/T", "/PID", p[0]],
                               capture_output=True)
            killed.append((p[0], r.returncode,
                           r.stdout.decode("cp850", "replace").strip()))
            print("KILL pid=%s rc=%s %s" % (p[0], r.returncode,
                                            r.stdout.decode("cp850", "replace").strip()))
    if not killed:
        print("kill_app: NO sotto_webview.py process found")
    return killed


def launch(probe_s, log_path):
    # THE HOUSE PATH: run.cmd (it owns the hidden pythonw launch, the arg
    # pre-flight and the bounded readiness handshake). The only flag added is
    # --probe-v2, which makes the shell run its own panel probe and then exit.
    args = ["cmd", "/c", "run.cmd", "--with-worker"]
    if probe_s > 0:
        args += ["--probe-v2", str(probe_s)]
    if log_path:
        args += ["--log", log_path]
    print("LAUNCH cwd=%s argv=%r" % (WEBVIEW, args))
    # DEVNULL, not PIPE: run.cmd `start`s the app DETACHED, and a detached child
    # INHERITS the wrapper's std handles -- with PIPE handles, communicate()
    # would block on a pipe that stays open until the app itself exits (measured:
    # the 150 s probe run made a PIPE launch block 160 s). With DEVNULL the
    # handles are NUL, run.cmd's own exit is the only thing left to wait for.
    p = subprocess.Popen(args, cwd=WEBVIEW, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=CREATE_NO_WINDOW)
    rc = p.wait(timeout=180)
    print("run.cmd rc=%s" % rc)
    return rc


def play(seconds, device):
    out = os.path.join(ROOT, "_main", "_app-play.out")
    err = os.path.join(ROOT, "_main", "_app-play.err")
    fo = open(out, "wb")
    fe = open(err, "wb")
    p = subprocess.Popen([PY, os.path.join(ROOT, "_main", "_join-play.py"),
                          device, str(seconds)],
                         cwd=ROOT, stdin=subprocess.DEVNULL,
                         stdout=fo, stderr=fe,
                         creationflags=CREATE_NO_WINDOW)
    print("PLAY pid=%s seconds=%s device=%r -> %s" % (p.pid, seconds, device, err))
    return p.pid


def wait_exit(seconds):
    deadline = time.time() + float(seconds)
    last = None
    while time.time() < deadline:
        rows = census()
        shell = [r for r in rows if "sotto_webview.py" in r[3]]
        if not shell:
            print("wait-exit: the app is GONE (no sotto_webview.py)")
            return 0
        state = ",".join(r[0] for r in shell)
        if state != last:
            print("  still up: shell pids=%s" % state)
            last = state
        time.sleep(3)
    print("wait-exit: TIMEOUT after %ss; shell still up" % seconds)
    return 1


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "census"
    if what == "census":
        census()
    elif what == "kill":
        kill_app()
    elif what == "launch":
        launch(float(sys.argv[2]) if len(sys.argv) > 2 else 0.0,
               sys.argv[3] if len(sys.argv) > 3 else
               os.path.join(ROOT, "_main", "webview-run.log"))
    elif what == "play":
        play(float(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3
             else "VoiceMeeter Input")
    elif what == "wait-exit":
        sys.exit(wait_exit(sys.argv[2] if len(sys.argv) > 2 else 180))
    else:
        print("unknown:", what)
        sys.exit(2)
