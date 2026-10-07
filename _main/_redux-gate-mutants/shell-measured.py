"""
Sotto — the WebView2 shell.

This REPLACES the Electron shell (app/_legacy-electron/main.js) as the app's window,
and it is a replacement, not a rewrite of the panel: panel.html / panel.css /
panel.js are loaded byte-for-byte from app/panel/, unmodified. The only
thing this file owns is the surface they talk to — the `window.sotto` object —
and that surface is a line-for-line port of app/_legacy-electron/preload.js.

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
import tempfile
import threading
import time

import hot_reload
import panel_state

HERE = os.path.dirname(os.path.abspath(__file__))
#: The panel UI. Read-only for this shell: these are the app's own panel files
#: and they are the contract, not ours to change.
PANEL_DIR = os.path.normpath(os.path.join(HERE, os.pardir, 'panel'))
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

# --- the panel AS TEXT: one JSON dump a reader opens with `read` ------------
# Owner's order, 2026-10-06, verbatim: "faz uma versao do sotto ou painel que tu
# pode ver sem precisar da visao". Until now the panel's state was only knowable
# through a screen capture, and a capture needs vision and is limited in time.
# The dump is written from state the shell ALREADY holds — the bridge's own
# counters, the panel's own live box read over the existing `exec_js` seam, and
# the `WORKER_STATS` line the bridge already reads off the worker's stderr — so
# it is a READ channel, not a second pipeline. Nothing the owner sees changes.
REPO_ROOT = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
PANEL_STATE_PATH = os.path.join(REPO_ROOT, '_main', 'panel-state.json')
#: The on-demand trigger: create this file and the next tick dumps immediately
#: (`py app/webview/panel_state.py --request`).
PANEL_STATE_REQUEST = PANEL_STATE_PATH + '.request'
PANEL_STATE_INTERVAL_S = 2.0

# --- THE PANEL'S VISIBILITY, as a file the WORKER can poll -------------------
# THE STACK LAW (owner, 2026-10-07, verbatim): *"o nvidia é pro ao vivo, o
# parakeet redux é pro geral. o ao vivo só acontece quando o painel ta aberto.
# quando ta fechado, o redux entra, e vira um transcritor LEVE ao contrario do
# nvidia."* The streaming engine must work only while the panel is OPEN; when it
# is CLOSED the batch engine takes over. The worker is a SEPARATE PROCESS, so
# "is the panel open" has to cross a process boundary. This file is that
# crossing, and it is the ONLY thing added here.
#
# WHY A FILE, AND NOT A MESSAGE. The worker speaks one channel: JSONL on ITS
# stdout. There is no worker->shell input pipe, and adding one would make
# "visibility" a second protocol with its own framing, its own ack and its own
# silent failure mode. A file the worker only READS cannot be corrupted by the
# worker, and a reader that misses a tick reads the CURRENT truth instead of a
# queued event that was already stale when it was queued.
#
# WHY `visible` IS MEASURED AND NOT INTENDED. It is `window_visible(hwnd)` —
# the same `IsWindowVisible` the hotkey path decides from and the cheap
# `--selftest` two-state check asserts — never "we called hide". A stale
# intention is exactly the defect class this repo has been bitten by twice
# (`PANEL_VISIBILITY_CACHE_STALE`, and the panel that was on screen while
# `PANEL_VISIBILITY_AT_STARTUP` said `visible=false`).
#
# THE AGE IS NOT SELF-REPORTED, for the reason `panel_state.py` spells out: a
# producer that dies cannot update a number inside the file it stopped writing.
# `writtenAtEpoch` + `staleAfterSeconds` let a reader REFUSE a dead shell's
# answer, and the worker's fail-safe is to treat missing/stale as
# `visible=true` (i.e. KEEP STREAMING) — because the alternative, obeying a
# stale `visible:false`, is the one failure the HARD RULE in AGENTS.md forbids:
# zero transcription while the owner is not looking.
PANEL_VISIBILITY_PATH = os.path.join(
    REPO_ROOT, '_main', 'panel-visibility.json')
PANEL_VISIBILITY_INTERVAL_S = 3.0
#: Bumped when a field is renamed or removed, so a reader refuses a shape it
#: does not know instead of reading a wrong number.
PANEL_VISIBILITY_SCHEMA = 'sotto.panel-visibility/1'

# --- the transcript history (the "redux"), on disk --------------------------
# The panel's TOP section is the accumulated transcript; the BOTTOM box is the
# live stream. History is written to `<root>/<YYYY-MM-DD>/<HH>.md` — a 24 h
# folder with one file per hour, appended as captions commit — so the owner can
# find his own data in the file manager and a search can walk it cheaply.
# The default root is the repo's own `history/` (H:/sotto/history): the owner
# asked for the data to live under H:/sotto. SOTTO_HISTORY_ROOT overrides it.
HISTORY_ROOT = os.path.normpath(
    os.environ.get('SOTTO_HISTORY_ROOT')
    or os.path.join(HERE, os.pardir, os.pardir, 'history'))
#: One history line: `- [HH:MM:SS] text`. Markdown-readable AND parseable.
HISTORY_LINE_RE = re.compile(r'^-\s+\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$')
HISTORY_DAY_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
#: The provenance the WRITER stamps on the end of a line (M8). It is an HTML
#: comment, so a Markdown reader shows the sentence and nothing else, and every
#: reader of the FILE strips it before treating the rest as text.
HISTORY_TAIL_RE = re.compile(r'\s*<!--.*?-->\s*$')
#: The vocabulary `_history_provenance` is allowed to write. A route outside it
#: is not written at all: a marker nobody can interpret is worse than none.
HISTORY_ROUTES = ('final', 'provisional-draft')
#: The route SOURCES `_history_provenance` is allowed to write as `src=` — WHICH
#: branch decided the route. `'fallback'` is the one the de-landing produced
#: SILENTLY: a line that reached the transcript ONLY because the renderer's
#: `routeFor` else-half manufactured `final` when the worker stamped no route at
#: all (P1 `4fb5b25380cbc8269977e22e`). Outside this list nothing is written.
#: The Node twin is `ROUTE_SOURCES` in `app/panel/history-store.js`.
HISTORY_ROUTE_SOURCES = ('worker-stamped', 'panel-deadline', 'fallback')
#: `explorer` for "show in folder" must never open a console window.
CREATE_NO_WINDOW = 0x08000000

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
# The reference arm decides this in `app/_legacy-electron/worker-bridge.js`'s STATE_MAP:
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
#: The ONE state that means an audio stream is OPEN (sotto_worker.py:2139 emits
#: `capture-started` on every tap attempt, whether or not it later proves flat).
#: From that line on the worker is mid-stream, and a hot reload must not restart
#: it under the owner's feet.
WORKER_CAPTURING_STATES = frozenset({'capture-started'})

# --- the worker's OWN verdict about the audio, and what the silence timer owes it
# A missing caption is NOT evidence of a fault. An IDLE DESKTOP produces digital
# silence BY DESIGN: measured by this repo's own idle-floor probe, the loopback of
# the default render endpoint carries peak=0.000000 over three independent 6 s
# captures (`_main/sdr_idlefloor.out`). So a worker whose taps are all flat is
# telling the truth about a quiet machine, and the ONLY thing the shell may do
# with that truth is show it.
#
# MEASURED DEFECT this replaces (lane SottoTapRestartLoop, live run
# `_main/_live_owner3.log`): the 15 s no-output watchdog killed and respawned the
# worker 8 times in ONE run (`BRIDGE_SILENT` x8, `spawns=10`), each respawn
# reloading a ~2.4 GB model (the worker's own `rss_mb=2413-2418`), because a
# caption is the only thing that lifted the timer and a quiet desktop can never
# produce one. The loop could not converge: there was never a caption to lift it,
# and never would be while nothing was rendering.
#
# The criterion is the WORKER'S OWN VERDICT, never the absence of a caption.
# These two sets are that verdict as the worker writes it: as a `status.state`
# (the device ladder's own conclusion) and as the `verdict` carried inside `done`.
WORKER_NO_AUDIO_STATES = frozenset({
    'silent-device',         # a tap ran a full window below the peak floor (exit 3)
    'device-exhausted',      # every candidate tap was flat
    'no-speech-in-capture',  # the tap carried signal and none of it was speech
    'music-only-capture',    # the endpoint is carrying non-speech
})
#: The same conclusion, carried by the run's `done` line. `captions-emitted` is
#: deliberately absent: it is the one verdict that says speech DID come out.
#: (`silent-capture` lives HERE and not above: verified against
#: worker/sotto_worker.py, it is a `verdict=`, never a `state=`.)
WORKER_NO_AUDIO_VERDICTS = frozenset({
    'silent-device', 'all-candidate-taps-flat', 'silent-capture',
    'no-callback-blocks', 'resample-produced-nothing',
    'buffer-never-reached-chunk-size', 'captions-all-music-gated',
    'captured-signal-has-no-speech',
})
#: The UI state the shell paints when the silence is the worker's own no-audio
#: verdict. Named, so the panel says WHAT is true instead of "Worker silent".
NO_AUDIO_STATE = 'no-audio'

# --- the worker's OWN counters line, read for the text dump -----------------
# `worker/sotto_worker.py` writes `WORKER_STATS tag=tick|final ...` on STDERR
# (`stats_line()`, every `--stats-interval` seconds, default 10). The bridge
# already reads that stream for its stderr tail — those lines were being DROPPED
# after three, so `peak` and `nonzero_blocks` were unreachable from outside the
# process. This parses the same line the bridge already sees; it starts no
# process and reads no other file.
WORKER_STATS_RE = re.compile(r'^WORKER_STATS\s+tag=(\S+)\s*(.*)$')

#: The worker's heartbeat cadence: `--stats-interval` default in
#: `worker/sotto_worker.py` (10 s), published as `WORKER_STATS tag=tick` on
#: stderr. It is the only periodic signal the worker emits, which is why the
#: no-progress watchdog counts it (see `WorkerBridge._note_progress`).
WORKER_STATS_INTERVAL_S = 10.0
#: The no-progress window. MEASURED, not guessed. The old 15000 ms was armed on
#: STDOUT alone, i.e. on CAPTIONS, and a real conversation's commit-to-commit
#: gap is routinely longer than that: the owner's own log
#: (`_main/webview-run.log`, 2026-10-06) commits lines 62 s, 62 s and 56 s
#: apart while the worker is transcribing normally — so the watchdog was
#: killing a healthy worker and paying a ~2.4 GB model reload each time.
#: It is now armed on ANY progress (a stdout line, or an ADVANCING worker
#: heartbeat), so the window only has to exceed the heartbeat: 3 x 10 s leaves
#: room for a stalled main loop (the worker runs inference on the same thread
#: that ticks) while still catching a worker that truly stops in 30 s.
#: `_main/restart-30s-oracle.py` asserts the relation mechanically against
#: `worker/sotto_worker.py`, because the two numbers live in two files.
WORKER_SILENCE_MS = 30000


def parse_worker_stats(line):
    """`{'tag': 'tick'|'final', 'fields': {...}, 'line': ...}` or None.

    Values stay STRINGS exactly as the worker printed them: a reader that wants
    `peak` as a float can convert it, and a value the worker never printed stays
    absent instead of becoming a zero this file invented.
    """
    match = WORKER_STATS_RE.match(str(line).strip())
    if not match:
        return None
    fields = {}
    for token in match.group(2).split():
        if '=' in token:
            key, value = token.split('=', 1)
            fields[key] = value
    return {'tag': match.group(1), 'fields': fields,
            'line': str(line).strip()}

# ── hot reload of the WORKER: debounce + guard + floor ──────────────────────
#: Trailing debounce on worker reload requests. `hot_reload.DEBOUNCE_MS` is 250
#: ms of quiet — the WATCHER's window — and it is BELOW the cadence of a
#: cross-lane editing burst: five lanes each saving every 1-3 s reach 250 ms of
#: quiet between consecutive saves, so every save flushed and every flush
#: restarted the worker (the churn this fixes). 2 s of quiet coalesces one
#: lane's save-storm while staying responsive.
WORKER_RELOAD_DEBOUNCE_MS = 2000
#: The owner's rule, verbatim: the model must not leave load "super rapido -
#: faz o model sair de load apos 3 minutos". There is NO idle-unload here to
#: configure (see docs/audit/load-churn.md): the churn was reloads, and a TTL
#: would ADD them. What 180 s bounds instead is the RELOAD RATE. Measured cost
#: of ONE load on this box: 2.0-8.3 s of stall and 1.4-2.1 GB RSS
#: (`worker/runs/*.jsonl`, the `model-loaded` line), so 180 s is ~20x the stall
#: it bounds and the model cannot cycle faster than the owner asked.
WORKER_RELOAD_MIN_INTERVAL_MS = 180000
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
        if verdict not in HEALTHY_DONE_VERDICTS:
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


def mark_launch_ready(path) -> bool:
    """run.cmd's readiness handshake (gap G3): touch `path` once the app is up.

    `run.cmd` `start`s the app detached, so the wrapper can never see any status
    after the spawn -- measured 2026-10-06 a launch logged `STAGING_LOADED` and
    then hung, and `run.cmd` still answered 0 (docs/audit/launch-entry.md §3/§4).
    The wrapper now hands a FRESH path here (`--ready-file`) and waits for it,
    bounded: the file appearing is "the app came up", the bound expiring is a
    HANG and the wrapper exits non-zero. A direct launch (no flag) is a no-op.
    A failure to write it is a WARN, not an exit: the app is up either way, and
    the wrapper's bound is the thing that reports the miss.
    """
    if not path:
        return False
    try:
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'ready pid={os.getpid()}\n')
        return True
    except OSError as exc:  # noqa: BLE001 -- must not take the app down
        warn(f'READY_FILE_FAILED path={path} {exc!r}')
        return False


def wait_ready_file(path, timeout_s: float) -> int:
    """run.cmd's bounded half of G3: poll `path` until it exists, or give up.

    Returns 0 the moment the app has touched the file (it is up), 4 when
    `timeout_s` elapses without it (a HANG -- the app was started and did not
    come up), which is the non-zero the wrapper passes on. The bound is read
    from `SOTTO_READY_BOUND` by the caller so a test can shorten it; the default
    is the wrapper's own.
    """
    deadline = time.time() + max(0.0, timeout_s)
    while True:
        if os.path.exists(path):
            return 0
        if time.time() >= deadline:
            return 4
        time.sleep(0.1)


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


# The `OFFSCREEN = -32000` cure was REMOVED 2026-10-06 (see create_window):
# a window created off-screen never finishes the WebView2 panel navigation, so
# `_on_loaded` never runs and the shell HANGS. Do not reintroduce it.


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
# Alt+C IS THE ONLY CONTROL — so its failure modes get first-class code
# ===========================================================================
#: Tried IN ORDER when the requested accelerator is already owned by another
#: program. `Alt+Shift+<key>` and `Ctrl+Alt+<key>` are the conventional choices
#: precisely because vendors grab the plain ones: on this box `Alt+F9` is already
#: taken (measured 2026-10-07 by `_main/_audit-hotkey-probe.py`, which is also the
#: instrument that proves `Alt+C` itself is FREE here — so a dead Alt+C was never
#: a taken key, and the owner's "Alt+C does nothing" had to be found downstream:
#: a second shell, or a panel path).
HOTKEY_FALLBACKS = ('Alt+Shift+C', 'Ctrl+Alt+C', 'Ctrl+Shift+C')

MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000

#: `CreateMutexW`'s handle, kept for the process lifetime on purpose: the kernel
#: releases it when this process dies, which is what makes "already running" a
#: fact with no stale lock to age out.
_SINGLE_INSTANCE = {'handle': None}


def take_single_instance_lock(name='Local\\SottoShell') -> bool:
    """True when THIS process is the one Sotto shell for this session.

    Alt+C is a GLOBAL key with exactly one owner: a second shell cannot register
    it (`RegisterHotKey` → 1409) and, without this guard, kept running with a dead
    hotkey and an invisible window of its own — so the owner's Alt+C answered the
    FIRST instance, which is how a stale panel that no longer updates looks
    exactly like a broken hotkey. With autostart (`HKCU\\...\\Run`) and a manual
    double-click arriving in the same login, that collision stops being
    hypothetical.

    A FAILED `CreateMutexW` returns True (proceed) and says so: refusing to start
    because a lock could not be created would be worse than a rare double shell.
    """
    try:
        kernel32.CreateMutexW.restype = wt.HANDLE
        handle = kernel32.CreateMutexW(None, False, name)
    except Exception as exc:  # noqa: BLE001 -- never cost the app a start
        log(f'SINGLE_INSTANCE_MUTEX_FAILED error={exc!r}')
        return True
    if not handle:
        log(f'SINGLE_INSTANCE_MUTEX_FAILED winerror={ctypes.get_last_error()}')
        return True
    _SINGLE_INSTANCE['handle'] = handle
    exists = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    log(f'SINGLE_INSTANCE name={name} already_running={str(exists).lower()}')
    return not exists


def warn_hotkey_unavailable(requested: str, tried) -> None:
    """The app's ONLY control could not be registered: say it ON SCREEN, once.

    The panel cannot be the messenger — by definition nothing can open it — so a
    modal dialog is the last channel. It runs on a DAEMON thread, so it blocks
    neither the UI loop nor the worker: the app keeps transcribing while the
    dialog waits to be dismissed. `MB_TOPMOST` because nothing in this shell ever
    takes focus, and the text names every key that was tried plus the one-line
    fix, because "the app is running but you cannot open it" is otherwise
    unfalsifiable from the owner's side.
    """
    lines = ',\n'.join(f'    {a}  (winerror={err})' for a, err in tried) or f'    {requested}'

    def _show():
        text = ('Sotto could not register its global hotkey, so the caption '
                'panel cannot be opened with the keyboard.\n\n'
                'Every accelerator below is already owned by another program:\n'
                f'{lines}\n\n'
                'Sotto is still running and still transcribing. To get the panel, '
                'either close the other program that owns the key, or start Sotto '
                'with a free one:\n\n'
                '    run.cmd --hotkey Alt+Shift+C\n\n'
                '(This message is shown once per launch; nothing is on screen '
                'otherwise.)')
        try:
            user32.MessageBoxW(None, text, 'Sotto — hotkey unavailable',
                               MB_OK | MB_ICONERROR | MB_TOPMOST | MB_SETFOREGROUND)
        except Exception as exc:  # noqa: BLE001 -- a warning must not kill a run
            log(f'HOTKEY_ALERT_FAILED error={exc!r}')

    log('HOTKEY_UNAVAILABLE alert=messagebox tried=' + json.dumps(
        [a for a, _ in tried]))
    threading.Thread(target=_show, name='sotto-hotkey-alert', daemon=True).start()


def arm_hotkey(shell, requested: str):
    """Register `requested`, then the fallbacks; return the live thread or None.

    Why a CHAIN and not one attempt: the shipped behaviour was a single
    `RegisterHotKey`, and its failure was one log line — the app stayed running,
    hidden, with its only control dead, and the owner was shown nothing at all
    (the whole design is "nothing appears until you ask"). A second choice that
    works turns a bricked app into an app with a different key, and the log says
    which one won (`HOTKEY_FALLBACK`) so the panel's own footer stays honest.
    """
    order = [requested] + [a for a in HOTKEY_FALLBACKS if a != requested]
    tried = []
    for accelerator in order:
        thread = HotkeyThread(accelerator, lambda: shell.toggle_panel('hotkey'))
        thread.start()
        thread.wait_ready(5)
        if thread.registered:
            if accelerator != requested:
                warn(f'HOTKEY_FALLBACK requested={requested} using={accelerator} '
                     'reason=requested-owned-by-another-program')
            return thread
        tried.append((accelerator, thread.register_error))
        log(f'HOTKEY_TRY_FAILED accelerator={accelerator} '
            f'winerror={thread.register_error}')
    warn_hotkey_unavailable(requested, tried)
    return None


# ===========================================================================
# start with Windows (HKCU\...\Run) — the owner asked for "iniciar com o windows"
# ===========================================================================
#: The Run value's name: what the owner sees in Task Manager → Startup.
AUTOSTART_VALUE_NAME = 'Sotto'
AUTOSTART_RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'


def autostart_command() -> str:
    """The command Windows should run at login — `pythonw.exe`, never cmd.exe.

    `run.cmd` cannot be the target: a `.cmd` is a console program, so Windows
    would flash a console window at every login, and this project forbids console
    windows on the owner's screen (measured: a stray `python` console was named by
    the house census and complained about twice). `pythonw.exe` is a GUI-subsystem
    binary: no console, no window, and the shell then does exactly what a
    double-click does — including starting the worker (F1).

    Both paths are QUOTED because `C:\\Program Files\\...` contains a space, and
    the log is passed so an autostart that fails leaves a receipt in the same file
    every other launch writes to.
    """
    pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    if not os.path.exists(pythonw):
        pythonw = sys.executable  # a machine with no pythonw: still better than cmd
    shell = os.path.join(HERE, 'sotto_webview.py')
    log_path = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir,
                                             '_main', 'webview-run.log'))
    return f'"{pythonw}" "{shell}" --log "{log_path}"'


def autostart_install() -> int:
    """Write the Run value. Idempotent; prints what it wrote."""
    import winreg  # local: keep this module importable on a box without winreg

    command = autostart_command()
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, AUTOSTART_VALUE_NAME, 0, winreg.REG_SZ,
                              command)
    except OSError as exc:
        print(f'sotto: AUTOSTART_INSTALL_FAILED {exc!r}')
        return 1
    print(f'sotto: AUTOSTART_INSTALLED name={AUTOSTART_VALUE_NAME}')
    print(f'sotto:   HKCU\\{AUTOSTART_RUN_KEY}\\{AUTOSTART_VALUE_NAME} = {command}')
    print('sotto: it starts hidden at login and waits for Alt+C; nothing appears '
          'until you ask.')
    print('sotto: to undo it:  run.cmd --uninstall-autostart')
    log(f'AUTOSTART_INSTALLED command={json.dumps(command)}')
    return 0


def autostart_uninstall() -> int:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, AUTOSTART_VALUE_NAME)
    except FileNotFoundError:
        print('sotto: AUTOSTART_NOT_INSTALLED (nothing to remove)')
        log('AUTOSTART_UNINSTALL name=absent')
        return 0
    except OSError as exc:
        print(f'sotto: AUTOSTART_UNINSTALL_FAILED {exc!r}')
        return 1
    print(f'sotto: AUTOSTART_REMOVED name={AUTOSTART_VALUE_NAME}')
    log('AUTOSTART_REMOVED')
    return 0


def autostart_status() -> int:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY, 0,
                            winreg.KEY_QUERY_VALUE) as key:
            value, _ = winreg.QueryValueEx(key, AUTOSTART_VALUE_NAME)
    except FileNotFoundError:
        print('sotto: AUTOSTART=off (no Run value)')
        return 1
    except OSError as exc:
        print(f'sotto: AUTOSTART_STATUS_FAILED {exc!r}')
        return 2
    matches = os.path.normcase(value) == os.path.normcase(autostart_command())
    print(f'sotto: AUTOSTART=on  value={value}')
    print(f'sotto:   matches this checkout: {matches}  '
          f'(expected: {autostart_command()})')
    return 0 if matches else 3


# ===========================================================================
# the page bridge — the port of app/_legacy-electron/preload.js
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

  // The history store round-trip. Same shape as getInfo's id round-trip, so
  // `history.tail()`/`search()`/`append()` really resolve with disk data
  // instead of handing back a synchronous guess.
  var histSeq = 0;
  var histPending = {};
  window.__sotto_history = function (id, json) {
    var resolve = histPending[id];
    if (!resolve) return;
    delete histPending[id];
    try { resolve(JSON.parse(json)); } catch (err) { resolve({ error: String(err) }); }
  };
  function historyCall(kind, payload) {
    return new Promise(function (resolve) {
      var id = 'h' + (++histSeq);
      histPending[id] = resolve;
      var msg = payload || {};
      msg.id = id;
      post(kind, msg);
    });
  }

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

    // The transcript history ("redux"). The SHELL owns the disk: it names the
    // file, appends the line, reads it back and reveals it in the file manager.
    // `append` resolves with the entry as written (real path included), so the
    // panel never has to guess the folder layout.
    history: {
      append: function (text, meta) {
        return historyCall('history-append',
          { text: String(text == null ? '' : text), meta: meta || {} });
      },
      tail: function (limit) {
        return historyCall('history-tail', { limit: Number(limit) || 400 });
      },
      search: function (query, limit) {
        return historyCall('history-search',
          { query: String(query == null ? '' : query), limit: Number(limit) || 200 });
      },
      root: function () { return historyCall('history-root', {}); },
      reveal: function (path) {
        post('history-reveal', { path: String(path == null ? '' : path) });
      }
    },

    HOTKEY: 'Alt+C',
    platform: 'win32'
  };

  // ── PAGE ERRORS MUST REACH THE LOG, OR A BROKEN PANEL LOOKS LIKE A QUIET ONE ──
  // Measured 2026-10-07, on the owner's screen with a video playing: the worker
  // transcribed for 20+ s at peak 0.44 and the shell logged thousands of
  // `BRIDGE_CAPTION_SENT delivered=true` lines, while the panel kept showing
  // "Starting the worker" and `#caption-list` stayed `display:none`. NOTHING in
  // the log said why: a throw inside panel.js is invisible to Python, because
  // `evaluate_js` reports the CALL, not the page's own JavaScript. This hook runs
  // from document start (before the panel's scripts), so an init-time throw — the
  // case that silently kills every subscription — is reported with its source
  // position and stack.
  function reportPageError(detail) {
    // A BARE resource event is not a panel error: a favicon or stylesheet that
    // 404s fires `error` with no message, no position and no stack, and reporting
    // it would put a fake `PAGE_ERROR` in every launch's log — which is how a
    // word that matters gets trained out of the next reader. Only a real script
    // error (message, position or stack) is reported.
    if (!detail.text || (detail.text === 'error' && !detail.source && !detail.stack)) return;
    try { post('page-error', detail); } catch (e) { /* nothing left to report with */ }
  }
  window.addEventListener('error', function (event) {
    reportPageError({
      text: String((event && (event.message || (event.error && event.error.message))) || 'error'),
      source: String((event && event.filename) || ''),
      line: Number((event && event.lineno) || 0),
      col: Number((event && event.colno) || 0),
      stack: String((event && event.error && event.error.stack) || '')
    });
  }, true);
  window.addEventListener('unhandledrejection', function (event) {
    var reason = event && event.reason;
    reportPageError({
      text: 'unhandledrejection: ' + String((reason && reason.message) || reason || ''),
      source: 'promise',
      line: 0,
      col: 0,
      stack: String((reason && reason.stack) || '')
    });
  });
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

#: The v2 acceptance probes. `exec_js` here does NOT await a returned Promise
#: (measured 2026-10-06: an async IIFE came back as `{}`), so the probe is split
#: into three SYNCHRONOUS reads that the shell sequences with real waits. The
#: waits are the point: the caption has to survive the formulation hold
#: (COMMIT_MAX_HOLD_MS = 1500 ms) before it commits and is written, and the
#: search is a bridge round-trip. `__STAMP__` is replaced by the shell with a
#: unique token, so the caption, its history line and the search that finds it
#: are tied together by one string instead of by timing luck.
PANEL_V2_INJECT = r"""
(() => {
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  const history = document.getElementById('history');
  const captions = document.getElementById('captions');
  const out = {
    url: location.href,
    shape: {
      history: !!history,
      live: !!captions,
      liveBox: !!document.getElementById('captions-body'),
      liveList: !!document.getElementById('caption-list'),
      // LIVE comes FIRST and the transcript drawer follows it (the live box is
      // the product and takes the space; see `panel.html`'s own comment on the
      // section order). This arm used to assert the OPPOSITE — `historyAboveLive`
      // — and the panel reorder of 2026-10-07 (F2/D1: a transcript that cannot
      // fill is collapsed UNDER the captions) would have made a stale arm RED
      // for the right change. `captions` precedes `history`, so history FOLLOWS.
      liveAboveHistory: !!(history && captions &&
        (captions.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING)),
    },
    buttons: {
      search: !!document.getElementById('search-button'),
      searchInput: !!document.getElementById('search-input'),
      reveal: !!document.getElementById('reveal-button'),
      revealLabel: txt(document.getElementById('reveal-button')).trim(),
    },
    historyApi: !!(window.sotto && window.sotto.history &&
      typeof window.sotto.history.tail === 'function' &&
      typeof window.sotto.history.search === 'function' &&
      typeof window.sotto.history.reveal === 'function'),
  };
  return out;
})()
"""

PANEL_V2_READ_LIVE = r"""
(() => {
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  const input = document.getElementById('search-input');
  input.value = '__STAMP__';
  document.getElementById('search-form').requestSubmit();
  return {
    live: {
      lines: qa('#caption-list .caption__text').map((e) => e.textContent),
      count: (document.getElementById('caption-list') || {}).childElementCount,
      placeholderHidden: !!(document.getElementById('placeholder') || {}).hidden,
      // The panel DISABLES the search input while no canonical producer exists
      // (nothing could match, and a search box that cannot work is a promise
      // with no backend). Read here so the transcript arm below can require the
      // honest state instead of inventing a hit.
      searchInputDisabled: !!(document.getElementById('search-input') || {}).disabled,
    },
    feed: qa('#history-list .hist__text').map((e) => e.textContent),
    feedFolderButtons: qa('#history-list .hist__folder').length,
    rootLabel: txt(document.getElementById('history-root')).trim(),
    searched: true,
  };
})()
"""

PANEL_V2_READ_SEARCH = r"""
(() => {
  const q = (s) => document.querySelector(s);
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  return {
    search: {
      hits: qa('#history-list .hist').length,
      texts: qa('#history-list .hist__text').map((e) => e.textContent),
      marked: !!q('#history-list mark'),
      note: txt(document.getElementById('history-status')).trim(),
      folderButtons: qa('#history-list .hist__folder').length,
    },
  };
})()
"""

#: The panel's LIVE box and footer, read back as TEXT — the read a screenshot
#: makes, in text. It reports each line's own state (provisional vs committed),
#: which is the one thing the shell cannot know from the IPC receipts alone: a
#: provisional line is rewritten in place by `panel.js` and never leaves the DOM.
PANEL_STATE_PROBE = r"""
(() => {
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  const list = document.getElementById('caption-list');
  const status = document.getElementById('status');
  const lines = list ? Array.from(list.children).map((li) => {
    const body = li.querySelector('.caption__text');
    return {
      text: body ? body.textContent : txt(li),
      provisional: li.classList.contains('caption--provisional'),
      latest: li.classList.contains('caption--latest'),
    };
  }) : null;
  const ph = document.getElementById('placeholder');
  const pt = document.querySelector('.captions__placeholder-title');
  const pb = document.querySelector('.captions__placeholder-body');
  return {
    url: location.href,
    live: {
      count: list ? list.childElementCount : -1,
      lines: lines,
      provisionalCount: lines
        ? lines.filter((line) => line.provisional).length : -1,
      hint: txt(document.getElementById('captions-hint')).trim(),
      hidden: list ? !!list.hidden : null,
      // THE FOLLOW, AS THREE NUMBERS. The owner's report was *"a transcricao nao
      // ta dando auto scroll no painel"* and no existing field could confirm or
      // refute it: `count` says how many lines exist, not whether the newest one
      // is on screen. `atBottom` is the exact predicate the panel's own follow
      // rule uses, read from the element that actually scrolls
      // (`#captions-body`, whose CSS is `overflow-y: auto`).
      scroll: (() => {
        const box = document.getElementById('captions-body');
        if (!box) return null;
        const scrollTop = box.scrollTop;
        const scrollHeight = box.scrollHeight;
        const clientHeight = box.clientHeight;
        return {
          top: scrollTop,
          height: scrollHeight,
          client: clientHeight,
          atBottom: (scrollHeight - scrollTop - clientHeight) < 48,
          overflowing: scrollHeight > clientHeight + 4,
        };
      })(),
    },
    status: {
      text: txt(document.getElementById('status-text')).trim(),
      kind: status
        ? (status.classList.contains('status--error') ? 'error'
          : status.classList.contains('status--live') ? 'live' : 'busy')
        : null,
    },
    placeholder: {
      hidden: ph ? !!ph.hidden : null,
      title: txt(pt).trim(),
      body: txt(pb).trim(),
    },
  };
})()
"""


class PanelVisibilityWriter:
    """Publish "is the panel on screen" to a file, on every transition AND on a
    cadence. The worker polls it; nothing else consumes it.

    THE CONTRACT (frozen shape — the worker's reader is built against it):

        {
          "schema": "sotto.panel-visibility/1",
          "visible": <bool>,        # window_visible(hwnd), MEASURED
          "since_ms": <int>,        # epoch ms at which THIS state began
          "age_ms": <int>,          # ms this state had lasted AT WRITE (0.0-style
                                    # "age at write": the authoritative duration is
                                    # `now_ms - since_ms`, computed by the READER)
          "pid": <int>,             # the SHELL's pid — the producer
          "reason": "<str>",        # the transition that opened this state
          "transitions": <int>,     # counted, so "it switched" is a number
          "writtenAt": "<iso>",
          "writtenAtEpoch": <float>,
          "staleAfterSeconds": <float>
        }

    WHY BOTH `since_ms` AND `age_ms`. The worker's question is "hidden for longer
    than N seconds". `since_ms` answers it absolutely and survives a reader that
    samples late; `age_ms` is the same fact as of the write and is what a human
    reading the file wants. A single field would have to be one of the two, and
    every reader downstream would have to guess which — the ambiguity that made a
    previous generation of this repo's probes disagree with each other.

    WHY A THREAD. The transition writes come from the UI thread (`show_panel`/
    `hide_panel`) and MUST NOT wait on a file. The cadence write runs here, every
    `interval_s`, re-reading the live window: that is what turns a map/unmap that
    happened WITHOUT going through `show_panel`/`hide_panel` — pywebview's own
    navigation-time `Show`, `_reassert_hidden`, a hot reload — into a recorded
    transition instead of a silent divergence between the file and the screen.
    """

    def __init__(self, path, observe, log=lambda _m: None,
                 interval_s=PANEL_VISIBILITY_INTERVAL_S):
        self.path = path
        #: `observe()` -> bool, read LIVE from the window at call time.
        self.observe = observe
        self.log = log
        self.interval_s = max(0.5, float(interval_s))
        self.visible = None
        self.since_ms = None
        self.reason = 'boot'
        self.transitions = 0
        self.writes = 0
        self.errors = 0
        self._stop = threading.Event()
        self._thread = None

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> bool:
        if self._thread is not None:
            return False
        # Order matters for a reader grepping this log: the ANNOUNCEMENT (which
        # names the path a reader must open) comes first, then the boot dump —
        # the same order `PanelStateWriter.start()` uses. The thread is started
        # LAST so the boot dump is deterministically the first write and the first
        # transition line carries `reason=boot` rather than a cadence tick's
        # `poll`.
        self.log(f'PANEL_VISIBILITY_WRITER path={self.path} '
                 f'interval_s={self.interval_s}')
        self.write('boot')
        self._thread = threading.Thread(target=self._loop,
                                        name='sotto-panel-visibility',
                                        daemon=True)
        self._thread.start()
        return True

    def stop(self, reason='stop') -> None:
        self._stop.set()
        self.log(f'PANEL_VISIBILITY_WRITER_STOP reason={reason} '
                 f'writes={self.writes} transitions={self.transitions} '
                 f'errors={self.errors}')

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            # Reason `poll`: this state was reached without a show/hide call, or
            # the call's write already happened and this is the same state — the
            # writer only logs a transition when the VALUE moved, so a steady
            # panel produces no transition lines at all.
            self.write('poll')

    # -- one publication ---------------------------------------------------
    def write(self, reason='poll', visible=None) -> bool:
        observed = bool(self.observe()) if visible is None else bool(visible)
        now_ms = int(time.time() * 1000)
        if self.visible is None:
            # The FIRST write is a transition: the state the panel came up in is
            # a fact worth exactly one line, and it is the one a reader needs to
            # know how long the run has been in it.
            self.visible = observed
            self.since_ms = now_ms
            self.reason = reason
            self.transitions += 1
            self._log_transition(reason)
        elif observed != self.visible:
            self.visible = observed
            self.since_ms = now_ms
            self.reason = reason
            self.transitions += 1
            self._log_transition(reason)
        payload = {
            'schema': PANEL_VISIBILITY_SCHEMA,
            'visible': self.visible,
            'since_ms': self.since_ms,
            'age_ms': now_ms - self.since_ms,
            'pid': os.getpid(),
            'reason': self.reason,
            'transitions': self.transitions,
            'writtenAt': panel_state.now_iso(),
            'writtenAtEpoch': round(time.time(), 3),
            'ageSecondsNote': (
                'age_ms is the age AT WRITE; the authoritative duration is '
                '(now_ms - since_ms) and is computed by the READER'),
            'staleAfterSeconds': round(max(self.interval_s * 3.0, 5.0), 2),
        }
        try:
            panel_state.write_atomic(self.path, payload)
        except Exception as exc:
            self.errors += 1
            self.log(f'PANEL_VISIBILITY_WRITE_FAILED path={self.path} '
                     f'error={exc!r}')
            return False
        self.writes += 1
        return True

    def _log_transition(self, reason) -> None:
        # ONE line per transition, in the shape a reader greps for. `reason` is
        # the CALLER's word (`hotkey`, `--show`, `hot-reload`, `navigation`,
        # `page`, `boot`) or `poll` when the window moved without a call — a
        # distinction that matters: `poll` means the file is the ONLY record the
        # transition happened, which is precisely when a silent divergence
        # would otherwise go unnoticed.
        self.log(f'PANEL_VISIBILITY_MODE '
                 f'visible={str(bool(self.visible)).lower()} reason={reason} '
                 f'transitions={self.transitions} since_ms={self.since_ms}')


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
            'page-error': self._page_error,
            'pointer': self._pointer,
            'history-append': self._history_append,
            'history-tail': self._history_tail,
            'history-search': self._history_search,
            'history-root': self._history_root,
            'history-reveal': self._history_reveal,
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

    def _page_error(self, payload):
        """A THROW INSIDE THE PANEL, on the record.

        The panel's errors used to be unobservable from Python: `evaluate_js`
        reports the CALL, so a `TypeError` inside `panel.js` left the shell
        logging healthy `BRIDGE_CAPTION_SENT delivered=true` lines while the
        owner looked at a panel frozen on its placeholder. This is the channel
        that names it — with position and stack, because "the panel is broken" is
        not actionable and "panel.js:187 TypeError: bridge.onCaption is not a
        function" is. Kept at warning level: the app keeps running, but a page
        that threw is the reason nothing on screen is moving.
        """
        payload = payload or {}
        warn(f'PAGE_ERROR text={json.dumps(str(payload.get("text", "")))} '
             f'at={payload.get("source") or "?"}:{payload.get("line") or 0}:'
             f'{payload.get("col") or 0} '
             f'stack={json.dumps(str(payload.get("stack", ""))[:400])}')

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

    # -- history (the "redux" store) ---------------------------------------
    def _history_reply(self, payload, result):
        history_id = (payload or {}).get('id', '')
        if history_id:
            self._shell.reply_history(history_id, result)

    def _history_append(self, payload):
        payload = payload or {}
        entry = self._shell.history_append(
            payload.get('text', ''), payload.get('meta'))
        self._history_reply(payload, {'entry': entry})

    def _history_tail(self, payload):
        payload = payload or {}
        self._history_reply(
            payload, self._shell.history_tail(int(payload.get('limit') or 400)))

    def _history_search(self, payload):
        payload = payload or {}
        self._history_reply(payload, self._shell.history_search(
            payload.get('query', ''), int(payload.get('limit') or 200)))

    def _history_root(self, payload):
        self._history_reply(payload or {}, self._shell.history_root())

    def _history_reveal(self, payload):
        self._shell.reveal_in_folder((payload or {}).get('path'))


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
        # True once the "hide unless the owner asked" guard is subscribed to the
        # control's NavigationStarting. It is the precondition of the panel being
        # hidden at startup, and it is armed in `_on_before_show` — see
        # `_arm_visibility_invariant`.
        self.visibility_armed = False
        # True once pywebview's OWN mapping call (`form.Show()`) has been
        # refused at the form instance — see `_gate_form_show`. Counts the maps
        # refused, so "the gate is on the shipped path" is a number in the log
        # and not a claim.
        self.panel_show_refused = 0
        self.pointer_interactive = False
        self.caption_log = []
        self.last_status = ''
        self.bridge_installed = None  # None until measured, True/False after
        self.renderer_ready = threading.Event()
        self.exiting = threading.Event()
        self.bridge = None            # WorkerBridge
        # A file change in `worker/` does NOT restart the worker directly: it
        # is queued and the policy decides (debounce, mid-stream guard, 180 s
        # floor). See WorkerReloadPolicy and docs/audit/load-churn.md.
        self._reload_policy = WorkerReloadPolicy(
            log_fn=log,
            get_bridge=lambda: self.bridge,
            restart=self._do_worker_restart,
        )
        self.hotkey = None
        self.hot_reload = None       # hot_reload.HotReload
        #: The panel AS TEXT: the periodic dump writer (panel_state.py). None
        #: until the panel's first load, which is when the DOM can be read.
        self.panel_state = None
        #: THE VISIBILITY CHANNEL (PanelVisibilityWriter). Armed at the same
        #: moment as `panel_state` and BEFORE the worker can be spawned, because
        #: the worker's mode switch polls this file: a worker that starts while
        #: the file does not exist yet would read "unknown" and — by the
        #: fail-safe — stream, which is the correct default but is NOT the
        #: honest answer once the file exists.
        self.panel_visibility = None
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
            # CREATED AT ITS REAL GEOMETRY. An off-screen creation
            # (`x=OFFSCREEN, y=OFFSCREEN`, OFFSCREEN=-32000) was tried
            # 2026-10-06 as the flash cure and MEASURED BROKEN: WebView2 does
            # not complete the stage->panel navigation for a window parked at
            # -32000, so `_on_loaded` never fires and the shell HANGS before
            # the panel loads (measured, no --exit-after, 9 s: log stops at
            # `STAGING_LOADED`, no `PRELOAD_ACTIVE`, no `RECEIVER_READY`). It
            # also broke the `--exit-after` probes the same way. Do not
            # reintroduce it. The startup flash is handled by `_reassert_hidden`
            # on `NavigationStarting`.
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
        # DO NOT clear `self.window.transparent` here. Tried 2026-10-06 and
        # MEASURED WRONG: pywebview's navigation `Show()` (edgechromium.py:347,
        # gated by `transparent`) is what makes a transparent WebView2 actually
        # LOAD; clearing the flag makes the stage->panel navigation never
        # complete, so `_on_loaded` never fires and the shell HANGS (measured
        # `_main/_flash-live-0.log`: stops at `STAGING_LOADED`, rc=-999, never
        # reaches PANEL_VISIBILITY_ON_SCREEN). Transparency must stay on. The
        # startup flash is handled by the OFFSCREEN creation position below.
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

        # THE MAPPING CALL IS REFUSED HERE. pywebview maps this form itself on
        # EVERY navigation start (`platforms/edgechromium.py:345-349`):
        #
        #     if self.pywebview_window.transparent:
        #         self.form.Show()
        #         self.form.Activate()
        #
        # `transparent` is ON by default in this shell (`--opaque` is the only
        # way off), so that call undoes `hidden=True` — and it is a call the
        # shell does not make and cannot order against. `_reassert_hidden`
        # (subscribed to the same event, right after) SHORTENS the window that
        # call maps; it cannot prevent the map, because the two run in the same
        # dispatch but the map is what the dispatch is doing. Measured by
        # `_main/panel-startup-flash-census.py` at a 25 ms cadence: the form was
        # WS_VISIBLE and NOT alpha-occluded in 1 of 6 launches even with the
        # re-assert in place. See `_gate_form_show`.
        self._gate_form_show(form)

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
        # THE VISIBILITY INVARIANT IS ARMED HERE, NOT IN `_on_core_ready`.
        # See `_arm_visibility_invariant` for why the two are separate
        # subscriptions; TICKET-55a4ab4b157bdd26bb9629c7 is what it costs to
        # let one registration be a side effect of the other.
        self._ui(self._arm_visibility_invariant)
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

    def _gate_form_show(self, form):
        """Refuse pywebview's own mapping call unless the owner asked.

        THE DEFECT THIS CLOSES. `Show` is a `System.Windows.Forms.Form` method,
        but pywebview calls it from PYTHON — `self.form.Show()`
        (`platforms/edgechromium.py:348`) — so an attribute set on the INSTANCE
        shadows it for exactly that call and nothing else. Measured:
        `_main/_pythonnet-show-shadow-test.py` → `instance: base.Show() ->
        INSTANCE-GATED`, with `type(base).Show` still the CLR method.

        WHY A GATE HERE AND NOT ANOTHER NET. Every previous cure re-hid the
        window AFTER pywebview mapped it, so the window was mapped and the only
        question was how long. This refuses the map itself. It changes NO
        subscription, which matters: `_main/panel-hidden-at-startup-oracle.py`
        asserts `NavigationStarting handlers=2 (1 pywebview + 1 shell)`, and
        that assertion keeps its exact meaning.

        WHY IT CANNOT COST THE OWNER THE PANEL. The shell has its OWN way to map
        the window — `show_panel` → `user32.ShowWindow(SW_SHOWNOACTIVATE)` — and
        BOTH user paths take it: Alt+C (`toggle_panel` → `show_panel`) and
        `--show` (`_on_loaded` → `self.show_panel('startup')`). Neither path
        calls `form.Show()`, so neither is refused.

        WHY THE CREATION DANCE IS STILL ALLOWED. pywebview's `hidden=True`
        branch (`platforms/winforms.py:777-781`) runs `Opacity=0; Show(); Hide();
        Opacity=1`. At that moment the form is FULLY TRANSPARENT, so its map is
        invisible by construction (the house already accepts this class: the
        `--opaque` arm's only catches are `alpha=0`, AGENTS.md). Refusing it
        would change the state the shipped app has always started in for no
        measured gain, so it is let through — the test is `Opacity < 1.0`, read
        from the form itself, not a shell flag that could drift out of step.
        """
        original = form.Show

        def guarded_show():
            try:
                opacity = float(form.Opacity)
            except Exception:
                opacity = 1.0
            if self.args.show or self.visible or opacity < 1.0:
                return original()
            self.panel_show_refused += 1
            log(f'PANEL_SHOW_REFUSED reason=not-asked opacity={opacity} '
                f'show_requested={str(bool(self.args.show)).lower()} '
                f'panel_shown={str(bool(self.visible)).lower()} '
                f'count={self.panel_show_refused} '
                'cure=_gate_form_show source=edgechromium.py:348')
            return None

        # An instance attribute shadows the CLR method for a PYTHON-side call
        # (measured, see the docstring). The delegate pywebview subscribed is a
        # method of ITS object and is untouched.
        form.Show = guarded_show
        log('PANEL_SHOW_GATE installed=true method=BrowserForm.Show '
            'refuses=map-at-full-opacity-unless-asked')

    def _arm_visibility_invariant(self):
        """Subscribe the hide-unless-asked guard, ONCE, as its own act.

        THE INVARIANT. pywebview asks for a transparent window and, on EVERY
        navigation, un-hides it itself: `if self.pywebview_window.transparent:
        self.form.Show(); self.form.Activate()`
        (edgechromium.py:346-349). That hack is load-bearing — clearing
        `transparent` stops the page loading at all (measured, see
        `create_window`) — so the shell's only defence is to re-hide the window
        immediately afterwards. `_on_navigation_start` is that defence, and its
        REGISTRATION is the entire invariant: with it absent the panel sits on
        the owner's desk while every internal flag still says "hidden".

        WHY IT IS ARMED HERE AND NOT IN `_on_core_ready`. Reading the installed
        pywebview (`platforms/edgechromium.py`, `platforms/winforms.py`):

          * `winforms.py:773` builds the form; `EdgeChrome.__init__` subscribes
            pywebview's handlers and calls `EnsureCoreWebView2Async(None)`
            (`edgechromium.py:101-102`, `:120`) — async, result discarded. The
            CONTROL exists; CoreWebView2 does not.
          * `winforms.py:775` fires `before_show`. This is therefore the last
            point that provably precedes EVERY navigation.
          * navigation #1 is raised from INSIDE the initialization-completed
            dispatch: `on_webview_ready` is what calls `load_url`
            (`edgechromium.py:305-311`), and pywebview subscribed that handler
            BEFORE the shell's `_on_core_ready`.

        So arming from `_on_core_ready` is a registration that is not merely
        late — it is registered by a callback the shell does not control, and
        when that callback does not arrive, `NavigationStarting` has no handler
        and nothing re-hides the window. That is the whole of
        TICKET-55a4ab4b157bdd26bb9629c7: the cure was reachable only through
        an unrelated subscription, so deleting one line left the panel visible
        while `py_compile` stayed at rc=0. Arming here removes the dependency;
        it also covers navigation #1, which the old registration could not.

        The guard is a precondition, not a best-effort: a control that is not
        there is a RAISE (this method runs before any navigation can, so the
        control must exist), never a silent return.
        `_main/panel-hidden-at-startup-oracle.py` holds the invariant by
        construction and fails if this registration ever stops being on the
        shipped path.
        """
        if self.visibility_armed:
            return
        if self.webview2 is None:
            raise RuntimeError(
                'PANEL_VISIBILITY_INVARIANT cannot be armed: no WebView2 '
                'control. Every navigation would be shown by pywebview with '
                'nothing to re-hide it.')
        # `+=` cannot live in a lambda (see `_subscribe_core_ready`), which is
        # why this is a method and not an inline statement.
        self.webview2.NavigationStarting += self._on_navigation_start
        self.visibility_armed = True
        log('PANEL_VISIBILITY_INVARIANT armed=true where=before_show '
            f'hwnd={self.hwnd}')

    def _on_core_ready(self, sender, args):
        """CoreWebView2 exists: install the preload-equivalent.

        Registration is per-ENVIRONMENT, not per-page, so registering while the
        staging page is the current document covers the panel's navigation too.

        IT NO LONGER SUBSCRIBES `NavigationStarting`. That registration was
        moved to `_arm_visibility_invariant`, called from `_on_before_show`,
        on 2026-10-06 for TICKET-55a4ab4b157bdd26bb9629c7. The reasoning it
        recorded here was correct about WHY the guard must sit on the
        CONTROL's `NavigationStarting` and not the CoreWebView2's — pywebview
        subscribes the same control event in `EdgeChrome.__init__`
        (edgechromium.py:102) and .NET raises handlers in subscription order,
        so pywebview's `form.Show()` (edgechromium.py:346-349) runs first and
        this handler runs immediately after it in the same dispatch; on a
        different forward the order is a race, and the re-assert was measured
        losing it and leaving the panel on screen. The error was the WORD
        "before the first page is loaded": this handler does not run before the
        first page is loaded, because navigation #1 is raised from inside this
        very dispatch (pywebview's `on_webview_ready` calls `load_url`,
        edgechromium.py:305-311). Keeping the registration here made the cure
        conditional on this callback arriving at all.
        """
        if not args.IsSuccess:
            log(f'WEBVIEW2_INIT_FAILED error={args.InitializationException}')
            return
        self.core = sender.CoreWebView2
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
        # NOTE: `_move_into_place` (the OFFSCREEN cure) was removed 2026-10-06:
        # creating the window at -32000 broke the panel load, and its move-back
        # left the panel VISIBLE at startup (measured: PANEL_VISIBILITY_ON_SCREEN
        # visible=true). Geometry is fixed at creation instead.
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

        # G3: the panel navigation has just completed. That is exactly the
        # boundary the 2026-10-06 hang never crossed -- it logged
        # `STAGING_LOADED`, its `load_url(panel)` never came back, there was no
        # `PRELOAD_ACTIVE`, and run.cmd still answered 0 (launch-entry.md §3/§4).
        # run.cmd's bounded wait keys on this file (see mark_launch_ready); the
        # file appearing is the wrapper's "the app came up".
        mark_launch_ready(self.args.ready_file)

        # Startup actions run ONCE per process, not once per navigation. A hot
        # reload re-enters this function; without this guard `--with-worker`
        # would spawn a SECOND worker and `--selftest` would run twice, so a
        # panel save would quietly multiply the thing the panel is for.
        if not self.startup_done:
            self.startup_done = True
            self.send_geometry()
            # The panel AS TEXT. Armed here — once the panel document (not the
            # staging page) has loaded — so the DOM read has something to read.
            # See panel_state.py and docs/audit/painel-texto.md.
            self.start_panel_state()
            # THE VISIBILITY CHANNEL — armed BEFORE `start_worker` below, in
            # this same block, so a worker spawned on this launch always finds
            # the file. The order is the point: see `self.panel_visibility`.
            self.start_panel_visibility()
            if self.args.show:
                self.show_panel('startup')
            self._measure_on_screen_visibility('startup')
            # -- F1: the worker starts by DEFAULT --------------------------
            # `docs/audit/auditoria-completa-20261007.md` F1: the documented
            # launch started no worker at all, so Alt+C showed a panel that
            # claimed to be waiting for audio with no capture process in
            # existence. The flag is now the OPT-OUT.
            #
            # THE DECISION IS MADE IN A STATED ORDER, most explicit first, and
            # the reason string is what the log carries (`WORKER_AUTOSTART
            # started/declined reason=…`, the same shape every existing reader
            # parses):
            #   1. --with-worker          -> force ('with-worker'). AUTHORITATIVE:
            #      a lane or script that wants the worker in a measurement keeps
            #      working, because the suppression below is only reached when
            #      this flag is absent.
            #   2. --no-worker            -> opt out ('no-worker')
            #   3. SOTTO_NO_WORKER=1      -> opt out ('env')
            #   4. a MEASUREMENT FLAG     -> decline
            #      ('measurement-flag(<flag>)'). The set is the flags that name a
            #      measurement, not transcription:
            #        --dump-dom   measures the panel's DOM and exits
            #        --selftest   proves the hotkey toggles and exits
            #        --memory     prints the host RSS and exits
            #        --no-hotkey  the shell's own help calls it "for MEASUREMENT
            #                     runs", and a real run cannot work without
            #                     Alt+C, so it is a reliable signal
            #        --exit-after a bound for a BOUNDED probe run
            #      WHY IT MATTERS: such a run would otherwise pay a ~2 GB model
            #      load and open an audio tap on every launch, and several
            #      oracles point the shell at a temp tree whose worker path does
            #      not exist -- churn plus restart backoff against an assertion
            #      about the panel, which is how a default turns into a
            #      regression for the instruments. Checked against every call
            #      site that needs the worker FOR REAL: `_main/_app-drive.py`
            #      (`--with-worker --probe-v2`), `_main/_live-launch.py`
            #      (`--with-worker`) and a plain double-click (no flags) -- none
            #      of them relies on `--exit-after` alone.
            #   5. otherwise              -> start ('default')
            # The table itself lives in `_worker_autostart_reason` so the rule
            # can be asserted without a WebView2 (see `_main/_lane1-*.py`).
            worker_reason = self._worker_autostart_reason(self.args)
            # EVERY path goes through `start_worker`, so a refusal takes the
            # SAME `WORKER_AUTOSTART=declined reason=…` line a silent failure
            # does and no reader has to learn a second shape. `start_worker`
            # declines by itself when a bridge already exists, and nothing
            # added here takes `self._lock`.
            self.start_worker(worker_reason)
            # -- D3: no worker means the panel must say so ------------------
            # The panel's shipped footer says "Idle · no audio source", which
            # claims the machine has no audio -- measured false (there IS audio;
            # what is missing is the PROCESS). Without F1 cured, no status ever
            # arrived either, so the claim stood for the whole session. One
            # status now, through the same path every worker status takes, so
            # both the placeholder and the footer stop claiming a wait that
            # cannot end -- and it NAMES THE FLAG, because "no worker" with the
            # flag in hand is a decision the owner can undo in one argument.
            #
            # Only the two opt-outs and a measurement flag get it: the panel the
            # owner reads must not claim a wait when the shell KNOWS there is no
            # worker. The sentence NAMES THE FLAG, because "no worker" with the
            # flag in hand is a decision he can undo in one argument -- "no audio
            # source" never said that.
            off_message = self._worker_off_message(worker_reason)
            if off_message:
                text, info = off_message
                self.apply_panel_state(text, 'error', info)
            if self.args.probe_v2 > 0:
                timer = threading.Timer(self.args.probe_v2,
                                        self.run_panel_v2_probe)
                timer.daemon = True
                timer.start()
                log(f'PANEL_V2_PROBE_WAIT s={self.args.probe_v2}')
            elif self.args.dump_dom:
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
        # ── NO RE-SHOW HERE. REMOVED ON PURPOSE (2026-10-07) ──────────────────
        # This was `if self.visible: self.show_panel('hot-reload')`. The owner
        # reported *"eu to tentando tirar ele da minha tela e ele respawna"*, and
        # this call is the respawn: every time a lane saved a file under
        # `app/panel/**` the shell re-navigated and RE-MAPPED the panel — a
        # second path to the very map `_gate_form_show` exists to refuse, running
        # AFTER the navigation where nothing can order against it.
        #
        # It is also unnecessary. pywebview re-maps the form on every navigation
        # start and the gate refuses that; a window that was VISIBLE is still
        # visible after a re-navigation (the content re-renders by itself), and a
        # window that was HIDDEN must stay hidden. So the correct action is:
        # assert the state the owner chose, and never the opposite.
        #
        # NOTE FOR WHOEVER READS THE F5 RECEIPT: the machine proof of the staging
        # bounce used to include a `PANEL_SHOWN reason=hot-reload` line. That line
        # no longer appears — by design. The reload is still proved by
        # `HOT_RELOAD_APPLIED reload=N` plus the panel loading the real document
        # (the `panel-state.json` `url` and a non-negative `live.count`).
        if not self.visible:
            self._reassert_hidden()
            log('HOT_RELOAD_KEPT_HIDDEN reason=owner-had-it-hidden '
                f'reload={self.reload_count}')

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

    def send_status(self, text, kind=''):
        """Status wire: `{'text': <str>, 'kind': <str>}` — F8 + D3, frozen.

        `docs/audit/auditoria-completa-20261007.md` F8: the bridge already HAS
        the severity (`WorkerBridge` classifies every worker status) and the
        panel threw it away and re-classified the sentence with a regex, so two
        classifiers decided one status and the panel's guess is the one the
        owner sees. The kind now travels WITH the text, as an OBJECT, through
        the existing `emit('status', …)` path — one source of truth. The object
        is plain JSON-serializable strings and nothing more; `panel.js` (other
        lane) reads `.kind` when it is there and falls back to the sentence.
        The page side tolerates a bare string too, so a stale shell cannot
        break a panel that has already been updated.
        """
        self.last_status = text
        self.emit('status', {'text': str(text), 'kind': str(kind or '')})

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

        # The SAME kind travels to the page twice, deliberately: in the status
        # object (`send_status`, which `panel.js` reads) and in the placeholder
        # write below, which is the shell's own direct paint of the severity.
        # One value, both readers — see `send_status` for why the panel must not
        # re-classify the sentence with a regex.
        self.send_status(line, kind)
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

    # -- the panel as TEXT -------------------------------------------------
    def panel_state_snapshot(self, reason='periodic'):
        """Everything the panel shows NOW, as plain data — see panel_state.py.

        Called by the writer thread every `PANEL_STATE_INTERVAL_S` and on the
        request sentinel. The DOM half is read over the SAME `exec_js` seam the
        probes use — the read a screenshot makes, in text — and the worker half
        is the bridge's own already-held state. Nothing here starts a process or
        a window, and nothing here changes what the owner sees.
        """
        dom = None
        if self.core is not None:
            dom = self.exec_js(PANEL_STATE_PROBE, timeout=5.0)
        bridge = self.bridge
        worker = bridge.snapshot() if bridge is not None else None
        panel_status = ((dom or {}).get('status') or {}).get('text')
        return {
            'namedState': self._named_panel_state(worker, panel_status),
            'panel': dom,
            'shell': {
                'visible': self.visible,
                'hotkey': self.args.hotkey,
                'rendererReady': self.renderer_ready.is_set(),
                'bridgeInstalled': self.bridge_installed,
                'lastStatus': self.last_status,
                'captionLogCount': len(self.caption_log),
                'reloadCount': self.reload_count,
                'workerPath': self.args.worker,
                'log': getattr(_LOG_FILE, 'name', None),
                'hotReload': self.hot_reload is not None,
            },
            # The visibility channel, as data, beside the two facts it is built
            # from: `shell.visible` (the window, this instant) and the file the
            # worker polls. A reader comparing them can see the channel drift or
            # refuse it; a reader that trusts only the file cannot.
            'panelVisibility': self.panel_visibility_snapshot(),
            'worker': worker,
        }

    @staticmethod
    def _named_panel_state(worker, panel_status):
        """One name for "what is the panel showing", by a STATED precedence.

        The panel's OWN footer wins while it is live — `panel.js` writes
        `Receiving captions` the moment a caption commits — because that is the
        sentence the owner reads. Below it fall the worker's failure vocabulary,
        then the bridge's own no-audio verdict. `no-worker` is a real state, not
        an empty string: a panel with no bridge is not the same panel as one
        holding a quiet worker.
        """
        if panel_status == 'Receiving captions':
            return 'receiving'
        if worker is None:
            return 'no-worker'
        pending = worker.get('pendingError') or {}
        if pending.get('state'):
            return str(pending['state'])
        state = str(worker.get('state') or '')
        if state in WORKER_ERROR_STATES:
            return state
        if worker.get('noAudio'):
            return NO_AUDIO_STATE
        return state or 'idle'

    def start_panel_visibility(self):
        """Arm the visibility channel. Idempotent per process.

        The observer is the WINDOW, read at call time: `window_visible(hwnd)` is
        the same `IsWindowVisible` every other visibility decision in this file
        is built from, so the file and the screen cannot disagree by
        construction. When there is no window yet the answer is False and the
        first real window is a transition — which is exactly the fact the worker
        needs (nothing on screen yet => nothing to go live for).
        """
        if self.panel_visibility is not None:
            return False
        self.panel_visibility = PanelVisibilityWriter(
            path=PANEL_VISIBILITY_PATH,
            observe=self.observe_panel_visible,
            log=log,
            interval_s=PANEL_VISIBILITY_INTERVAL_S,
        )
        return self.panel_visibility.start()

    def observe_panel_visible(self) -> bool:
        """The LIVE answer: is the panel window on screen right now?"""
        hwnd = self.hwnd
        return False

    def publish_panel_visibility(self, reason):
        """Record a visibility transition the moment it happens.

        Called from the SHOW/HIDE calls themselves, so the file changes within
        the same instant as the window rather than up to `interval_s` later: a
        worker that is being switched by this file must not be told "hidden" a
        tick after the owner pressed Alt+C. Silent when the arm was never made
        (a measurement run that never loaded the panel) — the cadence writer is
        the only other writer, and it takes the same path.
        """
        writer = self.panel_visibility
        if writer is None:
            return False
        return writer.write(reason)

    def panel_visibility_snapshot(self):
        """The channel as DATA, for the panel-state dump and for probes."""
        writer = self.panel_visibility
        if writer is None:
            return None
        return {
            'path': PANEL_VISIBILITY_PATH,
            'visible': writer.visible,
            'since_ms': writer.since_ms,
            'reason': writer.reason,
            'transitions': writer.transitions,
            'writes': writer.writes,
            'errors': writer.errors,
        }

    def start_panel_state(self):
        """Arm the periodic + on-request dump. Idempotent per process."""
        if self.panel_state is not None:
            return False
        self.panel_state = panel_state.PanelStateWriter(
            path=PANEL_STATE_PATH,
            request_path=PANEL_STATE_REQUEST,
            snapshot=self.panel_state_snapshot,
            log=log,
            interval_s=PANEL_STATE_INTERVAL_S,
        )
        return self.panel_state.start()

    # -- history: the "redux" store, on disk --------------------------------
    # Layout: `<root>/<YYYY-MM-DD>/<HH>.md` — a 24 h folder, one file per hour,
    # appended as captions commit. The shell owns the path (the panel is handed
    # the entry back), so the folder convention lives in exactly one place.
    def history_root(self):
        """The history store's root, and whether a canonical producer exists.

        FROZEN SHAPE (other lanes read it): `{'root': <path>,
        'canonicalProducer': None}`.

        `canonicalProducer` is `None` because of the audit's **F2**
        (`docs/audit/auditoria-completa-20261007.md`): `app/panel/
        history-source.js:51` accepts a canonical line only when its meta
        carries `producer === 'redux'`, and NO engine in this repo ever stamps
        `producer` — the live path builds its meta with three literal keys
        (`caption-formulation.js:408`), and the batch engine that could stamp it
        (Parakeet Redux) is neither on disk nor called. So the transcript cannot
        fill: the feed is decorative and the search has nothing to search. The
        shell says so HERE, as data, instead of the panel inferring it from an
        empty list; `panel.js` (other lane) uses it to collapse the feed and
        disable the search. It becomes a producer NAME only if a production
        call site starts stamping one.
        """
        return {'root': HISTORY_ROOT, 'canonicalProducer': None}

    def _history_path_for(self, when):
        return os.path.join(
            HISTORY_ROOT,
            time.strftime('%Y-%m-%d', when),
            time.strftime('%H', when) + '.md',
        )

    @staticmethod
    def _history_provenance(options):
        """The `<!-- route=… start=… reason=… -->` suffix for one line (M8).

        WHY IT EXISTS: `formulate()` appends terminal punctuation to every line
        the renderer commits, so a fragment the panel abandoned after 1500 ms
        and a sentence the worker actually closed were byte-identical in this
        file. The route is what tells them apart; `start` is the worker's own
        line identity (`worker/sotto_worker.py:_event`), so a line here can be
        lined up with the worker's `start=` in its JSONL, and `reason` is the
        rule that fired at the instant of the write.

        It is written ON the line, and NOT into `entry['text']`: the feed and
        the search show the sentence, the file carries the provenance.
        """
        if not isinstance(options, dict):
            return ''
        route = str(options.get('route') or '').strip()
        if route not in HISTORY_ROUTES:
            return ''
        parts = [f'route={route}']
        start = options.get('start')
        if isinstance(start, (int, float)) and not isinstance(start, bool):
            parts.append(f'start={float(start):.2f}')
        # WHICH branch decided the route (M9). Written AFTER `start=` so every
        # existing `route=… start=…` reader keeps its capture. `src=fallback`
        # is the de-landing announcing itself (P1 `4fb5b25380cbc8269977e22e`).
        src = str(options.get('routeSource') or '').strip()
        if src in HISTORY_ROUTE_SOURCES:
            parts.append(f'src={src}')
        reason = re.sub(r'\s+', ' ', str(options.get('reason') or '')).strip()
        if reason:
            parts.append(f'reason={reason}')
        return ' <!-- ' + ' '.join(parts) + ' -->'

    def history_append(self, text, options=None):
        """Append ONE committed caption. Returns the entry as written, or None."""
        body = re.sub(r'\s+', ' ', str(text or '')).strip()
        if not body:
            return None
        # HISTORICO-VS-REDUX GUARD — OWNER 2026-10-06: the transcript carries
        # ONLY a line the WORKER closed (`route=final`). The panel already
        # declines a `provisional-draft` (panel.js `recordHistory`); this is the
        # same invariant at the store, so no other caller can put the LIVE
        # caption in the owner's transcript. The LIVE caption stays in the box.
        # See docs/audit/historico-vs-redux.md.
        if isinstance(options, dict) and str(options.get('route') or '').strip() == 'provisional-draft':
            return None
        now = time.localtime()
        path = self._history_path_for(now)
        entry = {
            'date': time.strftime('%Y-%m-%d', now),
            'hour': time.strftime('%H', now),
            'time': time.strftime('%H:%M:%S', now),
            'text': body,
            'path': path,
        }
        provenance = self._history_provenance(options)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'a', encoding='utf-8') as handle:
                handle.write(f'- [{entry["time"]}] {body}{provenance}\n')
        except OSError as exc:  # noqa: BLE001 -- a write miss must not kill the app
            warn(f'HISTORY_APPEND_FAILED path={json.dumps(path)} error={exc!r}')
            return None
        log(f'HISTORY_APPEND path={json.dumps(path)} time={entry["time"]} '
            f'bytes={len(body.encode("utf-8"))}')
        return entry

    def _history_files(self):
        """Every hour file under the root, OLDEST first: [(date, hour, path)]."""
        out = []
        try:
            days = sorted(name for name in os.listdir(HISTORY_ROOT)
                          if HISTORY_DAY_RE.match(name))
        except OSError:
            return out
        for day in days:
            folder = os.path.join(HISTORY_ROOT, day)
            try:
                hours = sorted(name for name in os.listdir(folder)
                               if name.endswith('.md'))
            except OSError:
                continue
            for name in hours:
                out.append((day, name[:-3], os.path.join(folder, name)))
        return out

    def _history_read(self, path):
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                return handle.read().splitlines()
        except OSError as exc:  # noqa: BLE001 -- an unreadable hour is skipped
            warn(f'HISTORY_READ_FAILED path={json.dumps(path)} error={exc!r}')
            return []

    def _history_entries(self):
        """NEWEST-first stream of entries. Reverse file order AND line order, so
        a `tail()` really returns the last N written, not the first N of the
        newest file."""
        for day, hour, path in reversed(self._history_files()):
            for line in reversed(self._history_read(path)):
                match = HISTORY_LINE_RE.match(line)
                if match:
                    # The provenance comment is the FILE's, not the feed's:
                    # strip it so search and the feed still see the sentence
                    # (M8 — see `_history_provenance`).
                    yield {'date': day, 'hour': hour, 'time': match.group(1),
                           'text': HISTORY_TAIL_RE.sub('', match.group(2)).strip(),
                           'path': path}

    def history_tail(self, limit=400):
        limit = max(1, int(limit))
        entries = []
        for entry in self._history_entries():
            entries.append(entry)
            if len(entries) >= limit:
                break
        entries.reverse()  # back to oldest-first for the feed
        return {'entries': entries, 'root': HISTORY_ROOT}

    def history_search(self, query, limit=200):
        needle = str(query or '').strip().lower()
        hits = []
        if needle:
            for entry in self._history_entries():
                if needle in entry['text'].lower():
                    hits.append(entry)
                    if len(hits) >= max(1, int(limit)):
                        break
        return {'query': query, 'hits': hits, 'root': HISTORY_ROOT}

    def reply_history(self, history_id, payload):
        self.exec_js(f'window.__sotto_history({json.dumps(history_id)}, '
                     f'{json.dumps(json.dumps(payload))})')

    def reveal_in_folder(self, path):
        """Open the OS file manager at the entry's FILE, or at the root.

        `explorer /select,"<file>"` for a file, `explorer "<dir>"` for a folder.
        CREATE_NO_WINDOW is mandatory: a helper that flashes a console on the
        owner's desktop is the exact defect this house refuses. A path outside
        the history root is REFUSED rather than opened — a reveal that can be
        pointed anywhere is a foot-gun, even from a trusted page.
        """
        raw = str(path or '').strip().strip('"')
        root_real = os.path.abspath(HISTORY_ROOT)
        if raw:
            target = os.path.abspath(raw)
            # Compare CASE-INSENSITIVELY (normcase) but keep the ORIGINAL case
            # for the command and the log: Explorer is case-insensitive, and a
            # lower-cased path in the receipt reads like a different folder.
            root_key = os.path.normcase(root_real)
            key = os.path.normcase(target)
            if key != root_key and not key.startswith(root_key + os.sep):
                warn(f'REVEAL_REFUSED path={json.dumps(raw)} '
                     f'reason=outside-history-root')
                return False
        else:
            target = root_real
        if not os.path.exists(target):
            warn(f'REVEAL_MISSING path={json.dumps(target)}')
            return False
        is_file = os.path.isfile(target)
        shown = os.path.normpath(target)
        command = (f'explorer /select,"{shown}"' if is_file
                   else f'explorer "{shown}"')
        try:
            subprocess.Popen(command, creationflags=CREATE_NO_WINDOW)
        except OSError as exc:  # noqa: BLE001 -- report, never crash the panel
            warn(f'REVEAL_FAILED path={json.dumps(shown)} error={exc!r}')
            return False
        log(f'REVEAL_IN_FOLDER path={json.dumps(shown)} select={str(is_file).lower()}')
        return True

    # -- pointer -----------------------------------------------------------
    def set_pointer_interactive(self, active):
        """Interactive while the mouse is over a control; click-through after.

        F9 (`docs/audit/auditoria-completa-20261007.md`, `sotto_webview.py:
        1474-1476`): `_on_before_show` puts `WS_EX_NOACTIVATE` on the window and
        `show_panel` shows it with `SW_SHOWNOACTIVATE`, which is RIGHT for
        appearance -- Alt+C must not steal focus from whatever the owner is
        typing into. It was WRONG for the interactive state: a `WS_EX_NOACTIVATE`
        window is not brought to the foreground by a click either, so the panel
        could never take keyboard focus at all and its `<input type="search"
        id="search-input">` could never receive a character -- typing with the
        panel in front sent the keys to the app BEHIND it. Both bits are now
        cleared on entry and restored on leave, so the only moment the panel can
        be activated is the moment the owner has his mouse on one of its
        controls. `show_panel`'s `SW_SHOWNOACTIVATE` is untouched: appearing
        still steals nothing.
        """
        if self.hwnd is None:
            return False
        click_through = not active
        # `noactivate` is the flag the page-side drive reads back; it is False
        # exactly while the pointer is over a control. Both calls take the
        # same value on Windows' side (`& ~flag` and `| flag`), so this is one
        # state change expressed in two styles, never two competing ones.
        try:
            if active:
                set_ex_style(self.hwnd, remove=WS_EX_NOACTIVATE)
            else:
                set_ex_style(self.hwnd, add=WS_EX_NOACTIVATE)
        except Exception as exc:  # noqa: BLE001 -- report, never kill the panel
            log(f'POINTER_INTERACTIVE_STYLE_FAILED error={exc!r}')
        make_click_through(self.hwnd, click_through)
        self.pointer_interactive = bool(active)
        log(f'POINTER_INTERACTIVE active={str(bool(active)).lower()} '
            f'click_through={str(click_through).lower()} '
            f'noactivate={str(not active).lower()}')
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

        MEASURED 2026-10-06: this pair is NOT the cure. `_main/
        panel-startup-flash-census.py` samples the shell's OWN pid tree every
        25 ms over 20 launches, and with BOTH halves in place the window was
        still caught on screen in **11 of 20 launches, longest 57.7 ms**. The
        pair SHORTENS the flash; it does not close it, because both halves run
        on a DIFFERENT event than the `Show()` they are undoing.

        The OFF-SCREEN creation that was meant to CLOSE it (`x=OFFSCREEN`,
        `OFFSCREEN = -32000`) was tried and REMOVED the same day: a window
        created at -32000 never finishes the WebView2 panel navigation, so the
        shell hung after STAGING_LOADED, `PRELOAD_ACTIVE`/`WORKER_AUTOSTART`
        were never reached and the app produced NOTHING — the flash was traded
        for a dead app, and the move-back left the panel VISIBLE at startup
        anyway (`PANEL_VISIBILITY_ON_SCREEN visible=true`). See the note in
        So this handler is the SECOND net, not the first: it hides the window
        the instant a navigation Shows it, and it does nothing when the owner
        asked for the panel (`--show`, or Alt+C).

        CORRECTED 2026-10-07. This paragraph used to end "It SHORTENS the flash;
        it does not close it", and that was measured true of the re-assert
        ALONE. The map itself is now refused before it happens: `_gate_form_show`
        (installed from `_on_before_show`) replaces the form INSTANCE's `Show`
        with a guard, so pywebview's `self.form.Show()` at full opacity never
        runs unless the owner asked. Measured by
        `_main/panel-startup-flash-census.py` at a 25 ms cadence, N=20 per arm:
        `_main/receipt-20261007-panel-startup-flash.md`. The closed form is kept
        because it is still the only net if the gate is ever removed, and
        because a `Show` from anywhere OTHER than that Python call would still
        be caught here.
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
        # A hide the owner did NOT ask for is still a hide, and the worker's
        # stack law is about the screen, not about intent. Published here so the
        # file cannot lag the window on this path either; the cadence writer
        # would otherwise catch it up to `interval_s` later.
        self.publish_panel_visibility('reassert-hidden')

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
        # The worker goes back to STREAMING on this line — see the stack law at
        # `PANEL_VISIBILITY_PATH`. `self.visible` is the MEASURED value above,
        # so a Show that silently failed publishes "still hidden" and the worker
        # stays on the batch path rather than switching to a panel nobody can
        # see.
        self.publish_panel_visibility(reason)
        return True

    def hide_panel(self, reason):
        if self.hwnd is None:
            return False
        hide_window(self.hwnd)
        self.visible = window_visible(self.hwnd)
        log(f'PANEL_HIDDEN reason={reason} '
            f'visible={str(self.visible).lower()}')
        self.publish_panel_visibility(reason)
        return True

    def toggle_panel(self, reason):
        """Show if hidden, hide if shown — decided by the WINDOW, not by a cache.

        `self.visible` is only updated when THIS object shows or hides the panel,
        and two other paths map or unmap the window behind its back: pywebview's
        own navigation-time `form.Show()` (gated) and `_reassert_hidden`. A stale
        `True` makes the owner's first Alt+C a no-op HIDE of a panel he cannot
        see — i.e. "Alt+C does nothing" until he presses it twice, and the log
        blames `reason=hotkey` in both directions. One `IsWindowVisible` removes
        the whole class; it is also what the cheap `--selftest` two-state check
        reads, so the two can no longer disagree.
        """
        live = window_visible(self.hwnd) if self.hwnd else False
        if live != self.visible:
            log(f'PANEL_VISIBILITY_CACHE_STALE cached={str(self.visible).lower()} '
                f'live={str(live).lower()} decided_by=window')
        self.visible = live
        return (self.hide_panel(reason) if live else self.show_panel(reason))

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
        if self.panel_state is not None:
            self.panel_state.stop('exit')
        if self.panel_visibility is not None:
            # A last write, so a worker still polling during the shell's exit
            # reads a FRESH answer rather than a stale one: this is the write
            # that turns "the shell is gone" into "the worker stops believing
            # me" via `staleAfterSeconds`, instead of the worker obeying the
            # last state it happens to hold.
            self.panel_visibility.write('exit')
            self.panel_visibility.stop('exit')
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
    @staticmethod
    def _worker_off_message(reason):
        """D3: the honest sentence for a shell with NO worker, or None.

        `panel.html:189` ships `Idle · no audio source`, and D3 of
        `docs/audit/auditoria-completa-20261007.md` names it for what it is: a
        FALSE claim. There is audio on this box (measured, `_main/listen-probe.py`
        and the routing law); what is missing is the PROCESS. With F1 cured the
        shell knows exactly why there is no worker, so it says so.

        Naming the flag is the point: "no worker" with the flag in hand is a
        decision the owner (or a lane) can undo in one argument, and
        `reason` is the same string the launch logged, so the log line and the
        painted sentence cannot disagree.

        Returns `(text, info)` for `apply_panel_state`, or `None` for a reason
        that must NOT paint anything: `with-worker` and `default` have a worker,
        and a measurement run (`measurement-flag(…)`) keeps the NEUTRAL panel its
        instrument is measuring -- a status fired into an instrument's DOM would
        be the shell changing the thing under measurement.
        """
        if reason == 'no-worker':
            sent_by = '--no-worker'
        elif reason == 'env':
            sent_by = 'SOTTO_NO_WORKER=1'
        elif reason.startswith('measurement-flag('):
            sent_by = reason[len('measurement-flag('):-1]
        else:
            return None
        return (
            f'No transcription worker is running (started with {sent_by})',
            {'title': 'No worker · captions are impossible',
             'body': f'This shell was started with {sent_by}, so no audio is '
                     'being captured. Start it without that flag (run.cmd, the '
                     'documented entry) to transcribe.'},
        )

    @staticmethod
    def _worker_autostart_reason(args, env=None):
        """F1: should the worker auto-start, and WHY — as one of five strings.

        `docs/audit/auditoria-completa-20261007.md` F1: the documented launch
        (`run.cmd`) started no worker at all, so Alt+C opened a panel claiming to
        wait for audio with no capture process in existence. The worker now
        starts by DEFAULT; the flag is the OPT-OUT.

        The return value is the `reason=` field of the
        `WORKER_AUTOSTART=started|declined reason=…` line, and `'default'` is the
        only value that starts it:

          `'with-worker'`      the flag was passed — AUTHORITATIVE, so a lane or
                               a script that wants the worker in a measurement
                               keeps working
          `'no-worker'`        `--no-worker`: shell only
          `'env'`              `SOTTO_NO_WORKER=1` in the environment
          `'measurement-flag(…)'` a mode that measures the panel or the shell,
                               not transcription: `--dump-dom`, `--selftest`,
                               `--memory`, `--no-hotkey` (the shell's own help
                               calls it "for MEASUREMENT runs", and a real run
                               cannot work without Alt+C) and `--exit-after` (a
                               bound for a BOUNDED probe run). Without this, a
                               plain probe launch would pay a ~2 GB model load
                               and open an audio tap on every arm.
          `'default'`          nothing said otherwise — start it

        Precedence is the order above, most explicit first. Checked against every
        call site that needs a worker FOR REAL: `_main/_app-drive.py`
        (`--with-worker --probe-v2`), `_main/_live-launch.py` (`--with-worker`)
        and a plain double-click (no flags) — none relies on `--exit-after`
        alone. Factored out of `_on_loaded` so the rule is assertable without a
        WebView2 (see `_main/_lane1-worker-default-arms.py`).
        """
        if getattr(args, 'with_worker', False):
            return 'with-worker'
        if getattr(args, 'no_worker', False):
            return 'no-worker'
        env = os.environ if env is None else env
        if str(env.get('SOTTO_NO_WORKER') or '').strip() == '1':
            return 'env'
        # `--exit-after` is a FLOAT (0.0 = off) and the rest are `store_true`;
        # truthiness is correct for both and keeps this one readable table.
        for flag, name in (('dump_dom', '--dump-dom'),
                           ('selftest', '--selftest'),
                           ('memory', '--memory'),
                           ('no_hotkey', '--no-hotkey'),
                           ('exit_after', '--exit-after')):
            if getattr(args, flag, False):
                return f'measurement-flag({name})'
        return 'default'

    #: The reasons that may SPAWN a worker. Everything else is the decline half of
    #: `_worker_autostart_reason`, which NAMES why; this tuple is what makes the
    #: name binding. `hot-reload` is here because a file change must restart the
    #: worker it already had (the reload policy decides WHEN, not whether).
    START_REASONS = ('default', 'with-worker', 'hot-reload')

    def start_worker(self, reason):
        if reason not in self.START_REASONS:
            # ── THE RULE'S BINDING HALF, AND IT WAS MISSING UNTIL NOW ─────────
            # `_worker_autostart_reason` was computed at the call site and then
            # DISCARDED: this method started a worker for any reason string, so a
            # `--dump-dom` / `--selftest` / `--memory` / `--no-hotkey` /
            # `--exit-after` launch paid a ~2 GB model load (the exact cost the
            # suppression set exists to avoid), and the D3 path told the panel
            # "No transcription worker is running (started with --dump-dom)"
            # WHILE a worker was loading. Both instruments that passed — the
            # 15-arm rule probe and the adversary lane's 22-arm sweep — test the
            # RULE, so neither could see the wiring; it was found by reading this
            # call site on 2026-10-07. `_main/_audit-worker-start-wiring.py` now
            # gates precisely this pair.
            log(f'WORKER_AUTOSTART=declined reason={reason} by=start_worker')
            return False
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
        # A status line is the boundary signal: an exit/`done`/`error` closes
        # the capture guard, so a reload held mid-stream can land here.
        self._reload_policy.boundary()

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

        THE MECHANISM IS THE STAGING BOUNCE, and it is not a cache-busting
        trick: this re-runs `stage.html` -> `panel.html`, the SAME navigation
        pair that brings the panel up at startup and is therefore already known
        to land on the real document. `_on_loaded` sees `staged == False`, does
        the staging navigation, and on the next load takes the panel branch and
        its `HOT_RELOAD_APPLIED` half; the `startup_done` guard keeps the
        once-per-process startup actions (geometry is re-sent by that branch,
        the worker is NOT respawned, `--selftest` does not run twice) from
        running again. The document that arrives is a fresh parse of the fresh
        bytes, which is what a `file://` stylesheet gets no guarantee of.

        WHY THE OLD MECHANISM WAS WRONG — `docs/audit/auditoria-completa-
        20261007.md` F5, measured and reproduced twice on 2026-10-06. It built

            url = file_url(PANEL_HTML) + f'?sotto_hr={self.reload_count}'

        i.e. a QUERY STRING on a `file://` URL, and `?` is not a legal Windows
        filename character, so the navigation failed and the pane landed on
        `chrome-error://chromewebdata/` — Chromium's OWN error page. The
        receipts are `_main/panel-state.json` reading `panel.url =
        chrome-error://chromewebdata/` with `panel.live.count = -1`, which is
        `PANEL_STATE_PROBE`'s sentinel for `#caption-list` ABSENT. The feature
        therefore destroyed the thing it exists to refresh: after any panel-file
        edit the panel stopped painting, the owner's transcript stopped growing
        with it, and only a shell restart brought it back. Any cache-busting
        that changes the URL of a `file://` document is out for the same reason.

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
        # `self.staged`, NOT `self._staged`: `_on_loaded` reads the public one to
        # decide whether the current document is the staging page. Setting a
        # misspelled twin here looked correct and did nothing, so the reload
        # re-ran the staging navigation and the panel came up on stage.html.
        # It is set to False (NOT True, as the old code did): False is what
        # makes `_on_loaded` perform the staging bounce instead of treating
        # stage.html as if it were already the panel.
        self.staged = False

        def _go():
            self.window.load_url(file_url(STAGE_HTML))

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
        """Queue a worker reload. The POLICY decides if and when it may run.

        The old body restarted on the spot, which is the churn the owner saw:
        with five lanes editing `worker/sotto_worker.py` all morning and a
        250 ms watcher window that ends between their saves, every save cost a
        full worker respawn — i.e. a model load (2.0-8.3 s, 1.4-2.1 GB, measured
        in `worker/runs/*.jsonl`). The reload is now debounced, and it is HELD
        while a capture stream is open. See `WorkerReloadPolicy`.
        """
        if self.bridge is None:
            log(f'HOT_RELOAD_WORKER_SKIPPED files={json.dumps(files)} '
                'reason=no-worker-running')
            return False
        return self._reload_policy.request(files)

    def _do_worker_restart(self, files):
        """The one place a hot reload actually stops and restarts the worker."""
        if self.bridge is None:
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
        self._reload_policy.stop()

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

    def run_panel_v2_probe(self):
        """PROVE the v2 panel end to end, from the page itself.

        Three SYNCHRONOUS reads over the REAL page and the REAL bridge, spaced
        by real waits: inject a caption through `window.sotto.pushCaption` (the
        channel the worker drives), let the formulation hold expire, read the
        live box and the feed, drive a UI search, then read the search results.
        The disk half is read back through the shell's OWN store, so the feed
        and the file on disk are checked by two independent paths tied to the
        same unique token.
        """
        stamp = 'SOTTO-V2-' + str(int(time.time() * 1000))
        injected = self.exec_js(PANEL_V2_INJECT) or {}
        # The LIVE caption is driven through the REAL worker path — the very
        # `on_worker_caption` the WorkerBridge calls — so this exercises
        # worker -> shell -> emit('caption') -> preload -> panel.js -> live box
        # -> history -> disk, not a shortcut around the bridge.
        caption = 'A legenda ao vivo ' + stamp + '.'
        self.on_worker_caption(caption, {'start': 0, 'end': 2})
        time.sleep(3.0)  # COMMIT_MAX_HOLD_MS (1500) + the append round-trip
        live = self.exec_js(PANEL_V2_READ_LIVE.replace('__STAMP__', stamp)) or {}
        time.sleep(1.5)  # the search round-trip
        search = self.exec_js(PANEL_V2_READ_SEARCH) or {}

        tail = self.history_tail(5)
        search_api = self.history_search(stamp, 5)

        # The reveal guard, exercised WITHOUT opening a window: a path outside
        # the history root must be REFUSED and a missing path must be reported.
        # The success case is a real `explorer` spawn (what the button does) and
        # is deliberately NOT run here — it would put a File Explorer window on
        # the owner's desktop.
        out_reveal = {
            'outside': self.reveal_in_folder(
                os.path.join(HISTORY_ROOT, os.pardir, 'sotto_webview.py')),
            'missing': self.reveal_in_folder(
                os.path.join(HISTORY_ROOT, '1999-01-01', '00.md')),
        }

        out = dict(injected)
        out.update(live)
        out.update(search)
        out['stamp'] = stamp
        out['tail'] = tail
        out['searchApi'] = search_api
        out['revealGuard'] = out_reveal

        shape = out.get('shape') or {}
        buttons = out.get('buttons') or {}
        livebox = out.get('live') or {}
        results = out.get('search') or {}
        feed_hit = any(stamp in str(t) for t in (out.get('feed') or []))
        disk_hit = any(stamp in str(e.get('text', ''))
                       for e in (tail.get('entries') or []))
        api_hit = bool((search_api.get('hits') or []))

        # ── THE TRANSCRIPT HALF IS CONDITIONAL, AND NAMES THE BRANCH IT TOOK ──
        # The four arms below (`feed_hit`, `results.hits > 0`, `disk_hit`,
        # `api_hit`) are the ORIGINAL ones, and they can only pass while a
        # canonical producer exists: the transcript accepts a line only if
        # `meta.producer` is literally `redux` (`history-source.js:51,61-63`) and
        # NOTHING in this repo stamps that field, so today the feed is empty and
        # the disk takes no line (audit F2; `_main/history-producer-gate.js`
        # measures exactly this and names it `no-producer-in-tree`).
        #
        # Kept as an unconditional conjunction, this probe was a gate that could
        # not say yes: `--probe-v2` would exit 3 on a panel that is WORKING, and
        # the exit would be read as the panel being broken. So the arm branches on
        # the capability the shell itself publishes (`history_root()`'s
        # `canonicalProducer`), asserts the HONEST state of each branch, and
        # reports which one it took in `transcriptBranch` — a green here always
        # means "the panel did what the pipeline allows", never "the transcript
        # works".
        canonical = self.history_root().get('canonicalProducer')
        if canonical:
            transcript_ok = bool(feed_hit and results.get('hits', 0) > 0
                                 and disk_hit and api_hit)
        else:
            # Nothing can fill it: the honest expectations are an EMPTY feed, an
            # EMPTY disk, a search that found nothing — and a search INPUT the
            # panel has disabled, because a search box that cannot match is worse
            # than no search box.
            transcript_ok = bool(
                not feed_hit and not disk_hit and not api_hit
                and results.get('hits', 0) == 0
                and livebox.get('searchInputDisabled')
            )
        out['transcriptBranch'] = 'canonical' if canonical else 'no-producer-in-tree'
        out['transcriptOk'] = transcript_ok

        out['ok'] = bool(
            shape.get('history') and shape.get('live')
            and shape.get('liveAboveHistory') and shape.get('liveBox')
            and buttons.get('search') and buttons.get('reveal')
            and out.get('historyApi')
            and livebox.get('count', 0) > 0
            and transcript_ok
            and out_reveal['outside'] is False
            and out_reveal['missing'] is False
        )
        log('PANEL_V2_PROBE ' + json.dumps(out, separators=(',', ':'),
                                           ensure_ascii=False))
        log(f'PANEL_V2_GATE={"GREEN" if out["ok"] else "RED"}')
        self.request_exit(0 if out['ok'] else 3, reason='panel-v2-probe')
        return out

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
# the worker bridge — the port of app/_legacy-electron/worker-bridge.js
# ===========================================================================


class WorkerReloadPolicy:
    """Decide whether a settled worker-file change MAY restart the worker.

    The watcher (`hot_reload.py`) decides WHEN a burst has settled; this decides
    whether that settled burst is allowed to cost a worker restart — and, if it
    is not, that it is QUEUED rather than dropped. Three rules, in order:

      1. DEBOUNCE — a trailing window (`WORKER_RELOAD_DEBOUNCE_MS`) coalesces a
         cross-lane save burst into ONE request.
      2. GUARD    — a worker that is mid-stream (capture open, the state the
         owner watches) is NEVER restarted under his feet. The reload is held
         and lands at the next boundary: a natural respawn re-reads the file,
         and that satisfied request is logged as APPLIED_AT_BOUNDARY rather than
         costing a second restart.
      3. FLOOR    — the owner's 3 minutes (`WORKER_RELOAD_MIN_INTERVAL_MS`): the
         model cannot leave load more often than once per 180 s.

    It is a class, not three methods on the shell, for one reason: the guard is
    the thing that was missing, so it must be drivable from a probe against real
    files without booting WebView2 (see `--probe-reload`). `get_bridge` is the
    single seam — it returns the live `WorkerBridge` (or `None`), and the probe
    returns a stand-in exposing the SAME two fields the policy reads.
    """

    def __init__(self, log_fn, get_bridge, restart,
                 debounce_ms=WORKER_RELOAD_DEBOUNCE_MS,
                 min_interval_ms=WORKER_RELOAD_MIN_INTERVAL_MS):
        self.log = log_fn
        self.get_bridge = get_bridge
        self.restart = restart
        self.debounce_ms = debounce_ms
        self.min_interval_ms = min_interval_ms
        self.pending = None          # files of the newest unapplied request
        self.pending_since = 0.0
        self._timer = None
        self._last_applied_at = 0.0  # monotonic time of the last reload we ran
        self._stopped = False

    # -- requests ----------------------------------------------------------
    def request(self, files):
        """A settled burst: queue it and arm/reset the trailing debounce."""
        if self._stopped:
            return False
        self.pending = list(files)
        self.pending_since = time.monotonic()
        self._arm(self.debounce_ms)
        self.log(f'HOT_RELOAD_WORKER_QUEUED files={json.dumps(self.pending)} '
                 f'debounce_ms={self.debounce_ms} '
                 f'min_interval_ms={self.min_interval_ms}')
        return True

    def boundary(self):
        """A worker status arrived: if a request is held, try to land it.

        Called from `on_worker_status` on every status line — including the
        exit line — so the deferred reload is not waiting on a timer that may
        never fire while the worker is down.
        """
        if self._stopped or self.pending is None:
            return
        br = self.get_bridge()
        if br is not None and br.is_capturing():
            return                    # still mid-stream: keep holding it
        self._arm(self.debounce_ms)

    def stop(self):
        self._stopped = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    # -- internals ---------------------------------------------------------
    def _arm(self, delay_ms):
        if self._stopped:
            return
        if self._timer is not None:
            self._timer.cancel()
        timer = threading.Timer(max(0, delay_ms) / 1000.0, self._fire)
        timer.daemon = True
        self._timer = timer
        timer.start()

    def _fire(self):
        if self._stopped or self.pending is None:
            return
        files = self.pending
        br = self.get_bridge()
        if br is None:
            # No worker at all: a file change must NOT spawn a 2 GB process
            # nobody asked for (main.js:624 states the same law).
            self.pending = None
            self.log(f'HOT_RELOAD_WORKER_SKIPPED files={json.dumps(files)} '
                     'reason=no-worker-running')
            return
        if br.is_capturing():
            self.log(f'HOT_RELOAD_WORKER_DEFERRED files={json.dumps(files)} '
                     'reason=capturing -- applies at the next boundary')
            return                    # pending stays; boundary() re-arms

        # A natural respawn already re-read the file. If it happened AFTER this
        # request was queued, the request is satisfied — do not restart again
        # (that double restart is itself churn).
        spawned_at = float(getattr(br, 'spawned_at', 0.0) or 0.0)
        if br.child is None or spawned_at >= self.pending_since:
            self.pending = None
            self.log(f'HOT_RELOAD_WORKER_APPLIED_AT_BOUNDARY '
                     f'files={json.dumps(files)} reason=respawn-reread-file')
            return

        if self._last_applied_at <= 0.0:
            # The floor counts from the INITIAL model load, not from the first
            # hot-reload request: the model has already paid one load.
            self._last_applied_at = spawned_at or time.monotonic()
        left_ms = self.min_interval_ms - int(
            (time.monotonic() - self._last_applied_at) * 1000)
        if left_ms > 0:
            self.log(f'HOT_RELOAD_WORKER_COOLDOWN files={json.dumps(files)} '
                     f'left_ms={left_ms} min_interval_ms={self.min_interval_ms}')
            self._arm(left_ms)
            return

        self.pending = None
        self._last_applied_at = time.monotonic()
        self.log(f'HOT_RELOAD_WORKER_RESTART files={json.dumps(files)} '
                 f'after_idle_ms={self.min_interval_ms}')
        self.restart(files)


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
                 on_caption=None, on_status=None, silence_ms=WORKER_SILENCE_MS,
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
        #: True from the `capture-started` status until the child stops/exits.
        #: This is the guard's input: a worker with an OPEN capture stream must
        #: not be restarted by a file change (owner: "o modelo loading ta toda
        #: hora saindo de load").
        self.capturing = False
        #: Monotonic time of the last spawn, so a queued reload can tell whether
        #: a natural respawn already re-read the file (WorkerReloadPolicy).
        self.spawned_at = 0.0
        # The last failure this worker reported, and the death the panel is
        # currently obliged to keep showing. `pending_error` is set by a
        # non-zero exit and cleared only by a CAPTION: a restart that has
        # produced no caption has proved nothing, so it must not clear it.
        self.last_error = None
        self.pending_error = None
        #: True once THIS child has published its own verdict that the audio it
        #: opened carries nothing to transcribe (see WORKER_NO_AUDIO_STATES /
        #: WORKER_NO_AUDIO_VERDICTS). Reset on every spawn, because the verdict
        #: is a fact about the CHILD that measured it, not about the shell. Read
        #: by `_on_silence`: a child that has said this is quiet because the
        #: machine is quiet, so the watchdog re-arms instead of killing it.
        self.no_audio = False
        #: What the child said, verbatim, for the log and for the UI state.
        self.no_audio_evidence = None
        self.deaths = 0
        self.stderr_tail = []
        #: The last `WORKER_STATS` line the worker printed on stderr, parsed.
        #: That stream is the ONLY place `peak`/`nonzero_blocks` are published,
        #: and this bridge already reads it (for `stderr_tail`) — the line was
        #: dropped after three, which is why those numbers were unreachable from
        #: outside the process. Kept whole for the panel-state text dump.
        self.last_worker_stats = None
        #: The last status that NAMED an endpoint (`device`, `capture-started`,
        #: `device-rotated`, `device-exhausted`, `silent-device`). The panel shows
        #: the device inside a human sentence; the raw fields are kept here so the
        #: dump can say WHICH endpoint is tapped without parsing prose.
        self.last_device_status = None
        #: The highest `blocks=` the CURRENT child has published in a
        #: `WORKER_STATS` line. The watchdog is armed against NO PROGRESS, and
        #: this counter advancing IS progress (see `_note_progress`). Reset per
        #: child: the counter starts again at 0, so a value left over from the
        #: dead process would suppress every re-arm of the new one.
        self._progress_blocks = None
        self._silence_timer = None
        self._restart_timer = None
        self._lock = threading.Lock()

    # -- state -------------------------------------------------------------
    def is_capturing(self):
        """True while an audio stream is open on the worker.

        Read by `WorkerReloadPolicy` WITHOUT the lock: it is a single boolean
        read, and taking the lock here would deadlock `_spawn` (which calls
        `_arm_silence` with the lock held and must stay lock-free on its way
        out — see the note there).
        """
        return bool(self.capturing) and self.child is not None

    def snapshot(self):
        """The bridge's OWN state as plain data, for the panel-state text dump.

        Read-only and cheap: it copies fields this object already holds and does
        NOT measure anything (no `peak` is computed here, no process is asked).
        `peak`/`nonzero_blocks` come from the worker's own `WORKER_STATS` line,
        which `_pump` already read off stderr.
        """
        child = self.child
        current = child.pid if child is not None else None
        stats = self.last_worker_stats
        device = self.last_device_status
        return {
            'state': self.state,
            'capturing': bool(self.capturing),
            'childPid': current,
            'spawns': self.spawns,
            'restarts': self.restarts,
            'deaths': self.deaths,
            'captions': self.captions,
            'statuses': self.statuses,
            'malformed': self.malformed,
            'lastExit': self.last_exit,
            'noAudio': bool(self.no_audio),
            'noAudioEvidence': self.no_audio_evidence,
            'pendingError': self.pending_error,
            'lastError': self.last_error,
            # `*Current` is the honest half of keeping a dead child's number
            # around: False means the line was published by a child this bridge
            # has already replaced, and it says so instead of looking live.
            'device': device,
            'deviceCurrent': bool(device) and device.get('childPid') == current,
            'workerStats': stats,
            'workerStatsCurrent': bool(stats) and stats.get('childPid') == current,
            'stderrTail': list(self.stderr_tail[-3:]),
        }

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
        # `stderr_tail` explains THIS death, so it is reset per child. The last
        # stats line and the last device are NOT cleared: each is stamped with
        # the pid that published it (`childPid`), so the snapshot can say whether
        # the number belongs to the live child or to the one that just died,
        # instead of showing a null that hides both.
        self.stderr_tail = []
        # A freshly spawned worker has no open stream yet; the guard re-opens
        # when its `capture-started` line arrives. `spawned_at` lets a queued
        # reload tell whether this respawn already re-read the file.
        self.capturing = False
        # A new child has declared nothing yet: the previous child's `silent-
        # device` is evidence about the OLD process, and letting it survive the
        # respawn would blind the watchdog for the new one.
        self.no_audio = False
        self.no_audio_evidence = None
        # The new child's `blocks=` counter starts again at 0 (see
        # `_progress_blocks`): carrying the dead process's last value over would
        # make every heartbeat look like a repeat and blind the watchdog.
        self._progress_blocks = None
        self.spawned_at = time.monotonic()

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
            # The child is passed EXPLICITLY rather than read from `self.child`
            # inside the thread: a dead worker's pipe can still be draining while
            # `self.child` already points at its replacement, and a WORKER_STATS
            # line stamped with the WRONG pid is an unattributable number.
            threading.Thread(target=self._pump, args=(stream, name, self.child),
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
            self.capturing = False
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
    def _pump(self, stream, name, child=None):
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
                    # The worker's own counters line, kept whole (see
                    # `last_worker_stats`): the text dump reads `peak` and
                    # `nonzero_blocks` from here, not from a new measurement.
                    if line.startswith('WORKER_STATS'):
                        parsed = parse_worker_stats(line)
                        if parsed is not None:
                            if child is not None:
                                parsed['childPid'] = child.pid
                            self.last_worker_stats = parsed
                            # The heartbeat is PROGRESS. Re-arming here is the
                            # whole cure: this stream used to `continue` before
                            # `_arm_silence`, so the one periodic signal the
                            # worker publishes never reached the watchdog.
                            self._note_progress(parsed)
                    continue
                self._arm_silence()
                text = line.strip()
                if text:
                    self._consume(text, child)
        except Exception as exc:
            self.log(f'BRIDGE_PUMP_DIED stream={name} error={exc!r}')
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _consume(self, line, child=None):
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
            if message.get('device'):
                # Remember WHICH endpoint this child is on. `device` names the
                # first candidate (with the full `candidates` list); a rotation
                # names the one it moved to. Kept as raw fields so the dump can
                # name the endpoint being tapped without parsing the sentence.
                self.last_device_status = {
                    'state': state,
                    'device': message.get('device'),
                    'api': message.get('api'),
                    'peak': message.get('peak'),
                    'reason': message.get('reason'),
                    'candidates': message.get('candidates'),
                }
                if child is not None:
                    self.last_device_status['childPid'] = child.pid
            # The worker's own answer to "is there anything to transcribe?".
            # Remembered per child (reset in `_spawn`) and read by `_on_silence`
            # so the watchdog stops treating "a quiet desktop" as "a jammed
            # worker" -- see WORKER_NO_AUDIO_STATES.
            evidence = self._no_audio_evidence(state, message)
            if evidence is not None:
                self.no_audio = True
                self.no_audio_evidence = evidence
            # The guard's input, kept where the state is READ, not inferred
            # later: `capture-started` opens the guard, and a terminal state or
            # the child's exit closes it. See `WorkerReloadPolicy`.
            if state in WORKER_CAPTURING_STATES:
                self.capturing = True
            elif state in WORKER_ERROR_STATES or state in ('done',
                                                           'selftest-done'):
                self.capturing = False
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

    def _note_progress(self, stats):
        """The worker's own heartbeat counts as PROGRESS; re-arm the watchdog.

        MUST NOT take `self._lock` — it is called from the pump thread, and the
        same rule as `_arm_silence` applies.

        THE DEFECT THIS CLOSES, measured in the owner's own log
        (`_main/webview-run.log`, 2026-10-06, `pid=4312`/`pid=47056`): the only
        PERIODIC signal the worker publishes is `WORKER_STATS tag=tick` on
        STDERR (`--stats-interval`, 10 s), and it carries the ADVANCING
        `blocks=` counter — the worker's own proof that it is still consuming
        audio. `_pump` re-armed the watchdog for STDOUT lines only, so that
        proof was invisible: 15 s without a CAPTION killed a worker that was
        transcribing (`BRIDGE_RESTART reason=silent`, 33 times in that log;
        `captions=29` on the very pid that was killed), and every respawn paid
        a ~2.4 GB model reload before it could caption again.

        The counter must ADVANCE. Otherwise a worker that reprints its last
        line forever — a wedged loop — would buy itself an eternal reprieve and
        the watchdog would stop being a watchdog.
        """
        try:
            blocks = int((stats.get('fields') or {}).get('blocks', ''))
        except (TypeError, ValueError):
            return
        if self._progress_blocks is not None and blocks <= self._progress_blocks:
            return
        self._progress_blocks = blocks
        self._arm_silence()

    def _cancel_timers(self):
        for name in ('_silence_timer', '_restart_timer'):
            timer = getattr(self, name, None)
            if timer is not None:
                timer.cancel()
                setattr(self, name, None)

    def _no_audio_evidence(self, state, message):
        """The worker's OWN sentence that there is nothing to transcribe.

        Returns the sentence (for the log) or None. Three shapes, all of them a
        measurement the WORKER made about the ENDPOINT -- never an inference the
        shell draws from a caption that did not arrive:

          * `device-rotated` with `reason=flat`: the per-candidate row the ladder
            writes on its way out of a window that produced NO CAPTION. The
            worker's word is `flat`, but it is NOT "below the peak floor" —
            measured on this box, a live idle run rotated with
            `peak=0.465216` against `floor=0.002`
            (`_main/_tap-restart-live-after.log`): the tap heard something and
            the model found nothing to transcribe in the window
            (sotto_worker.py:2163 settles only on a CAPTION). So the row means
            "this candidate carried nothing I could transcribe, moving on" —
            the ladder accounting for the silence, candidate after candidate,
            which is exactly what an idle desktop produces.
            `open-failed` is deliberately NOT included: a device that could not
            be OPENED is a fault, not a measurement of the audio.
          * a terminal device state (`silent-device`, `device-exhausted`,
            `silent-capture`, `no-speech-in-capture`, `music-only-capture`).
          * a `done` whose verdict is one of WORKER_NO_AUDIO_VERDICTS. An absent
            or unknown verdict is NOT evidence of no audio, so it does not count.
        """
        message = message or {}
        if state == 'device-rotated':
            if str(message.get('reason') or '') == 'flat':
                return (f'device-rotated reason=flat '
                        f'peak={message.get("peak")} '
                        f'floor={message.get("peak_floor")}')
            return None
        if state == 'done':
            verdict = str(message.get('verdict') or '').strip()
            if verdict and verdict in WORKER_NO_AUDIO_VERDICTS:
                return f'done verdict={verdict}'
            return None
        if state in WORKER_NO_AUDIO_STATES:
            return f'state={state}'
        return None

    def _on_silence(self):
        if self.stopped or self.child is None:
            return
        if self.no_audio:
            # BENIGN, and the fix for this lane's defect. The worker has already
            # published its own verdict that the tap carries nothing to
            # transcribe, and a tap that carries nothing produces NOTHING on
            # stdout by design -- so this quiet is the CORRECT behaviour on a
            # quiet machine, not a jam. Killing it here is what produced 8
            # `BRIDGE_SILENT` and `spawns=10` in ONE live run, each respawn
            # reloading a ~2.4 GB model, with no caption able to ever break the
            # cycle (owner's brief: "o loop nunca converge").
            #
            # Nothing is killed. The state is NAMED so the panel says what is
            # true, and the timer is re-armed so the watchdog keeps watching --
            # it must still catch a child that wedges AFTER saying this.
            self.log(f'BRIDGE_SILENT_BENIGN ms={self.silence_ms} '
                     f'pid={self.child.pid} state={NO_AUDIO_STATE} '
                     f'because={json.dumps(self.no_audio_evidence)}'
                     f' restarts={self.restarts}')
            if self.pending_error is None:
                # Only when no death is on screen: a real exit outranks a benign
                # quiet, and painting a status over it is the swallow this file
                # already fights (see `pending_error`).
                self._bridge_status(
                    'Audio tap silent - nothing to transcribe', 'busy',
                    {'title': 'No audio to transcribe',
                     'body': 'The worker measured every tap it opened below the '
                             'peak floor: this endpoint is carrying digital '
                             'silence, which is what a quiet desktop looks like. '
                             'The worker keeps listening; it is not restarted.'},
                    NO_AUDIO_STATE)
            else:
                self.log(f'BRIDGE_SILENT_BENIGN_HELD state={NO_AUDIO_STATE} '
                         f'behind={json.dumps(self.pending_error["state"])}')
            self._arm_silence()
            return
        # ANOMALOUS. The tap was open (or had declared itself) and then went
        # mute WITHOUT the worker ever saying what the audio was: that is the
        # jam this watchdog exists for, and it still restarts.
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
        self.capturing = False
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
                        help='the global toggle accelerator (default: Alt+C). If '
                             'another program already owns it the shell tries '
                             + ' / '.join(HOTKEY_FALLBACKS)
                             + ' and logs which one won (HOTKEY_FALLBACK)')
    parser.add_argument('--no-hotkey', action='store_true',
                        help='do not register the global hotkey. A MEASUREMENT '
                             'run must use this: Alt+C is the app\'s only '
                             'control, and a probe that owns it shows the '
                             "owner its own panel when he presses his key")
    parser.add_argument('--install-autostart', action='store_true',
                        help='make Windows start Sotto at login (HKCU\\...\\Run, '
                             'pointing at pythonw.exe so no console appears), '
                             'then exit')
    parser.add_argument('--uninstall-autostart', action='store_true',
                        help='remove that autostart entry, then exit')
    parser.add_argument('--autostart-status', action='store_true',
                        help='print whether autostart is installed and whether it '
                             'still points at THIS checkout, then exit')
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
    #: F1 (docs/audit/auditoria-completa-20261007.md): the worker starts BY
    #: DEFAULT. Until 2026-10-07 `start_worker` was reachable only under
    #: `if self.args.with_worker:`, and `run.cmd` -- the entry the owner
    #: double-clicks -- never passed it: 32 shell starts in `_main/webview-run.log`,
    #: 10 with a worker and every one of them `reason=with-worker`. So Alt+C on
    #: the documented path opened a panel that said "Waiting for audio" forever,
    #: with no transcription process in existence. The opt-OUT is now the flag.
    parser.add_argument('--no-worker', action='store_true',
                        help='do NOT start the worker: the shell only. The '
                             'worker starts by default (F1); this is the '
                             'opt-out, for a shell-only run')
    #: An ALIAS, kept for the lane instruments that pass it (`_main/_app-drive.py`,
    #: `_main/_live-launch.py`) and for `--help` compatibility: it is accepted,
    #: it does not change behaviour, and it can no longer be the REASON a run has
    #: a worker. Precedence with `--no-worker` is stated in `_on_loaded`.
    parser.add_argument('--with-worker', action='store_true',
                        help='start the worker at launch. Alias: the worker '
                             'already starts by default (F1), so this flag now '
                             'only FORCES the worker where an automatic '
                             'opt-out would decline it -- see --no-worker')
    parser.add_argument('--dump-dom', action='store_true',
                        help="measure the panel with the Electron arm's probe "
                             'and exit')
    parser.add_argument('--dump-dom-wait', type=float, default=0.0,
                        help='seconds to wait before the --dump-dom probe, so '
                             'the dump can measure a state that only exists '
                             'after the worker has run (0 = measure at startup, '
                             'unchanged)')
    parser.add_argument('--probe-v2', type=float, default=0.0, metavar='SECONDS',
                        help='after SECONDS, run the panel-v2 acceptance probe: '
                             '(two sections, live caption, history on disk, '
                             'search) and exit 0 GREEN / 3 RED')
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
    parser.add_argument('--probe-reload', action='store_true',
                        help='prove the worker hot-reload guard: touch the '
                             'worker file while a capture is open and print '
                             'the restart count (starts no window)')
    parser.add_argument('--log', default=None, help='mirror stdout here')
    #: run.cmd's pre-flight switch. SUPPRESS keeps it out of `--help`, so the
    #: usage printed by `run.cmd --help` is byte-for-byte the one it printed
    #: before this mode existed (it is the wrapper's, not the user's, flag).
    parser.add_argument('--check-args', action='store_true',
                        help=argparse.SUPPRESS)
    #: run.cmd's readiness handshake (gap G3). The wrapper `start`s the app
    #: DETACHED, so a hang after the spawn is invisible to it; it hands a FRESH
    #: path here and waits for it, bounded (the file appearing is "the app came
    #: up", the bound expiring is a HANG). SUPPRESS: it is the wrapper's flag,
    #: not a user flag, and `--help` must stay byte-for-byte as it was.
    parser.add_argument('--ready-file', default=None,
                        help=argparse.SUPPRESS)
    #: run.cmd's bounded readiness poll (the other half of G3). A MODE: it takes
    #: a path, waits for the app to touch it, and exits 0/4. It is the wrapper's
    #: flag, so it stays out of `--help`.
    parser.add_argument('--wait-ready', default=None, metavar='PATH',
                        help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def pywebview_version():
    try:
        import importlib.metadata as md
        return md.version('pywebview')
    except Exception:
        return 'unknown'


def _preflight_refuse(args, message: str, code: int) -> int:
    """Record a pre-flight refusal where the caller can still see it, and return
    the code the wrapper passes on.

    The pre-flight runs under pythonw.exe, whose stdout/stderr are None, so the
    interpreter's own message is discarded and the exit code is the whole
    contract the wrapper can read. The reason is mirrored to `--log` when the
    caller gave one (appending, like every other line) and printed when there is
    a console (a direct run). This opens no window and starts nothing.
    """
    if getattr(args, 'log', None):
        _open_log(args.log)
    log(message)
    return code


def probe_reload():
    """Prove the worker-reload guard against REAL files and a REAL watcher.

    The defect: a settled worker-file change restarted the worker on the spot,
    even mid-stream, so five lanes saving all morning produced a restart storm
    (the "model loading toda hora" the owner saw). Three arms, each able to
    print RED:

      1. GUARD    a capture is open; the worker file is touched N times, spaced
                  wider than the watcher's 250 ms window so each touch WOULD
                  flush. Expect: ZERO restarts during the capture, and exactly
                  ONE worker spawn in total once the stream ends.
      2. STORM    the SAME N touches with the guard and the floor removed (the
                  old behaviour). Expect: N restarts. This is the arm that makes
                  arm 1 mean something — if the storm is not reproducible, the
                  guard is not being tested.
      3. BURST    a tight burst (8 writes in <250 ms) with no capture. Expect:
                  exactly ONE restart (the debounce coalesces it).

    No WebView2, no worker process: the only stand-in is the bridge, which
    exposes the two fields the policy reads (`child`, `is_capturing()`), and the
    `restart` callable, which counts. Everything else is the production classes.
    """
    root = tempfile.mkdtemp(prefix='sotto-reload-')
    panel_dir = os.path.join(root, 'panel')
    worker_dir = os.path.join(root, 'worker')
    os.makedirs(panel_dir)
    os.makedirs(worker_dir)
    worker_py = os.path.join(worker_dir, 'sotto_worker.py')
    with open(worker_py, 'w', encoding='utf-8') as fh:
        fh.write('# seed\n')

    rc = 0

    class StandInBridge:
        """Exactly the surface WorkerReloadPolicy reads, and no more."""

        def __init__(self):
            self.child = object()          # a worker is up
            self.capturing = False
            self.spawned_at = time.monotonic() - 1000.0
            self.spawns = 0

        def is_capturing(self):
            return self.capturing

    def run_arm(debounce_ms, min_interval_ms):
        br = StandInBridge()

        def restart(files):
            br.spawns += 1
            br.spawned_at = time.monotonic()
            return True

        policy = WorkerReloadPolicy(log_fn=print, get_bridge=lambda: br,
                                    restart=restart, debounce_ms=debounce_ms,
                                    min_interval_ms=min_interval_ms)
        hr = hot_reload.HotReload(log=lambda line: None,
                                  on_worker_changed=policy.request,
                                  panel_dir=panel_dir, worker_dir=worker_dir)
        if not hr.start():
            return None, None, None
        return br, policy, hr

    touches = 6

    # ── arm 1: the guard — a capture is open while the file is touched ──────
    # A short 200 ms debounce keeps the arm quick; the GUARD, not the debounce,
    # is what this arm isolates.
    br, policy, hr = run_arm(200, WORKER_RELOAD_MIN_INTERVAL_MS)
    if br is None:
        print('VERDICT arm=guard watchers=0 got=0-1')
        shutil.rmtree(root, ignore_errors=True)
        return 3
    br.capturing = True
    for i in range(touches):
        with open(worker_py, 'a', encoding='utf-8') as fh:
            fh.write(f'# touch {i}\n')
        time.sleep(0.4)                    # > the watcher's 250 ms window
    time.sleep(0.9)                        # let the last flush reach the policy
    during = br.spawns
    print(f'ARM guard touches={touches} restarts_during_capture={during} '
          f'expect=0')
    if during != 0:
        rc = 3
    # the stream ends: the worker exits, then respawns ONCE (the app's own
    # supervisor), which re-reads the file — no second restart is owed.
    br.capturing = False
    br.child = None
    policy.boundary()
    time.sleep(0.9)
    br.child = object()
    br.spawned_at = time.monotonic()
    respawns = 1
    total = br.spawns + respawns
    print(f'ARM guard total_spawns={total} '
          f'(policy_restarts={br.spawns} + boundary_respawn={respawns}) '
          f'expect=1')
    if total != 1:
        rc = 3
    policy.stop()
    hr.stop('arm1')

    # ── arm 2: the storm — the SAME touches with the guard removed ──────────
    br, policy, hr = run_arm(0, 0)
    if br is None:
        print('VERDICT arm=storm watchers=0 got=0-1')
        shutil.rmtree(root, ignore_errors=True)
        return 3
    br.capturing = False                   # pre-fix: no guard existed at all
    for i in range(touches):
        with open(worker_py, 'a', encoding='utf-8') as fh:
            fh.write(f'# storm {i}\n')
        time.sleep(0.4)
    time.sleep(0.9)
    print(f'ARM storm touches={touches} restarts={br.spawns} '
          f'expect={touches}')
    if br.spawns != touches:
        rc = 3
    policy.stop()
    hr.stop('arm2')

    # ── arm 3: the debounce — a tight burst is ONE request ──────────────────
    br, policy, hr = run_arm(WORKER_RELOAD_DEBOUNCE_MS, 0)
    if br is None:
        print('VERDICT arm=burst watchers=0 got=0-1')
        shutil.rmtree(root, ignore_errors=True)
        return 3
    for i in range(8):
        with open(worker_py, 'a', encoding='utf-8') as fh:
            fh.write(f'# burst {i}\n')
        time.sleep(0.03)                   # under the watcher's window
    time.sleep(0.5 + WORKER_RELOAD_DEBOUNCE_MS / 1000.0)
    print(f'ARM burst writes=8 restarts={br.spawns} expect=1 '
          f'debounce_ms={WORKER_RELOAD_DEBOUNCE_MS}')
    if br.spawns != 1:
        rc = 3
    policy.stop()
    hr.stop('arm3')

    shutil.rmtree(root, ignore_errors=True)
    print(f'SELFTEST reload rc={rc}')
    return rc


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)

    if args.wait_ready:
        # ---- run.cmd's bounded readiness poll: the other half of G3 ---------
        # `run.cmd` `start`s the app DETACHED, so it can never see a hang after
        # the spawn -- measured 2026-10-06 a launch logged STAGING_LOADED and
        # stopped, and the wrapper still answered 0 (launch-entry.md §3/§4). It
        # hands a FRESH path to the app (`--ready-file`) and calls THIS mode,
        # which waits, bounded, for the app to touch it: 0 = up, 4 = HANG.
        # pythonw keeps it windowless; nothing is opened, logged or started.
        try:
            bound = float(os.environ.get('SOTTO_READY_BOUND', '30'))
        except ValueError:
            bound = 30.0
        return wait_ready_file(args.wait_ready, bound)

    if args.check_args:
        # ---- run.cmd's PRE-FLIGHT: the one mode that STARTS NOTHING ----------
        # `start` in run.cmd detaches the app, so the wrapper never sees the
        # interpreter's status. Measured 2026-10-06 (lane SottoRunCmdEntry):
        # `run.cmd --bogus-flag` returned rc=0 with no log bytes, no shell line
        # and no process -- argparse exits 2 on pythonw.exe, whose stdout is
        # None, and `start` reports only its OWN success, so a rejected flag
        # answered as success. The wrapper runs THIS first and spawns the app
        # only when it returns 0: the list is validated by the shell's own
        # parser, one flag table, and a second copy in batch cannot drift.
        #
        # Reaching here means parse_args ACCEPTED the list (a rejected one exits
        # 2 from parse_args above, before this line -- that status is the one
        # the wrapper passes on).
        #
        # G1: the panel must be present. This return USED to happen before the
        #     panel check further down (:2483), so with app/panel/panel.html
        #     missing `run.cmd` exited 0 while a real launch exited 3 -- the
        #     same "failure answering as success" the pre-flight exists to
        #     close (docs/audit/launch-entry.md, §2 G1).
        if not os.path.exists(PANEL_HTML):
            return _preflight_refuse(args,
                                     f'PANEL_MISSING path={PANEL_HTML}', 3)
        # G2: `import webview` is late (the WinForms assemblies it loads must not
        #     be imported before the UI loop exists), so an ImportError surfaced
        #     as the process' rc=1 only AFTER `run.cmd` had already answered 0.
        #     Import it HERE, where the wrapper is still listening, and pass the
        #     same status a real launch would exit with.
        try:
            import webview  # noqa: F401
        except Exception as exc:  # noqa: BLE001 -- any import failure is G2
            return _preflight_refuse(
                args,
                f'PYWEBVIEW_IMPORT_FAILED {type(exc).__name__}: {exc}', 1)
        return 0

    if args.probe_reload:
        # ---- the reload-guard proof: starts NO window and NO worker ----------
        # It only touches real files and drives the real watcher + policy, so it
        # is safe under pythonw and prints its own verdict to the log/console.
        return probe_reload()

    _open_log(args.log)
    log(f'shell=webview2 pywebview={pywebview_version()} '
        f'python={sys.version.split()[0]} pid={os.getpid()}')

    if not os.path.exists(PANEL_HTML):
        log(f'PANEL_MISSING path={PANEL_HTML}')
        return 3

    args.python = args.python or default_python()

    # ── the three autostart modes print and exit: no window, no worker ───────
    # They are here (and not before `_open_log`) so the receipt of what was
    # written to the registry lands in the same run log as everything else.
    if args.install_autostart:
        return autostart_install()
    if args.uninstall_autostart:
        return autostart_uninstall()
    if args.autostart_status:
        return autostart_status()

    # ── ONE SHELL AT A TIME — BUT ONLY WHEN A HOTKEY IS AT STAKE ─────────────
    # The mutex protects the GLOBAL HOTKEY, which is the only genuinely exclusive
    # resource here (a second shell cannot register it: `RegisterHotKey` → 1409,
    # and the owner's Alt+C then answers the first, possibly stale, instance).
    # A MEASUREMENT run registers no hotkey — that is exactly why AGENTS.md makes
    # `--no-hotkey` mandatory for one — so it must NEVER be refused by this lock.
    # It was, for one revision: `_main/_audit-verify-all`-style probes and the
    # `--dump-dom` dump below were both refused with
    # `SINGLE_INSTANCE already_running=true` while the owner's app was up, i.e.
    # the guard bricked every instrument in the repo (measured 2026-10-07). The
    # union of the flags is deliberate: a probe that forgot `--no-hotkey` still
    # runs, and the log says which flag excused it.
    lock_excuse = None
    if args.no_hotkey:
        lock_excuse = '--no-hotkey'
    elif args.dump_dom:
        lock_excuse = '--dump-dom'
    elif args.selftest:
        lock_excuse = '--selftest'
    elif args.memory:
        lock_excuse = '--memory'
    elif args.probe_v2 > 0:
        lock_excuse = '--probe-v2'
    if lock_excuse:
        log(f'SINGLE_INSTANCE_SKIPPED reason={lock_excuse} '
            '(a measurement run registers no global hotkey)')
    elif not take_single_instance_lock():
        warn('Sotto is already running in this session: this launch will not show '
             'anything. Press Alt+C for the running panel, or close it with the '
             'panel\'s Quit button before starting another one.')
        return 0

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
        # The chain lives in `arm_hotkey`: the requested key, then
        # `HOTKEY_FALLBACKS`, then — if every one is owned by another program —
        # a dialog on a daemon thread, because a hidden app with a dead hotkey
        # and no message is indistinguishable from a broken app.
        shell.hotkey = arm_hotkey(shell, args.hotkey)

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