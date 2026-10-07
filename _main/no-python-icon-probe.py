#!/usr/bin/env python3
"""What icon does the Sotto panel window ACTUALLY carry?

Measures, on the HIDDEN panel hwnd of a real shell run (`--no-hotkey
--no-hot-reload --exit-after N`, NEVER `--show`):

  * `WM_GETICON` for ICON_SMALL (0) / ICON_BIG (1) / ICON_SMALL2 (2)
  * `GetClassLongPtrW(GCLP_HICON)` / `(GCLP_HICONSM)`
  * `GetWindowLongPtrW(GWL_EXSTYLE)` -- WS_EX_TOOLWINDOW (out of the taskbar and
    out of Alt+Tab) vs WS_EX_APPWINDOW (forced INTO the taskbar)
  * the window's own `System.AppUserModel.ID`, read OUT OF PROCESS through
    `SHGetPropertyStoreForWindow` (the only AUMID that is readable from outside;
    `GetCurrentProcessExplicitAppUserModelID` is per-process and is read by the
    shell itself, logged as `APP_USER_MODEL_ID`)
  * the process image path, so the Python-icon fallback has a named source
  * the PIXEL hash of the icon Windows shows for that image (extracted with
    `ExtractIconExW` + `DrawIconEx` + `GetDIBits`), so "the before icon is the
    Python icon" is a comparison of bytes, not of a non-zero handle

NOTHING is shown: the window is never mapped, no audio device is opened (the
measurement flags suppress the worker), and the child is `pythonw.exe` with
CREATE_NO_WINDOW.

Usage:
  python _main/no-python-icon-probe.py --label before
  python _main/no-python-icon-probe.py --label after --icon app/webview/sotto.ico
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
PYW = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)
ole32 = ctypes.WinDLL('ole32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WM_GETICON = 0x007F
ICON_SMALL, ICON_BIG, ICON_SMALL2 = 0, 1, 2
GCLP_HICON, GCLP_HICONSM = -14, -34
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
DI_NORMAL = 0x0003
CREATE_NO_WINDOW = 0x08000000

user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
user32.GetClassLongPtrW.restype = ctypes.c_ssize_t
user32.GetClassLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindow.restype = wt.HWND
user32.GetWindow.argtypes = [wt.HWND, ctypes.c_uint]
user32.GetDC.restype = ctypes.c_void_p
user32.GetDC.argtypes = [wt.HWND]
user32.ReleaseDC.restype = ctypes.c_int
user32.ReleaseDC.argtypes = [wt.HWND, ctypes.c_void_p]
user32.DrawIconEx.restype = wt.BOOL
user32.DrawIconEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                              wt.HICON, ctypes.c_int, ctypes.c_int,
                              ctypes.c_uint, wt.HICON, ctypes.c_uint]
user32.GetIconInfo.restype = wt.BOOL
user32.GetIconInfo.argtypes = [wt.HICON, ctypes.c_void_p]
# EVERY call that takes a HANDLE needs its argtypes: with none, ctypes converts
# a Python int to a 32-bit C int and an HWND/HDC above 2**31 raises
# `OverflowError: int too long to convert` — measured, and it cost this probe a
# whole result once.
user32.FillRect.restype = ctypes.c_int
user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.EnumWindows.argtypes = [ctypes.c_void_p, wt.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.CreateSolidBrush.restype = ctypes.c_void_p
gdi32.CreateSolidBrush.argtypes = [wt.DWORD]
gdi32.DeleteObject.restype = wt.BOOL
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.restype = wt.BOOL
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                            ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p,
                            ctypes.c_uint]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.TerminateProcess.restype = wt.BOOL
kernel32.TerminateProcess.argtypes = [wt.HANDLE, ctypes.c_uint]
shell32.ExtractIconExW.restype = ctypes.c_uint
shell32.ExtractIconExW.argtypes = [wt.LPCWSTR, ctypes.c_int,
                                   ctypes.POINTER(wt.HICON),
                                   ctypes.POINTER(wt.HICON), ctypes.c_uint]
shell32.SHGetPropertyStoreForWindow.restype = ctypes.HRESULT
shell32.SHGetPropertyStoreForWindow.argtypes = [wt.HWND, ctypes.c_void_p,
                                                ctypes.POINTER(ctypes.c_void_p)]
ole32.PropVariantClear.restype = ctypes.HRESULT
ole32.PropVariantClear.argtypes = [ctypes.c_void_p]


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wt.WORD),
                ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
                ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wt.DWORD),
                ('biClrImportant', wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wt.DWORD * 3)]


# ── the window's own AppUserModel.ID, out of process ─────────────────────────
class GUID(ctypes.Structure):
    _fields_ = [('Data1', wt.DWORD), ('Data2', wt.WORD), ('Data3', wt.WORD),
                ('Data4', ctypes.c_ubyte * 8)]


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [('fmtid', GUID), ('pid', wt.DWORD)]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [('vt', wt.WORD), ('r1', wt.WORD), ('r2', wt.WORD),
                ('r3', wt.WORD), ('p', ctypes.c_void_p), ('pad', ctypes.c_void_p)]


VT_LPWSTR = 31
PKEY_AppUserModel_ID = PROPERTYKEY(
    GUID(0x9F4C2855, 0x9F79, 0x4B39, (ctypes.c_ubyte * 8)(0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)), 5)
IID_IPropertyStore = GUID(0x886D8EEB, 0x8CF2, 0x4446,
                          (ctypes.c_ubyte * 8)(0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99))


def window_aumid(hwnd: int):
    """The AUMID the shell will be grouped by, read from the WINDOW's store."""
    pps = ctypes.c_void_p()
    hr = shell32.SHGetPropertyStoreForWindow(
        wt.HWND(hwnd), ctypes.byref(IID_IPropertyStore), ctypes.byref(pps))
    if hr != 0 or not pps.value:
        return {'read': False, 'hr': hr, 'value': None}
    try:
        vtbl = ctypes.cast(pps, ctypes.POINTER(ctypes.c_void_p))[0]
        get_value = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p,
                                       ctypes.POINTER(PROPERTYKEY),
                                       ctypes.POINTER(PROPVARIANT))(
            ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[3])
        pv = PROPVARIANT()
        hr2 = get_value(pps, ctypes.byref(PKEY_AppUserModel_ID), ctypes.byref(pv))
        if hr2 != 0:
            return {'read': False, 'hr': hr2, 'value': None}
        value = None
        if pv.vt == VT_LPWSTR and pv.p:
            value = ctypes.wstring_at(pv.p)
        ole32.PropVariantClear(ctypes.byref(pv))
        return {'read': True, 'hr': 0, 'value': value, 'vt': pv.vt}
    finally:
        vtbl = ctypes.cast(pps, ctypes.POINTER(ctypes.c_void_p))[0]
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
            ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[2])
        release(pps)


# ── the pixels of an HICON, so two icons can be compared by bytes ────────────
class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wt.BOOL), ('xHotspot', wt.DWORD), ('yHotspot', wt.DWORD),
                ('hbmMask', ctypes.c_void_p), ('hbmColor', ctypes.c_void_p)]


def hicon_drawable(hicon: int) -> bool:
    """An HICON read out of ANOTHER process is not a handle this process can
    draw: `GetIconInfo` is the cheap test. Without it a failed `DrawIconEx`
    would hand back the black fill and a plausible-looking FALSE hash."""
    if not hicon:
        return False
    ii = ICONINFO()
    ok = bool(user32.GetIconInfo(wt.HICON(hicon), ctypes.byref(ii)))
    if ok:
        for hbm in (ii.hbmMask, ii.hbmColor):
            if hbm:
                gdi32.DeleteObject(hbm)
    return ok


def hicon_pixels(hicon: int, size: int = 32) -> str | None:
    if not hicon:
        return None
    if not hicon_drawable(hicon):
        return None
    hdc = user32.GetDC(None)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, size, size)
    old = gdi32.SelectObject(memdc, bmp)
    try:
        rect = RECT(0, 0, size, size)
        user32.FillRect(memdc, ctypes.byref(rect), gdi32.CreateSolidBrush(0x00000000))
        user32.DrawIconEx(memdc, 0, 0, wt.HICON(hicon), size, size, 0, None, DI_NORMAL)
        bi = BITMAPINFO()
        bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.bmiHeader.biWidth = size
        bi.bmiHeader.biHeight = -size          # top-down
        bi.bmiHeader.biPlanes = 1
        bi.bmiHeader.biBitCount = 32
        bi.bmiHeader.biCompression = 0         # BI_RGB
        buf = (ctypes.c_ubyte * (size * size * 4))()
        got = gdi32.GetDIBits(memdc, bmp, 0, size, ctypes.byref(buf),
                              ctypes.byref(bi), 0)
        if got != size:
            return None
        return hashlib.sha256(bytes(buf)).hexdigest()[:16]
    finally:
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(None, hdc)


def _safe_pixels(hicon) -> str | None:
    """An instrument failure must not lose the whole measurement."""
    if not hicon:
        return None
    try:
        return hicon_pixels(hicon)
    except Exception as exc:  # noqa: BLE001
        return f'ERR:{type(exc).__name__}:{exc}'


def exe_icon_pixels(path: str, size: int = 32) -> str | None:
    large = wt.HICON()
    small = wt.HICON()
    n = shell32.ExtractIconExW(path, 0, ctypes.byref(large), ctypes.byref(small), 1)
    if n <= 0 or not large:
        return None
    try:
        return hicon_pixels(large.value, size)
    finally:
        user32.DestroyIcon(large)
        if small:
            user32.DestroyIcon(small)


def ico_file_pixels(path: str) -> dict:
    """Pixel hash of EVERY frame in the .ico, so it can be matched against the
    hash the SHELL computes in-process from `form.Icon`."""
    out = {'path': path, 'exists': bool(path and os.path.isfile(path)), 'frames': {}}
    if not out['exists']:
        return out
    with open(path, 'rb') as fh:
        out['file_sha256'] = hashlib.sha256(fh.read()).hexdigest()[:16]
    try:
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        out['error'] = f'no-PIL:{type(exc).__name__}'
        return out
    try:
        im = Image.open(path)
        for size in sorted(getattr(im, 'ico', None).sizes() if getattr(im, 'ico', None) else [im.size]):
            im.size = size
            im.load()
            out['frames'][f'{size[0]}x{size[1]}'] = hashlib.sha256(
                im.convert('RGBA').tobytes()).hexdigest()[:16]
    except Exception as exc:  # noqa: BLE001
        out['error'] = f'{type(exc).__name__}:{exc}'
    return out


# ── the run ──────────────────────────────────────────────────────────────────
def log_has(log_path: str, needle: str) -> bool:
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
            return needle in fh.read()
    except FileNotFoundError:
        return False


def wait_for(log_path: str, needle: str, deadline: float) -> bool:
    while time.time() < deadline:
        if log_has(log_path, needle):
            return True
        time.sleep(0.1)
    return False


def read_hwnd_from_log(log_path: str, deadline: float):
    while time.time() < deadline:
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    if 'PANEL_VISIBILITY_AT_STARTUP' in line and 'hwnd=' in line:
                        for tok in line.split():
                            if tok.startswith('hwnd='):
                                raw = tok.split('=', 1)[1]
                                if raw.isdigit() and int(raw) != 0:
                                    return int(raw)
        except FileNotFoundError:
            pass
        time.sleep(0.1)
    return None


def image_path(pid: int) -> str | None:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return None
    finally:
        kernel32.CloseHandle(h)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--label', required=True)
    ap.add_argument('--icon', default=None,
                    help='the .ico the shell is expected to carry (for the hash comparison)')
    ap.add_argument('--secs', type=float, default=12.0)
    ap.add_argument('--settle', type=float, default=10.0,
                    help='after the hwnd exists, wait this long (or until '
                         'RECEIVER_READY) before reading: an icon read the '
                         'instant the hwnd appears is a MID-STARTUP state')
    ap.add_argument('--shell', default=SHELL,
                    help='the shell to launch (a control arm is the same file '
                         'with only the fix reverted)')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    stamp = time.strftime('%Y%m%d-%H%M%S')
    log_path = os.path.join(HERE, f'_no-python-icon-{args.label}-{stamp}.log')
    # ABSOLUTE: the child runs with cwd=app/webview, so a relative script path
    # would resolve a second time against it and never be found (pythonw.exe then
    # exits silently, stdout and stderr both None).
    cmd = [PYW, os.path.abspath(args.shell), '--no-hotkey', '--no-hot-reload',
           '--exit-after', str(int(args.secs + args.settle)), '--log', log_path]
    creationflags = CREATE_NO_WINDOW
    proc = subprocess.Popen(cmd, cwd=os.path.join(ROOT, 'app', 'webview'),
                            creationflags=creationflags,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid = proc.pid
    result = {'label': args.label, 'pid': pid, 'log': log_path,
              'cmd': ' '.join(cmd), 'icon_arg': args.icon}
    try:
        hwnd = read_hwnd_from_log(log_path, time.time() + args.secs)
        result['hwnd'] = hwnd
        if not hwnd:
            result['verdict'] = 'NO-HWND'
            return 1
        # LET THE STARTUP FINISH. Reading the icon the instant the hwnd exists
        # reads a MID-STARTUP state, and terminating there also skips the panel
        # load entirely — so a regression in loading would go unseen.
        ready = wait_for(log_path, 'RECEIVER_READY', time.time() + args.settle)
        result['receiver_ready'] = ready
        result['panel_loaded'] = log_has(log_path, 'STAGING_LOADED')
        time.sleep(1.0)
        # A CENSUS AT OUR OWN CADENCE, over the whole settle window: 100 ms is
        # enough to catch a startup flash and a ThreadExceptionDialog.
        census, seen = [], {}
        until = time.time() + 2.0
        while time.time() < until:
            for w in windows_of_pid(pid):
                key = (w['hwnd'], w['class'], w['title'])
                entry = seen.setdefault(key, dict(w, samples=0, visible_samples=0))
                entry['samples'] += 1
                entry['visible_samples'] += 1 if w['visible'] else 0
            time.sleep(0.1)
        census = list(seen.values())
        result['window_census'] = census
        result['visible_window_samples'] = sum(w['visible_samples'] for w in census)
        result['distinct_windows'] = len(census)
        result['image'] = image_path(pid)
        result['exe_icon_pixels'] = exe_icon_pixels(result['image'] or '')
        result['ico_file_pixels'] = ico_file_pixels(args.icon or '')
        result['window'] = {
            'class': _text(user32.GetClassNameW, hwnd),
            'title': _text(user32.GetWindowTextW, hwnd),
            'owner': int(user32.GetWindow(ctypes.c_void_p(hwnd), 4) or 0),  # GW_OWNER
            'exstyle': int(user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)),
            'aumid': window_aumid(hwnd),
        }
        result['window']['ex_toolwindow'] = bool(result['window']['exstyle'] & WS_EX_TOOLWINDOW)
        result['window']['ex_appwindow'] = bool(result['window']['exstyle'] & WS_EX_APPWINDOW)
        result['wm_geticon'] = {
            'ICON_SMALL': _icon(user32.SendMessageW(ctypes.c_void_p(hwnd), WM_GETICON, ICON_SMALL, 0)),
            'ICON_BIG': _icon(user32.SendMessageW(ctypes.c_void_p(hwnd), WM_GETICON, ICON_BIG, 0)),
            'ICON_SMALL2': _icon(user32.SendMessageW(ctypes.c_void_p(hwnd), WM_GETICON, ICON_SMALL2, 0)),
        }
        result['class_long'] = {
            'GCLP_HICON': _icon(user32.GetClassLongPtrW(ctypes.c_void_p(hwnd), GCLP_HICON)),
            'GCLP_HICONSM': _icon(user32.GetClassLongPtrW(ctypes.c_void_p(hwnd), GCLP_HICONSM)),
        }
        big = result['wm_geticon']['ICON_BIG'] or result['class_long']['GCLP_HICON']
        small = result['wm_geticon']['ICON_SMALL'] or result['class_long']['GCLP_HICONSM']
        # A HICON belongs to the process that owns it; these two are drawn
        # BEST EFFORT and reported as None when the handle is not drawable here
        # (see `hicon_drawable`). The authoritative pixel hash comes from the
        # SHELL, in-process: `WINDOW_ICON ... pixels=`.
        result['window_icon_pixels_big'] = _safe_pixels(big)
        result['window_icon_pixels_small'] = _safe_pixels(small)
        result['window_icon_drawable_here'] = bool(big and hicon_drawable(big))
        result['shell_log'] = _shell_lines(log_path)
        result['verdict'] = 'MEASURED'
        return 0
    finally:
        # PID-EXACT: only the process this probe spawned, and only after its
        # image path is confirmed to be the interpreter we launched.
        img = image_path(pid)
        if img and os.path.basename(img).lower().startswith('python'):
            h = kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
            if h:
                kernel32.TerminateProcess(h, 0)
                kernel32.CloseHandle(h)
        try:
            proc.wait(timeout=3)
        except Exception:
            pass
        with open(args.out or os.path.join(HERE, f'no-python-icon-{args.label}.json'),
                  'w', encoding='utf-8') as fh:
            json.dump(result, fh, indent=2)
        print(json.dumps(result, indent=2))


def _icon(value):
    return int(value) if value else 0


def _shell_lines(log_path: str) -> dict:
    """The shell's OWN measurement lines, so both colours cite one instrument."""
    want = ('WINDOW_ICON', 'WINDOW_ICON_APPLIED', 'APP_USER_MODEL_ID',
            'PANEL_EXSTYLE_REASSERT', 'PANEL_VISIBILITY_AT_STARTUP',
            'RECEIVER_READY')
    out = {k: [] for k in want}
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                for key in want:
                    if key in line:
                        out[key].append(line.strip())
    except FileNotFoundError:
        pass
    return out


def _text(fn, hwnd):
    buf = ctypes.create_unicode_buffer(512)
    fn(ctypes.c_void_p(hwnd), buf, 512)
    return buf.value


def windows_of_pid(pid: int):
    """Every top-level window this pid owns, and whether it is VISIBLE.

    A census of the probe's OWN subject, so "no window appeared" is a count and
    not an impression — the house census samples once per 60 s and cannot see a
    short-lived window (AGENTS.md). It also catches a WinForms
    `ThreadExceptionDialog`, which is a real window that a swallowed UI-thread
    exception would put on the owner's screen.
    """
    found = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _lparam):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid:
            return True
        found.append({
            'hwnd': int(hwnd),
            'class': _text(user32.GetClassNameW, hwnd),
            'title': _text(user32.GetWindowTextW, hwnd),
            'visible': bool(user32.IsWindowVisible(hwnd)),
        })
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


if __name__ == '__main__':
    sys.exit(main())
