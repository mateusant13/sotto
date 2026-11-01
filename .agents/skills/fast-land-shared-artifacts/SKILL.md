---
name: fast-land-shared-artifacts
description: Keep code, necessary proof, and disk use moving together. Use before agent fan-out or builds/tests that can create substantial files.
version: 1.0.0
---

# Fast landing and shared artifact budget

Owner directive effective 2026-10-31T02:59:01-03:00. The goal is shipped behavior with only the process and evidence needed to make it safe. Optional paperwork that costs more than the change is skipped. Necessary docs and proof move with the code in the same delivery.

## Before fan-out or heavy output

1. Name the exact workspace, output volume, sanctioned target/cache paths, and every planned heavy operation. Read only those paths; never sweep a whole drive to estimate them.
2. Measure free bytes on the destination volume and current bytes in those exact shared paths. Estimate peak incremental bytes across the whole batch, counting each genuinely shared artifact once and per-lane scratch separately. State the method and uncertainty. If the estimate is unknown, run one bounded probe or serialize; do not launch several speculative copies.
3. Reuse one sanctioned target/cache per project and toolchain across its agents and worktrees. Do not create a target, virtual environment, model cache, repository clone, or build-output copy for each lane. Isolate code with Git worktrees while sharing Git objects and the project's existing artifact store.
4. If the shared target cannot be written safely by simultaneous jobs, serialize those jobs or use a proven shared content-addressed cache. Do not solve a lock or concurrency issue by cloning the heavy artifact.
5. Obey the project's live build policy; never invent or override a target path. Keep required source and tests. Avoid downloads, duplicate logs, full transcripts, and bundled reports that are not part of the acceptance proof.
6. Remove only generated artifacts whose owner and regeneration path are known. Measure exact paths and bytes before removal; preserve user work, uncommitted source, and uncertain data.
7. After work, report the exact output paths, added/freed bytes, and the command or measurement. Keep one useful evidence artifact, not copies of it.

## Rule for parallel work

Before dispatch, calculate the combined disk impact of all ready lanes. Several agents may share one target; they do not get several targets. If the shared target is unsafe, run the disk-heavy phase serially. Keep agent count governed by useful independent code work and the machine's measured process limits, not by duplicated caches.
