import sqlite3
import sqlite_vec

print("attrs", [a for a in dir(sqlite_vec) if not a.startswith("_")])
print("__version__", getattr(sqlite_vec, "__version__", None))
d = sqlite3.connect(":memory:")
d.enable_load_extension(True)
sqlite_vec.load(d)
d.enable_load_extension(False)
print("vec_version", d.execute("select vec_version()").fetchone())
try:
    d.execute("create virtual table t using vec0(id integer primary key, e float[4] distance_metric=cosine)")
    print("cosine ctor OK")
except Exception as e:
    print("cosine ctor FAILED:", e)
d.execute("insert into t values(1, ?)", (sqlite_vec.serialize_float32([1.0, 0, 0, 0]),))
d.execute("insert into t values(2, ?)", (sqlite_vec.serialize_float32([0.0, 1.0, 0, 0]),))
print(d.execute("select id, distance from t where e match ? and k=2", (sqlite_vec.serialize_float32([1.0, 0, 0, 0]),)).fetchall())
