# Research lane probe: ONNX Runtime execution-provider availability on THIS box.
# Read-only. Loads NO model. Re-verifies the AGENTS.md claim
# "CUDAExecutionProvider is requested but not loadable here -> ['CPUExecutionProvider']".
import sys, os, traceback

print("PYTHON", sys.version.replace("\n", " "), "|", sys.executable)

try:
    import onnxruntime as ort
    print("ORT_VERSION", ort.__version__)
    print("ORT_FILE", ort.__file__)
    print("ORT_AVAILABLE_PROVIDERS", ort.get_available_providers())
    print("ORT_DEVICE", ort.get_device())
except Exception as e:
    print("ORT_IMPORT_FAILED", type(e).__name__, e)
    traceback.print_exc()
    ort = None

if ort is not None:
    # Try to actually BUILD a session with CUDA requested. Use a tiny model built
    # in memory if the onnx helper is present; otherwise skip.
    try:
        import numpy as np
        so = ort.SessionOptions()
        so.log_severity_level = 3
        # minimal identity graph via onnx helper
        import onnx
        from onnx import helper, TensorProto
        g = helper.make_graph(
            [helper.make_node("Identity", ["x"], ["y"])],
            "id", [], [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])],
        )
        m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
        m.ir_version = 8
        raw = m.SerializeToString()
        for prov in (["CUDAExecutionProvider", "CPUExecutionProvider"],
                     ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
                     ["DmlExecutionProvider", "CPUExecutionProvider"],
                     ["OpenVINOExecutionProvider", "CPUExecutionProvider"]):
            try:
                s = ort.InferenceSession(raw, so, providers=prov)
                print("SESSION_REQUESTED", prov, "-> ACTUAL", s.get_providers())
            except Exception as e:
                print("SESSION_REQUESTED", prov, "-> FAILED", type(e).__name__, str(e)[:300])
    except Exception as e:
        print("SESSION_PROBE_SKIPPED", type(e).__name__, e)

for mod in ("onnxruntime_genai", "onnxruntime.capi._pybind_state"):
    try:
        m = __import__(mod, fromlist=["*"])
        v = getattr(m, "__version__", None)
        if v is None:
            try:
                import onnxruntime_genai as og
                v = og.__version__
            except Exception:
                v = "?"
        print("MODULE_OK", mod, v)
    except Exception as e:
        print("MODULE_FAIL", mod, type(e).__name__, str(e)[:200])

try:
    import torch
    print("TORCH_VERSION", torch.__version__)
    print("TORCH_CUDA_BUILD", torch.version.cuda)
    print("TORCH_CUDA_IS_AVAILABLE", torch.cuda.is_available())
    print("TORCH_CUDA_DEVICE_COUNT", torch.cuda.device_count())
    if torch.cuda.is_available():
        print("TORCH_CUDA_DEVICE0", torch.cuda.get_device_name(0),
              "cc=%s.%s" % torch.cuda.get_device_capability(0))
except Exception as e:
    print("TORCH_IMPORT_FAILED", type(e).__name__, str(e)[:300])
