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
import json
import os
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


def _measure(text, px, cache, family='Segoe UI', weight=700, italic=False):
    """Width in px of `text` at `px`, measured by the renderer that draws it.

    `GraphicsPath.AddString` + `FillPath` is what paints the caption, so the width
    that decides a line break has to come from the same GDI+ engine. The tighter
    `StringFormat.GenericTypographic` measures ~4.7% smaller (measured 2026-10-17:
    683.32 px against 715.24 px for 20 W at 34 px), and that is GDI's opinion, not
    GDI+ path metrics -- break for one and draw with the other and the last letter
    gets clipped. Over-estimating is safe; clipping is not.

    THE CACHE IS NOT AN OPTIMISATION, IT IS CORRECTNESS. MEASURED 2026-10-17:
    with the `Graphics`/`Bitmap`/`Font` held only in the local scope of the factory,
    they are collected the moment it returns and the NEXT call raises
    `ArgumentException: Parametro invalido`. Default arguments pin them in the
    closure for the life of the function object.

    THE KEY CARRIES THE FACE, NOT ONLY THE SIZE. Before the theme reached this
    renderer the key was `round(px, 2)` and one global Segoe UI font; a caption
    that changed family would have been MEASURED with the previous theme's face
    and DRAWN with the new one -- line breaks that move the moment the colour
    changes. `family`/`bold`/`italic` are part of the identity of the closure.
    """
    import clr
    clr.AddReference('System.Drawing')
    from System.Drawing import Bitmap, Graphics, Font, FontStyle, GraphicsUnit
    key = (str(family), int(weight), bool(italic), round(float(px), 2))
    hit = cache.get(key)
    if hit is None:
        bmp = Bitmap(8, 8)
        g = Graphics.FromImage(bmp)
        font = _make_font(str(family), key[3], int(weight), bool(italic))

        def width_of(text, _g=g, _f=font):
            return 0.0 if not text else _g.MeasureString(text, _f).Width

        hit = width_of
        cache[key] = hit
    return hit


_MEASURE_CACHE = {}


# ═══════════════════════════════════════════════════════════════════════════
# THE BRAND CONTRACT — the panel's own live line, carried to the native overlay
# ═══════════════════════════════════════════════════════════════════════════
# WHY THIS LIVES IN PYTHON AND NOT IN CSS. The overlay the owner actually sees
# is a layered Win32 window painted by GDI+ (`_premultiplied_bitmap`), not
# `caption.html`. A theme that only edits the panel reaches half the product.
# The panel measures its OWN forming row (`captureBrandTokens` in
# `app/panel/brand-bridge.js`) and posts the result through
# `window.sotto.dispatch('brand-tokens', …)`; this table is the receiving end,
# and every field has a default that reproduces the pre-theme overlay EXACTLY.
_THEME_DEFAULT = {
    'theme': '',
    'fontFamily': 'Segoe UI',
    'livePx': 34.0,
    'prevPx': 24.0,
    'leading': 1.35,
    'prevLeading': 1.35,
    'liveWeight': 700,
    'prevWeight': 700,
    'liveItalic': False,
    'prevItalic': False,
    'liveUpper': False,
    'prevUpper': False,
    'liveColor': (245, 248, 252, 255),
    'prevColor': (240, 245, 252, 215),
    'strokeColor': (0, 0, 0, 255),
    'strokePx': 6.0,
    'plate': None,
    'plateRadius': 10.0,
    'ruleW': 0.0,
    'ruleColor': (0, 0, 0, 0),
    'led': (55, 214, 122, 255),
    'ledW': 10.0,
    'ledH': 10.0,
    'gap': 8.0,
    # (top, right, bottom, left)
    'pad': (14.0, 14.0, 14.0, 14.0),
    'align': 'center',
}


def _num(value, default):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if out != out or out in (float('inf'), float('-inf')):  # NaN/inf
        return float(default)
    return out


def _flag(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on', 'italic',
                                         'uppercase')
    return bool(value)


def _font_family(css):
    """`"Barlow Condensed", ui-sans-serif, sans-serif` -> `Barlow Condensed`.

    The first family is the design's choice; the rest are fallbacks the panel
    declares for the browser. GDI+ has one font, so it gets that one.
    """
    text = str(css or '').strip()
    if not text:
        return 'Segoe UI'
    first = text.split(',')[0].strip().strip('"').strip("'")
    return first or 'Segoe UI'


def _rgba(value, default=None):
    """A CSS colour -> `(r, g, b, a)` 0-255. Unknown -> `default`."""
    if value is None:
        return default
    # ALREADY NORMALISED. `_normalise_theme` is called more than once for the
    # same theme (the panel sends tokens, `_layout` and the bitmap each pass
    # them through again), so a `(r, g, b, a)` tuple has to survive a second
    # pass unchanged. Treating it as a CSS string silently dropped the plate
    # and the rule on the second call -- the overlay drew the default caption.
    if isinstance(value, (tuple, list)) and len(value) in (3, 4):
        try:
            vals = [max(0, min(255, int(round(float(v))))) for v in value]
        except (TypeError, ValueError):
            return default
        if len(vals) == 3:
            vals.append(255)
        return tuple(vals)
    text = str(value).strip()
    if not text or text in ('none', 'transparent', 'currentcolor'):
        return (0, 0, 0, 0) if text == 'transparent' else default
    if text.startswith('#'):
        h = text[1:]
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        if len(h) == 4:
            h = ''.join(c * 2 for c in h)
        if len(h) in (6, 8):
            try:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                a = int(h[6:8], 16) if len(h) == 8 else 255
                return (r, g, b, a)
            except ValueError:
                return default
    # CHROMIUM RESOLVES `color-mix()` AND `oklch()` TO `color(srgb …)`.
    # MEASURED 2026-10-21 on GlassCards: the row's computed `border-left-color`
    # arrived as `color(srgb 0.913725 0.658824 0.356863 / 0.3)`; an rgb()-only
    # parser dropped it and the overlay lost the design's rail. The values are
    # already sRGB components in 0..1.
    m = __import__('re').match(r'color\(\s*srgb\s+([^)]*)\)', text)
    if m:
        parts = [p for p in __import__('re').split(r'[\s,/]+', m.group(1).strip()) if p]
        try:
            vals = [max(0.0, min(1.0, float(p))) for p in parts[:3]]
            r, g, b = [int(round(v * 255)) for v in vals]
            a = 255
            if len(parts) > 3:
                raw = max(0.0, min(1.0, float(parts[3])))
                a = int(round(raw * 255))
            return (r, g, b, a)
        except (ValueError, IndexError):
            return default
    m = __import__('re').match(r'rgba?\(([^)]*)\)', text)
    if m:
        parts = [p for p in __import__('re').split(r'[\s,/]+', m.group(1).strip()) if p]
        try:
            r = int(round(float(parts[0])))
            g = int(round(float(parts[1])))
            b = int(round(float(parts[2])))
            a = 255
            if len(parts) > 3:
                raw = float(parts[3])
                a = int(round(raw * 255)) if raw <= 1.0 else int(round(raw))
            return (max(0, min(255, r)), max(0, min(255, g)),
                    max(0, min(255, b)), max(0, min(255, a)))
        except (ValueError, IndexError):
            return default
    return default


def _colour(t, fallback=(255, 255, 255, 255)):
    """A stored theme colour (already 0-255) -> GDI+ `Color`."""
    from System.Drawing import Color
    r, g, b, a = t
    return Color.FromArgb(int(a), int(r), int(g), int(b))


# ── THE FACES ────────────────────────────────────────────────────────────────
# The panel's fonts are woff2; GDI+ cannot open them. `make-overlay-fonts.py`
# converts them to TTF + `manifest.json` (the `@font-face` family, weight and
# style of each file). This resolver is the ONLY place the overlay chooses a
# face, so the measure and the draw can never pick different ones.
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
_FONT_INDEX = None
_FONT_FACES = {}


def _font_index():
    global _FONT_INDEX
    if _FONT_INDEX is None:
        index = {}
        try:
            with open(os.path.join(_FONT_DIR, 'manifest.json'),
                      encoding='utf-8') as fh:
                data = json.load(fh)
            for family, faces in (data.get('families') or {}).items():
                index[str(family).strip().lower()] = list(faces or [])
        except Exception:
            index = {}
        _FONT_INDEX = index
    return _FONT_INDEX


def _face_for(family, weight, italic):
    faces = _font_index().get(str(family or '').strip().lower())
    if not faces:
        return None
    pool = [f for f in faces if bool(f.get('italic')) == bool(italic)]
    if not pool:
        pool = faces
    weight = int(weight)
    return min(pool, key=lambda f: (abs(int(f.get('weight', 400)) - weight),
                                    0 if bool(f.get('italic')) == bool(italic) else 1))


def _private_family(face):
    key = str(face.get('file') or '')
    hit = _FONT_FACES.get(key)
    if hit is not None:
        return hit
    import clr
    clr.AddReference('System.Drawing')
    from System.Drawing.Text import PrivateFontCollection
    pfc = PrivateFontCollection()
    pfc.AddFontFile(os.path.join(_FONT_DIR, key))
    family = pfc.Families[0]
    # THE COLLECTION MUST OUTLIVE THE FAMILY. GDI+ returns a FontFamily owned by
    # the collection; letting the collection go leaves the Font pointing at
    # freed native memory -- the same lifetime trap `_measure` documents.
    hit = (family, pfc, face)
    _FONT_FACES[key] = hit
    return hit


def _make_font(family, px, weight, italic):
    """The ONE face factory: private TTF first, installed family second."""
    import clr
    clr.AddReference('System.Drawing')
    from System.Drawing import Font, FontStyle, GraphicsUnit
    weight = int(weight)
    face = _face_for(family, weight, italic)
    if face:
        try:
            fam, _pfc, chosen = _private_family(face)
            style = FontStyle.Regular
            # The FILE is the weight. Asking GDI+ for Bold on a 700 file would
            # embolden it a second time; asking for Bold on a 400 file is the
            # only way to honour a design whose 700 face is not in the panel.
            if weight >= 600 and int(chosen.get('weight', 400)) < 600:
                style = style | FontStyle.Bold
            if italic and not bool(chosen.get('italic')):
                style = style | FontStyle.Italic
            return Font(fam, px, style, GraphicsUnit.Pixel)
        except Exception:
            pass
    style = FontStyle.Regular
    if weight >= 600:
        style = style | FontStyle.Bold
    if italic:
        style = style | FontStyle.Italic
    try:
        return Font(str(family), px, style, GraphicsUnit.Pixel)
    except Exception:
        return Font('Segoe UI', px, style, GraphicsUnit.Pixel)


def _luminance(rgba):
    r, g, b = rgba[0], rgba[1], rgba[2]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _normalise_theme(tokens):
    """Panel tokens (CSS px) -> the overlay's own px, or an idempotent pass.

    THE 1.85 IS A SURFACE CONVERSION, NOT A STYLE CHOICE. The panel's live line
    is read at ~50 cm in a 380 px column; the overlay is a television caption
    read across the room. A 10.5 px broadcast row and a 34 px reading row are
    the SAME hierarchy in their own surfaces, so the overlay multiplies the
    panel size by one constant and clamps it to [21, 48]. Without the clamp a
    36 px design would draw a 66 px caption and a 10.5 px design would draw a
    19 px one, i.e. the theme would decide legibility instead of the product.
    """
    out = dict(_THEME_DEFAULT)
    if not tokens:
        return out
    src = dict(tokens)

    panel_live = src.get('panelLivePx')
    if panel_live is not None:
        pl = max(6.0, _num(panel_live, 18.5))
        live = max(21.0, min(48.0, pl * 1.85))
        ratio = live / pl
        # THE PREVIOUS LINE IS AN ECHO, NOT A SECOND HEADLINE. Designs whose
        # history and live line share a size (GlassCards 13/13) would otherwise
        # draw the previous caption at the live size; cap it at 0.78.
        prev = min(live * 0.78,
                   max(13.0, _num(src.get('panelPrevPx'), pl * 0.72) * ratio))
        pad = src.get('panelPad') or [10, 12, 10, 12]
        pad = tuple(max(0.0, _num(v, 10.0) * ratio) for v in pad)
        rule = max(0.0, _num(src.get('panelRuleW'), 0.0) * ratio)
        out['livePx'] = live
        out['prevPx'] = prev
        out['pad'] = pad
        out['ruleW'] = rule
    else:
        out['livePx'] = max(12.0, _num(src.get('livePx'), out['livePx']))
        out['prevPx'] = max(9.0, _num(src.get('prevPx'), out['prevPx']))
        pad = src.get('pad')
        if pad:
            out['pad'] = tuple(max(0.0, _num(v, 14.0)) for v in pad)
        out['ruleW'] = max(0.0, _num(src.get('ruleW'), out['ruleW']))

    if src.get('fontFamily'):
        out['fontFamily'] = _font_family(src['fontFamily'])
    out['theme'] = str(src.get('theme') or '')
    out['leading'] = max(0.9, min(2.4, _num(src.get('liveLeading'), 1.35)))
    out['prevLeading'] = max(0.9, min(2.4, _num(src.get('prevLeading'), 1.35)))
    out['liveWeight'] = int(max(100, min(900, _num(src.get('liveWeight'), 700))))
    out['prevWeight'] = int(max(100, min(900, _num(src.get('prevWeight'), 700))))
    out['liveItalic'] = _flag(src.get('liveItalic'), False)
    out['prevItalic'] = _flag(src.get('prevItalic'), False)
    out['liveUpper'] = _flag(src.get('liveUpper'), False)
    out['prevUpper'] = _flag(src.get('prevUpper'), False)

    ink = _rgba(src.get('liveColor'))
    if ink:
        # A DESIGN'S DIM INK IS A PANEL GESTURE. `text-white/45` over a dark
        # column reads as "not settled yet"; the same 45% over a video frame is
        # an unreadable caption. Hue is kept, alpha gets a floor.
        out['liveColor'] = (ink[0], ink[1], ink[2],
                            max(ink[3], 214))
    prev = _rgba(src.get('prevColor'))
    if prev:
        out['prevColor'] = (prev[0], prev[1], prev[2],
                            max(prev[3], 150))

    # A second pass carries `plate` (a tuple), not `rowBg` (the CSS string).
    plate = _rgba(src.get('rowBg')) or _rgba(src.get('plate'))
    if plate and plate[3] > 6 and str(src.get('rowBgImage') or 'none') == 'none':
        # `rowBg` is the EFFECTIVE colour (the bridge composites the row's wash
        # over the panel), so its own opacity is the overlay's opacity, not the
        # design's 7%. Legacy payloads without `rowBgAlpha` keep their own alpha.
        alpha = plate[3]
        if src.get('rowBgAlpha') is not None:
            alpha = int(round(max(0.0, min(1.0, _num(
                src.get('rowBgAlpha'), plate[3] / 255.0))) * 255))
        out['plate'] = (plate[0], plate[1], plate[2], max(alpha, 140))
        # A PLATE WITH NO PADDING PUTS THE TEXT ON ITS FIRST PIXEL (owner's
        # defect, measured in the first overlay stills: the row's own padding is
        # 0 in several designs and the plate is the trigger). The floor only
        # applies when a plate is actually drawn; a design with no plate keeps
        # its own zero padding so the caption stays optically centred.
        out['pad'] = tuple(max(10.0, v) for v in out['pad'])
    out['plateRadius'] = max(0.0, _num(src.get('rowRadius'), 10.0) *
                             (out['livePx'] / max(1.0, _num(panel_live, out['livePx']))))

    rule_col = _rgba(src.get('ruleColor'))
    if rule_col and rule_col[3] > 6 and out['ruleW'] > 0.2:
        # A 1-2 px rail at the design's own 30% is invisible over video. Keep
        # the hue, raise the alpha to a readable rail.
        out['ruleColor'] = (rule_col[0], rule_col[1], rule_col[2],
                            max(rule_col[3], 160))
    else:
        out['ruleW'] = 0.0
        out['ruleColor'] = (0, 0, 0, 0)

    # THREE INPUTS, ONE QUESTION: is the row's dot on? An explicit
    # `ledVisible` (panel tokens) wins, then an already-normalised `led`
    # tuple, then the default (on, as pre-brand overlay).
    if 'ledVisible' in src:
        led_on = _flag(src.get('ledVisible'), False)
    elif isinstance(src.get('led'), (tuple, list)):
        led_on = len(src['led']) == 4 and src['led'][3] > 6
    else:
        led_on = True
    if led_on:
        led = _rgba(src.get('led')) or _rgba(src.get('ledColor')) or _rgba(src.get('accent'))
        if led and led[3] > 6:
            out['led'] = (led[0], led[1], led[2], 255)
            out['ledW'] = max(4.0, min(18.0, _num(src.get('ledW'),
                                                   out['livePx'] * 0.22)))
            out['ledH'] = max(4.0, min(18.0, _num(src.get('ledH'),
                                                   out['ledW'])))
        else:
            out['led'] = None
            out['ledW'] = 0.0
            out['ledH'] = 0.0
    else:
        out['led'] = None
        out['ledW'] = 0.0
        out['ledH'] = 0.0
    # THE SECOND PASS CANNOT RECOVER THIS FROM `led is None` ALONE: a theme
    # that HAD a dot and one that never did both normalise to None. The marker
    # makes "off" explicit, so `_layout` and the bitmap keep agreeing after a
    # theme has been normalised twice (the panel -> shell -> layout path does).
    out['ledVisible'] = bool(out['led'])

    out['align'] = 'center' if str(src.get('textAlign') or '').startswith('center') else 'left'
    ink_final = out['liveColor']
    out['strokePx'] = max(2.0, out['livePx'] * 0.16)
    out['strokeColor'] = ((0, 0, 0, 235) if _luminance(ink_final) > 110
                          else (255, 255, 255, 235))
    return out


def _geom(scale, theme):
    """Every pixel both the layout and the bitmap must agree on, ONCE.

    `_layout` measures the box; `_premultiplied_bitmap` paints it. Two copies of
    "how much padding" is how a plate ends up drawn 4 px away from the text it
    is supposed to hold.
    """
    t = _normalise_theme(theme)
    cur_px = max(12.0, t['livePx'] * scale)
    prev_px = max(10.0, t['prevPx'] * scale)
    pad_t, pad_r, pad_b, pad_l = [v * scale for v in t['pad']]
    rule_w = t['ruleW'] * scale
    gap = t['gap'] * scale
    led_w = t['ledW'] * scale if t['led'] else 0.0
    led_h = t['ledH'] * scale if t['led'] else 0.0
    x_text = pad_l + (rule_w + gap if rule_w else 0.0)
    if led_w:
        x_text += led_w + gap
    return {
        't': t,
        'cur_px': cur_px,
        'prev_px': prev_px,
        'pad_t': pad_t, 'pad_r': pad_r, 'pad_b': pad_b, 'pad_l': pad_l,
        'rule_w': rule_w,
        'led_w': led_w, 'led_h': led_h,
        'gap': gap,
        'x_text': x_text,
        'line_h': cur_px * t['leading'],
        'prev_h': prev_px * t['prevLeading'],
        'align': t['align'],
    }


def _case(text, upper):
    return (text or '').upper() if upper else (text or '')

#: THE OWNER, 2026-10-17, verbatim: *"e a legenda ta do tamanho da tela. é pra tu
#: verificar online como quebrar de um jeito bom. ou como o youtube faz"*.
#:
#: A pesquisa deu o consenso de Netflix/TED/BBC/Section508/VEED: no maximo 2
#: linhas, ~42 caracteres por linha, quebrar apos pontuacao e antes de
#: conjuncao/preposicao, e a largura limitada a 68% de um quadro 16:9. Duas coisas
#: da pesquisa mudao a implementacao, e as duas estao escritas no modulo:
#: `caption_wrap.py`. O overflow -- o que nao cabe em duas linhas -- VOLTA ao
#: desenho em vez de ser cortado em silencio: uma frase truncada sem sinal e pior
#: do que uma frase partida.
try:
    import caption_wrap as _cw
except Exception:  # noqa: BLE001  -- a legenda nao pode partir por um import
    _cw = None


def _layout(text, previous, scale, work_width, theme=None):
    """ONE layout for the caption, used by the measure AND by the draw.

    Having two copies of "how many lines" is how a caption gets measured at one
    height and drawn at another. This returns everything both sides need:
    `(cur_lines, prev_line, width, height, scrolled)`.

    `scrolled` is the text that left the two-line window. It exists so the claim
    "no word is ever dropped" is CHECKABLE from the caller's side instead of
    being a promise in a comment -- see `wrap_tail` for the promise this finally
    keeps.

    MEASURED 2026-10-17 at Segoe UI Bold 34 px on this box: budget 727 px, the
    68% fraction of a 1920 px work area being 1305 px and the 42-character ceiling
    being the one that binds.

    `theme` is optional and defaults to the pre-brand overlay exactly. It carries
    the FACE as well as the size, because a theme may be a condensed or a serif
    caption and a line broken with Segoe UI's metrics is the wrong line for it.
    """
    g = _geom(scale, theme)
    t = g['t']
    cur_px, prev_px = g['cur_px'], g['prev_px']
    text = _case(text, t['liveUpper'])
    previous = _case(previous, t['prevUpper'])
    cur_family = t['fontFamily']
    cur_bold, prev_bold = t['liveWeight'] >= 600, t['prevWeight'] >= 600

    # `_measure` RETURNS A MEASURING FUNCTION (see its docstring: the closure
    # pins the GDI+ objects), so the call is two steps. Calling it once and
    # using the closure as a number is the bug this comment exists to prevent.
    def cur_w(s):
        return _measure(s, cur_px, _MEASURE_CACHE, cur_family, cur_bold,
                        t['liveItalic'])(s)

    def prev_w(s):
        return _measure(s, prev_px, _MEASURE_CACHE, cur_family, prev_bold,
                        t['prevItalic'])(s)

    budget = _cw.budget_px(work_width, cur_px, cur_w) if _cw else int(work_width * 0.5)

    # THE WINDOW SLIDES. This line used to be
    #
    #     cur_lines, _overflow = _cw.wrap(text or '', cur_w, budget)
    #
    # with the second value bound to an underscore and read NOWHERE, so every
    # word past the second line was simply never drawn -- silently, on every
    # caption that outgrew two lines. MEASURED 2026-10-18 on the owner's own
    # last 400 captions: 168 of them lost words, 772 words in total, the worst
    # losing 59 of its 68. Owner, verbatim: *"ta cortando palavras"*.
    #
    # `wrap_tail` keeps `MAX_LINES` at 2 -- the industry number, and the one the
    # owner asked for by name (*"verificar online como quebrar de um jeito bom.
    # ou como o youtube faz"*) -- and makes the two lines the LAST two, so the
    # newest words are the ones on screen and no word is ever simply lost.
    if _cw and '\n' not in text:
        cur_lines, scrolled = _cw.wrap_tail(text or '', cur_w, budget)
    else:
        cur_lines = text.splitlines() if '\n' in text else ([text] if text else [])
        scrolled = ''
    if not cur_lines:
        cur_lines = ['']

    # The previous line is ONE line, kept one back, and clamped to the same budget
    # so it can never be the wide one.
    prev_line = ''
    if previous:
        prev_line = (_cw.wrap(previous, prev_w, int(budget * 0.8))[0][0]
                     if _cw else previous)

    widest = max([cur_w(l) for l in cur_lines] + ([prev_w(prev_line)] if prev_line else [0]))
    max_text = max(1.0, work_width - g['x_text'] - g['pad_r'])
    # THE LAST GLYPH'S RIGHT SIDE. `MeasureString` and the `AddString`/`FillPath`
    # pair disagree by a few pixels on the final advance, and the bitmap is sized
    # from the measurement: the fresh 2026-10-21 GlassCards still read
    # `...em formaca` with the `o.` outside the bitmap. A trailing safety margin
    # is paid for in plate width, never in a lost word.
    safety = max(18.0, cur_px * 0.9)
    width = int(max(240 * scale, min(widest + g['x_text'] + g['pad_r'] + safety, max_text)))
    height = int(g['pad_t'] + g['pad_b'] + g['line_h'] * len(cur_lines) + (g['prev_h'] if prev_line else 0))
    return cur_lines, prev_line, max(1, width), max(1, height), scrolled


def _premultiplied_bitmap(cur_lines, prev_line, width, height, scale, theme=None):
    """Draw the caption onto a 32bpp premultiplied-ARGB bitmap (GDI+).

    THE THEME IS PAINTED, NOT APPLIED BY CSS. A plate is the row's own
    `backgroundColor` (rounded by its `border-radius`), the rule is its
    `border-left`, and the text is the row's computed face/ink. Values arrive
    from `brand-bridge.js` and are normalised by `_normalise_theme`; with no
    theme this function reproduces the 2026-10-18 overlay pixel for pixel.
    """
    import clr
    clr.AddReference("System.Drawing")
    from System.Drawing import (Bitmap, Graphics, Color, Font, FontStyle,
                                GraphicsUnit, Pen, SolidBrush, RectangleF,
                                StringFormat, StringAlignment, StringFormatFlags)
    from System.Drawing.Imaging import PixelFormat
    from System.Drawing.Text import TextRenderingHint
    from System.Drawing.Drawing2D import (GraphicsPath, LineJoin,
                                          SmoothingMode)

    geo = _geom(scale, theme)
    t = geo['t']
    bmp = Bitmap(width, height, PixelFormat.Format32bppPArgb)
    g = Graphics.FromImage(bmp)
    g.Clear(Color.Transparent)
    g.SmoothingMode = SmoothingMode.AntiAlias
    g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit

    cur_font = _make_font(t['fontFamily'], geo['cur_px'], t['liveWeight'],
                          t['liveItalic'])
    prev_font = _make_font(t['fontFamily'], geo['prev_px'], t['prevWeight'],
                           t['prevItalic'])
    fmt = StringFormat()
    fmt.Alignment = (StringAlignment.Center if t['align'] == 'center'
                     else StringAlignment.Near)
    fmt.LineAlignment = StringAlignment.Center
    # The lines are ALREADY wrapped by `caption_wrap`; letting AddString wrap a
    # second time would break at a different word and disagree with the box.
    fmt.FormatFlags = StringFormatFlags.NoWrap

    # ── the plate ────────────────────────────────────────────────────────────
    if t['plate'] and t['plate'][3] > 0:
        radius = max(0.0, min(float(t['plateRadius']) * scale,
                              min(width, height) / 2.0))
        plate = GraphicsPath()
        if radius <= 0.5:
            plate.AddRectangle(RectangleF(0.0, 0.0, float(width), float(height)))
        else:
            d = radius * 2.0
            plate.AddArc(0.0, 0.0, d, d, 180.0, 90.0)
            plate.AddArc(width - d, 0.0, d, d, 270.0, 90.0)
            plate.AddArc(width - d, height - d, d, d, 0.0, 90.0)
            plate.AddArc(0.0, height - d, d, d, 90.0, 90.0)
            plate.CloseFigure()
        brush = SolidBrush(_colour(t['plate']))
        g.FillPath(brush, plate)
        brush.Dispose()
        plate.Dispose()

    # ── the rule (the row's border-left) ─────────────────────────────────────
    if geo['rule_w'] > 0.1 and t['ruleColor'][3] > 0:
        brush = SolidBrush(_colour(t['ruleColor']))
        g.FillRectangle(brush, 0.0, 0.0, float(geo['rule_w']), float(height))
        brush.Dispose()

    def draw_line(s, font, color, top, h):
        brush = SolidBrush(_colour(color))
        path = GraphicsPath()
        rect = RectangleF(float(geo['x_text']), float(top),
                          float(max(1, width - geo['x_text'] - geo['pad_r'])),
                          float(h))
        path.AddString(s, font.FontFamily, int(font.Style), font.Size,
                       rect, fmt)
        pen = Pen(_colour(t['strokeColor']),
                  max(1.5, float(t['strokePx']) * scale))
        pen.LineJoin = LineJoin.Round
        g.DrawPath(pen, path)
        g.FillPath(brush, path)
        path.Dispose()
        pen.Dispose()
        brush.Dispose()

    y = float(geo['pad_t'])
    if prev_line:
        draw_line(prev_line, prev_font, t['prevColor'], y, geo['prev_h'])
        y += geo['prev_h']
    for line in cur_lines:
        draw_line(_case(line, t['liveUpper']), cur_font, t['liveColor'],
                  y, geo['line_h'])
        y += geo['line_h']

    # The design's own mark: an LED/rail on the left, or nothing when the row
    # hides `.caption__led` (the token says so; it is not guessed from the theme
    # name).
    if geo['led_w'] and cur_lines and cur_lines[0]:
        led_x = geo['x_text'] - geo['led_w'] - geo['gap']
        # BESIDE THE LIVE LINE, NOT BESIDE THE PREVIOUS ONE. With a previous
        # line above, the old `pad + h/2` put the "listening" dot at the
        # previous line's shoulder; the dot belongs to what is being said now.
        cy = (geo['pad_t'] + (geo['prev_h'] if prev_line else 0.0)
              + geo['line_h'] / 2.0)
        brush = SolidBrush(_colour(t['led']))
        g.FillEllipse(brush, float(led_x), float(cy - geo['led_h'] / 2.0),
                      float(geo['led_w']), float(geo['led_h']))
        brush.Dispose()
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


#: ONE WORD EVERY THIS MANY SECONDS. 0.045 s is the same cadence `panel.css`
#: already uses for the panel's own `--type-step`, so the live caption and the
#: panel sprout at ONE speed and the owner does not have to learn two rhythms.
#: It is a module constant on purpose: a word arriving every 45 ms is 22 words
#: per second, faster than anyone speaks, so the reveal finishes inside the
#: engine's own cadence instead of lagging it.
WORD_STEP_S = 0.045


def _same_line(old, new):
    """Is `new` still the SAME caption as `old`, even if words were rewritten?

    THE FIRST WORD IS THE WHOLE TEST. Matching the whole prefix would say "no"
    the moment the model firms up or corrects a single word, and the sprout
    would restart on every partial -- the "blinked and retyped on every fragment"
    failure `panel.js` documents for the letter reveal.

    The cost of this looseness is honest and small: if the next caption happens
    to begin with the same word ("obrigado" then "obrigado por tudo"), the
    sprout still runs in order -- the shared word is already out and the rest
    appear one at a time behind it. Nothing is hidden and nothing is reordered.
    """
    ow, nw = (old or "").split(), (new or "").split()
    if not ow or not nw:
        return not ow and not nw
    return ow[0] == nw[0]


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
        # THE DESIGN THE PANEL IS WEARING RIGHT NOW. Default == the overlay that
        # shipped before the brand contract existed (Segoe UI 34 px, green dot),
        # so a panel that never posts tokens loses nothing.
        self.theme = dict(_THEME_DEFAULT)
        self._wndproc = WNDPROC(self._on_message)
        self._ready = threading.Event()
        # ── THE WORD-BY-WORD SPROUT (2026-10-18) ────────────────────────────
        # `_shown` is how many words of `self.text` are ACTUALLY on screen. It
        # is the whole feature: before it, `_update` painted the entire forming
        # line in one `UpdateLayeredWindow`, so a fragment carrying three words
        # put three words on screen in the same frame. Owner, verbatim:
        # *"ta surgindo duas palavras ou mais na legenda, inves de uma por vez"*
        # and *"nao e revelar por letra. e pra brotar palavra por palavra"*.
        #
        # `_reveal_gen` is the generation counter that retires a timer which is
        # already armed when the line it belongs to is gone -- the same "decide
        # at RUN time, not by cancelling the Timer" trick `_hotkey_single` uses
        # in the shell, because a Timer may already be inside `_update`.
        self._shown = 0
        self._n = 0
        self._reveal_timer = None
        self._reveal_gen = 0
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

    def set_theme(self, tokens=None):
        """Wear a design: the panel's own live row decides the overlay's face.

        CALLED FROM THE SHELL, ON THE PANEL'S PUSH. The measurement happens in
        the document (`brand-bridge.js`) because only the document knows what
        CSS actually resolved to -- family fallbacks, `color-mix`, the owner's
        caption-scale dial. This side only sanitises and caches.
        """
        theme = _normalise_theme(tokens)
        with self.lock:
            self.theme = theme
            # The measure cache is keyed by face+size, so a new theme is a new
            # key and does not need eviction; clearing it is about the SIZE
            # going down (a 10.5 px theme would otherwise keep hundreds of
            # measured strings for a size no other theme uses).
            _MEASURE_CACHE.clear()
            if self.hwnd and (self.text or self.previous):
                self._update()
        self.log('CAPTION_OVERLAY_THEME name=%s font=%s live=%.1f prev=%.1f '
                 'plate=%s rule=%.1f led=%s align=%s'
                 % (theme.get('theme') or '-', theme.get('fontFamily'),
                    theme.get('livePx'), theme.get('prevPx'),
                    'yes' if theme.get('plate') else 'no',
                    theme.get('ruleW') or 0.0,
                    'yes' if theme.get('led') else 'no', theme.get('align')))
        return dict(theme)

    def _measure(self, text, previous):
        """Width/height for the current text. ONE layout, shared with the draw."""
        _lines, _prev, width, height, _scrolled = _layout(
            text, previous, self.scale, self.work.get('width', 1920),
            self.theme)
        return width, height

    def _update(self):
        if not self.hwnd:
            return False
        # NOT `self.text`: the sprout decides how much of it is out. This one
        # line is the entire difference between "three words in one frame" and
        # "three words, one at a time".
        text = self._display_text()
        previous = self.previous or ""
        if not text and not previous:
            self.hide()
            return True
        # ONE layout, computed once, handed to the bitmap. Two copies of "how many
        # lines" is how a caption gets measured at one height and drawn at another.
        cur_lines, prev_line, width, height, _scrolled = _layout(
            text, previous, self.scale, self.work.get('width', 1920),
            self.theme)
        bmp = _premultiplied_bitmap(cur_lines, prev_line, width, height,
                                    self.scale, self.theme)
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

    def set_text(self, text, previous="", instant=False):
        """One caption. `instant=True` skips the sprout (the standalone probe).

        THE REVEAL'S FOUR RULES, each with a reason:

        * THE FIRST WORD IS SHOWN IN THIS CALL, not after a tick, so the caption
          answers Alt+C in the same frame instead of 45 ms later.
        * A REWRITE DOES NOT RESTART ANYTHING. `panel.js` named the alternative
          exactly: *"a word that blinked and retyped on every fragment would be
          worse than no reveal at all"*. `_same_line` compares the FIRST word and
          nothing else -- comparing the whole prefix would restart the sprout on
          every single rewrite, which is precisely the bug.
        * A NEW LINE RESTSARTS AT 1, so the next sentence sprouts from its start.
        * A TAIL THAT SHRANK CANNOT SHOW WORDS THAT NO LONGER EXIST, hence the
          `min`.
        """
        with self.lock:
            self.previous = str(previous or "")
            full = str(text or "")
            words = full.split()
            if _same_line(self.text, full):
                self._shown = min(self._shown, len(words))
            else:
                self._shown = 1 if words else 0
            self.text = full
            self._n = len(words)
            if instant:
                self._shown = self._n
                self._arm_reveal()
            else:
                self._arm_reveal()
            return self._update()

    # ── THE SPROUT ITSELF ───────────────────────────────────────────────────
    def _display_text(self):
        """What is actually drawn: the first `_shown` words of the line."""
        return self.text if self._shown >= self._n else " ".join(
            (self.text or "").split()[:max(0, self._shown)])

    def _arm_reveal(self):
        """(Re)arm one tick. No-op when the whole line is already out."""
        if self._shown >= self._n:
            self._reveal_timer = None
            return
        self._reveal_gen += 1
        gen = self._reveal_gen
        t = threading.Timer(WORD_STEP_S, lambda: self._reveal_tick(gen))
        t.daemon = True
        self._reveal_timer = t
        t.start()

    def _reveal_tick(self, gen):
        try:
            with self.lock:
                if gen != self._reveal_gen or self._shown >= self._n:
                    return
                self._shown += 1
                self._update()
                more = self._shown < self._n
            if more:
                self._arm_reveal()
        except Exception as exc:  # noqa: BLE001 -- see the fail-open rule
            self._fail_open(exc)

    def _fail_open(self, exc):
        """A broken sprout must never freeze the caption on one word.

        The reveal is a nicety; the caption is the product. So any error in the
        tick puts EVERY word out at once and repaints, which is exactly the
        behaviour the product had before this feature existed.
        """
        try:
            with self.lock:
                self._shown = self._n
                self._update()
            self.log(f"CAPTION_REVEAL_FAILED_OPEN error={exc!r} "
                     f"shown={self._n}")
        except Exception as exc2:  # noqa: BLE001
            self.log(f"CAPTION_REVEAL_FAILED_OPEN error={exc2!r}")

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
        # The timer chain is daemonic, but retiring it here means a destroyed
        # overlay cannot try to `_update` a window handle that is already gone.
        with self.lock:
            self._reveal_gen += 1
            self._reveal_timer = None
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
    # `instant=True`: the probe exists to measure the transparency of a real
    # sentence, not to watch a sprout, and 45 ms per word would show one word.
    ov.set_text("Teste de legenda transparente", "", instant=True)
    ov.show(True)
    time.sleep(seconds)
    ov.destroy()


if __name__ == "__main__":
    probe()
