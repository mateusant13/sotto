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
import hashlib
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
#: Boot grace for the model load. MEASURED 2026-10-08: a direct worker run
#: takes ~67 s (`load_s=66.88`) from spawn to `model-loaded`, during which the
#: only stdout lines are the warmup statuses (`boot`/`model-loading`, HELD
#: behind any pending error) and no `WORKER_STATS` tick exists yet (ticks
#: start after capture). The 30 s no-progress window therefore fired mid-load
#: and `_kill_and_restart('silent')` terminated a healthy loader (rc=1,
#: `statuses=4`, never `model-loaded`), looping forever without a caption.
#: Until `capture-started` the watchdog re-arms instead of killing while the
#: child is younger than this grace. 120 s is ~1.8x the measured load, leaving
#: margin for a slow disk without hiding a truly wedged loader forever.
WORKER_BOOT_GRACE_MS = 120000


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
#: THE CEILING ON A HELD RELOAD, and it exists because "applies at the next
#: boundary" once meant "never". MEASURED on the owner's app 2026-10-08: **20
#: QUEUED / 20 DEFERRED / 0 APPLIED / 0 respawns** since the worker started at
#: 08:01:56 — every edit to `worker/sotto_worker.py` was retained and he was
#: running hours-old code, then reporting defects that were already fixed. The
#: boundary is now the CLOSED LINE (`final:true`), which arrives on every pause;
#: this is the fallback for a monologue that closes no line at all.
#:
#: WHY 25 s: speech closes a line at every pause, so 25 s of continuous audio
#: without one closed line is already an unusual stretch; the cost of forcing is
#: ONE model warm-up (2.0-8.3 s of stall, 1.4-2.1 GB, measured in
#: `worker/runs/*.jsonl`); and the FLOOR above still bounds the RATE, so this
#: cannot cause churn — it can only decide WHEN inside the floor a reload lands.
#: The owner's order is "hot reload ao maximo", and half a minute is the worst
#: case here rather than the typical one.
WORKER_RELOAD_MAX_DEFER_MS = 25000
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
# THE STRIP — the SHORT band Alt+C opens (owner, 2026-10-08)
# ===========================================================================
#
# Owner, verbatim: *"alt c > abre embaixo. passo o mouse encima > aparece mais
# botoes"* — the live caption at the BOTTOM, horizontally CENTRED, controls
# revealed on hover. The product decision is written down in
# `app/panel/surface.js:6-8` (the hotkey must NOT open the whole 380x900 panel;
# it opens a short strip, and the full panel is a place the owner goes on
# purpose) and the wire contract in `app/panel/panel.js:1239-1243`
# (`bridge.setPanelSurface(surface, reason)` — the SHELL resizes).
#
# WHY THE HEIGHT IS READ FROM THE STYLESHEET AND NOT TYPED HERE. The panel lane
# measured the strip's real geometry and put the ONE number in `:root`:
# `panel.css:52` `--strip-height: 150px` (with `:53` `--strip-chrome: 78px`, and
# `:1060` deriving the content floor as
# `calc(var(--strip-height) - var(--strip-chrome))`). `panel.css:44` documents the
# read. A second copy here would let the next theme edit leave the shell lying
# about the window it sized, so `SottoShell.refresh_strip_height()` reads
# `getComputedStyle(document.documentElement).getPropertyValue('--strip-height')`
# at the moment the strip is applied and uses THAT number. `STRIP_HEIGHT_FALLBACK`
# is only what is used when the page cannot answer (it is not a second source of
# truth — every use is logged with `source=css|fallback`).
#
# THE NUMBERS, and why (all DIP; this host is 96 dpi / scale 1.0):
#   * width  `min(1040, max(480, round(work.width * 0.62)))`. The classic
#     subtitle band is ~55-65 % of the screen; the cap keeps it a caption and not
#     a second panel, the floor keeps it from being a slit.
#   * height the stylesheet's `--strip-height`, read at runtime.
#   * x      horizontally CENTRED in the WORK area — the owner's *"no meio"*.
#   * y      `work.y + work.height - height - 48`, i.e. 48 px above the bottom of
#     the WORK area (not of the screen), which is what clears the taskbar.
STRIP_WIDTH_MAX = 1040
STRIP_WIDTH_MIN = 480
STRIP_WIDTH_FRACTION = 0.62
#: The CSS custom property that IS the strip's height (`panel.css:52`).
STRIP_HEIGHT_CSS_VAR = '--strip-height'
#: Used ONLY when the page cannot answer; every use is logged as a fallback.
STRIP_HEIGHT_FALLBACK = 148
STRIP_BOTTOM_MARGIN = 48

#: THE LOG BUDGET OF THE STATS FEED. `on_worker_stats` fires once per worker
#: `WORKER_STATS` line, and that line is a METER sample — the worker may publish
#: it at tens of Hz. A log line per sample is an unbounded log, and an unbounded
#: log is how a feature gets turned off to keep the file quiet (it happened: the
#: worker's meter default was set to zero). So the push logs its FIRST sample and
#: then at most one line per this many seconds, each carrying the count it stands
#: for. The PANEL is still fed at the worker's own cadence — only the LOG is
#: aggregated.
STATS_LOG_INTERVAL_S = 30.0

#: THE WAVE. `worker/sotto_worker.py:3591` emits `{"type":"meter","peak":…,
#: "blocks":…}` once per meter window (10 Hz by default) and its `peak` is the
#: peak OF THAT WINDOW, while the `WORKER_STATS` line on stderr carries the
#: RUNNING MAXIMUM of the whole run. A wave drawn from a running maximum is a
#: staircase that only rises and then flattens — that IS the defect the owner
#: reported ("as ondas que crescem e diminuem nao ta funcionando"). So a fresh
#: meter sample WINS over the stats line, and the two are never mixed.
METER_FRESH_S = 2.0
#: The meter path used to fall into the unknown-kind `else`, which logged
#: `BRIDGE_UNKNOWN type='meter'` PER SAMPLE — measured 35 B × 10 Hz ≈ 20.5 KB/min
#: with no end. The DATA is not throttled (that mistake was made once already, on
#: the worker side): only this log line is, on the same budget as the push.
METER_LOG_INTERVAL_S = 30.0


def file_sha256(path):
    """The first 16 hex of a file's sha256, or `None` if it cannot be read.

    An IDENTITY, not a security check: it answers "is the code on disk the code
    the process is running?" in 16 characters that fit in a log line. Read in
    1 MiB chunks, so hashing the ~240 KB worker or this ~350 KB shell is a
    millisecond and never a stall.
    """
    try:
        digest = hashlib.sha256()
        with open(path, 'rb') as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b''):
                digest.update(chunk)
        return digest.hexdigest()[:16]
    except OSError:
        return None


#: WHAT THIS PROCESS ACTUALLY READ. A Python process compiles its source ONCE, at
#: import; nothing reloads it. So the file's hash AT IMPORT is the honest answer
#: to "what code am I running?", and comparing it with the file on disk NOW is the
#: difference between "the app is current" and "the owner is running old code" —
#: the exact discovery that cost him a bug report about words that had already
#: been fixed.
SHELL_SHA256_AT_IMPORT = file_sha256(__file__)
SHELL_PATH = os.path.abspath(__file__)


def strip_geometry(work, height=STRIP_HEIGHT_FALLBACK, dock='bottom-centre'):
    """The bottom-centre caption band, CONTAINED in `work` (DIP).

    Kept a pure function for the same reason `dock_right` is: the output is
    inside the work area whatever the work area is, including degenerate
    rectangles and a work area shorter than the band.
    """
    w = max(0, work['width'])
    h = max(0, work['height'])
    want_height = int(height) if isinstance(height, (int, float)) \
        else STRIP_HEIGHT_FALLBACK

    band_width = min(STRIP_WIDTH_MAX,
                     max(STRIP_WIDTH_MIN, round(w * STRIP_WIDTH_FRACTION)))
    band_width = min(band_width, w)
    band_height = max(1, min(want_height, h))

    x = work['x'] + (w - band_width) // 2
    y = work['y'] + h - band_height - STRIP_BOTTOM_MARGIN

    geometry = {
        'workX': work['x'],
        'workY': work['y'],
        'workWidth': w,
        'workHeight': h,
        'x': max(work['x'], round(x)),
        'y': max(work['y'], round(y)),
        'width': max(1, round(band_width)),
        'height': band_height,
        'margin': STRIP_BOTTOM_MARGIN,
        'docked': dock,
    }
    # Containment is an invariant, not a hope — the same rule `dock_right` keeps.
    geometry['x'] = min(geometry['x'], work['x'] + w - geometry['width'])
    geometry['y'] = min(geometry['y'], work['y'] + h - geometry['height'])
    return geometry


def clamp_geometry(rect, work):
    """Fit a SAVED rect into the CURRENT work area; say whether it moved.

    This is the honest answer to "the resolution changed" — which was NOT
    measured for this lane and must not be invented. A saved rect is kept when
    it still fits, and is moved/resized into the work area when it does not; the
    caller logs the difference so a moved window is never a silent surprise.
    """
    w = max(0, work['width'])
    h = max(0, work['height'])
    want_width = max(1, min(int(rect.get('width') or 1), max(1, w)))
    want_height = max(1, min(int(rect.get('height') or 1), max(1, h)))
    x = max(work['x'], min(int(rect.get('x') or work['x']),
                          work['x'] + w - want_width))
    y = max(work['y'], min(int(rect.get('y') or work['y']),
                          work['y'] + h - want_height))
    clamped = {
        'workX': work['x'], 'workY': work['y'],
        'workWidth': w, 'workHeight': h,
        'x': x, 'y': y, 'width': want_width, 'height': want_height,
        'margin': 0, 'docked': str(rect.get('docked') or 'saved'),
    }
    moved = (x != int(rect.get('x') or x) or y != int(rect.get('y') or y)
             or want_width != int(rect.get('width') or want_width)
             or want_height != int(rect.get('height') or want_height))
    return clamped, moved


#: The surfaces the ONE document can wear. The names are `app/panel/surface.js`'s
#: (`SURFACES`), and this shell refuses anything else instead of guessing.
SURFACE_NAMES = ('strip', 'panel')


def normalise_surface_name(name):
    """`'strip'`/`'panel'` from what a caller actually sent, else None.

    Mirrors `surface.js:39-46` on purpose, including its tolerance for the
    CSS-ish spellings a shell might copy out of the stylesheet
    (`surface--strip`, `surface-strip`). A name this file does not know is
    REFUSED — never silently treated as the panel, because a caller that sent
    `'strip '` and got a 900 px window would read as a layout bug.
    """
    value = str(name if name is not None else '').strip().lower()
    value = re.sub(r'^surface-+', '', value)
    return value if value in SURFACE_NAMES else None


# ===========================================================================
# Win32 — work area, DPI, extended styles, the hotkey
# ===========================================================================

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)

MONITOR_DEFAULTTOPRIMARY = 0x00000001

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
#: What WinForms' `Form.CreateParams` sets while `ShowInTaskbar` is true and the
#: form has no owner — and it BEATS `WS_EX_TOOLWINDOW`, putting the panel in the
#: taskbar. Measured set on this shell's hwnd; see `reassert_taskbar_ex_style`.
WS_EX_APPWINDOW = 0x00040000
WS_EX_CONTROLPARENT = 0x00010000

SW_SHOWNOACTIVATE = 4
SW_HIDE = 0
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

# THE ARGTYPES ARE LOAD-BEARING, and this cost a real defect. Without them
# ctypes marshals every Python int as a 32-bit C `int`, so `HWND_TOPMOST` (-1)
# reached a 64-bit `HWND` parameter as **0x00000000FFFFFFFF** — an invalid
# handle — and `SetWindowPos` answered **FALSE with `last_error=1400`
# (ERROR_INVALID_WINDOW_HANDLE)** while still applying the SIZE. Measured on this
# host 2026-10-08, moving the strip to its bottom-centre rect: the band changed
# width to 1040 and stayed at the docked panel's `(1528,66)`.
# `_main/_strip-surface-probe.py` reads the rect back and would have caught it;
# `set_topmost()` had been failing silently for the same reason (it logs nothing).
user32.SetWindowPos.restype = wt.BOOL
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]

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


# ===========================================================================
# THE WINDOW'S FACE — the icon and the identity the taskbar groups by
#
# The owner's report, 2026-10-08, verbatim: "eu tambem nao gosto que aparece um
# icone de python quando eu aperto o painel". He is describing the truth: this
# shell runs under `pythonw.exe`, and pywebview's WinForms backend, when it is
# given no icon, copies the icon out of `sys.executable` into the form
# (`webview/platforms/winforms.py:243-251`):
#
#     if _state['icon'] and os.path.isfile(_state['icon']):
#         self.Icon = Icon(_state['icon'])
#     else:
#         icon_handle = windll.shell32.ExtractIconW(handle, sys.executable, 0)
#         ...
#
# `sys.executable` under `pythonw.exe` is the Python interpreter, so the panel
# presented the PYTHON icon in the taskbar and in Alt+Tab. pywebview's own
# docstring calls the `icon=` parameter "Supported only on GTK/QT"
# (`webview/__init__.py:205`); the WinForms backend reads it anyway, and that is
# the seam used here.
#
# The identity is the second half: `SetCurrentProcessExplicitAppUserModelID`
# stops Windows from grouping this process with every other pythonw.exe on the
# box under the Python icon. Both are read back and logged, never assumed.
# ===========================================================================

SOTTO_ICON = os.path.join(HERE, 'sotto.ico')
SOTTO_APP_USER_MODEL_ID = 'sotto.overlay'

WM_GETICON = 0x007F
WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
ICON_SMALL2 = 2
GCLP_HICON = -14
GCLP_HICONSM = -34

user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t,
                                ctypes.c_ssize_t]
user32.GetClassLongPtrW.restype = ctypes.c_ssize_t
user32.GetClassLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
# `restype = ctypes.HRESULT` makes ctypes RAISE on a failing HRESULT, which
# turned the honest BEFORE answer (`E_NOT_SET`) into an exception; a plain
# `c_long` lets the code report the status instead of catching it.
shell32.GetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
shell32.GetCurrentProcessExplicitAppUserModelID.argtypes = [
    ctypes.POINTER(ctypes.c_wchar_p)]
shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wt.LPCWSTR]


def process_app_user_model_id() -> dict:
    """This process' OWN AppUserModelID, read back from shell32.

    `GetCurrentProcessExplicitAppUserModelID` answers `E_NOT_SET`
    (`0x80070490`) when nothing has set one — which is the honest BEFORE value,
    not `None` dressed up as a failure.
    """
    try:
        ptr = ctypes.c_wchar_p()
        hr = shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(ptr))
    except Exception as exc:  # noqa: BLE001 - a read must never kill a launch
        return {'ok': False, 'hr': None, 'value': None,
                'error': type(exc).__name__}
    if hr != 0:
        return {'ok': False, 'hr': hr & 0xFFFFFFFF, 'value': None}
    return {'ok': True, 'hr': 0, 'value': ptr.value}


def window_icon_snapshot(hwnd) -> dict:
    """What the WINDOW says its icon is: `WM_GETICON` + the class icon.

    Both are read, because they are different channels and only one of them is
    what `WM_SETICON` writes. Read from the window, never from the intent.
    """
    if not hwnd:
        return {'hwnd': None}
    return {
        'hwnd': int(hwnd),
        'wm_geticon_small': int(user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL, 0) or 0),
        'wm_geticon_big': int(user32.SendMessageW(hwnd, WM_GETICON, ICON_BIG, 0) or 0),
        'wm_geticon_small2': int(user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL2, 0) or 0),
        'class_hicon': int(user32.GetClassLongPtrW(hwnd, GCLP_HICON) or 0),
        'class_hiconsm': int(user32.GetClassLongPtrW(hwnd, GCLP_HICONSM) or 0),
    }


def form_icon_pixels(form) -> str:
    """The PIXELS of `form.Icon`, hashed in-process.

    This is the instrument that makes "the window carries the Python icon" a
    comparison of bytes instead of a non-zero handle: an HICON read out of
    another process cannot be drawn (GDI handles are process-local), so the
    hash has to be taken where the icon lives.
    """
    try:
        import hashlib
        icon = getattr(form, 'Icon', None)
        if icon is None:
            return 'absent'
        bmp = icon.ToBitmap()
        w, h = int(bmp.Width), int(bmp.Height)
        data = bytearray()
        for y in range(h):
            for x in range(w):
                c = bmp.GetPixel(x, y)
                data.extend((c.R, c.G, c.B, c.A))
        bmp.Dispose()
        return f'{w}x{h}:' + hashlib.sha256(bytes(data)).hexdigest()[:16]
    except Exception as exc:  # noqa: BLE001
        return f'ERR:{type(exc).__name__}'


def icon_source(form) -> str:
    """Where the icon ON the form came from: pywebview's own `_state['icon']`,
    or the `sys.executable` fallback that is the defect."""
    try:
        import webview
        path = (getattr(webview, '_state', None) or {}).get('icon')
    except Exception:  # noqa: BLE001
        path = None
    if path and os.path.isfile(path):
        return f'file:{path}'
    return f'pythonw-fallback:{sys.executable}'


def icon_file_sha256(path: str = SOTTO_ICON) -> str:
    """The sha256 of the icon FILE, so the in-process pixel hash can be tied to
    the exact bytes the shell loaded (the probe hashes the same file)."""
    try:
        import hashlib
        with open(path, 'rb') as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except Exception as exc:  # noqa: BLE001
        return f'ERR:{type(exc).__name__}'


def window_icon_report(form, hwnd) -> str:
    snap = window_icon_snapshot(hwnd)
    return (f"WINDOW_ICON source={icon_source(form)} "
            f"file={SOTTO_ICON} file_exists={str(os.path.isfile(SOTTO_ICON)).lower()} "
            f"file_sha256={icon_file_sha256()} "
            f"form_icon={form_icon_pixels(form)} "
            f"wm_geticon_small={snap.get('wm_geticon_small')} "
            f"wm_geticon_big={snap.get('wm_geticon_big')} "
            f"wm_geticon_small2={snap.get('wm_geticon_small2')} "
            f"class_hicon={snap.get('class_hicon')} "
            f"class_hiconsm={snap.get('class_hiconsm')} "
            f"image={sys.executable}")


def set_process_app_user_model_id(value: str = SOTTO_APP_USER_MODEL_ID) -> dict:
    """THE FIX, first half: give the process its own identity.

    Windows groups taskbar buttons by AppUserModelID, and a process that has
    none is grouped by its EXECUTABLE — so this shell was grouped with every
    other `pythonw.exe` on the box, under the Python icon. This must run EARLY,
    before any window exists, because the identity is read when the taskbar
    button is created.
    """
    try:
        hr = shell32.SetCurrentProcessExplicitAppUserModelID(value)
    except Exception as exc:  # noqa: BLE001
        return {'set': False, 'value': None, 'hr': None,
                'error': type(exc).__name__}
    return {'set': hr == 0, 'value': value if hr == 0 else None,
            'hr': hr & 0xFFFFFFFF}


def apply_window_icon(form, hwnd, path: str = SOTTO_ICON) -> dict:
    """THE FIX, second half: the window's own icon.

    Two channels, because they answer different questions and Windows reads
    both: the WinForms `Icon` property (which .NET pushes with `WM_SETICON` for
    ICON_BIG and ICON_SMALL) and three explicit `WM_SETICON` sends — including
    **ICON_SMALL2**, the one the taskbar and Alt+Tab actually read and the one
    .NET's own setter never sends.

    The HICON must outlive the call: `WM_SETICON` stores the HANDLE, not a copy,
    so the `Icon` object is kept on the form (`_sotto_icon`) as well as in the
    form's own `Icon` property.
    """
    result = {'applied': False, 'path': path, 'reason': None, 'handle': None}
    if not path or not os.path.isfile(path):
        result['reason'] = 'icon-file-missing'
        return result
    try:
        from System.Drawing import Icon as DrawingIcon
        icon = DrawingIcon(path)
    except Exception as exc:  # noqa: BLE001
        result['reason'] = f'load-failed:{type(exc).__name__}'
        return result
    try:
        form.Icon = icon
        try:
            form._sotto_icon = icon
        except Exception:  # noqa: BLE001 - a .NET object may refuse attributes
            pass
        handle = int(icon.Handle.ToInt64())
        if hwnd:
            for which in (ICON_BIG, ICON_SMALL, ICON_SMALL2):
                user32.SendMessageW(hwnd, WM_SETICON, which, handle)
        result['applied'] = True
        result['handle'] = handle
    except Exception as exc:  # noqa: BLE001
        result['reason'] = f'apply-failed:{type(exc).__name__}:{exc}'
    return result


def reassert_taskbar_ex_style(hwnd, where: str) -> dict:
    """Re-apply the taskbar/focus bits the shell asked for and WinForms wiped.

    MEASURED BEFORE THE FIX (`_main/no-python-icon-before.json`): at
    `PANEL_VISIBILITY_AT_STARTUP` the ex-style was
    `WS_EX_APPWINDOW|WS_EX_CONTROLPARENT|WS_EX_TOPMOST` — **no
    `WS_EX_TOOLWINDOW`** — although the shell had logged setting it a few lines
    earlier. WinForms re-applies `Form.CreateParams` (which sets
    `WS_EX_APPWINDOW` while `ShowInTaskbar` is true and there is no owner) when
    pywebview's startup `Opacity`/`Show`/`Hide` dance recreates the handle, and
    that wipes every bit added by `SetWindowLong`. `WS_EX_APPWINDOW` is the one
    that puts the panel in the taskbar, which is the surface the owner was
    looking at when he reported the Python icon.
    """
    if not hwnd:
        return {'hwnd': None}
    before = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
    after = set_ex_style(hwnd, add=WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                         remove=WS_EX_APPWINDOW)
    state = {
        'where': where, 'before': before, 'after': int(after),
        'toolwindow': bool(int(after) & WS_EX_TOOLWINDOW),
        'appwindow': bool(int(after) & WS_EX_APPWINDOW),
    }
    log(f"PANEL_EXSTYLE_REASSERT where={where} "
        f"before=0x{before:08x} after=0x{int(after):08x} "
        f"toolwindow={str(state['toolwindow']).lower()} "
        f"appwindow={str(state['appwindow']).lower()}")
    return state


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

#: The one name the shipped app uses. A DIFFERENT name is a private lock, and it
#: is deliberately not excused by the measurement flags (see `main`).
DEFAULT_MUTEX_NAME = 'Local\\SottoShell'


def take_single_instance_lock(name=DEFAULT_MUTEX_NAME) -> bool:
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


# ===========================================================================
# THE TRAY — the app's face and its Quit, where the owner asked for them
#
# Owner, 2026-10-08, verbatim: "tira o botao de quit sotto do painel. só tem q
# quit no icon do system tray". THE TRAY DID NOT EXIST: measured on 2026-10-08,
# `grep -rn 'pystray|NotifyIcon|Shell_NotifyIcon|QSystemTrayIcon' app/` returns
# ZERO matches. So the Quit had to be BUILT before it could be moved, or the
# owner would have been left with no way to close the app but the task manager.
#
# It is plain Win32 `Shell_NotifyIconW` on a MESSAGE-ONLY window owned by its own
# thread — no new dependency, and the icon is the one already generated for the
# window (`SOTTO_ICON`), not a second one.
#
# WHY ITS OWN THREAD AND ITS OWN WINDOW: the notification-area callback arrives
# as a message, so something has to pump. The hotkey thread cannot be borrowed
# (it exists only when a hotkey was registered — a `--no-hotkey` run has none),
# and the WebView2 UI loop is not ours to post into. One daemon thread with one
# `GetMessageW` loop is the whole cost.
# ===========================================================================

WM_APP = 0x8000
WM_TRAY_CALLBACK = WM_APP + 1
WM_TRAY_STOP = WM_APP + 2
WM_COMMAND = 0x0111
WM_RBUTTONUP = 0x0205
WM_LBUTTONUP = 0x0202
WM_DESTROY = 0x0002

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x01, 0x02, 0x04
MF_STRING, MF_SEPARATOR = 0x0000, 0x0800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x0002, 0x0100
HWND_MESSAGE = -3

TRAY_ID = 0xB0F1              # any uid; this one is ours
ID_TRAY_OPEN = 1              # "Open panel" — the FULL panel, not the strip
ID_TRAY_QUIT = 2              # "Quit Sotto" — the one the owner named
#: "Edit caption position" — the edit mode's ONLY entrance (owner's lane brief:
#: now that the tray exists it is the obvious home, and it is impossible to
#: trigger by accident while reading a caption). A 4th id, so the two shipped
#: items keep their numbers and the tray probe's `[2]='Quit Sotto'` lookup works.
ID_TRAY_EDIT = 3
TRAY_WINDOW_CLASS = 'SottoTrayWindow'
TRAY_TIP = 'Sotto — Alt+C shows the captions'

# Argtypes for the tray's own calls. Without them ctypes converts a Python int
# to a 32-bit C int and an HWND/HICON above 2**31 raises OverflowError.
user32.RegisterClassExW.restype = wt.WORD
user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
user32.CreateWindowExW.restype = wt.HWND
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wt.HWND, wt.HMENU,
                                   wt.HINSTANCE, ctypes.c_void_p]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t,
                                  ctypes.c_ssize_t]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.c_void_p, wt.HWND, ctypes.c_uint,
                               ctypes.c_uint]
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.restype = ctypes.c_ssize_t
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostMessageW.restype = wt.BOOL
user32.PostMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t,
                                ctypes.c_ssize_t]
user32.CreatePopupMenu.restype = wt.HMENU
user32.AppendMenuW.restype = wt.BOOL
user32.AppendMenuW.argtypes = [wt.HMENU, ctypes.c_uint, ctypes.c_size_t,
                               wt.LPCWSTR]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.TrackPopupMenu.argtypes = [wt.HMENU, ctypes.c_uint, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wt.HWND,
                                  ctypes.c_void_p]
user32.DestroyMenu.restype = wt.BOOL
user32.DestroyMenu.argtypes = [wt.HMENU]
user32.GetMenuItemCount.restype = ctypes.c_int
user32.GetMenuItemCount.argtypes = [wt.HMENU]
user32.GetMenuItemID.restype = ctypes.c_uint
user32.GetMenuItemID.argtypes = [wt.HMENU, ctypes.c_int]
user32.GetMenuStringW.restype = ctypes.c_int
user32.GetMenuStringW.argtypes = [wt.HMENU, ctypes.c_uint, wt.LPWSTR,
                                  ctypes.c_int, ctypes.c_uint]
user32.GetCursorPos.argtypes = [ctypes.c_void_p]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.LoadImageW.restype = wt.HANDLE
user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, ctypes.c_uint,
                              ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.DestroyIcon.argtypes = [wt.HICON]
kernel32.GetModuleHandleW.restype = wt.HMODULE
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
shell32.Shell_NotifyIconW.restype = wt.BOOL
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.c_void_p]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wt.DWORD), ('hWnd', wt.HWND), ('uID', ctypes.c_uint),
        ('uFlags', ctypes.c_uint), ('uCallbackMessage', ctypes.c_uint),
        ('hIcon', wt.HICON), ('szTip', wt.WCHAR * 128),
        ('dwState', wt.DWORD), ('dwStateMask', wt.DWORD),
        ('szInfo', wt.WCHAR * 256), ('uVersion', ctypes.c_uint),
        ('szInfoTitle', wt.WCHAR * 64), ('dwInfoFlags', wt.DWORD),
        ('guidItem', ctypes.c_byte * 16), ('hBalloonIcon', wt.HICON),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint), ('style', ctypes.c_uint),
        ('lpfnWndProc', ctypes.c_void_p), ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int), ('hInstance', wt.HINSTANCE),
        ('hIcon', wt.HICON), ('hCursor', ctypes.c_void_p),
        ('hbrBackground', ctypes.c_void_p), ('lpszMenuName', wt.LPCWSTR),
        ('lpszClassName', wt.LPCWSTR), ('hIconSm', wt.HICON),
    ]


class TrayIcon:
    """A notification-area icon with a real context menu.

    `on_command` is called with the menu id, from the tray thread. The menu is
    built with `TPM_RETURNCMD` and the chosen id is then posted back as a REAL
    `WM_COMMAND`, so the probe can drive the same handler the menu drives
    (`PostMessageW(tray_hwnd, WM_COMMAND, ID_TRAY_QUIT, 0)`) instead of a test
    hook that bypasses it.
    """

    def __init__(self, icon_path, on_command, log_fn, warn_fn):
        self.icon_path = icon_path
        self.on_command = on_command
        self.log = log_fn
        self.warn = warn_fn
        self.hwnd = None
        self.hicon = None
        self.menu = None
        self._thread = None
        self._ready = threading.Event()
        self._wndproc = None
        self._failed = None

    # -- lifecycle ---------------------------------------------------------
    def start(self, timeout=5.0) -> bool:
        self._thread = threading.Thread(target=self._run, name='sotto-tray',
                                        daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return self.hwnd is not None

    def stop(self, reason='stop'):
        if self.hwnd:
            try:
                self._delete()
                user32.PostMessageW(self.hwnd, WM_TRAY_STOP, 0, 0)
            except Exception:  # noqa: BLE001
                pass
        # NEVER JOIN THE CURRENT THREAD. The Quit is handled ON this thread (the
        # menu command arrives as a message), so `join` on it raised
        # `RuntimeError: cannot join current thread` — measured 2026-10-08, and
        # it left the shell ALIVE with its worker after the owner had asked it to
        # close: an app that will not quit is worse than one that will not start.
        # `PostQuitMessage` above ends the loop, so the thread stops by itself.
        if (self._thread is not None and self._thread.is_alive()
                and self._thread is not threading.current_thread()):
            self._thread.join(2)
        self.log(f'TRAY_STOP reason={reason} hwnd={self.hwnd}')

    # -- the icon ----------------------------------------------------------
    def _nid(self):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = TRAY_ID
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY_CALLBACK
        nid.hIcon = self.hicon
        nid.szTip = TRAY_TIP
        return nid

    def _add(self):
        nid = self._nid()
        ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
        self.log(f'TRAY_ICON_ADD ok={str(ok).lower()} uid={TRAY_ID} '
                 f'cbSize={nid.cbSize} hicon={self.hicon} '
                 f'icon={self.icon_path}')
        return ok

    def _delete(self):
        nid = self._nid()
        ok = bool(shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid)))
        self.log(f'TRAY_ICON_DELETE ok={str(ok).lower()} uid={TRAY_ID}')
        return ok

    # -- the thread --------------------------------------------------------
    def _run(self):
        try:
            self._create_window()
            if not self._load_icon():
                return
            if not self._add():
                return
            # The menu is BUILT AND LOGGED at startup, so its Quit item (id and
            # text) is on the record without anyone having to right-click. It is
            # destroyed here and rebuilt when it is actually drawn.
            user32.DestroyMenu(self._build_menu())
            self.menu = None
            self._ready.set()
            self._pump()
        except Exception as exc:  # noqa: BLE001 -- a tray must not kill the app
            self._failed = f'{type(exc).__name__}: {exc}'
            self.warn(f'TRAY_FAILED error={self._failed}')
            self._ready.set()
        finally:
            if self.hicon:
                user32.DestroyIcon(self.hicon)
                self.hicon = None

    def _load_icon(self) -> bool:
        """The SAME .ico the window wears — `LoadImageW` from the file."""
        if not self.icon_path or not os.path.isfile(self.icon_path):
            self.warn(f'TRAY_ICON_MISSING path={self.icon_path}')
            return False
        IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x0010, 0x0040
        handle = user32.LoadImageW(None, self.icon_path, IMAGE_ICON,
                                  16, 16, LR_LOADFROMFILE)
        if not handle:
            self.warn(f'TRAY_ICON_LOAD_FAILED path={self.icon_path} '
                      f'winerror={ctypes.get_last_error()}')
            return False
        self.hicon = handle
        return True

    def _create_window(self):
        hinst = kernel32.GetModuleHandleW(None)
        self._wndproc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND,
                                           ctypes.c_uint, ctypes.c_size_t,
                                           ctypes.c_ssize_t)(self._on_message)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = TRAY_WINDOW_CLASS
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS is fine (a restart)
                raise OSError(err, 'RegisterClassExW')
        hwnd = user32.CreateWindowExW(0, TRAY_WINDOW_CLASS, '', 0, 0, 0, 0, 0,
                                      HWND_MESSAGE, None, hinst, None)
        if not hwnd:
            raise OSError(ctypes.get_last_error(), 'CreateWindowExW')
        self.hwnd = int(hwnd)
        self.log(f'TRAY_WINDOW created=true hwnd={self.hwnd} '
                 f'class={TRAY_WINDOW_CLASS} message_only=true')

    def _on_message(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY_CALLBACK:
            if lparam in (WM_RBUTTONUP, WM_LBUTTONUP):
                self._show_menu()
            return 0
        if msg == WM_COMMAND:
            command = int(wparam) & 0xFFFF
            self.log(f'TRAY_COMMAND id={command}')
            try:
                self.on_command(command)
            except Exception as exc:  # noqa: BLE001
                self.warn(f'TRAY_COMMAND_FAILED id={command} '
                          f'{type(exc).__name__}: {exc}')
            return 0
        if msg == WM_TRAY_STOP:
            user32.PostQuitMessage(0)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self):
        menu = self._build_menu()
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        # SetForegroundWindow is what makes the menu dismiss correctly when the
        # owner clicks elsewhere; without it the menu can be left orphaned.
        user32.SetForegroundWindow(wt.HWND(self.hwnd))
        command = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                                        pt.x, pt.y, 0, wt.HWND(self.hwnd),
                                        None)
        user32.DestroyMenu(menu)
        self.menu = None
        if command:
            # A REAL WM_COMMAND, so the menu and the probe take one path.
            user32.PostMessageW(wt.HWND(self.hwnd), WM_COMMAND, command, 0)

    def _build_menu(self):
        """Built, LOGGED, and then drawn — so the log proves every item exists
        (its id and its text) without anyone having to click.

        THREE items now, and the two shipped ids keep their numbers: `[1]` Open
        panel (the FULL panel — Alt+C is what opens the strip), `[3]` Edit
        caption position, `[2]` Quit Sotto. `_main/tray-quit-probe.py` finds the
        Quit by its TEXT (`[2]='Quit Sotto'`), so a new item cannot break it.
        """
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, ID_TRAY_OPEN, 'Open panel')
        user32.AppendMenuW(menu, MF_STRING, ID_TRAY_EDIT,
                           'Edit caption position')
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_TRAY_QUIT, 'Quit Sotto')
        self.menu = int(menu)
        items = menu_items(menu)
        self.log('TRAY_MENU ' + ' '.join(
            f"[{i['id']}]={i['text']!r}" if i['id'] else '[sep]'
            for i in items))
        return menu

    def _pump(self):
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        self.log('TRAY_LOOP_EXIT')


def menu_items(menu) -> list:
    """The items of an HMENU, as Windows has them — id and text."""
    count = user32.GetMenuItemCount(menu)
    items = []
    buf = ctypes.create_unicode_buffer(128)
    for index in range(count):
        ident = user32.GetMenuItemID(menu, index)
        user32.GetMenuStringW(menu, index, buf, 128, 0x0400)  # MF_BYPOSITION
        items.append({'index': index, 'id': int(ident),
                      'text': buf.value if ident else ''})
    return items


# ===========================================================================
# ALT+C CLOSES WHEN THE OWNER CLICKS OUTSIDE
#
# Owner, 2026-10-08, verbatim: *"permita o alt c fechar quando eu clico pra fora
# dele"*.
#
# WHY THE OBVIOUS SIGNAL IS NOT AVAILABLE. "The window loses focus" cannot be
# read here, and that is a deliberate product decision, not an oversight: the
# panel is shown with `SW_SHOWNOACTIVATE` and carries `WS_EX_NOACTIVATE`, so it
# NEVER takes focus (it must not steal focus from a film or a game). A window
# that never activates can never receive `WM_ACTIVATE`/`WA_INACTIVE`, and
# `GetForegroundWindow() != ours` is true before the panel is even shown.
#
# WHY NOT `SetCapture`. Capture would route the outside click INTO this window,
# which means the click the owner aimed at the app underneath is SWALLOWED —
# exactly what the click-through panel exists to avoid.
#
# SO: a `WH_MOUSE_LL` hook, which only OBSERVES. It never consumes the click
# (`CallNextHookEx` is always reached), so the click still lands where he aimed
# it, and the panel goes away at the same time. The proc does one rect test and
# returns: a slow low-level hook stalls the mouse SYSTEM-WIDE, so nothing here
# blocks, and every path is wrapped.
#
# THE GUARDS, each of which is a case the owner would otherwise meet:
#   * the panel must be MEASURED visible (`IsWindowVisible`), never a cache;
#   * the click must be OUTSIDE the panel's rect — a click inside never closes;
#   * a click that lands on OUR OWN window (the tray menu, a dialog) is not
#     "outside", even when its coordinates are;
#   * the watcher is ARMED only once the owner has actually shown the panel, so
#     the two startup navigations cannot close anything by themselves.
# ===========================================================================

WH_MOUSE_LL = 14
HC_ACTION = 0
WM_LBUTTONDOWN, WM_RBUTTONDOWN = 0x0201, 0x0204
WM_MBUTTONDOWN, WM_XBUTTONDOWN = 0x0207, 0x020B
WM_MOUSEMOVE = 0x0200
WM_QUIT = 0x0012
WM_PROBE_CLICK = WM_APP + 9
#: EDIT MODE's drag sample: the hook proc POSTS this to its own thread instead of
#: moving the window inside the hook. The hook proc must return immediately — it
#: runs on the hook thread and a slow one stalls the pointer SYSTEM-WIDE — so the
#: `SetWindowPos` happens in the message loop, which is also where the rate is
#: bounded (`EDIT_DRAG_MIN_INTERVAL_MS`).
WM_EDIT_DRAG = WM_APP + 10

#: A few pixels of slack on the rect test: a click on the panel's own edge is
#: still a click on the panel, and the owner cannot aim to the pixel.
CLICK_OUTSIDE_SLACK = 2

#: The drag's ceiling: at most one `SetWindowPos` per this many ms (20 Hz). The
#: receipt's design says it plainly — moving the NATIVE window per frame is the
#: short path to flicker (`docs/release-and-overlay-plan.md:75-78`), so the drag
#: is a low-frequency move, not a smooth one.
EDIT_DRAG_MIN_INTERVAL_MS = 50


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [('pt', POINT), ('mouseData', wt.DWORD), ('flags', wt.DWORD),
                ('time', wt.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


user32.SetWindowsHookExW.restype = wt.HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                     wt.HINSTANCE, wt.DWORD]
user32.UnhookWindowsHookEx.restype = wt.BOOL
user32.UnhookWindowsHookEx.argtypes = [wt.HHOOK]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, ctypes.c_size_t,
                                  ctypes.c_ssize_t]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.c_void_p]
user32.GetForegroundWindow.restype = wt.HWND
user32.PostThreadMessageW.restype = wt.BOOL
user32.PostThreadMessageW.argtypes = [wt.DWORD, ctypes.c_uint, ctypes.c_size_t,
                                      ctypes.c_ssize_t]
user32.GetCurrentThreadId = None  # NOT in user32; see kernel32 below
kernel32.GetCurrentThreadId.restype = wt.DWORD
kernel32.GetCurrentThreadId.argtypes = []
user32.WindowFromPoint.restype = wt.HWND
user32.WindowFromPoint.argtypes = [POINT]


class OutsideClickWatcher(threading.Thread):
    """Watches for a mouse-down OUTSIDE the panel while the panel is visible."""

    def __init__(self, shell):
        super().__init__(name='sotto-outside-click', daemon=True)
        self.shell = shell
        self.hook = None
        self.armed = False
        self.thread_id = None
        self._ready = threading.Event()
        self._proc = None
        self.decisions = []
        # ── EDIT MODE, on THIS thread ────────────────────────────────────────
        # The drag is carried by the thread that already exists and already owns
        # a `WH_MOUSE_LL` hook and a message loop, so the edit mode adds NO
        # thread to the process. `edit_mode` is written by the UI thread (the
        # tray command) and read here; a plain bool is enough for that.
        self.edit_mode = False
        self._dragging = False
        self._last_drag_post = 0.0
        self.drag_samples = 0

    def start(self, timeout=5.0) -> bool:
        super().start()
        self._ready.wait(timeout)
        return self.hook is not None

    def stop(self, reason='stop'):
        if self.hook:
            try:
                user32.UnhookWindowsHookEx(self.hook)
            except Exception:  # noqa: BLE001
                pass
            self.hook = None
        if self.thread_id:
            try:
                user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
            except Exception:  # noqa: BLE001
                pass
        if self.is_alive() and self is not threading.current_thread():
            self.join(2)
        log(f'OUTSIDE_CLICK_STOP reason={reason}')

    # -- the hook ----------------------------------------------------------
    def run(self):
        """`run`, NOT `_run`: this class IS a Thread, and `Thread.start()` calls
        `self.run()`. Named `_run` it silently did NOTHING — the thread exited at
        once, `_ready` was never set, and the shell sat for the full 5 s timeout
        before reporting `OUTSIDE_CLICK_UNAVAILABLE`. Measured 2026-10-08. (The
        tray class can use `_run` because it is not a Thread; it passes `_run` as
        a `target`.)"""
        try:
            self.thread_id = int(kernel32.GetCurrentThreadId())
            self._proc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                                            ctypes.c_size_t,
                                            ctypes.c_ssize_t)(self._on_mouse)
            self.hook = user32.SetWindowsHookExW(
                WH_MOUSE_LL, ctypes.cast(self._proc, ctypes.c_void_p), None, 0)
            if not self.hook:
                warn(f'OUTSIDE_CLICK_HOOK_FAILED SetWindowsHookExW '
                     f'winerror={ctypes.get_last_error()}')
            log(f'OUTSIDE_CLICK_HOOK installed={str(bool(self.hook)).lower()} '
                f'hook={self.hook} thread={self.thread_id} type=WH_MOUSE_LL '
                f'consumes_click=false')
            self._ready.set()
            msg = MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_PROBE_CLICK:
                    # The MEASUREMENT path: the same decision function the hook
                    # calls, on the same thread, reached through this thread's
                    # real message loop. What is NOT exercised is the OS
                    # delivering a physical click.
                    x, y = _unpack_point(msg.wParam)
                    self._consider(x, y, WM_LBUTTONDOWN, source='probe')
                elif msg.message == WM_EDIT_DRAG:
                    # The drag sample the hook proc posted. The window move
                    # happens HERE, off the hook procedure, so the hook never
                    # blocks the pointer.
                    x, y = _unpack_point(msg.wParam)
                    self.shell.edit_drag_to(x, y, persist=bool(msg.lParam))
                else:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:  # noqa: BLE001 -- a watcher must not kill the app
            warn(f'OUTSIDE_CLICK_HOOK_FAILED {type(exc).__name__}: {exc}')
            self._ready.set()
        finally:
            log('OUTSIDE_CLICK_LOOP_EXIT')

    def _on_mouse(self, code, wparam, lparam):
        # FAST, and it always reaches CallNextHookEx: a low-level mouse hook that
        # raises or blocks stalls the pointer for the WHOLE machine.
        try:
            if code == HC_ACTION:
                message = int(wparam)
                if self.edit_mode:
                    # THE DRAG. Nothing here moves a window: the sample is POSTED
                    # to this thread's own message loop (see WM_EDIT_DRAG), and
                    # the post is rate-limited. The hook proc therefore costs a
                    # comparison and a `PostThreadMessageW`.
                    self._on_mouse_edit(message, lparam)
                elif message in (WM_LBUTTONDOWN, WM_RBUTTONDOWN,
                                 WM_MBUTTONDOWN, WM_XBUTTONDOWN):
                    info = ctypes.cast(lparam,
                                       ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    self._consider(int(info.pt.x), int(info.pt.y), message,
                                   source='hook')
        except Exception:  # noqa: BLE001
            pass
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _on_mouse_edit(self, message, lparam):
        """EDIT MODE's half of the hook: track the drag, move nothing."""
        if message == WM_LBUTTONDOWN:
            info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            x, y = int(info.pt.x), int(info.pt.y)
            hwnd = self.shell.hwnd
            if hwnd and _point_in_window(hwnd, x, y):
                rect = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                self.shell.edit_grab = (x - rect.left, y - rect.top)
                self._dragging = True
                self._last_drag_post = 0.0
                log(f'PANEL_EDIT_DRAG start point=({x},{y}) '
                    f'grab={self.shell.edit_grab}')
            else:
                # A press OUTSIDE the band does not drag it, and it must not
                # close it either — the owner is positioning the window, so an
                # outside click is not "put the panel away" while edit mode is on.
                self._record(x, y, 'hook', 'edit-mode-outside', closed=False)
            return
        if message == WM_MOUSEMOVE:
            if not self._dragging:
                return
            now = time.monotonic() * 1000.0
            if now - self._last_drag_post < EDIT_DRAG_MIN_INTERVAL_MS:
                return
            self._last_drag_post = now
            info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            self.drag_samples += 1
            user32.PostThreadMessageW(self.thread_id, WM_EDIT_DRAG,
                                      _pack_point(int(info.pt.x), int(info.pt.y)),
                                      0)
            return
        if message == WM_LBUTTONUP:
            if not self._dragging:
                return
            self._dragging = False
            info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            # `lParam=1` is the "and persist it" half: the drop is the moment the
            # rect becomes the one to restore.
            user32.PostThreadMessageW(self.thread_id, WM_EDIT_DRAG,
                                      _pack_point(int(info.pt.x), int(info.pt.y)),
                                      1)

    # -- the decision ------------------------------------------------------
    def _consider(self, x, y, message, source='hook'):
        """Returns True when this click closed the panel."""
        shell = self.shell
        reason = None
        hwnd = shell.hwnd
        if shell.exiting.is_set():
            reason = 'exiting'
        elif self.edit_mode:
            # The owner is POSITIONING the band. An outside click while edit mode
            # is on must not put the window away — the first missed grab would end
            # the edit he just asked for, and the tray item is the way out.
            reason = 'edit-mode'
        elif not self.armed:
            reason = 'not-armed'          # the startup navigations
        elif not hwnd or not window_visible(hwnd):
            reason = 'panel-not-visible'  # MEASURED, never the cache
        elif _point_in_window(hwnd, x, y):
            reason = 'inside'
        elif _window_is_ours(user32.WindowFromPoint(POINT(x, y))):
            reason = 'our-own-window'     # the tray menu, a dialog
        if reason is not None:
            self._record(x, y, source, reason, closed=False)
            return False
        self._record(x, y, source, 'outside', closed=True)
        shell.hide_panel('click-outside')
        return True

    def _record(self, x, y, source, reason, closed):
        entry = {'x': x, 'y': y, 'source': source, 'decision': reason,
                 'closed': closed}
        self.decisions.append(entry)
        del self.decisions[:-20]
        log(f'OUTSIDE_CLICK source={source} point=({x},{y}) '
            f'decision={reason} closed={str(closed).lower()} '
            f'armed={str(self.armed).lower()} '
            f'visible={str(bool(self.shell.hwnd and window_visible(self.shell.hwnd))).lower()}')


def _unpack_point(packed):
    """One integer carries both coordinates: x in the low 16 bits, y above."""
    value = int(packed)
    x = value & 0xFFFF
    y = (value >> 16) & 0xFFFF
    if x >= 0x8000:
        x -= 0x10000
    if y >= 0x8000:
        y -= 0x10000
    return x, y


def _pack_point(x, y):
    return (int(x) & 0xFFFF) | ((int(y) & 0xFFFF) << 16)


def _point_in_window(hwnd, x, y) -> bool:
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    return (rect.left - CLICK_OUTSIDE_SLACK <= x <= rect.right + CLICK_OUTSIDE_SLACK
            and rect.top - CLICK_OUTSIDE_SLACK <= y <= rect.bottom + CLICK_OUTSIDE_SLACK)


def _window_is_ours(hwnd) -> bool:
    """True when `hwnd` belongs to THIS process (our menu, our dialog)."""
    if not hwnd:
        return False
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(wt.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value) == os.getpid()


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

  var subs = { caption: [], status: [], geometry: [], stats: [] };
  var queue = [];
  var infoSeq = 0;
  var infoPending = {};
  var statsSeq = 0;
  var statsPending = {};

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

  // A COUNT OF WHAT ARRIVED, per kind. Not decoration: the panel's level meter
  // is fed BOTH by a poll (`getStats`, every 1000 ms) and by this push, so a
  // measurement that only saw `data-level="live"` could not tell a working push
  // from a poll doing all the work. `_main/_strip-stats-probe.py` reads this
  // counter and requires the PUSH to have landed more than once.
  window.__sotto_emit = function (kind, json) {
    var payload = null;
    try { payload = JSON.parse(json); } catch (err) { payload = null; }
    window.__sotto_emit.counts[kind] = (window.__sotto_emit.counts[kind] || 0) + 1;
    emit(kind, payload);
  };
  window.__sotto_emit.counts = {};

  window.__sotto_info = function (id, json) {
    var resolve = infoPending[id];
    if (!resolve) return;
    delete infoPending[id];
    try { resolve(JSON.parse(json)); } catch (err) { resolve({ error: String(err) }); }
  };

  // The worker's OWN counters, on the same id round-trip as `getInfo`, so
  // `bridge.getStats()` really resolves with a measurement instead of a
  // synchronous guess. The payload is the panel's whitelist and nothing else —
  // `peak` and `blocks` — and a field the worker never printed stays ABSENT
  // (`panel.js:1709` trusts only the fields it actually carries).
  window.__sotto_stats = function (id, json) {
    var resolve = statsPending[id];
    if (!resolve) return;
    delete statsPending[id];
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
    onStats: function (cb) { return subscribe('stats', cb); },

    hide: function () { post('hide', null); },
    toggle: function () { post('toggle', null); },
    quit: function () { post('quit', null); },

    // ── THE REPAIR CONTROL ──────────────────────────────────────────────────
    // `panel.js` `wireRevive` is the caller: the owner ruled (2026-10-08)
    // *"e o botao de error ou de idle sei que, ao clicar, deve fazer a pipeline
    // inteira ser revivida, se nao tiver funcionando"*. So the panel's status
    // (footer, and the strip's own state) is CLICKABLE, and one click means
    // kill the worker and start a new one — unconditionally, because a repair
    // control that argues with the owner about whether he needed it is worse
    // than no control. The `reason` travels so the log says who asked.
    revive: function (reason) {
      post('revive', { reason: String(reason == null ? 'panel' : reason) });
    },

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

    // ── THE WORKER'S OWN COUNTERS (`getStats`/`onStats`) ────────────────────
    // `panel.js:1695-1724` (`wireLevel`) subscribes to `onStats` AND polls
    // `getStats` once a second; it reads `peak` and `blocks` and nothing else,
    // and a MISSING field is not a measurement, so it must stay missing rather
    // than arrive as a zero this shell invented. The numbers come from the
    // worker's own `WORKER_STATS` line, which `WorkerBridge._pump` already
    // parses into `last_worker_stats`.
    getStats: function () {
      return new Promise(function (resolve) {
        var id = 's' + (++statsSeq);
        statsPending[id] = resolve;
        post('stats', { id: id });
      });
    },

    // ── THE SURFACE CONTRACT (the shell resizes; the page only wears it) ─────
    // `app/panel/panel.js:1239-1243` calls THIS member and nothing else:
    //
    //     bridge.setPanelSurface('panel', reason)
    //
    // Its absence is not cosmetic. Without it `openFullPanel` falls through to
    // `panel.js:1245-1247` — "switch the layout here ... The strip is NOT short
    // until the window is" — so the strip's own "Open panel" button left the
    // window strip-sized. The shell answers by setting the document surface
    // (`window.SottoSurfaces.set`, the API `surface.js` defines) AND moving the
    // HWND to that surface's geometry, in the same breath.
    setPanelSurface: function (surface, reason) {
      post('panel-surface', {
        surface: String(surface == null ? '' : surface),
        reason: String(reason == null ? '' : reason)
      });
      return true;
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
              'captionApplied', 'statusApplied', 'ready', 'clearApplied',
              // The two members this shell owed the panel: the surface switch
              // (it must resize the window) and the worker's own counters.
              // `revive` is the repair control the panel's status calls.
              'setPanelSurface', 'getStats', 'onStats', 'revive']
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
                 interval_s=PANEL_VISIBILITY_INTERVAL_S, extra=None):
        self.path = path
        #: `observe()` -> bool, read LIVE from the window at call time.
        self.observe = observe
        self.log = log
        self.interval_s = max(0.5, float(interval_s))
        #: `extra()` -> dict merged into every payload. It carries the `geometry`
        #: key the EDIT mode persists (see `SottoShell.geometry_snapshot`). Kept
        #: a callback rather than a dict so the file always names the rect the
        #: window has AT THE WRITE, not the one it had when this object was built.
        self.extra = extra
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
        # THE `geometry` KEY — additive, and it is why the edit mode does NOT get
        # a second file. `schema` stays `sotto.panel-visibility/1`: no field was
        # renamed or removed, and the worker's `PanelVisibilityReader` reads
        # `visible`/`writtenAtEpoch`/`staleAfterSeconds` and ignores every other
        # key (read, not assumed), so an extra key cannot change what the worker
        # does. A SECOND file could: the shell would write one and the worker's
        # poll would read the other, and nothing would say which was authoritative.
        if self.extra is not None:
            try:
                extra = self.extra()
            except Exception as exc:  # noqa: BLE001 -- the file must still land
                extra = None
                self.log(f'PANEL_VISIBILITY_EXTRA_FAILED error={exc!r}')
            if isinstance(extra, dict):
                payload['geometry'] = extra
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
            # THE REPAIR CONTROL. A `kind` of its own rather than reusing
            # `toggle`/`quit`: the panel's status is not a second hide button,
            # and the log has to be able to tell a revive from a hot reload.
            'revive': self._revive,
            'info': self._info,
            'stats': self._stats,
            'panel-surface': self._panel_surface,
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

    def _revive(self, payload):
        """The panel's status was clicked — see `SottoShell.revive_worker`.

        Nothing here decides WHETHER to revive: the owner asked for a repair
        control, so this only carries his request (and its reason) to the shell.
        """
        reason = str((payload or {}).get('reason') or 'panel')
        self._shell.revive_worker(reason)

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

    def _stats(self, payload):
        """`bridge.getStats()` — the panel's own pull, once a second.

        Served on the SAME id round-trip as `info`, so the panel gets a real
        resolved Promise rather than a synchronous guess, and so a reader of this
        log can tell a pull from a push.
        """
        stats_id = (payload or {}).get('id', '')
        self._shell.reply_stats(stats_id, self._shell.stats())

    def _panel_surface(self, payload):
        """`bridge.setPanelSurface(surface, reason)` — the member this shell owed.

        `panel.js:1239-1243` is the ONLY caller, and it calls it for exactly one
        thing: opening the FULL panel from the strip. The shell must switch the
        document surface AND resize the window, which is why this is a shell
        member and not a page-side attribute write.
        """
        payload = payload or {}
        self._shell.set_panel_surface(payload.get('surface'),
                                      payload.get('reason') or 'page')

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
        # ── THE REVIVE (the panel's status is a repair control) ─────────────
        # `revive_worker` runs on a thread of its own because
        # `WorkerBridge.stop` waits up to 5 s for the child, and the whole point
        # of the click is that the panel comes back. The lock plus this field
        # are what refuse a SECOND click while the first revive is in flight:
        # two overlapping respawns would leave one child orphaned.
        self._revive_lock = threading.Lock()
        self._revive_thread = None
        self.hotkey = None
        self.tray = None
        self.click_watcher = None
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
        # ── THE TWO SURFACES (owner, 2026-10-08) ─────────────────────────────
        #: The surface the owner's control opens. `'strip'` — the SHORT caption
        #: band at the bottom, horizontally centred — because
        #: `app/panel/surface.js:6-8` records the decision that Alt+C must NOT
        #: open the whole 380x900 panel. `--show` is the exception: it is the
        #: developer's "panel up now" and stays the FULL panel, byte for byte.
        self.surface = 'strip'
        #: The surface the WINDOW currently wears. The window is CREATED at the
        #: docked-panel geometry (`create_window`), so this starts as `'panel'`
        #: and the first Alt+C is what moves it to the strip — while it is still
        #: hidden, which is the only moment a `SetWindowPos` cannot flicker.
        self.surface_applied = 'panel'
        #: The strip's height is the STYLESHEET's (`panel.css:52`
        #: `--strip-height: 150px`), read at runtime by
        #: `refresh_strip_height()`; `strip_height_css` is the last value read
        #: from the page and `strip_height_extra` the runtime addition on top of
        #: it. `strip_height` is the sum — what the window is actually sized to.
        #: Changed at runtime with `set_strip_height()`.
        self.strip_height_css = None
        self.strip_height_extra = 0
        self.strip_height = STRIP_HEIGHT_FALLBACK
        #: The rect an EDIT session saved, read back from the `geometry` key of
        #: `_main/panel-visibility.json` at startup and re-written on every edit.
        #: `None` means "never edited" — the computed default stands.
        self.saved_geometry = None
        #: True while the owner is positioning the caption band (tray menu
        #: `Edit caption position`). See `set_edit_mode`.
        self.edit_mode = False
        self.edit_moves = 0
        #: The cursor's offset from the window origin, captured when the drag
        #: started, so the band follows the pointer instead of jumping to it.
        self.edit_grab = None
        #: Counters for the stats channel: a reply is the panel's POLL being
        #: answered, a push is the worker's own counters being forwarded.
        self.stats_replies = 0
        self.stats_pushes = 0
        #: Log aggregation for the per-sample push: the LAST count that was
        #: logged and when. One line per `STATS_LOG_INTERVAL_S` at most, so a
        #: tens-of-Hz meter cannot grow the log without bound.
        self.stats_logged = 0
        self.stats_logged_at = 0.0
        #: THE WAVE's own push counter. `stats_pushes` counts the pushes driven by
        #: the worker's stderr `WORKER_STATS` line; this counts the pushes driven
        #: by its stdout `meter` events. Both travel in `SHELL_EXIT`, because the
        #: push LOG prints once per interval and could never prove a 10 Hz feed.
        self.meter_pushes = 0

    # -- geometry ----------------------------------------------------------
    def compute_geometry(self):
        self.display = primary_display()
        self.geometry = dock_right(self.display['workArea'])
        return self.geometry

    # -- window ------------------------------------------------------------
    #: How much later than the REQUESTED `--exit-after` this second, HARD watchdog
    #: fires. The in-load timer (`_on_loaded`) is the documented "N seconds after
    #: load" exit and is unarmed until the panel loads; this one exists only for the
    #: window of time BEFORE that, where a hang upstream of the load (a WebView2 start
    #: that never completes, a bridge that blocks on its own lock) would otherwise
    #: leave an INVISIBLE shell alive forever with no timer at all. The grace period
    #: is generous so it can never pre-empt a healthy in-load exit.
    EXIT_WATCHDOG_GRACE_S = 60.0

    def _arm_exit_watchdog(self):
        """Arm a HARD self-kill for the window BEFORE the panel loads.

        MEASURED CONTEXT (this lane). A shell launched with `--exit-after N` is
        normally killed by the timer armed in `_on_loaded`. That timer does not
        exist until the panel loads, so a hang UPSTREAM of the load — a WebView2
        start that never reaches the receiver, `WorkerBridge.start()` blocking on
        its own non-reentrant lock — leaves a HIDDEN `pythonw` alive with no exit
        at all. Measured: one such shell (pid 40876) survived ~20 minutes and,
        worse, a leftover instance of any kind made SEVERAL LATER launches of
        this same shell stall before `RECEIVER_READY` (see the battery-RED
        investigation). An instrument that leaks one of these can poison the next
        several runs, so the fix belongs in the SHELL, not in each probe.

        WHY A HARD `os._exit` AND NOT `request_exit`: `request_exit` joins
        `bridge.stop()`, which takes the very `self._lock` a startup hang may be
        holding — so the graceful path cannot rescue exactly the case this
        watchdog exists for. This fires only if the process is still alive
        `exit_after + EXIT_WATCHDOG_GRACE_S` after the window was created, i.e.
        after any healthy run has already exited on its own.

        ADDITIVE and REVERSIBLE: it logs WHERE it was armed, it is a no-op
        without `--exit-after`, and it does not change the in-load timer's
        meaning.
        """
        if not self.args.exit_after:
            return
        grace = self.EXIT_WATCHDOG_GRACE_S
        delay = float(self.args.exit_after) + grace

        def _fire():
            log('SHELL_EXIT reason=exit-after-watchdog '
                f'where=window-created grace_s={grace} '
                'note=graceful-exit-never-fired')
            # Flush what we can, then leave NOW. `request_exit` is deliberately
            # NOT called: see the docstring.
            try:
                os._exit(0)
            except BaseException:  # noqa: BLE001
                os._exit(1)

        log(f'SHELL_EXIT_ARMED where=window-created after_s={delay:.1f} '
            f'(exit_after={self.args.exit_after} '
            f'+ grace={grace:.0f})')
        timer = threading.Timer(delay, _fire)
        timer.daemon = True
        timer.start()

    def create_window(self):
        import webview  # imported late: it loads the WinForms assemblies

        geometry = self.compute_geometry()
        # The rect the last EDIT session saved, read BEFORE anything is laid out:
        # `geometry_for()` consults it, so a restored position is what the first
        # Alt+C opens. It is a READ of the existing `_main/panel-visibility.json`
        # (the `geometry` key) — never a second file, which would let the shell
        # and the worker's poll disagree about which one is authoritative.
        self.restore_saved_geometry()
        self._arm_exit_watchdog()
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
            # NOT `icon=` HERE. `icon` is a parameter of `webview.start()`
            # (`webview/__init__.py:179`, applied to `_state['icon']` at :221-222)
            # and `create_window` (:309) does not accept it: passing it here
            # raised `TypeError` INSIDE `create_window`, which on pythonw.exe
            # (stdout and stderr both None) is a SILENT death — measured, the
            # run stopped at `panel geometry:` with no traceback and no window.
            # The icon is passed to `start()` below.
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

        # MEASUREMENT, and it changes nothing: what icon the form is carrying
        # and what the window answers for `WM_GETICON`. pywebview has already
        # run `BrowserForm.__init__` (winforms.py:773 runs before the
        # `before_show` at :775), so this reads the icon pywebview CHOSE.
        log(window_icon_report(form, self.hwnd))
        # ...and then the fix, on the same handle: the WinForms `Icon` property
        # plus three explicit `WM_SETICON` sends. Logged with its own read-back
        # so the two lines can be compared.
        _icon = apply_window_icon(form, self.hwnd)
        log(f"WINDOW_ICON_APPLIED applied={str(_icon['applied']).lower()} "
            f"path={_icon['path']} handle={_icon['handle']} "
            f"reason={_icon['reason']}")
        log(window_icon_report(form, self.hwnd))

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
        # The ex-style the shell asked for in `_on_before_show` does NOT survive
        # pywebview's startup dance — measured, see `reassert_taskbar_ex_style`.
        # This is the first moment after that dance, so it is where the bits are
        # put back.
        self.ex_style = reassert_taskbar_ex_style(hwnd, 'post-startup-dance')
        log(window_icon_report(form, hwnd))

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
                # `--show` is the DEVELOPER's "panel up now" and stays the FULL
                # panel: it is the one flag every measurement arm uses, and the
                # strip is what the owner's Alt+C opens, not what a probe asks
                # for. Passing it explicitly also means this call cannot be
                # changed by the strip default later.
                self.show_panel('startup', surface='panel')
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
            if self.args.probe_outside_click:
                # A short beat so the panel document has settled before the
                # three decisions are driven.
                log('OUTSIDE_CLICK_PROBE_ARMED s=2.0')
                timer = threading.Timer(2.0, self.run_outside_click_probe)
                timer.daemon = True
                timer.start()
            if self.args.probe_edit_mode:
                log('PANEL_EDIT_PROBE_ARMED s=2.0')
                timer = threading.Timer(2.0, self.run_edit_mode_probe)
                timer.daemon = True
                timer.start()
            if self.args.probe_stats:
                # Long enough for the panel's own 1000 ms poll to have run several
                # times against a worker that has published `WORKER_STATS`.
                wait = self.args.probe_stats_wait
                log(f'PANEL_STATS_PROBE_ARMED s={wait}')
                timer = threading.Timer(wait, self.run_stats_probe)
                timer.daemon = True
                timer.start()
            if self.args.probe_hover:
                log('PANEL_HOVER_PROBE_ARMED s=6.0')
                timer = threading.Timer(6.0, self.run_hover_probe)
                timer.daemon = True
                timer.start()
            if self.args.probe_revive > 0:
                # The repair control, measured from the DOM inwards: the wait is
                # long enough for a `--with-worker` child to have finished its
                # model load, because a revive with no child to kill proves
                # nothing about the pid changing.
                log(f'REVIVE_PROBE_ARMED s={self.args.probe_revive}')
                timer = threading.Timer(self.args.probe_revive,
                                        self.run_revive_probe)
                timer.daemon = True
                timer.start()
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
        if self.surface_applied == 'strip':
            # The stylesheet may have just changed under us (a theme edit is
            # exactly what a hot reload carries), and the window's height is the
            # stylesheet's number — so re-read it and re-apply if it moved.
            if self.refresh_strip_height('hot-reload'):
                self._apply_window_geometry(self.geometry_for('strip'),
                                            reason='strip-height-hot-reload')
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

        THE CALLABLE IS WRAPPED, and that is not decoration. `BeginInvoke` runs
        it on the UI thread, so anything it raises is an UNHANDLED exception in
        the message loop: WinForms answers that with
        `System.Windows.Forms.ThreadExceptionDialog` — a VISIBLE window, which
        this repo forbids, on the owner's screen, for a defect nobody asked to
        see. Measured 2026-10-08: a `NameError` in a posted callable produced
        neither a log line nor a crash, and the run looked healthy. A failure
        here is a log line, never a dialog.
        """
        from System import Func, Type  # pythonnet, loaded by pywebview

        form = self.form or self._form()
        if form is None:
            return

        def guarded():
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                warn(f'POSTED_CALLABLE_FAILED fn={getattr(fn, "__name__", fn)} '
                     f'{type(exc).__name__}: {exc}')

        form.BeginInvoke(Func[Type](guarded))

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

    def emit_async(self, kind, payload):
        """`emit` WITHOUT waiting for the round trip — for a per-sample feed.

        `emit` blocks on a `Task[String]` completion, which is right for a caption
        (the caller wants to know it landed) and WRONG for the stats channel: the
        worker may publish a meter sample at tens of Hz, and every one of those
        round trips would stall whoever called it. Measured on this host: the
        pump thread delivers captions on the same thread that reads the worker's
        stderr, so a blocking push per sample would delay the captions
        themselves.

        So this posts the script through `_ui` (a `BeginInvoke`, no wait) and
        drops the resulting `Task`. Ordering between two `emit_async` calls is not
        guaranteed, and does not need to be: each one carries a WHOLE payload, and
        the panel's `pushLevel` is a pure function of the last one it saw.
        """
        from System import Action, Func, Object, String
        from System.Threading.Tasks import Task

        script = ('window.__sotto_emit(' + json.dumps(kind) + ','
                  + json.dumps(json.dumps(payload)) + ')')

        def _complete(task):
            try:
                if task.IsFaulted:
                    warn(f'emit_async failed: {task.Exception!r}')
            except Exception as exc:  # noqa: BLE001
                warn(f'emit_async failed: {exc!r}')

        def _run():
            self.webview2.Invoke(Func[Object](
                lambda: self.core.ExecuteScriptAsync(script).ContinueWith(
                    Action[Task[String]](_complete))))

        try:
            self._ui(_run)
        except Exception as exc:  # noqa: BLE001
            warn(f'emit_async failed: {exc!r}')

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
                # The layout state, so a reader of this file can tell which
                # surface the window wears without a second instrument.
                'surface': self.surface,
                'surfaceApplied': self.surface_applied,
                'stripHeight': self.strip_height,
                'editMode': self.edit_mode,
                'editMoves': self.edit_moves,
                'savedGeometry': self.saved_geometry,
                # ── THE STALENESS QUERY, IN THE STATE FILE ───────────────────
                # "Am I running old code?" must be a LOOKUP, not a discovery
                # made by the owner reporting a defect that was already fixed.
                # `shell.code.shell.stale` is the one nobody can reload: a Python
                # process reads its source once, so a changed `sotto_webview.py`
                # under a live session needs a deliberate restart, and the hint
                # travels with the fact.
                'code': self._reload_policy.state(),
                'meterPushes': self.meter_pushes,
                'statsPushes': self.stats_pushes,
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
            extra=self.geometry_snapshot,
        )
        return self.panel_visibility.start()

    def observe_panel_visible(self) -> bool:
        """The LIVE answer: is the panel window on screen right now?"""
        hwnd = self.hwnd
        return bool(window_visible(hwnd)) if hwnd else False

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

    # -- the two surfaces: the strip (Alt+C) and the full panel ------------
    def work_area(self):
        """The WORK area of the display this shell lays out in, in DIP.

        `primary_display()` is the one source: `MonitorFromPoint(POINT(0,0),
        MONITOR_DEFAULTTOPRIMARY)` — the PRIMARY monitor, the same one the docked
        panel has always used. On this box there is exactly ONE monitor
        (`_main/_strip-work-area-probe.ps1`: `monitors=1`, `work=[0,0 1920x1032]`,
        DPI 96), so "which monitor does the strip open on" cannot be measured
        here and is NOT guessed at: it opens on the primary, like the panel, and
        the multi-monitor case is disclosed as unmeasured in
        `_main/receipt-strip-surface.md`.
        """
        display = self.display or primary_display()
        self.display = display
        return display['workArea']

    def geometry_for(self, surface):
        """The rect `surface` wants, in the CURRENT work area.

        A saved (edited) rect wins over the computed default, and is clamped into
        the work area — the honest answer to a resolution change, which this lane
        did NOT measure. The clamp says so in the log when it MOVES anything, so
        a window the owner placed is never silently relocated.
        """
        work = self.work_area()
        saved = self.saved_geometry
        if isinstance(saved, dict) and saved.get('surface') == surface:
            geometry, moved = clamp_geometry(saved, work)
            if moved:
                log('PANEL_GEOMETRY_CLAMPED '
                    f'surface={surface} '
                    f'was={saved.get("width")}x{saved.get("height")}'
                    f'@({saved.get("x")},{saved.get("y")}) '
                    f'now={geometry["width"]}x{geometry["height"]}'
                    f'@({geometry["x"]},{geometry["y"]}) '
                    f'work={geometry["workWidth"]}x{geometry["workHeight"]}'
                    f'@({geometry["workX"]},{geometry["workY"]})')
            return geometry
        if surface == 'strip':
            return strip_geometry(work, self.strip_height)
        return dock_right(work)

    def strip_height_from_css(self):
        """The strip's height, READ OUT OF THE STYLESHEET. `None` if unavailable.

        The panel lane's rule, and it is the right one: the CSS is the SINGLE
        source of truth for this number (`panel.css:52`, with `:1060` deriving the
        content floor from it), so the shell must not carry a second copy. The
        property is read off `document.documentElement` — `:root` is where it is
        declared — and its `"150px"` is parsed to a number. Anything that is not a
        positive finite pixel value answers `None` and the caller falls back, with
        the fallback logged.
        """
        script = ("(() => {"
                  "const v = getComputedStyle(document.documentElement)"
                  f".getPropertyValue('{STRIP_HEIGHT_CSS_VAR}');"
                  "return v === null || v === undefined ? null : String(v).trim();"
                  "})()")
        try:
            raw = self.exec_js(script)
        except Exception as exc:  # noqa: BLE001
            log(f'STRIP_HEIGHT_CSS_FAILED error={exc!r}')
            return None
        if not isinstance(raw, str) or not raw:
            return None
        text = raw.strip().lower()
        if text.endswith('px'):
            text = text[:-2].strip()
        try:
            value = float(text)
        except ValueError:
            log(f'STRIP_HEIGHT_CSS_UNPARSED raw={json.dumps(raw)}')
            return None
        if not (value > 0) or value != value or value > 2000:
            log(f'STRIP_HEIGHT_CSS_UNUSABLE raw={json.dumps(raw)}')
            return None
        return value

    def refresh_strip_height(self, reason='surface-strip'):
        """Re-read the stylesheet's height and adopt it, once per real change.

        `self.strip_height_extra` is the runtime ADDITION (0 today — nothing calls
        `set_strip_height`, because the hover reveal is the panel lane's CSS). So
        the window height is `css + extra`, and a theme edit moves the window on
        the next strip application. Returns True when the number moved.
        """
        value = self.strip_height_from_css()
        if value is None:
            if self.strip_height_css is None:
                log(f'STRIP_HEIGHT source=fallback '
                    f'value={self.strip_height} reason={reason} '
                    f'why=css-unavailable')
            return False
        value = int(round(value))
        if value == self.strip_height_css:
            return False
        was = self.strip_height
        self.strip_height_css = value
        self.strip_height = value + self.strip_height_extra
        log(f'STRIP_HEIGHT from={was} to={self.strip_height} source=css '
            f'css_value={value} extra={self.strip_height_extra} reason={reason}')
        return True

    def set_strip_height(self, height, reason='runtime'):
        """Change the strip's height AT RUNTIME and re-derive the window.

        The height is the STYLESHEET's (`panel.css:52`), so this does not replace
        it: it records an ADDITION on top of it (`strip_height_extra`), which is
        how a future reveal can grow the band without a second copy of the base
        number. Nothing calls it today. Returns True when the number moved.
        """
        try:
            value = int(height)
        except (TypeError, ValueError):
            warn(f'STRIP_HEIGHT_REFUSED value={height!r} reason={reason}')
            return False
        value = max(48, min(value, 2000))
        base = self.strip_height_css if self.strip_height_css is not None \
            else STRIP_HEIGHT_FALLBACK
        if value == self.strip_height:
            return False
        log(f'STRIP_HEIGHT from={self.strip_height} to={value} source=override '
            f'base={base} extra={value - base} reason={reason}')
        self.strip_height_extra = value - base
        self.strip_height = value
        if self.surface == 'strip':
            self.set_panel_surface('strip', f'height-{reason}')
        return True

    def set_panel_surface(self, surface, reason='page'):
        """`bridge.setPanelSurface(surface, reason)` — layout AND window, together.

        THE MEMBER THIS SHELL OWED THE PANEL. Before it existed, `grep -n
        'surface|SottoSurfaces|strip' app/webview/sotto_webview.py` matched 37
        lines and NOT ONE was an implementation of this call, so
        `panel.js:1241`'s test failed and `openFullPanel` fell through to
        `panel.js:1245-1247` — switch the layout, leave the window strip-sized.

        The two halves are ONE action on purpose. Setting the attribute alone
        gives a 380x900 column wearing strip CSS; resizing alone gives a strip
        window wearing panel CSS. Order: the DOCUMENT first (`exec_js` waits for
        the script), then the HWND, so the window never shows one surface's
        stylesheet at the other surface's size.
        """
        name = normalise_surface_name(surface)
        if name is None:
            warn(f'PANEL_SURFACE_REFUSED surface={json.dumps(str(surface))} '
                 f'reason={reason}')
            return False
        self.surface = name
        if name == 'strip':
            # THE STYLESHEET DECIDES THE HEIGHT (`panel.css:52`), and this is the
            # moment it matters: the page is loaded by the time a surface is
            # applied, so the read answers with the real number instead of a copy
            # kept in this file.
            self.refresh_strip_height(f'surface-{reason}')
        script = ('(function () { if (window.SottoSurfaces) { '
                  'window.SottoSurfaces.set(' + json.dumps(name) + '); '
                  'return window.SottoSurfaces.current(); } return null; })()')
        applied = self.exec_js(script)
        geometry = self.geometry_for(name)
        self._apply_window_geometry(geometry, reason=f'surface-{name}')
        self.surface_applied = name
        log(f'PANEL_SURFACE surface={name} reason={reason} '
            f'document_surface={json.dumps(applied)} '
            f'window={geometry["width"]}x{geometry["height"]}'
            f'@({geometry["x"]},{geometry["y"]}) '
            f'docked={geometry["docked"]} '
            f'edit_mode={str(self.edit_mode).lower()}')
        self.publish_panel_visibility(f'surface-{name}')
        return True

    def _apply_window_geometry(self, geometry, reason='surface'):
        """Move/resize the NATIVE window, then pin the client area to it.

        ONE call per surface change and one per edit-mode drag sample — never per
        frame. `docs/release-and-overlay-plan.md:75-78` is the warning this obeys:
        moving the native window every frame is the short path to flicker.
        """
        self.geometry = geometry
        hwnd = self.hwnd
        scale = (self.display or {}).get('scaleFactor') or 1.0
        if hwnd:
            ctypes.set_last_error(0)
            ok = user32.SetWindowPos(
                hwnd, HWND_TOPMOST,
                int(geometry['x'] * scale), int(geometry['y'] * scale),
                int(geometry['width'] * scale), int(geometry['height'] * scale),
                SWP_NOACTIVATE)
            # The ERROR CODE, not just the boolean: measured on this host,
            # `ok=false` with the size applied and the position NOT — which is
            # only diagnosable from the code (`1400` = ERROR_INVALID_WINDOW_HANDLE
            # is what a mis-marshalled `HWND_TOPMOST` produces).
            log(f'WINDOW_GEOMETRY reason={reason} ok={str(bool(ok)).lower()} '
                f'last_error={ctypes.get_last_error()} '
                f'window={geometry["width"]}x{geometry["height"]}'
                f'@({geometry["x"]},{geometry["y"]}) '
                f'docked={geometry["docked"]} '
                f'visible={str(window_visible(hwnd)).lower()}')
        # The CLIENT area is forced after every resize, for the reason
        # `_fit_client_area` documents: pywebview sizes the WebView2 child to the
        # client area computed under the OLD border, so a resize without this
        # leaves the document laid out at the previous size.
        try:
            self._ui(lambda: self._fit_client_area(self._form()))
        except Exception as exc:  # noqa: BLE001 -- report, never kill the panel
            warn(f'WINDOW_GEOMETRY_CLIENT_FAILED reason={reason} error={exc!r}')
        self.send_geometry()

    def geometry_snapshot(self):
        """The rect to PERSIST, in the shape the `geometry` key carries.

        The surface is the one the WINDOW wears (`surface_applied`), never the
        one the owner's next Alt+C will ask for: at startup the window is at the
        docked-panel rect while `self.surface` already says `'strip'`, and
        labelling that rect `strip` would teach the restore path to open the
        strip at the panel's size.
        """
        geometry = self.geometry
        if not isinstance(geometry, dict):
            return None
        return {
            'surface': self.surface_applied,
            'x': int(geometry.get('x') or 0),
            'y': int(geometry.get('y') or 0),
            'width': int(geometry.get('width') or 0),
            'height': int(geometry.get('height') or 0),
            'docked': str(geometry.get('docked') or ''),
            'workWidth': int(geometry.get('workWidth') or 0),
            'workHeight': int(geometry.get('workHeight') or 0),
        }

    def restore_saved_geometry(self):
        """Read the `geometry` key the last edit wrote, and CLAMP it.

        ONE FILE, NOT TWO. `_main/panel-visibility.json` already exists and is
        written by `PanelVisibilityWriter`; a second file would let the shell and
        the worker's poll disagree about which one is authoritative. The key is
        additive: `schema` stays `sotto.panel-visibility/1` because no field was
        renamed or removed, and the worker's reader (`PanelVisibilityReader`)
        reads `visible`/`writtenAtEpoch`/`staleAfterSeconds` and ignores the rest
        — verified by reading it, not assumed.

        The clamp happens HERE, once, so the log carries the move exactly once
        instead of on every show.
        """
        try:
            with open(PANEL_VISIBILITY_PATH, encoding='utf-8') as fh:
                payload = json.load(fh)
        except FileNotFoundError:
            return None
        except Exception as exc:  # noqa: BLE001 -- a bad file is not a crash
            warn(f'PANEL_GEOMETRY_RESTORE_FAILED path={PANEL_VISIBILITY_PATH} '
                 f'error={exc!r}')
            return None
        rect = payload.get('geometry') if isinstance(payload, dict) else None
        if not isinstance(rect, dict):
            return None
        name = normalise_surface_name(rect.get('surface'))
        if name is None:
            warn('PANEL_GEOMETRY_RESTORE_REFUSED '
                 f'surface={json.dumps(str(rect.get("surface")))}')
            return None
        geometry, moved = clamp_geometry(rect, self.work_area())
        self.saved_geometry = {
            'surface': name, 'x': geometry['x'], 'y': geometry['y'],
            'width': geometry['width'], 'height': geometry['height'],
            'docked': geometry['docked'],
        }
        log('PANEL_GEOMETRY_RESTORED '
            f'surface={name} '
            f'rect={geometry["width"]}x{geometry["height"]}'
            f'@({geometry["x"]},{geometry["y"]}) '
            f'writtenAt={payload.get("writtenAt")} '
            f'clamped={str(moved).lower()}')
        if moved:
            log('PANEL_GEOMETRY_CLAMPED '
                f'surface={name} '
                f'was={rect.get("width")}x{rect.get("height")}'
                f'@({rect.get("x")},{rect.get("y")}) '
                f'now={geometry["width"]}x{geometry["height"]}'
                f'@({geometry["x"]},{geometry["y"]}) '
                f'work={geometry["workWidth"]}x{geometry["workHeight"]}'
                f'@({geometry["workX"]},{geometry["workY"]})')
        return self.saved_geometry

    def show_panel(self, reason, surface=None):
        if self.hwnd is None:
            return False
        # THE STRIP IS WHAT ALT+C OPENS, AND THE RESIZE HAPPENS HERE — while the
        # window is still HIDDEN. This is the one moment a `SetWindowPos` on the
        # native window cannot flicker (`docs/release-and-overlay-plan.md:75-78`),
        # and it is why the surface is applied on the SHOW path rather than at
        # startup: the window is CREATED at the docked-panel geometry, so every
        # existing arm that reads `panel geometry:` keeps reading what it always
        # read, and the strip is what the owner meets when he presses Alt+C.
        #
        # `surface=` is the EXPLICIT override: `--show` and the tray's
        # `Open panel` pass `'panel'`, because both mean the full column.
        want = surface or self.surface
        if want != self.surface_applied:
            self.set_panel_surface(want, reason)
        set_topmost(self.hwnd)
        # SW_SHOWNOACTIVATE, not Show(): the panel must never take focus away
        # from whatever the owner is typing into (main.js: `focusable=false`).
        show_without_activating(self.hwnd)
        self.visible = window_visible(self.hwnd)
        # ARMED HERE, and only here: the watcher can close the panel from now on,
        # which is what keeps the two startup navigations from closing anything
        # (the panel is hidden then, so the visible-guard already refuses, and
        # this makes it explicit rather than incidental).
        if self.click_watcher is not None and self.visible:
            self.click_watcher.armed = True
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
        if live:
            return self.hide_panel(reason)
        # ALT+C OPENS THE STRIP — ALWAYS, and that is a pin, not a default. The
        # owner's decision (`app/panel/surface.js:6-8`) is about the HOTKEY, so
        # the hotkey asks for `'strip'` explicitly: if he had opened the full
        # panel from the strip's own button (`bridge.setPanelSurface('panel')`,
        # which sets `self.surface`), Alt+C must still give him the short band
        # and not the panel he just left. Every other caller keeps the shell's
        # current surface.
        return self.show_panel(
            reason, surface='strip' if reason == 'hotkey' else None)

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
            # The surface the owner's Alt+C opens, the one the window WEARS, and
            # the strip's runtime height. Reported here because `getInfo` is the
            # one place a probe can read the shell's own idea of its layout
            # without a second channel.
            'surface': self.surface,
            'surfaceApplied': self.surface_applied,
            'stripHeight': self.strip_height,
            'editMode': self.edit_mode,
        }

    def reply_info(self, info_id, payload):
        self.exec_js(f'window.__sotto_info({json.dumps(info_id)}, '
                     f'{json.dumps(json.dumps(payload))})')

    # -- worker stats on the bridge (getStats / onStats) --------------------
    def stats(self):
        """The worker's OWN counters, whitelisted to what the panel reads.

        THE SHAPE IS THE PANEL'S, NOT THIS FILE'S. `panel.js:1702-1710` reads
        `peak` and `blocks`; `panel.js:1738-1740` (the "behind" chip) reads
        `queue_drops` and `rate`, which this shell does not compute — and it must
        NOT invent them, because a fabricated `rate` would light a chip about a
        lag nobody measured. So the payload is exactly `{peak, blocks}`.

        TWO SOURCES, ONE SHAPE, AND THE WAVE WINS WHILE IT IS FRESH:

        * `{"type":"meter","peak":…,"blocks":…}` on STDOUT, once per meter window
          (10 Hz by default) — `peak` is the peak OF THAT WINDOW, and this is what
          a wave must be drawn from;
        * the `WORKER_STATS` line on STDERR, once per its own interval — `peak`
          there is the RUNNING MAXIMUM of the whole run, and a wave drawn from a
          running maximum is a staircase that only rises and then flattens. That
          IS the defect the owner reported.

        So a meter sample younger than `METER_FRESH_S` supplies the payload and
        the stats line is not consulted at all: the two are NEVER MIXED, because
        a window peak next to a run-maximum `blocks` would be two different
        pictures of one measurement. With no meter (the worker's `--meter-hz 0`,
        or an older worker) the behaviour is exactly what it was.

        `last_worker_stats` is `{'tag', 'fields', 'line'}` (`parse_worker_stats`)
        and the numbers live in `fields` as the STRINGS the worker printed. A
        field the worker did not print stays ABSENT: `panel.js:1641` refuses a
        non-finite peak, so absent means "no measurement", never a zero.
        """
        meter = getattr(self.bridge, 'last_meter', None) \
            if self.bridge is not None else None
        if isinstance(meter, dict) and (
                time.monotonic() - float(meter.get('at') or 0.0)) <= METER_FRESH_S:
            payload = {}
            for key in ('peak', 'blocks'):
                value = meter.get(key)
                if value is not None:
                    payload[key] = float(value)
            return payload
        raw = getattr(self.bridge, 'last_worker_stats', None) \
            if self.bridge is not None else None
        fields = raw.get('fields') if isinstance(raw, dict) else None
        payload = {}
        if isinstance(fields, dict):
            for key in ('peak', 'blocks'):
                value = fields.get(key)
                if value is None:
                    continue
                try:
                    payload[key] = float(value)
                except (TypeError, ValueError):
                    continue
        return payload

    def reply_stats(self, stats_id, payload):
        # LOGGED, not silent: the panel's own poll (`panel.js:1722`, every 1000 ms)
        # is the only way to tell "the member exists" from "the member is ANSWERED".
        # The first reply and then every 60th — one line a minute at the panel's
        # cadence, so the log stays readable while the channel stays visible.
        self.stats_replies += 1
        if self.stats_replies == 1 or self.stats_replies % 60 == 0:
            log(f'BRIDGE_STATS_REPLY id={stats_id} count={self.stats_replies} '
                f'payload={json.dumps(payload, separators=(",", ":"))}')
        self.exec_js(f'window.__sotto_stats({json.dumps(stats_id)}, '
                     f'{json.dumps(json.dumps(payload))})')

    def on_worker_stats(self, parsed):
        """PUSH half of the stats channel: the worker just published counters.

        Same payload as `stats()` — one shape for the pull and the push, so the
        panel cannot receive two different pictures of one measurement.

        TWO RULES, both learned the hard way:

        * **NO LOG LINE PER SAMPLE.** The meter is a per-sample feed (the worker
          may publish tens of Hz), and a line per sample is a log that grows
          without bound — that flood is why the worker's meter default was once
          turned OFF, i.e. a feature was disabled to keep a log quiet. This logs
          the FIRST push and then at most ONE line per `STATS_LOG_INTERVAL_S`,
          carrying the number of pushes it stands for. The bytes-per-minute
          before/after are in `_main/receipt-strip-surface.md`.
        * **NO WAITING.** The push is `emit_async` — the pump thread that calls
          this is the same one that carries captions, and a blocking round trip
          per meter sample would delay them.
        """
        payload = self.stats()
        self.stats_pushes += 1
        self._stats_log_maybe(payload)
        self.emit_async('stats', payload)

    def _stats_log_maybe(self, payload):
        """At most one `BRIDGE_STATS_PUSH` line per interval, with a count."""
        now = time.monotonic()
        first = self.stats_logged == 0
        due = (now - self.stats_logged_at) >= STATS_LOG_INTERVAL_S
        if not (first or due):
            return
        window = 0.0 if first else now - self.stats_logged_at
        log(f'BRIDGE_STATS_PUSH count={self.stats_pushes} '
            f'in_window_s={round(window, 1)} '
            f'rate_hz={round((self.stats_pushes - self.stats_logged) / window, 2) if window > 0 else "first"} '
            f'payload={json.dumps(payload, separators=(",", ":"))}')
        self.stats_logged = self.stats_pushes
        self.stats_logged_at = now

    def on_worker_meter(self, sample):
        """PUSH half of the WAVE: the worker closed a meter window.

        Called from the bridge's stdout pump — the SAME thread that carries the
        captions — once per window (10 Hz by default). Two rules, both already
        learned on the stats push next door:

        * **NO WAITING**: `emit_async`, so a slow page cannot delay a caption.
        * **NO LOG LINE PER SAMPLE**: the bridge logs `BRIDGE_METER` on its own
          budget (first sample, then one per `METER_LOG_INTERVAL_S`); this half
          logs NOTHING per sample, and its count travels in `SHELL_EXIT` as
          `meterPushes=`. A line here would re-create exactly the 20.5 KB/min
          flood that the meter's own branch removed.

        The payload is `stats()`, not the raw sample: it is the SAME shape the
        poll returns, so the push and the pull cannot disagree — and because a
        fresh meter sample is what `stats()` reads first, the payload IS this
        window's `{peak, blocks}`.
        """
        self.meter_pushes += 1
        self.emit_async('stats', self.stats())

    def quit(self, reason):
        self.request_exit(0, reason=reason)

    # -- tray --------------------------------------------------------------
    def start_tray(self) -> bool:
        """The icon in the notification area, and its Quit.

        Owner, 2026-10-08: *"tira o botao de quit sotto do painel. só tem q quit
        no icon do system tray"* — so this is now the ONLY way to close the app,
        and a tray that fails to appear would leave him with the task manager.
        It therefore says so LOUDLY (`TRAY_FAILED`) instead of being a silent
        missing feature.
        """
        self.tray = TrayIcon(SOTTO_ICON, self.tray_command, log, warn)
        ok = self.tray.start()
        if not ok:
            warn('TRAY_UNAVAILABLE the notification-area icon did not come up; '
                 'the app keeps running and Alt+C still works, but the Quit '
                 f'has no home (error={self.tray._failed})')
        return ok

    def tray_command(self, command):
        if command == ID_TRAY_QUIT:
            log('TRAY_QUIT requested=true')
            self.request_exit(0, reason='tray-quit')
        elif command == ID_TRAY_OPEN:
            # THE FULL PANEL, because that is what the item says. Alt+C is what
            # opens the SHORT strip (`surface.js:6-8`); the tray is the owner's
            # deliberate way to the whole column, and the strip's own "Open
            # panel" button takes the same road through
            # `bridge.setPanelSurface('panel')`.
            log('TRAY_OPEN requested=true surface=panel')
            live = window_visible(self.hwnd) if self.hwnd else False
            if live and self.surface == 'panel':
                self.hide_panel('tray')
            else:
                self.show_panel('tray', surface='panel')
        elif command == ID_TRAY_EDIT:
            log('TRAY_EDIT requested=true')
            self.set_edit_mode(not self.edit_mode, 'tray')

    # -- EDIT MODE (the caption band's position, persisted) ----------------
    def set_edit_mode(self, enabled, reason='tray'):
        """Turn the caption band's position editor on or off.

        ENTERED FROM THE TRAY ONLY. The owner's brief: `Edit caption position` is
        "the obvious home now that the tray exists, and it is impossible to
        trigger by accident while reading a caption" — no always-visible chrome
        on the panel, no hotkey.

        WHY THE EX-STYLES CHANGE. A panel that is click-through
        (`WS_EX_TRANSPARENT`) and never activates (`WS_EX_NOACTIVATE`) cannot be
        grabbed or receive a drag: those two bits are exactly what makes Alt+C
        usable over a film, so they are lifted for the duration of the edit and
        put back on the way out. `make_click_through(hwnd, False)` is the existing
        helper, and the NOACTIVATE bit is cleared with the same `set_ex_style` the
        pointer-interactive path uses.
        """
        enabled = bool(enabled)
        if enabled == self.edit_mode:
            return False
        hwnd = self.hwnd
        if hwnd is None:
            warn(f'PANEL_EDIT_MODE_REFUSED on={enabled} reason={reason} '
                 'no_window=true')
            return False
        self.edit_mode = enabled
        if enabled:
            # The band has to be ON SCREEN to be positioned — and the strip is
            # what the owner is positioning, so the show path applies it (and
            # does the resize while the window is still hidden).
            if not window_visible(hwnd):
                self.show_panel(f'edit-{reason}')
            try:
                make_click_through(hwnd, False)
                set_ex_style(hwnd, remove=WS_EX_NOACTIVATE)
            except Exception as exc:  # noqa: BLE001 -- report, never kill the app
                warn(f'PANEL_EDIT_MODE_STYLE_FAILED error={exc!r}')
            if self.click_watcher is not None:
                # The watcher's own thread reads this; it also STOPS closing the
                # panel on an outside click while the owner is positioning it.
                self.click_watcher.edit_mode = True
            else:
                # The drag is CARRIED by the watcher thread (it already owns the
                # mouse hook and a message loop), so a run without it can enter
                # edit mode and move nothing. Say so instead of leaving the owner
                # with a band that will not follow the pointer.
                warn('PANEL_EDIT_MODE_NO_DRAG the outside-click watcher is not '
                     'running (--no-click-outside), so the band cannot be '
                     'dragged; the tray item still toggles the mode')
            self.edit_moves = 0
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            log(f'PANEL_EDIT_MODE on=true reason={reason} surface={self.surface} '
                f'click_through=false noactivate=false '
                f'rect=({rect.left},{rect.top},{rect.right},{rect.bottom}) '
                'hint=drag_the_band')
        else:
            try:
                make_click_through(hwnd, True)
                set_ex_style(hwnd, add=WS_EX_NOACTIVATE)
            except Exception as exc:  # noqa: BLE001
                warn(f'PANEL_EDIT_MODE_STYLE_FAILED error={exc!r}')
            if self.click_watcher is not None:
                self.click_watcher.edit_mode = False
            # The rect the window ended on is the one to restore next launch.
            self.saved_geometry = self.geometry_snapshot()
            self.publish_panel_visibility('edit-off')
            log(f'PANEL_EDIT_MODE on=false reason={reason} '
                f'moves={self.edit_moves} '
                f'geometry={self.saved_geometry} click_through=true '
                'noactivate=true')
        return True

    def edit_drag_to(self, x, y, persist=False):
        """One drag sample, applied at a LOW frequency (see the watcher).

        Called from the outside-click watcher's MESSAGE LOOP, never from inside
        its hook procedure: a slow hook stalls the pointer system-wide. The move
        itself is a bare `SetWindowPos` with `SWP_NOSIZE` — no client-area work
        (a MOVE does not change the client area) and no `exec_js` — so the loop
        stays responsive. The heavier half (the client-area re-fit) is POSTED,
        and the file write happens only when the drag ENDS.
        """
        if not self.edit_mode:
            return False
        geometry = dict(self.geometry or {})
        width = int(geometry.get('width') or 0)
        height = int(geometry.get('height') or 0)
        if width <= 0 or height <= 0:
            return False
        grab = self.edit_grab or (0, 0)
        work = self.work_area()
        nx = max(work['x'], min(int(x) - int(grab[0]),
                               work['x'] + work['width'] - width))
        ny = max(work['y'], min(int(y) - int(grab[1]),
                               work['y'] + work['height'] - height))
        moved = (nx != int(geometry.get('x') or 0)
                 or ny != int(geometry.get('y') or 0))
        if moved:
            geometry['x'] = nx
            geometry['y'] = ny
            geometry['docked'] = 'edited'
            self.geometry = geometry
            scale = (self.display or {}).get('scaleFactor') or 1.0
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST,
                                int(nx * scale), int(ny * scale), 0, 0,
                                SWP_NOSIZE | SWP_NOACTIVATE)
            self.edit_moves += 1
        if persist:
            self.saved_geometry = self.geometry_snapshot()
            # Fire-and-forget: the client area is re-pinned once the drag ends,
            # never from inside the hook thread's message loop.
            self._post(lambda: self._fit_client_area(self._form()))
            self.publish_panel_visibility('edit-move')
            log(f'PANEL_EDIT_GEOMETRY_SAVED surface={self.surface_applied} '
                f'window={width}x{height}@({nx},{ny}) moves={self.edit_moves} '
                f'work={work["width"]}x{work["height"]}@({work["x"]},{work["y"]})')
        return moved

    def start_click_watcher(self) -> bool:
        """Arm the outside-click watcher (see `OutsideClickWatcher`)."""
        self.click_watcher = OutsideClickWatcher(self)
        ok = self.click_watcher.start()
        if not ok:
            warn('OUTSIDE_CLICK_UNAVAILABLE the low-level mouse watcher did not '
                 'install; the panel still opens and closes with Alt+C')
        return ok

    def run_outside_click_probe(self):
        """MEASUREMENT for the outside-click cure — the three cases, in order.

        The panel is made VISIBLE BUT NOT SEEN with `form.Opacity = 0`, which is
        the mechanism pywebview's OWN startup dance uses to map a window
        invisibly (`winforms.py:777-781`) — so `IsWindowVisible(hwnd)` is TRUE
        (the guard the decision actually reads) while nothing reaches the owner's
        screen. `--show` is NOT used.

        The three decisions are driven through the watcher thread's REAL message
        loop (`PostThreadMessageW`), so what is exercised is the decision
        function, the guards, the thread and `hide_panel` — everything except the
        OS delivering a physical click to the hook.
        """
        form = self._form()
        if form is None or self.click_watcher is None:
            log('OUTSIDE_CLICK_PROBE unavailable form_or_watcher=false')
            return
        try:
            form.Opacity = 0.0
        except Exception as exc:  # noqa: BLE001
            log(f'OUTSIDE_CLICK_PROBE opacity_failed={type(exc).__name__}: {exc}')
            return
        log('OUTSIDE_CLICK_PROBE begin opacity=0 visible_but_not_seen=true')
        rect = RECT()
        # (1) BEFORE ARMING — the two startup navigations.
        self.click_watcher._consider(0, 0, WM_LBUTTONDOWN, source='probe-startup')
        # (2) SHOWN, then a click OUTSIDE the rect.
        self.show_panel('probe-outside-click')
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        log(f'OUTSIDE_CLICK_PROBE shown visible={str(window_visible(self.hwnd)).lower()} '
            f'armed={str(self.click_watcher.armed).lower()} '
            f'rect=({rect.left},{rect.top},{rect.right},{rect.bottom})')
        outside_x, outside_y = rect.left - 20, rect.top + 10
        user32.PostThreadMessageW(self.click_watcher.thread_id, WM_PROBE_CLICK,
                                  _pack_point(outside_x, outside_y), 0)
        time.sleep(1.0)
        log(f'OUTSIDE_CLICK_PROBE after_outside_click '
            f'visible={str(window_visible(self.hwnd)).lower()}')
        # (3) SHOWN again, then a click INSIDE the rect.
        self.show_panel('probe-inside-click')
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        inside_x = (rect.left + rect.right) // 2
        inside_y = (rect.top + rect.bottom) // 2
        user32.PostThreadMessageW(self.click_watcher.thread_id, WM_PROBE_CLICK,
                                  _pack_point(inside_x, inside_y), 0)
        time.sleep(1.0)
        log(f'OUTSIDE_CLICK_PROBE after_inside_click '
            f'visible={str(window_visible(self.hwnd)).lower()}')
        self.request_exit(0, reason='probe-outside-click')

    def run_edit_mode_probe(self):
        """MEASUREMENT for the EDIT MODE — the whole path, window never seen.

        The panel is made VISIBLE BUT NOT SEEN with `form.Opacity = 0`, the very
        mechanism pywebview's own startup dance uses to map a window invisibly
        (`winforms.py:777-781`): `IsWindowVisible(hwnd)` is TRUE — the guard every
        decision here reads — while nothing reaches the owner's screen. `--show`
        is NOT used, and NO physical mouse is moved: the drag sample is posted
        through the watcher thread's REAL message loop (`PostThreadMessageW`),
        which is the exact path the hook procedure posts to, so what is exercised
        is the hook's own route minus the OS delivering a physical move.

        IT CANNOT HANG, and that is a rule earned here: a probe whose exception
        escapes a `threading.Timer` callback dies with a traceback on a stderr
        that `pythonw` does not have, leaving a HIDDEN SHELL ALIVE forever (the
        probe that launched it then kills it and reports an empty arm). So the
        steps are wrapped: any raise is written INTO THE LOG, and the exit is in a
        `finally`.
        """
        try:
            self._edit_mode_probe_steps()
        except Exception:  # noqa: BLE001
            import traceback
            log('PANEL_EDIT_PROBE FAILED '
                + traceback.format_exc().replace('\n', ' | '))
        finally:
            self.request_exit(0, reason='probe-edit-mode')

    def run_stats_probe(self):
        """MEASUREMENT for the STATS CHANNEL — read out of the panel's OWN DOM.

        `getStats`/`onStats` are the two members this shell owed the panel
        (`panel.js:1695-1724` is the level meter's consumer). A text presence check
        would pass on a member that is never ANSWERED, so this reads the
        CONSEQUENCE: the meter bars' inline `--meter-h` and `body.dataset.level`,
        after the panel's own 1000 ms poll has run against a worker that published
        `WORKER_STATS`. No window: `exec_js` needs no mapped surface, and `--show`
        is not passed.
        """
        # NOTE: no `//` comments inside this script. The whole thing is ONE line of
        # JS once concatenated, and a `//` comment swallows the rest of it — that
        # is exactly how this probe first returned `null` (measured).
        script = (
            "(() => ({"
            " level: document.body.dataset.level || null,"
            " bars: Array.from(document.querySelectorAll('.chrome__meter i'))"
            ".map((b) => b.style.getPropertyValue('--meter-h')),"
            " have: document.querySelectorAll('.chrome__meter i').length,"
            " emits: (window.__sotto_emit && window.__sotto_emit.counts) || null"
            "}))()")
        try:
            value = self.exec_js(script)
        except Exception as exc:  # noqa: BLE001
            value = {'probe_failed': repr(exc)}
        log('PANEL_STATS_PROBE ' + json.dumps(value, separators=(',', ':')))
        self.request_exit(0, reason='probe-stats')

    # -- the hover claim ----------------------------------------------------
    # The owner said, verbatim: *"passo o mouse encima > aparece mais botoes"*.
    # The stylesheet SUGGESTS an answer (`.strip-button:hover` changes only
    # `background`/`colour`, and `.stripbar` is `display:none` on the panel
    # surface), but a CSS read cannot answer the question the owner is really
    # asking: **if the reveal is CSS-only inside a small window, are the buttons
    # still inside the hit-test, or clipped out of it?** That needs the REAL
    # renderer, so this synthesises a hover with CDP `Input.dispatchMouseEvent`
    # — a real renderer hit-test with NO physical cursor moved (the owner's
    # mouse never leaves his desk) — and reads the outcome per surface.
    _HOVER_READ_JS = (
        "(() => {"
        " const bar = document.querySelector('.stripbar');"
        " const bs = bar ? getComputedStyle(bar) : null;"
        " const btns = Array.from(document.querySelectorAll('.strip-button'));"
        " return {"
        " surface: document.body.dataset.surface || null,"
        " inner: [innerWidth, innerHeight],"
        " stripbar_display: bs ? bs.display : null,"
        " stripbar_visibility: bs ? bs.visibility : null,"
        " stripbar_opacity: bs ? bs.opacity : null,"
        " buttons: btns.map((b) => {"
        "  const r = b.getBoundingClientRect();"
        "  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;"
        "  const laid = r.width > 0 && r.height > 0;"
        "  const inView = laid && cx >= 0 && cy >= 0"
        "   && cx <= innerWidth && cy <= innerHeight;"
        "  const hit = inView ? document.elementFromPoint(cx, cy) : null;"
        "  return {"
        "   label: (b.textContent || '').trim().slice(0, 16),"
        "   box: [Math.round(r.width), Math.round(r.height)],"
        "   centre: [Math.round(cx), Math.round(cy)],"
        "   display: getComputedStyle(b).display,"
        "   in_viewport: inView,"
        "   hit_is_button: !!(hit && (hit === b"
        "     || hit.closest('.strip-button') === b)),"
        "   hit: hit ? (hit.id || hit.tagName) : null,"
        "   hover: b.matches(':hover'),"
        "   pressed: b.getAttribute('aria-pressed') }"
        " }) }; })()")

    _HOVER_STATE_JS = (
        "Array.from(document.querySelectorAll('.strip-button'))"
        ".map((b) => b.matches(':hover'))")

    _PRESSED_JS = (
        "(() => { const b = document.querySelector('.strip-button');"
        " return b ? b.getAttribute('aria-pressed') : null; })()")

    def _cdp(self, method, params, timeout=5.0):
        """One CDP round trip, marshalled like `exec_js` (UI thread + Task wait).

        `CoreWebView2` is a UI-thread object, and the call returns a `Task`, so
        this is the same shape as `exec_js`: `Invoke` the call on the UI thread,
        complete on `ContinueWith`, wait on an `Event` OFF that thread.
        """
        from System import Action, Func, Object
        from System.Threading.Tasks import Task

        box = {}
        done = threading.Event()

        def _complete(task):
            try:
                if task.IsFaulted:
                    box['error'] = repr(task.Exception)
                else:
                    box['ok'] = True
            except Exception as exc:  # noqa: BLE001
                box['error'] = repr(exc)
            finally:
                done.set()

        def _run():
            self.webview2.Invoke(Func[Object](
                lambda: self.core.CallDevToolsProtocolMethodAsync(
                    method, json.dumps(params)).ContinueWith(
                    Action[Task](_complete))))

        try:
            self._ui(_run)
        except Exception as exc:  # noqa: BLE001
            box['error'] = repr(exc)
            done.set()
        if not done.wait(timeout):
            return {'error': 'cdp-timeout'}
        return box

    def _synthetic_move(self, x, y):
        return self._cdp('Input.dispatchMouseEvent', {
            'type': 'mouseMoved', 'x': int(x), 'y': int(y),
            'button': 'none', 'buttons': 0, 'pointerType': 'mouse'})

    def _synthetic_click(self, x, y):
        out = []
        for kind in ('mousePressed', 'mouseReleased'):
            out.append(self._cdp('Input.dispatchMouseEvent', {
                'type': kind, 'x': int(x), 'y': int(y),
                'button': 'left', 'buttons': 1, 'clickCount': 1,
                'pointerType': 'mouse'}))
            time.sleep(0.12)
        return out

    def run_hover_probe(self):
        """MEASUREMENT of the hover claim, in BOTH surfaces, window never seen.

        Same visibility contract as the edit-mode probe: `form.Opacity = 0`
        maps the window without showing it, `IsWindowVisible` is TRUE so the
        layout and the renderer hit-test are real, and nothing reaches the
        owner's screen. `--show` is NOT used and NO physical mouse is moved.

        IT CANNOT HANG, for the reason `run_edit_mode_probe` documents: the
        steps are wrapped and the exit is in a `finally`.
        """
        try:
            self._hover_probe_steps()
        except Exception:  # noqa: BLE001
            import traceback
            log('PANEL_HOVER_PROBE FAILED '
                + traceback.format_exc().replace('\n', ' | '))
        finally:
            self.request_exit(0, reason='probe-hover')

    def _hover_probe_steps(self):
        form = self._form()
        if form is None:
            log('PANEL_HOVER_PROBE unavailable form=false')
            return
        try:
            form.Opacity = 0.0
        except Exception as exc:  # noqa: BLE001
            log(f'PANEL_HOVER_PROBE opacity_failed={type(exc).__name__}: {exc}')
            return
        log('PANEL_HOVER_PROBE begin opacity=0 visible_but_not_seen=true '
            'cursor_moved=false')
        report = {}
        for surface in ('strip', 'panel'):
            try:
                self.set_panel_surface(surface, 'probe-hover')
            except Exception as exc:  # noqa: BLE001
                log(f'PANEL_HOVER_PROBE surface={surface} '
                    f'set_failed={type(exc).__name__}: {exc}')
                continue
            time.sleep(2.0)
            # Re-read the frame once more right before the per-button loop: on
            # the panel surface the window resize (`WINDOW_GEOMETRY`) and the
            # `display:none` of `.stripbar` land in SEPARATE frames, and a
            # snapshot taken between them reports a stale `innerWidth/Height`.
            settled = self.exec_js(
                "({inner:[innerWidth,innerHeight],"
                " d:(document.querySelector('.stripbar')?"
                "getComputedStyle(document.querySelector('.stripbar')).display:null)})")
            log(f'PANEL_HOVER_PROBE surface={surface} settled '
                + json.dumps(settled, separators=(',', ':')))
            before = self.exec_js(self._HOVER_READ_JS)
            report[surface] = {'before': before}
            log(f'PANEL_HOVER_PROBE surface={surface} phase=before '
                + json.dumps(before, separators=(',', ':')))
            buttons = (before or {}).get('buttons') or []
            # Park the synthetic pointer far from every button first, so the
            # FIRST per-button reading is a real "hover moved to this button"
            # rather than an accident of where the pointer already was.
            parked = self._synthetic_move(2, 2)
            time.sleep(0.3)
            per_button = []
            hoverable = [e for e in buttons if e.get('in_viewport')]
            if not hoverable:
                # Nothing is laid out inside the frame on this surface, so a
                # `:hover` reading here would be a pointer-position artifact,
                # not a reveal. Record it as UNREACHABLE rather than measure it.
                report[surface]['per_button'] = []
                report[surface]['hover'] = 'unreachable_no_button_in_viewport'
                log(f'PANEL_HOVER_PROBE surface={surface} phase=hover '
                    + json.dumps(report[surface]['hover']))
                buttons = hoverable
            else:
                for entry in hoverable:
                    centre = entry.get('centre') or [None, None]
                    x, y = centre[0], centre[1]
                    if x is None or y is None:
                        continue
                    moved = self._synthetic_move(x, y)
                    time.sleep(0.3)
                    state = self.exec_js(self._HOVER_STATE_JS)
                    per_button.append({
                        'label': entry.get('label'), 'at': [x, y],
                        'hovered_here': state,
                        'cdp': moved.get('error') or 'ok',
                    })
                report[surface]['per_button'] = per_button
                log(f'PANEL_HOVER_PROBE surface={surface} phase=hover '
                    + json.dumps(per_button, separators=(',', ':')))
            # ONE synthesised click on the FIRST laid-out button: the question
            # is not "does it toggle" but "is it REACHABLE at all".
            click_target = None
            for entry in buttons:
                if entry.get('in_viewport') and entry.get('box') != [0, 0]:
                    click_target = entry
                    break
            if click_target is not None:
                before_pressed = self.exec_js(self._PRESSED_JS)
                self._synthetic_move(2, 2)
                time.sleep(0.15)
                clicked = self._synthetic_click(click_target['centre'][0],
                                                click_target['centre'][1])
                time.sleep(0.6)
                after_pressed = self.exec_js(self._PRESSED_JS)
                report[surface]['click'] = {
                    'target': click_target.get('label'),
                    'hit_is_button': click_target.get('hit_is_button'),
                    'before': before_pressed, 'after': after_pressed,
                    'toggled': before_pressed != after_pressed,
                    'cdp': [c.get('error') or 'ok' for c in clicked],
                }
                log(f'PANEL_HOVER_PROBE surface={surface} phase=click '
                    + json.dumps(report[surface]['click'], separators=(',', ':')))
            else:
                report[surface]['click'] = {
                    'target': None, 'toggled': False,
                    'reason': 'no button is inside the viewport on this surface',
                }
                log(f'PANEL_HOVER_PROBE surface={surface} phase=click '
                    + json.dumps(report[surface]['click'], separators=(',', ':')))
            if parked.get('error'):
                log(f'PANEL_HOVER_PROBE surface={surface} park_cdp_error='
                    f'{parked["error"]}')
        log('PANEL_HOVER_PROBE SUMMARY ' + json.dumps(report, separators=(',', ':')))

    def _edit_mode_probe_steps(self):
        form = self._form()
        if form is None:
            log('PANEL_EDIT_PROBE unavailable form=false')
            return
        try:
            form.Opacity = 0.0
        except Exception as exc:  # noqa: BLE001
            log(f'PANEL_EDIT_PROBE opacity_failed={type(exc).__name__}: {exc}')
            return
        log('PANEL_EDIT_PROBE begin opacity=0 visible_but_not_seen=true')
        # (1) ENTER through the tray's OWN command id — the real entrance, and
        #     the same handler the menu's `WM_COMMAND` reaches.
        self.tray_command(ID_TRAY_EDIT)
        rect = RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        log(f'PANEL_EDIT_PROBE after_enter visible={str(window_visible(self.hwnd)).lower()} '
            f'edit_mode={str(self.edit_mode).lower()} '
            f'rect=({rect.left},{rect.top},{rect.right},{rect.bottom})')
        # (1b) AN OUTSIDE CLICK WHILE EDITING MUST NOT PUT THE BAND AWAY. Driven
        #      through the watcher's own decision function, which is the same one
        #      the hook calls — the first missed grab must not end the edit.
        if self.click_watcher is not None:
            closed = self.click_watcher._consider(5, 5, WM_LBUTTONDOWN,
                                                 source='probe-edit-outside')
            log('PANEL_EDIT_PROBE outside_click_while_editing closed='
                f'{str(bool(closed)).lower()} '
                f'visible={str(window_visible(self.hwnd)).lower()} '
                f'decision={(self.click_watcher.decisions[-1] or {}).get("decision")}')
        # (2) ONE DRAG SAMPLE. `edit_grab` is None because no physical
        #     button-down happened, so `edit_drag_to` moves the band's ORIGIN to
        #     the point — the decisions under test are the move, the clamp and the
        #     persist, not the grab offset (which only the hook sets).
        target_x, target_y = 700, 400
        if self.click_watcher is not None and self.click_watcher.thread_id:
            log(f'PANEL_EDIT_PROBE drag from=({rect.left},{rect.top}) '
                f'to=({target_x},{target_y})')
            user32.PostThreadMessageW(self.click_watcher.thread_id, WM_EDIT_DRAG,
                                      _pack_point(target_x, target_y), 1)
            time.sleep(1.0)
        else:
            log('PANEL_EDIT_PROBE drag_skipped watcher=false')
        # (2b) THE KEY, READ BACK OFF DISK FROM INSIDE THIS PROCESS. The file is
        #      shared with a possibly-running older shell that rewrites it every
        #      `interval_s`, so an OUTSIDE reader can lose the race; read here, a
        #      millisecond after the write, it cannot be raced away.
        try:
            with open(PANEL_VISIBILITY_PATH, encoding='utf-8') as fh:
                on_disk = json.load(fh)
            log('PANEL_EDIT_PROBE file_geometry='
                + json.dumps(on_disk.get('geometry'))
                + ' file_pid=' + str(on_disk.get('pid'))
                + ' file_schema=' + json.dumps(on_disk.get('schema'))
                + ' file_visible=' + json.dumps(on_disk.get('visible')))
        except Exception as exc:  # noqa: BLE001
            log(f'PANEL_EDIT_PROBE file_read_failed error={exc!r}')
        # (3) LEAVE through the same id, which is what persists and puts the two
        #     ex-styles back.
        self.tray_command(ID_TRAY_EDIT)
        log('PANEL_EDIT_PROBE after_leave edit_mode='
            f'{str(self.edit_mode).lower()} saved={json.dumps(self.saved_geometry)}')
        self.request_exit(0, reason='probe-edit-mode')

    def request_exit(self, code=0, reason='requested'):
        if self.exiting.is_set():
            return
        self.exiting.set()
        self._exit_code = code
        if self.click_watcher is not None:
            self.click_watcher.stop('exit')
        # The tray goes FIRST: `os._exit` at the end of this method would leave
        # the icon in the notification area as a ghost the owner cannot dismiss
        # (it would still be there, pointing at a dead window).
        if self.tray is not None:
            self.tray.stop('exit')
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
        # The stats totals travel with the exit line: the push is logged at most
        # once per `STATS_LOG_INTERVAL_S`, so a short run's log would otherwise
        # never show how many samples the feed actually carried. One line, at the
        # end, and it is the number `_main/_strip-stats-log-probe.py` reads to
        # prove the feed was DELIVERED while the log stayed small.
        log(f'SHELL_EXIT rc={code} reason={reason} '
            f'statsPushes={self.stats_pushes} statsReplies={self.stats_replies} '
            f'meterPushes={self.meter_pushes}')
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
                           ('probe_revive', '--probe-revive'),
                           ('exit_after', '--exit-after')):
            if getattr(args, flag, False):
                return f'measurement-flag({name})'
        return 'default'

    #: The reasons that may SPAWN a worker. Everything else is the decline half of
    #: `_worker_autostart_reason`, which NAMES why; this tuple is what makes the
    #: name binding. `hot-reload` is here because a file change must restart the
    #: worker it already had (the reload policy decides WHEN, not whether).
    #: `revive` is here because the PANEL asks for it (the owner's repair
    #: control, `revive_worker` below). Leaving it out is the failure this tuple
    #: exists to prevent and it is silent: `start_worker` logs
    #: `WORKER_AUTOSTART=declined` and the click would look like a no-op.
    START_REASONS = ('default', 'with-worker', 'hot-reload', 'revive')

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
            on_stats=self.on_worker_stats,
            on_meter=self.on_worker_meter,
        )
        log(f'WORKER_PATH {self.args.worker}')
        log(f'WORKER_COMMAND {self.args.python}')
        started = self.bridge.start(reason)
        log(f'WORKER_AUTOSTART={"started" if started else "declined"} '
            f'reason={reason}')
        if started:
            # The staleness query, answered at the moment the worker comes up:
            # from here on "am I running old code?" is one grep in the log.
            self.code_state_log(f'worker-started-{reason}')
        return started

    def on_worker_caption(self, text, meta):
        self.emit('caption', {'text': text, 'meta': meta})
        log(f'BRIDGE_CAPTION_SENT delivered=true text={json.dumps(text)}')
        # ── THE REAL BOUNDARY ────────────────────────────────────────────────
        # `final:true` is a line the WORKER CLOSED (`sotto_worker.py:2078`): at
        # that instant the in-flight text is committed, so a worker restart costs
        # a fraction of a second of audio and nothing else. That is the boundary
        # a held hot reload lands on — NOT "the worker stopped", which never
        # happens while there is audio (measured: 20 queued / 20 deferred / 0
        # applied). A partial (`final:false`) is NOT a boundary: the line is
        # still being rewritten and a restart would cut it mid-word.
        if meta.get('final') is True:
            self._reload_policy.boundary(closed=True, why='closed-line')

    def on_worker_status(self, text, kind, info):
        self.apply_panel_state(text, kind, info)
        # A status line is the OTHER boundary signal: an exit/`done`/`error`
        # closes the capture guard, so a reload held mid-stream can land here.
        # While the worker is capturing this is not a boundary at all, and the
        # policy says so instead of pretending (see `WorkerReloadPolicy`).
        self._reload_policy.boundary(why='status')

    def code_state_log(self, reason):
        """ONE LINE that answers "am I running old code?" before anyone asks.

        Emitted at startup and after every reload application. The shell's own
        half is the part nobody can reload: a Python process compiles its source
        once, so if `sotto_webview.py` changed under a live session the owner is
        running the old shell and the ONLY cure is a deliberate restart — which
        is why the hint travels with the fact.
        """
        state = self._reload_policy.state()
        worker, shell = state['worker'], state['shell']
        log(f'CODE_STATE reason={reason} '
            f'worker_disk={worker["disk"]} worker_loaded={worker["loaded"]} '
            f'worker_stale={str(worker["stale"]).lower()} '
            f'shell_disk={shell["disk"]} shell_loaded={shell["loaded"]} '
            f'shell_stale={str(shell["stale"]).lower()} '
            f'pending_ms={state["pending_ms"]} '
            f'restart_hint={json.dumps(shell["restart_hint"])}')
        return state

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

    # -- the panel's repair control ----------------------------------------

    def revive_worker(self, reason):
        """Kill the worker and start a new one, ALWAYS, because the owner asked.

        The owner's ruling, verbatim (2026-10-08): *"e o botao de error ou de idle
        sei que, ao clicar, deve fazer a pipeline inteira ser revivida, se nao
        tiver funcionando"*. So the panel's status — the footer AND the strip's
        own state, `panel.js` `wireRevive` — is a repair control, and this is what
        it drives: the child is terminated, every latch that could outlive it is
        dropped, and a fresh worker is spawned.

        DELIBERATELY UNCONDITIONAL. There is no health check here, because any
        heuristic can disagree with the man looking at the screen, and a repair
        button that second-guesses him is worse than no button. The cost is one
        model load (~2-8 s), which is why the element's own `title` states it
        BEFORE he clicks. `start_worker`'s own guard (`if self.bridge is not
        None`) is the only thing that can decline, and this clears `self.bridge`
        first, so it cannot.

        Runs on a THREAD: `WorkerBridge.stop` waits up to 5 s for the child, and
        doing that on the UI thread would freeze the panel at the exact moment
        the owner asked it to come back.
        """
        with self._revive_lock:
            if self._revive_thread is not None and self._revive_thread.is_alive():
                # A SECOND click while the first revive is in flight must NOT
                # stack a second respawn: two `stop()`s and two `start_worker`s
                # would leave one child unowned, or replace the bridge mid-load.
                log(f'REVIVE_REFUSED reason=already-in-flight '
                    f'request={json.dumps(str(reason))}')
                return False
            bridge = self.bridge
            old_pid = getattr(getattr(bridge, 'child', None), 'pid', None)
            log(f'REVIVE_REQUESTED reason={json.dumps(str(reason))} '
                f'had_bridge={str(bridge is not None).lower()} '
                f'pid={old_pid if old_pid is not None else "none"}')
            # The panel must never look frozen while the child is being killed.
            # This paint is the SHELL's, sent before the thread starts, and it
            # is `busy` on purpose: a repair in progress is not a new error.
            self.apply_panel_state('Restarting the pipeline…', 'busy')
            self._revive_thread = threading.Thread(
                target=self._do_revive, args=(reason,),
                name='sotto-revive', daemon=True)
            self._revive_thread.start()
            return True

    def _do_revive(self, reason):
        """The revive, off the UI thread. See `revive_worker` for why it exists."""
        try:
            # FIRST, before anything else: the hot-reload policy's pending
            # timers. A reload queued while the panel sat on an error would
            # otherwise fire into the middle of this revive and restart the
            # worker a second time — the exact stacking the caller's guard
            # refuses for clicks.
            try:
                self._reload_policy.stop()
            except Exception as exc:  # a stuck policy must not cancel a repair
                log(f'REVIVE_RELOAD_STOP_FAILED error={exc!r}')

            bridge = self.bridge
            if bridge is not None:
                # THE STICKY DEATH IS DROPPED HERE, AND ONLY HERE. A
                # `pending_error` survives the automatic restart until a CAPTION
                # proves recovery (AGENTS.md makes that law, and
                # `_main/panel-exit3-oracle.py` gates it) — which is right for a
                # death nobody asked about and wrong for a repair the owner just
                # ordered: without this the panel would keep painting the old
                # error word over the revive he asked for. Same for `no_audio`:
                # it is evidence about a child that is about to be terminated.
                held = getattr(bridge, 'pending_error', None)
                if held is not None:
                    log('REVIVE_CLEARED pending_error='
                        f'{json.dumps(str(held.get("text")))}')
                    bridge.pending_error = None
                if getattr(bridge, 'no_audio', False):
                    log(f'REVIVE_CLEARED no_audio=true '
                        f'because={json.dumps(bridge.no_audio_evidence)}')
                    bridge.no_audio = False
                    bridge.no_audio_evidence = None
                # `stop` is what cancels the old bridge's own restart timer, so
                # a death's scheduled respawn cannot land after this one.
                bridge.stop('revive')
            self.bridge = None
            started = self.start_worker('revive')
            new_bridge = self.bridge
            pid = getattr(getattr(new_bridge, 'child', None), 'pid', None)
            log(f'REVIVE_DONE started={str(started).lower()} '
                f'pid={pid if pid is not None else "none"} '
                f'spawns={getattr(new_bridge, "spawns", 0) if new_bridge else 0}')
        except Exception as exc:  # the owner must be told, not shown a freeze
            log(f'REVIVE_FAILED error={exc!r}')
            try:
                self.apply_panel_state(f'Could not restart the pipeline — {exc}',
                                       'error')
            except Exception:
                pass
        finally:
            with self._revive_lock:
                self._revive_thread = None

    def _do_worker_restart(self, files):
        """The one place a hot reload actually stops and restarts the worker."""
        if self.bridge is None:
            return False
        self.bridge.stop('hot-reload')
        self.bridge = None
        started = self.start_worker('hot-reload')
        log(f'HOT_RELOAD_WORKER_RESTART files={json.dumps(files)} '
            f'spawns={self.bridge.spawns if self.bridge else 0} '
            f'pid={getattr(getattr(self.bridge, "child", None), "pid", None)} '
            f'started={str(started).lower()}')
        # AFTER the reload: the NEW pid and the NEW hash, so "the code is current
        # now" is a fact in the log and not something to be inferred.
        self.code_state_log('worker-reloaded')
        return started

    def stop_hot_reload(self, reason):
        if self.hot_reload is not None:
            self.hot_reload.stop(reason)
        self._reload_policy.stop()

    # -- probes ------------------------------------------------------------
    def run_revive_probe(self):
        """PRESS the panel's status, in the real page, and read back what happened.

        See `--probe-revive`. `el.click()` dispatches a REAL `click` on the real
        element, so the listener `panel.js` installed is what runs: the panel
        paints its own sentence and posts `revive`. The shell's half then shows
        up in the log (`REVIVE_REQUESTED` / `REVIVE_DONE`), which is what
        `_main/revive-pipeline-oracle.py` reads. A probe that called
        `revive_worker` directly would prove none of the button.
        """
        js = """
(() => {
  try {
    const el = document.getElementById('status')
            || document.getElementById('strip-state');
    const strip = document.getElementById('strip-state');
    const wired = (e) => e ? [(e.getAttribute('role') || '-'),
                              (e.getAttribute('tabindex') || '-'),
                              (e.style.cursor || '-')].join('|') : 'absent';
    if (!el) return { ok: false, why: 'no-status-element' };
    const before = { footer: wired(document.getElementById('status')),
                     strip: wired(strip) };
    el.click();
    const text = document.getElementById('status-text');
    return {
      ok: true,
      pressed: el.id,
      wired: before,
      title: el.title,
      text: text ? text.textContent : '',
      offscreen: text ? text.classList.contains('status__text--offscreen') : null,
      statusError: el.classList.contains('status--error'),
      hasRevive: !!(window.sotto && typeof window.sotto.revive === 'function')
    };
  } catch (e) {
    // A PROBE THAT CANNOT SAY WHY IT FAILED IS A PROBE THAT LIES BY OMISSION.
    // Measured: without this, a throw inside the page's own click listener made
    // `evaluate_js` return nothing and the log said only `REVIVE_PROBE null`,
    // which reads as "the timer never fired" and sends the next reader after the
    // wrong half of the chain.
    return { ok: false, threw: String((e && e.message) || e),
             stack: String((e && e.stack) || '').split('\\n').slice(0, 4).join(' | ') };
  }
})()
"""
        result = self.exec_js(js)
        log('REVIVE_PROBE ' + json.dumps(result, separators=(',', ':')))

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


#: How often a held request is re-evaluated while the worker is capturing. The
#: old code armed NOTHING while capturing and relied on `boundary()`, which
#: itself returned while capturing — so "pending stays" meant "pending forever".
WORKER_RELOAD_DEFER_RECHECK_MS = 10000
#: The DEFERRED line is aggregated like the stats push: the first one, then at
#: most one per this interval, each carrying how long the wait has been.
WORKER_RELOAD_DEFER_LOG_MS = 30000


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

    ── CORRECTED 2026-10-08: THE BOUNDARY IS REAL, AND A DEFERRAL HAS A CEILING.
    ── Rule 2 said "applies at the next boundary" and the boundary was defined as
    `not is_capturing()` — which is false ONLY when the worker STOPS, and his
    worker never stops while there is audio. MEASURED on the owner's app: **20
    QUEUED / 20 DEFERRED / 0 APPLIED / 0 respawns** since the worker started at
    08:01:56, i.e. every edit to `worker/sotto_worker.py` was retained forever and
    he was running hours-old code — and reporting bugs that were already fixed.
    Two corrections, and they are the owner's own order ("hot reload ao maximo"):

      * THE BOUNDARY IS THE **CLOSED LINE**. Every caption the worker emits
        carries `final:true` when the WORKER CLOSED that line
        (`sotto_worker.py:2078`) — at that instant the in-flight text is already
        committed and there is nothing to lose but a fraction of a second of
        audio. `boundary(closed=True)` therefore passes the capture guard.
      * THE CEILING IS `WORKER_RELOAD_MAX_DEFER_MS`. A monologue that closes no
        line for that long gets the reload anyway, logged LOUDLY as FORCED with
        the reason. An unbounded deferral is a broken promise.

    The FLOOR still applies AFTER both: it bounds the RATE at which the model may
    be reloaded, and it is the owner's own rule. So the order is
    boundary -> ceiling -> floor, and every decision is one log line.

    It is a class, not three methods on the shell, for one reason: the guard is
    the thing that was missing, so it must be drivable from a probe against real
    files without booting WebView2 (see `--probe-reload`). `get_bridge` is the
    single seam — it returns the live `WorkerBridge` (or `None`), and the probe
    returns a stand-in exposing the SAME two fields the policy reads.
    """

    def __init__(self, log_fn, get_bridge, restart,
                 debounce_ms=WORKER_RELOAD_DEBOUNCE_MS,
                 min_interval_ms=WORKER_RELOAD_MIN_INTERVAL_MS,
                 max_defer_ms=WORKER_RELOAD_MAX_DEFER_MS,
                 defer_recheck_ms=WORKER_RELOAD_DEFER_RECHECK_MS):
        self.log = log_fn
        self.get_bridge = get_bridge
        self.restart = restart
        self.debounce_ms = debounce_ms
        self.min_interval_ms = min_interval_ms
        self.max_defer_ms = max_defer_ms
        self.defer_recheck_ms = defer_recheck_ms
        self.pending = None          # files of the newest unapplied request
        self.pending_since = 0.0
        #: Set when a CLOSED line arrives while a request is held: that is the
        #: real boundary, and it is consumed by the next `_fire`.
        self._boundary_hit = False
        self._defer_logged_at = 0.0
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
        self._boundary_hit = False
        self._defer_logged_at = 0.0
        self._arm(self.debounce_ms)
        self.log(f'HOT_RELOAD_WORKER_QUEUED files={json.dumps(self.pending)} '
                 f'debounce_ms={self.debounce_ms} '
                 f'min_interval_ms={self.min_interval_ms} '
                 f'max_defer_ms={self.max_defer_ms}')
        return True

    def boundary(self, closed=False, why='status'):
        """A worker event arrived: if a request is held, try to land it.

        Called from `on_worker_status` on every status line — including the exit
        line — so the deferred reload is not waiting on a timer that may never
        fire while the worker is down.

        `closed=True` is the REAL boundary (a `final:true` caption: the line is
        committed) and it is the only signal that passes the capture guard. A
        status line while capturing is not a boundary at all — the old code
        treated it as one and then returned, which is how a held reload became a
        held reload forever.
        """
        if self._stopped or self.pending is None:
            return
        br = self.get_bridge()
        if br is not None and br.is_capturing() and not closed:
            return                    # still mid-stream: keep holding it
        if closed:
            self._boundary_hit = True
            self.log(f'HOT_RELOAD_WORKER_BOUNDARY reason={why} '
                     f'files={json.dumps(self.pending)} '
                     f'waited_ms={int((time.monotonic() - self.pending_since) * 1000)}')
        self._arm(self.debounce_ms)

    def stop(self):
        self._stopped = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def state(self):
        """THE STALENESS QUERY — "am I running old code?", answerable, not found.

        Read by the log at startup and after every reload, and published in
        `_main/panel-state.json` under `shell.code`, so the question is a lookup
        instead of a bug report about a defect that was already fixed.
        """
        br = self.get_bridge()
        worker_path = getattr(br, 'worker_path', None)
        disk = file_sha256(worker_path) if worker_path else None
        loaded = getattr(br, 'loaded_sha256', None) if br is not None else None
        shell_disk = file_sha256(SHELL_PATH)
        pending_ms = None
        if self.pending is not None:
            pending_ms = int((time.monotonic() - self.pending_since) * 1000)
        return {
            'worker': {'path': worker_path, 'disk': disk, 'loaded': loaded,
                       'stale': bool(disk and loaded and disk != loaded)},
            'shell': {'path': SHELL_PATH, 'disk': shell_disk,
                      'loaded': SHELL_SHA256_AT_IMPORT,
                      'stale': bool(shell_disk
                                    and shell_disk != SHELL_SHA256_AT_IMPORT),
                      'reloadable': False,
                      'restart_hint': ('tray icon -> Quit Sotto, then run.cmd '
                                       '(a Python process reads its source once)')},
            'pending': self.pending,
            'pending_ms': pending_ms,
            'max_defer_ms': self.max_defer_ms,
        }

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
            self._boundary_hit = False
            self.log(f'HOT_RELOAD_WORKER_SKIPPED files={json.dumps(files)} '
                     'reason=no-worker-running')
            return

        waited_ms = int((time.monotonic() - self.pending_since) * 1000)
        capturing = bool(br.is_capturing())
        # ── THE THREE WAYS PAST THE CAPTURE GUARD, in the owner's order ────────
        #  1. a CLOSED LINE arrived — the in-flight text is committed, so a
        #     restart costs a fraction of a second of audio and nothing else;
        #  2. the CEILING elapsed — no boundary in `max_defer_ms`, so the reload
        #     happens ANYWAY and says so loudly (an unbounded deferral is a
        #     broken promise, and it is what left him on hours-old code);
        #  3. the worker is not capturing at all (the old, natural case).
        boundary = self._boundary_hit
        forced = capturing and not boundary and waited_ms >= self.max_defer_ms
        if capturing and not (boundary or forced):
            now = time.monotonic()
            if self._defer_logged_at <= 0.0 or (
                    (now - self._defer_logged_at) * 1000.0
                    >= WORKER_RELOAD_DEFER_LOG_MS):
                self._defer_logged_at = now
                state = self.state()
                self.log(f'HOT_RELOAD_WORKER_DEFERRED files={json.dumps(files)} '
                         f'reason=capturing waited_ms={waited_ms} '
                         f'max_defer_ms={self.max_defer_ms} '
                         f'code_is_stale={str(state["worker"]["stale"]).lower()} '
                         f'sha256_disk={state["worker"]["disk"]} '
                         f'sha256_at_spawn={state["worker"]["loaded"]} '
                         'applies_at=next-closed-line-or-ceiling')
            # BOUNDED: re-arm, so the ceiling is actually reached. The old code
            # returned without arming and waited for a `boundary()` that could
            # never come while capturing.
            self._arm(self.defer_recheck_ms)
            return

        if forced:
            state = self.state()
            self.log(f'HOT_RELOAD_WORKER_FORCED files={json.dumps(files)} '
                     f'reason=no-boundary-in-{self.max_defer_ms}ms '
                     f'waited_ms={waited_ms} '
                     f'code_is_stale={str(state["worker"]["stale"]).lower()} '
                     f'sha256_disk={state["worker"]["disk"]} '
                     f'sha256_at_spawn={state["worker"]["loaded"]} '
                     'cost=one-model-warm-up')
        elif boundary and capturing:
            self.log(f'HOT_RELOAD_WORKER_BOUNDARY_APPLIED '
                     f'files={json.dumps(files)} reason=closed-line '
                     f'waited_ms={waited_ms}')

        # A natural respawn already re-read the file. If it happened AFTER this
        # request was queued, the request is satisfied — do not restart again
        # (that double restart is itself churn).
        #
        # STRICTLY AFTER, and that `>` is load-bearing: MEASURED on this box,
        # `time.monotonic()` has a coarse tick (two consecutive calls compare
        # EQUAL, and still equal 100 us apart), so a spawn recorded just before
        # the request lands in the SAME tick as `pending_since`. With `>=` that
        # equality was read as "a respawn happened after the request" and the
        # reload was declared satisfied by a respawn that never happened — the
        # held reload silently dropped, i.e. the owner back on old code, which is
        # the very defect this policy is being repaired for. Found by arm 6 of
        # `--probe-reload` (the FLOOR arm), which expected a COOLDOWN and got
        # APPLIED_AT_BOUNDARY.
        spawned_at = float(getattr(br, 'spawned_at', 0.0) or 0.0)
        if br.child is None or spawned_at > self.pending_since:
            self.pending = None
            self._boundary_hit = False
            self.log(f'HOT_RELOAD_WORKER_APPLIED_AT_BOUNDARY '
                     f'files={json.dumps(files)} reason=respawn-reread-file '
                     f'pid={getattr(br.child, "pid", None)} '
                     f'sha256_at_spawn={getattr(br, "loaded_sha256", None)}')
            return

        if self._last_applied_at <= 0.0:
            # The floor counts from the INITIAL model load, not from the first
            # hot-reload request: the model has already paid one load.
            self._last_applied_at = spawned_at or time.monotonic()
        left_ms = self.min_interval_ms - int(
            (time.monotonic() - self._last_applied_at) * 1000)
        if left_ms > 0:
            # THE OUTER BOUND, and it is the owner's own rule: the model may not
            # leave load more often than once per `min_interval_ms`. It is the
            # last check, so a boundary or the ceiling does NOT override it — it
            # bounds the RATE, not whether the reload happens at all.
            state = self.state()
            self.log(f'HOT_RELOAD_WORKER_COOLDOWN files={json.dumps(files)} '
                     f'left_ms={left_ms} min_interval_ms={self.min_interval_ms} '
                     f'waited_ms={waited_ms} '
                     f'code_is_stale={str(state["worker"]["stale"]).lower()} '
                     f'sha256_disk={state["worker"]["disk"]} '
                     f'sha256_at_spawn={state["worker"]["loaded"]} '
                     'applies_when=floor-elapses')
            self._arm(left_ms)
            return

        self.pending = None
        self._boundary_hit = False
        self._last_applied_at = time.monotonic()
        self.log(f'HOT_RELOAD_WORKER_RESTART files={json.dumps(files)} '
                 f'after_idle_ms={self.min_interval_ms} waited_ms={waited_ms}')
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
                 on_caption=None, on_status=None, on_stats=None,
                 on_meter=None,
                 silence_ms=WORKER_SILENCE_MS,
                 backoff_base=1000, backoff_max=30000):
        self.command = command or default_python()
        self.worker_path = worker_path
        self.device = device if isinstance(device, str) and device.strip() else None
        self.capture_mode = capture_mode
        self.log = log
        self.on_caption = on_caption or (lambda text, meta: None)
        self.on_status = on_status or (lambda text, kind, info: None)
        #: The stats PUSH. Defaulted to a no-op like the other two, so a bridge
        #: built without it (a probe, the electron-era arm) is byte-identical.
        self.on_stats = on_stats or (lambda parsed: None)
        #: THE WAVE. Defaulted to a no-op like the other three, so a bridge built
        #: without it (a probe, the electron-era arm) behaves as before.
        self.on_meter = on_meter or (lambda sample: None)
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
        #: THE WAVE. `{"type":"meter","peak":<window peak>,"blocks":<blocks in
        #: the window>}`, published by the worker once per meter window (10 Hz by
        #: default). `peak` here is the peak OF THAT WINDOW — the stats line above
        #: carries the RUNNING MAXIMUM — so this is the value the panel's wave
        #: must be drawn from, and `stats()` prefers it while it is fresh.
        self.last_meter = None
        self.meters = 0
        self._meter_logged = 0
        self._meter_logged_at = 0.0
        #: The file hash of `worker_path` AS OF THE LAST SPAWN: what the running
        #: process loaded. Compared with the file on disk NOW to answer "is the
        #: owner running old code?" (see `WorkerReloadPolicy.state`).
        self.loaded_sha256 = None
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

        # WHAT THIS CHILD LOADED. Taken at the spawn, so the question "is the
        # file on disk still the file this process is running?" is a comparison
        # of two hashes rather than a bug report about an already-fixed defect.
        # Named `loaded_sha256` and not `sha256`: it is the file AS OF THE SPAWN,
        # which is the honest answer for a process we cannot introspect.
        self.loaded_sha256 = file_sha256(self.worker_path)

        self.log(f'BRIDGE_SPAWNED pid={self.child.pid} '
                 f'argv={json.dumps([self.command, self.worker_path])} '
                 f'worker_sha256={self.loaded_sha256} '
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
                            # The PUSH half of `getStats`/`onStats`: the panel's
                            # level meter is fed from the same parsed line the
                            # panel-state dump reads, so the two cannot disagree.
                            # GUARDED, and that is load-bearing: this runs inside
                            # the stderr reader's `try`, whose `except` logs
                            # BRIDGE_PUMP_DIED and ENDS THE STREAM — a raise here
                            # would take the worker's whole stderr channel (and
                            # the watchdog's heartbeat) down with it.
                            try:
                                self.on_stats(parsed)
                            except Exception as exc:  # noqa: BLE001
                                self.log(f'BRIDGE_STATS_CALLBACK_FAILED '
                                         f'error={exc!r}')
                            # The heartbeat is PROGRESS. Re-arming here is the
                            # whole cure: this stream used to `continue` before
                            # `_arm_silence`, so the one periodic signal the
                            # worker publishes never reached the watchdog.
                            pass  # NEG-ARM: the pre-fix shell never counted the heartbeat
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
            # A CAPTION IS ALSO THE ONLY PROOF ABOUT THE AUDIO, so it lifts the
            # no-audio verdict with the same force -- 2026-10-08.
            #
            # MEASURED, on the owner's own live run, before this block existed:
            # `_main/panel-state.json` published `"noAudio": true` with
            # `"captions": 21295` and the stale evidence
            # `device-rotated reason=flat peak=0.0 floor=0.002`, so
            # `_named_panel_state` named the panel `no-audio` while it was
            # transcribing. TWO defects in one stale flag:
            #   * the watchdog went blind. `_on_silence` returns early whenever
            #     `no_audio` is true, so after ONE flat window every later quiet
            #     is BENIGN for the LIFE OF THE CHILD -- a worker that wedged
            #     afterwards could never be caught, which is the opposite of what
            #     that branch was written for.
            #   * the panel was told "No audio to transcribe" over a working
            #     transcript (`_bridge_status` above), which is exactly the
            #     "nao ta ao vivo" the owner reported.
            # The evidence itself is why it must not latch: `device-rotated
            # reason=flat` is the worker's row for "THIS CANDIDATE carried nothing
            # I could transcribe, moving on" (`_no_audio_evidence` above), and the
            # ladder moves AWAY from that candidate -- so the sentence is about an
            # endpoint the tap is no longer on. A caption is measured on the
            # endpoint the tap IS on, and it outranks it.
            if self.no_audio:
                self.log(f'BRIDGE_NO_AUDIO_LIFTED reason=caption '
                         f'captions={self.captions} '
                         f'because={json.dumps(self.no_audio_evidence)}')
                self.no_audio = False
                self.no_audio_evidence = None
            self.on_caption(str(text), meta)
        elif kind == 'meter':
            self._meter(message, child)
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

    def _meter(self, message, child=None):
        """THE WAVE: one `{peak, blocks}` WINDOW from the worker's own meter.

        The shape is the worker's (`sotto_worker.py:3591`,
        `emit(type="meter", **level)` where `level` is `{"peak","blocks"}`), and
        it is deliberately the SAME two fields the stats payload carries: the
        panel has one consumer (`panel.js:1640` `pushLevel`) and must never be
        handed two different pictures of one measurement.

        WHY IT IS A BRANCH OF ITS OWN. Without it this line fell through to the
        unknown-kind `else`, which logs `BRIDGE_UNKNOWN type='meter'` PER SAMPLE
        — measured 35 B × 10 Hz ≈ **20.5 KB/min with no end**. The cure is NOT to
        stop publishing the meter (that exact mistake was made once already, on
        the worker side, where the meter default was set to zero to keep the log
        quiet): the LOG is what gets a budget, and the data keeps flowing.

        The `peak` here is the peak of THIS WINDOW; the `WORKER_STATS` line on
        stderr carries the RUNNING MAXIMUM of the whole run. A wave drawn from a
        running maximum is a staircase that only rises and then flattens — which
        is the defect the owner reported — so `SottoShell.stats()` prefers this
        sample while it is fresh.
        """
        self.meters += 1
        sample = {'at': time.monotonic()}
        for key in ('peak', 'blocks'):
            value = message.get(key)
            if value is None:
                continue
            try:
                sample[key] = float(value)
            except (TypeError, ValueError):
                self.malformed += 1
        if child is not None:
            sample['childPid'] = child.pid
        self.last_meter = sample
        now = sample['at']
        if self._meter_logged == 0 or (
                (now - self._meter_logged_at) >= METER_LOG_INTERVAL_S):
            self.log(f'BRIDGE_METER count={self.meters} '
                     f'in_window_s='
                     f'{round(0.0 if self._meter_logged == 0 else now - self._meter_logged_at, 1)} '
                     f'sample=' + json.dumps(
                         {k: v for k, v in sample.items() if k != 'at'},
                         separators=(',', ':')))
            self._meter_logged = self.meters
            self._meter_logged_at = now
        try:
            self.on_meter(sample)
        except Exception as exc:
            # A panel-side failure must not take the pump thread down with it:
            # that thread also carries the CAPTIONS.
            self.log(f'BRIDGE_METER_CALLBACK_FAILED error={exc!r}')

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
        if not self.capturing:
            # BOOT GRACE. Before `capture-started` the worker may be loading
            # the ~2 GB model (measured ~67 s on this box): its only stdout
            # lines are the warmup statuses and no heartbeat tick exists yet,
            # so the 30 s window cannot distinguish "wedged" from "loading".
            # While the child is younger than WORKER_BOOT_GRACE_MS the timer
            # re-arms instead of killing; past the grace a truly stuck loader
            # is still restarted.
            try:
                age_ms = (time.monotonic() - float(self.spawned_at or 0.0)) * 1000.0
            except (TypeError, ValueError):
                age_ms = float('inf')
            if age_ms < WORKER_BOOT_GRACE_MS:
                self.log(f'BRIDGE_SILENT_BOOT ms={self.silence_ms} '
                         f'pid={self.child.pid} age_ms={age_ms:.0f}')
                self._arm_silence()
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
        # ── THE ORPHAN-HOLDER FIX (2026-10-08): WAIT FOR THE OLD CHILD ──────
        # This used to `terminate()` and return, leaving the old process to
        # die (and release its WASAPI endpoint) whenever Windows got around
        # to it. The respawn timer was already counting, so the replacement
        # worker opened candidate 1 while its predecessor still held it and
        # died `0x8889000A AUDCLNT_E_DEVICE_IN_USE` — deaths climbing,
        # captions stuck, forever. Now it waits up to 5 s and kills, exactly
        # like `stop()`: when `_schedule_restart` runs, the endpoint is free
        # (or the holder is dead). Lock-free on purpose: this runs on the
        # silence-timer thread and `_spawn` callers may hold `self._lock`;
        # `threading.Lock` is not reentrant (see `_arm_silence`).
        child, self.child = self.child, None
        if child is not None:
            try:
                child.terminate()
            except Exception:
                pass
            try:
                child.wait(timeout=5)
            except Exception:
                try:
                    child.kill()
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
    parser.add_argument('--no-hot-reload', action='store_true',                        help='do not watch panel assets / worker sources')
    parser.add_argument('--probe-reload', action='store_true',
                        help='prove the worker hot-reload guard: touch the '
                             'worker file while a capture is open and print '
                             'the restart count (starts no window)')
    parser.add_argument('--log', default=None, help='mirror stdout here')
    #: The notification-area icon (the ONLY Quit, since the owner asked for the
    #: panel's button to go). It is ON by default; this turns it off for an arm
    #: that must not touch the owner's notification area at all.
    parser.add_argument('--no-tray', action='store_true',
                        help='start without the notification-area icon')
    #: Alt+C closes when the owner clicks outside. ON by default (the owner asked
    #: for it); this turns it off for an arm that must not install a mouse hook.
    parser.add_argument('--no-click-outside', action='store_true',
                        help='do not close the panel when clicking outside it')
    #: MEASUREMENT: the three outside-click cases with the panel visible but not
    #: seen (`form.Opacity = 0`), then exit. Never `--show`.
    parser.add_argument('--probe-outside-click', action='store_true',
                        help=argparse.SUPPRESS)
    #: MEASUREMENT: the edit mode end to end — enter through the tray's command
    #: id, one drag sample through the watcher's message loop, leave, persist —
    #: with the panel visible but not seen (`form.Opacity = 0`). Never `--show`,
    #: and no physical mouse input. SUPPRESS: it is a probe, not a user flag.
    parser.add_argument('--probe-edit-mode', action='store_true',
                        help=argparse.SUPPRESS)
    #: MEASUREMENT: the stats channel, read out of the panel's OWN DOM. Text
    #: presence proves nothing about a FEED, so this reads the consequence — the
    #: meter bars' `--meter-h` and `body.dataset.level` — after the panel's own
    #: 1000 ms poll has run against a worker that published `WORKER_STATS`.
    parser.add_argument('--probe-stats', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--probe-stats-wait', type=float, default=8.0,
                        help=argparse.SUPPRESS)
    #: MEASUREMENT of the OWNER'S HOVER CLAIM, in BOTH surfaces: *"passo o
    #: mouse encima > aparece mais botoes"*. A CSS read cannot answer whether
    #: the buttons are still INSIDE the hit-test once the reveal happens, so
    #: this synthesises a real renderer hover with CDP
    #: `Input.dispatchMouseEvent` (NO physical cursor is moved) and reads, per
    #: surface: each button's laid-out box, whether `:hover` actually fires,
    #: what `document.elementFromPoint` returns at the button's centre (hit-test
    #: OR clipping), and whether a synthesised click toggles `aria-pressed`.
    parser.add_argument('--probe-hover', action='store_true',
                        help=argparse.SUPPRESS)
    #: MEASUREMENT of the REPAIR CONTROL, from the DOM inwards. After SECONDS it
    #: asks the REAL page to press the REAL status element (`#status`.click()),
    #: so the whole chain is under measurement: the listener `panel.js`
    #: installed, `bridge.revive()`, `SottoHost.dispatch`, and the shell's
    #: kill-and-respawn. Calling `revive_worker` straight from Python would
    #: prove the shell half and NOTHING about the button the owner presses.
    #: Pass `--with-worker` with it: this is a measurement flag, so on its own it
    #: suppresses the worker (`measurement-flag(...)`) and there would be no
    #: child to kill — which is what `_main/revive-pipeline-oracle.py` does.
    parser.add_argument('--probe-revive', type=float, default=0.0,
                        metavar='SECONDS', help=argparse.SUPPRESS)
    #: The single-instance mutex name. The default is the shipped one; a private
    #: name is how a probe proves the lock is RELEASED on Quit without colliding
    #: with the owner's own running app (which holds the default).
    parser.add_argument('--mutex-name', default=DEFAULT_MUTEX_NAME,
                        help=argparse.SUPPRESS)
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
    (the "model loading toda hora" the owner saw). SIX arms, each able to print
    RED:

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
      4. CLOSED-LINE  a capture is open and STAYS open, and a CLOSED line
                  (`final:true`) arrives. Expect: the held reload APPLIES —
                  this is the boundary that exists while the owner is listening
                  (the old policy waited for the worker to STOP, which never
                  happens: 20 queued / 20 deferred / 0 applied, measured).
      5. CEILING  a capture is open, NO boundary ever arrives, and the ceiling is
                  short. Expect: the reload applies ANYWAY, and the log says
                  FORCED. A deferral with no ceiling is a broken promise.
      6. FLOOR    the ceiling has elapsed but the owner's 3-minute floor has not.
                  Expect: COOLDOWN — the floor bounds the RATE even when a
                  boundary or the ceiling says "now".

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

    def run_arm(debounce_ms, min_interval_ms, max_defer_ms=None,
                defer_recheck_ms=None):
        br = StandInBridge()

        def restart(files):
            br.spawns += 1
            br.spawned_at = time.monotonic()
            return True

        kwargs = {}
        if max_defer_ms is not None:
            kwargs['max_defer_ms'] = max_defer_ms
        if defer_recheck_ms is not None:
            kwargs['defer_recheck_ms'] = defer_recheck_ms
        policy = WorkerReloadPolicy(log_fn=print, get_bridge=lambda: br,
                                    restart=restart, debounce_ms=debounce_ms,
                                    min_interval_ms=min_interval_ms, **kwargs)
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

    # ── arm 4: THE CLOSED LINE — the boundary that really exists ────────────
    # A capture is open and STAYS open. `final:true` arrives (the worker closed
    # a line). The held reload must APPLY. This is the arm the old policy could
    # never pass: it waited for `is_capturing()` to go false, i.e. for the worker
    # to stop, and the owner's worker never stops while there is audio.
    br, policy, hr = run_arm(0, 0)
    if br is None:
        print('VERDICT arm=closed-line watchers=0 got=0-1')
        shutil.rmtree(root, ignore_errors=True)
        return 3
    br.capturing = True
    policy.request(['worker/sotto_worker.py'])
    time.sleep(0.2)
    during = br.spawns
    print(f'ARM closed-line restarts_before_boundary={during} expect=0')
    if during != 0:
        rc = 3
    policy.boundary(closed=True, why='closed-line')
    time.sleep(0.5)
    print(f'ARM closed-line restarts_after_boundary={br.spawns} expect=1 '
          f'still_capturing={br.capturing}')
    if br.spawns != 1 or not br.capturing:
        rc = 3
    policy.stop()
    hr.stop('arm4')

    # ── arm 5: THE CEILING — no boundary ever, and it applies anyway ────────
    br, policy, hr = run_arm(0, 0, max_defer_ms=400, defer_recheck_ms=100)
    if br is None:
        print('VERDICT arm=ceiling watchers=0 got=0-1')
        shutil.rmtree(root, ignore_errors=True)
        return 3
    br.capturing = True                   # and it NEVER goes false in this arm
    policy.request(['worker/sotto_worker.py'])
    time.sleep(1.4)                        # > the 400 ms ceiling, with rechecks
    print(f'ARM ceiling restarts={br.spawns} expect=1 still_capturing=true '
          f'max_defer_ms=400')
    if br.spawns != 1 or not br.capturing:
        rc = 3
    if policy.pending is not None:
        print(f'ARM ceiling pending_still_held={json.dumps(policy.pending)} '
              'expect=None')
        rc = 3
    policy.stop()
    hr.stop('arm5')

    # ── arm 6: THE FLOOR — the ceiling elapsed, the floor has not ───────────
    br, policy, hr = run_arm(0, 60000, max_defer_ms=200, defer_recheck_ms=100)
    if br is None:
        print('VERDICT arm=floor watchers=0 got=0-1')
        shutil.rmtree(root, ignore_errors=True)
        return 3
    br.capturing = True
    # The model has just loaded: the floor counts from the spawn.
    br.spawned_at = time.monotonic()
    policy.request(['worker/sotto_worker.py'])
    time.sleep(0.9)                        # > the ceiling, < the 60 s floor
    print(f'ARM floor restarts={br.spawns} expect=0 '
          f'pending_held={policy.pending is not None} '
          f'min_interval_ms=60000 max_defer_ms=200')
    if br.spawns != 0 or policy.pending is None:
        rc = 3
    policy.stop()
    hr.stop('arm6')

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
    _aumid_set = set_process_app_user_model_id()
    _aumid = process_app_user_model_id()
    log(f"APP_USER_MODEL_ID value={_aumid['value']} ok={str(_aumid['ok']).lower()} "
        f"hr={_aumid['hr']} set={str(_aumid_set['set']).lower()} "
        f"set_hr={_aumid_set['hr']} image={sys.executable}")

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
    # A PRIVATE mutex name is not the one the owner's app holds, so there is
    # nothing to collide with and taking it is safe even in a measurement run —
    # which is what makes "the Quit releases the lock" a measurement instead of
    # an argument from OS behaviour. With the DEFAULT name the excuse stands:
    # refusing a probe because the owner's app is up is what bricked the whole
    # instrument set once already.
    if args.mutex_name != DEFAULT_MUTEX_NAME:
        lock_excuse = None
    elif args.no_hotkey:
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
    elif not take_single_instance_lock(args.mutex_name):
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

    # THE TRAY. Last of the three, for the same reason as the others: it must not
    # be able to cost the app its start, and it is the only home the Quit has.
    if args.no_tray:
        log('TRAY_DISABLED reason=--no-tray')
    else:
        shell.start_tray()

    # The outside-click watcher, last for the same reason as the rest: a hook that
    # fails to install must not cost the app its start.
    if args.no_click_outside:
        log('OUTSIDE_CLICK_DISABLED reason=--no-click-outside')
    else:
        shell.start_click_watcher()

    if args.memory and args.memory_wait:
        threading.Timer(args.memory_wait, shell.run_memory).start()

    import webview
    # THE PANEL'S FACE, and the only channel pywebview actually offers:
    # `start(icon=...)` stores it in `_state['icon']`, which the WinForms backend
    # reads when it builds the form (`platforms/winforms.py:243-244`) — despite
    # its own docstring claiming the parameter is "Supported only on GTK/QT"
    # (`webview/__init__.py:205`). Without it the backend copies the icon out of
    # `sys.executable`, i.e. `pythonw.exe`, i.e. THE PYTHON ICON, which is the
    # owner's report. `apply_window_icon` (from `_on_before_show`) re-applies it
    # with an explicit `WM_SETICON`, ICON_SMALL2 included.
    webview.start(icon=SOTTO_ICON)
    return shell._exit_code


if __name__ == '__main__':
    sys.exit(main())