# INTEGRATION-14 — the product root and `main` are one tree

**Seat:** agent session · **Date:** 2026-10-09
**Subject:** bring `H:\sotto` (the tree the app actually runs) current, then collapse it with `main`
**Scratch:** `I:\cc-tmp` (`TMPDIR/TEMP/TMP` set there). `git add -A` never used.
**Product root:** `H:\sotto` · **Merge worktree:** `H:\sotto-wt\ArbV8`

## Why

INTEGRATION-13 ended by naming the one standing limitation:

> **`H:/sotto` — a raiz que o app realmente usa — continua intocada e 191 commits atrás de `main`.**

That was the last open divergence: all the work landed in `main` lived in a
worktree, while the process the owner launches read a tree that had never seen
it. This lane closed it in both directions.

## What was done

### 1. Capture the product root's uncommitted work

`H:/sotto` carried 1002 dirty entries. Measured before committing:

- **973 paths** considered (82 tracked edits + 891 untracked)
- **29 artefact paths excluded**, then refined to **file granularity** so whole
  directories would not drag binaries in: final plan **1364 files / 26.2 MB**,
  everything source/receipts/scripts (largest = 2.2 MB of text)
- `_moved/aireplay-wt/` excluded — it is a scratch worktree, not product content
- **secret-scan: 2 hits, both false positives** (`Token = 'RETENTION-BYTES'`,
  `token: '--size-caption'`) — no keys
- **6 paths refused by `.gitignore`** (`_main/denoise-runs/*.err`, rule `*.err`
  at `.gitignore:35`) — respected, refiltered out
- **12 tracked binary edits** (11 PNG + 1 `.exe`, ~2.3 MB) staged explicitly

`git add --pathspec-from-file` was used because 1364 arguments would exceed the
command-line limit. Result: **`4e2127a`, 1369 files**, uncommitted modifications
**→ 0**, dirty entries 1002 → 82 (all artefacts). Pushed before anything else.

### 2. Merge `main` INTO the product root — 3 conflicts, all unions

`git merge main` auto-merged 250 files including `app/panel/panel.css` and
stopped on exactly **3**. Measured against the merge base first:

| file | base | ours vs base | main vs base | verdict |
|---|---|---|---|---|
| `AGENTS.md` | 52951 | +77 −10 | +78 −0 | both edited |
| `_moved/aireplay/AGENTS.md` | 31905 | +128 −50 | +19 −1 | both edited |
| `app/panel/theme-switcher.js` | 13769 | +95 −9 | +277 −7 | both edited |
| `app/panel/panel.css` | — | +611 −18 | +111 −0 | **auto-merged** |

Probe for duplication — **each side had what the other lacked, zero overlap**:

```
AGENTS.md              OURS shell-contract(08): 1   MAIN: 0
                       MAIN CORRECTIONS(07):   1   OURS: 0
_moved/aireplay/...    MAIN TWO-STATEMENTS-SPLIT: 1  OURS: 0
                       OURS IT-HAS-BEEN-RUN:     1  MAIN: 0
theme-switcher.js      OURS previous/group/variant: 1 each  MAIN: 0 each
                       MAIN chevron+dropdown: 1          OURS: 0
```

So no side was a superset and every resolution is a **union**, not a pick. One
hunk per file, resolved by rule:

- **`AGENTS.md`** — base is empty inside the hunk, so both sides *appended*
  different sections. Kept both, chronological: main's `CORRECTIONS 2026-10-07`
  then ours' `THE SHELL'S OWN CONTRACT … 2026-10-08`.
- **`_moved/aireplay/AGENTS.md`** — both blocks replace the SAME two paragraphs.
  Part 1 keeps **main's** careful *"TWO STATEMENTS USED TO BE CONFLATED HERE;
  SPLIT — DO NOT MERGE THEM BACK"* restructure (it separates the 16 GB design
  floor from the owner's measured 47.74 GiB) **plus** the two sentences only ours
  had (`Receipts 14 + 16 … not hooked up`, `3.9 GB … SUPERSEDED`). Part 2 keeps
  **ours**, because it carries the newer fact: `onnx-asr IT HAS BEEN RUN (892.7 MB)`.
- **`app/panel/theme-switcher.js`** — kept **ours'** `previous()` / `group()` /
  `variant()` (0 occurrences in main — dropping them would break callers) with
  **main's** updated `mount()` doc comment (chevron + dropdown).

`_wt-resolve.py` (`I:\cc-tmp`) performed this: `git merge-file -p --diff3` per
file, split the single conflict, applied the rule, refused to write if any marker
survived. **`MERGE READY`**, then gates, then commit **`5bf0242`**.

### 3. Collapse: `main` absorbs the product root

`git merge-tree --write-tree main feat/build-verify-1` → **rc=0 (clean)** before
anything was attempted. Scope: **1368 files** (1274 added + 94 modified), 28.3 MB.

One collision only: `control/optchat/view.txt` existed untracked in ArbV8 and the
incoming branch added it — **and the two versions differ** (516 B local `fc7ba4a7…`
vs 513 B incoming `07e75984…`). Git aborted cleanly (rc=1, HEAD unchanged). The
local copy was **renamed beside the incoming one**, never deleted:
`control/optchat/view.arbv8-local-fc7ba4a7.txt`. Retry → **rc=0**.

## Verification

| check | result |
|---|---|
| `origin/main` / `main` / product root `HEAD` / `feat/build-verify-1` / `origin/feat/build-verify-1` | **all five = `5bf0242`** |
| divergence `main ↔ product root` | **0 0** |
| unpushed (product root) / unpushed (main) | **0 / 0** |
| conflict markers remaining | **0** |
| files deleted by either merge | **0** |
| protected 10 in ArbV8 | **`ALL_OK=True`** (all present) |
| gates, product-root merge (253 staged) | py **48/0**, js **49/0**, json **9/0** |
| gates, main merge (1368 changed) | py **273/0**, js **62/0**, json **174/4** |
| `run.cmd --help` | **rc=0**, 4048 B |
| `run.cmd --bogus-flag` | **rc=2** (exit contract intact) |
| **real panel load** `run.cmd --dump-dom --no-hotkey` | **rc=0**, `BRIDGE_GATE=GREEN hasPanelElement=true`, `SHELL_EXIT rc=0` |
| JS errors during that load | **0** (`PAGE_ERROR`/`Uncaught`/`SyntaxError`/`ReferenceError` = none) |
| receipts on `origin/main` | `INTEGRATION-11/-12/-13` **all present** |
| tracked files on `main` | **2515**, **404** commits |
| branches / worktrees | 10 / 11 |
| disk on `H:` | **102 G free** (12.6 GB were freed earlier this session) |

## The 4 JSON failures — all pre-existing, none introduced here

`json 174/4` on the main merge. Each was re-checked **in the source it came
from**, and each fails identically there:

- `_main/_design-zips/{directions,transcription}/tsconfig.json` (712 B) — line 10
  is `/* Bundler mode */`: these are **JSONC**, which `tsc` accepts and strict
  `json.load` rejects. They sit inside zip artefacts for a product that has **no
  build step** (`AGENTS.md` §1). *Caveat, stated plainly: an attempt to prove
  "JSONC, therefore fine" with a hand-rolled comment stripper was WRONG — the
  regex ate the `/*` inside the string literal `"@/*"` and produced a phantom
  "Invalid control character". The evidence that stands is the original strict
  error (line 10, the block comment) plus the file's own content.*
- `_moved/aireplay/_main/lane9-cura-{cuda,lang}.json` — **0 bytes**, tracked.
  Empty files; trivially invalid. In the parked, non-product tree.

Neither group is on the live path. Both were committed exactly as found — the
capture's job was to preserve, not to rewrite.

## Defects in this lane's own instruments (all found and fixed before use)

1. **Relative paths resolved against the script's cwd.** `protected_state()`
   opened `AGENTS.md` etc. relative to wherever the script ran, so a run from
   `I:\cc-tmp` reported a false **VIOLATION** for every merge. In a second
   variant `git("worktree", "remove", …)` passed the subcommand as the *repo*
   argument — it removed nothing while reporting **135 refusals**. Fixed with an
   explicit `os.chdir` / `git -C <repo>`.
2. **A gate that did not filter on disk existence** reported 40+ failures for
   files deleted *on purpose* (the `_backup/` removal). Re-run filtered: py
   **34/0**, js **49/0**, json **9/0**, `non-_backup deleted: 0`.

## Not done / limits

- The **4 JSON** above are pre-existing, not fixed — 2 are legitimately JSONC,
  2 are empty parked files. No runtime check of TypeScript was run (`tsc` is not
  on this box).
- **Runtime verification covers the panel shell**, not the worker: no live
  transcription was exercised by this lane (the owner's app owns the audio
  endpoint).
- **`_moved/aireplay/AGENTS.md` part 1** is a hand-composed union of two
  independent corrections to the same paragraph. Both facts are present and
  non-duplicated (verified by count), but it is worth a human read.
