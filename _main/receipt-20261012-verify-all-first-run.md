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
The exact failing arm is not yet named; that is the first measurement of the next round.

## What this changes about the objective

The last clause — "a clean, single-summary `_main/_audit-verify-all.cmd` run at exit code 0" — was
recorded for several rounds as BLOCKED BY THE OWNER ORDER. It is not blocked: the script starts nothing,
so it can run, and it now RUNS and reports **3 red steps with their causes**. The clause is unmet for a
different reason than assumed: three steps are red, two of them instruments that have gone stale against
code that moved (one of those is a battery semantics error, not an instrument error).

## Instruments added or extended this round

* `_main/verify-all-launch-audit.py` (NEW) — the precondition for running the battery; 41 steps, 0
  launchers; in the instrument battery as `verify-all starts nothing`.
* `_main/unfinished-items-coverage-oracle.py` — unchanged this round; still the enumeration gate.
