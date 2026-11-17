#!/usr/bin/env python
"""concurrency_summary.py -- the ladder table, from the probe's own JSON files.

Reads `_main/bench/concurrency/n<N>.json` (written by `concurrency_probe.py`)
and prints one row per rung. Nothing here measures anything: it re-expresses
the probe's numbers so the document's table has ONE derivation, not a hand
transcription of five JSON files.

Usage:
    python _main/bench/concurrency_summary.py _main/bench/concurrency/n1.json ...
"""
from __future__ import annotations

import json
import sys


def row(path: str) -> dict:
    d = json.load(open(path, encoding="utf-8"))
    ps = d["per_stream"]
    infers = [s["infer_wall_s"] for s in ps if s["rtf"]]
    rtfs = [s["rtf"] for s in ps if s["rtf"]]
    cores = [s["cores"] for s in ps if s["cores"]]
    loads = [s["load_s"] for s in ps if s["load_s"]]
    rss = [s["peak_rss_mb_worker"] for s in ps if s["peak_rss_mb_worker"]]
    cpu_total = sum(s["cpu_s"] for s in ps)
    return {
        "rung": d["label"],
        "n": d["streams_requested"],
        "done": d["streams_finished"],
        "stalled": d.get("streams_stalled") or [],
        "ambient": d.get("ambient_cpu_pct_before"),
        "peak_box": d.get("peak_box_pct"),
        "rss_total": d.get("peak_total_rss_mb"),
        "rss_per_stream": round(sum(rss) / len(rss), 1) if rss else None,
        "vram_peak": (d.get("gpu") or {}).get("vram_peak_mb"),
        "rtf_min": min(rtfs) if rtfs else None,
        "rtf_max": max(rtfs) if rtfs else None,
        "cores_per_stream": round(sum(cores) / len(cores), 2) if cores else None,
        "cores_sum": round(sum(cores), 2),
        "cpu_s_total": round(cpu_total, 1),
        "core_s_per_audio_s": d.get("mean_core_s_per_audio_s"),
        "load_s_max": max(loads) if loads else None,
        "wall_s": d.get("wall_s"),
        "audio_per_wall": d.get("throughput_audio_s_per_wall_s"),
        "free_after": d.get("host_free_mb_after"),
    }


def main(argv) -> int:
    rows = [row(p) for p in argv[1:]]
    cols = ["rung", "n", "done", "stalled", "ambient", "peak_box", "rss_total",
            "rss_per_stream", "vram_peak", "rtf_min", "rtf_max",
            "cores_per_stream", "cores_sum", "cpu_s_total", "core_s_per_audio_s",
            "load_s_max", "wall_s", "audio_per_wall", "free_after"]
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(r[c]) for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
