"""Does the DWM THUMBNAIL path read a window's COMPOSITED pixels here?

THE QUESTION. The author's instrument asks the window to paint itself
(`PrintWindow`). The composited pixels -- what the owner's eye would receive
-- come from the DWM's own redirection surface. `DwmRegisterThumbnail` asks the
DWM to render ANOTHER window's redirection surface into one of MY windows, and
that is the DWM's own composition, not the target's self-render.

WHY IT MATTERS HERE: Windows Graphics Capture (the other candidate) needs a
D3D11 device, and this box refuses to create one (measured: E_INVALIDPARAM
0x80070057 for every adapter and for HARDWARE/WARP/REFERENCE, at medium AND at
the owner's HIGH integrity). The DWM thumbnail API needs NO D3D11 device, so it
is the last compositor-side instrument left.

THE TWO ARMS, both on windows this script OWNS:
  source-populated   a window painted with bars and text
  source-flat        a window painted with one flat colour

If the read-out cannot tell those two apart, the instrument is blind and says
so -- a blank answer is not evidence.

USAGE:  python _main/_falsify/dwm-thumb-test.py
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

SIZE = wintypes.SIZE

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
    _fields_ = [('dwFlags', wintypes.DWORD),
                ('rcDestination', RECT),
                ('rcSource', RECT),
                ('opacity', wintypes.UINT),
                ('fVisible', wintypes.BOOL),
                ('fSourceHasAlpha', wintypes.BOOL)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


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
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
user32.InvalidateRect.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
dwmapi.DwmRegisterThumbnail.argtypes = [wintypes.HWND, wintypes.HWND,
                                       ctypes.POINTER(wintypes.HANDLE)]
dwmapi.DwmRegisterThumbnail.restype = ctypes.c_long
dwmapi.DwmUpdateThumbnailProperties.argtypes = [wintypes.HANDLE,
                                                ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES)]
dwmapi.DwmUpdateThumbnailProperties.restype = ctypes.c_long
dwmapi.DwmUnregisterThumbnail.argtypes = [wintypes.HANDLE]
dwmapi.DwmUnregisterThumbnail.restype = ctypes.c_long
dwmapi.DwmQueryThumbnailSourceSize.argtypes = [wintypes.HANDLE,
                                               ctypes.POINTER(SIZE)]
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
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteObject.restype = wintypes.BOOL
user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT), wintypes.HBRUSH]
user32.FillRect.restype = ctypes.c_int
gdi32.SetTextColor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
gdi32.SetTextColor.restype = wintypes.DWORD
gdi32.SetBkMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdi32.SetBkMode.restype = ctypes.c_int
user32.DrawTextW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_int,
                             ctypes.POINTER(RECT), wintypes.UINT]
user32.DrawTextW.restype = ctypes.c_int
gdi32.SetTextColor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
gdi32.SetBkMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.DrawTextW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_int,
                             ctypes.c_void_p, wintypes.UINT]
user32.DrawTextW.restype = ctypes.c_int


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('style', wintypes.UINT),
                ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int), ('hInstance', wintypes.HINSTANCE),
                ('hIcon', wintypes.HICON), ('hCursor', wintypes.HANDLE),
                ('hbrBackground', wintypes.HBRUSH),
                ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR),
                ('hIconSm', wintypes.HICON)]


class W:
    """A window we own. `flat` paints one colour; otherwise bars and text."""

    COUNT = 0

    def __init__(self, w=380, h=140, flat=True):
        W.COUNT += 1
        self.name = 'SottoThumb%d' % W.COUNT
        self.flat = flat
        self.w, self.h = w, h
        self._proc = WNDPROC(self._wndproc)
        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
        cls.lpfnWndProc = self._proc
        cls.lpszClassName = self.name
        import ctypes as _c
        k32 = _c.WinDLL('kernel32')
        k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        k32.GetModuleHandleW.restype = wintypes.HMODULE
        cls.hInstance = k32.GetModuleHandleW(None)
        user32.RegisterClassExW(ctypes.byref(cls))
        self.hwnd = int(user32.CreateWindowExW(
            0, self.name, self.name, WS_POPUP | WS_CLIPCHILDREN,
            -10000, -10000, w, h, None, None, cls.hInstance, None) or 0)
        user32.SetWindowPos(wintypes.HWND(self.hwnd), None, -10000, -10000,
                            w, h, 0x0040)
        user32.ShowWindow(wintypes.HWND(self.hwnd), SW_SHOWNOACTIVATE)
        user32.UpdateWindow(wintypes.HWND(self.hwnd))

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg in (WM_PAINT, WM_PRINT, WM_PRINTCLIENT):
            ps = PAINTSTRUCT()
            hdc = user32.BeginPaint(wintypes.HWND(hwnd), ctypes.byref(ps))
            r = RECT()
            user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(r))
            if self.flat:
                brush = gdi32.CreateSolidBrush(0x202020)
                user32.FillRect(hdc, ctypes.byref(r), brush)
                gdi32.DeleteObject(brush)
            else:
                for i in range(12):
                    left = 6 + i * 30
                    bar = RECT(left, 10 + (i % 4) * 20, left + 22,
                               24 + (i % 4) * 20)
                    brush = gdi32.CreateSolidBrush(0x30A0C0 + i * 0x0300)
                    user32.FillRect(hdc, ctypes.byref(bar), brush)
                    gdi32.DeleteObject(brush)
                gdi32.SetTextColor(hdc, 0xFFFFFF)
                gdi32.SetBkMode(hdc, 1)
                user32.DrawTextW(hdc, 'CONTENT FIRST', -1, ctypes.byref(r), 0)
            user32.EndPaint(wintypes.HWND(hwnd), ctypes.byref(ps))
            return 0
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_DESTROY:
            return 0
        return user32.DefWindowProcW(wintypes.HWND(hwnd), msg, wparam, lparam)


def describe(px):
    if not px:
        return 'EMPTY'
    sub = px[1::max(4, (len(px) // 4096) // 4 * 4)]
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


def read_dest(hwnd):
    r = RECT()
    user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return 'no-rect'
    mem = gdi32.CreateCompatibleDC(None)
    bmp = gdi32.CreateCompatibleBitmap(mem, w, h)
    old = gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(wintypes.HWND(hwnd), mem, PW_RENDERFULLCONTENT)
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
        return 'printwindow ok=%s rows=%s NO-BITMAP' % (bool(ok), got)
    return 'printwindow ok=%s %s' % (bool(ok), describe(buf.raw))


def arm(label, source):
    dest = W(w=380, h=140, flat=True)
    thumb = wintypes.HANDLE()
    hr = dwmapi.DwmRegisterThumbnail(wintypes.HWND(dest.hwnd),
                                     wintypes.HWND(source.hwnd),
                                     ctypes.byref(thumb))
    if hr != 0:
        print('%-16s DwmRegisterThumbnail hr=0x%08x' % (label, hr & 0xffffffff))
        return
    size = SIZE()
    hr2 = dwmapi.DwmQueryThumbnailSourceSize(thumb, ctypes.byref(size))
    props = DWM_THUMBNAIL_PROPERTIES()
    props.dwFlags = DWM_TNP_RECTDESTINATION | DWM_TNP_RECTSOURCE | \
        DWM_TNP_SOURCEOVERRIDE
    props.rcDestination = RECT(0, 0, dest.w, dest.h)
    props.rcSource = RECT(0, 0, source.w, source.h)
    props.opacity = 255
    props.fVisible = True
    props.fSourceHasAlpha = False
    hr3 = dwmapi.DwmUpdateThumbnailProperties(thumb, ctypes.byref(props))
    # Let the DWM composite it.
    import time
    time.sleep(0.6)
    user32.InvalidateRect(wintypes.HWND(dest.hwnd), None, True)
    user32.UpdateWindow(wintypes.HWND(dest.hwnd))
    time.sleep(0.4)
    print('%-16s reg=0x%08x querysize=0x%08x update=0x%08x srcsize=%dx%d'
          % (label, hr & 0xffffffff, hr2 & 0xffffffff, hr3 & 0xffffffff,
             size.cx, size.cy))
    print('%-16s DEST READ: %s' % ('', read_dest(dest.hwnd)))
    dwmapi.DwmUnregisterThumbnail(thumb)


def main():
    flat = W(flat=True)
    populated = W(flat=False)
    print('source flat hwnd=%d  source populated hwnd=%d'
          % (flat.hwnd, populated.hwnd))
    print('DIRECT READ of the populated source (PrintWindow): %s'
          % read_dest(populated.hwnd))
    arm('flat', flat)
    arm('populated', populated)


if __name__ == '__main__':
    main()
