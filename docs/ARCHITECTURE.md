# Sotto architecture

English map of the shipped runtime. Every `file:line` below was resolved against
`H:/sotto` on 2026-11-27 (branch `feat/speaker-attribution-20261019`). The older,
Portuguese account is `docs/spec/01-ARCHITECTURE.md`; the macro feature matrix is
`features/INDEX.md:8-24` and `features/features.json:8-9`. This document maps
processes, data paths, single owners, monoliths and gates. It does not change any
of them.

## Processes and ownership

**Launcher — `app/webview/run.cmd`.** The owner's double-click or logon startup
enters this batch file. It resolves `pythonw.exe` beside the interpreter
(`run.cmd:112-132`), refuses to fall back to a console-producing `python.exe`
(`run.cmd:59,128-132`), validates flags with a pre-flight that starts nothing
(`run.cmd:216`), starts the shell detached with `start ""` (`run.cmd:266,272`),
and waits on `--wait-ready` with a 30 s bound that `SOTTO_READY_BOUND` can
override (`run.cmd:255-256,276`). Because the shell runs under `pythonw.exe`, it
has no console or stdout: the receipt is the log file, not the terminal
(`run.cmd:51-59,272`).

**Shell — `app/webview/sotto_webview.py`, 28,318 lines measured in `H:/sotto`.**
The shell is the process the owner sees. It owns the WebView2 window; the window
is created at `sotto_webview.py:13830` / `:13853` and the panel page is loaded at
`:15308` / `:15624`, the worker's lifetime, the native caption window, the
history store and the on-disk UI settings. It treats `app/panel/` as read-only
contract (`sotto_webview.py:118-125`). `SottoShell` occupies
`sotto_webview.py:13600-23844` (10,245 lines measured); `ExternalCaptionWatcher`
is at `:3963-7607` (3,645 lines) and `WorkerBridge` at `:24645-26428` (1,784
lines).

**ASR worker — `worker/sotto_worker.py`, 10,229 lines measured.** One separate
process, launched by `WorkerBridge._spawn`, not by the batch file:
`sotto_webview.py:25235-25252` calls `subprocess.Popen([python, '-u',
worker_path] + extra_args, cwd=<worker dir>, stdin=DEVNULL, stdout=PIPE,
stderr=PIPE, env=<_child_env>, text=True, bufsize=1, ...)`. The exception is the
preload bridge, which gets a stdin pipe for the single preload activation line
(`:25237-25238,25265-25268`). `-u` and `PYTHONUNBUFFERED=1` are latency fixes,
not style: a buffered caption was measured stuck for 109 s in the pipe
(`:25229-25233`). The child's **whole** environment contract is decided in one
place, `WorkerBridge._child_env` (`:25064-25125`): `dict(os.environ)` plus
`PYTHONUNBUFFERED`, `SOTTO_CAPTURE_MODE`, `SOTTO_REDUX_WHEN_HIDDEN` and
`SOTTO_REDUX_LIVE` via `setdefault`, and `SOTTO_AUDIO_DEVICE` /
`SOTTO_TARGET_PID` only when asked. The thread budget is deliberately **not** an
environment key; it travels in argv (`:25081-25083`). The worker owns the audio
device and all ASR policy: `SottoShell.start_worker`
(`:19119-19166`) refuses spawn reasons outside `START_REASONS`, refuses when the
shell is exiting, and refuses when a bridge already exists — so a second child
cannot be born during shutdown. `stdin=DEVNULL` means there is no command
channel; control that is not "replace the child" lives in files or inside the
worker.

**Speaker sidecar — `worker/speaker_sidecar.py`, 1,992 lines measured.** The shell
owns its lifetime through `SpeakerSidecar` (`sotto_webview.py:24309-24356`),
resolving the script from `__file__` (`:26838-26849`) and starting it as a
separate process with `CREATE_NO_WINDOW` and `BELOW_NORMAL_PRIORITY_CLASS`
(`:24321-24330`). It exists apart from the worker because the worker already
loads 1.2-2 GB of ASR and the diarizer adds another 277 MB and about 1.4x
realtime CPU (`:24312-24319`). The sidecar publishes `_main/diar-live.json`
(`worker/speaker_sidecar.py:58`; the atomic writer is defined at `:209-221` and
called at `:542` and `:585`). The `--speakers-cheap` arm instead writes the
separate `_main/diar-watch.json`; the two paths and their required keys are
deliberately different (`sotto_webview.py:26852-26862`,
`worker/speaker_bridge.py:201-206`).

**Panel and helper windows.** `app/panel/panel.html` is the WebView2 page the
shell loads; `app/panel/` owns the DOM, themes and local history UI
(`features/INDEX.md:14,17`). The words on screen are **not** in the panel page:
`app/panel/panel.html:1220-1224,1327-1330` marks `caption.html` / `caption-float`
retired and names `NativeCaptionOverlay` (`app/webview/caption_overlay.py:564`,
2,180 lines measured) as the painter. `app/webview/youtube_cdp_source.py`
(2,548 lines), `app/webview/youtube_captions.py` (2,515 lines) and
`app/webview/youtube_clock.py` (216 lines) are in-process modules of the shell,
not processes.

## Data paths

**Audio → ASR → JSONL → shell.** The worker opens the loopback/microphone tap in
its own process (`worker/sotto_worker.py:3813-3849`, `mic_tap.open_stream` at
`:4954-5000`) and mixes the microphone into the loopback before the ASR callback
(`:8086-8089`). Every event leaves the worker through one function, `emit`
(`:1023-1055`): one JSON object, one line, flushed; captions first pass
`live_route.admit` (`:1046-1047`), so a batch-only line is marked
`history_only` instead of being painted. The only shell-side reader is
`WorkerBridge._consume` (`sotto_webview.py:25562-25639`): it case-normalises
`type`, accepts exactly `caption`, `meter` and `status`, counts anything else as
malformed, rejects an empty caption text (`:25580-25588`), stamps
`historySession` from the child that actually produced the line (`:25591-25596`)
and calls `on_caption` (`:25623`). A real caption is the only thing that clears
the death hold and the `no_audio` verdict (`:25599-25622`).

**Caption → paint and history.** `SottoShell.on_worker_caption`
(`:20847-20904`) is the single funnel. If a player owns the screen, the ASR line
is refused from both paint and history (`:20871-20882`). Otherwise the shell
pushes the text to the native window: `ov.set_text(new_text, new_prev, instant,
cue=cue, late_s=_late_s)` and `ov.show(True)` at `:19845-19849`, implemented by
`NativeCaptionOverlay.set_text` (`app/webview/caption_overlay.py:1757`). Only a
closed worker line is a transcript line: `history_append`
(`:16895-16913`) refuses `route=provisional-draft` and logs the refusal; the
file path is chosen by `_history_path_for` (`:16593`) under
`history/<YYYY-MM-DD>/<HH>.md` (`docs/spec/01-ARCHITECTURE.md:140`).

**YouTube CDP → cue → native overlay.** `CdpCaptionSource`
(`app/webview/youtube_cdp_source.py:1363`) is one thread, one connection, one
cheap `snapshot()` per poll; the shell attaches at boot and keeps one live
source (`sotto_webview.py:18857-18882`), so watcher and CDP do not race two
readers on the same tab (`:18857`). Track text comes from
`youtube_captions.fetch_track` (`app/webview/youtube_captions.py:1179`); the cue
covering an instant is selected by `cue_at` (`:495-524`); the shell looks up
that cue at `sotto_webview.py:6644-6649`, which feeds the same paint path as
`SottoShell.external_caption` at `:21050-21196`, including the `cue=` carried
into `NativeCaptionOverlay.set_text` (`:19847`, `caption_overlay.py:1757`). The
player's own captions suppress ASR paint while they exist
(`sotto_webview.py:20871-20882`).

**Files as the third channel.** With `stdin` absent, non-kill control travels on
disk: `_main/panel-visibility.json` (shell writer, worker reader, fails safe to
`visible=true`), `_main/panel-state.json`, `_main/caption-settings.json`,
`_main/hotkey-settings.json`, `_main/diar-live.json`, `_main/webview-run.log`,
`_main/webview-worker-tracebacks.log` and `history/` are catalogued with their
writers, readers and contracts in `docs/spec/01-ARCHITECTURE.md:128-142`.

## The single-owner rules

- **One capture reader.** `worker/capture_share.py:1-32` states the contract:
  the worker's already-mixed 16 kHz mono float32 block is published on one
  loopback TCP socket; **one client slot**, a second client gets `BUSY`
  (`:13,45,199,226`); the queue holds 32 blocks (`:48`) and the publisher is
  inert with no client. The worker constructs the publisher at
  `worker/sotto_worker.py:8092-8096`; the sidecar is the one client
  (`worker/speaker_sidecar.py:1828-1862`) and falls back to its own tap when the
  handshake fails. This is what keeps the number of device openers at one.
- **One pause rule.** `app/webview/youtube_clock.py:187-216` defines the pure
  predicate `pause_proven(clock_static, clock_moving, photo_fresh)`: the clock
  samples use a 0.30 s freshness window, an 8.0 s hold and a 0.15 s error budget
  (`:57,61,69`). The shell calls it at `sotto_webview.py:5835-5837` and clears
  the screen only on that verdict; a stale photo or a moving clock refuses the
  pause (`:5838-5879`). `_main/yt-pause-disagreement-oracle.py` owns this
  invariant in the battery (`_main/_audit-verify-all.cmd:1580-1585`).
- **One display selector.** The pure function `select_display_for_point`
  (`app/webview/display_geometry.py:159-276`) contains containment,
  nearest-monitor and primary fallback plus the work-area clamp. The Win32
  probe calls it at `app/webview/display_geometry.py:349`; the strip's final
  rect calls the same function at `sotto_webview.py:22279`. `primary_display`
  (`app/webview/display_geometry.py:148-156`) is only the docked panel's
  startup geometry. The paired oracle is `_main/multi-monitor-oracle.py`
  (`_main/_audit-verify-all.cmd:1788-1792`).
- **One thread budget, printed once.** The shell puts `--threads N` in argv,
  never in the pinned child environment (`sotto_webview.py:24597-24628,
  25081-25083`). The worker resolves it in `limit_threads`
  (`worker/sotto_worker.py:710-741`) and prints the effective value with
  `WORKER_THREADS threads=%d source=%d` at `:7405-7412`. The comment at `:705-709`
  records the measured failure this prevents: about 98 worker threads per
  process on a 20-logical-core host and an OpenMP-barrier deadlock between two
  concurrent workers. The paired gate is
  `_main/worker-thread-limit-oracle.py`, positive plus `--neg-arm`
  (`_main/_audit-verify-all.cmd:430-433`).

Speaker attribution is stamped on this same worker path: the sidecar writes
`_main/diar-live.json`, `worker/speaker_bridge.py:102-118` applies the payload to
caption lines through `speaker_id.attribute_from_payload`, and
`worker/speaker_id.py:260-285` builds the per-source key
`<base>/voice:speaker-N` (labels are assigned in first-appearance order at
`:163-178`). Stale or missing payloads leave `source` unchanged, so attribution
can go quiet without taking captions down (`speaker_bridge.py:121-162`,
`sotto_webview.py:24312-24319`).

## Monoliths and the split plan

Measured in `H:/sotto` on 2026-11-27: `app/webview/sotto_webview.py` has 28,318
lines, 202 top-level function/class definitions and 610 top-level AST nodes;
`worker/sotto_worker.py` 10,229 lines; `worker/speaker_sidecar.py` 1,992;
`app/webview/youtube_cdp_source.py` 2,548; `app/webview/youtube_captions.py`
2,515; `app/webview/caption_overlay.py` 2,180; `worker/capture_share.py` 444;
`worker/speaker_bridge.py` 263; `app/webview/youtube_clock.py` 216. The three
dominant classes are `SottoShell` (10,245 lines), `ExternalCaptionWatcher`
(3,645) and `WorkerBridge` (1,784), as listed above.

`revival/SPLIT-PLAN.md:1-8` is the measured split rail: it recorded 28,655 lines
and 623 top-level declarations on 2026-11-27, an `architecture_coherence` value
of 60 against a target of 90, and the rule that every cut must be proved by the
oracle of its own domain. The canonical shell now measures 28,318 lines and 610
top-level AST nodes — 337 lines and 13 top-level nodes less than the plan's
snapshot, because slice S1 has landed: the display symbols live in
`app/webview/display_geometry.py` (370 lines measured), and the shell's
selector call sites remain at `sotto_webview.py:22279`. The plan's slices
(`revival/SPLIT-PLAN.md:29-36`):

| slice | source range in the plan | destination | gate recorded in the plan |
|---|---|---|---|
| S1 | `:3406-3750` | `app/webview/display_geometry.py` (landed, 370 lines) | `_main/multi-monitor-oracle.py` (6 arms) |
| S2 | `:8825-9677` | `app/webview/hotkey_arms.py` | `_main/altc-gesture-oracle.py` (104), `_main/altc-soak-oracle.py` |
| S3 | `:10792-11697` | `app/webview/tray_surface.py` | `_main/tray-menu-oracle.py` (27), `_main/panel-language-oracle.js` |
| S4 | `:7952-8575` | `app/webview/window_chrome.py` | `_main/topmost-keepalive-oracle.py` (10), `_main/overlay-ink-oracle.py` |
| S5 | `:1842-2715` | `app/webview/process_lifecycle.py` | `_main/relaunch-ready-oracle.py` (8), `_main/console-window-audit.py` |
| S6 | `:12828-13754` | `app/webview/host_window.py` | `_main/panel-hidden-at-startup-oracle.py`, `_main/ui-watchdog-oracle.py` |
| S7 | `:4299-7943` | `app/webview/yt_clock.py`, `yt_read.py`, `yt_watch.py` | `_main/yt-capture-replay-oracle.py` (43 arms), `_main/yt-pause-disagreement-oracle.py`, `_main/yt-read-budget-oracle.py` |
| S8 | `:13936-24180` | `app/webview/shell_*.py` | the whole battery, one step per slice |

The plan's acceptance conditions are green oracle before and after the same
command, `undefined-names` green with the new module in the population,
`dead-unwired` PASS with no `new-unwired`, `_main/_gitattributes-verify.py` PASS
(`app/webview/*.py` is CRLF), and `codeintel health --budget-ms 10000` pasted
before and after (`revival/SPLIT-PLAN.md:38-45`). The shell cannot be imported as
a test: it runs code at import and had 623 top-level declarations at the plan's
snapshot (`revival/SPLIT-PLAN.md:18-21`).

## Where the gates live

`_main/_audit-verify-all.cmd` is the aggregated battery, not shipped runtime
(`features/INDEX.md:10`; `features/features.json:1356`). Its header
(`_main/_audit-verify-all.cmd:2-45`) defines four step kinds: `gate` (rc 0),
`control` (rc 0 **and** its own caught-bad-copy verdict), `skipped` (an
unrunnable arm is counted as skipped, never as a verified gate) and `expect-red`
(rc **1** with the violation printed; rc 0 or 2 is a failure). The file used to
exit 0 even with three red steps; it now aggregates every step's rc and exits
non-zero on any failure (`:14-27`). Measured in this tree: 615 `call :step`
lines and 444 `call :expectred` lines.

One invariant → one oracle, with a positive arm and, where the oracle supports
it, a deliberately-red `--neg-arm`:

| invariant | owner in code | battery pair |
|---|---|---|
| Child environment contract | `sotto_webview.py:25064-25125` | `_main/app-target-oracle.py` at `_main/_audit-verify-all.cmd:2964-2966` |
| Worker thread budget | `sotto_worker.py:710-741,7405-7412` | `_main/worker-thread-limit-oracle.py` at `:430-433` |
| YouTube pause verdict | `youtube_clock.py:187-216` | `_main/yt-pause-disagreement-oracle.py` at `:1580-1585` |
| Display choice / work-area clamp | `app/webview/display_geometry.py:159-276,349`, `sotto_webview.py:22279` | `_main/multi-monitor-oracle.py` at `:1788-1792` |
| Speaker watch payload | `speaker_sidecar.py:1281-1285`, `speaker_bridge.py:201-206` | `_main/speaker-watch-oracle.py` at `:2718-2724` |
| No undefined names after a move | whole shell + worker population | `_main/undefined-names-oracle.py` at `:2065-2070` |
| No newly unwired module | `panel.html`, shell, worker | `_main/dead-unwired-oracle.py` at `:1611-1616` |

Other oracles named by the split plan are `_main/battery-launch.py --verify`,
`_main/_gitattributes-verify.py` and the domain gates in the S1-S8 table above
(`revival/SPLIT-PLAN.md:14-17,29-36`). Per-step rc beacons and full logs are
written under `_main/_audit-verify/` (`_main/_audit-verify-all.cmd:5-9`). The
battery opens no window, audio device or app, so a green here never claims the
owner's live session was exercised; a live claim needs the owner's restart
(`revival/SPLIT-PLAN.md:20-23,45`).
