"""Interleaved store comparison, so contention cannot masquerade as a difference.

Rounds alternate: numpy control, table A (cosine), table E (default L2), table C (cosine, 1000
partitions). Same vectors, same unit-length query, same process, one after the other. If a table
is slow in every round while numpy stays flat, the table is slow -- not the box.

Run: python _main/_index-store-probe5.py [--json OUT] [--rounds 4]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--rounds", type=int, default=4)
    a = ap.parse_args()
    import sqlite_vec

    rng = np.random.default_rng(4242)
    X = rng.standard_normal((120_000, D), dtype=np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    q = rng.standard_normal(D, dtype=np.float32)
    q /= np.linalg.norm(q)
    qb = sqlite_vec.serialize_float32(q)

    conns = {}
    for name, path in (("A_cosine_nopartition", "A_nopartition.db"),
                       ("E_L2_nopartition", "E_L2_nopartition.db"),
                       ("C_cosine_1000partitions", "C_partition_video.db")):
        p = os.path.join(WORK, path)
        if os.path.exists(p):
            db = sqlite3.connect(p)
            db.enable_load_extension(True)
            sqlite_vec.load(db)
            db.enable_load_extension(False)
            db.execute("pragma wal_checkpoint(TRUNCATE)")
            conns[name] = db

    res = {"probe": "_index-store-probe5.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "vectors": 120000, "dims": D, "rounds": {}}

    def one(db, k):
        t0 = time.perf_counter()
        db.execute("select seg_id, distance from vec_seg where emb match ? and k=%d" % k, [qb]).fetchall()
        return (time.perf_counter() - t0) * 1e3

    def numpy_one():
        t0 = time.perf_counter()
        np.argpartition(X @ q, -100)[-100:]
        return (time.perf_counter() - t0) * 1e3

    per = {"numpy_k100": [], "A_k100": [], "E_k100": [], "C_k10": [], "C_k100": []}
    for r in range(a.rounds):
        per["numpy_k100"].append(numpy_one())
        for key, name in (("A_k100", "A_cosine_nopartition"), ("E_k100", "E_L2_nopartition"),
                          ("C_k10", "C_cosine_1000partitions"), ("C_k100", "C_cosine_1000partitions")):
            if name in conns:
                k = 10 if key.endswith("k10") else 100
                per[key].append(one(conns[name], k))
    for key, vals in per.items():
        if not vals:
            continue
        v = sorted(vals)
        res["rounds"][key] = {"min_ms": round(v[0], 1), "median_ms": round(v[len(v) // 2], 1),
                              "all_ms": [round(x, 1) for x in vals]}
    for db in conns.values():
        db.close()
    res["note"] = ("numpy and the three vec0 tables measured alternately in one process; "
                   "a table that is slow in every round is slow, not the box")
    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
