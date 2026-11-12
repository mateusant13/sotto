#!/usr/bin/env python
# NO-BUG: mutant-tracking -- os mutantes CONGELADOS que oraculos executam tem de estar no indice.
"""mutant-tracking -- o fecho do D-01 do ledger da especificacao.

O DEFEITO MEDIDO (2026-11-11, `docs/spec/10-DEFECTS.md` §D-01). Dois ficheiros existiam so' na
arvore de trabalho -- `.gitignore:128` listava `worker/_sotto_worker_agcinert.py` e `worker/runs/`
excluia `_verdict-order-mutant.py` -- e dois oraculos os EXECUTAM:

    _main/agc_order_live.py:37        MUTANT = ... worker/_sotto_worker_agcinert.py
    _main/verdict-order-oracle.py:71  MUTANT = ... worker/runs/_verdict-order-mutant.py

Num clone limpo esses dois instrumentos nao correm, e um instrumento que so' existe na maquina onde
nasceu nao e' um instrumento. O `git add -f` fechou o caso UMA vez; nada impedia que um
`git rm --cached` o reabrisse -- e a propria licao da casa diz que um caso fechado por trabalho
manual volta. Este portao e' essa linha que faltava.

O QUE ELE EXIGE, e as tres de uma vez:

  1. `git ls-files --error-unmatch <caminho>` responde para cada mutante congelado (esta' no indice);
  2. o `.gitattributes` prega cada um a `text eol=crlf`, que e' o EOL medido desses ficheiros;
  3. o leitor sabe RECUSAR: um caminho que nao esta' no indice e um `.gitattributes` sem a linha
     reprovam pelo mesmo codigo. Sem esta metade, um `ls-files` mal chamado imprime "0 achados"
     sobre uma arvore vazia -- a classe que esta casa ja' pagou varias vezes.

Uso:
    python _main/mutant-tracking-oracle.py           -> 0 verde, 1 RED
    python _main/mutant-tracking-oracle.py --neg-arm -> muta o DADO (nunca o ficheiro) e exige o RED
"""
from __future__ import annotations

import fnmatch
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

#: Os mutantes congelados que algum oraculo EXECUTA. Nomear aqui e' dizer "isto e' produto de
#: teste, vive no indice e tem EOL preso". Um nome novo entra com o oraculo que o executa ao lado.
MUTANTS = [
    ('worker/_prefix_audioflag.py', '_main/agc_order_live.py'),
    ('worker/_sotto_worker_agcinert.py', '_main/agc_order_live.py'),
    ('worker/runs/_verdict-order-mutant.py', '_main/verdict-order-oracle.py'),
]


def _git(args):
    """Corre o git SEM janela (`CREATE_NO_WINDOW`), que e' a lei desta casa para todo o filho."""
    flags = 0x08000000 if os.name == 'nt' else 0
    si = None
    if os.name == 'nt':
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
    out = subprocess.run(['git'] + args, cwd=ROOT, capture_output=True, text=True,
                         creationflags=flags, startupinfo=si)
    return out.returncode, (out.stdout or '') + (out.stderr or '')


def tracked(path):
    rc, out = _git(['ls-files', '--error-unmatch', path])
    return rc == 0, out.strip()


def attrs_text():
    p = os.path.join(ROOT, '.gitattributes')
    return io.open(p, encoding='utf-8', errors='replace').read()


def attrs_line(text, path):
    """A linha que prega `path` a crlf, ou None.

    O `.gitattributes` DESTE repo usa PADROES, nao so' caminhos literais: `worker/runs/*.py` e'
    uma linha, e o mutante do `verdict-order` e' coberto por ela. MEDIDO 2026-11-12: a primeira
    versao deste leitor comparava `parts[0] == path` e acusou um sitio CORRECTO -- o mutante estava
    preso, por glob. Um portao que acusa quem esta' certo perde a autoridade, e o braco N5 existe
    para que essa versao nao volte.
    """
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and 'eol=crlf' in parts[1:] and fnmatch.fnmatch(path, parts[0]):
            return line
    return None


def evaluate(names, tracked_fn, attrs):
    """(falhas, detalhes) -- PURA sobre os dois leitores, para o braco poder negar o dado."""
    fails, notes = [], []
    for path, consumer in names:
        ok, said = tracked_fn(path)
        if not ok:
            fails.append('%s NAO esta no indice (o oraculo %s o executa)' % (path, consumer))
        line = attrs_line(attrs, path)
        if line is None:
            fails.append('%s sem `text eol=crlf` no .gitattributes' % path)
        notes.append((path, ok, bool(line)))
    return fails, notes


def neg_arms():
    """Duas negacoes do DADO, as duas com o MESMO `evaluate` que publica o veredicto."""
    arms = []
    names = [('worker/_sotto_worker_agcinert.py', '_main/agc_order_live.py')]
    real_attrs = attrs_text()

    def arm(name, ok, detail):
        arms.append({'arm': name, 'ok': bool(ok), 'detail': detail})

    fails, _ = evaluate(names, lambda p: (False, ''), real_attrs)
    arm('N1 caminho fora do indice reprova', any('indice' in f for f in fails),
        '%d falha(s)' % len(fails))
    fails, _ = evaluate(names, lambda p: (True, p), '# nada aqui\n')
    arm('N2 .gitattributes sem a linha reprova', any('eol=crlf' in f for f in fails),
        '%d falha(s)' % len(fails))
    ok_path, _ = tracked('worker/sotto_worker.py')
    arm('N3 o positivo de controlo: um ficheiro que ESTA no indice passa o leitor',
        ok_path, 'tracked(worker/sotto_worker.py)=%s' % ok_path)
    fails, _ = evaluate(names, lambda p: (True, p), real_attrs)
    arm('N4 o dado verdadeiro NAO reprova (a recusa nao e incondicional)',
        not fails, '%d falha(s)' % len(fails))
    globbed = [('worker/runs/x.py', 'controlo')]
    fails, _ = evaluate(globbed, lambda p: (True, p), 'worker/runs/*.py    text eol=crlf\n')
    arm('N5 um PADRAO do .gitattributes conta como pino (o repo usa globs)',
        not fails, '%d falha(s)' % len(fails))
    return arms


def main(argv):
    names = MUTANTS
    arms = []
    if '--neg-arm' in argv:
        arms = neg_arms()
        bad = [a for a in arms if not a['ok']]
        for a in arms:
            print('  ARM %s %s -- %s' % ('ok  ' if a['ok'] else 'RED ', a['arm'], a['detail']))
        print('NEG-ARM: %s -- %d/%d mutacoes do DADO apanhadas'
              % ('PASS' if not bad else 'FAIL', len(arms) - len(bad), len(arms)))
        return 1 if not bad else 0

    attrs = attrs_text()
    fails, notes = evaluate(names, tracked, attrs)
    for path, ok, pinned in notes:
        print('  %-44s tracked=%-5s eol=crlf=%s' % (path, ok, pinned))
    for f in fails:
        print('  RED', f)
    print('MUTANT-TRACKING %s -- %d mutante(s), %d falha(s)'
          % ('GREEN' if not fails else 'RED', len(names), len(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
