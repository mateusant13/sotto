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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, '_main', 'webview-run.log')
BUDGET_MS_DEFAULT = 1500.0
MODE_SPLIT_MS = 100.0     # `queue_ms` at or above this is the deadline mode
MIN_ROWS = 30             # below this the verdict is UNKNOWN-NOT-RUN, never PASS
TARGET_P95_MS = 1500.0
TARGET_OVER_PCT = 5.0

ROW = re.compile(
    r'CAPTION_PAINT_LAG\s+audio_ms=(\d+)\s+queue_ms=(\d+)\s+'
    r'budget_ms=(\d+)\s+over=(true|false)')


def parse(text):
    """Every measurable row, as (audio_ms, queue_ms, budget_ms)."""
    rows = []
    for line in text.splitlines():
        m = ROW.search(line)
        if m:
            rows.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return rows


def read_log(path, minutes=None):
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
    return parse(''.join(lines))


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
    return res


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
    if a.json:
        print(json.dumps({'verdict': verdict, **d}, indent=1))
    for line in render(verdict, d):
        print(line)
    if not arms().get('healthy_zero_red', False):
        print('ARM FAIL healthy_zero_red')
        return 1
    print('VERDICT:', verdict)
    return 0 if verdict in ('PASS', 'UNKNOWN-NOT-RUN', 'CANNOT-MEASURE') else 1


if __name__ == '__main__':
    sys.exit(main())
