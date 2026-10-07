import subprocess, sys, time, os, threading

CMD = [sys.executable, r"H:\sotto\worker\sotto_worker.py",
       "--selftest", "--audio", r"H:\sotto\worker\assets\sample1.flac"]

tag = sys.argv[1]
outdir = r"H:\sotto-wt\e2e-rerun\_main"

import psutil  # hard dependency: no silent fallback, a missing psutil must be loud

peak = {"bytes": 0}
# Counters so a swallowed condition can be asserted on by the caller, never discarded.
lost = {"children": 0, "exit": 0}


def sample_rss(proc):
    """Poll RSS of proc+children until it exits. Peak never decreases.

    A child that vanishes mid-sample is EXPECTED (workers exit); it is counted in
    lost['children'] and printed, not silently passed over: the cost is that one
    child's RSS is absent from that single sample, not from the run.
    Process exit mid-sample is the loop terminator, counted in lost['exit'].
    """
    try:
        p = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        lost["exit"] += 1
        print(f"[probe] process {proc.pid} already gone before first sample", file=sys.stderr)
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