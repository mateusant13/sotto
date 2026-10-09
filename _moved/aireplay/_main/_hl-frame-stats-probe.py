"""_hl-frame-stats-probe.py -- the population the frame thresholds come from.

Every number the highlights detector ships has to be either measured HERE, with a
population and a window, or labelled a default chosen without data.  This probe is
where "measured" comes from.

What it measures, per clip:
  * mean luma per frame (gray, scaled), and
  * `diff` = mean |f[i] - f[i-1]| over the scaled gray plane, normalised to [0,1].

`diff` is the ONLY primitive the detector scores on.  It is model-free, needs no
inference, and is computable from the frames the capture path already produced --
which is the whole reason this feature is built on frames and not on audio
(27 of 27 capture outputs on this box carry no audio stream; see receipts/).

Run:  py -3 _main/_hl-frame-stats-probe.py > _main/_hl-frame-stats-probe.log 2>&1
Rule 2 of the house: redirect to a file and read $LASTEXITCODE.  Never pipe.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]

#: The analysis grid.  64x36 gray at 10 fps is ~2.3 kB per frame; a 30 s clip is
#: ~700 kB.  CHOSEN, not measured: it is a resolution where a full-frame change is
#: still visible and the decode stays cheap.  It is NOT a product threshold.
GRID_W, GRID_H = 64, 36
ANALYSIS_FPS = 10


def frame_stats(path: Path) -> dict:
    """Decode `path` to a gray grid and return per-frame mean/diff series."""
    cmd = [
        "ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
        "-vf", f"fps={ANALYSIS_FPS},scale={GRID_W}:{GRID_H},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        return {"ok": False, "err": proc.stderr.decode("utf-8", "replace")[:200]}

    frame_bytes = GRID_W * GRID_H
    n = len(proc.stdout) // frame_bytes
    if n < 2:
        return {"ok": False, "err": f"only {n} frame(s) decoded"}
    buf = np.frombuffer(proc.stdout[: n * frame_bytes], dtype=np.uint8)
    frames = buf.reshape(n, GRID_H, GRID_W).astype(np.int16)

    luma = frames.mean(axis=(1, 2)) / 255.0
    diff = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2)) / 255.0
    return {"ok": True, "n": n, "luma": luma, "diff": diff}


def pct(a: np.ndarray, q: float) -> float:
    return float(np.percentile(a, q)) if a.size else float("nan")


def main() -> int:
    root = REPO / "_main"
    files = sorted(
        p for ext in ("*.mp4", "*.mkv", "*.mov")
        for p in root.rglob(ext) if p.stat().st_size > 200_000
    )
    print("PROBE _hl-frame-stats-probe")
    print(f"GRID = {GRID_W}x{GRID_H} gray @ {ANALYSIS_FPS} fps   "
          f"diff = mean|f[i]-f[i-1]| over the whole grid, normalised to [0,1]")
    print(f"POPULATION = every *.mp4/*.mkv/*.mov > 200 KB under _main/ (recursive), "
          f"one decode each, no sampling.  N = {len(files)}")
    print(f"WINDOW = all files present on disk at run time")
    print()

    rows = []
    total_s = 0.0
    for p in files:
        st = frame_stats(p)
        if not st.get("ok"):
            print(f"SKIP {p.relative_to(REPO)}  ({st.get('err')})")
            continue
        d = st["diff"]
        dur = st["n"] / ANALYSIS_FPS
        total_s += dur
        rows.append((p, d, st["luma"], dur))
        print(f"{str(p.relative_to(REPO)):52s} dur={dur:6.1f}s frames={st['n']:5d} "
              f"diff p50={pct(d,50):.5f} p90={pct(d,90):.5f} p99={pct(d,99):.5f} "
              f"max={d.max():.5f} mean={d.mean():.5f}")

    if not rows:
        print("\nNO CLIPS DECODED -- the census itself is empty")
        return 2

    pool = np.concatenate([d for _, d, _, _ in rows])
    print()
    print(f"POOLED over {len(rows)} clips / {total_s:.1f} s of decoded footage, "
          f"{pool.size} frame-diffs")
    for q in (1, 5, 25, 50, 75, 90, 95, 99, 99.9):
        print(f"  pooled diff p{q:<5} = {pct(pool, q):.6f}")
    print(f"  pooled diff max  = {pool.max():.6f}")

    # Per-clip spread of the p50: the floor a static scene actually sits at.
    p50s = np.array([pct(d, 50) for _, d, _, _ in rows])
    print(f"  per-clip diff p50: min={p50s.min():.6f} median={np.median(p50s):.6f} "
          f"max={p50s.max():.6f}")

    json.dump(
        {
            "grid": [GRID_W, GRID_H], "fps": ANALYSIS_FPS,
            "population": len(rows), "pooled_frames": int(pool.size),
            "pooled_total_s": round(total_s, 2),
            "pooled_percentiles": {str(q): pct(pool, q)
                                   for q in (1, 5, 25, 50, 75, 90, 95, 99, 99.9)},
            "pooled_max": float(pool.max()),
            "per_clip_p50": {"min": float(p50s.min()),
                             "median": float(np.median(p50s)),
                             "max": float(p50s.max())},
        },
        open(REPO / "_main" / "_hl-frame-stats.json", "w", encoding="utf-8"),
        indent=2)
    print("\nwrote _main/_hl-frame-stats.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())