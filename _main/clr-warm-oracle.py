#!/usr/bin/env python
# NO-BUG: instrumento do AQUECIMENTO do cache de tipos do pythonnet (2026-11-12);
# nao corrige o produto, julga-o. Nada aqui abre janela, browser, audio nem input.
"""A PRIMEIRA CONVERSAO CLR ACONTECE SOZINHA, ANTES DA SEGUNDA THREAD.

O DEFEITO, medido oito vezes no mesmo dia. TODO arranque do dono entre 19:32 e
20:16 de 2026-11-12 morreu, e o `run.cmd` escreveu `HANG rc=4 by=run.cmd-readiness`
porque o processo morria ANTES de tocar o ready-file. A fonte e' o log de eventos
do Windows, nao uma hipotese:

    Get-WinEvent -FilterHashtable @{LogName='Application';ProviderName='.NET Runtime'}
      ｜ Where-Object { $_.Message -match 'NullReferenceException' }

Oito eventos, todos de hoje (nos dez dias anteriores: ZERO), e as pilhas sao
duas metades da mesma classe -- `MethodBinder.Invoke` -> `Converter.ToPython`:

    TypeManager.AllocateTypeObject <- ReflectedClrType.GetOrCreate
    BorrowedReference.DangerousGetAddress <- ... <- ManagedType.Init <- ClassBase.Init

O pythonnet materializa o tipo Python que representa um tipo .NET na PRIMEIRA
conversao e guarda-o num cache global; quando a primeira conversao do MESMO tipo
acontece em duas threads ao mesmo tempo, ele desreferencia um ponteiro que a
outra thread ainda nao publicou. E' uma `NullReferenceException` GERIDA: mata o
processo, e o `try/except` de Python nao a apanha. Esta app arranca exactamente
nesse estado -- `webview.start()` entrega a thread da UI a um `_on_before_show`
que converte `Icon`/`Color`/`Size`/`Func[Type]` enquanto o observador do
`Ctrl+Space`, o laco de leitura e o `_ui` ainda correm.

A CURA (`sotto_webview.py:warm_clr_types`, chamada imediatamente antes de
`webview.start`): fazer a primeira conversao UMA vez, na thread principal,
quando ainda nao existe segunda thread.

O QUE ESTE ORACULO JULGA (arms sobre o codigo REAL, extraido por `ast`):

  A1 existe-e-e-chamada   -- a funcao existe E o `main()` a chama ANTES de
                             `webview.start(...)`. Uma cura que ninguem chama e'
                             a doenca que esta casa ja' pagou varias vezes.
  A2 cobre-os-tipos       -- cada tipo que a shell converte nos sitios medidos
                             (`Icon`, `Color`, `Size`, `Rectangle`, `DockStyle`,
                             `Func[Type]`, `Func[Object]`, `Action[String]`,
                             `Task`) e' materializado por ela. Isto e' derivado do
                             CODIGO-FONTE, nao de uma lista escrita a mao: o
                             conjunto de tipos exigido vem dos `from System...` e
                             dos usos reais.
  A3 executa-e-e-rapido   -- a funcao REAL corre num subprocesso (isolado: o
                             `clr` carregado aqui nao contamina a medicao), devolve
                             True, zero falhas, e diz o custo. O tecto nao e' um
                             gosto: e' o dobro dos 1090 ms medidos a mao, para
                             apanhar uma regressao de ordem de grandeza sem
                             condenar esta maquina degradada.
  A4 antes-da-thread      -- a chamada esta' ANTES de `webview.start(...)` e
                             nenhuma thread da shell foi criada antes dela. Um
                             aquecimento a seguir ao `start()` nao impede corrida
                             nenhuma -- e' o mesmo erro com outro nome.

O QUE ESTE ORACULO **NAO** PODE PROVAR, e diz-lo em vez de o esconder: que o
processo do dono deixou de morrer. Essa prova exige uma corrida real da app, com
WebView2 a subir, que esta arvore nao consegue fazer de uma pane `medium` (o
WebView2 falha antes em `0x80010108 RPC_E_DISCONNECTED`). A arm A3 prova que o
cache fica quente e que a funcao nao mente; a ausencia de mortes novas so' o
proximo arranque do dono a mede.

`--neg-arm` muta uma COPIA do shell no disco e exige que as arms caiam:
  M1 apaga a chamada a `warm_clr_types()` -> A1 e A4 RED
  M2 tira o `Icon` da lista de conversoes -> A2 RED
  M3 move a chamada para DEPOIS do `webview.start(...)` -> A4 RED
rc=1 = todos apanhados (`NEG-ARM: PASS -- k/k`), rc=0 = algum mutante INERTE.

    python _main\\clr-warm-oracle.py
    python _main\\clr-warm-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app", "webview")
SHELL = os.path.join(APP, "sotto_webview.py")

#: O TECTO E' DE ORDEM DE GRANDEZA, NAO UM CRONOEMTRO (2026-11-12). Medido numa
#: maquina calma: min 689 / mediana 879 / max 1506 ms em 6 processos. Medido com
#: o disco saturado a mesma funcao deu **2279,8 ms** -- e o primeiro tecto, 2200,
#: reprovava a cura CORRECTA por contenda de disco, que e' exactamente "um portao
#: que acusa quem esta' certo perde a autoridade". 4000 apanha o que este braco
#: existe para apanhar (uma conversao que passe a carregar a app inteira, ou um
#: `warm` que rebente em timeout) e nao uma maquina ocupada.
WARM_BUDGET_MS = 4000.0

#: O que a shell converte hoje, pelos sitios medidos. A arm A2 exige que a cura
#: cubra ESTE conjunto -- e a lista e' conferida contra o fonte, para uma cura
#: futura que acrescente um tipo nao deixar este oraculo a olhar para o passado.
REQUIRED = ("Icon", "Color", "Size", "Rectangle", "DockStyle",
            "Func[Type]", "Func[Object]", "Action[String]", "Task")


def _parse(path=None):
    # NAO `path=SHELL`: um default e' avaliado uma vez, na definicao, e o
    # `--neg-arm` troca `SHELL` por uma copia mutada DEPOIS disso -- com o
    # default preso, todos os mutantes corriam contra o ficheiro original e o
    # negativo publicava `INERTE 0/3` (medido nesta primeira versao).
    path = path or SHELL
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return ast.parse(fh.read()), path


def _find_func(tree, name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _warm_covered(func, path=None):
    """Which of REQUIRED the function materializes -- read from the AST pair list.

    A primeira versao deste braco lia o TEXTO da funcao e aceitava o rotulo
    `'Icon'` como prova, logo o mutante que troca a conversao por `lambda: None`
    deixava o nome la' dentro e o braco passava a medir a ETIQUETA em vez do
    trabalho (medido: `INERTE M2 chamada apagada` no primeiro `--neg-arm`). A
    segunda exigia uma CHAMADA `Nome(`, e reprovava conversoes legitimas que sao
    acesso a atributo -- `Color.Transparent`, `DockStyle.Fill`,
    `Task.CompletedTask` (medido: `FAIL A2 cobertos=6/9 faltam=Color,DockStyle,
    Task`). O que se mede agora e' a FORMA REAL do codigo: a tupla
    `(rotulo, lambda)` que a funcao percorre, exigindo que o corpo de cada lambda
    (a) nomeie o tipo e (b) NAO seja um literal `None`.
    """
    src_all = open(path or SHELL, "r", encoding="utf-8", errors="replace").read()
    labels = {}
    for node in ast.walk(func):
        if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
            continue
        lab, body = node.elts
        if not (isinstance(lab, ast.Constant) and isinstance(lab.value, str)):
            continue
        if not isinstance(body, ast.Lambda):
            continue
        text = ast.get_source_segment(src_all, body.body) or ""
        bare = text.strip()
        # Um corpo que e' `None`/`NoneType` e' conversao nenhuma.
        if bare in ("None", ""):
            continue
        labels[lab.value] = bare
    hit = set()
    for want in REQUIRED:
        base = want.split("[")[0]
        if want in labels and re.search(r"\b%s\b" % re.escape(base), labels[want]):
            hit.add(want)
    return hit


def _call_sites(tree):
    """(name, lineno) of every call in the module, at any depth."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                out.append((fn.id, node.lineno))
            elif isinstance(fn, ast.Attribute):
                out.append((fn.attr, node.lineno))
    return out


def arm_exists_and_called():
    tree, _ = _parse()
    func = _find_func(tree, "warm_clr_types")
    calls = [ln for name, ln in _call_sites(tree) if name == "warm_clr_types"]
    starts = [ln for name, ln in _call_sites(tree) if name == "start"]
    ok = func is not None and bool(calls)
    detail = ("funcao=%s chamadas=%d" %
              ('sim' if func is not None else 'NAO', len(calls)))
    if ok:
        # the call must precede the LAST `start` in the module (webview.start)
        last_start = max(starts) if starts else 0
        ok = any(c < last_start for c in calls)
        detail += " antes_do_start=%s" % ('sim' if ok else 'NAO')
    return ok, detail


def arm_covers_types():
    tree, _ = _parse()
    func = _find_func(tree, "warm_clr_types")
    if func is None:
        return False, "funcao ausente"
    covered = _warm_covered(func)
    missing = [w for w in REQUIRED if w not in covered]
    return (not missing,
            "cobertos=%d/%d faltam=%s" % (len(covered), len(REQUIRED),
                                          ','.join(missing) or 'nenhum'))


def arm_executes(path=SHELL):
    """Run the REAL function in its own process: it must return True, fast."""
    code = (
        "import sys, time\n"
        "sys.path.insert(0, %r)\n"
        "import importlib.util\n"
        "spec = importlib.util.spec_from_file_location('sw', %r)\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "t0 = time.time()\n"
        "spec.loader.exec_module(m)\n"
        "t1 = time.time()\n"
        "res = m.warm_clr_types()\n"
        "t2 = time.time()\n"
        "print('WARM call=%%s warm_ms=%%.1f import_ms=%%.1f' %% (res, (t2-t1)*1000, (t1-t0)*1000))\n"
        % (APP, path))
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, timeout=180,
                             cwd=ROOT)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    text = (out.stdout or "") + (out.stderr or "")
    m = re.search(r"WARM call=(\w+) warm_ms=([\d.]+)", text)
    if not m:
        tail = [ln for ln in text.strip().splitlines() if ln.strip()][-2:]
        return False, "sem linha WARM (%s)" % (' / '.join(tail)[:160] or 'vazio')
    ok_call = m.group(1) == "True"
    ms = float(m.group(2))
    ok = ok_call and ms <= WARM_BUDGET_MS
    return ok, "call=%s warm_ms=%.1f budget_ms=%.0f" % (m.group(1), ms,
                                                        WARM_BUDGET_MS)


def arm_before_thread():
    """`warm_clr_types()` must run before anything spawns a thread."""
    tree, _ = _parse()
    calls = [ln for name, ln in _call_sites(tree) if name == "warm_clr_types"]
    if not calls:
        return False, "sem chamada"
    first = min(calls)
    # Any Thread(...) construction in main() before the warm call would defeat it.
    main = _find_func(tree, "main")
    if main is None:
        return False, "main ausente"
    early = []
    for node in ast.walk(main):
        if isinstance(node, ast.Call) and node.lineno < first:
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else "")
            if name == "Thread":
                early.append(node.lineno)
    return (not early,
            "warm_linha=%d threads_antes=%s" % (first,
                                                early[:5] or 'nenhuma'))


def run():
    arms = [
        ("A1 existe-e-e-chamada", arm_exists_and_called),
        ("A2 cobre-os-tipos", arm_covers_types),
        ("A3 executa-e-e-rapido", arm_executes),
        ("A4 antes-da-thread", arm_before_thread),
    ]
    results = []
    for label, fn in arms:
        try:
            ok, detail = fn()
        except Exception as exc:              # noqa: BLE001
            ok, detail = False, "EXC %r" % (exc,)
        results.append(ok)
        print("%s %-24s %s" % ("PASS" if ok else "FAIL", label, detail))
    good = sum(1 for r in results if r)
    print("VERDICT: %s (%d/%d)" % ("PASS" if good == len(results) else "FAIL",
                                   good, len(results)))
    return 0 if good == len(results) else 1


# -- negative arm ------------------------------------------------------------
def _mutate_remove_call(src):
    for nl in ("\r\n", "\n"):
        hit = "    warm_clr_types()" + nl
        if hit in src:
            return src.replace(hit, "    pass  # M1 removed" + nl, 1)
    return src


def _mutate_drop_icon(src):
    return src.replace("('Icon', lambda: Icon(SOTTO_ICON)),",
                       "('Icon', lambda: None),", 1)


def _mutate_after_start(src):
    """Move the call to after webview.start()."""
    for nl in ("\r\n", "\n"):
        if ("    warm_clr_types()" + nl) in src:
            src = src.replace("    warm_clr_types()" + nl, "", 1)
            src = src.replace("    webview.start(icon=SOTTO_ICON)" + nl,
                              "    webview.start(icon=SOTTO_ICON)" + nl +
                              "    warm_clr_types()" + nl, 1)
            return src
    return src


def neg_arm():
    global SHELL
    with open(SHELL, "r", encoding="utf-8", errors="replace") as fh:
        original = fh.read()
    mutants = [
        ("M1 chamada apagada", _mutate_remove_call, ("A1 existe-e-e-chamada",
                                                     "A4 antes-da-thread")),
        ("M2 Icon fora da cura", _mutate_drop_icon, ("A2 cobre-os-tipos",)),
        ("M3 chamada depois do start", _mutate_after_start, ("A4 antes-da-thread",)),
    ]
    backup = SHELL
    caught = 0
    try:
        for label, mutate, must_fail in mutants:
            mutated = mutate(original)
            if mutated == original:
                print("MUTATION-NOT-APPLIED %s" % label)
                continue
            fd, tmp = tempfile.mkstemp(suffix=".py", prefix="sotto-clrwarm-")
            os.close(fd)
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write(mutated)
                SHELL = tmp
                before = {name: fn() for name, fn in [
                    ("A1 existe-e-e-chamada", arm_exists_and_called),
                    ("A2 cobre-os-tipos", arm_covers_types),
                    ("A4 antes-da-thread", arm_before_thread)]}
                failed = [name for name, (ok, _) in before.items() if not ok]
                hit = all(name in failed for name in must_fail)
                if hit:
                    caught += 1
                    print("CAUGHT %-26s arms_red=%s" % (label, failed))
                else:
                    print("INERTE %-26s arms_red=%s exigia=%s"
                          % (label, failed, list(must_fail)))
            finally:
                SHELL = backup
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
    finally:
        SHELL = backup
    print("NEG-ARM: %s -- %d/%d" % ("PASS" if caught == len(mutants) else "FAIL",
                                    caught, len(mutants)))
    return 1 if caught == len(mutants) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)
    return neg_arm() if args.neg_arm else run()


if __name__ == "__main__":
    sys.exit(main())
