# Research lane probe 2: sherpa-onnx per-stream options + wheel source census.
import os, re, glob
import sherpa_onnx
D = os.path.dirname(sherpa_onnx.__file__)
print("SHERPA", sherpa_onnx.__version__, "|", D)

print("\n--- files in the wheel ---")
for f in sorted(glob.glob(os.path.join(D, "**", "*"), recursive=True)):
    if os.path.isfile(f):
        print("   %-46s %d" % (f.replace(D, ""), os.path.getsize(f)))

print("\n--- pattern census over the wheel's own python sources ---")
PATTERNS = ["nemotron", "prompt_index", "language", "lang_id", "auto_prompt_id",
            "hotwords", "model_type", "provider", "cuda", "directml", "timestamps",
            "set_option", "has_option"]
for f in sorted(glob.glob(os.path.join(D, "**", "*.py"), recursive=True)):
    try:
        txt = open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    hits = ["%s=%d" % (p, len(re.findall(p, txt, re.I))) for p in PATTERNS
            if re.search(p, txt, re.I)]
    if hits:
        print("  %-34s %s" % (os.path.basename(f), " ".join(hits)))

print("\n--- every nemotron / prompt_index / language line, with context ---")
for f in sorted(glob.glob(os.path.join(D, "**", "*.py"), recursive=True)):
    try:
        lines = open(f, encoding="utf-8", errors="replace").read().split("\n")
    except Exception:
        continue
    for i, ln in enumerate(lines):
        if re.search(r"prompt_index|nemotron|auto_prompt_id|\blanguage\b", ln, re.I):
            print("  %s:%d: %s" % (os.path.basename(f), i + 1, ln.strip()[:170]))
