"""The index STORE: sqlite-vec vs a numpy array, on the real shape (120 k segments, 3 channels).

Question: "what is the store, the schema and the fusion rule?"
This probe answers the STORE half, with numbers, on this box:
  - insert throughput of vec0 (the two-speed indexer's light writer must sustain this)
  - KNN latency k=10/100, unfiltered and with the two filters the product needs
    (channel equality = "which channel matched"; start_ms range = "in this time window";
     video_id equality = a partition-key probe)
  - the same query in pure numpy over the same vectors, same filters
  - the file size of the whole store on disk
  - the JOIN that turns a vector hit into "open file X at 03:41.2"

Run: python _main/_index-store-probe.py [--json OUT] [--apart N]
"""
import argparse
import json
import os
import sqlite3
import sys
import time

import numpy as np

D = 256
N_VIDEO = 1000
SEG_PER_VIDEO = 120          # 10 min at 5 s
N_SEG = N_VIDEO * SEG_PER_VIDEO          # 120 000
SPEECH_FRAC = 0.60           # segments that carry speech
OCR_FRAC = 0.16              # segments that carry on-screen text
STORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_index-store")


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


def unit(x):
    x = np.asarray(x, dtype=np.float32)
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


def build_corpus(rng):
    """seg_id -> vector per channel, plus the ids/labels the vec0 table needs."""
    seeds = rng.standard_normal((N_SEG, D), dtype=np.float32)
    chans = [("visual", N_SEG, np.arange(N_SEG))]
    n_sp = int(N_SEG * SPEECH_FRAC)
    sp_ids = np.sort(rng.choice(N_SEG, n_sp, replace=False))
    n_oc = int(N_SEG * OCR_FRAC)
    oc_ids = np.sort(rng.choice(N_SEG, n_oc, replace=False))
    chans.append(("speech", n_sp, sp_ids))
    chans.append(("ocr", n_oc, oc_ids))
    rows = []
    vecs = {"visual": None, "speech": None, "ocr": None}
    for name, n, ids in chans:
        # each channel gets its OWN vector (three provenance channels are three spaces)
        v = unit(seeds[ids] + rng.standard_normal((n, D), dtype=np.float32) * 0.35)
        vecs[name] = v
        rows.append((name, ids, v))
    return rows, vecs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--db", default=os.path.join(STORE_DIR, "index.db"))
    a = ap.parse_args()
    import sqlite_vec

    os.makedirs(STORE_DIR, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        p = a.db + suffix
        if os.path.exists(p):
            os.remove(p)

    rng = np.random.default_rng(20261008)
    t0 = time.perf_counter()
    rows, vecs = build_corpus(rng)
    gen_s = time.perf_counter() - t0
    n_vec = sum(len(ids) for _, ids, _ in rows)
    res = {
        "probe": "_index-store-probe.py",
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sqlite_vec_version": getattr(sqlite_vec, "__version__", None),
        "sqlite_version": sqlite3.sqlite_version,
        "dims": D,
        "videos": N_VIDEO,
        "segments": N_SEG,
        "vectors_total": n_vec,
        "vectors_by_channel": {n: int(len(ids)) for n, ids, _ in rows},
        "corpus_gen_s": round(gen_s, 2),
    }

    db = sqlite3.connect(a.db)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute("pragma journal_mode=WAL")
    db.execute("pragma synchronous=NORMAL")
    res["sqlite_vec_python"] = getattr(sqlite_vec, "__version__", None)
    res["vec_version_sql"] = db.execute("select vec_version()").fetchone()[0]
    try:
        db.execute(
            """create virtual table vec_seg using vec0(
                 vec_id integer primary key,
                 video_id integer partition key,
                 channel text,
                 start_ms integer,
                 seg_id integer,
                 emb float[256] distance_metric=cosine)"""
        )
        res["constructor"] = "cosine, partition_key=video_id, metadata=channel/start_ms/seg_id"
    except sqlite3.OperationalError as e:
        res["constructor"] = "cosine REFUSED (%s) -- fell back to L2 on unit vectors" % e
        db.execute(
            """create virtual table vec_seg using vec0(
                 vec_id integer primary key,
                 video_id integer partition key,
                 channel text,
                 start_ms integer,
                 seg_id integer,
                 emb float[256])"""
        )

    # the ordinary relational half: video + segment + transcript + ocr + marker
    db.executescript(
        """
        create table video(id integer primary key, path text, duration_ms integer,
                           mtime_ns integer, size_bytes integer, first_bytes_sha256 text,
                           indexed_at integer, state text);
        create table segment(seg_id integer primary key, video_id integer, start_ms integer,
                             end_ms integer, n_visual integer default 0, n_ocr integer default 0,
                             n_speech integer default 0);
        create table transcript(seg_id integer, start_ms integer, end_ms integer, text text,
                                producer text);
        create table ocr(seg_id integer, start_ms integer, end_ms integer, text text, box text);
        create table marker(seg_id integer, kind text, value text, source text);
        create index segment_video on segment(video_id, start_ms);
        """
    )
    db.executemany(
        "insert into video values(?,?,?,?,?,?,?,?)",
        [
            (v, r"H:\Videos\clips\clip_%04d.mp4" % v, 600_000 + (v % 7) * 1000,
             1770000000000000000 + v, 300_000_000 + v, "sha256:%064x" % v, int(time.time()), "indexed")
            for v in range(N_VIDEO)
        ],
    )
    db.executemany(
        "insert into segment values(?,?,?,?,?,?,?)",
        [
            (s, s // SEG_PER_VIDEO, (s % SEG_PER_VIDEO) * 5000, (s % SEG_PER_VIDEO) * 5000 + 5000, 1, 0, 0)
            for s in range(N_SEG)
        ],
    )

    # ---- INSERT (this is the light real-time writer's ceiling) ----
    t0 = time.perf_counter()
    n = 0
    for name, ids, v in rows:
        vid = ids // SEG_PER_VIDEO
        sm = (ids % SEG_PER_VIDEO) * 5000
        db.executemany(
            "insert into vec_seg(vec_id, video_id, channel, start_ms, seg_id, emb) values(?,?,?,?,?,?)",
            [
                (int(ids[i]) * 4 + {"visual": 0, "speech": 1, "ocr": 2}[name], int(vid[i]), name,
                 int(sm[i]), int(ids[i]), sqlite_vec.serialize_float32(v[i]))
                for i in range(len(ids))
            ],
        )
        n += len(ids)
    db.commit()
    ins_s = time.perf_counter() - t0
    res["insert"] = {"vectors": n, "seconds": round(ins_s, 2), "vectors_per_s": round(n / ins_s),
                     "ms_per_vector": round(ins_s / n * 1e3, 4)}
    res["count_vec_seg"] = db.execute("select count(*) from vec_seg").fetchone()[0]

    q = unit(rng.standard_normal(D, dtype=np.float32))
    qblob = sqlite_vec.serialize_float32(q)
    res["knn_sql"] = {}

    def knn(sql, params=None, reps=8):
        params = list(params or [])
        cur_prep = db.execute(sql, params + [qblob])
        return ms(lambda: db.execute(sql, params + [qblob]).fetchall(), reps=reps), len(cur_prep.fetchall())

    # k sweep, unfiltered (all three channels in one table)
    for k in (10, 100, 1000):
        t, got = knn("select seg_id, channel, distance from vec_seg where emb match ? and k=%d order by distance" % k, [], reps=5)
        t["rows_returned"] = got
        res["knn_sql"]["k=%d" % k] = t
    # channel equality -- "which channel matched" (the provenance chip)
    t, got = knn("select seg_id, channel, distance from vec_seg where emb match ? and k=100 and channel='speech'")
    t["rows_returned"] = got
    res["knn_sql"]["k=100 channel=speech"] = t
    # time window: 60 s of the library (what "in this window" costs)
    t, got = knn("select seg_id, channel, distance from vec_seg where emb match ? and k=100 and start_ms>=100000 and start_ms<160000")
    t["rows_returned"] = got
    res["knn_sql"]["k=100 start_ms in [100000,160000)"] = t
    # partition key probe: one video (120 visual + ~72 speech + ~19 ocr rows)
    t, got = knn("select seg_id, channel, distance from vec_seg where emb match ? and k=100 and video_id=42")
    t["rows_returned"] = got
    res["knn_sql"]["k=100 video_id=42 (partition key)"] = t

    # ---- the answer shape: vector hit -> "open file X at 03:41.2" ----
    sql_answer = """
    with hits as (
      select seg_id, channel, distance from vec_seg
      where emb match ? and k=100 order by distance
    )
    select h.seg_id, s.start_ms, v.path, h.channel, h.distance
    from hits h join segment s on s.seg_id = h.seg_id join video v on v.id = s.video_id
    limit 10"""
    t = ms(lambda: db.execute(sql_answer, [qblob]).fetchall(), reps=5)
    first = db.execute(sql_answer, [qblob]).fetchall()[0]
    t["first_row"] = {"seg_id": first[0], "start_ms": first[1], "path": first[2], "channel": first[3],
                      "distance": round(first[4], 4),
                      "hms": "%02d:%02d.%d" % (first[1] // 60000, (first[1] // 1000) % 60, (first[1] % 1000) // 100)}
    res["answer_query"] = t

    db.commit()
    db.execute("pragma wal_checkpoint(TRUNCATE)")
    db.close()
    res["disk"] = {s or "db": os.path.getsize(a.db + s) for s in ("", "-wal", "-shm")
                   if os.path.exists(a.db + s)}
    res["disk"]["db_MiB"] = round(res["disk"]["db"] / 2**20, 1)

    # ---- the SAME queries in numpy, same filters, same data ----
    X = np.zeros((n_vec, D), dtype=np.float32)
    Xm = np.zeros(n_vec, dtype=bool)
    Xsp = np.zeros(n_vec, dtype=bool)
    rowid = np.zeros(n_vec, dtype=np.int64)
    segid = np.zeros(n_vec, dtype=np.int64)
    startms = np.zeros(n_vec, dtype=np.int64)
    off = 0
    for name, ids, v in rows:
        m = len(ids)
        X[off:off + m] = v
        rowid[off:off + m] = ids * 4 + {"visual": 0, "speech": 1, "ocr": 2}[name]
        segid[off:off + m] = ids
        startms[off:off + m] = (ids % SEG_PER_VIDEO) * 5000
        if name == "visual":
            Xm[off:off + m] = True
        elif name == "speech":
            Xsp[off:off + m] = True
        off += m
    res["numpy_matrix_MiB"] = round(X.nbytes / 2**20, 1)

    def np_knn(mask, k=100):
        s = X @ q
        s = np.where(mask, s, -np.inf)
        idx = np.argpartition(s, -k)[-k:]
        return idx[np.argsort(-s[idx])]

    for label, mask in (("no filter", np.ones(n_vec, bool)), ("speech only", Xsp),
                        ("window 60 s", (startms >= 100000) & (startms < 160000))):
        t = ms(lambda m=mask: np_knn(m), reps=8)
        t["candidates_after_filter"] = int(mask.sum())
        res.setdefault("knn_numpy_k100", {})[label] = t
    t = ms(lambda: np_knn(Xm, 10), reps=8)
    res["knn_numpy_k10_unfiltered"] = t

    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
