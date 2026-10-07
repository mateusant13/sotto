# e2e_probe.ps1 -- END-TO-END population run for the Sotto capture->index chain.
#
# SCOPE: drive the REAL capture binary 5 times, record every rc and every clip,
# then run the search gate's NEGATIVE control against whatever population came
# out.  Nothing here fabricates media or vectors: if the capture produces no
# clip, this script reports zero clips and says the negative control is VACUOUS.
#
# House rule honoured: rc is taken by redirect-then-$LASTEXITCODE.  Nothing is
# piped into Select-Object -First N (that swallows a crashing child's stderr).
# Measurements run single-threaded / <=2 threads.
#
# Usage:  powershell.exe -NoProfile -ExecutionPolicy Bypass -File e2e_probe.ps1

$ErrorActionPreference = 'Continue'

# ---- 2-thread budget, set before anything numeric loads --------------------
foreach ($v in 'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS') {
    Set-Item -Path "env:$v" -Value '2'
}
$env:TMPDIR = 'I:\cc-tmp'

$Exe     = 'H:\aireplay\_main\build\aireplay-capture.exe'
$Work    = 'I:\cc-tmp\e2e2'
$Repo    = 'H:\sotto-wt\ArbV8\_moved\aireplay'
New-Item -ItemType Directory -Force -Path $Work | Out-Null

if (-not (Test-Path $Exe)) { Write-Host "FATAL: capture binary missing: $Exe"; exit 2 }

# ---- the 5 runs -----------------------------------------------------------
# Varied on the SOURCE and the MODE only.  Every one of them is a real
# end-to-end attempt through the shipped capture path.
$runs = @(
    @{ n='run1'; a=@('--run','--seconds','6','--cut-at','3','--monitor');                    label='primary monitor (WGC CreateForMonitor)' }
    @{ n='run2'; a=@('--run','--seconds','6','--cut-at','3');                               label='auto test window (WGC CreateForWindow)' }
    @{ n='run3'; a=@('--run','--seconds','6','--cut-at','3','--window-top','--window-alpha','1'); label='layered full-desktop test window' }
    @{ n='run4'; a=@('--run','--seconds','8','--cut-at','4','--monitor','--mode','desktop'); label='primary monitor, desktop mode' }
    @{ n='run5'; a=@('--run','--seconds','8','--cut-at','4','--mode','gaming','--inject-fault','none'); label='test window, gaming mode, no fault' }
)

$results = @()
foreach ($r in $runs) {
    $clip = Join-Path $Work "$($r.n).mp4"
    $out  = Join-Path $Work "$($r.n).out.txt"
    $log  = Join-Path $Work "$($r.n).log.txt"
    if (Test-Path $clip) { Remove-Item $clip -Force }

    $argline = ($r.a + @('--out', $clip, '--log', $log)) -join ' '
    # stdin redirected from NUL so the stdin-control loop sees a closed pipe and
    # the run proceeds; this is how a detached host starts it.
    $cmd = '"' + $Exe + '" ' + $argline + ' < NUL > "' + $out + '" 2>&1'
    cmd /c $cmd
    $rc = $LASTEXITCODE

    $text = (Get-Content $out -ErrorAction SilentlyContinue) -join "`n"
    # The exact first broken-link line, verbatim, no paraphrase.
    $errLine = ($text -split "`n" |
                Where-Object { $_ -match 'SETUP FAILURE|failed 0x|FAILED|LAW 6|ARMED' } |
                Select-Object -First 1)
    $clipExists = Test-Path $clip
    $clipLen = 0
    if ($clipExists) { $clipLen = (Get-Item $clip).Length }

    $results += [pscustomobject]@{
        run           = $r.n
        source        = $r.label
        rc            = $rc
        clip_produced = [bool]$clipExists
        clip_bytes    = $clipLen
        first_error   = $errLine
    }
    Write-Host ("{0}  rc={1}  clip={2} ({3} bytes)  {4}" -f $r.n, $rc, $clipExists, $clipLen, $errLine)
}

$clipsProduced = @($results | Where-Object { $_.clip_produced }).Count

# ---- the index half --------------------------------------------------------
# Reached ONLY with real clips.  With zero clips the gate below is VACUOUS and
# is labelled as such rather than being reported as a pass.
$db = Join-Path $Work 'e2e2.sqlite'
if (Test-Path $db) { Remove-Item $db -Force }
$py = @"
import json, os, pathlib, sys
for v in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[v] = '2'
sys.path.insert(0, r'$Repo\src\index')
import store, search
db = pathlib.Path(r'$db')
conn = store.connect(db)
clips = list(pathlib.Path(r'$Work').glob('*.mp4'))
out = {'clips_seen': len(clips), 'clips_indexed': 0, 'retrieved': 0,
       'rank_of_correct': None, 'vacuous': len(clips) == 0}
if clips:
    for c in clips:
        key = __import__('hashlib').sha256(c.read_bytes()).hexdigest()
        vid = store.upsert_video(conn, content_key=key, path=str(c),
                                 size_bytes=c.stat().st_size,
                                 mtime_ns=c.stat().st_mtime_ns, duration_ms=0)
        store.upsert_segment(conn, video_id=vid, start_ms=0, end_ms=5000)
        out['clips_indexed'] += 1
# NEGATIVE CONTROL: a term present in ZERO clips must return nothing relevant.
idx = search.SearchIndex(conn)
neg = idx.search_text('zzq_impossible_term_not_in_any_clip', k=10)
out['negative_control_hits'] = len(neg)
out['negative_control_pass'] = (len(neg) == 0)
print(json.dumps(out))
"@
$pyFile = Join-Path $Work '_neg.py'
Set-Content -Path $pyFile -Value $py -Encoding UTF8
$pyOut = Join-Path $Work '_neg.out.txt'
$pyErr = Join-Path $Work '_neg.err.txt'
python $pyFile > $pyOut 2> $pyErr
$pyRc = $LASTEXITCODE
$negRaw = (Get-Content $pyOut -ErrorAction SilentlyContinue) -join ''
$neg = $null
try { $neg = $negRaw | ConvertFrom-Json } catch { $neg = $null }

Write-Host ''
Write-Host '=== 5-RUN TABLE ==='
$results | Format-Table -AutoSize | Out-String | Write-Host
Write-Host ("clips produced : {0}/5" -f $clipsProduced)
Write-Host ("python gate rc : {0}" -f $pyRc)
if ($neg) {
    Write-Host ("clips indexed  : {0}" -f $neg.clips_indexed)
    Write-Host ("clips retrieved: {0}" -f $neg.retrieved)
    Write-Host ("rank correct   : {0}" -f $neg.rank_of_correct)
    Write-Host ("NEG control    : hits={0} pass={1} VACUOUS={2}" -f `
        $neg.negative_control_hits, $neg.negative_control_pass, $neg.vacuous)
} else {
    Write-Host ("index gate did not emit JSON. stderr:")
    Write-Host (Get-Content $pyErr -ErrorAction SilentlyContinue)
}

$summary = [pscustomobject]@{
    runs             = $results.Count
    clips_produced   = $clipsProduced
    clips_indexed    = if ($neg) { $neg.clips_indexed } else { $null }
    clips_retrieved  = if ($neg) { $neg.retrieved } else { $null }
    rank_of_correct  = if ($neg) { $neg.rank_of_correct } else { $null }
    negative_hits    = if ($neg) { $neg.negative_control_hits } else { $null }
    negative_pass    = if ($neg) { $neg.negative_control_pass } else { $null }
    negative_vacuous = if ($neg) { $neg.vacuous } else { $null }
    population       = $clipsProduced
}
$summary | ConvertTo-Json | Set-Content -Path (Join-Path $Work 'e2e2-summary.json') -Encoding UTF8
Write-Host ''
Write-Host '=== SUMMARY JSON ==='
Get-Content (Join-Path $Work 'e2e2-summary.json')