# BOTH-COLOUR TEST of the heartbeat mutex (exclusive FileStream, FileShare::None).
#
# An instrument that cannot say NO is worthless, so this ships the pass AND a
# deliberately-broken control that must go RED.
#
# SEMANTICS (kept deliberately dumb so a boolean can never be misread):
#   $excluded = $true  means "the second acquire was REFUSED"  -> that is GOOD.
# Unique temp names per run, so a previous run can never contaminate this one.

$ErrorActionPreference = 'Continue'
$stamp = [System.IO.File]::WriteAllText
$id = [Guid]::NewGuid().ToString('N').Substring(0, 8)
$tmpDir = 'H:\sotto\_moved\aireplay\_main'
$testLock = Join-Path $tmpDir ("_hb-test-{0}.lock" -f $id)
$freeLock = Join-Path $tmpDir ("_hb-free-{0}.lock" -f $id)
$fails = 0

function Open-Exclusive($path) {
    # returns $null on success, the exception on refusal
    try {
        $h = [System.IO.File]::Open($path, [System.IO.FileMode]::OpenOrCreate,
              [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        return $h
    } catch { return $null }
}

# ---- ARM-0: first acquire on a free path MUST succeed ----
$h0 = Open-Exclusive $testLock
$arm0 = ($null -ne $h0)
Write-Output ("ARM-0 first-acquire-succeeds = {0}   [expect True]" -f $arm0)
if (-not $arm0) { $fails++ }

# ---- ARM-A: second acquire while held MUST be REFUSED (this is the overlap guard) ----
$hA = Open-Exclusive $testLock
$excludedA = ($null -eq $hA)          # TRUE == blocked == good
Write-Output ("ARM-A second-acquire-EXCLUDED = {0}   [expect True = two passes cannot overlap]" -f $excludedA)
if (-not $excludedA) { $fails++ }
if ($hA) { $hA.Close(); $hA.Dispose() }

# ---- ARM-B: after release the lock MUST be re-acquirable (no permanent deadlock) ----
if ($h0) { $h0.Close(); $h0.Dispose() }
$hB = Open-Exclusive $testLock
$armB = ($null -ne $hB)
Write-Output ("ARM-B reacquire-after-release = {0}   [expect True = no deadlock]" -f $armB)
if (-not $armB) { $fails++ }
if ($hB) { $hB.Close(); $hB.Dispose() }

# ---- ARM-C: NEGATIVE CONTROL - a path that was never locked MUST open cleanly.
# If this control cannot succeed, every other "excluded=True" is meaningless. ----
$hC = Open-Exclusive $freeLock
$armC = ($null -ne $hC)
Write-Output ("ARM-C unlocked-path-opens = {0}   [expect True = control can actually succeed]" -f $armC)
if (-not $armC) { $fails++ }
if ($hC) { $hC.Close(); $hC.Dispose() }

# ---- ARM-D: THE NEGATIVE CONTROL, reproducing the REAL historical bug faithfully.
# The old mutex did `New-Item -ItemType Directory` on a DIRECTORY path. On Windows
# that succeeds against an existing directory, so it excluded nothing. This arm
# must reproduce that on a directory (not on the file used by the other arms -
# testing it against a file would "exclude" for the wrong reason and the control
# would be theatre).
$oldDir = Join-Path $tmpDir ("_hb-oldmutex-{0}" -f $id)
$oldMutexExcluded = $true
New-Item -ItemType Directory -Path $oldDir -ErrorAction Stop | Out-Null
try {
    # OLD mutex VERBATIM, including the -Force that made it worthless.
    New-Item -ItemType Directory -Path $oldDir -Force -ErrorAction Stop | Out-Null
    $oldMutexExcluded = $false
} catch { $oldMutexExcluded = $true }
Write-Output ("ARM-D OLD-mkdir-mutex(-Force)-excludes = {0}   [expect False = the old lock was WORTHLESS]" -f $oldMutexExcluded)
if ($oldMutexExcluded) { $fails++ }   # if the old mutex ever excluded, this control proves nothing

$hHold2 = Open-Exclusive $testLock
$newMutexExcluded = ($null -eq (Open-Exclusive $testLock))
Write-Output ("ARM-D NEW-handle-mutex-excludes = {0}   [expect True = the new lock WORKS]" -f $newMutexExcluded)
if (-not $newMutexExcluded) { $fails++ }
if ($hHold2) { $hHold2.Close(); $hHold2.Dispose() }

# ---- ARM-E: the prompt must be non-empty (empty prompt = a silent useless pass) ----
$plen = (Get-Item 'H:\sotto\_moved\aireplay\_main\continue-prompt.md').Length
Write-Output ("ARM-E prompt-bytes = {0}   [expect >0]" -f $plen)
if ($plen -le 0) { $fails++ }

# ---- ARM-F: no REAL heartbeat lock held right now (or a pass is running) ----
$busy = $false
try { $probe = [System.IO.File]::Open((Join-Path $tmpDir 'heartbeat.lock'),
        [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None); $busy = $false; $probe.Close(); $probe.Dispose()
} catch { $busy = $true }
Write-Output ("ARM-F real-lock-busy = {0}   [expect False = no pass running]" -f $busy)
if ($busy) { $fails++ }

foreach ($p in @($testLock, $freeLock)) { if (Test-Path $p) { [System.IO.File]::Delete($p) } }
if (Test-Path $oldDir) { [System.IO.Directory]::Delete($oldDir, $true) }

Write-Output ''
Write-Output ("ARMS FAILED = {0}   [expect 0]" -f $fails)
exit $fails
