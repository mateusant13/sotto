#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check-bug-hunt-wiring.py — portao do adaptador `bug-hunt-sotto`.

Prova, so por leitura de bytes, que o MODO BUG-HUNT do Sotto tem uma porta de entrada descobrivel e
que essa porta **nao** e uma segunda fonte de verdade:

  1. agents-route       `AGENTS.md` nomeia `bug-hunt-sotto` num bloco de defeito NAO-TRIVIAL
  2. postmortem-timing  o bloco do postmortem continua a dizer: bug ACTIVO -> nada de postmortem
  3. skill-frontmatter  a skill existe e declara `name: bug-hunt-sotto`
  4. skill-links        a skill liga `docs/bug-hunt.md`, `_main/caption-dup-repro.py` e postmortem-sotto
  5. doc-11-steps       `docs/bug-hunt.md` ainda declara os 11 passos e os quatro portoes
  6. thin-no-copy       a skill cabe no tecto de bytes e nao copia os titulos do protocolo

Modo mutacao (`--mutation NAME`, `--all-mutations`): copia a raiz para um directorio temporario,
ASSEGURA primeiro que a copia intacta PASSA (`COPY-BROKEN`, rc=2, se nao passar — uma recusa por
ficheiro em falta nao e prova de detector), so depois muta o que o nome diz, e exige FAIL.

Sem `subprocess`, sem rede, sem escrita dentro da raiz do repo.
Saida: uma linha por verificacao + `BATTERY-VERDICT check-bug-hunt-wiring PASS|FAIL checks=N fail=M`.
rc: 0 PASS, 1 FAIL, 2 sem veredicto (raiz invalida, copia partida ou erro de uso).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile

SKILL_REL = os.path.join(".opencode", "skills", "bug-hunt-sotto", "SKILL.md")
DOC_REL = os.path.join("docs", "bug-hunt.md")
REPRO_REL = os.path.join("_main", "caption-dup-repro.py")
AGENTS_REL = "AGENTS.md"

SKILL_MAX_BYTES = 5200
GATES = ("input-path", "seam-coverage", "bug-ledger", "tooling-intent")
DOC_HEADINGS = (
    "### O la\u00e7o (11 passos, comprimido; a ordem importa)",
    "### Os quatro port\u00f5es que o tornam obrigat\u00f3rio",
)
COPY_FILES = (AGENTS_REL, SKILL_REL, DOC_REL, REPRO_REL)


def _read(root: str, rel: str) -> str:
    with open(os.path.join(root, rel), "rb") as fh:
        return fh.read().decode("utf-8", "replace")


def _write(root: str, rel: str, text: str) -> None:
    with open(os.path.join(root, rel), "wb") as fh:
        fh.write(text.encode("utf-8"))


# ---------------------------------------------------------------- as seis provas


def check_agents_route(root: str):
    try:
        text = _read(root, AGENTS_REL)
    except OSError as exc:
        return False, "AGENTS.md ilegivel: %s" % exc
    index = text.find("bug-hunt-sotto")
    if index < 0:
        return False, "AGENTS.md nao nomeia a skill bug-hunt-sotto"
    before = text[max(0, index - 320):index].upper()
    if "NAO-TRIVIAL" not in before:
        return False, "a mencao a bug-hunt-sotto nao vive num bloco de defeito NAO-TRIVIAL"
    return True, "AGENTS.md roteia defeito nao-trivial -> bug-hunt-sotto"


def check_postmortem_timing(root: str):
    try:
        text = _read(root, AGENTS_REL)
    except OSError as exc:
        return False, "AGENTS.md ilegivel: %s" % exc
    index = text.find("DEPOIS DO INCIDENTE: POSTMORTEM")
    if index < 0:
        return False, "AGENTS.md perdeu o bloco DEPOIS DO INCIDENTE: POSTMORTEM"
    segment = text[index:index + 1400]
    cut = segment.find("\n## ", 4)
    if cut > 0:
        segment = segment[:cut]
    if "ACTIVO" not in segment:
        return False, "o bloco do postmortem deixou de dizer que com o bug ACTIVO nao ha postmortem"
    if "bug-hunt" not in segment.lower():
        return False, "o bloco do postmortem deixou de encaminhar para o bug-hunt"
    return True, "postmortem continua apos a contencao (bug ACTIVO -> bug-hunt)"


def check_skill_frontmatter(root: str):
    path = os.path.join(root, SKILL_REL)
    if not os.path.isfile(path):
        return False, "skill ausente: %s" % SKILL_REL
    text = _read(root, SKILL_REL)
    if not text.startswith("---"):
        return False, "skill sem frontmatter YAML"
    end = text.find("\n---", 3)
    if end < 0:
        return False, "frontmatter da skill nao fecha"
    front = text[3:end]
    if not re.search(r"^name:\s*bug-hunt-sotto\s*$", front, re.M):
        return False, "frontmatter sem `name: bug-hunt-sotto`"
    if not re.search(r"^description:\s*\S+", front, re.M):
        return False, "frontmatter sem `description:`"
    return True, "skill presente com frontmatter name/description"


def check_skill_links(root: str):
    try:
        text = _read(root, SKILL_REL)
    except OSError as exc:
        return False, "skill ilegivel: %s" % exc
    end = text.find("\n---", 3)
    body = text[end:] if end >= 0 else text
    missing = [
        needle
        for needle in ("docs/bug-hunt.md", "_main/caption-dup-repro.py", "postmortem-sotto")
        if needle not in body
    ]
    if missing:
        return False, "skill nao liga: %s" % ", ".join(missing)
    return True, "skill liga doc 11 passos + repro minimo + postmortem"


def check_doc_11_steps(root: str):
    try:
        text = _read(root, DOC_REL)
    except OSError as exc:
        return False, "docs/bug-hunt.md ilegivel: %s" % exc
    if "11 passos" not in text:
        return False, "docs/bug-hunt.md deixou de declarar os 11 passos"
    missing = [gate for gate in GATES if gate not in text]
    if missing:
        return False, "docs/bug-hunt.md perdeu portoes: %s" % ", ".join(missing)
    return True, "docs/bug-hunt.md ainda e a fonte dos 11 passos + 4 portoes"


def check_thin_no_copy(root: str):
    try:
        text = _read(root, SKILL_REL)
    except OSError as exc:
        return False, "skill ilegivel: %s" % exc
    size = len(text.encode("utf-8"))
    if size > SKILL_MAX_BYTES:
        return False, "skill gorda: %d B > %d B (segunda fonte de verdade)" % (size, SKILL_MAX_BYTES)
    for heading in DOC_HEADINGS:
        if heading in text:
            return False, "skill copia o titulo do protocolo: %r" % heading
    if "docs/bug-hunt.md" not in text:
        return False, "skill sem ponteiro ao protocolo: nao se sabe onde esta a fonte"
    return True, "skill fina (%d B <= %d B) e sem titulos copiados" % (size, SKILL_MAX_BYTES)


CHECKS = (
    ("agents-route", check_agents_route),
    ("postmortem-timing", check_postmortem_timing),
    ("skill-frontmatter", check_skill_frontmatter),
    ("skill-links", check_skill_links),
    ("doc-11-steps", check_doc_11_steps),
    ("thin-no-copy", check_thin_no_copy),
)


def run_checks(root: str):
    return [(name, ) + check(root) for name, check in CHECKS]


# --------------------------------------------------------------- bracos negativos

MUTATIONS = (
    "drop-agents-route",
    "drop-skill-doc-link",
    "drop-skill-repro-link",
    "drop-postmortem-timing",
    "append-protocol-copy",
)


def _tmp_dir() -> str:
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    if not os.path.isdir(base):
        base = tempfile.gettempdir()
    return base


def _copy_tree(root: str, dest: str) -> None:
    for rel in COPY_FILES:
        source = os.path.join(root, rel)
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(source, target)


def _drop_lines(root: str, rel: str, needle: str) -> int:
    text = _read(root, rel)
    kept = [line for line in text.splitlines(True) if needle not in line]
    removed = len(text.splitlines(True)) - len(kept)
    _write(root, rel, "".join(kept))
    return removed


def apply_mutation(root: str, name: str) -> None:
    if name == "drop-agents-route":
        if not _drop_lines(root, AGENTS_REL, "bug-hunt-sotto"):
            raise RuntimeError("AGENTS.md nao tinha linha nenhuma com bug-hunt-sotto")
        return
    if name == "drop-skill-doc-link":
        if not _drop_lines(root, SKILL_REL, "docs/bug-hunt.md"):
            raise RuntimeError("a skill nao tinha linha nenhuma com docs/bug-hunt.md")
        return
    if name == "drop-skill-repro-link":
        if not _drop_lines(root, SKILL_REL, "_main/caption-dup-repro.py"):
            raise RuntimeError("a skill nao tinha linha nenhuma com o repro")
        return
    if name == "drop-postmortem-timing":
        text = _read(root, AGENTS_REL)
        index = text.find("DEPOIS DO INCIDENTE: POSTMORTEM")
        if index < 0:
            raise RuntimeError("AGENTS.md sem bloco de postmortem para mutar")
        segment = text[index:index + 1400]
        cut = segment.find("\n## ", 4)
        if cut > 0:
            segment = segment[:cut]
        if "ACTIVO" not in segment:
            raise RuntimeError("o bloco do postmortem nao diz ACTIVO: nada para mutar")
        mutated = segment.replace("ACTIVO", "CONTIDO")
        _write(root, AGENTS_REL, text[:index] + mutated + text[index + len(segment):])
        return
    if name == "append-protocol-copy":
        skill = _read(root, SKILL_REL)
        doc = _read(root, DOC_REL)
        _write(root, SKILL_REL, skill + "\n" + doc)
        return
    raise RuntimeError("mutacao desconhecida: %s" % name)


def run_mutation(root: str, name: str):
    tmp = tempfile.mkdtemp(prefix="bug-hunt-wiring-", dir=_tmp_dir())
    try:
        real_root = os.path.realpath(root)
        if os.path.realpath(tmp).startswith(real_root + os.sep):
            raise RuntimeError("directorio temporario dentro da raiz do repo")
        _copy_tree(root, tmp)
        baseline = run_checks(tmp)
        if not all(ok for _, ok, _ in baseline):
            failed = [n for n, ok, _ in baseline if not ok]
            return "COPY-BROKEN", baseline, "copia intacta ja falha: %s" % ", ".join(failed)
        apply_mutation(tmp, name)
        mutated = run_checks(tmp)
        refused = [n for n, ok, _ in mutated if not ok]
        if refused:
            return "NEG-ARM PASS", mutated, "recusou por: %s" % ", ".join(refused)
        return "NEG-ARM FAIL", mutated, "o check passou numa copia mutada (detector cego)"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="portao do adaptador bug-hunt-sotto")
    parser.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument("--mutation", choices=MUTATIONS)
    parser.add_argument("--all-mutations", action="store_true")
    parser.add_argument("--list-mutations", action="store_true")
    args = parser.parse_args(argv)

    if args.list_mutations:
        for name in MUTATIONS:
            print(name)
        return 0

    root = os.path.abspath(args.root)
    for rel in COPY_FILES:
        if not os.path.isfile(os.path.join(root, rel)):
            print("BUG-HUNT-WIRING: NO-VERDICT raiz sem %s" % rel)
            return 2

    names = list(MUTATIONS) if args.all_mutations else ([args.mutation] if args.mutation else [])
    if not names:
        results = run_checks(root)
        for name, ok, detail in results:
            print("CHECK %-20s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
        fail = sum(1 for _, ok, _ in results if not ok)
        verdict = "PASS" if fail == 0 else "FAIL"
        print("BATTERY-VERDICT check-bug-hunt-wiring %s checks=%d fail=%d" % (verdict, len(results), fail))
        return 0 if fail == 0 else 1

    outcomes = []
    for name in names:
        try:
            status, results, detail = run_mutation(root, name)
        except (OSError, RuntimeError) as exc:
            print("MUTATION %-24s ERROR  %s" % (name, exc))
            return 2
        print("MUTATION %-24s %s  %s" % (name, status, detail))
        for check_name, ok, check_detail in results:
            print("  mut-check %-20s %s  %s" % (check_name, "PASS" if ok else "FAIL", check_detail))
        outcomes.append(status)

    if "COPY-BROKEN" in outcomes:
        print("BATTERY-VERDICT check-bug-hunt-wiring NO-VERDICT copy-broken mutations=%d"
              % len(outcomes))
        return 2
    fail = sum(1 for status in outcomes if status != "NEG-ARM PASS")
    verdict = "PASS" if fail == 0 else "FAIL"
    print("BATTERY-VERDICT check-bug-hunt-wiring %s mutations=%d neg-arm-fail=%d"
          % (verdict, len(outcomes), fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
