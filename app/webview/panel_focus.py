"""Quem fica com o PRIMEIRO PLANO quando o painel aparece -- e quando isso e' preciso.

Extraido de `sotto_webview.py` em 2026-11-01: o modulo tinha crescido acima do tecto do
ratchet (`_main/code-health-oracle.py`) e estes tres sao uma POLITICA, nao um servico de
janela -- leem o estado do cursor (`GetClipCursor`), decidem se o mapa activa a janela, e
devolvem essa decisao a quem mostra o painel. Sao os unicos sitios do shell que falam com
`SetForegroundWindow`, e por isso a casa deles e' aqui.

O `log` entra por PARAMETRO: o shell tem o seu (escreve no `webview-run.log` do dono) e um
modulo que o importasse fecharia um ciclo shell -> politica -> shell.

O que este ficheiro garante, medido (2026-11-01, `_main/pov-selftest.py`):
    cursor LIVRE      -> SW_SHOWNOACTIVATE, `FOREGROUND_KEPT reason=no-pointer-lock`
    cursor CAPTURADO  -> SW_SHOW+SetForegroundWindow, `FOREGROUND_TAKEN reason=pointer-lock`
    antes disto, TODO show tomava o primeiro plano e o `selftest` reprovava-o em
    `focus_stolen_by_own_window=true`.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

from win32_types import CURSORINFO, RECT

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32.GetClipCursor.argtypes = [ctypes.POINTER(RECT)]
user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindow.restype = wt.BOOL
user32.SetForegroundWindow.restype = wt.BOOL
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.GetForegroundWindow.restype = wt.HWND
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]

HWND_TOPMOST = -1
SW_RESTORE = 9
SW_SHOW = 5
SW_SHOWNOACTIVATE = 4
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010


def set_topmost(hwnd) -> bool:
    """Re-assert TopMost without moving, resizing or activating."""
    return bool(user32.SetWindowPos(wt.HWND(hwnd), wt.HWND(HWND_TOPMOST), 0, 0, 0, 0,
                                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE))


def _foreground_steal_attached(hwnd, log=print) -> bool:
    """Rouba o primeiro plano com a fila de input LIGADA a do dono atual.

    O `SetForegroundWindow` e RECUSADO quando quem chama nao e o processo em primeiro
    plano -- medido nesta maquina: `PANEL_FOREGROUND_UNLOCK ok=false` quatro vezes
    seguidas (05:57:04/05:57:07/05:57:11), com o painel a aparecer ATRAS da janela em
    uso. E o comportamento documentado do Windows, nao um bug do Sotto.

    A saida documentada e `AttachThreadInput`: enquanto as duas filas estao ligadas, o
    Windows trata os dois threads como um so para efeitos de primeiro plano, e a chamada
    passa. Desligar no `finally` e obrigatorio -- deixar as filas ligadas prende o input
    dos dois processos um ao outro.
    """
    try:
        fg = int(user32.GetForegroundWindow() or 0)
        if not fg:
            return False
        owner = wt.DWORD(0)
        t_fg = int(user32.GetWindowThreadProcessId(wt.HWND(fg), ctypes.byref(owner)) or 0)
        t_me = int(kernel32.GetCurrentThreadId())
        attached = False
        try:
            if t_fg and t_fg != t_me:
                attached = bool(user32.AttachThreadInput(wt.DWORD(t_me), wt.DWORD(t_fg), True))
            user32.BringWindowToTop(wt.HWND(hwnd))
            ok = bool(user32.SetForegroundWindow(wt.HWND(hwnd)))
            log('PANEL_FOREGROUND_ATTACH ok=%s fg_thread=%s me_thread=%s attached=%s'
                % (str(ok).lower(), t_fg, t_me, str(attached).lower()))
            return ok
        finally:
            if attached:
                user32.AttachThreadInput(wt.DWORD(t_me), wt.DWORD(t_fg), False)
    except Exception as exc:  # noqa: BLE001 -- nunca matar a hotkey
        log(f'PANEL_FOREGROUND_ATTACH_FAILED error={exc!r}')
        return False


#: `GetSystemMetrics` indices that describe the WHOLE virtual desktop -- the rect
#: a clip has to be smaller than to count as a lock.
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
#: Borders, shadows and per-monitor rounding never amount to more than this; a
#: pointer lock is off by a whole window, not by 3 px.
POINTER_LOCK_TOLERANCE_PX = 8
CURSOR_SHOWING = 0x00000001


user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetClipCursor.restype = wt.BOOL
user32.GetClipCursor.argtypes = [ctypes.POINTER(RECT)]
user32.GetCursorInfo.restype = wt.BOOL
user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]



def pointer_lock_state(log=print) -> dict:
    """O app em PRIMEIRO PLANO tem o rato preso AGORA?

    O SINAL E' O CLIP RECT, e e' honesto porque e' o MECANISMO: um jogo com pointer
    lock chama `ClipCursor` a' volta da propria janela (ou de uma caixa pequena no
    ponto de mira) para o cursor nao sair de la'. Uma app normal -- o terminal em
    que o dono escreve, o browser, o Explorer -- deixa o clip no desktop virtual
    inteiro. Logo `GetClipCursor` contra `SM_*VIRTUALSCREEN` separa os dois sem
    perguntar nada ao jogo, e sem o shell tocar em `ClipCursor` (que continua a ser
    do jogo).

    O cursor INVISIVEL e' reportado ao lado e NUNCA usado sozinho: `GetCursorInfo`
    diz `CURSOR_SHOWING` para quase todas as apps, mas tambem cala o ponteiro num
    leitor de video em ecra inteiro, que nao e' um pointer lock.

    Nunca levanta: um probe falhado devolve `clipped=false` e a razao no detalhe --
    errar para "nao roubar o foco" e' a direccao segura para o dono.
    """
    state = {'clipped': False, 'clip': None, 'desktop': None,
             'cursor_visible': None, 'detail': 'ok'}
    try:
        desk_w = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
        desk_h = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
        state['desktop'] = '%dx%d' % (desk_w, desk_h)
        r = RECT()
        if user32.GetClipCursor(ctypes.byref(r)):
            w = int(r.right - r.left)
            h = int(r.bottom - r.top)
            state['clip'] = '%dx%d@(%d,%d)' % (w, h, r.left, r.top)
            state['clipped'] = bool(
                w <= 0 or h <= 0
                or w < max(1, desk_w - POINTER_LOCK_TOLERANCE_PX)
                or h < max(1, desk_h - POINTER_LOCK_TOLERANCE_PX))
        info = CURSORINFO()
        info.cbSize = ctypes.sizeof(CURSORINFO)
        if user32.GetCursorInfo(ctypes.byref(info)):
            state['cursor_visible'] = bool(info.flags & CURSOR_SHOWING)
        state['detail'] = ('clip=%s desktop=%s cursor_visible=%s'
                           % (state['clip'], state['desktop'],
                              str(state['cursor_visible']).lower()))
    except Exception as exc:  # noqa: BLE001 -- never block a show on a probe
        state['detail'] = 'clip-probe-failed=%r' % (exc,)
    return state


def foreground_unlock(hwnd, log=print) -> dict:
    """Map the panel, and take the FOREGROUND only to free a POINTER LOCK.

    ── PORQUE ISTO DEIXOU DE SER INCONDICIONAL (2026-11-01) ───────────────────
    O dono, verbatim: *"nunca travar o pc do usuario ... NUNCA"*. Esta funcao
    tomava o primeiro plano em TODOS os shows, e por medicao isso fazia do PAINEL
    a janela em primeiro plano: `_main/pov-selftest.py` imprime
    `focus_stolen_by_own_window=true`. Vinte Alt+C roubavam o caret do dono vinte
    vezes, no terminal em que ele estava a escrever.

    O desbloqueio de rato que a versao anterior servia e' um ESTADO DE JOGO, e um
    estado de jogo e' observavel por pressao (`pointer_lock_state`): o jogo poe o
    cursor preso (`ClipCursor`) para o rato nao sair da janela. Nenhuma outra
    app -- o terminal, o browser, o Explorer -- o prende. Logo:

        cursor PRESO     -> SW_RESTORE + SW_SHOW + SetForegroundWindow
                            (`FOREGROUND_TAKEN reason=pointer-lock`)
        cursor LIVRE     -> SO' SW_SHOWNOACTIVATE
                            (`FOREGROUND_KEPT reason=no-pointer-lock`)

    UM CLIQUE NO PAINEL CONTINUA A ATIVA'-LO, e isso nao se contradiz: o Windows
    ativa uma janela ao clique do proprio dono (`WM_MOUSEACTIVATE` ->
    `MA_ACTIVATE`, que NAO come o clique), portanto o foco segue a mao que o pediu
    em vez do programa que mapeou uma janela.

    Devolve um dict (o chamador regista `show=`/`focus=` numa so' linha). Nunca
    levanta: um show falhado e' uma linha de log, nunca um Alt+C perdido.
    """
    out = {'mapped': False, 'foreground': False, 'reason': 'no-hwnd',
           'show': 'none', 'lock': {}}
    if not hwnd:
        return out
    lock = pointer_lock_state()
    out['lock'] = lock
    try:
        set_topmost(hwnd)
        if lock['clipped']:
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.ShowWindow(hwnd, SW_SHOW)
            ok = bool(user32.SetForegroundWindow(hwnd))
            # E SE O WINDOWS RECUSAR, INSISTE PELA FILA LIGADA. Ver o helper: o
            # `SetForegroundWindow` e' recusado quando quem chama nao esta' em
            # primeiro plano, e um jogo em pointer lock esta'.
            if not ok:
                ok = _foreground_steal_attached(hwnd, log)
            out.update({'mapped': True, 'foreground': bool(ok),
                        'reason': 'pointer-lock',
                        'show': 'SW_SHOW+FOREGROUND'})
            log('FOREGROUND_TAKEN reason=pointer-lock hwnd=%s ok=%s %s'
                % (hwnd, str(bool(ok)).lower(), lock.get('detail')))
            return out
        mapped = bool(user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE))
        out.update({'mapped': mapped, 'foreground': False,
                    'reason': 'no-pointer-lock', 'show': 'SW_SHOWNOACTIVATE'})
        log('FOREGROUND_KEPT reason=no-pointer-lock hwnd=%s mapped=%s %s'
            % (hwnd, str(mapped).lower(), lock.get('detail')))
        return out
    except Exception as exc:  # noqa: BLE001 -- report, never kill the hotkey
        log(f'PANEL_FOREGROUND_UNLOCK_FAILED error={exc!r}')
        out['reason'] = 'failed'
        return out

