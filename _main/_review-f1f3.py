"""ADVERSARIAL REVIEW probe — attacks 1 (F1 autostart rule) and 2 (F3 verdict).

Reads the REAL files, drives the REAL functions, writes its receipt to a FILE
(this sandbox denies every pipe, so nothing here may use subprocess or
capture_output). No window, no audio device, no app launch.

    cmd /c "python _main\_review-f1f3.py > _main\_review-f1f3.log 2>&1"
"""

import importlib.util
import inspect
import os
import re
import sys

ROOT = r'H:\sotto'
WEB = os.path.join(ROOT, 'app', 'webview')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
sys.path.insert(0, WEB)

out = []
def say(line=''):
    out.append(str(line))
    print(line, flush=True)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── PART A: F1, the autostart rule ───────────────────────────────────────────
say('=' * 72)
say('PART A — F1: SottoShell._worker_autostart_reason, the REAL parser + rule')
say('=' * 72)
sw = load_module('sotto_webview', os.path.join(WEB, 'sotto_webview.py'))
say(f'shell revision: {os.path.getsize(os.path.join(WEB, "sotto_webview.py"))} B, '
    f'mtime {os.path.getmtime(os.path.join(WEB, "sotto_webview.py")):.0f}')
say(f'signature: {inspect.signature(sw.SottoShell._worker_autostart_reason)}')

ARMS = [
    ('no flags at all (double-click)',            [], {}),
    ('--show only',                               ['--show'], {}),
    ('--no-worker',                               ['--no-worker'], {}),
    ('--with-worker',                             ['--with-worker'], {}),
    ('--no-worker --with-worker',                 ['--no-worker', '--with-worker'], {}),
    ('--with-worker --no-worker',                 ['--with-worker', '--no-worker'], {}),
    ('--exit-after 0 (float 0.0 = "off")',        ['--exit-after', '0'], {}),
    ('--exit-after 0.0',                          ['--exit-after', '0.0'], {}),
    ('--exit-after 25',                           ['--exit-after', '25'], {}),
    ('--no-hotkey',                               ['--no-hotkey'], {}),
    ('--worker <fake> --no-hotkey',               ['--worker', r'H:\sotto\_main\_armE-fake-worker.py', '--no-hotkey'], {}),
    ('--worker <fake> --no-hotkey --with-worker', ['--worker', r'H:\sotto\_main\_armE-fake-worker.py', '--no-hotkey', '--with-worker'], {}),
    ('--dump-dom',                                ['--dump-dom'], {}),
    ('--selftest',                                ['--selftest'], {}),
    ('--memory',                                  ['--memory'], {}),
    ('--probe-v2 3',                              ['--probe-v2', '3'], {}),
    ('SOTTO_NO_WORKER=1',                         [], {'SOTTO_NO_WORKER': '1'}),
    ('SOTTO_NO_WORKER=0',                         [], {'SOTTO_NO_WORKER': '0'}),
    ('SOTTO_NO_WORKER=true',                      [], {'SOTTO_NO_WORKER': 'true'}),
    ('SOTTO_NO_WORKER= 1 (space)',                [], {'SOTTO_NO_WORKER': ' 1 '}),
    ('SOTTO_NO_WORKER=1 + --with-worker',         ['--with-worker'], {'SOTTO_NO_WORKER': '1'}),
    ('SOTTO_NO_WORKER=1 + --exit-after 25',       ['--exit-after', '25'], {'SOTTO_NO_WORKER': '1'}),
]

STARTS = ('default', 'with-worker')
say(f'{"argv / env":<46} {"reason":<28} starts?')
say('-' * 92)
findings = []
for label, argv, env in ARMS:
    args = sw.parse_args(argv)
    reason = sw.SottoShell._worker_autostart_reason(args, env)
    starts = reason in STARTS
    say(f'{label:<46} {reason:<28} {"YES" if starts else "no"}')
    findings.append((label, argv, env, reason, starts))

# The property that matters: the DOCUMENTED launch must start, and every
# declared opt-out / measurement mode must not — and --with-worker must win.
def check(label, want_start):
    for lab, _a, _e, reason, starts in findings:
        if lab == label:
            ok = starts == want_start
            say(f'[{"PASS" if ok else "FAIL"}] {label}: want starts={want_start}, got reason={reason}')
            return ok
    say(f'[SETUP] arm not found: {label}')
    return False

a_ok = all([
    check('no flags at all (double-click)', True),
    check('--show only', True),
    check('--probe-v2 3', True),
    check('--no-worker', False),
    check('SOTTO_NO_WORKER=1', False),
    check('SOTTO_NO_WORKER=0', True),
    check('--exit-after 0 (float 0.0 = "off")', True),
    check('--exit-after 25', False),
    check('--no-hotkey', False),
    check('--dump-dom', False),
    check('--selftest', False),
    check('--memory', False),
    check('--worker <fake> --no-hotkey', False),
    check('--worker <fake> --no-hotkey --with-worker', True),
    check('--no-worker --with-worker', True),
    check('SOTTO_NO_WORKER=1 + --with-worker', True),
])

# The ORACLE that would die if the alias stopped winning: its real argv.
say('')
say('the live oracle argv that depends on the alias (panel-exit3-oracle.py:831):')
orc = ['--no-hotkey', '--with-worker', '--worker', r'H:\sotto\_main\_armE-fake-worker.py',
       '--no-hot-reload', '--dump-dom']
r = sw.SottoShell._worker_autostart_reason(sw.parse_args(orc), {})
say(f'  --no-hotkey --with-worker --worker <fake> --no-hot-reload --dump-dom -> {r!r}')
say(f'  [{"PASS" if r == "with-worker" else "FAIL"}] the alias still wins over three measurement flags')

# ── PART B: F3, the verdict rule ─────────────────────────────────────────────
say('')
say('=' * 72)
say('PART B — F3: decide_verdict, extracted from the live file and swept')
say('=' * 72)
src = open(WORKER, encoding='utf-8').read()
lines = src.splitlines()
start = None
for i, line in enumerate(lines):
    if line.startswith('def decide_verdict(counters, outcome, ran_but_silent) -> str:'):
        start = i
        break
if start is None:
    say('SETUP ERROR: decide_verdict not found')
    sys.exit(2)
body = []
for line in lines[start + 1:]:
    if line.strip() and not line.startswith(('    ', '\t')):
        break
    body.append(line)
ns = {}
exec('def decide_verdict(counters, outcome, ran_but_silent) -> str:\n'
     + '\n'.join(body), ns)
dv = ns['decide_verdict']
say(f'worker revision: {len(src.encode("utf-8"))} B; function body: {len(body)} lines '
    f'(def at line {start + 1})')

BASE = {'captions': 0, 'chunks': 44, 'blocks': 100, 'nonzero_blocks': 90,
        'resampled_samples': 100000, 'music_gated_chunks': 0, 'vad_gated_chunks': 0}
OUTCOMES = [None, 'all-flat', 'open-failed', 'settled', '']

hits = []
raises = []
calls = 0
for key in list(BASE) + ['some_unknown_key']:
    for val in (0, 1, 2, -1, '0', None):
        c = dict(BASE)
        if val is None:
            c.pop(key, None)
        else:
            c[key] = val
        for outcome in OUTCOMES:
            for rbs in (False, True):
                calls += 1
                try:
                    v = dv(c, outcome, rbs)
                except Exception as exc:
                    raises.append((key, val, type(exc).__name__, str(exc)[:60]))
                    continue
                if v == 'captions-emitted':
                    caps = c.get('captions', 'absent')
                    # THE FILTER MUST MATCH THE HEADING. This used to append EVERY
                    # healthy verdict, so the swept `captions=1` / `captions=2`
                    # cases — which are positive ints and are SUPPOSED to be
                    # healthy — were printed under "captions is NOT a positive int"
                    # and made `b_ok` FALSE on every revision, including a correct
                    # one: a gate that could not say PASS (measured against the
                    # revision that closed the escapes, 2026-10-07).
                    positive = (isinstance(caps, int) and not isinstance(caps, bool)
                                and caps > 0)
                    if not positive:
                        hits.append((key, val, outcome, rbs, v, caps))

say(f'calls: {calls} (one key varied at a time over {len(BASE) + 1} keys x 6 values x '
    f'{len(OUTCOMES)} outcomes x 2 ran_but_silent)')
say('')
say('combinations that returned captions-emitted while captions is NOT a positive int:')
if not hits:
    say('  NONE')
else:
    seen = set()
    for key, val, outcome, rbs, v, caps in hits:
        sig = (key, val)
        if sig in seen:
            continue
        seen.add(sig)
        say(f'  varied {key}={val!r} -> verdict={v!r} with captions={caps!r} '
            f'(outcome={outcome!r}, ran_but_silent={rbs})')
    say(f'  distinct (key,value) pairs: {len(seen)} of {len(hits)} hits')

# the reverse lie: captions > 0 but a no-audio word
say('')
reverse = []
for outcome in OUTCOMES:
    for rbs in (False, True):
        c = dict(BASE, captions=3, music_gated_chunks=44, vad_gated_chunks=10)
        v = dv(c, outcome, rbs)
        # THE ORDER IS THE CONTRACT (decide_verdict's own docstring): a measured
        # device fact is tested BEFORE the captions count, so `ran_but_silent=True`
        # or an exhausted ladder legitimately beats `captions=3`. Only a
        # NON-contradictory input can carry the reverse lie, so only those are
        # counted — otherwise this list is non-empty by design and the verdict
        # below is RED forever.
        contradictory = rbs or outcome in ('all-flat', 'open-failed')
        if v != 'captions-emitted' and not contradictory:
            reverse.append((c.copy(), outcome, rbs, v))
say(f'reverse control (captions=3, music_gated=44=chunks, vad_gated=10): '
    f'{len(reverse)} combination(s) that did NOT return a healthy finish')
for c, outcome, rbs, v in reverse:
    say(f'  captions=3 -> {v!r}  (outcome={outcome!r} ran_but_silent={rbs})')

# a negative / non-int captions, explicitly
say('')
for weird in (-1, '0', 0.0, None):
    c = dict(BASE)
    if weird is None:
        c.pop('captions')
    else:
        c['captions'] = weird
    say(f'  captions={weird!r:<8} -> {dv(c, None, False)!r}')

b_ok = (not hits) and (not reverse) and (not raises)
say('')
say('combinations that RAISED inside the verdict function (a run would end in a traceback):')
if not raises:
    say('  NONE')
else:
    seen = set()
    for key, val, exc, msg in raises:
        if (key, val, exc) in seen:
            continue
        seen.add((key, val, exc))
        say(f'  {key}={val!r} -> {exc}: {msg}')
    say(f'  distinct: {len(seen)} of {len(raises)} raised call(s)')

say('')
say(f'PART A (F1 rule): {"GREEN" if a_ok else "RED"}')
say(f'PART B (F3 rule): {"GREEN" if b_ok else "RED"}')
with open(os.path.join(ROOT, '_main', '_review-f1f3.log'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
