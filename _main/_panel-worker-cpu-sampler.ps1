# Sample the OWNER'S worker CPU (native Get-Process only — NO WMI, no CIM) beside
# the panel's own published visibility, so "does the live engine burn cores while
# the panel is CLOSED" becomes a number instead of a belief.
#
# Cost: one pwsh thread, one Get-Process per second on a single known pid, one
# small JSON read. No process enumeration, no WMI, no window census.
$ErrorActionPreference = 'SilentlyContinue'
$out = 'H:\sotto\_main\_panel-worker-cpu.jsonl'
$vis = 'H:\sotto\_main\panel-visibility.json'
$workerPid = 29008
$seconds = 300
Remove-Item $out -ErrorAction SilentlyContinue
$deadline = (Get-Date).AddSeconds($seconds)
while ((Get-Date) -lt $deadline) {
  $p = Get-Process -Id $workerPid -ErrorAction SilentlyContinue
  $v = $null
  try { $v = Get-Content $vis -Raw | ConvertFrom-Json } catch { }
  $row = [ordered]@{
    ts      = (Get-Date).ToString('o')
    cpu     = if ($p) { [double]$p.CPU } else { $null }
    threads = if ($p) { $p.Threads.Count } else { $null }
    ws_mb   = if ($p) { [math]::Round($p.WorkingSet64 / 1MB, 1) } else { $null }
    visible = if ($v) { $v.visible } else { $null }
    sinceMs = if ($v) { $v.since_ms } else { $null }
    reason  = if ($v) { $v.reason } else { $null }
  }
  ($row | ConvertTo-Json -Compress) | Add-Content -Path $out
  Start-Sleep -Milliseconds 1000
}
