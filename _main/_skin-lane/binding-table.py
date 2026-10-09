"""The per-design binding resolution table, read off the artifact.

Exit code is the verdict: 0 only when every design resolved `live` AND `historyRow`,
because those two are the decorated keys the integrator cannot work without.

Usage:  py -3 _main/_skin-lane/binding-table.py [skin-dir]
"""
import io
import json
import os
import sys

KEYS = ['live', 'wordTemplate', 'caret', 'speaker', 'statusWord', 'meter',
        'historyList', 'historyRow', 'historyTime']
MUST = ['live', 'historyRow']


def main(argv):
    skin = argv[1] if len(argv) > 1 else r'H:\sotto\app\panel\skins\cinematic-2'
    with io.open(os.path.join(skin, 'index.json'), encoding='utf-8') as fh:
        idx = json.load(fh)

    designs = idx['designs']
    print('zip=%s  designs=%d  complete=%s  css=%s  viewport=%s'
          % (idx['zip'], len(designs), idx.get('complete'), idx['css'], idx['viewport']))
    print('')

    width = max(len(d) for d in designs) + 2
    head = 'design'.ljust(width) + ''.join(k[:11].ljust(12) for k in KEYS)
    print(head)
    print('-' * len(head))

    total = {k: 0 for k in KEYS}
    nulls = {k: [] for k in KEYS}
    failed = []
    for d in designs:
        b = idx['bindings'][d]
        cells = ''
        for k in KEYS:
            ok = b.get(k) is not None
            total[k] += 1 if ok else 0
            if not ok:
                nulls[k].append(d)
            cells += ('yes' if ok else 'NULL').ljust(12)
        missing = [k for k in MUST if b.get(k) is None]
        if missing:
            failed.append((d, missing))
        print(d.ljust(width) + cells + ('  <-- MISSING ' + ','.join(missing) if missing else ''))

    print('')
    print('resolved per key (of %d):' % len(designs))
    for k in KEYS:
        tag = ' MUST' if k in MUST else ''
        print('  %-14s %2d/%d%s%s' % (k, total[k], len(designs), tag,
                                      ('   null for: ' + ', '.join(nulls[k])) if nulls[k] else ''))

    print('')
    print('strategies used:')
    strat = {}
    for d in designs:
        for k, p in idx['bindingProof'][d].items():
            if p.get('resolved'):
                strat.setdefault(p.get('strategy'), []).append('%s.%s' % (d, k))
    for s, hits in sorted(strat.items()):
        print('  %-16s %d' % (s, len(hits)))
    uniq = sum(1 for d in designs for k, p in idx['bindingProof'][d].items()
               if p.get('resolved') and not p.get('unique'))
    print('  resolved but NOT unique: %d' % uniq)

    print('')
    census = [d for d in designs if idx['stats'][d]['liveCensus']]
    if census:
        sample = census[0]
        print('the live line, as the vendor builds it (%s):' % sample)
        c = idx['stats'][sample]['liveCensus']
        print('  <%s class="%s"> with %d children,' % (c['tag'], c['cls'], c['childCount']))
        print('  children: %s' % (c['children'][:6],))

    if failed:
        print('')
        print('VERDICT: FAIL - %d design(s) did not resolve a MUST key' % len(failed))
        for d, m in failed:
            print('   %s: %s' % (d, ','.join(m)))
        return 1
    print('')
    print('VERDICT: PASS - every design resolved %s' % ' and '.join(MUST))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
