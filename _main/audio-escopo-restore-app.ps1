# AudioEscopo — replace the BROKEN app instance with a working one.
#
# WHY: the running shell (pid 20656, started 10:03:14) spawned its worker with
# `I:\!manager\.venv\Scripts\python.EXE` (no onnxruntime) and the worker died on
# every restart: BRIDGE_DEATH rc=1 deaths=5, `ModuleNotFoundError: No module
# named 'onnxruntime'`. The panel therefore shows "Worker stopped (exit 1)" and
# the app can NEVER transcribe. That instance is not recoverable — it re-spawns
# the same wrong interpreter each time (default_python() -> shutil.which('python')).
#
# So: kill it (artifact-named; nothing else matches), then relaunch THE APP with
# the worker interpreter PINNED to the one this box's worker actually needs, using
# the shell's own `--python` flag rather than hoping PATH resolves correctly.
$log = 'H:\sotto\_main\audio-escopo-restore.log'
"=== AudioEscopo restore $(Get-Date -Format o) ===" | Out-File -FilePath $log -Encoding utf8

"--- before ---" | Out-File -FilePath $log -Append -Encoding utf8
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'sotto_webview\.py' -or $_.CommandLine -match 'sotto_worker\.py' } |
    ForEach-Object { "  pid=$($_.ProcessId) $($_.Name) started=$($_.CreationDate.ToString('HH:mm:ss'))" } |
    Out-File -FilePath $log -Append -Encoding utf8

$victims = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'sotto_webview\.py' -or $_.CommandLine -match 'sotto_worker\.py' }
foreach ($v in $victims) {
    if ($v.CommandLine -notmatch 'sotto_webview\.py' -and $v.CommandLine -notmatch 'sotto_worker\.py') {
        "REFUSED pid=$($v.ProcessId): command line does not name the artifact" |
            Out-File -FilePath $log -Append -Encoding utf8
        continue
    }
    "KILL pid=$($v.ProcessId) $($v.Name)" | Out-File -FilePath $log -Append -Encoding utf8
    try { Stop-Process -Id $v.ProcessId -Force -ErrorAction Stop }
    catch { "  stop failed: $_" | Out-File -FilePath $log -Append -Encoding utf8 }
}
Start-Sleep -Seconds 3

# Relaunch through the app's OWN entry point, pinning the worker interpreter.
$py = 'C:\Program Files\Python311\python.exe'
"LAUNCH: run.cmd --with-worker --python `"$py`"" | Out-File -FilePath $log -Append -Encoding utf8
$out = & cmd.exe /c "H:\sotto\app\webview\run.cmd --with-worker --python `"$py`"" 2>&1
$rc = $LASTEXITCODE
"run.cmd rc=$rc" | Out-File -FilePath $log -Append -Encoding utf8
$out | Out-File -FilePath $log -Append -Encoding utf8
Start-Sleep -Seconds 4

"--- after ---" | Out-File -FilePath $log -Append -Encoding utf8
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'sotto_webview\.py' -or $_.CommandLine -match 'sotto_worker\.py' } |
    ForEach-Object { "  pid=$($_.ProcessId) $($_.Name) started=$($_.CreationDate.ToString('HH:mm:ss'))" } |
    Out-File -FilePath $log -Append -Encoding utf8
