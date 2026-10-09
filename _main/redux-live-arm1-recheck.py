#!/usr/bin/env python
"""redux-live-arm1-recheck.py -- is ARM 1's cost table the MODEL or the MACHINE?

WHY THIS FILE EXISTS. Two instruments measured the same thing and disagreed by 8x:

    _main/redux-live-window-probe.py ARM 1 (12:28, one shared session):
        2 s -> 2.557 s | 3 s -> 3.820 s | 5 s -> 10.774 s | 8 s -> 22.493 s
    _main/redux-live-cost-attribution.py  (12:55, fresh process, 4x 5 s calls):
        5 s -> 1.523 / 1.103 / 1.271 / 1.485 s

Same reader (`transcribe.read_audio`), same model, same `transcribe(pcm, "segment")`,
same `threads=2`, same 5 s of the same WAV. One of the two is measuring something
other than the model.

THE DISCRIMINATOR IS `time.process_time()`, and that is the whole point of this
file: CPU-seconds burned by this process do NOT depend on how much of the machine
the OS hands us. Wall time does. So per call this prints BOTH and their ratio:

    wall ~= cpu        the call really costs that much CPU  -> the MODEL is the cost
    wall >> cpu        we were DESCHEDULED                  -> the MACHINE is the cost

It replays ARM 1's exact sequence (2, 3, 5, 8 s, one session, one call each) and
then repeats it a second time in the SAME process, so the two passes differ only in
how warmed the session is -- which separates "the model degrades across calls" from
"the machine was busy".

Usage:
    py -3 -u _main/redux-live-arm1-recheck.py --threads 2
    py -3 -u _main/redux-live-arm1-recheck.py --threads 2 --passes 3 --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WAV = HERE / "pt-br-sample.wav"


def utf8_streams() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            pass


def main(argv=None) -> int:
    utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--windows", default="2,3,5,8")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    windows = [float(w) for w in args.windows.split(",") if w.strip()]
    sys.path.insert(0, str(ROOT / "worker"))
    sys.path.insert(0, str(ROOT / "worker" / "models" / "parakeet-redux-reference"))

    import transcribe as reference  # the SAME module redux_live.OnnxBackend imports

    pcm_all = reference.read_audio(WAV)
    print(f"# redux-live-arm1-recheck  wav={WAV.name}  {pcm_all.size} samples = "
          f"{pcm_all.size / 16000:.2f} s  threads={args.threads}  passes={args.passes}")
    print("# loading the model once, the way redux_live.OnnxBackend does")
    t0 = time.perf_counter()
    model = reference.OnnxParakeet(ROOT / "worker" / "models" / "parakeet-redux-onnx-int4",
                                   threads=args.threads)
    print(f"# loaded in {time.perf_counter() - t0:.2f} s")

    rows = []
    for p in range(1, args.passes + 1):
        print(f"\npass {p}  (same session; pass 1 is the coldest)")
        print(f"  {'window_s':>8} {'wall_s':>8} {'cpu_s':>8} {'wall/cpu':>9} {'xRT':>6}  text")
        for seconds in windows:
            chunk = pcm_all[: int(seconds * 16000)]
            c0 = time.process_time()
            w0 = time.perf_counter()
            result = model.transcribe(chunk, "segment")
            wall = time.perf_counter() - w0
            cpu = time.process_time() - c0
            ratio = wall / cpu if cpu else float("nan")
            rows.append({"pass": p, "window_s": round(len(chunk) / 16000.0, 2),
                         "wall_s": round(wall, 3), "cpu_s": round(cpu, 3),
                         "wall_per_cpu": round(ratio, 2),
                         "x_realtime": round((len(chunk) / 16000.0) / wall, 2) if wall else None,
                         "text": str(result.get("text") or "").strip()})
            print(f"  {rows[-1]['window_s']:>8.2f} {wall:>8.3f} {cpu:>8.3f} {ratio:>9.2f} "
                  f"{rows[-1]['x_realtime']:>6.2f}  {rows[-1]['text'][:58]!r}")

    # ---- verdict: the MODEL's cost is the cpu_s column, not the wall column ----
    print("\nVERDICT")
    by_window: dict[float, list[dict]] = {}
    for r in rows:
        by_window.setdefault(r["window_s"], []).append(r)
    worst = max(rows, key=lambda r: r["wall_per_cpu"])
    cpu_per_audio = {w: sum(x["cpu_s"] for x in rs) / len(rs) / w
                     for w, rs in sorted(by_window.items())}
    print(f"  CPU-seconds per audio-second (the MODEL, contention-proof): "
          + "  ".join(f"{w:g}s={v:.2f}" for w, v in cpu_per_audio.items()))
    print(f"  worst wall/cpu = {worst['wall_per_cpu']} at window {worst['window_s']}s "
          f"(pass {worst['pass']})")
    for w, rs in sorted(by_window.items()):
        walls = [x["wall_s"] for x in rs]
        cpus = [x["cpu_s"] for x in rs]
        print(f"  window {w:g}s: wall {min(walls):.3f}..{max(walls):.3f} "
              f"({max(walls) / min(walls):.1f}x spread)  "
              f"cpu {min(cpus):.3f}..{max(cpus):.3f} ({max(cpus) / min(cpus):.1f}x spread)")
    spread = max(r["wall_s"] for r in rows) / min(r["wall_s"] for r in rows)
    print(f"  wall spread across ALL rows: {spread:.1f}x")
    if spread > 3:
        print("  => the WALL numbers are dominated by machine contention: a table built from "
              "one wall measurement is a table of the machine's mood, not of the model.")
    print("VERDICT DONE")
    if args.json:
        print(json.dumps({"rows": rows, "cpu_per_audio_s": cpu_per_audio}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
