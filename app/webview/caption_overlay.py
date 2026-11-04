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
from overlay_paint import (  # noqa: F401 -- superficie publica deste modulo
    _MEASURE_CACHE, _THEME_DEFAULT, _case, _colour, _font_family, _geom,
    _layout, _luminance, _make_font, _measure, _measure_budget,
    _normalise_theme, _premultiplied_bitmap, _rgba, _same_line,
)


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

    def __init__(self, rows, t, at=None, capacity=PLAYER_ROWS, rate=1.0):
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

    def clock(self, now=None):
        now = time.monotonic() if now is None else float(now)
        elapsed = min(max(0.0, now - self.at), PLAYER_HOLD_S)
        t = self.t + elapsed * self.rate
        if self.floor is not None:
            t = max(t, self.floor)
        return t

    def frame(self, now=None):
        """As linhas desenhadas agora -- prefixo revelado pelo relogio de cada
        palavra, a MESMA regra do caminho do YouTube (`youtube_reveal.frame`)."""
        import youtube_reveal
        # `rollup=0` e `exit_s=0`: a linha que sai nao entra -- o ecra tem no
        # maximo `PLAYER_ROWS` linhas (ordem do dono).
        return youtube_reveal.frame(self.rows, self.clock(now),
                                    self.capacity, 0, 0.0)

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


class NativeCaptionOverlay:
    #: O fade de entrada esta' DESLIGADO (ordem do dono 2026-11-03). O botao
    #: fica para o oraculo poder provar as duas metades: com `False`, nenhum
    #: frame intermedio e' publicado; com `True`, a animacao antiga volta -- e o
    #: braco negativo do oraculo le exatamente essa diferenca.
    FADE_ON = False

    """A per-pixel-alpha caption window. No WebView2, no plate."""

    CLASS_NAME = "SottoNativeCaption"

    def __init__(self, log=None):
        self.log = log or (lambda msg: None)
        self.lock = threading.RLock()
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
        # `_tick_gen` retira um tick ja' armado quando a linha que o armou ja' nao
        # existe -- a mesma tecnica do sprout, e pela mesma razao: um `Timer` pode
        # ja' estar dentro de `_update` quando o texto muda.
        self._tick_gen = 0
        self._tick_timer = None
        # O FADE DA LINHA NOVA (ordem do dono, 2026-10-30: *"por que a nossa
        # legenda nao tem a mesma animacao da do youtube?"*). `_fade_t0` e' o
        # instante em que a linha mudou, ou None quando nao ha' fade a correr.
        self._fade_t0 = None
        self._fade_gen = 0
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

    def _measure(self, text, previous):
        """Largura em px: o MESMO motor que desenha, nunca `GenericTypographic`
        -- medido 2026-10-17, 4,7% mais estreito, e quebrar com um e desenhar com
        o outro corta a ultima letra."""
        _lines, _prev, width, height, _scrolled = _layout(
            text, previous, self.scale, self.work.get('width', 1920),
            self.theme)
        return width, height

    def _fade_alpha(self):
        """O `SourceConstantAlpha` deste frame -- SEMPRE 255 (sem fade).

        O DONO TIROU O FADE, DUAS VEZES. 2026-10-30 ele pediu a animacao do
        YouTube; 2026-11-03, sobre uma captura: *"e ta com animacao fade in que
        eu JA MANDEI VOCE TIRAR"*. A legenda do YouTube NAO faz fade de
        entrada: a linha nova APARECE, e a que sai desliza para fora com o
        roll-up. Fade na janela inteira e' invencao nossa, e custa frames:
        cada alfa intermedio e' um `UpdateLayeredWindow` a mais.

        `FADE_ON` e' o botao: com ele DESLIGADO nada aqui produz alfa
        intermedio, e o caminho de desenho continua a existir para o oraculo
        poder provar as duas metades (com ele ligado, a animacao antiga volta).
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
        # O CUE DO PLAYER: a proxima PALAVRA dele, no relogio dele. Sem isto o
        # cue esperava pela leitura seguinte do UIA e a frase entrava de uma vez.
        if self._cue is not None:
            ahead = self._cue.next_clock(now)
            if ahead is not None:
                step = max(word_fade.FRAME_S, float(ahead) - now)
                delay = step if delay is None else min(delay, step)
        return delay

    def _arm_tick(self):
        """Agenda o proximo frame. Sem nada a mudar, nao arma nada -- e o timer
        nao fica a girar num ecra parado."""
        delay = self._next_delay()
        if delay is None:
            self._tick_timer = None
            return
        self._tick_gen += 1
        gen = self._tick_gen
        timer = threading.Timer(delay, lambda: self._tick(gen))
        timer.daemon = True
        self._tick_timer = timer
        timer.start()

    def _tick(self, gen):
        try:
            with self.lock:
                if gen != self._tick_gen:
                    return
                self._update()
        except Exception as exc:  # noqa: BLE001 -- see the fail-open rule
            self._fail_open(exc)

    def _update(self):
        if not self.hwnd:
            return False
        # NOT `self.text`: o MOTOR decide o que esta' desenhado neste instante (o
        # prefixo revelado de cada linha) e o alfa de cada uma. Esta chamada e' a
        # diferenca entre "tres palavras num quadro" e "tres palavras, uma a uma".
        text, alphas = self._display()
        previous = self.previous or ""
        if not text and not previous:
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
        # ONE layout, computed once, handed to the bitmap. Two copies of "how many
        # lines" is how a caption gets measured at one height and drawn at another.
        cur_lines, prev_line, width, height, _scrolled = _layout(
            text, previous, self.scale, self.work.get('width', 1920),
            self.theme)
        # OS ALFAS SAO DAS LINHAS QUE `_layout` VAI DESENHAR. Se a contagem nao
        # bater (a `_layout` pode juntar uma linha vazia), o alfa que sobra e'
        # ignorado e nenhuma linha recebe o alfa de outra -- a comparacao e' por
        # indice e os dois lados vem do MESMO texto.
        if alphas and len(alphas) != len(cur_lines):
            alphas = list(alphas[:len(cur_lines)]) + [255] * max(
                0, len(cur_lines) - len(alphas))
        bmp = _premultiplied_bitmap(cur_lines, prev_line, width, height,
                                    self.scale, self.theme, alphas)
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
            x = int(self.work.get('x', 0)
                    + (self.work.get('width', 1920) - width) / 2)
            y = int(self.work.get('y', 0) + self.work.get('height', 1080)
                    - height - 48 * self.scale)
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
            # O CARIMBO DA PINTURA DO CUE -- so' depois do `UpdateLayeredWindow`
            # dizer OK, porque antes disto nao ha' pixel nenhum no ecra.
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
        new = _PlayerCue(rows, t, at=at, rate=(payload or {}).get('rate'))
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
        if self._live is None:
            self._row_alphas = None
            return self._display_text(), None
        import youtube_reveal
        marks = self._live.frame(time.monotonic())
        if not self.FADE_ON:
            # SEM FADE: a linha que sai NAO desvanece -- ela desaparece quando o
            # motor a tira da janela (o roll-up de duas linhas do YouTube nao tem
            # dissolve, e o dono ja' mandou tirar a animacao duas vezes).
            marks = [m for m in marks if not m.get("exiting")]
            self._row_alphas = [255] * len(marks)
        else:
            self._row_alphas = [mark["alpha"] for mark in marks]
        if not marks:
            return "", None
        return (youtube_reveal.rows_text([mark["text"] for mark in marks]),
                self._row_alphas)

    def _cue_texts(self):
        """As linhas do cue AGORA, ja' presas a `PLAYER_ROWS` linhas fisicas.

        `frame` ja' corta em `capacity` LINHAS do payload; uma linha que traga a
        sua propria quebra vale por duas no ecra, e e' `_clamp_rows` que fecha
        isso.
        """
        cue = self._cue
        now = time.monotonic()
        marks = cue.frame(now)
        texts = _clamp_rows([mark.get("text") for mark in marks])
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
                self.visible = True
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
        self._tick_gen += 1
        self.visible = False
        if self.hwnd:
            _user32.ShowWindow(self.hwnd, SW_HIDE)
        return True

    def destroy(self):
        # The timer chain is daemonic, but retiring it here means a destroyed
        # overlay cannot try to `_update` a window handle that is already gone.
        with self.lock:
            self._tick_gen += 1
            self._tick_timer = None
        if self.hwnd:
            try:
                _user32.PostMessageW(self.hwnd, 0x0010, 0, 0)  # WM_CLOSE
            except Exception:
                pass
            self.hwnd = None
        if self._thread.is_alive():
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
