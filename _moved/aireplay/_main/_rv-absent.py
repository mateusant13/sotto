import os, json

ROOT = r"H:\sotto\_moved\aireplay"
OUT = os.path.join(ROOT, "receipts")

CENSUS = """**The census that proves the absence.** POPULATION = **every** session row whose
`parent_session_id` is this orchestrator, `mvs_b7a9f3a7db404912b32d28fc11b83645` — **45 rows**,
every one of them with **zero** children of its own. WINDOW = one `mode=ro` query, 2026-10-07
13:35–13:40 BRT, against `runtime-state.sqlite` (3.1 GB, last written 13:34:46).

**First, a correction to the route the brief supplied.** The brief says a reviewer's session is a
CHILD of the lane's session. *That is false on this store* — the census returns **0**
grandchildren across all 45 lanes. Reviewers are **SIBLINGS** under the same parent, separable
only by `agent_name = 'verifier'` and by title. Anyone repeating the child-of-lane query will
conclude "no reviewer" for every lane including L4 and L16, which do have one.

Of those 45, **13 carry `agent_name = 'verifier'`**. Every one, by title:

| verifier seat | title | what it reviewed |
|---|---|---|
| `mvs_36edbf94…` | L1 reviewer - instant replay trigger audit | **L1** — verdict recovered |
| `mvs_03762d41…` | L3 reviewer - ring buffer RAM budget audit | **L3** — verdict recovered |
| `mvs_9c1a6ee2…` | L4 reviewer - index and search audit | **L4** — already on disk |
| `mvs_a4c053f4…` | L8 reviewer - integration design audit | **L8** — verdict recovered |
| `mvs_2e2a644a…` | L15 reviewer - highlights spec audit | **L15** — verdict recovered |
| `mvs_116b6318…` | L16 reviewer - wake audit verification | **L16** — already on disk |
| `mvs_7bdbb1dd…` | Review the broadcast and capture card spec | **L14** — dispatched 13:33:05, **NO VERDICT YET** |
| `mvs_97c6a61d…` | L20 synthesize reviewer verdicts into fixes | synthesis, not a lane reviewer |
| `mvs_25670c59…` | Read L4 and L16 verdicts and route defects | routing, not a lane reviewer |
| `mvs_d4cd50d0…` | Re-verify L4 findings against rewritten index | L4 second pass, **no verdict yet** |
| `mvs_cba42e5b…` | Review the six L3 defect closures | L3 closure, **no verdict yet** |
| `mvs_e968a220…` | Review the L20 verdict synthesis | synthesis review, **no verdict yet** |
| `mvs_be09576a…` | Review the six wake defect closures | L16 closure, **no verdict yet** |

**Four lanes were reviewed (L1, L3, L4, L8, L15, L16 — six). This lane is not one of them.**"""

LANES = [
 ("L2", "WASAPI loopback audio", "`src/capture/wasapi_audio.{h,cpp}`",
  "`receipts/receipt-16-wasapi-audio-loopback.md` (13 209 B)",
  "`src/capture/wasapi_audio.cpp` exists (measured). Fleet row 2 of `_main/ORCHESTRATOR-STATE.md:82-99`.",
  "This lane produced a large receipt (13 209 B) measuring the missing audio feature, and **no reviewer was ever dispatched**. The file number `16` in that receipt filename does **not** mean lane 16 — the same number also carries lane 3's ring-cap receipt. Receipt numbers are not lane ids."),
 ("L5", "ShadowPlay parity research", "`research/shadowplay-parity.md`, `research/open-source-alternatives.md`",
  "**NO RECEIPT FILE** in `receipts/` for this lane",
  "Both research files exist (measured). Fleet row 5.",
  "**Two gaps at once: no receipt and no review.** The lane's output is committed and unreviewed. This file records the receipt gap too, because CHK-REV-1 asks about lanes, and a lane whose evidence is not on disk cannot be reviewed from the repo at all."),
 ("L6", "index search spec", "`specs/04-index-search.md`",
  "**NO RECEIPT FILE** in `receipts/` for this lane",
  "`specs/04-index-search.md` exists and is ` M` (30 931 B, mid-write). Fleet row 6.",
  "No receipt, no review. Note this spec was **rewritten by L6 at 12:49:59, mid-L4-review** — `review-L4.md` records that its own §1.1–§2.5 citations are pinned to a sha that was rewritten underneath it. L6 is the reason L4's citations are stale, and L6 itself was never reviewed."),
 ("L7", "4K window support", "`src/capture/replay.*`, `test_window.*`",
  "**NO RECEIPT FILE** in `receipts/` for this lane",
  "`src/capture/replay.cpp` 645 lines, `replay.h` present (measured). Fleet row 7.",
  "No receipt, no review. L7 is load-bearing for other lanes: **both L3's F3 and L8's S3 rest on L7 having landed at 12:26** and lifted the 1920x1080 clamp. The fix that two other reviews depend on was itself never reviewed."),
 ("L9", "ASR end-to-end parity", "`src/asr/**`",
  "`receipts/receipt-17-asr-parity.md` (25 864 B) — self-labels `Lane 9`",
  "`src/asr/runner.py` exists (measured). Fleet row 9.",
  "A 25 864 B receipt claiming the ASR works end to end on real speech, with no reviewer. The receipt file is numbered 17 while the lane is 9 — again, **receipt numbers are not lane ids**."),
 ("L10", "capture capability battery", "`src/capture/run_battery.ps1`, `probe-cap-*.ps1`",
  "`receipts/receipt-18-capture-capability-battery.md` (33 930 B)",
  "`src/capture/run_battery.ps1` exists (measured). Fleet row 10.",
  "The largest receipt in `receipts/` (33 930 B) is a measurement battery with no reviewer. **L3's F3 correction cites `receipt-18` §2** (WGC refuses every item) as the load-bearing evidence for a re-based claim — so an unreviewed 34 KB battery is currently propping up another lane's corrected finding."),
 ("L12", "durability and git coverage", "`_main/durability-gate.ps1`",
  "`receipts/receipt-20-durability-git-coverage.md` (22 399 B) — self-labels `Lane 20`",
  "`_main/durability-gate.ps1` exists (measured). Fleet row 12.",
  "**Identity conflict, recorded not resolved:** fleet row 12 is DURABILITY owning `durability-gate.ps1`, and this receipt owns that same file — but the receipt self-labels **Lane 20**. I wrote both `review-L12.md` and `review-L20.md` rather than silently merging two lane numbers into one. Which number is canonical is an owner decision, not mine."),
 ("L13", "overlay HUD spec", "`specs/05-overlay-hud.md`",
  "**NO RECEIPT FILE** in `receipts/` for this lane",
  "`specs/05-overlay-hud.md` **DOES NOT EXIST** (measured, `Test-Path` False). Fleet row 13.",
  "No receipt, no review, **and the deliverable is absent**. The spec set has since been renumbered (live `specs/` holds `05-clip-to-asr.md`, `06-broadcast-and-capture-card.md`, `07-engine-process.md`), so this lane's HUD spec may have been renumbered, absorbed, or never written. **Nobody has checked which**, and the file that would have been checked is gone."),
 ("L14", "broadcast and capture card spec", "`specs/06-broadcast-and-capture-card.md`",
  "**NO RECEIPT FILE** in `receipts/` for this lane",
  "`specs/06-broadcast-and-capture-card.md` exists, **60 096 B and UNTRACKED (`??`)** — the largest untracked file in the repo. Fleet row 14.",
  "**This lane is the one in-flight exception — a reviewer EXISTS but has not finished.** `mvs_7bdbb1dd705044f995d8ff0d19ff025d` (*\"Review the broadcast and capture card spec\"*, `agent_name='verifier'`) was created **13:33:05**, 90 seconds before this census. Its last assistant row (`id 234123`) is **65 characters**: *\"Cleaning up scratch and proving I left the deliverable untouched.\"* — **no verdict line exists.** Do not read the dispatch as a review."),
 ("L17", "clip to ASR pipeline", "`src/pipeline/**`",
  "`receipts/receipt-24-clip-to-asr-chain.md` (25 590 B) — self-labels `Lane 17`",
  "`src/pipeline` exists (measured).",
  "A receipt that claims the chain **clip → audio → transcript → index row → search** works end to end, with no reviewer of any kind. The receipt carries a `REVISION 2` note, so it was revised at least once and nobody checked the revision."),
 ("L18", "overlay panel", "`src/ui/**`",
  "`receipts/receipt-25-overlay-panel.md` (20 956 B) — self-labels `Lane 18`",
  "`src/ui` exists (measured).",
  "The panel lane — the lane whose output the owner actually looks at — has a 21 KB receipt and no reviewer. Its receipt cites git `029d995` as the project state; `HEAD` is now `13e4da2`, so the receipt is pinned to a sha that has moved."),
 ("L19", "receipt audit harness", "`_main/receipt-audit.*`",
  "`receipts/receipt-26-receipt-audit.md` (26 064 B) — self-labels `Lane: receipt-audit`",
  "Fleet row 19; runtime seat `mvs_3ba7e94ca8864584b60c4840a1284ff5` *\"L19 receipt audit harness\"*, status `started`, last updated **12:58:37** — it never ran.",
  "The lane that mechanically audits other lanes' receipts was itself never reviewed, and its own session is `started` (aborted before doing work). Its receipt at `:470` claims *\"verifier verdict exists and §6 does not pretend otherwise\"* — **that claim is about its own arms, not about a review of itself**, and it should not be read as this lane's review existing."),
 ("L20", "see review-L12.md — receipt-20 self-labels this number", "see review-L12.md",
  "`receipts/receipt-20-durability-git-coverage.md` (22 399 B) — self-labels `Lane 20`",
  "Same receipt as L12. See that file.",
  "**Written to avoid a silent merge.** L12 (fleet) and L20 (receipt self-label) may be one lane or two; the evidence does not settle it and guessing would put a false claim into version control. Both files carry the same census."),
 ("L21", "correct the false claims in AGENTS.md", "`AGENTS.md`",
  "`receipts/receipt-29-agents-truth.md` (15 655 B) — self-labels `Lane 21`",
  "`AGENTS.md` is 39 851 B, mtime **13:14:11**, last touched by `bae4e1e`. Fleet row 20 in the runtime roster.",
  "**This lane rewrote the file that three other reviews cite**, and it is itself unreviewed. Concretely: `review-L8.md`'s headline evidence (86 `BRIDGE_DEATH`s at `AGENTS.md:456-458`) **no longer resolves** — `BRIDGE_DEATH` has **0 occurrences** in the working tree and **0 at HEAD**. The lane that removed it was never reviewed for whether the removal was correct. Its receipt owns exactly two files and its own scope claim is checkable."),
 ("L22", "clip storage and retention", "storage layout / retention",
  "`receipts/receipt-30-clip-storage-retention.md` (17 626 B) — self-labels `Lane: 22`",
  "Runtime seat `mvs_9d79f4d4da2b4bf8a7f3a61267e8be0f` *\"L22 clip storage and retention\"*, updated 13:26:36.",
  "Receipt claims `LANE22-GATE PASS (rc=0)`. **No reviewer, and the gate was never run by anyone else** — a gate that only its own lane has run is the exact shape this repo's `review-L4.md` flagged as an ornament (*\"a gate nobody has seen go red is an ornament\"*)."),
 ("L23", "instant-replay trigger defects", "`src/capture/trigger.{h,cpp}`",
  "`receipts/receipt-23-trigger-defects.md` (20 322 B) — self-labels `Lane: 23`",
  "**MID-WRITE — another lane is editing this receipt right now** (measured 391 lines in tree vs 390 at HEAD).",
  "L23 fixed two trigger defects that L1's reviewer then reviewed as part of L1's file. **L23 itself has no reviewer.** Note the ordering hazard: `review-L1.md` cites `receipt-23` as evidence and `review-L8.md`'s S3 says `receipt-23` *did not exist* at 12:44 — it exists now. A receipt that appears mid-review invalidates every claim made about its absence."),
 ("aggregate-gate", "aggregate gate for all lanes", "`_main/all-gates.ps1`",
  "`receipts/receipt-19-aggregate-gate.md` (20 946 B) — self-labels `Lane: aggregate-gate`",
  "`_main/all-gates.ps1` exists (measured). Fleet row 11 (ALLGATES).",
  "Named in the receipts as `aggregate-gate` and in the fleet table as **L11** — the same lane under two names. **One honest file, filed under the receipt's own name.** This is the gate that claims to run everything; it has never been reviewed, so nobody has established that it is *honest* in the sense its own receipt title asserts."),
 ("receipt-audit", "receipt audit harness", "`_main/receipt-audit.*`",
  "`receipts/receipt-26-receipt-audit.md` (26 064 B) — self-labels `Lane: receipt-audit`",
  "Runtime seat `mvs_3ba7e94c8864584b60c4840a1284ff5`, status `started`, never ran to completion.",
  "The receipt carries **two different numbers** (file `26`, and the lane's own session is rostered L19). Filed under the receipt's own self-label. Same lane as the runtime's L19; see the conflict note there."),
 ("review-synthesis", "synthesise reviewer verdicts into fixes", "routing only, edits nothing",
  "`receipts/receipt-28-review-synthesis.md` (52 622 B) — the LARGEST receipt in `receipts/`",
  "Runtime seat `mvs_97c6a61dfa3642ab8a80f3f7f17346d4` *\"L20 synthesize reviewer verdicts into fixes\"*, `agent_name='verifier'`, updated 13:26:45. Filed under the receipt's own name; the runtime titles it L20, which collides with L20 above.",
  "**A synthesis lane is not a reviewer, and its own self-audit says so** — it counted *\"itself as a 7th reviewer (`REVIEWERS_FOUND=7` against 6 real reviewers)\"* and flagged that as an error. That honesty is worth recording: **this receipt is an index of other people's verdicts, not an independent review of anything.** Its later reviewer (`mvs_e968a220…`, *\"Review the L20 verdict synthesis\"*) has produced **no verdict yet**."),
 ("preview-designs", "design directions preview page", "a preview page",
  "`receipts/receipt-preview-designs.md` (9 336 B) — self-labels `Lane: preview-designs`",
  "Receipt header says `repo: H:\\aireplay`; this tree is `H:\\sotto\\_moved\\aireplay`. **The path in the receipt does not match the tree it was found in.**",
  "A visual/design lane outside the numbered fleet. **No reviewer.** Two honest caveats: the receipt names a repo path this tree is not at, so whether it was written against this code at all is unestablished; and its own verdict line (*\"uma página que mostra as cinco direções de design\"*) is a lane self-report, not a review."),
 ("render-panel-temas", "themed capture renderer", "renderer for themed captures",
  "`receipts/receipt-render-panel-temas.md` (18 803 B) — self-labels `Lane: render-panel-temas`",
  "Receipt header: `escreve em: H:\\aireplay`, `lê de: H:\\sotto` (**reads from**). Same path mismatch as above.",
  "The receipt carries its own *\"Veredicto do instrumento: PASS (0 problemas, 1 passagem…)\"* — **that is the instrument's verdict, not a reviewer's**, and it is exactly the shape this repo distrusts. The receipt also declares it reads from `H:\\sotto`, i.e. a **cross-tree dependency** on a tree that this one was moved out of. No reviewer was dispatched."),
]

TEMPLATE = """# Review of LANE {lane} — {subject}

> **Provenance of this file.** Written by lane *Close the review-on-disk debt for 14 lanes*
> (`mvs_54687d45969d461181c10929993039e8`) to satisfy `_main/REVIEW-MODEL.md:41` — control
> **CHK-REV-1**, *"every committed lane has receipts/review-<LANE>.md on disk"*.
> **This file is NOT a transcription. There is no reviewer verdict to transcribe.**
> It records the **absence** of a review, which `_main/REVIEW-MODEL.md:21` calls out as the
> structural failure: *"The system produces review objects faster than it consumes them and
> nothing in the design notices."*
> Every count below was measured by me, read-only, from
> `C:\\Users\\Administrador\\.minimax\\v2\\sqlite\\runtime-state.sqlite` (`file:…?mode=ro`) and from
> the working tree. I wrote **zero** bytes to the store and **touched no existing file**.

---

## ⚠ STATUS — NO REVIEWER VERDICT EXISTS FOR THIS LANE

**Nothing in this file is a review.** It is a control record. Read it as evidence that the lane
is **unreviewed**, never as evidence that the lane is sound or unsound.

**What the lane produced:** owns {owns}.
{receipt_line}

**Context:** {ctx}

> {note}

---

## Verdict

**NO REVIEWER WAS EVER DISPATCHED FOR THIS LANE. There is no verdict line to quote.**

This is deliberately not written as `PASS` and not as `FAIL`. A lane with no review is **not
done**, and it is not failed either — it is **unmeasured against review**, and the only honest
encoding of that state is the one above. Writing `NO - no review found` would smuggle in a
comparison to a spec this lane was never measured against; writing `YES` would manufacture
confidence that does not exist.

**Every one of the four verdicts recovered for this run is the line
`Does your implementation meet the spec? NO - …`.** None carries a bare PASS/FAIL token. So a
search for "PASS"/"FAIL" across the store finds nothing, and finding nothing is **not** evidence
that no reviewer ran. Absence here was established by **session title and `agent_name`**, never
by keyword.

---

## POPULATION and WINDOW

{census}

**Result for this lane: 0 reviewer sessions, 0 verdict lines, 0 findings.**

---

## Findings

**None. There is no reviewer, so there are no findings.**

| id | severity | file:line | what was claimed | what is actually there | the fix | owning lane |
|---|---|---|---|---|---|---|
| — | — | — | **no reviewer exists** | — | **dispatch a reviewer** | {lane} |

**The empty Findings table is the finding.** It is left in place, with its full header, so that
`CHK-REV-3` (*"each defect it found carries an owning lane, so a fix is routable"*) fails
visibly rather than silently: there is no row to route, because nothing was reviewed.

---

## UNVERIFIABLE / do not route as fixes

1. **Everything about this lane's correctness.** No reviewer read it; I did not read its code.
   This file makes **no claim** that the lane is right or wrong.
2. **`CH K-REV-2` and `CHK-REV-4` both FAIL here.** CHK-REV-2 requires the review to name at
   least one `file:line` the reviewer personally inspected — there is no reviewer.
   **CHK-REV-4 is the control: *"a review naming no file:line FAILS"* — this file names zero
   reviewer-inspected lines, so by the control's own letter this file FAILS.** It is published
   anyway, deliberately, because the alternative is a gap that is invisible.
3. **Do not treat this file as covering the lane's gate.** A green `LANEn-GATE PASS` recorded in
   the lane's own receipt is a **self-report**. This repo's `receipts/receipt-26-receipt-audit.md`
   exists precisely because that shape is unreliable, and `review-L4.md` records a lane's own
   verdict being the only thing that had ever checked a claim.
4. **Do not route anything from this file.** There is nothing to route.

---

## The reviewer's own gate doubt

**There is no reviewer, so there is no gate doubt to carry.**

That absence is itself the doubt this project should hold: *the gate that would have produced
this doubt is the thing that never ran.* `_main/REVIEW-MODEL.md:43-47` names CHK-REV-4 as the
arm that matters — *"a review naming no file and no line may have read nothing, and a
file-existence check passes it happily."* **A file-existence check on `receipts/review-*.md`
would count this file as the lane being reviewed. That is the failure mode CHK-REV-4 was written
to prevent, and this file is the first thing on disk that would trigger it.**

The honest control for *this* file is therefore not "does it exist" but the question in the next
section: **does it admit it is not a review?** It does, in the title, in the status box, and in
the empty Findings table.

---

## SELF-AUDIT

**There is no reviewer's SELF-AUDIT to carry, because there is no reviewer.** Writing one here —
even a carefully hedged one — would be the exact failure this project has been bitten by twice:
manufacturing a review that did not happen.

What is **known** about the absence is recorded above, with its population and window. What is
**not** known, and cannot be recovered from the store:

- **Whether a reviewer was dispatched and died before writing anything.** The census finds 0
  sessions titled for this lane, but the store keeps no row for a dispatch that never created a
  session. **Absence of a session is not proof of absence of an intention.**
- **Whether the lane was reviewed *verbally*, inside another lane's turn, and never recorded.**
  Lanes in this fleet were told to dispatch their own verifier; several receipts show a reviewer
  was discussed. **Nothing on disk or in the store carries it.**
- **Whether the lane is actually good.** This file takes no position. That is not modesty — it
  is the only claim the evidence supports.

---

## SELF-AUDIT of THIS persisting lane

**Position.** Read-only against the runtime store (`mode=ro`, no write). Writer of exactly one
new file: this one. I edited **no existing file** — not the lane's receipts, not its code, not
`_main/`, not `src/**`.

**What I verified myself, by measurement:**

| fact | how | result |
|---|---|---|
| 45 lanes/reviewer seats exist under this orchestrator | `SELECT … WHERE parent_session_id='mvs_b7a9f3a7db404912b32d28fc11b83645'` | **45 rows**, all with **0** children — reviewers are siblings, not children |
| how many seats are reviewers at all | same census, filtered `agent_name='verifier'` | **13**, all listed in the table above |
| any seat titled for this lane | title match over all 45 | **0** |
| the file did not already exist | `Test-Path receipts/review-{lane}.md` | **FALSE** — no overwrite risk |

**What I did NOT verify.**

- **I did not read this lane's code, receipts, or gate.** I read receipt *headers* to identify
  what the lane produced. That is identification, not review.
- **I did not re-measure any number the lane published.** Where this file quotes a byte count, a
  line count or a git sha, that is from the working tree at the time of writing, not from the
  lane's own claim being confirmed.
- **I did not check whether the lane was reviewed under a different name.** Two lanes in this
  run appear under two names (`L11`/`aggregate-gate`, `L19`/`receipt-audit`); for those, the
  absence claim is stated per name and could in principle be wrong for the other name.
- **The census is a snapshot.** It was taken at 13:35–13:40 BRT against a store last written
  13:34:46. **A reviewer dispatched after that timestamp would not appear here** — and four were
  in flight when I looked.

**Confidence in MY OWN contribution:** **high** that no reviewer session for this lane existed at
13:40 BRT — it is a mechanical census over 45 rows with the titles printed, so it is checkable.
**Zero** confidence about the lane's quality, because I measured none.
"""

written = []
for lane, subject, owns, receipt_line, ctx, note in LANES:
    fn = "review-%s.md" % lane
    path = os.path.join(OUT, fn)
    if os.path.exists(path):
        print("SKIP (exists): %s" % fn)
        continue
    body = TEMPLATE.format(lane=lane, subject=subject, owns=owns,
                           receipt_line=receipt_line, ctx=ctx, note=note, census=CENSUS)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    written.append((fn, len(body.encode("utf-8"))))

print("WROTE %d files:" % len(written))
for fn, n in written:
    print("  %-34s %d B" % (fn, n))