"""The CDP CLIENT: attach to a WebView2 DevTools endpoint and ask the renderer
for its own frame.

THE CHANNEL. `Page.captureScreenshot` makes the RENDERER composite its own
content and return a PNG. Nothing in that path calls `PrintWindow`, `WM_PRINT`,
or the DWM redirection surface -- the pixels come from the WebView2's own
compositor. That is what makes this a DIFFERENT instrument from the census's.

THE VERDICT. The PNG is decoded and classified with a rule that is NOT the
census's rule: the census uses a strided-sample `std`/`spread` on a BGRA
buffer; this one counts DISTINCT COLOURS over the decoded image and computes
the per-channel standard deviation over the RGB samples. A blank frame is one
with (almost) no distinct colours; a content frame has many. Both numbers are
printed, so a reader can apply either threshold.

THE CONNECTION. `websocket-client` is installed; `Page.captureScreenshot` needs
a websocket, not the HTTP endpoint.

USAGE: python _main/_falsify/cdp-client.py <port> [outfile]
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import urllib.request


def log(*a):
    print(*a, flush=True)


def fetch_targets(port, timeout=5):
    url = 'http://127.0.0.1:%d/json/list' % port
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', 'replace'))


def classify_png(data):
    """Distinct colours + per-channel std over the DECODED image."""
    try:
        from PIL import Image
    except ImportError:
        return 'no-pillow'
    img = Image.open(io.BytesIO(data)).convert('RGB')
    w, h = img.size
    colours = img.getcolors(maxcolors=1 << 20)
    distinct = len(colours) if colours is not None else '>1M'
    px = list(img.getdata())
    if not px:
        return 'empty-image'
    step = max(1, len(px) // 4096)
    sample = px[::step]
    n = len(sample)
    means = [sum(c[i] for c in sample) / n for i in range(3)]
    stds = []
    for i in range(3):
        var = sum((c[i] - means[i]) ** 2 for c in sample) / n
        stds.append(var ** 0.5)
    std = (stds[0] ** 2 + stds[1] ** 2 + stds[2] ** 2) ** 0.5
    return ('size=%dx%d distinct=%s rgb_std=%.2f (per-channel %s) mean=(%.1f,%.1f,%.1f)'
            % (w, h, distinct, std,
               ','.join('%.2f' % s for s in stds),
               means[0], means[1], means[2]))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9333
    try:
        targets = fetch_targets(port)
    except Exception as exc:
        log('CDP_UNREACHABLE port=%d %r' % (port, exc))
        return 2
    log('CDP targets=%d' % len(targets))
    for t in targets:
        log('  target type=%s title=%r ws=%s' %
            (t.get('type'), t.get('title'), t.get('webSocketDebuggerUrl')))

    page = None
    for t in targets:
        if t.get('type') == 'page' and t.get('webSocketDebuggerUrl'):
            page = t
            break
    if page is None:
        log('CDP_NO_PAGE')
        return 3

    import websocket
    ws = websocket.create_connection(page['webSocketDebuggerUrl'],
                                     timeout=10)
    counter = [0]

    def cmd(method, params=None):
        counter[0] += 1
        ws.send(json.dumps({'id': counter[0], 'method': method,
                            'params': params or {}}))
        deadline = time.time() + 15
        while time.time() < deadline:
            msg = json.loads(ws.recv())
            if msg.get('id') == counter[0]:
                return msg
        return None

    ready = cmd('Runtime.evaluate',
                {'expression': 'String(window.__ready)', 'returnByValue': True})
    log('RENDERER window.__ready ->', json.dumps(ready)[:200])

    # `Page.enable` first: captureScreenshot on a page whose Page domain was
    # never enabled can simply never answer (measured: timeout 15 s).
    en = cmd('Page.enable')
    log('Page.enable ->', json.dumps(en)[:120])
    shot = cmd('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
    if not shot or 'result' not in shot:
        log('SCREENSHOT_ERR', json.dumps(shot)[:300])
        return 4
    data = shot['result']['data']
    png = base64.b64decode(data)
    out = os.environ.get('FALSIFY_SHOT_OUT')
    if out:
        with open(out, 'wb') as fh:
            fh.write(png)
        log('PNG saved %s (%d bytes)' % (out, len(png)))
    log('SCREENSHOT bytes=%d %s' % (len(png), classify_png(png)))
    ws.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
