$procs = Get-CimInstance Win32_Process
foreach ($p in $procs) {
  if ($p.Name -match '^pythonw?\.exe$') {
    $cl = $p.CommandLine
    if ($null -eq $cl) { $cl = "(null-cmdline)" }
    else { $cl = $cl.Substring(0, [Math]::Min(150, $cl.Length)) }
    try { $st = ([Management.ManagementDateTimeConverter]::ToDateTime($p.CreationDate)).ToString("HH:mm:ss") } catch { $st = "?" }
    Write-Output ("pid={0} ppid={1} name={2} started={3} cmd={4}" -f $p.ProcessId, $p.ParentProcessId, $p.Name, $st, $cl)
  }
}
Write-Output "PY-DONE"
