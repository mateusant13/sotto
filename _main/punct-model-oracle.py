#!/usr/bin/env python
# NO-BUG: ordem do dono de 2026-11-05 *"usa pontuacao de forma inteligente"* -- trabalho de CAPACIDADE sobre pontuacao opcional, sem id no `_main/bug-ledger.json`
"""Optional punctuation behavior and GPU policy, checked without model weights.

Ordem do dono (2026-11-05, verbatim): *"por que a gente nao normaliza as frases
ou usa pontuacao de forma inteligente?"*. `worker/punctuation_model.py` has an
optional English Sherpa punctuation path. The installed native API accepts a
CUDA provider request but offers no CPU-fallback disable or device/node
readback; production therefore refuses before model discovery/import/creation.
This oracle runs the real text/startup policy functions -- not a model:

  A. `punctuate()` on English text returns punctuation using a fake engine;
     routine checks never load or invoke optional weights;
  B. a GUARDA DE LINGUA: `pt-BR` e `None` devolvem o texto BYTE-IDENTICO. Nao e'
     zelo: medido nesta maquina, o modelo ingles sobre portugues devolve
     `"EU Gosto Muito, disso sabe como E que E"` -- caixa aleatoria com
     aparencia de pontuacao, que e' pior do que nao pontuar;
  C. o `?` a meio de uma hipotese parcial e' removido (`that I? didn't` foi
     medido no log dele) e um comma que FECHA a linha tambem;
  D. provider-list CUDA with CPU, unknown, or CUDA-only census refuses before
     model discovery, package setup/import, constructor, or inference; input
     text remains byte-identical and `status()` reports the refusal;
  E. o `LineFormer._event` pontua a linha FECHADA e nao a parcial -- a fiacao,
     exercitada no objecto real.

The `--neg-arm` controls mutate copies and require all six regressions to go
RED, including an inverted native GPU-placement guard.

Uso:
    python _main/punct-model-oracle.py
    python _main/punct-model-oracle.py --gpu-policy-only
    python _main/punct-model-oracle.py --neg-arm
"""
from __future__ import annotations

import ast
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORKER = ROOT / "worker"
sys.path.insert(0, str(WORKER))

EXIT_PASS, EXIT_FAIL = 0, 1

#: O texto que o modelo tem de pontuar. Escolhido para ser INEQUIVOCO: duas
#: oracoes justapostas sem marca.
EN_SAMPLE = "hello there how are you doing today"
PT_SAMPLE = "eu gosto muito disso sabe como e que e"

results: list[tuple[bool, str, str]] = []


def add(ok: bool, name: str, detail: str = "") -> None:
    results.append((bool(ok), name, detail))


def _fresh_module():
    """Um modulo NOVO por arm: o motor e' memoizado por modulo."""
    for name in list(sys.modules):
        if name == "punctuation_model":
            del sys.modules[name]
    import punctuation_model  # noqa: PLC0415

    return punctuation_model


def _model_present() -> bool:
    d = WORKER / "models" / "punct-en"
    return (d / "model.int8.onnx").is_file() and (d / "bpe.vocab").is_file()


class _FakePunctuationEngine:
    """Model-free consumer fixture; routine oracle runs never load weights."""

    def add_punctuation_with_case(self, _text):
        return "hello there, how are you doing today."


def _startup_punctuation_guard():
    """Return the real startup `if supported_lang: load()` node from worker AST."""
    source = (WORKER / "sotto_worker.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        calls = [child for child in ast.walk(node.test)
                 if isinstance(child, ast.Call)]
        body_calls = [child for child in ast.walk(ast.Module(
            body=node.body, type_ignores=[])) if isinstance(child, ast.Call)]
        if (any(ast.unparse(call.func) == "punctuation_model.supported_lang"
                for call in calls)
                and any(ast.unparse(call.func) == "punctuation_model.load"
                        for call in body_calls)):
            return node
    raise AssertionError("real punctuation startup guard was not found")


def gpu_policy_controls(module_path=None) -> list[tuple[bool, str, str]]:
    """Exercise the real startup load guard with a fake native public API."""
    import builtins  # noqa: PLC0415

    rows = []

    def run_case(label, census):
        with tempfile.TemporaryDirectory(prefix="punct-gpu-policy-") as tmp:
            root = Path(tmp)
            (root / "model.int8.onnx").write_bytes(b"fake-graph")
            (root / "bpe.vocab").write_text("fake-vocab", encoding="utf-8")
            seen = {"find": 0, "ensure": 0, "import": 0,
                    "construct": 0, "infer": 0}

            class Device:
                def __init__(self, ep_name):
                    self.ep_name = ep_name

            class Config:
                def __init__(self, *args, **kwargs):
                    seen["construct"] += 1

            class GenericEngine(_FakePunctuationEngine):
                def __init__(self, _config):
                    seen["construct"] += 1

                def add_punctuation_with_case(self, text):
                    seen["infer"] += 1
                    return "hello there, how are you doing today."

            native = types.ModuleType("sherpa_onnx")
            # The provider list is deliberately misleading in the CPU and
            # unknown arms: only a strict native placement API could use it.
            native.get_available_providers = lambda: [
                "CUDAExecutionProvider", "CPUExecutionProvider"]
            native.OnlinePunctuationModelConfig = Config
            native.OnlinePunctuationConfig = Config
            native.OnlinePunctuation = GenericEngine
            if census is not None:
                native.get_ep_devices = lambda: [Device(census)]

            prior_native = sys.modules.get("sherpa_onnx")
            sys.modules["sherpa_onnx"] = native
            if module_path is None:
                pm = _fresh_module()
            else:
                sys.modules.pop("punctuation_model", None)
                module_spec = importlib.util.spec_from_file_location(
                    "punctuation_model_policy_mutant", module_path)
                pm = importlib.util.module_from_spec(module_spec)
                module_spec.loader.exec_module(pm)
            pm.set_lang("en-US")
            original_find = pm.find_model
            original_ensure = pm._ensure_package_importable
            pm.find_model = lambda _root=None: (seen.__setitem__("find", seen["find"] + 1)
                                                or root)
            pm._ensure_package_importable = lambda _d: seen.__setitem__(
                "ensure", seen["ensure"] + 1)
            original_import = builtins.__import__

            def tracked_import(name, *args, **kwargs):
                if name == "sherpa_onnx":
                    seen["import"] += 1
                return original_import(name, *args, **kwargs)

            builtins.__import__ = tracked_import
            try:
                # Execute the actual worker startup guard, then the real
                # punctuation consumer. Both must preserve the ASR text.
                startup = _startup_punctuation_guard()
                exec(compile(ast.Module(body=[startup], type_ignores=[]),
                             "sotto_worker.py", "exec"),
                     {"punctuation_model": pm})
                text_out = pm.punctuate(EN_SAMPLE, root=root)
                result = {
                    "reason": pm.status()["reason"],
                    "text": text_out,
                    **seen,
                }
            finally:
                builtins.__import__ = original_import
                pm.find_model = original_find
                pm._ensure_package_importable = original_ensure
                if prior_native is None:
                    sys.modules.pop("sherpa_onnx", None)
                else:
                    sys.modules["sherpa_onnx"] = prior_native
            return result

    for label, census, reason in (
        ("provider-list-cuda-device-cpu", "CPUExecutionProvider",
         "CUDA provider list cannot override CPU-only native census"),
        ("provider-list-cuda-device-unknown", None,
         "unknown native census refuses before startup model discovery"),
        ("provider-list-cuda-device-cuda", "CUDAExecutionProvider",
         "CUDA census alone is insufficient without fallback/readback API"),
    ):
        result = run_case(label, census)
        clean = all(result[k] == 0 for k in (
            "find", "ensure", "import", "construct", "infer"))
        ok = (clean and result["text"] == EN_SAMPLE
              and result["reason"] == "gpu-placement-unprovable")
        rows.append((ok, reason,
                     "reason=%s text_identity=%s counts=%r" %
                     (result["reason"], result["text"] == EN_SAMPLE,
                      {k: result[k] for k in (
                          "find", "ensure", "import", "construct", "infer")})))
    return rows
def arms() -> None:
    print("modelo real nao e' carregado pelo oraculo de rotina; engine fake no consumidor")

    pm = _fresh_module()
    pm.set_lang("en-US")
    pm._ENGINE = _FakePunctuationEngine()
    out = pm.punctuate(EN_SAMPLE)
    add(any(m in out for m in (",", ".")),
        "A1 consumer pontua com engine fake, sem construir pesos",
        f"out={out!r}")

    # A guarda de lingua, contra o consumidor real com engine fake.
    pm.set_lang("pt-BR")
    add(pm.punctuate(EN_SAMPLE) == EN_SAMPLE,
        "B1 tag pt-BR devolve o texto BYTE-IDENTICO (nao 'quase igual')",
        repr(pm.punctuate(EN_SAMPLE)))
    pm.set_lang(None)
    add(pm.punctuate(EN_SAMPLE) == EN_SAMPLE,
        "B2 tag DESCONHECIDA nao e' 'provavelmente ingles'", repr(pm.punctuate(EN_SAMPLE)))
    pm.set_lang("en-US")
    add(pm.punctuate(EN_SAMPLE, tag="pt") == EN_SAMPLE,
        "B3 a tag EXPLICITA no argumento ganha da tag do processo",
        repr(pm.punctuate(EN_SAMPLE, tag="pt")))
    add(pm.supported_lang("en") and pm.supported_lang("EN_us")
        and not pm.supported_lang("pt-PT") and not pm.supported_lang(""),
        "B4 `supported_lang`: en/EN_us sim, pt-PT e vazio nao")

    # O filtro, na funcao REAL.
    pm.set_lang("pt-BR")
    add("lang-unsupported" in pm.log_line() and "pt-BR" in pm.log_line(),
        "B5 a linha do log NOMEIA a lingua que desliga a pontuacao", pm.log_line())
    pm.set_lang("en-US")
    add("?" not in pm._filter("in what year did you switch away from that I? didn't"),
        "C1 `?` a MEIO e' removido", repr(pm._filter("a I? didn't")))
    add(pm._filter("and a German government office,") == "and a German government office",
        "C2 comma a FECHAR a linha e' removido", repr(pm._filter("x office,")))
    add(pm._filter("how are you doing today?") == "how are you doing today.",
        "C3 `?` a FECHAR vira ponto (nao some)", repr(pm._filter("how are you?")))
    add(pm._filter("") == "" and pm._filter("sem marca") == "sem marca",
        "C4 texto sem marca passa intacto")

    # Sem modelo / desligado.
    tmp = Path(tempfile.mkdtemp(prefix="punct-absent-"))
    try:
        pm2 = _fresh_module()
        pm2.set_lang("en-US")
        out = pm2.punctuate(EN_SAMPLE, root=tmp)
        add(out == EN_SAMPLE
            and pm2.status()["reason"] == "gpu-placement-unprovable",
            "D1 placement sem prova -> identidade antes de procurar modelo",
            pm2.status()["reason"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    os.environ["SOTTO_PUNCT_MODEL"] = "0"
    try:
        pm3 = _fresh_module()
        pm3.set_lang("en-US")
        out = pm3.punctuate(EN_SAMPLE)
        add(out == EN_SAMPLE and pm3.status()["reason"] == "disabled-by-env",
            "D2 `SOTTO_PUNCT_MODEL=0` desliga mesmo com o modelo no disco",
            pm3.status()["reason"])
    finally:
        os.environ.pop("SOTTO_PUNCT_MODEL", None)

    pm4 = _fresh_module()
    pm4.set_lang("en-US")
    add(pm4.punctuate("") == "" and pm4.punctuate("   ") == "   ",
        "D3 vazio/devolve o que recebeu, sem carregar nada", pm4.status()["reason"])

    # A FIACAO, no objecto REAL (`LineFormer`).
    pm5 = _fresh_module()
    pm5.set_lang("en-US")
    pm5._ENGINE = _FakePunctuationEngine()
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location("sotto_worker", WORKER / "sotto_worker.py")
    sw = importlib.util.module_from_spec(spec)
    sys.modules["sotto_worker"] = sw
    spec.loader.exec_module(sw)
    lf = sw.LineFormer(min_chars=1, emit_partial=True)
    closed = lf._event(EN_SAMPLE, final=True, closed=True, stable=True)
    partial = lf._event(EN_SAMPLE, stable=True)
    want = pm5.punctuate(EN_SAMPLE)
    add(closed["text"] == want,
        "E1 a linha FECHADA leva a pontuacao", f"{closed['text']!r} vs {want!r}")
    add(partial["text"] == EN_SAMPLE,
        "E2 a linha PARCIAL nao leva (nao ha comma a saltar de sitio)",
        repr(partial["text"]))

    # F. O ESTADO CHEGA AO LOG DA SHELL. Nasceu de um defeito medido hoje: a
    #    linha `PUNCT_MODEL` era `err()`, e `err` e' STDERR -- a shell so' o
    #    guarda na cauda da morte, logo a pergunta "a pontuacao esta' ligada?"
    #    so' se respondia depois de ja' nao haver o que medir. O mesmo erro que
    #    o `BRIDGE_RSS` pagou. O estado viaja no status `stage=providers` (que a
    #    shell JA' loga) e a shell escreve-o.
    worker_src = (WORKER / "sotto_worker.py").read_text(encoding="utf-8")
    shell_src = (ROOT / "app" / "webview" / "sotto_webview.py").read_text(encoding="utf-8")
    add("punct_model=punctuation_model.log_line()" in worker_src,
        "F1 o worker publica o estado no status que a shell loga")
    add("if punct:" in shell_src and "self.log(punct)" in shell_src,
        "F2 a shell ESCREVE a linha (nao a deixa no stderr)")

    results.extend(gpu_policy_controls())


def _mutate(target: Path, pairs) -> list[str]:
    text = target.read_text(encoding="utf-8")
    notes = []
    for old, new, note in pairs:
        if old not in text:
            return []
        text = text.replace(old, new, 1)
        notes.append(note)
    target.write_text(text, encoding="utf-8")
    return notes


def neg_arm() -> int:
    """Mutacoes model-free no worker/modulo; cada uma tem de derrubar arm."""
    muts = [
        ("lang-guard",
         [("    if not supported_lang(tag):\n        return text\n",
           "    if False:\n        return text\n",
           "a guarda de lingua desarmada")],
         "B1"),
        ("mid-question",
         [('    out = _MID_QUESTION.sub("", text)\n', "    out = text\n",
           "o `?` a meio volta")],
         "C1"),
        ("trailing-comma",
         [("    out = _TRAILING_COMMA.sub(\"\", out)\n", "",
           "o comma a fechar volta")],
         "C2"),
        ("closed-only",
         [("        if (final or closed) and text:\n", "        if text:\n",
           "a parcial passa a ser pontuada")],
         "E2"),
        ("state-in-log",
         [("        punct_model=punctuation_model.log_line(),\n", "",
           "o estado volta a nao viajar")],
         "F1"),
    ]
    failures = 0
    for name, pairs, arm in muts:
        tmp = Path(tempfile.mkdtemp(prefix="punct-neg-"))
        try:
            a = (WORKER / "punctuation_model.py").read_text(encoding="utf-8")
            b = (WORKER / "sotto_worker.py").read_text(encoding="utf-8")
            (tmp / "punctuation_model.py").write_text(a, encoding="utf-8")
            (tmp / "sotto_worker.py").write_text(b, encoding="utf-8")
            # O ALVO depende do mutante: `closed-only` e `state-in-log` vivem no
            # WORKER; os outros tres no modulo. Errar o alvo da' "nao consegui
            # mutar", nunca um verde -- mas custa uma volta.
            target = tmp / ("sotto_worker.py" if name in ("closed-only", "state-in-log")
                            else "punctuation_model.py")
            notes = _mutate(target, pairs)
            if not notes:
                print(f"NEG-ARM: nao consegui mutar {name} (o texto mudou)")
                failures += 1
                continue
            print(f"\n=== NEG-ARM {name}: {notes[0]}")
            rc = _run_arms_with(tmp, arm)
            if rc == EXIT_FAIL:
                print(f"NEG-ARM {name} PASS -- RED as designed ({arm})")
            else:
                print(f"NEG-ARM {name} FAIL -- o oraculo NAO ve a regressao em {arm}")
                failures += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # The placement guard is part of the normal oracle's arms. Mutating it to
    # allow the generic provider-only path must make those same arms RED.
    source = (WORKER / "punctuation_model.py").read_text(encoding="utf-8")
    old_guard = "_NATIVE_GPU_PLACEMENT_VERIFIED = False"
    if old_guard not in source:
        print("NEG-ARM gpu-placement-guard FAIL -- mutation anchor missing")
        failures += 1
    else:
        tmp = Path(tempfile.mkdtemp(prefix="punct-gpu-neg-"))
        try:
            mutant = tmp / "punctuation_model.py"
            mutant.write_text(source.replace(
                old_guard, "_NATIVE_GPU_PLACEMENT_VERIFIED = True", 1),
                encoding="utf-8")
            rows = gpu_policy_controls(module_path=mutant)
            reds = [name for ok, name, _ in rows if not ok]
            if reds:
                print("NEG-ARM gpu-placement-guard PASS -- startup policy RED: %s"
                      % "; ".join(reds))
            else:
                print("NEG-ARM gpu-placement-guard FAIL -- weakened guard survived")
                failures += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if failures:
        print("\nNEG-ARM FAIL -- o oraculo nao ve a regressao")
        return EXIT_PASS
    print("\nNEG-ARM: PASS -- as seis regressoes derrubam o oraculo")
    return EXIT_FAIL


def _run_arms_with(dirpath: Path, arm: str) -> int:
    """Corre SO' as arms em `dirpath` (um worker com mutacao) e devolve rc."""
    MODELS = str(WORKER / "models" / "punct-en")
    code = f'''
MODELS = {MODELS!r}
import sys, importlib.util
from pathlib import Path
sys.path.insert(0, r"{dirpath}")
import punctuation_model as pm
pm.set_lang("en-US")
class FakePunctuationEngine:
    def add_punctuation_with_case(self, text):
        return "hello there, how are you doing today."
pm._ENGINE = FakePunctuationEngine()
SAMPLE = {EN_SAMPLE!r}
arm = {arm!r}
ok = True
if arm == "B1":
    # O `root` e' EXPLICITO: a copia mutada vive num directorio temporario, e
    # sem isto o proprio `find_model` devolveria `None` e a arm ficava verde por
    # AUSENCIA de modelo em vez de por guarda -- um falso verde do instrumento.
    pm.set_lang("pt-BR")
    ok = pm.punctuate(SAMPLE, root=r"{MODELS}") == SAMPLE
elif arm == "C1":
    ok = "?" not in pm._filter("that I? didn't")
elif arm == "C2":
    ok = pm._filter("x office,") == "x office"
elif arm == "F1":
    ok = "punct_model=punctuation_model.log_line()" in open(r"{dirpath}/sotto_worker.py", encoding="utf-8").read()
elif arm == "E2":
    spec = importlib.util.spec_from_file_location("sw_m", r"{dirpath}/sotto_worker.py")
    m = importlib.util.module_from_spec(spec); sys.modules["sw_m"] = m
    try:
        spec.loader.exec_module(m)
        lf = m.LineFormer(min_chars=1, emit_partial=True)
        ok = lf._event(SAMPLE, stable=True)["text"] == SAMPLE
    except Exception:
        ok = False
print("ARM", arm, "GREEN" if ok else "RED")
sys.exit(0 if ok else 1)
'''
    import subprocess  # noqa: PLC0415

    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       timeout=180)
    print((r.stdout or "").strip()[:400])
    return r.returncode


def main() -> int:
    if "--gpu-policy-only" in sys.argv:
        rows = gpu_policy_controls()
        failed = 0
        for ok, name, detail in rows:
            print(f"{'PASS' if ok else 'FAIL'}  {name}"
                  + (f"   [{detail}]" if detail else ""))
            failed += not ok
        print(f"\nGPU POLICY VERDICT: {'PASS' if not failed else 'FAIL'} "
              f"({len(rows) - failed}/{len(rows)})")
        return EXIT_PASS if not failed else EXIT_FAIL
    if "--neg-arm" in sys.argv:
        return neg_arm()
    arms()
    bad = [r for r in results if not r[0]]
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail and not ok else ""))
    print(f"\n{len(results) - len(bad)}/{len(results)} arms green")
    print("VERDICT:", "PASS" if not bad else "FAIL")
    return EXIT_PASS if not bad else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
