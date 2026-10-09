"""Sotto search: three-channel Reciprocal Rank Fusion + the FTS5 lexical list.

Design + measured numbers: docs/research/07-index-search.md sec 3.

The rule: ONE KNN per channel, merged by Reciprocal Rank Fusion,
    score(seg) = sum_c  w_c / (60 + rank_c(seg))
    w = {speech 1.0, ocr 1.0, visual 0.7}
RRF and not a score sum because the three channels live in three spaces with
three distance scales: RANKS are the only comparable quantity, so the fusion
needs no calibration.

NO RERANKER.  The smallest local cross-encoder measured 10.8 s/query at 2
threads -- 130x the entire fused query (83 ms) -- and no measurement exists
that it improves top-5 on this data (07 sec 4).

The lexical (FTS5) channel is the required baseline for OCR: game tokens like
`ERRO 0x80070005: ACESSO NEGADO` come back byte-exact (lane 02).  Its RRF weight
is UNKNOWN -- 07 sec 7 item 6 -- so it is exposed as a parameter, not guessed
into the weights dict as if it were measured.
"""

from __future__ import annotations

import sqlite3

import numpy as np

import store

RRF_K = 60                 # the standard constant; doc 07 sec 3
K_PER_CHANNEL = 100        # each channel contributes k=100
WEIGHTS = {"speech": 1.0, "ocr": 1.0, "visual": 0.7}
VECTOR_CHANNELS = ("speech", "ocr", "visual")


def _l2(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


class Hit(dict):
    """A hit IS a 5 s window of a file: seg_id -> start_ms -> path."""


class SearchIndex:
    """The in-RAM scan.  Build once, query many times."""

    def __init__(self, conn: sqlite3.Connection, *, include_missing: bool = False):
        self.conn = conn
        (self.vecs, self.seg_ids, self.channels, self.video_ids,
         self._blocks) = store.load_matrix(conn, include_missing=include_missing)
        self.n, self.dim = (self.vecs.shape[0], self.vecs.shape[1]
                            if self.vecs.size else 0)

    # -- one channel --------------------------------------------------------
    def knn(self, query: np.ndarray, *, channel: str, k: int = K_PER_CHANNEL,
            video_id: int | None = None, t0_ms: int | None = None,
            t1_ms: int | None = None) -> list[tuple[int, int, float]]:
        """Returns [(seg_id, rank, cosine)] for one channel, best first.

        SCANS ONLY THIS CHANNEL'S ROWS.  `store.load_matrix` groups the matrix by
        channel, so the block is a contiguous view and the scan is this channel's
        rows -- not the whole matrix with the other channels masked out
        afterwards.  A channel with no rows is absent from `_blocks` and costs
        nothing at all.

        Measured at n=211200 (POPULATION n=211200, WINDOW 60 queries, <=2
        threads) this took the query from 3 whole-matrix scans to 1 block scan;
        see _main/index_perf_profile.md for the before/after.
        """
        if self.n == 0:
            return []
        block = self._blocks.get(channel)
        if block is None:
            return []                       # no rows for this channel: no scan
        lo, hi = block
        q = _l2(query)
        sims = self.vecs[lo:hi] @ q         # this channel's rows only
        if video_id is not None or t0_ms is not None or t1_ms is not None:
            sims = np.where(self._filter_mask(lo, hi, video_id, t0_ms, t1_ms),
                            sims, -np.inf)
        take = min(k, sims.shape[0])
        if take <= 0:
            return []
        # ascending partition then take the tail: same k as np.argpartition(-sims,
        # take-1)[:take] without allocating and negating a full-length array.
        top = np.argpartition(sims, sims.shape[0] - take)[-take:]
        top = top[np.argsort(-sims[top])]
        seg_ids = self.seg_ids
        return [(int(seg_ids[lo + i]), rank + 1, float(sims[i]))
                for rank, i in enumerate(top) if np.isfinite(sims[i])]

    def _filter_mask(self, lo: int, hi: int, video_id: int | None,
                     t0_ms: int | None, t1_ms: int | None) -> np.ndarray:
        """Row filter over the channel block.  Built ONLY when a filter is asked
        for: the unfiltered case needs no mask at all, which is the whole query."""
        mask = np.ones(hi - lo, dtype=bool)
        if video_id is not None:
            mask &= (self.video_ids[lo:hi] == video_id)
        if t0_ms is not None or t1_ms is not None:
            # start_ms is RELATIVE TO EACH VIDEO'S OWN START, so a window is
            # always (video_id, t0_ms, t1_ms) -- never a bare library-wide range.
            rows = self.conn.execute(
                "SELECT seg_id, start_ms FROM segment WHERE "
                + ("video_id = ? AND " if video_id is not None else "")
                + "start_ms >= ? AND start_ms <= ?",
                tuple(x for x in (video_id, t0_ms or 0, t1_ms if t1_ms is not None
                                  else 2 ** 62) if x is not None)).fetchall()
            ok = np.array([int(r["seg_id"]) for r in rows], dtype=np.int64)
            mask &= np.isin(self.seg_ids[lo:hi], ok)
        return mask

    # -- the fused query ----------------------------------------------------
    def search(self, query: np.ndarray, *, k: int = 10,
               weights: dict[str, float] | None = None,
               video_id: int | None = None, t0_ms: int | None = None,
               t1_ms: int | None = None) -> list[Hit]:
        """RRF over the vector channels.  Every hit names the channels that
        matched, with each channel's rank + cosine -- the three UI chips."""
        weights = {**WEIGHTS, **(weights or {})}
        scores: dict[int, float] = {}
        detail: dict[int, dict[str, dict]] = {}
        for channel, weight in weights.items():
            if channel not in VECTOR_CHANNELS:
                continue
            for seg_id, rank, cosine in self.knn(
                    query, channel=channel, k=K_PER_CHANNEL, video_id=video_id,
                    t0_ms=t0_ms, t1_ms=t1_ms):
                scores[seg_id] = scores.get(seg_id, 0.0) + weight / (RRF_K + rank)
                detail.setdefault(seg_id, {})[channel] = {"rank": rank,
                                                          "cosine": round(cosine, 6)}
        return self._materialise(scores, detail, k)

    # -- the lexical channel ------------------------------------------------
    def search_text(self, query: str, *, k: int = 100) -> list[tuple[int, int, float]]:
        """FTS5 channel.  Returns [(seg_id, rank, bm25_as_cosine_proxy)].

        bm25 is a distance, not a cosine, so it must not enter a cosine field:
        it is reported as-is under `bm25` by _materialise.
        """
        if not query.strip():
            return []
        try:
            rows = self.conn.execute(
                "SELECT seg_id, bm25(text_fts) AS s FROM text_fts "
                "WHERE text_fts MATCH ? ORDER BY s LIMIT ?",
                (query, k)).fetchall()
        except sqlite3.OperationalError:
            return []          # malformed FTS5 expression: no lexical hits, no crash
        return [(int(r["seg_id"]), i + 1, -float(r["s"]))
                for i, r in enumerate(rows)]

    def search_all(self, query: np.ndarray | None = None, *, text: str | None = None,
                   k: int = 10, fts_weight: float = 1.0,
                   video_id: int | None = None, t0_ms: int | None = None,
                   t1_ms: int | None = None) -> list[Hit]:
        """The full fusion: 3 vector channels + FTS5.  fts_weight is a PARAMETER
        because its correct value is UNKNOWN (07 sec 7 item 6)."""
        scores: dict[int, float] = {}
        detail: dict[int, dict[str, dict]] = {}

        def absorb(seg_id: int, channel: str, rank: int, weight: float, **extra):
            scores[seg_id] = scores.get(seg_id, 0.0) + weight / (RRF_K + rank)
            detail.setdefault(seg_id, {})[channel] = dict(rank=rank, **extra)

        if query is not None:
            for channel, weight in WEIGHTS.items():
                for seg_id, rank, cosine in self.knn(
                        query, channel=channel, k=K_PER_CHANNEL, video_id=video_id,
                        t0_ms=t0_ms, t1_ms=t1_ms):
                    absorb(seg_id, channel, rank, weight, cosine=round(cosine, 6))
        if text:
            for seg_id, rank, s in self.search_text(text, k=K_PER_CHANNEL):
                if video_id is not None or t0_ms is not None or t1_ms is not None:
                    if not self._in_window(seg_id, video_id, t0_ms, t1_ms):
                        continue
                absorb(seg_id, "fts", rank, fts_weight, bm25=round(s, 6))
        return self._materialise(scores, detail, k)

    # -- helpers ------------------------------------------------------------
    def _in_window(self, seg_id: int, video_id: int | None, t0_ms: int | None,
                   t1_ms: int | None) -> bool:
        sql = "SELECT s.start_ms, s.video_id FROM segment s WHERE s.seg_id = ?"
        r = self.conn.execute(sql, (seg_id,)).fetchone()
        if r is None:
            return False
        if video_id is not None and int(r["video_id"]) != video_id:
            return False
        if t0_ms is not None and int(r["start_ms"]) < t0_ms:
            return False
        if t1_ms is not None and int(r["start_ms"]) > t1_ms:
            return False
        return True

    def _materialise(self, scores: dict[int, float], detail: dict, k: int) -> list[Hit]:
        order = sorted(scores, key=lambda s: (-scores[s], s))[:k]
        meta = store.segments_for(self.conn, order) if order else {}
        hits: list[Hit] = []
        for seg_id in order:
            info = meta.get(seg_id)
            if info is None:
                continue
            chans = detail.get(seg_id, {})
            hits.append(Hit(
                seg_id=seg_id, score=round(scores[seg_id], 8),
                video_id=int(info["video_id"]), path=info["path"],
                start_ms=int(info["start_ms"]), end_ms=int(info["end_ms"]),
                missing=int(info["missing"]),
                # explainable by construction: which channels matched, and how
                channels=sorted(chans),
                evidence=chans,
                at=f"{info['path']} @ {info['start_ms'] // 60000:02d}:"
                   f"{(info['start_ms'] % 60000) / 1000:06.3f}"))
        return hits


def jaccard(a: str, b: str) -> float:
    """The free re-rank: pure-python Jaccard, 0.146 ms median for 100 candidates
    (07 sec 4) -- 74 000x cheaper than the smallest cross-encoder."""
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    return len(sa & sb) / len(sa | sb) if sa or sb else 0.0