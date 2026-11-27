"""Monitor and display geometry for the WebView2 shell (S1 of revival/SPLIT-PLAN.md).

Everything below used to be a top-level block of `sotto_webview.py` (`:3412-3750`).
It is lifted here so the shell stops carrying a second copy of the Win32 geometry
vocabulary, and so `_main/multi-monitor-oracle.py` can AST-extract the PURE
selector from the shipped module without importing the shell and opening a window.

`select_display_for_point` stays PURE: it reads no Win32 handle, file or shell
state. `target_placement` is the Win32 probe around it, and `primary_display`
is the historical docked-startup fallback. The shell re-exports every name, so
its call sites are unchanged.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

from win32_types import POINT, RECT

#: The shell builds its own `user32` WinDLL at shell scope; this module owns one
#: too. Passing the shell's handle in would mean threading a parameter through
#: eight functions and every call site, and importing the shell from here would
#: be circular (the shell imports this module). A second WinDLL for the same
#: process-wide library is cheap, and `ctypes.get_last_error()` is thread-local
#: rather than per-WinDLL, so the WinError paths keep working unchanged.
user32 = ctypes.WinDLL('user32', use_last_error=True)

#: Both Win32 flags belong to the functions below (`primary_display`,
#: `_selection_monitors_and_primary`, `target_placement`), so they moved with
#: them instead of being duplicated here and at shell scope.
MONITOR_DEFAULTTOPRIMARY = 0x00000001
MONITOR_DEFAULTTONEAREST = 0x00000002


class MONITORINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_ulong), ('rcMonitor', RECT),
                ('rcWork', RECT), ('dwFlags', ctypes.c_ulong)]


def dpi_scale() -> float:
    """Physical pixels per DIP for this process.

    pywebview marks the process System-DPI-aware (winforms.py:820), so one DIP
    is `dpi/96` physical pixels and the work area has to be divided back before
    it is compared with Electron's DIP numbers. On this host it is 1.0 (Electron
    logged scaleFactor=1), which is why the two arms agree.
    """
    try:
        dpi = user32.GetDpiForSystem()
    except AttributeError:  # pragma: no cover - pre-1607 Windows
        return 1.0
    return (dpi / 96.0) if dpi else 1.0


_SHCORE = None


def _shcore():
    """`shcore` loaded ONCE, with the prototype set once.

    MEASURED 2026-11-25 (reviewer finding): `_monitor_scale` runs on the caption
    path, which asks for geometry up to 240 times a second, and it built a fresh
    `ctypes.WinDLL('shcore')` -- a LoadLibrary plus three argtype assignments --
    on every call. The library is process-wide and its prototype never changes,
    so it is loaded lazily and kept. `None` means "this Windows has no shcore",
    which is also a fact worth caching once.
    """
    global _SHCORE
    if _SHCORE is None:
        try:
            lib = ctypes.WinDLL('shcore', use_last_error=True)
            lib.GetDpiForMonitor.argtypes = [
                ctypes.c_void_p, ctypes.c_int,
                ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
            lib.GetDpiForMonitor.restype = ctypes.c_long
            _SHCORE = lib
        except Exception:  # noqa: BLE001
            _SHCORE = False          # tried, unavailable; do not retry per frame
    return _SHCORE or None


def _monitor_scale(handle) -> float:
    """Per-monitor DPI, falling back to the process DPI when shcore refuses.

    `dpi_scale()` is the SYSTEM DPI (GetDpiForSystem). On a two-monitor desk
    with different scaling that number is right for exactly one of them, so a
    window docked to the other monitor lands at the wrong physical size. The
    owner's report (2026-10-17) is that every panel spawns in the wrong place
    and "em diferentes monitores faria pior ainda"; this is that defect.
    """
    try:
        shcore = _shcore()
        if shcore is not None:
            dx = ctypes.c_uint(0)
            dy = ctypes.c_uint(0)
            if shcore.GetDpiForMonitor(handle, 0, ctypes.byref(dx),
                                       ctypes.byref(dy)) == 0 and dx.value:
                return dx.value / 96.0
    except Exception:  # noqa: BLE001
        pass
    return dpi_scale()


def _selection_monitor(handle) -> dict:
    """One monitor in BOTH coordinate spaces: physical (selection) and DIP (layout).

    Win32 reports the virtual screen in PHYSICAL pixels, with negative x for a
    monitor left of the primary. `_display_for_monitor` divides by THIS
    monitor's scale to get the DIP rect WebView2 uses; `MonitorFromPoint`
    compares against the raw rect. Keeping both views of the same monitor is
    what lets selection stay pure without scaling any number twice.
    """
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(handle, ctypes.byref(mi)):
        raise ctypes.WinError(ctypes.get_last_error())
    scale = _monitor_scale(handle)

    def physical(r):
        return {'x': int(r.left), 'y': int(r.top),
                'width': int(r.right - r.left),
                'height': int(r.bottom - r.top)}

    def dip(r):
        return {'x': round(r.left / scale), 'y': round(r.top / scale),
                'width': round((r.right - r.left) / scale),
                'height': round((r.bottom - r.top) / scale)}

    return {
        'handle': handle,
        'scaleFactor': scale,
        'bounds': physical(mi.rcMonitor),
        'workArea': physical(mi.rcWork),
        'display': {
            'handle': handle,
            'bounds': dip(mi.rcMonitor),
            'workArea': dip(mi.rcWork),
            'scaleFactor': scale,
        },
    }


def _display_for_monitor(handle) -> dict:
    """The Electron-shaped DIP view of one monitor (one GetMonitorInfo source)."""
    return _selection_monitor(handle)['display']


def primary_display() -> dict:
    """Primary display bounds + work area, in DIP, the shape Electron reports.

    Kept ONLY for the docked panel's startup geometry (`compute_geometry`) and
    as the last-resort fallback when no monitor can be probed. The strip and
    overlay choose their monitor in `select_display_for_point`, never here.
    """
    handle = user32.MonitorFromPoint(POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)
    return _display_for_monitor(handle)


def select_display_for_point(point, monitors, primary_index=0, geometry=None):
    """PURE: which monitor owns `point`, and a rect clamped to ITS work area.

    `point` is a PHYSICAL virtual-screen `(x, y)` (negative x is a monitor to
    the LEFT of the primary, as Win32 reports it). `monitors` is a sequence of
    dicts with physical `bounds` / `workArea` rects (`x`,`y`,`width`,`height`)
    and a `scaleFactor` (physical px per DIP); `primary_index` names the
    fallback. Selection mirrors `MonitorFromPoint`: containment first,
    MONITOR_DEFAULTTONEAREST when no monitor contains the point, then primary
    when there is nothing to choose from (including an empty monitor list).

    `geometry`, when given, is a requested rect in DIP. It is converted to
    PHYSICAL ONCE (multiply by the chosen monitor's scale), clamped into that
    monitor's WORK AREA -- never its full bounds -- and converted back to DIP
    ONCE. Extra keys of an input dict (`workX`, `docked`, `surface`, ...) travel
    with it. No Win32 call, no file, no shell state: an oracle can own this.
    """
    def num(value, default=0.0):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return default
        return v if v == v and abs(v) != float('inf') else default

    def rect(shape):
        shape = shape if isinstance(shape, dict) else {}
        return (num(shape.get('x')), num(shape.get('y')),
                max(0.0, num(shape.get('width'))),
                max(0.0, num(shape.get('height'))))

    items = list(monitors) if monitors else []
    xy = None
    if isinstance(point, dict):
        xy = (num(point.get('x')), num(point.get('y')))
    else:
        try:
            xy = (num(point[0]), num(point[1]))
        except (TypeError, ValueError, IndexError, KeyError):
            xy = None

    index, reason, best = None, 'primary', None
    primary = int(num(primary_index, 0))
    if items:
        for idx, mon in enumerate(items):
            x, y, w, h = rect(mon.get('bounds'))
            if xy is not None and x <= xy[0] < x + w and y <= xy[1] < y + h:
                index, reason = idx, 'point'
                break
            if xy is None:
                continue
            dx = max(x - xy[0], 0.0, xy[0] - (x + w))
            dy = max(y - xy[1], 0.0, xy[1] - (y + h))
            dist = dx * dx + dy * dy
            if best is None or dist < best[0]:
                best = (dist, idx)
        if index is None:
            if best is not None:
                index, reason = best[1], 'nearest'
            else:
                # NO POINT AT ALL (a probe that failed) is the one case that
                # asks the caller's question: "which monitor is primary".
                index = primary if 0 <= primary < len(items) else 0
                reason = 'primary'

    chosen = None
    if index is not None and 0 <= index < len(items):
        chosen = items[index]
    else:
        index = None

    display = chosen.get('display') if isinstance(chosen, dict) else None
    if display is None and chosen is not None:
        scale = num(chosen.get('scaleFactor'), 1.0)
        scale = scale if scale > 0 else 1.0

        def as_dip(shape):
            x, y, w, h = rect(shape)
            # A DIP EXTENT IS NEVER ZERO: at 400 % DPI a one-physical-pixel
            # work area rounds to 0, and a 0x0 window is not a window. The
            # clamp is on the EXTENT only; the origin keeps its own rounding.
            return {'x': round(x / scale), 'y': round(y / scale),
                    'width': max(1, round(w / scale)),
                    'height': max(1, round(h / scale))}

        display = {
            'handle': chosen.get('handle'),
            'bounds': as_dip(chosen.get('bounds')),
            'workArea': as_dip(chosen.get('workArea')),
            'scaleFactor': scale,
        }
    work = display.get('workArea') if isinstance(display, dict) else None

    clamped = None
    if geometry is not None and chosen is not None:
        scale = num(chosen.get('scaleFactor'), 1.0)
        scale = scale if scale > 0 else 1.0
        wx, wy, ww, wh = rect(chosen.get('workArea'))
        if ww > 0 and wh > 0:
            gx, gy, gw, gh = rect(geometry)
            # ONE multiply, ONE clamp in physical space, ONE divide back.
            px = gx * scale
            py = gy * scale
            pw = min(max(1.0, gw * scale), ww)
            ph = min(max(1.0, gh * scale), wh)
            px = max(wx, min(px, wx + ww - pw))
            py = max(wy, min(py, wy + wh - ph))
            clamped = dict(geometry) if isinstance(geometry, dict) else {}
            clamped['x'] = round(px / scale)
            clamped['y'] = round(py / scale)
            clamped['width'] = round(pw / scale)
            clamped['height'] = round(ph / scale)

    return {
        'index': index, 'reason': reason, 'point': xy,
        'monitors': items, 'primaryIndex': primary_index,
        'monitor': chosen, 'display': display,
        'workArea': work, 'geometry': clamped,
    }


def _selection_monitors_and_primary():
    """Win32 -> the PURE selector's inputs: all monitors + primary's index."""
    cb_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC,
                                 ctypes.POINTER(wt.RECT), wt.LPARAM)
    monitors = []

    def collect(hmon, _hdc, _lprc, _data):
        try:
            monitors.append(_selection_monitor(int(hmon or 0)))
        except Exception:  # noqa: BLE001 -- a stale monitor cannot block layout
            pass
        return True

    callback = cb_type(collect)
    user32.EnumDisplayMonitors.argtypes = [
        wt.HDC, ctypes.POINTER(wt.RECT), cb_type, wt.LPARAM]
    user32.EnumDisplayMonitors.restype = wt.BOOL
    if not user32.EnumDisplayMonitors(None, None, callback, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        primary = int(user32.MonitorFromPoint(
            POINT(0, 0), MONITOR_DEFAULTTOPRIMARY) or 0)
    except Exception:  # noqa: BLE001
        primary = 0
    for index, mon in enumerate(monitors):
        if mon['handle'] == primary:
            return monitors, index
    return monitors, 0


def target_placement(geometry=None):
    """Probe the point Win32 gives us, then let the PURE function decide.

    The foreground window still wins when it belongs to another app: that is
    the pre-existing Alt+C rule and this change does not alter it. Its monitor
    is mapped back to an interior point so the same pure function owns the
    final choice AND the work-area clamp. Sotto's own window means the cursor;
    a failed probe means the primary.
    """
    monitors, primary_index = [], 0
    try:
        monitors, primary_index = _selection_monitors_and_primary()
    except Exception:  # noqa: BLE001
        pass
    point = None
    try:
        user32.GetForegroundWindow.restype = wt.HWND
        user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        fg = user32.GetForegroundWindow()
        if fg:
            b = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(fg, b, 256)
            if not b.value.strip().lower().startswith('sotto'):
                handle = user32.MonitorFromWindow(fg, MONITOR_DEFAULTTONEAREST)
                for mon in monitors:
                    if mon.get('handle') == handle:
                        wa = mon['workArea']
                        point = (wa['x'] + wa['width'] // 2,
                                 wa['y'] + wa['height'] // 2)
                        break
    except Exception:  # noqa: BLE001
        pass
    if point is None:
        try:
            pt = POINT()
            if user32.GetCursorPos(ctypes.byref(pt)):
                point = (pt.x, pt.y)
        except Exception:  # noqa: BLE001
            pass
    result = select_display_for_point(point, monitors, primary_index,
                                      geometry=geometry)
    if not result.get('display'):
        # No usable monitor list: the historical primary fallback, unchanged.
        display = primary_display()
        result = dict(result)
        result['display'] = display
        result['workArea'] = display['workArea']
        if geometry is not None and result.get('geometry') is None:
            result['geometry'] = geometry
    return result


def target_display() -> dict:
    """The monitor the OWNER is looking at, in DIP (the historical return shape).

    Alt+C is pressed while looking at a screen, and the strip belongs on THAT
    screen: another app's window picks the monitor, Sotto's own window falls
    back to the cursor, then to the primary. The DECISION now lives in the
    pure `select_display_for_point`; this is only the Win32 probe around it.
    """
    return target_placement()['display']
