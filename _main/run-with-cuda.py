#!/usr/bin/env python
"""Run a Python script with the NVIDIA CUDA/cuDNN DLL directories on PATH.

Why this exists
---------------
onnxruntime-gpu 1.30.0 is built against CUDA 13.0 (its own words:
"CUDA version used in build: 13.0"). It dlopens
`onnxruntime/capi/onnxruntime_providers_cuda.dll`, whose imports include
`cublasLt64_13.dll`. Those DLLs ship with the `nvidia-cublas` /
`nvidia-cudnn-cu13` wheels under `<site-packages>/nvidia/...`, which is NOT on
PATH. The provider therefore fails to load with

    Error loading "...onnxruntime_providers_cuda.dll" which depends on
    "cublasLt64_13.dll" which is missing. (Error 126)

and onnxruntime silently continues on CPUExecutionProvider.

The fix is the one the ONNX Runtime CUDA Execution Provider page names in the
same sentence as that error ("make sure they're in the PATH"), plus its
documented `onnxruntime.preload_dlls(directory="")` helper. Nothing is
installed; the wheels are already present.

MEASURED 2026-10-06: setting PATH alone is sufficient to make the CUDA
provider load; preload_dlls alone is also sufficient. Both are applied here so
the launcher works whether or not the caller already preloads.

Usage
-----
    python H:\\sotto\\_main\\run-with-cuda.py <script.py> [args...]

Scope: this file touches nothing outside the running process. It does not set a
machine- or user-level environment variable and does not write to PATH
permanently, so it cannot leak a cu13 tree into another project's environment.
"""

import os
import runpy
import sys


def _cuda_bin_dirs() -> list:
    """Every directory under site-packages/nvidia that actually holds DLLs.

    The layout moved between wheel generations -- cu13 wheels use
    `nvidia/cu13/bin/x86_64/`, older ones `nvidia/<pkg>/lib/`. Scan rather than
    hard-code a name so this keeps working across upgrades.
    """
    import site

    roots = []
    try:
        roots.extend(site.getsitepackages())
    except AttributeError:  # virtualenv without the helper
        pass
    try:
        roots.append(site.getusersitepackages())
    except Exception:
        pass

    found = []
    for root in roots:
        nvidia = os.path.join(root, "nvidia")
        if not os.path.isdir(nvidia):
            continue
        for dirpath, _dirnames, filenames in os.walk(nvidia):
            if any(f.lower().endswith((".dll", ".so")) for f in filenames):
                found.append(dirpath)
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    target = sys.argv[1]
    sys.argv = sys.argv[1:]

    dirs = _cuda_bin_dirs()
    existing = os.environ.get("PATH", "").split(os.pathsep)
    for d in dirs:
        if d not in existing:
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")

    # Documented helper: load CUDA/cuDNN from the NVIDIA site packages by hand.
    # Best-effort -- the PATH entries above already cover the case where the
    # installed onnxruntime build predates preload_dlls.
    try:
        import onnxruntime

        if hasattr(onnxruntime, "preload_dlls"):
            onnxruntime.preload_dlls(directory="")
    except Exception:
        pass

    sys.path.insert(0, os.path.dirname(os.path.abspath(target)))
    runpy.run_path(target, run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())