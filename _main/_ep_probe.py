"""EP probe — what does InferenceSession.get_providers() REALLY say?

Usage:
  python _ep_probe.py <model.onnx> [provider ...]        # naive (no DLL plumbing)
  python _ep_probe.py --cuda-dlls <model.onnx> [prov...] # with worker's _add_cuda_dll_dirs
  python _ep_probe.py --census                            # what is installed here

get_available_providers() = what the PACKAGE supports.
get_providers()           = what the SESSION actually uses. Only the second counts.
"""
import os
import sys
import json
import time

args = sys.argv[1:]
mode = "naive"
if args and args[0] == "--census":
    import onnxruntime as ort
    print(json.dumps({
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "ort_version": ort.__version__,
        "ort_file": ort.__file__,
        "available": list(ort.get_available_providers()),
    }, indent=2))
    try:
        import onnxruntime_genai as og
        print(json.dumps({"ort_genai": og.__version__}))
    except Exception as e:
        print(json.dumps({"ort_genai": f"ABSENT {type(e).__name__}: {e}"}))
    sys.exit(0)

if args and args[0] == "--cuda-dlls":
    mode = "worker-plumbing"
    args = args[1:]
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "worker"))
    try:
        import sotto_worker
        sotto_worker._add_cuda_dll_dirs()
        print("CUDA_DLL_DIRS: applied", file=sys.stderr)
    except Exception as e:
        print(f"CUDA_DLL_DIRS: FAILED {type(e).__name__}: {e}", file=sys.stderr)

model = args[0]
requested = args[1:] or ["CPUExecutionProvider"]

import onnxruntime as ort

available = list(ort.get_available_providers())
so = ort.SessionOptions()
so.log_severity_level = 4
so.intra_op_num_threads = 2
so.inter_op_num_threads = 1

t0 = time.perf_counter()
err = None
try:
    sess = ort.InferenceSession(model, so, providers=requested)
    real = list(sess.get_providers())
except Exception as exc:
    sess = None
    real = None
    err = f"{type(exc).__name__}: {str(exc)[:400]}"
t1 = time.perf_counter()

print(json.dumps({
    "mode": mode,
    "model": os.path.basename(model),
    "requested": requested,
    "available": available,
    "REAL_get_providers": real,
    "error": err,
    "load_s": round(t1 - t0, 3),
}, indent=2))
