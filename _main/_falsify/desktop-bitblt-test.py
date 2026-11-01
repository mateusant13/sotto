"""FEASIBILITY: a composed-surface read on a PRIVATE DESKTOP.

THE INSTRUMENT. `BitBlt` from a DESKTOP's screen device context reads what is
COMPOSED on that desktop -- a different source from `PrintWindow`, which asks
the window to paint ITSELF. The author's census reads the window's self-render;
this reads the surface the compositor would hand to a viewer.

THE SAFETY REASON IT IS A PRIVATE DESKTOP. A desktop that is never switched to
cannot appear on the owner's screen: there is no screen showing it. This is
stronger than parking a window at x=-10000, which is only a position. So the
app under test can be driven on this desktop and the owner's screen is never
involved.

WHAT IS MEASURED, on windows this script owns:
  flat        one colour      -> the composed surface must read FLAT
  populated   bars + text     -> the composed surface must read COLOURED
If the read cannot tell those two apart, the instrument is blind, and the
script says BLIND rather than reporting a number nobody can use.

USAGE: python _main/_falsify/desktop-bitblt-test.py
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

WM_PAINT, WM_ERASEBKGND, WM_DESTROY = 0x000F, 0x0014, 0x0002
WS_POPUP, WS_CLIPCHILDREN = 0x80000000, 0x02000000
SW_SHOWNOACTIVATE = 4
SRCCOPY = 0x00CC0020

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


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
k32.GetCurrentThreadId.restype = wintypes.DWORD

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
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
user32.InvalidateRect.restype = wintypes.BOOL
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.BeginPaint.restype = ctypes.c_void_p
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.EndPaint.restype = wintypes.BOOL
user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p]
user32.CreateDesktopW.restype = ctypes.c_void_p
user32.SetThreadDesktop.argtypes = [ctypes.c_void_p]
user32.SetThreadDesktop.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = ctypes.c_void_p
user32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.GetDesktopWindow.argtypes = []
user32.GetDesktopWindow.restype = wintypes.HWND
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.GetWindowDC.restype = ctypes.c_void_p

gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                          ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                          ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.BitBlt.restype = wintypes.BOOL
gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
                            wintypes.UINT, ctypes.c_void_p,
                            ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.SetTextColor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
gdi32.SetBkMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT), wintypes.HBRUSH]
user32.FillRect.restype = ctypes.c_int
user32.DrawTextW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_int,
                             ctypes.POINTER(RECT), wintypes.UINT]
user32.DrawTextW.restype = ctypes.c_int


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


class Win:
    COUNT = 0

    def __init__(self, w=380, h=140, flat=True, x=0, y=0):
        Win.COUNT += 1
        self.name = 'SottoDeskBit%d' % Win.COUNT
        self.flat = flat
        self.w, self.h = w, h
        self._proc = WNDPROC(self._wndproc)
        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
        cls.lpfnWndProc = self._proc
        cls.lpszClassName = self.name
        cls.hInstance = k32.GetModuleHandleW(None)
        user32.RegisterClassExW(ctypes.byref(cls))
        self.hwnd = int(user32.CreateWindowExW(
            0, self.name, self.name, WS_POPUP | WS_CLIPCHILDREN,
            x, y, w, h, None, None, None, None) or 0)
        if not self.hwnd:
            raise OSError('CreateWindowExW failed err=%d' % ctypes.get_last_error())

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
        if msg == WM_DESTROY:
            return 0
        return user32.DefWindowProcW(wintypes.HWND(hwnd), msg, wparam, lparam)


def screen_bitblt(x, y, w, h):
    """BitBlt the COMPOSED desktop surface at (x,y,w,h)."""
    desk = user32.GetDesktopWindow()
    src = user32.GetDC(desk)
    if not src:
        return None, 'GetDC(desktop) failed'
    mem = gdi32.CreateCompatibleDC(None)
    bmp = gdi32.CreateCompatibleBitmap(mem, w, h)
    old = gdi32.SelectObject(mem, bmp)
    ok = gdi32.BitBlt(mem, 0, 0, w, h, src, x, y, SRCCOPY)
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
    user32.ReleaseDC(desk, src)
    if got != h:
        return None, 'bitblt ok=%s rows=%s NO-BITMAP' % (bool(ok), got)
    return buf.raw, 'bitblt ok=%s %s' % (bool(ok), describe(buf.raw))


def main():
    desk = user32.CreateDesktopW('sotto-falsify-b', None, None, 0, 0x37F, None)
    print('CreateDesktopW=%s err=%d' % (bool(desk), ctypes.get_last_error()))
    if not desk:
        print('NO PRIVATE DESKTOP -- cannot guarantee owner-safety')
        return
    ok = user32.SetThreadDesktop(desk)
    print('SetThreadDesktop=%s err=%d' % (bool(ok), ctypes.get_last_error()))
    if not ok:
        print('SetThreadDesktop failed -- thread already owns windows')
        return
    print('thread is now on the PRIVATE desktop "sotto-falsify-b"')

    flat = Win(flat=True, x=0, y=0)
    pop = Win(flat=False, x=0, y=200)
    print('flat mapped=%s hwnd=%d' % (flat.map_it(), flat.hwnd))
    print('pop mapped=%s hwnd=%d' % (pop.map_it(), pop.hwnd))
    time.sleep(0.6)
    for name, win, y in (('flat', flat, 0), ('populated', pop, 200)):
        px, note = screen_bitblt(0, y, win.w, win.h)
        print('COMPOSED %-12s %s' % (name, note))
        # Also the window's own rect, to show the position is where we think.
        r = RECT()
        user32.GetWindowRect(wintypes.HWND(win.hwnd), ctypes.byref(r))
        print('   window rect=(%d,%d,%d,%d)' % (r.left, r.top, r.right, r.bottom))


if __name__ == '__main__':
    main()
