"""NEGATIVE CONTROL for `_index-crash-probe.py`: the same hard kill, with durability OFF.

The main probe says "committed rows survive a `taskkill /F`". An instrument that cannot say NO is
worthless, so this is the same measurement on a deliberately-broken copy of the SAME writer:
`journal_mode=OFF, synchronous=OFF` (no rollback journal, no fsync). If the kill lands inside a
transaction, the file should come back corrupt or short -- that is the RED that gives the green
above its meaning. If this arm ALSO comes back clean, the main probe's green proves nothing about
crash safety and that must be said out loud.

Run: pythonw.exe _main\_index-crash-neg-probe.py --json _main\index-crash-neg.json --rows 20000
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_index-crash")
PY = sys.executable
D = 256


def child(dbpath, nrows):
    import sqlite_vec

    db = sqlite3.connect(dbpath, isolation_level=None)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute("pragma journal_mode=OFF")        # <- the deliberately broken copy
    db.execute("pragma synchronous=OFF")
    db.execute("create virtual table vec_seg using vec0(vec_id integer primary key, "
               "emb float[256] distance_metric=cosine)")
    rng = np.random.default_rng(7)
    done = 0
    while True:
        db.execute("begin")
        for i in range(done, done + 500):
            v = rng.standard_normal(D, dtype=np.float32)
            db.execute("insert into vec_seg values(?,?)", (i, sqlite_vec.serialize_float32(v)))
        db.execute("commit")
        done += 500
        with open(dbpath + ".progress", "w") as f:
            f.write(str(done))
        if nrows and done >= nrows:
            time.sleep(1.0)
            done = 0
            db.execute("delete from vec_seg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--rows", type=int, default=20_000)
    ap.add_argument("--child")
    a = ap.parse_args()
    if a.child:
        return child(a.child, a.rows) or 0

    import sqlite_vec

    os.makedirs(WORK, exist_ok=True)
    dbp = os.path.join(WORK, "crash-neg.db")
    for s in ("", "-wal", "-shm", ".progress"):
        if os.path.exists(dbp + s):
            os.remove(dbp + s)
    p = subprocess.Popen([PY, os.path.abspath(__file__), "--child", dbp, "--rows", str(a.rows)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)
    t0 = time.time()
    committed = 0
    while time.time() - t0 < 60:
        if os.path.exists(dbp + ".progress"):
            try:
                committed = int(open(dbp + ".progress").read().strip())
            except ValueError:
                pass
            if committed >= a.rows // 2:      # kill INSIDE the run, mid-transaction
                break
        time.sleep(0.1)
    time.sleep(0.2)
    subprocess.run(["taskkill", "/F", "/PID", str(p.pid)], capture_output=True)   # exact PID
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass

    res = {"probe": "_index-crash-neg-probe.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "arm": "NEGATIVE CONTROL: journal_mode=OFF, synchronous=OFF, same hard kill",
           "kill": "taskkill /F /PID (TerminateProcess)",
           "rows_committed_by_writer_at_kill": committed,
           "db_bytes_at_kill": os.path.getsize(dbp) if os.path.exists(dbp) else 0,
           "journal_files_present": {s: os.path.exists(dbp + s) for s in ("-wal", "-shm", "-journal")}}
    db = sqlite3.connect(dbp)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    try:
        integrity = db.execute("pragma integrity_check").fetchone()[0]
    except Exception as e:
        integrity = "integrity_check RAISED: %s: %s" % (type(e).__name__, e)
    survived, knn, err = None, None, None
    try:
        survived = db.execute("select count(*) from vec_seg").fetchone()[0]
    except Exception as e:
        err = "%s: %s" % (type(e).__name__, e)
    if survived is not None:
        try:
            q = np.zeros(D, dtype=np.float32)
            q[0] = 1.0
            knn = db.execute("select count(*) from (select vec_id from vec_seg where emb match ? and k=100)",
                             (sqlite_vec.serialize_float32(q),)).fetchone()[0]
        except Exception as e:
            err = "%s: %s" % (type(e).__name__, e)
    res.update({"integrity_check": integrity, "rows_after_kill": survived,
                "knn_k100_rows_after_reopen": knn, "query_error": err,
                "RED": bool(integrity != "ok" or survived is None or err),
                "verdict": ("RED as expected: durability off loses or corrupts data -- the main "
                            "probe's green is meaningful" if (integrity != "ok" or survived is None or err)
                            else "GREEN: this control did NOT go red -- the crash probe cannot say NO")})
    db.close()
    txt = json.dumps(res, indent=2)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    try:
        print(txt)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
