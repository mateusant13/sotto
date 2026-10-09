#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_main/_focus-window-census.py -- censo de janelas do MEU pid, a cadencia
propria (a regra da casa: 60 s nao prova ausencia).

Enumera as janelas top-level visiveis a cada `--cadence-ms` e responde:
  * o pid vigiado teve alguma janela WS_VISIBLE?  (a afirmacao a provar = 0)
  * o CONTROLADO positivo (um pid que SE SABE ter janela visivel, tipicamente o
    processo em foco do dono) apareceu?  (se 0, o instrumento esta cego)

As duas cores na MESMA corrida. Nao cria janela nenhuma.

  pythonw.exe _main\\_focus-window-census.py --secs 300 --cadence-ms 50 \\
      --watch-pid 1234 --control-pid 5678 --out _main\\focus-census.json
"""
import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

GW_HWNDNEXT = 2
user32.GetTopWindow.restype = wintypes.HWND
user32.GetTopWindow.argtypes = [wintypes.HWND]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]


def pid_of(hwnd):
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def enum_visible():
    """{pid: [(hwnd,title,class), ...]} das janelas top-level visiveis."""
    out = {}
    h = int(user32.GetTopWindow(None) or 0)
    n = 0
    while h and n < 4000:
        n += 1
        if user32.IsWindowVisible(h):
            pid = pid_of(h)
            tb = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(h, tb, 512)
            cb = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cb, 256)
            out.setdefault(pid, []).append(
                {"hwnd": "0x%08X" % (h & 0xFFFFFFFFFFFFFFFF), "title": tb.value, "class": cb.value})
        h = int(user32.GetWindow(h, GW_HWNDNEXT) or 0)
    return out, n


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--secs", type=float, default=300.0)
    p.add_argument("--cadence-ms", type=float, default=50.0)
    p.add_argument("--watch-pid", type=int, action="append", default=[])
    p.add_argument("--control-pid", type=int, action="append", default=[])
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    t0 = time.time()
    samples = 0
    watch_hits = {pid: 0 for pid in a.watch_pid}
    control_hits = {pid: 0 for pid in a.control_pid}
    watch_examples = {}
    control_examples = {}
    foreground_visible_samples = 0
    total_visible_samples = 0
    nxt = time.perf_counter()
    while time.time() - t0 < a.secs:
        vis, walked = enum_visible()
        samples += 1
        total_visible_samples += sum(len(v) for v in vis.values())
        for pid in a.watch_pid:
            if pid in vis:
                watch_hits[pid] += 1
                watch_examples.setdefault(pid, vis[pid][:3])
        for pid in a.control_pid:
            if pid in vis:
                control_hits[pid] += 1
                control_examples.setdefault(pid, vis[pid][:3])
        fg = int(user32.GetForegroundWindow() or 0)
        if fg and pid_of(fg) in vis:
            foreground_visible_samples += 1
        nxt += a.cadence_ms / 1000.0
        d = nxt - time.perf_counter()
        if d > 0:
            time.sleep(d)
        else:
            nxt = time.perf_counter()

    out = {
        "secs": a.secs, "cadence_ms": a.cadence_ms, "samples": samples,
        "wall_s": round(time.time() - t0, 3),
        "watch_pids": a.watch_pid, "watch_visible_samples": watch_hits,
        "watch_examples": watch_examples,
        "control_pids": a.control_pid, "control_visible_samples": control_hits,
        "control_examples": control_examples,
        "foreground_visible_samples": foreground_visible_samples,
        "avg_visible_windows_per_sample": (round(total_visible_samples / samples, 2) if samples else None),
        "self_pid": os.getpid(),
    }
    out["verdict"] = {
        "watch_is_clean": all(v == 0 for v in watch_hits.values()) if watch_hits else None,
        "control_is_alive": any(v > 0 for v in control_hits.values()) if control_hits else None,
    }
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
