"""ram_probe.py -- replace the RAM ASSUMPTION with a MEASUREMENT.

Owner: _main/ram_probe.py on feat/ram-budget-2.  Does NOT touch product code.

Two modes:

  --mode index   Build the real index DB at N and measure the RSS delta of
                 store.load_matrix().  Fast.  Checks the inherited claim
                 "+303.8 MB at N=211200".

  --mode soak    Run the ingest soak for ARM (uncapped|capped).  Samples
                 private bytes + working set on a FIXED interval and reports
                 idle / 1 min / 10 min / peak.  The capped arm must
                 PLATEAU; the uncapped arm must GROW.  That contrast is what
                 proves the cap does something.

Every number this prints carries POPULATION and WINDOW.  Nothing here reports
a single instantaneous sample as a "peak" -- peak is max over the sample set,
and the set size and interval are printed with it.

THREADS: at most 2.  Set before numpy does any real work.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# MUST precede the numpy import for the budget to bind.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import numpy as np  # noqa: E402
import psutil  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "_moved" / "aireplay" / "src" / "index"
sys.path.insert(0, str(SRC))

import store  # noqa: E402  (the real product loader, imported not reimplemented)

PROC = psutil.Process()
MiB = 1048576.0


def _mem() -> dict:
    """private bytes + working set for THIS process, in MiB."""
    full = PROC.memory_full_info()
    return {
        "private_mib": full.private / MiB,
        "ws_mib": full.uss * 0 + full.rss / MiB,      # working set
        "rss_mib": full.rss / MiB,
        "peak_ws_mib": getattr(full, "peak_wset", 0) / MiB,
    }


def stamp(t0: float) -> float:
    return time.perf_counter() - t0


# ---------------------------------------------------------------------------
# index mode: build N, measure the load delta
# ---------------------------------------------------------------------------

def build_db(path: Path, n: int, *, dim: int = 256, segs_per_video: int = 8) -> dict:
    """Populate the real schema with n embeddings. Returns build facts.

    One embedding per SEGMENT (embedding PK is (seg_id, channel)), so the row
    count in the table really is n -- otherwise the ON CONFLICT upsert collapses
    repeats and the index is smaller than the population it claims.
    """
    if path.exists():
        path.unlink()
    for suf in ("-wal", "-shm"):
        p = path.with_name(path.name + suf)
        if p.exists():
            p.unlink()
    conn = store.connect(path)
    n_seg = n                                  # 1 embedding per segment
    n_vid = max(1, (n + segs_per_video - 1) // segs_per_video)
    rng = np.random.default_rng(211200)

    t0 = time.perf_counter()
    # content_key is CHECKed at exactly 64 hex chars, so make it a real digest.
    conn.execute("BEGIN")
    for v in range(n_vid):
        ck = hashlib.sha256(f"sotto-probe-video-{v}".encode()).hexdigest()
        conn.execute(
            "INSERT INTO video (content_key, path, size_bytes, mtime_ns, state)"
            " VALUES (?,?,?,?,?)",
            (ck, f"H:/vid/{v}.mp4", 1024, 1, "indexed"))
    conn.execute("COMMIT")

    conn.execute("BEGIN")
    seg_id = 0
    for s in range(n_seg):
        vid = (s // segs_per_video) % max(1, n_vid)
        seg_id += 1
        conn.execute(
            "INSERT INTO segment (seg_id, video_id, start_ms, end_ms, state)"
            " VALUES (?,?,?,?,?)",
            (seg_id, vid + 1, 0, 1000, "done"))
        if seg_id % 5000 == 0:            # keep the tx from growing unbounded
            conn.execute("COMMIT")
            conn.execute("BEGIN")
    conn.execute("COMMIT")

    # upsert_embeddings opens and commits its OWN transaction, so no outer BEGIN.
    eid = 0
    CH = 5000
    while eid < n:
        batch = []
        for _ in range(min(CH, n - eid)):
            seg = eid + 1
            vec = rng.standard_normal(dim).astype(np.float16)
            batch.append((seg, "visual", vec))
            eid += 1
        store.upsert_embeddings(conn, batch, model="ram-probe", dim=dim)
    build_s = time.perf_counter() - t0
    facts = store.store_bytes(conn)
    conn.close()
    facts["build_s"] = build_s
    facts["n_embeddings"] = n
    facts["n_segments"] = n_seg
    facts["n_videos"] = n_vid
    return facts


def measure_index(n: int, dbdir: Path, *, dim: int = 256) -> dict:
    path = dbdir / f"index-{n}.sqlite"
    before_build = _mem()
    facts = build_db(path, n, dim=dim)
    gc.collect()
    time.sleep(0.5)
    after_build = _mem()

    conn = store.connect(path)
    n_rows = conn.execute("SELECT COUNT(*) FROM embedding").fetchone()[0]
    t0 = time.perf_counter()
    pre = _mem()
    out = store.load_matrix(conn)          # <-- THE measured call
    load_s = time.perf_counter() - t0
    gc.collect(); time.sleep(0.3)
    post = _mem()
    vecs = out[0]
    shape = list(vecs.shape)
    conn.close()

    return {
        "n": n,
        "n_rows_in_db": n_rows,
        "dim": dim,
        "matrix_shape": shape,
        "matrix_mib": vecs.nbytes / MiB,
        "db_on_disk_mib": facts["file_mib"],
        "db_file_bytes": facts["file_bytes"],
        "page_size": facts["page_size"],
        "build_s": facts["build_s"],
        "load_s": load_s,
        "rss_before_load_mib": pre["rss_mib"],
        "rss_after_load_mib": post["rss_mib"],
        "rss_delta_load_mib": post["rss_mib"] - pre["rss_mib"],
        "ws_delta_load_mib": post["ws_mib"] - pre["ws_mib"],
        "private_delta_load_mib": post["private_mib"] - pre["private_mib"],
        "private_after_build_mib": after_build["private_mib"],
        "ws_after_build_mib": after_build["ws_mib"],
        "build_private_mib": after_build["private_mib"] - before_build["private_mib"],
        "population": f"this host, this process, N={n} embeddings, dim={dim}",
        "window": "single build+load, one process, psutil memory_full_info()",
    }


# ---------------------------------------------------------------------------
# soak mode: the two arms
# ---------------------------------------------------------------------------

def load_bounded(conn: sqlite3.Connection, max_rows: int) -> np.ndarray:
    """The CAP. Same query as store.load_matrix, but STREAMED and TRUNCATED.

    store.load_matrix calls fetchall(): every row becomes a sqlite3.Row holding
    a Python bytes object. That is the unbounded term. Here the cursor is walked
    with a bounded fetchmany and the matrix never exceeds max_rows rows, so the
    resident set is bounded by max_rows * dim * 4 regardless of table size.
    """
    cur = conn.execute(
        "SELECT e.seg_id, e.dim, e.dtype, e.vec FROM embedding e "
        "JOIN segment s ON s.seg_id = e.seg_id "
        "ORDER BY e.seg_id LIMIT ?", (max_rows,))
    dim = 256
    buf = np.empty((max_rows, dim), dtype=np.float32)
    i = 0
    while True:
        rows = cur.fetchmany(2000)
        if not rows:
            break
        for r in rows:
            if i >= max_rows:
                break
            a = np.frombuffer(r["vec"],
                              dtype=np.float16 if r["dtype"] == "fp16" else np.float32)
            buf[i, :len(a)] = a.astype(np.float32)
            i += 1
    cur.close()
    return buf[:i]


def soak(arm: str, *, seconds: float, interval: float, ingest_every: float,
         max_rows: int, dim: int, dbdir: Path) -> dict:
    """Ingest embeddings continuously, sample WS/private on a FIXED interval."""
    assert interval > 0
    db = dbdir / f"soak-{arm}.sqlite"
    if db.exists():
        db.unlink()
    for suf in ("-wal", "-shm"):
        p = db.with_name(db.name + suf)
        if p.exists():
            p.unlink()
    conn = store.connect(db)
    conn.execute("BEGIN")
    conn.execute("INSERT INTO video (content_key, path, size_bytes, mtime_ns, state)"
                 " VALUES (?,?,?,?,?)",
                 (hashlib.sha256(b"sotto-soak-video").hexdigest(),
                  "H:/s.mp4", 1, 1, "indexed"))
    conn.execute("COMMIT")

    rng = np.random.default_rng(7)
    samples: list[dict] = []
    t0 = time.perf_counter()
    next_sample = 0.0
    next_ingest = 0.0
    ingested = 0
    seg = 0
    idle = _mem()
    peak_ws = idle["ws_mib"]
    peak_priv = idle["private_mib"]

    while True:
        now = stamp(t0)
        if now >= next_ingest:
            seg += 1
            conn.execute("INSERT OR IGNORE INTO segment (seg_id, video_id, start_ms,"
                         " end_ms, state) VALUES (?,1,0,1000,'done')", (seg,))
            rows = [(seg, "visual", rng.standard_normal(dim).astype(np.float16))
                    for _ in range(8)]
            store.upsert_embeddings(conn, rows, model="soak", dim=dim)
            ingested += 8
            next_ingest = now + ingest_every
        if now >= next_sample:
            # sample THEN exercise the read path, so the sample shows the cost
            m = _mem()
            held = None
            try:
                if arm == "uncapped":
                    # the product call: fetchall() of every row, every sample
                    rows = conn.execute(
                        "SELECT e.seg_id, e.dim, e.dtype, e.vec FROM embedding e "
                        "JOIN segment s ON s.seg_id=e.seg_id").fetchall()
                    if len(rows) > 200000:
                        rows = None
                    held = len(rows) if rows is not None else 0
                    del rows
                else:
                    mat = load_bounded(conn, max_rows)
                    held = mat.shape[0]
                    del mat
                gc.collect()
            except Exception as exc:  # keep sampling even if the arm errors
                held = f"ERR {type(exc).__name__}"
            m2 = _mem()
            peak_ws = max(peak_ws, m2["ws_mib"])
            peak_priv = max(peak_priv, m2["private_mib"])
            samples.append({
                "t_s": round(now, 2),
                "ws_mib": m2["ws_mib"],
                "private_mib": m2["private_mib"],
                "rss_mib": m2["rss_mib"],
                "rows_visible": ingested,
                "held": held,
            })
            next_sample = now + interval
        if now >= seconds:
            break
        time.sleep(0.01)

    total_s = stamp(t0)
    conn.close()
    try:
        size_mib = db.stat().st_size / MiB
    except OSError:
        size_mib = 0.0

    def at(label):
        target = {"idle": 0.0, "1min": 60.0, "5min": 300.0, "10min": 600.0}[label]
        best = min(samples, key=lambda s: abs(s["t_s"] - target)) if samples else None
        return best

    ws = [s["ws_mib"] for s in samples]
    pv = [s["private_mib"] for s in samples]
    n1 = max(1, int(60.0 / interval))
    n5 = max(1, int(300.0 / interval))
    late = ws[-min(len(ws), max(2, int(300.0 / interval))):] or ws
    early = ws[:n1] or ws

    # linear slope of working set over the whole window, MiB per hour
    slope = _slope([s["t_s"] for s in samples], ws) * 3600.0 if len(samples) > 2 else 0.0
    slope_priv = (_slope([s["t_s"] for s in samples], pv) * 3600.0
                  if len(samples) > 2 else 0.0)

    return {
        "arm": arm,
        "max_rows_cap": max_rows if arm == "capped" else None,
        "ingest_every_s": ingest_every,
        "interval_s": interval,
        "samples": len(samples),
        "window_s": total_s,
        "rows_ingested": ingested,
        "db_on_disk_mib": size_mib,
        "idle": idle,
        "at_1min": at("1min"),
        "at_5min": at("5min"),
        "at_10min": at("10min"),
        "ws_max_mib": max(ws) if ws else None,
        "priv_max_mib": max(pv) if pv else None,
        "ws_first_minute_mean_mib": sum(early) / len(early) if early else None,
        "ws_last_5min_mean_mib": sum(late) / len(late) if late else None,
        "ws_growth_last5_vs_first1_mib": ((sum(late) / len(late) - sum(early) / len(early))
                                          if early and late else None),
        "ws_slope_mib_per_hour": slope,
        "private_slope_mib_per_hour": slope_priv,
        "curve": samples,
        "population": (f"this host, this process, arm={arm}, ingest "
                       f"{8 / ingest_every:.1f} rows/s of dim={dim} fp16"),
        "window": f"{len(samples)} samples at {interval}s over {total_s:.0f}s",
    }


def _slope(xs, ys) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("index", "soak", "both"), default="index")
    ap.add_argument("--n", type=int, action="append", default=None)
    ap.add_argument("--ns", type=int, nargs="*", default=[20000, 211200])
    ap.add_argument("--arm", choices=("uncapped", "capped"), default="uncapped")
    ap.add_argument("--seconds", type=float, default=660.0)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--ingest-every", type=float, default=0.05)
    ap.add_argument("--max-rows", type=int, default=60000)
    ap.add_argument("--dim", type=int, default=256)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    dbdir = Path(os.environ.get("RAMPROBE_DIR", r"I:\cc-tmp\ramprobe"))
    dbdir.mkdir(parents=True, exist_ok=True)
    out = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "pid": PROC.pid}

    if a.mode in ("index", "both"):
        out["index"] = [measure_index(n, dbdir, dim=a.dim) for n in (a.ns or [20000])]
    if a.mode in ("soak", "both"):
        out["soak"] = soak(a.arm, seconds=a.seconds, interval=a.interval,
                           ingest_every=a.ingest_every, max_rows=a.max_rows,
                           dim=a.dim, dbdir=dbdir)

    dst = Path(a.out) if a.out else dbdir / f"ramprobe-{a.mode}-{a.arm}.json"
    dst.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "soak"}, indent=2))
    if "soak" in out:
        s = dict(out["soak"])
        s.pop("curve")
        print(json.dumps(s, indent=2))
    print(f"RESULT: wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())