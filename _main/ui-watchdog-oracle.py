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
TIMEOUT_MS = 6000           # igual ao detector (UI_WATCHDOG_TIMEOUT_MS=6000)


def ui_responds(hwnd, timeout_ms=TIMEOUT_MS):
    """A MESMA pergunta do cao-de-guarda, com as MESMAS flags.

    Devolve `(respondeu, err)`: o `err` e' o que separa "a janela nao
    respondeu porque estourou o prazo" (`1460`) de "a chamada nao reportou
    nada" (`0`). A app matou-se as 06:57:25 por tratar os dois como iguais.
    """
    if not hwnd:
        return False, -1
    result = ctypes.c_size_t(0)
    ctypes.set_last_error(0)
    got = send(ctypes.c_void_p(int(hwnd)), WM_NULL, 0, 0,
               SMTO_ABORTIFHUNG, int(timeout_ms), ctypes.byref(result))
    return bool(got), ctypes.get_last_error()


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
    got, err = ui_responds(hwnd)
    dt = time.time() - t0
    stop_event.set()
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)  # WM_CLOSE
    ok = bool(got) == esperado
    print('  %-20s hwnd=%-9s respondeu=%-5s err=%-5s esperado=%-5s %6.2fs  %s'
          % (nome, hwnd, got, err, esperado, dt, 'ok' if ok else 'ERRADO'))
    ERRORS[nome] = err
    return ok


holder = {}
ready = threading.Event()
ERRORS = {}

print('UI-WATCHDOG-ORACLE -- a mesma chamada do detector, 3 bracos de janela')
resultados = [
    arm('janela saudavel', True, True),
    arm('janela congelada', False, False),
]
got_zero, err_zero = ui_responds(0)
ok_zero = got_zero is False
print('  %-20s hwnd=0       respondeu=%-5s err=%-5s esperado=False   %s'
      % ('sem janela (0)', got_zero, err_zero, 'ok' if ok_zero else 'ERRADO'))
resultados.append(ok_zero)

ok = all(resultados)
# ── A POLITICA: quando uma amostra conta como golpe ──────────────────────────
# A chamada ao Windows so' diz `got`/`err`; QUEM decide que isso e' um golpe e'
# `app/webview/ui_watchdog_policy.py`, e essa decisao era o defeito: as 06:57:25
# a app saiu com tres amostras `err=0` enquanto pintava legenda. Estes bracos
# alimentam a FUNCAO REAL que a shell corre.
import importlib.util
import os
import shutil
import tempfile


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


POLICY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'app', 'webview', 'ui_watchdog_policy.py')
P = _load(POLICY, 'ui_watchdog_policy_under_test')
BUDGET = 5.0 + TIMEOUT_MS / 1000.0   # poll + prazo, como no laco


def policy_arm(nome, samples, esperado_acts, mod=P):
    st = mod.State(3)
    acts = [mod.feed(st, mod.classify(g, e, t, BUDGET)) for g, e, t in samples]
    ok = acts == esperado_acts
    print('  %-30s %-42s %s' % (nome, acts, 'ok' if ok else 'ERRADO'))
    return ok


def owner_case(mod=P):
    """Tres `err=0` como os MEDIDOS no log do dono: NAO pode sair."""
    return policy_arm('tres err=0 -> nao sai (dono)',
                      [(0, 0, 6.0)] * 3, ['wait'] * 3, mod)


def frozen_case(mod=P):
    """O congelamento medido por este orgao (`err=1460`): sai a terceira."""
    return policy_arm('tres err=1460 -> confirm',
                      [(0, 1460, 6.0)] * 3, ['wait', 'wait', 'confirm'], mod)


def starved_case(mod=P):
    """O laco que levou 20,3 s com orcamento de 11 s nao vale golpe."""
    st = mod.State(3)
    mod.feed(st, 'strike')
    mod.feed(st, 'strike')
    kind = mod.classify(0, 1460, 20.3, BUDGET)
    act = mod.feed(st, kind)
    ok = kind == 'starved' and act == 'wait' and st.strikes == 0
    print('  %-30s kind=%-38s %s' % ('laco de 20,3 s', kind,
                                     'ok' if ok else 'ERRADO'))
    return ok


def confirm_case(mod=P):
    """A volta de confirmacao: so' a assinatura manda sair.

    Medido (`SendMessageTimeoutW` num hwnd bogus): `got=0 err=1400`. Uma janela
    recriada nunca responde, e sair por ela mataria a app por um hwnd morto.
    """
    st = mod.State(3)
    acts = (mod.confirm(st, 'strike'), mod.confirm(st, 'noerr'),
            mod.confirm(st, 'answered'))
    ok = acts == ('exit', 'wait', 'wait')
    print('  %-30s %-41s %s' % ('confirmacao exige a assinatura', str(acts),
                                 'ok' if ok else 'ERRADO'))
    return ok


def cap_case(mod=P):
    """O TECTO: sem assinatura, so' a decima segunda volta manda sair.

    Impede o outro extremo: uma janela que nunca responde ficaria no ecra para
    sempre se a app exigisse `ERROR_TIMEOUT` para sair.
    """
    st = mod.State(3)
    for _ in range(11):
        mod.feed(st, 'noerr')
    before = mod.hard_cap(st)
    mod.feed(st, 'noerr')
    ok = (not before) and mod.hard_cap(st)
    print('  %-30s %-41s %s' % ('teco: 11 nao, 12 sim', str(before),
                                 'ok' if ok else 'ERRADO'))
    return ok


# o contracto entre o orgao e a app: o erro que ESTE orgao mediu numa janela
# presa de verdade tem de ser o que a politica aceita como golpe
ok_sig = (ERRORS.get('janela congelada') == P.ERROR_TIMEOUT)
print('  %-30s janela=%-5s politica=%-5s %s'
      % ('assinatura de congelamento', ERRORS.get('janela congelada'),
         P.ERROR_TIMEOUT, 'ok' if ok_sig else 'ERRADO'))

resultados += [owner_case(), frozen_case(), starved_case(), confirm_case(),
               cap_case(), ok_sig]


# ── O BRACO NEGATIVO: mutar a POLITICA e exigir que os bracos caiam ──────────
def neg_arm():
    anchor_err = "return 'strike' if err == ERROR_TIMEOUT else 'noerr'"
    anchor_starve = ("if budget_s > 0 and took_s > budget_s * STARVE_FACTOR:")
    anchor_confirm = "    if kind == 'strike':\n        return 'exit'"
    muts = [
        ('M1 qualquer got=0 conta', anchor_err, "return 'strike'"),
        ('M2 sem guarda de esfomeamento', anchor_starve, 'if False:'),
        ('M3 confirmacao deixa sair', anchor_confirm,
         "    if kind != 'answered':\n        return 'exit'"),
        ('M4 tecto desarmado', 'return state.noerr >= NOERR_HARD_CAP',
         'return False'),
    ]
    with open(POLICY, encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    caught = 0
    tmpdir = tempfile.mkdtemp(prefix='wdpolicy-neg-')
    try:
        for i, (nome, old, new) in enumerate(muts):
            if old not in text:
                print('  %-30s ANCORA AUSENTE -- mutante nao aplicado' % nome)
                continue
            d = os.path.join(tmpdir, 'm%d' % i)
            os.makedirs(d, exist_ok=True)
            mp = os.path.join(d, 'ui_watchdog_policy.py')
            with open(mp, 'w', encoding='utf-8', newline='') as fh:
                fh.write(text.replace(old, new))
            M = _load(mp, 'wd_mutant_%d' % i)
            fell = []
            for label, fn in (('dono', owner_case), ('congelado', frozen_case),
                              ('esfomeado', starved_case),
                              ('confirmacao', confirm_case),
                              ('teco', cap_case)):
                try:
                    if not fn(M):
                        fell.append(label)
                except Exception:            # noqa: BLE001
                    fell.append(label + '(exc)')
            ok = bool(fell)
            caught += 1 if ok else 0
            print('  %-30s caiu=%-28s %s' % (nome, ','.join(fell) or '-',
                                             'ok' if ok else 'ERRADO'))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return caught, len(muts)


print('-- braco negativo (mutantes da politica)')
caught, total = neg_arm()
ok_neg = caught == total
print('  %-30s %d/%d %s' % ('mutantes apanhados', caught, total,
                            'ok' if ok_neg else 'ERRADO'))
ok = ok and ok_neg
print('UI-WATCHDOG-ORACLE %s -- %d/%d bracos, neg-arm %d/%d'
      % ('PASS' if ok else 'FAIL', sum(1 for r in resultados if r),
         len(resultados), caught, total))
if ok_neg:
    print('NEG-ARM: PASS (%d/%d mutantes caidos)' % (caught, total))
else:
    print('NEG-ARM: FAIL (a politica aceita um mutante)')
# A CONVENCAO DA BATERIA (2026-11-03): o passo `red-as-expected-*` declara
# `:expectred` e exige rc=1. "Apanhei todos os mutantes" E' o resultado
# VERMELHO esperado; rc=0 quando um escapa (o passo fica vermelho de verdade).
if '--neg-arm' in sys.argv:
    sys.exit(1 if ok_neg else 0)
sys.exit(0 if ok else 1)
