# GATE-RECHECK — scale gate re-proof (lane/gatecheck)

Status: IN PROGRESS — worktree created from `main` @ 8d33896.

## Scope
Re-prove the `scale_gate_selftest.py` fix: the gate previously printed `RESULT: PASS`
while compliance was `frac_under_16ms=0.000` (passed at ZERO percent). Fix merged;
positive control added. This lane re-runs the self-test in FULL, re-proves the
negative arms still go RED, re-proves the positive arm still goes GREEN, and
cross-checks one claim in `gate-verdict.md` against measured output.

## Population / Window
TBD — recorded at run time.

## Findings
TBD.