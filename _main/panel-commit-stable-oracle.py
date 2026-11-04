#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""panel-commit-stable-oracle.py -- THE TWO MODES OF THE HOLD, AND WHAT MOVED.

WHY THIS EXISTS (owner order, 2026-11-04). `CAPTION_APPLIED` is the COMMIT; the
provisional text was already on screen at `renderProvisional` and NOTHING logged
that instant. So before believing any deletion this probe measures BOTH legs of a
caption line, on the REAL panel, over the WHOLE fragment sequence the shipped log
recorded (`_main/webview-run.log`, every `CAPTION_IN`, read-only):

    push  -> CAPTION_PROVISIONAL_PAINT   what the EYE gets, and when
    paint -> commit                      what the metric was really measuring

THE METRIC IS NOT A p50 (correction, 2026-11-04). The field is BIMODAL: a line
either closes because the next fragment arrived, or it waits out the 1500 ms
ceiling. A p50 on that field describes the sampling window, not the population, so
this probe publishes BOTH MODES WITH THEIR RATES plus p95 and the OVER-BUDGET
SHARE:

    healthy mode   queue_ms < 100 ms      the deadline never fired
    deadline mode  1400 <= queue_ms <= 1520   the ceiling WAS the clock

`queue_ms` = push of the fragment -> acknowledgement, `audio_ms` = capture instant
(`tap_ms`) -> acknowledgement: the two clocks the shell writes on every
`CAPTION_APPLIED`, re-derived here from the log's own `tap_ms`.

THE TWO ARMS, ONE LINE APART. `before` is the same tree with the `stable` commit
removed from `caption-formulation.js` IN MEMORY (the mutant is written outside the
tree and hashed). Same corpus, same panel, one line of difference.

THE FALLBACK ARM. A corpus with no `stable` stamp must STILL be closed by the
1500 ms ceiling: the deadline was not deleted, it was demoted to the population the
worker never proved.

Nothing is launched: no window, no audio device, no Electron, no app. The panel runs
in a node vm with a hand-rolled DOM and a virtual clock.

Usage:
    python _main/panel-commit-stable-oracle.py
    python _main/panel-commit-stable-oracle.py --log H:/sotto/_main/webview-run.log
    python _main/panel-commit-stable-oracle.py --neg-arm   # control: the mutant MUST
                                                           # bring the wait back (exit 1)

Exit: 0 = every verdict held. 1 = a verdict failed (or, in --neg-arm, the control
worked as designed). 2 = setup error (no log, node missing, replay crashed).
"""

from __future__ import print_function

import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REPLAY = os.path.join(HERE, 'panel-commit-stable-replay.js')

# THE SHIPPED LOG. Gitignored and ~66 MB, so `--log PATH` points at the checkout
# that carries it; a missing log is a SETUP ERROR, never a pass.
LOG = os.path.join(HERE, 'webview-run.log')

# The contract, not a description of the run.
EYE_LEG_MAX_MS = 5           # push -> paint, both arms: the pixel never waited
BUDGET_MS = 1500             # the shell's CAPTION_BUDGET_MS
HEALTHY_MS = 100             # a line this quick never waited for the ceiling
DEADLINE_LO_MS = 1400        # the ceiling's own band, +-100 ms
DEADLINE_HI_MS = 1520
DEADLINE_LEG_MIN_MS = 1400   # the control: the mutant must put the wait back
# After the fix the ceiling may only still close the fragments the worker NEVER
# proved (`final:true stable:false` + producers with no `stable` stamp). Their own
# share of the corpus is printed beside this number so the bound can be read against
# the population it is allowed to cover.
UNSHARED_MAX_SHARE = 12.0

CAPTION_IN = re.compile(
    r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) sotto: CAPTION_IN '
    r'start=(\S+) end=(\S+) final=(\w+) stable=(\w+) tap_ms=(\S+) age_ms=(\S+) '
    r'text=(.*)$')


def say(line=''):
    sys.stdout.write(str(line) + '\n')


def fail(message):
    say('SETUP ERROR: ' + message)
    sys.exit(2)


def sha256_file(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def corpus_from_log(path):
    """Every `CAPTION_IN` the shipped log recorded, in the shape the replay eats.

    `t` is ms since the first fragment (the replay's virtual clock), and
    `base_epoch_ms` turns it back into the log's own wall clock so `audio_ms` can be
    re-derived from the fragment's own `tap_ms` — the same subtraction the shell
    does when it writes `CAPTION_APPLIED`.
    """
    if not os.path.exists(path):
        fail('the log is not on disk: %s (pass --log PATH)' % path)
    fragments = []
    with io.open(path, 'r', encoding='utf-8', errors='replace') as handle:
        for line in handle:
            match = CAPTION_IN.match(line.rstrip('\r\n'))
            if not match:
                continue
            when_text, start, end, final, stable, tap_ms, _age, text = match.groups()
            when = datetime.datetime.strptime(when_text, '%Y-%m-%d %H:%M:%S.%f')
            number = lambda value: None if value == 'None' else float(value)
            fragments.append({
                't': int(when.timestamp() * 1000),
                'wall': when_text,
                'text': json.loads(text) if text.startswith('"') else text,
                'meta': {
                    'start': number(start),
                    'end': number(end),
                    'final': final == 'true',
                    'stable': stable == 'true',
                    'tap_ms': int(tap_ms) if tap_ms != 'None' else None,
                },
            })
    if not fragments:
        fail('no CAPTION_IN in %s' % path)
    base = fragments[0]['t']
    for fragment in fragments:
        fragment['t'] -= base
    doc = {
        'base_epoch_ms': base,
        'window': [fragments[0]['wall'], fragments[-1]['wall']],
        'source_sha256': sha256_file(path),
        'fragments': fragments,
    }
    return doc


def run_replay(corpus_path, arm, extra=None):
    cmd = ['node', REPLAY, '--corpus', corpus_path, '--arm', arm]
    if extra:
        cmd.extend(extra)
    try:
        proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
    except OSError as exc:
        fail('cannot run node: %r' % (exc,))
    text = out.decode('utf-8', 'replace')
    errors = err.decode('utf-8', 'replace')
    if proc.returncode != 0:
        fail('replay %s failed rc=%d\n%s\n%s' % (arm, proc.returncode, text[-2000:], errors[-2000:]))
    try:
        return json.loads(text)
    except ValueError as exc:
        fail('replay %s printed no JSON (%r)\n%s\n%s' % (arm, exc, text[-2000:], errors[-2000:]))


def run_fallback():
    cmd = ['node', REPLAY, '--fallback-corpus', '--arm', 'after']
    try:
        proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
    except OSError as exc:
        fail('cannot run node: %r' % (exc,))
    if proc.returncode != 0:
        fail('fallback replay failed rc=%d\n%s' % (proc.returncode, err.decode('utf-8', 'replace')[-2000:]))
    return json.loads(out.decode('utf-8', 'replace'))


def percentile(sorted_values, fraction):
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, int(round(fraction * len(sorted_values) + 0.5)) - 1))
    return sorted_values[index]


def distribution(values):
    clean = sorted(v for v in values if isinstance(v, (int, float)))
    if not clean:
        return {'n': 0, 'p50': None, 'p95': None, 'p99': None, 'max': None}
    return {
        'n': len(clean),
        'p50': clean[len(clean) // 2],
        'p95': percentile(clean, 0.95),
        'p99': percentile(clean, 0.99),
        'max': clean[-1],
    }


def modes(rows):
    """THE POPULATION, SPLIT THE WAY THE FIELD IS SHAPED.

    `rows` are the replay's `[queue_ms, audio_ms]` pairs. A line is in the DEADLINE
    mode when its acknowledgement came 1400-1520 ms after its fragment was pushed
    (the ceiling, to the millisecond), HEALTHY when it came within 100 ms (the next
    fragment closed it), and the remainder is everything else (an audio-gap or a
    status flush, both real closers that are neither).
    """
    queue = [r[0] for r in rows if isinstance(r[0], (int, float))]
    audio = [r[1] for r in rows if isinstance(r[1], (int, float))]
    deadline = [q for q in queue if DEADLINE_LO_MS <= q <= DEADLINE_HI_MS]
    healthy = [q for q in queue if q < HEALTHY_MS]
    over = [a for a in audio if a > BUDGET_MS]

    total = len(queue) or 1
    return {
        'lines': len(queue),
        'healthy': len(healthy),
        'healthyShare': round(100.0 * len(healthy) / total, 1),
        'healthyP50': distribution(healthy)['p50'],
        'deadline': len(deadline),
        'deadlineShare': round(100.0 * len(deadline) / total, 1),
        'deadlineP50': distribution(deadline)['p50'],
        'other': len(queue) - len(healthy) - len(deadline),
        'audio': distribution(audio),
        'overBudget': len(over),
        'overBudgetShare': round(100.0 * len(over) / total, 1),
        'audioDeadlineMode': distribution([r[1] for r in rows if isinstance(r[1], (int, float))
                                           and isinstance(r[0], (int, float))
                                           and DEADLINE_LO_MS <= r[0] <= DEADLINE_HI_MS]),
    }


def audit_rows(result):
    """The replay's per-commit pairs, or a setup error when the join produced none."""
    rows = result.get('commitRows') or []
    if not rows:
        fail('the %s replay produced no joinable commits (%d commits, %d paints)'
             % (result.get('arm'), result.get('commits', 0), result.get('paints', 0)))
    return rows


def cell(value):
    return '-' if value is None else str(value)


def show(label, before, after, unit=''):
    say('  %-34s %-28s %-28s'
        % (label, str(before) + unit, str(after) + unit))


def table(before, after, mb, ma, worker):
    say('')
    say('  THE TWO LEGS -- same corpus, same panel, one line apart')
    say('  %-34s %-28s %-28s' % ('', 'BEFORE (ceiling = clock)', 'AFTER (worker proved it)'))
    for name, key in (('push -> provisional paint (EYE)', 'pushToPaint'),
                      ('paint -> commit (metric)', 'paintToCommit'),
                      ('push -> commit (acknowledgement)', 'pushToCommit')):
        b = before['legs'][key]
        a = after['legs'][key]
        show(name + ' p50/p95/max',
             '%s / %s / %s' % (cell(b['p50']), cell(b['p95']), cell(b['max'])),
             '%s / %s / %s' % (cell(a['p50']), cell(a['p95']), cell(a['max'])), ' ms')
    say('')
    say('  THE POPULATION (the metric is not a p50 -- the field is bimodal)')
    show('lines acknowledged', mb['lines'], ma['lines'])
    show('HEALTHY mode  queue<100 ms', '%d (%s %%)' % (mb['healthy'], mb['healthyShare']),
         '%d (%s %%)' % (ma['healthy'], ma['healthyShare']))
    show('  its queue p50', cell(mb['healthyP50']), cell(ma['healthyP50']), ' ms')
    show('DEADLINE mode 1400-1520 ms', '%d (%s %%)' % (mb['deadline'], mb['deadlineShare']),
         '%d (%s %%)' % (ma['deadline'], ma['deadlineShare']))
    show('  its queue p50', cell(mb['deadlineP50']), cell(ma['deadlineP50']), ' ms')
    show('other closer (gap/status)', mb['other'], ma['other'])
    show('audio_ms  p50/p95/p99/max',
         '%s / %s / %s / %s' % (cell(mb['audio']['p50']), cell(mb['audio']['p95']),
                                cell(mb['audio']['p99']), cell(mb['audio']['max'])),
         '%s / %s / %s / %s' % (cell(ma['audio']['p50']), cell(ma['audio']['p95']),
                                cell(ma['audio']['p99']), cell(ma['audio']['max'])), ' ms')
    show('OVER BUDGET (audio>%d ms)' % BUDGET_MS,
         '%d (%s %%)' % (mb['overBudget'], mb['overBudgetShare']),
         '%d (%s %%)' % (ma['overBudget'], ma['overBudgetShare']))

    say('')
    show('fragments / paints / commits',
         '%d / %d / %d' % (before['fragments'], before['paints'], before['commits']),
         '%d / %d / %d' % (after['fragments'], after['paints'], after['commits']))
    show('rows (<li>) / elements created',
         '%d / %d' % (before['domCreated']['li'], before['domCreated']['all']),
         '%d / %d' % (after['domCreated']['li'], after['domCreated']['all']))
    say('  WORKER leg (tap -> push), ARM-INDEPENDENT and NOT this lane: '
        'p50=%s p95=%s p99=%s max=%s ms (n=%s)'
        % (cell(worker['p50']), cell(worker['p95']), cell(worker['p99']),
           cell(worker['max']), cell(worker['n'])))
    say('  route/routeSource  before=%s' % json.dumps(before['routes'], sort_keys=True))
    say('                     after =%s' % json.dumps(after['routes'], sort_keys=True))


def main():
    global LOG
    neg_arm = '--neg-arm' in sys.argv
    for index, item in enumerate(sys.argv):
        if item == '--log' and index + 1 < len(sys.argv):
            LOG = sys.argv[index + 1]

    if not os.path.exists(REPLAY):
        fail('instrument missing: %s' % REPLAY)

    doc = corpus_from_log(LOG)
    fragments = doc['fragments']
    handle, corpus_path = tempfile.mkstemp(prefix='panel-commit-stable-', suffix='.json')
    os.close(handle)
    with io.open(corpus_path, 'w', encoding='utf-8') as out:
        json.dump(doc, out, ensure_ascii=False)
    corpus_sha = sha256_file(corpus_path)

    stable = sum(1 for f in fragments if f['meta']['stable'])
    unproved = [f for f in fragments if not f['meta']['stable']]
    final_unstable = sum(1 for f in fragments if f['meta']['final'] and not f['meta']['stable'])

    say('CORPUS  %d CAPTION_IN  %s .. %s  sha256=%s'
        % (len(fragments), doc['window'][0], doc['window'][1], corpus_sha[:16]))
    unproved_share = round(100.0 * len(unproved) / len(fragments), 1)
    say('        log sha256=%s  stable=%d  unproved=%d (%s %%) (final:true stable:false = %d)'
        % (doc['source_sha256'][:16], stable, len(unproved), unproved_share, final_unstable))

    before = run_replay(corpus_path, 'before')
    after = run_replay(corpus_path, 'after')
    fallback = run_fallback()
    os.unlink(corpus_path)

    say('BYTES   panel.js sha256=%s' % after['sha256']['panel'][:16])
    say('        caption-formulation.js shipped=%s before-arm=%s'
        % (after['sha256']['engine'][:16], before['sha256']['engineArmUsed'][:16]))
    say('        mutant: %s' % (before.get('mutant') or '-'))

    mb = modes(audit_rows(before))
    ma = modes(audit_rows(after))
    # THE LEG THIS LANE DOES NOT OWN, measured where it happens: the capture instant
    # to the push. It is the same set of fragments in BOTH arms (it is upstream of
    # the panel), so it is computed from the corpus and never from a commit join —
    # a per-arm reading would compare two different sets and could be made to move
    # by the fix without the worker changing at all.
    worker = distribution([(doc['base_epoch_ms'] + f['t']) - f['meta']['tap_ms']
                           for f in fragments
                           if f['meta']['tap_ms'] is not None])
    table(before, after, mb, ma, worker)

    fb = fallback['legs']['paintToCommit']
    say('')
    say('  FALLBACK POPULATION (no `stable` stamp: player channel, batch pass, older workers)')
    say('  the ceiling still closes it: n=%s p50=%s p95=%s max=%s ms'
        % (cell(fb['n']), cell(fb['p50']), cell(fb['p95']), cell(fb['max'])))

    checks = []
    checks.append(('EYE leg is unchanged in BOTH arms (push -> paint p50 <= %d ms)' % EYE_LEG_MAX_MS,
                   (before['legs']['pushToPaint']['p50'] or 0) <= EYE_LEG_MAX_MS
                   and (after['legs']['pushToPaint']['p50'] or 0) <= EYE_LEG_MAX_MS,
                   'before=%s after=%s ms' % (cell(before['legs']['pushToPaint']['p50']),
                                              cell(after['legs']['pushToPaint']['p50']))))
    checks.append(('BEFORE carries the ceiling mode, at the ceiling itself',
                   mb['deadline'] >= 100 and DEADLINE_LO_MS <= (mb['deadlineP50'] or 0) <= DEADLINE_HI_MS,
                   'before deadline mode=%d lines (%s %%), their queue p50=%s ms'
                   % (mb['deadline'], mb['deadlineShare'], cell(mb['deadlineP50']))))
    checks.append(('AFTER: the deadline mode collapses to the unproved population',
                   ma['deadlineShare'] <= UNSHARED_MAX_SHARE,
                   'before=%s %% after=%s %% (unproved fragments=%s %%)'
                   % (mb['deadlineShare'], ma['deadlineShare'], cell(unproved_share))))
    checks.append(('AFTER: the healthy mode grows', ma['healthy'] > mb['healthy'],
                   'before=%d after=%d lines' % (mb['healthy'], ma['healthy'])))
    checks.append(('AFTER: audio p95 falls', (ma['audio']['p95'] or 0) < (mb['audio']['p95'] or 0),
                   'before p95=%s after p95=%s ms'
                   % (cell(mb['audio']['p95']), cell(ma['audio']['p95']))))
    checks.append(('AFTER: over-budget share falls',
                   ma['overBudgetShare'] < mb['overBudgetShare'],
                   'before=%s %% after=%s %%' % (mb['overBudgetShare'], ma['overBudgetShare'])))
    checks.append(('AFTER: no route is manufactured (every commit worker-stamped)',
                   all(key.endswith('/worker-stamped') for key in after['routes'])
                   and all(key.split('/')[0] in ('final', 'provisional-draft') for key in after['routes']),
                   json.dumps(after['routes'], sort_keys=True)))
    checks.append(('FALLBACK: an unproved tail is still closed by the ceiling (p50 >= %d ms)'
                   % DEADLINE_LEG_MIN_MS,
                   (fb['p50'] or 0) >= DEADLINE_LEG_MIN_MS,
                   'fallback p50=%s ms' % cell(fb['p50'])))
    checks.append(('FALLBACK: no line is lost (3 fragments in, 3 commits out)',
                   fb['n'] == 3, 'fallback commits=%s' % cell(fb['n'])))

    say('')
    for label, ok, detail in checks:
        say('  [%s] %s  (%s)' % ('PASS' if ok else 'FAIL', label, detail))

    if neg_arm:
        # THE CONTROL. The `before` arm IS the mutant: the same tree with the
        # `stable` commit removed. It must put the wait BACK, and the eye leg must
        # still be zero in it (otherwise the mutation broke the instrument rather
        # than the behaviour). rc=1 is this battery's red-by-design convention.
        # THE CONTROL IS JUDGED ON THE SAME METRIC AS THE FIX — the ceiling mode's
        # POPULATION and its own p50 — never on a whole-field p50, which is exactly
        # the statistic the correction withdrew.
        control = (mb['deadline'] >= 100
                   and DEADLINE_LO_MS <= (mb['deadlineP50'] or 0) <= DEADLINE_HI_MS
                   and mb['deadlineShare'] > 5.0
                   and before['legs']['pushToPaint']['p50'] <= EYE_LEG_MAX_MS)
        say('')
        say('NEG-ARM: %s -- stable commit removed; the ceiling mode came back at '
            '%d lines (%s %% of them, queue p50=%s ms), eye leg p50=%s ms'
            % ('PASS' if control else 'FAIL', mb['deadline'], cell(mb['deadlineShare']),
               cell(mb['deadlineP50']), cell(before['legs']['pushToPaint']['p50'])))
        if not control:
            say('VERDICT: FAIL -- the control did NOT go back up, so the after arm proves nothing')
            sys.exit(0)
        say('VERDICT: RED BY DESIGN (the control is the defect: the ceiling is the clock again)')
        sys.exit(1)

    all_ok = all(ok for _label, ok, _detail in checks)
    say('')
    say('VERDICT: %s' % ('PASS' if all_ok else 'FAIL'))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
