# Receipt 27 — queue delivery latency, measured with the authoritative link

Closes the open item in `_main/DEBT-LEDGER.md` (D-IDLE-WAKE, latency arm) and the P0 that
sat open across three turns. Instrument: `_main/delivery-latency.py`.

---

## 1. The measurement

A turn is a **queue delivery** only when `local_runtime_turn_ingress.queue_item_ids_json`
names a queue item. That is the link. A `role='user'` message row is not — receipt-23
records the retraction that came from confusing the two.

```
POPULATION = the newest 5 turn_ingress rows for session mvs_b7a9f3a7db404912b32d28fc11b83645
of those, rows whose queue_item_ids_json IS NOT NULL = 2

item_id                                  injected   turn accepted
queue_4d760084-bc97-4edf-bef4-6dd6399a2556   12:40:54   12:43:50
```

**Latency, injected → queue-linked turn accepted: 2 min 56 s.**

WINDOW = injected 12:40:54, turn accepted 12:43:50, both read at 13:01:08.

The queue row is now **gone** — consumed, not left pending. POPULATION across all sessions
is larger: of the newest **200** ingress rows, **155** carry a non-null
`queue_item_ids_json`, so queue-linked turns are the normal case, not an exotic one.

## 2. What this does and does not prove

| claim | verdict |
|---|---|
| The queue consumes a row and starts a turn | **PROVEN** — POP=2 queue-linked turns in this session, POP=155/200 across sessions |
| Queue latency | **2 min 56 s**, POP=1 resolved sample for this session |
| The CRON delivered it | **NO — and this distinction is the whole point.** `queue_4d760084` was planted **by hand** at 12:40:54 by a direct `inject` call. The measurement is the queue's latency, not the cron's end-to-end. |
| The `rc=0` delivery at 12:56:30 | went through **`mcode exec`**, not the queue. It does **not** appear as a queue-linked turn in this session's ingress — POP=7 ingress rows for the idle session, of which exactly **1** is queue-linked, and that one is the 12:20:04 delivery, not the 12:56:30 one. |

So there are **two channels with two different latencies**, and I am not going to quote one
for the other:

- **queue** — for a session with a turn in flight. Latency measured: **2 m 56 s**.
- **`mcode exec`** — for an idle session. Measured: the process returns `rc=0`; its own
  process duration was **3 m 08 s**, which includes a full agent turn and is **not** a
  delivery latency. The exec path's delivery latency is **NOT INSTRUMENTED**.

## 3. A correction to receipt-23 — the conclusion is DISCARDED, the reasoning survives

Receipt-23 retracted my claim that the cron woke this session, on the evidence that message
row 227835's turn had `queue_item_ids_json = NULL`. This section previously wrote **"That
specific finding stands — that turn was hand-pushed."**

**It does not stand. It is refuted, and this receipt said so in its own section 1.** Row
227835's turn **IS** the queue-linked turn accepted at 12:43:50: message row 227835 ->
`turn_aeec7923-878b-4025-88ca-f34ed6f4f59e`, `queue_item_ids_json =
["queue_4d760084-bc97-4edf-bef4-6dd6399a2556"]`, `claim_source='api'`,
`client_request_id='queue-delivery:claim_4d856235-b931-4100-b02f-3a34fd027cf5'`,
`status='completed'`, `queue_acknowledged_at_ms = 12:43:50 BRT`. **The "hand-pushed" sentence
described the same turn that section 1 of THIS file had already resolved end to end.** There
was no second turn hiding beside it. Both halves of this receipt were true at once, and that
is the whole defect.

Read-only query of `local_runtime_turn_ingress` for `mvs_b7a9f3a7db404912b32d28fc11b83645`,
13:31 BRT: **POPULATION = 10 ingress rows, of which 2 are queue-linked** —
`turn_aeec7923…` at **12:43:50** (`queue_4d760084…`) and `turn_4bb0112f…` at **12:55:18**
(`queue_f6e768e9…`), both `status='completed'`. **WINDOW = 12:43:50 -> 12:55:18 BRT.** The
other **8** (`turn_muy8i3nv…`, 7 × `turn_task_delivery_*`) are genuinely unlinked — which is
what a real NULL looks like, and why the instrument was never the problem.

**What survives of this section, unchanged and still the point:** *a single row is not a
population.* It was true then in the direction receipt-23 got wrong — a marker match, or a
single NULL, cannot settle a mechanism. It is true now in the direction receipt-27 got wrong:
one resolved latency sample cannot settle a distribution, and §1's own table already held the
row that refuted §3. Over-claiming from a text match, over-generalising from a null, and
generalising from one sample are the same disease. The cure is the same in all three cases:
**state the population, state the window, and never promote a single row to a verdict without
running the instrument that could have said no.**

## 4. The instrument, and why it exists

`_main/delivery-latency.py` never greps for a marker. It walks the ingress table, keeps only
rows with a non-null `queue_item_ids_json`, resolves each named item, and prints
`UNRESOLVED` for a row it cannot resolve — never zero latency, never a silent drop.

Two bugs were fixed in building it, both caught by running it rather than reading it:
`no such column: i.created_at_ms` (the real column is `accepted_at_ms`, which is why this
receipt introspected the schema instead of assuming it), and an f-string with nested quotes
that Python 3.11 rejects.

## 5. What this receipt does NOT claim

- **N=1** for the resolved latency. 155/200 queue-linked turns exist; I resolved one.
- It does not claim a **cadence**: the owner's requirement is a wake *every 3 minutes* with
  the agent alive between fires. One delivery is not a cadence.
- It does not claim the 2 m 56 s applies to the exec path.
- It does not claim lanes persist. They do not — see the ledger entry of 12:56.