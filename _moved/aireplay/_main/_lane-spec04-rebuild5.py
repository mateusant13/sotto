import re, sqlite3
SPEC = r"H:\sotto\_moved\aireplay\specs\04-index-search.md"
blocks = re.findall(r"```sql\n(.*?)```", open(SPEC, encoding="utf-8").read(), flags=re.S)
def fresh():
    db = sqlite3.connect(":memory:")
    db.execute("pragma foreign_keys=ON")
    for b in blocks: db.executescript(b)
    db.execute("insert into video(clip_uuid,path,produced_by,added_at) values('u','p','capture-cut',0)")
    db.execute("insert into segment(video_id,start_ms,end_ms) values(1,0,5000) on conflict(video_id,start_ms) do update set end_ms=excluded.end_ms returning seg_id").fetchone()
    db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars) values(1,0,5000,'',' ','a','b',0)")
    db.execute("insert into segment(video_id,start_ms,end_ms) values(1,4600,10000)")
    return db
def rb(db, tag):
    try:
        db.execute("insert into transcript_fts(transcript_fts) values('rebuild')")
        print("  %-40s OK rows=%d" % (tag, db.execute("select count(*) from transcript_fts").fetchone()[0]))
    except Exception as e:
        print("  %-40s FAIL %s: %s" % (tag, type(e).__name__, e))

db = fresh(); rb(db, "baseline (1 transcript)")
db = fresh(); db.execute("insert into embedding(seg_id,channel,dim,dtype,vec,model,model_sha256,built_at) values(1,'speech',256,'float16',?,'m','h',0)", (b"\x00\x00",)); rb(db, "after an embedding row")
db = fresh(); s3=db.execute("insert into segment(video_id,start_ms,end_ms) values(1,9000,14000) returning seg_id").fetchone()[0]; db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars) values(?,9000,14000,'segunda feira','segunda feira','a','b',12)",(s3,)); rb(db, "after 2nd transcript")
db = fresh()
try: db.execute("select rowid from transcript_fts where transcript_fts match ?", ('"segunda-feira"',)).fetchall()
except Exception as e: print("  (quoted match raised)", e)
rb(db, "after a QUOTED match (no rows yet)")