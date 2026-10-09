$procs = Get-CimInstance Win32_Process
foreach ($p in $procs) {
  $cl = $p.CommandLine
  if ($null -ne $cl -and ($cl -match 'sotto_worker\.py' -or $cl -match 'sotto_webview\.py')) {
    $short = $cl.Substring(0, [Math]::Min(140, $cl.Length))
    try { $st = $p.CreationDate.ToString("HH:mm:ss") } catch { $st = "?" }
    Write-Output ("pid={0} ppid={1} started={2} cmd={3}" -f $p.ProcessId, $p.ParentProcessId, $st, $short)
  }
}
Write-Output "CENSUS-DONE"
