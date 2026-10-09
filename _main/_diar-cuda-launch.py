"""Launcher: put the CUDA-12 runtime the sherpa provider needs on the DLL search
path, then run _diar-run.py with the remaining argv.

WHY THIS FILE EXISTS (the trap, measured twice):
`os.add_dll_directory()` returns a HANDLE, and the directory is removed again the
moment that handle is garbage-collected. The first two attempts discarded the
return values (`os.add_dll_directory(d)` as a bare statement) and the CUDA
provider kept failing with the IDENTICAL error --

    RuntimeError: OrtSessionOptionsAppendExecutionProvider_Cuda: Failed to load
    shared library ... onnxruntime_providers_cuda.dll which depends on
    "cublasLt64_12.dll" which is missing. (Error 126)

-- even though `cublasLt64_12.dll` is on this box at
site-packages\\nvidia\\cublas\\bin and site-packages\\torch\\lib. The missing
dependency was never missing; the search path was being torn down before use.
Holding the handles in a module-level list is the whole fix.

Note the asymmetry, because it is a real trap for the next lane: the WORKER's
onnxruntime wants CUDA 13 (`nvidia\\cu13\\bin\\x86_64\\cublasLt64_13.dll`, the
directory `worker/sotto_worker.py:277` adds), while sherpa-onnx 1.13.4's BUNDLED
provider wants CUDA 12 (`cublasLt64_12.dll`). Two ORT builds, two CUDA majors.
"""
import os
import runpy
import sys
import sysconfig

# purelib IS the site-packages dir. Do NOT derive it from os.__file__: the naive
# `dirname(dirname(os.__file__))` yields <prefix>\Python311 (os.py lives in
# <prefix>\Python311\Lib), so `join(that, 'site-packages')` names a directory
# that does not exist -- measured: the launcher logged `dll dirs held: 0` and the
# CUDA arm failed with the IDENTICAL cublasLt64_12.dll error it was written to
# fix. The held-directory COUNT is the positive control; keep printing it.
SP = sysconfig.get_paths()["purelib"]
CUDA12_DIRS = [
    os.path.join(SP, "nvidia", "cublas", "bin"),
    os.path.join(SP, "torch", "lib"),
]
CUDA13_DIRS = [os.path.join(SP, "nvidia", "cu13", "bin", "x86_64")]

_HANDLES = []          # KEEP ALIVE -- see the docstring
for _d in CUDA12_DIRS + CUDA13_DIRS:
    if os.path.isdir(_d):
        _HANDLES.append(os.add_dll_directory(_d))
os.environ["PATH"] = os.pathsep.join(
    [d for d in CUDA12_DIRS + CUDA13_DIRS if os.path.isdir(d)]
    + [os.environ.get("PATH", "")]
)

if __name__ == "__main__":
    script = sys.argv[1]
    sys.argv = [os.path.basename(script)] + sys.argv[2:]
    sys.stderr.write("dll dirs held: %d\n" % len(_HANDLES))
    runpy.run_path(script, run_name="__main__")
