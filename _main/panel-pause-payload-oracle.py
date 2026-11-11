#!/usr/bin/env python
# NO-BUG: executa `SottoShell.stats` num shell FALSO; nao prova o botao de pause na UI nem o clique do dono.
"""O PAYLOAD DE `stats()` CARREGA O PAUSE -- nas DUAS saidas.

ORDEM DO DONO, verbatim (2026-11-06): *"o botao de pause tambem nao ta completo.
o botao nao muda pra unpause."*

O QUE ESTE ORACULO EXECUTA. A funcao REAL (`SottoShell.stats`) de
`app/webview/sotto_webview.py`, ligada a um shell FALSO que tem so' o que ela
le' (`bridge.last_meter`, `bridge.last_worker_stats`, `_paused`). Nada de leitura
de texto: um `grep` diria que a linha existe mesmo num ramo que nunca corre.

AS ARMS

  A1  medidor FRESCO (o caso normal: um tick de medidor substitui a linha de
      WORKER_STATS inteira) com `_paused=True` -> o payload diz `paused: True`.
  A2  o mesmo ramo com `_paused=False` -> `paused: False` (e o campo EXISTE:
      "ausente" e' "nao me contaram", nao "a correr").
  A3  medidor VELHO (a outra saida, a linha do worker) -> o payload tambem diz.
  A4  um shell sem o atributo (`_paused` nunca criado) -> `paused: False`, e
      nunca `AttributeError`: o `stats()` corre em fios de fundo e uma excepcao
      aqui calava o medidor inteiro.
  A5  O PAYLOAD CONTINUA O QUE ERA: `tag` presente em todos os ramos, e o
      `paused` NAO substitui nem renomeia nada (as duas chaves que o painel le'
      estao la' quando o medidor as traz).

`--neg-arm` escreve uma COPIA do modulo com o carimbo arrancado das duas saidas e
exige que A1 e A3 fiquem vermelhas -- o codigo de "apanhado" e' 1.
"""
import argparse
import ast
import io
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')


def _shell_module(path=None):
    """The REAL module, imported once. `path` lets the neg-arm load a COPY."""
    sys.path.insert(0, os.path.dirname(path or SHELL))
    name = 'sotto_webview'
    if path is not None:
        name = 'sotto_webview_mutant'
    return __import__(name)


class FakeBridge(object):
    def __init__(self, meter=None, stats=None):
        self.last_meter = meter
        self.last_worker_stats = stats


class FakeShell(object):
    """Only the attributes `stats()` reads. Anything else is a defect."""

    def __init__(self, paused, meter=None, stats=None, drop_paused_attr=False):
        self.bridge = FakeBridge(meter=meter, stats=stats)
        if not drop_paused_attr:
            self._paused = paused


def measure(module, shell):
    return module.SottoShell.stats(shell)


def run(module, label):
    ok = 0
    total = 0
    lines = []

    def arm(name, real, want):
        nonlocal ok, total
        total += 1
        good = real == want
        ok += 1 if good else 0
        lines.append('[%s] %s' % ('PASS' if good else 'FAIL', name))
        lines.append('       real    = %r' % (real,))
        lines.append('       want    = %r' % (want,))

    meter_fresh = {'at': time.monotonic(), 'peak': 0.42, 'blocks': 11}
    payload = measure(module, FakeShell(True, meter=meter_fresh))
    arm('A1 medidor FRESCO com _paused=True -> paused True (e o resto do payload intacto)',
        [payload.get('paused'), payload.get('tag'), payload.get('peak'), payload.get('blocks')],
        [True, 'meter', 0.42, 11])

    payload = measure(module, FakeShell(False, meter=meter_fresh))
    arm('A2 o mesmo ramo com _paused=False -> paused False, e o campo EXISTE',
        ['paused' in payload, payload.get('paused')], [True, False])

    stale = {'at': time.monotonic() - 3600.0, 'peak': 0.1, 'blocks': 1}
    worker = {'tag': 'tick', 'fields': {'tag': 'tick', 'peak': '0.7', 'blocks': '30'},
              'line': 'WORKER_STATS peak=0.7 blocks=30 tag=tick'}
    payload = measure(module, FakeShell(True, meter=stale, stats=worker))
    arm('A3 medidor VELHO (a saida do WORKER_STATS) tambem carrega o pause',
        [payload.get('paused'), payload.get('tag'), payload.get('peak'), payload.get('blocks')],
        [True, 'tick', 0.7, 30.0])

    payload = measure(module, FakeShell(False, meter=meter_fresh, drop_paused_attr=True))
    arm('A4 shell sem o atributo -> paused False, e nao levanta',
        [payload.get('paused'), payload.get('tag')], [False, 'meter'])

    payload = measure(module, FakeShell(True, meter=None, stats=None))
    arm('A5 sem medidor e sem linha -> still the whole state, tag=stats',
        [payload.get('paused'), payload.get('tag')], [True, 'stats'])

    print('\n'.join(lines))
    print('%s: %d/%d' % (label, ok, total))
    return ok, total


def neg_arm():
    """Uma COPIA com o carimbo arrancado das duas saidas: A1 e A3 tem de cair."""
    src = io.open(SHELL, encoding='utf-8').read()
    line = "payload['paused'] = bool(getattr(self, '_paused', False))"
    changed = src.replace(line, 'pass  # MUTANT: o pause deixa de viajar')
    if changed == src:
        print('NEG-ARM IMPOSSIVEL -- o carimbo nao foi encontrado; o oraculo esta velho')
        return 2
    tmpdir = os.path.join(os.path.abspath(os.environ.get('TMPDIR') or 'I:\\cc-tmp'),
                          'sotto-pause-arm')
    os.makedirs(tmpdir, exist_ok=True)
    mutant = os.path.join(tmpdir, 'sotto_webview_mutant.py')
    io.open(mutant, 'w', encoding='utf-8').write(changed)
    # A copia importa os IRMAOS do diretorio real (`hot_reload`, `win32_types`,
    # ...): so' ESTE ficheiro difere, e um mutante que nao importa nao prova nada.
    sys.path.insert(0, os.path.dirname(SHELL))
    sys.path.insert(0, tmpdir)
    module = __import__('sotto_webview_mutant')
    # The mutant imports its own siblings from the real dir: only the copy of
    # THIS file differs.
    ok, total = run(module, 'MUTANT')
    caught = ok <= total - 2
    print('NEG-ARM: %s -- %d/%d arms ainda passam' % ('PASS' if caught else 'FAIL', ok, total))
    # A CONVENCAO DA CASA: o braco negativo devolve **1 quando APANHA**. Devolver
    # 0 ao apanhar faz do controlo um passo que nunca pode falhar -- medido
    # 2026-11-08: este ficheiro devolvia 0 com `NEG-ARM: PASS` e a linha do
    # `_audit-verify-all.cmd` declarava-o com rc esperado 0, logo nem o passo nem
    # o `:expectred` tinham como ficar vermelhos.
    return 1 if caught else 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--neg-arm', action='store_true')
    args = parser.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    module = _shell_module()
    ok, total = run(module, 'VERDICT')
    print('VERDICT: %s -- %d/%d arm(s)' % ('PASS' if ok == total else 'FAIL', ok, total))
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main())
