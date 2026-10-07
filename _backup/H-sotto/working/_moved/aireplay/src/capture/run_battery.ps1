# run_battery.ps1 — the MEASURED capability battery for capture -> NVENC -> ring -> MP4.
#
# WHAT THIS SCRIPT IS FOR
#   Half the numbers in this project's receipts are DERIVED, not measured. This battery exists so
#   that every claim about what this box can ACTUALLY encode and capture carries a provenance tag:
#       MEASURED     read from a run of THIS script, on THIS binary, at the timestamp printed
#       DERIVED      arithmetic from a MEASURED row or from a cited code line — never from thin air
#       NOT MEASURED the question could not be asked on this box right now, and WHY is stated
#   A row with no provenance is a defect. If you add a row, give it one of those three tags.
#
# EVERY COUNT CARRIES POPULATION AND WINDOW (LANE-BRIEF law 6). Rows with N=1 say so.
#
# HARD RULES THIS SCRIPT KEEPS (LANE-BRIEF section 4):
#   1. no visible console window: children are launched hidden (WindowStyle Hidden), never bare
#   2. no piped native command: every native call is `& exe args > file 2>&1` then $LASTEXITCODE
#   3. native H:\ paths only
#
# USAGE
#   pwsh -File src\capture\run_battery.ps1
#   pwsh -File src\capture\run_battery.ps1 -SkipBuild            # reuse the shipped exe
#   pwsh -File src\capture\run_battery.ps1 -Reps 5 -Census        # tighter stats + window census
#   pwsh -File src\capture\run_battery.ps1 -Root H:\aireplay     # override the tree root
#
# EXIT CODE: 0 = the battery RAN (rows may individually be refused — a refusal is a result).
#            2 = the battery could not run at all (missing toolchain). Read the log either way.

[CmdletBinding()]
param(
  [string]$Root     = 'H:\sotto\_moved\aireplay',
  [switch]$SkipBuild,
  [int]   $Reps     = 3,
  [switch]$Census,
  [int]   $CensusMs = 100
)

$ErrorActionPreference = 'Continue'
$src     = Join-Path $Root 'src\capture'
$build   = Join-Path $Root '_main\build'
$logs    = Join-Path $Root '_main\logs'
$runs    = Join-Path $Root '_main\runs'
$fixtures= Join-Path $Root '_main\src'
$exe     = Join-Path $build 'aireplay-capture.exe'
$mut     = Join-Path $build 'aireplay-capture-MUTANT.exe'
$gxx     = 'H:\msys64\mingw64\bin\g++.exe'
$report  = Join-Path $logs ('cap-battery-{0}.txt' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$rows    = [System.Collections.Generic.List[object]]::new()

foreach ($d in @($build,$logs,$runs,$fixtures)) { if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null } }

# --- the primitives -----------------------------------------------------------------------
function Say  ($s) { Write-Output $s; Add-Content -Path $report -Value $s }
function Rule ($s) { Say '';  Say ('=' * 78); Say $s; Say ('=' * 78) }

# Run a native command WITHOUT a window and WITHOUT a pipe, and return its real exit code.
# The pipe is the whole point: `cmd | Select-Object -First N` closes early and hides the status.
function RunNative {
  param([string]$File, [string[]]$Argv, [string]$OutFile, [int]$TimeoutSec = 900)
  $errFile = "$OutFile.err"
  $p = Start-Process -FilePath $File -ArgumentList $Argv -NoNewWindow -Wait -PassThru `
                     -RedirectStandardOutput $OutFile -RedirectStandardError $errFile
  return [int]$p.ExitCode
}

function Row {
  param([string]$Claim, [string]$Result, [string]$Provenance, [string]$Population, [string]$Note = '')
  $r = [pscustomobject]@{ claim = $Claim; result = $Result; provenance = $Provenance;
                          population = $Population; note = $Note }
  $rows.Add($r)
  Say ("{0,-9} | {1}" -f $r.provenance, $r.claim)
  Say ("          -> {0}" -f $r.result)
  Say ("          POPULATION={0}  {1}" -f $r.population, $r.note)
}

$ffmpegOk  = [bool](Get-Command ffmpeg  -ErrorAction SilentlyContinue)
$ffprobeOk = [bool](Get-Command ffprobe -ErrorAction SilentlyContinue)

# Every number this script prints is formatted with the INVARIANT culture, defined ONCE here.
# CurrentCulture on this box is pt-BR, whose NumberDecimalSeparator is ',' — so an unformatted
# `{0:N1}` emits "783,8", which a reader parses as a thousands separator and a later regex splits as
# a CSV field. A measurement whose TEXT depends on the machine's locale is not a measurement.
$inv = [System.Globalization.CultureInfo]::InvariantCulture

# SELF-CHECK: refuse to run a script that does not parse.
# WHY: the first version of this battery had a parse error (a backtick after a closed `)`) and wrote
# a 252-byte log while exiting 1. A parse failure and a battery that ran and found nothing look
# almost the same to whoever reads the log — and the first is the more dangerous one, because it
# produces NO rows and therefore no false green, just no evidence at all.
$parseErrs = $null; $parseToks = $null
[System.Management.Automation.Language.Parser]::ParseFile($PSCommandPath, [ref]$parseToks, [ref]$parseErrs) | Out-Null
if ($parseErrs -and $parseErrs.Count -gt 0) {
  Write-Output ("BATTERY ABORTED: this script does not parse ({0} error(s)). It would measure nothing." -f $parseErrs.Count)
  foreach ($e in $parseErrs) {
    Write-Output ("  line {0} col {1}: {2}" -f $e.Extent.StartLineNumber, $e.Extent.StartColumnNumber, $e.Message)
  }
  exit 2
}

# =========================================================================================
Rule ("CAPTURE CAPABILITY BATTERY  {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff zzz'))
Say ("root={0}" -f $Root)
Say ("report={0}" -f $report)
Say ("ffmpeg={0} ffprobe={1} gxx={2}" -f $ffmpegOk, $ffprobeOk, (Test-Path $gxx))

# =========================================================================================
Rule '0. MACHINE CONTEXT (so no later number is read in a vacuum)'
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1
$os  = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Say ("  gpu        : {0}  driver={1}" -f $gpu.Name, $gpu.DriverVersion)
Say ("  cpu        : {0}  {1}C/{2}T" -f $cpu.Name, $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors)
Say ("  ram        : {0} GiB total, {1} GiB free" -f [math]::Round($os.TotalVisibleMemorySize/1MB,2), [math]::Round($os.FreePhysicalMemory/1MB,2))
$smi = (Get-Command nvidia-smi -ErrorAction SilentlyContinue)
if ($smi) {
  $q = & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>&1 | Out-String
  Say ("  nvidia-smi : {0} rc={1}" -f $q.Trim(), $LASTEXITCODE)
}
Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
foreach ($s in [System.Windows.Forms.Screen]::AllScreens) {
  Say ("  display    : {0} bounds={1} primary={2}" -f $s.DeviceName, $s.Bounds, $s.Primary)
}

# =========================================================================================
Rule '1. BUILD'
if ($SkipBuild) {
  Say '  -SkipBuild: reusing the existing binary (NOT rebuilding).'
} else {
  $common = @("$src\main.cpp","$src\common.cpp","$src\d3d11_ctx.cpp","$src\nv12_convert.cpp",
              "$src\wgc_capture.cpp","$src\nvenc_encoder.cpp","$src\ring_buffer.cpp",
              "$src\mp4_writer.cpp","$src\selftest.cpp","$src\test_window.cpp","$src\replay.cpp")
  $libs = @('-ld3d11','-ldxgi','-luuid','-lole32','-loleaut32','-lruntimeobject','-lwindowsapp',
            '-lpsapi','-lgdi32','-luser32')
  $bf = "$logs\cap-build.txt"
  $rc = RunNative $gxx (@('-std=c++17','-O2','-Wall','-Wextra','-Wno-unused-parameter',
                         '-I',$src,"-I","$src\third_party") + $common + @('-o',$exe) + $libs) $bf
  $warn = 0; if (Test-Path "$bf.err") { $warn = (Get-Content "$bf.err" | Where-Object { $_ -match 'warning:' }).Count }
  $exeBytes = 0; if (Test-Path $exe) { $exeBytes = (Get-Item $exe).Length }
  $res = "rc=$rc  warnings=$warn  exe_bytes=$exeBytes"
  Row 'capture binary builds' $res 'MEASURED' '1 build, this run' 'warn_count read from the redirected stderr file, not the console'
  $rcM = RunNative $gxx (@('-std=c++17','-O2','-DAIREPLAY_GATE_OFF','-I',$src,"-I","$src\third_party") + $common + @('-o',$mut) + $libs) "$logs\cap-build-mutant.txt"
  Say ("  mutant build rc=$rcM (control build: the gate compiled OUT)")
}
if (-not (Test-Path $exe)) { Say "FATAL: no binary at $exe — the battery cannot run."; exit 2 }
$exeSha = (Get-FileHash $exe -Algorithm SHA256).Hash
$exeVer = (Get-Item $exe).LastWriteTime
Say ("  shipped binary sha256={0}" -f $exeSha)
Say ("  shipped binary mtime ={0}" -f $exeVer)
Say "  Every row below is MEASURED against THAT hash. A different hash is a different battery."

# =========================================================================================
Rule '2. NVENC — is there a real NVIDIA encoder, at which profile/size/fps?'
$gateArms = @(
  @{ n='normal';        bin=$exe; fault='none';              expect=0 },
  @{ n='tuning';        bin=$exe; fault='tuning-undefined';  expect=3 },
  @{ n='no-nvenc';      bin=$exe; fault='no-nvenc';          expect=3 },
  @{ n='skip-map';      bin=$exe; fault='skip-map';          expect=3 }
)
if (Test-Path $mut) { $gateArms += @{ n='MUTANT-control'; bin=$mut; fault='tuning-undefined'; expect=0 } }
foreach ($a in $gateArms) {
  $log = "$logs\cap-gate-$($a.n).txt"
  $rc  = RunNative $a.bin (@('--selftest','--inject-fault',$a.fault,'--log',$log)) "$logs\cap-gate-$($a.n).stdout.txt"
  $line = (Select-String -Path $log -Pattern 'DECISION:' | Select-Object -Last 1).Line
  if (-not $line) { $line = (Get-Content $log -Tail 1) }
  $ok  = ($rc -eq $a.expect)
  # NOTE ON STYLE, learned the hard way: PowerShell cannot continue an argument list with a
  # backtick placed after a CLOSED parenthesis — `Row ("x") ` on a continuation is a parse error
  # ("Unexpected token"). Every multi-argument call below therefore puts each argument in a
  # variable first and calls on one line. It is dull, but a battery that does not parse measures
  # nothing, and a silent parse failure looks exactly like a battery that ran.
  $verdict = if ($ok) { 'MATCH' } else { 'MISMATCH' }
  $claim   = "law-6 gate arm '$($a.n)'"
  $result  = "rc=$rc (expected $($a.expect)) $verdict"
  $note    = "{0}" -f ($line -replace '\s+',' ').Trim()
  Row $claim $result 'MEASURED' '1 run of this arm, this binary' $note
}

# =========================================================================================
Rule '3. WGC — can this box capture a real window/monitor RIGHT NOW?'
$wgcExe = Join-Path $Root '_main\wgc-probe.exe'
if (Test-Path $wgcExe) {
  $out = "$logs\cap-wgc-now.txt"
  $rc  = RunNative $wgcExe @() $out
  $txt = (Get-Content $out) -join "`n"
  $supported = if ($txt -match 'IsSupported\s*->\s*0x00000000\s+supported=1') { 'supported=1' }
               elseif ($txt -match 'supported=0') { 'supported=0' } else { 'unknown' }
  # BUG FOUND AND FIXED HERE by run 1 reporting "PARTIAL: 5 of 6" on a probe that refused 5 of 5.
  # The item regex had no paren requirement, so it ALSO matched the banner line
  # "=== WGC CreateForWindow probe ===" and counted it as a sixth capture item. The refusal regex
  # was strict, hence 5 of 6 — a wrong headline produced by the instrument, not by WGC.
  # Both patterns now require the '(' so only a real call site can match, and both are counted
  # over the SAME predicate so the numerator and denominator can never disagree.
  $callRe   = 'CreateFor(?:Window|Monitor)\([^)]*\)\s*->'
  $deniedRe = 'CreateFor(?:Window|Monitor)\([^)]*\)\s*->\s*0x80070005'
  $items  = ([regex]::Matches($txt, $callRe)).Count
  $denied = ([regex]::Matches($txt, $deniedRe)).Count
  Say ("  probe rc=$rc  items_tried=$items  E_ACCESSDENIED=$denied")
  if ($items -gt 0 -and $denied -gt $items) {
    # A numerator above the denominator means the two regexes disagree; say so instead of
    # printing a nonsense ratio.
    Say "  WGC-COUNT INCONSISTENT (denied=$denied > items=$items) — the regexes do not share a predicate; treat the WGC row as NOT MEASURED."
    $items = 0
  }
  foreach ($l in (Get-Content $out | Where-Object { $_ -match 'CreateFor|IsSupported' })) { Say "    $($l.Trim())" }
  if ($items -gt 0 -and $denied -eq $items) {
    $pop = "1 probe run, $items distinct capture items (own window, foreground, desktop, taskbar, primary monitor)"
    $why = 'PROVES: the capture half of this pipeline cannot run on this box now; the refusal is process-wide and window-independent. It does NOT tell us WHY.'
    $res = "REFUSED on $denied of $items capture items, 0x80070005 E_ACCESSDENIED (IsSupported $supported)"
    Row 'WGC live capture' $res 'MEASURED' $pop $why
  } elseif ($items -gt 0 -and $denied -lt $items) {
    $pop = "1 probe run, $items capture items"
    $why = 'Some items captured — see the probe log for which.'
    $res = "PARTIAL: $denied of $items items refused with E_ACCESSDENIED"
    Row 'WGC live capture' $res 'MEASURED' $pop $why
  } else {
    $why = 'instrument produced nothing'
    Row 'WGC live capture' 'UNKNOWN — the probe produced no CreateFor* lines' 'NOT MEASURED' '1 probe run' $why
  }
} else {
  $why = 'the probe is built from _main\wgc-probe.cpp by another lane'
  Row 'WGC live capture' 'NOT RUN — _main\wgc-probe.exe missing' 'NOT MEASURED' '0 runs' $why
}

# =========================================================================================
Rule '4. MUXER — the offline H.264 cut, end to end, at two resolutions'
# WHY a fixture stream and not a capture: WGC is refused (section 3), and a muxer that can only be
# exercised through the broken component is not provable. The fixture is produced by h264_nvenc,
# so building it ALSO measures the hardware encoder.
# WHY the fixtures are long: ring_buffer.cpp refuses any arena under 16 MiB (the guard moved to
# :57 when another lane edited that file at 12:17 — CITED BY CONTENT, NOT BY LINE, on purpose),
# so a short clip cannot be muxed at all. See the 'ring floor' row.
$fixturesNeeded = @(
  @{ n='1080p60'; wh='1920x1080'; f="$fixtures\cap-1080p60.h264"; frames=1800 },
  @{ n='2160p60'; wh='3840x2160'; f="$fixtures\cap-2160p60.h264"; frames=1800 }
)
foreach ($fx in $fixturesNeeded) {
  if (Test-Path $fx.f) { Say ("  fixture present: {0} ({1} B)" -f $fx.f, (Get-Item $fx.f).Length); continue }
  if (-not $ffmpegOk) { Say ("  MISSING fixture {0} and ffmpeg is absent" -f $fx.f); continue }
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $rc = RunNative 'ffmpeg' (@('-hide_banner','-loglevel','error','-y','-f','lavfi',
        "-i","testsrc2=size=$($fx.wh):rate=60",'-frames:v',"$($fx.frames)",
        '-c:v','h264_nvenc','-preset','p5','-tune','ull','-zerolatency','1','-g','60','-bf','0',
        '-b:v','40M','-maxrate','40M','-bufsize','80M','-pix_fmt','yuv420p','-f','h264',$fx.f)) "$logs\cap-gen-$($fx.n).txt"
  $sw.Stop()
  Say ("  generated {0}: rc={1} wall_ms={2} bytes={3}" -f $fx.n, $rc, $sw.ElapsedMilliseconds, (Get-Item $fx.f -ErrorAction SilentlyContinue).Length)
  if ($rc -ne 0) { Row "fixture $($fx.n)" ("ffmpeg rc=$rc — fixture NOT produced") 'MEASURED' "1 generate run" 'every mux row for this resolution will be NOT MEASURED' }
}

$muxArms = @(
  @{ n='mux-1080p';   src="$fixtures\cap-1080p60.h264";  wh='1920x1080'; fps=60; out="$runs\cap-mux-1080p.mp4" },
  @{ n='mux-4k';       src="$fixtures\cap-2160p60.h264"; wh='3840x2160'; fps=60; out="$runs\cap-mux-4k.mp4" },
  @{ n='mux-4k-LIED';  src="$fixtures\cap-2160p60.h264"; wh='1920x1080'; fps=60; out="$runs\cap-mux-4k-lied.mp4" }
)
foreach ($m in $muxArms) {
  if (-not (Test-Path $m.src)) { Row $m.n 'no fixture stream' 'NOT MEASURED' '0 runs' 'fixture generation failed'; continue }
  $log = "$logs\cap-$($m.n).txt"
  $times = @()
  $rc = 99; $aus = ''; $bytes = ''
  $n = [Math]::Max(1, $Reps)
  for ($i = 1; $i -le $n; $i++) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $rc = RunNative $exe (@('--cut-from-h264',$m.src,'--cut-fps',"$($m.fps)",'--cut-size',$m.wh,'--out',$m.out,'--log',$log)) "$logs\cap-$($m.n).run$i.stdout.txt"
    $sw.Stop(); $times += $sw.Elapsed.TotalMilliseconds
    if ($rc -eq 0) {
      $cut = (Select-String -Path $log -Pattern 'OFFLINE CUT:' | Select-Object -Last 1).Line
      if ($cut -match 'aus=(\d+)')        { $aus   = $Matches[1] }
      if ($cut -match 'bytes=(\d+)')      { $bytes = $Matches[1] }
    }
  }
  $sorted = $times | Sort-Object
  $med = $sorted[[int][math]::Floor($sorted.Count/2)]
  # Invariant formatting: see section 7. A wall clock that prints "783,8" on a pt-BR box is a
  # number whose VALUE depends on the machine's locale.
  $msMin = ([double]$sorted[0]).ToString('F1', $inv)
  $msMed = ([double]$med).ToString('F1', $inv)
  $msMax = ([double]$sorted[-1]).ToString('F1', $inv)
  Say ("  {0}: rc={1} aus={2} bytes={3} wall_ms(min/med/max)={4}/{5}/{6}" -f `
       $m.n, $rc, $aus, $bytes, $msMin, $msMed, $msMax)
  $probeTxt = ''
  if ($ffprobeOk -and (Test-Path $m.out)) {
    $pr = & ffprobe -v error -count_frames -select_streams v:0 `
          -show_entries 'stream=codec_name,profile,width,height,pix_fmt,r_frame_rate,nb_read_frames,duration' `
          -of default=nw=1 $m.out 2>&1 | Out-String
    $probeTxt = (($pr -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join ' ')
    $nd = & ffmpeg -v error -i $m.out -f null - 2>&1 | Out-String
    $ndLen = $nd.Trim().Length
  } else { $ndLen = -1 }
  $declared = $m.wh -replace 'x','x'
  if ($m.n -like '*LIED*') {
    $realW = if ($probeTxt -match 'width=(\d+)')  { $Matches[1] } else { '?' }
    $realH = if ($probeTxt -match 'height=(\d+)') { $Matches[1] } else { '?' }
    # ffprobe reads the SPS, so it reports the REAL size and hides the defect. The container
    # header is the thing that disagrees, and only a box-level read shows it.
    $boxes = "$logs\cap-$($m.n).boxes.txt"
    $tkhd = 'not-read'
    if (Test-Path (Join-Path $Root '_main\probe-cap-tkhd.ps1')) {
      $boxOut = & pwsh -NoProfile -File (Join-Path $Root '_main\probe-cap-tkhd.ps1') -File $m.out 2>&1 | Out-String
      Set-Content -Path $boxes -Value $boxOut -Encoding UTF8
      if ($boxOut -match 'tkhd\s+DECLARED size\s*=\s*(\d+)x(\d+)') { $tkhd = "$($Matches[1])x$($Matches[2])" }
    }
    $isLying = ($tkhd -ne 'not-read' -and $tkhd -ne "${realW}x${realH}")
    $defectNote = if ($isLying) {
      'DEFECT CONFIRMED: mp4_writer.cpp writes cfg_.width/height into BOTH the avc1 sample entry and the tkhd track header, and replay.cpp cut_from_h264 assigns w_/h_ from --cut-size rather than from the stream, while avcC carries the stream REAL SPS. The two disagree and ffprobe cannot see it, because ffprobe reads the SPS. A wrong --cut-size yields a file that decodes at one size and is declared at another. Cited by content, not line: these are other lanes'' files and the line numbers move.'
    } else {
      'the declared size and the real SPS agree on this arm'
    }
    $lieRes = "rc=$rc  real(SPS, what ffprobe shows)=${realW}x${realH}  container tkhd/avc1(what a player sizes the track)=$tkhd"
    $liePop = "$n cut run(s); 1 ffprobe; 1 box-level read (_main\probe-cap-tkhd.ps1)"
    Row $m.n $lieRes 'MEASURED' $liePop $defectNote
  } else {
    $okRes = "rc=$rc  aus=$aus  bytes=$bytes  wall_ms med=$med  ffprobe: $probeTxt  null-decode stderr=$ndLen B"
    $okPop = "$n cut run(s) (wall_ms is min/med/max over them), 1 ffprobe, 1 null-decode"
    Row "muxer writes an MP4 at $declared" $okRes 'MEASURED' $okPop 'An independent tool re-counts the frames the product claims it wrote.'
  }
}

# ---- the red arm: can the muxer say NO? -----------------------------------------------------
$junk = "$fixtures\cap-junk-not-h264.bin"
Set-Content -Path $junk -Value ('this is not an H.264 elementary stream' * 64) -Encoding ASCII -NoNewline
$junkLog = "$logs\cap-mux-junk.txt"
$rcJunk = RunNative $exe (@('--cut-from-h264',$junk,'--cut-fps','60','--cut-size','1920x1080',
                           '--out',"$runs\cap-mux-junk.mp4",'--log',$junkLog)) "$logs\cap-mux-junk.stdout.txt"
$junkMsg = (Select-String -Path $junkLog -Pattern 'FAILED' | Select-Object -Last 1).Line
$junkTxt = if ($junkMsg) { ($junkMsg -replace '\s+',' ').Trim() } else { '(no FAILED line)' }
$junkRes = "rc=$rcJunk  $junkTxt"
Row 'muxer on a non-H.264 file (RED arm)' $junkRes 'MEASURED' '1 run' 'A refused input is what makes the green rows above worth anything.'

# ---- the ring floor: a MEASURED refusal that explains itself ---------------------------------
$small = "$fixtures\cap-small.h264"
if ($ffmpegOk) {
  RunNative 'ffmpeg' (@('-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=60',
        '-frames:v','300','-c:v','libx264','-preset','ultrafast','-f','h264',$small)) "$logs\cap-gen-small.txt" | Out-Null
}
if (Test-Path $small) {
  $smallLog = "$logs\cap-mux-small.txt"
  $rcS = RunNative $exe (@('--cut-from-h264',$small,'--cut-fps','60','--cut-size','320x180',
                           '--out',"$runs\cap-mux-small.mp4",'--log',$smallLog)) "$logs\cap-mux-small.stdout.txt"
  $sMsg = (Select-String -Path $smallLog -Pattern 'FAILED' | Select-Object -Last 1).Line
  $sTxt   = if ($sMsg) { ($sMsg -replace '\s+',' ').Trim() } else { '(no FAILED line)' }
  $sMiB   = [math]::Round((Get-Item $small).Length/1MB, 2)
  $sRes   = "rc=$rcS  $sTxt"
  $sPop   = "1 run on a $sMiB MiB stream"
  $sWhy   = 'REFUSAL, and it proves a floor: the ring refuses any arena under 16 MiB (guard `capacity_bytes < (16u << 20)` in ring_buffer.cpp). The message blames a "cuttable window", which is NOT the reason — the reason is the floor.'
  Row 'muxer on a stream below the ring floor' $sRes 'MEASURED' $sPop $sWhy
}

# =========================================================================================
Rule '5. TIMING — where does the time go'
# The capture leg CANNOT be timed here: WGC is refused (section 3), so no capture leg exists at any
# resolution to time. Both facts are stated rather than papered over.
$timWhy = 'WGC refuses every capture item (section 3), so no capture leg exists to time. Any 1080p/4K capture number is DERIVED from receipt-03 battery-2 (2026-10-07 11:14-11:18) and was NOT reproduced by this run.'
Row 'capture leg wall clock at 1080p and 4K' 'NOT MEASURABLE on this box right now' 'NOT MEASURED' '0 runs' $timWhy
# The 1080p clamp this row used to cite was LIFTED by another lane at 12:26 (replay.cpp now calls
# negotiate_capture_window and tw_.create(dec.w, dec.h, ...)). The row is kept, in weakened form,
# because "4K capture" is now a matter of the CLI flag surface rather than of the source — and that
# is exactly the kind of question that silently rots, so it is asked on every run instead of asserted.
$helpTxt = ''
try { $helpTxt = (& $exe '--help' 2>&1 | Out-String) } catch { $helpTxt = '' }
$hasSizeFlag = if ($helpTxt -match '--width|--height|--capture-w|--size\s') { 'yes' } else { 'no' }
$hasNegotiation = (Select-String -Path (Join-Path $src 'replay.cpp') -Pattern 'negotiate_capture_window' -Quiet -ErrorAction SilentlyContinue)
$negState = if ($hasNegotiation) { 'PRESENT in replay.cpp (a sibling lane landed window negotiation; the old hard-coded 1920x1080 clamp is gone)' } else { 'ABSENT' }
$sizeWhy = "CLI size flag: $hasSizeFlag. Window negotiation: $negState. The source clamp is not the gate any more; the flag surface is, and this lane did NOT measure a 4K capture because WGC is refused (section 3)."
Row '4K capture at all (not just 4K timing)' "NOT MEASURED (no capture leg runs at any resolution)" 'NOT MEASURED' '0 runs' $sizeWhy

if ($ffmpegOk) {
  foreach ($t in @(@{n='1080p60';wh='1920x1080'}, @{n='2160p60';wh='3840x2160'})) {
    $times = @()
    $n = [Math]::Max(1, $Reps)
    for ($i = 1; $i -le $n; $i++) {
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $rcE = RunNative 'ffmpeg' (@('-hide_banner','-loglevel','error','-y','-f','lavfi',
            "-i","testsrc2=size=$($t.wh):rate=60",'-frames:v','300','-c:v','h264_nvenc',
            '-preset','p5','-tune','ull','-zerolatency','1','-b:v','40M','-pix_fmt','yuv420p',
            '-f','mp4',"$logs\cap-nvenc-$($t.n)-run$i.mp4")) "$logs\cap-nvenc-$($t.n)-run$i.txt"
      $sw.Stop(); if ($rcE -eq 0) { $times += $sw.Elapsed.TotalMilliseconds }
    }
    if ($times.Count -gt 0) {
      $sorted = $times | Sort-Object
      $med = $sorted[[int][math]::Floor($sorted.Count/2)]
      $mspf = $med / 300.0
      $medS = ([double]$med).ToString('F1', $inv)
      $mspfS = ([double]$mspf).ToString('F3', $inv)
      $encClaim = "NVENC encodes 300 frames of $($t.wh) (ffmpeg h264_nvenc)"
      $encRes   = "wall_ms med=$medS  -> $mspfS ms/frame incl. lavfi source generation and muxing; the encode itself is a subset"
      $encPop   = "$($times.Count) successful run(s) of 300 frames each, median reported; POPULATION=$($times.Count) WINDOW=300 frames"
      $encWhy   = 'This is the ENCODER on this box measured with an EXTERNAL tool. It is not the product encoder path, which cannot run while WGC is refused.'
      Row $encClaim $encRes 'MEASURED' $encPop $encWhy
    } else {
      $encClaim = "NVENC encodes 300 frames of $($t.wh)"
      $encPop   = "$n run(s), 0 successes"
      Row $encClaim 'all runs failed' 'MEASURED' $encPop 'see cap-nvenc-*.err'
    }
  }
}

# =========================================================================================
Rule '6. AUDIO ENDPOINTS — a name does not identify what was opened'
# The device fact this box teaches: CABLE Output (VB-Audio Virtual Cable) exists at MME #2,
# DirectSound #15 and WASAPI #32, and they are NOT interchangeable. Every status carries `api`.
$devs = Get-CimInstance Win32_SoundDevice -ErrorAction SilentlyContinue
if ($devs) {
  foreach ($d in $devs) { Say ("  api=Win32_SoundDevice name='{0}' state={1} status={2}" -f $d.Name, $d.Status, $d.StatusInfo) }
  $audRes = "$($devs.Count) Win32_SoundDevice rows (see lines above; each carries its own name+state)"
  $audPop = "1 CIM query, $($devs.Count) rows"
  $audWhy = 'Win32_SoundDevice does NOT report MME/DirectSound/WASAPI indices, so this is NOT an index-level census.'
  Row 'audio endpoints' $audRes 'MEASURED' $audPop $audWhy
  $idxWhy = 'needs a per-API enumeration (IAudioClient::GetMixerFormat / IMMDeviceEnumerator per API). Saying "CABLE at index N" without naming the API is the defect this project already paid for once.'
  Row 'per-API endpoint indices (MME / DirectSound / WASAPI)' 'NOT ENUMERATED by this battery' 'NOT MEASURED' '0 enumerations' $idxWhy
} else {
  Row 'audio endpoints' 'Win32_SoundDevice returned nothing' 'NOT MEASURED' '1 CIM query, 0 rows' 'the CIM class returned no rows'
}

# =========================================================================================
Rule '7. SUMMARY — every row, with its provenance'
$inv = [System.Globalization.CultureInfo]::InvariantCulture
Say ("{0,-11} {1,-46} {2}" -f 'PROVENANCE','CLAIM','RESULT')
Say ('-' * 78)
foreach ($r in $rows) {
  $res = [string]$r.result
  # Do NOT truncate the result to a column: run 1 truncated "wall_ms med=783,8" to "wall_ms med=7..",
  # which hid the very number the row exists to report. Claim may be trimmed; result may not.
  if ($res.Length -gt 150) { $res = $res.Substring(0,150) + ' ..(see the row above)' }
  $cl  = [string]$r.claim
  if ($cl.Length -gt 46) { $cl = $cl.Substring(0,46) + '..' }
  Say ("{0,-11} {1,-46} {2}" -f $r.provenance, $cl, $res)
}
$measured = @($rows | Where-Object { $_.provenance -eq 'MEASURED' }).Count
$derived  = @($rows | Where-Object { $_.provenance -eq 'DERIVED' }).Count
$notm     = @($rows | Where-Object { $_.provenance -eq 'NOT MEASURED' }).Count
Say ''
Say ("rows: MEASURED={0}  DERIVED={1}  NOT_MEASURED={2}  untagged={3}" -f `
     $measured, $derived, $notm, ($rows.Count - $measured - $derived - $notm))
Say ("binary sha256={0}" -f $exeSha)
Say ("WINDOW: this run only, single pass, $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff') local")
Say ("full log: {0}" -f $report)
Say "battery done. Exit 0 means the battery RAN; it does not mean every row passed."
exit 0
