# Worktree Hygiene Receipt

Lane `lane/hygiene` @ `H:\sotto-wt\hygiene`. Machine census. **No move was executed.** Plan only.

## Base and window

- base: `main` @ `f9e38d6cc8d3fd1307d87740769091e21d079f75`, `git rev-list main --count` = 206
- three successive passes; per worktree `git status --porcelain` and `git rev-list main..<branch> --count`
- **population moved 170 -> 173 -> 177 across the passes**: other lanes register worktrees while this runs. The farm is a moving target; this plan is valid only against the population at execution time.
- base sanity: `24df100 b8d7e4b 3d53365 3e90f92 d6257ec a66da947` all confirmed ancestors of `main` (`git merge-base --is-ancestor`), so `uniq=0` on those branches is genuine, not a broken base

## Census table

| worktree | branch | HEAD | dirty | unique-commits-in-main..branch | bucket |
|---|---|---|---|---|---|
| H:/sotto | `feat/build-verify-1` | `24df100` | 818 | 0 | DIRTY-RESCUE |
| H:/sotto-wt-EmbedRuntime | `feat/ring-cap-ram` | `a66da94` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-wt-IndexImpl | `feat/index-impl` | `936d062` | 3 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/ArbV8 | `main` | `f9e38d6` | 9 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/asrq2 | `lane/asrq2` | `b5134a4` | 1 | 2 | DIRTY-RESCUE |
| H:/sotto-wt/audio-v6 | `feat/audio-v6` | `dbe7d8a` | 2 | 1 | DIRTY-RESCUE |
| H:/sotto-wt/audiobat | `lane/audiobat` | `f9e38d6` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/audiofix | `lane/audiofix` | `a6d4af5` | 2 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/AuthFix | `feat/auth-fix-1` | `3d53365` | 2 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/buildfix | `chore/build-recipe-1` | `5f165fa` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/census2 | `chore/true-census-2` | `8fe1175` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/crash | `feat/crash-probe-3` | `2e6d674` | 1 | 1 | DIRTY-RESCUE |
| H:/sotto-wt/crash4 | `feat/crash-probe-4` | `559fa1b` | 2 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/crash5 | `feat/crash-probe-5` | `dd027c1` | 1 | 1 | DIRTY-RESCUE |
| H:/sotto-wt/cronlive | `lane/cronlive` | `f9e38d6` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/cut4 | `feat/cut-verb-4` | `7434749` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/cut5 | `feat/cut-verb-5` | `f660d6d` | 1 | 2 | DIRTY-RESCUE |
| H:/sotto-wt/cutverb3 | `feat/cut-verb-3` | `0ac3fc2` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/e2e | `feat/probe-e2e-2` | `38d88b1` | 2 | 1 | DIRTY-RESCUE |
| H:/sotto-wt/e2e-rerun | `lane/e2e` | `76c40e7` | 2 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/e2e2 | `feat/probe-e2e-3` | `a41bff3` | 3 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/idx2 | `feat/index-perf-2` | `6cfe9b9` | 5 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/IndexCollisionV6 | `research/collision-v6` | `bf82f07` | 2 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/ParseFix | `feat/parse-fix-1` | `1fb8bf0` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/recovery | `lane/recovery` | `2249e96` | 1 | 1 | DIRTY-RESCUE |
| H:/sotto-wt/ReplyFix | `feat/reply-fix-1` | `3d53365` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/rrf | `feat/rrf-3ch-1` | `b4c16a4` | 1 | 1 | DIRTY-RESCUE |
| H:/sotto-wt/rrf2 | `feat/rrf-3ch-2` | `b1319a1` | 1 | 1 | DIRTY-RESCUE |
| H:/sotto-wt/rrf3 | `feat/rrf-3ch-3` | `1095c72` | 1 | 1 | DIRTY-RESCUE |
| H:/sotto-wt/StdinV9 | `feat/stdin-v9` | `fe544e4` | 1 | 2 | DIRTY-RESCUE |
| H:/sotto-wt/WakeBothColoursV2 | `test/wake-both-colours-v2` | `e1f516a` | 2 | 0 | DIRTY-RESCUE |
| H:/sotto-wt/wgc | `feat/wgc-fix-1` | `e281ac3` | 1 | 1 | DIRTY-RESCUE |
| H:/sotto-wt/wgc3 | `feat/wgc-fix-3` | `fea4a34` | 2 | 0 | DIRTY-RESCUE |
| I:/wt/CutVerbI2 | `feat/cut-verb-i2` | `db0cf35` | 1 | 0 | DIRTY-RESCUE |
| H:/sotto-docs-ram-v5 | `docs/ram-v5` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt-ArchiveHeadless | `chore/archive-headless` | `d6257ec` | 0 | 0 | EMPTY |
| H:/sotto-wt-AudioMux | `feat/audio-mux` | `52d1552` | 0 | 0 | EMPTY |
| H:/sotto-wt-EncoderGate | `feat/encoder-gate` | `e1f516a` | 0 | 0 | EMPTY |
| H:/sotto-wt-EngineContract | `feat/engine-contract` | `ddff5c7` | 0 | 0 | EMPTY |
| H:/sotto-wt-EngineContractV2 | `feat/engine-contract-v2` | `ddff5c7` | 0 | 0 | EMPTY |
| H:/sotto-wt-EngineProc | `feat/engine-process` | `a66da94` | 0 | 0 | EMPTY |
| H:/sotto-wt-FlatEndpoint | `feat/FlatEndpoint` | `3e90f92` | 0 | 0 | EMPTY |
| H:/sotto-wt-IndexCollision | `research/index-collision` | `c591b57` | 0 | 0 | EMPTY |
| H:/sotto-wt-OcrImpl | `feat/ocr-impl` | `a66da94` | 0 | 0 | EMPTY |
| H:/sotto-wt-PanelGap | `feat/PanelGap` | `3e90f92` | 0 | 0 | EMPTY |
| H:/sotto-wt-RamDoc | `docs/fix-ram-assumption` | `d6257ec` | 0 | 0 | EMPTY |
| H:/sotto-wt-RingBudget | `research/ring-budget-measured` | `e1f516a` | 0 | 0 | EMPTY |
| H:/sotto-wt-RingCapRam | `feat/ring-cap-ram-c` | `caf7a9a` | 0 | 0 | EMPTY |
| H:/sotto-wt-Spec04Index | `feat/spec-04-index` | `7a63741` | 0 | 0 | EMPTY |
| H:/sotto-wt-StdinCut | `feat/stdin-cut` | `d6257ec` | 0 | 0 | EMPTY |
| H:/sotto-wt-StdinCutV2 | `feat/stdin-cut-v2` | `e1f516a` | 0 | 0 | EMPTY |
| H:/sotto-wt-StdinCutV3 | `feat/stdin-cut-v3` | `e1f516a` | 0 | 0 | EMPTY |
| H:/sotto-wt-TapRestartLoop | `feat/TapRestartLoop` | `3e90f92` | 0 | 0 | EMPTY |
| H:/sotto-wt/altc | `lane/altc` | `91c0666` | 0 | 0 | EMPTY |
| H:/sotto-wt/asr-clip-contract | `feat/asr-clip-contract` | `f12d18f` | 0 | 0 | EMPTY |
| H:/sotto-wt/AsrClipV2 | `feat/asr-clip-contract-v2` | `e1f516a` | 0 | 0 | EMPTY |
| H:/sotto-wt/AsrContractV4 | `feat/asr-contract-v4` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/asrq | `lane/asrq` | `caa8187` | 0 | 0 | EMPTY |
| H:/sotto-wt/audio-mux-v2 | `feat/audio-mux-v2` | `4e57461` | 0 | 0 | EMPTY |
| H:/sotto-wt/audio-mux-v3 | `feat/audio-mux-v3` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/audio-v7 | `feat/audio-v7` | `d63a954` | 0 | 0 | EMPTY |
| H:/sotto-wt/AudioTap | `feat/audio-tap-real-1` | `3d53365` | 0 | 0 | EMPTY |
| H:/sotto-wt/AudioTapV4 | `feat/audio-v4` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/AudioTapV5 | `feat/audio-v5` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/audiowire | `feat/audio-wire-2` | `3fdd076` | 0 | 0 | EMPTY |
| H:/sotto-wt/blind4 | `feat/blind-parser-4` | `3b9af15` | 0 | 0 | EMPTY |
| H:/sotto-wt/cap2panel | `lane/cap2panel` | `b5b1b90` | 0 | 0 | EMPTY |
| H:/sotto-wt/cleanup | `chore/worktree-cleanup-1` | `366d6a5` | 0 | 0 | EMPTY |
| H:/sotto-wt/crash6 | `feat/crash-probe-6` | `33dcd5c` | 0 | 0 | EMPTY |
| H:/sotto-wt/CrashProbe | `feat/crash-probe-1` | `3d53365` | 0 | 0 | EMPTY |
| H:/sotto-wt/cut6 | `feat/cut-verb-6` | `33a6742` | 0 | 0 | EMPTY |
| H:/sotto-wt/CutVerb | `feat/cut-verb-1` | `3d53365` | 0 | 0 | EMPTY |
| H:/sotto-wt/DetachedTest | `feat/detached-test-1` | `1fb8bf0` | 0 | 0 | EMPTY |
| H:/sotto-wt/DiskFix | `feat/disk-fix-1` | `a9c2109` | 0 | 0 | EMPTY |
| H:/sotto-wt/docs | `lane/docs` | `e8c4bf0` | 0 | 0 | EMPTY |
| H:/sotto-wt/encoder-gate | `feat/encoder-gate-v2` | `e1f516a` | 0 | 0 | EMPTY |
| H:/sotto-wt/encoder-gate-v3 | `feat/encoder-gate-v3` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/EngineProcV4 | `feat/engine-v4` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/ffprod | `lane/ffprod` | `a296318` | 0 | 0 | EMPTY |
| H:/sotto-wt/ForgeryFix | `feat/forgery-fix-1` | `a9c2109` | 0 | 0 | EMPTY |
| H:/sotto-wt/gatecheck | `lane/gatecheck` | `31171a2` | 0 | 0 | EMPTY |
| H:/sotto-wt/gateverify | `chore/gate-verify-1` | `e7ff874` | 0 | 0 | EMPTY |
| H:/sotto-wt/hotkey2 | `chore/hotkey-2` | `dc67cfa` | 0 | 0 | EMPTY |
| H:/sotto-wt/idx16 | `lane/idx16` | `ea63eae` | 0 | 0 | EMPTY |
| H:/sotto-wt/IndexCollisionV2 | `research/index-collision-v2` | `3cbd55f` | 0 | 0 | EMPTY |
| H:/sotto-wt/IndexCollisionV3 | `research/index-collision-v3` | `527050f` | 0 | 0 | EMPTY |
| H:/sotto-wt/integrity | `lane/integrity` | `dad108f` | 0 | 0 | EMPTY |
| H:/sotto-wt/mergeall | `lane/mergeall` | `7242a69` | 0 | 0 | EMPTY |
| H:/sotto-wt/mergesweep | `chore/merge-sweep-1` | `018546f` | 0 | 0 | EMPTY |
| H:/sotto-wt/panelrun | `chore/panel-run-1` | `978da0d` | 0 | 0 | EMPTY |
| H:/sotto-wt/parakeet | `chore/parakeet-1` | `c37ae58` | 0 | 0 | EMPTY |
| H:/sotto-wt/parity | `lane/parity` | `04affb3` | 0 | 0 | EMPTY |
| H:/sotto-wt/ram4 | `feat/ram-budget-4` | `77af385` | 0 | 0 | EMPTY |
| H:/sotto-wt/RamFixV4 | `docs/ram-fix-v4` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/RRFProbe | `feat/rrf-probe-1` | `3d53365` | 0 | 0 | EMPTY |
| H:/sotto-wt/scalegate | `feat/scale-gate-4` | `6aa764b` | 0 | 0 | EMPTY |
| H:/sotto-wt/ScaleProbe | `feat/scale-probe-1` | `248dfc9` | 0 | 0 | EMPTY |
| H:/sotto-wt/SliceV5 | `feat/slice-v5` | `eb1c963` | 0 | 0 | EMPTY |
| H:/sotto-wt/SliceV7 | `feat/slice-v7` | `f937646` | 0 | 0 | EMPTY |
| H:/sotto-wt/StdinV6 | `feat/stdin-v6` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/StdinV7 | `feat/stdin-v7` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/WakeV4 | `test/wake-v4` | `b8d7e4b` | 0 | 0 | EMPTY |
| H:/sotto-wt/wip/feat-slice-v6 | `feat/slice-v6` | `a08cc82` | 0 | 0 | EMPTY |
| H:/sotto-wt/wip/fix-ram-assumption-v2 | `docs/fix-ram-assumption-v2` | `e1f516a` | 0 | 0 | EMPTY |
| H:/sotto-wt/wip/fix-ram-assumption-v3 | `docs/fix-ram-assumption-v3` | `b8d7e4b` | 0 | 0 | EMPTY |
| I:/wt/CutVerbI1 | `feat/cut-verb-i1` | `db0cf35` | 0 | 0 | EMPTY |
| I:/wt/ParseFix2 | `feat/parse-fix-2` | `db0cf35` | 0 | 0 | EMPTY |
| H:/sotto-wt/ArbV9 | `feat/stdin-v9` | `fe544e4` | 0 | 2 | KEEP |
| H:/sotto-wt/argfix | `chore/audio-flag-1` | `fe18e22` | 0 | 1 | KEEP |
| H:/sotto-wt/asr | `chore/asr-truth-1` | `d58f77e` | 0 | 1 | KEEP |
| H:/sotto-wt/AudioTap2 | `feat/audio-tap-2` | `17599e5` | 0 | 1 | KEEP |
| H:/sotto-wt/audioverify | `chore/audio-verify-1` | `e047fcf` | 0 | 1 | KEEP |
| H:/sotto-wt/AuthFix2 | `feat/auth-fix-2` | `d6b34cc` | 0 | 1 | KEEP |
| H:/sotto-wt/blind2 | `feat/blind-bdeda02-2` | `3a3856f` | 0 | 2 | KEEP |
| H:/sotto-wt/blind3 | `feat/blind-bdeda02-3` | `542756b` | 0 | 1 | KEEP |
| H:/sotto-wt/bridgewire | `chore/bridge-wire-1` | `6ce820a` | 0 | 1 | KEEP |
| H:/sotto-wt/briefkit | `lane/briefkit` | `9971bfd` | 0 | 1 | KEEP |
| H:/sotto-wt/buildcheck | `chore/build-check-2` | `cf1e284` | 0 | 3 | KEEP |
| H:/sotto-wt/capthr | `chore/caption-threshold-1` | `643064c` | 0 | 1 | KEEP |
| H:/sotto-wt/census | `chore/true-census-1` | `f55d3aa` | 0 | 1 | KEEP |
| H:/sotto-wt/correct | `docs/retraction-correction-1` | `4caea02` | 0 | 1 | KEEP |
| H:/sotto-wt/CrashProbe2 | `feat/crash-probe-2` | `3ba542a` | 0 | 1 | KEEP |
| H:/sotto-wt/cron6 | `lane/cron6` | `1994870` | 0 | 1 | KEEP |
| H:/sotto-wt/crondiag | `lane/crondiag` | `ca6884e` | 0 | 1 | KEEP |
| H:/sotto-wt/cronstall | `lane/cronstall` | `e2e5e5f` | 0 | 1 | KEEP |
| H:/sotto-wt/cront | `lane/cront` | `b0d0750` | 0 | 2 | KEEP |
| H:/sotto-wt/cront5 | `lane/cront5` | `0fbf3d5` | 0 | 1 | KEEP |
| H:/sotto-wt/CutVerb2 | `feat/cut-verb-2` | `d0a3b9f` | 0 | 1 | KEEP |
| H:/sotto-wt/decisions | `lane/decisions` | `ca29d44` | 0 | 2 | KEEP |
| H:/sotto-wt/epstable | `feat/endpoint-stable-1` | `76b67f3` | 0 | 1 | KEEP |
| H:/sotto-wt/epverify | `chore/endpoint-verify-1` | `1b62dc4` | 0 | 1 | KEEP |
| H:/sotto-wt/features | `chore/panel-features-1` | `38c6e57` | 0 | 1 | KEEP |
| H:/sotto-wt/ffprep | `lane/ffprep` | `c2798c8` | 0 | 2 | KEEP |
| H:/sotto-wt/finalcap | `chore/final-caption-1` | `f6cebf2` | 0 | 1 | KEEP |
| H:/sotto-wt/guardfix | `lane/guardfix` | `8a13fe4` | 0 | 1 | KEEP |
| H:/sotto-wt/hotkey | `chore/hotkey-1` | `d0cb61f` | 0 | 1 | KEEP |
| H:/sotto-wt/hotkey3 | `chore/hotkey-3` | `0db2739` | 0 | 1 | KEEP |
| H:/sotto-wt/hygiene | `lane/hygiene` | `563abdd` | 0 | 1 | KEEP |
| H:/sotto-wt/idx3 | `feat/index-perf-3` | `f4f2616` | 0 | 3 | KEEP |
| H:/sotto-wt/idxperf | `feat/index-perf-1` | `cc5c433` | 0 | 1 | KEEP |
| H:/sotto-wt/langfix | `chore/lang-quality-1` | `f15826a` | 0 | 1 | KEEP |
| H:/sotto-wt/maxch | `lane/maxch` | `99a0204` | 0 | 1 | KEEP |
| H:/sotto-wt/MergeAudit2 | `feat/merge-audit-2` | `17072a2` | 0 | 1 | KEEP |
| H:/sotto-wt/mergegate | `lane/mergegate` | `91fdcb3` | 0 | 1 | KEEP |
| H:/sotto-wt/merges | `lane/merges` | `b2f6d4e` | 0 | 1 | KEEP |
| H:/sotto-wt/mvp | `docs/mvp-order-1` | `2fb1528` | 0 | 1 | KEEP |
| H:/sotto-wt/nr | `lane/nr` | `2e90b2c` | 0 | 1 | KEEP |
| H:/sotto-wt/panelbuild | `chore/panel-build-1` | `212d592` | 0 | 1 | KEEP |
| H:/sotto-wt/parser | `lane/parser` | `fa290c4` | 0 | 1 | KEEP |
| H:/sotto-wt/ptv2 | `lane/ptv2` | `c7ca105` | 0 | 1 | KEEP |
| H:/sotto-wt/ptverify | `lane/ptverify` | `c3fca69` | 0 | 1 | KEEP |
| H:/sotto-wt/pushprep | `lane/pushprep` | `43780ae` | 0 | 2 | KEEP |
| H:/sotto-wt/ram2 | `feat/ram-budget-2` | `acccdac` | 0 | 1 | KEEP |
| H:/sotto-wt/ram3 | `feat/ram-budget-3` | `957ed84` | 0 | 1 | KEEP |
| H:/sotto-wt/rambudget | `feat/ram-budget-1` | `9ea4084` | 0 | 1 | KEEP |
| H:/sotto-wt/RamV6 | `docs/ram-v6` | `7a994b4` | 0 | 1 | KEEP |
| H:/sotto-wt/recordfix | `lane/recordfix` | `73cd3f3` | 0 | 1 | KEEP |
| H:/sotto-wt/recover | `lane/recover` | `8c7ba01` | 0 | 1 | KEEP |
| H:/sotto-wt/roadmap | `lane/roadmap` | `f55dbd7` | 0 | 1 | KEEP |
| H:/sotto-wt/RRFProbe2 | `feat/rrf-probe-2` | `55a95f6` | 0 | 1 | KEEP |
| H:/sotto-wt/scalegate2 | `lane/scalegate2` | `d5c47e8` | 0 | 1 | KEEP |
| H:/sotto-wt/ScaleProbe2 | `feat/scale-probe-2` | `10c7ef3` | 0 | 1 | KEEP |
| H:/sotto-wt/shresearch | `lane/shresearch` | `50c25f9` | 0 | 2 | KEEP |
| H:/sotto-wt/sweep2 | `chore/merge-sweep-2` | `dd9f9c1` | 0 | 1 | KEEP |
| H:/sotto-wt/taint | `chore/evidence-audit-1` | `a155cac` | 0 | 1 | KEEP |
| H:/sotto-wt/thresh | `lane/thresh` | `26aa3f1` | 0 | 1 | KEEP |
| H:/sotto-wt/Verify499 | `feat/verify-499-1` | `458856c` | 0 | 1 | KEEP |
| H:/sotto-wt/wgc2 | `feat/wgc-fix-2` | `729d609` | 0 | 2 | KEEP |
| H:/sotto-wt/worker | `chore/worker-truth-1` | `d7fe23d` | 0 | 1 | KEEP |
| H:/sotto-wt/worker2 | `chore/worker-truth-2` | `2ed9509` | 0 | 1 | KEEP |
| I:/wt/AudioReal | `feat/audio-tap-real` | `0561c65` | 0 | 1 | KEEP |
| I:/wt/AudioWire | `feat/audio-wire` | `239450d` | 0 | 1 | KEEP |
| I:/wt/Blind1 | `feat/blind-bdeda02` | `2f0da0c` | 0 | 1 | KEEP |
| I:/wt/ForgeryFix2 | `feat/forgery-fix-2` | `5ee8369` | 0 | 1 | KEEP |
| I:/wt/Rev1 | `feat/review-db0cf35` | `56b9e9d` | 0 | 1 | KEEP |
| I:/wt/Rev952 | `feat/review-952` | `e065cac` | 0 | 1 | KEEP |
| I:/wt/RRFCrash | `feat/rrf-crash-1` | `5ab682b` | 0 | 1 | KEEP |

POPULATION: 177 registered worktrees (H: = 167, I: = 10)

## DIRTY worktrees - file inventory

A destroyed-work incident already cost this project one uncommitted file. Nothing in DIRTY-RESCUE may move until a rescue commit exists. Note `H:/sotto` (the primary tree) and `H:/sotto-wt/ArbV8` (integration) are NOT farm lanes and are excluded from every move below.

### H:/sotto - `feat/build-verify-1` - dirty=818 - uniq-in-main=0

```
 M AGENTS.md
 M README.md
 M _main/_armE-fake-worker.py
 M _main/_audit-render/make-harness.py
 M _main/_audit-render/panel-chrome-frame.html
 M _main/_audit-render/panel-chrome-real.html
 M _main/_audit-render/panel-cost-on.html
 M _main/_audit-render/panel-cost-reduced.html
 M _main/_audit-render/panel-cost-relayout.html
 M _main/_audit-render/panel-harness.html
 M _main/_audit-verify-all.cmd
 M _main/_audit-verify/_battery-summary.txt
 M _main/_audit-verify/js/BOOTSTRAP_JS.js
 M _main/_audit-verify/js/BRIDGE_PROBE.js
 M _main/_design-lane/gen_themes.py
 M _main/_panel-anim-cost-arm.py
 M _main/_panel-anim-cost.js
 M _main/_panel-anim-cost.json
 M _main/_panel-chrome-arm.py
 M _main/_panel-chrome-probe.js
 M _main/_panel-clear-lifted-mutant.py
 M _main/_panel-verdict-benign-mutant.py
 M _main/_panel2-dom-probe.js
 M _main/_redux-gate-mutants/env-optin.py
 M _main/_redux-gate-mutants/fail-safe.py
... (793 more lines)
```

### H:/sotto-wt/ArbV8 - `main` - dirty=9 - uniq-in-main=0

```
 M _main/CRON-VERDICT.md
?? FRICTION-LEDGER.md
?? _main/cron-restore-probe.py
?? _main/cron-restore-refute.py
?? _main/cron-silence-control.py
?? _main/cron-store-loose-ends.py
?? _main/pos.bat
?? _main/spawn2.bat
?? control/
```

### H:/sotto-wt/idx2 - `feat/index-perf-2` - dirty=5 - uniq-in-main=0

```
 M _moved/aireplay/_main/index_perf_prof.py
 M _moved/aireplay/src/index/search.py
 M _moved/aireplay/src/index/store.py
?? _moved/aireplay/_main/idx2_split_bench.py
?? _moved/aireplay/src/index/_scratch/
```

### H:/sotto-wt-IndexImpl - `feat/index-impl` - dirty=3 - uniq-in-main=0

```
?? _moved/aireplay/src/index/.gitignore
?? _moved/aireplay/src/index/_index-red-crash-child.py
?? _moved/aireplay/src/index/_index-red-probe.py
```

### H:/sotto-wt/e2e2 - `feat/probe-e2e-3` - dirty=3 - uniq-in-main=0

```
 M _main/e2e_probe.ps1
?? _main/build/
?? _main/e2e-build.cmd
```

### H:/sotto-wt/audio-v6 - `feat/audio-v6` - dirty=2 - uniq-in-main=1

```
 M _moved/aireplay/src/capture/audio_tap.h
?? _moved/aireplay/src/capture/audio_tap.cpp
```

### H:/sotto-wt/audiofix - `lane/audiofix` - dirty=2 - uniq-in-main=0

```
?? _main/check_audio_flag.py
?? worker/_prefix_audioflag.py
```

### H:/sotto-wt/AuthFix - `feat/auth-fix-1` - dirty=2 - uniq-in-main=0

```
 M _moved/aireplay/src/capture/main.cpp
?? _build.txt
```

### H:/sotto-wt/crash4 - `feat/crash-probe-4` - dirty=2 - uniq-in-main=0

```
 M _main/crash_probe.ps1
?? _main/build/
```

### H:/sotto-wt/e2e - `feat/probe-e2e-2` - dirty=2 - uniq-in-main=1

```
?? _main/_stdin_probe.py
?? _main/build/
```

### H:/sotto-wt/e2e-rerun - `lane/e2e` - dirty=2 - uniq-in-main=0

```
?? _main/_e2e_receipt_cmd.py
?? _main/runB.rc
```

### H:/sotto-wt/IndexCollisionV6 - `research/collision-v6` - dirty=2 - uniq-in-main=0

```
?? _armc/
?? _merged/
```

### H:/sotto-wt/WakeBothColoursV2 - `test/wake-both-colours-v2` - dirty=2 - uniq-in-main=0

```
?? _probe_schema.out.txt
?? _probe_schema.py
```

### H:/sotto-wt/wgc3 - `feat/wgc-fix-3` - dirty=2 - uniq-in-main=0

```
?? _main/build/
?? _main/logs/
```

### H:/sotto-wt-EmbedRuntime - `feat/ring-cap-ram` - dirty=1 - uniq-in-main=0

```
 M _moved/aireplay/src/capture/d3d11_ctx.cpp
```

### H:/sotto-wt/asrq2 - `lane/asrq2` - dirty=1 - uniq-in-main=2

```

```

### H:/sotto-wt/audiobat - `lane/audiobat` - dirty=1 - uniq-in-main=0

```
?? _main/AUDIO-BATTERY.md
```

### H:/sotto-wt/buildfix - `chore/build-recipe-1` - dirty=1 - uniq-in-main=0

```
 M _moved/aireplay/src/capture/build.cmd
```

### H:/sotto-wt/census2 - `chore/true-census-2` - dirty=1 - uniq-in-main=0

```
?? _main/TRUE-CENSUS.md
```

### H:/sotto-wt/crash - `feat/crash-probe-3` - dirty=1 - uniq-in-main=1

```
?? _main/crash_probe.ps1
```

### H:/sotto-wt/crash5 - `feat/crash-probe-5` - dirty=1 - uniq-in-main=1

```
?? _main/build/
```

### H:/sotto-wt/cronlive - `lane/cronlive` - dirty=1 - uniq-in-main=0

```
?? _main/CRON-LIVE.md
```

### H:/sotto-wt/cut4 - `feat/cut-verb-4` - dirty=1 - uniq-in-main=0

```
 M _moved/aireplay/src/capture/main.cpp
```

### H:/sotto-wt/cut5 - `feat/cut-verb-5` - dirty=1 - uniq-in-main=2

```
 M _moved/aireplay/src/capture/main.cpp
```

### H:/sotto-wt/cutverb3 - `feat/cut-verb-3` - dirty=1 - uniq-in-main=0

```
?? _main/build/
```

### H:/sotto-wt/ParseFix - `feat/parse-fix-1` - dirty=1 - uniq-in-main=0

```
 M _moved/aireplay/src/capture/main.cpp
```

### H:/sotto-wt/recovery - `lane/recovery` - dirty=1 - uniq-in-main=1

```
?? _recovered/
```

### H:/sotto-wt/ReplyFix - `feat/reply-fix-1` - dirty=1 - uniq-in-main=0

```
 M _moved/aireplay/src/capture/main.cpp
```

### H:/sotto-wt/rrf - `feat/rrf-3ch-1` - dirty=1 - uniq-in-main=1

```
?? _main/rrf_probe.py
```

### H:/sotto-wt/rrf2 - `feat/rrf-3ch-2` - dirty=1 - uniq-in-main=1

```
 M _main/rrf_probe.py
```

### H:/sotto-wt/rrf3 - `feat/rrf-3ch-3` - dirty=1 - uniq-in-main=1

```
?? _main/rrf_probe.py
```

### H:/sotto-wt/StdinV9 - `feat/stdin-v9` - dirty=1 - uniq-in-main=2

```
?? _build/
```

### H:/sotto-wt/wgc - `feat/wgc-fix-1` - dirty=1 - uniq-in-main=1

```
?? _main/build/
```

### I:/wt/CutVerbI2 - `feat/cut-verb-i2` - dirty=1 - uniq-in-main=0

```
 M _moved/aireplay/src/capture/main.cpp
```

## ARCHIVE PLAN (proposed - NOT executed)

Scope: the 144 farm worktrees under `H:\sotto-wt\`, excluding `H:\sotto-wt\ArbV8` (integration) and excluding `H:/sotto`, `H:/sotto-docs-ram-v5`, and all 10 `I:\wt\*` worktrees. `git worktree move` is same-drive only, so the `I:\` worktrees cannot be archived into `H:\` by this mechanism and need a separate decision.

Destination preserves the subpath under `H:\sotto-wt\`, so rollback restores the EXACT original path - required for the 3 nested worktrees under `wip\`. Verified: 0 rollback-target collisions, 0 leaf collisions (141 flat + 3 nested).

Bucket to destination: EMPTY -> `done`, KEEP -> `wip`, DIRTY-RESCUE -> `unsure`.

### Step 0 - preconditions
```
New-Item -ItemType Directory -Force -Path H:\sotto-wt\_archive\wip,H:\sotto-wt\_archive\done,H:\sotto-wt\_archive\unsure | Out-Null
```

### ROLLBACK (this undoes the entire MOVE section below)

Single command. It only touches real worktree directories (identified by a `.git` marker), skips the `wip`/`done`/`unsure` container dirs, and skips any destination that already exists, so it is safe to re-run:

```
Get-ChildItem H:\sotto-wt\_archive\wip,H:\sotto-wt\_archive\done,H:\sotto-wt\_archive\unsure -Directory -Recurse -Depth 1 | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName '.git') } | ForEach-Object { $dest = Join-Path 'H:\sotto-wt' ($_.FullName -replace '^H:\\sotto-wt\\_archive\\(wip|done|unsure)\\',''); if(-not (Test-Path -LiteralPath $dest)){ git -C H:\sotto-wt\ArbV8 worktree move $_.FullName $dest } }
```

Explicit per-worktree rollback (move command reversed). Authoritative form - 144 commands, one per moved worktree:
```
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\asrq2" "H:\sotto-wt\asrq2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\audio-v6" "H:\sotto-wt\audio-v6"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\audiobat" "H:\sotto-wt\audiobat"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\audiofix" "H:\sotto-wt\audiofix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\AuthFix" "H:\sotto-wt\AuthFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\buildfix" "H:\sotto-wt\buildfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\census2" "H:\sotto-wt\census2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\crash" "H:\sotto-wt\crash"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\crash4" "H:\sotto-wt\crash4"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\crash5" "H:\sotto-wt\crash5"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\cronlive" "H:\sotto-wt\cronlive"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\cut4" "H:\sotto-wt\cut4"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\cut5" "H:\sotto-wt\cut5"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\cutverb3" "H:\sotto-wt\cutverb3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\e2e" "H:\sotto-wt\e2e"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\e2e-rerun" "H:\sotto-wt\e2e-rerun"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\e2e2" "H:\sotto-wt\e2e2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\idx2" "H:\sotto-wt\idx2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\IndexCollisionV6" "H:\sotto-wt\IndexCollisionV6"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\ParseFix" "H:\sotto-wt\ParseFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\recovery" "H:\sotto-wt\recovery"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\ReplyFix" "H:\sotto-wt\ReplyFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\rrf" "H:\sotto-wt\rrf"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\rrf2" "H:\sotto-wt\rrf2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\rrf3" "H:\sotto-wt\rrf3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\StdinV9" "H:\sotto-wt\StdinV9"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\WakeBothColoursV2" "H:\sotto-wt\WakeBothColoursV2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\wgc" "H:\sotto-wt\wgc"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\unsure\wgc3" "H:\sotto-wt\wgc3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\altc" "H:\sotto-wt\altc"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\asr-clip-contract" "H:\sotto-wt\asr-clip-contract"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\AsrClipV2" "H:\sotto-wt\AsrClipV2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\AsrContractV4" "H:\sotto-wt\AsrContractV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\asrq" "H:\sotto-wt\asrq"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\audio-mux-v2" "H:\sotto-wt\audio-mux-v2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\audio-mux-v3" "H:\sotto-wt\audio-mux-v3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\audio-v7" "H:\sotto-wt\audio-v7"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\AudioTap" "H:\sotto-wt\AudioTap"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\AudioTapV4" "H:\sotto-wt\AudioTapV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\AudioTapV5" "H:\sotto-wt\AudioTapV5"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\audiowire" "H:\sotto-wt\audiowire"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\blind4" "H:\sotto-wt\blind4"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\cap2panel" "H:\sotto-wt\cap2panel"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\cleanup" "H:\sotto-wt\cleanup"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\crash6" "H:\sotto-wt\crash6"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\CrashProbe" "H:\sotto-wt\CrashProbe"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\cut6" "H:\sotto-wt\cut6"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\CutVerb" "H:\sotto-wt\CutVerb"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\DetachedTest" "H:\sotto-wt\DetachedTest"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\DiskFix" "H:\sotto-wt\DiskFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\docs" "H:\sotto-wt\docs"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\encoder-gate" "H:\sotto-wt\encoder-gate"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\encoder-gate-v3" "H:\sotto-wt\encoder-gate-v3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\EngineProcV4" "H:\sotto-wt\EngineProcV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\ffprod" "H:\sotto-wt\ffprod"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\ForgeryFix" "H:\sotto-wt\ForgeryFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\gatecheck" "H:\sotto-wt\gatecheck"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\gateverify" "H:\sotto-wt\gateverify"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\hotkey2" "H:\sotto-wt\hotkey2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\idx16" "H:\sotto-wt\idx16"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\IndexCollisionV2" "H:\sotto-wt\IndexCollisionV2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\IndexCollisionV3" "H:\sotto-wt\IndexCollisionV3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\integrity" "H:\sotto-wt\integrity"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\mergeall" "H:\sotto-wt\mergeall"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\mergesweep" "H:\sotto-wt\mergesweep"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\panelrun" "H:\sotto-wt\panelrun"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\parakeet" "H:\sotto-wt\parakeet"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\parity" "H:\sotto-wt\parity"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\ram4" "H:\sotto-wt\ram4"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\RamFixV4" "H:\sotto-wt\RamFixV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\RRFProbe" "H:\sotto-wt\RRFProbe"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\scalegate" "H:\sotto-wt\scalegate"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\ScaleProbe" "H:\sotto-wt\ScaleProbe"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\SliceV5" "H:\sotto-wt\SliceV5"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\SliceV7" "H:\sotto-wt\SliceV7"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\StdinV6" "H:\sotto-wt\StdinV6"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\StdinV7" "H:\sotto-wt\StdinV7"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\WakeV4" "H:\sotto-wt\WakeV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\wip\feat-slice-v6" "H:\sotto-wt\wip\feat-slice-v6"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\wip\fix-ram-assumption-v2" "H:\sotto-wt\wip\fix-ram-assumption-v2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\done\wip\fix-ram-assumption-v3" "H:\sotto-wt\wip\fix-ram-assumption-v3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\ArbV9" "H:\sotto-wt\ArbV9"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\argfix" "H:\sotto-wt\argfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\asr" "H:\sotto-wt\asr"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\AudioTap2" "H:\sotto-wt\AudioTap2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\audioverify" "H:\sotto-wt\audioverify"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\AuthFix2" "H:\sotto-wt\AuthFix2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\blind2" "H:\sotto-wt\blind2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\blind3" "H:\sotto-wt\blind3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\bridgewire" "H:\sotto-wt\bridgewire"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\briefkit" "H:\sotto-wt\briefkit"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\buildcheck" "H:\sotto-wt\buildcheck"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\capthr" "H:\sotto-wt\capthr"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\census" "H:\sotto-wt\census"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\correct" "H:\sotto-wt\correct"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\CrashProbe2" "H:\sotto-wt\CrashProbe2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\cron6" "H:\sotto-wt\cron6"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\crondiag" "H:\sotto-wt\crondiag"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\cronstall" "H:\sotto-wt\cronstall"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\cront" "H:\sotto-wt\cront"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\cront5" "H:\sotto-wt\cront5"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\CutVerb2" "H:\sotto-wt\CutVerb2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\decisions" "H:\sotto-wt\decisions"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\epstable" "H:\sotto-wt\epstable"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\epverify" "H:\sotto-wt\epverify"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\features" "H:\sotto-wt\features"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\ffprep" "H:\sotto-wt\ffprep"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\finalcap" "H:\sotto-wt\finalcap"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\guardfix" "H:\sotto-wt\guardfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\hotkey" "H:\sotto-wt\hotkey"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\hotkey3" "H:\sotto-wt\hotkey3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\hygiene" "H:\sotto-wt\hygiene"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\idx3" "H:\sotto-wt\idx3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\idxperf" "H:\sotto-wt\idxperf"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\langfix" "H:\sotto-wt\langfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\maxch" "H:\sotto-wt\maxch"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\MergeAudit2" "H:\sotto-wt\MergeAudit2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\mergegate" "H:\sotto-wt\mergegate"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\merges" "H:\sotto-wt\merges"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\mvp" "H:\sotto-wt\mvp"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\nr" "H:\sotto-wt\nr"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\panelbuild" "H:\sotto-wt\panelbuild"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\parser" "H:\sotto-wt\parser"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\ptv2" "H:\sotto-wt\ptv2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\ptverify" "H:\sotto-wt\ptverify"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\pushprep" "H:\sotto-wt\pushprep"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\ram2" "H:\sotto-wt\ram2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\ram3" "H:\sotto-wt\ram3"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\rambudget" "H:\sotto-wt\rambudget"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\RamV6" "H:\sotto-wt\RamV6"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\recordfix" "H:\sotto-wt\recordfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\recover" "H:\sotto-wt\recover"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\roadmap" "H:\sotto-wt\roadmap"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\RRFProbe2" "H:\sotto-wt\RRFProbe2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\scalegate2" "H:\sotto-wt\scalegate2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\ScaleProbe2" "H:\sotto-wt\ScaleProbe2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\shresearch" "H:\sotto-wt\shresearch"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\sweep2" "H:\sotto-wt\sweep2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\taint" "H:\sotto-wt\taint"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\thresh" "H:\sotto-wt\thresh"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\Verify499" "H:\sotto-wt\Verify499"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\wgc2" "H:\sotto-wt\wgc2"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\worker" "H:\sotto-wt\worker"
git -C H:\sotto-wt\ArbV8 worktree move "H:\sotto-wt\_archive\wip\worker2" "H:\sotto-wt\worker2"
```

### MOVE (proposed, gated)

#### done  (EMPTY - zero unique commits, clean) - 52 worktrees
```
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/altc" "H:\sotto-wt\_archive\done\altc"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/asr-clip-contract" "H:\sotto-wt\_archive\done\asr-clip-contract"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/AsrClipV2" "H:\sotto-wt\_archive\done\AsrClipV2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/AsrContractV4" "H:\sotto-wt\_archive\done\AsrContractV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/asrq" "H:\sotto-wt\_archive\done\asrq"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/audio-mux-v2" "H:\sotto-wt\_archive\done\audio-mux-v2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/audio-mux-v3" "H:\sotto-wt\_archive\done\audio-mux-v3"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/audio-v7" "H:\sotto-wt\_archive\done\audio-v7"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/AudioTap" "H:\sotto-wt\_archive\done\AudioTap"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/AudioTapV4" "H:\sotto-wt\_archive\done\AudioTapV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/AudioTapV5" "H:\sotto-wt\_archive\done\AudioTapV5"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/audiowire" "H:\sotto-wt\_archive\done\audiowire"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/blind4" "H:\sotto-wt\_archive\done\blind4"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cap2panel" "H:\sotto-wt\_archive\done\cap2panel"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cleanup" "H:\sotto-wt\_archive\done\cleanup"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/crash6" "H:\sotto-wt\_archive\done\crash6"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/CrashProbe" "H:\sotto-wt\_archive\done\CrashProbe"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cut6" "H:\sotto-wt\_archive\done\cut6"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/CutVerb" "H:\sotto-wt\_archive\done\CutVerb"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/DetachedTest" "H:\sotto-wt\_archive\done\DetachedTest"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/DiskFix" "H:\sotto-wt\_archive\done\DiskFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/docs" "H:\sotto-wt\_archive\done\docs"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/encoder-gate" "H:\sotto-wt\_archive\done\encoder-gate"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/encoder-gate-v3" "H:\sotto-wt\_archive\done\encoder-gate-v3"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/EngineProcV4" "H:\sotto-wt\_archive\done\EngineProcV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ffprod" "H:\sotto-wt\_archive\done\ffprod"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ForgeryFix" "H:\sotto-wt\_archive\done\ForgeryFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/gatecheck" "H:\sotto-wt\_archive\done\gatecheck"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/gateverify" "H:\sotto-wt\_archive\done\gateverify"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/hotkey2" "H:\sotto-wt\_archive\done\hotkey2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/idx16" "H:\sotto-wt\_archive\done\idx16"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/IndexCollisionV2" "H:\sotto-wt\_archive\done\IndexCollisionV2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/IndexCollisionV3" "H:\sotto-wt\_archive\done\IndexCollisionV3"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/integrity" "H:\sotto-wt\_archive\done\integrity"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/mergeall" "H:\sotto-wt\_archive\done\mergeall"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/mergesweep" "H:\sotto-wt\_archive\done\mergesweep"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/panelrun" "H:\sotto-wt\_archive\done\panelrun"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/parakeet" "H:\sotto-wt\_archive\done\parakeet"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/parity" "H:\sotto-wt\_archive\done\parity"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ram4" "H:\sotto-wt\_archive\done\ram4"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/RamFixV4" "H:\sotto-wt\_archive\done\RamFixV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/RRFProbe" "H:\sotto-wt\_archive\done\RRFProbe"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/scalegate" "H:\sotto-wt\_archive\done\scalegate"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ScaleProbe" "H:\sotto-wt\_archive\done\ScaleProbe"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/SliceV5" "H:\sotto-wt\_archive\done\SliceV5"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/SliceV7" "H:\sotto-wt\_archive\done\SliceV7"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/StdinV6" "H:\sotto-wt\_archive\done\StdinV6"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/StdinV7" "H:\sotto-wt\_archive\done\StdinV7"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/WakeV4" "H:\sotto-wt\_archive\done\WakeV4"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/wip/feat-slice-v6" "H:\sotto-wt\_archive\done\wip\feat-slice-v6"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/wip/fix-ram-assumption-v2" "H:\sotto-wt\_archive\done\wip\fix-ram-assumption-v2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/wip/fix-ram-assumption-v3" "H:\sotto-wt\_archive\done\wip\fix-ram-assumption-v3"
```

#### wip  (KEEP - unique commits not in main) - 63 worktrees
```
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ArbV9" "H:\sotto-wt\_archive\wip\ArbV9"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/argfix" "H:\sotto-wt\_archive\wip\argfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/asr" "H:\sotto-wt\_archive\wip\asr"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/AudioTap2" "H:\sotto-wt\_archive\wip\AudioTap2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/audioverify" "H:\sotto-wt\_archive\wip\audioverify"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/AuthFix2" "H:\sotto-wt\_archive\wip\AuthFix2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/blind2" "H:\sotto-wt\_archive\wip\blind2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/blind3" "H:\sotto-wt\_archive\wip\blind3"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/bridgewire" "H:\sotto-wt\_archive\wip\bridgewire"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/briefkit" "H:\sotto-wt\_archive\wip\briefkit"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/buildcheck" "H:\sotto-wt\_archive\wip\buildcheck"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/capthr" "H:\sotto-wt\_archive\wip\capthr"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/census" "H:\sotto-wt\_archive\wip\census"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/correct" "H:\sotto-wt\_archive\wip\correct"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/CrashProbe2" "H:\sotto-wt\_archive\wip\CrashProbe2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cron6" "H:\sotto-wt\_archive\wip\cron6"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/crondiag" "H:\sotto-wt\_archive\wip\crondiag"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cronstall" "H:\sotto-wt\_archive\wip\cronstall"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cront" "H:\sotto-wt\_archive\wip\cront"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cront5" "H:\sotto-wt\_archive\wip\cront5"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/CutVerb2" "H:\sotto-wt\_archive\wip\CutVerb2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/decisions" "H:\sotto-wt\_archive\wip\decisions"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/epstable" "H:\sotto-wt\_archive\wip\epstable"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/epverify" "H:\sotto-wt\_archive\wip\epverify"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/features" "H:\sotto-wt\_archive\wip\features"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ffprep" "H:\sotto-wt\_archive\wip\ffprep"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/finalcap" "H:\sotto-wt\_archive\wip\finalcap"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/guardfix" "H:\sotto-wt\_archive\wip\guardfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/hotkey" "H:\sotto-wt\_archive\wip\hotkey"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/hotkey3" "H:\sotto-wt\_archive\wip\hotkey3"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/hygiene" "H:\sotto-wt\_archive\wip\hygiene"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/idx3" "H:\sotto-wt\_archive\wip\idx3"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/idxperf" "H:\sotto-wt\_archive\wip\idxperf"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/langfix" "H:\sotto-wt\_archive\wip\langfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/maxch" "H:\sotto-wt\_archive\wip\maxch"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/MergeAudit2" "H:\sotto-wt\_archive\wip\MergeAudit2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/mergegate" "H:\sotto-wt\_archive\wip\mergegate"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/merges" "H:\sotto-wt\_archive\wip\merges"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/mvp" "H:\sotto-wt\_archive\wip\mvp"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/nr" "H:\sotto-wt\_archive\wip\nr"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/panelbuild" "H:\sotto-wt\_archive\wip\panelbuild"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/parser" "H:\sotto-wt\_archive\wip\parser"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ptv2" "H:\sotto-wt\_archive\wip\ptv2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ptverify" "H:\sotto-wt\_archive\wip\ptverify"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/pushprep" "H:\sotto-wt\_archive\wip\pushprep"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ram2" "H:\sotto-wt\_archive\wip\ram2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ram3" "H:\sotto-wt\_archive\wip\ram3"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/rambudget" "H:\sotto-wt\_archive\wip\rambudget"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/RamV6" "H:\sotto-wt\_archive\wip\RamV6"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/recordfix" "H:\sotto-wt\_archive\wip\recordfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/recover" "H:\sotto-wt\_archive\wip\recover"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/roadmap" "H:\sotto-wt\_archive\wip\roadmap"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/RRFProbe2" "H:\sotto-wt\_archive\wip\RRFProbe2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/scalegate2" "H:\sotto-wt\_archive\wip\scalegate2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ScaleProbe2" "H:\sotto-wt\_archive\wip\ScaleProbe2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/shresearch" "H:\sotto-wt\_archive\wip\shresearch"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/sweep2" "H:\sotto-wt\_archive\wip\sweep2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/taint" "H:\sotto-wt\_archive\wip\taint"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/thresh" "H:\sotto-wt\_archive\wip\thresh"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/Verify499" "H:\sotto-wt\_archive\wip\Verify499"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/wgc2" "H:\sotto-wt\_archive\wip\wgc2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/worker" "H:\sotto-wt\_archive\wip\worker"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/worker2" "H:\sotto-wt\_archive\wip\worker2"
```

#### unsure  (DIRTY-RESCUE - BLOCKED until each has a rescue commit) - 29 worktrees

Do NOT run these before a rescue commit exists on each branch, or the uncommitted files move with the directory without being in git history.
```
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/asrq2" "H:\sotto-wt\_archive\unsure\asrq2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/audio-v6" "H:\sotto-wt\_archive\unsure\audio-v6"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/audiobat" "H:\sotto-wt\_archive\unsure\audiobat"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/audiofix" "H:\sotto-wt\_archive\unsure\audiofix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/AuthFix" "H:\sotto-wt\_archive\unsure\AuthFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/buildfix" "H:\sotto-wt\_archive\unsure\buildfix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/census2" "H:\sotto-wt\_archive\unsure\census2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/crash" "H:\sotto-wt\_archive\unsure\crash"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/crash4" "H:\sotto-wt\_archive\unsure\crash4"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/crash5" "H:\sotto-wt\_archive\unsure\crash5"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cronlive" "H:\sotto-wt\_archive\unsure\cronlive"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cut4" "H:\sotto-wt\_archive\unsure\cut4"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cut5" "H:\sotto-wt\_archive\unsure\cut5"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/cutverb3" "H:\sotto-wt\_archive\unsure\cutverb3"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/e2e" "H:\sotto-wt\_archive\unsure\e2e"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/e2e-rerun" "H:\sotto-wt\_archive\unsure\e2e-rerun"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/e2e2" "H:\sotto-wt\_archive\unsure\e2e2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/idx2" "H:\sotto-wt\_archive\unsure\idx2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/IndexCollisionV6" "H:\sotto-wt\_archive\unsure\IndexCollisionV6"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ParseFix" "H:\sotto-wt\_archive\unsure\ParseFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/recovery" "H:\sotto-wt\_archive\unsure\recovery"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/ReplyFix" "H:\sotto-wt\_archive\unsure\ReplyFix"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/rrf" "H:\sotto-wt\_archive\unsure\rrf"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/rrf2" "H:\sotto-wt\_archive\unsure\rrf2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/rrf3" "H:\sotto-wt\_archive\unsure\rrf3"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/StdinV9" "H:\sotto-wt\_archive\unsure\StdinV9"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/WakeBothColoursV2" "H:\sotto-wt\_archive\unsure\WakeBothColoursV2"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/wgc" "H:\sotto-wt\_archive\unsure\wgc"
git -C H:\sotto-wt\ArbV8 worktree move "H:/sotto-wt/wgc3" "H:\sotto-wt\_archive\unsure\wgc3"
```

CENSUS VERDICT: KEEP 70 / DIRTY-RESCUE 34 / EMPTY 73 / ORPHAN 0
