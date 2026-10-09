import re, sqlite3, traceback
SPEC = r"H:\sotto\_moved\aireplay\specs\04-index-search.md"
txt = open(SPEC, encoding="utf-8").read()
blocks = re.findall(r"```sql\n(.*?)```", txt, flags=re.S)
db = sqlite3.connect(":memory:")
for b in blocks:
    db.executescript(b)
print("tables:", [r[0] for r in db.execute("select name from sqlite_master where type='table'")])
print()
print("--- the spec's FTS fence verbatim ---")
print(blocks[7])
print("--- triggers in the spec: ---")
n = db.execute("select count(*) from sqlite_master where type='trigger'").fetchone()[0]
print("  trigger count =", n, "<-- 0 means the lexical surface is never populated")
print()
print("--- rebuild transcript_fts with the full schema ---")
db.execute("insert into video(clip_uuid,path,produced_by,added_at) values('u','p','capture-cut',0)")
db.execute("insert into segment(video_id,start_ms,end_ms) values(1,0,5000)")
db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars) values(1,0,5000,'segunda feira','segunda feira','a','b',12)")
try:
    db.execute("insert into transcript_fts(transcript_fts) values('rebuild')")
    print("  rebuild OK -> rows", db.execute("select count(*) from transcript_fts").fetchone()[0])
except Exception as e:
    print("  rebuild FAILED:", type(e).__name__, e)
    print("  --- traceback tail ---")
    traceback.print_exc()
print()
print("--- try rebuilding ocr_fts instead (content_rowid='rowid' on a composite PK) ---")
db.execute("insert into ocr(seg_id,line_no,t_ms,t_end_ms,text_raw,text_norm,engine,model_sha256) values(1,0,0,300,'erro','erro','win','h')")
try:
    db.execute("insert into ocr_fts(ocr_fts) values('rebuild')")
    print("  ocr rebuild OK -> rows", db.execute("select count(*) from ocr_fts").fetchone()[0])
except Exception as e:
    print("  ocr rebuild FAILED:", type(e).__name__, e)