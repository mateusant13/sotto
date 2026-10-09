import json, sqlite3
j = json.load(open(r"H:\sotto\_moved\aireplay\_main\lane-spec04-asr-emit.json", encoding="utf-8"))
texts = [s["text"] for s in j["segments"]]
c = sqlite3.connect(":memory:")
c.execute("create virtual table f using fts5(text_norm, content='', tokenize='unicode61 remove_diacritics 2')")
c.executemany("insert into f(rowid,text_norm) values(?,?)", list(enumerate(texts)))
def q(term):
    try:
        rows = c.execute("select rowid from f where f match ? order by bm25(f)", (term,)).fetchall()
        return f"OK n={len(rows)} rows={rows}"
    except sqlite3.Error as e:
        return f"RAISED {type(e).__name__}: {e}"
for t in ["segunda-feira", '"segunda-feira"', "segunda", "interditada", "ACESSO", "acess*",
          '"ponte"', "segunda OR ponte", "r-adio", '"segunda-feira"', "rio"]:
    print(f"{t!r:20} -> {q(t)}")