"""Where the worker's boot goes, measured in fresh processes, one phase at a time.

    python worker/_probe/boot-phases.py [importtorch|notorch|probe|encoder|og|all]

Each phase prints `PHASE name_s=<seconds>` on stdout so a receipt can quote the
number instead of a memory. `all` runs the phases in the worker's own order in
ONE process (the shape that actually ships); the single-phase modes answer "what
does THIS phase cost", which is what a change has to move.

Read-only: no audio device, no caption, no window.
"""
from __future__ import annotations

import json
import os
import site
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.dirname(HERE)
MODEL = os.path.join(WORKER, "models", "nemotron-3.5-asr-ptbr-onnx-int4")
SITE_BASES = list(site.getsitepackages())


def _out(name, t0):
    print("PHASE %s_s=%.3f" % (name, time.time() - t0), flush=True)


def nvidia_dirs():
    dirs = []
    for base in SITE_BASES:
        nv = os.path.join(base, "nvidia")
        if not os.path.isdir(nv):
            continue
        for root, subdirs, files in os.walk(nv):
            if root[len(nv):].count(os.sep) > 3:
                subdirs[:] = []
                continue
            if any(f.lower().endswith((".dll", ".so")) for f in files):
                dirs.append(root)
    return dirs


def add_dirs(dirs):
    handles = []
    for d in dirs:
        if os.path.isdir(d):
            try:
                handles.append(os.add_dll_directory(d))
            except OSError:
                pass
            if d not in os.environ.get("PATH", "").split(os.pathsep):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    return handles


def torch_lib_by_import():
    t0 = time.time()
    import torch  # noqa: F401  -- the thing under test

    _out("import_torch", t0)
    return os.path.join(os.path.dirname(torch.__file__), "lib")


def torch_lib_by_spec():
    import importlib.util

    spec = importlib.util.find_spec("torch")
    if spec is None or not spec.origin:
        return None
    return os.path.join(os.path.dirname(spec.origin), "lib")


def session(path, providers, opts=None):
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.intra_op_num_threads = 4
    so.inter_op_num_threads = 1
    for k, v in (opts or {}).items():
        setattr(so, k, v)
    return ort.InferenceSession(path, so, providers=providers)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    print("MODE", mode, "MODEL", os.path.basename(MODEL), flush=True)

    if mode == "importtorch":
        t0 = time.time()
        lib = torch_lib_by_import()
        print("torch_lib", lib, flush=True)
        return 0
    if mode == "notorch":
        t0 = time.time()
        dirs = nvidia_dirs()
        add_dirs(dirs)
        _out("cuda_dirs_no_torch", t0)
        return 0

    entries = [("CUDAExecutionProvider", {"arena_extend_strategy": "kSameAsRequested"}),
               "CPUExecutionProvider"]

    if mode == "probe":
        t0 = time.time()
        s = session(os.path.join(MODEL, "joint.onnx"), entries)
        _out("probe_joint_cuda", t0)
        print("providers", s.get_providers(), flush=True)
        return 0
    if mode in ("cuda_nvidia_only", "cuda_spec_torch", "cuda_torch_import"):
        t0 = time.time()
        if mode == "cuda_torch_import":
            lib = torch_lib_by_import()
        elif mode == "cuda_spec_torch":
            lib = torch_lib_by_spec()
        else:
            lib = None
        dirs = ([lib] if lib else []) + nvidia_dirs()
        add_dirs(dirs)
        _out("cuda_dirs", t0)
        t0 = time.time()
        s = session(os.path.join(MODEL, "joint.onnx"), entries)
        _out("probe_joint_cuda", t0)
        print("providers", s.get_providers(), "dirs", len(dirs), flush=True)
        t0 = time.time()
        session(os.path.join(MODEL, "encoder.onnx"), entries)
        _out("sess_encoder", t0)
        return 0
    if mode == "encoder":
        t0 = time.time()
        s = session(os.path.join(MODEL, "encoder.onnx"), entries)
        _out("encoder_cuda", t0)
        print("providers", s.get_providers(), flush=True)
        return 0
    if mode == "encoder_cpu":
        t0 = time.time()
        s = session(os.path.join(MODEL, "encoder.onnx"), ["CPUExecutionProvider"])
        _out("encoder_cpu", t0)
        return 0
    if mode == "encoder_basic":
        import onnxruntime as ort

        t0 = time.time()
        s = session(os.path.join(MODEL, "encoder.onnx"), entries,
                    {"graph_optimization_level": ort.GraphOptimizationLevel.ORT_ENABLE_BASIC})
        _out("encoder_cuda_basic", t0)
        return 0
    if mode == "og":
        t0 = time.time()
        import onnxruntime_genai as og

        m = og.Model(MODEL)
        _out("og_model", t0)
        t0 = time.time()
        sp = og.StreamingProcessor(m)
        _out("og_processor", t0)
        print("og", type(sp).__name__, flush=True)
        return 0

    # ── `all`: the shipped order, in one process ──────────────────────────────
    t0 = time.time()
    lib_torch = torch_lib_by_spec()
    dirs = ([lib_torch] if lib_torch else []) + nvidia_dirs()
    add_dirs(dirs)
    _out("cuda_dirs_spec", t0)

    t0 = time.time()
    s = session(os.path.join(MODEL, "joint.onnx"), entries)
    _out("probe_joint_cuda", t0)
    print("probe_providers", s.get_providers(), flush=True)
    del s

    for name in ("encoder", "decoder", "joint"):
        t0 = time.time()
        session(os.path.join(MODEL, name + ".onnx"), entries)
        _out("sess_" + name, t0)

    t0 = time.time()
    import onnxruntime_genai as og

    m = og.Model(MODEL)
    _out("og_model", t0)
    t0 = time.time()
    og.StreamingProcessor(m)
    _out("og_processor", t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
