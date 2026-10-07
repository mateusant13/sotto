#!/usr/bin/env python3
"""Does `--window-size` reflow the layout before the capture, or is the PNG a crop?

DECIDES THE WHOLE LANE: if the PNG is a crop of a wider layout, then a capture
of the panel is a picture of a layout the owner never sees, and no measurement
taken from it is worth anything.

Method: the page draws a GREEN bar whose width IS `innerWidth` at paint time, and
re-draws it on every `resize`. The PNG is then measured: a bar as wide as the PNG
means the layout was reflowed to `--window-size` before capture; a bar wider than
the PNG (clipped) means the capture is a crop.
"""

import os
import struct
import subprocess
import tempfile

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
TMP = os.path.join(tempfile.gettempdir(), 'sotto-reflow')
os.makedirs(TMP, exist_ok=True)

HTML = """<!doctype html><html><head><style>
html,body{margin:0;padding:0;background:#101010}
#bar{position:absolute;left:0;top:0;height:20px;background:#0f0}
#bar2{position:absolute;left:0;top:30px;height:20px;background:#00f}
#vp{position:absolute;left:0;top:60px;color:#fff;font:14px monospace;white-space:pre}
</style></head><body>
<div id="bar"></div><div id="bar2"></div><pre id="vp"></pre>
<script>
function paint(tag) {
  var iw = innerWidth, ih = innerHeight;
  var cw = document.documentElement.clientWidth, ch = document.documentElement.clientHeight;
  document.getElementById('bar').style.width = iw + 'px';
  document.getElementById('bar2').style.width = cw + 'px';
  document.getElementById('vp').textContent =
    tag + ' innerW=' + iw + ' innerH=' + ih + ' clientW=' + cw + ' clientH=' + ch
    + ' dpr=' + devicePixelRatio;
}
window.addEventListener('resize', function () { paint('RESIZE'); });
window.addEventListener('load', function () { paint('LOAD'); });
paint('PARSE');
</script></body></html>
"""
PAGE = os.path.join(TMP, 'reflow.html')
with open(PAGE, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(HTML)
URL = 'file:///' + PAGE.replace('\\', '/')
FLAGS = ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--mute-audio',
         '--no-first-run', '--no-default-browser-check', '--disable-extensions']


def measure(w, h, s, tag):
    prof = os.path.join(TMP, 'prof-' + tag)
    out = os.path.join(TMP, 'reflow-%s.png' % tag)
    if os.path.exists(out):
        os.remove(out)
    subprocess.run([CHROME] + FLAGS + ['--user-data-dir=' + prof,
                   '--window-size=%d,%d' % (w, h), '--force-device-scale-factor=%d' % s,
                   '--virtual-time-budget=2000', '--screenshot=' + out, URL],
                   capture_output=True, timeout=90)
    with open(out, 'rb') as fh:
        head = fh.read(33)
    pw, ph = struct.unpack('>II', head[16:24])
    from PIL import Image
    im = Image.open(out).convert('RGB')
    px = im.load()
    green = 0
    for x in range(pw):
        r, g, b = px[x, 5]
        if g > 150 and r < 100:
            green = x + 1
        else:
            break
    blue = 0
    for x in range(pw):
        r, g, b = px[x, 35]
        if b > 150 and r < 100:
            blue = x + 1
        else:
            break
    return {'png': (pw, ph), 'green_innerWidth': green, 'blue_clientWidth': blue,
            'green_clipped': green >= pw, 'blue_clipped': blue >= pw}


for w, h, s in ((380, 900, 1), (380, 900, 2), (500, 1000, 1), (1920, 1080, 1)):
    tag = '%dx%d-s%d' % (w, h, s)
    print('%-14s %s' % (tag, measure(w, h, s, tag)))
