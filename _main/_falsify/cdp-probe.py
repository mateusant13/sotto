"""Is CDP reachable from a pywebview WebView2 with REMOTE_DEBUGGING_PORT set?

THE RENDERER'S OWN TESTIMONY. With `--remote-debugging-port`, the WebView2
exposes a DevTools endpoint. `Page.captureScreenshot` asks the RENDERER for
its own composited output -- a channel that never touches `PrintWindow`,
`WM_PRINT`, or the DWM redirection path. That makes it a genuinely different
instrument from the census's.

THE HOUSE CONSTRAINT: a MEDIUM-integrity child cannot initialise the WebView2
here (measured by the house: `WEBVIEW2_INIT_FAILED 0x80010108`), so this probe
must run at the owner's HIGH integrity -- `launch-as-token.py` provides it.

Everything goes to a file: a pywebview app owns the console.

    FALSIFY_OUT=I:\\cc-tmp\\_falsify\\cdp-out.txt \\
        python _main/_falsify/cdp-probe.py
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

OUT_PATH = os.environ.get('FALSIFY_OUT',
                           r'I:\cc-tmp\_falsify\cdp-out.txt')
OUT = open(OUT_PATH, 'w', encoding='utf-8')


def log(*a):
    OUT.write(' '.join(str(x) for x in a) + '\n')
    OUT.flush()


PORT = int(os.environ.get('FALSIFY_CDP_PORT', '9333'))

os.environ.setdefault('PYWEBVIEW_LOG', 'ERROR')
import webview  # noqa: E402

webview.settings['REMOTE_DEBUGGING_PORT'] = PORT
log('settings REMOTE_DEBUGGING_PORT =', webview.settings['REMOTE_DEBUGGING_PORT'])

HTML = """<html><body style="margin:0;background:#101418">
<div style="width:120px;height:80px;background:#e0e0e0"></div>
<div style="width:60px;height:40px;background:#3060a0"></div>
<script>window.__ready=1;</script></body></html>"""

win = webview.create_window('cdp-probe', html=HTML, width=380, height=140,
                            x=-10000, y=-10000, frameless=True, hidden=True)
log('window created hwnd=', getattr(win, 'gui', None) and 'yes')
try:
    webview.start(win)
except Exception as exc:  # noqa: BLE001
    log('webview.start EXC', repr(exc))
log('webview.start returned')
OUT.close()
