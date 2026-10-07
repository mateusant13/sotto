#!/usr/bin/env python3
"""Is `--screenshot` a CROP or a SCALE of a differently-sized viewport?

Measured: `--window-size=380,900` gives `innerWidth=500`, `innerHeight=805`, but
a 380x900 PNG. One of those two is a lie, and which one decides whether ANY
capture in this lane can be trusted. This page makes it visible: a 100x100 red
square at the origin (a scale changes its size, a crop does not), a 1px magenta
line at x=379, and a 1px cyan line at x=499.
"""

import os
import struct
import subprocess
import tempfile

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
TMP = os.path.join(tempfile.gettempdir(), 'sotto-crop')
os.makedirs(TMP, exist_ok=True)

HTML = """<!doctype html><html><head><style>
html,body{margin:0;padding:0;background:#111}
#sq{position:absolute;left:0;top:0;width:100px;height:100px;background:#f00}
#l379{position:absolute;left:379px;top:0;width:1px;height:200px;background:#f0f}
#l499{position:absolute;left:499px;top:0;width:1px;height:200px;background:#0ff}
#l899{position:absolute;left:0;top:899px;width:200px;height:1px;background:#ff0}
#vp{position:absolute;left:0;top:120px;color:#fff;font:16px monospace}
</style></head><body>
<div id="sq"></div><div id="l379"></div><div id="l499"></div><div id="l899"></div>
<pre id="vp"></pre>
<script>
window.addEventListener('load', function () {
  document.getElementById('vp').textContent =
    'iw=' + innerWidth + ' ih=' + innerHeight + ' dpr=' + devicePixelRatio;
});
</script></body></html>
"""
PAGE = os.path.join(TMP, 'crop.html')
with open(PAGE, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(HTML)
URL = 'file:///' + PAGE.replace('\\', '/')

FLAGS = ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--mute-audio',
         '--no-first-run', '--no-default-browser-check', '--disable-extensions']


def shot(w, h, s, tag):
    prof = os.path.join(TMP, 'prof-' + tag)
    out = os.path.join(TMP, 'crop-%s.png' % tag)
    if os.path.exists(out):
        os.remove(out)
    cmd = [CHROME] + FLAGS + ['--user-data-dir=' + prof,
                              '--window-size=%d,%d' % (w, h),
                              '--force-device-scale-factor=%d' % s,
                              '--virtual-time-budget=1500',
                              '--screenshot=' + out, URL]
    subprocess.run(cmd, capture_output=True, timeout=90)
    return out


def png_dims(p):
    with open(p, 'rb') as fh:
        head = fh.read(33)
    w, h = struct.unpack('>II', head[16:24])
    return w, h


def classify(p):
    """Find the red square's extent and which 1px lines survived."""
    from PIL import Image
    im = Image.open(p).convert('RGB')
    W, H = im.size
    px = im.load()
    # red square: scan row 5 for the last red pixel
    sq_w = 0
    for x in range(W):
        r, g, b = px[x, 5]
        if r > 200 and g < 60 and b < 60:
            sq_w = x + 1
        else:
            break
    sq_h = 0
    for y in range(H):
        r, g, b = px[5, y]
        if r > 200 and g < 60 and b < 60:
            sq_h = y + 1
        else:
            break
    def has_line(x, col):
        if x >= W:
            return 'off-image'
        for y in range(0, min(H, 200)):
            r, g, b = px[x, y]
            if abs(r - col[0]) < 60 and abs(g - col[1]) < 60 and abs(b - col[2]) < 60:
                return 'yes'
        return 'no'
    return {'png': (W, H), 'square': (sq_w, sq_h),
            'magenta_x379': has_line(379, (240, 0, 240)),
            'cyan_x499': has_line(499, (0, 240, 240)),
            'yellow_y899': 'yes' if H > 899 and px[5, 899][0] > 200 and px[5, 899][2] < 60 else 'no'}


for w, h, s in ((380, 900, 1), (380, 900, 2), (1920, 1080, 1), (500, 1000, 1)):
    tag = '%dx%d-s%d' % (w, h, s)
    p = shot(w, h, s, tag)
    print(tag, classify(p))
