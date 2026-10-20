# ORACLE for docs/model-specs/README.md — re-runnable, exits 0 only if the shipped
# worker config and the model's OWN genai_config.json agree on the two constants the
# decoder depends on. Writes its verdict to a log (launched with pythonw: no console)
# AND to stdout, so the battery's step log carries the verdict too.
#
# NEGATIVE ARM (2026-10-11 — closes audit row #56, which read "model-spec-oracle nao tem
# braco negativo (detector de drift, nao oraculo)"). `--neg-arm` re-runs the SAME checks
# against COPIES of genai_config.json with ONE constant mutated each, inside TMPDIR, and
# requires the verdict to FLIP to MISMATCH — while the live control stays OK in the same
# run. An instrument that cannot say NO cannot say YES either; the two mutants are one per
# constant, so a check that silently stopped reading a field would be caught here.
#
# THE MUTANTS ARE TEXTUAL, ON A UNIQUE ANCHOR. The anchor is an EXACT string of the
# model's genai_config.json; before it is used the oracle COUNTS it in the file. An anchor
# that is missing (the model was re-exported and the oracle is now stale) or that appears
# more than once (the mutation would hit the wrong field) is DECORATIVE: it proves
# nothing, so the oracle refuses to count it, says so, and exits 2. A mutant that was
# applied but did not flip the verdict is reported as SURVIVED — the gate is blind there.
#
# EXIT CODES
#   normal run   0 = PASS ("VERDICT: PASS"), 1 = FAIL
#   --neg-arm    1 = PASS BY DESIGN (the negative arm is SUPPOSED to find the drift; the
#                     battery's :expectred recorder asks for exactly that), 0 = a mutant
#                     was NOT caught, 2 = setup error (a decorative mutant).
import json, os, sys, io

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "model-spec-oracle.log")
log = io.open(OUT, "w", encoding="utf-8")
def p(*a):
    line = " ".join(str(x) for x in a)
    log.write(line + "\n"); log.flush()
    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except Exception:                                           # noqa: BLE001
        pass

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_SETUP = 2

# THE MUTANTS: (label, the UNIQUE anchor in genai_config.json, its replacement).
MUTANTS = [
    ("chunk_samples", '    "chunk_samples": 8960,', '    "chunk_samples": 1234,'),
    ("blank_id", '    "blank_id": 13087,', '    "blank_id": 1,'),
]


def live_model_dir(repo):
    return json.load(io.open(os.path.join(repo, "worker", "config.json"), encoding="utf-8"))["model"]["dir"]


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


def _mutant_text(tmpdir, label, anchor, replacement):
    """A copy of the LIVE genai_config.json with ONE anchored field changed.

    Returns (path, reason). `reason` is None on success, or the reason the mutant is
    DECORATIVE and must not be counted: the anchor is missing (stale oracle) or
    ambiguous (it would hit the wrong field).
    """
    live = live_model_dir(REPO)
    src = os.path.join(REPO, "worker", live, "genai_config.json")
    with io.open(src, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    hits = text.count(anchor)
    if hits != 1:
        return None, ("ANCHOR %s (%d hit(s))" % ("MISSING" if hits == 0 else "AMBIGUOUS", hits))
    mutated = text.replace(anchor, replacement, 1)
    if mutated == text:
        return None, "ANCHOR applied to NOTHING"
    dst = os.path.join(tmpdir, "genai-%s.json" % label)
    with io.open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.write(mutated)
    return dst, None


def neg_arm():
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="sotto-model-spec-neg-", dir=os.environ.get("TMPDIR") or None)
    try:
        control_ok = evaluate(REPO, os.path.join(
            REPO, "worker", live_model_dir(REPO), "genai_config.json"), p)
        caught = 0
        decorative = 0
        for label, anchor, replacement in MUTANTS:
            path, reason = _mutant_text(tmpdir, label, anchor, replacement)
            if path is None:
                decorative += 1
                p("NEG-ARM M[%s] :" % label, "DECORATIVE -- %s; NOT counted" % reason)
                continue
            ok = evaluate(REPO, path, lambda *a: None)
            red = ok is False
            if red:
                caught += 1
            p(f"NEG-ARM M[{label}] :", "MISMATCH (RED as required)" if red
              else "OK -- THE ORACLE CANNOT SAY NO")
        p("")
        p("NEG-ARM control (live files) :", "OK (green, as required)" if control_ok
          else "MISMATCH -- the control itself is broken")
        total = len(MUTANTS)
        ok = (caught == total and control_ok and decorative == 0)
        p("NEG-ARM " + ("PASS" if ok else "FAIL")
          + f" -- mutants {caught}/{total} caught, {decorative} decorative")
        if decorative:
            # A decorative mutant is worse than no mutant at all: the oracle cannot
            # say NO about a file whose anchor it did not find. Setup error.
            return EXIT_SETUP
        if not ok:
            # rc=0 = "a mutant was NOT caught" -- the contract this file writes in
            # its OWN header (lines 20-24) and the convention the AGENTS.md states.
            # MEASURED 2026-10-20: this line returned EXIT_FAIL (=1), which is the
            # SAME number the pass-by-design path returns below, so the instrument
            # could not tell "found the drift" from "did not find it" -- and the
            # battery's :expectred (which asks for exactly 1) therefore passed a
            # BLIND gate. A gate that cannot say NO is decoration.
            return EXIT_PASS
        # rc=1 BY DESIGN: the negative arm is SUPPOSED to find the drift, so "found it"
        # is a non-zero exit -- the battery's :expectred recorder asks for exactly that.
        return 1
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    if "--neg-arm" in sys.argv:
        sys.exit(neg_arm())

    _live_dir = live_model_dir(REPO)
    ok = evaluate(REPO, os.path.join(REPO, "worker", _live_dir, "genai_config.json"), p)
    p("")
    p("VERDICT:", "PASS" if ok else "FAIL — config and model spec disagree; fix before touching decode")
    log.close()
    sys.exit(EXIT_PASS if ok else EXIT_FAIL)
