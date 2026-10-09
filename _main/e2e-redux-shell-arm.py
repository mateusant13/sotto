"""END-TO-END: the REAL app (run.cmd) driving worker/redux_live.py, no device opened.

Why this arm exists
-------------------
Every other claim about the switch in `_main/receipt-redux-live.md` was verified by
READING `app/webview/sotto_webview.py` (the `--worker` flag, `_spawn`, the loud
`BRIDGE_WORKER_MISSING` branch). That is "the mechanism the code implements", not
"the app does it". This arm runs the shipped launcher with the Redux engine and
reads the shell's OWN log for the captions.

How it avoids touching the owner's stream
-----------------------------------------
`SOTTO_FILE_TAP` makes the worker take its audio from a file and open NO endpoint
(`sotto_worker.py:3374-3382`; `redux_live.py::tap_candidates` reproduces that branch
because `device_candidates` does NOT read the variable). The owner's worker holds the
loopback and a video is playing: this arm must not contend for it, and does not.

The window rule
---------------
Sampled at 100 ms from BEFORE `run.cmd` is spawned, in-process, with
`user32.EnumWindows` + `IsWindowVisible` (explicit argtypes; a missing argtypes makes
`SetWindowPos`-family calls fail silently). Three claims, and the second is the
control that stops the first from being vacuous:

  ARM A  no visible window is owned by the shell or its worker (title `Sotto`,
         class `WindowsForms10…`, or a python-family image name);
  ARM B  the census is NOT blind -- some other pid HAS a visible window in the same
         samples (the owner's Chrome is always up);
  ARM C  no pid in `PYTHON_FAMILY` owns a visible window at all.

`--neg-arm` proves ARM C can go RED by feeding it a pid that IS python (this probe's
own), which costs the owner no window and no focus steal.

Usage:
    py -3 _main/e2e-redux-shell-arm.py [--seconds 45] [--wav PATH] [--neg-arm]
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_CMD = ROOT / "app" / "webview" / "run.cmd"
REDUX = ROOT / "worker" / "redux_live.py"
DEFAULT_WAV = ROOT / "_main" / "en-us-sample.wav"
LOG = ROOT / "_main" / "e2e-redux-shell.log"
CREATE_NO_WINDOW = 0x08000000
PYTHON_FAMILY = {"python", "pythonw", "py", "conhost"}


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            pass


# ── the census ────────────────────────────────────────────────────────────────
user32 = ctypes.WinDLL("user32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.EnumWindows.restype = wt.BOOL
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowVisible.restype = wt.BOOL
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD


def visible_windows() -> dict:
    """pid -> list of (title, class) for every VISIBLE top-level window."""
    found: dict = {}

    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        found.setdefault(int(pid.value), []).append((buf.value, cls.value))
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return found


def resolve_names(pids) -> dict:
    """ONE process-table call for every pid the census saw -- never a per-sample walk."""
    pids = sorted({int(p) for p in pids if p})
    if not pids:
        return {}
    csv = ",".join(str(p) for p in pids)
    try:
        out = subprocess.run(
            ["pwsh", "-NoProfile", "-Command",
             f"Get-Process -Id {csv} -ErrorAction SilentlyContinue | "
             f"Select-Object Id,ProcessName | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=60,
            creationflags=CREATE_NO_WINDOW)
        raw = (out.stdout or "").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        return {int(row["Id"]): str(row["ProcessName"]) for row in data}
    except Exception as exc:
        print(f"resolve_names failed: {type(exc).__name__}: {exc}")
        return {}


class Sampler(threading.Thread):
    """100 ms census; `self._halt` is NOT `self._stop` (Thread already owns that)."""

    def __init__(self, cadence_ms: int):
        super().__init__(name="e2e-census", daemon=True)
        self.cadence = cadence_ms / 1000.0
        self._halt = threading.Event()
        self.samples = 0
        self.by_pid: dict = {}
        self.per_sample: list = []

    def run(self) -> None:
        while not self._halt.is_set():
            snap = visible_windows()
            self.samples += 1
            self.per_sample.append(set(snap))
            for pid, wins in snap.items():
                self.by_pid.setdefault(pid, [])
                for win in wins:
                    if win not in self.by_pid[pid]:
                        self.by_pid[pid].append(win)
            self._halt.wait(self.cadence)

    def stop(self) -> None:
        self._halt.set()


# ── the arm ───────────────────────────────────────────────────────────────────
def parse_log(path: Path) -> dict:
    """Read the shell's OWN log for the decisive lines. Absence is reported as such."""
    if not path.exists():
        return {"exists": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    shell_pid = None
    for line in lines:
        m = re.search(r"pid=(\d+)", line)
        if m and "shell=" in line:
            shell_pid = int(m.group(1))
            break
    return {
        "exists": True,
        "bytes": len(text.encode("utf-8", "replace")),
        "lines": len(lines),
        "shell_pid": shell_pid,
        "autostart": [ln.strip() for ln in lines if "WORKER_AUTOSTART" in ln],
        "worker_path": [ln.strip() for ln in lines if "WORKER_PATH" in ln],
        "missing": [ln.strip() for ln in lines if "BRIDGE_WORKER_MISSING" in ln],
        "caption_sent": sum(1 for ln in lines if "BRIDGE_CAPTION_SENT" in ln),
        "page_error": [ln.strip() for ln in lines if "PAGE_ERROR" in ln],
        "deaths": sum(1 for ln in lines if "BRIDGE_DEATH" in ln),
        "malformed": sum(1 for ln in lines if "BRIDGE_MALFORMED" in ln),
        "redux_done": [ln.strip() for ln in lines if '"verdict"' in ln
                       or "redux" in ln.lower() and "model-loaded" in ln],
        "captions_tail": [ln.strip() for ln in lines if "BRIDGE_CAPTION_SENT" in ln][-4:],
    }


def main(argv=None) -> int:
    _utf8()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds", type=float, default=45.0,
                    help="how long to census (the shell gets --exit-after)")
    ap.add_argument("--wav", default=str(DEFAULT_WAV))
    ap.add_argument("--neg-arm", action="store_true",
                    help="feed ARM C a pid that IS python, to prove it can go RED")
    args = ap.parse_args(argv)

    for path, what in ((RUN_CMD, "run.cmd"), (REDUX, "redux_live.py"),
                       (Path(args.wav), "the wav")):
        if not path.exists():
            print(f"REFUSED: {what} not found at {path}")
            return 2

    if LOG.exists():
        LOG.unlink()

    env = dict(os.environ)
    env["SOTTO_FILE_TAP"] = str(Path(args.wav).resolve())
    env["SOTTO_NO_WORKER"] = ""  # explicitly unset: --with-worker is authoritative

    sampler = Sampler(100)
    sampler.start()
    time.sleep(0.6)  # a pre-spawn control: the census must already see windows

    pre = set(sampler.by_pid)
    cmd = ["cmd", "/c", str(RUN_CMD),
           "--worker", str(REDUX),
           "--with-worker",
           "--no-hotkey",
           "--exit-after", str(int(args.seconds)),
           "--log", str(LOG)]
    print("cadence=100ms  seconds=%g" % args.seconds)
    print("SOTTO_FILE_TAP=%s  (the engine opens NO audio device)" % env["SOTTO_FILE_TAP"])
    print("spawn: " + " ".join(cmd))
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True,
                          text=True, timeout=180, creationflags=CREATE_NO_WINDOW)
    rc = proc.returncode
    print(f"run.cmd returned rc={rc} after {time.perf_counter() - t0:.2f}s "
          f"(it detaches; the app lives on)")
    if (proc.stdout or "").strip():
        print("run.cmd stdout: " + (proc.stdout or "").strip()[:600])
    if (proc.stderr or "").strip():
        print("run.cmd stderr: " + (proc.stderr or "").strip()[:600])

    # Wait for the app to finish its --exit-after, then a little slack.
    deadline = t0 + args.seconds + 25
    while time.perf_counter() < deadline:
        time.sleep(1.0)
        rep = parse_log(LOG)
        # Stop as soon as the app's pid is gone, rather than burning the whole slack.
        if rep.get("shell_pid"):
            alive = subprocess.run(
                ["pwsh", "-NoProfile", "-Command",
                 f"@(Get-Process -Id {rep['shell_pid']} -ErrorAction SilentlyContinue).Count"],
                capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW)
            if (alive.stdout or "").strip().startswith("0"):
                print(f"shell pid {rep['shell_pid']} gone at "
                      f"+{time.perf_counter() - t0:.1f}s")
                break
    sampler.stop()
    sampler.join(timeout=10)

    names = resolve_names(sampler.by_pid)
    rep = parse_log(LOG)

    print()
    print(f"samples={sampler.samples} at 100ms  distinct pids with a window={len(sampler.by_pid)}")
    print(f"PRE-SPAWN control: pids={len(pre)}")

    # ARM A / C: who owns a visible window, BY NAME.
    family = []
    forms = []
    for pid, wins in sorted(sampler.by_pid.items()):
        name = names.get(pid, "?")
        for title, cls in wins:
            if name.lower() in PYTHON_FAMILY:
                family.append(f"{pid}:{name}:{title!r}")
            if "Sotto" in title or "WindowsForms10" in cls:
                forms.append(f"{pid}:{name}:{title!r}:{cls}")

    if args.neg_arm:
        family.append(f"{os.getpid()}:python:<injected>")

    other_seen = sum(1 for snap in sampler.per_sample if snap - {os.getpid()})
    arm_a = not forms
    arm_b = other_seen > 0
    arm_c = not family

    print()
    print("windows seen, by pid (name: count of windows):")
    for pid, wins in sorted(sampler.by_pid.items(), key=lambda kv: -len(kv[1]))[:12]:
        titles = [t for t, _c in wins][:2]
        print(f"  pid {pid} ({names.get(pid, '?')}) {len(wins)} win {titles}")
    print()
    print(f"ARM A / no shell-or-panel window: forms={forms} -> "
          f"{'GREEN' if arm_a else 'RED'}")
    print(f"ARM B / instrument is not blind: other-pid visible in "
          f"{other_seen}/{sampler.samples} samples -> {'GREEN' if arm_b else 'RED'}")
    print(f"ARM C / no python-family window: {family} -> "
          f"{'GREEN' if arm_c else 'RED'}")
    if args.neg_arm:
        print("NEG-ARM / ARM C goes RED on a known python pid -> "
              + ("RED as required" if not arm_c else "STILL GREEN -- ARM C IS BLIND"))
        return 0 if not arm_c else 1

    print()
    print("SHELL LOG " + str(LOG))
    if not rep.get("exists"):
        print("  NO LOG AT ALL -- the run left no receipt")
    else:
        print(f"  bytes={rep['bytes']} lines={rep['lines']} shell_pid={rep['shell_pid']}")
        print(f"  WORKER_AUTOSTART: {rep['autostart']}")
        print(f"  WORKER_PATH: {rep['worker_path']}")
        print(f"  BRIDGE_WORKER_MISSING: {rep['missing']}")
        print(f"  BRIDGE_CAPTION_SENT count={rep['caption_sent']} deaths={rep['deaths']} "
              f"malformed={rep['malformed']}")
        print(f"  PAGE_ERROR: {rep['page_error']}")
        for line in rep["captions_tail"]:
            print("  tail: " + line[:200])

    e2e = (rep.get("caption_sent", 0) > 0 and not rep.get("missing")
           and not rep.get("page_error"))
    print()
    print(f"VERDICT {'PASS' if (arm_a and arm_b and arm_c and e2e) else 'FAIL'} -- "
          f"no_window={arm_a} instrument_not_blind={arm_b} no_python_window={arm_c} "
          f"captions_through_the_shell={rep.get('caption_sent', 0) > 0}")
    return 0 if (arm_a and arm_b and arm_c and e2e) else 1


if __name__ == "__main__":
    raise SystemExit(main())
