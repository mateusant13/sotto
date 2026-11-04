# THE MIN-CONTENT FLOOR OF THE PANEL CHAIN -- measured, not reasoned about.
#
# WHY. The shell's own --dump-dom measures the REAL panel at its REAL size
# (viewport 380x900) and reports DOMDUMP boxes; a headless --dump-dom cannot: on this
# box every request at or under 515 renders 492 inner (measured three ways in
# _floor-arms.py). So the panel arm of rects.py has been reporting 492 and the
# shipped width was unmeasured by DOM.
#
# MEASURED 2026-10-09 with the shell's --dump-dom at the shipped 380:
#   viewport [380,900], body [380,900]
#   #panel          rect [0,0,380,900]
#   .captions       rect [15,93,416,740]      <-- 416 wide inside a 380 panel
#   .captions__body rect [15,116,416,716]
#   #placeholder    rect [16,117,414,714]
#   .status         rect [15,843,416,47]
#   .panel__header  rect [15,15,416,28]
# i.e. the panel's children are ~36 px WIDER than the panel holding them. At 492
# (rects.py) the same children measure 462 and the box EXACTLY fills the panel
# (15 + 462 + 15 = 492), so a 492-wide arm structurally cannot see the overflow.
#
# WHAT THIS PROBE MEASURES. The min-content width of every element under #panel:
# the width below which a box CANNOT shrink. An element whose min-content exceeds
# the panel's content box at the shipped width is what pushes the chain to 416.
# It runs at a width the headless arm CAN reach (520 -> inner 496, above the floor)
# because min-content does not depend on the viewport.
#
# RUN:  pyw -3 _main/_design-lane/_mincontent.py [--themes theme-3] [--surface panel]

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rects  # noqa: E402

# NOTE 1 -- NO INLINE <script> HERE, EVER. panel.html:24 carries
# `script-src 'self'`, so the page's own CSP REFUSES any inline script while the
# external `_rects.js` beside it is allowed: this probe therefore ships its code as
# EXTERNAL files in the work dir, exactly like rects.py ships `_rects.js`. Measured
# 2026-10-09: a sink written by an inline script serialises EMPTY, which reports
# NO-PROBE-OUTPUT while the page rendered perfectly (the bug this note records).
# NOTE 2 -- window.__MINC is only DEFINED here; the runner CALLS it on
# DOMContentLoaded. A definition that self-executes runs at parse time, before
# `#panel` may exist, and the later call then returns undefined.
JS = r"""
window.__MINC = function () {
  const name = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string' && el.className.trim()
      ? '.' + el.className.trim().replace(/\s+/g, '.') : '');
  // Off-DOM sizer: the wrapper is sized to min-content, so its used width is the
  // clone's minimum width. Fixed-position + left:-99999px keeps it out of the
  // measured layout and out of the viewport.
  const minContent = (el) => {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:fixed;left:-99999px;top:0;height:0;' +
                         'width:min-content;visibility:hidden;';
    const clone = el.cloneNode(true);
    clone.style.width = 'min-content';
    clone.style.position = 'static';
    clone.style.maxWidth = 'none';
    wrap.appendChild(clone);
    document.body.appendChild(wrap);
    const w = wrap.getBoundingClientRect().width;
    wrap.remove();
    return Math.round(w * 100) / 100;
  };
  const panel = document.querySelector('#panel') || document.querySelector('.panel');
  const pcs = panel ? getComputedStyle(panel) : null;
  const padL = pcs ? parseFloat(pcs.paddingLeft) || 0 : 0;
  const padR = pcs ? parseFloat(pcs.paddingRight) || 0 : 0;
  const rows = [];
  if (panel) {
    rows.push({ name: '#panel', w: panel.getBoundingClientRect().width,
                minc: minContent(panel), self: true });
    const all = panel.querySelectorAll('*');
    for (const el of all) {
      if (!el.getClientRects().length) continue;
      const m = minContent(el);
      if (m > 140) rows.push({ name: name(el), w: Math.round(el.getBoundingClientRect().width * 100) / 100, minc: m });
    }
  }
  return { panel: panel ? { name: '#panel', w: panel.getBoundingClientRect().width,
                             padL: padL, padR: padR } : null,
           rows: rows };
};
"""

# The runner, the second external file. It CREATES its own sink (a `<pre>` is
# cheap and survives CSP's style rules), so the probe never depends on an element
# the injection happens to insert, and a throw is written into the sink too.
RUNNER = r"""
window.__mincSink = function (text) {
  var pre = document.getElementById('minc-out');
  if (!pre) { pre = document.createElement('pre'); pre.id = 'minc-out'; }
  pre.textContent = text;
  document.body.appendChild(pre);
};
function __mincGo() {
  try {
    window.__mincSink(JSON.stringify(window.__MINC()));
  } catch (e) {
    window.__mincSink(JSON.stringify({ error: String(e),
                                      stack: (e && e.stack) || '' }));
  }
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () { setTimeout(__mincGo, 300); });
} else {
  setTimeout(__mincGo, 300);
}
"""


def measure(html_path, w, h, js_path):
    url = 'file:///' + html_path.replace(os.sep, '/')
    cmd = [rects.EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
           '--no-default-browser-check', '--hide-scrollbars',
           '--force-device-scale-factor=1', '--virtual-time-budget=8000',
           '--window-size=%d,%d' % (w, h), '--dump-dom', url]
    proc = subprocess.run(cmd, capture_output=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
    return (proc.stdout or b'').decode('utf-8', 'replace')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--themes', default='theme-3')
    ap.add_argument('--surface', default='panel', choices=('panel', 'strip'))
    ap.add_argument('--size', default='520x992')
    ap.add_argument('--work', default=None)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    w, h = [int(x) for x in args.size.lower().split('x')]
    work = args.work or os.path.join(os.environ.get('TMPDIR', 'I:/cc-tmp'), 'mincontent')
    if os.path.isdir(work):
        shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)

    # rects.build() writes the panel fixture; the two probe files go beside it so
    # the stylesheet load order and the data-theme/data-surface rewrites stay the
    # SHIPPED ones -- only the measuring script differs.
    html = rects.build(args.themes, args.surface, work)
    # EXTERNAL FILES, NOT AN INLINE TAG: panel.html:24's CSP is `script-src
    # 'self'`, which refuses an inline `<script>` and allows a sibling file.
    jspath = os.path.join(work, '_minc.js')
    runpath = os.path.join(work, '_mincrun.js')
    with open(jspath, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(JS)
    with open(runpath, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(RUNNER)
    src = open(html, encoding='utf-8').read()
    if '_mincrun.js' not in src:
        tags = ('<script src="_minc.js"></script>'
                '<script src="_mincrun.js"></script>')
        src = src.replace('</body>', tags + '</body>')
        with open(html, 'w', encoding='utf-8') as fh:
            fh.write(src)

    dom = measure(html, w, h, jspath)
    # Attributes between the id and ">" are allowed: the sink carries a
    # style, so a regex that demands the immediate ">" never matches.
    m = re.search(r'<pre id="minc-out"[^>]*>(.*?)</pre>', dom, re.S)
    if not m:
        print('NO-PROBE-OUTPUT (dom %d B)' % len(dom))
        return 1
    data = json.loads(m.group(1))
    panel = data.get('panel')
    if not panel:
        print('NO #panel in this surface (surface=%s)' % args.surface)
        return 1
    content = panel['w'] - panel['padL'] - panel['padR']
    print('surface=%s theme=%s  window=%dx%d  inner=%dx%d (this arm is ABOVE the 492 floor)'
          % (args.surface, args.themes, w, h, w - 24, h - 92))
    print('#panel  %.1f wide, padding L/R %.1f/%.1f -> CONTENT BOX %.1f'
          % (panel['w'], panel['padL'], panel['padR'], content))
    print('SHIPPED PANEL: 380 wide; same padding %.1f/%.1f -> shipped content box %.1f.'
          % (panel['padL'], panel['padR'], 380 - panel['padL'] - panel['padR']))
    print('')
    print('%-42s %10s %10s  %s' % ('element', 'rect w', 'min-content', 'verdict'))
    widest = 0
    for r in data['rows']:
        if r['minc'] > widest:
            widest = r['minc']
        over = r['minc'] > content
        print('%-42s %10.1f %10.1f  %s' % (r['name'][:42], r['w'], r['minc'],
              'EXCEEDS CONTENT BOX' if over else 'fits'))
    print('')
    print('MIN-CONTENT FLOOR of the chain: %.1f px (widest element above)' % widest)
    if widest > content:
        print('VERDICT: the panel cannot be narrower than %.1f + padding = %.1f px.' % (widest, widest + panel['padL'] + panel['padR']))
        print('         The shipped panel is 380 px, so its children OVERFLOW by %.1f px' % (widest + panel['padL'] + panel['padR'] - 380))
        print('         -- which is what the shell --dump-dom measured as .captions 416 wide.')
    else:
        print('VERDICT: every element fits its content box; the 416 px measured at 380')
        print('         comes from somewhere else.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
