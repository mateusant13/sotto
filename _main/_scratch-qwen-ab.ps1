# SCRATCH head-to-head driver. Deleted after the receipt quotes it.
# Runs each arm on each window as a SEPARATE process (per-run peak RSS is a process fact),
# below-normal priority (the shipped default), --force so the cache never serves one model's
# text as another's, and captures the one JSON line per run.
$ErrorActionPreference = 'Continue'
$root = 'H:\sotto'
$arm1 = 'worker\models\qwen3.5-0.8b-ortgenai-cpu'
$arm2 = 'worker\models\qwen3-0.6b-arm-int4'

$runs = @(
  @{tag='arm1_0.8b_hour16';      dir=$arm1; args=@('--hour','2026-10-06T16')},
  @{tag='arm1_0.8b_win16_1640';  dir=$arm1; args=@('--from','2026-10-06T16:00','--to','2026-10-06T16:40')},
  @{tag='arm2_0.6b_hour16';      dir=$arm2; args=@('--hour','2026-10-06T16')},
  @{tag='arm2_0.6b_win16_1640';  dir=$arm2; args=@('--from','2026-10-06T16:00','--to','2026-10-06T16:40')},
  @{tag='arm1_0.8b_hour16_DETERMINISM_REPEAT'; dir=$arm1; args=@('--hour','2026-10-06T16')}
)

foreach ($r in $runs) {
  $log = Join-Path $root ("_main\_scratch-qwen-" + $r.tag + ".jsonl")
  Write-Output ("=== " + $r.tag + "  ->  " + $log)
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  & py -3 (Join-Path $root 'worker\qwen_summary.py') @($r.args) --model-dir (Join-Path $root $r.dir) --json --force --max-seconds 600 *> $log
  $rc = $LASTEXITCODE
  $sw.Stop()
  Write-Output ("    rc=" + $rc + "  wall=" + [math]::Round($sw.Elapsed.TotalSeconds,1) + "s")
  Get-Content -LiteralPath $log -Encoding UTF8 | Select-Object -Last 1
}
Write-Output '=== done'
