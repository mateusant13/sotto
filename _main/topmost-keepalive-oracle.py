#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: capacidade/observabilidade copiada do RE de 2026-11-04 (Perssua + Handy); nao corresponde a nenhum id de `_main/bug-ledger.json`.
"""O PAINEL QUE PERDE O BIT TOPMOST -- o laco que o devolve tem de ser MEDIDO.

O QUE FOI COPIADO. Duas aplicacoes da mesma classe (ver
`H:/perssua-re/FINDINGS.md` e `H:/oss-re/FINDINGS.md`) re-asserem
`SetWindowPos(HWND_TOPMOST)` num timer de 2 s, porque o bit que o Sotto poe no
show nao e' propriedade: um player em ecra inteiro ou um jogo o tiram e a legenda
que o dono pediu fica por baixo, em silencio.

O QUE ESTE PORTAO PROVA. Executa `app/webview/topmost_keepalive.py` -- a decisao
pura (`should_reassert`) e o laco (`TopmostKeepalive.tick`) -- contra um
`GetWindowLongW` de mentira. Nove arms, e cada um tem o seu negativo:

  1. bit presente      -> ZERO chamadas ao USER32, e o tique conta.
  2. bit perdido       -> UMA re-afirmacao, nomeada no log.
  3. janela escondida  -> nunca re-afirma (ninguem ve a janela).
  4. leitor devolve None -> nao autoriza chamada (desconhecido nao e' "sem bit").
  5. leitor levanta    -> `TOPMOST_READ_FAILED`, o laco sobrevive.
  6. re-afirmar levanta -> `TOPMOST_REASSERT_FAILED`, o laco sobrevive.
  7. re-afirmar devolve False -> `TOPMOST_LOST_STILL` (diz que NAO voltou).
  8. hwnd vazio        -> nem le' (janela morta nao custa uma chamada).
  9. laco real         -> 3 tiques, intervalo respeitado, e para no stop.

BRACO NEGATIVO. `--neg-arm` muta `WS_EX_TOPMOST` para 0 numa COPIA do modulo (o
mutante "nunca mais re-afirma") e re-corre os mesmos arms; tem de cair o arm 2.
O codigo testado e' a copia, nunca o original.
"""

import io
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODULE = os.path.join(REPO, 'app', 'webview', 'topmost_keepalive.py')


def load_module(path):
    mod = types.ModuleType('topmost_keepalive_under_test')
    src = io.open(path, 'r', encoding='utf-8').read()
    exec(compile(src, path, 'exec'), mod.__dict__)
    return mod


class FakeWindow(object):
    def __init__(self, style, visible=True, read_raises=None, write_raises=None,
                 write_ok=True):
        self.style = style
        self.visible = visible
        self.read_raises = read_raises
        self.write_raises = write_raises
        self.write_ok = write_ok
        self.reads = 0
        self.writes = 0
        self.logs = []
        self.on_write = None

    def is_visible(self, hwnd):
        if self.read_raises:
            raise self.read_raises
        return self.visible

    def reader(self, hwnd):
        self.reads += 1
        if self.read_raises:
            raise self.read_raises
        return self.style

    def writer(self, hwnd):
        self.writes += 1
        if self.write_raises:
            raise self.write_raises
        if self.on_write:
            self.on_write(self)
        return self.write_ok

    def log(self, line):
        self.logs.append(line)

    def keepalive(self, mod, hwnd=0x1234, interval=2.0, sleep=None, clock=None,
                  stop=None):
        return mod.TopmostKeepalive(
            hwnd, self.is_visible, self.reader, self.writer, self.log,
            interval=interval, sleep=sleep, clock=clock, stop=stop)


def arm_bit_present(mod):
    w = FakeWindow(mod.WS_EX_TOPMOST | 0x00080000)
    ka = w.keepalive(mod)
    out = ka.tick()
    ok = (out is False and w.reads == 1 and w.writes == 0
          and ka.ticks == 1 and not w.logs)
    return ok, ('writes=%d reads=%d ticks=%d logs=%r'
                % (w.writes, w.reads, ka.ticks, w.logs))


def arm_bit_lost(mod):
    w = FakeWindow(0x00080000)  # visivel, sem TOPMOST
    ka = w.keepalive(mod)
    out = ka.tick()
    ok = (out is True and w.writes == 1 and ka.reasserted == 1
          and any('TOPMOST_REASSERT lost=true' in s for s in w.logs))
    return ok, 'out=%r writes=%d log=%r' % (out, w.writes, w.logs)


def arm_hidden_never(mod):
    # A decisao pura E o laco: uma janela escondida nao custa nem uma leitura de
    # estilo nem uma chamada ao USER32.
    pure = (mod.should_reassert(False, 0) is False
            and mod.should_reassert(False, mod.WS_EX_TOPMOST) is False)
    w = FakeWindow(0, visible=False)
    ka = w.keepalive(mod)
    out = ka.tick()
    ok = pure and out is False and w.writes == 0 and w.reads == 0
    return ok, 'pure=%s out=%r writes=%d reads=%d' % (pure, out, w.writes,
                                                      w.reads)


def arm_reader_none(mod):
    w = FakeWindow(None)
    ka = w.keepalive(mod)
    out = ka.tick()
    return (out is False and w.writes == 0), 'out=%r writes=%d' % (out, w.writes)


def arm_reader_raises(mod):
    w = FakeWindow(0, read_raises=OSError('hwnd morto'))  # visibility reader
    ka = w.keepalive(mod)
    out = ka.tick()
    again = w.keepalive(mod)
    second = again.tick()  # o laco sobrevive a' primeira leitura falhada
    ok = (out is False and w.writes == 0
          and any('TOPMOST_READ_FAILED' in s for s in w.logs))
    return (ok and second is False), 'out=%r logs=%r second=%r' % (
        out, w.logs, second)


def arm_write_raises(mod):
    w = FakeWindow(0, write_raises=OSError('recusado'))
    ka = w.keepalive(mod)
    out = ka.tick()
    ok = (out is False and ka.reasserted == 0
          and any('TOPMOST_REASSERT_FAILED' in s for s in w.logs))
    return ok, 'out=%r logs=%r' % (out, w.logs)


def arm_write_refused(mod):
    w = FakeWindow(0, write_ok=False)
    ka = w.keepalive(mod)
    out = ka.tick()
    ok = (out is False and ka.reasserted == 0
          and any('TOPMOST_LOST_STILL' in s for s in w.logs))
    return ok, 'out=%r logs=%r' % (out, w.logs)


def arm_no_hwnd(mod):
    w = FakeWindow(0)
    ka = w.keepalive(mod, hwnd=None)
    out = ka.tick()
    ok = (out is False and w.reads == 0 and w.writes == 0)
    return ok, 'reads=%d writes=%d' % (w.reads, w.writes)


def arm_loop(mod):
    w = FakeWindow(0)
    sleeps = []
    ticks = {'n': 0}

    def sleep(seconds):
        sleeps.append(seconds)
        ticks['n'] += 1

    ka = w.keepalive(mod, interval=2.0, sleep=sleep,
                     stop=lambda: ticks['n'] >= 3)
    ka.run()
    ok = (ka.ticks == 3 and w.writes == 3
          and sleeps == [2.0, 2.0, 2.0])
    return ok, 'ticks=%d writes=%d sleeps=%r' % (ka.ticks, w.writes, sleeps)


def arm_no_ctypes(mod):
    """O modulo nao fala com o Windows: a janela e' injectada pelo shell."""
    ok = not hasattr(mod, 'ctypes') and not hasattr(mod, 'user32')
    return ok, 'ctypes=%s user32=%s' % (hasattr(mod, 'ctypes'),
                                        hasattr(mod, 'user32'))


ARMS = [
    ('bit-present-no-call', arm_bit_present),
    ('bit-lost-reasserts', arm_bit_lost),
    ('hidden-never', arm_hidden_never),
    ('reader-none-no-call', arm_reader_none),
    ('reader-raises-survives', arm_reader_raises),
    ('write-raises-survives', arm_write_raises),
    ('write-refused-is-named', arm_write_refused),
    ('no-hwnd-no-call', arm_no_hwnd),
    ('loop-3-ticks-2s', arm_loop),
    ('no-ctypes-in-module', arm_no_ctypes),
]


def run(path):
    mod = load_module(path)
    rows = []
    for name, fn in ARMS:
        try:
            ok, detail = fn(mod)
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, 'EXCEPTION %r' % (exc,)
        rows.append((name, ok, detail))
        print('%-24s %s %s' % (name, 'PASS' if ok else 'RED', detail))
    return rows


def main(argv):
    if '--neg-arm' in argv:
        print('MUTANTE: WS_EX_TOPMOST = 0 (o laco nunca mais re-afirma)')
        tmpdir = tempfile.mkdtemp(prefix='topmost-neg-')
        try:
            copy = os.path.join(tmpdir, 'topmost_keepalive.py')
            shutil.copyfile(MODULE, copy)
            src = io.open(copy, 'r', encoding='utf-8').read()
            mutated = src.replace('WS_EX_TOPMOST = 0x00000008',
                                  'WS_EX_TOPMOST = 0', 1)
            assert mutated != src, 'ancora do mutante nao existe'
            io.open(copy, 'w', encoding='utf-8', newline='\n').write(mutated)
            rows = run(copy)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        red = [n for n, ok, _ in rows if not ok]
        caught = [n for n in ('bit-present-no-call', 'bit-lost-reasserts')
                  if n in red]
        if caught:
            print('NEG-ARM PASS (mutante apanhado: %s)' % ', '.join(caught))
            return 1
        print('NEG-ARM IMPOSSIVEL -- o mutante passou')
        return 2

    rows = run(MODULE)
    bad = [n for n, ok, _ in rows if not ok]
    print('VERDICT: %s (%d/%d arms)' % ('RED' if bad else 'PASS',
                                        len(rows) - len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
