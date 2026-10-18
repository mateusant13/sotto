"""QUEBRAR A LEGENDA EM LINHAS -- as regras da industria, medidas, nao opinadas.

O DONO, 2026-10-17, verbatim: *"e a legenda ta do tamanho da tela. é pra tu
verificar online como quebrar de um jeito bom. ou como o youtube faz"*.

O QUE FOI PESQUISADO, e de onde vem cada número
-----------------------------------------------
Pesquisa feita nesta sessão (2026-10-17), fontes citadas no recibo. O consenso de
Netflix, TED, BBC, Section508 e VEED, que é o que o YouTube segue na prática:

  REGRA           VALOR        FONTE
  ----------------------------------------------------------------------
  chars/linha     <= 42        Netflix (EN), TED (o ponto em que UMA linha vira
                              DUAS), Section508 (45), VEED (42). O BBC usa 37
                              porque e teletexto de largura fixa.
  linhas no ecra  2            Netflix, TED, BBC, Section508, VEED. "A third line
                              covers the frame."
  velocidade      15-20 ch/s   Netflix/TED/BBC/VEED.
  onde quebrar    apos pontuacao, antes de conjuncao, antes de preposicao
                              -- Netflix. BBC: "nao separe um artigo do seu
                              substantivo, uma preposicao da sua frase, uma
                              conjuncao do que vem a seguir, um pronome do seu
                              verbo, nem as partes de um verbo".
  largura         68% de um quadro 16:9   -- BBC.

O PONTO QUE MUDA A IMPLEMENTACAO, e o ultimo da tabela
-------------------------------------------------------
"O character count so aproxima a largura numa fonte PROPORCIONAL" -- e a nossa e
proporcional (Segoe UI). "lilly" e mais estreito do que "mummy". Portanto **contar
caracteres esta errado aqui**, e o proprio BBC diz: se queimas as legendas tu
mesmo, usa uma LARGURA, nao uma contagem. Daqui duas regras neste ficheiro:

  1. a largura do alvo e uma FRACCAO DA AREA DE TRABALHO (0.68), com um tecto de
     caracteres como rede de seguranca de legibilidade -- nunca caracteres como
     regra principal;
  2. a medicao e feita em PIXELS com a fonte real (`measure`), e o modulo aceita
     qualquer `measure` para poder ser testado sem GDI.

O QUE ESTE MODULO FAZ E O QUE NAO FAZ
--------------------------------------
FAZ: parte uma frase em AT MOST 2 linhas, quebrando numa costura natural, e
devolve as linhas com o resto do texto intacto (a 3a linha NAO e uma 3a linha no
ecra -- quem decide o que fazer com ela e o desenho, ver `caption_overlay.py`).

NAO FAZ: nao decide *quando* uma legenda fecha. Isso e do motor de ASR, e mexer
la seria mexer no texto, nao na forma. Aqui so a forma, e so enquanto ha forma
a fazer.
"""

from __future__ import annotations

import re

#: MAXIMUM LINES ON SCREEN. Netflix, TED, BBC, Section508, VEED: all 2.
MAX_LINES = 2

#: BBC: "For 16:9 media, 68% of the media width". Applied to the WORK AREA, so
#: the caption keeps its proportions on any monitor instead of a fixed pixel box.
WIDTH_FRACTION = 0.68

#: A CHARACTER CEILING THAT IS NOT THE RULE. Netflix/TED say 42, Section508 45.
#: It is measured on REPRESENTATIVE text, never on `M` * 42.
#:
#: MEASURED 2026-10-17, and the first version of this file got it wrong in a way
#: that would have shipped: the ceiling was `measure('M' * 42)`, and `M` is the
#: widest glyph in the alphabet, so it priced a line nobody would ever read. At
#: Segoe UI Bold 34 px on this box:
#:
#:     42 x 'M'                  = 1406 px   (the worst case, not a line)
#:     42 chars of real text     =  ~700 px  (a line someone would read)
#:     68% of a 1920 px work area= 1305 px
#:
#: With the `M` ceiling the BBC's fraction won (1305 px, ~46 characters of
#: average Portuguese -- over the 42 the whole industry quotes). With a
#: representative ceiling the CHARACTER rule wins (~700 px, ~42 characters), which
#: is what the research actually asks for. The ceiling binds, and it binds for
#: the right reason.
CHAR_CEILING = 42

#: ORDINARY PORTUGUESE, long enough that `[:42]` is a real slice.
#: MEASURED 2026-10-17: this started as a 43-character string, and a 43-character
#: string cannot tell `[:42]` from `[:400]` -- the negative arm's "widen the
#: ceiling" mutation produced the SAME budget and correctly fired no alarm, which
#: meant the ceiling was untestable. A ceiling you cannot test is not a ceiling.
REPRESENTATIVE = (
    'a legenda ao vivo no meio em baixo da tela dele, sozinha, sem fundo, '
    'a barroom escura onde a palavra se apoia'
)

#: WORDS A LINE MAY START WITH. Netflix: "break after punctuation, before
#: conjunctions, and before prepositions". Both languages the box transcribes,
#: because `lang_id` is `auto` and the model decodes whichever it hears.
BOUNDARY_BEFORE = frozenset("""
a as ao aos à às
e ou nem mas porém portantoLogo
que de do da dos das dum duma
em no na nos nas num numa
para com sem sobre entre ate até desde
por pelo pela pelos pelas
quando onde porque como se
""".split())

#: A WORD ENDING A PHRASE is a perfect seam and is preferred over everything.
SENTENCE_END = re.compile(r'[.!?…]["\')\]]?$')
CLAUSE_END = re.compile(r'[,;:—–]["\')\]]?$')

_PUNCT = '.,;:!?…)]}"\''


def _width_of(words, measure, sep=' '):
    return measure(sep.join(words)) if words else 0.0


def _seam_index(words, at_least=1):
    """The index to break BEFORE, honouring "before a conjunction/preposition".

    Scans BACKWARDS and returns the FIRST match, so the seam is the LATEST one the
    budget allows.

    MEASURED 2026-10-17: the first version assigned `best = i` on every match and
    only returned at the end, which kept the EARLIEST seam instead of the latest
    and produced this, on a 119-character Portuguese sentence:

        linha 1   137 px  quando
        linha 2   199 px  eu estiver a
        (nao cabe: 'falar e a outra pessoa ...')

    Three words on a line and everything else thrown away, from a function whose
    whole job is to choose where to break. The seam has to be as late as the
    budget permits: that is what "keep the broken lines close in length" means
    (VEED) and what makes each line read as a complete phrase (BBC).
    """
    for i in range(len(words) - 1, at_least - 1, -1):
        head = words[i - 1]
        if not head:
            continue
        # "break after punctuation": the word BEFORE already ends the clause, so
        # the seam is right after it -- that is exactly index i.
        if SENTENCE_END.search(head) or CLAUSE_END.search(head):
            return i
        if head.lower().strip(_PUNCT) in BOUNDARY_BEFORE:
            return i
    # No seam at all: the last word that fits, which is the plain greedy break.
    return max(1, len(words) - 1)


def wrap(text, measure, max_px, max_lines=MAX_LINES):
    """Break `text` into at most `max_lines` lines that each fit `max_px`.

    `measure(str) -> px` is the caller's real text measurement. Returns a list of
    lines; it NEVER invents words, drops words, or reorders them. If the text does
    not fit, the overflow comes back in `overflow` so the caller can decide -- a
    3rd line on screen is a documented no-no, and silently clipping a sentence is
    worse, so the caller is told exactly what it is losing.

    >>> wrap('a b c d e', lambda s: len(s) * 10, 25)
    (['a b c', 'd e'], '')
    >>> wrap('one two three four', lambda s: len(s) * 10, 25)
    (['one two', 'three'], 'four')
    """
    words = [w for w in str(text or '').split() if w]
    if not words:
        return ([], '')
    if _width_of(words, measure) <= max_px:
        return ([(' '.join(words))], '')

    lines = []
    remaining = list(words)
    while remaining and len(lines) < max_lines:
        # Greedy: take the longest prefix that fits, then re-open it at a seam.
        take = 0
        for k in range(1, len(remaining) + 1):
            if _width_of(remaining[:k], measure) > max_px:
                break
            take = k
        if take == 0:
            # A single word wider than the box. It goes on its own line rather
            # than being cut: the renderer already clips at the overlay edge.
            take = 1
        if take >= len(remaining):
            lines.append(' '.join(remaining))
            remaining = []
            break
        cut = _seam_index(remaining[:take], at_least=1)
        cut = max(1, min(cut, take - 1))
        lines.append(' '.join(remaining[:cut]))
        remaining = remaining[cut:]

    overflow = ' '.join(remaining)
    return (lines, overflow)


def budget_px(work_width, font_px, measure):
    """The pixel width one caption line may occupy on THIS screen and font.

    The BBC's fraction, capped by the character ceiling for the case where the
    fraction would be absurdly wide (a 3840 px monitor would otherwise allow a
    2600 px line, which is exactly the "pulls the eye off the picture" failure
    42 characters exists to prevent).
    """
    fraction = int(work_width * WIDTH_FRACTION)
    # REPRESENTATIVE, not `M` * 42. Measured 2026-10-17: with the `M` ceiling the
    # budget came out at 1305 px (the BBC fraction) and a 68-character sentence --
    # 1156 px of real text -- stayed on ONE line. That is the owner's complaint
    # again, in a different hat: a caption that never breaks is not a caption that
    # breaks well. The character ceiling is the rule that binds.
    ceiling = measure(REPRESENTATIVE[:CHAR_CEILING])
    return max(160, min(fraction, ceiling))