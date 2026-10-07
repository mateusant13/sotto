"""FUSION of the three provenance channels + the reranker's arithmetic.

Part 1 -- fusion: one KNN per channel against the store built by `_index-store-probe.py`,
  merged with Reciprocal Rank Fusion, restricted to a time window, and every hit carrying its
  OWN evidence (which channel matched, at what rank, and the text/OCR line that gave it).
  Latency is measured for the whole "query -> 10 explainable hits" path.

Part 2 -- reranker: the DENOMINATOR measured here (this box's multi-threaded fp32 GEMM rate),
  against READ parameter counts of the real candidate models; FLOPs = 2 x P x L per candidate.
  No model is downloaded and none is loaded -- this is arithmetic on measured throughput.

Run: python _main/_index-fusion-probe.py [--json OUT] [--db ...]
"""
import argparse
import json
import os
import sqlite3
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "_index-store", "index.db")
D = 256
RRF_K = 60
W = {"speech": 1.0, "ocr": 1.0, "visual": 0.7}      # the fusion rule's one tuning knob
N_VIDEO, SEG_PER_VIDEO = 1000, 120


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


def gemm_rate():
    """The box's own throughput, so the reranker latency is not a guess about hardware."""
    import platform
    out = {"cpu": platform.processor(), "threads_env": {k: os.environ.get(k) for k in
           ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}}
    rng = np.random.default_rng(5)
    out["shapes"] = {}
    for (m, k, n) in ((512, 512, 512), (512, 1024, 3072), (64, 384, 1536), (6400, 768, 768)):
        A = rng.standard_normal((m, k), dtype=np.float32)
        B = rng.standard_normal((k, n), dtype=np.float32)
        t = ms(lambda: A @ B, reps=5, warm=2)["min_ms"] / 1e3
        flops = 2.0 * m * k * n
        out["shapes"]["%dx%dx%d" % (m, k, n)] = {
            "ms": round(t * 1e3, 3), "GFLOP": round(flops / 1e9, 3),
            "GFLOP_per_s": round(flops / t / 1e9, 1)}
    return out


def reranker_table(gflops_per_s):
    """Candidates: params are READ from the HF API (URL in the receipt); FLOPs is arithmetic."""
    cands = [
        ("cross-encoder/ms-marco-MiniLM-L6-v2", 22_714_113, "apache-2.0"),
        ("mixedbread-ai/mxbai-rerank-xsmall-v1", 70_830_337, "apache-2.0"),
        ("mixedbread-ai/mxbai-rerank-base-v1", 184_422_913, "apache-2.0"),
        ("BAAI/bge-reranker-base", 278_044_931, "mit"),
        ("jinaai/jina-reranker-v2-base-multilingual", 278_437_633, "cc-by-nc-4.0 (NOT shippable)"),
        ("BAAI/bge-reranker-v2-m3", 567_755_777, "apache-2.0"),
        ("Qwen/Qwen3-Reranker-0.6B", 595_776_512, "apache-2.0"),
    ]
    rows = []
    for name, p, lic in cands:
        r = {"model": name, "params": p, "license": lic, "fp16_disk_MiB": round(p * 2 / 2**20, 1),
             "int8_disk_MiB": round(p / 2**20, 1)}
        for L in (64, 128):
            fl = 2.0 * p * 100 * L            # 100 candidates, L tokens each, 2 FLOP per MAC
            r["L%d" % L] = {
                "TFLOP": round(fl / 1e12, 3),
                "s_at_fp32_measured": round(fl / (gflops_per_s["fp32"] * 1e9), 2),
                "s_at_int8_kernel_158.9": round(fl / (158.9e9), 2),
                "s_at_int4_kernel_398": round(fl / (398e9), 2),
            }
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--db", default=STORE)
    a = ap.parse_args()
    import sqlite_vec

    res = {"probe": "_index-fusion-probe.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rrf_k": RRF_K, "channel_weights": W}

    g = gemm_rate()
    res["gemm_measured"] = g
    gfl = {"fp32": g["shapes"]["512x512x512"]["GFLOP_per_s"],
           "fp32_big": g["shapes"]["512x1024x3072"]["GFLOP_per_s"]}
    res["gemm_measured"]["fp32_for_reranker"] = gfl["fp32"]
    res["reranker_arithmetic"] = reranker_table(gfl)

    if not os.path.exists(a.db):
        res["fusion"] = "SKIPPED: %s absent (run _index-store-probe.py first)" % a.db
    else:
        db = sqlite3.connect(a.db)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        rng = np.random.default_rng(99)
        q = rng.standard_normal(D, dtype=np.float32)
        q /= np.linalg.norm(q)
        qb = sqlite_vec.serialize_float32(q)

        def channel_hits(chan, k=100, window=None):
            sql = ("select seg_id, start_ms, distance from vec_seg "
                   "where emb match ? and k=%d and channel='%s'" % (k, chan))
            params = [qb]
            if window:
                sql += " and start_ms>=? and start_ms<?"
                params += list(window)
            return db.execute(sql, params).fetchall()

        def fuse(window=None, k=100):
            lists = {}
            for ch in ("speech", "ocr", "visual"):
                lists[ch] = channel_hits(ch, k, window)
            score, why = {}, {}
            for ch, rows in lists.items():
                for rank, (seg_id, start_ms, dist) in enumerate(rows):
                    score[seg_id] = score.get(seg_id, 0.0) + W[ch] / (RRF_K + rank + 1)
                    why.setdefault(seg_id, []).append(
                        {"channel": ch, "rank": rank + 1, "distance": round(dist, 4)})
            top = sorted(score.items(), key=lambda kv: -kv[1])[:10]
            out = []
            for seg_id, sc in top:
                meta = db.execute(
                    """select v.path, s.start_ms, s.video_id,
                              (select text from transcript t where t.seg_id=s.seg_id limit 1),
                              (select text from ocr o where o.seg_id=s.seg_id limit 1)
                       from segment s join video v on v.id=s.video_id where s.seg_id=?""",
                    (seg_id,)).fetchone()
                start = meta[1]
                out.append({
                    "seg_id": seg_id,
                    "open": "%s @ %02d:%02d.%d" % (os.path.basename(meta[0]), start // 60000,
                                                   (start // 1000) % 60, (start % 1000) // 100),
                    "path": meta[0], "video_id": meta[2],
                    "score": round(sc, 6),
                    "channels": sorted({w["channel"] for w in why[seg_id]}),
                    "why": why[seg_id],
                    "speech_text": meta[3], "ocr_text": meta[4],
                })
            return out

        one = channel_hits("speech", 100)
        res["per_channel_hits"] = {ch: len(channel_hits(ch, 100)) for ch in ("speech", "ocr", "visual")}
        res["fusion_latency_ms"] = {
            "all_channels_no_window": ms(lambda: fuse(), reps=5),
            "all_channels_60s_window": ms(lambda: fuse(window=(100000, 160000)), reps=5),
        }
        res["unfiltered_hit_count_matches_window"] = (
            "window 100000..160000 keeps only segments in that minute of each video")
        res["fusion_top10_example"] = fuse()[:10]
        res["explainability_check"] = {
            "every_hit_names_its_channels": all(r["channels"] for r in res["fusion_top10_example"]),
            "channels_seen": sorted({c for r in res["fusion_top10_example"] for c in r["channels"]}),
        }
        db.close()

    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
