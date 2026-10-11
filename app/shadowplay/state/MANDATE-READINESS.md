# Can the mandate's "15 to 50 subagents RUNNING" be measured in this runtime?

Answer measured, not argued. WINDOW_UTC 2026-10-11T09:58:41Z, store read mode=ro,
POPULATION = every row in local_runtime_sessions.

## The status vocabulary, complete

| status | rows |
|---|---|
| idle | 3747 |
| aborted | 1121 |
| error | 681 |
| interrupted | 357 |
| started | 1 |
| TOTAL_ROWS | 5907 |

Five values. There is no "running", no "queued", and no "succeeded". The mandate's own note --
"'succeeded' is not 'running'" -- is satisfied trivially, because there is no succeeded
either. What I have been printing as "0 running" for several reports is the count of
"started", which is 1 globally and 0 under my parent_session_id.

## The nearest thing the store CAN express

Recency of updated_at_ms, as a liveness proxy rather than a status:

| window | global | mine |
|---|---|---|
| last 5 min | 1 | 0 |
| last 15 min | 1 | 0 |
| last 60 min | 1 | 0 |
| last 360 min | 1 | 0 |

MAX_UPDATED_AT_MS = 2026-10-11T09:58:28Z, which is this session. So the recency proxy does
work: it names exactly one live thing, and the one live thing is me. The answer to "how many
subagents are running" is 0 under every reading available here.

## Other columns, for completeness

session_type: branch 5903, root 4. session_kind: task 3612, conversation 2160, cron 135.
visibility: visible 5907. archived: 5897 no, 10 yes. runtime: pi-agent 5907.
purpose_kind: EMPTY for all 5907 rows -- the column exists and holds nothing, so any rule
keyed on purpose_kind would match nothing here.

## What the mandate would have to ask for to be checkable

1. A status that means live. "started" is the closest and there is exactly one of it.
2. Or a liveness convention: a session is running if updated_at_ms is within N minutes. That
   is measurable today and I have measured it.
3. Or a runtime-side answer: the count of subagent sessions whose process is alive, which the
   store cannot express and I cannot read from here.

Until one of those exists, "15 to 50 running" has no measurement behind it, and any report
that quotes a running number without saying which of these three it used is quoting a free
parameter.
