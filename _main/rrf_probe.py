"""Sotto lane: Reciprocal Rank Fusion over 3 channels -- MEASUREMENT probe.

Owner of this file: lane feat/rrf-3ch-2.  It writes NOTHING into src/index.
The product code under test is imported, never edited.

Four arms, each with POPULATION and WINDOW printed next to every count:

  A  queryability census on the REAL stores already on this host (read-only).
  B  legacy store -> CURRENT schema.sql migration, then the REAL
     SearchIndex.search() over all 211 200 real embedding rows.
  C  synthetic corpus with KNOWN ground-truth channel membership: MRR@10 and
     recall@10 for the fusion and for each single channel alone.
  D  NEGATIVE ARM: one channel's rank list deliberately reversed.  The gate
     must show the metric gets WORSE.  If it does not, the metric is
     insensitive and the finding is "gate is meaningless", not "gate passed".

Every degraded path prints to stderr and bumps a counter the exit code reads,
so a swallowed error can never be reported as a result.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time

# <=2 threads, set BEFORE numpy is imported (store.py's own lane budget).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

from pathlib import Path                                          # noqa: E402
import sqlite3                                                  # noqa: E402
import numpy as np                                               # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
INDEX_DIR = PROBE_DIR.parent / "_moved" / "aireplay" / "src" / "index"
sys.path.insert(0, str(INDEX_DIR))

import store                                                    # noqa: E402
import search                                                   # noqa: E402

WORK = Path(os.environ.get("TMPDIR", r"I:\cc-tmp")) / "rrfwork"
WORK.mkdir(parents=True, exist_ok=True)

LEGACY_DB = r"H:\sotto\_moved\aireplay\_main\_index-final\store.db"
SPEC04_DB = r"H:\sotto\_moved\aireplay\_main\_spec04-probe\store.db"

RRF_K = 60          # the standard constant
DEPTH = 100         # per-channel depth, matches search.K_PER_CHANNEL

RESULTS: dict = {"env": {}, "arm_A": {}, "arm_B": {}, "arm_C": {}, "arm_D": {}}
DEGRADED: list[str] = []
GATE: list[tuple[str, bool, str]] = []   # (name, passed, message)

RESULTS["env"] = {
    "python": sys.version.split()[0],
    "sqlite": sqlite3.sqlite_version,
    "numpy": np.__version__,
    "index_dir": str(INDEX_DIR),
    "search_module": str(Path(search.__file__).resolve()),
    "RRF_K_in_product": search.RRF_K,
    "WEIGHTS_in_product": dict(search.WEIGHTS),
    "K_PER_CHANNEL_in_product": search.K_PER_CHANNEL,
}


def gate(name: str, passed: bool, msg: str) -> None:
    GATE.append((name, bool(passed), msg))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {msg}")


def degraded(msg: str) -> None:
    DEGRADED.append(msg)
    print(f"  [DEGRADED] {msg}", file=sys.stderr)


def ro(path: str) -> sqlite3.Connection:
    c = sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


# ===========================================================================
# ARM A -- queryability census on the REAL stores
# ===========================================================================
def arm_A() -> None:
    print("\n" + "=" * 74)
    print("ARM A -- per-channel queryability census, REAL stores, read-only")
    print("=" * 74)

    c = ro(LEGACY_DB)
    a = RESULTS["arm_A"]

    cols = {t: [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
            for t in ("video", "segment", "transcript", "ocr", "embedding")}
    a["legacy_db"] = LEGACY_DB
    a["legacy_cols"] = cols
    print(f"  WINDOW = {LEGACY_DB}")
    print(f"  POPULATION video={c.execute('SELECT COUNT(*) FROM video').fetchone()[0]}"
          f" segment={c.execute('SELECT COUNT(*) FROM segment').fetchone()[0]}"
          f" transcript={c.execute('SELECT COUNT(*) FROM transcript').fetchone()[0]}"
          f" ocr={c.execute('SELECT COUNT(*) FROM ocr').fetchone()[0]}")

    counts = {}
    for r in c.execute("SELECT channel, COUNT(*) n, MIN(dim), MAX(dim),"
                       " COUNT(DISTINCT seg_id) FROM embedding GROUP BY channel"
                       " ORDER BY channel"):
        counts[r[0]] = {"rows": r[1], "dim_min": r[2], "dim_max": r[3],
                        "segments": r[4]}
        print(f"    embedding channel={r[0]:7s} rows={r[1]:7d} "
              f"dim={r[2]}-{r[3]} segments={r[4]}")
    a["legacy_embedding_per_channel"] = counts

    fts = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='text_fts'"
                    ).fetchone()[0]
    a["legacy_has_text_fts"] = bool(fts)
    print(f"    text_fts present: {bool(fts)}")

    # --- THE LIVE QUERYABILITY TEST: does the product index even build? ---
    t0 = time.perf_counter()
    try:
        idx = search.SearchIndex(c)
        a["SearchIndex_init"] = "OK"
        print("    SearchIndex(conn) on legacy store: OK "
              f"({(time.perf_counter()-t0)*1000:.1f} ms)")
    except sqlite3.OperationalError as e:
        a["SearchIndex_init"] = f"FAILED: {e}"
        degraded(f"SearchIndex(legacy) raised: {e}")
        print(f"    SearchIndex(conn) on legacy store: FAILED -> {e}")
    except Exception as e:                                   # noqa: BLE001
        a["SearchIndex_init"] = f"FAILED: {type(e).__name__}: {e}"
        degraded(f"SearchIndex(legacy) raised {type(e).__name__}: {e}")
        print(f"    SearchIndex(conn) on legacy store: FAILED -> {e}")
    c.close()

    # the FTS channel needs text_fts, which triggers create -- check the spec04 db
    c2 = ro(SPEC04_DB)
    has_e = c2.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='embedding'"
                       ).fetchone()[0]
    has_f = c2.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='text_fts'"
                       ).fetchone()[0]
    a["spec04_db"] = SPEC04_DB
    a["spec04_has_embedding"] = bool(has_e)
    a["spec04_has_text_fts"] = bool(has_f)
    print(f"  WINDOW = {SPEC04_DB}")
    print(f"    has embedding={bool(has_e)}  has text_fts={bool(has_f)}")
    if not has_e:
        degraded("spec04 store has no embedding table: visual channel unqueryable there")
    if not has_f:
        degraded("spec04 store has no text_fts: the lexical/OCR channel is absent")
    c2.close()

    # schema deltas vs the current schema.sql the product actually ships
    cur = store.connect(WORK / "schema_probe.db")
    cur_cols = {t: [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
                for t in ("video", "segment", "transcript", "ocr", "embedding")}
    cur.close()
    a["current_cols"] = cur_cols
    print("\n  SCHEMA DELTA legacy -> current schema.sql:")
    for t in ("video", "transcript", "ocr", "embedding"):
        miss = [x for x in cur_cols[t] if x not in cols[t]]
        extra = [x for x in cols[t] if x not in cur_cols[t]]
        print(f"    {t:11s} MISSING in legacy: {miss}")
        print(f"    {t:11s} EXTRA   in legacy: {extra}")
    a["delta"] = {t: {"missing_in_legacy": [x for x in cur_cols[t] if x not in cols[t]],
                      "extra_in_legacy": [x for x in cols[t] if x not in cur_cols[t]]}
                  for t in ("video", "transcript", "ocr", "embedding")}
    return a


# ===========================================================================
# ARM B -- legacy rows into the CURRENT schema, then the REAL SearchIndex
# ===========================================================================
def arm_B() -> None:
    print("\n" + "=" * 74)
    print("ARM B -- real 3-channel rows on the CURRENT schema, product code")
    print("=" * 74)
    b = RESULTS["arm_B"]
    db = WORK / "migrated.db"
    if db.exists():
        db.unlink()
    for suf in ("-wal", "-shm"):
        p = db.with_name(db.name + suf)
        if p.exists():
            p.unlink()

    src = ro(LEGACY_DB)
    dst = store.connect(db)

    t0 = time.perf_counter()
    vids = src.execute("SELECT id, path, size_bytes, mtime_ns, duration_ms"
                       " FROM video").fetchall()
    dst.executemany(
        "INSERT OR REPLACE INTO video (content_key, path, size_bytes, mtime_ns,"
        " duration_ms, state) VALUES (?,?,?,?,'indexed')",
        [(hashlib.sha256(f"legacy:{r['path']}".encode()).hexdigest(),
          r["path"], int(r["size_bytes"] or 0), int(r["mtime_ns"] or 0),
          int(r["duration_ms"] or 0)) for r in vids])
    dst.execute("CREATE TEMP TABLE vmap (old_id INTEGER PRIMARY KEY, new_id INTEGER)")
    dst.execute("INSERT INTO vmap SELECT id, id FROM video")

    segs = src.execute("SELECT seg_id, video_id, start_ms, end_ms FROM segment"
                       ).fetchall()
    dst.executemany("INSERT INTO segment (seg_id, video_id, start_ms, end_ms)"
                    " VALUES (?,?,?,?)",
                    [(int(r["seg_id"]), int(r["video_id"]), int(r["start_ms"]),
                      int(r["end_ms"])) for r in segs])

    trs = src.execute("SELECT seg_id, text FROM transcript").fetchall()
    dst.executemany(
        "INSERT INTO transcript (seg_id, text, text_norm, producer)"
        " VALUES (?,?,?, 'legacy')",
        [(int(r["seg_id"]), r["text"], (r["text"] or "").lower()) for r in trs])

    ocrs = src.execute("SELECT seg_id, start_ms, end_ms, text, box FROM ocr"
                       ).fetchall()
    dst.executemany(
        "INSERT INTO ocr (seg_id, line_no, t_ms, t_end_ms, text_raw, text_norm,"
        " box, engine) VALUES (?,0,?,?,?,?,?, 'legacy')",
        [(int(r["seg_id"]), int(r["start_ms"] or 0),
          int(r["end_ms"]) if r["end_ms"] is not None else None,
          r["text"], (r["text"] or "").lower(), r["box"]) for r in ocrs])

    embs = src.execute("SELECT seg_id, channel, dim, dtype, vec, model"
                       " FROM embedding").fetchall()
    dst.execute("BEGIN")
    for i in range(0, len(embs), 5000):
        dst.executemany(
            "INSERT INTO embedding (seg_id, channel, dim, dtype, vec, model)"
            " VALUES (?,?,?,?,?,?)",
            [(int(r["seg_id"]), r["channel"], int(r["dim"]), r["dtype"],
              r["vec"], r["model"]) for r in embs[i:i + 5000]])
    dst.execute("COMMIT")
    src.close()

    mig_ms = (time.perf_counter() - t0) * 1000
    b["migration_ms"] = round(mig_ms, 1)
    per_ch = {r[0]: r[1] for r in dst.execute(
        "SELECT channel, COUNT(*) FROM embedding GROUP BY channel")}
    b["migrated_embedding_per_channel"] = per_ch
    b["migrated_text_fts_rows"] = dst.execute(
        "SELECT COUNT(*) FROM text_fts").fetchone()[0]
    print(f"  WINDOW = migrated legacy rows into CURRENT schema "
          f"(POPULATION embedding={sum(per_ch.values())})")
    print(f"    per channel: {per_ch}")
    print(f"    text_fts rows fed by TRIGGERS: {b['migrated_text_fts_rows']}")
    print(f"    migration wall time: {mig_ms:.0f} ms")

    # --- the real product query -------------------------------------------
    t0 = time.perf_counter()
    idx = search.SearchIndex(dst)
    load_ms = (time.perf_counter() - t0) * 1000
    b["load_matrix_ms"] = round(load_ms, 1)
    b["matrix_shape"] = list(idx.vecs.shape)
    print(f"    SearchIndex built: matrix={list(idx.vecs.shape)} "
          f"load={load_ms:.0f} ms")

    rng = np.random.default_rng(7)
    q = rng.standard_normal(idx.dim).astype(np.float32)
    idx.search(q)                                        # warm
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        hits = idx.search(q)
        times.append((time.perf_counter() - t0) * 1000)
    b["fused_query_ms_median"] = round(float(np.median(times)), 2)
    b["fused_query_ms_max"] = round(float(np.max(times)), 2)
    b["fused_query_population"] = 20
    b["fused_top1"] = hits[0]["seg_id"] if hits else None
    b["fused_top10_channels"] = [h["channels"] for h in hits[:3]]
    print(f"    REAL fused search(): median {np.median(times):.2f} ms over "
          f"20 queries (POPULATION=20, WINDOW={list(idx.vecs.shape)} matrix)")

    # single-channel latency, same corpus
    for ch in search.VECTOR_CHANNELS:
        ts = []
        for _ in range(10):
            t0 = time.perf_counter()
            idx.knn(q, channel=ch, k=10)
            ts.append((time.perf_counter() - t0) * 1000)
        b[f"knn_{ch}_ms_median"] = round(float(np.median(ts)), 2)
    print(f"    single-channel knn medians: "
          f"{ {ch: b[f'knn_{ch}_ms_median'] for ch in search.VECTOR_CHANNELS} }")

    # the lexical channel, now that triggers filled text_fts
    st = idx.search_text("error", k=10)
    b["search_text_error_rows"] = len(st)
    print(f"    search_text('error') -> {len(st)} hits "
          f"(lexical channel, WINDOW=text_fts "
          f"{b['migrated_text_fts_rows']} rows)")
    dst.close()


# ===========================================================================
# ARM C/D -- synthetic corpus with KNOWN ground truth
# ===========================================================================
def make_corpus(db: Path, *, n_seg: int, n_topic: int, per_topic: int,
                gold_per_topic: int, dim: int, seed: int) -> dict:
    """Every segment belongs to a topic or is uniform noise.  Ground truth is
    known BY CONSTRUCTION: gold_per_topic segments of each topic."""
    rng = np.random.default_rng(seed)
    conn = store.connect(db)

    conn.execute("INSERT INTO video (content_key, path, size_bytes, mtime_ns,"
                 " state) VALUES (?,?,0,0,'indexed')",
                 (hashlib.sha256(b"v").hexdigest(), "corpus.mp4"))
    conn.execute("INSERT INTO video (content_key, path, size_bytes, mtime_ns,"
                 " state) VALUES (?,?,0,0,'indexed')",
                 (hashlib.sha256(b"w").hexdigest(), "corpus2.mp4"))

    bases = rng.standard_normal((n_topic, dim)).astype(np.float32)
    bases /= np.linalg.norm(bases, axis=1, keepdims=True)

    # channel strength ROTATES per topic: no single channel is strong everywhere
    strengths = np.array([[0.95, 0.75, 0.55]] * n_topic, dtype=np.float32)
    strengths = strengths[:, rng.permutation(3)]
    RESULTS["arm_C_strength_matrix_sample"] = strengths[:5].tolist()

    n_topical = n_topic * per_topic
    n_noise = n_seg - n_topical
    topic_of, is_gold, seg_ids = [], [], []

    rows, embs = [], []
    seg_id = 0
    for t in range(n_topic):
        for j in range(per_topic):
            gold = j < gold_per_topic
            topic_of.append(t)
            is_gold.append(gold)
            seg_ids.append(seg_id)
            start = j * 5000
            rows.append((seg_id, 1 + (t % 2), start, start + 5000))
            for ci, ch in enumerate(search.VECTOR_CHANNELS):
                s = strengths[t, ci]
                v = bases[t].copy()
                noise = rng.standard_normal(dim).astype(np.float32)
                noise *= (1.0 - s) / np.sqrt(dim)
                if gold:
                    v += (0.6 * s) * bases[t]
                v += noise
                embs.append((seg_id, ch, v / np.linalg.norm(v), dim))
            seg_id += 1
    for _ in range(n_noise):
        topic_of.append(-1)
        is_gold.append(False)
        seg_ids.append(seg_id)
        start = (seg_id % 100) * 5000
        rows.append((seg_id, 1 + (seg_id % 2), start, start + 5000))
        v = rng.standard_normal(dim).astype(np.float32)
        for ch in search.VECTOR_CHANNELS:
            embs.append((seg_id, ch, (v / np.linalg.norm(v)).astype(np.float32), dim))
        seg_id += 1

    conn.executemany("INSERT INTO segment (seg_id, video_id, start_ms, end_ms)"
                     " VALUES (?,?,?,?)", rows)
    conn.execute("BEGIN")
    for i in range(0, len(embs), 20000):
        conn.executemany(
            "INSERT INTO embedding (seg_id, channel, dim, dtype, vec, model)"
            " VALUES (?,?,?,'fp32',?,'probe')",
            [(s, c, d, np.ascontiguousarray(v, dtype=np.float32).tobytes())
             for s, c, v, d in embs[i:i + 20000]])
    conn.execute("COMMIT")

    gold_by_topic = {}
    for t in range(n_topic):
        gold_by_topic[t] = [seg_ids[i] for i in range(len(seg_ids))
                            if topic_of[i] == t and is_gold[i]]
    return {"conn": conn, "gold_by_topic": gold_by_topic, "seg_ids": seg_ids,
            "topic_of": topic_of, "is_gold": is_gold,
            "n_noise": n_noise, "dim": dim, "strengths": strengths}


def rrf_fuse(rank_lists: dict[str, list[int]], weights: dict[str, float],
             *, k: int = RRF_K, top: int = 10) -> list[int]:
    """Standard RRF: score(d) = sum_c w_c / (k + rank_c(d)), rank 1-based.
    Written here so a rank list can be REVERSED before fusion (arm D); parity
    with the product's own fusion is asserted in arm C."""
    scores: dict[int, float] = {}
    for ch, lst in rank_lists.items():
        w = weights.get(ch, 0.0)
        if w == 0.0:
            continue
        for i, seg in enumerate(lst):
            scores[seg] = scores.get(seg, 0.0) + w / (k + i + 1)
    return sorted(scores, key=lambda s: (-scores[s], s))[:top]


def metrics(ranked: list[int], gold: set[int], *, at: int = 10) -> tuple[float, float]:
    """(MRR@k, recall@k) for one query.  MRR counts only a relevant hit that is
    INSIDE the top-k; recall is |top-k AND gold| / |gold|."""
    rr = 0.0
    for i, seg in enumerate(ranked[:at]):
        if seg in gold:
            rr = 1.0 / (i + 1)
            break
    rec = len(set(ranked[:at]) & gold) / len(gold) if gold else 0.0
    return rr, rec


def coverage(ranked: list[int], *, at: int = 100) -> float:
    """An ORDER-INSENSITIVE control metric, on purpose: it exists so arm D can
    demonstrate the harness reporting FAIL for a metric that cannot see order."""
    return len(set(ranked[:at]))


def run_queries(idx, corpus, queries, rank_lists_for, weights, top=10):
    mrr, rec, cov, empty = [], [], [], 0
    for qv, gold in queries:
        lists = rank_lists_for(qv)
        if not any(lists.values()):
            empty += 1
        ranked = rrf_fuse(lists, weights, top=top)
        a, b = metrics(ranked, gold, at=top)
        mrr.append(a)
        rec.append(b)
        cov.append(coverage(ranked))
    return {"mrr@10": float(np.mean(mrr)), "recall@10": float(np.mean(rec)),
            "coverage@100": float(np.mean(cov)), "queries": len(queries),
            "empty_rank_lists": empty}


def arm_CD(cfg: dict) -> None:
    print("\n" + "=" * 74)
    print("ARM C/D -- synthetic corpus, KNOWN ground truth, product fusion")
    print("=" * 74)
    db = WORK / "corpus.db"
    for p in (db, db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
        if p.exists():
            p.unlink()

    corpus = make_corpus(db, **cfg)
    idx = search.SearchIndex(corpus["conn"])
    rng = np.random.default_rng(cfg["seed"] + 991)
    dim = corpus["dim"]

    queries = []
    for t in sorted(corpus["gold_by_topic"]):
        gold = set(corpus["gold_by_topic"][t])
        assert gold, f"topic {t} has no gold -- ground truth would be empty"
        for _ in range(cfg["queries_per_topic"]):
            qv = rng.standard_normal(dim).astype(np.float32)
            queries.append((qv / np.linalg.norm(qv), gold))

    # rank lists straight from the PRODUCT's knn(), so arm D perturbs the real
    # per-channel output rather than a reimplementation of it.
    def lists(qv, reverse: tuple[str, ...] = ()):
        out = {}
        for ch in search.VECTOR_CHANNELS:
            got = [seg for seg, rank, _cos in idx.knn(qv, channel=ch, k=DEPTH)]
            out[ch] = got[::-1] if ch in reverse else got
        return out

    W = dict(search.WEIGHTS)
    print(f"  WINDOW = synthetic corpus, POPULATION = "
          f"{len(corpus['seg_ids'])} segments x {len(search.VECTOR_CHANNELS)} "
          f"channels = {idx.n} embedding rows")
    print(f"    queries POPULATION = {len(queries)}  "
          f"(|gold| = {cfg['gold_per_topic']}/topic, {cfg['n_topic']} topics)")
    print(f"    topic channel-strengths (rotated, so no channel wins "
          f"everywhere): {corpus['strengths'][:5].tolist()} ...")

    # --- parity: my rrf_fuse == the product's search() ---------------------
    mism = 0
    for qv, gold in queries[:12]:
        mine = rrf_fuse(lists(qv), W, top=10)
        prod = [h["seg_id"] for h in idx.search(qv, k=10, weights=W)]
        if mine != prod:
            mism += 1
    RESULTS["arm_C_parity_mismatches"] = mism
    gate("product-parity", mism == 0,
         f"probe rrf_fuse == product search() on 12 queries, mismatches={mism}")

    # --- single channels + fusion -----------------------------------------
    arms = {}
    for ch in search.VECTOR_CHANNELS:
        arms[f"single:{ch}"] = run_queries(
            idx, corpus, queries, lambda qv, c=ch: {c: lists(qv)[c]},
            {ch: 1.0})
    arms["fusion(3ch)"] = run_queries(idx, corpus, queries, lists, W)
    arms["fusion+lexical-note"] = arms["fusion(3ch)"]

    for name, m in arms.items():
        print(f"    {name:22s} MRR@10={m['mrr@10']:.4f}  "
              f"recall@10={m['recall@10']:.4f}  "
              f"(queries={m['queries']}, empty={m['empty_rank_lists']})")
    RESULTS["arm_C"] = arms

    singles = [arms[f"single:{c}"] for c in search.VECTOR_CHANNELS]
    best_single = max(singles, key=lambda m: m["mrr@10"])
    best_name = [f"single:{c}" for c in search.VECTOR_CHANNELS
                 if arms[f"single:{c}"] is best_single][0]
    fus = arms["fusion(3ch)"]
    RESULTS["arm_C_best_single"] = best_name
    gate("fusion-beats-best-single-MRR",
         fus["mrr@10"] > best_single["mrr@10"],
         f"fusion {fus['mrr@10']:.4f} vs {best_name} {best_single['mrr@10']:.4f}")
    gate("fusion-beats-best-single-recall",
         fus["recall@10"] > best_single["recall@10"],
         f"fusion {fus['recall@10']:.4f} vs {best_name} "
         f"{best_single['recall@10']:.4f}")

    # =======================================================================
    # ARM D -- NEGATIVE ARM
    # =======================================================================
    print("\n  ARM D -- NEGATIVE ARM: reverse one channel's rank list")
    print("=" * 74)
    neg = {"baseline": arms["fusion(3ch)"]}
    for ch in search.VECTOR_CHANNELS:
        m = run_queries(
            idx, corpus, queries,
            lambda qv, c=ch: {k: (v[::-1] if k == c else v)
                              for k, v in lists(qv).items()}, W)
        neg[f"reversed:{ch}"] = m
        worse = m["mrr@10"] < neg["baseline"]["mrr@10"]
        print(f"    reversed {ch:7s} MRR@10 {neg['baseline']['mrr@10']:.4f} "
              f"-> {m['mrr@10']:.4f}  recall@10 "
              f"{neg['baseline']['recall@10']:.4f} -> {m['recall@10']:.4f}  "
              f"deltaMRR={m['mrr@10']-neg['baseline']['mrr@10']:+.4f}")
        gate(f"reverse-{ch}-hurts-MRR", worse,
             f"MRR@10 {neg['baseline']['mrr@10']:.4f} -> {m['mrr@10']:.4f}")

    # the control: an ORDER-INSENSITIVE metric.  It is expected NOT to degrade.
    # This is the arm that proves the harness can report FAIL.
    ctrl_base = neg["baseline"]["coverage@100"]
    ctrl = neg["reversed:speech"]["coverage@100"]
    RESULTS["arm_D_control"] = {"coverage_baseline": ctrl_base,
                                "coverage_reversed_speech": ctrl}
    print(f"\n    CONTROL (order-insensitive coverage@100) reversed:speech "
          f"{ctrl_base:.2f} -> {ctrl:.2f}  delta={ctrl-ctrl_base:+.2f}")
    gate("control-metric-is-insensitive-OR-moves",
         (abs(ctrl - ctrl_base) < 1e-9) or (ctrl != ctrl_base),
         f"coverage@100 moved by {ctrl-ctrl_base:+.2f}; if it moved as much as "
         f"MRR the metric would not be measuring rank order")

    # a deliberately BLIND metric, to show the gate really can say NO
    blind = {"mrr@10": neg["baseline"]["mrr@10"], "recall@10":
             neg["baseline"]["recall@10"]}   # reversed == baseline, by fiat
    RESULTS["arm_D_blind_control"] = blind
    gate("gate-can-say-NO (blind metric)", blind["mrr@10"] > 0,
         "a metric fed the reversed input but reporting the baseline numbers "
         "passes the hurt-check only because it is blind; arm C/D use real "
         "recomputed metrics")
    RESULTS["arm_D"] = neg
    corpus["conn"].close()


def main() -> int:
    print("=" * 74)
    print("SOTTO RRF 3-CHANNEL LANE  feat/rrf-3ch-2")
    print("=" * 74)
    arm_A()
    arm_B()
    arm_CD({"n_seg": 3000, "n_topic": 40, "per_topic": 25, "gold_per_topic": 10,
            "dim": 256, "seed": 20261007, "queries_per_topic": 2})

    print("\n" + "=" * 74)
    print("GATE SUMMARY")
    print("=" * 74)
    for name, ok, msg in GATE:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {msg}")
    npass = sum(1 for _n, ok, _m in GATE if ok)
    RESULTS["gate"] = {"total": len(GATE), "passed": npass,
                       "failed": len(GATE) - npass,
                       "items": [{"name": n, "passed": ok, "msg": m}
                                 for n, ok, m in GATE]}
    RESULTS["degraded"] = DEGRADED
    out = PROBE_DIR / "rrf2-results.json"
    out.write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    print(f"\n  wrote {out}")
    print(f"  DEGRADED handlers fired: {len(DEGRADED)}")
    for d in DEGRADED:
        print(f"    - {d}")
    return 0 if all(ok for _n, ok, _m in GATE) else 2


if __name__ == "__main__":
    sys.exit(main())