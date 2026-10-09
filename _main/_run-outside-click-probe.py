#!/usr/bin/env python3
"""Run the shell's `--probe-outside-click` mode and wait for it.

A launcher, not a measurement: the shell's own log is the instrument. `pythonw.exe`
with CREATE_NO_WINDOW, and the pid is tracked exactly so nothing is left behind.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
PYW = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
LOG = os.path.join(HERE, '_outside-click-probe.log')

if os.path.exists(LOG):
    os.remove(LOG)
cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--no-tray',
       '--probe-outside-click', '--log', LOG]
proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL),
                        creationflags=0x08000000,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f'pid={proc.pid} log={LOG}')
try:
    proc.wait(timeout=45)
except Exception:
    proc.kill()
print(f'rc={proc.returncode}')
