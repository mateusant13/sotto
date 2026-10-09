import re, io, json
P = r"H:\sotto\_moved\aireplay\specs\04-index-search.md"
raw = open(P,"rb").read()
txt = raw.decode("utf-8")
print("bytes", len(raw), "sha256", __import__("hashlib").sha256(raw).hexdigest()[:16])
print("CRLF", raw.count(b"\r\n"), "bare LF", raw.count(b"\n") - raw.count(b"\r\n"))
print()
print("-- ROADMAP gate --")
for name, pat in [("6 tables", r"CREATE TABLE (video|segment|transcript|ocr|embedding|marker)\("),
                  ("meta (added)", r"CREATE TABLE meta\("),
                  ("rrf weights speech1.0", r"speech[`\"]?\s*[:=]\s*1\.0"),
                  ("visual 0.7", r"visual[`\"]?\s*[:=]\s*0\.7"),
                  ("lexical 1.0", r"lexical[`\"]?\s*[:=]\s*1\.0"),
                  ("k=100", r"k = 100|k=100"),
                  ("CREATE VIRTUAL TABLE fts5", r"CREATE VIRTUAL TABLE")]:
    print(f"  {name:28} {len(re.findall(pat, txt))}")
print()
print("-- banned --")
for w in ["TBD","TODO","FIXME","???","XXX"]:
    hits = [m.start() for m in re.finditer(re.escape(w), txt)]
    print(f"  {w:8} {len(hits)}")
print()
print("-- provenance tags --")
for tag in ["MEASURED","READ","UNKNOWN","⚙"]:
    print(f"  {tag:9} {txt.count(tag)}")
print()
print("-- table count by CREATE TABLE --")
print(" ", sorted(set(re.findall(r"CREATE TABLE (\w+)\(", txt))))
print("-- virtual tables --")
print(" ", sorted(set(re.findall(r"CREATE VIRTUAL TABLE (\w+)\(", txt))))
print("-- indexes --")
print(" ", sorted(set(re.findall(r"CREATE INDEX (\w+)", txt))))
print()
print("-- asr segment keys present --")
for k in ["i, start, end, audio_s, wall_s, chars, text"]:
    print(f"  {k!r:40} {k in txt}")
print("-- measured facts asserted --")
for s in ["914.32","922.38","922.18","0.0458","0.1670","14.583","37.572","8.667","55.584","3.75",
          "0.1670","3.43.1","814","804","0.20","segunda-feira","no such column: feira"]:
    print(f"  {s:28} {s in txt}")