#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# BLOCKS: BUG-20261023-01 BUG-20261021-02
"""TOOLING-INTENT ORACLE -- nenhuma ferramenta nova sem declarar o bug que serve.

A LEI (manager, `state/research/bug-hunt-workflow-approaches.md`, 2026-10-23,
§\"Manager changes to consider\"): *\"Tooling work is eligible during that effort
only when it removes a named bug's concrete blocker to reproduction, diagnosis,
containment, repair, or verification.\"* E, mecanicamente: *\"Add
`blocked_bug_ids` and `evidence_unblocked` to any proposal for new orchestration
tooling; leave both empty only when the owner explicitly chooses capability work
over bug reduction.\"*

O DEFEITO QUE ISTO FECHA. Neste repo ha ~180 ficheiros `*oracle*.py` / `*-gate.py`
/ `*-guard.py`, e nenhum dizia para que bug existia. Um portao sem intencao
declarada pode passar anos verde sem impedir nada -- e o proprio acto de o
escrever parece progresso. A nota diz o contrario: a ferramenta existe para
desbloquear um bug nomeado, ou entao e trabalho de capacidade e TEM de o dizer.

O CONTRATO (no cabecalho do ficheiro, nas primeiras 60 linhas, no inicio da
linha -- um comentario no meio do codigo nao conta):

    BLOCKS: BUG-20261023-01 BUG-20261021-02
        Cada id TEM de existir em `_main/bug-ledger.json`. Um id inventado e
        uma intencao falsa, e e vermelho.
    NO-BUG: <razao com >=20 caracteres>
        Trabalho de capacidade. E permitido -- mas tem de ser dito, e a razao
        tem de existir.

Um ficheiro que nao declare nenhum dos dois so passa se estiver no
`_main/tooling-intent-baseline.json` (a populacao que ja existia quando a lei
nasceu). A contagem de nao declarados e IMPRESSA e nao pode crescer: e um
ratchet, nao uma amnistia. Um ficheiro novo sem declaracao e vermelho.

LIMITE DECLARADO: o baseline e uma lista de nomes, logo um ficheiro do baseline
a quem alguem apague o cabecalho continua a passar. Fechar isso exigiria
historia, nao um censo. O que o portao garante e o que a nota pedia: nenhuma
ferramenta NOVA sem intencao, e a divida antiga visivel e a encolher.

    python _main/tooling-intent-oracle.py            # rc=0 verde, rc=2 vermelho
    python _main/tooling-intent-oracle.py --neg-arm  # rc=1 POR DESENHO

NAO lanca nada: le cabecalhos e o ledger. Pode entrar na bateria.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASELINE = os.path.join(HERE, 'tooling-intent-baseline.json')
LEDGER = os.path.join(HERE, 'bug-ledger.json')
TOOL_GLOBS = ('*oracle*.py', '*-gate.py', '*-guard.py', '*_gate*.py',
              '*_guard*.py')
DECL = re.compile(r'^#\s*(BLOCKS|NO-BUG):(.*)$')
BUG_ID = re.compile(r'^BUG-\d{8}-\d{2}$')
HEAD_LINES = 60
MIN_NOBUG = 20


def _read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def population(root):
    """{nome: caminho} dos ficheiros de enforcement, sem duplicados."""
    out = {}
    for pat in TOOL_GLOBS:
        for path in glob.glob(os.path.join(root, pat)):
            out.setdefault(os.path.basename(path), path)
    return out


def declaration(path):
    """(kind, payload) do cabecalho, ou (None, None)."""
    for line in _read(path).splitlines()[:HEAD_LINES]:
        m = DECL.match(line.strip())
        if m:
            return m.group(1), m.group(2).strip()
    return None, None


def ledger_ids(path=LEDGER):
    try:
        with open(path, encoding='utf-8') as fh:
            led = json.load(fh)
    except (OSError, ValueError):
        return set()
    return {b.get('id') for b in (led.get('bugs') or []) if b.get('id')}


def check(files, known_ids, baseline):
    """[(nome, estado, razao)] + contagens."""
    rows = []
    for name in sorted(files):
        kind, payload = declaration(files[name])
        if kind == 'BLOCKS':
            ids = payload.split()
            bad = [i for i in ids if not BUG_ID.match(i)]
            unknown = [i for i in ids if BUG_ID.match(i) and i not in known_ids]
            if not ids:
                rows.append((name, 'RED', 'BLOCKS vazio: nomear o bug ou usar NO-BUG'))
            elif bad:
                rows.append((name, 'RED', 'BLOCKS com id malformado: %s' % bad))
            elif unknown:
                rows.append((name, 'RED', 'BLOCKS aponta para bug fora do ledger: %s'
                             % unknown))
            else:
                rows.append((name, 'DECLARED', 'BLOCKS %s' % ' '.join(ids)))
        elif kind == 'NO-BUG':
            if len(payload) < MIN_NOBUG:
                rows.append((name, 'RED', 'NO-BUG sem razao (%d < %d chars)'
                             % (len(payload), MIN_NOBUG)))
            else:
                rows.append((name, 'DECLARED', 'NO-BUG %s' % payload[:58]))
        else:
            if name in baseline:
                rows.append((name, 'GRANDFATHERED', 'sem declaracao (no baseline)'))
            else:
                rows.append((name, 'RED', 'ferramenta nova sem BLOCKS: nem NO-BUG:'))
    return rows


def verdict(rows, baseline, root):
    declared = [r for r in rows if r[1] == 'DECLARED']
    grand = [r for r in rows if r[1] == 'GRANDFATHERED']
    red = [r for r in rows if r[1] == 'RED']
    for name, state, why in red:
        print('RED  %-46s %s' % (name, why))
    for name, state, why in declared:
        print('DECL %-46s %s' % (name, why))
    print('populacao: %d ferramenta(s) em %s' % (len(rows), root))
    print('declaradas: %d | baseline (sem declaracao): %d | vermelhas: %d'
          % (len(declared), len(grand), len(red)))
    print('ratchet: baseline declara %d; hoje sem declaracao sao %d (nao pode crescer)'
          % (len(baseline), len(grand)))
    ok = not red and len(grand) <= len(baseline)
    if len(grand) > len(baseline):
        print('RED  a divida de ferramentas sem intencao CRESCEU (%d > %d)'
              % (len(grand), len(baseline)))
    return ok


def neg_arm(root):
    """3 mutantes, cada um numa arvore LIMPA propria: um vermelho so conta se
    for pela razao do mutante, nao por lixo deixado pelo anterior."""
    known = {'BUG-20261023-01'}
    baseline = ['_old-oracle.py']
    clean = {
        '_ok-oracle.py': '# BLOCKS: BUG-20261023-01\nx = 1\n',
        '_old-oracle.py': 'x = 1\n',
        '_no-bug-gate.py': ('# NO-BUG: ratchet de divida antiga, nao '
                            'desbloqueia bug nomeado\nx = 1\n'),
    }
    mutants = [
        ('M1 ferramenta nova sem declaracao', '_novo-oracle.py', 'x = 1\n'),
        ('M2 BLOCKS aponta para um bug fora do ledger', '_bad-id-oracle.py',
         '# BLOCKS: BUG-19990101-99\nx = 1\n'),
        ('M3 BLOCKS vazio', '_empty-blocks-guard.py', '# BLOCKS:\nx = 1\n'),
        ('M4 NO-BUG sem razao', '_no-reason-gate.py', '# NO-BUG: nao\nx = 1\n'),
    ]
    caught = 0
    for name, mutant_name, body in mutants:
        tmp = tempfile.mkdtemp(prefix='tooling-intent-neg-')
        try:
            for fname, fbody in clean.items():
                with open(os.path.join(tmp, fname), 'w', encoding='utf-8') as fh:
                    fh.write(fbody)
            with open(os.path.join(tmp, mutant_name), 'w', encoding='utf-8') as fh:
                fh.write(body)
            try:
                rows = check(population(tmp), known, baseline)
                ok = verdict(rows, baseline, tmp)
            except Exception as exc:  # noqa: BLE001
                ok = False
                print('       (o mutante rebentou: %r)' % (exc,))
            if not ok:
                print('NEG-ARM %-48s RED as expected' % name)
                caught += 1
            else:
                print('NEG-ARM %-48s ** INERT **' % name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # Controlo POSITIVO: a arvore limpa tem de PASSAR. Sem isto, um portao que
    # fica vermelho sempre apanhava todos os mutantes e nao provava nada.
    tmp = tempfile.mkdtemp(prefix='tooling-intent-pos-')
    try:
        for fname, fbody in clean.items():
            with open(os.path.join(tmp, fname), 'w', encoding='utf-8') as fh:
                fh.write(fbody)
        rows = check(population(tmp), known, baseline)
        positive = verdict(rows, baseline, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('POS-ARM %-48s %s' % ('arvore limpa', 'PASS as expected' if positive
                                else '** RED (o portao nao distingue) **'))
    print('NEG-ARM %d of %d mutant(s) caught' % (caught, len(mutants)))
    if caught == len(mutants) and positive:
        print('NEG-ARM PASS')
        return 1
    print('VERDICT: FAIL -- %d mutante(s) de intencao passaram'
          % (len(mutants) - caught))
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true',
                    help='3 mutantes num diretorio temporario')
    ap.add_argument('--root', default=HERE, help='onde procurar as ferramentas')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    if args.neg_arm:
        return neg_arm(args.root)
    try:
        with open(BASELINE, encoding='utf-8') as fh:
            baseline = (json.load(fh).get('undeclared') or [])
    except (OSError, ValueError) as exc:
        print('RED  o baseline nao pode ser lido (%r): sem baseline nao ha '
              'ratchet, so uma promessa' % (exc,))
        print('TOOLING-INTENT VERDICT FAIL')
        return 2
    rows = check(population(args.root), ledger_ids(), set(baseline))
    ok = verdict(rows, baseline, args.root)
    print('TOOLING-INTENT VERDICT %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
