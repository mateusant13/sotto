# _lane3-ringcap-falsify.ps1 — proves the lane-3 gate can say NO.
#
# A gate that only ever prints PASS is decoration.  This script attacks ARM-D (the control):
# it replaces the PRE-CHANGE ring_buffer copy with the CURRENT one and re-runs the gate.  The
# current code HAS the budget API, so the control's caller now links, and the check
# "old_copy_really_lacks_the_api" must go RED.  If it stays green, arm D is vacuous and the
# gate is not measuring anything.
#
# The evidence files are restored afterwards and verified by SHA-256, so the falsification
# cannot silently become the new baseline.
#
# Exit: 0 = the gate correctly refused (falsification worked). Non-zero = the gate is broken.

$ErrorActionPreference = 'Continue'
$Prod  = 'H:\sotto\_moved\aireplay'
$Main  = Join-Path $Prod '_main'
$Ctl   = Join-Path $Main '_lane3-ringcap-control'
$Logs  = Join-Path $Main 'logs'
$Gate  = Join-Path $Main '_lane3-ringcap-gate.ps1'

$ph = Join-Path $Ctl 'ring_buffer.h.prefix'
$pc = Join-Path $Ctl 'ring_buffer.cpp.prefix'
$origHashH = (Get-FileHash -Algorithm SHA256 -LiteralPath $ph).Hash
$origHashC = (Get-FileHash -Algorithm SHA256 -LiteralPath $pc).Hash
Write-Output "FALSIFY baseline ring_buffer.h.prefix   sha256=$origHashH"
Write-Output "FALSIFY baseline ring_buffer.cpp.prefix sha256=$origHashC"

# Snapshot the evidence so a crash mid-script cannot lose it.
$bak = Join-Path $Ctl 'evidence-backup'
foreach ($f in @($ph, $pc)) { Copy-Item -LiteralPath $f -Destination (Join-Path $bak (Split-Path -Leaf $f)) -Force }

try {
    # The attack: make the "pre-change" copy BE the current code.
    Copy-Item -LiteralPath (Join-Path $Prod 'src\capture\ring_buffer.h')   -Destination $ph -Force
    Copy-Item -LiteralPath (Join-Path $Prod 'src\capture\ring_buffer.cpp') -Destination $pc -Force
    Write-Output 'FALSIFY planted the CURRENT ring_buffer over the pre-change control copy'

    # NOTE: the log path must NOT be this script's own stdout redirect, or pwsh deadlocks
    # writing a file it is already redirecting into.  Doing that made the script fall through
    # to an implicit exit 0 — a MASKED GREEN on a run that had proved nothing.
    $log = Join-Path $Logs 'lane3-falsify-gate.log'
    pwsh -NoProfile -File $Gate > $log 2>&1
    $rc = $LASTEXITCODE

    $out = Get-Content -LiteralPath $log -Raw
    $armedDgreen  = ($out -match "ARM-D[\s\S]*?\[PASS\] old_copy_really_lacks_the_api")
    $armedDred    = ($out -match "ARM-D[\s\S]*?\[FAIL\] old_copy_really_lacks_the_api")
    $gateFailed   = ($out -match 'LANE3-GATE FAIL')

    Write-Output ("FALSIFY gate rc={0}  gate_said_FAIL={1}  armD_passed={2}  armD_failed={3}" -f $rc, $gateFailed, $armedDgreen, $armedDred)

    $ok = ($rc -ne 0) -and $gateFailed -and $armedDred -and (-not $armedDgreen)
    if ($ok) {
        Write-Output ''
        Write-Output 'FALSIFY PASS: with the control copy poisoned by the current code, ARM-D went RED'
        Write-Output '             and the gate refused.  The control is not vacuous.'
        Write-Output 'FALSIFY VERDICT PASS'
        exit 0
    }
    Write-Output ''
    Write-Output "FALSIFY VERDICT FAIL: the gate did not go RED on a poisoned control (rc=$rc)"
    Write-Output '--- gate output ---'
    Write-Output $out
    $script:falsifyFailed = $true
}
finally {
    Copy-Item -LiteralPath (Join-Path $bak 'ring_buffer.h.prefix')   -Destination $ph -Force
    Copy-Item -LiteralPath (Join-Path $bak 'ring_buffer.cpp.prefix') -Destination $pc -Force
    $restoredH = (Get-FileHash -Algorithm SHA256 -LiteralPath $ph).Hash
    $restoredC = (Get-FileHash -Algorithm SHA256 -LiteralPath $pc).Hash
    Write-Output ''
    Write-Output ("FALSIFY evidence restored: h={0} c={1}" -f ($restoredH -eq $origHashH), ($restoredC -eq $origHashC))
    if ($restoredH -ne $origHashH -or $restoredC -ne $origHashC) {
        Write-Output 'FALSIFY ABORT: the pre-change evidence did NOT restore to its original bytes'
        $script:restoreFailed = $true
    }
}

# The ONLY two ways this script may end: the verdict, or a restore failure.  A script that
# simply falls off the end reports exit 0 — a green that means nothing, which is precisely the
# masked-status failure this repo already has a receipt about.  Never rely on falling through.
if ($script:restoreFailed) { exit 2 }
if ($script:falsifyFailed) { exit 1 }
exit 0