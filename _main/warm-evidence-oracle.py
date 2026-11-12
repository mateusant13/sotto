#!/usr/bin/env python3
"""warm-evidence-oracle -- o motor quente PAGA-SE? (D-04)

O DEFEITO, medido 2026-11-12 no log inteiro do motor:

    $ grep -o "WARM_[A-Z_]*" _main/warm-engine.log | sort | uniq -c
          8 WARM_ENGINE_START
          8 WARM_LOAD_BEGIN
          8 WARM_LOAD_MS          <- 7,5 s a 26,0 s de disco, ~1 GB residente
          8 WARM_EXIT             <- todos `idle-expired held_s=600`
    $ grep -c WARM_ATTACHED _main/webview-run.log
    0

O shell pedia `SottoWarmEngine` a CADA abertura; o motor carregava e expirava em
`WARM_PARK_TTL_S = 600 s`, enquanto as aberturas do dono distam 2 h a 16 h. Cada
pedido pagava a carga no arranque em que a shell ja' esta' a ler 1,9 GB, e o
anexo nunca aconteceu -- nem uma vez. A cura e' a serie decidir
(`app/webview/warm_evidence.py`), com fail-open: sem serie legivel, PEDE.

O QUE ESTE ORACULO JULGA, treze arms, nenhuma larga a app, nenhuma abre janela,
nenhuma toca em dispositivo de audio:

  A1-A4  a regra PURA: evidencia curta pede, serie de cargas sem anexo recusa,
         um anexo devolve o pedido, entrada ilegivel nao vira recusa
  A5     a contagem e' por CAMPO (uma tag dentro de outra nao conta)
  A6     um log ilegivel devolve `None`, nunca zero
  A7     `request_verdict_for` com log ausente -> PEDE (`sem-evidencia`)
  A8     o par de ficheiros de verdade, num diretorio temporario, nas duas direcoes
  A9     estrutural: `_try_warm_attach` delega e nao chama `start_warm_engine_task`
  A10    estrutural: no metodo novo, `if keep` vem antes e a evidencia antes do pedido
  A11    VIVO: o metodo REAL extraido por `ast`, com stub -- keep, recusa e excecao
  A12    os dois numeros declarados sao plausiveis (`MIN_LOADS >= 2`, cauda <= 4 MiB)
  A13    o `_LOG_FILE` que a shell passa e' o log dela, e a assinatura tem 2 nomes

`--neg-arm` corre a MESMA populacao contra cinco mutacoes, cada uma tem de cair
pela SUA arm (rc=1 quando apanha -- a convencao desta casa: um negativo que
devolve 0 ao apanhar e' um portao que nao pode falhar).
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
MODULE = os.path.join(ROOT, "app", "webview", "warm_evidence.py")


def shell_text(path=SHELL):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def method_source(text, name):
    """O fonte EXACTO do metodo (ou funcao) de topo `name`, por `ast`."""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    return ""


def load_module(source=None, path=MODULE):
    """O modulo puro. Sem `source`, importa o do disco; com ele, executa a copia."""
    if source is None:
        directory = os.path.dirname(os.path.abspath(path))
        if directory not in sys.path:
            sys.path.insert(0, directory)
        import importlib.util
        spec = importlib.util.spec_from_file_location("warm_evidence_real", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["warm_evidence_real"] = module
        spec.loader.exec_module(module)
        return module
    namespace = {"__name__": "warm_evidence_mutant"}
    exec(compile(source, path, "exec"), namespace)
    return type("Mutant", (), namespace)


class Arms:
    def __init__(self):
        self.arms = []

    def arm(self, name, ok, detail=""):
        self.arms.append((name, bool(ok), detail))
        print("  %s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


def write_log(path, lines):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def run_pure(mod, arms):
    """A1-A8: a regra e o leitor, sem shell nenhuma."""
    v = mod.verdict
    few = v(2, 0)
    arms.arm("A1 evidencia curta (2 cargas) PEDE", few["request"] is True
             and few["why"] == "pouca-evidencia", repr(few))
    never = v(8, 0)
    arms.arm("A2 8 cargas e ZERO anexos RECUSA", never["request"] is False
             and never["why"] == "nunca-anexou", repr(never))
    some = v(8, 1)
    arms.arm("A3 um anexo devolve o pedido", some["request"] is True
             and some["why"] == "ja-anexou", repr(some))
    jam = v("abc", None)
    arms.arm("A4 entrada ilegivel NAO vira recusa", jam["request"] is True
             and jam["loads"] == 0 and jam["attaches"] == 0, repr(jam))

    tmp = tempfile.mkdtemp(prefix="warm-evidence-")
    try:
        log = write_log(os.path.join(tmp, "warm.log"), [
            "2026-11-11 01:04:05 WARM_LOAD_MS ms=8060.0  resident_mb=1010.2",
            "2026-11-11 17:34:35 WARM_LOAD_MS ms=12471.5 resident_mb=1010.2",
            "2026-11-11 20:01:27 WARM_LOAD_MS ms=26027.8 resident_mb=1012.8",
            "2026-11-11 20:01:30 NOTICE WARM_LOAD_MS_DEFERRED why=shed-alta",
            "2026-11-11 20:11:01 WARM_EXIT why=idle-expired held_s=600.1",
        ])
        counted = mod.count_tag(log, "WARM_LOAD_MS")
        arms.arm("A5 conta por CAMPO (a tag no meio de outra nao conta)", counted == 3,
                 "counted=%r" % (counted,))
        missing = mod.count_tag(os.path.join(tmp, "nao-existe.log"), "WARM_LOAD_MS")
        arms.arm("A6 log ilegivel devolve None (nunca zero)", missing is None,
                 "got=%r" % (missing,))
        absent = mod.request_verdict_for(os.path.join(tmp, "nao-existe.log"), log)
        arms.arm("A7 sem serie legivel PEDE (fail-open)",
                 absent["request"] is True and absent["why"] == "sem-evidencia",
                 repr(absent))

        quiet = write_log(os.path.join(tmp, "shell-quiet.log"), [
            "2026-11-11 20:01:20 WARM_FALLBACK_COLD reason=absent reason_attach=default",
            "2026-11-11 20:01:21 WARM_ENGINE_START_TASK task=SottoWarmEngine rc=0",
        ])
        refused = mod.request_verdict_for(log, quiet)
        loud = write_log(os.path.join(tmp, "shell-attached.log"), [
            "2026-11-11 20:01:20 WARM_ATTACHED reason=default pid=912 mode=live load_ms=8.0",
        ])
        allowed = mod.request_verdict_for(log, loud)
        arms.arm("A8 o par de ficheiros decide nas DUAS direcoes",
                 refused["request"] is False and allowed["request"] is True,
                 "quiet=%r attached=%r" % (refused["why"], allowed["why"]))
    finally:
        for name in os.listdir(tmp):
            try:
                os.unlink(os.path.join(tmp, name))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def run_wiring(text, arms):
    """A9/A10/A13: a fiacao no fonte que embarca."""
    attach = method_source(text, "_try_warm_attach")
    request = method_source(text, "_request_warm_engine")
    arms.arm("A9 _try_warm_attach DELEGA o pedido",
             "self._request_warm_engine(keep)" in attach
             and "start_warm_engine_task(" not in attach,
             "chama=%s direto=%s" % ("self._request_warm_engine(keep)" in attach,
                                     "start_warm_engine_task(" in attach))
    keep_at = request.find("if keep:")
    ask_at = request.find("warm_evidence.request_verdict_for(")
    go_at = request.find("start_warm_engine_task(")
    # O METODO TEM TRES PEDIDOS (keep, veredicto, fail-open) e os tres vem
    # depois do `if keep`; o que a arm exige e' que NENHUM deles aconteca antes
    # de a evidencia ser consultada, e que o pedido do caminho normal venha
    # depois dela. (A primeira versao exigia `ask < go` e media `go` = o pedido
    # do proprio ramo `keep`, que vive ANTES -- o mutante ficava INERTE.)
    asks = [i for i in range(len(request)) if request.startswith(
        "warm_evidence.request_verdict_for(", i)]
    goes = [i for i in range(len(request)) if request.startswith(
        "start_warm_engine_task(", i)]
    arms.arm("A10 keep vem antes, e nenhum pedido antes da evidencia",
             len(asks) == 1 and len(goes) == 3
             and keep_at < asks[0] and all(g > asks[0] for g in goes[1:]),
             "keep=%d asks=%r goes=%r" % (keep_at, asks, goes))
    arms.arm("A13 a shell le DOIS logs e o do motor vem do modulo",
             "warm_module().LOG_FILE" in request and "_LOG_FILE" in request,
             "engine=%s shell=%s" % ("warm_module().LOG_FILE" in request,
                                     "_LOG_FILE" in request))


class ShellStub:
    def __init__(self):
        self.lines = []
        self.starts = 0
        self.requested = None

    def log_line(self, msg):
        self.lines.append(msg)


def run_live(mod, text, arms):
    """A11: o metodo REAL, extraido por `ast`, com stubs. Nenhuma largada."""
    source = method_source(text, "_request_warm_engine")
    if not source:
        arms.arm("A11 o metodo real existe no fonte", False, "ausente")
        return
    body = "\n".join(line[4:] if line.startswith("    ") else line
                     for line in source.splitlines())

    def build(verdict=None, boom=False):
        stub = ShellStub()
        ns = {
            "log": stub.log_line,
            "warm_evidence": mod,
            "_LOG_FILE": os.path.join(ROOT, "_main", "webview-run.log"),
            "warm_module": lambda: type("M", (), {"LOG_FILE": MODULE})(),
        }

        def start(**kwargs):
            stub.starts += 1
            return True

        ns["start_warm_engine_task"] = start
        if boom:
            def explode(_engine, _shell):
                raise OSError("log ilegivel")
            ns["warm_evidence"] = type("E", (), {"request_verdict_for": explode})()
        elif verdict is not None:
            ns["warm_evidence"] = type(
                "E", (), {"request_verdict_for": staticmethod(lambda a, b: verdict)})()
        exec(compile(body, "<_request_warm_engine>", "exec"), ns)
        from types import SimpleNamespace
        return SimpleNamespace(stub=stub, fn=ns["_request_warm_engine"])

    keep = build(verdict={"request": False, "why": "nunca-anexou", "loads": 8,
                          "attaches": 0})
    keep.fn(keep.stub, True)
    no = build(verdict={"request": False, "why": "nunca-anexou", "loads": 8,
                        "attaches": 0})
    no.fn(no.stub, False)
    yes = build(verdict={"request": True, "why": "ja-anexou", "loads": 8,
                         "attaches": 1})
    yes.fn(yes.stub, False)
    fail = build(boom=True)
    fail.fn(fail.stub, False)
    ok = (keep.stub.starts == 1
          and no.stub.starts == 0
          and any("WARM_ENGINE_NOT_REQUESTED" in ln and "nunca-anexou" in ln
                  for ln in no.stub.lines)
          and yes.stub.starts == 1
          and fail.stub.starts == 1
          and any("WARM_ENGINE_EVIDENCE_FAILED" in ln for ln in fail.stub.lines))
    arms.arm("A11 o metodo real: keep pede, recusa nao pede, excecao pede", ok,
             "keep=%d no=%d yes=%d fail=%d"
             % (keep.stub.starts, no.stub.starts, yes.stub.starts, fail.stub.starts))


def run_numbers(mod, arms):
    """A12: os numeros declarados, julgados contra o que eles protegem."""
    arms.arm("A12 MIN_LOADS >= 2 e a cauda <= 4 MiB",
             int(mod.MIN_LOADS) >= 2 and 0 < int(mod.SHELL_TAIL_BYTES) <= 4 * 1024 * 1024,
             "MIN_LOADS=%r tail=%r" % (mod.MIN_LOADS, mod.SHELL_TAIL_BYTES))


def main(argv):
    neg = "--neg-arm" in argv
    text = shell_text()
    mod = load_module()
    arms = Arms()
    print("sotto: warm-evidence -- o motor quente paga-se? (D-04)")
    run_pure(mod, arms)
    run_wiring(text, arms)
    run_live(mod, text, arms)
    run_numbers(mod, arms)

    if neg:
        source = open(MODULE, encoding="utf-8", newline="").read()
        muts = [
            ("M1 a regra nunca recusa", "A2",
             lambda s: s.replace("    out['request'] = False\n", "", 1)),
            ("M2 conta a tag como SUBSTRING de qualquer campo", "A5",
             lambda s: s.replace("            if field == needle or field.startswith(eq):",
                                 "            if needle in field:", 1)),
            ("M3 log ilegivel vira zero", "A6",
             lambda s: s.replace("    except OSError:\n        return None",
                                 "    except OSError:\n        return 0", 1)),
            ("M5 MIN_LOADS = 1", "A1",
             lambda s: s.replace("MIN_LOADS = 3", "MIN_LOADS = 1", 1)),
        ]
        caught = 0
        for name, expected, mutate in muts:
            mutant = mutate(source)
            if mutant == source:
                print("  %-62s MUTACAO-NAO-APLICOU" % name)
                continue
            fresh = Arms()
            try:
                run_pure(load_module(mutant), fresh)
            except Exception as exc:  # noqa: BLE001 -- fonte invalido == apanhado
                caught += 1
                print("  %-62s RED em %-6s caught (%r)" % (name, expected, exc))
                continue
            red = [n for n, ok, _d in fresh.arms if not ok]
            hit = any(n.split()[0] == expected for n in red)
            caught += 1 if hit else 0
            print("  %-62s RED em %-6s %s" % (name, expected,
                                              "caught" if hit else "NOT-CAUGHT red=%r" % (red,)))

        # M4: a shell pede SEM olhar o veredicto.
        broken = text.replace("        if verdict['request']:",
                              "        if True:", 1)
        if broken == text:
            print("  %-62s MUTACAO-NAO-APLICOU" % "M4 a shell ignora o veredicto")
        else:
            fresh = Arms()
            run_live(load_module(), broken, fresh)
            red = [n for n, ok, _d in fresh.arms if not ok]
            hit = any(n.split()[0] == "A11" for n in red)
            caught += 1 if hit else 0
            print("  %-62s RED em %-6s %s" % ("M4 a shell ignora o veredicto", "A11",
                                              "caught" if hit else "NOT-CAUGHT red=%r" % (red,)))
        total = len(muts) + 1
        print("NEG-ARM: %s -- %d/%d mutantes apanhados"
              % ("PASS" if caught == total else "FAIL", caught, total))
        return 1 if caught == total else 0

    fails = [(n, d) for n, ok, d in arms.arms if not ok]
    print("VERDICT: arms=%d pass=%d fail=%d"
          % (len(arms.arms), len(arms.arms) - len(fails), len(fails)))
    print("VERDICT: %s" % ("PASS" if not fails else "FAIL"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
