#!/usr/bin/env python
"""panel-paint-first-census -- A PRIMEIRA FRAME DO SHOW, MEDIDA EM PIXEIS.

A ORDEM DO DONO, verbatim (2026-11-01): *"nada, literalmente nada, deve ter bug de
render. o painel dar show, nao deve carregar o background e mostrar, e depois
carregar a ui ou algo assim. isso e inaceitavel."*

O QUE ESTE INSTRUMENTO MEDE, e porquê por pixels e nao por log. O log diz que a
app chamou `ShowWindow`; nao diz o que chegou ao vidro. A unica leitura que
responde à ordem dele e' a da PRIMEIRA FRAME visivel: se ela e' uma cor chapada
(o fundo do FORM, sem UI) ou se ja' tem conteudo. Por isso:

  1  acha a janela do painel pela LOG DA PROPRIA APP (`PANEL_VISIBILITY_*` carrega
     `hwnd=`; `PANEL_SHOWN`/`PANEL_HIDDEN` trazem `hwnd=` desde 2026-11-01), e
     nunca por titulo -- a instancia do dono tambem se chama `Sotto` e nao se toca;
  2  captura a area de cliente com `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)`
     a >= 60 Hz, um DC e um bitmap REUTILIZADOS (mede-se frames, nao alocacoes);
  3  classifica cada frame em `blank` (desvio-padrao ~0 sobre a area toda: uma cor
     chapada, o fundo do FORM) ou `content` (acima de um limiar MEDIDO -- ver as
     armas de controlo abaixo, que imprimem os numeros dos dois lados);
  4  para cada show, conta quantas frames `blank` precederam a primeira frame
     `content` visivel e os milissegundos ate' ela.

PORQUE SO' AS FRAMES VISIVEIS CONTAM. Uma janela escondida tambem pode ser
capturada (`PrintWindow` nao depende da posicao), e antes do mapa ela e' -- por
construcao -- uma cor chapada. Contar essas seria inventar o defeito.

A FRAME 0 E' A PRIMEIRA FRAME QUE ELE PODE VER, e desde 2026-11-01 sao DUAS
condicoes, nao uma. O shell mapeia a janela FORA do ecra virtual para pagar a
PRIMEIRA pintura do processo (`PAINT_WARM` no log, uma vez por arranque) e so'
depois mostra o painel, ja' quente, no rect do show. Uma janela visivel mas fora
do ecra virtual ninguem a ve: contar essas frames como show seria medir um rect
que nao esta' em ecra nenhum. A frame 0 de um show e' a primeira frame com
`IsWindowVisible=true` E o rect da janela a intersectar o ecra virtual; uma
stretch visivel fora do ecra imediatamente antes de um show fica no relatorio como
`staged` -- e no build curado ela e' 0, porque o aquecimento e' no ARRANQUE e nao
por show (medido: mover a janela mapeada custa os mesmos ~270 ms). As armas de
CONTROLO nao usam esta regra: a janela delas esta' fora do ecra por construcao e o
que elas provam e' o CLASSIFICADOR (`PrintWindow` nao depende da posicao), nao a
posicao.

A ARMA DE CONTROLO (obrigatoria, e' o que torna o numero uma medida). O mesmo
classificador corre sobre uma janela que ESTE INSTRUMENTO cria, FORA do ecra do
dono (`x=-10000`, `SW_SHOWNOACTIVATE`):
    control-blank-first    mapeada com um fundo solido e so' depois populada
                           -> TEM de reportar blank_frames > 0 (senao o
                           classificador e' cego e os zeros da app nao valem nada);
    control-content-first  mapeada ja' populada
                           -> TEM de reportar blank_frames = 0 (senao o
                           classificador chama "blank" a tudo, e o mesmo zero
                           seria um artefacto do instrumento).

E "BLANK" NAO E' "NAO HA' CAPTURA" (2026-11-01, e este era um defeito MEU). A
primeira versao desta arma reportava `blank_frames=1`: a frame `i0`, mapeada e ja'
pintada, vinha `std=0.0 mean=0.0` -- o buffer INTEIRO a zero, incluindo os bytes
que o `PrintWindow` deveria ter escrito. A janela do controlo pinta o fundo em
`0x202020` (mean=32) e a app em `#0B0F14` (mean~15): nenhuma cor de nenhuma das
duas e' zero. Um buffer a zero nao e' uma frame chapada, e' a MEMORIA ANTES DE
QUALQUER PINTURA -- o `PrintWindow` devolveu TRUE e o DWM ainda nao tinha superficie
para a janela recem-mapeada. Isso e' uma CAPTURA PERDIDA (`no-surface`), a mesma
classe que `printwindow-false`/`no-dc`, e e' contada como tal em vez de virar 1
blank. Nao ha' limiar novo aqui: `mean==0.0 e std==0.0` e' a assinatura de um
buffer intocado, nao um numero ajustado para o caso passar.

O DRIVER E' O DA CASA. Arranca uma SEGUNDA instancia com `--mutex-name` privado,
tecla livre, `--no-worker` e o token de um processo `high` do dono
(`_main/launch-as-token.py`, fonte `explorer.exe`), exactamente como
`_main/pov-selftest.py`: a instancia do dono nao e' tocada, nao se mata nada, e a
unica tecla usada e' a do selftest da PROPRIA app (`--selftest` posta o WM_HOTKEY
na fila dela; nao ha `keybd_event`/`SendInput` aqui -- input sintetico mede o
Windows, nao a app).

USO
    python _main\\panel-paint-first-census.py --run
    python _main\\panel-paint-first-census.py --run --control-only
    python _main\\panel-paint-first-census.py --run --app-only --variants uncured
    python _main\\panel-paint-first-census.py --run --json

AS DUAS ARMAS DA APP, e porque sao duas. Uma cura so' e' uma cura se o MESMO
instrumento, na MESMA corrida, acusar VERMELHO no codigo de antes e VERDE no de
depois. Por isso o braco da app corre duas vezes:

    cured     o shell do worktree (`app/webview/sotto_webview.py`, os bytes agora)
              -> todo show TEM de dar `blank_frames=0`
    uncured   os bytes de `41e7bc6^` (o commit de antes da cura; ver UNCURED_REV)
              -> pelo menos um show TEM de dar `blank_frames>0`, senao este
              instrumento nunca viu o defeito que diz medir

O DRIVER E' INJECTADO, e o motivo e' medido, nao preferido. O caminho real de
abertura comeca no Alt+C, e o `--selftest` da app empurra o `WM_HOTKEY` na fila
dela; no snapshot que este instrumento mede a resolucao do toque NAO produz show
nenhum (`HOTKEY_PRESSED count=2` e nenhum `PANEL_SHOWN`:
`I:/cc-tmp/panel-paint-first-app.log` linhas 64-66) -- esse ficheiro e' de outro
lane e nao e' desta cura. Entao o driver chama a FUNCAO CURADA directamente
(`show_strip`, `show_side`, as mesmas onde o Alt+C acaba) numa COPIA do shell com
uma unica substituicao de texto, e o nome do ficheiro temporario diz o que ele e'
(`_census-<tag>-sotto_webview.py`, apagado no fim). Nada do produto e' editado.

rc=0  o veredicto passou (cured sem frames blank, uncured com blank>0, e as duas
      armas de controlo a comportarem-se como o desenho exige)
rc=1  o veredicto falhou, e a linha VERDICT diz qual clausula
rc=2  nao foi possivel medir (a app nao arrancou / o painel nunca apareceu) --
      isso nao e' um verde nem um vermelho, e' um instrumento sem sujeito
"""
# BATTERY-HEAVY: app-window -- larga uma instancia PRIVADA da app (off-screen em
# x=-10000, `SW_SHOWNOACTIVATE`, token `high` do dono) para ler os pixeis do primeiro frame
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
LAUNCH_AS_TOKEN = os.path.join(ROOT, '_main', 'launch-as-token.py')
TMP = os.environ.get('SOTTO_TMP') or r'I:\cc-tmp'

#: `--mutex-name` PRIVADO: a instancia do dono fica com o `Local\SottoShell` dele.
MUTEX = 'SottoPaintFirstCensus'
#: `Alt+Shift+F12` e' a tecla que a casa mediu LIVRE (`_main/_audit-hotkey-probe.py`,
#: 2026-10-07: Alt+F9 estava tomado). Uma lane vizinha pode estar a usa-la no mesmo
#: minuto, e o registo e' global ao desktop -- por isso ha' um fallback e o log da
#: app diz qual foi aceite (`HOTKEY_REGISTERED`/`HOTKEY_REGISTER_FAILED`).
FREE_HOTKEYS = ('Alt+Shift+F12', 'Ctrl+Alt+Shift+F12')

CREATE_NO_WINDOW = 0x08000000
PW_RENDERFULLCONTENT = 0x00000002
SW_SHOWNOACTIVATE = 4
SW_HIDE = 0

#: O LIMIAR, e porque estes numeros. Medidos nas armas de controlo (impressos em
#: cada corrida): uma janela pintada de UMA cor da' std=0.0/spread=0; a mesma
#: janela populada com barras e texto da' std >> 20/spread=255. O limiar fica
#: MUITO abaixo do segundo e MUITO acima do primeiro, e a linha
#: `CONTROL separation` prova a folga em cada corrida em vez de a afirmar.
BLANK_STD_MAX = 2.5
BLANK_SPREAD_MAX = 8
#: ~4096 amostras da area de cliente inteira (cantos incluidos, que e' onde o
#: fundo nu aparece). `sum()`/`set()` sobre 4096 bytes custam ~0.5 ms, o que
#: deixa a folga toda para o `PrintWindow`.
SAMPLE_POINTS = 4096
CAPTURE_PERIOD_S = 1.0 / 60.0

#: O ECRA VIRTUAL (`GetSystemMetrics`): a uniao de todos os monitores. E' o que
#: separa "a janela foi mapeada" de "a janela esta' onde o dono a pode ver".
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long),
                ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]


# -- every signature declared: a 64-bit handle passed as a C int FAILS SILENTLY,
# -- which is the defect the strip lane already paid for (see `set_topmost`).
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                            ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = ctypes.c_void_p
user32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.ReleaseDC.restype = ctypes.c_int
user32.PrintWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
                            wintypes.UINT, ctypes.c_void_p,
                            ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.restype = wintypes.BOOL


_lines = []
_fh = None


def say(msg=''):
    _lines.append(msg)
    try:
        print(msg, flush=True)
    except Exception:  # noqa: BLE001 -- no console under the owner's token
        pass
    if _fh is not None:
        try:
            _fh.write(msg + '\n')
            _fh.flush()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# the pixel channel: one DC, one bitmap, reused for every frame
# ---------------------------------------------------------------------------

def classify(px, w, h):
    """`blank` or `content`, from the BGRA bytes of the whole client area.

    The sample is a fixed stride over the WHOLE buffer, so the corners (where a
    bare FORM background shows first) weigh as much as the centre. Reported raw
    (std/spread/distinct) so a threshold change is a number, never a mood.
    """
    if not w or not h or len(px) < 16:
        return None
    step = max(4, ((len(px) // SAMPLE_POINTS) // 4) * 4)
    sub = px[1::step]
    n = len(sub)
    if not n:
        return None
    total = sum(sub)
    mean = total / n
    var = sum(v * v for v in sub) / n - mean * mean
    std = var ** 0.5 if var > 0 else 0.0
    spread = max(sub) - min(sub)
    return {'std': round(std, 3), 'spread': int(spread),
            'distinct': len(set(sub)), 'mean': round(mean, 1),
            'samples': n,
            'blank': bool(std <= BLANK_STD_MAX and spread <= BLANK_SPREAD_MAX)}


class Grabber:
    """`PrintWindow(PW_RENDERFULLCONTENT)` of ONE window, allocation-free per frame."""

    def __init__(self, hwnd):
        self.hwnd = int(hwnd)
        self.w = self.h = 0
        self.hdc = self.mem = self.bmp = self.old = None
        self.buf = None
        self.info = None
        self.durations = []
        self.failures = 0
        self.reasons = {}

    def _release(self):
        if self.mem and self.old:
            gdi32.SelectObject(self.mem, self.old)
        if self.bmp:
            gdi32.DeleteObject(self.bmp)
        if self.mem:
            gdi32.DeleteDC(self.mem)
        if self.hdc:
            user32.ReleaseDC(wintypes.HWND(self.hwnd), self.hdc)
        self.hdc = self.mem = self.bmp = self.old = None
        self.buf = self.info = None

    def _ensure(self):
        r = RECT()
        if not user32.GetClientRect(wintypes.HWND(self.hwnd), ctypes.byref(r)):
            return False
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0:
            return False
        if (w, h) == (self.w, self.h) and self.mem:
            return True
        self._release()
        self.w, self.h = w, h
        self.hdc = user32.GetDC(wintypes.HWND(self.hwnd))
        if not self.hdc:
            return False
        self.mem = gdi32.CreateCompatibleDC(self.hdc)
        self.bmp = gdi32.CreateCompatibleBitmap(self.hdc, w, h)
        if not self.mem or not self.bmp:
            self._release()
            return False
        self.old = gdi32.SelectObject(self.mem, self.bmp)
        self.buf = ctypes.create_string_buffer(w * h * 4)
        self.info = BITMAPINFOHEADER()
        self.info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self.info.biWidth = w
        self.info.biHeight = -h              # top-down, like the house probe
        self.info.biPlanes = 1
        self.info.biBitCount = 32
        self.info.biCompression = 0          # BI_RGB
        return True

    def grab(self):
        """One frame -> the classifier's verdict, plus how long the grab took."""
        t0 = time.perf_counter()
        if not self._ensure():
            self._count('no-dc')
            return {'ok': False, 'why': 'no-dc'}
        ctypes.set_last_error(0)
        ok = user32.PrintWindow(wintypes.HWND(self.hwnd), self.mem,
                                PW_RENDERFULLCONTENT)
        if not ok:
            # `err=5` here is UIPI, not a window problem: the caller runs at a
            # LOWER integrity than the target and Windows DROPS `WM_PRINT`.
            why = 'printwindow-false-err=%d' % (ctypes.get_last_error(),)
            self._count(why)
            return {'ok': False, 'why': why}
        got = gdi32.GetDIBits(self.mem, self.bmp, 0, self.h, self.buf,
                              ctypes.byref(self.info), 0)
        if got != self.h:
            self._count('getdibits-%d' % (got,))
            return {'ok': False, 'why': 'getdibits-%d' % (got,)}
        ms = (time.perf_counter() - t0) * 1000.0
        self.durations.append(ms)
        out = classify(self.buf.raw, self.w, self.h) or {'ok': False, 'why': 'empty'}
        # ── "BLANK" NAO E' "NAO HA' CAPTURA" (ver a docstring do modulo) ──────
        # Um buffer com mean==0.0 E std==0.0 esta' INTEIRO a zero: nenhum byte
        # foi escrito pelo `PrintWindow`, que devolveu TRUE na mesma. Isto e' o
        # DWM sem superficie para uma janela recem-mapeada (medido na arma
        # `control-content-first`: `i0[std=0.0 spread=0.0 mean=0.0]`, com a
        # janela a pintar `0x202020`). Contar isto como blank acusaria o
        # classificador de chamar blank a uma frame de CONTEUDO; contá-lo como
        # captura perdida e' o que a frame e' de facto. As cores de ambas as
        # janelas sao nao-zero, portanto o teste nao esconde pintura nenhuma.
        if out['std'] == 0.0 and out['mean'] == 0.0:
            self._count('no-surface')
            return {'ok': False, 'why': 'no-surface', 'grab_ms': round(ms, 2),
                    'size': '%dx%d' % (self.w, self.h)}
        out['ok'] = True
        out['grab_ms'] = round(ms, 2)
        out['size'] = '%dx%d' % (self.w, self.h)
        return out

    def _count(self, why):
        self.failures += 1
        self.reasons[why] = self.reasons.get(why, 0) + 1

    def close(self):
        self._release()


def window_pid(hwnd) -> int:
    if not hwnd:
        return 0
    owner = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(owner))
    return int(owner.value)


def window_text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, 512)
    return buf.value


def window_onscreen(hwnd) -> bool:
    """O rect da janela toca no ecra virtual? -- a SEGUNDA metade da frame 0.

    `IsWindowVisible` diz que o Windows a considera visivel, e uma janela mapeada
    com o rect fora do ecra e' visivel. O que o dono ve e' a INTERSECCAO com o
    ecra virtual (a uniao dos monitores), e e' isso que este predicado responde --
    a mesma pergunta para "sem show" e "aquecimento fora do ecra".
    """
    rect = RECT()
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return False
    x0 = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    y0 = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    x1 = x0 + user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    y1 = y0 + user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    return (min(rect.right, x1) - max(rect.left, x0) > 0
            and min(rect.bottom, y1) - max(rect.top, y0) > 0)


# ---------------------------------------------------------------------------
# the frame loop -- ONE loop, used by the app arm and by both control arms
# ---------------------------------------------------------------------------

def capture_for(hwnd, seconds, period=CAPTURE_PERIOD_S, on_frame=None, stop=None):
    """Frame loop at >= 60 Hz: visibility, foreground and pixels on the same clock.

    Returns (frames, grabber). `on_frame(n, frame)` runs between frames so a
    caller can change the subject (the control arm populates its window mid-run)
    and `stop` (an Event) ends the loop early -- the app arm uses it for "the
    instance under measurement has exited", so the census does not spend the
    whole budget capturing a dead window.
    """
    grabber = Grabber(hwnd)
    frames = []
    deadline = time.monotonic() + float(seconds)
    index = 0
    while time.monotonic() < deadline and not (stop is not None and stop.is_set()):
        t0 = time.perf_counter()
        visible = bool(user32.IsWindowVisible(wintypes.HWND(hwnd)))
        fg = int(user32.GetForegroundWindow() or 0)
        frame = {'t': t0, 'visible': visible, 'onscreen': window_onscreen(hwnd),
                 'fg': fg, 'fg_pid': window_pid(fg)}
        if visible:
            frame.update(grabber.grab())
        else:
            frame.update({'ok': False, 'why': 'hidden'})
        frame['i'] = index
        frames.append(frame)
        index += 1
        if on_frame is not None:
            on_frame(index, frame)
        left = t0 + period - time.perf_counter()
        if left > 0:
            time.sleep(left)
    return frames, grabber


def runs_of_visible(frames, onscreen=False):
    """Contiguous visible stretches: one stretch IS one show.

    `onscreen=True` is the APP arm, and it is the definition of a show since
    2026-11-01: the shell maps the panel OUT of the virtual screen and moves it
    on only after the page's paint ack, so `IsWindowVisible` alone would start the
    show at a rect nobody can see (the `staged` frames, reported apart). The
    CONTROL arms keep the plain version: their window lives at `x=-10000` on
    purpose, and what they prove is the classifier, not the staging.
    """
    runs, cur = [], None
    for f in frames:
        shown = f['visible'] and (f.get('onscreen') or not onscreen)
        if shown:
            if cur is None:
                cur = []
                runs.append(cur)
            cur.append(f)
        else:
            cur = None
    return runs


#: A visible stretch shorter than this that NEVER reached content is pywebview's
#: own `hidden=True` dance, not a show. MEASURED 2026-11-01 (first full run of
#: this instrument): one frame, at the panel's own 380x900 rect, `std=0.0`, at
#: t≈+0.9 s and BEFORE any `PANEL_SHOWN` -- the same microseconds-of-Opacity=0
#: map the house documented on 2026-10-12. Counting it as a show would report a
#: blank first frame that no Alt+C produced.
MIN_SHOW_FRAMES = 3


def split_startup_dance(runs):
    """(shows, ignored): drop stretches that are the startup dance."""
    keep, ignored = [], []
    for run in runs:
        reached = any(f.get('ok') and not f.get('blank') for f in run)
        if len(run) < MIN_SHOW_FRAMES and not reached:
            ignored.append(run)
        else:
            keep.append(run)
    return keep, ignored


def _staged_before(frames, first):
    """(frames, ms) spent VISIBLE but OFF the virtual screen, right before `first`.

    A window that is mapped out of sight and then brought on screen spends that
    stretch where nobody can see it, so it is reported apart instead of being
    counted as blanks. It is ZERO on the cured build, and that is by design: the
    first present is paid ONCE at startup (`PAINT_WARM` in the log, window off
    the virtual screen), and every show then maps at its own rect already warm --
    measured, because MOVING a mapped window back on screen pays the same ~270 ms
    the cure exists to remove.
    """
    idx = next((k for k, f in enumerate(frames) if f is first), 0)
    count, t0 = 0, None
    for f in reversed(frames[:idx]):
        if not (f['visible'] and not f.get('onscreen')):
            break
        count += 1
        t0 = f['t']
    return count, (0.0 if t0 is None else round((first['t'] - t0) * 1000.0, 1))


def summarise_run(run, frames, shell_pid):
    """blank frame count and ms-to-first-content for ONE show, plus the focus.

    `blank_frames` counts VISIBLE blank frames from the first frame the owner can
    SEE (visible AND on screen -- see `runs_of_visible`) onwards, stopping at the
    first content frame. A show that never reaches content reports
    `first_content_ms=None` and `blank_frames=<all frames>`, because "it never
    painted" is the defect in its worst form and rounding it into a zero would be
    the lie this instrument exists to prevent. Frames that are visible but off
    the screen are the staging stretch and are reported as `staged_*`, never as
    blanks: the owner could not see them.
    """
    first = run[0]
    staged_frames, staged_ms = _staged_before(frames, first)
    blanks = 0
    first_content = None
    capture_failures = 0
    for f in run:
        if not f.get('ok'):
            capture_failures += 1
            continue
        if f.get('blank'):
            if first_content is None:
                blanks += 1
        else:
            first_content = f
            break
    later_blanks = 0
    if first_content is not None:
        seen = False
        for f in run:
            if f is first_content:
                seen = True
                continue
            if seen and f.get('ok') and f.get('blank'):
                later_blanks += 1
    after = [f for f in run if f['t'] <= first['t'] + 0.25]
    stolen = bool(shell_pid
                  and any(f['fg_pid'] == shell_pid for f in after)
                  and (run[0] and frames and _fg_before(frames, first) != shell_pid))
    return {
        'started_ms': round((first['t'] - frames[0]['t']) * 1000.0, 1),
        'visible_frames': len(run),
        'staged_frames': staged_frames,
        'staged_ms': staged_ms,
        'capture_failures': capture_failures,
        'blank_frames': blanks,
        'first_content_ms': (None if first_content is None
                             else round((first_content['t'] - first['t']) * 1000.0, 1)),
        'later_blank_frames': later_blanks,
        'first_std': first.get('std'),
        'first_spread': first.get('spread'),
        'first_mean': first.get('mean'),
        'first_size': first.get('size'),
        'focus_before_pid': _fg_before(frames, first),
        'focus_after_pid': run[min(1, len(run) - 1)]['fg_pid'],
        'focus_stolen_by_shell': stolen,
        't0': first['t'],
    }


def _fg_before(frames, first):
    for f in reversed(frames):
        if f['t'] < first['t']:
            return f['fg_pid']
    return 0


# ---------------------------------------------------------------------------
# the app arm -- a SECOND instance, private mutex, free key, the owner's token
# ---------------------------------------------------------------------------

def source_pid():
    """The owner's own `high` process whose token we borrow: `explorer.exe`."""
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]

    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_void_p),
                    ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD),
                    ('szExeFile', ctypes.c_wchar * 260)]

    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    entry = Entry()
    entry.dwSize = ctypes.sizeof(Entry)
    ok = k32.Process32FirstW(snap, ctypes.byref(entry))
    found = []
    while ok:
        if str(entry.szExeFile).lower() == 'explorer.exe':
            found.append(int(entry.th32ProcessID))
        ok = k32.Process32NextW(snap, ctypes.byref(entry))
    k32.CloseHandle(snap)
    if not found:
        raise SystemExit('no explorer.exe on this box: nothing to borrow a token from')
    return found[-1]


#: The census's inner arm, launched with the owner's token, writes its report
#: here; the outer arm prints that file and returns its rc.
INNER_OUT = os.path.join(TMP, 'panel-paint-first-inner.out')

#: Where a variant copy of the shell has to live: NEXT TO the original, because
#: the shell imports its siblings by module name (`panel_state`, `youtube_reveal`,
#: `hotkey_*`) and `sys.path[0]` is the script's own directory. The house probe
#: does the same (`_main/panel-paint-probe.py`, `VARIANT_DIR`).
VARIANT_DIR = os.path.dirname(SHELL)

#: The driver the census injects, verbatim. Module level, and inserted BEFORE
#: the `__main__` guard, so it is defined by the time `main()` runs.
DRIVER_SRC = '''
def paint_census_drive(shell):
    """O DRIVER DO CENSO: chama as FUNCOES CURADAS, tres vezes, e sai.

    Ver `_main/panel-paint-first-census.py` para o motivo medido de ser um driver
    e nao o Alt+C: a resolucao do toque (ficheiro de OUTRO lane) nao produz show
    neste snapshot (`HOTKEY_PRESSED count=2` sem `PANEL_SHOWN`). O que se mede
    aqui e' a funcao onde o toque acaba -- `show_strip` / `show_side` -- na copia
    do shell que este instrumento construiu, nunca no produto.
    """
    try:
        time.sleep(1.0)
        shell.hide_panel('census-baseline')
        steps = (('strip', 'census-1'), ('panel', 'census-2'),
                 ('strip', 'census-3'))
        for surface, reason in steps:
            time.sleep(0.7)
            log('CENSUS_DRIVER show=%s surface=%s' % (reason, surface))
            # A EXPERIENCIA, e o que ela separa: o painel tem DUAS metades -- a
            # janela (user32) e o documento (CSS). Se a metade do documento for
            # aplicada ANTES do mapa, a primeira frame visivel ja' tem a UI; se
            # for aplicada no mapa (o caminho do produto hoje), a frame que o
            # dono ve e' o fundo do FORM. Aqui o documento e' aplicado antes, com
            # a janela ainda escondida, e depois `show_strip`/`show_side` mapeiam
            # -- e, como a superficie ja' esta' aplicada, NAO a reaplicam.
            try:
                shell.set_panel_surface(surface, reason + '-warm')
                log('CENSUS_DRIVER warmed surface=%s' % (surface,))
                time.sleep(0.6)
            except Exception as exc:  # noqa: BLE001
                log('CENSUS_DRIVER warm FAILED error=%r' % (exc,))
            if surface == 'strip':
                shell.show_strip(reason)
            else:
                shell.show_side(reason)
            time.sleep(1.3)
            log('CENSUS_DRIVER hide=%s' % reason)
            shell.hide_panel('census-hide-' + reason)
        log('CENSUS_DRIVER done shows=%d' % len(steps))
    except Exception as exc:  # noqa: BLE001 -- um driver que morre tem de dizer
        log('CENSUS_DRIVER FAILED error=%r' % (exc,))
    finally:
        shell.request_exit(0, reason='census-driver')

'''

_SELFTEST_ANCHOR = 'self.run_selftest()'
_MAIN_ANCHOR = "if __name__ == '__main__':"
_DRIVER_CALL = 'paint_census_drive(self)'


#: O COMMIT DE ANTES DA CURA, pinado (2026-11-01). A arma `uncured` lia `HEAD`,
#: e isso deixou de servir no minuto em que a cura foi COMMITADA: os dois bracos
#: passaram a ser os mesmos bytes e o controle negativo da' verde por nao haver
#: nada de errado para medir -- o zero de um instrumento que ja' nao distingue
#: nada. `41e7bc6` e' o commit que introduziu `arm_paint_ack` (medido com
#: `git log -S arm_paint_ack`), logo a copia ANTERIOR leva a partir de `41e7bc6^`.
UNCURED_REV = '41e7bc6^'


def variant_bytes(tag, uncured_rev=None):
    """Os bytes do shell para `tag`: `cured` = o worktree, `uncured` = `UNCURED_REV`."""
    if tag == 'cured':
        with open(SHELL, 'r', encoding='utf-8', newline='') as fh:
            return fh.read()
    if tag == 'uncured':
        rev = uncured_rev or UNCURED_REV
        proc = subprocess.run(['git', '-C', ROOT, 'show',
                               '%s:app/webview/sotto_webview.py' % rev],
                              capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        if proc.returncode != 0 or not proc.stdout:
            raise SystemExit('variant uncured: `git show %s:...` failed: %s'
                             % (rev, proc.stderr.strip()[:200] or 'no output'))
        if 'arm_paint_ack' in proc.stdout:
            raise SystemExit(
                'variant uncured: %s JA TEM a cura (arm_paint_ack) -- escolher '
                'outro rev, senao o controle negativo mede o codigo curado' % rev)
        return proc.stdout
    raise SystemExit('variant: unknown tag %r (cured|uncured)' % (tag,))


def build_variant(tag):
    """Write `<VARIANT_DIR>/_census-<tag>-sotto_webview.py` and return its path.

    TWO text substitutions, each with its own assertion, because a driver that
    silently failed to install would make this instrument measure the STARTUP
    path and publish it as "the show": the exact class of lie the house keeps
    paying for. Every anchor is checked for uniqueness in the SOURCE BYTES, and
    the BUILT FILE is grepped for the driver before it is run.
    """
    text = variant_bytes(tag)
    if text.count(_SELFTEST_ANCHOR) != 1:
        raise SystemExit('variant %s: %r is not unique in the shell (%d) -- '
                         'refusing' % (tag, _SELFTEST_ANCHOR,
                                       text.count(_SELFTEST_ANCHOR)))
    if text.count(_MAIN_ANCHOR) != 1:
        raise SystemExit('variant %s: %r is not unique in the shell (%d) -- '
                         'refusing' % (tag, _MAIN_ANCHOR, text.count(_MAIN_ANCHOR)))
    if 'paint_census_drive' in text:
        raise SystemExit('variant %s: the shell already carries the driver -- '
                         'refusing' % (tag,))
    out = text.replace(_SELFTEST_ANCHOR, _DRIVER_CALL, 1)
    out = out.replace(_MAIN_ANCHOR, DRIVER_SRC + _MAIN_ANCHOR, 1)
    path = os.path.join(VARIANT_DIR, '_census-%s-sotto_webview.py' % (tag,))
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(out)
    built = read_text(path)
    if _DRIVER_CALL not in built or 'def paint_census_drive' not in built:
        os.remove(path)
        raise SystemExit('variant %s: the driver did NOT land in the built file '
                         '-- refusing' % (tag,))
    return path


def drop_variant(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
            say('  cleanup removed=%s' % os.path.basename(path))
    except OSError as exc:
        say('  cleanup FAILED path=%s error=%r' % (path, exc))


#: The app instance this instrument launches (kept as ONE module global so
#: `app_finished` can read its exit code instead of parsing a shell file).
_APP = {}


def write_app_launch(exit_after, hotkey, shell, log_path, mutex):
    """The private instance's argv. `--selftest` is the hook the driver replaced
    in the variant; `--mutex-name` keeps the owner's lock free, and it carries the
    ARM's tag so two arms can never collide if one lingers."""
    return [sys.executable, shell, '--selftest', '--no-worker',
            '--mutex-name', mutex, '--hotkey', hotkey,
            '--exit-after', '%g' % float(exit_after), '--log', log_path]


def read_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def spawn_app(exit_after, hotkey, shell, log_path, out_path, mutex):
    """Launch the private instance DIRECTLY, and say why that is enough.

    ── UIPI, MEASURED (2026-11-01, this box, this instrument) ────────────────
    `PrintWindow` sends `WM_PRINT` to the target, and User Interface Privilege
    Isolation DROPS that message when the caller runs at a LOWER integrity than
    the target: a MEDIUM census asking a HIGH app for its pixels got
    `PrintWindow -> FALSE, GetLastError=5 (ACCESS_DENIED)` on every one of 101
    frames -- the same err=5 the house already measured for `TRAY_ICON_ADD` from
    a medium child. So a census that runs in the lane's own (medium) integrity
    can never see the owner's app at all, and any "blank_frames=0" it printed
    would be a statement about a DC it never filled.

    The cure is the house's own: `_main/launch-as-token.py` gives THIS PROCESS
    the owner's token, and a child created from a high process inherits high.
    The app therefore needs no token dance of its own -- see `elevate`.
    """
    os.makedirs(TMP, exist_ok=True)
    for p in (log_path, out_path):
        try:
            os.remove(p)
        except OSError:
            pass
    out = open(out_path, 'w', encoding='utf-8', errors='replace')
    proc = subprocess.Popen(write_app_launch(exit_after, hotkey, shell, log_path,
                                             mutex),
                            stdout=out, stderr=subprocess.STDOUT,
                            cwd=ROOT, creationflags=CREATE_NO_WINDOW)
    _APP['proc'] = proc
    _APP['stdout'] = out
    return 'pid=%d (child of this high process: the app inherits the owner token)' % proc.pid


def elevate(args):
    """Re-run THIS script with the owner's own token, then print its report.

    Returns the rc the inner arm reached, or None when the elevation itself
    failed (which is a reason to say so, never to fake a measurement).
    """
    passthrough = ['--variants', args.variants,
                   '--seconds', '%g' % args.seconds,
                   '--exit-after', '%g' % args.exit_after,
                   '--find-timeout', '%g' % args.find_timeout]
    if args.app_only:
        passthrough.append('--app-only')
    if args.control_only:
        passthrough.append('--control-only')
    if getattr(args, 'save_json', ''):
        # O FILHO e' quem mede, portanto e' ele que grava. Ja' vai ABSOLUTO: o
        # `launch-as-token` nao garante o cwd do lancador (medido 2026-11-01).
        passthrough += ['--save-json', args.save_json, '--json']
    try:
        os.remove(INNER_OUT)
    except OSError:
        pass
    cmd = [sys.executable, LAUNCH_AS_TOKEN, str(source_pid()), sys.executable,
           os.path.abspath(__file__), '--run', '--inner', INNER_OUT] + passthrough
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, creationflags=CREATE_NO_WINDOW)
    launch = (proc.stdout or proc.stderr or '').strip().replace('\n', ' | ')
    say('  elevation: %s' % (launch[:300] or '(no answer from launch-as-token)'))
    # THE OUTER WAIT COVERS EVERY ARM. One arm costs about the app's own startup
    # (measured: 83 s on a loaded box) plus its `--exit-after`, and the inner
    # process runs one arm per variant.
    arms = len([t for t in str(args.variants).split(',') if t.strip()])
    deadline = time.monotonic() + arms * (args.seconds + args.find_timeout) + 180
    while time.monotonic() < deadline:
        text = read_text(INNER_OUT)
        if 'INNER rc=' in text:
            break
        time.sleep(0.5)
    text = read_text(INNER_OUT)
    if not text:
        return None
    for line in text.rstrip().splitlines():
        say(line)
    m = re.search(r'INNER rc=(-?\d+)', text)
    return int(m.group(1)) if m else None



def wait_for_panel(deadline_s, log_path):
    """(shell_pid, hwnd) read from the APP'S OWN LOG, with EnumWindows as the net.

    The pid comes from the banner (`shell=webview2 ... pid=N`); the hwnd from any
    line the app writes about itself that carries one (`PANEL_VISIBILITY_*` and,
    since 2026-11-01, `PANEL_SHOWN ... hwnd=`), and EnumWindows by pid only when
    no such line has landed yet. Nothing here can bind to the owner's live
    instance, which also owns a window called `Sotto` but has a different pid.
    """
    t0 = time.monotonic()
    pid = 0
    while time.monotonic() - t0 < deadline_s:
        text = read_text(log_path)
        if text:
            if not pid:
                m = re.search(r'^[^\n]*shell=webview2[^\n]*\bpid=(\d+)', text, re.M)
                if m:
                    pid = int(m.group(1))
            m = re.search(r'PANEL_SHOWN[^\n]*\bhwnd=(\d+)', text) \
                or re.search(r'PANEL_VISIBILITY_\w+[^\n]*\bhwnd=(\d+)', text)
            if m and int(m.group(1)):
                return pid, int(m.group(1))
            if pid:
                hwnd = _top_level_for_pid(pid)
                if hwnd:
                    return pid, hwnd
        time.sleep(0.05)
    return pid, 0


def _top_level_for_pid(pid):
    hits = []

    def cb(hwnd, _lp):
        if window_pid(hwnd) != pid:
            return True
        if window_text(hwnd) != 'Sotto':
            return True
        hits.append(int(hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return hits[0] if hits else 0


def app_finished():
    proc = _APP.get('proc')
    return proc is not None and proc.poll() is not None


def arm_app(args, tag):
    """Build the variant, launch it, capture across every show it makes."""
    shell = build_variant(tag)
    log_path = os.path.join(TMP, 'panel-paint-first-%s.log' % (tag,))
    out_path = os.path.join(TMP, 'panel-paint-first-%s.out' % (tag,))
    hotkey = FREE_HOTKEYS[0] if tag == 'cured' else FREE_HOTKEYS[1]
    mutex = '%s-%s' % (MUTEX, tag)
    say('')
    say('== ARM app[%s]: %s (private mutex, free key, owner token) =='
        % (tag, os.path.basename(shell)))
    say('  source: %s' % ('app/webview/sotto_webview.py (the worktree, now)'
                          if tag == 'cured' else
                          'git show HEAD:app/webview/sotto_webview.py (before the cure)'))
    try:
        say('  launch: %s' % spawn_app(args.exit_after, hotkey, shell, log_path,
                                       out_path, mutex))
        pid, hwnd = wait_for_panel(args.find_timeout, log_path)
        if not pid or not hwnd:
            log_tail = read_text(log_path).strip().splitlines()[-4:]
            say('  FIND FAILED pid=%s hwnd=%s' % (pid, hwnd))
            for line in log_tail:
                say('    log: %s' % line[:180])
            return {'ok': False, 'why': 'panel-window-not-found', 'variant': tag,
                    'log_path': log_path}

        say('  panel hwnd=%d pid=%d (from the app log)' % (hwnd, pid))
        stop = threading.Event()
        box = {}

        def loop():
            box['frames'], box['grabber'] = capture_for(hwnd, args.seconds,
                                                        stop=stop)

        # the capture runs WHILE the app works; the app's own exit ends it
        th = threading.Thread(target=loop, daemon=True)
        th.start()
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline and not app_finished():
            time.sleep(0.2)
        stop.set()
        th.join(timeout=10)
        got = box.get('frames') or []
        grabber = box.get('grabber')
        if grabber is not None:
            durations = sorted(grabber.durations)
            say('  capture: %d frames, %d grab failures %s, grab_ms p50=%.1f p95=%.1f'
                % (len(got), grabber.failures, grabber.reasons or '',
                   durations[len(durations) // 2] if durations else -1.0,
                   durations[int(len(durations) * 0.95)] if durations else -1.0))
            grabber.close()
        if len(got) > 1:
            span = got[-1]['t'] - got[0]['t']
            say('  capture rate: %.1f Hz over %.1f s'
                % ((len(got) - 1) / span if span else 0, span))
        text = read_text(log_path)
        shows = re.findall(r'PANEL_SHOWN[^\n]*', text)
        app_runs, ignored = split_startup_dance(runs_of_visible(got, onscreen=True))
        say('  log: PANEL_SHOWN x%d  PANEL_HIDDEN x%d  |  measured visible '
            'stretches=%d  ignored_startup_map=%d  driver x%d'
            % (len(shows), len(re.findall(r'PANEL_HIDDEN', text)), len(app_runs),
               len(ignored), len(re.findall(r'CENSUS_DRIVER show=', text))))
        for run in ignored:
            say('  IGNORED stretch frames=%d size=%s std=%s -- pywebview\'s '
                '`hidden=True` dance maps the form for microseconds with '
                'Opacity=0 before anything paints (measured 2026-10-12); it is '
                'not a show and nobody asked for it'
                % (len(run), run[0].get('size'), run[0].get('std')))
        results = []
        for n, run in enumerate(app_runs, 1):
            row = summarise_run(run, got, pid)
            row['show'] = n
            row['log'] = (shows[n - 1][:160] if n - 1 < len(shows)
                          else '(no PANEL_SHOWN line)')
            results.append(row)
        ack_lines = re.findall(r'PAINT_ACK ack=[^\n]*', text)
        for warm in re.findall(r'PAINT_WARM [^\n]*', text):
            say('  warm: %s' % warm[:160])
        fg_lines = re.findall(r'FOREGROUND_(?:TAKEN|KEPT)[^\n]*', text)
        for row in results:
            say('')
            say('  SHOW #%d  blank_frames=%d  first_content_ms=%s  '
                'visible_frames=%d  later_blanks=%d  capture_failures=%d'
                % (row['show'], row['blank_frames'], row['first_content_ms'],
                   row['visible_frames'], row['later_blank_frames'],
                   row['capture_failures']))
            say('    staged: frames=%d ms=%s (visible, OFF the virtual screen: '
                'nobody could see those frames)'
                % (row['staged_frames'], row['staged_ms']))
            say('    first frame: std=%s spread=%s mean=%s size=%s  (blank if std<=%s)'
                % (row['first_std'], row['first_spread'], row['first_mean'],
                   row['first_size'], BLANK_STD_MAX))
            say('    focus: before_pid=%s after_pid=%s stolen_by_shell=%s'
                % (row['focus_before_pid'], row['focus_after_pid'],
                   str(row['focus_stolen_by_shell']).lower()))
            say('    log: %s' % row['log'])
            # POR `reason=`, NAO POR INDICE: o aquecimento de arranque tambem
            # escreve `PAINT_ACK`, portanto o n-esimo ack do log ja' nao e' o
            # n-esimo show.
            reason = re.search(r'reason=(\S+)', row['log'])
            want = 'reason=%s ' % (reason.group(1),) if reason else None
            ack = next((l for l in ack_lines if want and want in l + ' '), None)
            if ack:
                say('    ack: %s' % ack[:160])
            if row['show'] - 1 < len(fg_lines):
                say('    fg : %s' % fg_lines[row['show'] - 1][:160])
        if not results:
            say('  NO SHOW MEASURED -- the visible stretches are empty; the log tail:')
            for line in text.strip().splitlines()[-6:]:
                say('    log: %s' % line[:180])
        return {'ok': bool(results), 'why': '' if results else 'no-show-measured',
                'shows': results, 'pid': pid, 'hwnd': hwnd, 'variant': tag,
                'log_path': log_path,
                'log_tail': text.strip().splitlines()[-8:], 'rc': _app_rc()}
    finally:
        drop_variant(shell)


def _app_rc():
    """The instance's own exit code, and a clean kill if it overran its budget.

    A private instance left running is a hidden window with a tray icon on the
    owner's desk; the budget expiring is not a reason to leave it there.
    """
    proc = _APP.get('proc')
    rc = proc.poll() if proc is not None else None
    if rc is None and proc is not None:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        say('  instance overran its budget: killed pid=%s' % proc.pid)
        rc = proc.poll()
    out = _APP.get('stdout')
    if out is not None:
        try:
            out.close()
        except Exception:  # noqa: BLE001
            pass
    return rc


# ---------------------------------------------------------------------------
# the control arm -- the SAME classifier, on a window whose truth we own
# ---------------------------------------------------------------------------

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)
WM_DESTROY, WM_PAINT, WM_ERASEBKGND = 0x0002, 0x000F, 0x0014
WM_PRINT, WM_PRINTCLIENT = 0x0317, 0x0318
WS_POPUP, WS_CLIPCHILDREN = 0x80000000, 0x02000000


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('style', wintypes.UINT),
                ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int), ('hInstance', ctypes.c_void_p),
                ('hIcon', ctypes.c_void_p), ('hCursor', ctypes.c_void_p),
                ('hbrBackground', ctypes.c_void_p),
                ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR),
                ('hIconSm', ctypes.c_void_p)]


user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                   wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                  wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_void_p]
user32.FillRect.restype = ctypes.c_int
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT), wintypes.BOOL]
user32.InvalidateRect.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.CreateSolidBrush.restype = ctypes.c_void_p
gdi32.SetTextColor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
gdi32.SetBkMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.DrawTextW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_int,
                             ctypes.POINTER(RECT), wintypes.UINT]
user32.DrawTextW.restype = ctypes.c_int
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.BeginPaint.restype = ctypes.c_void_p
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.EndPaint.restype = wintypes.BOOL


class ControlWindow:
    """A window we own: painted flat first, populated on request.

    It is the negative arm of the classifier and it sits OFF the owner's screen
    (`x=-10000`, `SW_SHOWNOACTIVATE`). Position does not change what
    `PrintWindow` renders -- the house measured that (`_main/panel-paint-probe.py`
    moves its copies to x=-10000 and still reads distinct colours) -- and the
    window is ours, so the paint is GDI and unconditional.
    """

    COUNT = 0

    def __init__(self, w=380, h=140, populated=False):
        ControlWindow.COUNT += 1
        self.name = 'SottoPaintFirstControl%d' % ControlWindow.COUNT
        self.phase = 1 if populated else 0           # 0 = flat, 1 = populated
        self.w, self.h = w, h
        self._proc = WNDPROC(self._wndproc)          # keep a reference alive
        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
        cls.lpfnWndProc = self._proc
        cls.lpszClassName = self.name
        if not user32.RegisterClassExW(ctypes.byref(cls)):
            raise OSError('RegisterClassExW failed err=%s'
                          % ctypes.get_last_error())
        self.hwnd = int(user32.CreateWindowExW(
            0, self.name, self.name, WS_POPUP | WS_CLIPCHILDREN,
            -10000, -10000, w, h, None, None, None, None) or 0)
        if not self.hwnd:
            raise OSError('CreateWindowExW failed err=%s' % ctypes.get_last_error())

    def map_it(self):
        user32.ShowWindow(wintypes.HWND(self.hwnd), SW_SHOWNOACTIVATE)
        return bool(user32.IsWindowVisible(wintypes.HWND(self.hwnd)))

    def paint_now(self):
        """Run the real paint WHILE still hidden -- the "already painted" state.

        The positive control needs the window's content to exist BEFORE the map,
        because that is the state the app must reach: content ready, then mapped.
        A window mapped before its first `WM_PAINT` reads blank for one frame,
        which is a fact about the map and not about the classifier.
        """
        user32.InvalidateRect(wintypes.HWND(self.hwnd), None, True)
        user32.UpdateWindow(wintypes.HWND(self.hwnd))

    def populate(self):
        self.phase = 1
        user32.InvalidateRect(wintypes.HWND(self.hwnd), None, True)
        user32.UpdateWindow(wintypes.HWND(self.hwnd))

    def destroy(self):
        user32.ShowWindow(wintypes.HWND(self.hwnd), SW_HIDE)
        user32.DestroyWindow(wintypes.HWND(self.hwnd))

    # -- the paint, in ONE place because WM_PAINT and WM_PRINTCLIENT must agree
    def _paint(self, hdc):
        rect = RECT(0, 0, self.w, self.h)
        base = gdi32.CreateSolidBrush(0x00202020)     # COLORREF 0x00BBGGRR
        user32.FillRect(hdc, ctypes.byref(rect), base)
        gdi32.DeleteObject(base)
        if not self.phase:
            return
        colours = (0x00E0E0E0, 0x003050A0, 0x0020A050, 0x00C04040,
                   0x00F0C040, 0x00A040C0)
        bar = max(8, self.h // (len(colours) + 2))
        for i, colour in enumerate(colours):
            brush = gdi32.CreateSolidBrush(colour)
            r = RECT(0, i * bar, self.w, (i + 1) * bar)
            user32.FillRect(hdc, ctypes.byref(r), brush)
            gdi32.DeleteObject(brush)
        gdi32.SetTextColor(hdc, 0x00FFFFFF)
        gdi32.SetBkMode(hdc, 1)                       # TRANSPARENT
        text = RECT(6, 4, self.w - 6, self.h - 4)
        user32.DrawTextW(hdc, 'Sotto paint-first control -- populated', -1,
                         ctypes.byref(text), 0x00000010)  # DT_SINGLELINE

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            ps = ctypes.create_string_buffer(72)
            hdc = user32.BeginPaint(wintypes.HWND(hwnd), ps)
            self._paint(hdc)
            user32.EndPaint(wintypes.HWND(hwnd), ps)
            return 0
        if msg == WM_ERASEBKGND:
            self._paint(wparam)
            return 1
        if msg in (WM_PRINT, WM_PRINTCLIENT):
            self._paint(wparam)
            return 0
        return user32.DefWindowProcW(wintypes.HWND(hwnd), msg, wparam, lparam)


def arm_control():
    """Both control arms, measured by the SAME classifier the app arm uses."""
    say('')
    say('== ARM control: our own window, same classifier, off the owner screen ==')
    out = {}
    # 1. flat first, populated later: MUST report blank_frames > 0
    win = ControlWindow(populated=False)
    try:
        mapped = win.map_it()
        switch_at = 0.9
        state = {'done': False, 't0': None}

        def maybe_populate(index, frame):
            if state['t0'] is None:
                state['t0'] = frame['t']
            if not state['done'] and frame['t'] - state['t0'] >= switch_at:
                state['done'] = True
                win.populate()

        frames, grabber = capture_for(win.hwnd, 1.8, on_frame=maybe_populate)
        grabber.close()
        runs = runs_of_visible(frames)
        row = summarise_run(runs[0], frames, 0) if runs else None
        out['blank_first'] = {'mapped': mapped, 'row': row, 'frames': len(frames),
                              't_switch_s': switch_at}
        say('  control-blank-first  mapped=%s frames=%d  blank_frames=%s  '
            'first_content_ms=%s  capture_failures=%s'
            % (str(mapped).lower(), len(frames),
               row['blank_frames'] if row else '(no visible frame)',
               row['first_content_ms'] if row else '(none)',
               row['capture_failures'] if row else '-'))
        stds_blank = [f['std'] for f in frames if f.get('ok') and f['t'] - frames[0]['t'] < switch_at]
        stds_content = [f['std'] for f in frames
                        if f.get('ok') and f['t'] - frames[0]['t'] >= switch_at + 0.1]
        say('    measured: std flat<=%.1f  std populated>=%.1f  (threshold %.2f)'
            % (max(stds_blank) if stds_blank else -1,
               min(stds_content) if stds_content else -1, BLANK_STD_MAX))
        out['blank_first']['std_flat_max'] = max(stds_blank) if stds_blank else None
        out['blank_first']['std_populated_min'] = (min(stds_content)
                                                  if stds_content else None)
    finally:
        win.destroy()
    # 2. populated from the first frame: MUST report blank_frames == 0
    win = ControlWindow(populated=True)
    try:
        win.paint_now()
        mapped = win.map_it()
        # AND THE PAINT IS FORCED ONCE MORE, SYNCHRONOUSLY, AFTER THE MAP. The
        # state the app must reach is "content ready AT the map", and this window
        # is ours, so it can reach it exactly: `UpdateWindow` before the map does
        # not paint a window that has never been mapped, and this one runs on the
        # census's OWN thread, so it returns only after `WM_PAINT` completed.
        #
        # E MESMO ASSIM A PRIMEIRA FRAME CAPTURADA VEM `std=0.0 mean=0.0` -- o
        # buffer INTEIRO a zero, incluindo os bytes que o `PrintWindow` devia ter
        # escrito (a linha `first frames` imprime-a ao lado da de conteudo). Isso
        # nao e' uma frame chapada: e' o DWM sem superficie para uma janela
        # mapeada um microssegundo antes, com `PrintWindow` a devolver TRUE e a
        # nao escrever nada. `Grabber.grab` classifica-a como CAPTURA PERDIDA
        # (`no-surface`) e `summarise_run` salta-a, como ja' fazia com
        # `printwindow-false`: uma captura que nao existe nao pode virar um blank.
        win.paint_now()
        frames, grabber = capture_for(win.hwnd, 0.5)
        grabber.close()
        runs = runs_of_visible(frames)
        row = summarise_run(runs[0], frames, 0) if runs else None
        out['content_first'] = {'mapped': mapped, 'row': row, 'frames': len(frames)}
        say('  control-content-first mapped=%s frames=%d  blank_frames=%s  '
            'capture_failures=%s'
            % (str(mapped).lower(), len(frames),
               row['blank_frames'] if row else '(no visible frame)',
               row['capture_failures'] if row else '-'))
        say('    grab failures: %s' % (grabber.reasons or '{}'))
        say('    first frames: %s'
            % ' '.join('i%d[%s std=%s spread=%s mean=%s]'
                       % (f['i'], 'ok' if f.get('ok') else f.get('why'),
                          f.get('std'), f.get('spread'), f.get('mean'))
                       for f in frames[:5]))
    finally:
        win.destroy()
    return out


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------

def verdict(apps, control, ran_control):
    """cured must be clean, uncured must be RED, and the controls must behave.

    THE RED CLAUSE IS NOT OPTIONAL. Without it a "blank_frames=0" is a claim by
    an instrument that has never been shown to see the defect; with it, the same
    process, the same capture and the same classifier call the PRE-CURE bytes
    blank and the cured bytes content on the same box in the same minute.
    """
    fails = []
    cured = apps.get('cured')
    uncured = apps.get('uncured')
    if cured is not None:
        if not cured.get('ok'):
            fails.append('app[cured] measured no show (%s)' % (cured.get('why'),))
        else:
            bad = [r for r in cured['shows'] if r['blank_frames'] > 0]
            if bad:
                fails.append('app[cured] shows with blank first frames: %s'
                             % ', '.join('#%d=%d' % (r['show'], r['blank_frames'])
                                         for r in bad))
            never = [r for r in cured['shows'] if r['first_content_ms'] is None]
            if never:
                fails.append('app[cured] shows that never reached content: %s'
                             % ', '.join('#%d' % (r['show'],) for r in never))
    if uncured is not None:
        if not uncured.get('ok'):
            fails.append('app[uncured] measured no show (%s) -- the instrument '
                         'never saw the defect it claims to measure'
                         % (uncured.get('why'),))
        else:
            red = [r for r in uncured['shows'] if r['blank_frames'] > 0]
            if not red:
                fails.append('app[uncured] reported blank_frames=0 on EVERY show '
                             '-- the classifier cannot see the blank-first-frame '
                             'defect, so the cured zeros mean nothing')
    if ran_control:
        a = control.get('blank_first') or {}
        b = control.get('content_first') or {}
        if not a.get('row') or a['row']['blank_frames'] <= 0:
            fails.append('control-blank-first did NOT report blank>0 -- the '
                         'classifier cannot see the defect, so the app zeros mean '
                         'nothing')
        if (not b.get('row') or b['row']['blank_frames'] != 0
                or b['row']['first_content_ms'] is None):
            fails.append('control-content-first did not land on a CONTENT frame '
                         'with blank_frames=0 -- either the classifier calls '
                         'everything blank or it never captured the window')
    return (not fails), fails


def load_reading(path):
    """The `--json` blob out of a saved report, or out of a battery log that holds it.

    A battery step captures stdout, so the report usually arrives wrapped in the
    VERDICT lines. Taking the LAST balanced `{...}` keeps both shapes working and
    never guesses which brace started the object.
    """
    text = open(path, encoding='utf-8', errors='replace').read()
    try:
        return json.loads(text)
    except ValueError:
        pass
    end = text.rfind('}')
    while end != -1:
        start = text.rfind('{', 0, end)
        while start != -1:
            try:
                return json.loads(text[start:end + 1])
            except ValueError:
                start = text.rfind('{', 0, start)
        end = text.rfind('}', 0, end)
    raise SystemExit('--judge: no JSON reading in %s -- nothing was measured there'
                     % (path,))


def judge_reading(reading):
    """`(ok, fails)` for a reading, by the SAME rules the live run uses."""
    apps = reading.get('apps') or {}
    control = reading.get('control') or {}
    return verdict(apps, control, bool(control))


def neg_arm(reading):
    """Four mutations of a clean reading; every one MUST be refused.

    The point is not that the judge can say PASS -- it is that each of its three
    clauses can fail. A gate nobody has shown to be able to go RED is a comment.
    """
    import copy
    cases = []

    def mutate(label, fn):
        r = copy.deepcopy(reading)
        fn(r)
        ok, fails = judge_reading(r)
        cases.append((label, not ok, fails))

    def blank_first_show(r):
        r['apps']['cured']['shows'][0]['blank_frames'] = 1

    def never_content(r):
        r['apps']['cured']['shows'][0]['first_content_ms'] = None

    def blind_classifier(r):
        for sh in r['apps']['uncured']['shows']:
            sh['blank_frames'] = 0

    def dead_control(r):
        r['control']['blank_first']['row']['blank_frames'] = 0

    mutate('cured-show-1-blank', blank_first_show)
    mutate('cured-never-content', never_content)
    mutate('classifier-blind-on-uncured', blind_classifier)
    mutate('control-blank-first-silent', dead_control)
    base_ok, base_fails = judge_reading(reading)
    caught = [c for c in cases if c[1]]
    print('NEG-ARM cases=%d caught=%d' % (len(cases), len(caught)))
    for label, refused, fails in cases:
        print('  %-32s %s  %s' % (label, 'RED-as-required' if refused else
                                  'NOT-CAUGHT', (fails or ['-'])[0]))
    print('  base reading on its own: %s' % ('PASS' if base_ok else
                                             'FAIL ' + '; '.join(base_fails)))
    if caught and base_ok:
        print('NEG-ARM PASS')
        return 1   # convencao da casa: o braco negativo PASSOU sai rc=1 e o passo e' expect-red
    print('NEG-ARM FAIL -- the judge cannot tell a clean reading from a broken one')
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--run', action='store_true',
                    help='medir (sem isto imprime a ajuda)')
    ap.add_argument('--app-only', action='store_true')
    ap.add_argument('--control-only', action='store_true')
    ap.add_argument('--variants', default='cured,uncured',
                    help='quais bytes da app medir: cured (o worktree), uncured '
                         '(HEAD), ou os dois separados por virgula')
    ap.add_argument('--seconds', type=float, default=400.0,
                    help='tecto do braco da app (a app sai sozinha por --exit-after)')
    ap.add_argument('--exit-after', type=float, default=360.0,
                    help='a instancia privada sai sozinha; tem de sobrar tempo '
                         'para a pagina carregar. MEDIDO 2026-11-02: o braco '
                         '`uncured` (shell do HEAD, copia fria) levou 158,7 s ate '
                         'ao primeiro show com 170 s de tecto -- a instancia saiu a '
                         'meio do driver, ficou 1 show de 3, e o controlo perdeu a '
                         'forca sem que nada estivesse errado na app')
    ap.add_argument('--find-timeout', type=float, default=90.0)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--save-json', metavar='PATH', default='',
                    help='grava a leitura para o portao a poder re-julgar sem '
                         'lancar nada (e o que a bateria le)')
    ap.add_argument('--judge', metavar='PATH', default='',
                    help='re-julga uma leitura ja gravada; nao lanca a app')
    ap.add_argument('--neg-arm', action='store_true',
                    help='com --judge: quatro mutacoes de uma leitura limpa, e '
                         'todas tem de ser recusadas')
    ap.add_argument('--inner', metavar='PATH', default='',
                    help='(uso interno) corre a medicao e escreve o relatorio neste '
                         'ficheiro -- e o braco que corre com o token do dono')
    args = ap.parse_args(argv)
    if getattr(args, 'save_json', ''):
        # ABSOLUTO antes do `elevate`: o filho corre com outro cwd (medido: a
        # leitura ia para o cwd do lancador e o portao nao a achava).
        args.save_json = os.path.abspath(args.save_json)
    if args.judge:
        reading = load_reading(args.judge)
        if args.neg_arm:
            return neg_arm(reading)
        ok, fails = judge_reading(reading)
        apps = reading.get('apps') or {}
        for tag in sorted(apps):
            shows = apps[tag].get('shows') or []
            print('REPLAY app[%s]: shows=%d blank_frames=%s first_content_ms=%s'
                  % (tag, len(shows), [r['blank_frames'] for r in shows],
                     [r['first_content_ms'] for r in shows]))
        print('VERDICT: %s%s' % ('PASS' if ok else 'FAIL',
                                 '' if ok else '  (%s)' % '; '.join(fails)))
        return 0 if ok else 1
    if not args.run:
        ap.print_help()
        return 2
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    if not args.inner:
        # UIPI: so' um processo da MESMA integridade que a app lhe pode pedir os
        # pixeis (`PrintWindow -> err=5` foi medido: ver `spawn_app`). Por isso o
        # padrao e' re-executar a medicao com o token do dono e imprimir o relatorio.
        say('panel-paint-first-census | shell=%s | blank if std<=%.2f and spread<=%d'
            % (os.path.basename(SHELL), BLANK_STD_MAX, BLANK_SPREAD_MAX))
        say('== elevation: the same census, with the owner\'s token (UIPI) ==')
        rc = elevate(args)
        if rc is None:
            say('VERDICT: FAIL  (could not run the census at the app\'s integrity: '
                'no report from the elevated arm -- nothing was measured)')
            return 2
        return rc
    global _fh
    os.makedirs(TMP, exist_ok=True)
    _fh = open(args.inner, 'w', encoding='utf-8', errors='replace')
    try:
        rc = _measure(args)
        say('INNER rc=%d' % rc)
        return rc
    finally:
        try:
            _fh.close()
        except Exception:  # noqa: BLE001
            pass


def _measure(args):
    tags = parse_variants(args)
    ran_app = not args.control_only and bool(tags)
    ran_control = not args.app_only
    say('panel-paint-first-census | shell=%s | blank if std<=%.2f and spread<=%d'
        % (os.path.basename(SHELL), BLANK_STD_MAX, BLANK_SPREAD_MAX))
    apps = {}
    control = {}
    if ran_app:
        for tag in tags:
            apps[tag] = arm_app(args, tag)
            shows = apps[tag].get('shows') or []
            blanks = [r['blank_frames'] for r in shows]
            say('  APP[%s] RESULT: shows=%d blank_frames=%s first_content_ms=%s'
                % (tag, len(shows), blanks,
                   [r['first_content_ms'] for r in shows]))
            if apps[tag].get('ok') and any(b > 0 for b in blanks):
                say('  NOTE: app[%s] began a show on a BLANK frame -- that is the '
                    'owner\'s defect, measured.' % (tag,))
    if ran_control:
        control = arm_control()
    ok, fails = verdict(apps, control, ran_control)
    say('')
    for tag in [t for t in tags if t in apps]:
        shows = apps.get(tag, {}).get('shows') or []
        say('VERDICT app[%s]: shows=%d blank_frames=%s first_content_ms=%s'
            % (tag, len(shows), [r['blank_frames'] for r in shows],
               [r['first_content_ms'] for r in shows]))
    if ran_control:
        a = (control.get('blank_first') or {})
        b = (control.get('content_first') or {})
        say('VERDICT control: blank-first blank_frames=%s (must be >0) | '
            'content-first blank_frames=%s (must be 0)'
            % (a.get('row', {}).get('blank_frames') if a.get('row') else None,
               b.get('row', {}).get('blank_frames') if b.get('row') else None))
    say('VERDICT: %s%s' % ('PASS' if ok else 'FAIL',
                           '' if ok else '  (%s)' % '; '.join(fails)))
    reading = {'apps': apps, 'control': control, 'ok': ok, 'fails': fails}
    if args.json:
        say(json.dumps(reading, indent=1, default=str))
    if getattr(args, 'save_json', ''):
        os.makedirs(os.path.dirname(os.path.abspath(args.save_json)), exist_ok=True)
        with open(args.save_json, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(reading, fh, indent=1, default=str)
        say('SAVED %s' % (args.save_json,))
    if any(not apps.get(t, {}).get('ok') for t in tags if t in apps):
        return 2
    return 0 if ok else 1


def parse_variants(args):
    """`--variants cured,uncured` -> the tags, refused if one is unknown."""
    tags = [t.strip() for t in str(args.variants).split(',') if t.strip()]
    for tag in tags:
        if tag not in ('cured', 'uncured'):
            raise SystemExit('--variants: unknown %r (cured|uncured)' % (tag,))
    if not tags:
        raise SystemExit('--variants: nothing to measure')
    return tags


if __name__ == '__main__':
    raise SystemExit(main())
