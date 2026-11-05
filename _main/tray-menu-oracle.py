# NO-BUG: Does the tray icon behave like every other tray app on this box?
"""Does the tray icon behave like every other tray app on this box?

OWNER, 2026-11-04, verbatim: *"icone do sotto e' uma merda de mexer. botao direito e'
travado pra abrir o menu dele. e' extremamente diferente de outros apps onde e' fluido.
tipo o vanguard."*

THE DEFECT CLASS. A notification-area icon hosts a POPUP MENU. Three things make that
menu feel stuck instead of fluid, and all three were true of this tray:

  1. The window it lives on was created as `HWND_MESSAGE`. A message-only window has no
     Z-order and cannot be activated, so `SetForegroundWindow` -- the call that lets the
     menu dismiss when the owner clicks anywhere else -- cannot take effect, and the menu
     is left standing until he clicks the icon again.
  2. The MSDN shell-notification recipe is THREE parts: `SetForegroundWindow`, then
     `PostMessage(hwnd, WM_NULL, 0, 0)`, then `TrackPopupMenu`. The middle call is the one
     that stops the first outside click from being eaten by the window coming to the
     front; without it the menu needs a SECOND click to close.
  3. Both buttons opened the menu, so a left click -- the gesture that opens the app in
     every other tray app -- did nothing but show a menu.

WHAT THIS FILE MEASURES. It drives the REAL `TrayIcon` class out of
`app/webview/sotto_webview.py` (imported headless, the way `_redux-visibility-probe.py`
does), creates its REAL window, and dispatches REAL messages into its REAL handler. The
menu draw itself is exercised with `TrackPopupMenu` replaced by a recorder, because the
real one is modal and would block an oracle forever; the recorder sees the exact call
ORDER and arguments the real one would receive.

IT PUTS NOTHING ON THE OWNER'S SCREEN: no `start()`, so no icon is added to his taskbar,
and the window is created without `WS_VISIBLE` (`IsWindowVisible` is asserted to be 0).

  python _main/tray-menu-oracle.py            # positive arms
  python _main/tray-menu-oracle.py --neg-arm  # mutants must be caught (rc=1 when they are)
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import re
import sys
import threading
import time

SHELL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                         'app', 'webview')
SHELL = os.path.join(SHELL_DIR, 'sotto_webview.py')

GA_PARENT = 1
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW = 0x00000080
WS_VISIBLE = 0x10000000

user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.GetAncestor.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, ctypes.c_uint]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.DestroyWindow.argtypes = [wt.HWND]
user32.PeekMessageW.restype = wt.BOOL
user32.PeekMessageW.argtypes = [ctypes.c_void_p, wt.HWND, ctypes.c_uint,
                                ctypes.c_uint, ctypes.c_uint]


def num(value) -> int:
    """A ctypes handle or an int, as an int. `c_void_p.value` can be bytes."""
    raw = getattr(value, 'value', value)
    if isinstance(raw, (bytes, bytearray)):
        return int.from_bytes(raw, 'little')
    return int(raw or 0)


def load(module_path=None):
    """The REAL shell module, imported headless, by path."""
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    if module_path is None:
        import sotto_webview as shell  # noqa: PLC0415
        return shell
    import importlib.util  # noqa: PLC0415
    spec = importlib.util.spec_from_file_location('shell_under_test',
                                                  module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['shell_under_test'] = mod
    spec.loader.exec_module(mod)
    return mod


def exstyle(hwnd, win):
    try:
        return int(win.GetWindowLongPtrW(wt.HWND(hwnd), GWL_EXSTYLE))
    except Exception:  # noqa: BLE001 -- 32-bit build falls back to the W call
        return int(win.GetWindowLongW(wt.HWND(hwnd), GWL_EXSTYLE))


def style(hwnd, win):
    try:
        return int(win.GetWindowLongPtrW(wt.HWND(hwnd), GWL_STYLE))
    except Exception:  # noqa: BLE001
        return int(win.GetWindowLongW(wt.HWND(hwnd), GWL_STYLE))


def drain(hwnd, win):
    """Every WM_COMMAND already posted to `hwnd`, as (id, wparam) tuples."""
    seen = []
    msg = wt.MSG()
    while win.PeekMessageW(ctypes.byref(msg), wt.HWND(hwnd), 0x0111, 0x0111, 1):
        seen.append((int(msg.message), int(msg.wParam)))
        win.TranslateMessage(ctypes.byref(msg))
        win.DispatchMessageW(ctypes.byref(msg))
    return seen


class Seam:
    """The one injected seam: the four user32 calls `_show_menu` makes.

    `TrackPopupMenu` is modal in reality (it owns the mouse until the owner picks
    something), so it is replaced by a recorder. The other three are wrapped, not
    replaced, so the real `SetForegroundWindow`/`PostMessageW` still happen and the
    ORDER they are called in is what the arm judges.
    """

    def __init__(self, shell):
        self.shell = shell
        self.calls = []
        self._saved = {}

    def __enter__(self):
        u = self.shell.user32
        self._saved['TrackPopupMenu'] = u.TrackPopupMenu
        self._saved['SetForegroundWindow'] = u.SetForegroundWindow
        self._saved['PostMessageW'] = u.PostMessageW

        real_fg = self._saved['SetForegroundWindow']
        real_post = self._saved['PostMessageW']

        def track(menu, flags, x, y, reserved, owner, rect):
            self.calls.append(('TrackPopupMenu', int(flags), int(x), int(y),
                               num(owner)))
            return 0

        def foreground(hwnd):
            ok = real_fg(hwnd)
            self.calls.append(('SetForegroundWindow', num(hwnd), int(ok)))
            return ok

        def post(hwnd, msg, wparam, lparam):
            self.calls.append(('PostMessageW', int(msg), num(hwnd),
                               num(wparam)))
            return real_post(hwnd, msg, wparam, lparam)

        u.TrackPopupMenu = track
        u.SetForegroundWindow = foreground
        u.PostMessageW = post
        return self

    def __exit__(self, *exc):
        u = self.shell.user32
        for name, fn in self._saved.items():
            setattr(u, name, fn)
        return False


def judge(shell) -> list:
    """Every arm, against the module under test. Returns [(name, ok, detail)]."""
    checks = []
    logs = []

    def log(line):
        logs.append(line)

    def warn(line):
        logs.append('WARN ' + line)

    tray = shell.TrayIcon(icon_path=None, on_command=lambda c: None,
                          log_fn=log, warn_fn=warn)
    tray._create_window()
    hwnd = tray.hwnd
    # THE MODAL MENU IS PATCHED FOR THE WHOLE BODY, not just for arm 5.
    # `TrackPopupMenu` owns the mouse until something is picked, so a mutant that
    # sends a LEFT click down the menu path would hang this oracle forever --
    # measured: the first version of this file hung on exactly that mutant. One
    # seam for the whole run, and every menu draw is recorded, in order.
    seam = Seam(shell)
    seam.__enter__()
    try:
        checks.append(('window_created', bool(hwnd) and bool(
            user32.GetAncestor(wt.HWND(hwnd), GA_PARENT)) or False,
            f'hwnd={hwnd}'))

        # ARMS 12-13 -- O ICONE COM A MAQUINA ESGOTADA (dono, 2026-11-05:
        # *"make the interaction with the icon better, cause it does not work when
        # my pc is close to exhausted. but other icones, do"*). A segunda metade
        # da frase e' o diagnostico: os outros icones sao de processos `NORMAL` e
        # respondem. Este fio dorme num `GetMessageW` e por isso pode subir a
        # `ABOVE_NORMAL` sem roubar CPU a ninguem.
        #
        # ARM 12 le o VALOR que o fio do icone realmente corre, de fora, com o
        # handle do fio -- nao a presenca de uma linha de codigo.
        prio = {'value': None, 'log': ''}
        started = threading.Event()

        def _probe_priority():
            got = tray._raise_thread_priority()
            prio['value'] = got
            prio['log'] = logs[-1] if logs else ''
            started.set()

        th = threading.Thread(target=_probe_priority, name='oracle-prio', daemon=True)
        th.start()
        started.wait(2.0)
        th.join(1.0)
        checks.append(('tray_thread_priority_raised', prio['value'] == 1,
                       'now=%r (1 = ABOVE_NORMAL) log=%r' % (prio['value'], prio['log'][:60])))

        # ARM 12b -- A FIACAO: o valor acima prova que a CURA funciona, nao que o
        # LACO A CHAMA. Um mutante que apaga `self._raise_thread_priority()` de
        # `_pump` passava na 12 (medido: NOT-CAUGHT). Aqui um `TrayIcon` NOVO corre
        # `_pump()` num fio proprio, como `_run` faz, e a linha
        # `TRAY_THREAD_PRIORITY` tem de sair DESSE laco.
        #
        # A janela pode NAO nascer (a classe ja' esta' registada por outra
        # instancia -- medido), e isso nao impede a arm: o raise e' a PRIMEIRA
        # coisa que `_pump` faz, antes de qualquer `GetMessageW`. O laco sai com um
        # `WM_QUIT` postado AO FIO (`PostThreadMessageW`), nao a uma janela.
        tray2 = shell.TrayIcon(icon_path=None, on_command=lambda c: None,
                               log_fn=log, warn_fn=warn)
        loop_seen = {'hwnd': 0, 'tid': 0, 'ready': threading.Event()}
        _logs_before = len(logs)

        def _tray_loop():
            loop_seen['tid'] = threading.get_native_id()
            # SEM JANELA, DE PROPOSITO. A primeira versao criava uma SEGUNDA
            # janela desta classe no mesmo processo; o `RegisterClassExW` devolve
            # `ERROR_CLASS_ALREADY_EXISTS` e fica registada a PRIMEIRA wndproc, um
            # thunk `ctypes` que morre com o modulo do mutante -- e o Windows
            # chama-lo depois disso da' `0xc000001d` (illegal instruction, medido
            # no `--neg-arm`: rc=29 a meio do segundo mutante). O que esta arm
            # julga e' a PRIMEIRA instrucao de `_pump`, e ela nao precisa de
            # janela nenhuma: `GetMessageW(None)` le a fila do FIO.
            loop_seen['ready'].set()
            tray2._pump()

        th2 = threading.Thread(target=_tray_loop, name='oracle-tray-loop',
                               daemon=True)
        th2.start()
        loop_seen['ready'].wait(3.0)
        time.sleep(0.05)
        pump_raised = any('TRAY_THREAD_PRIORITY' in ln
                          for ln in logs[_logs_before:])
        try:
            user32.PostThreadMessageW.argtypes = [ctypes.c_uint, ctypes.c_uint,
                                                  ctypes.c_void_p,
                                                  ctypes.c_void_p]
            user32.PostThreadMessageW(int(loop_seen['tid']), 0x0012, 0, 0)  # WM_QUIT
        except Exception:  # noqa: BLE001
            pass
        th2.join(1.5)
        checks.append(('tray_loop_calls_the_raise', pump_raised,
                       'TRAY_THREAD_PRIORITY no laco=%s' % pump_raised))

        # ARM 13 -- RETIRADA, e o motivo fica escrito porque a tentacao volta: a
        # primeira versao media "o menu abre com a caixa saturada" com
        # queimadores NO PROPRIO processo (7 227 ms sem resposta — era o GIL, nao
        # a prioridade) e a segunda com queimadores noutros processos mas a janela
        # criada no fio ERRADO (mensagens postadas vao para a fila do fio que
        # criou a janela, logo o `_pump` nunca via o clique). Nenhuma das duas
        # media o icone. A arm que MEDE a cura e' a 12, e ela le o VALOR que o fio
        # corre, de fora, com o handle do fio. Uma arm que precisa de uma inferencia
        # sobre o escalonador do Windows nao e' um instrumento: e' uma esperanca.

        # ARM 1 -- nothing appears on his screen and nothing enters Alt+Tab.
        vis = bool(user32.IsWindowVisible(wt.HWND(hwnd)))
        ex = exstyle(hwnd, user32)
        checks.append(('hidden_on_owner_screen', not vis,
                       f'IsWindowVisible={int(vis)}'))
        checks.append(('toolwindow_no_taskbar',
                       bool(ex & WS_EX_TOOLWINDOW), f'exstyle=0x{ex:X}'))

        # ARM 2 -- NOT message-only. MEASURED, and the folklore was wrong:
        # `GetAncestor(hwnd, GA_PARENT)` is NOT 0 for a message-only window on
        # this build (0x1000E mutant vs 0x1000C cured -- both non-zero), so the
        # discriminator that survived the mutant is the WS_POPUP bit: a
        # message-only window is created with style 0x4C00000, the hidden
        # top-level popup with 0x84000000. The parent half stays as a weaker
        # companion check and is reported, not relied on.
        parent = int(user32.GetAncestor(wt.HWND(hwnd), GA_PARENT) or 0)
        st = style(hwnd, user32)
        checks.append(('not_message_only', parent != 0 and bool(st & WS_POPUP),
                       f'ga_parent=0x{parent:X} style=0x{st:X}'))
        checks.append(('never_visible_bit', not (st & WS_VISIBLE),
                       f'style_visible={int(bool(st & WS_VISIBLE))}'))

        # ARM 3 -- LEFT opens the thing, through a REAL WM_COMMAND.
        tray._on_message(hwnd, shell.WM_TRAY_CALLBACK, 0, shell.WM_LBUTTONUP)
        got = drain(hwnd, user32)
        checks.append(('left_click_opens_panel',
                       any(m == shell.WM_COMMAND and w == shell.ID_TRAY_OPEN
                           for m, w in got),
                       f'posted={got} expected_id={shell.ID_TRAY_OPEN}'))

        # ARM 4 -- RIGHT opens the MENU, and does not also open the panel.
        opened = []
        real_show = tray._show_menu
        tray._show_menu = lambda: opened.append(True)
        try:
            tray._on_message(hwnd, shell.WM_TRAY_CALLBACK, 0, shell.WM_RBUTTONUP)
        finally:
            tray._show_menu = real_show
        right_posted = drain(hwnd, user32)
        checks.append(('right_click_opens_menu', len(opened) == 1,
                       f'menu_shown={len(opened)} posted={right_posted}'))
        checks.append(('right_click_does_not_open_panel', not right_posted,
                       f'posted={right_posted}'))

        # ARM 5 -- the three-part recipe, IN ORDER: foreground, WM_NULL, menu.
        seam.calls.clear()
        tray._show_menu()
        seq = [c[0] for c in seam.calls]
        want = ['SetForegroundWindow', 'PostMessageW', 'TrackPopupMenu']
        null_ok = any(c[0] == 'PostMessageW' and c[1] == shell.WM_NULL
                      and c[2] == hwnd for c in seam.calls)
        owner_ok = any(c[0] == 'TrackPopupMenu' and c[4] == hwnd
                       for c in seam.calls)
        checks.append(('menu_recipe_order', seq == want,
                       f'calls={seq}'))
        checks.append(('menu_posts_wm_null_before', null_ok,
                       f'calls={seam.calls}'))
        checks.append(('menu_owned_by_tray_window', owner_ok,
                       f'calls={seam.calls}'))
        checks.append(('foreground_measured_and_logged',
                       any('TRAY_MENU_FOREGROUND' in line for line in logs),
                       f'log={logs[-3:]}'))
    finally:
        seam.__exit__(None, None, None)
        try:
            user32.DestroyWindow(wt.HWND(hwnd))
        except Exception:  # noqa: BLE001
            pass
    return checks


# ---------------------------------------------------------------------------
# the mutants: the three call sites, reverted one at a time
# ---------------------------------------------------------------------------
CREATE_FIXED = """        hwnd = user32.CreateWindowExW(WS_EX_TOOLWINDOW, TRAY_WINDOW_CLASS, '',
                                      WS_POPUP, 0, 0, 0, 0, 0,
                                      None, hinst, None)"""
CREATE_MUTANT = """        hwnd = user32.CreateWindowExW(0, TRAY_WINDOW_CLASS, '', 0, 0, 0, 0, 0,
                                      HWND_MESSAGE, None, hinst, None)"""

BUTTONS_FIXED = """            if lparam == WM_RBUTTONUP:
                self._show_menu()"""
BUTTONS_MUTANT = """            if lparam in (WM_RBUTTONUP, WM_LBUTTONUP):
                self._show_menu()"""

MENU_FIXED = """        user32.PostMessageW(wt.HWND(self.hwnd), WM_NULL, 0, 0)
"""
MENU_MUTANT = """"""

RAISE_FIXED = """    def _pump(self):
        self._raise_thread_priority()
"""
RAISE_MUTANT = """    def _pump(self):
"""

MUTANTS = [
    ('tray_priority_raise_removed', RAISE_FIXED, RAISE_MUTANT,
     ['tray_loop_calls_the_raise']),
    ('hidden_popup_reverted_to_message_only', CREATE_FIXED, CREATE_MUTANT,
     ['not_message_only']),
    ('left_click_reverted_to_menu', BUTTONS_FIXED, BUTTONS_MUTANT,
     ['left_click_opens_panel']),
    ('wm_null_post_removed', MENU_FIXED, MENU_MUTANT,
     ['menu_posts_wm_null_before']),
]


def neg_arm() -> int:
    raw = open(SHELL, encoding='utf-8', newline='').read()
    # The shell is CRLF on this tree; the anchors below are written with \n.
    # A mutation that silently matches nothing is the mutant pretending to be
    # absent, which is exactly the failure this arm must not have.
    crlf = '\r\n' in raw
    src = raw.replace('\r\n', '\n')
    caught = 0
    total = 0
    for name, before, after, must_fail in MUTANTS:
        total += 1
        if before not in src:
            print(f'MUTANT NOT APPLICABLE {name}: anchor not found')
            continue
        path = os.path.join(SHELL_DIR, 'sotto_webview__mutant_tray.py')
        mutated = src.replace(before, after, 1)
        if crlf:
            mutated = mutated.replace('\n', '\r\n')
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(mutated)
        try:
            shell = load(path)
            checks = {c[0]: c for c in judge(shell)}
        finally:
            for mod in ('shell_under_test',):
                sys.modules.pop(mod, None)
            try:
                os.remove(path)
            except OSError:
                pass
            for cached in list(sys.modules):
                if cached == 'shell_under_test':
                    sys.modules.pop(cached, None)
        bad = [(n, checks[n][2]) for n in must_fail if not checks[n][1]]
        ok = len(bad) == len(must_fail)
        caught += int(ok)
        print(f'MUTANT {name}: {"CAUGHT" if ok else "NOT-CAUGHT"} '
              f'arms={must_fail} detail={bad}')
    print(f'NEG-ARM SUMMARY cases={total} caught={caught}')
    print('NEG-ARM: PASS' if caught == total else 'NEG-ARM: FAIL')
    return 1 if caught == total else 0


def main() -> int:
    shell = load()
    checks = judge(shell)
    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f'ARM {"PASS" if ok else "FAIL"} {name} {detail}')
    print(f'CHECK arms={len(checks)} failed={len(failed)}')
    print('VERDICT: PASS' if not failed else 'VERDICT: FAIL')
    return 0 if not failed else 1


if __name__ == '__main__':
    if '--neg-arm' in sys.argv:
        sys.exit(neg_arm())
    sys.exit(main())
