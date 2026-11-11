#!/usr/bin/env python
# NO-BUG: executa `on_external_captions_released` sobre uma shell FALSA; nao prova o release na sessao viva do dono nem o estado em disco dela.
"""O RELEASE DO PLAYER NAO PODE SER GASTO POR UM `return` -- o latch do parque.

O DEFEITO QUE ESTE ORACULO MEDE (2026-11-10). `on_external_captions_released`
consumia `_external_parked` e, nas duas linhas seguintes, `self._paused` ou
`not (self.visible or self._caption_window_shown)` faziam `return False` -- e o
`set_engine_park(None)` que vem DEPOIS nunca corria. Como o release e' de BORDA
(o watcher do player avisa uma vez), a chamada seguinte morria no
`if not self._external_parked: return False`.

MEDIDO no estado em disco da sessao do dono (2026-11-09, 21:36:12): o ficheiro
ainda dizia `"park": "captions"` com `"visible": false`, reimpresso a cada 3 s,
`staleAfterSeconds=9.0` nunca a expirar; e em 187 339 linhas de log havia
**1** `EXTERNAL_CAPTIONS_ENGINE_RESUMED` contra **16** `ENGINE_PARK reason=`.
O motor ficava largado para sempre -- e as palavras dele foram *"a legenda
congela e nunca volta"* / *"o audio volta e nada acontece"*.

O QUE O ORACULO EXECUTA: a funcao REAL, extraida por `ast` do ficheiro que
embarca, sobre um shell FALSO. Nada de reimplementar a decisao numa copia: um
oraculo que reescreve o que julga mede a copia.

ARMAS
  A1 release com o painel ESCONDIDO e o overlay escondido -> o parque e' limpo.
     (E' o braco que morre em HEAD, e e' o caso do dono.)
  A2 release com `_paused` -> o parque e' limpo (regra 3: desligar o display nao
     desliga o modelo).
  A3 sem parque pendente -> `False`, ZERO escritas.
  A4 parque de VRAM nao e' libertado por um release de legendas (o campo e'
     partilhado: so' o motivo `captions` sai daqui).
  A5 shell a sair -> `False`, ZERO escritas, latch INTACTO, e a linha
     `EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting`.
  A6 o espelho da pausa e' limpo em TODOS os caminhos (o portao de ecra ficaria
     de pe' e bloquearia a fonte seguinte).
  A7 a linha de sucesso nomeia o estado que a decidiu (`paused=` e `visible=`).

NEGATIVO: as duas guardas sao repostas NA FUNCAO EXTRAIDA (mutacao cirurgica do
mecanismo, nunca "o ficheiro de HEAD") e A1/A2 tem de cair -- rc=1 ao apanhar,
que e' a convencao desta casa.
"""
import ast
import io
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
FUNC = 'on_external_captions_released'


def find_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def build(src, segment):
    """A funcao REAL compilada no seu proprio namespace. `log` e' um coletor."""
    lines = [line[4:] if line.startswith('    ') else line
             for line in segment.splitlines()]
    body = '\n'.join(lines)
    ns = {'time': time, 'log': None}
    log_lines = []

    def _log(msg):
        log_lines.append(str(msg))

    ns['log'] = _log
    exec(compile(body, SHELL, 'exec'), ns)
    return ns[FUNC], log_lines


class _Exit(object):
    def __init__(self, set_):
        self._set = bool(set_)

    def is_set(self):
        return self._set

    def set(self):
        self._set = True


class FakeShell(object):
    def __init__(self, parked=True, park='captions', paused=False,
                 visible=False, caption=False, exiting=False):
        self._external_parked = bool(parked)
        self._paused = bool(paused)
        self.visible = bool(visible)
        self._caption_window_shown = bool(caption)
        self._park = park
        self._last_external_resume = 0.0
        self._player_frame_seen = True
        self.mirrors_cleared = False
        self.exiting = _Exit(exiting)
        self.writes = []

    def _clear_yt_source_mirrors(self):
        self.mirrors_cleared = True

    def engine_park_reason(self):
        return self._park

    def set_engine_park(self, value):
        self.writes.append(value)
        self._park = value


def run_arms(fn, log_lines):
    checks = []

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    # A1 -- o caso do dono: painel escondido, overlay escondido.
    del log_lines[:]
    sh = FakeShell(parked=True, park='captions', visible=False, caption=False)
    out = fn(sh)
    check('A1-hidden-release-clears-park',
          out is True and sh.writes == [None] and sh._external_parked is False,
          {'returned': out, 'writes': sh.writes,
           'latch': sh._external_parked, 'log': log_lines[-1:]})

    # A2 -- `_paused` nao guarda o pedido de parque.
    del log_lines[:]
    sh = FakeShell(parked=True, park='captions', paused=True)
    out = fn(sh)
    check('A2-paused-release-clears-park',
          out is True and sh.writes == [None],
          {'returned': out, 'writes': sh.writes, 'log': log_lines[-1:]})

    # A3 -- sem pedido pendente, nenhuma escrita.
    del log_lines[:]
    sh = FakeShell(parked=False)
    out = fn(sh)
    check('A3-no-park-no-write',
          out is False and sh.writes == [],
          {'returned': out, 'writes': sh.writes})

    # A4 -- o motivo VRAM e' de outro dono.
    del log_lines[:]
    sh = FakeShell(parked=True, park='vram')
    out = fn(sh)
    check('A4-vram-park-kept',
          out is False and sh.writes == [] and sh._park == 'vram',
          {'returned': out, 'writes': sh.writes, 'park': sh._park})

    # A5 -- a shell a sair nao escreve nada e nao gasta o latch.
    del log_lines[:]
    sh = FakeShell(parked=True, park='captions', exiting=True)
    out = fn(sh)
    check('A5-exiting-keeps-latch',
          out is False and sh.writes == [] and sh._external_parked is True
          and any('EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED' in line
                  for line in log_lines),
          {'returned': out, 'writes': sh.writes,
           'latch': sh._external_parked, 'log': log_lines[-1:]})

    # A6 -- o espelho da pausa morre em todos os caminhos.
    arms6 = []
    for kw in ({'parked': False}, {'park': 'vram'}, {'exiting': True},
               {'paused': True}):
        sh = FakeShell(**kw)
        fn(sh)
        arms6.append(sh.mirrors_cleared)
    check('A6-mirrors-cleared-every-path', all(arms6), {'per_path': arms6})

    # A7 -- a linha de sucesso nomeia o estado que decidiu.
    del log_lines[:]
    sh = FakeShell(parked=True, park='captions', paused=False, visible=False)
    fn(sh)
    line = log_lines[-1] if log_lines else ''
    check('A7-log-names-state',
          'EXTERNAL_CAPTIONS_ENGINE_RESUMED' in line and 'paused=false' in line
          and 'visible=false' in line,
          {'line': line})

    return checks


MUTANT_GATES = ("        if self._paused:\n"
                "            return False\n"
                "        if not (self.visible or getattr(self, "
                "'_caption_window_shown', False)):\n"
                "            return False\n")


def mutant_segment(segment):
    """As DUAS guardas de HEAD, repostas na funcao EXTRAIDA.

    Cirurgico de proposito: mutar o ficheiro de HEAD apodrece no dia em que a
    cura e' cometida, e mutar o ficheiro inteiro muda o que o oraculo mede.
    """
    anchor = '        now = time.monotonic()'
    if anchor not in segment:
        return None
    return segment.replace(anchor, MUTANT_GATES + anchor, 1)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    src = io.open(SHELL, encoding='utf-8').read()
    tree = ast.parse(src)
    node = find_func(tree, FUNC)
    if node is None:
        print('LATCH-ORACLE VERDICT: FAIL -- %s nao existe em %s'
              % (FUNC, SHELL))
        return 1
    segment = ast.get_source_segment(src, node)
    if not segment:
        print('LATCH-ORACLE VERDICT: FAIL -- sem segmento para %s' % FUNC)
        return 1
    fn, log_lines = build(src, segment)

    if '--neg-arm' in argv:
        mutated = mutant_segment(segment)
        if mutated is None:
            print('NEG-ARM IMPOSSIVEL -- a ancora de mutacao sumiu da funcao')
            return 2
        mfn, mlog = build(src, mutated)
        mchecks = run_arms(mfn, mlog)
        caught = [c['name'] for c in mchecks if not c['ok']]
        want = {'A1-hidden-release-clears-park', 'A2-paused-release-clears-park'}
        ok = want <= set(caught)
        print('MUTANT ARMS')
        for c in mchecks:
            print('  %-34s %s' % (c['name'], 'PASS' if c['ok'] else 'RED'))
        print('NEG-ARM: %s -- mutante apanhado por %d arm(s): %s'
              % ('PASS' if ok else 'FAIL', len(caught), ', '.join(caught)))
        return 1 if ok else 0

    checks = run_arms(fn, log_lines)
    failed = [c for c in checks if not c['ok']]
    print('LATCH ARMS')
    for c in checks:
        print('  %-34s %s' % (c['name'], 'PASS' if c['ok'] else 'RED'))
        if not c['ok']:
            print('      detail: %r' % (c['detail'],))
    verdict = 'PASS' if not failed else 'FAIL'
    print('LATCH-ORACLE VERDICT: %s (%d/%d)' % (verdict, len(checks) - len(failed),
                                                len(checks)))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
