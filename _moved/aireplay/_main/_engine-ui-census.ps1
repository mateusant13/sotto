$ErrorActionPreference = 'SilentlyContinue'
$out = $env:CENSUS_OUT
$max = [int]$env:CENSUS_MAX_S
$stop = $env:CENSUS_STOP_FILE
$cad = [int]$env:CENSUS_MS
$start = Get-Date
$n = 0
while ($true) {
  $now = Get-Date
  if (((New-TimeSpan -Start $start -End $now).TotalSeconds -ge $max) -or (Test-Path $stop)) { break }
  $n++
  $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'"
  $tracked = @()
  foreach ($p in $procs) {
    if ($p.CommandLine -match 'aireplay\\src\\engine\\(engine\.py|ui_child\.py|stub_capture\.py|asr_worker\.py)') {
      $h = 0; $t = ''
      $gp = Get-Process -Id $p.ProcessId
      if ($gp) { $h = $gp.MainWindowHandle; $t = $gp.MainWindowTitle }
      $tracked += ('{0}:{1}:h={2}:t={3}' -f $p.Name, $p.ProcessId, $h, $t)
    }
  }
  $vis = @($tracked | Where-Object { $_ -match ':h=[1-9][0-9]*' }).Count
  $line = ('{0:yyyy-MM-dd HH:mm:ss}  sample={1} tracked={2} visible={3} :: {4}' -f $now, $n, $tracked.Count, $vis, ($tracked -join ' '))
  Add-Content -Path $out -Value $line
  Start-Sleep -Milliseconds $cad
}
Add-Content -Path $out -Value ("CENSUS-END samples=" + $n)
