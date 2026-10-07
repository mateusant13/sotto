# AudioEscopo — restart THE APP so the running worker is the FIXED one.
#
# WHY A RESTART IS REQUIRED (not optional here):
#   app/webview/sotto_webview.py's hot-reload QUEUED the worker restart when
#   worker/wasapi_loopback.py changed, then DEFERRED it with
#   `reason=capturing -- applies at the next boundary`. `boundary()` is only
#   attempted from `on_worker_status`, and `is_capturing()` stays true while the
#   old worker keeps streaming a silent device — so the held reload never lands.
#   Without this restart the owner keeps seeing "Audio tap silent - nothing to
#   transcribe" on a worker that predates the fix.
#
# KILL FILTER NAMES THE ARTIFACT (AGENTS.md hard rule): sotto_worker\.py and
# sotto_webview\.py, never the bare word `sotto` (that once killed two unrelated
# closure-admission.sh processes).
$log = 'H:\sotto\_main\audio-escopo-restart.log'
"=== AudioEscopo restart $(Get-Date -Format o) ===" | Out-File -FilePath $log -Encoding utf8

$victims = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'sotto_worker\.py' -or $_.CommandLine -match 'sotto_webview\.py' }
foreach ($v in $victims) {
    "KILL pid=$($v.ProcessId) name=$($v.Name)" | Out-File -FilePath $log -Append -Encoding utf8
    try {
        Stop-Process -Id $v.ProcessId -Force -ErrorAction Stop
    } catch {
        "  stop failed: $_" | Out-File -FilePath $log -Append -Encoding utf8
    }
}
"killed=$($victims.Count)" | Out-File -FilePath $log -Append -Encoding utf8
Start-Sleep -Seconds 2
