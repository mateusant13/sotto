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
# Launched with pythonw by _main/lang-id-runs.py, so no console appears.
import io
import json
import os
import sys

ROOT = r"H:\sotto"
OUT = os.path.join(ROOT, "_main", "lang-id-oracle.log")
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "worker"))

log = io.open(OUT, "w", encoding="utf-8")
FAILS = []


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


def check(name, ok, detail=""):
    p(f"[{'ok ' if ok else 'RED'}] {name}" + (f" :: {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


import lang_prompt as lp  # noqa: E402

MODEL_DIR = os.path.join(ROOT, "worker", "models", "nemotron-3.5-asr-streaming-0.6b-int8")

# ── 1. the table ──────────────────────────────────────────────────────────────
table = lp.load_language_table(MODEL_DIR)
p("=== 1. the table (the model's own languages.json)")
p("table      :", table.path)
p("numPrompts :", table.num_prompts)
p("autoSlot   :", table.auto_slot)
check("table is a languages.json on disk", table.path.endswith("languages.json"))
check("numPrompts == 128", table.num_prompts == 128, str(table.num_prompts))
check("autoSlot == 101", table.auto_slot == 101, str(table.auto_slot))

# ── 2. the documented ids ─────────────────────────────────────────────────────
p("")
p("=== 2. the documented ids resolve as docs/model-specs/README.md §3 says")
for req, want_id, want_tag in ((0, 0, "en-US"), (12, 12, "pt-BR"), (13, 13, "pt-PT"), (101, 101, "auto"), ("en", 0, "en-US"), ("pt-BR", 12, "pt-BR")):
    r = lp.resolve_lang_id(req, MODEL_DIR)
    p(f"  {str(req):>6} -> id={r.lang_id:<4} tag={r.tag:<6} source={r.source}")
    check(f"{req!r} -> {want_id}/{want_tag}", r.lang_id == want_id and r.tag == want_tag, f"got {r.lang_id}/{r.tag}")

# ── 3. the shipped default is the host locale, not a hardcode ─────────────────
p("")
p("=== 3. the shipped default")
host = lp.os_locale_tag()
r_os = lp.resolve_lang_id("os", MODEL_DIR)
r_none = lp.resolve_lang_id(None, MODEL_DIR)
p("host locale :", host)
p("resolve('os'):", f"id={r_os.lang_id} tag={r_os.tag} source={r_os.source} note={r_os.note!r}")
p("resolve(None):", f"id={r_none.lang_id} tag={r_none.tag} source={r_none.source}")
hit = table.lookup(host) if host else None
if hit:
    check("'os' == the host locale mapped through the table", r_os.lang_id == hit[0], f"{r_os.lang_id} vs {hit[0]}")
else:
    check("'os' falls back to auto when the locale names no slot", r_os.lang_id == table.auto_slot, str(r_os.lang_id))
check("None means the same as 'os'", r_none.lang_id == r_os.lang_id)

# ── 4. the negative arm ───────────────────────────────────────────────────────
p("")
p("=== 4. undeclared ids are REFUSED, never clamped")
for bad in (999, -1, 300, 128, "klingon", "zz-ZZ", "107"):
    try:
        r = lp.resolve_lang_id(bad, MODEL_DIR)
        check(f"{bad!r} refused", False, f"ACCEPTED as {r.lang_id}/{r.tag} — that is a clamp")
    except lp.LangIdError as exc:
        p(f"  {str(bad):>8} -> REFUSED: {str(exc)[:96]}...")
        check(f"{bad!r} refused", True)

# ── 5. the value REACHES the model ────────────────────────────────────────────
p("")
p("=== 5. does it reach the model? (real encoder, same audio, only lang_id differs)")
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import sotto_worker as sw  # noqa: E402

pcm, sr = sf.read(os.path.join(ROOT, "worker", "assets", "sample1.flac"), dtype="float32")
if pcm.ndim > 1:
    pcm = pcm.mean(axis=1)
if sr != sw.TARGET_SR:
    pcm = sw.resample_to_16k(pcm, sr)

asr = sw.StreamAsr(MODEL_DIR, providers=["CPUExecutionProvider"], use_vad=False, lang_id=12)
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
    cc, ct, ccl = sw._initial_encoder_caches(np, asr.enc, MODEL_DIR)
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
        p(f"  encoder lang_id={lid:<4} -> shape {outs[lid].shape} mean|out|={float(np.abs(outs[lid]).mean()):.6f}")
    except Exception as exc:
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
    p("      refuses it BEFORE a 1.2 GB session is built, in milliseconds, with a message")
    p("      naming the table — see the `--lang-id 999` arm of _main/lang-id-runs.py.")
else:
    p("NOTE: onnxruntime ACCEPTED lang_id=999 and produced numbers. The graph does not")
    p("      police the slot, so the loud refusal in worker/lang_prompt.py is the ONLY")
    p("      thing standing between a typo and a silently wrong prompt. This is exactly")
    p("      why the resolver refuses instead of clamping.")

# ── 6. the dead-config defect is gone ─────────────────────────────────────────
p("")
p("=== 6. the defect that made config.json's lang_id dead")


def argparse_default(flag):
    src = io.open(os.path.join(ROOT, "worker", "sotto_worker.py"), encoding="utf-8").read()
    for block in src.split("ap.add_argument(")[1:]:
        if block.lstrip().startswith(f'"{flag}"'):
            return block.split("ap.add_argument(")[0]
    return ""


import re  # noqa: E402

body = argparse_default("--lang-id")
p("--lang-id decl:", " ".join(body.split())[:200])
check(
    "--lang-id default is None (so config.json is reachable)",
    re.search(r"default\s*=\s*None", body) is not None and "default=0" not in body.replace(" ", ""),
    body.strip()[:120],
)

p("")
p("VERDICT:", "OK" if not FAILS else "FAILED: " + ", ".join(FAILS))
log.close()
sys.exit(0 if not FAILS else 1)
