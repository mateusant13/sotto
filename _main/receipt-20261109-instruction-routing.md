# Receipt — instruction routing: Herdr default removed from Sotto

Date: 2026-11-09
Scope: `H:/sotto/AGENTS.md` (project-local instruction surface) + this receipt.
Owner item: `TODO-omp-handoff-20261109.md:40` ("Resolve the instruction/routing correction").
**STATE: DARK** — the correction is written and is the project instruction surface the harness loads, but I did not exercise a fresh session honouring it. No Herdr was used for this work; no app, window, or battery was launched.

## Contract (source of each checkbox)

- Owner handoff item 1 — source: `H:/sotto/TODO-omp-handoff-20261109.md:40`.
- Stay in current harness; Herdr only for genuine cross-project coordination — source: the brief and the handoff's operating constraints.
- Preserve dirty files; no app launch; no visible window; no Herdr for this handoff — source: the brief house rules.
- `## SELF-AUDIT` and `## CACHE/PRICE` — source: the task's standard-instruction blocks.

## 1. The exact instructions that caused the default

### 1.1 Direct cause, project-local (fixed here)

`H:/sotto/AGENTS.md:50-51`, before the edit:

```
## Herdr panes (mandatory)
Cap: one visible pane per canonical project across workspaces/worktrees. Create via `python I:/!manager/tools/herdr-visible-pane-budget.py workspace --cwd <root> --label <id>` only; unknown/already-present projects refuse. Reuse main pane; extra workers headless; no raw create/focus/move/close.
```

The heading says **mandatory** and the body says **Create via … only**, so an agent reading the project instructions treats Herdr as the default pane path. It entered in commit `9e8b628` (2026-10-30 02:11:02 -0300, subject `bend: the caption laws, their proofs, their controls and the oracles that bind them`) — added as a side effect of a bend/caption commit, not by an owner request.

### 1.2 The rule it was copied from (manager-owned; residual)

`I:/!manager/AGENTS.md:40`:

```
## RULE: Herdr — each session read state/herdr-inbox; start/verify lane-watch via Watcher (cwd I:\!watcher); inspect non-Sotto tails/process/goals, resume stalls; Sotto receipts only.
```

`I:/!manager/AGENTS.md:104-106`:

```
## RULE: Herdr panes are capped per project (P1)
oracle: `python tools/herdr-visible-pane-budget.py selftest`
Before creating any Herdr pane/workspace, use this helper; source checks reject raw creation commands. Hard cap: **one pane per canonical project across all workspaces/worktrees**. Git identity plus `state/herdr/project-map.json` aliases; unknown identity refuses. The helper locks admission, forces `--no-focus`, logs creation, and never auto-closes. Use the existing main pane or headless workers.
```

`H:/sotto/AGENTS.md:51` was a compression of this rule.

`I:/!manager/docs/protocols/project-harness-routing.md:3-5`:

```
This is the routing source of truth for the Herdr project map. Check the project root before opening or resuming an agent; use the existing pane and project session where possible.
```

### 1.3 The instruction that makes "update AGENTS.md routing" a default side effect

`C:/Users/Administrador/.agents/skills/prepare-project/SKILL.md:21`:

```
**Routing gate (mandatory readiness row).** `task-resolver` is the entry point for every non-trivial task, and a project's `AGENTS.md` is where that has to be written down: check `grep -n "task-resolver" AGENTS.md`. No hit is a readiness DEFECT, not a suggestion — add the block from [the routing line](../task-resolver/references/project-agents-routing-line.md), keep the project's own constraints around it, and report the before/after hit.
```

`C:/Users/Administrador/.agents/skills/prepare-project/SKILL.md:23`:

```
**Storage-census gate (mandatory readiness row).** A project's `AGENTS.md` MUST name the command that measures the bytes the project has generated ACROSS ALL DISKS ... no hit is a readiness DEFECT. Add the pointer to `python I:/!watcher/tools/artifact-census.py --project <root> [--budget-gib N] [--gate]` ...
```

`C:/Users/Administrador/.agents/skills/fast-land-shared-artifacts/SKILL.md:25` and `:39-42` repeat the same "AGENTS.md MUST name the command; a missing line is a DEFECT" rule. These lines make a readiness pass edit `AGENTS.md` routing as ordinary work; they mandate the task-resolver/census lines, **not** the Herdr line — the Herdr text came from 1.2.

### 1.4 Shared-skill / persona lines that keep Herdr as the delivery path (residual, not edited)

`C:/Users/Administrador/.agents/skills/handoff/SKILL.md:22-25`:

```
Merged 2026-10-27 from `claude-handoff`, whose only extra content was "seed a fresh background agent with the
summary". Here that agent is a **Herdr lane**, so the delivery path is `python tools/lane-dispatch.py` against
an existing, already-open pane — never a `claude --bg`-style CLI spawn, which creates a session no pane shows
and no watcher governs.
```

`C:/Users/Administrador/.agents/skills/_packs/agents/agent-bus/SKILL.md:40-43`:

```
| `pi` | the **manager** lane only (`I:\!manager`) |
| `pi:vodrip` | the lane whose `state/herdr/lanes.json` label is `vodrip` |
| `pi:*` | every pi lane (deliberate broadcast) |
| `opencode` / `codex` / `sotto` / `watcher` | that party (unchanged) |
```

`C:/Users/Administrador/.agents/skills/_packs/performance/popup-offenders/SKILL.md:61`:

```
3. `cwd` → pane: match against `herdr pane list` (`cwd` of each pane). That names
   the lane, and the lane is who fixes it.
```

`C:/Users/Administrador/.omp/agent/agents/herdr-lane.md:66-67`:

```
console: `windowsHide: true` / `CREATE_NO_WINDOW` on every child. One pane per project, and you
close nothing you did not open.
```

`C:/Users/Administrador/.omp/agent/agents/herdr-orchestrator.md:74-75`:

```
`DETACHED_PROCESS`, no `shell: "cmd.exe"`, no visible console. The only visible terminal is a
herdr pane the owner asked for, and panes are capped one per canonical project.
```

`C:/Users/Administrador/.omp/agent/hooks/pre/pressure-guard.ts:11-14` (comment only; the hook injects a pressure brief, not a Herdr DM):

```
 * A herdr DM is a message to a LANE: it waits for that lane to be idle. This hook
 * is a message to the AGENT, and it arrives through `additionalContext`, which the
 * runtime delivers with developer priority BEFORE the next provider request — so it
 * lands while the agent is working, in the same turn.
```

### 1.5 Inspected and NOT causal

- `C:/Users/Administrador/.agents/skills/skills-updater/SKILL.md:14-16,28` — it says "amend only authorized local surfaces" and "Prefer deleting or narrowing a harmful requirement over adding another universal rule." No Herdr line; it did not cause the default.
- `C:/Users/Administrador/.agents/skills/herdr-coordination/SKILL.md` — **does not exist** at that path, nor under `C:/Users/Administrador/.agents/skills/**`, `C:/Users/Administrador/.omp/agent/skills/**`, `I:/!manager/.agents/skills/**`, `H:/sotto/.opencode/skills/**` (no such dir) or `H:/sotto/.agents/skills/**` (only agent-browser, fast-land-shared-artifacts, task-resolver). The session skill list names it, but there is no file to quote; discovery anomaly, not a textual cause.
- `H:/sotto/.agents/skills/**` — no Herdr line.
- `C:/Users/Administrador/.omp/agent/AGENTS.md:574-577` — skill-routing check ("At session start, consult `skills-updater` … Then use the canonical `task-resolver`"); about skills, not Herdr.
- `H:/sotto/_main/_omp-goal.ps1:4` — explicitly launches a `herdr-lane` persona; it is an opt-in lane launcher, not ordinary work.
- No hook under `H:/sotto` exists; the only pre-hook is `C:/Users/Administrador/.omp/agent/hooks/pre/pressure-guard.ts`, quoted above.
- Other `_packs` hits are console-hiding / historical / backup / token lists, not routing defaults: `_packs/design/best-of-all-worlds/SKILL.md.bak-yaml-20261028:150,156` and `_packs/design/best-of-all-worlds/references/historical-machine-adapter.md:151,157` ("A console-subsystem child (`node`, `python`, `cmd`, `powershell`, `git`, `herdr`) is spawned only with `windowsHide: true` …"; "The only permitted visible terminal is a herdr pane the owner asked for."); `_packs/performance/popup-offenders/SKILL.md:94-104` (`herdr.exe` as a console offender); `skills-updater/scripts/skill-depth-lint.py:45` and `skill-depth-verify.py:29` (binary-name regex). None mandates Herdr as the default.

## 2. What changed

`H:/sotto/AGENTS.md:50-51` is now:

```
## Herdr: cross-project coordination only, never the default
Default is to stay in the current harness (this session, this worktree). Use Herdr only when coordination genuinely spans canonical projects -- a decision or artifact another project's lane must receive. Ordinary project work must not create/focus/move/close a pane, and must not rewrite this file's routing/instructions; a routing edit needs an explicit owner request or a real cross-project need. When Herdr is genuinely needed: cap one visible pane per canonical project across workspaces/worktrees; create via `python I:/!manager/tools/herdr-visible-pane-budget.py workspace --cwd <root> --label <id>` only; unknown/already-present projects refuse; reuse the main pane; extra workers headless; no raw create/focus/move/close.
```

This is one replacement of the two offending lines. It makes the current harness the default, keeps Herdr for genuine cross-project coordination, and forbids rewriting the file's routing as a side effect of ordinary work. It preserves discoverability: the helper command, the cap, and the pane rules are still named.

## 3. Deliberately NOT changed, and why

- **Shared skills** (`handoff:22-25`, `agent-bus:40-43`, `popup-offenders:61`): the project-local edit neutralises the default for this repo, and the shared lines are cross-project mechanisms. The handoff line is the strongest residual cause: a future cross-project handoff still routes through a Herdr lane. Editing it is broad and separately authorized; named here instead.
- **Manager `AGENTS.md:40,104-106` and `project-harness-routing.md:3-5`**: manager-owned, affect every project. They are the source rule, not this repo's ordinary-work default. `project-harness-routing.md` also says "Continue in the existing project pane and retain its visible location", which already agrees with staying put.
- **`_main/_omp-goal.ps1:4` and the `herdr-lane`/`herdr-orchestrator` personas**: opt-in lane dispatch, not ordinary work; changing them would break the manager's lane path.
- **`TODO-omp-handoff-20261109.md`**: owner's handoff with other live items; not mine to edit.
- **Herdr tools**: not deleted or hidden; the new section still names `herdr-visible-pane-budget.py`, the cap and the pane rules.
- **No** `_main/_audit-verify-all.cmd` edit (battery may be in flight), **no** `_main/code-health-baseline.json` refresh, **no** product file.

## 4. Re-read of the final AGENTS.md section

`H:/sotto/AGENTS.md:50-53:raw`:

```
## Herdr: cross-project coordination only, never the default
Default is to stay in the current harness (this session, this worktree). Use Herdr only when coordination genuinely spans canonical projects -- a decision or artifact another project's lane must receive. Ordinary project work must not create/focus/move/close a pane, and must not rewrite this file's routing/instructions; a routing edit needs an explicit owner request or a real cross-project need. When Herdr is genuinely needed: cap one visible pane per canonical project across workspaces/worktrees; create via `python I:/!manager/tools/herdr-visible-pane-budget.py workspace --cwd <root> --label <id>` only; unknown/already-present projects refuse; reuse the main pane; extra workers headless; no raw create/focus/move/close.

## Mandatory task-resolver and model routing
```

## 5. git diff --stat for my files

```
 AGENTS.md | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)
```

`git status --porcelain -- AGENTS.md _main/receipt-20261109-instruction-routing.md` → ` M AGENTS.md` plus the untracked receipt (`?? _main/receipt-20261109-instruction-routing.md`). `git diff --stat` does not list untracked files. The repo's other dirty files are other lanes' work and were not touched.

## 6. Commands actually run

- `grep -n "Herdr panes (mandatory)" AGENTS.md` → rc=1 (no match).
- `grep -n "cross-project coordination only, never the default" AGENTS.md` → rc=0, line 50.
- `grep -rn "Herdr panes" H:/sotto` → no matches.
- `git diff --stat -- AGENTS.md` → 1 file, 2 insertions, 2 deletions.
- `git status --porcelain -- AGENTS.md _main/receipt-20261109-instruction-routing.md` → ` M AGENTS.md`, `?? _main/receipt-20261109-instruction-routing.md`.
- `bash I:/!manager/scripts/cache-task-report.sh <my transcript>` → output below.

## CACHE/PRICE
- task/agent: H:/pi-agent/sessions/--H--sotto--/2026-11-06T19-14-01-218Z_01a1b248-3d82-756a-a50a-2fd9ba36272b/InstructionRouting.jsonl
- source: H:\pi-agent\sessions\--H--sotto--\2026-11-06T19-14-01-218Z_01a1b248-3d82-756a-a50a-2fd9ba36272b\InstructionRouting.jsonl
- cache: read=2323712 write=0 hit=97.2610% (cache-read / input+cache-read); universe: 43 usage rows from H:\pi-agent\sessions\--H--sotto--\2026-11-06T19-14-01-218Z_01a1b248-3d82-756a-a50a-2fd9ba36272b\InstructionRouting.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-2/deepseek-v4.1-flash: calls=43 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-2/deepseek-v4.1-flash $0.00000000 vs $0.00000000 over 43 of 43 matched usage rows
- when-failed: NOT A PREFIX VERDICT — cache-read census: 0 of 42 warm-eligible turns read 0 cache tokens (state=CACHE-MISS-NONE; population: 42 warm-eligible turns of 43 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-11-09T16:45:56.974Z..2026-11-09T16:51:39.908Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-11-06T19-14-01-218Z_01a1b248-3d82-756a-a50a-2fd9ba36272b\InstructionRouting.jsonl)
- where-failed: NOT A PREFIX VERDICT — cache-read census: 0 of 42 warm-eligible turns read 0 cache tokens (state=CACHE-MISS-NONE; population: 42 warm-eligible turns of 43 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-11-09T16:45:56.974Z..2026-11-09T16:51:39.908Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-11-06T19-14-01-218Z_01a1b248-3d82-756a-a50a-2fd9ba36272b\InstructionRouting.jsonl)
- report generated_at: 2026-11-09T16:51:42.611852+00:00
- usage rows: 43
- model + route: opencode-go-2/deepseek-v4.1-flash
- input tokens: 65439
- output tokens: 24358
- cache-read tokens: 2323712
- cache-write tokens: 0
- hit ratio: 97.2610% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-2/deepseek-v4.1-flash: calls=43 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-2/deepseek-v4.1-flash $0.00000000 vs $0.00000000 over 43 of 43 matched usage rows
- prefix breaks: NOT A PREFIX VERDICT — cache-read census: 0 of 42 warm-eligible turns read 0 cache tokens (state=CACHE-MISS-NONE; population: 42 warm-eligible turns of 43 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-11-09T16:45:56.974Z..2026-11-09T16:51:39.908Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-11-06T19-14-01-218Z_01a1b248-3d82-756a-a50a-2fd9ba36272b\InstructionRouting.jsonl)
- WHEN / WHERE failed:
0 of 42 warm-eligible turns read 0 cache tokens (state=CACHE-MISS-NONE; population: 42 warm-eligible turns of 43 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-11-09T16:45:56.974Z..2026-11-09T16:51:39.908Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-11-06T19-14-01-218Z_01a1b248-3d82-756a-a50a-2fd9ba36272b\InstructionRouting.jsonl)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## SELF-AUDIT

- **protocolos em falta** — I did not add a mechanical instruction-lint that keeps this wording from regressing. The house rule forbids editing `_main/_audit-verify-all.cmd` while a battery may be in flight, and the acceptance says "no other file touched", so I left it as a named residual instead of a gate. What I would do differently: land the one-line grep gate in the same pass when the battery is idle.
- **verificacao adicional** — ran the cheap pair: old heading absent (rc=1), new heading present (rc=0), and `Herdr panes` absent repo-wide. This raised confidence that no other project file still carries the old default.
- **checkboxes novas** — add to an instruction-lint: `grep -nE "^## Herdr.*mandatory" AGENTS.md` must be empty, and `grep -n "cross-project coordination only, never the default" AGENTS.md` must hit; a change that restores the old heading must leave it RED.
- **review por outro subagente** — `sim-com-escopo — instruction/routing only`: a fresh agent reads `AGENTS.md:50-51`, confirms the default is "current harness", and confirms no other project file still says "Herdr panes (mandatory)".
- **gate-change-request** — n/a — no gate defect found; this is an instruction-file correction, not a gate change.
- **gate-doubt**
  - `verde-de-verdade:` `git diff --stat -- AGENTS.md` (1 file, 2/2) and `git status --porcelain -- AGENTS.md _main/receipt-20261109-instruction-routing.md` (` M AGENTS.md`, `?? receipt`). The green is real for tracked files but `git diff --stat` cannot see untracked files, so it could pass vacuously about "no other file touched"; paired with the full `git status` (other lanes' dirty files present, untouched) and the repo-wide `grep "Herdr panes"` → no matches.
  - `falta-no-gate:` no gate checks that the Herdr section stays conditional. A future readiness pass could copy `I:/!manager/AGENTS.md:104-106` back into this file and every existing gate stays green. That is the scenario this change walks through.
  - `gate-melhor:` `grep -nE "^## Herdr.*mandatory" H:/sotto/AGENTS.md` must exit 1, and `grep -n "cross-project coordination only, never the default" H:/sotto/AGENTS.md` must exit 0. Input that must leave it RED: restoring the heading `## Herdr panes (mandatory)`.
- **confianca** — `alta` for the trace and the edit; `media` for the behavioural effect until a fresh session reads the new `AGENTS.md`.
- **nao verificado** — no fresh agent session exercised the new default; no runtime; the shared residual (`handoff/SKILL.md:22-25`) still routes cross-project handoffs through a Herdr lane; the manager rules at `I:/!manager/AGENTS.md:40,104-106` remain in force for manager-scoped work.
