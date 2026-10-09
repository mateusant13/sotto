# Review of LANE L15 — `specs/07-highlights.md`: automatic clip extraction

> **Provenance of this file.** Written by lane *Close the review-on-disk debt for 14 lanes*
> (`mvs_54687d45969d461181c10929993039e8`) to satisfy `_main/REVIEW-MODEL.md:41` —
> control **CHK-REV-1**, *"every committed lane has receipts/review-<LANE>.md on disk"*.
> Recovered read-only from `C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite`
> (`file:…?mode=ro`), reviewer session **`mvs_2e2a644a671b4d0cac32dc46aeb699d3`**
> (*"L15 reviewer - highlights spec audit"*, agent `verifier`, `session_type=branch`,
> created 12:29:55, last updated 12:51:16 BRT).
> Source rows: **`228145`** (main findings report, 15 996 chars) · **`228202`**
> (WHAT'S NEXT, 3 295) · **`228282`** (SELF-AUDIT, 5 331) · **`228352`** (POPULATION AND WINDOW
> + P0, 5 925) · **`228400`** (closing SELF-AUDIT + verdict, 5 596).
> Recounted live, not taken from a prior lane's census: the session holds **27 message
> rows / 25 assistant**.
> **This file is a transcription, not a review.** Nothing in it was re-measured by me except
> the citation-resolution box, labelled *verified by the persisting lane*, below.

---

## 🔴 HAZARD — THE SUBJECT OF THIS REVIEW NO LONGER EXISTS ON DISK

*Verified by the persisting lane*, `git status --porcelain=v1 -- specs` (rc=0):

```
 M specs/03-capture-encode.md
 M specs/04-index-search.md
 D specs/07-highlights.md          <-- THE REVIEWED DOCUMENT
?? specs/05-clip-to-asr.md
?? specs/06-broadcast-and-capture-card.md
?? specs/07-engine-process.md
```

**`specs/07-highlights.md` is DELETED in the working tree and the spec set has been RENUMBERED.**
Live `specs/` is now `01-capture-modes-and-scheduling.md` · `02-asr.md` ·
`03-capture-encode.md` · `04-index-search.md` · `05-clip-to-asr.md` ·
`06-broadcast-and-capture-card.md` · `07-engine-process.md`. The file exists at `HEAD`
(**439 lines**, commit `51f84cc`), and *only* there.

**Consequences, stated plainly:**

1. **Every `specs/07-highlights.md:NNN` citation below is a citation into a deleted file.** Do
   not open it on disk; read it at `51f84cc` / `HEAD`. This is the same class of hazard
   `review-L4.md` carries for `src/index/schema.py`.
2. **The name `07` now means a different document.** `specs/07-engine-process.md` is 936 B and
   untracked. Any routing note that says "07-highlights" is now ambiguous with "07-engine-process".
3. **`specs/05-overlay-hud.md` (lane L13's deliverable) is ALSO absent** — there is no HUD spec
   under any number. Recorded here because it is the same renumbering event; I did not chase it.
4. **Whether the findings survive the renumber is unknown and was checked by nobody** — the
   reviewer finished at 12:51:16, the last commit to the file is the 12:2x freeze.

*`src/capture/**` is also mid-write* under lanes L1/L23/L3; the reviewer's own snapshot table
(`228145`) records `trigger.h` at 12:33:47 and `replay.cpp` at 12:26:28, **both after** spec 07
was frozen at 12:22:52.

### Remaining citations, checked

*Verified by the persisting lane*, `_main/_rv-cite.py` against **`HEAD` = `13e4da225355e16c30b49722c35f5c0e665dd4a2`**
(POPULATION = every non-`specs/07` `file:line` the verdict names; WINDOW = one run, ~13:40 BRT):

| cited file | lines in working tree | lines at HEAD | verdict |
|---|---|---|---|
| `_main/oracle-07-highlights.py` | 262 | 261 | `:104-120`, `:147-176`, `:216-218` resolve both |
| `src/capture/replay.cpp` | 645 | 632 | `:125`, `:132-138`, `:149` resolve both |
| `src/capture/trigger.h` | 272 | 245 | `:47-53`, `:99-103`, `:106`, `:120` resolve both |
| `src/asr/segment.py` | 126 | 126 | `:64`, `:97`, `:102-104` resolve both |
| `src/asr/transcribe.py` | 141 | 141 | `:47` resolves both |
| `src/asr/level.py` | 152 | 152 | `:45`, `:146` resolve both |
| `src/asr/constants.py` | 254 | 254 | `:91`, `:142-144`, `:172` resolve both |
| `specs/03-capture-encode.md` | 311 | 311 | `:137-140` resolves both (file is ` M`) |
| `receipts/receipt-14-ring-cap-vram-vs-ram.md` | 104 | 97 | resolves both — **but this file is mid-write by another lane** |

**Every surviving citation resolves in both bases.** The hazard is deletion and renumbering, not
line drift.

---

## Verdict

The reviewer's own closing line, verbatim, from his **last** turn (`id 228400`):

> Does your implementation meet the spec? NO - the mandated central question is answered
> incorrectly: the spec claims the rule does not call a walk a highlight, but a footstep-shaped
> corpus fires 36/36 (n=0 real walks on this box, disclosed above), because the `degenerate-signal`
> dynamic-range gate rewards impulsiveness; additionally `THRESHOLD` and `W_E` are inert on every
> measured corpus (the rate is produced solely by `MIN_GAP_S`), the containment arm the spec names
> as its false-positive claim is tautological, and Appendix B attributes the tone's 1.22x to the
> walk corpus whose measured value is 2.224x.

The **main report** turn (`id 228145`) closes with the quantified variant:

> Does your implementation meet the spec? NO - the mandated central question is answered
> incorrectly: the spec claims the rule does not call a walk a highlight, but an impulsive footstep
> walk (36/36 configurations, 5-9 emits per 180 s, 12 breaching the α gate) does, because the
> `degenerate-signal` dynamic-range gate rewards impulsiveness; additionally `THRESHOLD`/`W_E` are
> inert on every measured corpus (rate is produced solely by `MIN_GAP_S`), the containment arm the
> spec calls its false-positive claim is tautological, and Appendix B attributes the tone's 1.22x
> to the walk corpus whose measured value is 2.224x.

**The verdict itself carries the honesty marker** — *"n=0 real walks on this box, disclosed
above"* is inside the verdict line, not bolted on after it. **No bare PASS/FAIL token exists**
in this reviewer's output.

---

## POPULATION and WINDOW

**The reviewer DID state a POPULATION and a WINDOW, per claim.** His own words (`228400`):

> **POPULATION/WINDOW of the whole audit: one session, 2026-10-07 ~12:30–12:45 -03, single
> execution per configuration. There is no repeat-run stability population anywhere in this
> report.**

And, verbatim, on the marker that must travel with everything below:

> - **S1 (the walk verdict is false)** — high, but weaker than the headline suggests: **n=36 runs
>   from ONE generator of my own; real-walk population is n=0.** The mechanism is understood, not
>   inferred from tone: impulsive audio has high `p99/p50`, which is exactly what `GATE 0` rewards.
> - **The §1.1 audio census was re-read, not re-measured** — I verified the 28 rows are complete
>   and self-consistent and did **not** re-run `ffprobe`. That claim is the lane's, at **n=0
>   re-measured by me**.
> - **BOX-7 carries no file count** — the honest form is "no hits in the files my glob matched",
>   not "no hits anywhere".

His 7 named boxes, verbatim:

| box | what it asserts | result |
|---|---|---|
| `HL07-AUDIT-BOX-1` | threshold invariance: sweep `THRESHOLD` 0.75→0.00 | emits and rate **constant at 3 / 15.00** — refutes "load-bearing rather than decorative" |
| `HL07-AUDIT-BOX-2` | containment tautology: remove both guards (`MIN_GAP_S=0`, `THRESHOLD=0`) | **11/11 segments emit, `outside_speech=0`** |
| `HL07-AUDIT-BOX-3` | footstep sweep: 4 seeds × 3 cadences × 3 footfall levels | **36 runs, 36/36 fire**, 5–9 emits/180 s, 12 breach α |
| `HL07-AUDIT-BOX-4` | refractory sensitivity `MIN_GAP_S` 20/10/5/2 | 20.00/36.67/36.67/40.00 per 10 min; clip coverage 46.7 %→93.3 % |
| `HL07-AUDIT-BOX-5` | `PEAK_REFERENCE_S` unexercised | `win=3000 ≥ len(ev)=1200` ⇒ `lo=0` for **every** candidate |
| `HL07-AUDIT-BOX-6` | citation and hash audit | 12 files hashed, ~11 line citations re-read byte-for-byte; **4 stale, 7 exact** |
| `HL07-AUDIT-BOX-7` | negative claims | 0 hits for `GetLastInputInfo`/`QueryAdapter`/`utilisation` — **file count not recorded** |

---

## Findings

Six findings. The reviewer's own section titles: **S1 CRITICAL, S2 CRITICAL, S3 MAJOR,
S4 MAJOR (upheld), S5 MINOR, S6 MINOR.**

| id | severity | file:line | what was claimed | what is actually there | the fix (reviewer's words) | owning lane |
|---|---|---|---|---|---|---|
| **S1** | CRITICAL | `specs/07-highlights.md:429-436` (Appendix B); corpus at `_main/oracle-07-highlights.py:104-120`; the 1.22× figure at `:89` | *"would this heuristic call a random 30 seconds of a walk in the park a highlight?"* → **"NO … the number that says so is the 1.22× dynamic range against a 3.0 gate"** | **the answer is false for the real signal.** The walk corpus `synth_walk_bed` is pink noise × a 23 s sine wander, **no impulsive content**. A walk is footsteps: sharp broadband transients. With a footstep corpus run through **the spec's own rule, unmodified, at the spec's own parameters**: **36 of 36 configurations fire — 5 to 9 highlights per 180 s — and 12 of 36 fail the α gate outright.** Footsteps *raise* `dr` (10–25), which is exactly what `GATE 0` rewards: *"the 'degenerate-signal' gate is a **silence detector wearing a highlight detector's clothes**."* At `MIN_GAP_S=20.0`, 6 emits × 14 s = **46.7 % of the walk clipped as highlights**; at 10.0 it is 85.6 %. The number the verdict rests on is **2.224, not the 1.22× printed in Appendix B** — *"the verdict's stated evidence does not even belong to the arm it is quoted for."* | *"rewrite Appendix B's verdict. The honest answer … is 'the rule calls a walk a highlight — measured, 36/36 configurations, 5–9 emits per 180 s.' Then either (i) state that the rule is **not shippable as a moment detector on audio alone** … or (ii) add an explicit `non-speech` rejection to §3 that is **independent of `dr`** (e.g. requiring `E` high *and* `A=1` *and* a speech-band/spectral-flatness test that the current `src/asr/level.py` does not provide, making that a **new primitive, not a parameter**). Delete the '1.22×' figure from the walk row."* | L15 + owner decision |
| **S2** | CRITICAL | `specs/07-highlights.md:256`, `:277`, `:333-338`, `:339`; the claim at `:172-177`; gate at `_main/oracle-07-highlights.py:216-218` | `THRESHOLD=0.75` is *"load-bearing rather than decorative: with `A = 1` the rule needs `E ≥ 0.375`"* | **two of three named parameters do no work.** `THRESHOLD` is **inert**: sweeping 0.75→0.00 leaves emits=3, rate=15.00/10min at every value. Per-candidate E ∈ **[0.9711, 1.0000]**, lowest score **0.9884** — all 11 candidates pass. *"**The 15.00/10 min figure is produced entirely by `MIN_GAP_S = 20.0`, not by the scoring formula.**"* `W_E` is near-inert: `PEAK_REFERENCE_S = 300` exceeds every corpus (longest 180 s), so `lo = 0` for every candidate and `ref` is p99 over the **whole prefix**, never the trailing window the parameter describes. α's ceiling is `600/20 = 30.0` and α is set to 20.0 *below* it — *"so the gate **can** fail — but only via the refractory, never via the formula"* — and 20.0 sits just above the measured 15.00 with no derivation. | *"state plainly in §3 and §7 that **`THRESHOLD` and `W_E` are inert on every measured corpus and that the entire measured rate is produced by `MIN_GAP_S`**; either lower `PEAK_REFERENCE_S` below the corpus length or add a corpus longer than 300 s; and re-derive α from the refractory ceiling … or declare it `ARBITRARY UPPER BOUND`."* | L15 |
| **S3** | MAJOR | `specs/07-highlights.md:276` (*"A0 containment … **this is the FP claim**"*); implementation at `_main/oracle-07-highlights.py:147-176` (`:156` `cands = segs`, `:175` the counter) | the containment arm is the spec's own named false-positive claim | **it is tautological.** Non-naive candidates **are** `segs` (`:156`), and the containment counter (`:175`) can only ever read 0 because an emit's `t` is an `argmax` *within* `[a,b)`. Guard removal confirms it: `MIN_GAP_S=0`, `THRESHOLD=0` → **`emits=11 outside_speech=0`**. *"It is true **by construction**, for any input, including a walk. **A gate that cannot go red is not a gate.**"* A3 (`:293-296`) does not rescue it — A3 tests a *different rule*. | *"stop calling containment the FP claim. Replace it with an arm that measures what it claims — e.g. emit on a **window grid** (not per segment) and count how many land outside a segment, which is falsifiable; or assert that containment is structural and say so, moving the FP burden entirely onto A1/A2."* | L15 |
| **S4** | MAJOR — **PASS** | `specs/07-highlights.md:35-57` (§1.1), `_main/_hl07-audio-census.txt` | *inherited 8/8 claim* | **upheld, and it improves on it**: POPULATION=**28**, WITH_AUDIO=**1**, and the one audio-bearing file is an ffmpeg synthetic, so **27/27 capture outputs are video-only**. Table complete and self-consistent; the audio dependency is stated as a blocker in §1.4, §6, §8 (M2 ⛔) and Appendix A. *"**Requirement met.**"* | none | — |
| **S5** | MINOR | `specs/07-highlights.md:219-220` (`replay.cpp:125`); `:99-103`; `:47-53`; `src/asr/level.py:45` | 11 line citations into files other lanes were editing | **4 stale, 7 exact** (his own `BOX-6` count). `replay.cpp:125` is now **`:149`**; `trigger.h:99-103` is the `CutRequest` struct and `span_seconds()` is `:120`; `trigger.h:47-53` is a comment about a deleted receipt-15; `level.py:45` is `class LevelEmitter` and `events_from_array` is **`:146`**. *"the drift is **not** the lane's error — those files changed at 12:26 and 12:33, after 07 was frozen at 12:22."* | *"re-anchor the three stale citations to **symbols**; fix `level.py:45` → `:146`."* | L15 |
| **S6** | MINOR | `specs/07-highlights.md:89` (`_hl07-speech-probe.log:19`) | a §1.3 row labelled **"dynamic range `p99/p50`"** with **19.90–24.76×** | `p99/p50 = 19.897`, `max/p50 = 24.764`. **One row, two metrics, one label** — the probe prints `max/med = 24.76x`. | *"Split into two labelled rows."* | L15 |

---

## UNVERIFIABLE / do not route as fixes

1. **S1's real-walk population is n=0.** *"36/36" is 36 runs from **ONE generator of my own**;
   the corpus is `SYNTHETIC`; no walk recording exists on this box.* It moves only if a real walk
   recording measures `dr < 3.0` — *"not plausible for footsteps"* — so it will not move, but the
   marker must travel.
2. **The §1.1 audio census was re-read, not re-measured** — 28 rows verified complete and
   self-consistent, `ffprobe` **not** re-run. n=0 re-measured by him.
3. **`BOX-7` carries no file count.** The honest claim is *"no hits in the files my glob
   matched"*, **not** *"no hits anywhere"*.
4. **No recall protocol is possible at all** — M4 requires ≥60 min of human-labelled gameplay and
   **no labelled corpus exists on this box**. Every rate in the spec is a *rate*, never
   precision/recall; *"I did not convert one into the other, and I could not."*
5. **`PEAK_REFERENCE_S` in production is UNKNOWN** — no corpus ≥ 300 s exists. The spec's own
   provenance rule (`:4-6`) demands it be labelled so.
6. **No C++ arm, no ring run, no live tap, no real-time behaviour** was exercised — out of scope
   for a spec review and requiring the visible-window-safe launch.
7. **The C++ line drift was checked against bytes at 12:33:47 (`trigger.h`) and 12:26:28
   (`replay.cpp`)** — *"those lanes may move again."*
8. **Rule 2 was observed** (redirect to file, read `$LASTEXITCODE`, never pipe a native
   command) — worth recording because it is the house law this repo has been bitten by.

---

## The reviewer's own gate doubt

> - My headline has a population of **n=0 real walks**, and the availability claim I weighted
>   heavily sits at **n=0 re-measured**. Both are disclosed above rather than folded into the verdict.
> - The verdict does not depend on either: Appendix B's `1.22×` is wrong against the spec's **own**
>   evidence (walk = 2.224×), and the threshold-inert and tautology findings are arithmetic that
>   do not decay with n the way S1 does.

From the main report:

> - **Gate doubt:** none material. The one soft spot in my own work is that the walk corpus is
>   synthetic — stated inline above, and the spec's own `SYNTHETIC` convention requires me to label
>   it so.

**Read it with the caveat that this is the ONE review of the four whose gate-doubt section says
"none material."** That is the reviewer's judgement on his own work and it is not contradicted
by anything in this file. It is also the reason S2 and S3 should be routed ahead of S1: they are
arithmetic, S1 is a synthetic proxy.

---

## SELF-AUDIT

Carried from the reviewer's own `## SELF-AUDIT` turns (`228282`, `228352`, `228400`), verbatim.

**Reviewed by another subagent:** *"**No.** … The spec itself records at `specs/07-highlights.md:425`
that its own reviewer dispatch never happened, so **no second pair of eyes has seen S1–S3**. The
orchestrator must treat this report as un-peer-reviewed."* **This file is that missing review.**

**Confidence, and what would move it:** S1 high but n=36-from-one-generator · S2 very high
(*"Direct arithmetic; the invariance across a 0.75→0.00 sweep is unambiguous"*) · S3 very high
(*"visible in the code path and confirmed by guard removal"*) · S5 certain as of the recorded
hashes · S6 certain.

**What was NOT verified:** whether the footstep corpus represents a real walk *rather than merely
alarming about one* · the §1.1 census was re-read not re-measured · `BOX-7` has no file count ·
real-time behaviour of `PEAK_REFERENCE_S` and of the rule on a live stream · C++ capture, ring,
NVENC · the C++ line drift may move again.

**Peer-review cost:** the spec itself records the dispatch never happened (`Appendix B, :425`).
*"This report is that missing review."*

---

## SELF-AUDIT of THIS persisting lane

**Reviewer position.** Read-only; the store was opened `mode=ro` and no byte was written to it.
I did **not** re-run the oracle, rebuild any corpus, re-measure `dr`, or open the deleted spec.
I transcribed and I labelled.

**What I verified myself** (2 boxes, measured):

| fact | command | rc | result |
|---|---|---|---|
| `receipts/review-L15.md` did not already exist | `Test-Path` | — | **FALSE** — no overwrite risk |
| does the reviewed document still exist? | `git status --porcelain=v1 -- specs` | 0 | **`D specs/07-highlights.md`**, spec set renumbered (`05-clip-to-asr`, `06-broadcast-and-capture-card`, `07-engine-process`, all `??`) |
| every non-`specs/07` `file:line` resolves? | `py -3 -B _main/_rv-cite.py` | 0 | **9 files, all resolve in BOTH bases**; `specs/07-highlights.md` = **not in working tree**, 439 lines at HEAD |

**What I did NOT verify.**

- **Whether S1–S6 survive the deletion and renumbering.** Nobody has checked. This is the
  biggest open question about this file and it is exactly the question `review-L4.md` could not
  answer either.
- **Whether the findings were applied to a successor document.** `specs/05-clip-to-asr.md` (824 B)
  and `specs/07-engine-process.md` (936 B) are tiny; I did **not** read either.
- Any of the 36 footstep runs, the threshold sweep, or the `dr` measurements. They are the
  reviewer's, at n=1 per configuration, against a document that no longer exists.
- `receipt-14` is **mid-write** by another lane (104 lines in tree vs 97 at HEAD) and is cited by
  S5/S6's cross-check. I did not edit it.
- `specs/03-capture-encode.md` is ` M` — another lane's file.

**Per-claim confidence in MY OWN contribution:** **high** that the reviewed document is deleted
and renumbered (mechanical, two-sided, named sha); **high** that the surviving citations resolve;
**zero** confidence that any finding is still live, because the document it is about is gone.