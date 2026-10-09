$procs = Get-CimInstance Win32_Process
foreach ($p in $procs) {
  if ($p.Name -match '^pythonw') {
    $cl = $p.CommandLine
    if ($null -eq $cl) { $cl = "(no cmdline)" }
    else { $cl = $cl.Substring(0, [Math]::Min(160, $cl.Length)) }
    Write-Output ("pid={0} ppid={1} cmd={2}" -f $p.ProcessId, $p.ParentProcessId, $cl)
  }
}
Write-Output "PYW-DONE"
