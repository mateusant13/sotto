"""Does a caption line arrive inside the budget? The ruler the contract named and the tree lacked.

The audit's §0 contract (2026-11-04) has two rulers: p95 caption latency and zero UI stalls. The
assembled report lists n-15 as "3 rulers missing", and one of them was named in the contract itself:
`_main/caption-budget-oracle.py` did not exist, so ruler (c) was CANNOT-MEASURE.

THE FIELD IS BIMODAL, and that is the whole reason this file exists rather than a one-line grep.
Measured by the runtime discovery on N=3,403 live rows (2026-10-13→11-04):

  * 76.7 % of lines: `queue_ms` < 100 ms — a new fragment closed the line and the panel's 1,500 ms
    deadline never fired. audio_ms p50 170 ms, over budget 2.9 %.
  * 22.4 % of lines: the deadline mode — median 1,504 ms, audio_ms p50 2,697 ms, over budget 100 %.

A p50 over that population is a statement about the sampling window (a 30-minute slice of the app's
death spiral gave 2,895 ms; a 42-hour parse gave 6 ms). So this oracle publishes the TWO MODES with
their RATES, the over-budget percentage of the whole population, and p95 — the numbers that survive a
change of window — and it refuses to sell a single p50 as the verdict.

  python _main/caption-budget-oracle.py [--log PATH] [--minutes N] [--json]
  python _main/caption-budget-oracle.py --neg-arm    # the planted corpora must be judged correctly

Verdict vocabulary is the skill's: PASS / FAIL / UNKNOWN-NOT-RUN / CANNOT-MEASURE. A series shorter
than `MIN_ROWS` is UNKNOWN-NOT-RUN, an absent log is CANNOT-MEASURE, and neither is green.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, '_main', 'webview-run.log')
BUDGET_MS_DEFAULT = 1500.0
MODE_SPLIT_MS = 100.0     # `queue_ms` at or above this is the deadline mode
MIN_ROWS = 30             # below this the verdict is UNKNOWN-NOT-RUN, never PASS
TARGET_P95_MS = 1500.0
TARGET_OVER_PCT = 5.0

# AS DUAS SUPERFICIES CONTAM (2026-11-04, MEDIDO). O overlay escreve
# `CAPTION_PAINT_LAG` e o painel escreve `CAPTION_APPLIED`; o painel e' a
# MAIORIA -- 22 233 linhas contra 1 567 no log inteiro (93,4 %) -- e um
# governador que so' le a primeira mede 6,6 % das pinturas da app.
ROW = re.compile(
    r'(?:CAPTION_PAINT_LAG|CAPTION_APPLIED)\s+(?:text=[^\n]*?\s)?'
    r'audio_ms=(\d+)\s+queue_ms=(\d+)\s+'
    r'budget_ms=(\d+)\s+over=(true|false)')


REUSED = re.compile(
    r'(?:CAPTION_PAINT_LAG|CAPTION_APPLIED)\s+.*?tap_reused=true')


def parse(text):
    """Every measurable row, as (audio_ms, queue_ms, budget_ms).

    A row marked `tap_reused=true` is NOT measurable and is dropped here on
    purpose: the age fields it omits (or carried) describe audio that already
    counted once, and 37,3 % of such rows held 85,2 % of the whole lag sum
    (measured 2026-11-04, 7 788 `CAPTION_IN`). `parse_counts` reports how many
    were dropped so a smaller N never looks like a quieter app.
    """
    return parse_counts(text)[0]


def parse_counts(text):
    rows = []
    reused = 0
    for line in text.splitlines():
        if REUSED.search(line):
            reused += 1
            continue
        m = ROW.search(line)
        if m:
            rows.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return rows, reused


_LAST_REUSED = 0


def read_log(path, minutes=None):
    global _LAST_REUSED
    _LAST_REUSED = 0
    if not os.path.isfile(path):
        return None
    with io.open(path, encoding='utf-8', errors='replace') as fh:
        lines = fh.readlines()
    if minutes:
        keep = []
        # The window is taken from the rows themselves, not from the file's
        # tail: a log whose last write is hours old must not produce a
        # "recent window" that is actually empty and silently green.
        stamps = []
        for line in lines:
            m = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', line)
            stamps.append(m.group(1) if m else None)
        known = [s for s in stamps if s]
        if not known:
            return []
        last = known[-1]
        import datetime
        edge = (datetime.datetime.strptime(last, '%Y-%m-%d %H:%M:%S')
                - datetime.timedelta(minutes=minutes))
        edge_s = edge.strftime('%Y-%m-%d %H:%M:%S')
        for line, stamp in zip(lines, stamps):
            if stamp and stamp >= edge_s:
                keep.append(line)
        lines = keep
    rows, _LAST_REUSED = parse_counts(''.join(lines))
    return rows


def quant(series, q):
    if not series:
        return None
    s = sorted(series)
    return s[min(len(s) - 1, int(q * len(s)))]


def judge(rows, budget_ms=BUDGET_MS_DEFAULT):
    """(verdict, detail dict). Pure, so the arms can drive it."""
    if rows is None:
        return 'CANNOT-MEASURE', {'why': 'log absent'}
    n = len(rows)
    if n < MIN_ROWS:
        return 'UNKNOWN-NOT-RUN', {'n': n, 'need': MIN_ROWS}
    audio = [r[0] for r in rows]
    queue = [r[1] for r in rows]
    deadline = [r[0] for r in rows if r[1] >= MODE_SPLIT_MS]
    fast = [r[0] for r in rows if r[1] < MODE_SPLIT_MS]
    over = sum(1 for a in audio if a > budget_ms)
    detail = {
        'n': n,
        'budget_ms': budget_ms,
        'p50': quant(audio, 0.50), 'p95': quant(audio, 0.95),
        'p99': quant(audio, 0.99), 'max': max(audio),
        'over_pct': round(100.0 * over / n, 1),
        'fast_pct': round(100.0 * len(fast) / n, 1),
        'fast_p50': quant(fast, 0.50),
        'fast_over_pct': (round(100.0 * sum(1 for a in fast if a > budget_ms)
                                / len(fast), 1) if fast else None),
        'deadline_pct': round(100.0 * len(deadline) / n, 1),
        'deadline_p50': quant(deadline, 0.50),
        'deadline_over_pct': (round(100.0 * sum(1 for a in deadline
                                                if a > budget_ms)
                                    / len(deadline), 1) if deadline else None),
        'queue_p50': quant(queue, 0.50),
    }
    ok = detail['p95'] <= TARGET_P95_MS and detail['over_pct'] <= TARGET_OVER_PCT
    return ('PASS' if ok else 'FAIL'), detail


def render(verdict, d):
    if verdict == 'CANNOT-MEASURE':
        return [f'CAPTION-BUDGET CANNOT-MEASURE {d["why"]}']
    if verdict == 'UNKNOWN-NOT-RUN':
        return [f'CAPTION-BUDGET UNKNOWN-NOT-RUN n={d["n"]} need>={d["need"]}']
    return [
        f'CAPTION-BUDGET population n={d["n"]} budget_ms={d["budget_ms"]:.0f} '
        f'verdict={verdict}',
        f'  ALL      p50={d["p50"]} p95={d["p95"]} p99={d["p99"]} max={d["max"]} '
        f'over={d["over_pct"]}% (target p95<={TARGET_P95_MS:.0f} and '
        f'over<={TARGET_OVER_PCT:.0f}%)',
        f'  FAST     rate={d["fast_pct"]}% p50={d["fast_p50"]} '
        f'over={d["fast_over_pct"]}%   (queue_ms<{MODE_SPLIT_MS:.0f})',
        f'  DEADLINE rate={d["deadline_pct"]}% p50={d["deadline_p50"]} '
        f'over={d["deadline_over_pct"]}%   (queue_ms>={MODE_SPLIT_MS:.0f})',
        (f'  EXCLUDED {d["reused"]} row(s) marked tap_reused=true -- the same '
         'audio attributed twice; not a latency'
         if d.get('reused') else '  EXCLUDED 0 rows marked tap_reused=true'),
        '  A p50 over this field is a statement about the window: the two modes '
        'and their rates are the verdict.',
    ]


def arms():
    """Each arm is a population with a known answer. A ruler that cannot be made RED is decoration."""
    res = {}
    healthy = [(120 + i % 60, 3) for i in range(200)]
    v, d = judge(healthy)
    res['healthy_zero_red'] = (v == 'PASS' and d['over_pct'] == 0.0)
    print(f'ARM 1 healthy population     -> {v} over={d["over_pct"]}% p95={d["p95"]}')

    deadline = [(2600, 1504) for _ in range(60)]
    v, d = judge(deadline)
    res['deadline_mode_red'] = (v == 'FAIL' and d['deadline_pct'] == 100.0)
    print(f'ARM 2 all lines wait out hold-> {v} deadline_rate={d["deadline_pct"]}% '
          f'over={d["over_pct"]}%')

    mixed = [(200, 4) for _ in range(77)] + [(2700, 1504) for _ in range(23)]
    v, d = judge(mixed)
    res['bimodal_reported'] = (v == 'FAIL'
                               and abs(d['fast_pct'] - 77.0) < 0.6
                               and abs(d['deadline_pct'] - 23.0) < 0.6
                               and d['over_pct'] == 23.0)
    print(f'ARM 3 bimodal 77/23          -> {v} fast={d["fast_pct"]}% '
          f'deadline={d["deadline_pct"]}% over={d["over_pct"]}%')

    v, d = judge([(100, 1)] * 5)
    res['short_is_unknown'] = (v == 'UNKNOWN-NOT-RUN')
    print(f'ARM 4 five rows              -> {v} (never PASS)')

    v, d = judge(None)
    res['absent_is_cannot_measure'] = (v == 'CANNOT-MEASURE')
    print(f'ARM 5 absent log             -> {v} (never 0, never green)')

    # A budget tighter than the population must flip the same healthy corpus red:
    # that is the proof the threshold is read, and not decoration beside it.
    v, _ = judge(healthy, budget_ms=50)
    res['threshold_is_read'] = (v == 'FAIL')
    print(f'ARM 6 same corpus, budget=50 -> {v} (threshold is read)')

    # ARM 6-bis: the PANEL surface must be readable. It is 93.4 % of the app's
    # paints, and a ruler that only parses the overlay measures 6.6 % of them.
    panel = '\n'.join(
        f'2026-11-04 10:00:{i % 60:02d}.000 sotto: CAPTION_APPLIED text="l{i}" '
        f'count={i} kind=partial aged_kind=transport audio_ms={200 + i % 50} '
        f'queue_ms=4 budget_ms=1500 over=false' for i in range(40))
    rows_p, reused_p = parse_counts(panel)
    v, d = judge(rows_p)
    res['panel_surface_read'] = (len(rows_p) == 40 and v == 'PASS')
    print(f'ARM 6bis 40 CAPTION_APPLIED  -> rows={len(rows_p)} {v} '
          f'(want 40, PASS: the panel is the majority surface)')

    # ARM 7-9: the predicate that decides whether a paint describes NEW audio,
    # run as it ships. Without it `audio_ms` counts one block many times.
    aged = _load_aged()
    if aged is None:
        res['aged_predicate_importable'] = False
        print('ARM 7 predicate              -> NOT IMPORTABLE')
        return res
    seq = [1000, 1000, 2000, 2000, 2000, 3000]
    last = None
    counted = 0
    for tap in seq:
        if aged(tap, last):
            counted += 1
            last = tap
    res['tap_counts_once'] = (counted == 3)
    print(f'ARM 7 taps {seq} -> counted={counted} (want 3: once per tap)')
    res['no_tap_is_not_aged'] = (aged(None, None) is False and aged(0, None) is False)
    print(f'ARM 8 absent tap             -> aged=None/0 -> {aged(None, None)}/'
          f'{aged(0, None)} (want False)')
    res['string_tap_works'] = (aged('4000', 3000) is True)
    print(f'ARM 9 tap as string "4000"   -> {aged("4000", 3000)} (want True)')

    # ARM 10: the EMIT SITE, driven for real. A static arm proves the predicate;
    # this proves the handler in `app/webview/sotto_webview.py` obeys it. Four
    # paints over two taps must publish two measurable rows and two `tap_reused`
    # rows -- and no negative age, which would enter the series as a fast line.
    panel = _panel_arms()
    res['panel_emit_site_obeys'] = panel.get('ok', False)
    print(f'ARM 10 panel emit site       -> {panel.get("detail", "NOT RUN")}')
    return res


def _panel_arms():
    """Drive `SottoHost._caption_applied` with a fake shell. No window, no device."""
    import types
    sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
    try:
        import sotto_webview as S
    except Exception as exc:                      # noqa: BLE001 -- reported, not hidden
        return {'ok': False, 'detail': f'import failed: {exc!r}'}
    host_cls = None
    for name, obj in vars(S).items():
        if isinstance(obj, type) and '_caption_applied' in vars(obj):
            host_cls = obj
            break
    if host_cls is None:
        return {'ok': False, 'detail': 'no class carries _caption_applied'}

    class FakeShell(object):
        CAPTION_BUDGET_MS = S.SottoShell.CAPTION_BUDGET_MS
        CAPTION_HOLD_BAND_MS = S.SottoShell.CAPTION_HOLD_BAND_MS

        def __init__(self):
            self.caption_log = []
            self._last_push_tap_ms = None
            self._last_push_final = False
            self._last_push_at = None
            self._caption_lag_blown = 0
            self.notes = []

        def _caption_lag_note(self, *a, **k):
            self.notes.append(k.get('kind'))

    lines = []
    real_log = S.log
    S.log = lambda m, *a, **k: lines.append(m)
    try:
        fake = types.SimpleNamespace()
        fake._shell = FakeShell()
        handler = types.MethodType(vars(host_cls)['_caption_applied'], fake)
        now = int(time.time() * 1000.0) - 300
        for tap, text in ((now, 'a'), (now, 'ab'), (now + 500, 'abc'),
                          (now + 500, 'abcd')):
            fake._shell._last_push_tap_ms = tap
            fake._shell._last_push_at = time.time() - 0.01
            handler({'text': text})
    finally:
        S.log = real_log
    measurable = [x for x in lines if 'audio_ms=' in x]
    reused = [x for x in lines if 'tap_reused=true' in x]
    negative = [x for x in measurable if 'audio_ms=-' in x]
    ok = (len(lines) == 4 and len(measurable) == 2 and len(reused) == 2
          and not negative)
    return {'ok': ok,
            'detail': f'rows={len(lines)} measurable={len(measurable)} '
                      f'reused={len(reused)} negative={len(negative)} '
                      f'(want 4/2/2/0)'}


def _load_aged(path=None):
    """`caption_lag_aged` as it ships, from the shell file, without starting it."""
    import importlib.util
    path = path or os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
    if not os.path.isfile(path):
        return None
    src = io.open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'^def caption_lag_aged\(.*?(?=^def )', src, re.S | re.M)
    if not m:
        return None
    ns = {}
    exec(compile(m.group(0), path, 'exec'), ns)
    return ns.get('caption_lag_aged')


def neg_arm():
    """Drive the REAL reader over copies of a corpus, mutating one field at a time."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix='capbudget-', dir=os.environ.get('TMPDIR')
                          or os.environ.get('TEMP') or '.')
    good = '\n'.join(
        f'2026-11-04 10:00:{i % 60:02d}.000 sotto: CAPTION_PAINT_LAG audio_ms={120 + i % 40} '
        f'queue_ms=3 budget_ms=1500 over=false text="linha {i}"'
        for i in range(80))
    mutants = {
        # A dose that actually crosses the threshold: the first version of this
        # mutant replaced 'audio_ms=1' with 'audio_ms=3' inside 120..159, which
        # stays well under the budget and proves nothing about the ruler.
        'audio_past_budget': re.sub(r'audio_ms=\d+', 'audio_ms=3000', good),
        'queue_past_split': good.replace('queue_ms=3', 'queue_ms=1504'),
        'rows_blanked': re.sub(r'CAPTION_PAINT_LAG', 'NOT_A_ROW',
                               good),
    }
    caught = 0
    total = 0
    path = os.path.join(tmp, 'corpus.log')
    with io.open(path, 'w', encoding='utf-8') as fh:
        fh.write(good)
    base_v, base_d = judge(read_log(path))
    print(f'BASELINE {base_v} over={base_d.get("over_pct")}% p95={base_d.get("p95")}')
    for name, text in mutants.items():
        total += 1
        with io.open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        rows = read_log(path)
        v, d = judge(rows)
        # The mutant is caught when the verdict or the published composition
        # moves in the direction the mutation names.
        if name == 'audio_past_budget':
            ok = (v == 'FAIL' or (d.get('over_pct') or 0) > (base_d.get('over_pct') or 0))
        elif name == 'queue_past_split':
            ok = (abs((d.get('deadline_pct') or 0) - 100.0) < 0.6)
        else:
            ok = (v == 'UNKNOWN-NOT-RUN')
        caught += int(ok)
        print(f'MUTANT {name}: {"CAUGHT" if ok else "NOT-CAUGHT"} verdict={v} '
              f'over={d.get("over_pct")} deadline={d.get("deadline_pct")}')
    # MUTANT of the shipped predicate: a copy of the shell with the identity
    # check disarmed must make ARM 7 count six instead of three. Mutating the
    # corpus would only prove the arithmetic of the arm.
    shell = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
    if os.path.isfile(shell):
        total += 1
        src = io.open(shell, encoding='utf-8', errors='replace').read()
        mutant = src.replace('    return tap != last_counted',
                             '    return True', 1)
        if mutant == src:
            ok = False
            print('MUTANT predicate_disarmed: NEG-ARM IMPOSSIVEL (a ancora '
                  '`return tap != last_counted` desapareceu do shell)')
        else:
            mpath = os.path.join(tmp, 'shell_mutant.py')
            with io.open(mpath, 'w', encoding='utf-8') as fh:
                fh.write(mutant)
            fn = _load_aged(mpath)
            counted = 0
            last = None
            for tap in (1000, 1000, 2000, 2000, 2000, 3000):
                if fn and fn(tap, last):
                    counted += 1
                    last = tap
            ok = (counted == 6)
            print(f'MUTANT predicate_disarmed: {"CAUGHT" if ok else "NOT-CAUGHT"} '
                  f'counted={counted} (want 6 = the defect)')
        caught += int(ok)
    print(f'NEG-ARM SUMMARY cases={total} caught={caught}')
    print('NEG-ARM: PASS' if caught == total else 'NEG-ARM: FAIL')
    return 1 if caught == total else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--log', default=LOG)
    ap.add_argument('--minutes', type=int, default=0)
    ap.add_argument('--budget-ms', type=float, default=BUDGET_MS_DEFAULT)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--neg-arm', action='store_true')
    a = ap.parse_args(argv)
    if a.neg_arm:
        return neg_arm()
    rows = read_log(a.log, a.minutes or None)
    verdict, d = judge(rows, a.budget_ms)
    d['reused'] = _LAST_REUSED
    if a.json:
        print(json.dumps({'verdict': verdict, **d}, indent=1))
    for line in render(verdict, d):
        print(line)
    a = arms()
    bad = [k for k, v in a.items() if not v]
    if bad:
        print('ARM FAIL ' + ' '.join(bad))
        return 1
    print('VERDICT:', verdict)
    return 0 if verdict in ('PASS', 'UNKNOWN-NOT-RUN', 'CANNOT-MEASURE') else 1


if __name__ == '__main__':
    sys.exit(main())
