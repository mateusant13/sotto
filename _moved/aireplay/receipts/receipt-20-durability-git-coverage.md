# Receipt 20 — durability: can a bad day still destroy this product?

**Lane 20 · snapshot 2026-10-07 12:37:15 -03:00 · WINDOW 20 min (in-flight rule)**
**POPULATION 1499 files** (excludes `node_modules/`, `__pycache__/`, `.git/`, `*.pyc`,
`_main/_durability-scratch/`)
**Gate:** `_main/durability-gate.ps1` — three phases, all runnable, all with exit codes.
**Verdict: FAIL.** Not because the product is gone, but because a `git clean -fd` in the
parent repo would still take **92 tracked-worthy paths**. Details below.

---

## 0. What this receipt is, and the one thing it is not

It is **not** a claim that "the tree is clean". It is a claim about a specific
destructive operation, measured against git itself:

> If somebody today runs `git clean -fd` in `H:\sotto`, which files of the product die?

The answer is produced by asking git (`git clean -nd`, a dry run that removes nothing)
and classifying the answer. Everything below is a count with a population and a window
attached, per lane rule 6.

**Gate invocation** (no wrapper, native paths, no pipes to native commands):

```
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\durability-gate.ps1              # exit 1 = FAIL
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\durability-gate.ps1 -SelfTest    # exit 0 = both colours proven
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\durability-gate.ps1 -RollbackProof  # exit 0 = 17/17
```

| phase | what it proves | exit | result |
|---|---|---|---|
| default | coverage + clean simulation | **1** | FAIL, 1 finding |
| `-SelfTest` | the classifier can go **red** | 0 | CLEAN arm PASS, STALE arm PASS |
| `-RollbackProof` | three rollbacks executed in scratch | 0 | 17 pass / 0 fail |

---

## 1. THE HEADLINE — the `a66da94` fix has already decayed, and a second repo appeared

This is the part that matters and it is new. Two things happened while this lane ran.

### 1.1 A nested `git init` landed inside the product, mid-lane

Measured timeline, all on this box:

| time | event | evidence |
|---|---|---|
| 11:40:34 | `a66da94` "durability: track the moved ShadowPlay clone" — 330 paths tracked in the parent | `git log -1 a66da94` |
| **12:14:0x** | `Test-Path H:\sotto\_moved\aireplay\.git` → **False**; the project had **no repo of its own** and lived entirely in `H:\sotto`'s index | measured before any write |
| **12:15:26** | `_moved\aireplay\.git` **created** (CreationTime), `H:\sotto\_moved\aireplay\.git` | `Get-Item .git -Force` |
| 12:23 → 12:36 | that repo commits repeatedly (`bae4e1e` → `22c3e422` → `d96a5a1c`) | `git log` |

So the brief's statement that `_moved/aireplay` "is a git repo" **was false at the start
of this lane** and is now true for a reason nobody chose: a lane ran `git init` in the
product root. The parent's 330 tracked paths are intact and the parent reports **no
deletions** — but two indexes now claim the same files.

### 1.2 The nested repo does NOT protect the files from the parent's `git clean`

This is the finding the whole lane exists for, and it is the opposite of the intuitive
reading. At snapshot 12:37:15:

```
git clean -nd -- ./_moved/aireplay      rc=0, would remove 214 paths
   of those TRACKED-WORTHY            92
     excused as in-flight              20
     AT RISK                           72
        of which LOST (no repo tracks)  0
        of which RECOVERABLE           72   (a nested repo tracks them)
```

**72 tracked-worthy paths would be deleted from the working tree by a parent
`git clean -fd`, even though every one of them is committed in the nested repo.**
`git clean` consults the index of the repo you ran it in. A nested `.git` is invisible to
that decision. So the nested repo is a **mitigation, not a fix** — the bytes survive, the
working files do not.

### 1.3 What it looked like BEFORE the nested repo existed (measured 12:14 and 12:20)

This is the decay of `a66da94`, and it is the number that should worry the owner. With
only the parent's index, `git clean -fd` would have taken, 54 paths later (12:20):

```
_moved/aireplay/src/capture/trigger.cpp          <- SOURCE
_moved/aireplay/src/capture/trigger.h            <- SOURCE
_moved/aireplay/src/capture/trigger_selftest.h   <- SOURCE
_moved/aireplay/src/engine/                      <- SOURCE, whole dir
_moved/aireplay/src/ui/                         <- SOURCE, whole dir
_moved/aireplay/src/index/                      <- whole dir
_moved/aireplay/receipts/receipt-03-capture-impl.md
_moved/aireplay/receipts/receipt-15-offline-cut-pass1147.md
_moved/aireplay/docs/design-notes/              <- whole dir
```

**The fix had held for 30 minutes and the product was already outside the parent's
index again.** Six of these predate `a66da94` (mtimes 10:20–10:52, i.e. they were written
*before* the tracking commit and missed by it); the rest arrived after it. `a66da94` was
a point-in-time sweep, not a standing rule — which is exactly the gap this gate closes.

---

## 2. Coverage by class — TRACKED vs UNTRACKED vs IGNORED, with POPULATION and WINDOW

Four states, because durability is **per-repo** and a single boolean would have hidden 1.1:

| state | meaning | survives `git clean -fd` in the parent? |
|---|---|---|
| `TRACKED` | the **parent** `H:\sotto` tracks it | **yes — the only fully safe state** |
| `NESTED-ONLY` | a nested repo tracks it, the parent does not | **no** — working file deleted, recoverable from the nested repo |
| `UNTRACKED` | no repo on this box tracks it | no, and **nothing can restore it** |
| `IGNORED` | every repo that sees it ignores it | yes |

`IGNORED` is derived **by subtraction** from `git ls-files` and
`git ls-files -o --exclude-standard`, so git's own ignore engine is the source of truth —
there is no second list of ignores inside the gate that could drift from `.gitignore`.

```
 CLASS          WHAT IT IS                    POP   TRACKED NESTED-ONLY  UNTRACK IGNORED  STALE IN-FLIGHT
 src-source     src/ source code               49        33         16        0       0      0        0
 specs          specs/                          6         3          2        1       0      0        1
 receipts       receipts/ evidence             21        15          3        3       0      0        3
 research       research/                       2         0          0        2       0      0        2
 docs           docs/ design + notes           47        44          3        0       0      0        0
 root-doc       root AGENTS/ROADMAP             2         2          0        0       0      0        0
 main-code      _main/ probes + gates         301        92        113       65      31      0       65
 main-evidence  _main/ run captures           876       133        528      184      31      0        0
 main-media     _main/ media + indexes         96         0          1        0      95      0        0
 control        control/                        1         1          0        0       0      0        0
 models         models/ weights                13         0          0        0      13      0        0
 UNCLASSIFIED   claimed by no class            85         7         62       10       6      -        -
 TOTAL                                                    330        728      265     176      0       71
```

**HOLES (tracked by NO repo, critical, older than the window): 0.**
**IN-FLIGHT (excused, printed anyway): 71.** Window = 20 min, rule below.

### The in-flight rule — stated so it can be argued with, not hand-picked

A tracked-worthy file is excused iff **all** of:

1. it is TRACKED-WORTHY by its class;
2. no repo tracks it and no ignore rule covers it;
3. `mtime > now − 20 min` ← **the WINDOW**, printed on every run;
4. `mtime >` the **parent** repo's HEAD commit time (`d6257ec2`, 11:53:24).

Rule 3 alone is a timer a slow lane can outlive. Rule 4 alone exempts every file written
after the last commit, forever. Together a file must be recent *and* newer than HEAD.
**Nothing is dropped silently** — all 71 excused files are printed by name. Re-run after
a lane dies and they become HOLES.

Rule 4 is anchored to the **parent** HEAD on purpose. Anchoring to the newest HEAD of any
repo found here produced **3 false holes** in an earlier revision: the nested repo
committed at 12:23:02, which is newer than several files of a lane demonstrably still
writing. That is recorded here because it is the transferable part — a rule that looks
stricter is not stricter.

### UNCLASSIFIED — 85 files no class claims

These are protected by nothing the gate defines, and the gate says so rather than
quietly passing them. Sample: `.gitignore`, `docs/brief-pesquisarsobre.txt`,
`docs/design/*/public/scenes/{deep,noir,stage}.jpg`, `_main/_rapidocr-override.yaml`,
`_main/_index-ann.pid`, `_main/heartbeat-run-*.md.stderr`. **Actable:** add a
`research/`-style class for design assets, or an explicit non-critical class for
`.pid`/`.yaml`/`.stderr` captures.

---

## 3. Rollbacks — three destructive operations, each executed in a scratch copy

Scratch: `H:\sotto\_moved\aireplay\_main\_durability-scratch\rollback-<timestamp>\`
(written and **moved** only; the single deletion performed is a `git clean` inside the
throwaway scratch repo — the operation under test). The real tree is never touched.

### R1 — the move `H:\aireplay` → `H:\sotto\_moved\aireplay`

**Rollback:** `Move-Item -LiteralPath H:\sotto\_moved\aireplay -Destination H:\aireplay`
(after removing the junction — a junction is not a valid move destination).

Executed: 3 files, `Move-Item` out then `Move-Item` back, sha256 compared before and after.
**3/3 sha256 restored, 3/3 files present. PROVEN.**

### R2 — the junction `H:\aireplay` → `H:\sotto\_moved\aireplay`

**Rollback:** `New-Item -ItemType Junction -Path 'H:\aireplay' -Target 'H:\sotto\_moved\aireplay'`

Executed in scratch: junction created, verified to be a reparse point, verified to
resolve to **identical bytes** (sha256 `0685B73C…`), `git rev-parse --show-toplevel`
through the link rc=0, and the target readable without going through the link.
**PROVEN (creation).**

> **NOT EXECUTED — disclosed.** Removing the real junction was not attempted: this
> environment blocks deletions issued from the shell, and the brief forbids bypassing that
> block. So *"deleting the link leaves the target intact"* is **reasoned, not executed**. It
> is sound because a junction stores no bytes of its own — the target is the real directory
> and stays fully readable — but it is the one claim in this receipt without an
> execution receipt, and it is named rather than buried.

### R3 — `git clean`

| what | rollback | proof |
|---|---|---|
| a **tracked** file | `git checkout HEAD -- <path>` | **PROVEN**, rc=0, bytes restored after `git rm` |
| an **untracked** file | **there is none** | **PROVEN negative**: `git checkout -- untracked.txt` → **rc=1** (pathspec does not match); `git fsck --unreachable` → rc=0, **0** dangling commits; the bytes are simply gone |
| anything untracked | copy the tree **outside** the repo first | **PROVEN**: external copy survived a second `git clean`, sha256 `02E6D3DA…` identical |

**This is the load-bearing result of the whole lane.** `git clean` is *exactly* the
operation with no in-git undo, which is why the coverage gate is not hygiene — it is the
only thing standing between a routine command and permanent loss.

**`ROLLBACK VERDICT: 17 pass / 0 fail`** — and **17/17 on two consecutive runs**. The
first draft was 16/17 on its second run because the scratch directory persisted and
`Move-Item` nested instead of renaming; each run now gets a fresh timestamped scratch dir.
A proof that only works the first time is not a proof.

---

## 4. The junction — what it covers, what it does not, what breaks

**Measured at 12:37:15** (live, not reconstructed):

```
exists=True   reparse-point=True   target=H:\sotto\_moved\aireplay
resolves for file IO = True        git works through it = True
sha256 via junction = D90E7BC283E6367D66D9E6C84FCD8A6E7A86B115A1EA10AEAE1B210CA7A466FD
sha256 direct      = D90E7BC283E6367D66D9E6C84FCD8A6E7A86B115A1EA10AEAE1B210CA7A466FD
SAME CONTENT THROUGH BOTH PATHS = True
```

It is a real junction, it resolves, and it is byte-identical to the direct path.
`git -C H:/aireplay rev-parse --show-toplevel` → `H:/sotto/_moved/aireplay`, rc=0, so
**git works through it and the path does not confuse it.**

**What it does NOT cover — measured, not guessed:**

- It is **one name for one tree**. It does not carry history: the git objects live in
  `H:\sotto\.git` (parent) and `H:\sotto\_moved\aireplay\.git` (nested). A path that
  walks *past* the link — `H:\aireplay\..` — leaves the project and is **not** covered by
  it; anything the receipts cite above the root resolves to `H:\` and is meaningless.
- It does **not** protect against the parent's `git clean` (§1.2) and it did **not**
  protect the tree from being outside the index for the first 30 minutes after `a66da94`
  (§1.3). The junction is an alias, not a backup.
- Anything created *outside* the target (e.g. `H:\aireplay-cache\`) is not reachable
  through it.

**What breaks if it is removed — measured:** **288 lines across 124 files** under the
project cite `H:\aireplay` / `H:/aireplay`. The densest: `_main/panel-temas-manifest.json`
(40), `_main/render-panel-temas.py` (13), `_main/onnx-asr-profile.json` (10),
`_main/census09-enum-H.json` (9), `receipts/receipt-render-panel-temas.md` (7),
`receipts/receipt-preview-designs.md` (6), `src/capture/run_battery.ps1` (5). Every one of
those citations becomes a dead reference. The product itself is **unaffected** — it lives
at the real path. **Verdict: keep it; it costs nothing and 124 files depend on it.**

---

## 5. Large untracked artefacts — and the right treatment for each

| size | path | current state | right treatment |
|---|---|---|---|
| 622,0 MB | `models/parakeet-tdt-0.6b-v3-onnx/encoder-model.int8.onnx` | IGNORED | **IGNORE, keep it ignored** — re-downloadable from `istupakov/parakeet-tdt-0.6b-v3-onnx`, rev `8f23f0c0`. Never tracked: a single 622 MB blob in an index is how the 2 GB push was refused before. |
| 1 050,1 MB | `_main/_index-store/index.db` | IGNORED | **IGNORE** — a measurement, rebuilt by `_main\_index-*-probe.py`; the measured *result* belongs in a receipt, which is tracked. |
| 1 044,0 MB | `_main/_index-store2/C_partition_video.db` | IGNORED | **IGNORE** — same. |
| 281,8 MB | `_main/_import-bench/synth-180s-1080p30.mp4` | IGNORED | **IGNORE**, or externalise a synthetic fixture to a capture dir. It is generated content, not captured owner footage. |
| 5 × 158,0 MB | `_main/logs/_remux-{A..E}-*.mp4` | IGNORED | **IGNORE** — derived remuxes of the owner's screen recording; private by the same argument the nested `.gitignore` already states. |
| 158,0 MB / 157,9 / 150,9 / 142,8 … | `_main/runs/clip-20261007-*.mp4` (45 clips) | IGNORED | **IGNORE** — run captures. |
| 134,8 MB | `_main/_index-ann/hnsw.faiss` | IGNORED | **IGNORE** — serialised index, rebuildable. |

**Rule of thumb this table encodes:** *weights and captures are externalised and ignored
with a stated reason; measurements live in receipts, not in the database that produced
them.* Total ignored-and-large in the project is ~5.9 GB, all of it in
`_main/_main/runs|logs|_index-*` and `models/` — i.e. the ignore rules are doing their
job. **No large file is a hole.** Nothing here needs tracking, and nothing here needs a
new ignore rule.

---

## 6. What the gate does NOT do, and why

- **It does not stage, commit, or fix anything.** No `.gitignore` was edited to make a
  check pass. No other lane's in-flight work was committed. The verdict is a report.
- **It does not resolve the nested-repo question.** Whether `_moved/aireplay` should be
  its own repo is an owner's decision with two honest answers (§7), not a lane's.
- **It cannot see work that exists only in a lane's memory**, in an uncommitted editor
  buffer, or in a scratch dir outside the project root.
- **Its verdict is pinned to a moment.** The tree gained 3 tracked-worthy source files
  *while this gate ran*. Every run prints its snapshot time and both HEAD shas; re-run
  before acting on a number.
- **The junction-removal property is reasoned, not executed** (§R2).

---

## 7. THE DECISION THIS RECEIPT OWNS UP TO (owner, not lane)

`git clean -fd` would take 92 tracked-worthy paths today. Two honest fixes:

- **(i) Fold the nested repo's index into the parent** — `git -C H:\sotto\_moved\aireplay
  fetch` the objects into `H:\sotto` and `git add` the subtree in the **parent**, then
  decide what to do with `_moved/aireplay/.git`. One repo, one `clean`, one answer.
  Cost: one large commit; the nested repo's 728-only paths enter the parent index.
- **(ii) Keep the nested repo and accept that two `git clean`s exist** — then the parent
  must never be cleaned, which is a rule, not a guarantee.

**(i) is the recommendation.** Until one of them is chosen, the correct operational rule
is: **do not run `git clean -fd` in `H:\sotto`.** It is the one command on this box with
no undo for untracked files, and it currently has 92 tracked-worthy targets.

---

## 8. Drift measured while this lane ran — the window is a timer, not a pardon

The counts above are pinned to 12:37:15. Four minutes later the same command returned:

| run | window | holes | in-flight | clean critical | verdict |
|---|---|---|---|---|---|
| 12:37:15 | 20 min | **0** | 71 | 92 | FAIL (1) |
| 12:41 | 20 min | **14** | 82 | 96 | FAIL (16) |
| 12:41 | **0 min** | **97** | 0 | 96 | FAIL (99) |

Read the third row first: **at a 0-minute window the gate reports 97 holes** — every
in-flight file becomes a hole. That is the negative control for the exemption itself. The
window is a real, stated, auditable lever; `-InFlightMinutes 0` removes all mercy and the
gate gets strictly *worse*, which is the direction a safety gate must move.

Read the first two rows together: **14 files aged out of the window in 4 minutes.** They
were live lanes at 12:37 and are holes at 12:41. The exemptions expired on schedule,
exactly as written, and every one is printed by name when it happens — this is the "if a
lane dies, re-run this gate" clause doing its job unattended.

**Two classification findings for whoever tunes the classes next** (I did not change
them — narrowing a critical class to make the gate greener is the failure mode this gate
exists to catch):

1. **`_main/_lane4-run/**` and `_main/_lane4-final*/**` are run OUTPUT, not source.** The
   holes above are almost all copies of the same two files under nested
   `meta-<timestamp>/_main/run/...` paths. Compare the nested repo's own `.gitignore`,
   which already makes exactly this distinction for `_main/build/` (`build/*` then
   `!build/*.cpp`). A `_main/_lane*-run/**` non-critical class would remove ~12 of the 14
   holes **without touching a real one**.
2. **`.pid`, `.stderr`, `.yaml` captures are UNCLASSIFIED** (§2, 85 files). They are
   evidence, not product.

---

## 9. Self-audit

**Bugs this lane found in its own gate** (each caught by a running check, not by reading):

| bug | how it surfaced | fix |
|---|---|---|
| Epoch conversion mixed local and UTC `DateTime` kinds, shifting every HEAD timestamp by the 3 h offset — **in-flight detection never fired** | `-SelfTest` arm CLEAN failed | `DateTimeOffset::FromUnixTimeSeconds` (file: `SecToLocal`) |
| A one-element result unrolled to a scalar, so `$rB[0]` indexed a string's first **character** | `-SelfTest` arm STALE reported FAIL while printing the right path | wrap in `@()` |
| `function Git` **shadowed `git.exe`** — `& git @Rest` recursed into the function itself | first real run, `Set-Location: cannot locate 'rev-parse'` | renamed `Invoke-Git`, pinned `& git.exe @Rest` |
| `$junction` (result) collided with `$Junction` (path) — PowerShell is case-insensitive | `cannot locate the path '@{Exists=True; …}'` | renamed `$junctionCheck` |
| Nested repo **at the project root** made `Substring($len+1)` throw | stack trace line 250 | length-compare guard |
| The gate counted **its own rollback scratch** as repos holding product objects | `REPOS: 5`, scratch repos listed | `IsScratch` now excludes `_main/_durability-scratch/` |
| The rollback proof was **not idempotent** — 17/17 then 16/17 on re-run | second consecutive run | fresh timestamped scratch per run |
| `research/` had no class at all | UNCLASSIFIED sample | added the class the brief asked for |

**Confidence, per claim:**

- *The clean would take 92 tracked-worthy paths* — **high**. It is `git clean -nd`
  output, rc=0, no piping, re-run 4×. It moves because lanes are writing; that is the
  population changing, not the method. **Would move me:** nothing short of the paths
  leaving the clean's target set.
- *A nested repo does not protect a file from the parent's clean* — **high**. It is the
  direct reading of `git clean -nd` on the parent for files that exist in the nested
  index; 72 such paths listed. **Would move me:** showing a `git clean -fd` in the parent
  that skips them.
- *The move and tracked-file rollbacks work* — **high**, 3/3 sha256 and rc=0, twice.
- *Junction rollback works* — **medium-high**; creation proven 4/4 assertions, and the
  real junction verified live (identical sha256 both paths, git rc=0).
- *Removing a junction leaves the target intact* — **reasoned, NOT executed** (§R2).
  Environment blocks shell deletions. Named, not buried.

**Protocols missing / gaps I know of:**

- The gate does not detect a **staged-but-uncommitted** file (`git add` without commit).
  A staged file is neither in `ls-files` tracked output as committed nor cleanly
  untracked; `git ls-files` does list it, so it reads TRACKED — correct for durability
  (it is in the index and survives a `clean`) but worth knowing.
- The gate does not verify that a `git push` exists or that a remote exists. Everything
  here is **local-object durability only**. A `rm -rf` of `.git` destroys everything this
  gate passes. **That is the single biggest unproven risk and it is outside the gate's
  scope as briefed.**
- Class tuning (§8) is deliberately left to a human.

**Did another subagent review this? NO.** See the blocker below.