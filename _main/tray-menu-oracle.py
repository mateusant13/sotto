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

    `AttachThreadInput` is WRAPPED TOO (2026-11-10): the cure for "the menu never
    takes the foreground" is that pair around `SetForegroundWindow`, and a pair
    that nobody records is a pair nobody can tell from absent. `fAttach` travels
    as the record's second field, so `on` and `off` are distinguishable in the
    ORDER list.
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
        self._saved['AttachThreadInput'] = u.AttachThreadInput

        real_fg = self._saved['SetForegroundWindow']
        real_post = self._saved['PostMessageW']
        real_attach = self._saved['AttachThreadInput']

        def track(menu, flags, x, y, reserved, owner, rect):
            self.calls.append(('TrackPopupMenu', int(flags), int(x), int(y),
                               num(owner), num(menu)))
            return 0

        def foreground(hwnd):
            ok = real_fg(hwnd)
            self.calls.append(('SetForegroundWindow', num(hwnd), int(ok)))
            return ok

        def post(hwnd, msg, wparam, lparam):
            self.calls.append(('PostMessageW', int(msg), num(hwnd),
                               num(wparam)))
            return real_post(hwnd, msg, wparam, lparam)

        def attach(t_me, t_fg, on):
            ctypes.set_last_error(0)
            ok = real_attach(t_me, t_fg, bool(on))
            self.calls.append(('AttachThreadInput', bool(on), int(num(t_me)),
                               int(num(t_fg)), int(bool(ok)),
                               int(ctypes.get_last_error())))
            return ok

        u.TrackPopupMenu = track
        u.SetForegroundWindow = foreground
        u.PostMessageW = post
        u.AttachThreadInput = attach
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
        #
        # O PRIMEIRO PLANO E' UM MODELO, NAO O DO HOSPEDEIRO (medido 2026-11-23).
        # Julgado contra o `GetForegroundWindow` VIVO, este braco mede o estado da
        # maquina e nao o codigo: numa corrida o `_restore_menu_foreground`
        # dispara e na outra nao (`tail=[]` vs `tail=['SetForegroundWindow']`), e
        # um mutante que passa numa e cai na outra e' o pior tipo de arm -- a
        # licao que as arms 19-20 deste mesmo ficheiro ja' tinham pago. Aqui o
        # primeiro plano e' uma celula: `SetForegroundWindow` escreve-a e responde
        # 1, `GetForegroundWindow` le'-a. Com isso o restore SEMPRE dispara (a
        # janela da bandeja fica "em primeiro plano" logo depois da receita), a
        # cauda e' sempre o restore, e o mutante que o poe ANTES do menu tem onde
        # ser apanhado.
        real_get_fg = shell.user32.GetForegroundWindow
        real_set_fg = shell.user32.SetForegroundWindow
        cell = {'fg': 0}

        def model_get_fg():
            # PLAIN INT, NEVER AN HWND: the shell does `int(GetForegroundWindow()
            # or 0)`, and `int()` of a `c_void_p` is a ValueError -- the first
            # version of this model made `_take_menu_foreground` fail with
            # `reason=failed:ValueError` and the recipe lost its foreground call.
            return int(cell['fg'])

        def model_set_fg(hwnd):
            # `wt.HWND(...)` chega aqui como `c_void_p`, e `int()` dele e' um
            # ValueError: le'-se o `.value` (None quando o handle e' nulo).
            value = int(getattr(hwnd, 'value', hwnd) or 0)
            cell['fg'] = value
            seam.calls.append(('SetForegroundWindow', value, 1))
            return 1

        shell.user32.GetForegroundWindow = model_get_fg
        shell.user32.SetForegroundWindow = model_set_fg
        try:
            cell['fg'] = 4242
            seam.calls.clear()
            tray._show_menu()
        finally:
            shell.user32.GetForegroundWindow = real_get_fg
            shell.user32.SetForegroundWindow = real_set_fg
        # The attach pair travels in the SAME ordered record (2026-11-10) so the
        # order between it and the foreground call is judgeable; the recipe this
        # arm freezes is still exactly these three, so the pair is filtered out.
        seq = [c[0] for c in seam.calls if c[0] != 'AttachThreadInput']
        want = ['SetForegroundWindow', 'PostMessageW', 'TrackPopupMenu']
        # A RECEITA E' O PREFIXO, E O QUE VEM DEPOIS TEM NOME (medido
        # 2026-11-23). O `_restore_menu_foreground` (2026-11-10) devolve o
        # primeiro plano a quem o tinha quando o menu fecha, e ele custa UM
        # `SetForegroundWindow` -- `calls=[SetForegroundWindow, PostMessageW,
        # TrackPopupMenu, SetForegroundWindow]`. Julgar a lista INTEIRA como a
        # receita fazia a arm acusar o sitio CORRECTO e perder a autoridade: a
        # receita sao as TRES primeiras chamadas, e a cauda so' pode ser o
        # restore, nunca uma chamada a mais dentro da receita.
        null_ok = any(c[0] == 'PostMessageW' and c[1] == shell.WM_NULL
                      and c[2] == hwnd for c in seam.calls)
        owner_ok = any(c[0] == 'TrackPopupMenu' and c[4] == hwnd
                       for c in seam.calls)
        checks.append(('menu_recipe_order', seq[:3] == want,
                       f'calls={seq}'))
        checks.append(('menu_restore_after_menu',
                       seq[3:] in ([], ['SetForegroundWindow']),
                       f'tail={seq[3:]}'))
        checks.append(('menu_posts_wm_null_before', null_ok,
                       f'calls={seam.calls}'))
        checks.append(('menu_owned_by_tray_window', owner_ok,
                       f'calls={seam.calls}'))
        checks.append(('foreground_measured_and_logged',
                       any('TRAY_MENU_FOREGROUND' in line for line in logs),
                       f'log={logs[-3:]}'))

        # ARMS 19-21 -- O PRIMEIRO PLANO QUE O SISTEMA RECUSA, E A CURA.
        #
        # O DEFEITO MEDIDO (2026-11-10, clique real do dono): 13 de 13
        # `TRAY_MENU_FOREGROUND ok=0 is_foreground=0`. Nao era o hotkey nem o
        # gesto -- era o `SetForegroundWindow` cru a ser recusado, porque a
        # fechadura de primeiro plano deste hospedeiro esta' no MAXIMO
        # (`SPI_GETFOREGROUNDLOCKTIMEOUT=0x7FFFFFFF` ms): a condicao "a fechadura
        # expirou" NUNCA se verifica, e o processo da bandeja nao e' o processo
        # em primeiro plano nem recebeu o ultimo evento (o clique e' recebido
        # pelo EXPLORER).
        #
        # A CURA e' a receita documentada: `AttachThreadInput(fg, me, TRUE)` ->
        # `SetForegroundWindow` -> `AttachThreadInput(fg, me, FALSE)`.
        #
        # ARMS 19-20 INJECTAM O PRIMEIRO PLANO. Sem isso a arm dependeria do
        # estado vivo do Windows -- que nesta sessao e' "recusado" e noutra pode
        # ser "permitido" -- e o mesmo mutante passava numa e caia na outra, que
        # e' o pior tipo de arm. Com o `GetForegroundWindow` a devolver uma janela
        # ESTRANGEIRA (fio diferente do nosso), as duas metades ficam decididas
        # por codigo nosso:
        #   * 19: o par de attach tem de existir EM VOLTA da chamada (ordem lida);
        #   * 20: a linha do log tem de dizer o que o SISTEMA diz -- e o sistema,
        #     aqui, nunca devolve o hwnd (o injectado devolve `foreign`), logo
        #     `is_foreground=0` e um `reason=took-foreground` seria mentira.
        real_get_fg = shell.user32.GetForegroundWindow
        foreign = int(user32.GetShellWindow() or 0)
        if not foreign:
            foreign = int(user32.FindWindowW('Shell_TrayWnd', None) or 0)
        if not foreign:
            foreign = int(user32.FindWindowW('Progman', None) or 0)

        def _injected_foreground():
            return foreign

        seam.calls.clear()
        logs_before = len(logs)
        shell.user32.GetForegroundWindow = _injected_foreground
        try:
            tray._show_menu()
        finally:
            shell.user32.GetForegroundWindow = real_get_fg
        steps = [c[0] for c in seam.calls]
        on_rec = [c for c in seam.calls
                  if c[0] == 'AttachThreadInput' and c[1] is True]
        i_fg_call = steps.index('SetForegroundWindow') if 'SetForegroundWindow' in steps else -1
        i_attach = steps.index('AttachThreadInput') if 'AttachThreadInput' in steps else -1
        attach_took = bool(on_rec) and bool(on_rec[0][4])
        attaches_before = 0 <= i_attach < i_fg_call
        # A FILA TEM DE SER DESLIGADA: deixar as duas filas ligadas prende o input
        # dos dois processos um ao outro -- e' a parte que se esquece.
        detaches_after = (not attach_took) or (
            'AttachThreadInput' in steps[i_fg_call + 1:])
        targets_other_thread = bool(on_rec) and on_rec[0][3] != on_rec[0][2]
        checks.append(('menu_attaches_the_foreground_thread',
                       bool(foreign) and attaches_before and detaches_after
                       and targets_other_thread,
                       f'foreign={foreign} steps={steps} attach={on_rec}'))
        line = ''
        for candidate in logs[logs_before:]:
            if 'TRAY_MENU_FOREGROUND' in candidate:
                line = candidate
        fields = dict(re.findall(r'([a-z_]+)=(\S+)', line))
        checks.append(('menu_foreground_log_is_what_the_os_says',
                       bool(fields)
                       and fields.get('is_foreground') == '0'
                       and fields.get('fg_before') == str(foreign)
                       and fields.get('reason') not in ('took-foreground',
                                                        'already-foreground'),
                       f'line={line!r}'))

        # ARM 21 -- O ESTADO QUE A ROTINA DEVOLVE E' O DO SISTEMA, sem injecao.
        # Esta arm nao julga se o Windows CONCEDE (isso depende da sessao); ela
        # julga se o que devolvemos e' o que `GetForegroundWindow` diz AGORA --
        # que e' exactamente a diferenca entre um log honesto e um que so' parece.
        fg_before_arm = int(user32.GetForegroundWindow() or 0)
        fg_state = tray._take_menu_foreground()
        os_says = int(user32.GetForegroundWindow() or 0) == int(hwnd)
        checks.append(('menu_foreground_state_is_the_os',
                       bool(fg_state['is_foreground']) == bool(os_says),
                       f"is_foreground={fg_state['is_foreground']} "
                       f'os_says={os_says} reason={fg_state["reason"]} '
                       f'attach_err={fg_state["attach_err"]}'))
        if os_says:
            # A arm ACABOU DE TOMAR O PRIMEIRO PLANO NESTE PROCESSO. Devolve-se a
            # quem o tinha: o oracle nao pode deixar o foco do dono fora do lugar
            # so' porque correu uma medicao.
            try:
                if fg_before_arm and fg_before_arm != int(hwnd):
                    user32.SetForegroundWindow(wt.HWND(fg_before_arm))
            except Exception:         # noqa: BLE001
                pass

        # ARMS 15-18 -- O INTERRUPTOR DO ALT+C (dono, 2026-11-07: *"faz um botao
        # 'desativar atalho alt c' no click direito do icon do sotto"*, *"e claro,
        # é ativar e desativar"*).
        #
        # 15: o TEXTO e' a ACCAO, e muda com o estado. Um item que dissesse
        # sempre "Desativar" seria um botao que nao sabe o que faz na segunda vez.
        state = {'enabled': True}
        live = {'on': False}
        tray3 = shell.TrayIcon(icon_path=None, on_command=lambda c: None,
                               log_fn=log, warn_fn=warn,
                               panels_state_fn=lambda: {
                                   'enabled': state['enabled'], 'accel': 'Alt+C'},
                               live_state_fn=lambda: {
                                   'on': live['on'], 'accel': 'Ctrl+Space'})
        # SEM JANELA, DE PROPOSITO. Uma SEGUNDA janela desta classe no mesmo
        # processo devolve `ERROR_CLASS_ALREADY_EXISTS` e deixa registada a
        # wndproc da PRIMEIRA -- um thunk `ctypes` que morre com o modulo do
        # mutante; o Windows chama-lo depois disso e o processo cai com
        # `0xc000001d` (medido no `--neg-arm` desta mesma arvore). O que estas
        # arms julgam e' o TEXTO do menu, e o menu nao precisa de janela.
        try:
            tray3._build_menu()
            armed_items = shell.menu_items(tray3.menu)
            text_armed = [i['text'] for i in armed_items
                          if i['id'] == shell.ID_TRAY_HOTKEY]
            text_live_off = [i['text'] for i in armed_items
                             if i['id'] == shell.ID_TRAY_LIVE]
            state['enabled'] = False
            live['on'] = True
            tray3.refresh_menu('oracle')
            off_items = shell.menu_items(tray3.menu)
            text_off = [i['text'] for i in off_items
                        if i['id'] == shell.ID_TRAY_HOTKEY]
            text_live_on = [i['text'] for i in off_items
                            if i['id'] == shell.ID_TRAY_LIVE]
            ids = [i['id'] for i in off_items if i['id']]
            checks.append(('menu_hotkey_item_says_disable_when_armed',
                           text_armed == ['Desativar atalho Alt+C'],
                           f'text={text_armed}'))
            checks.append(('menu_hotkey_item_says_enable_when_disarmed',
                           text_off == ['Ativar atalho Alt+C'],
                           f'text={text_off}'))
            # O ITEM DA LEGENDA AO VIVO (dono, 2026-11-09: *"ctrl space is not
            # yet known by a user, so put it on the right click of the icon as a
            # 'activate subtitles - ctrl space'"*). O TEXTO nomeia a TECLA --
            # um item que so' dissesse "Ligar legendas" deixava o dono sem saber
            # qual e' o atalho, que e' exactamente a queixa que o item responde.
            checks.append(('menu_live_item_says_enable_with_accel',
                           text_live_off == ['Ligar legendas (Ctrl+Space)'],
                           f'text={text_live_off}'))
            checks.append(('menu_live_item_says_disable_when_on',
                           text_live_on == ['Desligar legendas (Ctrl+Space)'],
                           f'text={text_live_on}'))
            checks.append(('menu_keeps_the_three_shipped_ids',
                           ids == [shell.ID_TRAY_OPEN, shell.ID_TRAY_HOTKEY,
                                   shell.ID_TRAY_LIVE, shell.ID_TRAY_EDIT,
                                   shell.ID_TRAY_QUIT],
                           f'ids={ids}'))
        finally:
            for handle in (tray3.menu,):
                try:
                    if handle:
                        user32.DestroyMenu(handle)
                except Exception:         # noqa: BLE001
                    pass
            tray3.menu = None

        # 16: O CLIQUE NAO CONSTROI O MENU. O defeito medido: `_build_menu()`
        # (CreatePopupMenu + 4 AppendMenu + uma varredura por item + um `log` com
        # `flush` no disco) corria DENTRO do clique, antes de o menu aparecer. A
        # arm compara o handle que o `TrackPopupMenu` recebe em DOIS cliques.
        seam.calls.clear()
        tray._show_menu()
        tray._show_menu()
        menus = [c[5] for c in seam.calls if c[0] == 'TrackPopupMenu']
        checks.append(('menu_is_built_once_and_reused',
                       len(menus) == 2 and menus[0] == menus[1],
                       f'menu_handles={menus}'))

        # 17: A FIACAO DO COMANDO. `tray_command(4)` tem de chamar o interruptor
        # -- um item que aparece e nao faz nada e' pior do que nao existir.
        fake = type('FakeShell', (), {'calls': []})()
        fake.toggle_panels_hotkey = lambda: fake.calls.append('toggle')
        shell.SottoShell.tray_command(fake, shell.ID_TRAY_HOTKEY)
        checks.append(('tray_command_routes_the_hotkey_id',
                       fake.calls == ['toggle'], f'calls={fake.calls}'))
        # 17-bis: E O ITEM DA LEGENDA AO VIVO ENTRA PELA MESMA PORTA QUE A TECLA.
        # `hotkey_live()` e' o que o `Ctrl+Space` chama; um item que chamasse um
        # segundo caminho teria uma segunda semantica.
        fake2 = type('FakeShell2', (), {'calls': []})()
        fake2.hotkey_live = lambda: fake2.calls.append('live')
        shell.SottoShell.tray_command(fake2, shell.ID_TRAY_LIVE)
        checks.append(('tray_command_routes_the_live_id',
                       fake2.calls == ['live'], f'calls={fake2.calls}'))
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

# O RESTORE QUE FECHA O MENU ANTES DE ELE ABRIR. O defeito que esta mutacao
# planta e' o que a arm `menu_restore_after_menu` existe para apanhar: a cauda
# deixa de ser so' o restore e a receita passa a ter uma chamada de primeiro
# plano a mais -- exactamente o `SetForegroundWindow` que roubaria o menu.
RESTORE_ORDER_FIXED = """        command = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,"""
RESTORE_ORDER_MUTANT = """        self._restore_menu_foreground(fg)
        command = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,"""

RAISE_FIXED = """    def _pump(self):
        self._raise_thread_priority()
"""
RAISE_MUTANT = """    def _pump(self):
"""

REUSE_FIXED = """        menu = self.menu
        if not menu:
            menu = self._build_menu()
        t_menu"""
REUSE_MUTANT = """        menu = self._build_menu()
        t_menu"""

LABEL_FIXED = """        label = (f'Desativar atalho {accel}' if armed
                 else f'Ativar atalho {accel}')"""
LABEL_MUTANT = """        label = f'Desativar atalho {accel}'"""

ROUTE_FIXED = """        elif command == ID_TRAY_HOTKEY:"""
ROUTE_MUTANT = """        elif command == 999:"""

#: O defeito de hoje (2026-11-10): o primeiro plano tomado sem ligar as filas de
#: input. `SetForegroundWindow` cru e' recusado enquanto a fechadura de primeiro
#: plano desta maquina (MAXIMA) nao expira -- que e' nunca.
ATTACH_FIXED = """                attached = bool(user32.AttachThreadInput(
                    wt.DWORD(state['me_thread']), wt.DWORD(fg_thread), True))
                state['attached'] = attached
                if not attached:
                    state['attach_err'] = ctypes.get_last_error()"""
ATTACH_MUTANT = """                attached = False"""

#: A outra metade -- um log que diz `is_foreground=1` sem o sistema o ter dito.
LOG_FIXED = """                 f'is_foreground={int(fg["is_foreground"])} '
"""
LOG_MUTANT = """                 f'is_foreground=1 '
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
    # O restore ANTES do menu: a receita ganha uma chamada de primeiro plano a
    # mais e a cauda deixa de ser so' o restore.
    ('menu_restore_before_menu', RESTORE_ORDER_FIXED, RESTORE_ORDER_MUTANT,
     ['menu_recipe_order', 'menu_restore_after_menu']),
    # O defeito de hoje: o menu reconstruido a cada clique (o `flush` no disco
    # fica entre o clique e o menu -- "aperto e nao responde").
    ('menu_rebuilt_on_every_click', REUSE_FIXED, REUSE_MUTANT,
     ['menu_is_built_once_and_reused']),
    # Um item que so' sabe desligar.
    ('hotkey_label_frozen_on_disable', LABEL_FIXED, LABEL_MUTANT,
     ['menu_hotkey_item_says_enable_when_disarmed']),
    # Um item que aparece e nao faz nada.
    ('hotkey_command_not_routed', ROUTE_FIXED, ROUTE_MUTANT,
     ['tray_command_routes_the_hotkey_id']),
    # O defeito de 2026-11-10: `SetForegroundWindow` sem o par de
    # `AttachThreadInput` -- recusado 13 de 13 vezes no clique real do dono.
    ('foreground_attach_removed', ATTACH_FIXED, ATTACH_MUTANT,
     ['menu_attaches_the_foreground_thread']),
    # E o log que mente sobre o que o sistema disse.
    ('foreground_log_hardcoded_to_1', LOG_FIXED, LOG_MUTANT,
     ['menu_foreground_log_is_what_the_os_says']),
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
