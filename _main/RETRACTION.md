# RETRACTED -- three of my reports measured a truncated listing

Written 2026-10-07 15:49:19 -03:00 at HEAD `ee80c92`.

## The defect in my own instrument
I listed a directory with `Select-Object -First 14` and reported the truncated
output as if it were the whole population. I wrote the opposite rule into every
lane brief -- "never pipe a native command to `Select-Object -First N`" -- and
broke it myself, in three consecutive reports.

## Evidence, reproducible at this HEAD
| Measure | Command | Result |
|---|---|---|
| markdown receipts in `_main/` | `Get-ChildItem _main -File -Filter *.md` | **97 files**, 1141450 bytes |
| product source files | `Get-ChildItem _moved/aireplay/src -Recurse` filtered to code extensions | **37 files**, 676352 bytes |
| panel+shell+worker commit is an ancestor of main | `git merge-base --is-ancestor a3c288f main` | **rc=0** (0 = yes) |
| main commit count | `git rev-list --count HEAD` | **134** |

## The three retractions
1. **"159 lines of production code across 100 branches"** -- RETRACTED. That counted
   `--numstat` over branches and ignored `_main/`. Corrected: 37
   source files, 676352 bytes.
2. **"9 of 13 capabilities NOT STARTED"** -- RETRACTED. Written without reading the
   tree. Commit `a3c288f` (panel+shell+worker, five themes, per-theme chrome,
   typewriter reveal, tray with Quit, 10 Hz per-window meter, window icon + AUMID)
   is an ancestor of main.
3. **"the project is nearly empty"** -- RETRACTED. 97 receipts, 1.1 MB, in main.

## What this retraction does NOT establish
It does not establish that the panel builds, that the hotkey delivers, or that any
of it runs. Those are unmeasured. A commit message saying "verified" is a claim,
not a measurement. Do not read this file as a green light.
