"""O FADE COM QUE O YOUTUBE ENTREGA UMA LINHA NOVA -- e a razao de ele nao custar nada.

A ORDEM DO DONO (2026-10-30), verbatim:

    *"por que a nossa legenda nao tem a mesma animacao da do youtube? arruma."*

O QUE O YOUTUBE FAZ. Duas coisas, e so' uma delas precisa de codigo aqui:

  * DENTRO DE UMA LINHA as palavras aparecem UMA A UMA. Nao e' animacao: e' o
    instante de cada palavra. Essa metade resolve-se com o relogio de palavra
    (`youtube_reveal.word_clock_count`) e a recomposicao a 60 ms -- ver
    `ExternalCaptionWatcher.RENDER_S`.
  * UMA LINHA NOVA entra com um FADE rapido (~120 ms). Essa metade e' ESTE
    ficheiro.

PORQUE E' QUE ISTO E' UMA FUNCAO PURA. O fade aplica-se ao canal alfa da
janela inteira, um numero por frame, entregue ao `UpdateLayeredWindow` no
`BLENDFUNCTION.SourceConstantAlpha`. Nenhum pixel e' reescrito, nenhuma
biblioteca nova entra: os 4 campos de `BLENDFUNCTION` ja' estavam a ser
preenchidos com 255 fixo. Um blend por pixel em Python custaria ~50 ms por frame
numa janela de 1920x90 -- mais do que o proprio fade dura.

A CURVA. Ease-out quadratico: o primeiro frame ja' mostra ~20 % da linha, e o
resto chega depressa. Um fade linear parece lento no fim; um ease-in parece
partir tarde. 120 ms e' o valor medido na legenda do proprio YouTube a olho
(unico instrumento possivel aqui: a animacao dele nao se le' por API).
"""
from __future__ import annotations

#: A duracao do fade de uma linha nova. Ver a nota da curva, acima.
DURATION_S = 0.12

#: O intervalo entre frames do fade. 60 Hz e' o que a janela ja' desenha.
FRAME_S = 1.0 / 60.0

#: `SourceConstantAlpha` e' um byte: 255 e' "fica como esta'".
FULL = 255


def alpha_at(elapsed, duration=DURATION_S):
    """O alfa da janela `elapsed` segundos depois de a linha nova comecar.

    `elapsed` None (ou antes de zero, se o relogio monotomico for de outro
    processo) devolve `FULL`: sem instante nao se inventa um fade, e uma linha
    que ficasse a 0 seria uma legenda invisivel -- o pior defeito possivel aqui.
    """
    if elapsed is None:
        return FULL
    try:
        t = float(elapsed)
    except (TypeError, ValueError):
        return FULL
    if t <= 0.0:
        return 0
    if t >= duration:
        return FULL
    fraction = t / float(duration)
    eased = 1.0 - (1.0 - fraction) ** 2
    value = int(round(FULL * eased))
    return max(0, min(FULL, value))


def done(alpha):
    """Este frame e' o ultimo do fade? (O timer do fade para aqui.)"""
    return int(alpha) >= FULL


def next_delay(elapsed, duration=DURATION_S):
    """Quanto falta para o proximo frame -- nunca mais que `FRAME_S`."""
    left = float(duration) - max(0.0, float(elapsed or 0.0))
    return max(0.0, min(FRAME_S, left))


#: A DURACAO DO FADE DE SAIDA -- a linha que ROLA PARA FORA da janela.
#:
#: Nao e' escolhida: e' o unico intervalo que reproduz os 16 quadros da captura
#: do player (`_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json`), e o
#: instrumento re-deriva os limites a cada corrida:
#: `_main/sim/measure-youtube-captions.py`, chave `rollup.exit_s_bracket_s` =
#: **0,424 .. 0,552 s**. Dentro do intervalo, 0,45 e' o valor que o modelo usa.
#:
#: A LINHA QUE SAI NAO APAGA E FICA: ela rola para cima, para fora da caixa da
#: janela -- medido, 1 das 16 amostras tem a linha FORA da caixa com `opacity`
#: ainda a 1. O que este numero da' ao desenho e' a outra metade: o tempo durante
#: o qual ela ainda e' pintada antes de o bitmap a largar.
EXIT_S = 0.45


def alpha_out(elapsed, duration=EXIT_S):
    """O alfa da linha que esta' a sair: FULL -> 0 em `duration` segundos.

    A CURVA E' A MESMA DO FADE DE ENTRADA, lida ao contrario: `alpha_at` faz
    `1-(1-x)^2` (sai depressa do zero); aqui o que sai depressa e' o APAGAR, e o
    que resta depois de `x` do tempo e' `(1-x)^2`. As duas curvas tem a mesma
    forma -- ease-out --, e por isso a linha nova e a velha parecem o mesmo
    movimento em sentidos opostos.

    `elapsed` None devolve FULL: sem instante nao se apaga nada. Uma linha que
    ficasse a 0 seria uma legenda invisivel, e este modulo nunca escolhe isso por
    falta de informacao.
    """
    if elapsed is None:
        return FULL
    try:
        t = float(elapsed)
    except (TypeError, ValueError):
        return FULL
    if t <= 0.0:
        return FULL
    if t >= float(duration):
        return 0
    left = 1.0 - (t / float(duration))
    return max(0, min(FULL, int(round(FULL * left * left))))
