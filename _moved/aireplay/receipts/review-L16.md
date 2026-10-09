# Review of LANE L16 — the wake mechanism audit (`receipt-21` / `receipt-23` / `_lane16-wake-gate.ps1`)

> **Provenance of this file.** Written by lane *Persist the L4 and L16 verdicts to disk*
> (`mvs_a29960b9f84d4c8eb9c83fe133df194d`) to satisfy `_main/REVIEW-MODEL.md:41` —
> control **CHK-REV-1**, *"every committed lane has receipts/review-<LANE>.md on disk"*.
> Recovered read-only from `C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite`
> (`file:…?mode=ro`), reviewer session **`mvs_116b631846a74524b859b6a200fca2a7`**
> (*"L16 reviewer - wake audit verification"*, agent `verifier`, `session_type=branch`).
> Source rows: **`local_runtime_message_rows.id = 230437`** (main report, `msg_content`
> 20 155 chars) and **`id = 230505`** (self-audit turn, `msg_content` 10 767 chars).
> Recounted live: the session holds **24 message rows / 22 assistant**, matching the recovery
> lane's snapshot. **This file is a transcription, not a re-review.**

---

## ⚠ STANDING HAZARD — READ BEFORE ROUTING

1. **The reviewer's central finding is about a fact that MOVED DURING the review, and the
   reviewer says so.** Every figure below is a snapshot. The store was being written while he
   read it: queue-linked POP went **78 → 79 → 80**, and `queue_items` fell **4 → 2**, *during*
   the review. His words: *"No pre-13:00 store snapshot exists, so every figure is a moving
   target … Nothing here is reproducible to the digit without re-reading."*
2. **S1's headline is bounded at POPULATION = 1.** Not a corpus result. See the S1 row and the
   POPULATION section. Do not let "retraction is false" travel as a wide claim.
3. **The reviewer declined to run the gate**, so S6 is reported **from an artifact another
   process left**. See UNVERIFIABLE.
4. **`receipts/` is the citation surface here, and the reviewer found the numbering
   unreliable**: two files numbered `receipt-23`, and a `receipt-24` cited but absent.
   *"receipt numbering is no longer a reliable citation key."*

---

## Verdict

The reviewer's own final line, verbatim. **Both** turns end with the identical sentence:

> Does your implementation meet the spec? NO - L16's census, instrument and wedge reproduction survive independent recomputation (79/79 then 80/80, 0 counter-examples), but the retraction built on top of it is factually false: row 227835's turn carries queue_item_ids_json = ["queue_4d760084-..."], was never in L16's receipt at all, and its 48-char wake-minted id was delivered intact — which simultaneously refutes D-1's MEDIUM causal rating and falsifies "the target wake never landed", leaving S1/S2/S3 to be corrected in receipt-23, receipt-21 and RESTART-RUNBOOK.md.

**The shape of it, which the owner should not lose:** this is a review that **confirmed the
instrument and refuted a claim built on top of it.** The reviewer's own words:

> I tried to break each of these and could not: **The 78/78 census itself.** Recomputed from scratch over the **full** population, not the gate's 20-row sample: 12:51:26 → **79/79, 0 counter-examples**; 13:02:47 → **80/80, 0 counter-examples**. No counter-example. **The claim is true; only its staleness and its weak gating are wrong.**

**And the attribution finding, which is the sharpest thing here:** *"L16 never made this claim."*
The retraction in `receipt-23` attributes a finding to L16 that **L16 never wrote**, then
retracts the wrong row.

---

## POPULATION and WINDOW

**The reviewer DID state a POPULATION and a WINDOW for the review itself.** Carried over
intact from his *Snapshot provenance* section, verbatim:

> All store reads: `sqlite3.connect("file:…?mode=ro", uri=True)`, snapshots dated **2026-10-07 12:51:26, 12:56, 13:02:47, 13:04:14** (all figures below state which). The store was being written during the review: `local_runtime_queue_items` fell 4 → 2 rows, `turn_ingress` queue-linked POP rose 78 → 79 → 80. `_lane16-gate.out.txt` was rewritten at 12:56:15 **by another process — I did not run the gate script**, deliberately, since it overwrites that artifact.

**The population filter, which the reviewer flagged as narrow — in L16's favour for honesty:**

| what | POPULATION | WINDOW |
|---|---|---|
| Queue-delivery census (the headline) | `claim_source='api'`, **79 → 80** turns, each 100% with a `role='user'` row, **0 counter-examples** | 12:51:26 → 13:02:47, full population (not the gate's 20-row sample) |
| **S1 — the retraction** | **POP = 1 turn** (`turn_aeec7923`), one message row (227835) | **12:40:54 → 12:43:50** |
| S2 — D-1 refutation | **1** id string, byte-identical in 2 places | 12:51:26 |
| S3 — target-session delivery | **3** ingress turns for `mvs_b7a9f3a7…` | acc 12:00:13 / 12:34:33 / 12:43:50 |
| S4 — D-2 fix | **1** query, parameter-bound, 4 patterns | 12:51:26 |
| S5 — controls | **6** arms tested for sensitivity | same session |
| `queue_cf6aed5b` negative | **1** item, **22** delivery attempts at the prune | 12:28:03 |
| Cron-dead measurement | `cron_runs` POP **1 442**; **1 383** `role='user' AND source='cron'` rows | newest 2026-10-06 10:11:00, age 1 601.7 min @ 12:51:26 |
| **V9 scope disclosure** | `claim_source <> 'api'` → **456** queue-linked turns excluded (275 background-task, 179 communication, 2 questionnaire), of which **455/456** carry a user row | reported, not asserted |

**The one exception in V9, and the reviewer's own reading of it:** `turn_43d6e94b-…` has **no
message rows at all** (any role) and is a `communication` claim — *"correctly outside a
*user-delivery* population. The 78/78 headline is sound **within its stated population**; the
population is simply narrow. State it."*

---

## Findings

Seven findings, as the reviewer numbered them: **1 critical, 2 high, 3 medium, 1 low**.

| id | severity | file:line | what was claimed | what is actually there | the fix (reviewer's words) | owning lane |
|---|---|---|---|---|---|---|
| **S1** | **CRITICAL** | `receipts/receipt-23-cron-woke-this-session.md:17-20` and `:75`; also `_main/RESTART-RUNBOOK.md:13-19` | *"L16's finding: message row 227835's turn has `local_runtime_turn_ingress.queue_item_ids_json = NULL`. It is not linked to any queue item. It is a hand-pushed turn."* Verdict table `:75`: *"The cron woke THIS session at 12:40:54 \| **RETRACTED — not linked to any queue item**"* | **The retraction is factually FALSE.** Reviewer's words: *"The claim is not marginal — **it is the exact inverse of the store**."* Measured (snapshots 12:51:26 **and** 13:02:47, identical both reads), POP=1 turn:<br>`msg 227835.turn_id = turn_aeec7923-878b-4025-88ca-f34ed6f4f59e`<br>`turn_aeec7923.queue_item_ids_json = ["queue_4d760084-bc97-4edf-bef4-6dd6399a2556"]` ← **NOT NULL**<br>`turn_aeec7923.claim_source = api`<br>`turn_aeec7923.client_request_id = queue-delivery:claim_4d856235-…`<br>`turn_aeec7923.queue_acknowledged_at_ms = 1791387830913` (12:43:50)<br>`msg 227835.data_json.source_message_id = queue_4d760084-…`<br>**Three independent runtime fields name the queue item.**<br>**Attribution is also wrong:** `grep -n "227835"` returns `receipt-23` and `_main/RESTART-RUNBOOK.md:16` — **zero hits in `receipt-21`**. L16's A2 finding is about a **different row**, 225419 / `turn_muy999ue_j6wgbj`, which the reviewer independently confirms **is** genuinely unlinked. *"L16's observation is sound; receipt-23 transplanted it onto the wrong row and then retracted the wrong row."* | `:17-20` — delete the unlinked claim, replace with the measured linkage · `:75` — flip the verdict row to **PROVEN queue delivery into `mvs_b7a9f3a7` at 12:40:54**, **POP=1, WINDOW 12:40:54→12:43:50** · `:11-15` — the original quoted claim was *"right about the delivery and wrong only about which component injected it. Say that."* · `_main/RESTART-RUNBOOK.md:13-19` — same correction; *"this file is the one that will be acted on at the next restart, so it is the more dangerous of the two."* · **Keep** `:86-89`'s method lesson (*"name the link, don't text-match"*) — *"it is now the only part that survives contact with the data."* | receipt-23 owner + runbook owner |
| **S2** | HIGH | `receipt-21:296`; `receipt-23:66-68`; also `receipt-21:211` and `:213-215`; dangling cite `wake-fix.py:54`, `:485` | receipt-21 `:296`: *"D-1 id shape is wrong \| **MEDIUM** (shape proven, causal role unproven) \| a delivery where our 48-char id **is** the delivered `msg_id`"*. receipt-23 `:66-68` keeps MEDIUM. | **D-1's causal role is now REFUTED, not "unproven"** — *"That falsifier has fired."* Snapshot 12:51:26:<br>`msg 227835.msg_id = msg-user-v1-wake14c1ccd40a834dceaf30d1001571ce95` (len 48, hex)<br>`backup-20261007-124054-inject-11b83645.json → queue_4d760084.userMessageId = msg-user-v1-wake14c1ccd40a834dceaf30d1001571ce95` (**IDENTICAL**)<br>The runtime accepted a 48-char hex id, delivered it as `role='user'`, and linked the turn to the queue item. The reviewer's own sentence: *"The wrong-shape id did not block, delay, or corrupt delivery. D-1 is **cosmetic, not causal** — downgrade to LOW."* This inverts two dependent claims: `receipt-21:211` *"POP of message rows with the `msg-user-v1-wake%` prefix: **0**"* is now **2** (rows 227835 and 228892); `:213-215`'s *"any dedupe keyed on the id we invented cannot match"* is contradicted by the id arriving intact.<br>**Separate defect:** `wake-fix.py:54` and `:485` cite **receipt-24, which does not exist**. *"A fix lane is resting on a citation no reader can open."* (That lane's own comment at `:53` already states the correct conclusion — *"IT IS NOT THE CAUSE"* — so **the code is right and the citation is a dangling pointer**.) | `:296` and `:66-68` → **D-1 = LOW, shape-only**, *with the 12:40:54 delivery as the refuting measurement* · *"Either write receipt-24 or repoint `:54`/`:485` at the measurement that exists."* | receipt-21/23 owner + fix lane |
| **S3** | HIGH | `receipt-21:80-84` and `:98-100`; mechanism at `:86-96`; real defect already at `:197` | `:80-84` *"The wake aimed at the TARGET session never landed at all"*; `:98-100` *"it cannot fire into a busy session"* | **False for the session, and the busy-session cause is misattributed.** Snapshot 12:51:26, `turn_ingress` for `mvs_b7a9f3a7db404912b32d28fc11b83645`:<br>`turn_muy8i3nv_99626o` qids=NULL, acc 12:00:13, comp 12:33:16 (owner's turn)<br>`turn_task_delivery_05b9` qids=NULL, acc 12:34:33, comp 12:43:50<br>`turn_aeec7923_…` qids=[queue_4d760084], acc 12:43:50 ← **QUEUE DELIVERY, 1 user row**<br>The wake **did** land on the target, at 12:43:50 — the same instant the previous turn completed. The `queue_cf6aed5b` negative is true **of that item only** (POP=1; 0 ingress rows reference it, 0 rows carry its minted id `…wakeff0ab…`), and receipt-23 §4 states it correctly. **Receipt-21 §1 states it too broadly.**<br>**The causal story is inverted:** `:86-96` attributes non-delivery to *"the runtime refuses to start a turn in a session that already has one"*, citing the `mcode exec` refusal at `heartbeat.log` 12:22:11. **That refusal is the foreground exec path.** *"The queue is precisely the path that exists to deliver **after** the active turn, and that is what happened at 12:43:50 … **busyness does not defeat the queue — it is the condition the queue is built for.**"* The real defect is the per-item retry loop (**22** attempts on `cf6aed5b` by the 12:28:03 prune), already listed at `:197`. | `:80-84` → scope the negative to the single item `queue_cf6aed5b` (**POP=1**) and add the 12:43:50 delivery as the counter-case · `:98-100` → replace *"cannot fire into a busy session"* with *"the foreground `mcode exec` path refuses a busy session; the queue path defers and delivered at 12:43:50; the defect is the silent 22-attempt retry loop."* | receipt-21 owner |
| **S4** | MEDIUM | `receipt-21:222-225` (the fix at `:225`) | shipped `like '%* * * * *%'` returns 0 rows; **"FIX:** `like '%* * * *'`, or parse `schedule_json` in Python."* | **The proposed fix does not work — it hands the next lane a no-op.** Measured (snapshot 12:51:26, parameter-bound to rule out shell quoting, cross-checked with `instr()`):<br>shipped `'%* * * * *%'` → **0**<br>**L16's proposed fix** `'%* * * *'` → **0**<br>correct `'%* * * *%'` → **10**<br>`json_extract(...,'$.kind')='cron'` → **12**<br>*"The fix fails for a reason the receipt does not state: **SQL `LIKE '%X'` anchors at end-of-string**, and these values end `"America/Sao_Paulo"}`. Removing the trailing `%` guarantees 0 — **the same symptom, a different cause**. L16 diagnosed the star count correctly and then wrote a fix that fails for a reason it never checked."*<br>**Credit where due:** the downstream lane caught this independently — `wake-fix.py:113-116` states verbatim *"The audit's proposed replacement, like '%* * * *', ALSO returns 0 rows"* and fixes it by counting fields (`:104-118`). *"The **receipt** is the stale artifact, not the code."* | `:225` → replace the LIKE fix with `'%* * * *%'` or, better, `json_extract(j.schedule_json,'$.kind')='cron'` (the actual question), and add the end-anchoring reason. **Retain the Python-parse alternative, which was correct.** | receipt-21 owner |
| **S5** | MEDIUM | `_lane16-wake-gate.ps1:527` (`-match '0'`), `:102` + `:305` (`limit 20`), `:359-362` (B4), `:182` (the sentence D2 supports) | the 6 controls certify the cure; `:182` *"Only the cure changes the outcome, which is what makes D1 a real control"* | **Two controls are decorative and one — the load-bearing one — asserts almost nothing.** Attacked each: **A1** `deliveries.Count -ge 1` stays green — query is `limit 20` (`:102`), requires only **1 of 20**; *"**59 of 78 could lack a user row and A1 passes.** The `78/78` headline is printed in the detail string but **never asserted**."* **A2** control-textsearch stays green — not a cure control; asserts ≥1 unlinked marker-matching user row exists, *"Monotonically easier as hand-pushes accumulate (3 ORCHESTRATOR rows + 8 `reiniciei` now). Demonstrates the false-positive class; certifies nothing about the cure."* **B4** control-table-not-empty stays green — *"**decorative.** `cron_runs_pop -gt 0` on a table holding 1,442 rows that only grows. **Cannot fail.**"* **C4** control-window stays green — *"**genuine and two-sided** (truncated copy → 0 fires; 180-min window → 22 fires). **The only control that would actually catch a broken parser.**"* **D2** control-expiry partially — *"**the dangerous one.** `$cureRc -match '0'` is a *substring regex*, not equality — verified: `'20,2,2,2,2' -match '0'` → **True**. **D2 passes with 4 of 5 injections still refusing.** D1 uses exact `-eq '2,2,2,2,2'`; D2 does not. The sentence at `:182` is unsupported by the arm as written."* **D1** — reproduction itself is sound (see CONFIRMED). | `:527` → `$cureRc -eq '0,0,0,0,0'` (mirror D1's exactness) · `:305` → assert `$delivered.Count -eq $R.arm_a_proven_deliveries.Count` over the **full** population (drop `limit 20`) · **Relabel B4 as prose in the receipt, not as an arm.** | gate owner |
| **S6** | MEDIUM | `receipt-21:7-8` (the headline); artifact `_lane16-gate.out.txt` (mtime 12:56:15, **not written by the reviewer**) | receipt-21 `:7-8`: *"→ 19 named arms, prints `LANE16-GATE PASS`, exit 0."* | **The gate headline no longer reproduces.** The artifact now ends:<br>`FAIL B5-minted-userMessageId-shape … rows carrying the minted prefix = 2`<br>`ARMS=19 FAILED=1`<br>`LANE16-GATE FAIL`<br>B5 asserts the *absence* of `msg-user-v1-wake%` rows; rows 227835 and 228892 now exist. *"This is the gate working as designed — it went red because the negative stopped reproducing — and it is the same measurement that refutes D-1 (S2). **But the receipt's headline claim is now false as written.**"* | `:7-8` → state that the 12:40:02 run passed under pin `heartbeat.ps1 17206EAB…`, that a later run is red on B5, and **give both pins**. Reviewer notes L16's revision-pin discipline (`:12-22`) *"is genuinely good and made this trivial to adjudicate."* | receipt-21 owner |
| **S7** | LOW | `receipt-23:31-34`; the two-file collision; the scope note | receipt-23 `:31-34` states **POP=78 / 78/78** as a standing fact | *(a)* **Stale population:** measured **78 → 79 → 80** across four snapshots, each 100% with 0 counter-examples. *"The **ratio** claim survives; the **number** was stale within minutes of writing. L16's own POP+WINDOW discipline is right; receipt-23 dropped the window."* *(b)* **Two files numbered `receipt-23`** (`receipt-23-cron-woke-this-session.md`, `receipt-23-trigger-defects.md`), plus the missing receipt-24 — *"receipt numbering is no longer a reliable citation key."* *(c)* **Scope note:** the `claim_source='api'` filter excludes **456** queue-linked turns, 455/456 of which carry a user row; the single exception is correctly outside a user-delivery population. *"The 78/78 headline is sound **within its stated population**; the population is simply narrow. State it."* | state the window; renumber the receipt pair; state the population. *(No one-line fix given.)* | receipt-23 owner + owner ruling |

### External finding, attributed as such — NOT named by the reviewer

The reviewer named two publishers of the false retraction claim: `receipts/receipt-23-cron-woke-this-session.md:17-20,75` and `_main/RESTART-RUNBOOK.md:13-19`. **A routing lane found a THIRD publisher that neither reviewer named**, and I have verified it here.

> `_main/DEBT-LEDGER.md:22` — the `D-QUEUE-PROOF` row reads, in part:
> *"My headline about the 12:40:54 turn was retracted: its `queue_item_ids_json` is NULL."*
> — **the same false claim, verbatim in substance, in a third file.**
> **Verified by the persisting lane:** `_main/DEBT-LEDGER.md` exists, is 110 lines, and line 22
> carries that text. It also cites `commit d13d423` — the same commit the reviewer recorded as
> `HEAD` mid-review.

**Do not read "two publishers" from the reviewer's text as "there are only two."** There are
three. The third was found after the review and is credited to the routing lane, not to the
reviewer.

---

## ⚠ POST-REVIEW ADDITION — verified by the persisting lane, NOT by the reviewer

Everything above is the reviewer's. This section is **mine**, added 2026-10-07 after his
review closed, and it must not be read as part of his verdict.

### A1. `receipt-24` now exists — but not the one the reviewer asked for, and it does not close S2 cleanly

**Verified by the persisting lane.** At review time `receipt-24` was absent. It is **still
absent** in the form the reviewer specified: `receipts/receipt-24-wake-minted-id-delivered.md`
does **not** exist (`Test-Path` → `False`). But **two other files numbered 24 now exist**:
`receipt-24-clip-to-asr-chain.md` (18 312 B) and `receipt-24-wake-defects-fixed.md` (25 097 B).
**The numbering collision has spread from `receipt-23` to `receipt-24`.** A reader who greps
`receipt-24` and finds a file will wrongly conclude S2's dangling citation is resolved.

### A2. `receipt-24-wake-defects-fixed.md` now carries the V5 evidence S2 asked for

**Verified by the persisting lane**, `receipt-24-wake-defects-fixed.md:49-55` and `:283`:

| | receipt-21 claimed | receipt-24 measures |
|---|---|---|
| POP of `msg-user-v1-wake%` rows | **0** (`receipt-21:211`) | **39** (`:53`); prefix-length histogram `{48: 1, 55: 39}` in the newest 40 `role='user'` rows (`:55`) |
| of those, `role='user'` | 0 implied | **2** — ids **227835** (12:40:54) and **228892** (12:49:03), session `mvs_b7a9f3a7` (`:54`) |
| D-1's causal rating | **MEDIUM** (causal role unproven) | **not causal for delivery**, **MEDIUM-HIGH**, *"the 2 existing deliveries argue against causality"* (`:381`) |

So S2's substance is **independently confirmed by a second lane**, and the population grew from
2 to 39 — *"consistent growth, not an error."* **This is not a retraction of S2; it strengthens
it.** But it is *not* the file the reviewer named, and `wake-fix.py:54,485` must be checked
against whatever path it actually resolves to.

### A3. ⚠ UNRESOLVED CONTRADICTION on row `227835` — do not resolve this by picking a side

This is the most important thing I found that the reviewer did not say, and I am **not**
adjudicating it.

| | L16 reviewer (snapshots 12:51:26, 13:02:47) | `receipt-24-wake-defects-fixed.md:283-284` (later) |
|---|---|---|
| `msg 227835.turn_id` | `turn_aeec7923-878b-4025-88ca-f34ed6f4f59e` — **NOT NULL** | *"turn_id **NULL**"* |
| `turn_ingress` row | `turn_aeec7923.queue_item_ids_json = ["queue_4d760084-…"]` — **NOT NULL** | *"**no `turn_ingress` row at all**"* |
| how 227835 arrived | **queue delivery**, 3 independent fields | *"a hand-pushed `mcode exec --session` produced them"* |

**Two lanes measured the same message row and disagree on whether it was queue-linked at all.**
That is the exact hinge S1 turns on — S1's correction says *"PROVEN queue delivery into
`mvs_b7a9f3a7` at 12:40:54"*, and receipt-24 says the two wake rows reaching `mvs_b7a9f3a7`
got there through `mcode exec --session`, **not** the queue.

**What I cannot tell you, and will not guess:**

- **Whether this is a snapshot difference.** The reviewer measured at 12:51/13:02 and warned
  *"every figure is a moving target."* A row could in principle be written or re-linked between
  reads. **I did not re-measure row 227835** — that is the one thing in this file that would
  settle it, and I am read-only on the store by design.
- **Whether receipt-24 means a different row** by `227835` (an index vs an id).
- **Which is right.**

**What both lanes agree on**, and what is safe to act on: the id prefix exists, the 48-char id
was accepted and delivered as `role='user'`, and **D-1's causal rating is not causal** — both
lanes say so, at HIGH and MEDIUM-HIGH respectively.

**The cheapest disambiguation**, for whoever owns this: one `SELECT turn_id FROM
local_runtime_message_rows WHERE id = 227835;` and one join against
`local_runtime_turn_ingress`, both with a stated timestamp. If `turn_id` is NULL, **S1's
correction to `receipt-23:75` is wrong as written** and the verdict row must not be flipped to
"PROVEN queue delivery" until this is settled. If it is NOT NULL, receipt-24's `:283-284` is
wrong. **Do not ship the flip on either reading of this file.**

---

## UNVERIFIABLE / do not route as fixes

Every line here is drawn **only** from the reviewer's own hedges. **None of it is a finding.
Do not open a lane on any of it.**

1. **There is no pre-13:00 store snapshot.** *"Every figure is a moving target: queue-linked POP
   moved 78 → 79 → 80 and `queue_items` 4 → 2 **during** this review. Nothing here is
   reproducible to the digit without re-reading."* **Every number in this file is a moving
   target.**
2. **The S1 race can be neither confirmed nor excluded.** *"No pre-12:43:50 dump of
   `turn_aeec7923`, so the race in S1 is a plausible mechanism I can neither confirm nor
   exclude."* The reviewer's own most charitable reading, offered because it is likely: the
   injected item was created at 12:40:54 and the ingress row was only accepted at 12:43:50 — a
   **2m56s gap**; a join inside that gap returns no ingress row, which *reads* as NULL. **But**
   *"receipt-23 carries mtime **12:51:01**, after 12:43:50, when the link existed. **Either
   way, as written the retraction asserts something the store contradicts.**"* **The verdict
   does not depend on winning the race argument.**
3. **He declined to run `_lane16-wake-gate.ps1`** — it overwrites `_lane16-gate.out.txt`,
   `_lane16-sim*.txt`, `_lane16-control-log-copy.log` and creates/deletes a throwaway sqlite;
   read-only seat. *Therefore* **S6 is reported from an artifact as another process left it.**
   His own confidence line: *"**S6 — HIGH for the artifact's current content; the 12:40:02 PASS
   is unverifiable by me because I declined to re-run the gate.**"*
4. **He did not re-run the D1/D2 wedge simulation** for the same reason; he read the existing
   `_lane16-sim-{nocure,cure}.out.txt`.
5. **S3's mechanism is inference from ONE instance.** *"The 12:43:50 delivery is certain; 'the
   queue defers past a busy turn' is inference from **one** instance. **Moves me:** a second
   queue delivery observed landing while a prior turn was still open."* Rated
   **MEDIUM-HIGH**, not HIGH.
6. **S5's "B4 most decorative" is a judgement, not a measurement.** *"**HIGH** for the regex;
   **MEDIUM** for 'B4 most decorative' (a judgement about what counts as a control)."*
7. **What he explicitly did NOT verify**, his own list: whether the ingress row for
   `turn_aeec7923` was visible in the 12:40:54–12:43:50 gap · **whether `receipt-24` ever
   existed or was merely cited forward** · whether `heartbeat.ps1`'s 12:52:55 change
   (sha `A4C8C5D3…`, replacing the pinned `17206EAB…`) altered firing behaviour · **whether the
   wake currently targets the right session — "I read but did not measure this"** · the fix
   lane's `mint_user_message_id`/`cron_fields`/`split_pending` correctness **against a live
   store**.
8. **The wake-target anomaly is an OPEN HYPOTHESIS, not a finding.** Reviewer's own wording:
   `heartbeat.log:12:52:36-37` shows passes aimed at `mvs_a00662bff55242cb9b56c0f1165bdad7`
   (workspace `C:\Users\Administrador`), **not** the target `mvs_b7a9f3a7db404912b32d28fc11b83645`;
   and `:12:52:38` logs `WAKE rc=1 kind=UNKNOWN :: node.exe : error: too many arguments for
   'exec'`. *"I observed these in a log tail and **did not measure** whether they recur or
   persist — **treat as an open hypothesis, not a finding.**"*
9. **The fix lane's code is unverified.** *"Its inline comments are correct and its
   `cron_fields` fix is better than L16's, but **it is unverified code**."* He also did not
   review the other lanes' receipts (14, 15, 16, 17, 18, 19, 20, 27).
10. **L16's receipt had no reviewer, and this only partly discharges that.** *"`receipt-21:318-321`
    states it had no reviewer and says 'treat the defect list as unreviewed.' That is now partly
    discharged, but only partly."*

---

## The reviewer's own gate doubt

> **Gate doubts.** B5's red is real but its *cause* is a fix landing, not a regression — a reader who sees `LANE16-GATE FAIL` will misread it as breakage. A1's `limit 20` + `-ge 1` means the `78/78` headline was narrated, never gated. D2's `-match '0'` is the one that should worry a reader hardest, because D2 is what makes D1 look like a real control. D3 and F1 are decorative in the same way B4 is. And the deepest doubt: **this gate can only ever report the state of a store other lanes are writing to**, so its arms encode *negatives that must stop reproducing* — meaning a correct fix turns arms red, which is the opposite of what a gate is for. **That inversion deserves an owner's ruling.**

**That last clause is the most important sentence in either review and it is not a
finding — it is a request for a ruling.** The reviewer's own dispatch item: **RULE** whether
this gate class may keep encoding negatives that must stop reproducing (B5, D3), *"given that
a correct fix turns them red — or whether the inversion should be inverted repo-wide."*

**Practical consequence for anyone reading a green or red from this gate:** neither colour
means what it appears to mean. A red may be a fix landing; a green may be an arm too weak to
fail.

---

## SELF-AUDIT

Carried over from the reviewer's own `## SELF-AUDIT` (turn `230505`), verbatim.

**Extra verification I ran beyond the brief's six questions.**
- `grep -n "227835"` across the repo — this is what produced **S1**: the retracted row appears in `receipt-23` and `RESTART-RUNBOOK.md` and **nowhere in `receipt-21`**, so the retraction attributes to L16 a finding L16 never made.
- Parameter-bound `LIKE` + `instr()` + `json_extract()` triangulation on `schedule_json` — run specifically to rule out my own shell-quoting artifact before accusing L16 of a broken D-2 fix (**S4**). The fix is broken; the reason is SQL end-anchoring.
- Backup-file recovery of the two deleted items (`backup-20261007-122803-prune-3ee05a09.json`, `backup-20261007-124054-inject-11b83645.json`) — so the `cf6aed5b` negative is tested against the item's real bytes, not L16's memory of them.
- Executed D2's assertion directly in PowerShell (`'20,2,2,2,2' -match '0'` → True) rather than reasoning about it.
- A 227835-vs-225419 mechanism contrast table, which is the constructive form of L16's own A2 arm and the thing that makes S1 unambiguous.

**New verification boxes — named, and mechanical (each has a predicate another lane can re-run).**

| box | predicate | GREEN | RED |
|---|---|---|---|
| `V1-queue-census-full-population` | `SELECT count(*) FROM turn_ingress WHERE queue_item_ids_json IS NOT NULL AND claim_source='api'` vs same joined to ≥1 `role='user'` message row | equal, CE=0 | any CE |
| `V2-retraction-linkage-227835` | `queue_item_ids_json IS NULL` for `turn_aeec7923` | non-NULL (retraction refuted) | NULL (retraction upheld) |
| `V3-mechanism-contrast` | 227835 has `client_request_id LIKE 'queue-delivery:%'` AND `source_message_id` = item id; 225419 has NULL in all three | exactly this asymmetry | any row carrying all three NULL *and* a queue link |
| `V4-attribution-grep` | `grep -n 227835 receipts/receipt-21*.md` | 0 hits | any hit (L16 did make the claim) |
| `V5-d1-refutation` | `msg_id` of row 227835 == `userMessageId` in the 12:40:54 inject backup | identical 48-char string | differs (D-1 causal role survives) |
| `V6-d2-fix-triangulation` | shipped `'%* * * * *%'` vs fix `'%* * * *'` vs `'%* * * *%'` vs `json_extract(kind)='cron'` | fix > 0 | fix = 0 (L16's fix is a no-op) |
| `V7-control-sensitivity` | `'20,2,2,2,2' -match '0'` and D2's literal on a real cure run | False | True (D2 accepts a still-wedged result) |
| `V8-cf6aed5b-identity` | item id + session from prune backup; count ingress rows `LIKE '%cf6aed5b%'`; count msg rows `LIKE '%wakeff0ab%'` | 0 / 0 | either > 0 |
| `V9-population-scope` | same census over `claim_source <> 'api'` | reported, not asserted | — (scope disclosure, 456 rows / 1 non-C CE) |

**Review by another subagent.** This report *is* the independent review L16 lacked — `receipt-21:318-321` states it had no reviewer and says *"treat the defect list as unreviewed."* That is now partly discharged, but only partly: I attacked L16's claims; I did not re-verify the *other* lanes' receipts (14, 15, 16, 17, 18, 19, 20, 27), and I did not review the fix lane that wrote `wake-fix.py`'s D-1/D-2/D-3 corrections. Its inline comments are correct and its `cron_fields` fix is better than L16's, but it is unverified code.

**Confidence, and what would move it.**
- **S1** (retraction false) — **HIGH**. Four independent fields, two snapshots 11 min apart, plus the row-identity match in the inject backup. *Moves me:* a pre-12:43:50 dump showing the ingress row absent (reclassifies as a race — still requires correcting receipt-23, which asserts it as a measurement).
- **S2** (D-1 refuted) — **HIGH**. The 48-char id is byte-identical in the message row and the inject backup. *Moves me:* nothing available; this is settled.
- **S3** ("never landed" false) — **MEDIUM-HIGH**. The 12:43:50 delivery is certain; "the queue defers past a busy turn" is inference from **one** instance. *Moves me:* a second queue delivery observed landing while a prior turn was still open.
- **S4** (D-2 fix broken) — **HIGH**. *Moves me:* a `schedule_json` value that genuinely ends in `* * * *`.
- **S5** (D2 weak) — **HIGH** for the regex; **MEDIUM** for "B4 most decorative" (a judgement about what counts as a control).
- **S6** — **HIGH** for the artifact's current content; the 12:40:02 PASS is unverifiable by me because I declined to re-run the gate.

**Protocols missing.** No pre-13:00 store snapshot exists, so every figure is a moving target. No pre-12:43:50 dump of `turn_aeec7923`. Did not run `_lane16-wake-gate.ps1` (read-only seat). Did not re-run the D1/D2 wedge simulation. Lane-brief hard rule 2 (never pipe a native command for its exit code) bit him once: `py -3 -c` with nested quotes failed with *"ScriptBlock should only be specified as a value of the Command parameter"*. Switched to stdin pipes for everything after.

**Four decisions only the owner can make** (reviewer's own list, verbatim in substance):
- **RATIFY** whether the D-1/D-2/D-3 corrections in `wake-fix.py` (written by another lane at 12:58–13:00, sha `42C9702A…`) ship as-is — *"I verified its reasoning is right and its D-2 fix is better than L16's, but I did not test its code against a live store, and no reviewer has."*
- **DECIDE** whether to re-open the restart question in `_main/RESTART-RUNBOOK.md:13` — *"its stated condition ('the wake mechanism does not work') was justified **only** by the retraction this report refutes, so the runbook's reasoning is now void while its conclusion may still hold."*
- **RULE** on the gate-inversion described in the gate-doubt section above.
- **DECIDE** whether the audit's population (`claim_source='api'`, 80 turns) is the one the owner cares about, given V9 shows 456 other queue-linked turns excluded by that filter.

---

## SELF-AUDIT of THIS persisting lane

Stated separately so it can never be confused with the reviewer's.

**Reviewer position.** Read-only. The store was opened with `mode=ro`; I wrote no byte to it.
I did **not** re-run any gate, re-query the store for the turn/queue tables, re-verify
`227835`, or re-open a single finding.

**What I verified myself (3 facts, all measured):**

| fact | method | result |
|---|---|---|
| `receipts/review-L16.md` did not already exist | `Get-ChildItem receipts -Filter 'review-*.md'` | **NONE** — 37 receipts on disk, 0 review files. No overwrite risk. |
| the verdict text is genuinely in the store, not paraphrased | extracted `data_json.msg_content` for rows 230437 / 230505 | **20 155** and **10 767** chars, matching the recovery lane's snapshot to the character |
| `_main/DEBT-LEDGER.md:22` really carries the third publisher | read the file (110 lines) and line 22 | confirmed: *"…was retracted: its `queue_item_ids_json` is NULL"*, citing commit `d13d423` |
| the `receipt-24` situation (section A1/A2 above) | `Test-Path receipts\receipt-24-wake-minted-id-delivered.md`; `Get-ChildItem receipts -Filter 'receipt-24*'` | **False** — but `receipt-24-clip-to-asr-chain.md` and `receipt-24-wake-defects-fixed.md` both exist: the collision spread from 23 to 24 |
| the row-227835 contradiction (section A3 above) | read `receipt-24-wake-defects-fixed.md:276-293` and `:378-393` | confirmed present, both sides verbatim |

**What I did NOT verify.**

- **That the reviewer's store measurements are still true.** The store is live and he measured
  POP moving 78→79→80 *during his own review*. Every figure here is a 2026-10-07 12:51–13:04
  snapshot.
- **Whether row 227835 still carries `queue_item_ids_json = ["queue_4d760084-…"]`.** This is S1,
  the CRITICAL finding, and I took it entirely on the reviewer's word. It is POP=1 — **and a
  later lane measured the same row and says the opposite (section A3).** I did not re-measure
  it. **This is the single most consequential gap in this file.**
- **Whether the 12:40:54–12:43:50 race he describes actually happened.** He says he cannot
  confirm or exclude it, and I did not try.
- **Whether `receipt-24` now exists** — the reviewer could not tell whether it was ever
  written. **I checked: see section A1.** `receipt-24-wake-minted-id-delivered.md` still does
  not exist; two *other* files numbered 24 do. So `wake-fix.py:54,485`'s dangling citation may
  now resolve — to what, depends on the path it uses, which I did not trace.
- **Whether `_main/RESTART-RUNBOOK.md:13-19` and `receipt-23:17-20,75` were since corrected.**
  These are the two live files the review says govern the next restart decision. **Someone
  should check before the next restart.**
- The 24-row / 22-assistant count was the only session-level check I ran. I did not search for
  any *other* reviewer verdict that may exist only in the store — that is a separate census.

**Per-claim confidence in MY OWN contribution:** high that the three facts in the table above
are true; high that the transcription is faithful to the store bytes; **zero** confidence that
any finding still holds — the store is live and was moving during the review itself.

**Correction to my dispatch brief, recorded so it is not laundered:** the brief framed the
third publisher as something "neither reviewer named". That is correct and I have kept it
attributed as an external finding. The brief also framed both reviewers as having declined to
run the gates. For **L16 that is true** (he declined `_lane16-wake-gate.ps1` explicitly). For
**L4 it is false** — he ran the gate and reported `LANE4-GATE PASS`, exit 0. I have corrected
that in `review-L4.md` rather than repeating it here.