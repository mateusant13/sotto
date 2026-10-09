#!/usr/bin/env python
"""LANE9-GATE -- does the ASR actually work END TO END on real speech?

The gap this closes, measured: the 8 sample clips carry NO audio stream, so nothing had ever
fed this engine anything from a capture. `audio.py` reads a file, so the honest first proof is
a REAL speech WAV through the REAL product path (`runner.transcribe`, the same function the
CLI and the parity harness call) -- not a unit test of the decoder.

Arms (named, each one a claim that can be wrong):

  A  real speech in -> transcript out, scored against a REGISTERED oracle
  B  the language prompt: what this export can and cannot be told, proven BOTH directions
  C  the CONTROL: the same checks against a COPY with the cures reverted -- must go red
  D  the LIVE engine refuses a provider this box cannot load (the cure's own red arm)

`--selfcheck` runs the NEGATIVE instruments -- the boxes that prove an arm CAN say no, because
a gate nobody has watched go red is an ornament. Verifier pass 1 proved ARM A could not fail on
content (F1) and that the provider cure had no live red arm (F2); these are the checks that
would have caught both. Writes nothing into the repo.

Provider honesty is part of every arm: `PROVIDERS = ("CPUExecutionProvider",)` because
CUDAExecutionProvider does not load on this box, and a provider that did not load is a
refusal, not a silent downgrade (AGENTS.md:230-234; `engine._verify_provider`).

WER NOTE, stated where it is computed and not hidden: the reference text is
`H:\\sotto\\_main\\redux-{en,ptbr}.txt`, the ORACLE transcript of a DIFFERENT engine (the
sibling's Redux ternary), NOT a human transcription of these clips. So ARM A's number is
**agreement with the oracle** -- two engines compared on the same audio. It is NOT a bound on
anything: if both engines were wrong the same way the error would be 0. It is never presented
here as an accuracy claim. A true WER needs a labelled corpus this box does not have:
NOT MEASURED. (F5, verifier: the earlier wording called this an "upper bound", which is false
in exactly that case.)

Normaliser limits, measured not assumed: case- and punctuation-insensitive, but
**accent-SENSITIVE** (`"rádio"` vs `"radio"` scores 1.0) and it does NOT normalise hyphens
(`"segunda-feira"` vs `"segunda feira"` scores 0.0). `wer_against` was checked against
hand-computable cases and an independent 900-pair sweep by the lane's verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr.constants import MODEL_DIR, PROVIDERS, SOTTO_ROOT  # noqa: E402

__all__ = ["main", "wer_against", "ARM_A_EN", "ARM_A_PT", "ARM_B_LANGS"]

# The two REAL speech clips already on this box. Both are 16 kHz mono PCM16 and are the
# registered parity inputs (constants.PARITY_EN / PARITY_PT), with an oracle transcript each.
ARM_A_EN = {
    "name": "A-en",
    "wav": SOTTO_ROOT / "_main" / "_redux-long" / "src-en-8s.wav",
    "oracle": SOTTO_ROOT / "_main" / "redux-en.txt",
    "language": "English",
}
ARM_A_PT = {
    "name": "A-pt",
    "wav": SOTTO_ROOT / "_main" / "_redux-long" / "src-pt-15s.wav",
    "oracle": SOTTO_ROOT / "_main" / "redux-ptbr.txt",
    "language": "Portuguese",
}

# ARM B: the four language arguments a caller might plausibly pass. A language switch that
# changes nothing is the defect; the graph check is what explains it.
ARM_B_LANGS = ["en", "pt", "Portuguese", "klingon"]

# ARM A's threshold, as a WORD ERROR RATE against the registered oracle. Zero, because the
# pre-existing parity harness already locks both clips at `ratio 1.0` / `char_diff_blocks 0`
# (`constants.PARITY_EN` / `PARITY_PT`: `ratio_min=1.0`, `max_char_diff_blocks=0`), so a
# regression here is a real regression and not a loosened tolerance. F1 (verifier): before
# this existed the arm could not fail on content at all.
ARM_A_MAX_WER = 0.0


# ---------------------------------------------------------------------------------------
# WER -- word-level edit distance, computed here because jiwer/editdistance are NOT on this
# box (verified: `import jiwer` -> ModuleNotFoundError). Plain DP over word tokens, Levenshtein
# with unit insert/delete/substitute cost.
# ---------------------------------------------------------------------------------------

def _norm_words(s: str) -> list[str]:
    s = re.sub(r"[^0-9a-záàâãéêíóôõúüçñ ]+", " ", s.lower())
    return [w for w in s.split() if w]


def wer_against(reference: str, hypothesis: str) -> dict:
    """Word error rate of `hypothesis` vs `reference`, with the substitution/insert/delete split.

    `reference` is the oracle transcript of another engine -- see the module docstring: this is
    AGREEMENT, not accuracy against human labels.
    """
    r, h = _norm_words(reference), _norm_words(hypothesis)
    n = len(r)
    if n == 0:
        # SAME KEYS as the normal branch. A partial dict here made the empty-reference case
        # raise KeyError on the caller instead of reporting (verifier F11).
        return {"wer": None, "wer_pct": None, "errors": None, "substitutions": None,
                "deletions": None, "insertions": None, "ref_words": 0, "hyp_words": len(h),
                "reason": "empty reference: no reference words, so no WER is defined"}
    d = [[0] * (len(h) + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    # Walk the table once to split the error types; a greedy re-walk would miscount.
    i, j, sub, dele, ins = n, len(h), 0, 0, 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (r[i - 1] != h[j - 1]):
            if r[i - 1] != h[j - 1]:
                sub += 1
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            dele += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    errors = d[n][len(h)]
    assert sub + dele + ins == errors, (sub, dele, ins, errors)
    return {
        "wer": round(errors / n, 6),
        "wer_pct": round(100.0 * errors / n, 3),
        "errors": errors,
        "substitutions": sub,
        "deletions": dele,
        "insertions": ins,
        "ref_words": n,
        "hyp_words": len(h),
    }


def oracle_last_line(p: Path) -> str:
    """redux-*.txt carry two header lines; the transcript is the LAST non-empty one.

    redux-ptbr.txt is cp1252, not UTF-8 (a 0xE1 at offset 135; parity.read_text_any:56). The
    decode actually used is ANNOUNCED on stderr, because scoring a mis-decoded reference would
    silently change characters -- and therefore the WER -- without anything looking wrong.
    """
    raw = Path(p).read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError as exc:
            print(f"NOTE: {p} is not valid {enc} ({exc}); trying the next encoding",
                  file=sys.stderr, flush=True)
            continue
        if enc != "utf-8":
            print(f"NOTE: {p} decoded as {enc}, NOT utf-8; the score below uses THIS decode",
                  file=sys.stderr, flush=True)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        return lines[-1].strip()
    raise RuntimeError(f"oracle file undecodable in utf-8/cp1252/latin-1: {p}")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def say(msg: str = "") -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------------------
# ARMS
# ---------------------------------------------------------------------------------------

def arm_a(case: dict, out: Path) -> dict:
    """Real speech WAV -> transcript, scored against the registered oracle."""
    from asr.runner import TranscribeConfig, transcribe

    wav, oracle = Path(case["wav"]), Path(case["oracle"])
    if not wav.exists():
        return {"arm": case["name"], "verdict": "FAIL", "why": f"wav missing: {wav}"}

    cfg = TranscribeConfig(wav=wav, level=False, label=case["name"])
    done = transcribe(cfg)
    ref = oracle_last_line(oracle)
    score = wer_against(ref, done["text"])
    th = done["threads"]

    out.write_text(done["text"], encoding="utf-8")
    exact = " ".join(done["text"].split()) == " ".join(ref.split())
    row = {
        "arm": case["name"],
        "wav": str(wav),
        "wav_audio_s": done["audio_s"],
        "wav_format": done["wav_format"],
        "language_of_clip": case["language"],
        "transcript": done["text"],
        "transcript_sha256": sha(done["text"]),
        "transcript_chars": len(done["text"]),
        "oracle": str(oracle),
        "oracle_ref_kind": "DIFFERENT ENGINE (Redux ternary) -- not human labels",
        "agrees_with_oracle": exact,
        "wer_vs_oracle": score,
        "wer_caveat": "agreement with another engine's transcript, NOT a human-labelled WER",
        "n_segments": done["n_segments"],
        "provider_requested": done["provider_requested"],
        "provider_loaded": th["session_providers"],
        # F4 (verifier pass 2): `all([])` is vacuously True, so an empty session list used to
        # report "cpu_only=True" without having looked at anything. Require a non-empty read.
        "provider_cpu_only": (bool(th["session_providers"])
                              and all(p == list(PROVIDERS) for p in th["session_providers"])),
        "language_conditioned": th["language_conditioned"],
        "metrics": {k: done[k] for k in ("load_s", "infer_s", "rtfx_steady", "rss_after_load_mb",
                                         "cpu_median_pct", "audio_s", "n_segments")},
    }
    problems = []
    if not done["text"].strip():
        problems.append("empty transcript")
    if not row["provider_cpu_only"]:
        problems.append(f"provider not CPU-only: {th['session_providers']}")
    if done["audio_s"] <= 0 or done["n_segments"] <= 0:
        problems.append("no audio or no segment produced")
    # F1 (verifier): THE SCORE MUST BE ABLE TO SAY NO. Without this the arm passed whenever a
    # transcript merely EXISTED, so a run that transcribed a whole different language -- or
    # pure noise -- would still print LANE9-GATE PASS. The oracle is a transcript of the same
    # clip by another engine, so requiring zero word errors is the tightest honest threshold
    # available: both registered clips measure exactly 0.0%.
    if score["wer"] is None:
        problems.append(f"no WER computable: {score.get('reason')}")
    elif score["wer"] > ARM_A_MAX_WER:
        problems.append(
            f"WER vs oracle {score['wer_pct']}% exceeds the {ARM_A_MAX_WER:.0%} threshold "
            f"({score['errors']} errors: sub={score['substitutions']} del={score['deletions']} "
            f"ins={score['insertions']}) -- the transcript does not match the trusted engine"
        )
    row["max_wer"] = ARM_A_MAX_WER
    row["verdict"] = "PASS" if not problems else "FAIL"
    row["why"] = "; ".join(problems) or (
        f"{done['n_segments']} segments, {len(done['text'])} chars, exact match with the oracle"
        if exact else f"WER vs oracle {score['wer_pct']}% ({score['errors']} errors)"
    )
    return row


def arm_b() -> dict:
    """The language prompt, proven BOTH ways: what the graph declares, what onnx_asr does with
    the kwarg, and what OUR engine does about it."""
    from asr.audio import read_slice
    from asr.engine import OnnxAsrEngine

    eng = OnnxAsrEngine()
    eng.load()
    asr = eng.model.asr

    # 1. The DECLARED graph inputs, read off the loaded sessions. This is the fact.
    graphs = {
        "encoder": [i.name for i in asr._encoder.get_inputs()],
        "decoder_joint": [i.name for i in asr._decoder_joint.get_inputs()],
    }
    lang_inputs = [n for names in graphs.values() for n in names
                   if n.lower() in ("lang_id", "language", "language_id", "lang")]
    conditioned = bool(lang_inputs)

    # 2. What onnx_asr does with the kwarg -- the silent no-op, measured per language.
    x_pt = read_slice(ARM_A_PT["wav"], 0.0, 0.0)
    base = eng.model.recognize(x_pt, sample_rate=16000)
    raw = {}
    for lang in ARM_B_LANGS:
        got = eng.model.recognize(x_pt, sample_rate=16000, language=lang)
        raw[lang] = {"sha256": sha(got), "chars": len(got), "identical_to_no_arg": got == base}

    # 3. What OUR engine does: refuses. Matching and mismatching language both.
    refusals = {}
    for lang in ("en", "pt", "klingon"):
        try:
            eng.recognize(x_pt, sample_rate=16000, language=lang)
            refusals[lang] = "ACCEPTED (no refusal)"
        except Exception as exc:  # noqa: BLE001 -- the refusal IS the measurement
            refusals[lang] = f"refused: {type(exc).__name__}"

    swallowed = [k for k, v in raw.items() if v["identical_to_no_arg"]]
    row = {
        "arm": "B-lang",
        "graph_inputs": graphs,
        "language_inputs_declared": lang_inputs,
        "language_conditioned": conditioned,
        "onnx_asr_raw_by_language": raw,
        "onnx_asr_swallows_every_language": len(swallowed) == len(ARM_B_LANGS),
        "swallowed": swallowed,
        "our_engine_by_language": refusals,
        "our_engine_refuses_all": all(v.startswith("refused") for v in refusals.values()),
        "probe_audio_s": round(len(x_pt) / 16000.0, 3),
    }
    problems = []
    if conditioned:
        # If a future export IS prompt-conditioned, this arm's premise changes and the gate
        # must say so rather than keep asserting a stale fact.
        problems.append(f"export now declares language input(s) {lang_inputs}: ARM B premise changed")
    if not row["onnx_asr_swallows_every_language"]:
        missing = set(ARM_B_LANGS) - set(swallowed)
        problems.append(f"onnx_asr no longer ignores the kwarg for {sorted(missing)}")
    if not row["our_engine_refuses_all"]:
        problems.append(f"engine accepted a language it cannot honour: {refusals}")
    row["verdict"] = "PASS" if not problems else "FAIL"
    row["why"] = "; ".join(problems) or (
        "graph declares NO language input; onnx_asr ignores the kwarg for all "
        f"{len(ARM_B_LANGS)} values (identical transcript); our engine refuses all of them"
    )
    return row


def arm_d() -> dict:
    """THE LIVE-ENGINE RED for the provider cure.

    F2 (verifier): `provider="cuda"` appeared ONLY inside the ARM C copy, so a live
    `_verify_provider` that had been neutered by a careless edit (an early `return`, say)
    would still have left all four arms green -- the cure would have had no red arm in the
    shipped code at all. This arm asks the LIVE engine, in the shipped package, for a
    provider this box cannot load, and requires the refusal. It is the arm that fails if
    someone deletes the cure.
    """
    from asr.engine import OnnxAsrEngine, ProviderUnavailableError

    row = {"arm": "D-provider-live", "provider_requested": "cuda"}
    try:
        OnnxAsrEngine(provider="cuda").load()
        row["outcome"] = "ACCEPTED"
        row["refused"] = False
    except ProviderUnavailableError as exc:
        row["outcome"] = f"refused: {exc}"
        row["refused"] = True
    except Exception as exc:  # noqa: BLE001 -- a different failure is still a failure to report
        row["outcome"] = f"refused, but by {type(exc).__name__}: {exc}"
        row["refused"] = True
        row["unexpected_exception"] = True

    # and the shipped arm must still work, i.e. the cure is not simply refusing everything
    try:
        good = OnnxAsrEngine(provider="cpu")
        good.load()
        row["cpu_arm_loads"] = True
        row["cpu_session_providers"] = good.session_providers
        row["cpu_only"] = (bool(good.session_providers)
                        and all(p == list(PROVIDERS) for p in good.session_providers))
    except Exception as exc:  # noqa: BLE001
        row["cpu_arm_loads"] = False
        row["cpu_only"] = False
        row["cpu_error"] = f"{type(exc).__name__}: {exc}"

    problems = []
    if not row["refused"]:
        problems.append("LIVE engine accepted --provider cuda on a box where CUDA does not load")
    if row.get("unexpected_exception"):
        problems.append("refused by the wrong exception type (not ProviderUnavailableError)")
    if not row.get("cpu_arm_loads") or not row.get("cpu_only"):
        problems.append(f"the shipped cpu arm stopped working: {row.get('cpu_error', row.get('cpu_session_providers'))}")
    row["verdict"] = "PASS" if not problems else "FAIL"
    row["why"] = "; ".join(problems) or (
        "the LIVE engine refuses --provider cuda (ProviderUnavailableError) and still loads "
        f"cpu-only {row.get('cpu_session_providers')}"
    )
    return row


def make_control_copy(root: Path) -> int:
    """Copy this package to `root/asr/` and strip BOTH cures, so the control runs pre-cure code.

    The copy is named `asr` on purpose: the control has to be importable as a package under a
    DIFFERENT root, and importing the live one would be the trap `constants.py:150-153`
    records -- a control that silently runs the product's own path and so can never go red.
    """
    if root.exists():
        shutil.rmtree(root)
    dst = root / "asr"
    dst.mkdir(parents=True)
    n = 0
    for f in Path(__file__).resolve().parent.glob("*.py"):
        shutil.copy2(f, dst / f.name)
        n += 1
    pyc = dst / "__pycache__"
    if pyc.exists():
        shutil.rmtree(pyc)

    eng = dst / "engine.py"
    t = eng.read_text(encoding="utf-8")
    if "        self._verify_provider(providers)\n" not in t:
        raise RuntimeError("control copy: the provider-verification call site moved; fix the revert")
    t = t.replace("        self._verify_provider(providers)\n", "")
    start = t.index("    def recognize(self, audio")
    end = t.index("    def phase_probe")
    t = t[:start] + (
        '    def recognize(self, audio, sample_rate: int = SAMPLE_RATE) -> str:\n'
        '        if self.model is None:\n'
        '            raise RuntimeError("engine.recognize() before engine.load()")\n'
        '        return self.model.recognize(audio, sample_rate=sample_rate)\n\n'
    ) + t[end:]
    eng.write_text(t, encoding="utf-8")

    # The runner in the copy must not demand the `language` kwarg the reverted engine lacks.
    # F3 (verifier): this `.replace()` used to be unguarded -- if the call site moved, the
    # replace would silently do nothing and the copy would raise TypeError for the wrong
    # reason, which looks like the defect under test. Assert the needle was really there.
    run = dst / "runner.py"
    r = run.read_text(encoding="utf-8")
    needle = "engine.recognize(audio, sample_rate=SAMPLE_RATE, language=cfg.language)"
    if needle not in r:
        raise RuntimeError(
            "control copy: the runner's recognize() call site moved; the copy would fail with "
            "TypeError for a reason that is not the cure. Fix the revert needle."
        )
    run.write_text(r.replace(needle, "engine.recognize(audio, sample_rate=SAMPLE_RATE)"),
                   encoding="utf-8")
    return n


def arm_c(root: Path) -> dict:
    """THE CONTROL: revert BOTH cures in a COPY and re-run the checks.

    A gate that only ever runs green proves nothing. This arm proves the instrument can say
    no: with `engine._verify_provider` and the `recognize` language refusal removed, the copy
    must ACCEPT a provider that did not load -- the exact silent-CPU-fallback defect -- and,
    through onnx_asr, ACCEPT a language the export cannot honour.
    """
    import importlib

    for m in [k for k in list(sys.modules) if k == "asr" or k.startswith("asr.")]:
        del sys.modules[m]
    sys.path.insert(0, str(root))
    try:
        ctl_engine = importlib.import_module("asr.engine")
        ctl_audio = importlib.import_module("asr.audio")
        ctl_src = str(importlib.import_module("asr").__file__)
    finally:
        sys.path.remove(str(root))
    for m in [k for k in list(sys.modules) if k == "asr" or k.startswith("asr.")]:
        del sys.modules[m]

    # HARD GATE: the control must be running the COPY. If this imports the live package the
    # control cannot fail, and an arm that cannot fail is decoration.
    if Path(ctl_src).resolve().parent != (root / "asr").resolve():
        raise RuntimeError(
            f"control imported {ctl_src}, which is NOT the copy at {root / 'asr'}; "
            "the control would be running the product's own path"
        )

    findings = {"control_imported_from": ctl_src}

    # The copy resolves REPO_ROOT from its own location (`constants.py:52`,
    # Path(__file__).parents[2]), so it would look for the model under `_main\models` and
    # fail with ModelDirError before reaching the cure. Pass the REAL model dir so the
    # control exercises the defect and not the path arithmetic.
    ctl_model = Path(importlib.import_module("asr.constants").MODEL_DIR)
    if ctl_model.resolve() != MODEL_DIR.resolve():
        ctl_model = MODEL_DIR
    findings["control_model_dir"] = str(ctl_model)

    # control 1: a provider that did not load must be ACCEPTED (the pre-cure behaviour)
    try:
        ctl_engine.OnnxAsrEngine(model_dir=ctl_model, provider="cuda").load()
        findings["cuda_silently_accepted"] = True
    except Exception as exc:  # noqa: BLE001
        findings["cuda_silently_accepted"] = False
        findings["cuda_error"] = f"{type(exc).__name__}: {exc}"

    # control 2: the copy's OWN recognize() must accept a language it cannot honour.
    #
    # F3 (verifier): the first draft called `e.model.recognize(...)` -- the raw onnx_asr
    # object, which is the same call ARM B already makes. That bypassed the reverted
    # `recognize` entirely, so this half of the control could not fail for the reason it
    # claims to test. It now goes through `e.recognize(...)`, the method the revert removed
    # the guard from, so a TypeError here means the revert did not take.
    if findings["cuda_silently_accepted"]:
        e = ctl_engine.OnnxAsrEngine(model_dir=ctl_model)
        e.load()
        x = ctl_audio.read_slice(ARM_A_PT["wav"], 0.0, 0.0)
        findings["ctl_recognize_takes_language"] = "language" in inspect.signature(e.recognize).parameters
        for lang in ("pt", "en"):
            try:
                e.recognize(x, sample_rate=16000, language=lang)
                findings[f"ctl_recognize_accepts_{lang}"] = "yes (silent no-op)"
            except TypeError as exc:
                # Expected for the PRE-CURE signature: the parameter does not exist at all.
                findings[f"ctl_recognize_accepts_{lang}"] = f"TypeError (pre-cure signature): {exc}"
            except Exception as exc:  # noqa: BLE001
                findings[f"ctl_recognize_accepts_{lang}"] = f"no: {type(exc).__name__}: {exc}"
        # And the raw path a caller would actually reach, recorded as context.
        base = e.recognize(x, sample_rate=16000)
        for lang in ("pt", "en"):
            got = e.model.recognize(x, sample_rate=16000, language=lang)
            findings[f"onnx_asr_swallow_{lang}"] = (
                f"{len(got)} chars, sha {sha(got)[:12]}, identical_to_no_arg={got == base}"
            )

    # The control PASSES only when BOTH pre-cure defects are visible in the copy: the
    # provider accepted, and the reverted `recognize` has no language guard to raise.
    reproduced = (findings.get("cuda_silently_accepted") is True
                  and findings.get("ctl_recognize_takes_language") is False)
    row = {
        "arm": "C-control",
        "copy_dir": str(root / "asr"),
        "copy_engine_sha256": "",
        "findings": findings,
        "expect": "cures removed => cuda is silently accepted and onnx_asr swallows a language",
        "verdict": "PASS" if reproduced else "FAIL",
        "why": ("control reproduced the pre-cure defect: the copy accepted a provider that did "
                "not load, and onnx_asr accepted a language the export cannot honour"
                if reproduced else f"control did NOT reproduce the defect: {findings}"),
    }
    return row


def selfcheck() -> int:
    """The NEGATIVE instruments: prove the arms CAN say no. No model is loaded.

    These exist because verifier pass 1 found the gate could not fail where it mattered:
    F1 (ARM A passed on any non-empty transcript, WER 100 % included) and F2 (the provider
    cure had no red arm in the shipped code). A gate nobody has watched go red is an ornament,
    so the red cases are shipped next to the green ones and re-run in one command.
    """
    boxes: list[tuple[str, bool, str]] = []

    # NEG-1  ARM A must FAIL on a wrong transcript. Injects a done-shaped dict carrying text
    # from the wrong language, so no model load is needed.
    import asr.runner as runner

    real_transcribe = runner.transcribe

    def wrong_text(cfg, on_event=None):
        return {
            "text": " uma frase completamente diferente no idioma errado ",
            "audio_s": 8.543, "n_segments": 2,
            "wav_format": {"path": str(cfg.wav), "sample_rate": 16000, "channels": 1,
                           "sampwidth": 2, "frames": 136689, "duration_s": 8.543},
            "threads": {"intra": 4, "inter": 1, "env": {},
                        "session_providers": [["CPUExecutionProvider"]],
                        "graph_inputs": {}, "language_conditioned": False, "model_name": "x",
                        "onnx_asr": "0", "onnxruntime": "1"},
            "provider_requested": "cpu", "load_s": 2.0, "infer_s": 1.0, "rtfx_steady": 3.0,
            "rss_after_load_mb": 700.0, "cpu_median_pct": 400.0, "segments": [],
        }

    runner.transcribe = wrong_text
    globals()["transcribe"] = wrong_text
    try:
        row = arm_a(ARM_A_EN, Path(tempfile.gettempdir()) / "lane9-selfcheck-armA.txt")
        boxes.append(("NEG-1 ARM A red on a wrong transcript", row["verdict"] == "FAIL",
                      f"verdict={row['verdict']} wer={row['wer_vs_oracle']['wer_pct']}% :: {row['why']}"))
    finally:
        runner.transcribe = real_transcribe
        globals()["transcribe"] = real_transcribe

    # NEG-2  wer_against on hand-computable cases, including the empty-reference shape (F11).
    for ref, hyp, exp, label in (("a b c", "a b c", 0.0, "identical"),
                                 ("a b c", "a b", 1 / 3, "deletion"),
                                 ("a b c", "a b c d", 1 / 3, "insertion"),
                                 ("a b c", "a x c", 1 / 3, "substitution"),
                                 ("a b c d", "a b", 2 / 4, "two deletions"),
                                 ("a b c d e", "x b c d y", 2 / 5, "two substitutions")):
        got = wer_against(ref, hyp)
        # Compare the ROUNDED value the function actually reports. Comparing the raw float
        # against 1/3 with a 1e-9 tolerance fails on rounding alone -- the first draft of this
        # selfcheck reported 3 false BADs for exactly that reason.
        ok = abs(round(got["wer"], 6) - round(exp, 6)) < 1e-9
        boxes.append((f"NEG-2 wer {label}", ok,
                      f"exp={round(exp, 6):.6f} got={got['wer']:.6f} sub={got['substitutions']} "
                      f"del={got['deletions']} ins={got['insertions']}"))
    # F11: the empty-reference branch must expose the same FIELDS the normal branch does, or a
    # caller reading `errors` gets a KeyError exactly when the score is least defined. The
    # `reason` key is diagnostic and is present only on the empty branch, so it is excluded.
    empty = wer_against("", "a b")
    normal = wer_against("a b", "b")
    missing = sorted(set(normal) - set(empty))
    boxes.append(("NEG-2 wer empty-reference shape parity", not missing,
                  f"missing_keys={missing or 'none'} empty_keys={sorted(empty)}"))

    # NEG-3  the provider check must fail CLOSED in every unprovable or mismatched state (F4).
    from asr.engine import OnnxAsrEngine

    def verdict(provider, sessions):
        e = OnnxAsrEngine(provider=provider)
        e.session_providers = sessions
        try:
            e._verify_provider(["CUDAExecutionProvider", "CPUExecutionProvider"])
            return "ACCEPTED"
        except Exception as exc:  # noqa: BLE001 -- the refusal is the measurement
            return f"REFUSED:{type(exc).__name__}"

    for label, provider, sessions, want in (
        ("cpu + CPU only", "cpu", [["CPUExecutionProvider"]], "ACCEPTED"),
        ("cpu + CUDA promoted", "cpu", [["CUDAExecutionProvider"]], "REFUSED"),
        ("cpu + TensorRT", "cpu", [["TensorrtExecutionProvider"]], "REFUSED"),
        ("cuda + loaded", "cuda", [["CUDAExecutionProvider", "CPUExecutionProvider"]], "ACCEPTED"),
        ("cuda + fell back", "cuda", [["CPUExecutionProvider"]], "REFUSED"),
        ("cuda + no session", "cuda", [], "REFUSED"),
        ("cpu  + no session", "cpu", [], "REFUSED"),
    ):
        got = verdict(provider, sessions)
        boxes.append((f"NEG-3 provider {label}", got.startswith(want), f"{got} (want {want})"))

    # NEG-4  the control copy must be a DIFFERENT package from the live one.
    root = Path(tempfile.gettempdir()) / "lane9-selfcheck-ctl"
    make_control_copy(root)
    ctl = arm_c(root)
    boxes.append(("NEG-4 control imports the COPY, not the live package",
                  "lane9-selfcheck-ctl" in ctl["findings"].get("control_imported_from", ""),
                  ctl["findings"].get("control_imported_from", "?")))
    boxes.append(("NEG-4 control reproduces the pre-cure defect", ctl["verdict"] == "PASS",
                  ctl["why"]))

    say("=== SELFCHECK -- the negative instruments (no model loaded) ===")
    for name, ok, detail in boxes:
        say(f"  {'OK ' if ok else 'BAD'} {name}")
        say(f"      {detail}")
    bad = [n for n, ok, _ in boxes if not ok]
    say()
    say(f"BOXES {len(boxes)}  pass={len(boxes) - len(bad)}  fail={len(bad)}")
    for n in bad:
        say(f"  FAILED: {n}")
    if bad:
        say("LANE9-SELFCHECK FAIL")
        return 1
    say("LANE9-SELFCHECK PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="asr.gate", description="LANE9 end-to-end ASR gate")
    p.add_argument("--json", default="", help="write the full result here")
    p.add_argument("--skip-c", action="store_true", help="skip the control (NOT a full run)")
    p.add_argument("--selfcheck", action="store_true",
                   help="run the NEGATIVE instruments (do the arms go red when they should?) "
                        "instead of the gate; loads no model, writes nothing into the repo")
    args = p.parse_args(argv)

    if args.selfcheck:
        return selfcheck()

    outdir = Path(__file__).resolve().parent.parent.parent / "_main"
    outdir.mkdir(parents=True, exist_ok=True)
    results = []

    for case in (ARM_A_EN, ARM_A_PT):
        say(f"=== ARM {case['name']} :: real speech ({case['language']}) -> transcript ===")
        row = arm_a(case, outdir / f"lane9-{case['name']}.txt")
        results.append(row)
        say(f"  wav        : {row['wav']}")
        if "wav_audio_s" in row:
            say(f"  audio      : {row['wav_audio_s']}s, {row['wav_format']['sample_rate']} Hz "
                f"{row['wav_format']['channels']}ch sampwidth={row['wav_format']['sampwidth']}")
            say(f"  transcript : {row['transcript']}")
            say(f"  oracle     : {row['oracle']}  [{row['oracle_ref_kind']}]")
            say(f"  agrees     : {row['agrees_with_oracle']}   chars={row['transcript_chars']}")
            w = row["wer_vs_oracle"]
            if w.get("wer") is not None:
                say(f"  WER vs oracle: {w['wer_pct']}%  ({w['errors']} errors over {w['ref_words']} "
                    f"ref words; sub={w['substitutions']} del={w['deletions']} ins={w['insertions']})")
            say(f"  CAVEAT     : {row['wer_caveat']}")
            say(f"  provider   : requested={row['provider_requested']} loaded={row['provider_loaded']} "
                f"cpu_only={row['provider_cpu_only']}")
        say(f"  VERDICT    : {row['verdict']}  {row['why']}")
        say()

    say("=== ARM B :: the language prompt, both directions ===")
    row = arm_b()
    results.append(row)
    say(f"  graph encoder      : {row['graph_inputs']['encoder']}")
    say(f"  graph decoder_joint: {row['graph_inputs']['decoder_joint']}")
    say(f"  language inputs    : {row['language_inputs_declared'] or 'NONE -- not prompt-conditioned'}")
    say(f"  onnx_asr ignores kwarg for all {len(ARM_B_LANGS)} values: "
        f"{row['onnx_asr_swallows_every_language']}  ({', '.join(row['swallowed'])})")
    say(f"  our engine         : {row['our_engine_by_language']}")
    say(f"  VERDICT    : {row['verdict']}  {row['why']}")
    say()

    say("=== ARM D :: the LIVE engine refuses a provider this box cannot load ===")
    row = arm_d()
    results.append(row)
    say(f"  requested  : {row['provider_requested']}  -> {row['outcome']}")
    say(f"  cpu arm    : loads={row.get('cpu_arm_loads')} cpu_only={row.get('cpu_only')} "
        f"{row.get('cpu_session_providers', '')}")
    say(f"  VERDICT    : {row['verdict']}  {row['why']}")
    say()

    if args.skip_c:
        # F: a partial run must NOT print the same PASS line as a full one -- an honest
        # omission is not a green (verifier self-audit item 4).
        say("=== ARM C :: control SKIPPED (--skip-c): this run proves NOTHING about the cures ===")
        say("LANE9-GATE INCOMPLETE (control skipped) -- NOT a pass")
        return 2
    else:
        say("=== ARM C :: the control: cures reverted in a COPY, must go red ===")
        ctl = Path(tempfile.gettempdir()) / "lane9-ctl"
        nfiles = make_control_copy(ctl)
        row = arm_c(ctl)
        row["files_copied"] = nfiles
        row["copy_engine_sha256"] = sha256_file(ctl / "asr" / "engine.py")
        results.append(row)
        say(f"  copy        : {ctl / 'asr'}  ({nfiles} modules, engine.py sha256 {row['copy_engine_sha256'][:16]})")
        say(f"  imported    : {row['findings'].get('control_imported_from')}")
        for k, v in row["findings"].items():
            if k == "control_imported_from":
                continue
            say(f"  {k:26s}: {v}")
        say(f"  VERDICT    : {row['verdict']}  {row['why']}")
        ok = all(r["verdict"] == "PASS" for r in results)
        say()

    passed = sum(1 for r in results if r["verdict"] == "PASS")
    say(f"ARMS {len(results)}  pass={passed}  fail={len(results) - passed}")
    for r in results:
        if r["verdict"] != "PASS":
            say(f"  FAILED: {r['arm']} -- {r['why']}")
    if args.json:
        Path(args.json).write_text(json.dumps({"arms": results}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")

    # The provider fact is printed on EVERY run: a gate that passes on a silent CPU fallback
    # is exactly the failure this repo already paid for once.
    say(f"PROVIDERS(shipped, requested, verified) = {list(PROVIDERS)}")
    if ok:
        say("LANE9-GATE PASS")
        return 0
    say("LANE9-GATE FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())