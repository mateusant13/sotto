# Does the sherpa CUDA arm ACTUALLY put work on the GPU?
#
# Runtime-independent instrument: nvidia-smi reports per-process GPU memory, so
# the question "was the GPU used" is answered by whether OUR pid ever appears in
# the compute-apps list -- not by what the code requested.
#
# Two arms, one command, because a census that only ever runs on the CUDA arm
# cannot tell "the GPU was used" from "this box always shows a GPU".
#   arm cuda : the sherpa CUDA run, watched per-pid
#   arm cpu  : the SAME run with --provider cpu, watched per-pid (negative control)
#
# Usage: pwsh -File _main\_diar-gpu-watch.ps1
param(
  [int]$CadenceMs = 150
)
$ErrorActionPreference = 'Stop'
$root = 'H:\sotto'
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'

function Watch-Arm {
  param([string]$Provider, [string]$Tag, [string]$Wav)
  $out  = "$root\_main\_diar-arm-$Tag.json"
  $errf = "$root\_main\_diar-gpuwatch-$Tag.err"
  $logf = "$root\_main\_diar-gpuwatch-$Tag.csv"
  $argv = @('_main\_diar-cuda-launch.py', '_main\_diar-run.py',
            '--wav', $Wav, '--threads', '2', '--threshold', '0.9',
            '--provider', $Provider, '--tag', $Tag, '--out', $out)
  $p = Start-Process -FilePath 'py' -ArgumentList (@('-3') + $argv) `
        -PassThru -WindowStyle Hidden -RedirectStandardError $errf `
        -RedirectStandardOutput "$root\_main\_diar-gpuwatch-$Tag.out"
  $samples = 0; $hits = 0; $maxMb = 0; $liveSamples = 0; $maxOtherPids = 0; $maxUtil = 0
  $rows = New-Object System.Collections.Generic.List[string]
  while (-not $p.HasExited) {
    $line = & nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>$null
    $util = (& nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>$null) -join ''
    $samples++
    # POSITIVE CONTROL for the absence claim: nvidia-smi must be RETURNING ROWS
    # while we look for our pid. A query that returns nothing would make "our pid
    # is absent" indistinguishable from "the instrument is dead".
    $allPids = @($line | Where-Object { $_ -match '^\s*\d+\s*,' })
    if ($allPids.Count -gt 0) { $liveSamples++ }
    if ($allPids.Count -gt $maxOtherPids) { $maxOtherPids = $allPids.Count }
    $u = 0; if ([int]::TryParse(($util -replace '[^0-9]', ''), [ref]$u)) { if ($u -gt $maxUtil) { $maxUtil = $u } }
    $mine = $allPids | Where-Object { $_ -match "^\s*$($p.Id)\s*," }
    if ($mine) {
      $hits++
      foreach ($m in $mine) {
        $mb = 0
        if ([int]::TryParse((($m -split ',')[1] -replace '[^0-9]', ''), [ref]$mb)) {
          if ($mb -gt $maxMb) { $maxMb = $mb }
        }
      }
    }
    $rows.Add(("{0}`t{1}`t{2}`t{3}`t{4}" -f $samples, $p.Id, $allPids.Count, $u, ($mine -join '|')))
    Start-Sleep -Milliseconds $CadenceMs
  }
  $p.WaitForExit()
  $rows | Set-Content -Path $logf -Encoding utf8
  $j = if (Test-Path $out) { Get-Content $out -Raw | ConvertFrom-Json } else { $null }
  [pscustomobject]@{
    arm = $Tag; provider = $Provider; pid = $p.Id; exit = $p.ExitCode
    samples = $samples
    instrument_live_samples = $liveSamples
    max_pids_in_compute_apps = $maxOtherPids
    max_gpu_util_pct = $maxUtil
    pid_in_compute_apps = $hits
    max_gpu_mem_mb = $maxMb
    wall_s = if ($j) { $j.wall_s } else { $null }
    rtf = if ($j) { $j.rtf } else { $null }
    n_speakers = if ($j) { $j.n_speakers } else { $null }
    rss_after_mb = if ($j) { $j.rss_after_mb } else { $null }
    log = $logf
  }
}

$res = @()
$res += Watch-Arm -Provider 'cuda' -Tag 'gpuwatch-cuda-ctrl' -Wav '_main\diar-models\0-four-speakers-zh.wav'
$res += Watch-Arm -Provider 'cpu'  -Tag 'gpuwatch-cpu-ctrl'  -Wav '_main\diar-models\0-four-speakers-zh.wav'

$res | Format-Table -AutoSize
$res | ConvertTo-Json -Depth 4 | Set-Content "$root\_main\_diar-gpu-watch.json" -Encoding utf8
Write-Host ""
Write-Host "GPU-WATCH verdict: cuda arm pid seen in compute-apps $($res[0].pid_in_compute_apps)/$($res[0].samples) samples, peak $($res[0].max_gpu_mem_mb) MB"
Write-Host "                   cpu  arm pid seen in compute-apps $($res[1].pid_in_compute_apps)/$($res[1].samples) samples, peak $($res[1].max_gpu_mem_mb) MB"
