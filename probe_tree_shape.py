"""Read-only probe of C:\\Users\\Administrador\\.minimax\\v2\\sessions tree shape.

Two independent traversals (os.scandir manual, os.walk) plus a PowerShell
Get-ChildItem -Recurse pass run separately by the caller.

Every count is emitted with its POPULATION (what was enumerated) and the
probe INSTANT (UTC) it was taken at.
"""
import json
import os
import sys
import time

ROOT = r"C:\Users\Administrador\.minimax\v2\sessions"
HORIZON_S = 3600
OUT = sys.argv[1] if len(sys.argv) > 1 else None

T0 = time.time()
NOW = T0  # single pinned instant for all window comparisons

res = {
    "root": ROOT,
    "probe_instant_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW)),
    "root_exists": os.path.isdir(ROOT),
    "horizon_s": HORIZON_S,
}


def err(d):
    """Record an OSError instead of letting it abort the walk silently."""
    errs.append({"path": d, "err": repr(e)})


errs = []

# ---------------------------------------------------------------- Q1
# Q1: immediate children of ROOT -- dirs, files, or both? No filter.
q1 = {"population": "immediate children of ROOT (no filter, no recursion)"}
if os.path.isdir(ROOT):
    d_cnt = f_cnt = 0
    names = []
    for e in os.scandir(ROOT):
        try:
            isd = e.is_dir(follow_symlinks=False)
        except OSError as exc:
            err(ROOT)
            continue
        if isd:
            d_cnt += 1
        else:
            f_cnt += 1
            names.append(e.name)
    q1["dirs"] = d_cnt
    q1["files"] = f_cnt
    q1["total"] = d_cnt + f_cnt
    q1["top_level_files_sample"] = names[:20]
else:
    q1["error"] = "ROOT is not a directory"
res["q1_immediate_children"] = q1

# ---------------------------------------------------------------- Q2/Q3
# Q2: depth at which a .jsonl first appears.
# Q3: total .jsonl (NO filter), and how many have mtime within HORIZON_S.
q2_depth_hist = {}          # depth -> count of .jsonl
q2_deepest = None           # (depth, path) deepest path holding a .jsonl
q2_deepest_any = None       # (depth, path) deepest dir at all
all_files = 0
all_dirs = 0
jsonl_total = 0
jsonl_recent = []
jsonl_all_sizes = []
dirs_total_oswalk = 0

if os.path.isdir(ROOT):
    # --- method A: os.walk(topdown=True) ---
    for dirpath, dirnames, filenames in os.walk(ROOT, onerror=err,
                                                followlinks=False):
        depth = dirpath[len(ROOT):].count(os.sep)
        all_dirs += 1
        all_files += len(filenames)
        for fn in filenames:
            if fn.lower().endswith(".jsonl"):
                full = os.path.join(dirpath, fn)
                jsonl_total += 1
                q2_depth_hist[depth] = q2_depth_hist.get(depth, 0) + 1
                if q2_deepest is None or depth > q2_deepest[0]:
                    q2_deepest = (depth, full)
                try:
                    st = os.stat(full)
                    age = NOW - st.st_mtime
                    jsonl_all_sizes.append(st.st_size)
                    if age <= HORIZON_S:
                        jsonl_recent.append({
                            "path": full,
                            "mtime_utc": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime)),
                            "age_s": round(age, 3),
                            "size": st.st_size,
                        })
                except OSError:
                    err(full)
        if q2_deepest_any is None or depth > q2_deepest_any[0]:
            q2_deepest_any = (depth, dirpath)

    # --- method B: os.scandir recursive, counting dirs separately ---
    stack = [(ROOT, 0)]
    scandir_dirs = 0
    scandir_files = 0
    while stack:
        cur, d = stack.pop()
        try:
            entries = list(os.scandir(cur))
        except OSError:
            err(cur)
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    scandir_dirs += 1
                    stack.append((e.path, d + 1))
                else:
                    scandir_files += 1
            except OSError:
                err(cur)
    res["q4_method_b_scandir"] = {
        "population": "all entries reachable from ROOT, recursive",
        "dirs": scandir_dirs,
        "files": scandir_files,
        "note": "scandir_dirs counts ROOT itself (depth 0)",
    }

res["q3_method_a_oswalk"] = {
    "population": "all directories under ROOT, recursive, no name filter",
    "dirs_including_root": all_dirs,
    "files_total_all_extensions": all_files,
    "jsonl_total_unfiltered": jsonl_total,
    "jsonl_recent_within_horizon": len(jsonl_recent),
    "jsonl_recent_window_s": HORIZON_S,
    "jsonl_depth_histogram": {str(k): v for k, v in sorted(q2_depth_hist.items())},
    "jsonl_total_bytes": sum(jsonl_all_sizes),
}

if q2_deepest:
    res["q2_jsonl_depth"] = {
        "population": ".jsonl files under ROOT, unfiltered",
        "shallowest_depth_with_jsonl": min(q2_depth_hist) if q2_depth_hist else None,
        "deepest_depth_with_jsonl": q2_deepest[0],
        "deepest_path_example": q2_deepest[1],
    }
if q2_deepest_any:
    res["q2_tree_max_depth"] = {
        "deepest_dir_depth": q2_deepest_any[0],
        "deepest_dir_path": q2_deepest_any[1],
    }

# ---------------------------------------------------------------- Q5
# Q5: sample 5 of the recent .jsonl's PARENT session dirs; newest file each.
samples = []
for rec in sorted(jsonl_recent,
                  key=lambda r: r["mtime_utc"],
                  reverse=True)[:5]:
    sdir = os.path.dirname(rec["path"])
    newest_name, newest_mt, newest_size = None, None, None
    n_files = 0
    try:
        for e in os.scandir(sdir):
            if e.is_file(follow_symlinks=False):
                n_files += 1
                st = e.stat()
                if newest_mt is None or st.st_mtime > newest_mt:
                    newest_mt, newest_name, newest_size = (
                        st.st_mtime, e.name, st.st_size)
    except OSError:
        err(sdir)
    samples.append({
        "session_dir": sdir,
        "n_files_in_dir": n_files,
        "newest_file_name": newest_name,
        "newest_file_mtime_utc": (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(newest_mt))
            if newest_mt else None),
        "newest_file_size": newest_size,
        "newest_file_age_s": (round(NOW - newest_mt, 3)
                              if newest_mt else None),
        "sampled_jsonl": rec["path"],
    })
res["q5_recent_session_dir_samples"] = {
    "population": ("top 5 session dirs by newest .jsonl mtime, among .jsonl "
                   f"with mtime within {HORIZON_S}s of probe instant"),
    "samples": samples,
}

res["errors"] = errs[:20]
res["error_count"] = len(errs)
res["elapsed_s"] = round(time.time() - T0, 3)

text = json.dumps(res, indent=2, sort_keys=False)
if OUT:
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
print(text)