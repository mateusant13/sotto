# ORACLE for the language-prompt deviation in docs/model-specs/README.md §6.2.
#
# Re-runnable. It fails if ANY of these stops being true:
#   1. the prompt table is read from the model's own languages.json;
#   2. the documented ids resolve to the documented tags (0=en-US, 12=pt-BR,
#      13=pt/pt-PT, 101=auto);
#   3. the shipped default ('os') is the host's user locale, not a hardcoded tag;
#   4. an undeclared id (999, -1, 'klingon') is REFUSED, never clamped;
#   5. the value REACHES the model: the encoder graph declares a `lang_id` input,
#      and changing it changes the encoder output on identical audio (i.e. it is
#      consumed, not ignored);
#   6. the defect that made `config.json`'s lang_id dead is gone: the CLI flag's
#      default is None, so the config rung is reachable.
#
# THE MODEL DIRECTORY IS NOT PINNED HERE. It is read from `worker/config.json`,
# the same file the product reads, so the oracle cannot rot when the product
# moves to another export (it did: the shipped directory is no longer the one a
# hardcoded name named, and the oracle died on a FileNotFoundError instead of
# saying anything).
#
# NEGATIVE ARM. `--neg-arm` runs the SAME checks against MUTANTS: a COPY of
# `worker/lang_prompt.py` and a COPY of `worker/sotto_worker.py`, each with ONE
# anchored line changed, inside TMPDIR. The mutants are TEXTUAL, on an EXACT
# anchor; before an anchor is used it is COUNTED in the file. An anchor that is
# missing (the oracle is stale) or that appears more than once (the mutation
# would hit the wrong place) is DECORATIVE: it proves nothing, so the oracle
# refuses to count it, says so, and exits 2. A mutant that was applied but left
# a check green is reported as SURVIVED -- the gate is blind there.
#
# EXIT CODES
#   normal run   0 = PASS ("VERDICT: PASS"), 1 = FAIL
#   --neg-arm    1 = PASS BY DESIGN (the negative arm is SUPPOSED to find the
#                 defect; the battery's :expectred recorder asks for exactly that),
#                 0 = a mutant was NOT caught, 2 = setup error (a decorative
#                 mutant).
import atexit
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "lang-id-oracle.log")
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "worker"))

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_SETUP = 2

# THE MUTANTS: each is a file this oracle judges, an EXACT anchor in it, and
# the replacement. The anchor is matched with the FILE's own EOL.
MUTANTS = [
    {
        "tag": "M1 the resolver CLAMPS an undeclared id instead of refusing it",
        "file": "worker/lang_prompt.py",
        "anchor_lines": ['raise _refuse(raw, table, "an integer outside the declared slot set")'],
        "replacement_lines": [
            'return Resolution(table.auto_slot, table.tag_of(table.auto_slot), "id", '
            'requested, table.path, "CLAMPED -- the mutant")'],
    },
    {
        "tag": "M2 --lang-id goes back to a hardcoded default (config.json goes dead again)",
        "file": "worker/sotto_worker.py",
        "anchor_lines": ['"--lang-id",', '        default=None,'],
        "replacement_lines": ['"--lang-id",', '        default=0,'],
    },
]


def emit_to(log):
    """A printer that writes to the log AND to stdout, so the battery's step log
    carries the verdict (the log file alone would leave the step log empty)."""
    def p(*a):
        line = " ".join(str(x) for x in a)
        log.write(line + "\n")
        log.flush()
        try:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except Exception:                                           # noqa: BLE001
            pass
    return p


def find_anchor(text, lines):
    """(anchor, hits): the block as THIS file writes it, and how many times it is
    there. The EOL is the file's own, so a CRLF file is matched with CRLF. A
    ONE-LINE anchor is the same string in both EOLs, so it is only counted once."""
    anchor = None
    hits = 0
    seen = set()
    for eol in ("\r\n", "\n"):
        candidate = eol.join(lines)
        if candidate in seen:
            continue
        seen.add(candidate)
        n = text.count(candidate)
        if n:
            hits += n
            if anchor is None:
                anchor = candidate
    return anchor, hits


def battery(lp, worker_source, model_dir, sw, p):
    """The six checks, against the `lang_prompt` module and the
    `worker/sotto_worker.py` source under test. Returns the list of failures."""
    FAILS = []

    def check(name, ok, detail=""):
        p(f"[{'ok ' if ok else 'RED'}] {name}" + (f" :: {detail}" if detail else ""))
        if not ok:
            FAILS.append(name)

    # ── 1. the table ────────────────────────────────────────────────────────
    table = lp.load_language_table(model_dir)
    p("=== 1. the table (the model's own languages.json)")
    p("table      :", table.path)
    p("numPrompts :", table.num_prompts)
    p("autoSlot   :", table.auto_slot)
    check("table is a languages.json on disk", table.path.endswith("languages.json"))
    check("numPrompts == 128", table.num_prompts == 128, str(table.num_prompts))
    check("autoSlot == 101", table.auto_slot == 101, str(table.auto_slot))

    # ── 2. the documented ids ───────────────────────────────────────────────
    p("")
    p("=== 2. the documented ids resolve as docs/model-specs/README.md §3 says")
    for req, want_id, want_tag in ((0, 0, "en-US"), (12, 12, "pt-BR"), (13, 13, "pt-PT"),
                                    (101, 101, "auto"), ("en", 0, "en-US"), ("pt-BR", 12, "pt-BR")):
        r = lp.resolve_lang_id(req, model_dir)
        p(f"  {str(req):>6} -> id={r.lang_id:<4} tag={r.tag:<6} source={r.source}")
        check(f"{req!r} -> {want_id}/{want_tag}", r.lang_id == want_id and r.tag == want_tag,
              f"got {r.lang_id}/{r.tag}")

    # ── 3. the shipped default is the host locale, not a hardcode ───────────
    p("")
    p("=== 3. the shipped default")
    host = lp.os_locale_tag()
    r_os = lp.resolve_lang_id("os", model_dir)
    r_none = lp.resolve_lang_id(None, model_dir)
    p("host locale :", host)
    p("resolve('os'):", f"id={r_os.lang_id} tag={r_os.tag} source={r_os.source} note={r_os.note!r}")
    p("resolve(None):", f"id={r_none.lang_id} tag={r_none.tag} source={r_none.source}")
    hit = table.lookup(host) if host else None
    if hit:
        check("'os' == the host locale mapped through the table", r_os.lang_id == hit[0],
              f"{r_os.lang_id} vs {hit[0]}")
    else:
        check("'os' falls back to auto when the locale names no slot", r_os.lang_id == table.auto_slot,
              str(r_os.lang_id))
    check("None means the same as 'os'", r_none.lang_id == r_os.lang_id)

    # ── 4. the negative arm ─────────────────────────────────────────────────
    p("")
    p("=== 4. undeclared ids are REFUSED, never clamped")
    for bad in (999, -1, 300, 128, "klingon", "zz-ZZ", "107"):
        try:
            r = lp.resolve_lang_id(bad, model_dir)
            check(f"{bad!r} refused", False, f"ACCEPTED as {r.lang_id}/{r.tag} — that is a clamp")
        except lp.LangIdError as exc:
            p(f"  {str(bad):>8} -> REFUSED: {str(exc)[:96]}...")
            check(f"{bad!r} refused", True)

    # ── 5. the value REACHES the model ──────────────────────────────────────
    p("")
    p("=== 5. does it reach the model? (real encoder, same audio, only lang_id differs)")
    import numpy as np  # noqa: E402
    import soundfile as sf  # noqa: E402

    pcm, sr = sf.read(os.path.join(ROOT, "worker", "assets", "sample1.flac"), dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    if sr != sw.TARGET_SR:
        pcm = sw.resample_to_16k(pcm, sr)

    asr = sw.StreamAsr(model_dir, providers=["CPUExecutionProvider"], use_vad=False, lang_id=12)
    p("enc inputs  :", [i.name for i in asr.enc.get_inputs()])
    p("lang_input  :", asr.lang_input)
    p("lid fed     :", asr.lid.tolist(), asr.lid.dtype)
    check("encoder DECLARES a lang_id input", asr.lang_input == "lang_id", str(asr.lang_input))
    check("the tensor fed carries the resolved id", asr.lid.tolist() == [12], str(asr.lid.tolist()))

    feats = asr.sp.process(pcm[: asr.chunk])
    af = feats["audio_features"]
    af = af.as_numpy() if hasattr(af, "as_numpy") else np.asarray(af)

    outs = {}
    for lid in (0, 12, 999):
        cc, ct, ccl = sw._initial_encoder_caches(np, asr.enc, model_dir)
        feed = {
            "audio_signal": af.astype(np.float32),
            "length": np.array([af.shape[1]], np.int64),
            "cache_last_channel": cc,
            "cache_last_time": ct,
            "cache_last_channel_len": ccl,
            "lang_id": np.array([lid], np.int64),
        }
        try:
            o = asr.enc.run(["outputs", "encoded_lengths", "cache_last_channel_next",
                             "cache_last_time_next", "cache_last_channel_len_next"], feed)
            outs[lid] = np.asarray(o[0], dtype=np.float32)
            p(f"  encoder lang_id={lid:<4} -> shape {outs[lid].shape} "
              f"mean|out|={float(np.abs(outs[lid]).mean()):.6f}")
        except Exception as exc:                                    # noqa: BLE001
            outs[lid] = None
            p(f"  encoder lang_id={lid:<4} -> RAISED {type(exc).__name__}: {str(exc)[:120]}")

    if outs.get(0) is not None and outs.get(12) is not None:
        d = float(np.abs(outs[0] - outs[12]).max())
        p(f"  max|enc(lang_id=0) - enc(lang_id=12)| = {d:.6f}  (0 would mean the input is ignored)")
        check("lang_id 0 vs 12 changes the encoder output", d > 0.0, f"max abs diff {d:.6f}")
    else:
        check("lang_id 0 vs 12 changes the encoder output", False, "an encoder run did not complete")

    p("")
    if outs.get(999) is None:
        p("NOTE: onnxruntime ITSELF rejected lang_id=999 on the encoder. Even so the resolver")
        p("      refuses it BEFORE the session is built, in milliseconds, with a message")
        p("      naming the table.")
    else:
        p("NOTE: onnxruntime ACCEPTED lang_id=999 and produced numbers. The graph does not")
        p("      police the slot, so the loud refusal in worker/lang_prompt.py is the ONLY")
        p("      thing standing between a typo and a silently wrong prompt. This is exactly")
        p("      why the resolver refuses instead of clamping.")

    # ── 6. the dead-config defect is gone ───────────────────────────────────
    p("")
    p("=== 6. the defect that made config.json's lang_id dead")

    def argparse_default(flag):
        for block in worker_source.split("ap.add_argument(")[1:]:
            if block.lstrip().startswith(f'"{flag}"'):
                return block.split("ap.add_argument(")[0]
        return ""

    body = argparse_default("--lang-id")
    p("--lang-id decl:", " ".join(body.split())[:200])
    check(
        "--lang-id default is None (so config.json is reachable)",
        re.search(r"default\s*=\s*None", body) is not None and "default=0" not in body.replace(" ", ""),
        body.strip()[:120],
    )

    return FAILS


def _model_dir():
    cfg = json.load(io.open(os.path.join(ROOT, "worker", "config.json"), encoding="utf-8"))
    return os.path.join(ROOT, "worker", cfg["model"]["dir"])


def _load_module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def neg_arm(p, model_dir, sw):
    """The mutants. Returns an exit code."""
    tmpdir = tempfile.mkdtemp(prefix="sotto-lang-id-neg-", dir=os.environ.get("TMPDIR") or None)
    atexit.register(shutil.rmtree, tmpdir, True)
    caught = 0
    decorative = 0
    for idx, m in enumerate(MUTANTS):
        src_path = os.path.join(ROOT, m["file"])
        if not os.path.isfile(src_path):
            decorative += 1
            p("  RED   mutant %-64s FILE MISSING -- DECORATIVE, not counted" % m["tag"])
            continue
        with io.open(src_path, "r", encoding="utf-8", newline="") as fh:
            text = fh.read()
        anchor, hits = find_anchor(text, m["anchor_lines"])
        if hits != 1:
            decorative += 1
            p("  RED   mutant %-64s ANCHOR %s (%d hit(s)) -- DECORATIVE, not counted"
              % (m["tag"], "MISSING" if hits == 0 else "AMBIGUOUS", hits))
            continue
        eol = "\r\n" if "\r\n" in anchor else "\n"
        replacement = eol.join(m["replacement_lines"])
        mutated_text = text.replace(anchor, replacement, 1)
        if mutated_text == text:
            decorative += 1
            p("  RED   mutant %-64s ANCHOR applied to NOTHING -- DECORATIVE, not counted" % m["tag"])
            continue

        # The mutant becomes the SUBJECT: a copy of the file, imported by path.
        copy = os.path.join(tmpdir, "mutant-%d-%s" % (idx, os.path.basename(m["file"])))
        with io.open(copy, "w", encoding="utf-8", newline="") as fh:
            fh.write(mutated_text)
        try:
            if m["file"].endswith("lang_prompt.py"):
                lp = _load_module_from(copy, "lang_prompt_mutant_%d" % idx)
                fails = battery(lp, text, model_dir, sw, lambda *a: None)
            else:
                lp = _load_module_from(os.path.join(ROOT, "worker", "lang_prompt.py"),
                                       "lang_prompt_live_for_mutant")
                fails = battery(lp, mutated_text, model_dir, sw, lambda *a: None)
        except Exception as exc:                                    # noqa: BLE001
            p("  RED   mutant %-64s did not even run (%s: %s) -- NOT counted"
              % (m["tag"], type(exc).__name__, str(exc)[:80]))
            decorative += 1
            continue
        if fails:
            caught += 1
            p("  GREEN mutant %-64s caught by: %s" % (m["tag"], "; ".join(fails[:3])))
        else:
            p("  RED   mutant %-64s SURVIVED -- the gate is blind here" % m["tag"])

    total = len(MUTANTS)
    ok = (caught == total and decorative == 0)
    p("")
    p("NEG-ARM " + ("PASS" if ok else "FAIL")
      + " -- mutants %d/%d caught, %d decorative" % (caught, total, decorative))
    if decorative:
        # A decorative mutant is worse than no mutant at all: the oracle cannot say
        # NO about a file whose anchor it did not find. Setup error.
        return EXIT_SETUP
    if not ok:
        return 0
    # rc=1 BY DESIGN: the negative arm is SUPPOSED to find the defect, so "found it"
    # is a non-zero exit -- the battery's :expectred recorder asks for exactly that.
    return 1


def main():
    neg = "--neg-arm" in sys.argv
    log = io.open(OUT, "w", encoding="utf-8")
    p = emit_to(log)
    model_dir = _model_dir()
    p("model dir   :", os.path.basename(model_dir))
    if not os.path.isdir(model_dir):
        p("SETUP ERROR: the model directory named by worker/config.json is not there: " + model_dir)
        p("")
        p("VERDICT: FAIL -- the model the oracle judges is not on this box")
        log.close()
        return EXIT_FAIL

    import lang_prompt as lp  # noqa: E402
    import sotto_worker as sw  # noqa: E402

    if neg:
        rc = neg_arm(p, model_dir, sw)
        log.close()
        return rc

    with io.open(os.path.join(ROOT, "worker", "sotto_worker.py"), "r", encoding="utf-8",
                 newline="") as fh:
        worker_source = fh.read()
    fails = battery(lp, worker_source, model_dir, sw, p)
    p("")
    p("VERDICT:", "PASS" if not fails else "FAIL: " + ", ".join(fails))
    log.close()
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
