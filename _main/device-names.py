# Enumerate the INPUT devices with their EXACT names and test them against the
# preferred_devices list in worker/config.json. Answers: why did the resolver land on
# "Driver de captura de som primário" instead of CABLE Output? Writes a log (pythonw).
import io, json, os, sys

OUT = r"H:\sotto\_main\device-names.log"
log = io.open(OUT, "w", encoding="utf-8")
def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n"); log.flush()

cfg = json.load(io.open(r"H:\sotto\worker\config.json", encoding="utf-8"))
pref = cfg["audio"].get("preferred_devices", [])
p("preferred_devices:", json.dumps(pref, ensure_ascii=False))

try:
    import sounddevice as sd
except Exception as e:
    p("sounddevice IMPORT FAILED:", type(e).__name__, e); log.close(); sys.exit(1)

try:
    devs = sd.query_devices()
except Exception as e:
    p("query_devices FAILED:", type(e).__name__, e); log.close(); sys.exit(1)

inputs, outputs = [], []
for i, d in enumerate(devs):
    if d["max_input_channels"] > 0:
        inputs.append((i, d["name"], d["max_input_channels"], round(d["default_samplerate"], 1), d["hostapi"]))
    if d["max_output_channels"] > 0:
        outputs.append((i, d["name"], d["hostapi"]))

api_names = [a["name"] for a in sd.query_hostapis()]
p("")
p("hostapis:", json.dumps(api_names, ensure_ascii=False))
p("")
p(f"INPUT devices ({len(inputs)}):")
for i, name, ch, sr, api in inputs:
    p(f"  id={i:<4} ch={ch} {sr} Hz  api={api_names[api] if api < len(api_names) else api}")
    p(f"        name={name!r}")

p("")
p("MATCH TEST — exact and substring, case-sensitive and case-insensitive:")
for want in pref:
    exact = [n for _, n, *_ in inputs if n == want]
    sub = [n for _, n, *_ in inputs if want in n]
    ci = [n for _, n, *_ in inputs if want.lower() in n.lower()]
    p(f"  want={want!r}")
    p(f"     exact={len(exact)}  substring={len(sub)}  case-insensitive={len(ci)}")
    for n in ci[:4]:
        p(f"        -> {n!r}")

try:
    d = sd.query_devices(kind="input")
    p("")
    p("default input device:", json.dumps(d["name"], ensure_ascii=False), "| id:", sd.default.device)
except Exception as e:
    p("default input FAILED:", type(e).__name__, e)

p("")
p("VERDICT: the name the failed live run opened was 'Driver de captura de som primário'.")
p("Present in INPUTS above?", any("prim" in n.lower() for _, n, *_ in inputs))
log.close()
