#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""UM ROTULO NAO SOBREVIVE A' FOTO QUE O PRODUZIU -- o portao (2026-11-26).

O DEFEITO, medido no log do dono (pid 57008, sessao em que ele disse "subtitles
from youtube worked for like 2 seconds and then froze"):

    YOUTUBE_TICK_MS avg=367 max=8828 n=... cdp_age_ms=8265 rows=2 why='painted'

`why` e' escrito pelo ultimo ramo que devolveu uma foto e fica STICKY; `rows`
era lido com `max_age=8.0`, cinco vezes o limite dos caminhos que PINTAM
(1,2-1,5 s). Resultado: a linha do log afirmava "a pintar, 2 linhas" descrevendo
uma foto de 8 s que o caminho de pintura tinha recusado -- o mesmo tipo de
mentira que a `rows=0 why='painted'` de 2026-11-05, e a que mandou uma
investigacao inteira para o sitio errado.

O QUE ESTE ORACULO JULGA, sobre o metodo REAL (`_yt_diag_now` +
`_yt_cdp_row_count` extraidos do `sotto_webview.py` vivo, nunca uma copia):

  a-fresco      foto de 0,2 s com 2 linhas -> rows=2, why='painted' (o caso bom
                nao muda: um portao que so sabe acusar e' um portao cego);
  b-velho       foto de 8 s com 2 linhas -> rows=0, why='painted-stale';
  c-sem-foto    nenhuma foto -> rows=0, why='painted-stale';
  d-vazio       foto fresca sem linhas, rotulo do player -> rotulo intacto.

`--neg-arm`: remove o rebaixamento numa COPIA do shell e exige b/c a VERMELHO.
"""
import ast
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WEBVIEW = os.path.dirname(SHELL)

METHODS = ('_yt_cdp_row_count', '_yt_diag_now')


def read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def extract(src, name):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return ast.get_source_segment(src, node)
    raise SystemExit('metodo ausente no shell: %s' % name)


def build(shell_src):
    """As duas funcoes REAIS, ligadas por um `self` falso."""
    ns = {'time': time}
    for name in METHODS:
        exec(compile(ast.parse(extract(shell_src, name)), '<%s>' % name, 'exec'), ns)
    return ns


class FakeSource:
    def __init__(self, snap, age_s):
        self._snap, self._age = snap, age_s

    def snapshot(self, max_age=0.6):
        return self._snap if (self._age is not None and self._age <= max_age) else None

    def snapshot_age(self):
        return self._age


def call(ns, src, diag, extra_rows=None):
    me = SimpleNamespace(_yt_cdp_source=src, _yt_diag=diag, yt_video_id='vid1',
                         DOM_FRESH_S=1.2,
                         yt_cdp_rows=None if extra_rows is None else extra_rows)
    me._yt_cdp_row_count = lambda max_age=1.2: ns['_yt_cdp_row_count'](
        me, max_age=max_age)
    return ns['_yt_diag_now'](me)


def arm_rows(ns):
    snap2 = {'rows': [{'t': 1.0, 'text': 'a'}, {'t': 2.0, 'text': 'b'}],
             'why': 'painted', 't': 2.0, 'stamp': time.monotonic()}
    cases = [
        ('a-fresco', FakeSource(snap2, 0.2), {'why': 'painted'}, (2, 'painted')),
        ('b-velho', FakeSource(snap2, 8.0), {'why': 'painted'}, (0, 'painted-stale')),
        ('c-sem-foto', FakeSource(None, None), {'why': 'painted'}, (0, 'painted-stale')),
        ('d-vazio', FakeSource({'rows': [], 'why': 'no-painted-caption',
                                'stamp': time.monotonic()}, 0.2),
         {'why': 'no-painted-caption'}, (0, 'no-painted-caption')),
    ]
    out = []
    for name, src, diag, want in cases:
        _src, _vid, _age, rows, why = call(ns, src, diag)
        ok = (rows, why) == want
        out.append((name, ok, 'rows=%s why=%r want=%r' % (rows, why, want)))
    return out


def neg_arm(shell_src):
    tmp = tempfile.mkdtemp(prefix='yt-diag-neg-')
    try:
        bad = shell_src.replace("        if why == 'painted' and rows == 0:\n"
                                "            why = 'painted-stale'\n",
                                "        if False:\n"
                                "            why = 'painted-stale'\n")
        if bad == shell_src:
            print('NEG-ARM a-rotulo ARM-MISSING (o bloco mudou de forma)')
            return False
        p = os.path.join(tmp, 'shell_m1.py')
        with open(p, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(bad)
        ns = build(bad)
        rows = arm_rows(ns)
        caught = all(ok for _, ok, _ in rows[1:3]) is False
        print('NEG-ARM a-rotulo %s (%s)'
              % ('CAUGHT' if caught else 'NOT-CAUGHT',
                 ', '.join('%s:%s' % (n, 'ok' if ok else 'red')
                           for n, ok, _ in rows)))
        return caught
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    shell_src = read(SHELL)
    if 'if why == \'painted\' and rows == 0:' not in shell_src:
        print('[FAIL] a-rotulo o rebaixamento sumiu do shell')
        return 1
    ns = build(shell_src)
    rows = arm_rows(ns)
    bad = 0
    for name, ok, detail in rows:
        print('[%s] %-10s %s' % ('PASS' if ok else 'FAIL', name, detail))
        if not ok:
            bad += 1
    if '--neg-arm' in argv:
        ok = neg_arm(shell_src)
        print('NEG-ARM VERDICT: %s' % ('PASS' if ok else 'FAIL'))
        # A CONVENCAO DA CASA: mutante apanhado = rc 1 (`red-as-expected`).
        # Um neg-arm que sai 0 e' indistinguivel de um oraculo que nao julga.
        return 1 if ok else 0
    print('YT-DIAG-TRUTH VERDICT: %s (%d/%d)'
          % ('GREEN' if not bad else 'RED', len(rows) - bad, len(rows)))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
