# _main/_lat-worker-memory.ps1 -- is the live worker's model actually IN RAM, or is it
# being trimmed and re-faulted from disk between chunks? Read-only; kills nothing.
#
# WHY THIS IS THE QUESTION: the log's own stats say the decode runs ~30x faster than
# real time, but the running worker's WorkingSet64 is only ~129 MB. A loaded
# nemotron int8 encoder alone is ~1.0 GB on disk. If the pages were trimmed, every
# 560 ms chunk would pay a disk re-read, and THAT would look exactly like "not in
# real time" while every counter in the JSONL still reported a healthy run.

$ErrorActionPreference = 'Continue'

$p = Get-Process -Id 29008 -ErrorAction SilentlyContinue
if (-not $p) { "pid 29008 is GONE -- the answer must be re-measured"; exit 0 }

"pid 29008  name=$($p.ProcessName)  started=$($p.StartTime.ToString('yyyy-MM-dd HH:mm:ss'))"
""
"--- memory, two ways (WorkingSet is TRIMMABLE; PrivateMemory is what the process owns) ---"
"WorkingSet64        {0,10:N1} MB" -f ($p.WorkingSet64/1MB)
"PrivateMemorySize64 {0,10:N1} MB" -f ($p.PrivateMemorySize64/1MB)
"PagedMemorySize64   {0,10:N1} MB" -f ($p.PagedMemorySize64/1MB)
"VirtualMemorySize64 {0,10:N1} MB" -f ($p.VirtualMemorySize64/1MB)
""
"--- is it WORKING? a 3 s delta: CPU and hard page faults ---"
$c0 = $p.CPU
$pf0 = (Get-CimInstance Win32_Process -Filter "ProcessId=29008").PageFaults
Start-Sleep -Seconds 3
$p2 = Get-Process -Id 29008
$pf1 = (Get-CimInstance Win32_Process -Filter "ProcessId=29008").PageFaults
$dcpu = $p2.CPU - $c0
"cpu_delta_s      {0,10:N2}  ({1:N1} % of one core over 3 s)" -f $dcpu, (100*$dcpu/3)
"pagefaults_delta {0,10}" -f ($pf1 - $pf0)
"ws_after_MB      {0,10:N1}" -f ($p2.WorkingSet64/1MB)
""
"--- system memory pressure (why trimming would happen at all) ---"
$os = Get-CimInstance Win32_OperatingSystem
"total_visible_MB {0,10:N0}" -f ($os.TotalVisibleMemorySize/1KB)
"free_physical_MB {0,10:N0}" -f ($os.FreePhysicalMemory/1KB)
"commit_limit_MB  {0,10:N0}" -f ($os.TotalVirtualMemorySize/1KB)
"commit_free_MB   {0,10:N0}" -f ($os.FreeVirtualMemory/1KB)
""
"--- top 8 processes by WorkingSet (who is holding the RAM) ---"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 8 |
    ForEach-Object { '{0,-22} {1,6}  {2,10:N1} MB' -f $_.ProcessName, $_.Id, ($_.WorkingSet64/1MB) }
