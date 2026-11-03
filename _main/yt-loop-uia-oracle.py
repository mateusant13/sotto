"""Oracle: with the CDP door open, the caption loop asks NOTHING to UIA.

THE MEASUREMENT THIS EXISTS FOR (owner's live session, 2026-11-03):

    EXTERNAL_CAPTIONS_READ_MS ms=46766.0 phases={'target': 0.0, 'source': 0.0}
    EXTERNAL_CAPTIONS_READ_MS ms=62234.0 phases={'target': 0.0, 'source': 0.0}

Both ticks are cheap until the `source` mark and then lose 46 s / 62 s with no
further phase recorded -- the block is between `_yt_mark('source')` and
`_yt_mark('vid')`, which is `_youtube_video_id` (a UIA `edit_values` scan of the
Chrome address bar: 94-109 ms on a good tick, tens of seconds on a bad one).
The owner's complaint is exactly that: "um extrair legenda do YouTube e dar
display na minha tela nao era pra ser nem o minimo de pesado".

THE RULE THIS PROVES. While a CDP source is attached, the video id comes from
the snapshot (`videoId`) and the lines come from the snapshot (`rows`). The UIA
scan is a FALLBACK for when there is no CDP at all -- never a second opinion.

ARMS
  1. DOM-FAST   -- a fresh snapshot with rows: `_youtube` returns the two lines
                   in under 50 ms, and NEITHER `_youtube_video_id` NOR
                   `_youtube_painted` was called;
  2. NO-SNAP    -- source attached, snapshot momentarily absent on a video we
                   already know: the tick returns nothing and STILL does not ask
                   UIA -- the next snapshot is ~80 ms away, a 46 s scan is not;
  2b. BOOTSTRAP -- no id known yet: exactly ONE UIA read, because the id is what
                   lets the CDP source pick our tab when two `watch` tabs are
                   open (`state=ambiguous` otherwise, measured 2026-11-03);
  3. NO-CDP     -- no source at all: `_youtube_video_id` IS called (the
                   fallback is alive -- this arm is what stops the fix from
                   becoming "UIA never runs").

Usage:
  py -3 _main/yt-loop-uia-oracle.py             # the working tree
  py -3 _main/yt-loop-uia-oracle.py --neg-arm   # the UIA fallback put back
                                                # under a live CDP -> must be RED
"""
import argparse
import importlib.util
import os
import sys
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
MUTANT = os.path.join(os.path.dirname(SHELL), '_uia-neg-shell.py')

#: The two lines the neg arm re-inserts: with a source attached and an id already
#: known, ask the accessibility tree anyway (the defect, restored).
#:
#: RE-ANCHORED 2026-11-03: the cure's `return` line changed shape (`return '',
#: _src, True` -- the id comes from the snapshot now), so the old anchor no longer
#: matched the file and the control reported `NEG-ARM IMPOSSIVEL: ancora ausente`
#: with rc=2. An anchor is a claim about the source; it ages like one.
#: RE-ANCHORED AGAIN 2026-11-03: a cura do ALVO MORTO meteu 20 linhas dentro
#: do ramo rapido, e o corpo passou a depender da aba viva. O que o mutante tem
#: de fazer e' so' isto: o ramo rapido deixa de ser tomado, e o tick cai na UIA.
_A = ("            if _src and _src is not False and "
      "getattr(self, 'yt_video_id', ''):\n")
_I = ("            if False:  # MUTANT: cai na UIA\n")
#: The shell is CRLF; the anchor is built in the file's own line endings.
ANCHOR = _A.replace("\n", "\r\n")
INJECT = _I.replace("\n", "\r\n")

BUDGET_MS = 50.0
ROWS = ['three errors that are error one, error', 'two, and error three.']


def load_shell(path, name):
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeCdp:
    """`youtube_cdp_source.CdpCaptionSource` as far as the loop can tell."""

    def __init__(self, rows=ROWS, age=0.0, video_id='NBCM_ZoWZo8'):
        self.rows = list(rows)
        self.video_id = video_id
        self.stamp = time.monotonic() - age
        self.reads = 0

    def snapshot(self, max_age=0.6):
        self.reads += 1
        if time.monotonic() - self.stamp > max_age:
            return None
        return {'rows': list(self.rows),
                'items': [{'x': 0, 'y': 0, 'w': 10, 'h': 10}],
                'stamp': self.stamp,
                'videoId': self.video_id, 'paused': False, 'title': 'T'}

    def start(self):
        return self

    def stop(self):
        return None


def build(mod, source):
    """The REAL watcher, with the two UIA entries counted instead of run."""
    watcher = mod.ExternalCaptionWatcher(SimpleNamespace())
    calls = {'vid': 0, 'painted': 0}
    watcher._yt_cdp_source = source

    def _vid(*a, **k):
        calls['vid'] += 1
        return 'NBCM_ZoWZo8'

    def _painted(*a, **k):
        calls['painted'] += 1
        return {'words': ['a'], 'items': [], 'why': 'fake'}

    watcher._youtube_video_id = _vid
    watcher._youtube_painted = _painted
    watcher.shell = SimpleNamespace()
    watcher.yt_video_id = ''
    return watcher, calls


def tick(watcher):
    t0 = time.perf_counter()
    out = watcher._youtube(1234, object(), object())
    ms = (time.perf_counter() - t0) * 1000.0
    return ms, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    shell = SHELL
    if args.neg_arm:
        src = open(SHELL, encoding='utf-8', newline='').read()
        if ANCHOR not in src:
            print('NEG-ARM IMPOSSIVEL: ancora ausente (primeiro trecho:%r)'
                  % src[src.find('if _src and _src is not False'):][:90])
            return 2
        open(MUTANT, 'w', encoding='utf-8', newline='').write(
            src.replace(ANCHOR, INJECT, 1))
        shell = MUTANT
    mod = load_shell(shell, '_uia_oracle_shell')

    results = []

    def arm(name, ok, detail):
        results.append((name, bool(ok), detail))
        print('%-10s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))

    # 1. DOM-FAST
    w, calls = build(mod, FakeCdp())
    ms, out = tick(w)
    rows = out[0][0][1] if out and out[0] else []
    arm('DOM-FAST', ms < BUDGET_MS and rows == ROWS
        and calls['vid'] == 0 and calls['painted'] == 0,
        'ms=%.1f rows=%d uia_vid=%d uia_painted=%d'
        % (ms, len(rows), calls['vid'], calls['painted']))

    # 2. NO-SNAP: an attached source whose snapshot has aged out, ON A VIDEO WE
    #    ALREADY KNOW (the steady state -- the id is learned once, on the first
    #    tick, precisely so the source can pick the tab when two are open).
    w, calls = build(mod, FakeCdp(age=9.0))
    w.yt_video_id = 'NBCM_ZoWZo8'
    ms, out = tick(w)
    arm('NO-SNAP', out[0] == [] and calls['vid'] == 0,
        'ms=%.1f out=%r uia_vid=%d' % (ms, out[0], calls['vid']))

    # 2b. BOOTSTRAP: no id known yet -- exactly ONE UIA read, and never more
    #     (it is what lets the CDP source pick OUR tab out of two `watch` tabs).
    w, calls = build(mod, FakeCdp(age=9.0))
    tick(w)
    tick(w)
    tick(w)
    arm('BOOTSTRAP', calls['vid'] == 1,
        'uia_vid=%d em 3 ticks (o id aprende-se uma vez)' % calls['vid'])

    # 3. NO-CDP: the fallback must still exist. The env var is what says
    #    "there is no CDP door" now that the door opens before the id
    #    (`_yt_cdp_ensure`), otherwise this arm would attach to the real Chrome.
    os.environ['SOTTO_YT_CDP'] = '0'
    w, calls = build(mod, None)
    ms, out = tick(w)
    os.environ.pop('SOTTO_YT_CDP', None)
    arm('NO-CDP', calls['vid'] >= 1,
        'ms=%.1f uia_vid=%d (fallback vivo)' % (ms, calls['vid']))

    if args.neg_arm:
        try:
            os.remove(MUTANT)
        except OSError:
            pass

    bad = [n for n, ok, _ in results if not ok]
    if args.neg_arm:
        # The mutant must be caught by NO-SNAP (that is the arm it changes).
        caught = 'NO-SNAP' in bad
        print('NEG-ARM %s -- mutante derrubou: %s'
              % ('PASS (RED as designed)' if caught else 'FAIL',
                 ', '.join(bad) or 'nada'))
        # CONTRATO DA BATERIA: rc=1 = o mutante foi apanhado.
        print('NEG-ARM: %s' % ('PASS' if caught else 'FAIL'))
        return 1 if caught else 0
    print('VERDICT: %s (arms=%d fail=%d)'
          % ('PASS' if not bad else 'FAIL', len(results), len(bad)))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
