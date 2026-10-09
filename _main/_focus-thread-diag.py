#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_main/_focus-thread-diag.py -- de ONDE vem cada thread do probe.

O probe do foco mediu 3 threads no fim e 5 no arranque, acima do orcamento de 2
desta lane. Este diagnostico isola a origem, passo a passo, para o recibo poder
dizer a verdade em vez de arredondar.

  pythonw.exe _main\\_focus-launch.py <log> _main\\_focus-thread-diag.py
"""
import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                         ctypes.c_void_p, wintypes.DWORD]

steps = []


def snap(label):
    try:
        import psutil
        p = psutil.Process(os.getpid())
        ids = sorted(t.id for t in p.threads())
        steps.append({"step": label, "n": len(ids), "ids": ids})
    except Exception as exc:
        steps.append({"step": label, "error": repr(exc)})


snap("0-modulo-carregado")
import psutil                                                    # noqa: E402
snap("1-import-psutil")
list(psutil.process_iter(["pid", "name", "cmdline"]))
snap("2-process_iter-completo")

stop = threading.Event()


def worker():
    while not stop.is_set():
        time.sleep(0.01)


th = threading.Thread(target=worker, daemon=True)
th.start()
snap("3-thread-poller-a-correr")

h = user32.GetForegroundWindow()
v = wintypes.DWORD(0)
for _ in range(50):
    dwmapi.DwmGetWindowAttribute(h, 14, ctypes.byref(v), 4)
snap("4-apos-50-DwmGetWindowAttribute")

stop.set()
th.join(timeout=2)
snap("5-apos-poller-parar")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "focus-thread-diag.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump({"pid": os.getpid(), "steps": steps}, f, ensure_ascii=False, indent=2)
