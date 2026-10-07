#!/usr/bin/env python3
"""THROWAWAY GEOMETRY PROBE — does the panel fit its own window?

Why this exists: `_main/render-panel-temas.py` has to choose a `--window-size`
for the captures. The brief says 1920x1080; `app/webview/sotto_webview.py` says
PANEL_WIDTH=380 / PANEL_HEIGHT=900. A 380-wide smoke shot of the real
`panel.html` looked CLIPPED, so before designing the fixture this probe measures
the panel's own layout box at both sizes and names the elements that overflow.

It copies the live panel files into a scratch dir (the page cannot be measured
in place without a script tag), appends ONE metrics script, and dumps the DOM at
two window sizes. Nothing in H:\\sotto is written.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
SRC = r'H:\sotto\app\panel'
DST = r'H:\aireplay\_main\_panel-geom-probe'

ASSETS = [
    'panel.html', 'panel.css', 'panel.js', 'caption-formulation.js',
    'history-source.js', 'surface.js', 'theme-switcher.js',
    'themes/themes.js', 'themes/fonts.css',
    'themes/theme-1.css', 'themes/theme-2.css', 'themes/theme-3.css',
    'themes/theme-4.css', 'themes/theme-5.css',
]

METRICS_JS = r'''
(function () {
  function box(sel) {
    var el = document.querySelector(sel);
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return { w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10,
             client: el.clientWidth, scroll: el.scrollWidth };
  }
  var over = [];
  var all = document.querySelectorAll('.panel *');
  for (var i = 0; i < all.length; i += 1) {
    var el = all[i];
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
      over.push({ tag: el.tagName, cls: String(el.className || '').slice(0, 60),
                  id: el.id || '', client: el.clientWidth, scroll: el.scrollWidth });
    }
  }
  var panel = document.querySelector('.panel');
  var out = {
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    dpr: window.devicePixelRatio,
    docClient: document.documentElement.clientWidth,
    docScroll: document.documentElement.scrollWidth,
    bodyScroll: document.body.scrollWidth,
    panel: box('.panel'),
    panelGridCols: panel ? getComputedStyle(panel).gridTemplateColumns : null,
    header: box('.panel__header'),
    controls: box('.panel__controls'),
    wordmark: box('.wordmark'),
    captions: box('.captions'),
    captionsBody: box('.captions__body'),
    captionList: box('#caption-list'),
    history: box('#history'),
    hud: box('.hud'),
    hudActions: box('.hud__actions'),
    status: box('.status'),
    themeButton: box('#theme-button'),
    overflowing: over.slice(0, 24),
    overflowingCount: over.length
  };
  var pre = document.createElement('pre');
  pre.id = '_geom';
  pre.hidden = true;
  pre.textContent = JSON.stringify(out, null, 1);
  document.body.appendChild(pre);
})();
'''


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest().upper()


def build():
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    os.makedirs(os.path.join(DST, 'themes'), exist_ok=True)
    os.makedirs(os.path.join(DST, 'fonts'), exist_ok=True)
    read = {}
    for rel in ASSETS:
        s = os.path.join(SRC, rel.replace('/', os.sep))
        d = os.path.join(DST, rel.replace('/', os.sep))
        shutil.copy2(s, d)
        read[rel] = sha256(s)
    for name in os.listdir(os.path.join(SRC, 'fonts')):
        s = os.path.join(SRC, 'fonts', name)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(DST, 'fonts', name))
            read['fonts/' + name] = sha256(s)
    with open(os.path.join(DST, '_geom.js'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(METRICS_JS)
    p = os.path.join(DST, 'panel.html')
    with open(p, encoding='utf-8') as fh:
        html = fh.read()
    html = html.replace('</body>', '    <script src="_geom.js"></script>\n  </body>')
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)
    return read


def dump(width, height, tag):
    prof = os.path.join(DST, 'prof-' + tag)
    url = 'file:///' + os.path.join(DST, 'panel.html').replace('\\', '/')
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars',
           '--mute-audio', '--no-first-run', '--no-default-browser-check',
           '--disable-extensions', '--user-data-dir=' + prof,
           '--window-size=%d,%d' % (width, height), '--virtual-time-budget=3000',
           '--dump-dom', url]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=120)
    dom = r.stdout or ''
    i = dom.find('<pre id="_geom"')
    if i < 0:
        print('NO METRICS in dump for', tag, 'rc=', r.returncode)
        print(dom[:2000])
        return None
    j = dom.find('>', i) + 1
    k = dom.find('</pre>', j)
    return json.loads(dom[j:k].replace('&quot;', '"').replace('&amp;', '&')
                      .replace('&lt;', '<').replace('&gt;', '>'))


if __name__ == '__main__':
    read = build()
    print('read %d files from %s' % (len(read), SRC))
    for rel in ('panel.html', 'panel.css', 'panel.js'):
        print('  %-24s %s' % (rel, read[rel]))
    for w, h in ((380, 900), (1920, 1080)):
        print('\n=== window %dx%d ===' % (w, h))
        m = dump(w, h, '%dx%d' % (w, h))
        if m:
            print(json.dumps(m, indent=1))
    sys.exit(0)
