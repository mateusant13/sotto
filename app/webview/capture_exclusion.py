"""CAPTURE EXCLUSION: a legenda nao entra na gravacao nem na partilha.

Portado do que o `perssua-re` faz com `SetWindowDisplayAffinity`: a janela
continua a ser desenhada no ecra do dono, mas o compositor do Windows nao a
entrega a quem captura o ecra (`Graphics.Capture`, OBS com `WGC`, `Snipping
Tool`, partilha de ecra do Teams/Zoom/Discord). E' o oposto do `WDA_MONITOR`,
que escurece a janela para quem captura.

AS DUAS CONSTANTES NAO SAO INTERCAMBIAVEIS. Medido no Windows desta maquina
(build 26200): `WDA_EXCLUDEFROMCAPTURE` (0x11) existe desde a build 19041 e e'
o unico modo que ESCONDE a janela; `WDA_MONITOR` (0x01) so' a deixa preta na
captura -- o dono ve a legenda, a gravacao ve um rectangulo preto. Por isso a
escada e' 0x11 -> 0x01 -> nada, e cada degrau e' publicado no log: um modo que
nao se sabe qual e' nao se pode afirmar.

O QUE ESTE MODULO NAO FAZ: nao toca em estilos da janela, nao faz hooks, nao
abre device nenhum. Uma chamada por janela, no momento em que ela nasce.
"""

from __future__ import annotations

import ctypes
import os
import sys

WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011

#: A build em que `WDA_EXCLUDEFROMCAPTURE` passou a existir (Windows 10 2004).
MIN_BUILD_EXCLUDE = 19041

_user32 = ctypes.WinDLL('user32', use_last_error=True)
_user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_user32.SetWindowDisplayAffinity.restype = ctypes.c_int
_user32.GetWindowDisplayAffinity.argtypes = [ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_uint)]
_user32.GetWindowDisplayAffinity.restype = ctypes.c_int


def build_number():
    """A build do Windows, ou 0 quando o interpretador nao a sabe."""
    try:
        return int(sys.getwindowsversion().build)
    except Exception:  # noqa: BLE001
        return 0


def can_exclude(build=None):
    """`True` quando `WDA_EXCLUDEFROMCAPTURE` e' uma constante que existe."""
    build = build_number() if build is None else int(build)
    return build >= MIN_BUILD_EXCLUDE


def enabled(environ=None):
    """O interruptor: ligado por omissao, `SOTTO_CAPTURE_EXCLUDE=0` desliga.

    Ligado por omissao porque esta e' a razao de existir do overlay: quem grava
    o ecra nao deve ficar com a legenda colada por cima do video. Desligado, a
    janela comporta-se como antes (entra na captura) e isso fica no log.
    """
    env = os.environ if environ is None else environ
    return str(env.get('SOTTO_CAPTURE_EXCLUDE', '1')).strip() not in ('0', 'false', 'off', 'no')


def apply(hwnd, want=True, build=None):
    """Aplica a afinidade e devolve `{'mode', 'ok', 'why'}`.

    `mode` e' o que ficou APLICADO (lido de volta pelo sistema, nunca o que se
    pediu): pedir 0x11 e ficar com 0x00 e' uma falha, nao um sucesso.
    """
    if not hwnd:
        return {'mode': WDA_NONE, 'ok': False, 'why': 'sem hwnd'}
    if not want:
        _user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), WDA_NONE)
        return {'mode': read(hwnd), 'ok': True, 'why': 'desligado'}
    ladder = []
    if can_exclude(build):
        ladder.append(WDA_EXCLUDEFROMCAPTURE)
    ladder.append(WDA_MONITOR)
    last_err = 0
    for mode in ladder:
        ok = _user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), mode)
        if not ok:
            last_err = ctypes.get_last_error()
            continue
        got = read(hwnd)
        if got == mode:
            return {'mode': got, 'ok': True,
                    'why': 'aplicado' if mode == WDA_EXCLUDEFROMCAPTURE else
                           'fallback 0x01 (build %s)' % (build_number() if build is None else build)}
    return {'mode': read(hwnd), 'ok': False,
            'why': 'SetWindowDisplayAffinity falhou (error=%d)' % last_err}


def read(hwnd):
    """O valor que o sistema diz estar em vigor, ou -1 quando nao responde."""
    if not hwnd:
        return -1
    value = ctypes.c_uint(0)
    if not _user32.GetWindowDisplayAffinity(ctypes.c_void_p(hwnd),
                                            ctypes.byref(value)):
        return -1
    return int(value.value)


def mode_name(mode):
    return {WDA_NONE: 'none', WDA_MONITOR: 'monitor',
            WDA_EXCLUDEFROMCAPTURE: 'exclude'}.get(mode, '0x%02x' % (mode & 0xff))
