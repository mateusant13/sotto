#!/usr/bin/env python
"""GATE: um passo CACHEAVEL que carrega a pagina real do painel tem de nomear
TODOS os ficheiros que essa pagina carrega.

O DEFEITO QUE ISTO FECHA (medido 2026-11-07, nesta arvore). Os dois passos
`panel-header-oracle` e `panel-history-clip` montam o `app/panel/panel.html`
VERDADEIRO -- o primeiro injecta cada `<link>` como `<style>` e faz `eval` em
cada `<script>`; o segundo abre a pagina no Chromium. A linha `call :step`
declarava 11 e 8 dependencias. O `panel.html` liga **25** assets, e os tres
manifestos de tema (`themes/themes.js`, `themes/panel-designs.js`,
`themes/zipc-panels.js`) nao estavam em nenhuma das duas listas.

Consequencia, e e' a razao de existir um portao e nao um comentario: o
`_stepcache` responde HIT pelo fingerprint das dependencias DECLARADAS. Editar um
tema ou um manifesto deixaria os dois passos em cache a reimprimir um PASS sobre
o ficheiro antigo -- a mesma classe que ja' mordeu esta casa ('uma dependencia
que o nao nomeia deixaria o passo em cache a descrever um ficheiro que ja mudou',
AGENTS.md). Um passo `always` nao tem este problema (nunca e' HIT), e por isso a
ARM 3 exige que estes dois NAO sejam `always`: se algum dia passarem a ser, esta
verificacao deixa de medir o que diz medir e o portao tem de dizer isso.

O QUE ESTE ORACULO EXIGE
  * le as linhas `call :step ...` da `.cmd` (o mesmo `STEP_RE` que a pagina de
    estado usa, para nao haver duas definicoes de 'declaracao de passo');
  * para cada passo da tabela `READS`, resolve os assets do `panel.html`
    por `href=`/`src=` e exige que a lista de deps seja SUPERCONJUNTO;
  * exige que cada dep declarada exista no disco (uma dep inexistente e' ruido:
    nunca muda o fingerprint).

ARM 1  as deps de cada passo carregador-de-pagina contem os assets do panel.html
ARM 2  cada dep declarada nesses passos existe
ARM 3  nenhum dos passos e' `always` (senao as deps nao governam nada)

NEG-ARM (`--neg-arm`): a MESMA verificacao sobre uma COPIA da `.cmd` a que foi
arrancado um asset (o manifesto `themes/zipc-panels.js`) -- tem de ficar
VERMELHO. O ficheiro vivo nunca e' escrito.

Exit: 0 verde, 1 vermelho, 2 erro de setup.
"""
# NO-BUG: portao da cobertura de dependencias dos passos cacheaveis que carregam o panel.html real
from __future__ import annotations

import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
CMD = os.path.join(HERE, "_audit-verify-all.cmd")
PANEL_HTML = os.path.join(REPO, "app", "panel", "panel.html")

ASSET_RE = re.compile(r'(?:href|src)="([^"]+)"')

RESULTS = []


def arm(name, real, want):
    ok = real == want
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        print(f"       real = {real!r}\n       want = {want!r}")
    return ok


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def declarations(cmd_path):
    """{nome: (always, [deps])} das linhas `call :step` da `.cmd`."""
    page = _load("_sotto_state_page", os.path.join(HERE, "sotto-state-page.py"))
    out = {}
    with io.open(cmd_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = page.STEP_RE.match(line)
            if not m:
                continue
            always, _heavy, name, _expect, deps, _log, _command = m.groups()
            if name in out:
                continue
            out[name] = (bool(always),
                         [d.strip() for d in (deps or "").split(";") if d.strip()])
    return out


def panel_assets():
    """[(relpath as the browser writes it, repo-relative windows path)]."""
    with io.open(PANEL_HTML, encoding="utf-8", errors="replace") as fh:
        html = fh.read()
    seen, out = set(), []
    for href in ASSET_RE.findall(html):
        rel = "app/panel/" + href.split("?")[0].split("#")[0]
        if rel in seen:
            continue
        seen.add(rel)
        out.append((href, "app\\panel\\" + href.replace("/", "\\")))
    return out


#: O que CADA passo le, dito pelo proprio passo: o probe (sempre), e os ficheiros
#: de produto que ele abre. Um passo novo da familia entra aqui no mesmo commit
#: que a linha `call :step` dele.
READS = {
    "panel2-dom-probe": ("_main\\_panel2-dom-probe.js", "__PAGE__"),
    "panel-header-oracle": ("_main\\panel-header-oracle.js", "__PAGE__"),
    "panel-history-clip": ("_main\\panel-history-clip-probe.mjs", "__PAGE__"),
    "panel-drag-targets": ("_main\\panel-drag-targets-oracle.js", "app\\panel\\strip-drag.js"),
    "panel-pause-payload": ("_main\\panel-pause-payload-oracle.py", "app\\webview\\sotto_webview.py"),
    "red-as-expected-panel-pause-payload": ("_main\\panel-pause-payload-oracle.py",
                                            "app\\webview\\sotto_webview.py"),
    "caption-visual-dom": ("_main\\caption-visual-dom-oracle.js", "__PAGE__"),
    "red-as-expected-caption-visual-dom": ("_main\\caption-visual-dom-oracle.js", "__PAGE__"),
}


def missing_from(deps, wanted):
    have = {d.replace("/", "\\").lower() for d in deps}
    return [w for w in wanted if w.replace("/", "\\").lower() not in have]


def judge(cmd_path):
    """(ok, [(arm, real, want)])."""
    decl = declarations(cmd_path)
    checks = []
    # `panel_assets()` already hands back the repo-relative WINDOWS path; taking it
    # apart again produced `app\panel\panel\themes\...` (measured 2026-11-07), so the
    # gate compared against paths that exist nowhere and reported 15 phantom misses.
    page = [win for _rel, win in panel_assets()]
    for step, required in READS.items():
        if step not in decl:
            checks.append((f"{step} declarado na .cmd", "ausente", "presente"))
            continue
        always, deps = decl[step]
        wanted = []
        for item in required:
            wanted.extend(page if item == "__PAGE__" else [item])
        checks.append((f"A1 {step}: deps cobrem o que o passo le",
                       sorted(missing_from(deps, wanted)), []))
        absent = [d for d in deps if not os.path.exists(os.path.join(REPO, d))]
        checks.append((f"A2 {step}: cada dep declarada existe", absent, []))
        # Um passo `always` nunca e' HIT, logo as deps nao governam nada nele --
        # a verificacao continuaria a passar sem medir cache nenhuma.
        checks.append((f"A3 {step} NAO e' `always` (as deps governam a cache)",
                       always, False))
    ok = all(real == want for _name, real, want in checks)
    return ok, checks


def main(argv):
    if "--neg-arm" in argv:
        tmp = tempfile.mkdtemp(prefix="panel-deps-")
        try:
            copy = os.path.join(tmp, "_audit-verify-all.cmd")
            shutil.copyfile(CMD, copy)
            with io.open(copy, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            # THE MUTATION IS SCOPED TO ONE LINE, and that scoping is itself a
            # measured correction: the first `zipc-panels.js;` in the file belongs
            # to ANOTHER step, so the old unscoped `replace(..., 1)` mutated a
            # declaration this gate does not judge and the mutant "passed"
            # (measured 2026-11-07: `NEG-ARM: FALHOU -- o mutante passou`).
            lines = text.split("\n")
            mutated, hit = text, False
            for i, line in enumerate(lines):
                if line.startswith("  call :step panel-header-oracle "):
                    lines[i] = line.replace("app\\panel\\themes\\zipc-panels.js;", "", 1)
                    hit = lines[i] != line
                    break
            if hit:
                mutated = "\n".join(lines)
            if not hit:
                print("NEG-ARM: IMPOSSIVEL -- a deps mutavel nao esta na copia")
                return 2
            with io.open(copy, "w", encoding="utf-8", newline="") as fh:
                fh.write(mutated)
            ok, checks = judge(copy)
            for name, real, want in checks:
                print(f"[{'PASS' if real == want else 'FAIL'}] {name}")
                if real != want:
                    print(f"       real = {real!r}\n       want = {want!r}")
            print(f"\nNEG-ARM: {'PASS -- o mutante foi apanhado' if not ok else 'FALHOU -- o mutante passou'}")
            return 0 if not ok else 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    ok, checks = judge(CMD)
    for name, real, want in checks:
        arm(name, real, want)
    print(f"\nVERDICT: {'PASS' if ok else 'FAIL'} -- {sum(RESULTS)}/{len(RESULTS)} arm(s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
