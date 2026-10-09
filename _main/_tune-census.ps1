# Which engine is the running worker using, and what is the panel wearing?
# File form is mandatory on this box: inline -Command returns EMPTY stdout.
$ErrorActionPreference = 'SilentlyContinue'

Write-Output "=== PROCESSES (artifact-named filters only) ==="
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'sotto_worker\.py|sotto_webview\.py' } |
  ForEach-Object {
    $cl = $_.CommandLine
    $model = if ($cl -match '--model\s+(\S+)') { $matches[1] } else { '(no --model flag: worker reads worker/config.json)' }
    $bits = @()
    if ($cl -match '--redux-when-hidden') { $bits += 'redux-when-hidden' }
    if ($cl -match '--lang-id\s+(\S+)') { $bits += ('lang-id=' + $matches[1]) }
    Write-Output ("pid={0} name={1} model={2} extra=[{3}]" -f $_.ProcessId, $_.Name, $model, ($bits -join ','))
    Write-Output ("  cmdline_len={0}" -f $cl.Length)
  }

Write-Output ""
Write-Output "=== worker/config.json model.dir (what the live engine loads with no flag) ==="
$cfg = 'H:\sotto\worker\config.json'
if (Test-Path $cfg) {
  $j = Get-Content $cfg -Raw | ConvertFrom-Json
  Write-Output ("model.dir      = {0}" -f $j.model.dir)
  Write-Output ("model.lang_id  = {0}" -f $j.model.lang_id)
  Write-Output ("use_denoise    = {0}" -f $j.use_denoise)
  Write-Output ("output.partial = {0}" -f $j.output.partial)
} else { Write-Output "config missing: $cfg" }

Write-Output ""
Write-Output "=== panel state / webview log tail ==="
$ps = 'H:\sotto\_main\panel-state.json'
if (Test-Path $ps) {
  Write-Output ("panel-state.json mtime = {0}" -f (Get-Item $ps).LastWriteTime)
  Get-Content $ps -Raw | Select-Object -First 1
} else { Write-Output "no panel-state.json" }
