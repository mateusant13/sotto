import sqlite3
print("sqlite", sqlite3.sqlite_version)

DDL_FTS = """
CREATE VIRTUAL TABLE transcript_fts USING fts5(
  text_norm, content='transcript', content_rowid='seg_id',
  tokenize='unicode61 remove_diacritics 2');
"""
TRG = """
CREATE TRIGGER transcript_ai AFTER INSERT ON transcript BEGIN
  INSERT INTO transcript_fts(rowid, text_norm) VALUES (new.seg_id, new.text_norm);
END;
CREATE TRIGGER transcript_ad AFTER DELETE ON transcript BEGIN
  INSERT INTO transcript_fts(transcript_fts, rowid, text_norm) VALUES('delete', old.seg_id, old.text_norm);
END;
CREATE TRIGGER transcript_au AFTER UPDATE ON transcript BEGIN
  INSERT INTO transcript_fts(transcript_fts, rowid, text_norm) VALUES('delete', old.seg_id, old.text_norm);
  INSERT INTO transcript_fts(rowid, text_norm) VALUES (new.seg_id, new.text_norm);
END;
"""

def build(with_trg):
    db = sqlite3.connect(":memory:")
    db.executescript("create table transcript(seg_id integer primary key, start_ms integer, end_ms integer, text text not null, text_norm text not null, producer text not null, model_sha256 text not null, n_chars integer not null);")
    db.execute(DDL_FTS)
    if with_trg:
        db.executescript(TRG)
    return db

for with_trg in (False, True):
    db = build(with_trg)
    db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars) values(1,0,5000,'segunda feira','segunda feira','a','b',12)")
    print("\n-- triggers present:", with_trg, "| fts rows after insert:", db.execute("select count(*) from transcript_fts").fetchone()[0])
    for label, stmt in [("values('rebuild')", "insert into transcript_fts(transcript_fts) values('rebuild')"),
                        ("values('rebuild',1)", "insert into transcript_fts(transcript_fts, rank) values('rebuild', 1)")]:
        try:
            db.execute(stmt)
            print("   %-22s OK  rows=%d" % (label, db.execute("select count(*) from transcript_fts").fetchone()[0]))
        except Exception as e:
            print("   %-22s FAIL %s: %s" % (label, type(e).__name__, e))