#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ORACLE: NINGUEM ESCREVE EM CHINESES NESTE REPO.

O QUE ISTO CAÇA. Uma classe de defeito REAL e RECORRENTE: uma palavra
portuguesa ou inglesa **substituída** por caracteres de outra escrita -- o
sinal de um IME que estava ligado. A frase continua a parecer uma frase, e o
signo nao aparece no terminal.

MEDIDO 2026-10-19 sobre os 3015 ficheiros de texto versionados (`git ls-files`):
**11 linhas, em 10 ficheiros**, com substituicao deste tipo. Uma delas estava
em CODIGO DE PRODUTO (`worker/audio_recorder.py`), e as outras em portões e
recibos -- ou seja, em material que os agentes leem e em material de que os
portões dependem.

A REGRA, E POR QUE TEM UM LIMIAR. Nao se pode banir toda a outra escrita: ha
material legitimo neste repo. O censo mediu os dois lados:

  * **defeito** (substituicao): 1 a 4 caracteres estranhos, dentro de prosa
    nossa -- porque uma palavra foi trocada, nao uma frase;
  * **legitimo** (amostra de outra lingua): 19 a 55 caracteres -- um fixture
    Devanagari para o probe de token-rate, uma citacao em japones, um
    documento em russo em `_moved/`.

O limiar e' **8**: mais do dobro do maior defeito (4) e menos de metade do
menor caso legitimo (19). A separacao nao e' um palpite -- e' a medida. E o
que o limiar NAO e': nao e' uma prova. E' uma triagem que **imprime a linha
exacta**, para se adjudicar em segundos. Um gate que atira uma lista de 200
ficheiros e' um gate que ninguem le; um gate que atira 3 linhas com ficheiro,
numero de linha e codepoint e' um gate que se atende.

O QUE NAO E' CAÇADO, E PORQUEM:

  * `.json` -- sao DADOS (transcricoes, fixtures, payloads de runtime). Texto
    nao-latino num payload de ASR e' o dado a falar, nao um defeito.
  * `_moved/` -- arvore estacionada de outro projecto, com documentacao em
    russo e japones. O proprio repo a chama "parked, not the product".
  * `node_modules/`, `zip-mockups/` -- dependencia e mockups.
  * PUNCTUACAO CJK (U+3000-U+303F) -- o ponto final japones `。` num doc de
    titulos e' pontuacao de uma lingua, nao uma palavra trocada. A regra caça
    LETRAS, nao pontuacao.

O BRACO NEGATIVO e' EXECUTADO: uma copia com um caracter CJK injurado tem de
ficar VERMELHA. Um gate que nunca viu o defeito nao provou que o ve.

`--neg-arm` faz o contralabor: injecta o caracter numa copia de um ficheiro
real e exige que o veredicto mude. Se nao conseguir injurar nada, diz
`CONTROL INVALID` e sai com codigo 5 -- nunca verde.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_CONTROL_INVALID = 5

# --- LETRAS de outras escritas. Nao inclui pontuacao (ver o docstring). ------
# Cirilico, hebraico, arabe, devanagari, tamil, telugu, kannada, malayalam,
# bengali, thai, lao, tibetano, hangul, han (CJK), kana.
#
# O GREGO NAO ESTA AQUI, de proposito: alfa, beta e delta sao notacao
#cientifica normal neste repo (canais alpha/beta no painel, e uma fila de
#indices que usa letras gregas como dados). Um portao que apanha notacao
#cientifica e' um portao que se desliga, e um portao desligado e' pior do que
#nenhum. O defeito que este gate caça -- a substituicao de uma palavra por
#ideogramas -- e' CJK na pratica integral: MEDIDO nas 11 linhas deste repo,
#TODAS as 11 eram ideogramas, e ZERO eram gregas.
FOREIGN_LETTER = re.compile(
    "[\u0400-\u04ff\u0530-\u058f\u0590-\u05ff"
    "\u0600-\u06ff\u0900-\u0dff\u0e00-\u0fff\u1000-\u109f"
    "\u1200-\u137f\u13a0-\u13ff\u1400-\u167f"
    "\u1680-\u169f\u16a0-\u16ff\u1700-\u171f\u1780-\u17ff"
    "\u3040-\u30ff\u3100-\u312f\u3130-\u318f\u31f0-\u31ff"
    "\u3400-\u4dbf\u4e00-\u9fff\ua960-\ua97f\uac00-\ud7af"
    "\uf900-\ufaff]"
)

TEXT_EXTENSIONS = {
    ".py", ".md", ".cmd", ".bat", ".js", ".mjs", ".css", ".html",
    ".txt", ".ps1", ".rc", ".sh", ".yml", ".yaml", ".toml", ".ini",
}

# Directorios e extensoes que ficam de fora, com o motivo.
EXCLUDED_DIRS = (
    ("_moved", "arvore estacionada de outro projecto (russo/japones)"),
    ("node_modules", "dependencia"),
    ("zip-mockups", "mockups de design"),
    (".git", "o proprio git"),
)
EXCLUDED_EXTENSIONS = (
    (".json", "sao DADOS: transcricoes, fixtures, payloads"),
    (".png", "binario"),
    (".jpg", "binario"),
    (".zip", "binario"),
    (".woff", "binario"),
    (".woff2", "binario"),
    (".ttf", "binario"),
    (".onnx", "binario"),
    (".wav", "binario"),
)

# Ficheiros INTEIROS, nomeados um a um, com o motivo de cada um. Uma
# excepcao declarada e justificada e' aceitavel; uma excepcao silenciosa nao e'.
#
# VAZIA de proposito. Houve uma vez um ficheiro aqui -- o catalogo de
# §7.21 do recibo mestre -- que guardava ideogramas de PROPOSITO, para o
# catalogo ser verificavel a olho. A solucao foi melhor do que a excepcao: o
# catalogo passou a descrever os caracteres POR CODEPOINT, que e' mais
# legivel para quem nao le chines, e este repo passou a nao ter NENHUM ficheiro
# com ideogramas de proposito. Um portao com a lista de excepcoes vazia e' um
# portao que ainda nao precisou de ser execeptuado -- e a lista fica a saida
# para o dia em que for preciso, com o motivo obrigatorio.
EXCLUDED_FILES = ()

# O limiar: ver o docstring. Medido: maior defeito = 4, menor caso legitimo = 19.
MAX_FOREIGN_LETTERS = 8

MIN_LINE_LENGTH = 12   # um ficheiro de 3 linhas nao e' "prosa"


def tracked_files():
    """Os ficheiros versionados que este gate le. `git ls-files` e' a fonte:
    o que esta em disco mas nao esta no repo nao interessa a ninguem."""
    proc = subprocess.run(["git", "-C", ROOT, "ls-files"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def excluded(rel):
    parts = rel.replace("\\", "/").split("/")
    for name, _why in EXCLUDED_DIRS:
        if name in parts:
            return True
    flat = rel.replace("\\", "/")
    for name, _why in EXCLUDED_FILES:
        if flat == name:
            return True
    ext = os.path.splitext(rel)[1].lower()
    for name, _why in EXCLUDED_EXTENSIONS:
        if ext == name:
            return True
    return False


def scan_text(text):
    """(linha, coluna, run) para cada run de letras estrangeiras. 1-based."""
    hits = []
    for lineno, line in enumerate(text.split("\n"), 1):
        for m in FOREIGN_LETTER.finditer(line):
            run = m.group(0)
            hits.append((lineno, m.start() + 1, run))
    return hits


def collect(files, root=ROOT):
    """[(rel, [(lineno, coluna, run), ...])] para os ficheiros que passam."""
    found = []
    for rel in files:
        if excluded(rel):
            continue
        if os.path.splitext(rel)[1].lower() not in TEXT_EXTENSIONS:
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        if len(text) < MIN_LINE_LENGTH:
            continue
        hits = scan_text(text)
        if hits and len(hits) <= MAX_FOREIGN_LETTERS:
            found.append((rel, hits))
    return found


def describe(run):
    return " ".join("U+%04X(%s)" % (ord(c), unicodedata.name(c, "?")[:22])
                     for c in sorted(set(run)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true",
                        help="control: injecta um caracter estranho numa "
                             "copia e exige que o gate a rejeite")
    args = parser.parse_args(argv)

    files = tracked_files()
    if files is None:
        print("RED   nao consegui ler `git ls-files`")
        return EXIT_FAIL
    print("ficheiros versionados: %d" % len(files))

    found = collect(files)
    total_letters = sum(len(hits) for _rel, hits in found)

    if args.neg_arm:
        # O CONTROL tem de MUTAR de verdade. Se nao conseguir injectar nada,
        # tem de dizer CONTROL INVALID -- nunca verde.
        if not files:
            print("CONTROL INVALID -- nao ha ficheiros para mutar")
            return EXIT_CONTROL_INVALID
        target = None
        for rel in files:
            if not excluded(rel) and os.path.splitext(rel)[1].lower() in TEXT_EXTENSIONS:
                target = rel
                break
        if target is None:
            print("CONTROL INVALID -- nenhum ficheiro elegivel para mutar")
            return EXIT_CONTROL_INVALID
        tmp = tempfile.mkdtemp(prefix="foreign-chars-")
        try:
            copy = os.path.join(tmp, "mutant.md")
            with open(os.path.join(ROOT, target), "r", encoding="utf-8",
                      errors="replace") as handle:
                body = handle.read()
            # injeta um ideograma CJK no MEIO de uma palavra latina
            mutated = body.replace("the", "t" + "\u4e2d" + "he", 1)
            if mutated == body:
                mutated = body + "\n\numa palavra injectada: a" + "\u4e2d" + "b\n"
            with open(copy, "w", encoding="utf-8") as handle:
                handle.write(mutated)
            control = collect([os.path.relpath(copy, tmp)], root=tmp)
            # o ficheiro mutado tem de ser REJECTED
            rejected = bool(control)
            print("CONTROL: mutacao em %s -> %s"
                  % (target, "REJEITADA (o gate viu)" if rejected else "ACEITA"))
            if not rejected:
                print("CONTROL INVALID -- o gate nao viu a mutacao")
                return EXIT_CONTROL_INVALID
            print("AGENTS-CHARS CONTROL PASS")
            return EXIT_PASS
        finally:
            try:
                for name in os.listdir(tmp):
                    os.unlink(os.path.join(tmp, name))
                os.rmdir(tmp)
            except OSError:
                pass

    print("\nARMS")
    if not found:
        print("  GREEN  nenhum ficheiro versionado tem uma letra de outra "
              "escrita colada a prosa nossa")
    for rel, hits in found:
        print("  RED    %s  (%d letra%s)"
              % (rel, len(hits), "" if len(hits) == 1 else "s"))
        for lineno, col, run in hits:
            print("          linha %d, coluna %d: %s" % (lineno, col, describe(run)))
    print("\n  %d ficheiro(s) com %d letra(s) estranha(s)"
          % (len(found), total_letters))

    verdict = "PASS" if not found else "FAIL"
    print("\nAGENTS-CHARS %s -- limiar %d letra(s) estranha(s) por ficheiro"
          % (verdict, MAX_FOREIGN_LETTERS))
    print("VERDICT: " + verdict)
    return EXIT_PASS if not found else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
