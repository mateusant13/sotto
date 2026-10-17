"""NATIVE TRANSPARENT CAPTION OVERLAY (Win32 layered window + GDI+).

WHY THIS FILE EXISTS
--------------------
WebView2 cannot do per-pixel transparency inside pywebview's WinForms host:
`TransparencyKey` / `LWA_COLORKEY` on the parent cannot key the WebView2
child's opaque pixels (Microsoft WebView2Feedback #118 measured exactly that),
and pywebview documents `transparent` as not supported on Windows. The result
is a solid plate behind the words -- white, dark, or magenta depending on
which background is set.

The supported Windows mechanism for a true see-through overlay is a LAYERED
window updated with `UpdateLayeredWindow` and a 32-bit premultiplied ARGB DIB.
That is what this module does: GDI+ draws the caption text (white fill, black
stroke, green LED) onto a transparent bitmap, and Win32 composites it over the
desktop with per-pixel alpha. No WebView2, no colour key, no plate.

The window is:
  * `WS_EX_LAYERED` + `ULW_ALPHA`  -> per-pixel alpha
  * `WS_EX_TRANSPARENT`            -> clicks pass through to the video
  * `WS_EX_TOOLWINDOW`             -> no taskbar entry
  * `WS_EX_NOACTIVATE`             -> never steals focus
  * `WS_POPUP` + topmost           -> overlay
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes as wt

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_POPUP = 0x80000000
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
DIB_RGB_COLORS = 0
BI_RGB = 0


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte),
                ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte),
                ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG),
                ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


_user32 = ctypes.WinDLL('user32', use_last_error=True)
_gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT,
                             wt.WPARAM, wt.LPARAM)

_user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
_user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p]
_user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wt.UINT]
_user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
_user32.UpdateLayeredWindow.argtypes = [
    wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE),
    wt.HDC, ctypes.POINTER(wt.POINT), wt.DWORD,
    ctypes.POINTER(BLENDFUNCTION), wt.DWORD]
_user32.GetDC.argtypes = [wt.HWND]
_user32.GetDC.restype = wt.HDC
_user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
_user32.DestroyWindow.argtypes = [wt.HWND]
_user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
_user32.GetMessageW.restype = ctypes.c_int
_user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
_user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
_user32.DispatchMessageW.restype = ctypes.c_ssize_t
_user32.PostQuitMessage.argtypes = [ctypes.c_int]
_user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
_user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
_kernel32.GetCurrentThreadId.restype = wt.DWORD
_kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wt.HINSTANCE
_gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
_gdi32.CreateCompatibleDC.restype = wt.HDC
_gdi32.CreateDIBSection.argtypes = [
    wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
    ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
_gdi32.CreateDIBSection.restype = wt.HBITMAP
_gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
_gdi32.SelectObject.restype = wt.HGDIOBJ
_gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
_gdi32.DeleteDC.argtypes = [wt.HDC]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR),
                ("hIconSm", wt.HICON)]


def _premultiplied_bitmap(text, previous, width, height, scale):
    """Draw the caption onto a 32bpp premultiplied-ARGB bitmap (GDI+)."""
    import clr
    clr.AddReference("System.Drawing")
    from System.Drawing import (Bitmap, Graphics, Color, Font, FontStyle,
                                GraphicsUnit, Pen, SolidBrush, RectangleF,
                                StringFormat, StringAlignment)
    from System.Drawing.Imaging import PixelFormat
    from System.Drawing.Text import TextRenderingHint
    from System.Drawing.Drawing2D import (GraphicsPath, LineJoin,
                                          SmoothingMode)

    bmp = Bitmap(width, height, PixelFormat.Format32bppPArgb)
    g = Graphics.FromImage(bmp)
    g.Clear(Color.Transparent)
    g.SmoothingMode = SmoothingMode.AntiAlias
    g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit

    cur_px = max(16.0, 34.0 * scale)
    prev_px = max(12.0, 24.0 * scale)
    cur_font = Font("Segoe UI", cur_px, FontStyle.Bold, GraphicsUnit.Pixel)
    prev_font = Font("Segoe UI", prev_px, FontStyle.Bold, GraphicsUnit.Pixel)
    fmt = StringFormat()
    fmt.Alignment = StringAlignment.Center
    fmt.LineAlignment = StringAlignment.Center

    pad = int(14 * scale)
    led = int(10 * scale)
    gap = int(8 * scale)
    cur_h = int(cur_px * 1.35)
    prev_h = int(prev_px * 1.35) if previous else 0
    y = pad
    x0 = pad + led + gap
    inner_w = max(1, width - x0 - pad)

    def draw_line(s, font, color, top, h):
        brush = SolidBrush(color)
        path = GraphicsPath()
        rect = RectangleF(float(x0), float(top), float(inner_w), float(h))
        path.AddString(s, font.FontFamily, int(FontStyle.Bold), font.Size,
                       rect, fmt)
        pen = Pen(Color.FromArgb(255, 0, 0, 0), max(2.0, 6.0 * scale))
        pen.LineJoin = LineJoin.Round
        g.DrawPath(pen, path)
        g.FillPath(brush, path)
        path.Dispose()
        pen.Dispose()
        brush.Dispose()

    if previous:
        draw_line(previous, prev_font,
                  Color.FromArgb(215, 240, 245, 252), y, prev_h)
        y += prev_h
    if text:
        draw_line(text, cur_font, Color.FromArgb(255, 245, 248, 252),
                  y, cur_h)
        # The LED the panel's caption uses, at the left of the live line.
        cy = y + cur_h / 2.0
        g.FillEllipse(SolidBrush(Color.FromArgb(255, 55, 214, 122)),
                      float(pad), float(cy - led / 2.0),
                      float(led), float(led))
    # DEBUG only when asked: a rendered bitmap is the fastest way to tell
    # "GDI+ drew nothing" from "Win32 did not composite it".
    import os
    dbg = os.environ.get("SOTTO_CAPTION_OVERLAY_PNG")
    if dbg:
        try:
            from System.Drawing.Imaging import ImageFormat
            bmp.Save(dbg, ImageFormat.Png)
        except Exception:
            pass
    return bmp


class NativeCaptionOverlay:
    """A per-pixel-alpha caption window. No WebView2, no plate."""

    CLASS_NAME = "SottoNativeCaption"

    def __init__(self, log=None):
        self.log = log or (lambda msg: None)
        self.lock = threading.RLock()
        self.hwnd = None
        self.thread_id = None
        self.visible = False
        self.text = ""
        self.previous = ""
        self.scale = 1.0
        self.work = {"x": 0, "y": 0, "width": 1920, "height": 1080}
        self._wndproc = WNDPROC(self._on_message)
        self._ready = threading.Event()
        # THE WINDOW OWNS ITS OWN THREAD AND MESSAGE PUMP. Creating it on the
        # pywebview/WinForms UI thread meant every Win32 call from the caption
        # watcher blocked the UI thread (measured 2026-10-17: the UI thread
        # stopped pumping and `_ui` logged `UI_THREAD_STALL` for 10 s). A
        # dedicated owner is the standard shape for a topmost overlay and it
        # keeps the panel's WebView2 thread free.
        self._thread = threading.Thread(target=self._thread_main,
                                        name='sotto-caption-overlay', daemon=True)
        self._thread.start()
        self._ready.wait(5.0)

    def _thread_main(self):
        self.thread_id = int(_kernel32.GetCurrentThreadId())
        self._register()
        self._create()
        self._ready.set()
        if not self.hwnd:
            return
        msg = wt.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

    def _register(self):
        hinst = _kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0x0001 | 0x0002
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = self.CLASS_NAME
        atom = _user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            err = ctypes.get_last_error()
            if err not in (0, 1410):  # 1410 = class already registered
                self.log(f"CAPTION_OVERLAY_CLASS_FAILED error={err}")

    def _create(self):
        hinst = _kernel32.GetModuleHandleW(None)
        ex = (WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
              | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
        hwnd = _user32.CreateWindowExW(
            ex, self.CLASS_NAME, "Sotto caption", WS_POPUP,
            -4000, -4000, 900, 120, None, None, hinst, None)
        if not hwnd:
            self.log(f"CAPTION_OVERLAY_CREATE_FAILED error={ctypes.get_last_error()}")
            return
        self.hwnd = hwnd
        self.log(f"CAPTION_OVERLAY_CREATED hwnd={hwnd} layered=true "
                 f"transparent=true noactivate=true")

    def _on_message(self, hwnd, msg, wparam, lparam):
        if msg == 0x0010:  # WM_CLOSE
            _user32.DestroyWindow(hwnd)
            return 0
        if msg == 0x0002:  # WM_DESTROY
            _user32.PostQuitMessage(0)
            return 0
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def set_work_area(self, work, scale=1.0):
        self.work = dict(work or self.work)
        self.scale = float(scale or 1.0)

    def _measure(self, text, previous):
        """Width/height in physical pixels for the current text."""
        import clr
        clr.AddReference("System.Drawing")
        from System.Drawing import (Bitmap, Graphics, Font, FontStyle,
                                    GraphicsUnit, SizeF)
        scale = self.scale
        cur_px = max(16.0, 34.0 * scale)
        prev_px = max(12.0, 24.0 * scale)
        cur_font = Font("Segoe UI", cur_px, FontStyle.Bold, GraphicsUnit.Pixel)
        prev_font = Font("Segoe UI", prev_px, FontStyle.Bold, GraphicsUnit.Pixel)
        tmp = Bitmap(8, 8)
        g = Graphics.FromImage(tmp)
        max_text = max(200 * scale, self.work.get('width', 1920) * 0.92)
        pad = 14 * scale
        led = 10 * scale
        gap = 8 * scale
        side = pad + led + gap + pad
        def width_of(s, f):
            if not s:
                return 0.0
            return g.MeasureString(s, f).Width
        cur_w = width_of(text, cur_font)
        prev_w = width_of(previous, prev_font) if previous else 0.0
        text_w = min(max(cur_w, prev_w), max_text - side)
        width = int(max(240 * scale, text_w + side))
        h_cur = cur_px * 1.35
        h_prev = prev_px * 1.35 if previous else 0
        height = int(pad * 2 + h_prev + h_cur)
        g.Dispose(); tmp.Dispose()
        return max(1, width), max(1, height)

    def _update(self):
        if not self.hwnd:
            return False
        text = self.text or ""
        previous = self.previous or ""
        if not text and not previous:
            self.hide()
            return True
        width, height = self._measure(text, previous)
        bmp = _premultiplied_bitmap(text, previous, width, height, self.scale)
        try:
            from System.Drawing.Imaging import ImageLockMode, PixelFormat
            from System.Drawing import Rectangle
            data = bmp.LockBits(
                Rectangle(0, 0, width, height),
                ImageLockMode.ReadOnly, PixelFormat.Format32bppPArgb)
            stride = abs(int(data.Stride))
            size = stride * height
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = BI_RGB
            bits = ctypes.c_void_p()
            hdc_screen = _user32.GetDC(None)
            hdc_mem = _gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = _gdi32.CreateDIBSection(
                hdc_mem, ctypes.byref(bmi), DIB_RGB_COLORS,
                ctypes.byref(bits), None, 0)
            old = _gdi32.SelectObject(hdc_mem, hbmp)
            ctypes.memmove(bits, ctypes.c_void_p(int(data.Scan0.ToInt64())), size)
            bmp.UnlockBits(data)
            x = int(self.work.get('x', 0)
                    + (self.work.get('width', 1920) - width) / 2)
            y = int(self.work.get('y', 0) + self.work.get('height', 1080)
                    - height - 48 * self.scale)
            pt_dst = wt.POINT(x, y)
            size_dst = wt.SIZE(width, height)
            pt_src = wt.POINT(0, 0)
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
            ok = _user32.UpdateLayeredWindow(
                self.hwnd, hdc_screen, ctypes.byref(pt_dst),
                ctypes.byref(size_dst), hdc_mem, ctypes.byref(pt_src),
                0, ctypes.byref(blend), ULW_ALPHA)
            _gdi32.SelectObject(hdc_mem, old)
            _gdi32.DeleteObject(hbmp)
            _gdi32.DeleteDC(hdc_mem)
            _user32.ReleaseDC(None, hdc_screen)
            if not ok:
                self.log(f"CAPTION_OVERLAY_UPDATE_FAILED "
                         f"error={ctypes.get_last_error()} size={width}x{height}")
            return bool(ok)
        except Exception as exc:
            import traceback
            self.log(f"CAPTION_OVERLAY_RENDER_FAILED error={exc!r}\n"
                     f"{traceback.format_exc()}")
            return False
        finally:
            try:
                bmp.Dispose()
            except Exception:
                pass

    def set_text(self, text, previous=""):
        with self.lock:
            self.text = str(text or "")
            self.previous = str(previous or "")
            return self._update()

    def show(self, on=True):
        with self.lock:
            if not self.hwnd:
                return False
            if on:
                if not (self.text or self.previous):
                    return False
                self._update()
                _user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                                     | SWP_SHOWWINDOW)
                _user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
                self.visible = True
            else:
                _user32.ShowWindow(self.hwnd, SW_HIDE)
                self.visible = False
            return True

    def destroy(self):
        if self.hwnd:
            try:
                _user32.PostMessageW(self.hwnd, 0x0010, 0, 0)  # WM_CLOSE
            except Exception:
                pass
            self.hwnd = None
        if self._thread.is_alive():
            self._thread.join(2.0)


def probe(seconds=3.0):
    """Show one test caption so the transparency can be measured."""
    import time
    ov = NativeCaptionOverlay(log=lambda m: print(m, flush=True))
    ov.set_work_area({"x": 0, "y": 0, "width": 1920, "height": 1032}, 1.0)
    ov.set_text("Teste de legenda transparente", "")
    ov.show(True)
    time.sleep(seconds)
    ov.destroy()


if __name__ == "__main__":
    probe()
