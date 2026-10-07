"""Startup + write-path cost of the recommended shape: SQLite is the record, the scan is in-process.

Measured here:
  1. how long it takes to load the whole vector table from SQLite into an fp32 numpy array
     (this is what "search works" costs after a restart -- the RAM array is derived data)
  2. the same load from a PLAIN table holding fp16 blobs (half the bytes) + the cast
  3. appending vectors at runtime: per-vector append into preallocated room vs a realloc
  4. a single-row commit cost (the light writer's real-time write) -- WAL, synchronous=NORMAL

Run: python _main/_index-load-probe.py [--json OUT]
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
WORK = os.path.join(HERE, "_index-load")
N = 120_000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    rng = np.random.default_rng(77)
    res = {"probe": "_index-load-probe.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"), "vectors": N, "dims": D}

    X = rng.standard_normal((N, D), dtype=np.float32)
    X16 = X.astype(np.float16)

    # 1+2: plain tables, fp32 and fp16 blobs
    for tag, arr, dt in (("fp32", X, np.float32), ("fp16", X16, np.float16)):
        dbp = os.path.join(WORK, "load_%s.db" % tag)
        for s in ("", "-wal", "-shm"):
            if os.path.exists(dbp + s):
                os.remove(dbp + s)
        db = sqlite3.connect(dbp)
        db.execute("pragma journal_mode=WAL")
        db.execute("pragma synchronous=NORMAL")
        db.execute("create table seg(vec_id integer primary key, seg_id integer, channel text, start_ms integer, emb blob)")
        t0 = time.perf_counter()
        db.executemany("insert into seg values(?,?,?,?,?)",
                       [(i, i, "visual", i * 5000 % 600000, arr[i].tobytes()) for i in range(N)])
        db.commit()
        ins = time.perf_counter() - t0
        db.execute("pragma wal_checkpoint(TRUNCATE)")
        entry = {"insert_s": round(ins, 2), "insert_vectors_per_s": round(N / ins),
                 "db_bytes": os.path.getsize(dbp), "db_MiB": round(os.path.getsize(dbp) / 2**20, 1)}
        t0 = time.perf_counter()
        cur = db.execute("select emb from seg order by vec_id")
        buf = b"".join(r[0] for r in cur)
        M = np.frombuffer(buf, dtype=np.dtype(dt)).reshape(-1, D)
        t_load = time.perf_counter() - t0
        entry["load_s"] = round(t_load, 3)
        entry["load_MB_per_s"] = round(len(buf) / 2**20 / t_load, 1)
        entry["loaded_dtype"] = str(M.dtype)
        if dt is np.float16:
            t0 = time.perf_counter()
            M32 = M.astype(np.float32)
            entry["cast_fp16_to_fp32_ms"] = round((time.perf_counter() - t0) * 1e3, 1)
            entry["castable"] = bool(np.array_equal(M32[0], X[0]))
        t0 = time.perf_counter()
        cur = db.execute("select emb from seg order by vec_id")
        n = sum(1 for _ in cur)
        entry["load_one_by_one_s"] = round(time.perf_counter() - t0, 3)
        res[tag] = entry
        db.close()

    # 3: append cost -- preallocated vs realloc
    cap = N + 10_000
    A = np.zeros((cap, D), dtype=np.float32)
    A[:N] = X
    v = X[0]
    t0 = time.perf_counter()
    for i in range(N, N + 10_000):
        A[i] = v
    res["append_preallocated_us_per_vector"] = round((time.perf_counter() - t0) / 10_000 * 1e6, 2)
    B = X.copy()
    t0 = time.perf_counter()
    B = np.resize(B, (N + 1, D))
    B[N] = v
    res["append_via_np_resize_ms"] = round((time.perf_counter() - t0) * 1e3, 1)

    # 4: the light writer's real-time cost: one row + one vector, committed, WAL
    dbp = os.path.join(WORK, "light.db")
    for s in ("", "-wal", "-shm"):
        if os.path.exists(dbp + s):
            os.remove(dbp + s)
    db = sqlite3.connect(dbp, isolation_level=None)
    db.execute("pragma journal_mode=WAL")
    db.execute("pragma synchronous=NORMAL")
    db.execute("create table seg(seg_id integer primary key, start_ms integer, text text)")
    db.execute("create table vec(seg_id integer primary key, emb blob)")
    db.execute("begin")
    db.execute("insert into seg values(1, 5000, 'uma linha de transcricao curta')")
    db.execute("insert into vec values(1, ?)", (X[0].tobytes(),))
    db.execute("commit")
    lat = []
    for i in range(2, 202):
        t0 = time.perf_counter()
        db.execute("begin")
        db.execute("insert into seg values(?,?,?)", (i, i * 5000, "linha %d" % i))
        db.execute("insert into vec values(?,?)", (i, X[i].tobytes()))
        db.execute("commit")
        lat.append((time.perf_counter() - t0) * 1e3)
    lat.sort()
    res["light_write_commit_ms"] = {"min": round(lat[0], 3), "median": round(lat[len(lat) // 2], 3),
                                    "p95": round(lat[int(len(lat) * 0.95)], 3), "max": round(lat[-1], 3),
                                    "n": len(lat)}
    db.close()

    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
