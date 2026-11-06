#!/usr/bin/env python
# NO-BUG: mede a pontuacao de MODELO contra os clipes reais; a classe nao tem id no leder
"""A PONTUACAO DE MODELO, julgada pela FUNCAO que embarca.

Ordem do dono (2026-11-05, verbatim): *"por que a gente nao normaliza as frases
ou usa pontuacao de forma inteligente?"*. `worker/punctuation_model.py` responde
com o restaurador `sherpa-onnx-online-punct-en` (Apache-2.0, int8 7,1 MB, CPU).
Este oraculo executa as funcoes REAIS -- nao um resumo delas:

  A. `punctuate()` no texto ingles DEVOLVE marca;
  B. a GUARDA DE LINGUA: `pt-BR` e `None` devolvem o texto BYTE-IDENTICO. Nao e'
     zelo: medido nesta maquina, o modelo ingles sobre portugues devolve
     `"EU Gosto Muito, disso sabe como E que E"` -- caixa aleatoria com
     aparencia de pontuacao, que e' pior do que nao pontuar;
  C. o `?` a meio de uma hipotese parcial e' removido (`that I? didn't` foi
     medido no log dele) e um comma que FECHA a linha tambem;
  D. sem modelo no disco, sem pacote, ou com `SOTTO_PUNCT_MODEL=0`, a funcao e'
     IDENTIDADE e `status()` diz o motivo;
  E. o `LineFormer._event` pontua a linha FECHADA e nao a parcial -- a fiacao,
     exercitada no objecto real.

O `--neg-arm` muta uma COPIA do worker sem as guardas e exige as arms RED.

Uso:
    python _main/punct-model-oracle.py
    python _main/punct-model-oracle.py --neg-arm
"""
from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile
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


def arms() -> None:
    present = _model_present()
    print(f"modelo em disco: {present}")

    pm = _fresh_module()
    pm.set_lang("en-US")
    out = pm.punctuate(EN_SAMPLE)
    add(os.environ.get("SOTTO_PUNCT_MODEL", "") != "0" and present
        and any(m in out for m in (",", ".")) or (not present and out == EN_SAMPLE),
        "A1 ingles ganha marca quando o modelo existe",
        f"out={out!r}")

    # A guarda de lingua, contra o motor REAL.
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
        add(out == EN_SAMPLE and pm2.status()["reason"] == "model-absent",
            "D1 modelo AUSENTE -> identidade + motivo nomeado", pm2.status()["reason"])
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
    """Cinco mutacoes numa COPIA do worker; cada uma tem de derrubar arm."""
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
    if failures:
        print("\nNEG-ARM FAIL -- o oraculo nao ve a regressao")
        return EXIT_PASS
    print("\nNEG-ARM: PASS -- as cinco regressoes derrubam o oraculo")
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
