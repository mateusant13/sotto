$procs = Get-CimInstance Win32_Process
$killed = @()
foreach ($p in $procs) {
  $cl = $p.CommandLine
  if ($null -ne $cl -and ($cl -match 'sotto_worker\.py' -or $cl -match 'sotto_webview\.py')) {
    $pid_ = $p.ProcessId
    try {
      Stop-Process -Id $pid_ -Force -ErrorAction Stop
      $killed += $pid_
      Write-Output ("KILLED pid={0} cmd={1}" -f $pid_, $cl.Substring(0, [Math]::Min(120, $cl.Length)))
    } catch {
      Write-Output ("KILL-FAILED pid={0} err={1}" -f $pid_, $_)
    }
  }
}
if ($killed.Count -eq 0) { Write-Output "NOTHING-TO-KILL" }
Write-Output "KILL-DONE"
