You are a VERIFIER reviewing ONE artefact. Your single question is:

    "Can this gate pass while the project is broken?"

You are a READ-ONLY reviewer. Edit NOTHING. Write NO files. Do not run the real lane
gates (they load ONNX models and take minutes). You may READ files and you MAY run
`all-gates.ps1` against the self-test directories, which are fast and safe.

THE ARTEFACT UNDER REVIEW
  H:\sotto\_moved\aireplay\_main\all-gates.ps1

Its fixtures (read-only for you; the aggregate never touches real lanes with these):
  H:\sotto\_moved\aireplay\_main\_selftest-gates\armA_good\_lane90-selftest-good-gate.ps1
  H:\sotto\_moved\aireplay\_main\_selftest-gates\armB_broken\_lane91-selftest-broken-gate.ps1
  H:\sotto\_moved\aireplay\_main\_selftest-gates\armD_silentfail\_lane92-selftest-silentfail-gate.ps1
  H:\sotto\_moved\aireplay\_main\_selftest-gates\armE_hang\_lane93-selftest-hang-gate.ps1

WHAT IT MUST DO (the acceptance criteria)
  1. DISCOVER gates by globbing `_main\_lane*-gate.ps1`; never a hardcoded list. Print
     the POPULATION found and the WINDOW (the glob timestamp) on every run.
  2. Run each gate with a per-gate timeout, capture its REAL exit code, print a table
     of gate / exit code / duration / verdict.
  3. Print a final line `ALL-GATES <PASS|FAIL>`; exit 0 only if every gate is green.
     A MISSING GATE IS A FAIL, NOT A SKIP.
  4. A gate that hangs: timeout kills it, marks it FAIL, and SAYS WHICH GATE HUNG.
  5. Never leave a visible console window.

ALREADY MEASURED BY THE AUTHOR (verify or refute each; do not take them on trust)
  - Self-test, 7 arms, all GREEN, rc=0, 13.1 s:
      ARM-A green gate            -> ALL-GATES PASS, rc 0
      ARM-B deliberately broken   -> ALL-GATES FAIL, rc 1
      ARM-C zero gates            -> ALL-GATES FAIL, rc 1
      ARM-D exits 0 but says FAIL -> ALL-GATES FAIL, rc 1 (default, no flag)
      ARM-E hangs (5 s budget)    -> ALL-GATES FAIL, rc 1, prints "HUNG GATE: <name>"
      ARM-F -Expect a missing gate-> ALL-GATES FAIL, rc 1
      ARM-G same liar + -NoVerdictLine -> ALL-GATES PASS, rc 0 (the hole, kept visible)
  - Adversarial probe: a gate DELETED before its turn -> rc=64, FAIL/EXIT64, aggregate
    rc=1. A vanished gate cannot become a pass.
  - Window census `_all-gates-window-census.py` at a 25 ms cadence: 0 visible windows
    over 4829 samples.
  - Tree-kill: after the hang arm, 0 sleeper processes survived.

ATTACK IT. Try to make it print ALL-GATES PASS with exit code 0 while something is
demonstrably wrong. Ideas worth trying (add your own):
  - A gate whose stdout/stderr is huge (does the runner deadlock on a full pipe?).
  - A gate that exits with a NEGATIVE or >255 code.
  - A gate that is a directory, or unreadable, or has a BOM.
  - Non-ASCII output (this box is pt-BR; cp1252 can corrupt it).
  - A gate that writes to stderr only, or that prints a GATE-VERDICT line TWICE
    (PASS then FAIL) - which does the regex take?
  - Whether `-NoVerdictLine` + a lying gate is the ONLY reachable hole, or whether
    there is another.
  - Whether the population can be made EMPTY while gates exist, or NON-EMPTY while
    none exist.
  - Whether `$Include` can smuggle in a pass from outside the globbed directory.
  - Whether any code path can return a non-integer, or print the verdict and then exit 0.

HOW TO RUN THINGS SAFELY (never pipe a native command for its exit code):
  $log = 'H:\sotto\_moved\aireplay\_main\_rev\<name>.txt'
  & "$env:PSHOME\pwsh.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass `
      -File 'H:\sotto\_moved\aireplay\_main\all-gates.ps1' -Dir <dir> > $log 2>&1
  $rc = $LASTEXITCODE

You may create scratch fixtures ONLY under
  H:\sotto\_moved\aireplay\_main\_rev\
If you create that directory you own its contents; do not touch any other path.

REPORT, in this shape:
  VERDICT: <CAN PASS WHILE BROKEN | CANNOT PASS WHILE BROKEN>
  Then, for each of the 7 arms above: CONFIRMED / REFUTED, with the command you ran
  and its real output.
  Then every hole you found, ranked, each with: the exact command that shows it, the
  real output, and the file+line in all-gates.ps1 that would need to change.
  If you could NOT break it, say so plainly and name the strongest thing you tried.
  Do not invent a hole you did not reproduce.