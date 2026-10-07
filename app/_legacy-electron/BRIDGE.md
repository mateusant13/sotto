# Sotto — the worker bridge

`worker-bridge.js` is the wire between the Electron panel (`main.js`) and the
Python ASR worker (`../../worker/sotto_worker.py`). It exists because the panel
said **"Waiting for audio"** forever: the shell and the worker were built
separately and nothing connected them, so no caption could ever arrive and the
panel had no way to say why.

Two rules shape everything below.

1. **The status must name the worker, never the audio.** Audio was never the
   missing thing on this host — see *Host facts* below. A panel that cannot
   distinguish "no worker" from "no audio" is a panel that lies.
2. **The receipt is the evidence.** Every state the bridge emits is printed to
   stdout with a `BRIDGE_*` token, and the panel acks it back as
   `STATUS_APPLIED` / `PLACEHOLDER_APPLIED`. Nothing here is provable by
   inspection alone.

## The STDOUT contract

The worker writes **one JSON object per line on stdout, flushed** and nothing
else there. The bridge line-splits the stream, `JSON.parse`s each line, and
dispatches on `type`:

```json
{"type":"caption","text":"...","start":<float>,"end":<float>,"model":"..."}
{"type":"status","state":"...","...":"..."}
```

| field    | type   | meaning                                                        |
| -------- | ------ | -------------------------------------------------------------- |
| `type`   | string | `"caption"` or `"status"`. Anything else is counted as malformed. |
| `text`   | string | caption text. Empty/whitespace-only is dropped, never rendered. |
| `start`  | float  | audio seconds, relative to the capture. Travels as caption `meta`. |
| `end`    | float  | audio seconds. Travels as caption `meta`.                      |
| `model`  | string | the model that produced the line.                               |
| `state`  | string | worker lifecycle state (see the table below).                    |

`start`/`end` are **audio** time, not wall clock. The panel renders the wall
clock itself (`panel.js` builds the timestamp from `new Date()`), so these two
fields travel as metadata and are not displayed.

### Parsing rules the bridge holds even when the worker misbehaves

- **Line-split, not chunk-split.** Chunks are accumulated in a buffer and split
  on `\n`; a caption split across two reads is delivered whole.
- **A last line with no trailing newline is still a line** (flushed on `close`).
- **A line that is not JSON is counted and skipped, never fatal.** A Python
  traceback on stdout must not end the caption stream. It is logged as
  `BRIDGE_MALFORMED` and counted in `bridge.malformed`.
- **CRLF is tolerated** (`\r` is stripped).

### States the live worker emits, and what the panel shows

Read from `sotto_worker.py` directly. Lookup is **separator-insensitive**: `-`,
`_` and space all normalise to `_`, because the worker emits `model-loading`
with a hyphen and an earlier draft of the map only had `model_loading`.

| worker `state`    | panel status line                                                | kind    |
| ----------------- | ---------------------------------------------------------------- | ------- |
| `boot`            | `Worker booting - starting onnxruntime...`                       | busy    |
| `model-loading`   | `Model loading...`                                               | busy    |
| `model-loaded`    | `Model loaded - opening the audio device...`                     | busy    |
| `device`          | `Capture not started - the worker has not opened the audio device` | busy   |
| `listening`       | `Listening - captions appear as speech is transcribed`           | live    |
| `done`            | `Worker finished its run - no further captions`                   | busy    |
| `error`           | `Worker reported an error`                                       | error   |

Also accepted, because they are the spellings other/future workers may use:
`loading_model`, `loading`, `ready`, `capture_starting`, `opening_device`,
`capturing`, `running`, `idle`, `stopping`, `stopped`. An **unknown state is
humanised, not dropped** (`Worker: Some New State`) — a dropped status is a
status the panel cannot distinguish from silence.

The worker's `error` statuses carry `stage` (`model-load`, `device`, `chunk`)
and `detail`; both are preserved in the emitted object's `state`/`info` and the
detail text appears in the `BRIDGE_STATUS` log line.

### Exit handling

- **Non-zero exit or a signal → `Worker died (code N) - <last stderr line>`.**
- **`code 0` → `Worker exited cleanly (code 0)`, not "died".** The live worker
  returns 0 after its `done` state; calling that a death would be a lie.
- **Either way the bridge schedules a restart**, because a session that ended
  is a session that should still be running.

## States the bridge owns (no worker line involved)

| receipt                                  | status line                                                          |
| ---------------------------------------- | -------------------------------------------------------------------- |
| `BRIDGE_START`                           | `Starting worker... (<file>)`                                        |
| `BRIDGE_WORKER_MISSING`                  | `Worker not found - <path> does not exist`                            |
| `BRIDGE_WORKER_SILENT`                   | `Worker silent - no output for 15s`                                  |
| `BRIDGE_WORKER_EXIT`                     | `Worker died (code N)` / `Worker exited cleanly (code 0)`             |
| `BRIDGE_RESTART`                         | `Worker not running - <reason>; restart N in X.Xs`                   |
| `BRIDGE_STOP`                            | `Worker stopped`                                                     |

The caption area's headline is replaced at the same time, via
`PLACEHOLDER_APPLIED`: `Starting the ASR worker`, `Worker not found`,
`Worker not running`, `Worker not answering`, `Worker stopped`, `Listening`,
`Capture not started`, `Worker finished`.

### Two invariants in `#status()`

- **Never empty.** `panel.js` `setStatus()` returns early on an empty string,
  so an empty status would leave the *previous* text on screen — which is how
  the stale message survived in the first place.
- **Never "waiting for audio" / "no audio".** Any text matching
  `FALSE_AUDIO_ABSENT` is rewritten to
  `Capture not started - the worker has not opened the audio device` and logged
  as `BRIDGE_STATUS_FALSIFIED`. This applies to text the *worker* invents too,
  not only to the bridge's own strings.

## Restart, backoff, and the first-output ceiling

- Backoff is exponential: `500ms`, doubling, clamped at `8000ms`
  (`{base, factor, max}`). The countdown is on screen, because "dead" with no
  hint that a retry is in flight reads as a hang.
- **One bridge, one child — and `start()` is idempotent on the BRIDGE, not on
  the child.** The old guard was `if (this.child) return false`, which reads
  "nothing is running" during the window where a worker has just died and this
  bridge's restart timer is still armed. Every `start()` inside that window was
  a second python, and the armed timer was a third. MEASURED 2026-10-06 (Alt+C
  spawned several unwanted processes; each worker is ~2.1 GB); the reproduction
  and both arms are in `docs/worker-single-instance-20261006.md`.

  The three accessors exist so a caller can make the same decision from outside:

  | accessor            | meaning                                                  |
  | ------------------- | -------------------------------------------------------- |
  | `hasPendingRestart` | a restart is ARMED inside this bridge (`timer !== null`)  |
  | `liveChildCount`    | 0 or 1 — one bridge owns at most one live child           |
  | `isActive`          | live child OR armed restart, and not stopped              |

  `#spawn()` refuses when `this.child !== null` (`BRIDGE_DOUBLE_SPAWN_REFUSED`)
  and cancels any timer that got it there: every legitimate respawn path
  (`close`, `error`, the silence ceiling, `stop`) clears `child` FIRST, so a
  non-null child on entry means the spawn would orphan a live worker.
  `#scheduleRestart()` cancels a still-armed timer before arming its own — a
  spawn that never starts emits BOTH `error` and `close`, which used to leave
  one invisible timer that `stop()` could not reach. `stop()` cancels both timers
  through the one `#cancelRestart()` path and logs what was armed.
- **`silenceMs` (default 15s) is a first-output ceiling, not a wall-clock one.**
  A worker that opens stdout and then says nothing is *silence*, and silence is
  the real failure mode here (a model import can wedge for minutes). The status
  names the failure as silence, then kills and restarts with backoff.
  The live worker emits `boot` and `model-loading` before any heavy work, so a
  legitimately slow model load never trips this.

## Host facts encoded in the defaults

These are **measured on this host**, not assumed (probe/tap_probe.py):

- System audio IS present: `Mapeador de som da Microsoft - Input` measures
  `CAPTURED peak=0.883270`; `VoiceMeeter Output` `peak=1.000000 rms=0.205321`.
- PortAudio's **blocking** read API does **not** work here — every device,
  including the Microsoft Sound Mapper, raises
  `PaErrorCode -9999 'Blocking API not supported yet'` (Windows WDM-KS -9999),
  and `sounddevice.Stream.read()` rejects its `timeout` kwarg. The working
  shape is a **callback** stream (`sd.InputStream(callback=cb)`), which is what
  `sotto_worker.py::LoopbackTap` uses.

So the bridge defaults to `SOTTO_CAPTURE_MODE=callback`, passed to the worker
as an **environment variable, never argv**. A worker built with `argparse`
dies on an argument it does not know but silently ignores an environment
variable it does not read: *a preference must never be able to kill the worker*.

`SOTTO_AUDIO_DEVICE` is exported **only when the owner asked for a device**
(`--device=`). It used to be exported unconditionally from
`DEFAULT_AUDIO_DEVICE`, which made the shell's guess outrank
`worker/config.json` on every run that asked for nothing — measured in the same
minute, one arm reading silence from the configured device while the other
produced captions from the forced one. `DEFAULT_AUDIO_DEVICE` survives as an
exported **hint**, not an override.

With no device named, `BRIDGE_START` logs `device=auto` and the worker resolves
the tap itself: it reads `config.json`, and if a candidate carries no signal for
`--tap-window` seconds (default 6) it rotates to the next one, logging one
`{"type":"status","state":"device-rotated",...}` line per switch. A run whose
every candidate is flat ends on `state=device-exhausted` — the panel's named
answer to "which device carries audio", instead of a name chosen before the run
started. The only flag the bridge appends is `--device`, and only when the owner
passed `--device=` explicitly.

The bridge maps both new states: `device-rotated` is `busy` (the worker is
doing the right thing), `device-exhausted` is `error` (no captions will arrive
until the routing changes).

## Flags (all optional, all additive)

| flag                | effect                                                          |
| ------------------- | ---------------------------------------------------------------- |
| *(none)*            | worker starts on the first Alt+C (show), not at launch          |
| `--with-worker`     | start the worker at launch as well                               |
| `--worker=<path>`   | worker entrypoint (default `../../worker/sotto_worker.py`)       |
| `--python=<path>`   | interpreter (default `python`)                                   |
| `--device=<name>`   | pin the input device; also forwarded as `--device <name>`         |
| `--capture=<mode>`  | capture mode, exported as `SOTTO_CAPTURE_MODE`                    |
| `--bridge-selftest` | run the bridge self-test and exit with its rc                    |

`--selftest` on its own is unchanged: no worker, no Python, no caption. Its
receipt is a frozen artefact for the shell lane, so the bridge does not
autostart there (`WORKER_AUTOSTART=skipped`).

A worker started with `--with-worker` speaks before the renderer has painted,
and an IPC message with no listener is discarded. On `sotto:renderer-ready` the
bridge's last status is **replayed** (`WORKER_STATUS_REPLAYED`), so the panel
opens onto the truth rather than the hardcoded placeholder.

## Self-test

```powershell
# the acceptance run - rc 0 = PASS, 3 = a step did not observe
electron.exe . --bridge-selftest

# the same steps with a local sink, no Electron
node bridge-selftest.js
```

It drives a **real child process** (`python -u -c`) that prints a canned JSONL
sequence, deliberately hostile: one line is not JSON at all. A stubbed stdout
would only test the parser against itself — chunking, mid-line death and
tracebacks are what actually break bridges, and none of them are stubbable.

| step                         | proves                                                             |
| ---------------------------- | ------------------------------------------------------------------ |
| `canned-jsonl-captions`      | every canned caption arrived, in order, with the exact text        |
| `canned-jsonl-statuses`      | model-loading / listening / idle each rendered for a human          |
| `malformed-line-survived`    | a non-JSON line is counted and the *next* caption still lands       |
| `no-empty-status`            | no status was ever empty (would leave the stale line in place)      |
| `no-false-waiting-for-audio` | no status ever claims audio is absent                              |
| `restart-after-crash`        | exit(3) → dead status → backoff → **second boot's caption lands**   |
| `missing-worker-status`      | a nonexistent path yields a status naming the worker, not audio    |
| `ipc-ack-captions-applied`   | (Electron only) the DOM acked each canned caption                  |

The restart step requires **two** boots: one boot would prove nothing about
restart. The missing-worker step uses a path outside `H:\sotto\worker`, because
that tree belongs to another lane.

### Single-instance self-test (separate file, on purpose)

`bridge-selftest.js` proves the bridge PARSES what a worker says. It does not
prove the bridge never spawns a second worker, which is a different failure with
a different instrument — the damage is PROCESSES, and `bridge.spawns` is a
self-report. So:

```powershell
# 9 steps; rc 0 = PASS, 3 = a step did not observe. Two arms, ~6 s.
node bridge-single-instance-selftest.js

# the same arms counted from OUTSIDE, by python command line. ~15 s.
node worker-proc-count-probe.js
```

Each worker appends its **own OS pid** to a file, and the verdict is the
MAXIMUM number of those pids alive at once, sampled every 5 ms — a second worker
that lived 40 ms and then died is still the bug the owner reported, and a
snapshot taken afterwards would call the run clean.

| arm                        | worker                        | what it is                                     |
| -------------------------- | ----------------------------- | ---------------------------------------------- |
| `hold` (control)           | sleeps, stays up               | the case the old child-only guard handled       |
| `die` (**the defect**)     | exits 7 immediately           | `child` null + restart timer ARMED = the window |

The control arm is labelled a control because it passes against the broken
bridge too. Proof that this gate can go red:

```powershell
# pre-fix bridge -> arm-die fails with maxLive=2 and the two pids named
New-Item -ItemType Directory -Force _single-instance | Out-Null   # generated; not committed
git show HEAD:app/electron/worker-bridge.js > _single-instance\worker-bridge-prefix.js
$env:SOTTO_BRIDGE_MODULE = "_single-instance\worker-bridge-prefix.js"
node bridge-single-instance-selftest.js   # rc 3
Remove-Item Env:SOTTO_BRIDGE_MODULE
```

`worker-proc-count-probe.js` counts `python.exe` processes whose command line
contains `worker_probe.py` — the probe's OWN script path, never the image name,
because other lanes run python on this box too. It spawns one PowerShell that
samples continuously; one WMI sample costs ~250 ms, longer than the whole defect
window, so per-sample process restarts would step straight over the thing being
measured.

### Running it while another instance is running

Electron's single-instance lock is shared per user-data dir. If another Sotto
panel is up, `--bridge-selftest` exits **3** with
`BRIDGE_SELFTEST FAIL reason=single-instance-lock-held` — it will not report a
PASS it did not earn. Run it with an isolated profile:

```powershell
electron.exe . --bridge-selftest --user-data-dir=$env:TEMP\sotto-bridge-selftest-profile
```

## Limits / not done

- The bridge does not import `ctranslate2` or `faster_whisper`, and never will
  in this path: `ctranslate2` hangs at import on this host and takes
  faster-whisper down with it. ASR imports belong to the worker lane.
- `requireExists: false` is a **test-only** seam (the self-test's `python -c`
  script is a JS string, not a file). Production always checks.
- Captions are not deduplicated, not persisted, and not timestamped from
  `start`/`end` — the panel owns rendering, this bridge owns transport.
- Backoff does not reset after a long healthy run; a worker that flaps hourly
  will still climb the backoff ladder.