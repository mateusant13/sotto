# The RUNNING worker's own cumulative counters, read twice T seconds apart, differenced.
#
# panel-state.json publishes workerStats/workerStatsCurrent as null on this shell revision, so the
# rate has to come from the worker's own tick lines that the shell relays into the log. Those lines
# carry CUMULATIVE totals (audio_s, infer_wall_s, chunks, tokens, queue_drops), which is exactly what
# makes a difference of two samples meaningful. The log has NO timestamps, so the sample distance is
# the sleep, not a parsed field.
$ErrorActionPreference = 'Stop'
$log = 'H:\sotto\_main\webview-run.log'
$T = 60

function Get-LastStats {
    # One pass over the whole file, keep only stats-bearing lines, take the last.
    $m = Select-String -Path $log -Pattern 'infer_wall_s=' -SimpleMatch:$false |
         Select-Object -Last 1
    if (-not $m) { return $null }
    $m.Line
}

$a = Get-LastStats
Start-Sleep -Seconds $T
$b = Get-LastStats

'--- A ---'; $a
'--- B ---'; $b

function Field($line, $name) {
    if (-not $line) { return $null }
    $mm = [regex]::Match($line, "$name=([-0-9.]+)")
    if ($mm.Success) { return [double]$mm.Groups[1].Value }
    return $null
}

$names = @('audio_s', 'infer_wall_s', 'chunks', 'captions', 'tokens', 'frames', 'queue_drops', 'rss_mb', 'gate_kept')
$da = Field $a 'audio_s'; $db = Field $b 'audio_s'
$ia = Field $a 'infer_wall_s'; $ib = Field $b 'infer_wall_s'
$ca = Field $a 'captions'; $cb = Field $b 'captions'

if ($null -eq $da -or $null -eq $db) {
    'VERDICT: no cumulative stats line found in the log'
    exit 0
}

$dAudio = $db - $da
$dInfer = $ib - $ia
"WINDOW_S=$T"
"DELTA audio_s=$([math]::Round($dAudio,2)) infer_wall_s=$([math]::Round($dInfer,3)) captions=$($cb-$ca)"
if ($dAudio -gt 0) {
    "RUNNING_RTF=$([math]::Round($dInfer / $dAudio, 4))"
    if ($dInfer -gt 0) { "HEADROOM_X=$([math]::Round($dAudio / $dInfer, 2))" }
} else {
    'RUNNING_RTF=undefined (no audio advanced between the two samples)'
}
