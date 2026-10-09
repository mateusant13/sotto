# RECEIPT 21 — WAKE MECHANISM AUDIT (lane16, auditor)

**Lane:** independently audit the wake mechanism — the thing that keeps this agent alive.
**Role:** AUDITOR. I did not modify the wake machinery. Every defect below is
reported with its exact fix and left unapplied, by instruction.
**Artifacts I own:** `_main/_lane16-wake-gate.ps1`, this receipt.
**Gate:** `pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane16-wake-gate.ps1`
→ 19 named arms. Result file `_main/_lane16-gate.out.txt` carries a **revision pin**
(sha256 + mtime) of `heartbeat.ps1`, `wake-fix.py`, `watch-wake.py`, because another
lane was editing them *while this audit ran*.
**This gate was run TWICE and the SECOND run is RED. Both pins are recorded below —
do not cite only the one that flatters this audit.** Neither artifact records a process
exit code; only the terminal line is quoted, verbatim.

| run | artifact | mtime | terminal line | `heartbeat.ps1` pin | `wake-fix.py` pin |
|---|---|---|---|---|---|
| run 1 | `_main/_lane16-gate-console.txt` | 2026-10-07 **12:40:02** | `ARMS: 19   FAILED: 0` → **`LANE16-GATE PASS`** | sha256 `17206EAB…` mtime 12:39:20 | sha256 `473305FC…` mtime 12:25:15 |
| run 2 | `_main/_lane16-gate.out.txt` | 2026-10-07 **13:02:59** | `ARMS=19 FAILED=1` → **`LANE16-GATE FAIL`** | sha256 `A4C8C5D3…` mtime 12:52:55 | sha256 `FACCF146…` mtime 13:02:50 |

The one failing arm is **`B5-minted-userMessageId-shape`**, whose own line reads
`wake-fix.py mints msg-user-v1-wake+hex32 (source=False); runtime writes msg_id len
48,55; live queue rows have len 55 (0 of them off-shape); rows carrying the minted
prefix = 2`. POP: **2** rows store-wide carry that prefix (see §7). Run 2 is therefore
RED because **two delivered `role='user'` rows still carry the old mint** — which is the
*disconfirming* measurement for D-1, not a live regression. **This receipt describes a
state that has since changed:** `wake-fix.py` no longer mints that shape at all (current
bytes sha256 `56DA814D…`, mtime 2026-10-07 13:27:02; `mint_user_message_id()` at `:97`
emits `secrets.token_urlsafe(32)`), and arm B5 asserts about history the fix cannot
undo. It is a stale-store assertion, not a defect.

> **REVISION PIN of the measurements in this receipt** (from the passing gate run
> at 2026-10-07 12:40:02):
> `heartbeat.ps1` sha256 `17206EAB0190B07D…` mtime 2026-10-07 12:39:20 ·
> `wake-fix.py` sha256 `473305FCF0950CBA…` mtime 2026-10-07 12:25:15 ·
> `watch-wake.py` sha256 `A4FA5CE9AD8D9001…` mtime 2026-10-07 12:07:47.
> `heartbeat.ps1` changed shape four times during this audit (12:07, 12:22,
> 12:35, 12:39) while `wake-fix.py` changed once (12:25, the `prune` mode).
> **The wake machinery was being rewritten by another lane while it was being
> audited.** Any number here belongs to those bytes and to the store as of
> 2026-10-07 12:40:02. Re-run the gate and re-read the pins before reusing a
> figure; a stale pin is how a correct line citation becomes a false claim.

---

## 0. The headline

The queue wake **works** — and it can be proven, but **only** through
`local_runtime_turn_ingress.queue_item_ids_json`, never through a text search.
What is broken is the other half: **the runtime's own cron scheduler has been
dead for 26.4 hours**, and the wake's *refusal* path is silent, so six
consecutive fires looked healthy while doing nothing.

The false claim this audit was told to fear ("nothing consumes the queue") was
wrong in one direction and right in the other: the queue **is** consumed and does
deliver — but not to the session that was being targeted, and not within 3 minutes.

---

## 1. Does a corrected queue row actually get DELIVERED as a `role='user'` row?

### ANSWER: YES. Proven. And the proof is *not* a text search.

**The instrument.** `local_runtime_turn_ingress` is the runtime's own record that a
queued item became a turn: `claim_source='api'` + a non-null `queue_item_ids_json`.

**POPULATION:** 78 queue-driven turns in the whole store
(`turn_ingress WHERE queue_item_ids_json IS NOT NULL AND claim_source='api'`).
The 20 most recent **all** carry ≥1 `role='user'` message row. (ARM A1.)

**The one fully traced delivery, item by item:**

| step | value |
|---|---|
| queue item | `queue_ec7ae0a0-d5ad-44a4-9d53-7a824dc2d162` (session `mvs_a00662bf`) |
| injected | 2026-10-07 **11:51:49** |
| `userMessageId` written | `msg-user-v1-D52aPwtIrpQdxgTD0f57LtdRvhNVHic3WgefMuudXhX` |
| `requestedTurnId` written | `turn_633acf0e-40de-4e05-b8ff-5120e5f426f4` |
| `turn_ingress` | same `turn_id`, `claim_source='api'`, `queue_item_ids_json=["queue_ec7ae0a0-…"]`, `queue_acknowledged_at_ms` set, accepted **12:20:04**, completed 12:20:09, status **`aborted`** |
| message row | id **225247**, `role='user'`, `source='api'`, session `mvs_a00662bf`, `msg_id` = **the injected id verbatim**, `turn_id` = **the injected turn id verbatim** |
| **latency injected → delivered** | **28 min 15 s** |

So: delivered, as a `role='user'` row, with the identity we wrote preserved —
but after 28 minutes, and the delivering turn then **aborted** 5 s later.

### The trap, measured live — and it is worse than "assistant rows quoting the marker"

A naive text search on the payload `ORCHESTRATOR MANDATE …` returns:

* **22** rows matching, any role;
* **1** row matching with `role='user'` — id 225419, session `mvs_a00662bf`,
  content sha256 `8953abb1ca9d9ea3`, **byte-identical** to a live queue row's payload;
* and that row's turn, `turn_muy999ue_j6wgbj`, has **`queue_item_ids_json = NULL`
  and `claim_source = NULL`**.

That is a hand-pushed foreground turn. **The queue never delivered it.** A text
search credits it to the cron anyway. ARM A2 pins exactly this: it fails if no
such unlinked row exists.

**The negative narrows to exactly ONE item — `queue_cf6aed5b`, POPULATION = 1.** Queue
row `queue_cf6aed5b` (session `mvs_b7a9f3a7`, created 12:14:55) accumulated **20
`deliveryAttempts`** by 12:26, produced **0** `turn_ingress` rows, **0** user rows,
its minted `msg_id` appears in **0** message rows, and it was later discarded
without delivery. Re-measured 2026-10-07 13:30 BRT, read-only: POP
`local_runtime_queue_items WHERE item_id LIKE 'queue_cf6aed5b%'` = **0** — the row no
longer exists at all. So this is a statement about **one discarded item**, *not* about
the target session.

**CORRECTION — the earlier draft said "the wake aimed at the TARGET session never
landed at all". That was WRONG, and the measurement that refutes it is the row below.**
POP `local_runtime_turn_ingress WHERE session_id='mvs_b7a9f3a7db404912b32d28fc11b83645'
AND queue_item_ids_json IS NOT NULL` = **2** (whole store, same read):

| turn | queue item | accepted | completed | status | delivered `msg_id` |
|---|---|---|---|---|---|
| `turn_aeec7923-878b-4025-88ca-f34ed6f4f59e` | `queue_4d760084-bc97-4edf-bef4-6dd6399a2556` | **2026-10-07 12:43:50** | 12:55:18 | **`completed`** | `msg-user-v1-wake14c1ccd40a834dceaf30d1001571ce95` → message row **227835** |
| `turn_4bb0112f-87a7-44eb-a135-0656d70b803a` | `queue_f6e768e9-a3a5-4fdf-bf44-2afbe44a5b56` | 2026-10-07 12:55:18 | 13:00:08 | **`completed`** | `msg-user-v1-wake81e67e020f4f450e8950c52921939b6c` → message row **228892** |

Both carry `claim_source='api'` and `queue_acknowledged_at_ms` set at the accept
instant; both produced a `role='user'` row whose `msg_id` is **the id we minted,
verbatim**. The first landed at **12:43:50** — into a session that had been holding a
turn since 12:00:13 — and that turn **completed**, where the traced 11:51:49 delivery in
§1 aborted. What this receipt actually measures is **latency and shape, not landing.**

### Why: the runtime refuses to start a turn in a session that already has one

* `local_runtime_session_locks`: session `mvs_b7a9f3a7` held
  `turn-lease:8084:…` from **12:00:13** to **12:47:24**.
* `turn_ingress` for that session: **exactly 1** row — the owner's own turn,
  `status='accepted'`, `completed_at_ms` NULL.
* The runtime says it in its own words, `heartbeat.log` 12:22:11:
  `mcode exec failed: The run failed: Session already has an active Turn. Use queue send to deliver the message after it.`

The 20 delivery attempts are therefore the **retry loop**, not duplicate wakes
(ARM A3 asserts the invariant that no item is ever delivered more than once).

**Consequence for the owner — INVERTED, and the 12:43:50 turn is what inverts it.**
An earlier draft of this receipt read busyness as the queue's *limit*: *"it is precisely
the idle case the owner needs — but it cannot fire into a busy session."* **That is
backwards.** Busyness is the condition the queue **exists for**, not a defect of it.
The runtime says so in its own words, quoted above: `Session already has an active Turn.
Use queue send to deliver the message after it.` — `queue send` is the *sanctioned*
route for a busy session, not a consolation prize. And the loop closes under load:
injected **12:40:54** → **accepted 12:43:50** → **completed 12:55:18**, into the session
that had held a turn since 12:00:13. A busy session is where a 3-minute wake earns its
keep; if the session were idle there would be nothing to wake. The surviving defects are
the other ones, unchanged and still real: **the retry is invisible in the log (D-3)**,
rows for unattached sessions strand forever (D-5), and the runtime's own cron scheduler
is dead (D-4).

---

## 2. Is the runtime's own cron scheduler alive in the running process?

### ANSWER: NO. Dead for 26.4 h. CONFIRMED, three independent ways.

| evidence | value |
|---|---|
| newest `local_runtime_v2_cron_runs.created_at_ms` | **2026-10-06 10:11:00** — age **1586.9 min** at 12:37:58 (ARM B1) |
| newest `role='user' AND source='cron'` message row | **2026-10-06 10:11:00** — same instant, age 1586.9 min (ARM B2) |
| POP `role='user' AND source='cron'` rows | **1383** — the scheduler once delivered 1383 user messages, and then stopped |
| probe cron `probe-ea7da67473ce` | armed 12:06:11, `next_run` 12:07:51, `run_count=0`, **0** rows in `cron_runs`, ~31 min overdue (ARM B3) |
| current runtime process | node pid **8084**, `…\@minimax-ai\code\cli.js --continue`, started **2026-10-07 11:59:30** |

The last line is the decisive one: **every row in the cron table predates the
process that is running now.** This process has produced zero cron runs in its
entire 2h38m uptime.

**The false-claim shape (ARM B4, control):** `cron_runs` still holds **1442
rows**. "The cron table is non-empty" PASSES, "a cron ran" PASSES — while the
scheduler is dead for a day. That is precisely how a confident green is produced
from a table that stopped moving.

---

## 3. Does the Windows task fire, and does each fire change the queue?

### The task fires reliably. Whether a fire CHANGES THE QUEUE is a different
### question, and for six consecutive fires the answer was **no**.

* Task `\SottoReplayHeartbeat`: Status `Pronto`, "Repetir: a cada 0 hora(s), 3 minuto(s)",
  início 11:52:00, last run **12:31:01**, last result **0**, next 12:34:00.
* Driver: `pwsh -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "…\heartbeat.ps1"`.
* **POP fires in the 15-min window** (at 12:37:58): **4**; max inter-fire gap
  **3.22 min** (ARM C1). Over a 180-min window: 18 fires (ARM C4 control).
* **Queue effect per fire:** 12:07:17 → 12:19:05 = **6 fires, 6× `WAKE refused rc=2`**.
  The task did its job; the wake did nothing, every time.

The log vocabulary changed three times during this audit
(v2 `WAKE queued` → v3 `WAKE enqueued/refused` → v4 `WAKE sending/no-op` + `PRUNE`),
so the gate asserts a **fire** on the *outcome line*, never on phrasing.

---

## 4. What is the failure mode when it does not work?

### A stale row accumulates, and the dedupe then refuses every future injection.
### Reproduced deterministically. YES — this is the real trap.

**Accumulation — measured.**
* POP rows with `expires_at_ms IS NOT NULL` across the whole table: **0**.
  Nothing in the shipped path ever expires a row.
* Oldest live queued row: `queue_1dfd5c7c`, session `mvs_ea552229`, created
  **2026-10-06 20:25:46** — **~972 min (16.2 h)** old, `status='queued'`,
  1 deliveryAttempt, **0** proven deliveries, never acknowledged. (ARM A4)
* The queue also swallowed the **owner's own real typed message**
  `reiniciei. que workspace estamos? só responde em uma frase`
  (queue row 4614, session `mvs_a00662bf`, 11:56:22). It never became a user row;
  it was deleted from the queue at ~12:20 **without delivery**. A queue row can
  silently eat a real user message.

**The wedge — the predicate.** `wake-fix.py` `cmd_inject` refuses whenever any
row is queued for the session:

```python
pending = con.execute(
    "select count(*) from local_runtime_queue_items where session_id=? "
    "and status='queued'", (args.session,)).fetchone()[0]
if pending and not args.allow_stack:
    return 2
```

**Deterministic reproduction on a throwaway store, using the EXACT shipped
predicate (ARM D1 / D2):**

| arm | setup | 5 consecutive injections |
|---|---|---|
| **D1 — cure reverted** (shipped predicate, no expiry) | 1 stale queued row, `expires_at_ms = NULL` | **2, 2, 2, 2, 2** |
| **D2 — control** (cure: stale row cleared) | same store, row deleted | **0, 0, 0, 0, 0** |

Only the cure changes the outcome, which is what makes D1 a real control.

**Live consequence:** 12:07:17 → 12:19:05, 6/6 fires `rc=2`.

**Cure, landed by another lane at 12:28:03 while this audit was running:**
`wake-fix.py prune` mode + `heartbeat.ps1` calling it —
`[12:28:03] PRUNE rc=0 :: PRUNE session=mvs_b7a9f3a7… stale_mins=3 … pruned=1`.
ARM D3 now asserts the durable contract instead: **RED only when a stale row
exists AND nothing prunes or expires it.**

**Severity ordering of the failure modes, worst first:**
1. **Silent refusal** — a fire that is refused logs exactly like a fire that worked.
2. **Permanent wedge** — a stale row for a session nobody is attached to blocks
   that session's wake forever (16.2 h and counting on `queue_1dfd5c7c`).
3. **Silent data loss** — real queued user messages deleted undelivered.
4. **Retry without progress** — 20 deliveryAttempts, zero deliveries, no alarm.

---

## 5. DEFECTS REPORTED — NOT FIXED (I am the auditor)

Each is a file, a line, and the fix. None applied.

**D-1 · `wake-fix.py:228` — invents a `userMessageId` of a shape the runtime never writes.**
```python
d["userMessageId"] = f"msg-user-v1-wake{uuid.uuid4().hex[:32]}"
```
The runtime writes `msg-user-v1-` + 43 base64url chars = **length 55**
(measured across 20 recent `role='user'` rows). This mints **length 48**, hex
alphabet. POP of message rows with the `msg-user-v1-wake%` prefix: **0**.
Measured consequence: the payload-identical delivered user row (225419) carries a
runtime-minted 55-char id, not the one we wrote — so any dedupe keyed on the id we
invent cannot match. **FIX:** copy `userMessageId` from the template unchanged,
like every other field (`d = dict(tpl)` already does this for the rest).

**D-2 · `wake-fix.py` `cmd_status` — the cron query can never match a real cron expression.**
```python
"where j.schedule_json like '%* * * * *%'"
```
A real expression is `*/3 * * * *`, which contains four trailing stars, not five.
Measured: this query returns **0 rows** while the store holds **30** scheduler
jobs. The status tool therefore prints an **empty cron section** — it hides the
exact outage documented above, and a reader concludes "no crons configured".
**FIX:** `like '%* * * *%'` (POP **10** rows) or
`json_extract(schedule_json,'$.kind')='cron'` (POP **12** rows), against POP **30**
scheduler jobs store-wide. **Do not write the shorter `like '%* * *'` I first proposed
— it returns 0 rows for the same reason the original did, and that is the whole point:**
a SQL `LIKE` pattern with no trailing `%` is END-ANCHORED, so a trailing `*` inside the
pattern is meaningless and the match must run to end-of-string; these rows end in
`"America/Sao_Paulo"}`. Re-measured 2026-10-07 13:30 BRT, whole table, read-only:
`'%* * * *'` → **0**, `'%* * * *%'` → **10**, `json_extract(...,'$.kind')='cron'` →
**12** (kinds: `cron` 12, `once` 18).

**D-3 · `heartbeat.ps1` — the refusal is logged indistinguishably from success.**
`WAKE refused rc=2 (already queued, not stacking)` was read as healthy for six
consecutive fires (12 min). **FIX:** log the blocking row's `item_id` and age, and
separate the two cases that matter — *a row is queued and the session is busy*
(fine, it will deliver) from *a row has been queued > N min with 0 attempts*
(wedged, prune it).

**D-4 · nothing alarms on the dead runtime cron.** 1383 cron deliveries, last one
26.4 h ago; probe crons arm and never run; the only cron observability is
`wake-fix.py status`, whose query is broken (D-2). **FIX:** alarm when
`now - max(local_runtime_v2_cron_runs.created_at_ms) > 15 min` **while** a row
exists with `local_runtime_v2_cron_definitions.deleted_at_ms IS NULL` joined to a
`state='active'` scheduler job.

**D-5 · rows for unattached sessions strand forever.** `queue_1dfd5c7c`, 16.2 h,
never claimed. Partially cured by the 12:28 `prune`; **verify the prune also
covers sessions with no attached runtime**, which is exactly row 4200's case.

**D-6 · each wake pass leaks a runtime process.** `heartbeat.log` 12:31:09 —
`rc=4 :: Runtime shutdown deadline exceeded after 60000ms` for the shutdown,
observability, logging and OAuth-watch cleanups. **N=1 observation, NOT a rate.**
**FIX:** measure across ≥20 passes before treating it as a rate; if real, the pass
must be bounded well under 60 s.

---

## 6. NOT VERIFIABLE WITHOUT RESTART / NOT MEASURED

* **Delivery into an IDLE session, end to end, inside 3 minutes — NOT MEASURED.**
  The target session held an active turn for the entire observation window
  (12:00:13 → 12:47:24). The one delivery I traced took **28 min 15 s**. So the
  owner's actual requirement — *"cron de 3 em 3 minutos acorda-me como uma
  mensagem de utilizador"* — is **NOT yet demonstrated**, and the runtime cron
  path that once did it (1383 times) has been dead for 26.4 h.
* **Whether the heartbeat ever flashes a console window — NOT MEASURED.**
  `heartbeat.ps1:78` runs `& python $wakeFix …` — `python.exe`, a *console*
  application — under a `-WindowStyle Hidden` pwsh. My gate censused only **its
  own** children: **460 samples at 50 ms, 0 visible** (ARM E1). Proving the
  heartbeat never flashes needs a ≥3 min census at its own cadence, because the
  house 60 s census cannot see a short-lived window. **This is a hard-rule risk
  and it is unmeasured.**

---

## 7. SELF-AUDIT

**Named verification boxes created (19 arms, 6 of them controls):**
`A1-queue-linked-delivery-proven` · `A2-control-textsearch-would-lie` *(control)* ·
`A3-no-duplicate-delivery` · `A4-no-expiry-strand` · `B1-cron-scheduler-stale` ·
`B2-cron-user-delivery-stopped` · `B3-probe-cron-never-ran` ·
`B4-control-table-not-empty` *(control)* · `B5-minted-userMessageId-shape` ·
`C1-task-fires-in-window` · `C2-latest-fire-is-healthy` · `C3-every-fire-accounted` ·
`C4-control-window-is-load-bearing` *(control, two-sided)* ·
`D0-dedupe-predicate-still-in-source` ·
`D1-stale-row-refuses-forever` *(cure reverted in a copy)* ·
`D2-control-expiry-clears-the-wedge` *(control)* ·
`D3-stale-row-never-blocks-a-wake` · `E1-no-visible-window-from-this-gate` ·
`F1-runtime-process-identified`.

**Confidence, per claim, and what would move it.**

| claim | confidence | what would move it |
|---|---|---|
| queue delivery works, proven by ingress linkage | **HIGH** | a single counter-example where a linked turn has no user row (20/20 currently have one) |
| text search would have produced a false green | **HIGH** | the unlinked row (225419) disappearing from the store |
| runtime cron dead ≥26 h | **HIGH** | any `cron_runs` row newer than 2026-10-06 10:11 |
| the target-session wake never landed | **HIGH** | finding a user row carrying `msg-user-v1-wakeff0ab…` |
| the wedge is permanent for an unattached session | **MEDIUM-HIGH** | evidence that PRUNE reaps rows whose session has no runtime — unmeasured |
| D-2 query never matches | **HIGH** | a scheduler row whose `schedule_json` really contains five stars |
| D-1 id shape is wrong | **LOW** — **re-rated 2026-10-07 13:30 BRT; the falsifier FIRED.** The shape claim survives; the *causal role* is **REFUTED**, not merely unproven. POP `local_runtime_message_rows WHERE msg_id LIKE 'msg-user-v1-wake%'` = **2**, and **row 227835** carries `msg-user-v1-wake14c1ccd40a834dceaf30d1001571ce95`, **byte-identical** to `_main/backup-20261007-124054-inject-11b83645.json` (same 48 chars, same sha256 `3fa899fbaff4254e…`, same `createdAt` 1791387654884 = 12:40:54). That id **IS** the delivered `msg_id`, of the turn **accepted 12:43:50** into the target session — so "any dedupe keyed on the id we invented cannot match" is **false as written**. Severity left is cosmetic (hex, not base64url), and `wake-fix.py:97` now mints the runtime shape anyway (`secrets.token_urlsafe(32)`; current bytes sha256 `56DA814D…`, mtime 13:27:02) | nothing that would raise it; what would *lower* it to none is counting the 2 rows as intended behaviour |

**Missing protocols.** No test of an idle-session delivery (blocked: the owner's
turn occupies the window). No ≥3 min window census of the heartbeat. No
independent reviewer (§8). No `git` work: I changed no tracked source, so there
is no sha to report — that is deliberate, not an omission.

**Gate doubts.**
* The store is being written by another lane *while the gate reads it*:
  `heartbeat.ps1` changed at 12:07, 12:22 and 12:35. Any live arm can flip
  between runs; that is why every run prints revision pins.
* The gate takes ~2.5 min: it does full-table `LIKE` scans over ~118k message rows.
* `A3` is close to vacuous — POP of live queued rows was 1 during the run. It
  asserts a real invariant (no duplicate delivery) but weakly.
* `C2` had to be weakened from "no failure in the log" to "the **latest** pass is
  healthy", because an append-only log keeps scars forever. A gate that demands
  a scar-free history is red by construction — I would rather report that than
  ship an arm that always passes.
* I fixed two of my own arms mid-run after they failed for the *wrong* reason
  (a marker set that shrank when a queue row was consumed; a lifetime-vs-window
  confusion). Both were instrument bugs, not findings, and both are now stable.

**Did another subagent review this?** **NO.** This seat has no subagent dispatch
tool (`task`), so the mandatory reviewer of §6 of the lane brief could not be run.
Everything in §5 and §6 is my own adversarial pass and has had no independent
challenge. **Treat the defect list as unreviewed.**

---

## 8. Raw evidence files (all in `_main/`)

`_lane16-census0..15.{py,out.txt}` (schema census, queue dump, delivery search,
turn_ingress trace, claim trace, cross-match, latency) ·
`_lane16-gate.out.txt` (the gate report with revision pins) ·
`_lane16-gate-console.txt` · `_lane16-control-log-copy.log` ·
`_lane16-sim-{nocure,cure}.out.txt` · `_lane16-stdin-test.out.txt`.

Every sqlite connection in this lane used
`sqlite3.connect("file:…?mode=ro", uri=True)`. **Nothing in the runtime store was
written by this lane.** The only file written outside `_main/` was a throwaway
`_lane16-wedge-sim.sqlite`, deleted at the end of ARM D.