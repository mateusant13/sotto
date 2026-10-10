# HONEST BASELINE - capture pipeline, H:/sotto/_moved/aireplay

AUDIT DATE: 2026-10-09. READ-ONLY AUDIT: no instrument changed, no gate run, no device opened.
EVERY NUMBER BELOW IS TAGGED with the file it came from. Where I read the file myself this session
the tag is MEASURED; where I quote an existing document it is READ (with file:line). Nothing here is
an estimate, an extrapolation or a rounded GUESS.

AGGREGATE OF RECORD (the single battery this baseline is built on):
  H:\sotto\_moved\aireplay\_main\logs\cap-battery-20261009-175104.txt
  149 text lines (150 lines incl. the trailing newline), 14036 B, mtime 2026-10-09T20:53:10.937Z.
  MEASURED: stat + full read this session.

## 1. THE EXACT COMMAND THAT REPRODUCES THE AGGREGATE

READ, AUDIT-FINDINGS.md:154-156:
  Launcher: I:/cc-tmp/lanef_battery_run.cmd ->
    pwsh -NoProfile -Profile-free run of the battery in the SHARED tree. Verbatim from that file:
    pwsh -NoProfile -File H:\sotto\_moved\aireplay\src\capture\run_battery.ps1 \
      -Root H:\sotto\_moved\aireplay -Reps 3 -Census < NUL > I:/cc-tmp\lanef-battery.txt 2>&1

  Measured flags, spelled out:
    -Reps 3    = POPULATION=3 for the external ffmpeg h264_nvenc encoder runs (report :98, :101)
    -Census    = requested the window census; it produced NO census rows (see section 12, defect F3d)

  The script name and flags are READ; that this exact command produced the report of record is
  READ (same file, :149-153). I did NOT run it. Anything not produced by a command I can quote is
  not in this baseline.

## 2. MACHINE CONTEXT (report :7, :12-16, MEASURED by read)

  toolchain   ffmpeg=True  ffprobe=True  gxx=True
  gpu         NVIDIA GeForce RTX 5080  driver=32.0.16.1714
  cpu         13th Gen Intel(R) Core(TM) i5-13600K  14C/20T
  ram         47,74 GiB total, 25,96 GiB free
  nvidia-smi  rc=0
  display     DISPLAY1 1920x1080

## 3. BUILD RESULT (report :21-27, MEASURED)

  capture binary   rc=0  warnings=6  exe_bytes=783865
  mutant (control) rc=0   (the same 11 sources compiled with -DAIREPLAY_GATE_OFF, script :139)
  shipped binary   _main/build/aireplay-capture.exe, 783865 B, mtime 2026-10-09T20:51:21.144Z
                   (MEASURED by stat; size matches exe_bytes above)
  mutant binary    _main/build/aireplay-capture-mutant.exe, 784377 B, mtime 2026-10-09T20:51:35.935Z
                   (MEASURED by stat)
  sha256 of the shipped binary (report :146, MEASURED):
    6CADE9A3C1D4623C6779EC4CCEA5C7CA67027FB1F2FF3AB55F3B8FA6E1A05296
  Warnings: all 6 in src/capture/audio_tap.cpp, at :576, :803, :460, :421, :396, :238
    (MEASURED by reading _main/logs/cap-build.txt.err - the only file of that pair with bytes;
     cap-build.txt itself is 0 B because g++ writes to stderr). Corroborates AUDIT-FINDINGS.md:164.
  Every row below is measured against THAT hash. A different hash is a different battery
    (report :27, MEASURED).

## 4. EVERY NVENC GATE ARM RESULT (report :32-46, MEASURED) - 5 arms, all MATCH their expected rc

  arm            rc  expected  DECISION (verbatim from _main/logs/cap-gate-<arm>.txt)
  normal         0   0         DECISION: ARMED - codec=H.264 engines=2 max=4096x4096 (exit 0)   [:16]
  tuning         3   3         DECISION: REFUSED - NO ENCODER INITIALISED - the replay hotkey is
                               NOT armed. Attempted: H.264:init(NvEncInitializeEncoder -> 8
                               (NV_ENC_ERR_INVALID_PARAM)                                        [:17]
  no-nvenc       3   3         DECISION: REFUSED - NO ENCODER INITIALISED - ... Attempted:
                               H.264:open(INJECTED FAULT: nvEncodeAPI64.dll treated as absent)   [:16]
  skip-map       3   3         DECISION: REFUSED - NO ENCODER INITIALISED - ... Attempted:
                               H.264:map(INJECTED FAULT: registered the texture but skipped
                               NvEncMapInputResource)                                            [:17]
  MUTANT-control 0   0         DECISION: ARMED - codec=MUTANT(no gate) engines=0 max=0x0 (exit 0) [:18]

  Read the table the right way: 4 of 5 arms REFUSE BY DESIGN and MATCH. "4 of 5 refused" is not a
  failing battery. The MUTANT-control arm is the control that proves the other four are not vacuous
  - the same binary with the gate compiled out reports ARMED with engines=0 and max=0x0
  (cap-gate-MUTANT-control.txt:15, MEASURED: "<-- A LIE: the gate is compiled out"). A gate that can
  go red is a gate. This one can.

## 5. WGC RESULT (report :49-61, MEASURED)

  probe rc=0   items_tried=5   E_ACCESSDENIED=5
  IsSupported: supported=1 (the API says yes; the box says no)
  The 5 refused items (cap-wgc-now.txt:6-10, MEASURED):
    own window, foreground window, desktop window, shell taskbar, primary monitor
    - every one 0x80070005 E_ACCESSDENIED
  POPULATION=1 probe run with 5 distinct capture items - NOT 5 independent runs
  PROBE of record: _main/wgc-probe.exe, 307103 B, mtime 2026-10-07T16:09:59.027Z (MEASURED, stat)
  CONSEQUENCE for the whole pipeline: the capture leg cannot run at ANY resolution on this box,
    so nothing downstream of "capture" has a measurement - see section 9.

## 6. MUXER ROWS (report :64-85, MEASURED) - the offline H.264 cut, end to end

  row                       rc   aus   bytes         wall_ms med  ffprobe
  mux-1080p (1920x1080)     0    1800  146621246     479.6003      h264 Main 1920x1080 60/1
  mux-4k    (3840x2160)     0    1800  149735942     466.5204      h264 Main 3840x2160 60/1
  mux-4k-LIED (wrong size)  0    1800  149735942     484.2         real SPS 3840x2160 BUT
                                container tkhd/avc1 DECLARED 1920x1080   <-- DEFECT, see below
  muxer on a non-H.264 arm  2    -     -                        OFFLINE CUT FAILED
  muxer below the ring floor 2    -     -                        OFFLINE CUT FAILED
  POPULATION=3 cut runs per resolution (median reported), 1 ffprobe, 1 null-decode each.
  null-decode stderr = 0 B on both good rows. ffprobe independently re-counts 1800 frames.
  Artifacts still on disk (MEASURED, stat): _main/runs/cap-mux-1080p.mp4,
    _main/runs/cap-mux-4k.mp4, _main/runs/cap-mux-4k-lied.mp4 - 3 files, exactly the 3 green rows;
    the two RED arms left no .mp4, which is the correct outcome.

  THE ONE PRODUCT DEFECT MEASURED IN THIS RUN - mux-4k-LIED (report :77-79, and the box-level read
  _main/logs/cap-mux-4k-LIED.boxes.txt:3-6, MEASURED):
    tkhd  DECLARED size = 1920x1080   (16.16 raw 125829120,70778880)
    avc1  DECLARED size = 1920x1080
    SELFCHECK ok: moov@149720781+15161 trak@149720897+15045 tkhd@149720905+92
    => a player that trusts tkhd sizes this track 1920x1080, whatever the SPS says
  ffprobe CANNOT see this because ffprobe reads the SPS. Cause (READ, AUDIT-FINDINGS.md:186-188):
  mp4_writer.cpp writes cfg_.width/height into BOTH the avc1 sample entry and the tkhd track
  header, and replay.cpp cut_from_h264 assigns w_/h_ from --cut-size rather than from the stream.
  Verdict: DEFECT CONFIRMED, rc=0 - it fails silently, which is the expensive kind.
  Verdict: MEASURED, POPULATION=3 cut runs, UNFIXED as of 2026-10-09.

## 7. TIMING ROWS (report :86-101, MEASURED) - ENCODER only, measured with an EXTERNAL tool

  ffmpeg h264_nvenc, 300 frames, 1920x1080: wall_ms med=1013.2  -> 3.377 ms/frame
  ffmpeg h264_nvenc, 300 frames, 3840x2160: wall_ms med=3224.1  -> 10.747 ms/frame
  POPULATION=3 successful runs each, WINDOW=300 frames.
  Those numbers include lavfi source generation and muxing; the encode itself is a subset
  (report :97, :100, quote). They are NOT the product's own numbers - they are ffmpeg's, measured
  on this box, by a tool that is independent of the product.
  Artifacts (MEASURED, stat): cap-nvenc-1080p60-run{1,2,3}.mp4 23560929 B each and
  cap-nvenc-2160p60-run{1,2,3}.mp4 28376536 B each, in _main/logs/ (sizes identical per arm).

## 8. AUDIO ROWS (report :103-119, MEASURED)

  8 Win32_SoundDevice rows, every one state=OK status=3, listed BY NAME ONLY:
    Dispositivo de audio USB (x2), NVIDIA High Definition Audio,
    NVIDIA Virtual Audio Device (Wave Extensible) (WDM), NVIDIA Broadcast,
    Realtek High Definition Audio, VB-Audio VoiceMeeter VAIO, VB-Audio Virtual Cable
  Win32_SoundDevice does NOT report MME/DirectSound/WASAPI indices (report :116, MEASURED).
  THEREFORE this battery neither confirms nor denies the routing law in AGENTS.md
  ("CABLE Output exists at MME #2 / DirectSound #15 / WASAPI #32, not interchangeable").
  If someone cites this report for a CABLE index, they are citing the wrong instrument.

## 9. THE NOT MEASURED ROWS AND WHY (report :90-95, :117-119, MEASURED) - THREE, not two

  1. "capture leg wall clock at 1080p and 4K" - NOT MEASURABLE. POPULATION=0 runs.
     Cause: WGC refuses every capture item (section 5), so there is no capture leg to time.
  2. "4K capture at all (not just 4K timing)" - NOT MEASURED. POPULATION=0 runs.
     Cause: same; no capture leg runs at ANY resolution.
  3. "per-API endpoint indices (MME / DirectSound / WASAPI)" - NOT ENUMERATED. POPULATION=0.
     Cause: this battery only runs a name-level CIM query; a per-API enumeration
     (IAudioClient::GetMixerFormat / IMMDeviceEnumerator per API) was never run.
  Rows 1 and 2 are the WGC consequence. Row 3 is an AUDIO gap with nothing to do with WGC.
  The battery's own tally (report :145, MEASURED) says: rows: MEASURED=15  DERIVED=0
  NOT_MEASURED=3  untagged=0. A report claiming "2 NOT_MEASURED rows" contradicts that tally.

## 10. THE LINES THAT BOUND EVERY CLAIM ABOVE (report :145-149, MEASURED)

  :145  rows: MEASURED=15  DERIVED=0  NOT_MEASURED=3  untagged=0
  :146  binary sha256=6CADE9A3C1D4623C6779EC4CCEA5C7CA67027FB1F2FF3AB55F3B8FA6E1A05296
  :147  WINDOW: this run only, single pass, 2026-10-09 17:53:10.936 local
  :148  full log: H:\sotto\_moved\aireplay\_main\logs\cap-battery-20261009-175104.txt
  :149  battery done. Exit 0 means the battery RAN; it does not mean every row passed.
  Timezone note (MEASURED, no silent conversion): the file's own name and header
  (:3 "CAPTURE CAPABILITY BATTERY 2026-10-09 17:51:04.695 -03:00") are LOCAL (-03:00), so
  17:51:04 local = 20:51:04.695Z, which is exactly the UTC mtimes of the logs above.
  WINDOW is ONE RUN, SINGLE PASS. There is no repeated battery of record to average with, so
  no number here has a confidence interval, and none may be quoted as a series.

## 11. LANE-GATE VERDICTS ON RECORD (population 15) - the other half of the gate picture

  Full census, per-gate table and the two stale-verdict findings are in gate-verdict-matrix.md
  section 1. In one line each, all MEASURED this session:
  - 6 of 15 gates have an aggregate verdict measured against the byte-identical file on disk today
    (_lane1-trigger 11956 B, _lane2-audio 32249 B, _lane23-trigger-defects 13674 B,
     _lane4-index 9060 B, _lane7-window 23027 B, _lane9-asr 4391 B).
  - 2 are STALE-BY-SIZE-AND-MTIME: _lane3-ringcap (aggregate saw 20673 B, disk has 36787 B) and
    _lane16-wake (aggregate saw 30116 B, disk has 69294 B). Their recorded PASS/FAIL are not
    current verdicts.
  - 7 are UNKNOWN - no aggregate verdict exists at any revision:
    _lane17-chain, _lane18-ui, _lane19-receipt-audit, _lane21-agents-truth, _lane22-storage,
    _lane24-wake-defects, _lane25-locale-number.
  - The only aggregate that exists, _main/_all-gates-real.txt (window
    2026-10-07T13:00:19.1865937-03:00, mtime 2026-10-07T16:10:16.263Z), says
    "SUMMARY gates=8 passed=7 failed=1" and "FAILED: _lane16-wake-gate.ps1" - and that failure
    is a gate-instrument failure OUT OF SCOPE, not a product failure. Never average it into a
    clone verdict.

## 12. WHAT THIS BASELINE DOES **NOT** PROVE

  - Any capture number at 1080p or 4K. None exists; WGC refuses. UNKNOWN, not zero.
  - That the product ever opened a WASAPI endpoint. The battery enumerates names only (section 8)
    and every loopback/WASAPI claim in AGENTS.md is out of this instrument's reach.
  - Press-to-clip latency p95 - READ at AUDIT-FINDINGS.md:133, "no run yet".
  - That no console window appeared. The -Census flag produced no census rows
    (READ, AUDIT-FINDINGS.md:199-200). UNKNOWN. A run cannot be described as "no window".
  - Any behavior after 2026-10-09T20:53:10.937Z. Nothing in this baseline is a claim about the
    current live state of the tree - and _main/build, _main/logs, _main/runs, _main/src all move
    whenever the battery runs.
  - Nothing about the 15 lane gates as of today (section 11).

## 13. COUNT DISCREPANCIES FOUND WHILE MEASURING (both against the report of record)

  a) AUDIT-FINDINGS.md:175 says "TIMING 3 rows" and then lists 4 (two NOT MEASURED plus the two
     EXTERNAL encoder rows). The report's timing section is 4 rows (report :90, :93, :96, :99).
     The 3-vs-4 is a doc slip; the rows themselves are correctly quoted.
  b) AUDIT-FINDINGS.md:175-177 does not mention the third NOT MEASURED row (per-API audio
     indices). See section 9 - that omission is what produced the "two NOT_MEASURED rows" belief.
## 14. CORRECTION 2026-10-10 - ONE BULLET IN SECTION 12 WAS TRUE THEN AND IS FALSE NOW

   Section 12 said, and still reads above:
     "Press-to-clip latency p95 - READ at AUDIT-FINDINGS.md:133, 'no run yet'."
   TRUE on 2026-10-09 when the aggregate ran. FALSE on 2026-10-10: the p95 instrument
   now exists and has RUN. Measured: source
   `_main/_p95-instrument/press-to-clip-probe.ps1` (32 935 B / 676 lines / 0 CRLF /
   pure ASCII / mtime 2026-10-09T23:39:46Z), result recorded in AUDIT-FINDINGS F16.7:
     PA: 10 cuts requested in one run of the p95 probe (child stdout, cadence 150 ms);
         n=5 executed cuts; p50=1 249 ms, p95=28 542 ms, max=28 542 ms, floor=1 166 ms,
         pollHz=858.0.
     WINDOW: ONE run of that probe, single pass. No series, no confidence interval.
   The stale bullet is left standing; this section is the correction, not a rewrite.

   RE-MEASURED 2026-10-10 AND STILL TRUE (so they are NOT corrected):
   - section 10 binary sha256 6CADE9A3C1D4623C6779EC4CCEA5C7CA67027FB1F2FF3AB55F3B8FA6E1A05296
     == _main/build/aireplay-capture.exe on disk today (783 865 B, mtime 2026-10-09T20:51:21Z).
   - gate-verdict-matrix.md INSTRUMENT OF RECORD line (run_battery.ps1 28 309 B, mtime
     2026-10-09T19:51:44.179Z, 436 lines) == the worktree file exactly; its LF blob in the
     parent is a84a90302398ec61813340bb7d00943f97c4cdb0 at 27 874 B / 435 LF, the gap being
     CRLF in the worktree under core.autocrlf, not drift.
   - the aggregate log is 14 036 B at its original UTC mtime; no new battery was run.
   Nothing in this correction re-opens any WGC number; the refusal is settled by
   AUDIT-FINDINGS F18 and the box must not be re-litigated by re-running the battery.
