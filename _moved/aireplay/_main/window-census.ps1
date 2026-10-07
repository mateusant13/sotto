# window-census.ps1 -- prove whether any VISIBLE console/window appears on the owner's screen
# while probes run. Samples at its OWN cadence (default 500 ms), because the house 60 s census
# cannot see a short-lived window (AGENTS.md, Sotto).
#   pwsh -File window-census.ps1 -Seconds 120 -EveryMs 500 -Out H:\aireplay\_main\logs\window-census.log
param(
  [int]$Seconds = 120,
  [int]$EveryMs = 500,
  [string]$Out = 'H:\aireplay\_main\logs\window-census.log'
)
$dir = Split-Path -Parent $Out
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$deadline = (Get-Date).AddSeconds($Seconds)
$samples = 0
$hits = 0
$seen = @{}
while ((Get-Date) -lt $deadline) {
  $samples++
  $procs = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowHandle -ne 0 -and $_.ProcessName -match '^(python|pythonw|py)$' }
  foreach ($p in $procs) {
    $hits++
    $key = "$($p.Id)"
    if (-not $seen.ContainsKey($key)) {
      $seen[$key] = $true
      $line = "ALERTA-JANELA ts={0} pid={1} nome={2} hwnd={3} title='{4}'" -f `
        (Get-Date -Format o), $p.Id, $p.ProcessName, $p.MainWindowHandle, $p.MainWindowTitle
      Add-Content -Path $Out -Value $line
    }
  }
  Start-Sleep -Milliseconds $EveryMs
}
Add-Content -Path $Out -Value ("CENSUS-END ts={0} samples={1} every_ms={2} visible_hits={3} distinct_pids={4}" -f `
  (Get-Date -Format o), $samples, $EveryMs, $hits, $seen.Count)
