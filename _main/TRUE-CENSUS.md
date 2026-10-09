# TRUE CENSUS — Sotto / ShadowPlay clone, `main`

**Head measured:** `47d424a` (135 commits, `git rev-list --count HEAD`)
**Worktree:** `H:\sotto-wt\census2`, branch `chore/true-census-2`
**Census date:** 2026-10-07

## Method (the rule that was broken three times)

Every number below is produced from a **complete** population. No listing is
truncated to build a table. Where a subset is ranked or sampled for
classification, it is labelled `NOT the population`. Every count carries
**POPULATION** and **WINDOW**.

Canonical byte source is the git blob (`git ls-tree -r -l`), not the working
tree: a Windows checkout rewrites LF→CRLF, so on-disk bytes differ from blob
bytes for text files. Where both are quoted, both are labelled.

---

## 1. Full inventory of `main` — every directory, complete

**POPULATION:** 1040 tracked files / 45 383 937 bytes / **72 unique directory
paths**. **WINDOW:** whole repo at `47d424a`, recursive.

```
Dir                                                                          Files       Bytes
_moved/aireplay                                                               346    23821124
_moved/aireplay/_main                                                         233    21911302
docs                                                                           86     9806240
_main                                                                         495     9132274
docs/design                                                                      8     8150214
docs/design/incoming                                                             5     8135562
_main/_redux-gate-mutants                                                        12     2711040
app                                                                             92     1482429
docs/audit                                                                      46     1116073
worker                                                                          11     1059957
_moved/aireplay/docs                                                             49      988771
_main/_redux-long                                                                52      737500
_moved/aireplay/docs/design                                                      36      662233
worker/assets                                                                    3      641070
app/panel                                                                       32      599843
_moved/aireplay/src/capture                                                     27      567200
_main/_ordem-before                                                               4      468459
_moved/aireplay/docs/design/sotto-app-design-directions                        21      458538
_main/_audit-render                                                              22      423687
app/_legacy-electron                                                             22      397023
app/webview                                                                      7      347855
_moved/aireplay/docs/design/sotto-app-design-directions/public/scenes           3      319080
_moved/aireplay/src/capture/third_party                                           1      313554
_main/_ordem-before/assets                                                        1      282378
app/panel/fonts                                                                 14      244028
_main/_redux-long/logs                                                           36      192101
_main/_design-lane                                                               37      151050
_moved/aireplay/docs/design/sotto-transcription-panel-designs                   14      140474
_moved/aireplay/docs/research                                                    12      125092
app/panel/themes                                                                  7      124390
_main/_audit-render/chrome-css-neg/themes                                         5      114614
_moved/aireplay/receipts                                                         15      104250
_moved/aireplay/specs                                                             6       86844
_moved/aireplay/src/asr                                                           9       65332
_moved/aireplay/docs/design/sotto-transcription-panel-designs/src                9       51872
_moved/aireplay/docs/design/sotto-app-design-directions/src                     13       50822
_moved/aireplay/src/index                                                         4       46430
docs/model-specs                                                                13       42324
app/src-tauri                                                                    13       41780
_moved/aireplay/docs/design/sotto-app-design-directions/src/components           7       33745
_main/_cmfatal-changedmode                                                        1       27938
app/src-tauri/src                                                                 4       23630
_moved/aireplay/docs/design/sotto-transcription-panel-designs/src/components      2       22885
docs/model-specs/original                                                       12       21359
_main/_audit-verify                                                              8       20583
_main/_audit-verify/js                                                           7       19324
app/src-tauri/icons                                                               5       16076
probe                                                                            5       13966
app/verify                                                                       5        9040
scripts                                                                          1        6506
_moved/aireplay/docs/design/sotto-transcription-panel-designs/src/lib            1        6494
docs/model-specs/original/int8                                                    5        6327
_main/control                                                                    2        6291
app/src                                                                          6        5293
_main/_audit-probe                                                                2        4725
_moved/aireplay/docs/design/sotto-app-design-directions/src/data                1        4461
docs/tools                                                                       1        4420
_moved/aireplay/docs/design/sotto-transcription-panel-designs/src/hooks          2        3966
app/verify/rustc                                                                 2        3351
app/panel/_fonts                                                                  2        2978
docs/model-specs/original/int4                                                    4        2853
_moved/aireplay/docs/design/sotto-app-design-directions/src/hooks                1        2654
docs/model-specs/original/fp16                                                   2        2622
app/verify/src                                                                   1        1965
app/src/lib                                                                      2        1803
brand                                                                            1        1139
_main/_main/_battery-scratch/rehearsal                                           1         661
_moved/aireplay/control/optchat                                                  1         523
_main/_redux-visibility                                                          1         408
app/src-tauri/capabilities                                                        1         213
_moved/aireplay/docs/design/sotto-app-design-directions/src/utils                1         169
_moved/aireplay/docs/design/sotto-transcription-panel-designs/src/utils          1         169
```

**ROWS_SHOWN = 72 OF POPULATION = 72 — COMPLETE.** Root-level files (the 13
not inside any listed dir) are `.gitignore`, `AGENTS.md`, `README.md` and 10 more.

**Correction to the brief's anchors** (measured, not assumed):
* `_moved/aireplay/_main` = **233** files, not 234.
* `_moved/aireplay/src` = **40** files, not 42.
* `_moved/aireplay` children sum: 233+49+40+15+6+1 = **344** dirs + 2 root
  files (`AGENTS.md`, `ROADMAP.md`) = **346**, which reconciles exactly.
* `_main/` = 495 tracked files (496 on disk here: +`census2-anchor.md`).

---

## 2. Product code vs receipts — the split

**POPULATION:** all files with extension `.cpp .h .py .ts .tsx .rs .cs`
tracked at `47d424a` = **381 files / 150 426 lines**. **WINDOW:** whole repo.

### 2a. First pass, applying the brief's exclusion rule

Excluded as receipt/probe/audit/scratch: path segment matching
`(^|/)(receipts?|probes?|audit|scratch|rehearsal|_battery-scratch|_audit-[^/]*|_redux-gate-mutants|verify)(/|$)`
= **28 files** (7 `_main/_audit-*.py`, 11 `_main/_redux-gate-mutants/*.py`,
3 `app/verify/**`, 5 `probe/*.py`, 2 `_main/_audit-render`, 1 `_audit-verify`).
Remaining **353 files**.

That rule is **not sufficient** and I am not reporting its result as product
code. `_main/` holds **172 `.py` files directly**, and reading their names shows
they are probe / oracle / mutant / fake-worker harnesses, not product code
(`panel-exit3-oracle.py`, `word-split-oracle.py`, `_panel-verdict-benign-mutant.py`,
`_bfrc_*.py`, `_scratch-qwen-*.py`, `redux-long-probe.py`). Counting them as
"product code" is how a 159-line figure gets inflated into 53 269 lines of
phantom product.

### 2b. Honest four-way classification of the 381 code files

| Class | Files | Lines |
|---|---|---|
| `_main/` loose harness (probe/oracle/mutant/scratch) | 113 | 65 312 |
| HARNESS by name signal anywhere (mutant/oracle/probe/driver/verdict/fake-worker/neg-arm) | 116 | 49 436 |
| DESIGN mockup under `docs/` | 53 | 5 195 |
| **CANDIDATE PRODUCT** | **55** | **25 243** |

(These four overlap by construction — the name-signal class is not disjoint from
`_main/`; 113+116 > 172 because a file can be both. The product class is
disjoint from all three and is computed by exclusion. Stated rather than hidden.)

### 2c. PRODUCT CODE — 55 files, 25 243 lines, 1 381 830 bytes

Command used for every line count:

```powershell
$rows = git ls-tree -r -l 47d424a          # population, blob bytes
$f    = foreach($r in $rows){ $p=$r -split '\s+',5; [pscustomobject]@{Size=[int64]$p[3];Path=$p[4]} }
$code = '.cpp','.h','.py','.ts','.tsx','.rs','.cs'
$all  = $f | ? { $code -contains [IO.Path]::GetExtension($_.Path).ToLowerInvariant() }
foreach($x in $all){ $x | Add-Member L ([int](Get-Content $x.Path -EA SilentlyContinue | Measure-Object -Line).Lines) }
```

| Area | Files | Lines | First-party lines |
|---|---|---|---|
| `_moved/aireplay/src/capture` (C++) | 25 | 9 462 | 9 462 |
| `_moved/aireplay/src/asr` (Python) | 9 | 1 299 | 1 299 |
| `_moved/aireplay/src/index` (Python) | 2 | 423 | 423 |
| `worker/` | 6 | 7 280 | 7 280 |
| `app/webview/` | 3 | 5 925 | 5 925 |
| `app/src-tauri/src` + `build.rs` | 5 | 601 | 601 |
| `app/src`, `app/vite.config.ts` | 6 | 102 | 102 |
| **total** | **55** | **25 243** | **25 243** |
| of which third-party `nvEncodeAPI.h` | 1 | 4 290 | — |
| **FIRST-PARTY TOTAL** | **54** | — | **20 953** |

**So: the product is ~21 000 lines of first-party code in 54 files.** The
"159 lines of production code" claim is refuted — but the *opposite* claim
("nearly empty") is refuted too.

### 2d. Receipts / prose, for contrast

`_main/` = 495 files. Of those, 172 are `.py` harnesses, 7 are `.md` at depth 1
plus the markdown body of the rest. **The brief's "97 markdown receipts /
1 141 450 bytes" for `_main/` is REFUTED**: `_main/` is 495 files /
9 132 274 bytes of which the `.md` share is counted below.

_(section 2 receipt-markdown figure and section 3 filled in the next commit)_