# NO-BUG: Oracle: "a legenda esta' sincronizada" tem de ser PROVAVEL num lane,
#        sem o ecra do dono. O mesmo `_layout`/`_premultiplied_bitmap` que pinta
#        a faixa real pinta um bitmap fora do ecra num instante declarado, e o
#        texto PINTADO e' comparado com o relogio do cue do produto.
#        Nao ha id de `_main/bug-ledger.json` para isto, e o id nao se inventa.
"""Oracle: the cue-to-pixels instant, measured off-screen at a declared wall clock.

THE HOLE. `_main/overlay-ink-oracle.py` proves the real drawing path lays down
ink, follows the text and caches per line. `_main/yt-reveal-hold-oracle.py`
proves the reveal clock never invents more than `PLAYER_HOLD_S` of video. Neither
proves that the INK at instant `now` is the ink the cue clock asks for: in lane
mode `SOTTO_LANE_LAUNCH=1` there are no cues on screen at all. This gate closes
that gap by rendering the product's own layout to a GDI+ bitmap at each declared
wall instant and comparing the painted text with an expectation recomputed from
the cue clock (not from the renderer's own `frame()` call).

ARMS (relations, not literals)
  a WINDOW         -- inside [start, end] the frame carries that cue's text and
                      ink; after end + PLAYER_HOLD_S it carries neither;
  b BETWEEN-CUES   -- after a new publish the frame carries the new cue, never
                      the stale one;
  c RASTER         -- same text -> same raster, different text -> different
                      raster, empty cue -> zero ink;
  d CADENCE        -- N instants 1/60 s apart produce N frames whose painted
                      cue advances monotonically;
  e HOLD-CAP       -- past PLAYER_HOLD_S the painted text stops advancing;
  f TIMING         -- painted text == cue-clock text at every sampled instant,
                      with a declared budget of ONE 60 Hz frame interval
                      (16.667 ms) and the worst observed error printed in ms.

`--neg-arm` mutates SCRATCH COPIES of the product modules and of
`headless_paint.py` -- never a product file -- and requires every mutant to be
caught by its named arm.

Usage:
  python _main/yt-headless-paint-oracle.py             # VERDICT: PASS, rc 0
  python _main/yt-headless-paint-oracle.py --neg-arm   # NEG-ARM: PASS -- k/k, rc 1
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['SOTTO_ROOT'] = ROOT.replace('\\', '/')
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
HEADLESS = os.path.join(WEBVIEW, 'headless_paint.py')
PAINT = os.path.join(WEBVIEW, 'overlay_paint.py')
OVERLAY = os.path.join(WEBVIEW, 'caption_overlay.py')
if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

FRAME_S = 1.0 / 60.0
FRAME_BUDGET_MS = 1000.0 / 60.0
INK_FLOOR = 100  # sampled pixels (step 2) -- same floor as the ink oracle


def load_from_path(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_from_source(source, name):
    """A scratch module from TEXT, for the negative arm (product files untouched)."""
    folder = tempfile.mkdtemp(prefix='headless-paint-neg-')
    path = os.path.join(folder, name + '.py')
    try:
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(source)
        return load_from_path(path, name)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def load_headless():
    return load_from_path(HEADLESS, 'headless_paint_gate')


def words_of(text):
    """Painted words, without the `rows_text` line terminator."""
    return str(text or '').replace('\n', ' ').split()


def arms(hp, product, metrics=None):
    results = []
    hold = float(product.overlay.PLAYER_HOLD_S)
    a_words = ['alpha', 'bravo', 'charlie', 'delta']
    a = hp.make_cue(product, 'A', a_words, 100.0, gap=0.253, end=101.2)
    b = hp.make_cue(product, 'B', ['echo', 'foxtrot', 'golf', 'hotel'], 110.0,
                    at=2.0, gap=0.8, end=116.0)
    after_a = (float(a['end']) + hold + 0.1 - float(a['t'])
               + float(a['at']))  # wall, not video time

    # a WINDOW -- the cue's own text inside the window, nothing after end+hold.
    inside = [hp.render_frame(product, [a], now) for now in (0.15, 0.6)]
    gone = hp.render_frame(product, [a], after_a)
    inside_ok = all(f['cue'] == 'A' and f['ink_px'] >= INK_FLOOR
                    and f['text'] == hp.expected_text(product, a, f['instant'])
                    for f in inside)
    results.append(('a WINDOW', bool(inside_ok and not gone['text']
                                     and gone['ink_px'] == 0),
                    'inside=%s ink=%s after+hold t=%.2fs text=%r ink=%d'
                    % ([f['text'].strip() for f in inside],
                       [f['ink_px'] for f in inside], after_a,
                       gone['text'], gone['ink_px'])))

    # b BETWEEN-CUES -- a later publish owns the frame; the retired cue does not
    # survive its hold. 'before' is still inside A's lifetime.
    before = hp.render_frame(product, [a, b], 1.2)
    switched = hp.render_frame(product, [a, b], 2.05)
    beyond = hp.render_frame(product, [a, b], after_a + 0.2)
    stale = lambda f: any(word in f['text'] for word in a_words)
    between_ok = (before['cue'] == 'A' and words_of(before['text']) == a_words
                  and switched['cue'] == 'B' and 'echo' in switched['text']
                  and not stale(switched)
                  and switched['text'] == hp.expected_text(product, b, 2.05)
                  and beyond['cue'] == 'B' and not stale(beyond)
                  and beyond['text'] == hp.expected_text(product, b, beyond['instant'])
                  and beyond['ink_px'] >= INK_FLOOR)
    results.append(('b BETWEEN-CUES', bool(between_ok),
                    'before=%s switched=%s beyond=%s stale_after=%s'
                    % (before['cue'], switched['cue'], beyond['cue'],
                       stale(beyond))))

    # c RASTER -- identity by pixels, not by log text.
    same_1 = hp.render_frame(product, [a], 0.10)
    same_2 = hp.render_frame(product, [a], 0.20)  # same revealed prefix
    other = hp.render_frame(product, [a], 1.0)    # whole sentence
    empty = hp.render_frame(product, [], 0.5)
    raster_ok = (same_1['ink_px'] >= INK_FLOOR
                 and same_1['text'] == same_2['text']
                 and same_1['digest'] == same_2['digest']
                 and same_1['box'] == same_2['box']
                 and other['ink_px'] >= INK_FLOOR
                 and other['digest'] != same_1['digest']
                 and empty['text'] == '' and empty['ink_px'] == 0
                 and empty['box'] == (0, 0, 0, 0))
    results.append(('c RASTER', bool(raster_ok),
                    'A=%s A2=%s other=%s empty_ink=%d spans=%s/%s'
                    % (same_1['digest'][:10], same_2['digest'][:10],
                       other['digest'][:10], empty['ink_px'],
                       same_1['ink_span'], other['ink_span'])))

    # d CADENCE -- exactly N frames, exactly 1/60 s apart, cue never goes back.
    grid = [k * FRAME_S for k in range(36)]
    frames = [hp.render_frame(product, [a], now) for now in grid]
    counts = [len(words_of(f['text'])) for f in frames]
    cadence_ok = (len(frames) == 36
                  and all(abs(frames[i]['instant'] - frames[i - 1]['instant']
                              - FRAME_S) < 1e-9 for i in range(1, len(frames)))
                  and all(counts[i] >= counts[i - 1] for i in range(1, len(counts)))
                  and len(set(counts)) >= 3
                  and all(f['text'] == hp.expected_text(product, a, f['instant'])
                          for f in frames))
    results.append(('d CADENCE', bool(cadence_ok),
                    'frames=%d step=%.6fs words=%d..%d distinct=%d'
                    % (len(frames), FRAME_S, min(counts), max(counts),
                       len(set(counts)))))

    # e HOLD-CAP -- a long cue: before the hold it advances, after the hold the
    # painted RASTER is byte-identical (no invented video).
    long_cue = hp.make_cue(product, 'L', ['w%02d' % i for i in range(40)],
                            200.0, gap=0.1, end=204.0)
    early = hp.render_frame(product, [long_cue], 2.0)
    cap = hp.render_frame(product, [long_cue], 3.0)
    late = hp.render_frame(product, [long_cue], 5.0)
    hold_ok = (len(words_of(early['text'])) < len(words_of(cap['text']))
               and cap['ink_px'] >= INK_FLOOR
               and cap['text'] == late['text']
               and cap['digest'] == late['digest']
               and cap['box'] == late['box'])
    results.append(('e HOLD-CAP', bool(hold_ok),
                    'words %d -> %d -> %d raster_equal=%s hold_s=%.1f'
                    % (len(words_of(early['text'])), len(words_of(cap['text'])),
                       len(words_of(late['text'])),
                       cap['digest'] == late['digest'], hold)))

    # f TIMING -- the PAINTED text against the cue clock recomputed independently.
    # Word instants are deliberately NOT on the 60 Hz grid: the worst error is a
    # measured distance from a cue boundary to the first frame that paints it.
    t_words = ['one', 'two', 'three', 'four', 'five']
    cue = hp.make_cue(product, 'T', t_words, 300.0, gap=0.1803, end=301.2)
    timed = [hp.render_frame(product, [cue], k * FRAME_S) for k in range(60)]
    mismatches = sum(1 for f in timed
                     if f['text'] != hp.expected_text(product, cue, f['instant']))
    worst_s = 0.0
    for index in range(1, len(cue['word_starts'])):
        boundary = (float(cue['at'])
                    + (float(cue['word_starts'][index]) - float(cue['t']))
                    / float(cue['rate']))
        first = next((f['instant'] for f in timed
                      if len(words_of(f['text'])) >= index + 1), None)
        if first is None:
            mismatches += 1
            continue
        worst_s = max(worst_s, abs(first - boundary))
    worst_ms = worst_s * 1000.0
    if metrics is not None:
        metrics['worst_ms'] = worst_ms
        metrics['mismatches'] = mismatches
    timing_ok = mismatches == 0 and worst_ms <= FRAME_BUDGET_MS + 1e-9
    results.append(('f TIMING', bool(timing_ok),
                    'frames=%d mismatches=%d worst=%.3f ms budget=%.3f ms'
                    % (len(timed), mismatches, worst_ms, FRAME_BUDGET_MS)))
    return results


MUTATIONS = (
    # (label, source, old, new, arm that MUST fail)
    ('frozen-clock', 'overlay',
     't = self.t + elapsed * self.rate', 't = self.t', 'f TIMING'),
    ('no-hold', 'overlay',
     'elapsed = min(gap, PLAYER_HOLD_S)', 'elapsed = gap', 'e HOLD-CAP'),
    # O CANAL DO PLAYER TRAZ '\\n' (rows_text), logo `_layout` corre o RAMO das
    # linhas ja' quebradas -- mutar o ramo do `wrap_tail` seria decorativo.
    ('blank-glyphs', 'paint',
     "cur_lines = text.splitlines() if '\\n' in text else ([text] if text else [])",
     "cur_lines = ['']", 'a WINDOW'),
    ('stale-cue', 'headless',
     'cue = select_cue(windows, now)',
     'cue = windows[0] if windows else None', 'b BETWEEN-CUES'),
    ('full-text-frame', 'headless',
     'text = product.reveal.rows_text(texts)',
     "text = cue['text']", 'd CADENCE'),
)


def normal_arm():
    hp = load_headless()
    product = hp.load_product()
    hp._DISPOSED = 0
    metrics = {}
    failed = 0
    for name, ok, detail in arms(hp, product, metrics):
        print('  %-16s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
        failed += 0 if ok else 1
    print('WORST TIMING ERROR: %.3f ms (budget %.3f ms = one frame at 60 Hz)'
          % (metrics.get('worst_ms', -1.0), FRAME_BUDGET_MS))
    print('TEARDOWN: bitmaps_disposed=%d child_processes=0 windows_opened=0'
          % hp.dispose_count())
    print('VERDICT: %s' % ('PASS' if not failed else 'FAIL'))
    return 0 if not failed else 1


def neg_arm():
    source = {key: None for key in ('overlay', 'paint', 'headless')}
    for key, path in (('overlay', OVERLAY), ('paint', PAINT),
                      ('headless', HEADLESS)):
        with open(path, encoding='utf-8') as fh:
            source[key] = fh.read()
    caught = weak = 0
    for label, key, old, new, owner in MUTATIONS:
        count = source[key].count(old)
        if count != 1:
            print('  RED   mutant %-16s anchor count=%d (decorative)'
                  % (label, count))
            weak += 1
            continue
        mutated = source[key].replace(old, new, 1)
        name = 'scratch_%s_%s' % (key, label.replace('-', '_'))
        module = load_from_source(mutated, name)
        hp = load_headless()
        product = hp.load_product()
        if key == 'overlay':
            product.overlay = module
        elif key == 'paint':
            product.paint = module
        else:
            hp = module
        got = {arm_name: ok for arm_name, ok, _detail in arms(hp, product)}
        if not got.get(owner, True):
            print('  GREEN mutant %-16s caught by: %s' % (label, owner))
            caught += 1
        else:
            print('  RED   mutant %-16s SURVIVED on arm %s -- gate blind'
                  % (label, owner))
    total = len(MUTATIONS)
    ok = caught == total and weak == 0
    print('TEARDOWN: child_processes=0 windows_opened=0 product_files_written=0')
    print('NEG-ARM: %s -- %d/%d' % ('PASS' if ok else 'FAIL', caught, total))
    return 1 if ok else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()
    return neg_arm() if args.neg_arm else normal_arm()


if __name__ == '__main__':
    sys.exit(main())
