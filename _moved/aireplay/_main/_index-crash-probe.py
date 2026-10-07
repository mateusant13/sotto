"""CRASH SAFETY of the two candidate stores, measured by killing a writer with TerminateProcess.

Part A -- sqlite-vec: a child process inserts vectors in committed batches inside WAL mode.
  The parent hard-kills it (no close, no checkpoint) and then reopens the file and asks:
  integrity_check, row counts, and does KNN still answer. Everything COMMITTED must survive;
  the in-flight transaction must be rolled back, not half-applied.

Part B -- hnswlib (if importable): a child calls save_index() in a loop, dropping a marker file
  around each save so the parent can kill the process INSIDE the write. A store whose only
  durability point is a whole-file dump is exactly as safe as that dump.

Run: python _main/_index-crash-probe.py [--json OUT] [--rows 60000]
Child: python _main/_index-crash-probe.py --child-sqlite DB --rows N
       python _main/_index-crash-probe.py --child-hnsw BIN
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_index-crash")
PY = sys.executable
D = 256


def sha256(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- children
def child_sqlite(dbpath, nrows):
    import sqlite3

    import sqlite_vec

    db = sqlite3.connect(dbpath, isolation_level=None)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute("pragma journal_mode=WAL")
    db.execute("pragma synchronous=NORMAL")
    db.execute("create table if not exists meta(k text primary key, v integer)")
    db.execute("create virtual table if not exists vec_seg using vec0(vec_id integer primary key, emb float[256] distance_metric=cosine)")
    rng = np.random.default_rng(7)
    done = 0
    batch = 500
    while True:
        db.execute("begin")
        for i in range(done, done + batch):
            v = rng.standard_normal(D, dtype=np.float32)
            db.execute("insert into vec_seg values(?,?)", (i, sqlite_vec.serialize_float32(v)))
        db.execute("commit")
        done += batch
        with open(dbpath + ".progress", "w") as f:
            f.write(str(done))
        if nrows and done >= nrows:
            time.sleep(1.0)   # stay alive so the parent's kill lands on a live, idle writer
            done = 0
            db.execute("delete from vec_seg")
    # unreachable


def child_hnsw(binpath):
    import hnswlib

    rng = np.random.default_rng(11)
    n = 120_000
    data = rng.standard_normal((n, D), dtype=np.float32)
    p = hnswlib.Index(space="cosine", dim=D)
    p.init_index(max_elements=n, ef_construction=200, M=16)
    p.add_items(data, np.arange(n))
    while True:
        with open(binpath + ".saving", "w") as f:
            f.write("1")
        p.save_index(binpath)
        os.remove(binpath + ".saving")
        time.sleep(0.05)


# ---------------------------------------------------------------- parent
def hard_kill(proc):
    """TerminateProcess via taskkill on the exact pid -- no console, no graceful path."""
    subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def popen(args):
    flags = 0x08000000  # CREATE_NO_WINDOW
    return subprocess.Popen([PY, os.path.abspath(__file__)] + args,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=flags)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--rows", type=int, default=60_000)
    ap.add_argument("--child-sqlite")
    ap.add_argument("--child-hnsw")
    a = ap.parse_args()
    if a.child_sqlite:
        return child_sqlite(a.child_sqlite, a.rows) or 0
    if a.child_hnsw:
        return child_hnsw(a.child_hnsw) or 0

    import sqlite3

    import sqlite_vec

    os.makedirs(WORK, exist_ok=True)
    res = {"probe": "_index-crash-probe.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"), "kill": "taskkill /F /PID (TerminateProcess)"}

    # ---------------- Part A: sqlite-vec
    dbp = os.path.join(WORK, "crash.db")
    for s in ("", "-wal", "-shm", ".progress"):
        if os.path.exists(dbp + s):
            os.remove(dbp + s)
    p = popen(["--child-sqlite", dbp, "--rows", str(a.rows)])
    t0 = time.time()
    committed = 0
    while time.time() - t0 < 120:
        if os.path.exists(dbp + ".progress"):
            try:
                committed = int(open(dbp + ".progress").read().strip())
            except ValueError:
                pass
            if committed >= a.rows + 10 * 500 or committed >= a.rows:
                break
        time.sleep(0.2)
    time.sleep(0.35)                      # let a write be genuinely in flight / just committed
    hard_kill(p)
    wal_bytes = os.path.getsize(dbp + "-wal") if os.path.exists(dbp + "-wal") else 0
    db = sqlite3.connect(dbp)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    integrity = db.execute("pragma integrity_check").fetchone()[0]
    survived = db.execute("select count(*) from vec_seg").fetchone()[0]
    rng = np.random.default_rng(3)
    q = rng.standard_normal(D, dtype=np.float32)
    hits = db.execute("select count(*) from (select vec_id from vec_seg where emb match ? and k=100)",
                      (sqlite_vec.serialize_float32(q),)).fetchone()[0]
    res["sqlite_vec"] = {
        "rows_committed_by_writer_at_kill": committed,
        "rows_after_kill": survived,
        "rows_lost_beyond_last_commit": committed - survived,
        "wal_bytes_at_kill": wal_bytes,
        "integrity_check": integrity,
        "knn_k100_rows_after_reopen": hits,
        "elapsed_s": round(time.time() - t0, 2),
        "verdict": "committed rows survive; uncommitted batch rolled back"
        if survived >= committed - 500 and integrity == "ok" and hits == 100 else "MISMATCH",
    }
    db.close()

    # ---------------- Part B: hnswlib (optional)
    try:
        import hnswlib  # noqa: F401
        have = True
    except Exception as e:
        have = False
        res["hnswlib"] = {"importable": False, "error": "%s: %s" % (type(e).__name__, e)}
    if have:
        binp = os.path.join(WORK, "crash.hnsw.bin")
        for s in ("", ".saving"):
            if os.path.exists(binp + s):
                os.remove(binp + s)
        p = popen(["--child-hnsw", binp])
        caught = False
        t0 = time.time()
        while time.time() - t0 < 240:
            if os.path.exists(binp + ".saving"):
                hard_kill(p)
                caught = True
                break
            if p.poll() is not None:
                break
        if not caught:
            hard_kill(p)
        size = os.path.getsize(binp) if os.path.exists(binp) else 0
        load_ok, load_err = False, None
        try:
            import hnswlib

            idx = hnswlib.Index(space="cosine", dim=D)
            idx.load_index(binp, max_elements=120_000)
            idx.set_ef(50)
            l, d = idx.knn_query(np.zeros((1, D), dtype=np.float32), k=5)
            load_ok = True
        except Exception as e:
            load_err = "%s: %s" % (type(e).__name__, e)
        res["hnswlib"] = {
            "importable": True,
            "killed_inside_save_index": caught,
            "file_bytes_after_kill": size,
            "load_index_after_kill_ok": load_ok,
            "load_index_error": load_err,
            "verdict": "a kill during save_index leaves an unusable file" if not load_ok
            else "save_index happened to be atomic in this attempt (retry to hunt the window)",
        }

    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
