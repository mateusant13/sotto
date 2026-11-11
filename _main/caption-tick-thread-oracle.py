#!/usr/bin/env python3
# NO-BUG: conta os fios criados pelo relogio do overlay com o `_arm_tick` real; nao mede CPU nem latencia da pintura no ecra do dono.
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

import importlib.util
import io
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "webview"))

import caption_overlay  # noqa: E402

MODULE = str(REPO / "app" / "webview" / "caption_overlay.py")
WORD_FADE = str(REPO / "app" / "webview" / "word_fade.py")


def _load(path, name):
    """Um modulo carregado PELO CAMINHO (e' assim que o negativo carrega a copia).

    `caption_overlay` importa `word_fade` por nome, logo a copia mutada tem de
    ter o irmao ao lado -- senao o mutante nao importa e nada e' provado.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _arm_a9(module_path, limit_ms=1.0):
    """A9 -- o relogio que o overlay usa para o prazo nao pode ter grao grosso.

    A medicao e' do RELOGIO, nao do texto: 60 000 leituras seguidas, o menor
    salto entre duas leituras distintas. `monotonic` devolve 15 ms aqui;
    `perf_counter` devolve menos de um microssegundo.
    """
    mod = _load(module_path, "tick_clock_probe")
    now = getattr(mod, "_frame_now", None)
    if now is None:
        return False
    seen = []
    t0 = now()
    while len(seen) < 200 and now() - t0 < 0.2:
        stamp = now()
        if not seen or stamp != seen[-1]:
            seen.append(stamp)
    if len(seen) < 50:
        return False
    gap = min(b - a for a, b in zip(seen, seen[1:]))
    return gap * 1000.0 < limit_ms


def _arm_a6(module_path):
    """A6 -- o tecto de frame, lido do `word_fade` QUE VIVE AO LADO do modulo."""
    path = os.path.join(os.path.dirname(os.path.abspath(module_path)),
                        "word_fade.py")
    wf = _load(path, "tick_word_fade")
    return (abs(wf.FRAME_S - 1.0 / 240.0) < 1e-9
            and int(getattr(wf, "FRAME_HZ", 0) or 0) == 240)


def _arm_a7(module):
    probe = object.__new__(module.NativeCaptionOverlay)
    probe._paint_cost_s = 0.0116
    probe._paint_limit_logged = 0.0
    lines = []
    probe.log = lines.append
    got = probe._limit_by_paint(1.0 / 240.0)
    budget = float(getattr(module, "CAPTION_FRAME_BUDGET", 0.0) or 0.0)
    # O PERIODO E' `custo / orcamento`, NAO o custo (2026-11-08). A versao
    # anterior punha o periodo IGUAL ao custo e o fio `sotto-caption-tick`
    # queimou 93,6 % de um nucleo na instancia viva (pid 42572): dormir o tempo
    # que se trabalha e' 100 % por construcao. A arm exige as duas metades --
    # a divisao pelo orcamento E que o periodo seja maior que o custo.
    return (budget > 0.0
            and abs(got - 0.0116 / budget) < 1e-9
            and got > 0.0116 * 1.05
            and any("CAPTION_FRAME_LIMIT" in ln for ln in lines)
            and any("budget=" in ln for ln in lines))


def _last_nap_is_sleep(module):
    """A8 -- conduz o laco REAL por UMA volta com o prazo a 3 ms de distancia.

    Nao se julga o texto do ficheiro: troca-se o `Event.wait` e o `time.sleep`
    do modulo por gravadores e exige-se que a volta curta use o `sleep` e que
    nao toque no `Event`. Uma volta que ainda dependa do `Event` para o ultimo
    trecho fica presa nos 5,03 ms medidos e nunca chega a 240 Hz.
    """
    # So' o sono do FRAME conta: o laco sem prazo espera 1 s no `Event` (é o
    # estado parado, e ali o `Event` é o certo -- nao ha' nada a acertar ao ms).
    seen = {"wait": 0, "frame_wait": 0, "sleep": 0.0}
    real_wait = module.time.sleep

    class FakeEvent(object):
        def wait(self, timeout=None):
            seen["wait"] += 1
            if timeout is not None and float(timeout) < 1.0:
                seen["frame_wait"] += 1
            return False

        def clear(self):
            return None

        def is_set(self):
            return False

        def set(self):
            return None

    def fake_sleep(seconds):
        seen["sleep"] += float(seconds or 0.0)

    obj = object.__new__(module.NativeCaptionOverlay)
    obj.lock = threading.RLock()
    obj._tick_gen = 0
    obj._tick_wake_gen = 0
    obj._tick_event = FakeEvent()
    obj._tick_stop = False
    obj._tick_deadline = module._frame_now() + 0.003
    obj.log = lambda *a: None
    obj._tick = lambda gen: None
    module.time.sleep = fake_sleep
    try:
        loop = threading.Thread(target=obj._tick_loop, daemon=True)
        loop.start()
        time.sleep(0.05)
        obj._tick_stop = True
        obj._tick_event = FakeEvent()
        loop.join(timeout=1.0)
        alive = loop.is_alive()
    finally:
        module.time.sleep = real_wait
        if alive:                      # nao deixa fio a girar com o sleep falso
            obj._tick_stop = True
    return seen["frame_wait"] == 0 and seen["sleep"] > 0.0 and not alive


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
    obj.log = lambda *a: None       # `_arm_tick` loga o cambio da resolucao
    obj._paint_cost_s = 0.0
    obj._paint_limit_logged = 0.0
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


def _arm_a10(module, seconds=0.9, cost=0.0116):
    """A10 -- O LACO REAL, COM O CUSTO REAL: a fracao de nucleo e' o ORCAMENTO.

    Esta e' a arm que teria apanhado o defeito MEDIDO na instancia viva (pid
    42572): com o periodo IGUAL ao custo, o laco dorme o tempo que trabalha e
    gasta 100 % de um nucleo. Aqui o `_update` dorme o custo de verdade e o laco
    e' o REAL (`_tick_loop`/`_tick`/`_arm_tick`), logo a fracao medida e'
    `quadros * custo / tempo` -- e ela tem de ficar no orcamento, nao em 1,0.

    Devolve (fracao, hz, quadros, tecto_hz).
    """
    budget = float(getattr(module, "CAPTION_FRAME_BUDGET", 0.0) or 0.0)
    obj = object.__new__(module.NativeCaptionOverlay)
    obj.lock = threading.RLock()
    obj._tick_gen = 0
    obj._tick_wake_gen = 0
    obj._tick_event = threading.Event()
    obj._tick_thread = None
    obj._tick_deadline = 0.0
    obj._tick_stop = False
    obj.hwnd = None
    obj.log = lambda *a: None
    obj._paint_cost_s = cost
    obj._paint_limit_logged = 0.0
    obj._next_delay = lambda: 1.0 / 240.0
    stamps = []

    def _update():
        stamps.append(module._frame_now())
        time.sleep(cost)                 # o custo da pintura, gasto a serio
        obj._arm_tick()

    obj._update = _update
    obj._arm_tick()
    time.sleep(seconds)
    obj._tick_stop = True
    obj._tick_event.set()
    if obj._tick_thread is not None:
        obj._tick_thread.join(timeout=1.0)
    n = len(stamps)
    frac = (n * cost / seconds) if seconds > 0 else 0.0
    hz = (n / seconds) if seconds > 0 else 0.0
    floor_hz = (1.0 / (cost / budget)) if (cost and budget) else 0.0
    return frac, hz, n, floor_hz


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

    # ── O TECTO DE 240 Hz E O QUE O LIMITA (dono, 2026-11-08) ───────────────
    # A6: o tecto do modulo E' 1/240 (o pedido dele, verbatim: *"acho que a
    # animacao da legenda pode ir ate 240hz"*).
    a6 = _arm_a6(MODULE)
    # A7: um quadro que CUSTA mais do que o pedido levanta o prazo ao custo -- e
    # diz o numero no log. Sem esta arm o tecto de 240 seria um pedido que a
    # pintura de 11,6 ms nunca pode honrar, e a animacao engasgaria.
    probe = object.__new__(caption_overlay.NativeCaptionOverlay)
    probe._paint_cost_s = 0.0116
    probe._paint_limit_logged = 0.0
    lines = []
    probe.log = lines.append
    limited = probe._limit_by_paint(1.0 / 240.0)
    _budget = float(getattr(caption_overlay, 'CAPTION_FRAME_BUDGET', 0.0) or 0.0)
    a7a = (_budget > 0.0 and abs(limited - 0.0116 / _budget) < 1e-9
           and limited > 0.0116 * 1.05)
    a7b = any("CAPTION_FRAME_LIMIT" in ln for ln in lines)
    free = object.__new__(caption_overlay.NativeCaptionOverlay)
    free._paint_cost_s = 0.0
    free._paint_limit_logged = 0.0
    free.log = lines.append
    a7c = free._limit_by_paint(1.0 / 240.0) == 1.0 / 240.0
    a7 = a7a and a7b and a7c
    # A8: o ultimo trecho do sono e' `time.sleep`, nao `Event.wait` -- medido:
    # `Event.wait(4,167 ms)` devolve em 5,03 ms (192 Hz de tecto).
    a8 = _last_nap_is_sleep(caption_overlay)

    # A9: O RELOGIO DO FRAME TEM RESOLUCAO DE FRAME. Medido 2026-11-08 nesta
    # maquina: `time.monotonic()` avanca de 15,000 ms em 15,000 ms, e todo o
    # prazo de quadro era aritmetica sobre ele -- 240 Hz lia-se como "0 ou 1
    # tique". A arm mede a granularidade do relogio que o overlay USA.
    a9 = _arm_a9(MODULE)
    # A10: o LACO REAL com o custo real -- a fracao de nucleo tem de ser o
    # orcamento, nao 1,0. E' a arm do defeito medido (93,6 % na instancia viva).
    # O CUSTO E' O MEDIDO NA INSTANCIA VIVA (11,6 ms): com o periodo antigo
    # (1/60) ele da' 0,69 de nucleo; sem limite nenhum, mais. O orcamento tem
    # de baixar isso para <= 0,40 sem tocar na taxa quando o quadro e' barato.
    frac, hz10, n10, floor_hz = _arm_a10(caption_overlay)
    _budget10 = float(getattr(caption_overlay, 'CAPTION_FRAME_BUDGET', 0.0) or 0.0)
    a10 = (n10 >= 8 and _budget10 > 0.0
           and frac <= _budget10 * 1.35          # folga do agendador, nao 100 %
           and floor_hz > 0.0 and hz10 <= floor_hz * 1.30)

    a1 = paints >= 20
    a2 = timers["n"] == 0
    a3 = grew <= 1
    a4 = quiet
    a5 = stopped
    checks = (("A1 o relogio pinta (frames=%d em 1 s)" % paints, a1),
              ("A2 zero threading.Timer (contados=%d)" % timers["n"], a2),
              ("A3 um fio so' (cresceu %d)" % grew, a3),
              ("A4 prazo cancelado nao pinta", a4),
              ("A5 destroy() para o fio", a5),
              ("A6 tecto de frame = 1/240", a6),
              ("A7 custo medido limita o pedido e loga", a7),
              ("A8 o ultimo trecho dorme em sleep", a8),
              ("A9 relogio do frame < 1 ms de grao", a9),
              ("A10 laco real: fracao de nucleo %.2f <= orcamento (%.0f Hz, %d quadros)"
               % (frac, hz10, n10), a10))
    for name, ok in checks:
        print("%-46s -> %s" % (name, "PASS" if ok else "FAIL"))
    if neg:
        caught = (not a2) and (not a3)
        print("NEG-ARM: %s (A2 caiu=%s, A3 caiu=%s com o Timer por frame de volta)"
              % ("PASS" if caught else "FAIL", not a2, not a3))
        # AS DUAS ARMS NOVAS TAMBEM TEM DE CAIR, cada uma pela SUA mutacao.
        src = io.open(WORD_FADE, encoding="utf-8", newline="").read()
        tmp = tempfile.mkdtemp(prefix="tick-240-")
        extra = []
        # (a) o tecto volta a 60 Hz -- na COPIA do `word_fade`, ao lado do modulo
        mut = os.path.join(tmp, "word_fade.py")
        io.open(mut, "w", encoding="utf-8", newline="").write(
            src.replace("FRAME_S = 1.0 / 240.0", "FRAME_S = 1.0 / 60.0", 1))
        os.makedirs(os.path.join(tmp, "app", "webview"), exist_ok=True)
        mut_mod = os.path.join(tmp, "app", "webview", "caption_overlay.py")
        io.open(mut_mod, "w", encoding="utf-8", newline="").write(
            io.open(MODULE, encoding="utf-8", newline="").read())
        io.open(os.path.join(tmp, "app", "webview", "word_fade.py"),
                "w", encoding="utf-8", newline="").write(
            io.open(mut, encoding="utf-8", newline="").read())
        extra.append(("tecto-de-volta-a-60",
                      not _arm_a6(mut_mod)))
        # (b) o limite por custo volta a ser o defeito de 100 % DE UM NUCLEO.
        # O ancoradouro mudou com a cura de 2026-11-08: o periodo deixou de ser
        # `cost * 1.02` e passou a ser `cost / CAPTION_FRAME_BUDGET`. Duas
        # mutacoes, porque sao duas as formas de reintroduzir o defeito: a linha
        # e a constante.
        mut2 = os.path.join(tmp, "app", "webview", "caption_overlay.py")
        io.open(mut2, "w", encoding="utf-8", newline="").write(
            io.open(MODULE, encoding="utf-8", newline="").read().replace(
                "        floor = cost / CAPTION_FRAME_BUDGET",
                "        floor = cost", 1))
        extra.append(("limite-volta-ao-custo",
                      not _arm_a7(_load(mut2, "tick_sem_limite"))))
        mut2b = os.path.join(tmp, "app", "webview", "caption_overlay_orc1.py")
        io.open(mut2b, "w", encoding="utf-8", newline="").write(
            io.open(MODULE, encoding="utf-8", newline="").read().replace(
                "CAPTION_FRAME_BUDGET = 0.40", "CAPTION_FRAME_BUDGET = 1.0", 1))
        extra.append(("orcamento-volta-a-1.0",
                      not _arm_a7(_load(mut2b, "tick_orc_1"))))
        # (c) o relogio do frame volta ao de grao grosso
        mut3 = os.path.join(tmp, "app", "webview", "caption_overlay_grosso.py")
        io.open(mut3, "w", encoding="utf-8", newline="").write(
            io.open(MODULE, encoding="utf-8", newline="").read().replace(
                "_frame_now = time.perf_counter", "_frame_now = time.monotonic", 1))
        shutil.copy2(WORD_FADE, os.path.join(tmp, "app", "webview", "word_fade.py"))
        extra.append(("relogio-de-grao-grosso", not _arm_a9(mut3)))
        for name, ok in extra:
            print("NEG-ARM %-26s %s" % (name, "CAUGHT" if ok else "NOT-CAUGHT"))
        caught = caught and all(ok for _n, ok in extra)
        print("NEG-ARM VERDICT: %s (%d/%d)"
              % ("PASS" if caught else "FAIL",
                 int(caught) + len(extra) - 1 + 2, 2 + len(extra)))
        return 1 if caught else 0
    ok = all(value for _n, value in checks)
    print("VERDICT: %s (%d/%d)" % ("PASS" if ok else "FAIL",
                                   sum(1 for _n, v in checks if v), len(checks)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
