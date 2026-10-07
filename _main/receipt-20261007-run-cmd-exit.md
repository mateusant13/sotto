# Receipt — `_main/run-cmd-exit-oracle.py` (the suite's third RED)

- lane: `SottoRunCmdExit`
- date: 2026-10-07
- target: `H:/sotto/_main/run-cmd-exit-oracle.py` (52152 B, the biggest oracle in the tree)
- suite context: `py -3 _main/_cura-oracle-suite.py` returned `SUITE: GREEN=13, RED=3`; this oracle was RED (rc=1)
- repo: `H:/sotto` only. No `I:/!manager` / omp file was edited. `I:/!manager/scripts/*` were only *read/run* (the two mandated reporting scripts).

## VERDICT — STALE ORACLE (instrument drift), not an app defect — FIXED

The oracle's rc=1 was **not** the wrapper's or the app's fault. The oracle's two
tree-builders copy a **hand-listed** set of the shell's files:

| builder | old copy list | what the shell actually imports |
|---|---|---|
| `build_tree` (the G1..G4 gap arms) | `('hot_reload.py', 'stage.html')` | `hot_reload`, **`panel_state`** (sotto_webview.py:54) |
| `build_reverted_copy` (`--neg-arm`) | `('sotto_webview.py','hot_reload.py','stage.html')` | same |

`panel_state.py` is a sibling the shell imports at module scope. With it absent
from a copy, the copied shell dies **before `main()`** with:

```
Traceback (most recent call last):
  File "…\_gaps-g1-after-…\app\webview\sotto_webview.py", line 54, in <module>
    import panel_state
ModuleNotFoundError: No module named 'panel_state'
```

→ the interpreter's own **rc 1**. Consequences (both measured):

- **G1 panel-absent** expected `after rc=3` (the shell's `PANEL_MISSING` class) but read
  `rc=1` → `GAP-VERDICT FAIL` → the whole oracle `rc=1`. **This is the deterministic
  cause of the suite's RED.**
- **G2 pywebview-absent** expected `rc=1` and *passed* — **for the wrong reason**: its
  rc=1 was the same import crash, not the shadowed `webview`. (A vacuous green, closed
  by the fix: G2's stdout now names `PYWEBVIEW_IMPORT_FAILED ImportError: pywebview is
  not installed (gaps oracle G2)`.)
- **`--neg-arm`** (the documented control pair) ALSO failed the same way:
  `ARM-VERDICT FAIL failed=['bogus','help','start-default','start-logged']` — arms 3/4
  read *"the app's OWN first line is in the run log :: (no `shell=webview2 … pid=` line)"*
  because the reverted copy's shell crashed at import.

The app itself is CORRECT. Proven with a **properly-complete copy** (panel.html absent,
`panel_state.py` present, created by hand, outside the oracle):

```
$ py -3 <proper-copy>/app/webview/sotto_webview.py --check-args --show ; echo rc=$?
sotto: PANEL_MISSING path=H:\sotto\_main\_g1fix-manual\app\electron\panel.html
PROPER_COPY_CHECKARGS_RC=3
```

## THE TIMEOUT CEILINGS I APPLIED (and why the hang cannot recur)

| ceiling | value | where |
|---|---|---|
| my outer tool ceiling | **600 s** per invocation | `bash timeout:600` |
| the suite's own ceiling | 300 s | `_main/_cura-oracle-suite.py:50` |
| the oracle's per-`run_wrapper` ceiling | 120 s (default) | `run-cmd-exit-oracle.py:262` |
| G3 hang arm bound | `SOTTO_READY_BOUND=5` → ~5 s | `GAP_BOUND_S='5'`, oracle:132 |
| `arm_start` waits | `exit_after+12 s` (SHELL_EXIT) / `exit_after+10 s` (pid gone); default `--exit-after 8.0` | oracle:551,561 |

**Observed wall time: 43–47 s** per full run — far under every ceiling. The
`run.cmd --with-worker` self-hang AGENTS.md forbids **cannot recur here**: the wrapper's
readiness wait is BOUNDED (`--wait-ready`, default 30 s / `SOTTO_READY_BOUND`), and G3
*proves* it by driving a never-ready stub to `rc=4 HANG` in ~5.5 s, with BEFORE=0 as the
control. No arm runs `--with-worker` against the real worker; arms 3/4 pass
`--no-hotkey --no-hot-reload --exit-after 8`.

## OUTPUT VERBATIM — the target run (rc=1, unmodified oracle, `H:/sotto`)

```
RUN-CMD EXIT ORACLE label=fixed pid=37828
RUN-CMD run_cmd=H:\sotto\app\webview\run.cmd
RUN-CMD run_cmd_sha256=8951e69c3b758fb05b9ca4a17f35a27b0556c6042e65d7ec232994e0bb5d367b
RUN-CMD under_test_sha256=8951e69c3b758fb05b9ca4a17f35a27b0556c6042e65d7ec232994e0bb5d367b (the live wrapper; equal means "the fix is under test")
RUN-CMD preflight_in_under_test=True
RUN-CMD shell_sha256=64b563429a6f0787b860ab9c058aca98fb3b32ee9f0ec15d9d9093ffed5de1b2 shell_mtime=1791295234
ARM argv          rc=0 want=0 ms=0 PASS
    [ok] ['no args (double-click)'] -> accepted by the pre-flight :: rc=0 argv=[]
    [ok] ['README.md: --show --with-worker'] -> accepted by the pre-flight :: rc=0 argv=['--show', '--with-worker']
    [ok] ['webview-app-20261006.md: --selftest --log'] -> accepted by the pre-flight :: rc=0 argv=['--selftest', '--log', 'H:\\sotto\\_main\\_runcmd-argv-arm-015220.log']
    [ok] ['webview-app-20261006.md: --exit-after 25'] -> accepted by the pre-flight :: rc=0 argv=['--exit-after', '25']
    [ok] ['runcmd-entry-driver.py ARM caption'] -> accepted by the pre-flight :: rc=0 argv=['--with-worker', '--log', 'H:\\sotto\\_main\\_runcmd-argv-arm-015220.log', '--no-hotkey', '--no-hot-reload', '--exit-after', '60']
    [ok] ['the --dump-dom measurement path'] -> accepted by the pre-flight :: rc=0 argv=['--dump-dom', '--log', 'H:\\sotto\\_main\\_runcmd-argv-arm-015220.log']
    [ok] ['the --memory / --opaque flags'] -> accepted by the pre-flight :: rc=0 argv=['--memory']
    [ok] ['the --memory / --opaque flags'] -> accepted by the pre-flight :: rc=0 argv=['--opaque']
ARM bogus         rc=2 want=2 ms=380 PASS
    [ok] rc == 2 (the child's own argparse status, passed through) :: rc=2
    [ok] the wrapper says so on its own console :: run.cmd: the shell REFUSED this launch (rc=2). Nothing was started.
    [ok] a receipt line is appended to the run log (before the fix this arm appended NO bytes at all) :: 'sotto: PREFLIGHT_REFUSED rc=2 by=run.cmd-preflight'
    [ok] nothing was started: no `shell=webview2` line appended :: appended_bytes=52
    [ok] no process is left behind in this tree :: leftovers=[]
ARM help          rc=0 want=0 ms=376 PASS
    [ok] rc == 0 :: rc=0
    [ok] the console interpreter printed the usage header :: ['usage: sotto-webview [-h] [--show] [--hotkey HOTKEY] [--no-hotkey]']
    [ok] every flag the shell declares is in the usage (19/19) :: none missing
    [ok] the pre-flight switch stays OUT of --help :: hidden
    [ok] no process is left behind in this tree :: leftovers=[]
ARM start-logged  rc=0 want=0 ms=3108 PASS pid=25348
    [ok] rc == 0 :: rc=0
    [ok] the wrapper returned BEFORE the app exited (the wait is the bounded READINESS handshake, not the 8.0s lifetime) :: wrapper_ms=3108 app_lives=8.0s
    [ok] the app's OWN first line is in the run log, with its pid :: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=25348
    [ok] the published pid (25348) was a real, running process :: pid=25348 alive=True
    [ok] the app reached its own clean exit (SHELL_EXIT line) :: SHELL_EXIT rc=0
    [ok] the READINESS boundary (PRELOAD_ACTIVE -- what the G3 handshake keys on) was crossed in the log :: PRELOAD_ACTIVE hasSotto=true
    [ok] no leftover: the published pid is gone :: pid=25348 gone=True
ARM start-default rc=0 want=0 ms=2330 PASS pid=26044
    [ok] rc == 0 :: rc=0
    [ok] the wrapper returned BEFORE the app exited (the wait is the bounded READINESS handshake, not the 8.0s lifetime) :: wrapper_ms=2330 app_lives=8.0s
    [ok] the app's OWN first line is in the run log, with its pid :: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=26044
    [ok] the published pid (26044) was a real, running process :: pid=26044 alive=True
    [ok] the app reached its own clean exit (SHELL_EXIT line) :: SHELL_EXIT rc=0
    [ok] the READINESS boundary (PRELOAD_ACTIVE -- what the G3 handshake keys on) was crossed in the log :: PRELOAD_ACTIVE hasSotto=true
    [ok] no leftover: the published pid is gone :: pid=26044 gone=True
GAPS the before/after pairs of docs/audit/launch-entry.md §2 (BEFORE = a copy whose shell+wrapper are the pre-fix bytes)
GAP G1 panel-absent        FAIL want=non-zero (3); before=0
  after  rc=1 ms=450 args=['--show']
  before rc=0 ms=278 args=['--show']
    [ok] AFTER: run.cmd REFUSES the launch (non-zero) :: rc=1
    [NO] AFTER: the refusal is rc 3 -- the SAME status the app exits with :: rc=1 want=3 stdout='run.cmd: the shell REFUSED this launch (rc=1). Nothing was started.\nrun.cmd: rc=2 is a bad flag, rc=3 a missing panel, rc=1 a missing pywebview. "run.cmd --help'
    [ok] AFTER: nothing was started (no shell line in this copy's log) :: log_bytes=52
    [ok] BEFORE: the pre-fix wrapper answered 0 -- the failure AS SUCCESS :: rc=0
    [ok] BEFORE: the app really did fail (its own log carries PANEL_MISSING) :: ['sotto: PANEL_MISSING path=H:\\sotto\\_main\\_gaps-g1-before-ernzz81z\\app\\electron\\panel.html']
GAP G2 pywebview-absent    PASS want=non-zero (1); before=0
  after  rc=1 ms=428 args=['--show']
  before rc=0 ms=259 args=['--show']
    [ok] AFTER: run.cmd REFUSES the launch (non-zero) :: rc=1
    [ok] AFTER: the refusal is rc 1 -- the status the app would exit with :: rc=1 want=1 stdout='run.cmd: the shell REFUSED this launch (rc=1). Nothing was started.\nrun.cmd: rc=2 is a bad flag, rc=3 a missing panel, rc=1 a missing pywebview. "run.cmd --help'
    [ok] AFTER: nothing was started (no shell line in this copy's log) :: log_bytes=52
    [ok] BEFORE: the pre-fix wrapper answered 0 -- the failure AS SUCCESS :: rc=0
    [ok] BEFORE: the app started anyway (pre-fix shell logged its first line) :: ['sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=38656']
    [ok] BEFORE: the PRE-FIX SHELL exits 1 with no pywebview (measured direct) :: rc=1 err_tail=['ImportError: pywebview is not installed (gaps oracle G2)']
GAP G3 hang                PASS want=non-zero (4); before=0
  after  rc=4 ms=5472 args=['--show']
  before rc=0 ms=241 args=['--show']
    [ok] AFTER: run.cmd reports a HANG -- rc 4, not 0 :: rc=4 want=4 ms=5472
    [ok] AFTER: the wrapper wrote its OWN HANG receipt to the run log :: ['sotto: HANG rc=4 by=run.cmd-readiness']
    [ok] AFTER: the app really had been started and never came up (STAGING_LOADED, no ready file, no PRELOAD_ACTIVE) :: ['sotto: STAGING_LOADED core=yes -> navigating to panel (G3 STUB never-ready)']
    [ok] BEFORE: the pre-fix wrapper answered 0 for the SAME hang :: rc=0
    [ok] BEFORE: the same stub had been started and never came up :: ['sotto: STAGING_LOADED core=yes -> navigating to panel (G3 STUB never-ready)']
GAP G4 console-fallback    PASS want=non-zero (3); before=0
  after  rc=3 ms=124 args=['--show']
  before rc=0 ms=147 args=['--show']
    [ok] AFTER: run.cmd exits 3 when pythonw.exe is absent :: rc=3 want=3 ms=124
    [ok] AFTER: it NAMES the refusal, so the owner is not left guessing :: ['run.cmd: no pythonw.exe beside H:\\sotto\\_main\\_gaps-g4-after-tgqmoo6i\\fakepy\\python.exe.', 'run.cmd: refusing to fall back to python.exe -- that opens a console window.']
    [ok] AFTER: nothing was started (no shell line in this copy's log) :: log_bytes=0
    [ok] AFTER: the fallback assignment is GONE from the wrapper under test (checked on the ACTIVE lines -- a REM quoting it does not count) :: absent
    [ok] BEFORE: the pre-fix wrapper still carries the console fallback :: present (the defect)
    [ok] BEFORE: it proceeded past the missing pythonw and answered 0 :: rc=0
CENSUS cadence_ms=100 samples=268 visible_samples=0 tracked_pids=85
CENSUS-GAPS samples=76 visible_samples=0 (the gap phase, where a window is the DEFECT being demonstrated)
CENSUS OK: no visible window in 268 samples of this run's own pids during the ARMS phase (the census primitives are the repo's)
ARM-VERDICT    PASS  all 4 arms green
GAP-VERDICT    FAIL  failed gaps=['G1 panel-absent']
CENSUS-VERDICT PASS  268 samples, 0 with a visible window
ARM-RCS bogus=2(want 2) help=0(want 0) start-logged=0(want 0) start-default=0(want 0) argv=0(want 0)
GAP-RCS G1 panel-absent        after=1 before=0
GAP-RCS G2 pywebview-absent    after=1 before=0
GAP-RCS G3 hang                after=4 before=0
GAP-RCS G4 console-fallback    after=3 before=0
VERDICT FAIL  arms=PASS gaps=FAIL census=PASS -> the arms/gaps failed (see the [NO] lines above)
RECEIPT H:\sotto\_main\run-cmd-exit-oracle-fixed.json
```

`rc=1` (the tool's own `EXIT=$?`). Full log: `_main/_runcmd-oracle-20261007.stdout.txt`.

## OUTPUT VERBATIM — after the fix (both call sites)

Plain run (`_main/_runcmd-oracle-20261007-final.stdout.txt`), the G1 gap and verdicts:

```
GAP G1 panel-absent        PASS want=non-zero (3); before=0
  after  rc=3 ms=417 args=['--show']
  before rc=0 ms=287 args=['--show']
    [ok] AFTER: run.cmd REFUSES the launch (non-zero) :: rc=3
    [ok] AFTER: the refusal is rc 3 -- the SAME status the app exits with :: rc=3 want=3 stdout='sotto: PANEL_MISSING path=H:\\sotto\\_main\\_gaps-g1-after-5ooxkzji\\app\\electron\\panel.html\nrun.cmd: the shell REFUSED this launch (rc=3). Nothing was started.\nrun'
…
CENSUS cadence_ms=100 samples=261 visible_samples=1 tracked_pids=96
CENSUS ALERTA-JANELA 23392:29237684 pid=23392 hwnd=29237684 title='Sotto' class='WindowsForms10.Window.8.app.0.aec740_r16_ad1' n=1
CENSUS-GAPS samples=74 visible_samples=0 (the gap phase, where a window is the DEFECT being demonstrated)
CENSUS RED: 1 of 261 samples had a VISIBLE window in this run's tree during the ARMS phase
ARM-VERDICT    PASS  all 4 arms green
GAP-VERDICT    PASS  all 4 gaps green (AFTER non-zero, BEFORE 0)
CENSUS-VERDICT FAIL  261 samples, 1 with a visible window
ARM-RCS bogus=2(want 2) help=0(want 0) start-logged=0(want 0) start-default=0(want 0) argv=0(want 0)
GAP-RCS G1 panel-absent        after=3 before=0
GAP-RCS G2 pywebview-absent    after=1 before=0
GAP-RCS G3 hang                after=4 before=0
GAP-RCS G4 console-fallback    after=3 before=0
VERDICT FAIL  arms=PASS gaps=PASS census=FAIL -> a VISIBLE window was measured (app-side, see CENSUS ALERTA-JANELA above)
```

`--neg-arm` control, after the fix (`_main/_runcmd-oracle-20261007-final-neg.stdout.txt`):

```
CENSUS OK: no visible window in 261 samples of this run's own pids during the ARMS phase (the census primitives are the repo's)
ARM-VERDICT    PASS  arm1(bogus) RED-as-expected=True arms2-4-still-green=True failed=['bogus']
ARM-NOTE       the argv arm is VACUOUS in this copy: the pre-fix wrapper has no pre-flight …
GAP-VERDICT    PASS  all 4 gaps green (AFTER non-zero, BEFORE 0)
CENSUS-VERDICT PASS  261 samples, 0 with a visible window
VERDICT PASS  all conjuncts green
```

(The same `--neg-arm` BEFORE the fix was `ARM-VERDICT FAIL failed=['bogus','help','start-default','start-logged']`, full log `_main/_runcmd-oracle-20261007-neg-before.stdout.txt`.)

## THE RESIDUAL — a SEPARATE, app-side conjunct the oracle honestly reports

The oracle's final verdict is the conjunction of **three independent claims**
(`arms_ok and census_ok and gaps_ok`). My fix clears **ARM** and **GAP** deterministically.
**CENSUS is a different claim**: *"no visible window in this run's own pids"*, and it can go
RED because the app itself flashes its panel at startup — the fact AGENTS.md already owns
(the panel is `WS_VISIBLE` for ~50 ms in ~18/20 launches at a 25 ms cadence, up to ~7 s on
unlucky starts; an app-side race, NOT a wrapper behaviour, and the oracle's own comment says a
census RED must never be read as "the wrapper failed").

Measured in my post-fix plain runs (cadence 100 ms):

| run | rc | CENSUS |
|---|---|---|
| after build_tree fix | 0 | 0 / 262 |
| final | **1** | **1 / 261** (`title='Sotto'`, pid 23392 → the app-side flash) |
| flake-1 | 0 | 0 / 264 |
| flake-2 | 0 | 0 / 259 |

So 3 of 4 post-fix runs went **`VERDICT PASS, all conjuncts green`**; the one rc=1 was the
**app-side CENSUS** flash, not a wrapper or oracle-instrument failure. I did **not** silence
that conjunct — it is a TRUE positive about the shell, owned by the panel-startup-flash lane
(`_main/panel-startup-flash-census.py`), and outside this oracle's (and this lane's) contract.

## CHANGED — sha256

Only ONE file was edited, by me:

| file | before | after |
|---|---|---|
| `_main/run-cmd-exit-oracle.py` | `5f43d7f296488c27ff87f41dc5aec9330e1be1a8e077f2857ff1b967de4ae5cb` | `10f78a3d3e3da0a73e09b048cc26109375fdc345c59a3ba04582b2b8143e361c` |

(intermediate, after the `build_tree` fix alone: `8db2f563fad4b7bb7c0a14330790667833d8b07ce4d137f2440d51d8a2299c76`)

Not changed (pinned in the runs): `app/webview/run.cmd` = `8951e69c…`, `app/webview/sotto_webview.py`
= `64b56342…`, `app/webview/panel_state.py` = `c7811e17…`.

The diff, both call sites (`build_tree` @:600 and `build_reverted_copy` @:864):

```diff
-    for name in ('hot_reload.py', 'stage.html'):
-        shutil.copy2(os.path.join(src_web, name), os.path.join(web, name))
+    # The copy must carry the shell's IMPORT CLOSURE, not a hand-listed pair.
+    # … the old list drifted the moment the shell grew `import panel_state`
+    # (sotto_webview.py:54): every gap copy then died with ModuleNotFoundError
+    # -> rc 1 BEFORE it could reach the check under test. Copy every `.py`
+    # sibling so a new module is carried automatically.
+    for name in sorted(os.listdir(src_web)):
+        if name.endswith('.py') or name == 'stage.html':
+            shutil.copy2(os.path.join(src_web, name), os.path.join(web, name))
```
(the identical rule replaces the hand-listed trio in `build_reverted_copy`.)

Scratch: I removed my own `_main/_g1fix-manual/` and the oracle's own abandoned
`_main/_gaps-*` copies (64 dirs → 0; `git status` lines 191 → 127). No non-scratch file was deleted.

## SELF-AUDIT

- **protocolos em falta:** The `--neg-arm` is the *documented* control pair that AGENTS.md pairs with this
  oracle ("both colours in ONE command"), and I ran only the plain run first, discovering the second
  (identical) drift site in `build_reverted_copy` only after fixing the first. What I would do
  differently: when a copy-based instrument is repaired, enumerate ALL its copy sites in the same
  invocation (`shutil.copy|mkdtemp|copytree` in one grep) before editing, not after.
- **verificacao adicional:** (ran) the `--neg-arm` control → it exposed the second call site;
  (ran) 4 post-fix plain runs to characterise the census flake. (not ran, cost named) pinning the
  app-side flash with the 25 ms instrument `_main/panel-startup-flash-census.py` — it launches ≥20
  shells, i.e. ≥20 panel flashes on the owner's screen, refused under the window rule.
- **checkboxes novas (MECHANIC):** (1) **copy-closure parity** — for any instrument that builds a
  detached copy of `app/webview`, assert the copied `.py` set ⊇ the shell's local imports
  (`grep '^import ' app/webview/sotto_webview.py` → {`hot_reload`,`panel_state`}); RED input: the
  pre-fix oracle's list `{hot_reload.py, stage.html}`. (2) **import-smoke before exit-code assertion**
  — a gap arm must first assert the COPY's shell can run (`--check-args`), so a copy that cannot even
  import fails as a COPY error, not as a wrong exit code in arm G1; RED input: today's pre-fix G1 copy.
- **review por outro subagente:** sim-com-escopo — a reviewer should re-run
  `py -3 _main/run-cmd-exit-oracle.py` and `… --neg-arm`, and confirm the CENSUS conjunct is the
  AGENTS.md app-side startup flash rather than a wrapper regression.
- **gate-doubt:**
  - *verde-de-verdade:* the post-fix GREEN is not vacuous — G1's AFTER rc=3 carries a second,
    independent observation (the shell's own `PANEL_MISSING path=…` line, and BEFORE=0 with the
    copy's log carrying `PANEL_MISSING`). The vacuity I FOUND is the opposite direction: **G2's rc-1
    expectation was passing VACUOUSLY pre-fix** — its rc-1 was the `panel_state` import crash, not
    the shadowed pywebview; the fix changed G2's stdout to `PYWEBVIEW_IMPORT_FAILED ImportError`.
    The CENSUS PASS runs (0/262, 0/264, 0/259) are the *documented* not-absence trap ("0 visible in N
    samples" ≠ absent, AGENTS.md) — which is exactly why the 1/261 catch is reported, not averaged away.
  - *falta-no-gate:* the oracle has **no arm that asserts a COPY can import itself**, so a
    tree-builder drift surfaces as a wrong exit code in an unrelated arm (G1 looked like "the gap
    failed" when the copy could not load at all). Scenario a future change crosses: someone renames
    or adds a third sibling module and the hand-list is not updated → G1 flips RED for a non-reason
    while G2 stays GREEN vacuously.
  - *gate-melhor:* the copy-closure parity check above, as a refusal inside `build_tree` /
    `build_reverted_copy` — after building the copy, compare its `.py` set to the shell's local
    imports and refuse if short. RED input: the pre-fix oracle on today's shell
    (copy `{hot_reload,stage.html}` vs imports `{hot_reload,panel_state}`).
- **confianca:** **alta** for the diagnosis (the `ModuleNotFoundError` traceback and the
  proper-copy `rc=3` are each measured in isolation); **media** that a suite re-run goes fully green —
  it also depends on the app-side census flash not firing (~1 in 4 at 100 ms cadence, measured).
- **nao verificado:** (a) whether Main's original suite rc=1 for this oracle was G1 or the census — I
  reproduced rc=1 with G1 (census 0 in that run), but Main's stdout was not in my hands; (b) the
  app-side panel-flash cure (owned by the panel-startup-flash lane, out of this lane's scope);
  (c) exact per-model price rates (UNKNOWN — not present in the session JSONL).

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: SottoRunCmdExit
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoRunCmdExit.jsonl
- cache: read=6076544 write=0 hit=96.8252% (cache-read / input+cache-read); universe: 43 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoRunCmdExit.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=41 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: … vs $0.00000000 over …
- when-failed: break_items=3; WHEN=2026-10-07T04:51:28.688000+00:00 | break_items=3; WHEN=2026-10-07T04:51:29.380000+00:00 | break_items=2; WHEN=2026-10-07T04:53:27.696000+00:00 | break_items=2; WHEN=2026-10-07T04:58:29.082000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 125941 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoRunCmdExit']; window: 2026-10-07T04:51:28.688000+00:00..2026-10-07T04:58:29.082000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a114b3-9406-7791-b787-b2fb158be5c2 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791348688688 | … provider=deepseek-flash … item_index=0; turn_id=1791348689380 | … item_index=54; turn_id=1791348807696 | … item_index=135; turn_id=1791349109082 (state=RESOLVED-BREAKS-OMP; …)
- report generated_at: 2026-10-07T05:01:08.365227+00:00
- usage rows: 43
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 199244
- output tokens: 36852
- cache-read tokens: 6076544
- cache-write tokens: 0
- hit ratio: 96.8252% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 10 (state=RESOLVED-BREAKS-OMP; …)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

(full output: `artifact://7490`; command `bash I:/!manager/scripts/cache-task-report.sh SottoRunCmdExit`)
