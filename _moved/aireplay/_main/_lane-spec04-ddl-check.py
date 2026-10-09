import re, sqlite3, json

SPEC = r"H:\sotto\_moved\aireplay\specs\04-index-search.md"
txt = open(SPEC, encoding="utf-8").read()
blocks = re.findall(r"```sql\n(.*?)```", txt, flags=re.S)
print("sql fences found:", len(blocks))
db = sqlite3.connect(":memory:")
db.execute("pragma foreign_keys=ON")
db.row_factory = sqlite3.Row
ok = True
for i, b in enumerate(blocks):
    try:
        db.executescript(b)
        print("  fence %d: OK (%d lines)" % (i, len(b.strip().splitlines())))
    except Exception as e:
        ok = False
        print("  fence %d: FAIL %s: %s" % (i, type(e).__name__, e))
        print("     first stmt:", b.strip().splitlines()[0][:90])
print("ALL FENCES EXECUTED:", ok)

print("")
print("-- the upsert the spec mandates (ON CONFLICT ... RETURNING) --")
try:
    db.execute("insert into video(clip_uuid,path,produced_by,added_at) values('u1','C:/a.mp4','capture-cut',0)")
    r = db.execute("insert into segment(video_id,start_ms,end_ms) values(1,0,5000) "
                   "on conflict(video_id,start_ms) do update set end_ms=excluded.end_ms "
                   "returning seg_id").fetchone()
    print("  first insert seg_id =", r["seg_id"])
    r2 = db.execute("insert into segment(video_id,start_ms,end_ms) values(1,0,5000) "
                    "on conflict(video_id,start_ms) do update set end_ms=excluded.end_ms "
                    "returning seg_id").fetchone()
    print("  re-run  seg_id =", r2["seg_id"], "(same row:", r["seg_id"] == r2["seg_id"], ")")
    print("  segment count =", db.execute("select count(*) from segment").fetchone()[0])
except Exception as e:
    print("  FAIL", type(e).__name__, e)

print("")
print("-- overlapping segment accepted? --")
try:
    db.execute("insert into segment(video_id,start_ms,end_ms) values(1,4600,10000)")
    print("  a segment overlapping its predecessor: ACCEPTED (correct: no non-overlap constraint)")
except Exception as e:
    print("  REJECTED ->", e)

print("")
print("-- empty transcript is legal, NULL is not --")
try:
    db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars)"
               " values(1,0,5000,'',' ','asr:x','deadbeef',0)")
    row = db.execute("select text,n_chars from transcript").fetchone()
    print("  text='' accepted:", repr(row[0]), "n_chars", row[1])
except Exception as e:
    print("  '' REJECTED ->", e)
try:
    db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars)"
               " values(2,0,5000,NULL,NULL,'asr:x','deadbeef',0)")
    print("  text=NULL accepted  <-- WRONG, NOT NULL should refuse")
except Exception as e:
    print("  text=NULL refused by NOT NULL:", type(e).__name__)

print("")
print("-- embedding CHECK constraints --")
blob = b"\x00\x00"
for ch, dt in [("speech", "float16"), ("nope", "float16"), ("speech", "bfloat16")]:
    try:
        db.execute("insert into embedding(seg_id,channel,dim,dtype,vec,model,model_sha256,built_at)"
                   " values(1,?,256,?,?,'m','h',0)", (ch, dt, blob))
        print("  channel=%r dtype=%r: accepted" % (ch, dt))
    except Exception as e:
        print("  channel=%r dtype=%r: refused -> %s" % (ch, dt, e))

print("")
print("-- FK enforcement (foreign_keys=ON) --")
try:
    db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars)"
               " values(99999,0,5000,'x','x','a','b',1)")
    print("  orphan transcript ACCEPTED <-- foreign_keys NOT enforced")
except Exception as e:
    print("  orphan transcript refused:", type(e).__name__)

print("")
print("-- FTS5 round trip through the spec's own triggers --")
# A FRESH segment: seg_id 1 already holds the empty-text row above, and
# transcript.seg_id is the PK -- so reusing it would be MY bug, not the schema's.
db.execute("insert into segment(video_id,start_ms,end_ms) values(1,9000,14000) returning seg_id")
seg2 = db.execute("select max(seg_id) from segment").fetchone()[0]
db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars)"
           " values(?,9000,14000,'na proxima segunda-feira','na proxima segunda-feira','asr:x','h',26)", (seg2,))
try:
    r = db.execute("select rowid from transcript_fts where transcript_fts match ?", ('"segunda-feira"',)).fetchall()
    print("  quoted MATCH -> rowids", [x[0] for x in r], "(the inserted seg_id is %d)" % seg2)
except Exception as e:
    print("  quoted MATCH FAILED", e)
try:
    db.execute("select rowid from transcript_fts where transcript_fts match ?", ("segunda-feira",)).fetchall()
    print("  unquoted MATCH returned without raising <-- spec 1.5 would be stale")
except Exception as e:
    print("  unquoted MATCH RAISED:", type(e).__name__, e, "(the trap, as documented)")

print("")
print("-- rebuild is possible from the base table (external content) --")
try:
    db.execute("insert into transcript_fts(transcript_fts) values('rebuild')")
    # transcript_fts has ONE column (text_norm); the seg id is the ROWID, reached as `rowid`.
    # Asking for a `seg_id` column here is the probe's own bug, not the schema's -- an
    # instrument that reports its own typo as a spec defect is worse than no instrument.
    r = db.execute("select rowid from transcript_fts where transcript_fts match ?", ('"segunda-feira"',)).fetchall()
    print("  rebuild OK ->", [x[0] for x in r], "rows for the quoted query")
except Exception as e:
    print("  rebuild FAILED", type(e).__name__, e)