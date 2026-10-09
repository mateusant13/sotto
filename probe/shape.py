"""Measure the REAL shape of the live session tree. No assumptions, no literals."""
import os, sys, time, collections, json

ROOTS = {
    "NEW_MINIMAX": r"C:\Users\Administrador\.minimax\v2\sessions",
    "OLD_OMP": r"C:\Users\Administrador\.omp\agent\sessions",
}

for label, root in ROOTS.items():
    print(f"=== {label} :: {root}")
    print(f"EXISTS: {os.path.isdir(root)}")
    if not os.path.isdir(root):
        continue
    stat_failures = collections.Counter()
    t0 = time.perf_counter()
    dir_hist = collections.Counter()
    jsonl_hist = collections.Counter()
    jsonl_total = 0
    newest_any = 0.0
    samples = collections.defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dir_hist[depth] += 1
        for fn in filenames:
            if fn.endswith(".jsonl"):
                jsonl_total += 1
                jsonl_hist[depth] += 1
                if len(samples[depth]) < 6:
                    samples[depth].append(os.path.join(rel, fn))
                fp = os.path.join(dirpath, fn)
                try:
                    newest_any = max(newest_any, os.stat(fp).st_mtime)
                except OSError as e:
                    # LOUD: counted and printed, never silently dropped.
                    stat_failures[f"{type(e).__name__}:{e}"] += 1
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"WALK_MS: {elapsed:.1f}")
    print(f"DEPTH_HISTOGRAM_DIRS: {dict(sorted(dir_hist.items()))}")
    print(f"DEPTH_HISTOGRAM_JSONL: {dict(sorted(jsonl_hist.items()))}")
    print(f"RECURSIVE_JSONL_TOTAL: {jsonl_total}")
    print(f"STAT_FAILURES: {sum(stat_failures.values())} {dict(stat_failures)}")
    print(f"NEWEST_JSONL_MTIME: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(newest_any)) if newest_any else 'none'}")
    for d in sorted(samples):
        for s in samples[d]:
            print(f"  SAMPLE[d={d}]: {s}")
    try:
        kids = sorted(p.name for p in os.scandir(root) if p.is_dir())
        print(f"IMMEDIATE_CHILD_DIRS({len(kids)}): {kids[:10]}")
    except OSError as e:
        print(f"IMMEDIATE_CHILD_DIRS_ERR: {type(e).__name__}: {e}")
    print()