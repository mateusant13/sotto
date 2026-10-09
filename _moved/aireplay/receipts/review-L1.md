# Review of LANE L1 — `src/capture/trigger.{h,cpp}`: the instant-replay hotkey

> **Provenance of this file.** Written by lane *Close the review-on-disk debt for 14 lanes*
> (`mvs_54687d45969d461181c10929993039e8`) to satisfy `_main/REVIEW-MODEL.md:41` —
> control **CHK-REV-1**, *"every committed lane has receipts/review-<LANE>.md on disk"*.
> Recovered read-only from `C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite`
> (`file:…?mode=ro`), reviewer session **`mvs_36edbf94c94f45f3975623c86322e66f`**
> (*"L1 reviewer - instant replay trigger audit"*, agent `verifier`, `session_type=branch`,
> created 12:49:47, last updated 13:01:05 BRT).
> Source rows: **`local_runtime_message_rows.id = 229300`** (main findings report,
> `msg_content` 17 478 chars) · **`229489`** (per-claim POPULATION/WINDOW census, 7 439) ·
> **`229562`** (SELF-AUDIT, 7 350) · **`229649`** (closing report, 5 884).
> Recounted live, not taken from a prior lane's census: the session holds **22 message
> rows / 20 assistant**.
> **This file is a transcription, not a review.** Nothing in it was re-measured by me except
> the citation-resolution box, labelled *verified by the persisting lane*, below.

---

## ⚠ HAZARD — READ BEFORE ROUTING ANY `file:line` IN THIS FILE

*Verified by the persisting lane*, `_main/_rv-cite.py` against **`HEAD` = `13e4da225355e16c30b49722c35f5c0e665dd4a2`**
(POPULATION = every distinct `file:line` the verdict names; WINDOW = one run, 2026-10-07 ~13:40 BRT):

| cited file | lines in working tree | lines at HEAD | verdict |
|---|---|---|---|
| `src/capture/trigger.cpp` | 567 | **502** | `:505`, `:523`, `:554` **DANGLING at HEAD**; ok in working tree |
| `src/capture/trigger.h` | 272 | 245 | resolves both |
| `src/capture/trigger_selftest.cpp` | 370 | 366 | resolves both |
| `src/capture/build.cmd` | 15 | 14 | `:12` resolves both |
| `src/capture/replay.cpp` | 645 | 632 | resolves both |
| `src/capture/main.cpp` | 621 | 413 | resolves both |
| `receipts/receipt-15-instant-replay-trigger.md` | 199 | **198** | `:199` **DANGLING at HEAD** |
| `_main/_lane1-trigger-gate.ps1` | 211 | **146** | `:150`, `:152`, `:157`, `:166` **DANGLING at HEAD** |
| `_main/_lane23-trigger-defects-gate.ps1` | 239 | **absent** | **NOT IN `HEAD`** — untracked file, ok in working tree |
| `_main/logs/lane1/lane1-trigger-gate.txt` | 23 | **absent** | **NOT IN `HEAD`** — a log, never committed |

The reviewer's own revision pin (`trigger.cpp` sha256 `241A9BF08D8951AF…`, 24 193 B, mtime
12:43:20) sits between those two bases. **Every citation above is exact against the bytes he
read; none of them is exact against `HEAD`.** Three consequences:

1. **Do not route F4's `arm_summary()` fix at HEAD.** `trigger.cpp:505-523` and `:554` do not
   exist in the committed file — the file has grown 65 lines since.
2. **`_lane23-trigger-defects-gate.ps1` was never committed at all.** The control-arm evidence
   the reviewer quotes as *the* strongest part of his report rests on a file that exists only in
   this working tree. It can be lost by a clean checkout.
3. **`receipt-15` is mid-write** by another lane (working tree 199 lines vs 198 at HEAD). Its
   line numbers are moving under the citation. I did not edit it.

---

## Verdict

The reviewer's own closing line, verbatim, from his **last** turn (`id 229649`):

> Does your implementation meet the spec? NO - the trigger is correctly written, honestly gated with two genuine control arms (N=1 each) and exemplary measurement discipline, but it emits two CutRequests per physical press on every binding that registers - 6 of 9 on this host - because both paths are armed with no cross-path dedup and no arm exercises both paths at once, leaving that finding at population 0 and unmeasured by any run; and receipt-15 §6's hookup cannot link because `build.cmd:12` never compiles `trigger.cpp`.

The **main report** turn (`id 229300`) closes with a near-identical variant, quoted because the
difference is itself evidence:

> Does your implementation meet the spec? NO - the trigger is correctly written, honestly gated with two genuine control arms and exemplary measurement discipline, but it emits two CutRequests per physical press on every binding that registers (6 of 9 on this host) because both paths are armed with no cross-path dedup and no arm exercises both paths at once; and receipt-15 §6's hookup cannot link because `build.cmd:12` never compiles `trigger.cpp`.

A third variant closes the per-claim census turn (`id 229489`), which adds *"leaving that
finding at population 0"*. **Three closings, one verdict.** This is the *only* shape the brief
warned about — **there is no bare `PASS`/`FAIL` token anywhere in this reviewer's output.**

---

## POPULATION and WINDOW

**The reviewer DID state a POPULATION and a WINDOW for the review itself**, and stated them
per-claim rather than once. His own words from `229489`:

> **Runtime measurements of trigger behaviour taken by me: 0.** I executed nothing.
> Everything behavioural in my report is either (a) static reading of ~1,260 lines across
> 4 source files, or (b) a **quotation of L1/L23's run logs**, which I did not produce.

His closing table (`229649`), verbatim:

| what | population | window |
|---|---|---|
| Files reviewed | **8** (4 source, 2 receipts, 2 gates), ~2 300 lines read | single sitting, 12:49:54 → ~13:0x |
| File stability | **6 files × 2 hash samples = 12 observations**, all identical | opening fingerprint 12:49:54 → re-hash same session |
| **Runtime behaviour measured BY ME** | **0** | — none. I executed no gate, no probe, no binary. |
| Gate transcripts read | **2**, N=1 run each | lane1 12:48:19→12:49:25; lane23 12:47:27→12:47:48 |
| Compile events in those transcripts | **4** (2 fixed, 2 mutant), all at sha `241A9BF0…` | same window as above |
| Registration data quoted (**L1's**, not mine) | **9 bindings, 1 moment, 1 host** | 12:49:25 |
| Control-arm evidence | **2 gates, 4 mutant builds, 6 assertion groups** — both controls verified RED on reverted copies | same |
| MS Learn quotation | **0 of my own** — internal consistency only | — |
| `NOT MEASURED IN-GAME` occurrences | **8** across 4 files + 2 gate tails | consistent throughout |

Review bound to `trigger.cpp` sha256 **`241A9BF08D8951AF…`**. His own caveat on the N=1
material, verbatim: *"**'Both green' is a single-run claim, not a reliability claim.** … The
`-Wall -Wextra` warnings=0 claim is likewise a single build."*

---

## Findings

Five findings, as the reviewer counted them: **1 critical, 1 high, 1 medium, 2 low.**

| id | severity | file:line | what was claimed | what is actually there | the fix (reviewer's words) | owning lane |
|---|---|---|---|---|---|---|
| **F1** | CRITICAL | `trigger.cpp:262` (arms the fallback for **every** binding), `:433-455` (`poll_once`), `:387` (pump thread), `:505-523` (`emit`) | the trigger arms one path per binding | **Both paths are armed on every binding.** `st.polled = true` is set for every binding, registered or not; the only read of `status_[i].registered` in `poll_once` is `:448` and it chooses only a **log note**. Each path has a **private** guard — `last_ns[idx]` (`:380-386`, pump-only) and `held_[i]` (`:459`, poll-only) — and `emit()` does **no** dedup, assigning a fresh `request_seq = seq_++`. One physical press ⇒ **two** `CutRequest`s. **6 of 9 bindings** on this host (`registered=6 polled_only=3`; refusals `Alt+F9`, `PrintScreen`, `F12`). The promoted primary `F10` is registered, so **F10 double-fires**. | *"arm the poll fallback only for bindings that failed to register, i.e. gate the emission in `poll_once` on `!status_[i].registered` — or, if both paths must stay armed for the UIPI case in `trigger.h:28-29`, add one shared per-binding 'last press' QPC consulted by both `emit()` sites so the second path suppresses within `kRepeatGuardNs`. Either way, add an arm that arms **both** paths on one binding and presses once, asserting `cuts == 1`."* | L1 |
| **F2** | HIGH | `src/capture/build.cmd:12` | receipt-15 §6's hookup links | **`trigger.cpp` is absent from the link line.** No build script anywhere compiles it (`Select-String 'trigger\.cpp'` across every `.cmd/.ps1/.sh` matches only the two lane gates and `durability-gate.ps1`); no source `#include`s it. `aireplay-capture.exe` therefore contains **zero** trigger code. Applying §6 as written fails at link with undefined `Trigger::arm`, `Trigger::take`, `default_binding_ladder()`. | *"add `"%SRC%\trigger.cpp"` to `build.cmd:12`, immediately **before** `"%SRC%\replay.cpp"`. Do **not** add `trigger_selftest.cpp` — it defines its own `main()` (`trigger_selftest.cpp:352`), which collides with `main.cpp`'s."* | whoever owns `build.cmd` (not L1) |
| **F3** | MEDIUM | `receipt-15-instant-replay-trigger.md:110` | the "Authoritative output" block is current | It quotes `STEP 2 sha256 fixed = B2495E4A…`, a revision that **no longer exists**; live `trigger.cpp` hashes `241A9BF0…`. Captured before lane 23 edited the file, and **carries no note saying so**. | *"add one line above the block — 'Transcript captured at `trigger.cpp` sha256 `B2495E4A…` (pre-lane-23). The current revision is `241A9BF0…`; its gate run and the modifier/F12 cures are in receipt-23.'"* | L1 |
| **F4** | LOW | `arm()` `:272-315`, `disarm()` `:317-334`, `arm_summary()` `:554` | `arm_summary()` is safe | `arm()`/`disarm()` never reset `stats_` (verified: no `stats_ =` reset in range). `polled_only = status_.size() - stats_.registrations_ok.load()` is **`size_t` subtraction**; after a second `arm()` on an N-binding ladder `registrations_ok == 2N` vs `status_.size() == N`, so `polled_only` **wraps to ~1.8e19**. Latent — nothing re-arms today. | *"reset the registration counters in `arm()` alongside `status_.clear()` (`:281-282`)."* | L1 |
| **F5** | LOW | `trigger.cpp:380` (`static thread_local uint64_t last_ns[kQueueCapacity + 16]`), `:378` | the array is large enough | **24 slots**, indexed by a binding index bounded only by `bindings_.size()`. A caller passing >24 bindings writes out of bounds. The shipped ladder is 9, so unreachable in product — but the array is sized from the **queue** capacity, which has nothing to do with the binding count. | *"size it from the binding count (a `std::vector<uint64_t>` sized in `arm()`), or clamp `idx` against `last_ns` extent as well as `bindings_.size()`."* | L1 |

**Four things he checked and explicitly cleared** (carried because a review that only lists
faults hides the half it verified): the F12 nuance is handled honestly and **refuses** the
stronger claim (`trigger.cpp:96-111`); the stale "no hotkey exists" premise appears once, in
the past tense, qualified against `replay.cpp:539` — *"No finding — the brief's trap did not
land"*; `NOT MEASURED IN-GAME` is honoured in 8 places; and the modifier-mask fix from lane
`bg_ef36a3fd` **is** present and correct (`trigger.cpp:442`). `trigger.h:42-55` carries a
**CITATION HISTORY** that records a once-false citation, deleted then restored — *"the correct
treatment of a once-false citation, and the reason I raise no finding on it."*

---

## UNVERIFIABLE / do not route as fixes

Everything here is drawn only from the reviewer's own hedges.

1. **F1 is population 0. It is CONFIRMED-BY-READING, not a measurement.** *"I did not execute
   a live two-path press — that would inject a keystroke into the owner's session."* **Do not
   read "6 of 9 double-fires" as an observed rate** — that figure is **L1's** registration
   count, quoted, at **1 moment, 1 host**, and `receipt-15:192-193` already says `F12` *"moved
   between two of my own runs."*
2. **F4 and F5 are latent** — unreachable on the shipped 9-binding ladder, gated on a caller
   that does not yet exist.
3. **The control arms are N=1 each.** *"both gates pass" is a single-run claim, not a
   reliability claim.* No flakiness figure exists for either gate.
4. **The `-Wall -Wextra` warnings=0 claim is one build.** *"Compiles is 1 invocation, not
   'always compiles.'"*
5. **He ran no gate and no probe.** His verdict on the gates is **from reading the arms and
   their output, not from re-executing them** — the transcripts he read are ~3 min older than
   his fingerprint, which he checked.
6. **The F12 finding is capped at internal consistency.** *"I did not fetch the MS Learn page
   … I cannot attest it is verbatim-accurate."*
7. **In-game behaviour is unmeasured by anyone.** No game was run, by any lane.
8. **`src/capture/**` was moving during his review** — `replay.cpp` 12:26, `trigger.cpp` 15:43Z,
   `wasapi_audio.cpp` 15:42Z, `trigger_selftest.h` 15:47Z. F1–F3 are pinned to his hashes only.
9. **The control-arm evidence is uncommitted** (see the hazard table) — *my* finding, not his.

---

## The reviewer's own gate doubt

> **Gate-doubt:** both gates build `trigger.cpp` **linked against a hand-listed set** rather than
> the repo's `build.cmd` line (`_lane1:37-44`, `_lane23:52-54`). That is legitimate — `build.cmd`
> has no trigger, and `trigger_selftest.cpp` carries its own `main()` — but it means **no gate can
> ever catch a `build.cmd` regression on this file**, which is exactly why F2 survived.

And, on F1's blindness, from the main report:

> **Why every gate is green anyway — this is the important part.** Each arm drives exactly one
> path, by construction … No arm ever has both paths live on one binding. The gate is structurally
> incapable of observing this defect, which is why its arms are honest and still miss it.

**Read the two together.** He rates the gate as *"a genuinely well-built gate"* — and his own
doubt is that F1 (population 0) and F2 (a build regression) both live where no arm looks. **A
green `LANE1-GATE PASS` is not evidence that F1 or F2 is fixed.**

---

## SELF-AUDIT

Carried from the reviewer's own sections (`229300` "Self-audit", `229562`, `229649`), verbatim.

**Confidence per claim:** F1 high-by-reading, not measured. F2/F3 certain — direct file
comparisons. F4/F5 certain as latent defects, unmeasured in product. Gate-control assessment
high — he read both arms, both mutants, both transcripts.

**Named verification boxes** (*no artifacts produced — read-only seat*):
`BOX-R1 grep build.cmd for trigger.cpp` → zero hits, **RUN, confirmed absent (F2)** ·
`BOX-R2 #include "trigger.cpp" unity check` → zero hits, **RUN** ·
`BOX-R4 two-path single-press arm` → **NOT RUN, DOES NOT EXIST** — *"This is the box that would
settle F1, and its absence is why the lane's green gate is not sufficient"* ·
`BOX-R5 file-stability re-hash` → **RUN**, all six files byte-identical.

**Reviewed by another subagent:** *"No reviewer verdict is recorded in either receipt. Receipt-23
§6 is L23's **self**-report … Per brief §6 both lanes owed a dispatched verifier; neither shows
one. This report is the first independent read of the trigger code."*

**Protocols missing** (his words, from the two dropped-section turns): he **dropped required
sections twice across continuations** — *"the same failure mode as the missing `## SELF-AUDIT`,
and the same root cause … the required sections are not optional garnish that gets trimmed when
the report grows — they are the report."* Both were restored before closing, but the episode is
his own and belongs in this file.

---

## SELF-AUDIT of THIS persisting lane

Stated separately so it can never be confused with the reviewer's.

**Reviewer position.** Read-only. The runtime store was opened with `mode=ro`; no byte was
written to it. I did **not** re-run either gate, re-hash the trigger sources, or re-open a single
finding. I transcribed and I labelled.

**What I verified myself** (1 box, measured, not assumed):

| fact | command | rc | result |
|---|---|---|---|
| `receipts/review-L1.md` did not already exist | `Test-Path` | — | **FALSE** — no overwrite risk |
| every `file:line` in the verdict resolves? | `py -3 -B _main/_rv-cite.py` | 0 | **10 files, 2 dangling at HEAD** (`trigger.cpp:505/523/554`, `receipt-15:199`), **2 absent from `HEAD`** entirely (`_lane23-trigger-defects-gate.ps1`, `lane1-trigger-gate.txt`) — table above |

**What I did NOT verify.**

- That **any** finding other than F2's citation still reads as claimed. A line-resolution check
  is not a re-verification of five findings.
- Whether F1 was **fixed** after 13:01. A closure lane (`mvs_1d0ddb59…`, *"Fix the six L3
  ring-buffer defects"*, and lane 23's defect pass) edited `src/capture/**` while this file was
  being written. `trigger.cpp` is 65 lines longer at HEAD than it was at review time.
- The **content** behind any line that resolved. I checked line counts, not what the lines say.
- The control arms' verdicts, which rest on an uncommitted gate file.
- Rows `229562`'s full text is cited by id only; I carried the SELF-AUDIT from `229300` and
  `229649`, which between them cover the same ground.

**Per-claim confidence in MY OWN contribution:** high that the citation table is true (it is a
mechanical check against a named sha); high that the transcription is faithful to the store
bytes; **zero** confidence that any finding is still live — the reviewer's own revision pin sits
between two different file lengths, and the control-arm evidence is uncommitted.