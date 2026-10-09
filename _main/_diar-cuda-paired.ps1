# PAIRED, INTERLEAVED provider comparison -- because a cross-run comparison on this
# box is INVALID: the identical CPU arm measured RTF 0.2571 (wall 14.621 s) earlier
# and RTF 0.14 (wall 8.66 s) minutes later, same file, same flags. The owner's app
# and sibling lanes move the load by ~1.8x. Any "CUDA is N% faster" taken from two
# runs at different times is a measurement of the box's mood, not of the provider.
#
# Design: A/B/A/B/A/B interleaved (cuda, cpu, cuda, cpu, cuda, cpu) so that slow
# periods hit both providers. Report per-pair ratios, then the median ratio.
# The PTX cache is fully warm by now (43 files / 368.9 MB, both graphs JIT'd), so a
# CUDA arm that writes 0 new cache files is CONFIRMED fully warm -- that is the
# positive control that this is the warm comparison, not another JIT run.
param(
  [string]$Cache = '',
  [int]$Pairs = 3,
  [string]$Wav = 'H:\sotto\_main\diar-models\0-four-speakers-zh.wav',
  [string]$OutJson = 'H:\sotto\_main\_diar-cuda-paired.json',
  [string]$ArmPrefix = 'paired'
)
$ErrorActionPreference = 'Stop'
Set-Location H:\sotto
if (-not $Cache) {
  $Cache = (Get-ChildItem -LiteralPath 'H:\sotto\_main' -Directory -Filter '_diar-cuda-cache-*' |
            Sort-Object Name -Descending | Select-Object -First 1).FullName
}
if (-not $Cache -or -not (Test-Path -LiteralPath $Cache)) { throw "no warm cache dir found" }
"warm cache dir: $Cache"

function Get-CacheCensus([string]$dir) {
  $f = @(Get-ChildItem -LiteralPath $dir -Recurse -File -ErrorAction SilentlyContinue)
  [pscustomobject]@{ files = $f.Count; bytes = [long](($f | Measure-Object -Property Length -Sum).Sum) }
}
$c0 = Get-CacheCensus $Cache
"cache at start : files=$($c0.files) bytes=$($c0.bytes)"
$env:CUDA_CACHE_PATH = $Cache

$rows = @()
function Invoke-One([string]$tag, [string]$provider, [int]$i) {
  $out = "H:\sotto\_main\_diar-arm-$ArmPrefix-$tag-$i.json"
  $err = "H:\sotto\_main\_diar-arm-$ArmPrefix-$tag-$i.err"
  $b = Get-CacheCensus $Cache
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  & py -3 _main\_diar-cuda-launch.py _main\_diar-run.py `
      --wav $Wav `
      --threads 2 --threshold 0.9 --provider $provider `
      --tag "$ArmPrefix-$tag-$i" --out $out 1> $null 2> $err
  $rc = $LASTEXITCODE
  $sw.Stop()
  $a = Get-CacheCensus $Cache
  $j = $null
  if (Test-Path -LiteralPath $out) { $j = Get-Content -LiteralPath $out -Raw | ConvertFrom-Json }
  $row = [pscustomobject]@{
    i = $i; tag = $tag; provider = $provider; rc = $rc
    wall_s = [math]::Round($sw.Elapsed.TotalSeconds, 3)
    rtf = if ($j) { [math]::Round([double]$j.rtf, 4) } else { $null }
    cpu_s = if ($j) { [math]::Round([double]$j.cpu_s, 3) } else { $null }
    cpu_pct_1core = if ($j) { [math]::Round([double]$j.cpu_pct_of_one_core, 1) } else { $null }
    rss_after_mb = if ($j) { [math]::Round([double]$j.rss_after_mb, 1) } else { $null }
    n_seg = if ($j) { $j.n_segments } else { $null }
    n_spk = if ($j) { $j.n_speakers } else { $null }
    cache_new_files = $a.files - $b.files
    cache_new_bytes = $a.bytes - $b.bytes
  }
  $script:rows += $row
  $row
}

for ($i = 1; $i -le $Pairs; $i++) {
  Invoke-One 'cuda' 'cuda' $i | Out-Null
  Invoke-One 'cpu'  'cpu'  $i | Out-Null
}

$rows | Format-Table -AutoSize

"--- paired ratios (cuda RTF / cpu RTF); <1 means CUDA faster ---"
$ratios = @()
for ($i = 1; $i -le $Pairs; $i++) {
  $cu = ($rows | Where-Object { $_.i -eq $i -and $_.provider -eq 'cuda' }).rtf
  $cp = ($rows | Where-Object { $_.i -eq $i -and $_.provider -eq 'cpu' }).rtf
  if ($cu -and $cp) {
    $r = [math]::Round($cu / $cp, 4)
    $ratios += $r
    "pair $i : cuda $cu / cpu $cp = $r"
  }
}
if ($ratios.Count) {
  $sorted = $ratios | Sort-Object
  $med = if ($sorted.Count % 2) { $sorted[[int][math]::Floor($sorted.Count/2)] }
         else { [math]::Round((($sorted[$sorted.Count/2 - 1] + $sorted[$sorted.Count/2]) / 2), 4) }
  $spread = [math]::Round(($sorted[-1] - $sorted[0]), 4)
  "median cuda/cpu RTF ratio : $med"
  "spread across pairs       : $spread"
  "verdict: $(if ($spread -gt 0.25) { 'INCONCLUSIVE -- run-to-run spread exceeds any provider effect' } elseif ($med -lt 0.9) { 'CUDA faster' } elseif ($med -gt 1.1) { 'CUDA slower' } else { 'WASH -- within 10%' })"
}

$c1 = Get-CacheCensus $Cache
"cache at end   : files=$($c1.files) bytes=$($c1.bytes)"
"cuda arms wrote new cache files this run: $((($rows | Where-Object { $_.provider -eq 'cuda' }) | Measure-Object -Property cache_new_files -Sum).Sum)  (0 => fully warm, this IS the warm comparison)"
"cpu  arms wrote new cache files this run: $((($rows | Where-Object { $_.provider -eq 'cpu' }) | Measure-Object -Property cache_new_files -Sum).Sum)"
$rows | ConvertTo-Json -Depth 4 | Out-File -Encoding utf8 $OutJson
