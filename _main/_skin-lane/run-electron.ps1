# Launch an Electron instrument after proving no stale Electron holds the profile.
#
# A stale electron.exe keeps the Chromium profile locked, and the symptom is an instrument
# that produces ZERO bytes and never exits (measured twice in this repo). The filter names
# the ARTIFACT — the electron executable's own path — never a bare word.
#
# This exists as a FILE because an inline `-Command` process filter returns EMPTY stdout on
# this box, so an inline version silently reports "nothing is running".
#
# Usage:  pwsh -File _main/_skin-lane/run-electron.ps1 -Main _main/_skin-lane/freeze.js -Args '--only','rainline'
param(
  [Parameter(Mandatory = $true)][string]$Main,
  # NOT named $Args: that is an AUTOMATIC PowerShell variable, and a parameter shadowing
  # it is not bound — the first run passed `--only rainline` as one quoted token, the
  # instrument never saw the flag, and it froze all 20 designs while the caller believed
  # it had asked for one.
  [string[]]$Extra = @(),
  [int]$TimeoutSec = 900
)

$exe = 'H:\sotto\app\node_modules\electron\dist\electron.exe'
$stale = @(Get-CimInstance Win32_Process -Filter "Name='electron.exe'" -ErrorAction SilentlyContinue |
           Where-Object { $_.ExecutablePath -eq $exe })
if ($stale.Count -gt 0) {
  foreach ($p in $stale) {
    Write-Output ("STALE electron pid={0} started={1} - killing" -f $p.ProcessId, $p.CreationDate)
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 2
} else {
  Write-Output "no stale electron.exe (matched by executable path)"
}

$argList = @($Main) + $Extra + @('--no-sandbox')
Write-Output ("launching: {0} {1}" -f $exe, ($argList -join ' '))
$p = Start-Process -FilePath $exe -ArgumentList $argList -NoNewWindow -Wait -PassThru `
  -RedirectStandardOutput "$env:TEMP\skin-out.txt" -RedirectStandardError "$env:TEMP\skin-err.txt" `
  -WorkingDirectory 'H:\sotto'
Get-Content "$env:TEMP\skin-out.txt"
$err = Get-Content "$env:TEMP\skin-err.txt" -ErrorAction SilentlyContinue
if ($err) { Write-Output '--- stderr ---'; $err | Select-Object -First 40 }
Write-Output ("EXIT={0}" -f $p.ExitCode)
