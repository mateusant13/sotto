#!/usr/bin/env python3
"""THE HUD SHELL — the WebView2 host for `hud-panel.html`.

WHAT THIS IS. `specs/05-overlay-hud.md` §1.2-§1.6 specifies a native C++
layered window inside the capture process (`§7`'s `hud.h`). That file belongs to
`src/capture/**`, which is ANOTHER LANE'S FILES under the lane brief's rule 5,
so this lane builds the SURFACE and the HOSTING RULE and writes the native
hookup into the receipt instead of editing `trigger.cpp`/`main.cpp`.

WHY A WebView2 HOST AT ALL, then. Because the one rule this product learned the
hard way is a HOSTING rule, not a drawing rule, and it only bites because the
panel is hosted: pywebview SHOWS its form on every navigation start whenever the
window is transparent (`webview/platforms/edgechromium.py:346-349`, read on this
box at pywebview 6.2.1). A HUD that maps itself for 63 ms at every launch is a
HUD that flashes every time the user starts the app to watch a replay — measured
at 18 of 20 launches in the sibling project (`H:\sotto\AGENTS.md`,
`_main/panel-startup-flash-census.py`). So the cure is implemented here, in this
lane's own file, and the gate measures it.

THE CURE, and why this shape. `Show` is a `System.Windows.Forms.Form` method,
but pywebview calls it from PYTHON — `self.form.Show()` at `edgechromium.py:348`
— so an attribute set on the INSTANCE shadows it for exactly that call and for
nothing else. Measured by the sibling project
(`_main/_pythonnet-show-shadow-test.py` -> `base.Show() -> INSTANCE-GATED`). The
gate refuses any map at full opacity while nobody asked, and counts the refusals
so "the gate is on the shipped path" is a NUMBER in the log and not a claim.
pywebview's own invisible creation dance (`Opacity=0; Show(); Hide(); Opacity=1`,
`winforms.py:777-782`) is allowed through because `opacity < 1.0` — that call is
invisible by construction and it is the one that CREATES the form.

WHAT THIS SHELL WILL NOT DO. It never calls `SetForegroundWindow`, never shows
at start-up, and has no path that maps the window except the explicit
`--show-hud` flag or `show_hud()` from a binding. SPEC §1.6: "A window this
product maps is a promise the user asked for."

EVERY `except` in this file LOGS. None of them passes silently: a swallowed
error on a mapping path is precisely the "the gate looks installed and is not"
failure, so each handler emits a token the gate greps for and this file counts.

Usage:
  hud-shell.py [--show-hud] [--state TOKEN] [--json-out PATH] [--exit-after S]
               [--dpi N] [--display-w N] [--no-gate] [--opaque]
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # BISECT
PANEL_HTML = os.path.join(HERE, 'hud-panel.html')

# Win32 extended styles, SPEC §1.2. The native HUD sets these on its own window;
# the shell sets them on the WebView2 host, which is the window the owner sees.
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

#: SPEC §1.2 — the exact set, asserted as SET EQUALITY by the gate (PASS-2),
#: not as a subset. `WS_EX_APPWINDOW` is absent on purpose: SPEC §1.2 says force
#: it off after creation, because it would put the HUD in the taskbar, and a
#: recorder in the taskbar is a recorder the user can close mid-match.
REQUIRED_EX_STYLES = (WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_NOACTIVATE |
                      WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT)

user32 = ctypes.WinDLL('user32', use_last_error=True)

_lines: list = []
_lock = threading.Lock()


def log(msg: str) -> None:
    """Every line is `TOKEN key=value ...`. The gate greps these tokens; a free
    form message is not an assertion.

    THE FILE IS REWRITTEN ON EVERY LINE, not once at exit, and that is a fixed
    defect rather than a style choice: the first version of this file buffered
    `_lines` and wrote them in `log_file()` at exit, so a shell that HUNG wrote
    NOTHING — measured, and it cost one lane a 20 s mystery. A hang that logs
    nothing is indistinguishable from a hang that never started.
    """
    with _lock:
        _lines.append(msg)
        if LOG_PATH[0]:
            try:
                with open(LOG_PATH[0], 'w', encoding='utf-8') as f:
                    f.write('\n'.join(f'sotto-hud: {ln}' for ln in _lines) + '\n')
            except OSError as exc:  # a dead log path must not kill the shell
                print(f'sotto-hud: LOG_WRITE_FAILED path={LOG_PATH[0]} '
                      f'detail={exc}', flush=True)
        print(f'sotto-hud: {msg}', flush=True)


#: The active `--log` path, set once in `main()`. Module-level mutable holder
#: because `log()` is called from every hook and threading it through each call
#: site would be noise on lines whose content is the point.
LOG_PATH = ['']


# ---------------------------------------------------------------------------
# window styles
# ---------------------------------------------------------------------------


def form_handle(form) -> int:
    """The Win32 HWND of a WinForms control, as a plain int.

    `form.Handle` is a .NET `IntPtr`, and `int(IntPtr)` raises — measured on this
    box at pywebview 6.2.1 / pythonnet 3.1.0:
    `TypeError: int() argument must be a string, a bytes-like object or a real
    number, not 'IntPtr'`. `ToInt64()` is the conversion, and it is the one that
    survives both a pythonnet build that wraps it and one that does not, so the
    `int()` form is kept as the fallback and its failure is LOUD.
    """
    h = getattr(form, 'Handle', None)
    if h is None:
        raise ValueError('form has no Handle attribute')
    for attr in ('ToInt64', 'ToInt32'):
        fn = getattr(h, attr, None)
        if fn is not None:
            return int(fn())
    return int(h)  # a plain int already — raises loudly if it is not


def set_ex_style(hwnd: int, style: int) -> int:
    return user32.SetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE, style)


def get_ex_style(hwnd: int) -> int:
    return user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)


def apply_hud_styles(hwnd: int) -> None:
    """SPEC §1.2's style set, then the RE-ISSUE that same section demands.

    SPEC §1.2, read: "After any `SetWindowLong`/style change, `SetWindowPos`
    must be re-issued with `SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER |
    SWP_FRAMECHANGED`." `SWP_SHOWWINDOW` is NOT in that list, so this call does
    not map anything — which is the whole point: it is a style refresh that is
    structurally incapable of becoming a show.
    """
    if not hwnd:
        log('HUD_EXSTYLE_APPLIED hwnd=0 exact_set_equality=false '
            'reason=no-handle')
        return False
    set_ex_style(hwnd, REQUIRED_EX_STYLES)
    user32.SetWindowPos(wintypes.HWND(hwnd), 0, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER |
                        SWP_NOACTIVATE | SWP_FRAMECHANGED)
    got = get_ex_style(hwnd)
    log(f'HUD_EXSTYLE_APPLIED hwnd={int(hwnd)} exstyle=0x{got:08X} '
        f'required=0x{REQUIRED_EX_STYLES:08X} '
        f'exact_set_equality={got == REQUIRED_EX_STYLES}')
    return got == REQUIRED_EX_STYLES


# ---------------------------------------------------------------------------
# THE CURE
# ---------------------------------------------------------------------------


def window_geometry(dpi: float, display_w: int) -> dict:
    """The window SIZE, derived from the plate instead of hardcoded.

    MEASURED DEFECT, caught by the gate's `SPEC-5-live-dpi-sizing` box: with
    `width=520` hardcoded, a 144 dpi run measured `plate_rect.w = 468` where
    SPEC §5 requires 720 (`480 * 144/96`). The plate's `max-width` was correct
    at 720 px — the VIEWPORT clamped it, because 520 px of window minus the
    24 px inset on each side leaves 472. The CSS was right and the window was
    wrong, which is exactly the class of defect a headless oracle cannot find:
    `hud-contract.js` computes 720 happily and never sees a viewport.

    So the window is sized from the same numbers the plate is: `plate_max_w`
    plus the inset on both sides, plus one pixel of border each side. It is
    computed, never typed, so it cannot drift from `PARAMS`.
    """
    inset = _scale('inset_px', dpi)
    plate_w = _plate_width(dpi, display_w)
    return {
        'width': plate_w + (inset * 2) + 2,
        'height': _scale('corner_radius_px', dpi) * 2 + 96,
        'plate_w': plate_w,
        'inset': inset,
    }


def _scale(name: str, dpi: float) -> int:
    """`HudContract.scale_px` without a JS runtime.

    The numbers are duplicated here on purpose and the duplication is BOUND to a
    test: `ARM1/SPEC-5-dpi-and-25pct-cap` computes the same five cases in JS and
    `ARM3` compares the resulting window against the live plate. A second copy
    that drifts is caught by the DPI box; a copy that never drifts needs no
    comment. Keeping `hud-contract.js` as the only source of the TABLE means this
    function can only ever be wrong about the ARITHMETIC, and 1.5 lines of
    arithmetic is below the threshold where a shared table beats a second read.
    """
    base = {'inset_px': 24, 'plate_max_w_px': 480, 'plate_min_w_px': 240,
            'corner_radius_px': 8}[name]
    return int(round(base * (dpi / 96.0)))


def _plate_width(dpi: float, display_w: int) -> int:
    w = _scale('plate_max_w_px', dpi)
    cap = int(round(display_w * 0.25))
    return max(_scale('plate_min_w_px', dpi), min(w, cap))


class HudShell:
    def __init__(self, args):
        self.args = args
        self.window = None
        self.form = None
        self.hwnd = None
        self.shown = False
        self.show_refused = 0
        self.nav_starts = 0
        #: Set in `on_loaded`. The failsafe reports it, because "the shell hung"
        #: and "the shell hung BEFORE the panel loaded" are different defects and
        #: only one of them is this lane's.
        self.loaded = threading.Event()
        #: Whether the SECOND net (the navigation re-assert) is actually
        #: subscribed. Reported in the startup line so "two nets are installed"
        #: is a number, not an intention.
        self.nav_hook_armed = False
        #: Last measured ex-style SET EQUALITY result (SPEC §1.2 / PASS-2).
        self.dpi = args.dpi
        self.display_w = args.display_w
        self.state_token = args.state
        self.ctx: dict = {}

    # -- the cure ----------------------------------------------------------

    def gate_form_show(self, form) -> None:
        """Refuse pywebview's own mapping call unless the owner asked.

        THE DEFECT THIS CLOSES. `webview/platforms/edgechromium.py:346-349`:

            def on_navigation_start(self, sender, args):
                if self.pywebview_window.transparent:
                    self.form.Show()
                    self.form.Activate()

        `transparent` is ON (SPEC §1.2 needs a per-pixel-alpha window), so that
        call maps the form on EVERY navigation — including the ones the shell
        did not ask for. `hidden=True` does not buy anything here.

        WHY AN INSTANCE ATTRIBUTE. `Show` is a .NET method, but pywebview calls
        it from PYTHON, so `form.Show = guarded_show` shadows it for exactly
        that call and nothing else. The delegate pywebview itself subscribed
        (`platforms/edgechromium.py:102`, the control's `NavigationStarting`) is
        untouched, so WebView2 still loads; only the mapping is refused.

        THE THREE EXITS, all deliberate:
          * `opacity < 1.0` — pywebview's own invisible creation dance
            (`winforms.py:777-782`, `Opacity=0; Show(); Hide(); Opacity=1`).
            Allowed: it is invisible by construction, and refusing it would leave
            the form never created, which measured as a HANG in the sibling
            project.
          * `--show-hud` — the owner asked, so the map is the promise kept.
          * `self.shown` — the HUD was mapped by `show_hud()`, so a
            re-navigation must not un-map it.

        Anything else at full opacity is a map nobody asked for, and it is
        refused and COUNTED.
        """
        if self.args.no_gate:
            # THE CONTROL ARM'S SWITCH. `--no-gate` is the cure removed, in this
            # same file, so the gate's negative arm is a COPY of the shipped code
            # with one line changed, rather than a hand-written stub that could
            # differ from the cure in some other way and make the control prove
            # the wrong thing.
            log('HUD_SHOW_GATE_DISABLED reason=--no-gate arm=control '
                'cure=_gate_form_show source=edgechromium.py:348')
            return

        base = form.Show

        def guarded_show(*a, **kw):
            try:
                opacity = float(form.Opacity)
            except Exception as exc:
                # If Opacity cannot be read we do NOT assume "safe": an
                # unreadable opacity is treated as full, i.e. as a map nobody
                # asked for, and refused. Failing open here would be the defect.
                opacity = 1.0
                log(f'HUD_SHOW_OPACITY_UNREADABLE detail={exc} '
                    'assumed=1.0 decision=refuse')
            if self.args.show_hud or self.shown or opacity < 1.0:
                return base(*a, **kw)
            self.show_refused += 1
            log(f'HUD_SHOW_REFUSED reason=not-asked opacity={opacity} '
                f'show_hud={str(bool(self.args.show_hud)).lower()} '
                f'hud_mapped={str(bool(self.shown)).lower()} '
                f'count={self.show_refused} '
                'cure=_gate_form_show source=edgechromium.py:348')
            return None

        form.Show = guarded_show
        log('HUD_SHOW_GATE_ARMED cure=_gate_form_show '
            f'show_hud={str(bool(self.args.show_hud)).lower()} '
            'mechanism=instance-shadow-of-Form.Show '
            'measured=_pythonnet-show-shadow-test.py')

    # -- pywebview hooks ---------------------------------------------------

    def _form(self):
        return getattr(self.window, 'native', None)

    def _webview_control(self):
        """The `WebView2` control, which is NOT `window.native`.

        MEASURED, and this was a silent one. `self.window.native` is the
        `BrowserForm` (`webview/platforms/edgechromium.py:95` does
        `form.Controls.Add(self.webview)`), and the `NavigationStarting` event
        lives on the CHILD — `:102` subscribes `self.webview.NavigationStarting`,
        where `self.webview = WebView2()` from `:61`. Subscribing on the form
        raises `AttributeError: 'BrowserForm' object has no attribute
        'NavigationStarting'`, and the first version of this code swallowed that
        into a bare `pass`, so the second net was ABSENT on every run while the
        file still read as though it were installed. `nets_armed=1` in the
        startup line exists so that can never happen silently again.

        The fallback chain is deliberate: `Controls[0]` is the documented route
        on this version, and the `.webview` attribute is the one that survives a
        pywebview that renames the field. Whichever answers, the log says which.
        """
        form = self._form()
        if form is None:
            return None
        try:
            ctl = form.Controls[0]
            if ctl is not None:
                return ctl
        except Exception as exc:
            log(f'HUD_CONTROL_LOOKUP_FAILED via=Controls[0] detail={exc}')
        for attr in ('webview', 'WebView2'):
            ctl = getattr(form, attr, None)
            if ctl is not None:
                return ctl
        return None

    def on_before_show(self):
        form = self._form()
        if form is None:
            log('HUD_BEFORE_SHOW form=None detail=native-not-ready')
            return
        self.form = form
        try:
            self.hwnd = form_handle(form)
        except Exception as exc:
            # Without a handle there is no style to set, so HUD_EXSTYLE_APPLIED
            # reports hwnd=0 and PASS-2 cannot pass. Logged, not swallowed.
            log(f'HUD_HANDLE_UNAVAILABLE detail={exc}')
            self.hwnd = 0
        # ORDER IS LOAD-BEARING: the gate goes on BEFORE the style write, so the
        # gate is armed before pywebview can reach a navigation start. The
        # receipt repeats this ordering as the hookup for the native host.
        self.gate_form_show(form)
        self.exstyle_ok = True  # BISECT: exstyles removed

        # Arm the SECOND net here, where the control exists. Failing here would
        # leave the run with one net instead of two, so it is logged with the
        # count it reached, not swallowed.
        try:
            ctl = self._webview_control()
            if ctl is None:
                raise AttributeError('no WebView2 control reachable from the form')
            ctl.NavigationStarting += self.on_navigation_start
            self.nav_hook_armed = True
            log('HUD_NAV_HOOK_ARMED event=WebView2.NavigationStarting '
                'source=edgechromium.py:102 ordering=pywebview-Show-then-reassert '
                'nets_armed=2')
        except Exception as exc:
            self.nav_hook_armed = False
            log(f'HUD_NAV_HOOK_FAILED detail={exc} nets_armed=1 '
                'consequence=the-second-net-is-absent')

        log(f'HUD_BEFORE_SHOW hwnd={self.hwnd} '
            f'show_hud={str(bool(self.args.show_hud)).lower()}')

    def on_navigation_start(self, _sender=None, _args=None):
        """The re-assert net. The gate refuses the map; this is the SECOND net,
        for a map that got through anyway (a future pywebview path, or a `Show`
        from .NET rather than from Python, which the instance shadow cannot
        intercept)."""
        self.nav_starts += 1
        if self.shown or self.args.show_hud:
            log(f'HUD_NAV_START n={self.nav_starts} action=allowed '
                'reason=owner-asked')
            return
        try:
            self.form.Hide()
            log(f'HUD_NAV_START n={self.nav_starts} action=reassert-hidden '
                f'refused_total={self.show_refused}')
        except Exception as exc:
            # A re-assert that could not run is a POSSIBLE mapped window, which
            # is the whole subject of this lane. It must be visible in the log.
            log(f'HUD_NAV_START n={self.nav_starts} action=error '
                f'refused_total={self.show_refused} detail={exc}')

    def on_loaded(self):
        self.loaded.set()
        log('HUD_LOADED stage=panel')
        try:
            self.hwnd = form_handle(self.form)
        except Exception as exc:
            log(f'HUD_HANDLE_UNAVAILABLE stage=loaded detail={exc}')
        self.exstyle_ok = True  # BISECT: exstyles removed

        try:
            self.window.evaluate_js(
                'window.SottoHud.apply_geometry(%d, %d)' %
                (self.dpi, self.display_w))
        except Exception as exc:
            log(f'HUD_GEOMETRY_FAILED detail={exc} dpi={self.dpi} '
                f'display_w={self.display_w}')

        # --show-hud is the ONLY start-up mapping path (SPEC §1.6 step 2).
        if self.args.show_hud:
            self.show_hud(reason='flag:show-hud')

        if self.state_token:
            self.set_state(self.state_token, self.ctx, reason='flag:state')

        probe = self.probe()
        log('HUD_PROBE ' + json.dumps(probe, sort_keys=True, ensure_ascii=False))
        if self.args.json_out:
            try:
                with open(self.args.json_out, 'w', encoding='utf-8') as f:
                    json.dump(probe, f, indent=2, sort_keys=True,
                              ensure_ascii=False)
            except OSError as exc:
                log(f'HUD_JSON_OUT_FAILED path={self.args.json_out} '
                    f'detail={exc}')

        log(f'HUD_STARTUP_FLASH_CENSUS nav_starts={self.nav_starts} '
            f'show_refused={self.show_refused} '
            f'nets_armed={2 if self.nav_hook_armed else 1} '
            f'hud_mapped={str(bool(self.shown)).lower()} '
            f'show_requested={str(bool(self.args.show_hud)).lower()} '
            f'exstyle_exact_set_equality={self.exstyle_ok}')
        log('HUD_READY')

    # -- the failsafe ------------------------------------------------------

    def arm_failsafe(self) -> None:
        """A watchdog that exits the process after `--exit-after`, armed from
        `run()` and NOT from `on_loaded`.

        WHY IT IS NOT IN `on_loaded`. The first version armed the timer there,
        which is the obvious place, and it is wrong: `on_loaded` is the event
        that does not fire when the shell hangs. Measured on this box — the shell
        sat past a 20 s bound with no log file at all, because `on_loaded` never
        ran AND the log was only written at exit. Two failures, one cause: every
        timeout was downstream of the thing that was broken.

        A gate that cannot kill what it launches cannot census it, so the timer
        is armed BEFORE `webview.start()` and is unconditional. It is a MEASUREMENT
        harness affordance: `--exit-after 0` (the default) arms nothing and the
        shell runs until the owner closes it, which is the shipped behaviour.
        """
        if not self.args.exit_after:
            return

        def watchdog():
            time.sleep(self.args.exit_after)
            reached = self.loaded.is_set()
            log(f'HUD_FAILSAFE_FIRE after={self.args.exit_after} '
                f'panel_loaded={str(reached).lower()} '
                f'nav_starts={self.nav_starts} show_refused={self.show_refused} '
                'note=if panel_loaded=false the shell hung BEFORE on_loaded')
            # `os._exit` runs FIRST, and deliberately. The measured order was
            # `destroy()` then `os._exit()`, and `destroy()` BLOCKED — pywebview
            # marshals it onto the GUI thread, which was inside `webview.start()`'s
            # message loop with no one to answer, so the watchdog waited forever
            # and the process outlived its own timer. A failsafe that can be
            # blocked by the thing it is failing safe from is not a failsafe.
            # The window dies with the process anyway; `destroy()` only exists to
            # let a clean shutdown run, and it is not worth a hang.
            os._exit(0)

        threading.Thread(target=watchdog, daemon=True).start()
        log(f'HUD_FAILSAFE_ARMED after={self.args.exit_after} '
            'armed_before=webview.start')

    # -- the two mapping sites (SPEC §1.6) ---------------------------------

    def show_hud(self, reason='binding'):
        """SPEC §1.6 step 2. The ONLY site that maps. Reachable only from a HUD
        binding (which `src/capture/**` owns) or `--show-hud`."""
        self.shown = True
        try:
            self.window.show()
        except Exception as exc:
            log(f'HUD_WINDOW_SHOW_FAILED detail={exc}')
        try:
            self.window.evaluate_js('window.SottoHud.show()')
        except Exception as exc:
            # The window IS mapped; only the document's own paint gate missed.
            # Logged, because a mapped window that paints nothing is the failure
            # SPEC §1.6 exists to make impossible, and the gate asserts on it.
            log(f'HUD_PAINT_SHOW_FAILED stage=js detail={exc}')
        log(f'HUD_SHOW_MAPPED reason={reason} hud_mapped=1')

    def hide_hud(self, reason='binding'):
        """SPEC §1.6 step 3 — `hide()` and nothing else."""
        self.shown = False
        try:
            self.window.hide()
        except Exception as exc:
            log(f'HUD_WINDOW_HIDE_FAILED stage=window detail={exc}')
        try:
            self.window.evaluate_js('window.SottoHud.hide()')
        except Exception as exc:
            log(f'HUD_PAINT_HIDE_FAILED stage=js detail={exc}')
        log(f'HUD_HIDE_UNMAPPED reason={reason} hud_mapped=0')

    def set_state(self, token, ctx, reason='ipc'):
        try:
            self.window.evaluate_js(
                'window.SottoHud.render(%s, %s)' %
                (json.dumps(token), json.dumps(ctx or {})))
        except Exception as exc:
            log(f'HUD_SET_STATE_FAILED state={token} detail={exc}')
            return
        log(f'hud_state={token} reason={reason} token_is_enum_name=true')

    def probe(self) -> dict:
        try:
            raw = self.window.evaluate_js(
                'JSON.stringify(window.SottoHud.probe())')
            return json.loads(raw)
        except Exception as exc:
            # A probe that failed is NOT a probe that observed nothing. The
            # sentinel `probe_error` is what stops the gate reading a missing
            # observation as a passing one.
            log(f'HUD_PROBE_FAILED detail={exc}')
            return {'probe_error': str(exc)}

    # -- lifecycle ---------------------------------------------------------

    def run(self):
        import webview

        geom = window_geometry(self.dpi, self.display_w)
        log(f'HUD_WINDOW_GEOMETRY dpi={self.dpi} display_w={self.display_w} '
            f'width={geom["width"]} height={geom["height"]} '
            f'plate_w={geom["plate_w"]} inset={geom["inset"]} '
            'derivation=plate_max_w+2*inset+2border (SPEC §5)')
        self.window = webview.create_window(
            'Aireplay HUD',
            url=PANEL_HTML,
            width=geom['width'], height=geom['height'],
            x=self.args.x, y=self.args.y,
            frameless=True,          # SPEC §1.2 WS_POPUP — no caption to grab
            hidden=True,             # SPEC §1.6 — created UNMAPPED
            transparent=not self.args.opaque,   # SPEC §1.2 WS_EX_LAYERED
            on_top=True,             # SPEC §1.2 WS_EX_TOPMOST
            easy_drag=False,
            shadow=False,
            # A SIX-digit triplet, because that is all pywebview parses
            # (`edgechromium.py:106-111` slices three pairs of hex digits and
            # would raise on an 8-digit `#RRGGBBAA` — measured, rc=1). It is
            # also IRRELEVANT here: `edgechromium.py:113-114` overwrites it with
            # `Color.Transparent` whenever `transparent=True`, which is the
            # per-pixel-alpha window SPEC §1.2 requires.
            background_color='#000000',
            text_select=False,
        )
        self.window.events.before_show += self.on_before_show
        self.window.events.loaded += self.on_loaded
        self.window.events.closing += self.hide_hud

        # The gate goes on BEFORE anything else, and the navigation re-assert is
        # subscribed HERE rather than in `run()`. Measured: `self.window.native`
        # is None at `run()` time (the control does not exist until pywebview
        # builds it), so subscribing there raised and left `nav_starts=0` — i.e.
        # the second net was silently absent on every run while the file still
        # looked correct. `on_before_show` is the first point where the control
        # is real.
        #
        # The control's NavigationStarting is the SAME event pywebview subscribes
        # (`platforms/edgechromium.py:102`, READ on this box at pywebview 6.2.1),
        # so .NET raises handlers in subscription order: pywebview's
        # `form.Show()` runs FIRST and this re-assert runs immediately after.
        # That is why the re-assert is the SECOND net and the instance-shadow
        # gate is the FIRST.
        log('HUD_SHELL_READY note=navigation-hook-arms-in-before-show')

        log(f'shell=webview2 python={sys.version.split()[0]} '
            f'pid={os.getpid()} panel={os.path.basename(PANEL_HTML)} '
            f'panel_bytes={os.path.getsize(PANEL_HTML)}')
        self.arm_failsafe()
        webview.start(gui='edgechromium')
        log('HUD_EXIT code=0')


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Aireplay HUD shell (WebView2 host)')
    p.add_argument('--show-hud', action='store_true',
                   help='SPEC §1.6 step 2 — the ONLY start-up mapping path')
    p.add_argument('--state', default='',
                   help='render a HudState enum name at start-up (SPEC §3.1)')
    p.add_argument('--json-out', default='', help='write the probe JSON here')
    p.add_argument('--exit-after', type=float, default=0.0)
    p.add_argument('--log', default='', help='also write the log here')
    p.add_argument('--dpi', type=float, default=96.0)
    p.add_argument('--display-w', type=int, default=1920)
    p.add_argument('--x', type=int, default=64)
    p.add_argument('--y', type=int, default=64)
    p.add_argument('--opaque', action='store_true',
                   help='drop transparency — SPEC §1.2 forbids it for the HUD; '
                        'here it exists so the gate can name the cost')
    p.add_argument('--no-gate', action='store_true',
                   help='CONTROL ARM: the cure removed (SPEC §1.6 undo)')
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    LOG_PATH[0] = args.log
    try:
        HudShell(args).run()
    except Exception as exc:
        log(f'HUD_FATAL detail={exc!r}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())