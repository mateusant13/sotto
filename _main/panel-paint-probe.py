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


def build_variant(path: str, revert_gate: bool = False,
                  strip: bool = False, floated: bool = False,
                  theme: str = '') -> str:
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
        time.sleep(2.0)
        shot = _grab()
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
                                     'PANEL_SHOW_REFUSED', 'PANEL_SHOW_GATE')):
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
        verdict = 'PAINTED' if shot['distinct_colours'] > 1 else 'UNIFORM'
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
    suffix = '-control' if revert else ''
    log('PAINT panel-paint-probe start='
        f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} secs={secs} '
        f'revert_gate={revert}')
    p = os.path.join(VARIANT_DIR, '_paint-offscreen-sotto_webview.py')
    sha = build_variant(p, revert_gate=revert, strip=strip, floated=floated,
                        theme=theme)
    log(f'VARIANT sha256_live={sha} path={os.path.basename(p)} '
        f'revert_gate={revert}')
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
