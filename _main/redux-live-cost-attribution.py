#!/usr/bin/env python3
"""Is the live decode cost MINE, or is the machine taking it away from me?

WHY THIS FILE EXISTS
--------------------
Two measurements of the SAME ONNX Redux model disagreed by 2-5x, and the brief's
whole design turns on that number:

  * ``_main/redux-engine-cost-probe.py``  15 s in **1.80 s** (8.33x real time)
  * ``_main/redux-live-window-probe.py``  15 s in **4.05 s** (3.71x real time)

A factor of 2.2 is not noise; it is either (a) a STEADY-STATE penalty that the
single-call batch measurement cannot see, (b) CONTENTION from the owner's live app
(28428/29008), or (c) a thread-count effect -- and the three need different fixes,
so guessing is not available.

HOW IT SEPARATES THEM
---------------------
It reports, per call, BOTH wall time and ``time.process_time()`` (CPU seconds this
process burned). The pair is the instrument:

  * wall high, cpu low   -> DESCHEDULED: the machine took the time, not the model
  * wall ~= cpu, both high -> the model really is that slow at this thread count
  * the FIRST call fast, the rest slow -> a STEADY-STATE penalty after warm-up

and it samples the owner's own processes (28428/29008) before and after every arm,
so "the machine was busy" is a measurement rather than an excuse. It touches
NOTHING: it reads ``Get-Process`` CPU counters only.

BUDGET: <= 2 threads for the measurement arms. ``--threads`` may be raised to
characterise the thread-count effect, and every such arm is labelled NOT-BUDGET.

Usage:
    py -3 _main/redux-live-cost-attribution.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKER = HERE.parent / "worker"
WAV = HERE / "pt-br-sample.wav"
ONNX_DIR = WORKER / "models" / "parakeet-redux-onnx-int4"
REF_DIR = WORKER / "models" / "parakeet-redux-reference"

sys.path.insert(0, str(REF_DIR))

#: The owner's app. NEVER touched -- only its CPU counter is read.
OWNER_PIDS = (28428, 29008)


def _log(msg: str) -> None:
    print(msg, flush=True)


def _utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (ValueError, OSError):
                pass


def owner_cpu_snapshot() -> dict:
    """CPU seconds consumed by the owner's processes, read from Get-Process.

    ``Get-Process`` (not WMI): the house rule forbids ``Get-CimInstance
    Win32_Process`` in a loop because WMI serialises the system, and a probe that
    slows the thing it measures is not a probe.
    """
    script = (
        "$out=@();"
        "foreach($id in @(" + ",".join(str(p) for p in OWNER_PIDS) + ")){"
        "$p=Get-Process -Id $id -ErrorAction SilentlyContinue;"
        "if($p){$out+=[pscustomobject]@{id=$p.Id;cpu=$p.CPU;ws=[math]::Round($p.WorkingSet64/1MB,1)}}};"
        "$out|ConvertTo-Json -Compress"
    )
    try:
        raw = subprocess.run(["pwsh", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        if not raw:
            return {}
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = [parsed]
        return {int(item["id"]): item for item in parsed}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def main(argv=None) -> int:
    _utf8_streams()
    parser = argparse.ArgumentParser(
        prog="redux-live-cost-attribution",
        description="Attribute the live decode cost: steady state, contention, or threads.")
    parser.add_argument("--threads", default="1,2,4", help="thread counts to characterise")
    parser.add_argument("--seconds", type=float, default=5.0, help="audio seconds per call")
    parser.add_argument("--calls", type=int, default=6, help="calls per thread count")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    import transcribe as reference

    pcm = reference.read_audio(WAV)[: int(args.seconds * 16000)]
    _log(f"redux-live-cost-attribution  audio={pcm.size / 16000:.2f} s per call, "
         f"calls={args.calls} each")
    _log(f"  owner pids watched (READ ONLY): {OWNER_PIDS}")

    results = []
    for threads in [int(x) for x in str(args.threads).split(",") if x.strip()]:
        budget = "" if threads <= 2 else "   <-- NOT the house budget"
        _log("")
        _log(f"threads={threads}{budget}")
        before = owner_cpu_snapshot()
        model = reference.OnnxParakeet(ONNX_DIR, threads=threads)
        wall = []
        cpu = []
        _log(f"  {'call':>5} {'wall_s':>8} {'cpu_s':>8} {'wall/cpu':>9} {'xRT(wall)':>10}  text")
        for index in range(args.calls):
            t0, c0 = time.perf_counter(), time.process_time()
            result = model.transcribe(pcm, "segment")
            w, c = time.perf_counter() - t0, time.process_time() - c0
            wall.append(w)
            cpu.append(c)
            ratio = w / c if c else float("inf")
            _log(f"  {index + 1:>5} {w:>8.3f} {c:>8.3f} {ratio:>9.2f} "
                 f"{args.seconds / w:>10.2f}  {str(result.get('text') or '')[:44]!r}")
        after = owner_cpu_snapshot()
        owner_delta = {}
        for pid in OWNER_PIDS:
            b, a = before.get(pid), after.get(pid)
            if isinstance(b, dict) and isinstance(a, dict):
                owner_delta[pid] = round(float(a["cpu"]) - float(b["cpu"]), 2)
        row = {
            "threads": threads,
            "wall_s": [round(x, 3) for x in wall],
            "cpu_s": [round(x, 3) for x in cpu],
            "first_wall_s": round(wall[0], 3),
            "steady_wall_s": round(sum(wall[1:]) / len(wall[1:]), 3) if len(wall) > 1 else None,
            "steady_over_first": round((sum(wall[1:]) / len(wall[1:])) / wall[0], 2)
                                 if len(wall) > 1 and wall[0] else None,
            "mean_wall_over_cpu": round(sum(wall) / sum(cpu), 2) if sum(cpu) else None,
            "owner_cpu_s_during_arm": owner_delta,
        }
        results.append(row)
        _log(f"  first={row['first_wall_s']}s  steady={row['steady_wall_s']}s  "
             f"steady/first={row['steady_over_first']}x  "
             f"mean wall/cpu={row['mean_wall_over_cpu']}  "
             f"owner_cpu_s_during_arm={owner_delta}")

    _log("")
    _log("VERDICT")
    for row in results:
        verdict = []
        if row["steady_over_first"] and row["steady_over_first"] > 1.4:
            verdict.append(f"STEADY-STATE penalty {row['steady_over_first']}x "
                           f"(first call is optimistic)")
        if row["mean_wall_over_cpu"] and row["mean_wall_over_cpu"] > 1.5:
            verdict.append(f"DESCHEDULED: wall/cpu={row['mean_wall_over_cpu']} "
                           f"(the machine, not the model)")
        else:
            verdict.append(f"CPU-bound: wall/cpu={row['mean_wall_over_cpu']}")
        owner = sum(v for v in (row["owner_cpu_s_during_arm"] or {}).values() if v)
        verdict.append(f"owner burned {owner:.1f} CPU-s during the arm")
        _log(f"  threads={row['threads']}: " + "; ".join(verdict))

    if args.json:
        print(json.dumps({"type": "result", "arms": results}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
