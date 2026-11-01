# Tooling bootstrap for a project that cannot yet prove its work

Do not install a framework merely because this skill names a capability. First inventory the existing task system, invokers, tests, tracing, runners, replay facilities, and closure controls. Add only the smallest missing mechanism that closes a named proof gap. Avoid a second backlog or a parallel copy of an existing tool.

## Invocation-time bootstrap (required)

When Task Resolver is invoked, this is executable work, not a future recommendation. Before product edits that depend on a deterministic predicate:

1. Map every acceptance row to an existing executable gate or to an explicit judgment/evidence check.
2. For each deterministic row with no reliable gate, add the smallest project-native control to the current task's dependency plan, wire it through the real invoker or closure path, and exercise its positive and negative arms immediately.
3. Repair an untrusted control before relying on it. A test, hook, skill, or script that exists but is not invoked is not a gate.
4. Continue other safe, independent task items while repairing a gate. Model/provider exhaustion never leaves the task idle; use the authorized fallback route and preserve unverified rows as open.

Build only controls needed by this task's acceptance rows. Do not turn this bootstrap into an unrelated tooling program.

## Minimum capability map

| Capability | Minimum useful behavior | Required falsifier/control |
|---|---|---|
| One task record and worklist | Stable task ID, final intent, acceptance, owner, dependencies, owned paths, editable TODO, immutable dispatch snapshot | A missing or stale TODO/acceptance row is rejected at dispatch or closure |
| Acceptance-to-gate map | Each acceptance row is marked `MECHANICAL` or `JUDGMENT`; each mechanical row names a real executable gate and falsifier | Remove a gate invocation or leave a mechanical row unmapped; the task preflight/closure refuses |
| Invoker map | Names the real production entrypoint, its callers/configuration, and activation path | A helper-only check cannot satisfy an activation claim |
| Bounded command runner | Captures exit status/output, first-output and wall ceilings, cancellation, and cleanup result | PASS, expected RED, unexpected RED, NO-VERDICT, and CANCELLED remain distinct; a setup crash cannot impersonate the target assertion |
| Evidence receipt/chain | Binds command/source, inputs/configuration, declared environment, toolchain, outputs, and parent receipts | Changing an input, output, or parent makes stale evidence refuse |
| Positive/negative controls | One real accepted case and one meaningful rejected/broken case for each mechanical claim | A no-op or vacuous fixture cannot pass as coverage |
| Mutation/revert | When the guard is safely mutable and exactly restorable, applies a focused fault in an isolated copy or controlled branch and restores exact bytes | The target assertion rejects the mutation and the gate returns GREEN after restoration; unrelated setup/import failures are NO-VERDICT |
| Replay | Re-executes a preserved real failure through the actual consumer | Replay distinguishes the known failure from the known-good control |
| Observability | Measures the population and interval relevant to the claim; distinguishes zero, missing, stale, and unhealthy | Remove/disable the expected signal and prove the observer reports missing/UNKNOWN |
| Closure gate | Admits only when required task rows have executed evidence, conditional omissions were declared at intake and approved by the task owner or closure authority before closure, and no `UNKNOWN` is counted as PASS | A deliberately incomplete/stale receipt or executor-only `NOT APPLICABLE` is refused |
| Resource governor | Limits or queues the actual heavy local process using measured host/project constraints | Pressure slows/queues that process while lightweight agent work remains live |

These are behavior contracts, not required product names. Reuse native test runners, property/stateful testing, tracing, profiling, queues, and process controls when they already meet the contract. Add a package only when a concrete defect class or evidence gap cannot be handled reliably with the current stack; record why, its compatibility surface, and how its behavior is verified.

## Harness adapter

For each harness, add one short mandatory instruction that triggers this skill for non-trivial software work. Deliver the skill through the strongest mechanism that harness supports, then prove discovery and invocation with a small marker task. If skills are not supported, link the same canonical instructions from the agent's operational file. Keep one canonical skill and verify every packaged copy by SHA-256; do not hand-edit divergent copies. Treat code intelligence, indexes, and traces as navigation aids until their coverage and health are demonstrated for the target entrypoint.

## Bootstrap order

1. Inventory existing task records, TODOs, test commands, real invokers, instrumentation, and closure scripts.
2. Choose the single source of truth for task status and the existing command runner.
3. Build an invoker-to-acceptance map for one real task; name any row that current tools cannot prove.
4. Add only the smallest missing control, receipt, replay fixture, activation check, or resource governor.
5. Exercise its positive, negative, mutation, restoration, timeout, and wiring arms as applicable.
6. Add the skill trigger, package the canonical bytes, and verify the harness actually surfaces them.
7. Run the new mechanism against one real task and record gaps as explicit open rows. Do not claim the bootstrap is effective from documentation alone.
