"""Why is vec0's KNN slow here? Isolate the partition key, the metadata filter and `order by`.

Table A: NO partition key (metadata only: channel, start_ms, seg_id)
Table B: partition key = channel (3 shards)
Table C: partition key = video_id (1000 shards)      <- the shape probed in _index-store-probe.py
Also: the documented "manual" method (vec_distance_cosine on a plain table + ORDER BY),
and a numpy control in the SAME process, same data, so the comparison is not across processes.

Run: python _main/_index-store-probe2.py [--json OUT] [--rows 120000]
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
        fn()
        ts.append((time.perf_counter() - t0) * 1e3)
    ts.sort()
    return {"min_ms": round(ts[0], 2), "median_ms": round(ts[len(ts) // 2], 2), "reps": reps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--rows", type=int, default=120_000)
    a = ap.parse_args()
    import sqlite_vec

    os.makedirs(WORK, exist_ok=True)
    rng = np.random.default_rng(4242)
    n = a.rows
    X = rng.standard_normal((n, D), dtype=np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    vid = np.arange(n) // 120
    sm = (np.arange(n) % 120) * 5000
    chan = np.where(np.arange(n) % 3 == 0, "speech", np.where(np.arange(n) % 7 == 0, "ocr", "visual"))
    q = rng.standard_normal(D, dtype=np.float32)
    q /= np.linalg.norm(q)
    qb = sqlite_vec.serialize_float32(q)

    res = {"probe": "_index-store-probe2.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rows": n, "dims": D, "sqlite_vec": getattr(sqlite_vec, "__version__", None),
           "sqlite": sqlite3.sqlite_version, "tables": {}}

    shapes = {
        "A_nopartition": "vec_id integer primary key, channel text, start_ms integer, seg_id integer, emb float[256] distance_metric=cosine",
        "B_partition_channel": "vec_id integer primary key, channel text partition key, start_ms integer, seg_id integer, emb float[256] distance_metric=cosine",
        "C_partition_video": "vec_id integer primary key, video_id integer partition key, channel text, start_ms integer, seg_id integer, emb float[256] distance_metric=cosine",
    }
    for name, cols in shapes.items():
        dbp = os.path.join(WORK, name + ".db")
        for s in ("", "-wal", "-shm"):
            if os.path.exists(dbp + s):
                os.remove(dbp + s)
        db = sqlite3.connect(dbp)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        db.execute("pragma journal_mode=WAL")
        db.execute("pragma synchronous=NORMAL")
        db.execute("create virtual table vec_seg using vec0(%s)" % cols)
        t0 = time.perf_counter()
        batch = 1000
        for i in range(0, n, batch):
            rows = []
            for j in range(i, min(i + batch, n)):
                base = (j, chan[j], int(sm[j]), j, sqlite_vec.serialize_float32(X[j]))
                if name == "C_partition_video":
                    base = (j, int(vid[j]), chan[j], int(sm[j]), j, sqlite_vec.serialize_float32(X[j]))
                rows.append(base)
            ph = ",".join("?" * len(rows[0]))
            db.executemany("insert into vec_seg values(%s)" % ph, rows)
        db.commit()
        ins = time.perf_counter() - t0
        out = {"insert_s": round(ins, 2), "insert_vectors_per_s": round(n / ins),
               "count": db.execute("select count(*) from vec_seg").fetchone()[0]}

        def q_run(sql, reps=5):
            return ms(lambda: db.execute(sql, [qb]).fetchall(), reps=reps)

        out["knn_k10"] = q_run("select seg_id, distance from vec_seg where emb match ? and k=10")
        out["knn_k10_no_order_by"] = q_run("select seg_id, distance from vec_seg where emb match ? and k=10 order by distance")
        out["knn_k100"] = q_run("select seg_id, distance from vec_seg where emb match ? and k=100")
        out["knn_k100_channel_speech"] = q_run(
            "select seg_id, distance from vec_seg where emb match ? and k=100 and channel='speech'")
        out["knn_k100_window"] = q_run(
            "select seg_id, distance from vec_seg where emb match ? and k=100 and start_ms>=100000 and start_ms<160000")
        if name == "C_partition_video":
            out["knn_k100_video42"] = q_run(
                "select seg_id, distance from vec_seg where emb match ? and k=100 and video_id=42")
        db.commit()
        db.execute("pragma wal_checkpoint(TRUNCATE)")
        sh = db.execute("select name from sqlite_master where name like 'vec_seg%' or name like 'sqlite_%'").fetchall()
        out["shadow_tables"] = [r[0] for r in sh]
        out["page_size"] = db.execute("pragma page_size").fetchone()[0]
        out["page_count"] = db.execute("pragma page_count").fetchone()[0]
        db.close()
        out["db_bytes"] = os.path.getsize(dbp)
        out["db_MiB"] = round(out["db_bytes"] / 2**20, 1)
        out["payload_MiB"] = round(n * D * 4 / 2**20, 1)
        res["tables"][name] = out

    # the "manual" documented method, on a plain table, same vectors
    dbp = os.path.join(WORK, "D_manual.db")
    for s in ("", "-wal", "-shm"):
        if os.path.exists(dbp + s):
            os.remove(dbp + s)
    db = sqlite3.connect(dbp)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute("create table seg(vec_id integer primary key, emb blob)")
    t0 = time.perf_counter()
    db.executemany("insert into seg values(?,?)", [(j, sqlite_vec.serialize_float32(X[j])) for j in range(n)])
    db.commit()
    ins = time.perf_counter() - t0
    res["tables"]["D_manual_plain_table+vec_distance_cosine"] = {
        "insert_s": round(ins, 2), "count": db.execute("select count(*) from seg").fetchone()[0],
        "knn_k100_orderby": ms(lambda: db.execute(
            "select vec_id, vec_distance_cosine(emb, ?) as d from seg order by d limit 100", [qb]).fetchall()),
    }
    db.close()

    # numpy control in THIS process, same matrix
    def np_knn():
        s = X @ q
        idx = np.argpartition(s, -100)[-100:]
        return idx[np.argsort(-s[idx])]

    res["numpy_control_same_process"] = ms(np_knn, reps=10)
    res["numpy_control_bytes_MiB"] = round(X.nbytes / 2**20, 1)
    res["numpy_at_k10"] = ms(lambda: np.argpartition(X @ q, -10)[-10:], reps=10)

    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
