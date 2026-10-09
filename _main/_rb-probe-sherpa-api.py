# Research lane probe: the EXACT sherpa-onnx API surface for (a) the nemotron streaming
# transducer and (b) the per-stream language prompt. Reads the installed wheel's own
# python sources — no model is loaded.
import os, re, glob, inspect, sys

import sherpa_onnx
D = os.path.dirname(sherpa_onnx.__file__)
print("SHERPA", sherpa_onnx.__version__, "|", D)

print("\n--- OnlineRecognizer.from_transducer FULL signature ---")
try:
    print(inspect.signature(sherpa_onnx.OnlineRecognizer.from_transducer))
except Exception as e:
    print("unavailable", e)

print("\n--- OnlineStream public methods ---")
print([m for m in dir(sherpa_onnx.OnlineStream) if not m.startswith("_")])
print("OnlineStream.set_option signature:",
      inspect.signature(sherpa_onnx.OnlineStream.set_option))

print("\n--- grep the wheel's python sources ---")
PATTERNS = ["nemotron", "prompt_index", "language", "lang_id", "auto_prompt_id",
            "hotwords", "model_type", "provider", "cuda", "directml", "timestamps"]
for f in sorted(glob.glob(os.path.join(D, "**", "*.py"), recursive=True)):
    try:
        txt = open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    hits = []
    for p in PATTERNS:
        n = len(re.findall(p, txt, re.I))
        if n:
            hits.append("%s=%d" % (p, n))
    if hits:
        print("  %-40s %s" % (os.path.basename(f), " ".join(hits)))

print("\n--- every 'language'-ish knob found, with 2 lines of context ---")
for f in sorted(glob.glob(os.path.join(D, "**", "*.py"), recursive=True)):
    try:
        lines = open(f, encoding="utf-8", errors="replace").read().split("\n")
    except Exception:
        continue
    for i, ln in enumerate(lines):
        if re.search(r"prompt_index|nemotron|auto_prompt_id", ln, re.I):
            print("  %s:%d: %s" % (os.path.basename(f), i + 1, ln.strip()[:160]))
