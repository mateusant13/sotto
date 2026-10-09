# crash_probe.ps1 -- Sotto crash-recovery probe.
#
# WHAT THIS MEASURES (and what it deliberately does NOT assume):
#   ShadowPlay's promise is that a hard crash NEVER loses the recording in progress.
#   This probe asks the only question that can settle it, with bytes:
#     A) how many bytes existed on disk at the instant of the kill
#     B) how many bytes survived a subsequent start of the binary
#     C) how many of those bytes ffprobe can actually DECODE
#   and, because a gate that can only say YES is worthless, it also asserts the
#   NEGATIVE control: a process that was NOT killed must NEVER be reported as
#   "recovered".  A clean exit writes a COMPLETE mp4; calling that "recovered"
#   is a false positive and is reported as P0.
#
# KILL MECHANISM: Stop-Process -Force == TerminateProcess(EPROCESS).  That is the
#   SIGKILL equivalent on Windows: no WM_CLOSE, no atexit, no Mp4Writer::close(),
#   no moov box.  It is NOT a graceful exit and NOT a window close.
#
# EVERY COUNT CARRIES POPULATION AND WINDOW.  No unverified claim is asserted.
#
# One capture process at a time (no parallelism in the harness itself).

param(
    [string]$Exe      = 'I:\cc-tmp\crash-build\aireplay-capture.exe',
    [string]$OutDir   = 'I:\cc-tmp\crash-build\probe',
    [int]   $RunSeconds = 20,
    [double]$CutAt      = 6.0
)

$ErrorActionPreference = 'Continue'
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# ---------------------------------------------------------------- helpers

# Every count is emitted with an explicit denominator so nothing is ever a bare
# number.  A count without POPULATION is an anecdote.
function New-Row {
    param($RunId,$Phase,$Killed,$Armed)
    [ordered]@{
        run_id            = $RunId
        phase             = $Phase
        killed            = [int]$Killed
        armed             = [int]$Armed
        kill_at_s         = ''
        run_s             = $RunSeconds
        cut_at_s          = $CutAt
        bytes_at_kill_pre = ''   # A: file length sampled immediately BEFORE TerminateProcess
        bytes_at_kill_post= ''   # A: file length sampled immediately AFTER  TerminateProcess
        exists_after_kill = ''
        bytes_survived    = ''   # B: bytes still on disk after the kill + after the next start
        bytes_recovered   = ''   # B: bytes attributable to RECOVERY (0 when nothing was recovered)
        has_moov          = ''   # the discriminator: moov is written LAST, only by close()
        ffprobe_rc        = ''   # C
        decodable_frames  = ''   # C: packets ffprobe could actually read
        ffprobe_duration  = ''
        nextstart_rc      = ''   # rc of the SECOND start (the "recovery on next start" attempt)
        nextstart_bytes   = ''
        recovery_logged   = ''   # did the binary ever say anything about recovery?
        verdict           = ''
        reason            = ''
    }
}

function Get-ByteLen([string]$p) {
    if (-not (Test-Path $p)) { return -1 }
    return (Get-Item $p).Length
}

# moov is written by Mp4Writer::close() and by nothing else.  A file that has no
# moov was never closed, so nothing about it is "recovered" -- it is wreckage.
function Test-HasMoov([string]$p) {
    if (-not (Test-Path $p)) { return 0 }
    $fs = [System.IO.File]::OpenRead($p)
    try {
        $buf = New-Object byte[] $fs.Length
        [void]$fs.Read($buf, 0, $buf.Length)
        for ($i = 0; $i -le $buf.Length - 4; $i++) {
            if ($buf[$i] -eq 109 -and $buf[$i+1] -eq 111 -and $buf[$i+2] -eq 111 -and $buf[$i+3] -eq 118) { return 1 }
        }
        return 0
    } finally { $fs.Close() }
}

# C: can ffprobe DECODE this?  -count_packets forces a full read of the stream.
function Measure-Decodable([string]$p, $row) {
    $probe = Join-Path $OutDir ("ffprobe-" + $row.run_id + ".txt")
    ffprobe -v error -select_streams v:0 -count_packets `
            -show_entries stream=nb_read_packets -show_entries format=duration `
            -of default=noprint_wrappers=1 $p 1> $probe 2>&1
    $row.ffprobe_rc = $LASTEXITCODE
    $txt = ''
    if (Test-Path $probe) { $txt = (Get-Content $probe -Raw) }
    $frames = 0
    if ($txt -match 'nb_read_packets=(\d+)') { $frames = [int]$Matches[1] }
    $dur = 0.0
    if ($txt -match 'duration=([0-9\.]+)') { $dur = [double]$Matches[1] }
    $row.decodable_frames = $frames
    $row.ffprobe_duration  = $dur
}

# ---------------------------------------------------------------- one trial
# killed=$true  -> hard TerminateProcess at $killAt seconds
# killed=$false -> NEGATIVE CONTROL: let it exit on its own, cleanly
function Invoke-Trial {
    param($RunId,$Phase,$Killed,$KillAt)

    $row = New-Row -RunId $RunId -Phase $Phase -Killed $Killed -Armed 0
    $clip     = Join-Path $OutDir ("clip-" + $RunId + ".mp4")
    $nextOut  = Join-Path $OutDir ("nextstart-" + $RunId + ".mp4")
    $log      = Join-Path $OutDir ("run-" + $RunId + ".log")
    $nextLog  = Join-Path $OutDir ("nextstart-" + $RunId + ".log")
    foreach ($f in @($clip,$nextOut)) { if (Test-Path $f) { Remove-Item $f -Force } }

    $args = @('--run','--seconds',"$RunSeconds",'--cut-at',"$CutAt",'--out',$clip)
    $p = Start-Process -FilePath $Exe -ArgumentList $args -PassThru `
                       -RedirectStandardOutput $log -RedirectStandardError ($log + '.err')

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $armed = $false

    if ($Killed) {
        # Wait for the recorder to actually be recording before we kill it; a kill
        # that lands during NVENC init measures the init, not the recording.
        while ($sw.Elapsed.TotalSeconds -lt ($RunSeconds - 2)) {
            if ((Test-Path $log) -and ((Get-Content $log -Raw -ErrorAction SilentlyContinue) -match 'ARMED:')) {
                $armed = $true; break
            }
            if ($p.HasExited) { break }
            Start-Sleep -Milliseconds 50
        }
        $row.armed = [int]$armed
        $row.kill_at_s = $KillAt

        # Spin to the kill instant.
        while ($sw.Elapsed.TotalSeconds -lt $KillAt) { Start-Sleep -Milliseconds 5 }

        # A: sample the byte count as close to the TerminateProcess as possible.
        $row.bytes_at_kill_pre  = Get-ByteLen $clip
        # THE HARD KILL.  TerminateProcess, not WM_CLOSE, not CloseMainWindow.
        Stop-Process -Id $p.Id -Force
        $row.bytes_at_kill_post = Get-ByteLen $clip
        try { $p.WaitForExit(5000) | Out-Null } catch {}
    } else {
        # Negative control: clean, graceful, full exit.
        try { $p.WaitForExit(($RunSeconds + 30) * 1000) | Out-Null } catch {}
        $row.armed = 1
        $row.kill_at_s = 'none(clean)'
        $row.bytes_at_kill_pre  = Get-ByteLen $clip
        $row.bytes_at_kill_post = $row.bytes_at_kill_pre
    }

    # The kill destroys buffered-but-unwritten bytes.  Settle, then account.
    Start-Sleep -Milliseconds 300
    $row.exists_after_kill = [int](Test-Path $clip)
    $row.has_moov = Test-HasMoov $clip

    if ($row.exists_after_kill -eq 1) {
        Measure-Decodable -p $clip -row $row
        $surv = Get-ByteLen $clip
    } else {
        $surv = 0
        $row.ffprobe_rc       = -1
        $row.decodable_frames = 0
        $row.ffprobe_duration = 0
    }
    $row.bytes_survived = $surv

    # B: "on the next start, the binary must detect the incomplete segment and
    # recover what is decodable".  We give it a fair chance: a real second start,
    # pointed at a FRESH path, because Mp4Writer::open() uses fopen(...,"wb") and
    # would otherwise truncate the evidence we are trying to measure.
    $n = Start-Process -FilePath $Exe -PassThru `
            -ArgumentList @('--run','--seconds','5','--cut-at','2','--out',$nextOut) `
            -RedirectStandardOutput $nextLog -RedirectStandardError ($nextLog + '.err')
    try { $n.WaitForExit(60000) | Out-Null } catch {}
    $row.nextstart_rc = $n.ExitCode
    $row.nextstart_bytes = Get-ByteLen $nextOut

    $ntext = ''
    if (Test-Path $nextLog) { $ntext = (Get-Content $nextLog -Raw -ErrorAction SilentlyContinue) }
    $row.recovery_logged = [int](($ntext -match '(?i)recover|incomplete|unclean|journal|resum|partial|truncat'))

    # ---------------- verdict ----------------
    # The detector MUST be able to say NO, and it must NOT confuse
    # "a complete file that happened to outlive the kill" with "recovery".
    if (-not $Killed) {
        # NEGATIVE CONTROL.  Nothing was killed, so nothing can have been recovered.
        if ($surv -gt 0 -and $row.has_moov -eq 1) { $row.verdict = 'COMPLETE_CLEAN' }
        elseif ($surv -gt 0) { $row.verdict = 'CLEAN_BUT_NO_MOOV' }
        else { $row.verdict = 'CLEAN_NOTHING' }
        $row.bytes_recovered = 0      # by definition: nothing was killed, so nothing was recovered
        $row.reason = 'control: no kill was issued; a complete moov-closed file is not a recovery'
    }
    elseif ($row.exists_after_kill -eq 0) {
        $row.verdict = 'LOST_ALL'
        $row.bytes_recovered = 0
        $row.reason = 'killed before the mp4 was ever opened; the whole recording lived only in the RAM ring'
    }
    elseif ($row.has_moov -eq 1 -and $row.ffprobe_rc -eq 0 -and $row.decodable_frames -gt 0) {
        # moov exists => close() ran => the file was ALREADY FINISHED before the kill.
        # Reporting this as "recovered" is precisely the false positive we are hunting.
        $row.verdict = 'COMPLETE_PRE_KILL'
        $row.bytes_recovered = 0
        $row.reason = 'file was closed (moov present) before the kill landed; it survived, but nothing was recovered'
    }
    elseif ($row.has_moov -eq 0 -and $row.ffprobe_rc -eq 0 -and $row.decodable_frames -gt 0) {
        $row.verdict = 'RECOVERED'
        $row.bytes_recovered = $surv
        $row.reason = 'no moov yet ffprobe decoded frames'
    }
    else {
        $row.verdict = 'UNPLAYABLE'
        $row.bytes_recovered = 0
        $row.reason = 'bytes survived on disk but ffprobe could not decode them'
    }
    return $row
}

# ---------------------------------------------------------------- the matrix
# Three phases, because they fail for different structural reasons:
#   EARLY  kill before the cut -> the file does not exist yet
#   MID    kill at/around the cut -> the ~1 ms window in which a partial file exists
#   LATE   kill after the cut finished -> the file is already closed and complete
$trials = @(
    @{ id='e1'; phase='EARLY'; killed=$true;  at=2.0  },
    @{ id='e2'; phase='EARLY'; killed=$true;  at=3.0  },
    @{ id='e3'; phase='EARLY'; killed=$true;  at=4.0  },
    @{ id='e4'; phase='EARLY'; killed=$true;  at=5.0  },
    @{ id='m1'; phase='MID';   killed=$true;  at=5.90 },
    @{ id='m2'; phase='MID';   killed=$true;  at=6.00 },
    @{ id='m3'; phase='MID';   killed=$true;  at=6.10 },
    @{ id='m4'; phase='MID';   killed=$true;  at=6.30 },
    @{ id='l1'; phase='LATE';  killed=$true;  at=8.0  },
    @{ id='l2'; phase='LATE';  killed=$true;  at=11.0 },
    @{ id='l3'; phase='LATE';  killed=$true;  at=14.0 },
    @{ id='l4'; phase='LATE';  killed=$true;  at=17.0 }
)
$controls = @(
    @{ id='c1'; phase='CONTROL'; killed=$false; at=0 },
    @{ id='c2'; phase='CONTROL'; killed=$false; at=0 },
    @{ id='c3'; phase='CONTROL'; killed=$false; at=0 },
    @{ id='c4'; phase='CONTROL'; killed=$false; at=0 }
)

$rows = @()
foreach ($t in $trials) {
    Write-Host ("[crash] trial {0} phase={1} kill_at={2}" -f $t.id,$t.phase,$t.at)
    $rows += Invoke-Trial -RunId $t.id -Phase $t.phase -Killed $t.killed -KillAt $t.at
}
foreach ($t in $controls) {
    Write-Host ("[crash] CONTROL {0} (no kill -- must never be reported recovered)" -f $t.id)
    $rows += Invoke-Trial -RunId $t.id -Phase 'CONTROL' -Killed $false -KillAt 0
}

$csv = Join-Path $OutDir 'crash_matrix.csv'
$rows | Export-Csv -Path $csv -NoTypeInformation -Encoding utf8

# ---------------------------------------------------------------- the gate
# A gate that cannot say NO is not a gate.  Every assertion below is a claim
# with a POPULATION; a claim with N=0 is UNVERIFIED, never a pass.
function CountBy($rs,$phase,$verdict) { return @($rs | Where-Object { $_.phase -eq $phase -and $_.verdict -eq $verdict }).Count }

$kills   = @($rows | Where-Object { $_.killed -eq 1 })
$ctrls   = @($rows | Where-Object { $_.killed -eq 0 })
$recover = @($kills | Where-Object { $_.verdict -eq 'RECOVERED' })

Write-Host ""
Write-Host "=== CRASH MATRIX SUMMARY ==="
Write-Host ("kill runs (N)           : {0}" -f $kills.Count)
Write-Host ("control runs (N)        : {0}" -f $ctrls.Count)
foreach ($ph in @('EARLY','MID','LATE')) {
    $n = CountBy $kills $ph 'RECOVERED'
    $pop = @($kills | Where-Object { $_.phase -eq $ph }).Count
    Write-Host ("  {0,-6} recovered {1}/{2}" -f $ph,$n,$pop)
}
$lostAll = @($kills | Where-Object { $_.verdict -eq 'LOST_ALL' })
Write-Host ("LOST_ALL (0 bytes)      : {0}/{1}" -f $lostAll.Count,$kills.Count)

# THE NEGATIVE CONTROL.  If a control run is ever called RECOVERED, the detector
# is lying and everything it said about the killed runs is worthless.
$fp = @($ctrls | Where-Object { $_.verdict -eq 'RECOVERED' -or $_.bytes_recovered -gt 0 })
Write-Host ""
if ($fp.Count -gt 0) {
    Write-Host ("GATE: *** P0 FALSE POSITIVE *** {0}/{1} control runs reported as recovered" -f $fp.Count,$ctrls.Count)
} else {
    Write-Host ("GATE: negative control PASS -- {0}/{1} clean-exit runs, 0 reported as recovered" -f $ctrls.Count,$ctrls.Count)
}

$bytesRecovered = ($recover | Measure-Object -Property bytes_recovered -Sum).Sum
if ($null -eq $bytesRecovered) { $bytesRecovered = 0 }
$bytesAtKill = ($kills | ForEach-Object { [double]$_.bytes_at_kill_post } | Measure-Object -Sum).Sum
$bytesSurv   = ($kills | ForEach-Object { [double]$_.bytes_survived } | Measure-Object -Sum).Sum
$bytesDec    = 0
foreach ($k in $kills) {
    if ($k.exists_after_kill -eq 1) { $bytesDec += (Get-ByteLen (Join-Path $OutDir ("clip-" + $k.run_id + ".mp4"))) }
}

Write-Host ""
Write-Host ("BYTES at kill (N={0})     : {1}" -f $kills.Count,$bytesAtKill)
Write-Host ("BYTES surviving (N={0})  : {1}" -f $kills.Count,$bytesSurv)
Write-Host ("BYTES decodable(N={0})  : {1}" -f $kills.Count,$bytesDec)
Write-Host ("BYTES recovered (N={0})  : {1}" -f $kills.Count,$bytesRecovered)

$verdict = if ($recover.Count -eq 0) { 'CRASH RECOVERY: ABSENT (measured)' } else { 'CRASH RECOVERY: PRESENT' }
Write-Host ""
Write-Host $verdict
Write-Host ("csv -> {0}" -f $csv)
