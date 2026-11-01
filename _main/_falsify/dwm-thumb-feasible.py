"""FEASIBILITY: can the DWM's OWN surface be read here, at all?

THE QUESTION. Windows Graphics Capture needs a D3D11 device, and this box
refuses to create one (measured: E_INVALIDPARAM 0x80070057 for EVERY adapter
and for HARDWARE / WARP / REFERENCE, at medium AND at the owner's HIGH
integrity). So the compositor-side instrument has to be the DWM THUMBNAIL API
(`DwmRegisterThumbnail`), which needs no D3D11 device: the DWM renders the
SOURCE window's redirection surface into a DESTINATION window, and the
destination is then read back.

THE QUESTION THIS ANSWERS, concretely:
  1. Does `DwmRegisterThumbnail` succeed for an OFF-SCREEN source (x=-10000),
     which is the only place a private instance may live?
  2. Does the thumbnail actually reach the destination's pixels, so the
     destination read is the SOURCE's composited surface?
  3. Does that read DISCRIMINATE a flat source from a populated one? An
     instrument that cannot say "blank" is not an instrument.

ARMS (all on windows this script owns):
  flat        one colour
  populated   bars + text
each read three ways: direct PrintWindow, thumbnail->dest PrintWindow, and
the same on a PRIVATE DESKTOP.

USAGE: python _main/_falsify/dwm-thumb-feasible.py
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
dwmapi = ctypes.WinDLL('dwmapi', use_last_error=True)

WM_DESTROY, WM_PAINT, WM_ERASEBKGND = 0x0002, 0x000F, 0x0014
WM_PRINT, WM_PRINTCLIENT = 0x0317, 0x0318
WS_POPUP, WS_CLIPCHILDREN = 0x80000000, 0x02000000
SW_SHOWNOACTIVATE = 4
PW_RENDERFULLCONTENT = 0x00000002
DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_RECTSOURCE = 0x00000010
DWM_TNP_SOURCEOVERRIDE = 0x00000200

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [('hdc', wintypes.HDC), ('fErase', wintypes.BOOL),
                ('rcPaint', RECT), ('fRestore', wintypes.BOOL),
                ('fIncUpdate', wintypes.BOOL),
                ('rgbReserved', ctypes.c_byte * 32)]


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [('dwFlags', wintypes.DWORD), ('rcDestination', RECT),
                ('rcSource', RECT), ('opacity', wintypes.UINT),
                ('fVisible', wintypes.BOOL), ('fSourceHasAlpha', wintypes.BOOL)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('style', wintypes.UINT),
                ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int), ('hInstance', wintypes.HINSTANCE),
                ('hIcon', wintypes.HICON), ('hCursor', wintypes.HANDLE),
                ('hbrBackground', wintypes.HBRUSH),
                ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR),
                ('hIconSm', wintypes.HICON)]


k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
k32.GetModuleHandleW.restype = wintypes.HMODULE

user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                   wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                  wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
user32.InvalidateRect.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = ctypes.c_void_p
user32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.PrintWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.BeginPaint.restype = ctypes.c_void_p
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.EndPaint.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT), wintypes.HBRUSH]
user32.FillRect.restype = ctypes.c_int
user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p]
user32.CreateDesktopW.restype = ctypes.c_void_p
user32.SetThreadDesktop.argtypes = [ctypes.c_void_p]
user32.SetThreadDesktop.restype = wintypes.BOOL
user32.SwitchDesktop.argtypes = [ctypes.c_void_p]
user32.SwitchDesktop.restype = wintypes.BOOL
user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
user32.GetThreadDesktop.restype = ctypes.c_void_p

dwmapi.DwmRegisterThumbnail.argtypes = [wintypes.HWND, wintypes.HWND,
                                        ctypes.POINTER(wintypes.HANDLE)]
dwmapi.DwmRegisterThumbnail.restype = ctypes.c_long
dwmapi.DwmUpdateThumbnailProperties.argtypes = [wintypes.HANDLE,
                                                 ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES)]
dwmapi.DwmUpdateThumbnailProperties.restype = ctypes.c_long
dwmapi.DwmUnregisterThumbnail.argtypes = [wintypes.HANDLE]
dwmapi.DwmUnregisterThumbnail.restype = ctypes.c_long
dwmapi.DwmQueryThumbnailSourceSize.argtypes = [wintypes.HANDLE,
                                                ctypes.POINTER(wintypes.SIZE)]
dwmapi.DwmQueryThumbnailSourceSize.restype = ctypes.c_long

gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
                            wintypes.UINT, ctypes.c_void_p,
                            ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.CreateSolidBrush.restype = wtypes_hbrush = wintypes.HBRUSH
gdi32.SetTextColor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
gdi32.SetBkMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.DrawTextW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_int,
                             ctypes.POINTER(RECT), wintypes.UINT]
user32.DrawTextW.restype = ctypes.c_int


class Win:
    COUNT = 0

    def __init__(self, w=380, h=140, flat=True, x=-10000, y=-10000):
        Win.COUNT += 1
        self.name = 'SottoFeas%d' % Win.COUNT
        self.flat = flat
        self.w, self.h = w, h
        self._proc = WNDPROC(self._wndproc)
        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
        cls.lpfnWndProc = self._proc
        cls.lpszClassName = self.name
        cls.hInstance = k32.GetModuleHandleW(None)
        user32.RegisterClassExW(ctypes.byref(cls))
        # hInstance=None on the CreateWindowExW call: with a real module handle
        # the window never receives WM_PAINT here (measured: paint hits 0).
        self.hwnd = int(user32.CreateWindowExW(
            0, self.name, self.name, WS_POPUP | WS_CLIPCHILDREN,
            x, y, w, h, None, None, None, None) or 0)
        if not self.hwnd:
            raise OSError('CreateWindowExW failed err=%d' % ctypes.get_last_error())
        user32.SetWindowPos(wintypes.HWND(self.hwnd), None, x, y, w, h, 0x0040)

    def map_it(self):
        user32.ShowWindow(wintypes.HWND(self.hwnd), SW_SHOWNOACTIVATE)
        user32.InvalidateRect(wintypes.HWND(self.hwnd), None, True)
        user32.UpdateWindow(wintypes.HWND(self.hwnd))
        return bool(user32.IsWindowVisible(wintypes.HWND(self.hwnd)))

    def _paint(self, hdc):
        rect = RECT(0, 0, self.w, self.h)
        base = gdi32.CreateSolidBrush(0x00202020)
        user32.FillRect(hdc, ctypes.byref(rect), base)
        gdi32.DeleteObject(base)
        if self.flat:
            return
        colours = (0x00E0E0E0, 0x003050A0, 0x0020A050, 0x00C04040,
                   0x00F0C040, 0x00A040C0)
        bar = max(8, self.h // (len(colours) + 2))
        for i, colour in enumerate(colours):
            brush = gdi32.CreateSolidBrush(colour)
            r = RECT(0, i * bar, self.w, (i + 1) * bar)
            user32.FillRect(hdc, ctypes.byref(r), brush)
            gdi32.DeleteObject(brush)
        gdi32.SetTextColor(hdc, 0x00FFFFFF)
        gdi32.SetBkMode(hdc, 1)
        text = RECT(6, 4, self.w - 6, self.h - 4)
        user32.DrawTextW(hdc, 'POPULATED', -1, ctypes.byref(text), 0x10)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            ps = ctypes.create_string_buffer(72)
            hdc = user32.BeginPaint(wintypes.HWND(hwnd), ps)
            self._paint(hdc)
            user32.EndPaint(wintypes.HWND(hwnd), ps)
            return 0
        if msg == WM_ERASEBKGND:
            self._paint(wparam)
            return 1
        if msg in (WM_PRINT, WM_PRINTCLIENT):
            self._paint(wparam)
            return 0
        if msg == WM_DESTROY:
            return 0
        return user32.DefWindowProcW(wintypes.HWND(hwnd), msg, wparam, lparam)


def describe(px):
    if not px:
        return 'EMPTY'
    step = max(4, (len(px) // 4096) // 4 * 4)
    sub = px[1::step]
    if not sub:
        return 'EMPTY'
    mean = sum(sub) / len(sub)
    var = sum(v * v for v in sub) / len(sub) - mean * mean
    std = var ** 0.5 if var > 0 else 0.0
    spread = max(sub) - min(sub)
    colours = set()
    for i in range(0, len(px) - 3, 4):
        colours.add(px[i:i + 3])
        if len(colours) > 256:
            break
    return 'distinct=%d std=%.2f spread=%d mean=%.1f' % (
        len(colours), std, spread, mean)


def read_dest_direct(hwnd):
    """What the DEST window painted ITSELF (not the thumbnail)."""
    r = RECT()
    hh = wintypes.HWND(int(hwnd))
    user32.GetClientRect(hh, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    mem = gdi32.CreateCompatibleDC(None)
    bmp = gdi32.CreateCompatibleBitmap(mem, w, h)
    old = gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hh, mem, PW_RENDERFULLCONTENT)
    info = BITMAPINFOHEADER()
    info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.biWidth = w
    info.biHeight = -h
    info.biPlanes = 1
    info.biBitCount = 32
    info.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0)
    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    return 'dest self-paint ok=%s rows=%s %s' % (bool(ok), got,
                                                 describe(buf.raw))


def read_pixels(hwnd):
    r = RECT()
    hh = wintypes.HWND(int(hwnd))
    if not user32.GetClientRect(hh, ctypes.byref(r)):
        return None, 'no-rect'
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return None, 'no-size'
    mem = gdi32.CreateCompatibleDC(None)
    bmp = gdi32.CreateCompatibleBitmap(mem, w, h)
    old = gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hh, mem, PW_RENDERFULLCONTENT)
    info = BITMAPINFOHEADER()
    info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.biWidth = w
    info.biHeight = -h
    info.biPlanes = 1
    info.biBitCount = 32
    info.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0)
    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    if got != h:
        return None, 'printwindow ok=%s rows=%s NO-BITMAP' % (bool(ok), got)
    return buf.raw, 'printwindow ok=%s %s' % (bool(ok), describe(buf.raw))


def thumb_read(src, label):
    """Register a thumbnail of `src` into a fresh destination and read IT."""
    dest = Win(flat=True)
    dest.map_it()
    thumb = wintypes.HANDLE()
    hr = dwmapi.DwmRegisterThumbnail(wintypes.HWND(dest.hwnd),
                                     wintypes.HWND(src.hwnd),
                                     ctypes.byref(thumb))
    if hr != 0:
        print('  %-22s DwmRegisterThumbnail hr=0x%08x' % (label, hr & 0xffffffff))
        return None
    props = DWM_THUMBNAIL_PROPERTIES()
    props.dwFlags = (DWM_TNP_RECTDESTINATION | DWM_TNP_RECTSOURCE |
                      DWM_TNP_SOURCEOVERRIDE)
    props.rcDestination = RECT(0, 0, dest.w, dest.h)
    props.rcSource = RECT(0, 0, dest.w, dest.h)
    props.opacity = 255
    props.fVisible = True
    props.fSourceHasAlpha = False
    hr2 = dwmapi.DwmUpdateThumbnailProperties(thumb, ctypes.byref(props))
    time.sleep(0.7)
    user32.InvalidateRect(wintypes.HWND(dest.hwnd), None, True)
    user32.UpdateWindow(wintypes.HWND(dest.hwnd))
    time.sleep(0.4)
    px, note = read_pixels(dest.hwnd)
    print('  %-22s reg=0x%08x update=0x%08x DEST=%s'
          % (label, hr & 0xffffffff, hr2 & 0xffffffff, note))
    print('  %-22s %s' % ('', read_dest_direct(dest.hwnd)))
    dwmapi.DwmUnregisterThumbnail(thumb)
    return px


def arm(desktop_note=''):
    flat = Win(flat=True)
    pop = Win(flat=False)
    flat.map_it()
    pop.map_it()
    time.sleep(0.4)
    print(' %s' % desktop_note)
    for name, win in (('flat', flat), ('populated', pop)):
        px, note = read_pixels(win.hwnd)
        print('  %-22s DIRECT %s' % (name, note))
    for name, win in (('flat', flat), ('populated', pop)):
        thumb_read(win, 'thumb-of-%s' % name)


def main():
    print('== ARM A: current desktop, windows at x=-10000 ==')
    arm('source+dest both at x=-10000')

    print()
    print('== ARM B: PRIVATE DESKTOP ==')
    desk = user32.CreateDesktopW('sotto-falsify', None, None, 0, 0x37F, None)
    if not desk:
        print('  CreateDesktopW failed err=%d' % ctypes.get_last_error())
        return
    old = user32.GetThreadDesktop(k32.GetCurrentThreadId())
    ok = user32.SetThreadDesktop(desk)
    print('  CreateDesktopW=%s SetThreadDesktop=%s' % (bool(desk), bool(ok)))
    if not ok:
        print('  SetThreadDesktop failed err=%d' % ctypes.get_last_error())
        return
    arm('private desktop "sotto-falsify", windows at x=-10000')


if __name__ == '__main__':
    main()
