# INTEGRATION — ONE SOTTO APP: the capture core and the WebView2 panel

Lane `single-app-design`. Written 2026-10-07. **Design lane: this file edits no source.**
Every claim about what exists today carries a file and a line, and every line was re-read
against the revision pinned in §0.1 (AGENTS.md "Keeping THIS file true", rules 1–3).

Related documents, which this one does **not** duplicate:
- `docs/design-notes/03-engine-ipc.md` — the JSONL envelope and the three IPC mechanisms. **Already written, already binding.** This file inherits its envelope verbatim.
- `docs/overlay-hotkey-contract.md` — the normative key contract. Same lane, separate file.
- `receipts/receipt-13-refute-integration-audit.md` — the refute pass. §2 below says exactly which of its claims still hold and which one has since been overtaken by code.

---

## 0. WHAT I COULD NOT VERIFY, STATED FIRST

### 0.1 The revisions this document was written against

Every line citation below was re-read against these files. **Re-run the pin before trusting
any of them** — AGENTS.md's "Keeping THIS file true" rules 1–3 exist because this tree moved
under me twice during this very lane.

| file | revision pinned |
|---|---|
| `app/webview/sotto_webview.py` | **374351 B, 6920 lines, mtime 2026-10-07 12:08:09** (`AGENTS.md:218` quotes a 4326-line revision — stale) |
| `src/capture/replay.h` | 166 lines |
| `src/capture/replay.cpp` | 581 lines |
| `src/capture/ring_buffer.h` | 83 lines |
| `src/capture/build.cmd` | `trigger.cpp` **absent** from the compile line |
| `src/engine/queue.h` / `json.h` / `json.cpp` | 78 / — / 6934 B |
| `src/capture/trigger.h` | **11708 → 12900 B**, sha256 `E22B673D72A5494A0…`, mtime 12:13:32 |
| `src/capture/trigger.cpp` | **16704 → 17373 B**, sha256 `2B4C2C3E3F4A12B…`, mtime 12:15:26 |

> **The trigger lane was actively writing while I read it.** `trigger.cpp` was 16704 B at
> 12:12:41 and 17373 B at 12:15:26 — **two revisions, three minutes.** Both file sizes appear
> in the table because I read both. Everything cited here is against the **later** revision,
> and I re-grepped every `trigger.*` line number after the change moved them.

### 0.2 Gaps

| # | gap | why it is a gap and not a sentence |
|---|---|---|
| **V1** | **"One process" is not achievable, and I did not run WebView2 to prove the alternative.** The brief asks how the two halves "coexist in one process". WebView2 runs its renderer in a separate process tree; I did not measure the process count on this host. See §1.2 — the design is stated so that the exact answer does not change it. |
| **V2** | **NVIDIA's real default hotkey set: `NOT VERIFIED`.** Two NVIDIA sources failed at the time of writing — `nvidia.custhelp.com/app/answers/detail/a_id/5035` and `a_id/5042` both returned an Oracle *"Technical Difficulties"* incident page, and `nvidia.com/en-us/geforce/shadowplay/` returned a 404 page. I did not find a readable vendor page, so **no number in the key contract is attributed to NVIDIA.** What *is* cited is Microsoft Learn, read (§hotkey doc) and the code in this repo. |
| **V3** | **`trigger.h`'s own measurement claim is unsupported.** `trigger.h:35-37` says the trigger is "measured by `_main\_lane1-trigger-gate.ps1` on THIS host (arms A/B/C/E)" and points at `receipts\receipt-15-instant-replay-trigger.md`. **Neither exists.** Measured: `Test-Path _main\_lane1-trigger-gate.ps1` → **False**; `receipts/` holds 17 files and `receipt-15-offline-cut-pass1147.md` is a different document from a different lane (8288 B, 11:52:26). I have not inherited that claim anywhere below. |
| **V4** | **In-game delivery: `NOT MEASURED`.** No game was run on this host. Every hotkey statement below is desktop-session behaviour. |
| **V5** | **Ring overhead vs the payload-only table: not re-measured here.** `receipt-13` §"What was NOT verified" carries the same gap forward; it needs a live capture run. |

---

## 1. THE ARCHITECTURE

### 1.1 The decision, in one sentence

**The C++ Engine is the parent and owns the ring; the WebView2 panel is a reconnectable child that holds no handle to the ring; the Python ASR is a second reconnectable child fed from the Engine's audio tee.**

This is not a new decision. `docs/design-notes/03-engine-ipc.md:51` already states it —
> "The **Engine is the PARENT**; the UI is a **reconnectable child**. Therefore: The Engine's capture ring keeps running when the UI dies — the UI holds no handle to the ring, only to the Engine's *event stream*."

**What this lane adds is that the production app today is the other way round**, which is
the single most important fact in this document:

| | production today (MEASURED) | what the product needs |
|---|---|---|
| parent | `sotto_webview.py` (the shell) — `main()` at `app/webview/sotto_webview.py:7448` | the **Engine** |
| child | the Python ASR worker, spawned by `WorkerBridge._spawn` (`:6345`) with `creationflags=CREATE_NO_WINDOW` (`:6388`, constant at `:171`) | the **UI** |
| when the child dies | the shell **respawns it** (`:6869` logs `BRIDGE_DEATH`, respawn at `:6442` → `_arm_silence`) | the parent must **not** die with it |
| consequence | the thing that can die in a loop is the one doing the work | the thing that must never die owns the ring |

`AGENTS.md` records what a respawn loop costs: **86 `BRIDGE_DEATH`s in one run**, every one
`WasapiError: Initialize(SHARED|LOOPBACK) failed: 0x8889000A` (`AUDCLNT_E_DEVICE_IN_USE`),
`captions=0`, restarted every 2 s forever. If capture lived in that child, those 86 restarts
would have destroyed and rebuilt the ring 86 times — and the ring *is* the product promise
(law 2: *"THE CLIP IS ALREADY WRITTEN WHEN THE KEY IS PRESSED"*).

### 1.2 "One app" is a product statement, not a process statement

The brief's phrase "coexist in one process" cannot be literal, and I will not write as if it
can. Two independent reasons, one measured and one structural:

- **Structural (READ, not measured here → V1):** WebView2 hosts the panel in
  `msedgewebview2.exe` child processes (browser, renderer, GPU, utility). The panel cannot be
  the ring's owner. The existing shell already models this: pywebview's WinForms backend runs
  the WebView2 control out-of-process, and `sotto_webview.py:3365` `_gate_form_show` has to
  intercept a `.NET` call made on a form the shell does not own.
- **Measured (AGENTS.md):** the WebView2 tree costs **416 MB** against Electron's 312 MB,
  +33%, and the owner ruled *"no fallback, WebView2 is the app."*

So "one app" is defined as: **one launcher, one tray icon, one single-instance mutex, one
hotkey namespace, one visible surface — over more than one OS process.** The process tree:

```
  run.cmd  (or the HKCU Run value; AGENTS.md: it is pythonw.exe, NEVER run.cmd)
      │
      └─ SOTTO ENGINE   (C++, mingw-w64 g++ 15.2.0 — src/capture/build.cmd:7)   ← PARENT
           │   owns: the NVENC session · the RAM ring · the WASAPI endpoint · the Trigger
           ├── msedgewebview2.exe × N        the panel — RECONNECTABLE, owns no ring handle
           └── pythonw.exe  worker/sotto_worker.py   the ASR — RECONNECTABLE
```

### 1.3 The thread model — and why the shell cannot starve capture

The requirement is that the WebView2 event loop cannot delay a cut. Three rules, each forced
by a line in the existing capture code.

**Rule A — the cut decision runs on the capture thread, and may not be moved off it.**
`Replay::issue_cut(uint64_t t_cut_ns)` is declared `replay.h:162` — inside the `private:`
section that opens at `replay.h:123` — and defined at `replay.cpp:171`. It reads
`capture_qpc_` (`std::vector<uint64_t>`, `replay.h:147`) **without a lock**, at
`replay.cpp:210`:

```cpp
// The capture-side counts are computed HERE, on the thread that owns capture_qpc_,
// so the cut thread never races the run loop for them.
uint64_t captured = 0;
for (uint64_t t : capture_qpc_) if (t >= base.qpc_ns && t <= t_cut_ns) ++captured;
```

`issue_cut` also calls `ring_.pin(base.abs_off)` (`replay.cpp:216`), which is what makes
*"a cut PINS the entries it needs"* (`ring_buffer.h:11-12`) true. **A `CutRequest` arriving
from any other thread therefore cannot be executed where it lands** — it must be *queued* and
*drained by the run loop*. This is the whole reason the hookup is not "call `issue_cut` from
the hotkey handler".

The existing call site proves the shape: `replay.cpp:539-542` is the only cut trigger today,
and it is inside `Replay::run()`'s frame loop, not on a thread of its own:

```cpp
if (!cut_issued && elapsed >= cut_ns) {
    issue_cut(f.qpc_ns);
    cut_issued = true;
}
```

**The exact hookup** (belongs to the capture lane; written here because I may not edit
`replay.cpp`). Inside `Replay::run()`, **before** the `if (elapsed >= run_ns) break;` at
`replay.cpp:480`, one drain of the trigger:

```cpp
CutRequest req;
while (trigger_.take(&req, 0)) {          // timeout 0 == non-blocking (trigger.h:153)
    issue_cut(req.t_cut_ns);              // SAME THREAD as capture_qpc_ — Rule A
    cut_issued = true;
    // one line, and it is the fix for the shell starving capture: it is a
    // non-blocking drain, so a UI that is wedged cannot hold the frame loop.
}
```

Two properties this buys, both measurable:

- **The drain is non-blocking.** `Trigger::take(&out, 0)` returns immediately. A hung panel,
  a blocked IPC write, a stalled renderer — none of them can sit inside the capture loop.
  Bounded work per iteration: the loop is otherwise already the tightest thing in the process.
- **The worst-case press→cut latency is one frame interval plus one loop pass.** The run loop
  sleeps `micro_wait_ms(1)` only on an *empty* frame pool (`replay.cpp:486-488`), and
  `WaitForSingleObjectEx` with a zero timeout is quantised to ~1 ms by the scheduler
  (`test_window.cpp:197` records that measurement for the window pump, same class of wait).
  At 60 fps a frame is 16.7 ms; at an idle pool the loop iterates about every 1 ms.
  **NOT MEASURED** end-to-end — §4 step 2 is the step that measures it.

**Rule D — the capture side is ONE-SHOT and SINGLE-SLOT. A real app needs both changed.**
This is the part the naive wiring gets wrong in the *other* direction, and it is the reason
step 1 is not "three lines":

- **One-shot.** `Replay::run()` (`replay.cpp:466`) bounds itself with
  `cfg_.run_seconds` (`replay.cpp:469`, break at `replay.cpp:480`), latches `cut_issued`
  (declared `replay.cpp:471`, set **only** at `replay.cpp:541`, **never reset**), waits once
  for the cut (`wait_cut_done(20000)`, `replay.cpp:557`), and returns (`:561`) — after which
  `shutdown()` (`:564`) releases the NVENC session, the D3D device and the window.
  **One `run()` = one clip = process exit.** A user pressing replay every 30 s for eight hours
  needs a supervisor that re-enters `run()`, and `cut_issued` must stop being a latch.
- **Single-slot.** `issue_cut` writes one job under `cut_mu_` (`replay.cpp:217-223`):
  `cut_job_ = job; cut_has_job_ = true; cut_busy_ = true;` — **with no check for a job already
  in flight.** A second press arriving while the first is still muxing **overwrites the slot**
  or double-notifies. `Trigger` will happily queue up to 8 requests
  (`kQueueCapacity = 8`, `trigger.cpp:21`); the layer below it cannot hold more than one.

**Normative requirement (capture lane):** the cut job becomes a **FIFO queue carrying
`CutRequest::request_seq`** — not a boolean — and `issue_cut` refuses rather than overwrites,
counting the refusal. The `request_seq` already exists on the request side (`trigger.h:86`
`request_seq = 0;  // 0 for the first press ever, +1 per press`), so nothing needs inventing;
it only has to be carried through to `CutResult`.

**Rule B — the cut itself already runs off the capture thread.**
`replay.cpp:166` starts `cut_thread_`; `cut_thread_main` (`replay.cpp:440-463`) waits on
`cut_cv_` and calls `perform_cut`. So the *muxing* — the expensive part, the one that writes
megabytes to the disk — never blocks the frame loop. The hotkey adds latency to a queue that
was already there; it does not create a new blocking path.

**Rule C — no thread in the capture path may ever block on a consumer.**
`Queue::push` (`src/engine/queue.h:69`, "false == dropped") takes a mutex and never waits on a
condition variable; at capacity it drops and counts (`design-notes/03-engine-ipc.md:125-138`).
The trigger already honours the same law at its own boundary: `kQueueCapacity = 8`
(`trigger.cpp:21`), and `emit` increments `stats_.queue_refused` and logs
`"a press was DROPPED, and this is the line that says so"` (`trigger.cpp:392-397`).

### 1.4 The IPC boundary

**Inherited verbatim from `design-notes/03-engine-ipc.md` — I am not re-specifying it.** The
envelope is one UTF-8 JSON object per line, `\n`-terminated, flushed inside the writer:
`{"v":1,"type":"clip.written","id":417,"ts":1759850342123,"payload":{…}}`
(`03-engine-ipc.md:70-85`). Three properties are load-bearing for this app and are quoted, not
re-derived:

1. **`id` is the resume cursor.** The UI reconnects with `since_id`; the Engine replays from
   its retained ring. A panel reload costs a `since_id`, not a disk rescan.
2. **A reader with `v != 1` counts the line as malformed; it does not guess** (`03`:76).
3. **stderr is human diagnostics and NEVER carries a protocol message** (`03`:59-62).

The two **new** boundaries this app needs that the note does not cover:

| boundary | direction | transport | why not the envelope |
|---|---|---|---|
| **Engine → ASR audio** | Engine → `sotto_worker.py` | **PCM tee**, 16 kHz mono s16le, over the child's **stdin**, as a length-prefixed binary frame — *not* JSON | 16 kHz s16 is 32 000 B/s. JSONL would hex it to 64 000 B/s of text for a stream that is the product's *fuel*. The envelope's own §3 forbids user/free-form payloads in this writer (`03`:98-102); raw PCM is the opposite case and must not go through it. |
| **ASR → Engine** | `sotto_worker.py` → Engine | the existing JSONL **on the child's stdout**, consumed with the production watchdog (`sotto_worker.py:374-377` `emit()`; the shell's reader at `sotto_webview.py:6467` `_pump` / `:6524` `_consume`) | already hardened in production; `03`:16-39 lists the four properties being inherited, including *"a null stream is logged loudly (`BRIDGE_PUMP_NULL`)"* and *"a malformed line increments a counter and returns"*. |

**THE BINDING CONSTRAINT: there may be exactly ONE owner of a WASAPI loopback endpoint.**
`worker/wasapi_loopback.py:878-890` opens with
`Initialize(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, …)` and raises
`WasapiError` when it fails. `AGENTS.md` records what happens when two processes race for it:
**86 deaths, every one `0x8889000A AUDCLNT_E_DEVICE_IN_USE`, `captions=0`.**

> **Design rule (load-bearing): the CAPTURE CORE owns the endpoint. The ASR never opens it.**
> The ASR is fed from the Engine's tee, not from a device.
>
> The alternative — ASR owns the device, capture asks for audio — makes capture depend on a
> Python process, which is exactly law 1 violated (*"CAPTURE NEVER WAITS FOR AI"*). This rule
> is the reason the PCM tee in the table above exists at all.
>
> **Cost, stated honestly:** the Engine must implement WASAPI loopback in C++. There is no C++
> tap in this repo today — `grep` over `src/capture` for `WASAPI|IAudioClient|AUDCLNT`
> returns nothing (POPULATION: 20 `.cpp`/`.h` files in `src/capture`, WINDOW: the tree as of
> 2026-10-07 12:15). The Python tap stays as the **reference implementation and the oracle**;
> it is not deleted, and §4 step 3 gates the C++ port against it byte-for-byte.

### 1.5 What happens when a half dies — the failure matrix

Every row names a failure that has actually been observed on this box, not a hypothetical.
"POPULATION/WINDOW" is given where the house rule 6 demands it.

| # | the half that dies | the concrete failure | handling | what the owner sees |
|---|---|---|---|---|
| **F1** | **UI / WebView2 renderer** | renderer or GPU process crash; panel reload; user closes the panel | Engine notices the child's pipe close (`EOF` on the event stream) and **does not respawn it into a recording**. If the panel is up, it is respawned with `since_id = last id seen`. Capture is untouched — the Engine does not hold a UI handle. | captions keep arriving; the panel returns on its own. Measured precedent for "the shell is replaceable": `AGENTS.md` records 8 worker cycles where the bridge logged `BRIDGE_EXIT` and the app recovered. |
| **F2** | **Engine (C++ parent)** | crash, OOM, GPU device lost, NVENC session loss | There is no parent left to restart it, so **the launcher owns this**: `run.cmd` / the `HKCU Run` value supervises and relaunches. A relaunch starts a **fresh empty ring** — it cannot recover the old one, and the contract says so rather than implying continuity. | recording stops; restart is automatic within the supervisor's interval; the panel (if alive) shows the Engine as gone rather than frozen. |
| **F3** | **ASR worker** | the Python process exits (measured precedent: 86 deaths, F-matrix row above) | Engine respawns it, **because the Engine is the parent and the ring is above the ASR**. This inverts today's direction (§1.1) and is the single change that makes the ring survive the observed failure. | captions pause; the recording and the clip do not. |
| **F4** | **WASAPI endpoint** | another process holds it (`0x8889000A`), or the audio device changes | The Engine **waits and retries** before giving up — measured cure already applied to the worker: *"a busy endpoint is waited for and retried twice (1.5 s) before the ladder moves on"* (`AGENTS.md`, worker `sotto_worker.py`). The C++ port copies that ladder, it does not invent a faster one. | clip continues; its audio track is missing **and says so** — never a silent 8/8-`AUDIO=NONE` clip, which is precisely the defect `receipt-13` row 2 upheld. |
| **F5** | **NVENC** | session exhaustion — **MEASURED: 10 sessions held, #11 refuses with status 21** (`docs/research/03-nvenc-sessions.md`, cited in `ROADMAP.md:32`) | Law 6 already ships the gate: `selftest.cpp` / `law_six_gate` refuses with a loud reason and **exit 3** rather than arming a key that cannot work (`main.cpp:229-230`: *"The replay hotkey is NOT armed. A dead hotkey that says why beats a live hotkey that does nothing."*). | the replay key does nothing **and the log says why**; the app does not lie. |
| **F6** | **ring under pressure** | the ring cannot free space without losing its last IDR | `ring_buffer.h:9-11`: the frame is **dropped and counted** (`dropped()`), and the encoder is asked to force an IDR. `main.cpp:320` publishes `ring_dropped` in the run summary. | a measurable counter, never a silent frame loss. |
| **F7** | **the ring is shorter than the request** | the user presses the key and gets 4 s when they asked for 30 | **Already named in the code**: `CutRequest::ring_span_s` / `shorter_than_requested` (`trigger.h:89-90`), filled from the `RingSpanProbe` (`trigger.h:99-104`, `trigger.cpp:378-382`) with the note *"the clip will be short, and this says so"*. | a short clip **plus the reason**, which is the difference between a product and a clamp. |
| **F8** | **no IDR in the ring at all** | the ring has no keyframe a decoder can start from | `replay.cpp:181-183` refuses and increments `cuts_refused`: *"NO IDR IN THE RING - refusing to write a clip a decoder cannot start"*. | a refused cut with a reason, not an unplayable file. |
| **F9** | **disk full / clip write fails** | `perform_cut` returns false | `cut_thread_main` counts `cuts_refused` (`replay.cpp:454-455`) and stores `last_cut_`; the run summary prints it (`main.cpp:367`). | the loss is counted and attributable. |
| **F10** | **the hotkey is owned by another app** | `RegisterHotKey` → 1409 | **Fully specified in the hotkey contract**; production precedent measured on this box: `Alt+C` FREE, `Alt+F9` OWNED (`sotto_webview.py:1254-1256`). | a fallback key registers and `WARN HOTKEY_FALLBACK requested=… using=…` is logged (`:2003-2004`); if every key is taken, one error dialog (`:1963-1982`). |
| **F11** | **a second app instance starts** | a second shell steals nothing but answers nothing | `take_single_instance_lock` (`sotto_webview.py:1276-1302`, `Local\SottoShell`) refuses the second. **Skipped for measurement flags** (`--no-hotkey`, `--dump-dom`, `--selftest`, `--memory`, `--probe-v2`) — AGENTS.md: *"Never make that lock unconditional again."* | one app, one hotkey owner. |

---

## 2. THE REFUTE PASS: WHAT SURVIVES, AND WHAT HAS BEEN OVERTAKEN

`receipt-13-refute-integration-audit.md` must be honoured, not repeated. Three of its rows,
re-measured on 2026-10-07:

| receipt-13 row | its verdict | **status now** | evidence |
|---|---|---|---|
| 1 — "No hotkey anywhere in capture" (0 hits over `src/capture/*.cpp\|*.h`) | UPHELD | **STALE — overtaken by new code, and the receipt was CORRECT WHEN MEASURED** | `src/capture/trigger.h` (11708 B) and `trigger.cpp` (16704 B at 12:12, 17373 B by 12:15) now exist and contain `RegisterHotKey`, `GetAsyncKeyState`, `WM_HOTKEY`, `VK_*`. This is **not** a refutation error; a sibling lane shipped the missing feature ~45 min after the receipt was written. **Do not cite receipt-13 row 1 as current.** |
| 2 — "Clips have no audio stream" (8/8 `AUDIO=NONE`) | UPHELD | **STILL HOLDS, and it is now the binding constraint** | unchanged; and §1.4 makes "one endpoint owner" the fix. |
| 3 — "The Tauri Rust has never compiled" | **REFUTED** (auditor retracted it) | **STILL REFUTED** | `cargo build` → rc=0, 215 707 515 B PE at `H:\jcode-target-gnu\debug\sotto.exe` — because `H:\cargo\config.toml` sets `target-dir` globally, so output never appears in `src-tauri\` (receipt-13:22-31). **The trap is still live: anyone reading `src-tauri\target\` will conclude the build failed.** |

**I am not resurrecting any refuted claim, and I am not letting a now-stale row keep
misleading lanes.** The only row I contradict is row 1, and I contradict it **in the receipt's
disfavour only because time passed** — its measurement method was sound.

---

## 3. WHAT THE SHELL IS TODAY (so no lane has to re-derive it)

`app/webview/sotto_webview.py`, **374351 B, 6920 lines, mtime 2026-10-07 12:08:09** (pinned;
`AGENTS.md:218` warns this file moves constantly and quotes a 4326-line revision). Every line
below was re-read against that revision.

| what | where | why it matters here |
|---|---|---|
| `HotkeyThread` — `RegisterHotKey(hWnd=NULL, …, MOD_NOREPEAT)` on its own thread, own queue | `:1171`, `:1202-1203`, `:1216-1225` | the pump-thread rule, **already proven on this box**; the C++ `Trigger` mirrors it (`trigger.h:12-22`) |
| fallback chain `('Alt+Shift+C','Ctrl+Alt+C','Ctrl+Shift+C')` | `:1259`, walked at `:1995` | reused verbatim by the hotkey contract |
| `HOTKEY_FALLBACK` log line naming which key won | `:2003-2004` | the honesty rule |
| one-off `MessageBoxW` when **every** key is taken | `:1963-1982`, raised on a thread because *"the panel cannot be the messenger: nothing can open it"* | copied into the contract |
| `single-instance` mutex `Local\SottoShell` | `:1276-1302` | F11 |
| `WorkerBridge` + `_spawn`/`_pump`/`_consume`/`_arm_silence` | `:6156`, `:6345`, `:6467`, `:6524`, `:6688` | the production JSONL bridge the Engine speaks to the ASR |
| `--hotkey` default `'Alt+C'` | `:7067`; armed at `:7588` | the one control the whole app has |
| `_gate_form_show` | `:3365` | the panel must not paint itself unasked — a rule the one-app design inherits unchanged |
| Tauri shell is an **M0 mock** | `H:\sotto\app\src-tauri\` exists; `tauri.conf.json` `frontendDist: "../dist"` — *neither* panel | confirmed: it points at a directory that is not `app\panel`. `receipt-13` §"not verified" called this open; it is still open. |

> **The shell is at `H:\sotto\app\webview\`, NOT under `_moved\aireplay`.** Measured:
> `Test-Path H:\sotto\_moved\aireplay\app` → **False**. `ROADMAP.md:39` and `:188` both
> reference `app/src-tauri`, which resolves correctly relative to `H:\sotto`. Any lane looking
> for the Tauri shell inside the ShadowPlay tree will not find it.

---

## 4. THE BUILD ORDER — FRONTEND LAST, EVERY STEP MEASURABLE

`ROADMAP.md` §2 sets the phases (P0 integrate → P1 unknowns → P2 one app → P3 frontend).
This is the ordered expansion with a pass condition attached to every step. **A step with no
observable pass condition does not appear here.** The app is useful — and shippable — from
**step 3 onward with no UI at all**.

### Step 0 — make the tree that holds the product durable *(gate, not work)*
`ROADMAP.md` §0c records B2 as fixed at commit `a66da94`: `git ls-files _moved` 0 → **328**,
`git clean -nd _moved` 419 paths → **2**.
**MEASURABLE:** `_main\_lane02-durability-oracle.ps1` GREEN; ARM-A (a non-existent path) RED.

### Step 1 — put the trigger on the run loop *(the smallest change that makes instant replay real)*
The seam is the three-line drain in §1.3 Rule A. **Before it:** the only cut is the timer at
`replay.cpp:539-542`, which has no operator input at all.
**MEASURABLE — and it can go RED:**
- press the bound key during a live 1080p60 encode → **a clip on disk in < 1 s**
  (`specs/01` S1 target, cited `ROADMAP.md:156`);
- `frames_ring_dropped == 0` (`common.h:56`, printed at `main.cpp:320`);
- `ffmpeg -v error -i <clip> -f null -` exits **0** — a clean decode, not a truncated file;
- **a held key produces exactly ONE cut.** The edge latch is `trigger.cpp:329-346`; the cure
  line is `trigger.cpp:346` (`held_[i] = down ? 1 : 0;`), and deleting that one line in a COPY
  must make a held key produce many. This is the both-colour gate.
- **two presses in quick succession produce TWO clips, and both are counted.** This is the gate
  for Rule D (§1.3) and the only one that catches the single-slot defect: `issue_cut`
  overwrites an in-flight job at `replay.cpp:217-223`. RED = two presses, one clip. **A step-1
  gate that only presses once cannot see this bug at all.**
- **RED arm:** a build whose run loop never drains the trigger reports `armed=true`,
  `requests>0` in the trigger's own counters, and **zero clips**. An instrument that cannot
  say NO here is worthless.
- **Gate the trigger itself FIRST.** `trigger.cpp` is **not in `src/capture/build.cmd`**'s
  compile line (READ 2026-10-07 — the line lists `main.cpp common.cpp d3d11_ctx.cpp
  nv12_convert.cpp wgc_capture.cpp nvenc_encoder.cpp ring_buffer.cpp mp4_writer.cpp
  selftest.cpp test_window.cpp replay.cpp` and no `trigger.cpp`). So step 1 begins with
  *adding it to the build*, and the compiler is the first oracle. **Until then `trigger.cpp`
  has never been compiled and I make no claim about it beyond reading it.**

### Step 2 — measure the press→clip latency, honestly
**MEASURABLE:** over ≥ 30 presses in one run, report **min / median / p95 / max** of
`press → clip file complete`, plus `detected_latency_us` (already a field, `trigger.h:87`)
and the drain-to-`issue_cut` delta. The budget is `< 1 s` at p95.
**This is the step that converts §1.3's arithmetic into a measurement.** If p95 misses 1 s,
the drain is in the wrong place — fix it here, not after the UI exists.

### Step 3 — audio: one owner, muxed beside the video *(the app is now useful: a real clip with sound)*
Port the WASAPI loopback to C++ in the Engine; **do not** import the Python tap into the
capture thread, and **do not** let the ASR open the device (§1.4).
**MEASURABLE, and it can go RED:** one capture whose clip `ffprobe -select_streams a` reports
`codec_type=audio` at 16 kHz mono; the same run shows `0x8889000A` **zero** times while the ASR
child is alive and transcribing from the tee. RED = an `AUDIO=NONE` clip (the exact 8/8 defect
`receipt-13` upheld) or any `DEVICE_IN_USE`.

### Step 4 — the Engine as parent: the shell becomes a child *(nothing visible changes; everything about failure changes)*
Invert §1.1. The Engine supervises both the panel and the ASR; the panel reconnect carries
`since_id`.
**MEASURABLE, both colours:** kill the **panel** process → the Engine keeps capturing and the
ring is never reallocated (`ring_capacity()` unchanged across the kill, `replay.h:95`);
kill the **ASR** → it is respawned and recording never stops. The RED arm is the pre-inversion
arrangement, where killing the worker takes the ring with it.

### Step 5 — SQLite: the durable spine (`ROADMAP.md` P0 item 4)
Identity is `content_key`, which a message-passing engine cannot express — `ROADMAP.md:170-171`.
**MEASURABLE:** a clip written, then the process killed hard (`TerminateProcess`, no clean
shutdown), then relaunched → the clip row is present and `content_key` resolves to the same
file. RED = a clean-shutdown-only fixture passing, which proves nothing.

### Step 6 — close P1's deciding unknowns (`ROADMAP.md` §2 P1)
`cargo build` in `H:\sotto\app\src-tauri` producing a binary **at the real path**
(`H:\jcode-target-gnu\debug\sotto.exe`, not `src-tauri\target\` — §2 row 3); OCR recall on
real screen text.
**BLOCKED, owner call:** the embedding benchmark needs a **~1.5 GB download** and there are
**no embedding weights on disk** (`ROADMAP.md:120-125`, B4). *Do not start it silently.*

### Step 7 — search + memory behind the Engine (`ROADMAP.md` P2)
3-channel RRF `{speech 1.0, ocr 1.0, visual 0.7}`, `k=100`; modules copied **with sha256 at
copy time** so later divergence is detectable.
**MEASURABLE:** the design's own number — **16 ms/query exact over 206 MiB**, numpy brute
force (`ROADMAP.md:34`) — re-measured end-to-end through the Engine, not just in the research
harness.

### Step 8 — FRONTEND, LAST (`ROADMAP.md` P3)
Only now does the panel host replay. Budget **150–300 MB acceptable; 800 MB–1.5 GB investigate
aggressively** (`ROADMAP.md:198-199`), and **benchmark early in this step, not at the end**.
**MEASURABLE:** panel opens and closes 100× with no leak; the WebView2 tree's RSS sits inside
the budget; and the panel still honours the two rules it already has — `_gate_form_show`
(`:3365`, nothing paints unless asked) and the live-vs-history producer guard
(`app/panel/history-source.js:51` `CANONICAL_PRODUCER = 'redux'`), whose related open risk is
recorded in `AGENTS.md`.

**Why this order earns "frontend last":** steps 1–7 deliver the entire product — instant
replay, sound, memory, search — through `run.cmd` and a log line. The panel is a **view**, not
a prerequisite. A lane that needs the UI earlier is building a different product.

---

## 5. THE TWO THINGS THAT BREAK FIRST

Both found by reading, both load-bearing. Stated here so they are designed for rather than
discovered.

### 5.1 A second WASAPI loopback opener kills both, silently
**Two processes opening the same loopback endpoint will kill each other, and the symptom is a
silent capture loop, not a loud crash.** `AGENTS.md` measured 86 such deaths. Every design
choice in §1.4 exists to make a second opener impossible.

> **STEP 3 IS AN ATOMIC CUTOVER, NOT AN ADDITIVE CHANGE.** Adding the C++ tap *without*
> removing the Python tap's endpoint open is precisely what produces the 86-death loop, and it
> would look like "the new audio code is broken." There is no intermediate state in which both
> are live. Sequence it as: port → gate the C++ tap in the COPY → **then** switch the ASR to
> the tee → **then** delete the Python open. The gate for the cutover is step 3's RED arm.

### 5.2 The capture side cannot yet take a second cut
`Replay::run()` is one-shot and the cut job is a single slot (Rule D, §1.3). An implementer who
adds the trigger drain and then presses the key twice will see the second press vanish, and
will not know whether the bug is theirs or the engine's. **It is the engine's.** §4 step 1 must
not be called done until pressing twice in quick succession yields two clips, both counted.