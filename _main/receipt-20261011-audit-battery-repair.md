
# Receipt - 2026-10-11: the audit battery, one step at a time to exit 0

Owner acceptance (the goal this serves): ONE clean _main/_audit-verify-all.cmd run at **exit 0**.

## 0. The RED run this repair lane started from

Measured run, 2026-10-10 17:31 America/Sao_Paulo (I:/cc-tmp/battery-20261010.out):

    steps : 41 gate=31 control=9 expect-red=1 missing=0
    BATTERY-VERDICT: RED - 8 step(s) failed
    BATTERY-EXIT=1 elapsed_s=140.1

Per-step rc: lane2-reset-probe=1, panel2-dom-probe=1, strip-surface-oracle=3,
strip-stats-log-budget=1, strip-hot-reload=3, strip-surface-runtime=3,
strip-geometry-restore=3, strip-stats-wave=3; all other 33 steps rc=0. The battery script itself
is unchanged: 32,203 B, 538 CRLF / 0 bare LF,
sha256 EBF715E9E4CF75B2FF5E62A529C2C375985246CBB7BFE8459EF2A9DD1BD0EB1C, re-verified 2026-10-11 04:00.

## 1. Every red step classified (measured, one line each)

| # | step | rc | verdict | cause |
|---|---|---|---|---|
| 1 | lane2-reset-probe | 1 | STALE INSTRUMENT | ARM 6c want list held 9 names; the module exports 10 (healSeams was the missing one) |
| 2 | panel2-dom-probe | 1 | STALE INSTRUMENT | 4 label/text expectations older than the shipped strings |
| 3 | strip-hot-reload | 3 | INSTRUMENT DRIFT | WorkerReloadPolicy.__init__() got an unexpected keyword argument 'max_defer_ms' - the probe called a signature the shell no longer has |
| 4 | strip-stats-log-budget | 1 | INSTRUMENT DRIFT + FEATURE ABSENT | the control could not be built: self._stats_log_maybe(payload) is not in the shell verbatim |
| 5 | strip-surface-runtime | 3 | PRODUCT GAP | arms A/D pass --probe-outside-click / --probe-edit-mode, which the shell argparse does not define (rc=2 in 0.25 s, every measurement array empty); the tray has no 'Edit caption' item (arm C) |
| 6 | strip-stats-wave | 3 | PRODUCT GAP | arms pass --probe-stats / --probe-stats-wait, undefined flags, same 0.25 s death |
| 7 | strip-geometry-restore | 3 | PRODUCT GAP | both arms ran (rc=0, ~11.5 s each) but produced restored=[] / clamped=[] - the shell emits no restore/clamp geometry log line at all |
| 8 | strip-surface-oracle | 3 | ORACLE DEFECT | its top-level except writes the JSON report and exits 3 *before* printing, so its 0-byte log carries no diagnosis; it builds broken copies of strip features that are not in the shell |

The shape of it: the two captioning-related steps were stale lists. **All five strip steps are the
strip lane's instruments describing shell features that do not exist.**

## 2. What has been fixed, measured

### 2.1 lane2-reset-probe - now GREEN (rc 0)

The want list is the shipped surface. Evidence:

- app/panel/caption-formulation.js:165   function healSeams(parts) {
- app/panel/caption-formulation.js:782     healSeams,   (inside the object literal begun at :779)
- app/panel/caption-formulation.js:800   module.exports = SottoFormulation;   - what the probe require()s
- runtime: Object.keys(require(engine)).sort() = 10 names, typeof healSeams === "function"
- repo-wide: exactly 2 hits for healSeams, the two above - **no caller anywhere**

Verification run (mine, not the subagent's): node _main\_lane2-reset-probe.js -> rc 0,
RESULT: GREEN, 16 arms [PASS], 0 FAIL lines, 59 log lines.

Disclosed, not fixed: healSeams is exported and uncalled. The arm "the module surface is
unchanged" now honestly asserts a surface carrying an unused member. Removing the export is a
product decision and is not taken here.

Digests: 37503f2f7e53469eca1b516495edf0ff9a0d277adaa7ab284a3bb089cd55dfd0 / 7775 B (before)
-> 5a6261c1030814df75ce82753ec3cbfb0f1f914acac0993221af3a9e1855d21a / 7788 B (after), +13 B.

### 2.2 panel2-dom-probe - now GREEN (rc 0, 82/82 arms)

Four wants, each proven against the shipped panel before the literal moved:

| arm | evidence in the product | old -> new |
|---|---|---|
| the forming line's caret glyph | panel.js:722 mark.textContent = provWords.length ? U+258D : '' (U+258D appears once in the file; the node is made at panel.js:698-701) | '·' -> '▍' |
| LIVE strip title | panel.js:269 REVIVE_HINT, joined at panel.js:1877-1879 | 'Receiving captions' -> 'Receiving captions — click to restart the pipeline (reloads the live engine)' |
| PAUSED strip title | the paused branch of the same expression, so one title carries TWO U+2014 | '…until you resume' -> '…until you resume — click to restart the pipeline (reloads the live engine)' |
| #strip-live-label text | panel.js:1818-1823 re-asserts 'LIVE' in both states; the shipped comment at :1819-1821 says the word is the control's NAME and the state is carried by aria-pressed + title + #strip-word; panel.css:1735 and :1862-1863 paint OFF red | 'Live off' -> 'LIVE' |

Verification run (mine): node _main\_panel2-dom-probe.js -> rc 0, RESULT: GREEN - 82/82 arms,
279 log lines, 82 [PASS], 0 FAIL. File integrity after: 53,979 B, 926 CRLF / 0 bare LF
(CRLF preserved; edit only, no write).

Digests: a3c60c1bcf747422d1f78c35f44e88326560f5d0591c71c8a89c1507bd0b7320 / 53,862 B (before)
-> 3a48718c79fac13c9fe2ce53c93f267ff5fab0c2124bd1986bd471cb50f45b42 / 53,979 B (after), +117 B.

Two things this repair deliberately did NOT do, so the next reader does not have to guess:

1. The arm is still titled "and the label follows the state", which the shipped design no longer
   does - panel.js:1819-1821 says the word is the control's name and the state lives in
   aria-pressed / title / #strip-word. The arm still compares against a literal and is not a
   tautology; renaming the arm title is a follow-up, not something to smuggle past a red gate.
2. app/panel/panel.css still carries a stale prose comment naming U+00B7 as the tail marker,
   near the .caption__mark rules. Panel CSS is another lane's file: flagged, not edited.

### 2.3 A trap worth its own section: commits in this shared checkout

Both edits were verified green first and only then staged. **Neither landed in a commit of mine.**
Between my git add and my git commit another lane committed the same checkout and swept my staged
files in:

- _main/_lane2-reset-probe.js -> landed inside c32e565
  ("install-hooks: versioned installer with --check, so a fresh clone is not silently gate-less")
- _main/_panel2-dom-probe.js -> landed inside 0a945c9
  ("PERF_PROBE_N env so the repeat distribution can be measured at all")

Both are durable and both are green (re-verified AFTER those commits), so nothing was lost - but no
commit message of mine describes them, and this receipt is that description. The rule that follows,
measured here: in this checkout a staged file is not yours until it is committed, and the second
git log -- <path> is part of the verification, not an optional courtesy.

A second, distinct trap in the same hour: the repo's pre-commit hook (run-all.mjs, wired by
3d0a3d7) runs 15 suites plus a gate on every commit. Its compose-probe.mjs arm failed with
"no per-user application data directory: neither LOCALAPPDATA nor APPDATA is set" - because a DSH
run_code process starts with an EMPTY environment (powershell -Command "$env:LOCALAPPDATA" is
empty there too), not because the product is broken. The real values are
C:\Users\Administrador\AppData\{Local,Roaming} (registry HKCU\Volatile Environment). Any commit
or battery run made from a tool process must be given those variables or its results are an
artefact of the sandbox.

## 3. What is still open, with the size of each

Steps 3-8 above.

### 3.1 The decisive finding: the contract is not a REGRESSION, it is a NEVER-MERGED WIP

`docs/shell-contract.md` (16,490 B / 210 lines, measured 2026-10-08 by lane `strip-surface`) documents
a shell revision of 397,180 B / 7,930 lines. A lane-side belief grew that the shell had SHRUNK against
its own contract. That belief is **REFUTED by measurement here**, and the refutation is more useful than
the belief was.

`git rev-list --all -- app/webview/sotto_webview.py` returns **exactly 6 distinct revisions** of the
shell in the whole object database. **CORRIGIDO 2026-10-11 — the claim written here ("and they GROW
monotonically") is REFUTED by two independent measurements.** (a) Ordered by COMMIT DATE the six
revisions do not grow: `160,779 -> 271,216 -> 406,194 -> 283,757 -> 284,381 -> 320,214` bytes — the
file FALLS 122,437 B between `55c422b` (10-08 09:14) and `3352f61` (10-08 10:08)
(`app/shadowplay/state/friction/FRICTION-LEDGER.md:1821-1825`); the table below is sorted by SIZE,
which is why it reads as growth, and the sentence that follows the table below ("The file never
shrank"; pre-edit line 131, now line 143) is the same claim restricted to a subseries that omits
`55c422b` and `336dfc8`. (b) The port that grew the
live shell is not monotonic in CONTENT either: the live file's BYTE series grows at every landing,
but the BLOCK series does not — of the 32 blocks extracted from the `55c422b` reference, **8 were
SKIPPED because the work they carry was already live** (blocks 6, 19, 22, 23, 24, 25, 26, 27) and
**2 were applied as surgical INSERTS, not wholesale replacements** (blocks 5 and 21)
(`_main/receipt-20261011-strip-contract-port.md:57-74`). The table below is those six revisions in
the order this receipt wrote them (by SIZE, not by date):

    406194  55c422b  10-08 09:14  On feat/build-verify-1: wip-boot-grace-before-strip-work
    320214  1d97536  10-10 12:46  feat(panel): land the 2026-10-09 transparent-panel body, strip controls and their gates
    284381  336dfc8  10-09 02:10  lane/strip-shell-2: Alt+C double-press side panel, foreground, transparency bridge
    283757  3352f61  10-08 10:08  lane/strip-shell: Alt+C mouse unlock + double-press side panel
    271216  a3c288f  10-07 10:27  panel+shell+worker: verified work of 2026-10-07/08
    160779  5ffeefc  10-06 06:59  durability: track the whole untracked production tree

160,779 -> 271,216 -> 283,757 -> 320,214 bytes. The file never shrank, and **no revision is within
8,000 bytes of the contract doc's 397,180**, so the doc measured a working-tree state that was never
committed as the mainline shell. (On disk the shell is CRLF: 326,796 B / 6,583 lines, blob 320,214 B.
The 6,582-byte difference is 6,583 CRs - not drift. Working tree is clean against HEAD.)

`git log --all -S` for `_stats_log_maybe`, `PANEL_EDIT_MODE` and `STRIP_HEIGHT_CSS_VAR` returns **zero
commits on the shell path**, and those markers are absent from all 6 revisions above. They are present
in the preserved copy `app/webview/_strip-logmutant-repro_sotto_webview.py` (7,630 lines at HEAD) and
in the largest surviving shell revision:

    marker                      55c422b (WIP)   preserved copy   live shell (HEAD)
    _stats_log_maybe            2               1                0
    PANEL_EDIT_MODE             6               6                0
    STRIP_HEIGHT_CSS_VAR        2               2                0
    on_worker_meter             2               2                0
    WORKER_RELOAD_MAX_DEFER_MS  3               3                0
    PANEL_GEOMETRY_RESTORED     1               1                0
    HOT_RELOAD_WORKER_FORCED    1               0                0
    HOT_RELOAD_WORKER_BOUNDARY  2               0                0
    BRIDGE_STATS_PUSH           2               3                0
    setPanelSurface             8               0                0
    run_hover_probe             2               0                0

`git branch -a --contains 55c422b` -> **EMPTY**; `git cat-file -t 55c422b` -> `commit`. The revision
that implements the contract is a **DANGLING commit, reachable from no ref**, sitting on
`feat/build-verify-1` under the message "wip-boot-grace-before-strip-work". Its merge-base with the
landed lineage is 24df100 (2026-10-07 13:58); the landed lineage instead descends 3352f61 -> 336dfc8
-> 1d97536. (`getStats`/`onStats` are JS-side bridge names and have no Python `def`; every other
contract marker is in the WIP.)

**Consequence.** The six strip gates do not measure a deleted feature. They measure a feature that was
**built and never landed**, on 2026-10-08, in a WIP tree whose objects still survive in this
repository. Restoration has a reference implementation to READ, not code to invent - and that object
database is the only copy, so it must not be garbage-collected before the decision is made.

### 3.2 strip-hot-reload - the rewritten probe, measured (subagent 3, live run)

`_main/_strip-reload-probe.py` was rewritten to stop guessing at the shell signature: 474 lines /
22,121 B -> **888 lines / 40,855 B / sha256
66fbb71f627d3b40ee1dafe38054893d39c92506e10864534bb26e57ac6082b5** (LF-only). It now reads
`inspect.signature(cls.__init__)` at run time, forwards accepted keywords UNCHANGED, and records the
rest as `report["mapping"]` UNMAPPED with the live signature as evidence. No arm was weakened,
skipped or commented out; three construction sites route through one helper block (:455).

Live run (mine, on the rewritten probe): `python _main\_strip-reload-probe.py`, rc=3, 73 lines /
6,900 B, zero `Traceback` / `BRIDGE_SILENT` / `SKIPPED`. **The crash is gone**; what replaces it is a
verdict: `VERDICT: RED` against shell sha256 `557a2b0d...`, 7 arms, 24 checks = **6 green / 18 red**,
17 SURFACE rows, 2 lines labelled VACUOUS on purpose. Green: arms A x2, C x2, E ("the owner's floor
bounds the RATE") and F ("the log grew by ONE line").

Measured behaviour, which is the substance behind the reds:

    HOT_RELOAD_WORKER_QUEUED  ... debounce_ms=0 min_interval_ms=0
    HOT_RELOAD_WORKER_DEFERRED ... reason=capturing - applies at the next boundary

the worker pid is held across every arm (A 556->556, C 4076->4076, D 45812->45812, E 47228->47228),
`restarts=0`; the stand-in's one closed line still arrives as a REAL caption
(`text="stand-in closed line" meta={'final': True, ...}`, `BRIDGE_CAPTION_SENT delivered=true`);
`last_worker_stats` is parsed from the real `WORKER_STATS tag=tick peak=0.443448 blocks=812`; and
**165 `BRIDGE_UNKNOWN` lines** come from `{"type":"meter"}` frames - the shell's own meter bug,
`WorkerBridge._consume` has no `meter` branch, so every sample falls into the unthrottled unknown-kind
`else` (:5628).

MAPPING records `max_defer_ms=600000` and `defer_recheck_ms=5000` UNMAPPED against the live signature
and `on_stats` / `on_meter` UNMAPPED against `WorkerBridge(...)`. **Subagent 3's conflict is
recorded and stands: `strip-hot-reload` is a `:record` GATE, so rc != 0 is recorded FAILED and the
battery exits 1. No probe-only edit can honestly make it 0 - the 18 reds are 18 absences in the loaded
shell.**

### 3.3 The closure choice, now that it is priced

Two of the eight reds are FIXED and durable in HEAD (§2). The remaining six are all strip-lane, and
per §3.1 all six measure a surface whose implementable reference is a dangling WIP commit. There are
exactly three honest closures, and none of them is a want-list edit:

- **(a) RESTORE** the contract into the landed shell. Priced by §3.1: it is a port, not an invention -
  `git show 55c422b:app/webview/sotto_webview.py` is the reference. The smallest, most defensible
  piece is the reload CEILING (`WORKER_RELOAD_MAX_DEFER_MS` + the `defer_recheck_ms` re-arm +
  `HOT_RELOAD_WORKER_FORCED ... reason=no-boundary-in-<ms>ms`), which also fixes a real user-visible
  bug: `_fire` (:5199-5203) sets `pending = None` and re-arms WITHOUT forcing, so an owner edit made
  while the worker captures never reloads. Every restored line needs a live run before it is claimed.
- **(b) RE-SCOPE** the gates as `:expectred` negative results. This is only honest if a receipt names
  the coverage lost: no outside-click, no edit mode, no geometry persistence, no per-sample stats, no
  meter branch, no reload ceiling - permanently unmeasured, not "not yet".
- **(c) ASK the owner** which of (a) or (b) he wants, given that (a) is a port with a reference
  implementation and a real bug at the end of it, and (b) is a permanent hole.

This lane has NOT taken (a) unilaterally: it edits `app/webview/sotto_webview.py`, which four live
worktrees (`lane/strip-shell-2`, `lane/strip-controls`, `feat/build-verify-1`, the audioclip lane)
share, and the owner has not chosen. It is recorded here so the choice can be made from measurements
instead of impressions.

## 4. Files touched by this lane (complete list)

| file | change |
|---|---|
| _main/_lane2-reset-probe.js | ARM 6c want list, +1 name (healSeams) |
| _main/_panel2-dom-probe.js | 4 want literals |
| _main/_strip-reload-probe.py | rewritten: run-time signature mapping, no weakened arms (888 lines / 40,855 B) |
| _main/receipt-20261011-audit-battery-repair.md | this receipt |

Nothing else. The battery script is byte-identical to before this lane started: 32,203 B, 538 CRLF /
0 bare LF, sha256 EBF715E9E4CF75B2FF1E62A529C2C375985246CBB7BFE8459EF2A9DD1BD0EB1C.

