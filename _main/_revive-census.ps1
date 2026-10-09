$procs = Get-CimInstance Win32_Process
foreach ($p in $procs) {
  $cl = $p.CommandLine
  if ($null -ne $cl -and ($cl -match 'sotto_worker\.py' -or $cl -match 'sotto_webview\.py')) {
    Write-Output ("pid={0} ppid={1} ws={2} cmd={3}" -f $p.ProcessId, $p.ParentProcessId, $p.WorkingSetSize, $cl)
  }
}
Write-Output "CENSUS-DONE"
