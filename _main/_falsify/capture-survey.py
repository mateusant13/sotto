"""Which capture path actually reads pixels here? A survey, not a guess.

PrintWindow(PW_RENDERFULLCONTENT) is the AUTHOR's path and is NOT up for
re-use. This probes the OTHER paths the brief names, on the SAME window, and
prints what each one returns:

  printwindow_client   PrintWindow(hwnd, hdc, PW_CLIENTONLY)          [different flags]
  wm_printclient       WM_PRINTCLIENT sent to the window's wndproc      [different message]
  wm_print             WM_PRINT sent to the window's wndproc           [different message]
  bitblt_screen        BitBlt from the screen DC (needs the window ON screen)

For each path it prints the distinct-colour count and the std/spread over the
client area, so "it returned nothing" is a NUMBER, not a shrug.

USAGE:  python _main/_falsify/capture-survey.py <hwnd>
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002
WM_PRINT = 0x0317
WM_PRINTCLIENT = 0x0318
SRCCOPY = 0x00CC0020


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


user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.GetWindowDC.restype = ctypes.c_void_p
user32.GetDesktopWindow.argtypes = []
user32.GetDesktopWindow.restype = wintypes.HWND
user32.GetDC.restype = ctypes.c_void_p
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = ctypes.c_void_p
user32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.PrintWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                ctypes.c_void_p]
user32.SendMessageW.restype = ctypes.c_ssize_t
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
gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                          ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                          ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.BitBlt.restype = wintypes.BOOL
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.GetWindowDC.restype = ctypes.c_void_p
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]


def describe(px, w, h):
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
    return ('distinct=%d std=%.2f spread=%d mean=%.1f' %
            (len(colours), std, spread, mean))


def grab(hwnd, mode):
    r = RECT()
    hh = wintypes.HWND(int(hwnd))
    if not user32.GetClientRect(hh, ctypes.byref(r)):
        return 'no-rect err=%d' % ctypes.get_last_error()
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return 'no-size'
    mem = gdi32.CreateCompatibleDC(None)
    bmp = gdi32.CreateCompatibleBitmap(mem, w, h)
    old = gdi32.SelectObject(mem, bmp)
    note = ''
    if mode == 'printwindow_client':
        ok = user32.PrintWindow(hh, mem, PW_CLIENTONLY)
        note = 'ok=%s' % bool(ok)
    elif mode == 'printwindow_full':
        ok = user32.PrintWindow(hh, mem, PW_RENDERFULLCONTENT)
        note = 'ok=%s' % bool(ok)
    elif mode == 'wm_printclient':
        res = user32.SendMessageW(hh, WM_PRINTCLIENT,
                                  wintypes.WPARAM(mem), wintypes.LPARAM(0))
        note = 'ret=%s' % res
    elif mode == 'wm_print':
        res = user32.SendMessageW(hh, WM_PRINT,
                                  wintypes.WPARAM(mem), wtypes.LPARAM(0))
        note = 'ret=%s' % res
    elif mode == 'printwindow_none':
        ok = user32.PrintWindow(hh, mem, 0)
        note = 'ok=%s' % bool(ok)
    elif mode == 'getdc_bitblt':
        src = user32.GetDC(hh)
        ok = gdi32.BitBlt(mem, 0, 0, w, h, src, 0, 0, SRCCOPY)
        user32.ReleaseDC(hh, src)
        note = 'ok=%s' % bool(ok)
    elif mode == 'bitblt_windowdc':
        src = user32.GetWindowDC(hh)
        ok = gdi32.BitBlt(mem, 0, 0, w, h, src, 0, 0, SRCCOPY)
        user32.ReleaseDC(hh, src)
        note = 'ok=%s' % bool(ok)
    else:
        note = 'unknown-mode'
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
        return '%s rows=%s NO-BITMAP' % (note, got)
    return '%s %s' % (note, describe(buf.raw, w, h))


def main():
    hwnd = int(sys.argv[1])
    print('hwnd=%d' % hwnd)
    for mode in ('printwindow_full', 'printwindow_none', 'printwindow_client',
                 'wm_printclient', 'wm_print', 'getdc_bitblt',
                 'bitblt_windowdc'):
        print('%-18s %s' % (mode, grab(hwnd, mode)))


if __name__ == '__main__':
    main()
