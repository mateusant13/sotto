#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# NO-BUG: ratchet estrutural (tamanho, funcoes longas, silencios); nao desbloqueia um bug nomeado, impede que a divida cresca
"""CODE-HEALTH ORACLE -- o "horrivel" medido, e um ratchet que so pode descer.

O PROBLEMA, MEDIDO 2026-10-23: `app/webview/sotto_webview.py` = **758 679 B / 13 273
linhas** num unico modulo; `worker/sotto_worker.py` = 386 286 B / 6 684 linhas;
`app/panel/panel.js` = 192 281 B / 3 660 linhas. Quarenta e sete `except: pass`.
Nao e uma opiniao de estilo: e a razao pela qual cada mudanca tem um raio de
explosao enorme e pela qual um `let` em TDZ ja matou o painel durante um dia.

O QUE ESTE PORTAO FAZ. Nao propoe um refactor e nao preme por um big-bang (as
notas que o dono mandou ler dizem o contrario: *"land one causal change at a
time"*, *"smaller batches"*). Mede, por ficheiro do produto, sete factos e exige
que **nenhum piore**:

    bytes, linhas, defs de topo, classes, funcao mais longa (linhas),
    `except ...: pass`, `global`

Uma funcao que cresce e um sitio onde um defeito se esconde; um ficheiro que
cresce e um merge que doi. O baseline e o estado medido no dia em que a lei
nasceu; o gate imprime a variacao e falha em QUALQUER aumento. Reduzir e sempre
verde -- e o objectivo.

REGRA PARA FICHEIROS NOVOS: um ficheiro do produto que nao esteja no baseline e
medido e impresso (nao falha por existir -- extrair e a cura), mas se passar de
`MAX_NEW_BYTES` falha: extrair 200 KB de um ficheiro para outro nao e um
refactor, e uma mudanca de sitio.

    python _main\\code-health-oracle.py            # rc=0 verde, rc=2 vermelho
    python _main\\code-health-oracle.py --update   # regenera o baseline (so com o dono de acordo)
    python _main\\code-health-oracle.py --neg-arm  # rc=1 POR DESENHO

NAO lanca nada: faz AST de ficheiros. Pode entrar na bateria.
"""
import argparse
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASELINE = os.path.join(HERE, 'code-health-baseline.json')
MAX_NEW_BYTES = 120000
METRICS = ('bytes', 'lines', 'defs', 'classes', 'max_func', 'except_pass',
           'globals')


def _read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def population(repo=REPO):
    """Ficheiros do PRODUTO (scratch com `_` a frente fica de fora)."""
    out = {}
    for rel_dir, exts in (('app/webview', ('.py',)), ('worker', ('.py',)),
                          ('app/panel', ('.js', '.css'))):
        d = os.path.join(repo, *rel_dir.split('/'))
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(exts) or name.startswith('_'):
                continue
            out['%s/%s' % (rel_dir, name)] = os.path.join(d, name)
    return out


def measure(path, rel):
    text = _read(path)
    row = {
        'bytes': os.path.getsize(path),
        'lines': text.count('\n') + (0 if text.endswith('\n') else 1),
        'defs': 0, 'classes': 0, 'max_func': 0, 'max_func_name': '',
        'except_pass': 0, 'globals': 0,
    }
    if not rel.endswith('.py'):
        return row
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        row['syntax_error'] = str(exc)
        return row
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            row['defs'] += 1
        elif isinstance(node, ast.ClassDef):
            row['classes'] += 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            span = (getattr(node, 'end_lineno', node.lineno) or node.lineno) \
                - node.lineno + 1
            if span > row['max_func']:
                row['max_func'] = span
                row['max_func_name'] = node.name
        elif isinstance(node, ast.ExceptHandler):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                row['except_pass'] += 1
        elif isinstance(node, ast.Global):
            row['globals'] += len(node.names)
    return row


def census(repo=REPO):
    return {rel: measure(path, rel) for rel, path in population(repo).items()}


def compare(today, baseline):
    """[(ficheiro, metrica, antes, agora)] de PIORAS, e o resto."""
    worse = []
    for rel, row in sorted(today.items()):
        base = baseline.get(rel)
        if not base:
            continue
        for m in METRICS:
            a = base.get(m, 0)
            b = row.get(m, 0)
            if b > a:
                worse.append((rel, m, a, b))
    return worse


def top_longest(today, n=10):
    rows = [(r['max_func'], r['max_func_name'], rel) for rel, r in today.items()]
    return sorted(rows, reverse=True)[:n]


def verdict(today, baseline, worse, new_files):
    for rel, row in sorted(today.items()):
        base = baseline.get(rel)
        if base is None:
            print('NEW  %-44s %7d B %5d linhas (fora do baseline)'
                  % (rel, row['bytes'], row['lines']))
        else:
            delta = row['bytes'] - base.get('bytes', 0)
            print('%s %-44s %7d B (%+d) %5d linhas  maior funcao=%d (%s)'
                  % ('SAME' if delta == 0 else ('LESS' if delta < 0 else 'MORE'),
                     rel, row['bytes'], delta, row['lines'],
                     row['max_func'], row['max_func_name'] or '-'))
    print('populacao: %d ficheiro(s) de produto | except-pass total=%d | global total=%d'
          % (len(today), sum(r['except_pass'] for r in today.values()),
             sum(r['globals'] for r in today.values())))
    print('as 5 funcoes mais longas (o proximo alvo de refactor):')
    for span, name, rel in top_longest(today, 5):
        print('   %4d linhas  %-34s %s' % (span, name, rel))
    ok = True
    for rel, m, a, b in worse:
        print('RED  %s: %s piorou de %d para %d' % (rel, m, a, b))
        ok = False
    for rel in new_files:
        if today[rel]['bytes'] > MAX_NEW_BYTES:
            print('RED  %s e novo e tem %d B > %d: extrair nao e despejar'
                  % (rel, today[rel]['bytes'], MAX_NEW_BYTES))
            ok = False
    print('piorem: %d metrica(s)' % len(worse))
    return ok


def neg_arm(today, baseline):
    mutants = []
    mutants.append(('M1 um ficheiro cresce 1 byte',
                    lambda: {k: dict(v) for k, v in today.items()}))
    # o mutante aplica-se DENTRO do ciclo para ficar visivel na comparacao
    caught = 0

    # UM MUTANTE SO' E' UM MUTANTE SE ATINGIR UM FICHEIRO QUE O BASELINE CONHECE.
    # MEDIDO 2026-10-30: `apply_except` escolhia o primeiro `.py` ALFABETICO que tivesse
    # a chave `except_pass` -- e as chaves existem em TODOS os ficheiros (a zero
    # incluido), logo podia calhar num ficheiro NOVO, que `compare` ignora por nao ter
    # baseline. O mutante ficava INERT e o braco negativo do passo dizia rc=2. Os tres
    # mutantes passam a escolher dentro do conjunto que o baseline conhece.
    known = [k for k in sorted(today) if k in (baseline or {})]

    def _pick(pred, metric):
        """O primeiro ficheiro do baseline para o qual `metric` esta' EM CIMA do baseline.

        A clausula `>=` nao e' estetica: MEDIDO 2026-11-01, `apply_except` escolhia o
        primeiro `.py` alfabetico com a chave e calhou em `app/webview/caption_overlay.py`,
        que tem 2 `except_pass` contra 4 no baseline -- a divida tinha sido PAGA, portanto
        `+1` continuava abaixo do tecto e o mutante ficava INERTE (o braco negativo
        publicava rc=2 sem que o comparador tivesse deixado de saber ver a divida).
        """
        for k in known:
            if pred(k, today[k]) and today[k].get(metric, 0) >= (baseline.get(k) or {}).get(metric, 0):
                return k
        raise SystemExit('NEG-ARM setup: nenhum ficheiro do baseline satisfaz o mutante %r'
                         % (metric,))

    def apply_grow(copy):
        rel = _pick(lambda k, v: True, 'bytes')
        copy[rel]['bytes'] += 1

    def apply_long_func(copy):
        rel = _pick(lambda k, v: k.endswith('.py') and 'max_func' in v, 'max_func')
        copy[rel]['max_func'] += 1

    def apply_except(copy):
        rel = _pick(lambda k, v: k.endswith('.py') and 'except_pass' in v, 'except_pass')
        copy[rel]['except_pass'] += 1

    for name, fn in (('M1 um ficheiro cresce 1 byte', apply_grow),
                     ('M2 a funcao mais longa cresce', apply_long_func),
                     ('M3 aparece um except-pass novo', apply_except)):
        copy = json.loads(json.dumps(today))
        fn(copy)
        worse = compare(copy, baseline)
        ok = not worse
        if not ok:
            print('NEG-ARM %-38s RED as expected (%s)'
                  % (name, worse[0][1]))
            caught += 1
        else:
            print('NEG-ARM %-38s ** INERT **' % name)
    # CONTROL: o comparador tem de saber dizer as DUAS coisas, na MESMA corrida.
    #
    # O controlo antigo era `not compare(today, baseline)`, ou seja, exigia a
    # ARVORE LIMPA para o braco negativo poder passar. Com divida antiga no
    # baseline (`sotto_webview.py`, `youtube_captions.py`, `youtube_window.py`,
    # `panel.js`, `worker/sotto_worker.py`, `caption-formulation.js` ja' acima
    # -- medido 2026-10-30) esse controlo ficava vermelho para sempre e o passo
    # `red-as-expected-code-health` publicava rc=2 em vez do rc=1 que a bateria
    # exige: o braco negativo deixava de medir se os MUTANTES sao apanhados e
    # passava a medir a divida, que ja' tem o seu proprio passo (`code-health`,
    # rc=2). O controlo certo e' o que prova que o comparador nao esta' mudo:
    # ele diz VERDE numa arvore cortada ao baseline e diz VERMELHO nessa mesma
    # arvore quando um numero cresce 1.
    clamped = {rel: {m: min(row.get(m, 0), (baseline.get(rel) or {}).get(m, 0))
                     for m in METRICS}
               for rel, row in today.items() if rel in baseline}
    clean = not compare(clamped, baseline)
    nudged = json.loads(json.dumps(clamped))
    if nudged:
        first = sorted(nudged)[0]
        nudged[first]['bytes'] += 1
    speaks_red = bool(compare(nudged, baseline))
    print('POS-ARM %-38s %s' % ('o comparador diz VERDE no baseline',
                                'PASS as expected' if clean else '** RED **'))
    print('POS-ARM %-38s %s' % ('e diz VERMELHO a +1 byte',
                                'PASS as expected' if speaks_red else '** MUDO **'))
    red_today = compare(today, baseline)
    print('INFO    %-38s %d metrica(s) acima do baseline (divida ja publicada '
          'pelo passo `code-health`)' % ('estado medido', len(red_today)))
    print('NEG-ARM %d of 3 mutant(s) caught' % caught)
    if caught == 3 and clean and speaks_red:
        print('NEG-ARM PASS')
        return 1
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--update', action='store_true',
                    help='regenera o baseline a partir do estado medido')
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    today = census()
    if args.update:
        with open(BASELINE, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump({'measured': '2026-10-23', 'metrics': list(METRICS),
                       'files': today}, fh, indent=2, ensure_ascii=False, sort_keys=True)
            fh.write('\n')
        print('baseline escrito: %d ficheiro(s)' % len(today))
        return 0
    try:
        with open(BASELINE, encoding='utf-8') as fh:
            baseline = json.load(fh).get('files') or {}
    except (OSError, ValueError) as exc:
        print('RED  sem baseline (%r): sem baseline nao ha ratchet' % (exc,))
        print('CODE-HEALTH VERDICT FAIL')
        return 2
    if args.neg_arm:
        return neg_arm(today, baseline)
    new_files = [r for r in today if r not in baseline]
    ok = verdict(today, baseline, compare(today, baseline), new_files)
    print('CODE-HEALTH VERDICT %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
