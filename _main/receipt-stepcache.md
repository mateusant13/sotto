# RECEIPT — the step cache of the battery (incremental / delta runs)

Owner, 2026-10-20, verbatim: *"faz cache e teste incremental/delta e etc pra tu
parar de re rodar tudo do zero TODA HORA"*.

This receipt says what was built, what was MEASURED, what was NOT measured, and
where the cache must not be trusted.

---

## 1. WHAT WAS DONE

### 1.1 The engine — `_main/_stepcache.py` (NEW, 15 228 B, LF, sha256 `CFD676BA…`)

One step, one fingerprint, one honest answer.

* **The fingerprint is CONTENT.** `sha256` over, for every dep sorted by path:
  `<path>\0<sha256 of the file's BYTES>\n`. An `mtime` decides nothing: a `touch`
  does not invalidate a step, and a rewrite with the same bytes does not either.
  The deps are resolved against the REPO ROOT, never against the cwd, and the
  fingerprint key is the path RELATIVE to the repo, so the tree can move.
* **The state on disk** is `H:\sotto\_cache\battery-steps.json` (28 737 B after
  the runs below, **51 entries = the 51 steps of the battery** in its current
  shape; the oracle writes in its OWN temp state and never in this one). One
  entry per step: `fingerprint`, `rc`, `exit_code`, `expect_rc`, `timestamp`,
  the dep list, the log path and the log's `sha256`.
  It is written ATOMICALLY (temp file + `os.replace`), so a crash mid-write
  cannot leave half a state behind.
* **The CLI:**
  * `python _main/_stepcache.py check --step NAME --deps "a;b" [--log L]
    [--expect-rc N] [--state FILE] [--always]` → prints exactly two lines,
    `HIT` + `rc=<n>` or `MISS` + `reason=<why>`, and exits 0 (HIT) or 1 (MISS).
    `--deps` accepts BOTH forms: one `;`-separated string (`--deps "a;b"`) and
    several space-separated files (`--deps a b`).
  * `python _main/_stepcache.py record --step NAME --deps "a;b" --rc N
    [--log L] [--state FILE]`
  * `python _main/_stepcache.py status [--step NAME]`
* **THE HONESTY RULE** (in `check()`, and nowhere else): a HIT needs (a) the
  fingerprint of the deps today to equal the recorded one, (b) the recorded `rc`
  to be the rc the step is SUPPOSED to produce — 0 for a gate/control/skipped,
  1 for the expect-red step — and (c) the log the step produced to still EXIST
  and its `sha256` to be the one recorded. Any of the three failing is a MISS.
  A step with **no deps** is always a MISS: nothing could invalidate it.

### 1.2 The gate — `_main/_stepcache-oracle.py` (NEW, 16 092 B, LF, sha256 `45D23CFF…`)

Runs in its own temp dir (`I:\cc-tmp\stepcache-test-<pid>\`), never touches the
real state nor the real battery (arm **m** proves both are byte-identical
before and after), and can be pointed elsewhere with `--state`.

### 1.3 The integration — `_main/_audit-verify-all.cmd`

**48 800 B, 725 CRLF / 0 bare LF, sha256 `43292641…`** as this lane patched it
(before: 38 240 B, 626 CRLF / 0 bare LF, sha256 `89A6B1F3…` — the brief's pin
`035CD132…` was STALE: the file had already moved on 2026-10-20 01:10, before
this lane touched it).

**AND, MEASURED AFTER THIS LANE'S LAST RUN: another lane edited the SAME file at
02:37:00 and added TWO steps (`panel-live-box-oracle` and
`external-subs-geometry-window`), using this lane's `:step` layer and giving
their steps their own deps.** The file is therefore now **51 832 B, 765 CRLF / 0
bare LF, sha256 `7CACF6AE…`, 51 steps**. THEIR run at 02:37 was GREEN:
`steps=51 gate=39 control=10 skipped=1 expect-red=1 missing=0 cached=46
failed=0` — 46 of the 51 steps came from this lane's cache, and the 5 that ran
are the 5 `always` steps. That run is an INDEPENDENT confirmation that the layer
works for steps this lane did not write.

* The file was patched **BY BYTES** (a Python patcher that asserted every
  replacement occurs exactly once and re-checked the CRLF property before and
  after). The `write` tool was never pointed at it: it emits LF, and cmd.exe
  seeks a batch file by BYTE OFFSET — in LF the step list runs TWICE.
* A new subroutine `:step [always] <name> <expect-rc> <deps;> <logfile> <cmd...>`
  runs every step. It asks the engine first; on a HIT it does **not** execute
  the command, it returns the recorded rc, prints the beacon with `  (cached)`
  and counts it. On a MISS it runs the command with its output redirected to the
  log, records the result, and the recorder prints the normal beacon.
* **The four kinds keep their meaning.** `:record`, `:control`, `:skipped` and
  `:expectred` were not touched except for reading `!STEP_RC!` instead of
  `!ERRORLEVEL!` and appending `  (cached)`. A **cached control still has to
  prove its verdict in its log**: `:control` reads the same log the previous run
  wrote and fails if the verdict text is not there.
* The deps of each step are the instrument ITSELF plus the product files it
  judges (e.g. `verdict-gate` = `_main\verdict-gate.py` + `worker\sotto_worker.py`;
  `panel2-dom-probe` = the probe + the 14 scripts `panel.html` loads + `panel.css`;
  `fresh-processor-probe` = the probe + `worker\config.json` + the 15 files of the
  model dir the config names).
* **The summary tells the truth**: `steps : 49  gate=37  control=10  skipped=1
  expect-red=1  missing=0  cached=44`, a `cached : K` line, `cached=K` in
  `_battery-summary.txt`, and the verdict says how many steps were reused. A
  cache hit can never hide a failure: a step that ran and returned non-zero is
  still RED, and the recorded rc of a failed step is never reused as a pass.
* **NEW STEP**: `stepcache-oracle`, registered as an ordinary gate.

### 1.4 The steps that are NEVER cached

A step whose truth is OUTSIDE the files cannot be cached, and these carry the
`always` marker:

| step | why it is always |
|---|---|
| `mute-audio` | the real default device and the owner's own volume |
| `hotkey-registration` | what the OS says about a hotkey RIGHT NOW |
| `hotkey-delivery` | the owner's live shell holds Alt+C (or does not) |
| `autostart-status` | the Windows registry |
| `skip-verdict-guard` | the sweep itself: it has to see every log, every run |

---

## 2. THE NUMBERS (measured, on this box, 2026-10-20)

The instrument is the wall clock around `cmd /c _main\_audit-verify-all.cmd`,
same shell, same box, back to back. The console of each run is in
`I:\cc-tmp\battery-{cold,warm,delta,final}.log`.

| run | what changed | wall clock | cached | verdict |
|---|---|---|---|---|
| **COLD** | empty cache (the state file did not exist) | **284,62 s** | 0 | GREEN WITH 1 SKIPPED |
| **WARM** | nothing changed | **14,44 s** | 44 | GREEN WITH 1 SKIPPED |
| **DELTA** | one line appended to `_main/_stepcache-oracle.py` | **43,65 s** | 33 | GREEN WITH 1 SKIPPED |
| **FINAL** | the line removed (the file back to its original bytes) | **21,77 s** | 40 | GREEN WITH 1 SKIPPED |
| *(other lane, 02:37)* | *2 more steps added to the battery by another lane* | *not timed by this lane* | *46* | *GREEN WITH 1 SKIPPED* |

**The gain: 284,62 s → 14,44 s = 19,7× faster** (a saving of 270,18 s, or 94,9 %
of the run), with the SAME verdict: 49 steps, 37 gates, 10 controls, 1 skipped,
1 expect-red, 0 missing, **0 failed**, exit code 0. (The four runs above were
measured while the battery had 49 steps; the other lane's 02:37 run had 51 and
was GREEN too.)

### 2.1 Why the DELTA run re-ran 16 steps (and why that is the cache working)

Of the 16, five are the `always` steps (they always run). The other eleven were
invalidated because **other lanes were editing the product WHILE the battery
ran**: `app\panel\panel.js` changed at 02:29:22 and `app\webview\external_subs.py`
at 02:30:19 (measured). The steps that re-ran were exactly the ones whose deps
those files are in: `live-vs-history-source-oracle`, `panel-state-guard-gate`,
`lane2-reset-probe`, `panel2-repeat-probe`, `panel2-dom-probe`,
`embedded-js-check`, `external-subs-stability`, `external-caption-chrome-census`,
`strip-surface-oracle`, `control-panel2-repeat-revert` and `stepcache-oracle`.
A cache that did NOT notice those would be the dangerous kind.

### 2.2 The gate of the cache itself

`python _main/_stepcache-oracle.py` → **VERDICT: PASS  arms 13/13  mutants 4/4
(2,1 s)**, rc=0.

The arms: (a) unchanged content → HIT; (b) changed content → MISS; (c) a
recorded rc≠0 → MISS; (d) deleted log → MISS; (e) changed log → MISS; (f) no
deps → MISS; (g) a corrupt state file → MISS and no crash; (h) the CLI answers
`HIT`/`MISS` exactly as announced (byte for byte, and the exit codes 0/1);
(i) an mtime-only change → still HIT (the fingerprint is content); (j) a changed
dep SET → MISS; (k) an expect-red step (rc=1) → HIT, while the same entry with
rc=0 → MISS; (l) a missing dep → MISS and no crash; (m) the real state and the
real battery are untouched by the oracle.

The **executed** negative arm: four BROKEN COPIES of the engine, each a textual
patch of a unique anchor, each loaded and put through the SAME battery, each of
which has to go RED **on its own claim**:

| mutant | broken claim | caught by |
|---|---|---|
| `fingerprint-ignorado` | changed content is reused | arm **b** |
| `log-nunca-verificado` | a deleted log is reused | arms **d** + **e** |
| `rc-nao-passe-aceito` | a recorded failure is reused | arm **c** |
| `sha256-do-log-ignorado` | a swapped log is reused | arm **e** |

**mutantes : 4/4 RED.** An anchor that is missing or ambiguous is refused as
decorative (and would be counted as a failure, not as a catch).

### 2.3 THE BATTERY IS RED RIGHT NOW, AND IT IS NOT THIS LANE'S CACHE

**The final runs (02:59, 03:19, 03:28) are RED: `strip-stats-log-budget=3`,
`strip-geometry-restore=3`** (`steps : 52 gate=40 control=10 skipped=1
expect-red=1 missing=0 cached=44`, exit 1). The measured cause:

* `app\webview\sotto_webview.py` was rewritten by ANOTHER lane at **02:55:53**
  (707 907 B). It is a file this lane does not own and must not touch.
* The three strip probes launch the shell as
  `pythonw.exe app\webview\sotto_webview.py --no-tray --exit-after 8 --log ...`
  and wait for it. With the shell as it is NOW, **the instance does not exit**:
  `_main\_strip-restore-probe.py:181` raises
  `subprocess.TimeoutExpired: Command '[...pythonw.exe, ...sotto_webview.py,
  --no-hotkey, --no-hot-reload, --no-worker, --no-tray, --exit-after, 8,
  --log, ...]' timed out after 10 seconds`, and the probe exits **rc=3
  (CRASH)**. The control `strip-stats-log-budget` dies the same way (its log is
  0 B), so it never prints `STRIP-LOG CONTROL PASS` and the control FAILS.
  The shell's OWN comment describes this exact failure mode (`:5645-5648`:
  *"the shell HANGS before the panel loads ... It also broke the `--exit-after`
  probes the same way"*).
* **The same three steps were GREEN in this lane's 02:22 cold run, with the
  cache layer already in place** (`strip-stats-log-budget rc=0 [CONTROL] went
  RED on the broken copy as required`, `strip-geometry-restore rc=0`,
  `strip-stats-wave rc=0`). The battery was GREEN WITH 1 SKIPPED then.
* **The cache did not cause it and did not hide it.** The deps of those three
  steps include `app\webview\sotto_webview.py`, so when that file's bytes
  changed the cache invalidated EXACTLY those steps, they re-ran, and the
  battery reported the real failure instead of reusing the previous green log.
  That is the cache doing its job; the RED is the other lane's regression, and
  the fix belongs to the shell's lane (this lane is forbidden from touching
  `app/webview\**`).

---

## 3. WHAT WAS NOT MEASURED

* **NOT measured: the cache across a real "the owner changed one line in the
  worker" cycle.** The delta proof above changed the ORACLE's own file (a file
  this lane owns) and observed the other lanes' concurrent edits. No step of
  `worker/**` was touched by this lane, so the worker's own invalidation was
  not exercised end to end — the mechanism is the same code path, but the
  measurement was not made.
* **NOT measured: the cache's behaviour when the state file is deleted or
  corrupted between runs** at the BATTERY level (the arm proves the engine does
  not crash and answers MISS; the battery-level run was not staged).
* **NOT measured: a cache hit on a step whose log was rewritten by ANOTHER run**
  (two batteries at once). The engine answers MISS (the log's sha256 is not the
  recorded one), but no two concurrent batteries were run.
* **NOT measured: the gain on the owner's real usage pattern** (how often the
  owner actually changes the product between runs). The 19,7× is the
  best case: nothing changed at all.
* **NOT measured: the wall clock of the individual steps.** The battery does not
  time its steps, so "which step is the expensive one" is not answered here. The
  cold/warm difference says the heavy step (`fresh-processor-probe`, the model
  load) is what the cache saves.
* The `hotkey-delivery` step reported **SKIPPED** in every run here, with its
  own words: *"to verify the skipped arm: close the Sotto shell and re-run this
  probe"* — the owner's shell was running (pid 51264, `--show`) and holds Alt+C.
  That is the pre-existing, declared behaviour of that arm, not a change.
* **NOT fixed by this lane: the three strip steps that are RED now** (§2.3).
  The cause is measured and it is in `app/webview/sotto_webview.py`, a file
  this lane does not own. Two of the three failures were also present before
  this lane's last commit (the shell has not changed since 02:55:53).
* **NOT measured: the battery's verdict with the shell fixed.** The last GREEN
  full run measured by this lane is the 02:22 cold run (49 steps) and the
  other lane's 02:37 run (51 steps, cached=46). The runs after 02:55:53 are
  RED because of the shell, so the number this lane can report for "the
  battery with the cache, green" is the 02:37 one (another lane's run, with
  46 of 51 steps reused) and this lane's own 02:22/02:26 runs.

---

## 4. THE LIMITATIONS (where this cache must not be trusted)

1. **A step whose truth is not in a file must be marked `always` and NEVER
   cached.** The registry (`autostart-status`), the real keyboard
   (`hotkey-registration`, `hotkey-delivery`), the real audio device
   (`mute-audio`) and the sweep itself (`skip-verdict-guard`) are the four
   cases in this battery. A cache that reuses a reading of the outside world is
   a lie, and a lie that is faster is still a lie. **A NEW step whose result
   depends on anything outside the files has to be marked `always` by whoever
   writes it — the cache cannot know.**
2. **The deps list is a human claim, and the cache believes it.** A dep that is
   missing from a step's list is a dep whose change will NOT invalidate that
   step. The engine cannot find the deps by itself; it hashes what it is told.
   Every list in the battery was read out of the instrument's own source (the
   constants `SHELL`, `WORKER`, `REPO`, the `require()` paths, the scripts
   `panel.html` loads), and the oracle's arms prove the MECHANISM, not the
   completeness of each list.
3. **A dir is not a dep.** The engine hashes FILES. A new file appearing inside
   a directory that is not in the list does not invalidate the steps that read
   that directory. The model dir is listed file by file for that reason.
4. **The hash of the model costs ~0,9 s per run** (783 MB, measured in Python)
   on the one step that reads the weights. That is the price of the content
   rule, and it is 0,9 s against a model load that takes minutes.
5. **The state file is machine-local and is NOT tracked by git** (it lives in
   `_cache\`, which the repo does not ignore; it carries absolute paths). It is
   meant to be deleted at any time: the next run is simply a cold one.
6. **A cached step still counts as a step.** It is counted in `steps`, in
   `gate`/`control`/`skipped` exactly as before, and the summary says how many
   were reused. A reader who wants to know what actually EXECUTED has to look
   for the `  (cached)` marker on the beacon.
7. **The battery must not be edited while a run is in progress** — not even by
   this lane. cmd.exe resumes a batch file by BYTE OFFSET, so a concurrent edit
   makes the run lie (documented in `AGENTS.md`, reproduced there in 2026-10-08).
   The patch was applied between runs, never during one.
