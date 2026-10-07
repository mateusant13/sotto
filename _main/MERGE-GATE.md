# MERGE GATE — lane/mergeall -> main

Seat: branch/mergegate (`mvs_e2f375cd37074fb1bb59d0db8249e176`)
Date: 2026-10-07
Baseline: main @ 8d33896 (166 commits, clean at gate open)
Candidate: lane/mergeall (38 commits ahead)

## Scope of this gate
Prove BEHAVIOURALLY the `worker/sotto_worker.py` change (+32/-4) on `lane/mergeall`:
`audio_file = os.environ.get("SOTTO_AUDIO_FILE") or args.audio` and
`file_mode = bool(audio_file) or args.selftest`, resolved once at boot.

Root already read the diff. This lane runs it.

## Facts
- product root: H:\sotto (authoritative, HAS weights)
- H:\sotto-wt\ArbV8 is a COPY worktree WITHOUT weights — never infer "weights absent" from it
- weights: worker\models (9 dirs); sample: worker\assets\sample1.flac (13.44s, English/Dickens)
- `--audio` alone now implies file mode, so `gate_enabled = not _file_mode` -> OFF. INTENDED.

## The 5 cases
| # | invocation | expectation |
|---|------------|-------------|
| 1 | `--audio FILE` alone | file mode, transcribes FILE, NEVER opens live device |
| 2 | `--selftest` alone | bundled sample1.flac, unchanged |
| 3 | `--selftest --audio FILE` | FILE, unchanged |
| 4 | neither flag | LIVE mode, unchanged |
| 5 | `SOTTO_AUDIO_FILE=FILE` | FILE, env wins over flag |

## Acceptance (non-negotiable)
1. Case 1 MUST NOT open the live device. PROVE it, not infer it.
2. `python H:\sotto\worker\sotto_worker.py --audio C:\nope.wav` MUST fail LOUDLY.
   Silent fallback to the live device here = GATE FAILURE.
3. Cases 2/3/4 must be bit-identical to pre-change behaviour.
4. Real rc + real stderr for every case. No summarised failures.

## Merge
- `git merge-tree` lane/mergeall vs main must be clean
- merge WITHOUT squash (lane commits are the record)
- ANY of the 5 cases failing -> BLOCK, no merge.

## Results
(see RESULTS section appended below)