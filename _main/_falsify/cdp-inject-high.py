"""Which CDP injection point works AT THE OWNER'S INTEGRITY?

The WebView2 on this box refuses to initialise from a MEDIUM process
(measured by the house: `WEBVIEW2_INIT_FAILED 0x80010108`), so the
injection test has to run HIGH. `launch-as-token.py` provides the owner's
token; the child is DETACHED and has no console, so everything is written
to a file.

ARMS:
  env        COREWEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=N
  settings   webview.settings['REMOTE_DEBUGGING_PORT'] = N

The shell's own code is never edited: both arms are separate children.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_cdp-inject-out.txt')

CHILD = r'''
import os, sys, time
os.environ.setdefault('PYWEBVIEW_LOG', 'ERROR')
import webview
MODE = os.environ.get('FALSIFY_CDP_MODE', 'env')
PORT = int(os.environ.get('FALSIFY_CDP_PORT', '9401'))
if MODE == 'settings':
    webview.settings['REMOTE_DEBUGGING_PORT'] = PORT
HTML = "<html><body style='background:#123'><div style='width:80px;height:60px;background:#eee'></div></body></html>"
w = webview.create_window('t', html=HTML, width=300, height=120,
                          x=-10000, y=-10000, frameless=True, hidden=True)
webview.start(w)
'''


def port_open(port, timeout=1.0):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(('127.0.0.1', port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main():
    child_path = os.path.join(HERE, '_cdp-inject-child.py')
    with open(child_path, 'w', encoding='utf-8') as fh:
        fh.write(CHILD)
    lines = []
    for mode in ('env', 'settings'):
        port = 9401 if mode == 'env' else 9402
        env = dict(os.environ)
        env['FALSIFY_CDP_MODE'] = mode
        env['FALSIFY_CDP_PORT'] = str(port)
        env['PYWEBVIEW_LOG'] = 'ERROR'
        if mode == 'env':
            env['COREWEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = (
                '--remote-debugging-port=%d' % port)
        else:
            env.pop('COREWEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', None)
        # The elevated child is DETACHED: it inherits the environment.
        proc = subprocess.Popen(
            [sys.executable, child_path], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000)
        deadline = time.time() + 30
        opened = False
        while time.time() < deadline:
            if port_open(port):
                opened = True
                break
            time.sleep(0.4)
        detail = ''
        if opened:
            try:
                with urllib.request.urlopen(
                        'http://127.0.0.1:%d/json/list' % port,
                        timeout=5) as r:
                    data = json.loads(r.read().decode())
                    detail = 'targets=%d types=%s' % (
                        len(data), [d.get('type') for d in data])
            except Exception as exc:  # noqa: BLE001
                detail = 'json ERR %r' % (exc,)
        lines.append('MODE=%-9s port=%d opened=%s %s'
                     % (mode, port, opened, detail))
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(1.0)
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    try:
        os.remove(child_path)
    except OSError:
        pass


if __name__ == '__main__':
    main()
