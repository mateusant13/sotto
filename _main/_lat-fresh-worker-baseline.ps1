# Control for: "is 7 304 MB of committed private memory normal for a live Sotto worker?"
#
# The subject is the owner's RUNNING worker, pid 29008, started 2026-10-07 08:01:56:
#   WorkingSet64        132.7 MB   <- what is resident
#   PrivateMemorySize64 7304.4 MB  <- what is committed
#   VirtualMemorySize64 100116 MB
# That is only meaningful next to a FRESH instance of the SAME config, so this loads the
# model once and samples both numbers.
#
# --selftest is "transcribe a file, no audio device needed" (sotto_worker.py:2920): it opens
# NO capture endpoint, so it cannot take AUDCLNT_E_DEVICE_IN_USE away from pid 29008.
#
# Instruments, named: PeakWorkingSet64 / PeakPrivateMemorySize64 sampled every 250 ms from the
# Process object; the child's MainWindowHandle is sampled on the same tick so "no visible
# console" is counted, not assumed (AGENTS: a hidden launch is a claim, not a fact).
$ErrorActionPreference = 'Stop'

$out = 'H:\sotto\_main\_lat-fresh-worker.out'
$err = 'H:\sotto\_main\_lat-fresh-worker.err'
Remove-Item $out, $err -ErrorAction SilentlyContinue

$p = Start-Process -FilePath 'C:\Program Files\Python311\python.exe' `
    -ArgumentList @('H:\sotto\worker\sotto_worker.py', '--selftest') `
    -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
"CHILD pid=$($p.Id)"

$peakWs = 0.0; $peakPriv = 0.0; $samples = 0; $visSamples = 0
while (-not $p.HasExited) {
    $p.Refresh()
    if ($p.WorkingSet64 -gt $peakWs) { $peakWs = $p.WorkingSet64 }
    if ($p.PrivateMemorySize64 -gt $peakPriv) { $peakPriv = $p.PrivateMemorySize64 }
    $samples++
    $g = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
    if ($g -and $g.MainWindowHandle -ne 0) { $visSamples++ }
    Start-Sleep -Milliseconds 250
}
$p.WaitForExit()

"EXIT rc=$($p.ExitCode)"
"SAMPLES=$samples  VISIBLE_MAINWINDOW_SAMPLES=$visSamples"
"PEAK_WORKINGSET_MB=$([math]::Round($peakWs / 1MB, 1))"
"PEAK_PRIVATE_MB=$([math]::Round($peakPriv / 1MB, 1))"
"SUBJECT_WORKINGSET_MB=132.7  SUBJECT_PRIVATE_MB=7304.4"
'--- stderr tail ---'
if (Test-Path $err) { Get-Content $err -Tail 20 }
'--- stdout tail ---'
if (Test-Path $out) { Get-Content $out -Tail 6 }
