---
name: task-resolver
description: "Use for every non-trivial software task: defects…"
license: Proprietary
metadata:
  version: "1.4.1"
  author: manager-house
---

# Task Resolver

Use this workflow from request to verified outcome. Local project rules and the owner's instructions take precedence. Reuse the project's existing task record, tests, tools, and vocabulary; do not create a second tracker or assume a harness-specific feature exists.

## Evidence vocabulary

- `PASS`: the named predicate was exercised and met.
- `EXPECTED-RED`: a pre-fix regression or targeted mutation failed at the intended assertion/verdict path, exactly as predicted. This is a successful control, not a green product result.
- `FAIL`: an acceptance predicate is violated or a required gate fails unexpectedly.
- `NO-VERDICT`: the instrument could not judge the predicate (for example setup/import error, timeout, missing input, or unhealthy observer). A process exit code alone does not name the cause.
- `UNKNOWN` / `NOT RUN`: evidence is insufficient or the check was not executed; required rows stay open.
- `NOT APPLICABLE`: only for a row marked conditional at intake, with its applicability predicate and evidence, plus approval by the task owner or project closure authority before closure. The executor cannot self-retire an open row. If applicability was not knowable at intake, keep it `UNKNOWN` until that authority updates the existing task record and snapshot under the project's change process.

## Invocation gate — mechanize what can be checked

Run this immediately at every non-trivial invocation, before dependent product edits:

1. Classify each acceptance row as `MECHANICAL` or `JUDGMENT` in the existing task record.
2. Every `MECHANICAL` row names an executable assertion/gate and a negative control that must produce `EXPECTED-RED`; include positive, failure, restoration, or cancellation arms where they matter. If the needed gate is missing or untrusted, add the smallest project-native checker and wire it into the real invoker, dispatch, or closure path as a prerequisite of this same task. Exercise its controls before relying on it. Do not defer a needed gate as a future recommendation.
3. Every `JUDGMENT` row names evidence and a falsifier, then receives the sequential refutation pass. Do not invent a metric to automate a judgment that has no observable boundary.
4. If the task lacks a required record, TODO, skill-delivery proof, evidence receipt, or closure mechanism, bootstrap only the smallest capability this task needs now; use [tooling-bootstrap.md](references/tooling-bootstrap.md). Do not create a second tracker or unrelated infrastructure.

Model or provider exhaustion is a routing event, never a reason to leave a lane idle or mark it blocked. Follow the project's authorized fallback policy; for the owner's projects, see [model-routing.md](references/model-routing.md). Keep actionable implementation and verification moving, and keep any unverified review row open. Never turn missing evidence into a pass.

## Required workflow

1. **Set the finish line.** Restate the requested outcome as one observable sentence. Convert every user-named requirement into an acceptance row with a falsifier. Record scope, affected users/data, stop condition, rollback, and unresolved decisions. A plausible interpretation is not acceptance.
2. **Choose one record.** Continue the existing issue, ticket, task card, or roadmap item. If none exists and the task is non-trivial, create one small record with a stable ID. Map each acceptance row to a dependency-aware TODO; give each item an owner, output, and executable acceptance exercise. Keep the TODO editable with append-only history and freeze its initial snapshot before dispatch. A TODO is a worklist, not another backlog.
3. **Understand before editing.** Read applicable instructions and relevant skills. Trace the actual production entrypoint through the affected code, callers, configuration, state, and existing checks. Name the real invoker, current behavior, evidence, assumptions, unknowns, and the cheapest falsifying probe. Read or inspect the exact artifacts you cite. If an unknown could change the design, resolve it before implementation.
4. **Check and pave the proof path now.** Identify which existing commands prove each acceptance row and whether they run through the real consumer. Prefer project-native search, tests, traces, replay, and gates. For each mechanical row with no reliable control, make the smallest needed instrument a dependency in this task, implement and wire it before dependent product edits, then exercise its positive, negative, and failure controls. Add a dependency only for a concrete proof gap; first check whether the current stack already provides the capability.
5. **Order the work.** Build a small dependency graph. Parallelize only independent discovery or disjoint writes; assign one owner per overlapping path. A solo agent records the path/version/digest of the skill bytes it read and any references consulted; this is a traceability note, not a claim that a harness delivered them. Before a worker/reviewer/scout starts, deliver the exact scope, required skill, editable task TODO, acceptance, falsifier, owned paths, and resource constraints. Freeze the initial TODO and record the exact skill/TODO bytes and hashes at the lane boundary. If delivery cannot be proved, that lane's delivery row stays `UNKNOWN`; route another lane or keep other task items moving, and do not close it.
6. **Triage safety and choose the task playbook.** For an active defect, follow `references/defect-diagnosis.md`: preserve evidence, assess ongoing harm, contain it when needed, and choose a safe experiment boundary before replaying or probing. Exercise the real invoker in a faithful isolated boundary with controlled external effects when possible; production activation is a separate exercise. If no safe faithful reproduction is available, preserve evidence and leave that proof row open. For a feature, define the observable contract and wire one vertical slice through the real entrypoint. For performance work, define population, workload, window, baseline, and user-visible metric before measuring; measure relevant CPU, memory/commit, GPU, disk, and I/O conditions and retain comparisons with their conditions. For refactors, state the invariant and prove behavior is preserved. For configuration, schema, or migration work, trace precedence and every consumer and prove upgrade plus rollback paths. For high-harm or recurring mechanisms, use a top-down fault tree and bottom-up failure-mode/class enumeration before patching; enumerate and close affected siblings. For research, separate sourced facts, inference, and unknowns, then tie each adopted claim to a code-level acceptance row. For tools or infrastructure, prove discovery, invocation, failure behavior, and cancellation—not just file presence.
7. **Establish a safe baseline.** Reproduce current behavior at the real invoker only within the safety boundary chosen in step 6, or record why reproduction is impossible. For a reproducible defect, observe and save the focused regression check failing on the unfixed behavior before changing it. Save the minimal evidence capsule needed to replay it: invocation, relevant input/state/config, expected and observed result, and hashes or redacted references. If no correct pre-fix test seam exists, record that gap; do not claim a proved fix. Every potentially blocking command or external wait needs a first-output ceiling, a wall ceiling, and cancellation where supported. Apply resource controls to actual heavy local processes; never impose arbitrary tool-call or agent-count quotas.
8. **Implement the smallest causal slice.** Change the mechanism that violates the contract. Keep unrelated cleanup out of the patch. Preserve failing evidence until the focused regression check can replay it. For recurring or high-impact failure modes, inspect the full affected class rather than fixing only the first instance. If a required baseline or gate becomes `RED`, stale, missing, or `UNKNOWN`, stop only dependent product writes; repair or refresh the proof path and advance independent safe items in the same live task. An expected `EXPECTED-RED` result from the pre-fix regression or targeted mutation is a successful control, not a blocking gate. Model exhaustion never idles the lane; route according to local policy and keep evidence states honest.
9. **Prove each acceptance row.** Run the narrowest checks that exercise the real invoker, plus affected regression checks. Use a positive control and a negative control for each mechanical claim. A negative control passes only when the expected rejection is attributable to the target assertion/verdict path; a crash, import, setup, timeout, or harness error is `NO-VERDICT`, not evidence that the guard fired. For a reproducible defect, the pre-fix regression must produce `EXPECTED-RED` on the unfixed behavior and `PASS` after the repair. For gates, invariants, and safety checks, use a targeted mutation/revert when the claimed guard is mutable and can be exactly restored in an isolated test boundary. The mutation must produce `EXPECTED-RED` at the intended assertion; unrelated failures do not count. If mutation is not safely applicable, record the predicate and reason, run the strongest same-invoker negative control, and leave the mutation claim unproved. Replay observed failures where possible. Bind multi-stage evidence to the exact source, configuration, toolchain, inputs, outputs, and predecessor receipts; reuse deterministic proof only when its complete fingerprint and outputs still match. Check external state live.
10. **Run a refutation pass.** After the first verification pass, perform a separate sequential pass whose purpose is to disprove the result: revisit every acceptance row, omitted user requirement, bypass path, affected sibling, stale receipt, restore step, and the exact artifact used by the real invoker. Record refuted claims instead of dropping them. This is a required adversarial pass, not an independent review; obey project rules that require independent reviewers.
11. **Close with evidence.** Report each acceptance row as `PASS`, `FAIL`, `UNKNOWN`, `NOT RUN`, or `NOT APPLICABLE` with its reason and evidence path. `UNKNOWN` and `NOT RUN` are open work. `NOT APPLICABLE` is valid only for a row marked conditional at intake, with its applicability predicate and evidence, plus approval by the task owner or project closure authority before closure; the executor cannot self-retire an open row. If applicability was not knowable at intake, keep the row `UNKNOWN` until that authority updates the existing task record and snapshot through the project's change process. Do not call a task done while a required row is open. State exactly what changed, which commands actually ran, what they printed/returned, what remains unverified, and the next owner/action. After containment or a meaningful near miss, use the local postmortem protocol to record measured impact, population/window, artifact-backed timeline, causal chain, detection escape, and owned corrective actions with acceptance, falsifier, and rollback; use diagnosis while the defect is active.

## Required task record

For a non-trivial task, the single source-of-truth record must identify: final intent; scope and owner; acceptance rows and their `MECHANICAL`/`JUDGMENT` class; real invoker; baseline; falsifier; dependency-ordered TODO; owned paths; positive and negative controls; the executable gate for every mechanical row; applicability decisions for conditional proofs; mutation/revert when applicable; provenance; rollback; process-resource guard for heavy local work; verification evidence; open unknowns; closure state. Use the project's existing schema. See `references/tooling-bootstrap.md` when the project lacks a capability needed to satisfy this contract.

## Completion rule

Claim only what the recorded evidence proves. A passing unit test does not prove production activation; a visible tool does not prove it is wired; a green gate does not prove its falsifier works; an arbitrary failure does not prove a negative control; a task title or TODO does not prove delivery. If the real invoker cannot be exercised, report the exact boundary and leave that acceptance row open.

## Escalation: procedure packs this workflow delegates to

This workflow is the default spine for every non-trivial task. Two installed skills own procedure that this file does not restate. Load them by id; do not paraphrase their contents here.

### `complete-understanding` — load before the first edit

Load it once the task is non-trivial and the affected entrypoint has not already been traced in this session. It owns the comprehension protocol: what to read, in what order, and how to tell "I understand" from "I have a plausible guess". This workflow owns acceptance and evidence; that skill owns comprehension. Neither replaces the other.

### `agentic-feature-build` — load when any escalation marker is present

The pack now lives **inside this repository** at `.agents/skills/agentic-feature-build/` (moved there 2026-10-27 so this spine's escalation cannot break when the global kit is pruned), with the same content also installed at `C:\Users\Administrador\.agents\skills\agentic-feature-build\`; its source lineage is `G:\superharness\.agents\skills\agentic-feature-build\`. Load the repo copy first and record the `version:` line you actually read. If the copies disagree, report the divergence with both versions instead of picking one. If neither resolves, this row is `UNKNOWN` and dependent product edits halt.

Loading it **by id with the skill tool** is the intended path, and it is the only one: the pack declares `opencode/autoinvoke: "false"`, so it is deliberately absent from the model-facing skill list. Absence from that list is not absence of the skill — measured 2026-10-25, the live resolver (`opencode api GET /api/skill`) returns the pack with `autoinvoke=false` and its full content. Escalating here is not an unowned invocation: `AGENTS.md` makes this file the mandatory spine for every non-trivial task, so the delegation is the owner's standing instruction, not a claim this file invents.

Load it for a task when **any** of these holds:

1. The change touches persistent state, security, money, concurrency, admission or gates, provider or model routing, observability claims, recovery, or data integrity/loss.
2. Material uncertainty exists: an unanswered question could change the behavior contract, the data shape, the acceptance result, or safe integration.
3. Two or more independently verifiable units exist whose dependency requires sequencing.
4. A prior escaped defect is in scope, or the owner asks for high confidence.
5. The behavior becomes available only through a build, install, reload, spawn, or runtime activation.

When escalated, record in the task record `pack: agentic-feature-build@<version> sha256=<hash>` plus the marker that triggered it, and load the pack's assurance selector before writing the plan. The pack's numbered review rounds, its independent-reviewer requirement, and its per-intention evidence checkboxes then govern this task in place of this file's orchestrator-discretion review. That scoped override is the only conflict rule: the pack never changes this file's evidence vocabulary, and `EXPECTED-RED` stays a control rather than a failure.

If the pack is missing, unreadable, or its recorded hash does not match, mark this escalation row `UNKNOWN` with the attempted path and halt dependent product edits. A missing pack is an open row, never a silent skip back to the default spine.

Escalation is a rule, not a preference: a qualifying task that ran without the pack carries an open assurance row and cannot be closed.

## Phases this spine owns

Absorbed 2026-10-27 from the global skill kit, so this file is the single place those procedures live. Each
paragraph states the rule the phase contributes and where it lands in the workflow above. Nothing here is a
second tracker: the record is still the project's task card / ticket, and the proof is still an executed
control.

**Contract before code (step 1).** For anything user-visible, keep one contract: the problem from the user's
perspective, the solution from the user's perspective, numbered user stories, implementation decisions
(modules and interfaces, not file paths or code snippets — those go stale), testing decisions, and an explicit
out-of-scope list. Release the contract to an implementer with no open question; an unasked question that
could change the contract is `unknown`, which selects high assurance rather than "no".

**Decomposition (step 5).** Slice into **tracer bullets**: each slice cuts a narrow but complete path through
every layer, is demoable or verifiable on its own, fits one fresh context, and declares its **blocking edges**.
Width beats depth only for a **wide refactor** — one mechanical change whose blast radius fans across the
tree — which is sequenced expand → migrate in batches → contract, never forced into a single slice. Work the
frontier (blockers all done). In this repo the tickets are task cards under `state/cards/`, and their blocking
edges are text; never invent a second issue tracker.

**Test-first slice (step 7-8).** Write the failing check first, at a **pre-agreed seam** that exercises the
real bug pattern at the call site, and run it before the implementation. One slice, one test, one minimal
implementation, then repeat. Refactoring is not part of the loop. A test that recomputes the expected value
the way the code does is tautological and forbidden by this repo's test-hygiene law. **Override for this
machine:** do not add a test suite to a codebase that has none — record the missing seam as the finding
instead, because a test at a shallow seam is false confidence.

**Probe when the design is uncertain (between steps 3 and 8).** A prototype is throwaway code that answers
one question. Mark it as a prototype, make it trivially runnable, keep state in memory, skip the polish, and
surface the state after every action so the owner can judge it. When it settles a decision, capture the
decision and drop the prototype; main keeps only the decision.

**Research (step 3).** Investigate against primary sources — official docs, source code, specs, first-party
APIs — and follow each claim back to the source that owns it. Delegate the reading to a read-only subagent so
the main session keeps working, and land the findings as one Markdown file with the source URL and date beside
each claim. A design without a cited source is a guess.

**Execute (steps 8-9).** Resume before you restart: adopt the existing canonical record rather than opening a
parallel one. For multi-unit work, run the ready frontier in parallel lanes, each in its own worktree, each
merging the spine back before reporting; communicate through context pointers (contract, cards, receipts,
commits), never by restating them.

**Review (step 10), when review is selected — it remains orchestrator discretion.** Run **two axes
separately and never rerank them into one verdict**: *Standards* (does the change violate a documented repo
standard or a known smell?) and *Spec* (does it miss, exceed, or mis-implement what was asked?). Pin the
fixed point, name the spec source, name the standards sources, and give each reviewer the complete diff. Code
can pass one axis and fail the other; that separation is the point. The author never approves their own work.

**Retro (step 11), after a contained incident.** The retrospective's output is an improvement to the
**environment**, not to the code that just landed: navigation, an automated check that would have caught it,
a review rule, a too-large `AGENTS.md`, tool economy, a no-op instruction, missing information access.
Classify first: a **mechanical** violation gets a deterministic check (lint rule, hook, CI job); only genuine
judgement calls become a written standard. Land the improvement as its own task card; use the local
`postmortem` protocol for the incident itself.

