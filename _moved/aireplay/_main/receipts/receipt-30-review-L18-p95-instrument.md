# receipt-30 -- REVIEW of aireplay lane L18 (press-to-clip p95 instrument)

REVIEW-VERDICT: PASS-WITH-DEFECTS

This is the independent reviewer row for lane L18. The lane is not done until this row
exists; this file is that row.

READ-ONLY REVIEW. The subject was measured by reading bytes on disk only. This review did
NOT run press-to-clip-probe.ps1, press-to-clip-probe.red.ps1, aireplay-capture.exe, any
NVENC/WGC session, or the capture battery: each writes clips and/or opens a device and/or
holds an NVENC session (machine-state change) and would breach the "no other lane gate
running" and "never open a device in a test" preconditions the probe itself enforces. The
only byte this review wrote is this receipt.

## 0. POPULATION / WINDOW / DATE  (tighter population/window is restated when an item differs)
- SUBJECT POPULATION: the product tree H:/sotto/_moved/aireplay, lane L18 = _main/_p95-instrument/.
- WINDOW: the tree as read during this review.
- DATE (UTC) of this review: 2026-10-10 (program clock 2026-10-10T03:27:30.798Z). Every
  number below was (re)measured from disk on that date. File mtimes are quoted separately.
- NOT the subject: the parent tree H:/sotto/app, H:/sotto/app/panel, H:/sotto/app/webview
  was never read or edited.
- Subject artefacts (stat + sha256 this review, 2026-10-10):
    probe   press-to-clip-probe.ps1        32935 B  675 LF  0 CR  0 non-ASCII  sha256 460411595EC4447B4C5CB20BD6C0E0DDBC9438E8B733199946E24A50D27887AC  mtime 2026-10-09T23:39:46.385Z
    red     press-to-clip-probe.red.ps1    36142 B  722 LF  0 CR  0 non-ASCII  sha256 6FD3D2BF811205CD830A0EBFB213079E8FF4011EC15AA871352B97003F0943AE  mtime 2026-10-09T23:41:30.389Z
    feed    _main/src/cap-small.h264        746792 B  sha256 49C88C90BA4B6B066632A5FBE176C7B5DF64D5256ED9D87579C7C211302E1260  mtime 2026-10-09T20:52:57.985Z
    exe     _main/build/aireplay-capture.exe 783865 B  sha256 6CADE9A3C1D4623C6779EC4CCEA5C7CA67027FB1F2FF3AB55F3B8FA6E1A05296  mtime 2026-10-09T20:51:21.144Z
    log     _main/logs/cap-battery-20261009-175104.txt  14036 B  149 lines  mtime 2026-10-09T20:53:10.937Z  (aggregate of record)

## 1. The five verification targets

V1  real FAIL colour  ->  PRESENT BY DESIGN, NOT DEMONSTRATED ON THIS BOX (run-verified).
    The control arm exists as a sibling file, press-to-clip-probe.red.ps1, "the SAME file
    plus one injected mutation and the self-check that must catch it" (README.md section 3;
    note red-arm line/size counts in that table are CONFIRMED exact: 675/32935 and 722/36142).
    Verified by reading the disk bytes (no run): the mutation force-replaces the pre-cut
    anchor ($tCmd) with the constant 0.0, so every measured delta collapses to the raw
    stopwatch epoch; a CONTROL-ARM SELF-CHECK then takes the median of the sorted deltas
    (Get-Percentile -Sorted $sorted -P 50) and, if the mutation is active and that median
    exceeds 1000.0 ms, prints RED-MUTATION and exits 1 (red 621-630) -- exactly the contract
    line "1 RED -- ... this is the code the control arm must return" (probe header 36-42).
    The red arm additionally carries a SECOND catcher (close-on-first-sight: completion test
    replaced by "file exists", caught via size_matches_reply mismatch, red 633-640 -> exit 1)
    and an unknown-mutation refuse (red 641-643 -> exit 2). So the control ships TWO catchers
    and can say NO; README section 3 saying "one injected mutation" understates it (trivial,
    not a defect: the default mutation is zero-t-cmd, the second mode is extra coverage).
    CAVEAT that bounds the verdict: README section 0 (lines 9-16) states every exit code, every
    verdict word and the control RED are "DESIGNED AND UNVERIFIED ... what the code does when
    read, not what was observed", because the directory was delivered "parse-checked, NEVER
    EXECUTED". Corroborated on disk: _p95-instrument/ contains only 2 .ps1 + 2 .md and NO log
    (cuts.jsonl / child-stdout.log / capture log all absent). So "an arm that DOES go RED on a
    broken subject" is SOURCE-VERIFIED here, NOT RUN-OBSERVED on this box.

V2  are exit codes contracts / F16.8  ->  CODES ARE A DECLARED CONTRACT; F16.8 IS LIVE IN CURRENT BYTES.
    probe header lines 36-42, verbatim: "EXIT CODES (the exit code IS the verdict): 0 GREEN --
    n cuts finalised, box walk clean on every clip ...;  1 RED -- at least one self-check failed
    (this is the code the control arm must return);  2 FAIL -- the measurement could not be
    taken, with the reason printed (refusal, timeout, insufficient population, precondition
    violation);  3 reserved for the control file; this file does not return it."
    MAIN PATH IS CONSISTENT: the final verdict block (627-630) sets $verdict GREEN, flips to RED
    if $script:Failures.Count -gt 0, prints the matching word, and (674-675) exits 1 on
    non-GREEN else 0. GREEN->0, RED->1 agree with the contract; the JSON summary carries
    verdict, child_exit and failures (637-642) so a code-driven consumer never guesses.
    F16.8 IS PRESENT in the current bytes: the branch at 584-590
        if ($deltas.Count -eq 0) { Say ""; Say "VERDICT RED" Red; Say "  REASON: no cut
        produced a measurable delta -- nothing was finalised." Red; ...; exit 2 }
    fires precisely on "no cut produced a measurable delta -- nothing was finalised" -- the
    contract's own words for exit 2 (FAIL / insufficient population). So a subject on which NO
    cut finalised (the refusing pre-fix exe, or a timeout) is labelled with the WORD reserved
    for a measured-and-failed outcome ("VERDICT RED") while emitting the CODE for
    could-not-measure (exit 2). The word and the code disagree, inside one run, on the shipped
    file. F16.8's central assertion (a subject that refused could not be measured prints the
    word RED over exit 2) ACCURATELY describes the current bytes.
    Refinement against F16.8's exact wording: F16.8 says "the FAIL branch lost its reason string
    in the first run". In the CURRENT bytes the branch DOES print a reason (587) and an explicit
    "HALF A (keypress -> cut decision) remains UNKNOWN" note (588). So the reason-loss symptom
    does NOT hold in the current file; only the word/code disagreement survives.

V3  re-derive every latency/miss number  ->  SURVIVES only for the census + log of record;
    the F16.6/F16.7 run numbers are UNKNOWN (their logs are absent on disk).
    SURVIVING, re-derived from disk this review (see table below): the NAL census of cap-small.h264
    (VCL 300 = 298 type-1 + 2 type-5; SPS type-7 x2; PPS type-8 x2 -> aus=300), the exe subject
    identity (783865 B / sha 6CADE9A3... = the pre-fix binary that still refuses SPS/PPS cuts), and
    the build + NVENC-gate rows of the aggregate of record cap-battery-20261009-175104.txt.
    UNKNOWN, no log on disk (verified absent this review): every F16.6 and F16.7 run number --
    commands_served, cuts_sent, clips_opened, clips_closed, cuts_refused, cuts_executed,
    frames_written, bytes_written, largest_clip_bytes, child exit 0, aus_waited_for_idr=1005, the
    n=5 / p50=1249 / p95=28542 / floor=1166 / pollHz=858.0 summary, the 5 refused cuts, the 5
    moov-last box-walk failures (last state chain-ok-last-is-mdat). A tree-wide grep of the
    F16.6/F16.7 signature strings returned hits ONLY in audit/ledger prose, replay.cpp source,
    probe source lines and README -- never in a run log. cap-battery-20261010-000317.txt
    (F16.6 LANE_LOG) is ABSENT; cuts.jsonl, child-stdout.log, exe.log, _p95 payload and a
    _main/p95-runs dir are ABSENT; the I:/cc-tmp/p95-instrument/run run dir is ABSENT. These
    numbers therefore survive ONLY as prose quoted in AUDIT-FINDINGS F16.6/F16.7, unaccompanied
    by any surviving log. The instrument that would re-derive them is press-to-clip-probe.ps1 (its
    child-stdout.log + cuts.jsonl + _p95 payload under its redirect); the log-of-record naming
    convention is _main/logs/cap-battery-<yyyymmdd-hhmmss>.txt -- neither holds a p95 run.

V4  no-visible-window  ->  HONOURED on the named spawn surface (source-verified, not run-observed).
    Spawn surface: press-to-clip-probe.ps1 lines 330-353 build the child ProcessStartInfo for
    _main/build/aireplay-capture.exe with UseShellExecute=$false (347), CreateNoWindow=$true
    (348), RedirectStandardInput/Output=$true (349-350), and TMPDIR forced to I:\cc-tmp
    (342,352-353). No ShellExecute window, no owner console spawned. The probe also runs its own
    ConsoleVisibility census (244-262) over its own pid tree. No p95 console-window census log
    exists on disk, so this claim is by source, not by run.

V5  ever open an audio device / start capture  ->  NO. DEVICE-FREE BY CONSTRUCTION.
    The child arguments (330-346) are the device-free cut arm: --cut-session --cut-from-h264
    <feed> --cut-dir <dir> --cut-fps N --cut-size WxH --cut-log <file>. There is NO audio flag,
    NO --run, NO --stdin. README section 2 (source-verified) states the --cut-session arm
    (main.cpp arm_cut_session, 1235-1324) contains ZERO NVENC / WGC / D3D11 / AudioTap
    references -- exactly why the instrument can measure half B "without opening a device". The
    probe additionally runs a device-ownership preflight (178-186, 264-270) that REFUSES to start
    if another lane gate owns NVENC/WASAPI, printing the offending pid + command line, and purges
    its own TMPDIR children on any refusal (283-291) before exit 2. No audio device is opened; no
    capture is started. (The only capture sessions ever logged in _main/logs are cap-* and
    lanef-*; none is a p95-instrument run.)

## 2. Surviving claims (each with evidence)
S1  Subject bytes/lines/sha match documentation. POPULATION: the 4 statted artefacts; WINDOW: tree
    as read 2026-10-10; DATE 2026-10-10. Evidence: section 0 table. README section 3 line counts
    (675 / 722) and sizes (32935 / 36142) are CONFIRMED exact -- no doc drift.
S2  The instrument measures the CUT half (B) only and says so on every run, and labels HALF A
    (keypress -> cut decision) UNKNOWN. POPULATION: probe + README; WINDOW 2026-10-10. Evidence:
    README 28-29 ("A is UNKNOWN here, and no number this instrument prints may be quoted as
    press-to-clip latency") and probe output 588, 634-635, 661 and JSON runRec half_a/half_b
    (661-662). This is the honest decomposition the lane promised and it is kept.
S3  The completion test is a real box-chain walk, not a size-stability guess. POPULATION: probe
    101-154; WINDOW 2026-10-10. Evidence: Test-Mp4Finalised walks the top-level box chain, requires
    it to end exactly at file length with last box "moov", MaxBoxes=8192, documented as "NOT a
    full ISO-BMFF or decode validation". F16.7's failure mode (chain-ok-last-is-mdat) maps to the
    last-is-mdat branch (probe 149).
S4  Exit codes are a declared, mostly-honoured contract, and the dangerous direction never occurs:
    GREEN only exits 0 when n cuts finalised AND every box walk clean AND reply/size consistency
    held AND poll cadence met (36-42, 613-625, 627-675); a zero-delta run exits 2 (584-589) and
    the only GREEN exit requires $verdict -eq GREEN (674-675). POPULATION: probe; WINDOW 2026-10-10.
S5  The control arm is source-verified to say NO and exit 1, on two distinct sabotage modes.
    POPULATION: press-to-clip-probe.red.ps1 on disk; WINDOW 2026-10-10. Evidence: red 621-630
    (zero-t-cmd median>1000 -> RED-MUTATION + exit 1), 633-640 (close-on-first-sight -> exit 1),
    641-643 (unknown -Mutation -> exit 2), header "MUST go RED".
S6  Run-safety / clean-refusal surface is present. POPULATION: probe; WINDOW 2026-10-10. Evidence:
    TempFiles registry + durability cleanup (200-238), ConsoleVisibility census (244-262),
    device-ownership refusal broadcast (264-270), TMPDIR child purge + REFUSED exit 2 (283-291),
    child non-zero ExitCode treated as an error not success (293-311), ffmpeg/ffprobe-missing
    refusal (325-329), stdin-pump orphan detection -> exit 2 (344-363).

## 3. Refuted claims (each with the refuting measurement)
R1  F16.8's symptom "the FAIL branch lost its reason string in the first run" is REFUTED for the
    CURRENT bytes. POPULATION: probe 584-590; WINDOW 2026-10-10; DATE 2026-10-10. Refuting
    measurement: the zero-delta FAIL branch prints a REASON line (587) and an explicit "HALF A
    remains UNKNOWN" line (588). The word/code disagreement F16.8 names DOES survive (D0); only the
    "reason lost" sub-clause is refuted against the shipped revision.
R2  README section 3 red-arm "722 lines" is CONFIRMED, not refuted: fresh direct LF count of
    press-to-clip-probe.red.ps1 = 722 (probe = 675). Both match README exactly. (Recorded so no one
    re-flags a phantom line-count drift.)

## 4. Defects (each with POPULATION / WINDOW / DATE)
D0  [LIVE, owned by L18] word/code disagreement on the FAIL port. press-to-clip-probe.ps1 lines
    586-589 print VERDICT RED then exit 2, while the file's own contract (36-42) names 2 as FAIL
    ("could not be taken / insufficient population") and reserves RED for exit 1. A subject on
    which no cut finalised is labelled "RED" (the word) and "FAIL" (the code) in one run. SEVERITY:
    low -- the exit CODE is correct, a reason IS printed (587), no false GREEN, no fabricated number;
    the harm is verbatim (a human reading the broadcast word sees a "measured and failed" label on
    an "unmeasured" outcome) and it violates the file's own "the exit code IS the verdict". FIX
    (narrow): relabel line 586 to the FAIL vocabulary (e.g. "VERDICT FAIL -- could not measure") so
    the word matches code 2; leave exit 2 as is. Inherited by the red file too. Cite: AUDIT-FINDINGS
    F16.8; DEBT-LEDGER L18 row line 142. POPULATION: press-to-clip-probe.ps1 on disk; WINDOW: current
    bytes; DATE 2026-10-10.
D1  [bounded caveat] the control arm's RED is DESIGNED AND UNVERIFIED (README section 0, 13-16):
    _p95-instrument was delivered parse-checked and never executed, and holds no run log on disk.
    The house rule (an instrument that cannot say NO is worthless / every gate ships both colours)
    is satisfied as a DELIVERED artefact -- the control exists and is wired to exit 1 -- but the red
    colour is read-verified, not run-observed, on this box. This is a delivery-condition bound, not a
    code defect; it is the single thing the owner must do before the RED assertions count.
    POPULATION: _p95-instrument/ (2 .ps1, 2 .md, no log); WINDOW: tree as read; DATE 2026-10-10.
D2  [trivial note, not a code defect] README section 3 says the red arm is "SAME file plus ONE
    injected mutation"; the file actually carries TWO catchable sabotage modes (zero-t-cmd default +
    close-on-first-sight) plus an unknown-motion refuse (red 633-643). Strictly stronger than
    described, so only the README prose understates the coverage. POPULATION: README.md +
    press-to-clip-probe.red.ps1; WINDOW 2026-10-10.
D3  [standing debt, NOT an L18 regression] latency HALF A (keypress -> cut decision) is UNKNOWN by
    design while the hotkey path is off by default; probe (588/661) and README (28-29) both declare
    this rather than paper over it. DEBT-LEDGER L18 row records it correctly; no fix is owed to L18.

## 5. UNKNOWNs (logs absent -- named, not guessed)
- F16.6 run block (commands_served/cuts_sent/clips_opened/clips_closed/cuts_refused/
  cuts_executed/frames_written/bytes_written/largest_clip_bytes/child-exit-0; post-fix exe 787009 B /
  sha DD61F920...; LANE_LOG cap-battery-20261010-000317.txt): UNKNOWN from disk -- that log and the
  p95 run artefacts are ABSENT. Would-be instrument: press-to-clip-probe.ps1 child-stdout.log +
  cuts.jsonl + _p95 payload.
- F16.7 run block (n=5 summary p50=1249 / p95=28542 / floor=1166 / pollHz=858.0; 5 refused cuts;
  5 moov-last failures; aus_waited_for_idr=1005): UNKNOWN from disk. Partial cross-check that DOES
  survive: cap-small.h264 has 300 VCL NALs (298 type-1 + 2 type-5) and 2 IDRs, so aus=300 is
  consistent with the feed; aus_waited_for_idr=1005 is not derivable from any surviving file.
- The p95-instrument exit colours are not run-verified on this box (see D1).
- Whether the fixcut post-fix binary was ever merged into the SHIPPED _main/build exe: the on-disk
  exe is the PRE-FIX 783865 B / 6CADE9A3... (mtime 2026-10-09T20:51:21Z), i.e. the binary that
  still refuses SPS/PPS cuts; F16.6's 787009 B build is NOT in _main/build. This is an L17
  lane-state fact, not an L18 instrument defect, recorded so this row is not misread as "the fix
  is shipped".

## 6. Verdict and what L18 still owes
The L18 instrument is sound, unusually honest about its own scope (half B only; half A UNKNOWN; a
not-measured is never dressed as a pass), device-free and window-clean on its named spawn surface,
and it ships both colours with two catchers on the red arm. It is NOT a clean PASS because D0 (the
F16.8 word/code disagreement) is live in the shipped bytes; it is NOT a NO because every defect is
in the safe direction (correct exit codes, reasons printed, no fabricated numbers, no device opened).
To close the lane: (1) repair or drop the line-586 wording so the word matches code 2 (D0);
(2) run one smoke pass of BOTH arms on an idle box and staple the resulting cuts.jsonl +
child-stdout.log + a cap-battery-<ts>.txt into this tree, which turns the D1 read-verified RED into
a run-verified one and re-derives the F16.6/F16.7 numbers now UNKNOWN; (3) optionally tighten the
README "one injected mutation" prose (D2).

-- independent reviewer, 2026-10-10 (UTC 2026-10-10T03:27Z). READ-ONLY on the subject; only this
receipt was written. Not committed (receipts/ is git-ignored via .gitignore:105
_moved/aireplay/_main/*/); no git add -f, no commit, no re-run of any probe/exe/battery.
