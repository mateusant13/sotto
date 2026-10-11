# ORACLE for docs/model-specs/README.md — re-runnable, exits 0 only if the shipped
# worker config and the model's OWN genai_config.json agree on the two constants the
# decoder depends on. Writes its verdict to a log (launched with pythonw: no console).
#
# NEGATIVE ARM (2026-10-11 — closes audit row #56, which read "model-spec-oracle nao tem
# braco negativo (detector de drift, nao oraculo)"). `--neg-arm` re-runs the SAME checks
# against COPIES of genai_config.json with ONE constant mutated each, inside TMPDIR, and
# requires the verdict to FLIP to MISMATCH — while the live control stays OK in the same
# run. An instrument that cannot say NO cannot say YES either; the two mutants are one per
# constant, so a check that silently stopped reading a field would be caught here.
import json, os, sys, io

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "model-spec-oracle.log")
log = io.open(OUT, "w", encoding="utf-8")
def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n"); log.flush()


def evaluate(repo, genai_path, emit):
    """The shipped checks, unchanged. Returns True iff config and model spec agree.

    `genai_path` is a parameter so the negative arm can point it at a mutated COPY while
    every other input (the worker config, the model dir, languages.json) stays live.
    """
    cfg = json.load(io.open(os.path.join(repo, "worker", "config.json"), encoding="utf-8"))
    d = cfg["model"]["dir"]
    genai = json.load(io.open(genai_path, encoding="utf-8"))["model"]

    blank = genai["blank_id"]
    chunk = genai["chunk_samples"]
    maxsym = genai["max_symbols_per_step"]
    lang = cfg["model"].get("lang_id")
    vad = cfg["model"].get("use_vad")

    emit("model dir      :", d)
    emit("blank_id       :", blank, "(spec says 13087)")
    emit("chunk_samples  :", chunk, "(spec says 8960)")
    emit("max_symbols    :", maxsym)
    emit("left_context   :", genai["left_context"])
    # `lang_id` is no longer a bare int: it may be an id, a tag, 'auto', or 'os' (the shipped
    # default = the host user locale). Print BOTH what the file says and what it resolves to.
    _resolved = "?"
    try:
        sys.path.insert(0, os.path.join(repo, "worker"))
        import lang_prompt as _lp

        _r = _lp.resolve_lang_id(lang, os.path.join(repo, "worker", d))
        _resolved = f"{_r.lang_id} ({_r.tag}, source={_r.source})"
    except Exception as _exc:  # a refused value must be visible here, not hidden
        _resolved = f"REFUSED/ERROR: {type(_exc).__name__}: {_exc}"
    emit("config lang_id :", lang, "(resolves to", _resolved + ")")
    emit("               : languages.json: 0=en-US, 12=pt-BR, 13=pt, 101=auto; 'os' = host locale")
    emit("config use_vad :", vad, "(model ships silero_vad tuned thr=0.3 silence=3360ms)")

    return (blank == 13087 and chunk == 8960)


def _mutant(tmpdir, field, value):
    """A copy of the LIVE genai_config.json with one field changed. Returns its path."""
    live = json.load(io.open(os.path.join(REPO, "worker", "config.json"), encoding="utf-8"))["model"]["dir"]
    src = os.path.join(REPO, "worker", live, "genai_config.json")
    doc = json.load(io.open(src, encoding="utf-8"))
    doc["model"][field] = value
    dst = os.path.join(tmpdir, f"genai-{field}-{value}.json")
    with io.open(dst, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return dst


def neg_arm():
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="sotto-model-spec-neg-", dir=os.environ.get("TMPDIR") or None)
    control_ok = evaluate(REPO, os.path.join(
        REPO, "worker",
        json.load(io.open(os.path.join(REPO, "worker", "config.json"), encoding="utf-8"))["model"]["dir"],
        "genai_config.json"), p)
    arms = [("chunk_samples", 1234, "chunk_samples"), ("blank_id", 1, "blank_id")]
    results = []
    for field, value, label in arms:
        ok = evaluate(REPO, _mutant(tmpdir, field, value), lambda *a: None)
        red = ok is False
        results.append(red)
        p(f"NEG-ARM M[{label}={value}] :", "MISMATCH (RED as required)" if red
          else "OK -- THE ORACLE CANNOT SAY NO")
    p("")
    p("NEG-ARM control (live files) :", "OK (green, as required)" if control_ok
      else "MISMATCH -- the control itself is broken")
    p("VERDICT:", "NEG-ARM PASS" if (all(results) and control_ok) else "NEG-ARM FAIL")
    return 0 if (all(results) and control_ok) else 1


if __name__ == "__main__":
    if "--neg-arm" in sys.argv:
        sys.exit(neg_arm())

    _live_dir = json.load(io.open(os.path.join(REPO, "worker", "config.json"), encoding="utf-8"))["model"]["dir"]
    ok = evaluate(REPO, os.path.join(REPO, "worker", _live_dir, "genai_config.json"), p)
    p("")
    p("VERDICT:", "OK" if ok else "MISMATCH — config and model spec disagree; fix before touching decode")
    log.close()
    sys.exit(0 if ok else 1)
