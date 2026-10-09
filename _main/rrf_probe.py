"""RRF v3 probe -- does Reciprocal Rank Fusion beat its own channels, and can
the gate say NO?

SCOPE / HONESTY NOTE, read this before the numbers:
  * The PRODUCT has POPULATION = 0 executable RRF queries.  Measured: there is
    no .db/.sqlite/.sqlite3 file anywhere in this worktree (see the receipt),
    so `search.SearchIndex` has never been constructed against a real corpus.
  * Every number below comes from a SYNTHETIC corpus this probe generates,
    with ground-truth channel membership known by construction.  It measures
    the ALGORITHM, not the product.  It does NOT claim the product works.
  * This probe does NOT modify search.py.  It imports it and compares.

WHAT IS MEASURED
  1. per-channel queryability of the REAL search.SearchIndex (3 vector
     channels + the FTS5 lexical list), each with a COUNT.
  2. MRR@10 and recall@10 for FUSION and for EACH SINGLE CHANNEL ALONE.
  3. NEGATIVE ARM: one channel's rank list deliberately REVERSED.  The gate
     exits 1 if the metric does not get WORSE -- an insensitive metric is a
     meaningless metric and that IS the finding.
  4. PARITY: my probe's RRF vs the product's SearchIndex.search().  If these
     disagree, the numbers above describe MY code, not the product's.

Run: py -3 _main/rrf_probe.py [--topics 40] [--segs 1200] [--seed 20261007]
Exit: 0 = fusion beat every single channel AND the negative arm degraded.
      1 = the gate said NO (see the FAIL line).
"""

from __future__ import annotations

import os

# BEFORE numpy.  The 2-thread lane budget is a measurement constraint.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import argparse
import hashlib
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
INDEX_DIR = REPO / "_moved" / "aireplay" / "src" / "index"
sys.path.insert(0, str(INDEX_DIR))
import search          # noqa: E402  -- the PRODUCT's search, unmodified
import store           # noqa: E402

RRF_K = 60                # standard constant, same as search.RRF_K
K_PER_CHANNEL = 100       # same as search.K_PER_CHANNEL
DIM = 256
WEIGHTS = {"speech": 1.0, "ocr": 1.0, "visual": 0.7}   # search.WEIGHTS
SEG_MS = 5000
CHANNELS = ("speech", "ocr", "visual")

# Per-channel presence rate.  visual ~ always (a frame always exists), speech
# most windows, OCR sparse.  These are the MEASURED-MIX ASSUMPTIONS of doc 07
# sec 6, restated as a synthetic corpus.
PRESENCE = {"speech": 0.60, "ocr": 0.16, "visual": 0.92}
# Per-channel embedding noise.  DELIBERATELY EQUAL: if one channel were
# quieter it would win alone and fusion could not beat it for the right reason.
SIGMA = {"speech": 0.90, "ocr": 0.90, "visual": 0.90}
QUERY_NOISE = 0.25         # a query encodes cleaner than a document


# ---------------------------------------------------------------------------
# corpus generation -- ground truth known by construction
# ---------------------------------------------------------------------------

def build_corpus(n_topics: int, n_segs: int, seed: int):
    """Returns (conn, truth) where truth[seg_id] = topic index."""
    rng = np.random.default_rng(seed)

    tmp = Path(tempfile.mkdtemp(prefix="rrf3-", dir=os.environ.get("TMPDIR") or None))
    conn = store.connect(tmp / "probe.db")   # applies the PRODUCT schema.sql

    centers = rng.normal(size=(n_topics, DIM)).astype(np.float32)
    centers /= np.linalg.norm(centers, axis=1, keepdims=True)

    truth: dict[int, int] = {}
    membership: dict[str, set] = {c: set() for c in PRESENCE}
    rows: list[tuple] = []

    n_videos = max(1, n_segs // 20)
    for v in range(n_videos):
        ck = hashlib.sha256(f"synthetic/video/{v}".encode()).hexdigest()
        vid = store.upsert_video(conn, content_key=ck, path=f"synthetic/clip_{v:04d}.mp4",
                                 size_bytes=1024 * (v + 1), mtime_ns=1_700_000_000_000_000_000 + v,
                                 duration_ms=600_000, w=1920, h=1080, fps=30.0,
                                 state="indexed")

        for s in range(20):
            if len(truth) >= n_segs:
                break
            start = s * SEG_MS
            seg_id = store.upsert_segment(conn, video_id=vid, start_ms=start,
                                          end_ms=start + SEG_MS, state="promoted")
            topic = int(rng.integers(0, n_topics))
            truth[seg_id] = topic

            present = {c for c in PRESENCE if rng.random() < PRESENCE[c]}
            if not present:
                present = {"visual"}
            for ch in present:
                membership[ch].add(seg_id)
                noise = rng.normal(size=DIM).astype(np.float32)
                vec = centers[topic] + SIGMA[ch] * noise
                rows.append((seg_id, ch, vec.astype(np.float32)))

            store.upsert_transcript(conn, seg_id=seg_id,
                                    text=f"topic {topic} janela {s}",
                                    text_norm=f"topic {topic} janela {s}")
            store.upsert_ocr_lines(conn, seg_id, [
                {"line_no": 0, "t_ms": 0, "text_raw": f"ERRO 0x8007{v:04d}: topico {topic}",
                 "text_norm": f"erro 0x8007{v:04d} topico {topic}", "conf": 0.9}])

    store.upsert_embeddings(conn, rows, model="synthetic-probe",
                            model_sha256="0" * 64, dtype="fp16", dim=DIM)
    conn.commit()
    return conn, truth, membership, centers, rng, tmp


def query_vectors(n_topics: int, centers: np.ndarray, rng, seed: int):
    r2 = np.random.default_rng(seed + 1)
    out = {}
    for t in range(n_topics):
        noise = r2.normal(size=DIM).astype(np.float32)
        v = centers[t] + QUERY_NOISE * noise
        out[t] = (v / np.linalg.norm(v)).astype(np.float32)
    return out


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def mrr_at_k(ranked: list[int], relevant: set, k: int) -> float:
    for i, seg in enumerate(ranked[:k], start=1):
        if seg in relevant:
            return 1.0 / i
    return 0.0


def recall_at_k(ranked: list[int], relevant: set, k: int) -> float:
    if not relevant:
        return 0.0
    return len([s for s in ranked[:k] if s in relevant]) / len(relevant)


def rrf(rank_lists: dict[str, list], weights: dict, *, reverse: str | None = None) -> list[int]:
    """Standard RRF, k=60.  `reverse` names ONE channel whose ordered rank list
    is flipped end-for-end -- the negative arm."""
    scores: dict[int, float] = {}
    for ch, ordered in rank_lists.items():
        seq = list(ordered)
        if ch == reverse:
            seq = seq[::-1]
        w = weights.get(ch, 1.0)
        for rank, seg in enumerate(seq, start=1):
            scores[seg] = scores.get(seg, 0.0) + w / (RRF_K + rank)
    return sorted(scores, key=lambda s: (-scores[s], s))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", type=int, default=40)
    ap.add_argument("--segs", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=20261007)
    args = ap.parse_args()

    t0 = time.perf_counter()
    conn, truth, membership, centers, _rng, tmp = build_corpus(
        args.topics, args.segs, args.seed)
    qvecs = query_vectors(args.topics, centers, _rng, args.seed)
    build_ms = (time.perf_counter() - t0) * 1000

    idx = search.SearchIndex(conn)
    relevant = {t: {s for s, tp in truth.items() if tp == t} for t in range(args.topics)}

    print(f"# RRF v3 probe   seed={args.seed}  topics={args.topics}  segments={len(truth)}")
    print(f"# corpus build {build_ms:.0f} ms   vectors loaded n={idx.n} dim={idx.dim}")
    print(f"# QUERY POPULATION = {args.topics} queries (one per topic), "
          f"WINDOW = whole synthetic corpus, no time filter")

    # -- 1. per-channel queryability of the PRODUCT SearchIndex --------------
    print("\n## 1. per-channel queryability (REAL search.SearchIndex)")
    print("| channel | rows indexed | queries returning >0 hits | median hits |")
    print("|---|---|---|---|")
    qa = {}
    for ch in ("speech", "ocr", "visual"):
        nz, tot, med = 0, [], []
        for t in range(args.topics):
            hits = idx.knn(qvecs[t], channel=ch, k=K_PER_CHANNEL)
            tot.append(len(hits))
            if hits:
                nz += 1
                med.append(len(hits))
        qa[ch] = (len(membership[ch]), nz, statistics.median(med) if med else 0)
        print(f"| {ch} | {len(membership[ch])} | {nz}/{args.topics} | "
              f"{qa[ch][2]} |")
    fts_rows = conn.execute("SELECT count(*) FROM text_fts").fetchone()[0]
    fts_nz = sum(1 for t in range(args.topics)
                 if idx.search_text(f"topico {t}"))
    print(f"| fts (lexical, 4th) | {fts_rows} rows | {fts_nz}/{args.topics} | "
          f"{statistics.median([len(idx.search_text(f'topico {t}')) for t in range(args.topics)]):.0f} |")
    print(f"\n  PRODUCT POPULATION of executed RRF queries = 0 (no index db exists on "
          f"disk; this table is the SYNTHETIC corpus, not the product).")

    # -- 2. rank lists from the PRODUCT knn ---------------------------------
    rank_lists: dict[str, list] = {ch: [] for ch in qa}
    per_query: dict[tuple, list] = {}
    for t in range(args.topics):
        for ch in ("speech", "ocr", "visual"):
            hits = idx.knn(qvecs[t], channel=ch, k=K_PER_CHANNEL)
            seq = [s for s, _r, _c in hits]
            per_query[(t, ch)] = seq
            rank_lists[ch].append(seq)

    # -- 3. metrics: each single channel and the fusion ---------------------
    def evaluate(make_ranked):
        mrrs, recs = [], []
        for t in range(args.topics):
            ranked = make_ranked(t)
            mrrs.append(mrr_at_k(ranked, relevant[t], 10))
            recs.append(recall_at_k(ranked, relevant[t], 10))
        return sum(mrrs) / len(mrrs), sum(recs) / len(recs)

    rows_out = {}
    for ch in ("speech", "ocr", "visual"):
        rows_out[ch] = evaluate(lambda t, ch=ch: per_query[(t, ch)])
    rows_out["FUSION"] = evaluate(lambda t: rrf({c: per_query[(t, c)] for c in CHANNELS if per_query[(t, c)]}, WEIGHTS))
    # parity against the product's own fusion
    prod = evaluate(lambda t: [h["seg_id"] for h in idx.search(qvecs[t], k=10)])
    rows_out["FUSION(product search.py)"] = prod

    print("\n## 2. MRR@10 / recall@10 -- POPULATION = "
          f"{args.topics} queries, k=10, ground truth = topic membership")
    print("| system | MRR@10 | recall@10 |")
    print("|---|---|---|")
    for name in ("speech", "ocr", "visual", "FUSION", "FUSION(product search.py)"):
        m, r = rows_out[name]
        print(f"| {name} | {m:.4f} | {r:.4f} |")

    # -- 4. NEGATIVE ARM: reverse ONE channel --------------------------------
    rev = {}
    for ch in ("speech", "ocr", "visual"):
        rev[ch] = evaluate(
            lambda t, ch=ch: rrf({c: per_query[(t, c)] for c in CHANNELS
                                  if per_query[(t, c)]}, WEIGHTS, reverse=ch))
    print("\n## 3. NEGATIVE ARM -- one channel's rank list REVERSED before fusing")
    print("| reversed channel | MRR@10 | recall@10 | delta MRR vs fusion |")
    print("|---|---|---|---|")
    worse_any = False
    for ch in ("speech", "ocr", "visual"):
        m, r = rev[ch]
        d = m - rows_out["FUSION"][0]
        print(f"| {ch} | {m:.4f} | {r:.4f} | {d:+.4f} |")
        if d < 0 or r < rows_out["FUSION"][1]:
            worse_any = True

    # -- 5. gate -------------------------------------------------------------
    best_mrr = max(rows_out[c][0] for c in CHANNELS)
    best_rec = max(rows_out[c][1] for c in CHANNELS)
    fail = []
    if rows_out["FUSION"][0] <= best_mrr:
        fail.append(f"fusion MRR@10 {rows_out['FUSION'][0]:.4f} did NOT beat the best "
                    f"single channel {best_mrr:.4f}")
    if rows_out["FUSION"][1] <= best_rec:
        fail.append(f"fusion recall@10 {rows_out['FUSION'][1]:.4f} did NOT beat the "
                    f"best single channel {best_rec:.4f}")
    if not worse_any:
        fail.append("reversing an input did NOT degrade the metric -- the metric "
                    "is INSENSITIVE and therefore meaningless")
    insensitive = [ch for ch in CHANNELS
                   if rev[ch][0] >= rows_out["FUSION"][0]
                   or rev[ch][1] >= rows_out["FUSION"][1]]
    if insensitive:
        fail.append(f"reversing {', '.join(insensitive)} did NOT make the metric "
                    f"WORSE -- the gate cannot say NO on those channels")
    if abs(rows_out["FUSION"][0] - prod[0]) > 1e-9:
        fail.append(f"PARITY FAIL: my RRF {rows_out['FUSION'][0]:.4f} != product "
                    f"search.py {prod[0]:.4f}")

    print()
    if fail:
        for f in fail:
            print(f"FAIL {f}")
        print("GATE rc=1 -- THE GATE SAID NO")
        rc = 1
    else:
        print(f"GATE rc=0 -- fusion beats every single channel, and every reversed "
              f"arm degraded, and probe RRF == product search.py")
        rc = 0

    conn.close()
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n# probe temp dir removed: {tmp}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())