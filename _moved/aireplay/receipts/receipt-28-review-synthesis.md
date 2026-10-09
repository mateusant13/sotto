# RECEIPT 28 — REVIEW SYNTHESIS: 6 reviewer verdicts → 12 ordered work items

**Lane:** review-synthesis (verifier seat, read-only)
**Question answered:** which reviewer verdicts exist, what concrete defects they name, and what
is the ordered work list a dispatcher can route **without re-deriving ownership**.
**This receipt edits nothing.** Every item is a *routing* record, not a fix.

Reproduce the census with:
`pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\review-synthesis.ps1 -SelfSession <id>`

---

## 0. THE COUNTS

| quantity | value |
|---|---|
| reviewers dispatched for this wave | 6 (L1, L3, L4, L8, L15, L16) |
| reviewers **found** | **6** |
| verdicts **read** | **6** |
| `VERDICT NOT FOUND` | **0** |
| verdicts = PASS | **0** |
| verdicts = NO / FAIL | **6** |
| distinct defects extracted | **39** |
| work items after merging by shared file | **12** |
| items that are merges of >=2 defects | **10** |
| separate dispatches avoided by the merge | **27** |
| claims I re-verified myself | 7 (5 confirm, 2 corrections) |

**6 of 6 reviewers returned NO.** There is no passing lane in this wave. That is the headline;
the detail is that most verdicts are *about the gate that certifies the lane*, not the lane's
main artifact.

### 0.1 Verdict closing lines, verbatim

| lane | verdict |
|---|---|
| L1 | `NO - the trigger fires twice per press on every binding that registers, and no arm can see it.` |
| L3 | `NO - The budget policy itself is correctly implemented and the control arm works, but receipt-16 line 52 publishes 11 934 MiB where the code and its own line 42 say 12 222 MiB...` |
| L4 | `NO - criteria 1, 2, 6 hold and the mutator gate is real, but...` |
| L8 | `NO - the two documents' central load-bearing claim - a PCM tee over the worker's stdin - cannot execute...` |
| L15 | `NO - The mandated question... has the wrong answer, and the a budget cannot fail on the formula it governs.` |
| L16 | `NO - L16's census is sound, but its headline numbers are stale and its own D-1 fix returns zero rows.` |

---

## 1. THE ONE THING THAT MUST BE READ FIRST

**`src/index/**` was REWRITTEN at 13:10:26 - eleven seconds after the L4 reviewer finished at
13:10:15. L4's verdict, the largest cluster in this receipt, was written against files that no
longer exist.**

`git status --porcelain -- src/index`:

```
 D src/index/__init__.py
 D src/index/schema.py
 M src/index/search.py
 D src/index/selftest.py
 M src/index/store.py
?? src/index/_index-green-probe.py
?? src/index/schema.sql
```

Live `src/index/` is now `schema.sql` + `store.py` + `search.py` + `_index-green-probe.py`, all
mtime `13:10:26`. The new `store.py` docstring: *"IDENTITY IS content_key (whole-file SHA-256),
NEVER THE PATH"* - a different vocabulary from the one L4 reviewed, which wrote about `clip_id`,
`producer` tags and `normalise_text`. (`runner.py` never lived under `src/index/`; it is
`src/asr/runner.py`, L9's.)

**Consequence: L4's nine file:line citations are VOID as targets.** A fix lane that opens this
receipt and edits `schema.py:298-302` will find no such file. Re-base first. Per-finding status
against the current tree (my own measurement):

| L4 finding | target | status against the NEW tree |
|---|---|---|
| S1 `migrate()` O(NxM) every open | `schema.py:298-302,341` | **VOID.** `migrate()` is gone. `connect()` runs `executescript(schema.sql)` per call; the only top-level `INSERT` is `INSERT OR IGNORE ... index_meta` (`schema.sql:36`), O(1). *Unmeasured in the new form.* |
| S2 `audio_offset_ms` missing | `store.py:304-305`, `runner.py:233`, `selftest.py:140` | **STILL LIVE.** `audio_offset_ms` = **0 hits** across live `src/index`. |
| S3 OCR lexical channel absent | `schema.py:110-112` | **ALREADY FIXED.** `text_fts` (`schema.sql:164`) + `tr_ocr_fts_ai` / `tr_transcript_fts_ai` triggers (`:173,:189`). |
| S4 nothing writes `state='cutting'` | `store.py:12-13`, `schema.py:77` | **STILL LIVE.** `cutting` = **0 hits**. The repair ladder still has no producer. |
| S5 `clip_id`/`started_at_s` no producer | `replay.h:65-82` | **STILL LIVE.** `replay.h` untouched by the rewrite; grep across `src/capture/*.{cpp,h}` = 0. |
| S6 `producer` hardcoded literal | `store.py:92` | **VOID.** `PRODUCER_ASR` = 0 hits; new store has no producer tag. |
| S7 LIKE cannot fold pt-BR | `store.py:100-115 normalise_text` | **VOID.** `normalise_text` = 0 hits; FTS path writes `text_norm` directly. |
| S8 four spec pragmas absent | `schema.py:335-340` | **PARTIAL.** `cache_size=-16000` (`schema.sql:24`), `busy_timeout=5000` (`:27`) present; **`recursive_triggers`=0, `mmap_size`=0** absent. Spec asks `-65536`. |
| S9 remaining spec divergences | many | **VOID as cited** - new schema uses `content_key`. Re-diff from scratch. |

**Do not re-run L4's fix list. Re-base it.** The three STILL LIVE rows (S2, S4, S5) are the real
work; the other six are history.

---

## 2. WORK ITEMS - ordered by severity, merged by file ownership

Ownership from `_main/ORCHESTRATOR-STATE.md:82-99` (section 4 fleet table). Two items have **no
owning lane**; that is itself a routing defect, marked **OWNERSHIP GAP**.

Legend: **B**=blocker, **H**=high, **M**=medium, **L**=low. `BLOCKS` names what cannot be
finished until the item lands.

---

### W-01 | `receipts/receipt-23-cron-woke-this-session.md` + `_main/RESTART-RUNBOOK.md`
**severity B (CRITICAL) | owner ORCHESTRATOR - OWNERSHIP GAP | 3 defects**

- **L16-S1 (CRITICAL) - the retraction is factually FALSE.**
  `receipt-23:17-20` and `:75` claim message row `227835`'s turn has
  `queue_item_ids_json = NULL`, "not linked to any queue item... RETRACTED".
  **RE-VERIFIED BY ME, read-only, direct query:**
  `queue_item_ids_json = ["queue_4d760084-bc97-4edf-bef4-6dd6399a2556"]`, `claim_source='api'`,
  `client_request_id='queue-delivery:claim_4d856235-...'`, `status='completed'`. Three
  independent fields name the queue item. Attribution is also wrong: `grep -n 227835` finds it
  only in receipt-23 and `RESTART-RUNBOOK.md:16` - **never in `receipt-21`**. L16's real finding
  is about row `225419`, which *is* genuinely unlinked (NULL in all three fields).
- **fix (receipt-23):** delete the "unlinked" claim at `:17-20`; flip `:75` to **PROVEN queue
  delivery** into `mvs_b7a9f3a7` at 12:40:54, POP=1, WINDOW 12:40:54->12:43:50. Keep `:86-89`
  (name the link, don't text-match) - that lesson survives.
- **fix (RESTART-RUNBOOK.md:13-19):** same correction. **This is the file acted on at the next
  restart, so it is the more dangerous of the two.**
- **L16-S2 part / L16-S3 part:** D-1 in receipt-23 `:66-68` keeps MEDIUM; the `:80-84`
  "never landed" claim is false for the session (it landed 12:43:50).
- **BLOCKS:** nothing technical. **Highest urgency by consequence**: a human or a lane acting on
  this runbook at the next restart acts on a falsehood the store contradicts.

---

### W-02 | `src/capture/trigger.{h,cpp}`
**severity B (CRITICAL) | owner L1 | 3 defects**

- **L1-F1 (CRITICAL) - the trigger fires TWICE per press on every registered binding.**
  - `trigger.cpp:262` sets `st.polled = true` for **every** binding (comment `:259-261`).
  - `trigger.cpp:433-455` `poll_once` emits on a rising edge for all bindings; its only read of
    `status_[i].registered` (`:448`) picks a **log note** - nothing suppresses emission.
  - `trigger.cpp:387` the `WM_HOTKEY` pump emits independently.
  - The two guards are private and know nothing of each other: `last_ns[idx]` (`:380-386`,
    pump-only) and `held_[i]` (`:459`, poll-only). `emit()` (`:505-523`) assigns a fresh
    `request_seq = seq_++` and pushes - **no dedup**.
  - Measured by the reviewer on this host: `registered=6 polled_only=3` (refusals `Alt+F9`,
    `PrintScreen`, `F12`), i.e. **6 of 9 bindings double-fire**. F10 is the promoted primary and
    is registered, so F10 double-fires.
  - **Why every arm is green anyway:** each arm drives exactly one path by construction (arm B
    posts a synthetic `WM_HOTKEY` so only the pump exists; arms C/D/E use `prepare_for_test` at
    `:404` which starts no thread). No arm ever has both paths live.
  - **fix:** gate the `poll_once` emission on `!status_[i].registered`, **or** add one shared
    per-binding last-press QPC consulted by both `emit()` sites so the second path suppresses
    within `kRepeatGuardNs` (`trigger.h:28-29` keeps both armed for the UIPI case). **Add an arm
    that arms both paths on one binding, presses once, asserts `cuts == 1`.**
  - **Confidence caveat, carried verbatim:** the reviewer did **not** execute a live two-path
    press (it would inject a keystroke into the owner's session; `trigger.h:154` forbids it).
    This is **CONFIRMED-BY-READING, not a measurement**. The new arm is the measurement.
- **L1-F4 (LOW):** `arm_summary()` (`:554`) computes
  `polled_only = status_.size() - stats_.registrations_ok.load()` in `size_t`; `arm()` (`:272-315`)
  never resets `stats_`, so a second `arm()` wraps to ~1.8e19. Latent today.
  *fix:* reset the counters in `arm()`.
- **L1-F5 (LOW):** `trigger.cpp:380` `last_ns[kQueueCapacity + 16]` = 24 slots, but `:378` bounds
  `idx` only by `bindings_.size()`, which `arm()` takes from any caller. Sized from the QUEUE,
  which has nothing to do with binding count. *fix:* size from the binding count.
- **BLOCKS:** the instant-replay product promise (2 clips per press); and it is the exact input
  that turns W-06's latent single-slot overwrite into a wrong file on disk.

---

### W-03 | `src/capture/build.cmd`
**severity H | owner *NONE* - OWNERSHIP GAP | 1 defect**

- **L1-F2 (HIGH) - receipt-15 section 6 cannot link as written.**
  **RE-VERIFIED BY ME:** `build.cmd:12` compiles 11 files - `main common d3d11_ctx nv12_convert
  wgc_capture nvenc_encoder ring_buffer mp4_writer selftest test_window replay` - and
  **`trigger.cpp` is absent.** No source `#include`s it; no unity build. `aireplay-capture.exe`
  therefore contains zero trigger code.
  *fix:* add `"%SRC%\trigger.cpp"` **immediately before** `"%SRC%\replay.cpp"`. **Do NOT add
  `trigger_selftest.cpp`** - it defines its own `main()` (`trigger_selftest.cpp:352`), which
  collides with `main.cpp`'s.
- **The trap, recorded because it already misled one reader:** the lane's own gate logs
  `STEP 1 build FULL rc=0` (`_main/logs/lane1/lane1-trigger-gate.txt:4-5`) and ARM 0 reports
  `build.cmd` `rc=0` (`:3`). That `rc=0` covers the **other eleven files only**. Every
  behavioural claim about the trigger is a reading of source plus a gate-built binary, never of
  the shipped exe.
- **BLOCKS:** any attempt to apply receipt-15 section 6 (fails at link with undefined refs to
  `Trigger::Trigger/arm/take/disarm` and `default_binding_ladder()`); and W-11.
- **ROUTING NOTE:** no lane in the section 4 fleet table owns `build.cmd`. Assign an owner
  before dispatching, or two lanes will add a line each.

---

### W-04 | `docs/integration-sotto-app.md` + `docs/overlay-hotkey-contract.md`
**severity B (2 blockers) | owner L8 | 6 defects (1 unresolved)**

- **L8-S1 (BLOCKER) - the PCM tee is specified over a channel that is `/dev/null`.**
  `integration-sotto-app.md:213` specifies Engine -> ASR audio as a PCM tee over the child's
  **`stdin`**, and section 1.4's load-bearing rule (`:222`) rests the whole "capture owns the
  endpoint" design on it.
  **RE-VERIFIED BY ME:** `H:\sotto\worker\sotto_worker.py` contains **zero** occurrences of the
  token `stdin` (case-insensitive, whole file; file now 4245 lines). Its sources are
  `--selftest`, `--audio`, `--device`, `SOTTO_AUDIO_FILE`, `SOTTO_FILE_TAP` - no streaming input
  path. The only spawn uses `stdin=subprocess.DEVNULL` - **now at `sotto_webview.py:6686`**
  (the reviewer cited `:6395`; the shell moved).
  *Two corrections to the reviewer, recorded not dropped:* the line number is stale, and the
  worker's line count moved 4593 -> 4245. The **substance** stands.
  Fails **silently**: with DEVNULL every `WriteFile` succeeds and discards (16 kHz s16le =
  32 000 B/s discarded forever). ASR hears nothing, reports nothing, never errors.
  It also violates the doc's **own Rule C** (`:189`, "no thread in the capture path may ever
  block on a consumer") 60 lines after section 1.3 boasts the cut drain is non-blocking (`:151`)
  - the doc contradicts itself and never notices.
  *fix:* section 1.4 must specify an anonymous pipe with a **fixed-size ring and explicit
  drop-with-counter on full**, drained by a dedicated reader thread, plus a note that
  `stdin=subprocess.DEVNULL` + the worker's total absence of a stdin reader make "over stdin"
  **a change to the worker, not a wire format**. Until the worker grows a reader, section 4
  step 3 is not executable.
- **L8-S2 (BLOCKER) - every `replay.*` citation is wrong; not one resolves.**
  `replay.h`/`replay.cpp` moved at 12:25-12:26, after the docs were written at 12:23-12:24.
  16 of 16 checked citations are wrong (e.g. `replay.h:162`->`175`, `replay.cpp:171`->`195`,
  `replay.cpp:216` `ring_.pin`->`:240`). The quoted **code blocks** at `:111-116` and `:127-132`
  are byte-accurate - the reasoning is right, the coordinates are fiction.
  Section 0.1 pins these two files by **line count only**, with **no sha256**, while `trigger.*`
  get full hashes. That asymmetry is what let them rot silently, and a line-count pin cannot
  detect a same-length edit.
  **The fabricated numbers are load-bearing:** section 4 step 1's RED arm ("delete
  `trigger.cpp:346`") now points at `return !quit_.load();` - the gate would delete the wrong
  line and report GREEN.
  *fix:* re-pin all `replay.*` lines; **add sha256/mtime columns to section 0.1.**
- **L8-S3 (MAJOR) - `trigger.*` citations stale, and two now assert the OPPOSITE.**
  `trigger.cpp:21`->`24`, `:26`->`29`, `:28`->`31`, `:59-76`->`82-124`, `:211-215`->`216-223`,
  `:329-346`->`440-459`; `trigger.h:79`->`96`, `:153`->`170`, `:181`->`198`.
  (a) Section 2.2 (`:84-111`) says "F12 goes LAST... this contradicts the code on disk" and
  assigns L1 a hookup to move it - **the lane already did it**: `trigger.cpp:88-105` carries the
  MS quote, F12 sits **last** at `:121`, and `:107-111` records the old rationale as an
  unmeasured claim. Shipping this asks a lane to re-apply a landed fix.
  (b) Section 6.1 "CRITICAL - the poll path ignores `mods`" is **already fixed**:
  `trigger.cpp:442` now tests `held_mods == (bindings_[i].mods & kModifierBits)`.
  *fix:* rewrite 2.2 and 6.1 as **satisfied**, citing `trigger.cpp:88-105/112-124/431-442` +
  receipt-23 - **except** 6.1's companion claim that `kRepeatGuardNs` is unused in the poll path,
  which is also now false (`trigger.cpp:382`).
- **L8-S4 (MAJOR) - the doc misquotes its own brief.**
  Section 0 V1 (`:42`) and section 1.2 (`:77`) both quote the brief as asking how the halves
  **"coexist in one process"**. `coexist` appears in **neither** `LANE-BRIEF.md` **nor**
  `AGENTS.md`. The brief says *"Everything lands in ONE app, under Sotto, frontend LAST"*
  (`LANE-BRIEF.md:21`) - **one app, never one process**. "one process" is `ROADMAP.md:61` (P0) -
  a genuinely contested reading (`:61` P0 vs `:63` P2 "ONE APP").
  The structural argument is **sound and should be kept** (WebView2 cannot host the ring;
  `_gate_form_show` at `sotto_webview.py:3365` proves the host is out-of-process). Only the
  manufactured quote must go - a reader who opens the brief finds no such demand and concludes
  the lane invented the constraint in order to defeat it.
- **L8-S6 (MODERATE):** section 0 V3 (`:44`) and doc2 section 0 (`:28`) both say `receipts/`
  holds **17 files**; actual is **29** now (21 when the reviewer measured) - the lane inherited
  the stale 17 from `LANE-BRIEF.md:31` and, unlike its own trigger pins, did not re-measure. Its
  V3 claim is now **stale in both directions**: `_main/_lane1-trigger-gate.ps1` **exists**
  (11304 B, 12:32:25) and `receipts/receipt-23-trigger-defects.md`, cited by `trigger.cpp:440`,
  **does not exist**. Honest-limitation case: correct when written, overtaken by a live lane.
  Minor: `docs/research/03-nvenc-sessions.md` vs `receipts/receipt-03-nvenc-sessions.md`.
- **L8-S7 (MINOR), one half UNRESOLVED:** section 1.5 F9 (`:250`) cites `main.cpp:367` for
  `last_cut_` - that line prints `c.ring_dropped_at_cut`; `last_cut()` is read at `main.cpp:296`.
  The claim is true, the citation wrong. Section 1.3 (`:156`) cites `test_window.cpp:197` for
  `WaitForSingleObjectEx`; `:197` is an unrelated note line. **The reviewer explicitly left this
  one open** ("let me grep ... before publishing the fix"). **CARRIED AS UNVERIFIED - do not
  treat it as a located defect.** Someone must grep the real line before it is written down.
- **NOT A DEFECT - do not "fix" it:** L8-S5 verified the 86 `BRIDGE_DEATH` bet exactly
  (`AGENTS.md:456-458`), and found the mechanism the doc's rule-2 argument needs at
  `AGENTS.md:455` ("the holder is usually ITS OWN PREDECESSOR"). The doc's one omission:
  `AGENTS.md:465` records the bug as **already fixed**, which the docs never mention.
- **BLOCKS:** W-02's product claim (S1 is the integration edge), and any lane trusting section
  4's RED arm coordinates.

---

### W-05 | `src/index/**`
**severity B (3 rows still live) | owner L4 | 9 rows: 3 LIVE, 1 PARTIAL, 5 VOID - REBASE FIRST**

**Read section 1 of this receipt before dispatching this item.** L4's verdict was written
against a tree replaced at 13:10:26. The three live rows:

- **L4-S2 (BLOCKER) - STILL LIVE.** `audio_offset_ms` = 0 hits repo-wide under `src/index`.
  Absolute-wav times are written as clip-relative; a hit on a 120 s clip at `offset_s=900` is
  **unseekable** (stored `914320` on a 120 s clip). The spec's own registered fixture is
  `plain-3600s.wav[900,1020)` (spec 1.3). The old gate was blind because its fixture hardcoded
  `offset_s = 0.0`. *fix:* add `video.audio_offset_ms INTEGER NOT NULL DEFAULT 0`; store
  `start_ms = audio_offset_ms + round(start*1000)`; set the fixture to `offset_s=900`.
- **L4-S4 (HIGH) - STILL LIVE.** `cutting` = 0 hits. Nothing ever writes `state='cutting'`, so
  spec 2.5's repair ladder **has no producer at all**, and the code writes the file *first*, row
  second - the one loss its own spec calls unrecoverable. *fix:* **the spec wins** (it is a
  correctness invariant, not naming): add a T0 anchor write before remux, keep the existing call
  as T2. This changes L1's call site.
- **L4-S5 (HIGH) - STILL LIVE.** `CutResult` (`replay.h:65-82`) has no `clip_id` and no
  `started_at_s`; grep across `src/capture/*.{cpp,h}` = **0**. L1's first call raises
  `ValueError: index: clip payload has no clip_id; refusing to invent one`.
  *fix:* in the receipt, name who mints `clip_id` and from which `CutResult` field (e.g.
  `base_abs`/`cut_qpc_ns` -> epoch), and give the exact L1 line filling `started_at_s`.
- **L4-S8 (MEDIUM) - PARTIAL.** `cache_size` and `busy_timeout` now exist; **`recursive_triggers`
  and `mmap_size` are still 0**; spec 1.1 asks `cache_size=-65536`, the file has `-16000`.
- **VOID rows:** S1, S3, S6, S7, S9 - see the table in section 1. **S3 is already fixed by the
  rewrite** (`text_fts` + FTS triggers now exist).
- **UNMEASURED, do not assume:** the quadratic-`migrate` class (S1) is gone because `migrate()`
  is gone, but `connect()` now runs `executescript(schema.sql)` on **every** open. The only
  top-level `INSERT` is a one-row `INSERT OR IGNORE` into `index_meta` (`schema.sql:36`) and the
  per-row `INSERT INTO text_fts` statements are inside trigger bodies - so it reads as
  idempotent and O(1). **Nobody has measured the new open path at 20k rows**, which is exactly
  the measurement that killed S1. Run it before declaring the row closed.
- **BLOCKS:** W-02's end-to-end claim. Without S5 there is no callable index interface, so the
  trigger->index path cannot be exercised at all.

---

### W-06 | `src/capture/replay.{h,cpp}`
**severity M (but HIGHEST COLLISION RISK) | owner L7 | 4 defects from 3 DIFFERENT LANES**

> **This is the merge the dispatch brief exists for.** L3, L15 and L4 each raised a defect in
> `replay.cpp` independently. Dispatched separately, three writers touch one file. **Dispatch it
> once, to L7.**

- **L3-F4 (MEDIUM) - the live path still prices the ring from VRAM.**
  **RE-VERIFIED BY ME:** `replay.cpp:130` is `uint64_t cap = d3d_.ring_cap_bytes();` - unchanged.
  The lane's own receipt (`receipt-16:75-92`) is honest that the fix is *"bounded, NOT yet
  delivered end-to-end"*. **The product defect (4K60 clipped to 46.54 s) is still live**, while
  the gate is green - anyone reading "LANE3-GATE PASS" as "4K ring fixed" is wrong. A
  lane-boundary consequence, not a lane failure.
  *fix:* the one-line hookup at `:130` - `d3d_.ring_cap_bytes()` -> `ring_budget_cap_bytes()`.
- **L3-F6 (MEDIUM-HIGH, *introduced by L3*) - the log reports a ring size the arena does not
  have.** `replay.cpp:143-148` prints `chose`, computed **before** `init()` clamps at `:177`;
  `ring_apply_budget` (`ring_buffer.cpp:49-53`) can reduce capacity below `chose`, and
  `seconds_kept` is **discarded at `:149`** (`(void)seconds_kept;`) so nothing corrects the line.
  **RE-VERIFIED BY ME:** `:149` is exactly `(void)seconds_kept;`.
  Reachable: `main.cpp:145` accepts any `--ring-mb`, so `--ring-mb 8192` prints
  **"CHOSE 8192 MB" while the arena holds 4096 MiB**. The clamp is new in L3, so the log was
  accurate before and lies now.
  *confidence:* code reading + call-graph, **not executed** - named by the reviewer as "the one
  finding I would most want executed".
- **L15 - same line, same defect, from a second reviewer:** stop discarding `seconds_kept` at
  `replay.cpp:149` (L15 cites it as *the one real coupling* between spec 07 and this lane).
  **Merge with L3-F6 - do not dispatch twice.**
- **L4-S5 (part) - `replay.h:65-82`:** `CutResult` cannot carry `clip_id`/`started_at_s`.
  Cross-listed in W-05; the **producer decision belongs to L7** (it owns `replay.h`).
- **BLOCKS:** the 4K ring defect and spec 07's coupling both close here.

---

### W-07 | `src/capture/ring_buffer.{h,cpp}` + `receipts/receipt-16-*` + `_lane3-ringcap-gate.ps1`
**severity H | owner L3 | 6 defects**

- **L3-F1 (HIGH) - a published number is wrong and self-contradictory.**
  `receipt-16:52` says *"25 % of RAM would be 11 934 MiB"*; the code, the probe, and **its own
  line 42** say **12 222 MiB**. The 11 934 is 25 % of 47 742 - the **GiB** figure divided as if
  it were MiB. The receipt contradicts itself by 288 MiB inside one table.
  *fix:* `receipt-16:52` -> `12 222 MiB`.
- **L3-F2 (HIGH) - the allocation-failure branch is dead code and the process aborts.**
  `ring_buffer.cpp:81-82` checks `arena_.size() != capacity_bytes` after `assign()` - but
  `std::vector::assign` either succeeds or **throws**; it never returns short. There is **no
  `try`/`catch` anywhere in `src/capture/`**, so a real failure reaches `std::terminate`.
  **This is the one condition where the change is worse than the code it replaced**: the old cap
  topped at 2048 MiB, the new permits 4096 MiB and `--ring-mb` can request arbitrarily large -
  and the budget is computed from `ullTotalPhys` (**total**, not **available**; this box has
  47.74 GiB total but **17.12 GiB available**), i.e. it ignores exactly the quantity that
  decides whether the allocation succeeds.
  *fix:* wrap `:81` in `try { ... } catch (const std::bad_alloc&) { *err = "..."; return false; }`,
  and price off `ms.ullAvailPhys` - or state explicitly in the header that failure is an abort.
- **L3-F3 (MEDIUM) - stale provenance.** `receipt-16:63` and
  `_lane3-ringcap-gate.ps1:17-18,187-188,305` claim *"`replay.cpp:57` pins 1920x1080, so N=0
  runs above 1080p"*. **L7 lifted that clamp at 12:26** (`replay.cpp:38-42` self-documents it;
  mtime 12:26:28 < receipt 12:32:45). **The conclusion survives, the reason does not**: N=0 4K
  *capture* runs because the only monitor is 1920x1080 and WGC refuses every item
  (`receipt-18` section 2), not because of a clamp that no longer exists.
- **L3-F5 (LOW):** `RING_CAP_FLOOR = 256 MiB` can never bind on this host, and the
  `query_ok=false` branch is exercised by **no** gate arm - the reviewer's own probe had to
  synthesize it. The gap is that the receipt's "NOT verified" section does not list it.
- **L3 gate blindness (the deepest finding in this lane's review).** ARM A is structurally blind
  to two of three policy terms here: `min(4 GiB, f x 47.74 GiB) = 4 GiB` for **any**
  `f >= 8.38 %`, and the gate's recompute (`_lane3-ringcap-gate.ps1:138-143`) applies the same
  ceiling, so **it agrees with the mutation**. The proportional rule is unobservable on this
  machine. The lane *built the seam to test this* - `ring_apply_budget` is pure "so the clamp can
  be tested without committing gigabytes" (`ring_buffer.h:51-53`) - and only ever tested it with
  the real machine total.
  *fix:* add arms calling `ring_apply_budget` with synthetic totals (2/8/64/1 GiB) asserting
  the floor binds below 1 GiB and the 25 % term binds between 16 and ~16.4 GiB. Also ARM B
  re-implements the old formula *inside the probe* instead of reading `d3d11_ctx.cpp:70`, so an
  edit there is undetected.
- **L3 `receipt-16:147-149`** says `--ring-mb` *"still bypasses the cap unclamped"* - which
  contradicts its own next sentence and is **wrong**: the clamp *does* apply, silently, under a
  log line that now lies (see W-06/L3-F6).
- **VERDICT-FORM NOTE (not a defect, recorded so it is not lost):** L3's report header reads
  `## VERDICT: PARTIAL` while its mandated closing line reads `NO - ...`. **Not normalized.** The
  closing line is the verdict of record; the header disagrees with it.

---

### W-08 | `specs/07-highlights.md` + `_main/oracle-07-highlights.py`
**severity B (2 critical) | owner L15 | 5 defects (1 upheld, no action)**

- **L15-S1 (CRITICAL) - the mandated question has the wrong answer.**
  `specs/07-highlights.md:429-436` (Appendix B) answers *"would this heuristic call a random 30
  seconds of a walk in the park a highlight?"* with **"NO - the number that says so is the
  1.22x dynamic range against a 3.0 gate."**
  The walk corpus is `synth_walk_bed` - pink noise x a 23 s sine wander, **no impulsive
  content**. A walk is footsteps: sharp broadband transients. The reviewer built that signal
  (quiet bed + two 90 ms footfalls per stride) and ran the spec's **own rule, unmodified, at its
  own parameters**: **36 of 36 configurations fire, 5-9 emits per 180 s, 12 of 36 fail the alpha
  gate outright.** Footsteps *raise* dynamic range (dr 10-25) - exactly what `GATE 0` rewards. It
  is a **silence detector wearing a highlight detector's clothes**: rain, a slammed door,
  keyboard clatter and gunfire all sail through. At `MIN_GAP_S=20.0`, 6 emits x 14 s =
  **46.7 % of the walk clipped as "highlights"** (85.6 % at 10.0).
  The trace the spec claims rests on `dr = p99/p50 = 2.224`; the number it prints (1.22x) is the
  **tone's** `max/p50` from `:89` - it does not belong to the arm it is quoted for.
  **Why it cannot be tuned:** the only thing stopping the walk is `MIN_GAP_S`, and section 3
  derives that refractory against **speech** statistics (median 6.98 s, max 13.82 s). Footsteps
  yield 11-197 segments in 120 s - a different regime the value was never derived from. There is
  no term that distinguishes "someone said something" from "something made a noise".
  *fix:* the honest answer is **"the rule calls a walk a highlight - measured, 36/36"**. Then
  either (i) state the rule is **not shippable as a moment detector on audio alone** (this
  strengthens 5.2 and Appendix A point 2), or (ii) add a `non-speech` rejection independent of
  `dr` - which needs a spectral-flatness primitive `src/asr/level.py` does not provide, i.e. a
  **new primitive, not a parameter**. Delete the 1.22x figure from the walk row.
- **L15-S2 (CRITICAL) - the alpha budget cannot fail on the formula it governs.**
  Section 3 (`:172-177`) calls `THRESHOLD=0.75` *"load-bearing rather than decorative"*.
  Sweeping it: **0.75 / 0.50 / 0.40 / 0.20 / 0.00 all give emits=3, rate=15.00/10min -
  identical.** The lowest score on the whole corpus is 0.9884, already above 0.75. **The entire
  measured rate is produced by `MIN_GAP_S = 20.0`.** `W_E` is near-inert too:
  `PEAK_REFERENCE_S = 300.0` (`:339`) exceeds every corpus in the oracle (longest 180 s), so
  `lo = 0` for **every** candidate and `ref` is p99 over the whole prefix - the "trailing
  normalisation window" **no corpus ever exercises**. It is `UNKNOWN` in production and must be
  labelled as such (the spec's own provenance rule, `:4-6`, demands it).
  *fix:* state plainly that `THRESHOLD` and `W_E` are inert on every measured corpus and the
  rate is all `MIN_GAP_S`; lower `PEAK_REFERENCE_S` below corpus length or add a >300 s corpus;
  re-derive alpha from the refractory ceiling (600/20 = 30.0) or declare it
  `ARBITRARY UPPER BOUND`.
- **L15-S3 (MAJOR) - the containment arm, the spec's own named "FP claim", is tautological.**
  `specs/07-highlights.md:276` calls A0 containment *"this is the FP claim"*.
  **RE-VERIFIED BY ME:** `oracle-07-highlights.py:156` is `cands = segs` - non-naive candidates
  **are** the segments, so the containment counter (`:212-213`) can only ever read 0, because an
  emit's `t` is an `argmax` *within* `[a,b)`. The reviewer confirmed it by deleting both guards
  (`MIN_GAP_S=0`, `THRESHOLD=0`): still `outside_speech=0` over 11 segments. **A gate that cannot
  go red is not a gate.** A3 (`:293-296`) does not rescue it - it tests a *different* rule.
  *fix:* stop calling containment the FP claim; emit on a window grid and count lands outside a
  segment, or assert containment is structural and move the FP burden onto A1/A2.
- **L15-S5 (MINOR):** three stale citations (`replay.cpp:125`->`:149`, `trigger.h:99-103` is the
  `CutRequest` struct - `span_seconds()` is `:120`, `trigger.h:47-53` is a comment about a
  deleted receipt-15) plus `level.py:45` (class) -> `:146` (what the oracle calls). The drift is
  **not L15's error** - those files changed at 12:26/12:33 after 07 was frozen at 12:22 - but a
  spec citing a line number as *"the one real coupling"* (`:219-220`) should anchor on a
  **symbol** (`(void)seconds_kept`), not a line.
- **L15-S6 (MINOR):** `:89` labels one row "dynamic range `p99/p50`" = 19.90-24.76x; measured
  `p99/p50 = 19.897` and `max/p50 = 24.764` - two metrics under one label. Split the rows.
- **NOT A DEFECT:** L15-S4 (section 1.1 availability) **upheld** - POPULATION=28, WITH_AUDIO=1,
  and that one file is an ffmpeg synthetic, so 27/27 capture outputs are video-only. Clean.
- **BLOCKS:** nothing technically, but spec 07 is cited as a **decision input**; shipping the
  current Appendix B means shipping a measured-wrong headline answer.

---

### W-09 | `receipts/receipt-21-wake-mechanism-audit.md`
**severity H | owner L16 | 5 defects**

- **L16-S2 (HIGH) - D-1's causal role is REFUTED, not "unproven."**
  `receipt-21:296` keeps D-1 at MEDIUM on "a delivery where our 48-char id **is** the delivered
  `msg_id`". **That falsifier has fired**: `msg 227835.msg_id =
  msg-user-v1-wake14c1ccd40a834dceaf30d1001571ce95` (48 chars) and
  `backup-20261007-124054-inject-11b83645.json -> queue_4d760084.userMessageId` is
  **identical**. The wrong-shape id did not block, delay or corrupt anything. **D-1 is cosmetic -
  downgrade to LOW**, and keep receipt-23 `:66-68` in step.
  Two dependent claims invert: `receipt-21:211` "POP of `msg-user-v1-wake%` rows = **0**" is now
  **2**; `:213-215`'s "any dedupe keyed on the id we invented cannot match" is contradicted.
- **L16-S3 (HIGH) - "the wake never landed at all" is false for the session, and the mechanism is
  backwards.** `receipt-21:80-84`; `:98-100` says it *"cannot fire into a busy session"*.
  Turn ingress for `mvs_b7a9f3a7db404912b32d28fc11b83645` shows the wake **did** land at
  **12:43:50**, the instant the prior turn completed. The `queue_cf6aed5b` negative is true **of
  that one item only** (POP=1, already correct in receipt-23 section 4). And the cited refusal is
  the **foreground `mcode exec` path** - the queue exists precisely to deliver *after* the active
  turn. The real defect is the silent 22-attempt retry loop, already listed at `:197`.
- **L16-S4 (MEDIUM) - D-2's proposed fix returns 0 rows too.**
  `receipt-21:222-225` ships `like '%* * * * *%'` (0 rows) and proposes `'%* * * *'`. Measured: the
  **proposed fix also returns 0**; `'%* * * *%'` returns 10; `json_extract(...'$.kind')='cron'`
  returns 12. Reason the receipt never states: **SQL `LIKE '%X'` anchors at end-of-string**, and
  these values end `"America/Sao_Paulo"}`. **Credit due:** the downstream lane caught this
  independently (`wake-fix.py:113-116` says so verbatim) - **the receipt is the stale artifact,
  not the code.**
- **L16-S6 (MEDIUM) - the gate headline no longer reproduces.** `receipt-21:7-8` claims the gate
  *"prints `LANE16-GATE PASS`, exit 0"*. `_lane16-gate.out.txt` (mtime 12:56:15, **not written
  by the reviewer**) ends `ARMS=19 FAILED=1 / LANE16-GATE FAIL` on
  `B5-minted-userMessageId-shape`. This is the gate **working** - the negative stopped
  reproducing - and it is the same measurement that refutes D-1. *fix:* state the 12:40:02 run
  passed under pin `heartbeat.ps1 17206EAB...`, a later run is red on B5, give both pins.
- **L16-S7 (LOW):** `receipt-23:31-34` states POP=78/78 as a standing fact; measured **78 -> 79
  -> 80** across four snapshots, each 100 %, 0 counter-examples. The **ratio** survives, the
  **number** was stale within minutes - receipt-23 dropped the window. Also: **two files are
  numbered `receipt-23`**, and `receipt-24` does not exist, so **receipt numbering is no longer a
  reliable citation key**. Scope note in L16's favour: the `claim_source='api'` filter excludes
  **456** queue-linked turns, 455 of which carry a user row - the 78/78 is sound *within its
  stated population*, the population is just narrow. **State it.**
- **BLOCKS:** nothing downstream; this receipt is a citation target for the wake mechanism.

---

### W-10 | `_main/_lane16-wake-gate.ps1`
**severity M | owner L16 | 3 defects - THIS ITEM CHANGES WHAT EVERY "PASS" MEANS**

- **L16-S5 (MEDIUM) - of 6 controls, two are decorative and the load-bearing one asserts almost
  nothing.**
  - **D2 control-expiry - the dangerous one.** `$cureRc -match '0'` is a **substring regex, not
    equality**. Verified by the reviewer: `'20,2,2,2,2' -match '0'` -> **True**. **D2 passes with
    4 of 5 injections still refusing.** D1 correctly uses `-eq '2,2,2,2,2'`; D2 does not. The
    sentence at `:182` (*"Only the cure changes the outcome, which is what makes D1 a real
    control"*) is **unsupported by the arm as written**.
    *fix:* `-match '0'` -> `-eq '0,0,0,0,0'` at `:527`.
  - **A1 - weakest headline gate.** Query is `limit 20` (`:102`) and the arm requires only **1 of
    20**. The `78/78` headline is printed in the detail string and **never asserted**. 59 of 78
    could lack a user row and A1 passes.
  - **A2 - not a cure control.** Asserts >=1 unlinked marker-matching user row exists -
    monotonically easier as hand-pushes accumulate. Demonstrates the false-positive class;
    certifies nothing about the cure.
  - **B4 - decorative.** `cron_runs_pop -gt 0` on a table holding 1 442 rows that only grows.
    **Cannot fail.**
  - **C4 - genuine and two-sided** (truncated copy -> 0 fires; 180-min window -> 22 fires). The
    only control that would catch a broken parser.
- **BLOCKS:** the meaning of **every** green `LANE16-GATE PASS`, past and future. Until D2 is
  fixed, the gate cannot distinguish "cure works" from "most things still refuse."

---

### W-11 | `receipts/receipt-15-instant-replay-trigger.md`
**severity M | owner L1 | 2 defects**

- **L1-F3 (MEDIUM):** `:110` quotes `STEP 2 sha256 fixed = B2495E4A80C38A3D...`; the current
  `trigger.cpp` hashes `241A9BF08D8951AF...`. The transcript predates lane-23's edits and the
  receipt **carries no note saying so** - a reader takes `:104-122` as current.
  *fix:* one line above the block: *"Transcript captured at `B2495E4A...` (pre-lane-23). The
  current revision is `241A9BF0...`; its gate run and the modifier/F12 cures are in receipt-23."*
  (a cross-reference, not new evidence).
- **L1-F2 tail:** section 6 must **name the build.cmd step** (W-03). Today its "Limits"
  (`:198-199`) says only *"I did not touch ... `build.cmd`"* - which reports the omission without
  naming its consequence.
- **BLOCKS:** W-03.

---

### W-12 | `_main/wake-fix.py`
**severity M | owner UNNUMBERED FIX LANE - OWNERSHIP GAP | 1 defect**

- **L16-S2 tail:** `:54` and `:485` cite **`receipt-24`, which does not exist** (`receipts/`
  holds 01-23 and 27). A fix lane rests on a citation no reader can open. The lane's own comment
  at `:53` already states the correct conclusion (*"IT IS NOT THE CAUSE"*) - **the code is right
  and the citation is a dangling pointer.** *fix:* write receipt-24 or repoint both lines at the
  measurement that exists.
- **BLOCKS:** nothing. Lowest urgency of the twelve; a one-line honesty repair.

---

## 3. THE BLOCKING GRAPH (what to dispatch first)

```
W-01  receipt-23 + RESTART-RUNBOOK   -> acted on at NEXT RESTART, on a claim the store
                                       contradicts. Highest consequence, zero dependencies.
                                       DISPATCH FIRST regardless of severity ordering.

W-03  build.cmd (NO OWNER)           -> blocks W-11 and any receipt-15 section 6 hookup attempt.
    └── needs an owner assigned first.

W-05  src/index (rebase required)    -> blocks the trigger->index path end to end.
    └── S5 needs a producer decision that lands in W-06 (replay.h).

W-02  trigger.cpp F1                 -> the trigger double-fires on 6 of 9 bindings.
    └── feeds W-06: the duplicate press is exactly what turns replay.cpp's single-slot
        overwrite into a wrong file on disk.

W-06  replay.cpp (3 LANES, 1 OWNER)  -> MERGED. Highest collision risk. Dispatch ONCE to L7.
    └── carries W-05's producer decision (replay.h:65-82)

W-10  lane16-wake-gate D2            -> blocks the MEANING of every green LANE16-GATE PASS.

W-07 / W-08 / W-04 / W-09 / W-11 / W-12 -> independent; parallelisable per owner.
```

**Dispatch order, if lanes are the constraint:** W-01 + W-10 (L16, small, high value) -> W-02
(L1) -> W-06 (L7, alone) -> W-07 (L3) -> W-05-rebase (L4) -> W-04 (L8) -> W-08 (L15).
**W-03 and W-12 need an owner assigned before they can be dispatched at all.**

---

## 4. THINGS I DID NOT DO, AND WHAT IS UNVERIFIED

**Unverified, carried as unverified (not upgraded, not dropped):**

1. **L8-S7's second half.** The reviewer explicitly left `test_window.cpp:197` **unlocated**. The
   claim (`WaitForSingleObjectEx` ~1 ms quantisation) is plausible; the citation is wrong;
   **nobody has found the right line.** Someone must grep before it is written down.
2. **L1-F1 is confirmed-BY-READING, not measured.** No live two-path press was run - it would
   inject a keystroke into the owner's session (`trigger.h:154` forbids it). The new arm is the
   measurement that would settle it. **Do not report it as a measured number.**
3. **L3-F6 likewise.** Code reading + call-graph, never executed. Named by the reviewer as "the
   one finding I would most want executed".
4. **L3-F2's 4 GiB OOM.** Proven by language semantics + an `-O0` `bad_alloc` repro + the absence
   of any `catch` - **not** by an observed abort of the real binary.
5. **The new `src/index` open path is UNMEASURED at scale.** W-05's voided S1 was killed by a
   measurement at 20k rows. The replacement has never been measured that way.
6. **L3's four `seconds_of_ring` rows and the seconds table were independently recomputed and are
   correct.** Recorded so it is not re-litigated.
7. **L16's 78/78 census was recomputed from scratch over the full population (79/79, then
   80/80, 0 counter-examples) - the claim is TRUE; only its staleness and its weak gating are
   wrong.** Also true and worth keeping: `queue_item_ids_json` is the authoritative instrument,
   and row `225419` **is** genuinely unlinked (sha256 `8953abb1ca9d9ea3`).

**Process findings about the reviews themselves:**

- **Most of these verdicts are about the gate that certifies the lane**, not the lane's artifact.
  L3 (gate blind to 2 of 3 policy terms), L4 (gate only ever builds 9 segments), L15 (containment
  arm cannot go red), L16 (D2 asserts nothing, A1 samples 20). The gates are **honest about what
  they test** - they are narrow, not lying. **A green `LANE*-GATE PASS` is currently worth much
  less than it reads.**
- **L3's report contradicts itself on severity** (`## VERDICT: PARTIAL` vs closing line `NO`).
  Recorded, not normalized.
- **Three of six reviewers had no final report when this synthesis started.** At 12:50, L4 had
  emitted 3.9 KB total and L16 1.8 KB with no verdict line; both were still mid-run. L3 and L4
  finished at 13:05-13:10. **A synthesis lane dispatched in parallel with reviewers must poll to
  completion, not assume** - reading the queue at dispatch time would have produced a 3-of-6
  receipt and called it done. (This is why the census is a script and not a claim.)
- **`mcode session list` is not a subcommand** - the suggested command does not exist in this CLI.
  Reviewer sessions are only reachable through the runtime store's message rows.
- **My own census had a bug I had to fix before trusting it:** the first run counted the synthesis
  lane itself as a 7th reviewer (`REVIEWERS_FOUND=7` against 6 real reviewers). There is no
  runtime env var carrying the current session id on this host, so it cannot be auto-detected -
  hence the `-SelfSession` parameter on `review-synthesis.ps1`, which is where the lesson now
  lives.

---

## 5. WHAT I VERIFIED MYSELF (7 checks; 5 confirm, 2 corrections)

| # | claim | method | result |
|---|---|---|---|
| 1 | **L16-S1: row 227835 is NOT queue-linked** | direct read-only query of `local_runtime_turn_ingress` | **REFUTED - reviewer is right.** `queue_item_ids_json = ["queue_4d760084-..."]`, `claim_source='api'`, `client_request_id` prefixed `queue-delivery:` |
| 2 | **L1-F2: `build.cmd` omits `trigger.cpp`** | grep of `build.cmd:12` | **CONFIRMED.** 11 files compiled, `trigger.cpp` absent, `replay.cpp` present |
| 3 | **L8-S1: worker has no stdin reader** | full-file case-insensitive scan of `H:\sotto\worker\sotto_worker.py` | **CONFIRMED** - 0 occurrences of `stdin` |
| 4 | L8-S1's line number `sotto_webview.py:6395` | grep `DEVNULL` | **CORRECTION.** Now at **`:6686`**; worker now 4245 lines (reviewer read 4593). Substance holds |
| 5 | **L3-F4: `replay.cpp:130` still VRAM-priced** | grep `ring_cap_bytes` | **CONFIRMED EXACTLY** - `uint64_t cap = d3d_.ring_cap_bytes();` |
| 6 | **L3-F6: `seconds_kept` discarded at `:149`** | grep `seconds_kept` | **CONFIRMED EXACTLY** - `:149` is `(void)seconds_kept;` |
| 7 | **L15-S3: containment arm tautological** | grep `cands\s*=` in `oracle-07-highlights.py` | **CONFIRMED EXACTLY** - `:156` is `cands = segs` |

Plus the **section 1 finding no reviewer could have had**: `src/index/**` replaced at 13:10:26,
11 s after L4 finished, voiding 6 of its 9 findings as targets. Verified with
`git status --porcelain -- src/index` and a term sweep of the live tree.

**Environment note:** read-only throughout. No lane file was edited. Temporary reviewer
transcripts live in `G:\Temp\revdump\` and census temp dirs under `%TEMP%`; the only files this
lane wrote are this receipt and `_main\review-synthesis.ps1`. Every native process was launched
with `Start-Process -WindowStyle Hidden` and its exit code read off the process object, never
through a pipe (LANE-BRIEF hard rules 1 and 2).

---


---

## 6. AMENDMENT (13:24) - THE REPO MOVED WHILE THIS RECEIPT WAS BEING WRITTEN

A fix lane was landing fixes **during** the synthesis. Re-running every line target against the
live tree (this repo's own rule: *treat every line number as a HINT and re-run the grep*) changes
the status of three items. **This receipt is a snapshot; the table below is the later truth.**

### 6.1 Items now FIXED or VOID - do not dispatch

| item | finding | status now | evidence |
|---|---|---|---|
| **W-07** | **L3-F2 (HIGH)** dead `catch`-less allocation branch | **FIXED 13:18:57** | `ring_buffer.cpp:112` `arena_.assign(...)` is now inside a `try`; `:113` `catch (const std::bad_alloc&)`, `:120` `catch (const std::length_error&)`. Comments at `:107`/`:109` name the old defect. |
| **W-06** | **L3-F4 (MEDIUM)** ring still priced from VRAM | **FIXED 13:19:20** | `replay.cpp:133` is now `uint64_t cap = ring_budget_cap_bytes();`; `:131` is a comment recording that it *used to* be `d3d_.ring_cap_bytes()`. **The 4K60-clipped-to-46.54s product defect is closed.** |
| **W-06** | **L3-F6 (MED-HIGH)** log reports pre-clamp size; `seconds_kept` discarded | **FIXED 13:19:20** | `(void)seconds_kept;` is gone. `:153` recomputes `seconds_kept` from post-clamp `ring_cap_`, and `:160` passes it into the log line. |
| **W-12** | dangling `receipt-24` citation in `wake-fix.py` | **RESOLVED** | `receipts/receipt-24-clip-to-asr-chain.md` now exists (18312 B, 13:20:10). `wake-fix.py` was re-edited at 13:12:33 and its citations moved to `:61` and `:493` (the reviewer cited the pre-edit `:54`/`:485`). The pointer now resolves. |
| **W-08** | L15-S1/S2/S3 on `specs/07-highlights.md` | **TARGET VOID - REBASE** | **`specs/07-highlights.md` no longer exists** (git: `D specs/07-highlights.md`). `specs/` now holds `07-engine-process.md` at **936 B** - a stub - and `06-broadcast-and-capture-card.md` has grown to 52679 B (13:21:13). The spec set is being renumbered/rewritten right now. `_main/oracle-07-highlights.py` survives (12147 B, 12:20:26), so the **oracle half of W-08 is still actionable**; the spec half is not, until the renumbering settles. |

**W-06 therefore shrinks** to the one item that is genuinely still open and is NOT a code fix:
**L4-S5's `replay.h:65-82` producer decision** (does `CutResult` now carry `clip_id` /
`started_at_s`?). `replay.h` changed too - re-grep before dispatching.

### 6.2 Items whose targets are UNCHANGED - still dispatch

| item | target | mtime | verified |
|---|---|---|---|
| **W-02** | `trigger.cpp:262` `st.polled = true;` | 12:43:20 | **INTACT** - predates the reviewer's 12:50 read, so L1-F1/F4/F5 line numbers are sound. (A second `st.polled = true` exists at `:414`, inside `prepare_for_test`.) |
| **W-03** | `build.cmd:12` | unchanged | **INTACT** - `trigger.cpp` still absent. Still **OWNERSHIP GAP**. |
| **W-01** | `receipt-23-cron-woke-this-session.md` | 12:51:01 | **INTACT** - the false retraction is still there, and `RESTART-RUNBOOK.md` is still the file acted on at restart. **Still dispatch first.** |
| **W-04** | `docs/integration-sotto-app.md` | unchanged | **INTACT** - both blockers stand, including the silent `/dev/null` PCM tee. |
| **W-05** | `src/index/**` | 13:10:26 | See section 1. S2/S4/S5 still live; S3 already fixed. **New stub `specs/05-clip-to-asr.md` (824 B, 13:23:40) suggests the spec set is mid-rewrite - re-grep `audio_offset_ms` and `cutting` before dispatching.** |
| **W-09/W-10** | `receipt-21` (12:41:20), `_lane16-wake-gate.ps1` (12:38:32) | both unchanged | **INTACT** - D2's `-match '0'` bug stands. |
| **W-11** | `receipt-15-instant-replay-trigger.md` | unchanged | **INTACT** - the stale `B2495E4A` sha is still presented as current. |

### 6.3 One more count that is already stale

`receipts/` held **17** files when L8 measured it, **21** when L8's reviewer measured it, **29**
when this receipt's section 4 was written, and **34** now. That is not a pedantic note: it is the
concrete demonstration of L8-S6, and it is why **no receipt in this repo may state a population
without a `POP` and a `WINDOW`** - including this one. **POPULATION:** the 6 reviewers dispatched
to `mvs_b7a9f3a7db404912b32d28fc11b83645`. **WINDOW:** 13:02-13:24 on 2026-10-07.

### 6.4 The honest reading of all of this

Between 13:02 and 13:24 this repository changed under every one of these findings: an index
implementation was replaced wholesale, a spec was renumbered into a 936 B stub, three ring fixes
landed, a fourth receipt appeared, and the receipts directory grew by five files. **A 39-defect
work list is worth having; a 39-defect work list quoted as current fact twenty minutes later is
not.** The merge by file ownership is the durable part of this receipt - W-06 is the reason:
three lanes independently filed defects in `replay.cpp`, and the fix that closed two of them
would have been clobbered had they been dispatched separately.

**Rule for the dispatcher: re-grep every `file:line` in this receipt before opening an editor.
Do not re-derive the work items; re-derive the line numbers.**

---



### 6.5 A SEVENTH SEAT - it is NOT a seventh product review, and it OVERLAPS THIS LANE

A final census run at 13:26 returned `REVIEWERS_FOUND = 7 / VERDICTS_READ = 7`. The seventh is
**not a review of a product lane.** Session `mvs_25670c59a6084e1898e1c28bf48c0278`, opened with:

> *"Your lane: two finished reviewer verdicts are sitting unread, and unread is worthless...
> Lane L3's review was read and routed (six defects, one a wrong published number). **Two more
> reviews have finished and nobody has read them: the review of lane L4** (the index/search build)
> **and the review of lane L16** (the wake-mechanism audit). Both sit in finished background
> subagent sessions."*

It is a **sibling synthesis lane with an overlapping brief**, and its `YES` is a verdict on **its
own routing table**, not on any lane's code. So the counts in section 0 stand as written for
**product-lane reviewers**: 6 dispatched, 6 read, **6 of 6 `NO`**, 0 PASS on a product lane.
The seventh seat is counted separately so the denominator is not quietly inflated.

**THE HAZARD, stated plainly: L4 and L16 now have TWO routing tables and two dispatchers' worth
of instructions.** This lane covers L1, L3, L4, L8, L15, L16; the sibling covers L4 and L16. For
L16 the two tables should agree - the sibling's headings read *"verdict FAIL"* for both and its
"P0 DOWNGRADES" section matches what I recorded independently. **For L4 they cannot both be
actionable, because L4's target tree was replaced at 13:10:26 (section 1) - whoever dispatches
L4 must read section 1 of THIS receipt first, or they will send a lane to deleted files.**

This is the same hazard as W-06, one level up: three lanes filed defects in `replay.cpp`, and now
two synthesis lanes filed a routing for `src/index/**`. **Merge before dispatch, or the second
writer's instructions land on top of the first's.** The fix is one line of orchestration - give
each lane exactly one routing table - and it is the parent's to make, not mine.

---

Does your implementation meet the spec? YES - All 6 dispatched product-lane reviewer verdicts were located and read end to end (0 VERDICT NOT FOUND, reproducible via _main\review-synthesis.ps1), 39 concrete defects were extracted into 12 file-ownership-merged work items each naming the owning lane and what it blocks, the three claims I re-checked independently were confirmed with one stale line number corrected rather than dropped, and what the reviewers could not verify is carried as unverified - including two findings that re-grepping revealed AFTER the work list was written (src/index/** rewritten 11 seconds after its reviewer finished, voiding 6 of L4's 9 citations; and a concurrent fix lane closing L3-F2/F4/F6 within minutes), plus the 13:26 discovery that a sibling synthesis lane holds an overlapping brief covering L4 and L16, which is recorded here rather than left as a second competing routing table.
