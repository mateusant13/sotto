#!/usr/bin/env python3
"""SPEC-CITATIONS -- a especificacao aponta para ficheiros que existem, e para linhas que existem.

O defeito que este portao existe para apanhar, MEDIDO em 2026-11-11: o `12-GLOSSARY.md`
nasceu com uma citacao `panel-visibility` que apontava para o sitio errado e com
`load_shedding:60` onde a constante estava na `:47`; o `README.md` listava um
`00-PROMISE.md` que nao existia; e um documento sem a seccao `Lacunas` esquece
silenciosamente o que nao sabe. Uma especificacao que cita um ficheiro inexistente
nao e' uma especificacao: e' prosa com numeros.

O que ele julga (cada braco diz o seu nome no output):

  A1  toda citacao `<ficheiro>:<linha>` resolve para um ficheiro do repo
  A2  toda linha citada existe no ficheiro (<= o numero de linhas)
  A3  todo o documento nomeado na tabela do `README.md` existe em `docs/spec/`
  A4  nenhum documento de `docs/spec/` fica FORA da tabela do `README.md`
  A5  todo o `02..09` e o `12` tem a seccao `## Lacunas`

A resolucao de caminho e' a mesma que um leitor humano faz: o nome citado pode vir
com ou sem raiz (`sotto_webview.py` vs `app/webview/sotto_webview.py`), por isso as
raizes conhecidas sao tentadas em ordem e o AMBIGUO e' reportado (dois ficheiros com o
mesmo nome em raizes diferentes e' uma citacao que nao identifica nada).

rc=0 verde, rc=1 falha, rc=2 sem populacao (CANNOT-MEASURE, nunca PASS).

    python _main/spec-citations-oracle.py
    python _main/spec-citations-oracle.py --neg-arm   # muta uma COPIA e exige RED
"""
from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "spec"
README = SPEC / "README.md"

#: As raizes onde um nome citado pode viver. A ordem e' a do repo, nao um gosto.
ROOTS = ("", "app/webview", "app/panel", "app", "worker", "_main", "_main/warm-engine",
         "docs", "docs/bend", "tools", "_main/_cache")

#: As extensoes que uma citacao pode nomear. `md` entra porque os documentos se citam.
EXTS = ("py", "js", "mjs", "css", "html", "json", "cmd", "md", "bend", "xml", "yml")

CITE = re.compile(
    r"`?([A-Za-z0-9_][\w./\\-]*\.(?:%s))[:`\s]*?(\d{1,6})`?" % "|".join(EXTS))

#: Documentos que TEM de escrever o que nao sabem.
NEEDS_LACUNAS = ("02-BOOT.md", "03-CAPTURE.md", "04-ENGINES.md", "05-LIVE-PATH.md",
                 "06-YOUTUBE.md", "07-HISTORY-STATE.md", "08-PANELS-UX.md",
                 "09-FAILURE-MODES.md", "12-GLOSSARY.md")

EXIT_PASS, EXIT_FAIL, EXIT_EMPTY = 0, 1, 2


def _lines(path):
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def resolve(name, root):
    """O caminho real de um nome citado, ou None. Devolve (path, ambiguous)."""
    rel = name.replace("\\", "/")
    hits = []
    for base in ROOTS:
        cand = (root / base / rel) if base else (root / rel)
        if cand.is_file():
            hits.append(cand)
    if not hits:
        return None, False
    # O mesmo ficheiro por dois caminhos nao e' ambiguidade.
    uniq = {(h.resolve()) for h in hits}
    return hits[0], len(uniq) > 1


def check(spec_dir, root):
    """Julga um directorio de especificacao. Devolve (ok, lines, stats)."""
    out, bad = [], 0
    docs = sorted(p for p in spec_dir.glob("*.md"))
    stats = {"docs": len(docs), "cites": 0, "unresolved": [], "extent": [],
             "ambiguous": [], "index_missing": [], "index_orphan": []}
    if not docs:
        return False, ["SPEC-CITATIONS CANNOT-MEASURE: nenhum documento em %s" % spec_dir], stats

    extent: dict = {}

    def line_count(path):
        """As linhas de um ficheiro, contadas UMA vez (1214 citacoes = 1214 leituras sem isto)."""
        key = str(path)
        if key not in extent:
            extent[key] = len(_lines(path))
        return extent[key]

    for doc in docs:
        for lineno, text in enumerate(_lines(doc), 1):
            for m in CITE.finditer(text):
                name, line = m.group(1), int(m.group(2))
                if name.endswith(".md") and line < 10:
                    continue  # "STATUS.md com 6 seccoes" nao e' uma citacao de linha
                stats["cites"] += 1
                path, ambiguous = resolve(name, root)
                if path is None:
                    stats["unresolved"].append((doc.name, lineno, name))
                    continue
                if ambiguous:
                    stats["ambiguous"].append((doc.name, lineno, name))
                total = line_count(path)
                if line > total:
                    stats["extent"].append((doc.name, lineno, name, line, total))

    for doc, lineno, name in stats["unresolved"]:
        out.append("  A1 RED %s:%d cita `%s`, que nao existe no repo" % (doc, lineno, name))
    out.append("  A1 %s  citacoes resolvidas: %d, sem ficheiro: %d"
               % ("GREEN" if not stats["unresolved"] else "RED",
                  stats["cites"] - len(stats["unresolved"]), len(stats["unresolved"])))
    bad += bool(stats["unresolved"])

    for doc, lineno, name, line, total in stats["extent"]:
        out.append("  A2 RED %s:%d cita `%s:%d` e o ficheiro tem %d linha(s)"
                   % (doc, lineno, name, line, total))
    out.append("  A2 %s  linhas dentro do ficheiro: %d fora de alcance"
               % ("GREEN" if not stats["extent"] else "RED", len(stats["extent"])))
    bad += bool(stats["extent"])

    index = _lines(README) if README.is_file() else []
    named = set()
    for text in index:
        for m in re.finditer(r"`([0-9A-Za-z_.-]+\.md)`", text):
            named.add(m.group(1))
    named = {n for n in named if n != "README.md"}
    present = {p.name for p in docs}

    stats["index_missing"] = sorted(n for n in named if n not in present)
    stats["index_orphan"] = sorted(p for p in present if p not in named and p != "README.md")
    for n in stats["index_missing"]:
        out.append("  A3 RED README.md indexa `%s`, que nao existe em docs/spec/" % n)
    out.append("  A3 %s  documentos indexados: %d, ausentes do disco: %d"
               % ("GREEN" if not stats["index_missing"] else "RED",
                  len(named), len(stats["index_missing"])))
    bad += bool(stats["index_missing"])

    for n in stats["index_orphan"]:
        out.append("  A4 RED `%s` existe em docs/spec/ e nao esta' na tabela do README.md" % n)
    out.append("  A4 %s  documentos no disco: %d, fora da tabela: %d"
               % ("GREEN" if not stats["index_orphan"] else "RED",
                  len(present) - 1, len(stats["index_orphan"])))
    bad += bool(stats["index_orphan"])

    missing_lac = []
    for name in NEEDS_LACUNAS:
        path = spec_dir / name
        if not path.is_file():
            continue  # A3/A4 ja' nomeiam o ausente
        body = "\n".join(_lines(path))
        if "## Lacunas" not in body:
            missing_lac.append(name)
    for n in missing_lac:
        out.append("  A5 RED `%s` nao tem a seccao `## Lacunas` (o que nao sabe nao se escreve)" % n)
    out.append("  A5 %s  documentos com o que-nao-se-sabe escrito: %d de %d"
               % ("GREEN" if not missing_lac else "RED",
                  len([n for n in NEEDS_LACUNAS if (spec_dir / n).is_file()]) - len(missing_lac),
                  len(NEEDS_LACUNAS)))
    bad += bool(missing_lac)

    if stats["ambiguous"]:
        for doc, lineno, name in stats["ambiguous"]:
            out.append("  A1 WARN %s:%d cita `%s`, que existe em duas raizes -- a citacao nao "
                       "identifica um ficheiro so'" % (doc, lineno, name))
    return bad == 0, out, stats


def _verdict(ok, out, stats):
    for line in out:
        print(line)
    print("\nSPEC-CITATIONS: docs=%d citacoes=%d sem_ficheiro=%d fora_de_alcance=%d "
          "index_ausente=%d fora_da_tabela=%d"
          % (stats["docs"], stats["cites"], len(stats["unresolved"]), len(stats["extent"]),
             len(stats["index_missing"]), len(stats["index_orphan"])))
    print("SPEC-CITATIONS VERDICT: %s" % ("PASS" if ok else "FAIL"))
    return EXIT_PASS if ok else EXIT_FAIL


def neg_arm():
    """Muta uma COPIA quatro vezes; cada mutante tem de derrubar O SEU braco.

    As mutacoes sao TEXTUAIS e plantadas na copia, nunca "o documento de HEAD" -- um
    negativo que depende do estado do repo apodrece no dia em que a cura e' escrita.
    """
    fails = 0
    def case(name, mutate, want):
        nonlocal fails
        tmp = Path(tempfile.mkdtemp(prefix="speccite-neg-"))
        try:
            spec = tmp / "docs" / "spec"
            shutil.copytree(SPEC, spec)
            mutate(spec, tmp)
            global README
            saved = README
            README = spec / "README.md"
            try:
                ok, out, _ = check(spec, ROOT)
            finally:
                README = saved
            red = [l for l in out if ("RED" in l and want in l)]
            if ok or not red:
                print("NEG-ARM %s FAIL -- o oraculo NAO ve a mutacao (ok=%s)" % (name, ok))
                fails += 1
            else:
                print("NEG-ARM %s PASS -- RED as designed: %s" % (name, red[0].strip()[:120]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def m1(spec, _root):
        p = spec / "05-LIVE-PATH.md"
        p.write_text(p.read_text(encoding="utf-8")
                     + "\n`[MEASURED]` `_main/oracle-que-nao-existe.py:12` diz que sim.\n",
                     encoding="utf-8")

    def m2(spec, _root):
        p = spec / "06-YOUTUBE.md"
        p.write_text(p.read_text(encoding="utf-8")
                     + "\n`[CODE]` `app/webview/youtube_cdp_source.py:999999`\n", encoding="utf-8")

    def m3(spec, _root):
        p = spec / "README.md"
        p.write_text(p.read_text(encoding="utf-8").replace(
            "| `STATUS.md` |", "| `99-DOC-QUE-NAO-EXISTE.md` | falta |\n| `STATUS.md` |", 1),
            encoding="utf-8")

    def m4(spec, _root):
        p = spec / "12-GLOSSARY.md"
        p.write_text(p.read_text(encoding="utf-8").replace("## Lacunas", "## Fim", 1),
                     encoding="utf-8")

    case("citacao-de-ficheiro-inexistente", m1, "A1 RED")
    case("linha-alem-do-fim", m2, "A2 RED")
    case("indice-com-documento-ausente", m3, "A3 RED")
    case("documento-sem-lacunas", m4, "A5 RED")
    print("\nNEG-ARM: %s -- %d/%d mutantes apanhados"
          % ("PASS" if not fails else "FAIL", 4 - fails, 4))
    return EXIT_FAIL if not fails else EXIT_PASS


def main(argv):
    if "--neg-arm" in argv:
        return neg_arm()
    ok, out, stats = check(SPEC, ROOT)
    return _verdict(ok, out, stats)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
