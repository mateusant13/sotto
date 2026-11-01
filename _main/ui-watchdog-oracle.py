#!/usr/bin/env python.exe
# -*- coding: utf-8 -*-
# NO-BUG: e o portao do detector `_start_ui_watchdog` (sotto_webview.py), nao uma correccao
"""UI-WATCHDOG-ORACLE -- prova que o detector de "a UI nao responde" detecta.

O detector do `sotto_webview.py` faz UMA pergunta ao Windows:

    SendMessageTimeoutW(hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, 4000ms)

e trata "nao voltou" como "a thread de UI esta presa". Este orgao exercita
exactamente essa chamada, com as mesmas flags e o mesmo orcamento, contra
janelas cujo estado nos CONTROLAMOS:

  1. janela SAUDAVEL   -- thread com `GetMessageW` a bombear        -> tem de responder
  2. janela CONGELADA  -- a mesma janela, thread a dormir sem bombear -> NAO pode responder
  3. hwnd invalido     -- 0                                        -> NAO pode responder

O braco 2 e o que importa: sem ele, o orgao so provava que a funcao devolve
alguma coisa. Foi escrito porque o dono exigiu, verbatim: *"nao deve travar
nunca. faça isso acontecer"* -- e um detector por testar nao e uma garantia.

    python _main\\ui-watchdog-oracle.py     # rc=0 PASS, rc=1 FAIL
"""
import ctypes
import ctypes.wintypes as wt
import sys
import threading
import time

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

send = user32.SendMessageTimeoutW
send.restype = ctypes.c_size_t
send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t,
                 ctypes.c_ssize_t, ctypes.c_uint, ctypes.c_uint,
                 ctypes.POINTER(ctypes.c_size_t)]

SMTO_ABORTIFHUNG = 0x0002   # igual ao detector
WM_NULL = 0x0000            # igual ao detector
TIMEOUT_MS = 4000           # igual ao detector


def ui_responds(hwnd, timeout_ms=TIMEOUT_MS):
    """A MESMA pergunta do cao-de-guarda, com as MESMAS flags."""
    if not hwnd:
        return False
    result = ctypes.c_size_t(0)
    got = send(ctypes.c_void_p(int(hwnd)), WM_NULL, 0, 0,
               SMTO_ABORTIFHUNG, int(timeout_ms), ctypes.byref(result))
    return bool(got)


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT,
                            wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    """`ctypes.wintypes` nao traz WNDCLASSW; a definicao e esta."""
    _fields_ = [('style', wt.UINT),
                ('lpfnWndProc', WNDPROC),
                ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int),
                ('hInstance', wt.HINSTANCE),
                ('hIcon', wt.HICON),
                ('hCursor', wt.HANDLE),
                ('hbrBackground', wt.HBRUSH),
                ('lpszMenuName', wt.LPCWSTR),
                ('lpszClassName', wt.LPCWSTR)]


_KEEPALIVE = []   # as WNDPROC tem de sobreviver ao registo da classe

user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [ctypes.c_void_p, wt.UINT,
                                  ctypes.c_size_t, ctypes.c_ssize_t]


def _proc(h, m, w, l):
    return user32.DefWindowProcW(ctypes.c_void_p(h), m, w, l)


def make_window(stop_event, pump):
    """Cria uma janela nesta thread; se `pump`, bombeia mensagens."""
    hinst = kernel32.GetModuleHandleW(None)
    cls = 'SottoWatchdogOracle%d' % id(stop_event)
    wc = WNDCLASSW()
    proc = WNDPROC(_proc)
    _KEEPALIVE.append(proc)
    wc.lpfnWndProc = proc
    wc.hInstance = hinst
    wc.lpszClassName = cls
    user32.RegisterClassW(ctypes.byref(wc))
    hwnd = user32.CreateWindowExW(0, cls, 'oracle', 0, 0, 0, 0, 0,
                                  None, None, hinst, None)
    if not hwnd:
        raise SystemExit('CreateWindowExW falhou: %s' % ctypes.get_last_error())
    holder['hwnd'] = int(hwnd)
    ready.set()
    if pump:
        msg = wt.MSG()
        while not stop_event.is_set():
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)
    else:
        # A janela EXISTE e esta nesta thread, mas ninguem bombeia: e isto que
        # uma UI presa e, do ponto de vista do Windows.
        stop_event.wait()


def arm(nome, pump, esperado):
    stop_event = threading.Event()
    ready.clear()
    holder.pop('hwnd', None)
    t = threading.Thread(target=make_window, args=(stop_event, pump), daemon=True)
    t.start()
    if not ready.wait(5.0) or 'hwnd' not in holder:
        print('  %-20s NAO CRIOU A JANELA' % nome)
        return False
    hwnd = holder['hwnd']
    t0 = time.time()
    got = ui_responds(hwnd)
    dt = time.time() - t0
    stop_event.set()
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)  # WM_CLOSE
    ok = got == esperado
    print('  %-20s hwnd=%-9s respondeu=%-5s esperado=%-5s %6.2fs  %s'
          % (nome, hwnd, got, esperado, dt, 'ok' if ok else 'ERRADO'))
    return ok


holder = {}
ready = threading.Event()

print('UI-WATCHDOG-ORACLE -- a mesma chamada do detector, 3 bracos')
resultados = [
    arm('janela saudavel', True, True),
    arm('janela congelada', False, False),
]
got_zero = ui_responds(0)
ok_zero = got_zero is False
print('  %-20s hwnd=0       respondeu=%-5s esperado=False   %s'
      % ('sem janela (0)', got_zero, 'ok' if ok_zero else 'ERRADO'))
resultados.append(ok_zero)

ok = all(resultados)
print('UI-WATCHDOG-ORACLE %s -- %d/%d bracos'
      % ('PASS' if ok else 'FAIL', sum(1 for r in resultados if r), len(resultados)))
sys.exit(0 if ok else 1)
