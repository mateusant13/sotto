# Receipt 23 — the text-match headline is retracted; the retraction's own evidence is TOO

**This receipt previously claimed the cron woke this live session, from a text match. That
text match is not evidence of a mechanism and the claim is retracted. But the retraction
that replaced it rested on a *stated* measurement that is itself false, so it is retracted as
well (2026-10-07, re-measured read-only). What stands now is stated below with the link
that carries it.**

> **CORRECTION (2026-10-07).** Lane L16's audit did not refute this receipt; it reported
> `local_runtime_turn_ingress.queue_item_ids_json = NULL` for message row 227835's turn. A
> direct read-only query of the live store shows the exact inverse. Both the original claim
> and the retraction rested on the same class of error — the original on a text match, the
> retraction on an unverified number. **No verdict in this file may be cited without its
> POPULATION and WINDOW.**

---

## 1. What I claimed, and why it was wrong

At 12:45:46 I wrote:

> `role='user'` id=227835, 12:40:54, `src=api`, carrying the ORCHESTRATOR MANDATE … the
> queue was empty afterwards: the row was **consumed** … the turn that followed began with
> the mandate as its incoming message — woken by the cron, not by the watcher.

**L16's finding, as reported:** message row 227835's turn has
`local_runtime_turn_ingress.queue_item_ids_json = NULL`. "It is not linked to any queue item.
It is a hand-pushed turn."

**That finding is REFUTED by the store, not merely doubted.** Re-measured read-only on
2026-10-07 at 13:27 BRT, window = the ingress row for that turn:

```
turn_id              = turn_aeec7923-878b-4025-88ca-f34ed6f4f59e
session_id           = mvs_b7a9f3a7db404912b32d28fc11b83645
queue_item_ids_json  = ["queue_4d760084-bc97-4edf-bef4-6dd6399a2556"]
claim_source         = api
client_request_id    = queue-delivery:claim_4d856235-b931-4100-b02f-3a34fd027cf5
status               = completed
accepted_at_ms       = 12:43:50 BRT   (queue_acknowledged_at_ms = 12:43:50 BRT)
```

Three independent fields name the queue item. **The turn WAS a queue delivery.** It was not
hand-pushed.

**The instrument discriminates, which is what makes this a refutation.** The same query on
`turn_muy999ue_j6wgbj` returns `queue_item_ids_json = NULL`, `claim_source = NULL`,
`client_request_id = NULL`, `status = completed`. A row that is genuinely unlinked reads NULL
in all three fields; row 227835's turn does not. The instrument can return NULL, and here it
does not.

**What I was right about the first time.** A marker match on `role='user'` proves a message
arrived. It does **not** prove *which mechanism* delivered it. That lesson survives this
correction untouched, and so does its reasoning about the "95 HEARTBEAT messages" and the
watcher's `DELIVERY-A CONFIRMED`.

## 2. The authoritative instrument

`local_runtime_turn_ingress.queue_item_ids_json`. A turn is a *queue delivery* only if that
column names a queue item.

**This number MOVES while you read it, so it must never be pinned as a standing fact.**
Re-measured read-only on 2026-10-07:

| population | definition | value | read (BRT) |
|---|---|---|---|
| **narrow (the one this receipt originally used)** | `queue_item_ids_json IS NOT NULL AND claim_source='api'` | **80**, of which **80/80** carry ≥1 `role='user'` row, **counter-examples = 0** | 13:27:32, re-read 13:27:44, 13:28:01, 13:28:38 |
| **broad** | `queue_item_ids_json IS NOT NULL` | **583** at 13:27:32 -> **585** at 13:28:01 -> **608** at 13:33 -> **618** at 13:38:10 | four reads, same session |
| **broad, carrying >=1 `role='user'` row** | joined against `local_runtime_message_rows` | **617 / 618**, i.e. **1** counter-example | 13:38:10 |
| **of the broad population, acknowledged** | `queue_acknowledged_at_ms IS NOT NULL` | **608 / 608** (of the 608 read at 13:33) | 13:33 |

The reviewer's series **78 -> 79 -> 80** is this same narrow census, moving; my four
re-reads put it at **80**. **The RATIO is stable and the NUMBER is not**: 100 % of the narrow
population carries a user row, at every reading. State the scope or do not state the number
— `claim_source='api'` alone excludes **538** queue-linked turns (618 - 80, read 13:38:10),
**537** of which also carry a user row. **The narrow census is the right one to quote and the
wrong one to generalise from.**

So queue delivery works **in general**, and this specific wake was one of them (section 1).

## 3. The one delivery actually traced end to end

POP = **1**. `queue_ec7ae0a0…` → ingress `turn_633acf0e…` → message row **225247**, whose
`msg_id` and `turn_id` are the injected ones **verbatim**. WINDOW: injected 11:51:49 →
delivered 12:20:04 = **28 min 15 s**. **That turn then aborted after 5 s.**

That is the honest state: a queue item was delivered as a user message, once, with identity
preserved, and the resulting turn died.

## 4. Why the wake aimed at this session did not land

POP = **1** item (`queue_cf6aed5b`): **20 deliveryAttempts, 0 turns, 0 messages**, discarded
undelivered. WINDOW 12:14:55→12:26.

Cause, measured: the runtime refuses a new turn in a busy session, and says so —
*"Session already has an active Turn. Use queue send to deliver the message after it."*
`session_locks` shows the target held `turn-lease:8084` from **12:00:13 → 12:47:24**, i.e.
across the entire window in which every fire was attempted.

## 5. Two defects this exposes in MY work, which are now actionable

**D-5 — PRUNE is session-scoped, so orphans are permanent by construction.** POP = **4**
queue rows, **0** of them with `expires_at_ms`; the orphan `queue_1dfd5c7c` aged
**959.3 → 974.2 min** across **5** samples, WINDOW 12:26→12:40:02, surviving the one logged
PRUNE event (POP = 1, scoped to the target session). Either prune session-wide, or set
`expires_at_ms` on insert.

**D-1 — the minted `userMessageId` has the wrong shape — RE-RATED LOW, and its falsifier has
fired.** The shape observation stands: POP = **20** most recent `role='user'` rows, all length
**55**; the minted wake ids are **48** (measured 13:28 BRT, both before and after the first
wake id — the histogram is 20×55 in either direction, so it is not an ordering artefact).

**The causal claim is REFUTED, and "POP of `msg-user-v1-wake%` = 0" was simply FALSE.**
Re-measured 13:27:32 BRT, **POPULATION = 2** such rows — **227835** (`msg-user-v1-wake14c1ccd…`,
12:40:54) and **228892** (`msg-user-v1-wake81e67e02…`, 12:49:03) — and **both carry the full
48-char id intact**, all 48 characters, with no truncation and no dedupe collision. Both
produced real queue deliveries: message row 227835 -> `turn_aeec7923…` (`queue_4d760084…`,
accepted 12:43:50) and row 228892 -> `turn_4bb0112f…` (`queue_f6e768e9…`, accepted 12:55:18),
both `status='completed'`. **WINDOW = 12:40:54 -> 12:55:18 BRT, read 13:27 BRT.**

The wrong-shape id therefore blocked, delayed and corrupted **nothing** that is measured.
**MEDIUM -> LOW. Cosmetic only.** (L16's MEDIUM rating rested on the POP=0 claim, and the
false POP=0 claim is what carried it.)

## 6. Corrected verdict

| claim | verdict |
|---|---|
| Queue delivery works as a mechanism | **PROVEN** — narrow census **POP 80**, **80/80** user rows, **0** counter-examples; broad census **583 -> 585 -> 608 -> 618**, WINDOW 13:27:32->13:38:10 BRT (the count moves; the ratio does not) |
| The 12:40:54 wake into THIS session was a queue delivery | **PROVEN** — **POPULATION = 2** resolved turns (`turn_aeec7923…` 12:43:50, `turn_4bb0112f…` 12:55:18), **WINDOW 12:40:54 -> 12:55:18 BRT**, each naming its queue item in `queue_item_ids_json` with `claim_source='api'` |
| The CRON specifically delivered that wake | **NOT PROVEN, and not claimed** — `queue_4d760084` was planted by a hand `inject` (`receipts/receipt-27-queue-delivery-latency.md` §2). Separately, every `WAKE delivered rc=0` in `_main/heartbeat.log` names the **owner's** session `mvs_a00662…`, POPULATION = 9, WINDOW 12:56:30->13:30:10 BRT — never this one |
| ~~"227835's turn is unlinked / hand-pushed"~~ | **RETIRED — FALSE.** `queue_item_ids_json = ["queue_4d760084-bc97-4edf-bef4-6dd6399a2556"]`, `claim_source='api'`, `status='completed'`, read 13:27 BRT. The instrument discriminates: `turn_muy999ue_j6wgbj` reads NULL in all three fields |
| The runtime's own cron scheduler is alive | **FALSE** — dead 26.5 h; newest run 2026-10-06 10:11:00, corroborated by 1,383 `source='cron'` user rows newest at the same instant |
| The Windows task fires | **TRUE** — 4 fires/15 min, max gap 3.22 min; but **6/6 consecutive fires were `rc=2` refusals**: the task did its job and the wake did nothing |
| A stale queue row wedges the channel permanently | **TRUE and reproduced** — shipped predicate `2,2,2,2,2`; with the cure `0,0,0,0,0` |

**What remains unproven, and is the owner's actual requirement:** that a wake reaches an
**idle** session within 3 minutes. The 12:43:50 and 12:55:18 deliveries landed into a session
that had a turn in flight, which is the queue's whole purpose — so they do **not** test the
idle case either way. L16 could not test it — the owner's turn held the window 12:00:13→
12:47:24 — and marked it `NOT VERIFIABLE WITHOUT RESTART`. That is still true.

**One more thing this receipt must not do again:** state a population without a WINDOW. The
broad census above moved **583 -> 618, i.e. +35 rows in 11 minutes**, while this file was
being corrected, and my own first draft of this very section carried two figures computed
from the 13:33 reading that were wrong by the 13:38 one. A number quoted here is a reading,
not a fact.

## 7. The lesson, stated so a future wake acts on it

I had a mechanism-shaped piece of evidence and read it as a mechanism. Before claiming
*which channel delivered a message*, name the link that ties the turn to the channel.
`role='user'` answers "did a message arrive"; `queue_item_ids_json` answers "did the queue
bring it". Those are different questions and I answered the wrong one three times today.

**And the retraction was the same failure wearing a lab coat.** The retraction did not
retract; it *replaced one unverified number with another unverified number* and then promoted
it to a verdict. A refutation needs its own instrument check — which is why the NULL in
`turn_muy999ue_j6wgbj` is what makes this a refutation and not an argument. **Check that your
refuting instrument CAN return the value you claim to have seen, before you publish it.**