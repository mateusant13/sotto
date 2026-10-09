# Sotto — restart the SHELL so the no-audio-latch cure is the code that runs.
#
# WHY A RESTART IS REQUIRED AT ALL: the cure is in `app/webview/sotto_webview.py`,
# and the running shell (pid observed in the census) was started BEFORE the edit —
# Python does not hot-reload itself. The PANEL assets do hot reload, so the gear
# button needs no restart; this one is only about the shell's Python.
#
# THE KILL FILTER NAMES THE ARTIFACT, never a generic word: `sotto_worker\.py` and
# `sotto_webview\.py`. Filtering on the bare word `sotto` once killed two unrelated
# processes on this box (AGENTS.md, hard rules).
#
# The launch is the DOCUMENTED one — `app/webview/run.cmd`, which goes through
# `pythonw.exe` (a GUI-subsystem binary: Windows allocates no console) and passes
# `--log _main/webview-run.log` plus a fresh `--ready-file`. `-WindowStyle Hidden`
# covers the wrapper itself, and NO window may appear on the owner's screen.

$ErrorActionPreference = 'Continue'
$log = 'H:\sotto\_main\_shell-restart-latch.log'
$findings = New-Object System.Collections.Generic.List[string]
function Say($m) { $findings.Add($m); Write-Output $m }

Say "=== 1. WHO IS RUNNING (before) ==="
$before = @(Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match 'sotto_worker\.py|sotto_webview\.py' })
foreach ($p in $before) { Say ("pid={0} name={1}" -f $p.ProcessId, $p.Name) }
if ($before.Count -eq 0) { Say "nothing running: the launch below starts the app fresh" }

Say ""
Say "=== 2. STOP THEM (artifact names only) ==="
foreach ($p in $before) {
  try {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
    Say ("killed pid={0} name={1}" -f $p.ProcessId, $p.Name)
  } catch {
    Say ("could not kill pid={0}: {1}" -f $p.ProcessId, $_.Exception.Message)
  }
}

# Wait until the process table is really clear: the single-instance lock
# (`Local\SottoShell`) and the audio endpoint both lag the kill by a moment, and a
# launch into either one is refused or lands on a busy endpoint.
$deadline = (Get-Date).AddSeconds(20)
$left = $null
do {
  Start-Sleep -Milliseconds 500
  $left = @(Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match 'sotto_worker\.py|sotto_webview\.py' })
} while ($left.Count -gt 0 -and (Get-Date) -lt $deadline)
Say ("still alive after the wait: {0}" -f $left.Count)
foreach ($p in $left) { Say ("  STILL pid={0} name={1}" -f $p.ProcessId, $p.Name) }

Say ""
Say "=== 3. LAUNCH (documented path, hidden) ==="
$logLenBefore = 0
if (Test-Path 'H:\sotto\_main\webview-run.log') {
  $logLenBefore = (Get-Item 'H:\sotto\_main\webview-run.log').Length
}
$p = Start-Process -FilePath 'cmd.exe' `
  -ArgumentList '/c', 'H:\sotto\app\webview\run.cmd' `
  -WorkingDirectory 'H:\sotto' -WindowStyle Hidden -PassThru
Say ("started run.cmd pid={0} (its own exit is the wrapper's, not the app's)" -f $p.Id)

Say ""
Say "=== 4. WAIT FOR THE PANEL AND THE MODEL ==="
$deadline = (Get-Date).AddSeconds(75)
$ready = $false
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 3
  if (Test-Path 'H:\sotto\_main\panel-state.json') {
    $st = Get-Content 'H:\sotto\_main\panel-state.json' -Raw | ConvertFrom-Json
    if ($st.worker -and $st.worker.state) {
      Say ("t+{0,3}s  state={1} namedState={2} noAudio={3} captions={4} pid={5}" -f `
        [int]((Get-Date) - $p.StartTime).TotalSeconds, $st.worker.state, $st.namedState, `
        $st.worker.noAudio, $st.worker.captions, $st.worker.childPid)
      if ($st.worker.state -eq 'capture-started') { $ready = $true; break }
    }
  }
}
Say ("reached capture-started: {0}" -f $ready)

Say ""
Say "=== 5. THE PROCESSES THE APP IS (after) ==="
$after = @(Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match 'sotto_worker\.py|sotto_webview\.py' })
foreach ($q in $after) { Say ("pid={0} name={1} cmdlen={2}" -f $q.ProcessId, $q.Name, $q.CommandLine.Length) }

Say ""
Say "=== 6. THE LOG, FROM THE NEW BYTES ONLY ==="
if (Test-Path 'H:\sotto\_main\webview-run.log') {
  $fs = [System.IO.File]::Open('H:\sotto\_main\webview-run.log', 'Open', 'Read', 'ReadWrite')
  try {
    $fs.Seek($logLenBefore, 'Begin') | Out-Null
    $sr = New-Object System.IO.StreamReader($fs)
    $tail = $sr.ReadToEnd()
  } finally { $fs.Dispose() }
  $lines = $tail -split "`r?`n"
  Say ("new log bytes: {0}  lines: {1}" -f ($tail.Length), $lines.Count)
  foreach ($pat in @('WORKER_AUTOSTART', 'RECEIVER_READY', 'PANEL_VISIBILITY_AT_STARTUP',
                     'PAGE_ERROR', 'BRIDGE_NO_AUDIO_LIFTED', 'BRIDGE_SILENT_BENIGN',
                     'BRIDGE_CAPTION_SENT', 'BRIDGE_STATUS_ERROR', 'SINGLE_INSTANCE')) {
    $hit = @($lines | Where-Object { $_ -match $pat })
    Say ("  {0,-26} x{1}{2}" -f $pat, $hit.Count,
      $(if ($hit.Count) { '   e.g. ' + $hit[-1].Substring(0, [Math]::Min(150, $hit[-1].Length)) } else { '' }))
  }
} else { Say "no log file" }

$findings | Out-File -Encoding utf8 $log
