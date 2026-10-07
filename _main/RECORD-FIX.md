# RECORD-FIX — durable records that were measurably wrong

Lane: `lane/recordfix`
Worktree: `H:\sotto-wt\recordfix`
Base: `H:\sotto-wt\ArbV8` @ `main` (a296318)
Started: 2026-10-07 17:17 -03 (Horário Padrão de Brasília)

## What this lane is

Three durable records carried claims that were repeated across turn reports as if
established. Direct measurement contradicts all three. This lane corrects the claim
**where the claim lives** — not by appending a receipt and leaving the wrong text in
place.

## Rule being enforced

Every correction carries **the measurement that justifies it**, plus **POPULATION**
(all rows in the table, not a sample) and **WINDOW** (the time range observed).
A wrong claim is never replaced with a vague right one. Anything not independently
checked is marked **UNCHECKED**, not asserted in either direction. History is only
ever appended to, never deleted.

## Records targeted

1. `AGENTS.md` (worktree root) — claims about the cron never firing, or that
   `deliveryAttempts=0` / `claimId=None` mean "no delivery".
2. Root-level notes under `H:\sotto` — `AGENTS.md`, `README*`, `*MEMORY*`,
   `*CONTEXT*`, `_main\*.md` — the claim "there is no cron store in `.minimax\v2`".
3. Friction ledger `I:\!manager\state\friction\FRICTION-LEDGER.md`.

## Measurements as given by root (to be independently re-verified before use)

Source: `C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite`

| Table | POPULATION |
|---|---|
| `local_runtime_v2_cron_runs` | 1442 rows |
| `local_runtime_v2_scheduler_jobs` | 30 rows, 5 active |

- Recent `local_runtime_v2_cron_runs` rows: `status='delivered'`, `error=None`,
  delivery latency ≈ 159 ms.
- Cron `d43fb9be-283d-4dd3-8e73-d9fb562fd181`, scheduler
  `3e640109-0683-4f55-9bd3-27bbb323bc6f`: `run_count=444`, `state='active'`,
  `schedule_generation=3`, expression `*/3 * * * *`, `project='I:\!manager'`,
  `prompt_bytes=8553`. Last delivered `1791291600699` = 2026-10-06 ~10:00 local.
- 5 of 30 scheduler rows are `active`; **3 of those 5 have `next_run_at_ms` in the
  past and are not firing.** That — not "never fires" — is the real defect.
- On-disk `I:\!manager\scripts\cron-mission-prompt.md` = **8612 bytes** vs
  `prompt_bytes=8553` in the DB. 59-byte divergence, **UNEXPLAINED**.

## Status

Steps 1-4 (TMPDIR, worktree, this receipt, first commit) done. Corrections in progress.