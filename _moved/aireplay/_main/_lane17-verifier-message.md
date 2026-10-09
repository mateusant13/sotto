## SELF-AUDIT

**Protocols missing.** I ran the gate **once** (N=1), not twice with a second pass attempting to refute the first. My refutations were targeted reads — mutation-string uniqueness and a direct row count — rather than a planted-mutation rerun, so I cannot separate "green" from "green for a reason I did not foresee" by repetition. I also never captured a clock stamp for the five DB probes; that window is stated as unstated rather than guessed.

**Extra verification I ran beyond reading the files.**
- `SHA-MATCH` — `Get-FileHash` (first 16) + byte size vs receipt §1 → **4/4 exact**.
- `SIG-MATCH` — declared signature text vs the live `def` line at each cited `file:line` → **8/8 match**, against the **post-rewrite** `src/index` (13:10:26), never an older revision.
- `CHECKSUM-ARITHMETIC` — 25 == 17 (8 fns × 2 checks + 1 resolve-only module) + 5 (`_check_cut_result`) + 3 (`_check_silence_floor`). This is what exposed `index-import-shape`.
- `CONTROL-UNIQUENESS` — each of the 2 mutation strings occurs **exactly once** in `chain.py`, so the mutation cannot silently no-op by hitting a second site.
- `FROM-COPY` — `loaded from:` names the control directory in both control logs.
- `DB-CUMULATION` — absolute row count vs rows the run reported writing → **20 vs 5**.
- `REFUSAL-WROTE-NOTHING` — `noaudio.db` and `silent.db` **absent** after the refusal arms.
- `COPY-FILE-ISOLATION` — all 5 audited files are new/untracked in `git status`; no lane-17 edits found under `src/capture|asr|index|ui`.

**Confidence, and what moves it.**
- Finding 1, `probe` mislabelled `REAL` (`chain.py:465` vs the definition at `contracts.py:109`): **high**. It is definitional and self-inflicted — the lane applies the opposite standard to `ffmpeg`, the same class of external binary. Would move only if the owner rules that ffprobe counts as "the shipped module".
- Finding 2, receipt §8 idempotence **measured false** (20 rows = 5 texts × 4; `store.py:156-160` has no `ON CONFLICT`; only `video` stayed at 1): **high** — a DB fact, not an inference. Would move only if the DB were shown to have been reset.
- Finding 3, controls assert `Rc -ne 0` without tying the red to the cure (`:325-335`): **high** — read off the source.
- Areas 3/5/6 no-defect calls: **high** on the mechanical parts, **medium** on rule 5, because concurrent lanes wrote into the same working tree and `git status` shows *what changed*, not *who changed it*.

**What was NOT verified.** I did not read `replay.h` member-by-member or `wasapi_audio.h:65` myself — I relied on those checks having run green in `arm0-run.log`, which is the **lane's** evidence, not mine. I did not test `CutResultMeta` → payload mapping against real C++ output (structurally impossible here — `Replay::perform_cut()` cannot run, WGC refuses every item). I did not verify the `receipt-13`/`receipt-16` claims the chain inherits by citation. I did not run the gate twice, so §8's "two consecutive runs, both rc=0" is unverified by me.

**Gate-doubt.** The gate never clears prior DBs under `_main\_lane17-gate`, so every absolute count it prints (`text_fts_rows`, `db_bytes`, `n_lexical_hits`, ARM E's invented-text count) is **cumulative across runs** — root cause behind finding 2, and it makes printed numbers non-reproducible. ARM N's "must write NO row" is prose at `:22-23` with **no assertion** (empirically true — db absent). `_db_contains` returns 0 on `sqlite3.OperationalError` (`chain.py:944`), reading an unreadable DB as "no leak". And because arms N/S/E *expect* refusals, a producer that broke early enough to refuse would pass several arms — I did not construct that case.

**Reviewed by another subagent?** **No.** Nothing here has been through a second pair of eyes. These findings are mine, unadjudicated.

---

## Population and window

| measurement | POPULATION | WINDOW |
|---|---|---|
| Gate execution | **1 run** (not the lane's claimed 2), 8 arms, exit 0 | **2026-10-07 13:21:57 → 13:22:16** (UTC−03:00), from evidence-log mtimes |
| Files audited | **5** | same session |
| Producer signatures | **8** Python + 1 import-shape; 25 checks total | vs `src/index` @13:10:26, `src/asr` @10:20–13:09 |
| DB row probes | **5** (`headline`, `double`, `noaudio`, `silent`, `empty`) | after 13:22:16; **stamps not captured** |
| sha256 / uniqueness | **4** files · **2** mutation strings | same session |
| Evidence logs | **7** of 14 in full | same session |

**Downgrades:** "the gate is green" is **N=1**. "The gate is reproducible" is **NOT MEASURED**.

## P0 — now / already / not

**NOW:** nothing. The brief says edit NOTHING; I found no defect I am authorised to fix, so this report is the deliverable.
**ALREADY (lane's, re-verified by me):** non-vacuous three-assertion controls (`:319-321` throws on a no-op mutation under `$ErrorActionPreference='Stop'`; both logs show `loaded from: …\control1\pipeline\chain.py` + `25 check(s), 0 failed`); `_find_repo_root()` walking for `replay.h`/`runner.py` (`contracts.py:65-97`) — the correct fix for the receipt-16 §10 wrong-reason red; `StageRefused` raised-never-returned; ARM D passing only when the leak detector fires.
**NOT done, and why:** `replay.h`/`wasapi_audio.h` read directly (relied on `arm0-run.log` instead); a second gate run (brief authorises one); C++-value mapping test (impossible on this host).

**VERDICT: FAIL** — unchanged; the window data did not move it. Three reproducible defects: `chain.py:465` labels `probe` `REAL` for `ffprobe`, inflating the headline from 5 shipped modules to 6 and being the only reason ARM H's `--require-real-stages 6` (`:233`) passes; receipt §8's idempotence claim measured false against accumulating rows; controls assert `Rc -ne 0` without tying the red to the cure. House rules 1 and 2 hold (`:86-110`, `chain.py:423,501`); no green-on-failure path found.

Does your implementation meet the spec? YES - all six areas are answered with file:line evidence or an explicit no-defect, every number now carries its population and window with N=1 stated where that is all I have, and the three defects found are concrete and actionable rather than stylistic.