#!/usr/bin/env python3
"""_qwen-cuda-init-probe.py -- WHY does CUDAExecutionProvider not bind?

The hardware probe found the contradiction AGENTS.md predicted: ORT 1.30.0
ADVERTISES ['TensorrtExecutionProvider','CUDAExecutionProvider',
'CPUExecutionProvider'] but a forced-CUDA session binds ['CPUExecutionProvider'].
A provider list is a claim; a bound session is the measurement.

This probe collects the RAW cause, not a summary:
  * which onnxruntime distribution is installed (CPU wheel vs onnxruntime-gpu)
  * the ORT session-creation warning/error text with log_severity_level=1
  * CUDA / cuDNN / cuBLAS DLL resolution (the usual cause on Windows:
    a provider DLL present but its CUDA dependency missing on PATH)
  * whether nvidia-smi + the toolkit exist, and where
  * a trtexec/TensorRT presence check (the OTHER advertised provider)

No downloads, no installs, no audio device, no window. Read-only.
Run: cmd /c "python _main\_qwen-cuda-init-probe.py > _main\_qwen-cuda-init-probe.log 2>&1"
"""

from __future__ import annotations

import ctypes
import glob
import importlib.metadata as md
import os
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000

# MEASURED encoding trap: creating an ONNX Runtime InferenceSession flips the
# Windows CRT stdout handle to UTF-16 (_O_U16TEXT), so every print AFTER the
# session lands as UTF-16LE and `cmd /c "python ... > log 2>&1"` produces a file
# that is UTF-16 -- unreadable as text by ordinary tools. Keeping our own
# handle open on the original fd and writing the report through it avoids the
# redirect entirely.
try:
    _STDOUT_FD = os.dup(1)
except OSError:
    _STDOUT_FD = None


class Report:
    """Tee the report to stdout AND, if given, a UTF-8 file we own.

    We open the file ourselves instead of relying on shell redirection because
    ORT changes the mode of fd 1 (see above); a handle Python owns keeps its
    own encoding for the whole run.
    """

    def __init__(self, path: str | None) -> None:
        self.fh = open(path, "w", encoding="utf-8", errors="replace") if path else None

    def __call__(self, *args, **kw) -> None:
        line = " ".join(str(a) for a in args)
        print(line, **kw)
        if self.fh:
            self.fh.write(line + "\n")
            self.fh.flush()

    def close(self) -> None:
        if self.fh:
            self.fh.close()


def force_utf8_stdout() -> None:
    """Best-effort recovery of stdout after the ORT CRT mode flip."""
    try:
        ctypes.windll.msvcrt._setmode(1, os.O_TEXT)
    except Exception:
        try:
            ctypes.windll.ucrtbase._setmode(1, os.O_TEXT)
        except Exception:
            pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# The report sink. Module __getattr__ hands it out under the name `p`, so the
# flat script below and the helper functions both write through the same tee.
_REPORT: Report | None = None


def __getattr__(name: str):
    if name == "p":
        assert _REPORT is not None, "report sink not initialised"
        return _REPORT
    raise AttributeError(name)


def hr(t: str) -> None:
    p()
    p("=" * 74)
    p(t)
    p("=" * 74)


def run(cmd: list[str], timeout: int = 25) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              creationflags=CREATE_NO_WINDOW)
        return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()
    except FileNotFoundError:
        return 127, "NOT FOUND on PATH"
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


_REPORT = Report(sys.argv[1] if len(sys.argv) > 1 else None)
p = _REPORT  # noqa: E741 -- the report sink, used by every line below and by hr()


hr("1. WHICH ONNXRUNTIME DISTRIBUTION IS INSTALLED")
try:
    dist = md.distribution("onnxruntime")
    p(f"  name          : {dist.metadata['Name']}")
    p(f"  version       : {dist.version}")
    try:
        p(f"  installer     : {dist.read_text('INSTALLER')!r}")
    except Exception:
        pass
    try:
        p(f"  direct_url    : {dist.read_text('direct_url.json')}")
    except Exception:
        p("  direct_url    : (none -- installed from an index, not a local wheel)")
except Exception as exc:  # noqa: BLE001
    p(f"  metadata FAILED: {exc}")

# The distinguishing fact: onnxruntime (CPU) vs onnxruntime-gpu (CUDA).
try:
    import onnxruntime as ort
    p(f"  ort.__version__            : {ort.__version__}")
    p(f"  ort.get_available_providers: {ort.get_available_providers()}")
    p(f"  ort.get_device()           : {ort.get_device()}")
    try:
        p(f"  ort.build_info             : {ort.build_info}")
    except Exception as exc:  # noqa: BLE001
        p(f"  ort.build_info             : unavailable ({exc})")
    p(f"  ort module path            : {os.path.dirname(ort.__file__)}")
except Exception as exc:  # noqa: BLE001
    p(f"  onnxruntime import FAILED: {exc}")
    ort = None

hr("2. PROVIDER DLLs SHIPPED BY THE WHEEL (capi/ is where they live)")
if ort is not None:
    capi = os.path.join(os.path.dirname(ort.__file__), "capi")
    p(f"  capi dir: {capi}")
    if os.path.isdir(capi):
        for entry in sorted(os.listdir(capi)):
            full = os.path.join(capi, entry)
            if os.path.isfile(full):
                p(f"    | {entry:<52} {os.path.getsize(full):>12,} B")
    else:
        p("  capi dir ABSENT")

    hr("2b. THE WHEEL'S OWN DEPENDENT-LOAD TEST for the CUDA provider DLL")
    # Windows LoadLibrary on the provider DLL itself: this is the naked cause.
    dll = os.path.join(capi, "onnxruntime_providers_cuda.dll")
    if os.path.isfile(dll):
        try:
            ctypes.WinDLL(dll)
            p(f"  LoadLibrary('{os.path.basename(dll)}') -> OK")
        except OSError as exc:
            p(f"  LoadLibrary('{os.path.basename(dll)}') -> FAILED")
            p(f"    winerror={getattr(exc, 'winerror', '?')} msg={exc}")
    else:
        p(f"  {os.path.basename(dll)} NOT SHIPPED by this wheel")
        p("  -> a CPU-only onnxruntime wheel: CUDA in the provider LIST would be")
        p("     impossible, so the listing above needs re-reading with the DLL names.")

hr("3. FORCE A CUDA SESSION WITH VERBOSE LOGGING (the raw refusal text)")
if ort is not None:
    try:
        import numpy as np
        from onnx import TensorProto, helper

        node = helper.make_node("Add", ["x", "y"], ["z"])
        graph = helper.make_graph(
            [node], "probe",
            [helper.make_tensor_value_info("x", TensorProto.FLOAT, [2]),
             helper.make_tensor_value_info("y", TensorProto.FLOAT, [2])],
            [helper.make_tensor_value_info("z", TensorProto.FLOAT, [2])],
        )
        model_onnx = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])

        so = ort.SessionOptions()
        so.log_severity_level = 1  # VERBOSE: prints the provider init diagnostics
        so.log_verbosity_level = 1
        p("  creating InferenceSession with providers=")
        p("    ['CUDAExecutionProvider','CPUExecutionProvider'], log_severity_level=1")
        p("  --- ORT verbose output begins ---")
        sess = ort.InferenceSession(
            model_onnx.SerializeToString(), so,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        force_utf8_stdout()
        p("  --- ORT verbose output ends ---")
        p(f"  RESULT bound providers : {sess.get_providers()}")
        r = sess.run(None, {"x": np.array([1.0, 2.0], np.float32),
                            "y": np.array([3.0, 4.0], np.float32)})
        p(f"  RESULT add(x,y)        : {[float(v) for v in r[0]]}")
        p(f"  VERDICT: CUDA bound = {sess.get_providers()[:1] == ['CUDAExecutionProvider']}")
    except Exception as exc:  # noqa: BLE001
        p(f"  session FAILED: {type(exc).__name__}: {exc}")

hr("4. THE CUDA TOOLKIT / DRIVER SIDE ON THIS BOX")
rc, out = run(["nvidia-smi"])
p(f"  nvidia-smi rc={rc}")
p("  " + "\n  ".join(out.splitlines()[:12]) if out else "  (no output)")

for env in ("CUDA_PATH", "CUDA_HOME", "CUDA_PATH_V12_3", "CUDA_PATH_V12_8",
            "CUDNN_PATH", "TRT_PATH"):
    p(f"  {env:<16} = {os.environ.get(env, '(unset)')}")

hr("4b. cudart / cublas / cudnn DLLs visible to this process")
# ctypes/WinDLL resolves through PATH + the app dir; this is what ORT sees too.
for name in ("cudart64_12.dll", "cudart64_13.dll", "cudart64_110.dll",
             "cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll",
             "cudnn64_8.dll", "nvinfer_10.dll", "nvinfer_1.dll"):
    try:
        ctypes.WinDLL(name)
        p(f"    {name:<24} LOADABLE")
    except OSError as exc:
        p(f"    {name:<24} not loadable (winerror={getattr(exc, 'winerror', '?')})")

# Also look for them on disk in the usual toolkit locations, so a PATH miss is
# distinguishable from an absent install.
hr("4c. on-disk search for those DLLs (toolkit present but off PATH?)")
roots = [r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA",
         r"C:\Program Files\NVIDIA\CUDNN", r"C:\Windows\System32",
         r"C:\Program Files\NVIDIA Corporation"]
for root in roots:
    if not os.path.isdir(root):
        p(f"  {root}  -> ABSENT")
        continue
    found: list[str] = []
    for pat in ("cudart64_*.dll", "cublas64_*.dll", "cudnn64_*.dll",
                "nvinfer_*.dll", "nvrtc64_*.dll"):
        found += glob.glob(os.path.join(root, "**", pat), recursive=True)[:6]
    p(f"  {root}  -> {len(found)} match(es)")
    for f in found[:14]:
        p(f"      {f}")

_REPORT.close()
