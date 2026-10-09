import re, sqlite3
SPEC = r"H:\sotto\_moved\aireplay\specs\04-index-search.md"
blocks = re.findall(r"```sql\n(.*?)```", open(SPEC, encoding="utf-8").read(), flags=re.S)
def fresh():
    db = sqlite3.connect(":memory:")
    db.execute("pragma foreign_keys=ON")
    for b in blocks: db.executescript(b)
    db.execute("insert into video(clip_uuid,path,produced_by,added_at) values('u','p','capture-cut',0)")
    db.execute("insert into segment(video_id,start_ms,end_ms) values(1,0,5000)")
    db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars) values(1,0,5000,'segunda feira','segunda feira','a','b',12)")
    return db
def rb(db):
    try:
        db.execute("insert into transcript_fts(transcript_fts) values('rebuild')")
        return "rebuild OK rows=%d" % db.execute("select count(*) from transcript_fts").fetchone()[0]
    except Exception as e:
        return "rebuild FAIL %s: %s" % (type(e).__name__, e)

print("A. no raising MATCH first          ->", rb(fresh()))

db = fresh()
try:
    db.execute("select rowid from transcript_fts where transcript_fts match ?", ("segunda-feira",)).fetchall()
except Exception as e:
    print("B. raising MATCH happened          ->", type(e).__name__, e)
print("   then                              ", rb(db))

db = fresh()
try:
    db.execute("select rowid from transcript_fts where transcript_fts match ?", ("segunda-feira",)).fetchall()
except Exception:
    pass
db.rollback()
print("C. raising MATCH + explicit rollback->", rb(db))

db = fresh()
try:
    db.execute("select rowid from transcript_fts where transcript_fts match ?", ("segunda-feira",)).fetchall()
except Exception:
    pass
print("D. raising MATCH, in_transaction?   ", db.in_transaction)
db.execute("rollback")
print("   after rollback                   ", rb(db))