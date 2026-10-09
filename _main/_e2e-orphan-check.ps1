# Orphan check after the end-to-end arm. The rule: a PowerShell filter that reads a
# process list runs from a FILE with Get-CimInstance -- the inline -Command form
# returns EMPTY stdout on this box and would report "nothing is running" as a fact.
$ErrorActionPreference = 'SilentlyContinue'
Write-Output "child pid from the shell log: 5588"
$child = Get-Process -Id 5588
if ($null -eq $child) {
  Write-Output "ORPHAN-CHILD: pid 5588 is GONE -> GREEN"
} else {
  Write-Output ("ORPHAN-CHILD: pid 5588 STILL ALIVE name={0} start={1} -> RED" -f $child.ProcessName, $child.StartTime)
}

$hits = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -and $_.CommandLine -match 'redux_live\.py' }
if ($null -eq $hits -or @($hits).Count -eq 0) {
  Write-Output "ORPHAN-SCAN: no process command line mentions redux_live.py -> GREEN"
} else {
  foreach ($h in @($hits)) {
    Write-Output ("ORPHAN-SCAN: pid {0} name={1} -> RED`n  {2}" -f $h.ProcessId, $h.Name, $h.CommandLine)
  }
}

# The owner's two pids must be untouched, and no audio device may be held by me.
foreach ($pid_ in 28428, 29008) {
  $p = Get-Process -Id $pid_
  if ($null -eq $p) {
    Write-Output ("OWNER-PID {0}: NOT RUNNING (was running earlier -- report it)" -f $pid_)
  } else {
    Write-Output ("OWNER-PID {0}: alive name={1} cpu_s={2:N1} rss_mb={3:N0}" -f `
      $pid_, $p.ProcessName, $p.CPU, ($p.WorkingSet64 / 1MB))
  }
}

$sotto = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -and $_.CommandLine -match 'sotto_webview\.py|redux_live\.py' }
Write-Output ("SOTTO-FAMILY processes now: {0}" -f @($sotto).Count)
foreach ($h in @($sotto)) {
  Write-Output ("  pid {0} name={1}" -f $h.ProcessId, $h.Name)
}
