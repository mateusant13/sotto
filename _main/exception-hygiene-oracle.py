#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# NO-BUG: ratchet de divida (40 `except: pass` em 11 ficheiros); desbloqueia higiene, nao um bug nomeado
"""EXCEPTION-HYGIENE ORACLE -- a divida de `except Exception: pass` nao cresce.

A LEI (consultgpt, `.cursor/rules/fix-on-sight.mdc`): *"Any error of any kind is
fixed on sight -- no workarounds, no silent fallbacks"*. Um `except Exception:
pass` sem razao escrita e o silencio mais barato que existe: o produto continua a
correr com uma perna partida e o log nao diz nada. Hoje sao **40** no codigo do
produto, em **11** ficheiros (medido 2026-10-23, `_main/exception-baseline.json`).

PORQUE UMA CATRACA E NAO UMA LIMPEZA: mudar 40 tipos de excepcao num turno e como
se parte um produto a serio -- cada `pass` pode ser um `OSError` de limpeza
legitimo ou um bug escondido, e a diferenca exige leitura, nao regex. A catraca
faz a coisa certa agora (**nao pode aumentar**) sem fingir que a leitura ja foi
feita.

AS TRES AFIRMACOES (AST, nunca substring -- um comentario que mencione
`except Exception: pass` nao pode contar como um):
  C1  nenhum ficheiro passa da sua linha de base (um ficheiro novo com um
      infractor falha, porque a linha de base dele e 0);
  C2  a linha de base nao mente: a soma dos numeros e igual ao medido, e todo o
      ficheiro citado existe (um baseline que se pode inflacionar em silencio
      esconde a divida em vez de a medir);
  C3  a ISENCAO e o COMENTARIO, e so ele: o mesmo constructo com uma `#` nas 3
      linhas acima nao conta -- e o braco C3 prova-o no sentido negativo (desligar
      a isencao faz o total subir).

A POPULACAO E DECLARADA, porque o AGENTS o exige: `app/webview/**`, `worker/**`,
`app/panel/**`, com `__pycache__`, `models`, `history`, `runs`, `_probe` fora, e
so ficheiros que NAO comecam por `_` (as copias mutantes e as sondas vivem la).
O que o instrumento NAO ve: ficheiros `.js` do painel, `_main/**`, e os
`except: pass` que nao estejam num `ExceptHandler` com o corpo exactamente
`pass` (um `pass` seguido de outra linha conta como tratado).

    python _main/exception-hygiene-oracle.py            # rc=0 verde, rc=2 vermelho
    python _main/exception-hygiene-oracle.py --neg-arm  # rc=1 POR DESENHO

Nao lanca nada, nao escreve no produto (so um ficheiro `excneg_probe.py`
temporario, apagado no `finally`), nao abre janela. Pode entrar na bateria.
"""
import argparse
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASELINE = os.path.join(HERE, 'exception-baseline.json')
PRODUCT_DIRS = ('app/webview', 'worker', 'app/panel')
SKIP_DIRS = {'__pycache__', 'models', 'history', 'runs', '_probe'}
BROAD = {'Exception', 'BaseException'}
NEG_NAME = 'excneg_probe.py'


def product_files(repo=REPO):
    """A populacao declarada, por ordem, para o relatorio ser estavel."""
    out = []
    for rel in PRODUCT_DIRS:
        root = os.path.join(repo, *rel.split('/'))
        for dirpath, dirnames, files in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(files):
                if name.endswith('.py') and not name.startswith('_'):
                    out.append(os.path.join(dirpath, name))
    return out


def _rel(path, repo=REPO):
    return os.path.relpath(path, repo).replace('\\', '/')


def offenders(path, exempt=True):
    """As linhas dos `except [Exception|bare]: pass` sem razao escrita."""
    with open(path, encoding='utf-8', errors='replace') as fh:
        src = fh.read()
    lines = src.replace('\r\n', '\n').split('\n')
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []                      # um ficheiro ilegal e outro portao
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if not (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
            continue
        if exempt and '#' in '\n'.join(lines[max(0, node.lineno - 3):node.lineno]):
            continue                   # a razao escrita isenta
        kind = node.type
        broad = kind is None or (isinstance(kind, ast.Name) and kind.id in BROAD)
        if broad:
            found.append(node.lineno)
    return found


def measure(repo=REPO, exempt=True):
    """{ficheiro: contagem} do medido AGORA."""
    out = {}
    for path in product_files(repo):
        n = len(offenders(path, exempt=exempt))
        if n:
            out[_rel(path, repo)] = n
    return out


def check(baseline, measured, files_now):
    """As tres afirmacoes. Devolve [(id, ok, got)]."""
    results = []

    # C1 -- ninguem cresce, e um ficheiro novo com infractor e um crescimento.
    grew = {f: (n, baseline.get(f, 0)) for f, n in measured.items()
            if n > baseline.get(f, 0)}
    results.append(('C1 nenhum ficheiro passa da linha de base', not grew,
                    {f: {'now': a, 'baseline': b} for f, (a, b) in grew.items()}))

    # C2 -- a linha de base nao mente (soma igual) e nao cita ficheiros mortos.
    total_measured = sum(measured.values())
    total_baseline = sum(baseline.values())
    missing = sorted(f for f in baseline if f not in files_now)
    ok_c2 = (total_measured == total_baseline) and not missing
    results.append(('C2 a linha de base e igual ao medido', ok_c2,
                    {'measured': total_measured, 'baseline': total_baseline,
                     'files_gone': missing}))

    # C3 -- a isencao do comentario esta VIVA (desligada, o total sobe).
    if total_baseline:
        without = sum(measure(exempt=False).values())
        ok_c3 = without > total_measured
        results.append(('C3 a isencao e o comentario, e so ele', ok_c3,
                        {'with_comment': total_measured, 'without': without}))
    else:
        results.append(('C3 a isencao e o comentario, e so ele', False,
                        'a linha de base esta vazia: a isencao nao e testavel'))
    return results


def load_baseline(path=BASELINE):
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    return {k: int(v) for k, v in data.items()}


def _probe_path(repo=REPO):
    return os.path.join(repo, 'app', 'webview', NEG_NAME)


def _write_probe(repo=REPO):
    path = _probe_path(repo)
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write('def probe():\n'
                 '    try:\n'
                 '        return 1\n'
                 '    except Exception:\n'
                 '        pass\n')
    return path


def run_neg_arm():
    """Os mutantes. Cada um TEM de deixar o portao VERMELHO."""
    baseline = load_baseline()
    files_now = {_rel(p) for p in product_files()}
    caught = 0

    mutants = []

    # M1 -- um ficheiro NOVO com um infractor silencioso.
    def m1():
        path = _write_probe()
        try:
            measured = measure()
            return check(baseline, measured, files_now | {_rel(path)})
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
    mutants.append(('M1 um ficheiro novo com `except Exception: pass`', m1))

    # M2 -- a linha de base e baixada: o medido passa a ser maior.
    def m2():
        victim = next(iter(sorted(baseline)))
        low = dict(baseline)
        low[victim] = 0
        return check(low, measure(), files_now)
    mutants.append(('M2 a linha de base e baixada em silencio', m2))

    # M3 -- a linha de base e inflacionada: a soma deixa de bater.
    def m3():
        up = dict(baseline)
        up[next(iter(sorted(up)))] += 1
        return check(up, measure(), files_now)
    mutants.append(('M3 a linha de base e inflacionada em silencio', m3))

    # M4 -- a linha de base cita um ficheiro que ja nao existe.
    def m4():
        ghost = dict(baseline)
        ghost['app/webview/ficheiro-que-nao-existe.py'] = 1
        return check(ghost, measure(), files_now)
    mutants.append(('M4 a linha de base cita um ficheiro morto', m4))

    for name, fn in mutants:
        try:
            results = fn()
            bad = [r for r in results if not r[1]]
        except Exception as exc:  # noqa: BLE001 -- ilegal tambem e apanhado
            bad = [('import', False, repr(exc))]
        if bad:
            print('NEG-ARM %-52s RED as expected' % name)
            caught += 1
        else:
            print('NEG-ARM %-52s ** INERT **' % name)

    print('NEG-ARM %d of %d mutant(s) caught' % (caught, len(mutants)))
    if caught == len(mutants):
        print('NEG-ARM PASS')
        return 1                       # rc=1 POR DESENHO: o defeito foi encontrado
    print('VERDICT: FAIL -- %d mutant(s) inertes' % (len(mutants) - caught))
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true',
                    help='corre os controlos: os mutantes tem de ficar VERMELHOS')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    if args.neg_arm:
        try:
            return run_neg_arm()
        finally:
            try:
                os.remove(_probe_path())
            except OSError:
                pass

    baseline = load_baseline()
    files = product_files()
    files_now = {_rel(p) for p in files}
    measured = measure()
    print('populacao: %d ficheiro(s) .py em %s (fora: %s, ficheiros com _)'
          % (len(files), ', '.join(PRODUCT_DIRS), ', '.join(sorted(SKIP_DIRS))))
    print('medido: %d infractor(es) em %d ficheiro(s)'
          % (sum(measured.values()), len(measured)))
    failures = []
    for claim, ok, got in check(baseline, measured, files_now):
        print('%s %s' % ('GREEN' if ok else 'RED  ', claim))
        if not ok:
            print('      got=%r' % (got,))
            failures.append(claim)
    # O relatorio diz o que ENCOLHEU, para o baseline poder descer sem drama.
    shrank = {f: (measured[f], baseline[f]) for f in measured
              if measured[f] < baseline.get(f, 0)}
    if shrank:
        print('nota: a divida ENCOLHEU em %s -- baixar a linha de base no '
              'mesmo commit' % ', '.join(sorted(shrank)))
    if failures:
        print('EXCEPTION-HYGIENE VERDICT FAIL (%d)' % len(failures))
        return 2
    print('EXCEPTION-HYGIENE VERDICT PASS -- a divida de `except Exception: '
          'pass` nao cresce (medida: %d)' % sum(measured.values()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
