# Receipt 22 — a single cron CAN send a message into a session, like the owner types

**The owner's question, verbatim:** *"testa um cronjob unico, ve se ele te manda
mensagem como eu mando."*

**Answer: YES, proven at the database level. 2026-10-07, session
`mvs_a00662bff55242cb9b56c0f1165bdad7`.**

---

## 1. The proof, and why it is proof

A row appeared in `local_runtime_message_rows` with **`role='user'`** carrying the
orchestrator mandate:

```
HIT id=225419  12:21:19  src=api
```

`role='user'` is the load-bearing part. A plain text search over the same table ALSO
matches **assistant** rows — this very receipt, and every report that quoted the mandate.
That trap has already fired twice on this project:

- a count of "95 HEARTBEAT messages" that was this agent's own report text;
- a watcher that printed `DELIVERY-A CONFIRMED` off an `role='assistant'` row.

An instrument that matches its own output proves nothing and reports green. Every
delivery claim here is therefore gated on `role='user'`.

**POPULATION** = all `role='user'` rows of that session (the scan is unbounded, not
sampled). **WINDOW** = the session's whole lifetime at read time, 12:23 local.

Then the receiving agent did the only thing that can distinguish delivery from an echo:
it **acted**. It reported a live fleet count, dispatched **10 subagents of its own** on
disjoint files, and closed with the mandated `Does your implementation meet the spec?`
line. `mcode exec` returned **rc=0 in 138 s**.

## 2. The three refusals on the way — they are the useful part

Two earlier attempts were refused. Neither was noise; each named a real precondition.

| attempt | rc | runtime's words | cause | fix |
|---|---|---|---|---|
| 1 | 4 | `Session workspace does not match --cwd` | `--cwd` must equal the session's own `workspace_dir`. Two sessions on this box differ: `H:\sotto` and `C:\Users\Administrador`. | read `workspace_dir` from `local_runtime_sessions`; `wake-fix.py session-workspace` |
| 2 | 4 | `An earlier queued message has priority` | a row sitting `queued` in an **idle** session is not pending work, it is a **permanent head-of-line block** — nothing drains a session with no process attached | `wake-fix.py prune --stale-mins N`, which backs up before deleting |
| 3 | **0** | — | — | — |

Attempt 2 is the dangerous one and it would have bitten forever: a single stale row makes
every later send fail with a message that looks like "busy" rather than "broken".

## 3. What does NOT work, measured

**Writing a queue row directly does not wake a live session.** A row inserted for
`mvs_b7a9f3a7db404912b32d28fc11b83645` at 12:14:55 sat `status='queued'`,
`claim_id=NULL` for 6+ minutes and produced **0** new `role='user'` rows.

The runtime *validates* that table — it answered with `Queue row is corrupt: <session>/<item>`
naming our own item — but it does not *consume* it for a session that has a turn in
flight. Two earlier conclusions in this repo were wrong because they inferred instead of
measuring:

- "there is no consumer, therefore injection cannot work" — wrong; it validates;
- "the row shape was fine" — wrong; it lacked `requestedTurnId` and `routing_fingerprint`.

Both were true-ish and both were useless. The **transport** was wrong, not the shape.

## 4. The two independent doors, both proven

| door | proof | note |
|---|---|---|
| `mcode exec --session <id>` | rc=0, 138 s, `role='user'` id=225419 | the cron's job. No-ops correctly when the target is already awake. |
| `wake-loop.py` watcher | armed 12:15:14 → exited 12:16:14 → **this conversation resumed**; re-armed 12:21:17 → exited 12:22:17 → resumed again | the floor. Independent of the cron. A background task exiting resumes the owning conversation. |
| subagent completion | 16 lanes running; a finishing lane resumes the conversation | the third door. |

**Dead, measured:** the runtime's own cron scheduler. `local_runtime_v2_cron_runs` newest
row is 2026-10-06 10:11, and a probe cron armed for 12:07:51 produced **0 runs**, despite
`state='active'` and `run_count=444` on its scheduler row. It does not run in this
process. The Windows Scheduled Task does (12:04:01, 12:07:02, 12:10:03, 12:13:03,
12:14:33, 12:16:0x, 12:19:00 — rc=0).

## 5. Rollback

```powershell
Stop-ScheduledTask -TaskName SottoReplayHeartbeat        # stop the cron
Disable-ScheduledTask -TaskName SottoReplayHeartbeat
git -C H:\sotto\_moved\aireplay revert <sha>             # driver v5 -> v4
# every pruned row has a backup: _main\backup-*-prune-*.json
```

## 6. What this receipt does NOT claim

- It does not claim the cron fired **on a schedule** yet. The 3-minute task has fired
  repeatedly; the `mcode exec` payload has been proven **once**, by hand. An automated
  fire delivering is the next measurement, not this one.
- It does not claim the runtime's scheduler is fixable from the store. Measured as dead;
  cause not attributed.
- It does not claim delivery to a session with a **live turn**. That case is a correct
  no-op (rc=4, "Session already has an active Turn") and is untested against this build.