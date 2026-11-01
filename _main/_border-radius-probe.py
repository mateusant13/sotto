#!/usr/bin/env python3
"""MEASURE the window's rounding, per theme, in a REAL Chromium (CDP).

WHY THIS EXISTS (owner, 2026-10-21):
  *"as bordas de cada design nao tao transparentes, tao cinzas/pretas. assim, nao
  ficam arredondadas pelo design."*

Two independent causes live in `app/panel/panel.css`, and neither could be seen by
grepping a rule:

  1. THE CANVAS. A background on the ROOT element PROPAGATES TO THE CANVAS, and the
     canvas background is painted across the whole viewport WITHOUT being clipped by
     the root's `border-radius` (CSS Backgrounds 3: the root's background "extends to
     cover the entire canvas"). So while `html` carried `rgba(11,15,20,0.98)`, the four
     corners stayed an opaque grey/black rectangle no matter what radius the design
     asked for.

  2. THE LITERAL FLOOR. `border-radius: 12px !important` was a LITERAL on `.panel`, so
     every design whose own radius is bigger (GlassCards `--radius-lg: 22px`, the
     cinematic family 18px) had its corner drawn INSIDE the radius it asked for. The
     floor is now `max(var(--radius, 14px), 12px)`: the 0px designs stay rounded, and
     every other design gets ITS OWN radius.

WHAT THIS PROBE READS, AND WHAT IT DELIBERATELY DOES NOT:
  It reads the COMPUTED style of `html`, `body` and `.panel` per theme, plus the
  element stack under the very corner pixel (1,1). That is the MECHANISM: if the root
  paints nothing and body's box is clipped by the same radius as the slab's, the corner
  is unpainted and the compositor shows the desktop there.

  It does NOT read the compositor's output pixels. `Page.captureScreenshot` in this
  rig renders onto an OPAQUE background (no `--default-background-color` and no
  `Emulation.setDefaultBackgroundColorOverride`), so a screenshot of a transparent
  corner would read as the rig's own white -- the same trap `_main/panel-startup-flash`
  warns about. The desktop half stays NOT MEASURED here, and says so.

  IT ALSO NEUTRALISES THE RIG'S OWN BACKGROUND. `_design-lane/shot.py:211` injects
  `html, body { background: #0b0d10; }` as `_shot.css` -- OPAQUE, ON THE ROOT, i.e. the
  exact defect pattern. Measuring the shipped CSS through that file would report the
  rig's bug as the app's. So `_shot.css` is emptied before the run; the app's own
  stylesheets are untouched.

Usage:
  py -3 _main/_border-radius-probe.py                 # every theme found in themes/
  py -3 _main/_border-radius-probe.py --themes theme-1,zipc-glass-cards
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, '_design-lane'))
import shot  # noqa: E402

DRIVER = os.path.join(HERE, '_ux-cdp.mjs')
THEMES_DIR = os.path.join(REPO, 'app', 'panel', 'themes')
WORK = 'I:/cc-tmp/border-radius'
NODE = 'node'

# A theme is whatever a stylesheet keys on `[data-theme=...]`. Read from the SHIPPED
# css, so a theme that was added or deleted is measured, not a hand-kept list.
THEME_RE = re.compile(r"""data-theme\s*=\s*['"]([^'"]+)['"]""")

PROBE = r"""
(async function () {
  'use strict';
  var wanted = __THEMES__;
  var man = window.SottoThemeManifest;
  /* THE MANIFEST'S LOOKUP IS `byName` (`themes/themes.js:282`); `find` is accepted
     too so the probe does not silently measure the BASE theme if the manifest is
     ever renamed -- a silent fallback here would file a false defect. */
  var lookup = (man && (man.byName || man.find)) ? (man.byName || man.find) : null;
  var linked = {};

  /* THE THEME'S OWN STYLESHEET, FIRST. `themes/cinematic.css` and
     `themes/panel-designs.css` are DEFERRED by `app/panel/lazy-assets.js`, which
     the SHELL injects before the page parses; without the shell's bridge its
     `ask()` retries forever and the file never arrives. So the probe links the
     theme's own file itself -- the same CSSOM the shell's gate ends up allowing --
     and WAITS for it. Measuring a `cine-*` theme without this reads the BASE
     theme's tokens and would file a false defect. */
  function linkFor(file) {
    if (linked[file]) { return linked[file]; }
    var p = new Promise(function (resolve) {
      var el = document.createElement('link');
      el.rel = 'stylesheet';
      el.href = file;
      el.onload = function () { resolve(true); };
      el.onerror = function () { resolve(false); };
      document.head.appendChild(el);
    });
    linked[file] = p;
    return p;
  }

  function bg(c) { return c.backgroundColor; }
  function rad(c) { return c.borderRadius; }
  function name(el) {
    var n = (el.tagName || '?').toLowerCase();
    var cl = el.className;
    if (cl && typeof cl === 'string') {
      var parts = cl.trim().split(/\s+/).filter(function (p) { return p.indexOf('is-') !== 0; });
      if (parts.length) { n += '.' + parts.slice(0, 3).join('.'); }
    }
    return n;
  }
  function frame() {
    return new Promise(function (r) {
      requestAnimationFrame(function () { requestAnimationFrame(r); });
    });
  }

  var out = [];
  var scripts = Array.prototype.map.call(
    document.querySelectorAll('script[src]'),
    function (s) { return s.getAttribute('src'); });
  var globals = ['SottoTheme', 'SottoThemeManifest', 'SottoSkin'].map(function (g) {
    return g + '=' + (typeof window[g]);
  });
  for (var i = 0; i < wanted.length; i += 1) {
    var t = wanted[i];
    var entry = lookup ? lookup(t) : null;
    var file = entry ? entry.file : null;
    var loaded = null;
    if (file) { loaded = await linkFor(file); }
    /* THE SWITCHER OWNS THE ATTRIBUTE. Setting it by hand is fought by its own
       MutationObserver, so go through the app's own door (same as shot.py:150). */
    try { if (window.SottoTheme && window.SottoTheme.set) { window.SottoTheme.set(t, { persist: false }); } } catch (e) {}
    document.documentElement.dataset.theme = t;
    await frame();

    var h = getComputedStyle(document.documentElement);
    var b = getComputedStyle(document.body);
    var p = document.querySelector('.panel');
    var pc = p ? getComputedStyle(p) : null;
    void document.body.offsetHeight; /* flush */
    var el = document.elementFromPoint(1, 1);
    var chain = [];
    var cur = el;
    while (cur && chain.length < 5) {
      var c = getComputedStyle(cur);
      chain.push(name(cur) + ' bg=' + bg(c) + ' r=' + rad(c));
      cur = cur.parentElement;
    }
    out.push({
      theme: t,
      file: file,
      sheet: loaded,
      manOk: !!lookup,
      manN: (man && man.themes) ? man.themes.length : 0,
      scripts: scripts,
      globals: globals,
      token: h.getPropertyValue('--radius').trim(),
      tokenLg: h.getPropertyValue('--radius-lg').trim(),
      html: { bg: bg(h), radius: rad(h) },
      body: { bg: bg(b), radius: rad(b) },
      panel: pc ? { radius: rad(pc) } : null,
      corner: chain
    });
  }
  return out;
})()
"""


def themes_on_disk():
    found = []
    for fn in sorted(os.listdir(THEMES_DIR)):
        if not fn.endswith('.css'):
            continue
        with open(os.path.join(THEMES_DIR, fn), encoding='utf-8') as fh:
            for m in THEME_RE.finditer(fh.read()):
                if m.group(1) not in found:
                    found.append(m.group(1))
    return found


def px(v):
    m = re.match(r'^([\d.]+)px$', (v or '').strip())
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser(description='the window rounding, measured')
    ap.add_argument('--themes', default='')
    ap.add_argument('--w', type=int, default=380)
    ap.add_argument('--h', type=int, default=900)
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()

    themes = [t.strip() for t in args.themes.split(',') if t.strip()] or themes_on_disk()
    if not themes:
        raise SystemExit('no theme found in %s' % THEMES_DIR)

    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    hp = shot.build(themes[0], 'panel', WORK)
    # THE RIG'S OWN OPAQUE ROOT BACKGROUND MUST GO (see the docstring).
    with open(os.path.join(WORK, '_shot.css'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('/* emptied by _border-radius-probe.py: shot.py paints the root opaque */\n')

    probe_p = os.path.join(WORK, '_probe.js')
    with open(probe_p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(PROBE.replace('__THEMES__', json.dumps(themes)))

    url = 'file:///' + hp.replace('\\', '/')
    cmd = [NODE, DRIVER, '--url', url, '--w', str(args.w), '--h', str(args.h),
           '--probe', probe_p, '--wait', '2500', '--maxtime', '90000']
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=200, cwd=REPO)
    except subprocess.TimeoutExpired:
        raise SystemExit('driver timeout')
    out = (p.stdout or '').strip()
    if not out:
        raise SystemExit('driver produced nothing; stderr=%s' % (p.stderr or '')[-600:])
    try:
        data = json.loads(out)
    except ValueError:
        raise SystemExit('driver did not return JSON: %s' % out[:600])
    if not data.get('ok'):
        raise SystemExit('driver failed: %s' % json.dumps(data)[:600])

    rows = data['probe'] or []
    print('BORDER-RADIUS PROBE -- computed style, real Chromium, viewport %dx%d'
          % (args.w, args.h))
    print('  viewport as reported by the page: %s' % json.dumps(data.get('viewport')))
    print('')
    print('  %-22s %-6s %-6s %-26s %-20s %-20s %-8s %s'
          % ('theme', 'radius', 'r-lg', 'file (sheet loaded?)', 'html bg / radius',
             'body bg / radius', '.panel r', 'verdict'))
    bad = []
    no_sheet = []
    for r in rows:
        tok = r['token']
        prad = r['panel']['radius'] if r['panel'] else 'NO .panel'
        # THE THREE CLAIMS.
        root_clear = r['html']['bg'] in ('rgba(0, 0, 0, 0)', 'transparent')
        # NOT `px(tok) or 14.0`: 0.0 is FALSY in Python, so a design that declares
        # `--radius: 0px` would be read as "no token" and the floor would come out
        # 14px -- a false defect filed against the product. 0px IS a value.
        tokpx = px(tok)
        floor = max(tokpx if tokpx is not None else 14.0, 12.0)
        matches = (px(prad) is not None and abs(px(prad) - floor) < 0.51)
        coincide = (r['body']['radius'] == prad)
        why = []
        if not r.get('manOk'):
            why.append('NO MANIFEST (SottoThemeManifest)')
        if r['sheet'] is False:
            why.append('THEME SHEET DID NOT LOAD (%s)' % (r.get('file') or '?'))
            no_sheet.append(r['theme'])
        if not root_clear:
            why.append('ROOT PAINTS %s' % r['html']['bg'])
        if not matches:
            why.append('PANEL %s != max(%s,12px)' % (prad, tok or '?'))
        if not coincide:
            why.append('BODY %s != PANEL %s' % (r['body']['radius'], prad))
        ok = not why
        if not ok:
            bad.append((r['theme'], '; '.join(why)))
        print('  %-22s %-6s %-6s %-26s %-20s %-20s %-8s %s'
              % (r['theme'][:22], tok or '-', r.get('tokenLg') or '-',
                 '%s (%s)' % (r.get('file') or 'NO FILE', r.get('sheet')),
                 '%s / %s' % (r['html']['bg'], r['html']['radius']),
                 '%s / %s' % (r['body']['bg'], r['body']['radius']),
                 prad, 'ok' if ok else 'FAIL: ' + '; '.join(why)))

    print('')
    print('  corner stack at (1,1), first theme only (top-most first):')
    for layer in (rows[0]['corner'] if rows else []):
        print('    %s' % layer)

    print('')
    if rows:
        print('  scripts served: %s' % ', '.join(rows[0].get('scripts') or []))
        print('  globals: %s' % '  '.join(rows[0].get('globals') or []))

    print('')
    print('  %d theme(s), %d failing, %d whose own stylesheet did not load'
          % (len(rows), len(bad), len(no_sheet)))
    for t, why in bad:
        print('    FAIL %s -- %s' % (t, why))
    print('')
    print('NOT MEASURED: the compositor\'s own output. A screenshot in this rig renders')
    print('onto an opaque background, so the desktop showing through the corners is')
    print('still a NOT MEASURED half -- the mechanism above is what is proven here.')
    print('')
    print('VERDICT: %s' % ('PASS' if not bad else 'FAIL'))

    if not args.keep:
        shutil.rmtree(WORK, ignore_errors=True)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
