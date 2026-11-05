#!/usr/bin/env python
# NO-BUG: instrumento da ordem do dono de 2026-11-05. Prova, NO WINDOWS DESTA
# MAQUINA, a mecanica de que o oracle puro (`ctrlspace-swallow-oracle.py`) so'
# fala por fakes: `RegisterHotKey` RESERVA a combinacao (logo a tecla nao chega
# a' janela em foco) e `UnregisterHotKey` DEVOLVE-a.
"""PROBE: `RegisterHotKey` toma mesmo o `Ctrl+Space` -- e devolve-o.

A PERGUNTA QUE ELE RESPONDE. O oraculo puro prova a TABELA e o FIO com um
`user32`-gravador. Falta a metade que nenhum fake pode dar: o Windows, nesta
maquina, recusa uma SEGUNDA reserva da mesma combinacao (`winerror=1409`) e
aceita-a de novo depois do `UnregisterHotKey`. Sem essa prova, "o espaco nao
chega a' outra app" e' uma inferencia da documentacao, nao uma medicao.

O QUE ELE NAO FAZ. Nao carrega tecla nenhuma (`keybd_event`/`SendInput` = 0: os
dois medem o Windows, nao a app), nao abre janela, nao mexe no audio. Reserva a
combinacao por ~100 ms e devolve-a. Se uma instancia do Sotto estiver viva, a
primeira reserva da' 1409 -- e isso TAMBEM e' a resposta: a tecla esta' tomada
por quem a deve tomar, e o probe diz `holder=someone-else`.

Uso:
    python _main/ctrlspace-swallow-probe.py            -> rc 0 PASS / rc 1 RED
    python _main/ctrlspace-swallow-probe.py --json     -> a leitura crua
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import sys

user32 = ctypes.WinDLL('user32', use_last_error=True)

MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
HOTKEY_ID = 0xB0F1


class _Runner(object):
    """Uma reserva feita do THREAD onde ela vive (`hWnd=NULL` e' por-fio)."""

    def __init__(self):
        self.register = None
        self.register_err = None
        self.thread_id = None

    def take(self):
        self.thread_id = int(ctypes.windll.kernel32.GetCurrentThreadId())
        msg = wt.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        ctypes.set_last_error(0)
        ok = user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_NOREPEAT,
                                   VK_SPACE)
        self.register = bool(ok)
        self.register_err = int(ctypes.get_last_error()) if not ok else 0
        return self.register

    def release(self):
        if self.thread_id is None:
            return False
        return bool(user32.UnregisterHotKey(None, HOTKEY_ID))


def main(argv):
    out = {'n_second_register_rc': None, 'second_err': None,
           'first_rc': None, 'first_err': None,
           'third_after_release_rc': None, 'third_err': None,
           'holder': None, 'verdict': 'FAIL'}
    a = _Runner()
    first = a.take()
    out['first_rc'] = int(a.register)
    out['first_err'] = a.register_err
    if not first:
        # Alguem tem a combinacao: ou a app do dono, ou outro programa. O probe
        # nao pode afirmar "a nossa reserva funciona" -- e nao afirma.
        out['holder'] = 'someone-else' if a.register_err == 1409 else 'error'
    else:
        out['holder'] = 'this-probe'
    # A SEGUNDA RESERVA, DE OUTRO FIO, E' A PROVA DE EXCLUSIVIDADE.
    b = _Runner()
    second = b.take()
    out['n_second_register_rc'] = int(b.register)
    out['second_err'] = b.register_err
    if second:
        b.release()
    released = a.release()
    c = _Runner()
    third = c.take()
    out['third_after_release_rc'] = int(c.register)
    out['third_err'] = c.register_err
    if third:
        c.release()

    # O VEREDITO DA MECANICA, sem confundir os dois casos.
    if first:
        exclusive = (not second) and b.register_err == 1409
        out['verdict'] = 'PASS' if (exclusive and third and released) else 'FAIL'
    else:
        # A tecla ja' era de alguem: a exclusividade prova-se pelo 1409 alheio.
        out['verdict'] = 'PASS' if a.register_err == 1409 else 'FAIL'

    if '--json' in argv:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print('CTRLSPACE-SWALLOW-PROBE holder=%(holder)s '
              'first=%(first_rc)s err=%(first_err)s'
              ' second=%(n_second_register_rc)s second_err=%(second_err)s'
              ' third_after_release=%(third_after_release_rc)s '
              'third_err=%(third_err)s' % out)
        print('CTRLSPACE-SWALLOW-PROBE VERDICT: %s -- a reserva e exclusiva: '
              'a segunda falha com 1409 e a liberta-cao devolve a tecla'
              % out['verdict'])
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
