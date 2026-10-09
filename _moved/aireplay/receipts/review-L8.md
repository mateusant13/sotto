# Review of LANE L8 — `docs/integration-sotto-app.md` + `docs/overlay-hotkey-contract.md`

> **Provenance of this file.** Written by lane *Close the review-on-disk debt for 14 lanes*
> (`mvs_54687d45969d461181c10929993039e8`) to satisfy `_main/REVIEW-MODEL.md:41` —
> control **CHK-REV-1**, *"every committed lane has receipts/review-<LANE>.md on disk"*.
> Recovered read-only from `C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite`
> (`file:…?mode=ro`), reviewer session **`mvs_a4c053f4d29045818c5298e1e36c0642`**
> (*"L8 reviewer - integration design audit"*, agent `verifier`, `session_type=branch`,
> created 12:27:13, last updated 12:50:04 BRT).
> Source rows: **`227864`** (main findings report + citation audit, 15 570 chars) ·
> **`228010`** (SELF-AUDIT, 8 497) · **`228087`** (P0 + *"Verdict unchanged"*, 6 295) ·
> **`228167`** (SELF-AUDIT, 8 607) · **`228226`** (closing P0 + POPULATION/WINDOW + SELF-AUDIT
> + verdict, 8 444).
> Recounted live, not taken from a prior lane's census: the session holds **48 message
> rows / 45 assistant**.
> **This file is a transcription, not a review.** Nothing in it was re-measured by me except
> the citation-resolution box, labelled *verified by the persisting lane*, below.

---

## ⚠ HAZARD — READ BEFORE ROUTING ANY `file:line` IN THIS FILE

*Verified by the persisting lane*, `_main/_rv-cite.py` against **`HEAD` = `13e4da225355e16c30b49722c35f5c0e665dd4a2`**
(POPULATION = every `file:line` this verdict names **inside this repo**; WINDOW = one run,
2026-10-07 ~13:40 BRT):

| cited file | lines in working tree | lines at HEAD | verdict |
|---|---|---|---|
| **`AGENTS.md`** | 483 | **405** | `:456-458` **DANGLING at HEAD** — **and the cited token is gone from the file entirely. See below.** |
| `ROADMAP.md` (repo root, **not** `_main/`) | 273 | 213 | `:42`, `:61` resolve both |
| `_main/LANE-BRIEF.md` | 144 | 143 | `:21` resolves both |
| `src/capture/trigger.cpp` | 567 | 502 | `:346` resolves both |
| `docs/integration-sotto-app.md` | 413 | 412 | resolves both |
| `docs/overlay-hotkey-contract.md` | 333 | 332 | resolves both |
| `sotto_webview.py:6395`, `sotto_webview.py:3365`, `worker/sotto_worker.py` | — | — | **CROSS-REPO** — these live in `H:\sotto\`, not here. Not resolvable by this repo's git. |

### 🔴 THE HEADLINE EVIDENCE OF THIS REVIEW IS DEAD

S5 is the review's own *"strongest part of both documents"*: **86 `BRIDGE_DEATH`s at
`AGENTS.md:456-458`, verbatim**, POPULATION 86, WINDOW one app run. That quotation is the
anchor for S1, for the load-bearing bet, and for the verdict's own first clause.

*Verified by the persisting lane* — `Select-String -Path AGENTS.md -Pattern 'BRIDGE_DEATH'`
→ **0 matches in the working tree**; `git show HEAD:AGENTS.md | Select-String 'BRIDGE_DEATH'`
→ **0 matches at HEAD**. Working-tree `AGENTS.md` line 456 is a table row about the
*verification battery* (`H:\sotto\_main\_audit-verify-all.cmd`), and line 458 is a
*Migration direction* paragraph. Neither has anything to do with the quote.

The file was rewritten: `AGENTS.md` is 39 851 B, mtime **13:14:11**, last touched by commit
`bae4e1e` (*"wake v3: repaired-row injector, self-waking loop, orchestrator mandate"*), and
lane L21 (*"L21 correct the false claims in AGENTS.md"*) is the owner that rewrote it.

**Consequence: S5 cannot be re-verified today by following the citation.** The quotation may
still be true — *I did not check whether the 86 deaths ever happened* — but this file can no
longer prove it. **Treat S5 as UNVERIFIED-AGAINST-A-DELETED-CITATION, not as refuted.**

---

## Verdict

The reviewer's own closing line, verbatim, from his **last** turn (`id 228226`):

> Does your implementation meet the spec? NO - the two documents are analytically sound and their load-bearing bet verifies exactly (86 BRIDGE_DEATHs at AGENTS.md:456), but every citation I checked into replay.{h,cpp} and trigger.{h,cpp} was wrong while every one into sotto_webview.py, ROADMAP.md and 03-engine-ipc.md was right, two gates would delete or read the wrong line and report green, §2.2/§6.1 prescribe fixes the trigger lane already shipped, and §1.4's PCM tee is specified over a channel the shell opens as DEVNULL (sotto_webview.py:6395) that the worker never reads.

The **main report** turn (`id 227864`) carries the quantified variant, which is the more useful
one and is quoted here for that reason:

> Does your implementation meet the spec? NO - the two documents are analytically sound and their load-bearing bet verifies exactly (86 BRIDGE_DEATHs at AGENTS.md:456), but 44 of 78 spot-checked line citations are wrong (56%;100% of the citations into replay.{h,cpp}, trigger.{h,cpp}), two gates would delete or read the wrong line and report green, §2.2/§6.1 prescribe fixes the trigger lane already shipped, and §1.4's PCM tee is specified over a channel the shell opens as DEVNULL (sotto_webview.py:6395) that the worker never reads (0 stdin tokens in 4593 lines).

**Three later turns also carry `## Verdict unchanged` / `## Confidence per claim` re-statements.**
There is **no bare PASS/FAIL token** in this reviewer's output; the closing line is the verdict.

---

## POPULATION and WINDOW

**The reviewer stated a POPULATION and a WINDOW, and then withdrew the headline number derived
from them.** His own table (`228226`), verbatim:

| count | POPULATION (what I enumerated) | WINDOW (when, against what) | strength |
|---|---|---|---|
| Citation targets checked | **~112** distinct file+line, hand-enumerated from my own tool output: `sotto_webview.py` 24 · `trigger.h` ~25 · `trigger.cpp` ~15 · `replay.cpp` 17 · `replay.h`+misc 15 · `03-engine-ipc.md` 8 · `ROADMAP.md` 8 | **2026-10-07 12:26–12:34 UTC-3**; `replay.*` @12:25:57–12:26:28, `trigger.*` @12:33:40–12:33:54 | **soft** — three recounts: 78, ~99, ~112 |
| Citations wrong | **~62** of those ~112 | same | **soft, same reason** |
| Error rate **by group** | `replay.{h,cpp}` + `trigger.{h,cpp}`: **~61 of 61 wrong (100%)** · `sotto_webview.py` + `ROADMAP.md` + `03-engine-ipc.md` + most misc: **~50 of 51 correct (98%)** | same | **high** — binary, reproduces across every group |
| `stdin` tokens in worker | **0** — whole file, case-insensitive | `worker/sotto_worker.py` @03:29:57, unchanged throughout | **very high** |
| `BRIDGE_DEATH`s | **86**, one app run | per `AGENTS.md:456-458` | **very high** — *see the hazard box: this citation no longer resolves* |
| L8's negative-existence claim | `receipt-15-instant-replay-trigger.md` **absent**; `receipts/` = **21 files** (L8 and the brief both say 17) | 12:30 | **high** |
| WebView2 process count | **NOT MEASURED** | — | **none — do not quote** |

**The claim he withdraws, verbatim:**

> **"56% of citations are wrong" is withdrawn.** Three reasons, each sufficient: I never
> enumerated how many citations *exist*, so there is no denominator for the document; my sample
> **over-represented** the four files L8 itself flagged as moving, biasing the rate upward; and
> my tally **moved when I recounted it**. **A number that changes on recount is not a number.**
>
> **What survives at full strength:** of the citations I checked, every one into
> `replay.{h,cpp}` and `trigger.{h,cpp}` was wrong, and every one into `sotto_webview.py`,
> `ROADMAP.md` and `03-engine-ipc.md` was right. That is a reproducible binary split.
> **The split is the finding; the percentage is not available** until `CITATION-POPULATION` is run.

**Carry the withdrawal, not the percentage.** The `56%` figure still appears in the main report
and in the verdict line; the reviewer retracted it in a later turn.

---

## Findings

Seven findings: **2 blocker, 2 major, 2 moderate, 1 minor**, plus one PASS finding (S5).

| id | severity | file:line | what was claimed | what is actually there | the fix (reviewer's words) | owning lane |
|---|---|---|---|---|---|---|
| **S1** | BLOCKER | `docs/integration-sotto-app.md:213` (§1.4 load-bearing rule `:222`, Rule C `:189`, `:151`); spawn at `sotto_webview.py:6395` | Engine → ASR audio is a **PCM tee over the child's `stdin`** | the only existing spawn passes **`stdin=subprocess.DEVNULL`**, and `worker/sotto_worker.py` — **4593 lines** — has **zero** occurrences of `stdin` (case-insensitive, full-file scan); its audio sources are `--selftest`, `--audio`, `--device`, `SOTTO_AUDIO_FILE`, `SOTTO_FILE_TAP`. **It fails silently**: with `DEVNULL` every `WriteFile` returns success and discards — 16 kHz s16le = **32 000 B/s discarded forever**, ASR hears nothing and never errors. **It also violates the doc's own Rule C** (*"no thread in the capture path may ever block on a consumer"*) within 60 lines. | *"§1.4 must state the transport that exists and is bounded — an anonymous pipe with a **fixed-size ring buffer and an explicit drop-with-counter on full**, drained by a dedicated reader thread, plus a §1.4 note that `stdin=subprocess.DEVNULL` … make 'over stdin' a *change to the worker*, not a wire format. Until the worker grows a reader, this boundary is unimplemented, and §4 step 3 as written is not executable."* | L8 + owner of `H:\sotto` worker |
| **S2** | BLOCKER | 16 `replay.*` + 4 `replay.h` citations, e.g. `replay.h:162`→**175**, `replay.cpp:171`→**195**, `:210`→**234**, `:216`→**240**, `:217-223`→**241-247**, `:466`→**496**, `:557/561/564`→**608/612/615** | the documents pin `replay.*` by **line count only** ("166 lines", "581 lines"), **no sha256** | **every single `replay.cpp`/`replay.h` citation is wrong — not one resolves** (his count: 16/16 and 4/4). The *code blocks* quoted at `:111-116` and `:127-132` are **byte-accurate** — *"the reasoning is right, the coordinates are fiction."* The fabricated numbers are **load-bearing**: §4 step 1's RED arm (*"delete `trigger.cpp:346`"*) points at a line that is now `return !quit_.load();` — **the gate would delete the wrong line and report GREEN**. | *"re-pin every `replay.*` line to the values in the table above and add the sha256/mtime columns to §0.1 … **a line-count pin cannot detect a same-length edit.**"* | L8 |
| **S3** | MAJOR | `trigger.cpp` `:21`→24, `:26`→29, `:28`→31, `:59-76`→82-124, `:65`→121, `:329-346`→440-459, `:346`→459; `trigger.h` `:79`→96, `:153`→170, `:181`→198 | the hotkey contract's `trigger.*` coordinates | **equally stale, and two now assert the opposite of the code.** §2.2 (`:84-111`) says *"F12 goes LAST. This contract contradicts the code on disk, deliberately"* and assigns L1 a hookup — **the lane already did it** (`trigger.cpp:88-105`, F12 last at `:121`). §6.1's *"CRITICAL — the poll path ignores `mods`"* is **already fixed** (`trigger.cpp:442`). Shipping either asks a lane to **re-apply a fix that landed.** | *"§2.2 and §6.1 must be rewritten as **satisfied**, citing `trigger.cpp:88-105/112-124/431-442` and `receipt-23` — except §6.1's companion claim that `kRepeatGuardNs` 'is currently unused in the poll path,' which is also now false (`trigger.cpp:382`)."* | L8 |
| **S4** | MAJOR | `docs/integration-sotto-app.md:42` (§0 V1) and `:77` (§1.2); truth at `_main/LANE-BRIEF.md:21`, `ROADMAP.md:61`/`:42` | the brief asks the two halves to *"coexist in one process"* | the string `coexist` appears in **neither** `LANE-BRIEF.md` **nor** `AGENTS.md`. The brief says only *"Everything lands in ONE app, under Sotto, frontend LAST"* — **"one app", never "one process"**. §1.2's whole argument is that the literal reading is impossible — **and the doc manufactures a stricter quote to refute.** A reader opening the brief finds no such demand. The substantive reading is **sound** (WebView2 cannot host the ring; `_gate_form_show` proves the host is out-of-process) — only the attribution is wrong. | *"§0 V1 and §1.2 must cite `LANE-BRIEF.md:21` ('ONE app') and `ROADMAP.md:61` (P0 'one process'), drop the fabricated `coexist in one process` quote, and keep the structural argument unchanged."* | L8 |
| **S5** | MODERATE — **PASS** | `AGENTS.md:456-458`; doc use at `:69-73`, `:216-220`, `:400` | 86 `BRIDGE_DEATH`s, POPULATION 86, one app run | *"**This is the strongest part of both documents.** The Engine-as-parent bet stands on verified evidence"* — `AGENTS.md:455` even names the mechanism the doc's rule-2 argument needs: *"the holder is usually ITS OWN PREDECESSOR."* One refinement: `AGENTS.md:465` records the cure (`deaths=0 restarts=0`) and **the doc never mentions the bug is already fixed**, overstating residual risk. | cite the cure too. **🔴 BUT the citation is now DEAD — see the hazard box. This finding cannot be re-verified by following it.** | L8 |
| **S6** | MODERATE | `docs/integration-sotto-app.md:246` (F5), `:44` (§0 V3), doc2 `:28`; `ROADMAP.md:32`; `_main/_lane1-trigger-gate.ps1` | *"`receipts/` holds 17 files"*; *"cited in `ROADMAP.md:32`"* | **actual 21 files** at review time. The substantive V3 claim **holds** — `receipt-15-instant-replay-trigger.md` did not exist. But **both docs' V3 are themselves now stale**: `_lane1-trigger-gate.ps1` **exists** (created ~8 min *after* the docs) and `receipt-23-trigger-defects.md` is cited by `trigger.cpp:440` but did not exist at audit time. *"This is the honest-limitation case: **correct when written, overtaken by a live lane.**"* | re-measure both counts at cite time | L8 |
| **S7** | MINOR | `docs/integration-sotto-app.md:250` → `main.cpp:367`; `:156` → `test_window.cpp:197` | `main.cpp:367` surfaces `perform_cut`'s failure via `last_cut_`; `test_window.cpp:197` shows the `WaitForSingleObjectEx` quantisation | `main.cpp:367` prints `c.ring_dropped_at_cut`; `last_cut()` is read at `main.cpp:296`. `test_window.cpp:197` is `r.note += "; produced a degenerate size…"` — **unrelated**. The S7 first claim is **true**, the citation wrong. | *"Let me `grep` for the wait to confirm where it really lives before publishing the fix."* — **he never ran it. Do not route the second half.** | L8 |

**What the lane got right** (carried because a review that lists only faults hides what it
verified): **Rule D verified independently and it holds** — `run()` is one-shot, `cut_issued`
latches at `:501` and is set only at `:592`, never reset; the cut slot is single with **no
in-flight check** against `kQueueCapacity = 8`; *"Confirmed exactly as the lane states."* V2/V4/V5
honesty is real and correctly scoped. The §0.1 sha256 pins are the right instinct.

---

## UNVERIFIABLE / do not route as fixes

1. **The 56% error rate is WITHDRAWN by the reviewer.** Quote the binary split, never the
   percentage. *(This is the exact trap the repo has already been bitten by.)*
2. **S5's citation is dead.** `BRIDGE_DEATH` = 0 matches at HEAD **and** in the working tree.
   The 86 deaths are **unverifiable-by-citation today**. This is *my* measurement, not his.
3. **S7's second half was never resolved** — he promised the `WaitForSingleObjectEx` grep and
   **never ran it**: *"**I promised it and never ran it.**"*
4. **He never built the project and never ran `_lane1-trigger-gate.ps1`** — both write
   artifacts. **Every capture-side finding is from reading, never from running.**
5. **No `git log`/`git show` archaeology** — he chose current state over history, *"cannot say
   whether L8's numbers were **ever** right."*
6. **WebView2 process count: NOT MEASURED.** *"**none — do not quote**."*
7. **No second reviewer, and he could not dispatch one** — *"this seat has no dispatch tool …
   Single-reader review of a single-writer deliverable — the weakest link in the chain."*
8. **The contradiction sweep is envelope-only** — all 9 checks hold, but *"not every downstream
   implication of `03`'s ARM list."*
9. **In-game delivery is untestable here** — `NOT MEASURED` by both documents.
10. **The trap fired during his own audit**: `trigger.cpp` moved a *third* time
    (19797 B @12:25:31 → 24123 B @12:33:40). Both trigger findings are stated against the
    12:33:40 revision only.

---

## The reviewer's own gate doubt

> **Gate-doubt:** my S3 `trigger.h` numbers need a re-pin, not adoption — applying them without a
> fresh hash would repeat the exact offence I am reporting. **My own integer instability is the
> argument against quoting any number from this report.** S1's severity turns on whether §4 step 3
> meant *"wire an existing channel"* or *"design a new one"*; I judged the former, which makes it a
> blocker, but under the latter reading it downgrades to a missing-implementation note — the
> `DEVNULL` fact survives either way. **I did not build the product:** I cannot say the code
> fails, only that these two documents misdescribe it.

And his ordering of what to do next, verbatim:

> Next actions, in order: `CITATION-POPULATION`, `STDIN-TEACHABILITY`, and a second reader on S1
> alone.

---

## SELF-AUDIT

Carried from the reviewer's own `## SELF-AUDIT` turns (`228010`, `228167`, `228226`), verbatim.

**Protocols missing:** the citation denominator · `git` archaeology · build and gate execution ·
`ffprobe`/`ffmpeg` · *"the `WaitForSingleObjectEx` grep I promised and skipped"* · process census.

**Extra verification beyond the brief:** snapshot anchor before reading, re-taken at the end
(caught the third `trigger.cpp` revision) · independent full re-read of `replay.cpp` 150-632 ·
whole-file `stdin` scan (produced S1) · quote-provenance search across three files (produced S4)
· re-measurement of L8's own negative-existence claims (produced S6) · `ring_buffer.cpp`
pin/unpin bodies read · *"and **three recounts of my own tally**."*

**New checkboxes, named and mechanical:** `CITATION-PIN-ASSERT` (red on any hashless or
line-count-only pin) · `STDIN-TEACHABILITY` (*"Currently RED on both halves"*) ·
`QUOTE-PROVENANCE` (*"Currently RED"*) · `GATE-LINE-TARGET` (*"Currently RED: deleting
`trigger.cpp:346` hits `return !quit_.load();`"*) · `CITATION-POPULATION` (*"**This replaces my
withdrawn percentage with a real one.**"*).

**Reviewed by another subagent?** *"**No.** L8 could not dispatch one (its seat had no dispatch
tool) and neither can I. Single-reader review of a single-writer deliverable — the weakest link
in the chain. If one thing gets a second pass, make it **S1**."*

**Confidence, and what moves it:** S1 0.95 · S2 0.97 · S3 0.92 — **softest**, `trigger.h` was
growing mid-audit · S4 0.90 · S5 0.98 · Rule D 0.96 · contradiction sweep 0.88 ·
**the ~46-of-~112 count: LOW, withdrawn.**

**His own form failures, reported by him:** a dropped/duplicated section across continuations,
and *"**Correction to my own body — my citation tally was an undercount**"* in `228010`.

---

## SELF-AUDIT of THIS persisting lane

**Reviewer position.** Read-only; the store was opened `mode=ro` and no byte was written to it.
I did **not** build anything, run any gate, re-read either document, or re-open a single
finding. I transcribed and I labelled.

**What I verified myself** (2 boxes, measured):

| fact | command | rc | result |
|---|---|---|---|
| `receipts/review-L8.md` did not already exist | `Test-Path` | — | **FALSE** — no overwrite risk |
| every in-repo `file:line` resolves? | `py -3 -B _main/_rv-cite.py` | 0 | **6 files: 5 resolve both; `AGENTS.md:456-458` DANGLING at HEAD** (405 lines vs 483 in tree) |
| **is the `BRIDGE_DEATH` quote still in `AGENTS.md`?** | `Select-String` in tree **and** `git show HEAD:AGENTS.md` | 0 | **0 matches in BOTH.** Tree line 456 = verification-battery row; line 458 = Migration direction |

**What I did NOT verify.**

- **Whether the 86 `BRIDGE_DEATH`s ever happened.** I proved only that the citation no longer
  resolves. *Absence of the token is not refutation of the event.*
- Whether the 44/78 / 56% citation audit still holds. It was **withdrawn by the reviewer** and
  the underlying files have moved since 12:34.
- **Whether S1's `sotto_webview.py:6395` still reads `stdin=subprocess.DEVNULL`.** That file is
  in `H:\sotto\`, outside this repo; I did not open it and it is another lane's to edit.
- Whether §2.2 / §6.1 were rewritten. I did not read either document.
- The S3 line-mapping table (14 `trigger.*` entries) — carried verbatim, **not** re-checked.

**Per-claim confidence in MY OWN contribution:** **high** that the `AGENTS.md` citation is dead
— it is a two-sided mechanical check against a named sha, and it is the single most important
thing in this file. **High** that the transcription is faithful to the store bytes. **Zero**
confidence that S1–S7 are still open; **and zero** confidence that S5 is still verifiable.