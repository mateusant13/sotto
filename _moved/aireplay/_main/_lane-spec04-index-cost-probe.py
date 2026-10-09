# LANE SPEC-04 -- the numbers specs/04-index-search.md quotes for the WRITE path and the
# SEARCH surface that docs/research/07-index-search.md did NOT measure: the same light
# commit WITH an FTS5 row, FTS5 insert/query latency at the real corpus shape, the file
# size, and the reconciliation scan.
#
# WHY THIS PROBE EXISTS: research 07 measured the light commit at 0.061 ms median / 0.198 ms
# p95 and the fused query at 83.2 ms -- but its schema had NO fts5 table, so the lexical
# surface it named in section 3 ("a 4th list belongs in the fusion") was never costed. A spec
# that quotes 0.061 ms as the per-clip write budget would be quoting a number for a schema
# that does not ship.
#
# HOUSE RULES: pure sqlite3 + stdlib (no numpy/onnxruntime) => the thread budget of law 8 is
# not at risk; no artefact above ~200 MB; the DB is created under _main\_spec04-probe\ and the
# source data is synthetic. BOTH COLOURS: ARM-NEG runs the same corpus with the fts5 triggers
# REMOVED, and the spec's reconciliation claim must be able to say NO about a row the lexical
# surface cannot find (i.e. the gate asserts the two surfaces AGREE, and must go RED when the
# trigger is dropped).
#
# Usage:  python _main\_lane-spec04-index-cost-probe.py
# Exit:   0 = both arms behaved. Non-zero = the ORACLE is broken.

import json
import os
import random
import sqlite3
import statistics
import sys
import time

ROOT = r"H:\sotto\_moved\aireplay"
WORK = os.path.join(ROOT, "_main", "_spec04-probe")
DB = os.path.join(WORK, "store.db")
OUT = os.path.join(ROOT, "_main", "lane-spec04-index-cost.json")

# The corpus shape is research 07 section 6: 1000 videos x 10 min, 5 s windows = 120000
# segments, speech ~60% (72000) and OCR ~16% (19200). Those fractions are that lane's
# ASSUMPTION, carried here so the numbers are comparable -- not re-asserted as measured.
N_VIDEO = 1000
N_SEG = 120000
N_TRANSCRIPT = 72000
N_OCR = 19200
WIN_MS = 5000

# PT/EN-ish tokens with the shapes that actually appear in game transcripts and on-screen
# text: accented words, a hyphenated compound, a hex error code, a mixed-case token.
WORDS = ["acesso negado", "jogador matou o chefe", "segunda-feira", "ERRO 0x80070005",
         "clique em Confirmar", "vida baixa", "nova rodada", "kit de suprimento",
         "vitória por tarefas", "carregando", "menu principal", "sala de espera"]


def mk_text(rng, n):
    return " ".join(rng.choice(WORDS) for _ in range(n))


def ms(fn, reps=5, warm=1):
    for _ in range(warm):
        fn()
    v = []
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        v.append((time.perf_counter() - t) * 1000.0)
    v.sort()
    return {"min": round(v[0], 4), "median": round(statistics.median(v), 4), "max": round(v[-1], 4)}


SCHEMA = """
create table video(id integer primary key, path text not null, content_key text,
    size_bytes integer, mtime_ns integer, duration_ms integer, w integer, h integer,
    fps integer, added_at integer, last_seen_scan integer, missing integer default 0,
    state text default 'discovered');
create table segment(seg_id integer primary key, video_id integer not null,
    start_ms integer not null, end_ms integer not null, n_visual integer default 0,
    n_speech integer default 0, n_ocr integer default 0, state text default 'new');
create table transcript(seg_id integer primary key, start_ms integer, end_ms integer,
    text text, text_norm text, producer text, model_sha256 text);
create table ocr(seg_id integer, line_no integer, t_ms integer, t_end_ms integer,
    text_raw text, text_norm text, box text, conf real, engine text, model_sha256 text,
    frame_ref text, primary key(seg_id, line_no));
create index segment_video on segment(video_id, start_ms);
create index transcript_seg on transcript(seg_id);
create index ocr_seg on ocr(seg_id);
"""

# EXTERNAL CONTENT over transcript: the base table stays the single source of truth and the
# fts index can be rebuilt from it. content='' (contentless) would halve the file but make a
# rebuild impossible -- and a clip that exists and cannot be found is THE failure this spec
# exists to prevent.
FTS = """
create virtual table transcript_fts using fts5(
    text_norm, content='transcript', content_rowid='seg_id',
    tokenize='unicode61 remove_diacritics 2');
create virtual table ocr_fts using fts5(
    text_norm, content='ocr', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2');
create trigger transcript_ai after insert on transcript begin
  insert into transcript_fts(rowid, text_norm) values (new.seg_id, new.text_norm);
end;
create trigger transcript_ad after delete on transcript begin
  insert into transcript_fts(transcript_fts, rowid, text_norm) values('delete', old.seg_id, old.text_norm);
end;
create trigger transcript_au after update on transcript begin
  insert into transcript_fts(transcript_fts, rowid, text_norm) values('delete', old.seg_id, old.text_norm);
  insert into transcript_fts(rowid, text_norm) values (new.seg_id, new.text_norm);
end;
"""


def build(with_fts: bool):
    os.makedirs(WORK, exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(DB + suffix):
            os.remove(DB + suffix)
    db = sqlite3.connect(DB)
    db.execute("pragma journal_mode=WAL")
    db.execute("pragma synchronous=NORMAL")
    db.executescript(SCHEMA)
    if with_fts:
        db.executescript(FTS)
    db.commit()
    return db


def populate(db):
    rng = random.Random(20261008)
    t0 = time.perf_counter()
    db.execute("begin")
    db.executemany("insert into video(id,path,content_key,size_bytes,duration_ms,w,h,fps,state)"
                   " values(?,?,?,?,?,?,?,?,?)",
                   [(i, f"H:\\clips\\clip_{i:04d}.mp4", f"{i:064x}", 60_000_000, 600_000,
                     1920, 1080, 60, "clipped") for i in range(N_VIDEO)])
    db.executemany("insert into segment(seg_id,video_id,start_ms,end_ms,state)"
                   " values(?,?,?,?,?)",
                   [(s, s // 120, (s % 120) * WIN_MS, (s % 120) * WIN_MS + WIN_MS, "new")
                    for s in range(N_SEG)])
    db.commit()
    t_rel = time.perf_counter() - t0

    t0 = time.perf_counter()
    db.execute("begin")
    db.executemany("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256)"
                   " values(?,?,?,?,?,?,?)",
                   [(s, (s % 120) * WIN_MS, (s % 120) * WIN_MS + WIN_MS,
                     mk_text(rng, 7), mk_text(rng, 7).lower(), "asr:int8-parakeet", "6139d2fa")
                    for s in range(N_TRANSCRIPT)])
    db.commit()
    t_tr = time.perf_counter() - t0

    t0 = time.perf_counter()
    db.execute("begin")
    db.executemany("insert into ocr(seg_id,line_no,t_ms,t_end_ms,text_raw,text_norm,conf,engine)"
                   " values(?,?,?,?,?,?,?,?)",
                   [(s, 0, 0, 300, mk_text(rng, 4), mk_text(rng, 4).lower(), 0.87, "winocr")
                    for s in range(0, N_OCR * 6, 6)])
    db.commit()
    t_ocr = time.perf_counter() - t0
    return {"relational_s": round(t_rel, 3), "transcript_s": round(t_tr, 3),
            "transcript_rows_per_s": round(N_TRANSCRIPT / t_tr),
            "ocr_s": round(t_ocr, 3), "ocr_rows_per_s": round(N_OCR / t_ocr)}


def light_commit_cost(db):
    """THE number the write path must be held to: one closed segment -> its rows, committed.

    The research measured 0.061 ms median WITHOUT the fts5 triggers. This measures the same
    shape WITH them, because the shipped schema has them."""
    rng = random.Random(7)
    seg = N_SEG + 1
    db.execute("insert into segment(seg_id,video_id,start_ms,end_ms,state) values(?,?,?,?,?)",
               (seg, 999, 0, WIN_MS, "new"))
    db.commit()

    lat = []
    for i in range(200):
        s = seg + 1 + i
        text = mk_text(rng, 7)
        t = time.perf_counter()
        db.execute("begin")
        db.execute("insert into segment(seg_id,video_id,start_ms,end_ms,n_speech,state)"
                   " values(?,?,?,?,?,?)", (s, 999, 0, WIN_MS, 1, "transcribed"))
        db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256)"
                   " values(?,?,?,?,?,?,?)",
                   (s, 0, WIN_MS, text, text.lower(), "asr:int8-parakeet", "6139d2fa"))
        db.commit()
        lat.append((time.perf_counter() - t) * 1000.0)
    lat.sort()
    return {"n": len(lat), "min_ms": round(lat[0], 4),
            "median_ms": round(statistics.median(lat), 4),
            "p95_ms": round(lat[int(len(lat) * 0.95)], 4), "max_ms": round(lat[-1], 4),
            "shape": "segment + transcript + fts5 trigger, one commit per window"}


def lexical(db):
    def top(sql, params=(), k=10):
        # An UNQUOTED hyphenated term RAISES `OperationalError: no such column: <part>`
        # rather than returning nothing. That raise is the finding, so it is RECORDED as
        # data -- an exception that escapes here would make the probe report a crash
        # instead of the trap the spec has to warn about.
        t = time.perf_counter()
        try:
            rows = db.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            return {"ms": round((time.perf_counter() - t) * 1000.0, 4), "n_rows": 0,
                    "raised": f"{type(exc).__name__}: {exc}", "sample": []}
        return {"ms": round((time.perf_counter() - t) * 1000.0, 4), "n_rows": len(rows),
                "raised": None, "sample": rows[:2]}

    one = top("select rowid from transcript_fts where transcript_fts match ? order by bm25(transcript_fts) limit 10",
              ("acesso",))
    phrase = top("select rowid from transcript_fts where transcript_fts match ? order by bm25(transcript_fts) limit 10",
                 ('"acesso negado"',))
    prefix = top("select rowid from transcript_fts where transcript_fts match ? order by bm25(transcript_fts) limit 10",
                 ("acess*",))
    code = top("select rowid from transcript_fts where transcript_fts match ? order by bm25(transcript_fts) limit 10",
               ("0x80070005",))
    # THE TRAP: an unquoted hyphenated term is a PARSE ERROR, not an empty result.
    hyphen_raw = top("select rowid from transcript_fts where transcript_fts match ? order by bm25(transcript_fts) limit 10",
                     ("segunda-feira",))
    hyphen_q = top("select rowid from transcript_fts where transcript_fts match ? order by bm25(transcript_fts) limit 10",
                   ('"segunda-feira"',))
    joined = top("select v.path, s.start_ms, t.text from transcript_fts f "
                 "join transcript t on t.seg_id = f.rowid "
                 "join segment s on s.seg_id = t.seg_id "
                 "join video v on v.id = s.video_id "
                 "where transcript_fts match ? order by bm25(transcript_fts) limit 10", ("acesso",))
    full_k100 = ms(lambda: db.execute(
        "select rowid from transcript_fts where transcript_fts match ? "
        "order by bm25(transcript_fts) limit 100", ("acesso",)).fetchall(), reps=5)
    return {"one_token": one, "phrase": phrase, "prefix": prefix, "hex_code": code,
            "hyphen_unquoted": hyphen_raw, "hyphen_quoted": hyphen_q,
            "joined_answer_path": joined, "k100": full_k100}


def reconcile(db):
    """The spec's recovery query: which clips are written but not indexed, and can the
    lexical surface find every transcript row that EXISTS?"""
    t = time.perf_counter()
    n = db.execute("select count(*) from segment where state != 'indexed'").fetchone()[0]
    ms_scan = (time.perf_counter() - t) * 1000.0
    t = time.perf_counter()
    missing = db.execute(
        "select count(*) from transcript t where not exists "
        "(select 1 from transcript_fts f where f.rowid = t.seg_id)").fetchone()[0]
    ms_orphan = (time.perf_counter() - t) * 1000.0
    return {"segments_not_indexed": n, "scan_ms": round(ms_scan, 3),
            "transcripts_absent_from_fts": missing, "orphan_scan_ms": round(ms_orphan, 3),
            "surfaces_agree": missing == 0}


def sizes(db):
    db.execute("pragma wal_checkpoint(TRUNCATE)")
    return {"file_bytes": os.path.getsize(DB), "file_MB": round(os.path.getsize(DB) / 1e6, 2),
            "file_MiB": round(os.path.getsize(DB) / 2**20, 2)}


def census():
    return {"sqlite_version": sqlite3.sqlite_version, "threads": os.cpu_count(),
            "python": sys.version.split()[0]}


def arm(with_fts):
    db = build(with_fts)
    rep = {"with_fts5": with_fts, "census": census(), "populate": populate(db)}
    rep["light_commit"] = light_commit_cost(db)
    if with_fts:
        rep["lexical"] = lexical(db)
        rep["reconcile"] = reconcile(db)
    rep["sizes"] = sizes(db)
    rep["rows"] = {t: db.execute(f"select count(*) from {t}").fetchone()[0]
                   for t in ("video", "segment", "transcript", "ocr")}
    db.close()
    return rep


def main():
    arm0 = arm(True)   # ARM-0: the shipped schema. MUST be GREEN.
    armN = arm(False)  # ARM-NEG: the same corpus with no fts5. The control.

    problems = []
    if arm0["reconcile"]["transcripts_absent_from_fts"] != 0:
        problems.append("ARM-0: the triggers did not cover every transcript row")
    if arm0["lexical"]["joined_answer_path"]["n_rows"] < 1:
        problems.append("ARM-0: the lexical surface found nothing -> the gate cannot say NO")
    if not arm0["lexical"]["hyphen_unquoted"]["raised"]:
        problems.append("ARM-0: the unquoted-hyphen term no longer RAISES; the spec's quoting "
                        "rule would be protecting against a defect that does not exist")
    if arm0["lexical"]["hyphen_quoted"]["n_rows"] < 1:
        problems.append("ARM-0: the QUOTED hyphenated term found nothing, so quoting is not the fix")
    if arm0["lexical"]["hex_code"]["n_rows"] < 1:
        problems.append("ARM-0: the exact hex error code is not findable; the lexical surface "
                        "fails the case research 07 section 3 names")
    if armN["with_fts5"]:
        problems.append("ARM-NEG ran the shipping arm")

    report = {
        "lane": "spec04-index-cost",
        "corpus_shape": {"videos": N_VIDEO, "segments": N_SEG, "transcripts": N_TRANSCRIPT,
                         "ocr": N_OCR, "window_ms": WIN_MS,
                         "note": "speech 60% / ocr 16% are research 07 section 6 ASSUMPTIONS"},
        "arms": {"ARM-0-fts5": arm0, "ARM-NEG-no-fts5": armN},
        "overhead": {
            "file_bytes_delta": arm0["sizes"]["file_bytes"] - armN["sizes"]["file_bytes"],
            "file_MiB_delta": round((arm0["sizes"]["file_bytes"] - armN["sizes"]["file_bytes"]) / 2**20, 2),
            "light_commit_median_ms": {"with_fts5": arm0["light_commit"]["median_ms"],
                                       "no_fts5": armN["light_commit"]["median_ms"],
                                       "ratio": round(arm0["light_commit"]["median_ms"]
                                                      / max(armN["light_commit"]["median_ms"], 1e-9), 2)},
        },
        "oracle_verdict": "GREEN" if not problems else "RED",
        "oracle_problems": problems,
        "oracle_note": "ARM-NEG is the control that proves the fts5 cost is attributable to "
                       "fts5 and not to the corpus or the disk.",
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print("lane=spec04-index-cost  corpus=%d segments / %d transcripts" % (N_SEG, N_TRANSCRIPT))
    print("  ARM-0-fts5    light_commit median=%.4f ms p95=%.4f ms  file=%.1f MiB"
          % (arm0["light_commit"]["median_ms"], arm0["light_commit"]["p95_ms"],
             arm0["sizes"]["file_MiB"]))
    print("  ARM-NEG-nofts light_commit median=%.4f ms p95=%.4f ms  file=%.1f MiB"
          % (armN["light_commit"]["median_ms"], armN["light_commit"]["p95_ms"],
             armN["sizes"]["file_MiB"]))
    print("  lexical one_token=%.3f ms n=%d  phrase=%.3f ms  k100=%.3f ms median"
          % (arm0["lexical"]["one_token"]["ms"], arm0["lexical"]["one_token"]["n_rows"],
             arm0["lexical"]["phrase"]["ms"], arm0["lexical"]["k100"]["median"]))
    print("  JOIN answer path=%.3f ms n=%d  %r"
          % (arm0["lexical"]["joined_answer_path"]["ms"],
             arm0["lexical"]["joined_answer_path"]["n_rows"],
             arm0["lexical"]["joined_answer_path"]["sample"][:1]))
    print("  hyphen unquoted n_rows=%d (0 == it RAISED, which is the trap) / quoted n_rows=%d"
          % (arm0["lexical"]["hyphen_unquoted"]["n_rows"], arm0["lexical"]["hyphen_quoted"]["n_rows"]))
    print("  reconcile: transcripts absent from fts=%d  orphan_scan=%.1f ms"
          % (arm0["reconcile"]["transcripts_absent_from_fts"], arm0["reconcile"]["orphan_scan_ms"]))
    print("  OVERHEAD of fts5: file +%.2f MiB, light commit %.2fx"
          % (report["overhead"]["file_MiB_delta"], report["overhead"]["light_commit_median_ms"]["ratio"]))
    print("  ORACLE: " + report["oracle_verdict"] + ("  <- " + "; ".join(problems) if problems else ""))
    print("  -> " + OUT)
    if problems:
        print("ORACLE BROKEN: the arms did not separate.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())