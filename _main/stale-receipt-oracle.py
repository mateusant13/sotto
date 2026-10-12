#!/usr/bin/env python3
"""stale-receipt-oracle -- is this artefact's claim about the CURRENT source?

WHY THIS EXISTS. Two audit rows are the same defect class, one level apart:

  * #29 -- `_main/panel-exit3-oracle.log` carries a PASS, and its mtime predates the
    shell it claims to have measured, so the PASS was won by an older revision (the
    row says a 3-arm one).
  * "Finding A" -- the top-level receipt of that same oracle is STALE against its own
    source (`oracles.md:404`).

Both are the failure mode the root AGENTS.md names in its rule 2: a number without its
revision is a number with a shelf life. This instrument makes the shelf life MACHINE
READABLE: for each (artefact, sources) pair it reports the two clocks and decides, and
it accepts a revision stamp as the stronger evidence when the artefact carries one.

WHAT IT DOES NOT DO. It never re-runs the artefact, and it never launches the product:
the owner's order forbids both (2026-10-11). A stale log is therefore DECLARED stale,
not refreshed -- refreshing it is a launch, and that is the owner's call.

BOTH COLOURS. `--neg-arm` copies the pairs into a scratch directory and re-stamps the
artefact's mtime so it is newer than its sources; every pair must then read CURRENT. An
instrument that can only say STALE cannot tell a stale file from a broken comparator.

Usage:
  py -3 _main/stale-receipt-oracle.py [--neg-arm] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))

#: (label, artefact, [sources]) -- the pairs the audit rows name. A pair with a source
#: list of one is still a clock comparison: the artefact must be at least as new as the
#: thing it describes.
PAIRS = (
    ('row #29 log', os.path.join(HERE, 'panel-exit3-oracle.log'),
     (os.path.join(HERE, 'panel-exit3-oracle.py'),
      os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py'))),
    # NOTE (measured): "Finding A" names the SAME artefact as row #29 -- both quote
    # `panel-exit3-oracle.log` (mtime 03:54:30 < source). Two rows, one file, one clock:
    # it is listed once here on purpose, and the row texts carry the pairing.
    ('meter chain receipt', os.path.join(HERE, 'receipt-20261011-worker-meter.md'),
     (os.path.join(ROOT, 'worker', 'sotto_worker.py'),)),
    ('bridge sweep receipt', os.path.join(HERE, 'receipt-20261011-audit-rows-sweep.md'),
     (os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py'),
      os.path.join(ROOT, 'worker', 'sotto_worker.py'))),
)

#: Revision stamps an artefact may carry instead of a usable clock. "2026-10-11" is the
#: date this instrument was written; a stamp OLDER than a source's mtime is the same
#: finding as an old clock, said in words.
STAMP_KEYS = ('measured_shell_sha256', 'source_sha256', 'revision')


def measure(artefact, sources):
    """The clocks and, when the artefact is JSON, any revision stamp it carries."""
    entry = {'artefact': artefact, 'exists': os.path.exists(artefact)}
    if not entry['exists']:
        entry['verdict'] = 'MISSING'
        return entry
    entry['artefact_mtime'] = os.path.getmtime(artefact)
    entry['artefact_size'] = os.path.getsize(artefact)
    entry['sources'] = []
    newest = 0.0
    for source in sources:
        row = {'path': source, 'exists': os.path.exists(source)}
        if row['exists']:
            row['mtime'] = os.path.getmtime(source)
            newest = max(newest, row['mtime'])
        entry['sources'].append(row)
    entry['newest_source_mtime'] = newest
    entry['age_s'] = round(newest - entry['artefact_mtime'], 1)
    stamps = {}
    if artefact.endswith('.json') or artefact.endswith('.log'):
        try:
            with open(artefact, encoding='utf-8') as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                for key in STAMP_KEYS:
                    if key in payload:
                        stamps[key] = payload[key]
        except Exception:  # noqa: BLE001  -- not JSON, or unreadable: no stamp, no claim
            stamps = {}
    entry['stamps'] = stamps
    entry['verdict'] = ('STALE' if entry['age_s'] > 0 and not stamps else 'CURRENT')
    if stamps and entry['age_s'] > 0:
        entry['verdict'] = 'STALE-BUT-STAMPED'
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--neg-arm', action='store_true',
                        help='re-stamp copies so every pair must read CURRENT')
    parser.add_argument('--verbose', action='store_true')
    parsed = parser.parse_args(argv)

    pairs = list(PAIRS)
    scratch = None
    if parsed.neg_arm:
        scratch = tempfile.mkdtemp(prefix='sotto-stale-neg-')
        fresh = []
        skipped = []
        for label, artefact, sources in pairs:
            if not os.path.exists(artefact):
                # A MISSING artefact cannot be re-stamped, so the neg-arm cannot speak
                # about it either; it is named, never silently required to be CURRENT.
                skipped.append(label)
                continue
            copy = os.path.join(scratch, os.path.basename(artefact) + '.' + label.replace(' ', '_').replace('#', ''))
            shutil.copy2(artefact, copy)
            # Newer than every source by an hour: the comparator must now say CURRENT.
            os.utime(copy, (time.time() + 3600, time.time() + 3600))
            fresh.append((label + ' (re-stamped copy)', copy, sources))
        pairs = fresh
        if skipped:
            print('  neg-arm skips ' + str(len(skipped))
                  + ' MISSING artefact(s): ' + ', '.join(skipped))

    say = print
    say('stale-receipt-oracle -- does the artefact describe the source it has today?')
    say('launches   : NOTHING (stat + JSON.parse + a copy of two files into TMPDIR)')
    say('pairs      : ' + str(len(pairs)))
    if scratch:
        say('scratch    : ' + scratch)
    say('')

    results = {}
    for label, artefact, sources in pairs:
        entry = measure(artefact, sources)
        results[label] = entry
        say('  ' + label.ljust(22) + entry['verdict'].ljust(16)
            + ('age_s=' + str(entry.get('age_s', '?')))
            + ('' if not entry.get('stamps') else '  stamps=' + json.dumps(entry['stamps'])[:60]))
        if parsed.verbose:
            say('      ' + json.dumps(entry, default=str))

    if parsed.neg_arm:
        wrong = [k for k, v in results.items() if v['verdict'] != 'CURRENT']
        say('')
        say('NEG-ARM: every re-stamped copy must read CURRENT; wrong: ' + str(wrong))
        if wrong:
            say('NEG-ARM FAIL')
            return 1
        say('NEG-ARM PASS')
        return 0

    stale = [k for k, v in results.items() if v['verdict'].startswith('STALE')]
    say('')
    say('VERDICT: ' + str(len(stale)) + ' of ' + str(len(results))
        + ' artefact(s) STALE against the source they describe'
        + (' (' + ', '.join(stale) + ')' if stale else '')
        + '; refreshing any of them needs a launch, which the owner order forbids, so '
          'they are DECLARED stale here instead of silently read as current')
    return 0


if __name__ == '__main__':
    sys.exit(main())
