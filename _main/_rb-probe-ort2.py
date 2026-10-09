# Research lane probe v2: does the CUDA EP of THIS onnxruntime actually INITIALISE and RUN?
# Read-only: loads a 1-node model built in memory, never a repo model.
import sys, time, os, traceback
import numpy as np
import onnx
from onnx import helper, TensorProto
import onnxruntime as ort

print("ORT_VERSION", ort.__version__, "| file", ort.__file__)
print("AVAILABLE", ort.get_available_providers())
print("DEVICE", ort.get_device())

g = helper.make_graph(
    [helper.make_node("MatMul", ["x", "w"], ["y"])],
    "mm",
    [helper.make_tensor_value_info("x", TensorProto.FLOAT, [64, 64]),
     helper.make_tensor_value_info("w", TensorProto.FLOAT, [64, 64])],
    [helper.make_tensor_value_info("y", TensorProto.FLOAT, [64, 64])],
)
m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 17)])
m.ir_version = 9
raw = m.SerializeToString()

x = np.random.rand(64, 64).astype(np.float32)
w = np.random.rand(64, 64).astype(np.float32)

def try_session(prov, feeds, tag):
    so = ort.SessionOptions()
    so.log_severity_level = 3
    t0 = time.time()
    try:
        s = ort.InferenceSession(raw, so, providers=prov)
        actual = s.get_providers()
        t1 = time.time()
        out = s.run(None, feeds)
        t2 = time.time()
        print("ARM %-14s create=%.3fs ACTUAL=%s run=%.4fs sum=%.6f" %
              (tag, t1 - t0, actual, t2 - t1, float(out[0].sum())))
        return actual
    except Exception as e:
        print("ARM %-14s FAILED %s %s" % (tag, type(e).__name__, str(e)[:400]))
        return None

try_session(["CPUExecutionProvider"], {"x": x, "w": w}, "cpu")
try_session(["CUDAExecutionProvider", "CPUExecutionProvider"], {"x": x, "w": w}, "cuda+fallback")
try_session(["CUDAExecutionProvider"], {"x": x, "w": w}, "cuda-only")

# Where does onnxruntime look for its provider DLLs, and which CUDA libs exist?
import glob
capi = os.path.join(os.path.dirname(ort.__file__), "capi")
print("CAPI_DIR", capi)
for f in sorted(glob.glob(os.path.join(capi, "*.dll"))):
    print("  DLL", os.path.basename(f), os.path.getsize(f))
cuda_bin = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8\bin"
if os.path.isdir(cuda_bin):
    for want in ("cublas64_12.dll", "cublasLt64_12.dll", "cudart64_12.dll", "cudnn64_9.dll"):
        p = os.path.join(cuda_bin, want)
        print("CUDA_BIN", want, "EXISTS" if os.path.exists(p) else "MISSING")
else:
    print("CUDA_BIN absent", cuda_bin)

# onnxruntime-genai: which providers does the installed build expose?
try:
    import onnxruntime_genai as og
    print("OG_VERSION", og.__version__)
    try:
        cfg = og.Config(os.path.join(os.path.dirname(og.__file__), "genai_config.json"))
        print("OG_DEFAULT_PROVIDER", cfg.provider)
    except Exception as e:
        print("OG_DEFAULT_PROVIDER probe skipped:", type(e).__name__, str(e)[:150])
except Exception as e:
    print("OG_FAILED", type(e).__name__, str(e)[:200])
