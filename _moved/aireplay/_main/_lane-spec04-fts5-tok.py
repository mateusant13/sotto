import sqlite3, json
c = sqlite3.connect(":memory:")
specs = [
 "unicode61",
 "unicode61 remove_diacritics 0",
 "unicode61 remove_diacritics 1",
 "unicode61 remove_diacritics 2",
 "ascii",
 "ascii remove_diacritics 1",
 "ascii remove_diacritics 2",
 "porter",
 "porter unicode61",
 "porter unicode61 remove_diacritics 2",
 "trigram",
]
ok = []
for i, s in enumerate(specs):
    try:
        c.execute(f"create virtual table v{i} using fts5(x, tokenize='{s}')")
        ok.append(s); print("OK    ", s)
    except Exception as e:
        print("FAIL  ", s, "|", e)
print("--- behaviour of unicode61 remove_diacritics 2 on real text ---")
c.execute("create virtual table f using fts5(txt, tokenize='unicode61 remove_diacritics 2')")
rows = ["ACESSO NEGADO", "acesso negado", "Acesso à Negado", "segunda-feira", "ERRO 0x80070005",
        "jogador MATOU o chefe", "0x80070005", "clique em Confirmar"]
c.executemany("insert into f(txt) values (?)", [(r,) for r in rows])
def q(s):
    try:
        return [r[0] for r in c.execute("select txt from f where f match ? order by rowid", (s,)).fetchall()]
    except Exception as e:
        return f"ERR {e}"
for term in ["acesso", "ACESSO", "negado", "Acesso à Negado", '"acesso negado"', "matou", "0x80070005",
             '"0x80070005"', "segunda", "segunda-feira", "confirm*", "acess*", "acesso OR matou", "foo NOT bar"]:
    print(repr(term), "->", q(term))