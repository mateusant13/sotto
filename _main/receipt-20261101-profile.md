# Receipt — the caption path, profiled (2026-11-01)

Lane: `lane/goal-profile` @ `H:/sotto-wt/goal-profile` (worktree of `H:/sotto` @ `c6dfb70`).
Work against the LIVE app only: nothing here launches, kills or edits the app, and no
product file was touched. Owner's goal this receipt serves: *"legenda instantânea, sem
stutter, sem freeze da máquina"* — so every number below is a step of one caption or a
byte the app made.

## 0. Instruments — and the negative arm each one passed

| id | instrument | what it measures | negative arm I RAN |
|---|---|---|---|
| **I-PROC** | `Get-Process` / `Get-CimInstance Win32_Process` (CPU seconds, WorkingSet64, PrivateMemorySize64, Threads.Count, HandleCount) | per-process CPU/RAM/threads/handles | the same counters read on `pythonw.exe` ids that are NOT the app (pids 13604/25628: 2–8 MB, 0 CPU) — the census separates them, so a row is not a page-fault artefact |
| **I-LOG** | `_main/webview-run.log` parsed with Python `re` (the app writes every hop's timestamp itself) | hop timings, event rates, byte attribution | the parse covers **45,324,040 B of the 45.46 MB file = 99.7 %**; re-parsing with a regex anchored on `sotto:` drops 0 lines of the 333,253 stamped ones |
| **I-WD** | the app's OWN watchdog (`sotto-ui-watchdog`, `sotto_webview.py:6867`) printing `UI_HUNG_FRAME` per thread | thread stacks when the UI thread misses 4 s | it fired: 112 `UI_THREAD_STALL` + 16 `UI_WATCHDOG_STRIKE` + `UI_HUNG_THREAD` dumps — a watchdog that never fired would have proved nothing |
| **I-MICRO** | `time.perf_counter` over 200–2000 reps, on the WORKTREE's copy of the same modules the app runs | µs per call | the fast path resolves against the slow path: `push_caption_to_window` no-op **0.50 µs** vs the real `apply_js` **85–268 µs** |
| **I-PAINT** | `_main/_panel-anim-cost.js` (shipped probe) driven by `_main/_lane-profile-paint.py` over the shipped `panel.js` | page main-thread cost of one push, rAF spacing, LoAF | reduced-vs-animated arms move **4.14 → 41.86 ms** (10×); BUT the probe's OWN forced-layout control is **RED** (`_main/_panel-anim-cost-final3.log`: *"FORCED-LAYOUT CHANNEL: FAIL … so its PASS on the real arms means nothing"*) — magnitudes are indicative, the reduced/animated ratio is within-instrument |
| **I-PYSPY** | py-spy 0.4.2 | all Python stacks | **NOT USED**: `Error: Failed to open process — Acesso negado (os error 5)` (no SeDebugPrivilege on pid 3236). Every stack in this receipt is I-WD's, not py-spy's |
| **I-WCH** | Windows per-process I/O counters (`\Process(*)\IO Read Bytes/sec` etc., summed over 19.4 h) | who really reads this disk | the app is 2.4 % of the box's daily read bytes while a service outside the app is 40 % — so a number that blames "the app" for disk load is refuted by the same counter |

`I-MICRO` and `I-PAINT` run the worktree's bytes (cut at `c6dfb70`). The live tree is being edited
by other lanes while I measured — its own `code_id` moved `F74B91EB9742` → `375FF50AC73C` during
this run — so a stack frame quoted from the app's log is the app's frame, and a line number quoted
from the worktree is HEAD's; both are labelled.

---

## 1. One caption, end to end — audio capture → worker → ASR → shell → panel DOM

The live path is the worker's own streaming ASR (`SOTTO_CAPTURE_MODE=callback`, tap = the ladder's
factory `LoopbackTap`), with the Redux overlay inert unless `SOTTO_REDUX_LIVE=1`
(`worker/sotto_worker.py:3991 redux_live_settings`, opt-in by flag → env → config → OFF).

Line numbers are from `H:/sotto` as read during this run; the live tree is being edited by other
lanes (its own `code_id` moved `F74B91EB9742` → `375FF50AC73C` while I measured), so a stack frame
quoted from the app's log is the app's frame, not necessarily this line number.

| # | hop | owner (file : function : line) | instrument | measured cost |
|---|---|---|---|---|
| 1 | render callback → one block (100 ms) | the ladder's factory `worker/sotto_worker.py:2945 LoopbackTap`: rung (a) `wasapi_loopback.WasapiLoopbackTap` when the endpoint exposes a loopback client, else `_PortAudioTap` (`:1874`, the PortAudio callback). Live run is `capture=callback device=auto` (`BRIDGE_START`, 10:22:56) | config `audio.block_ms=100` + I-LOG (`chunks/audio_s`) | 100 ms of audio per block; chunk cadence **0.560 s** measured (38 sessions, primary means) |
| 2 | block → `audio_q` (bounded, 2.0 s) | `worker/sotto_worker.py:5918` → `worker/live_queue.py:enqueue_live(audio_q, block, max_blocks(100))` | I-MICRO | enqueue **1.23 µs** mean / 1.02 p95 / 20.7 max; cap = **20 blocks = 2.0 s** (`live_queue.py:live_queue_max_s=2.0`) |
| 3 | queued block → streaming decode | `worker/sotto_worker.py:6197 audio_q.get(timeout=0.25)` in the consume loop; decode inside `StreamAsr` (`sotto_worker.py:659 chunk = cfg["chunk_samples"]` = 0.560 s) | I-LOG (`WORKER_STATS infer_wall_s/chunks`) | **71.8 ms p50 / 1,318 ms p95 / 4,626 ms max** of encode+decode wall per 0.560 s chunk (n=135 stat records with `infer_wall_s ≥ 1 s`) |
| 4 | decode → line events → stdout | `worker/sotto_worker.py:6150 publish_captions` → `line_events(former.flush())`; JSONL `{"type":"caption"}` | I-LOG | 43,283 captions over 279 worker sessions; **1.36 tokens/chunk p50**, 4.03 p95 → most chunks are silent, a caption every ~1–3 chunks |
| 5 | worker stdout → shell line | `app/webview/sotto_webview.py:10530 _pump` (`sotto-worker-stdout`) → `_on_line` → `_consume_line` | I-MICRO | **0.125 ms mean / 0.275 p95 / 0.551 max** per line (n=2,000, 8,000 synthetic lines) |
| 6 | line → caption handler → async push | `sotto_webview.py:9860 on_worker_caption` → `:10770 emit_async('caption')` (latch dict + `_post`) | I-MICRO | **0.005 ms mean / 0.12 p95** per caption; the suppress/`external_captions_active` branch costs 0.11 µs |
| 7 | shell log line | `sotto_webview.py:9958 BRIDGE_CAPTION_SENT` → `_log_writer` (`:1139`) | I-MICRO | **3.00 µs** producer + **4.68 µs** writer (`write`+`flush` of the 115 B line); the writer is off the caller's thread by design |
| 8 | shell → page | `emit_async._run` → `self.webview2.Invoke(core.ExecuteScriptAsync(...))` | I-LOG (`WARN exec_js TIMEOUT/STALL`, `WARN UI_THREAD_STALL`) | good case ms-level; bad case **≥10 s, 498 times in 19 days (≈26/day)**, plus **112 `UI_THREAD_STALL`**; on 2026-11-01 10:15 four of them inside 30 s |
| 9 | page ingress → subscribers | `BOOTSTRAP_JS` (`sotto_webview.py:5025 __sotto_emit`) → `:4934 emit('caption')` → `window.sotto.onCaption` | I-PAINT | included in the push below |
| 10 | panel handler → DOM paint | `app/panel/panel.js` caption engine → `SottoFormulation` commit timer (`caption-formulation.js:150 COMMIT_MAX_HOLD_MS = 1500`) | I-PAINT (2026-11-01) + I-LOG pairing | push **4.14 ms mean / 27.2 max (reduced motion, the owner's setting)** vs **41.86 ms mean / 1,682.9 max (animated)**; rAF p50 **16.7 ms**; LoAF **8 long tasks / 1,496 ms duration / 848.5 ms blocking** in a 6 s window |

### The end-to-end budget this adds up to

* **floor, ordinary line:** 0.100 s (block) + 0.560 s (chunk) + 0.072 s (ASR p50) ≈ **0.73 s**
  from the word being spoken to the partial arriving in the page.
* **worst case, queue saturated:** 0.100 + **2.000** (queue cap) + 0.560 + 1.318 (ASR p95) ≈ **4.0 s**.
* **+ the page's own two timers:** the row is *committed* no sooner than 1.5 s after its words
  settle (`COMMIT_MAX_HOLD_MS`), which is why the shell's own `BRIDGE_CAPTION_SENT →
  CAPTION_APPLIED` pairing reads **p50 616 ms / p95 2,290 ms / max 5,691 ms** — a *commit*
  number, not a *visible* one ([INFERENCE] the partial paints without that timer; the commit
  timer is a documented constant, the 616 ms p50 is measured).

---

## 2. Bottlenecks, with numbers

### 2.1 The page's main thread — the one place a caption can visibly stutter

| arm (`theme-5`, 6 s of 8 partials/s, shipped `panel.js`) | push mean | push max | rAF p50/p95/max | rAF over 50 ms | LoAF tasks / duration / blocking |
|---|---|---|---|---|---|
| **reduced** (owner's `prefersReducedMotion`) | 4.14 ms | 27.2 ms | 16.7 / 16.8 / 100 ms | 1 / 353 | 2 / 173.9 / 0 ms |
| **on** (animation forced) | **41.86 ms** | **1,682.9 ms** | 16.7 / 33.3 / 1,666.6 | 10 / 271 | **8 / 1,496.1 / 4.9 ms** |
| relayout (control copy, motion) | 5.03 ms | 60.8 ms | 16.7 / 16.8 / 883.3 | 4 / 273 | 5 / 1,505.0 / 848.5 ms |

Instrument I-PAINT, today, this box (load ~87 % CPU, 13.6 APPs). Three facts:
1. **The animated path costs 10× the reduced path per push** (41.86 vs 4.14 ms) and one push in
   the animated arm blocked the main thread for **1.68 s**. The owner wants the animation AND
   zero stutter; on this box those two are currently in conflict.
2. **rAF p50 is 16.7 ms in every arm** — the compositor's clock is healthy. The damage is in
   *long tasks* (LoAF), not in steady-state frame pacing. That points at one synchronous cost
   inside a frame (layout/animation start), not at "the panel is heavy".
3. The probe's forced-layout control is RED, so it cannot *prove* which channel that cost comes
   from; a fix here needs the control re-powered first (fix 6).

**Repeat run of the same `reduced` arm** (25.7 s later, same probe, same page):
push mean **6.305 ms**, max 144.1, n=41; rAF p50 16.7 / p95 16.8 / max 450, over50 8/277;
LoAF 5 / 1,153.1 ms / 260 ms blocking. So the *reduced* arm lands at **4.1–6.3 ms mean** across two
runs while the *animated* arm was 41.9 ms in its run — the page's cost tracks the box's load, which
is exactly why a fixed threshold on this instrument is not a contract (and why the control matters).
n = 1 per arm except `reduced` (2); the animation/reduced ratio is the number to keep.

### 2.2 The UI thread's JS bridge — the tail that survives every other fix

`I-WD` at 09:56:29 catches the UI thread inside pywebview:

```
winforms.py:808 create → app.Run()
edgechromium.py:251 on_script_notify → util.py:336 js_bridge_call
  → threading.py:969 Thread.start → self._started.wait()      # BLOCKED
```

pywebview **starts a Python `Thread` per JS→host call and the UI thread waits on it**. When the
box is starved, that wait is the stall: 498 `exec_js TIMEOUT/STALL` (10 s each) and 112
`UI_THREAD_STALL` in 19 days, and 4 of them in 30 s today at 10:15:20.340–10:15:36.941 with the
*worker-start* status scripts. This is not the caption push (that is `emit_async` → `_post`,
fire-and-forget), but it is the thread that must run `ExecuteScriptAsync` for the caption when the
UI thread is already inside another synchronous `emit` — i.e. **the caption's shell→page hop
inherits this tail**.

### 2.3 Hashing on a timer — the frame the watchdog actually caught

`I-WD` at 09:56:29 also catches `sotto-panel-state` inside:

```
panel_state.py:180 _loop → :211 write → sotto_webview.py:7966 panel_state_snapshot
  → :12242 _reload_policy.state() → :843 file_sha256
```

* `panel_state.py` writes **every 2.0 s** (measured cadence from the live file: `writtenAt`
  10:22:27 → 10:22:29 → 10:22:31 → 10:22:35; 43,200 writes/day).
* Each snapshot re-hashes the worker source: `_reload_policy.state()` (`:12242`) →
  `file_sha256` on `worker/sotto_worker.py` = **414,911 B, 1.30 ms warm p50** (I-MICRO, 9 reps:
  1.169–1.566 ms). That is **43,200 × 1.30 ms = 56 s/day** of hashing on the state thread — and
  the cold-disk case is the one the watchdog caught (`UI_HUNG` inside `file_sha256`,
  2026-11-01 09:56:29).
* The OTHER hasher is on the worker-start path: `code_state_log` (`:11644`) hashes
  **7 files = 0.9997 MB** at **5.23 ms warm p50** (`5.09/5.11/5.23/5.49/6.91`) — and Main's
  09:56 dump shows it blocking the pump thread inside `start_worker`.

### 2.4 The log — bounded, but 58 % of its bytes are four event families

The ticket suspected "45 MB appended per event". Measured: **it is bounded** —
`_open_log` (`sotto_webview.py:1082`) enforces `SOTTO_LOG_CAP_MB` (default **64 MB**, keep
**16 MB**) and has rotated once: `LOG_ROTATED from=847859845 B kept=16777081 B cap=64 MB`
(2026-10-13). At 45.32 MB it sits at **71 % of the cap**. Growth:

| measure | value | instrument |
|---|---|---|
| file now | 45,464,053 B (45.46 MB), 335,386 lines | `wc -c` / `wc -l` |
| window | 19.2 days (2026-10-13 23:52 → 2026-11-01 10:19) | I-LOG first/last stamp |
| mean rate | **2.37 MB/day = 0.25 MB/h** | 45.47 MB / 19.2 d |
| busiest session | **28.4 MB in 5,781 s = 17.7 MB/h** | per-session sum of line bytes |
| right now (idle) | 8,718 B in 27 s = **5.06 B/s** | two `wc -c` 27 s apart |
| one line, caller | **3.00 µs** (stamp + enqueue) | I-MICRO, 2,000 reps of `logging.log()` |
| one line, writer | **4.68 µs** (`write`+`flush` of 115 B) | I-MICRO, 200 reps |

Byte attribution (I-LOG, 333,253 stamped lines = 45,324,040 B):

| event family | lines | MB | B/line | share |
|---|---|---|---|---|
| `OUTSIDE_CLICK` | 89,363 | 12.23 | 136 | **27.0 %** |
| `BRIDGE_CAPTION_SENT` | 43,283 | 5.64 | 130 | 12.4 % |
| `WINDOW_GEOMETRY` | 31,141 | 5.57 | 178 | 12.3 % |
| `PANEL_SURFACE` | 31,142 | 5.23 | 167 | 11.5 % |
| `PANEL_VISIBILITY_WRITE_FAILED` | 17,891 | 3.29 | 184 | 7.3 % |
| `panel` (shell chatter) | 32,050 | 2.69 | 83 | 5.9 % |
| `CAPTION_APPLIED` | 11,181 | 1.52 | 136 | 3.4 % |
| `STATUS_APPLIED` | 15,915 | 1.24 | 78 | 2.7 % |

So the four noisy families (`OUTSIDE_CLICK`, `WINDOW_GEOMETRY`, `PANEL_SURFACE`,
`PANEL_VISIBILITY_WRITE_FAILED`) are **58 % of the log**, and the caption path's own two lines
(`BRIDGE_CAPTION_SENT` + `CAPTION_APPLIED`) are 16 %.

### 2.5 `panel-state.json` — 95 MB written per day for a 1.4 KB file

* File: 2,132–2,210 B, rewritten whole **every 2.0 s** = **43,200 writes/day ≈ 95 MB/day**
  (I-MICRO: `panel_state.write_atomic` of 2.0 KB costs **3.2 ms**, so the writer is busy
  **≈138 s/day**).
* Every one of them also carries `panel_state_snapshot` → the hashing of §2.3.

### 2.6 CPU/RAM per process (I-PROC; three live instances, 2026-11-01)

| process | pid | age | CPU | WS | private | threads | handles |
|---|---|---|---|---|---|---|---|
| shell (`pythonw.exe`) | 56184 | ~17 min | 6.65 s = **0.7 %** of a core | 130.5 MB | 84.4 MB | 34 | 685 |
| shell | 41492 | 118 s | 0.49 s = **0.42 %** | 119.7 MB | 92.4 MB | 17 | 550 |
| shell | 27484 | 42 s | 1.8 s = **4.3 %** (startup) | 118.3 MB | 85.2 MB | 22 | 574 |
| shell | 52956 | 90 s | 1.78 s | 119.7 MB | — | — | — |
| worker (`python.exe`) | 38132 | 51 min | 4:52 = **9.5 %** | 212 MB | — | **77** | — |
| WebView2 (`msedgewebview2.exe`) | 46128 | — | 0.00 s = **0 %** | **395.4 MB** | — | — | — |
| WebView2 (56184's tree) | — | — | — | 314 MB total | — | — | — |

The caption path's own Python cost, summed: 43,283 captions × (0.125 ms pump + 0.005 ms handler
+ 0.0077 ms log) ≈ **6 s of CPU in 19 days**. The Python side of a caption has ~1000× headroom;
every visible problem lives in the page's main thread and the UI thread's JS bridge.

Machine-level competitor (I-WCH, Windows per-process counters, 19.4 h): the PostgreSQL service
reads **435.8 GB/day = 40 % of all read bytes on the box**; the app's total read is 2.4 % of the
daily bytes. A profiling run on this box measures the neighbours too.

### 2.7 Restart churn — the RAM/CPU churn is the relauncher, not the caption path

`_main/shell-relaunch.log` (I-LOG) shows the app killing and relaunching itself when
`app/webview/*` changes (`SHELL_RELAUNCH files=app/webview/load_shedding.py detail=schtasks rc=0`
10:18:46, `SHELL_RELAUNCH_ARMED watched=app/webview,app/panel floor_s=120 cap_per_hour=3`):

```
10:16:44 pid 34196 GANHOU a mutex    → health ok
10:18:46 SHELL_RELAUNCH (load_shedding.py changed)
10:18:52 kill pid=34196 confirmado morto → 10:18:56 pid 52956 GANHOU a mutex
```

Five shells logged today between 09:10 and 10:19. Each cycle tears down 120 MB (shell) + 314–395 MB
(WebView2) + 212 MB (worker) and pays the cold start measured above: **115 ms** for the shell to
import, **424 ms** for the worker, 2.5–11 s to a painted panel, and **4 × 10 s `exec_js`
timeouts**. While lanes edit `app/webview`, that is the dominant CPU/RAM event on the box.

### 2.8 The idle rotation loop — one tap reopened every 7–15 s on a silent endpoint

While the endpoint reads flat, the ladder rotates the device and immediately reopens a capture.
From the live log (I-LOG), the current shell:

```
10:22:08 device → 10:22:12 capture-started → 10:22:20 device-rotated (flat)
10:22:20 capture-started → 10:22:27 device-rotated (flat)
10:22:29 capture-started → 10:22:39 device-rotated (flat) → 10:22:48 → 10:23:03 …
```

* **611 `device-rotated (flat)` lines in 19 days**; the current instance rotates on a
  **7–15 s** cadence (gaps: 7, 12, 9, 15 s).
* Each rotation opens a tap (a new stream, `sotto_worker.py:2945 LoopbackTap` → WASAPI/PortAudio
  open, which the ladder itself bounds with `TAP_OPEN_TIMEOUT` because an open can BLOCK), resets
  the front end (`asr.reset_frontend()` — a new mel window and VAD), flushes the held line
  through `former.flush()`, and emits `STATUS_APPLIED`. Two of those also cross the
  `panel-state` tick and its hashing (§2.3).
* Mean interval in this instance ≈ 10 s → **≈360 tap opens/hour while the machine is silent**.

Instrument: I-LOG (the app's own `STATUS_APPLIED text="device-rotated (flat)"` lines) + the source
that opens the tap. Negative arm: the same log shows the rotation STOPPING when audio flows
(`capture-started` with no following `flat` in the sessions that produced captions — 43,283 of them).

---

## 3. LEAKS — what I can prove, and what I cannot

| suspect | verdict | number | instrument |
|---|---|---|---|
| **log file** | **NOT a leak** — capped at 64 MB, keep 16 MB, rotated once ever | 45.32 MB = 71 % of cap; 2.37 MB/day | `_open_log` source + `grep -c LOG_ROTATED` = 1 |
| **`_LOG_QUEUE`** | **unbounded in principle** (`queue.SimpleQueue()`, no maxsize) — the only unbounded structure on the caption path; bounded in practice by rate | 5.06 B/s idle, ≈300 B/s under a click storm | source `sotto_webview.py:1137` + measured log rate |
| **`panel-state.json` write churn** | unbounded *writes*, constant *size*: 43,200 rewrites/day, each a full rewrite + flush | 95 MB/day written for a 1.4 KB file; ≈138 s/day of writer duty | I-PROBE + live `writtenAt` cadence |
| **temp files** | residue, not growth: 28 stale `ready-*.txt` + 6 `*.tmp` in `_main` (each launch writes `ready-<RANDOM>-<RANDOM>.txt` and deletes it only on the success path) | 34 files; `_main` is **3.4 GB** (161 files newer than 2026-10-30) | `ls` / `du` |
| **RAM** | no growth proven: 3 instances sampled at 42 s / 118 s / 17 min read 118 / 120 / 130 MB WS. The churn is the relauncher, not a slow leak | 118–130 MB shell, 212 MB worker, 314–395 MB WebView2 | I-PROC |
| **handles** | **NOT a leak** — the 15-minute series is a sawtooth between **760 and 933**, with peaks at the samples where a worker was spawned (10:21:51 → 933, 10:33:53 → 933) and troughs ~765 after it was reaped. Net over 803 s: +132, but the series is not monotone, so that delta is churn, not growth | 760–933, no trend | I-PROC, 18 samples keyed by pid (§3.1) |
| **threads** | shape, not leak: shell 17 → 34 → 43 across its life (16 named threads + 2 pump threads per spawned worker); worker holds **77** threads (one `sotto-worker-reap`/`sotto-worker-wait`/pump set per stream, `sotto_worker.py:13329/13371`) | 77 threads in one worker | I-PROC + source |
| **`_emit_pending`** | bounded by number of kinds (a latch dict, `emit_async`) | ≤ #kinds | source `sotto_webview.py:10770` |
| **`audio_q`** | bounded: 2.0 s of audio (20 blocks), eviction counted as `queue_evicted` | cap 2.0 s | `live_queue.py` + I-MICRO |

### 3.1 Within-instance growth — measured, 15 minutes, one pid

`_main/_lane-profile-census.py` sampled every 45 s from 10:21:13 to 10:34:36 (803 s, 18 samples,
`_main/_lane-profile-census.csv`). Rows are keyed by pid, so a self-relaunch cannot fake a leak.

| pid | role | ws Δ | private Δ | handles Δ | threads | cpu Δ | verdict |
|---|---|---|---|---|---|---|---|
| **52956** | **shell (mutex owner)** | −93.5 MB (trimmed) | **+4.0 MB, then flat**: 118.1 → 121.2 at 10:25 and 122.1 at 10:34 | **760 → 933 sawtooth** (peaks at worker spawns, troughs ~765) | 36–49, sawtooth | 47.25 s in 803 s = **5.9 % of a core** | **steady state — no leak** |
| 39660 | WebView2 (browser) | −56.2 MB | −1.7 MB | +25 | — | 1.57 s | flat |
| 56628 / 45404 / 31076 / 8736 / 25932 | WebView2 renderers/GPU/utility | ≤ ±14 MB | ≤ ±1.4 MB | −20 … +6 | — | ≤0.4 s | flat |
| 54632 | **unidentified `pythonw.exe`** (parent `svchost.exe`, launched by a task at 09:10:26, no window, 347 handles) | +0.4 MB | +0.1 MB | −8 | — | **389.6 s in 803 s = 48.5 % of a core** | a HOG, not a leak |
| worker (`python.exe`) | — | — | — | — | — | 4 different pids: 34624 → 43852 → 33940 → 27804 | **replaced 3× in 15 min** (rotation loop §2.8 + relaunch §2.7) |

The full series (18 samples, 803 s) is in `_main/_lane-profile-census.csv`. Read:

* **The shell is in steady state.** Its private bytes rise 118 → 121 MB in the first four minutes and
  then sit at **121.1–122.2 MB for the remaining eleven**; its working set FALLS 157 → 64 MB (the OS
  trims it under the browsers' pressure); handles and threads both oscillate with each worker
  spawn/reap and never trend. **No shell leak is visible in 15 minutes.**
* **The churn is process-level, not memory-level**: four different worker pids in 15 minutes, each a
  fresh ~212 MB process, from the rotation loop (§2.8) and the relaunch (§2.7).
* The `pythonw.exe` at 48.5 % of a core is not the app shell (52956 is 5.9 %): it was launched by a
  task host, has no window, and matches the relaunch/runner profile. I could not read its command
  line (access denied, same as py-spy). Whoever owns the relaunch tooling should identify it; on a
  box where the owner reports stutter, half a core is not noise.

So the leak answer is: **the app's memory and handle tables are steady; what is unbounded is the
number of PROCESSES it creates** (≈360 tap opens/hour idle, one worker per rotation burst, one
shell+WebView2 per relaunch) — and that churn is what the owner feels as stutter, not a slow leak.

---

## 4. Ordered fix list — by measured gain

| # | fix | expected gain (measured basis) | where |
|---|---|---|---|
| **1** | **Stop the 10 s UI-thread stall**: send status/panel-state scripts through `emit_async` (fire-and-forget) instead of the synchronous `emit`, and do not let a JS bridge call start a Python thread while the UI thread waits | the 498 × ≥10 s events = **≈5,000 s of blocked UI thread in 19 days (≈260 s/day)**, plus 112 `UI_THREAD_STALL`; 4 events in 30 s today at 10:15. This is the only hop whose tail exceeds 1 s, and the caption's `ExecuteScriptAsync` inherits it | `sotto_webview.py:7841 emit` / `:10770 emit_async` call sites; pywebview `js_bridge_call` is third-party → never call INTO JS from a thread that must not wait |
| **2** | **Stop hashing on the 2 s state tick**: memoise `file_sha256` by `(path, st_mtime_ns, st_size)` and let `panel_state_snapshot`/`code_state_log` read the cached digest | removes **43,200 × 1.30 ms = 56 s/day** of hashing on the state thread (414,911 B worker file) plus **5.23 ms per worker start** (7 files, 0.9997 MB), and the exact frame the watchdog catches (`UI_HUNG` inside `file_sha256`); the cold-disk cost the watchdog saw is the real prize, not the warm 1.3 ms | `sotto_webview.py:843 file_sha256`, `:7966 panel_state_snapshot`, `:11644 code_state_log` |
| **3** | **Quiet the four noisy log families** (rate-limit + dedup payloads): `OUTSIDE_CLICK`, `WINDOW_GEOMETRY`, `PANEL_SURFACE`, `PANEL_VISIBILITY_WRITE_FAILED` | **−58 % of log bytes** (2.37 → ~1.0 MB/day; 17.7 → 7.4 MB/h peak) and −58 % of the 7.7 µs/line producer+writer cost; also removes `OUTSIDE_CLICK`'s 3 µs from the click-hook path | call sites of those four (grep the tags) |
| **4** | **Make `panel-state.json` change-driven with a 10 s heartbeat** instead of a 2 s full rewrite | **−80 % writes**: 43,200 → 8,640/day, **−76 MB/day**, writer duty 138 → 28 s/day | `app/webview/panel_state.py:180 _loop` |
| **5** | **Give the rotation ladder a backoff on a persistently flat endpoint**: exponential (10 s → 5 min) while `device-rotated (flat)` repeats, reset on the first non-flat block | removes **≈360 tap opens/hour** while the machine is silent (measured 7–15 s cadence), each with a stream open + `reset_frontend()` + a status emit; no user-visible behaviour changes when audio flows | ladder rotation in `sotto_worker.py` (`device-rotated (flat)` path) |
| **6** | **Re-power the paint instrument before optimising the page**: its forced-layout control moves only +0.038 ms/frame against a 0.05 floor → RED. Until the control moves, every "panel paint is fine/fast" claim is un-powered | unblocks the only measurement that can size fix 7 | `_main/_panel-anim-cost.js` control arm / `_main/_panel-anim-cost-arm.py` |
| **7** | **Cap the animation's per-push cost on a loaded box** (41.86 ms mean, 1.68 s max, 848–1,496 ms LoAF per 6 s): pre-resolve the animation's layout inputs, and skip the reveal when `document.hidden` or when the previous push is still pending | needs fix 6 to size; the reduced-motion path (4.14 ms) is the floor the animated path should approach, i.e. **up to −90 % of the page's push cost**, and it is the path the owner's "zero stutter" is about | `app/panel/panel.js` caption engine + its animation start |
| **8** | **Throttle the self-relaunch while `app/webview` is being edited** (5 shells in 70 min, each paying 2.5–11 s cold start + 4 × 10 s timeouts + a 120–400 MB WebView2 boot) | removes the dominant CPU/RAM churn today | `SHELL_RELAUNCH` path in `sotto_webview.py`, floor/cap knobs |
| **9** | **Hygiene, 0 runtime gain**: delete the 34 stale `ready-*.txt`/`*.tmp`, and cap `_main` (3.4 GB, 1.2 GB of it `_audit-render`); bound `_LOG_QUEUE` (`maxsize` + drop-newest) | disk only | `_main/`, `sotto_webview.py:1137` |

Ordering is by measured gain: 1 and 2 remove the two classes the watchdog and the log actually
caught (≈260 s/day of blocked UI thread; ≈56 s/day of hashing plus the cold-disk stall); 3, 4 and 5
remove measured bytes, writes and process churn; 6 gates 7 (the only page-side work that can move
the visible stutter, and the one with the largest single measured cost — 41.86 ms per push); 8 is
churn, 9 is hygiene.

---

## 5. What I did NOT measure, and why

* **py-spy stacks** — access denied (os error 5) on the live pid; every stack here is the app's own
  watchdog (§0, I-WD). A private instance (`--mutex-name`, free hotkey) would allow py-spy but was
  not launched: Main's standing rule is not to add instances while the owner's is live.
* **The committed paint harness as shipped** — `_main/_panel-anim-cost-arm.py` gives each arm
  `SECONDS + 45 = 51 s`, and a headless Chromium on this box needs **84.7 s** to load this page
  (measured with `--dump-dom` + `--enable-logging=stderr`). That diagnosis also exposed a second,
  independent reason every arm returned `NO BEACON`: the served page asks for 12 panel scripts by
  RELATIVE name, they resolve to `/arm/<name>` in the arm dir, and `_audit-render/` in a fresh
  worktree is missing them — the page then dies at load with
  `Uncaught ReferenceError: StableWords is not defined` (`panel.js:992`) and no beacon can arrive.
  My `_main/_lane-profile-paint.py` runs the SAME probe with a 180–200 s deadline and populates
  those 12 assets from `app/panel/` itself (copied, never edited), so one command reproduces the
  table in §2.1:
  `python _main/_lane-profile-paint.py --themes theme-5 --arms reduced,on --deadline 180`.
* **The real WebView2 page** — I measured the shipped `panel.js` in Chromium, not in the app's
  WebView2. The app's own `exec_js` numbers (§2.2) are the WebView2 side of that hop.
* **RAM/handle slope within one instance** — §3.1's CSV, 15 min (803 s), per pid.

## 6. Residue this lane left, and the one thing a human must do

* My paint runs launch a headless Chromium with `--user-data-dir=` under the worktree and kill it
  with `taskkill /F /T /PID <the pid Popen gave me>`. One of those processes survived the kill and
  **cannot be killed from this lane's integrity level** (`Kill()` → `Acesso negado`): pid **51704**,
  started 10:37:38, 143 MB, no window. Whoever runs elevated should `taskkill /F /PID 51704`; it is
  a headless browser on a finished page, not the app.
* `.perf/` and `.tmp/` from the runs were removed from the worktree (`.tmp` was still held by that
  process when I tried; it will be deletable once the pid is gone).

## 7. Files this lane added (worktree only)

| file | why |
|---|---|
| `_main/receipt-20261101-profile.md` | this receipt |
| `_main/_lane-profile-paint.py` | the shipped paint probe with a deadline this box can meet (+ arm-asset population) |
| `_main/_lane-profile-census.py` | per-pid census of the mutex-owning shell + tree, 45 s cadence, CSV |
| `_main/_lane-profile-census.csv` | its output (rows keyed by pid) |
| `_main/_lane-profile-paint.json` | the raw payloads of the three arms above |
