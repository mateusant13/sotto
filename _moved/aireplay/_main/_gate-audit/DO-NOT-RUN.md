# DO NOT RUN - the capture battery, all-gates, and the WGC probe, right now

AUDIT DATE: 2026-10-09. This file is the answer to "why not just run it again?".
Nothing below is a reason about style or caution in general. Every reason names the thing that
breaks, with the measurement that proves it breaks. Tags: MEASURED = I measured it this session;
READ = quoted from a file with file:line; UNVERIFIED = passed in as a rule, not measured by me.

## 0. THE ONE-LINE ANSWER

Do not run the battery, all-gates, or the WGC probe until the box is idle and the owner has a
window, because (a) a run overwrites 69 evidence files this audit is built on, (b) the capture
battery opens real NVENC encoder sessions while nothing on this box can currently tell you how
many are already held - MEASURED, nvidia-smi returns rc=255 right now - and (c) the tree is under
active edit by other lanes, so a verdict you get is stale the moment you get it.

## 1. WHAT A RE-RUN DESTROYS (MEASURED, this session)

The battery names its outputs with FIXED names, so a second run overwrites them in place.
Measured in H:\sotto\_moved\aireplay\_main\logs\ (cap-* files):

  cap-* files in that directory ..................... 73
  timestamped aggregates (cap-battery-<ts>.txt) ......  4   <- these SURVIVE, under new names
  fixed-name files OVERWRITTEN IN PLACE ............. 69   <- these are the evidence
  bytes overwritten in place ....................... 155848102 (148.6 MiB, all of it .mp4)
  plus, in _main\runs\: cap-mux-1080p.mp4 146621246, cap-mux-4k.mp4 149735942,
      cap-mux-4k-lied.mp4 149735942 - overwritten in place (446 MB of mp4)
  plus, in _main\src\: cap-small.h264 746792 and cap-junk-not-h264.bin 2432 regenerated.
      The two big fixtures (cap-1080p60.h264 146606044, cap-2160p60.h264 149720741) are NOT
      regenerated - the script skips them when present (READ, run_battery.ps1:235).

  The 69 include, by prefix (measured counts):
    cap-gate-{normal,tuning,no-nvenc,skip-map,MUTANT-control}  3 files each  = 15
    cap-build / cap-build-mutant                                   2 each     =  4
    cap-wgc-now                                                    2          =  2
    cap-mux-1080p / cap-mux-4k / cap-mux-4k-LIED                   7/7/8      = 22
    cap-mux-junk / cap-mux-small                                   3 each     =  6
    cap-gen-small                                                  2          =  2
    cap-nvenc-{1080p60,2160p60}-run{1,2,3}  (.mp4, .txt, .txt.err) 18         = 18

  CONSEQUENCE, in plain words: after a re-run, the report of record
  (_main/logs/cap-battery-20261009-175104.txt) still exists, but the per-arm logs it was built from
  no longer hold what they held when it was written, and gate-verdict-matrix.md /
  HONEST-BASELINE.md would be citing files that have since been replaced. The audit would have to
  be redone from scratch, not amended. (MEASURED: same fixed names in the script, :159-160, :178,
  :254-263, :328-342, :363-391; and on disk now.)

## 2. THE DEVICE SIDE (why it is not just an evidence problem)

  2a. A GREEN capture battery proves the box can encode. The gate arms open a real encoder
      session: MEASURED, _main/logs/cap-gate-normal.txt:15-16 reports
      "OK: H.264 initialised; engines=2 max=4096x4096; zero-copy input registered AND mapped"
      and rc=0. The external timing arm encodes 6 real streams: MEASURED,
      cap-nvenc-1080p60-run{1,2,3}.mp4 at 23560929 B each and cap-nvenc-2160p60-run{1,2,3}.mp4 at
      28376536 B each. So a re-run is a re-acquisition of encoder sessions, not a no-op.

  2b. The session cap. The audit brief states a 10-session NVENC cap with the 11th refused
      (status 21). Tag: UNVERIFIED by this audit - I did not measure it, and you should not take a
      number on faith from me any more than from a report. What IS measured is the thing that makes
      the cap dangerous right now:

  2c. THE BOX CANNOT TELL YOU ITS ENCODER STATE - MEASURED, this session:
        $ nvidia-smi --query-gpu=encoder.stats.sessionCount,memory.used,memory.total \
                     --format=csv,noheader
        rc=255   Failed to initialize NVML: Unknown Error
        $ nvidia-smi --list-gpus
        rc=255   Failed to initialize NVML: Unknown Error
      The battery's own run reported "nvidia-smi rc=0" at 17:51:04 -03:00 (READ, report :13). So the
      read-only instrument that would tell you whether the cap is already loaded was working four
      hours into the audit window and is NOT working now. Cause: UNKNOWN. Do not conclude anything
      about the GPU's health from it, and above all do not "test the NVENC path" to check whether
      NVML's failure is real. If you cannot see the encoder state, you cannot bound the blast
      radius of opening six more sessions.

  2d. The capture leg is refused on this box, so the risky part buys nothing: MEASURED,
      _main/logs/cap-wgc-now.txt:6-10, five distinct capture items refused 0x80070005
      E_ACCESSDENIED while GraphicsCaptureSession::IsSupported reports supported=1 (:4). A re-run
      cannot produce a capture measurement on this box today. The only new information a re-run
      could deliver about capture is whether the access refusal changed - and the read-only checks in
      section 5 are the cheaper way to learn the box state at all.

  2e. The STAGING / window rule: the battery's own -Census flag produced NO census rows
      (READ, AUDIT-FINDINGS.md:199-200), which means a run of this battery cannot prove that no
      visible console or probe window appeared on the owner's screen. The house rule is hard:
      "Never leave a visible console window on the owner's screen" (AGENTS.md), and a 60 s census
      that only proves presence is not an exception. Running an instrument whose own census
      mechanism was measured non-functional is a gamble on the owner's patience, not a
      measurement.

## 3. OTHER LANES (why "just run it in parallel" is the worst option)

  MEASURED, this session: H:\sotto\_moved\aireplay has 53 modified files, 287 deleted files and
  838 untracked entries in its index (READ, AUDIT-FINDINGS.md F6, re-confirmed by reading the tree).
  Five lanes are active per the dispatch brief. The 15 lane gates (_lane*-gate.ps1) are themselves
  moving: F-A and F-B in gate-verdict-matrix.md section 1 measure that _lane3-ringcap-gate.ps1 and
  _lane16-wake-gate.ps1 changed sizes AFTER the only aggregate that exists was recorded
  (_lane3: 20673 B at the aggregate -> 36787 B today; _lane16: 30116 B -> 69294 B today).
  Running anything now measures a file that another lane may be editing at the same instant.
  The rule that applies is the one this repo already learned the hard way: a run whose subject's
  sha256 changes mid-run is DIRTY - state it and repeat it, never present it as clean.
  Also MEASURED: free space on the box is H: 52.1 GiB / I: 144.3 GiB / G: 22.7 GiB / C: 32.7 GiB.
  G: - the volume AGENTS.md names as the one that "fills and kills lanes with ENOSPC" - is at
  22.7 GiB free while five lanes are running. A battery run writes ~446 MB to H:, so it is not the
  straw that breaks G:, but any lane that spills to G: today is one write away from ENOSPC.

## 4. THE DO-NOT-RUN LIST (exact)

  DO NOT RUN, in this order of badness:
   1. pwsh -NoProfile -File H:\sotto\_moved\aireplay\src\capture\run_battery.ps1
      -Root H:\sotto\_moved\aireplay -Reps 3 -Census   (any flags; the flags do not change the
      destruction in section 1, and -Reps is what multiplies the encoder sessions in 2a)
   2. any invocation of all-gates.ps1 / run-all-gates.cmd (the 15 lane gates - population and
      current sizes are in gate-verdict-matrix.md section 1; several are under active edit)
   3. H:\sotto\_moved\aireplay\_main\wgc-probe.exe (the only instrument that could produce a
      capture item, and the only one that overwrites cap-wgc-now.txt)
   4. any of the 15 _lane*-gate.ps1 scripts. If a single gate verdict is genuinely needed, ask that
      lane's owner to run it, and quote THEIR window, not this audit's.
   5. builds. If a build is ever needed here, it is ONLY
      H:\sotto\_moved\aireplay\src\capture\build.cmd with H:\msys64\mingw64\bin\g++.exe
      (READ, AGENTS.md: that tree's build.cmd:3,7 is the only statement of the host compiler;
      cl.exe and nvcc.exe are both absent from PATH on this host). anything else is untested.
   6. H:\sotto\_main\_audit-verify-all.cmd - a DIFFERENT repository from the one this audit
      covers. Do not run it to "check the gates": 29 steps, two int8 model loads, and per AGENTS.md
      its exit code IS the verdict (a run with three red steps once exited 0).
   7. git: never "git add -A" / "git add .", never commit without "-F <file>" and explicit paths,
      never push, never "git reset --hard" / "git stash -u" / "git checkout .".
      (The nested repo is 7 commits ahead of origin/main at 1b6f56e; pushing is out.)
   8. do not delete the junction H:\aireplay -> H:\sotto\_moved\aireplay.

## 5. WHAT IS SAFE INSTEAD (read-only; each one answers a question you actually have)

  All of these open NO device, write NO file into the audited tree, and can be run right now.

  a) "Is the baseline still the baseline?" re-hash the binary:
       pwsh -NoProfile -Command "(Get-FileHash -Algorithm SHA256
         'H:\sotto\_moved\aireplay\_main\build\aireplay-capture.exe').Hash"
     Expected, from report :146: 6CADE9A3C1D4623C6779EC4CCEA5C7CA67027FB1F2FF3AB55F3B8FA6E1A05296
     A different hash means every MEASURED row in HONEST-BASELINE.md is from a different binary.
     (MEASURED, both files still on disk: aireplay-capture.exe 783865 B, mutant 784377 B.)

  b) "Is the mux defect still there?" read the artifact you already have - do not regenerate it:
       ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height
         -of csv "H:\sotto\_moved\aireplay\_main\runs\cap-mux-4k-lied.mp4"
       ffprobe will say 3840x2160, because ffprobe reads the SPS - it CANNOT see the defect.
       The defect is in the container headers, so use the box reader:
       pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\probe-cap-tkhd.ps1
     MEASURED: that script is 125 lines with ZERO write operations (no Out-File / Set-Content /
     Add-Content / New-Item / Export-Csv / Remove-Item / Copy-Item / Move-Item) - it is safe to
     run read-only. Point it at the EXISTING cap-mux-4k-lied.mp4 (149735942 B), never at a
     regenerated file, or you have measured a different artifact.

  c) "Which gates have a current verdict?" census the gate files by size+mtime+sha256 - exactly
     what gate-verdict-matrix.md section 1 does. This is read-only and it is the whole answer:
     6 current, 2 stale, 7 UNKNOWN. No gate needs to run to know that.

  d) "Can the box encode at all?" ask the device, do not open a session:
       nvidia-smi --query-gpu=encoder.stats.sessionCount,memory.used,memory.total --format=csv,noheader
     MEASURED right now: rc=255 "Failed to initialize NVML: Unknown Error". If NVML comes back,
     that is new information about the box - record it; do not use it as licence to run the battery.

  e) "Is the toolchain still the measured one?" ffmpeg -version / ffprobe -version
     (the report's own row :7 says ffmpeg=True ffprobe=True gxx=True; the exact versions are the
     check that costs nothing).

  f) "Did anything on the box change that would un-refuse WGC?" there is NO read-only instrument
     for this. The WGC probe is the only one and it is on the do-not-run list. Answer honestly:
     UNKNOWN until someone runs it deliberately.

  g) A capture-leg number does not exist at ANY resolution on this box today, and no read-only
     command can create one. Do not write a capture row. NOT MEASURED is the honest cell.

## 6. IF SOMEONE STILL HAS TO RUN IT - the preconditions, in order

   1. The owner agrees to a window, and the lanes that hold the GPU / audio / the tree are
      quiesced (name them first; do not assume).
   2. NVML answers nvidia-smi again (2c), so the encoder state is visible before you add to it.
   3. Back up first - this is the one that people skip and it is the cheapest:
        Copy-Item _main\logs\cap-*.*  to a new timestamped directory  (73 files, ~148.6 MiB),
        plus _main\runs\ (446 MB) if regenerated artifacts matter.
      A re-run with the old logs preserved is a NEW data point. A re-run without them is a REPLACEMENT
      of the only baseline in existence - and the current data would be gone with no way to
      reconstruct it.
   4. Record the sha256 of the binary and of every gate script before and after
      (AGENTS.md rule: a subject whose sha256 changes mid-run makes the run DIRTY).
   5. Run ONE instrument at a time, sequentially. Never two gates in parallel - the session cap and
      the single audio owner make parallel runs produce refusals that look like failures.
   6. TMPDIR=I:\cc-tmp (G: is at 22.7 GiB free with five lanes running).
   7. Spawn nothing on the owner's screen: pythonw.exe / creationflags 0x08000000|0x00000008, and
      take your own window census at your own cadence, because the battery's -Census produced none.
   8. When it is done, treat the result as a SECOND battery, never as a correction of the first:
      the two windows differ, and quoting them as a series would be a lie the report itself
      forbids (report :147: "WINDOW: this run only, single pass").
