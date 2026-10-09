# MERGE-ALL — integration lane receipt

Scope: fold 15 sibling `lane/*` branches into `main` safely, refusing empty work.

Method per branch: `git merge-tree $(git merge-base main <br>) main <br>` BEFORE any merge,
then real merge on `lane/mergeall`, then branch-shipped tests with real exit codes.

Highest-stakes decision: `lane/audiofix` (production code `worker/sotto_worker.py`)
cross-checked against `lane/e2e`'s refutation of the original pipeline receipt.

Never `git add -A`. Never commit to `main` from a lane. Merge decision handed back with evidence.

Status: in progress.