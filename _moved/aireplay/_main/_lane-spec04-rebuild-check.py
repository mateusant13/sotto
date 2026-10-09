import sqlite3
print("sqlite", sqlite3.sqlite_version)

def t(label, ddl, rebuild="insert into transcript_fts(transcript_fts) values('rebuild')"):
    db = sqlite3.connect(":memory:")
    db.execute("create table transcript(seg_id integer primary key, text_norm text not null)")
    try:
        db.execute(ddl)
    except Exception as e:
        print(label, "DDL FAIL", e); return
    db.execute("insert into transcript(seg_id,text_norm) values(5,'na proxima segunda-feira')")
    db.execute("insert into transcript_fts(rowid,text_norm) values(5,'na proxima segunda-feira')")
    n = db.execute("select count(*) from transcript_fts").fetchone()[0]
    hit = db.execute("select rowid from transcript_fts where transcript_fts match ?", ('"segunda-feira"',)).fetchall()
    print("%-58s rows=%d match=%s" % (label, n, [x[0] for x in hit]))
    try:
        db.execute(rebuild); print("   rebuild OK")
    except Exception as e:
        print("   rebuild FAIL:", type(e).__name__, e)

t("content= + content_rowid=seg_id",
  "create virtual table transcript_fts using fts5(text_norm, content='transcript', content_rowid='seg_id', tokenize='unicode61 remove_diacritics 2')")
t("content= only",
  "create virtual table transcript_fts using fts5(text_norm, content='transcript', tokenize='unicode61 remove_diacritics 2')")
t("content='' (contentless)",
  "create virtual table transcript_fts using fts5(text_norm, content='', tokenize='unicode61 remove_diacritics 2')")
t("no content= (own table)",
  "create virtual table transcript_fts using fts5(text_norm, tokenize='unicode61 remove_diacritics 2')")

print()
print("-- with content_rowid, what does 'rebuild' actually try? --")
db = sqlite3.connect(":memory:")
db.execute("create table transcript(seg_id integer primary key, text_norm text not null)")
db.execute("create virtual table transcript_fts using fts5(text_norm, content='transcript', content_rowid='seg_id')")
db.execute("insert into transcript(seg_id,text_norm) values(5,'segunda feira')")
try:
    db.execute("insert into transcript_fts(transcript_fts) values('rebuild')")
    print("  rebuild ok, rows =", db.execute("select count(*) from transcript_fts").fetchone()[0])
except Exception as e:
    print("  rebuild error:", e)
print("  -- try explicit-column rebuild --")
try:
    db.execute("insert into transcript_fts(transcript_fts, rank) values('rebuild', 1)")
    print("  ok rows =", db.execute("select count(*) from transcript_fts").fetchone()[0])
except Exception as e:
    print("  err:", e)