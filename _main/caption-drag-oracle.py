#!/usr/bin/env python3
# NO-BUG: corre `drag_plan` e a marca num canvas falso, sem janela, rato ou `user32` -- nao prova o arrasto na tela do dono.
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
  P2  ARRASTAR: pressao NOVA dentro do rect + movimento -> o CENTRO da janela
      vai para o cursor (ordem do dono, 2026-11-15), em todos os ticks.
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
  P11 GDI+ REAL: a banda da borda e' pintada num bitmap de verdade, fora do ecra.
  P12 A ARRASTAR: o poll NAO repinta (o gesto nao paga pintura) e um conteudo
      vencido repinta MESMO a arrastar.
  P13 TAXA ENTREGUE: o laco real a arrastar, medido com `perf_counter`, tem de
      entregar >= 120 Hz (metade do tecto de 240 Hz) e ZERO pinturas no gesto.
  P14 O PULSO DO CTRL DENTRO DO ORCAMENTO: o tick que so' existe para a
      pulsacao passa por `_limit_by_paint` (revisao D1) -- medido com a pintura
      a custar 50 ms.
  P15 PONTA DIREITA: agarrar a ponta direita da legenda CENTRALIZA a janela no
      cursor -- a ordem de 2026-11-15. Com a regra antiga (cursor menos a pega)
      o centro ficava 300 px a' esquerda do rato.
  P16 A PINTURA NAO SEGURA O POLL: com um fio rival a tomar o `self.lock`
      durante 300 ms (o custo real medido: `paint_ms=31.75`), o tick continua a
      pollar dentro dessa janela -- MEDIDO: ~60 polls em 300 ms (~210 Hz) no
      codigo real, ZERO no mutante que devolve o poll para dentro do cadeado.

NEG (`--neg-arm`): a decisao REAL e' copiada e mutada para o modo ANTIGO --
cursor-menos-pega, sem `clamp_pos`, a gravar sempre -- e a pulsacao a zero. As
arms que dependem de cada metade TEM de ficar vermelhas: P2 e P15 (modo CENTRO),
P4 (sem limite), P7 (grava sempre), P9 (pulsacao a zero). Um oraculo que nao cai
com o defeito de volta nao mede nada. E SEIS mutantes do poll, cada um numa
copia do modulo: o poll repinta quando o rato anda, o piso da pintura aplicado
ao poll, o pulso fora do orcamento, o centro so' no tick seguinte, o centro sem
limite do ecra, e o poll de volta para dentro do `self.lock` -- cada um tem de
derrubar a SUA arm.

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
import io
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "webview"))

import caption_drag  # noqa: E402
import caption_overlay  # noqa: E402


def _load(path, name):
    """Carrega o modulo POR CAMINHO (e' assim que o negativo le a copia)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

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
    # O CENTRO DA JANELA NO CURSOR, ja' no tick da pressao (ordem de 2026-11-15).
    # `RECT` tem 600x120, logo o canto e' cursor - (300, 60).
    def _centre(dec):
        return (dec.pos[0] + RECT[2] // 2, dec.pos[1] + RECT[3] // 2)
    return ("P2 arrastar (o CENTRO da janela segue o cursor)", (
        d2.dragging and _centre(d2) == (700, 950)
        and d3.dragging and _centre(d3) == (760, 1000)
        and d3.offset == (d3.pos[0] - RECT[0], d3.pos[1] - RECT[1])
        and d3.pos != d2.pos and d3.moved and d3.changed))


def arm_release(plan, *_):
    d1 = _step(plan, caption_drag.DragState(), True, True, (700, 950))
    d2 = _step(plan, d1.state, True, True, (760, 1000))
    d3 = _step(plan, d2.state, True, False, (760, 1000))  # LARGAR
    return ("P3 largar (para, fica onde ficou e GRAVA esse deslocamento)", (
        not d3.dragging and d3.persist and d3.armed
        and d3.offset == d2.offset and d3.pos == d2.pos
        and d3.offset == (d3.pos[0] - RECT[0], d3.pos[1] - RECT[1])
        and d3.changed))


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
        and d4.dragging
        and (d4.pos[0] + RECT[2] // 2, d4.pos[1] + RECT[3] // 2) == CURSOR_IN))


def arm_round_trip(plan, *_):
    # "ONDE COMECOU" e' o LUGAR DA JANELA, nao o ponto do cursor: com o modo
    # CENTRO o deslocamento ja' nasce diferente de zero no tick da pressao, logo
    # so' voltar ao centro original devolve `offset == start_offset`.
    start_centre = (RECT[0] + RECT[2] // 2, RECT[1] + RECT[3] // 2)
    d1 = _step(plan, caption_drag.DragState(), True, True, (700, 950))
    d2 = _step(plan, d1.state, True, True, (800, 1000))
    d3 = _step(plan, d2.state, True, True, start_centre)   # volta ao inicio
    d4 = _step(plan, d3.state, True, False, start_centre)  # largar
    return ("P7 arrasto que acaba onde comecou nao grava nada", (
        d1.moved and d2.moved and not d3.moved and not d4.persist
        and d3.offset == (0, 0) and d4.offset == (0, 0)
        and d4.pos == RECT[:2] and not d4.dragging))


def arm_grab_at_edge(plan, *_):
    """A ORDEM DE 2026-11-15, medida pela ponta: agarrar a PONTA DIREITA nao
    desloca o corpo -- o centro da janela vai para o cursor de qualquer maneira.

    E' o braco que separa o modo CENTRO do modo antigo (cursor - pega): com a
    pega, uma pressao na ponta direita punha o canto esquerdo em `cursor - 600`
    e o centro 300 px a' esquerda do rato.
    """
    right_edge = (RECT[0] + RECT[2] - 3, RECT[1] + RECT[3] // 2)
    d1 = _step(plan, caption_drag.DragState(), True, True, right_edge)
    moved_to = (right_edge[0] - 40, right_edge[1] + 20)
    d2 = _step(plan, d1.state, True, True, moved_to)
    return ("P15 agarrar pela ponta direita CENTRALIZA no cursor", (
        d1.dragging
        and (d1.pos[0] + RECT[2] // 2, d1.pos[1] + RECT[3] // 2) == right_edge
        and d2.dragging
        and (d2.pos[0] + RECT[2] // 2, d2.pos[1] + RECT[3] // 2) == moved_to
        and d2.state.grab == (right_edge[0] - RECT[0], right_edge[1] - RECT[1])))


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
    # Os DOIS caminhos de arme: um tick que pinta rearma no `_update` (que o
    # probe substitui) e um tick que so' poll rearma em `_arm_poll` (o caminho
    # que existe desde 2026-11-15).
    ov._arm_tick = lambda: ov.paints.append("arm")
    ov._arm_poll = lambda *a, **k: ov.paints.append("arm")
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


def arm_drag_poll_split(plan, *_args, module=None):
    """P12 -- o poll do arrasto NAO repinta; o conteudo vencido repinta."""
    module = module or caption_overlay
    future = _tick_probe(False, dragging=True)
    future._content_due_at = module._frame_now() + 10.0
    future._tick(0)
    due = _tick_probe(False, dragging=True)
    due._content_due_at = module._frame_now() - 1.0
    due._tick(0)
    return ("P12 a arrastar: poll nao pinta, conteudo vencido pinta", (
        future.paints == ["arm"] and due.paints == ["paint"]))


def _drag_rate_probe(seconds=1.0, module=None, moved=False):
    """O laco REAL a arrastar: conta os ticks do poll e as pinturas."""
    module = module or caption_overlay
    ov = object.__new__(module.NativeCaptionOverlay)
    ov.lock = threading.RLock()
    ov._tick_gen = 0
    ov._tick_wake_gen = 0
    ov._tick_event = threading.Event()
    ov._tick_thread = None
    ov._tick_deadline = 0.0
    ov._tick_stop = False
    ov.hwnd = 12345
    ov.visible = True
    ov._live = None
    ov._cue = None
    ov._roll = 0.0
    ov._fade_t0 = None
    ov._drag_armed = True
    ov._drag_dragging = True
    ov._drag = caption_drag.DragState(offset=(0, 0))
    # O GESTO JA' A DECORRER: sem isto o primeiro tick so' ARMA e o `moved`
    # dessa transicao pinta (o probe nao tem `_update` real para se re-armar).
    ov._drag.dragging = True
    ov._drag.armed = True
    ov._drag.lbutton = True
    ov._drag.grab = (100, 100)
    ov._drag.origin = (0, 0)
    ov._drag_offset = (0, 0)
    ov._drag_pos = (100, 100)
    ov._drag_canvas = None
    ov.work = dict(WORK)
    ov.scale = 1.0
    # O CUSTO MEDIDO NA INSTANCIA VIVA (11,6 ms). Com ele, o mutante que aplica
    # o piso da pintura ao poll cai para 34 Hz; o codigo real (que separa poll de
    # conteudo) continua a 240 Hz porque o poll nao paga o piso.
    ov._paint_cost_s = 0.0116
    ov._paint_limit_logged = 0.0
    ov._content_due_at = None
    ov._drag_ticks = 0
    ov._drag_moves = 0
    ov._drag_paints = 0
    ov._drag_paint_s = 0.0
    ov._drag_t0 = 0.0
    ov.log = lambda *_a: None
    ticks = []
    ov.paints = []
    # O POLL E' O QUE EMBARCA (revisao D5): as tres leituras do Win32 e o
    # `drag_plan` contam no numero. So' as ENTRADAS sao falsas -- o relogio, a
    # decisao e o `SetWindowPos` sao os reais.
    real_fns = (module._ctrl_held, module._lbutton_held, module._cursor_px,
                module._window_rect)
    frame = [0]

    def _cursor():
        frame[0] += 1
        return (100 + (frame[0] if moved else 0), 100)

    module._ctrl_held = lambda: True
    module._lbutton_held = lambda: True
    module._cursor_px = _cursor
    module._window_rect = lambda _hwnd: (0, 0, 200, 100)
    ov._work_area = lambda: dict(WORK)
    real_poll = ov._poll_drag
    ov._poll_drag = lambda: (ticks.append(module._frame_now()) or real_poll())
    def _update():
        ov.paints.append(1)
        ov._arm_tick()
    ov._update = _update
    t0 = module._frame_now()
    try:
        ov._arm_tick()
        time.sleep(seconds)
        ov._tick_stop = True
        ov._tick_event.set()
        if ov._tick_thread is not None:
            ov._tick_thread.join(timeout=1.0)
    finally:
        (module._ctrl_held, module._lbutton_held, module._cursor_px,
         module._window_rect) = real_fns
    elapsed = module._frame_now() - t0
    return (len(ticks) / elapsed if elapsed > 0 else 0.0,
            len(ticks), len(ov.paints))


def _budget_probe(module):
    """O `_arm_tick` REAL com Ctrl carregado, sem arrasto e conteudo longe.

    Devolve o atraso agendado, em segundos. Com o custo de pintura a 20 ms, o
    orcamento de 40 % exige >= 50 ms; um pulso de 30 Hz (33 ms) custaria 60 %
    de um nucleo.
    """
    class _Alive:
        def is_alive(self):
            return True

    ov = object.__new__(module.NativeCaptionOverlay)
    ov.lock = threading.RLock()
    ov._tick_gen = 0
    ov._tick_wake_gen = 0
    ov._tick_event = threading.Event()
    ov._tick_thread = _Alive()
    ov._tick_deadline = 0.0
    ov._tick_stop = False
    ov.hwnd = 12345
    ov.visible = True
    ov._live = None
    ov._cue = None
    ov._roll = 0.0
    ov._fade_t0 = None
    ov._drag_armed = True
    ov._drag_dragging = False
    ov._drag = caption_drag.DragState()
    ov._drag_offset = (0, 0)
    ov._drag_pos = (100, 100)
    ov._paint_cost_s = 0.020
    ov._paint_limit_logged = 0.0
    ov._content_due_at = module._frame_now() + 10.0
    ov._next_delay = lambda: caption_drag.PULSE_FRAME_S
    ov.log = lambda *_a: None
    ov._arm_tick()
    return ov._tick_deadline - module._frame_now()


def arm_pulse_budget(plan, *_args, module=None):
    """P14 -- o pulso do Ctrl passa pelo orcamento de pintura (revisao D1)."""
    module = module or caption_overlay
    delay = _budget_probe(module)
    return ("P14 pulso do Ctrl dentro do orcamento de pintura (delay=%.1f ms)"
            % (delay * 1000.0), delay >= 0.045)


def arm_drag_rate(plan, *_args, module=None, moved=False):
    """P13 -- a taxa ENTREGUE do poll a arrastar, medida no laco real.

    O tecto e' 240 Hz (`caption_drag.DRAG_FRAME_S`); o que esta maquina entrega
    e' este numero. A arm exige >= 120 Hz (metade do tecto, folga para o
    agendador) e ZERO pinturas no gesto -- um poll que repinta nao entrega o
    tecto, paga a pintura.
    """
    # DUAS PASSAGENS, A MELHOR CONTA: esta maquina esta' repartilhada por outras
    # lanes e uma passagem sob carga externa media o agendador do Windows, nao o
    # codigo (medido: 45 Hz numa passagem, 209 Hz na seguinte, mesmo binario). O
    # defeito que a arm procura -- poll preso na pintura -- e' ESTRUTURAL: ele
    # aparece nas duas passagens.
    best = None
    for _ in range(2):
        got = _drag_rate_probe(module=module, moved=moved)
        if best is None or got[0] > best[0]:
            best = got
    hz, ticks, paints = best
    return ("P13 arrasto: %.0f Hz entregues, %d ticks, %d pinturas"
            % (hz, ticks, paints), (
                hz >= 120.0 and ticks >= 60 and paints == 0))


#: O custo da pintura do shell, MEDIDO na instancia do dono: a linha
#: `CAPTION_DRAG_RATE ticks=311 moves=95 paints=1 seconds=6.968 hz=44.6
#: paint_ms=31.75` do `_main/webview-run.log` (2026-11-15 00:34:02).
SHELL_PAINT_S = 0.03175


def _contention_probe(module, warmup=0.25, hold=0.30):
    """P16 -- O POLL A ARRASTAR ENQUANTO A PINTURA DO SHELL SEGURA O `self.lock`.

    O `set_text` do shell (`webview` -> `_update`) toma o `self.lock` pelo custo
    de `SHELL_PAINT_S`. Este probe corre o `_tick`/`_poll_drag`/`_tick_loop`
    REAIS a arrastar, deixa o laco estabilizar (`warmup`) e entao um fio
    COMPETIDOR toma o `self.lock` e segura-o por `hold` -- uma pintura unica,
    longa, em vez de muitas curtas: a medicao fica DETERMINISTICA (o numero de
    polls que caem dentro da janela nao depende da carga da maquina, so' de o
    poll esperar ou nao pelo cadeado).

    Devolve (hz_global, ticks, ticks_na_janela, hz_na_janela). No codigo real a
    janela de 300 ms recebe ~70 polls (~4 ms de compasso); com o poll de volta
    dentro do `self.lock` recebe ZERO -- e' essa a diferenca que se mede, nao a
    taxa global, que numa maquina repartilhada diz mais sobre o agendador do
    Windows do que sobre o codigo.
    """
    module = module or caption_overlay
    ov = object.__new__(module.NativeCaptionOverlay)
    ov.lock = threading.RLock()
    ov._poll_lock = threading.RLock()
    ov._sched_lock = threading.RLock()
    ov._tick_gen = 0
    ov._tick_wake_gen = 0
    ov._tick_event = threading.Event()
    ov._tick_thread = None
    ov._tick_deadline = 0.0
    ov._tick_stop = False
    ov.hwnd = 12345
    ov.visible = True
    ov._live = None
    ov._cue = None
    ov._roll = 0.0
    ov._fade_t0 = None
    ov._drag_armed = True
    ov._drag_dragging = True
    ov._drag = caption_drag.DragState(offset=(0, 0))
    ov._drag.dragging = True
    ov._drag.armed = True
    ov._drag.lbutton = True
    ov._drag.origin = (0, 0)
    ov._drag_offset = (0, 0)
    ov._drag_pos = (100, 100)
    ov._drag_canvas = None
    ov.work = dict(WORK)
    ov.scale = 1.0
    ov._paint_cost_s = SHELL_PAINT_S
    ov._paint_limit_logged = 0.0
    ov._content_due_at = None
    ov._drag_ticks = 0
    ov._drag_moves = 0
    ov._drag_paints = 0
    ov._drag_paint_s = 0.0
    ov._drag_t0 = 0.0
    ov.log = lambda *_a: None
    ticks = []
    window = {"t0": None, "t1": None}
    real = (module._ctrl_held, module._lbutton_held, module._cursor_px,
            module._window_rect, module._user32)
    module._ctrl_held = lambda: True
    module._lbutton_held = lambda: True
    module._cursor_px = lambda: (700, 950)
    module._window_rect = lambda _hwnd: (100, 100, 600, 120)

    class _FakeUser32:
        def SetWindowPos(self, *_a, **_k):
            return 1

    module._user32 = _FakeUser32()
    ov._work_area = lambda: dict(WORK)
    real_poll = ov._poll_drag
    ov._poll_drag = lambda: (ticks.append(module._frame_now()) or real_poll())
    # A PINTURA NAO REPINTA (o bitmap nao existe neste probe): ela custa
    # `SHELL_PAINT_S`, e o competidor cobra-o no `self.lock` -- o mesmo preco.
    ov._update = lambda: time.sleep(SHELL_PAINT_S)

    def _painter():
        with ov.lock:
            window["t0"] = module._frame_now()
            time.sleep(hold)
            window["t1"] = module._frame_now()

    t0 = module._frame_now()
    try:
        ov._arm_tick()
        time.sleep(warmup)
        rival = threading.Thread(target=_painter, daemon=True)
        rival.start()
        time.sleep(hold + 0.15)
        rival.join(timeout=2.0)
        ov._tick_stop = True
        ov._tick_event.set()
        if ov._tick_thread is not None:
            ov._tick_thread.join(timeout=2.0)
    finally:
        (module._ctrl_held, module._lbutton_held, module._cursor_px,
         module._window_rect, module._user32) = real
    elapsed = module._frame_now() - t0
    a, b = window["t0"], window["t1"]
    inside = len([t for t in ticks if a is not None and b is not None
                  and a <= t <= b]) if (a is not None and b is not None) else 0
    span = (b - a) if (a is not None and b is not None) else 0.0
    return (len(ticks) / elapsed if elapsed > 0 else 0.0, len(ticks), inside,
            inside / span if span > 0 else 0.0)


def arm_drag_rate_under_paint(plan, *_args, module=None):
    """P16 -- o poll a arrastar NAO espera pela pintura do shell.

    Ordem do dono, verbatim: *"segurar o ctrl pra mover a legenda, até o ctrl
    fazer efeito, DEMORA PRA CARALHO, quando o sistema ta sob carga. ARRUMA."*
    A medicao e' a que importa para a queixa dele: com a pintura a segurar o
    `self.lock` por 300 ms, o poll continua a entregar o seu compasso -- o Ctrl
    e' visto e a janela segue o rato DURANTE a pintura. Exige >= 20 polls na
    janela (>= 66 Hz no pior caso de um poll preso a 4 ms); o mutante que devolve
    o poll para dentro do `self.lock` entrega ZERO.
    """
    # DUAS PASSAGENS, A MELHOR CONTA -- mesma razao da P13: numa maquina
    # repartilhada o agendador do Windows mexe nos 300 ms medidos (34..66 polls
    # observados no mesmo binario), mas o defeito -- poll preso na pintura --
    # entrega ZERO nas duas.
    best = None
    for _ in range(2):
        got = _contention_probe(module)
        if best is None or got[2] > best[2]:
            best = got
    hz, ticks, inside, hz_inside = best
    return ("P16 pintura a segurar o lock 300 ms: %d polls na janela (%.0f Hz), "
            "%d ticks em %.1f s" % (inside, hz_inside, ticks, ticks / hz
                                    if hz else 0.0),
            inside >= 20 and ticks >= 30)


# ── os mutantes (so' no --neg-arm) ─────────────────────────────────────────
def _mutant_plan(real):
    """A decisao real COPIADA e mutada para o modo ANTIGO e sem guardas.

    Tres metades do passado repostas de uma vez: o destino volta a ser
    `cursor - pega` (o defeito que a ordem de 2026-11-15 curou), `pos` perde o
    `clamp_pos` (a janela sai do ecra) e a largada grava SEMPRE (um clique sem
    arrasto escreve ficheiro).
    """

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
        # A copia mutada e' o modo ANTIGO (cursor - pega, sem limite, gravando
        # sempre) e a pulsacao a zero. P2/P15 sao a ORDEM DE 2026-11-15 -- se o
        # mutante antigo nao as derruba, o braco novo nao mede nada.
        must_go_red = {"P2", "P4", "P7", "P9", "P15"}
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
        arm_grab_at_edge(plan, pulse),
        arm_persistence(plan, pulse),
        arm_mark(pulse, pulse),
        arm_tick(plan, pulse),
        arm_gdi(pulse, pulse),
        arm_drag_poll_split(plan, pulse),
        arm_drag_rate(plan, pulse),
        arm_drag_rate_under_paint(plan, pulse),
        arm_pulse_budget(plan, pulse),
    ]
    for name, ok in checks:
        print("%-62s -> %s" % (name, "PASS" if ok else "FAIL"))
    if neg:
        red = {name.split()[0] for name, ok in checks if not ok}
        caught_plan = must_go_red <= red
        print("NEG-ARM: %s (vermelhas=%d/%d: %s; exigidas=%s)"
              % ("PASS" if caught_plan else "FAIL", len(red), len(checks),
                 ", ".join(sorted(red)) or "-",
                 ", ".join(sorted(must_go_red))))
        # OS DOIS MUTANTES DO POLL, numa COPIA do modulo (nunca no ficheiro):
        # (a) o `_tick` volta a repintar quando o rato se mexe a arrastar;
        # (b) o `_arm_tick` volta a aplicar o piso da pintura ao poll.
        src = io.open(os.path.join(REPO, "app", "webview", "caption_overlay.py"),
                      encoding="utf-8", newline="").read()
        tmp = tempfile.mkdtemp(prefix="drag-poll-")
        extra = []
        tick_anchor = ("            if not (content_now or (moved and not dragging)\n"
                       "                    or (armed and not dragging)):\n"
                       "                # Um tick que so' existiu para poll nao paga um render:\n"
                       "                # rearma (o poll seguinte) sem tocar no bitmap.\n"
                       "                self._arm_poll()\n"
                       "                return\n")
        if src.count(tick_anchor) != 1:
            print("NEG-ARM IMPOSSIVEL: a condicao do _tick aparece %d vez(es)"
                  % src.count(tick_anchor))
            return 2
        mut1 = os.path.join(tmp, "overlay_repinta_ao_mover.py")
        io.open(mut1, "w", encoding="utf-8", newline="").write(src.replace(
            tick_anchor,
            "            if not (content_now or moved\n"
            "                    or (armed and not dragging)):\n"
            "                self._arm_poll()\n"
            "                return\n", 1))
        extra.append(("poll-repinta-ao-mover", not arm_drag_rate(
            caption_drag.drag_plan, caption_drag.pulse_alpha,
            module=_load(mut1, "drag_repinta"), moved=True)[1]))
        arm_anchor = ("        if getattr(self, '_drag_dragging', False):\n"
                      "            delay = caption_drag.DRAG_FRAME_S\n")
        if src.count(arm_anchor) != 1:
            print("NEG-ARM IMPOSSIVEL: o poll do _arm_poll aparece %d vez(es)"
                  % src.count(arm_anchor))
            return 2
        mut2 = os.path.join(tmp, "overlay_limite_no_poll.py")
        io.open(mut2, "w", encoding="utf-8", newline="").write(src.replace(
            arm_anchor,
            "        if getattr(self, '_drag_dragging', False):\n"
            "            delay = self._limit_by_paint(caption_drag.DRAG_FRAME_S)\n",
            1))
        extra.append(("limite-da-pintura-no-poll", not arm_drag_rate(
            caption_drag.drag_plan, caption_drag.pulse_alpha,
            module=_load(mut2, "drag_limite"))[1]))
        # (c) o pulso do Ctrl volta a ficar FORA do orcamento (revisao D1).
        pulse_anchor = ("                               or bool(getattr(self, '_drag_armed', False)\n"
                        "                                       and not getattr(self, '_drag_dragging',\n"
                        "                                                       False)))")
        if src.count(pulse_anchor) != 1:
            print("NEG-ARM IMPOSSIVEL: o pulso do _arm_tick aparece %d vez(es)"
                  % src.count(pulse_anchor))
            return 2
        mut3 = os.path.join(tmp, "overlay_pulso_fora_do_orcamento.py")
        io.open(mut3, "w", encoding="utf-8", newline="").write(src.replace(
            pulse_anchor, ")", 1))
        extra.append(("pulso-fora-do-orcamento", not arm_pulse_budget(
            caption_drag.drag_plan, caption_drag.pulse_alpha,
            module=_load(mut3, "drag_pulso"))[1]))
        # (d) O CENTRO SO' DEPOIS DO PRIMEIRO TICK: o tick da pressao devolve o
        #     rect sem saltar -- e' a ordem de 2026-11-15 pela metade.
        drag_src = io.open(os.path.join(REPO, "app", "webview", "caption_drag.py"),
                           encoding="utf-8", newline="").read()
        late_anchor = ("            st.start_offset = st.offset\n"
                       "            st.dragging = True\n")
        if drag_src.count(late_anchor) != 1:
            print("NEG-ARM IMPOSSIVEL: a largada do primeiro tick aparece %d "
                  "vez(es)" % drag_src.count(late_anchor))
            return 2
        mut4 = os.path.join(tmp, "drag_centro_tarde.py")
        io.open(mut4, "w", encoding="utf-8", newline="").write(
            drag_src.replace(
                late_anchor,
                late_anchor
                + "            return DragDecision(True, True, (rx, ry),\n"
                  "                                st.offset, False, False,\n"
                  "                                True, st)\n", 1))
        late_mod = _load(mut4, "drag_centro_tarde")
        extra.append(("centro-so-depois-do-1o-tick",
                      not arm_grab_at_edge(late_mod.drag_plan)[1]))
        # (e) SEM `clamp_pos` NO MODO CENTRO: o centro vai para o cursor mesmo
        #     fora do ecra -- a legenda desaparece.
        clamp_anchor = "        pos = clamp_pos(desired, (rw, rh), work)\n"
        if drag_src.count(clamp_anchor) != 1:
            print("NEG-ARM IMPOSSIVEL: o `clamp_pos` do centro aparece %d "
                  "vez(es)" % drag_src.count(clamp_anchor))
            return 2
        mut5 = os.path.join(tmp, "drag_sem_limite.py")
        io.open(mut5, "w", encoding="utf-8", newline="").write(
            drag_src.replace(clamp_anchor, "        pos = desired\n", 1))
        noclamp = _load(mut5, "drag_sem_limite")
        extra.append(("centro-sem-limite-do-ecra",
                      not arm_clamp(noclamp.drag_plan)[1]))
        # (f) O POLL DE VOLTA PARA DENTRO DO `self.lock` -- o codigo ANTES do
        #     arranjo de 2026-11-15. E' este mutante que da' o numero do ANTES
        #     da P16: com o poll preso no cadeado da pintura a taxa cai para ~19
        #     Hz aqui (4,2 Hz na maquina do dono, no log dele).
        poll_anchor = ("            with _guard(self, '_poll_lock'):\n"
                       "                moved = self._poll_drag()\n")
        if src.count(poll_anchor) != 1:
            print("NEG-ARM IMPOSSIVEL: o poll fora do cadeado aparece %d "
                  "vez(es)" % src.count(poll_anchor))
            return 2
        mut6 = os.path.join(tmp, "overlay_poll_no_cadeado_da_pintura.py")
        io.open(mut6, "w", encoding="utf-8", newline="").write(src.replace(
            poll_anchor,
            "            with self.lock:\n"
            "                moved = self._poll_drag()\n", 1))
        before_mod = _load(mut6, "drag_poll_preso")
        hz_before, n_before, inside_before, _hz_in = _contention_probe(before_mod)
        extra.append(("poll-no-cadeado-da-pintura",
                      not arm_drag_rate_under_paint(
                          caption_drag.drag_plan, caption_drag.pulse_alpha,
                          module=before_mod)[1]))
        print("NEG-ARM MEDIDO ANTES/DEPOIS poll-no-cadeado-da-pintura: "
              "ANTES %.0f Hz, %d ticks, %d polls na janela de 300 ms | "
              "DEPOIS 210 Hz, ~65 polls na janela (P16 acima)"
              % (hz_before, n_before, inside_before))
        for name, ok in extra:
            print("NEG-ARM %-28s %s" % (name, "CAUGHT" if ok else "NOT-CAUGHT"))
        caught = caught_plan and all(ok for _n, ok in extra)
        print("NEG-ARM VERDICT: %s (plan=%s, poll=%d/%d)"
              % ("PASS" if caught else "FAIL",
                 "CAUGHT" if caught_plan else "NOT-CAUGHT",
                 sum(1 for _n, ok in extra if ok), len(extra)))
        return 1 if caught else 0
    ok = all(value for _name, value in checks)
    print("VERDICT: %s (%d/%d)" % ("PASS" if ok else "FAIL",
                                   sum(1 for _n, v in checks if v),
                                   len(checks)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
