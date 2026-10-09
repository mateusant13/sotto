"""Lane RRF-3CH-1: the FIRST executed measurement of 3-channel Reciprocal Rank Fusion.

POPULATION OF EXECUTED RRF QUERIES BEFORE THIS PROBE: 0.

WHAT THIS MEASURES
------------------
src/index/search.py has shipped an RRF implementation since the lane landed
(k=60, weights speech 1.0 / ocr 1.0 / visual 0.7) but NO probe had ever run it.
This probe is the first thing to call `SearchIndex.search()` with a POPULATION
that has ground truth attached, and the first thing to compare the fused score
against each of its OWN THREE COMPONENTS measured alone.

Per-channel queryability is established FIRST, by counting rows and calling
`SearchIndex.knn()` per channel -- a channel with zero embedding rows cannot be
a fusion input, and the count is printed with POPULATION + WINDOW.

THE CORPUS IS SYNTHETIC AND BUILT HERE
---------------------------------------
12 topics x 30 relevant segments, plus per-topic distractors, plus a background
pool.  Every segment's true channel membership is known because this file
generated it.  No real media, no owner library, no claim about real footage.

Three query FAMILIES, because a single number would hide the mechanism:
  all3     every relevant segment carries ALL THREE channel vectors.  Fusion
           should win: consensus across channels beats one-channel similarity.
  disjoint relevant segments are partitioned across the three channels, one
           channel each.  A single channel can only see its own third.
  ocr_only relevant segments carry the ocr vector only.  Fusion CANNOT
           retrieve what no channel holds -- reported honestly, not hidden.

NEGATIVE ARM (the gate must be able to say NO)
-----------------------------------------------
Same fusion, but one channel's rank list is REVERSED before fusing.  If
reversing an input does not make the metric WORSE, the metric is insensitive
and therefore meaningless -- that is the finding, and RESULT is FAIL.

PARITY CHECK: the probe's own `rrf_fuse` is asserted to reproduce
`SearchIndex.search()` exactly, top-10 seg_ids identical.  Everything below
(fusion, single channels, reversed arms) runs through that one scorer, so a
parity failure invalidates the whole run rather than silently passing.

THREADS: exactly <=2, env set BEFORE numpy is imported (store.py's own rule).

Usage:  python rrf_probe.py [n_queries_per_family] [n_background] [n_distractors]
EXIT:  0 only if parity holds AND fusion beats its best single channel AND the
       reversed arm measures strictly WORSE.  Any of those failing -> rc 1.
"""
import os

# --- thread budget FIRST, before numpy exists in this process ---------------
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import pathlib  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent                 # _main/rrf_probe.py -> the worktree root

# The index code is NOT at <root>/src/index in this tree -- it was moved to
# _moved/aireplay/src/index.  Resolve it by finding the real search.py rather
# than hard-coding the brief's path, so the probe runs where the code lives.
_index = None
for _cand in (ROOT / "src" / "index", ROOT / "_moved" / "aireplay" / "src" / "index"):
    if (_cand / "search.py").exists() and (_cand / "store.py").exists():
        _index = _cand
        break
if _index is None:
    print("FAIL: could not locate src/index/{search,store}.py under %s" % ROOT)
    sys.exit(2)
sys.path.insert(0, str(_index))

import store  # noqa: E402
import search  # noqa: E402

store.set_thread_budget(2)
import numpy as np  # noqa: E402

DIM = 256
SEED = 20261007
MODEL = "rrf-probe-labelled-v1"
TOPK = 10                 # WINDOW for the reported metrics
K_PER_CHANNEL = 100       # WINDOW each channel contributes, == search.K_PER_CHANNEL

N_TOPICS = 12
N_RELEVANT = 30           # relevant segments per topic
FAMILIES = ("all3", "disjoint", "ocr_only")

# similarity knobs: a distractor is a ONE-channel zoomie that out-scores every
# true match inside its own channel.  A true all3 match is moderate in all
# three.  This is the mechanism RRF is supposed to exploit.
DIST_SIM = 0.90           # distractor vs topic centroid, in its one channel
TRUE_SIM = 0.70           # true match vs topic centroid, per held channel
QUERY_SIM = 0.75          # query vs topic centroid


# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------
def _unit(rng, dim=DIM):
    return rng.standard_normal(dim).astype(np.float32)


def _norm(a):
    return a / max(float(np.linalg.norm(a)), 1e-12)


def build_corpus(conn, *, n_background, n_distractors):
    """Returns (seg_ids, truth) where truth[seg_id] = (topic, frozenset(channels))."""
    rng = np.random.default_rng(SEED)
    tmp = HERE.parent / ".rrf-probe-media"          # never a real media path
    tmp.mkdir(parents=True, exist_ok=True)
    videos = []
    for i in range(3):
        videos.append(store.upsert_video(
            conn,
            content_key=rng.bytes(32).hex(),
            path=str(tmp / f"synthetic_{i}.mp4"),
            size_bytes=1_000_000 + i, mtime_ns=1_760_000_000_000_000_000,
            duration_ms=600_000, codec="synthetic", w=1920, h=1080, fps=25.0))

    truth: dict[int, tuple[int, frozenset]] = {}
    embedding_rows: list[tuple[int, str, np.ndarray]] = []
    seg_ids: list[int] = []
    seg_no = 0

    def new_seg(video_i, topic, channels, start_ms):
        nonlocal seg_no
        sid = store.upsert_segment(
            conn, video_id=videos[video_i], start_ms=start_ms, end_ms=start_ms + 5000,
            n_visual=1 if "visual" in channels else 0,
            n_speech=1 if "speech" in channels else 0,
            n_ocr=1 if "ocr" in channels else 0, state="promoted")
        truth[sid] = (topic, frozenset(channels))
        seg_ids.append(sid)
        seg_no += 1
        return sid

    for t in range(N_TOPICS):
        family = FAMILIES[t % len(FAMILIES)]
        centroid = _unit(rng)

        # ---- the relevant set, membership is the family's whole point -----
        for j in range(N_RELEVANT):
            if family == "all3":
                chans = {"speech", "ocr", "visual"}
            elif family == "ocr_only":
                chans = {"ocr"}
            else:                                   # disjoint: one channel each
                chans = {("speech", "ocr", "visual")[j % 3]}
            sid = new_seg(j % 3, t, chans, seg_no * 5000)
            for c in chans:
                noise = _unit(rng)
                embedding_rows.append(
                    (sid, c, _norm(TRUE_SIM * centroid + np.sqrt(1 - TRUE_SIM ** 2) * noise)))

        # ---- distractors: high similarity in exactly ONE channel ----------
        for j in range(n_distractors):
            c = ("speech", "ocr", "visual")[j % 3]
            noise = _unit(rng)
            sid = new_seg(j % 3, -1, {c}, seg_no * 5000)   # topic -1 = not relevant
            embedding_rows.append(
                (sid, c, _norm(DIST_SIM * centroid + np.sqrt(1 - DIST_SIM ** 2) * noise)))

    # ---- background pool: uniform noise, relevant to nothing --------------
    for j in range(n_background):
        noise = _unit(rng)
        c = ("speech", "ocr", "visual")[j % 3]
        sid = new_seg(j % 3, -1, {c}, seg_no * 5000)
        embedding_rows.append((sid, c, _norm(noise)))

    store.upsert_embeddings(conn, embedding_rows, model=MODEL, dtype="fp32", dim=DIM)
    fam_topics = {f: [t for t in range(N_TOPICS) if FAMILIES[t % len(FAMILIES)] == f]
                  for f in FAMILIES}
    assert all(isinstance(x, int) for v in fam_topics.values() for x in v), \
        "fam_topics must hold TOPIC IDS, not family names"
    return seg_ids, truth, fam_topics


def make_queries(fam_topics, per_family, rng):
    """query = (topic_id, vector).  Iterates TOPIC IDS, never the family names."""
    qs = []
    for t in sorted(x for v in fam_topics.values() for x in v):
        centroid = _unit(rng, DIM)
        for _ in range(per_family):
            q = _norm(QUERY_SIM * centroid + np.sqrt(1 - QUERY_SIM ** 2) * _unit(rng))
            qs.append((t, q))
    return qs


# ---------------------------------------------------------------------------
# RRF scorer -- the standard formula, k=60, one term per channel
# ---------------------------------------------------------------------------
def rrf_fuse(rank_lists: dict[str, list[tuple[int, int, float]]],
             weights: dict[str, float]) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for channel, wl in rank_lists.items():
        w = weights.get(channel, 0.0)
        if not w:
            continue
        for seg_id, rank, _cos in wl:
            scores[seg_id] = scores.get(seg_id, 0.0) + w / (search.RRF_K + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def invert_ranks(wl: list[tuple[int, int, float]]) -> list[tuple[int, int, float]]:
    """Genuinely INVERT one channel's ranking.

    Reversing the python list alone is a NO-OP and must not be mistaken for a
    broken input: each tuple carries its own `rank`, so reordering the list
    leaves every (seg_id, score) contribution identical.  This remaps rank
    r -> n+1-r, which is what "reversed" has to mean for RRF.
    """
    n = len(wl)
    return [(seg_id, n - rank + 1, cos) for seg_id, rank, cos in reversed(wl)]


def metrics(ranked, relevant: set[int], k=TOPK):
    """ranked: [(seg_id, score), ...] best first.  Returns (mrr, recall, rank1)."""
    top = [s for s, _ in ranked[:k]]
    rrs = [1.0 / (i + 1) for i, s in enumerate(top) if s in relevant]
    rec = len([s for s in top if s in relevant]) / len(relevant) if relevant else 0.0
    return (rrs[0] if rrs else 0.0), rec, (top[0] in relevant if top else False)


def mean_pair(rows):
    if not rows:
        return 0.0, 0.0
    return (sum(r[0] for r in rows) / len(rows),
            sum(r[1] for r in rows) / len(rows))


# ---------------------------------------------------------------------------
def main(argv):
    per_family = int(argv[1]) if len(argv) > 1 else 20
    n_background = int(argv[2]) if len(argv) > 2 else 600
    n_distractors = int(argv[3]) if len(argv) > 3 else 120
    if per_family <= 0:
        print("n_queries_per_family must be positive")
        return 2

    print("index dir       : %s" % _index)
    print("thread budget   : 2 (env set pre-numpy)")
    print("RRF_K           : %d   K_PER_CHANNEL: %d   TOPK(window): %d"
          % (search.RRF_K, K_PER_CHANNEL, TOPK))
    print("WEIGHTS (prod)  : %s" % search.WEIGHTS)

    rng = np.random.default_rng(SEED)
    tmpdb = pathlib.Path(tempfile.mkdtemp(prefix="rrf-probe-")) / "labelled.sqlite"
    conn = store.connect(tmpdb)
    seg_ids, truth, fam_topics = build_corpus(
        conn, n_background=n_background, n_distractors=n_distractors)

    # ================= 1. PER-CHANNEL QUERYABILITY, WITH EVIDENCE ==========
    idx = search.SearchIndex(conn)
    print("\n--- POPULATION (embedding rows, this probe's corpus) ---")
    total_rows = int(conn.execute("SELECT COUNT(*) FROM embedding").fetchone()[0])
    print("embedding rows  : %d   segments: %d   dim: %d" % (total_rows, idx.n, idx.dim))
    queryable = {}
    for c in search.VECTOR_CHANNELS:
        rows = int(conn.execute(
            "SELECT COUNT(*) FROM embedding WHERE channel = ?", (c,)).fetchone()[0])
        mask_n = int(idx._masks[c].sum())
        # EVIDENCE: actually call knn on that channel and count returned hits.
        rng_q = np.random.default_rng(SEED + 7)
        probe_vec = idx.vecs[int(rng_q.integers(0, idx.n))]
        hits = idx.knn(probe_vec, channel=c, k=K_PER_CHANNEL)
        queryable[c] = {"rows": rows, "mask_n": mask_n, "knn_hits": len(hits)}
        print("  channel %-7s : rows=%-6d mask=%-6d knn(hits)=%-5d  QUERYABLE=%s"
              % (c, rows, mask_n, len(hits), "YES" if len(hits) else "NO"))

    qlist = make_queries(fam_topics, per_family, rng)
    n_queries = len(qlist)
    n_topics_per_family = {f: len(fam_topics[f]) for f in FAMILIES}
    print("\nqueries         : %d  (%d topics x %d queries per topic, %d families)"
          % (n_queries, len(fam_topics[fam_topics and FAMILIES[0]] or []),
             per_family, len(FAMILIES)))
    print("  topics/family : %s" % n_topics_per_family)
    print("query WINDOW    : per-channel k=%d, reported top-%d" % (K_PER_CHANNEL, TOPK))

    # --- per-channel recall of ITS OWN ground truth, before fusing anything --
    by_chan: dict[str, list] = {c: [] for c in search.VECTOR_CHANNELS}
    rev_by_chan: dict[str, list] = {c: [] for c in search.VECTOR_CHANNELS}
    fused_rows: list = []
    all_channels_rows: list = []
    prod_hits_rows: list = []
    order: list[str] = []          # family of each result row, in append order
    parity_ok = True
    parity_detail = ""

    for topic, q in qlist:
        family = FAMILIES[topic % len(FAMILIES)]
        relevant = {s for s, (t, _c) in truth.items() if t == topic}
        if not relevant:
            continue
        lists = {c: idx.knn(q, channel=c, k=K_PER_CHANNEL) for c in search.VECTOR_CHANNELS}

        for c in search.VECTOR_CHANNELS:
            single = [(s, 0.0) for s, _r, _c2 in lists[c]]
            by_chan[c].append(metrics(single, relevant))
            # NEGATIVE ARM: full 3-channel fusion, but this channel's list is
            # reversed.  Everything else is untouched, so any change in the
            # metric is attributable to the reversed input alone.
            broken = dict(lists)
            broken[c] = invert_ranks(lists[c])
            rev_by_chan[c].append(
                metrics(rrf_fuse(broken, dict(search.WEIGHTS)), relevant))

        fused_rows.append(metrics(rrf_fuse(lists, dict(search.WEIGHTS)), relevant))
        all_channels_rows.append(metrics(rrf_fuse(lists, {c: 1.0 for c in lists}), relevant))
        order.append(family)

        # parity against the shipped product path
        prod = idx.search(q, k=TOPK)
        prod_hits_rows.append(metrics([(h["seg_id"], h["score"]) for h in prod], relevant))
        mine = rrf_fuse(lists, dict(search.WEIGHTS))[:TOPK]
        if [s for s, _ in mine] != [h["seg_id"] for h in prod]:
            parity_ok = False
            parity_detail = (f"topic {topic}: probe={[s for s,_ in mine][:3]} "
                             f"product={[h['seg_id'] for h in prod][:3]}")

    # ================= 2. RESULTS ==========================================
    def line(name, rows):
        m, r = mean_pair(rows)
        print("  %-34s MRR@%d=%.4f  recall@%d=%.4f"
              % (name, TOPK, m, TOPK, r))
        return m, r

    print("\n=== RESULTS  POPULATION=%d queries  WINDOW=top-%d  corpus=%d segments/%" 
          "d embedding rows ===" % (n_queries, TOPK, idx.n, total_rows))
    print("\n-- single channels alone (their own top-k list, nothing fused) --")
    single = {}
    for c in search.VECTOR_CHANNELS:
        single[c] = line(f"{c} alone", by_chan[c])
    print("\n-- fusion --")
    fus_m, fus_r = line("RRF fusion (prod weights)", fused_rows)
    uni_m, uni_r = line("RRF fusion (equal weights)", all_channels_rows)
    pm, pr = line("SearchIndex.search() [shipped]", prod_hits_rows)

    # per-family detail -- a single pooled number hides the mechanism
    print("\n-- per family (same metrics, split by query family) --")
    buckets = {f: {"fusion": [], "by_chan": {c: [] for c in search.VECTOR_CHANNELS}}
              for f in FAMILIES}
    for pos, fam in enumerate(order):
        buckets[fam]["fusion"].append(fused_rows[pos])
        for c in search.VECTOR_CHANNELS:
            buckets[fam]["by_chan"][c].append(by_chan[c][pos])
    for f in FAMILIES:
        # best single channel = the one with the best FAMILY MEAN, chosen once.
        # (Picking a per-query argmax would hand the baseline an oracle.)
        bn = max(search.VECTOR_CHANNELS,
                 key=lambda c: mean_pair(buckets[f]["by_chan"][c])[0])
        print("  [%s] n=%d" % (f, len(buckets[f]["fusion"])))
        line("    fusion", buckets[f]["fusion"])
        line("    best single (%s)" % bn, buckets[f]["by_chan"][bn])
        for c in search.VECTOR_CHANNELS:
            if c != bn:
                line("      %s alone" % c, buckets[f]["by_chan"][c])

    # ================= 3. NEGATIVE ARM: reversed channel ===================
    print("\n=== NEGATIVE ARM: one channel's rank list REVERSED before fusion ===")
    clean = line("fusion (clean)", fused_rows)
    rev_results = {}
    for c in search.VECTOR_CHANNELS:
        rev_results[c] = line("fusion, %s reversed" % c, rev_by_chan[c])

    # ================= 4. VERDICT ==========================================
    print("\n=== GATE ===")
    ok = True
    if not parity_ok:
        print("FAIL: parity -- probe rrf_fuse != SearchIndex.search() (%s)" % parity_detail)
        ok = False
    else:
        print("PASS: parity -- probe rrf_fuse reproduces SearchIndex.search() "
              "top-%d exactly on all %d queries" % (TOPK, n_queries))

    best_name = max(search.VECTOR_CHANNELS, key=lambda c: single[c][0])
    best_m, best_r = single[best_name]
    print("best single     : %s  MRR@%d=%.4f recall@%d=%.4f"
          % (best_name, best_m * 0 + TOPK, best_m, TOPK, best_r))
    if not (fus_m > best_m and fus_r >= best_r):
        print("FAIL: fusion did NOT beat its best single channel "
              "(MRR %.4f vs %.4f, recall %.4f vs %.4f)" % (fus_m, best_m, fus_r, best_r))
        ok = False
    else:
        print("PASS: fusion beats best single channel %s "
              "(MRR %.4f > %.4f, recall %.4f >= %.4f)"
              % (best_name, fus_m, best_m, fus_r, best_r))

    worse = [c for c in search.VECTOR_CHANNELS if rev_results[c][0] < clean[0]]
    if not worse:
        print("FAIL: metric INSENSITIVE -- reversing any channel did not make MRR@%d "
              "worse; this metric cannot detect a broken input" % TOPK)
        ok = False
    else:
        for c in search.VECTOR_CHANNELS:
            d = rev_results[c][0] - clean[0]
            print("  reversed %-7s : MRR@%d %.4f (delta %+.4f) %s"
                  % (c, TOPK, rev_results[c][0], d,
                     "WORSE (expected)" if d < 0 else "NOT WORSE -- INSENSITIVE"))

    print("\nVERDICT-MRR@%d  fusion=%.4f  %s=%.4f  fusion_minus_best=%+.4f"
          % (TOPK, fus_m, best_name, best_m, fus_m - best_m))
    print("VERDICT-recall@%d fusion=%.4f %s=%.4f fusion_minus_best=%+.4f"
          % (TOPK, fus_r, best_name, best_r, fus_r - best_r))
    print("POPULATION: %d executed RRF queries over %d segments / %d embedding rows "
          "(%s); WINDOW top-%d, per-channel k=%d"
          % (n_queries, idx.n, total_rows,
             " ".join("%s=%d" % (c, queryable[c]["rows"])
                      for c in search.VECTOR_CHANNELS),
             TOPK, K_PER_CHANNEL))

    conn.close()
    print("\nRESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))