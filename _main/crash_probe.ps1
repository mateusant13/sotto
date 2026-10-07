# crash_probe.ps1 — does a HARD kill lose the recording in progress?
#
# THE CLAIM UNDER TEST (ShadowPlay): "a hard kill NEVER loses the recording in progress".
#
# This probe runs the real capture binary and SIGKILLs it (TerminateProcess, exit code
# 0xC000013A) at three different phases, then reports three numbers per run:
#     1. bytes_at_kill        bytes of the output MP4 on disk at the moment of the kill
#     2. bytes_after_restart  bytes surviving after a restart-recovery attempt
#     3. bytes_decodable      bytes ffprobe can actually decode (sum of video packet sizes)
#
# THE GATE CAN SAY NO.  A run is only ever classified RECOVERED if it was PROVEN killed.
# Two INDEPENDENT proofs of a hard kill are required, because either alone could lie:
#     P1  exit code == 0xC000013A (STATUS_CONTROL_C_EXIT, set by TerminateProcess).
#         The application itself only ever returns 0, 2 or 3 (main.cpp), so it can NEVER
#         produce this value on its own. This alone proves external termination.
#     P2  the run log contains no "EXIT=" line. main.cpp writes "EXIT=%d" as the LAST
#         statement of main, and log_line() fflushes every line, so a graceful exit always
#         leaves "EXIT=" on disk. A hard kill cannot.
# If EITHER proof fails the run is classified NOT-KILLED and is NEVER reported as recovered.
# A NOT-KILLED run that happens to leave a good file is a FALSE POSITIVE and is counted
# as a P0 defect of this gate, loudly, with its evidence.
#
# Negative controls run with --no-kill: the process is left to exit on its own. The gate
# must classify every one of them NOT-KILLED. If the gate reports a control as recovered,
# the gate is broken and that is reported as a P0.
#
# Measurements are strictly serial (never more than one capture process alive at a time).
# Exit codes are captured by redirection and read from $LASTEXITCODE; nothing is ever piped
# through Select-Object -First N, which masks the real code.

param(
    [string]   $Exe      = 'H:\sotto-wt\crash4\_main\build\crash4-capture.exe',
    [string]   $WorkDir  = 'I:\cc-tmp\crash4',
    [string]   $Report   = 'H:\sotto-wt\crash4\_main\crash4-results.json',
    [int]      $RunSeconds = 20,
    [double]   $CutAt     = 10.0,
    [string]   $Ffp = 'C:\Users\Administrador\AppData\Local\Microsoft\WinGet\Links\ffprobe.exe',
    [string]   $Ffm = 'C:\Users\Administrador\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Exe)) { throw "probe: exe not found: $Exe" }

# ------------------------------------------------------------------ hard kill (kernel32)
# Stop-Process -Force and Process.Kill() both land on TerminateProcess, but going straight
# to the syscall with an explicit exit code removes any doubt about what "hard" means here.
$null = Add-Type -Namespace CrashProbe -Name Kern -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true)]
public static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInherit, uint dwPid);
[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool TerminateProcess(IntPtr hProcess, uint uExitCode);
[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool CloseHandle(IntPtr hObject);
'@

$PROCESS_TERMINATE          = 0x0001
$PROCESS_QUERY_LIMITED_INFO = 0x1000
$KILL_EXITCODE             = 0xC000013A   # STATUS_CONTROL_C_EXIT

function Invoke-HardKill([int]$ProcId) {
    # Returns $true only if TerminateProcess() itself succeeded on a live handle.
    $h = [CrashProbe.Kern]::OpenProcess(
            ($PROCESS_TERMINATE -bor $PROCESS_QUERY_LIMITED_INFO), $false, [uint32]$ProcId)
    if ($h -eq [IntPtr]::Zero) { return $false }
    try {
        return [CrashProbe.Kern]::TerminateProcess($h, [uint32]$KILL_EXITCODE)
    } finally {
        $null = [CrashProbe.Kern]::CloseHandle($h)
    }
}

function Get-Bytes([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return [int64]0 }
    if (-not (Test-Path -LiteralPath $Path)) { return [int64]0 }
    try { return [int64](Get-Item -LiteralPath $Path).Length } catch { return [int64]0 }
}

# ffprobe: how many bytes of this file can a decoder ACTUALLY read?
# -count_packets forces a real demux; a truncated file with no moov yields zero packets.
function Measure-Decodable([string]$File) {
    $res = [ordered]@{ packets = 0; decodableBytes = [int64]0; rc = -1; err = '' }
    if ((Get-Bytes $File) -le 0) { $res.err = 'no file'; return $res }
    $tmpErr = Join-Path $WorkDir 'ffprobe.err'
    $sizes = & $Ffp -v error -select_streams v:0 -show_entries packet=size -of csv=p=0 $File 2> $tmpErr
    $res.rc = $LASTEXITCODE
    if (Test-Path -LiteralPath $tmpErr) {
        $e = (Get-Content -LiteralPath $tmpErr -Raw)
        if ($e) { $res.err = $e.Trim() }
    }
    foreach ($s in $sizes) {
        $t = ($s -as [string]).Trim()
        if ($t -match '^\d+$') {
            $res.packets += 1
            $res.decodableBytes += [int64]$t
        }
    }
    return $res
}

# Stronger than packet counting: actually run the decoder over the whole file.
function Measure-FullDecode([string]$File) {
    $res = [ordered]@{ ok = $false; rc = -1; err = '' }
    if ((Get-Bytes $File) -le 0) { $res.err = 'no file'; return $res }
    $tmpErr = Join-Path $WorkDir 'ffmpeg.err'
    $null = & $Ffm -v error -i $File -f null NUL 2> $tmpErr
    $res.rc = $LASTEXITCODE
    if (Test-Path -LiteralPath $tmpErr) {
        $e = (Get-Content -LiteralPath $tmpErr -Raw)
        if ($e) { $res.err = $e.Trim() }
    }
    $res.ok = ($res.rc -eq 0)
    return $res
}

function Read-ExitCode($Proc) {
    try { $Proc.Refresh(); return [int64]$Proc.ExitCode } catch { return [int64]-999 }
}

# ------------------------------------------------------------------ one run
function Invoke-Run {
    param(
        [string] $Label,
        [double] $KillAt,        # seconds after process start; -1 = do not kill (control)
        [int]    $Index
    )

    $mp4   = Join-Path $WorkDir ("{0}-{1:d2}.mp4"  -f $Label, $Index)
    $log   = Join-Path $WorkDir ("{0}-{1:d2}.log"  -f $Label, $Index)
    $recov = Join-Path $WorkDir ("{0}-{1:d2}-recovery.mp4" -f $Label, $Index)
    foreach ($f in @($mp4, $log, $recov)) { if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force } }

    $so = Join-Path $WorkDir ("{0}-{1:d2}.out" -f $Label, $Index)
    $se = Join-Path $WorkDir ("{0}-{1:d2}.err" -f $Label, $Index)

    $args = @('--run', '--seconds', "$RunSeconds", '--cut-at', "$CutAt",
              '--out', $mp4, '--log', $log)

    $r = [ordered]@{
        label = $Label; index = $Index; phase = $Label
        killAt_s            = $KillAt
        pid                 = 0
        aliveBeforeKill     = $false
        killIssued          = $false
        killIssuedAt_s      = 0.0
        exitCode            = [int64]-999
        logHasExitMarker    = $false
        proofP1_exitcode    = $false
        proofP2_noExitLine  = $false
        KILLED              = $false
        lastLogLine         = ''
        bytes_pre_kill      = [int64]0
        bytes_at_kill       = [int64]0
        bytes_after_restart = [int64]0
        bytes_decodable     = [int64]0
        packets_decodable   = 0
        ffprobe_rc          = -1
        ffprobe_err         = ''
        full_decode_ok      = $false
        full_decode_rc      = -1
        full_decode_err     = ''
        recovery_artifacts  = ''
        recovery_bytes      = [int64]0
        VERDICT             = ''
    }

    $sw  = [System.Diagnostics.Stopwatch]::StartNew()
    $proc = Start-Process -FilePath $Exe -ArgumentList $args -PassThru -NoNewWindow `
                          -RedirectStandardOutput $so -RedirectStandardError $se
    $r.pid = $proc.Id

    # wait for the capture to actually ARM before starting the phase clock, so the phase
    # offsets mean the same thing on every run (NVENC init is ~1-2 s of jitter otherwise)
    $armed = $false
    while ($sw.Elapsed.TotalSeconds -lt 25) {
        Start-Sleep -Milliseconds 100
        if (Test-Path -LiteralPath $log) {
            $t = (Get-Content -LiteralPath $log -Raw)
            if ($t -and $t -match 'ARMED:') { $armed = $true; break }
            if ($t -and $t -match 'LAW 6 REFUSAL') { break }
        }
        if ($proc.HasExited) { break }
    }
    $tArm = $sw.Elapsed.TotalSeconds
    $r['armSeconds'] = [math]::Round($tArm, 3)

    if (-not $armed) {
        $r.VERDICT = 'NOT-KILLED (never armed: no recording existed to lose)'
        $r.KILLED = $false
        $sw.Stop()
        $results.Add($r)
        return
    }

    # ---- phase clock starts at ARM
    $target = $tArm + $KillAt
    while ($sw.Elapsed.TotalSeconds -lt $target) {
        Start-Sleep -Milliseconds 5
        $proc.Refresh()
        if ($proc.HasExited) { break }
    }

    $r.bytes_pre_kill = Get-Bytes $mp4

    if ($KillAt -lt 0) {
        # ---- NEGATIVE CONTROL: no kill. Let it finish on its own.
        $null = $proc.WaitForExit(60000)
        $r.exitCode = Read-ExitCode $proc
        $sw.Stop()
        $r.killIssued = $false
        if (Test-Path -LiteralPath $log) {
            $t = (Get-Content -LiteralPath $log -Raw)
            $r.logHasExitMarker = [bool]($t -match '(?m)^EXIT=')
            $lines = ($t -split "`r?`n") | Where-Object { $_ -ne '' }
            if ($lines) { $r.lastLogLine = $lines[-1] }
        }
        $r.proofP1_exitcode   = ($r.exitCode -eq $KILL_EXITCODE)
        $r.proofP2_noExitLine = (-not $r.logHasExitMarker)
        $r.KILLED = ($r.proofP1_exitcode -and $r.proofP2_noExitLine)
        $r.bytes_at_kill = Get-Bytes $mp4
        $d = Measure-Decodable $mp4
        $r.packets_decodable = $d.packets; $r.bytes_decodable = $d.decodableBytes
        $r.ffprobe_rc = $d.rc; $r.ffprobe_err = $d.err
        $f = Measure-FullDecode $mp4
        $r.full_decode_ok = $f.ok; $r.full_decode_rc = $f.rc; $r.full_decode_err = $f.err
        # A control that leaves a perfectly good file is exactly the false-positive shape.
        $r.VERDICT = if (-not $r.KILLED -and ($r.bytes_decodable -gt 0)) {
            'NOT-KILLED (control) — file present is NOT recovery'
        } else { 'NOT-KILLED (control)' }
        $results.Add($r)
        return
    }

    # ---- HARD KILL
    $proc.Refresh()
    $r.aliveBeforeKill = (-not $proc.HasExited)
    $r.killIssued      = Invoke-HardKill -ProcId $proc.Id
    $r.killIssuedAt_s  = [math]::Round($sw.Elapsed.TotalSeconds - $tArm, 3)
    $null = $proc.WaitForExit(15000)
    $r.exitCode = Read-ExitCode $proc
    $sw.Stop()

    # number 1: bytes on disk at the moment of the kill (process is dead; size is frozen)
    $r.bytes_at_kill = Get-Bytes $mp4

    if (Test-Path -LiteralPath $log) {
        $t = (Get-Content -LiteralPath $log -Raw)
        $r.logHasExitMarker = [bool]($t -match '(?m)^EXIT=')
        $lines = ($t -split "`r?`n") | Where-Object { $_ -ne '' }
        if ($lines) { $r.lastLogLine = $lines[-1] }
    }
    $r.proofP1_exitcode   = ($r.exitCode -eq $KILL_EXITCODE)
    $r.proofP2_noExitLine = (-not $r.logHasExitMarker)
    $r.KILLED = ($r.aliveBeforeKill -and $r.killIssued -and $r.proofP1_exitcode -and $r.proofP2_noExitLine)

    # ---- number 2: restart-recovery. A FRESH process, which knows nothing of the dead run.
    if (Test-Path -LiteralPath $mp4) {
        $before = (Get-Item -LiteralPath $mp4).LastWriteTimeUtc
        $null = (Get-Item -LiteralPath $mp4).LastWriteTimeUtc
    }
    $rsw = [System.Diagnostics.Stopwatch]::StartNew()
    $rso = Join-Path $WorkDir ("{0}-{1:d2}-rec.out" -f $Label, $Index)
    $rse = Join-Path $WorkDir ("{0}-{1:d2}-rec.err" -f $Label, $Index)
    $rlog = Join-Path $WorkDir ("{0}-{1:d2}-rec.log" -f $Label, $Index)
    $rargs = @('--run', '--seconds', '3', '--cut-at', '2', '--out', $recov, '--log', $rlog)
    $rproc = Start-Process -FilePath $Exe -ArgumentList $rargs -PassThru -NoNewWindow `
                           -RedirectStandardOutput $rso -RedirectStandardError $rse
    $null = $rproc.WaitForExit(60000)
    $rrecExit = Read-ExitCode $rproc
    $rsw.Stop()

    $r.bytes_after_restart = Get-Bytes $mp4
    $r.recovery_bytes      = Get-Bytes $recov
    # did the restart invent any artefact other than its own fresh clip?
    $extra = @(Get-ChildItem -LiteralPath $WorkDir -Filter ("{0}-{1:d2}*recovery*" -f $Label, $Index) -ErrorAction SilentlyContinue)
    $r.recovery_artifacts = (($extra | ForEach-Object { $_.Name }) -join ';')

    # ---- number 3: bytes actually decodable by ffprobe, on what survived
    $d = Measure-Decodable $mp4
    $r.packets_decodable = $d.packets; $r.bytes_decodable = $d.decodableBytes
    $r.ffprobe_rc = $d.rc; $r.ffprobe_err = $d.err
    $f = Measure-FullDecode $mp4
    $r.full_decode_ok = $f.ok; $r.full_decode_rc = $f.rc; $r.full_decode_err = $f.err

    $r['restartExitCode'] = $rrecExit
    $r.VERDICT = if (-not $r.KILLED) {
        'NOT-KILLED — GATE SAID NO (not counted as recovered)'
    } elseif ($r.bytes_decodable -gt 0 -and $r.full_decode_ok) {
        'KILLED — bytes on disk survived and decode'
    } elseif ($r.bytes_at_kill -gt 0) {
        'KILLED — bytes on disk but NOT decodable (no moov / truncated)'
    } else {
        'KILLED — ZERO bytes on disk; the recording in progress is gone'
    }
    $results.Add($r)
}

# ------------------------------------------------------------------ main
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$results = New-Object System.Collections.ArrayList

$phases = @(
    @{ name = 'early'; offsets = @(3.0, 3.0, 2.8, 3.2) },
    @{ name = 'mid';   offsets = @(10.00, 10.05, 10.15, 10.30) },
    @{ name = 'late';  offsets = @(16.0, 16.5, 17.0, 16.2) }
)

$i = 0
foreach ($p in $phases) {
    foreach ($off in $p.offsets) {
        $i++
        Write-Host ("[{0}/{1}] phase={2} killAt={3}s" -f $i, 12, $p.name, $off)
        Invoke-Run -Label $p.name -KillAt $off -Index $i
    }
}

# ---- negative controls: NOT killed. POPULATION = 3.
for ($c = 1; $c -le 3; $c++) {
    Write-Host ("[control/{0}] no kill" -f $c)
    Invoke-Run -Label 'control' -KillAt -1 -Index $c
}

# ------------------------------------------------------------------ report
$kills = @($results | Where-Object { $_.phase -ne 'control' })
$ctrl  = @($results | Where-Object { $_.phase -eq 'control' })

$out = [ordered]@{
    generatedUtc  = (Get-Date).ToUniversalTime().ToString('o')
    exe           = $Exe
    runSeconds    = $RunSeconds
    cutAt         = $CutAt
    populationKilled = $kills.Count
    populationControls = $ctrl.Count
    results       = $results
}
$out | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Report -Encoding utf8

Write-Host ""
Write-Host "=== PHASE TABLE (serial, one capture process alive at a time) ==="
foreach ($p in $phases) {
    $rows = @($results | Where-Object { $_.phase -eq $p.name })
    $killed = @($rows | Where-Object { $_.KILLED }).Count
    Write-Host ("--- phase {0}: POPULATION={1} killed={2} ---" -f $p.name, $rows.Count, $killed)
    foreach ($r in $rows) {
        Write-Host ("  {0,-9} killAt={1,6}s killRc=0x{2:X} atKill={3,8}B afterRestart={4,8}B decodable={5,8}B packets={6,4} fullDecode={7}" -f `
            $r.label, $r.killAt_s, [uint32]$r.exitCode, $r.bytes_at_kill, $r.bytes_after_restart,
            $r.bytes_decodable, $r.packets_decodable, $r.full_decode_ok)
    }
}
Write-Host ""
Write-Host "=== NEGATIVE CONTROL (no kill issued) ==="
foreach ($r in $ctrl) {
    Write-Host ("  control-{0} killIssued={1} KILLED={2} exitCode={3} exitMarker={4} decodable={5}B" -f `
        $r.index, $r.killIssued, $r.KILLED, $r.exitCode, $r.logHasExitMarker, $r.bytes_decodable)
}
$ctrlMisreported = @($ctrl | Where-Object { $_.KILLED }).Count
Write-Host ("  FALSE POSITIVES (control classified as killed/recovered): {0}" -f $ctrlMisreported)
Write-Host ""
Write-Host ("report: {0}" -f $Report)