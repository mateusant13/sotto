# Launch a measurement process HIDDEN and census its windows at 25 ms while it runs.
# House rule: never leave a visible window; the 60 s governor cannot prove absence,
# so this samples at its own cadence. The census names a PID, never a bare word.
param(
  [Parameter(Mandatory=$true)][string[]]$ProbeArgs,
  [string]$Tag = "probe",
  [string]$LogDir = "H:\aireplay\_main",
  [int]$SampleMs = 25
)

$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class WinCensus {
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowTextW(IntPtr hWnd, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassNameW(IntPtr hWnd, StringBuilder s, int n);
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    public static List<string> VisibleFor(HashSet<uint> pids) {
        var found = new List<string>();
        EnumWindows((h, l) => {
            if (!IsWindowVisible(h)) return true;
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (pids.Contains(pid)) {
                var t = new StringBuilder(256); GetWindowTextW(h, t, 256);
                var c = new StringBuilder(256); GetClassNameW(h, c, 256);
                found.Add(pid + "|" + h.ToInt64() + "|" + t.ToString() + "|" + c.ToString());
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
"@

$exe = "C:\Program Files\Python311\pythonw.exe"
$proc = Start-Process -FilePath $exe -ArgumentList $ProbeArgs -WindowStyle Hidden -PassThru
$t0 = Get-Date
$samples = 0
$visible = 0
$longest = 0.0
$lastVisibleStart = $null
$named = New-Object System.Collections.Generic.List[string]
$pids = New-Object 'System.Collections.Generic.HashSet[uint32]'
[void]$pids.Add([uint32]$proc.Id)
# Independent second instrument: an OUTSIDE process reading the probe's own working set.
# The probe also samples itself in-process; two instruments, one subject.
$wsRows = New-Object System.Collections.Generic.List[string]
$sw = [System.Diagnostics.Stopwatch]::StartNew()

while (-not $proc.HasExited) {
  # keep the tracked set current: any child of the probe counts as its window.
  # The child walk is a CIM query (~100 ms), so it runs once every ~1 s, NOT every sample:
  # the 25 ms cadence must stay fast enough to catch a window that lives a few frames.
  if ($samples % 40 -eq 0) {
    try {
      Get-CimInstance Win32_Process -Filter "ParentProcessId=$($proc.Id)" -ErrorAction SilentlyContinue |
        ForEach-Object { [void]$pids.Add([uint32]$_.ProcessId) }
    } catch { }
  }
  $found = [WinCensus]::VisibleFor($pids)
  try {
    $pr = Get-Process -Id $proc.Id -ErrorAction Stop
    $wsRows.Add(("{0:F3},{1:F1},{2:F1}" -f $sw.Elapsed.TotalSeconds, ($pr.WorkingSet64/1MB), ($pr.PeakWorkingSet64/1MB)))
  } catch { }
  $samples++
  if ($found.Count -gt 0) {
    $visible++
    if ($null -eq $lastVisibleStart) { $lastVisibleStart = Get-Date }
    $found | ForEach-Object { if ($named.Count -lt 20) { $named.Add($_) } }
  } else {
    if ($null -ne $lastVisibleStart) {
      $d = ((Get-Date) - $lastVisibleStart).TotalMilliseconds / 1000.0
      if ($d -gt $longest) { $longest = $d }
      $lastVisibleStart = $null
    }
  }
  Start-Sleep -Milliseconds $SampleMs
}
if ($null -ne $lastVisibleStart) {
  $d = ((Get-Date) - $lastVisibleStart).TotalMilliseconds / 1000.0
  if ($d -gt $longest) { $longest = $d }
}

$wall = ((Get-Date) - $t0).TotalSeconds
$wsPath = Join-Path $LogDir "onnx-asr-external-ws-$Tag.csv"
"t_s,ws_mb,peak_ws_mb" | Out-File -FilePath $wsPath -Encoding ascii
$wsRows | Out-File -FilePath $wsPath -Encoding ascii -Append
$line = "TAG=$Tag pid=$($proc.Id) rc=$($proc.ExitCode) wall=$([math]::Round($wall,2))s samples=$samples effective_cadence_ms=$([math]::Round(1000*$wall/[math]::Max($samples,1),1)) visible_samples=$visible longest_visible_s=$([math]::Round($longest,3)) tracked_pids=$($pids.Count)"
$line | Out-File -FilePath (Join-Path $LogDir "onnx-asr-census-$Tag.txt") -Encoding utf8
Write-Output $line
if ($named.Count -gt 0) { $named | ForEach-Object { Write-Output "VISIBLE_WINDOW $_" } }
Write-Output "rc=$($proc.ExitCode)"
