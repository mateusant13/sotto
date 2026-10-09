import sqlite3, json, sys
c = sqlite3.connect(":memory:")
print("sqlite_version", sqlite3.sqlite_version)
print("module_version", sqlite3.version)
opts = [r[0] for r in c.execute("pragma compile_options")]
print("FTS5_compile_option", "ENABLE_FTS5" in opts)
print("FTS3_compile_option", "ENABLE_FTS3" in opts)
print("JSON1_compile_option", "ENABLE_JSON1" in opts)
print("RTREE_compile_option", "ENABLE_RTREE" in opts)
tok = [r[0] for r in c.execute("select name from pragma_module_list()") ]
print("modules", tok)
# can we actually create an fts5 table with the tokenizers we intend?
for t in ("unicode61", "ascii", "porter"):
    try:
        c.execute(f"create virtual table t_{t} using fts5(x, tokenize='{t} remove_diacritics 2')")
        print("tokenizer_ok", t)
    except Exception as e:
        print("tokenizer_FAIL", t, type(e).__name__, e)
try:
    c.execute("create virtual table t_trgm using fts5(x, tokenize='trigram')")
    print("tokenizer_ok trigram")
except Exception as e:
    print("tokenizer_FAIL trigram", type(e).__name__, e)
print("sqlite_version_info", sqlite3.sqlite_version_info)