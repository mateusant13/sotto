"""Post-checkpoint re-query: is table C's 2.4 s KNN caused by the 1000-way sharding, or by the
1.1 GB WAL that was still open during the earlier measurement? Checkpoint first, then query.

Run: python _main/_index-store-probe3.py [--json OUT]
"""
import argparse
import json
import os
import sqlite3
import sys
import time

import numpy as np

D = 256
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_index-store2")


def ms(fn, reps=5, warm=1):
    for _ in range(warm):
        fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        ts.append((time.perf_counter() - t0) * 1e3)
        fn()
    ts.sort()
    return {"min_ms": round(ts[0], 2), "median_ms": round(ts[len(ts) // 2], 2), "reps": reps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    import sqlite_vec

    rng = np.random.default_rng(4242)
    _ = rng.standard_normal((120_000, D), dtype=np.float32)   # keep the RNG state identical
    q = rng.standard_normal(D, dtype=np.float32)
    q /= np.linalg.norm(q)
    qb = sqlite_vec.serialize_float32(q)

    res = {"probe": "_index-store-probe3.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"), "tables": {}}
    for name in ("C_partition_video", "A_nopartition"):
        dbp = os.path.join(WORK, name + ".db")
        if not os.path.exists(dbp):
            continue
        db = sqlite3.connect(dbp)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        before = {"db_bytes": os.path.getsize(dbp),
                  "wal_bytes": os.path.getsize(dbp + "-wal") if os.path.exists(dbp + "-wal") else 0}
        t0 = time.perf_counter()
        db.execute("pragma wal_checkpoint(TRUNCATE)")
        ckpt_s = time.perf_counter() - t0
        out = {"before_checkpoint": before, "checkpoint_s": round(ckpt_s, 2),
               "after_db_bytes": os.path.getsize(dbp),
               "page_size": db.execute("pragma page_size").fetchone()[0],
               "page_count": db.execute("pragma page_count").fetchone()[0],
               "count": db.execute("select count(*) from vec_seg").fetchone()[0]}
        out["knn_k10_after_checkpoint"] = ms(
            lambda: db.execute("select seg_id, distance from vec_seg where emb match ? and k=10", [qb]).fetchall())
        out["knn_k100_after_checkpoint"] = ms(
            lambda: db.execute("select seg_id, distance from vec_seg where emb match ? and k=100", [qb]).fetchall())
        out["knn_k100_window_after_checkpoint"] = ms(
            lambda: db.execute("select seg_id, distance from vec_seg where emb match ? and k=100 "
                               "and start_ms>=100000 and start_ms<160000", [qb]).fetchall())
        if name == "C_partition_video":
            out["knn_k100_video42_after_checkpoint"] = ms(
                lambda: db.execute("select seg_id, distance from vec_seg where emb match ? and k=100 "
                                   "and video_id=42", [qb]).fetchall())
        db.close()
        res["tables"][name] = out
    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
