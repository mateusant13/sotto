$procs = Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match 'sotto_worker\.py' -or $_.CommandLine -match 'sotto_webview\.py'
} | Select-Object ProcessId, ParentProcessId, CreationDate, CommandLine
$count = ($procs | Measure-Object).Count
Write-Output "MATCH_COUNT=$count"
foreach ($p in $procs) {
  Write-Output ("PID={0} PPID={1} CREATED={2} CMD={3}" -f $p.ProcessId, $p.ParentProcessId, $p.CreationDate, $p.CommandLine)
}
Write-Output "---ALL PYTHON---"
$py = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' } | Select-Object ProcessId, ParentProcessId, Name, CommandLine
foreach ($p in $py) {
  Write-Output ("PID={0} PPID={1} NAME={2} CMD={3}" -f $p.ProcessId, $p.ParentProcessId, $p.Name, $p.CommandLine)
}
