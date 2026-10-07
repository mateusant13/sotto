"""Two follow-ups the first probes left open.

(1) C's 2.4 s: is it the 1000-way partitioning, or a 1 GB WAL left open during the query?
    Reopen A and C AFTER a checkpoint and re-time. (The earlier run showed wal_bytes=0 before
    the checkpoint, but this makes it explicit and re-measures in one process.)
(2) Is `distance_metric=cosine` the slow part? Build the SAME 120 k unit vectors in a vec0
    table with the DEFAULT L2 metric (on unit vectors, ranking by L2 == ranking by dot) and
    compare k=10/k=100.

Run: python _main/_index-store-probe4.py [--json OUT]
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
N = 120_000


def ms(fn, reps=5, warm=1):
    for _ in range(warm):
        fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1e3)
    ts.sort()
    return {"min_ms": round(ts[0], 2), "median_ms": round(ts[len(ts) // 2], 2), "reps": reps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    import sqlite_vec

    rng = np.random.default_rng(4242)
    X = rng.standard_normal((N, D), dtype=np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    q = rng.standard_normal(D, dtype=np.float32)
    q /= np.linalg.norm(q)
    qb = sqlite_vec.serialize_float32(q)

    res = {"probe": "_index-store-probe4.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"), "tables": {}}

    for name in ("A_nopartition", "C_partition_video"):
        dbp = os.path.join(WORK, name + ".db")
        if not os.path.exists(dbp):
            continue
        db = sqlite3.connect(dbp)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        pre = {"db_bytes": os.path.getsize(dbp),
               "wal_bytes": os.path.getsize(dbp + "-wal") if os.path.exists(dbp + "-wal") else 0}
        db.execute("pragma wal_checkpoint(TRUNCATE)")
        out = {"pre": pre, "post_checkpoint_wal_bytes":
               os.path.getsize(dbp + "-wal") if os.path.exists(dbp + "-wal") else 0,
               "count": db.execute("select count(*) from vec_seg").fetchone()[0]}
        out["knn_k10"] = ms(lambda: db.execute(
            "select seg_id, distance from vec_seg where emb match ? and k=10", [qb]).fetchall())
        out["knn_k100"] = ms(lambda: db.execute(
            "select seg_id, distance from vec_seg where emb match ? and k=100", [qb]).fetchall())
        out["knn_k100_window"] = ms(lambda: db.execute(
            "select seg_id, distance from vec_seg where emb match ? and k=100 and start_ms>=100000 and start_ms<160000",
            [qb]).fetchall())
        # sanity: the answer must be the same distances as numpy would give
        top = db.execute("select seg_id, distance from vec_seg where emb match ? and k=5", [qb]).fetchall()
        np_scores = X @ q
        np_top = np.argsort(-np_scores)[:5]
        out["top5_sql"] = [(int(s), round(float(d), 4)) for s, d in top]
        out["top5_numpy_cos_dist"] = [(int(i), round(float(1 - np_scores[i]), 4)) for i in np_top]
        out["top5_agrees"] = [int(s) for s, _ in top] == [int(i) for i in np_top]
        db.close()
        res["tables"][name] = out

    # (2) default L2 metric, same vectors
    dbp = os.path.join(WORK, "E_L2_nopartition.db")
    for s in ("", "-wal", "-shm"):
        if os.path.exists(dbp + s):
            os.remove(dbp + s)
    db = sqlite3.connect(dbp)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute("pragma journal_mode=WAL")
    db.execute("pragma synchronous=NORMAL")
    db.execute("create virtual table vec_seg using vec0(vec_id integer primary key, channel text, "
               "start_ms integer, seg_id integer, emb float[256])")
    t0 = time.perf_counter()
    for i in range(0, N, 1000):
        db.executemany("insert into vec_seg values(?,?,?,?,?)",
                       [(j, "visual", int(j * 5000 % 600000), j, sqlite_vec.serialize_float32(X[j]))
                        for j in range(i, min(i + 1000, N))])
    db.commit()
    ins = time.perf_counter() - t0
    out = {"insert_s": round(ins, 2), "insert_vectors_per_s": round(N / ins),
           "knn_k10": ms(lambda: db.execute(
               "select seg_id, distance from vec_seg where emb match ? and k=10", [qb]).fetchall()),
           "knn_k100": ms(lambda: db.execute(
               "select seg_id, distance from vec_seg where emb match ? and k=100", [qb]).fetchall()),
           "knn_k100_window": ms(lambda: db.execute(
               "select seg_id, distance from vec_seg where emb match ? and k=100 and start_ms>=100000 "
               "and start_ms<160000", [qb]).fetchall())}
    top = db.execute("select seg_id, distance from vec_seg where emb match ? and k=5", [qb]).fetchall()
    np_scores = X @ q
    out["top5_sql_l2"] = [(int(s), round(float(d), 4)) for s, d in top]
    out["top5_numpy"] = [int(i) for i in np.argsort(-np_scores)[:5]]
    out["top5_agrees"] = [int(s) for s, _ in top] == out["top5_numpy"]
    db.commit()
    db.close()
    out["db_bytes"] = os.path.getsize(dbp)
    out["db_MiB"] = round(out["db_bytes"] / 2**20, 1)
    res["tables"]["E_L2_nopartition"] = out

    # numpy control in the same process
    res["numpy_control"] = ms(lambda: np.argpartition(X @ q, -100)[-100:], reps=10)

    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
