# Receipt — the battery tells the truth about itself (lane `SottoBatteryHonest`, 2026-10-08)

**One file changed by hand:** `_main/_audit-verify-all.cmd` — 26 692 B (456 CRLF, 0 bare LF), sha256
`038B5167B193E672BCB5A2FD1A3BE0D28B307D1E3D327A722095D2F0A2DF41BD`, **CRLF line endings
(required — see §2)**. Revision history of this file today, all CRLF: `9DA38ECF…` / 18 595 B = 29
steps (the first aggregating version); `649A6499…` / 20 690 B = 31 steps, after
`_panel2-repeat-probe.js` was repaired by another lane and wired here as a gate AND a control;
`038B5167…` / 26 692 B = **32 steps**, after the fourth step kind (`:skipped`) and the skip guard
landed (§4a).
Nothing else in the repo was edited: no `worker/**`, no `app/**`, no gate/probe/instrument file, no
doc other than this receipt. The instruments named in the brief and the repair lane's probe
(`verdict-gate.py`, `history-producer-gate.js`, `_panel2-repeat-probe.js`) were read and run, never
touched.

The defect this lane was given, restated so the fix can be read against it: the battery printed
each step's rc and then `exit /b 0` **unconditionally**, so a run with three red steps
(`hotkey-delivery` rc=1, `verdict-gate` rc=2, `history-producer-gate` rc=1) exited 0. The file
everyone quotes as "the battery is green" could report success while steps were red.

---

## 1. The aggregation

Four kinds of step, because one number cannot mean two things — and because a SKIP is neither:

| kind | recorder | passes when |
|---|---|---|
| **gate** | `:record <name> <rc>` | rc = 0 |
| **control** | `:control <name> <rc> <log> <text> [<text2>]` | rc = 0 **AND** the log carries the instrument's own control verdict (`CONTROL PASS`, `NEG-VERDICT: GREEN`, `NEGARM : PASS`, `neg_arm_e`). These steps succeed only by catching a deliberately-broken COPY, so **a control that does not go red is a FAILURE** — and so is an rc=0 with no verdict in the log. The optional second text demands a second independent fact from the same run. |
| **skipped** | `:skipped <name> <rc> <log> <verified-text> <skip-text> [<skip-text2>]` | rc = 0 **AND** one of exactly two verdicts: the instrument's **skip** verdict → counted in `skipped=`, listed, and **NEVER** in `gate=`, because nothing was verified; or its **verified** verdict → counted as a real gate. **rc≠0, MISSING, half a skip verdict, or neither verdict is a FAILURE.** See §4a. |
| **expect-red** | `:expectred <name> <rc> <log> <text…>` | rc **= 1** (the defect found) **AND** the violation text. An instrument with no control wrapper of its own (`--gate-off`). rc=0 means the control did not go red; rc=2 is a setup error. Both are failures. |

* Every step's rc is passed to its recorder as an argument, so no step can print a beacon without
  being counted. The rc is read with `!ERRORLEVEL!` **inside** the `if exist ( )` blocks under
  `setlocal EnableDelayedExpansion` — the reporter fix already landed stays intact.
* **A MISSING instrument is a failure**: `else ( call :record name MISSING )` records rc=MISSING,
  increments the missing count and fails the run. It used to be a line on a screen.
* The text checks are done by `:hastext`, a `python -c` argv comparison over the log read as
  **bytes → UTF-8 with `errors=replace`**, so a console-codepage mojibake cannot hide a missing
  verdict. This was not hypothetical: two of the wired control logs (`control-redux-flag-neg-arm.log`,
  `control-history-producer-stamp-nvidia.log`) contain `�` where the instrument printed an em dash,
  and every required text was chosen ASCII for that reason. If python itself is unavailable the check
  fails closed.
* Summary: `steps / gate / control / skipped / expect-red / missing`, the **per-step rc list**, the
  **controls list with their rcs**, the **skipped list**, the **failed names**, the verdict, and the
  exit code. The same lines are written to `_main/_audit-verify/_battery-summary.txt`.
* **The exit code IS the aggregation**: `if not "!BAD!"=="0" exit /b 1` / `exit /b 0`. There is no
  other `exit /b` path that can return 0. A SKIPPED step does not fail the run — the environment made
  the arm unrunnable, which is not a defect of the instrument — but it is never printed as a gate
  either, and the verdict sentence says so in words.

**Clean run** — full text: `_main/_audit-verify/_run-20261008-clean.log` (32 steps, the revision
`038B5167…` above), exit code **0**, exactly **one** summary line in the whole console:

```
=============== BATTERY SUMMARY ===============
steps    : 32   gate=24  control=6  skipped=1  expect-red=1  missing=0
per-step :  pycompile-sotto_webview=0 pycompile-webview-helpers=0 pycompile-sotto_worker=0 pycompile-wasapi+lang=0 transcript-append-oracle=0 live-vs-history-source-oracle=0 historico-vs-redux-probe=0 history-producer-gate=0 panel-state-guard-gate=0 verdict-gate=0 lane2-reset-probe=0 lane3-verdict-probe=0 lane4-tap-stop-probe=0 audit-history-dead=0 panel2-repeat-probe=0 worker-start-wiring=0 embedded-js-check=0 lane1-worker-default-arms=0 review-f1f3=0 review-tapstop=0 hotkey-registration=0 hotkey-delivery=0 autostart-status=0 control-verdict-gate-unguard=0 control-history-producer-stamp-nvidia=0 control-redux-flag-neg-arm=0 control-panel-exit3-neg-arm=0 control-wasapi-com-init=0 control-panel2-repeat-revert=0 red-as-expected-historico-gate-off=1 fresh-processor-probe=0 skip-verdict-guard=0
controls :  control-verdict-gate-unguard(rc=0) control-history-producer-stamp-nvidia(rc=0) control-redux-flag-neg-arm(rc=0) control-panel-exit3-neg-arm(rc=0) control-wasapi-com-init(rc=0) control-panel2-repeat-revert(rc=0) red-as-expected-historico-gate-off(rc=1)
failed   : -none-
skipped  :  hotkey-delivery
BATTERY-VERDICT: GREEN WITH 1 SKIPPED - 1 step(s) did NOT verify this run and are NOT counted as gates:  hotkey-delivery
CLEAN-EXITCODE=0
```

(Earlier revisions are kept: `_run-20261008-clean-29steps-before-panel2.log` — `steps : 29 gate=23
control=5`; `_run-20261008-clean-31steps-before-skipped.log` — `steps : 31 gate=24 control=6`, the
same shape but with `hotkey-delivery` still counted as a gate.)

Every one of the 24 gates is rc=0 (the three reds of the pre-fix baseline are still fixed), all six
controls caught their copy, and the expect-red step found its defect. Note the two rcs that are **not
0 and are still passes** — `red-as-expected-historico-gate-off=1` is the instrument's own "violations
found" code, and the controls legitimately exit 0 while their logs say `RED` inside. The `[CONTROL]`
/ `[EXPECT-RED]` tag on the step line and the separate `controls :` line are what let a reader tell
them from ordinary gates.

**THE HONEST SENTENCE, AND IT IS THE WHOLE POINT OF §4a: today's green does NOT include "Alt+C reaches
its handler".** `hotkey-delivery` sits in `skipped=`, not in `gate=`, and it is printed on its own
`skipped :` line, because `_audit-hotkey-delivery.py` exits 0 with `VERDICT: SKIPPED — every arm that
could run held, but this run CANNOT claim "Alt+C reaches its handler"` while the owner's live shell
holds Alt+C (`ARM 1 ownership probe: Alt+C held=True winerror=1409`, `live Sotto shell pid=27492`).
The other arms of that probe — the fallback chain, the single-instance lock, the toggle rule — really
were exercised, and the probe says so in the same breath; only the delivery arm did not run.
**When the owner next closes the app, that same step prints `VERDICT: GREEN` and moves out of
`skipped=` into `gate=` (so the line becomes `steps : 32 gate=25 … skipped=0` and the verdict sentence
loses its `WITH 1 SKIPPED` clause). The transition is visible in the summary, never silent.**
Evidence: `_main/_audit-verify/hotkey-delivery.log`.

## 2. FIRST FINDING — the aggregating battery ran its list TWICE, and the cause was the line endings

The first run of the new file (written by a tool that emits `\n`) produced **two** summaries in one
run and executed steps out of order: pass 1 skipped 13 steps and reported `steps : 16 … GREEN`, then
cmd resumed and re-ran the skipped steps plus the whole tail, printing a second summary with
`steps : 40`. Two model loads, two of every control.

That was one observation, so it was **reproduced on demand** rather than asserted: a copy of the
shipped file whose ONLY differences are LF line endings and a private output dir (18 282 B, 337 LF,
**0 CRLF**, sha256 `992225C33412F9FD1E1B903B01EAE4BA6A13A287B01ED135F8094D9D08901C81`) ran exactly
the same way — **two** summaries (`steps : 16` then `steps : 40`), **40** `[step]` beacons for **28**
distinct step names. That copy was deleted; its console is kept verbatim at
`_main/_audit-verify/_run-20261008-LF-only-double-run.log`.

The shipped file, converted to CRLF with the same content and no other change (18 595 B, 337 CRLF,
sha256 `9DA38ECF…`), ran its list **once**: `steps : 29`, one summary, exit 0 —
`_main/_audit-verify/_run-20261008-clean-29steps-before-panel2.log`.

Cause, read off the mechanism and consistent with both measurements: the recorders are reached by
`call :label` / `exit /b`, and cmd seeks a batch file by **byte offset**. With 1-byte LF endings those
stored offsets drift, so the interpreter resumes at the wrong line. The rule is now in the file header
for whoever edits it next, because a battery that silently runs its list twice is the same defect
class as a battery that exits 0 on a red step: it answers a question nobody asked. It also means a
future edit that rewrites this file with `\n` re-breaks it — verify with a CRLF/LF count, not by
reading.

## 3. The negative proof (both colours, no real instrument touched)

A COPY of the shipped battery, `_main/_negproof-battery.cmd` (sha256
`DDEF3B7839984E638E08A353E9245CF88D85D622A45D0248B09F7103463622FC`, **deleted after the run**),
with exactly one step injected and a private output dir. It was rebuilt and re-run from the CURRENT
bytes after the panel2 steps were wired, so the proof holds for the shipped revision
`649A6499…` (the earlier 30-step run of the 29-step revision was superseded):

```
echo === NEGATIVE PROOF: one step injected to FAIL on purpose (cmd /c exit 3) ===
cmd /c exit 3
call :record INJECTED-FAILING-STEP !ERRORLEVEL!
```

Full text: `_main/_audit-verify/_run-20261008-negproof.log`. **Exit code 1**, and the step is named:

```
[step] INJECTED-FAILING-STEP rc=3  ** FAILED **
...
steps    : 33   gate=25  control=6  skipped=1  expect-red=1  missing=0
failed   :  INJECTED-FAILING-STEP=3
skipped  :  hotkey-delivery
BATTERY-VERDICT: RED - 1 step(s) failed
NEGPROOF-EXITCODE=1
```

Every real step still ran and still held (25/25 gates rc=0, all six controls red, the expect-red step
red by design, `hotkey-delivery` still the one declared skip), so the injected red is
the only thing that moved: the batch now says **no** and names the step. The copy was rebuilt from the
CURRENT bytes for this revision (sha256 `771D3080E611909742F07A7B4DD50AE1F19AEF83D70FEC621A5BF9AE2B74B2C9`);
the previous revision's run is kept at `_main/_audit-verify/_run-20261008-negproof-32steps-before-skipped.log`.

**The aggregation itself was rehearsed in both colours before the full run** (copies kept in
`_main/` during the rehearsal, deleted; consoles kept as
`_main/_audit-verify/_run-20261008-rehearsal-{clean,dirty}.log`). The clean rehearsal — 2 gates + 1
control + 1 expect-red — exited **0** with `BATTERY-VERDICT: GREEN`. The dirty rehearsal injected two
failing rc's, one MISSING instrument, **a control that exits 0 without its verdict**, and **an
expect-red step that did not go red** — it exited **1** and named all five:

```
failed   :  failing-step=3 also-failing=7 missing-simulated=MISSING rehearsed-control-stayed-green=0 rehearsed-did-not-go-red=0
BATTERY-VERDICT: RED - 5 step(s) failed
```

The two controls in that list are the brief's requirement, demonstrated rather than asserted: a
control that does not go red, and a RED-by-design instrument that stays green, are both failures here.
One rehearsal artefact worth keeping: the first rehearsal copy was placed OUTSIDE `_main/`, so
`%~dp0..` made ROOT wrong, every `if exist` went MISSING, and one instrument exited 1 by accident
(`Cannot find module`) — the `expect-red` text check caught it. **A copy of this battery must live in
`_main/`** or it is measuring a different tree.

## 4. Controls wired into the battery (7 steps: 6 `:control` + 1 `:expectred`)

Each name below is the step name in the summary; the logs live in `_main/_audit-verify/`.

| step | command | clean run | what proves it is a control |
|---|---|---|---|
| `control-verdict-gate-unguard` | `python _main\verdict-gate.py --control-unguard-captions-zero` | rc=0 | `_main/_audit-verify/control-verdict-gate-unguard.log`: shipped worker `RESULT … GREEN - 14/14 arm(s)`; `_main/_lane6-worker-copy.py` (a COPY with only `elif emitted <= 0:` neutralised) `RESULT (the unguarded COPY (control)): RED - 13/14 arm(s)`; `CONTROL PASS - arm (b) fails on the copy exactly as it should`. The copy is deleted by the instrument. |
| `control-history-producer-stamp-nvidia` | `node _main\history-producer-gate.js --control-stamp-nvidia` | rc=0 | `control-history-producer-stamp-nvidia.log`: `_main/_lane6-engine-mutant.js` (a COPY of `caption-formulation.js` whose `committedProducer()` returns `'nvidia'`) → `verdict real = RED`, `verdict want = RED`, `CONTROL PASS — the gate catches a producer tag that is forwarded but is not the canonical one`. Its final line is literally `RESULT: RED — PRODUCER-VERDICT: inconsistent` **and the step is still a pass**: this is the instrument's documented control contract (rc=0 only when the mutant went RED), which is exactly why the summary prints a separate `controls :` line. |
| `control-redux-flag-neg-arm` | `python _main\redux-flag-gate.py --neg-arm` | rc=0 | `control-redux-flag-neg-arm.log`: `mutants built: 12/12`, `NEG-VERDICT: GREEN — all 12 mutants moved exactly their own claim`, `GATE-VERDICT: GREEN — shipped pair holds every claim AND every claim is load-bearing`. The `--neg-arm` form already includes the shipped GREEN evaluation, so the plain form is not a second step. |
| `control-panel-exit3-neg-arm` | `python _main\panel-exit3-oracle.py --unit --neg-arm` | rc=0 | `control-panel-exit3-neg-arm.log`: JSON `"verdict": "PASS"` with the `neg_arm` / `neg_arm_e` mutant records present (benign-verdict mutant and clear-lifted mutant, each required to go RED). `--unit` needs no shell, no model, no audio; it runs in 0.4 s. |
| `control-wasapi-com-init` | `python _main\wasapi-com-init-oracle.py` (no flag) | rc=0 | `control-wasapi-com-init.log`: `LIVE : PASS`, `NEGARM : PASS (pre-fix copy RED on 3 arm(s))`, `VERDICT PASS`. Both colours in one command by design, and it opens no audio device (stubbed `_ole32`; only `CoInitializeEx`/`CoUninitialize` in the real arms). Its own `--neg-arm` is the pre-fix copy alone — a debug subset — which is why the plain form is what is wired. |
| `control-panel2-repeat-revert` | `node _main\_panel2-repeat-probe.js --revert` | rc=0 | `control-panel2-repeat-revert.log`: `_main/_panel2-repeat-panel-mutant.js` (a COPY of `app/panel/panel.js` with the identity lookup replaced by `const existing = null`) → `CONTROL: arms failed = 4 of 4 — want > 0`, `CONTROL PASS — the identity rule is what removes the repetition`, `control copy removed: true`, `RESULT: GREEN — control behaved as required`. **Two required texts, not one**, because this probe's failure mode was an unreachable verdict (§6.1): rc=0 alone would also have been produced by a run whose arms never executed. Its GREEN half is the plain step `panel2-repeat-probe` (`RESULT: GREEN — 4/4 arm(s)`) in the same battery run. |
| `red-as-expected-historico-gate-off` | `node _main\historico-vs-redux-probe.js --gate-off` | **rc=1** (pass) | `control-historico-gate-off.log`: `[FAIL] no provisional draft reaches the transcript (any flush cadence)`, `[FAIL] every line on disk is a worker-closed line (route=final)`, `RESULT: RED — 2 violation(s)`. This instrument has NO control wrapper, so it is wired as `:expectred` (rc must be exactly 1 + the violation text). The **GREEN half is the plain step in the same battery run**: `historico-vs-redux-probe=0` in the clean summary — both colours, one command, `_main/_audit-verify/oracle-historico-vs-redux.log`. |

Cost of all seven: **~3 s total** (measured individually: 0.1–0.4 s each, plus `redux-flag-gate` 0.2 s
and `_panel2-repeat-probe.js` 1.0 s). None starts a window, a shell, an audio device or the app.

`:control` gained an **optional second required text** for this step, so the recorder now demands two
independent facts from one run when a probe's verdict can be unreachable. The modified recorder was
rehearsed on a scratch copy derived from the real file before the full run (copy deleted; the run is
quoted here because it is the evidence that the new argument fails closed):

```
[step] rehearsed-panel2-two-texts rc=0        [CONTROL] went RED on the broken copy as required
[step] rehearsed-second-text-absent rc=0      ** CONTROL FAILED: rc=0 but the log never printed no such sentence in this log **
[step] rehearsed-first-text-absent rc=0       ** CONTROL FAILED: rc=0 but the log never printed the control verdict NOT IN THE LOG AT ALL … **
[step] rehearsed-control-missing rc=MISSING   ** CONTROL FAILED: THE INSTRUMENT IS NOT THERE … **
BATTERY-VERDICT: RED - 3 step(s) failed
```

## 4a. The FOURTH kind — `skipped` — and the skip guard

Why it exists: `hotkey-delivery` used to sit in the same `gate=` column as a verified gate while its
one arm had not run. That is the same defect as the battery exiting 0 with three reds — **a skip
printed as a pass** — one level down, inside a step instead of a run.

**The kind.** `:skipped <name> <rc> <log> <verified-text> <skip-text> [<skip-text2>]` accepts exactly
three outcomes and no fourth:

| what the instrument did | rc | recorded as |
|---|---|---|
| printed its **skip** verdict (both skip texts present) | 0 | `skipped=` — listed on the `skipped :` line, **never** in `gate=`, and the whole-run verdict sentence names it |
| printed its **verified** verdict, no skip verdict | 0 | `gate=` — it really verified this run |
| rc≠0 · MISSING · half a skip verdict · **neither verdict** | any | **FAILURE** |

The last row is the direction that matters: an instrument that cannot say whether it verified or
skipped is not rounded up to a pass, and a silent no-op cannot pose as a skip. For this probe the
skip claim needs **two** texts — `VERDICT: SKIPPED` **AND** `CANNOT claim` — so a stray mention of the
word in a verified run cannot be read as a skip.

**The guard, closing the other direction.** `:record` steps say nothing about skips, so a single sweep
after the last step fails the whole run if ANY log carries `VERDICT: SKIPPED` while its step is not
declared skip-capable — one check covering every step, including steps added later. The declared logs
are named by `:skipped` itself (measured on this host: of the 32 step logs, only `hotkey-delivery.log`
carries that marker; `control-wasapi-com-init.log` contains the word `SKIPPED` in prose for an internal
sub-arm — `real-mismatch-owes-nothing SKIPPED -- module has no _com_init() (pre-fix shape)` — and is
deliberately NOT flagged, because an instrument that skips a sub-arm and still prints its own overall
verdict is the instrument's business, which is exactly what its `NEGARM : PASS` records).

**Rehearsed before the full run**, on a scratch copy derived from the real file, with synthetic logs
whose verdicts are known by construction (copy and its output dir deleted; console kept verbatim at
`_main/_audit-verify/_run-20261008-rehearsal3-skipped.log`):

```
[step] r3-guard-without-exemption rc=1  ** FAILED **            <- a skip verdict in an undeclared log
[step] r3-guard-with-exemption rc=0                             <- the same sweep, log declared
[step] r3-skip-verdict-counts-as-skipped rc=0  [SKIPPED] NOT VERIFIED: … its own words being VERDICT: SKIPPED
[step] r3-verified-verdict-counts-as-gate rc=0  [SKIP-CAPABLE, verified this run] VERDICT: GREEN … this IS a gate
[step] r3-neither-verdict-is-a-failure rc=0  ** STEP FAILED: rc=0 but the log carries NEITHER … **
[step] r3-skip-verdict-but-rc1-is-a-failure rc=1  ** STEP FAILED: rc=1 … a non-zero rc is a FAILURE, not a skip **
[step] r3-half-a-skip-verdict-is-no-skip rc=0  ** STEP FAILED: rc=0 but the log carries NEITHER … **
[step] r3-missing-instrument-is-no-skip rc=MISSING  ** STEP FAILED: THE INSTRUMENT IS NOT THERE … **
steps    : 8   gate=3  control=0  skipped=1  expect-red=0  missing=1
skipped  :  r3-skip-verdict-counts-as-skipped
BATTERY-VERDICT: RED - 5 step(s) failed
```

The counting is the claim: `skipped=1` and that step is absent from `gate=3`, while the step that
printed the verified verdict IS in `gate=3`. The rehearsal also caught a real parse bug before it
could reach the shipped file — a literal `)` inside an unquoted `echo` closed the block early and
truncated the `[SKIPPED]` line (the `%~5` expansion is parse-time, unlike `!WHY!`, which is why the
failure text survives its own parentheses). Fixed by taking the parentheses out of the echoed text.

**The guard is not vacuous, and that was measured on the real log directory.** The run's own guard log
reads `no skip verdict outside the declared skip step(s)`; the SAME sweep re-run by hand against
`_main/_audit-verify` **with the exemption removed** prints `flagged: hotkey-delivery.log` and exits 1,
while `hotkey-delivery.log` really does carry `VERDICT: SKIPPED — every arm that could run held, but
this run CANNOT claim "Alt+C reaches its handler"` (with the em dash turned into `�` by the console
codepage — the guard matches the ASCII prefix, so the mojibake cannot hide it). So the guard's rc=0 in
the clean run means "exactly the declared step skipped", not "the glob was empty".

## 5. The sweep — every control that exists and nobody ran

Searched `_main` (`.py`, `.js`, `.cmd`) for `--control-`, `--neg-arm`, `--gate-off`, `--mutant`,
`--revert`, `--emit-mutant`, `--emit-panel-mutant`, `--invert-threshold`, `--no-smi-on-path`,
`--allow-onscreen`. Every hit, with its disposition:

| hit | disposition |
|---|---|
| `verdict-gate.py --control-unguard-captions-zero` | **wired** (§4) |
| `history-producer-gate.js --control-stamp-nvidia` | **wired** (§4) |
| `redux-flag-gate.py --neg-arm` | **wired** |
| `panel-exit3-oracle.py --unit --neg-arm` | **wired** |
| `wasapi-com-init-oracle.py` (+ its `--neg-arm`) | **wired** (stronger plain form) |
| `historico-vs-redux-probe.js --gate-off` | **wired** as `:expectred` |
| `_panel2-repeat-probe.js --revert` | **wired** (§4) — after a repair lane fixed its verdict path; see §6.1 for what was broken and how it was measured before and after. |
| `run-cmd-exit-oracle.py --neg-arm` (and its plain arm) | **NOT wired**: it runs the wrapper with `--with-worker` (`run-cmd-exit-oracle.py:420,436`), i.e. it starts the app AND its worker, which opens a WASAPI tap → violates this lane's hard rule (never open an audio device) and the battery's own contract that nothing here starts the app. Also not cheap: 4 arms × `--exit-after 8` plus a window census. |
| `delivery-rate-oracle.py --mutant pump|drop`, `--invert-threshold` | **NOT wired**: "a LIVE run whose worker is a COPY patched back" — live capture + model load. Opens a device; not cheap. |
| `panel-paint-probe.py --revert-gate` | **NOT wired**: it paints the REAL WebView2 panel and compares `px_sha256`; needs a shell and a mapped window on the owner's box. The battery hosts nothing that maps the panel. |
| `panel-startup-flash-census.py --allow-onscreen` | **NOT a control**: it is a permission override for the flash census (which launches the shell ~20×). Nothing for a battery that must not map a window. |
| `route-stamp-gate.js --emit-mutant <path>`, `--emit-panel-mutant <path>` | **NOT wired**: the flag only WRITES a mutant copy (and refuses to overwrite the live file); the RED arm is a SECOND command (`--engine <path>` / `--panel <path>`, rc 1 expected). Not one self-contained step — and neither gate is a battery step at all, so wiring the pair would add a gate and a control I was not asked to adopt. |
| `silent-fallback-probe.js --emit-mutant <path>` | **NOT wired**: same emit-then-rerun shape as `route-stamp-gate.js`. |
| `flat-endpoint-control-changedmode.py` | **NOT wired**: runs the worker with `--max-seconds 45 --tap-window 5` → opens an audio device. Forbidden here. |
| `_qwen-hw-probe.py --no-smi-on-path` | **NOT wired**: a robustness self-test of an unrelated GPU/Qwen probe (simulates a machine with no `nvidia-smi`). Not an app-verification control, and its interesting arms need a model. |
| `alt-c-e2e-probe.py --inject` | **NOT wired**: an injected-keypress E2E arm, not a gate control; it drives the REAL Alt+C, which the owner's live app holds. |
| `_cura-oracle-suite.py` (`--emit-mutant` at :70), `panel-live-vs-history-probe.js` (:25), `dr-ring-probe.py` (:3) | **Not flags at all** — comments pointing at another file's control. No `--control-*` mode of their own. |
| mutant SHELLS consumed through `PANEL_ORACLE_SHELL` / `SOTTO_*` env vars (`_prefix-under-test.py`, `_panel-clear-lifted-mutant.py`, `_shell-visible-neg-arm.py`, `_restart-30s-prefix-mutant.py`, `sotto-webview-prefix-20261006.py`) | **Not controls with flags**: they are the *inputs* of the oracles above. Their consumer is wired only where it needs no shell (`panel-exit3-oracle.py --unit --neg-arm`); the shell-consuming ones are excluded by the same window/device rule. |

No control was weakened, shortened or given a cheaper substitute to make it fit. Instruments whose
default run already carries both colours inside it (`wasapi-com-init-oracle.py`,
`_lane1-worker-default-arms.py`, `_review-*`, the `panel-exit3` unit arms) are covered by their plain
step; the sweep is flag-based, and their "other colour" is not behind a flag.

## 6. Findings I am reporting instead of fixing (not my files)

1. **`_main/_panel2-repeat-probe.js` — CORRECTED (this entry first said "dead in both colours", which
   was the wrong conclusion from a correct observation, and it is exactly how a working instrument
   stays unwired).** What I measured at 05:39 against the then-current revision: plain `rc=1` and
   `--revert` `rc=1`, both ending in `TypeError: Cannot read properties of null (reading 'textContent')`
   at `:263` with no `RESULT:` line of any kind, and `_main/_panel2-repeat-panel-mutant.js` (80 748 B)
   left on disk because the `fs.rmSync(MUTANT)` sat after the crash point. The **ARMS were running the
   whole time** — ARMs A/B/C had already printed `[FAIL]` with their measured rows on the `--revert`
   leg — and what was broken was the VERDICT PATH: ARM D read the DOM *after* `p.window.close()`
   (`:229`), a closed jsdom Document returns `null`, so the throw landed before any verdict could be
   printed and the same throw took the mutant cleanup with it. A repair lane has since moved the DOM
   text capture before the close, made `closeWindow()` clear timers and close in a `try`, run the arms
   in a closure whose throw is a recorded FAIL, and moved the mutant removal into a `finally` that
   prints `control copy removed: true|false` (a failed removal counts as a failed arm).
   **Re-measured by me on the current revision** (`_panel2-repeat-probe.js`, 17 959 B,
   sha256 `AC6660D445D7C08B1AD78987EADAA859B0FDC64FE4CBAC5EBA7E24C17F4BA57D`): plain → `RESULT: GREEN
   — 4/4 arm(s)`, rc=0; `--revert` → `CONTROL: arms failed = 4 of 4 — want > 0`, `CONTROL PASS — the
   identity rule is what removes the repetition`, `control copy removed: true`, `RESULT: GREEN —
   control behaved as required`, rc=0, **0** mutant copies left on disk (the other lane's transcripts:
   `_main/_panel2-repeat-fixed.log`, `_main/_panel2-repeat-fixed-revert.log`; my own probes:
   `_main/_panel2-check-plain.log`, `_main/_panel2-check-revert.log`). The lesson worth keeping is not
   "the probe was broken" but "a crash before the verdict is indistinguishable, from the outside, from
   an instrument with nothing to say" — the step that now guards it demands **two** independent facts
   (`CONTROL PASS` AND `control copy removed: true`), because one verdict string was exactly what this
   instrument could not produce.
2. **`redux-flag-gate.py`'s docstring says SEVEN mutants; the run builds TWELVE** (`mutants built:
   12/12`: flag-exists, flag-guarded, env-optin, memory-gate, switch-wired, stamp, hard-rule,
   fail-safe, payload-guarded, verdict-counts-batch, shell-loop, shell-measured). The header's
   "SEVEN mutated COPIES — one per claim" and "`--neg-arm` … + 7 mutants" are stale; the gate itself
   is fine.
3. **`verdict-gate.py --control-unguard-captions-zero` returns `0` even if the SHIPPED worker came
   out RED** — its contract is `return 0 if passed else 1` where `passed` is only "the copy went
   RED". The battery is honest about this because the plain `verdict-gate` step is a step of its own
   in the same run (rc=0 today), but a lone control run cannot tell you the shipped gate is green.
   Its own summary line does print both states; the exit code does not. Reporting, not changing.
4. **Byproducts the two wired controls leave in `_main/`**: `_main/_redux-gate-mutants/` +
   `_main/_redux-gate.log` (declared paths of `redux-flag-gate.py`) and
   `_main/_panel-verdict-benign-mutant.py` + `_main/_panel-clear-lifted-mutant.py` (declared paths of
   `panel-exit3-oracle.py`). Every battery run now regenerates them; I left them in place because they
   are the instruments' own declared artefacts, not my scratch.
5. Pre-existing and unchanged: `history-producer-gate.js --control-stamp-nvidia`'s final line reads
   `RESULT: RED — PRODUCER-VERDICT: inconsistent` while it exits 0 — correct by its contract, and a
   trap for anyone reading only the log's last line. The battery's `[CONTROL]` tag and the `controls :`
   summary line are the discriminator.

## 7. What I could NOT verify

* **The two rotted controls' original rot is not reproduced** — `verdict-gate.py
  --control-unguard-captions-zero` and `history-producer-gate.js --control-stamp-nvidia` are run here
  in their REPAIRED state (another lane fixed them today). What this lane proves is that they now
  run, go RED on their copies and are counted; that they had been exiting 2 unnoticed is the other
  lane's measurement, and their receipts are the evidence for the rot itself.
* **The battery has never been run with a genuinely red REAL step** — only with the injected
  `cmd /c exit 3` and with the rehearsal's synthetic failures. No real instrument is red today, so
  the "a real red makes it exit non-zero" case is proven on the mechanism, not on a real failure.
* **One step's green is a SKIP, and the summary now says so** (`hotkey-delivery` in `skipped=`, §4a):
  the Alt+C delivery arm does not run while the owner's app holds the key, so the clean run's green
  still does **not** include "Alt+C reaches its handler". That claim needs a run with the app closed —
  and at that moment the same step prints `VERDICT: GREEN` and moves from `skipped=` to `gate=` in the
  same summary line, which is the visible transition §1 and §4a describe.
* **The real instrument's verified path is unexercised today.** `:skipped`'s green branch was proven
  with a synthetic log in the rehearsal; the REAL `_audit-hotkey-delivery.py` cannot print
  `VERDICT: GREEN` while the owner's app is up, so the skip/green discrimination on the real probe has
  only ever run in the skip direction. The green marker (`VERDICT: GREEN`) and the skip markers
  (`VERDICT: SKIPPED` + `CANNOT claim`) were read from the probe's own verdict lines (458/465/472) and
  measured mutually exclusive in the one log that exists today — but that is reading plus one-sided
  evidence, not a two-colour run.
* **The skip guard knows one vocabulary.** It fires on `VERDICT: SKIPPED` only; an instrument that
  words its skip differently would pass it. It also globs `%OUT%\*.log`, so a stale log left by a step
  that is now MISSING could trip it (that run fails on the missing instrument anyway, so the guard
  cannot turn a red run green — but it can add a second, confusing red). `_run-*.log` consoles are
  out of scope by construction.
* **`run-cmd-exit-oracle.py`, `panel-paint-probe.py`, `delivery-rate-oracle.py --mutant` and
  `flat-endpoint-control-changedmode.py` were classified from their own docstrings/source and NOT
  run** (they would start the app, open an audio device or map a window). Their "not cheap / not
  self-contained" reasons are read, not measured — with the single exception of run-cmd's
  `--with-worker` launch flags, which are quoted by file:line.
* **`latest` line numbers**: this lane moved nothing else, but `worker/sotto_worker.py` and
  `app/webview/sotto_webview.py` are edited concurrently by other lanes, so every line number quoted
  here (`run-cmd-exit-oracle.py:420,436`, `_panel2-repeat-probe.js:229,263`, `verdict-gate.py:589`)
  is a hint for the revision of 2026-10-08 and must be re-grepped before being acted on.
* The battery's own heavy step (`_audit-fresh-processor-probe.py`, int8 model load) ran six times
  today — three clean passes (LF run, CRLF run, the panel2 revision), two negative proofs and the LF
  reproduction — and **no window was censused by this lane**. The claim "the battery maps no window"
  rests here on design (nothing in it starts the shell; the only shell invocation is the pre-existing
  `sotto_webview.py --autostart-status` registry read) and on this lane never passing `--show`, not on
  a measurement at its own cadence — which is the rule this repo holds window claims to. No audio
  device was opened by anything this lane ran: the battery's own contract forbids it, and the two
  candidate controls that would have opened one were the two I refused to wire (§5).

## 8. Re-running this

```
cmd /c "_main\_audit-verify-all.cmd"                 REM exit 0 only if every step held
type _main\_audit-verify\_battery-summary.txt        REM the same summary, one file
```

Regenerate the negative proof by copying `_main/_audit-verify-all.cmd` into `_main/` under another
name, inserting the three lines from §3, **converting the copy to CRLF**, and running it: it must
exit 1 and name `INJECTED-FAILING-STEP`. The copy used here was deleted after the run; its console is
kept at `_main/_audit-verify/_run-20261008-negproof.log`.
