"""Attribute a silent window: the MACHINE stalled, or only this shell did.

The question this answers, in the owner's words: *"subtitles worked for like 2
seconds and then froze"*. The shell appends one line per event to
`_main/webview-run.log`; a hole in that file has two very different causes and
they need different fixes:

  * the machine stopped scheduling (paging/CPU storm/VM pause) — the process
    cannot fix the host, but the product can stop depending on an exact cadence;
  * the shell's own GIL was held (a COM call, a slow read) — that IS the
    product's bug.

A thread inside the shell cannot tell the two apart: it stalls with the process.
`app/webview/stall_heartbeat.py` is a separate process writing 1 Hz to its own
file, so the comparison is real:

    log hole + heartbeat hole   -> HOST        (both processes lost the machine)
    log hole + heartbeat clean  -> SHELL-ONLY  (our GIL)
    heartbeat hole, log clean   -> HOST-IDLE   (the machine stalled; no line was
                                                due, so nothing was lost)

MEASURED 2026-11-26 (`_main/webview-run.log` 05:42:22.751 -> 05:44:14.916 and the
worker's own `history/audio/gaps.jsonl:258` 111.241 s): the two silences of the
owner's session were HOST, decided by two processes' independent clocks before
this instrument existed. From now on the same verdict costs one command.

Usage:
    python _main/stall-attr.py --log _main/webview-run.log [--hb <file>] [--min-gap 5]
    python _main/stall-attr.py --selftest

Exit codes: 0 analysed (verdict printed) | 3 CANNOT-MEASURE (no heartbeat file,
so a shell-only stall cannot be separated from a host stall).
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))

STAMP = re.compile(r'^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}\.\d{3}) ')

DEFAULT_HB = os.path.join(ROOT, '_main', '_cache', 'stall-heartbeat.log')


def stamps(lines):
    """`[epoch, ...]` for every line carrying the shell's own stamp."""
    out = []
    for line in lines:
        m = STAMP.match(line)
        if not m:
            continue
        try:
            out.append(datetime.strptime(m.group(1) + ' ' + m.group(2),
                                         '%Y-%m-%d %H:%M:%S.%f').timestamp())
        except ValueError:
            continue
    return out


def holes(points, min_gap):
    """`[{from, to, gap_s}]` for consecutive gaps greater than `min_gap`."""
    out = []
    for a, b in zip(points, points[1:]):
        if b - a > min_gap:
            out.append({'from': a, 'to': b, 'gap_s': round(b - a, 3)})
    return out


def classify(log_holes, hb_holes, slack=1.0):
    """Tag each log hole HOST or SHELL-ONLY, and each orphan hb hole HOST-IDLE."""
    rows = []
    for h in log_holes:
        overlap = [g for g in hb_holes
                   if g['from'] < h['to'] + slack and g['to'] > h['from'] - slack]
        rows.append({'kind': 'HOST' if overlap else 'SHELL-ONLY',
                     'from': h['from'], 'to': h['to'], 'gap_s': h['gap_s'],
                     'hb_gap_s': max((g['gap_s'] for g in overlap), default=None)})
    for g in hb_holes:
        if not any(r['from'] < g['to'] and r['to'] > g['from'] for r in rows):
            rows.append({'kind': 'HOST-IDLE', 'from': g['from'], 'to': g['to'],
                         'gap_s': g['gap_s'], 'hb_gap_s': g['gap_s']})
    return rows


def _fmt(epoch):
    return datetime.fromtimestamp(epoch).strftime('%H:%M:%S.%f')[:-3]


def analyse(log_path, hb_path, min_gap=5.0):
    """`(rows, why)` — `rows` is [] and `why` names the refusal."""
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
            log_lines = fh.readlines()
    except OSError as exc:
        return [], 'log-unreadable: %r' % (exc,)
    pts = stamps(log_lines)
    if len(pts) < 2:
        return [], 'log-has-no-stamps'
    log_holes = holes(pts, min_gap)
    if not os.path.exists(hb_path):
        return [], 'no-heartbeat: %s' % hb_path
    import stall_heartbeat
    hb_holes, span = stall_heartbeat.tail_gaps(hb_path, gap_s=min_gap)
    if span is None:
        return [], 'heartbeat-empty: %s' % hb_path
    return classify(log_holes, hb_holes), ''


def report(rows, log_path, hb_path, min_gap):
    if not rows:
        print('STALL-ATTR no-hole min_gap=%.1f log=%s hb=%s'
              % (min_gap, log_path, os.path.basename(hb_path)))
        print('VERDICT: CLEAN')
        return 0
    counts = {}
    for r in rows:
        counts[r['kind']] = counts.get(r['kind'], 0) + 1
        print('STALL-ATTR %-10s %s -> %s gap_s=%.1f hb_gap_s=%s'
              % (r['kind'], _fmt(r['from']), _fmt(r['to']), r['gap_s'],
                 ('%.1f' % r['hb_gap_s']) if r['hb_gap_s'] is not None else 'none'))
    print('STALL-ATTR-SUMMARY holes=%d host=%d shell-only=%d host-idle=%d'
          % (len(rows), counts.get('HOST', 0), counts.get('SHELL-ONLY', 0),
             counts.get('HOST-IDLE', 0)))
    shell = counts.get('SHELL-ONLY', 0)
    print('VERDICT: %s' % ('SHELL-ONLY' if shell else 'HOST'))
    return 1


def _selftest():
    """Four fixtures, one per verdict — the arm that must be able to fail."""
    import stall_heartbeat as hb
    ok = True
    tmp = tempfile.mkdtemp(prefix='stall-attr-')
    try:
        def write_log(path, ts):
            with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                for t in ts:
                    fh.write(datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                             + ' sotto: x\n')

        def write_hb(path, ts):
            with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                for i, t in enumerate(ts):
                    fh.write(hb.record(i, t, float(i)) + '\n')

        base = 1795682540.0
        # (a) HOST: log and heartbeat both hold the same 20 s hole.
        a_log = os.path.join(tmp, 'a.log')
        a_hb = os.path.join(tmp, 'a.hb')
        write_log(a_log, [base, base + 1, base + 21, base + 22])
        write_hb(a_hb, [base, base + 1, base + 21, base + 22])
        rows, why = analyse(a_log, a_hb, min_gap=5.0)
        ok &= (len(rows) == 1 and rows[0]['kind'] == 'HOST')
        print('  a-host-gap                 %s  %s'
              % ('ok' if len(rows) == 1 and rows[0]['kind'] == 'HOST' else 'FAIL',
                 (rows[0]['kind'] if rows else why)))

        # (b) SHELL-ONLY: the log holds, the heartbeat keeps ticking.
        b_log = os.path.join(tmp, 'b.log')
        b_hb = os.path.join(tmp, 'b.hb')
        write_log(b_log, [base, base + 1, base + 16, base + 17])
        write_hb(b_hb, [base + i for i in range(0, 18)])
        rows, why = analyse(b_log, b_hb, min_gap=5.0)
        ok &= (len(rows) == 1 and rows[0]['kind'] == 'SHELL-ONLY')
        print('  b-shell-only               %s  %s'
              % ('ok' if len(rows) == 1 and rows[0]['kind'] == 'SHELL-ONLY' else 'FAIL',
                 (rows[0]['kind'] if rows else why)))

        # (c) HOST-IDLE: the machine held, the log simply had nothing due.
        c_log = os.path.join(tmp, 'c.log')
        c_hb = os.path.join(tmp, 'c.hb')
        write_log(c_log, [base + i for i in range(0, 30)])
        write_hb(c_hb, [base, base + 1, base + 40, base + 41])
        rows, why = analyse(c_log, c_hb, min_gap=5.0)
        ok &= (len(rows) == 1 and rows[0]['kind'] == 'HOST-IDLE')
        print('  c-host-idle                %s  %s'
              % ('ok' if len(rows) == 1 and rows[0]['kind'] == 'HOST-IDLE' else 'FAIL',
                 (rows[0]['kind'] if rows else why)))

        # (d) NO HEARTBEAT: a refusal, never a green.
        d_log = os.path.join(tmp, 'd.log')
        write_log(d_log, [base, base + 30])
        rows, why = analyse(d_log, os.path.join(tmp, 'absent.hb'), min_gap=5.0)
        ok &= (rows == [] and why.startswith('no-heartbeat'))
        print('  d-no-heartbeat-is-refused  %s  %s'
              % ('ok' if rows == [] and why.startswith('no-heartbeat') else 'FAIL', why))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


#: A classificacao e' UMA linha; o mutante que a cega tem de derrubar o
#: selftest, senao o `b` (SHELL-ONLY) e' uma afirmacao sem braco.
MUTANT = ("'HOST' if overlap else 'SHELL-ONLY'", "'HOST' if True else 'SHELL-ONLY'")


def neg_arm():
    """Run the SAME selftest against a classifier that always says HOST."""
    import importlib.util
    import shutil
    tmp = tempfile.mkdtemp(prefix='stall-attr-neg-')
    try:
        src = open(os.path.abspath(__file__), 'r', encoding='utf-8', newline='').read()
        old, new = MUTANT
        if old not in src:
            print('  always-host MUTANT-BROKEN (anchor missing)')
            return 0
        copy = os.path.join(tmp, 'm.py')
        with open(copy, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(src.replace(old, new, 1))
        spec = importlib.util.spec_from_file_location('stall_attr_mut', copy)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rc = mod._selftest()
        if rc != 0:
            print('NEG-ARM 1/1 CAUGHT')
            print('NEG-ARM VERDICT: PASS')
            return 1
        print('  always-host SURVIVED -- the selftest is blind here')
    except Exception as exc:                  # noqa: BLE001
        print('  always-host MUTANT-BROKEN (%r)' % (exc,))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('NEG-ARM VERDICT: BLIND')
    return 0


def main(argv):
    args = list(argv)
    if '--selftest' in args:
        return _selftest()
    if '--neg-arm' in args:
        code = neg_arm()
        print('VERDICT: %s' % ('CAUGHT' if code == 1 else 'BLIND'))
        return code
    log_path = os.path.join(ROOT, '_main', 'webview-run.log')
    hb_path = DEFAULT_HB
    min_gap = 5.0
    while args:
        a = args.pop(0)
        if a == '--log' and args:
            log_path = args.pop(0)
        elif a == '--hb' and args:
            hb_path = args.pop(0)
        elif a == '--min-gap' and args:
            min_gap = float(args.pop(0))
    rows, why = analyse(log_path, hb_path, min_gap)
    if why:
        print('STALL-ATTR CANNOT-MEASURE why=%s' % why)
        print('VERDICT: CANNOT-MEASURE')
        return 3
    return report(rows, log_path, hb_path, min_gap)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
