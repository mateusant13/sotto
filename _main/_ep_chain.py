"""Fallback-chain probe — pick the best EP that REALLY initialises, and prove the fallback.

The claim under test, in the product's own terms:
  "at startup the product discovers what the machine has, picks the best EP that
   actually initialises (not the one the package supports), and falls to the next
   if it fails — logging the provider it is REALLY using."

Instrument design, so a green means something:
  * Every level is decided by `InferenceSession.get_providers()`, never by
    `get_available_providers()`.
  * A level that raises, or that initialises but does not appear in
    `get_providers()`, is a FAILED level and the chain moves on.
  * `--force-fail N` makes level N report failure on purpose, so the SAME run
    shows the level that works AND the level that falls (both colours).

Usage:
  python _ep_chain.py --model DIR [--prefer dml,cuda,cpu] [--force-fail 0]
                      [--threads N] [--json OUT]
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.normpath(os.path.join(HERE, "..", "worker"))
sys.path.insert(0, WORKER)
sys.path.insert(0, HERE)

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--prefer", default="auto", help="comma list: dml,cuda,trt,cpu or 'auto'")
ap.add_argument("--force-fail", type=int, default=-1, help="index of level to force-fail")
ap.add_argument("--threads", type=int, default=2)
ap.add_argument("--json", default=None)
args = ap.parse_args()

os.environ["OMP_NUM_THREADS"] = str(args.threads)

import sotto_worker as sw  # noqa: E402
sw._add_cuda_dll_dirs()
import onnxruntime as ort  # noqa: E402

ALIAS = {
    "dml": "DmlExecutionProvider",
    "directml": "DmlExecutionProvider",
    "cuda": "CUDAExecutionProvider",
    "gpu": "CUDAExecutionProvider",
    "trt": "TensorrtExecutionProvider",
    "tensorrt": "TensorrtExecutionProvider",
    "cpu": "CPUExecutionProvider",
}

# The product's preference order, vendor-neutral first (owner's scope change):
# DirectML works on ANY Windows GPU; CUDA/TensorRT is the fast optional path;
# CPU is the floor that must never disappear.
PREFER = ["DmlExecutionProvider", "CUDAExecutionProvider", "TensorrtExecutionProvider",
          "CPUExecutionProvider"]

if args.prefer != "auto":
    PREFER = [ALIAS.get(p.strip().lower(), p.strip()) for p in args.prefer.split(",") if p.strip()]


def pick(model_path, prefer, threads, force_fail=-1):
    """Return (chosen_provider, trace). The trace is the product's startup log line."""
    available = list(ort.get_available_providers())
    trace = []
    chosen = None
    for idx, prov in enumerate(prefer):
        if force_fail == idx:
            trace.append({"level": idx, "provider": prov, "registered": prov in available,
                          "attempted": False, "used": None, "seconds": 0.0,
                          "result": "FORCED-FAIL (instrument: this level was told to fail)"})
            continue
        if prov not in available:
            trace.append({"level": idx, "provider": prov, "registered": False,
                          "attempted": False, "used": None, "seconds": 0.0,
                          "result": "not-registered (package does not offer it)"})
            continue
        so = ort.SessionOptions()
        so.log_severity_level = 4
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        t0 = time.perf_counter()
        try:
            sess = ort.InferenceSession(model_path, so, providers=[prov])
            used = list(sess.get_providers())
            secs = time.perf_counter() - t0
            if prov in used:
                trace.append({"level": idx, "provider": prov, "registered": True,
                              "attempted": True, "used": used, "seconds": round(secs, 3),
                              "result": "OK"})
                chosen = prov
                del sess
                break
            trace.append({"level": idx, "provider": prov, "registered": True,
                          "attempted": True, "used": used, "seconds": round(secs, 3),
                          "result": f"silently-dropped (session fell back to {used})"})
            del sess
        except Exception as exc:
            trace.append({"level": idx, "provider": prov, "registered": True,
                          "attempted": True, "used": None,
                          "seconds": round(time.perf_counter() - t0, 3),
                          "result": f"raised {type(exc).__name__}: {str(exc)[:200]}"})
    return chosen, trace


model_path = os.path.join(args.model, "encoder.onnx")
chosen, trace = pick(model_path, PREFER, args.threads, args.force_fail)

out = {
    "executable": sys.executable,
    "ort_version": ort.__version__,
    "available": list(ort.get_available_providers()),
    "preference_order": PREFER,
    "force_fail_level": args.force_fail,
    "chosen": chosen,
    "trace": trace,
}
# The log line the product would print at startup — built after `available` is known.
out["startup_log_line"] = (
    "EP_CHAIN chosen=" + str(chosen)
    + " available=" + ",".join(out["available"])
    + " trace=" + " > ".join(f"{t['provider']}:{t['result']}" for t in trace)
)
print(json.dumps(out, indent=2, ensure_ascii=False))
if args.json:
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
