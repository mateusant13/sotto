# RECEIPT 24 — THE SIX WAKE DEFECTS APPLIED, PLUS A SEVENTH

**Lane:** apply the defects of `receipt-21-wake-mechanism-audit.md` (lane16, auditor).
I am the applier, not the auditor. Every number in receipt-21 that this lane
depends on was **re-measured before the code was touched**, and two of them did
not survive. Those are in §1 and they are the most useful thing here.

**Files I own and changed (nothing else):**
`heartbeat.ps1` · `wake-fix.py` · `check-delivery.py` · this receipt.

**Gate:** `pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane24-wake-defects-gate.ps1`
→ **23 arms, 8 of them controls, `LANE24-GATE PASS`, exit 0**, result
`_main/_lane24-gate.out.txt`.

**Revision pin of the gate run that produced PASS** (2026-10-07T16:28:12Z):
`heartbeat.ps1` sha256 `FB5216B0C05E0E86B399ECD83…` · `wake-fix.py`
`56DA814D7008C32D2AA2CDD1D…` · `check-delivery.py` `C5633CE46E1A1B9641D2E7861…`.
**These bytes are the claim.** The wake machinery was being rewritten by another
lane while receipt-21 audited it; the same hazard applies to this receipt. (An
earlier PASS in this lane pinned `49A7EF…`/`92AC0F…`/`5AB18B…`; those predate the
self-review fixes in §6.4 and are superseded.)

> **A GATE THAT ONLY EVER PRINTS PASS IS NOT A GATE.** This one went RED **four
> separate times** during construction — run 1: 4 RED, run 2: 1 RED — and it caught
> **two defects in my own instruments**, both of which would have shipped as green
> (§6). Every control reverts its cure in a COPY and asserts the arm fails on that
> copy, and `New-Revert` **throws** if the revert pattern is missing, because a
> control that silently no-ops is worse than no control.

---

## 0. The headline

The wake machinery now **fails loudly and cannot wedge**, and the alarm the audit
asked for is wired and **is firing in production right now** (`CRON-ALARM rc=3` on
the live 27 h outage, `heartbeat.log` 13:22:01).

The most important finding is not one of the six. It is §1: **two of the audit's
numbers were wrong, and one of its proposed fixes would not have worked.** An
audit is an input, not a conclusion.

---

## 1. TWO OF RECEIPT-21's NUMBERS DID NOT SURVIVE RE-MEASUREMENT

Both re-measured read-only before any edit. Evidence `_main/_lane24-census.out.txt`,
`_main/_lane24-census2.out.txt`.

### 1.1 "POP of message rows with the `msg-user-v1-wake%` prefix: **0**" — it is 39.

| | receipt-21 (12:40) | re-measured (12:58 → 13:22) |
|---|---|---|
| `msg-user-v1-wake%` rows, whole table | **0** | **39** |
| of those, `role='user'` | 0 (implied) | **2** — ids 227835 (12:40:54), 228892 (12:49:03), session `mvs_b7a9f3a7` |
| `msg-user-v1-wake%` prefix length histogram | — | `{48: 1, 55: 39}` in the newest 40 `role='user'` rows |

The two user rows carry **our** 48-char ids **verbatim**. So receipt-21's own
stated mover for its D-1 confidence — *"a delivery where our 48-char id **is** the
delivered `msg_id`"* — has since occurred, twice.

**Therefore D-1 was NOT blocking delivery.** The audit rated the causal role
MEDIUM/unproven; the honest answer is **no, it was not causal on the exec path**,
and I say so in §3.1 rather than banking the fix as a delivery fix.

### 1.2 The proposed fix for D-2 would ALSO have returned 0 rows.

Receipt-21 §D-2 says the shipped `like '%* * * * *%'` wants five stars while a real
expression has four, and proposes `like '%* * * *'`. Measured on the live store:

| pattern | rows (POP = 30 scheduler jobs) |
|---|---|
| `like '%* * * * *%'` (shipped) | **0** |
| `like '%* * * *'` (**the audit's proposed fix**) | **0** |
| `like '%* * * *%'` (five stars, wildcards at both ends) | 10 |
| `json_extract(schedule_json,'$.expression')` with 5 fields | **12** |

The proposed fix drops the **trailing** `%`, so the pattern must match to
end-of-string — and these rows end in `"America/Sao_Paulo"}`. Both star patterns
are wrong. The cure counts **fields**, which is what "is this a cron" means.
Had I applied the audit's fix literally, D-2 would have stayed broken and the
status tool would still have printed an empty cron section.

---

## 2. WHAT THE OTHER AUDIT NUMBERS DID SURVIVE (reproduced before editing)

| claim | receipt-21 | re-measured | verdict |
|---|---|---|---|
| runtime `userMessageId` length | 55 (POP 20) | 55 in 39 of the newest 40 | reproduced |
| shipped mint length | 48 | 48 | reproduced |
| shipped cron query rows | 0 of 30 | 0 of 30 | reproduced |
| wedge, shipped predicate | `2,2,2,2,2` | `2,2,2,2,2` | reproduced |
| wedge, cured | `0,0,0,0,0` | `0,0,0,0,0` | reproduced |
| rows with `expires_at_ms` set | 0 of 4 | 0 of 2 | reproduced |
| `cron_runs` newest | 2026-10-06 10:11:00 | same; age **27.2 h** at 13:24 | reproduced, still decaying |
| shutdown-deadline occurrences | N=1 | see §3.6 — **N is now 5, not a rate** | extended |

Both wedge arms were reproduced **by driving the shipped `wake-fix.py` as a
subprocess and reading its real exit code** (`_main/_lane24-wedge-sim.py`).
Receipt-21's ARM D1/D2 re-implemented the predicate in the gate's own python,
which proves the gate's copy of the predicate, not the one that ships.

---

## 3. THE SEVEN DEFECTS, ONE BY ONE

### 3.1 D-1 — `userMessageId` shape · FIXED · **and it is NOT a delivery fix**

**Change** `wake-fix.py`: `mint_user_message_id()` returns
`'msg-user-v1-' + secrets.token_urlsafe(32)` = **length 55**, 43 base64url chars
decoding to 32 bytes — the measured runtime shape, checked against the runtime's
own histogram in the gate (39 of the newest 40).

**I deviated from the audit's fix, deliberately.** Receipt-21 says *"copy
`userMessageId` from the template unchanged, like every other field"*. `d = dict(tpl)`
already does that for every other field; copying this one verbatim would give
**every wake the same id as the template row**. A collision is strictly worse than
a wrong alphabet. Shape is what was asked for; identity stays unique.

**STATED PLAINLY, as required: this does not change delivery.** Proof: two
`role='user'` rows already reached the session carrying our **48-char** ids
(§1.1). The id shape was wrong and is now right. That is the whole claim.

**Adjacent shape mismatch found, NOT fixed (out of scope, disclosed):** the
runtime writes `createdAt` as a **string** (`'1791329146949'`); we write an int.
Same one-line class. It did not block the two deliveries above. Left alone.

### 3.2 D-2 — the cron query · FIXED (not with the audit's fix)

`cmd_status` now selects
`json_extract(schedule_json,'$.expression')` and filters on
`len(cron_fields(expr)) == 5`. POP 30 jobs → **12 cron-expression jobs listed**,
including `probe-ea7da67473ce` (`*/3`, `run_count=0`, next_run 55 min overdue) and
`d43fb9be` (`*/3`, `run_count=444`) — the outage receipt-21 documented, now
visible. Gate arm reverts the cure in a copy and asserts the reverted copy lists
**0** — the exact "no crons configured" illusion.

### 3.3 D-3 — the dedupe wedge · FIXED IN THE PREDICATE, and the limit is stated

The shipped predicate counted `status='queued'` rows regardless of age. Now
`split_pending()` separates **LIVE** from **DEAD**: a row whose `expires_at_ms`
has passed is not a pending message, it is a corpse, and it is dropped with a
backup. `--stale-mins 999` (prune **off**) still yields `0,0,0,0,0` on an expired
row.

**The limit, as an arm, not a footnote:** on a row with `expires_at_ms = NULL` the
**shipped** code still returns `2,2,2,2,2`. The predicate fix does **not** close
that hole, and the gate asserts the hole exists (`D3-shipped-predicate-still-wedges…`).
This is exactly why D-5's sweep is load-bearing rather than belt-and-braces.

**D-3's other half — the refusal must be legible.** `WAKE refused rc=2` was a
fixed string that read as healthy for six consecutive fires. `describe_row()` now
prints one `BLOCKING` line per row with item_id, age, claim, expiry and
deliveryAttempts, and the driver logs the whole thing.

### 3.4 D-5 — orphan rows · **BOTH cures, and here is why**

Receipt-21 asked me to decide: prune session-wide, **or** set `expires_at_ms`.

**I do both, because neither alone is a cure you can demonstrate:**

- **Session-wide sweep is the primary.** The wedge predicate is keyed on
  `session_id`, so a session-scoped prune *structurally cannot* reach an orphan in
  another session. That is the whole defect.
- **`expires_at_ms` on insert is the belt.** The column exists and is indexed, but
  **MEASURED: 0 rows in this store have ever carried it.** "The runtime reaps it"
  is unproven, so it cannot be the load-bearing half.
  The TTL is **30 min**, which is not a guess: the runtime's own in-memory cron
  queue discards an undelivered entry after `OCe = 1800*1e3`
  (`chunk-U7ACBEGU.js:1467`).

**Safety of the sweep** (the obvious objection): a **foreign** session's row must
exceed `--orphan-min-mins` (60) to be reaped; the target's own floor is
`--stale-mins`. A **claimed** row is never reaped at any age. 60 min is
deliberately more conservative than the runtime's own 30. Gate arm asserts all
three: orphan swept, another session's 5-min row **kept**, the target's own 5-min
row **kept** under the busy-path command.

**Attribution, stated honestly:** orphan `queue_1dfd5c7c` (988.6 min at 13:00) was
present in my 13:00 census and **absent by 13:16**. The newest prune backup is
13:04:04, which **predates** this lane's sweep going live (13:16). **This lane
cannot claim it reaped that row**, and does not.

### 3.5 D-4 — no alarm on a dead scheduler · FIXED, ONE ALARM (D-2 and D-4 together)

`wake-fix.py cron-alarm` → **rc=3** when `now - max(cron_runs.created_at_ms) > 15 min`
**while** an undeleted cron definition joins a `state='active'` scheduler job; rc=0
otherwise. The driver calls it **once per fire**, before anything else, and logs a
second WARNING line on rc=3.

Both halves of the condition are load-bearing: a store with no crons armed is not
an outage, and a dead scheduler with nothing armed is harmless.

**It is firing in production.** `heartbeat.log` 13:22:01:
`CRON-ALARM rc=3 … newest_run=2026-10-06 10:11:00 age=1631.0min
armed_active_crons=5`. POP: `cron_runs` rows = 1442, window = whole store.

### 3.6 D-6 — `Runtime shutdown deadline exceeded` · **COUNTERED, NOT FIXED, NO RATE**

**I claim no rate, and I say what N I have.** The instrument now counts:

```
PASS-SHUTDOWN-COUNTER exec_passes=5 shutdown_deadline=0 this_pass=0 rate=0,0%
  first_exec_utc=2026-10-07T16:06:39Z
```

**N = 5 exec passes**, 0 occurrences, since the instrument landed at 13:19.
Receipt-21 had N=1 with 2 log lines. **5 is not a rate** — receipt-21's own note
that 20 passes ≈ 60 minutes still stands, and this file's `--timeout 12m` does not
make that faster. The counter is the deliverable: at N≥20 the number becomes real.

The denominator is **exec passes**, not fires, because a fire that takes the queue
path runs no `mcode exec` and leaks no runtime process. Counter file:
`_main/wake-counters.json`. Proven live by driving the **real** `heartbeat.ps1`
against a stub `mcode` that emits the string: `exec_passes=1 shutdown_deadline=1`.

### 3.7 D-7 — **`status` does not predict exec acceptance** (added mid-lane)

Ground truth: POP = 2 refusals, 13:05:05 and 13:08:59, both rc=4, both
`"Session already has an active Turn. Use queue send to deliver the message after it."`
`turn_ingress` rows accepted in the window: **n = 0**. **No delivery latency is
computed, because there is no `accepted_at_ms` to compute it against.**

**Which signal actually predicts — measured, by reconstructing each refusal at its
own instant (`_main/_lane24-d7-census2.py`):**

| signal | predicts-busy? | POP |
|---|---|---|
| `local_runtime_sessions.status` | **0 of 2 — FALSE NEGATIVE** | 2 |
| an OPEN turn (`accepted_at_ms ≤ now < completed_at_ms`) | **2 of 2** | 2 |

The chosen predicate is **two signals**, because neither alone is safe:

- **PRIMARY — a turn lease** in `local_runtime_session_locks`, `expires_at_ms > now`.
  It is what the runtime names in its own error, and it carries a real expiry:
  POP 10 lock rows store-wide, all `owner_kind='turn'`, 0 without expiry, 0 expired.
- **SECONDARY — an open turn, BOUNDED at 45 min.** It has no expiry and does
  linger: POP 10 unfinished rows, oldest 60.3 min. Unbounded it would wedge the
  channel — the D-3 defect class again. 45 min sits just above the measured turn
  duration distribution over **POP 3743** completed turns: median 11.8 / p90 41.8 /
  p99 98.9 / max 253.6 min.

**Two measurement bugs I had to fix before I could trust this, named rather than
quietly repaired:**
1. `local_runtime_session_locks` is **current-state only** — rows are deleted when
   the turn completes (the 13:07:11 lease was present at 13:10:46, gone by 13:11:07,
   the turn having completed 13:10:53). A "lease held at 13:05?" query run today
   says **nothing about 13:05**. Good live predicate, useless historical one.
2. `completed_at_ms is not null` is **not** "was finished at that instant". My first
   version reported both refusals as FINISHED. Both timestamps are retained; the
   comparison must be against the instant.

**The belt — and this is the part that actually closes it.** No pre-flight read can
be perfect: a turn can start between the read and the exec. So when exec is refused
for that reason the driver **falls back to the queue in the same pass** — the
transport the runtime itself names. A pre-flight read is a heuristic; **the refusal
is the fact.**

**Live corroboration of the disagreement**, found while building this: session
`mvs_ea552229` reads `status=aborted` with no lease and no open turn — status says
busy, nothing is running. The failure is not one-directional.

---

## 4. THE DELIVERY CHECK (the arm the brief demanded)

**Authoritative link, and the only one used:**
`local_runtime_turn_ingress.queue_item_ids_json` **names the queue item** AND
`queue_acknowledged_at_ms` is set AND a `role='user'` message row in the same
session carries that same **`turn_id`**. Three runtime tables joined by
runtime-written identifiers. No payload text is consulted anywhere in the proof.

**MEASURED: `DELIVERED_BY_QUEUE = 20/20`** (POP = 80 queue-driven turns store-wide,
newest 20 examined).

**Why the `turn_id` hop and not the item's `userMessageId`:** the STRICT variant
(msg_id match) is **0/20**, because a delivered queue row is **deleted** by the
runtime, so its `userMessageId` cannot be read back. The `turn_id` hop is what
survives. Had I asserted the strict variant the arm would have been red forever
for a reason that is not a defect.

**The trap, measured and still live.** A `role='user'` text match is NOT proof of
delivery by the queue. Rows 227835 and 228892 carry our wake payload, `turn_id`
NULL, and **no `turn_ingress` row at all** — a hand-pushed `mcode exec --session`
produced them. `check-delivery.py` prints `MARKER_MATCHES_ARE_NOT_PROOF` so the
distinction cannot be lost a second time, and the gate proves the instrument
rather than asserting it: against a **doctored store** where the marker matches 1
user row and nothing is linked, the checker reports **0/0**. A marker-grep would
have reported a delivery there.

`check-delivery.py` was rewritten around this and gained `--require-linked` /
`--db`, which its previous signature had no equivalent of.

---

## 5. THE GATE — 23 arms, 8 controls

`_lane24-wake-defects-gate.ps1`. Controls marked ★; each reverts its cure in a COPY.

| # | arm | what it holds down |
|---|---|---|
| 1 | D1-minted-id-matches-the-runtime-shape | the 55-char shape, checked against the runtime's own histogram |
| 2 | ★ D1-control-mint-reverted-goes-RED | 48-char hex mint fails the same assertion |
| 3 | D2-cron-query-finds-real-expressions | 12 cron jobs listed |
| 4 | ★ D2-control-star-pattern-reverted-goes-RED | five-star copy lists **0** |
| 5 | D4-cron-alarm-fires-on-the-live-outage | rc=3 on the real 27 h outage |
| 6 | ★ D4-control-alarm-silent-when-cron-is-fresh | **two-sided**: same predicate, freshest run moved to now → rc=0 |
| 7 | ★ D4-control-alarm-reverted-goes-RED | threshold 10¹⁸ min → silent on the same outage |
| 8 | D3-wedge-is-impossible-not-merely-swept | `0,0,0,0,0` with the prune **off** |
| 9 | D3-shipped-predicate-still-wedges-on-a-NEVER-expiring-row | documents the **limit** (`2,2,2,2,2`) |
| 10 | ★ D3-control-expiry-blind-predicate-goes-RED | expiry-blind copy → `2,2,2,2,2` |
| 11 | D5-orphan-swept-but-no-fresh-row-is-collateral | orphan swept; **two** fresh rows kept |
| 12 | ★ D5-control-session-scoped-prune-reverted-goes-RED | pre-fix copy → orphan survives |
| 13 | D7-idle-status-but-turn-lease-held-takes-the-QUEUE-path | the control the brief asked for |
| 14 | D7-open-turn-alone-also-marks-busy | secondary signal in isolation |
| 15 | D7-a-stuck-open-turn-cannot-wedge-the-channel | 90-min open turn → **not** busy |
| 16 | ★ D7-control-branching-on-status-reverted-goes-RED | status-branch copy says `busy=NO` |
| 17 | D6-shutdown-deadline-counter-is-instrumented | real heartbeat vs stub mcode, N=1/1 |
| 18 | A1-queue-linked-delivery-proven-by-turn-ingress | 20/20 by ingress linkage |
| 19 | ★ A2-control-textsearch-would-lie | 2 unlinked user rows exist right now |
| 20 | A3-doctored-store-marker-matches-but-nothing-is-linked | 0/0 where a grep would say "delivered" |
| 21 | X1-no-visible-window-from-this-gate | 25 ms census of its own pid tree |
| 22 | X2-multiline-prompt-goes-over-stdin-not-argv | D-argv survives |
| 23 | X3-driver-branches-on-wake-plan-and-falls-back-to-queue | D-7 survives |

**Inherited fixes preserved and asserted as arms 22/23:** the prompt goes over
**stdin** via `--input -` (never argv), and the prune-vs-queue branch structure.

**Live store is read-only to this gate.** Every writing arm builds a throwaway
store under `_main/_lane24-gate\`.

---

## 6. THE GATE CAUGHT TWO DEFECTS IN MY OWN INSTRUMENTS

Reported because a receipt that only lists wins is not a receipt.

1. **A control that passed for the wrong reason.** The D-7 control asserted on
   `/busy=NO/`, which matched the substring inside `status_says_busy=NO` — and its
   store carried *both* a lease and an open turn, so the secondary signal masked
   the reverted primary. Fixed by splitting into three single-signal stores and
   anchoring the parse on `(?<![_a-zA-Z])busy=(YES|NO)`.
2. **A result file containing the gate's own source.** Piping a `{ … }` block into
   `Set-Content` wrote **529 bytes of script** instead of the report on this pwsh.
   Reproduced in isolation, then replaced with an explicit array and `-Value`.

Plus three instrument faults found and fixed before they could mislead: the cron
`sweep` was deleting its own template row; the orphan sim asserted the wrong
scenario (`--stale-mins 3` prunes the target's row **by design**); and the cron
"fresh" control tried to `INSERT` into a table with five `CHECK` constraints and a
foreign key (`CHECK constraint failed: local_runtime_cron_run_trigger`) — now
an `UPDATE`.

### 6.4 A defect in the SHIPPED code, found by self-review after the gate went green

`split_pending()` returned **two** buckets (live / dead) and treated a **claimed**
row as ordinary. That produced a real inconsistency between the two write paths:
**`cmd_inject` deleted every expired row, while `cmd_prune` kept every claimed
row.** So an expired-and-claimed row — one the runtime had taken and was
delivering *right now* — would have been deleted out from under it by the inject
path. Two paths, one predicate, opposite answers on the same row.

Fixed: `split_pending()` now returns **three** buckets — `live`, `dead`,
`claimed` — and a claimed row is neither pending (refusing on it would refuse a
message already in flight) nor reapable. `cmd_inject` prints it as `IN-FLIGHT`
and excludes it from the drop; `cmd_prune` keeps it. Gate re-run green on the new
shas.

**This is the fourth defect this lane found in its own work, and the reason the
"green gate" above is not sufficient evidence on its own.**

---

## 7. SELF-AUDIT

**Confidence per claim, and what would move it.**

| claim | confidence | what would move it |
|---|---|---|
| the seven defects are fixed as described | **HIGH** | one control that stops failing when its cure is reverted |
| D-1 shape was **not** causal for delivery | **MEDIUM-HIGH** | a delivery where a malformed id is rejected; the 2 existing deliveries argue against causality |
| D-7 `status` is not a predictor | **HIGH for 2/2** | it rests on POP 2. A refusal where a lease was **not** held and no turn was open would widen the story |
| the lease is the right primary signal | **MEDIUM** | a refusal with no lease held at all — the locks table cannot answer that historically |
| 45 min is the right bound for an open turn | **LOW-MEDIUM** | 45 is just above p90 of 3743 turns; a legitimately 2 h turn would be mis-read as idle, costing one wasted exec |
| alarm threshold 15 min is right | **MEDIUM** | a legitimately sparse cron cadence would alarm spuriously |
| queue delivery works end to end | **HIGH** | one linked turn with no user row (currently 20/20 have one) |
| **our own wakes have never been queue-delivered** | **HIGH** | 0 `turn_ingress` rows name any `msg-user-v1-wake…` id |

**The last row is the honest headline about the owner's actual requirement.** The
two wake messages that reached `mvs_b7a9f3a7` did so through `mcode exec
--session`, **not** through the queue. **A wake of ours claimed by a turn whose
`queue_item_ids_json` names our queue item has still never happened.** The channel
is proven (20/20 on the runtime's own rows); *our* use of it is unproven.

**Missing protocols.** No ≥3 min window census of the heartbeat itself (only its
own children — arm 21). No delivery latency for D-7, because n=0 turns were
accepted. No ≥20 exec passes, so no shutdown rate. No idle-session end-to-end
delivery by *our* queue row. `git`: **no commit was made** — the working tree in
this repo was not clean of other lanes' work, and committing other lanes' files
under my name would be worse than not committing.

**Gate doubts.**
* The live store is being written by the runtime and by other lanes **while the
  gate reads it**. Every run prints revision pins; a stale pin invalidates a
  figure.
* Arms 13–16 drive a synthetic store, not the live refusal. The refusal state was
  reconstructed from the store after the fact (§3.7), which is weaker than
  catching it live.
* Arm 19 is weak in the way receipt-21 flagged its own A3: it asserts that 2
  unlinked rows **exist**, and they can be consumed from the store.
* Arm 21 censused **0 child processes** at 25 ms — the gate's own children had
  already exited. It is a true reading and a weak one.

**Did another subagent review this?** **NO — and the reason is a missing tool, not
a skipped step.** §6 of `LANE-BRIEF.md` makes the reviewer mandatory. **This seat
has no subagent dispatch tool**, so `task(agent_name="verifier", …)` could not be
issued. Receipt-21 §7 records the identical blocker for lane16, so this defect is
known to the project and not unique to this lane.

**What I did instead, and what it is worth:** a four-defect adversarial self-review
(§6.1–6.4), which found a real inconsistency in the shipped code that a green gate
had not caught. **That is not a substitute for an independent reviewer.** Nothing
here has had an adversarial challenge from someone who did not write it, and the
receipt should be read with that stated plainly — exactly as receipt-21 asked.

---

## 8. WHAT I DID **NOT** DO

* **Did not** change `heartbeat.ps1`'s `$TARGET_SESSION`. It still points at
  `mvs_a00662bff…`, not this lane's own parent. That is the owner's routing
  decision, not mine.
* **Did not** fix the `createdAt` string-vs-int mismatch (§3.1). Disclosed, out of
  scope.
* **Did not** change the 60 s runtime shutdown deadline. It is upstream in the
  runtime; this lane only made it countable.
* **Did not** rename `CANONICAL_PRODUCER`, touch `history-source.js`, or go near
  `src/capture/**`, `src/index/**`, `src/asr/**` or the specs — other lanes are
  live in those.
* **Did not** report a delivery latency for D-7. n=0 turns accepted.
* **Did not** claim a shutdown rate. N=5.

---

## 9. RAW EVIDENCE (`_main/`)

`_lane24-census{,2}.py` + `.out.txt` (the two refuted numbers) ·
`_lane24-d7-census{,2}.py` + `.out.txt` (the D-7 predictor search) ·
`_lane24-delivery-census.py` + `.out.txt` (20/20 strict-vs-turn hop) ·
`_lane24-wedge-sim.py` · `_lane24-orphan-sim.py` (the two simulations) ·
`_lane24-gate.out.txt` (the 23-arm report with revision pins) ·
`_lane24-gate-console.txt` · `_lane24-gate\` (per-arm raw output).

Every sqlite connection read the live store as
`file:…?mode=ro`. Writes went to throwaway stores under `_lane24-gate\`, plus the
driver's own live writes via the Windows task: the sweep and `expires_at_ms` on
insert, each backed up to a JSON file first.