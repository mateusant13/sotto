"""CRASH SAFETY, both colours in ONE instrument, with the kill aimed INSIDE a transaction.

The first attempt (`_index-crash-probe.py`) slept a fixed 0.35 s before killing, so the kill could
land BETWEEN transactions -- and its negative control (durability OFF) then came back green, which
proves nothing. This probe removes that ambiguity: the child writes a marker file that says
`T:<done>` the instant it is INSIDE a transaction (right after `begin`, before the batch), and the
parent kills the exact pid the moment it reads that marker. Both arms use the SAME method, the same
row count and the same batch size, so the only difference is durability:

  ARM A  journal_mode=WAL, synchronous=NORMAL   <- the shipped configuration
  ARM B  journal_mode=OFF, synchronous=OFF      <- the deliberately broken copy (must go RED)

A kill inside a transaction with WAL must lose only the in-flight batch and keep `integrity_check`
clean. With durability OFF it must lose or corrupt something -- if it does not, this instrument
cannot say NO and the green above is not evidence.

Run: pythonw.exe _main\_index-crash2-probe.py --json _main\index-crash2.json --rows 20000
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
WORK = os.path.join(HERE, "_index-crash2")
PY = sys.executable
D = 256
BATCH = 2000


def child(dbpath, nrows, mode):
    import sqlite_vec

    db = sqlite3.connect(dbpath, isolation_level=None)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    if mode == "wal":
        db.execute("pragma journal_mode=WAL")
        db.execute("pragma synchronous=NORMAL")
    elif mode == "off":
        db.execute("pragma journal_mode=OFF")
        db.execute("pragma synchronous=OFF")
    else:
        # ARM C: durability off AND a page cache too small to hold the in-flight transaction, so
        # the transaction's pages REACH THE FILE before commit. This is the arm that should break.
        db.execute("pragma journal_mode=OFF")
        db.execute("pragma synchronous=OFF")
        db.execute("pragma cache_size=50")
    db.execute("create virtual table if not exists vec_seg using vec0("
               "vec_id integer primary key, emb float[256] distance_metric=cosine)")
    rng = np.random.default_rng(7)
    done = 0
    while True:
        with open(dbpath + ".progress", "w") as f:      # "T:" == inside the transaction
            f.write("T:%d" % done)
        db.execute("begin")
        for i in range(done, done + BATCH):
            v = rng.standard_normal(D, dtype=np.float32)
            db.execute("insert into vec_seg values(?,?)", (i, sqlite_vec.serialize_float32(v)))
        db.execute("commit")
        done += BATCH
        with open(dbpath + ".progress", "w") as f:
            f.write("C:%d" % done)
        if nrows and done >= nrows:
            done = 0
            db.execute("delete from vec_seg")


def run_arm(mode, rows):
    dbp = os.path.join(WORK, "crash_%s.db" % mode)
    for s in ("", "-wal", "-shm", ".progress", "-journal"):
        if os.path.exists(dbp + s):
            os.remove(dbp + s)
    p = subprocess.Popen([PY, os.path.abspath(__file__), "--child", dbp, "--rows", str(rows),
                          "--mode", mode], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=0x08000000)
    last_commit, caught_in_txn, t0 = 0, False, time.time()
    while time.time() - t0 < 60:
        if os.path.exists(dbp + ".progress"):
            try:
                v = open(dbp + ".progress").read().strip()
            except OSError:
                v = ""
            if v.startswith("T:") and int(v[2:]) >= BATCH * 2:   # a couple of commits in, so it is real
                caught_in_txn = True
                break
            if v.startswith("C:"):
                last_commit = int(v[2:])
        time.sleep(0.002)
    subprocess.run(["taskkill", "/F", "/PID", str(p.pid)], capture_output=True)   # exact PID only
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    files = {s: (os.path.getsize(dbp + s) if os.path.exists(dbp + s) else 0)
             for s in ("", "-wal", "-shm", "-journal")}
    out = {"mode": mode, "killed_inside_transaction": caught_in_txn,
           "last_committed_before_kill": last_commit, "files_at_kill": files}
    import sqlite_vec as sv

    db = sqlite3.connect(dbp)
    db.enable_load_extension(True)
    sv.load(db)
    db.enable_load_extension(False)
    try:
        out["integrity_check"] = db.execute("pragma integrity_check").fetchone()[0]
    except Exception as e:
        out["integrity_check"] = "RAISED %s: %s" % (type(e).__name__, e)
    out["rows_after_kill"], out["query_error"] = None, None
    try:
        out["rows_after_kill"] = db.execute("select count(*) from vec_seg").fetchone()[0]
    except Exception as e:
        out["query_error"] = "%s: %s" % (type(e).__name__, e)
    if out["rows_after_kill"] is not None:
        try:
            q = np.zeros(D, dtype=np.float32)
            q[0] = 1.0
            out["knn_k100_rows_after_reopen"] = db.execute(
                "select count(*) from (select vec_id from vec_seg where emb match ? and k=100)",
                (sv.serialize_float32(q),)).fetchone()[0]
        except Exception as e:
            out["query_error"] = "%s: %s" % (type(e).__name__, e)
    db.close()
    if out["rows_after_kill"] is not None and last_commit:
        out["rows_lost_beyond_last_commit"] = last_commit - out["rows_after_kill"]
    out["clean"] = bool(out["integrity_check"] == "ok" and out["query_error"] is None
                        and (out["rows_lost_beyond_last_commit"] if "rows_lost_beyond_last_commit" in out
                             else 0) == 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--rows", type=int, default=20_000)
    ap.add_argument("--child")
    ap.add_argument("--mode", default="wal")
    a = ap.parse_args()
    if a.child:
        return child(a.child, a.rows, a.mode) or 0

    os.makedirs(WORK, exist_ok=True)
    res = {"probe": "_index-crash2-probe.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rows": a.rows, "batch": BATCH,
           "kill": "taskkill /F /PID on the marker 'T:' (inside a transaction)"}
    res["armA_wal_synchronous_normal"] = run_arm("wal", a.rows)
    res["armB_journal_off_synchronous_off"] = run_arm("off", a.rows)
    res["armC_journal_off_small_cache"] = run_arm("off_smallcache", a.rows)
    a_, b_, c_ = (res["armA_wal_synchronous_normal"], res["armB_journal_off_synchronous_off"],
                  res["armC_journal_off_small_cache"])
    res["verdict"] = {
        "armA_green": a_["clean"],
        "armB_red": (not b_["clean"]),
        "armC_red": (not c_["clean"]),
        "all_arms_caught_a_transaction": bool(a_["killed_inside_transaction"]
                                              and b_["killed_inside_transaction"]
                                              and c_["killed_inside_transaction"]),
        "conclusion": ("GREEN-with-control: WAL survives a mid-transaction kill intact and at least "
                       "one durability-off arm goes RED, so the green is earned"
                       if a_["clean"] and (not b_["clean"] or not c_["clean"]) else
                       "INCONCLUSIVE: no control arm went red -- this instrument cannot say NO "
                       "about crash safety, and the WAL arm's green must not be quoted as proof"),
    }
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
