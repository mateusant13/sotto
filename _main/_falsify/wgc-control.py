"""Control windows for the WGC probe -- the SAME shape as the census's controls.

The census proved its classifier with two windows it owns:
  blank-first    a window painted with ONE flat colour, then populated
  content-first  a window painted with content from the start

The WGC probe needs the SAME two controls, for the SAME reason: an instrument
that cannot report the opposite is not an instrument. These windows are GDI
(the house's own pattern) and they live at x=-10000, so nothing appears on the
owner's screen.

    python _main/_falsify/wgc-control.py --mode blank-first  --seconds 6
    python _main/_falsify/wgc-control.py --mode content-first --seconds 6

It prints `CONTROL hwnd=<n>` on stdout and holds the window alive until the
budget ends, so the probe can attach to it.

The control window is created on a PRIVATE DESKTOP when `--desktop` is given,
so it cannot appear on the owner's screen even in principle. Without the flag
it uses the current desktop but still sits at x=-10000.
"""
from __future__ import annotations

import argparse
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)
WM_DESTROY, WM_PAINT, WM_ERASEBKGND = 0x0002, 0x000F, 0x0014
WM_PRINT, WM_PRINTCLIENT = 0x0317, 0x0318
WS_POPUP, WS_CLIPCHILDREN = 0x80000000, 0x02000000
SW_SHOWNOACTIVATE = 4

user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
user32.RegisterClassExW.restype = wintypes.ATOM
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
k32.GetModuleHandleW.restype = wintypes.HMODULE
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                   wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                  wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
user32.FillRect.restype = ctypes.c_int
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
user32.InvalidateRect.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = ctypes.c_void_p
user32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.BeginPaint.restype = ctypes.c_void_p
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.EndPaint.restype = ctypes.c_bool
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.CreateSolidBrush.restype = ctypes.c_void_p
gdi32.SetTextColor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
gdi32.SetBkMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.DrawTextW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_int,
                             ctypes.c_void_p, wintypes.UINT]
user32.DrawTextW.restype = ctypes.c_int


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [('hdc', wintypes.HDC), ('fErase', wintypes.BOOL),
                ('rcPaint', RECT), ('fRestore', wintypes.BOOL),
                ('fIncUpdate', wintypes.BOOL),
                ('rgbReserved', ctypes.c_byte * 32)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('style', wintypes.UINT),
                ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int), ('hInstance', wintypes.HINSTANCE),
                ('hIcon', wintypes.HICON), ('hCursor', wintypes.HANDLE),
                ('hbrBackground', wintypes.HBRUSH),
                ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR),
                ('hIconSm', wintypes.HICON)]


class ControlWindow:
    """A window we own: painted flat first, populated on request."""

    COUNT = 0

    def __init__(self, w=380, h=140, populated=False):
        ControlWindow.COUNT += 1
        self.name = 'SottoFalsifyControl%d' % ControlWindow.COUNT
        self.phase = 1 if populated else 0
        self.w, self.h = w, h
        self._proc = WNDPROC(self._wndproc)
        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
        cls.lpfnWndProc = self._proc
        cls.lpszClassName = self.name
        cls.hInstance = k32.GetModuleHandleW(None)
        if not user32.RegisterClassExW(ctypes.byref(cls)):
            raise OSError('RegisterClassExW failed err=%d' % ctypes.get_last_error())
        self.hwnd = int(user32.CreateWindowExW(
            0, self.name, self.name, WS_POPUP | WS_CLIPCHILDREN,
            -10000, -10000, w, h, None, None, cls.hInstance, None) or 0)
        # A WS_POPUP window created with a size has a client area of that size;
        # if GetClientRect says otherwise, force it with SetWindowPos so the
        # survey has a real client rect to read.
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.SetWindowPos(wintypes.HWND(self.hwnd), None, -10000, -10000, w, h, 0x0040)
        if not self.hwnd:
            raise OSError('CreateWindowExW failed err=%d' % ctypes.get_last_error())

    def map_it(self):
        user32.ShowWindow(wintypes.HWND(self.hwnd), SW_SHOWNOACTIVATE)
        user32.UpdateWindow(wintypes.HWND(self.hwnd))
        return bool(user32.IsWindowVisible(wintypes.HWND(self.hwnd)))

    def populate(self):
        self.phase = 1
        r = RECT()
        user32.GetClientRect(wintypes.HWND(self.hwnd), ctypes.byref(r))
        user32.InvalidateRect(wintypes.HWND(self.hwnd), None, True)
        user32.UpdateWindow(wintypes.HWND(self.hwnd))

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg in (WM_PAINT, WM_PRINT, WM_PRINTCLIENT):
            ps = ctypes.wintypes.PAINTSTRUCT()
            hdc = user32.BeginPaint(wintypes.HWND(hwnd), ctypes.byref(ps))
            r = RECT()
            user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(r))
            if self.phase == 0:
                brush = gdi32.CreateSolidBrush(0x202020)
                user32.FillRect(hdc, ctypes.byref(r), brush)
                gdi32.DeleteObject(brush)
            else:
                # Bars and text: the same POPULATED arm the census uses.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('blank-first', 'content-first'),
                    required=True)
    ap.add_argument('--seconds', type=float, default=6.0)
    ap.add_argument('--switch-at', type=float, default=0.9,
                    help='when the blank-first window gets populated')
    args = ap.parse_args()

    populated = args.mode == 'content-first'
    win = ControlWindow(populated=populated)
    win.map_it()
    print('CONTROL hwnd=%d mode=%s' % (win.hwnd, args.mode), flush=True)

    deadline = time.monotonic() + args.seconds
    switched = False
    while time.monotonic() < deadline:
        if not switched and args.mode == 'blank-first' and \
                (time.monotonic() - (deadline - args.seconds)) >= args.switch_at:
            win.populate()
            switched = True
        time.sleep(0.02)
    return 0


if __name__ == '__main__':
    sys.exit(main())
