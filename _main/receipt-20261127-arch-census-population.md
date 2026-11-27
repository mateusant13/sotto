# Receipt — the arch slider's monolith census counts files that are not production code

**Date:** 2026-11-27
**Subject:** `architecture_coherence` (60 → 90 target), the 30-point gap
**Verdict:** the gap is real; the census adds 5 non-production files on top of it,
which is worth **+1 point**, not the 30.

## 1. What the census actually counts

`exocortex/panorama.py:542 `_scan_monoliths` walks the repo and flags every
`.py/.rs/.ts/.tsx/.js` file with `>= MONOLITH_THRESHOLD_LOC = 1500`. Its only
pruning is:

```python
dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS
                                     and not d.startswith("_probe"))
```

`SKIP_DIRS` is a **name set**, so a dot-directory at any depth is never pruned.
The same module already owns the correct predicate for this question — and does
not use it here:

```python
# exocortex/panorama.py:112
return any(p in SKIP_DIRS for p in parts[:-1])
```

`load_user_skip()` (`.codeintel/skip.json` + `CODEINTEL_SKIP_DIRS`) exists in
`codeintel/health/preflight.py:447`. `panorama.py` never calls it.

## 2. The five files it counts that are not production code

| LOC | file | why it is not production |
|---:|---|---|
| 6668 | `worker/models/.sotto-runtime/genai-cuda/.../builders/base.py` | vendored runtime, **git-ignored** (`git check-ignore` → yes, `git ls-files` → 0) |
| 1947 | `worker/models/punct-en/sherpa_onnx/offline_recognizer.py` | vendored package, **git-ignored** |
| 1669 | `worker/models/.sotto-runtime/.../builders/qwen.py` | vendored runtime, **git-ignored** |
| 4512 | `worker/_prefix_audioflag.py` | **tracked mutant fixture** (deliberate RED arm; must not be deleted) |
| 2562 | `worker/_sotto_worker_agcinert.py` | **tracked mutant fixture** (same) |

`git ls-files worker/models/` returns **0 entries** — that tree is a model store,
not source.

## 3. Measured population split

Run of the census rule over the declared scope:

```
PRODUCTION monoliths: 11
NON-PRODUCTION:        5
```

## 4. What correcting it buys — the arithmetic, not a guess

`exocortex/revival_engine.py:425-432`:

```python
mono_pct  = mono_cnt * 100.0 / scanned_files
arch = 100 - min(40, int(mono_pct * 4.5 + min(mono_cnt, 10) * 1.5))
```

| monoliths | arch score |
|---:|---:|
| 16 (today, as counted) | 60 |
| 15 | **60** |
| 13 | **60** |
| 12 | 61 |
| 11 (correct production count) | 63 |
| 9 | 69 |
| 6 | 79 |
| 5 | 83 |
| 3 | **90** |

**A corrected census moves 60 → 63.** The 30-point gap needs the count at **3 or
fewer**: a nine-file split campaign (`sotto_webview.py` 28 395,
`sotto_worker.py` 10 230, `panel.js` 4 897, `redux_live.py` 4 381, plus the
2 500-line app-layer and worker files).

## 5. Why it is not fixed in this commit

- `exocortex/` and `codeintel/` belong to the installed codeintel tree
  (`H:/codeintel-worktrees/triad-milestones-20261105`), which is **not this
  repo**, carries **2 209 dirty files**, and is not an owner checkout of mine.
  Editing another project's measurable code to move my number is exactly the
  metric-gaming the repo law forbids.
- The honest route is the one the project already owns: `.codeintel/skip.json`
  (or `CODEINTEL_SKIP_DIRS`) — **but `panorama.py` never reads it**, so the
  route only works after the same foreign-tree edit.

**Reported to the seat that owns the instrument. Not papered over here.**

## 6. The 11 real monoliths (the campaign, if a seat takes it)

```
28395  app/webview/sotto_webview.py
10230  worker/sotto_worker.py
 4897  app/panel/panel.js
 4381  worker/redux_live.py
 2550  app/webview/youtube_captions.py
 2549  app/webview/youtube_cdp_source.py
 2181  app/webview/caption_overlay.py
 1993  worker/speaker_sidecar.py
 1793  worker/engine_switch.py
 1626  app/webview/warm_engine.py
 1625  worker/wasapi_loopback.py
```

`revival/SPLIT-PLAN.md` already names 8 slices with their oracle owners. The
last two files (`warm_engine`, `wasapi_loopback`) are 125 lines from the
threshold each and are the cheapest two.
