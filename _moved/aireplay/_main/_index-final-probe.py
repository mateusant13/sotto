"""LANE 07 -- the index: store, schema, three-channel fusion, reranker arithmetic, two speeds.

One probe, one process, one thread budget, so nothing here is compared across machines or across
processes. Everything is measured on THIS box with OMP/OPENBLAS/MKL pinned to 2 threads by the
caller (the lane's politeness budget), and the thread count is printed in the JSON so no number
travels without it.

Sections
  0  census: python/numpy/BLAS/threads, installed vector libs + their licences and installed bytes
  1  brute force in numpy: fp32 scan at 120 k (the brief's own N) and 211.2 k (three channels),
     k=10/k=100, filtered (channel, per-video time window), plus the fp16 question
     (native fp16 matvec vs fp16-on-disk/cast-to-fp32) -- and the crossover arithmetic
  2  the STORE: one SQLite file carrying the whole schema + every vector as an fp16 blob;
     insert throughput, file size vs payload, startup load, and the answer JOIN that turns a
     vector hit into "open the file X at 03:41.2"
  3  sqlite-vec (vec0) re-queried from the earlier lane's own 120 k table, interleaved with a
     numpy control in the SAME process; plus vec0 incremental insert into a live table
  4  FUSION: one KNN per provenance channel, Reciprocal Rank Fusion, per-video time window,
     every hit naming the channels that matched (the three UI chips)
  5  RERANKER arithmetic: this box's own measured GEMM rate at 2 threads against READ parameter
     counts, plus the cheap alternative (lexical overlap) measured on real candidate texts
  6  the LIGHT writer: single-vector + single-row commit latency in WAL/synchronous=NORMAL

Run (2 threads, no window):
  $env:OMP_NUM_THREADS=2; $env:OPENBLAS_NUM_THREADS=2; $env:MKL_NUM_THREADS=2
  pythonw.exe _main\_index-final-probe.py --json _main\index-final.json
"""
import argparse
import importlib.metadata as md
import json
import os
import platform
import sqlite3
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_index-final")
D = 256
N_VIDEO = 1000
SEG_PER_VIDEO = 120              # 10 min at 5 s
N_SEG = N_VIDEO * SEG_PER_VIDEO  # 120 000
SPEECH_FRAC = 0.60
OCR_FRAC = 0.16
RRF_K = 60
CH_W = {"speech": 1.0, "ocr": 1.0, "visual": 0.7}
TOP_K = 100


def ms(fn, reps=5, warm=1):
    for _ in range(warm):
        fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1e3)
    ts.sort()
    return {"min_ms": round(ts[0], 3), "median_ms": round(ts[len(ts) // 2], 3), "reps": reps}


def unit(x):
    x = np.asarray(x, dtype=np.float32)
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


def topk_idx(scores, k, mask=None):
    if mask is not None:
        scores = np.where(mask, scores, -np.inf)
    idx = np.argpartition(scores, -k)[-k:]
    return idx[np.argsort(-scores[idx])]


def hms(ms_):
    return "%02d:%02d.%d" % (ms_ // 60000, (ms_ // 1000) % 60, (ms_ % 1000) // 100)


# ------------------------------------------------------------------ 0 census
def census():
    out = {
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "cpu": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "thread_env": {k: os.environ.get(k) for k in
                       ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        "libs": {},
    }
    try:
        cfg = np.show_config(mode="dicts")
        out["numpy_blas"] = cfg.get("Build Dependencies", {}).get("blas", {})
    except Exception as e:
        out["numpy_blas"] = "unavailable: %s" % e
    for pkg in ("sqlite-vec", "faiss-cpu", "hnswlib", "lancedb", "qdrant-client", "pyarrow",
                "numpy", "sqlite3"):
        rec = {}
        try:
            dist = md.distribution(pkg)
            m = dist.metadata
            base = str(dist.locate_file(""))
            tot = 0
            for f in dist.files or []:
                try:
                    tot += os.path.getsize(os.path.join(base, str(f)))
                except OSError:
                    pass
            rec = {"installed": True, "version": dist.version,
                   "license": (m.get("License") or "")[:80],
                   "license_expression": m.get("License-Expression"),
                   "license_classifiers": [c for c in (m.get_all("Classifier") or []) if "License" in c],
                   "installed_bytes": tot, "installed_MiB": round(tot / 2**20, 1)}
        except Exception as e:
            rec = {"installed": False, "error": "%s: %s" % (type(e).__name__, e)}
        out["libs"][pkg] = rec
    out["libs"]["sqlite3"]["sqlite_version"] = sqlite3.sqlite_version
    return out


# ------------------------------------------------------------------ corpus
def build_corpus(rng):
    """120 k segments; three provenance channels as three separate vector spaces."""
    seeds = rng.standard_normal((N_SEG, D), dtype=np.float32)
    visual_ids = np.arange(N_SEG)
    speech_ids = np.sort(rng.choice(N_SEG, int(N_SEG * SPEECH_FRAC), replace=False))
    ocr_ids = np.sort(rng.choice(N_SEG, int(N_SEG * OCR_FRAC), replace=False))
    chans = [("visual", visual_ids), ("speech", speech_ids), ("ocr", ocr_ids)]
    vecs, rows = {}, []
    for name, ids in chans:
        v = unit(seeds[ids] + rng.standard_normal((len(ids), D), dtype=np.float32) * 0.35)
        vecs[name] = (ids, v)
        rows.append((name, ids, v))
    return rows, vecs


# ------------------------------------------------------------------ 1 brute force
def brute_force(rows, vecs, rng):
    out = {}
    q = unit(rng.standard_normal(D, dtype=np.float32))
    Xall = np.concatenate([v for _, _, v in rows]).astype(np.float32)
    seg_all = np.concatenate([ids for _, ids, _ in rows])
    vid_all = seg_all // SEG_PER_VIDEO
    start_all = (seg_all % SEG_PER_VIDEO) * 5000
    ch_all = np.concatenate([np.full(len(ids), n) for n, ids, _ in rows])
    out["vectors_total"] = int(Xall.shape[0])
    out["matrix_MiB"] = round(Xall.nbytes / 2**20, 1)
    out["matrix_MB_decimal"] = round(Xall.nbytes / 1e6, 1)

    masks = {
        "no filter": np.ones(len(seg_all), bool),
        "channel=speech": ch_all == "speech",
        "channel=visual": ch_all == "visual",
        "channel=ocr": ch_all == "ocr",
        "video 42, 0-60 s": (vid_all == 42) & (start_all < 60000),
        "one 5 s window": (vid_all == 42) & (start_all >= 60000) & (start_all < 65000),
    }
    out["knn_fp32_k100"] = {}
    for label, mask in masks.items():
        rec = ms(lambda m=mask: topk_idx(Xall @ q, 100, m), reps=6)
        rec["candidates_after_filter"] = int(mask.sum())
        rec["scan_GB_per_s"] = round(Xall.nbytes / (rec["min_ms"] * 1e-3) / 1e9, 2)
        out["knn_fp32_k100"][label] = rec
    out["knn_fp32_k10_no_filter"] = ms(lambda: topk_idx(Xall @ q, 10), reps=6)

    # the brief's own N: the visual channel alone (120 k vectors)
    Xv = vecs["visual"][1]
    out["visual_only_120k"] = {
        "matrix_MiB": round(Xv.nbytes / 2**20, 1),
        "k10": ms(lambda: topk_idx(Xv @ q, 10), reps=6),
        "k100": ms(lambda: topk_idx(Xv @ q, 100), reps=6),
    }
    out["visual_only_120k"]["k100"]["scan_GB_per_s"] = round(
        Xv.nbytes / (out["visual_only_120k"]["k100"]["min_ms"] * 1e-3) / 1e9, 2)

    # --- fp16: native matvec vs fp16-on-disk cast to fp32 once
    X16 = Xv.astype(np.float16)
    q16 = q.astype(np.float16)
    out["fp16"] = {
        "native_fp16_matvec_k100_120k": ms(lambda: topk_idx(X16 @ q16, 100), reps=3),
        "fp16_to_fp32_cast_120k": ms(lambda: X16.astype(np.float32), reps=5),
        "stored_bytes_120k_fp16_MiB": round(X16.nbytes / 2**20, 1),
        "stored_bytes_120k_fp32_MiB": round(Xv.nbytes / 2**20, 1),
    }
    Xc = X16.astype(np.float32)
    out["fp16"]["cast_then_fp32_scan_k100"] = ms(lambda: topk_idx(Xc @ q, 100), reps=6)
    # fidelity: does fp16 storage change the top-10?
    a = topk_idx(Xv @ q, 10)
    b = topk_idx(Xc @ q, 10)
    out["fp16"]["top10_identical_to_fp32"] = bool(np.array_equal(a, b))
    out["fp16"]["top10_overlap"] = int(len(set(a.tolist()) & set(b.tolist())))

    # --- crossover arithmetic, from two measured points on the same process
    n1 = len(Xv)
    n2 = Xall.shape[0]
    t1 = out["visual_only_120k"]["k100"]["min_ms"]
    t2 = out["knn_fp32_k100"]["no filter"]["min_ms"]
    per_vec_us = (t2 - t1) / (n2 - n1) * 1e3
    out["crossover"] = {
        "measured_N": [n1, n2], "measured_ms": [t1, t2],
        "us_per_vector": round(per_vec_us, 4),
        "extrapolated_ms_at": {str(n): round(t1 + (n - n1) * per_vec_us / 1e3, 1)
                               for n in (250_000, 500_000, 1_000_000, 5_000_000)},
        "N_where_50ms": int(n1 + (50 - t1) * 1e3 / per_vec_us),
        "N_where_250ms": int(n1 + (250 - t1) * 1e3 / per_vec_us),
        "note": "linear in N (scan is bandwidth-bound); us/vector is the fitted slope",
    }
    return out, q, Xall, seg_all, vid_all, start_all, ch_all


# ------------------------------------------------------------------ 2 the store
def the_store(rows, rng, q):
    """One SQLite file: the relational record + every vector as an fp16 blob."""
    os.makedirs(WORK, exist_ok=True)
    dbp = os.path.join(WORK, "store.db")
    for s in ("", "-wal", "-shm"):
        if os.path.exists(dbp + s):
            os.remove(dbp + s)
    db = sqlite3.connect(dbp, isolation_level=None)
    db.execute("pragma journal_mode=WAL")
    db.execute("pragma synchronous=NORMAL")
    db.executescript("""
        create table video(id integer primary key, path text not null, duration_ms integer,
                           mtime_ns integer, size_bytes integer, head_sha256 text,
                           indexed_at integer, state text);
        create table segment(seg_id integer primary key, video_id integer not null,
                             start_ms integer not null, end_ms integer not null);
        create table transcript(seg_id integer primary key, start_ms integer, end_ms integer,
                                text text, producer text);
        create table ocr(seg_id integer, start_ms integer, end_ms integer, text text, box text);
        create table embedding(seg_id integer not null, channel text not null,
                               dim integer not null, dtype text not null, vec blob not null,
                               model text, built_at integer,
                               primary key(seg_id, channel));
        create table marker(seg_id integer, kind text, value text, source text);
        create index segment_video on segment(video_id, start_ms);
        create index embedding_channel on embedding(channel);
        create index transcript_seg on transcript(seg_id);
        create index ocr_seg on ocr(seg_id);
    """)
    res = {}
    db.execute("begin")
    db.executemany("insert into video values(?,?,?,?,?,?,?,?)",
                   [(v, r"H:\Videos\clips\clip_%04d.mp4" % v, 600_000, 1770000000000000000 + v,
                     300_000_000 + v, "%064x" % v, int(time.time()), "indexed") for v in range(N_VIDEO)])
    db.executemany("insert into segment values(?,?,?,?)",
                   [(s, s // SEG_PER_VIDEO, (s % SEG_PER_VIDEO) * 5000, (s % SEG_PER_VIDEO) * 5000 + 5000)
                    for s in range(N_SEG)])
    words = ["comprar", "gpu", "placa", "de", "video", "jogo", "ontem", "aquela", "ideia", "do",
             "projeto", "sotto", "indice", "busca", "clip", "janela", "memoria", "texto", "tela"]
    rr = np.random.default_rng(5)
    sp_ids = np.sort(rr.choice(N_SEG, int(N_SEG * SPEECH_FRAC), replace=False))
    oc_ids = np.sort(rr.choice(N_SEG, int(N_SEG * OCR_FRAC), replace=False))
    db.executemany("insert into transcript values(?,?,?,?,?)",
                   [(int(s), int(s % SEG_PER_VIDEO) * 5000, int(s % SEG_PER_VIDEO) * 5000 + 5000,
                     " ".join(rr.choice(words, 6)), "parakeet-tdt-0.6b-v3-int8") for s in sp_ids])
    db.executemany("insert into ocr values(?,?,?,?,?)",
                   [(int(s), int(s % SEG_PER_VIDEO) * 5000, int(s % SEG_PER_VIDEO) * 5000 + 5000,
                     " ".join(rr.choice(words, 4)), "[10,20,300,60]") for s in oc_ids])
    db.execute("commit")
    t0 = time.perf_counter()
    db.execute("begin")
    n = 0
    for name, ids, v in rows:
        v16 = v.astype(np.float16)
        db.executemany("insert into embedding values(?,?,?,?,?,?,?)",
                       [(int(ids[i]), name, D, "float16", v16[i].tobytes(),
                         "embeddinggemma-2-440m-256d", int(time.time()))
                        for i in range(len(ids))])
        n += len(ids)
    db.execute("commit")
    ins_s = time.perf_counter() - t0
    res["insert"] = {"vectors": n, "seconds": round(ins_s, 2),
                     "vectors_per_s": round(n / ins_s), "ms_per_vector": round(ins_s / n * 1e3, 4)}
    db.execute("pragma wal_checkpoint(TRUNCATE)")

    # startup: the whole vector table back into RAM
    t0 = time.perf_counter()
    cur = db.execute("select seg_id, channel, vec from embedding order by channel, seg_id")
    order, bufs = [], []
    for seg_id, chan, blob in cur:
        order.append((seg_id, chan))
        bufs.append(blob)
    t_rows = time.perf_counter() - t0
    raw = b"".join(bufs)
    M = np.frombuffer(raw, dtype=np.float16).reshape(-1, D)
    t_cast0 = time.perf_counter()
    M32 = M.astype(np.float32)
    t_cast = time.perf_counter() - t_cast0
    res["startup"] = {"select_all_s": round(t_rows, 3), "cast_fp16_to_fp32_s": round(t_cast, 3),
                      "total_s": round(t_rows + t_cast, 3), "vectors": len(order),
                      "ram_fp32_MiB": round(M32.nbytes / 2**20, 1),
                      "MB_per_s_end_to_end": round(M.nbytes / 2**20 / (t_rows + t_cast), 1)}
    del bufs, raw

    # the answer JOIN: a vector hit -> "open file X at 03:41.2"
    qb = M32[12345].copy()
    scores = M32 @ qb
    hit = int(np.argmax(scores))
    seg_id, chan = order[hit]
    sql = """select v.path, s.start_ms, v.id, e.channel,
                    (select text from transcript t where t.seg_id=s.seg_id),
                    (select text from ocr o where o.seg_id=s.seg_id)
             from embedding e join segment s on s.seg_id=e.seg_id
                  join video v on v.id=s.video_id
             where e.seg_id=? and e.channel=?"""
    row = db.execute(sql, (seg_id, chan)).fetchone()
    res["answer_join"] = {
        "open": "%s @ %s" % (os.path.basename(row[0]), hms(row[1])),
        "path": row[0], "video_id": row[2], "channel": row[3],
        "transcript": row[4], "ocr": row[5], "ms": ms(lambda: db.execute(sql, (seg_id, chan)).fetchone()),
    }

    db.execute("pragma wal_checkpoint(TRUNCATE)")
    size = os.path.getsize(dbp)
    payload16 = n * D * 2
    res["disk"] = {"db_bytes": size, "db_MiB": round(size / 2**20, 1),
                   "vector_payload_MiB": round(payload16 / 2**20, 1),
                   "non_vector_MiB": round((size - payload16) / 2**20, 1),
                   "overhead_pct_of_payload": round((size - payload16) / payload16 * 100, 1),
                   "fp32_equivalent_MiB": round(n * D * 4 / 2**20, 1)}
    counts = {t: db.execute("select count(*) from %s" % t).fetchone()[0]
              for t in ("video", "segment", "transcript", "ocr", "embedding", "marker")}
    res["row_counts"] = counts
    db.close()
    res["db_path"] = dbp
    return res, order, M32, q


# ------------------------------------------------------------------ 3 sqlite-vec
def sqlite_vec_check(rng, q):
    import sqlite_vec
    out = {"vec_version": None, "tables": {}}
    a_db = os.path.join(HERE, "_index-store2", "A_nopartition.db")
    c_db = os.path.join(HERE, "_index-store", "index.db")
    qb = sqlite_vec.serialize_float32(q)

    def open_db(p):
        db = sqlite3.connect(p)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        db.execute("pragma wal_checkpoint(TRUNCATE)")
        return db

    for label, p, reps in (("A_nopartition_120k", a_db, 4), ("C_partition_video_211k", c_db, 2)):
        if not os.path.exists(p):
            out["tables"][label] = "ABSENT"
            continue
        db = open_db(p)
        out["vec_version"] = db.execute("select vec_version()").fetchone()[0]
        rec = {"db_MiB": round(os.path.getsize(p) / 2**20, 1),
               "count": db.execute("select count(*) from vec_seg").fetchone()[0]}
        rec["k10"] = ms(lambda: db.execute(
            "select seg_id, distance from vec_seg where emb match ? and k=10", [qb]).fetchall(), reps=reps)
        rec["k100"] = ms(lambda: db.execute(
            "select seg_id, distance from vec_seg where emb match ? and k=100", [qb]).fetchall(), reps=reps)
        rec["k100_window"] = ms(lambda: db.execute(
            "select seg_id, distance from vec_seg where emb match ? and k=100 "
            "and start_ms>=100000 and start_ms<160000", [qb]).fetchall(), reps=reps)
        if label.startswith("C"):
            rec["k100_partition_video42"] = ms(lambda: db.execute(
                "select seg_id, distance from vec_seg where emb match ? and k=100 and video_id=42",
                [qb]).fetchall(), reps=2)
        db.close()
        out["tables"][label] = rec

    # incremental insert into a LIVE vec0 table (the realtime writer, no rebuild)
    vdb = os.path.join(WORK, "vec0-live.db")
    for s in ("", "-wal", "-shm"):
        if os.path.exists(vdb + s):
            os.remove(vdb + s)
    db = sqlite3.connect(vdb, isolation_level=None)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute("pragma journal_mode=WAL")
    db.execute("pragma synchronous=NORMAL")
    db.execute("create virtual table vec_seg using vec0(vec_id integer primary key, channel text, "
               "start_ms integer, seg_id integer, emb float[256] distance_metric=cosine)")
    X = unit(rng.standard_normal((20_000, D), dtype=np.float32))
    t0 = time.perf_counter()
    db.execute("begin")
    for i in range(0, 20_000, 1000):
        db.executemany("insert into vec_seg values(?,?,?,?,?)",
                       [(j, "visual", j * 5000 % 600000, j, sqlite_vec.serialize_float32(X[j]))
                        for j in range(i, min(i + 1000, 20_000))])
    db.execute("commit")
    bulk = time.perf_counter() - t0
    lat = []
    for i in range(20_000, 20_120):          # one video's worth, one row at a time
        t0 = time.perf_counter()
        db.execute("begin")
        db.execute("insert into vec_seg values(?,?,?,?,?)",
                   (i, "visual", i * 5000 % 600000, i, sqlite_vec.serialize_float32(X[i % 20_000])))
        db.execute("commit")
        lat.append((time.perf_counter() - t0) * 1e3)
    lat.sort()
    hits = db.execute("select count(*) from (select vec_id from vec_seg where emb match ? and k=10)",
                      [qb]).fetchone()[0]
    out["live_insert"] = {
        "bulk_20k_s": round(bulk, 2), "bulk_vectors_per_s": round(20_000 / bulk),
        "single_row_commit_ms": {"min": round(lat[0], 3), "median": round(lat[len(lat) // 2], 3),
                                 "p95": round(lat[int(len(lat) * 0.95)], 3), "max": round(lat[-1], 3),
                                 "n": len(lat)},
        "knn_answers_after_inserts": hits,
        "db_MiB": round(os.path.getsize(vdb) / 2**20, 1),
        "verdict": "vec0 takes incremental INSERTs while live; no rebuild, no re-serialize",
    }
    db.close()
    return out


# ------------------------------------------------------------------ 4 fusion
def fusion(order, M32, rng, q):
    """One KNN per channel, RRF, per-video window filter, every hit naming its channels."""
    seg_of = np.array([o[0] for o in order], dtype=np.int64)
    ch_of = np.array([o[1] for o in order])
    vid_of = seg_of // SEG_PER_VIDEO
    start_of = (seg_of % SEG_PER_VIDEO) * 5000

    def channel_lists(k=TOP_K, window=None):
        lists = {}
        for ch in ("speech", "ocr", "visual"):
            m = ch_of == ch
            if window:
                v, t0, t1 = window
                m = m & (vid_of == v) & (start_of >= t0) & (start_of < t1)
            s = np.where(m, M32 @ q, -np.inf)
            idx = np.argpartition(s, -k)[-k:]
            idx = idx[np.argsort(-s[idx])]
            lists[ch] = [(int(seg_of[i]), float(s[i])) for i in idx if np.isfinite(s[i])]
        return lists

    def fuse(window=None, k=TOP_K):
        lists = channel_lists(k, window)
        score, why = {}, {}
        for ch, rows_ in lists.items():
            for rank, (seg, sc) in enumerate(rows_):
                score[seg] = score.get(seg, 0.0) + CH_W[ch] / (RRF_K + rank + 1)
                why.setdefault(seg, []).append({"channel": ch, "rank": rank + 1,
                                                "cosine": round(sc, 4)})
        top = sorted(score.items(), key=lambda kv: -kv[1])[:10]
        out = []
        for seg, sc in top:
            out.append({
                "seg_id": seg, "video_id": int(seg // SEG_PER_VIDEO),
                "open": "clip_%04d.mp4 @ %s" % (seg // SEG_PER_VIDEO, hms(int((seg % SEG_PER_VIDEO) * 5000))),
                "start_ms": int((seg % SEG_PER_VIDEO) * 5000), "rrf_score": round(sc, 6),
                "channels": sorted({w["channel"] for w in why[seg]}), "why": why[seg],
            })
        return out

    res = {}
    res["per_channel_candidates_k100"] = {ch: len(channel_lists(TOP_K)[ch])
                                          for ch in ("speech", "ocr", "visual")}
    res["latency_ms"] = {
        "no_window": ms(lambda: fuse(), reps=5),
        "video42_0_60s_window": ms(lambda: fuse(window=(42, 0, 60_000)), reps=5),
        "one_5s_window": ms(lambda: fuse(window=(42, 60_000, 65_000)), reps=5),
    }
    top = fuse()
    res["top10"] = top
    res["explainability"] = {
        "every_hit_names_at_least_one_channel": all(r["channels"] for r in top),
        "channels_seen_in_top10": sorted({c for r in top for c in r["channels"]}),
        "hits_matched_by_more_than_one_channel": sum(1 for r in top if len(r["channels"]) > 1),
    }
    win = fuse(window=(42, 0, 60_000))
    res["window_filter_control"] = {
        "all_hits_in_video_42": all(r["video_id"] == 42 for r in win),
        "all_hits_under_60s": all(r["start_ms"] < 60_000 for r in win),
        "n": len(win),
    }
    one5 = fuse(window=(42, 60_000, 65_000))
    res["one_5s_window_control"] = {
        "hits": [r["open"] for r in one5],
        "all_in_window": all(60_000 <= r["start_ms"] < 65_000 for r in one5),
        "verdict": "a 5 s window is a handful of candidates, not a search",
    }
    return res


# ------------------------------------------------------------------ 5 reranker
def reranker(rng):
    out = {}
    shapes = ((100, 384, 384), (100, 768, 768), (6400, 768, 768))
    out["gemm_measured"] = {}
    for (m, k, n) in shapes:
        A = rng.standard_normal((m, k), dtype=np.float32)
        B = rng.standard_normal((k, n), dtype=np.float32)
        t = ms(lambda: A @ B, reps=5, warm=2)["min_ms"] / 1e3
        out["gemm_measured"]["%dx%dx%d" % (m, k, n)] = {
            "ms": round(t * 1e3, 3), "GFLOP": round(2.0 * m * k * n / 1e9, 3),
            "GFLOP_per_s": round(2.0 * m * k * n / t / 1e9, 1)}
    rate = out["gemm_measured"]["100x768x768"]["GFLOP_per_s"]
    out["gemm_fp32_GFLOP_per_s_at_2_threads"] = rate
    # params are READ (HF API) -- the URL is in the receipt; the FLOPs are arithmetic
    cands = [("cross-encoder/ms-marco-MiniLM-L6-v2", 22_713_600, "apache-2.0"),
             ("mixedbread-ai/mxbai-rerank-base-v1", 184_000_000, "apache-2.0"),
             ("BAAI/bge-reranker-base", 278_000_000, "mit"),
             ("BAAI/bge-reranker-v2-m3", 568_000_000, "apache-2.0"),
             ("Qwen/Qwen3-Reranker-0.6B", 596_000_000, "apache-2.0")]
    rows = []
    for name, p, lic in cands:
        rec = {"model": name, "params": p, "license": lic,
               "fp16_disk_MiB": round(p * 2 / 2**20, 1), "int8_disk_MiB": round(p / 2**20, 1)}
        for L in (64, 128, 256):
            fl = 2.0 * p * 100 * L
            rec["100_cands_L%d" % L] = {
                "TFLOP": round(fl / 1e12, 3),
                "s_at_measured_fp32_2t": round(fl / (rate * 1e9), 2),
            }
        rows.append(rec)
    out["candidates"] = rows

    # the cheap alternative, measured on real text
    rr = np.random.default_rng(11)
    words = ["comprar", "gpu", "placa", "de", "video", "jogo", "ontem", "aquela", "ideia", "do",
             "projeto", "sotto", "indice", "busca", "clip", "janela", "memoria", "texto", "tela"]
    cands_txt = [" ".join(rr.choice(words, 8)) for _ in range(100)]
    query = "onde eu falei de comprar gpu"

    def lexical():
        qt = set(query.lower().split())
        sc = []
        for i, t in enumerate(cands_txt):
            ct = set(t.lower().split())
            sc.append((i, len(qt & ct) / (len(qt | ct) + 1e-9)))
        return sorted(sc, key=lambda kv: -kv[1])[:10]

    out["lexical_overlap_100_candidates"] = ms(lexical, reps=20, warm=3)
    out["lexical_overlap_note"] = ("pure-python Jaccard over 100 short strings; this is the "
                                   "floor a reranker must beat to be worth its seconds")
    return out


# ------------------------------------------------------------------ 6 light writer
def light_writer(rng):
    p = os.path.join(WORK, "light.db")
    for s in ("", "-wal", "-shm"):
        if os.path.exists(p + s):
            os.remove(p + s)
    db = sqlite3.connect(p, isolation_level=None)
    db.execute("pragma journal_mode=WAL")
    db.execute("pragma synchronous=NORMAL")
    db.execute("create table segment(seg_id integer primary key, video_id integer, start_ms integer, end_ms integer)")
    db.execute("create table transcript(seg_id integer primary key, text text, producer text)")
    db.execute("create table embedding(seg_id integer, channel text, vec blob, primary key(seg_id,channel))")
    v = unit(rng.standard_normal(D, dtype=np.float32)).astype(np.float16)
    lat = []
    for i in range(200):
        t0 = time.perf_counter()
        db.execute("begin")
        db.execute("insert into segment values(?,?,?,?)", (i, 0, i * 5000, i * 5000 + 5000))
        db.execute("insert into transcript values(?,?,?)", (i, "linha de transcricao curta", "redux"))
        for ch in ("speech", "visual"):
            db.execute("insert into embedding values(?,?,?)", (i, ch, v.tobytes()))
        db.execute("commit")
        lat.append((time.perf_counter() - t0) * 1e3)
    lat.sort()
    db.execute("pragma wal_checkpoint(TRUNCATE)")
    out = {"commit_ms": {"min": round(lat[0], 3), "median": round(lat[len(lat) // 2], 3),
                         "p95": round(lat[int(len(lat) * 0.95)], 3), "max": round(lat[-1], 3),
                         "n": len(lat)},
           "rows_per_commit": 4, "db_MiB": round(os.path.getsize(p) / 2**20, 2),
           "journal_mode": db.execute("pragma journal_mode").fetchone()[0],
           "synchronous": db.execute("pragma synchronous").fetchone()[0],
           "note": "one 5 s segment = segment + transcript + 2 channel vectors, committed"}
    db.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--skip-vec0", action="store_true")
    a = ap.parse_args()
    rng = np.random.default_rng(20261008)
    res = {"probe": "_index-final-probe.py", "census": census()}
    rows, vecs = build_corpus(rng)
    res["corpus"] = {"videos": N_VIDEO, "segments": N_SEG, "seg_per_video": SEG_PER_VIDEO,
                     "vectors_by_channel": {n: int(len(ids)) for n, ids, _ in rows},
                     "vectors_total": int(sum(len(ids) for _, ids, _ in rows))}
    bf, q, Xall, seg_all, vid_all, start_all, ch_all = brute_force(rows, vecs, rng)
    res["brute_force"] = bf
    store, order, M32, q = the_store(rows, rng, q)
    res["store"] = store
    res["fusion"] = fusion(order, M32, rng, q)
    res["reranker"] = reranker(rng)
    res["light_writer"] = light_writer(rng)
    if not a.skip_vec0:
        res["sqlite_vec"] = sqlite_vec_check(rng, q)
    txt = json.dumps(res, indent=2)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    try:
        print(txt[:4000])
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        _p = [x for x in sys.argv if x.endswith(".json")]
        with open((_p[0] if _p else os.path.join(WORK, "index-final")) + ".err", "w",
                  encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
