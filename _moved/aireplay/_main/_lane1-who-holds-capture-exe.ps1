# _lane1-who-holds-capture-exe.ps1 — who has _main\build\aireplay-capture.exe open?
# A .ps1 FILE, not an inline -Command: measured on this box, the inline form returns EMPTY
# stdout from Get-CimInstance Win32_Process while the file form returns every row (AGENTS.md).
$ErrorActionPreference = "Continue"
$rows = Get-CimInstance Win32_Process -Filter "Name='aireplay-capture.exe'"
if (-not $rows) { Write-Output "NO aireplay-capture.exe PROCESS RUNNING" }
foreach ($r in $rows) {
    Write-Output ("PID={0} CREATED={1} CMD={2}" -f $r.ProcessId, $r.CreationDate, $r.CommandLine)
}
$exe = "H:\aireplay\_main\build\aireplay-capture.exe"
if (Test-Path $exe) {
    Write-Output ("EXE lastwrite={0} size={1}" -f (Get-Item $exe).LastWriteTime, (Get-Item $exe).Length)
    try {
        $fs = [System.IO.File]::Open($exe, 'Open', 'ReadWrite', 'None')
        $fs.Close()
        Write-Output "EXE LOCK STATE: not locked (opened exclusively OK)"
    } catch {
        Write-Output ("EXE LOCK STATE: LOCKED -> {0}" -f $_.Exception.Message)
    }
}