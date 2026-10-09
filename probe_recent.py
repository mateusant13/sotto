"""Second-stage probe: cross-check the '111 recent lanes' claim.

Counts DISTINCT session dirs (depth-4 under ROOT) whose newest file falls
inside the horizon, vs. the raw count of recent .jsonl FILES. These two are
different populations and were likely conflated.

Read-only. Opens any sqlite store with mode=ro and uri=True; never copies it.
"""
import json
import os
import sqlite3
import sys
import time

ROOT = r"C:\Users\Administrador\.minimax\v2\sessions"
SQLITE_DIR = r"C:\Users\Administrador\.minimax\v2\sqlite"
HORIZON_S = 3600
NOW = time.time()

# Every swallowed OSError lands here and is reported in the output, so a
# permission/path failure can never masquerade as a measured low count.
SCAN_ERRORS = []

out = {
    "probe_instant_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW)),
    "horizon_s": HORIZON_S,
}

# depth-4 dirs = the "<HH-MM-SS-mmm>-session_<b64>" dirs
session_dirs = []
for y in os.scandir(ROOT):
    if not y.is_dir(follow_symlinks=False):
        continue
    for mo in os.scandir(y.path):
        if not mo.is_dir(follow_symlinks=False):
            continue
        for d in os.scandir(mo.path):
            if not d.is_dir(follow_symlinks=False):
                continue
            for sd in os.scandir(d.path):
                if sd.is_dir(follow_symlinks=False):
                    session_dirs.append(sd.path)

out["q_session_dirs"] = {
    "population": "directories at depth 4 under ROOT (year/month/day/session)",
    "count": len(session_dirs),
}

recent_session_dirs = []
newest_overall = None
for sd in session_dirs:
    mt = None
    try:
        for e in os.scandir(sd):
            if e.is_file(follow_symlinks=False):
                st = e.stat()
                if mt is None or st.st_mtime > mt:
                    mt = st.st_mtime
    except OSError as exc:
        # LOUD: an unreadable session dir would silently undercount the
        # recent-dir population, so record it instead of swallowing it.
        SCAN_ERRORS.append({"path": sd, "err": repr(exc)})
        continue
    if mt is None:
        continue
    if NOW - mt <= HORIZON_S:
        recent_session_dirs.append((sd, mt))
    if newest_overall is None or mt > newest_overall:
        newest_overall = mt

out["q_recent_session_dirs"] = {
    "population": (f"session dirs (depth 4) whose NEWEST file mtime is within "
                   f"{HORIZON_S}s of probe instant"),
    "count": len(recent_session_dirs),
}
out["q_newest_file_anywhere_in_tree"] = {
    "mtime_utc": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(newest_overall))
                  if newest_overall else None),
}


def dir_stats(sd):
    """Newest file + size + total bytes. Returns (best, n_files, total_bytes)."""
    best, n, total = None, 0, 0
    try:
        for e in os.scandir(sd):
            if e.is_file(follow_symlinks=False):
                st = e.stat()
                n += 1
                total += st.st_size
                if best is None or st.st_mtime > best[1]:
                    best = (e.name, st.st_mtime, st.st_size)
    except OSError as exc:
        SCAN_ERRORS.append({"path": sd, "err": repr(exc)})
    return best, n, total


def messages_size(sd):
    try:
        for e in os.scandir(sd):
            if e.is_file(follow_symlinks=False) and e.name == "messages.jsonl":
                return e.stat().st_size
    except OSError as exc:
        SCAN_ERRORS.append({"path": sd, "err": repr(exc)})
    return None


samples = []
for sd, mt in sorted(recent_session_dirs, key=lambda t: t[1], reverse=True)[:5]:
    best, n, total = dir_stats(sd)
    samples.append({
        "session_dir": sd,
        "n_files": n,
        "newest_file_name": best[0] if best else None,
        "newest_file_mtime_utc": (time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(best[1])) if best else None),
        "newest_file_size": best[2] if best else None,
        "newest_file_age_s": round(NOW - best[1], 3) if best else None,
        "dir_total_bytes": total,
        "messages_jsonl_size": messages_size(sd),
    })
out["q5_samples"] = {
    "population": "top 5 recent session dirs by newest-file mtime",
    "samples": samples,
}

# Full file listing for those same 5, to show whether activity is real.
breakdown = []
for sd, mt in sorted(recent_session_dirs, key=lambda t: t[1], reverse=True)[:5]:
    rows = []
    try:
        for e in os.scandir(sd):
            if e.is_file(follow_symlinks=False):
                st = e.stat()
                rows.append({"name": e.name,
                             "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                        time.gmtime(st.st_mtime)),
                             "size": st.st_size})
    except OSError as exc:
        SCAN_ERRORS.append({"path": sd, "err": repr(exc)})
    breakdown.append({
        "session_dir": sd,
        "dir_name_start_stamp": "-".join(os.path.basename(sd).split("-")[:3]),
        "files": sorted(rows, key=lambda r: r["mtime_utc"]),
    })
out["q5_file_breakdown"] = breakdown

# ---- sqlite store, READ-ONLY, never copied ----
sqlite_info = {"dir": SQLITE_DIR, "stores": []}
if os.path.isdir(SQLITE_DIR):
    for e in sorted(os.scandir(SQLITE_DIR), key=lambda x: x.name):
        if e.is_file(follow_symlinks=False):
            sqlite_info["stores"].append({
                "name": e.name, "size": e.stat().st_size,
                "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                          time.gmtime(e.stat().st_mtime))})
out["sqlite_inventory"] = sqlite_info

target = None
for e in sqlite_info["stores"]:
    if e["name"].endswith(".db") or e["name"].endswith(".sqlite3"):
        target = e["name"]
if target:
    uri = "file:" + os.path.join(SQLITE_DIR, target).replace("\\", "/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    info = {"store": target, "uri_mode": "ro", "tables": tables, "counts": {}}
    for t in tables:
        try:
            cur.execute('SELECT COUNT(*) FROM "%s"' % t.replace('"', '""'))
            info["counts"][t] = cur.fetchone()[0]
        except sqlite3.Error as exc:
            info["counts"][t] = "ERR " + repr(exc)
    con.close()
    out["sqlite_readonly"] = info

out["scan_errors"] = SCAN_ERRORS[:20]
out["scan_error_count"] = len(SCAN_ERRORS)

text = json.dumps(out, indent=2)
print(text)