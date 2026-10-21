# THE TRUE-WIDTH DOM PROBE -- the 380 px arm that headless --dump-dom cannot reach.
#
# WHY IT EXISTS. Every headless arm on this box renders innerWidth >= 492
# (measured: _floor-arms.py, three modes; dsf 1/1.25/1.3/1.5/2 all print 492),
# so the shipped 380 px panel was never measured by a DOM instrument. The panel's
# own children were measured 416 wide at 380 (shell --dump-dom, DOMDUMP), which
# no instrument here can reproduce, because no instrument here renders 380.
#
# The shell (app/webview/sotto_webview.py) IS such an instrument: create_window
# with frameless=True width=380 gives client == window, DOMDUMP measured
# viewport [380,900], and run_dump_dom (:4839) executes its probe with
# exec_js (:3631) -> CoreWebView2.ExecuteScriptAsync on a window it never
# SHOWS. Both facts are copied here verbatim: the same flagship engine, the same
# hidden-window trick, the same ExecuteScriptAsync eval.
#
# CSP: panel.html:24 is `script-src 'self'`, so an INLINE <script> the fixture
# injects is refused (measured, _mincontent.py 2026-10-09: an inline runner's sink
# serialised EMPTY). ExecuteScriptAsync is NOT blocked by that CSP -- the shell's
# own DOMDUMP proves it -- so this probe evaluates one IIFE per run.
#
# RUN:  pyw -3 _main/_design-lane/_wvprobe.py [--width 380] [--theme theme-3]
#       [--surface panel] [--settle 1.5] [--out I:/cc-tmp/wv.json]

import argparse
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rects  # noqa: E402

# The probe, evaluated in the page. It measures what the DOMDUMP could not: the
# grid TRAcKS of #panel (the one number that names a 416 px track), the scroll sink
# of each element (a 416 px child inside a 380 px panel has to be clipped by a
# scroll container or by overflow:hidden -- scrollWidth vs clientWidth says which),
# and the min-content floor of every element in the chain (viewport independent,
# so every arm can be compared).
JS = r"""
(() => {
  const Q = (s) => document.querySelector(s);
  const box = (el) => { const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y),
             w: Math.round(r.width), h: Math.round(r.height) }; };
  const num = (v) => Math.round(parseFloat(v) * 100) / 100;
  // Off-DOM sizer: the wrapper is sized to min-content, so its used width is the
  // clone's minimum width. Fixed + offscreen keeps it out of both the layout and
  // the viewport.
  const minc = (el) => {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:fixed;left:-99999px;top:0;height:0;' +
                         'width:min-content;visibility:hidden;';
    const c = el.cloneNode(true);
    c.style.width = 'min-content';
    c.style.position = 'static';
    c.style.maxWidth = 'none';
    wrap.appendChild(c);
    document.body.appendChild(wrap);
    const w = wrap.getBoundingClientRect().width;
    wrap.remove();
    return num(w);
  };
  const maxc = (el) => {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:fixed;left:-99999px;top:0;height:0;' +
                         'width:max-content;visibility:hidden;';
    const c = el.cloneNode(true);
    c.style.width = 'max-content';
    c.style.position = 'static';
    c.style.maxWidth = 'none';
    wrap.appendChild(c);
    document.body.appendChild(wrap);
    const w = wrap.getBoundingClientRect().width;
    wrap.remove();
    return num(w);
  };
  const SELS = ['html', 'body', '#panel', '.panel__header', '.panel__controls',
                '.wordmark', '.captions', '.captions__body', '.captions__list',
                '.caption', '.caption__text', '.caption__time', '#placeholder',
                '.history', '.history__label', '.status', '.status__text',
                '.chrome', '.stripbar', '#caption-list'];
  const out = { viewport: [window.innerWidth, window.innerHeight],
                zoom: window.devicePixelRatio || 1,
                bodyScroll: [document.body.scrollWidth, document.body.scrollHeight],
                docScroll: [document.documentElement.scrollWidth,
                            document.documentElement.scrollHeight],
                url: location.href, els: {}, minc: {} };
  for (const s of SELS) {
    const el = Q(s);
    if (!el) { out.els[s] = null; continue; }
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    out.els[s] = { rect: box(el),
                   display: cs.display, position: cs.position,
                   overflow: cs.overflow,
                   scrollW: el.scrollWidth, clientW: el.clientWidth,
                   minW: cs.minWidth, w: cs.width, box: cs.boxSizing,
                   pad: cs.padding, mar: cs.margin };
    out.minc[s] = minc(el);
  }
  // THE TRACK. A grid item that is wider than the panel's content box is wider
  // because of its track, and gridTemplateColumns names the track VERBATIM
  // (used value: '1fr' stays '416px').
  for (const s of ['#panel', '.captions', '.captions__list']) {
    const el = Q(s);
    if (!el) continue;
    const cs = getComputedStyle(el);
    out['grid' + s] = { display: cs.display,
                        cols: cs.gridTemplateColumns,
                        rows: cs.gridTemplateRows,
                        gtc: cs.gridTemplateColumnSizes || null,
                        gap: cs.gap, minW: cs.minWidth,
                        alignContent: cs.alignContent,
                        justifyContent: cs.justifyContent };
  }
  // WHO WIDENS THE HEADER. The panel is one implicit `auto` column, so the
  // track's floor is the LARGEST min-content contribution of its items; the
  // header's `.panel__controls` is `flex: none`, and an inflexible flex item
  // contributes its MAX-content. This block names the child that does it.
  out.ctorls = [];
  document.querySelectorAll('.panel__controls > *').forEach(el => {
    const cs = getComputedStyle(el);
    out.ctorls.push({ name: el.tagName.toLowerCase() +
                                (el.id ? '#' + el.id : '') +
                                (typeof el.className === 'string' && el.className.trim()
                                   ? '.' + el.className.trim().replace(/\s+/g, '.') : ''),
                      text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 20),
                      rect: box(el), minc: minc(el), maxc: maxc(el),
                      flex: cs.flex, minw: cs.minWidth, w: cs.width,
                      vis: cs.visibility, disp: cs.display });
  });
  // THE FLOOR, SIDE BY SIDE: the header's min-content, the panel's min-content,
  // the controls' min/max, and the panel's CONTENT BOX (the width the design says
  // every item must fit inside).
  // WHICH FONT STATE THIS IS. The 416 px the shell measured at 380 and the
    // 403 it measures once the webfonts have loaded differ by 13.125 px -- a font
    // RACE, not a different page. document.fonts.status is the only field that
    // tells the two arms apart, so every floor report carries it.
    let fstate = 'unavailable';
    try {
      fstate = document.fonts.status;
      if (fstate !== 'loaded') {
        out.fontsPending = Array.from(document.fonts).filter(f => f.status !== 'loaded')
                                        .map(f => f.family + ' ' + f.weight + ' ' + f.status);
      }
    } catch (e) { fstate = 'threw: ' + e.message; }
    out.fonts = fstate;
    out.fontsReadyAt = null;
    // WHICH FACE PAINTED, AND WHEN IT LANDED. The header's three text elements
    // use THREE DIFFERENT faces of the same family: .wordmark__name is
    // font-weight 700 (theme-1.css:141 reads var(--weight-brand) = 700, :93),
    // #theme-button's label inherits the UA default 400, and
    // .chrome--tele[data-chrome=head] is 600 (theme-1.css:600). This box has
    // only the 200/700/800/900 Barlow Condensed faces INSTALLED FOR THE USER
    // (HKCU registry, 8 entries), so 700 can paint from the system Bold while
    // 400 and 600 still wait on the woff2. document.fonts.check() names which
    // weights are usable at this instant and the resource entries name the
    // instant each woff2 landed -- the two together are the swap window.
    try {
      out.faceCheck = {};
      [200, 400, 500, 600, 700, 800, 900].forEach(w => {
        out.faceCheck[w] = document.fonts.check(w + ' 15px "Barlow Condensed"'); });
      var _resAll = performance.getEntriesByType('resource');
      out.resCount = _resAll.length;
      out.resAll = _resAll.slice(0, 16).map(function (r) {
        return r.name.split('/').pop() + '|' + r.initiatorType + '@' + Math.round(r.responseEnd)
          + 'ms(load=' + Math.round(r.duration) + ')'; });
      out.res = _resAll
        .filter(r => /barlow-condensed[^/]*\.woff2$/.test(r.name))
        .map(r => r.name.split('/').pop().replace('barlow-condensed-latin-', 'w') + '@' + Math.round(r.responseEnd) + 'ms');
      out.fontFaces = Array.from(document.fonts)
        .filter(f => /Barlow/i.test(f.family))
        .map(f => f.family + '/' + f.weight + '/' + f.style + '=' + f.status);
    } catch (e) { out.faceErr = e.message; }
  out.floor = { header_minc: minc(Q('.panel__header')),
                panels_minc: minc(Q('#panel')),
                controls_minc: minc(Q('.panel__controls')),
                controls_maxc: maxc(Q('.panel__controls')),
                wordmark_minc: minc(Q('.wordmark')),
                panel_rect: box(Q('#panel')),
                panel_content_box: null };
  { const pr = Q('#panel'), cs = getComputedStyle(pr);
    out.floor.panel_content_box = num(pr.clientWidth
        - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)); }
  // THE PAINT: which element actually paints the 416 px colour band, if any.
  const probe = Q('#panel');
  if (probe) {
    const kids = probe.children;
    out.kids = [];
    for (const k of kids) {
      out.kids.push({ name: k.tagName.toLowerCase() + (k.id ? '#' + k.id : '') +
                       (k.className && typeof k.className === 'string'
                          ? '.' + k.className.trim() : ''),
                      rect: box(k), minc: minc(k) });
    }
  }
  // THE TIMELINE, when the page carries one. `_watch.js` is an EXTERNAL sibling
  // this arm may inject into a COPY of panel.html (inline is refused by the page
  // CSP), recording the widths of every header descendant at a 25 ms cadence from
  // document start. It answers the one question a single sample cannot: is the
  // value a property of the page or of the MOMENT it was read.
  if (window.__watch) { out.watch = window.__watch.slice(0, 600);
                         out.watch_done = !!window.__watch_done; }
  return out;
})()
"""


def win_geometry(display, width, height):
    # The shell's own dock_right (sotto_webview.py:494): the form is created at its
    # FINAL geometry, right-aligned in the work area with a 12 px margin. Copied so
    # this probe's arithmetic is the shipped one.
    left, top, right, bottom = display
    margin = 12
    x = right - margin - width
    y = top + margin
    return x, y, width, height


def primary_display():
    # rects.py does not know the screen; the probe needs it for the dock. A
    # failure here must be LOUD, not a silent fallback: the geometry of the window
    # is the measurement, so a 0x0 screen would silently measure nothing.
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    if not user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
        raise RuntimeError('SystemParametersInfoW(SPI_GETWORKAREA) failed')
    return (rect.left, rect.top, rect.right, rect.bottom)


def measure(url, width, height, settle):
    import webview  # imported late: it loads the WinForms assemblies

    box = {'error': None, 'json': None, 'refused': [0]}
    done = threading.Event()

    # THE SHADOW GATE, copied from the shell's _gate_form_show (:3145-3199).
    # pywebview maps a TRANSPARENT window itself on every navigation start
    # (`platforms/edgechromium.py:348 self.form.Show()`), and that hack is
    # load-bearing -- without transparency the page never loads. A measurement
    # run must not put a window on the owner's desk, so the map is refused the
    # same way the shipped shell refuses it: an INSTANCE attribute shadows the
    # CLR method for a python-side call (measured, _pythonnet-show-shadow-test.py).
    def gate(form):
        original = form.Show

        def guarded_show():
            try:
                opacity = float(form.Opacity)
            except Exception:  # noqa: BLE001
                opacity = 1.0
            if opacity < 1.0:
                # pywebview's own creation dance is invisible by construction.
                return original()
            box['refused'][0] += 1
            return None

        form.Show = guarded_show

    def on_loaded():
        # The fixture's own runner settles at 300 ms (rects' _rects.js), so a short
        # settle here is enough for BOTH this probe's numbers and the fixture's.
        time.sleep(settle)
        try:
            box['json'] = webview.windows[0].evaluate_js(JS)
        except Exception as exc:  # noqa: BLE001
            box['error'] = '%s: %s' % (type(exc).__name__, exc)
        finally:
            done.set()
        # The GUI loop only ends when the window it owns is gone, and a MEASUREMENT
        # run must not sit on the owner's desk waiting for one.
        try:
            win.destroy()
        except Exception:  # noqa: BLE001
            pass

    x, y, w, h = win_geometry(primary_display(), width, height)
    # THE FRAME IS MEASURED, NOT ASSUMED. `frameless=True` does NOT reach a
    # borderless form on this box: the form keeps a 16x39 non-client frame, so a
    # request of width 380 renders innerWidth 364 (measured). A probe that reports
    # 364 while its caller asked for 380 is measuring the FRAME, not the panel -- so
    # the two measured deltas are ADDED BACK here and the window is created one
    # frame larger, making the CONTENT area the size the caller asked for.
    # `measure()` then compares what it actually rendered against what was asked
    # and says so in the header, so no run can pass a 364 arm off as 380.
    FRAME_X, FRAME_Y = 16, 39   # measured 2026-10-09: 396 -> innerWidth 380
    # THE SHIPPED KWARGS. The shell's create_window (:2860-2896) is the ONLY
    # configuration here that yields client == window on this box: a window created
    # WITHOUT transparent=True keeps a 16x39 non-client frame (measured:
    # width=380 renders innerWidth=364, innerHeight=861), and the shell measures
    # 380. So the same flags are used, and the Show() gate above keeps it hidden.
    win = webview.create_window(title='sotto-design-probe', url=url, width=w + FRAME_X,
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
    return box['json']


def _quit():
    try:
        import webview
        for w in list(webview.windows):
            w.destroy()
    except Exception:  # noqa: BLE001
        pass


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--theme', default='theme-3')
    ap.add_argument('--surface', default='panel', choices=('panel', 'strip'))
    ap.add_argument('--url', default=None,
                    help='render THIS url instead of the fixture, so the LIVE '
                         'app/panel/panel.html state is measured verbatim')
    ap.add_argument('--width', type=int, default=380)
    ap.add_argument('--height', type=int, default=900)
    ap.add_argument('--settle', type=float, default=1.5)
    ap.add_argument('--work', default=None)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    work = args.work or os.path.join(os.environ.get('TMPDIR', 'I:/cc-tmp'),
                                     'wvprobe')
    if os.path.isdir(work):
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)

    # Same fixture builder as rects.py: the SHIPPED stylesheet order and the
    # data-theme/data-surface rewrites, only the measuring script differs. So this
    # arm's numbers are comparable with every rects.py number already on record.
    # --url measures the LIVE document, byte for byte, including its own
    # EXTERNAL scripts (panel.js is a sibling file, so the panel CSP allows it).
    # The fixture path rewrites data-theme / data-surface and injects _rects.js,
    # and BOTH of those change the page -- this arm changes nothing.
    if args.url:
        html = args.url
    else:
        html = rects.build(args.theme, args.surface, work)
    url = 'file:///' + html.replace(os.sep, '/')

    data = measure(url, args.width, args.height, args.settle)
    if isinstance(data, str):
        data = json.loads(data)

    vw, vh = data.get('viewport', [None, None])
    print('window=%dx%d  viewport=%s  zoom=%s  url=%s'
          % (args.width, args.height, data.get('viewport'),
             data.get('zoom'), data.get('url')))
    # THE PROBE ASSERTS ITS OWN INPUT. A run whose RENDERED viewport is not the
    # requested one is a different arm: it is measuring the frame, not the panel.
    # The window was created one frame larger for exactly this reason, so a
    # mismatch here means the calibration moved and every number below describes
    # a different subject than the one the command line asked for.
    if [vw, vh] != [args.width, args.height]:
        print('FRAME-MISMATCH  requested=%dx%d  rendered=%dx%d  <- every number '
              'below is the FRAME, not the panel'
              % (args.width, args.height, vw, vh))
    else:
        print('FRAME-OK  requested=%dx%d  rendered=%dx%d  (the measured 16x39 '
              'non-client frame was compensated)' % (args.width, args.height, vw, vh))
    print('bodyScroll=%s  docScroll=%s' % (data.get('bodyScroll'),
                                            data.get('docScroll')))
    panel = data.get('els', {}).get('#panel')
    if panel:
        print('#panel rect=%s scrollW=%d clientW=%d minW=%s'
              % (panel['rect'], panel['scrollW'], panel['clientW'],
                 panel['minW']))
    print('')
    print('%-22s %-26s %8s %8s %6s %-8s %s'
          % ('element', 'rect', 'minc', 'scrollW', 'clientW', 'overflow', 'minW'))
    for s, e in data.get('els', {}).items():
        if not e:
            print('%-22s %s' % (s, 'ABSENT'))
            continue;
        print('%-22s %-26s %8s %8s %6d %-8s %s'
              % (s, '[%s,%s,%s,%s]' % (e['rect']['x'], e['rect']['y'],
                                        e['rect']['w'], e['rect']['h']),
                 data.get('minc', {}).get(s), e['scrollW'], e['clientW'],
                 e['overflow'], e['minW']))
    print('')
    for k in sorted(data):
        if k.startswith('grid'):
            print('%s %s' % (k, json.dumps(data[k], sort_keys=True)))
    if args.out:
        with open(args.out, 'w', encoding='utf-8', newline='\r\n') as fh:
            fh.write(json.dumps(data, ensure_ascii=False, indent=1) + '\r\n')
    print('')
    fl = data.get('floor', {})
    if fl:
        pr = fl.get('panel_rect', {})
        print('')
        print('THE FLOOR: header minc=%.2f  |  panel minc=%.2f  |  controls '
              'minc=%.2f maxc=%.2f  |  wordmark minc=%.2f'
              % (fl.get('header_minc'), fl.get('panels_minc'),
                 fl.get('controls_minc'), fl.get('controls_maxc'),
                 fl.get('wordmark_minc')))
        fc = data.get("faceCheck") or {}
        if fc:
            print("FACES USABLE NOW (document.fonts.check): "
                  + "  ".join("%s=%s" % (w, "YES" if v else "no") for w, v in sorted(fc.items())))
        print("RESOURCE TIMING: " + str(data.get("resCount")) + " entries reported (file:// subresources)");
        for _r in (data.get("resAll") or []):
            print("   " + _r);
        rs = data.get("res") or []
        if rs:
            print("BARLOW WOFF2 LANDED AT: " + ", ".join(rs))
        ff = data.get("fontFaces") or []
        if ff:
            print("document.fonts Barlow faces: " + " | ".join(ff))
        print('PANEL CONTENT BOX = %.2f   (window %d minus the 2x1px border and '
              'the 2x14px padding = the width every panel child must fit inside)'
              % (fl.get('panel_content_box'), pr.get('w', 0)))
        print('PANEL__CONTROLS children -- the named source of that floor:')
        for c in data.get('ctorls', []):
            r = c.get('rect', {})
            print('  %-42s rect=[%.0f,%.0f,%.0fx%.0f] minc=%7.2f maxc=%7.2f '
                  'flex=%-8s minw=%-6s %s'
                  % ((c.get('name') + ' "' + c.get('text', '') + '"')[:42],
                     r.get('x', 0), r.get('y', 0), r.get('w', 0), r.get('h', 0),
                     c.get('minc'), c.get('maxc'), c.get('flex'), c.get('minw'),
                     c.get('vis')))
    wl = data.get('watch') or []
    if wl:
        print('')
        print('THE TIMELINE (25 ms cadence from document start, %d samples,%s)'
              % (len(wl), ' complete' if data.get('watch_done') else ' TRUNCATED'))
        print('  only the rows where .panel__header WIDTH CHANGED are printed;')
        print('the font column is document.fonts.status at that instant.')
        def _chg(k):
            prev = None
            rows = []
            for s in wl:
                if s.get(k) != prev:
                    rows.append(s)
                    prev = s.get(k)
            return rows
        seen = set()
        for s in wl:
            if s.get('.panel__header') is not None:
                seen.add(s['.panel__header'])
        if len(seen) > 1:
            print('  !! DISTINCT header widths in ONE page load: %s'
                  % ', '.join('%.3f' % v for v in sorted(seen)))
        for s in _chg('.panel__header'):
            print('  t=%5dms fonts=%-9s theme=%-8s state=%-8s header=%s'
                  ' wordmark=%s chrome=%s on=%s off=%s controls=%s themebtn=%s'
                  % (s['t'], s.get('f'), s.get('theme'), s.get('state'),
                     s.get('.panel__header'), s.get('.wordmark'), s.get('.chrome'),
                     s.get('.chrome__on'), s.get('.chrome__off'),
                     s.get('.panel__controls'), s.get('#theme-button')))
        print('  FIRST row : ' + json.dumps(wl[0], sort_keys=True))
        print('  LAST  row : ' + json.dumps(wl[-1], sort_keys=True))
    else:
        print('')
        print('THE TIMELINE: no window.__watch in this page (no _watch.js sibling).')
    print('')
    print('THE QUESTION: is .captions wider than #panel\'s content box?')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())