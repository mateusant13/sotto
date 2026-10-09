"""search.py -- the READ side: a text query over transcripts, filtered by time / device / duration.

The search surface is FTS5 over `transcript.text_norm`, probed at open time (`schema.fts5_available`)
with a LIKE fallback over the same column when FTS5 is absent. Both paths run the SAME filter SQL
and return the SAME `SearchResult` shape, with `mode` naming which one answered -- so the panel
can never draw a hit that the store cannot reproduce.

FILTER AXES, and why each is on `video` and not on `segment`:
  device  -- `video.source_device`, the capture device L1 records.
  time    -- `video.started_at_s`, epoch seconds of the clip WINDOW START. NOT a bare
             `segment.start_ms` range across the library: `start_ms` is relative to each
             clip's own start, so such a range is meaningless (07-index-search.md:51, which
             measured it and made the window per-video). For one clip the segment window is
             what you want, and that is `segment.start_ms` -- exposed by the same query.
  duration-- `video.duration_ms`, so "long clips only" is one indexed range.

EVERY RESULT CARRIES ITS POPULATION. `SearchResult.population` is how many CLIPS matched the
FILTER (the denominator), next to `len(hits)` (the numerator). "It works" without them is a
vibe, not a claim (LANE-BRIEF section 4, rule 6).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .schema import FTS_TABLE

__all__ = ["SearchFilter", "SearchResult", "search_text", "fts5_match_expression"]

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)  # letters and digits, incl. accents; no `_`


def _ms(seconds: float | None) -> int | None:
    """Seconds in, ms compared -- the same single boundary the writer uses (store._ms)."""
    return None if seconds is None else int(round(float(seconds) * 1000))


@dataclass(frozen=True)
class SearchFilter:
    """Seconds in, milliseconds compared, NULL = no bound on that axis."""

    device: str | None = None
    since_s: float | None = None       # clip window start, INCLUSIVE
    until_s: float | None = None       # clip window start, EXCLUSIVE
    min_duration_s: float | None = None
    max_duration_s: float | None = None
    clip_id: str | None = None
    include_missing: bool = False      # default FALSE: a file that is gone is not a hit

    def where(self) -> tuple[str, list[Any]]:
        """The filter SQL, identical for both search modes. Parameterised -- no string-built
        values ever reach the statement."""
        clauses: list[str] = []
        params: list[Any] = []
        if not self.include_missing:
            clauses.append("v.missing = 0")
        if self.device is not None:
            clauses.append("v.source_device = ?")
            params.append(self.device)
        if self.clip_id is not None:
            clauses.append("v.id = ?")
            params.append(self.clip_id)
        if self.since_s is not None:
            clauses.append("v.started_at_s >= ?")
            params.append(float(self.since_s))
        if self.until_s is not None:
            clauses.append("v.started_at_s < ?")
            params.append(float(self.until_s))
        if self.min_duration_s is not None:
            clauses.append("v.duration_ms >= ?")
            params.append(_ms(self.min_duration_s))
        if self.max_duration_s is not None:
            clauses.append("v.duration_ms <= ?")
            params.append(_ms(self.max_duration_s))
        return (" AND ".join(clauses) if clauses else "1=1"), params


@dataclass
class SearchResult:
    hits: list[dict] = field(default_factory=list)
    mode: str = "fts5"            # "fts5" | "like" | "empty"
    query: str = ""
    tokens: list[str] = field(default_factory=list)
    population: int = 0           # CLIPS matching the filter -- the denominator
    matched_clips: int = 0        # distinct clips among the hits
    total_hits: int = 0           # hits BEFORE `limit` -- so truncation is visible
    truncated: bool = False

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "query": self.query,
            "tokens": list(self.tokens),
            "population": self.population,
            "found": len(self.hits),
            "total_hits": self.total_hits,
            "matched_clips": self.matched_clips,
            "truncated": self.truncated,
            "hits": list(self.hits),
        }


def fts5_match_expression(query: str, require_all: bool = True) -> tuple[str, list[str]]:
    """Turn a human query into a SAFE FTS5 MATCH expression, or ("", []) when nothing survives.

    Raw user text into MATCH is a crash: `"`, `*`, `:`, `-`, `AND`/`OR`/`NEAR` are all FTS5
    syntax, and an unbalanced quote raises `sqlite3.OperationalError` at query time. Every token
    is emitted as a quoted prefix phrase (`"tok"*`) and the tokens are ANDed (default) or ORed.
    Returns the expression and the tokens actually used, so the caller can report what it
    searched for instead of silently matching nothing.
    """
    tokens = _TOKEN_RE.findall(query or "")
    if not tokens:
        return "", []
    joiner = " AND " if require_all else " OR "
    # The token regex already dropped every FTS5 metacharacter, so quoting is belt-and-braces.
    return joiner.join('"' + t.replace('"', '""') + '"*' for t in tokens), tokens


def _population(con: sqlite3.Connection, flt: SearchFilter) -> int:
    where, params = flt.where()
    return int(con.execute(
        f"SELECT count(*) FROM video v WHERE {where}", params
    ).fetchone()[0])


# Both modes select the SAME columns and join the SAME way, so a hit is comparable across them:
# transcript -> segment -> video is the answer path 07-index-search.md:44 measured at 0.011 ms.
_COLUMNS = """
SELECT t.seg_id        AS seg_id,
       v.id            AS clip_id,
       v.path          AS clip_path,
       v.h264_path     AS h264_path,
       v.aac_path      AS aac_path,
       v.source_device AS source_device,
       v.started_at_s  AS started_at_s,
       v.duration_ms   AS duration_ms,
       s.start_ms      AS start_ms,
       s.end_ms        AS end_ms,
       (s.end_ms - s.start_ms) AS audio_s,
       t.text          AS text,
       t.producer      AS producer,
       v.mode          AS mode
"""

# Both modes share the FROM/JOIN shape, so a hit is comparable across them: transcript ->
# segment -> video is the answer path 07-index-search.md:44 measured at 0.011 ms. The columns
# and the WHERE clause are separate from the FROM so the SAME statement can be reused for the
# COUNT (no columns) and for the page (columns + LIMIT).
_FTS_FROM = """FROM transcript_fts f
JOIN transcript t ON t.seg_id = f.seg_id
JOIN segment   s ON s.seg_id = t.seg_id
JOIN video     v ON v.id     = s.video_id
WHERE transcript_fts MATCH ? AND {where}
"""

_LIKE_FROM = """FROM transcript t
JOIN segment s ON s.seg_id = t.seg_id
JOIN video   v ON v.id     = s.video_id
WHERE {match} AND {where}
"""


def search_text(
    con: sqlite3.Connection,
    query: str,
    filt: SearchFilter | None = None,
    *,
    limit: int = 50,
    require_all: bool = True,
    use_fts: bool | None = None,
) -> SearchResult:
    """Search transcripts for `query`, filtered. The one read path the product uses.

    `use_fts=None` means "whatever this db was built with" (the probed answer). `use_fts=False`
    forces the LIKE fallback -- it exists so the fallback can be PROVEN alive rather than
    assumed (gate arm A checks both modes return the same hit set).
    """
    flt = filt or SearchFilter()
    result = SearchResult(query=query, population=_population(con, flt))
    limit = max(1, int(limit))  # SQLite reads `LIMIT -1` as "no limit", which is not an option

    have_fts = bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ?", (FTS_TABLE,)
    ).fetchone())
    use_fts = have_fts if use_fts is None else bool(use_fts) and have_fts

    expression, tokens = fts5_match_expression(query, require_all=require_all)
    result.tokens = tokens

    if not tokens:
        # An empty or all-punctuation query is NOT an error and NOT "everything": it is no
        # query. `MATCH ''` would raise, and answering "all rows" would be a lie about intent.
        result.mode = "empty"
        return result

    where, params = flt.where()
    if use_fts:
        base, args, order, mode = (
            _FTS_FROM.format(where=where), [expression, *params],
            "ORDER BY bm25(transcript_fts), t.start_ms", "fts5",
        )
    else:
        # LIKE over the same normalised column, one clause per token, wildcards escaped.
        base, args, order, mode = (
            _LIKE_FROM.format(
                match=" AND ".join(f"t.text_norm LIKE ? ESCAPE '\\'" for _ in tokens),
                where=where,
            ),
            [f"%{_like_escape(tok)}%" for tok in tokens] + params,
            "ORDER BY t.start_ms", "like",
        )

    # The TOTAL is counted in SQL and the page is fetched with a LIMIT. Fetching every match and
    # slicing it in python would pull the whole corpus into memory to show 50 rows -- at the
    # product's own arithmetic that is 120 000 segments (07-index-search.md:73).
    result.total_hits = int(con.execute(f"SELECT count(*) {base}", args).fetchone()[0])
    rows = con.execute(
        f"{_COLUMNS}{base} {order} LIMIT {limit + 1}", args
    ).fetchall()

    result.mode = mode
    result.truncated = result.total_hits > limit
    result.hits = [dict(row) for row in rows[:limit]]
    result.matched_clips = len({hit["clip_id"] for hit in result.hits})
    return result


def _like_escape(token: str) -> str:
    """`%`, `_` and `\\` are LIKE metacharacters; the token regex cannot emit them, but a
    caller-supplied token could, and a stray `%` would turn a search into 'everything'."""
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def clips(con: sqlite3.Connection, *, device: str | None = None, include_missing: bool = False
          ) -> list[dict]:
    """Browse without a text query -- the gallery's own list, and the population the panel
    counts against. Same filter semantics as `search_text`, so a count here and a count there
    are the same number."""
    flt = SearchFilter(device=device, include_missing=include_missing)
    where, params = flt.where()
    rows = con.execute(
        f"SELECT v.id AS clip_id, v.path AS clip_path, v.source_device AS source_device, "
        f"v.started_at_s AS started_at_s, v.duration_ms AS duration_ms, v.mode AS mode, "
        f"v.state AS state, v.missing AS missing, "
        f"(SELECT count(*) FROM segment s WHERE s.video_id = v.id) AS n_segments "
        f"FROM video v WHERE {where} ORDER BY v.started_at_s",
        params,
    ).fetchall()
    return [dict(row) for row in rows]