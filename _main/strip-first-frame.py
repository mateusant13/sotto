"""THE FIRST FRAME: does the form's flat background ever reach the screen?

WHY THIS FILE EXISTS
--------------------
_main/strip-whose-pixels.py samples at a ~0.1-0.2 s cadence and
_main/webview-child-gate.py polls every 0.2 s and keeps the LAST of ~12
samples, so both measure the SETTLED strip. Neither can answer the question the
2026-10-10 handoff actually raised:

    when the strip is mapped, is the FIRST thing the owner sees the form's own
    BackColor (the flat block), with the WebView2 composite arriving only after?

The order in show_strip / show_side / show_panel is
(move hidden window) -> (style child WS_VISIBLE) -> foreground_unlock = the map
-> transparency_hack = the composite. Between the map and the composite the form
paints its own BackColor, which _on_before_show sets to
Color.FromArgb(0xFF, 0x0B, 0x0F, 0x14) = rgb(11, 15, 20). A window that lasts a
few milliseconds is invisible to a 0.2 s poll and is exactly what the owner
would perceive as a flash.

HOW IT MEASURES
---------------
A dedicated sampler thread runs a TIGHT loop (no sleep) and, every iteration:

  1. GetWindowRect on the shell form HWND, so it FOLLOWS the window from the
     instant place_panel moves it (the rect is final before the map);
  2. IsWindowVisible on that form;
  3. WindowFromPoint at the rect centre -> the pid that OWNS the pixel. Before
     the map this is the desktop/taskbar; at the map it becomes the shell pid.
     This is the arm that tells "Sotto is on screen" apart from "we are looking
     at the wallpaper" -- a luminance count cannot tell those apart.
  4. only once the form has a sane rect, BitBlt the whole rect off the screen DC
     and classify a SPARSE GRID of it:
        distinct = number of distinct colours among the grid points
        flat     = every grid point within +/-TOL of the FIRST grid point, i.e.
                   the whole window is ONE colour -- nothing has painted
        slab     = that one colour is the form BackColor rgb(11, 15, 20)
                   (the failure-mode slab set by _on_before_show); a SEPARATE
                   flag on purpose, because the blank frame is NOT always the
                   slab colour -- measured rgb(32,32,32) and rgb(12,16,21) on
                   two runs of the same bytes, so keying the verdict on the
                   exact colour would have made the instrument blind to half
                   its own subject.
     flat is "the panel has painted nothing"; a WebView2 page that has painted
     anything (text, borders, an image) yields flat = 0.

Every sample records its own duration, so the report states the cadence the run
actually achieved. That cadence is the instrument resolution and its honest
limit: a frame shorter than one loop iteration can be missed.

THE ARMS
--------
  FLAT  (before the swap)   a blank single-colour window IS expected: >= 1
                            sample in the window is flat (slab or not).
  CLEAN (after the swap)    no sample in the window is flat -- the composite
                            was there from the first owned sample.

A CLEAN reading is only credible when the same instrument, on the same subject,
has SEEN the flat block -- so the BEFORE run is the sensitivity control, and a
run that sees nothing is reported NO-CONFIDENCE, never GREEN. Exit codes:
  0 = the requested arm was observed (FLAT arm: flat seen; CLEAN arm: not seen)
  1 = the requested arm was NOT observed
  2 = NO-CONFIDENCE (fewer than MIN_WINDOW samples owned by Sotto, i.e. the
      instrument never got a look at the window at all)

The window is [first sample whose pixel the shell owns, +400 ms]. Sotto owning
the pixel is also the moment the clock starts, so a defect frame cannot hide
before the clock starts.

The shell is launched exactly as _main/webview-child-gate.py launches it
(CREATE_NO_WINDOW|DETACHED_PROCESS, real Alt+C, --exit-after), but with
--no-worker: this is a pixel measurement and an audio tap on every arm is
neither needed nor wanted. Nothing here writes an image.
"""

import ctypes
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SHELL = r"H:\sotto\app\webview\sotto_webview.py"
TMP = os.environ.get("TMPDIR", r"I:\cc-tmp")
LOG = TMP + r"\first-frame.log"
REPORT = TMP + r"\first-frame-report.txt"
# main() records the --report path here so the FATAL handler cannot write the
# traceback to a different file than the rest of the report (measured 2026-10-10).
_REPORT_PATH = []

VK_MENU, VK_C = 0x12, 0x43
SRC = 0x00CC0020
FLAT_R, FLAT_G, FLAT_B = 0x0B, 0x0F, 0x14   # _on_before_show BackColor #0B0F14
TOL = 2
WINDOW_MS = 400.0
MIN_WINDOW = 3
GRID_X, GRID_Y = 16, 7

HWND, BOOL, DWORD, LPARAM = (wintypes.HWND, wintypes.BOOL, wintypes.DWORD,
                             wintypes.LPARAM)


class R(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class BIH(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long),
                ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]


def _text(h):
    b = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, b, 512)
    return b.value or '<unnamed>'


def _rect(h):
    r = R()
    user32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def _pid_of(h):
    p = DWORD(0)
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def _cls(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value or '<noclass>'


def _root(h):
    """GA_ROOT=2: the top-level window that owns h, however deep it is."""
    return user32.GetAncestor(h, 2)


def find_form(pid):
    """Top-level window titled Sotto owned by pid, or 0."""
    found = []

    @ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
    def cb(h, l):
        if _pid_of(h) == pid and _text(h) == 'Sotto':
            found.append(h)
            return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else 0


def sane(w, h):
    return 200 <= w <= 4000 and 40 <= h <= 2000


class Sampler(threading.Thread):
    """Tight loop; records one row per iteration until stopped or budgeted."""

    def __init__(self, pid, budget):
        threading.Thread.__init__(self)
        self.daemon = True
        self.pid = pid
        self.budget = budget
        self.rows = []
        self.stop = False
        self.census_calls = 0
        self.done = threading.Event()

    def run(self):
        hwnd = 0
        dc = user32.GetWindowDC(0)
        mem = gdi32.CreateCompatibleDC(dc)
        bmp = gdi32.CreateCompatibleBitmap(dc, 4000, 2000)
        old = gdi32.SelectObject(mem, bmp)
        cap = 4000 * 2000 * 4
        buf = ctypes.create_string_buffer(cap)
        bih = BIH()
        bih.biSize = ctypes.sizeof(BIH)
        bih.biPlanes, bih.biBitCount, bih.biCompression = 1, 32, 0
        while not self.stop and len(self.rows) < self.budget:
            t0 = time.perf_counter()
            if not hwnd:
                hwnd = find_form(self.pid)
                self.census_calls += 1
                if not hwnd:
                    time.sleep(0.002)
                    continue
            x, y, w, h = _rect(hwnd)
            vis = bool(user32.IsWindowVisible(hwnd))
            owner = 0
            hcls = ''
            root_is_form = False
            if w > 0 and h > 0:
                pt = POINT(x + w // 2, y + h // 2)
                hw = user32.WindowFromPoint(pt)
                if hw:
                    owner = _pid_of(hw)
                    hcls = _cls(hw)
                    root_is_form = (_root(hw) == hwnd)
            own = root_is_form or owner == self.pid
            distinct = 0
            flat = 0
            slab = 0
            rgb0 = (0, 0, 0)
            ok = vis and sane(w, h)
            if ok:
                gdi32.BitBlt(mem, 0, 0, w, h, dc, x, y, SRC)
                bih.biWidth, bih.biHeight = w, -h
                gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bih), 0)
                px = buf.raw
                seen = set()
                near = 0
                slabhits = 0
                rgb0 = None
                for gy in range(1, GRID_Y + 1):
                    yy = min(h - 1, gy * h // (GRID_Y + 1))
                    base = yy * w * 4
                    for gx in range(1, GRID_X + 1):
                        xx = min(w - 1, gx * w // (GRID_X + 1))
                        o = base + xx * 4
                        b, g, r = px[o], px[o + 1], px[o + 2]
                        if rgb0 is None:
                            rgb0 = (r, g, b)
                        seen.add((r, g, b))
                        if (abs(r - rgb0[0]) <= TOL and abs(g - rgb0[1]) <= TOL
                                and abs(b - rgb0[2]) <= TOL):
                            near += 1
                        if (abs(r - FLAT_R) <= TOL and abs(g - FLAT_G) <= TOL
                                and abs(b - FLAT_B) <= TOL):
                            slabhits += 1
                distinct = len(seen)
                flat = 1 if near == GRID_X * GRID_Y else 0
                slab = 1 if slabhits == GRID_X * GRID_Y else 0
            self.rows.append({'t': t0, 'vis': vis, 'own': own, 'hpid': owner,
                              'hcls': hcls, 'w': w, 'h': h, 'ok': ok,
                              'distinct': distinct, 'flat': flat,
                              'slab': slab, 'rgb': rgb0,
                              'dt': time.perf_counter() - t0})
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, dc)
        self.done.set()


def send_alt_c():
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_C, 0, 2, 0)
    user32.keybd_event(VK_MENU, 0, 2, 0)


def _write(path, lines):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    except OSError as e:
        if sys.stdout is not None:
            print('could not write report: %r' % (e,))


def main():
    argv = sys.argv
    arm = argv[argv.index('--arm') + 1] if '--arm' in argv else 'flat'
    shell = argv[argv.index('--shell') + 1] if '--shell' in argv else SHELL
    secs = float(argv[argv.index('--secs') + 1]) if '--secs' in argv else 6.0
    span = float(argv[argv.index('--span') + 1]) if '--span' in argv else 2.5
    #: --shows 2 measures a SECOND show of the strip with the renderer already
    #: warm: press 1 shows, press 2 hides, press 3 shows again. Every press is
    #: spaced WIDER than HOTKEY_DOUBLE_MS (1500 ms), because a second press
    #: inside that window is read as the SIDE-panel gesture, not a toggle.
    shows = int(argv[argv.index('--shows') + 1]) if '--shows' in argv else 1
    gap = float(argv[argv.index('--gap') + 1]) if '--gap' in argv else 2.2
    report_path = (argv[argv.index('--report') + 1]
                   if '--report' in argv else REPORT)
    _REPORT_PATH.append(report_path)
    out = []

    def emit(s=''):
        # pythonw.exe has sys.stdout = None; the FILE is the report channel.
        if sys.stdout is not None:
            try:
                print(s)
            except Exception:
                pass
        out.append(s)

    user32.SetProcessDPIAware()
    if os.path.exists(LOG):
        os.remove(LOG)
    emit('SUBJECT %s' % shell)
    emit('ARM %s  (flat = expect the flat block; clean = expect none)' % arm)
    p = subprocess.Popen([sys.executable, shell, '--no-worker',
                          '--exit-after', '90', '--log', LOG],
                         creationflags=0x08000000 | 0x00000008)
    emit('LAUNCHED pid=%d  (real shell, no worker, real Alt+C -- a MEASUREMENT '
         'run that owns the hotkey)' % p.pid)
    t0 = time.time()
    ready = False
    while time.time() - t0 < 45:
        try:
            if 'PRELOAD_ACTIVE' in open(LOG, encoding='utf-8',
                                        errors='replace').read():
                ready = True
                break
        except OSError:
            pass
        time.sleep(0.4)
    if not ready:
        emit('VERDICT NO-CONFIDENCE -- PRELOAD_ACTIVE never appeared')
        emit('EXIT 2')
        p.kill()
        _write(report_path, out)
        return 2
    emit('PRELOAD_ACTIVE seen; settling %ss' % secs)
    time.sleep(secs)

    # The sampler self-stops when its budget is spent. Sampling a HIDDEN strip
    # costs ~0.06 ms/row (16 000 rows/s) against ~18 ms/row when it is on
    # screen, so a --shows 2 run burns the single-show budget during press 1
    # and never reaches press 3. Scale it by the number of shows.
    budget = 40000 if shows < 2 else 150000
    emit('sampler budget=%d row(s)' % budget)
    s = Sampler(p.pid, budget=budget)
    s.start()
    time.sleep(0.15)
    npress = len(s.rows)
    emit('sampler armed (rows=%d before the press)' % npress)
    tpress = time.perf_counter()
    send_alt_c()
    emit('Alt+C sent (press 1: SHOW the strip)')
    tpress2 = None
    if shows >= 2:
        # Press 2 must be OUTSIDE the double-press window, or it is read as the
        # SIDE gesture instead of a toggle-to-hide.
        time.sleep(gap)
        tlast = time.perf_counter()
        send_alt_c()
        emit('Alt+C sent (press 2: HIDE, %.0f ms after press 1)'
             % ((tlast - tpress) * 1000.0))
        time.sleep(gap)
        tpress2 = time.perf_counter()
        send_alt_c()
        emit('Alt+C sent (press 3: SHOW again, %.0f ms after press 2)'
             % ((tpress2 - tlast) * 1000.0))
    time.sleep(span)
    s.stop = True
    s.join(timeout=8)
    emit('EXIT CODE SCOPE: the arm exit code below describes the FIRST show '
         'only; the second show has its own verdict line.')
    emit('sampler stopped: %d rows in %.2fs (%.0f rows/s)'
         % (len(s.rows), span, len(s.rows) / span))

    rows = s.rows
    if not rows:
        emit('VERDICT NO-CONFIDENCE -- sampler produced no rows')
        emit('EXIT 2')
        p.kill()
        _write(report_path, out)
        return 2
    dts = sorted(r['dt'] for r in rows)
    med = dts[len(dts) // 2]
    emit('find_form calls=%d (1 = the form was found on the first try)'
         % s.census_calls)

    first = None
    for i, r in enumerate(rows):
        if r['own']:
            first = i
            break
    if first is None:
        emit('  DIAG: rows after the press (first 12), point at form centre')
        emit('  row      +ms  vis dist own hpid     hcls')
        for i, r in enumerate(rows[npress:npress + 12], start=npress):
            emit('  %5d %+7.1f   %d  %4d   %d  %-8d %s'
                 % (i, (r['t'] - tpress) * 1000.0, r['vis'], r['distinct'],
                    r['own'], r['hpid'], r['hcls']))
        emit('VERDICT NO-CONFIDENCE -- no sample had the shell owning the strip '
             'centre; Alt+C mapped nothing, or the point was never Sotto')
        emit('EXIT 2')
        p.kill()
        _write(report_path, out)
        return 2

    tmap = rows[first]['t']
    win = [r for r in rows[first:] if (r['t'] - tmap) * 1000.0 <= WINDOW_MS]
    owned_ok = [r for r in win if r['own'] and r['ok']]
    flats = [r for r in owned_ok if r['flat']]
    colours = sorted({r['rgb'] for r in flats})

    # --- THE SECOND SHOW: is the blank a first-map artefact or per-map? -----
    if tpress2 is not None:
        second = None
        for i, r in enumerate(rows):
            if r['t'] >= tpress2 and r['own']:
                second = i
                break
        emit('--- SECOND SHOW (press 3, renderer already warm) ---')
        if second is None:
            emit('SECOND-SHOW VERDICT NO-CONFIDENCE -- no owned sample after the '
                 'second show; Alt+C mapped nothing there')
        else:
            tmap2 = rows[second]['t']
            win2 = [r for r in rows[second:]
                    if (r['t'] - tmap2) * 1000.0 <= WINDOW_MS]
            ok2 = [r for r in win2 if r['own'] and r['ok']]
            flats2 = [r for r in ok2 if r['flat']]
            col2 = sorted({r['rgb'] for r in flats2})
            emit('  first pixel owned by the shell at row %d (+%.1f ms after '
                 'press 3)' % (second, (tmap2 - tpress2) * 1000.0))
            emit('  samples=%d  owned+classified=%d  flat-single-colour=%d'
                 % (len(win2), len(ok2), len(flats2)))
            if not ok2:
                emit('SECOND-SHOW VERDICT NO-CONFIDENCE -- %d sample(s) in the '
                     'second window, none owned+classified' % len(win2))
            elif flats2:
                emit('SECOND-SHOW VERDICT BLANK RECURS -- %d of %d classified '
                     'sample(s) after the SECOND map were one colour (%s), so '
                     'the blank is NOT a first-map artefact'
                     % (len(flats2), len(ok2), col2))
            else:
                emit('SECOND-SHOW VERDICT CLEAN -- 0 of %d classified sample(s) '
                     'after the second map were blank; the blank is specific to '
                     'the first map of a process' % len(ok2))

    emit('--- the map ---')
    emit('  first pixel owned by the shell at row %d (+%.1f ms after the press)'
         % (first, (tmap - tpress) * 1000.0))
    emit('  row      +ms  own   vis   dist flat slab    ms  rgb')
    lo = max(0, first - 4)
    for i in range(lo, min(len(rows), first + 8)):
        r = rows[i]
        emit('  %5d %+7.1f %-5s %-5s %4d %4d %4d %5.2f  %s'
             % (i, (r['t'] - tmap) * 1000.0, r['own'], r['vis'], r['distinct'],
                r['flat'], r['slab'], r['dt'] * 1000.0, r['rgb']))
    emit('--- the %g ms window after the map ---' % WINDOW_MS)
    emit('  samples=%d  owned+classified=%d  flat-single-colour=%d'
         % (len(win), len(owned_ok), len(flats)))
    after = [r for r in rows[first:] if r['own'] and r['ok']]
    painted = None
    for r in after:
        if r['distinct'] > 1:
            painted = r
            break
    if painted is None:
        emit('  BLANK HELD to the end: all %d owned sample(s) in %.1f s were '
             'a SINGLE colour -- the panel never painted'
             % (len(after), span))
    else:
        nblank = len([r for r in after if r['t'] < painted['t']])
        emit('  BLANK HELD for %.1f ms after the map: the panel first painted at '
             'row %d, distinct=%d, after %d single-colour owned sample(s)'
             % ((painted['t'] - tmap) * 1000.0, rows.index(painted),
                painted['distinct'], nblank))
    if flats:
        f0 = flats[0]
        emit('  FIRST FLAT FRAME at +%.1f ms after the map (distinct=%d, %dx%d)'
             % ((f0['t'] - tmap) * 1000.0, f0['distinct'], f0['w'], f0['h']))
    emit('  achieved cadence: median %.2f ms, min %.2f ms, max %.2f ms '
         '(that is the resolution; a frame shorter than one row can be missed)'
         % (med * 1000.0, dts[0] * 1000.0, dts[-1] * 1000.0))

    p.kill()
    if len(owned_ok) < MIN_WINDOW:
        emit('VERDICT NO-CONFIDENCE -- only %d classified sample(s) owned by the '
             'shell in the window (need >= %d); the instrument never got a '
             'proper look, so it cannot say yes or no'
             % (len(owned_ok), MIN_WINDOW))
        emit('EXIT 2')
        _write(report_path, out)
        return 2
    if arm == 'flat':
        if flats:
            emit('VERDICT FLAT-FRAME SEEN -- %d of %d classified sample(s) in '
                 'the first %g ms were a SINGLE-colour window (the panel had not '
                 'painted); colours seen: %s; %d of them were the form BackColor '
                 'slab rgb(11,15,20)+/-%d'
                 % (len(flats), len(owned_ok), WINDOW_MS, colours,
                    len([r for r in flats if r['slab']]), TOL))
            emit('EXIT 0')
            _write(report_path, out)
            return 0
        emit('VERDICT RED -- the FLAT arm expected the flat block and saw none '
             '(the instrument did not catch it this run)')
        emit('EXIT 1')
        _write(report_path, out)
        return 1
    if flats:
        emit('VERDICT RED -- the CLEAN arm expected the composite from the first '
             'sample and saw %d blank single-colour sample(s); colours seen: %s'
             % (len(flats), colours))
        emit('EXIT 1')
        _write(report_path, out)
        return 1
    emit('VERDICT NO FLAT FRAME -- 0 of %d classified sample(s) in the first '
         '%g ms after the map were a blank single-colour window; the composite '
         'was there from the first owned sample onward'
         % (len(owned_ok), WINDOW_MS))
    emit('EXIT 0')
    _write(report_path, out)
    return 0


if __name__ == '__main__':
    try:
        rc = main()
    except BaseException:
        import traceback
        try:
            path = _REPORT_PATH[0] if _REPORT_PATH else REPORT
            with open(path, 'a', encoding='utf-8') as f:
                f.write('\nFATAL\n' + traceback.format_exc() + '\n')
        except OSError:
            pass
        rc = 2
    sys.exit(rc)
