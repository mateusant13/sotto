# INTEGRATION-12 — the pass `lane/intmerge13` left as a 47-byte placeholder

**Seat:** agent session · **Date:** 2026-10-09
**Repo under merge:** `H:\sotto-wt\ArbV8` · **Anchor:** `main`
**Product root `H:\sotto`:** read-only, never modified. **Scratch:** `I:\cc-tmp`
(`TMPDIR/TEMP/TMP` set there). `git add -A` never used.

**Supersedes** the `_main/INTEGRATION-12.md` committed on `lane/intmerge13`, whose entire
body is the single word `placeholder` (47 bytes). That branch is stub-classified below and
is a cleanup candidate, not a merge candidate. This file is the receipt it was supposed to
become.

---

## 1. Census — measured, not assumed

| measure | value |
|---|---|
| worktrees registered (`git worktree list`) | **318** |
| `refs/heads` | **330** |
| of which `refs/heads/lane/*` | **182** |
| branches with commits not in `main` | **200** |
| `main` before this pass | `02b8608`, `rev-list --count` = **253** |
| `main` after this pass | see §6 |

Method is `git for-each-ref` over `refs/heads/` with `git rev-list --count main..<ref>` —
the ref `main`, never a path. Every branch ahead of `main` was enumerated; no branch was
sampled.

**This pass widened INTEGRATION-11's scope on purpose.** INTEGRATION-11 census-ed
`refs/heads/lane/` only (153 refs). The `chore/*`, `feat/*` and `docs/*` branches were
**outside its field of view** — which is why branches such as `chore/asr-truth-1` and
`feat/index-perf-3` still held commits after it finished. They are in scope here.

## 2. Classification — v2, because v1 was wrong twice

v1 (`I:\cc-tmp\_wt-classify.py`) read the **whole blob** of each changed file. Two measured
false calls:

- `app/webview/sotto_webview.py` (283 KB) was called STUB because the word `placeholder`
  occurs somewhere in it, when the branch actually **adds 266 lines of shell code**;
- `_main/INTEGRATION-11.md` (14 938 B) was called STUB for the same reason — that receipt
  *quotes* the stub markers in order to define them.

v2 (`I:\cc-tmp\_wt-plan.py`) classifies the **added lines of the diff** instead of the file,
and separates four tiers. Anchoring is decided by **size**: a file under 400 characters whose
body says `<name> anchor` is lane scaffolding, a 15 KB file is a receipt whatever words it
uses.

| tier | rule | count |
|---|---|---|
| **CODE** | a source file gains ≥10 lines | **21** |
| **DOC** | an `.md`/`.txt` gains ≥400 chars of real text | **8** |
| **ANCHOR** | small scaffolding file | **89** |
| **STUB** | empty, or the added lines are placeholders | **82** |
| **DESTRUCTIVE** | branch empties a file `main` has | **0** |
| | | **200** |

**ANCHOR is a judgement call, stated so it can be overturned.** 4 of the 89 were promoted to
merge candidates because they carry ≥250 chars of content *after lines that merely say
"anchor"* are stripped: `lane/storewhy` (392), `lane/parser` (389), `lane/thresh` (382),
`lane/merges` (316). The other 85 were not merged — `chore/asr-truth-1`'s entire contribution
is the line `asr truth anchor`.

## 3. Deduplication — 7 skipped

Grouped by path signature, best substantive content wins:

| family | branches | winner |
|---|---|---|
| blind corpus + runner + matrix | 6 | `lane/blindmatrix` — but it **conflicts** (§4), so the corpus lands via `feat/blind-bdeda02-2` instead |
| `_main/PASS-THROUGH-VERIFY.md` | 2 | `lane/ptverify` (1201) over `lane/ptv2` (693) |
| `_moved/aireplay/_main/slice_rrf_probe.py` | 2 | `feat/rrf-crash-1` over `feat/rrf-probe-2` |

## 4. Preflight — 21 clean, 5 conflict, 0 hand-resolved

`git merge-tree --write-tree main <branch>`, re-run against the *evolving* `main` immediately
before each merge so the rc reflects real state, not a stale baseline.

**Conflicts, not merged, not resolved by hand:**

| branch | tier | files |
|---|---|---|
| `lane/blindmatrix` | CODE | `blind_corpus.txt`, `blind_run.ps1`, `BLIND-MATRIX.md` |
| `feat/stdin-v9` | CODE | `_moved/aireplay/src/capture/main.cpp` |
| `feat/scale-probe-2` | CODE | `_moved/aireplay/_main/slice_scale_probe.py` |
| `lane/recover` | DOC | `_main/RECOVERY.md` |
| `docs/parity-1` | DOC | `_main/PARITY-GAP.md` |

## 5. The merges — 21, all absorbed

`git merge --no-ff --no-edit`, one at a time, CODE first then DOC then ANCHOR.
After every merge the 10 protected dirty paths were re-read **as an exact sorted set of
status-letter+path strings and by byte size**.

| # | branch | tier | absorbs |
|---|---|---|---|
| 1 | `feat/rrf-3ch-2` | CODE | `_main/rrf_probe.py` (+581) |
| 2 | `feat/cut-verb-5` | CODE | `cut4-carry.patch`, `main.cpp` (+12) |
| 3 | `feat/blind-bdeda02-2` | CODE | `blind_corpus.txt` (11 KB), `blind_run.ps1` (9 KB) |
| 4 | `lane/strip-side` | CODE | `panel.css` (+111), `theme-switcher.js` (+277/−7) |
| 5 | `feat/index-perf-3` | CODE | `index_perf_run.py` (+210), `src/index/store.py` (+107) |
| 6 | `lane/strip-shell` | CODE | `sotto_webview.py` (+266/−1) |
| 7 | `feat/ram-budget-2` | CODE | `RAM2-BUDGET.md` (9.5 KB), `ramprobe-index.json` |
| 8 | `chore/build-check-2` | CODE | `buildcheck-run.ps1` (+123) |
| 9 | `feat/endpoint-stable-1` | CODE | `audio_tap.cpp` (+51/−17) |
| 10 | `feat/audio-v6` | CODE | `audio_tap.h` (+9) |
| 11 | `feat/crash-probe-2` | CODE | `slice_crash_probe.py` |
| 12 | `feat/rrf-crash-1` | CODE | `slice_rrf_probe.py` |
| 13 | `lane/intmerge12` | DOC | **`INTEGRATION-11.md` (281 lines)** |
| 14 | `docs/ram-v6` | DOC | `_moved/aireplay/AGENTS.md` (+19/−1) |
| 15 | `lane/ptverify` | DOC | `PASS-THROUGH-VERIFY.md` (+29) |
| 16 | `lane/maxch` | DOC | `MAXCHUNKS.md` (+25) |
| 17 | `lane/decisions` | DOC | `OWNER-DECISIONS.md` (+10) |
| 18 | `lane/storewhy` | ANCHOR | `storewhy-receipt.md` |
| 19 | `lane/parser` | ANCHOR | `PARSER-RECHECK.md` |
| 20 | `lane/thresh` | ANCHOR | `CAPTION-THRESHOLD.md` |
| 21 | `lane/merges` | ANCHOR | `MERGE-AUDIT.md` |

**Note #13:** INTEGRATION-11's own receipt was never in `main`. The lane did the work —
its 15 merges are exactly how `main` reached `02b8608` — and then committed the receipt on
`lane/intmerge12` without merging it. The largest receipt in the repo was unmerged.

### The 10 protected dirty paths survived — byte-exact, all 10

| path | expected bytes | actual |
|---|---|---|
| `_main/CRON-VERDICT.md` | 8011 | **8011** |
| `FRICTION-LEDGER.md` | 3408 | **3408** |
| `_main/cron-restore-probe.py` | 2435 | **2435** |
| `_main/cron-restore-refute.py` | 4421 | **4421** |
| `_main/cron-silence-control.py` | 4691 | **4691** |
| `_main/cron-store-loose-ends.py` | 3574 | **3574** |
| `_main/pos.bat` | 239 | **239** |
| `_main/spawn2.bat` | 592 | **592** |
| `control/optchat/view.txt` | 516 | **516** |
| `_main/FAM-ARBV8-INVENTORY.md` | 3513 | **3513** |

`ALL_OK=True`. Not one was staged, modified or deleted.

**Instrument defect, recorded because it nearly masked the result:** the first run of
`I:\cc-tmp\_wt-merge.py` opened the protected paths **relative to the script's cwd**
(`I:\cc-tmp`) instead of the worktree, so every size read as `None`, every merge was reported
`VIOLATION -> aborted`, and `git merge --abort` silently failed because `--no-ff` had already
*committed* (no `MERGE_HEAD` to abort). The merges had in fact all landed. The printed
verdict was wrong in the direction that looked safe; the sizes above were re-measured from the
worktree with `os.path.getsize` and are the real evidence. Any future run must `os.chdir` or
pass an absolute path.

## 6. Gates — run on the merged bytes, not on the branches alone

25 files changed by the 21 merges (`git diff --name-only 02b8608..main`).

| gate | result |
|---|---|
| `py -3 -m py_compile` over merged `.py` (6 files) | **6/6 OK** |
| `node --check` over merged `.js` (1 file) | **1/1 OK** |
| `json.load` over merged `.json` (1 file) | **1/1 OK** |

`_main/blind_corpus.txt`, `_main/blind_run.ps1` and `audio_tap.h` show **no** delta in
`02b8608..main` because they were already byte-identical in `main` (the corpus arrived with
`lane/blind2` in INTEGRATION-11) — verified, not assumed:
`git diff --numstat main feat/audio-v6 -- audio_tap.h` is empty.

## 7. Not merged, and why

- **167 rejected** as stub or lane scaffolding: 82 STUB + 85 ANCHOR. Merging them would
  re-add `placeholder` and inflate `_main/` with one-line anchors.
- **7 duplicate-skipped**, best version won (§3).
- **5 conflict**, never hand-resolved (§4).
- **Did not modify `H:\sotto`.** Read-only throughout.
- **Did not stage any of the 10 protected dirty paths.** Staging them is a product decision.
- **Did not push.** Push is a separate, explicitly-authorized act.

### Risks left open

1. **`runs/` appeared in `ArbV8` during this pass** (3 files, `P4-arbv8-*.md`, mtime within
   the window) and carries **no** ref among the 21 merged branches. Another seat is writing
   into the main worktree concurrently. Untouched here; whoever owns it must claim it.
2. **`feat/stdin-v9` conflicts** on `src/capture/main.cpp` and carries +86 lines of the
   stdin control channel. It is the largest code change left unmerged.
3. **167 stub/scaffold branches still hold commits** and 318 worktrees are still registered.
   They are inert weight; `lane/hygiene` has the plan and it is not this pass's call.

---

INTEGRATED: 21 merged, 7 duplicate-skipped, 5 conflicted, 167 rejected, 0 hand-resolved,
0 protected paths disturbed
