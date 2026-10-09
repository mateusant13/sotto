# PARSER-RECHECK — blind matrix re-run + adversarial break

Status: IN PROGRESS. Skeleton committed before work started (rules: commit fast, never `git add -A`).

## Scope
Re-run the 45-case blind matrix for the C++ stdin/parser subsystem (hardened in
4852381, db0cf35, 952f3bf, bdeda02), then attack it with cases the original
matrix does not cover.

## Findings
(filled below as work lands)