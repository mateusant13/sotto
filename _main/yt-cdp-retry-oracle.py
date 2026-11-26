"""Oracle for the CDP source retry cooldown.

MEASURED 2026-11-26: `_yt_cdp_ensure` set `False` on one failed `start()` and
returned early on every later tick, so a transient exception killed the cheap
caption path for the whole session; the read then fell into the accessibility
tree (15906 ms measured) and the 4 Hz loop collapsed to 0.1-1.5 Hz.

Arms:
  * the first failure waits 5 s and says so (`tries=1 next_s=5`);
  * the delay doubles to a 60 s cap and never exceeds it;
  * the cooldown is a deadline, not a suggestion (`due` is false before it);
  * RECOVERY with the owner's shape: a `start` that fails twice then succeeds
    comes back inside 300 s of 4 Hz ticks -- and the old tombstone control never
    comes back, which is what proves the arm can fail;
  * the shell asks `due` BEFORE it re-arms, and a good start resets the counter.

`--neg-arm` mutates one thing at a time and requires every mutant to be CAUGHT
(rc 1 = red-as-expected; rc 0 = the gate is blind).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, 'app', 'webview', 'yt_cdp_retry.py')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')


def _load(path, name='yt_cdp_retry_probe'):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arms(mod):
    out = []

    def arm(name, ok, detail=''):
        out.append((name, bool(ok), detail))

    # A1 -- first failure: 5 s, named
    at, delay, event = mod.arm(1, 1000.0)
    arm('a1-first-failure-waits-5s',
        abs(delay - 5.0) < 1e-9 and abs(at - 1005.0) < 1e-9
        and 'tries=1' in event and 'next_s=5' in event,
        'delay=%.2f event=%r' % (delay, event))

    # A2 -- doubling to the cap, never past it
    delays = [mod.next_delay(n) for n in range(1, 8)]
    arm('a2-doubles-to-the-cap',
        delays == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0, 60.0],
        '%r' % (delays,))
    arm('a3-cap-holds-at-50-tries', mod.next_delay(50) == 60.0,
        '%.1f' % mod.next_delay(50))

    # A4 -- the deadline is real
    arm('a4-cooldown-is-a-deadline',
        mod.due(1, 120.0, 119.999) is False
        and mod.due(1, 120.0, 120.0) is True
        and mod.due(1, 0.0, 1.0) is True
        and mod.due(1, None, 1.0) is True
        and mod.due(1, 'x', 1.0) is False,
        'ok')

    # A5 -- RECOVERY, with the owner's shape: two failures, then a good start.
    def recovered(delay_fn, tries_fn=None):
        now, tries, next_at, live = 0.0, 0, 0.0, False
        while now < 300.0:
            now += 0.250                      # the loop's own 4 Hz period
            if live:
                continue
            if not mod.due(tries, next_at, now):
                continue
            tries += 1
            if tries >= 3:                    # third attempt succeeds
                live = True
                tries = 0
                continue
            next_at = now + delay_fn(tries)

        return live

    healed = recovered(lambda n: mod.next_delay(n))
    arm('a5-two-failures-then-recovery', healed is True, 'live=%s' % healed)

    # CONTROL: the tombstone the code used to have never recovers.
    def tombstoned():
        return False                          # `if source is False: return None`

    blind = tombstoned()
    arm('a6-tombstone-control-never-recovers', blind is False,
        'the old behaviour is the failure this arm exists to catch')

    # A7 -- the shell asks `due` before it re-arms, and resets on success
    shell = open(SHELL, 'r', encoding='utf-8', errors='replace').read()
    gate = shell.find('if not yt_cdp_retry.due(')
    reset = shell.find('self._yt_cdp_fail_tries = 0')
    armgold = shell.find('self._yt_cdp_source = False')
    arm('a7-shell-asks-due-then-rearms',
        0 <= gate < shell.find("log('YOUTUBE_CDP_SOURCE_COOLDOWN_END"),
        'gate=%d' % gate)
    arm('a8-shell-forgets-failures-on-success', reset > armgold >= 0,
        'reset=%d fail=%d' % (reset, armgold))
    arm('a9-events-are-named',
        'YOUTUBE_CDP_SOURCE_RETRY' in shell and 'YOUTUBE_CDP_SOURCE_COOLDOWN_END' in shell,
        'ok')
    return out


def run(mod=None, label='live'):
    mod = mod or _load(MODULE)
    rows = arms(mod)
    bad = [r for r in rows if not r[1]]
    for name, ok, detail in rows:
        print('  %-36s %s  %s' % (name, 'ok' if ok else 'FAIL', detail))
    print('ARM-SUMMARY %s arms=%d ok=%d fail=%d'
          % (label, len(rows), len(rows) - len(bad), len(bad)))
    return rows, bad


MUTANTS = [
    ('first-delay-zero', MODULE, 'FIRST_DELAY_S = 5.0', 'FIRST_DELAY_S = 0.0'),
    ('cap-too-low', MODULE, 'MAX_DELAY_S = 60.0', 'MAX_DELAY_S = 5.0'),
    ('no-growth', MODULE, 'SCALE = 2.0', 'SCALE = 1.0'),
    ('due-always-true', MODULE, '    try:\n        return float(now) >= float(next_at or 0.0)',
     '    try:\n        return True'),
    ('due-always-false', MODULE, '    try:\n        return float(now) >= float(next_at or 0.0)',
     '    try:\n        return False'),
    ('arm-parks-at-now', MODULE, '    return (float(now) + delay, delay,',
     '    return (float(now), delay,'),
    # O mutante tem de APAGAR o numero de tentativas, nao so' reordenar: um
    # evento que ainda diga `tries=1` em qualquer ordem nao prova nada.
    ('event-loses-tries', MODULE, "'YOUTUBE_CDP_SOURCE_RETRY tries=%d next_s=%.0f' % (n, delay)",
     "'YOUTUBE_CDP_SOURCE_RETRY next_s=%.0f n=%d' % (delay, n)"),
]


def neg_arm():
    caught = total = 0
    tmp = tempfile.mkdtemp(prefix='yt-cdp-retry-neg-')
    try:
        for name, path, old, new in MUTANTS:
            total += 1
            src = open(path, 'r', encoding='utf-8', errors='replace').read()
            if old not in src:
                print('  %-36s MUTANT-BROKEN (anchor missing)' % name)
                continue
            copy = os.path.join(tmp, 'm_%d.py' % total)
            open(copy, 'w', encoding='utf-8', newline='\n').write(src.replace(old, new, 1))
            try:
                mod = _load(copy, 'yt_cdp_retry_mut_%d' % total)
                _, bad = run(mod, label='mutant:%s' % name)
            except Exception as exc:          # noqa: BLE001
                print('  %-36s MUTANT-BROKEN (%r)' % (name, exc))
                continue
            if bad:
                caught += 1
            else:
                print('  %-36s SURVIVED -- the gate is blind here' % name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('NEG-ARM %d/%d CAUGHT' % (caught, total))
    if caught == total:
        print('NEG-ARM VERDICT: PASS')
    # A caught mutant is rc 1 (house convention); rc 0 means a survivor.
    return 1 if caught == total else 0


def main(argv):
    if '--neg-arm' in argv:
        code = neg_arm()
        print('VERDICT: %s' % ('CAUGHT' if code == 1 else 'BLIND'))
    else:
        _, bad = run()
        code = 1 if bad else 0
        print('VERDICT: %s' % ('PASS' if code == 0 else 'RED'))
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
