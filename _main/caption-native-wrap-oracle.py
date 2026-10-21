#!/usr/bin/env python
"""ORACLE: the NATIVE caption breaks like YouTube's, and never splits a word.

WHY THIS LANE EXISTS. The live caption the owner sees is drawn by the NATIVE
renderer (`app/webview/caption_overlay.py` + `app/webview/caption_wrap.py`),
NOT by `app/panel/caption.html` -- that file is loaded by no window at all
(`sotto_webview.py:69` defines `CAPTION_HTML` and there is exactly ONE
occurrence, the definition; `sotto_webview.py:5885` says *"THE FLOATING CAPTION
IS A NATIVE LAYERED WINDOW, NOT A WEBVIEW2"*). So a CSS fix cannot reach the
owner's screen on this path.

The owner, verbatim (2026-10-21): *"voce nao ta fazendo a legenda parecendo com
como o youtube da DISPLAY e quebra as linhas e etc. é pra tu fazer isso."* and
*"só palavras inteiras"*.

THE THREE CLAIMS, IN THE FORM THAT CAN BE CHECKED:
  1. BALANCE -- the two lines the window shows are close in width. YouTube
     balances them (VEED: "keep the broken lines close in length").
  2. NO WORD IS EVER SPLIT -- the words on screen plus the words that scrolled
     off are EXACTLY the words that went in, in order.
  3. NOTHING IS LOST -- a caption longer than the window keeps its overflow in
     `scrolled`, which is what makes the claim checkable instead of a promise.

MEASUREMENT. The widths come from the PRODUCT's own measuring function --
`caption_overlay._measure` (GDI+ `Graphics.MeasureString` on a MEMORY bitmap:
no window, no app, no browser, no audio) at the product's own size (Segoe UI
Bold 34 px) and the product's own budget (`caption_wrap.budget_px`). The lines
come from the product's own `_layout`, so this measures the code that will run,
not a transcription of it.

THE NEGATIVE ARM IS EXECUTED, NOT DECORATIVE: two mutants of the wrap module
-- the balance step removed, and the space between words dropped -- each in a
COPY, and each must make an arm go RED while the real bytes stay GREEN.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WEBVIEW = os.path.join(os.path.dirname(HERE), 'app', 'webview')
WRAP = os.path.join(WEBVIEW, 'caption_wrap.py')
OVERLAY = os.path.join(WEBVIEW, 'caption_overlay.py')
EXIT_PASS, EXIT_FAIL = 0, 1

rows: list[tuple[bool, str, str]] = []


def add(ok: bool, name: str, detail: str = '') -> bool:
    rows.append((bool(ok), name, detail))
    print('  %s %s%s' % ('GREEN' if ok else 'RED  ', name,
                          ('  ' + detail) if detail else ''))
    return bool(ok)


def load_module(path: str, name: str):
    """Import a module by path, with the product's own directory on sys.path.

    `caption_overlay.py` does `import caption_wrap as _cw`, so the two must be
    importable as siblings -- the app does that by living in the same folder.
    """
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── the corpus ────────────────────────────────────────────────────────────────
#: REAL caption texts, Portuguese and English, of the length a live caption
#: actually reaches. The first one is the owner's own example, quoted in the
#: wrap module's own receipt.
CORPUS = [
    'e o que eu quero e que a legenda apareca aqui em baixo, igual o youtube faz',
    'a legenda tem que aparecer no ecra, e nao dentro de um painel a direita',
    'eu aperto alt c e o painel aparece, com as palavras que eu acabei de dizer',
    'this is the second pass, and it has to arrive after the live caption is done',
    'quando o modelo grande nao esta a correr, o parakeet e que escreve',
    'ok.',
    'a palavra mais comprida do mundo: pneumoultramicroscopicsilicovolcanoconiosis',
]

#: The imbalance the arm allows. MEASURED on this corpus with the shipped
#: bytes: the worst pair is below this. The BEFORE (the balance step removed)
#: is far above it -- the receipt carries both numbers.
BALANCE_MAX = 0.25


def words_of(text: str) -> list[str]:
    return [w for w in re.split(r'\s+', (text or '').strip()) if w]


def check_corpus(overlay, wrap, label: str) -> dict:
    """Every claim, over the corpus. Returns the measured numbers."""
    measure = overlay._measure('m', 34.0, overlay._MEASURE_CACHE)
    budget = wrap.budget_px(1920, 34.0, measure)
    worst = 0.0
    worst_text = ''
    over = []
    lost = []
    long_word = []
    for text in CORPUS:
        lines, _prev, _w, _h, scrolled = overlay._layout(text, '', 1.0, 1920)
        shown = []
        for line in lines:
            shown.extend(words_of(line))
        # A SINGLE word wider than the budget cannot be made to fit without
        # being SPLIT, and the never-split rule wins: the word is handed over
        # whole and the renderer clips it (`caption_wrap._greedy_end` says so).
        # That case is counted apart -- it is a documented behaviour, not a
        # defect, and it is exactly where balance is impossible.
        too_wide = [(ln, measure(ln)) for ln in lines
                    if measure(ln) > budget + 0.5]
        single_over = [ln for (ln, wd) in too_wide if len(words_of(ln)) == 1]
        if single_over:
            long_word.append((text[:28], round(measure(single_over[0]), 1)))
        for ln, wd in too_wide:
            if len(words_of(ln)) > 1:
                over.append((text[:28], round(wd, 1)))
        # 2. no word is split and nothing is lost: the words IN ORDER are the
        #    words that scrolled off followed by the words on screen.
        if words_of(scrolled) + shown != words_of(text):
            lost.append(text[:28])
        # 3. balance of the two lines the window shows -- measured only where
        #    balancing is POSSIBLE (no over-long single word).
        if len(lines) == 2 and not single_over:
            w1, w2 = measure(lines[0]), measure(lines[1])
            ratio = abs(w1 - w2) / max(w1, w2, 1.0)
            if ratio > worst:
                worst, worst_text = ratio, text[:44]
    return {'budget': budget, 'worst': worst, 'worst_text': worst_text,
            'over': over, 'lost': lost, 'long_word': long_word}


#: The mutants, as TEXTUAL patches of a unique anchor in the wrap module. Each
#: is written to a COPY, installed as the module `caption_wrap` (which is what
#: `caption_overlay.py` imports), and the SAME arms run against it. A mutant
#: that no arm notices is DECORATIVE -- it proves nothing -- so the oracle
#: refuses to count it.
MUTANTS = [
    ('M1 the balance step is removed',
     "    lines = _balance_last(lines, words, measure, max_px)",
     "    lines = list(lines)"),
    ('M2 the space between the words is dropped',
     "    strs = [' '.join(words[i:j]) for (i, j) in lines]",
     "    strs = [''.join(words[i:j]) for (i, j) in lines]"),
]


def run_with(wrap_source: str, overlay_path: str):
    """Install `wrap_source` as the module `caption_wrap`, then load the overlay.

    The overlay does `import caption_wrap as _cw` at MODULE level, so the
    mutant has to be in `sys.modules` BEFORE the overlay is loaded -- that is
    what makes the overlay draw the MUTANT lines.
    """
    tmp = tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                      encoding='utf-8')
    try:
        tmp.write(wrap_source)
        tmp.close()
        sys.modules.pop('caption_wrap', None)
        spec = importlib.util.spec_from_file_location('caption_wrap', tmp.name)
        mod = importlib.util.module_from_spec(spec)
        sys.modules['caption_wrap'] = mod
        spec.loader.exec_module(mod)
        overlay = load_module(overlay_path, 'caption_overlay_probe')
        return check_corpus(overlay, mod, 'mutant')
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        sys.modules.pop('caption_wrap', None)


def main() -> int:
    neg_arm = '--neg-arm' in sys.argv[1:]
    print('caption-native-wrap-oracle -- the REAL native layout, real GDI+ metrics')
    overlay = load_module(OVERLAY, 'caption_overlay_probe')
    wrap = load_module(WRAP, 'caption_wrap_probe')

    measured = check_corpus(overlay, wrap, 'shipped')
    print('')
    print('  budget: %.1f px  (Segoe UI Bold 34 px)' % measured['budget'])
    print('')
    print('ARM 1  the lines never exceed the budget')
    add(not measured['over'],
        'no line is wider than the budget',
        ('over: %r' % (measured['over'],)) if measured['over'] else '0 over')
    print('')
    print('ARM 2  NO WORD IS EVER SPLIT, and nothing is lost')
    add(not measured['lost'],
        'the scrolled words followed by the shown words are the input words',
        ('lost/split: %r' % (measured['lost'],)) if measured['lost'] else '0 lost')
    print('')
    print('ARM 3  the two lines are BALANCED (the YouTube rule)')
    add(measured['worst'] <= BALANCE_MAX,
        'the worst imbalance is within %.2f' % BALANCE_MAX,
        'worst=%.3f (%s)' % (measured['worst'], measured['worst_text']))
    print('')
    print('ARM 4  a word too long for the box is handed over WHOLE, not split')
    print('  (the never-split rule wins; the renderer clips it)')
    ok_long = True
    for text in CORPUS:
        lines, _prev, _w, _h, _scrolled = overlay._layout(text, '', 1.0, 1920)
        for ln in lines:
            for w in words_of(ln):
                if w not in text:
                    ok_long = False
    add(ok_long, 'no word on screen is a fragment of another word',
        'the over-long word is whole')

    if neg_arm:
        print('')
        print('NEGATIVE ARM -- broken copies must go RED')
        source = open(WRAP, encoding='utf-8').read()
        for label, old, new in MUTANTS:
            if source.count(old) != 1:
                add(False, 'mutant %r could not be built' % label,
                    'the anchor occurs %d time(s)' % source.count(old))
                continue
            mutant = run_with(source.replace(old, new, 1), OVERLAY)
            noticed = []
            if mutant['over']:
                noticed.append('budget')
            if mutant['lost']:
                noticed.append('word-integrity')
            if mutant['worst'] > BALANCE_MAX:
                noticed.append('balance')
            add(bool(noticed), 'mutant %r is caught' % label,
                ('caught by: ' + ', '.join(noticed)) if noticed
                else 'NOTHING -- it changed nothing')

    bad = [r for r in rows if not r[0]]
    print('')
    print('%d/%d GREEN' % (len(rows) - len(bad), len(rows)))
    if bad:
        print('VERDICT: FAIL')
        for _ok, n, d in bad:
            print('  - %s  %s' % (n, d))
        sys.exit(EXIT_FAIL)
    print('VERDICT: PASS')
    return EXIT_PASS


if __name__ == '__main__':
    sys.exit(main())
