#!/usr/bin/env python
# NO-BUG: instrumento (2026-11-25) da colocacao de pontuacao em CPU e da recusa de cuda por nome -- usa um motor FALSO, nao carrega pesos, nao corrige o produto
"""CPU punctuation placement and fail-closed policy, checked without weights.

`worker/punctuation_model.py` used to be dead at runtime: an unprovable GPU
placement flag refused `load()` before model discovery, so the 7.1 MB int8
English restorer never ran. The repair asks for CPU **by name** (`PROVIDER`,
`THREADS`) and refuses a `cuda` request by name, like the diarizer's
`DIARIZER_PROVIDER`. This oracle runs the real module against a FAKE
`sherpa_onnx`: no weights, no native runtime, no window, no audio device.

Arms:
  provider-cpu  CPU builds the engine once from a fake native module; config
                carries provider=cpu / num_threads=1; placement printed once;
                `log_line()` can report the provider without raising.
  lang-pt-skip  a non-en tag returns the text BYTE-IDENTICALLY and neither
                loads nor calls the model (including an explicit pt argument).
  model-absent  missing model/vocab files fail closed with reason=model-absent;
                no native import, no constructor.
  env-off       SOTTO_PUNCT_MODEL=0 refuses with reason=disabled-by-env.
  cuda-refused  a `cuda` request is refused BY NAME with
                reason=provider-cuda-refused, before disk/import/constructor.

`--neg-arm` mutates a copy of the module for every arm and requires that arm to
go RED, printing which mutation which arm caught. Every verdict is printed by
the decider with its exit code (0 PASS / 1 FAIL).

    python _main/punctuation-oracle.py
    python _main/punctuation-oracle.py --neg-arm
"""
from __future__ import annotations

import builtins
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORKER = ROOT / "worker"
MODULE = WORKER / "punctuation_model.py"

EXIT_PASS, EXIT_FAIL = 0, 1
EN_SAMPLE = "hello there how are you doing today"
PLACEMENT = "PUNCT_PLACEMENT provider=cpu threads=1"
THREADS_EXPECTED = 1  # declared budget in the module, independently asserted here


@contextlib.contextmanager
def model_dir(present: bool = True):
    """Fake model/vocab pair in a temp dir; routine runs never load weights."""
    with tempfile.TemporaryDirectory(prefix="punct-oracle-") as tmp:
        root = Path(tmp)
        if present:
            (root / "model.int8.onnx").write_bytes(b"fake-graph")
            (root / "bpe.vocab").write_text("fake-vocab", encoding="utf-8")
        yield str(root)


@contextlib.contextmanager
def fake_sherpa(rec: dict):
    """Install a recording `sherpa_onnx` -- no native import, no real engine."""
    native = types.ModuleType("sherpa_onnx")

    class OnlinePunctuationModelConfig:
        def __init__(self, **kwargs):
            rec["model_cfg"] = dict(kwargs)

    class OnlinePunctuationConfig:
        def __init__(self, *args, **kwargs):
            rec["cfg"] = {"positional": len(args), **kwargs}

    class OnlinePunctuation:
        def __init__(self, cfg):
            rec["built"] += 1

        def add_punctuation_with_case(self, text):
            rec["infer"] += 1
            return "hello there, how are you doing today."

    native.OnlinePunctuationModelConfig = OnlinePunctuationModelConfig
    native.OnlinePunctuationConfig = OnlinePunctuationConfig
    native.OnlinePunctuation = OnlinePunctuation
    prior = sys.modules.get("sherpa_onnx")
    sys.modules["sherpa_onnx"] = native
    original_import = builtins.__import__

    def tracked_import(name, *args, **kwargs):
        if name == "sherpa_onnx":
            rec["imports"] += 1
        return original_import(name, *args, **kwargs)

    builtins.__import__ = tracked_import
    try:
        yield native
    finally:
        builtins.__import__ = original_import
        if prior is None:
            sys.modules.pop("sherpa_onnx", None)
        else:
            sys.modules["sherpa_onnx"] = prior


def recorder() -> dict:
    return {"model_cfg": None, "cfg": None, "built": 0, "infer": 0, "imports": 0}


def load_module(path: Path, tag: str):
    """A fresh module per arm: the engine and state are memoized per module."""
    name = "punct_oracle_" + tag
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def report(checks) -> tuple[bool, str]:
    bad = [name for ok, name in checks if not ok]
    detail = "all checks green" if not bad else "FAILED: " + ", ".join(bad)
    return not bad, detail


def arm_provider_cpu(path: Path) -> tuple[bool, str]:
    rec = recorder()
    with fake_sherpa(rec), model_dir() as root:
        pm = load_module(path, "cpu")
        pm.set_lang("en-US")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            engine = pm.load(root=root)
        out = pm.punctuate(EN_SAMPLE, root=root)
        cfg = rec["model_cfg"] or {}
        status = pm.status()
        printed = stdout.getvalue().strip().splitlines()
        return report([
            (engine is not None and rec["built"] == 1, "engine built once from fake native"),
            (status["reason"] == "loaded", "reason=loaded"),
            (cfg.get("provider") == "cpu", "config provider=cpu"),
            (cfg.get("num_threads") == THREADS_EXPECTED
             and pm.THREADS == THREADS_EXPECTED
             and status["threads"] == THREADS_EXPECTED, "declared thread ceiling"),
            (printed == [PLACEMENT], "placement printed once: %r" % printed),
            (status["provider"] == "cpu", "status provider=cpu"),
            (out != EN_SAMPLE and rec["infer"] >= 1, "built engine actually used"),
            ("provider=cpu" in pm.log_line(), "log_line names provider without raising"),
        ])


def arm_lang_skip(path: Path) -> tuple[bool, str]:
    rec = recorder()
    with fake_sherpa(rec), model_dir() as root:
        pm = load_module(path, "lang")
        calls = {"load": 0, "infer": 0}

        class Spy:
            """An engine that would be called if the language guard broke."""

            def add_punctuation_with_case(self, _text):
                calls["infer"] += 1
                return "hello there, how are you doing today."

        pm._ENGINE = Spy()
        pm.load = lambda *_a, **_kw: (calls.__setitem__(
            "load", calls["load"] + 1) or pm._ENGINE)
        pm.set_lang("pt-BR")
        out_proc = pm.punctuate(EN_SAMPLE, root=root)
        pm.set_lang("en-US")
        out_arg = pm.punctuate(EN_SAMPLE, tag="pt-BR", root=root)
        return report([
            (out_proc == EN_SAMPLE, "pt process tag returns byte-identical text"),
            (out_arg == EN_SAMPLE, "explicit pt argument returns byte-identical text"),
            (calls["load"] == 0, "load() never called for pt"),
            (calls["infer"] == 0, "model never called for pt"),
            (not pm.supported_lang("pt-BR"), "supported_lang still en-only"),
        ])


def arm_model_absent(path: Path) -> tuple[bool, str]:
    rec = recorder()
    with fake_sherpa(rec), model_dir(present=False) as root:
        pm = load_module(path, "absent")
        pm.set_lang("en-US")
        out = pm.punctuate(EN_SAMPLE, root=root)
        status = pm.status()
        return report([
            (out == EN_SAMPLE, "text unchanged without files"),
            (status["reason"] == "model-absent", "named reason=model-absent"),
            (not status["engine"], "no engine"),
            (rec["imports"] == 0, "no native import"),
            (rec["built"] == 0, "no engine constructor"),
        ])


def arm_env_off(path: Path) -> tuple[bool, str]:
    rec = recorder()
    os.environ["SOTTO_PUNCT_MODEL"] = "0"
    try:
        with fake_sherpa(rec), model_dir() as root:
            pm = load_module(path, "env")
            pm.set_lang("en-US")
            out = pm.punctuate(EN_SAMPLE, root=root)
            status = pm.status()
            return report([
                (out == EN_SAMPLE, "text unchanged with SOTTO_PUNCT_MODEL=0"),
                (status["reason"] == "disabled-by-env", "named reason=disabled-by-env"),
                (rec["imports"] == 0, "no native import"),
                (rec["built"] == 0, "no engine constructor"),
            ])
    finally:
        os.environ.pop("SOTTO_PUNCT_MODEL", None)


def arm_env_bad_value(path: Path) -> tuple[bool, str]:
    """`SOTTO_PUNCT_MODEL=garbage` must NOT enable the model (reviewer finding).

    The first version of `_env_allows` was a deny-list: any value it did not
    recognise fell through to `True`, so a typo turned the model ON -- the
    expensive side. A switch whose invalid value picks the costlier branch is
    not a switch, and the oracles did not notice because they only ever set the
    documented `0`.
    """
    rec = recorder()
    out_rows = []
    ok = True
    for bad in ("garbage", "2", "ENABLE", " 1x "):
        os.environ["SOTTO_PUNCT_MODEL"] = bad
        try:
            with fake_sherpa(rec), model_dir() as root:
                pm = load_module(path, "envbad")
                pm.set_lang("en-US")
                text = pm.punctuate(EN_SAMPLE, root=root)
                status = pm.status()
                this_ok = bool(
                    text == EN_SAMPLE
                    and status["engine"] is None
                    and str(status["reason"]).startswith("bad-env-value")
                    and rec["imports"] == 0
                    and rec["built"] == 0)
                ok = ok and this_ok
                out_rows.append("%r->%s" % (bad, "off" if this_ok else
                                            "ON(%s)" % (status["reason"],)))
        finally:
            os.environ.pop("SOTTO_PUNCT_MODEL", None)
    return report([(ok, " ".join(out_rows))])


def arm_env_on(path: Path) -> tuple[bool, str]:
    """`SOTTO_PUNCT_MODEL=1` still means ON (the allowlist did not break the switch)."""
    rec = recorder()
    os.environ["SOTTO_PUNCT_MODEL"] = "1"
    try:
        with fake_sherpa(rec), model_dir() as root:
            pm = load_module(path, "envon")
            pm.set_lang("en-US")
            text = pm.punctuate(EN_SAMPLE, root=root)
            status = pm.status()
            return report([
                (text != EN_SAMPLE, "SOTTO_PUNCT_MODEL=1 punctuates"),
                (status["engine"] is not None, "engine built"),
                (rec["built"] == 1, "one engine constructor"),
            ])
    finally:
        os.environ.pop("SOTTO_PUNCT_MODEL", None)


def arm_cuda_refused(path: Path) -> tuple[bool, str]:
    rec = recorder()
    with fake_sherpa(rec), model_dir() as root:
        pm = load_module(path, "cuda")
        pm.PROVIDER = "cuda"
        pm.set_lang("en-US")
        out = pm.punctuate(EN_SAMPLE, root=root)
        status = pm.status()
        return report([
            (out == EN_SAMPLE, "cuda request leaves text unchanged"),
            (status["reason"] == "provider-cuda-refused", "refused BY NAME"),
            (status["provider"] == "cuda", "status names the refused request"),
            (rec["imports"] == 0, "no native import"),
            (rec["built"] == 0, "no engine constructor"),
        ])


ARMS = {
    "provider-cpu": arm_provider_cpu,
    "lang-pt-skip": arm_lang_skip,
    "model-absent": arm_model_absent,
    "env-off": arm_env_off,
    "cuda-refused": arm_cuda_refused,
}

#: (mutation name, arm it must redden, exact source anchor, replacement, why)
MUTATIONS = [
    ("provider-config", "provider-cpu",
     "                    provider=requested,\n",
     "                    provider=\"cuda\",\n",
     "the config no longer asks for cpu"),
    ("thread-ceiling", "provider-cpu",
     "THREADS = 1\n", "THREADS = 4\n",
     "the declared thread ceiling is raised"),
    ("language-guard", "lang-pt-skip",
     "    if not supported_lang(tag):\n", "    if False:\n",
     "the en-only guard is disarmed"),
    ("model-presence", "model-absent",
     "        if d is None:\n", "        if False:\n",
     "absent model files no longer fail closed"),
    ("env-disable", "env-off",
     "        if not _env_allows():\n", "        if False:\n",
     "SOTTO_PUNCT_MODEL=0 is ignored"),
    ("cuda-refusal", "cuda-refused",
     "    if requested == \"cuda\":\n", "    if requested == \"gpu\":\n",
     "cuda is no longer refused by name"),
]


def run_arm_in_child(arm: str, path: Path) -> tuple[int, str]:
    env = dict(os.environ)
    env.pop("SOTTO_PUNCT_MODEL", None)
    command = [sys.executable, str(Path(__file__).resolve()),
               "--arm", arm, "--module", str(path)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              env=env, timeout=90)
    except subprocess.TimeoutExpired:
        return EXIT_FAIL, "TIMEOUT"
    return proc.returncode, (proc.stdout or proc.stderr or "").strip()


def normal() -> int:
    failed = 0
    for name, fn in ARMS.items():
        try:
            ok, detail = fn(MODULE)
        except Exception as exc:  # an oracle crash is never a green arm
            ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
        print("%s  %-14s %s" % ("PASS" if ok else "FAIL", name, detail))
        failed += not ok
    print("\n%d/%d arms green" % (len(ARMS) - failed, len(ARMS)))
    print("VERDICT:", "FAIL" if failed else "PASS")
    return EXIT_FAIL if failed else EXIT_PASS


def neg_arm() -> int:
    source = MODULE.read_text(encoding="utf-8")
    bad = 0
    for name, arm, old, new, why in MUTATIONS:
        if source.count(old) != 1:
            print("NEG-ARM %s FAIL -- anchor found %d times (stale mutation)"
                  % (name, source.count(old)))
            bad += 1
            continue
        with tempfile.TemporaryDirectory(prefix="punct-neg-") as tmp:
            mutant = Path(tmp) / "punctuation_model.py"
            mutant.write_text(source.replace(old, new, 1), encoding="utf-8")
            rc, out = run_arm_in_child(arm, mutant)
        if rc != EXIT_PASS:
            print("NEG-ARM %s PASS -- arm %s RED (%s): %s"
                  % (name, arm, why, out.splitlines()[-1] if out else "no output"))
        else:
            print("NEG-ARM %s FAIL -- arm %s stayed GREEN (%s)"
                  % (name, arm, why))
            bad += 1
    print("\n%d/%d mutations reddened their arm" % (len(MUTATIONS) - bad, len(MUTATIONS)))
    # HOUSE CONVENTION for a control run: exit 1 when the injected defects were
    # all caught (`:expectred` in the battery demands rc=1), 2 when the control
    # itself failed. The positive run keeps 0/1.
    print("NEG-ARM VERDICT:", "PASS" if not bad else "FAIL")
    return 2 if bad else 1


def main() -> int:
    argv = sys.argv[1:]
    if "--arm" in argv:
        name = argv[argv.index("--arm") + 1]
        path = (Path(argv[argv.index("--module") + 1])
                if "--module" in argv else MODULE)
        if name not in ARMS:
            print("ARM %s UNKNOWN" % name)
            return EXIT_FAIL
        return run_arm_in_process(name, path)
    if "--neg-arm" in argv:
        return neg_arm()
    return normal()


def run_arm_in_process(name: str, path: Path) -> int:
    try:
        ok, detail = ARMS[name](path)
    except Exception as exc:
        ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
    print("ARM %s %s %s" % (name, "GREEN" if ok else "RED", detail))
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
