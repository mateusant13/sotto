# Receipt — housekeeping, 2026-10-08 (two bounded jobs)

Lane/agent: delegated session, parent `session-ab8603de-dc05-40ba-966c-f756dd2a5a4c`.
Scope honoured: `AGENTS.md` (one bullet), `_main/_panel2-repeat-probe.js`, this receipt. Nothing under
`worker/**` or `app/**` was touched. No process was killed, nothing was started, no audio device was
opened, `--show` was never passed, no shell run happened at all. The owner's live app
(`pythonw.exe` shell + `python.exe` worker under `H:\sotto`) was never named in a filter and never
touched — the two commands this lane ran are `node` and `pwsh` only.

---

## JOB 1 — the durable battery facts are in `AGENTS.md`

### The bullet, verbatim (the ONLY edit to the file)

```markdown
- **`_main\_audit-verify-all.cmd` MUST STAY CRLF, AND ITS EXIT CODE IS ITS VERDICT — measured 2026-10-08, do not re-litigate (this file said nothing about the battery until now, which is how a green word and a red run coexisted).** The subroutines are reached by `call :label` / `exit /b`, and **cmd.exe seeks a batch file by BYTE OFFSET**: with LF-only endings those stored offsets drift and the step list runs **TWICE** — measured (`_main\_audit-verify\_run-20261008-LF-only-double-run.log`): pass 1 reported `steps : 16 gate=10` GREEN, then cmd resumed and re-ran the tail, printing a SECOND summary `steps : 40 gate=28 control=10 expect-red=2` — 40 beacons for **29 distinct steps**, every control twice, **two int8 model loads**. The file is CRLF today (`len=18595`, 337 CRLF / 0 bare LF, sha256 `9DA38ECFCD33C53889458F17087FAF35012AE3BD4B3CCC914384E6B6B3D45BB`); the same bytes converted to LF ran once. **Any tool that rewrites it with `\n` silently re-breaks it — convert back (`-replace "\n", "\r\n"`) or the aggregation lies.** The battery AGGREGATES and its **exit code IS the verdict**: three step kinds — `:record` (the gate), `:control` (passes ONLY when the instrument's control actually went RED on its broken copy AND printed its control verdict), `:expectred` (rc must be exactly 1 with the violation text) — a MISSING instrument is a FAILURE, and any failure exits 1. Measured: clean run `steps : 29 gate=23 control=5 expect-red=1 missing=0 / BATTERY-VERDICT: GREEN / exit-code: 0` (`_main\_audit-verify\_battery-summary.txt`); negative proof `INJECTED-FAILING-STEP rc=3 … BATTERY-VERDICT: RED - 1 step(s) failed … NEGPROOF-EXITCODE=1` (`_run-20261008-negproof.log`). **Before this, a run with THREE red steps (`hotkey-delivery`, `verdict-gate`, `history-producer-gate`) exited 0** — a failure answering as success. So read the `BATTERY-VERDICT` / exit-code pair, never a step's own `rc`, never a lone last line, and never a `steps :` count without checking there is only ONE of them.
```

Placed as the last bullet of *Measured facts that must not be re-litigated*, immediately before
`## Keeping THIS file true`. `AGENTS.md` grew 53517 B and is still **LF-only (0 CRLF / 588 LF)** —
the file's own convention, and unchanged by this edit (`Select-String -Pattern 'MUST STAY CRLF'`
→ 1 hit, so there is exactly one such bullet).

### Every number above, and where it was read (not taken from the dispatch)

| claim | instrument | reading |
|---|---|---|
| CRLF today | byte scan + `Get-FileHash` | `len=18595`, 337 CRLF / **0 bare LF**, sha256 `9DA38ECFCD33C53889458F17087FAF35012AE3BD4B3CCC914384E6B6B3D45BB` |
| LF run doubles the step list | `_main\_audit-verify\_run-20261008-LF-only-double-run.log` | TWO summaries in one run: `steps : 16 gate=10 control=5 expect-red=1` then `steps : 40 gate=28 control=10 expect-red=2` |
| 40 beacons for 29 distinct steps | the `.cmd`'s own step inventory (24 `:record` + 5 `:control` + 1 `:expectred`) | 30 `call` sites, 29 distinct names; **this lane counts 29, not the 28 the dispatch said** — pass 1 of the LF run executed 16 of them, pass 2 re-ran them plus the tail |
| clean run | `_main\_audit-verify\_battery-summary.txt` | `steps=29 gate=23 control=5 expect-red=1 missing=0 failed=0` / `exit-code: 0` / `BATTERY-VERDICT: GREEN` |
| negative proof | `_main\_audit-verify\_run-20261008-negproof.log` | `[step] INJECTED-FAILING-STEP rc=3 ** FAILED **` → `BATTERY-VERDICT: RED - 1 step(s) failed` → `NEGPROOF-EXITCODE=1` |
| the old "red steps exited 0" defect | the battery's own header, `_main\_audit-verify-all.cmd:17-21` | `exit /b 0` unconditionally, with three red steps (`hotkey-delivery` rc=1, `verdict-gate` rc=2, `history-producer-gate` rc=1) — quoted from the file, not re-driven |

**The battery file itself was NOT modified**: its sha256 after this lane's work is still
`9DA38ECFCD33C53889458F17087FAF35012AE3BD4B3CCC914384E6B6B3D45BB`.

### The line in that bullet's vicinity that needed correcting — there is none

The dispatch said "correct any line in that bullet's vicinity that says the battery's rcs can be
trusted without aggregation". Measured before editing: `grep` for `battery|_audit-verify|BATTERY-VERDICT|aggregat`
over `AGENTS.md` returned **ZERO matches** — the file had never mentioned the battery at all, so no
stale line existed to correct. The correction is therefore carried INSIDE the new bullet, by naming
the old behaviour explicitly (*"Before this, a run with THREE red steps … exited 0 — a failure
answering as success"*), which is the only edit the file received.

### One deliberate deviation from the brief

The brief asked for "`\n`" as the re-break mechanism. `\n` alone is correct, but the safer statement
is about **bare LF** (equivalently "a tool that writes `\n`"), which is what the bullet says; the
file's own remedy comment is quoted too (`-replace "\n", "\r\n"`). Nothing else was reworded.

---

## JOB 2 — `_main/_panel2-repeat-probe.js`: FIXED, not retired

### First, a correction of the report as given to me

The dispatch read: *"an instrument that cannot pass in either colour is worse than none."* Measured
today, that is **not** what was true, and the difference decides the verdict:

* Before the fix, **ARMs A, B and C PASSED in the plain colour** (4 committed rows, 4 distinct
  starts, no repeated prefix) and the **four arms went RED exactly as designed in the `--revert`
  colour** (6 rows: `7.84` and `16.24` drawn twice). The `--revert` control is *supposed* to exit 1.
* What died was the **verdict line for both colours**, at `p.document.getElementById('caption-list')`
  — a jsdom Document is no longer usable after `window.close()` at the old `:229`, so the read
  returned `null` (`TypeError: Cannot read properties of null (reading 'textContent')`), ARM D was
  never evaluated, no `[PASS]/[FAIL]` line for D, no `RESULT:`, and the mutant copy
  (`_panel2-repeat-panel-mutant.js`, 80748 B) was left on disk because `fs.rmSync(MUTANT)` sat after
  the crash point.

So the arms were right and the harness around them was broken. **Decision: FIX.** A retirement would
have thrown away a working negative control and left the panel's line-identity rule unguarded, which
is exactly the "worse than none" outcome.

### The fix (three parts, all in that one file)

1. `p.document.getElementById('caption-list').textContent` is **CAPTURED while the DOM is live**
   (`boxText`), before any release; ARM D reads that copy.
2. `closeWindow(window)` replaces the bare `p.window.close()`: it clears the jsdom timers the probe
   was using `close()` for (that is what actually hangs node), and any `close()` throw is reported
   rather than propagated.
3. The arms run inside `runArms()`; a throw is converted to a recorded FAIL plus a `report a broken
   instrument` line, and the mutant removal moved into a **`finally` that runs on every path**,
   printing `control copy removed: true|false`. A removal that FAILS is itself pushed as a failed arm,
   so no run can report success with the broken copy on disk.

The controls were not weakened: every expectation array (`want`, and the `--revert` `control`) is
byte-for-byte what it was, the printed `[PASS]/[FAIL]` order is unchanged, and the exit contract
(0 green / 1 arm failed / 2 setup) is unchanged.

### Both colours, measured after the fix

```
$ node _main/_panel2-repeat-probe.js                 # plain
[PASS] ARM A … real = []   [PASS] ARM B … real = []   [PASS] ARM C … real = 4
[PASS] ARM D … real = [true,"Problems and use this skill and that skill and on the.",false]
RESULT: GREEN — 4/4 arm(s)                                      rc=0

$ node _main/_panel2-repeat-probe.js --revert         # the negative control
[FAIL] ARM A real = ["7.84","16.24"]      (duplicated rows printed)
[FAIL] ARM B 2 repeated prefix pairs printed
[FAIL] ARM C real = 6 want = 4
[FAIL] ARM D real = [false,…] want = [true,…]
control copy removed: true
CONTROL: arms failed = 4 of 4 — want > 0
CONTROL PASS — the identity rule is what removes the repetition: with it disabled every commit appends
RESULT: GREEN — control behaved as required                       rc=0
```

`CONTROL PASS` now prints — the string the battery's `:control` kind requires. Console transcripts
kept: `_main\_panel2-repeat-fixed.log` (plain) and `_main\_panel2-repeat-fixed-revert.log`
(`--revert`). Probe revision after the edit: **17959 B, sha256 `AC6660D445D7C08B…`**. `node --check`
clean. Its own header now records the dead period and the four-part cure, so the next reader does not
re-derive it.

### Leftovers check

`Get-ChildItem _main\ -Filter "_panel2-repeat-panel-mutant.js"` → **0 matches** after both runs (the
probe prints `control copy removed: true` on each). Before the fix the `--revert` run left an 80748 B
copy behind; that is now impossible without the run going RED.

**Residual, stated honestly:** the mutant is removed in the `finally`, but a run that fails *before*
the control copy is written (missing jsdom → rc 2, missing fixture → rc 2) is not covered by that
`finally`, because there is nothing to remove yet. That is a deliberate reading of ownership: a
mutant whose OWNER never created it is earlier owners' leftover. Demonstrated empirically elsewhere
in this repo — a pre-existing 80748 B copy from the pre-fix probe survived this lane's first plain
run (it exits before writing anything), and the `--revert` run then overwrote it and removed it,
which is why `false` is not reported when one was already present.

### Who else references it (reported, not touched)

14 hits for the string `panel2-repeat` repo-wide:

* `app/panel/panel.js:418` — a comment naming the probe as a reader of `data-start`/`data-revision`
  (the probe's assertions rest on those attributes). **Not mine to edit; no edit needed** (the
  attributes it reads are unchanged).
* `_main\receipt-battery-honest.md:163,183-190,228` — the receipt that declared it dead, and that
  correctly refused to wire it because the battery lane did not own the file. **Now stale**: the
  probe passes in both colours and its control is `CONTROL PASS`-clean, so `--revert` is a
  *candidate* battery step. That receipt is not a file this lane may edit — the owner of it should
  update §5/§6 (its own line 163 disposition and §6 finding 1) and may then wire
  `node _main\_panel2-repeat-probe.js --revert` as a `:control` step: it needs jsdom, no window, no
  audio, no shell, ~1–2 s, and prints `CONTROL PASS`.
* `_main\receipt-rename-panel.md:92` — a historical path-rename list. Still true; no action.
* `_main\_panel2-repeat-probe.js` itself (name, usage lines, its own "run the control too" hint).
* **Nothing else**: no reference in `_audit-verify-all.cmd`, no `--emit-mutant` caller, no shell,
  worker or app file imports it. The only file that names the mutant path is the probe itself.

---

## What I could NOT verify (and what I refused to run)

1. **I did not run the battery end-to-end.** Its numbers reach this receipt from the battery's own
   artifacts (summary file, negative-proof console, LF-only console) and from its header, and the
   dispatch's numbers agree with all of them — but no run of `_audit-verify-all.cmd` was made by this
   lane. The reason is a hard rule, not budget: the battery contains
   `python _main\_audit-hotkey-probe.py` and `python _main\_audit-hotkey-delivery.py`, which register
   the **global** Alt+C (`_audit-hotkey-delivery.py` registers, fires a real `WM_HOTKEY`, and proves a
   fallback chain under an owned key). The owner's live app holds Alt+C, so a battery run while it is
   up could steal or collide with the owner's control key plus a ~2 GB int8 model load — the same
   reasoning that made the battery lane refuse to wire `run-cmd-exit-oracle.py`'s `--with-worker` arms.
   So: the "29 / gate=23 / control=5 / GREEN / exit 0" and "RED / exit 1" claims are **read from
   artifacts dated 2026-10-08 05:43**, not re-driven by me.
2. **Distinct step count is 29, not 28.** The dispatch's "40 beacons for 28 distinct steps" is off by
   one; 40 = 16 (pass 1) re-run plus the tail = the 29 distinct steps plus 11 re-executions. My count
   comes from the `.cmd`'s own `call` inventory (24 `:record` + 5 `:control` + 1 `:expectred`), which
   matches the clean summary's `steps=29 gate=23 control=5 expect-red=1` (one `:record`, the heavy
   `fresh-processor-probe`, is not counted as a gate). **I did not run the double-run to confirm the
   number of distinct BEACONS directly** — only the two summary lines exist as evidence.
3. **`AGENTS.md`'s edit is verified only structurally** (one new bullet, LF endings intact, file
   parses as the same markdown section order). No test asserts its content, and other agents load it
   live — if a concurrent lane rewrote the file after 05:47:59, my bullet is the one that could be
   lost. The current on-disk file was re-read by the harness after the edit and contains the bullet.
4. **The probe's ARM B fixture is weak on its own**: with the identity rule ON, ARM B passes
   *vacuously* (an empty `prefixPairs`), and it is the `--revert` colour that gives it its teeth
   (2 real repeated pairs). That was true before this lane and is unchanged — it is why the `--revert`
   control must be named as the real evidence for the owner's symptom.
5. No claim is made here about windows or audio for anything this lane ran: the probe is jsdom-only
   (no browser, no `window.show`, no device) and the other commands were `Get-Content`/`Get-FileHash`/
   `Select-String`/`node`.
