#!/usr/bin/env python3
"""What viewport does `--window-size` really give headless Chrome here?

The panel's own geometry is 380x900 (app/webview/sotto_webview.py PANEL_WIDTH/
PANEL_HEIGHT). A capture of it must use a viewport of exactly that, or the
"screenshot" is a picture of a layout the owner never sees. This probe measures
the mapping (requested window size, forced scale factor) -> (innerWidth,
innerHeight, PNG size) with unique profile dirs and one Chrome at a time.

Also answers: does Chrome clamp the window to a minimum width?
"""

import json
import os
import subprocess
import tempfile

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
TMP = os.path.join(tempfile.gettempdir(), 'sotto-vp2')
os.makedirs(TMP, exist_ok=True)

HTML = """<!doctype html><html><body><pre id="vp"></pre>
<script>
window.addEventListener('load', function () {
  document.getElementById('vp').textContent = JSON.stringify({
    iw: innerWidth, ih: innerHeight, dpr: devicePixelRatio,
    ow: outerWidth, oh: outerHeight, sw: screen.width, sh: screen.height,
    docClient: document.documentElement.clientWidth,
    docClientH: document.documentElement.clientHeight
  });
});
</script></body></html>
"""
PAGE = os.path.join(TMP, 'vp.html')
with open(PAGE, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(HTML)
URL = 'file:///' + PAGE.replace('\\', '/')

FLAGS = ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--mute-audio',
         '--no-first-run', '--no-default-browser-check', '--disable-extensions',
         '--disable-sync', '--disable-background-networking']


def run(extra, tag, timeout=90):
    prof = os.path.join(TMP, 'prof-' + tag)
    cmd = [CHROME] + FLAGS + ['--user-data-dir=' + prof] + extra
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=timeout)
        return r.stdout or '', r.returncode
    except subprocess.TimeoutExpired:
        return '', 'TIMEOUT'


def png_size(path):
    try:
        with open(path, 'rb') as fh:
            head = fh.read(33)
        if head[:8] != b'\x89PNG\r\n\x1a\n':
            return 'not-png'
        import struct
        w, h = struct.unpack('>II', head[16:24])
        return (w, h)
    except OSError:
        return 'missing'


combos = [(380, 900, 2), (380, 900, 1), (396, 995, 1), (500, 1000, 1),
          (760, 1800, 2), (420, 940, 1), (1920, 1080, 1), (380, 900, 3)]
print('%-14s %-6s %-34s %s' % ('requested', 'scale', 'viewport (from page)', 'png'))
for w, h, s in combos:
    tag = '%dx%d-s%d' % (w, h, s)
    base = ['--window-size=%d,%d' % (w, h), '--force-device-scale-factor=%d' % s,
            '--virtual-time-budget=1500']
    dom, rc = run(base + ['--dump-dom', URL], tag + '-dom')
    vp = 'rc=%s no-metrics' % rc
    i = dom.find('<pre id="vp">')
    if i >= 0:
        j = i + len('<pre id="vp">')
        k = dom.find('</pre>', j)
        vp = dom[j:k] or 'EMPTY'
    shot = os.path.join(TMP, 'shot-%s.png' % tag)
    if os.path.exists(shot):
        os.remove(shot)
    _, rc2 = run(base + ['--screenshot=' + shot, URL], tag + '-shot')
    print('%-14s %-6s %-34s %s' % ('%dx%d' % (w, h), s, vp, png_size(shot)))
