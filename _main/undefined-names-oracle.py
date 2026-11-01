"""Nomes USADOS e nunca definidos -- o que o compilador nao ve e o compilador deixa passar.

PORQUE EXISTE (medido 2026-11-01, duas vezes no mesmo dia, as duas em producao):

1. `worker/sotto_worker.py` morreu no arranque com
   `NameError: name 'REDUX_LIVE_DEFAULT' is not defined` DEPOIS de a extraccao para
   `worker/engine_switch.py` ter passado 39/39 comparacoes de AST e 23 ficheiros de
   `py_compile`. O nome e' usado em `argparse` (`default=REDUX_LIVE_DEFAULT`) e nao
   estava na lista de `from engine_switch import (...)`. `py_compile` aceita -- um
   `NameError` so' nasce no instante em que a linha corre, e essa linha corre no
   `main()` que arranca o worker. A app do dono ficou com
   `BRIDGE_DEATH rc=4 ... BRIDGE_EXIT ... captions=0` e ninguem transcrevia nada.
2. `app/webview/sotto_webview.py` usava `_window_is_ours` em dois sitios e a
   DEFINICAO desapareceu numa fusao de ramos (nenhum dos dois lados a tinha depois
   da resolucao). Compila perfeitamente; o `NameError` nasce no `ClickWatcher._poll`.

Nenhum dos dois portoes da casa os apanha: `py_compile` olha a sintaxe, e a bateria
corre oraculos que importam o modulo -- um import passa.

O QUE MEDE. Para cada `Name` em contexto de leitura, o nome esta' definido se for um
builtin, um import, uma variavel com `Store` em qualquer sitio do ficheiro, um
argumento, um `except ... as`, um `global`, ou um `def`/`class`. E' uma aproximacao
grosseira de escopo (um `Store` noutra funcao conta como definido) e isso e'
DELIBERADO: a direccao do erro e' "nao acusar", para que um verde aqui signifique
alguma coisa. Os dois defeitos reais de hoje foram ambos apanhados por ela.

USO
    python _main/undefined-names-oracle.py            # a populacao de producao
    python _main/undefined-names-oracle.py --neg-arm  # prova que o detector morde
"""
from __future__ import annotations

import argparse
import ast
import builtins
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

#: O conjunto e' o CODIGO DE PRODUCAO que corre no computador do dono. Ficheiros de
#: `_main/` ficam de fora de proposito: sao instrumentos, mudam a toda a hora, e um
#: vermelho la' nao e' um defeito do produto.
POPULATION = (
    'app/webview/sotto_webview.py',
    'app/webview/caption_overlay.py',
    'app/webview/overlay_paint.py',
    'app/webview/bridge_census.py',
    'app/webview/code_identity.py',
    'app/webview/panel_focus.py',
    'app/webview/selftest_instrument.py',
    'app/webview/win32_types.py',
    'app/webview/youtube_reveal.py',
    'app/webview/word_fade.py',
    'app/webview/load_shedding.py',
    'app/webview/hotkey_gesture.py',
    'app/webview/hotkey_settings.py',
    'app/webview/panel_state.py',
    'worker/sotto_worker.py',
    'worker/engine_switch.py',
    'worker/engine_policy.py',
    'worker/live_queue.py',
)

BUILTINS = set(dir(builtins)) | {
    '__name__', '__file__', '__doc__', '__package__', '__spec__', '__debug__'}


def defined_names(tree):
    """Todo nome que o ficheiro pode ter definido em QUALQUER escopo."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split('.')[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.Global):
            names.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            names.update(node.names)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and getattr(node, 'name', None):
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and getattr(node, 'rest', None):
            names.add(node.rest)
    return names


def undefined(path):
    """{nome: [linhas]} dos nomes usados e nunca definidos no ficheiro."""
    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        tree = ast.parse(handle.read(), path)
    known = defined_names(tree) | BUILTINS
    missing = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and node.id not in known):
            missing.setdefault(node.id, []).append(int(node.lineno))
    for lines in missing.values():
        lines.sort()
    return missing


def scan(population):
    """{path: {nome: [linhas]}} so' dos ficheiros que TÊM nomes indefinidos."""
    out = {}
    for rel in population:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            out[rel] = {'__MISSING_FILE__': [0]}
            continue
        found = undefined(path)
        if found:
            out[rel] = found
    return out


#: O NEGATIVO. Um ficheiro que usa um nome que ninguem definiu, com a forma exacta
#: do defeito de hoje (um nome vindo de um modulo que importa uma LISTA de nomes):
#: `base.py` define-o, `user.py` importa tres dos quatro e usa o quarto.
NEG_BASE = 'REDUX_LIVE_DEFAULT = False\nREDUX_OTHER = False\n'
NEG_USER = (
    'from base import REDUX_OTHER\n'
    '\n'
    'def main():\n'
    '    return REDUX_LIVE_DEFAULT, REDUX_OTHER\n'
)
#: E o par que TEM de passar: os DOIS nomes importados.
POS_USER = (
    'from base import REDUX_LIVE_DEFAULT, REDUX_OTHER\n'
    '\n'
    'def main():\n'
    '    return REDUX_LIVE_DEFAULT, REDUX_OTHER\n'
)


def neg_arm():
    """O detector tem de acusar `NEG_USER` e calar-se sobre `POS_USER`."""
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, 'base.py')
        with open(base, 'w', encoding='utf-8') as handle:
            handle.write(NEG_BASE)
        neg = os.path.join(tmp, 'user.py')
        with open(neg, 'w', encoding='utf-8') as handle:
            handle.write(NEG_USER)
        caught = undefined(neg)
        if 'REDUX_LIVE_DEFAULT' in caught:
            print('  RED  o nome nao importado e NAO usado -> acusado  %r'
                  % (caught,))
        else:
            print('  FALHA o detector nao viu o defeito de hoje')
            ok = False
        pos = os.path.join(tmp, 'ok.py')
        with open(pos, 'w', encoding='utf-8') as handle:
            handle.write(POS_USER)
        quiet = undefined(pos)
        if quiet:
            print('  FALHA o detector acusou um ficheiro correcto: %r' % (quiet,))
            ok = False
        else:
            print('  GREEN o par correcto passa sem uma linha')
    #: A CONVENCAO DA CASA: um braco negativo que provou o vermelho SAI `rc=1`
    #: (ver `code-health-oracle --neg-arm` e `call :expectred`, que exige 1 e
    #: procura "NEG-ARM PASS" no log). Um zero aqui seria lido como "o defeito
    #: nao foi reproduzido".
    print('NEG-ARM %s' % ('PASS -- o detector morde e o par correcto e mudo'
                          if ok else 'FAIL -- o detector ficou mudo'))
    return 1 if ok else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    bad = scan(POPULATION)
    if not bad:
        print('UNDEFINED-NAMES GREEN -- %d ficheiros de producao, 0 nomes usados '
              'e nunca definidos' % len(POPULATION))
        return 0
    for path, names in sorted(bad.items()):
        for name, lines in sorted(names.items()):
            print('RED  %s: %s usado em %s' % (path, name, lines[:8]))
    print('UNDEFINED-NAMES VERDICT FAIL -- %d ficheiro(s)' % len(bad))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
