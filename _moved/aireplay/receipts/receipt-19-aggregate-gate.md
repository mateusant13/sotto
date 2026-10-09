# RECEIPT 19 — the aggregate gate: one command that tells the truth about the project

Lane: aggregate-gate. Date: 2026-10-07. Files owned:
`_main/all-gates.ps1`, this receipt.

## 0. THE ONE-LINE ANSWER

```
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\all-gates.ps1
```

It discovers every `_main\_lane*-gate.ps1`, runs each with a per-gate timeout, reads
each one's **real** exit code from the process object, prints a table and a single
final line `ALL-GATES PASS|FAIL`, and exits 0 only if every gate is green.

**As of the final measured run: `ALL-GATES FAIL` — POPULATION 8, 7 green, 1 red**
(`_lane16-wake-gate.ps1`, exit 1, 89.6 s). That is the point of the file: before it
existed, the project reported green by default. A run costs ~10 min because the
model-loading gates are genuinely slow; `-TimeoutSec` tunes the per-gate budget.

## 1. WHAT IT DOES, AGAINST THE FIVE REQUIREMENTS

| # | requirement | where | MEASURED |
|---|---|---|---|
| 1 | discover by glob, never a hardcoded list; print POPULATION and WINDOW | `Get-NearMissGates` :129, `Get-GatePopulation` :153, WINDOW :383 | population 0→8 live during this lane (§4) |
| 2 | per-gate timeout, REAL exit code, table of gate/exit/duration/verdict | `Invoke-Gate` :213, `Write-ResultTable` :345 | 8 rows, real codes, `_all-gates-real.txt` |
| 3 | final line `ALL-GATES PASS\|FAIL`; missing gate = FAIL not skip | :393-395, :469-473 | ARM-C zero gates → FAIL rc=1 |
| 4 | a hang is killed, marked FAIL, and **names the gate** | :425-427 | ARM-E → `HUNG GATE: _lane93-… exceeded 5s` |
| 5 | never a visible console window | `CreateNoWindow=$true` :223 | 0 windows / 4829 samples (§5) |

*Line numbers are for the revision at the foot of §10 (590 lines, sha256 in §10).
Re-verify before citing — this repo has been bitten by a correct citation from a stale
revision (AGENTS.md, receipt-15).*

**Plus one this brief did not ask for:** a gate that exists but cannot be *discovered*
(a directory, or a misspelled name) is a FAIL row, not silence — reviewer Hole 3, §9.

### The discovery really is live

The glob picked up gates as lanes landed, **during this lane**:

| when | POPULATION |
|---|---|
| lane start | **0** gates existed |
| 12:24 | 0 |
| 12:27 | 4 |
| 12:41 | 8 |

A hardcoded list would still have been checking 0 gates at 12:24 and would have gone
stale the moment `_lane2-audio-gate.ps1` landed at 12:40. This is the concrete
argument for the glob.

## 2. BOTH COLOURS — THE PROOF IT CAN GO RED

`-SelfTest` runs **9 arms**, each a REAL child invocation of the same code path the
real run uses. No mocks, no assertions about my own arithmetic.

```
py -3 … ; pwsh -NoProfile -File _main\all-gates.ps1 -SelfTest
→ rc=0, wall=17.1 s, SELFTEST PASS
```

| arm | fixture | rc | final line |
|---|---|---|---|
| A green is PASS | armA_good | 0 | ALL-GATES PASS |
| B broken is FAIL | armB_broken | 1 | ALL-GATES FAIL |
| C **no gates** is FAIL | armC_empty | 1 | ALL-GATES FAIL |
| D exits 0 but declares FAIL | armD_silentfail | 1 | ALL-GATES FAIL |
| D2 no verdict line, default | armI_launder | 0 | ALL-GATES PASS |
| D2b no verdict line, required | armI_launder `-RequireVerdictLine` | 1 | ALL-GATES FAIL |
| E **hang** is FAIL | armE_hang | 1 | ALL-GATES FAIL + `HUNG GATE:` |
| F `-Expect` absent gate | armA_good + bogus name | 1 | ALL-GATES FAIL |
| G documented opt-out hole | armD + `-NoVerdictLine` | 0 | ALL-GATES PASS |

Full transcript: `_main/_selftest-run.txt`.

**ARM-B is the answer to "a gate that has only ever printed PASS is not a gate."**
It is a copy of ARM-A with one expectation inverted, and it is scored FAIL.

## 3. ADVERSARIAL PROBES — WHERE I TRIED TO BREAK IT, AND WHAT I FOUND

| probe | attack | result |
|---|---|---|
| `_adv-race.txt` | a gate **deleted before its turn** | **rc=64 FAIL/EXIT64**, aggregate rc=1 — a vanished gate cannot pass |
| `_rev/dualverdict.txt` | prints `GATE-VERDICT PASS` **then** `FAIL`, exits 0 | **was PASS — a real bug, now fixed**, see below |
| `_rev/dualpass.txt` | control: prints `PASS` twice, exits 0 | PASS (fix did not break honest gates) |
| `_adv-launder.txt` | writes `ALL-GATES PASS` to stdout, stderr **and a log file**, no verdict line | default → FAIL/NO-VERDICT; `-NoVerdictLine` → PASS (the one documented hole) |

### BUG 1 — a later `FAIL` was ignored (found by my own probe)

`Get-Verdict` used `[regex]::Match`, which returns the **first** match. A gate printing
`GATE-VERDICT PASS` and then `GATE-VERDICT FAIL` scored **PASS**: the first line talked
the runner out of reading the second. Fixed to `[regex]::Matches` with any-FAIL-wins;
`_rev/dualverdict2.txt` shows `FAIL/VERDICT <- exit 0 but the gate declared FAIL on 1
of 2 GATE-VERDICT lines`.

### BUG 2 — my "good" and "broken" fixtures were both broken

The first self-test run reported **ARM-A RED** — the gate named "good" exited 1. Its
negative control asserted `expect True` on an already-true inverted value, and all
three fixtures incremented `$fails` on the wrong side. Two rounds of fixing, each
round recorded in the fixture headers. ARM-B had been "passing" only because I had
hardcoded `exit 3`. **A hardcoded exit code is precisely what an aggregate must not
trust**, so ARM-B now exits its real failure count.

### BUG 3 — a probe of mine did not create the condition it claimed

The first mid-run-disappearance probe had the gate delete **itself**, after it was
already running — the race never happened, and it printed a false `ALL-GATES PASS`.
Corrected to delete a *later* gate before its turn. The flawed version's directory was
moved to trash; the corrected one is `_selftest-gates/armH_midrun/` with a README.

### BUG 4 — my first window census was theatre

It shelled out to `wmic` on **every 25 ms sample**, so it could not sample at 25 ms at
all and would have reported PASS while watching almost nothing. Rewritten in-process
via `CreateToolhelp32Snapshot`.

## 4. THE FIRST REAL RUN — and a judgement call it forced

`_main/_all-gates-real.txt`, window `2026-10-07T12:41:20-03:00`, POPULATION=8,
wall 568.5 s, **rc=1**:

```
GATE                              EXIT   DURATION  VERDICT
_lane1-trigger-gate.ps1           0      88.0s     FAIL/NO-VERDICT
_lane16-wake-gate.ps1            -1     200.1s     FAIL/TIMEOUT
_lane2-audio-gate.ps1             1      27.5s     FAIL/EXIT1
_lane23-trigger-defects-gate.ps1  0      13.5s     FAIL/NO-VERDICT
_lane3-ringcap-gate.ps1           0      15.1s     FAIL/NO-VERDICT
_lane4-index-gate.ps1            0       2.2s     FAIL/NO-VERDICT
_lane7-window-gate.ps1            0     172.3s     FAIL/NO-VERDICT
_lane9-asr-gate.ps1               0      47.1s     FAIL/NO-VERDICT
```

I had made "every gate must print `GATE-VERDICT`" the **default**, and it produced
**6 of 8 FAIL rows that were not defects** — no lane had adopted the line. That buried
the one real signal (`_lane2-audio-gate`, `FAIL/EXIT1`) under six adoption failures,
which is precisely how a real failure gets missed. **Default changed** to: exit code
authoritative, but a **self-declared `GATE-VERDICT FAIL` always beats exit 0**.
Catches the liar (ARM-D) at zero adoption cost. `-RequireVerdictLine` remains
available and stricter.

**Two real findings from that run, in other lanes' files, which I do NOT own:**
- `_lane16-wake-gate.ps1` exceeded a **200 s** budget → `FAIL/TIMEOUT`, tree killed.
- `_lane2-audio-gate.ps1` exited **1** — a genuine red.

Both were fixed by their authors while this lane was running; in the FINAL run (§4b)
`_lane2-audio-gate.ps1` is green, and `_lane16-wake-gate.ps1` now finishes in 89.6 s
but still exits 1. Neither file was edited by me — this runner only observed them.

### FINAL real run — the corrected policy, `_main/_all-gates-real.txt`

Window `2026-10-07T13:00:19-03:00`, POPULATION=8, wall **597.5 s**, **rc=1**:

```
GATE                              EXIT   DURATION  VERDICT
_lane1-trigger-gate.ps1           0      70.3s     PASS
_lane16-wake-gate.ps1             1      89.6s     FAIL/EXIT1
_lane2-audio-gate.ps1             0      43.5s     PASS
_lane23-trigger-defects-gate.ps1  0      21.5s     PASS
_lane3-ringcap-gate.ps1           0      26.4s     PASS
_lane4-index-gate.ps1             0       4.2s     PASS
_lane7-window-gate.ps1            0     132.9s     PASS
_lane9-asr-gate.ps1               0     208.2s     PASS

SUMMARY gates=8 passed=7 failed=1
ALL-GATES FAIL
```

**This is the argument for changing the default, measured.** Under the strict default
the same population reported **8 failures** (6 of them fictional). Under the corrected
policy it reports **the truth: 7 green, 1 genuinely red.** A gate runner that cries
wolf on six healthy lanes is a gate nobody reads.

Two rows **changed for the better** between runs, both worth naming:
- `_lane16-wake-gate.ps1`: `FAIL/TIMEOUT (200 s)` → `FAIL/EXIT1 (89.6 s)`. Its author
  fixed it while I ran; it now finishes and fails for a real reason.
- `_lane2-audio-gate.ps1`: `FAIL/EXIT1` → `PASS`. Also fixed upstream.

**The one outstanding red is real and belongs to another lane:**
`_lane16-wake-gate.ps1` exits 1 in 89.6 s. Not mine, not edited by me.

No phantom near-misses appeared against the real `_main` population, confirming the
Hole-3 fix does not fire on a healthy directory.

## 5. HARD RULE 1 — no visible console window

`_main/_all-gates-window-census.py` samples every **25 ms** (the house census samples
once per 60 s, which per this project's own measured finding cannot prove absence):

```
cadence     = 25 ms target, 188.0 ms worst observed gap
samples     = 4829 over 241.7 s  (20.0 Hz effective)
window-seen = 0 samples over 0 distinct pid(s)
VERDICT PASS
```

Children are launched `CreateNoWindow=$true` + `UseShellExecute=$false`, i.e. the
`CREATE_NO_WINDOW` path. A child that spawns a console of its own would still be
caught, because the census tracks the whole process tree.

## 6. ORPHANS — hard rule 1's sibling

After the hang arm: **0 sleeper processes survived** (`Kill($true)`, the whole tree —
killing only the root is what produced the orphan writers in receipt-15 §0). The ARM-E
fixture deliberately spawns a grandchild so the tree-kill is a tested claim.

Two caveats, stated rather than hidden:
- When I cancelled a long real run at the shell, **one orphan of mine survived briefly**
  and exited on its own. My runner's timeout path is proven; **external cancellation
  of the runner is not** and can orphan a child. If you Ctrl-C the aggregate, kill the
  tree yourself.
- My own process census initially matched **itself**, because the search string
  appeared in its own command line. The "2 survivors" in the transcript were my census
  and another lane's probe. Filter on the artifact path, never a bare word.

## 7. THE REMAINING HOLE — now stated in the file's own header

Two, both deliberate and both re-runnable:

1. **A gate that prints no `GATE-VERDICT` line is judged on its exit code alone.** So
   a gate that fails every check, prints nothing, and exits 0 scores PASS. Making the
   line mandatory was tried, MEASURED, and reverted: it turned 6 healthy lanes into
   `FAIL/NO-VERDICT` and buried the one real failure. `-RequireVerdictLine` turns it
   back on. Found by the reviewer as **HOLE 1**.
2. **`-NoVerdictLine`** waives the self-declared-FAIL rule as well. Self-test **ARM-G
   asserts this still happens**, so the day someone closes it the self-test goes RED
   and says why.

**What this gate CANNOT do, and no aggregate can:** tell you that a gate tested
anything. A gate that asserts nothing and exits 0 is indistinguishable from a working
gate. Only its author can close that. The near-miss scan (§9, Hole 3) closes the
*filesystem-shaped* version of that problem — a gate that exists but is undiscoverable
now fails loudly instead of vanishing.

## 8. RE-RUN COMMANDS (all read `$LASTEXITCODE`, never a pipe)

```powershell
# the truth about the project
$log='H:\sotto\_moved\aireplay\_main\_all-gates-real.txt'
& "$env:PSHOME\pwsh.exe" -NoProfile -File 'H:\sotto\_moved\aireplay\_main\all-gates.ps1' > $log 2>&1
$rc=$LASTEXITCODE                      # 0 only if EVERY gate is green

# prove it can still go red (9 arms)
& "$env:PSHOME\pwsh.exe" -NoProfile -File 'H:\sotto\_moved\aireplay\_main\all-gates.ps1' -SelfTest > $log 2>&1
$rc=$LASTEXITCODE                      # 0 = SELFTEST PASS

# demand a lane's gate EXISTS (missing => FAIL, never a skip)
… -Expect _lane2-audio-gate.ps1

# no visible window, at a 25 ms cadence
py -3 'H:\sotto\_moved\aireplay\_main\_all-gates-window-census.py'
```

Sequential by design: a hung lane holding a device would otherwise make two lanes fail
for one fault. A full run costs the SUM of the budgets (measured: 568 s for 8 gates).

## SELF-AUDIT

1. **Confidence.** High that it cannot pass while a gate is red, hung, absent or
   lying about its own failure — nine arms plus four adversarial probes, all measured.
   **Medium** on the claim "no visible window": 4829 samples at 20 Hz over one run.
   A window appearing in a *lane* gate that only opens briefly, only on some runs,
   could still slip past. What moves it: a longer census over several real runs.
2. **Protocols missing.** No independent subagent review (§9 — the seat has no dispatch
   tool). One real run only — no soak, no repeat.
3. **Extra verification beyond the brief.** Mid-run deletion, verdict-laundering,
   dual-verdict, honest-gate control, orphan census, and a 25 ms window census. Each
   found or excluded a specific hole; three of them found real bugs in my own code.
4. **New named verification boxes.** `all-gates.ps1 -SelfTest` (9 arms),
   `CENSUS-ALL-GATES` (25 ms window census), `_selftest-gates/armH_midrun`
   (mid-run deletion), `_selftest-gates/armI_launder` (verdict laundering).
5. **Gate doubts.**
   - `verde-de-verdade:` the RED arms are real child runs of the shipped code path.
   - `falta-no-gate:` nothing checks that a lane's gate still *asserts the thing it
     claims* — a lane can gut its own gate and this aggregate would report PASS.
     A per-gate "arms executed ≥ N" assertion would need the gates to report it.
   - `gate-melhor:` a `-Json` machine-readable result, so CI can diff populations
     between runs and notice a gate disappearing. The log dir already holds every
     gate's raw output for that.
6. **Reviewed by another agent:** **yes** — §9. Its verdict was **CAN PASS WHILE
   BROKEN**, all three of its findings CONFIRMED by me and fixed, and one of its
   recommended fixes rejected on measured evidence. It could not execute anything on
   this host, so its arms are unverified by it and verified by me instead.

## 9. REVIEWER — verbatim, and what I did about it

Dispatched read-only with the single question **"can this gate pass while the project
is broken?"**. Its verdict, quoted:

> **VERDICT: CAN PASS WHILE BROKEN**
>
> One reachable hole remains at the **default** invocation — a gate that exits 0, prints
> no `GATE-VERDICT` line, and has failed every check inside it scores `PASS`, rc=0. The
> author's ARM-G (`-NoVerdictLine` + liar) is **no longer the only hole**; the default
> widened to admit the same defect without any flag.
>
> **Critical caveat on method:** this host's permission gate blocked **all** process
> spawning and script execution … I could not run a single one of the 7 arms … What
> follows is verified by **reading the live file and executing faithful transcriptions
> of its decision functions** — not by running the gate. Treat the 7 arms as UNVERIFIED
> by me, and the holes as logic-level CONFIRMED but end-to-end UNPROVEN.
>
> **HOLE 1** … The file's own header (line 44) claims the opposite … The code
> contradicts its own documented contract.
>
> **HOLE 3** — glob blind spots are silent skips (confirmed on real fixtures) … Nothing
> fails; the gate is simply absent from the population and from the printed table.
>
> Also: **ARM-C's fixture `armC_empty` does not exist on disk**, so ARM-C passes because
> the *directory is absent*, not because it is *empty*.
>
> "The strongest thing I tried: the PASS-then-FAIL double-verdict laundering attack. It
> **worked** on the earlier revision … The author fixed it mid-review … That fix is real
> and I am not reporting it as a hole."

**Its caveat is correct and I am not glossing it: the reviewer could not execute
anything on this host, so its 7 arms are UNVERIFIED *by it*. I verified all of them
myself by running them (§2), which is why they are measured here rather than asserted.**

### I confirmed all three findings, and fixed all three

| finding | my verdict | action |
|---|---|---|
| HOLE 1 header contradicts code | **CONFIRMED** | header rewritten (`:42-53`) to state exactly what the default does, including the consequence it does NOT catch |
| HOLE 2 ARM-G is not the only route | **CONFIRMED** | same header fix; the default hole is now stated in the file's own limits |
| HOLE 3 glob blind spots are silent skips | **CONFIRMED** | `Get-NearMissGates` `:130` — directories and misnamed `_lane*gate*.ps1` now become **FAIL rows** |
| `armC_empty` absent | **CONFIRMED** | directory created, with a README stating it must stay empty |

**Hole 3 fix, measured** (`_main/_rev/nearmiss.txt`), against the reviewer's own fixture:

```
GATES POPULATION = 2
  [ok]       _lane10-real-gate.ps1   39 B  glob
  [MISSING]  _lane12-typo-gates.ps1  39 B  near-miss
_lane12-typo-gates.ps1  n/a  0.0s  FAIL/MISSING  <- does not match the glob _lane*-gate.ps1
ALL-GATES FAIL        (rc=1)
```

Control (`_main/_rev/cleanpop.txt`): a clean directory gains **no** phantom near-misses,
rc=0. The fix does not fire on a healthy population.

### I DISAGREE with the reviewer's proposed fix for Hole 1

It recommends making the line requirement the default (`all-gates.ps1:290`). **I
measured that and it is wrong for this project.** The first real run — the reviewer
could not run it — showed 6 of 8 gates reporting `FAIL/NO-VERDICT` purely because no
lane had adopted the line, burying the single real failure (`_lane2-audio-gate`,
`FAIL/EXIT1`). That is *how a real failure gets missed*, which is worse than the hole
the fix closes. The residual hole is therefore **documented in the file's own header in
the words above**, and `-RequireVerdictLine` is available for whoever wants the strict
reading. This is a disagreement with evidence, not a dismissal.

**What the reviewer got right and I could not have found by reading: the header/code
contradiction.** The logic was defensible; the file was lying about itself in writing.
That is the finding I am keeping.

## WHAT'S NEXT / WHAT I DID NOT DO

- **Adopt or reject `GATE-VERDICT PASS|FAIL`** in lane gates — owner's call. Not
  required today; it only tightens `-RequireVerdictLine`.
- **`_lane16-wake-gate.ps1` still exits 1** (89.6 s, not a timeout any more) — the one
  real red in the final run. That file belongs to another lane; I did not edit it.
- **A `-Json` output and a per-run population diff** — not built; the log dir is a
  partial substitute.
- **I did not commit.** Hard rule 7 permits a commit only on a green gate, and the
  project is currently `ALL-GATES FAIL`. The sha of what I produced is in §10.

## 10. ARTEFACTS

| path | what |
|---|---|
| `_main/all-gates.ps1` | the aggregate gate (590 lines) |
| `_main/_selftest-gates/arm{A,B,C,D,E,I}_*/` | 9-arm fixtures; `armC_empty` is deliberately empty |
| `_main/_selftest-gates/armH_midrun/_README.md` | mid-run deletion probe |
| `_main/_selftest-gates/armI_launder/_README.md` | laundering probe + the remaining hole |
| `_main/_all-gates-window-census.py` | `CENSUS-ALL-GATES`, 25 ms cadence |
| `_main/_selftest-run.txt` | 9-arm transcript |
| `_main/_all-gates-real.txt` | the real run (§4) |
| `_main/_adv-race.txt`, `_adv-launder.txt`, `_rev/*.txt` | probe transcripts |
| `_main/_review-prompt.md`, `_reviewer-verdict.txt` | the review brief and its verbatim verdict |

`_main/_rev/` holds scratch: my adversarial probes plus the reviewer's own
`_rev/gtest/` fixtures, which are load-bearing for §9 and must NOT be cleaned up.

**I did not commit** (hard rule 7: only on a green gate; the project is
`ALL-GATES FAIL`). Fingerprint of what I produced, MEASURED at the end of this lane:

```
_main/all-gates.ps1
  29247 B   590 lines   LF endings, no BOM (house convention)
  sha256 8E1734F3A2E427FF2A3D276DCD3B97AE6DF3470BE2DDC983C94943E193B28F01
  mtime 2026-10-07 12:58:50
```

`git -C H:\sotto\_moved\aireplay status --porcelain` for the two files I own:

```
 M _main/all-gates.ps1
?? receipts/receipt-19-aggregate-gate.md
```

Both are **uncommitted**, deliberately. The earlier `DDC578F0…` sha quoted mid-receipt
is the PRE-reviewer revision and is left there only to show the file moved under the
reviewer — do not use it to identify this artefact.