# Review of LANE L3 — `src/capture/ring_buffer.{h,cpp}`: the ring sized from system RAM

> **Provenance of this file.** Written by lane *Close the review-on-disk debt for 14 lanes*
> (`mvs_54687d45969d461181c10929993039e8`) to satisfy `_main/REVIEW-MODEL.md:41` —
> control **CHK-REV-1**, *"every committed lane has receipts/review-<LANE>.md on disk"*.
> Recovered read-only from `C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite`
> (`file:…?mode=ro`), reviewer session **`mvs_03762d410f7742bba386650146f04cbf`**
> (*"L3 reviewer - ring buffer RAM budget audit"*, agent `verifier`, `session_type=branch`,
> created 12:47:03, last updated 13:07:09 BRT).
> Source rows: **`229790`** (main report: checks, evidence, findings, 11 741 chars) ·
> **`229940`** · **`230066`** (three downgrades) · **`230154`** (SELF-AUDIT, 7 357) ·
> **`230238`** · **`230323`** (closing SELF-AUDIT + verdict, 7 151).
> Recounted live, not taken from a prior lane's census: the session holds **44 message
> rows / 42 assistant**.
> **This file is a transcription, not a review.** Nothing in it was re-measured by me except
> the citation-resolution box, labelled *verified by the persisting lane*, below.

---

## ⚠ HAZARD — READ BEFORE ROUTING ANY `file:line` IN THIS FILE

*Verified by the persisting lane*, `_main/_rv-cite.py` against **`HEAD` = `13e4da225355e16c30b49722c35f5c0e665dd4a2`**
(POPULATION = every distinct `file:line` the verdict names; WINDOW = one run, 2026-10-07 ~13:40 BRT):

| cited file | lines in working tree | lines at HEAD | verdict |
|---|---|---|---|
| `src/capture/ring_buffer.cpp` | 287 | 237 | `:20-53`, `:39-43`, `:81-82` resolve both |
| `src/capture/ring_buffer.h` | 141 | 115 | `:51-53` resolves both |
| `src/capture/replay.cpp` | 645 | 632 | `:38-42`, `:57`, `:130`, `:143-148` resolve both |
| `src/capture/main.cpp` | 621 | 413 | `:145`, `:247` resolve both |
| `src/capture/d3d11_ctx.cpp` | 85 | 85 | `:70` resolves both |
| `receipts/receipt-16-ring-cap-from-system-ram.md` | 189 | 188 | `:42`, `:52`, `:63`, `:75-92` resolve both |
| `_main/_lane3-ringcap-gate.ps1` | 557 | **297** | `:305` **DANGLING at HEAD**; ok in working tree |

**Unlike L4 and L1, this review's citations survive the move.** Every code citation resolves in
*both* bases. One gate citation (`:305`) does not, and `receipt-16` gained exactly one line
between the review and `HEAD`.

**Two disclosures the reader must carry.**

1. **`receipt-16` is self-marked superseded.** Its own header says *"PARTLY SUPERSEDED — read
   `receipt-32-ring-defects-closed.md` first."* F1's target line `:52` is inside the superseded
   document. Fix F1 **in `receipt-32`**, which already records *"Reviewer verdict received: FAIL,
   six findings."*
2. **`src/capture/**` is mid-write right now.** A closure lane
   (`mvs_1d0ddb59c30d4e5d99425076bb4e6822`, *"Fix the six L3 ring-buffer defects"*, 13:13:49) and
   its reviewer (`mvs_cba42e5b9a1f47a6b96d59e11d02fda7`, *"Review the six L3 defect closures"*,
   13:28:35) are live. I did not edit any file under `src/`.

---

## Verdict

The reviewer's own closing line, verbatim, from his **last** turn (`id 230323`):

> Does your implementation meet the spec? NO - The budget policy is correctly implemented and the control arm went red once as claimed, but receipt-16 line 52 publishes 11 934 MiB against the code's own 12 222 MiB (N=3 arithmetic agreement), ring_buffer.cpp:81-82 leaves the allocation-failure branch unreachable so a failed 4 GiB arena aborts uncaught (mechanism proven, 0 aborts observed), replay.cpp:143-148 logs a pre-clamp ring size the arena does not hold (N=0, hypothesis not measurement), the "replay.cpp:57" provenance claim is stale because lane L7 lifted the clamp at 12:26, and ARM A's blindness to the 25% term holds only on this 47.74 GiB host.

The **main report** turn (`id 229790`) carries a second variant, quoted because it differs in a
way that matters — it says *"aborts uncaught, over a cap now twice as large as the code it
replaced"*:

> Does your implementation meet the spec? NO - The budget policy itself is correctly implemented and the control arm works, but receipt-16 line 52 publishes 11 934 MiB where the code and its own line 42 say 12 222 MiB, ring_buffer.cpp:81-82 leaves the allocation-failure branch unreachable (std::bad_alloc aborts, uncaught, over a cap now twice as large as the code it replaced), and the load-bearing "replay.cpp:57 pins 1920x1080" citation is stale because lane L7 lifted that clamp at 12:26.

**Note the third verdict word.** The main report's own heading reads **`## VERDICT: PARTIAL`**
(`229790`) — *"The specified policy is implemented correctly … But two things block PASS."* The
closing line, the dispatch-guard line and the `FAIL` in his SELF-AUDIT (*"**Verdict unchanged:
FAIL.** Findings F1–F6 stand"*) are three different words for one verdict. **No bare PASS/FAIL
token search finds this review; the closing line is the verdict.**

---

## POPULATION and WINDOW

**The reviewer DID state a POPULATION and a WINDOW, for the audit and for each named box.** His
own words: *"**Review date: 2026-10-07 12:47–12:56 −03:00.** Subject bytes: `ring_buffer.cpp`
8238 B, sha256 `082BAF4D…C6D85` · `ring_buffer.h` 5505 B, sha256 `30F34AA3…85A447` ·
`receipt-16` 8949 B, mtime 12:32:45."* And: *"**POPULATION/WINDOW of the whole audit: one
host, 1× RTX 5080 @ 15 979 MiB, 1× 1920×1080 monitor, 12:48–12:57 on 2026-10-07.**"*

His named-box table (`230323`), verbatim:

| box | what it asserts | POPULATION | WINDOW | result |
|---|---|---|---|---|
| `LANE3-ARITH-01` | `min(4 GiB, 25%·ullTotalPhys)` recomputed outside the C++ | 2 independent RAM APIs × 1 recompute | single sample **12:49:57** | PASS (4096 MiB, both paths) |
| `LANE3-REBUILD-02` | code compiles clean and reproduces its numbers | 1 build, 1 execution (rc=0, **0 warnings**) | ~12:54:5x, console-only, no timestamped log | PASS |
| `LANE3-CTRL-03` | pre-change copy fails the control source; current links | 2 builds + 1 execution | **12:46:59–12:47:06** | PASS |
| `LANE3-FALSIFY-04` | poisoned control ⇒ gate rc=1, ARM-D red, evidence restored | **1** invocation | **12:33:33** | PASS — **N=1, no stability claim** |
| `LANE3-FLOOR-05` | failed-query / small-RAM floor path | **0 executions** — hand-synthesised | n/a | **NOT EXERCISED** by the lane's gate |
| `LANE3-OOM-06` | allocation-failure semantics | 2 builds (**1 discarded**), 1 execution at `-O0`, grep = **0 `catch`** in `src/capture/` | ~12:56 | **FAIL (defect)** — mechanism proven, **0 aborts observed** |
| `LANE3-PROV-07` | every receipt-16 number is MEASURED-or-DERIVED and correct | 3 independent computations | 12:49:57, 12:50:26, ~12:54:5x | **1 FAIL (F1)** |
| `LANE3-CITE-08` | is `replay.cpp:57` still the 1080p clamp? | 1 read + 1 grep (8 hits) + 3 mtimes | **12:53:44** | **FAIL (F3)** — it is not |
| `LANE3-SCOPE-09` | diff confined to `ring_buffer.*` | 1 `git diff --no-index` (+66 lines) | 12:52:14 | PASS |
| `LANE3-SPS-10` | real resolution of the 2160p artifacts | 2 files, **decoder invalid** | ~12:55 | **NO CLAIM — withdrawn** |

---

## Findings

Six findings. The main report grades F1–F5; **F6 was introduced by a later turn** and is marked
there as *"introduced by this lane's own change"*:

| id | severity | file:line | what was claimed | what is actually there | the fix (reviewer's words) | owning lane |
|---|---|---|---|---|---|---|
| **F1** | HIGH | `receipt-16:52` vs its own `receipt-16:42`; code `ring_buffer.cpp:39-43` | line 52 publishes *"25 % of RAM would be 11 934 MiB"* | the code, the probe, and **receipt line 42 itself** all say **12 222 MiB**. The 11 934 is 25% of 47 742 — someone divided the **GiB** figure as if it were **MiB**. Recomputed independently: `25% of 48 888 MiB = 12 222 MiB`; `25% of 47 742 MiB = 11 935 MiB`. **The receipt contradicts itself by 288 MiB inside a single table.** | *"`receipt-16:52` — replace `11 934 MiB` with `12 222 MiB`."* **See hazard: fix it in `receipt-32`, not the superseded `receipt-16`.** | L3 |
| **F2** | HIGH | `src/capture/ring_buffer.cpp:81-82`; `--ring-mb` at `main.cpp:145,247` | the allocation-failure branch handles a failed arena | `arena_.assign(...)` then `if (arena_.size() != capacity_bytes) { *err = …; return false; }` — **`std::vector::assign` either succeeds or throws; it never returns short.** Verified at `-O0` that an impossible assign raises `std::bad_alloc`, and grep finds **zero `catch`** anywhere in `src/capture/`. The only "handled" outcome is **unreachable**, and a real failure propagates to `std::terminate`. **This is the one condition where the change is worse than the code it replaced**: the old cap topped out at 2048 MiB, the new permits 4096 MiB, and the budget is computed from `ullTotalPhys` (**total**, not **available**) while this box has 47.74 GiB total but only **17.12 GiB available**. | *"wrap `ring_buffer.cpp:81` in `try { … } catch (const std::bad_alloc&) { *err = "could not allocate the ring arena"; return false; }`, and price the cap off `ms.ullAvailPhys` … rather than `ullTotalPhys` — or state explicitly in the header that the budget is deliberately total-based and that failure is an abort."* | L3 |
| **F3** | MEDIUM | `receipt-16:63`; `_lane3-ringcap-gate.ps1:17-18,187-188,305`; `replay.cpp:57` and `:38-42` | *"`replay.cpp:57` pins the capture window at 1920x1080, so N = 0 runs exist above 1080p"* | **lane L7 lifted that clamp at 12:26.** Line 57 is now `*h = (uint32_t)(mi.rcMonitor.bottom - mi.rcMonitor.top);` and `replay.cpp:38-42` documents the lift in its own comment. `mtime replay.cpp = 12:26:28`, receipt written `12:32:45` — **the receipt was authored after L7 and still cites the old line.** **The conclusion survives; the stated reason does not** — it now rests on the host's only monitor being 1920×1080 and WGC refusing every item (`receipt-18` §2), not on a source clamp that no longer exists. | *"replace the `replay.cpp:57` citation with: 'the 1080p clamp was lifted by lane L7 at 12:26 …; N=0 4K capture runs because this host's only monitor is 1920×1080 and WGC refuses every item (`receipt-18` §2).'"* | L3 |
| **F4** | MEDIUM | `replay.cpp:130` (`d3d_.ring_cap_bytes()`) vs `receipt-16:75-92` | the lane's own words are right, but the fix is not delivered | recorded **as a finding, not praise**: the live path still prices the ring from VRAM. **The product defect (4K60 clipped to 46.54 s) is still live.** The one-line hookup at `replay.cpp:130` is still owed by whoever owns `replay.cpp`. *"This is a lane-boundary consequence, not a lane failure — but the gate is green while the user-visible bug persists."* | apply the one-line hookup `d3d_.ring_cap_bytes()` → `ring_budget_cap_bytes()` | whoever owns `replay.cpp` (not L3) |
| **F5** | LOW | `RING_CAP_FLOOR = 256 MiB`; `ring_buffer.cpp:20-53` | an explicit floor so a small machine still gets a usable buffer | the floor exists and is honest, but on this 47.74 GiB host **it can never bind**, so **ARM A exercises only the ceiling path**. The failed-query branch (`query_ok=false`) is exercised by **0** gate arms. Not a defect — the gap is that the receipt's "What is NOT verified" does not list it. | add a synthetic-total arm that forces the floor | L3 |
| **F6** | MEDIUM→**hypothesis** | `replay.cpp:143-148` | the log reports the true ring size | the log line reports a **pre-clamp** size the arena does not hold. **Downgraded by the reviewer himself** from "Medium-high" to *"**Hypothesis, not measurement. N=0 executions.**"* | one run of `--ring-mb 8192` comparing the log line against `capacity()` — *"**the single most valuable missing check**"* | L3 |

**Three things he checked and explicitly cleared:** the VRAM source was the **correct** one
(`Win32_VideoController.AdapterRAM` reports 4 GiB through a field overflow; DXGI reports
16 755 195 904 B — trusting CIM would have produced a *false* finding against the lane); every
one of the receipt's four seconds-of-ring rows recomputed correct and labelled DERIVED — *"**No
DERIVED-dressed-as-MEASURED found** — this was the specific failure I was told to hunt for, and
it is absent"*; and the lane's scope was clean (diff confined to `ring_buffer.{h,cpp}`,
`d3d11_ctx.cpp` untouched).

---

## UNVERIFIABLE / do not route as fixes

Drawn only from the reviewer's own hedges.

1. **F6 is N=0. Do not route it as a defect.** The reviewer downgraded it himself; it is a
   hypothesis with no execution behind it.
2. **F2's mechanism is proven; its triggering event is not.** *"the specific 4 GiB OOM is a
   reasoned consequence, **not a reproduced abort**."* Zero aborts observed.
3. **F5's floor path has 0 executions**, hand-synthesised.
4. **He never re-ran the lane's gate or the falsify script** — both mutate `_main/logs/*` and
   `_main/_lane3-ringcap-control/`. ARM-D and the falsify are evidenced from **recorded** runs
   plus his own two-sided compile, *"not from a run I launched."*
5. **No repetition of any check.** *"every 'PASS' in this report is N=1 and carries no flakiness
   claim."*
6. **No second host.** Every conclusion is scoped to this machine (47.74 GiB, 1× RTX 5080,
   1× 1920×1080).
7. **The `ullAvailPhys = 17.12 GiB` figure is ONE sample** — *"it evidences that the code ignores
   availability, not any particular availability level."*
8. **Gate blindness to the 25% term is host-scoped.** He corrected his own over-general claim:
   at 8 GiB the term binds and ARM A's recompute would diverge. It holds for ≳16 GiB.
9. **`LANE3-SPS-10` was withdrawn by him** — his hand-rolled SPS decoder returned nonsense
   (46×52) and he *"discarded it rather than build a finding on it."* **No claim survives here.**
10. **Moving target:** `src/capture/**` was written during the review; F1–F3 are pinned to his
    hashes only. *This is now doubly true — a closure lane is editing the same files as this file
    is written.*

---

## The reviewer's own gate doubt

His four doubts, verbatim, from `230323`:

> 1. **ARM A is blind to two of the three policy terms on this host.** `min(4 GiB, f × 47.74 GiB)
>    = 4 GiB` for any `f ≥ 8.38 %`, and the gate's independent recompute applies the *same*
>    ceiling — so `25% → 50%` is invisible. The floor binds only below 1 GiB RAM. The lane **built
>    the seam to test exactly this** (`ring_apply_budget` as a pure function,
>    `ring_buffer.h:51-53`) and then only tested it against the real machine total.
> 2. **ARM D proves API absence by compile failure, not a behavioural difference in the cap value.**
> 3. **ARM B hardcodes the old formula inside the probe** instead of reading `d3d11_ctx.cpp:70`,
>    so an edit to that line would go undetected.
> 4. **The gate is green while the user-visible 4K60 defect is still live** (F4). "LANE3-GATE
>    PASS" must not be read as "4K ring fixed".

**Doubt 4 is the one that matters for routing.** He also rates the control as the thing he most
expected to find broken and did not: *"**The control is real, which is the thing I most expected
to find broken and did not.** … A gate with a working control does not report green
unconditionally."* **Read the two together: the instrument is sound, and it is blind to the
user-visible defect.**

---

## SELF-AUDIT

Carried from the reviewer's own `## SELF-AUDIT` (`230323`), verbatim.

**Protocols missing:** the lane's gate and falsify were never executed by him · no end-to-end
`--ring-mb` run, so **F6 remains an unexecuted hypothesis** · no observed allocation failure ·
**no repetition of any check** · no second host.

**Extra verification beyond the brief:** clean-room recompile from TEMP copies rather than
trusting the lane's log · two-sided compile of ARM-D himself · *"**A deliberate `-O0` rebuild
after the `-O2` run returned an implausible 'no throw'; I distrusted the optimizer's answer
rather than reporting it, which is the only reason F2's throw-semantics claim stands**"* ·
cross-checked the VRAM source · *"**Rejected my own tool result** when the hand-rolled SPS
decoder returned nonsense (46×52): withdrawn rather than reported."*

**Reviewed by another subagent?** *"**No.** The lane's own receipt states 'The reviewer was NOT
dispatched… No independent subagent reviewed this.' I am that first independent review, and
**nobody has reviewed this report** — including its POPULATION/WINDOW census, which is itself
unaudited."*

**His own honest reporting of a form failure:** the session's second-to-last turn opens *"My
previous turn dropped the section while fixing the P0 block. Re-appending it, complete and
closing the report."* — **a required section was dropped once and restored.** It belongs in this
file.

---

## SELF-AUDIT of THIS persisting lane

**Reviewer position.** Read-only; the store was opened `mode=ro` and no byte was written to it.
I did **not** re-run the gate, re-run the falsify, recompile `ring_buffer.cpp`, or re-open a
single finding. I transcribed and I labelled.

**What I verified myself** (1 box, measured):

| fact | command | rc | result |
|---|---|---|---|
| `receipts/review-L3.md` did not already exist | `Test-Path` | — | **FALSE** — no overwrite risk |
| every `file:line` in the verdict resolves? | `py -3 -B _main/_rv-cite.py` | 0 | **7 files, 1 dangling** (`_lane3-ringcap-gate.ps1:305`, 297 lines at HEAD vs 557 in tree); **the 5 code citations resolve in both bases** |

**What I did NOT verify.**

- That **any** finding still reads as claimed. I checked line counts, not line content.
- Whether F1–F6 were **closed**. `receipt-32-ring-defects-closed.md` claims all six were; a
  closure lane and its reviewer are live right now and **neither has produced a verdict yet**.
- Whether `receipt-16`'s `:52` still reads `11 934 MiB`. I confirmed the file is 189 lines in the
  tree and 188 at HEAD — that it changed, **not** that the number changed.
- The 10 named boxes. I carried the reviewer's own POPULATION/WINDOW/result for each; I ran
  **none** of them.

**Per-claim confidence in MY OWN contribution:** high that the citation table is true; high that
the transcription is faithful to the store bytes; **zero** confidence that any finding is still
open or still correct — a closure lane is editing the exact files this review cites.