# SOTTO — THE CONCRETE ROADMAP (one app, replay + memory, frontend LAST)

Written 2026-10-07, after the move of `H:\aireplay` into this workspace.
**Product name: SOTTO.** `H:\aireplay` is only a legacy folder name (a junction now).

The owner asked, in order: *research first, then a concrete roadmap, then keep
building until the app is finished, frontend last, one app only.* This file is the
"concrete roadmap" half. Everything in it is built on numbers that were **MEASURED
on this box**; where that is not true it says UNKNOWN.

---

## 0. WHAT CHANGED TODAY (the facts that reset the plan)

Three beliefs in circulation were **false**, and all three were blocking work:

| Believed | MEASURED | Consequence |
|---|---|---|
| "Tauri/Rust is abandoned on this host — cargo hangs on crates.io" | `cargo 1.97.1` runs: `cargo generate-lockfile` → **rc=0**, "Updating crates.io index", 7 packages locked. **1896 crates already vendored** in `H:\cargo\registry`. | **Rust/Tauri is back ON the table.** The whole final stack is Tauri 2 + Rust. This belief would have killed it. |
| "an independent driver solves the stale-cron problem" | the driver was **built** — and it has **never worked**: every pass is `rc=2` in ~1 s, `mcode exec failed: A prompt, --input -, or at least one --file is required.` (see B1, §4) | The independent driver is necessary but **not sufficient**. A driver that fires on time and produces nothing is worse than no driver, because it looks like progress. Fix = step 1 of §2b. |

**The move** (`H:\aireplay` → `H:\sotto\_moved\aireplay`, 6678 files) is done and
reversible: `H:\aireplay` is now a **junction** back to it, so every absolute path
in the 13 existing receipts still resolves. Rollback = one rename.

---

## 1. WHERE THE BUILD STANDS (measured, not asserted)

| subsystem | state today | evidence |
|---|---|---|
| **Capture** (D3D11→NVENC→ring) | **C++ written** (`src/capture/`, 18 files). NVENC opens + initialises; 10 sessions held, #11 refuses status **21**. | `docs/research/03-nvenc-sessions.md` |
| **ASR** | **Python written + reproduced** (`src/asr/`, 10 modules). int8 ONNX Parakeet. Byte-identical to the oracle, EN 130/130 + PT 159/159. | `receipts/receipt-02-asr-impl.md` |
| **Index** | **Design measured, no code.** numpy brute force, 206 MiB, **16 ms/query exact**, 3-channel RRF. | `docs/research/07-index-search.md` |
| **Embeddings** | **Decision made, runtime open.** `google/embeddinggemma-2`, ONE 768-d vector per call. | `docs/research/06-embeddings.md` |
| **OCR** | Researched (lane 02), no code. | `docs/research/02-ocr.md` |
| **Library import** | Researched (lane 08), no code. | `docs/research/08-import-library.md` |
| **UI / panel** | The WebView2 panel already exists in `H:\sotto\app\panel` (5 themes, hot reload proven). | `H:\sotto\receipts\` |
| **Tauri shell** | `app/src-tauri/` exists with real Rust (`main.rs`, `commands.rs`, `memory.rs`, `geometry.rs`) — and Rust now builds. | this file |

**The gap is not research. The gap is integration.** Four subsystems are measured
or written; none of them are wired into one process that runs together.

### 0b. FOUR BLOCKERS FOUND BY MEASUREMENT ON 2026-10-07 (they outrank P0–P3)

None of these were on the previous roadmap. Each was measured, not inferred.

| # | blocker | MEASURED how | why it stops work |
|---|---|---|---|
| **B1** | **The heartbeat driver has NEVER done work.** Every pass dies in ~1 s with `rc=2`, `mcode exec failed: A prompt, --input -, or at least one --file is required.` | `_main\heartbeat.log` (11:27:42, 11:29:02 both `rc=2`) + the 76 B `.stderr` beside each run | The task `SottoReplayHeartbeat` fires on time (NextRunTime 11:38:00) and produces nothing. The owner's "keep going every 3 min" ask is **armed but dead**. `--file` only *attaches* a file; it is not a prompt. |
| **B2** | **The product tree is UNTRACKED in git.** 671 untracked files under `_moved/aireplay`; `git ls-files _moved` = **0**. | lane 02 `_main\lane02-durability.json` | `git clean -fd` would remove **412 paths** — the entire product. No rollback exists. This is the same durability hole the house already paid for once. |
| **B3** | **Worktrees cannot see the product.** All 7 worktrees report `sees_product=False`. | lane 02, same file | A lane dispatched into a worktree sees `AGENTS.md` and 10 sibling entries, and **no `docs/`, no `specs/`, no `src/`**. Worktree isolation is only safe AFTER B2 is fixed. |
| **B4** | **The embedding measurement cannot run: no weights on disk.** `models\` holds only `parakeet-tdt-0.6b-v3-onnx` (670 622 916 B) and `.hf-home` (113 798 B). | `Get-ChildItem models -Directory` with per-dir byte sums | P1's falsifier needs a ~1.5 GB download. **That is the owner's call, not ours** — do not start it silently. |

**B1 and B2 are the first two executable steps of this roadmap.**

---

## 2. THE ORDER (frontend LAST is a hard rule, not a preference)

    P0  INTEGRATE      one process, four subsystems, no UI work
    P1  CLOSE THE GAPS the two UNKNOWNs that decide the architecture
    P2  ONE APP        the shell, the search, the memory
    P3  FRONTEND       the panel, last, against a real backend

### P0 — INTEGRATE

**P0.0 comes first and is NOT optional — it is B1 and B2 above. Integration into a
tree that `git clean` can delete, driven by a driver that never runs, is not work.**
**B1 and B2 are DONE as of 2026-10-07** (see §0c below).

### 0c. B1 AND B2 RESOLVED — 2026-10-07 (measured, not asserted)

**B2 (durability) — FIXED, commit `a66da94`.** Re-measured after the commit:

| measure | before | after |
|---|---|---|
| `git ls-files _moved` | **0** | **328** |
| untracked entries under `_moved` | 679 | 1 |
| `git clean -nd _moved` would remove | **419 paths** | **2** (the heartbeat lock + lockfile) |

The 2 remaining paths are the live lock handle and its transient — by design, they
are recreated every pass and hold no work. Staging bar measured before committing:
**291 files, 0 with deletions (pure additions), largest file 1.80 MB** — no model
weights, no multi-GB blobs. The `_main/` oracle sources are deliberately tracked:
they are how every claim here gets falsified.

**B1 (the heartbeat) — FIXED, and the lane's diagnosis was WRONG in a way that
matters.** The roadmap's B1 said the fix was "pass the prompt positionally, because
`--file` only attaches". That is **not what was wrong**, and following it would
have been a fix for a cause that does not exist. The measured truth is three
separate faults, found by firing it and reading the real stderr each time:

| # | symptom | real cause | fix |
|---|---|---|---|
| 1 | `%1 não é um aplicativo Win32 válido` | `mcode` resolves to **three** things on PATH; `Start-Process` grabbed the extensionless shell script | use `H:\env\npm-global\mcode.cmd` by absolute native path |
| 2 | `rc=2  A prompt, --input -, or at least one --file is required` | flags were passed with no prompt text | `--file $promptFile` |
| 3 | `rc=4  Session already has an active Turn` | the heartbeat targeted the **owner's live session** — he is talking in it, so this could *never* work | give the heartbeat **its own session** via `--cwd`, never name the owner's session id |

**Proof it now does real work** (not merely "rc=0"): pass PID 24360 ran from
11:29:15 with **33.2 s of CPU**, held the exclusive lock the whole time, and
independently compiled `_main\wgc-probe.exe` (303 093 B, 11:31:27) — a pass
doing capture research on its own initiative.

**The lock is proven, not assumed.** `_hb-lock-selftest.ps1` → **rc=0, 8 arms,
both colours**. ARM-D is the real one: the old `New-Item -ItemType Directory -Force`
mutex **fails to exclude** (it succeeds against an existing directory), which is
why the first driver would have let two passes overlap. The working mutex is an
exclusive `FileStream` with `FileShare::None`, which also means a killed pass drops
its own lock and there is no stale-lock sweep to get wrong.

**B3 (worktrees could not see the product) — FIXED.** MEASURED before: a lane
worktree reported `Test-Path _moved\aireplay\specs` → **False**, i.e. a dispatched
lane would have seen `AGENTS.md` and nothing else. All four lanes
(`EmbedRuntime`, `IndexImpl`, `OcrImpl`, `EngineProc`) were fast-forwarded
`a3c288f → a66da94` and now report `sees_product=True`.
**Worktree isolation is only safe AFTER B2 — a lane in a worktree that cannot see
the product is not isolated, it is blind.**

**B4 (the embedding benchmark cannot run) — CONFIRMED, and it is the OWNER's call.**
MEASURED: `models/` holds only `parakeet-tdt-0.6b-v3-onnx` (670 622 916 B) and
`.hf-home` (113 798 B). **No embedding weights on disk.** The 768d-vs-256d recall
falsifier in P1 needs a ~1.5 GB download. **Do not start it silently — that
decision is the owner's.** The index can be built and shipped at 768d in the
meantime; the choice is only about whether 256d is acceptable.



**P0 SCOPE CORRECTED 2026-10-07 by the refute pass.** This section originally
read "wire four subsystems together — no new features". Measurement says two of
the four are missing **features**, not glue:

> - **No hotkey exists.** `Select-String` for `RegisterHotKey|GetAsyncKeyState|
>   WM_HOTKEY|SetWindowsHookEx|GetKeyState|VK_` across **ALL** of
>   `src/capture/*.cpp|*.h` → **0 hits**. The cut is *time-triggered*
>   (`cfg.cut_at_s`). **The "instant replay" trigger — the product's whole promise
>   — does not exist.**
> - **No audio exists.** `ffprobe -select_streams a` on **8** clips (3.0 s–30.0 s,
>   the largest 165 MB) → **8/8 `AUDIO=NONE`**, h264 video-only. ASR meanwhile is
>   file-fed (`transcribe.py --wav`, required). *Nothing is ever spoken into the
>   index.*
> - **`src/index/` is EMPTY**; there is **no SQLite anywhere** in `src/`.
> - **`memory.rs` is not a memory index** — it is a `GetProcessMemoryInfo`
>   working-set probe, and `commands.rs` returns a hardcoded `active:false,
>   source:"m0-no-capture"`. The Tauri shell is an M0 mock.
>
> Both hotkey and audio claims were **re-measured on the whole population**, not on
> the single grep and single ffprobe the audit lane used — see
> `receipts/receipt-13-refute-integration-audit.md`.

So P0 is **one vertical slice that creates the two missing capabilities**:

1. **`stdin` → cut.** `{"cmd":"cut"}` on the capture process's stdin is the
   smallest change that turns a time-triggered cut into real instant replay. The
   capture binary has **no stdin reader today**, so this IS the seam.
   *Acceptance that can go RED:* press the key during a live 1080p60 encode →
   clip on disk in < 1 s (`specs/01` S1 target), **zero** `ring_dropped`
   (`ring_buffer.h:9-11`), and the clip decodes clean via `ffmpeg -f null -`.
2. **WASAPI loopback → muxed audio.** Capture must carry system audio beside the
   video, resampled to 16 kHz mono. **The machinery already exists and is proven
   in this repo's own tree:** `H:\sotto\worker\wasapi_loopback.py` + the device
   ladder (`sotto_worker.py:942-1088`) + `resample_to_16k` (`:1090`). **Reuse it,
   do not rebuild it.**
   *Acceptance that can go RED:* one capture whose clip `ffprobe` reports a stream
   with `codec_type=audio`, with ASR text over that same audio.
3. **One Engine process that is the PARENT**, UI as a reconnectable child — so the
   UI dying can never stop recording. IPC = **JSON Lines over stdin/stdout**, since
   that exact bridge is already hardened in production here (`sotto_worker.py:374-377`
   `emit()`, consumed by `sotto_webview.py:5964-5975` with a watchdog).
4. **One SQLite file** (`research 07` schema) — the durable spine. It exists
   because identity is `content_key`, which a message-passing engine cannot express.
5. **Ring budget from measured hardware** (law 7) and **no encoder → no armed key**
   (law 6) — both already implemented in `selftest.cpp:63`; keep them.
6. **Both-colour gate on every claim** — an instrument that cannot say NO is worthless.

### P1 — CLOSE THE DECIDING UNKNOWNS

1. **Embedding runtime** — pin a newer `transformers`, or use llama.cpp's merged
   mmproj path. **This is the biggest unknown and it decides the index build.**
   **BLOCKED ON B4: there are no embedding weights on this box, and the download
   (~1.5 GB) is the owner's call. Do not start it without asking him.**
2. **The embeddings benchmark with its falsifier** — 200 s of the owner's own
   footage → 5 s windows → peak RSS/VRAM/s-per-window and **recall@5 at 768d vs
   256d**. *If 256d video recall is unusable, the answer is 768d — not a different
   model.* Same blocker as above.
3. **OCR recall on real screen text** (lane 02 measured only some paths).
4. **Tauri build on this host, for real** — the belief is dead, but a belief is not
   a build. `cargo build` in `H:\sotto\app\src-tauri` must produce a binary before
   P2 claims Tauri.

### P2 — ONE APP
Search (3-channel RRF + FTS5), the memory panel, the library import, the ring, all
behind the engine. Proven modules are **copied with sha256 at copy time** so later
divergence is detectable, not discovered.

### P3 — FRONTEND, LAST
The panel exists (`H:\sotto\app\panel`, 5 themes). It is wired **after** P0–P2 are
measured and running. Budget the owner's box: **150–300 MB acceptable; 800 MB–1.5 GB
investigate aggressively.** Do the benchmark early in P3, not at the end.

---

## 2b. THE NEXT THREE EXECUTABLE STEPS (each with a test that can go RED)

| # | step | acceptance — and how it goes RED |
|---|---|---|
| **1** | Fix `heartbeat.ps1`'s `mcode exec` call (prompt as positional arg, not `--file`). | GREEN = a pass writes a **non-empty** `heartbeat-run-*.md` and rc=0. RED = empty output file or rc≠0. **Both colours:** ARM-A points `--file`/prompt at a non-existent path and MUST return rc≠0 with a non-empty `.stderr`. |
| **2** | `git add` the product tree **by explicit path** (never `-A`), then commit. | GREEN = `git ls-files _moved` > 0 **and** `git clean -nd _moved` reports 0 paths. RED = either still 0 tracked, or `clean -nd` still lists paths. Re-run lane 02 — it is the instrument for exactly this claim. |
| **3** | Write `specs/04-index-search.md` from `docs/research/07-index-search.md` (design already measured; this is transcription, not invention). | GREEN = the spec carries the 6 tables, the RRF weights `{speech 1.0, ocr 1.0, visual 0.7}`, `k=100`, and every number tagged MEASURED/READ/UNKNOWN with its source line. RED = an untagged number, or a missing table. Lane 01 prints the facts; a doc-lint checks the tagging. |

**Step 3 is gated on step 2 only for durability, not for content** — the spec can be
written while the tree is still untracked, but it must not be *committed* until then.

## 2c. WHAT IS BLOCKED ON A DECISION THAT IS NOT MINE

- **Downloading `google/embeddinggemma-2` (~1.5 GB)** — P1's falsifier cannot run
  without it. Owner call. See B4.
- **`git add` of the product tree** — reversible, but it changes the repo's shape
  and the tree is 671 files. I did not do it unilaterally; it is step 2 above and
  should be confirmed before a lane runs it.

---

## 3. THE LAWS (do not re-litigate without a measurement that contradicts one)

1. **CAPTURE NEVER WAITS FOR AI.** Bounded queues, drop-with-a-counter, never block.
2. **THE CLIP IS ALREADY WRITTEN WHEN THE KEY IS PRESSED.** The ring is the guarantee.
3. **LOCAL-FIRST, NO CLOUD.** No content telemetry.
4. **THE INDEX IS TINY NEXT TO THE VIDEO.** Never store frames; never a second copy.
5. **LIGHT ENOUGH FOR MANY USERS.** Heaviest work happens when the user is NOT playing.
6. **NO ENCODER → NO ARMED KEY**, and a loud reason. Adopt for every subsystem.
7. **THE RING IS BUDGETED BY MEASURED HARDWARE**, not taste.
8. **THE OWNER'S MACHINE OUTRANKS OUR THROUGHPUT.** Our lanes measure at ≤2 threads.
   (The product's engine is the exception — it wants the measured knee, 4.)

---

## 4. HOW THE WORK CONTINUES

`_main\heartbeat.ps1` fires every 3 minutes via the Windows task
`SottoReplayHeartbeat` (MEASURED `NextRunTime 11:38:00`, task state `Running`). It
takes an **exclusive FileStream lock** so two passes can never overlap, it gets its
own session, and it writes every pass to `_main\heartbeat-run-*.md`.

**BUT — MEASURED 2026-10-07: the driver is armed and dead.** Three consecutive
passes returned `rc=2` in about one second, each with the same 76-byte stderr:

    mcode exec failed: A prompt, --input -, or at least one --file is required.

`mcode exec --help` (READ) shows `--file <path>` is **"attach a file"** — an
attachment, not a prompt. The driver passes flags and a `--file` and no prompt, so
every pass fails before the model is ever reached. **The owner's "every 3 minutes,
keep going" ask is therefore NOT actually being met**, and it has never been met by
this driver. Fixing it is step 1 of §2b. Until then, treat the heartbeat as **not a
progress mechanism**.

**Every pass: research first (MEASURED / READ / UNKNOWN, with the command), roadmap
before building, frontend last, one app.** A pass that cannot progress must name the
blocker rather than fake motion.

## 5. THE ORACLES THAT GUARD THIS ROADMAP

Both live in `_main\`, both ship **both colours**, both were RED on first run — on
bugs in their own author, which is the point.

| oracle | what it proves | both colours |
|---|---|---|
| `_lane02-durability-oracle.ps1` | the product tree is tracked, worktrees can see it, `clean -nd` is empty | ARM-0 real path GREEN · ARM-A non-existent path RED |
| `_lane01-index-spec-inputs.py` | `docs/research/07-index-search.md` still carries the schema, the three channels, and UNKNOWN markers | ARM-0 real doc GREEN · ARM-A copy with the ```sql fence stripped and OCR renamed RED |

Both write a JSON verdict and return **non-zero when the oracle itself is broken** —
a failure can never answer as success. Lane 01 also re-hashes its input and asserts
the source is unchanged, so a lane cannot silently rewrite the research it reads.
