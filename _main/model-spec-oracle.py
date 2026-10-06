# ORACLE for docs/model-specs/README.md — re-runnable, exits 0 only if the shipped
# worker config and the model's OWN genai_config.json agree on the two constants the
# decoder depends on. Writes its verdict to a log (launched with pythonw: no console).
import json, os, sys, io

OUT = r"H:\sotto\_main\model-spec-oracle.log"
log = io.open(OUT, "w", encoding="utf-8")
def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n"); log.flush()

os.chdir(r"H:\sotto")
cfg = json.load(io.open("worker/config.json", encoding="utf-8"))
d = cfg["model"]["dir"]
genai = json.load(io.open(os.path.join("worker", d, "genai_config.json"), encoding="utf-8"))["model"]

blank = genai["blank_id"]
chunk = genai["chunk_samples"]
maxsym = genai["max_symbols_per_step"]
lang = cfg["model"].get("lang_id")
vad = cfg["model"].get("use_vad")

p("model dir      :", d)
p("blank_id       :", blank, "(spec says 13087)")
p("chunk_samples  :", chunk, "(spec says 8960)")
p("max_symbols    :", maxsym)
p("left_context   :", genai["left_context"])
# `lang_id` is no longer a bare int: it may be an id, a tag, 'auto', or 'os' (the shipped
# default = the host user locale). Print BOTH what the file says and what it resolves to.
_resolved = "?"
try:
    sys.path.insert(0, os.path.join(os.getcwd(), "worker"))
    import lang_prompt as _lp

    _r = _lp.resolve_lang_id(lang, os.path.join("worker", d))
    _resolved = f"{_r.lang_id} ({_r.tag}, source={_r.source})"
except Exception as _exc:  # a refused value must be visible here, not hidden
    _resolved = f"REFUSED/ERROR: {type(_exc).__name__}: {_exc}"
p("config lang_id :", lang, "(resolves to", _resolved + ")")
p("               : languages.json: 0=en-US, 12=pt-BR, 13=pt, 101=auto; 'os' = host locale")
p("config use_vad :", vad, "(model ships silero_vad tuned thr=0.3 silence=3360ms)")

ok = (blank == 13087 and chunk == 8960)
p("")
p("VERDICT:", "OK" if ok else "MISMATCH — config and model spec disagree; fix before touching decode")
log.close()
sys.exit(0 if ok else 1)
