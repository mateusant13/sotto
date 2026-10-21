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

#: HOW FAR BACK A NATURAL SEAM MAY PULL THE LINE, IN WORDS.
#:
#: MEASURED 2026-10-18, and this number exists because the scan was unbounded.
#: The version that had no limit walked all the way to `at_least` looking for the
#: latest boundary, and because "a", "e", "que" and "de" are all in
#: `BOUNDARY_BEFORE`, the "latest boundary" was often index 1 or 2 -- a first line
#: of one or two words. Three real sentences, greedy prefix already measured at
#: 34 px Segoe UI Bold against a 727.06 px budget:
#:
#:     take=6 prefix=641px seam=1 -> line 1 = "A"       (36 px,  5% of budget)
#:     take=9 prefix=638px seam=1 -> line 1 = "Then,"   (103 px, 14% of budget)
#:     take=8 prefix=657px seam=2 -> line 1 = "And a"   (107 px, 15% of budget)
#:
#: The width that is wasted on line 1 is not cosmetic: it is pushed into line 2,
#: and line 2's overflow was being dropped, so a bad seam is a DIRECT cause of
#: lost words. VEED's "keep the broken lines close in length" and the BBC's "a
#: third line covers the frame" pull in the same direction.
#:
#: 3 words is the smallest limit that still reaches a comma or a preposition in
#: ordinary Portuguese and English sentences without emptying the line.
MAX_BACK_FROM_GREEDY = 3

#: `wrap` is called with this as `max_lines` when the caller wants EVERY line, so
#: the window can be chosen afterwards. One million is "no ceiling" without
#: risking `max_lines=0` somewhere downstream.
UNBOUNDED_LINES = 1 << 20

_PUNCT = '.,;:!?…)]}"\''


def _width_of(words, measure, sep=' '):
    return measure(sep.join(words)) if words else 0.0


def _seam_index(words, at_least=1, max_back=MAX_BACK_FROM_GREEDY):
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

    AND "AS LATE AS THE BUDGET PERMITS" HAS A CEILING. The fix above traded one
    failure for its mirror image: scanning to `at_least` finds a boundary, but
    the latest boundary in a sentence of ordinary words can still be index 1,
    because the most common Portuguese and English function words are all in
    `BOUNDARY_BEFORE`. `max_back` is that ceiling, and `MAX_BACK_FROM_GREEDY`
    holds the measurement.
    """
    # THE FLOOR IS THE WHOLE FIX, and it is one line. `words` is the greedy
    # prefix -- the longest run that already FITS -- so its last index is the
    # plain greedy break, which is always available and always fills the line.
    # A natural seam is worth backing up for; it is not worth emptying the line
    # for. See `MAX_BACK_FROM_GREEDY` for the measurement that produced it.
    # `max_back` bounds how far a seam reaches BACK FROM THE END of the greedy
    # prefix; the third clause bounds how much of the line it may CONSUME. On a
    # six-word prefix they agree, but on a two- or three-word prefix `max_back`
    # alone reaches all the way down to `at_least` -- and "a", "e", "que" and
    # "de" are all in `BOUNDARY_BEFORE`, which is how a three-word fit became
    # the one-word line "A" (measured 2026-10-18: 36 px of a 727 px budget).
    # A seam may save a line from ending on a preposition; it may not empty the
    # line to find one.
    floor = max(at_least, len(words) - max_back, (len(words) + 1) // 2)
    for i in range(len(words) - 1, floor - 1, -1):
        head = words[i - 1]
        if not head:
            continue
        # "break after punctuation": the word BEFORE already ends the clause, so
        # the seam is right after it -- that is exactly index i.
        if SENTENCE_END.search(head) or CLAUSE_END.search(head):
            return i
        if head.lower().strip(_PUNCT) in BOUNDARY_BEFORE:
            return i
    # No seam within reach: take the WHOLE prefix. `words` is the greedy run that
    # already fits the budget, so `len(words)` is the plain greedy break and it
    # spends every pixel the budget allows.
    #
    # THIS USED TO BE `max(1, len(words) - 1)`, one word short of the fit.
    # Together with the caller's own `min(cut, take - 1)`, EVERY line of EVERY
    # caption gave up its last fitting word -- a whole word of the 727 px budget
    # discarded per line, nothing logged, nothing visible as an error. `len(words)`
    # is also what makes this file's two original doctests reachable at all;
    # see `_main/caption-wrap-doctest-provenance.py`.
    return len(words)


def _greedy_end(words, measure, max_px, start):
    """The largest index `k` (>= start+1) whose prefix from `start` fits.

    A single word wider than `max_px` becomes its own line (`start + 1`): the
    wrap NEVER splits a word, so the only honest choice is to hand the word over
    whole and let the renderer clip it at the overlay edge. See `_layout`.
    """
    k = start
    for j in range(start + 1, len(words) + 1):
        if _width_of(words[start:j], measure) > max_px:
            break
        k = j
    return max(start + 1, k)


def _greedy_lines(words, measure, max_px):
    """Greedy lines re-opened at a natural seam, as `(start, end)` index pairs.

    The SAME break rule `wrap` has always used -- fill to the budget, then
    re-open at the latest natural seam (`_seam_index`) -- but expressed over
    indices so the balance step can move a boundary without losing a word. The
    LAST line is the raw remainder, exactly as before: it is the line the
    balance step exists for.
    """
    out = []
    i = 0
    n = len(words)
    while i < n:
        j = _greedy_end(words, measure, max_px, i)
        if j < n:
            cut = _seam_index(words[i:j], at_least=1)
            cut = max(1, min(cut, j - i))
            j = i + cut
        out.append((i, j))
        i = j
    return out


def _is_seam(words, m):
    """Does the word BEFORE index `m` end a clause, or is it a boundary word?

    The same predicate `_seam_index` uses, read at one boundary, so the balance
    step can prefer a natural break without importing a second rule.
    """
    head = words[m - 1]
    if not head:
        return False
    return bool(SENTENCE_END.search(head) or CLAUSE_END.search(head)
                or head.lower().strip(_PUNCT) in BOUNDARY_BEFORE)


def _balance_last(lines, words, measure, max_px):
    """Re-break the boundary between the LAST two lines so their widths are close.

    WHY: a greedy break leaves the last line as whatever is left over, and the
    two-line window the overlay shows is the LAST two lines -- so the leftover is
    on screen. MEASURED 2026-10-21 on the owner's own last 400 captions, with
    the real Segoe UI Bold 34 px against the real 727.06 px budget: median
    imbalance 0.596, worst 0.939 (a 723 px line over a 44 px line). The receipt's
    own example (`e o que eu quero e que a legenda apareca aqui em baixo, igual o
    youtube faz`) measures 532.5 px over 329.3 px = 0.382.

    YouTube balances the two lines it shows; the research in this module's header
    (VEED: "keep the broken lines close in length") says the same. So the
    boundary is moved to the split that minimises the width difference.

    THE TWO HARD RULES THE MOVE STILL OBEYS, and they are why this is a re-break
    and not a re-write:
      * a line NEVER exceeds `max_px` -- every candidate is checked against it;
      * NO WORD IS EVER SPLIT -- a candidate is a word index, so words stay whole
        and in order.

    A natural seam wins a near-tie, and among equal choices the larger `m` wins,
    so line 1 stays as full as the balance allows ("a line is filled greedily").
    """
    if len(lines) < 2:
        return lines
    (a, b) = lines[-2]
    (c, d) = lines[-1]
    best_diff = None
    cands = []
    for m in range(a + 1, d):
        w1 = _width_of(words[a:m], measure)
        w2 = _width_of(words[m:d], measure)
        if w1 > max_px or w2 > max_px:
            continue
        diff = abs(w1 - w2)
        cands.append((m, diff))
        if best_diff is None or diff < best_diff:
            best_diff = diff
    if not cands or best_diff is None:
        return lines
    # A seam within a hair of the best balance keeps the natural break; the
    # tolerance is 1% of the budget, far below a word's width, so it can only
    # pick a seam that is already a near-tie, never trade balance for grammar.
    near = [m for (m, diff) in cands if diff <= best_diff + max(1.0, 0.01 * max_px)]
    m = min(near, key=lambda m: (0 if _is_seam(words, m) else 1,
                                 dict(cands)[m], -m))
    return list(lines[:-2]) + [(a, m), (m, d)]


def wrap(text, measure, max_px, max_lines=MAX_LINES):
    """Break `text` into at most `max_lines` lines that each fit `max_px`.

    `measure(str) -> px` is the caller's real text measurement. Returns a list of
    lines; it NEVER invents words, drops words, or reorders them. If the text does
    not fit, the overflow comes back in `overflow` so the caller can decide -- a
    3rd line on screen is a documented no-no, and silently clipping a sentence is
    worse, so the caller is told exactly what it is losing.

    # 10 px per character, so a 60 px budget holds SIX characters: 'a b c' is five
    # and fits, 'a b c d' is seven and does not. The seam has nothing to reach
    # inside a three-word fit, so line 1 takes the greedy break and line 2 the
    # rest.
    >>> wrap('a b c d e', lambda s: len(s) * 10, 60)
    (['a b c', 'd e'], '')

    # 75 px holds 'one two' (70) and not 'one two three' (130).
    >>> wrap('one two three four', lambda s: len(s) * 10, 75)
    (['one two', 'three'], 'four')

    # AND THE BUDGET THE OLD EXAMPLES NAMED, kept as a regression arm with its
    # real answer: at 25 px only ONE word fits per line, so a three-word first
    # line is not a seam choice, it is arithmetic. This is what the two examples
    # above used to claim, and it is why they failed at HEAD -- 2 attempted / 2
    # failed on `git show HEAD`, unchanged by the seam patch.
    >>> wrap('a b c d e', lambda s: len(s) * 10, 25)
    (['a', 'b'], 'c d e')
    """
    words = [w for w in str(text or '').split() if w]
    if not words:
        return ([], '')
    if _width_of(words, measure) <= max_px:
        return ([(' '.join(words))], '')
    if max_lines <= 0:
        return ([], ' '.join(words))

    # Greedy fill, re-opened at the latest natural seam (`_seam_index`), and
    # THEN the last boundary is re-balanced so the two lines the window shows are
    # close in width -- the YouTube rule the owner asked for by name
    # (*"como o youtube da DISPLAY e quebra as linhas"*). The balance step is a
    # RE-BREAK of an existing boundary, so it moves whole words between two lines
    # but can never split one and can never make a line wider than the budget.
    lines = _greedy_lines(words, measure, max_px)
    lines = _balance_last(lines, words, measure, max_px)
    strs = [' '.join(words[i:j]) for (i, j) in lines]
    if len(strs) <= max_lines:
        return (strs, '')
    shown = strs[:max_lines]
    overflow = ' '.join(words[lines[max_lines - 1][1]:])
    return (shown, overflow)


def wrap_tail(text, measure, max_px, max_lines=MAX_LINES):
    """The LAST `max_lines` lines of the sentence, and the text that scrolled off.

    WHY THIS EXISTS -- it is the promise in this module's own header, made
    callable. `wrap` returns `overflow` "so the caller can decide"; the only
    caller bound it to `_overflow` and dropped it, so a growing forming line
    simply stopped being drawn once it passed two lines. MEASURED 2026-10-18 on
    the owner's own last 400 captions: 168 of them lost words, 772 words in
    total, the worst losing 59 of 68. Owner, verbatim: *"ta cortando palavras"*.

    THE FIX IS A WINDOW THAT SLIDES, not a bigger cap. Netflix, TED, BBC,
    Section508 and VEED all agree on 2 lines, and that number came from the
    owner's own instruction to research how YouTube breaks a caption -- so
    `MAX_LINES` stays 2 and the QUESTION becomes which two. The tail: the newest
    words, which are the words he just heard and the ones the engine is still
    rewriting. The words that scroll off were on screen first, which is exactly
    what a live caption does and what the YouTube one the owner asked to copy
    does. A third line is still never on screen.

    `scrolled` is what left the window, returned for the same reason `wrap`
    returns `overflow`: the caller may want to log it, and a claim of "no word is
    ever dropped" has to be checkable rather than asserted.

    At 10 px per character and a 25 px budget each line holds ONE of these
    words, so the 40-word sentence makes 40 lines and the window keeps the last
    two:

    >>> lines, gone = wrap_tail(' '.join('w%d' % i for i in range(40)),
    ...                         lambda s: len(s) * 10, 25, max_lines=2)
    >>> lines
    ['w38', 'w39']
    >>> gone.split()[0], gone.split()[-1], len(gone.split())
    ('w0', 'w37', 38)

    Every word is in `lines` or in `gone`, which is the whole claim: 2 + 38 = 40.
    """
    lines, _still_over = wrap(text, measure, max_px,
                              max_lines=UNBOUNDED_LINES)
    if not lines:
        return ([], '')
    if len(lines) <= max_lines:
        return (lines, '')
    scrolled = ' '.join(lines[:-max_lines])
    return (lines[-max_lines:], scrolled)


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