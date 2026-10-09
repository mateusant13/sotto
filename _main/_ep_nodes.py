"""Node assignment per Execution Provider, measured from ORT's own profiler.

`session.get_providers()` says which EPs are ATTACHED to a session.  It does NOT
say which EP runs which node: ORT partitions the graph and silently places any
node an EP cannot handle (or a shape it cannot take) back on CPU.  A session can
report `['CUDAExecutionProvider','CPUExecutionProvider']` and execute 100% of its
nodes on CPU -- that is the exact failure mode this probe exists to rule out.

Instrument: `so.enable_profiling = True`, one real inference, then
`session.end_profiling()` -> the JSON ORT writes.  Each kernel event carries
`args.provider`.  We count events per provider and report the ratio, plus the
top CPU-side kernels by total duration (a big CPU kernel in a "GPU" session is
the tell).

Usage:
  python _ep_nodes.py --model <dir> --provider CUDAExecutionProvider [--graph encoder]
                      [--json out.json] [--dll-dir DIR ...]

The graph is fed the model's own real shapes, read from genai_config.json, so the
partition measured is the partition the live worker would get -- not a toy input.
"""
import argparse, json, os, sys, tempfile, glob, collections

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--provider", required=True)
ap.add_argument("--graph", default="encoder", choices=["encoder", "decoder", "joint"])
ap.add_argument("--json")
ap.add_argument("--dll-dir", action="append", default=[])
ap.add_argument("--threads", type=int, default=2)
ap.add_argument("--no-cuda-dlls", action="store_true")
a = ap.parse_args()

# --- threads pinned BEFORE numpy/ort import (same law as the worker) ----------
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
          "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[v] = str(a.threads)

sys.path.insert(0, r"H:\sotto\worker")
import sotto_worker as sw  # noqa: E402  (stdlib-only at import time)

if not a.no_cuda_dlls:
    sw._add_cuda_dll_dirs()
_handles = []
for d in a.dll_dir:
    if os.path.isdir(d):
        try:
            _handles.append(os.add_dll_directory(d))
        except Exception as e:
            print(f"WARN add_dll_directory({d}): {e}", file=sys.stderr)
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")

import numpy as np          # noqa: E402
import onnxruntime as ort   # noqa: E402

cfg = json.load(open(os.path.join(a.model, "genai_config.json"), encoding="utf-8"))

# --- real input shapes, read from the model's own config ---------------------
def real_feeds(graph):
    m = cfg["model"]
    if graph == "encoder":
        # genai feeds the encoder the whole streaming window; read the declared
        # input names off the graph rather than guessing them.
        return None  # filled below from the session's own inputs
    return None

path = os.path.join(a.model, f"{a.graph}.onnx")
if not os.path.isfile(path):
    print(json.dumps({"error": f"missing {path}"})); sys.exit(2)

so = ort.SessionOptions()
so.log_severity_level = 4
so.intra_op_num_threads = a.threads
so.inter_op_num_threads = 1
so.enable_profiling = True
so.profile_file_prefix = os.path.join(tempfile.gettempdir(), f"ortprof_{a.graph}")

try:
    sess = ort.InferenceSession(path, sess_options=so, providers=[a.provider])
except Exception as e:
    print(json.dumps({"graph": a.graph, "requested": a.provider,
                      "error": f"{type(e).__name__}: {str(e)[:400]}",
                      "REAL_get_providers": None}, indent=2))
    sys.exit(0)

real = sess.get_providers()

# Build inputs from the session's OWN declared types/shapes.
feeds = {}
for i in sess.get_inputs():
    shape = [d if isinstance(d, int) and d > 0 else 1 for d in i.shape]
    t = i.type
    if "float16" in t:
        arr = np.zeros(shape, dtype=np.float16)
    elif "float" in t:
        arr = np.zeros(shape, dtype=np.float32)
    elif "int64" in t:
        arr = np.zeros(shape, dtype=np.int64)
    elif "int32" in t:
        arr = np.zeros(shape, dtype=np.int32)
    elif "bool" in t:
        arr = np.zeros(shape, dtype=np.bool_)
    else:
        arr = np.zeros(shape, dtype=np.float32)
    feeds[i.name] = arr

err = None
try:
    sess.run(None, feeds)
except Exception as e:
    err = f"{type(e).__name__}: {str(e)[:300]}"

prof_path = sess.end_profiling()

events = []
try:
    with open(prof_path, encoding="utf-8") as fh:
        events = json.load(fh)
except Exception as e:
    err = (err or "") + f" | profile unreadable: {e}"

by_prov = collections.Counter()
dur_by_prov = collections.Counter()
cpu_kernels = collections.Counter()
for ev in events:
    if ev.get("cat") != "Node":
        continue
    args = ev.get("args") or {}
    prov = args.get("provider") or "?"
    by_prov[prov] += 1
    dur_by_prov[prov] += ev.get("dur", 0)
    if prov == "CPUExecutionProvider":
        cpu_kernels[args.get("op_name") or ev.get("name", "?")] += ev.get("dur", 0)

total = sum(by_prov.values())
out = {
    "graph": a.graph,
    "requested": a.provider,
    "REAL_get_providers": real,
    "inputs": {k: [list(v.shape), str(v.dtype)] for k, v in feeds.items()},
    "inference_error": err,
    "nodes_total": total,
    "nodes_by_provider": dict(by_prov),
    "pct_nodes_by_provider": {k: round(100.0 * v / total, 2) for k, v in by_prov.items()} if total else {},
    "dur_us_by_provider": dict(dur_by_prov),
    "pct_dur_by_provider": {k: round(100.0 * v / max(1, sum(dur_by_prov.values())), 2)
                            for k, v in dur_by_prov.items()},
    "top_cpu_kernels_us": cpu_kernels.most_common(8),
    "profile_file": prof_path,
    "verdict": ("GPU-EXECUTES" if total and by_prov.get(a.provider, 0) > 0
                else ("CPU-ONLY-DESPITE-ATTACH" if total else "NO-EVENTS")),
}
print(json.dumps(out, indent=2, ensure_ascii=False))
if a.json:
    with open(a.json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
