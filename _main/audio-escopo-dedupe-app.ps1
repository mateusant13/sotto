# AudioEscopo — remove MY OWN duplicate app instance.
#
# WHY: two full Sotto apps were running on the owner's box at once —
#   pid 39556 pythonw + pid 27084 python  (started 09:30, MY run.cmd relaunch)
#   pid 37684 pythonw + pid 38560 python  (started 09:35, a SECOND run.cmd launch)
# Two panels and two workers is a duplicate, and the owner's box is already
# loaded. Both instances run the SAME code (worker/wasapi_loopback.py 09:27 and
# worker/sotto_worker.py 09:26, unchanged), so removing one changes nothing about
# which code the owner runs.
#
# WHICH ONE: mine. A kill filter must never take a sibling lane's subject, and
# the 09:35 launch is not mine to remove — the pids below are the exact processes
# this lane spawned, re-verified against the artifact paths before any kill.
$log = 'H:\sotto\_main\audio-escopo-dedupe.log'
"MINE = 39556/27084 (09:30, this lane's relaunch); KEEPING 37684/38560" |
    Out-File -FilePath $log -Encoding utf8

$mine = @(39556, 27084)
foreach ($pid_ in $mine) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pid_" -ErrorAction SilentlyContinue
    if (-not $proc) {
        "SKIP pid=$pid_ not running" | Out-File -FilePath $log -Append -Encoding utf8
        continue
    }
    # ARTIFACT CHECK before the kill: only a sotto_webview.py / sotto_worker.py
    # process may be touched; anything else is left alone and reported.
    if ($proc.CommandLine -notmatch 'sotto_webview\.py' -and $proc.CommandLine -notmatch 'sotto_worker\.py') {
        "REFUSED pid=$pid_ commandline does not name the artifact: $($proc.CommandLine)" |
            Out-File -FilePath $log -Append -Encoding utf8
        continue
    }
    "KILL pid=$pid_ name=$($proc.Name)" | Out-File -FilePath $log -Append -Encoding utf8
    try { Stop-Process -Id $pid_ -Force -ErrorAction Stop }
    catch { "  stop failed: $_" | Out-File -FilePath $log -Append -Encoding utf8 }
}
Start-Sleep -Seconds 2
