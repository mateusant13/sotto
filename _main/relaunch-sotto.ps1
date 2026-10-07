# Kill the Sotto APP and its ORPHANED workers, then relaunch.
# Deliberately NARROW: matches the worker script path and the app entry,
# and excludes a lane's probe (`sotto-vs-ref-probe.py`) which must survive.
$ErrorActionPreference = 'SilentlyContinue'

$procs = Get-CimInstance Win32_Process
$killed = @()

foreach ($p in $procs) {
    $c = $p.CommandLine
    if (-not $c) { continue }

    # a lane's probe -> never touch
    if ($c -like '*sotto-vs-ref-probe*') { continue }
    # a lane's own short-lived test panel -> let it expire on --exit-after
    if ($c -like '*--exit-after*')          { continue }

    # FULL PATH under H:\sotto, never a bare token, and never a generic word:
    # a filter that matched a generic token once killed 12 processes of the
    # owner's OTHER project (I:\!manager\_scratch\tbig-census.py, which
    # auto-respawned). Both slash styles, case-insensitive, anchored on H:\sotto.
    $isApp    = ($c -match '(?i)H:[\\/]sotto[\\/]app[\\/]webview[\\/]sotto_webview\.py') -and ($c -match '--log')
    $isWorker = ($c -match '(?i)H:[\\/]sotto[\\/]worker[\\/]sotto_worker\.py')

    if ($isApp -or $isWorker) {
        Write-Output ("KILL pid={0,-6} {1,-12} {2}" -f $p.ProcessId, $p.Name, $c.Substring(0, [Math]::Min(95, $c.Length)))
        Stop-Process -Id $p.ProcessId -Force
        $killed += $p.ProcessId
    }
}

Write-Output ("TOTAL killed={0}" -f $killed.Count)
Start-Sleep -Seconds 4
Write-Output '--- survivors matching *sotto* ---'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*sotto*' } |
    ForEach-Object { Write-Output ("  pid={0,-6} {1}" -f $_.ProcessId, $_.CommandLine.Substring(0,[Math]::Min(95,$_.CommandLine.Length))) }

Start-Process -FilePath 'C:\Program Files\Python311\pythonw.exe' `
    -ArgumentList '"H:\sotto\app\webview\sotto_webview.py"','--log','"H:\sotto\_main\webview-run.log"','--with-worker' `
    -WorkingDirectory 'H:\sotto'
Write-Output 'RELAUNCHED app'
