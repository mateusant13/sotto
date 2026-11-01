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
