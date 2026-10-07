# _gpu-watch.ps1 - sample ONE process's own dedicated VRAM for a bounded time.
#
# Why this exists: on this Windows/WDDM box `nvidia-smi --query-compute-apps` lists the pids but
# reports `used_gpu_memory [MiB] = [N/A]` for every one of them (measured), so it can prove a child
# holds a CUDA context and cannot say how much it holds. The whole-GPU `memory.used` does move, but
# it also moves with every other program the owner is running. The GPU Process Memory perf counters
# DO carry the per-process number, and this is the smallest thing that reads them.
#
# It writes each sample as it goes, because the caller kills it as soon as the child exits: a file
# written only at the end of the loop never survives (measured -- the first version lost the data).
param(
  [Parameter(Mandatory = $true)][int]$TargetPid,
  [Parameter(Mandatory = $true)][int]$Seconds,
  [Parameter(Mandatory = $true)][string]$Out,
  [int]$IntervalMs = 2000
)
$deadline = (Get-Date).AddSeconds($Seconds)
$max = 0
$sw = New-Object System.IO.StreamWriter($Out, $false)
$sw.AutoFlush = $true
$sw.WriteLine("pid={0} interval_ms={1}" -f $TargetPid, $IntervalMs)
while ((Get-Date) -lt $deadline) {
  $now = 0
  try {
    $samples = (Get-Counter "\GPU Process Memory(pid_${TargetPid}_*)\Dedicated Usage" -ErrorAction Stop).CounterSamples
    foreach ($s in $samples) {
      if ($s.CookedValue -gt $now) { $now = $s.CookedValue }
    }
  } catch { }
  if ($now -gt $max) { $max = $now }
  # CookedValue is bytes; MiB is what the rest of the receipt speaks.
  $sw.WriteLine("{0},{1},{2}" -f (Get-Date -Format 'HH:mm:ss.fff'), [math]::Round($now / 1MB, 1), [math]::Round($max / 1MB, 1))
  Start-Sleep -Milliseconds $IntervalMs
}
$sw.WriteLine("max_mib={0}" -f [math]::Round($max / 1MB, 1))
$sw.Close()
