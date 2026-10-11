# THE min-width:0 PROBE -- does the LIVE panel overflow because .panel__header /
# .captions are grid items with the default min-width:auto?
#
# WHY IT EXISTS. _main/receipt-20261010-panel-overflow.md section 4 asserts the
# defect from the STYLESHEET ("In a flex/grid context the default min-width:auto
# refuses to shrink a child below its content, so a long unbreakable caption or a
# wide header can push past the panel's width") and section 5 records the fix as
# NOT done. That is an inference, not a measurement. This probe measures it.
#
# WHAT IT MEASURES, in ONE loaded page, so nothing but the CSS state differs:
#   arm live  -- the document as shipped, no inline style at all
#   arm auto  -- .panel__header / .captions forced min-width:auto (THE UNFIXED STATE)
#   arm zero  -- .panel__header / .captions forced min-width:0   (THE PROPOSED FIX)
# and, per injection point, the RESOLVED grid track of #panel (the one number
# that says the grid column grew past the panel content box), #panel
# scrollWidth-clientWidth, .panel__controls' right edge against that content
# box, and the off-DOM min-content/max-content floor of the two items.
#
# THE CONTROL IS THE INSTRUMENT ITSELF: arm auto and arm zero are the same page,
# the same fonts, the same injected nodes, milliseconds apart. If forcing auto
# does not move a single number, the stylesheet claim is refuted at this width.
#
# RUN: py -3 _main/_panel-minwidth-probe.py [--width 380] [--out I:/cc-tmp/minwidth.json]

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL_HTML = os.path.normpath(os.path.join(HERE, '..', 'app', 'panel', 'panel.html'))

# The probe, evaluated in the page. NO backticks and NO dollar-brace anywhere:
# run_code's payload is a JS template literal (see AGENTS notes).
JS = r"""
(() => {
  const r2 = (v) => Math.round(v * 100) / 100;
  const Q = (s) => document.querySelector(s);
  const out = { pts: [], marks: [], env: {}, selftest: {} };
  const PANEL = Q('#panel');
  const HEAD = Q('.panel__header');
  const CAPS = Q('.captions');
  if (!PANEL || !HEAD || !CAPS) {
    out.fatal = 'missing one of #panel / .panel__header / .captions';
    return out;
  }
  const cs = (el) => getComputedStyle(el);
  const px = (v) => { const n = parseFloat(v); return isNaN(n) ? 0 : n; };
  out.env = {
    viewport: [innerWidth, innerHeight],
    theme: document.documentElement.getAttribute('data-theme'),
    themeBody: document.body.getAttribute('data-theme'),
    skin: document.body.getAttribute('data-skin'),
    skinTheme: document.body.getAttribute('data-skin-theme'),
    surface: document.body.getAttribute('data-surface'),
    state: document.body.getAttribute('data-state'),
    themeBtn: !!Q('#theme-button'),
    captionList: !!Q('#caption-list'),
    captionListHidden: !!(Q('#caption-list') && Q('#caption-list').hidden),
    controlsKids: Q('.panel__controls') ? Q('.panel__controls').children.length : -1,
    fonts: document.fonts.status,
    hrefs: Array.prototype.map.call(document.styleSheets, (s) => s.href ? s.href.split('/').pop() : '(inline)')
  };
  const LONG = 'W'.repeat(160);
  const cbox = () => {
    const s = cs(PANEL);
    const pad = px(s.paddingLeft) + px(s.paddingRight);
    const bor = px(s.borderLeftWidth) + px(s.borderRightWidth);
    const r = PANEL.getBoundingClientRect();
    return { byClient: r2(PANEL.clientWidth - pad),
             byRect: r2(r.width - bor - pad),
             pad: r2(pad), border: r2(bor) };
  };
  const trackW = () => {
    const parts = cs(PANEL).gridTemplateColumns.split(' ').map(parseFloat).filter((v) => !isNaN(v));
    return parts.length ? r2(Math.max.apply(null, parts)) : null;
  };
  const mincMaxc = (sel) => {
    const el = Q(sel);
    if (!el) return { minc: null, maxc: null };
    const one = (mode) => {
      const wrap = document.createElement('div');
      wrap.style.cssText = 'position:fixed;left:-99999px;top:0;height:0;width:' + mode +
                           ';visibility:hidden;';
      const c = el.cloneNode(true);
      c.style.width = mode;
      c.style.position = 'static';
      c.style.maxWidth = 'none';
      wrap.appendChild(c);
      document.body.appendChild(wrap);
      const w = wrap.getBoundingClientRect().width;
      wrap.remove();
      return r2(w);
    };
    return { minc: one('min-content'), maxc: one('max-content') };
  };
  const snap = (tag) => {
    const cb = cbox();
    const pr = PANEL.getBoundingClientRect();
    const bR = px(cs(PANEL).borderRightWidth);
    const pR = px(cs(PANEL).paddingRight);
    const contentRight = pr.right - bR - pR;
    const kids = Array.prototype.slice.call(document.querySelectorAll('.panel__controls > *'));
    const rights = kids.map((k) => k.getBoundingClientRect().right);
    const hR = HEAD.getBoundingClientRect();
    const cR = CAPS.getBoundingClientRect();
    const clipped = rights.length ? Math.max.apply(null, rights) - contentRight : null;
    return {
      tag: tag,
      panelOver: PANEL.scrollWidth - PANEL.clientWidth,
      panelClient: PANEL.clientWidth,
      panelScroll: PANEL.scrollWidth,
      docOver: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      track: trackW(),
      contentW: cb.byClient,
      headerW: r2(hR.width),
      headerScrollOver: HEAD.scrollWidth - HEAD.clientWidth,
      capsW: r2(cR.width),
      capsScrollOver: CAPS.scrollWidth - CAPS.clientWidth,
      controlsRight: rights.length ? r2(Math.max.apply(null, rights)) : null,
      clippedBy: clipped === null ? null : r2(clipped),
      minW: { header: cs(HEAD).minWidth, caps: cs(CAPS).minWidth },
      scrollW: { header: HEAD.scrollWidth, caps: CAPS.scrollWidth }
    };
  };
  const setAll = (v) => { HEAD.style.minWidth = v; CAPS.style.minWidth = v; };
  const arm = (tag) => {
    if (tag === 'live') { setAll(''); }
    if (tag === 'auto') { setAll('auto'); }
    if (tag === 'zero') { setAll('0px'); }
    return snap(tag);
  };
  const CAP = Q('#caption-list');
  const CAP_HIDDEN = CAP ? CAP.hidden : null;
  const points = [
    { name: 'none', mk: () => [], rm: () => {} },
    { name: 'caption-text (overflow-wrap:anywhere)', mk: () => {
        if (!CAP) return null;
        CAP.hidden = false;
        const li = document.createElement('li');
        li.className = 'caption';
        const t = document.createElement('span');
        t.className = 'caption__time';
        t.textContent = '00:00';
        const b = document.createElement('span');
        b.className = 'caption__text';
        b.textContent = LONG;
        li.appendChild(t); li.appendChild(b);
        CAP.appendChild(li);
        return [li];
      }, rm: () => { if (CAP) { CAP.innerHTML = ''; CAP.hidden = CAP_HIDDEN; } } },
    { name: 'captions-hint (real element, no wrap declared)', mk: () => {
        const el = Q('#captions-hint');
        if (!el) return null;
        const old = el.textContent; el.textContent = LONG;
        return [() => { el.textContent = old; }];
      }, rm: (h) => { h.forEach((f) => f()); } },
    { name: 'stats-chip (real element, nowrap)', mk: () => {
        const el = Q('#stats-chip');
        if (!el) return null;
        const old = el.textContent; const wasHidden = el.hidden;
        el.hidden = false; el.textContent = LONG;
        return [() => { el.textContent = old; el.hidden = wasHidden; }];
      }, rm: (h) => { h.forEach((f) => f()); } },
    { name: 'wordmark__text (real element)', mk: () => {
        const el = Q('.wordmark__text');
        if (!el) return null;
        const old = el.textContent; el.textContent = LONG;
        return [() => { el.textContent = old; }];
      }, rm: (h) => { h.forEach((f) => f()); } },
    { name: 'controls + extra span (synthetic)', mk: () => {
        const el = Q('.panel__controls');
        if (!el) return null;
        const s = document.createElement('span');
        s.textContent = LONG;
        el.appendChild(s);
        return [s];
      }, rm: (h) => { h.forEach((n) => n.remove()); } },
    { name: 'captions__bar + extra span (synthetic)', mk: () => {
        const el = Q('.captions__bar');
        if (!el) return null;
        const s = document.createElement('span');
        s.textContent = LONG;
        el.appendChild(s);
        return [s];
      }, rm: (h) => { h.forEach((n) => n.remove()); } }
  ];
  for (const p of points) {
    const made = p.mk();
    if (made === null) { out.pts.push({ name: p.name, skipped: true }); continue; }
    const row = { name: p.name, live: arm('live'), auto: arm('auto'), zero: arm('zero') };
    p.rm(made);
    out.pts.push(row);
  }
  setAll('');
  const headKids = () => Array.prototype.map.call(HEAD.children, (el, i) => {
    const s = cs(el);
    const r = el.getBoundingClientRect();
    return { i: i, tag: el.tagName.toLowerCase(),
             cls: (el.className || '').toString().slice(0, 32),
             id: el.id || null,
             disp: s.display, minW: s.minWidth, flex: s.flex,
             w: r2(r.width), l: r2(r.left), r: r2(r.right),
             over: el.scrollWidth - el.clientWidth,
             sw: el.scrollWidth, cw: el.clientWidth,
             oflow: s.overflow,
             txt: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 20) };
  });
  const sweepOne = (tag) => {
    const s = snap(tag);
    const kids = headKids();
    const vis = kids.filter((k) => k.disp !== 'none').sort((a, b) => a.l - b.l);
    const ovl = [];
    for (let i = 1; i < vis.length; i++) {
      if (vis[i].l < vis[i - 1].r - 0.5) {
        ovl.push((vis[i - 1].cls || vis[i - 1].id) + '>' + (vis[i].cls || vis[i].id)
                 + '@' + r2(vis[i - 1].r - vis[i].l));
      }
    }
    const paint = [];
    for (let i = 0; i + 1 < vis.length; i++) {
      const k = vis[i];
      const pr = r2(k.l + k.sw);
      if (pr > vis[i + 1].l + 0.5) {
        paint.push((k.cls || k.id) + ' paintRight=' + pr + ' > next '
                   + (vis[i + 1].cls || vis[i + 1].id) + '.left=' + vis[i + 1].l
                   + ' by ' + r2(pr - vis[i + 1].l));
      }
    }
    const alphaOf = (c) => {
      if (!c) { return 0; }
      const m = /rgba?\(([^)]+)\)/.exec(c);
      if (!m) { return c === 'transparent' ? 0 : 1; }
      const p = m[1].split(',');
      return p.length > 3 ? parseFloat(p[3]) : 1;
    };
    const tagOf = (el) => {
      if (!el) { return 'none'; }
      const c = el.getAttribute ? (el.getAttribute('class') || '') : (el.className || '').toString();
      return el.tagName.toLowerCase() + (c ? '.' + c.slice(0, 24) : '');
    };
    const paintTop = [];
    if (paint.length) {
      const hy = (HEAD.getBoundingClientRect().top + HEAD.getBoundingClientRect().bottom) / 2;
      for (let i = 0; i + 1 < vis.length; i++) {
        const k = vis[i];
        const pr = r2(k.l + k.sw);
        if (pr > vis[i + 1].l + 0.5) {
          const x = r2((vis[i + 1].l + pr) / 2);
          const el = document.elementFromPoint(x, hy);
          const chain = [];
          let cover = 'none';
          let node = el;
          while (node && node !== HEAD && chain.length < 4) {
            const a = alphaOf(cs(node).backgroundColor);
            chain.push(tagOf(node) + '(a=' + r2(a) + ')');
            if (cover === 'none' && a >= 0.5) { cover = tagOf(node) + ' a=' + r2(a); }
            node = node.parentElement;
          }
          paintTop.push({ x: x, over: (k.cls || k.id) + ' text', under: tagOf(el),
                          underAlpha: el ? r2(alphaOf(cs(el).backgroundColor)) : null,
                          chain: chain.join(' < '), cover: cover,
                          controlsBg: cs(Q('.panel__controls')).backgroundColor,
                          firstCtl: (function () {
                            const c = Q('.panel__controls');
                            if (!c || !c.children.length) { return null; }
                            const f = c.children[0];
                            const fr = f.getBoundingClientRect();
                            return { tag: f.tagName.toLowerCase(), cls: tagOf(f),
                                     l: r2(fr.left), r: r2(fr.right),
                                     bg: cs(f).backgroundColor, a: r2(alphaOf(cs(f).backgroundColor)) };
                          })() });
        }
      }
    }
    return { tag: tag, track: s.track, panelOver: s.panelOver, clippedBy: s.clippedBy,
             headerW: s.headerW, capsW: s.capsW, contentW: s.contentW,
             minW: s.minW, kids: kids, ovl: ovl, paint: paint, paintTop: paintTop,
             kidsRight: vis.length ? vis[vis.length - 1].r : null };
  };
  const root = document.documentElement;
  const sv = { theme: root.getAttribute('data-theme'),
               skin: document.body.getAttribute('data-skin'),
               skinTheme: document.body.getAttribute('data-skin-theme') };
  const setAttr = (el, k, v) => { if (v === null) { el.removeAttribute(k); }
                                  else { el.setAttribute(k, v); } };
  out.sweep = [sweepOne('as-shipped')];
  const SWEEP_THEMES = [null, 'theme-1', 'theme-2', 'theme-3', 'theme-4', 'theme-5',
                        'cine-midnight-rain', 'cine-cafe'];
  for (const t of SWEEP_THEMES) {
    setAttr(root, 'data-theme', t);
    out.sweep.push(sweepOne('theme=' + t));
  }
  setAttr(root, 'data-theme', sv.theme);
  document.body.setAttribute('data-skin', '1');
  document.body.setAttribute('data-skin-theme', 'cine-cafe');
  out.sweep.push(sweepOne('skin=1 (skin-theme=cine-cafe)'));
  setAttr(document.body, 'data-skin', sv.skin);
  setAttr(document.body, 'data-skin-theme', sv.skinTheme);
  out.sweep.push(sweepOne('restored'));
  const armHdr = (tag, theme, both) => {
    setAttr(root, 'data-theme', theme);
    HEAD.style.minWidth = '0px';
    if (both) { CAPS.style.minWidth = '0px'; }
    const row = sweepOne(tag);
    HEAD.style.minWidth = '';
    CAPS.style.minWidth = '';
    setAttr(root, 'data-theme', sv.theme);
    return row;
  };
  out.sweep.push(armHdr('theme=theme-1 + hdr:0', 'theme-1', false));
  out.sweep.push(armHdr('theme=theme-1 + hdr:0 + caps:0', 'theme-1', true));
  out.sweep.push(armHdr('theme=theme-4 + hdr:0', 'theme-4', false));
  out.sweep.push(armHdr('theme=theme-2 + hdr:0', 'theme-2', false));
  out.sweep.push(armHdr('theme=theme-3 + hdr:0', 'theme-3', false));
  out.sweep.push(armHdr('theme=theme-5 + hdr:0', 'theme-5', false));
  out.sweep.push(armHdr('theme=null + hdr:0', null, false));
  const svState = document.body.getAttribute('data-state');
  setAttr(document.body, 'data-state', 'live');
  out.sweep.push(sweepOne('state=live (as-shipped)'));
  out.sweep.push(armHdr('state=live + hdr:0', sv.theme, false));
  setAttr(document.body, 'data-state', svState);
  out.sweep.push(sweepOne('restored2'));
  out.marks = [
    { sel: '.panel__header', floor: mincMaxc('.panel__header') },
    { sel: '.captions', floor: mincMaxc('.captions') },
    { sel: '.panel__controls', floor: mincMaxc('.panel__controls') },
    { sel: '.wordmark', floor: mincMaxc('.wordmark') },
    { sel: '.captions__hint', floor: mincMaxc('#captions-hint') }
  ];
  out.selftest = { cbox: cbox(), referrer: document.location.href,
                   captionRow: !!Q('.caption') };
  return out;
})()
"""


def win_geometry(display, width, height):
    left, top, right, bottom = display
    margin = 12
    return right - margin - width, top + margin, width, height


def primary_display():
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    if not user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
        raise RuntimeError('SystemParametersInfoW(SPI_GETWORKAREA) failed')
    return (rect.left, rect.top, rect.right, rect.bottom)


def measure(url, width, height, settle):
    import webview

    box = {'error': None, 'json': None, 'refused': [0]}
    done = threading.Event()

    def gate(form):
        original = form.Show

        def guarded_show():
            try:
                opacity = float(form.Opacity)
            except Exception:
                opacity = 1.0
            if opacity < 1.0:
                return original()
            box['refused'][0] += 1
            return None

        form.Show = guarded_show

    def on_loaded():
        time.sleep(settle)
        try:
            box['json'] = webview.windows[0].evaluate_js(JS)
        except Exception as exc:
            box['error'] = '%s: %s' % (type(exc).__name__, exc)
        finally:
            done.set()
        try:
            win.destroy()
        except Exception:
            pass

    x, y, w, h = win_geometry(primary_display(), width, height)
    FRAME_X, FRAME_Y = 16, 39
    win = webview.create_window(title='sotto-minwidth-probe', url=url, width=w + FRAME_X,
                                height=h + FRAME_Y, x=x, y=y, frameless=True,
                                transparent=True, on_top=True, resizable=False,
                                easy_drag=False, hidden=True, text_select=False,
                                background_color='#0b0f14')
    win.events.before_show += lambda: gate(win.native)
    win.events.loaded += on_loaded
    threading.Thread(target=lambda: (done.wait(90), _quit()), daemon=True).start()
    webview.start()
    if box['error']:
        raise RuntimeError(box['error'])
    if not box['json']:
        raise RuntimeError('no probe output (window=%dx%d)' % (w, h))
    return box['json'], box['refused'][0]


def _quit():
    try:
        import webview
        for w in list(webview.windows):
            w.destroy()
    except Exception:
        pass


def rowline(p):
    if p.get('skipped'):
        return '  %-46s SKIPPED (element absent)' % p['name']
    def cell(a):
        s = p[a]
        return 'track=%-8s over=%-4s hdr=%-4s caps=%-4s clip=%-7s minw=%s' % (
            s['track'], s['panelOver'], s['headerScrollOver'], s['capsScrollOver'],
            s['clippedBy'], s['minW']['header'])
    return ('  %-46s\n      live %s\n      auto %s\n      zero %s'
            % (p['name'], cell('live'), cell('auto'), cell('zero')))


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default=None)
    ap.add_argument('--width', type=int, default=380)
    ap.add_argument('--height', type=int, default=900)
    ap.add_argument('--settle', type=float, default=2.0)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    url = args.url or (PANEL_HTML.replace('\\', '/') and
                       'file:///' + PANEL_HTML.replace('\\', '/'))
    print('PROBE panel-minwidth')
    print('  url    : ' + url)
    print('  asked  : %dx%d' % (args.width, args.height))
    data, refused = measure(url, args.width, args.height, args.settle)
    print('  refused maps (hidden by the gate): %d' % refused)

    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=1, sort_keys=True)

    if data.get('fatal'):
        print('FATAL: ' + data['fatal'])
        print('VERDICT NO-CONFIDENCE -- ' + data['fatal'])
        return 2
    env = data['env']
    st = data['selftest']
    print('  viewport: %s  theme=%s (body=%s) skin=%s skin-theme=%s surface=%s state=%s'
          % (env['viewport'], env['theme'], env.get('themeBody'), env.get('skin'),
             env.get('skinTheme'), env['surface'], env['state']))
    print('  fonts=%s' % env['fonts'])
    print('  theme-button=%s caption-list=%s hidden=%s controls-kids=%s caption-row=%s'
          % (env['themeBtn'], env['captionList'], env['captionListHidden'],
             env['controlsKids'], st['captionRow']))
    print('  stylesheets: ' + ', '.join(env['hrefs']))
    cbox = st['cbox']
    print('  content box: byClient=%.2f byRect=%.2f (pad=%.2f border=%.2f)'
          % (cbox['byClient'], cbox['byRect'], cbox['pad'], cbox['border']))
    drift = abs(cbox['byClient'] - cbox['byRect'])
    if drift > 0.75:
        print('SELFTEST MISMATCH: two computations of the content box differ by %.2f px' % drift)
        print('VERDICT NO-CONFIDENCE -- content box not agreed')
        return 2
    if not env['viewport'][0]:
        print('VERDICT NO-CONFIDENCE -- zero-width viewport')
        return 2

    print('')
    print('THE PER-POINT TABLE  (traces: live = shipped CSS, auto = min-width:auto forced,'
          ' zero = min-width:0 forced)')
    print('  track   = resolved #panel grid column width, in px')
    print('  over    = #panel scrollWidth - clientWidth (structural overflow)')
    print('  hdr/caps= scrollWidth - clientWidth of that item')
    print('  clip    = max right edge of .panel__controls minus the panel content-box right edge')
    print('  minw    = the item computed min-width in that arm')
    for p in data['pts']:
        print(rowline(p))

    content = cbox['byClient']
    print('')
    print('THE FLOORS (off-DOM clone, viewport independent, live arm)')
    floors = {}
    for m in data['marks']:
        floors[m['sel']] = m['floor']
        print('  %-20s min-content=%-10s max-content=%s'
              % (m['sel'], m['floor']['minc'], m['floor']['maxc']))
    hmin = (floors.get('.panel__header') or {}).get('minc')
    cmin = (floors.get('.captions') or {}).get('minc')
    print('  panel content box = %.2f px' % content)

    sweep = data.get('sweep') or []
    if sweep:
        print('')
        print('THE VARIANT SWEEP (shipped arm, no injection: does the REAL state overflow?)')
        print('  %-34s %-9s %-6s %-9s %-9s %-9s %-6s %s'
              % ('variant', 'track', 'over', 'clip', 'kidsRight', 'headerW', 'minw',
                 'sibling overlaps'))
        for s in sweep:
            print('  %-34s %-9s %-6s %-9s %-9s %-9s %-6s %s'
                  % (s['tag'], s['track'], s['panelOver'], s['clippedBy'],
                     s.get('kidsRight'), s['headerW'], s['minW']['header'],
                     ('; '.join(s.get('ovl') or [])[:60] or 'none')))
        print('  kidsRight = right edge (viewport px) of the last visible .panel__header child;'
              ' viewport is %s wide' % env['viewport'][0])
        for s in sweep:
            vis = [k for k in s['kids'] if k['disp'] != 'none']
            print('  [%s] %d/%d header kids visible: %s'
                  % (s['tag'], len(vis), len(s['kids']),
                     ' | '.join('%s.%s w=%s over=%s minw=%s'
                                % (k['tag'], k['cls'] or (k['id'] or '-'), k['w'],
                                   k['over'], k['minW'])
                                for k in vis)))
            for pc in (s.get('paint') or []):
                print('      paint-extent crossing: %s' % pc)
            for pt in (s.get('paintTop') or []):
                fc = pt.get('firstCtl') or {}
                print('        x=%s topmost=%s a=%s | chain %s | OPAQUE COVER: %s'
                      % (pt['x'], pt['under'], pt['underAlpha'], pt['chain'], pt['cover']))
                print('          .panel__controls bg=%s | first control %s %s-%s bg=%s a=%s'
                      % (pt['controlsBg'], fc.get('tag'), fc.get('l'), fc.get('r'),
                         fc.get('bg'), fc.get('a')))
            if not (s.get('paint') or []):
                print('      paint-extent crossing: none')

    base = next((p for p in data['pts'] if p['name'] == 'none'), None)
    no_regress = None
    if base:
        b_live, b_zero = base['live'], base['zero']
        keys = ['panelOver', 'track', 'headerW', 'capsW', 'controlsRight', 'clippedBy',
                'headerScrollOver', 'capsScrollOver', 'docOver']
        diffs = [k for k in keys if b_live[k] != b_zero[k]]
        no_regress = (not diffs, diffs)
        print('')
        print('THE NO-REGRESSION PROOF (shipped document, no injection: live vs zero arm)')
        print('  live  track=%s over=%s headerW=%s capsW=%s controlsRight=%s clip=%s'
              % (b_live['track'], b_live['panelOver'], b_live['headerW'], b_live['capsW'],
                 b_live['controlsRight'], b_live['clippedBy']))
        print('  zero  track=%s over=%s headerW=%s capsW=%s controlsRight=%s clip=%s'
              % (b_zero['track'], b_zero['panelOver'], b_zero['headerW'], b_zero['capsW'],
                 b_zero['controlsRight'], b_zero['clippedBy']))
        print('  fields moved by the fix: ' + (', '.join(diffs) if diffs else 'NONE'))

    overflowing = []
    for p in data['pts']:
        if p.get('skipped'):
            continue
        a, z = p['auto'], p['zero']
        if a['panelOver'] > 0 or a['headerScrollOver'] > 0 or a['capsScrollOver'] > 0:
            overflowing.append({'name': p['name'], 'auto_over': a['panelOver'],
                                'auto_track': a['track'], 'zero_over': z['panelOver'],
                                'zero_track': z['track'], 'auto_clip': a['clippedBy'],
                                'zero_clip': z['clippedBy']})
    shipped_over = None
    if base:
        shipped_over = base['live']['panelOver']
        print('')
        print('THE SHIPPED DOCUMENT, bare: #panel scrollWidth-clientWidth = %s px,'
              ' doc overflow = %s px' % (base['live']['panelOver'], base['live']['docOver']))

    print('')
    print('THE ANSWER')
    for o in overflowing:
        print('  %s: auto arm overflows by %s px (track %s px) -> zero arm %s px (track %s px),'
              ' controls clipped by auto=%s zero=%s'
              % (o['name'], o['auto_over'], o['auto_track'], o['zero_over'], o['zero_track'],
                 o['auto_clip'], o['zero_clip']))
    header_free = (hmin is not None and hmin <= content)
    caps_free = (cmin is not None and cmin <= content)
    print('  header min-content %s <= content %.2f : %s' % (hmin, content, header_free))
    print('  captions min-content %s <= content %.2f : %s' % (cmin, content, caps_free))
    if not overflowing:
        print('VERDICT NO-OVERFLOW-POSSIBLE-AT-SHIPPED-WIDTH')
        print('  the min-content floor of both grid items is already under the content box, so')
        print('  no content can widen the track: the fix is DEFENSIVE, and the receipt section 4')
        print('  claim is NOT reproduced at this width.')
    else:
        real = [o for o in overflowing if o['zero_over'] == 0]
        print('VERDICT OVERFLOW-REPRODUCED (%d point(s)); cured by min-width:0 at %d of them'
              % (len(overflowing), len(real)))
        print('  reachability is a separate claim: see the per-point names -- the caption case is')
        print('  shielded by .caption__text overflow-wrap:anywhere, so a long caption WORD cannot')
        print('  reach it; the real-element points are where a long runtime string could.')
    if no_regress is not None:
        print('FIX-CHANGES-SHIPPED-GEOMETRY: ' + ('NO' if no_regress[0] else 'YES ' + str(no_regress[1])))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        import traceback
        try:
            sys.stdout.write('FATAL\n' + traceback.format_exc())
            sys.stdout.write('VERDICT NO-CONFIDENCE -- instrument raised\n')
        except Exception:
            pass
        raise SystemExit(2)
