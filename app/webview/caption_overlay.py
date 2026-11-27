"""NATIVE TRANSPARENT CAPTION OVERLAY (Win32 layered window + GDI+).

WHY THIS FILE EXISTS
--------------------
WebView2 cannot do per-pixel transparency inside pywebview's WinForms host:
`TransparencyKey` / `LWA_COLORKEY` on the parent cannot key the WebView2
child's opaque pixels (Microsoft WebView2Feedback #118 measured exactly that),
and pywebview documents `transparent` as not supported on Windows. The result
is a solid plate behind the words -- white, dark, or magenta depending on
which background is set.

The supported Windows mechanism for a true see-through overlay is a LAYERED
window updated with `UpdateLayeredWindow` and a 32-bit premultiplied ARGB DIB.
That is what this module does: GDI+ draws the caption text (white fill, black
stroke, green LED) onto a transparent bitmap, and Win32 composites it over the
desktop with per-pixel alpha. No WebView2, no colour key, no plate.

The window is:
  * `WS_EX_LAYERED` + `ULW_ALPHA`  -> per-pixel alpha
  * `WS_EX_TRANSPARENT`            -> clicks pass through to the video
  * `WS_EX_TOOLWINDOW`             -> no taskbar entry
  * `WS_EX_NOACTIVATE`             -> never steals focus
  * `WS_POPUP` + topmost           -> overlay
"""

from __future__ import annotations

import ctypes
import json
import threading
import time
from ctypes import wintypes as wt

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

#: O ESTILO DA JANELA, NUM SO' SITIO (2026-11-04). Era uma conta local dentro de
#: `_create`; passou a constante do modulo porque o oraculo da captura mede o
#: VALOR que a janela recebe -- `WS_EX_TRANSPARENT` e' o click-through nativo
#: (a hit-region do `perssua-re`, sem hook nenhum de input) e `WS_EX_NOACTIVATE`
#: e' o que impede o overlay de roubar o foco ao video.
EX_STYLE = (0x00080000      # WS_EX_LAYERED
            | 0x00000020    # WS_EX_TRANSPARENT  (click-through NATIVO)
            | 0x00000080    # WS_EX_TOOLWINDOW
            | 0x08000000    # WS_EX_NOACTIVATE
            | 0x00000008)   # WS_EX_TOPMOST
WS_POPUP = 0x80000000
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
DIB_RGB_COLORS = 0
BI_RGB = 0
SWP_NOZORDER = 0x0004
#: AS TECLAS DO ARRASTO (2026-11-08). Lidas com `GetAsyncKeyState` no tick que
#: ja' existe -- o padrao sancionado do repo (o arrasto do modo de edicao da
#: strip faz exactamente isto). NENHUM hook global.
VK_LBUTTON = 0x01
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
#: A area de TRABALHO do monitor da janela -- exclui a barra de tarefas.
MONITOR_DEFAULTTONEAREST = 2
#: QUANTO DE UM NUCLEO A PINTURA DA LEGENDA PODE OCUPAR (2026-11-08).
#: Nao e' um numero de gosto: e' o divisor que transforma o custo medido de um
#: quadro na taxa maxima de quadros (`_limit_by_paint`). A versao anterior punha
#: o periodo IGUAL ao custo, e um laco que dorme o tempo que trabalha gasta
#: 100 % de um nucleo por construcao -- foi o que o instrumento externo mediu na
#: instancia viva (pid 42572, `sotto-caption-tick` a 93,6 %, reprodutivel).
#: Com 40 %, uma pintura de 11,6 ms da' 34 Hz; curada a 2 ms, da' 200 Hz -- a
#: taxa sobe quando o quadro fica barato, que e' a ordem do dono.
CAPTION_FRAME_BUDGET = 0.40


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte),
                ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte),
                ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG),
                ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


_user32 = ctypes.WinDLL('user32', use_last_error=True)
_gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT,
                             wt.WPARAM, wt.LPARAM)

_user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
_user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p]
_user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wt.UINT]
_user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", wt.RECT),
                ("rcWork", wt.RECT), ("dwFlags", ctypes.c_ulong)]
_user32.UpdateLayeredWindow.argtypes = [
    wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE),
    wt.HDC, ctypes.POINTER(wt.POINT), wt.DWORD,
    ctypes.POINTER(BLENDFUNCTION), wt.DWORD]
_user32.GetDC.argtypes = [wt.HWND]
_user32.GetDC.restype = wt.HDC
_user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
_user32.DestroyWindow.argtypes = [wt.HWND]
_user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
_user32.GetMessageW.restype = ctypes.c_int
_user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
_user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
_user32.DispatchMessageW.restype = ctypes.c_ssize_t
_user32.PostQuitMessage.argtypes = [ctypes.c_int]
_user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
_user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
# ── O ARRASTO: as TRES leituras do tick, e o rect real da janela ─────────────
_user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_user32.GetAsyncKeyState.restype = ctypes.c_short
_user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
_user32.GetCursorPos.restype = wt.BOOL
_user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
_user32.GetWindowRect.restype = wt.BOOL
_user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
_user32.MonitorFromWindow.restype = ctypes.c_void_p
_user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p,
                                    ctypes.POINTER(MONITORINFO)]
_user32.GetMonitorInfoW.restype = wt.BOOL
_kernel32.GetCurrentThreadId.restype = wt.DWORD
_kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wt.HINSTANCE
_gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
_gdi32.CreateCompatibleDC.restype = wt.HDC
_gdi32.CreateDIBSection.argtypes = [
    wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
    ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
_gdi32.CreateDIBSection.restype = wt.HBITMAP
_gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
_gdi32.SelectObject.restype = wt.HGDIOBJ
_gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
_gdi32.DeleteDC.argtypes = [wt.HDC]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR),
                ("hIconSm", wt.HICON)]


# ── A METADE PURA DA PINTURA VIVE EM `app/webview/overlay_paint.py` ───────────
# Medir (GDI+, a MESMA engine que desenha), resolver a cor e a cara, normalizar o
# tema, calcular a geometria e pintar o bitmap sao funcoes de
# `(texto, tema, escala)`, e todas vivem no modulo ao lado. Aqui fica a JANELA: o
# `CreateWindowExW`, a thread da mensagem, o `UpdateLayeredWindow`.
#
# O ratchet estrutural (`_main/code-health-oracle.py`) e' a razao da divisao, e os
# nomes sao os MESMOS de proposito: `caption_overlay._layout`, `._geom`,
# `._measure`, `._premultiplied_bitmap`, `._THEME_DEFAULT` e `._MEASURE_CACHE`
# continuam a existir para quem os le' de fora (a shell e os oraculos
# `youtube-rows`/`caption-native-wrap`), por isso a lista abaixo e' a superficie
# historica deste modulo e nao "imports por usar".
from overlay_paint import (  # noqa: F401,E402 -- superficie publica deste modulo
    _MEASURE_CACHE, _THEME_DEFAULT, _case, _colour, _font_family, _geom,
    _layout, _luminance, _make_font, _measure, _measure_budget,
    _normalise_theme, _premultiplied_bitmap, _rgba, _same_line,
    EDGE_PX as _EDGE_PX,
)

# ── O ARRASTO COM CTRL (2026-11-08) ─────────────────────────────────────────
# A DECISAO vive no modulo ao lado, sem Win32 nenhum (`caption_drag`); aqui fica
# so' o poll que a alimenta e o `SetWindowPos` que aplica o resultado. O oraculo
# `_main/caption-drag-oracle.py` corre a MESMA funcao que embarca.
import caption_drag  # noqa: E402 -- superficie usada no tick da janela


# ── A JANELA DO PLAYER NO RELOGIO DO PROPRIO PLAYER (2026-11-03) ─────────────
#: Quantas linhas o overlay desenha no caminho do player. O YouTube declara
#: `rcRows: 2` no payload e o dono pediu o mesmo no ecra: no maximo DUAS.
PLAYER_ROWS = 2
#: Ate' quando a extrapolacao do relogio do player vale sem uma leitura nova --
#: o mesmo numero do `YT_ANCHOR_MAX_S` do `sotto_webview`: um video pausado nao
#: pode continuar a revelar palavras por inercia.
PLAYER_HOLD_S = 3.0


def _clamp_rows(rows, limit=PLAYER_ROWS):
    """No maximo `limit` linhas FISICAS, com as quebras que o player desenhou.

    Uma linha do payload pode trazer a sua propria quebra (`'\\n'` dentro do
    texto), logo uma lista de duas linhas pode valer TRES no ecra. Quando passa
    do tecto saem as do TOPO -- a que esta' a rolar para fora --, nunca a que
    esta' a crescer.
    """
    parts = []
    for row in rows or ():
        for part in str(row).splitlines():
            part = " ".join(part.split())
            if part:
                parts.append(part)
    return parts[-max(1, int(limit)):]


class _PlayerCue:
    """A JANELA QUE O PLAYER ESTA' A DESENHAR, e o relogio que a revela.

    O DEFEITO QUE ISTO CURA (medido 2026-11-03, `_main/webview-run.log`, pid
    28888): 18 linhas `YOUTUBE_CAPTION ... why=painted-other-track` e o cue a
    chegar INTEIRO de segundo a segundo. O overlay recebia-o ja' pronto
    (`set_text(..., instant=True)`) e pintava-o todo no instante da chegada --
    a frase aparecia de uma vez e a palavra nunca aparecia palavra a palavra,
    que e' o que o dono pediu (*"surgir palavras ... igual o youtube"*).

    O QUE ESTA CLASSE GUARDA: as LINHAS do player com o relogio de cada palavra
    (`rows`, a forma de `youtube_reveal.rows_from_cues`: `text`, `words`,
    `start`, `end`, `cap`) e o instante do VIDEO em que foram lidas (`t`), com o
    `monotonic()` da leitura (`at`). O relogio em vigor e' `t + (agora - at)`,
    limitado a `PLAYER_HOLD_S`: entre duas leituras do UIA a palavra seguinte
    aparece no instante em que o player a desenha -- e nao no instante em que o
    UIA respondeu, que e' o defeito.

    RESYNC: uma instancia nova por cue (`set_text(..., cue=...)`). O relogio
    nunca RECUA -- `floor` e' o instante mais adiantado ja' desenhado, e um `t`
    atrasado (o UIA salta de segundo em segundo) nao apaga palavras reveladas.
    Um seek para tras NAO leva o `floor` (ver `_cue_from`).
    """

    def __init__(self, rows, t, at=None, capacity=PLAYER_ROWS, rate=1.0, log=None):
        self.rows = []
        for row in rows or ():
            if isinstance(row, dict):
                self.rows.append(dict(row))
            elif str(row or "").strip():
                # UMA LINHA SEM RELOGIO NEM PALAVRAS: e' o que o shell tem hoje
                # (`youtube_window.revealed_lines` devolve TEXTO). Entra inteira
                # e sem `start` -- `youtube_reveal._drawn` desenha-a sempre, e o
                # `cue_t0` do cue cai no `t` da leitura em vez de num zero falso
                # que estragava o `land_lag_ms`.
                self.rows.append({"text": str(row), "end": None,
                                  "words": [], "cap": None})
        self.t = float(t)
        self.at = time.monotonic() if at is None else float(at)
        # A VELOCIDADE DO PLAYER (2026-11-04). `clock()` avancava 1 s de video
        # por 1 s de parede; a 2x a palavra seguinte chegava ao dobro do tempo.
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            rate = 1.0
        self.rate = rate if 0.05 <= rate <= 16.0 else 1.0
        self.floor = None
        self.capacity = max(1, int(capacity))
        starts = []
        for row in self.rows:
            try:
                starts.append(float(row.get('start')))
            except (TypeError, ValueError):
                continue
        #: O `start` do cue -- o denominador do `land_lag_ms`. Sem nenhum `start`
        #: declarado, o cue comeca no instante em que o player estava.
        self.cue_t0 = min(starts) if starts else self.t
        #: O relogio do player na PRIMEIRA pintura deste cue (`None` = ainda nao
        #: pintou nada). E a metade do `land_lag_ms` que nao vem do shell.
        self.first_paint_t = None
        self.paint_texts = []
        self.logged = False
        #: O TECTO DO RELOGIO ERA MUDO (2026-11-26). `PLAYER_HOLD_S` existe para
        #: nao inventar video que ninguem mediu: passados 3,0 s sem uma leitura
        #: nova o relogio da revelacao PARA no fim do cue. So' que ele parava
        #: calado -- e o dono, que ouve o audio a continuar, ve uma linha
        #: congelada e chama-lhe "travou". MEDIDO nos proprios logs dele: o
        #: produtor chegou a estar 8,2 s (02:38:08) e 8,71 s sem publicar, ou
        #: seja 5,2 s de revelacao perdidos por episodio COM o ecra a mostrar a
        #: linha antiga. Uma linha por cue (nunca por quadro) nomeia o episodio.
        self.log = log or (lambda message: None)
        self.held_logged = False
        #: O MAIOR `gap - PLAYER_HOLD_S` visto neste cue, em segundos. E o
        #: numero que `_main/yt-reveal-hold-oracle.py` julga, e o que o recibo
        #: de um incidente cita: sem ele, "congelou" continua a ser impressao.
        self.held_s = 0.0

    def clock(self, now=None):
        now = time.monotonic() if now is None else float(now)
        gap = max(0.0, now - self.at)
        elapsed = min(gap, PLAYER_HOLD_S)
        if gap > PLAYER_HOLD_S:
            self.held_s = max(self.held_s, gap - PLAYER_HOLD_S)
            if not self.held_logged:
                self.held_logged = True
                self.log('CAPTION_REVEAL_HELD gap_s=%.2f hold_s=%.2f lost_s=%.2f '
                         't=%.3f rows=%d'
                         % (gap, PLAYER_HOLD_S, gap - PLAYER_HOLD_S,
                            self.t, len(self.rows)))
        t = self.t + elapsed * self.rate
        if self.floor is not None:
            t = max(t, self.floor)
        return t

    def frame(self, now=None):
        """As linhas desenhadas agora -- prefixo revelado pelo relogio de cada
        palavra, a MESMA regra do caminho do YouTube (`youtube_reveal.frame`).

        COM O ROLL-UP (2026-11-08, ordem do dono: *"quero a animacao de quando
        comeca uma linha nova e a outra linha vai pra cima"*). Antes daqui o
        `rollup` era 0 e a terceira linha nunca era desenhada: a linha velha
        DESAPARECIA de um quadro para o outro e a nova entrava por baixo sem
        ninguem se mexer. Agora saem as `capacity` linhas da janela MAIS a que
        esta' a rolar para fora, e quem as empurra e' `roll()`.
        """
        import youtube_reveal
        return youtube_reveal.frame(self.rows, self.clock(now),
                                    self.capacity, youtube_reveal.ROLLUP_ROWS,
                                    youtube_reveal.EXIT_S)

    def roll(self, now=None):
        """Quanto do deslocamento vertical ja' aconteceu: 0.0 (parado) -> 1.0.

        O deslocamento e' o que o dono ve': a linha nova comeca e TODAS as linhas
        sobem um espaco de linha, com a mais velha a sair por cima. A duracao e'
        a do *exit* medido no player (`youtube_reveal.EXIT_S`) e o instante de
        partida e' o `displaced_at` que o `frame` devolve -- o `start` da linha
        que empurrou, no relogio do video, nao o instante em que o UIA respondeu.
        """
        import youtube_reveal
        marks = self.frame(now)
        if len(marks) <= self.capacity:
            return 0.0
        displaced_at = marks[0].get("displaced_at")
        if displaced_at is None:
            return 0.0
        return youtube_reveal.roll_progress(self.clock(now) - float(displaced_at),
                                           youtube_reveal.EXIT_S)

    def next_clock(self, now=None):
        """O proximo instante (monotonic) em que algo muda -- ou `None`.

        E' o unico `Timer` certo para a revelacao: o instante de uma palavra, ou
        o `start` de uma linha que ainda nao comecou.
        """
        now = time.monotonic() if now is None else float(now)
        cur = self.clock(now)
        ahead = []
        for row in self.rows:
            try:
                start = float(row.get('start'))
            except (TypeError, ValueError):
                start = None
            if start is not None and start > cur + 1e-6:
                ahead.append(start)
            for word in row.get('words') or ():
                try:
                    w = float(word.get('start'))
                except (TypeError, ValueError):
                    continue
                if w > cur + 1e-6:
                    ahead.append(w)
        if not ahead:
            return None
        return now + (min(ahead) - cur)


# ── O LADO WIN32 DO ARRASTO: TRES LEITURAS, UM RECTO, UM ADAPTADOR ───────────
# Tudo o que toca em `user32` para o arrasto vive aqui e e' fino de proposito:
# a decisao esta' em `caption_drag`, que nao importa ctypes.

def _ctrl_held():
    """`True` se QUALQUER Ctrl esta' carregado agora. Sem hook, sem fio."""
    for vk in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
        if _user32.GetAsyncKeyState(vk) & 0x8000:
            return True
    return False


def _lbutton_held():
    return bool(_user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)


def _cursor_px():
    """O cursor em coordenadas de ECRÃ, ou None se o Windows recusar."""
    pt = wt.POINT()
    if not _user32.GetCursorPos(ctypes.byref(pt)):
        return None
    return (int(pt.x), int(pt.y))


def _window_rect(hwnd):
    """`(x, y, w, h)` da janela como o Windows a compos no ecra."""
    rect = wt.RECT()
    if not hwnd or not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return (int(rect.left), int(rect.top),
            int(rect.right - rect.left), int(rect.bottom - rect.top))


def _monitor_work(hwnd):
    """A area de trabalho do monitor da janela (sem barra de tarefas), ou None."""
    try:
        mon = _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        if not mon:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not _user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return None
        work = info.rcWork
        return {'x': int(work.left), 'y': int(work.top),
                'width': int(work.right - work.left),
                'height': int(work.bottom - work.top)}
    except Exception:  # noqa: BLE001 -- sem monitor, fica o `self.work`
        return None


def _gdi_colour(rgba):
    from System.Drawing import Color
    return Color.FromArgb(int(rgba[3]), int(rgba[0]), int(rgba[1]),
                          int(rgba[2]))


class _DragCanvas:
    """O adaptador GDI+ da marca do arrasto: UM `Pen`, reutilizado por frame.

    A pulsacao muda a COR do Pen em vez de construir um Pen novo -- o custo por
    frame fica no `Color` (struct) e nao num objecto GDI+. O `Graphics` nao se
    pode guardar porque o bitmap e' novo em cada frame; e' o unico objecto que a
    marca paga, e so' enquanto o Ctrl esta' carregado.
    """

    def __init__(self):
        self._gfx = None
        self._pen = None

    def bind(self, gfx):
        self._gfx = gfx
        if self._pen is None:
            from System.Drawing import Pen
            self._pen = Pen(_gdi_colour(caption_drag.ACCENT_RGB + (255,)), 3.0)

    def outline(self, x, y, w, h, colour, thickness):
        """O protocolo que o oraculo imita: um rect a' volta do bitmap."""
        if self._gfx is None or self._pen is None:
            return
        self._pen.Width = float(thickness)
        self._pen.Color = _gdi_colour(colour)
        self._gfx.DrawRectangle(self._pen, float(x), float(y),
                                float(w), float(h))


#: A RESOLUCAO DO RELOGIO DO SISTEMA, LEVANTADA SO' ENQUANTO HA' ANIMACAO.
#:
#: O QUE ISTO **NAO** E': a cura do laco. Medido 2026-11-08 com o laco REAL, o
#: `sleep` de 4,17 ms devolvia 16,00 ms e a culpa nao era da resolucao -- era do
#: RELOGIO do prazo (`time.monotonic()`, 15 ms de grao; ver `_frame_now` abaixo).
#: Com o relogio curado, `timeBeginPeriod(1)` deu 4,21 ms e `timeEndPeriod(1)`
#: 4,18 ms: dentro do ruido, porque a resolucao DESTA maquina ja' estava em
#: 1,00 ms (`NtQueryTimerResolution`) por causa de outro processo.
#:
#: O QUE ISTO E': a garantia de que um sono de 4 ms nao dependa de um TERCEIRO.
#: A resolucao de 1 ms nesta maquina nao e' nossa -- vem de quem mais corre nela,
#: e uma medida que depende disso nao e' uma medida. O `timeEndPeriod(1)` devolve
#: a maquina ao que era no primeiro instante sem frame armado, para o custo em
#: bateria existir so' enquanto ha' animacao.
_TIMER_PERIOD = {'on': False}


def _guard(obj, name):
    """O cadeado DEDICADO do objeto, ou o `lock` geral quando ele nao existe.

    Os oraculos (`caption-drag-oracle`, `caption-tick-thread-oracle`) constroem
    o overlay com `object.__new__` e poem so' o `lock`: um atributo a mais
    faltaria la' e o tick levantava `AttributeError`. O `getattr` e' o mesmo
    padrao de compatibilidade que `_content_due_at` ja' usa.
    """
    lock = getattr(obj, name, None)
    return lock if lock is not None else obj.lock


def _timer_period(on, log_fn=None):
    """Liga/desliga a resolucao de 1 ms do relogio -- idempotente e fail-open."""
    if on == _TIMER_PERIOD['on']:
        return
    try:
        winmm = ctypes.WinDLL('winmm')
        if on:
            winmm.timeBeginPeriod(1)
        else:
            winmm.timeEndPeriod(1)
    except Exception:
        return                      # sem winmm nao ha' nada a fazer, e nao e' erro
    _TIMER_PERIOD['on'] = on
    if log_fn is not None:
        try:
            log_fn('CAPTION_FRAME_TIMER period_ms=%d' % (1 if on else 0))
        except Exception:
            pass


#: O RELOGIO DO FRAME E' `perf_counter`, NAO `monotonic` -- MEDIDO 2026-11-08.
#:
#: Nesta maquina `time.monotonic()` tem **15,000 ms de granularidade** (200 000
#: leituras seguidas devolvem 50 valores distintos, todos a 15 ms; o mesmo teste
#: em `time.perf_counter()` da' 0,0003 ms). Todo o prazo de frame era aritmetica
#: sobre esse relogio: pedir 4,167 ms (240 Hz) lia-se como "0 ou 1 tique", pedir
#: 16,7 ms (60 Hz) como "1 ou 2 tiques" -- a animacao andava em degraus de 15 ms
#: e nenhum tecto acima de ~62 Hz podia ser alcancado, por mais que o `sleep`
#: dormisse ao microssegundo. Medido antes da cura, com o laco REAL: 66 quadros/s
#: para um pedido de 240 Hz e p50 de 16,00 ms; pedido de 60 Hz dava 31,00 ms.
#:
#: `perf_counter` e' monotonico e de alta resolucao no Windows (QPC); e' o mesmo
#: relogio que `time.sleep` obedece. Os CARIMBOS que viajam para fora do overlay
#: continuam em `time.monotonic()`: eles comparam com o relogio do shell, e
#: misturar as duas escalas num so' numero seria pior do que o defeito.
_frame_now = time.perf_counter


#: O ASPECTO QUE A LEGENDA EMBARCA, lido UMA vez no import (2026-11-09).
#:
#: Dono, verbatim: *"the background in the subtitles is too wide. should be
#: more concise and less bloaty"* e, na mesma rodada, o pedido de transparencia
#: escolhivel. O default vive em `caption_settings.DEFAULT_PLATE` ('tight'): uma
#: legenda sem ficheiro de configuracao ja' nasce apertada, e a configuracao so'
#: AFASTA esse default quando o dono escolhe outra coisa.
#:
#: LIDO NO IMPORT, nao a cada pintura: `_caption_style` corre uma vez por quadro
#: e um `json.load` por quadro seria 60 leituras de disco por segundo no caminho
#: da animacao. Quem muda o valor em runtime chama `set_visual`.
_SHIPPED_VISUAL = {'plate': 'tight', 'opacity': 1.0}
try:
    import caption_settings as _caption_settings
except Exception:                       # noqa: BLE001 -- sem o modulo, o default acima
    _caption_settings = None
if _caption_settings is not None:
    try:
        _SHIPPED_VISUAL = dict(_caption_settings.visual())
    except Exception:                   # noqa: BLE001
        pass


class NativeCaptionOverlay:
    #: O fade de entrada esta' DESLIGADO (ordem do dono 2026-11-03). O botao
    #: fica para o oraculo poder provar as duas metades: com `False`, nenhum
    #: frame intermedio e' publicado; com `True`, a animacao antiga volta -- e o
    #: braco negativo do oraculo le exatamente essa diferenca.
    FADE_ON = False

    """A per-pixel-alpha caption window. No WebView2, no plate."""

    CLASS_NAME = "SottoNativeCaption"

    def __init__(self, log=None):
        self._init_state(log)
        # THE WINDOW OWNS ITS OWN THREAD AND MESSAGE PUMP. Creating it on the
        # pywebview/WinForms UI thread meant every Win32 call from the caption
        # watcher blocked the UI thread (measured 2026-10-17: the UI thread
        # stopped pumping and `_ui` logged `UI_THREAD_STALL` for 10 s). A
        # dedicated owner is the standard shape for a topmost overlay and it
        # keeps the panel's WebView2 thread free.
        self._thread = threading.Thread(target=self._thread_main,
                                        name='sotto-caption-overlay', daemon=True)
        self._thread.start()
        self._ready.wait(5.0)

    @classmethod
    def for_test(cls, log=None):
        """Overlay sem janela: o estado REAL, sem o fio de mensagens.

        Os oraculos de tick, arrasto e roll-up exercem os metodos reais
        (`_tick`, `_display`, `_limit_by_paint`) sem abrir a janela Win32 que
        `__init__` cria. Estado = o de producao; faltam so' a janela e o fio.
        Nao usar na aplicacao.
        """
        obj = object.__new__(cls)
        obj._init_state(log)
        return obj

    def _init_state(self, log=None):
        self.log = log or (lambda msg: None)
        self.lock = threading.RLock()
        #: O CADEADO DO POLL DO ARRASTO (ordem do dono, verbatim: *"segurar o
        #: ctrl pra mover a legenda, até o ctrl fazer efeito, DEMORA PRA
        #: CARALHO, quando o sistema ta sob carga. ARRUMA."*). O `lock` geral e'
        #: tomado pela pintura de conteudo (`set_text` -> `_update`) pelo custo
        #: medido de 31,75 ms (`CAPTION_DRAG_RATE ... paint_ms=31.75`, no
        #: `_main/webview-run.log`); com o poll DENTRO do mesmo lock, a taxa
        #: entregue caiu a 4,2 Hz (mesmo log), e o Ctrl demorava a aparecer.
        #: Só' o poll e as contas do arrasto passam por este cadeado, que a
        #: pintura nunca toma -- por isso a janela segue o rato sem esperar
        #: pintura nenhuma.
        self._poll_lock = threading.RLock()
        #: O CADEADO DA AGENDA do tick (prazo + geracao). `_tick_loop` e o poll
        #: tem de se re-armar MESMO com a pintura a segurar o `self.lock`:
        #: medido no `caption-drag-oracle` P16, com a pintura a ocupar o cadeado
        #: por 300 ms, o codigo real entrega ~60 polls nessa janela e o mutante
        #: que espera pela pintura entrega ZERO.
        self._sched_lock = threading.RLock()
        self.hwnd = None
        self.thread_id = None
        self.visible = False
        # `_blank` e' "o bitmap actual nao tem pixel nenhum" -- ver `show`.
        self._blank = True
        self.text = ""
        self.previous = ""
        self.scale = 1.0
        self.work = {"x": 0, "y": 0, "width": 1920, "height": 1080}
        # THE DESIGN THE PANEL IS WEARING RIGHT NOW. Default == the overlay that
        # shipped before the brand contract existed (Segoe UI 34 px, green dot),
        # so a panel that never posts tokens loses nothing.
        self.theme = dict(_THEME_DEFAULT)
        # O ASPECTO ESCOLHIDO (dono, 2026-11-09): a placa aperta-se e o alfa da
        # placa e' escolhivel. Sem ficheiro, e' o default que embarca.
        self.plate_mode = _SHIPPED_VISUAL.get('plate', 'tight')
        self.opacity = _SHIPPED_VISUAL.get('opacity', 1.0)
        # ── O PAINEL MANDA NO Z (dono, 2026-11-14) ───────────────────────────
        # VERBATIM: *"os paineis devem ficar ACIMA da legenda. no `z index`. a
        # legenda, agora mesmo, ta encima do painel"*. O `show(True)` corre a
        # CADA linha e faz `SetWindowPos(HWND_TOPMOST)` + `ShowWindow`, e as duas
        # re-erguem a janela dentro da banda topmost -- por isso a legenda
        # aterrou por cima do painel. `z_below` e' um provedor que devolve o hwnd
        # que esta' DEVE ficar acima desta janela (o painel, quando visivel), e o
        # `show` poe a legenda logo abaixo dele DEPOIS de se erguer. None = sem
        # painel, o comportamento antigo (topmost puro).
        self.z_below = None
        self._wndproc = WNDPROC(self._on_message)
        self._ready = threading.Event()
        # ── O MOTOR DA LEGENDA AO VIVO (2026-11-01) ──────────────────────
        # `_live` e' o `youtube_reveal.LiveRows` desta legenda: o ASR entrega texto a
        # CRESCER, o motor da' a cada palavra o instante em que ela chegou e devolve
        # as LINHAS do YouTube -- reveladas palavra a palavra, quebradas pela regra
        # do `caption_wrap`, com a janela a rolar. Nao ha' aqui um segundo tempo: o
        # sprout de 45 ms de relogio de parede morreu com este trabalho, e o
        # `_main/youtube-1to1-oracle.py` (arm `one-engine`) recusa-o de volta.
        #
        # PORQUE O MOTOR E NAO UM TIMER AQUI: o dono, 2026-11-01, verbatim:
        # *"mesmo quando é só transcricao em tempo real, deve imitar o
        # comportamento da legenda do youtube"*. Duas regras de tempo (uma no
        # caminho do YouTube, outra no do ASR) e' exactamente o que produzia duas
        # legendas diferentes no mesmo ecra.
        self._live = None
        # `_cue` e' o CUE DO PLAYER com o relogio dele (ver `_PlayerCue`). Os dois
        # motores nunca correm ao mesmo tempo: um cue do player substitui o
        # `_live` do ASR, e um `set_text(..., instant=False)` volta a substituir o
        # cue. `set_text` e' quem decide -- aqui so' se guarda.
        self._cue = None
        # `_row_alphas` e' o alfa POR LINHA do ultimo frame (255 = linha viva); a
        # linha que sai desvanece por dentro do bitmap, porque o
        # `SourceConstantAlpha` do `UpdateLayeredWindow` e' um numero por JANELA.
        self._row_alphas = None
        # `_roll` e' quanto do deslocamento vertical do ULTIMO frame ja'
        # aconteceu (0.0 -> 1.0, ver `_PlayerCue.roll`). E' o numero que faz a
        # linha velha SAIR PARA CIMA em vez de desaparecer: as linhas sao
        # desenhadas com `-roll * line_h` de deslocamento, e a mais velha e'
        # cortada pelo topo da caixa.
        self._roll = 0.0
        # `_tick_gen` retira um tick ja' armado quando a linha que o armou ja' nao
        # existe -- a mesma tecnica do sprout, e pela mesma razao: um `Timer` pode
        # ja' estar dentro de `_update` quando o texto muda.
        self._tick_gen = 0
        # UM FIO SO' PARA O RELOGIO DO DESENHO (2026-11-08). Antes cada frame armava
        # um `threading.Timer` -- um FIO NOVO por frame, ~62/s com a legenda ao vivo
        # a 16 ms -- e cada `CreateThread` custa kernel. Agora um fio `daemon` espera
        # no `Event` com prazo: ver `_tick_loop`.
        self._tick_timer = None          # compatibilidade: o ultimo PRAZO, nao um fio
        self._tick_event = threading.Event()
        self._thread = None
        self._tick_thread = None
        self._tick_deadline = 0.0        # `_frame_now`; 0 = nada armado
        #: O custo MEDIDO do ultimo `_update` (segundos) -- so' a fase de pintura.
        #: Fica no log e no `CAPTION_FRAME_LIMIT` como INFORMACAO; quem decide a
        #: taxa e' `_paint_frame_cost_s` (o tick inteiro), nunca esta parcela.
        self._paint_cost_s = 0.0
        #: O custo MEDIDO do ULTIMO TICK QUE PINTOU (segundos), do inicio do
        #: `_tick` ao fim do arme: poll + tentativa de `self.lock` + `_update`
        #: + `_arm_poll`/`_arm_tick`. E' ESTE numero que o orcamento divide
        #: (`_limit_by_paint`): medido na instancia viva (pid 34520, 2026-11-17)
        #: o fio gastava 71,7 % de um nucleo enquanto o log declarava 40 %,
        #: porque a conta so' via a pintura e todo o resto do tick era pago por
        #: fora. Um tick de POLL (sem pintura) nao o escreve -- senao um poll
        #: barato entre dois quadros devolvia o tecto de 240 Hz ao quadro caro.
        self._paint_frame_cost_s = 0.0
        #: As fases DESSE mesmo tick que pintou (poll e `_update`), para a linha
        #: `CAPTION_TICK_COST` ser um triplo coerente: `tick >= poll + paint`.
        #: Publicar o `tick_ms` de um tick de poll ao lado do `paint_ms` do
        #: ultimo quadro dava `tick_ms < paint_ms` -- medido no log de 01:25:52
        #: (`paint_ms=10.54 tick_ms=0.28`), uma linha que mente sobre a soma.
        self._paint_frame_poll_s = 0.0
        self._paint_frame_paint_s = 0.0
        #: O custo do ultimo tick, seja ele de poll ou de pintura (segundos), e
        #: o contador da janela de 5 s do `CAPTION_TICK_COST`.
        self._tick_cost_s = 0.0
        self._tick_poll_s = 0.0
        self._tick_cost_logged = 0.0
        self._tick_cost_n = 0
        #: Quando o log do limite foi escrito pela ultima vez (segundos).
        self._paint_limit_logged = 0.0
        self._tick_stop = False
        self._tick_wake_gen = 0
        # O FADE DA LINHA NOVA (ordem do dono, 2026-10-30: *"por que a nossa
        # legenda nao tem a mesma animacao da do youtube?"*). `_fade_t0` e' o
        # instante em que a linha mudou, ou None quando nao ha' fade a correr.
        self._fade_t0 = None
        self._fade_gen = 0
        # ── O ARRASTO COM CTRL (2026-11-08) ─────────────────────────────────
        # `_drag` e' a memoria do gesto ENTRE ticks; `_drag_offset` e' o par
        # persistido, restaurado ja' (a primeira pintura nasce no sitio onde o
        # dono a deixou). `_drag_pos` e' o canto que a janela ocupa durante o
        # arrasto -- enquanto ele existe, a pintura usa-O em vez de recalcular
        # a base, para o texto a mudar de largura nao fazer a janela saltar.
        self._drag_offset = caption_drag.load_offset()
        self._drag = caption_drag.DragState(offset=self._drag_offset)
        self._drag_armed = False
        self._drag_dragging = False
        # ── A PLACA DE CADA QUADRO, EM NUMERO (2026-11-12) ──────────────────
        # Ordem do dono, verbatim: *"por algum motivo, o background da legenda
        # atrasou pra aparecer. entao a legenda ficou uns segundos sem
        # background."* A placa e' desenhada DENTRO do mesmo bitmap que o glifo
        # (`overlay_paint._paint_bitmap`), logo a unica forma de ela faltar num
        # quadro com texto e' o tema ainda nao ter chegado: `set_theme` repinta,
        # mas a janela nasce com `plate=no` e o desenho do painel chega ~3 s
        # depois (`CAPTION_OVERLAY_THEME_APPLIED ... why=page`, medido 19:41:43
        # -> 19:41:46). Estes tres campos transformam esse atraso num NUMERO:
        # `_paint_n` conta quadros, `_plate_state` guarda o que o ultimo levou,
        # e o log so' escreve na MUDANCA com o contador ao lado -- uma linha por
        # quadro a 60 Hz seria o mesmo custo que a DM de stutter cobrou ao tick.
        self._paint_n = 0
        self._plate_state = None
        #: A primeira pintura que levou TEXTO, para o atraso da placa ser
        #: medido contra ela ("texto visivel sem placa" = `text_paint_n` menor
        #: que o quadro em que a placa entrou).
        self._text_paint_n = None
        self._text_paint_at = 0.0
        self._drag_pos = None
        self._drag_canvas = None
        #: `True` quando o ultimo `_arm_tick` foi armado por CONTEUDO (palavra,
        #: roll, fade) e nao pelo poll do arrasto. E' o que decide se `_tick`
        #: repinta ou so' le' o teclado (ver `_tick`).
        self._tick_content = True
        #: O PRAZO DO CONTEUDO no relogio do frame (`_frame_now`), separado do
        #: prazo do POLL. `None` = nenhum conteudo pendente. E' o que permite o
        #: poll do arrasto correr no tecto de 240 Hz sem repintar a cada tick:
        #: `_tick` so' desenha quando ESTE prazo venceu (ou quando a pulsacao do
        #: Ctrl pede). Ver `_next_delay`.
        self._content_due_at = None
        #: A MEDICAO DO ARRASTO: ticks, movimentos e pinturas entre o inicio e o
        #: fim de um gesto. Publicada em `CAPTION_DRAG_RATE` ao largar; um numero
        #: medido, nunca o tecto declarado.
        self._drag_ticks = 0
        self._drag_moves = 0
        self._drag_paints = 0
        self._drag_paint_s = 0.0
        self._drag_t0 = 0.0

    def _thread_main(self):
        self.thread_id = int(_kernel32.GetCurrentThreadId())
        self._register()
        self._create()
        self._ready.set()
        if not self.hwnd:
            return
        msg = wt.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

    def _register(self):
        hinst = _kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0x0001 | 0x0002
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = self.CLASS_NAME
        atom = _user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            err = ctypes.get_last_error()
            if err not in (0, 1410):  # 1410 = class already registered
                self.log(f"CAPTION_OVERLAY_CLASS_FAILED error={err}")

    def _create(self):
        hinst = _kernel32.GetModuleHandleW(None)
        hwnd = _user32.CreateWindowExW(
            EX_STYLE, self.CLASS_NAME, "Sotto caption", WS_POPUP,
            -4000, -4000, 900, 120, None, None, hinst, None)
        if not hwnd:
            self.log(f"CAPTION_OVERLAY_CREATE_FAILED error={ctypes.get_last_error()}")
            return
        self.hwnd = hwnd
        self.log(f"CAPTION_OVERLAY_CREATED hwnd={hwnd} layered=true "
                 f"transparent=true noactivate=true")
        # A EXCLUSAO DE CAPTURA (2026-11-04, portada do `perssua-re`): a janela
        # continua a pintar para o dono e desaparece de quem grava o ecra. Uma
        # chamada por janela, e o MODO que fica e' lido de volta -- um 0x11
        # pedido e nao aplicado conta como falha, nunca como sucesso.
        try:
            import capture_exclusion
            self.capture = capture_exclusion.apply(
                hwnd, want=capture_exclusion.enabled())
            self.log('CAPTION_OVERLAY_CAPTURE mode=%s(0x%02x) ok=%s why=%s build=%s '
                     'ex_style=0x%08x transparent=%s noactivate=%s'
                     % (capture_exclusion.mode_name(self.capture['mode']),
                        self.capture['mode'] & 0xff, self.capture['ok'],
                        self.capture['why'], capture_exclusion.build_number(),
                        EX_STYLE, bool(EX_STYLE & WS_EX_TRANSPARENT),
                        bool(EX_STYLE & WS_EX_NOACTIVATE)))
        except Exception as exc:  # noqa: BLE001 -- a legenda nao pode morrer por isto
            self.capture = {'mode': -1, 'ok': False, 'why': repr(exc)}
            self.log(f'CAPTION_OVERLAY_CAPTURE_FAILED error={exc!r}')

    def _on_message(self, hwnd, msg, wparam, lparam):
        if msg == 0x0010:  # WM_CLOSE
            _user32.DestroyWindow(hwnd)
            return 0
        if msg == 0x0002:  # WM_DESTROY
            _user32.PostQuitMessage(0)
            return 0
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def set_work_area(self, work, scale=1.0):
        self.work = dict(work or self.work)
        self.scale = float(scale or 1.0)

    def set_theme(self, tokens=None):
        """Wear a design: the panel's own live row decides the overlay's face.

        Chamado pelo shell no push do painel: so' o documento sabe em que deu o
        CSS (fallbacks, `color-mix`, a escala dele). Aqui so' se sanitiza e se
        guarda.
        """
        theme = _normalise_theme(tokens)
        with self.lock:
            self.theme = theme
            # A cache e' por face+tamanho: limpar e' para o tamanho DESCER.
            _MEASURE_CACHE.clear()
            if self.hwnd and (self.text or self.previous):
                self._update()
        self.log('CAPTION_OVERLAY_THEME name=%s font=%s live=%.1f prev=%.1f '
                 'plate=%s rule=%.1f led=%s align=%s'
                 % (theme.get('theme') or '-', theme.get('fontFamily'),
                    theme.get('livePx'), theme.get('prevPx'),
                    'yes' if theme.get('plate') else 'no',
                    theme.get('ruleW') or 0.0,
                    'yes' if theme.get('led') else 'no', theme.get('align')))
        return dict(theme)

    def _caption_style(self):
        """O aspecto aplicado; um objecto SEM os atributos recebe o que EMBARCA.

        O default deixou de ser `normal`/1.0 em 2026-11-09 -- e' o que o dono
        pediu (*"less bloaty"*) e o que `caption_settings.DEFAULT_PLATE` diz. O
        oraculo (`_main/caption-plate-oracle.py`, arm A6) le exactamente esta
        diferenca, e o `--neg-arm` dele muta esta linha.
        """
        mode = str(getattr(self, 'plate_mode', None)
                   or _SHIPPED_VISUAL.get('plate') or 'tight').lower()
        try:
            alpha = float(getattr(self, 'opacity', _SHIPPED_VISUAL.get('opacity', 1.0)))
        except (TypeError, ValueError):
            alpha = 1.0
        return {'plate_mode': mode if mode in ('tight', 'normal') else 'tight',
                'opacity': max(0.30, min(1.0, alpha))}

    def set_visual(self, opacity=None, plate=None):
        """Aplica o aspecto vindo das configuracoes, e repinta o que esta' no ar.

        UMA PORTA PARA A ESCOLHA DO DONO (2026-11-09). O valor ja' foi PRESO por
        `caption_settings.set_visual` (o unico sitio do clamp, que grava); aqui
        so' se aplica e se pinta -- duas copias do clamp e' como o botao mostra
        um numero e a legenda usa outro.

        `None` = nao mexe. Devolve o que ficou aplicado, para o log do shell
        dizer o numero REAL e nao o pedido.
        """
        if plate is not None:
            self.plate_mode = str(plate or '').strip().lower() or None
        if opacity is not None:
            try:
                self.opacity = float(opacity)
            except (TypeError, ValueError):
                pass
        applied = self._caption_style()
        self.plate_mode, self.opacity = applied['plate_mode'], applied['opacity']
        with self.lock:
            _MEASURE_CACHE.clear()
            if self.hwnd and (self.text or self.previous):
                self._update()
        self.log('CAPTION_OVERLAY_VISUAL plate=%s opacity=%.2f'
                 % (applied['plate_mode'], applied['opacity']))
        return applied

    def set_capture_exclude(self, want=None):
        """Liga/desliga o "modo stealth" na JANELA VIVA, agora.

        O dono escolhe no painel e a janela que ele ja' esta' a ver muda no mesmo
        gesto -- sem reiniciar o Sotto, que era a unica alternativa quando isto
        so' corria no `_create`. `want is None` volta a ler a decisao de
        `capture_exclusion.enabled()` (env -> ficheiro), para o shell nao ter uma
        segunda copia da regra. Devolve o modo LIDO DE VOLTA do sistema.
        """
        try:
            import capture_exclusion
        except Exception as exc:  # noqa: BLE001 -- a legenda nao morre por isto
            return {'mode': -1, 'ok': False, 'why': repr(exc)}
        resolved = capture_exclusion.enabled() if want is None else bool(want)
        if not self.hwnd:
            self.capture = {'mode': -1, 'ok': False, 'why': 'sem hwnd'}
            self.log('CAPTION_OVERLAY_CAPTURE_DEFERRED want=%s' % resolved)
            return dict(self.capture)
        got = capture_exclusion.apply(self.hwnd, want=resolved)
        self.capture = got
        self.log('CAPTION_OVERLAY_CAPTURE mode=%s(0x%02x) ok=%s why=%s want=%s'
                 % (capture_exclusion.mode_name(got['mode']),
                    got['mode'] & 0xff, got['ok'], got['why'], resolved))
        return dict(got)

    def _measure(self, text, previous):
        """Largura em px: o MESMO motor que desenha, nunca `GenericTypographic`
        -- medido 2026-10-17, 4,7% mais estreito, e quebrar com um e desenhar com
        o outro corta a ultima letra."""
        _lines, _prev, width, height, _scrolled = _layout(
            text, previous, self.scale, self.work.get('width', 1920),
            self.theme, **self._caption_style())
        return width, height

    def _fade_alpha(self):
        """O `SourceConstantAlpha` deste frame -- SEMPRE 255 (sem fade).

        O DONO TIROU O FADE, DUAS VEZES. 2026-10-30 pediu a animacao do YouTube;
        2026-11-03, sobre uma captura: *"e ta com animacao fade in que eu JA
        MANDEI VOCE TIRAR"*. A linha nova APARECE, a que sai desliza para fora
        com o roll-up; fade na janela inteira custa um `UpdateLayeredWindow`
        por alfa intermedio. `FADE_ON` e' o botao, e o caminho de desenho existe
        para o oraculo provar as duas metades.
        """
        if not self.FADE_ON:
            self._fade_t0 = None
            return 255
        if self._fade_t0 is None:
            return 255
        import word_fade
        elapsed = time.monotonic() - self._fade_t0
        alpha = word_fade.alpha_at(elapsed)
        if word_fade.done(alpha):
            self._fade_t0 = None
        return alpha

    def _next_delay(self):
        """Quanto falta para o proximo frame que MUDA alguma coisa.

        TRES RAZOES PARA REPINTAR, e a mais proxima manda -- e nenhuma delas e' um
        compasso fixo:

          * o fade da janela (`word_fade.alpha_at`), frame a frame;
          * a proxima PALAVRA da linha viva (`LiveRows.next_clock`): e' o unico
            instante em que o texto muda, logo o unico instante em que vale a pena
            desenhar. Um tick de 60 ms (`RENDER_S` do shell) desenharia 60 frames
            por segundo para mostrar uma palavra a cada 240 ms;
          * uma linha a SAIR: `frame(t)` diz que ha' uma, e ela desvanece ao longo
            de `word_fade.EXIT_S`, logo precisa de frames ate' chegar a zero.
        """
        import word_fade
        now = time.monotonic()
        delay = None
        if self._fade_t0 is not None:
            delay = word_fade.next_delay(now - self._fade_t0)
        if self._live is not None:
            ahead = self._live.next_clock(now)
            if ahead is not None:
                step = max(word_fade.FRAME_S, float(ahead) - now)
                delay = step if delay is None else min(delay, step)
            if any(mark["exiting"] for mark in self._live.frame(now)):
                delay = (word_fade.FRAME_S if delay is None
                         else min(delay, word_fade.FRAME_S))
        # O ROLL-UP PRECISA DE FRAMES (2026-11-08). Enquanto o deslocamento
        # vertical nao chegou a 1.0 ha' pixel novo em cada quadro -- e' a unica
        # razao pela qual a linha velha sobe em vez de desaparecer. Sem esta
        # linha o video ficava parado no primeiro quadro da transicao.
        if 0.0 < self._roll < 1.0:
            delay = (word_fade.FRAME_S if delay is None
                     else min(delay, word_fade.FRAME_S))
        # O CUE DO PLAYER: a proxima PALAVRA dele, no relogio dele. Sem isto o
        # cue esperava pela leitura seguinte do UIA e a frase entrava de uma vez.
        if self._cue is not None:
            ahead = self._cue.next_clock(now)
            if ahead is not None:
                step = max(word_fade.FRAME_S, float(ahead) - now)
                delay = step if delay is None else min(delay, step)
        # ── O ARRASTO TAMBEM ARMA O TICK (2026-11-08) ───────────────────────
        # Tres razoes novas, nenhuma delas um timer proprio:
        #   * com o Ctrl carregado ha' uma pulsacao para desenhar (30 Hz);
        #   * a arrastar, a janela tem de seguir o cursor (tecto de 240 Hz);
        #   * com a legenda no ecra, um poll lento (10 Hz) e' o que permite VER
        #     o Ctrl descer com a legenda parada -- sem ele nao ha' tick nenhum
        #     nesse estado. Este ultimo NAO repinta: `_tick` distingue-os por
        #     `_tick_content`.
        self._tick_content = delay is not None
        # O PRAZO DO CONTEUDO E' UM SO', no relogio do frame, e ele e' o que
        # `_tick` consulta antes de pagar uma pintura. O `pace` abaixo pode ser
        # MAIS CURTO (o poll do arrasto a 240 Hz): nesse caso o tick so' le' o
        # rato, e a pintura espera por este prazo. Sem esta separacao o poll de
        # 4 ms herdava a decisao "ha' conteudo" e pintava 240 vezes por segundo
        # (o orcamento de CPU limitava a 34 Hz e o arrasto perdia o tecto).
        self._content_due_at = (None if delay is None
                                else _frame_now() + max(0.0, float(delay)))
        if getattr(self, '_drag_dragging', False):
            pace = caption_drag.DRAG_FRAME_S
        elif getattr(self, '_drag_armed', False):
            pace = caption_drag.PULSE_FRAME_S
        elif getattr(self, 'hwnd', None) and getattr(self, 'visible', False):
            pace = caption_drag.POLL_S
        else:
            pace = None
        if pace is not None:
            delay = pace if delay is None else min(delay, pace)
        return delay

    def _arm_tick(self):
        """Agenda o proximo frame. Sem nada a mudar, nao arma nada -- e o fio do
        relogio nao fica a girar num ecra parado (espera no `Event`)."""
        _timer_period(True, self.log)
        delay = self._next_delay()
        if delay is not None:
            # O ORCAMENTO DE PINTURA VALE PARA O QUADRO QUE PINTA, nao para o
            # poll. Um tick de poll a 240 Hz custa tres leituras de teclado e
            # `GetWindowRect` (~microssegundos); aplicar-lhe o piso de 29 ms da
            # pintura limitava o ARRASTO a 34 Hz -- a taxa que o dono pediu
            # (240 Hz) ficava no tecto e nunca chegava ao cursor.
            #
            # `due` ausente = objeto de oraculo/legado (o `_make` do
            # `caption-tick-thread-oracle` substitui `_next_delay`): mantem o
            # comportamento antigo, em que todo tick era um quadro.
            due = getattr(self, '_content_due_at', 'missing')
            if isinstance(due, str):
                paint_frame = True
            elif due is None:
                paint_frame = bool(getattr(self, '_drag_armed', False)
                                   and not getattr(self, '_drag_dragging', False))
            else:
                now = _frame_now()
                paint_frame = (due <= now + 0.001
                               or (due - now) <= float(delay) + 0.001
                               # O PULSO DO CTRL TAMBEM E' UM QUADRO QUE PINTA
                               # (2026-11-09, revisao D1): sem esta condicao um
                               # conteudo com o proximo prazo longe deixava o
                               # pulso de 30 Hz fora do orcamento de pintura.
                               or bool(getattr(self, '_drag_armed', False)
                                       and not getattr(self, '_drag_dragging',
                                                       False)))
            if paint_frame:
                delay = self._limit_by_paint(delay)
        self._arm_at(delay)

    def _arm_at(self, delay):
        """Escreve o prazo (`delay`, ou `None`) e acorda o fio do relogio.

        O CADEADO E' O DA AGENDA (`_sched_lock`), NAO O DA PINTURA. Ordem do
        dono, verbatim: *"segurar o ctrl pra mover a legenda, até o ctrl fazer
        efeito, DEMORA PRA CARALHO, quando o sistema ta sob carga. ARRUMA."* O
        `self.lock` esta' tomado pelo `set_text`/`_update` do shell pelo custo
        medido de 31,75 ms (`CAPTION_DRAG_RATE ... paint_ms=31.75`); esperar por
        ele aqui atrasava o ARME seguinte em exactamente esse custo, e o poll do
        arrasto perdia o compasso. Medido no `caption-drag-oracle` P16: com a
        pintura a segurar o cadeado por 300 ms, o codigo real entrega ~60 polls
        nessa janela e o mutante que poem a agenda a esperar entrega ZERO.
        """
        sched = _guard(self, '_sched_lock')
        if delay is None:
            with sched:
                self._tick_deadline = 0.0
            self._tick_event.set()
            return
        with sched:
            self._tick_gen += 1
            self._tick_deadline = _frame_now() + max(0.001, float(delay))
            self._tick_wake_gen = self._tick_gen
        if self._tick_thread is None or not self._tick_thread.is_alive():
            self._tick_thread = threading.Thread(target=self._tick_loop,
                                                 name='sotto-caption-tick',
                                                 daemon=True)
            self._tick_thread.start()
        self._tick_event.set()

    def _limit_by_paint(self, delay):
        """O PEDIDO DE FRAME NAO PODE CUSTAR MAIS DO QUE O ORCAMENTO DE CPU DELE.

        Duas ordens do dono, e a segunda nasceu de uma medicao que a primeira
        deixou passar.

        1) Dono, 2026-11-08: *"acho que a animacao da legenda pode ir ate 240hz"*.
           O tecto foi levantado (`word_fade.FRAME_S` = 1/240), mas um tecto nao
           e' uma taxa: `_premultiplied_bitmap` re-cria o caminho do texto com
           contorno a cada quadro e mede **11,6 ms de p50** no tamanho real da
           caixa.

        2) DOIS DEFEITOS, e o recibo desta casa separa-os porque um deles nunca
           chegou a correr no processo vivo.

           a) O QUE A INSTANCIA VIVA CORRIA (pid 42572, medido 2026-11-08):
              `git show 7ec728d^:app/webview/word_fade.py` da' `FRAME_S = 1/60`
              e ZERO `_limit_by_paint` -- o laco pedia um quadro a cada 16,7 ms
              sem olhar ao custo, e com a pintura a 11,6 ms o piso e' 69 % de um
              nucleo. O instrumento externo mediu
              `SHELL-THREAD-BUDGET pid=42572 total=103.4% top=tid 48064
              sotto-caption-tick=93.6%`, reprodutivel em duas amostras: o stutter
              que o dono sentiu era este laco.

           b) O QUE A PRIMEIRA VERSAO DESTA FUNCAO FARIA: periodo IGUAL ao custo
              (`cost * 1.02`). Um laco que dorme exactamente o tempo que
              trabalha gasta **100 % de um nucleo por construcao** -- ela foi
              escrita e commitada horas antes deste docstring, e o processo vivo
              era anterior a ela (a etiqueta `SHELL_CODE_ID` do log prova-o), logo
              **nao foi ela que o dono sentiu**. Fica escrito porque e' a classe
              que o orcamento existe para impedir.

        A regra passa a ser ORCAMENTO, nao custo: o periodo e'
        `cost / CAPTION_FRAME_BUDGET`, ou seja a pintura pode ocupar no maximo
        40 % de um nucleo. Com o custo medido de 11,6 ms isso da' 29 ms por
        quadro (34 Hz) e 40 % de nucleo; com a pintura curada a 2 ms da' 5 ms
        (200 Hz) -- a taxa sobe quando o quadro fica barato, que e' a ordem do
        dono, e nunca passa de 40 % do nucleo.

        O `cost` E' O TICK INTEIRO, NAO A PINTURA (2026-11-17). Medido na
        instancia viva (pid 34520,
        `shell-thread-cpu.py 34520 --seconds 8`: `sotto-caption-tick` a 71,7 %
        de um nucleo) enquanto o log `CAPTION_FRAME_LIMIT` declarava 40 %: a
        conta antiga so' via o `_update` (6,59-8,71 ms) e o `_poll_drag`, a
        tentativa de `self.lock` e o arme do tick seguinte eram pagos POR FORA
        do divisor. O numero certo e' `_paint_frame_cost_s`, medido do inicio do
        `_tick` ao fim do arme no ultimo tick que pintou (`CAPTION_TICK_COST`
        publica a separacao poll/paint/tick).

        Quando ela morde, o log diz os numeros (uma linha a cada 5 s, nao por
        quadro) para o limite ser medivel e nao uma opiniao.
        """
        cost = float(getattr(self, '_paint_frame_cost_s', 0.0) or 0.0)
        if cost <= 0.0:
            # NENHUM TICK MEDIDO AINDA (ou um probe de oraculo que so' injecta o
            # custo da pintura): o divisor nunca fica abaixo da pintura. Num
            # overlay real o primeiro tick que pinta escreve o tick inteiro, e
            # `tick >= paint` sempre -- logo este ramo nao muda a producao.
            cost = float(getattr(self, '_paint_cost_s', 0.0) or 0.0)
        if cost <= 0.0:
            return delay
        floor = cost / CAPTION_FRAME_BUDGET
        if delay >= floor:
            return delay
        now = _frame_now()
        if now - float(getattr(self, '_paint_limit_logged', 0.0)) >= 5.0:
            self._paint_limit_logged = now
            self.log('CAPTION_FRAME_LIMIT want_hz=%.0f paint_ms=%.2f tick_ms=%.2f '
                 'budget=%.2f rate_hz=%.0f'
                 % (1.0 / max(1e-6, float(delay)),
                    float(getattr(self, '_paint_cost_s', 0.0)) * 1000.0,
                    cost * 1000.0, CAPTION_FRAME_BUDGET,
                    1.0 / max(1e-6, floor)))
        return floor

    def _tick_loop(self):
        """O UNICO fio do relogio: dorme ate' ao prazo, acorda, pinta, repete."""
        sched = _guard(self, '_sched_lock')
        while not self._tick_stop:
            with sched:
                deadline = self._tick_deadline
                gen = getattr(self, '_tick_wake_gen', self._tick_gen)
            if not deadline:
                # Nada armado: a resolucao do relogio volta ao que era. Sem
                # isto o `timeBeginPeriod(1)` ficaria a gastar bateria da
                # maquina do dono por uma animacao que ja' acabou.
                _timer_period(False, self.log)
                self._tick_event.wait(1.0)
                self._tick_event.clear()
                continue
            left = deadline - _frame_now()
            if left > 0.0:
                # O ULTIMO TRECHO E' `sleep`, NAO `Event.wait` -- MEDIDO
                # 2026-11-08 nesta maquina: `Event.wait(4,167 ms)` devolve com
                # 5,03 ms de minimo (192 Hz de tecto) enquanto `time.sleep(4 ms)`
                # devolve em 4,17 ms de p50 (239 Hz). O `Event` serve para
                # acordar cedo quando o prazo muda; abaixo de 5 ms quem dorme e'
                # o `sleep`, senao o tecto de 240 Hz nunca e' alcancado.
                if left > 0.005:
                    signalled = self._tick_event.wait(min(left, 1.0))
                    self._tick_event.clear()
                    if signalled:
                        continue      # prazo mudou: recalcula em vez de pintar
                    left = deadline - _frame_now()
                    if left > 0.0:
                        continue
                else:
                    time.sleep(max(0.0, left))
                    # O `set()` que o `_arm_tick` deixou no evento e' o aviso que
                    # ACABAMOS de acordar para ele: consumido aqui, sem uma
                    # segunda volta. Medido: sem esta linha cada frame pagava
                    # dois sonos e a taxa do relogio caia a ~127 Hz.
                    self._tick_event.clear()
                    # SO' SE AINDA FALTA UM MILISSEGUNDO INTEIRO. Medido: um
                    # `time.sleep` abaixo de 1 ms e' arredondado para o grao do
                    # timer (15,6 ms com a resolucao por omissao), portanto
                    # voltar ao topo para dormir a ultima migalha custava um
                    # quadro inteiro por frame -- a taxa caia a 62 Hz. Chegar
                    # 0,2 ms cedo a um quadro nao existe no ecra.
                    if deadline - _frame_now() > 0.001:
                        continue
            with sched:
                if gen != self._tick_gen:
                    # UM PRAZO ORFAO NAO SE HONRA E NAO SE REPETE (2026-11-23):
                    # a geracao foi trocada por quem nao limpou o prazo. Deixar
                    # o prazo aqui faz esta volta nunca ser honrada e nunca
                    # dormir -- o laco volta ao topo com `left <= 0` e gira a
                    # 100 % de um nucleo. Retira-se SO' o prazo DESTA volta.
                    if self._tick_deadline == deadline:
                        self._tick_deadline = 0.0
                    continue
                if self._tick_deadline != deadline:
                    continue
                self._tick_deadline = 0.0
            self._tick(gen)

    def _arm_poll(self, retry=False):
        """O ARME SEGUINTE DE UM TICK QUE NAO PINTOU -- sem tocar na pintura.

        Ate' 2026-11-15 este caminho chamava o `_arm_tick` inteiro, que
        recalculava o prazo do CONTEUDO (`_next_delay`, `word_fade`) e passava
        pelo orcamento. Isso tornava o poll refem do relogio do texto; agora o
        poll usa o ritmo do ESTADO (`DRAG_FRAME_S` a arrastar, `PULSE_FRAME_S`
        com Ctrl, `POLL_S` parado) e so' olha para o prazo do conteudo ja'
        calculado (`_content_due_at`), nunca o recalcula. `retry` e' o caminho de
        emergencia: a pintura do shell estava a correr e o conteudo ficou para
        ja' -- 4 ms depois tenta outra vez.
        """
        now = _frame_now()
        if getattr(self, '_drag_dragging', False):
            delay = caption_drag.DRAG_FRAME_S
        elif getattr(self, '_drag_armed', False):
            delay = caption_drag.PULSE_FRAME_S
        elif getattr(self, 'hwnd', None) and getattr(self, 'visible', False):
            delay = caption_drag.POLL_S
        else:
            delay = None
        due = getattr(self, '_content_due_at', None)
        if isinstance(due, float):
            left = max(0.0, due - now)
            # O PISO DA PINTURA SO' VALE QUANDO O CONTEUDO E' QUE MANDA: um
            # quadro de conteudo vencido custa a pintura, mas o poll a 240 Hz
            # nao. Aplicar o piso aqui e depois perder por ser maior que o
            # compasso do arrasto so' escreveria a linha `CAPTION_FRAME_LIMIT`
            # a cada 5 s sobre um limite que ninguem aplicou.
            if delay is None or left < delay:
                delay = self._limit_by_paint(left)
        if retry and (delay is None or delay > caption_drag.DRAG_FRAME_S):
            delay = caption_drag.DRAG_FRAME_S
        if delay is not None:
            _timer_period(True, self.log)
        self._arm_at(delay)

    def _tick(self, gen):
        # O TICK INTEIRO E' O QUE O ORCAMENTO DIVIDE (2026-11-17): o cronometro
        # comeca AQUI e fecha no `finally` do fim, depois de o arme seguinte ter
        # corrido. `_poll_s` separa a parcela do poll para o log dizer QUAL fase
        # paga o excedente -- medido, nao suposto.
        _tick_t0 = _frame_now()
        _poll_s = 0.0
        _painted = False
        try:
            # ── O POLL FORA DO CADEADO DA PINTURA (2026-11-15) ──────────────
            # Ordem do dono, verbatim: *"segurar o ctrl pra mover a legenda,
            # até o ctrl fazer efeito, DEMORA PRA CARALHO, quando o sistema ta
            # sob carga. ARRUMA."* O `self.lock` e' o MESMO que o shell toma no
            # `set_text`->`_update`, pelo custo medido de 31,75 ms
            # (`CAPTION_DRAG_RATE ... paint_ms=31.75`, `_main/webview-run.log`);
            # com o poll la' dentro, a taxa entregue foi 4,2 Hz no mesmo log.
            # O poll do arrasto tem cadeado PROPRIO (`_poll_lock`), que a
            # pintura nunca toma: enquanto o Ctrl esta' em baixo ou um arrasto
            # decorre, a janela segue o rato sem esperar pintura nenhuma.
            _poll_t0 = _frame_now()
            with _guard(self, '_poll_lock'):
                moved = self._poll_drag()
                armed = getattr(self, '_drag_armed', False)
                dragging = getattr(self, '_drag_dragging', False)
            _poll_s = _frame_now() - _poll_t0
            if gen != self._tick_gen:
                # Um arme mais novo ja' tomou o lugar deste: o poll acima
                # correu de qualquer forma, mas pintar seria pintar o passado.
                return
            # QUEM REPINTA: conteudo VENCIDO, o gesto a mudar, ou a pulsacao.
            # A arrastar com o rato parado nao ha' nada a mudar no bitmap
            # (o contorno ja' esta' solido e o `SetWindowPos` ja' moveu a
            # janela) -- o tick continua a ler o rato, mas nao paga render.
            # O `moved` NAO repinta durante o arrasto: a janela ja' seguiu o
            # cursor no `_poll_drag`, e repintar aqui prendia o arrasto ao
            # custo da pintura (11,6 ms = 34 Hz) em vez do poll barato.
            due = getattr(self, '_content_due_at', 'missing')
            if isinstance(due, str):
                content_now = bool(getattr(self, '_tick_content', True))
            elif due is None:
                content_now = False
            else:
                content_now = _frame_now() + 0.001 >= float(due)
            if not (content_now or (moved and not dragging)
                    or (armed and not dragging)):
                # Um tick que so' existiu para poll nao paga um render:
                # rearma (o poll seguinte) sem tocar no bitmap.
                self._arm_poll()
                return
            # A PINTURA ESPERA, O POLL NAO (2026-11-15). Se o shell ja' esta' a
            # pintar (`set_text`), este quadro nao se enfileira atras dele: o
            # poll do proximo tick volta a tentar, e o arrasto nao perde o
            # compasso por causa de um bitmap que ja' vai ser substituido.
            if not self.lock.acquire(False):
                self._arm_poll(retry=True)
                return
            try:
                # O CUSTO DA PINTURA E' O QUE DECIDE A TAXA (ver
                # `_limit_by_paint`): medido aqui, no caminho real.
                _t0 = _frame_now()
                self._update()
                _cost = _frame_now() - _t0
                self._paint_cost_s = _cost
                _painted = True
                if dragging:
                    with _guard(self, '_poll_lock'):
                        self._drag_paints = int(getattr(self, '_drag_paints', 0)) + 1
                        self._drag_paint_s = (float(getattr(self, '_drag_paint_s', 0.0))
                                              + _cost)
            finally:
                self.lock.release()
        except Exception as exc:  # noqa: BLE001 -- see the fail-open rule
            self._fail_open(exc)
        finally:
            self._note_tick_cost(_frame_now() - _tick_t0, _poll_s, _painted)

    def _note_tick_cost(self, tick_s, poll_s, painted):
        """Grava o custo do tick INTEIRO e publica a separacao a cada 5 s.

        2026-11-17: o `CAPTION_FRAME_LIMIT` declarava 40 % de nucleo enquanto o
        instrumento externo media 71,7 % no fio `sotto-caption-tick` (pid 34520).
        A conta do limite so' via o `_update`; o resto do tick era invisivel.
        Esta funcao mede o que o fio GASTA de facto e diz de que fase vem:

          poll_ms  o `_poll_drag` (Win32/`drag_plan`) sob o `_poll_lock`, do
                   MESMO tick que a linha descreve;
          paint_ms o `_update` desse mesmo tick;
          tick_ms  do inicio desse `_tick` ao fim do arme seguinte -- a soma que
                   o `_limit_by_paint` divide pelo orcamento.

        As tres parcelas vem do ULTIMO TICK QUE PINTOU, e nao do ultimo tick:
        um tick de poll barato ao lado do `paint_ms` do quadro anterior dava
        `tick_ms < paint_ms`, uma linha que mente sobre a soma.

        `rate_hz` e' a taxa ENTREGUE na janela de 5 s (quadros contados / tempo),
        nao o pedido. A primeira janela so' abre o relogio: sem uma janela
        completa a taxa seria a idade do `perf_counter`.
        """
        self._tick_cost_s = float(tick_s)
        self._tick_poll_s = float(poll_s)
        if painted:
            # SO' O TICK QUE PINTOU alimenta o orcamento: o proximo pedido de
            # quadro e' limitado pelo custo do ultimo quadro, nao pelo de um poll
            # barato que passou pelo meio.
            self._paint_frame_cost_s = float(tick_s)
            self._paint_frame_poll_s = float(poll_s)
            self._paint_frame_paint_s = float(getattr(self, '_paint_cost_s', 0.0))
        self._tick_cost_n = int(getattr(self, '_tick_cost_n', 0)) + 1
        now = _frame_now()
        last = float(getattr(self, '_tick_cost_logged', 0.0) or 0.0)
        if last <= 0.0:
            self._tick_cost_logged = now
            return
        elapsed = now - last
        if elapsed < 5.0:
            return
        count = self._tick_cost_n
        self._tick_cost_logged = now
        self._tick_cost_n = 0
        try:
            self.log('CAPTION_TICK_COST poll_ms=%.2f paint_ms=%.2f tick_ms=%.2f '
                     'rate_hz=%.0f'
                     % (float(getattr(self, '_paint_frame_poll_s', 0.0)) * 1000.0,
                        float(getattr(self, '_paint_frame_paint_s', 0.0)) * 1000.0,
                        float(getattr(self, '_paint_frame_cost_s', 0.0)) * 1000.0,
                        (count / elapsed) if elapsed > 0.0 else 0.0))
        except Exception:  # noqa: BLE001 -- medir nunca parte o tick
            pass

    # ── O ARRASTO: UM POLL NO TICK QUE JA' EXISTE ───────────────────────────
    def _work_area(self):
        """A area de trabalho em que a legenda vive, num dict `x/y/width/height`.

        E' a mesma que o shell entrega em `set_work_area` -- o arrasto fica
        preso a' MESMA area em que a legenda e' centrada, para nao haver duas
        verdades sobre onde acaba o ecra. So' quando ela nao veio (0x0) se
        pergunta ao monitor da janela.
        """
        try:
            out = {'x': int(self.work.get('x', 0) or 0),
                   'y': int(self.work.get('y', 0) or 0),
                   'width': int(self.work.get('width', 0) or 0),
                   'height': int(self.work.get('height', 0) or 0)}
        except (AttributeError, TypeError, ValueError):
            out = {'x': 0, 'y': 0, 'width': 0, 'height': 0}
        if out['width'] <= 0 or out['height'] <= 0:
            return _monitor_work(getattr(self, 'hwnd', None)) or {
                'x': 0, 'y': 0, 'width': 1920, 'height': 1080}
        return out

    def _drag_reset(self):
        """Esquece o gesto em curso SEM gravar -- a legenda escondida nao se arrasta."""
        with _guard(self, '_poll_lock'):
            self._drag = caption_drag.DragState(
                offset=getattr(self, '_drag_offset', (0, 0)))
            self._drag_armed = False
            self._drag_dragging = False
            self._drag_pos = None

    def _poll_drag(self):
        """Le' Ctrl/botao/cursor NESTE tick e aplica a decisao. Devolve `moved`.

        Sem janela ou com a legenda escondida nao ha' o que agarrar: o gesto e'
        esquecido (sem gravar) e o tick nao paga nada. Sem hook, sem fio novo,
        sem `SetWindowsHookEx`: tres `Get*` baratos no fio do relogio que a
        legenda ja' tem -- o padrao do arrasto de edicao da strip.
        """
        if not getattr(self, 'hwnd', None) or not getattr(self, 'visible', False):
            if getattr(self, '_drag_armed', False) or getattr(
                    self, '_drag_dragging', False):
                self._drag_reset()
                return True
            return False
        ctrl = _ctrl_held()
        lbtn = _lbutton_held()
        cursor = _cursor_px()
        rect = _window_rect(self.hwnd)
        if cursor is None or rect is None:
            return False
        decision = caption_drag.drag_plan(ctrl, lbtn, cursor, rect,
                                          self._work_area(),
                                          offset=self._drag_offset,
                                          state=self._drag)
        was_dragging = bool(getattr(self, '_drag_dragging', False))
        if decision.dragging and not was_dragging:
            # O GESTO COMECOU: a medicao e' DESTE arrasto, nao da instancia.
            self._drag_ticks = 0
            self._drag_moves = 0
            self._drag_paints = 0
            self._drag_paint_s = 0.0
            self._drag_t0 = _frame_now()
        if decision.dragging:
            self._drag_ticks = int(getattr(self, '_drag_ticks', 0)) + 1
        self._drag = decision.state
        self._drag_armed = decision.armed
        self._drag_dragging = decision.dragging
        self._drag_offset = decision.offset
        self._drag_pos = decision.pos if decision.dragging else None
        if decision.dragging and decision.pos != (rect[0], rect[1]):
            # A JANELA SEGUE O CURSOR JA' NESTE TICK, sem esperar pela pintura:
            # e' o `SetWindowPos` que tira o atraso visivel do arrasto.
            _user32.SetWindowPos(self.hwnd, None, int(decision.pos[0]),
                                 int(decision.pos[1]), 0, 0,
                                 SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOZORDER)
            self._drag_moves = int(getattr(self, '_drag_moves', 0)) + 1
        if decision.persist:
            saved = caption_drag.save_offset(decision.offset)
            self.log('CAPTION_DRAG_OFFSET x=%d y=%d saved=%s'
                     % (int(decision.offset[0]), int(decision.offset[1]),
                        str(bool(saved)).lower()))
            # A TAXA ENTREGUE, medida no relogio do frame -- nao o tecto. O
            # `target_hz` e' o pedido (240); o `hz` e' o que esta maquina deu,
            # com o numero de pinturas que o poll NAO pagou.
            _elapsed = _frame_now() - float(getattr(self, '_drag_t0', 0.0) or 0.0)
            if _elapsed > 0.0:
                _paints = int(getattr(self, '_drag_paints', 0))
                self.log('CAPTION_DRAG_RATE ticks=%d moves=%d paints=%d '
                         'seconds=%.3f hz=%.1f target_hz=%d paint_ms=%.2f'
                         % (int(getattr(self, '_drag_ticks', 0)),
                            int(getattr(self, '_drag_moves', 0)), _paints,
                            _elapsed,
                            int(getattr(self, '_drag_ticks', 0)) / _elapsed,
                            int(caption_drag.DRAG_FRAME_HZ),
                            (1000.0 * float(getattr(self, '_drag_paint_s', 0.0))
                             / _paints) if _paints else 0.0))
        return bool(decision.changed)

    def _paint_drag_outline(self, bmp, width, height):
        """Liga o adaptador GDI+ ao bitmap DESTE frame e desenha a marca.

        Uma falha aqui nao pode matar a legenda: o `except` registra e o bitmap
        segue sem a marca. O `Graphics` e' o unico objecto por frame -- o bitmap
        e' novo em cada um, logo nao ha' como guarda-lo como o `Pen`.
        """
        try:
            from System.Drawing import Graphics
            from System.Drawing.Drawing2D import SmoothingMode
            if self._drag_canvas is None:
                self._drag_canvas = _DragCanvas()
            gfx = Graphics.FromImage(bmp)
            try:
                gfx.SmoothingMode = SmoothingMode.AntiAlias
                self._drag_canvas.bind(gfx)
                return self._paint_drag_affordance(
                    self._drag_canvas, width, height, self.scale)
            finally:
                gfx.Dispose()
        except Exception as exc:  # noqa: BLE001 -- a marca e' um extra
            self.log('CAPTION_DRAG_MARK_FAILED error=%r' % (exc,))
            return None

    def _paint_drag_affordance(self, canvas, width, height, scale=1.0,
                               now=None, pulse=None):
        """A MARCA MINIMA "DA' PRA ARRASTAR" -- desenhada, nao prometida.

        Um contorno ACCENT (`caption_drag.ACCENT_RGB`, o `--accent-from` do
        painel) por dentro da borda do bitmap da legenda. Pulsa devagar com o
        Ctrl carregado (alfa `PULSE_MIN_ALPHA`..255) e fica SOLIDO enquanto se
        arrasta -- e' a diferenca entre "podes agarrar" e "estas a agarrar".

        COM O CTRL LEVANTADO NAO TOCA NO CANVAS. E' essa a metade que o oraculo
        `_main/caption-drag-oracle.py` conta em pixeis: zero alteracoes na banda
        da borda.

        O canvas e' um protocolo de UMA chamada (`outline(x, y, w, h, colour,
        thickness)`), para o mesmo metodo correr contra o GDI+ real e contra um
        canvas falso de pixeis sem saber a diferenca. `pulse` e' a mesma costura
        de um parametro so' (o `FADE_ON` e' o precedente neste ficheiro): o
        oraculo entrega uma pulsacao mutada e exige o braco vermelho, sem tocar
        no modulo que embarca.
        """
        if not getattr(self, '_drag_armed', False):
            return None
        dragging = bool(getattr(self, '_drag_dragging', False))
        alpha = (pulse or caption_drag.pulse_alpha)(
            time.monotonic() if now is None else now, dragging)
        try:
            scale = float(scale or 1.0)
        except (TypeError, ValueError):
            scale = 1.0
        thickness = max(1.0, round(3.0 * scale))
        inset = max(1.0, round(2.0 * scale)) + thickness / 2.0
        w = float(width) - 2.0 * inset
        h = float(height) - 2.0 * inset
        if w <= 1.0 or h <= 1.0:
            return None
        colour = caption_drag.ACCENT_RGB + (int(alpha),)
        canvas.outline(inset, inset, w, h, colour, thickness)
        return (inset, inset, w, h)

    def _plate_signature(self, width, height):
        """A PLACA DESTE QUADRO EM NUMERO: `(on, w, h, alpha)`.

        Ordem do dono, 2026-11-12, verbatim: *"por algum motivo, o background
        da legenda atrasou pra aparecer. entao a legenda ficou uns segundos sem
        background."* O glifo e a placa saem do MESMO bitmap, logo a unica
        forma de existir texto sem placa e' o tema ainda nao ter chegado a esta
        janela -- e ate' agora isso nao tinha numero nenhum no log.

        Devolve `(1, w, h, a)` quando a placa entra no bitmap e `(0, 0, 0, a)`
        quando nao entra. A geometria e' a MESMA conta de
        `overlay_paint._paint_bitmap` (a placa entra `EDGE_PX` para dentro), e
        por isso ela e' lida de `overlay_paint` em vez de recalculada aqui.
        """
        try:
            geo = _geom(self.scale, self.theme, **self._caption_style())
        except Exception:                     # noqa: BLE001 -- medir nunca parte
            return (0, 0, 0, 0)
        t = geo['t']
        ink = t.get('plate')
        if ink and int(ink[3]) > 0:
            inset = float(_EDGE_PX)
            return (1, int(max(1, width - 2 * inset)),
                    int(max(1, height - 2 * inset)), int(ink[3]))
        return (0, 0, 0, int(ink[3]) if ink else 0)

    def _log_plate(self, width, height, has_text):
        """UMA linha por MUDANCA de placa -- com o numero do quadro ao lado.

        A forma e' a do `CAPTION_PAINT_SURFACE` (`ms=`/`epoch=`) de proposito:
        o instrumento que le' a linha do tempo da legenda cruza esta linha com
        a pintura pela HORA, e duas formas diferentes obrigariam a duas
        gramaticas no mesmo leitor.

        `plate_px` e' a caixa da placa (nao a da janela): e' o buraco que o dono
        ve' quando a placa falta. `text_n=` diz em que quadro o TEXTO apareceu
        pela primeira vez, para o atraso ser um numero -- quando a placa entra
        num quadro com `plate_n > text_n`, a legenda esteve (plate_n - text_n)
        quadros no ecra sem fundo.
        """
        self._paint_n = int(getattr(self, '_paint_n', 0)) + 1
        if has_text and self._text_paint_n is None:
            self._text_paint_n = self._paint_n
            self._text_paint_at = time.monotonic()
        sig = self._plate_signature(width, height)
        if has_text:
            sig = sig + (1,)
        else:
            sig = sig + (0,)
        if sig == getattr(self, '_plate_state', None):
            return
        self._plate_state = sig
        if has_text and self._text_paint_n is not None:
            lag_n = self._paint_n - self._text_paint_n
            lag_ms = int(round((time.monotonic()
                                - float(self._text_paint_at or 0.0)) * 1000.0))
        else:
            lag_n = 0
            lag_ms = 0
        self.log('CAPTION_PLATE plate=%s plate_px=%dx%d plate_alpha=%d '
                 'text=%d paint_n=%d text_n=%s lag_frames=%d lag_ms=%d'
                 % ('on' if sig[0] else 'off', sig[1], sig[2], sig[3], sig[4],
                    self._paint_n,
                    '-' if self._text_paint_n is None else self._text_paint_n,
                    lag_n, lag_ms))

    def _update(self):
        if not self.hwnd:
            return False
        # NOT `self.text`: o MOTOR decide o que esta' desenhado neste instante (o
        # prefixo revelado de cada linha) e o alfa de cada uma. Esta chamada e' a
        # diferenca entre "tres palavras num quadro" e "tres palavras, uma a uma".
        text, alphas = self._display()
        previous = self.previous or ""
        if not text and not previous:
            # O QUADRO SAIU SEM TEXTO (2026-11-12): a placa tambem sai do ecra, e
            # isso e' um ESTADO que o log tem de mostrar -- sem esta linha, um
            # leitor da linha do tempo nao distingue "placa esquecida no ecra"
            # de "placa removida com os pixels".
            try:
                self._log_plate(0, 0, False)
            except Exception:                 # noqa: BLE001 -- medir nunca parte
                pass
            if self._cue is not None:
                # O cue existe mas ainda nao tem palavra revelada (o relogio do
                # player esta' antes do `start` da linha, ou entre duas linhas):
                # saem os PIXELS, fica o CUE. `hide()` limpava o estado -- e nao
                # arma tick nenhum, logo a revelacao nunca voltava.
                self._blank_pixels()
            else:
                self.hide()
            self._arm_tick()
            return True
        # ONE layout, computed once, handed to the bitmap. `rows=PLAYER_ROWS`:
        # no ROLL-UP desenha-se `PLAYER_ROWS + 1` linhas mas a CAIXA fica no
        # tamanho da janela -- e' o conteudo que sobe dentro dela.
        cur_lines, prev_line, width, height, _scrolled = _layout(
            text, previous, self.scale, self.work.get('width', 1920),
            self.theme, **self._caption_style(),
            rows=PLAYER_ROWS if str(text or '').count('\n') >= PLAYER_ROWS else None)
        # OS ALFAS SAO DAS LINHAS QUE `_layout` VAI DESENHAR; a comparacao e' por
        # indice e os dois lados vem do MESMO texto (alfa sobrante e' ignorado).
        if alphas and len(alphas) != len(cur_lines):
            alphas = list(alphas[:len(cur_lines)]) + [255] * max(
                0, len(cur_lines) - len(alphas))
        bmp = _premultiplied_bitmap(cur_lines, prev_line, width, height,
                                    self.scale, self.theme, alphas,
                                    roll=self._roll, **self._caption_style())
        # A MARCA "DA' PRA ARRASTAR" DENTRO DO MESMO BITMAP (2026-11-08). Com o
        # Ctrl carregado o contorno pulsa; a arrastar fica solido; com ele
        # levantado nenhum pixel e' tocado. Nao ha' janela nem bitmap extra: e'
        # este bitmap que ja' ia ser composto.
        # A PLACA, EM NUMERO, ANTES do blit (2026-11-12): mede o que ESTE
        # quadro levou, e so' escreve quando o estado muda (`_log_plate`).
        try:
            self._log_plate(width, height, bool(text))
        except Exception:                     # noqa: BLE001 -- medir nunca parte
            pass
        if getattr(self, '_drag_armed', False):
            self._paint_drag_outline(bmp, width, height)
        try:
            from System.Drawing.Imaging import ImageLockMode, PixelFormat
            from System.Drawing import Rectangle
            data = bmp.LockBits(
                Rectangle(0, 0, width, height),
                ImageLockMode.ReadOnly, PixelFormat.Format32bppPArgb)
            stride = abs(int(data.Stride))
            size = stride * height
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = BI_RGB
            bits = ctypes.c_void_p()
            hdc_screen = _user32.GetDC(None)
            hdc_mem = _gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = _gdi32.CreateDIBSection(
                hdc_mem, ctypes.byref(bmi), DIB_RGB_COLORS,
                ctypes.byref(bits), None, 0)
            old = _gdi32.SelectObject(hdc_mem, hbmp)
            ctypes.memmove(bits, ctypes.c_void_p(int(data.Scan0.ToInt64())), size)
            bmp.UnlockBits(data)
            # A POSICAO: base centrada em baixo + o deslocamento do dono, sempre
            # presa a' area de trabalho. Durante o arrasto quem manda e' o
            # `_drag_pos` do poll (o cursor), e o deslocamento e' recalculado
            # contra a base DESTE frame -- assim um texto que muda de largura a
            # meio do arrasto nao faz a janela saltar ao largar.
            base_x = int(self.work.get('x', 0)
                         + (self.work.get('width', 1920) - width) / 2)
            base_y = int(self.work.get('y', 0) + self.work.get('height', 1080)
                         - height - 48 * self.scale)
            with _guard(self, '_poll_lock'):
                # O POLL ESCREVE ESTES QUATRO no fio do tick (desde 2026-11-15
                # fora do `self.lock`): ler o par aqui sem o cadeado do poll
                # podia casar o `x` de um tick com o `y` do seguinte e gravar um
                # deslocamento que ninguem pediu. O `self.lock` continua a
                # excluir os dois PINTORES -- este cadeado so' fecha a janela
                # em que o poll escreve.
                dragging = bool(getattr(self, '_drag_dragging', False))
                drag_pos = getattr(self, '_drag_pos', None)
                drag_offset = getattr(self, '_drag_offset', (0, 0))
                if dragging and drag_pos is not None:
                    x, y = int(drag_pos[0]), int(drag_pos[1])
                else:
                    x, y = caption_drag.clamp_pos(
                        (base_x + int(drag_offset[0]),
                         base_y + int(drag_offset[1])),
                        (width, height), self._work_area())
                self._drag_offset = (int(x - base_x), int(y - base_y))
            pt_dst = wt.POINT(x, y)
            size_dst = wt.SIZE(width, height)
            pt_src = wt.POINT(0, 0)
            fade = self._fade_alpha()
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, fade, AC_SRC_ALPHA)
            ok = _user32.UpdateLayeredWindow(
                self.hwnd, hdc_screen, ctypes.byref(pt_dst),
                ctypes.byref(size_dst), hdc_mem, ctypes.byref(pt_src),
                0, ctypes.byref(blend), ULW_ALPHA)
            # HA' PIXEL NOVO NO ECRA: o `show()` pode voltar a mostra-lo.
            self._blank = not bool(ok)
            _gdi32.SelectObject(hdc_mem, old)
            _gdi32.DeleteObject(hbmp)
            self._arm_tick()
            _gdi32.DeleteDC(hdc_mem)
            _user32.ReleaseDC(None, hdc_screen)
            if not ok:
                self.log(f"CAPTION_OVERLAY_UPDATE_FAILED "
                         f"error={ctypes.get_last_error()} size={width}x{height}")
            # O CARIMBO SO' DEPOIS DO `UpdateLayeredWindow` OK: antes nao ha'
            # pixel nenhum no ecra.
            self._log_land()
            return bool(ok)
        except Exception as exc:
            import traceback
            self.log(f"CAPTION_OVERLAY_RENDER_FAILED error={exc!r}\n"
                     f"{traceback.format_exc()}")
            return False
        finally:
            try:
                bmp.Dispose()
            except Exception:
                pass

    def set_text(self, text, previous="", instant=False, *, cue=None, late_s=0.0):
        """Uma legenda. `instant=True` e' a JANELA DO PLAYER: chega ja' revelada,
        linha a linha, e nada aqui a volta a temporizar.

        TRES FONTES, DOIS MOTORES (`youtube_reveal`):

          * `cue={...}` -- o caminho do YouTube COM O RELOGIO DELE. O payload traz
            as linhas do player com o instante de cada palavra (`rows`, a forma de
            `youtube_reveal.rows_from_cues`) e o instante do video em que foram
            lidas (`t`, com o `monotonic()` da leitura em `at`). O overlay revela
            palavra a palavra NO RELOGIO DO PLAYER e re-sincroniza a cada cue novo
            (ver `_PlayerCue`). `text` continua a ser o texto todo, para o
            `show()` e o `hide()` continuarem a valer.
          * `instant=True` SEM `cue` -- o texto chega ja' cortado e desenha-se
            inteiro. E' o comportamento historico; sem relogio nenhum nao ha'
            como revelar sem inventar tempo.
          * `instant=False` -- o ASR ao vivo. O texto CRESCE. O `LiveRows` da' a
            cada palavra o instante em que ela chegou, quebra as linhas com a
            regra do `caption_wrap` (a mesma de sempre: <= 2 linhas, nunca parte
            uma palavra) e o motor revela palavra a palavra ao compasso medido do
            YouTube -- e mostra as 2 linhas do ecra mais a que esta' a sair.

        A PALAVRA QUE NAO MUDOU NAO REAPARECE: `LiveRows.push` guarda o instante
        das palavras que continuam iguais no prefixo, por isso uma correccao do
        modelo no fim da frase nao reinicia a revelacao da frase inteira -- o
        defeito que `panel.js` descreve como *"a word that blinked and retyped on
        every fragment would be worse than no reveal at all"*. No caminho do cue
        o mesmo vem de graca: o relogio de cada palavra e' do PAYLOAD, logo um
        cue novo nao re-data nada.
        """
        with self.lock:
            self.previous = str(previous or "")
            full = str(text or "")
            words = full.split()
            changed = not _same_line(self.text, full)
            self.text = full
            if cue is not None:
                self._cue = self._cue_from(cue)
            elif instant:
                self._cue = None
                self._live = None
                self._row_alphas = None
            else:
                self._cue = None
                live = self._live_for()
                # O RELOGIO DA REVELACAO E' O DO AUDIO, NAO O DA CHEGADA
                # (2026-11-04). Dono, verbatim: *"a legenda do youtube ta fora de
                # sync. atrasada. depois faz um catch up super rapido e atrasa de
                # novo"*. A causa: `push(text, time.monotonic())` datava cada
                # palavra pelo instante em que o ASR a entregou, e o ASR entrega
                # tarde (`CAPTION_PAINT_LAG audio_ms=1567`), em lotes. Com o
                # relogio na chegada, a palavra nova nascia no futuro, o lote
                # seguinte era comprimido (`MAX_LAG_S`) e o ecra apanhava o atraso
                # de uma vez -- o dente de serra. `late_s` recua a ancora para
                # quando o audio foi falado: as palavras que ja' passaram aparecem
                # JUNTAS no sitio certo, e o resto segue ao compasso do YouTube.
                live.push(full, time.monotonic() - max(0.0, float(late_s or 0.0)))
            # A LINHA MUDOU: APARECE. Nao se arma fade nenhum -- ver
            # `_fade_alpha` (o dono mandou tirar; a linha do YouTube aparece).
            if changed and words and self.FADE_ON:
                self._fade_t0 = time.monotonic()
            return self._update()

    def _cue_from(self, payload):
        """O cue novo e o RESYNC do relogio (`_PlayerCue`), com o piso do anterior.

        O PISO SO' VALE NA MESMA LINHA DO TEMPO. Um seek para tras faz o cue novo
        comecar ANTES do antigo, e herdar o piso prendia a revelacao no instante
        de onde o video saiu -- a legenda ficava a falar do passado ate' ao fim do
        cue. `0,05 s` e' a folga para o mesmo cue relido com arredondamento.
        """
        old = self._cue
        try:
            rows = list((payload or {}).get('rows') or ())
            t = float((payload or {}).get('t'))
        except (AttributeError, TypeError, ValueError):
            self.log('CAPTION_CUE_INVALID payload=%r' % (payload,))
            return None
        at = (payload or {}).get('at')
        new = _PlayerCue(rows, t, at=at, rate=(payload or {}).get('rate'),
                         log=self.log)
        if not new.rows:
            # SEM LINHAS NAO HA' CUE: o overlay desenha o texto que recebeu, em
            # vez de ficar vazio -- um payload vazio e' o mesmo caso do
            # `CAPTION_CUE_INVALID`, so' que silencioso.
            self.log('CAPTION_CUE_EMPTY t=%.3f' % t)
            return None
        if old is not None and new.cue_t0 + 0.05 >= old.cue_t0:
            new.floor = old.clock()
        # O CUE QUE NUNCA CHEGOU A PINTAR: conta-se, nao se esconde (o
        # `cues_descartados` do `_main/youtube-land-oracle.py`).
        if old is not None and not old.logged:
            self.log('CAPTION_CUE_DROP cue_t0=%.3f reason=superseded'
                     % old.cue_t0)
        self._live = None
        self._row_alphas = None
        return new

    def _log_land(self):
        """O CARIMBO DA PINTURA DO CUE -- a linha que o `youtube-land-oracle` le.

        `lag_ms` e' (relogio do player na PRIMEIRA pintura) - (t0 do cue): quanto
        a NOSSA legenda entrou depois do player, no relogio do proprio video. Nao
        e' a idade do texto na fila (isso e' o `CAPTION_OVERLAY_LAG` do shell,
        medido em relogio de parede): dois numeros, dois desvios diferentes.
        """
        cue = self._cue
        if cue is None or cue.logged or cue.first_paint_t is None:
            return
        cue.logged = True
        lag_ms = int(round((cue.first_paint_t - cue.cue_t0) * 1000.0))
        self.log('CAPTION_LAND cue_t0=%.3f paint_t=%.3f lag_ms=%d rows=%d '
                 'words=%d text=%s'
                 % (cue.cue_t0, cue.first_paint_t, lag_ms,
                    len(cue.paint_texts),
                    sum(len(row.split()) for row in cue.paint_texts),
                    json.dumps(' '.join(cue.paint_texts)[:90])))

    def _live_for(self):
        """O motor da legenda ao vivo, criado uma vez."""
        import youtube_reveal
        if self._live is None:
            self._live = youtube_reveal.LiveRows(wrap=self._wrap_fn())
        return self._live

    def _wrap_fn(self):
        """A QUEBRA DE LINHA do YouTube, com a fonte e a largura REAIS.

        O `LiveRows` nao mede nada: pede as linhas a este callable. A regra e' a do
        `caption_wrap` -- a mesma que a legenda usa desde 2026-10-17: no maximo 2
        linhas no ecra, quebra numa costura natural, NUNCA parte uma palavra, e o
        tecto de 42 caracteres que o payload do YouTube tambem respeita (medido:
        a linha mais larga dos 19 eventos tem 42). A janela (2 linhas + a que sai)
        fica no motor, nao aqui: um `wrap` que devolvesse so' 2 linhas punha o
        roll-up a cargo da quebra, que e' o defeito que se esta' a curar.

        Le' `self.scale`/`self.work`/`self.theme` NO INSTANTE DA CHAMADA: um tema
        novo ou um monitor novo mudam a medida, e uma closure que os fixasse no
        momento em que foi criada quebrava a linha com a fonte errada para sempre.
        """
        import caption_wrap as cw

        def wrap(text):
            cur_w, budget = _measure_budget(self.scale,
                                            self.work.get('width') or 1920,
                                            self.theme)
            lines, _scrolled = cw.wrap(text, cur_w, budget,
                                       max_lines=cw.UNBOUNDED_LINES)
            return lines

        return wrap

    # ── O QUE ESTA' DESENHADO NESTE FRAME ───────────────────────────────────
    def _display(self):
        """`(texto, alfas)` deste frame -- do MOTOR quando ha' linha viva.

        O texto sai com uma linha por `\n` (`rows_text`), que e' o marcador que
        `_layout` le' para NAO re-quebrar o que ja' vem quebrado: a quebra e' do
        motor, e uma segunda quebra com outra regra e' como uma legenda ganha duas
        geometrias.
        """
        if self._cue is not None:
            # ── O CUE DO PLAYER, NO RELOGIO DO PLAYER (2026-11-03) ─────────────
            # A linha NAO aparece quando chega: aparece ate' onde o relogio do
            # video ja' chegou. `_cue_texts` le' o relogio de cada palavra do
            # payload, e `_log_land` carimba a primeira pintura (a metade
            # `paint_t` do `land_lag_ms`).
            import youtube_reveal
            texts = self._cue_texts()
            self._row_alphas = [255] * len(texts)
            if not texts:
                return "", None
            return youtube_reveal.rows_text(texts), self._row_alphas
        if self._cue is None and self._live is None:
            self._row_alphas = None
            self._roll = 0.0
            return self._display_text(), None
        import youtube_reveal
        now = time.monotonic()
        marks = self._live.frame(now)
        # O ROLL-UP NO CAMINHO DO ASR TAMBEM (2026-11-08). A ordem do dono nao
        # distingue a fonte: quando comeca uma linha nova, a velha SOBE. Antes
        # daqui a linha a sair era DESCARTADA (`m["exiting"]` filtrado) e o
        # `_roll` ficava em 0: a linha nova aparecia por baixo e a velha
        # desaparecia de um quadro para o outro.
        self._roll = 0.0
        # `frame` ja' marca a linha que saiu com `displaced_at`, e so' ela: a
        # mais antiga das desenhadas. Se ela nao estiver a sair, o numero e'
        # None e nao ha deslocamento nenhum.
        displaced_at = marks[0].get("displaced_at") if marks else None
        if displaced_at is not None:
            self._roll = youtube_reveal.roll_progress(
                now - float(displaced_at), youtube_reveal.EXIT_S)
        # SEM FADE: a linha que sai NAO desvanece -- ela sobe e e' cortada pelo
        # topo da caixa (medido no player: `opacity` fica em 1 e ela sai da
        # caixa). O alfa por linha continua 255; quem a tira do ecra e' o
        # deslocamento, nao um dissolve.
        self._row_alphas = [255] * len(marks)
        if not marks:
            return "", None
        return (youtube_reveal.rows_text([mark["text"] for mark in marks]),
                self._row_alphas)

    def _cue_texts(self):
        """As linhas do cue AGORA, ja' presas a `PLAYER_ROWS` linhas do ecra.

        `frame` ja' corta em `capacity` LINHAS do payload; uma linha que traga
        a sua propria quebra vale por duas no ecra, e e' `_clamp_rows` que fecha
        isso. O TECTO AQUI E' `PLAYER_ROWS + 1` e nao `PLAYER_ROWS`: a linha a
        mais e' a que esta' a ROLAR PARA FORA, e corta-la aqui apagaria a metade
        visivel do roll-up -- o dono veria a linha nova empurrar o vazio.
        """
        cue = self._cue
        now = time.monotonic()
        marks = cue.frame(now)
        self._roll = cue.roll(now)
        texts = _clamp_rows([mark.get("text") for mark in marks],
                            PLAYER_ROWS + 1)
        if texts and cue.first_paint_t is None:
            # A PRIMEIRA PINTURA deste cue, no relogio do player.
            cue.first_paint_t = cue.clock(now)
            cue.paint_texts = texts
        return texts

    def _blank_pixels(self):
        """Esconde os PIXELS sem esquecer o cue em curso (ver `_update`).

        `hide()` e' a limpeza; isto e' so' o pixel. Um cue do player passa
        legitimamente por instantes sem nada desenhado (antes do `start` da linha,
        ou entre as duas linhas) e apagar o estado ali matava a revelacao em curso.
        """
        self.visible = False
        self._blank = True
        if self.hwnd:
            _user32.ShowWindow(self.hwnd, SW_HIDE)
        return True

    def _display_text(self):
        """O texto inteiro, quando o MOTOR nao e' a fonte (a janela do player).

        A janela do YouTube chega ja' revelada -- `window_by_paint` cortou-a pelo
        relogio e pela pintura --, logo nao ha' aqui prefixo nenhum a calcular. O
        que nao pode acontecer e' esta funcao inventar um corte: ela devolve o que
        recebeu.
        """
        return self.text

    def _fail_open(self, exc):
        """Um motor partido nunca congela a legenda numa palavra.

        A revelacao e' um extra; a legenda e' o produto. Qualquer erro no tick
        deixa de usar o motor e desenha o texto INTEIRO que ja' chegou -- que e'
        exactamente o comportamento anterior a esta funcao existir.
        """
        try:
            with self.lock:
                self._live = None
                # O CUE TAMBEM: um motor partido nao pode ser o dono do ecra para
                # sempre. Sem isto, cada tick repetia a mesma excepcao e a legenda
                # nunca chegava a desenhar o texto que ja' tinha.
                self._cue = None
                self._row_alphas = None
                self._update()
            self.log(f"CAPTION_REVEAL_FAILED_OPEN error={exc!r}")
        except Exception as exc2:  # noqa: BLE001
            self.log(f"CAPTION_REVEAL_FAILED_OPEN error={exc2!r}")

    def _screen_proof(self):
        """(on_screen, rect, alpha) MEDIDO do Windows, nao do `self.visible`.

        Nasceu de um `CAPTION_OVERLAY_PUSH visible=true` que o dono NAO VIU. O
        campo `visible` e' o que NOS chamamos ao `ShowWindow`; a pergunta dele e'
        outra -- a janela esta' DENTRO de um monitor e o alfa nao e' zero? Uma
        prova por leitura de estado e' a unica que responde a ela sem abrir a app
        num ecra que nao e' o dele.
        """
        try:
            rect = wt.RECT()
            _user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            mon = _user32.MonitorFromPoint(wt.POINT(cx, cy), 2)  # NEAREST
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            ok = bool(_user32.GetMonitorInfoW(mon, ctypes.byref(info))) if mon else False
            work = info.rcWork if ok else None
            on_screen = bool(ok) and (work.left <= cx < work.right
                                      and work.top <= cy < work.bottom)
            try:
                alpha = ctypes.c_ubyte(0)
                flags = ctypes.c_ulong(0)
                key = ctypes.c_ulong(0)
                _user32.GetLayeredWindowAttributes(
                    self.hwnd, ctypes.byref(key), ctypes.byref(alpha),
                    ctypes.byref(flags))
                alpha_v = int(alpha.value)
            except Exception:                 # noqa: BLE001
                alpha_v = -1
            return (on_screen,
                    (rect.left, rect.top, rect.right - rect.left,
                     rect.bottom - rect.top), alpha_v)
        except Exception as exc:              # noqa: BLE001
            self.log('CAPTION_OVERLAY_GEOMETRY_FAILED error=%r' % (exc,))
            return (None, None, -1)

    def show(self, on=True):
        with self.lock:
            if not self.hwnd:
                return False
            if on:
                if not (self.text or self.previous):
                    return False
                self._update()
                # SEM PIXEL NAO SE MOSTRA A JANELA (2026-11-03): o
                # `UpdateLayeredWindow` nao foi chamado e o bitmap que la' esta'
                # e' o do cue anterior -- mostrar aqui era a legenda velha a
                # voltar. O tick armado pinta no instante da palavra seguinte.
                if self._blank:
                    return True
                _user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                                     | SWP_SHOWWINDOW)
                _user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
                # E O PAINEL NAO E' TAPADO POR ELA (dono, 2026-11-14). As DUAS
                # chamadas acima re-erguem esta janela dentro da banda topmost --
                # medido nesta maquina: `SetWindowPos(moved, insertAfter)` deixa o
                # `insertAfter` ACIMA, e `ShowWindow` num show re-mapeia ao topo da
                # banda. Como o `show` corre a cada linha, sem isto a legenda
                # aterra por cima do painel de forma consistente. A chamada e' UMA:
                # a propria legenda e' movida com `insertAfter=painel`, portanto
                # fica logo abaixo dele. Um provedor morto nao derruba a pintura.
                below = None
                try:
                    provider = self.z_below
                    below = int(provider() or 0) if provider is not None else 0
                except Exception as exc:          # noqa: BLE001
                    self.log('CAPTION_Z_PROVIDER_FAILED error=%r' % (exc,))
                    below = 0
                if below:
                    try:
                        _user32.SetWindowPos(self.hwnd, wt.HWND(below), 0, 0, 0, 0,
                                             SWP_NOMOVE | SWP_NOSIZE
                                             | SWP_NOACTIVATE)
                    except Exception as exc:      # noqa: BLE001
                        self.log('CAPTION_Z_BELOW_FAILED panel=%d error=%r'
                                 % (below, exc))
                self.visible = True
                if not getattr(self, '_geom_logged', False):
                    self._geom_logged = True
                    on_screen, rect, alpha = self._screen_proof()
                    self.log('CAPTION_OVERLAY_GEOMETRY shown=true '
                             'on_screen=%s rect=%r alpha=%d hwnd=%d'
                             % (str(on_screen).lower(), rect, alpha,
                                int(self.hwnd)))
            else:
                _user32.ShowWindow(self.hwnd, SW_HIDE)
                self.visible = False
            return True

    def hide(self):
        """FECHA E LIMPA a linha; SEM lock (`_update` chama-o com o lock na mao).

        FALTAVA: `_update` chamava `self.hide()` com o texto vazio, a classe nao
        tinha `hide` e o ULTIMO bitmap ficava no ecra -- a legenda do anterior.
        """
        self.text = ""
        self.previous = ""
        self._live = None
        self._cue = None
        self._row_alphas = None
        self._blank = True
        # O GESTO NAO SOBREVIVE AO ESCONDER-SE: uma legenda que sai do ecra a
        # meio de um arrasto nao pode voltar "agarrada" a um cursor que ja' nao
        # interfere. Nada e' gravado aqui -- nao houve largar.
        self._drag_reset()
        # O PRAZO SAI JUNTO COM A GERACAO (2026-11-23). So' retirar o tick
        # (`_tick_gen += 1`) deixava o prazo armado: o laco acordava no instante
        # antigo, via a geracao trocada e voltava ao topo SEM dormir, para
        # sempre -- medido no log do dono como `sotto-caption-tick` a 53-77 % de
        # um nucleo durante 10 h depois de um `Ctrl+Space` (hide()). E' a mesma
        # forma do `destroy()`, que ja' limpava os dois juntos.
        with _guard(self, '_sched_lock'):
            self._tick_gen += 1
            self._tick_deadline = 0.0
        self._tick_event.set()
        self.visible = False
        if self.hwnd:
            _user32.ShowWindow(self.hwnd, SW_HIDE)
        return True

    def destroy(self):
        # The timer chain is daemonic, but retiring it here means a destroyed
        # overlay cannot try to `_update` a window handle that is already gone.
        with _guard(self, '_sched_lock'):
            self._tick_gen += 1
            self._tick_timer = None
            self._tick_deadline = 0.0
            self._tick_stop = True
        self._tick_event.set()
        if self.hwnd:
            try:
                _user32.PostMessageW(self.hwnd, 0x0010, 0, 0)  # WM_CLOSE
            except Exception:
                pass
            self.hwnd = None
        if getattr(self, '_thread', None) is not None and self._thread.is_alive():
            self._thread.join(2.0)


def probe(seconds=3.0):
    """Show one test caption so the transparency can be measured."""
    import time
    ov = NativeCaptionOverlay(log=lambda m: print(m, flush=True))
    ov.set_work_area({"x": 0, "y": 0, "width": 1920, "height": 1032}, 1.0)
    # `instant=True`: the probe exists to measure the transparency of a real
    # sentence, not to watch a sprout, and 45 ms per word would show one word.
    ov.set_text("Teste de legenda transparente", "", instant=True)
    ov.show(True)
    time.sleep(seconds)
    ov.destroy()


if __name__ == "__main__":
    probe()
