# GATE VERDICT MATRIX - capture battery, repo H:/sotto/_moved/aireplay

AUDIT DATE: 2026-10-09 (filesystem mtimes read this session are 2026-10-09T20:51:06Z .. 2026-10-09T20:53:11Z)
SCOPE: H:/sotto/_moved/aireplay (nested git repo, branch main @ 1b6f56e per AUDIT-FINDINGS.md:259)
METHOD: READ-ONLY. No instrument was changed. No gate was run. No binary was built. No NVENC
        session and no WASAPI endpoint was opened. Every fact below is tagged:
          MEASURED  - I read the file/stat it myself this session
          READ      - I read it out of an existing document, quoted with file:line
          UNKNOWN   - nothing on disk answers it
INSTRUMENT OF RECORD: src/capture/run_battery.ps1 (28309 B, mtime 2026-10-09T19:51:44.179Z, 436 lines)
AGGREGATE OF RECORD: _main/logs/cap-battery-20261009-175104.txt (14036 B, 149 text lines,
        mtime 2026-10-09T20:53:10.937Z, MEASURED by stat + full read)

## 0. THE VOCABULARY A VERDICT MAY USE (from the instrument itself, not from me)

MEASURED, run_battery.ps1:24-25 (READ):
  0 = the battery RAN (rows may individually be refused - a refusal is a result).
  2 = the battery could not run at all (missing toolchain).
MEASURED, run_battery.ps1:173 (READ): a gate arm's row is MATCH or MISMATCH of rc vs its expected rc.
A row with no provenance tag is a defect (run_battery.ps1:410-435 tallies MEASURED/DERIVED/
NOT_MEASURED/untagged; untagged=0 in the aggregate of record).

## 1. THE DIRECT ANSWER TO "WHICH 7 GATES HAVE NO AGGREGATE VERDICT"

MEASURED. Population window H:/sotto/_moved/aireplay/_main, pattern ^_lane.*gate.*\.ps1$ (readdir,
this session) = 15 gates. This is the population the harness doc cites (README of the harness, READ at
_shadowplay-verify-harness.md:190: "The population was 8 then and is 15 now.").

THE 7 WITH NO AGGREGATE VERDICT ON RECORD (all MEASURED: each file's mtime is AFTER the aggregate ran):

  gate file                                  size     mtime (MEASURED this session)
  _main/_lane17-chain-gate.ps1               26616    2026-10-07T16:31:10.554Z
  _main/_lane18-ui-gate.ps1                  16967    2026-10-07T16:22:58.419Z
  _main/_lane19-receipt-audit-gate.ps1       15535    2026-10-07T16:28:51.522Z
  _main/_lane21-agents-truth-gate.ps1        12482    2026-10-07T16:15:35.708Z
  _main/_lane22-storage-gate.ps1             18045    2026-10-07T16:21:33.391Z
  _main/_lane24-wake-defects-gate.ps1        32565    2026-10-07T16:23:32.087Z
  _main/_lane25-locale-number-gate.ps1       17961    2026-10-08T01:03:03.994Z

Why they have none (MEASURED + READ):
- _main/_all-gates-real.txt, 1706 B, mtime 2026-10-07T16:10:16.263Z, its own header line 1:
  "ALL-GATES window=2026-10-07T13:00:19.1865937-03:00 ... GATES POPULATION = 8" (lines 1, 3).
  13:00:19-03:00 = 16:00:19Z. Every one of the 7 mtimes above is later than 16:10:16Z, so none of them
  existed when the only aggregate ran. Their verdict is UNKNOWN - not FAIL. VERDICT: UNKNOWN.
- _main/_all-gates-logs/20261007-130019/ holds exactly 8 .ps1.log files (MEASURED, readdir) and none
  of the 7 appears there - corroboration that they never ran under the aggregate.

TWO FINDINGS THE EXISTING DOCS DO NOT STATE (MEASURED, this session) - both matter, both correctable:

F-A. _main/_lane3-ringcap-gate.ps1 CHANGED AFTER THE AGGREGATE RAN. The aggregate's own census line
     (_all-gates-real.txt:8) records "20673 B  mtime=2026-10-07T15:31:24.8011753Z"; the file on disk
     today is 36787 B, mtime 2026-10-07T16:25:42.430Z (MEASURED, stat). Its recorded verdict
     "PASS / 26.4s" was measured against a revision that is no longer on disk. Treat as UNKNOWN-BY-
     SIZE-AND-MTIME, not as a current PASS.
F-B. _main/_lane16-wake-gate.ps1 CHANGED THE SAME WAY. _all-gates-real.txt:5 records
     "30116 B  mtime=2026-10-07T15:38:32.3829238Z"; on disk today it is 69294 B, mtime
     2026-10-08T00:39:04.764Z (MEASURED, stat). Its recorded verdict "FAIL/EXIT1 / 89.6s"
     (line 18, "the ONLY failure, OUT OF SCOPE" per line 27) is STALE-BY-SIZE-AND-MTIME. It is still
     out of scope, but it is no longer a measured failure either.

So of the 15 gates: 6 have an aggregate verdict measured against the byte-identical file that exists
today (_lane1-trigger 11956 B, _lane2-audio 32249 B, _lane23-trigger-defects 13674 B,
_lane4-index 9060 B, _lane7-window 23027 B, _lane9-asr 4391 B - each size matches
_all-gates-real.txt lines 4-11 exactly, MEASURED by comparison); 2 are stale (F-A, F-B); 7 are
UNKNOWN. That is 6 + 2 + 7 = 15. The "8 gates have verdicts" figure is therefore 6 current, not 8.

## 2. THE MATRIX - one row per gate step run_battery.ps1 runs today

Log names are exact, taken from the instrument's own code (run_battery.ps1 line refs are READ).
"EXISTS" = MEASURED by stat this session, with size and mtime.
Where the verdict line is quoted, the line number is the line INSIDE THAT LOG.

### Section 1. BUILD  (run_battery.ps1:122-147)

| step | log file | on disk | verdict | provenance |
|---|---|---|---|---|
| build capture binary | _main/logs/cap-build.txt | 0 B, 20:51:06.013Z; cap-build.txt.err 1908 B, 20:51:07.078Z (MEASURED) | rc=0 warnings=6 exe_bytes=783865 | MEASURED (report :21-22) |
| build gated mutant (control) | _main/logs/cap-build-mutant.txt | 0 B, 20:51:21.190Z; .err 343 B, 20:51:22.052Z (MEASURED). Output binary _main/build/aireplay-capture-mutant.exe 784377 B, mtime 2026-10-09T20:51:35.935Z (MEASURED, stat) | "mutant build rc=0 (control build: the gate compiled OUT)" report :24 | MEASURED |

Quoted verdict, cap-build.txt.err:2 (the only file that carries text; cap-build.txt itself is empty
because RunNative redirects stdout there and g++ writes nothing to stdout):
  audio_tap.cpp:576:7: warning: 'sotto::LoopbackTap' has a field 'sotto::{anonymous}::Endpoint ...'
Same file lines 5, 8, 11, 14, 17 = 6 warning lines, ALL in src/capture/audio_tap.cpp. This confirms
AUDIT-FINDINGS.md:164 "warnings=6 (all in audio_tap.cpp)".
Shipped binary: _main/build/aireplay-capture.exe, 783865 B, mtime 2026-10-09T20:51:21.144Z (MEASURED,
stat) - matches exe_bytes=783865 in the report row.
Shipped hash (report :25, READ): 6CADE9A3C1D4623C6779EC4CCEA5C7CA67027FB1F2FF3AB55F3B8FA6E1A05296

### Section 2. NVENC - the 5 "law-6 gate arms"  (run_battery.ps1:151-174, the loop that emits Row at :173)

These are the gate steps run_battery.ps1 itself runs. There are exactly 5 arms and the MUTANT arm is
conditional on the mutant exe existing (:157), which it did.

| arm | log file (_main/logs/) | on disk (MEASURED) | DECISION line IN that log | rc / expected | verdict |
|---|---|---|---|---|---|
| normal | cap-gate-normal.txt | 1128 B, 20:51:36.207Z | :16  DECISION: ARMED - codec=H.264 engines=2 max=4096x4096 (exit 0) | rc=0 / exp 0 | MATCH - PASS |
| tuning | cap-gate-tuning.txt | 1525 B, 20:51:36.425Z | :17  DECISION: REFUSED - NO ENCODER INITIALISED - the replay hotkey is NOT armed. Attempted: H.264:init(NvEncInitializeEncoder -> 8 (NV_ENC_ERR_INVALID_PARAM) | rc=3 / exp 3 | MATCH - REFUSED AS DESIGNED |
| no-nvenc | cap-gate-no-nvenc.txt | 1315 B, 20:51:36.612Z | :16  DECISION: REFUSED - NO ENCODER INITIALISED ... Attempted: H.264:open(INJECTED FAULT: nvEncodeAPI64.dll treated as absent) | rc=3 / exp 3 | MATCH - REFUSED AS DESIGNED |
| skip-map | cap-gate-skip-map.txt | 1444 B, 20:51:36.842Z | :17  DECISION: REFUSED - NO ENCODER INITIALISED ... Attempted: H.264:map(INJECTED FAULT: registered the texture but skipped NvEncMapInputResource) | rc=3 / exp 3 | MATCH - REFUSED AS DESIGNED |
| MUTANT-control | cap-gate-MUTANT-control.txt | 1408 B, 20:51:37.063Z | :18  DECISION: ARMED - codec=MUTANT(no gate) engines=0 max=0x0 (exit 0) | rc=0 / exp 0 | MATCH - CONTROL GOES RED-COLORED-BY-DESIGN |

Corroborating stdout redirections (all MEASURED to exist): cap-gate-normal.stdout.txt 1145 B,
cap-gate-tuning.stdout.txt 1545 B, cap-gate-no-nvenc.stdout.txt 1333 B,
cap-gate-skip-map.stdout.txt 1463 B, cap-gate-MUTANT-control.stdout.txt 1428 B, each with a 0-byte
.err sibling (written by RunNative at run_battery.ps1:56-62, script :160).

READ THIS THE RIGHT WAY: 4 of the 5 arms REFUSE on purpose and MATCH their expected rc, so a
"4 of 5 refused" reading is NOT a failing battery. The MUTANT-control arm is the arm that proves the
other four are not vacuous: it is the same binary compiled with -DAIREPLAY_GATE_OFF (script :139) and
it reports ARMED with engines=0, max=0x0 - a gate that can go red. AUDIT-FINDINGS.md:165-166 states
the same rule: "a gate that cannot go red is not a gate - this one can".
STEP COUNT for the aggregate rows: these 5 arms are report rows 2-6 (cap-battery-20261009-175104.txt
:32, :35, :38, :41, :44), all tagged MEASURED, all "MATCH".

### Section 3. WGC  (run_battery.ps1:177-220)

| step | log file | on disk | verdict | provenance |
|---|---|---|---|---|
| WGC live capture probe | _main/logs/cap-wgc-now.txt | 960 B, 20:51:37.235Z (MEASURED) | "probe rc=0  items_tried=5  E_ACCESSDENIED=5" report :51 | MEASURED |

Quoted lines from cap-wgc-now.txt itself (MEASURED, full read):
  :4   GraphicsCaptureSession::IsSupported -> 0x00000000 supported=1
  :6   CreateForWindow(our own window        ) -> 0x80070005 E_ACCESSDENIED     hwnd=0000000003b92062 ...
  :7   CreateForWindow(foreground window     ) -> 0x80070005 E_ACCESSDENIED     hwnd=0000000004891b26 ...
  :8   CreateForWindow(desktop window        ) -> 0x80070005 E_ACCESSDENIED     hwnd=000000000001000c ...
  :9   CreateForWindow(shell taskbar         ) -> 0x80070005 E_ACCESSDENIED     hwnd=0000000000010102 ...
  :10  CreateForMonitor(primary monitor     ) -> 0x80070005 E_ACCESSDENIED     item=0000000000000000
Verdict row: report :59-61 "MEASURED | WGC live capture -> REFUSED on 5 of 5 capture items,
0x80070005 E_ACCESSDENIED (IsSupported supported=1)". WINDOW (report :147, READ): this run only,
single pass. PROBE: 5 refusals in ONE probe run, 5 distinct capture items. It is NOT 5 population
samples - it is 1 probe with 5 items, and the refusal is process-wide and window-independent.
The probe that produced this is _main/wgc-probe.exe, 307103 B, mtime 2026-10-07T16:09:59.027Z
(MEASURED, stat). The source _main/wgc-probe.cpp is the sibling lane's file (script :218 READ).

### Section 4. MUXER  (run_battery.ps1:222-343)

Fixtures were ALREADY PRESENT, so the two fixture-generation steps wrote NO log this run
(script :235 "fixture present: ... ; continue"). MEASURED: _main/src/cap-1080p60.h264 146606044 B
(2026-10-07T15:15:23.841Z), _main/src/cap-2160p60.h264 149720741 B (2026-10-07T15:16:02.757Z).
Consequence: _main/logs/cap-gen-1080p60.txt and cap-gen-2160p60.txt DO NOT EXIST (MEASURED, stat
error) - and that is correct behaviour, not a missing verdict.

| step | log file (_main/logs/) | on disk (MEASURED) | verdict row in the report | provenance |
|---|---|---|---|---|
| muxer 1080p (3 cut runs) | cap-mux-1080p.txt + cap-mux-1080p.run1..3.stdout.txt | 1349 B, 20:51:38.696Z; 1363 B each x3 | :69-71 rc=0 aus=1800 bytes=146621246 med 479.6003 ms; ffprobe re-counts 1800 frames, null-decode stderr 0 B | MEASURED |
| muxer 4K (3 cut runs) | cap-mux-4k.txt + .run1..3.stdout.txt | 1343 B, 20:51:57.256Z; 1357 B each x3 | :73-75 rc=0 aus=1800 bytes=149735942 med 466.5204 ms; ffprobe 3840x2160, null-decode 0 B | MEASURED |
| mux-4k-LIED (control for a wrong --cut-size) | cap-mux-4k-LIED.txt + .run1..3.stdout.txt + .boxes.txt | 1352 B, 20:52:29.015Z; 1367/1367/1366 B; boxes 354 B | :77-79 DEFECT CONFIRMED: real SPS 3840x2160 vs container tkhd/avc1 1920x1080 | MEASURED |
| muxer on non-H.264 (RED arm) | cap-mux-junk.txt + .stdout.txt | 522 B, 20:52:57.925Z; 530 B | :80-82 rc=2 OFFLINE CUT FAILED: ring capacity below 16 MiB | MEASURED |
| generate small fixture | cap-gen-small.txt (+.err) | 0 B / 0 B @ 20:52:57.936Z / 20:52:57.937Z | no row - run_battery.ps1:330 pipes the rc to Out-Null, so neither a Say nor a Row is emitted | MEASURED |
| muxer below the ring floor | cap-mux-small.txt + .stdout.txt | 522 B, 20:52:58.010Z; 530 B | :83-85 rc=2, same wrong-blame message; 1 run on a 0.71 MiB stream | MEASURED |

Quoted from cap-mux-4k-LIED.boxes.txt:3-6 (MEASURED):
  tkhd  DECLARED size = 1920x1080   (16.16 raw 125829120,70778880)
  avc1  DECLARED size = 1920x1080
  SELFCHECK ok: moov@149720781+15161 trak@149720897+15045 tkhd@149720905+92
  => a player that trusts tkhd sizes this track 1920x1080, whatever the SPS says
This is the ONLY proof of the LIED defect: ffprobe reads the SPS and reports 3840x2160, so the
defect is invisible to ffprobe (script :290-291, READ). The box-level read
(_main/probe-cap-tkhd.ps1, 7295 B, 2026-10-07T15:24:53.137Z, MEASURED stat) is what shows it.

### Section 5. TIMING  (run_battery.ps1:345-392)

| step | log file (_main/logs/) | on disk (MEASURED) | verdict row | provenance |
|---|---|---|---|---|
| ffmpeg h264_nvenc 1080p x3 | cap-nvenc-1080p60-run1..3.txt (+.mp4) | .txt 0 B each @ 20:52:58.045 / 20:52:59.073 / 20:53:00.086Z; .mp4 23560929 B each @ 20:52:59.025Z / 20:53:00.037Z / 20:53:01.051Z | :96-98 med 1013.2 ms -> 3.377 ms/frame, POPULATION=3 WINDOW=300 frames | MEASURED |
| ffmpeg h264_nvenc 2160p x3 | cap-nvenc-2160p60-run1..3.txt (+.mp4) | .txt 0 B each @ 20:53:01.104Z / 20:53:04.293Z / 20:53:07.652Z; .mp4 28376536 B each @ 20:53:04.209Z / 20:53:07.389Z / 20:53:10.771Z | :99-101 med 3224.1 ms -> 10.747 ms/frame, POPULATION=3 WINDOW=300 frames | MEASURED |
| capture leg wall clock 1080p/4K | none - the row is emitted without running anything | no log file exists | :90-92 NOT MEASURABLE, POPULATION=0 runs | NOT MEASURED (script :350 emits it unconditionally) |
| 4K capture at all | none | no log | :93-95 NOT MEASURED (no capture leg runs at any resolution), POPULATION=0 | NOT MEASURED (script :361) |

The two .txt files being 0 bytes is correct: ffmpeg -loglevel error wrote nothing on success.

### Section 6. AUDIO ENDPOINTS  (run_battery.ps1:394-409)

| step | log file | on disk | verdict row | provenance |
|---|---|---|---|---|
| audio endpoints census | NONE - written inline into the report via Say (script :400) | n/a | :114-116 8 Win32_SoundDevice rows, MEASURED | MEASURED |
| per-API endpoint indices | NONE | n/a | :117-119 NOT ENUMERATED by this battery, POPULATION=0 | NOT MEASURED (script :406) |

The 8 devices are LISTED BY NAME ONLY (report :106-113, MEASURED) - none of them carries an MME,
DirectSound or WASAPI index, and the row says so (:116). AUDIT-FINDINGS.md:178-179 states the same.
This is the row that makes the AGENTS.md routing law (MME #2 / DirectSound #15 / WASAPI #32, not
interchangeable) UNMEASURED BY THIS BATTERY - the battery cannot confirm or deny it.

### Section 7. SUMMARY  (run_battery.ps1:411-435)

| step | log file | on disk | verdict | provenance |
|---|---|---|---|---|
| row tally | _main/logs/cap-battery-<timestamp>.txt | cap-battery-20261009-175104.txt, 14036 B, 20:53:10.937Z | :145 rows: MEASURED=15  DERIVED=0  NOT_MEASURED=3  untagged=0; :146 binary sha256=6CADE9A3...; :147 WINDOW: this run only, single pass, 2026-10-09 17:53:10.936 local; :149 battery done. Exit 0 means the battery RAN; it does not mean every row passed. | MEASURED |

## 3. CORRECTION TO THE BRIEF: THERE ARE **THREE** NOT_MEASURED ROWS, NOT TWO

The brief supplied to this audit says "the two rows that are NOT_MEASURED" and attributes both to
WGC. That is one row short. MEASURED, by reading all 18 summary rows (cap-battery-20261009-175104.txt
:126-143) and the instrument's own tally at :145:

  rows: MEASURED=15  DERIVED=0  NOT_MEASURED=3  untagged=0

The three NOT MEASURED rows are:
  1. capture leg wall clock at 1080p and 4K      (:90-92, and :138 in the table) - cause: WGC refused
  2. 4K capture at all                           (:93-95, and :139 in the table) - cause: WGC refused
  3. per-API endpoint indices (MME / DS / WASAPI) (:117-119, and :143 in the table) - cause: NOT
     ENUMERATED by this battery. NOT a WGC consequence. It is an audio gap.
The rows in the first two are the two the brief means; the third is a different defect in a different
section. Report all three, or the tally line (:145) will contradict the report.

## 4. WHAT HAS NO VERDICT ROW AT ALL IN THIS BATTERY

- All 15 _lane*-gate.ps1 lane gates (see section 1). run_battery.ps1 runs ZERO of them; the two
  instruments are disjoint. MEASURED: pattern-match of the two populations.
- Press-to-clip latency p95 - READ at AUDIT-FINDINGS.md:133 "no run yet".
- Any gate verdict for the 15-gate population on today's revisions - READ at
  AUDIT-FINDINGS.md:134, still true (see section 1).
- The delivery files the other lanes owe: _main/_timing/report.txt, _main/_tools/wgc.txt,
  _main/_tools/boxes.txt, _main/_tools/muxer.txt, _main/_tools/nvenc.html,
  _main/_receipts/review-43..46-lane-{f,g,h,i}.md, _main/_audit-verify/battery-summary.txt - ALL
  MEASURED ABSENT by stat this session, which corroborates AUDIT-FINDINGS.md:88-91
  ("DELIVERED - NOT READ YET ... Untracked on disk, awaiting the NAMED FILES").
- _main/_audit-verify/ does not exist in the nested tree (MEASURED, stat error). The battery named in
  AGENTS.md lives under H:/sotto/_main, a different repo. Do not cite one for the other.

## 5. THE EXIT CODE, STATED ONCE SO IT IS NOT MISREAD

The aggregate of record ends "battery done. Exit 0 means the battery RAN; it does not mean every row
passed." (cap-battery-20261009-175104.txt:149, MEASURED). 3 of its 18 rows are NOT MEASURED and one
of them (mux-4k-LIED, report :135) is a CONFIRMED DEFECT in the shipped product. Exit 0 is a
statement about the instrument, never about the product.
