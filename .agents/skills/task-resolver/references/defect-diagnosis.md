# Active-defect diagnosis playbook

Use this while something is broken, slow, or silently wrong and the cause is not yet established. Preserve evidence first. A postmortem is for after containment, not a substitute for diagnosis.

## Sequence

1. **Contain safely.** Stop ongoing damage when the impact is understood and reversible. Preserve the failing artifact, state, and relevant logs before cleanup. Record the production entrypoint, observed symptom, affected population/window, expected behavior, and the exact failure boundary.
2. **Reproduce through the real invoker.** Establish a baseline with the same consumer, configuration, and meaningful state. A direct helper call is supporting evidence only unless it is the production path. If the failure is intermittent, capture repeated successes and failures rather than labeling one run representative.
3. **Rank falsifiable causes.** Write a short hypothesis table: candidate mechanism, evidence for/against, cheapest one-variable probe, predicted result, and a result that would refute it. Probe the highest-information candidate first. Change one variable per probe and do not patch based on a plausible story. For high-harm or recurring defects, make a top-down fault tree and bottom-up failure-mode/class inventory before fixing; enumerate every sibling and state how each was checked.
4. **Minimize only when valid.** Use Delta Debugging (`ddmin`) when the failure is repeatable and the input/config/event sequence can be reduced. Preserve the original case; define a deterministic predicate; verify the minimized case still has the same signature and removing each remaining unit makes it pass. If the predicate is noisy or stateful, stabilize/replay it first or mark minimization inapplicable with evidence.
5. **Compare executions.** Replay a known-good and failing case with the same controlled environment. Compare the first divergent observable state, not only final text. Use traces, counters, or logs only after proving the instrumentation covers the real invoker and is healthy; missing data is not a zero.
6. **Find the causal boundary.** Separate trigger, faulty mechanism, failed/missing guard, and impact. Trace callers and configuration in both directions. If the symptom occurs in multiple paths, enumerate the defect class and track each instance explicitly.
7. **Fix the cause.** Make the narrowest change that restores the intended invariant at the responsible boundary. Do not merely suppress the warning, retry an impossible operation, or widen a timeout without evidence that this is the faulty mechanism.
8. **Prove the repair.** Replay the original failing case, run positive and negative controls, and test relevant siblings. For a reproducible defect, capture `EXPECTED-RED` from the focused regression check on the unfixed behavior before patching; after patching, replay the same check and confirm `PASS`. Mutate or revert the focused guard when it is safely mutable and exactly restorable in an isolated boundary. The mutation must fail at the intended assertion/verdict path; an import/setup/harness crash is `NO-VERDICT`. Confirm restoration returns it to `PASS`. If mutation is not safely applicable, state the predicate and reason, run the strongest same-invoker negative control, and leave the mutation claim open. Verify recovery/rollback behavior and that evidence was not corrupted by the probe.
9. **Refute, then learn.** A second pass tries counterexamples, bypasses, races, stale state, and affected callers. A required RED/stale/missing/UNKNOWN gate blocks dependent writes; independent read-only investigation may continue. `EXPECTED-RED` from the pre-fix regression and focused mutation is a successful control. Once contained, record a postmortem with measured impact/population/window, an artifact-backed timeline, the causal chain, the detection escape, and corrective actions in the existing task record; assign an owner, acceptance, falsifier, rollback, recurrence prevention, and an observable silent-failure metric.

## Diagnosis evidence capsule

Keep only what is needed to reproduce and distinguish the claim: invoker and exact arguments; input/state/config identity; expected and observed output; relevant trace/log slice; environment/toolchain; hypothesis and falsifier; baseline/replay result; minimized-case predicate and proof when used; source/config hashes; cleanup/restore result. Redact secrets without changing the behavior under test.

## Stop conditions

- A one-variable probe does not match its prediction: reject or revise the hypothesis before patching.
- Instrumentation health or coverage is unknown: mark the observation `UNKNOWN` and establish coverage before using it as a premise.
- A destructive experiment lacks a reversible control: stop before running it and design a safe equivalent.
- The minimized input no longer reproduces the original signature: it is not a valid reduction.
- The focused mutation stays green: the claimed guard is not proven; repair the test/gate or lower the claim.
