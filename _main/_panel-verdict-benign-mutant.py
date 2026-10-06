"""
Sotto — the WebView2 shell.

This REPLACES the Electron shell (app/electron/main.js) as the app's window,
and it is a replacement, not a rewrite of the panel: panel.html / panel.css /
panel.js are loaded byte-for-byte from app/electron/, unmodified. The only
thing this file owns is the surface they talk to — the `window.sotto` object —
and that surface is a line-for-line port of app/electron/preload.js.

  preload.js  ->  WebView2 equivalent
  ---------------------------------------------------------------------
  contextBridge.exposeInMainWorld  ->  CoreWebView2.
                                       AddScriptToExecuteOnDocumentCreatedAsync
  ipcRenderer.on  ->  ExecuteScriptAsync(window.__sotto_emit(...))
  ipcRenderer.send -> chrome.webview.postMessage -> pywebview's own WebMessage
                                       pump -> js_bridge_call -> dispatch()
  ipcRenderer.invoke -> the same channel plus a reply id

`AddScriptToExecuteOnDocumentCreatedAsync` is the exact analogue of Electron's
`preload:` webPreference: it runs in the page's main world before any page
script, on every navigation, so panel.js sees `window.sotto` already defined
when it runs at the bottom of <body>. That is why the panel needed no edit —
and panel.js's own "Preload bridge missing" branch is the receipt when it
fails (see `--dump-dom`, which asserts that string is absent).

Geometry is a port of main.js::dockRight, and the `--dump-dom` probe is the
SAME probe text main.js runs, so the two arms' numbers can be diffed.

Deliberate divergences from the Electron arm, all named in
docs/webview-shell-20261006.md:
  * MOD_NOREPEAT on the hotkey, so holding Alt+C does not machine-gun the panel.
  * No `setVisibleOnAllWorkspaces` equivalent (WebView2/WinForms has none).
  * The worker's cosmetic state-name map (worker-bridge.js STATE_MAP) is not
    ported; raw worker states pass through, and the two status INVARIANTS that
    protect the panel (never empty, never "no audio") are.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

import hot_reload

HERE = os.path.dirname(os.path.abspath(__file__))
#: The panel UI. Read-only for this shell: it is the Electron arm's files and
#: they are the contract, not ours to change.
PANEL_DIR = os.path.normpath(os.path.join(HERE, os.pardir, 'electron'))
PANEL_HTML = os.path.join(PANEL_DIR, 'panel.html')
#: An empty page the shell opens FIRST, so the preload is registered before the
#: panel is ever parsed. See stage.html for why the ordering needs buying.
STAGE_HTML = os.path.join(HERE, 'stage.html')
DEFAULT_WORKER_PATH = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, 'worker', 'sotto_worker.py')
)


def file_url(path):
    """`file:///C:/...` — an explicit file URL, like Electron's loadFile().

    Passing a bare path to pywebview does NOT open the file: `_resolve_url`
    sees a local path and silently starts pywebview's own HTTP server over it
    (window.py:277-280), so the panel arrived as
    `http://127.0.0.1:23602/electron/panel.html` and, because that server was
    started with only the staging file in its route table, it answered
    `Error: 404 Not Found` — measured, with the probe reporting
    `hasPanelElement: false`. An explicit `file://` URL skips the server
    entirely, which is also what the Electron arm did.
    """
    return 'file:///' + os.path.abspath(path).replace('\\', '/')

# --- geometry constants — the port of main.js:39-50 -------------------------
PANEL_WIDTH = 380
PANEL_HEIGHT = 900
PANEL_MARGIN = 12
PANEL_MAX_WORK_FRACTION = 0.34
MAX_CAPTIONS = 200

#: Capture shape. PortAudio's BLOCKING read API does not work on this host, so
#: the worker is told to use the callback shape — same default as
#: worker-bridge.js DEFAULT_CAPTURE_MODE.
DEFAULT_CAPTURE_MODE = 'callback'

# --- worker-bridge.js invariants, kept because they protect the panel -------
FALSE_AUDIO_ABSENT_RE = re.compile(
    r'\bwait(?:ing)?\s+for\s+audio\b|\bno\s+audio\b', re.IGNORECASE)
CAPTURE_NOT_STARTED = (
    'Capture not started - the worker has not opened the audio device'
)
FAILURE_WORDS_RE = re.compile(
    r'error|fail|fatal|dead|stopped|crash|denied|missing', re.IGNORECASE)

# --- the worker's OWN vocabulary, and how the panel must paint it -----------
# The reference arm decides this in `app/electron/worker-bridge.js`'s STATE_MAP:
# there `device_exhausted` is `kind: 'error'` and `device_rotated` is not. This
# shell never ported that table (it says so in `_readable`) and classified every
# state with FAILURE_WORDS_RE alone — an English prose list that contains none
# of this worker's failure states (`error`, `device-exhausted`, `silent-device`)
# and cannot see the verdict carried inside `done`. Measured consequence: a
# worker that died of a silent device was painted with the same NEUTRAL styling
# as warm-up, so the panel showed a healthy-looking app while nothing could ever
# transcribe. The DECISION is what gets ported here, not the prose.
WORKER_ERROR_STATES = frozenset({
    'error',             # any stage: model-load, device, open-stream, chunk
    'device-exhausted',  # every candidate tap was flat
    'silent-device',     # a tap ran a full window below the peak floor (exit 3)
})
#: `done` is neutral only while the run's OWN verdict says captions came out.
HEALTHY_DONE_VERDICTS = frozenset({'captions-emitted'})
#: States that report a worker still WARMING UP. They must not paint over a
#: death the panel is already showing: the shell restarts a dead worker
#: automatically, so the first thing after every exit 3 is `model-loading`, and
#: a panel that takes that at face value reports a healthy app in a death loop.
WORKER_WARMUP_STATES = frozenset({
    'boot', 'model-loading', 'model-loaded', 'device', 'capture-started',
    'device-rotated', 'selftest-start',
})
#: Fixed field order, so two runs' bodies diff by VALUE and not by shape.
STATUS_BODY_FIELDS = ('stage', 'detail', 'verdict', 'device', 'api', 'peak',
                      'peak_floor', 'blocks', 'window_s', 'captions', 'tokens',
                      'chunks', 'rotations', 'reason', 'rate')
STATUS_BODY_MAX = 400


def worker_status_kind(state, message):
    """'error' | 'busy' for ONE worker status line, by the reference arm's rule.

    Either test alone gets a real case wrong — the state is what this worker
    names itself, and the verdict is the only thing that can tell a `done` that
    produced speech from a `done` that produced nothing.
    """
    state = str(state or '')
    if state in WORKER_ERROR_STATES:
        return 'error'
    if state == 'done':
        # POSITIVE form, and the `verdict and` guard that used to stand here was
        # the swallow one level down: with it, a `done` carrying NO verdict (or
        # an empty one) failed the test, fell through to FAILURE_WORDS_RE, which
        # does not contain the word `done`, and the panel painted a bare "done"
        # as a healthy finish -- a worker that never said it transcribed, shown
        # as the one state that means it did. The contract is positive: only a
        # verdict that SAYS captions came out is benign; an UNKNOWN word and an
        # ABSENT word are both "this worker did not tell us it worked".
        verdict = str((message or {}).get('verdict') or '').strip()
        if verdict and verdict not in HEALTHY_DONE_VERDICTS:
            return 'error'
    return 'error' if FAILURE_WORDS_RE.search(state) else 'busy'


def worker_status_text(state, message, readable):
    """The footer line for ONE worker status: the worker's OWN cause, not a token.

    A bare `silent-device` in the footer is the swallow this exists to remove.
    The prose is kept clear of FALSE_AUDIO_ABSENT_RE on purpose: `_status`
    rewrites any "no audio" claim to CAPTURE_NOT_STARTED and forces the kind to
    busy, which would take a device failure and paint it as warm-up.
    """
    message = message or {}
    if state == 'done':
        if worker_status_kind(state, message) == 'error':
            verdict = str(message.get('verdict') or '').strip()
            if not verdict:
                # An absent verdict must not be rendered as the f-string of a
                # missing key ("Worker finished on None"), and it must not read
                # as a neutral end: the panel is saying the worker stopped
                # without saying it transcribed.
                return ('Worker finished on an UNKNOWN verdict - the worker '
                        'never said it transcribed')
            return f'Worker finished on {verdict}'
        return readable
    if state not in WORKER_ERROR_STATES:
        return readable
    device = str(message.get('device') or '').strip()
    api = str(message.get('api') or '').strip()
    peak = message.get('peak')
    floor = message.get('peak_floor')
    stage = str(message.get('stage') or '').strip()
    detail = str(message.get('detail') or '').strip()
    if state == 'silent-device':
        where = f'{device} [{api}]' if device and api else (device or 'the tap')
        if peak is not None and floor is not None:
            return f'Silent audio device - {where} peaked {peak} < floor {floor}'
        return f'Silent audio device - {where} delivered no signal'
    if state == 'device-exhausted':
        return ('Audio tap carried no signal - every candidate device was flat')
    if stage and detail:
        return f'Worker error at {stage} - {detail}'
    if detail:
        return f'Worker error - {detail}'
    if stage:
        return f'Worker error at {stage}'
    return readable


def worker_status_body(state, message):
    """The placeholder body for a worker status: the fields that explain it.

    The panel's own warm-up copy is what fills this area otherwise, and a panel
    whose headline says "warming up" while the worker is dead is the same lie as
    a neutral footer line.
    """
    message = message or {}
    parts = []
    for key in STATUS_BODY_FIELDS:
        value = message.get(key)
        if value is None or value == '':
            continue
        parts.append(f'{key}={value}')
    return ' '.join(parts)[:STATUS_BODY_MAX]

# ===========================================================================
# logging — stdout lines are the acceptance artefact
# ===========================================================================

_LOG_LOCK = threading.Lock()
_LOG_FILE = None


def _open_log(path):
    global _LOG_FILE
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        _LOG_FILE = open(path, 'a', encoding='utf-8', buffering=1)


def log(message: str) -> None:
    """One `sotto: ` prefixed line on stdout, mirrored to --log when asked.

    The Electron arm logs the same way (main.js:56), so the two run logs read
    alike and a claim in the receipt can be checked without watching the screen.
    """
    line = f'sotto: {message}'
    with _LOG_LOCK:
        print(line, flush=True)
        if _LOG_FILE is not None:
            _LOG_FILE.write(line + '\n')
            _LOG_FILE.flush()


def warn(message: str) -> None:
    log(f'WARN {message}')


# ===========================================================================
# geometry — the port of main.js::dockRight
# ===========================================================================


def dock_right(work, width=PANEL_WIDTH, height=PANEL_HEIGHT,
               margin=PANEL_MARGIN, dock='right'):
    """Dock a panel to the right edge of `work`, vertically centred.

    Kept a pure function for the same reason main.js keeps it pure: the output
    is contained in the work area whatever the work area is, including
    degenerate rectangles. `work` is `{'x','y','width','height'}` in DIP.
    """
    want_width = width if isinstance(width, (int, float)) else PANEL_WIDTH
    want_height = height if isinstance(height, (int, float)) else PANEL_HEIGHT
    want_margin = margin if isinstance(margin, (int, float)) else PANEL_MARGIN
    w = max(0, work['width'])
    h = max(0, work['height'])

    # A margin that leaves the panel no room to live in is a margin that
    # shrinks before anything else does.
    m = max(0, min(want_margin, w / 8, h / 8))
    # A panel wider than its share of the work area is a mistake, not a layout.
    panel_width = min(want_width, max(0, w * PANEL_MAX_WORK_FRACTION))
    panel_height = min(want_height, max(0, h - 2 * m))

    x = work['x'] + w - panel_width - m
    y = work['y'] + round((h - panel_height) / 2)

    geometry = {
        'workX': work['x'],
        'workY': work['y'],
        'workWidth': w,
        'workHeight': h,
        'x': max(work['x'], round(x)),
        'y': max(work['y'], round(y)),
        'width': max(1, round(panel_width)),
        'height': max(1, round(panel_height)),
        'margin': m,
        'docked': dock,
    }

    # Containment is an invariant, not a hope: clamp back into the work area.
    geometry['x'] = min(geometry['x'], work['x'] + w - geometry['width'])
    geometry['y'] = min(geometry['y'], work['y'] + h - geometry['height'])
    return geometry


def summary(g) -> str:
    """One line for the startup receipt — the same shape as main.js summary()."""
    return (
        f"docked={g['docked']} "
        f"work={g['workWidth']}x{g['workHeight']}@({g['workX']},{g['workY']}) "
        f"window={g['width']}x{g['height']}@({g['x']},{g['y']}) "
        f"margin={g['margin']}"
    )


# ===========================================================================
# Win32 — work area, DPI, extended styles, the hotkey
# ===========================================================================

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

MONITOR_DEFAULTTOPRIMARY = 0x00000001

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

SW_SHOWNOACTIVATE = 4
SW_HIDE = 0
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

_HOTKEY_ID = 0xB0F0  # any id will do; this one is ours and is not a window id


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [('hwnd', wt.HWND), ('message', ctypes.c_uint),
                ('wParam', ctypes.c_ulonglong), ('lParam', ctypes.c_longlong),
                ('time', ctypes.c_uint), ('pt', ctypes.c_long * 2)]


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


def primary_display() -> dict:
    """Primary display bounds + work area, in DIP, the shape Electron reports."""
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    handle = user32.MonitorFromPoint(POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)
    if not user32.GetMonitorInfoW(handle, ctypes.byref(mi)):
        raise ctypes.WinError(ctypes.get_last_error())

    scale = dpi_scale()

    def as_rect(r):
        return {
            'x': round(r.left / scale),
            'y': round(r.top / scale),
            'width': round((r.right - r.left) / scale),
            'height': round((r.bottom - r.top) / scale),
        }

    return {
        'handle': handle,
        'bounds': as_rect(mi.rcMonitor),
        'workArea': as_rect(mi.rcWork),
        'scaleFactor': scale,
    }


def set_ex_style(hwnd, add=0, remove=0) -> int:
    """Toggle extended styles on the panel HWND and return the new value."""
    current = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    updated = (current | add) & ~remove
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, updated)
    return updated


def make_click_through(hwnd, enabled: bool) -> int:
    """WS_EX_TRANSPARENT on/off — the Win32 spelling of click-through.

    Electron spells this `setIgnoreMouseEvents(true, {forward: true})`.
    WebView2 has no equivalent and WinForms has none either, but the extended
    style is what that call ultimately sets, and it still lets mouse *move*
    events reach the page, which is how the page asks for interactivity over
    its own controls.
    """
    if enabled:
        return set_ex_style(hwnd, add=WS_EX_TRANSPARENT)
    return set_ex_style(hwnd, remove=WS_EX_TRANSPARENT)


def show_without_activating(hwnd) -> bool:
    return bool(user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE))


def hide_window(hwnd) -> bool:
    return bool(user32.ShowWindow(hwnd, SW_HIDE))


def window_visible(hwnd) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


def set_topmost(hwnd) -> bool:
    return bool(user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE))


def foreground_window() -> int:
    return int(user32.GetForegroundWindow() or 0)


def parse_accelerator(accelerator: str):
    """'Alt+C' -> (MOD_ALT, ord('C'))."""
    mods = 0
    key = None
    named = {'ALT': MOD_ALT, 'MENU': MOD_ALT, 'CTRL': MOD_CONTROL,
             'CONTROL': MOD_CONTROL, 'SHIFT': MOD_SHIFT, 'WIN': MOD_WIN,
             'SUPER': MOD_WIN}
    for part in accelerator.split('+'):
        token = part.strip()
        if not token:
            continue
        if token.upper() in named:
            mods |= named[token.upper()]
        else:
            key = token.upper()
    if key is None:
        raise ValueError(f'no key in accelerator {accelerator!r}')
    if len(key) != 1:
        vk = {'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74,
              'F6': 0x75, 'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79,
              'F11': 0x7A, 'F12': 0x7B}
        if key not in vk:
            raise ValueError(f'unsupported accelerator key {key!r}')
        return mods, vk[key]
    return mods, ord(key)


class HotkeyThread(threading.Thread):
    """Global Alt+C on its own thread with its own message queue.

    RegisterHotKey(hWnd=NULL, ...) associates the hotkey with the CALLING
    THREAD and posts WM_HOTKEY to that thread's queue, so the toggle works
    whether or not any Sotto window exists, is visible, or has focus — which is
    the whole point of the hotkey (main.js:29-31 says the same). Running it on a
    private queue also means the WebView2 UI loop cannot starve it, and nothing
    here calls Activate/SetForegroundWindow, so it cannot steal focus.
    """

    def __init__(self, accelerator: str, on_hotkey, log_fn=log):
        super().__init__(name='sotto-hotkey', daemon=True)
        self.accelerator = accelerator
        self.modifiers, self.vk = parse_accelerator(accelerator)
        self.on_hotkey = on_hotkey
        self.log_fn = log_fn
        self.registered = False
        self.register_error = None
        self.thread_id = None
        self.pressed = 0
        self._stop = threading.Event()
        self._ready = threading.Event()

    def run(self):
        self.thread_id = int(kernel32.GetCurrentThreadId())
        # Force the queue into existence: RegisterHotKey against the current
        # thread is refused when the thread has never pumped a message.
        msg = MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        if not user32.RegisterHotKey(None, _HOTKEY_ID,
                                     self.modifiers | MOD_NOREPEAT, self.vk):
            self.register_error = ctypes.get_last_error()
            self.log_fn(f'HOTKEY_REGISTER_FAILED accelerator={self.accelerator} '
                        f'winerror={self.register_error}')
            self._ready.set()
            return

        self.registered = True
        self.log_fn(f'HOTKEY_REGISTERED accelerator={self.accelerator} '
                    f'register=true isRegistered=true toggle=show|hide '
                    f'mod_norepeat=true thread={self.thread_id}')
        self._ready.set()

        while not self._stop.is_set():
            got = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if got in (0, -1):
                break
            if msg.message == WM_HOTKEY:
                self.pressed += 1
                try:
                    self.on_hotkey()
                except Exception as exc:  # a toggle must never kill the pump
                    self.log_fn(f'HOTKEY_HANDLER_FAILED error={exc!r}')

    def stop(self):
        self._stop.set()
        if self.registered:
            user32.UnregisterHotKey(None, _HOTKEY_ID)
            self.registered = False

    def wait_ready(self, timeout=5.0) -> bool:
        return self._ready.wait(timeout)

    def simulate_press(self) -> bool:
        """Post a real WM_HOTKEY to this thread's queue.

        This exercises the registration's own delivery path — the same queue
        the OS writes to — which is what makes the two-state toggle evidence
        real rather than a direct call to the toggle function.
        """
        if not self.registered or self.thread_id is None:
            return False
        return bool(user32.PostThreadMessageW(self.thread_id, WM_HOTKEY,
                                              _HOTKEY_ID, 0))


# ===========================================================================
# the page bridge — the port of app/electron/preload.js
# ===========================================================================

#: Injected into the page's main world before any page script, on every
#: navigation. This is `preload.js` with its Electron transport swapped for
#: WebView2's, and its API surface IDENTICAL: same method names, same argument
#: order, same callback shape, same constants.
BOOTSTRAP_JS = r"""
(function () {
  'use strict';
  if (window.sotto) return;   // a second injection must not replace a live bridge

  var subs = { caption: [], status: [], geometry: [] };
  var queue = [];
  var infoSeq = 0;
  var infoPending = {};

  function emit(kind, payload) {
    var list = subs[kind] || [];
    for (var i = 0; i < list.length; i++) {
      try { list[i](payload); }
      catch (err) {
        console.error('sotto: a ' + kind + ' listener threw: ' +
          (err && err.message ? err.message : err));
      }
    }
  }

  function channelOpen() {
    return !!(window.pywebview && window.pywebview._returnValuesCallbacks &&
              window.chrome && window.chrome.webview);
  }

  function wire(kind, payload) {
    // Three rules, all measured against pywebview 6.2.1 on this host:
    //  1. The message is an ARRAY. Its pump does
    //     `func_name, func_param, value_id = json.loads(get_WebMessageAsJson())`
    //     (edgechromium.py:244); posting a string hands it one long string and
    //     it raises "too many values to unpack (expected 3)".
    //  2. The middle slot is `JSON.stringify(arguments)` — an ARRAY of
    //     POSITIONAL arguments, because pywebview then does
    //     `func(*func_params)` (util.py:255). Posting a bare object made Python
    //     unpack its KEYS: `ready({captions, placeholder, hasBridge})` arrived
    //     as three positional strings ("SottoHost.dispatch() takes 2
    //     positional arguments but 3 were given").
    //  3. Each element is encoded ONCE. pywebview json.loads()s the slot and
    //     hands the element to Python as-is, so the element must already be
    //     the STRING `dispatch` expects. Encoding the object twice handed
    //     Python a dict instead ("the JSON object must be str, bytes or
    //     bytearray, not dict").
    return ['dispatch',
            JSON.stringify([JSON.stringify({ kind: kind, payload: payload })]),
            '0'];
  }

  function post(kind, payload) {
    var message = wire(kind, payload);
    if (!channelOpen()) { queue.push(message); return; }
    window.chrome.webview.postMessage(message);
  }

  function ensureSink() {
    // pywebview answers every message it dispatched by calling
    // `_returnValuesCallbacks[funcName][valueId]` (util.py:264-266). That slot
    // is normally created by `_createApi` when the page calls the api THROUGH
    // pywebview; we post on the raw channel, so nothing created it and every
    // message raised
    // "window.pywebview._returnValuesCallbacks.dispatch.0 is not a function".
    // This host has no synchronous return values to hand back — main -> page
    // is ExecuteScriptAsync and page -> main is fire-and-forget — so a sink
    // that drops the value is the whole truthfulness of the situation.
    var slots = window.pywebview._returnValuesCallbacks;
    if (!slots.dispatch) slots.dispatch = {};
    if (typeof slots.dispatch['0'] !== 'function') {
      slots.dispatch['0'] = function (returnObj) {
        if (returnObj && returnObj.isError) {
          console.error('sotto: host dispatch returned an error: ' +
            returnObj.value);
        }
      };
    }
  }

  function flush() {
    if (!channelOpen()) return false;
    ensureSink();
    while (queue.length) window.chrome.webview.postMessage(queue.shift());
    return true;
  }

  // `bridge.ready()` is called while panel.js is still parsing, long before
  // pywebview has injected its api. Buffering until the channel opens is what
  // lets panel.js run unmodified instead of being special-cased.
  window.addEventListener('pywebviewready', flush);
  if (!flush()) setInterval(flush, 50);

  function normalise(text, meta) {
    if (text == null) return null;
    var value = String(text).replace(/\s+/g, ' ').trim();
    if (value === '') return null;
    return { text: value, meta: (meta && typeof meta === 'object') ? meta : {} };
  }

  window.__sotto_emit = function (kind, json) {
    var payload = null;
    try { payload = JSON.parse(json); } catch (err) { payload = null; }
    emit(kind, payload);
  };

  window.__sotto_info = function (id, json) {
    var resolve = infoPending[id];
    if (!resolve) return;
    delete infoPending[id];
    try { resolve(JSON.parse(json)); } catch (err) { resolve({ error: String(err) }); }
  };

  function subscribe(kind, callback) {
    if (typeof callback !== 'function') return function () {};
    subs[kind].push(callback);
    return function () {
      var i = subs[kind].indexOf(callback);
      if (i >= 0) subs[kind].splice(i, 1);
    };
  }

  window.sotto = {
    pushCaption: function (text, meta) {
      var caption = normalise(text, meta);
      if (!caption) return false;
      post('caption-observed', caption);
      emit('caption', caption);
      return true;
    },

    setStatus: function (text) {
      var value = String(text == null ? '' : text);
      post('status-observed', { text: value });
      emit('status', value);
      return true;
    },

    onCaption: function (cb) { return subscribe('caption', cb); },
    onStatus: function (cb) { return subscribe('status', cb); },
    onGeometry: function (cb) { return subscribe('geometry', cb); },

    hide: function () { post('hide', null); },
    toggle: function () { post('toggle', null); },
    quit: function () { post('quit', null); },

    setPointerInteractive: function (active) {
      post('pointer', { active: Boolean(active) });
    },

    // preload.js resolves a Promise here (ipcRenderer.invoke). The WebView2
    // transport has no invoke, so the id round-trip below is what makes this a
    // real resolved Promise rather than a synchronous object.
    getInfo: function () {
      return new Promise(function (resolve) {
        var id = 'i' + (++infoSeq);
        infoPending[id] = resolve;
        post('info', { id: id });
      });
    },

    captionApplied: function (text) {
      post('caption-applied', { text: String(text == null ? '' : text) });
    },
    statusApplied: function (text) {
      post('status-applied', { text: String(text == null ? '' : text) });
    },
    ready: function (payload) { post('renderer-ready', payload || {}); },
    clearApplied: function (remaining) {
      post('caption-cleared', { remaining: Number(remaining) || 0 });
    },

    HOTKEY: 'Alt+C',
    platform: 'win32'
  };
})();
"""

#: The `--dump-dom` probe. This is main.js:273-290 VERBATIM, so the two arms
#: print the same keys in the same order and the lines diff directly.
DUMP_DOM_PROBE = r"""
(() => {
  const sels = ['#panel', '.panel__header', '.wordmark', '.captions', '#placeholder',
                '#caption-list', '.status', '.wordmark__name', '#clear-button', '#status'];
  const out = { viewport: [innerWidth, innerHeight],
                zoom: (window.devicePixelRatio || 1),
                body: [document.body.scrollWidth, document.body.scrollHeight],
                sheets: document.styleSheets.length, els: {} };
  for (const s of sels) {
    const el = document.querySelector(s);
    if (!el) { out.els[s] = null; continue; }
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    out.els[s] = { rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
                   color: cs.color, display: cs.display, position: cs.position,
                   visibility: cs.visibility, opacity: cs.opacity };
  }
  return out;
})()
"""

#: The assertion that the bridge really was installed before panel.js ran.
#: panel.js:34 writes this exact sentence when `window.sotto` is undefined, so
#: its ABSENCE is a positive receipt that no injection race was lost.
BRIDGE_PROBE = r"""
(() => {
  const missing = document.body.textContent.indexOf('Preload bridge missing') >= 0;
  return {
    hasSotto: typeof window.sotto === 'object' && window.sotto !== null,
    // Which document is this, really? A probe that reports "the bridge is
    // there" while measuring a page with no `#panel` in it is a probe lying by
    // omission, so the document's own identity travels with the verdict.
    url: location.href,
    title: document.title,
    readyState: document.readyState,
    hasPanelElement: !!document.getElementById('panel'),
    methods: ['pushCaption', 'setStatus', 'onCaption', 'onStatus', 'onGeometry',
              'hide', 'toggle', 'quit', 'setPointerInteractive', 'getInfo',
              'captionApplied', 'statusApplied', 'ready', 'clearApplied']
              .filter((m) => typeof window.sotto[m] === 'function'),
    hotkey: window.sotto ? window.sotto.HOTKEY : null,
    platform: window.sotto ? window.sotto.platform : null,
    panelSaidBridgeMissing: missing,
    statusText: (document.getElementById('status-text') || {}).textContent || '',

    // WHAT THE PANEL SHOWS, not what the shell intended to send it. The
    // `statusText` above is the footer line; the two class flags are how the
    // panel paints severity (`status--error` is the red one), and the
    // placeholder block is the headline the owner reads before any caption
    // exists. A dump that carries only the text cannot tell "the panel showed
    // a dead worker" from "the panel showed the word `done` in a neutral
    // colour", which is a distinction this shell has already been wrong about.
    status: (() => {
      const s = document.getElementById('status');
      return { text: (document.getElementById('status-text') || {}).textContent || '',
               className: s ? String(s.className) : null,
               error: !!(s && s.classList.contains('status--error')),
               live: !!(s && s.classList.contains('status--live')) };
    })(),
    placeholder: (() => {
      const ph = document.getElementById('placeholder');
      const t = document.querySelector('.captions__placeholder-title');
      const b = document.querySelector('.captions__placeholder-body');
      return { hidden: ph ? !!ph.hidden : null,
               warming: !!(ph && ph.classList.contains('captions__placeholder--warming')),
               title: (t || {}).textContent || '',
               body: (b || {}).textContent || '' };
    })(),
    captions: (() => {
      const l = document.getElementById('caption-list');
      return { count: l ? l.childElementCount : -1, hidden: l ? !!l.hidden : null };
    })()
  };
})()
"""


class SottoHost:
    """The Python side of `window.sotto` — the js_api pywebview exposes.

    ONE public method, `dispatch`, carries every page->host message. That is
    deliberate: `chrome.webview.postMessage` is available from document start
    (pywebview's own `window.pywebview.api` is NOT — it only exists after the
    page finishes loading), and speaking pywebview's own wire format means the
    host reuses pywebview's WebMessage pump instead of racing a second handler
    onto the same event.
    """

    def __init__(self, shell):
        # PRIVATE on purpose. pywebview walks every public attribute of the
        # js_api (util.py:190-206) and recurses into objects that are not
        # callable, so a public `self.shell` sends it from SottoHost into
        # SottoShell into the pywebview Window into the WinForms Form and from
        # there into the whole .NET object graph — measured as
        # `maximum recursion depth exceeded while calling a Python object` on
        # `shell.form.Controls.Owner.DefaultFont.FontFamily...`. An attribute
        # whose name starts with `_` is skipped before it is even read.
        self._shell = shell

    def dispatch(self, wire):
        """`wire` is the JSON string the page sent as the pywebview func_param."""
        try:
            message = json.loads(wire)
        except (TypeError, ValueError) as exc:
            log(f'BRIDGE_BAD_MESSAGE error={exc!r}')
            return
        if not isinstance(message, dict):
            log(f'BRIDGE_BAD_MESSAGE shape={type(message).__name__}')
            return

        kind = message.get('kind')
        payload = message.get('payload')
        handler = {
            'caption-observed': self._caption_observed,
            'status-observed': self._status_observed,
            'caption-applied': self._caption_applied,
            'status-applied': self._status_applied,
            'caption-cleared': self._caption_cleared,
            'renderer-ready': self._renderer_ready,
            'pointer': self._pointer,
            'hide': lambda p: self._shell.hide_panel('page'),
            'toggle': lambda p: self._shell.toggle_panel('page'),
            'quit': lambda p: self._shell.quit('page'),
            'info': self._info,
        }.get(kind)
        if handler is None:
            log(f'BRIDGE_UNKNOWN_KIND kind={kind!r}')
            return
        try:
            handler(payload)
        except Exception as exc:  # a page callback must not kill the host
            log(f'BRIDGE_HANDLER_FAILED kind={kind} error={exc!r}')

    # -- receipts ----------------------------------------------------------
    def _caption_observed(self, payload):
        self._shell.note_caption_observed(payload)

    def _status_observed(self, payload):
        self._shell.note_status_observed((payload or {}).get('text', ''))

    def _caption_applied(self, payload):
        text = (payload or {}).get('text', '')
        self._shell.caption_log.append(text)
        del self._shell.caption_log[:-MAX_CAPTIONS]
        log(f'CAPTION_APPLIED text={json.dumps(text)} '
            f'count={len(self._shell.caption_log)}')

    def _status_applied(self, payload):
        text = (payload or {}).get('text', '')
        log(f'STATUS_APPLIED text={json.dumps(text)}')

    def _caption_cleared(self, payload):
        remaining = (payload or {}).get('remaining', 0)
        self._shell.caption_log.clear()
        log(f'CAPTIONS_CLEARED remaining={remaining}')

    def _renderer_ready(self, payload):
        payload = payload or {}
        placeholder = re.sub(r'\s+', ' ', str(payload.get('placeholder', ''))).strip()
        log(f'RECEIVER_READY captions={payload.get("captions", 0)} '
            f'hasBridge={bool(payload.get("hasBridge"))} '
            f'placeholder={json.dumps(placeholder[:80])}')
        self._shell.renderer_ready.set()

    def _pointer(self, payload):
        self._shell.set_pointer_interactive(bool((payload or {}).get('active')))

    def _info(self, payload):
        info_id = (payload or {}).get('id', '')
        self._shell.reply_info(info_id, self._shell.info())


# ===========================================================================
# the shell
# ===========================================================================


class SottoShell:
    def __init__(self, args):
        self.args = args
        self.window = None            # pywebview Window
        self.form = None              # pywebview's WinForms BrowserForm
        self.webview2 = None          # the WebView2 control
        self.core = None              # CoreWebView2
        self.hwnd = None
        self.staged = False   # have we navigated from stage.html to the panel
        self.geometry = None
        self.display = None
        self.visible = False
        self.pointer_interactive = False
        self.caption_log = []
        self.last_status = ''
        self.bridge_installed = None  # None until measured, True/False after
        self.renderer_ready = threading.Event()
        self.exiting = threading.Event()
        self.bridge = None            # WorkerBridge
        self.hotkey = None
        self.hot_reload = None       # hot_reload.HotReload
        self.reload_count = 0        # how many panel re-navigations have run
        self.startup_done = False    # startup actions run once per process
        self.startup_visible = None  # None until the window is measured
        self._exit_code = 0

    # -- geometry ----------------------------------------------------------
    def compute_geometry(self):
        self.display = primary_display()
        self.geometry = dock_right(self.display['workArea'])
        return self.geometry

    # -- window ------------------------------------------------------------
    def create_window(self):
        import webview  # imported late: it loads the WinForms assemblies

        geometry = self.compute_geometry()
        # Open on the staging page, not the panel. pywebview loads the URL from
        # its own CoreWebView2InitializationCompleted handler, which is
        # subscribed BEFORE the host's, so a preload registered from the host's
        # handler is registered after the panel's navigation is already in
        # flight — measured as `PRELOAD_ACTIVE hasSotto=false` on the first
        # parse. Staging buys one navigation of ordering so the panel's FIRST
        # parse already has the bridge. See stage.html.
        url = file_url(STAGE_HTML)

        log('panel window created frame=false transparent=' +
            str(not self.args.opaque).lower() +
            ' alwaysOnTop=true skipTaskbar=true resizable=false '
            'show=false focusable=false engine=WebView2/pywebview')
        log(f'panel geometry: {summary(geometry)}')
        log('primary display bounds=' + json.dumps(self.display['bounds']) +
            ' workArea=' + json.dumps(self.display['workArea']) +
            f" scaleFactor={self.display['scaleFactor']}")

        self.window = webview.create_window(
            title='Sotto',
            url=url,
            js_api=SottoHost(self),
            width=geometry['width'],
            height=geometry['height'],
            x=geometry['x'],
            y=geometry['y'],
            frameless=True,
            transparent=not self.args.opaque,
            on_top=True,
            resizable=False,
            easy_drag=False,
            hidden=True,
            # pywebview takes a hex TRIPLET, so the transparent case is carried
            # by `transparent=True` (which sets the WebView2 default background
            # to Transparent), not by an 8-digit colour here.
            **({} if self.args.opaque else {'background_color': '#0b0f14'}),
            text_select=False,
        )
        self.window.events.before_show += self._on_before_show
        self.window.events.loaded += self._on_loaded
        self.window.events.closing += self._on_closing
        return self.window

    def _form(self):
        return getattr(self.window, 'native', None)

    def _on_before_show(self):
        """The earliest hook that exists: the WinForms form is built and
        EnsureCoreWebView2Async has been *called* but has not completed."""
        form = self._form()
        if form is None:
            return
        self.form = form
        try:
            self.hwnd = int(form.Handle.ToInt64())
        except Exception:
            self.hwnd = None
        self.webview2 = form.webview

        # The panel never takes focus and never sits in the taskbar; in Win32
        # both are extended styles, not window flags.
        hwnd = self.hwnd
        if hwnd:
            set_ex_style(hwnd,
                         add=WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
                             | WS_EX_TRANSPARENT)
            log('panel setAlwaysOnTop(floating) ok '
                'style=WS_EX_LAYERED|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|'
                'WS_EX_TRANSPARENT')
            log('panel setFocusable(false) ok (WS_EX_NOACTIVATE)')
            log('panel setIgnoreMouseEvents(true, forward) ok (WS_EX_TRANSPARENT)')
            log('panel setVisibleOnAllWorkspaces SKIPPED - no WebView2/WinForms '
                'equivalent exists')

        self._fit_client_area(form)
        self._ui(self._subscribe_core_ready)
        # The startup-visibility probe is POSTED, never called from here:
        # before_show fires BEFORE pywebview's own Show();Hide() dance
        # (winforms.py:775 is this event; :777-782 is the dance), so a call at
        # this point would read a window that has not been created yet. Posted,
        # it runs on the UI thread the moment create() returns -- i.e. at the
        # state the owner would actually get.
        self._post(self._measure_startup_visibility)

    def _fit_client_area(self, form):
        """Make the CLIENT area exactly the docked panel size.

        pywebview sets `Form.Size` (winforms.py:209) while the form still has
        the default Sizable border, and only later switches to `None` for
        `frameless=True` (winforms.py:269-271). The WebView2 child is then
        sized to the client area computed under the OLD border, so the panel
        laid out at 364x861 inside a 380x900 window — measured, and the reason
        the DOMDUMP viewport disagreed with the Electron arm. Setting
        `ClientSize` after the border change pins the client area to the
        geometry the shell actually promised.
        """
        from System.Drawing import Size
        from System.Windows.Forms import DockStyle

        scale = self.display['scaleFactor']
        want_w = int(self.geometry['width'] * scale)
        want_h = int(self.geometry['height'] * scale)
        form.ClientSize = Size(want_w, want_h)
        self.webview2.Dock = DockStyle.Fill
        log(f'panel client area forced to {want_w}x{want_h} '
            f'(window {self.geometry["width"]}x{self.geometry["height"]})')

    def _measure_startup_visibility(self):
        """Is the panel ON THE OWNER'S SCREEN the moment the window exists?

        One line, and it is a MEASUREMENT, not a claim: `visible` is
        `IsWindowVisible(hwnd)` — the same channel the house window census
        reads (`Get-Process … .MainWindowHandle`, which .NET computes with
        `IsWindowVisible` + `GW_OWNER == 0`), so the log line and the census
        can be held against each other.

        WHY IT IS POSTED. pywebview's `hidden=True` branch (winforms.py:777-782)
        runs `Opacity=0; Show(); Hide(); Opacity=1`, so the form IS WS_VISIBLE
        for the span of one Show/Hide pair — measured in `_main/_dance-probe.py`
        with a bare WinForms form: visible=True between the two statements and
        False again after `Hide()` and after `Opacity=1`. A call placed in
        `_on_before_show` would read the state BEFORE that dance; posted, this
        runs after `create()` returns, which is the state the owner gets.

        `--show` is the app's own way to come up visible, so a `visible=true`
        there is the expected answer, not a defect — the line states the fact
        either way and never argues.
        """
        hwnd = self.hwnd
        visible = window_visible(hwnd) if hwnd else False
        self.startup_visible = visible
        form = self._form()
        try:
            form_visible = str(bool(form.Visible)).lower()
            opacity = form.Opacity
        except Exception:
            form_visible, opacity = 'unknown', 'unknown'
        log(f'PANEL_VISIBILITY_AT_STARTUP visible={str(visible).lower()} '
            f'hwnd={hwnd} form.Visible={form_visible} opacity={opacity} '
            f'show_requested={str(bool(self.args.show)).lower()}')

    def _measure_on_screen_visibility(self, where):
        """The panel's state ONCE THE STARTUP SEQUENCE HAS SETTLED.

        `PANEL_VISIBILITY_AT_STARTUP` reads the window pywebview's `hidden=True`
        dance leaves behind, and that dance does leave it hidden — measured, and
        reproducible in `_main/_dance-probe.py` with a bare WinForms form. It is
        therefore NOT the whole answer, and on its own it is the log that looks
        clean while the owner has a window on his screen:

            pywebview SHOWS the form again on EVERY navigation start when the
            window is transparent (edgechromium.py:345-349 —
            `if transparent: self.form.Show()`), and this shell navigates twice
            (stage.html, then the panel). `transparent` is ON by default
            (`--opaque` turns it off), so the panel came up ON SCREEN while
            `run.cmd` promises "start hidden".

        This line reads the state the owner actually gets, after the panel has
        loaded, in the same channel as the line above.
        """
        hwnd = self.hwnd
        visible = window_visible(hwnd) if hwnd else False
        log(f'PANEL_VISIBILITY_ON_SCREEN visible={str(visible).lower()} '
            f'where={where} hwnd={hwnd} '
            f'panel_shown={str(bool(self.visible)).lower()} '
            f'show_requested={str(bool(self.args.show)).lower()}')

    def _subscribe_core_ready(self):
        """Subscribe with `+=`, the only form pythonnet accepts for an event.

        Measured, both alternatives refused:
          * `add_CoreWebView2InitializationCompleted(fn)` ->
            "'method' value cannot be converted to System.EventHandler`1[...]"
          * `setattr(control, 'CoreWebView2InitializationCompleted', fn)` ->
            "TypeError: cannot set event attributes"
        pythonnet implements `obj.Event += handler` by returning a wrapper
        from the event GETTER and mutating that, so the statement form is the
        real API. It cannot live inside a lambda, hence this method.
        """
        self.webview2.CoreWebView2InitializationCompleted += self._on_core_ready

    def _on_core_ready(self, sender, args):
        """CoreWebView2 exists: install the preload-equivalent.

        Registration is per-ENVIRONMENT, not per-page, so registering while the
        staging page is the current document covers the panel's navigation too.
        """
        if not args.IsSuccess:
            log(f'WEBVIEW2_INIT_FAILED error={args.InitializationException}')
            return
        self.core = sender.CoreWebView2
        # pywebview SHOWS the form on every navigation start for a transparent
        # window (edgechromium.py:345-349), which is what put the panel on the
        # owner's screen at startup. Subscribe here, before the first page is
        # loaded, so the FIRST navigation is already covered.
        self.core.NavigationStarting += self._on_navigation_start
        self._install_bootstrap('initialization-completed')

    def _install_bootstrap(self, where):
        """Register the preload on the CoreWebView2, on the UI thread.

        `AddScriptToExecuteOnDocumentCreatedAsync` returns `Task[String]` in
        this binding, NOT an `IAsyncOperation`: reaching for `.Completed` on it
        raises `'Task[String]' object has no attribute 'Completed'`, which is
        exactly what the first run of this shell printed. The completion idiom
        is `ContinueWith(Action[Task[String]](...))`, which is also what
        pywebview itself uses for ExecuteScriptAsync
        (platforms/edgechromium.py:154-155).
        """
        from System import Action, String
        from System.Threading.Tasks import Task

        def _done(task):
            log(f'PRELOAD_INSTALLED where={where} status={task.Status}')

        def _add():
            self.core.AddScriptToExecuteOnDocumentCreatedAsync(
                BOOTSTRAP_JS).ContinueWith(Action[Task[String]](_done))

        self._ui(_add)

    def _on_loaded(self):
        """pywebview has injected its api and a page has finished loading."""
        if self.core is None:
            # `loaded` is set from a pywebview worker thread (util.py:232), and
            # CoreWebView2 is UI-thread-affine: reading it directly raises
            # "CoreWebView2 can only be accessed from the UI thread".
            def _grab():
                if self.webview2 is not None and \
                        self.webview2.CoreWebView2 is not None:
                    return self.webview2.CoreWebView2
                return None
            self.core = self._ui(_grab)

        if not self.staged:
            # First load is stage.html. The preload is registered by now, so
            # navigating here is what makes the panel's first parse correct.
            self.staged = True
            log(f'STAGING_LOADED core={"yes" if self.core else "no"} -> '
                f'navigating to panel {PANEL_HTML}')
            self.window.load_url(file_url(PANEL_HTML))
            return
        probe = self.exec_js(BRIDGE_PROBE)
        if probe and probe.get('hasSotto'):
            self.bridge_installed = True
            log(f'PRELOAD_ACTIVE hasSotto=true '
                f'methods={len(probe.get("methods", []))} '
                f'hotkey={probe.get("hotkey")} '
                f'platform={probe.get("platform")}')
        else:
            # Lost the race, or the script was rejected. Register it now and
            # reload: registration is persistent, so the SECOND parse has it.
            self.bridge_installed = False
            log('PRELOAD_ACTIVE hasSotto=false - reinstalling and reloading once')
            self._install_bootstrap('post-load-repair')
            self._ui(lambda: self.core.Reload())

        # Startup actions run ONCE per process, not once per navigation. A hot
        # reload re-enters this function; without this guard `--with-worker`
        # would spawn a SECOND worker and `--selftest` would run twice, so a
        # panel save would quietly multiply the thing the panel is for.
        if not self.startup_done:
            self.startup_done = True
            self.send_geometry()
            if self.args.show:
                self.show_panel('startup')
            self._measure_on_screen_visibility('startup')
            if self.args.with_worker:
                self.start_worker('with-worker')
            if self.args.dump_dom:
                # `--dump-dom-wait` is the difference between measuring the
                # panel and measuring the panel's STARTUP. A worker that will
                # die of a silent device spends its first seconds alive, so a
                # probe taken at t=0 photographs the warm-up and reports it as
                # the answer — which is how "the code is surfaced on the panel"
                # gets asserted without ever having seen the code.
                if self.args.dump_dom_wait > 0:
                    timer = threading.Timer(self.args.dump_dom_wait,
                                            self.run_dump_dom)
                    timer.daemon = True
                    timer.start()
                    log(f'DOMDUMP_WAIT s={self.args.dump_dom_wait}')
                else:
                    self.run_dump_dom()
            elif self.args.selftest:
                self.run_selftest()
            if self.args.memory and not self.args.memory_wait:
                self.run_memory()
            if self.args.exit_after:
                timer = threading.Timer(self.args.exit_after,
                                        self.request_exit, args=(0,))
                timer.daemon = True
                timer.start()
            return

        # A re-navigation (hot reload): re-send geometry and keep whatever
        # visibility the owner had. The hotkey is registered by THIS process,
        # so re-navigating the page cannot lose Alt+C.
        self.send_geometry()
        log(f'HOT_RELOAD_APPLIED reload={self.reload_count} '
            f'visible={str(self.visible).lower()} '
            f'hotkey_still_registered='
            f'{str(bool(self.hotkey and self.hotkey.registered)).lower()}')
        if self.visible:
            self.show_panel('hot-reload')

    def _on_closing(self):
        if self.bridge is not None:
            self.bridge.stop('closing')
        if self.hotkey is not None:
            self.hotkey.stop()
        self.stop_hot_reload('closing')
        log('SHELL_CLOSING')

    # -- UI thread marshalling --------------------------------------------
    def _ui(self, fn):
        """Run `fn` on the thread that owns the WebView2 control.

        CoreWebView2 members must be called from the UI thread; the worker
        reader thread and the hotkey thread are not it. pywebview marshals only
        its own form operations, so the host does it for itself.
        """
        from System import Func, Type  # pythonnet, loaded by pywebview

        form = self.form or self._form()
        if form is None:
            return None
        if form.InvokeRequired:
            done = threading.Event()
            box = {}

            def run():
                try:
                    box['value'] = fn()
                except Exception as exc:  # surfaced to the caller below
                    box['error'] = exc
                finally:
                    done.set()

            form.BeginInvoke(Func[Type](run))
            done.wait(10)
            if 'error' in box:
                raise box['error']
            return box.get('value')
        return fn()

    def _post(self, fn):
        """Queue `fn` on the UI thread and DO NOT wait for it.

        `_ui` waits, so it must never be used from inside a UI-thread callback:
        the delegate it posts can only run once the callback that posted it has
        returned, and `_ui` would sit on `done.wait(10)` while holding the very
        thread that has to run it. This is the fire-and-forget twin, for the
        case where the POINT is to run after the current UI message ends.
        """
        from System import Func, Type  # pythonnet, loaded by pywebview

        form = self.form or self._form()
        if form is None:
            return
        form.BeginInvoke(Func[Type](fn))

    # -- JS execution ------------------------------------------------------
    def exec_js(self, script, timeout=10.0):
        """Evaluate `script` in the page and return its JSON-decoded value.

        Same idiom as pywebview's own evaluate_js
        (platforms/edgechromium.py:152-159): the call is made through the
        control's `Invoke` so it runs on the UI thread, and completion arrives
        on a `ContinueWith(Action[Task[String]])`. `.Completed` does not exist
        on a `Task[String]` in this binding.
        """
        from System import Action, Func, Object, String
        from System.Threading.Tasks import Task

        box = {}
        done = threading.Event()

        def _complete(task):
            try:
                if task.IsFaulted:
                    box['error'] = repr(task.Exception)
                else:
                    box['json'] = task.Result
            except Exception as exc:
                box['error'] = repr(exc)
            finally:
                done.set()

        def _run():
            self.webview2.Invoke(Func[Object](
                lambda: self.core.ExecuteScriptAsync(script).ContinueWith(
                    Action[Task[String]](_complete))))

        try:
            self._ui(_run)
        except Exception as exc:
            box['error'] = repr(exc)
            done.set()

        self._ui(_run)
        if not done.wait(timeout):
            return None
        if 'error' in box:
            warn(f'exec_js failed: {box["error"]}')
            return None
        try:
            return json.loads(box.get('json', 'null'))
        except ValueError:
            return box.get('json')

    def emit(self, kind, payload):
        """main -> page: the WebView2 spelling of preload's `emit(kind, payload)`."""
        self.exec_js('window.__sotto_emit(' +
                     json.dumps(kind) + ',' + json.dumps(json.dumps(payload)) + ')')

    def send_status(self, text):
        self.last_status = text
        self.emit('status', str(text))

    def send_geometry(self):
        self.emit('geometry', self.geometry)

    # -- panel state -------------------------------------------------------
    def apply_panel_state(self, text, kind='busy', info=None):
        """main.js::applyPanelState — the footer line AND the placeholder.

        panel.html ships the placeholder hardcoded as "Waiting for audio", which
        on this host is a claim that is measured false, so the headline has to
        follow the real state. Done with the same class names panel.js already
        queries, which is what lets the panel files stay untouched.
        """
        line = str(text or '').strip()
        if not line:
            log('bridge status rejected: empty text would leave the stale line '
                'in place')
            return False

        self.send_status(line)
        info = info or {}
        shown = self.exec_js(
            '(() => {'
            '  const title = ' + json.dumps(info.get('title') or '') + ';'
            '  const body = ' + json.dumps(info.get('body') or '') + ';'
            '  const kind = ' + json.dumps(kind) + ';'
            "  const t = document.querySelector('.captions__placeholder-title');"
            "  const b = document.querySelector('.captions__placeholder-body');"
            '  if (t && title) t.textContent = title;'
            '  if (b && body) b.textContent = body;'
            "  const s = document.getElementById('status');"
            "  if (s) { s.classList.toggle('status--live', kind === 'live');"
            "           s.classList.toggle('status--error', kind === 'error'); }"
            "  return t ? t.textContent : '';"
            '})()')
        if shown:
            log(f'PLACEHOLDER_APPLIED title={json.dumps(str(shown))}')
        return True

    def note_caption_observed(self, payload):
        payload = payload or {}
        log(f'CAPTION_OBSERVED text={json.dumps(str(payload.get("text", "")))}')

    def note_status_observed(self, text):
        log(f'STATUS_OBSERVED text={json.dumps(str(text))}')

    # -- pointer -----------------------------------------------------------
    def set_pointer_interactive(self, active):
        if self.hwnd is None:
            return False
        make_click_through(self.hwnd, not active)
        self.pointer_interactive = bool(active)
        log(f'POINTER_INTERACTIVE active={str(bool(active)).lower()} '
            f'click_through={str(not active).lower()}')
        return True

    # -- show / hide -------------------------------------------------------
    def _on_navigation_start(self, sender, args):
        """The panel is about to navigate: pywebview is about to SHOW it.

        `edgechromium.py:345-349` does, on every navigation start:

            if self.pywebview_window.transparent:
                self.form.Show()
                self.form.Activate()

        That hack is what makes a transparent WebView2 window paint at all
        ("no idea why this works"), and it is TRANSPARENT-BY-DEFAULT here, so
        it silently undoes `hidden=True`: measured 2026-10-06, the panel came
        up on screen with `PANEL_VISIBILITY_AT_STARTUP visible=false` (the
        `hidden` dance did leave it hidden) and `PANEL_VISIBILITY_ON_SCREEN
        visible=true`, on the owner's desktop, while `run.cmd` promises "start
        hidden". The census named the pid: `_main/panel-startup-visibility.log`.

        The hack is left alone — it is load-bearing — and the shell's own
        INTENT is re-asserted right after it, TWICE:

          * synchronously, which is the tight one: .NET raises the handlers of
            one event in subscription order and pywebview subscribed while the
            form was being built, so this handler runs AFTER its Show() and
            closes the window inside the same dispatch;
          * and POSTED, which is the one that cannot be wrong: the posted
            delegate runs once every handler of this event has returned, so it
            covers the other order too.

        MEASURED, posted half only (run 2026-10-06T07:10:22Z): the panel was
        still caught on screen for ONE 200 ms sample out of 41
        (`_main/panel-startup-visibility-AFTER.log`, arm P, `CENSUS-PID …
        visible_samples_over_tree=1`) — a few hundred ms of window on the
        owner's desk at every start. The synchronous half closes that; the
        posted half is what keeps the cure true if the handler order ever
        flips. Nothing happens when the owner asked for the panel (`--show`,
        or Alt+C).
        """
        if self.args.show or self.visible:
            return
        self._reassert_hidden()
        self._post(self._reassert_hidden)

    def _reassert_hidden(self):
        """Put the panel away if nobody asked for it, and say so in the log."""
        hwnd = self.hwnd
        if not hwnd or self.args.show or self.visible:
            return
        if not window_visible(hwnd):
            return
        hide_window(hwnd)
        log(f'PANEL_VISIBILITY_REASSERTED reason=navigation '
            f'visible={str(window_visible(hwnd)).lower()}')

    def show_panel(self, reason):
        if self.hwnd is None:
            return False
        set_topmost(self.hwnd)
        # SW_SHOWNOACTIVATE, not Show(): the panel must never take focus away
        # from whatever the owner is typing into (main.js: `focusable=false`).
        show_without_activating(self.hwnd)
        self.visible = window_visible(self.hwnd)
        log(f'PANEL_SHOWN reason={reason} '
            f'visible={str(self.visible).lower()} '
            'show=SW_SHOWNOACTIVATE focus_stolen=false')
        return True

    def hide_panel(self, reason):
        if self.hwnd is None:
            return False
        hide_window(self.hwnd)
        self.visible = window_visible(self.hwnd)
        log(f'PANEL_HIDDEN reason={reason} '
            f'visible={str(self.visible).lower()}')
        return True

    def toggle_panel(self, reason):
        return (self.hide_panel(reason) if self.visible
                else self.show_panel(reason))

    # -- page -> host handlers --------------------------------------------
    def info(self):
        return {
            'hotkey': self.args.hotkey,
            'versions': {'shell': 'webview2/pywebview',
                         'python': sys.version.split()[0]},
            'geometry': self.geometry,
            'visible': self.visible,
            'rendererReady': self.renderer_ready.is_set(),
            'panel': PANEL_HTML,
        }

    def reply_info(self, info_id, payload):
        self.exec_js(f'window.__sotto_info({json.dumps(info_id)}, '
                     f'{json.dumps(json.dumps(payload))})')

    def quit(self, reason):
        self.request_exit(0, reason=reason)

    def request_exit(self, code=0, reason='requested'):
        if self.exiting.is_set():
            return
        self.exiting.set()
        self._exit_code = code
        if self.bridge is not None:
            self.bridge.stop('exit')
        if self.hotkey is not None:
            self.hotkey.stop()
        self.stop_hot_reload('exit')
        # `window.destroy()` marshals a Close() onto the UI thread and WAITS
        # for it. With a live worker streaming statuses, each status is an
        # ExecuteScriptAsync on that same thread, so the queue can be deep
        # enough that a synchronous destroy outlives the exit timer it was
        # called from — measured: `--with-worker --exit-after 30` never printed
        # SHELL_EXIT and had to be killed. Closing is cosmetic here (os._exit
        # follows immediately), so it runs on its own thread and is capped.
        if self.window is not None:
            def _close():
                try:
                    self.window.destroy()
                except Exception:
                    pass
            closer = threading.Thread(target=_close, name='sotto-close',
                                      daemon=True)
            closer.start()
            closer.join(3)
        log(f'SHELL_EXIT rc={code} reason={reason}')
        sys.stdout.flush()
        if _LOG_FILE is not None:
            _LOG_FILE.flush()
        os._exit(code)

    # -- worker ------------------------------------------------------------
    def start_worker(self, reason):
        if self.bridge is not None:
            return False
        self.bridge = WorkerBridge(
            command=self.args.python,
            worker_path=self.args.worker,
            device=self.args.device,
            capture_mode=self.args.capture or DEFAULT_CAPTURE_MODE,
            log=log,
            on_caption=self.on_worker_caption,
            on_status=self.on_worker_status,
        )
        log(f'WORKER_PATH {self.args.worker}')
        log(f'WORKER_COMMAND {self.args.python}')
        started = self.bridge.start(reason)
        log(f'WORKER_AUTOSTART={"started" if started else "declined"} '
            f'reason={reason}')
        return started

    def on_worker_caption(self, text, meta):
        self.emit('caption', {'text': text, 'meta': meta})
        log(f'BRIDGE_CAPTION_SENT delivered=true text={json.dumps(text)}')

    def on_worker_status(self, text, kind, info):
        self.apply_panel_state(text, kind, info)

    # -- hot reload --------------------------------------------------------
    # `hot_reload.py` watches and debounces; WHAT a reload means is decided
    # here, because only this object knows about the CoreWebView2 and the
    # bridge. The Electron arm splits it the same way (hot-reload.js watches,
    # main.js reloads) — same shape, different engine.
    def start_hot_reload(self):
        self.hot_reload = hot_reload.HotReload(
            log=log,
            on_panel_assets_changed=self.reload_panel_assets,
            on_worker_changed=self.restart_worker,
            panel_dir=PANEL_DIR,
            worker_dir=os.path.dirname(os.path.abspath(self.args.worker)),
        )
        return self.hot_reload.start()

    def reload_panel_assets(self, files):
        """Re-navigate the live page, in place, without a new window.

        `Navigate` and not `Reload`: a `file://` stylesheet can be served from
        the WebView2 cache, and a cached stylesheet makes "the reload did
        nothing" indistinguishable from "the reload never fired". Navigating
        to the same URL with a fresh cache-busting query is what makes the
        edit actually visible — which is the whole point of the feature.

        The hotkey belongs to THIS process, not to the page, so a re-navigation
        cannot lose Alt+C. It is re-read anyway and a loss is logged, because a
        hot reload that silently eats the only way to open the panel is the
        failure the owner would notice first.
        """
        if self.core is None or self.window is None:
            log(f'HOT_RELOAD_PANEL_SKIPPED files={json.dumps(files)} '
                'reason=no-core')
            return False
        self.reload_count += 1
        url = (file_url(PANEL_HTML) + f'?sotto_hr={self.reload_count}')
        # `self.staged`, NOT `self._staged`: `_on_loaded` reads the public one to
        # decide whether the current document is the staging page. Setting a
        # misspelled twin here looked correct and did nothing, so the reload
        # re-ran the staging navigation and the panel came up on stage.html.
        self.staged = True

        def _go():
            self.window.load_url(url)

        try:
            self._ui(_go)
        except Exception as exc:
            log(f'HOT_RELOAD_PANEL_THREW files={json.dumps(files)} '
                f'error={exc!r}')
            return False
        log(f'HOT_RELOAD_PANEL_DONE files={json.dumps(files)} '
            f'reload={self.reload_count} hotkey={self.args.hotkey}')
        return True

    def restart_worker(self, files):
        """Stop the one worker and start it again, on a worker file change."""
        if self.bridge is None:
            log(f'HOT_RELOAD_WORKER_SKIPPED files={json.dumps(files)} '
                'reason=no-worker-running')
            return False
        self.bridge.stop('hot-reload')
        self.bridge = None
        started = self.start_worker('hot-reload')
        log(f'HOT_RELOAD_WORKER_RESTART files={json.dumps(files)} '
            f'spawns={self.bridge.spawns if self.bridge else 0} '
            f'started={str(started).lower()}')
        return started

    def stop_hot_reload(self, reason):
        if self.hot_reload is not None:
            self.hot_reload.stop(reason)

    # -- probes ------------------------------------------------------------
    def run_dump_dom(self):
        """The Electron arm's --dump-dom: same probe, same line shape.

        Unlike the Electron arm this does NOT show the window: the dump measures
        the DOM, not a pixel surface, and a measurement run must not put a window
        on the owner's screen (main.js has to show it only because capturePage()
        needs a drawable surface).
        """
        dump = self.exec_js(DUMP_DOM_PROBE)
        if dump is None:
            log('DOMDUMP failed: probe returned nothing')
            self.request_exit(3, reason='dump-dom-failed')
            return
        log('DOMDUMP ' + json.dumps(dump, separators=(',', ':')))
        probe = self.exec_js(BRIDGE_PROBE) or {}
        log('BRIDGEPROBE ' + json.dumps(probe, separators=(',', ':')))

        # The gate has to survive a page that is NOT the panel. It once passed
        # vacuously: `panelSaidBridgeMissing` is the ABSENCE of a string in the
        # body, and a 404 page has no body text at all — so an earlier run
        # printed `hasSotto=true panelSaidBridgeMissing=false` while the URL was
        # `http://127.0.0.1:23602/electron/panel.html` returning
        # "Error: 404 Not Found" with no `#panel` anywhere. Three conditions,
        # all required, so the panel must be the document that answered.
        failures = []
        if probe.get('panelSaidBridgeMissing'):
            failures.append('panel-reported-missing-preload')
        if not probe.get('hasPanelElement'):
            failures.append('no-#panel-element')
        if not str(probe.get('url') or '').endswith('panel.html'):
            failures.append(f"wrong-document={probe.get('url')}")
        if not probe.get('hasSotto'):
            failures.append('window.sotto-absent')
        if (dump.get('els') or {}).get('#panel') is None:
            failures.append('domdump-#panel-null')

        if failures:
            log('BRIDGE_GATE=RED reasons=' + ','.join(failures))
            self.request_exit(3, reason='bridge-gate-red')
            return
        log('BRIDGE_GATE=GREEN hasPanelElement=true url=' +
            f"{probe.get('url')} panelSaidBridgeMissing=false")
        self.request_exit(0, reason='dump-dom')

    def run_memory(self):
        report = memory_report()
        log('MEMORY ' + json.dumps(report, separators=(',', ':')))
        return report

    def run_selftest(self):
        """Prove the hotkey registers and toggles, without a human at a keyboard.

        The press is a real WM_HOTKEY posted to the registering thread's own
        queue, so the delivery path under test is the one the OS writes to.
        """
        rc = 0
        if self.hotkey is None:
            # `--no-hotkey --selftest` is a contradiction: the self-test's whole
            # subject is the registration. Say so instead of raising on None.
            log('SELFTEST refused=--no-hotkey (nothing registered to prove)')
            self.request_exit(3, reason='selftest-needs-hotkey')
            return 3
        if not self.hotkey.wait_ready(5):
            log('SELFTEST hotkey_registered=false')
            rc = 3
        else:
            log(f'SELFTEST hotkey_registered='
                f'{str(self.hotkey.registered).lower()} '
                f'accelerator={self.hotkey.accelerator}')
            before = foreground_window()
            self.hide_panel('selftest-baseline')
            log(f'SELFTEST state=hidden visible={str(self.visible).lower()}')
            pressed = self.hotkey.simulate_press()
            time.sleep(0.8)
            log(f'SELFTEST state=after-hotkey-1 '
                f'visible={str(self.visible).lower()} '
                f'press_delivered={str(pressed).lower()} '
                f'presses={self.hotkey.pressed}')
            self.hotkey.simulate_press()
            time.sleep(0.8)
            log(f'SELFTEST state=after-hotkey-2 '
                f'visible={str(self.visible).lower()} '
                f'presses={self.hotkey.pressed}')
            after = foreground_window()
            log(f'SELFTEST focus_before={before} focus_after={after} '
                f'focus_stolen={str(before != after).lower()}')
            if (not self.hotkey.registered or not pressed
                    or self.visible or self.hotkey.pressed != 2):
                rc = 3
        log(f'SELFTEST rc={rc}')
        self.request_exit(rc, reason='selftest')


# ===========================================================================
# the worker bridge — the port of app/electron/worker-bridge.js
# ===========================================================================


class WorkerBridge:
    """Spawns worker/sotto_worker.py and turns its JSONL into panel events.

    The contract is the worker's, not this shell's: one JSON object per line on
    stdout, `{"type":"caption","text":...}` and `{"type":"status","state":...}`
    (sotto_worker.py:6-7). Everything else here is the same policy the Electron
    bridge runs: the device travels ONLY when the owner named one, a missing
    worker names the WORKER rather than the shell's ENOENT, an empty status is
    refused, and a status that asserts audio is absent is falsified — because
    the system tap on this host measures CAPTURED, so that sentence would be a
    lie with a fix attached to it.
    """

    def __init__(self, command, worker_path, device=None,
                 capture_mode=DEFAULT_CAPTURE_MODE, log=log,
                 on_caption=None, on_status=None, silence_ms=15000,
                 backoff_base=1000, backoff_max=30000):
        self.command = command or default_python()
        self.worker_path = worker_path
        self.device = device if isinstance(device, str) and device.strip() else None
        self.capture_mode = capture_mode
        self.log = log
        self.on_caption = on_caption or (lambda text, meta: None)
        self.on_status = on_status or (lambda text, kind, info: None)
        self.silence_ms = silence_ms
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

        self.child = None
        self.state = 'idle'
        self.restarts = 0
        self.spawns = 0
        self.captions = 0
        self.statuses = 0
        self.malformed = 0
        self.stopped = False
        self.last_exit = None
        # The last failure this worker reported, and the death the panel is
        # currently obliged to keep showing. `pending_error` is set by a
        # non-zero exit and cleared only by a CAPTION: a restart that has
        # produced no caption has proved nothing, so it must not clear it.
        self.last_error = None
        self.pending_error = None
        self.deaths = 0
        self.stderr_tail = []
        self._silence_timer = None
        self._restart_timer = None
        self._lock = threading.Lock()

    # -- status ------------------------------------------------------------
    def _status(self, text, kind='busy', info=None):
        value = str(text if text is not None else '').strip()
        if value == '':
            value = 'Worker status unavailable'
            kind = 'error'
        elif FALSE_AUDIO_ABSENT_RE.search(value):
            self.log(f'BRIDGE_STATUS_FALSIFIED text={json.dumps(value)}')
            value = CAPTURE_NOT_STARTED
            kind = 'busy'
        self.on_status(value, kind, info or {})
        return value

    def _bridge_status(self, text, kind, placeholder, state):
        self.state = state
        self._status(text, kind, placeholder)

    # -- lifecycle ---------------------------------------------------------
    def start(self, reason='start'):
        with self._lock:
            if self.stopped or self.child:
                return False
            self.log(
                f'BRIDGE_START reason={reason} command={self.command} '
                f'worker={self.worker_path} '
                f'device={"auto" if self.device is None else json.dumps(self.device)} '
                f'capture={self.capture_mode}')
            self._bridge_status(
                f'Starting worker... ({os.path.basename(self.worker_path)})',
                'busy',
                {'title': 'Starting the worker',
                 'body': 'The transcription worker is being launched. No audio '
                         'is being read yet.'},
                'starting')
            self._spawn()
            return True

    def _spawn(self):
        # The missing-file check is not an optimisation: spawning a nonexistent
        # path fails asynchronously and reports a message that names the shell,
        # not the worker. This names the worker, which is the whole point.
        if not os.path.exists(self.worker_path):
            self.log(f'BRIDGE_WORKER_MISSING path={self.worker_path}')
            self._bridge_status(
                f'Worker not found - {self.worker_path} does not exist', 'error',
                {'title': 'Worker not found',
                 'body': 'The shell found no worker entrypoint at the path it '
                         'was given.'},
                'missing')
            self._schedule_restart('missing')
            return

        self.state = 'spawning'
        self.spawns += 1
        self.stderr_tail = []

        env = dict(os.environ)
        env['SOTTO_CAPTURE_MODE'] = self.capture_mode
        if self.device is not None:
            env['SOTTO_AUDIO_DEVICE'] = self.device

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) \
            if os.name == 'nt' else 0

        try:
            self.child = subprocess.Popen(
                [self.command, self.worker_path],
                cwd=os.path.dirname(self.worker_path) or os.getcwd(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=creationflags,
            )
        except Exception as exc:
            self.child = None
            self.log(f'BRIDGE_SPAWN_FAILED error={exc!r}')
            self._bridge_status(
                f'Worker could not start - {exc}', 'error',
                {'title': 'Worker could not start',
                 'body': 'The shell tried to launch the worker and the '
                         'interpreter refused.'},
                'error')
            self._schedule_restart('spawn-failed')
            return

        self.log(f'BRIDGE_SPAWNED pid={self.child.pid} '
                 f'argv={json.dumps([self.command, self.worker_path])} '
                 f'SOTTO_CAPTURE_MODE={self.capture_mode} '
                 'SOTTO_AUDIO_DEVICE=' +
                 (self.device if self.device is not None else '(unset)'))

        for stream, name in ((self.child.stdout, 'stdout'),
                             (self.child.stderr, 'stderr')):
            threading.Thread(target=self._pump, args=(stream, name),
                             name=f'sotto-worker-{name}', daemon=True).start()
        threading.Thread(target=self._wait, name='sotto-worker-wait',
                         daemon=True).start()

        self._arm_silence()

    def stop(self, reason='stop'):
        with self._lock:
            if self.stopped:
                return False
            self.stopped = True
            self._cancel_timers()
            child, self.child = self.child, None
        if child is not None:
            self.log(f'BRIDGE_STOP reason={reason} pid={child.pid}')
            try:
                child.terminate()
                child.wait(timeout=5)
            except Exception:
                try:
                    child.kill()
                except Exception:
                    pass
            return True
        self.log(f'BRIDGE_STOP reason={reason} pid=none')
        return False

    # -- stdout ------------------------------------------------------------
    def _pump(self, stream, name):
        # A reader thread that dies takes the worker's WHOLE output channel with
        # it, and `except Exception: pass` made that indistinguishable from a
        # worker that said nothing: the run then logs `statuses=0` and the panel
        # shows only a bare exit code. Measured on this box: a live run logged
        # `statuses=0` on every one of 8 worker cycles while stderr arrived
        # normally. Two lines of logging is the difference between that being
        # diagnosable and being invisible.
        if stream is None:
            self.log(f'BRIDGE_PUMP_NULL stream={name} - the child has no pipe '
                     'on this stream, so nothing can ever be read from it')
            return
        try:
            for line in stream:
                if name == 'stderr':
                    self.stderr_tail.append(line.rstrip())
                    del self.stderr_tail[:-3]
                    continue
                self._arm_silence()
                text = line.strip()
                if text:
                    self._consume(text)
        except Exception as exc:
            self.log(f'BRIDGE_PUMP_DIED stream={name} error={exc!r}')
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _consume(self, line):
        try:
            message = json.loads(line)
        except ValueError:
            self.malformed += 1
            self.log(f'BRIDGE_MALFORMED line={json.dumps(line[:200])}')
            return
        if not isinstance(message, dict):
            self.malformed += 1
            return

        kind = message.get('type')
        if kind == 'caption':
            text = message.get('text')
            if text is None:
                self.malformed += 1
                return
            meta = {k: v for k, v in message.items()
                    if k not in ('type', 'text')}
            self.captions += 1
            # A caption is the ONLY proof that the current worker is really
            # transcribing, so it is the only thing allowed to lift a death the
            # panel is showing. Anything else (a restart's warm-up status) has
            # proved nothing yet.
            if self.pending_error is not None:
                self.log(f'BRIDGE_DEATH_LIFTED reason=caption captions={self.captions}')
                self.pending_error = None
            self.on_caption(str(text), meta)
        elif kind == 'status':
            self.statuses += 1
            state = str(message.get('state') or '')
            if state:
                self.state = state
            info = {k: v for k, v in message.items() if k not in ('type', 'state')}
            title = info.pop('title', None)
            body = info.pop('body', None)
            reason = info.pop('reason', None)
            severity = info.pop('level', None)
            if severity != 'error':
                severity = worker_status_kind(state, message)
            text = worker_status_text(state, message,
                                      self._readable(state, reason))
            if severity == 'error':
                # Remembered, so the automatic restart that follows cannot paint
                # its warm-up over a death the owner has not been shown yet.
                self.last_error = {'state': state, 'text': text,
                                   'body': body or worker_status_body(state, message)}
                self.log(f'BRIDGE_STATUS_ERROR state={json.dumps(state)} '
                         f'kind={severity} text={json.dumps(text)}')
            elif self.pending_error is not None and state in WORKER_WARMUP_STATES:
                # A restart re-emits model-loading/model-loaded/capture-started
                # every cycle. Painting those over a pending death is how the
                # panel came to show a healthy app while the worker was dying in
                # a loop, so they are logged and held instead.
                self.log(f'BRIDGE_STATUS_HELD state={json.dumps(state)} '
                         f'behind={json.dumps(self.pending_error["state"])}')
                return
            if severity == 'error':
                if not body:
                    body = (self.last_error or {}).get('body') or ''
                if not title:
                    title = 'Not transcribing'
            self._status(text, severity, {'title': title, 'body': body})
        else:
            self.malformed += 1
            self.log(f'BRIDGE_UNKNOWN type={kind!r}')

    def _readable(self, state, reason):
        """Say the state in words without pretending to a map we did not port.

        The Electron bridge renders worker states through STATE_MAP. That table
        is a cosmetic dictionary in another file and is NOT ported here; a raw
        state token is shown verbatim rather than guessed at, which is a fact
        instead of an invention.
        """
        return f'{state} ({reason})' if reason else state

    # -- supervision -------------------------------------------------------
    def _arm_silence(self):
        """Re-arm the no-output watchdog.

        MUST NOT take `self._lock`. `_spawn` is called from `start()` WITH the
        lock held and arms this watchdog on its way out, so a lock-taking body
        deadlocks the caller against itself — `threading.Lock` is not
        reentrant. Measured on this box (`_main/exit3-armB1.log`): the shell
        hung there, `start()` never returned, so `run.cmd --with-worker` never
        armed `--exit-after`, never ran its `--dump-dom` probe, and its stdout
        reader thread blocked before its first line. That is why a live run
        logged `BRIDGE_EXIT ... statuses=0` on all eight worker cycles and the
        panel could only ever show the bare `Worker stopped (exit 3)`.

        No lock is needed here: `_on_silence` re-checks `self.stopped`, so the
        worst case of a race with `stop()` is a timer that fires and returns.
        """
        if self.stopped:
            return
        if self._silence_timer is not None:
            self._silence_timer.cancel()
        timer = threading.Timer(self.silence_ms / 1000.0, self._on_silence)
        timer.daemon = True
        self._silence_timer = timer
        timer.start()

    def _cancel_timers(self):
        for name in ('_silence_timer', '_restart_timer'):
            timer = getattr(self, name, None)
            if timer is not None:
                timer.cancel()
                setattr(self, name, None)

    def _on_silence(self):
        if self.stopped or self.child is None:
            return
        self.log(f'BRIDGE_SILENT ms={self.silence_ms} pid={self.child.pid}')
        self._status('Worker is running but has said nothing', 'error',
                     {'title': 'Worker silent',
                      'body': 'The worker process is alive and produced no '
                              'output within the silence window.'})
        self._kill_and_restart('silent')

    def _wait(self):
        child = self.child
        if child is None:
            return
        rc = child.wait()
        self.last_exit = rc
        self.log(f'BRIDGE_EXIT pid={child.pid} rc={rc} spawns={self.spawns} '
                 f'captions={self.captions} statuses={self.statuses} '
                 f'malformed={self.malformed} '
                 f'stderr_tail={json.dumps(self.stderr_tail[-3:])}')
        self.child = None
        if self.stopped:
            return
        # The stderr tail is the worker's own sentence about its own death
        # (`SILENT-DEVICE ... peak=... < floor=...`); the reference arm keeps
        # three lines "to explain a death on the status line" and this shell
        # kept them only in its log, which is not where the owner looks.
        stderr_note = ' | '.join(self.stderr_tail[-2:])[:240]
        if rc != 0:
            # A non-zero exit is a DEATH, not a pause. The panel is obliged to
            # keep saying so through the automatic restart, because the restart's
            # warm-up statuses say nothing about whether the death will repeat.
            self.deaths += 1
            self.pending_error = self.last_error or {
                'state': 'exit', 'text': f'worker exit {rc}', 'body': ''}
            text = f'Worker stopped (exit {rc}) - {self.pending_error["text"]}'
        else:
            self.pending_error = None
            text = f'Worker stopped (exit {rc})'
        if self.pending_error is not None:
            self.log(f'BRIDGE_DEATH rc={rc} deaths={self.deaths} '
                     f'last={json.dumps(self.pending_error["text"])} '
                     f'stderr_tail={json.dumps(self.stderr_tail[-2:])}')
        self._status(text, 'error',
                     {'title': 'Worker stopped',
                      'body': ' '.join(x for x in (
                          (self.last_error or {}).get('body') if rc != 0 else '',
                          stderr_note,
                          'A restart is scheduled. Captions stay off until the '
                          'worker reports a caption.') if x)})
        self._schedule_restart('exit')

    def _kill_and_restart(self, reason):
        child, self.child = self.child, None
        if child is not None:
            try:
                child.terminate()
            except Exception:
                pass
        self._schedule_restart(reason)

    def _schedule_restart(self, reason):
        if self.stopped:
            return
        delay = min(self.backoff_max, self.backoff_base * (2 ** self.restarts))
        self.restarts += 1
        self.log(f'BRIDGE_RESTART reason={reason} in_ms={delay} '
                 f'restart={self.restarts}')
        timer = threading.Timer(delay / 1000.0, self._restart)
        timer.daemon = True
        self._restart_timer = timer
        timer.start()

    def _restart(self):
        if self.stopped or self.child is not None:
            return
        self.state = 'restarting'
        self._spawn()


def default_python() -> str:
    """`python` when it resolves, else the interpreter running this shell.

    worker-bridge.js hardcodes 'python'. This host reports which one it used
    rather than failing with an ENOENT the owner then has to decode.
    """
    return shutil.which('python') or sys.executable


# ===========================================================================
# memory
# ===========================================================================


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong),
                ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


def rss_mb(pid: int):
    """Working set of `pid` in MB, measured with GetProcessMemoryInfo."""
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel32.OpenProcess.restype = wt.HANDLE
    handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)  # QUERY+VM_READ
    if not handle:
        return None
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters),
                                          counters.cb):
            return None
        return counters.WorkingSetSize / (1024.0 * 1024.0)
    finally:
        kernel32.CloseHandle(handle)


TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_ulong), ('cntUsage', ctypes.c_ulong),
                ('th32ProcessID', ctypes.c_ulong),
                ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', ctypes.c_ulong),
                ('cntThreads', ctypes.c_ulong),
                ('th32ParentProcessID', ctypes.c_ulong),
                ('pcPriClassBase', ctypes.c_long), ('dwFlags', ctypes.c_ulong),
                ('szExeFile', ctypes.c_wchar * 260)]


def _process_table():
    """Every (pid, ppid, exe) on the machine, from the Toolhelp snapshot.

    Not `wmic`: on this host `wmic` is not on PATH
    (`wmic process ... ` -> `error: command not found: wmic`, measured), so a
    wmic-based census would report an empty child list and quietly understate
    the memory. This reads the same fact from the kernel.
    """
    kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    kernel32.Process32FirstW.argtypes = [wt.HANDLE,
                                          ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [wt.HANDLE,
                                         ctypes.POINTER(PROCESSENTRY32W)]
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wt.HANDLE(-1).value or not snapshot:
        return []
    rows = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            rows.append((int(entry.th32ProcessID),
                         int(entry.th32ParentProcessID),
                         entry.szExeFile))
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return rows


def child_processes(parent_pid: int):
    """[(pid, depth, exe)] for every DESCENDANT of `parent_pid`.

    Descendants, not just direct children: the first version counted direct
    children only and measured 210.9 MB, but WebView2's browser process
    spawns its own renderer/gpu/utility children, so that number was a floor,
    not a total. A shell comparison that flatters itself by stopping one level
    up is not a comparison. BFS over the same kernel snapshot, so the cost is
    one pass.
    """
    rows = _process_table()
    by_parent = {}
    for pid, ppid, exe in rows:
        by_parent.setdefault(ppid, []).append((pid, exe))
    out, frontier, depth = [], [parent_pid], 1
    while frontier:
        nxt = []
        for parent in frontier:
            # not the direct-child variant: the tree has to be walked whole
            for pid, exe in by_parent.get(parent, ()):
                out.append((pid, depth, exe))
                nxt.append(pid)
        frontier = nxt
        depth += 1
    return out


def memory_report():
    """This host's RSS plus every WebView2 descendant process, in MB.

    The Electron arm's 213.9 MB is `electron.exe`, which is a BROWSER PROCESS
    with its own renderer/gpu children; a like-for-like number has to include
    the WebView2 tree or it would flatter this shell. Both the host alone and
    the tree total are reported so neither number can be quoted alone.
    """
    me = os.getpid()
    host = rss_mb(me) or 0.0
    kids = []
    for pid, depth, exe in sorted(child_processes(me)):
        mb = rss_mb(pid)
        if mb is None:
            continue
        kids.append({'pid': pid, 'name': exe, 'depth': depth,
                     'rss_mb': round(mb, 1)})
    child_total = sum(k['rss_mb'] for k in kids)
    return {
        'host_pid': me,
        'host_rss_mb': round(host, 1),
        'webview_tree': kids,
        'webview_tree_rss_mb': round(child_total, 1),
        'total_rss_mb': round(host + child_total, 1),
    }


# ===========================================================================
# CLI
# ===========================================================================


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog='sotto-webview',
        description='The Sotto panel, hosted by WebView2 (pywebview).')
    parser.add_argument('--show', action='store_true',
                        help='show the panel at startup instead of waiting '
                             'for Alt+C')
    parser.add_argument('--hotkey', default='Alt+C',
                        help='the global toggle accelerator (default: Alt+C)')
    parser.add_argument('--no-hotkey', action='store_true',
                        help='do not register the global hotkey. A MEASUREMENT '
                             'run must use this: Alt+C is the app\'s only '
                             'control, and a probe that owns it shows the '
                             "owner its own panel when he presses his key")
    parser.add_argument('--worker', default=DEFAULT_WORKER_PATH,
                        help='worker entrypoint to spawn')
    parser.add_argument('--python', default=None,
                        help='interpreter for the worker (default: `python`, '
                             'else this interpreter)')
    parser.add_argument('--device', default=None,
                        help='audio device. PASSED ONLY WHEN SET: the worker '
                             'resolves the tap itself by default')
    parser.add_argument('--capture', default=None,
                        help=f'capture mode (default: {DEFAULT_CAPTURE_MODE})')
    parser.add_argument('--with-worker', action='store_true',
                        help='start the worker at launch')
    parser.add_argument('--dump-dom', action='store_true',
                        help="measure the panel with the Electron arm's probe "
                             'and exit')
    parser.add_argument('--dump-dom-wait', type=float, default=0.0,
                        help='seconds to wait before the --dump-dom probe, so '
                             'the dump can measure a state that only exists '
                             'after the worker has run (0 = measure at startup, '
                             'unchanged)')
    parser.add_argument('--opaque', action='store_true',
                        help='force an opaque window, to A/B transparency')
    parser.add_argument('--selftest', action='store_true',
                        help='prove the hotkey registers and toggles, then exit')
    parser.add_argument('--memory', action='store_true',
                        help='print the host RSS in MB')
    parser.add_argument('--memory-wait', type=float, default=0.0,
                        help='seconds to let the page settle before measuring')
    parser.add_argument('--exit-after', type=float, default=0.0,
                        help='quit on a wall clock, so an acceptance run ends '
                             'by itself')
    parser.add_argument('--no-hot-reload', action='store_true',
                        help='do not watch panel assets / worker sources')
    parser.add_argument('--log', default=None, help='mirror stdout here')
    return parser.parse_args(argv)


def pywebview_version():
    try:
        import importlib.metadata as md
        return md.version('pywebview')
    except Exception:
        return 'unknown'


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)

    _open_log(args.log)
    log(f'shell=webview2 pywebview={pywebview_version()} '
        f'python={sys.version.split()[0]} pid={os.getpid()}')

    if not os.path.exists(PANEL_HTML):
        log(f'PANEL_MISSING path={PANEL_HTML}')
        return 3

    args.python = args.python or default_python()

    shell = SottoShell(args)
    shell.create_window()

    # The hotkey lives on its own thread with its own message queue, so it is
    # registered before the UI loop exists and cannot be starved by it.
    # `--no-hotkey` is for MEASUREMENT runs: a probe that takes Alt+C steals the
    # one control the app has, and answers the owner's keypress with its own
    # panel (measured: two PANEL_SHOWN reason=hotkey lines during a probe run).
    if args.no_hotkey:
        log('HOTKEY_DISABLED reason=--no-hotkey')
    else:
        shell.hotkey = HotkeyThread(args.hotkey,
                                    lambda: shell.toggle_panel('hotkey'))
        shell.hotkey.start()
        shell.hotkey.wait_ready(5)

    # Hot reload is armed AFTER the hotkey, so a watcher that cannot start can
    # never cost the one feature the panel cannot live without. `--no-hot-reload`
    # is checked before anything is armed, exactly like the Electron arm's.
    if args.no_hot_reload:
        log('HOT_RELOAD_DISABLED reason=--no-hot-reload')
    elif not shell.start_hot_reload():
        warn('hot reload could not arm its watchers; the app still runs')

    if args.memory and args.memory_wait:
        threading.Timer(args.memory_wait, shell.run_memory).start()

    import webview
    webview.start()
    return shell._exit_code


if __name__ == '__main__':
    sys.exit(main())