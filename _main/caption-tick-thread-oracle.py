#!/usr/bin/env python3
"""O RELOGIO DO OVERLAY NAO CRIA UM FIO POR FRAME (2026-11-08).

Nasceu do DM do watcher: ele mediu `creation=90.879 creations/s` na arvore do
`sotto_webview.py` durante um stutter de 192 s. A unica criacao por frame que
esta app tem e' o `threading.Timer` que o `_arm_tick` armava a cada quadro --
com a legenda ao vivo a 16 ms isso e' dezenas de fios criados por segundo,
cada um `CreateThread` + `WaitForSingleObject`.

As arms correm o `_arm_tick`, o `_tick_loop` e o `_tick` REAIS de
`caption_overlay`, com o `_update` substituido por um contador (o resto do
caminho e' o que embarca):

  A1 o relogio PINTA: N ticks em T segundos (o trabalho nao parou);
  A2 ZERO `threading.Timer` construido, seja qual for o numero de frames;
  A3 um fio SO': `threading.active_count()` cresce no maximo 1;
  A4 prazo cancelado (`delay=None`) nao deixa o fio a girar: ele espera no
     `Event` e nao pinta nada novo;
  A5 `destroy()` para o fio (a thread morre dentro de 2 s).

NEG (`--neg-arm`): poe de volta a implementacao ANTIGA (`threading.Timer` por
frame) e exige A2 e A3 vermelhos -- um oraculo que nao cai com o defeito de
volta nao mede nada.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "webview"))

import caption_overlay  # noqa: E402


def _make(delay=0.005):
    """Um overlay SEM janela: os metodos reais, o `_update` contado."""
    obj = object.__new__(caption_overlay.NativeCaptionOverlay)
    obj.lock = threading.RLock()
    obj._tick_gen = 0
    obj._tick_timer = None
    obj._tick_event = threading.Event()
    obj._tick_thread = None
    obj._tick_deadline = 0.0
    obj._tick_stop = False
    obj.hwnd = None               # sem janela: `destroy` nao posta WM_CLOSE
    obj._thread = threading.Thread(target=lambda: None, daemon=True)
    obj._thread.start()
    obj.paints = []
    obj._next_delay = lambda: delay
    def _update():
        obj.paints.append(time.monotonic())
        obj._arm_tick()          # o caminho real: `_update` rearma o proximo frame
    obj._update = _update
    return obj


def _old_arm_tick(obj, delay):
    """A IMPLEMENTACAO ANTIGA, para o braco negativo."""
    obj._tick_gen += 1
    gen = obj._tick_gen
    timer = threading.Timer(delay, lambda: obj._tick(gen))
    timer.daemon = True
    obj._tick_timer = timer
    timer.start()


def main(argv=None) -> int:
    neg = "--neg-arm" in (argv if argv is not None else sys.argv[1:])

    timers = {"n": 0}
    real_timer = threading.Timer

    def counting_timer(*a, **k):
        timers["n"] += 1
        return real_timer(*a, **k)

    threading.Timer = counting_timer
    threads0 = threading.active_count()
    obj = _make()
    try:
        seconds = 1.0
        peak = threads0
        if neg:
            # braco negativo: a implementacao antiga, um `Timer` por frame
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                _old_arm_tick(obj, 0.005)
                peak = max(peak, threading.active_count())
                time.sleep(0.005)
        else:
            obj._arm_tick()          # UM arme; a cadeia `_update`->`_arm_tick` corre
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                peak = max(peak, threading.active_count())
                time.sleep(0.005)
        paints = len(obj.paints)
        grew = peak - threads0
        # A4: prazo cancelado
        obj._next_delay = lambda: None
        obj._arm_tick()
        frozen = len(obj.paints)
        time.sleep(0.3)
        quiet = len(obj.paints) == frozen
        # A5: destroy para o fio
        obj.destroy()
        time.sleep(0.4)
        stopped = not (obj._tick_thread and obj._tick_thread.is_alive())
    finally:
        threading.Timer = real_timer

    a1 = paints >= 20
    a2 = timers["n"] == 0
    a3 = grew <= 1
    a4 = quiet
    a5 = stopped
    checks = (("A1 o relogio pinta (frames=%d em 1 s)" % paints, a1),
              ("A2 zero threading.Timer (contados=%d)" % timers["n"], a2),
              ("A3 um fio so' (cresceu %d)" % grew, a3),
              ("A4 prazo cancelado nao pinta", a4),
              ("A5 destroy() para o fio", a5))
    for name, ok in checks:
        print("%-46s -> %s" % (name, "PASS" if ok else "FAIL"))
    if neg:
        caught = (not a2) and (not a3)
        print("NEG-ARM: %s (A2 caiu=%s, A3 caiu=%s com o Timer por frame de volta)"
              % ("PASS" if caught else "FAIL", not a2, not a3))
        return 1 if caught else 0
    ok = all(value for _n, value in checks)
    print("VERDICT: %s (%d/%d)" % ("PASS" if ok else "FAIL",
                                   sum(1 for _n, v in checks if v), len(checks)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
