import json, hashlib, io
p = r"H:\sotto\_moved\aireplay\_main\lane-spec04-asr-emit.json"
raw = open(p,"rb").read()
print("bytes", len(raw), "sha256", hashlib.sha256(raw).hexdigest()[:16])
# is it valid UTF-8?
try:
    txt = raw.decode("utf-8"); print("utf8_decode OK")
except UnicodeDecodeError as e:
    print("utf8_decode FAIL", e); raise SystemExit(1)
j = json.loads(txt)
print("segments", len(j["segments"]))
print("text[0] =", j["segments"][0]["text"])
print("has non-ascii:", any(ord(c) > 127 for c in j["segments"][0]["text"]))
# every segment: keys exactly as the spec will claim
keys = set()
for s in j["segments"]: keys |= set(s.keys())
print("union of segment keys:", sorted(keys))
print("empty-text segments:", sum(1 for s in j["segments"] if s["chars"] == 0))
# overlap check, from the REAL numbers
ov = [(a["i"], round(a["end"]-b["start"],3)) for a,b in zip(j["segments"], j["segments"][1:])]
print("adjacent overlaps (s):", ov)
print("strictly increasing start:", all(a["start"] < b["start"] for a,b in zip(j["segments"], j["segments"][1:])))
print("start == offset + something >= offset:", all(s["start"] >= j["offset_s"] for s in j["segments"]))
print("max chars", max(s["chars"] for s in j["segments"]), "sum", sum(s["chars"] for s in j["segments"]), "len(text)", len(j["text"]))