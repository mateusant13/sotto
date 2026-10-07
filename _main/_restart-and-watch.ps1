# Restart the Sotto app cleanly and then WATCH what the real panel renders.
#
# The kill filters NAME THE ARTIFACT (house rule): `sotto_webview.py` for the
# shell and `sotto_worker.py` for the capture process. A filter on the bare word
# `sotto` once killed two unrelated processes, so this file never does that.
#
# Run with:  powershell -NoProfile -File _main\_restart-and-watch.ps1
$ErrorActionPreference = 'Continue'
$procs = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
    Where-Object { $_.CommandLine -match 'sotto_webview\.py|sotto_worker\.py' }
foreach ($p in $procs) {
    "killing pid=$($p.ProcessId) :: $($p.CommandLine.Substring(0, [Math]::Min(90, $p.CommandLine.Length)))"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
"remaining: $((Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" | Where-Object { $_.CommandLine -match 'sotto_webview\.py|sotto_worker\.py' } | Measure-Object).Count)"
