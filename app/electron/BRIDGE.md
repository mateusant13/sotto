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
- A restart is idempotent — `start()` on a live bridge is a no-op.
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

So the bridge defaults to `SOTTO_CAPTURE_MODE=callback` and
`SOTTO_AUDIO_DEVICE="Mapeador de som da Microsoft - Input"`, passed to the
worker as **environment variables, never argv**. A worker built with `argparse`
dies on an argument it does not know but silently ignores an environment
variable it does not read: *a preference must never be able to kill the worker*.
The only flag the bridge appends is `--device`, and only when the owner passed
`--device=` explicitly — the live worker already lists the measured-best tap
first in its own `preferred` order, so the default imposes nothing.

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