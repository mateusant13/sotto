# SO REPLAY HEARTBEAT - the CORRECTED driver.
#
# ============================================================================
# WHAT WAS WRONG, and why this file was rewritten rather than patched.
#
# v1 used:  mcode exec --cwd <root> --file prompt
# That does NOT wake the agent. It SPAWNS A NEW HEADLESS SESSION that runs an
# agent nobody sees. MEASURED cost: 28 sessions created since 11:00 today, two of
# them 1 second apart (11:49:38 / 11:49:39) - a 3-minute cadence creating a fresh
# invisible session ~480 times a day, flooding the owner's session list with
# nothing to show for it.
#
# So "dispara" and "trabalha" were TRUE and "manda-te mensagem" was FALSE - not a
# tuning problem, the WRONG MECHANISM. Two different mechanisms; only one was wired.
#
# THE RIGHT MECHANISM is the one the runtime itself named. When an exec is refused
# with "Session already has an active Turn", the error says: "Use queue send to
# deliver the message after it." `queue send` is not a CLI subcommand - it is a row
# in local_runtime_queue_items. MEASURED by reading a real queued item: it carries
# a userMessageId and message.content, i.e. it IS a user message, delivered when the
# current turn ends. "Like a user" - which is exactly what the owner asked for.
#
# v2 enqueues into that table with wake.py. It does NOT touch the owner's session,
# does NOT spawn sessions, and does NOT restart anything.
# ============================================================================

$ErrorActionPreference = 'Continue'
$root      = 'H:\sotto\_moved\aireplay'
$mainDir   = Join-Path $root '_main'
$lockFile  = Join-Path $mainDir 'heartbeat.lock'
$logFile   = Join-Path $mainDir 'heartbeat.log'
$wakePy    = Join-Path $mainDir 'wake.py'
$promptMd  = Join-Path $mainDir 'continue-prompt.md'

# The session to wake. The owner can change this one line; it is the ONLY thing
# that decides whose session gets the message.
$TARGET_SESSION = 'mvs_a00662bff55242cb9b56c0f1165bdad7'

function Log($msg) {
    Add-Content -Path $logFile `
        -Value ("[{0}] {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $msg) -Encoding UTF8
}

# --- lock: an EXCLUSIVE handle. The old mkdir mutex did NOT exclude anything on
# Windows (it succeeds against an existing directory); this one does. Proved by
# _hb-lock-selftest.ps1, rc=0, ARM-D being the control. ---
$lock = $null
try {
    $lock = [System.IO.File]::Open($lockFile,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None)
} catch {
    Log 'SKIP - a previous wake is still pending'
    exit 0
}

Log ('WAKE queued -> session ' + $TARGET_SESSION)
try {
    if (-not (Test-Path $wakePy)) { Log ('MISSING ' + $wakePy); exit 0 }

    # Never stack duplicates. If a message is already waiting, this fire is a no-op
    # rather than a second queued turn.
    $pending = & python $wakePy $TARGET_SESSION
    if ($pending -match ':\s*([1-9]\d*)\s*$') {
        Log ('ALREADY PENDING (' + $Matches[1] + ') - not stacking a second wake')
        exit 0
    }

    $out = & python $wakePy $TARGET_SESSION $promptMd 2>&1
    Log ('enqueue -> ' + ($out -join ' ').Trim())
}
catch {
    Log ('ERROR: ' + $_.Exception.Message)
}
finally {
    if ($lock) { $lock.Close(); $lock.Dispose() }
}
