# GPU diagnostic: WHY did the CUDA provider not load? Prints the wheel, the GPU,
# and ORT's OWN error text (severity=1). Must run under python.exe so stderr is real
# (pythonw has no stderr, which is exactly how the reason gets lost).
import json, os, subprocess, sys, traceback

print("=== python ===")
print(sys.executable)
print(sys.version.split()[0])

print("=== onnxruntime wheel ===")
try:
    import onnxruntime as ort
    print("version   :", ort.__version__)
    print("__file__  :", ort.__file__)
    print("available :", ort.get_available_providers())
except Exception as e:
    print("ort import FAILED:", e)
    ort = None

print("=== is it the GPU build? ===")
for mod in ("onnxruntime", "onnxruntime_gpu"):
    try:
        m = __import__(mod)
        print(" ", mod, "->", getattr(m, "__file__", "?"))
    except Exception as e:
        print(" ", mod, "-> absent:", type(e).__name__)

print("=== packages (pip) ===")
for name in ("onnxruntime", "onnxruntime-gpu", "onnxruntime-directml", "nvidia-cublas-cu12", "nvidia-cudnn-cu12"):
    r = subprocess.run([sys.executable, "-m", "pip", "show", name], capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith("Version:")), "NOT INSTALLED")
    print(f"  {name:<24} {line}")

print("=== GPU (nvidia-smi) ===")
try:
    r = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                       capture_output=True, text=True, timeout=20)
    print("query rc:", r.returncode, r.stdout.strip(), r.stderr.strip()[:200])
    r2 = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=20)
    for l in r2.stdout.splitlines()[:12]:
        print("   ", l)
except Exception as e:
    print("nvidia-smi FAILED:", type(e).__name__, e)

enc = r"H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-int8\encoder.onnx"

print("=== CUDA DLLs on PATH / in the venv ===")
for d in os.environ.get("PATH", "").split(os.pathsep):
    if not d.strip():
        continue
    try:
        hits = [f for f in os.listdir(d) if f.lower().startswith(("cublas", "cudnn", "cudart", "cufft", "nvrtc", "cudart64"))]
        if hits:
            print("  ", d, "->", hits[:6])
    except Exception:
        pass

print("=== ORT session attempt with CUDA, severity=1 (its own words) ===")
if ort is not None:
    import warnings
    warnings.filterwarnings("ignore")
    for provs in (["CUDAExecutionProvider"], ["CUDAExecutionProvider", "CPUExecutionProvider"], ["TensorrtExecutionProvider", "CUDAExecutionProvider"]):
        try:
            so = ort.SessionOptions()
            so.log_severity_level = 1
            so.enable_profiling = False
            s = ort.InferenceSession(enc, so, providers=provs)
            print(f"  asked {provs} -> ACTUAL {s.get_providers()}")
            del s
        except Exception as e:
            print(f"  asked {provs} -> RAISED {type(e).__name__}: {str(e)[:600]}")
