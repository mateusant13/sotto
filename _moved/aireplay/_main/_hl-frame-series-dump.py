"""_hl-frame-series-dump.py -- cache the per-frame diff series so analysis stops re-decoding.

The first probe answered "how big is a frame change here".  This one answers the
question the THRESHOLD actually depends on: how big is a frame change *relative to
the scene it happened in*, and is any real clip in this corpus an isolated BURST
rather than sustained activity.

It dumps one .npz with one array per clip (`name` -> diff series, float32) plus the
per-frame mean luma, so every later analysis is instant and reproducible from disk.

Run:  py -3 _main/_hl-frame-series-dump.py > _main/_hl-frame-series-dump.log 2>&1
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
GRID_W, GRID_H = 64, 36
ANALYSIS_FPS = 10


def series(path: Path) -> tuple[np.ndarray, np.ndarray] | None:
    cmd = [
        "ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
        "-vf", f"fps={ANALYSIS_FPS},scale={GRID_W}:{GRID_H},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        return None
    fb = GRID_W * GRID_H
    n = len(proc.stdout) // fb
    if n < 3:
        return None
    f = np.frombuffer(proc.stdout[: n * fb], dtype=np.uint8).reshape(n, GRID_H, GRID_W)
    f = f.astype(np.int16)
    return (np.abs(np.diff(f, axis=0)).mean(axis=(1, 2)) / 255.0).astype(np.float32), \
           (f.mean(axis=(1, 2)) / 255.0).astype(np.float32)


def main() -> int:
    root = REPO / "_main"
    files = sorted(
        p for ext in ("*.mp4", "*.mkv", "*.mov")
        for p in root.rglob(ext) if p.stat().st_size > 200_000
    )
    out: dict[str, np.ndarray] = {}
    lumas: dict[str, np.ndarray] = {}
    for p in files:
        r = series(p)
        if r is None:
            print(f"SKIP {p.relative_to(REPO)}")
            continue
        key = str(p.relative_to(REPO))
        out[key], lumas[key] = r
    np.savez_compressed(REPO / "_main" / "_hl-frame-series.npz",
                        diff=np.array(list(out.values()), dtype=object),
                        luma=np.array(list(lumas.values()), dtype=object),
                        names=np.array(list(out.keys())))
    print(f"POPULATION = every *.mp4/*.mkv/*.mov > 200 KB under _main/, one decode each")
    print(f"N = {len(out)} clips, "
          f"{sum(len(v) for v in out.values()) / ANALYSIS_FPS:.1f} s decoded")
    print("wrote _main/_hl-frame-series.npz")
    return 0


if __name__ == "__main__":
    sys.exit(main())