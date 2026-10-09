# window-census-fast.ps1 -- a census that can actually SEE a short-lived console window.
#
# WHY THIS FILE EXISTS. The owner complained, twice, that terminals keep opening on his
# screen. The house census samples ONCE PER 60 s, so a window that lives less than that
# passes it unseen. A census that cannot see the thing it is supposed to detect is the
# DEFECT, so this one proves it can see it BEFORE it claims anything about the cure.
#
#   pwsh -NoProfile -File window-census-fast.ps1 -Launches 20 -EveryMs 25
#
# ARMS (each repeated $Launches times, default 20):
#
#   catch-console    a REAL console window, launched Minimized on purpose. This is the
#                    control. If it produces 0 visible samples the census is BLIND and
#                    the whole run is meaningless -> VERDICT FAIL, loudly.
#   defect-plain     `Start-Process python.exe` with no window style. This is the recipe
#                    the repo actually contains. Minimized, same reason as above.
#   fixed-pythonw    `pythonw.exe` -- GUI subsystem, never allocates a console.
#   fixed-hidden     `python.exe` + `-WindowStyle Hidden` == CREATE_NO_WINDOW (0x08000000).
#   fixed-nonewwin   `python.exe` + `-NoNewWindow`.
#
# THE COST THAT IS PAID, NOT HIDDEN. `catch-console` and `defect-plain` really do map a
# console window. They are launched MINIMIZED so the owner does not get a full window
# flashing on his desk -- which is the exact thing that was complained about. A minimized
# window is still WS_VISIBLE (IsWindowVisible == TRUE) and still iconic; the census records
# the iconic flag on every sample, so "it was mapped" and "it was not obtrusive" are two
# separate recorded facts, not one claim. See receipts/receipt-35-fast-window-census.md.
#
# SELF-CENSUS. This script reads its OWN pid out of the console it was launched into and
# reports `census_console_hwnd`. If that is 0 the census itself has no console, which
# changes what `fixed-nonewwin` means for the reader, so it is never left implicit.
#
# EXIT CODE. 0 = the census caught the control AND every fixed arm was clean.
#             1 = the census is blind, or a fixed arm mapped a window.
#             Read `$LASTEXITCODE`; do not pipe this.

param(
  [int]    $Launches  = 20,
  [int]    $EveryMs   = 25,
  [int]    $HoldMs    = 1500,     # how long the launched process must stay alive
  [int]    $TailMs    = 250,      # sampling after the child exits, for the destroy path
  [string] $Out       = 'H:\sotto\_moved\aireplay\_main\logs\window-census-fast.log',
  [string] $JsonOut   = '',
  [string[]]$Arms     = @('catch-console','defect-plain','fixed-pythonw','fixed-hidden','fixed-nonewwin'),
  [switch]   $Enumerate
)

$ErrorActionPreference = 'Stop'
$OUTDIR = Split-Path -Parent $Out
if ($OutDir -and -not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# ---------------------------------------------------------------------------
# native probe: EnumWindows + IsWindowVisible in ONE call, so a sample costs
# microseconds and the cadence is set by the sleep, not by the enumeration.
# ---------------------------------------------------------------------------
if (-not ('SottoWin' -as [type])) {
  Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class SottoWin {
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
    [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
    delegate bool EnumProc(IntPtr h, IntPtr p);

    // pid|hwnd|class|title|state   (state = iconic|normal)
    public static string[] Visible() {
        var rows = new List<string>();
        EnumWindows(delegate(IntPtr h, IntPtr p) {
            if (!IsWindowVisible(h)) return true;
            uint pid; GetWindowThreadProcessId(h, out pid);
            var c = new StringBuilder(256); GetClassName(h, c, 256);
            var t = new StringBuilder(256); GetWindowText(h, t, 256);
            rows.Add(pid + "|" + h.ToInt64() + "|" + c + "|" + t + "|" + (IsIconic(h) ? "iconic" : "normal"));
            return true;
        }, IntPtr.Zero);
        return rows.ToArray();
    }
    public static string OwnerName(uint pid) {
        try {
            using (var p = System.Diagnostics.Process.GetProcessById((int)pid)) return p.ProcessName;
        } catch { return "?"; }
    }
}
'@ -Language CSharp
}

# ---------------------------------------------------------------------------
# The SAMPLER ITSELF runs on a C# thread, not in the PowerShell loop.
#
# Two defects this replaces, both found by running it rather than reasoning about it:
#  1. CADENCE. The PowerShell loop measured 60.8 ms median / 190.5 ms p95 while asking
#     for 25 ms -- building one PSCustomObject per visible window per sample, 24 of them,
#     is not free. A 25 ms grid that silently runs at 60 ms is a census that is blind to
#     a 40 ms window, which is exactly the failure this file exists to kill.
#  2. THE MISS IS STRUCTURAL. Sampling began AFTER `Start-Process` returned, so the first
#     few tens of ms of every launch were unobserved by construction.
# The thread is started BEFORE the launch and the cadence is measured, not requested.
# ---------------------------------------------------------------------------
if (-not ('SottoSampler' -as [type])) {
  Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public class SottoSampler {
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
    delegate bool EnumProc(IntPtr h, IntPtr p);

    readonly int _ms; readonly HashSet<long> _base; readonly List<string> _seen = new List<string>();
    readonly HashSet<string> _keys = new HashSet<string>();
    readonly List<double> _iv = new List<double>();
    volatile bool _run; Thread _t; Stopwatch _sw;

    public SottoSampler(int ms, long[] baselineHwnds) {
        _ms = ms < 1 ? 1 : ms;
        _base = new HashSet<long>();
        if (baselineHwnds != null) foreach (var h in baselineHwnds) _base.Add(h);
    }

    void Tick() {
        var rows = new List<string>();
        EnumWindows(delegate(IntPtr h, IntPtr p) {
            if (!IsWindowVisible(h)) return true;
            long hwnd = h.ToInt64();
            if (_base.Contains(hwnd)) return true;
            uint pid; GetWindowThreadProcessId(h, out pid);
            var c = new StringBuilder(256); GetClassName(h, c, 256);
            var t = new StringBuilder(256); GetWindowText(h, t, 256);
            rows.Add(pid + "|" + hwnd + "|" + c + "|" + t + "|" + (IsIconic(h) ? "iconic" : "normal"));
            return true;
        }, IntPtr.Zero);
        double now = _sw.Elapsed.TotalMilliseconds;
        _iv.Add(now - _last); _last = now;
        foreach (var r in rows) { if (_keys.Add(r)) _seen.Add(now.ToString("F1") + "|" + r); }
    }

    double _last;

    public void Start() {
        _run = true; _sw = Stopwatch.StartNew(); _last = 0;
        _t = new Thread(() => {
            var spin = new SpinWait();
            while (_run) { Tick(); spin.SpinOnce(); long end = _sw.ElapsedMilliseconds + _ms; while (_sw.ElapsedMilliseconds < end) Thread.Sleep(0); }
        });
        _t.IsBackground = true;
        _t.Priority = ThreadPriority.AboveNormal;
        _t.Start();
    }

    public List<string> Stop() { _run = false; if (_t != null) _t.Join(3000); return _seen; }
    public int Ticks() { return _iv.Count; }
    public double MedianMs() { return Stat(0.50); }
    public double P95Ms() { return Stat(0.95); }
    public double MinMs() { return Stat(0.0); }

    double Stat(double q) {
        if (_iv.Count == 0) return -1;
        var v = new List<double>(_iv); v.Sort();
        int i = (int)(v.Count * q); if (i >= v.Count) i = v.Count - 1; if (i < 0) i = 0;
        return Math.Round(v[i], 1);
    }
}
'@ -Language CSharp
}

# A console window's HWND belongs to conhost.exe, NOT to the cmd/python that caused it,
# so attribution by descendant-pid alone silently misses every console ever. That is a
# third way a census goes blind and it is why CONSOLE_CLASSES is matched by CLASS here.
$CONSOLE_CLASSES = @('ConsoleWindowClass','CASCADIA_HOSTING_WINDOW_CLASS','PseudoConsoleWindow')

function Get-VisibleRows {
  $rows = New-Object System.Collections.Generic.List[object]
  foreach ($r in [SottoWin]::Visible()) {
    $p = $r -split '\|', 5
    if ($p.Count -lt 5) { continue }
    $rows.Add([pscustomobject]@{
      Pid   = [int]$p[0]; Hwnd = [long]$p[1]; Class = $p[2]
      Title = $p[3]; State = $p[4]; IsConsole = ($CONSOLE_CLASSES -contains $p[2])
    })
  }
  $rows
}

function Resolve-PythonExe {
  foreach ($c in @('C:\Program Files\Python311\python.exe')) { if (Test-Path $c) { return $c } }
  $c = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
  if ($c) { return $c }
  throw 'python.exe not found'
}

$PY   = Resolve-PythonExe
$PYW  = $PY -replace 'python\.exe$','pythonw.exe'
if (-not (Test-Path $PYW)) { throw "pythonw.exe not found next to $PY" }
$CMD  = (Get-Command cmd.exe -ErrorAction SilentlyContinue).Source
if (-not $CMD) { throw 'cmd.exe not found' }

$baseline = @{}
foreach ($r in Get-VisibleRows) { $baseline[[string]$r.Hwnd] = $true }

$log = New-Object System.Collections.Generic.List[string]
function Say([string]$m) { $log.Add($m); Write-Output $m; Add-Content -Path $Out -Value $m }

$selfConsole = [SottoWin]::GetConsoleWindow()
Say ("WINDOW-CENSUS-FAST ts={0} every_ms_req={1} launches={2} cadence_is_measured_not_assumed" -f (Get-Date -Format o), $EveryMs, $Launches)
Say ("SELF census_pid={0} census_console_hwnd={1} ({2})" -f $PID, $selfConsole.ToInt64(),
     $(if ($selfConsole.ToInt64() -ne 0) { 'this census HAS a console: NoNewWindow children share it' } else { 'this census has NO console: it is GUI-subsystem or hidden' }))
Say ("BASELINE visible_windows_at_start={0} of which_console={1}" -f $baseline.Count, (@(foreach ($r in Get-VisibleRows) { if ($r.IsConsole) { $r } })).Count)

# ---------------------------------------------------------------------------
# -Enumerate: the owner's question answered directly -- "which terminals are on my
# screen right now, and which lane launched them". ONE snapshot, names every visible
# window with its owning process AND its command line, so a console belongs to a lane
# instead of being an accusation with no address. This is the mode to run when a
# terminal has just appeared and someone wants to know who owns it.
# ---------------------------------------------------------------------------
if ($Enumerate) {
  $cmds = @{}
  try {
    foreach ($r in (Get-CimInstance Win32_Process -ErrorAction Stop)) {
      $cmds[[int]$r.ProcessId] = [pscustomobject]@{ Name=$r.Name; Parent=[int]$r.ParentProcessId; Cmd=$r.CommandLine }
    }
  } catch { Say "CIM-FAIL $($_.Exception.Message)" }
  Say ("ENUMERATE ts={0}" -f (Get-Date -Format o))
  $n = 0
  foreach ($r in ((Get-VisibleRows) | Sort-Object -Property @{E='IsConsole';D=$true}, Class, Pid)) {
    $n++
    $info = $cmds[[int]$r.Pid]
    $parent = if ($info -and $cmds.ContainsKey([int]$info.Parent)) { $cmds[[int]$info.Parent].Name } else { '?' }
    Say ("  JANELA {0} pid={1} owner={2} parent={3} console={4} state={5} class={6} title='{7}'" -f `
          $n, $r.Pid, $(if($info){$info.Name}else{'?'}), $parent, $r.IsConsole, $r.State, $r.Class, $r.Title)
    if ($info -and $info.Cmd) {
      $c = $info.Cmd; if ($c.Length -gt 220) { $c = $c.Substring(0,220) + '...' }
      Say ("          cmd={0}" -f $c)
    }
  }
  Say ("ENUMERATE-END visible={0} console={1}" -f $n, (@(foreach ($r in Get-VisibleRows) { if ($r.IsConsole) { $r } })).Count)
  exit 0
}

# one arm = one launch recipe. `Must` is the verdict that arm has to earn.
$ARMDEF = @{
  'catch-console'  = @{ Must = 'CAUGHT';  Expect = 'caught';  Desc = 'real console window, MINIMIZED on purpose -- the control' }
  'defect-plain'   = @{ Must = 'CAUGHT';  Expect = 'caught';  Desc = 'Start-Process python.exe with no window style -- the recipe in the repo' }
  'fixed-pythonw'  = @{ Must = 'CLEAN';   Expect = 'clean';   Desc = 'pythonw.exe -- GUI subsystem, never allocates a console' }
  'fixed-hidden'   = @{ Must = 'CLEAN';   Expect = 'clean';   Desc = 'python.exe + -WindowStyle Hidden == CREATE_NO_WINDOW 0x08000000' }
  'fixed-nonewwin' = @{ Must = 'CLEAN';   Expect = 'clean';   Desc = 'python.exe + -NoNewWindow' }
}

$intervals = New-Object System.Collections.Generic.List[double]
$results = @{}
$foreignAll = @{}
$tickTotals = New-Object System.Collections.Generic.List[int]
$cadMedians = New-Object System.Collections.Generic.List[double]
$cadP95s    = New-Object System.Collections.Generic.List[double]
$baselineHwnds = [long[]]@($baseline.Keys | ForEach-Object { [long]$_ })

# A sleeper SCRIPT FILE, not `-c`. First run passed the inline form and Start-Process
# re-split it: python received `import` alone and died with SyntaxError in ~50 ms, so the
# child never stayed up for the window to be observed. The console still mapped, so the
# arm "passed" -- on a corpse. A file argument cannot be re-split.
$sleeper = Join-Path ([IO.Path]::GetTempPath()) 'sotto-win-sleeper.py'
Set-Content -Path $sleeper -Encoding ascii -Value "import time,sys`ntime.sleep(float(sys.argv[1]))`n"

# ONE CIM query per arm, after sampling, to decide whether a caught window belongs to the
# arm at all. Asking per SAMPLE is not affordable (CIM costs ~100-300 ms vs a 25 ms
# budget) and NOT asking at all is worse: run 1 scored `-NoNewWindow` FAIL on 15/20 while
# every catch was somebody ELSE's window (an `Aireplay HUD` and a chrome `Salvar como`).
# Attribution is a census question, not a sampling question.
function Resolve-Ancestry([int[]]$pids) {
  $map = @{}
  if (-not $pids -or $pids.Count -eq 0) { return $map }
  try { $rows = Get-CimInstance Win32_Process -ErrorAction Stop } catch { return $map }
  foreach ($r in $rows) {
    if ($null -ne $r.ProcessId) { $map[[int]$r.ProcessId] = [int]$r.ParentProcessId }
  }
  $map
}

function In-Tree([int]$pid0, [int]$root, $map) {
  $cur = $pid0; $guard = 0
  while ($cur -gt 0 -and $guard++ -lt 64) {
    if ($cur -eq $root) { return $true }
    if (-not $map.ContainsKey($cur)) { return $false }
    $cur = $map[$cur]
  }
  $false
}

foreach ($arm in $Arms) {
  if (-not $ARMDEF.ContainsKey($arm)) { Say "SKIP unknown arm '$arm'"; continue }
  $def = $ARMDEF[$arm]
  $caught = 0; $clean = 0; $detail = @{}
  $sleepS = [Math]::Max(0.05, $HoldMs / 1000.0)
  $roots = New-Object System.Collections.Generic.List[int]

  for ($i = 1; $i -le $Launches; $i++) {
    # Sampling starts BEFORE the launch. Run 2 began sampling after Start-Process returned,
    # so the opening of every window was unobserved by construction.
    $samp = [SottoSampler]::new($EveryMs, [long[]]$baselineHwnds)
    $samp.Start()
    $proc = $null
    switch ($arm) {
      'catch-console'  { $proc = Start-Process -FilePath $CMD -ArgumentList @('/c','ping -n 8 127.0.0.1 >nul') -WindowStyle Minimized -PassThru }
      'defect-plain'   { $proc = Start-Process -FilePath $PY  -ArgumentList @($sleeper, "$sleepS") -WindowStyle Minimized -PassThru }
      'fixed-pythonw'  { $proc = Start-Process -FilePath $PYW -ArgumentList @($sleeper, "$sleepS") -PassThru }
      'fixed-hidden'   { $proc = Start-Process -FilePath $PY  -ArgumentList @($sleeper, "$sleepS") -WindowStyle Hidden -PassThru }
      'fixed-nonewwin' { $proc = Start-Process -FilePath $PY  -ArgumentList @($sleeper, "$sleepS") -NoNewWindow -PassThru }
    }
    $roots.Add([int]$proc.Id)

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalMilliseconds -lt ($HoldMs + $TailMs)) {
      if ($proc.HasExited -and $sw.Elapsed.TotalMilliseconds -gt $HoldMs) { break }
      Start-Sleep -Milliseconds 10
    }
    if (-not $proc.HasExited) { try { $proc.Kill() } catch {} }
    Start-Sleep -Milliseconds 60   # let the console be torn down before the next launch

    foreach ($row in $samp.Stop()) {
      # the sampler emits: t_ms|pid|hwnd|class|title|state  (6 fields, leading ts)
      $p = $row -split '\|', 6
      if ($p.Count -lt 6) { continue }
      $key = "$($p[1])|$($p[3])|$($p[4])"
      if ($detail.ContainsKey($key)) { continue }
      $detail[$key] = [pscustomobject]@{
        Pid = [int]$p[1]; Class = $p[3]; Title = $p[4]; State = $p[5]
        IsConsole = ($CONSOLE_CLASSES -contains $p[3]); AtMs = [int][double]$p[0]; Mine = $false
      }
    }
    $tickTotals.Add($samp.Ticks())
    $cadMedians.Add($samp.MedianMs()); $cadP95s.Add($samp.P95Ms())
  }

  # attribute every catch to an arm now that sampling is done
  $tree = Resolve-Ancestry (@($detail.Values | ForEach-Object { $_.Pid }) | Sort-Object -Unique)
  $mine = @(); $foreign = @()
  foreach ($w in $detail.Values) {
    if (@($roots | Where-Object { In-Tree $w.Pid $_ $tree }).Count -gt 0) { $w.Mine = $true; $mine += $w }
    else { $foreign += $w }
  }
  foreach ($w in $foreign) {
    $fk = "$($w.Pid)|$($w.Class)"
    if (-not $foreignAll.ContainsKey($fk)) {
      $foreignAll[$fk] = [pscustomobject]@{ Pid=$w.Pid; Class=$w.Class; Title=$w.Title; State=$w.State; IsConsole=$w.IsConsole; Owner=([SottoWin]::OwnerName([uint32]$w.Pid)) }
    }
  }
  $armCaught = @($mine | Where-Object { $_.IsConsole }).Count
  $armWindows = $mine.Count
  $need = [Math]::Max(1,[int][Math]::Ceiling($Launches/2))
  $ok = if ($def.Expect -eq 'caught') { $armCaught -ge 1 } else { $armWindows -eq 0 }
  $results[$arm] = [ordered]@{
    desc = $def.Desc; launches = $Launches; arm_console_windows = $armCaught; arm_windows = $armWindows
    distinct = $detail.Count; foreign = $foreign.Count
    verdict = $(if ($ok) { 'PASS' } else { 'FAIL' })
    windows = @($mine); foreign_windows = @($foreign)
  }
  Say ("ARM {0} verdict={1} launches={2} arm_console_windows={3} arm_windows={4} foreign={5} need_for_caught={6} :: {7}" -f `
        $arm, $(if($ok){'PASS'}else{'FAIL'}), $Launches, $armCaught, $armWindows, $foreign.Count, $need, $def.Desc)
  foreach ($w in $mine) {
    Say ("  ALERTA-JANELA arm={0} pid={1} owner={2} class={3} console={4} state={5} at_ms={6} title='{7}'" -f `
          $arm, $w.Pid, ([SottoWin]::OwnerName([uint32]$w.Pid)), $w.Class, $w.IsConsole, $w.State, $w.AtMs, $w.Title)
  }
}

# achieved cadence: the number that decides whether this census is 25 ms or not
$sorted = @($intervals | Sort-Object)
$median = if ($sorted.Count) { [Math]::Round($sorted[[int]($sorted.Count/2)], 1) } else { -1 }
$p95    = if ($sorted.Count) { [Math]::Round($sorted[[int]($sorted.Count*0.95)], 1) } else { -1 }

$blind    = @($Arms | Where-Object { $ARMDEF.ContainsKey($_) -and $ARMDEF[$_].Must -eq 'CAUGHT' -and $results.ContainsKey($_) -and $results[$_].arm_console_windows -eq 0 })
$dirtyFix = @($Arms | Where-Object { $ARMDEF.ContainsKey($_) -and $ARMDEF[$_].Must -eq 'CLEAN' -and $results.ContainsKey($_) -and $results[$_].arm_windows -gt 0 })

$verdict = if ($blind.Count -gt 0) { 'FAIL-BLIND' } elseif ($dirtyFix.Count -gt 0) { 'FAIL-DIRTY' } else { 'PASS' }
# CADENCE IS REPORTED AS ACHIEVED, PER LAUNCH. "25 ms" in the header is the REQUEST; the
# verdict of "this census can see a short window" rests on the measured number, and run 2
# is the reason: it asked for 25 ms and delivered 60.8 ms median, which is why the sampler
# moved off the PowerShell loop and onto a C# thread.
$ticks = ($tickTotals | Measure-Object -Sum).Sum
$cadM = (@($cadMedians | Sort-Object)); $cadP = (@($cadP95s | Sort-Object))
$medOfMedians = if ($cadM.Count) { [Math]::Round($cadM[[int]($cadM.Count/2)],1) } else { -1 }
$worstP95     = if ($cadP.Count) { [Math]::Round($cadP[-1],1) } else { -1 }
Say ("CENSUS-END ts={0} verdict={1} ticks={2} launches_measured={3} requested_ms={4} achieved_median_of_medians_ms={5} worst_p95_ms={6}" -f `
      (Get-Date -Format o), $verdict, $ticks, $cadM.Count, $EveryMs, $medOfMedians, $worstP95)
Say ("  blind_arms={0} fixed_arms_that_dirty={1}" -f ($blind -join ','), ($dirtyFix -join ','))

# FOREIGN WINDOWS ARE REPORTED, NOT SCORED. They are windows that appeared on the owner's
# desktop while this census ran and that belong to NO arm here -- i.e. some other lane.
# They do not make an arm fail, but they are the closest thing this instrument has to the
# owner's complaint, so every one of them is named with its owning process.
Say ("FOREIGN-WINDOWS n={0} (visible during the run, owned by no arm -- these are OTHER lanes')" -f $foreignAll.Count)
foreach ($w in $foreignAll.Values) {
  Say ("  ALERTA-JANELA-FOREIGN pid={0} owner={1} class={2} console={3} state={4} title='{5}'" -f `
        $w.Pid, $w.Owner, $w.Class, $w.IsConsole, $w.State, $w.Title)
}

$payload = [ordered]@{
  ts = (Get-Date -Format o); verdict = $verdict; launches_per_arm = $Launches
  requested_every_ms = $EveryMs; achieved_median_of_medians_ms = $medOfMedians; worst_p95_ms = $worstP95
  ticks = $ticks; census_console_hwnd = $selfConsole.ToInt64()
  blind_arms = @($blind); fixed_arms_that_dirty = @($dirtyFix)
  foreign_windows = @($foreignAll.Values); arms = $results
}
if ($JsonOut) {
  $jd = Split-Path -Parent $JsonOut
  if ($jd -and -not (Test-Path $jd)) { New-Item -ItemType Directory -Path $jd -Force | Out-Null }
  $payload | ConvertTo-Json -Depth 8 | Set-Content -Path $JsonOut -Encoding UTF8
}

if ($verdict -ne 'PASS') { exit 1 } else { exit 0 }