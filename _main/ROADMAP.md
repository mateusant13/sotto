# SOTTO — ShadowPlay clone: feature gap, ordered delivery, acceptance gates

**Lane:** `lane/roadmap` · **Written:** 2026-10-07 · **Target:** a COMPLETE NVIDIA ShadowPlay clone,
integrated under Sotto, **frontend LAST**.

**THE CODE IS THE TRUTH.** Every PRESENT/PARTIAL verdict below cites a `file:line` re-grepped on
2026-10-07. Where a document in this repo contradicts the code, the code wins and the document's
claim is recorded as a deviation. `worker/README.md` itself admits its line numbers "DRIFT"
(`worker/README.md:33-38`) and still points at a panel directory that no longer exists
(`worker/README.md:4` says `app/electron/panel.*`; the shipped panel is `app/panel/`).

---

## 0. MEASURED FACTS (taken on this host today, not inherited from the briefing)

### 0.1 The briefing's hardware premise is WRONG in the one place that matters most

The briefing said *"no CUDA, no MSVC, mingw g++ 15.2 only"*. The first half is right, the
conclusion drawn from it is not. Measured:

| probe | result |
|---|---|
| `nvidia-smi --query-gpu=name,driver_version --format=csv,noheader` | **`NVIDIA GeForce RTX 5080, 617.14`** |
| `nvcc` | ABSENT |
| `cl` (MSVC) | ABSENT |
| `g++` | `H:\msys64\mingw64\bin\g++.exe`, **15.2.0** (MSYS2 MinGW) |
| `ffmpeg -version` | **8.1.1** (gyan.dev full build) |
| `ffmpeg -encoders` | **`h264_nvenc`, `hevc_nvenc`, `av1_nvenc`** all present |
| WebView2 runtime | `154.0.4258.62` |
| `python --version` | 3.11.8 |

**Consequence — the single most important line in this document.** The RTX 5080 is present and its
driver works, and FFmpeg reaches **NVENC H.264 / HEVC / AV1 without the CUDA toolkit and without
MSVC**. "No CUDA" is therefore *not* a blocker for ShadowPlay-grade recording: NVENC is exposed
through FFmpeg's dynamic loading, not through `nvcc`. Every NVENC-shaped risk in the previous
attempt was bought by choosing a C++ kernel; **this roadmap does not build one in Phase 0–3.**

### 0.2 What Sotto actually is today

Sotto is **audio → captions**, not video. `AGENTS.md:3-5` carries the owner's verbatim acceptance
(*"o alt c mostre as transcricoes em tempo real, de qualquer audio do meu pc. e legendas."*).

- `worker/sotto_worker.py` — 4164 lines / ~236 KB. JSONL on stdout, **audio** loopback → RNN-T → captions.
- `app/webview/sotto_webview.py` — 7199 lines. pywebview/WebView2 shell, entry `app/webview/run.cmd`.
- `app/panel/panel.{html,css,js}` — 663 / 1583 / 2114 lines. Caption + history UI.
- `worker/models/` — 9 local model dirs, all ONNX CPU/INT4.

A grep for `Windows.Graphics.Capture|GraphicsCaptureItem|screen_capture|WGC|mss.|import cv2|ffmpeg|av.open|VideoWriter`
across `H:\sotto` returns **zero hits in shipped code** — every hit is inside `_moved/aireplay`.
**Sotto contains no video capture of any kind.**

### 0.3 There is a prior attempt, and it was moved aside

`_moved/aireplay/` is a frozen clone attempt: 60+ receipts, 24 reviews, C++ sources
(`replay.cpp`, `ring_buffer.cpp`, `wasapi_audio.cpp`, `trigger-mutant.cpp`), and its own
`ROADMAP.md` (P0 INTEGRATE `:66`, P1 unknowns `:176`, P2 one app `:192`, P3 frontend last `:196`).

Its own words, `_moved/aireplay/HANDOVER.md:21-23`:

> "A transcrição, o índice e as verificações estão implementados e medidos. **A captura de janelas
> está BLOQUEADA** desde as 11:20 (WGC `E_ACCESSDENIED`), e o bloqueio **não** se levantou."

And the architecture it committed to, `_moved/aireplay/src/capture/replay.h:1`:

> "the whole path: WGC -> NV12 -> NVENC -> RAM ring -> clip.mp4"

It hedged the broken component with an offline path, `replay.h:119-125`:

> "OFFLINE VALIDATION OF THE CUT PATH — no WGC, no NVENC, no D3D11 … This exists because WGC began
> refusing every capture item on this box (E_ACCESSDENIED)".

`_moved/aireplay/src/pipeline/contracts.py:448` repeats it as a standing gap.

**Read as prior art, this is one lesson and one warning.**
- *Lesson:* the cut/mux path was right, and it is reusable.
- *Warning:* it was reached through a **C++ kernel that needed MSVC this host does not have**,
  which is why `_moved/aireplay/src/pipeline/chain.py:221` records `Replay::perform_cut()` as a
  "DOUBLE … cannot run here". The toolchain, not the idea, killed it.
- The handover instructs: *"mede de novo em vez de citar este ficheiro"* (`HANDOVER.md:4-6`).
  **This roadmap therefore treats the WGC verdict as a prior measurement to re-prove in Phase 0,
  not as a fact.**

---

## 1. The ShadowPlay feature set, with a source per feature

Primary source is NVIDIA's own product page for the NVIDIA App (the app that now carries
ShadowPlay), plus the NVIDIA Broadcast page. NVIDIA's AEM site serves a clean markdown rendition at
the same path with `.md` appended; that is what was fetched.

| # | Feature | Source URL |
|---|---|---|
| F1 | **Instant Replay** — DVR-style rolling buffer, save the last 30 seconds (length configurable) | https://www.nvidia.com/en-us/software/nvidia-app/ · https://savereplay.com/guides/record-gameplay-clips-nvidia-instant-replay |
| F2 | **Manual record** to 8K HDR 30fps / 4K HDR 120fps; **AV1** on RTX 40+ | https://www.nvidia.com/en-us/software/nvidia-app/ |
| F3 | **Capture area**: full screen, window, or **custom region** | https://www.nvidia.com/en-us/software/nvidia-app/ · https://www.pcguide.com/gpu/how-to-record-with-geforce-experience-shadowplay/ |
| F4 | **Multi-capture** — game + webcam/mic simultaneously, separate tracks | https://www.nvidia.com/en-us/software/nvidia-app/ · https://mundobytes.com/en/Record-your-screen-with-NVIDIA-ShadowPlay-and-GeForce-Experience/ |
| F5 | **Webcam picture-in-picture overlay** with camera filters | https://www.nvidia.com/en-us/software/nvidia-app/ · https://www.pcguide.com/gpu/how-to-record-with-geforce-experience-shadowplay/ |
| F6 | **NVIDIA Broadcast effects** — Noise Removal, Room Echo Removal, Studio Voice, Virtual Background (remove/replace/blur), Virtual Key Light, Eye Contact, Video Noise Removal, Auto Frame | https://www.nvidia.com/en-us/geforce/broadcasting/broadcast-app/ |
| F7 | **Replay save + timeline trimming** before export | https://savereplay.com/guides/record-gameplay-clips-nvidia-instant-replay |
| F8 | **Performance overlay** — FPS, 1% Low, frametime, GPU & CPU utilization, VRAM, PC latency, Reflex Analyzer | https://www.nvidia.com/en-us/software/nvidia-app/ |
| F9 | **Game filters** — Freestyle: RTX Dynamic Vibrance, RTX HDR, 1200+ titles | https://www.nvidia.com/en-us/software/nvidia-app/ |
| F10 | **Highlights** — automatic detection and recording of gameplay moments | https://www.nvidia.com/en-us/software/nvidia-app/ · https://gamerhardware.org/nvidia-shadowplay-recording-guide/ |
| F11 | **Streaming / broadcast** from the same pipeline | https://www.nvidia.com/en-us/software/nvidia-app/ · https://mundobytes.com/en/Record-your-screen-with-NVIDIA-ShadowPlay-and-GeForce-Experience/ |
| F12 | **Audio mixing** — desktop + mic as separate sources with per-source volume | https://gamerhardware.org/nvidia-shadowplay-recording-guide/ · https://mundobytes.com/en/Record-your-screen-with-NVIDIA-ShadowPlay-and-GeForce-Experience/ |
| F13 | **Global hotkeys** — overlay toggle, save instant replay, mic toggle, highlight, screenshot | https://www.nvidia.com/en-us/software/nvidia-app/ · https://savereplay.com/guides/record-gameplay-clips-nvidia-instant-replay |

**Cost-of-capture note for F6/F9:** NVIDIA Broadcast's effects and Freestyle's RTX filters are
shader-level NVIDIA features. On this box they are reachable only through NVIDIA SDK components
(NVENC is fine via FFmpeg §0.1); a true equivalent of Freestyle is **out of reach without the CUDA
toolkit** and is sized L below, and is explicitly sequenced last so it cannot block the core.

---

## 2. THE GAP TABLE

`Sotto has` is measured against **shipped** code only. `_moved/` is excluded from the "has" column
and used only as prior art.

| # | Feature | ShadowPlay has | Sotto has | Evidence (file:line) | Gap | Blocking dependency |
|---|---|---|---|---|---|---|
| F1 | Instant replay rolling buffer | 30s rolling, save on demand | **ABSENT** | no capture in shipped tree; contract is audio-only (`worker/README.md:3`, `AGENTS.md:3-5`) | **L** | Phase 0 capture source + Phase 1 ring |
| F2 | Manual record 4K/8K, AV1 | NVENC AV1 on RTX 40+ | **ABSENT** (encoder is *available*, unused) | `ffmpeg -encoders` → `av1_nvenc` present; no caller in `worker/` or `app/` | **L** | Phase 1 |
| F3 | Full-screen / window / region capture | all three | **ABSENT** | grep for `Windows.Graphics.Capture\|mss.\|import cv2` → 0 hits outside `_moved` | **L** | Phase 0 + Phase 4 |
| F4 | Multi-capture, separate tracks | game + webcam + mic | **ABSENT** | no video compositor in `app/panel/panel.js` (2114 lines, all caption/history) | **L** | Phase 4 |
| F5 | Webcam PiP + camera filters | yes | **ABSENT** | no webcam device enumeration in `app/webview/sotto_webview.py` (7199 lines) | **M** | Phase 4 |
| F6 | Broadcast effects (bg removal, eye contact, auto-frame…) | 8 effects | **ABSENT** — and no model on disk | `worker/models/` holds 9 ASR/LLM dirs only; no segmentation model | **L** | Phase 7 (needs NV SDK / CUDA — see B3) |
| F7 | Save replay + timeline trim | trim in UI | **ABSENT** | no mux/timeline in shipped tree | **M** | Phase 2 |
| F8 | Performance overlay | FPS/1% Low/GPU/CPU/VRAM/latency | **PARTIAL** — a global overlay window exists and is DPI/shape-aware, but draws **captions, not metrics** | `app/webview/sotto_webview.py:744` ("Win32 — work area, DPI, extended styles, the hotkey"); `:571`; `:930` `SOTTO_APP_USER_MODEL_ID='sotto.overlay'` | **M** | Phase 5 |
| F9 | Game filters (Freestyle, RTX HDR, Vibrance) | 1200+ titles | **ABSENT** | no GPU shader path in shipped tree | **L** | Phase 7 (CUDA absent) |
| F10 | Highlights auto-capture | automatic moments | **PARTIAL** — a real, working *speech* event detector already exists and is over a live loopback; it is caption logic, not video logic | `worker/sotto_worker.py` states `no-speech-in-capture`, `music-only-capture`, `device-rotated`; `app/webview/sotto_webview.py:216` `WORKER_CAPTURING_STATES` | **L** | Phase 6 (detector reusable) |
| F11 | Streaming | yes | **ABSENT** | grep `rtmp` across `H:\sotto` → no shipped caller | **M** | Phase 6 |
| F12 | Audio mixing, per-source volume | desktop + mic separate | **PARTIAL** — one **loopback** audio path exists and is deeply hardened; **no mic source, no mixer, no per-source volume** | `worker/sotto_worker.py` capture ladder + silence/exhaustion states; routing law measured in `AGENTS.md:27-49` | **M** | Phase 3 |
| F13 | Global hotkeys | 5+ distinct, rebindable | **PARTIAL** — **one** hotkey (Alt+C), fixed purpose, rebindable via `run.cmd --hotkey`, with real failure handling | `app/webview/sotto_webview.py:1202` `RegisterHotKey`, `:1182` `HotkeyThread`, `:1985` `arm_hotkey`, `:1950` `warn_hotkey_unavailable`, `:31` MOD_NOREPEAT | **S** | Phase 5 (reuses `HotkeyThread`) |

**Roll-up:** 1 of 13 features is genuinely PRESENT, 4 are PARTIAL, 8 are ABSENT. Sotto's reusable
assets are the audio loopback (F12), the event-detection vocabulary (F10), the overlay/hotkey
plumbing (F8, F13) and the WebView2 shell. **Nothing in the video path exists and must be built.**

---

## 3. HARDWARE BLOCKERS ON THIS HOST — named, not glossed

| ID | Blocker | Measured | What it actually blocks | Bypass |
|---|---|---|---|---|
| **B1** | **WGC refuses every capture item** (`E_ACCESSDENIED`) — prior measurement, since 11:20 on 2026-10-07 | `_moved/aireplay/HANDOVER.md:21-23`; `src/pipeline/contracts.py:448`; `src/capture/replay.h:121-123` | ALL live capture: F1, F2, F3, F4, F5, F10 | **Phase 0 must find a non-WGC source** (Desktop Duplication, `ddasink`, GDI). **This is the largest blocker in the project.** |
| **B2** | **No MSVC**; only MinGW `g++` 15.2 | `Get-Command cl` → ABSENT; `g++ --version` → 15.2.0 | Any C++/WinRT/COM capture kernel — which is exactly what `_moved/aireplay` tried and could not build (`chain.py:221`) | **Keep Phases 0–6 in Python + FFmpeg.** C++ is off the critical path entirely |
| **B3** | **No CUDA toolkit** (`nvcc` ABSENT) | `Get-Command nvcc` → ABSENT | Freestyle-class shader filters (F9) and true Broadcast SDK effects (F6) | **NVENC is NOT blocked** (§0.1). F6/F9 degrade or ship as `ffmpeg`-level filters |
| **B4** | Prior `aireplay` work is **moved aside**, not merged | `_moved/` | none, but its C++ is unbuildable here | Reuse only its *cut/mux design* (`replay.h:119-125`) and receipts |

**B1 is the one that sinks the project if it is not solved first.** Everything in Phase 1–6 is
downstream of "this box can produce live frames at all". Phase 0 exists solely to answer it.

---

## 4. THE ORDER — frontend LAST, each phase independently verifiable

Every gate is a command that **exits non-zero on failure**, plus a **deliberately-broken negative
arm** that must go RED. If the negative arm passes, the gate is not a gate and the phase does not
count. Gate scripts follow the repo's existing oracle convention (`_main/*-oracle.py`,
`_main/*-probe.py`).

Windows PowerShell, run from the lane's worktree root.

---

### Phase 0 — UNBLOCK CAPTURE (the deciding unknown; nothing else is worth starting until this is green)

**Do:** re-measure B1 on this box today, then prove **one** live screen-capture path that does not
use WGC. Ladder, cheapest first: (a) re-run the WGC probe to confirm the refusal is still real;
(b) Desktop Duplication via `dxcam`; (c) `ffmpeg -f ddasink`; (d) `ffmpeg -f gdigrab` as the
always-works floor. Record which rung answered.

**Gate (must exit 0):**
```powershell
python _main/oracles/capture-oracle.py --require-live --min-fps 15 --seconds 5
if ($LASTEXITCODE -ne 0) { exit 1 }
```
**Negative arm (must exit NON-ZERO):**
```powershell
python _main/oracles/capture-oracle.py --require-live --arm=broken
if ($LASTEXITCODE -eq 0) { Write-Error "GATE CANNOT GO RED"; exit 1 }
```
`--arm=broken` points the oracle at a deliberately wrong capture backend (the one rung measured
dead in 0(a)); it must fail.

**If Phase 0 exits non-zero on every rung, STOP. Everything below is unreachable** and the finding
itself is the deliverable — escalate, do not build on a dead foundation.

---

### Phase 1 — RAM RING + NVENC (encode at rate, never to disk)

**Do:** frames from Phase 0 → `ffmpeg` → **`h264_nvenc`** (and prove **`av1_nvenc`**) into an
in-memory ring with eviction accounting. No file I/O on the hot path. Measure encode fps vs source
fps and prove the ring never blocks capture.

**Gate (must exit 0):**
```powershell
python _main/oracles/ring-nvenc-oracle.py --seconds 30 --ram-only --require-codec h264_nvenc
if ($LASTEXITCODE -ne 0) { exit 1 }
```
**Negative arm (must exit NON-ZERO):**
```powershell
python _main/oracles/ring-nvenc-oracle.py --seconds 30 --arm=evict-without-accounting
if ($LASTEXITCODE -eq 0) { Write-Error "GATE CANNOT GO RED"; exit 1 }
```
The arm injects a frame-sized drop; the oracle must notice the discontinuity and exit non-zero.

**Hardware note: green is expected here.** NVENC is reachable without nvcc (§0.1). This phase does
**not** touch B2 or B3.

---

### Phase 2 — INSTANT REPLAY + CUT (F1, F7) — the feature the whole product is named for

**Do:** hotkey-triggered cut of the last N seconds out of the ring while **recording continues**;
pin the range so the cut thread cannot be overrun. Reuse the proven design of
`_moved/aireplay/src/capture/replay.h:7-8` ("The cut PINS the ring range it needs") without reusing
its C++.

**Gate (must exit 0):**
```powershell
python _main/oracles/instant-replay-oracle.py --arm=live --keep-recording --assert-gap 0
if ($LASTEXITCODE -ne 0) { exit 1 }
```
**Negative arm (must exit NON-ZERO):**
```powershell
python _main/oracles/instant-replay-oracle.py --arm=overwrite
if ($LASTEXITCODE -eq 0) { Write-Error "GATE CANNOT GO RED"; exit 1 }
```
`--arm=overwrite` removes the pin so the cut races the writer; the oracle must detect a corrupted
or short clip and exit non-zero.

---

### Phase 3 — AUDIO MIXER (F12) — reuse Sotto's one mature subsystem

**Do:** add a **mic** source and per-source volume alongside the existing loopback. The loopback
path is already hardened and already knows the failure vocabulary (`silent-device`,
`device-exhausted`, `music-only-capture`). Respect `AGENTS.md:27-49`: on this host a silent loopback
is usually **correct behaviour** caused by routing, and the mixer must say so rather than exit 0.

**Gate (must exit 0):**
```powershell
python _main/oracles/audio-mix-oracle.py --sources loopback,mic --gain 0.0,1.0
if ($LASTEXITCODE -ne 0) { exit 1 }
```
**Negative arm (must exit NON-ZERO):**
```powershell
python _main/oracles/audio-mix-oracle.py --sources loopback,mic --gain 0.0,0.0 --expect-silence
if ($LASTEXITCODE -eq 0) { Write-Error "GATE CANNOT GO RED"; exit 1 }
```
Muting both sources must produce measured digital silence (peak below a declared floor) and a
non-zero exit; if it reports signal at both gains, the gain control is inert.

---

### Phase 4 — CAPTURE CONTROL + COMPOSITOR (F3, F4, F5)

**Do:** full-screen / window / **region** selection; a second capture source composited as
**webcam PiP**; emit separate tracks.

**Gate (must exit 0):**
```powershell
python _main/oracles/region-compositor-oracle.py --region 320,180 --pip bottom-right --assert-both-tracks
if ($LASTEXITCODE -ne 0) { exit 1 }
```
**Negative arm (must exit NON-ZERO):**
```powershell
python _main/oracles/region-compositor-oracle.py --region 320,180 --pip bottom-right --arm=single-surface
if ($LASTEXITCODE -eq 0) { Write-Error "GATE CANNOT GO RED"; exit 1 }
```
The arm composites into one surface; the oracle must see the PiP rectangle missing from the region
and exit non-zero.

---

### Phase 5 — OSD + GLOBAL HOTKEY SET (F8, F13) — frontend, but not panel work

**Do:** the overlay is the one UI surface that must exist *with* capture, because a hotkey that
toggles an OSD is useless if the OSD stalls the encoder. Add FPS/frametime/GPU/CPU/VRAM to the
existing overlay, and a rebindable hotkey set. **Reuse, do not rebuild:** `HotkeyThread`
(`sotto_webview.py:1182`), `RegisterHotKey` (`:1202`), `arm_hotkey` (`:1985`),
`warn_hotkey_unavailable` (`:1950`).

**Gate (must exit 0):**
```powershell
python _main/oracles/osd-oracle.py --assert-metrics fps,frametime,gpu,cpu,vram --assert-no-encode-stall
if ($LASTEXITCODE -ne 0) { exit 1 }
```
**Negative arm (must exit NON-ZERO):**
```powershell
python _main/oracles/osd-oracle.py --arm=blocking-overlay --assert-no-encode-stall
if ($LASTEXITCODE -ne 0) { exit 0 } else { Write-Error "GATE CANNOT GO RED"; exit 1 }
```
The arm paints the OSD on the capture thread and must visibly stall NVENC, making the oracle fail
its no-stall assertion — i.e. this negative arm must produce a NON-ZERO from the oracle, and the
wrapper must then exit 0.

---

### Phase 6 — HIGHLIGHTS, FILTERS, STREAMING (F10, F11)

**Do:** auto-detect moments, game-level filters, and push the existing pipeline to RTMP.
**Reuse:** the event detector behind `no-speech-in-capture` / `device-rotated` is a working
trigger vocabulary over live audio — it becomes the audio track of a highlights system.

**Gate (must exit 0):**
```powershell
python _main/oracles/highlights-stream-oracle.py --require-clip --require-rtmp-handshake
if ($LASTEXITCODE -ne 0) { exit 1 }
```
**Negative arm (must exit NON-ZERO):**
```powershell
python _main/oracles/highlights-stream-oracle.py --require-clip --require-rtmp-handshake --arm=no-detector
if ($LASTEXITCODE -eq 0) { Write-Error "GATE CANNOT GO RED"; exit 1 }
```
Disabling the detector must yield zero auto-captured clips and a non-zero exit.

---

### Phase 7 — BROADCAST-CLASS EFFECTS (F6, F9) — **HARD-BLOCKED BY B3, flagged not glossed**

Background removal, eye contact, auto-frame, Freestyle-class RTX filters.

**These cannot be built properly on this host.** `nvcc` is ABSENT (B3), and there is no segmentation
model in `worker/models/` (9 dirs, all ASR/LLM). Shipping these honestly means either (a) shipping
NVIDIA's own Broadcast binary as an external dependency, or (b) shipping an `ffmpeg`-level
approximation and **labelling it as not-ShadowPlay-equivalent**. Do not let this phase block 0–6.

**Gate — only meaningful as an honesty check:**
```powershell
python _main/oracles/effects-capability-oracle.py --assert-labelled-degraded
if ($LASTEXITCODE -ne 0) { exit 1 }
```
**Negative arm (must exit NON-ZERO):**
```powershell
python _main/oracles/effects-capability-oracle.py --assert-labelled-degraded --arm=claim-parity
if ($LASTEXITCODE -eq 0) { Write-Error "GATE CANNOT GO RED"; exit 1 }
```
The arm claims parity it does not have; the oracle must exit non-zero.

---

### Phase 8 — FRONTEND (LAST) — `app/panel/`

Only now does panel work begin: replay library, timeline trimming UI, settings, F7/F8 surfaces.
`app/panel/panel.js` (2114 lines) is already the host and is reused, not replaced.

**Gate (must exit 0):**
```powershell
python _main/oracles/panel-trim-oracle.py --require-scrub --require-export --assert-reel-decode-fps 0
if ($LASTEXITCODE -ne 0) { exit 1 }
```
**Negative arm (must exit NON-ZERO):**
```powershell
python _main/oracles/panel-trim-oracle.py --require-scrub --require-export --arm=decode-during-reel
if ($LASTEXITCODE -eq 0) { Write-Error "GATE CANNOT GO RED"; exit 1 }
```
Decoding in the UI thread must drop measured reel FPS to 0 and fail the assertion.

---

### Order at a glance

| Phase | Closes | Depends on | Hardware |
|---|---|---|---|
| 0 | deciding unknown (B1) | — | **may be blocked** |
| 1 | F2 ring+NVENC | 0 | **green expected** |
| 2 | F1, F7 | 1 | green |
| 3 | F12 | — | green |
| 4 | F3, F4, F5 | 1 | green |
| 5 | F8, F13 | 1 | green |
| 6 | F10, F11 | 1, 3 | green |
| 7 | F6, F9 | 0 | **B3 — blocked** |
| 8 | frontend | 2, 4, 5 | green |

---

## 5. THE TOP 3 RISKS THAT WOULD SINK THIS

### R1 — There is no usable live capture source on this box (B1)
The whole product is a function of frames arriving. `_moved/aireplay` spent an entire delivery on
everything *except* the one component that produced nothing.
**Early detection:** Phase 0's gate, run **first and alone**, with the ladder reported rung by rung.
Deadline signal: if no rung answers within Phase 0, the project has no Phase 1.

### R2 — The NVENC/ring path is tuned to a source that does not exist
Everything downstream is built against assumed frame timing from a capture path that has never
worked here. A ring buffer tuned to phantom fps will pass a synthetic test and fail live.
**Early detection:** Phase 1's gate must run its 30 s window against the **real Phase 0 source**,
and record source-fps vs encode-fps. A gate that passes only on synthetic frames is a false green —
the receipt must state which source produced the frames.

### R3 — The prior delivery's failure mode repeats: a C++ kernel that cannot be built (B2)
The instinct on a blocked capture path is to drop to C++ for D3D11/NVENC. This host has no MSVC.
`_moved/aireplay` already walked this road and recorded the wreckage (`chain.py:221`).
**Early detection:** Phase 0's ladder must be written and **compiled** in Python+FFmpeg first; if a
lane proposes `.cpp`, the gate from Phase 1 onward (`--require-codec h264_nvenc` via FFmpeg) is
what refuses it. Add a standing rule: **no `.cpp` in Phases 0–6.**

---

## 6. LAWS (do not re-litigate without a measurement that contradicts one)

1. **Re-measure, don't cite.** `HANDOVER.md:4-6` says so about itself. Phase 0 re-proves B1.
2. **No `git add -A`.** This lane committed one explicit path and nothing else.
3. **Never modify `H:\sotto`.** This lane reads it and works in its own worktree only.
4. **A gate that cannot go RED is not a gate.** Every phase carries a negative arm; run both.
5. **Frontend LAST is a hard rule**, not a preference — Phase 8 is the only panel phase.
6. **No CUDA means no NVENC** is **FALSE** on this host (§0.1). Do not re-open it without a
   measurement.
7. **A silent loopback is usually correct** (`AGENTS.md:27-49`) — routing, not a regression.
8. **No `.cpp` in Phases 0–6** — no MSVC (B2).

---

*Every line number above was re-grepped on 2026-10-07 against the shipped tree. Where a document
disagreed with the code, the code won and the disagreement is recorded in §0.2 / §0.3.*