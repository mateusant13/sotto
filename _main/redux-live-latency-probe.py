#!/usr/bin/env python
"""redux-live-latency-probe.py -- does the Redux LIVE engine track real time, or diverge?

WHAT IT MEASURES, and why each number is the number it is
--------------------------------------------------------
`worker/sotto_worker.py`'s `FileTap` calls `on_block` "once per `block_ms` of
audio on a wall-clock schedule" (its own docstring), so a `--wav` run consumes
audio at REAL TIME and the WAV's position IS the wall clock. That is what makes
this instrument possible without touching the owner's audio endpoint (his worker
29008 holds it, and a live stream is playing):

    lag = t_wall(caption arrived) - caption["end"]

`end` is the audio second the engine had covered when it wrote the line, so `lag`
is exactly "how long after that audio played did the text exist". A lag that is
flat in `end` means the engine tracks real time; a lag that grows with `end` means
it is falling behind and the delay diverges. The slope of a least-squares fit of
`lag` against `end` is therefore the verdict, not an impression.

THE THREE ARMS OF THE MACHINE, all sampled by ONE `Get-Process` call (never
`Win32_Process` in a loop -- the house rule):
  * the CHILD (the live engine): peak RSS, mean CPU.
  * the OWNER's pids 28428 (shell) / 29008 (worker), sampled only -- never touched.
  * EVERY process: the total CPU-seconds burned, which is the system load the
    engine has to compete with. `Get-Counter '\\Processor(_Total)\\...'` FAILS on
    this box (measured), so the sum of `Get-Process .CPU` deltas is the instrument.

NO AUDIO DEVICE IS OPENED. The source is a WAV, by construction.

Usage:
    py -3 _main/redux-live-latency-probe.py --engine onnx --max-seconds 20
    py -3 _main/redux-live-latency-probe.py --engine ternary --max-seconds 20 --json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORKER = ROOT / "worker" / "redux_live.py"
OWNER_PIDS = (28428, 29008)
CREATE_NO_WINDOW = 0x08000000


def utf8_streams() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# The process sampler. ONE `Get-Process` per sample, in ONE pwsh call, on its own
# thread so the 20 ms caption poll is never stalled by it.
# ---------------------------------------------------------------------------

PS_SAMPLE = r"""
$ErrorActionPreference='SilentlyContinue'
$all = (Get-Process | Measure-Object -Property CPU -Sum).Sum
$child = Get-Process -Id {child} -ErrorAction SilentlyContinue
$o1 = Get-Process -Id {o1} -ErrorAction SilentlyContinue
$o2 = Get-Process -Id {o2} -ErrorAction SilentlyContinue
[pscustomobject]@{{
  rss = if ($child) {{ [int64]$child.WorkingSet64 }} else {{ -1 }}
  cpu = if ($child) {{ [double]$child.CPU }} else {{ -1 }}
  all = [double]$all
  owner1 = if ($o1) {{ [double]$o1.CPU }} else {{ -1 }}
  owner2 = if ($o2) {{ [double]$o2.CPU }} else {{ -1 }}
}} | ConvertTo-Json -Compress
"""


class Sampler(threading.Thread):
    """Samples the child + the whole machine on a wall-clock cadence."""

    def __init__(self, child_pid: int, cadence_s: float) -> None:
        super().__init__(name="sampler", daemon=True)
        self.child_pid = child_pid
        self.cadence_s = cadence_s
        self.samples: list[dict] = []
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        script = PS_SAMPLE.format(child=self.child_pid, o1=OWNER_PIDS[0], o2=OWNER_PIDS[1])
        while not self._halt.is_set():
            t = time.perf_counter()
            try:
                out = subprocess.run(
                    ["pwsh", "-NoProfile", "-Command", script],
                    capture_output=True, text=True, timeout=20,
                ).stdout.strip()
                row = json.loads(out) if out else None
            except Exception as exc:  # a failed sample is a HOLE, recorded as one
                row = {"error": str(exc)[:120]}
            if row is not None:
                row["t"] = t
                self.samples.append(row)
            sleep = self.cadence_s - (time.perf_counter() - t)
            if sleep > 0:
                self._halt.wait(sleep)


# ---------------------------------------------------------------------------
# The caption reader. The child writes JSONL to a FILE (not a pipe), so there is
# no stdio plumbing to break; we poll the file and stamp each line on arrival.
# ---------------------------------------------------------------------------


def read_captions(path: Path, stop: threading.Event, poll_s: float) -> list[dict]:
    """Every JSON line, stamped with the wall time it BECAME VISIBLE in the file."""
    events: list[dict] = []
    offset = 0
    buf = ""
    while True:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                chunk = fh.read()
                offset = fh.tell()
        except OSError:
            chunk = ""
        if chunk:
            buf += chunk
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                obj["_t_wall"] = time.perf_counter()
                events.append(obj)
        if stop.is_set() and not chunk:
            # one last drain
            try:
                with path.open("r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(offset)
                    tail = fh.read()
            except OSError:
                tail = ""
            for line in tail.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                obj["_t_wall"] = time.perf_counter()
                events.append(obj)
            return events
        stop.wait(poll_s)


def slope(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope of ys against xs. Flat => tracks real time."""
    n = len(xs)
    if n < 3:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else float("nan")


def main(argv=None) -> int:
    utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", default="onnx", choices=("onnx", "ternary"))
    ap.add_argument("--wav", default=str(HERE / "pt-br-sample.wav"))
    ap.add_argument("--max-seconds", type=float, default=20.0)
    ap.add_argument("--window-s", type=float, default=None, help="omit => the worker's default")
    ap.add_argument("--step-s", type=float, default=None, help="omit => the worker's default")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--poll-ms", type=float, default=20.0)
    ap.add_argument("--sample-ms", type=float, default=1000.0)
    ap.add_argument("--out", default=None, help="where the child's JSONL is written")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    out_path = Path(args.out) if args.out else HERE / f"redux-live-latency-{args.engine}.jsonl"
    if out_path.exists():
        out_path.unlink()

    cmd = [sys.executable, str(WORKER), "--engine", args.engine, "--wav", str(args.wav),
           "--max-seconds", str(args.max_seconds), "--threads", str(args.threads)]
    if args.window_s is not None:
        cmd += ["--window-s", str(args.window_s)]
    if args.step_s is not None:
        cmd += ["--step-s", str(args.step_s)]

    ncores = os.cpu_count() or 1
    print(f"# redux-live-latency-probe  engine={args.engine}  wav={Path(args.wav).name} "
          f"max_seconds={args.max_seconds}  threads={args.threads}  cores={ncores}")
    print(f"# child: {' '.join(cmd[1:])}")
    print(f"# NOTE: no audio device is opened -- FileTap on a WAV, paced at real time.")

    t0 = time.perf_counter()
    with out_path.open("wb") as sink:
        proc = subprocess.Popen(cmd, stdout=sink, stderr=subprocess.PIPE,
                                cwd=str(ROOT), creationflags=CREATE_NO_WINDOW)
        sampler = Sampler(proc.pid, args.sample_ms / 1000.0)
        sampler.start()
        stop = threading.Event()
        captions: list[dict] = []
        reader = threading.Thread(
            target=lambda: captions.extend(
                read_captions(out_path, stop, args.poll_ms / 1000.0)),
            name="reader", daemon=True,
        )
        reader.start()
        try:
            rc = proc.wait(timeout=args.max_seconds + 240)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = -1
        stop.set()
        reader.join(timeout=10)
        sampler.stop()
        sampler.join(timeout=10)
        err = b""
        if proc.stderr is not None:
            try:
                err = proc.stderr.read()
            except Exception:
                err = b""
        proc.stderr.close() if proc.stderr else None
    wall = time.perf_counter() - t0

    caps = [c for c in captions if c.get("type") == "caption"]
    finals = [c for c in caps if c.get("final") is True]
    # `_t_wall` is `time.perf_counter()` (monotonic since BOOT); `end` is an audio
    # second. Subtracting one from the other directly gives ~17300 s on this box --
    # a first run of this probe printed exactly that. Both are put on the same
    # origin here.
    #
    # The origin is `capture-started`, NOT the spawn: the model load (~1-3 s) and
    # the ONNX session build happen BEFORE the tap opens, so audio second 0 begins
    # at that line, and using `t0` would add the whole load time to every latency
    # as a constant offset. The offset would not move the slope, but it would
    # corrupt the absolute number, which is the one the brief asks for.
    started = [c for c in captions if c.get("state") == "capture-started"]
    origin = started[0]["_t_wall"] if started else t0
    for c in caps:
        c["_t_run"] = round(c["_t_wall"] - origin, 3)
        c["_lag"] = round(c["_t_run"] - float(c.get("end") or 0.0), 3)

    # The child's own `done` line -- `type=status, state=done`. Its window
    # telemetry is the only place the hard cap can be checked from outside.
    dones = [c for c in captions if c.get("state") == "done"]
    done = dones[-1] if dones else {}

    # ---- latency: does lag grow with the audio position? ---------------------
    fx = [float(c.get("end") or 0.0) for c in finals]
    fy = [float(c["_lag"]) for c in finals]
    fin_slope = slope(fx, fy)
    lags = [float(c["_lag"]) for c in caps]
    first_lag = lags[0] if lags else float("nan")
    last_lag = lags[-1] if lags else float("nan")

    # ---- the child's own cost -----------------------------------------------
    good = [s for s in sampler.samples if s.get("rss", -1) >= 0]
    rss = [s["rss"] / (1024 * 1024) for s in good]
    cpu_pairs = [(s["t"], s["cpu"]) for s in good if s.get("cpu", -1) >= 0]
    cpu_s = 0.0
    cpu_span = 0.0
    if len(cpu_pairs) >= 2:
        cpu_s = cpu_pairs[-1][1] - cpu_pairs[0][1]
        cpu_span = cpu_pairs[-1][0] - cpu_pairs[0][0]
    cpu_pct_1core = (cpu_s / cpu_span * 100.0) if cpu_span > 0 else float("nan")

    # ---- the machine --------------------------------------------------------
    all_pairs = [(s["t"], s["all"]) for s in sampler.samples if "all" in s]
    sys_cpu_s = sys_span = 0.0
    if len(all_pairs) >= 2:
        sys_cpu_s = all_pairs[-1][1] - all_pairs[0][1]
        sys_span = all_pairs[-1][0] - all_pairs[0][0]
    cores_busy = (sys_cpu_s / sys_span) if sys_span > 0 else float("nan")

    # ---- the owner's processes, sampled only --------------------------------
    def owner_delta(idx: int) -> float:
        key = f"owner{idx}"
        pairs = [(s["t"], s[key]) for s in sampler.samples if s.get(key, -1) >= 0]
        return (pairs[-1][1] - pairs[0][1]) if len(pairs) >= 2 else float("nan")

    owner1 = owner_delta(1)
    owner2 = owner_delta(2)

    result = {
        "engine": args.engine,
        "rc": rc,
        "wall_s": round(wall, 2),
        "audio_covered_s": finals[-1]["end"] if finals else None,
        "captions": len(caps),
        "finals": len(finals),
        # The window cap is a MEASURED property of the run, not a claim: the child
        # publishes `max_window_s` in its own `done` line and it must never exceed
        # the configured window. `backlog_s` is the queue depth at the end -- with
        # the cap in force a late pass queues audio, so a non-zero backlog at exit
        # is the honest shape of "the box could not keep up".
        "window_s": done.get("window_s"),
        "step_s": done.get("step_s"),
        "max_window_s": done.get("max_window_s"),
        "backlog_s": done.get("backlog_s"),
        "overruns": done.get("overruns"),
        "passes": done.get("passes"),
        "latency": {
            "first_partial_lag_s": first_lag,
            "last_partial_lag_s": last_lag,
            "final_lag_min_s": min(fy) if fy else None,
            "final_lag_max_s": max(fy) if fy else None,
            "final_lag_mean_s": round(statistics.mean(fy), 3) if fy else None,
            "final_lag_slope_per_audio_s": (round(fin_slope, 4)
                                           if fin_slope == fin_slope else None),
        },
        "child": {
            "rss_first_mb": round(rss[0], 1) if rss else None,
            "rss_last_mb": round(rss[-1], 1) if rss else None,
            "rss_peak_mb": round(max(rss), 1) if rss else None,
            "cpu_s": round(cpu_s, 2),
            "mean_pct_of_one_core": round(cpu_pct_1core, 1) if cpu_pct_1core == cpu_pct_1core else None,
            "mean_pct_of_all_cores": (round(cpu_pct_1core / ncores, 1)
                                      if cpu_pct_1core == cpu_pct_1core else None),
        },
        "system": {
            "cpu_s": round(sys_cpu_s, 2),
            "cores_busy": round(cores_busy, 2) if cores_busy == cores_busy else None,
            "pct_of_all_cores": (round(cores_busy / ncores * 100.0, 1)
                                 if cores_busy == cores_busy else None),
        },
        "owner": {
            "shell_28428_cpu_s": round(owner1, 2) if owner1 == owner1 else None,
            "worker_29008_cpu_s": round(owner2, 2) if owner2 == owner2 else None,
        },
        "samples": len(sampler.samples),
        "stderr_tail": err.decode("utf-8", "replace")[-1500:],
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\nrc={rc}  wall={wall:.1f}s  audio covered={result['audio_covered_s']}s  "
              f"captions={len(caps)} ({len(finals)} final)")
        if fy:
            print(f"  LATENCY  first partial {first_lag:+.2f}s -> last {last_lag:+.2f}s | "
                  f"finals min {min(fy):+.2f} max {max(fy):+.2f} "
                  f"mean {statistics.mean(fy):+.2f}s | slope {fin_slope:+.3f} s per audio-s")
        else:
            print(f"  LATENCY  NO FINAL CAPTION -> the slope cannot be computed "
                  f"(first partial lag {first_lag:+.2f}s, last {last_lag:+.2f}s)")
        print(f"  WINDOW   configured {result['window_s']}s step {result['step_s']}s | "
              f"largest decoded window {result['max_window_s']}s | "
              f"backlog at end {result['backlog_s']}s | overruns "
              f"{result['overruns']}/{result['passes']} passes")
        print(f"  CHILD    rss first {result['child']['rss_first_mb']} -> peak "
              f"{result['child']['rss_peak_mb']} MB | cpu {cpu_s:.1f} CPU-s over "
              f"{cpu_span:.1f}s = {result['child']['mean_pct_of_one_core']}% of one core, "
              f"{result['child']['mean_pct_of_all_cores']}% of {ncores}")
        print(f"  SYSTEM   {sys_cpu_s:.1f} CPU-s over {sys_span:.1f}s = {cores_busy:.2f} of "
              f"{ncores} cores busy ({result['system']['pct_of_all_cores']}%)")
        print(f"  OWNER    shell 28428 burned {owner1:.1f} CPU-s, worker 29008 burned "
              f"{owner2:.1f} CPU-s during this run (sampled, never touched)")
        if err.strip():
            print(f"  stderr tail: {result['stderr_tail'][-400:]}")

    # ---- verdict -------------------------------------------------------------
    flat = (fin_slope == fin_slope) and abs(fin_slope) < 0.15
    if rc != 0:
        verdict = "FAILED-RUN"
    elif not finals:
        verdict = "NO-CAPTIONS"
    elif flat and last_lag < 3.0:
        verdict = "TRACKS-REAL-TIME"
    elif not flat:
        verdict = f"DIVERGES (lag grows {fin_slope:+.2f} s per audio-s)"
    else:
        verdict = f"TRACKS-BUT-LAGGY (last partial {last_lag:+.2f}s behind)"
    print(f"\nVERDICT {verdict}")
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
