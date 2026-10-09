You are an INDEPENDENT VERIFIER auditing one lane's deliverable. Audit for CONCRETE DEFECTS
only. EDIT NOTHING — you have no file to write and you must not create one. Report findings as
text.

REPO: H:\sotto\_moved\aireplay  (a git repo; the product tree)
READ FIRST, IN FULL: H:\sotto\_moved\aireplay\_main\LANE-BRIEF.md

THE LANE'S CLAIM (its own words, from receipts/receipt-24-clip-to-asr-chain.md):
"6 of 8 stages ran against the REAL shipped module. 1 ran against a real binary standing in for
a producer that does not exist. 1 is a double, and says so." It claims the chain
clip -> audio -> transcript -> index row -> search works end to end, and that its gate
`_main/_lane17-chain-gate.ps1` prints `LANE17-GATE PASS` with exit 0 on 8/8 arms.

FILES UNDER AUDIT (all owned by the lane; all NEW):
  src/pipeline/__init__.py
  src/pipeline/contracts.py
  src/pipeline/chain.py
  _main/_lane17-chain-gate.ps1
  receipts/receipt-24-clip-to-asr-chain.md

FILES IT MUST NOT HAVE TOUCHED (other lanes own them and were writing concurrently):
  src/capture/**, src/asr/**, src/index/**, src/ui/**

WHAT I WANT YOU TO CHECK, IN PRIORITY ORDER:

1. THE CONTROL ARMS ARE NOT VACUOUS. This is the highest-value question. ARM C1 copies
   src/pipeline into scratch, reverts ONE line in the copy, and asserts the run goes red.
   Verify by READING that the reverted line is really the cure under test, that the assertions
   on the control arm are the SAME assertions as the live arm, and — critically — that the arm
   would fail if the copy silently failed to apply the mutation. The lane claims a guard for
   this; check the guard is real and sufficient. The lane also claims an earlier version of its
   control went red for the WRONG reason. Judge whether the current version can still do that.

2. THE PROVENANCE TABLE IS HONEST. Does any stage claim REAL while actually running a
   double, a stub, or something the lane wrote itself? Specifically: is `extract` correctly
   labelled REAL_SUBSTITUTE rather than REAL, and is `capture` correctly labelled DOUBLE?
   Is `SCAFFOLD: False` a truthful statement about this run?

3. THE CONTRACT FILE MATCHES THE LIVE PRODUCERS. contracts.py claims to verify signatures of
   src/asr/*, src/index/* and two C++ headers at run time. Read the real producer files and
   check the declared signatures are actually what those files expose. NOTE: src/index was
   REWRITTEN by another lane mid-task (13:10:26) — schema.py became schema.sql,
   __init__.py was deleted, and store.py/search.py were replaced. Verify the contracts match
   the CURRENT contents of those files, not an older revision.

4. THE RECEIPT'S NUMBERS ARE SUPPORTED BY THE EVIDENCE. The receipt quotes provenance counts,
   stage measurements, gate results and sha256 values. Check them against
   _main/_lane17-gate/evidence/*.log and against the receipt's own quoted output. Flag ANY
   number in the receipt that the logs do not support, and any claim that is stated more
   strongly than the evidence carries.

5. HOUSE RULES from LANE-BRIEF section 4. Specifically rule 2 (never pipe a native command
   when you need its exit code — look for `| Select-Object`, pipelines masking $LASTEXITCODE,
   or any place the gate's verdict could come from a closed pipe), rule 1 (no visible console
   window — check every process launch is CreateNoWindow/Hidden), and rule 5 (edit only owned
   files).

6. SILENT FAILURE. Is there any path where a stage fails but the gate still reports green?
   Any exception swallowed, any `except: pass`, any assertion whose failure still exits 0?

YOU MAY RUN, read-only, if you need to: the gate itself
(`pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane17-chain-gate.ps1`, ~45 s),
and greps/reads. Do NOT edit, create or delete any file in the repo. Never pipe a native
command when you need its exit code (`cmd > file 2>&1`, then read $LASTEXITCODE).

REPORT FORMAT — answer each of the 6 areas above with either CONCRETE DEFECTS (file:line +
why it is wrong + what would fix it) or `no defect found`, and end with a single line:
`VERDICT: PASS` or `VERDICT: FAIL` and one sentence of justification. Be adversarial and
specific. If you find nothing wrong in an area, say so plainly rather than inventing
concerns; a fabricated finding costs the project as much as a missed one.