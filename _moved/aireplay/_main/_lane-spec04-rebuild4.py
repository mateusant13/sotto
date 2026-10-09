import re, sqlite3, traceback
SPEC = r"H:\sotto\_moved\aireplay\specs\04-index-search.md"
txt = open(SPEC, encoding="utf-8").read()
blocks = re.findall(r"```sql\n(.*?)```", txt, flags=re.S)

def fresh():
    db = sqlite3.connect(":memory:")
    db.execute("pragma foreign_keys=ON")
    for b in blocks:
        db.executescript(b)
    return db

def rb(db, label):
    try:
        db.execute("insert into transcript_fts(transcript_fts) values('rebuild')")
        print("  %-42s rebuild OK rows=%d" % (label, db.execute("select count(*) from transcript_fts").fetchone()[0]))
        return True
    except Exception as e:
        print("  %-42s rebuild FAIL %s: %s" % (label, type(e).__name__, e))
        return False

db = fresh()
db.execute("insert into video(clip_uuid,path,produced_by,added_at) values('u','p','capture-cut',0)")
db.execute("insert into segment(video_id,start_ms,end_ms) values(1,0,5000)")
db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars) values(1,0,5000,'',' ','a','b',0)")
print("after empty-text insert:"); rb(db, "seg1 empty text")

# Do NOT hardcode seg_id -- ask for it. A segment with no transcript row is the interesting
# case, and hardcoding seg 3 is a PROBE bug, not a schema fact (the FK correctly refused it).
s2 = db.execute("insert into segment(video_id,start_ms,end_ms) values(1,9000,14000) returning seg_id").fetchone()[0]
print("second segment id:", s2)
db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars) values(?,9000,14000,'segunda feira','segunda feira','a','b',12)", (s2,))
print("after 2nd insert:"); rb(db, "seg1 + seg2 both with transcripts")

print("seg_ids present:", [r[0] for r in db.execute("select seg_id from transcript")])
print("transcript_fts rowids:", [r[0] for r in db.execute("select rowid from transcript_fts")])
print("segment rows:", [r[0] for r in db.execute("select seg_id from segment")])
print("video rows:", [r[0] for r in db.execute("select id from video")])
print()
print("--- is it the MISSING seg_id 2 (never had a transcript)? ---")
db2 = fresh()
db2.execute("insert into video(clip_uuid,path,produced_by,added_at) values('u','p','capture-cut',0)")
db2.execute("insert into segment(video_id,start_ms,end_ms) values(1,0,5000)")
db2.execute("insert into segment(video_id,start_ms,end_ms) values(1,9000,14000)")
db2.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars) values(1,0,5000,'x','x','a','b',1)")
print("  transcript rows:", [r[0] for r in db2.execute("select seg_id from transcript")])
rb(db2, "gap in segment ids (1 present, 2 missing)")
print()
print("--- now add a transcript for seg 2 and retry ---")
db2.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars) values(2,9000,14000,'y','y','a','b',1)")
rb(db2, "after filling the gap")