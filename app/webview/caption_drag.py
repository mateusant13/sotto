"""O DECISOR DO ARRASTO DA LEGENDA -- puro, zero Win32 (2026-11-08).

Ordem do dono, verbatim: *"segurar control, permite eu arrastar a legenda pra
onde eu quero. e o control segurado tambem vai ter um indicativo bem minimo de
que da pra arrastar a legenda"*.

PORQUE ESTE MODULO EXISTE SEPARADO DA JANELA. A janela (`caption_overlay`) e'
Win32+GDI+ e nao se pode exercitar sem um ecra. A DECISAO -- "com Ctrl e o
botao esquerdo carregado dentro do rect, isto e' um arrasto; o destino e' o
cursor menos a pega; o resultado fica dentro da area de trabalho" -- e' uma
funcao de seis numeros e e' aqui que ela vive, para o oraculo poder provar cada
braco (armar, arrastar, largar, o limite do ecra, o clique sem Ctrl, o Ctrl
fora do rect, o arrasto que acaba onde comecou) sem tocar em `user32`.

O QUE O CHAMADOR FAZ: le' o estado com `GetAsyncKeyState`/`GetCursorPos` no
tick que ja' existe, chama `drag_plan`, e aplica `decision.pos` com
`SetWindowPos`. Nenhum hook, nenhum fio novo, nenhum timer por frame -- o
`caption_overlay` ja' tem UM fio de relogio e e' ele que poll.

A PERSISTENCIA. O deslocamento que fica depois de largar e' um par de inteiros
relativo a' posicao base da legenda (centrada em baixo). Ele mora em
`_main/caption-drag-offset.json`, ao lado dos outros estados mutaveis do repo
(`hotkey-settings.json`, `panel-state.json`) -- um segundo sitio seria uma
segunda verdade. Um ficheiro ausente, vazio ou partido vale `(0, 0)`: a legenda
nunca pode deixar de aparecer por causa de um JSON.
"""

from __future__ import annotations

import json
import os

#: A raiz do repo: `app/webview/caption_drag.py` -> tres pais.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#: O ficheiro do deslocamento persistido.
STATE_PATH = os.path.join(_REPO, '_main', 'caption-drag-offset.json')

# ── OS TEMPOS DO TICK, num so' sitio ─────────────────────────────────────────
#: O compasso da pulsacao da marca "da' pra arrastar". Um ciclo completo em
#: 1,2 s: lento o bastante para se ler como convite, e nao como alarme.
PULSE_PERIOD_S = 1.2
#: O alfa MINIMO da pulsacao (0..255). Nunca chega a zero: a marca existe
#: enquanto o Ctrl estiver carregado, ela so' respira.
PULSE_MIN_ALPHA = 96
#: Enquanto se ARRASTA: o contorno fica solido (alfa 255) e o tick corre a 60 Hz
#: para a janela seguir o cursor sem arrastar atras.
DRAG_FRAME_S = 1.0 / 60.0
#: Enquanto se mostra a marca: 30 Hz chegam para a pulsacao e custam metade.
PULSE_FRAME_S = 1.0 / 30.0
#: O ritmo do POLL quando nao ha' nada a animar. Sem isto a legenda parada nao
#: tem tick nenhum e uma pressao de Ctrl nunca seria vista; 10 leituras por
#: segundo de tres chamadas baratas e' o preco de ver o gesto com a legenda
#: parada. Nao ha' repintura nenhuma neste compasso (ver `caption_overlay._tick`).
POLL_S = 0.1

#: A cor da marca -- o `--accent-from` do painel (`#7dd3fc`). A mesma cor que a
#: app ja' usa, nao uma nova.
ACCENT_RGB = (125, 211, 252)


class DragState:
    """A MEMORIA DO GESTO entre dois ticks: o que o proximo passo precisa saber.

    Imutavel por convencao: `drag_plan` devolve sempre uma instancia nova, para
    que um braco do oraculo nao veja o estado mudado por outro.
    """

    __slots__ = ('armed', 'dragging', 'lbutton', 'grab', 'origin',
                 'start_offset', 'offset')

    def __init__(self, offset=(0, 0)):
        self.armed = False
        self.dragging = False
        #: O botao esquerdo no tick ANTERIOR. E' o que distingue "pressao nova"
        #: de "botao que ja' estava carregado quando o Ctrl desceu".
        self.lbutton = False
        #: cursor - canto do rect no instante da pressao: o ponto agarrado.
        self.grab = (0, 0)
        #: A posicao BASE (rect - offset) no instante da pressao. E' o que
        #: absorve o texto a mudar de largura a meio do arrasto: a janela segue
        #: `pos`, e o deslocamento e' recalculado contra esta base.
        self.origin = (0, 0)
        #: O offset no instante da pressao -- o "onde comecou" do arrasto.
        self.start_offset = (int(offset[0]), int(offset[1]))
        #: O deslocamento CORRENTE, relativo a' posicao base.
        self.offset = (int(offset[0]), int(offset[1]))

    def copy(self):
        out = DragState(self.offset)
        out.armed = self.armed
        out.dragging = self.dragging
        out.lbutton = self.lbutton
        out.grab = self.grab
        out.origin = self.origin
        out.start_offset = self.start_offset
        return out


class DragDecision:
    """O que fazer neste tick, e o estado que o proximo tick vai receber."""

    __slots__ = ('armed', 'dragging', 'pos', 'offset', 'moved', 'persist',
                 'changed', 'state')

    def __init__(self, armed, dragging, pos, offset, moved, persist, changed,
                 state):
        #: Ctrl carregado: a marca "da' pra arrastar" esta' acesa.
        self.armed = armed
        #: Um arrasto esta' a decorrer AGORA.
        self.dragging = dragging
        #: O canto superior esquerdo que a janela deve ocupar (ja' dentro da
        #: area de trabalho). Em repouso e' o rect actual -- `changed` diz se
        #: e' preciso mexer.
        self.pos = pos
        #: O novo deslocamento persistivel, relativo a' posicao base.
        self.offset = offset
        #: A janela mexeu-se desde que a pressao comecou.
        self.moved = moved
        #: O arrasto ACABOU de terminar depois de mover: gravar `offset`.
        self.persist = persist
        #: Algo visual mudou (armado/arrastar/posicao): este tick pinta.
        self.changed = changed
        #: O estado a entregar ao proximo `drag_plan`.
        self.state = state


def _pair(value):
    try:
        return (int(value[0]), int(value[1]))
    except (TypeError, ValueError, IndexError, KeyError):
        return (0, 0)


def _rectangle(rect):
    """(x, y, w, h) a partir de uma tupla ou de um dict de rect."""
    if isinstance(rect, dict):
        x = int(rect.get('x', rect.get('left', 0)) or 0)
        y = int(rect.get('y', rect.get('top', 0)) or 0)
        w = int(rect.get('width', 0) or 0)
        h = int(rect.get('height', 0) or 0)
        return (x, y, max(0, w), max(0, h))
    try:
        return (int(rect[0]), int(rect[1]), max(0, int(rect[2])),
                max(0, int(rect[3])))
    except (TypeError, ValueError, IndexError, KeyError):
        return (0, 0, 0, 0)


def clamp_pos(pos, size, work):
    """Prende um canto superior esquerdo DENTRO da area de trabalho.

    A janela nunca pode sair do ecra por arrasto: o dono larga o rato e a
    legenda tem de continuar a existir. Uma janela MAIOR do que a area de
    trabalho encosta no canto superior esquerdo dela (o texto comeca onde se
    le', nao a meio do vazio).
    """
    x, y = _pair(pos)
    w, h = _pair(size)
    wx = int((work or {}).get('x', 0) or 0)
    wy = int((work or {}).get('y', 0) or 0)
    ww = int((work or {}).get('width', 0) or 0)
    wh = int((work or {}).get('height', 0) or 0)
    if ww > 0:
        hi = wx + ww - w
        x = wx if hi < wx else min(max(x, wx), hi)
    if wh > 0:
        hi = wy + wh - h
        y = wy if hi < wy else min(max(y, wy), hi)
    return (x, y)


def pulse_alpha(now, dragging, period=PULSE_PERIOD_S):
    """O alfa da marca neste instante: 0..255, e SOLIDO enquanto se arrasta.

    Uma onda triangular, nao um seno: `math.sin` seria uma chamada por frame e
    um numero que ninguem ve' a diferenca. Triangular e' aritmetica pura e da'
    a mesma respiracao.
    """
    if dragging:
        return 255
    try:
        period = float(period)
        t = float(now)
    except (TypeError, ValueError):
        return 255
    if period <= 0.0:
        return 255
    phase = (t % period) / period
    tri = 1.0 - abs(2.0 * phase - 1.0)      # 0 -> 1 -> 0
    return int(round(PULSE_MIN_ALPHA + (255 - PULSE_MIN_ALPHA) * tri))


def drag_plan(ctrl_down, lbutton_down, cursor, rect, work, offset=(0, 0),
              state=None):
    """A DECISAO do arrasto neste tick -- pura, sem efeitos e sem Win32.

    Entradas: se o Ctrl esta' carregado, se o botao esquerdo esta' carregado, o
    cursor em coordenadas de ecra, o rect actual da janela `(x, y, w, h)`, a
    area de trabalho, e o deslocamento corrente. `state` e' a memoria do tick
    anterior (`DragState`); sem ela a funcao responde de forma instantanea (um
    arrasto nao pode comecar e continuar no mesmo passo, porque nao ha'
    "anterior").

    Regras, e o porque' de cada uma:

      * ARRASTAR EXIGE TRES COISAS: Ctrl carregado, botao esquerdo carregado, e
        o cursor DENTRO do rect. Sem Ctrl o clique passa ao video, como sempre
        passou -- o overlay e' `WS_EX_TRANSPARENT` e nao rouba clique nenhum.
      * A PRESSAO TEM DE SER NOVA (`not state.lbutton`). Com o botao ja'
        carregado, largar o Ctrl por cima dele nao pode agarra a legenda: o
        dono esta' a fazer outra coisa.
      * O DESTINO E' cursor - pega: a janela move-se exactamente com o rato.
      * O LIMITE E' A AREA DE TRABALHO (`clamp_pos`), em cada tick -- nao so'
        no fim. Assim nem um arrasto para fora durante um segundo tira a
        legenda do ecra.
      * LARGAR GRAVA SO' SE MEXEU (`moved`). Um clique sem arrasto -- ou um
        arrasto que acaba onde comecou -- nao escreve ficheiro nenhum.
    """
    ctrl = bool(ctrl_down)
    lb = bool(lbutton_down)
    cx, cy = _pair(cursor)
    rx, ry, rw, rh = _rectangle(rect)
    if state is not None:
        st = state.copy()
    else:
        st = DragState(offset)
    pos = (rx, ry)
    persist = False
    was_armed = st.armed
    was_dragging = st.dragging
    inside = rx <= cx < rx + rw and ry <= cy < ry + rh
    moved = False

    if st.dragging:
        desired = (cx - st.grab[0], cy - st.grab[1])
        pos = clamp_pos(desired, (rw, rh), work)
        st.offset = (pos[0] - st.origin[0], pos[1] - st.origin[1])
        moved = st.offset != st.start_offset
        if ctrl and lb:
            st.armed = True
        else:
            st.dragging = False
            st.armed = ctrl
            persist = bool(moved)
    elif ctrl and lb and not st.lbutton and inside:
        # PRESSAO NOVA DENTRO DO RECT, COM CTRL: o arrasto comeca aqui.
        st.grab = (cx - rx, cy - ry)
        st.origin = (rx - st.offset[0], ry - st.offset[1])
        st.start_offset = st.offset
        st.dragging = True
        st.armed = True
    else:
        # EM REPOUSO. A marca segue o Ctrl exatamente: aparece quando ele desce
        # (mesmo com o cursor fora do rect) e desaparece quando ele sobe.
        st.armed = ctrl
        if not ctrl:
            st.dragging = False

    st.lbutton = lb
    changed = (st.armed != was_armed
               or st.dragging != was_dragging
               or persist
               or pos != (rx, ry))
    return DragDecision(st.armed, st.dragging, pos, st.offset, moved, persist,
                        changed, st)


def load_offset(path=None):
    """O deslocamento gravado, ou `(0, 0)`. Nunca levanta."""
    target = path or STATE_PATH
    try:
        with open(target, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return (int(data.get('x', 0) or 0), int(data.get('y', 0) or 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return (0, 0)


def save_offset(offset, path=None):
    """Grava o deslocamento. Devolve True quando o ficheiro ficou no sitio.

    Escrita atomica (`tmp` + `os.replace`): uma queda a meio nao deixa um JSON
    partido que a proxima arranque leria como `(0, 0)` sem ninguem saber porquê.
    """
    target = path or STATE_PATH
    x, y = _pair(offset)
    tmp = target + '.tmp'
    try:
        folder = os.path.dirname(target)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump({'x': x, 'y': y}, fh)
        os.replace(tmp, target)
        return True
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
