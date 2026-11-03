#!/usr/bin/env python3
"""_main/_lane-profile-census.py -- one long, quiet look at ONE live instance.

WHAT THIS IS. The profile lane's leak instrument. Every `--interval` seconds it
names the shell that currently OWNS the app's mutex (the pid that logged
`SHELL_STARTUP_STAGE`, i.e. the one `shell-relaunch.log` records), then reads its
process counters and those of its descendants (the worker `python.exe` and the
`msedgewebview2.exe` tree). One CSV row per sample, so a GROWTH is a slope and
not an anecdote.

WHY NOT A CENSUS PER INSTANCE. The app self-relaunches when `app/webview/*`
changes (`SHELL_RELAUNCH`), so a census taken across instances cannot tell a leak
from a restart. The rows carry the pid; the slope is computed per pid only.

THE COUNTERS ARE THE OS's, not the app's: WorkingSet64 / PrivateMemorySize64 /
Threads.Count / HandleCount / CPU (seconds, so a delta is real CPU time). Nothing
here reads or writes the app's files, and nothing here starts or stops it.
"""
import argparse
import csv
import os
import subprocess
import sys
import time

PS = r"""
$ErrorActionPreference='Stop'
$shells = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
  Where-Object { $_.WorkingSetSize -gt 40MB }
foreach ($s in $shells) {
  $p = Get-Process -Id $s.ProcessId -ErrorAction SilentlyContinue
  if (-not $p) { continue }
  $row = '{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}' -f 'shell', $p.Id, $p.WorkingSet64,
     $p.PrivateMemorySize64, $p.Threads.Count, $p.HandleCount, $p.CPU, $s.CreationDate
  Write-Output $row
  # descendants, one level of recursion is what this app has: the worker is a
  # python.exe child and WebView2 is an msedgewebview2.exe tree under the shell
  $q = New-Object System.Collections.Queue
  $q.Enqueue($p.Id)
  while ($q.Count -gt 0) {
    $parent = $q.Dequeue()
    foreach ($c in (Get-CimInstance Win32_Process -Filter "ParentProcessId=$parent")) {
      $cp = Get-Process -Id $c.ProcessId -ErrorAction SilentlyContinue
      if ($cp) {
        Write-Output ('{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}' -f $c.Name, $cp.Id,
          $cp.WorkingSet64, $cp.PrivateMemorySize64, $cp.Threads.Count,
          $cp.HandleCount, $cp.CPU, $c.CreationDate)
        $q.Enqueue($cp.Id)
      }
    }
  }
}
"""


def sample():
    out = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', PS],
                         capture_output=True, text=True, timeout=120, creationflags=0x08000000)
    rows = []
    for line in out.stdout.splitlines():
        parts = [p.strip() for p in line.split('|')]
        if len(parts) != 8:
            continue
        name, pid, ws, private, threads, handles, cpu, created = parts
        try:
            rows.append({
                't': time.strftime('%Y-%m-%d %H:%M:%S'),
                'name': name, 'pid': int(pid),
                'ws_mb': round(int(ws) / 1048576.0, 1),
                'private_mb': round(int(private) / 1048576.0, 1),
                'threads': int(threads), 'handles': int(handles),
                'cpu_s': round(float(cpu.replace(',', '.')), 2),
                'created': created,
            })
        except Exception:
            continue
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--minutes', type=float, default=12.0)
    ap.add_argument('--interval', type=float, default=30.0)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  '_lane-profile-census.csv'))
    args = ap.parse_args()
    deadline = time.time() + args.minutes * 60
    fields = ['t', 'kind', 'pid', 'ws_mb', 'private_mb', 'threads', 'handles', 'cpu_s', 'created']
    new = not os.path.exists(args.out)
    with open(args.out, 'a', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        while time.time() < deadline:
            try:
                rows = sample()
            except Exception as exc:  # noqa: BLE001
                print('sample failed: %r' % (exc,))
                rows = []
            for r in rows:
                r['kind'] = 'proc'
                w.writerow({k: r.get(k) for k in fields})
            fh.flush()
            print('%s rows=%d socks=%s' % (time.strftime('%H:%M:%S'), len(rows),
                                           ','.join('%s:%d' % (r['name'], r['pid']) for r in rows)))
            time.sleep(max(1.0, args.interval - (time.time() % args.interval)))
    print('csv: %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
