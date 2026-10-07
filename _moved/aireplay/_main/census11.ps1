# census11.ps1 -- prove whether any VISIBLE window appears while the threads-11 sweep runs.
# The house 60 s census cannot see a short-lived window, so this samples at its OWN cadence.
# Filter is broad on purpose (python/pythonw/py/pwsh/powershell/conhost/node): if ANY of them
# maps a window, it is logged with pid + class + title, and the reader attributes it.
#   pwsh -NoProfile -File census11.ps1 -Seconds 900 -EveryMs 200 -Out <log>
param(
  [int]$Seconds = 900,
  [int]$EveryMs = 200,
  [string]$Out = 'H:\aireplay\_main\logs\census11.log'
)
$dir = Split-Path -Parent $Out
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
"# census11 start ts={0} every_ms={1} seconds={2}" -f (Get-Date -Format o), $EveryMs, $Seconds |
  Add-Content -Path $Out
$deadline = (Get-Date).AddSeconds($Seconds)
$samples = 0
$hits = 0
$seen = @{}
while ((Get-Date) -lt $deadline) {
  $samples++
  $procs = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowHandle -ne 0 -and $_.ProcessName -match '^(python|pythonw|py|pwsh|powershell|conhost|node)$' }
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
