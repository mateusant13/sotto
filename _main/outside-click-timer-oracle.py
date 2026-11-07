#!/usr/bin/env python3
"""O vigia de clique-fora NAO gira -- o timer dele e' de 10 Hz, nao de 1 600.

O QUE ELE MEDE, E POR QUE NAO E' UM TESTE DE ESTILO (2026-11-07, ordem do dono
sobre o stutter: *"é pra sempre verificar o maior culpado do stutter"*):

  `OutsideClickWatcher` chamava `_restart_timer()` em CADA `WM_TIMER`, e
  `_restart_timer` fazia `KillTimer` + `SetTimer` com o MESMO id. Re-armar um
  timer de thread dentro do seu proprio handler DEGENERA-o. Medido nesta caixa:

    SetTimer pedido uma vez .............................   9 Hz
    KillTimer+SetTimer a cada tick (o primitivo) ........ 2 064 Hz
    a CLASSE real a correr .............................. 1 591 Hz / 13,1 % de um core
    `THREAD_CPU` da instancia viva (`sotto-outside-click`) .  14-27 % de um core

  13-27 % de um core a girar numa maquina a 98 % e' pressao de escalonador com
  o dono a esperar -- e era o unico custo daquele vigia que nao era trabalho.

AS ARMS (todas correm a CLASSE REAL, nunca uma copia do laco):

  A1 primitivo: um `SetTimer` so' dispara 6-14 vezes em 3 s (esperado ~9 Hz).
  A2 primitivo: o re-arme a cada tick TEM de degenerar (>200 Hz) -- sem esta
     arm o A1 nao prova nada sobre a causa, so' sobre o relogio.
  A3 classe real: 10 s armada => ticks entre 6 e 14 Hz (o desenho e' 10 Hz).
  A4 classe real: CPU da thread < 2 % de um core (medido, `GetThreadTimes`).
  A5 classe real: `KillTimer`+`SetTimer` <= 1 por segundo (o memo).
  A6 classe real: desarmar MATA o tick (0 ticks em 2 s depois de `armed=False`).
  A7 classe real: editar o intervalo (100 ms -> 25 ms do arrasto) RE-ARMA --
     o memo nao pode transformar a cura numa mordaca.

`--neg-arm` poe de volta o re-arme a cada tick numa COPIA de
`app/webview/sotto_webview.py` e exige A3/A4/A5 VERMELHAS. rc=1 quando apanha.
Sem `--neg-arm`: rc=0 so' com as sete verdes, rc=1 caso contrario.

NADA AQUI ABRE JANELA: a classe corre com `window_visible` fixado em True (o
caso do dono com o painel a vista) e a shell falsa responde ao `hwnd`. Nenhum
audio, nenhum processo filho, nenhuma app.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import re
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WM_TIMER = 0x0113
WM_QUIT = 0x0012
TIMER_ID = 0x5150

k32 = ctypes.windll.kernel32


def _thread_cpu(ident):
    """(kernel, user) em unidades de 100 ns para UMA thread."""
    h = k32.OpenThread(0x0800, False, int(ident))     # QUERY_LIMITED
    if not h:
        return None
    try:
        c, e, k, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
        if not k32.GetThreadTimes(h, ctypes.byref(c), ctypes.byref(e),
                                  ctypes.byref(k), ctypes.byref(u)):
            return None
        ft = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime   # noqa: E731
        return ft(k), ft(u)
    finally:
        k32.CloseHandle(h)


def _primitive(restart_each_tick, seconds=3.0):
    """UM timer de thread, com e sem o re-arme a cada tick. Devolve Hz."""
    hits = [0]
    ready = threading.Event()
    tid = [0]

    def loop():
        tid[0] = k32.GetCurrentThreadId()
        u = ctypes.windll.user32
        u.SetTimer(None, TIMER_ID, 100, None)
        ready.set()
        msg = wt.MSG()
        t0 = time.time()
        while time.time() - t0 < seconds:
            if u.GetMessageW(ctypes.byref(msg), None, 0, 0) <= 0:
                break
            if msg.message == WM_TIMER:
                hits[0] += 1
                if restart_each_tick:
                    u.KillTimer(None, TIMER_ID)
                    u.SetTimer(None, TIMER_ID, 100, None)
        u.KillTimer(None, TIMER_ID)
        u.PostThreadMessageW(tid[0], WM_QUIT, 0, 0)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    ready.wait(2.0)
    t.join(seconds + 3.0)
    return hits[0] / seconds


def _load_shell(path=None):
    """Importa o `sotto_webview` de `path` (ou do repo) como modulo proprio."""
    import importlib.util
    target = path or SHELL
    # Os IRMAOS (`hot_reload`, `youtube_cdp_source`, ...) vem sempre da arvore
    # do repo: o mutante e' so' o ficheiro em teste, nao um segundo pacote.
    here = os.path.dirname(os.path.abspath(SHELL))
    if here not in sys.path:
        sys.path.insert(0, here)
    name = 'shell_under_test_%d' % (len(sys.argv) + int(time.time() * 1000))
    spec = importlib.util.spec_from_file_location(name, os.path.abspath(target))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeShell:
    """O minimo que `_poll` toca. NENHUMA janela: `window_visible` e' fixado."""
    def __init__(self):
        self.hwnd = 0x1234
        self.exiting = threading.Event()
        self.hidden = []

    def hide_panel(self, why):
        self.hidden.append(why)


def _run_watcher(shell, seconds, arm_at=0.4, edit_s=None):
    """Corre a CLASSE real em TRES fases e devolve os numeros de cada uma.

    FASE 1 (a que julga a cura): armada, intervalo de 100 ms do desenho.
    FASE 2 (so' se `edit_s`): `edit_mode` leva o intervalo a 25 ms -- TEM de
    re-armar UMA vez, e depois correr a 40 Hz sem voltar a tocar no timer.
    FASE 3: desarmar TEM de matar o tick.

    O QUE CONTA COMO RE-ARME: a transicao do memo `_timer_ms`, nao a chamada de
    `_restart_timer` -- ele corre em cada tick por desenho.
    """
    shell.window_visible = lambda hwnd: True     # o painel esta' a vista
    w = shell.OutsideClickWatcher(FakeShell())
    rearms = [0]
    # CONTA-SE A CHAMADA REAL, nao a transicao do memo: um mutante que zere o
    # memo ANTES de re-armar (o que o `--neg-arm` planta) nao muda o valor
    # final e passaria despercebido a uma contagem por transicao.
    u32 = shell.user32
    real_set = u32.SetTimer

    def counting_set(hwnd, tid, ms, proc):
        rearms[0] += 1
        return real_set(hwnd, tid, ms, proc)

    u32.SetTimer = counting_set
    ticks = [0]
    real_poll = w._poll

    def counting_poll():
        ticks[0] += 1
        return real_poll()

    w._poll = counting_poll
    w.start()
    time.sleep(arm_at)                     # a fila de mensagens nasce no GetMessageW
    dbg = {}
    w.armed = True
    cpu0, t0, ticks0, rearms0 = _thread_cpu(w.ident), time.time(), ticks[0], rearms[0]
    time.sleep(seconds)
    span1 = time.time() - t0
    cpu1 = _thread_cpu(w.ident)
    hz1 = (ticks[0] - ticks0) / span1
    rearm1 = (rearms[0] - rearms0) / span1
    cpu = 0.0
    if cpu0 and cpu1:
        cpu = ((cpu1[0] - cpu0[0]) + (cpu1[1] - cpu0[1])) / 1e7 / span1 * 100.0
    if edit_s:
        w.edit_mode = True                 # 100 ms -> 25 ms
        dbg['edit_rearms_pre'] = rearms[0]
        time.sleep(edit_s)
        dbg['edit_rearms'] = rearms[0] - dbg['edit_rearms_pre']
        dbg['edit_ticks'] = ticks[0]
    before_disarm = ticks[0]
    w.armed = False
    w.edit_mode = False
    # Os DOIS setters postam um `WM_TIMER` cada (e' o pedido de re-ritmo desta
    # thread, e cada pedido corre um `_poll`: um despertar, nao um ciclo). Drena-
    # se esse par primeiro -- o que se mede a seguir e' a fila VAZIA.
    time.sleep(0.4)
    quiet_from = ticks[0]
    time.sleep(1.2)
    dbg['after_disarm'] = ticks[0] - quiet_from
    dbg['disarm_wakeups'] = quiet_from - before_disarm
    w.stop('oracle')
    return (hz1, cpu, rearm1, ticks[0], dbg)


def judge(measured, ceiling_hz=14.0, floor_hz=6.0, cpu_max=2.0, resets_max=1.0):
    hz, cpu, resets, ticks, dbg = measured
    arms = []
    ok_rate = floor_hz <= hz <= ceiling_hz
    arms.append(('A3 taxa', 'PASS' if ok_rate else 'FAIL',
                 '%.1f Hz (esperado %.0f-%.0f)' % (hz, floor_hz, ceiling_hz)))
    arms.append(('A4 cpu', 'PASS' if cpu < cpu_max else 'FAIL',
                 '%.2f %% de um core (tecto %.1f)' % (cpu, cpu_max)))
    arms.append(('A5 re-armes', 'PASS' if resets <= resets_max else 'FAIL',
                 '%.1f re-arme(s)/s (tecto %.0f)' % (resets, resets_max)))
    arms.append(('A6 desarmar', 'PASS' if dbg.get('after_disarm', 1) == 0 else 'FAIL',
                 '%d tick(s) depois de armed=False (esperado 0)'
                 % dbg.get('after_disarm', -1)))
    if 'edit_rearms' in dbg:
        one = dbg['edit_rearms'] == 1
        arms.append(('A7 intervalo', 'PASS' if one else 'FAIL',
                     'edit_mode re-armou %d vez(es) (esperado 1: o memo nao e mordaca)'
                     % dbg['edit_rearms']))
    return arms


def _primitive_arms():
    plain = _primitive(False)
    spin = _primitive(True)
    arms = [
        ('A1 primitivo', 'PASS' if 6.0 <= plain <= 14.0 else 'FAIL',
         '%.1f Hz com SetTimer unico (esperado ~9)' % plain),
        ('A2 causa', 'PASS' if spin > 200.0 else 'FAIL',
         '%.0f Hz com re-arme a cada tick (>200 prova a causa)' % spin),
    ]
    return arms, plain, spin


def _mutate(path, out):
    """Repoe o re-arme a cada tick numa COPIA (o braco negativo)."""
    src = open(path, encoding='utf-8').read()
    patched, n = re.subn(
        r'( *)want = int\(self\._interval_ms\(\)\) if self\._wants_poll\(\) else 0\n',
        r'\1want = int(self._interval_ms()) if self._wants_poll() else 0\n'
        r'\1self._timer_ms = 0            # MUTANTE: esquece o memo\n', src)
    if n != 1:
        print('MUTANTE IMPOSSIVEL: ancora do memo nao encontrada (%d)' % n)
        return False
    open(out, 'w', encoding='utf-8', newline='').write(patched)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--seconds', type=float, default=10.0)
    args = ap.parse_args()

    prim_arms, plain, spin = _primitive_arms()
    for name, verdict, note in prim_arms:
        print('%-14s %-5s %s' % (name, verdict, note))

    if not args.neg_arm:
        shell = _load_shell()
        measured = _run_watcher(shell, args.seconds, edit_s=1.0)
        arms = prim_arms + judge(measured)
    else:
        tmp = os.path.join(tempfile.mkdtemp(prefix='sotto-negarm-'), 'sotto_webview.py')
        if not _mutate(SHELL, tmp):
            return 2
        try:
            shell = _load_shell(tmp)
            measured = _run_watcher(shell, args.seconds, edit_s=1.0)
            arms = prim_arms + judge(measured)
        finally:
            shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)

    bad = [a for a in arms if a[1] != 'PASS']
    for name, verdict, note in arms:
        print('%-14s %-5s %s' % (name, verdict, note))

    if args.neg_arm:
        # convencao da casa: o negativo devolve 1 QUANDO APANHA o mutante
        caught = [a[0] for a in bad]
        need = {'A3 taxa', 'A4 cpu', 'A5 re-armes', 'A6 desarmar'}
        if need & set(caught):
            print('NEG-ARM: PASS -- mutante apanhado por %s' % ', '.join(sorted(caught)))
            return 1
        print('NEG-ARM: FAIL -- o mutante passou (%d falha(s): %s)'
              % (len(bad), ', '.join(caught) or 'nenhuma'))
        return 0

    if bad:
        print('OUTSIDE-CLICK-TIMER VERDICT: FAIL (%d/%d)' % (len(bad), len(arms)))
        return 1
    print('OUTSIDE-CLICK-TIMER VERDICT: PASS (%d/%d)' % (len(arms), len(arms)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
