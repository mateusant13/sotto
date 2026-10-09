"""What IS a lane in the new tree? Basename distribution per depth, and the
within-horizon set. Decides option (a) vs (b) on measurement, not assumption."""
import os, time, collections, datetime

NEW = r"C:\Users\Administrador\.minimax\v2\sessions"
HORIZON = 3600.0

names_by_depth = collections.defaultdict(collections.Counter)
# for each depth: first path segment class (dir name shape)
shape_by_depth = collections.defaultdict(collections.Counter)
now = time.time()
cutoff = now - HORIZON
within = []
stat_failures = collections.Counter()
session_dir_filecensus = collections.Counter()

for dirpath, dirnames, filenames in os.walk(NEW):
    rel = os.path.relpath(dirpath, NEW)
    depth = 0 if rel == "." else rel.count(os.sep) + 1
    for fn in filenames:
        if not fn.endswith(".jsonl"):
            continue
        base = fn[:-len(".jsonl")]
        # classify the basename, not its literal
        if base == "messages":
            cls = "messages"
        elif base.startswith("user-message-locators"):
            cls = "user-message-locators"
        elif base.startswith("g") and "ctx_" in base:
            cls = "snapshot(g*--ctx_*)"
        else:
            cls = f"OTHER:{base[:40]}"
        names_by_depth[depth][cls] += 1
        fp = os.path.join(dirpath, fn)
        try:
            st = os.stat(fp)
        except OSError as e:
            # LOUD: a file we cannot stat cannot be dated, so it is silently
            # absent from `within` -- counted here so the caller can audit it.
            stat_failures[f"{type(e).__name__}:{e}"] += 1
            continue
        if st.st_mtime >= cutoff:
            within.append((st.st_mtime, rel, fn, cls))
    # census of what lives directly inside a depth-4 session dir
    if depth == 4:
        for fn in filenames:
            session_dir_filecensus[fn if not fn.endswith(".jsonl") else fn[:-6] + ".jsonl"] += 1
        for dn in dirnames:
            session_dir_filecensus["DIR::" + dn] += 1

print("=== BASENAME CLASS HISTOGRAM PER DEPTH (new tree)")
for d in sorted(names_by_depth):
    print(f"  DEPTH {d}: {dict(names_by_depth[d].most_common(12))}")

print()
print(f"=== CONTENT CENSUS DIRECTLY INSIDE DEPTH-4 SESSION DIRS (top 20)")
for k, v in session_dir_filecensus.most_common(20):
    print(f"  {v:6d}  {k}")

print()
print(f"=== WITHIN {HORIZON}s HORIZON (cutoff={datetime.datetime.utcfromtimestamp(cutoff).isoformat()}Z)")
print(f"  COUNT: {len(within)}")
print(f"  POPULATION(jsonl seen in walk): {sum(sum(c.values()) for c in names_by_depth.values())}")
print(f"  STAT_FAILURES: {sum(stat_failures.values())} {dict(stat_failures)}")
cls_count = collections.Counter(c for _, _, _, c in within)
print(f"  CLASS BREAKDOWN: {dict(cls_count)}")
depth_count = collections.Counter(r.count(os.sep) + 1 for _, r, _, _ in within)
print(f"  PARENT-DEPTH BREAKDOWN: {dict(sorted(depth_count.items()))}")
print("  NEWEST 15 WITHIN HORIZON:")
for mtime, rel, fn, cls in sorted(within, reverse=True)[:15]:
    print(f"    {datetime.datetime.utcfromtimestamp(mtime).isoformat()}Z  d={rel.count(os.sep)+1}  [{cls}]  {rel}\\{fn}")

print()
print("=== SESSION DIRS WITHIN HORIZON (parent dir mtime >= cutoff)")
live_sess = set()
for mtime, rel, fn, cls in within:
    live_sess.add(os.path.dirname(rel) if os.sep in rel else rel)
print(f"  LIVE SESSION DIRS TOUCHED WITHIN HORIZON: {len(live_sess)}")
for s in sorted(live_sess)[:10]:
    print(f"    {s}")