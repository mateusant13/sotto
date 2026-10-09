import subprocess, sys, time, os, threading, psutil

# The EXACT command from PIPELINE-WORKS.md line 26 (no --selftest, plus --max-chunks 40).
CMD = [sys.executable, r"H:\sotto\worker\sotto_worker.py",
       "--audio", r"H:\sotto\worker\assets\sample1.flac", "--max-chunks", "40"]

tag = sys.argv[1]
outdir = r"H:\sotto-wt\e2e-rerun\_main"
peak = {"bytes": 0}
lost = {"children": 0, "exit": 0}


def sample_rss(proc):
    """Poll RSS of proc+children to exit. Peak never decreases.
    Child vanishing mid-sample is EXPECTED; counted in lost['children'] and printed,
    not silently passed over (one sample loses that child's RSS, not the run)."""
    try:
        p = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        lost["exit"] += 1
        print(f"[probe] pid {proc.pid} gone before first sample", file=sys.stderr)
        return
    while True:
        try:
            total = p.memory_info().rss
        except psutil.NoSuchProcess:
            lost["exit"] += 1
            return
        for c in p.children(recursive=True):
            try:
                total += c.memory_info().rss
            except psutil.Error as e:
                lost["children"] += 1
                print(f"[probe] child {c.pid} RSS unavailable: {e!r}", file=sys.stderr)
        if total > peak["bytes"]:
            peak["bytes"] = total
        try:
            if not p.is_running():
                return
        except psutil.NoSuchProcess:
            lost["exit"] += 1
            return
        time.sleep(0.05)


t0 = time.time()
proc = subprocess.Popen(CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
th = threading.Thread(target=sample_rss, args=(proc,), daemon=True)
th.start()
out, err = proc.communicate()
wall = time.time() - t0
th.join(timeout=2.0)
rc = proc.returncode

open(os.path.join(outdir, f"run{tag}.stdout.jsonl"), "wb").write(out)
open(os.path.join(outdir, f"run{tag}.stderr.txt"), "wb").write(err)
open(os.path.join(outdir, f"run{tag}.rc"), "w").write(str(rc))

print(f"TAG={tag}")
print(f"RC={rc}")
print(f"WALL_S={wall:.2f}")
print(f"INDEP_PEAK_RSS_MB={peak['bytes'] / (1024*1024):.1f}")
print(f"LOST_CHILD_SAMPLES={lost['children']}")
print(f"LOST_EXIT_MARKERS={lost['exit']}")
print(f"STDOUT_BYTES={len(out)}")
print(f"STDERR_BYTES={len(err)}")