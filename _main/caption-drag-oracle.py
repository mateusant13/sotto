#!/usr/bin/env python3
"""O ARRASTO DA LEGENDA COM CTRL -- decisao, marca, e os bracos vermelhos.

Ordem do dono, verbatim: *"segurar control, permite eu arrastar a legenda pra
onde eu quero. e o control segurado tambem vai ter um indicativo bem minimo de
que da pra arrastar a legenda"*.

Este oraculo NAO abre janela, NAO toca em `user32` e NAO le' o ecra. Ele corre
a MESMA funcao que embarca (`caption_drag.drag_plan`, pura) e o MESMO metodo que
pinta a marca (`NativeCaptionOverlay._paint_drag_affordance`), este ultimo
contra um canvas de PIXEIS falso -- a unica prova honesta de "o contorno existe
com Ctrl carregado e nao existe sem ele" sem um ecra onde olhar.

As arms:

  P1  ARMAR: Ctrl carregado, sem tocar no rato -> `armed`, nada arrasta.
  P2  ARRASTAR: pressao NOVA dentro do rect + movimento -> a janela segue o
      cursor (pos e offset exatos), `moved`.
  P3  LARGAR: o botao sobe -> deixa de arrastar, GRAVA o deslocamento.
  P4  LIMITE DO ECRA: arrastar para fora (canto superior esquerdo e inferior
      direito) -> a janela fica presa dentro da area de trabalho.
  P5  CLIQUE SEM CTRL: pressao e largar dentro do rect -> nada acontece (nem
      arrasto, nem marca, nem gravacao) -- o clique continua a passar ao video.
  P6  CTRL FORA DO RECT: pressao fora nao agarra; e um botao que JA' estava
      carregado quando o Ctrl desceu tambem nao (a pressao tem de ser nova).
  P7  ARRASTO QUE ACABA ONDE COMECOU: `moved` desfaz-se e NADA e' gravado.
  P8  PERSISTENCIA: gravar/ler o deslocamento, e um ficheiro ausente ou partido
      vale `(0, 0)` em vez de matar a legenda.
  P9  A MARCA: o metodo REAL de pintura contra um canvas falso -- com o Ctrl
      carregado muda pixeis SO' na banda da borda (interior intocado), com ele
      levantado muda ZERO; a arrastar o alfa e' 255 (solido).
  P10 O TICK: o poll ocioso NAO repinta; um tick de conteudo repinta; um tick
      com Ctrl carregado repinta (a pulsacao). E' o que impede o poll de
      esconder a revelacao.

NEG (`--neg-arm`): a decisao REAL e' copiada e mutada -- (1) sem `clamp_pos`,
(2) largar grava sempre, (3) pulsacao a zero -- e as arms que dependem disso
(P4, P7, P9) TEM de ficar vermelhas. Um oraculo que nao cai com o defeito de
volta nao mede nada.

`--cost` mede o preco da marca num bitmap GDI+ real, fora do ecra (com Ctrl
levantado vs carregado). E' o numero que o relatorio cita; nao corre por
omissao para o oraculo continuar barato.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "webview"))

import caption_drag  # noqa: E402
import caption_overlay  # noqa: E402

WORK = {"x": 0, "y": 0, "width": 1920, "height": 1080}
RECT = (660, 900, 600, 120)          # x, y, w, h -- onde a legenda vive
CURSOR_IN = (900, 950)               # dentro do rect
CURSOR_OUT = (10, 10)                # fora do rect
BAND = 8                             # largura da banda de borda, em px


# ── O CANVAS FALSO: um bitmap de pixeis e o protocolo de UMA chamada ────────
class FakeCanvas:
    """Um canvas de pixeis que imita o `_DragCanvas.outline` do overlay.

    Ele nao sabe desenhar GDI+; sabe responder a' unica pergunta do oraculo:
    QUANTOS pixeis da banda da borda mudaram, e o interior ficou intocado?
    Um pixel "mudado" e' um pixel com alfa > 0 -- escrever alfa 0 nao e'
    desenhar nada (e' o mutante da pulsacao a zero).
    """

    def __init__(self, width, height):
        self.width = int(width)
        self.height = int(height)
        self.px = [[0, 0, 0, 0] for _ in range(self.width * self.height)]
        self.calls = 0

    def outline(self, x, y, w, h, colour, thickness):
        self.calls += 1
        t = max(1, int(round(float(thickness))))
        x0 = int(round(x))
        y0 = int(round(y))
        x1 = int(round(float(x) + float(w)))
        y1 = int(round(float(y) + float(h)))
        colour = [int(v) for v in colour]
        for yy in range(max(0, y0), min(y1 + 1, self.height)):
            row = yy * self.width
            for xx in range(max(0, x0), min(x1 + 1, self.width)):
                if ((xx - x0) < t or (x1 - xx) < t
                        or (yy - y0) < t or (y1 - yy) < t):
                    self.px[row + xx] = list(colour)

    # -- as perguntas -------------------------------------------------------
    def changed(self, band=None):
        """Pixeis com alfa > 0, no total ou so' fora da banda interior."""
        out = 0
        for index, cell in enumerate(self.px):
            if cell[3] <= 0:
                continue
            if band is not None:
                x = index % self.width
                y = index // self.width
                margin = min(x, y, self.width - 1 - x, self.height - 1 - y)
                if margin > band:
                    continue
            out += 1
        return out

    def interior(self, band=BAND):
        """Pixeis com alfa > 0 DENTRO do interior (tem de ser zero)."""
        out = 0
        for index, cell in enumerate(self.px):
            if cell[3] <= 0:
                continue
            x = index % self.width
            y = index // self.width
            if min(x, y, self.width - 1 - x, self.height - 1 - y) > band:
                out += 1
        return out

    def alphas(self):
        return {cell[3] for cell in self.px if cell[3] > 0}


# ── as arms: cada uma devolve (nome, ok) ────────────────────────────────────
def _step(plan, state, ctrl, lb, cursor, rect=RECT, work=WORK):
    return plan(ctrl, lb, cursor, rect, work, state=state)


def arm_arm(plan, *_):
    d = _step(plan, caption_drag.DragState(), True, False, CURSOR_IN)
    return ("P1 armar (Ctrl sem tocar no rato)", (
        d.armed and not d.dragging and not d.persist
        and d.pos == RECT[:2] and d.changed and d.offset == (0, 0)))


def arm_drag(plan, *_):
    d1 = _step(plan, caption_drag.DragState(), True, False, CURSOR_IN)
    d2 = _step(plan, d1.state, True, True, (700, 950))    # pressao NOVA
    d3 = _step(plan, d2.state, True, True, (760, 1000))   # movimento
    return ("P2 arrastar (a janela segue o cursor)", (
        d2.dragging and d2.pos == (660, 900)
        and d3.dragging and d3.pos == (720, 950)
        and d3.offset == (60, 50) and d3.moved and d3.changed))


def arm_release(plan, *_):
    d1 = _step(plan, caption_drag.DragState(), True, True, (700, 950))
    d2 = _step(plan, d1.state, True, True, (760, 1000))
    d3 = _step(plan, d2.state, True, False, (760, 1000))  # LARGAR
    return ("P3 largar (para e grava o deslocamento)", (
        not d3.dragging and d3.persist and d3.offset == (60, 50)
        and d3.pos == (720, 950) and d3.armed and d3.changed))


def arm_clamp(plan, *_):
    d1 = _step(plan, caption_drag.DragState(), True, True, (700, 950))
    left = _step(plan, d1.state, True, True, (-5000, -5000))
    right = _step(plan, left.state, True, True, (99999, 99999))
    hi = (WORK["width"] - RECT[2], WORK["height"] - RECT[3])
    return ("P4 limite do ecra (nunca sai da area de trabalho)", (
        left.pos == (0, 0) and right.pos == hi))


def arm_click_without_ctrl(plan, *_):
    d1 = _step(plan, caption_drag.DragState(), False, True, CURSOR_IN)
    d2 = _step(plan, d1.state, False, False, CURSOR_IN)
    return ("P5 clique sem Ctrl e' ignorado", (
        not d1.dragging and not d1.armed and not d1.persist
        and not d2.dragging and not d2.armed and not d2.persist
        and d2.offset == (0, 0) and d2.pos == RECT[:2] and not d2.changed))


def arm_ctrl_outside(plan, *_):
    d1 = _step(plan, caption_drag.DragState(), True, True, CURSOR_OUT)
    d2 = _step(plan, d1.state, True, True, CURSOR_IN)     # ja' carregado
    d3 = _step(plan, d2.state, True, False, CURSOR_IN)    # larga
    d4 = _step(plan, d3.state, True, True, CURSOR_IN)     # pressao nova
    return ("P6 Ctrl fora do rect nao agarra (pressao tem de ser nova)", (
        not d1.dragging and not d1.persist and d1.offset == (0, 0) and d1.armed
        and not d2.dragging and not d3.dragging
        and d4.dragging and d4.pos == RECT[:2]))


def arm_round_trip(plan, *_):
    d1 = _step(plan, caption_drag.DragState(), True, True, (700, 950))
    d2 = _step(plan, d1.state, True, True, (800, 1000))
    d3 = _step(plan, d2.state, True, True, (700, 950))    # volta ao inicio
    d4 = _step(plan, d3.state, True, False, (700, 950))   # largar
    return ("P7 arrasto que acaba onde comecou nao grava nada", (
        d2.moved and not d3.moved and not d4.persist
        and d3.offset == (0, 0) and d4.offset == (0, 0)
        and d4.pos == RECT[:2] and not d4.dragging))


def arm_persistence(plan, *_):
    folder = tempfile.mkdtemp(prefix="sotto-drag-")
    path = os.path.join(folder, "offset.json")
    missing = caption_drag.load_offset(os.path.join(folder, "nope.json"))
    saved = caption_drag.save_offset((-123, 45), path)
    loaded = caption_drag.load_offset(path)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{partido")
    corrupt = caption_drag.load_offset(path)
    return ("P8 persistencia (grava, le', e um JSON partido vale 0,0)", (
        missing == (0, 0) and saved and loaded == (-123, 45)
        and corrupt == (0, 0)))


def _paint_overlay(armed, dragging):
    """Um overlay SEM janela: so' o estado que a marca le'."""
    ov = object.__new__(caption_overlay.NativeCaptionOverlay)
    ov._drag_armed = bool(armed)
    ov._drag_dragging = bool(dragging)
    ov._drag_canvas = None
    ov.log = lambda _msg: None
    return ov


def arm_mark(pulse, *_):
    width, height, scale, now = 240, 80, 1.0, 0.31
    up = FakeCanvas(width, height)
    _paint_overlay(False, False)._paint_drag_affordance(
        up, width, height, scale, now, pulse=pulse)
    off_changed = up.changed()

    on = FakeCanvas(width, height)
    rect = _paint_overlay(True, False)._paint_drag_affordance(
        on, width, height, scale, now, pulse=pulse)
    band = on.changed(band=BAND)
    inner = on.interior(BAND)
    alphas = on.alphas()

    drag = FakeCanvas(width, height)
    _paint_overlay(True, True)._paint_drag_affordance(
        drag, width, height, scale, now, pulse=pulse)
    solid = drag.alphas() == {255}

    ok = (off_changed == 0 and rect is not None and band > 0 and inner == 0
          and alphas and min(alphas) >= caption_drag.PULSE_MIN_ALPHA
          and solid)
    return ("P9 a marca (pixels na banda da borda so' com Ctrl; solida a arrastar)",
            ok)


def _tick_probe(content, armed=False, dragging=False):
    ov = object.__new__(caption_overlay.NativeCaptionOverlay)
    ov.lock = threading.RLock()
    ov._tick_gen = 0
    ov.hwnd = None
    ov.visible = True
    ov._drag_armed = armed
    ov._drag_dragging = dragging
    ov._drag_pos = None
    ov._drag_offset = (0, 0)
    ov._drag = caption_drag.DragState()
    ov._drag_canvas = None
    ov._tick_content = content
    ov.log = lambda _msg: None
    ov.scale = 1.0
    ov.paints = []
    ov._poll_drag = lambda: False
    ov._update = lambda: ov.paints.append("paint")
    ov._arm_tick = lambda: ov.paints.append("arm")
    return ov


def arm_tick(plan, *_):
    idle = _tick_probe(False)
    idle._tick(0)
    content = _tick_probe(True)
    content._tick(0)
    armed = _tick_probe(False, armed=True)
    armed._tick(0)
    return ("P10 poll ocioso nao repinta; conteudo e Ctrl repintam", (
        idle.paints == ["arm"] and content.paints == ["paint"]
        and armed.paints == ["paint"]))


def _bitmap_alpha_band(bmp, width, height, band=BAND):
    """Conta alfa > 0 na banda da borda e no interior de um bitmap GDI+ real."""
    import ctypes
    from System.Drawing import Rectangle
    from System.Drawing.Imaging import ImageLockMode, PixelFormat
    data = bmp.LockBits(Rectangle(0, 0, width, height),
                        ImageLockMode.ReadOnly, PixelFormat.Format32bppPArgb)
    try:
        stride = abs(int(data.Stride))
        raw = ctypes.string_at(int(data.Scan0.ToInt64()), stride * height)
        bottom_up = int(data.Stride) < 0
        edge = inner = 0
        for y in range(height):
            row = (height - 1 - y) * stride if bottom_up else y * stride
            for x in range(width):
                if raw[row + x * 4 + 3] <= 0:
                    continue
                if min(x, y, width - 1 - x, height - 1 - y) > band:
                    inner += 1
                else:
                    edge += 1
        return edge, inner
    finally:
        bmp.UnlockBits(data)


def arm_gdi(pulse, *_):
    """A MESMA pintura contra um bitmap GDI+ real (fora do ecra).

    O canvas falso da P9 prova a GEOMETRIA; esta arm prova que o adaptador que
    embarca (`_DragCanvas`: Pen GDI+, `DrawRectangle`) escreve pixeis mesmo --
    e que com o Ctrl levantado nao escreve nenhum.
    """
    try:
        import clr
        clr.AddReference("System.Drawing")
        from System.Drawing import Bitmap
    except Exception as exc:  # noqa: BLE001 -- sem GDI+ nao ha' legenda nenhuma
        return ("P11 GDI+ real pinta a banda da borda (sem GDI+: %r)" % (exc,),
                False)
    width, height = 240, 80
    bmp = Bitmap(width, height)
    try:
        off = _paint_overlay(False, False)
        off.scale = 1.0
        off._paint_drag_outline(bmp, width, height)
        off_edge, off_inner = _bitmap_alpha_band(bmp, width, height)

        on = _paint_overlay(True, False)
        on.scale = 1.0
        on._paint_drag_outline(bmp, width, height)
        edge, inner = _bitmap_alpha_band(bmp, width, height)
        return ("P11 GDI+ real pinta a banda da borda", (
            off_edge == 0 and off_inner == 0 and edge > 0 and inner == 0))
    finally:
        bmp.Dispose()


# ── os mutantes (so' no --neg-arm) ─────────────────────────────────────────
def _mutant_plan(real):
    """A decisao real COPIADA e mutada: sem limite e a gravar sempre."""

    def plan(ctrl_down, lbutton_down, cursor, rect, work, offset=(0, 0),
             state=None):
        d = real(ctrl_down, lbutton_down, cursor, rect, work, offset=offset,
                 state=state)
        pos = d.pos
        off = d.offset
        if d.dragging:
            pos = (int(cursor[0]) - int(d.state.grab[0]),
                   int(cursor[1]) - int(d.state.grab[1]))
            off = (pos[0] - d.state.origin[0], pos[1] - d.state.origin[1])
        return caption_drag.DragDecision(
            d.armed, d.dragging, pos, off, d.moved, True, True, d.state)

    return plan


def _mutant_pulse(_now, _dragging, period=None):
    return 0


# ── o custo da marca (fora do ecra; `--cost`) ──────────────────────────────
def _cost(frames=1000):
    try:
        import clr
        clr.AddReference("System.Drawing")
        from System.Drawing import Bitmap
    except Exception as exc:  # noqa: BLE001 -- sem GDI+ o custo e' UNKNOWN
        print("COST UNKNOWN — %r" % (exc,))
        return None
    width, height = 600, 120
    bmp = Bitmap(width, height)
    ov = _paint_overlay(True, False)
    ov.scale = 1.0
    for _ in range(20):                      # aquecimento (JIT + Pen)
        ov._paint_drag_outline(bmp, width, height)
    # CPU DO PROCESSO, nao relogio de parede: a maquina esta' repartilhada por
    # outras lanes e o `perf_counter` media a contencao, nao o custo. O numero
    # que interessa e' quanto trabalho a marca ACRESCENTA.
    t0 = time.process_time()
    for _ in range(frames):
        ov._paint_drag_outline(bmp, width, height)
    down = (time.process_time() - t0) / frames
    ov._drag_armed = False
    t0 = time.process_time()
    for _ in range(frames):
        ov._paint_drag_outline(bmp, width, height)
    up = (time.process_time() - t0) / frames
    bmp.Dispose()
    print("COST frames=%d size=%dx%d ctrl_up_us=%.1f ctrl_down_us=%.1f "
          "delta_us=%.1f (bitmap GDI+ fora do ecra; nao e' o ecra do dono)"
          % (frames, width, height, up * 1e6, down * 1e6,
             (down - up) * 1e6))
    # O POLL: as tres leituras do Win32 + a decisao pura, no tick ocioso (Ctrl
    # em cima). E' o preco de a legenda parada poder ver o Ctrl descer.
    plan = caption_drag.drag_plan
    state = caption_drag.DragState()
    cursor = caption_overlay._cursor_px() or (0, 0)
    t0 = time.process_time()
    for _ in range(frames):
        decision = plan(caption_overlay._ctrl_held(),
                        caption_overlay._lbutton_held(),
                        cursor, RECT, WORK, state=state)
        state = decision.state
    poll = (time.process_time() - t0) / frames
    print("POLL frames=%d ctrl_up_us=%.1f (3 chamadas Win32 + drag_plan; "
          "sem repintura)" % (frames, poll * 1e6))
    return (up, down)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    neg = "--neg-arm" in args
    if "--cost" in args:
        _cost()
        if not args or set(args) <= {"--cost"}:
            return 0

    if neg:
        plan = _mutant_plan(caption_drag.drag_plan)
        pulse = _mutant_pulse
        must_go_red = {"P4", "P7", "P9"}
    else:
        plan = caption_drag.drag_plan
        pulse = caption_drag.pulse_alpha
        must_go_red = set()

    checks = [
        arm_arm(plan, pulse),
        arm_drag(plan, pulse),
        arm_release(plan, pulse),
        arm_clamp(plan, pulse),
        arm_click_without_ctrl(plan, pulse),
        arm_ctrl_outside(plan, pulse),
        arm_round_trip(plan, pulse),
        arm_persistence(plan, pulse),
        arm_mark(pulse, pulse),
        arm_tick(plan, pulse),
        arm_gdi(pulse, pulse),
    ]
    for name, ok in checks:
        print("%-62s -> %s" % (name, "PASS" if ok else "FAIL"))
    if neg:
        red = {name.split()[0] for name, ok in checks if not ok}
        caught = must_go_red <= red
        print("NEG-ARM: %s (vermelhas=%d/%d: %s; exigidas=%s)"
              % ("PASS" if caught else "FAIL", len(red), len(checks),
                 ", ".join(sorted(red)) or "-",
                 ", ".join(sorted(must_go_red))))
        return 1 if caught else 0
    ok = all(value for _name, value in checks)
    print("VERDICT: %s (%d/%d)" % ("PASS" if ok else "FAIL",
                                   sum(1 for _n, v in checks if v),
                                   len(checks)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
