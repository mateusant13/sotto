"""OS DOIS INSTRUMENTOS DE SELFTEST do shell, fora do produto.

PORQUE E' QUE ISTO VIVE NUM MODULO PROPRIO. `app/webview/sotto_webview.py` esta'
debaixo do ratchet estrutural (`_main/code-health-oracle.py`: bytes, linhas,
defs, classes, funcao mais longa, `except: pass`, `global` -- nenhum pode
piorar), e a lane do Alt+C trouxe o INSTRUMENTO da medicao para dentro do shell:
as constantes `SELFTEST_*`, o veredicto `selftest_broken`, as duas leituras de
foco e o `run_selftest` inteiro. Um instrumento de medicao dentro do produto e'
codigo que mede, nao codigo que serve o dono -- e o shell pagava-o em bytes,
linhas e defs. A cura que o proprio ratchet nomeia e' esta: extrair, sem tocar no
comportamento. `sotto_webview.py` importa estes nomes de volta com os MESMOS
nomes, por isso nenhum chamador (a largada `--selftest`, os oraculos) muda.

O QUE ESTA' AQUI, e nada mais:
  * o instrumento do Alt+C (`--selftest`) -- o orcamento do passo e as tres
    janelas de medicao (`SELFTEST_*`), o veredicto PURO `selftest_broken`, a
    amostragem de foco (`foreground_window`, `window_pid`) e `run_selftest` com
    os helpers que so' ele usa (`screen()`, `wait_for()`, `step()` e o rasto de
    foco);
  * o instrumento do reload do worker (`--probe-reload`, que imprime
    `SELFTEST reload rc=`): ele ja' vivia no fim do mesmo ficheiro e mede a
    mesma coisa -- o produto a comportar-se -- por isso vem com o primeiro em
    vez de ficar a ser a unica sonda dentro do shell.

O QUE NAO ESTA' AQUI, e nao pode estar: `HotkeyThread.simulate_press` (a entrega
da pressao e' MECANISMO do thread, e `_main/altc-delivery` chama-a),
`pointer_lock_state` (e' produto: `foreground_unlock` le), `window_visible`
(idem) e `WorkerReloadPolicy` (idem: o `--probe-reload` e' o unico chamador
daquele lado). ESTE MODULO NAO IMPORTA `sotto_webview`: um ciclo
shell->instrumento->shell seria a segunda tabela que o repo inteiro existe para
nao ter. As pecas do produto entram por PARAMETRO.

A AMOSTRAGEM DE FOCO E' A MESMA LINHA DE WIN32, so' mudou de ficheiro: os
`restype`/`argtypes` de `GetForegroundWindow`/`GetWindowThreadProcessId` viajam
com as funcoes que os usam, e o handle `user32` e' o MESMO (`ctypes.WinDLL`
cacheia o DLL por nome), logo uma leitura feita aqui e uma feita no shell sao
indistinguiveis para o Windows.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import shutil
import tempfile
import time

import hot_reload

user32 = ctypes.WinDLL('user32', use_last_error=True)

user32.GetForegroundWindow.restype = wt.HWND


def foreground_window() -> int:
    return int(user32.GetForegroundWindow() or 0)


#: WHO owns a window. `--selftest` needs this to tell "the panel took the
#: foreground" from "the owner switched apps while the test was running": only
#: the FIRST is a defect of this program, and a verdict that cannot tell them
#: apart is flaky on a live desktop (audit rows #28 / #H6 / Finding B, closed
#: by `_main/selftest-focus-oracle.py`).
user32.GetWindowThreadProcessId.restype = ctypes.c_uint
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(ctypes.c_uint)]


def window_pid(hwnd: int) -> int:
    """The pid that owns `hwnd`, or 0 for no window."""
    if not hwnd:
        return 0
    owner = ctypes.c_uint(0)
    user32.GetWindowThreadProcessId(wt.HWND(hwnd), ctypes.byref(owner))
    return int(owner.value)


#: O ORCAMENTO DO PASSO: pressao -> o estado mudou no ecra. E' o dono que o
#: escreveu (`_main/altc-first-caption-oracle.py --budget-ms`, fabrica 1 500 ms),
#: e e' o mesmo numero para as duas teclas.
SELFTEST_STEP_BUDGET_MS = 1500.0

#: A JANELA DE MEDICAO da PRIMEIRA exibicao -- e porque e' maior que o orcamento.
#: MEDIDO 2026-11-01 (Main, na instancia do dono): a primeira exibicao custou
#: **12 070 ms** -- `HOTKEY_TOGGLE step=show` 10:14:47.808 -> `PANEL_SHOWN`
#: 10:14:59.878, com `WARN exec_js TIMEOUT after 10.0s` pelo meio. Uma janela de
#: 3 s nao ve isso: ela expira antes de o painel aparecer e o teste chama-lhe
#: "pressao nao entregue", que e' a conclusao errada sobre o facto errado. 20 s
#: deixam o numero APARECER, e sao os 1 500 ms que reprovam -- por `latency_ms`.
SELFTEST_COLD_WINDOW_S = 20.0

#: As armas DEPOIS da primeira: um show/hide quente custou ~45 ms (medido no log
#: do dono 2026-11-01 10:15:00, 10 alternancias em 0.432 s). 6 s e' folga de
#: MEDICAO, nao orcamento: quem reprova por lentidao e' `latency_ms`.
SELFTEST_STEP_WINDOW_S = 6.0

#: Cada uma das dez pressoes da arma 5: 2,5 s por pressao deixa o laco inteiro
#: caber no `--exit-after` do instrumento de fora, e uma pressao que nao muda o
#: ecra em 2,5 s ja' e' um defeito que nao melhora por esperar mais.
SELFTEST_PRESS_WINDOW_S = 2.5


def selftest_broken(reading: dict) -> tuple[bool, str]:
    """The self-test VERDICT, factored out of the method so it can be driven
    with synthetic readings and no hotkey. Pure on purpose: no globals, no
    ctypes -- the oracle proves it by exec-ing this exact source in a bare
    namespace, so a dependency creeping in here fails the gate instead of
    passing through a module import.

    `focus_stolen_by_own_window` is the clause the old verdict was missing: it
    measured `focus_stolen` (before != after) and logged it, then computed
    `broken` WITHOUT it -- so a run in which the panel took the foreground was
    reported GREEN. The word "stolen" is now attributed: a FOREIGN window that
    became foreground is somebody else using the PC, not this program cheating,
    and failing on that would be a false alarm on every busy desktop.
    """
    if not reading.get('registered'):
        return True, 'the hotkey never registered'
    if not reading.get('pressed'):
        return True, 'the simulated press was not delivered'
    # ENTREGA E LATENCIA SAO DUAS CLAUSULAS, e a primeira NUNCA apaga a segunda.
    # `pressed` diz so' "o `WM_HOTKEY` chegou" (e o `count=` do log bate com o
    # numero de presses); quanto tempo o estado levou a mudar e' `latency_ms`,
    # medido contra `SELFTEST_STEP_BUDGET_MS`. Antes era uma clausula so': uma
    # espera curta expirava, a leitura dizia `pressed=False` e o veredicto
    # culpava a ENTREGA de uma LENTIDAO -- medido 2026-11-01, `SELFTEST rc=3`
    # com `broken=the simulated press was not delivered` numa app que alternava
    # dez vezes em 432 ms.
    latency = reading.get('latency_ms')
    budget = reading.get('latency_budget_ms')
    if latency is not None and budget is not None and float(latency) > float(budget):
        first = float(reading.get('first_show_ms') or 0.0)
        return True, ('pressao -> o ecra mudou em %.0f ms; o orcamento e %.0f ms '
                      '(a PRIMEIRA exibicao foi %.0f ms, first_show_slow=%s). '
                      'A pressao FOI entregue: isto e latencia, nao entrega.'
                      % (float(latency), float(budget), first,
                         str(first > float(budget)).lower()))
    # O NUMERO DE PRESSAO ESPERADO E' DA LEITURA, nao do juiz. Ja' foi fixo em 2
    # (dois toques, contrato de 2026-10-30) e o contrato de 2026-11-01 faz quatro
    # passos mais dez; um juiz com o numero antigo dentro reprovaria o proprio
    # desenho. Uma leitura que nao declare `expect_presses` nao e' prova sobre a
    # contagem (as leituras sinteticas dos oraculos de foco).
    if (reading.get('expect_presses') is not None
            and reading.get('presses') != reading['expect_presses']):
        return True, ('expected %r presses, saw %r'
                      % (reading.get('expect_presses'), reading.get('presses')))
    if 'visible' in reading and reading['visible'] != reading.get('want_visible'):
        return True, ('the window should read visible=%r after the last press, got %r'
                      % (reading.get('want_visible'), reading.get('visible')))
    if reading.get('focus_stolen_by_own_window'):  # FOCUS-CLAUSE
        # UMA EXCECAO SO', E ELA ESTA' DOCUMENTADA NA APP: `foreground_unlock` e
        # `show_strip` dizem *"The no-focus invariant (`SW_SHOWNOACTIVATE`) holds
        # for every path EXCEPT the owner's own Alt+C: when he presses the app's
        # only control he is asking for the panel"*, e o show da hotkey loga
        # `PANEL_SHOWN ... focus_stolen=intentional(hotkey)` (medido 2026-11-01
        # 10:18:24.402, instancia de sonda). Um veredicto que ignore isso reprova
        # para sempre a app que a lei manda ter -- foi o `SELFTEST rc=3` de hoje.
        # Uma leitura SEM `focus_steal_allowed` (as sinteticas do
        # `selftest-focus-oracle`) continua a ser julgada como sempre foi.
        #
        # NAO HA' CLAUSULA POR PASSO AQUI, e e' medido: `foreground_window()`
        # amostrado logo depois de um passo apanha a mudanca do passo ANTERIOR
        # (a activacao do Alt+C assenta um frame depois do `SetForegroundWindow`)
        # -- na primeira corrida com rasto por passo, quem levou a culpa foi o
        # `2-hidden`, que nao toma foco nenhum. O rasto (`SELFTEST focus_steals=`)
        # fica no log como EVIDENCIA; o veredicto nao o julga, porque julgar um
        # numero que sabemos atrasado e' inventar.
        if str(reading.get('focus_steal_allowed') or '') not in ('pointer-lock',
                                                                 'hotkey'):
            return True, ('the panel TOOK the foreground -- focus_before=%r focus_after=%r; '
                          'SW_SHOWNOACTIVATE is the contract and this is it being broken'
                          % (reading.get('focus_before'), reading.get('focus_after')))
    # -- O CONTRATO DE 2026-11-01, UM PASSO POR PRESSAO. Cada clausula e'
    # verificada so' quando a leitura CARREGA a chave, para as leituras
    # sinteticas mais antigas dos oraculos de foco continuarem a significar o que
    # significavam -- uma leitura sem estas chaves nao e' prova sobre elas.
    if 'first_press_strip' in reading and not reading['first_press_strip']:
        return True, 'a PRIMEIRA pressao de Alt+C nao abriu a faixa de baixo'
    if 'second_press_hidden' in reading and not reading['second_press_hidden']:
        return True, 'a SEGUNDA pressao de Alt+C nao escondeu a faixa'
    if 'third_press_panel' in reading and not reading['third_press_panel']:
        return True, 'a TERCEIRA pressao de Alt+C nao abriu o painel da direita'
    if 'fourth_press_hidden' in reading and not reading['fourth_press_hidden']:
        return True, 'a QUARTA pressao de Alt+C nao escondeu o painel'
    if ('ten_press_alternations' in reading
            and not reading['ten_press_alternations']):
        return True, ('dez pressoes nao deram dez alternancias na ordem: %r'
                      % (reading.get('ten_press_observed'),))
    if 'live_toggled' in reading and not reading['live_toggled']:
        return True, 'o Ctrl+Space nao ligou/desligou a legenda ao vivo'
    if 'live_left_panels' in reading and not reading['live_left_panels']:
        return True, 'o Ctrl+Space mexeu no painel; a tecla da legenda e so a legenda'
    if 'live_caption_left_alone' in reading and not reading['live_caption_left_alone']:
        return True, 'o Alt+C mexeu na legenda; o painel e a legenda sao gestos diferentes'
    return False, ''


def run_selftest(shell, *, log, HotkeyThread, hotkey_numbers,
                 hotkey_config, window_visible, pointer_lock_state):
    """Prove BOTH hotkeys deliver exactly one step per press, six ways.

    The press is a real `WM_HOTKEY` posted to a hotkey thread's own queue, so
    the delivery path under test is the one the OS writes to. THE THREAD DOES
    NOT TAKE THE OWNER'S KEY: in a MEASUREMENT launch (`--selftest`) the
    global keys are disarmed by `main()`, so when one is missing this method
    starts a hotkey thread with `register=False` -- queue and pump, no
    `RegisterHotKey` -- and `simulate_press` posts the same message the system
    would. Nothing on the owner's keyboard is intercepted.

    THE ARMS (2026-11-01 contract -- cada pressao e' UM passo):

        arm 1  press        hidden  -> STRIP   (caption UNCHANGED)
        arm 2  press        strip   -> HIDDEN
        arm 3  press        hidden  -> PANEL
        arm 4  press        panel   -> HIDDEN
        arm 5  ten presses  hidden  -> strip, hidden, panel, hidden, ...
                            (ten alternations, in that order, with the key
                             "held": no release event is ever delivered, and
                             the retired duration seam does not exist)
        arm 6  Ctrl+Space   the LIVE CAPTION toggles once, NO panel moves

    `selftest_broken` is the gate and every arm is a clause in it, so a wrong
    arm exits non-zero. Nothing here injects a duration (`fake_hold_ms` was
    deleted with the contract it served) and nothing uses `keybd_event`:
    `AGENTS.md` -- input sintetico mede o Windows, nao a app.

    ENTREGA E LATENCIA SAO DUAS MEDICOES. `posted` (mais o `count=` do log)
    diz que o `WM_HOTKEY` chegou; `seen`/`latency_ms` dizem quanto tempo o
    ecra levou a mudar, julgado por `SELFTEST_STEP_BUDGET_MS` (1 500 ms). A
    primeira exibicao espera `SELFTEST_COLD_WINDOW_S` porque ela custou
    **12 070 ms** a 2026-11-01 (medido: `HOTKEY_TOGGLE step=show`
    10:14:47.808 -> `PANEL_SHOWN` 10:14:59.878) -- e uma janela curta nao
    acha "app lenta", acha "pressao nao entregue", que e' a conclusao errada
    sobre o facto errado.
    """
    rc = 0
    # ── THE THREADS UNDER TEST ─────────────────────────────────────────
    # A real launch hands us the armed threads. A MEASUREMENT launch arms
    # none (main() disarms them so the owner's Alt+C never answers a probe),
    # and that is not a reason to skip the test: a probe thread has the same
    # queue and the same pump, it only does not call `RegisterHotKey`.
    panels = shell.hotkey
    live = getattr(shell, 'live_hotkey', None)
    started = []
    try:
        if panels is None:
            panels = HotkeyThread(hotkey_numbers().PANELS_ACCELERATOR,
                                  lambda: shell.hotkey_pressed(),
                                  role='panels-probe', register=False)
            panels.start()
            started.append(panels)
        if live is None:
            try:
                live_accel = hotkey_config().accelerators()['live']
            except Exception:  # noqa: BLE001 -- a fabrica e' sempre resposta
                live_accel = hotkey_numbers().LIVE_ACCELERATOR
            live = HotkeyThread(live_accel, lambda: shell.hotkey_live(),
                                role='live-probe', register=False)
            live.start()
            started.append(live)
        panels_ready = panels.wait_ready(5)
        live_ready = live.wait_ready(5)
        log(f'SELFTEST threads panels={panels.accelerator} '
            f'panels_ready={str(panels_ready).lower()} '
            f'panels_registered={str(bool(panels.registered)).lower()} '
            f'live={live.accelerator} live_ready={str(live_ready).lower()} '
            f'live_registered={str(bool(live.registered)).lower()} '
            f'probe={str(bool(started)).lower()}')
        if not (panels_ready and live_ready):
            log('SELFTEST broken=um dos threads da hotkey nao subiu')
            log('SELFTEST rc=3')
            shell.request_exit(3, reason='selftest-threads')
            return 3

        def screen():
            """O que a JANELA mede, agora -- nunca a cache `shell.visible`."""
            return (bool(window_visible(shell.hwnd)),
                    str(getattr(shell, 'panel_mode', '') or ''))

        def wait_for(predicate, timeout):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if predicate():
                    return True
                time.sleep(0.01)
            return bool(predicate())

        # QUEM TOMOU O FOCO, E EM QUE PASSO. O show do Alt+C toma o
        # foreground de proposito (`foreground_unlock`: e' o destravar do
        # rato); o HIDE nao tem essa desculpa. Sem rasto por passo o
        # veredicto so' sabe "alguem tomou", e reprova o que a lei manda.
        focus_trace = []

        def note_focus(label, is_show):
            focus_trace.append((label, bool(is_show), foreground_window()))

        def step(thread, predicate, label, window, is_show):
            """UMA pressao pelo caminho de entrega: (posted, seen, ms).

            `posted` e' a prova de ENTREGA (`simulate_press` pos o `WM_HOTKEY`
            na fila, e o `HOTKEY_PRESSED count=N` do log e' esse numero);
            `seen`/`ms` sao a prova de LATENCIA. Duas provas, dois campos --
            fundi-las foi como o teste passou a culpar a entrega de uma
            primeira exibicao lenta (2026-11-01).
            """
            t0 = time.monotonic()
            posted = bool(thread.simulate_press())
            seen = wait_for(predicate, window)
            spent = (time.monotonic() - t0) * 1000.0
            note_focus(label, is_show)
            log(f'SELFTEST step={label} posted={str(posted).lower()} '
                f'seen={str(seen).lower()} screen={screen()} '
                f'latency_ms={spent:.1f} window_s={window:.1f}')
            return posted, seen, spent

        before_focus = foreground_window()
        caption_start = bool(getattr(shell, '_caption_wanted', False))
        shell.hide_panel('selftest-baseline')
        # O PONTO DE PARTIDA E' DECLARADO: o ciclo alterna o show seguinte a
        # partir da ultima superficie APLICADA, por isso um teste que nao a
        # fixasse comecaria num estado que depende do que a app fez antes.
        shell.set_panel_surface('panel', 'selftest-baseline')
        log(f'SELFTEST state=hidden visible={str(screen()[0]).lower()} '
            f'surface={shell.surface_applied} '
            f'caption={str(caption_start).lower()}')

        # ARM 1 -- hidden -> STRIP, caption UNCHANGED. Esta e' a exibicao
        # FRIA: e' ela que paga o primeiro `exec_js` da pagina, e por isso
        # espera a janela grande -- o numero aparece, e o orcamento julga.
        caption_before = bool(getattr(shell, '_caption_wanted', False))
        p1, a1, ms1 = step(panels, lambda: screen() == (True, 'strip'),
                           '1-strip-cold', SELFTEST_COLD_WINDOW_S, True)
        caption_after = bool(getattr(shell, '_caption_wanted', False))
        # ARM 2 -- strip -> HIDDEN.
        p2, a2, ms2 = step(panels, lambda: not screen()[0], '2-hidden',
                           SELFTEST_STEP_WINDOW_S, False)
        # ARM 3 -- hidden -> PANEL.
        p3, a3, ms3 = step(panels, lambda: screen() == (True, 'side'),
                           '3-panel', SELFTEST_STEP_WINDOW_S, True)
        # ARM 4 -- panel -> HIDDEN.
        p4, a4, ms4 = step(panels, lambda: not screen()[0], '4-hidden',
                           SELFTEST_STEP_WINDOW_S, False)
        # ARM 5 -- DEZ pressoes, dez alternancias, NA ORDEM. A tecla fica
        # "em baixo" no unico sentido que a app conhece: nenhum evento de
        # libertacao e' entregue, e o seam de duracao ja' nao existe.
        expected = [(True, 'strip'), (False, 'strip'), (True, 'side'),
                    (False, 'side')] * 2 + [(True, 'strip'), (False, 'strip')]
        observed = []
        ten_posted = True
        ten_changed = True
        ten_ms = []
        for index, want in enumerate(expected):
            t0 = time.monotonic()
            posted = bool(panels.simulate_press())
            # EXPLICITO, PASSO A PASSO. `screen() != anterior` nao serve: o
            # `panel_mode` muda no `set_panel_surface`, antes de a janela
            # mapear, por isso um "mudou" dispara num estado meio-aplicado
            # (medido 2026-11-01 10:21:42.894: a 10a pressao registou
            # `(False,'strip')` no instante em que o modo ja' era 'strip' e a
            # janela ainda nao). Esperar o par EXACTO mede o que ele V~E.
            changed = wait_for(lambda w=want: screen() == w,
                               SELFTEST_PRESS_WINDOW_S)
            ten_ms.append((time.monotonic() - t0) * 1000.0)
            note_focus('5-ten-%d-%s' % (index + 1, 'show' if want[0] else 'hide'),
                       want[0])
            observed.append(screen())
            ten_posted = ten_posted and posted
            ten_changed = ten_changed and changed
        log('SELFTEST arm=5-ten presses=%d alt_held=no-release-event '
            'expected=%s observed=%s latency_ms=%s'
            % (len(observed), expected, observed,
               ','.join('%.1f' % ms for ms in ten_ms)))
        # ARM 6 -- Ctrl+Space: a legenda comuta UMA vez, e nenhum painel se
        # mexe (nem aparece, nem muda de superficie).
        panel_before_live = screen()
        p6, a6, ms6 = step(live, lambda: bool(getattr(shell, '_caption_wanted', False))
                           != caption_before, '6-live', SELFTEST_STEP_WINDOW_S,
                           False)
        caption_live = bool(getattr(shell, '_caption_wanted', False))
        panel_after_live = screen()
        if caption_live != caption_start:
            shell._set_live_enabled({'on': caption_start})
            time.sleep(0.1)

        after_focus = foreground_window()
        after_pid = window_pid(after_focus)
        focus_stolen = before_focus != after_focus
        stolen_by_us = bool(focus_stolen and after_focus
                            and after_pid == os.getpid())
        # O QUE CADA PASSO FEZ AO FOCO. `focus_stolen_by_own_window` e' o
        # total (o numero que o `selftest-focus-oracle` julga); este rasto
        # diz QUAL passo o tomou, e se esse passo era um show (permitido,
        # `foreground_unlock`) ou um hide/tecla da legenda (nao).
        steals, previous = [], before_focus
        for label, is_show, hwnd in focus_trace:
            if hwnd and hwnd != previous and window_pid(hwnd) == os.getpid():
                steals.append((label, is_show))
            previous = hwnd or previous
        bad_steals = [label for label, is_show in steals if not is_show]
        log(f'SELFTEST focus_steals={steals} '
            f'focus_stolen_on_hide={bad_steals}')
        log(f'SELFTEST focus_before={before_focus} focus_after={after_focus} '
            f'focus_stolen={str(focus_stolen).lower()} after_pid={after_pid} '
            f'focus_stolen_by_own_window={str(stolen_by_us).lower()}')
        latencies = [ms for ms in (ms1, ms2, ms3, ms4, ms6) + tuple(ten_ms)
                     if ms is not None]
        worst_ms = max(latencies) if latencies else None
        reading = {
            'registered': bool(panels_ready and live_ready),
            # ENTREGA: so' as pressoes postadas. O estado que cada uma devia
            # ter produzido e' a clausula da arma, e o tempo e' `latency_ms`.
            'pressed': bool(p1 and p2 and p3 and p4 and p6 and ten_posted),
            'expect_presses': 14, 'presses': panels.pressed,
            'latency_ms': worst_ms,
            'latency_budget_ms': SELFTEST_STEP_BUDGET_MS,
            'first_show_ms': ms1,
            'ten_press_latency_ms': ten_ms,
            'seen_all': bool(a1 and a2 and a3 and a4 and a6 and ten_changed),
            'visible': bool(screen()[0]), 'want_visible': False,
            'first_press_strip': a1,
            'second_press_hidden': a2,
            'third_press_panel': a3,
            'fourth_press_hidden': a4,
            'ten_press_alternations': bool(ten_changed and observed == expected),
            'ten_press_observed': observed,
            'live_toggled': a6,
            'live_left_panels': panel_before_live == panel_after_live,
            'live_caption_left_alone': caption_after == caption_before,
            'focus_stolen_by_own_window': stolen_by_us,
            # A UNICA excepcao e' o CURSOR CAPTURADO, e nao "o Alt+C": o
            # show passou a decidir por `pointer_lock_state()` (ver
            # `foreground_unlock`), logo o que esta leitura pode declarar e' so'
            # aquilo que a maquina esta' a medir AGORA. Com o cursor livre a
            # declaracao e' vazia e o `selftest_broken` julga o roubo como
            # sempre julgou -- e' assim que a arm `focus_stolen` voltou a
            # valer alguma coisa.
            'focus_steal_allowed': ('pointer-lock'
                                    if pointer_lock_state()['clipped'] else ''),
            'focus_before': before_focus, 'focus_after': after_focus,
        }
        broken, why = selftest_broken(reading)
        if broken:
            log(f'SELFTEST broken={why}')
        else:
            log('SELFTEST broken=false focus_attributed='
                f'{str(stolen_by_us).lower()}')
        log('SELFTEST expectation=hotkeys(alt_c=one-step-per-press, '
            'ctrl_space=live-caption) delivered=%s presses=%d '
            'panels_registered=%s observed=%s latency_ms=%s '
            'first_show_ms=%.1f first_show_slow=%s budget_ms=%.0f '
            'window_cold_s=%.1f'
            % (str(reading['pressed']).lower(), panels.pressed,
               str(bool(panels.registered)).lower(), observed,
               ','.join('%.1f' % lat for lat in latencies),
               (ms1 or 0.0),
               str(float(ms1 or 0.0) > SELFTEST_STEP_BUDGET_MS).lower(),
               SELFTEST_STEP_BUDGET_MS, SELFTEST_COLD_WINDOW_S))
        rc = 3 if broken else 0
    finally:
        for thread in started:
            try:
                thread.stop()
            except Exception as exc:  # noqa: BLE001 -- sair nao pode falhar
                log(f'HOTKEY_STOP_FAILED role={thread.role} error={exc!r}')
    log(f'SELFTEST rc={rc}')
    shell.request_exit(rc, reason='selftest')


def probe_reload(*, WorkerReloadPolicy, WORKER_RELOAD_MIN_INTERVAL_MS,
                 WORKER_RELOAD_DEBOUNCE_MS):
    """Prove the worker-reload guard against REAL files and a REAL watcher.

    The defect: a settled worker-file change restarted the worker on the spot,
    even mid-stream, so five lanes saving all morning produced a restart storm
    (the "model loading toda hora" the owner saw). Three arms, each able to
    print RED:

      1. GUARD    a capture is open; the worker file is touched N times, spaced
                  wider than the watcher's 250 ms window so each touch WOULD
                  flush. Expect: ZERO restarts during the capture, and exactly
                  ONE worker spawn in total once the stream ends.
      2. STORM    the SAME N touches with the guard and the floor removed (the
                  old behaviour). Expect: N restarts. This is the arm that makes
                  arm 1 mean something — if the storm is not reproducible, the
                  guard is not being tested.
      3. BURST    a tight burst (8 writes in <250 ms) with no capture. Expect:
                  exactly ONE restart (the debounce coalesces it).

    No WebView2, no worker process: the only stand-in is the bridge, which
    exposes the two fields the policy reads (`child`, `is_capturing()`), and the
    `restart` callable, which counts. Everything else is the production classes.
    """
    root = tempfile.mkdtemp(prefix='sotto-reload-')
    panel_dir = os.path.join(root, 'panel')
    worker_dir = os.path.join(root, 'worker')
    os.makedirs(panel_dir)
    os.makedirs(worker_dir)
    worker_py = os.path.join(worker_dir, 'sotto_worker.py')
    with open(worker_py, 'w', encoding='utf-8') as fh:
        fh.write('# seed\n')

    rc = 0

    class StandInBridge:
        """Exactly the surface WorkerReloadPolicy reads, and no more."""

        def __init__(self):
            self.child = object()          # a worker is up
            self.capturing = False
            self.spawned_at = time.monotonic() - 1000.0
            self.spawns = 0

        def is_capturing(self):
            return self.capturing

    def run_arm(debounce_ms, min_interval_ms):
        br = StandInBridge()

        def restart(files):
            br.spawns += 1
            br.spawned_at = time.monotonic()
            return True

        policy = WorkerReloadPolicy(log_fn=print, get_bridge=lambda: br,
                                    restart=restart, debounce_ms=debounce_ms,
                                    min_interval_ms=min_interval_ms)
        hr = hot_reload.HotReload(log=lambda line: None,
                                  on_worker_changed=policy.request,
                                  panel_dir=panel_dir, worker_dir=worker_dir)
        if not hr.start():
            return None, None, None
        return br, policy, hr

    touches = 6

    # ── arm 1: the guard — a capture is open while the file is touched ──────
    # A short 200 ms debounce keeps the arm quick; the GUARD, not the debounce,
    # is what this arm isolates.
    br, policy, hr = run_arm(200, WORKER_RELOAD_MIN_INTERVAL_MS)
    if br is None:
        print('VERDICT arm=guard watchers=0 got=0-1')
        shutil.rmtree(root, ignore_errors=True)
        return 3
    br.capturing = True
    for i in range(touches):
        with open(worker_py, 'a', encoding='utf-8') as fh:
            fh.write(f'# touch {i}\n')
        time.sleep(0.4)                    # > the watcher's 250 ms window
    time.sleep(0.9)                        # let the last flush reach the policy
    during = br.spawns
    print(f'ARM guard touches={touches} restarts_during_capture={during} '
          f'expect=0')
    if during != 0:
        rc = 3
    # the stream ends: the worker exits, then respawns ONCE (the app's own
    # supervisor), which re-reads the file — no second restart is owed.
    br.capturing = False
    br.child = None
    policy.boundary()
    time.sleep(0.9)
    br.child = object()
    br.spawned_at = time.monotonic()
    respawns = 1
    total = br.spawns + respawns
    print(f'ARM guard total_spawns={total} '
          f'(policy_restarts={br.spawns} + boundary_respawn={respawns}) '
          f'expect=1')
    if total != 1:
        rc = 3
    policy.stop()
    hr.stop('arm1')

    # ── arm 2: the storm — the SAME touches with the guard removed ──────────
    br, policy, hr = run_arm(0, 0)
    if br is None:
        print('VERDICT arm=storm watchers=0 got=0-1')
        shutil.rmtree(root, ignore_errors=True)
        return 3
    br.capturing = False                   # pre-fix: no guard existed at all
    for i in range(touches):
        with open(worker_py, 'a', encoding='utf-8') as fh:
            fh.write(f'# storm {i}\n')
        time.sleep(0.4)
    time.sleep(0.9)
    print(f'ARM storm touches={touches} restarts={br.spawns} '
          f'expect={touches}')
    if br.spawns != touches:
        rc = 3
    policy.stop()
    hr.stop('arm2')

    # ── arm 3: the debounce — a tight burst is ONE request ──────────────────
    br, policy, hr = run_arm(WORKER_RELOAD_DEBOUNCE_MS, 0)
    if br is None:
        print('VERDICT arm=burst watchers=0 got=0-1')
        shutil.rmtree(root, ignore_errors=True)
        return 3
    for i in range(8):
        with open(worker_py, 'a', encoding='utf-8') as fh:
            fh.write(f'# burst {i}\n')
        time.sleep(0.03)                   # under the watcher's window
    time.sleep(0.5 + WORKER_RELOAD_DEBOUNCE_MS / 1000.0)
    print(f'ARM burst writes=8 restarts={br.spawns} expect=1 '
          f'debounce_ms={WORKER_RELOAD_DEBOUNCE_MS}')
    if br.spawns != 1:
        rc = 3
    policy.stop()
    hr.stop('arm3')

    shutil.rmtree(root, ignore_errors=True)
    print(f'SELFTEST reload rc={rc}')
    return rc
