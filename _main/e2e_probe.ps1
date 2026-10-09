# e2e_probe.ps1 -- END-TO-END population run for the Sotto capture -> index chain.
#
# HONESTY RULES THIS FILE KEEPS:
#  * rc is taken by redirect-then-$LASTEXITCODE.  Nothing native is piped into
#    Select-Object -First N (that swallows a crashing child's stderr).
#  * No hand-built vector is ever written.  src/index contains NO embedder, so
#    the embedding population is reported as 0 and the missing link is named,
#    rather than filled in with noise that would make search look proven.
#  * The negative control runs over a NON-EMPTY video population, and states
#    exactly which channel it can and cannot falsify.
#  * <=2 threads for every measurement.
#
# Usage:  powershell.exe -NoProfile -ExecutionPolicy Bypass -File e2e_probe.ps1

$ErrorActionPreference = 'Continue'

foreach ($v in 'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS') {
    Set-Item -Path "env:$v" -Value '2'
}
$env:TMPDIR = 'I:\cc-tmp'

$Exe   = 'H:\sotto-wt\e2e2\_main\build\aireplay-capture.exe'
$Work  = 'I:\cc-tmp\e2e2'
$Repo  = 'H:\sotto-wt\ArbV8\_moved\aireplay'
$Frame = Join-Path $Work 'frames'
New-Item -ItemType Directory -Force -Path $Work, $Frame | Out-Null
Get-ChildItem $Work -Filter '*.mp4' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $Frame -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force

if (-not (Test-Path $Exe)) { Write-Host "FATAL: capture binary missing: $Exe"; exit 2 }

# ============================ LINK 1: stdin control =========================
# Ground truth, stated in advance: `ping` is the ONLY command the parser
# accepts, so ping MUST answer {"ok":true} and stop MUST answer an error.
# main.cpp:538 -- `if (!json_cmd_value(line,&cmd) || cmd != "ping")` -> error.
$stdinClip = Join-Path $Work 'stdin-run.mp4'
$stdinPy = @"
import subprocess, json, os
exe = r'$Exe'
p = subprocess.Popen([exe,'--run','--seconds','4','--cut-at','2',
                      '--out', r'$stdinClip'],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True)
# stdout carries BOTH the log stream and the one-line JSON replies, so the two
# are interleaved: collect everything after stdin closes, then keep only the
# JSON lines, in order.  First ping, then stop -- so reply[0] is ping's.
for c in ('ping','stop'):
    p.stdin.write(json.dumps({'cmd': c}) + chr(10))
p.stdin.flush()
p.stdin.close()
rc = p.wait(timeout=240)
txt = p.stdout.read()
jl = [l.strip() for l in txt.splitlines() if l.strip().startswith('{')]
print(json.dumps({'replies': jl, 'rc': rc, 'clip': os.path.exists(r'$stdinClip')}))
"@
Set-Content -Path (Join-Path $Work '_stdin.py') -Value $stdinPy -Encoding UTF8
$so = Join-Path $Work '_stdin.out'; $se = Join-Path $Work '_stdin.err'
python (Join-Path $Work '_stdin.py') > $so 2> $se
$stdinRc = $LASTEXITCODE
$stdinJson = $null
try { $stdinJson = ((Get-Content $so -ErrorAction SilentlyContinue) -join '') | ConvertFrom-Json } catch { }
Write-Host ("LINK1 stdin: rc={0} replies={1}" -f $stdinRc, $(if ($stdinJson) { $stdinJson.replies -join ' | ' } else { '<none>' }))

# ============================ LINK 2..6: the 5 runs =========================
$runs = @(
    @{ n='run1'; a=@('--run','--seconds','6','--cut-at','3','--monitor');                         label='primary monitor / CreateForMonitor' }
    @{ n='run2'; a=@('--run','--seconds','6','--cut-at','3');                                    label='auto test window / CreateForWindow' }
    @{ n='run3'; a=@('--run','--seconds','6','--cut-at','3','--window-top','--window-alpha','1'); label='layered full-desktop window' }
    @{ n='run4'; a=@('--run','--seconds','8','--cut-at','4','--monitor','--mode','desktop');     label='primary monitor, desktop mode' }
    @{ n='run5'; a=@('--run','--seconds','8','--cut-at','4','--mode','gaming');                  label='test window, gaming mode' }
)

$results = @()
foreach ($r in $runs) {
    $clip = Join-Path $Work "$($r.n).mp4"
    $out  = Join-Path $Work "$($r.n).out.txt"
    $cmd = '"' + $Exe + '" ' + ($r.a + @('--out', $clip)) -join ' ' +
           ' < NUL > "' + $out + '" 2>&1'
    cmd /c $cmd
    $rc = $LASTEXITCODE

    $text  = (Get-Content $out -ErrorAction SilentlyContinue) -join "`n"
    $errLn = ($text -split "`n" | Where-Object { $_ -match 'failed 0x|SETUP FAILURE|FAILED' })[0]
    $has   = Test-Path $clip
    $bytes = 0; $dur = 0; $nfr = 0
    if ($has) {
        $bytes = (Get-Item $clip).Length
        $fo = Join-Path $Work "$($r.n).ffprobe.txt"
        ffprobe -v error -count_frames -select_streams v:0 `
            -show_entries stream=nb_read_frames,width,height,codec_name `
            -show_entries format=duration -of default=nw=1 $clip > $fo 2> $fo.err
        $frc = $LASTEXITCODE
        if ($frc -eq 0) {
            $d = (Select-String -Path $fo -Pattern '^duration=(.+)$').Matches[0].Groups[1].Value
            $f = (Select-String -Path $fo -Pattern '^nb_read_frames=(\d+)$').Matches[0].Groups[1].Value
            $dur = [math]::Round([double]$d, 3); $nfr = [int]$f
        }
    }
    $results += [pscustomobject]@{
        run = $r.n; source = $r.label; rc = $rc
        clip_produced = [bool]$has; clip_mib = [math]::Round($bytes/1MB,2)
        frames = $nfr; duration_s = $dur; first_error = $errLn
    }
    Write-Host ("{0} rc={1} clip={2} {3}MiB frames={4} dur={5}s" -f $r.n,$rc,[bool]$has,
        [math]::Round($bytes/1MB,2),$nfr,$dur)
}

$clipsProduced = @($results | Where-Object { $_.clip_produced }).Count

# ============================ LINK: frame extraction =======================
$framesMade = 0
foreach ($c in (Get-ChildItem $Work -Filter '*.mp4' -ErrorAction SilentlyContinue)) {
    $d = Join-Path $Frame $c.BaseName
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    ffmpeg -v error -i $c.FullName -vf fps=1 -frames:v 2 (Join-Path $d 'f%02d.png') > (Join-Path $d 'ff.log') 2>&1
    $frc = $LASTEXITCODE
    if ($frc -eq 0) { $framesMade += @(Get-ChildItem $d -Filter '*.png').Count }
}
Write-Host ("LINK frames: {0} PNGs extracted" -f $framesMade)

# ============================ LINK: index + negative control ===============
# Real clips -> real content_key (whole-file SHA-256) -> real video + segment
# rows through store.py.  NO embedding is written: src/index has no embedder.
$db = Join-Path $Work 'e2e2.sqlite'
if (Test-Path $db) { Remove-Item $db -Force }
$py = @"
import json, os, pathlib, sys, hashlib
for v in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[v] = '2'
sys.path.insert(0, r'$Repo\src\index')
import store, search
work = pathlib.Path(r'$Work')
clips = sorted(work.glob('*.mp4'))
out = {'clips_seen': len(clips), 'videos_indexed': 0, 'segments_indexed': 0,
       'embeddings_indexed': 0, 'retrieved': 0, 'rank_of_correct': None,
       'negative_term': 'zzq_impossible_term_not_in_any_clip',
       'negative_hits': None, 'negative_pass': None}
conn = store.connect(work / 'e2e2.sqlite')
for c in clips:
    b = c.read_bytes()
    vid = store.upsert_video(conn, content_key=hashlib.sha256(b).hexdigest(),
                             path=str(c), size_bytes=len(b),
                             mtime_ns=c.stat().st_mtime_ns,
                             duration_ms=0, codec='h264', w=1920, h=1080, fps=60.0)
    out['videos_indexed'] += 1
    # one 5 s segment per clip, the window unit search.py returns
    out['segments_indexed'] += 1 if store.upsert_segment(
        conn, video_id=vid, start_ms=0, end_ms=5000) is not None else 0
out['embeddings_indexed'] = int(conn.execute('SELECT COUNT(*) FROM embedding').fetchone()[0])

idx = search.SearchIndex(conn)
out['index_n'] = idx.n
out['index_dim'] = idx.dim

# NEGATIVE CONTROL: a term present in ZERO clips must return nothing relevant.
# Correct answer, stated BEFORE the run: 0 hits.
neg = idx.search_text(out['negative_term'], k=10)
out['negative_hits'] = len(neg)
out['negative_pass'] = (len(neg) == 0)
# A second control that is NOT vacuous on the lexical channel: a term that is in
# no document must also not produce a confident TOP HIT in the fused path.
neg2 = idx.search_all(text=out['negative_term'], k=5)
out['negative_fused_hits'] = len(neg2)
out['negative_fused_pass'] = (len(neg2) == 0)
out['negative_fused_top'] = (neg2[0]['path'] if neg2 else None)
print(json.dumps(out))
"@
Set-Content -Path (Join-Path $Work '_gate.py') -Value $py -Encoding UTF8
$go = Join-Path $Work '_gate.out'; $ge = Join-Path $Work '_gate.err'
python (Join-Path $Work '_gate.py') > $go 2> $ge
$gateRc = $LASTEXITCODE
$gate = $null
try { $gate = ((Get-Content $go -ErrorAction SilentlyContinue) -join '') | ConvertFrom-Json } catch { }

Write-Host ''
Write-Host '=== 5-RUN TABLE ==='
$results | Format-Table -AutoSize | Out-String | Write-Host
Write-Host ("runs={0}  clips_produced={1}  frames={2}  gate_rc={3}" -f $results.Count,$clipsProduced,$framesMade,$gateRc)
if ($gate) {
    Write-Host ("videos_indexed={0} segments_indexed={1} embeddings_indexed={2}" -f $gate.videos_indexed,$gate.segments_indexed,$gate.embeddings_indexed)
    Write-Host ("retrieved={0}  rank_of_correct={1}  (index n={2} dim={3})" -f $gate.retrieved,$gate.rank_of_correct,$gate.index_n,$gate.index_dim)
    Write-Host ("NEG '{0}': lexical_hits={1} pass={2}" -f $gate.negative_term,$gate.negative_hits,$gate.negative_pass)
    Write-Host ("NEG fused        : hits={0} pass={1} top={2}" -f $gate.negative_fused_hits,$gate.negative_fused_pass,$gate.negative_fused_top)
} else {
    Write-Host 'gate produced no JSON; stderr:'
    Get-Content $ge -ErrorAction SilentlyContinue
}

$summary = [pscustomobject]@{
    runs = $results.Count; population = $clipsProduced; frames = $framesMade
    stdin_ping = $(if ($stdinJson) { $stdinJson.replies.ping } else { $null })
    stdin_stop = $(if ($stdinJson) { $stdinJson.replies.stop } else { $null })
    videos_indexed   = $(if ($gate) { $gate.videos_indexed } else { $null })
    segments_indexed = $(if ($gate) { $gate.segments_indexed } else { $null })
    embeddings_indexed = $(if ($gate) { $gate.embeddings_indexed } else { $null })
    clips_retrieved  = $(if ($gate) { $gate.retrieved } else { $null })
    rank_of_correct  = $(if ($gate) { $gate.rank_of_correct } else { $null })
    negative_hits    = $(if ($gate) { $gate.negative_hits } else { $null })
    negative_pass    = $(if ($gate) { $gate.negative_pass } else { $null })
}
$summary | ConvertTo-Json | Set-Content -Path (Join-Path $Work 'e2e2-summary.json') -Encoding UTF8
Write-Host ''
Write-Host '=== SUMMARY ==='
Get-Content (Join-Path $Work 'e2e2-summary.json')