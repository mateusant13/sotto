# LANE9-GATE -- the mechanical gate for lane 9 ("the ASR works end-to-end on real audio").
#
# Arms live in src/asr/gate.py (that file is owned by lane 9; this script only launches it and
# reads its exit code).  A, B and C are printed by the driver:
#   A  real speech WAV (already on this box) -> transcript, scored against the registered oracle
#   B  the language prompt, both directions: the graph declares no language input, onnx_asr
#      silently ignores the kwarg, and our engine refuses it
#   C  the CONTROL -- the same package with both cures reverted in a COPY, which must show the
#      pre-cure defect (a provider that did not load, accepted anyway)
#
# Prints LANE9-GATE PASS and exits 0 only when every arm behaves.  Arms A-en, A-pt, B, C, D.
#
# RULES HONOURED HERE (LANE-BRIEF.md section 4):
#   rule 1  no visible console window: pythonw.exe / Start-Process -WindowStyle Hidden
#   rule 2  the exit code is read from the process object's .ExitCode, NEVER through a pipe
#   rule 3  native H:\ paths only
#
# Usage:  pwsh -File _main\_lane9-asr-gate.ps1
#         pwsh -File _main\_lane9-asr-gate.ps1 -Json _main\lane9-gate.json
param(
    [string]$Json = "",
    [int]$TimeoutSec = 3600
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # the transcripts are non-ASCII; cp1252 would die on print

$Repo    = 'H:\sotto\_moved\aireplay'
$Src     = Join-Path $Repo 'src'
$Out     = Join-Path $Repo '_main'
$Log     = Join-Path $Out 'lane9-asr-gate.log'
$JsonOut = if ($Json) { if ([IO.Path]::IsPathRooted($Json)) { $Json } else { Join-Path $Repo $Json } }
           else { Join-Path $Out 'lane9-asr-gate.json' }

if (-not (Test-Path (Join-Path $Src 'asr\gate.py'))) {
    Write-Output "LANE9-GATE FAIL"
    Write-Output "  driver missing: $Src\asr\gate.py"
    exit 1
}

Write-Output "LANE9-GATE  repo=$Repo"
Write-Output "  wavs (real speech, already on this box):"
Write-Output "    H:\sotto\_main\_redux-long\src-en-8s.wav    (English, 8.543 s)"
Write-Output "    H:\sotto\_main\_redux-long\src-pt-15s.wav   (Portuguese, 15.0 s)"

# rule 1: no console window on the owner's screen.
#   `Start-Process -WindowStyle Hidden` sets STARTUPINFO's wShowWindow AND is the documented
#   PowerShell route to CREATE_NO_WINDOW for a console-subsystem child; it is applied HERE
#   rather than on a System.Diagnostics.Process, because ProcessStartInfo on .NET exposes no
#   CreationFlags property -- a variable holding 0x08000000|0x00000008 that nothing reads
#   would be decoration, and decoration is what this repo keeps having to unpick.
$stdoutFile = Join-Path $Out 'lane9-asr-gate.stdout.txt'
$stderrFile = Join-Path $Out 'lane9-asr-gate.stderr.txt'
$pyw = 'C:\Program Files\Python311\pythonw.exe'
$exe = if (Test-Path $pyw) { $pyw } else { 'py' }
$argList = if ($exe -eq 'py') { @('-3', '-m', 'asr.gate', '--json', $JsonOut) }
           else              { @('-m', 'asr.gate', '--json', $JsonOut) }

$p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $Src `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile

# $TimeoutSec is honoured here: -Wait alone would block forever (verifier F8 -- it was
# declared and never used, so a hung run looked like a slow one).
if (-not $p.WaitForExit($TimeoutSec * 1000)) {
    try { $p.Kill() } catch { }
    Write-Output "LANE9-GATE FAIL"
    Write-Output "  driver exceeded ${TimeoutSec}s and was killed"
    exit 1
}
$rc = $p.ExitCode   # rule 2: the process object's own status, never a pipe's
$stdout = if (Test-Path $stdoutFile) { Get-Content $stdoutFile -Raw -Encoding UTF8 } else { '' }
$stderr = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw -Encoding UTF8 } else { '' }

# The transcript must survive non-ASCII; Write-Output would re-encode through the console.
[Console]::OutputEncoding = [Text.Encoding]::UTF8
if ($stdout) { Write-Output $stdout.TrimEnd() }
if ($stderr) {
    Write-Output "--- driver stderr (full, unfiltered: a traceback must stay visible -- verifier F9) ---"
    Write-Output $stderr.TrimEnd()
}

$summary = "LANE9-GATE rc=$rc  $(Get-Date -Format s)"
Add-Content -Path $Log -Value $summary -Encoding UTF8
Write-Output "  json: $JsonOut"
Write-Output "  log : $Log"

if ($rc -eq 0) {
    Write-Output "LANE9-GATE PASS"
    exit 0
}
Write-Output "LANE9-GATE FAIL (rc=$rc)"
exit $rc