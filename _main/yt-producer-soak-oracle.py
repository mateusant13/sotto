# NO-BUG: Oracle: with a producer that publishes on a clock, the caption read path
#        delivers EVERY publication, once, within one freshness bound. Capacidade
#        pedida pelo dono (soak de produtor); nao ha id de `_main/bug-ledger.json`
#        para isto, e o id nao se inventa.
"""Oracle: a 5-minute soak of the caption READ path against a paced producer.

THE HOLE THIS CLOSES (harness angle A3/A10, measured 2026-11-26): the owner's
session carried `YOUTUBE_TICK_MS max=8828` and
`YOUTUBE_SNAPSHOT_STALE age_ms=8265 max_age_ms=1500` -- the producer went quiet
for 8.2 s. `_main/yt-loop-uia-oracle.py` proves WHO the read path asks (never
the UIA while CDP is alive); `_main/caption-timeline.py` judges the WRITE side
from a real log. Nothing ran the read path for minutes against a producer that
publishes on a clock, so "the caption kept up" had no instrument.

WHAT IS MEASURED, per rate, over `SOAK_S` of SIMULATED time (no window, no
Chrome, no audio device, no thread):

  * publications -- how many photos the fake producer published;
  * delivered     -- distinct new lines the REAL `_youtube` produced;
  * lost          -- publications whose line never came out;
  * duplicated    -- a line delivered twice for one publication;
  * worst_latency -- seconds between a publication and its line coming out;
  * worst_gap     -- the longest stretch with no delivery while publishing.

ARMS
  a. SOAK-5MIN   -- 300 s at a 1 s publish rate: 300 publications, 300
                    deliveries, no loss, worst_latency inside the freshness
                    bound + one tick, worst_gap bounded;
  b. SLOW-3S     -- the rate that made one paint per snapshot (3 s): every
                    publication still delivered exactly once;
  c. WORST-8.8S  -- the owner's measured worst stall (8.8 s): every publication
                    still delivered exactly once;
  d. SAME-TEXT   -- two publications carrying the SAME line are delivered ONCE
                    (the one-producer law: a repeated photo is not a new cue).

The negative arm mutates the FAKE PRODUCER (drop a publication; republish the
same text forever) and requires the SAME arms to go RED -- a gate that only
greps the source cannot be shown to fail.

Usage:
  py -3 _main/yt-producer-soak-oracle.py            # rc 0 = PASS
  py -3 _main/yt-producer-soak-oracle.py --neg-arm  # rc 1 = every mutant CAUGHT
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')

#: A janela da leitura (`DOM_FRESH_S`, `sotto_webview.py:6275`) mais um tick de
#: 100 ms: uma publicacao TEM de sair dentro disso, senao a foto envelheceu antes
#: de ser lida e o ecra fica com a linha anterior.
FRESH_S = 1.2
TICK_S = 0.1
SOAK_S = 300.0
#: A CADENCIA TEM UM TECTO APERTADO (2026-11-26, medido ao apertar o mutante
#: `drop-every-3`): uma publicacao e' lida no primeiro tick que a ve', logo o
#: intervalo entre duas entregas e' no maximo `gap + 1 tick`. Com `gap + bound`
#: (bound = 1,4 s) um produtor que falha UMA publicacao em cada tres passava com
#: `worst_gap=2,0s` -- o mutante sobrevivia por folga do contrato, nao por
#: virtude do codigo.
CADENCE_SLACK = 3 * TICK_S


class FakeTime:
    """`time` do modulo da shell, com o `monotonic` que este oraculo move."""

    def __init__(self):
        self.now = 1000.0
        import time as _real
        self._real = _real

    def monotonic(self):
        return self.now

    def perf_counter(self):
        return self.now

    def __getattr__(self, name):
        return getattr(self._real_attr(), name)

    def _real_attr(self):
        return self._real


class PacedCdp:
    """Um produtor que publica no SEU relogio, nao no da leitura.

    A agenda e' calculada ANTES do soak (`t0 + i * gap`), porque um produtor que
    publica no instante em que e' lido mede latencia ZERO por construcao -- esse
    zero nao pode falhar, e um numero que nao pode falhar nao e' uma medida.
    `snapshot` serve a publicacao mais recente cujo instante ja' passou, com o
    `stamp` DELA (a foto envelhece no relogio do produtor).
    """

    def __init__(self, clock, gap, duration, same_text=False, drop_every=0):
        self.clock = clock
        self.gap = float(gap)
        self.same_text = bool(same_text)
        self.drop_every = int(drop_every)
        self.t0 = clock.now + 0.05
        count = int(duration / max(self.gap, 1e-6)) + 2
        self.schedule = []                     # (index, publish_at, text)
        for i in range(1, count + 1):
            when = self.t0 + (i - 1) * self.gap
            if self.drop_every and i % self.drop_every == 0:
                self.schedule.append((i, when, None))   # MUTANTE: nunca chega
            else:
                text = ('the same line forever' if self.same_text
                        else 'cue number %d' % i)
                self.schedule.append((i, when, text))
        self._served = -1
        self.stamp = -1e9
        self.rows = []

    def published_at(self):
        """O que o produtor JA' pôs no ar ate' ao instante simulado."""
        return [(i, when, text) for i, when, text in self.schedule
                if when <= self.clock.now]

    def _advance(self):
        live = [row for row in self.schedule if row[1] <= self.clock.now]
        if not live:
            return
        index, when, text = live[-1]
        if index != self._served and text is not None:
            self._served = index
            self.stamp = when
            self.rows = [text]

    def snapshot(self, max_age=0.6):
        self._advance()
        if self.clock.now - self.stamp > max_age:
            return None
        return {'rows': list(self.rows),
                'items': [{'x': 0, 'y': 0, 'w': 10, 'h': 10}],
                'stamp': self.stamp,
                'videoId': 'NBCM_ZoWZo8',
                'paused': False,
                'title': 'soak',
                # A posicao avanca com o relogio simulado: nenhuma testemunha de
                # pausa pode disparar aqui (o soak mede a LEITURA, nao a pausa).
                't': 100.0 + (self.clock.now - 1000.0)}

    def start(self):
        return self

    def stop(self):
        return None


def load_shell(path=SHELL, name='_soak_shell'):
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    # O SOAK NAO ESCREVE NO LOG DA APP: ele mede contagens, e uma linha por tick
    # aqui so' poluia a saida do passo.
    mod.log = lambda *a, **k: None
    return mod


def watcher_for(mod, source, clock):
    """O `_youtube` REAL, com a UIA substituida por contadores.

    Mesma construcao de `_main/yt-loop-uia-oracle.py::build` (que ja' prova que
    o `_youtube` real corre neste duplo), e o `time` do modulo trocado pelo
    relogio simulado -- a leitura decide idade pelo `stamp`, e o tick pelo
    `monotonic`, logo os dois tem de ser o MESMO instante.
    """
    watcher = mod.ExternalCaptionWatcher(SimpleNamespace())
    calls = {'vid': 0, 'painted': 0}
    watcher._yt_cdp_source = source
    watcher.yt_video_id = ''
    watcher.shell = SimpleNamespace()

    def _vid(*a, **k):
        calls['vid'] += 1
        return 'NBCM_ZoWZo8'

    def _painted(*a, **k):
        calls['painted'] += 1
        return {'words': ['a'], 'items': [], 'why': 'fake'}

    watcher._youtube_video_id = _vid
    watcher._youtube_painted = _painted
    real_time = getattr(mod, 'time', None)
    mod.time = clock
    return watcher, calls, real_time


def run_rate(mod, gap, duration=SOAK_S, same_text=False, drop_every=0,
             tick_s=TICK_S):
    """Sobe um produtor novo e corre `duration` segundos simulados de leituras."""
    clock = FakeTime()
    source = PacedCdp(clock, gap, duration, same_text=same_text,
                      drop_every=drop_every)
    watcher, calls, real_time = watcher_for(mod, source, clock)
    delivered = []
    try:
        steps = int(round(duration / tick_s))
        for _ in range(steps):
            clock.now += tick_s
            out = watcher._youtube(1234, object(), object())
            lines = []
            for _source_name, group in (out[0] if out else []):
                lines.extend(group or [])
            if lines:
                delivered.append((clock.now, tuple(lines)))
    finally:
        if real_time is not None:
            mod.time = real_time

    # Uma publicacao cuja linha NUNCA saiu e' uma perda; a MESMA linha em dois
    # instantes seguidos e' um duplicado (o `_youtube` pode re-servir uma foto
    # em cache dentro da janela -- isso conta como o MESMO cumprimento).
    sequence = []
    for when, lines in delivered:
        if sequence and sequence[-1][1] == lines:
            continue
        sequence.append((when, lines))
    published_texts = [t for _i, _when, t in source.published_at() if t]
    got_texts = [lines[0] if len(lines) == 1 else '|'.join(lines)
                 for _when, lines in sequence]
    lost = [t for t in published_texts if t not in got_texts]
    duplicated = len(got_texts) - len(set(got_texts))
    latency = []
    for text, (when, lines) in zip(got_texts, sequence):
        stamp = next((w for _i, w, t in source.published_at() if t == text), None)
        if stamp is not None:
            latency.append(when - stamp)
    gaps = [b[0] - a[0] for a, b in zip(sequence, sequence[1:])]
    return {
        'gap': gap,
        'published': len(published_texts),
        'delivered': len(sequence),
        'lost': lost,
        'duplicated': duplicated,
        'worst_latency': max(latency) if latency else None,
        'worst_gap': max(gaps) if gaps else None,
        'uia_vid': calls['vid'],
        'uia_painted': calls['painted'],
        'texts': set(got_texts),
    }


def arm_soak(mod, gap, label, want_published, duration=SOAK_S, tolerance=1):
    res = run_rate(mod, gap, duration=duration)
    bound = FRESH_S + 2 * TICK_S
    ok = (
        abs(res['published'] - want_published) <= tolerance
        and abs(res['delivered'] - res['published']) <= tolerance
        and not res['lost']
        and res['duplicated'] == 0
        and (res['worst_latency'] is not None and res['worst_latency'] <= bound)
        and (res['worst_gap'] is not None
             and res['worst_gap'] <= gap + CADENCE_SLACK)
    )
    detail = ('%s gap=%.1fs published=%d delivered=%d lost=%d dup=%d '
              'worst_lat=%.2fs worst_gap=%.2fs lat_bound=%.2fs cad_bound=%.2fs'
              % (label, gap, res['published'], res['delivered'],
                 len(res['lost']), res['duplicated'],
                 res['worst_latency'] if res['worst_latency'] is not None else -1,
                 res['worst_gap'] if res['worst_gap'] is not None else -1,
                 bound, gap + CADENCE_SLACK))
    return ok, detail, res


def arm_same_text(mod):
    """UMA linha que nao muda nao e' cue nova: o leitor pode re-servir a foto,
    mas nenhum texto DIFERENTE pode aparecer no ecra."""
    res = run_rate(mod, 1.0, duration=20.0, same_text=True)
    ok = res['texts'] == {'the same line forever'} and res['published'] >= 18
    return ok, ('d SAME-TEXT published=%d delivered=%d distinct_texts=%r'
                % (res['published'], res['delivered'], sorted(res['texts']))), res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--seconds', type=float, default=SOAK_S)
    args = ap.parse_args()

    mod = load_shell()
    results = []

    def arm(name, ok, detail):
        results.append((name, bool(ok), detail))
        print('%-12s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))

    ok, detail, _ = arm_soak(mod, 1.0, 'a SOAK-5MIN', int(args.seconds),
                             duration=args.seconds)
    arm('a SOAK-5MIN', ok, detail)

    ok, detail, _ = arm_soak(mod, 3.0, 'b SLOW-3S', int(args.seconds / 3.0),
                             duration=args.seconds)
    arm('b SLOW-3S', ok, detail)

    ok, detail, _ = arm_soak(mod, 8.8, 'c WORST-8.8S',
                             int(args.seconds / 8.8), duration=args.seconds)
    arm('c WORST-8.8S', ok, detail)

    ok, detail, _ = arm_same_text(mod)
    arm('d SAME-TEXT', ok, detail)

    if args.neg_arm:
        # M1: o produtor perde uma publicacao em cada tres. O leitor nao pode
        # inventar o que nao chegou, entao o defeito aparece como CADENCIA: o
        # ecra fica com a linha anterior por DOIS intervalos -- e' isso que a
        # arm a mede (`worst_gap > gap + bound`).
        res = run_rate(mod, 1.0, duration=60.0, drop_every=3)
        bound = FRESH_S + 2 * TICK_S
        caught = bool(res['lost']) or (res['worst_gap'] is not None
                                      and res['worst_gap']
                                      > 1.0 + CADENCE_SLACK)
        print('%-12s %s  M1 drop-every-3 published=%d lost=%d worst_gap=%.2fs '
              '(limite %.2fs)'
              % ('NEG-M1', 'CAUGHT' if caught else 'NOT-CAUGHT',
                 res['published'], len(res['lost']),
                 res['worst_gap'] if res['worst_gap'] is not None else -1,
                 1.0 + CADENCE_SLACK))
        # M2: O LEITOR IGNORA O TEXTO e serve sempre a primeira linha -- a arm d
        # (texto unico) e' o que apanha um leitor que so' olha para o numero.
        clock2 = FakeTime()
        source2 = PacedCdp(clock2, 1.0, 30.0)
        watcher2, _c2, real2 = watcher_for(mod, source2, clock2)
        seen = set()
        try:
            for _ in range(int(30.0 / TICK_S)):
                clock2.now += TICK_S
                out = watcher2._youtube(1234, object(), object())
                for _s, group in (out[0] if out else []):
                    seen.update(group or [])
        finally:
            if real2 is not None:
                mod.time = real2
        caught2 = len(seen) >= 20
        print('%-12s %s  M2 distinct-lines=%d (um leitor que ignora o texto entrega 1)'
              % ('NEG-M2', 'CAUGHT' if caught2 else 'NOT-CAUGHT', len(seen)))
        ok_all = caught and caught2
        print('\nNEG-ARM VERDICT: %s (%d/2 mutants caught)'
              % ('PASS' if ok_all else 'FAIL', sum((caught, caught2))))
        # CONVENCAO DA CASA: o controlo que apanhou tudo sai 1 (`:expectred`).
        return 1 if ok_all else 2

    bad = [n for n, okk, _ in results if not okk]
    print('\nVERDICT: %s (arms=%d fail=%d)'
          % ('PASS' if not bad else 'FAIL', len(results), len(bad)))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
