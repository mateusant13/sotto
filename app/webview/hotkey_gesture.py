"""O GESTO DO ALT+C -- um toque, dois toques, e SEGURAR.

ORDEM DO DONO, 2026-10-30 (supersede o contrato de 2026-10-18, em que UM toque
era a legenda):

    1 tap  -> o painel de BAIXO   (`show_strip`)
    2 taps -> o painel da DIREITA (`show_side`)
    HOLD   -> a legenda AO VIVO liga/desliga

PORQUE E' QUE ISTO PRECISA DE UM SINAL NOVO. `RegisterHotKey` com
`MOD_NOREPEAT` (ligado desde sempre, `sotto_webview.py`) entrega **um**
`WM_HOTKEY` por pressao e **nenhum** evento de libertação -- nao ha `WM_KEYUP`
naquela fila, e `msg.lParam` nunca era lido. Sem o instante da libertação,
"segurar" e' indistinguivel de "tocar": o contrato antigo tentava adivinha-lo
a contar presses dentro de 700 ms, e **medido no log do dono** (2026-10-30,
163 rajadas): 56 de 1 pressao, 34 de 2, e 73 de 3+ — um segundo de Alt+C
segurado caía em "triplo" e mostrava o painel da DIREITA em vez de ligar a
legenda. O contador **nao** e' o gesto.

A leitura certa e' `GetAsyncKeyState(VK_MENU)`: o Alt ainda esta' em baixo
quando o `WM_HOTKEY` chega, e sai quando o dono larga. Quanto tempo ficou
em baixo **e'** a duracao do gesto. Aqui vive so' a decisao, pura, para poder
ser medida sem teclado e sem janela.
"""
from __future__ import annotations

#: Segurado pelo menos isto: o gesto e' o HOLD e nao um toque.
#: E' o valor de FABRICA. O limiar em vigor vem de `hotkey_settings.hold_ms()`,
#: que o dono muda no painel da direita (ordem de 2026-10-30); esta constante
#: fica a ser o que se usa quando ninguem escolheu nada, ou quando o ficheiro
#: da escolha esta' ilegivel. A regra continua pura: quem a chama passa o numero.
#:
#: PORQUE E' QUE ERA 500, PASSOU A 900, E PASSOU A 200 (medido, na mao dele).
#: 500 -> 900 em 2026-10-30, quando ele reclamou, verbatim: *"EU TO APERTANDO
#: ALT C E TA LIGANDO E DESLIGANDO A LEGENDA PORRA"*. As 21 pressoes lidas pelo
#: `HotkeyThread` nessa sessao:
#:
#:     93 110 187 204 438 468 | 531 578 641 ... 1187 1250 1344 2000 3047
#:
#: O vazio entre 641 e 1187 e' onde 900 foi posto. **200 e' a ORDEM DE HOJE**
#: (2026-10-30, verbatim: *"a porra do alt c, bota 200ms"*), e ela entra com o
#: risco escrito em vez de escondido: **204, 438 e 468 ms da tabela acima caem
#: agora em HOLD** -- um toque que dure mais de um quinto de segundo comuta a
#: legenda em vez de mostrar o painel. O numero nao foi re-medido; foi ESCOLHIDO
#: por ele, e por isso a lista do painel (`hotkey_settings.HOTKEY_HOLD_MS_CHOICES`)
#: continua a oferecer 300/400/500/700/900/1200 para ele voltar atras num clique.
HOTKEY_HOLD_MS = 200.0

#: Dois toques separados por <= isto sao UM gesto de dois toques.
HOTKEY_TAP_WINDOW_MS = 400.0

#: Tecto da medicao: uma tecla presa (ou um `GetAsyncKeyState` que nunca baixa)
#: nao pode bloquear o thread da hotkey para sempre.
HOLD_CEILING_MS = 5000.0


def is_hold(held_ms, hold_ms=HOTKEY_HOLD_MS):
    """A tecla ficou em baixo o suficiente para o gesto ser o HOLD?

    `held_ms` desconhecido (`None`) NAO e' um HOLD: nao se inventa um gesto a
    partir de uma medicao que nao existe. Um toque e' o que sempre funcionou.
    """
    if held_ms is None:
        return False
    try:
        return float(held_ms) >= float(hold_ms)
    except (TypeError, ValueError):
        return False


def resolve_taps(taps):
    """Quantos toques -> que painel: `'side'` a partir de dois, `'strip'` num.

    TRES OU MAIS cai no `'side'` e NAO num quarto estado: o dono deu tres
    significados e o terceiro e' o painel da direita; um quarto estado seria
    inventado por mim. Um toque e' sempre o painel de baixo.
    """
    try:
        n = int(taps)
    except (TypeError, ValueError):
        n = 1
    return 'side' if n >= 2 else 'strip'


def surface_for(taps):
    """O nome de superficie que `show_strip`/`show_side` usam (`'strip'`/`'panel'`)."""
    return 'panel' if resolve_taps(taps) == 'side' else 'strip'

#: O CICLO DO DONO (2026-10-30), verbatim: *"alt segurado e c multiplas vezes
#: devem continuar mostrando os paineis e alternando entra mostrar nada, mostrar
#: o primeiro, mostrar o segundo"*. Cada pressao AVANCA um estado, para sempre,
#: com a tecla em baixo ou nao -- e' o que a frase dele pede: `nada -> baixo ->
#: direita -> nada`. O contrato anterior (1 toque = baixo, 2 = direita, repetir
#: o mesmo painel FECHA) produzia `baixo -> direita -> nada -> direita -> nada`:
#: o quarto toque nunca voltava ao primeiro painel, e era isso que o dono
#: chamava de "nao fez".
CYCLE = (None, 'strip', 'panel')


def next_surface(visible, surface):
    """O proximo estado do ciclo, a partir do que a JANELA veste agora.

    `visible`/`surface` sao o que o shell MEDIU (`IsWindowVisible` +
    `surface_applied`), nunca uma intencao: um `show` que falhou deixou o painel
    escondido, e o ciclo tem de continuar de onde o dono esta' a ver.

    Devolve `None` (esconder), `'strip'` (painel de baixo) ou `'panel'`
    (painel da direita).
    """
    if not visible:
        return 'strip'
    return 'panel' if str(surface or '') == 'strip' else None
