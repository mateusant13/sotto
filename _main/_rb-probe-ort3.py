# Research lane probe v3: WHICH DLL DIRECTORY makes the CUDA EP of onnxruntime-gpu 1.30.0 load?
# Read-only. Usage:  python _rb-probe-ort3.py <arm>
#   arm = base | cu13 | all-nvidia | torchlib | cu13+cudnn
import sys, os, time, glob
import numpy as np

SP = r"C:\Program Files\Python311\Lib\site-packages"
ARM = sys.argv[1] if len(sys.argv) > 1 else "base"

DIRS = {
    "cu13":      [os.path.join(SP, r"nvidia\cu13\bin\x86_64")],
    "all-nvidia": [os.path.join(SP, r"nvidia\cu13\bin\x86_64"),
                   os.path.join(SP, r"nvidia\cublas\bin"),
                   os.path.join(SP, r"nvidia\cuda_runtime\bin"),
                   os.path.join(SP, r"nvidia\cudnn\bin"),
                   os.path.join(SP, r"nvidia\cufft\bin"),
                   os.path.join(SP, r"nvidia\curand\bin"),
                   os.path.join(SP, r"nvidia\nvjitlink\bin")],
    "torchlib":  [os.path.join(SP, r"torch\lib")],
    "cu13+cudnn": [os.path.join(SP, r"nvidia\cu13\bin\x86_64"),
                   os.path.join(SP, r"nvidia\cudnn\bin")],
}

extra = DIRS.get(ARM, [])
for d in extra:
    if os.path.isdir(d):
        try:
            os.add_dll_directory(d)
        except Exception as e:
            print("add_dll_directory failed", d, e)
os.environ["PATH"] = os.pathsep.join(extra + [os.environ.get("PATH", "")])

print("ARM", ARM)
print("ADDED", [d for d in extra if os.path.isdir(d)])
print("MISSING_DIRS", [d for d in extra if not os.path.isdir(d)])

import onnxruntime as ort
print("ORT", ort.__version__)
print("AVAILABLE", ort.get_available_providers())

import onnx
from onnx import helper, TensorProto
g = helper.make_graph(
    [helper.make_node("MatMul", ["x", "w"], ["y"])], "mm",
    [helper.make_tensor_value_info("x", TensorProto.FLOAT, [512, 512]),
     helper.make_tensor_value_info("w", TensorProto.FLOAT, [512, 512])],
    [helper.make_tensor_value_info("y", TensorProto.FLOAT, [512, 512])])
m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 17)])
m.ir_version = 9
raw = m.SerializeToString()
x = np.random.rand(512, 512).astype(np.float32); w = np.random.rand(512, 512).astype(np.float32)

so = ort.SessionOptions(); so.log_severity_level = 3
t0 = time.time()
try:
    s = ort.InferenceSession(raw, so, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    print("SESSION_ACTUAL", s.get_providers(), "create=%.3fs" % (time.time() - t0))
    # warm up, then time 50 runs to see whether it is really on the GPU
    s.run(None, {"x": x, "w": w})
    t0 = time.time()
    for _ in range(50):
        s.run(None, {"x": x, "w": w})
    print("50_RUNS_SECONDS %.4f" % (time.time() - t0))
except Exception as e:
    print("SESSION_FAILED", type(e).__name__, str(e)[:600])
