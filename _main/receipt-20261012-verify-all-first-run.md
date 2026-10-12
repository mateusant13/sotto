# Receipt — the first run of `_main/_audit-verify-all.cmd` in this session (2026-10-12)

## Why this run was allowed at all

The owner order forbids opening Sotto: *"para de abrir o sotto, ta travando meu pc quando ele abre."*
The battery was therefore treated as forbidden, because a sibling tree documents it as launching the shell
dozens of times. THAT CLAIM IS FALSE FOR THE PRODUCT-ROOT COPY, and I measured it before running anything:

`_main/verify-all-launch-audit.py` (new, reads only) walks EVERY step the script declares — all four kinds
(gate, control, skipped, expect-red) — takes the command line above each `call :<kind>`, and looks for
launcher signatures (`run.cmd`, `pythonw`, `--dump-dom`, `--arm-e-real`, `--show`, `Start-Process`,
`start /`, `_live-launch`), with an explicit safe-use list for commands that only READ the app file
(`py_compile`, `--autostart-status`, `--check-args`, `--help`). Measured: **41 steps, 0 launcher
signatures** → `VERDICT: PASS`, rc=0. The step that WOULD touch the owner app (`hotkey-delivery`) is
declared skip-capable and verified itself as a gate this run.

SAFETY CONFIRMED AFTER THE RUN, not assumed: `Get-CimInstance Win32_Process` (via a `.ps1` FILE, because
the inline form returns empty on this box) shows **0** python processes matching `sotto_webview|sotto_worker`
and **19** `msedgewebview2.exe` whose parents are WhatsApp, SearchHost, Widgets and two self-parented
trees — none of them mine. Nothing was left running and no window was left on the desk.

## What the battery reported

```
steps    : 41   gate=31  control=9  skipped=0  expect-red=1  missing=0
failed   :  strip-surface-oracle=3 autostart-status=1 control-redux-flag-neg-arm=1
skipped  : -none-
BATTERY-VERDICT: RED - 3 step(s) failed
```

Exit code **1**. Single summary, as the objective asks for — but not clean, so the objective is NOT met
yet. The three reds, each diagnosed to a first cause with its evidence:

### 1. `autostart-status` rc=1 — THE EXIT CODE IS THE STATUS. This is a FALSE RED in the battery step.

`app/webview/sotto_webview.py:2435-2452` (`autostart_status`) returns **1 when there is no Run value**
("autostart is off"), 2 on an OSError, 0 when the value matches this checkout, 3 when it is on but points
elsewhere. Reproduced by hand: `python app\webview\sotto_webview.py --autostart-status` → rc=1 with exactly
four lines, the last being `sotto: AUTOSTART=off (no Run value)` — the query WORKED. The battery records
this step as a plain gate (`:record`), i.e. it demands rc=0, so a healthy "off" machine is reported as a
failure. The fix belongs in the step semantics (accept 0 and 1, still fail on 2 and 3), never in the
registry: installing autostart to make a gate green would change the owner machine without being asked.

### 2. `strip-surface-oracle` rc=3 — the instrument is STALE, the shipped code is right.

Its real arm fails with `stats.empty: got {'tag': 'stats'}, expected {}` and four siblings. The shell
stamps that field ON PURPOSE: `sotto_webview.py:5941` `payload['tag'] = (fields.get('tag') …) or 'stats'`,
with its own comment at `:5938-5940` explaining that copying only peak/blocks THREW THE TAG AWAY. So the
oracle predates a deliberate payload addition and must be rebaselined to expect the tag (its control arms
still go RED correctly, which is why the step is a `:control` and not a silent pass).

### 3. `control-redux-flag-neg-arm` rc=1 — the mutant arm did not go RED.

The log shows every `[shipped]` arm True (flag-guarded, env-optin, switch-wired, stamp, hard-rule,
fail-safe), so the shipped file passes and the CONTROL copy failed to catch it. Detail to note for the next
step: `_main/_audit-verify/control-redux-flag-neg-arm.log` is **not valid UTF-8** (CP1252 bytes), and this
session file reader refuses it — the next measurement must read it as bytes or with the console encoding.
**RESOLVED the same day, and my first reading above was wrong.** The banner said `[shipped] VERDICT RED (12/13 claims hold) — failing: hard-rule`, so the mutant never RAN: `--neg-arm` exits 1 because the SHIPPED pair failed a claim, not because a mutant failed to flip. `claims["hard-rule"] = bool(armed) and refused` held `refused=True` and `armed=False`, and the cause was a stale anchor: the live worker now reads `self.armed = bool(` / `self.enabled and self.runner_available and self.model_available)` — a THIRD condition, wrapped across two lines — so the gate single-line regex matched nothing. Rebaselined to the meaning (flag AND runner, extra conditions allowed) and its mutant anchor likewise (the one-line substring, dropping the runner/model conditions). After: shipped GREEN 13/13 and 12/12 mutants built, each RED on its own claim.

## What this changes about the objective

The last clause — "a clean, single-summary `_main/_audit-verify-all.cmd` run at exit code 0" — was
recorded for several rounds as BLOCKED BY THE OWNER ORDER. It is not blocked: the script starts nothing,
so it can run, and it now RUNS and reports **3 red steps with their causes**. The clause is unmet for a
different reason than assumed: three steps are red, two of them instruments that have gone stale against
code that moved (one of those is a battery semantics error, not an instrument error).

## THE GREEN RUN — same day, after three fixes

```
steps    : 41   gate=31  control=9  skipped=0  expect-red=1  missing=0
failed   : -none-
skipped  : -none-
BATTERY-VERDICT: GREEN - every step held and every control went RED on its broken copy
```

Exit code **0**, one summary. What each fix was:

1. `_main/autostart-status-check.py` (NEW) + one command line in the battery. The exit code IS the status
   (1 = off), so a plain gate painted a healthy machine red. The wrapper reads the registry itself (key and
   value names parsed from the shell source so they cannot drift), ALSO runs the shell own
   `--autostart-status` and requires the two to AGREE, exits 0 for the two valid states, 3 for another
   checkout, 4 on disagreement. Measured: state=off, shell rc=1, agree, step green. Autostart was NOT
   installed — changing the owner machine to turn a gate green is not a fix.
2. `_main/_strip-surface-oracle.py` — six expectation sites rebaselined to the payload the shell
   DELIBERATELY stamps (`tag`), cited to `:5941`/`:5938-5940`. After: rc=0, `STRIP-ORACLE CONTROL PASS
   broken-copies-red=4 arms=109`.
3. `_main/redux-flag-gate.py` — the stale `hard-rule` anchor and its mutant anchor, as described above.

Safety re-measured after BOTH runs: 0 python processes matching sotto_webview|sotto_worker; the 19
WebView2 trees belong to WhatsApp, SearchHost and Widgets. The battery starts nothing, twice over.

Also verified after the fixes: map gate GREEN 135 applied / 1 open; instrument battery 75/75 rc=0;
launch audit PASS (41 steps, 0 launcher signatures). The battery keeps CRLF: 32637 B, 538 CRLF, 0 bare LF.

## Instruments added or extended this round

* `_main/verify-all-launch-audit.py` (NEW) — the precondition for running the battery; 41 steps, 0
  launchers; in the instrument battery as `verify-all starts nothing`.
* `_main/unfinished-items-coverage-oracle.py` — unchanged this round; still the enumeration gate.
