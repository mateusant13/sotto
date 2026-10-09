# Research lane probe: (1) clean ORT-GenAI API surface; (2) the import-order collision
# between sherpa_onnx and onnxruntime_genai, both colours.
# Usage: python _rb-probe-genai.py <arm>   arm = genai-alone | genai-then-sherpa | sherpa-then-genai
import sys, os, glob

ARM = sys.argv[1] if len(sys.argv) > 1 else "genai-alone"
print("ARM", ARM)

def try_import(label, mod):
    try:
        m = __import__(mod, fromlist=["*"])
        print("  %-16s OK   %s" % (label, getattr(m, "__version__", "?")))
        return m
    except Exception as e:
        print("  %-16s FAIL %s: %s" % (label, type(e).__name__, str(e)[:200]))
        return None

og = sherpa = ort = None
if ARM == "genai-alone":
    og = try_import("onnxruntime_genai", "onnxruntime_genai")
elif ARM == "genai-then-sherpa":
    og = try_import("onnxruntime_genai", "onnxruntime_genai")
    sherpa = try_import("sherpa_onnx", "sherpa_onnx")
elif ARM == "sherpa-then-genai":
    sherpa = try_import("sherpa_onnx", "sherpa_onnx")
    og = try_import("onnxruntime_genai", "onnxruntime_genai")

ort = try_import("onnxruntime", "onnxruntime")

if og is not None:
    print("GENAI PUBLIC:", [n for n in dir(og) if not n.startswith("_")])
    for n in ("StreamingProcessor", "AsrProcessor", "MultiModalProcessor", "Tokenizer", "Model",
              "Config", "Generator", "GeneratorParams", "Audios", "Images", "is_cuda_available"):
        print("  %-20s %s" % (n, "PRESENT" if hasattr(og, n) else "ABSENT"))
    try:
        print("  is_cuda_available() ->", og.is_cuda_available())
    except Exception as e:
        print("  is_cuda_available() raised", e)

if ort is not None:
    print("ORT", ort.__version__, "available", ort.get_available_providers())

# which onnxruntime DLLs exist on disk, and which one got loaded?
print("--- onnxruntime DLLs on disk ---")
SP = r"C:\Program Files\Python311\Lib\site-packages"
for p in glob.glob(os.path.join(SP, "**", "onnxruntime*.dll"), recursive=True):
    print("   ", p.replace(SP, "..."), os.path.getsize(p))
print("--- onnxruntime_genai wheel contents ---")
gdir = os.path.join(SP, "onnxruntime_genai")
if os.path.isdir(gdir):
    for f in sorted(os.listdir(gdir)):
        fp = os.path.join(gdir, f)
        print("   ", f, os.path.getsize(fp) if os.path.isfile(fp) else "<dir>")
print("--- sherpa_onnx wheel .dll/.pyd ---")
import sherpa_onnx as _s  # noqa
sdir = os.path.dirname(_s.__file__)
for f in sorted(os.listdir(sdir)):
    if f.endswith((".dll", ".pyd")):
        print("   ", f, os.path.getsize(os.path.join(sdir, f)))
