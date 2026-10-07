#!/usr/bin/env pythonw
"""asr02-threadprobe.py -- is the thread pin REAL, measured from inside the product's engine?

The product's central claim (`specs/02-asr.md` section 2) is `intra_op_num_threads = 4`,
`inter_op = 1`, and the reason it is a CONTRACT is that lane 11 measured CPU% exactly equal to
N (`docs/research/11-onnx-threads.md:27`). This probe checks the product's own engine, not the
lane's: it loads through `asr.engine.OnnxAsrEngine`, runs the SAME 10 s chunk at 1 and at 4
threads, and polls the process's own CPU% at 250 ms during the INFERENCE phase only (the phase
split of `_main/probe-onnx-asr-threads.py:117-132`).

No audio device, no window (`pythonw`, and this script spawns nothing).
"""

from __future__ import annotations

import json
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(r"H:\aireplay")
sys.path.insert(0, str(ROOT / "src"))

from asr.constants import MODEL_DIR  # noqa: E402
from asr.engine import OnnxAsrEngine, pin_thread_env  # noqa: E402

WAV = Path(r"H:\sotto\_main\_redux-long\plain-3600s.wav")
OFFSET, CHUNK, REPS = 900.0, 10.0, 3
OUT = ROOT / "_main" / "logs" / "asr02-threadprobe.json"
LOG = ROOT / "_main" / "logs" / "asr02-threadprobe.log"
LINES: list[str] = []


def say(m: str) -> None:
    LINES.append(m)


def main() -> int:
    import psutil

    from asr.audio import read_slice

    x = read_slice(WAV, OFFSET, CHUNK * REPS)
    chunk = int(CHUNK * 16000)
    proc = psutil.Process()
    results = []

    for threads in (1, 4):
        pin_thread_env(threads)
        engine = OnnxAsrEngine(model_dir=MODEL_DIR, intra_op_num_threads=threads, inter_op_num_threads=1)
        load_s = engine.load()
        samples: list[float] = []
        stop = threading.Event()

        def poll() -> None:
            proc.cpu_percent(None)
            while not stop.is_set():
                samples.append(proc.cpu_percent(None))
                stop.wait(0.25)

        th = threading.Thread(target=poll, daemon=True)
        th.start()
        t0 = time.perf_counter()
        texts = []
        for i in range(REPS):
            a = x[i * chunk : (i + 1) * chunk]
            texts.append(engine.recognize(a))
        wall = time.perf_counter() - t0
        stop.set()
        th.join(timeout=2.0)
        vals = sorted(samples[1:]) or [0.0]
        row = {
            "threads": threads,
            "load_s": round(load_s, 3),
            "audio_s": REPS * CHUNK,
            "wall_s": round(wall, 3),
            "rtfx": round(REPS * CHUNK / wall, 2),
            "cpu_samples": len(vals),
            "cpu_median_pct": round(statistics.median(vals), 1),
            "cpu_max_pct": round(max(vals), 1),
            "cpu_mean_pct": round(sum(vals) / len(vals), 1),
            "cpu_ratio_to_threads": round(statistics.median(vals) / threads, 2),
            "text_chars": [len(t) for t in texts],
            "text_equal_to_first": all(t == texts[0] for t in texts),
            "session_providers": engine.session_providers,
        }
        results.append(row)
        say(f"[threads={threads}] load={row['load_s']}s wall={row['wall_s']}s rtfx={row['rtfx']} "
            f"cpu median={row['cpu_median_pct']}% max={row['cpu_max_pct']}% "
            f"(median/threads={row['cpu_ratio_to_threads']}) samples={len(vals)}")

    # the pin is REAL only if 1 thread ~= 100% and 4 threads ~= 400%
    one = next(r for r in results if r["threads"] == 1)
    four = next(r for r in results if r["threads"] == 4)
    verdict = {
        "one_thread_is_about_100pct": 60.0 <= one["cpu_median_pct"] <= 160.0,
        "four_threads_is_about_400pct": 250.0 <= four["cpu_median_pct"] <= 550.0,
        "speedup_4_over_1": round(four["rtfx"] / one["rtfx"], 2) if one["rtfx"] else None,
        "text_identical_between_counts": one["text_chars"] == four["text_chars"],
    }
    say(f"[verdict] {verdict}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"results": results, "verdict": verdict, "log": LINES},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if all(v for k, v in verdict.items() if isinstance(v, bool)) else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:  # noqa: BLE001
        import traceback
        rc = 3
        LINES.append("EXCEPTION\n" + traceback.format_exc())
    LOG.write_text("\n".join(LINES) + f"\nTHREADPROBE-RC {rc}\n", encoding="utf-8")
    raise SystemExit(rc)
