"""Does the CUDA arm of the diarization stack ACTUALLY put the graph on the GPU?

The sherpa-onnx arm is the primary evidence (measured RTF 1.5745 on CUDA vs
0.2571 on CPU, same file, same arm). This probe answers the follow-up question
that number raises: was the GPU used at all, or did ORT silently fall back?

Method, and it is the SAME weights sherpa loads (no re-export, no re-quantize):
  * open each ONNX with onnxruntime directly, once per provider;
  * read `sess.get_providers()` -- what the session actually HOLDS, not what was
    requested (ORT drops a provider it cannot initialise);
  * set log_severity_level=1 (VERBOSE) and COUNT the per-node placement lines
    `... placed on <Provider>` -- the definitive per-node answer;
  * time N runs on a zeros input of the model's own declared shape.

A provider that is merely "available" is not evidence it was used: the positive
control is the node-placement census, and it has a negative control built in --
if every node reads CPUExecutionProvider, the CUDA run is a fallback and the
RTF comparison above is not a GPU measurement.
"""
import argparse
import json
import os
import sys
import sysconfig
import time

# purelib IS site-packages; see the note in _diar-cuda-launch.py for why
# deriving it from os.__file__ silently names a nonexistent directory.
PKG = sysconfig.get_paths()["purelib"]
CUDA_DLL_DIRS = [
    os.path.join(PKG, "nvidia", "cublas", "bin"),
    os.path.join(PKG, "torch", "lib"),
]


def add_cuda_dll_dirs():
    """The handles MUST be kept alive: os.add_dll_directory() removes the
    directory again when its return value is garbage-collected."""
    kept = []
    for d in CUDA_DLL_DIRS:
        if os.path.isdir(d):
            kept.append(os.add_dll_directory(d))
    os.environ["PATH"] = os.pathsep.join(
        [d for d in CUDA_DLL_DIRS if os.path.isdir(d)]
        + [os.environ.get("PATH", "")]
    )
    return kept


def placements(log_path):
    """count '<name> placed on <Provider>' from an ORT VERBOSE log"""
    import re
    counts = {}
    pat = re.compile(r"\bplaced on (\w+ExecutionProvider)\b")
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = pat.search(line)
            if m:
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def probe(model, provider, runs, verbose=False):
    """NOTE: onnxruntime 1.30.0 has NO SessionOptions.log_file_path (measured:
    AttributeError). The VERBOSE placement lines go to STDERR, so the census is
    taken by redirecting this process' stderr to a file with --verbose and
    parsing it afterwards with --parse-log.

    NOTE 2, and it bounds what this probe can say: this is the PIP onnxruntime
    1.30.0, NOT the runtime sherpa-onnx 1.13.4 bundles (its own ORT is 1.24.4,
    per the API-version error). The placement census below therefore describes
    1.30.0. The sherpa GPU question is settled by nvidia-smi during the real
    sherpa run, not by this file.
    """
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = 2
    so.log_severity_level = 1 if verbose else 3
    try:
        sess = ort.InferenceSession(model, so, providers=[provider])
    except Exception as exc:                       # exact error IS the result
        return {"model": os.path.basename(model), "provider_requested": provider,
                "load_error": "%s: %s" % (type(exc).__name__, exc)}
    held = sess.get_providers()
    feed = {}
    for i in sess.get_inputs():
        shape = [d if isinstance(d, int) else 1 for d in i.shape]
        feed[i.name] = __import__("numpy").zeros(shape, dtype=__import__("numpy").float32)
    sess.run(None, feed)                            # warm-up, not timed
    t0 = time.perf_counter()
    for _ in range(runs):
        sess.run(None, feed)
    wall = time.perf_counter() - t0
    return {
        "model": os.path.basename(model),
        "model_bytes": os.path.getsize(model),
        "provider_requested": provider,
        "providers_held": held,
        "inputs": [{"name": i.name, "shape": i.shape, "type": i.type} for i in sess.get_inputs()],
        "runs": runs,
        "wall_s": round(wall, 4),
        "ms_per_run": round(1000 * wall / runs, 3),
        "node_placements": placements(log_path),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", default=r"_main\diar-models\sherpa-onnx-pyannote-segmentation-3-0\model.onnx")
    ap.add_argument("--emb", default=r"_main\diar-models\3dspeaker_eres2net_base_16k.onnx")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--out", default=r"_main\_diar-provider-probe.json")
    ap.add_argument("--logdir", default=r"_main\diar-provider-logs")
    args = ap.parse_args()

    add_cuda_dll_dirs()
    os.makedirs(args.logdir, exist_ok=True)

    import onnxruntime as ort
    print("onnxruntime %s" % ort.__version__)
    print("available providers: %s" % ort.get_available_providers())

    results = []
    for tag, model in (("seg", args.seg), ("emb", args.emb)):
        for provider in ("CPUExecutionProvider", "CUDAExecutionProvider"):
            logp = os.path.join(args.logdir, "%s-%s.log" % (tag, provider.split("Execution")[0].lower()))
            r = probe(model, provider, args.runs, logp)
            r["tag"] = tag
            results.append(r)
            if "load_error" in r:
                print("%-4s %-22s LOAD ERROR  %s" % (tag, provider, r["load_error"]))
            else:
                print("%-4s %-22s held=%-24s %8.3f ms/run  placements=%s"
                      % (tag, provider, ",".join(p.replace("ExecutionProvider", "") for p in r["providers_held"]),
                         r["ms_per_run"], r["node_placements"]))

    out = {"instrument": "_diar-provider-probe.py",
           "ort_version": ort.__version__,
           "available_providers": ort.get_available_providers(),
           "runs": args.runs, "results": results}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
