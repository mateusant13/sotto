# heartbeat-truth — is the 3-minute heartbeat actually delivering?

Measured 2026-10-07 13:43–13:44 BRT. Read-only. Nothing in the heartbeat was changed.
Owner session under test: `mvs_a00662bff55242cb9b56c0f1165bdad7`.
Runtime DB: `C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite` (opened `mode=ro`).

## STEP 1 — queue table

Table name (from `sqlite_master WHERE name LIKE '%queue%'`): the real one is
`local_runtime_queue_items`. Siblings are `local_runtime_queues`,
`local_runtime_queue_row_migrations`, `local_runtime_turn_diff_retention_queue`,
`local_runtime_queue_migration_quarantine`, `local_runtime_queue_pauses`.

| Measure asked for | Real value | Notes |
|---|---|---|
| total rows | **0** | `local_runtime_queue_items` is empty |
| rows with `claimId` NOT NULL | **0** | column is `claim_id` (snake_case), not `claimId` |
| rows with `deliveryAttempts` > 0 | **N/A — column does not exist** | no `delivery_attempts` anywhere in the schema; not invented |
| `MIN(created_at)` | **NULL** | column is `created_at_ms` (INTEGER epoch ms), not `created_at`; no rows, so no min |
| `MAX(created_at)` | **NULL** | same column-name correction; no rows, so no max |
| rows in last 30 minutes | **0** | |
| rows for the owner session | **0** | |
| rows with `claim_lease_expires_at_ms` set | **0** | only delivery-side column that does exist |
| `local_runtime_queues` with non-empty `items_json` | **0** | |
| (extra) last-30-min turns in `local_runtime_turn_ingress` | **7** | 13:16, 13:22, 13:25, 13:28, 13:31, 13:34, 13:40 |
| (extra) last-30-min `user` rows in `local_runtime_message_rows` | **7** | all `source=api`, all exactly 4598 bytes |

**`claimId=None` / `deliveryAttempts=0` is therefore STILL UNPROVEN by itself** — but not
because delivery fails. Those columns are on a table the heartbeat does not use.

## STEP 2 — machinery

| Item | State |
|---|---|
| `H:\sotto\_moved\aireplay\_main\heartbeat.ps1` | exists, 28107 bytes, LastWriteTime **2026-10-07T13:43:19.82-03:00** |
| `H:\sotto\_moved\aireplay\_main\wake.py` | exists, 4157 bytes, LastWriteTime **2026-10-07T11:51:45.58-03:00** |
| heartbeat process running | **YES** — PID 13636 `pwsh.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "…\heartbeat.ps1" -ChildExec -ChildWorkspace "C:\Users\Administrador"` |
| `heartbeat.log` | last write 13:43:02; 166 lines; 5 `TASK-FIRE`; 11 `WAKE delivered rc=0`; 2 `WAKE QUEUE FAILED` |
| `wake-counters.json` | `{"passes":9,"shutdown_deadline":0,"first_pass_utc":"2026-10-07T16:06:39Z"}` |

## STEP 3 — verdict

**IS THE HEARTBEAT DELIVERING: YES.**

Deciding evidence, taken from the runtime's own records and *not* from the heartbeat's
self-report: in the last 30 minutes the owner session accepted **7 turns** on a ~3-minute
cadence (13:16, 13:22, 13:25, 13:28, 13:31, 13:34, 13:40), and each one wrote a `user`
message row with `source=api` whose payload is byte-identical at 4598 bytes and opens with
`# ORCHESTRATOR MANDATE — the payload the cron delivers`. A heartbeat that were not
delivering could not produce that cadence or that payload.

The recorded limit ("`claimId=None`, `deliveryAttempts=0`, so the queue is not consumed")
was a **false negative from measuring the wrong transport**. The queue table is empty
because the heartbeat's primary transport is `mcode exec --session <id>`, which starts a
turn directly and never writes a queue row. The queue is only a *fallback*, used when a
turn is already open; in this window that fallback tried twice and both times logged
`WAKE QUEUE FAILED rc=1 reason=exec-child-inflight :: NO TEMPLATE ANYWHERE` — so on a busy
session those two ticks were **not** delivered. That is a real gap, and it is the only
delivery failure visible.

### What is still unproven

- The `claimId` / `deliveryAttempts` test can **never** prove delivery on this design,
  because the delivered path writes no queue row. Stop using it as the health signal.
- Not measured: whether the *content* of the delivered wake is acted on (a turn being
  accepted is not the same as the owner replying to it).
- Not measured: the 2 fallback failures are drops, not deferrals — they lose ticks.

### The single measurement that would settle the queue question

Send **one** wake through the queue transport on purpose (owner session busy), then read
`SELECT claim_id, status, queue_acknowledged_at_ms FROM local_runtime_turn_ingress WHERE
session_id='mvs_a00662bff55242cb9b56c0f1165bdad7' ORDER BY accepted_at_ms DESC` and
confirm the new row carries a non-NULL `claim_id` and a non-NULL
`queue_acknowledged_at_ms`. That is the only row the queue path can produce.