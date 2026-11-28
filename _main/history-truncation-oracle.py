#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NO-BUG: the transcript feed, search and export truncated silently at 400/200/400 rows -- no page cursor, no "there is more"; the panel showed part of a session as if it were all of it
"""A PAGINA QUE NAO DIZ QUE HA' MAIS E' A TRUNCAGEM SILENCIOSA (medido 2026-11-28).

O DEFEITO QUE ESTE ORACULO GUARDA. `app/panel/history-store.js` cortava em
`tail(400)`, `search(200)` e `exportBody(400)` com um `break` seco; o twin Python
(`SottoShell.history_tail/_search/_export`) fazia o mesmo. O painel pedia 400,
guardava no maximo 500 e nao tinha como pedir a pagina anterior -- logo o
historico dele acabava a meio da sessao e NADA dizia que havia mais (o dono,
verbatim, 2026-11-05: *"o painel da direita fica perdendo historico"*).

A CURA, e as quatro coisas que ela tem de provar:

  1. `tail(limit)` devolve `truncated` -- medido lendo UMA entrada a mais -- e
     `cursor`, a linha mais antiga devolvida.
  2. `tail(limit, cursor)` devolve a pagina SEGUINTE, estritamente mais antiga,
     sem repetir nenhuma linha da anterior.
  3. `search(limit)` e `exportBody(limit)` dizem `truncated` quando um resultado
     real ficou de fora.
  4. OS DOIS TWINS CONCORDAM: o mesmo fixture tem de dar as MESMAS linhas, o
     MESMO `truncated` e o MESMO cursor no Node e no Python.

O fixture e' um root temporario com sete linhas em dois ficheiros de hora, escrito
no formato do store (`- [HH:MM:SS] texto`). Nada aqui toca `H:/sotto/history`.

PORTEIRO `--neg-arm`: apaga o `truncated` das duas caudas (o codigo de ANTES, com
o corte seco) e exige que o braco do `tail` fique VERMELHO.

rc: 0 PASS, 1 FAIL (a truncagem continua muda, ou o mutante nao morre), 3 CANNOT-MEASURE.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, "app", "webview", "sotto_webview.py")
STORE = os.path.join(REPO, "app", "panel", "history-store.js")

_NO_WINDOW = dict(creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                  startupinfo=subprocess.STARTUPINFO(
                      dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))

#: Sete linhas, duas horas, um so' dia: duas paginas de tres e uma de uma.
FIXTURE = (
    ('2026-11-28', '09', [
        ('09:00:01', 'linha 01'),
        ('09:10:02', 'linha 02'),
        ('09:20:03', 'linha 03'),
        ('09:30:04', 'linha 04'),
    ]),
    ('2026-11-28', '10', [
        ('10:00:05', 'linha 05'),
        ('10:10:06', 'linha 06'),
        ('10:20:07', 'linha 07'),
    ]),
)

JS_ARMS = r"""
const m = require(process.argv[1]);
const out = {};
const p1 = m.tail(3);
out.p1 = {n: p1.entries.length, times: p1.entries.map((e) => e.time),
          truncated: p1.truncated, cursor: p1.cursor};
const p2 = m.tail(3, p1.cursor);
out.p2 = {n: p2.entries.length, times: p2.entries.map((e) => e.time),
          truncated: p2.truncated, cursor: p2.cursor};
const p3 = m.tail(3, p2.cursor);
out.p3 = {n: p3.entries.length, times: p3.entries.map((e) => e.time),
          truncated: p3.truncated, cursor: p3.cursor};
const ex = m.export('txt', 3);
out.export_small = {n: ex.entries, truncated: ex.truncated};
const ex2 = m.export('txt', 50);
out.export_all = {n: ex2.entries, truncated: ex2.truncated};
const s1 = m.search('linha', 2);
out.search_small = {n: s1.hits.length, truncated: s1.truncated};
const s2 = m.search('linha', 50);
out.search_all = {n: s2.hits.length, truncated: s2.truncated};
process.stdout.write(JSON.stringify(out));
"""


def write_fixture(root):
    for date, hour, rows in FIXTURE:
        folder = os.path.join(root, date)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, hour + '.md'), 'w', encoding='utf-8', newline='\n') as fh:
            for at, text in rows:
                fh.write('- [%s] %s\n' % (at, text))


def run_node(store_path, root):
    env = dict(os.environ)
    env['SOTTO_HISTORY_ROOT'] = root
    proc = subprocess.run(['node', '-e', JS_ARMS, store_path],
                          capture_output=True, text=True, timeout=120, env=env,
                          **_NO_WINDOW)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or 'node failed').strip()[:400]
    return json.loads(proc.stdout), None


def _python_shell(mod):
    """O OBJECTO MINIMO QUE O CODIGO REAL EXIGE -- nada e' reimplementado aqui.

    `history_tail` / `history_search` chamam so' `_history_entries`, que por sua
    vez chama `_history_files` e `_history_read`; os tres sao sem estado de shell
    (nenhum `self.<atributo>`), logo ligar os METODOS REAIS a um `SimpleNamespace`
    exercita as funcoes do produto, nao uma copia delas.
    """
    holder = types.SimpleNamespace()
    for name in ('_history_entries', '_history_files', '_history_read'):
        setattr(holder, name, types.MethodType(getattr(mod.SottoShell, name), holder))
    return holder


def python_arms(mod, root):
    shell = _python_shell(mod)
    out = {}
    p1 = mod.SottoShell.history_tail(shell, 3)
    out['p1'] = {'n': len(p1['entries']), 'times': [e['time'] for e in p1['entries']],
                 'truncated': p1.get('truncated'), 'cursor': p1.get('cursor')}
    p2 = mod.SottoShell.history_tail(shell, 3, p1.get('cursor'))
    out['p2'] = {'n': len(p2['entries']), 'times': [e['time'] for e in p2['entries']],
                 'truncated': p2.get('truncated'), 'cursor': p2.get('cursor')}
    p3 = mod.SottoShell.history_tail(shell, 3, p2.get('cursor'))
    out['p3'] = {'n': len(p3['entries']), 'times': [e['time'] for e in p3['entries']],
                 'truncated': p3.get('truncated'), 'cursor': p3.get('cursor')}
    ex = mod.SottoShell.history_export(shell, 'txt', 3)
    out['export_small'] = {'n': ex['entries'], 'truncated': ex.get('truncated')}
    ex2 = mod.SottoShell.history_export(shell, 'txt', 50)
    out['export_all'] = {'n': ex2['entries'], 'truncated': ex2.get('truncated')}
    s1 = mod.SottoShell.history_search(shell, 'linha', 2)
    out['search_small'] = {'n': len(s1['hits']), 'truncated': s1.get('truncated')}
    s2 = mod.SottoShell.history_search(shell, 'linha', 50)
    out['search_all'] = {'n': len(s2['hits']), 'truncated': s2.get('truncated')}
    return out


def load_module(path, tag='trunc'):
    import importlib.util
    sys.path.insert(0, os.path.join(REPO, 'app', 'webview'))
    spec = importlib.util.spec_from_file_location('sw_%s_%d' % (tag, os.getpid()), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def judge(js, py):
    """Cada afirmacao e' um braco com nome; a comparacao Node x Python e' outro."""
    fails = []

    def check(name, cond, detail):
        if not cond:
            fails.append('%s: %s' % (name, detail))
        print('%s %s%s' % ('[PASS]' if cond else '[FAIL]', name,
                           '' if cond else ' -- ' + detail))

    if js is None or py is None:
        check('os dois twins correram', False, 'js=%r py=%r' % (js, py))
        return fails
    for side, data in (('node', js), ('python', py)):
        check('%s: primeira pagina sao as 3 mais recentes' % side,
              data['p1']['times'] == ['10:00:05', '10:10:06', '10:20:07'],
              repr(data['p1']))
        check('%s: ha mais depois da primeira pagina' % side,
              data['p1'].get('truncated') is True, repr(data['p1']))
        check('%s: segunda pagina continua sem repetir' % side,
              data['p2']['times'] == ['09:10:02', '09:20:03', '09:30:04']
              and data['p2'].get('truncated') is True, repr(data['p2']))
        check('%s: ultima pagina acaba em silencio honesto' % side,
              data['p3']['times'] == ['09:00:01'] and data['p3'].get('truncated') is False,
              repr(data['p3']))
        check('%s: exporte parcial diz que e parcial' % side,
              data['export_small']['n'] == 3 and data['export_small'].get('truncated') is True,
              repr(data['export_small']))
        check('%s: exporte completo nao inventa truncagem' % side,
              data['export_all']['n'] == 7 and data['export_all'].get('truncated') is False,
              repr(data['export_all']))
        check('%s: busca cortada diz que cortou' % side,
              data['search_small']['n'] == 2 and data['search_small'].get('truncated') is True,
              repr(data['search_small']))
        check('%s: busca completa nao inventa truncagem' % side,
              data['search_all']['n'] == 7 and data['search_all'].get('truncated') is False,
              repr(data['search_all']))
    # A PROSA NAO SE COMPARA: `_history_entries` do Python acrescenta a marca
    # terminal (`.` apos pausa/prosa) por desenho, logo o contrato destes bracos
    # e' a ORDEM (`time`), o `truncated` e o cursor -- o que a truncagem mudou.
    check('os dois twins concordam (ordem, truncated, cursor)',
          js['p1'] == py['p1'] and js['p2'] == py['p2'] and js['p3'] == py['p3'],
          'js=%r\npython=%r' % (js, py))
    check('os dois twins concordam na busca e no exporte',
          js['search_small'] == py['search_small']
          and js['search_all'] == py['search_all']
          and js['export_small'] == py['export_small']
          and js['export_all'] == py['export_all'], 'divergencia')
    return fails


def mutate_js(src):
    """O `tail` de ANTES: corta no limite e nao devolve `truncated` nem cursor."""
    start = src.index('function tail(limit = 400, before = null) {')
    end = src.index('\n}\n', start) + 3
    return src[:start] + (
        'function tail(limit = 400, before = null) {\n'
        '  const want = Math.max(1, Number(limit) || 400);\n'
        '  const out = [];\n'
        '  for (const entry of entries(before)) {\n'
        '    out.push(entry);\n'
        '    if (out.length >= want) break;\n'
        '  }\n'
        '  out.reverse();\n'
        '  return { entries: out, root: ROOT };\n'
        '}\n') + src[end:]


def mutate_py(src):
    """O `history_tail` de ANTES: corta no limite e nao devolve `truncated` nem cursor."""
    head = '    def history_tail(self, limit=400, before=None):'
    start = src.index(head)
    end = src.index('\n    def ', start + len(head)) + 1
    before_fix = (
        head + '\n'
        '        limit = max(1, int(limit))\n'
        '        entries = []\n'
        '        for entry in self._history_entries():\n'
        '            entries.append(entry)\n'
        '            if len(entries) >= limit:\n'
        '                break\n'
        '        entries.reverse()  # back to oldest-first for the feed\n'
        "        return {'entries': entries, 'root': HISTORY_ROOT}\n"
        '\n')
    return src[:start] + before_fix + src[end:]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)

    tmp = tempfile.mkdtemp(prefix='hist-trunc-')
    try:
        write_fixture(tmp)
        os.environ['SOTTO_HISTORY_ROOT'] = tmp
        if args.neg_arm:
            js_src = open(STORE, 'rb').read().decode('utf-8')
            py_src = open(SHELL, 'rb').read().decode('utf-8').replace('\r\n', '\n')
            js_path = os.path.join(tmp, 'store_mutant.js')
            py_path = os.path.join(tmp, 'shell_mutant.py')
            with open(js_path, 'w', encoding='utf-8', newline='\n') as fh:
                # O mutante vive no TEMP: o require relativo do store tem de virar
                # ABSOLUTO, senao o node nao o carrega e o braco mediria um ENOENT
                # em vez da regra (um mutante que morre por sintaxe nao prova nada).
                fh.write(mutate_js(js_src).replace(
                    "require('./history-context-store')",
                    'require(' + json.dumps(os.path.join(REPO, 'app', 'panel',
                                                         'history-context-store.js')) + ')'))
            with open(py_path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(mutate_py(py_src))
            js, jerr = run_node(js_path, tmp)
            mod = load_module(py_path, 'mut')
            try:
                py = python_arms(mod, tmp)
            except Exception as exc:  # noqa: BLE001 -- um mutante que explode tambem morre
                py = None
                print('  mutante python levantou %r' % (exc,))
            fails = judge(js, py)
            if jerr:
                print('  node: %s' % jerr)
            if fails:
                print('NEG-ARM PASS: sem `truncated`/cursor a pagina mente (%d falhas)'
                      % len(fails))
                return 1
            print('VERDICT: FAIL -- o mutante passou; o oraculo nao julga a truncagem')
            return 1

        js, jerr = run_node(STORE, tmp)
        if jerr:
            print('CANNOT-MEASURE why=node %s' % jerr)
            return 3
        mod = load_module(SHELL, 'live')
        py = python_arms(mod, tmp)
        fails = judge(js, py)
        print('VERDICT: %s -- %s' % ('PASS' if not fails else 'FAIL',
                                     '%d falha(s)' % len(fails) if fails else 'sem falhas'))
        return 0 if not fails else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
