#Requires -Version 5.1
<#
  press-to-clip-probe.red.ps1 -- CONTROL ARM.  THIS COPY IS DELIBERATELY BROKEN.
  It is press-to-clip-probe.ps1 with ONE injected mutation (and the self-check that must catch
  it).  It MUST go RED and exit 1.  A control that stays green is a failing control.

  MUTATION A (baked in, -Mutation zero-t-cmd): the QPC stamp taken immediately before each cut
    command is replaced by the constant 0.0, so every delta is the raw stopwatch epoch --
    tens of thousands of ms -- instead of a latency.  Caught by the CONTROL-ARM SELF-CHECK,
    which must find a median above 1000 ms, print RED-MUTATION: zero-t-cmd and exit 1.
  MUTATION B (-Mutation close-on-first-sight): the completion test (top-level box walk, chain
    well formed, ends at file length, LAST box = moov) is replaced by "the file exists", so
    t_file_closed is stamped while the clip is still being written.  Caught because the size at
    that instant cannot equal the reply closed_bytes and the box walk never ends in moov.

  THIS FILE MEASURES THE CUT HALF ONLY, exactly like the file it was copied from.

  WHAT IT DOES
    Runs the REAL product binary (default: _main\build\aireplay-capture.exe) in its DEVICE-FREE
    arm --cut-session --cut-from-h264 <feed> --cut-dir <dir>, feeds it N cut commands on stdin at
    a fixed cadence, and stamps, per cut:
       t_cmd         QPC stamp taken immediately BEFORE the {"cmd":"cut"} line is written
       t_file_closed first poll at which the closed clip passes a top-level ISO-BMFF box walk
                     (well-formed chain, ends exactly at file length, LAST box = moov)
       delta         t_file_closed - t_cmd   (the headline number)
       t_reply       first stdout reply line for that cut (the child own receipt)
       size          file size at the declared close, cross-checked against the reply
    Then it prints ONE summary line: n, p50, p95, p99, min, max and the PERCENTILE METHOD.

  WHAT IT DOES NOT DO (do not quote it for anything else)
    * It does not press a hotkey and it does not measure keypress -> cut decision.  That half is
      UNKNOWN here: src/capture/main.cpp never constructs a Trigger (the only reference is the
      observer replay.hotkey() at main.cpp:627) and --hotkey defaults OFF (main.cpp:645-647).
    * It touches no capture device: no WGC, no NVENC session, no WASAPI tap.  Verified by reading
      arm_cut_session (main.cpp:1235-1324): zero NVENC / WGC / D3D11 / AudioTap references in it.
    * It does not measure a disk flush.  t_file_closed is the moment the finalised bytes are
      visible to another process through the OS file cache, not the moment a platter is written.

  RUN PRECONDITIONS (also in README.md; refusing is a FAILURE, never a silent skip)
    * No other lane gate may be running (NVENC max 10 sessions; exactly ONE WASAPI loopback owner).
      The probe refuses, printing the offending pid and command line, unless -NoPreflight.
    * Native H:\ paths only.  TMPDIR for the child is forced to I:\cc-tmp (G: fills).
    * No visible console window: the child is started with UseShellExecute=false and
      CreateNoWindow=true (CREATE_NO_WINDOW); it never allocates its own console.
    * The clip dir must resolve under I:\cc-tmp unless -ForceWorkDirAnywhere is given; the exe own
      default (H:\aireplay\_main\runs) is inside the protected tree and is ALWAYS overridden.

  EXIT CODES (the exit code IS the verdict)
    0  GREEN   -- n cuts finalised, box walk clean on every clip, reply/size consistency held,
                  poll cadence contract met.
    1  RED     -- at least one self-check failed (this is the code the control arm must return).
    2  FAIL    -- the measurement could not be taken, with the reason printed (refusal, timeout,
                  insufficient population, precondition violation).
    3  reserved for the control file; this file does not return it.
#>
[CmdletBinding()]
param(
    [string] $Exe = 'H:\sotto\_moved\aireplay\_main\build\aireplay-capture.exe',
    [string] $Feed = 'H:\sotto\_moved\aireplay\_main\src\cap-small.h264',
    [int]    $Fps = 60,
    [string] $Size = '1920x1080',
    [int]    $Cuts = 30,
    [int]    $CadenceMs = 150,
    [string] $WorkDir = 'I:\cc-tmp\p95-instrument\run',
    [int]    $MinPollHz = 200,
    [int]    $PollHz = 500,
    [int]    $CutTimeoutMs = 5000,
    [int]    $WarmupMs = 300,
    [double] $GoalP95Ms = 250.0,
    [string] $Mutation = 'zero-t-cmd',
    [int]    $FirstCutIndex = 0,
    [string] $ResultJsonl = '',
    [switch] $KeepClips,
    [switch] $ForceWorkDirAnywhere,
    [switch] $NoPreflight
)

$ErrorActionPreference = 'Stop'
$script:Failures = @()

# ----------------------------------------------------------------- clock + helpers
$script:Freq = [System.Diagnostics.Stopwatch]::Frequency
$script:T0   = [System.Diagnostics.Stopwatch]::GetTimestamp()

function Now-Ms {
    # QPC-anchored static read: safe from any thread, so the reader runspace and the poll loop
    # stamp on the SAME clock without sharing a Stopwatch instance.
    return (([System.Diagnostics.Stopwatch]::GetTimestamp() - $script:T0) * 1000.0 / $script:Freq)
}

function Say([string]$Text, [string]$Colour = '') {
    if ($Colour) { Write-Host $Text -ForegroundColor $Colour } else { Write-Host $Text }
}

function Note-Failure([string]$Text) {
    $script:Failures += $Text
    Say ('  FAILURE: ' + $Text) 'Red'
}

function F3($Value) {
    if ($null -eq $Value) { return '?' }
    return ('{0:N3}' -f [double]$Value)
}

function Get-Percentile {
    param([double[]]$Sorted, [double]$P)
    if ($null -eq $Sorted -or $Sorted.Count -eq 0) { return $null }
    $rank = [int][math]::Ceiling(($P / 100.0) * $Sorted.Count)
    if ($rank -lt 1) { $rank = 1 }
    if ($rank -gt $Sorted.Count) { $rank = $Sorted.Count }
    return $Sorted[$rank - 1]
}

function Test-Mp4Finalised {
    # ffprobe-free completion test.  A clip written by Mp4Writer is finalised iff its TOP-LEVEL box
    # chain is well formed, ends EXACTLY at the file length, and the last box is 'moov' -- which is
    # what Mp4Writer::close() appends after patching the mdat size (mp4_writer.cpp:95-111, :305-311).
    # While the clip is still being written the chain cannot satisfy this (unpatched mdat size, no
    # trailing moov), so this is a COMPLETION test, not a size-stability guess.
    # It is a box-chain walk, NOT a full ISO-BMFF or decode validation.
    param([string]$Path, [int]$MaxBoxes = 8192)
    $res = New-Object psobject
    $res | Add-Member NoteProperty ok $false
    $res | Add-Member NoteProperty boxes 0
    $res | Add-Member NoteProperty last ''
    $res | Add-Member NoteProperty reason ''
    $res | Add-Member NoteProperty size ([int64](-1))
    if (-not [System.IO.File]::Exists($Path)) { $res.reason = 'absent'; return $res }
    $fs = $null
    try {
        $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open,
                                     [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $len = $fs.Length
        $res.size = $len
        if ($len -lt 8) { $res.reason = 'len-lt-8'; return $res }
        $hdr = New-Object byte[] 16
        $pos = [int64]0; $n = 0; $last = ''
        while ($pos -lt $len) {
            if (($pos + 8) -gt $len) { $res.reason = 'truncated-header'; $res.boxes = $n; $res.last = $last; return $res }
            $fs.Position = $pos
            $got = $fs.Read($hdr, 0, 8)
            if ($got -ne 8) { $res.reason = 'short-read'; $res.boxes = $n; $res.last = $last; return $res }
            $sz = [int64](([int]$hdr[0] * 16777216) + ([int]$hdr[1] * 65536) + ([int]$hdr[2] * 256) + [int]$hdr[3])
            $typ = [System.Text.Encoding]::ASCII.GetString($hdr, 4, 4)
            if ($sz -eq 1) {
                $got = $fs.Read($hdr, 0, 8)
                if ($got -ne 8) { $res.reason = 'short-extended-size'; $res.boxes = $n; $res.last = $last; return $res }
                $hi = [int64](([int]$hdr[0] * 16777216) + ([int]$hdr[1] * 65536) + ([int]$hdr[2] * 256) + [int]$hdr[3])
                $lo = [int64](([int]$hdr[4] * 16777216) + ([int]$hdr[5] * 65536) + ([int]$hdr[6] * 256) + [int]$hdr[7])
                $sz = ($hi * 4294967296) + $lo
            }
            elseif ($sz -eq 0) { $sz = $len - $pos }
            if ($sz -lt 8 -or ($pos + $sz) -gt $len) {
                $res.reason = ('bad-box-size:' + $typ + ':' + $sz); $res.boxes = $n; $res.last = $last; return $res
            }
            $last = $typ; $pos += $sz; $n++
            if ($n -gt $MaxBoxes) { $res.reason = 'too-many-boxes'; $res.boxes = $n; $res.last = $last; return $res }
        }
        $res.boxes = $n; $res.last = $last
        if ($pos -ne $len) { $res.reason = 'trailing-bytes'; return $res }
        if ($last -eq 'moov') { $res.ok = $true; $res.reason = 'chain-ok-moov-last' }
        else { $res.reason = ('chain-ok-last-is-' + $last) }
        return $res
    }
    catch { $res.reason = ('open-failed: ' + $_.Exception.Message); return $res }
    finally { if ($fs) { $fs.Dispose() } }
}

function Get-IntField {
    param([string]$Line, [string]$Key)
    $m = [regex]::Match($Line, '"' + [regex]::Escape($Key) + '":(\d+)')
    if ($m.Success) { return [int64]$m.Groups[1].Value }
    return $null
}
function Get-BoolField {
    param([string]$Line, [string]$Key)
    $m = [regex]::Match($Line, '"' + [regex]::Escape($Key) + '":(true|false)')
    if ($m.Success) { return ($m.Groups[1].Value -eq 'true') }
    return $null
}
function Get-StrField {
    param([string]$Line, [string]$Key)
    $m = [regex]::Match($Line, '"' + [regex]::Escape($Key) + '":"([^"]*)"')
    if ($m.Success) { return $m.Groups[1].Value }
    return $null
}

function Test-DeviceOwners {
    # The process list MUST come from a .ps1 FILE via Get-CimInstance Win32_Process: measured on
    # this box, the inline -Command form returns EMPTY stdout and would silently report "nothing
    # is running".  An empty census is therefore reported as a failure, never as "all clear".
    param([int]$SelfPid, [int[]]$OwnPids)
    $pats = @(
        'aireplay-capture(\.exe)?.*--(run|selftest|audio-endpoint|monitor|window-top|window-alpha|inject-fault)',
        'clip-probe-live', 'lane3-ringcap-synth', 'aireplay-trigger',
        'sotto_worker\.py', 'sotto_webview\.py', 'inject-all-probe', 'listen-probe',
        'all-gates\.ps1', '_lane\d+-[A-Za-z0-9-]+\.ps1', '_audit-verify-all\.cmd',
        'ffmpeg\.exe'
    )
    $hits = @()
    $rows = @()
    try { $rows = @(Get-CimInstance Win32_Process -Property ProcessId, Name, CommandLine) } catch { }
    if ($rows.Count -eq 0) {
        return @('CENSUS-EMPTY: Get-CimInstance Win32_Process returned no rows -- the device-ownership preflight cannot be trusted on this run (use -NoPreflight only if you personally know the box is idle)')
    }
    foreach ($r in $rows) {
        $cl = $r.CommandLine
        if (-not $cl) { continue }
        if ($r.ProcessId -eq $SelfPid) { continue }
        $mine = $false
        foreach ($pp in $OwnPids) { if ($r.ProcessId -eq $pp) { $mine = $true } }
        if ($mine) { continue }
        foreach ($pat in $pats) {
            if ($cl -match $pat) { $hits += ('pid=' + $r.ProcessId + ' name=' + $r.Name + ' cmd=' + $cl); break }
        }
    }
    return $hits
}


# ----------------------------------------------------------------- header
Say ''
Say '================================================================================'
Say ' SOTTO / PRESS-TO-CLIP LATENCY INSTRUMENT -- CUT HALF ONLY'
Say ' press-to-clip-probe.red.ps1 -- CONTROL ARM -- DELIBERATELY BROKEN -- MUST GO RED'
Say '================================================================================'
Say ''
Say 'DECOMPOSITION (printed every run; read this before any number below)'
Say '  press-to-clip = [ A: keypress -> the cut decision is taken ]'
Say '                + [ B: cut command -> clip finalised on disk, next clip open ]'
Say '  A -- UNKNOWN / UNMEASURED.  This instrument presses no key.  main.cpp never constructs a'
Say '       Trigger (the only reference is the observer replay.hotkey() at main.cpp:627) and'
Say '       --hotkey defaults to off (main.cpp:645-647); trigger.cpp is on the build link line'
Say '       (build.cmd:23) but nothing in main.cpp arms it.  No number in this output may be'
Say '       quoted as press-to-clip latency.'
Say '  B -- MEASURED HERE.  t_cmd = QPC stamp taken immediately before the cut command line is'
Say '       written to the child stdin pipe.  t_file_closed = first poll at which cut-NNNN.mp4'
Say '       passes the top-level box walk (well-formed chain, ends exactly at file length, LAST'
Say '       box = moov) -- the moov Mp4Writer::close() appends (mp4_writer.cpp:305-311).'
Say '       t_reply is reported separately: it is the child own receipt line (WriteFile +'
Say '       FlushFileBuffers, main.cpp:815-823), observed at the pipe, not at the filesystem.'
Say '  NOT MEASURED EITHER: physical disk flush, encoder packet latency, the ring-buffer age of'
Say '       the first frame in the clip, and anything at all about the capture device.'
Say ''

Say ''
Say '################################################################################'
Say (' CONTROL ARM: this file is press-to-clip-probe.ps1 with the mutation ' + $Mutation)
Say ' injected on purpose.  Every number it prints is WRONG BY CONSTRUCTION and the run must'
Say ' end RED with exit 1.  If it ends GREEN the control has failed, not the instrument.'
Say '################################################################################'

# ----------------------------------------------------------------- preflight
$exePath = $Exe
if (-not [System.IO.File]::Exists($exePath)) {
    Say ('PRECONDITION FAILED: exe not found: ' + $exePath) 'Red'
    exit 2
}
if (-not [System.IO.File]::Exists($Feed)) {
    Say ('PRECONDITION FAILED: h264 feed not found: ' + $Feed) 'Red'
    exit 2
}

$workFull = [System.IO.Path]::GetFullPath($WorkDir)
if (($workFull -notlike 'I:\cc-tmp\*') -and ($workFull -ne 'I:\cc-tmp')) {
    if (-not $ForceWorkDirAnywhere) {
        Say  'PRECONDITION FAILED: -WorkDir must resolve under I:\cc-tmp (G: fills; the exe own' 'Red'
        Say ('  default H:\aireplay\_main\runs is inside the protected tree).  Got: ' + $workFull) 'Red'
        Say  '  Pass -ForceWorkDirAnywhere only if you have checked where the clips will land.' 'Red'
        exit 2
    }
}
$clipDir = Join-Path $workFull 'clips'
New-Item -ItemType Directory -Force -Path $clipDir | Out-Null
$resolvedClip = (Resolve-Path $clipDir).Path

if (($resolvedClip -like 'I:\cc-tmp\*') -or $ForceWorkDirAnywhere) {
    Get-ChildItem -Path $resolvedClip -Filter 'cut-*.mp4' -File -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
    }
    $stale = @(Get-ChildItem -Path $resolvedClip -File -ErrorAction SilentlyContinue)
    if ($stale.Count -gt 0) {
        Say ('PRECONDITION FAILED: clip dir is not empty after the sweep: ' + $resolvedClip) 'Red'
        foreach ($s in $stale) { Say ('  stale: ' + $s.Name + '  ' + $s.Length + ' B') 'Red' }
        Say  '  Refusing to measure into a dir holding files this run did not create.' 'Red'
        exit 2
    }
}
else {
    Say ('PRECONDITION FAILED: refusing to sweep ' + $resolvedClip + ' -- not under I:\cc-tmp') 'Red'
    exit 2
}

if (-not $NoPreflight) {
    Say 'PREFLIGHT: looking for other device owners (Get-CimInstance Win32_Process, from this FILE)...'
    $hits = @(Test-DeviceOwners -SelfPid $PID -OwnPids @())
    if ($hits.Count -gt 0) {
        Say 'PRECONDITION FAILED: another artifact that can own a device (or a lane gate) is running:' 'Red'
        foreach ($h in $hits) { Say ('  ' + $h) 'Red' }
        Say '  NVENC allows at most 10 sessions and there is exactly ONE WASAPI loopback owner,' 'Red'
        Say '  so two device gates must never be concurrent.  Wait, or pass -NoPreflight if you' 'Red'
        Say '  know the named row cannot hold a device.' 'Red'
        exit 2
    }
    Say 'PREFLIGHT: no other device owner found.'
}

$exeHash  = (Get-FileHash -Algorithm SHA256 -LiteralPath $exePath).Hash
$feedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Feed).Hash
$exeLen   = (Get-Item -LiteralPath $exePath).Length
$feedLen  = (Get-Item -LiteralPath $Feed).Length

# Fast Annex-B access-unit count, only for feeds small enough to read whole (documented limit).
$feedAus = -1
if ($feedLen -le 67108864) {
    $bytes = [System.IO.File]::ReadAllBytes($Feed)
    $bn = $bytes.Length
    $c = 0
    for ($i = 0; $i -lt $bn - 2; $i++) {
        if ($bytes[$i] -eq 0 -and $bytes[$i + 1] -eq 0 -and $bytes[$i + 2] -eq 1) { $c++; $i += 2 }
    }
    $feedAus = $c
}
$feedSeconds = -1.0
if ($feedAus -gt 0 -and $Fps -gt 0) { $feedSeconds = $feedAus / [double]$Fps }

Say ''
Say ('SUBJECT  exe   = ' + $exePath)
Say ('         size  = ' + $exeLen + ' B   sha256 = ' + $exeHash)
Say ('         feed  = ' + $Feed)
Say ('         size  = ' + $feedLen + ' B   sha256 = ' + $feedHash)
if ($feedAus -gt 0) {
    Say ('         feed holds ' + $feedAus + ' Annex-B access units = ' + ('{0:N2}' -f $feedSeconds) + ' s at the declared ' + $Fps + ' fps')
}
else {
    Say  '         feed AU count = UNKNOWN (feed larger than the 64 MiB fast-count limit)'
}
Say ('         clip dir = ' + $resolvedClip)
$needSeconds = ($Cuts * $CadenceMs) / 1000.0
Say ('PLAN     cuts = ' + $Cuts + ' at ' + $CadenceMs + ' ms cadence = ' + ('{0:N2}' -f $needSeconds) + ' s of feed, plus ' + $WarmupMs + ' ms warmup')
if ($feedSeconds -gt 0 -and $needSeconds -gt $feedSeconds) {
    Say ('PRECONDITION FAILED: the feed is shorter than the plan.  ' + ('{0:N2}' -f $needSeconds) + ' s of feed are needed but the file holds ' + ('{0:N2}' -f $feedSeconds) + ' s at ' + $Fps + ' fps.') 'Red'
    Say  '  Cut latency does not depend on fps, but the FEEDER runs out and the tail cuts close an' 'Red'
    Say  '  empty clip, which Mp4Writer refuses (mp4_writer.cpp:98).  Lower -CadenceMs or -Fps.' 'Red'
    exit 2
}

Say ''
Say 'POLL-MODE: a tight direct-file poll of the PREDICTED path (cut-%04d.mp4, index = cut ordinal;'
Say '  ClipSession::path_for, main.cpp:1030-1034) via FileStream open + top-level box walk.'
Say '  NOT FileSystemWatcher: FSW delivery is asynchronous and buffered (InternalBufferSize), so its'
Say '  notification latency would be ADDED to t_file_closed as unbounded jitter this instrument'
Say '  does not measure.  NOT Get-ChildItem: a directory listing enumerates every entry on every'
Say '  poll, so its cost grows with the number of clips kept; the closed path is deterministic, so'
Say '  one file is read.  Sampling error: every delta is quantised by the poll interval; the true'
Say '  latency lies in [delta, delta + 1/pollHz_achieved].'
Say ''

# ----------------------------------------------------------------- child
$childOut = Join-Path $workFull 'child-stdout.log'
if ($ResultJsonl) { $jsonl = $ResultJsonl } else { $jsonl = Join-Path $workFull 'cuts.jsonl' }
$env:TMPDIR = 'I:\cc-tmp'

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName               = $exePath
$psi.Arguments              = '--cut-session --cut-from-h264 "' + $Feed + '" --cut-dir "' + $resolvedClip + '" --cut-fps ' + $Fps + ' --cut-size ' + $Size + ' --log "' + (Join-Path $workFull 'exe.log') + '"'
$psi.UseShellExecute        = $false
$psi.CreateNoWindow         = $true
$psi.RedirectStandardInput  = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError  = $false
if ($psi.EnvironmentVariables.ContainsKey('TMPDIR')) { $psi.EnvironmentVariables['TMPDIR'] = 'I:\cc-tmp' }
else { $psi.EnvironmentVariables.Add('TMPDIR', 'I:\cc-tmp') }

Say ('COMMAND  ' + $exePath)
Say ('         ' + $psi.Arguments)
Say ''

$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
[void]$p.Start()

$q = New-Object 'System.Collections.Concurrent.ConcurrentQueue[object]'
$readerScript = {
    param($proc, $queue, $freq, $t0, $logPath)
    $w = $null
    try {
        $w = New-Object System.IO.StreamWriter($logPath, $false, [System.Text.Encoding]::ASCII)
        $w.AutoFlush = $true
    } catch { }
    $srv = $proc.StandardOutput
    while ($true) {
        $line = $null
        try { $line = $srv.ReadLine() } catch { break }
        if ($null -eq $line) { break }
        $now = [System.Diagnostics.Stopwatch]::GetTimestamp()
        $ms  = (($now - $t0) * 1000.0 / $freq)
        [void]$queue.Enqueue([pscustomobject]@{ t_ms = $ms; line = $line })
        if ($w) { try { $w.WriteLine($line) } catch { } }
    }
    if ($w) { try { $w.Dispose() } catch { } }
    [void]$queue.Enqueue([pscustomobject]@{ t_ms = -1.0; line = '__STDOUT_EOF__' })
}
$rs = [powershell]::Create()
[void]$rs.AddScript($readerScript).AddArgument($p).AddArgument($q).AddArgument($script:Freq).AddArgument($script:T0).AddArgument($childOut)
$async = $rs.BeginInvoke()

$replies   = New-Object 'System.Collections.ArrayList'   # reply lines, arrival order, with QPC stamps
$childTail = New-Object 'System.Collections.ArrayList'   # the child's non-JSON log lines
$records   = New-Object 'System.Collections.ArrayList'

function Drain-Queue {
    $item = $null
    while ($q.TryDequeue([ref]$item)) {
        if ($item.t_ms -lt 0) { return }
        if ($item.line.StartsWith('{')) { [void]$replies.Add([pscustomobject]@{ t_ms = $item.t_ms; line = $item.line }) }
        else {
            [void]$childTail.Add($item.line)
            if ($childTail.Count -gt 40) { $childTail.RemoveAt(0) }
        }
    }
}

# Warmup: let the feeder put access units into clip 0 before the first command, so cut #0 is not a
# measurement of an empty clip.
$warmEnd = (Now-Ms) + $WarmupMs
while ((Now-Ms) -lt $warmEnd) { Drain-Queue; [System.Threading.Thread]::Sleep(1) }

$pollIters = [int64]0
$pollMs    = 0.0
$interval  = 1000.0 / [double]$PollHz
$first     = $FirstCutIndex
$cadenceAnchor = Now-Ms

Say 'CUTS (ms on the QPC clock started before the child was launched; delta = t_closed - t_cmd)'
Say '  idx   t_cmd     t_closed    delta   t_reply    frames        bytes  box  reply'

$stop = $false
for ($k = 0; $k -lt $Cuts -and -not $stop; $k++) {
    if ($k -gt 0) {
        $nextAt = $cadenceAnchor + $CadenceMs
        while ((Now-Ms) -lt $nextAt) { Drain-Queue; [System.Threading.Thread]::Sleep(1) }
    }
    Drain-Queue

    try { $p.StandardInput.WriteLine('{"cmd":"cut"}'); $p.StandardInput.Flush() }
    catch { Note-Failure ('stdin write failed at cut ' + $k + ': ' + $_.Exception.Message); break }

    if ($Mutation -eq 'zero-t-cmd') { $cadenceAnchor = Now-Ms; $tCmd = 0.0 }
    else { $tCmd = Now-Ms; $cadenceAnchor = $tCmd }

    $expected  = Join-Path $resolvedClip ('cut-{0:D4}.mp4' -f ($first + $k))
    $deadline  = $tCmd + $CutTimeoutMs
    $tClosed   = -1.0
    $boxReason = ''
    $boxCount  = 0
    $boxLast   = ''
    $tSeen     = -1.0
    $nextPoll  = $tCmd

    while ($true) {
        Drain-Queue
        $now = Now-Ms
        if ($now -ge $deadline) { break }
        if ($now -ge $nextPoll) {
            $pollIters++
            $st = Test-Mp4Finalised -Path $expected
            if ($st.size -ge 0 -and $tSeen -lt 0) { $tSeen = $now }
            $nextPoll = Now-Ms + $interval
            if ($Mutation -eq 'close-on-first-sight') { if ($st.size -ge 0) { $tClosed = Now-Ms; $boxReason = 'MUTATION-first-sight'; $boxCount = $st.boxes; $boxLast = $st.last; break } }
            elseif ($st.ok) { $tClosed = Now-Ms; $boxReason = $st.reason; $boxCount = $st.boxes; $boxLast = $st.last; break }
            else { $boxReason = $st.reason; $boxCount = $st.boxes; $boxLast = $st.last }
        }
        if (($nextPoll - $now) -gt 1.2) { [System.Threading.Thread]::Sleep(1) } else { [System.Threading.Thread]::SpinWait(200) }
    }
    $pollMs += ((Now-Ms) - $tCmd)

    # the reply for THIS cut: the child writes one line per cut command, in order
    $tReply = -1.0
    $replyLine = ''
    $replyDeadline = Now-Ms + 2000.0
    while ((Now-Ms) -lt $replyDeadline) {
        Drain-Queue
        if ($replies.Count -gt 0) {
            $r = $replies[0]
            [void]$replies.RemoveAt(0)
            $tReply = $r.t_ms
            $replyLine = $r.line
            break
        }
        [System.Threading.Thread]::Sleep(1)
    }

    $sizeBytes    = $null
    $replyOk      = $null
    $closedBytes  = $null
    $closedFrames = $null
    $closedClip   = $null
    $sizeMatches  = $null
    $statusWord   = 'NO-REPLY'

    if ($tClosed -lt 0) {
        Note-Failure ('cut ' + $k + ' did not produce a finalised cut-' + ('{0:D4}' -f ($first + $k)) + '.mp4 within ' + $CutTimeoutMs + ' ms (last box-walk state: ' + $boxReason + ')')
    }
    else {
        $sizeBytes = [int64](Get-Item -LiteralPath $expected).Length
        if ($replyLine) {
            $replyOk      = Get-BoolField -Line $replyLine -Key 'ok'
            $closedBytes  = Get-IntField -Line $replyLine -Key 'closed_bytes'
            $closedFrames = Get-IntField -Line $replyLine -Key 'closed_frames'
            $closedClip   = Get-IntField -Line $replyLine -Key 'closed_clip'
            if ($null -ne $closedBytes) {
                $sizeMatches = ($closedBytes -eq $sizeBytes)
                if (-not $sizeMatches) {
                    Note-Failure ('cut ' + $k + ': file size at the declared close (' + $sizeBytes + ') does not match the reply closed_bytes (' + $closedBytes + ')')
                }
            }
            if ($null -ne $closedClip -and $closedClip -ne ($first + $k)) {
                Note-Failure ('cut ' + $k + ': reply closed_clip=' + $closedClip + ' but index ' + ($first + $k) + ' was expected')
            }
            if ($replyOk -eq $true) { $statusWord = 'ok' }
            elseif ($replyOk -eq $false) {
                $errText = Get-StrField -Line $replyLine -Key 'error'
                $statusWord = 'REFUSED'
                $why = ''
                if ($errText) { $why = ', error=' + $errText }
                Note-Failure ('cut ' + $k + ': the child did not finalise the clip (ok=false' + $why + ') -- stopping the run here')
                $stop = $true
            }
            else { $statusWord = 'NO-OK' }
        }
        else { Note-Failure ('cut ' + $k + ': no reply line arrived on the child stdout pipe within 2000 ms') }
    }

    $rec = [ordered]@{
        kind               = 'cut'
        index              = $k
        clip               = ($first + $k)
        path               = $expected
        t_cmd_ms           = [math]::Round($tCmd, 3)
        t_file_closed_ms   = $null
        delta_ms           = $null
        t_reply_ms         = $null
        reply_delta_ms     = $null
        t_first_seen_ms    = $null
        box_check          = $boxReason
        box_count          = $boxCount
        box_last           = $boxLast
        reply_ok           = $replyOk
        closed_clip        = $closedClip
        closed_frames      = $closedFrames
        closed_bytes       = $closedBytes
        size_bytes         = $sizeBytes
        size_matches_reply = $sizeMatches
        reply_line         = $replyLine
    }
    if ($tClosed -ge 0) { $rec.t_file_closed_ms = [math]::Round($tClosed, 3); $rec.delta_ms = [math]::Round($tClosed - $tCmd, 3) }
    if ($tReply  -ge 0) { $rec.t_reply_ms = [math]::Round($tReply, 3); $rec.reply_delta_ms = [math]::Round($tReply - $tCmd, 3) }
    if ($tSeen   -ge 0) { $rec.t_first_seen_ms = [math]::Round($tSeen, 3) }

    [void]$records.Add([pscustomobject]$rec)
    $framesDisp = '?'
    if ($null -ne $closedFrames) { $framesDisp = [string]$closedFrames }
    $bytesDisp = '?'
    if ($null -ne $sizeBytes) { $bytesDisp = [string]$sizeBytes }
    $cutLine = '  {0,3}  {1,8}  {2,8}  {3,7}  {4,8}  {5,6}  {6,12}  {7,3}  {8}' -f $k, (F3 $rec.t_cmd_ms), (F3 $rec.t_file_closed_ms), (F3 $rec.delta_ms), (F3 $rec.reply_delta_ms), $framesDisp, $bytesDisp, $boxCount, $statusWord
    Say $cutLine

    if (-not $KeepClips -and $tClosed -ge 0) {
        # keep the run light on I:; the size and the delta are already recorded above
        try { Remove-Item -LiteralPath $expected -Force -ErrorAction SilentlyContinue } catch { }
    }
}

# ----------------------------------------------------------------- teardown
try { $p.StandardInput.Close() } catch { }
if (-not $p.WaitForExit($CutTimeoutMs + 10000)) {
    Note-Failure 'the child did not exit after stdin EOF; killing it'
    try { $p.Kill() } catch { }
}
$exitChild = -1
try { $exitChild = $p.ExitCode } catch { }
try { [void]$rs.EndInvoke($async) } catch { }
Drain-Queue
if ($rs) { try { $rs.Dispose() } catch { } }


# ----------------------------------------------------------------- statistics
$deltas = @()
$replyDeltas = @()
foreach ($r in $records) { if ($null -ne $r.delta_ms) { $deltas += [double]$r.delta_ms } }
foreach ($r in $records) { if ($null -ne $r.reply_delta_ms) { $replyDeltas += [double]$r.reply_delta_ms } }
$sorted      = @($deltas | Sort-Object)
$sortedReply = @($replyDeltas | Sort-Object)

$hz = 0.0
if ($pollMs -gt 0) { $hz = $pollIters * 1000.0 / $pollMs }
$floorMs = 1000.0 / [math]::Max($hz, 1.0)

Say ''
Say 'CHILD-LOG-TAIL (the exe own words; the full stream is in child-stdout.log)'
foreach ($l in $childTail) { Say ('  | ' + $l) }
Say ('CHILD    exit code = ' + $exitChild)

if ($deltas.Count -eq 0) {
    Say ''
    Say 'VERDICT FAIL' 'Yellow'
    Say '  REASON: no cut produced a measurable delta -- nothing was finalised.  See the failures above.' 'Red'
    Say '  HALF A (keypress -> cut decision) remains UNKNOWN and nothing here speaks about it.' 'Red'
    exit 2
}

$n   = $deltas.Count
$p50 = Get-Percentile -Sorted $sorted -P 50
$p95 = Get-Percentile -Sorted $sorted -P 95
$p99 = Get-Percentile -Sorted $sorted -P 99
$mn  = $sorted[0]
$mx  = $sorted[$sorted.Count - 1]

# ---- CONTROL-ARM SELF-CHECK (present only in this deliberately broken copy) ----
$mutMed = Get-Percentile -Sorted $sorted -P 50
if ($Mutation -eq 'zero-t-cmd' -and $mutMed -gt 1000.0) {
    Say ''
    Say 'RED-MUTATION: zero-t-cmd' 'Red'
    Say  '  The stamp taken before the cut command was replaced by the constant 0.0, so every delta' 'Red'
    Say ('  is the raw stopwatch epoch, not a latency.  median = ' + (F3 $mutMed) + ' ms, which no' ) 'Red'
    Say  '  cut-side latency can be.  This copy is broken on purpose and must go RED.' 'Red'
    Say  '  ACTION: run press-to-clip-probe.ps1 (the unmutated file) for a real measurement.' 'Red'
    exit 1
}
$mutBadSizes = 0
foreach ($r in $records) { if ($null -ne $r.size_matches_reply -and $r.size_matches_reply -ne $true) { $mutBadSizes++ } }
if ($Mutation -eq 'close-on-first-sight' -and $mutBadSizes -gt 0) {
    Say ''
    Say 'RED-MUTATION: close-on-first-sight' 'Red'
    Say  '  The completion test was replaced by "the file exists", so t_file_closed is stamped while' 'Red'
    Say ('  the clip is still being written.  ' + $mutBadSizes + ' of ' + $records.Count + ' clips had a size that' ) 'Red'
    Say  '  disagreed with the reply closed_bytes and no box walk ended in moov.  Must go RED.' 'Red'
    exit 1
}
if ($Mutation -ne 'zero-t-cmd' -and $Mutation -ne 'close-on-first-sight') {
    Say ('CONTROL-ARM ERROR: unknown -Mutation ' + $Mutation + ' -- expected zero-t-cmd or close-on-first-sight') 'Red'
    exit 2
}

Say ''
Say ('POLL     iterations = ' + $pollIters + '  observed ms = ' + ('{0:N1}' -f $pollMs) + '  achieved = ' + ('{0:N1}' -f $hz) + ' Hz  (contract >= ' + $MinPollHz + ' Hz; target ' + $PollHz + ' Hz)')
Say ('         quantisation floor = ' + ('{0:N3}' -f $floorMs) + ' ms -- the true latency lies in [delta, delta + floor]')
Say ''
Say ('SUMMARY n=' + $n + ' p50=' + (F3 $p50) + 'ms p95=' + (F3 $p95) + 'ms p99=' + (F3 $p99) + 'ms min=' + (F3 $mn) + 'ms max=' + (F3 $mx) + 'ms unit=ms method=nearest-rank(rank=ceil(p/100*n),1-based,ascending-sorted) pollHz=' + ('{0:N1}' -f $hz) + ' floor=' + ('{0:N3}' -f $floorMs) + 'ms warmup=' + $WarmupMs + 'ms')

if ($sortedReply.Count -gt 0) {
    Say ('SUMMARY-REPLY (child-internal half of B; same method) n=' + $sortedReply.Count + ' p50=' + (F3 (Get-Percentile -Sorted $sortedReply -P 50)) + 'ms p95=' + (F3 (Get-Percentile -Sorted $sortedReply -P 95)) + 'ms p99=' + (F3 (Get-Percentile -Sorted $sortedReply -P 99)) + 'ms min=' + (F3 $sortedReply[0]) + 'ms max=' + (F3 $sortedReply[$sortedReply.Count - 1]) + 'ms')
}
else {
    Say 'SUMMARY-REPLY UNKNOWN -- no reply line was observed on the child stdout pipe'
}

# ----------------------------------------------------------------- contracts
$cleanBoxes = $true
foreach ($r in $records) { if ($r.box_check -ne 'chain-ok-moov-last') { $cleanBoxes = $false } }
if (-not $cleanBoxes) { Note-Failure 'at least one clip did not pass the moov-last box walk' }
if ($n -lt $Cuts) { Note-Failure ('ONLY ' + $n + ' EXECUTED CUTS (need ' + $Cuts + ')') }
if ($n -lt 30)    { Note-Failure 'population below 30 cuts -- a p95 from fewer than 30 samples is not a p95' }
foreach ($r in $records) {
    if ($null -ne $r.size_matches_reply -and $r.size_matches_reply -ne $true) { Note-Failure ('cut ' + $r.index + ': declared-close size and reply closed_bytes disagree') }
    if ($null -ne $r.reply_ok -and $r.reply_ok -ne $true) { Note-Failure ('cut ' + $r.index + ': reply ok=false') }
}
if ($hz -lt $MinPollHz) { Note-Failure ('poll cadence ' + ('{0:N1}' -f $hz) + ' Hz is below the ' + $MinPollHz + ' Hz contract') }
if ($GoalP95Ms -gt 0 -and $p95 -gt $GoalP95Ms) {
    Say ('GOAL     p95 ' + (F3 $p95) + ' ms EXCEEDS the owner-chosen goal ' + $GoalP95Ms + ' ms (goal is a target the owner picked, not a measurement)') 'Yellow'
}

$verdict = 'GREEN'
if ($script:Failures.Count -gt 0) { $verdict = 'RED' }
Say ''
if ($verdict -eq 'GREEN') { Say 'VERDICT GREEN' 'Green' } else { Say 'VERDICT RED' 'Red' }
$boxesWord = 'NO'
if ($cleanBoxes) { $boxesWord = 'yes' }
Say ('  cuts measured = ' + $n + ' of ' + $Cuts + ' requested; every clip passed the moov-last box walk: ' + $boxesWord)
Say  '  This is HALF B of press-to-clip (cut command -> finalised clip).  HALF A (keypress -> cut'
Say  '  decision) is UNKNOWN here and must never be added to these numbers.'

$summaryRec = [ordered]@{
    kind = 'summary'; n = $n; requested = $Cuts; verdict = $verdict
    p50_ms = $p50; p95_ms = $p95; p99_ms = $p99; min_ms = $mn; max_ms = $mx
    method = 'nearest-rank(rank=ceil(p/100*n),1-based,ascending-sorted)'
    poll_hz = [math]::Round($hz, 2); poll_iters = $pollIters; poll_floor_ms = [math]::Round($floorMs, 3)
    goal_p95_ms = $GoalP95Ms; child_exit = $exitChild; failures = $script:Failures
}
if ($sortedReply.Count -gt 0) {
    $summaryRec['reply_p50_ms'] = [math]::Round((Get-Percentile -Sorted $sortedReply -P 50), 3)
    $summaryRec['reply_p95_ms'] = [math]::Round((Get-Percentile -Sorted $sortedReply -P 95), 3)
}
else {
    $summaryRec['reply_p50_ms'] = $null
    $summaryRec['reply_p95_ms'] = $null
}
$runRec = [ordered]@{
    kind = 'run'; instrument = 'press-to-clip-probe.red.ps1'; instrument_scope = 'CUT HALF ONLY'; control_arm = $true; mutation = $Mutation
    utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    exe = $exePath; exe_bytes = $exeLen; exe_sha256 = $exeHash
    feed = $Feed; feed_bytes = $feedLen; feed_sha256 = $feedHash
    feed_aus = $feedAus; declared_fps = $Fps; declared_size = $Size
    cuts = $Cuts; cadence_ms = $CadenceMs; warmup_ms = $WarmupMs
    child_arguments = $psi.Arguments; clip_dir = $resolvedClip; child_stdout_log = $childOut
    tmpdir = 'I:\cc-tmp'
    half_a = 'UNKNOWN (keypress -> cut decision is not measured by this instrument)'
    half_b = 't_cmd -> clip finalised (box chain well formed, moov last, ends at file length)'
}
$jw = New-Object System.IO.StreamWriter($jsonl, $false, [System.Text.Encoding]::ASCII)
$jw.AutoFlush = $true
$jw.WriteLine(($runRec | ConvertTo-Json -Compress))
foreach ($r in $records) { $jw.WriteLine(($r | ConvertTo-Json -Compress)) }
$jw.WriteLine(($summaryRec | ConvertTo-Json -Compress))
$jw.Dispose()
Say ('WROTE    ' + $jsonl)
Say ('WROTE    ' + $childOut)
Say ''

if ($verdict -ne 'GREEN') { exit 1 }
exit 0
