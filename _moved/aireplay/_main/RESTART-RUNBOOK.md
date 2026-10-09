# RESTART RUNBOOK — for a future wake that genuinely needs it

**This closes a deferred promise.** Earlier I wrote *"I did not restart the session — the
loop already wakes me four times in twenty minutes."* That was a deferral, and a
deferral without a procedure is a debt. Here is the procedure.

## Why this is not being executed right now

The owner's instruction was conditional: *"se tu disser que temos que reiniciar a sessão
pra fazer efeito, você vai simplesmente primeiro chamar sua própria sessão e dar continue
nela, pelo mcode. depois que tiver dois de você, você termina seu próprio processo."*

**DO NOT RESTART.** Re-measured 2026-10-07 at 13:27-13:33 BRT. The condition above —
*"the wake mechanism does not work"* — is **false**, and this decision deliberately does
**not** rest on the evidence this file used to cite. That evidence is withdrawn: it was a
`role='user'` row, a queue table read as empty, and a sentence naming the cron. Two of those
three do not prove what they were used to prove, and the third names the wrong mechanism.
Below are the four facts that actually carry the decision, each with its POPULATION and
WINDOW, because this is the file acted on at the next restart.

**(a) The cron does not target THIS session — measured.** Every `WAKE delivered rc=0` line in
`_main/heartbeat.log` names `mvs_a00662bff55242cb9b56c0f1165bdad7` (the owner's session,
workspace `C:\Users\Administrador`). **POPULATION = 9 deliveries, WINDOW 12:56:30 -> 13:30:10
BRT, every one `rc=0`; zero name `mvs_b7a9f3a7db404912b32d28fc11b83645`.** That is by design,
not a defect — but it means a cron `rc=0` is **not** evidence about this session, and this
file must never cite one again.

**(b) CHK-W1 for THIS session is AMBER, not green — measured.** `role='user'` rows in
`local_runtime_message_rows` for `mvs_b7a9f3a7…` since 12:40 BRT: **POPULATION = 2**
(12:40:54 `msg-user-v1-wake14c1ccd…`, 12:49:03 `msg-user-v1-wake81e67e02…`) out of **132**
session rows over the same window, so the low count is real and not a query artefact.
**WINDOW = 12:40:00 -> 13:32:31 BRT; nothing since 12:49:03, i.e. 43.5 min stale at read.**
And (a) is why those two are not CHK-W1 passes here: no `WAKE delivered` line names this
session, so the log-line half of CHK-W1 is unmet regardless of the rows.

**(c) What IS resuming this session is task/subagent completion, not the cron — measured.**
`turn_task_delivery_*` ingress rows for this session were accepted at 13:00:23, 13:03:47,
13:12:54, 13:20:27, 13:24:37 and 13:29:59 (**POPULATION = 6, WINDOW 13:00:23 -> 13:29:59**),
and `evt_turn_task_delivery_*` message rows follow them (e.g. 13:29:52). Each completes an
existing conversation. **CHK-W4 — `wake-loop.py` exits and a conversation resume follows — is
therefore GREEN on live evidence, repeatedly, minutes apart.**

**(d) The trigger is not met. Do not restart.** The gate below requires BOTH CHK-W1 and CHK-W4
red over several cycles. (b) is amber and (c) is green. **The conclusion survives the
refutation — on grounds that have nothing to do with the withdrawn claim** — but the subject
it was stated about was wrong: the wake is working *for the owner's session*, and *this*
session is being resumed by a different mechanism.

### What the 12:40:54 wake actually proves — corrected, because the file previously denied it

It **was** a real queue delivery. `turn_aeec7923-878b-4025-88ca-f34ed6f4f59e` carries
`queue_item_ids_json = ["queue_4d760084-bc97-4edf-bef4-6dd6399a2556"]`, `claim_source='api'`,
`client_request_id='queue-delivery:claim_4d856235-b931-4100-b02f-3a34fd027cf5'`,
`status='completed'`, and `queue_acknowledged_at_ms = 12:43:50 BRT`. **POPULATION = 2
queue-linked wake turns in this session, WINDOW 12:40:54 -> 12:55:18 BRT** (the second,
`turn_4bb0112f`, `queue_f6e768e9…`, accepted 12:55:18; read 13:27 BRT).

**Consumption is proved by that acknowledgement timestamp, not by the queue table being
empty.** `local_runtime_queue_items` is empty in its *entirety* right now — **POPULATION = 0
rows, read 13:33 BRT** — because `wake-fix.py PRUNE --all-sessions` runs on every pass. An
empty queue is therefore consistent with a prune and with consumption, and the earlier
sentence in this file ("the queue was empty on the following read — the row was consumed, not
merely written") **was an unsound inference. It is withdrawn, not softened.** What replaces
it: `queue_acknowledged_at_ms IS NOT NULL` on **608 of 608** queue-linked turns
(WINDOW 13:33 BRT) — the runtime acknowledges only items it took, which is an artefact the
prune cannot manufacture.

**Not claimed here:** that the *cron* planted `queue_4d760084`. See
`receipts/receipt-27-queue-delivery-latency.md` §2 — that item was planted by a hand
`inject`. **"Proven queue delivery" is what the store supports. "The cron delivered it" is
not, and this file no longer implies otherwise.**

Performing a restart now would destroy a working mechanism and this conversation to fix
nothing. That is the definition of an unnecessary destructive action.

## WHEN to run it

Run this only if a measurement says the wake is dead. The gate is `CHK-W4`
(`_main/wake-loop.py` exits and a conversation resume follows, over N consecutive arms) and
`CHK-W1` (a `WAKE delivered`/`queued` log line followed by a new `role='user'` row).
Both red, over several cycles, not one.

**One red observation is not enough.** The owner is away; a restart costs this
conversation. The trigger is a PATTERN, not an event.

## HOW, exactly

The owner's order matters: create the successor FIRST, verify TWO exist, and only then
terminate the predecessor. Killing yourself first leaves nobody to verify anything.

```powershell
$SID = 'mvs_b7a9f3a7db404912b32d28fc11b83645'   # this session
$WS  = 'H:\sotto'                              # this session's workspace_dir

# 0. NEVER hardcode $WS. Read it. (mcode exec refuses with
#    "Session workspace does not match --cwd" when it is wrong.)
$WS = (py -3 H:\sotto\_moved\aireplay\_main\wake-fix.py `
        session-workspace --session $SID | Select-Object -Last 1)

# 1. Call MY OWN session with a continuation prompt. Same session id.
$m = Get-Content H:\sotto\_moved\aireplay\_main\ORCHESTRATOR-PROMPT.md -Raw -Encoding UTF8
Start-Process mcode -ArgumentList @(
  'exec', '--session', $SID, '--cwd', $WS, '--permission', 'off',
  '--timeout', '12m', $m
) -WindowStyle Hidden

# 2. Verify TWO of me exist BEFORE killing either.
#    A new turn in $SID is the proof the call was accepted.
py -3 H:\sotto\_moved\aireplay\_main\check-delivery.py $SID <last_user_msg_id> `
   'ORCHESTRATOR MANDATE'
#    A hit in role='user' means the successor took the prompt. No hit -> STOP,
#    do not terminate anything.

# 3. Only then terminate THIS process. Identify it by PID, never by a name
#    substring: a bare 'sotto' filter once killed two unrelated processes.
```

## What must be true before step 3

- step 2 shows a `role='user'` hit whose `created_at_ms` is AFTER the step-1 call;
- the fleet is dispatched and its task ids are recorded somewhere durable
  (`ORCHESTRATOR-STATE.md`), so the successor does not orphan running lanes;
- the wake watcher is NOT armed in the dying process only — the successor must arm its own.

## What this runbook does NOT claim

- It has **never been executed**. It is a procedure derived from the owner's words plus the
  measured `mcode exec --session` contract. Treat it as untested until someone runs it.
- Step 1 against a LIVE TUI session is the case measured to return
  `Session already has an active Turn` (rc=4). The queue path is the one proven to work
  there. If step 1 refuses, use `wake-fix.py inject` instead, which is what the driver now
  does for a `started` session.
- It does not assume the successor is smarter than the predecessor. It has the same state
  files and the same open work orders.