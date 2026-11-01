"""CENSUS: how many processes does a battery run START on the owner's PC?

THE OWNER, verbatim (2026-10-21, session `ses_ea36ec6efffeE7E32m9COGhkxL`):

    17:39:14  "entendo por que a bateria trava e da stutter. e por que o start do
               que quer que seja, da stutter no meu computador"

MEASURED on this machine, 2026-10-21: starting ANY process costs the owner a
53-127 ms stutter, because the disks are nearly full and a start is a disk
read. So the number of STARTS is the number that matters -- not the wall time.

WHAT THIS INSTRUMENT IS: a Windows process-START trace (the kernel's own
`Win32_ProcessStartTrace` event) wrapped around a battery run, then narrowed to
the battery's OWN PROCESS TREE. It answers one question with a kernel fact:
**what did the battery start?**

THE NARROWING IS NOT OPTIONAL. MEASURED 2026-10-22: the first version traced the
whole MACHINE and reported 10 417 starts, because this box re-spawns its MCP
servers (`cmd.exe`, `node.exe`) under the OpenCode server, and the owner's own
applications start processes all the time. A number from the whole machine is
not a fact about the battery. So the trace keeps `ProcessID` AND
`ParentProcessID`, and after the run the census walks the tree from the pid
`Start-Process -PassThru` handed back for the battery's own `cmd.exe`. Starts
that cannot be traced back to that pid are reported as `unattributed` and are
NEVER counted as the battery's.

TWO CLASSES INSIDE THE TREE:

  * THE OWNER'S WORLD -- the starts the owner FEELS. In this trace the app shell
    does not appear as `sotto_webview.py`; the kernel sees the interpreter, so
    the names to watch are `pythonw.exe` (how every probe launches the shell),
    `msedgewebview2.exe` (the WebView2 runtime: 38 processes and a saturated
    VRAM, measured 2026-10-21 and written down in
    `_main/_strip-stats-log-probe.py`) and `sotto_worker.py`.
  * THE BATTERY'S OWN BOOKKEEPING -- `python`/`cmd`/`powershell`: each one costs
    its 53-127 ms, but they are the price of verifying anything at all.

THE MEASUREMENT IS A KERNEL EVENT, NOT A POLL: a 250 ms poll of the process
table MISSES a python that starts and exits in 100 ms, and this battery starts
dozens of those.

THE .ps1 IS WRITTEN AS A FILE ON PURPOSE: the AGENTS' own measured lesson
(`_main/_audit-hotkey-delivery.py`) is that the inline `powershell -Command`
form of a CIM query returns EMPTY stdout on this box. The file form works.

    python _main\\_battery-start-census.py                 -> the default battery
    python _main\\_battery-start-census.py --heavy         -> with SOTTO_BATTERY_HEAVY=1
    python _main\\_battery-start-census.py --cmd "<cmd>"   -> any command
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATTERY = os.path.join(ROOT, "_main", "_audit-verify-all.cmd")

CREATE_NO_WINDOW = 0x08000000

# The starts the owner FEELS. Everything else is bookkeeping.
# NOTE: `sotto_webview.py`/`sotto_worker.py` are what the SOURCE is called; the
# kernel event carries the interpreter's name (`pythonw.exe`), which is how every
# probe in this repo launches the shell.
OWNER_WORLD = ("msedgewebview2.exe", "sotto_webview.py", "sotto_worker.py",
               "pythonw.exe")

PS1 = r'''$ErrorActionPreference='SilentlyContinue'
$log = $args[0]
$out = $args[1]
$bat = $args[2]
$heavy = $args[3]
Register-WmiEvent -Class Win32_ProcessStartTrace -SourceIdentifier ProcStart | Out-Null
# THE SUBSCRIPTION IS NOT LIVE WHEN Register-WmiEvent RETURNS. MEASURED
# 2026-10-22: a command that ran for 0.1 s right after registering produced
# ZERO events -- not even the machine-wide ones -- while the same wrapper with a
# 2 s command saw them. The trace has to be given a moment to go live, or the
# census reads "nothing happened" for a start that really happened.
Start-Sleep -Milliseconds 1500
$env:SOTTO_BATTERY_HEAVY = $heavy
# NOT `Start-Process`: it JOINS its -ArgumentList with spaces, and cmd.exe's /c
# quote rule then mangles a command with several quoted parts (MEASURED
# 2026-10-22: `"C:\...\pythonw.exe" -c "import time;time.sleep(1.5)"` came back
# rc=1 in 0.1 s). The .NET Process with a RAW `Arguments` string hands cmd
# exactly what was asked for, and `ExitCode` works without the Start-Process
# handle quirk (its first version read `rc` as null).
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'cmd.exe'
$psi.Arguments = '/c ' + $bat
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$psi.WorkingDirectory = (Get-Location).Path
$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
$sw = [Diagnostics.Stopwatch]::StartNew()
$null = $p.Start()
$root = $p.Id
$outTask = $p.StandardOutput.ReadToEndAsync()
$errTask = $p.StandardError.ReadToEndAsync()
$p.WaitForExit()
$rc = $p.ExitCode
$sw.Stop()
[IO.File]::WriteAllText($log, $outTask.Result)
[IO.File]::WriteAllText("$log.err", $errTask.Result)
Start-Sleep -Milliseconds 1500

$ename = @{}
$epar = @{}
foreach ($e in (Get-Event -SourceIdentifier ProcStart)) {
  $id = [int]$e.SourceEventArgs.NewEvent.ProcessID
  $ename[$id] = $e.SourceEventArgs.NewEvent.ProcessName
  $epar[$id] = [int]$e.SourceEventArgs.NewEvent.ParentProcessID
}
Unregister-Event -SourceIdentifier ProcStart

$kids = @{}
foreach ($k in $epar.Keys) {
  $pp = $epar[$k]
  if (-not $kids.ContainsKey($pp)) { $kids[$pp] = New-Object System.Collections.ArrayList }
  [void]$kids[$pp].Add($k)
}
$seen = @{}
$seen[$root] = $true
$queue = New-Object System.Collections.Queue
$queue.Enqueue($root)
while ($queue.Count -gt 0) {
  $cur = [int]$queue.Dequeue()
  if ($kids.ContainsKey($cur)) {
    foreach ($c in $kids[$cur]) {
      if (-not $seen.ContainsKey($c)) { $seen[$c] = $true; $queue.Enqueue($c) }
    }
  }
}

$rows = New-Object System.Collections.ArrayList
$own = New-Object System.Collections.ArrayList
$treed = 0
foreach ($id in $seen.Keys) {
  if ($id -eq $root) { continue }
  $n = $ename[$id]
  if (-not $n) { continue }
  $treed = $treed + 1
  [void]$rows.Add($n)
  if (@('msedgewebview2.exe','sotto_webview.py','sotto_worker.py','pythonw.exe') -contains $n) {
    [void]$own.Add($n)
  }
}
$unattributed = 0
foreach ($id in $ename.Keys) {
  if (-not $seen.ContainsKey($id)) { $unattributed = $unattributed + 1 }
}

$groups = $rows | Group-Object | Sort-Object Count -Descending | ForEach-Object { [pscustomobject]@{ name=$_.Name; count=$_.Count } }
$res = [pscustomobject]@{
  rc = $rc
  elapsed_s = [Math]::Round($sw.Elapsed.TotalSeconds,1)
  tree_root_pid = $root
  total = $treed
  unattributed = $unattributed
  owner_world = $own.Count
  owner_world_names = ($own | Group-Object | ForEach-Object { $_.Name + " x" + $_.Count }) -join ", "
  by_name = @($groups)
}
$res | ConvertTo-Json -Depth 5 | Set-Content -Path $out -Encoding UTF8
Write-Output "CENSUS-DONE"
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cmd", default=None,
                    help="the command to wrap (default: the battery)")
    ap.add_argument("--heavy", action="store_true",
                    help="run with SOTTO_BATTERY_HEAVY=1 (the heavy steps RUN)")
    ap.add_argument("--neg-arm", action="store_true",
                    help="control: wrap a command that MUST count as the owner's "
                         "world (`pythonw.exe -c pass`) -- the census must SEE it, "
                         "or the census cannot say NO to anything")
    args = ap.parse_args(argv)

    tmp = tempfile.mkdtemp(prefix="battery-census-",
                           dir=os.environ.get("TMPDIR") or tempfile.gettempdir())
    ps1 = os.path.join(tmp, "census.ps1")
    log = os.path.join(tmp, "battery.log")
    out = os.path.join(tmp, "census.json")
    with open(ps1, "w", encoding="utf-8", newline="") as fh:
        fh.write(PS1.replace("\n", "\r\n"))
    cmd = args.cmd or BATTERY
    if args.neg_arm:
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        cmd = '"%s" -c pass' % pyw

    env = dict(os.environ)
    env.pop("SOTTO_BATTERY_HEAVY", None)
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", ps1, log, out, cmd, "1" if args.heavy else "0"],
        capture_output=True, text=True, timeout=3600, cwd=ROOT, env=env,
        creationflags=CREATE_NO_WINDOW,
    )
    if not os.path.exists(out):
        print("CENSUS FAILED: the trace produced nothing")
        print((proc.stdout or "")[-800:])
        print((proc.stderr or "")[-800:])
        return 1
    with open(out, "r", encoding="utf-8-sig", errors="replace") as fh:
        data = json.load(fh)

    print("BATTERY START CENSUS -- what the battery STARTED on the owner's PC")
    print("  command    : %s" % cmd)
    print("  heavy mode : %s" % ("ON (SOTTO_BATTERY_HEAVY=1)" if args.heavy else "OFF"))
    print("  battery rc : %s" % data.get("rc"))
    print("  elapsed    : %s s" % data.get("elapsed_s"))
    print("  tree root  : pid %s (the battery's own cmd.exe) -- ONLY its "
          "descendants are counted" % (data.get("tree_root_pid"),))
    print("  TOTAL STARTS IN THE TREE: %s" % data.get("total"))
    print("  starts on the machine NOT in the tree (never counted): %s"
          % data.get("unattributed"))
    print("  THE OWNER'S WORLD: %s start(s)  %s"
          % (data.get("owner_world"), data.get("owner_world_names") or ""))
    print("  by name:")
    for row in data.get("by_name", [])[:16]:
        print("    %5d  %s" % (row["count"], row["name"]))
    print("  the run's log: %s" % log)
    if args.neg_arm:
        seen = data.get("owner_world") or 0
        ok = seen >= 1
        print("NEG-ARM: the census %s the owner's world it was shown "
              "(owner_world=%s, names=%s)"
              % ("SAW" if ok else "MISSED", seen,
                 data.get("owner_world_names") or "-none-"))
        print("NEG-ARM " + ("PASS" if ok else "FAIL -- the census is blind"))
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
