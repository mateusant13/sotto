# SO REPLAY HEARTBEAT - fires every 3 minutes, one pass at a time, forever.
#
# WHY A FILE AND NOT THE RUNTIME CRON: the runtime cron store
# (local_runtime_v2_cron_definitions) is real and row d43fb9be is armed, but the
# scheduler hydrates from the store only at PROCESS START, so a row written while
# mcode is already running never fires. MEASURED 2026-10-07: that row's
# next_run_at_ms was 2026-10-06T11:00:32 while the clock read 2026-10-07 11:22 —
# a day stale, i.e. NOT ticking in a running process. This driver does not depend
# on the runtime scheduler at all.
#
# THE LOCK IS THE POINT. Two overlapping passes double-dispatch and race the same
# files.
#
# MEASURED CORRECTION 2026-10-07: my first mutex used `New-Item -ItemType
# Directory` on an existing path and PASSED the acquire every time - the
# both-colour selftest ARM-A went RED (second acquire NOT blocked). On Windows a
# directory that already exists is not an exclusive create, so that lock could
# never have prevented an overlap. The working mutex is an EXCLUSIVE FileStream:
# the OS holds it open for as long as the process lives, and a second process
# cannot take it. If this pass is killed, the handle dies with it and the next
# fire acquires cleanly - no stale-lock sweep is needed at all.

$ErrorActionPreference = 'Continue'
$root = 'H:\sotto\_moved\aireplay'
$mainDir = Join-Path $root '_main'
$lockFile = Join-Path $mainDir 'heartbeat.lock'
$logFile = Join-Path $mainDir 'heartbeat.log'
$promptFile = Join-Path $mainDir 'continue-prompt.md'

function Log($msg) {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $logFile -Value ("[{0}] {1}" -f $ts, $msg) -Encoding UTF8
}

# --- acquire the lock: an EXCLUSIVE handle, held open for the whole pass ---
$lock = $null
try {
    $lock = [System.IO.File]::Open(
        $lockFile,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None)
}
catch {
    # IOException == another pass holds it. Exit quietly; that is not an error.
    Log 'LOCK-BUSY - a pass is already running, exit'
    exit 0
}

Log 'LOCK acquired (exclusive handle) - pass starting'
try {
    # Keep the previous pass's transcript; -o makes the result measurable on disk.
    $out = Join-Path $mainDir ("heartbeat-run-{0}.md" -f (Get-Date).ToString('yyyyMMdd-HHmmss'))

    # MEASURED FIX 2026-10-07, two defects found by watching a real fire fail:
    #
    #  1. rc=2 "A prompt, --input -, or at least one --file is required." I passed
    #     flags but no prompt text. The prompt now travels with --file.
    #  2. rc=4 "Session already has an active Turn." Targeting the OWNER's live
    #     session can never work - he is talking in it. MEASURED, not assumed.
    #     So the heartbeat gets its OWN session in this workspace and leaves the
    #     owner's session alone. Never target a session with a live Turn.
    $mcodeCmd = 'H:\env\npm-global\mcode.cmd'
    if (-not (Test-Path $mcodeCmd)) { Log ("MISSING launcher: " + $mcodeCmd); exit 0 }

    $p = Start-Process -FilePath $mcodeCmd `
        -ArgumentList @('exec', '--cwd', $root, '--file', $promptFile, '-o', $out) `
        -WorkingDirectory $root -NoNewWindow -PassThru `
        -RedirectStandardOutput "$out.stdout" -RedirectStandardError "$out.stderr"

    $finished = $p.WaitForExit(15 * 60 * 1000)
    if (-not $finished) {
        Log 'PASS TIMEOUT at 15 min - stopping this pass only'
        try { $p.Kill() } catch {}
        Log 'PASS timeout - killed'
        exit 0
    }
    Log ("PASS done rc={0} -> {1}" -f $p.ExitCode, $out)
}
catch {
    Log ("PASS ERROR: " + $_.Exception.Message)
}
finally {
    # Release by closing the handle. The OS drops it even if this process is
    # killed, so there is no stale lock to sweep.
    if ($lock) { $lock.Close(); $lock.Dispose() }
    Log 'LOCK released'
}
