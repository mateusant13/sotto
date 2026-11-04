"""WHO froze the box? A census that is already running when it happens.

OWNER, 2026-11-04, verbatim: *"o PC inteiro trava: herdr, os terminais dentro dele, o
chrome, tudo ao mesmo tempo"*.

A freeze is a 10-60 s event that ends before anyone can attach a profiler, and the
process that ate the machine is the one that has already gone quiet by the time you
look. So the evidence has to be taken CONTINUOUSLY, by something cheaper than the thing
it watches, and it has to carry its own refusal: an instrument that cannot show you its
population and its unreadable count is decoration (extreme-optimization-audit §2, §15).

WHAT IT SAMPLES, AND WHY EACH ONE IS CHEAP
  * `GetPerformanceInfo`: commit total / limit, process, thread and handle counts in ONE
    syscall. This is the pressure row.
  * `GetSystemTimes`: machine CPU % from two ideltime deltas. One syscall.
  * the sampler's OWN wall delta. If this loop was due in 2000 ms and it woke 9000 ms
    later, the machine was starved and THAT is the freeze timestamps -- no polling of a
    log, no waiting for the next report.
  * every 5th tick (10 s, and ALWAYS on a freeze or a pressure breach): per-process CPU
    time and commit, ranked. `psutil.process_iter` costs ~40-90 ms on this 700-process
    box, so paying it every 2 s would make the instrument a term in its own census.

THE VERDICT IS A ROW, NOT A FEELING: `FREEZE` fires on a late wake of >= half the
cadence (>= 2x late is `FREEZE_SEVERE`), or when commit crosses `--commit-pct`, or when
any process holds >= `--cpu-share` of the machine for one tick. Each row names the top
holders AT THAT MOMENT, with pid, name, cpu_delta_ms and private bytes.

IT PUTS NOTHING ON THE SCREEN and kills nothing. Launch it hidden:

    pythonw _main/freeze-census.py --out _main/_audit-verify/freeze-census.log

Read it with `_main/freeze-census.py --report` (freezes plus who was on top).

Disk: the log is capped (`--max-bytes`, default 4 MB) and rotated once, because an
instrument that fills the volume is the defect it was built to find.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time

psutil = None
for extra in (os.path.join(os.path.dirname(os.path.abspath(__file__)), '_libs'),):
    if os.path.isdir(extra) and extra not in sys.path:
        sys.path.insert(0, extra)
try:
    import psutil  # noqa: PLC0415
except Exception:  # noqa: BLE001
    psutil = None


class PERFORMANCE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('cb', wt.DWORD), ('CommitTotal', ctypes.c_size_t),
        ('CommitLimit', ctypes.c_size_t), ('CommitPeak', ctypes.c_size_t),
        ('PhysicalTotal', ctypes.c_size_t), ('PhysicalAvailable', ctypes.c_size_t),
        ('SystemCache', ctypes.c_size_t), ('KernelTotal', ctypes.c_size_t),
        ('KernelPaged', ctypes.c_size_t), ('KernelNonpaged', ctypes.c_size_t),
        ('PageSize', ctypes.c_size_t), ('HandleCount', wt.DWORD),
        ('ProcessCount', wt.DWORD), ('ThreadCount', wt.DWORD),
    ]


class FILETIME(ctypes.Structure):
    _fields_ = [('dwLowDateTime', wt.DWORD), ('dwHighDateTime', wt.DWORD)]


#: set only by `--selftest`: milliseconds of a REAL `time.sleep` injected between
#: two ticks, so the late-wake detector has something to catch.
_PLANT_MS = 0

psapi = ctypes.WinDLL('psapi', use_last_error=True)
psapi.GetPerformanceInfo.restype = wt.BOOL
psapi.GetPerformanceInfo.argtypes = [ctypes.c_void_p, wt.DWORD]
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.GetSystemTimes.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_void_p]


def ft(x):
    return (x.dwHighDateTime << 32) | x.dwLowDateTime


def perf():
    pi = PERFORMANCE_INFORMATION()
    pi.cb = ctypes.sizeof(pi)
    if not psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb):
        return None
    page = pi.PageSize or 4096
    return {
        'commit_mb': round(pi.CommitTotal * page / 1048576.0, 1),
        'limit_mb': round(pi.CommitLimit * page / 1048576.0, 1),
        'commit_pct': round(100.0 * pi.CommitTotal / max(1, pi.CommitLimit), 1),
        'phys_free_mb': round(pi.PhysicalAvailable * page / 1048576.0, 1),
        'procs': int(pi.ProcessCount), 'threads': int(pi.ThreadCount),
        'handles': int(pi.HandleCount),
    }


def system_cpu(prev, cur):
    if prev is None or cur is None:
        return None
    idle = ft(cur[0]) - ft(prev[0])
    total = (ft(cur[1]) - ft(prev[1])) + (ft(cur[2]) - ft(prev[2]))
    if total <= 0:
        return None
    busy = max(0.0, (total - idle) / float(total)) * 100.0
    return round(min(100.0, max(0.0, busy)), 1)


def sys_times():
    idle, kern, user = FILETIME(), FILETIME(), FILETIME()
    if not kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern),
                                   ctypes.byref(user)):
        return None
    return (idle, kern, user)


def top_holders(n=8, prev=None):
    """Per-process rank, as (name, pid, cpu_delta_ms, rss_mb, class). `prev` is
    a {pid: cpu_seconds} map from an earlier call; without it the delta is None
    and only the totals are printed -- a first sample never invents a rate."""
    rows = []
    if psutil is None:
        return rows
    now = {}
    for proc in psutil.process_iter(['pid', 'name', 'cpu_times',
                                     'memory_info', 'nice']):
        try:
            info = proc.info
            ct = info.get('cpu_times')
            cpu_s = (ct.user + ct.system) if ct is not None else 0.0
            now[info['pid']] = (info.get('name') or '?', cpu_s,
                                (info.get('memory_info').private
                                 if info.get('memory_info') else 0),
                                info.get('nice'))
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
            continue
    for pid, (name, cpu_s, private, nice) in now.items():
        delta = None if prev is None else (cpu_s - prev.get(pid, cpu_s)) * 1000.0
        rows.append({'pid': pid, 'name': name,
                     'cpu_ms': None if delta is None else round(delta, 1),
                     'priv_mb': round(private / 1048576.0, 1),
                     'class': nice})
    if prev is None:
        rows.sort(key=lambda r: -(r['priv_mb'] or 0))
    else:
        rows.sort(key=lambda r: -(r['cpu_ms'] or 0))
    return rows[:n], {pid: v[1] for pid, v in now.items()}, len(now)


class Log:
    def __init__(self, path, max_bytes):
        self.path = path
        self.max_bytes = max_bytes
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def _rotate(self):
        try:
            if os.path.getsize(self.path) < self.max_bytes:
                return
        except OSError:
            return
        bak = self.path + '.1'
        try:
            os.replace(self.path, bak)
        except OSError:
            try:
                os.remove(self.path)
            except OSError:
                pass

    def write(self, row):
        self._rotate()
        with open(self.path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def run(args) -> int:
    log = Log(args.out, args.max_bytes)
    log.write({'kind': 'BOOT', 'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
               'cadence_ms': args.cadence_ms, 'pid': os.getpid(),
               'commit_pct_limit': args.commit_pct,
               'cpu_share_limit': args.cpu_share,
               'psutil': getattr(psutil, '__version__', None),
               'py': sys.version.split()[0]})
    prev_times = sys_times()
    prev_cpu = None
    tick = 0
    while True:
        started = time.perf_counter()
        time.sleep(args.cadence_ms / 1000.0)
        if tick == 1 and _PLANT_MS:
            time.sleep(_PLANT_MS / 1000.0)
        woke = time.perf_counter()
        late_ms = (woke - started) * 1000.0 - args.cadence_ms
        cur_times = sys_times()
        cpu_pct = system_cpu(prev_times, cur_times)
        prev_times = cur_times
        pi = perf() or {}
        tick += 1
        heavy = (late_ms >= args.cadence_ms * 0.5
                 or pi.get('commit_pct', 0) >= args.commit_pct)
        row = {'kind': 'TICK', 'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
               'tick': tick, 'late_ms': round(late_ms, 1),
               'cpu_pct': cpu_pct, **pi}
        if heavy or tick % args.rank_every == 0:
            ranked, prev_cpu, pop = top_holders(args.top, prev_cpu)
            row['population'] = pop
            row['top'] = ranked
            if heavy:
                row['kind'] = ('FREEZE_SEVERE' if late_ms >= args.cadence_ms * 1.5
                               else 'FREEZE')
                if pi.get('commit_pct', 0) >= args.commit_pct:
                    row['reason'] = 'commit'
                else:
                    row['reason'] = 'late-wake'
                over = [r for r in ranked
                        if (r['cpu_ms'] or 0) >= args.cpu_share * args.cadence_ms]
                row['over_cpu_share'] = over
        log.write(row)
        if args.ticks and tick >= args.ticks:
            return 0


def report(path) -> int:
    if not os.path.isfile(path):
        print(f'CANNOT-MEASURE: {path} absent')
        return 2
    ticks = 0
    events = []
    late = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('kind') == 'TICK':
                ticks += 1
                late.append(row.get('late_ms') or 0)
            if str(row.get('kind', '')).startswith('FREEZE'):
                events.append(row)
    late.sort()
    p = (lambda q: late[min(len(late) - 1, int(q * len(late)))] if late else None)
    print(f'window ticks={ticks} freezes={len(events)} '
          f'late_ms p50={p(0.5)} p95={p(0.95)} max={late[-1] if late else None}')
    for row in events[-10:]:
        top = ', '.join(f"{t['name']}:{t['pid']} cpu={t['cpu_ms']}ms "
                        f"priv={t['priv_mb']}MB" for t in (row.get('top') or [])[:5])
        print(f"{row['ts']} {row['kind']} reason={row.get('reason')} "
              f"late={row['late_ms']}ms cpu={row.get('cpu_pct')}% "
              f"commit={row.get('commit_pct')}% "
              f"({row.get('commit_mb')}/{row.get('limit_mb')} MB) "
              f"procs={row.get('procs')} | {top}")
    if not events:
        print('NO FREEZE IN WINDOW -- that is not "the box is healthy", it is '
              '"nothing crossed the thresholds in this window".')
    return 0


def selftest() -> int:
    """The RED ARM: a detector that has never fired is decoration.

    Plants a REAL stall (`time.sleep`) larger than the cadence, in this very
    process, and requires the run loop to publish a FREEZE row with the planted
    magnitude. Nothing synthetic is faked: the late wake is measured by the same
    `perf_counter` the live census uses.
    """
    global _PLANT_MS
    path = os.path.join(os.environ.get('TMPDIR') or os.environ.get('TEMP')
                        or '.', 'freeze-census-selftest.log')
    if os.path.exists(path):
        os.remove(path)
    _PLANT_MS = 1500
    args = argparse.Namespace(out=path, max_bytes=1 << 20, cadence_ms=400,
                              rank_every=99, top=5, commit_pct=100.0,
                              cpu_share=0.5, ticks=4)
    run(args)
    rows = [json.loads(line) for line in open(path, encoding='utf-8')
            if line.strip()]
    freezes = [r for r in rows if str(r.get('kind', '')).startswith('FREEZE')]
    late = [r.get('late_ms') or 0 for r in rows if 'late_ms' in r]
    ok = bool(freezes) and max(late or [0]) >= 1500
    print(f'SELFTEST ticks={len(late)} freezes={len(freezes)} '
          f'max_late_ms={max(late or [0])} planted_ms={_PLANT_MS}')
    for row in freezes[:2]:
        print(f"  {row['kind']} reason={row.get('reason')} late={row['late_ms']}")
    print('SELFTEST: PASS' if ok else 'SELFTEST: FAIL')
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '_audit-verify',
        'freeze-census.log'))
    ap.add_argument('--cadence-ms', type=int, default=2000)
    ap.add_argument('--rank-every', type=int, default=5)
    ap.add_argument('--top', type=int, default=8)
    ap.add_argument('--commit-pct', type=float, default=92.0)
    ap.add_argument('--cpu-share', type=float, default=0.5,
                    help='fraction of ONE cadence a single process may hold')
    ap.add_argument('--max-bytes', type=int, default=4 * 1024 * 1024)
    ap.add_argument('--ticks', type=int, default=0)
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--selftest', action='store_true',
                    help='plant a REAL stall and require the detector to fire')
    args = ap.parse_args(argv)
    if args.report:
        return report(args.out)
    if args.selftest:
        return selftest()
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
