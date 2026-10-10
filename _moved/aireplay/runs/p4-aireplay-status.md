# P4 — AIREPLAY PROJECT STATUS

**Date:** 2026-10-08 ~21:39 BRT
**Lane:** aireplay (inspection)
**Owner:** absent (11 prompts)

---

## 1. CURRENT STATE

### 1.1 Project Identity

| field | value |
|---|---|
| Product name | **SOTTO** (owner decision 2026-10-07) |
| Folder | `H:\sotto\_moved\aireplay` (real path) |
| Junction | `H:\aireplay` → real path (for legacy absolute paths) |
| Product | Better NVIDIA ShadowPlay: instant replay + searchable memory |
| Stack | Tauri 2 + Rust shell, C++ capture, Python ASR/Index, React/TS/Tailwind UI |

### 1.2 Git State

| metric | value |
|---|---|
| Branch | `main` |
| Ahead of origin | **6 commits** |
| Last commit | `4c97e9f` 2026-10-08 04:56:19 -0300 |
| Uncommitted files | **58 modified**, many untracked |
| Uncommitted insertions | **16 788** |
| Uncommitted deletions | **6 971** |

**Recent commits (last 15):**

```
4c97e9f 2026-10-08 04:56 lane25: both colours proven on the gate
9c7719c 2026-10-08 04:56 capture: retroactive clip extraction [T-N,T]
49dbdea 2026-10-08 04:55 win: censo de janelas a 25 ms
5cd0001 2026-10-08 04:54 lane25: census POPULATION 15 sites / 3784 live source files
20358d3 2026-10-08 04:53 RETRACT: 42-100 min wake delay was artifact
a6e7b6e 2026-10-07 22:05 share: export pipeline, upload interface + YouTube client
f62d182 2026-10-07 21:51 src: instantaneo das lanes de construcao (48 ficheiros)
654e7e1 2026-10-07 21:51 receitos, especificacoes e ferramentas: 227 ficheiros
f6446dc 2026-10-07 21:34 wake: detach the exec so every 3-min tick is served
87efeaf 2026-10-07 13:47 lane25: census 18 locale-grouped format sites
9787983 2026-10-07 13:44 Close the review-on-disk debt: 25 receipts/review-*.md
d51447c 2026-10-07 13:39 RETRACT the retraction: "227835 is unlinked" is FALSE
13e4da2 2026-10-07 13:35 durability: versionar 15 receipts nunca staged
fd156a0 2026-10-07 13:34 Persist the L4 and L16 reviewer verdicts to disk
a999c49 2026-10-07 13:33 receipts/receipt-21: four reviewer corrections
```

### 1.3 Uncommitted Work (58 files)

**Source code changes (4 files, 266 insertions, 26 deletions):**

| file | change | summary |
|---|---|---|
| `src/index/highlights.py` | +109/-26 | Rise threshold logic rewritten: new `HIGH_RISE_QUIET=3.601` constant, corrected `HIGH_RISE_CEILING_SUSTAINED` from 3.02 to 3.17, `rise_threshold` moved from `DEFAULTS_CHOSEN_WITHOUT_DATA` to derived-from-measured-gap |
| `src/ui/hud-shell.py` | +155/-26 | New `apply_popup_style()` function: strips caption chrome via `GWL_STYLE` write instead of pywebview's `frameless=True` (which never completes navigation on this box) |
| `src/ui/_bisect.py` | +18 | New file (untracked) |
| `src/ui/_probe-run.py` | +10/-2 | Modifications |

**Log/receipt changes (54 files):** Mostly `_main/logs/*`, `_main/*.txt`, `_main/wgc-probe.cpp`, `control/optchat/view.txt`, `receipts/receipt-35-wake-gate-tie.md`, `_main/panel-temas-manifest.json`.

**Untracked source directories (not in git):**

| directory | files | status |
|---|---|---|
| `src/pipeline/` | 7 files (share_export, share_upload, share_metadata, share_gate, contracts, chain) | Written, gate passes, **not tracked** |
| `src/storage/` | 3 files (layout, retention) | Written, **not tracked** |
| `src/ui/` | 5+ files (hud-shell, share_dialog, hotkeys, _bisect, _probe-run) | Written, **not tracked** |
| `src/index/highlights_contract.py` | 1 file | Written, **not tracked** |
| `src/ui/_bisect/` | 4 files | Written, **not tracked** |

### 1.4 Module Inventory

| subsystem | location | state | evidence |
|---|---|---|---|
| **ASR** | `src/asr/` (10 files) | ✅ Written + parity proven | `receipt-02`, `receipt-04`, `receipt-05`, `receipt-17` |
| **Index** | `src/index/` (5 files) | ✅ Written + search proven | `receipt-06`, `receipt-07`, `receipt-08` |
| **Capture** | `src/capture/` (18 C++ files) | ⚠️ Written, NVENC proven, **WGC blocked** | `receipt-01`, `receipt-03`, `receipt-14`, `receipt-18` |
| **Engine IPC** | `src/engine/` (4 files) | ⚠️ Primitives only, no process | `json.{h,cpp}`, `queue.{h,cpp}` |
| **Share/Export** | `src/pipeline/` (7 files) | ✅ Written + gate passes | `receipt-36` |
| **Storage** | `src/storage/` (3 files) | ✅ Written | `receipt-30` |
| **UI/HUD** | `src/ui/` (5+ files) | ⚠️ Written, not integrated | `receipt-34` (untracked) |
| **Highlights** | `src/index/highlights.py` | ⚠️ Oracle passes, impl exists | `receipt-36` (untracked) |

### 1.5 Specs

| spec | size | state |
|---|---|---|
| `specs/01-capture-modes-and-scheduling.md` | 8 591 B | ✅ Tracked |
| `specs/02-asr.md` | 25 457 B | ✅ Tracked |
| `specs/03-capture-encode.md` | 22 552 B | ✅ Tracked |
| `specs/04-index-search.md` | 60 347 B | ✅ Tracked |
| `specs/05-clip-to-asr.md` | 824 B | ⚠️ Stub — **untracked** |
| `specs/06-broadcast-and-capture-card.md` | 60 096 B | ⚠️ **untracked** |
| `specs/07-engine-process.md` | 936 B | ⚠️ Stub — **untracked** |

---

## 2. PENDING WORK AND TODOS

### 2.1 BLOCKERS (outrank P0–P3)

| # | blocker | status | evidence |
|---|---|---|---|
| **B1** | **WGC `E_ACCESSDENIED`** — all capture refused since 2026-10-07 11:20 | 🔴 **OPEN** — 4 independent measurements, 5/5 refused. Policy says Allow. 3 hypotheses untested. | `HANDOVER.md` §3 |
| **B2** | **Embedding weights not on disk** — ~1.5 GB download needed | 🔴 **OPEN** — owner's call, do not start silently | `ROADMAP.md` B4 |
| **B3** | **No Engine process** — IPC primitives exist, no parent process | 🟡 **SPEC READY** — `runs/P4-aireplay-engine-process.md` | `ROADMAP.md` P0 |
| **B4** | **No audio in clips** — 8/8 clips `AUDIO=NONE` | 🔴 **OPEN** — WASAPI loopback exists, not muxed | `receipt-13` |
| **B5** | **No hotkey in shipped binary** — code exists, not in `build.cmd` | 🟡 **KNOWN** — one-line fix | `research/open-source-alternatives.md` G1 |

### 2.2 Uncommitted Work Needing Review

1. **`src/index/highlights.py`** — significant rewrite of rise threshold logic. New `HIGH_RISE_QUIET=3.601` proves rise alone doesn't separate quiet from busy. `abs_floor` is the real gate. Needs review + commit.

2. **`src/ui/hud-shell.py`** — new `apply_popup_style()` function. Works around pywebview `frameless=True` never completing navigation. Needs review + commit.

3. **`src/pipeline/` (7 files)** — share/export/upload pipeline. Gate passes (96 checks, both colours). **Not tracked in git.** Needs `git add` + commit.

4. **`src/storage/` (3 files)** — layout + retention. **Not tracked.** Needs `git add` + commit.

5. **`src/ui/` (5+ files)** — HUD shell, share dialog, hotkeys. **Not tracked.** Needs `git add` + commit.

6. **`src/index/highlights_contract.py`** — **not tracked.** Needs `git add` + commit.

7. **`specs/05`, `specs/06`, `specs/07`** — stubs or new specs. **Not tracked.** Needs `git add` + commit.

### 2.3 Specs Ready for Implementation

| spec | file | what it specifies |
|---|---|---|
| Engine process | `runs/P4-aireplay-engine-process.md` | One parent process, 4 subsystems, reconnectable UI, JSON Lines IPC |
| Clip-to-ASR | `runs/P4-aireplay-clip-to-asr.md` | Clip → audio extraction → ASR → index insertion pipeline |
| WGC unblock | `runs/P4-aireplay-wgc-unblock.md` | 3 hypotheses (integrity level, window station, service state) + RequestAccessAsync experiment |

### 2.4 Open Debts from Receipts

| debt | source | status |
|---|---|---|
| `wake-fix.py:60` docstring stale (describes old mint format) | `receipt-35` §4 | Open — code is correct, docstring is stale |
| `B5-minted-userMessageId-shape` arm red on gate | `receipt-35` §6 | Open — store has 2 historical rows, arm expects 5578 |
| `C1-task-fires-in-window` regex misses `WAKE QUEUE FAILED` lines | `receipt-35` §3 | Open — 26 lines invisible to C1 |
| `MAX = 585 s` wake latency peak (18h–20h 2026-10-07) | `receipt-36-RETRACT` | Open — real, unexplained |
| Wake path outside `heartbeat.log` | `receipt-36-RETRACT` | Open — log says "only this Windows task is still firing" |

---

## 3. RECOMMENDED NEXT STEPS

### Priority 1 — Commit the Uncommitted Work

**58 files are modified, 16 788 insertions, 6 971 deletions.** This is the most urgent pending work. The untracked source directories (`src/pipeline/`, `src/storage/`, `src/ui/`, `src/index/highlights_contract.py`) and specs (`05`, `06`, `07`) need to be tracked.

**Action:** Review the 4 modified source files, then `git add` by explicit path and commit.

### Priority 2 — WGC Unblock (B1)

The WGC `E_ACCESSDENIED` block is the #1 blocker. The investigation spec (`runs/P4-aireplay-wgc-unblock.md`) has 3 untested hypotheses:

- **H1:** Run probe as administrator → tests integrity level
- **H2:** Run probe in interactive session → tests window station/desktop
- **H3:** Check GraphicsCapture service state → tests service health
- **ARM-D:** Call `RequestAccessAsync` before `CreateForWindow` → tests if this lifts the block

**Action:** Test H1–H3 and ARM-D. If `RequestAccessAsync` fixes it, add it to `src/capture/wgc_capture.cpp`.

### Priority 3 — Engine Process (B3)

The spec is ready (`runs/P4-aireplay-engine-process.md`). The recommendation is a Python Engine with C++ capture subprocess, using JSON Lines IPC.

**Action:** Implement `src/engine/engine.py`, `src/engine/protocol.py`, `src/engine/test_engine.py`.

### Priority 4 — Clip-to-ASR Pipeline (B4)

The spec is ready (`runs/P4-aireplay-clip-to-asr.md`). The pipeline: clip → ffmpeg audio extraction → ASR → index insertion.

**Action:** Implement `src/pipeline/clip_to_asr.py` + test.

### Priority 5 — Wire Hotkey into Build (B5)

`src/capture/trigger.cpp` has `RegisterHotKey` at line 163 and `WM_HOTKEY` pump at line 292. It's missing a line in `build.cmd`.

**Action:** Add trigger selftest to `build.cmd`.

### Priority 6 — Audio Muxing (B4)

8/8 clips have `AUDIO=NONE`. WASAPI loopback exists (`src/capture/wasapi_audio.cpp`, 47 739 B). The muxer (`src/capture/mp4_writer.cpp`) needs an AAC audio stream alongside H.264.

**Action:** Add audio stream to muxer, resampled to 16 kHz mono.

---

## 4. PROVENANCE

| claim | source | date |
|---|---|---|
| Git state | `git log`, `git status`, `git diff --stat` | 2026-10-08 |
| WGC block | `HANDOVER.md` §3 | 2026-10-07 |
| Roadmap/blockers | `ROADMAP.md` | 2026-10-07 |
| Uncommitted changes | `git diff --stat` | 2026-10-08 |
| Specs ready | `runs/P4-aireplay-*.md` | 2026-10-07/08 |
| Receipt debts | `receipts/receipt-35`, `receipt-36-RETRACT` | 2026-10-07/08 |
| Module inventory | `HANDOVER.md` §1 | 2026-10-07 |
