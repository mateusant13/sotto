#!/usr/bin/env python
"""GATE: a janela da legenda diz `visible=true` e o dono NAO A VE -- o numero que
decide isso agora tem um PORTAO, nao uma linha de log.

O DEFEITO MEDIDO (P0 do dono). `CAPTION_OVERLAY_PUSH count=1 visible=true
hwnd=1775132` apareceu no log dele e a legenda nao estava no ecra. `visible` e'
o que NOS dissemos ao `ShowWindow`; a pergunta dele e' outra -- a janela esta'
DENTRO da area de trabalho de um monitor e o alfa dela NAO e' zero? O
`caption_overlay.NativeCaptionOverlay._screen_proof()` responde a essa pergunta
lendo o Windows (`GetWindowRect`, `MonitorFromPoint`, `GetMonitorInfoW`,
`GetLayeredWindowAttributes`). O log `CAPTION_OVERLAY_GEOMETRY shown=true
on_screen=.. rect=.. alpha=..` existia -- e NADA o julgava: `grep -c
CAPTION_OVERLAY_GEOMETRY _main/_audit-verify-all.cmd` = 0. Um campo por onde
passou a queixa do dono nao pode ser um campo que ninguem le.

O QUE ESTE ORACULO FAZ. Executa a FUNCAO REAL -- nao uma copia da regra -- com
a janela que ele proprio cria (oculta), e julga as quatro classes de resposta:

  A1 `real-win32-rect-and-alpha`      [WIN32 REAL]
      Cria uma janela `WS_EX_LAYERED` (nunca mostrada: sem `WS_VISIBLE`, em
      `-4000,-4000`) e chama `_screen_proof()` com o `user32` verdadeiro. Exige
      `rect == (-4000, -4000, 400, 90)` -- a PROVA de que a leitura veio do
      `GetWindowRect` e nao de um valor de estado -- e `alpha == 255`, o valor
      posto pelo `SetLayeredWindowAttributes` e LIDO de volta.
  A2 `real-win32-on_screen-cross-check` [WIN32 REAL]
      O `on_screen` devolvido tem de concordar com uma RECONTA independente do
      mesmo predicado no mesmo centro (`MonitorFromPoint`+`GetMonitorInfoW`).
  A3 `stub-inside-true`               [STUB]
      Um ponto DENTRO da area de trabalho -> `on_screen=True`.
  A4 `stub-outside-false`             [STUB]
      Um ponto FORA de todos os monitores -> `on_screen=False`.
  A5 `stub-alpha-zero-reported`       [STUB]
      `GetLayeredWindowAttributes` a responder 0 -> o alfa E' RELATADO como 0 e
      o veredicto do proprio oraculo e' `RED` por 'invisible'. E' exactamente a
      classe do dono: `visible=true`, nada no ecra. Um alfa 0 nao pode passar
      por visivel so' porque `ShowWindow` foi chamado.
  A6 `stub-failure-logged`            [STUB]
      Uma leitura que rebenta tem de SAIR pelo caminho de falha: a linha
      `CAPTION_OVERLAY_GEOMETRY_FAILED` no log e o retorno `(None, None, -1)`.
  A7 `measured-in-show`               [FONTE]
      O `show()` continua a chamar `_screen_proof()` e a publicar `on_screen=`
      e `alpha=` -- o portao mede uma funcao que o produto ainda usa.

WIN32 REAL vs STUB, POR ARM: A1/A2 correm contra `user32` verdadeiro (uma
janela LAYERED real, oculta, criada neste processo; nada e' mostrado). A3-A6
correm com um `user32` SUBSTITUIDO que responde por aritmetica -- a janela real
continua a existir, mas a geometria e o alfa vem do stub, para a assercao ser
determinista em qualquer maquina (um monitor em `-4000` mudaria o resultado
real de A4).

--neg-arm: quatro mutacoes de uma COPIA de `caption_overlay.py` (a area de
trabalho invertida; o alfa ignorado; o fecho de falha descartado; o rect
calculado de `self.visible` em vez do `GetWindowRect`). As quatro TEM de ser
apanhadas: rc=1 e `NEG-ARM`. Uma que escape -> rc=0.

Exit: 0 verde, 1 vermelho, 2 erro de setup.
"""
# NO-BUG: portao do P0 'visible=true e nao vi nada' -- executa o `_screen_proof` real e recusa um alfa 0 como visivel
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import os
import sys
import tempfile
from ctypes import wintypes as wt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
WEBVIEW = os.path.join(ROOT, "app", "webview")
OVERLAY = os.path.join(WEBVIEW, "caption_overlay.py")

WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
LWA_ALPHA = 0x00000002

REAL_RECT = (-4000, -4000, 400, 90)      # a janela do oraculo: fora do ecra
INSIDE_RECT = (200, 200, 400, 90)        # aritmetica do stub: centro (400,245)
OUTSIDE_RECT = (-4000, -4000, 400, 90)   # centro negativo, fora de tudo
WORK = (0, 0, 1920, 1032)                # area de trabalho que o stub declara

MONITOR = 0x1000                         # handle inventado pelo stub, nao nulo


# ---------------------------------------------------------------- utilidades


def say(text):
    print(text)


def judge(proof):
    """O VEREDICTO do oraculo para uma leitura: (cor, razao).

    `alpha == 0` e' RED por 'invisible' e nao por 'unmeasured': ha' janela, ela
    esta' no ecra e nada dela aparece -- a classe exacta que o dono reportou.
    """
    if not isinstance(proof, tuple) or len(proof) != 3:
        return "RED", "malformed proof=%r" % (proof,)
    on_screen, rect, alpha = proof
    if on_screen is None or rect is None:
        return "RED", "unmeasured proof=%r" % (proof,)
    if on_screen is not True:
        return "RED", "off-screen"
    if alpha is None or int(alpha) <= 0:
        return "RED", "invisible: alpha=%r" % (alpha,)
    return "GREEN", "on_screen alpha=%d" % int(alpha)


def load_module(path, name):
    """O modulo COMO ESTA' NO DISCO -- e' a funcao real que corre, nao uma copia da regra."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Subject(object):
    """O objecto que `_screen_proof` le': so' `hwnd` e `log`."""

    def __init__(self, hwnd, log):
        self.hwnd = hwnd
        self.log = log.append


def probe(module, hwnd, user32, log):
    """Chama `_screen_proof` com o `user32` dado; devolve a leitura ou o erro."""
    previous = module._user32
    module._user32 = user32
    try:
        subject = Subject(hwnd, log)
        try:
            return module.NativeCaptionOverlay._screen_proof(subject)
        except Exception as exc:                       # noqa: BLE001
            return ("RAISED", exc)
    finally:
        module._user32 = previous


# ---------------------------------------------------------------- stub do user32


class StubUser32(object):
    """Responde as quatro leituras por ARITMETICA -- sem Win32 nenhum.

    `fail=True` faz o `GetWindowRect` levantar: e' o braco do caminho de falha.
    """

    def __init__(self, rect=INSIDE_RECT, work=WORK, alpha=255, fail=False):
        self.rect = rect
        self.work = work
        self.alpha = alpha
        self.fail = fail

    def GetWindowRect(self, hwnd, pointer):
        if self.fail:
            raise OSError("stub: GetWindowRect unavailable")
        target = pointer._obj
        left, top, width, height = self.rect
        target.left = left
        target.top = top
        target.right = left + width
        target.bottom = top + height
        return 1

    def MonitorFromPoint(self, point, flags):
        # Um monitor NEAREST EXISTE sempre (no Windows real `2` nunca devolve 0);
        # o que decide "fora do ecra" e' o `rcWork` nao conter o centro.
        return MONITOR

    def GetMonitorInfoW(self, monitor, pointer):
        target = pointer._obj
        left, top, right, bottom = self.work
        target.rcMonitor = wt.RECT(left, top, right, bottom)
        target.rcWork = wt.RECT(left, top, right, bottom)
        target.dwFlags = 0
        return 1

    def GetLayeredWindowAttributes(self, hwnd, key, alpha, flags):
        alpha._obj.value = self.alpha
        flags._obj.value = LWA_ALPHA
        return 1


# ---------------------------------------------------------------- janela real


class RealWindow(object):
    """Uma janela LAYERED real, criada por este processo e NUNCA mostrada.

    Sem `WS_VISIBLE` e sem `ShowWindow`: ela nasce oculta e morre oculta. O
    `WS_EX_LAYERED` e' o que faz `GetLayeredWindowAttributes` responder.
    """

    def __init__(self):
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.CreateWindowExW.restype = ctypes.c_void_p
        self.user32.CreateWindowExW.argtypes = [
            wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p]
        self.user32.SetLayeredWindowAttributes.argtypes = [
            ctypes.c_void_p, wt.DWORD, ctypes.c_ubyte, wt.DWORD]
        self.user32.DestroyWindow.argtypes = [ctypes.c_void_p]
        self.hwnd = None

    def create(self, alpha=255):
        left, top, width, height = REAL_RECT
        self.hwnd = self.user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            "STATIC", "sotto-caption-overlay-oracle", WS_POPUP,
            left, top, width, height, None, None, None, None)
        if not self.hwnd:
            raise OSError("CreateWindowExW failed error=%d"
                          % ctypes.get_last_error())
        if not self.user32.SetLayeredWindowAttributes(self.hwnd, 0, alpha,
                                                      LWA_ALPHA):
            raise OSError("SetLayeredWindowAttributes failed error=%d"
                          % ctypes.get_last_error())
        return self.hwnd

    def destroy(self):
        if self.hwnd:
            try:
                self.user32.DestroyWindow(self.hwnd)
            except Exception:                          # noqa: BLE001
                pass
            self.hwnd = None


# ---------------------------------------------------------------- as arms


def real_cross_check(window):
    """Recalcula o `on_screen` por FORA da funcao, com as mesmas quatro chamadas."""
    user32 = window.user32
    left, top, width, height = REAL_RECT
    cx = (left + left + width) // 2
    cy = (top + top + height) // 2
    user32.MonitorFromPoint.restype = ctypes.c_void_p
    monitor = user32.MonitorFromPoint(wt.POINT(cx, cy), 2)
    if not monitor:
        return False
    info = INFO()
    info.cbSize = ctypes.sizeof(INFO)
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(INFO)]
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return False
    work = info.rcWork
    return (work.left <= cx < work.right and work.top <= cy < work.bottom)


class INFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", wt.RECT),
                ("rcWork", wt.RECT), ("dwFlags", ctypes.c_ulong)]


def measure(module, window):
    """Corre as SETE arms contra um modulo carregado; devolve [(nome, ok, detalhe)]."""
    out = []
    hwnd = window.hwnd

    # ── A1: WIN32 real -- o rect e o alfa vem do Windows, nao do estado ─────
    log = []
    proof = probe(module, hwnd, module._user32, log)
    got_rect = proof[1] if isinstance(proof, tuple) and len(proof) == 3 else None
    got_alpha = proof[2] if isinstance(proof, tuple) and len(proof) == 3 else None
    want_rect = (REAL_RECT[0], REAL_RECT[1], REAL_RECT[2], REAL_RECT[3])
    out.append(("real-win32-rect-and-alpha",
                got_rect == want_rect and got_alpha == 255,
                "rect=%r alpha=%r log=%r" % (got_rect, got_alpha, log[-1:])))

    # ── A2: WIN32 real -- o on_screen concorda com uma RECONTA independente ─
    want_on = real_cross_check(window)
    got_on = proof[0] if isinstance(proof, tuple) and len(proof) == 3 else None
    out.append(("real-win32-on_screen-cross-check",
                got_on is want_on, "on_screen=%r reconta=%r" % (got_on, want_on)))

    # ── A3: stub, ponto DENTRO da area de trabalho ─────────────────────────
    log = []
    proof = probe(module, hwnd, StubUser32(rect=INSIDE_RECT), log)
    ok = (isinstance(proof, tuple) and len(proof) == 3
          and proof[0] is True and proof[1] == (200, 200, 400, 90)
          and proof[2] == 255 and judge(proof)[0] == "GREEN")
    out.append(("stub-inside-true", ok, "proof=%r verdict=%r" % (proof, judge(proof))))

    # ── A4: stub, ponto FORA de todos os monitores ─────────────────────────
    log = []
    proof = probe(module, hwnd, StubUser32(rect=OUTSIDE_RECT), log)
    ok = (isinstance(proof, tuple) and len(proof) == 3
          and proof[0] is False and judge(proof)[0] == "RED")
    out.append(("stub-outside-false", ok, "proof=%r verdict=%r" % (proof, judge(proof))))

    # ── A5: stub, alfa 0 -- a classe do dono: visible=true, nada no ecra ───
    log = []
    proof = probe(module, hwnd, StubUser32(rect=INSIDE_RECT, alpha=0), log)
    colour, why = judge(proof)
    ok = (isinstance(proof, tuple) and len(proof) == 3
          and proof[2] == 0 and colour == "RED" and "invisible" in why)
    out.append(("stub-alpha-zero-reported", ok,
                "proof=%r verdict=%s/%s" % (proof, colour, why)))

    # ── A6: stub, a leitura rebenta -- tem de sair pelo caminho de falha ───
    log = []
    proof = probe(module, hwnd, StubUser32(fail=True), log)
    ok = (proof == (None, None, -1)
          and any("CAPTION_OVERLAY_GEOMETRY_FAILED" in line for line in log))
    out.append(("stub-failure-logged", ok,
                "proof=%r log=%r" % (proof, log[-1:])))

    # ── A7: a funcao continua ligada ao produto (show publica os numeros) ──
    text = open(OVERLAY, "rb").read().decode("utf-8", "replace")
    show = text[text.find("    def show(self, on=True):"):]
    show = show[:show.find("    def hide(self):")]
    wired = ("self._screen_proof()" in show
             and "CAPTION_OVERLAY_GEOMETRY shown=true" in show
             and "on_screen=" in show and "alpha=" in show)
    out.append(("measured-in-show", wired, "wired=%s" % wired))
    return out


# ---------------------------------------------------------------- neg-arm

#: (nome, texto ANTIGO, texto NOVO, arm que TEM de ficar RED).
#: As quatro mutacoes do pedido, uma por classe de defeito que a funcao mede.
MUTANTS = (
    ("work-area-inverted",
     "            on_screen = bool(ok) and (work.left <= cx < work.right\n"
     "                                      and work.top <= cy < work.bottom)",
     "            on_screen = bool(ok) and not (work.left <= cx < work.right\n"
     "                                          and work.top <= cy < work.bottom)",
     "stub-inside-true"),
    ("alpha-ignored",
     "                alpha_v = int(alpha.value)",
     "                alpha_v = 255",
     "stub-alpha-zero-reported"),
    ("closure-discarded",
     "        except Exception as exc:              # noqa: BLE001\n"
     "            self.log('CAPTION_OVERLAY_GEOMETRY_FAILED error=%r' % (exc,))\n"
     "            return (None, None, -1)",
     "        except ZeroDivisionError as exc:      # noqa: BLE001\n"
     "            self.log('CAPTION_OVERLAY_GEOMETRY_FAILED error=%r' % (exc,))\n"
     "            return (None, None, -1)",
     "stub-failure-logged"),
    ("rect-from-self.visible",
     "            rect = wt.RECT()\n"
     "            _user32.GetWindowRect(self.hwnd, ctypes.byref(rect))",
     "            rect = (wt.RECT(0, 0, 900, 120) if getattr(self, 'visible', False)\n"
     "                    else wt.RECT(-4000, -4000, -3100, -3880))",
     "real-win32-rect-and-alpha"),
)


def run_neg_arm(text, window):
    """Quatro copias mutadas: cada uma TEM de derrubar a arm nomeada."""
    if not os.path.isdir(WEBVIEW):
        return 2
    tmp = tempfile.mkdtemp(prefix="sotto-overlay-screen-neg-")
    caught = 0
    try:
        for index, (name, old, new, arm) in enumerate(MUTANTS):
            if old not in text:
                say("  %-24s SETUP: o texto a mutar desapareceu" % name)
                return 2
            path = os.path.join(tmp, "caption_overlay_%d.py" % index)
            with open(path, "wb") as handle:
                handle.write(text.replace(old, new, 1).encode("utf-8"))
            try:
                module = load_module(path, "neg_caption_overlay_%d" % index)
                results = measure(module, window)
            except Exception as exc:                   # noqa: BLE001
                say("  %-24s SETUP: o mutante nem carrega: %r" % (name, exc))
                return 2
            failed = [item for item, ok, _detail in results if not ok]
            hit = arm in failed
            caught += 1 if hit else 0
            say("  %-24s arm=%-32s caught=%s failed=%s"
                % (name, arm, str(hit).lower(), ",".join(failed) or "-"))
    finally:
        for item in os.listdir(tmp):
            try:
                os.remove(os.path.join(tmp, item))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass
    say("NEG-ARM cases=%d caught=%d" % (len(MUTANTS), caught))
    if caught == len(MUTANTS):
        # RED POR DESENHO: as quatro foram apanhadas, logo o braco negativo PASSA.
        say("NEG-ARM: PASS")
        return 1
    say("NEG-ARM: FAIL -- %d mutante(s) sobreviveram" % (len(MUTANTS) - caught))
    return 0


# ---------------------------------------------------------------- CLI


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true",
                        help="controlo: quatro copias mutadas de caption_overlay.py "
                             "tem de fazer rc=1 e dizer NEG-ARM")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                  # noqa: BLE001
        pass
    if not os.path.isfile(OVERLAY):
        say("SETUP: %s ausente" % OVERLAY)
        return 2
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    try:
        module = load_module(OVERLAY, "caption_overlay_under_test")
    except Exception as exc:                           # noqa: BLE001
        say("SETUP: caption_overlay nao carrega: %r" % (exc,))
        return 2
    source = open(OVERLAY, "rb").read().decode("utf-8", "replace")
    window = RealWindow()
    try:
        window.create(alpha=255)
        if args.neg_arm:
            return run_neg_arm(source, window)
        results = measure(module, window)
    finally:
        window.destroy()
    failures = 0
    for name, ok, detail in results:
        say("[%s] arm: %s -- %s" % ("PASS" if ok else "FAIL", name, detail))
        if not ok:
            failures += 1
    say("")
    say("CAPTION-OVERLAY-SCREEN VERDICT %s -- arms=%d fail=%d"
        % ("PASS" if failures == 0 else "RED", len(results), failures))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
