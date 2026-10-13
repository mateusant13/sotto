"""Does the panel still PAINT? A pixel check, taken OFF the owner's desk.

WHY THIS EXISTS. The 2026-10-07 cure (`_gate_form_show`) refuses pywebview's
own `form.Show()` at full opacity, so the window is never MAPPED at startup.
Every cheaper check (RECEIVER_READY, PRELOAD_ACTIVE, `--dump-dom`, the panel
state writer) proves the page RUNS — none of them proves a single pixel is
composited. pywebview's own comment calls the Show-on-navigating "a hack to make
transparent window work / no idea why this works", so "the app still logs
RECEIVER_READY" is NOT evidence that the panel is not blank. This probes the
pixels through `PrintWindow(PW_RENDERFULLCONTENT)`, which renders the window's
own content into a bitmap whatever its position — so the copy can sit at
x=-10000 and nothing appears on the owner's screen.

ARMS (each a COPY of the live shell, x moved off the desk; both deleted at end):
  asked     the live shell + `--show`: the owner's own ask. Its window MUST be
            found AND its bitmap MUST be non-uniform, or the fix blanked the
            panel. This is the arm that can FAIL the cure.
  notasked  the live shell, nobody asked. The window must NOT be found among
            the mapped windows (negative control for this instrument: if this
            arm also reports PAINTED, the capture is not measuring an ask).

Usage: py -3 _main/panel-paint-probe.py [--secs 7]
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
VARIANT_DIR = os.path.dirname(SHELL)
LOG = os.path.join(HERE, 'panel-paint-probe.log')

CREATE_NO_WINDOW = 0x08000000
PW_RENDERFULLCONTENT = 0x00000002

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
MONITOR_DEFAULTTONULL = 0x00000000

_lines: list[str] = []


def log(msg: str) -> None:
    _lines.append(msg)
    with open(LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(_lines) + '\n')
    print(msg, flush=True)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long),
                ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def window_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    return buf.value


def window_text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, 512)
    return buf.value


def find_panel_window(pid: int):
    """The shell's own top-level 'Sotto' form, IF it is mapped."""
    hits = []

    def cb(hwnd, _lp):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        if window_text(hwnd) != 'Sotto':
            return True
        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        hits.append({
            'hwnd': int(hwnd), 'class': window_class(hwnd),
            'on_monitor': bool(user32.MonitorFromWindow(
                wintypes.HWND(hwnd), MONITOR_DEFAULTTONULL)),
            'rect': (r.left, r.top, r.right, r.bottom),
        })
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return hits


def _write_png(path, w: int, h: int, px: bytes) -> int:
    """BGRA bytes (top-down) to a PNG. Stdlib only: zlib + struct."""
    import struct
    import zlib
    raw = bytearray()
    for y in range(h):
        raw.append(0)                      # filter type 0 for every row
        row = px[y * w * 4:(y + 1) * w * 4]
        for x in range(w):
            i = x * 4
            raw += bytes((row[i + 2], row[i + 1], row[i], row[i + 3]))  # BGRA
    # THE ALPHA IS THE WHOLE POINT of carrying it: `form.BackColor =
    # Color.Transparent` either makes the unpainted pixels see-through or it does
    # not, and a sha256 cannot tell you which. Reported here so the claim
    # "the overlay is invisible" is a number and not an impression.
    alphas = {}
    for i in range(3, len(px), 4):
        alphas[px[i]] = alphas.get(px[i], 0) + 1
    top = sorted(alphas.items(), key=lambda kv: -kv[1])[:5]
    print('ALPHA %s' % ' '.join('%d:%d' % (a, n) for a, n in top), flush=True)

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))

    body = (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 6))
            + chunk(b'IEND', b''))
    with open(path, 'wb') as fh:
        fh.write(body)
    return len(body)


def capture(hwnd, w: int, h: int) -> dict:
    """PrintWindow into a DIB and summarise the pixels (distinct colours)."""
    hdc = user32.GetWindowDC(wintypes.HWND(hwnd))
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(wintypes.HWND(hwnd), mem, PW_RENDERFULLCONTENT)
    info = BITMAPINFOHEADER()
    info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.biWidth = w
    info.biHeight = -h               # top-down
    info.biPlanes = 1
    info.biBitCount = 32
    info.biCompression = 0           # BI_RGB
    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0)
    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(wintypes.HWND(hwnd), hdc)
    px = buf.raw[:w * h * 4]
    # OPTIONAL PNG, added 2026-10-12 by the Lead. The probe reported a sha256 and
    # a colour count, which proves THAT something painted but never WHAT -- and
    # the owner's complaints are all about what he sees. With SOTTO_PAINT_PNG set
    # the same pixels are written out so a human (or an agent reading the image)
    # can look at the surface instead of trusting a hash.
    dest = os.environ.get('SOTTO_PAINT_PNG')
    if dest:
        try:
            n = _write_png(dest, w, h, px)
            print('PNG %s %dx%d %d B' % (dest, w, h, n), flush=True)
        except Exception as exc:  # noqa: BLE001
            print('PNG_FAILED %r' % (exc,), flush=True)
    colours = set()
    for i in range(0, len(px) - 3, 4):
        colours.add(px[i:i + 3])
        if len(colours) > 64:
            break
    return {'printwindow_ok': bool(ok), 'getdibits_rows': got,
            'distinct_colours': len(colours),
            'px_sha256': hashlib.sha256(px).hexdigest()[:16],
            'bytes': len(px)}


GATE_REMOVED = (
    ('        self._gate_form_show(form)\n',
     '        pass  # paint-probe control: the 2026-10-07 gate removed\n'),
)


#: THE PRELOAD PROBE (2026-10-13). Fired from the PRELOAD's own context -- it is
#: appended to `_bootstrap_js`'s return value, i.e. the same script that carries
#: `BOOTSTRAP_JS` and `lazy-assets.js` -- and it fires the SAME two channels
#: `ask()` can use: `window.sotto.dispatch(...)` (what lazy-assets.js calls)
#: and a RAW `window.chrome.webview.postMessage` in the shell's own 3-slot wire
#: format. The state is encoded IN THE KIND, because the shell logs
#: `BRIDGE_UNKNOWN_KIND kind=...`: c=chrome.webview present,
#: p=pywebview._returnValuesCallbacks present, s=window.sotto.dispatch present,
#: a=pywebview.api present.
PRELOAD_PROBE_JS = r"""
(function () {
  'use strict';
  function st() {
    var c = !!(window.chrome && window.chrome.webview && window.chrome.webview.postMessage);
    var p = !!(window.pywebview && window.pywebview._returnValuesCallbacks);
    var s = !!(window.sotto && typeof window.sotto.dispatch === 'function');
    var a = !!(window.pywebview && window.pywebview.api);
    return 'c' + (c ? 1 : 0) + 'p' + (p ? 1 : 0) + 's' + (s ? 1 : 0) + 'a' + (a ? 1 : 0);
  }
  function fire(kind) {
    try {
      var s = window.sotto;
      if (s && typeof s.dispatch === 'function') {
        s.dispatch(kind, { rs: String(document.readyState || '?') });
      }
    } catch (err) { }
  }
  function raw(kind) {
    try {
      if (window.chrome && window.chrome.webview && window.chrome.webview.postMessage) {
        window.chrome.webview.postMessage(['dispatch',
          JSON.stringify([JSON.stringify({ kind: kind, payload: {} })]), '0']);
      }
    } catch (err) { }
  }
  var marks = [0, 300, 1000, 2500, 5000];
  for (var i = 0; i < marks.length; i++) {
    (function (i) {
      setTimeout(function () {
        fire('preprobe-s' + i + '-' + st());
        raw('preprobe-r' + i + '-' + st());
      }, marks[i]);
    })(i);
  }
})();
"""


#: THE PAGE PROBE, and it is a REAL page script: the preload only INSTALLS a
#: `<script>` ELEMENT, and the element's own text is what runs -- inline scripts
#: execute in the document's own world, which is where panel.js runs. Same two
#: channels as the preload probe, so the pair is one experiment with two arms.
PAGE_PROBE_JS = r"""
(function () {
  'use strict';
  function pageProbe() {
    function st() {
      var c = !!(window.chrome && window.chrome.webview && window.chrome.webview.postMessage);
      var p = !!(window.pywebview && window.pywebview._returnValuesCallbacks);
      var s = !!(window.sotto && typeof window.sotto.dispatch === 'function');
      var a = !!(window.pywebview && window.pywebview.api);
      return 'c' + (c ? 1 : 0) + 'p' + (p ? 1 : 0) + 's' + (s ? 1 : 0) + 'a' + (a ? 1 : 0);
    }
    function fire(kind) {
      try {
        var s = window.sotto;
        if (s && typeof s.dispatch === 'function') {
          s.dispatch(kind, { rs: String(document.readyState || '?') });
        }
      } catch (err) { }
    }
    function raw(kind) {
      try {
        if (window.chrome && window.chrome.webview && window.chrome.webview.postMessage) {
          window.chrome.webview.postMessage(['dispatch',
            JSON.stringify([JSON.stringify({ kind: kind, payload: {} })]), '0']);
        }
      } catch (err) { }
    }
    var marks = [0, 500, 1500, 3000];
    for (var i = 0; i < marks.length; i++) {
      (function (i) {
        setTimeout(function () {
          fire('pageprobe-s' + i + '-' + st());
          raw('pageprobe-r' + i + '-' + st());
        }, marks[i]);
      })(i);
    }
  }
  function install() {
    try {
      var el = document.createElement('script');
      el.textContent = '(' + pageProbe.toString() + ')();';
      (document.head || document.documentElement || document.body).appendChild(el);
    } catch (err) { }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else { install(); }
})();
"""


#: THE OUT-OF-BAND READBACK (2026-10-13). The page->shell direction is silent, so
#: the page state is read over the seam that DOES work: exec_js
#: (CoreWebView2.ExecuteScriptAsync), whose value comes back to Python directly
#: and never touches the page->shell bridge. This is what says WHICH component of
#: the shell channelOpen() -- window.pywebview,
#: pywebview._returnValuesCallbacks, window.chrome.webview -- is missing, and it
#: carries window.SottoLazy.log(), the deferred loader OWN record of what it did
#: (boot / settle / load / ask / ask-failed).
PAGE_READBACK_JS = r"""
(function () {
  function t(x) { return typeof x; }
  var c = window.chrome && window.chrome.webview;
  var out = {};
  try {
    out.rs = String(document.readyState);
    out.pywebview = t(window.pywebview);
    out.platform = window.pywebview ? String(window.pywebview.platform) : null;
    out.rv = t(window.pywebview && window.pywebview._returnValuesCallbacks);
    out.api = t(window.pywebview && window.pywebview.api);
    out.chrome = t(window.chrome);
    out.cw = t(c);
    out.pm = t(c && c.postMessage);
    out.sotto = t(window.sotto);
    out.disp = t(window.sotto && window.sotto.dispatch);
    out.ann = t(window.announceReady);
    out.lazy = t(window.SottoLazy);
    out.links = document.querySelectorAll("link[data-sotto-lazy]").length;
    out.scripts = document.querySelectorAll("script[data-sotto-lazy]").length;
    out.counts = window.__sotto_emit ? window.__sotto_emit.counts : null;
    var p = document.getElementById("placeholder");
    out.ph = p ? String(p.textContent).replace(/\s+/g, " ").slice(0, 60) : null;
    out.lazyLog = window.SottoLazy ? window.SottoLazy.log() : null;
    out.apiDispatch = t(window.pywebview && window.pywebview.api && window.pywebview.api.dispatch);
    var cin = document.querySelector('link[href$="themes/cinematic.css"]');
    try { out.cinRules = cin && cin.sheet && cin.sheet.cssRules ? cin.sheet.cssRules.length : (cin ? -1 : -2); } catch (e) { out.cinRules = 'blocked'; }
    out.sottoSkins = t(window.SOTTO_SKINS);
    out.skinHost = t(window.SottoSkin);
    out.bodySkin = document.body ? String(document.body.getAttribute('data-skin') || '') : null;
    out.lazyHrefs = Array.prototype.map.call(
      document.querySelectorAll('link[data-sotto-lazy],script[data-sotto-lazy]'),
      function (e) { return String(e.getAttribute('href') || e.getAttribute('src')); });
    out.sheets = document.styleSheets.length;
  } catch (e) { out.err = String(e); }
  return JSON.stringify(out);
})()
"""


def build_variant(path: str, revert_gate: bool = False,
                  strip: bool = False, floated: bool = False,
                  theme: str = '', caption: str = '',
                  dragoffset=None, probe: str = '',
                  readback: bool = False) -> str:
    with open(SHELL, encoding='utf-8') as f:
        src = f.read()
    out = src.replace(
        "        self.geometry = dock_right(self.display['workArea'])\n",
        "        self.geometry = dock_right(self.display['workArea'])\n"
        "        # OFF-SCREEN copy (panel-paint-probe.py)\n"
        "        self.geometry['x'] = -10000\n", 1)
    if out == src:
        raise SystemExit('variant: offscreen edit did not apply — refusing')
    # THE SAVED RECT DEFEATS THE OFF-SCREEN PARKING, and that is not theoretical.
    # `geometry_for` returns `saved_geometry` whenever one exists for the surface
    # (sotto_webview.py:6607), so the `x = -10000` above is OVERWRITTEN and the
    # window appears ON THE OWNER'S DESK. MEASURED 2026-10-12: the probe logged
    # `PANEL_VISIBILITY_ON_SCREEN visible=true` and then found no window to
    # capture, because the one it made sat at the saved `panel` x=1528 and not at
    # -10000. The parking only ever worked while NO saved rect existed, and one
    # Alt+C run creates one. So the variant drops the saved rect as well, and
    # REFUSES rather than running if the anchor has moved.
    restored = "        self.restore_saved_geometry()\n"
    if restored not in out:
        raise SystemExit('variant: saved-geometry edit did not apply — refusing')
    out = out.replace(
        restored,
        "        # OFF-SCREEN copy: a saved rect would beat the parking above\n"
        "        self.saved_geometry = None\n", 1)
    # THE STRIP, NOT THE PANEL. `--show` hardcodes `surface='panel'`
    # (sotto_webview.py:4557), and the strip is the surface the owner's slab
    # complaint is ABOUT: 1040 px of window painting #0B0F14 under a small pill.
    # Capturing the panel cannot see that, so the variant opens the strip.
    if strip:
        show_anchor = "self.show_panel('startup', surface='panel')\n"
        if show_anchor not in out:
            raise SystemExit('variant: --strip edit did not apply — refusing')
        out = out.replace(
            show_anchor,
            "self.show_panel('startup', surface='strip')\n", 1)
        if floated:
            # A SECOND application, because the surface script above is what sets
            # `data-float`, and `refresh_strip_height` runs BEFORE it. Re-applying
            # is what the fixed `setFloat` now does in real use, so this measures
            # the real ordering instead of the broken one.
            again = "self.show_panel('startup', surface='strip')\n"
            if again not in out:
                raise SystemExit('variant: float re-apply edit did not apply')
            out = out.replace(
                again,
                "self.show_panel('startup', surface='strip')\n"
                "            self.set_panel_surface('strip', 'float-probe')\n", 1)
        # THE PARKING ABOVE ONLY PATCHES THE PANEL'S `dock_right`. The strip is
        # centred by `dock_strip`, so in --strip mode the window came up AT
        # x=770 ON THE OWNER'S MONITOR -- measured: on_monitor=True
        # rect=(770, 884, 1150, 1032). Parking inside `dock_strip` does NOT work
        # either: it ends with `max(work['x'], round(x))`, which clamps -10000
        # straight back to 0 (tried, measured, still on_monitor=True). So the park
        # is applied AFTER `geometry_for`, which is the one point both surfaces
        # pass through, and this REFUSES if the anchor has moved.
        geom_anchor = "        geometry = self.geometry_for(name)\n"
        if geom_anchor not in out:
            raise SystemExit('variant: geometry_for edit did not apply — refusing')
        out = out.replace(
            geom_anchor,
            "        geometry = self.geometry_for(name)\n"
            "        geometry['x'] = -10000  # OFF-SCREEN copy (paint-probe)\n", 1)
    # THE FLOATED CAPTION IS THE ONLY SURFACE WHERE THE PAGE DOES NOT PAINT THE
    # WHOLE WINDOW, so it is the only one that can answer the owner's actual word:
    # *"invisivel"*. `data-float="on"` is written by caption-float.js in normal
    # use; here it is written from the shell's own surface script, which runs when
    # the page is already loaded, so the float layout and --float-height are real.
    if floated:
        surf_anchor = ("'return window.SottoSurfaces.current(); } return null; })()'")
        if surf_anchor not in out:
            raise SystemExit('variant: --float edit did not apply — refusing')
        out = out.replace(
            surf_anchor,
            "'document.documentElement.setAttribute(\\'data-float\\',\\'on\\'); "
            "document.body.setAttribute(\\'data-float\\',\\'on\\'); "
            "return window.SottoSurfaces.current(); } return null; })()'", 1)
    # A THEME, SO THE DESIGNS CAN BE MEASURED INSTEAD OF PARSED. The owner's
    # report is *"varios designs estao bugados"* and every check so far has been a
    # parse of CSS bytes. This writes `data-theme` from the surface script -- the
    # same script the float mode uses -- so two themes can be captured and their
    # PIXELS compared. A theme whose signature is identical to another is a
    # recolour, which is the thing the owner said he does not want.
    if theme:
        anchor = ("'return window.SottoSurfaces.current(); } return null; })()'")
        if anchor not in out:
            raise SystemExit('variant: --theme edit did not apply — refusing')
        safe = theme.replace('\\', '').replace("'", '')
        # A ONE-SHOT WRITE IS NOT ENOUGH, AND THE BOGUS CONTROL PROVED IT.
        # Writing data-theme once produced the SAME pixels for theme-1, theme-3,
        # GlassCards, cine-cellar, cine-north-fog AND a theme that does not exist
        # -- all sha 09A63E78919C21A1. A nonexistent theme cannot paint the same as
        # a real one, so the write was being overwritten: theme-switcher.js applies
        # the STORED theme after the page loads. This PINS the attribute instead:
        # a MutationObserver re-asserts it whenever the switcher changes it, plus a
        # slow interval as a belt. The bogus control is what says whether it works.
        pin = ("'const T=\\\"" + safe + "\\\";"
               "const de=document.documentElement;"
               "const pin=()=>{if(de.getAttribute(\\\"data-theme\\\")!==T)"
               "de.setAttribute(\\\"data-theme\\\",T);};"
               "pin();"
               "try{new MutationObserver(pin).observe(de,"
               "{attributes:true,attributeFilter:[\\\"data-theme\\\"]});}catch(e){}"
               "try{setInterval(pin,150);}catch(e){}"
               "return window.SottoSurfaces.current(); } return null; })()'")
        out = out.replace(anchor, pin, 1)
    # THE DISCRIMINATOR. Two readings were left open: (a) the attribute never
    # reaches the render, or (b) with no captions the panel visible pixels are
    # styled by panel.css alone and are theme-independent. They are told apart by
    # ASKING THE DOCUMENT what it wears at capture time, so the variant reads
    # `data-theme` back after the surface script and logs it. A read-back that
    # says the theme IS set turns (a) into a false reading; one that says the
    # switcher overwrote it turns (b) into a false reading.
    if theme:
        rb = "        applied = self.exec_js(script)\n"
        if rb not in out:
            raise SystemExit('variant: readback edit did not apply — refusing')
        out = out.replace(
            rb,
            "        applied = self.exec_js(script)\n"
            "        try:\n"
            "            _t = self.exec_js(\"(function(){var d=document.documentElement;\"\n"
            "                                 \"return String(d.getAttribute('data-theme')) + '|' +\"\n"
            "                                 \"String(document.body && document.body.getAttribute('data-theme'));})()\")\n"
            "            log('PROBE_THEME_READBACK documentElement|body=' + str(_t))\n"
            "        except Exception as _e:\n"
            "            log('PROBE_THEME_READBACK_FAILED ' + repr(_e))\n", 1)
    # FEED THE SWITCHER INSTEAD OF FIGHTING IT. theme-switcher.js reads its
    # choice from `localStorage['sotto.theme']` (theme-switcher.js:42) and applies
    # it AFTER the page loads, which is why three rounds of pinning data-theme
    # were defeated. The bootstrap JS below is injected by the shell PRELOAD, so it
    # runs BEFORE any page script: writing the store key there makes the switcher
    # apply OUR theme as its own stored choice. The bogus control decides whether
    # it worked -- a theme that does not exist must now paint differently from one
    # that does.
    if theme:
        boot = "  window.sotto = {"
        if boot not in out:
            raise SystemExit('variant: bootstrap edit did not apply — refusing')
        out = out.replace(
            boot,
            "  try { window.localStorage.setItem('sotto.theme', '" + safe
            + "'); } catch (err) {}\n" + boot, 1)
    # THE DRAG, VERIFIED WITHOUT A HAND ON THE MOUSE. The shell half of the strip
    # drag has never been shown to move the WINDOW -- only that the bridge exposes
    # the method and the gesture oracle passes. This calls the page own
    # `window.sotto.setStripOffset(dx, dy, 'move')` from the surface script, and the
    # probe ALREADY LOGS THE WINDOW RECT, so the two rects ARE the measurement: the
    # window must move by exactly (dx, dy) from its docked position.
    if dragoffset:
        drag_anchor = 'return window.SottoSurfaces.current();'
        if drag_anchor not in out:
            raise SystemExit('variant: --dragoffset edit did not apply -- refusing')
        dx, dy = dragoffset
        # setTimeout ON PURPOSE: the surface script runs BEFORE the window is
        # positioned, and `_set_strip_offset` refuses unless the applied surface is
        # already `strip`. Firing immediately would be refused and the measurement
        # would say "the drag does nothing" when the truth is "the drag was never
        # delivered". 900 ms lands after `set_panel_surface` has finished.
        # FIRE TWICE ON PURPOSE, FOR THE DIAGNOSTIC. The IMMEDIATE call runs before
        # the window is positioned, so the shell either logs `STRIP_DRAG_REFUSED
        # why=not-strip` -- which PROVES the call ARRIVES and timing is the only
        # problem -- or logs nothing at all, which proves it never arrives and the
        # problem is the context the surface script runs in. The DELAYED call is the
        # one that would actually move the window.
        # NO SINGLE QUOTES ANYWHERE IN THE JS, AND json.dumps IS WHY. This text
        # lands inside the shell's SINGLE-quoted Python literal, so an apostrophe in
        # the JS terminates the Python string: MEASURED twice -- `kind:'dragprobe'`
        # and `'move'` both produced "SyntaxError: invalid syntax" in the built
        # variant and the shell never loaded, which read as NO WINDOW. json.dumps
        # gives a DOUBLE-quoted JS literal and nothing needs escaping.
        import json as _jd
        _mv = _jd.dumps('move')
        # A SYNTHETIC POINTER DRAG, NOT A DIRECT BRIDGE CALL, AND THAT IS THE
        # WHOLE POINT. MEASURED: a call made from this script does NOT reach the
        # shell -- neither window.pywebview.api.dispatch nor
        # window.sotto.setStripOffset -- because the context the shell own exec_js
        # runs in cannot see the bridge. But the PANEL OWN handler can: its buttons
        # call the bridge and change surfaces all day. So dispatch the events the
        # handler listens for and let IT call the bridge from the page normal
        # context. This tests the WHOLE chain -- gesture, panel code, bridge, shell,
        # window -- which is what "is the bar movable" actually means.
        #
        # ALL DOUBLE QUOTES, via json.dumps: single quotes here would terminate the
        # shell single-quoted Python literal this text lands in, which is a mistake I
        # made three times.
        import json as _jd
        _dx = str(int(dx))
        _dy = str(int(dy))
        # THE RAW CHANNEL PROBE, AND IT IS THE DECISIVE ONE. `post()` in the shell
        # bootstrap does NOT use window.pywebview.api.dispatch -- MEASURED at
        # sotto_webview.py:2805-2808, it uses `window.chrome.webview.postMessage` with
        # a three-slot ARRAY whose middle slot is JSON.stringify([JSON.stringify({kind,
        # payload})]). My earlier probes used the pywebview api channel, which the
        # shell never listens on, so "nothing arrived" proved nothing about the page.
        # This posts a kind the shell does not know, so `BRIDGE_UNKNOWN_KIND
        # kind=dragprobe` appearing in its log PROVES the raw channel and this context
        # both work -- and that the fault, if any, is window.sotto specifically.
        # NOT `probe`. This block used to ASSIGN to `probe`, which is a PARAMETER of
        # build_variant -- so with --dragoffset the local overwrote it, and the
        # `unknown --probe` refusal further down fired on the drag JS itself:
        #   variant: unknown --probe 'try{window.chrome.webview.postMessage(["dispatch"...
        #   -- refusing
        # and the probe produced NO log at all. MEASURED 2026-10-13: `--dragoffset`
        # was broken by the refactor that added --probe, and I read the silence as
        # another failure of the drag. Shadowing a parameter is the whole bug.
        chan_probe = ('try{window.chrome.webview.postMessage(["dispatch",'
                      'JSON.stringify([JSON.stringify({kind:"dragprobe",payload:{}})]),"0"]);}'
                      'catch(e){}')
        drag_js = (chan_probe + 'setTimeout(function(){try{'
                   # #strip-controls, WHICH IS `bar` IN THE HANDLER -- and the
                   # pointermove goes on WINDOW, not document. Both are read straight
                   # off panel.html: the listener is `bar.addEventListener(
                   # "pointerdown")` where `bar = document.getElementById(
                   # "strip-controls")` (:1098), and the move is `window.addEventListener(
                   # "pointermove")` (:1151). I first dispatched on the right element and
                   # the wrong move target, then "corrected" the element to `.stripbar`,
                   # which is a DIFFERENT handler in panel.js and not this one. Two
                   # guesses, both wrong, and the source said so the whole time.
                   # EVERY PROPERTY THE HANDLER READS IS SET EXPLICITLY NOW. The
                   # handler (panel.html:1140) starts with `if (event.button !== 0)
                   # return;` and then a `closest("button, a, input, select, textarea")`
                   # guard. A constructed PointerEvent defaults `button` to 0, which
                   # SHOULD pass -- but a default and an explicit value are not the same
                   # thing to assert, and `isPrimary`/`pointerType`/`buttons` are read by
                   # pointer code elsewhere. Set them all, so a failure means the drag
                   # does not work and not that the event was malformed.
                   'var P=function(t,x,y){return new PointerEvent(t,{clientX:x,clientY:y,'
                   'bubbles:true,cancelable:true,composed:true,pointerId:1,pointerType:"mouse",'
                   'isPrimary:true,button:0,buttons:1});};'
                   'var b=document.getElementById("strip-controls");if(!b)return;'
                   'var r=b.getBoundingClientRect();'
                   'var x0=r.left+20,y0=r.top+10;'
                   'b.dispatchEvent(P("pointerdown",x0,y0));'
                   'window.dispatchEvent(P("pointermove",x0+' + _dx + ',y0+' + _dy + '));'
                   'window.dispatchEvent(P("pointermove",x0+' + _dx + ',y0+' + _dy + '));'
                   'window.dispatchEvent(new PointerEvent("pointerup",'
                   '{clientX:x0+' + _dx + ',clientY:y0+' + _dy + ',bubbles:true,pointerId:1}));'
                   '}catch(e){}},900);')
        # THE LINE THAT APPLIES IT. It went missing in a rewrite, the injection was
        # computed and thrown away, and I read "nothing arrived" as "the bridge is
        # unreachable" -- a defect accusation against the product, from a probe that
        # never fired. THE CHECK THAT CATCHES IT: grep the BUILT VARIANT, not this
        # source, for the probe string.
        out = out.replace(drag_anchor, drag_js + drag_anchor, 1)

    # THE CAPTION, FOR THE FLAT-THEME DISCRIMINATOR. Pushes text through the page
    # own `window.sotto.pushCaption` so the panel HAS content.
    #
    # WARNING: THIS MODE IS NOT FINISHED. It builds and compiles, but EVERY capture
    # with it came back SEM PNG -- no window mapped -- so the injection breaks the
    # page or the window mapping and the discriminator it exists for has NOT been
    # run. Do not read a --caption capture as evidence, and do not read its absence
    # as a theme that paints nothing.
    if caption:
        # A DIFFERENT ANCHOR ON PURPOSE: the --theme block runs FIRST and already
        # consumed the long form of this statement, so this anchor is the bare one,
        # which survives whatever the theme block did to the text around it.
        # NO BACKSLASHES: json.dumps gives a DOUBLE-QUOTED JS string, which sits
        # happily inside the shell single-quoted Python literal.
        import json as _json
        cap_anchor = 'return window.SottoSurfaces.current();'
        if cap_anchor not in out:
            raise SystemExit('variant: --caption edit did not apply -- refusing')
        inject = ('try{var w=window;for(var i=0;i<12;i++){if(w.sotto&&w.sotto.pushCaption)'
                  'w.sotto.pushCaption(' + _json.dumps(caption + ' ') + ' + i, null);}}catch(e){}')
        out = out.replace(cap_anchor, inject + cap_anchor, 1)
    # ── THE DISCRIMINATOR (2026-10-13) ─────────────────────────────────────
    # WHY THE PRELOAD'S `ask()` NEVER ARRIVES, AND THE ONE TEST THAT DECIDES IT:
    # the PRELOAD's own context vs a PAGE SCRIPT's, on the SAME two channels. The
    # preload probe is appended to `_bootstrap_js`'s return value, so it is the
    # SAME script that carries BOOTSTRAP_JS and lazy-assets.js -- same world, same
    # moment. The page probe is an inline `<script>` element the preload only
    # INSTALLS; its text executes as a page script. Each fires
    # `window.sotto.dispatch` (the call lazy-assets.js makes) AND a raw
    # `window.chrome.webview.postMessage` in the shell's 3-slot wire format.
    # ── THE OUT-OF-BAND READBACK (2026-10-13) ─────────────────────────────
    # Logged from `panel_state_snapshot`, which runs every 2 s on the writer
    # thread: the page own world, read over the seam that works (exec_js).
    if readback:
        rb_anchor = '        dom = self.exec_js(PANEL_STATE_PROBE, timeout=5.0)\n'
        if out.count(rb_anchor) != 1:
            raise SystemExit('variant: readback anchor is not unique '
                             f'({out.count(rb_anchor)}) — refusing')
        rb = (rb_anchor +
              '        # PAGE_READBACK (paint-probe): the page own world, over exec_js.\n'
              '        try:\n'
              '            _rb = self.exec_js(' + repr(PAGE_READBACK_JS) + ', timeout=5.0)\n'
              '            log("PAGE_READBACK reason=" + str(reason) + " " + str(_rb))\n'
              '        except Exception as _e:\n'
              '            log("PAGE_READBACK_FAILED reason=" + str(reason) + " " + repr(_e))\n')
        out = out.replace(rb_anchor, rb, 1)
        if 'PAGE_READBACK reason=' not in out:
            raise SystemExit('variant: readback edit did not apply — refusing')
    if probe:
        if probe not in ('preload', 'page', 'both'):
            raise SystemExit(f'variant: unknown --probe {probe!r} — refusing')
        anchor = '    return BOOTSTRAP_JS + "\\n" + loader\n'
        if out.count(anchor) != 1:
            raise SystemExit('variant: preload-probe anchor is not unique '
                             f'({out.count(anchor)}) — refusing')
        extra = ''
        if probe in ('preload', 'both'):
            extra += ' + "\\n" + ' + repr(PRELOAD_PROBE_JS)
        if probe in ('page', 'both'):
            extra += ' + "\\n" + ' + repr(PAGE_PROBE_JS)
        out = out.replace(
            anchor, '    return BOOTSTRAP_JS + "\\n" + loader' + extra + '\n', 1)
        if 'preprobe-s' not in out or 'pageprobe-s' not in out:
            raise SystemExit('variant: preload-probe edit did not apply — refusing')
    if revert_gate:
        for old, new in GATE_REMOVED:
            if old not in out:
                raise SystemExit('variant: --revert-gate edit did not apply')
            out = out.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)
    return hashlib.sha256(src.encode()).hexdigest()[:16]


def pythonw() -> str:
    exe = sys.executable or ''
    if exe.lower().endswith('pythonw.exe'):
        return exe
    cand = exe.replace('python.exe', 'pythonw.exe')
    return cand if os.path.exists(cand) else exe


def arm(tag: str, extra: list, secs: float, shell: str,
        wait_for_show: bool = False) -> dict:
    alog = os.path.join(HERE, f'_paint-{tag}.log')
    if os.path.exists(alog):
        os.remove(alog)
    args = [pythonw(), shell, '--log', alog, '--no-hotkey', '--no-hot-reload',
            '--exit-after', str(secs), *extra]
    outp = open(alog + '.stdout', 'wb')
    proc = subprocess.Popen(args, stdout=outp, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                            cwd=os.path.dirname(shell),
                            creationflags=CREATE_NO_WINDOW)
    pid = proc.pid
    log(f'=== ARM {tag} extra={extra} pid={pid} secs={secs} '
        f'wait_for_show={wait_for_show} ===')
    shot = None
    t0 = time.time()

    def _log_text():
        try:
            with open(alog, encoding='utf-8', errors='replace') as f:
                return f.read()
        except OSError:
            return ''

    def _grab():
        hits = find_panel_window(pid)
        if not hits:
            return None
        h = hits[0]
        x0, y0, x1, y1 = h['rect']
        w, hh = max(1, x1 - x0), max(1, y1 - y0)
        s = dict(h)
        s.update(capture(h['hwnd'], w, hh))
        s['t_s'] = round(time.time() - t0, 2)
        return s

    if wait_for_show:
        # DO NOT capture the first mapped window. pywebview's `hidden=True`
        # dance maps the form for microseconds with `Opacity=0` BEFORE anything
        # is painted — MEASURED: a capture at t=0.95 s returned
        # `distinct_colours=1` (a blank form) for a panel that then loaded and
        # painted normally. So wait for the shell's OWN `PANEL_SHOWN` line and
        # let the page settle; only then is a capture a statement about paint.
        while time.time() - t0 < secs:
            time.sleep(0.3)
            if 'PANEL_SHOWN' in _log_text():
                break
        # WAIT FOR A SETTLED FRAME, NOT A FIXED DELAY. MEASURED 2026-10-13: a
        # single capture 2 s after PANEL_SHOWN is a RACE. The SAME theme produced
        # 1492 colours on one run and 1 on the next (PAINTED then UNIFORM), and a
        # third theme produced no PNG at all -- the capture was landing mid
        # re-render, which is what the theme switch causes. TWO CONSECUTIVE
        # IDENTICAL FRAMES is what makes a capture a statement about paint rather
        # than about timing, and it costs a couple of seconds.
        # THE BUDGET IS INDEPENDENT OF --secs, AND THAT IS THE FIX. It used to be
        # `max(6.0, secs * 0.9)`, so a caller who shortened --secs to make the run
        # quicker ALSO shortened the settle window without knowing it. MEASURED
        # 2026-10-13: the census ran at --secs 10 (a 9 s budget) and the same theme
        # came back PAINTED in one run and UNIFORM in the next, while the stability
        # test at --secs 12 (10.8 s) looked convincing. The settle window is now a
        # constant that --secs cannot shrink.
        SETTLE_BUDGET_S = 25.0
        # AND THE SAMPLE INTERVAL WAS ALIASING WITH THE CARET. MEASURED
        # 2026-10-13: `theme-3.css` carries `animation: sotto-caret 1.06s
        # steps(1) infinite` -- a blinking caret, on purpose, that NEVER settles
        # for more than one phase. The loop sampled every 1.2 s, which is within
        # 0.14 s of that 1.06 s period, so consecutive frames landed in the same
        # phase on some runs and drifted on others. THAT is the whole reason the
        # same theme came back PAINTED and UNIFORM from the same bytes: not a
        # racy renderer, an instrument whose sample rate beat against the thing it
        # was measuring. 0.35 s puts about three samples inside one 1.06 s phase,
        # so a stable pair is found while the caret is still on.
        SAMPLE_S = 0.35
        prev = None
        settled = False
        deadline = time.time() + SETTLE_BUDGET_S
        while time.time() < deadline:
            cur = _grab()
            if cur is not None:
                if prev is not None and cur.get('px_sha256') == prev.get('px_sha256'):
                    shot = cur
                    settled = True
                    break
                prev = cur
            time.sleep(SAMPLE_S)
        if not settled:
            # AN UNSETTLED CAPTURE MUST NOT BE ABLE TO PASS FOR A MEASUREMENT.
            # The old code fell back to the last frame and set settled=false, and
            # the census never checked the flag -- which is exactly how two themes
            # were published as PAINTED and UNIFORM from the same bytes. The
            # verdict now says UNSETTLED and the caller has to deal with it.
            shot = prev
            if shot is not None:
                shot['settled'] = False
            log(f'CAPTURE_UNSETTLED budget_s={SETTLE_BUDGET_S}')
        else:
            shot['settled'] = True
    else:
        while time.time() - t0 < secs:
            time.sleep(0.3)
            if _grab() is not None:
                shot = _grab()
                break

    try:
        proc.wait(timeout=secs + 45)
    except subprocess.TimeoutExpired:
        proc.kill()
    outp.close()
    tail = []
    if os.path.exists(alog):
        for ln in open(alog, encoding='utf-8', errors='replace'):
            if any(k in ln for k in ('RECEIVER_READY', 'PRELOAD_ACTIVE',
                                     'PANEL_VISIBILITY_ON_SCREEN', 'PANEL_SHOWN',
                                     'PANEL_SHOW_REFUSED', 'PANEL_SHOW_GATE',
                                     'BRIDGE_UNKNOWN_KIND', 'PANEL_LAZY_ALLOW',
                                     'PANEL_LAZY_ASK_REFUSED', 'PANEL_LAZY_EMPTY url=',
                                     'BRIDGE_BAD_MESSAGE', 'BRIDGE_HANDLER_FAILED')):
                tail.append(ln.strip())
    if shot is None:
        log(f'ARM {tag}: NO mapped Sotto window found in {secs} s — nothing '
            'was captured')
    else:
        log(f'ARM {tag}: hwnd={shot["hwnd"]} class={shot["class"]} '
            f'on_monitor={shot["on_monitor"]} rect={shot["rect"]} '
            f'printwindow_ok={shot["printwindow_ok"]} '
            f'getdibits_rows={shot["getdibits_rows"]} '
            f'distinct_colours={shot["distinct_colours"]} (capped at 65) '
            f'bytes={shot["bytes"]} px_sha256={shot["px_sha256"]} '
            f't_s={shot["t_s"]}')
    for ln in tail:
        log(f'  log: {ln}')
    verdict = 'NO-WINDOW'
    if shot is not None:
        # AN UNSETTLED FRAME IS NOT A MEASUREMENT. The old code fell back to the
        # last frame and set settled=false, and the census never checked the flag --
        # which is how two themes were published as PAINTED and UNIFORM from the
        # same bytes. UNSETTLED is its own verdict and the caller must deal with it.
        verdict = ('UNSETTLED' if not shot.get('settled', True)
                   else ('PAINTED' if shot['distinct_colours'] > 1 else 'UNIFORM'))
    log(f'ARM-VERDICT {tag}: {verdict}')
    return {'tag': tag, 'shot': shot, 'verdict': verdict}


def main() -> int:
    a = sys.argv[1:]
    secs = 7.0
    if '--secs' in a:
        secs = float(a[a.index('--secs') + 1])
    revert = '--revert-gate' in a
    strip = '--strip' in a
    floated = '--float' in a
    theme = ''
    if '--theme' in a:
        theme = str(a[a.index('--theme') + 1])
    caption = ''
    if '--caption' in a:
        caption = str(a[a.index('--caption') + 1])
    dragoffset = None
    if '--dragoffset' in a:
        _d = str(a[a.index('--dragoffset') + 1]).split(',')
        dragoffset = (int(_d[0]), int(_d[1]))
    probe = ''
    if '--probe' in a:
        probe = str(a[a.index('--probe') + 1])
    readback = '--readback' in a
    suffix = '-control' if revert else ''
    log('PAINT panel-paint-probe start='
        f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} secs={secs} '
        f'revert_gate={revert}')
    p = os.path.join(VARIANT_DIR, '_paint-offscreen-sotto_webview.py')
    sha = build_variant(p, revert_gate=revert, strip=strip, floated=floated,
                        theme=theme, caption=caption,
                        dragoffset=dragoffset, probe=probe,
                        readback=readback)
    log(f'VARIANT sha256_live={sha} path={os.path.basename(p)} '
        f'revert_gate={revert} probe={probe!r} theme={theme!r} strip={strip} '
        f'readback={readback}')
    try:
        # `--opaque` is the A/B for the TRANSPARENCY. The shell sets the form
        # BackColor to #0B0F14 only under that flag and to Color.Transparent
        # otherwise, so running the SAME capture both ways isolates what the form
        # contributes to the pixels the page does not paint. Without this pair, a
        # capture showing grey tells you nothing about whether the slab is gone.
        extra_asked = ['--show'] + (['--opaque'] if '--opaque' in a else [])
        asked = arm('asked' + suffix, extra_asked, secs, p, wait_for_show=True)
        notasked = arm('notasked' + suffix, [], secs, p)
    finally:
        if os.path.exists(p):
            os.remove(p)
            log(f'CLEANUP removed={os.path.basename(p)}')
    log('=== VERDICT ===')
    log(f'asked   : {asked["verdict"]}  (MUST be PAINTED)')
    log(f'notasked: {notasked["verdict"]}  (MUST be NO-WINDOW — the capture\'s '
        'own negative control)')
    ok = asked['verdict'] == 'PAINTED' and notasked['verdict'] == 'NO-WINDOW'
    log(f'PAINT-VERDICT {"PASS" if ok else "FAIL"}')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
