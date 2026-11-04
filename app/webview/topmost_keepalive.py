#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""O PAINEL VOLTA A SER TOPMOST QUANDO O PERDE (2026-11-04).

PORQUE EXISTE. O Sotto poe `HWND_TOPMOST` no show e nunca mais pergunta. Um
leitor de video em ecra inteiro, um jogo, ou o proprio Windows a reorganizar o
Z-order tiram o bit e a legenda que o dono pediu fica POR BAIXO -- sem erro, sem
log, e sem forma de ele saber por que. Medido na mesma classe de aplicacoes: um
overlay de legendas open-source re-assere `SetWindowPos(HWND_TOPMOST)` num timer
de 2 s (`H:/oss-re/FINDINGS.md`, secção do `Handy`), e o Perssua faz o mesmo por
outro caminho (`H:/perssua-re/FINDINGS.md`).

O QUE ESTE MODULO NAO FAZ. Nao chama `ShowWindow`, nao move a janela, nao muda o
tamanho, e nao toca em nada quando o bit ESTA' la' -- uma re-afirmacao cega seria
uma chamada ao USER32 a cada 2 s para o resto da sessao, um custo sem efeito. So
age quando `GetWindowLongW(GWL_EXSTYLE)` diz que o bit desapareceu, e diz no log
que agiu (`TOPMOST_REASSERT lost=true`) e que voltou a nao estar
(`TOPMOST_LOST_STILL`), para o caso de outro processo o tirar de novo.

A DECISAO E' PURA (`should_reassert`) e o laco recebe todas as funcoes de fora,
porque o portao `_main/topmost-keepalive-oracle.py` executa os dois sem abrir
janela nenhuma.
"""

#: `WS_EX_TOPMOST` -- a unica coisa que este modulo le'.
WS_EX_TOPMOST = 0x00000008

#: 2 s, o intervalo que a mesma classe de overlay usa: um pouco abaixo do passo
#: em que o dono nota a legenda por baixo, e um pouco acima do custo do
#: `GetWindowLongW` (uma chamada local por tique).
DEFAULT_INTERVAL_S = 2.0


def should_reassert(visible, style_bits):
    """Devolve True so' quando a janela esta' VISIVEL e PERDEU o bit.

    `visible=False` nunca pede nada: uma janela escondida e' topmost por omissao
    quando voltar (o show poe o bit), e re-afirmar uma janela escondida seria
    mexer no Z-order de uma janela que ninguem ve.
    """
    if not visible:
        return False
    if not isinstance(style_bits, int):
        # Um leitor que devolve None (janela morta, handle invalido) nao e' uma
        # janela sem bit -- e' um desconhecido, e um desconhecido nao autoriza
        # uma chamada ao USER32.
        return False
    return not (style_bits & WS_EX_TOPMOST)


class TopmostKeepalive(object):
    """Laco de re-afirmacao. Todas as dependencias entram por argumento."""

    def __init__(self, hwnd, visible_of, style_of, reassert, log,
                 interval=DEFAULT_INTERVAL_S, sleep=None, clock=None,
                 stop=None):
        import time as _time
        self.hwnd = hwnd
        self._visible_of = visible_of
        self._style_of = style_of
        self._reassert = reassert
        self._log = log
        self.interval = float(interval)
        self._sleep = sleep or _time.sleep
        self._clock = clock or _time.monotonic
        self._stop = stop or (lambda: False)
        self.ticks = 0
        self.reasserted = 0
        self.last_lost_at = None
        self.thread = None

    # -- uma volta do laco, separada do laco para o portao a poder chamar --
    def tick(self):
        self.ticks += 1
        hwnd = self.hwnd() if callable(self.hwnd) else self.hwnd
        if not hwnd:
            return False
        try:
            visible = bool(self._visible_of(hwnd))
            style = self._style_of(hwnd) if visible else 0
        except Exception as exc:  # noqa: BLE001 -- um leitor morto nao mata o laco
            self._log('TOPMOST_READ_FAILED error=%r' % (exc,))
            return False
        if not should_reassert(visible, style):
            return False
        self.last_lost_at = self._clock()
        try:
            ok = bool(self._reassert(hwnd))
        except Exception as exc:  # noqa: BLE001
            self._log('TOPMOST_REASSERT_FAILED error=%r' % (exc,))
            return False
        if ok:
            self.reasserted += 1
            self._log('TOPMOST_REASSERT lost=true ticks=%d' % self.ticks)
        else:
            self._log('TOPMOST_LOST_STILL ticks=%d' % self.ticks)
        return ok

    def run(self):  # pragma: no cover -- o portao chama `tick()` em vez disto
        import threading
        while not self._stop():
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001
                self._log('TOPMOST_TICK_FAILED error=%r' % (exc,))
            self._sleep(self.interval)

    def start(self):
        import threading
        self.thread = threading.Thread(target=self.run,
                                       name='sotto-topmost', daemon=True)
        self.thread.start()
        return self.thread
