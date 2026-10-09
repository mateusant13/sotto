# The OWNER'S RUNNING worker's CURRENT rate — the actual subject of "it's not in real time".
#
# A fresh arm is not the subject. pid 29008 started 2026-10-07 08:01:56; the disk file is
# 8 h 54 min newer, so "what the file can do" and "what his process is doing" are different
# claims. This measures HIS process, live, without touching it.
#
# Instrument: _main/panel-state.json is rewritten by the shell every ~6 s and carries the
# worker's own CUMULATIVE counters. Two snapshots T seconds apart, differenced.
#   RTF        = d(infer_wall_s) / d(audio_s)
#   captions   delta says whether real speech actually flowed: in a silent window the RTF
#              is meaningless, so the count is reported next to it either way.
#   queue_drops delta is the panel's own lag sentence (`panel.js:2100/2114`): non-zero means
#              the decoder really is behind and captions ARE lagging the speaker.
$ErrorActionPreference = 'Stop'
$T = 45

function Get-Snap {
    $j = Get-Content 'H:\sotto\_main\panel-state.json' -Raw | ConvertFrom-Json
    $w = $j.worker
    $s = if ($w.workerStatsCurrent) { $w.workerStatsCurrent } else { $w.workerStats }
    [pscustomobject]@{
        at        = (Get-Date -Format 'HH:mm:ss')
        pid       = $w.childPid
        state     = $w.state
        capturing = $w.capturing
        spawns    = $w.spawns
        deaths    = $w.deaths
        captions  = $w.captions
        chunks    = $s.chunks
        audio_s   = $s.audio_s
        infer     = $s.infer_wall_s
        tokens    = $s.tokens
        frames    = $s.frames
        drops     = $s.queue_drops
        rss       = $s.rss_mb
        kept      = $s.gate_kept
        music     = $s.music_gated_chunks
        vad       = $s.vad_gated_chunks
    }
}

$a = Get-Snap
Start-Sleep -Seconds $T
$b = Get-Snap

'A = ' + ($a | ConvertTo-Json -Compress)
'B = ' + ($b | ConvertTo-Json -Compress)

$dAudio = [double]$b.audio_s - [double]$a.audio_s
$dInfer = [double]$b.infer - [double]$a.infer
$dCap   = [int]$b.captions - [int]$a.captions
$dChunk = [int]$b.chunks - [int]$a.chunks
$dDrop  = [int]$b.drops - [int]$a.drops

"WINDOW_S=$T"
"DELTA audio_s=$([math]::Round($dAudio,2)) infer_wall_s=$([math]::Round($dInfer,3)) chunks=$dChunk captions=$dCap queue_drops=$dDrop"
if ($dAudio -gt 0) {
    "RUNNING_RTF=$([math]::Round($dInfer / $dAudio, 4))"
    "HEADROOM_X=$([math]::Round($dAudio / [math]::Max($dInfer, 0.000001), 2))  (audio seconds decoded per second of compute)"
} else {
    'RUNNING_RTF=undefined (no audio advanced in this window)'
}
"SUBJECT_WORKINGSET_MB=132.7  SUBJECT_PRIVATE_MB=7304.4  FRESH_CONTROL_WORKINGSET_MB=2416.6  FRESH_CONTROL_PRIVATE_MB=4962.6"
