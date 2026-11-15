#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""O PAINEL FICA ACIMA DA LEGENDA (dono, 2026-11-14).

VERBATIM: *"os paineis devem ficar ACIMA da legenda. no `z index`. a legenda, agora
mesmo, ta encima do painel, e eu nao consigo enxergar o painel bem"*.

PORQUE ACONTECIA, medido nesta maquina e nao lido em documentacao:

* as duas janelas sao TOPMOST (`caption_overlay.EX_STYLE` tem `WS_EX_TOPMOST`; o
  painel recebe o bit em `set_topmost`), e dentro da MESMA banda o Z-order e' o da
  ultima chamada;
* `caption_overlay.show(True)` corre a CADA linha de legenda e chama
  `SetWindowPos(hwnd, HWND_TOPMOST, ...)` -- que poe o overlay no topo da banda --
  e logo `ShowWindow(hwnd, SW_SHOWNOACTIVATE)`, que num `show` de janela ja'
  visivel tambem a re-ergue. Duas chamadas por linha, ambas a favor da legenda.

A SEMANTICA DO `SetWindowPos` FOI MEDIDA, NAO SUPOSTA (2026-11-14, duas provas
lado a lado, janelas reais criadas fora do ecra virtual e destruidas no fim):

    SetWindowPos(moved=B, insertAfter=A)  ->  A acima de B
    SetWindowPos(moved=A, insertAfter=B)  ->  B acima de A
    SetWindowPos(Y, HWND_TOP)             ->  Y acima de X   (controlo de sanidade)

Ou seja: o que manda no Z e' o `insertAfter`, e o `moved` fica-lhe POR BAIXO. Logo
"o painel acima da legenda" e' UMA chamada -- mover a LEGENDA com
`insertAfter=painel` -- e nao uma afirmacao cega de topmost no painel, que dentro da
banda nao decide nada.

O QUE ESTE MODULO E'. A decisao PURA (`should_raise`) e a caminhada PURA do Z
(`is_above`), mais um aplicador fino (`ZAuthority`) que recebe TODAS as chamadas ao
USER32 por argumento. O portao `_main/z-order-oracle.py` conduz as tres sem abrir
janela visivel.
"""

#: Tecto da caminhada do Z. Uma banda topmost desta maquina ronda as dezenas de
#: janelas; 64 e' folga para a maquina do dono (medida: 722 processos e uma banda
#: topmost de poucas dezenas) e impede que um `GetWindow` em ciclo custe uma
#: varredura infinita por tique.
CHAIN_LIMIT = 64


def should_raise(panel_visible, caption_visible, panel_above_caption):
    """O painel precisa de ser posto acima da legenda?

    So' quando as DUAS estao visiveis e a legenda esta' por cima. Uma janela
    escondida nao entra em decisao nenhuma -- mover o Z de quem ninguem ve e' uma
    chamada ao USER32 sem efeito, e a legenda escondida nao tapa nada.
    """
    if not panel_visible or not caption_visible:
        return False
    return not panel_above_caption


def is_above(target, below, prev_of, limit=CHAIN_LIMIT):
    """`target` esta' ACIMA de `below` no Z-order?

    `prev_of(hwnd)` devolve a janela imediatamente ACIMA de `hwnd`
    (`GetWindow(hwnd, GW_HWNDPREV)`), ou 0 no fim da banda. A caminhada sobe a
    partir de `below`; se encontrar `target`, ele esta' por cima.

    `target` igual a `below` e' FALSO: uma janela nao esta' acima de si propria, e
    dizer que sim faria o aplicador nao agir no dia em que os dois handles fossem
    o mesmo por engano.
    """
    if not target or not below or target == below:
        return False
    cur = below
    for _ in range(max(1, int(limit))):
        cur = prev_of(cur)
        if not cur:
            return False
        if cur == target:
            return True
    return False


class ZAuthority(object):
    """Aplica a ordem. Todas as chamadas ao sistema entram por argumento.

    `panel_of()`      -> hwnd do painel, ou 0
    `caption_of()`    -> hwnd do overlay da legenda, ou 0
    `visible_of(h)`   -> bool
    `prev_of(h)`      -> janela imediatamente acima de `h`, ou 0
    `insert_below`    -> `insert_below(moved, insert_after)`: poe `insert_after`
                         ACIMA de `moved` (a chamada real e' um unico
                         `SetWindowPos(moved, insert_after, 0,0,0,0,
                         SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE)`).
    """

    def __init__(self, panel_of, caption_of, visible_of, prev_of, insert_below,
                 log, limit=CHAIN_LIMIT):
        self._panel_of = panel_of
        self._caption_of = caption_of
        self._visible_of = visible_of
        self._prev_of = prev_of
        self._insert_below = insert_below
        self._log = log
        self.limit = int(limit)
        self.raised = 0
        self.calls = 0

    def _pair(self):
        try:
            panel = int(self._panel_of() or 0)
            caption = int(self._caption_of() or 0)
        except Exception as exc:                      # noqa: BLE001
            self._log('Z_ORDER_READ_FAILED error=%r' % (exc,))
            return 0, 0
        return panel, caption

    def order_ok(self):
        """(ok, panel, caption) -- le o Z real, sem tocar em nada."""
        panel, caption = self._pair()
        if not panel or not caption:
            return True, panel, caption
        try:
            both_visible = bool(self._visible_of(panel)
                                and self._visible_of(caption))
        except Exception as exc:                      # noqa: BLE001
            self._log('Z_ORDER_READ_FAILED error=%r' % (exc,))
            return True, panel, caption
        if not both_visible:
            return True, panel, caption
        above = is_above(panel, caption, self._prev_of, self.limit)
        return (not should_raise(True, True, above)), panel, caption

    def ensure(self, why):
        """Poe o painel acima da legenda se, e so' se, ele estiver por baixo.

        Devolve True quando agiu. Nunca levanta: um USER32 que recusa nao pode
        derrubar o caminho do show nem o tique do vigia.
        """
        ok, panel, caption = self.order_ok()
        if ok or not panel or not caption:
            return False
        return self.raise_panel(caption, panel, why)

    def raise_panel(self, caption, panel, why):
        """UMA chamada: a legenda passa para logo abaixo do painel."""
        try:
            written = self._insert_below(caption, panel)
        except Exception as exc:                      # noqa: BLE001
            self._log('Z_ORDER_RAISE_FAILED why=%s error=%r' % (why, exc))
            return False
        self.calls += 1
        if written:
            self.raised += 1
            self._log('Z_ORDER_RAISED why=%s panel=%d caption=%d raised=%d'
                      % (why, panel, caption, self.raised))
        else:
            self._log('Z_ORDER_RAISE_REFUSED why=%s panel=%d caption=%d'
                      % (why, panel, caption))
        return bool(written)


#: O que o `enter` do applier recebe do shell. Nome unico para o portao citar sem
#: repetir literais: quem le' `z_order.CAPTION_BELOW_PANEL` sabe o que espera.
CAPTION_BELOW_PANEL = ('caption', 'panel')
