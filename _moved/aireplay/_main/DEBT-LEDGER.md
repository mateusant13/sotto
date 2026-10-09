# DEBT LEDGER — every item I declared "not done", and what closed it

**Why this file exists.** Three times the P0 ratchet re-raised items I had already closed,
because it compares my prose, not the repository. A promise kept only in a chat turn is a
promise with no state. This is the state.

Rules for this ledger, which are the rules that were missing:

1. An item may only be marked `CLOSED` with a **file, a commit, or a measurement** attached.
   "Decided not to" is not a closure; it is a closure with a receipt.
2. An item may only be marked `VOID` with a **measurement that removed its precondition**.
3. Anything else stays `OPEN`, and an OPEN item past its second report is `ESCALATED`.
4. Every lane that lands MUST have a reviewer row here before it counts as done.

---

## Closed

| id | item | resolution | proof |
|---|---|---|---|
| D-RESTART | "Não reiniciei a sessão" — the owner's restart path, deferred | **VOID** — the restart was conditional on the wake being broken. It was not broken: the wake loop resumed the conversation at 12:16:14, 12:22:17, 12:31:23 and 12:39:19, POP=4 events, WINDOW 12:15→12:39. Restarting would destroy a working mechanism and this conversation to fix nothing. The owner's *procedure* is preserved anyway for a future wake that needs it. | `_main/RESTART-RUNBOOK.md`, commit `4ce26c7`; "deliver a wake to an IDLE session within 3 min" is OPEN below as the real requirement |
| D-QUEUE-PROOF | "Não observei a entrega da fila" | **CLOSED, and now the conclusion is right too.** Delivery exists — narrow census `queue_item_ids_json IS NOT NULL AND claim_source='api'`: **POP=80**, **80/80** carry a `role='user'` row, **0 counter-examples**, WINDOW 13:27:32->13:28:38 BRT (broad census `queue_item_ids_json IS NOT NULL`: 583 -> 585 -> 608 -> **618**, WINDOW 13:27:32->13:38:10 — the count MOVES, the ratio does not). **The retraction filed here was itself false and is retired:** the 12:40:54 turn is a **proven queue delivery**, POPULATION=2 resolved turns, WINDOW 12:40:54->12:55:18 BRT. | `receipts/receipt-23-cron-woke-this-session.md` §1/§2/§6; read-only query of `runtime-state.sqlite` 13:27 BRT: `queue_item_ids_json=["queue_4d760084-bc97-4edf-bef4-6dd6399a2556"]`, `claim_source='api'`, `status='completed'` |
| D-REMEASURE | "Não re-mediquei nada neste turno" | **CLOSED** — re-measured at 12:45:46 with populations stated, and again at 12:51:19 verifying the retraction commit and runbook exist on disk rather than asserting it. | two census runs, WINDOW 12:45:46 and 12:51:19 |
| D-L3-REVIEW | "Não despachei reviewer para a L3" | **CLOSED** — verifier dispatched as `bg_1d034503`. | task list at dispatch time |
| D-HEADLINE | my claim that the cron woke this session | **RETRACTED — and the retraction's stated evidence is RETIRED as false.** The text match never proved a mechanism. L16's counter-claim (`queue_item_ids_json = NULL`) is **false**: that turn names its queue item, `claim_source='api'`. **What survives:** the turn was a **queue delivery** (POP=2, WINDOW 12:40:54->12:55:18 BRT). **What does not:** that the *cron* planted it — `queue_4d760084` was hand-injected (`receipt-27` §2), and every `WAKE delivered rc=0` names the owner's session `mvs_a00662…` (POP=9, WINDOW 12:56:30->13:30:10), never this one. **Headline stays retracted; the reason it was retracted was wrong.** | `receipts/receipt-23-cron-woke-this-session.md` §1/§6, `_main/heartbeat.log`, `receipts/receipt-27-queue-delivery-latency.md` §2 |

## Open — and these are the real work

| id | item | owner | status |
|---|---|---|---|
| **D-IDLE-WAKE** | **A wake must reach an IDLE session within 3 minutes. This is the owner's actual requirement and it is NOT MEASURED.** The owner's turn held the window 12:00:13→12:47:24. | needs a window with no turn in it | OPEN |
| D-D1 | Minted `userMessageId` is 48 chars; the 20 most recent runtime rows are 55. Shape proven wrong, causal role NOT proven. L16 rates it MEDIUM. | fix lane | OPEN |
| D-D5 | PRUNE is session-scoped, so an orphan row in a session with no attached runtime is permanent by construction. POP=4 rows, 0 with `expires_at_ms`; orphan aged 959.3→974.2 min over 5 samples. | orchestrator decision: prune session-wide, or set `expires_at_ms` on insert | OPEN |
| D-D6 | `Runtime shutdown deadline exceeded after 60000ms` on every exec against a live session. POP=1 occurrence; a rate needs ≥20 passes ≈ 60 min of wall clock. | needs a long window | OPEN |
| D-D4 | No alarm when `now - max(cron_runs.created_at_ms) > 15 min` while an active cron definition exists. The runtime cron is dead 26.5 h (POP=1,442 run rows, newest 2026-10-06 10:11:00, corroborated by 1,383 `source='cron'` user rows with the same newest instant). | fix lane | OPEN |

## Lane → reviewer index

A lane with no reviewer row here is **not done**, no matter how good its receipt is.

| lane | owns | reviewer dispatched | reviewer verdict read |
|---|---|---|---|
| L1 trigger | `src/capture/trigger.*` | `bg_3b0a0b54` | **read** — verdict `NO`, 13:01:05 |
| L2 audio | `src/capture/wasapi_audio.*` | — | — |
| L3 ringcap | `src/capture/ring_buffer.*` | `bg_1d034503` | **read** — verdict `NO`, 13:07:09 |
| L4 index | `src/index/**` | `bg_86b2306c` | **read** — verdict `NO`, 13:10:15 |
| L5 research | `research/*` | — (landed 12:51) | — |
| L6 spec04 | `specs/04-*` | — (still running) | — |
| L7 window | `src/capture/replay.*`, `test_window.*` | — (still running) | — |
| L8 integration | `docs/integration-*`, `overlay-hotkey-contract.md` | `bg_5cc75264` | **read** — verdict `NO`, 12:50:04 |
| L9 asr | `src/asr/**` | — (still running) | — |
| L10 battery | `run_battery.ps1`, probes | — (still running) | — |
| L11 all-gates | `_main/all-gates.ps1` | — (still running) | — |
| L12 durability | `_main/durability-gate.ps1` | — (landed 12:49) | — |
| L13 hud | `specs/05-*` | — (landed 12:50) | — |
| L14 broadcast | `specs/06-*` | — (still running) | — |
| L15 highlights | `specs/07-*` | `bg_feb2d120` | **read** — verdict `NO`, 12:51:16 (verdict read; the TARGET is gone: `specs/07-highlights.md` deleted, `specs/07-engine-process.md` is a 936 B stub) |
| L16 wake audit | receipt-21, `_lane16-wake-gate.ps1` | `bg_57f798ae` | **read** — verdict `NO`, 13:10:20. **This is the verdict that filed the false retraction; its stated evidence is refuted in `receipts/receipt-23-cron-woke-this-session.md` §1** |

**Count: 6 of the 6 lanes that ever got a reviewer dispatched have that verdict READ — all
six say `NO`.** Re-measured 13:30:36 BRT against the live store, POPULATION = the **11** verifier
seats under `mvs_b7a9f3a7db404912b32d28fc11b83645`: **8 carry a final verdict line, 3 are still
in flight** (started 13:27:57-13:28:54), and of the 8, **6 are the product-lane reviewers named
in the table above** (L1, L3, L4, L8, L15, L16) while 2 are synthesis seats, not product
lanes. **Denominator, stated because the old line was wrong twice: this table names 16 lanes,
only 6 of which ever had a reviewer dispatched, and "0 of 16" counted 10 lanes that had no
reviewer at all as if they had an unread verdict.**

The "0 of 16" line above was written before the wave landed and was never re-run. **It was
false the moment receipt-28 closed**, which read all six (`verdicts read = 6`, reproducible via
`_main/review-synthesis.ps1`; that script now **crashes** on a `None` `msg_content` —
`review-synthesis.ps1` embeds a `content()` that returns `None`, and one of the 3 in-flight
seats hits it. The number above was obtained by running the same query with that defect
repaired, without editing the script. **Fix that script before citing it again.**)

**What is still unfinished is not "reading verdicts" — it is that 6 of 6 verdicts are `NO`, and
10 of 16 lanes have no reviewer dispatched at all.**

## The bug this file was written to prevent

Twice today I reported a lane as delivered on the strength of its own report. Once L8
correctly refused to claim its review was done, because its seat had no dispatcher — and it
was right to refuse. An unreviewed lane reported as reviewed is the exact shape of the bugs
this project keeps finding: a gate that passes because nobody checked whether it can fail.
---

## MEASURED 12:56 — SUBAGENTS DO NOT SURVIVE THE TURN THAT DISPATCHED THEM

The agent woken into session `mvs_a00662…` reported, unprompted:

> "A frota anterior **foi morta entre turnos** — encontrei **0** vivas quando cheguei.
> Cinco `canceled`. Não foi uma falha de planeamento: **é o comportamento do runtime**."

POPULATION = **10** lanes that agent had dispatched at 12:21 (POP=5 observed `canceled`),
WINDOW = dispatched 12:21 → found dead on arrival 12:56.

**What this invalidates.** `ORCHESTRATOR-PROMPT.md` §1 says: *"Your own per-session
concurrency cap is finite and you have already measured it is at least 16. To exceed it,
lanes delegate: a worker may dispatch its own children. Growth happens by delegation."*

That is **false on this runtime** as measured. A lane does not outlive the turn that created
it, so a fleet cannot be built up across turns — it can only exist WITHIN one turn. The
owner's "15 to 50 running" is therefore a per-turn ceiling here, not a standing population,
unless this is disproved.

**What it does NOT invalidate.** The wake loop still works across turns — it resumed this
conversation at 12:16:14, 12:22:17, 12:31:23, 12:39:19 and again now. The fleet is the
thing that does not persist; the WAKE does.

## The delivery that proved it

```
[12:53:22] WAKE sending -> mvs_a00662bff55242cb9b56c0f1165bdad7 chars=3954
[12:56:30] WAKE delivered rc=0 -> mvs_a00662bff55242cb9b56c0f1165bdad7
           :: "## Frota viva: 14 subagents — POPULAÇÃO 14, JANELA 12:5x (medido agora)"
```

POPULATION = **1** fire into a session measured `status=idle` (workspace
`C:\Users\Administrador`, read 12:58:09). WINDOW = sent 12:53:22 → rc=0 at 12:56:30.

Two things to keep honest about:
- **3 m 08 s is the `mcode exec` process duration**, which includes a whole agent turn. It
  is NOT delivery latency. The delivery latency is NOT MEASURED — `turn_ingress` was not
  read for this turn. Do not quote 3 m 08 s as "the wake arrives in 3 minutes".
- The receiving agent's report is its own; I have not independently verified its claim of
  "14 subagents" with my own `task_query` for ITS session.
