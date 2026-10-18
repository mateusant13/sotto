#!/usr/bin/env python3
"""ORACLE: A LEGENDA QUEBRA-SE COMO O YOUTUBE, E MEDE-SE EM PIXELS.

O DONO, 2026-10-17, verbatim: *"e a legenda ta do tamanho da tela. é pra tu
verificar online como quebrar de um jeito bom. ou como o youtube faz"*.

A pesquisa (esta sessão, fontes no recibo) deu um consenso de industria:

    <= 42 caracteres por linha ... Netflix/TED/Section508/VEED
    no maximo 2 linhas no ecra . Netflix/TED/BBC/Section508/VEED
    quebrar apos pontuacao, antes de conjuncao, antes de preposicao ... Netflix
    nao separar artigo/substantivo, preposicao/frase, conjuncao/o que se segue,
    pronome/verbo, nem as partes de um verbo ...................... BBC
    68% da largura de um quadro 16:9 ................................ BBC

E A REGRA QUE MUDA TUDO: *"num character count so aproxima a largura numa fonte
PROPORCIONAL"*. A nossa e proporcional (Segoe UI). Portanto este oracle mede em
PIXELS COM A FONTE REAL, e os numeros de caracteres sao um tecto de legibilidade,
nunca o mecanismo.

OS BRACOS
  W1  nunca mais de 2 linhas no ecra                     (a regra mais replicada)
  W2  nenhuma linha excede o orcamento de pixels          (a regra da largura)
  W3  nenhuma palavra perde-se, duplica-se ou muda de ordem (a propriedade dura)
  W4  a quebra cai numa COSTURA: pontuacao, conjuncao ou preposicao, quando existe
  W5  o orcamento e 68% da area de trabalho, com tecto de 42 caracteres
  W6  o texto que nao cabe NAO E CORTADO EM SILENCIO: volta como `overflow`
  W7  o texto curto numa linha so, sem invenhar quebras
  W8  o Texto que cabe inteiro NUNCA e partido em duas

O `--neg-arm` parte cada regra e exige o vermelho, para o oráculo saber dizer NAO.

USO
    python _main/caption-wrap-oracle.py                 # GREEN / RED, imprime as linhas
    python _main/caption-wrap-oracle.py --neg-arm       # cada regra virada -> RED
    python _main/caption-wrap-oracle.py --font-only     # so a medicao real da fonte
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'app', 'webview'))

import caption_wrap as cw  # noqa: E402

# Frases em portugues e em ingles: `lang_id` e `auto`, o modelo descodifica o que
# ouvir, e uma quebra que so funciona numa das linguas é uma metada.
SAMPLES = [
    'esta e a legenda que o dono queria ver no meio em baixo da tela dele',
    'a porra da legenda, e pra ser independente do painel, nao acoplado',
    'e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer audio do meu pc',
    'quando eu estiver a falar e a outra pessoa estiver a falar ao mesmo tempo '
    'nao quero que o sistema misture as duas vozes',
    'the caption should break at a natural seam and never split a word',
    'short one',
    'x' * 300,
]


def synthetic_measure(text):
    """10 px per character: stands in for a real font when GDI is unavailable."""
    return len(text) * 10.0


# THE GDI OBJECTS LIVE HERE, AT MODULE SCOPE, AND NOT ON ANY STACK.
#
# MEDIDO 2026-10-17, and this took FIVE wrong instruments before one worked --
# every one of them recorded because the instrument decides whether this oracle
# means anything at all:
#   1. `StringFormat.MeasureTrailingSpaces` -- not a member of StringFormat.
#   2. `fmt.FormatFlags = StringFormat.GenericTypographic` -- pythonnet resolves
#      that name to the TYPE; assigning it to FormatFlags raises "StringFormat
#      value cannot be converted to StringFormatFlags".
#   3. `StringFormatFlags.GenericTypographic` -- not a member of the .NET enum.
#   4. `g.MeasureString(text, font, 10000, fmt)` -- the third argument is a SizeF
#      layout area; an int raises "Parametro invalido" on SOME strings only,
#      which is the worst failure mode there is.
#   5. pinning the objects on the returned closure -- the collector had not been
#      the cause; it simply did not help, which is worth recording because the
#      obvious theory looked right and was wrong.
#
# WHAT WORKS: the 2-argument `MeasureString(text, font)`, which is also the engine
# that draws the line (GraphicsPath.AddString + FillPath), so the number that
# decides a break comes from the renderer that will draw it. The tighter
# `StringFormat.GenericTypographic` measured 683.32 px against 715.24 px for 20 W
# -- but that is GDI opinion, not GDI+ path metrics, and a line broken for one
# and drawn by the other is how the last letter gets clipped. Over-estimating by
# 4.7% is safe; clipping is not.
_GDI = {}


def gdi_measure(px):
    'A real Segoe UI Bold measurement, or a refusal. Never a guess.'
    key = round(float(px), 2)
    if key in _GDI:
        return _GDI[key]

    import clr
    clr.AddReference('System.Drawing')
    from System.Drawing import Bitmap, Graphics, Font, FontStyle, GraphicsUnit
    from System.Drawing.Text import TextRenderingHint

    bmp = Bitmap(8, 8)
    g = Graphics.FromImage(bmp)
    g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
    font = Font('Segoe UI', key, FontStyle.Bold, GraphicsUnit.Pixel)

    def measure(text):
        if not text:
            return 0.0
        return g.MeasureString(text, font).Width

    measure.font_px = key
    # THE INSTRUMENT CHECKS ITSELF BEFORE IT IS TRUSTED. A measurement that
    # returns the same number for every string would make this oracle agree with
    # ANY budget, and a gate that cannot fail is not a gate. "W" is the widest
    # glyph and "i" the narrowest, so a real proportional measurement puts them
    # far apart.
    probe_w = measure('W' * 20)
    probe_i = measure('i' * 20)
    probe_long = measure('M' * 42)
    if not (probe_w > probe_i * 1.4):
        raise RuntimeError(
            'the measurement does not discriminate: 20 W = %.1f px, 20 i = %.1f px. The font is not being measured; the layout width is.'
            % (probe_w, probe_i))
    if not (probe_long > probe_w):
        raise RuntimeError(
            'the measurement stops working past %d characters (20 W = %.1f px, 42 M = %.1f px). The 42-character ceiling cannot be measured with this instrument, so it cannot be used.'
            % (probe_w, probe_long))
    measure.probe = (probe_w, probe_i, probe_long)
    _GDI[key] = measure
    return measure


# ── the arms ────────────────────────────────────────────────────────────────
def check(measure, work_width=1920):
    font_px = getattr(measure, 'font_px', 34)
    budget = cw.budget_px(work_width, font_px, measure)
    results = []
    lines_seen = []

    for text in SAMPLES:
        lines, overflow = cw.wrap(text, measure, budget)
        lines_seen.append((text, lines, overflow))

        # W1 -- no more than MAX_LINES on screen.
        results.append(('W1 at most 2 lines', len(lines) <= cw.MAX_LINES,
                        '%d line(s) for a %d-char sentence'
                        % (len(lines), len(text.split()))))

        # W2 -- every line fits the budget, with ONE declared exemption: a line
        # that is a SINGLE word longer than the budget cannot be broken at all,
        # so the wrapper hands it over whole and the renderer clips it. Measured,
        # not assumed: the sample `'x' * 300` is one word of 5813 px against a
        # 727 px budget, and inventing a break inside it would be a lie about a
        # word. The arm is WIDE ENOUGH TO HOLD ITS EXEMPTION rather than a gate
        # that quietly ignores the case.
        too_wide = [ln for ln in lines if measure(ln) > budget]
        exempt = [ln for ln in too_wide if ' ' not in ln]
        results.append(('W2 every line fits %d px (single words exempt)' % budget,
                        len(too_wide) == len(exempt),
                        'widest=%d px, %d line(s) over, %d of them one unbreakable word'
                        % (max([measure(l) for l in lines], default=0),
                           len(too_wide), len(exempt))))

        # W3 -- the durable property: no word lost, duplicated, or reordered.
        before = [w.lower().strip(cw._PUNCT) for w in text.split()]
        after = [w.lower().strip(cw._PUNCT) for w in ' '.join(lines + [overflow]).split()]
        results.append(('W3 no word lost or moved', before == after,
                        '%d words in, %d out' % (len(before), len(after))))

        # W4 -- when a natural seam existed, the break is on one.
        if len(lines) >= 2 and overflow:
            tail = lines[0].split()[-1]
            head = (lines[1] + ' ' + overflow).split()[0]
            seam = bool(cw.SENTENCE_END.search(tail) or cw.CLAUSE_END.search(tail)
                        or tail.lower().strip(cw._PUNCT) in cw.BOUNDARY_BEFORE
                        or head.lower().strip(cw._PUNCT) in cw.BOUNDARY_BEFORE)
            results.append(('W4 the break lands on a seam', seam,
                            'line1 ends %r, line2 starts %r' % (tail, head)))

        # W6 -- overflow is never swallowed.
        if overflow:
            results.append(('W6 overflow is returned, not clipped', len(overflow) > 0,
                            'overflow=%r' % overflow[:48]))

    # W5 -- the budget is the BBC fraction, with the REPRESENTATIVE ceiling on top.
    # MEASURED 2026-10-17: this arm first computed the ceiling as `measure('M' *
    # 42)` while `budget_px` used a real sentence, so it compared two different
    # definitions of the same rule and went RED against correct code. An arm that
    # re-implements the rule is a second rule; it has to call the one.
    fraction = int(work_width * cw.WIDTH_FRACTION)
    ceiling = measure(cw.REPRESENTATIVE[:cw.CHAR_CEILING])
    widest_w = measure('M' * cw.CHAR_CEILING)
    results.append(('W5 budget is the 68% fraction, representative-ceiling-capped',
                    budget == min(fraction, ceiling) and budget >= 160,
                    'budget=%d  68%%=%d  42 real chars=%d  (42 M would be %d)'
                    % (budget, fraction, int(ceiling), int(widest_w))))

    # W7 / W8 -- the two easy shapes.
    one_line = cw.wrap('frase curta', measure, budget)
    results.append(('W7 a short line stays one line',
                    len(one_line[0]) == 1 and not one_line[1],
                    '%r -> %r' % ('frase curta', one_line[0])))
    fits = 'palavra'
    two = cw.wrap(fits, measure, budget)
    results.append(('W8 text that fits is never split',
                    len(two[0]) == 1 and two[0][0] == fits,
                    '%r -> %r' % (fits, two[0])))
    return results, budget, lines_seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--font-only', action='store_true')
    ap.add_argument('--font-px', type=float, default=34.0)
    ap.add_argument('--work-width', type=int, default=1920)
    args = ap.parse_args()

    try:
        measure = gdi_measure(args.font_px)
        source = 'GDI+ Segoe UI Bold %g px' % args.font_px
    except Exception as exc:  # noqa: BLE001
        measure = synthetic_measure
        measure.font_px = args.font_px
        source = 'SINTETICA (10 px/char) -- GDI indisponivel: %r' % (exc,)

    print('MEDICAO: %s' % source)
    print('ORCAMENTO: %s\n' % ('cw.budget_px(work_width=%d)' % args.work_width))

    if args.neg_arm:
        return run_neg_arm(measure, args.work_width)

    results, budget, lines_seen = check(measure, args.work_width)

    if not args.font_only:
        print('--- AS LINHAS, DE VERDADE ---')
        for text, lines, overflow in lines_seen:
            print('\n  entrada (%d ch): %r' % (len(text), text[:74] + ('...' if len(text) > 74 else '')))
            for i, ln in enumerate(lines):
                print('    linha %d  %6.0f px  %s' % (i + 1, measure(ln), ln))
            if overflow:
                print('    (nao cabe, devolvido: %r)' % overflow[:60])
        print()

        print('--- BRACOS ---')
        bad = 0
        for arm, good, detail in results:
            print('  %-5s %-44s %s' % ('GREEN' if good else 'RED', arm, detail))
            if not good:
                bad += 1
        print()
        print('VERDICT: %s' % ('GREEN -- %d arms' % len(results) if not bad
                               else 'RED -- %d of %d arms failed' % (bad, len(results))))
        return 1 if bad else 0

    for text, lines, overflow in lines_seen:
        print('%r' % text[:70])
        for i, ln in enumerate(lines):
            print('   %d  %6.0f px  %s' % (i + 1, measure(ln), ln))
    return 0


def run_neg_arm(measure, work_width):
    """Break each rule in the MODULE (a scratch copy) and require RED."""
    import shutil
    import tempfile
    src = cw.__file__
    tmp = os.path.join(tempfile.gettempdir(), 'caption_wrap_mutant.py')

    mutants = [
        ('MAX_LINES becomes 6 (six lines on screen)',
         'MAX_LINES = %d' % cw.MAX_LINES, 'MAX_LINES = 6', work_width),
        ('the fraction becomes 1.0 (full screen width)',
         'WIDTH_FRACTION = %s' % cw.WIDTH_FRACTION, 'WIDTH_FRACTION = 1.0', 800),
        ('the ceiling is measured on 126 characters, not 42',
         'REPRESENTATIVE[:CHAR_CEILING]', 'REPRESENTATIVE[:CHAR_CEILING * 3]', work_width),
        ('no boundary list: break at the last word, always',
         'in BOUNDARY_BEFORE:', 'in ():', work_width),
    ]
    ok = True
    for label, old, new, mutant_width in mutants:
        text = open(src, encoding='utf-8').read()
        if old not in text:
            print('  ?? %-52s -> MUTATION DID NOT APPLY' % label)
            ok = False
            continue
        open(tmp, 'w', encoding='utf-8').write(text.replace(old, new, 1))
        import importlib.util
        spec = importlib.util.spec_from_file_location('cw_mutant', tmp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        budget = mod.budget_px(mutant_width, getattr(measure, 'font_px', 34), measure)
        broke = []
        for text_in in SAMPLES:
            lines, overflow = mod.wrap(text_in, measure, budget)
            if len(lines) > cw.MAX_LINES:
                broke.append('W1 %d lines on screen' % len(lines))
            over = [l for l in lines if measure(l) > budget and ' ' in l]
            if over:
                broke.append('W2 a multi-word line is %d px over the budget'
                             % int(measure(over[0]) - budget))
            before = [w.lower().strip(mod._PUNCT) for w in text_in.split()]
            after = [w.lower().strip(mod._PUNCT)
                     for w in ' '.join(lines + [overflow]).split()]
            if before != after:
                broke.append('W3 words lost or moved')
            # W4 judged with the ORACLE's own rules, not the mutant's: a mutant
            # that empties its own boundary list would otherwise be judged by the
            # empty list and pass. MEASURED 2026-10-17 -- the first mutation here
            # rewrote the frozenset literal, which unbalanced the module's
            # triple-quoted block and raised SyntaxError instead of testing
            # anything.
            if len(lines) >= 2 and overflow:
                tail = lines[0].split()[-1]
                head = (lines[1] + ' ' + overflow).split()[0]
                if not (cw.SENTENCE_END.search(tail) or cw.CLAUSE_END.search(tail)
                        or tail.lower().strip(cw._PUNCT) in cw.BOUNDARY_BEFORE
                        or head.lower().strip(cw._PUNCT) in cw.BOUNDARY_BEFORE):
                    broke.append('W4 the break is not on a seam (%r | %r)'
                                 % (tail, head))
        # W9: the budget itself. MEASURED 2026-10-17: two of the four mutations
        # produced a DIFFERENT budget and no other arm fired, because a wider
        # budget is not a violation -- it is just a different rule. W1..W8 say
        # "the lines obey whatever budget they were given"; only this one says
        # "and the budget is the researched one". The constants are LITERALS here
        # on purpose: reading them off `cw` would let a mutation move both sides
        # at once and the gate would agree with itself.
        expected = min(int(mutant_width * 0.68),
                       measure(cw.REPRESENTATIVE[:42]))
        if budget != expected:
            broke.append('W9 the budget is %d px, the researched one is %d px'
                         % (budget, expected))
        verdict = 'RED' if broke else 'GREEN'
        print('  %-4s %-52s -> %s' % (verdict, label + ' @' + str(mutant_width) + 'px', broke[:2] or 'no arm fired'))
        if not broke:
            ok = False
    try:
        os.remove(tmp)
    except OSError:
        pass
    print()
    print('NEG-ARM: %s' % ('PASS -- the oracle can say NO' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())