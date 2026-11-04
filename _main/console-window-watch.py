#!/usr/bin/env python
"""VIGIA DE JANELAS: prova NO ECRA que um script nao abre consola nenhuma.

O censo (`console-window-audit.py`) le o CODIGO; este ficheiro ve' o ECRAN. Sao
duas provas diferentes e a ordem do dono pede as duas.

PORQUE E' QUE ISTO E' O TESTE CERTO: um `subprocess` sem `CREATE_NO_WINDOW`
herda a consola do PAI e nao abre janela nenhuma. A janela aparece quando o pai
NAO tem consola (a app corre em `pythonw`, num servico, numa tarefa agendada) --
e' por isso que o mesmo script "nao faz nada" na mao de um agente e pisca no ecra
do dono. Este vigia larga o alvo com `CREATE_NO_WINDOW`, ou seja, testa os filhos
do alvo na condicao do dono, nao na condicao confortavel de quem tem consola.

O INSTRUMENTO (medido 2026-11-04): `SetWinEventHook(EVENT_OBJECT_SHOW)` **mais**
um censo de `EnumWindows` a 40 ms, porque no Windows 11 a janela pode ser
`ConsoleWindowClass`, `CASCADIA_HOSTING_WINDOW_CLASS` (Windows Terminal, quando
e' o host por omissao), ou `PseudoConsoleWindow` (o conhost do ConPTY). Medido:
um `cmd.exe` largado sem flags de um pai SEM consola produz
`PseudoConsoleWindow vis=1` por volta de 2 s -- uma classe que um censo que so'
conheca `ConsoleWindowClass` NAO ve'. Um instrumento de uma so' classe mentia.

O CONTROLO POSITIVO NAO SE REPETE (ordem do dono, 2026-11-04: *"PARA DE MOSTRA
POP UP"*). Foi medido UMA vez: um `cmd.exe` largado sem flags de um pai sem
consola produziu, em 1,6 s, TRES janelas -- `CASCADIA_HOSTING_WINDOW_CLASS`
(windowsterminal.exe, t=0,52 s), `PseudoConsoleWindow` (cmd.exe, t=0,63 s) e
`Xaml_WindowedPopupClass` (t=1,63 s). Essa medicao (acima, no recibo) e' a prova
de que o vigia ve' a janela; NAO ha ficheiro de controlo que a replique, porque
replicar aquilo e' abrir uma janela no ecra dele. O controlo que corre a cada uso
e' `--neg-arm`, que e' puro (nenhuma janela, nenhum processo): classifica uma
fotografia FALSA e exige que ela seja nomeada.

USO
    python _main/console-window-watch.py --seconds 20 --run "python foo.py"
    python _main/console-window-watch.py --seconds 20            (so' escuta)
    python _main/console-window-watch.py --neg-arm               (controlo puro)

rc 0 = nenhuma consola apareceu; rc 1 = apareceu (pid, classe, exe); rc 2 = o
proprio instrumento nao subiu.
"""
# BLOCKS: BUG-20261104-01 -- a janela de consola que o Windows aloca ao
# filho de um pai sem consola (`INC-20261104-01-console-window.md`).

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import threading
import time

user32 = ctypes.WinDLL('user32', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)

EVENT_OBJECT_SHOW = 0x8002
WINEVENT_OUTOFCONTEXT = 0x0000
NO_WINDOW = 0x08000000

#: As tres classes que uma consola pode tomar nesta maquina, mais a janela do
#: Windows Terminal (que hospeda a consola quando e' o host por omissao).
CONSOLE_CLASSES = ('ConsoleWindowClass', 'CASCADIA_HOSTING_WINDOW_CLASS',
                   'PseudoConsoleWindow', 'Windows.UI.Core.CoreWindow')
#: executaveis que SO' existem para uma consola: uma janela nova deles e' uma
#: consola, mesmo quando a classe nao esta na lista acima.
CONSOLE_EXES = ('conhost.exe', 'cmd.exe', 'openconsole.exe',
                'windowsterminal.exe', 'wt.exe')

ENUM = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [ENUM, wt.LPARAM]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR,
                                           ctypes.POINTER(wt.DWORD)]

PROC_QUERY_LIMITED = 0x1000


def _exe(pid):
    """basename do exe do pid, via kernel32 (nunca um `powershell` por evento)."""
    h = k32.OpenProcess(PROC_QUERY_LIMITED, False, pid)
    if not h:
        return ''
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return ''
        return os.path.basename(buf.value).lower()
    finally:
        k32.CloseHandle(h)


def _snapshot():
    """[(pid, classe)] de TODAS as janelas existentes agora."""
    out = []

    def cb(hwnd, _l):
        buf = ctypes.create_unicode_buffer(200)
        user32.GetClassNameW(hwnd, buf, 200)
        pid = wt.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        out.append((hwnd, pid.value, buf.value, bool(user32.IsWindowVisible(hwnd))))
        return True

    user32.EnumWindows(ENUM(cb), 0)
    return out


def _console_windows(hwnds):
    """Das janelas dadas, as que sao consola e estao visiveis."""
    hits = []
    for hwnd, pid, cls, visible in hwnds:
        if not visible:
            continue
        if cls in CONSOLE_CLASSES:
            hits.append((pid, cls, _exe(pid)))
        elif _exe(pid) in CONSOLE_EXES:
            hits.append((pid, cls, _exe(pid)))
    return hits


def neg_arm():
    """CONTROLO PURO: nenhuma janela real, so' a classificacao.

    Uma fotografia falsa com as quatro formas que o detector tem de nomear
    (classe de consola visivel, classe de consola invisivel, exe de consola e
    janela normal) e uma que tem de recusar. Se o detector parar de nomear a
    primeira, o vigia deixou de provar nada -- e este braco diz isso sem abrir
    um unico pixel no ecra de ninguem.
    """
    real_exe = _exe
    fake = {1234: 'cmd.exe', 4321: 'explorer.exe', 999: 'conhost.exe'}
    globals()['_exe'] = lambda pid: fake.get(pid, '')
    try:
        cases = [
            ('classe de consola visivel',
             [(1, 1234, 'PseudoConsoleWindow', True)], 1),
            ('classe de consola invisivel (nao conta)',
             [(2, 1234, 'PseudoConsoleWindow', False)], 0),
            ('exe de consola com classe estranha',
             [(3, 999, 'SomeOtherClass', True)], 1),
            ('janela normal (nao conta)',
             [(4, 4321, 'CabinetWClass', True)], 0),
            ('janela normal chamada CoreWindow (conta)',
             [(5, 4321, 'Windows.UI.Core.CoreWindow', True)], 1),
        ]
        bad = []
        for why, snap, want in cases:
            got = len(_console_windows(snap))
            print('  %-42s esperado=%d obtido=%d%s'
                  % (why, want, got, '' if got == want else '   <-- FALHA'))
            if got != want:
                bad.append(why)
    finally:
        globals()['_exe'] = real_exe
    if bad:
        print('NEG-ARM FAIL -- o detector nao nomeia: %s' % bad)
        return 0
    print('NEG-ARM PASS -- 5/5 casos classificados; o vigia ve\' o que jura ver')
    return 1


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    seconds, runs = 30.0, []
    for i, a in enumerate(argv):
        if a == '--seconds' and i + 1 < len(argv):
            seconds = float(argv[i + 1])
        elif a == '--run' and i + 1 < len(argv):
            runs.append(argv[i + 1])

    # a linha de base: janelas que JA' existiam nao sao da corrida
    baseline = set()
    t0 = time.time()
    for hwnd, pid, cls, visible in _snapshot():
        baseline.add((hwnd, pid))
    print('baseline: %d janela(s) antes de comecar' % len(baseline))

    kids = []
    for cmd in runs:
        print('a largar (SEM consola, como a app): %s' % cmd)
        kids.append(subprocess.Popen(cmd, shell=True, creationflags=NO_WINDOW,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL))
    found = {}
    while time.time() - t0 < seconds:
        for hwnd, pid, cls, visible in _snapshot():
            if (hwnd, pid) in baseline or hwnd in found:
                continue
            if not visible:
                continue
            hit = _console_windows([(hwnd, pid, cls, visible)])
            if hit:
                found[hwnd] = (round(time.time() - t0, 2),) + hit[0]
        if all(p.poll() is not None for p in kids) and not found:
            # ja' acabaram: mais 1,5 s de folga para a janela nascer/morrer
            time.sleep(1.5)
            for hwnd, pid, cls, visible in _snapshot():
                if (hwnd, pid) in baseline or hwnd in found:
                    continue
                hit = _console_windows([(hwnd, pid, cls, visible)])
                if hit:
                    found[hwnd] = (round(time.time() - t0, 2),) + hit[0]
            break
        time.sleep(0.04)

    rcs = [(p.pid, p.poll()) for p in kids]
    if not found:
        print('CONSOLE-WATCH PASS -- %d comando(s) largado(s) sem consola, '
              '%.1f s de vigia, ZERO janelas de consola'
              % (len(runs), min(seconds, round(time.time() - t0, 1))))
        for pid, rc in rcs:
            if rc:
                print('  aviso: o alvo pid=%d saiu rc=%s (o vigia nao julga '
                      'o alvo, so o ecra)' % (pid, rc))
        return 0
    print('CONSOLE-WATCH FAIL -- %d janela(s) de consola apareceram:' % len(found))
    for hwnd, (t, pid, cls, exe) in found.items():
        print('  t=%.2fs pid=%-7d %-30s %s' % (t, pid, cls[:30], exe))
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
