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

### P0 — INTEGRATE (no new features; make what exists run together)

**P0.0 comes first and is NOT optional — it is B1 and B2 above. Integration into a
tree that `git clean` can delete, driven by a driver that never runs, is not work.**

1. **Fix the heartbeat invocation (B1).** `mcode exec` needs the prompt as a
   *positional argument* or `--input -`; `--file` only attaches. One-line fix, then
   re-arm. **Acceptance that can go RED:** a pass whose `heartbeat-run-*.md` is
   **empty** and whose rc≠0 is a FAILURE, and the ARM-B arm (prompt path pointed at
   a non-existent file) must produce rc≠0 and a non-empty `.stderr`.
2. **Commit the product tree (B2).** `git ls-files _moved` must go 0 → >0 and the
   `git clean -nd _moved` count must drop to 0. **Never `git add -A`** — stage the
   tree by explicit path, and never `checkout`/`reset` over uncommitted work.
3. **One Memory Engine process** that owns capture + ASR + index, independent of
   the UI (law: if the UI dies, recording continues). Tauri is a *bridge* only —
   never the realtime scheduler, never capture inside a Tauri command.
4. **Wire the replay hotkey to a real encoder init.** Law 6: no encoder → the key
   is NOT armed, and the reason is said out loud.
5. **One SQLite file** (`schema` in research 07) holding video/segment/transcript/
   ocr/embedding/marker. Live clips and the imported library are the SAME table —
   the difference is the producer, never the table. Lane 01 confirms the schema is
   already fully specified in `docs/research/07-index-search.md:33-43`: `video`,
   `segment`, `transcript`, `ocr`, `embedding`, `marker`. **Spec 04 is therefore a
   TRANSCRIPTION job, not a design job.**
6. **Ring budget from measured hardware** (law 7): 120 s = 572 MiB @1080p60,
   **1 431 MiB @4K60/100 Mbps, 2 861 MiB @4K60/200 Mbps**. The product must *say*
   what it chose and why.
7. **Both-colour gate on every claim** — an instrument that cannot say NO is
   worthless; each ships the pass AND a deliberately-broken arm that must go RED.

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
