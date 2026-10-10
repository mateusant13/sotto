# P4 — ENGINE PROCESS: ONE PARENT, FOUR SUBSYSTEMS, RECONNECTABLE UI

Status: **SPEC — ready for implementation**
Lane: `feat/engine-process`
Depends on: `specs/07-engine-process.md` (stub), `src/engine/` (primitives only)

## 1. THE GAP

`src/engine/` contains exactly four files — `json.{h,cpp}`, `queue.{h,cpp}` — which are the
IPC primitives (LineWriter, LineReader, bounded Queue with drop-counter). There is **no Engine
process**. The capture binary (`src/capture/main.cpp`) runs standalone with `--stdin` for
one-shot JSON commands. The ASR runs file-fed (`python -m asr.transcribe --wav`). The index
is a Python module with no live ingestion path.

The ROADMAP P0 says: *"One Engine process that is the PARENT, UI as a reconnectable child —
so the UI dying can never stop recording."* That process does not exist.

## 2. WHAT THE ENGINE IS

A single long-running process that owns:

| subsystem | module | state |
|---|---|---|
| Capture | `src/capture/` (C++) | written, NVENC proven |
| ASR | `src/asr/` (Python) | written, parity proven |
| Index | `src/index/` (Python) | written, search proven |
| Highlights | `src/index/highlights.py` | written, oracle passes |

The Engine is the **parent**. The UI (Tauri shell or `src/ui/hud-shell.py`) is a **child**
that can die and reconnect without stopping capture/ASR/index.

## 3. IPC CONTRACT — JSON Lines over stdin/stdout

The proven substrate is `worker/sotto_worker.py:374-377` (`emit()`) and
`worker/sotto_webview.py:5964-5975` (consumer with watchdog). The Engine uses the same
pattern: one JSON object per line, `\n`-terminated, on stdin and stdout.

### 3.1 Commands (UI → Engine, on Engine's stdin)

```json
{"cmd": "cut"}
```
Trigger an instant-replay cut. The Engine writes the clip from the ring buffer.

```json
{"cmd": "status"}
```
Return current state: capture active, encoder initialised, ring fill, ASR loaded, index size.

```json
{"cmd": "search", "query": "onde eu falei de comprar GPU?"}
```
Run a 3-channel RRF search over the index. Returns hits with provenance chips.

```json
{"cmd": "attach"}
```
Register a new UI child. The Engine starts streaming events to this child's stdin.

```json
{"cmd": "detach"}
```
Unregister the UI child. Capture/ASR/index continue.

### 3.2 Events (Engine → UI, on Engine's stdout)

```json
{"evt": "capture_started", "ts": 1699999999.123}
{"evt": "clip_written", "path": "clip-20261008-190000.mp4", "duration_s": 30.0}
{"evt": "asr_partial", "text": "...", "ts_ms": 12345}
{"evt": "asr_final", "text": "...", "ts_ms": 12345, "seg_id": 42}
{"evt": "index_updated", "seg_id": 42, "channels": ["speech", "ocr", "visual"]}
{"evt": "health", "ring_fill_pct": 45.2, "dropped": 0, "asr_rss_mb": 890}
```

## 4. LIFECYCLE

### 4.1 Startup

1. Engine process starts (C++ or Python — decision below).
2. Capture subsystem initialises NVENC. If NVENC fails, Engine exits with code 3 (LAW 6).
3. ASR loads the int8 ONNX model. If ASR fails, Engine continues without ASR (degraded mode).
4. Index opens/creates the SQLite file.
5. Engine enters the main loop: read stdin commands, run capture frame, run ASR on audio
   segments, run index updates.

### 4.2 UI attach/detach

- UI connects by spawning the Engine as a child process (or connecting to a named pipe).
- On `attach`, the Engine starts streaming events to the UI.
- On `detach` (or UI process exit detected via `EPIPE`/`SIGPIPE`), the Engine stops streaming
  but continues capture/ASR/index.
- On UI reconnect, the Engine replays the last N events (bounded, e.g. 100) so the UI
  can catch up.

### 4.3 Shutdown

- On `SIGINT` or `{"cmd": "shutdown"}`, the Engine:
  1. Stops accepting new commands.
  2. Flushes the ring buffer to a final clip.
  3. Flushes ASR segments to the index.
  4. Closes the SQLite file cleanly.
  5. Exits with code 0.

## 5. LANGUAGE DECISION

The Engine can be C++ or Python. The trade-off:

| | C++ | Python |
|---|---|---|
| Capture | already C++ | needs subprocess or FFI |
| ASR | needs ONNX Runtime C++ API | already Python |
| Index | needs SQLite C++ | already Python |
| IPC | already C++ (`src/engine/`) | needs `json` + `subprocess` |

**Recommendation: Python Engine with C++ capture subprocess.** The ASR and index are Python.
The capture binary already has `--stdin` for JSON commands. The Engine spawns
`aireplay-capture --run --stdin` as a child, communicates via JSON Lines, and manages the
ASR and index in-process. This avoids rewriting ASR/index in C++ and reuses the proven
capture binary.

## 6. ACCEPTANCE — tests that can go RED

### ARM-A: Engine starts, capture fails, Engine exits 3

```
Engine with NVENC unavailable → exit code 3, stderr names LAW 6.
```

### ARM-B: Engine starts, UI attaches, capture runs, clip is written

```
Engine + UI child → {"cmd":"cut"} → clip file exists, ffprobe reports h264 video stream.
```

### ARM-C: UI dies, capture continues

```
Engine + UI child → UI process killed → Engine still running → {"cmd":"status"} → capture active.
```

### ARM-D: ASR degraded mode

```
Engine + ASR model missing → Engine starts, ASR disabled, capture continues, index receives no speech channel.
```

### ARM-E: Index search returns provenance chips

```
Engine + index with data → {"cmd":"search","query":"test"} → hits with channels:["speech","ocr","visual"].
```

## 7. FILES TO CREATE

| file | what |
|---|---|
| `src/engine/engine.py` | The Engine process: main loop, IPC, lifecycle |
| `src/engine/protocol.py` | JSON Lines validator (both colours) |
| `src/engine/test_engine.py` | ARM-A through ARM-E |

## 8. PROVENANCE

Every constant in this spec carries a `file:line` or a MEASURED/READ/UNKNOWN tag.
The IPC contract is derived from `worker/sotto_worker.py:374-377` (READ, not measured here).
The lifecycle is derived from `ROADMAP.md` P0 (READ).
The language decision is a recommendation, not a measurement.
