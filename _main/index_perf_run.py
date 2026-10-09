"""Run slice_scale_probe.py with the machine state declared beside its figures.

WHY THIS EXISTS
---------------
`_moved/aireplay/_main/slice_scale_probe.py` prints p50/p95/max/%-under-budget
without ever saying what machine produced them.  Measured consequence: the same
n=211200 run was recorded as a 3.3x miss in one window and a 4.7x miss in
another, and n=20000 read 5.34 ms on a quiet host and 15.14 ms on a 13-lane
one.  Those are not two facts about the code; they are one fact about the code
plus an undeclared amount of someone else's CPU.

The probe is NOT edited here -- its gate is owned and proven by another lane.
This runner wraps it instead: it samples the host before, during and after,
and prints that declaration in the same WINDOW/POPULATION vocabulary the probe
already uses, so a reader sees contamination without having to know to ask.

USAGE
-----
  python index_perf_run.py 211200            # 1 run
  python index_perf_run.py 211200 --runs 3   # spread over 3 runs
  python index_perf_run.py 20000 --runs 3

EXIT: 0 only if EVERY run passed the probe's own gate.  One failure is a
failure; a spread where the first run passed and the third failed is NOT a
pass, and this runner refuses to report it as one.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SRC_INDEX = ROOT / "_moved" / "aireplay" / "src" / "index"
PROBE = ROOT / "_moved" / "aireplay" / "_main" / "slice_scale_probe.py"

sys.path.insert(0, str(SRC_INDEX))
import store  # noqa: E402

# The probe's own figures, pulled back out of its stdout so the runner can
# build a spread.  These are the SAME strings the probe printed -- the runner
# never re-measures or re-rounds, it only re-reads what was already reported.
RE_SCALE = re.compile(r"^SCALE: n=(\d+) p50=([\d.]+)ms p95=([\d.]+)ms "
                      r"frac_under_16ms=([\d.]+)", re.M)
RE_UNDER = re.compile(r"^under 16 ms\s+: ([\d.]+)%", re.M)
RE_MAX = re.compile(r"^query ms\s+: min=([\d.]+) p50=([\d.]+) "
                    r"p95=([\d.]+) max=([\d.]+)", re.M)
RE_RESULT = re.compile(r"^RESULT: (PASS|FAIL)", re.M)


class LoadWatcher:
    """Samples host_load() on a thread so the DECLARATION covers the run window,
    not just its edges.  A box that is quiet before and busy during is the
    common case, so sampling only the start would under-report contention."""

    def __init__(self, interval: float = 2.0):
        self.interval = interval
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._t: threading.Thread | None = None

    def _loop(self):
        while not self._stop.is_set():
            self.samples.append(store.host_load(cpu_interval=0.25))
            self._stop.wait(self.interval)

    def __enter__(self):
        self.samples.append(store.host_load(cpu_interval=0.25))
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t:
            self._t.join(timeout=5)
        self.samples.append(store.host_load(cpu_interval=0.25))
        return False

    def summary(self) -> dict:
        """Worst case across the window -- a run is only as quiet as its
        busiest moment, so the MAX cpu_util is the honest number to quote."""
        s = self.samples
        cpu = [x["cpu_util_pct"] for x in s if x.get("cpu_util_pct") is not None]
        lanes = [x["concurrent_lanes"] for x in s
                 if x.get("concurrent_lanes") is not None]
        return {
            "cpu_util_pct_max": max(cpu) if cpu else None,
            "cpu_util_pct_min": min(cpu) if cpu else None,
            "cpu_util_pct_mean": (round(sum(cpu) / len(cpu), 1) if cpu else None),
            "concurrent_lanes_max": max(lanes) if lanes else None,
            "samples": len(s),
            "logical_cores": s[0]["logical_cores"] if s else None,
            "physical_cores": s[0]["physical_cores"] if s else None,
            "total_processes": s[0]["total_processes"] if s else None,
        }


def one_run(n: int, n_queries: int, chunk: int, quiet: bool):
    """One probe run with the load declaration wrapped around it. -> dict"""
    env = dict(os.environ)
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS"):
        env[v] = "2"
    print(f"\n{'=' * 78}\nRUN n={n} n_queries={n_queries} chunk={chunk}\n{'=' * 78}")
    t0 = time.strftime("%Y-%m-%d %H:%M:%S")
    with LoadWatcher() as w:
        t_start = time.perf_counter()
        p = subprocess.run([sys.executable, str(PROBE), str(n), str(n_queries),
                            str(chunk)], env=env, cwd=str(PROBE.parent),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        wall = time.perf_counter() - t_start
    out = p.stdout or ""
    if not quiet:
        sys.stdout.write(out)
        if p.stderr:
            sys.stderr.write(p.stderr)
    ld = w.summary()

    def grab(rx, i=0, cast=float):
        m = rx.search(out)
        return cast(m.group(i)) if m else None

    row = {
        "n": n, "rc": p.returncode, "passed": p.returncode == 0,
        "wall_s": round(wall, 1), "start": t0,
        "p50_ms": grab(RE_SCALE, 2), "p95_ms": grab(RE_SCALE, 3),
        "frac_under": grab(RE_SCALE, 4), "under_pct": grab(RE_UNDER, 1),
        "max_ms": grab(RE_MAX, 4), "min_ms": grab(RE_MAX, 1),
        "verdict": (RE_RESULT.search(out).group(1)
                    if RE_RESULT.search(out) else "?"),
        "load": ld,
    }
    print(f"rc={row['rc']} verdict={row['verdict']} "
          f"p50={row['p50_ms']} p95={row['p95_ms']} max={row['max_ms']} "
          f"under={row['under_pct']}%  wall={row['wall_s']}s")
    print(f"DECLARATION (WINDOW {t0}, POPULATION n={n}, {n_queries} queries, "
          f"<=2 threads): cpu {ld['cpu_util_pct_min']}-"
          f"{ld['cpu_util_pct_max']}% (mean {ld['cpu_util_pct_mean']}%) of "
          f"{ld['physical_cores']}p/{ld['logical_cores']}l, "
          f"<= {ld['concurrent_lanes_max']} concurrent lanes, "
          f"{ld['total_processes']} procs, {ld['samples']} samples")
    return row


def spread(rows, key):
    v = [r[key] for r in rows if r.get(key) is not None]
    if not v:
        return None
    return {"min": min(v), "max": max(v), "mean": round(sum(v) / len(v), 2)}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int, nargs="?", default=211200)
    ap.add_argument("--queries", type=int, default=100)
    ap.add_argument("--chunk", type=int, default=4096)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--quiet", action="store_true",
                    help="suppress probe stdout, keep only the summary")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    a = ap.parse_args(argv[1:])

    rows = [one_run(a.n, a.queries, a.chunk, a.quiet) for _ in range(a.runs)]

    print(f"\n{'=' * 78}\nSPREAD over {len(rows)} run(s) at "
          f"POPULATION n={a.n}, WINDOW {rows[0]['start']} -> "
          f"{time.strftime('%H:%M:%S')}, <=2 threads\n{'=' * 78}")
    print(f"{'run':>3} {'rc':>3} {'verdict':>7} {'p50':>8} {'p95':>8} {'max':>8} "
          f"{'under%':>7} {'cpu%max':>8} {'lanes':>5}")
    for i, r in enumerate(rows, 1):
        print(f"{i:>3} {r['rc']:>3} {r['verdict']:>7} {r['p50_ms']:>8} "
              f"{r['p95_ms']:>8} {r['max_ms']:>8} {r['under_pct']:>7} "
              f"{r['load']['cpu_util_pct_max']:>8} "
              f"{r['load']['concurrent_lanes_max']:>5}")
    for k, label in (("p50_ms", "p50 ms"), ("p95_ms", "p95 ms"),
                     ("max_ms", "max ms"), ("under_pct", "% under 16 ms")):
        s = spread(rows, k)
        if s:
            print(f"{label:>14}: min={s['min']} max={s['max']} mean={s['mean']}")
    cpu = spread([r["load"] for r in rows], "cpu_util_pct_max")
    if cpu:
        print(f"{'cpu% max':>14}: min={cpu['min']} max={cpu['max']} "
              f"mean={cpu['mean']}  <-- the contamination axis")

    all_pass = all(r["passed"] for r in rows)
    verdict = "ALL RUNS PASS" if all_pass else "AT LEAST ONE RUN FAILED"
    print(f"\nVERDICT: {verdict} ({sum(r['passed'] for r in rows)}/{len(rows)} "
          f"runs met the probe's own gate)")
    print("NOTE: a PASS above is a statement about the host too. Re-read the "
          "cpu% max column before treating it as a property of the code.")

    if a.json:
        a.json.write_text(json.dumps({"n": a.n, "rows": rows,
                                     "all_pass": all_pass}, indent=2),
                         encoding="utf-8")
        print(f"wrote {a.json}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))