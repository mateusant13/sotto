"""Does `COREWEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` reach the WebView2?

The probe needs the DevTools endpoint on a PRIVATE instance of the real
shell, and the shell's code must not be edited. Two candidate injection
points, both measured here:

  A  the environment variable `COREWEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`
  B  `webview.settings['REMOTE_DEBUGGING_PORT']` (pywebview's own setting)

pywebview builds `props.AdditionalBrowserArguments` itself
(`platforms/edgechromium.py:82-91`) and APPENDS `--remote-debugging-port=<N>`
when the setting is not None. The environment variable is the WebView2
runtime's own hook and is independent of pywebview.

This script answers: which of the two actually opens the port?
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


def main():
    child_path = os.path.join(HERE, '_cdp-inject-child.py')
    with open(child_path, 'w', encoding='utf-8') as fh:
        fh.write(CHILD)
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
        proc = subprocess.Popen([sys.executable, child_path], env=env,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.time() + 25
        opened = False
        while time.time() < deadline and proc.poll() is None:
            if port_open(port):
                opened = True
                break
            time.sleep(0.4)
        detail = ''
        if opened:
            try:
                with urllib.request.urlopen(
                        'http://127.0.0.1:%d/json/list' % port, timeout=5) as r:
                    detail = 'targets=%d' % len(json.loads(r.read().decode()))
            except Exception as exc:  # noqa: BLE001
                detail = 'json ERR %r' % (exc,)
        print('MODE=%-9s port=%d opened=%s %s'
              % (mode, port, opened, detail), flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    try:
        os.remove(child_path)
    except OSError:
        pass


if __name__ == '__main__':
    main()
