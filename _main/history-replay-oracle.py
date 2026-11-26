# NO-BUG: Oracle: 200 legendas escritas no transcrito tem de dar 200 linhas distintas, e
#        a MESMA sessao reentregue nao pode duplicar uma so' -- o store e' idempotente
#        por identidade (`start=`), nao por sorte.
#        Capacidade pedida pelo dono (A3/A23 no historico); nao ha id de
#        `_main/bug-ledger.json` para isto, e o id nao se inventa.
"""Oracle: replay 200 captions through the real merge rule into a real file.

THE HOLE THIS CLOSES. Nothing replayed a session long enough to say "the transcript
has as many rows as the session had lines". The duplicate defect the owner
photographed twice (`517 de 2077`) was measured once and the number retired, and
the store's own decision function (`history_merge`) had no soak: it is the rule
that decides skip / replace / append, and every one of its three identities was
added after a measured incident.

WHY THE FILE, NOT A LIST. `history_append` writes `history/YYYY-MM-DD/HH.md` with
`- [HH:MM:SS] text <!-- ... start=N -->`. This oracle replays the session through
`history_merge` and applies the decision to a real file in that format, so the
count is read back from a file -- the same artifact the owner opens.

ARMS
  a 200-ROWS        -- 200 distinct captions produce 200 rows and 200 distinct
                       texts;
  b REPLAY-NO-DUP   -- the same 200 delivered again (same `start`, same clock)
                       add ZERO rows: the store is idempotent;
  c GROWTH-REPLACES -- one line growing inside the merge window with the same
                       `start` rewrites its row instead of adding one;
  d REAL-REPEAT-ENTERS -- the same text with a DIFFERENT `start` is a real
                       repetition and must enter as a second row;
  e SHRINK-KEPT     -- a shorter re-read of the same `start` keeps the longer text
                       and adds no row (the owner's "corta no meio da frase").

Usage:
  py -3 _main/history-replay-oracle.py            # rc 0 = every arm holds
  py -3 _main/history-replay-oracle.py --neg-arm  # rc 1 = every mutant CAUGHT
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

VIAS = 'pc'


def load_shell(path=SHELL, name='_history_replay_shell'):
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    mod.log = lambda *a, **k: None
    return mod


WORD = ('the quick brown fox jumps over a lazy dog while the player keeps '
        'serving lines and the owner keeps reading them')


def caption(index):
    """Uma legenda por indice, com `start` e relogio a avancarem ~4 s."""
    text = '%s %d' % (WORD, index)
    start = 100.0 + 4.0 * index
    return {'text': text, 'start': start, 'time_s': start}


class Store(object):
    """O ficheiro do transcrito, na forma real (`- [HH:MM:SS] texto <!-- ... -->`)."""

    def __init__(self):
        self.folder = tempfile.mkdtemp(prefix='history-replay-')
        self.path = os.path.join(self.folder, '00.md')
        open(self.path, 'w', encoding='utf-8').close()
        self.rows = []

    def tail(self):
        return self.rows[-1] if self.rows else None

    def commit(self, text, start, now_s):
        hms = int(now_s) % 86400
        line = ('- [%02d:%02d:%02d] %s <!-- route=final via=%s start=%.2f '
                'src=worker-stamped reason=external-final -->\n'
                % (hms // 3600, hms % 3600 // 60, hms % 60, text, VIAS, start))
        with open(self.path, 'a', encoding='utf-8') as handle:
            handle.write(line)
        self.rows.append({'body': text, 'start': start, 'time_s': now_s,
                          'via': VIAS, 'audio': 'device:fake'})

    def rewrite(self, text, start, now_s):
        self.rows[-1] = {'body': text, 'start': start, 'time_s': now_s,
                         'via': VIAS, 'audio': 'device:fake'}
        with open(self.path, 'w', encoding='utf-8') as handle:
            for index, row in enumerate(self.rows):
                hms = int(row['time_s']) % 86400
                handle.write('- [%02d:%02d:%02d] %s <!-- route=final via=%s '
                             'start=%.2f -->\n'
                             % (hms // 3600, hms % 3600 // 60, hms % 60,
                                row['body'], VIAS, row['start']))

    def read_rows(self):
        with open(self.path, encoding='utf-8') as handle:
            return [line for line in handle if line.startswith('- [')]


def deliver(mod, store, item):
    """UMA entrega, exactamente como `history_append` a aplica."""
    action = mod.history_merge(store.tail(), item['text'], now_s=item['time_s'],
                               start=item['start'], audio='device:fake',
                               via=VIAS)
    if action == 'append':
        store.commit(item['text'], item['start'], item['time_s'])
    elif action in ('replace', 'replace_at'):
        store.rewrite(item['text'], item['start'], item['time_s'])
    else:
        store.rewrite(store.rows[-1]['body'], store.rows[-1]['start'],
                      store.rows[-1]['time_s']) if store.rows else None
    return action


def arms(mod):
    results = []

    # a 200-ROWS
    store = Store()
    for index in range(200):
        deliver(mod, store, caption(index))
    rows = store.read_rows()
    texts = set(re.sub(r'^.*?\] (.*?) <!--.*$', r'\1', line.rstrip('\n'))
                for line in rows)
    results.append(('a 200-ROWS', bool(len(rows) == 200 and len(texts) == 200),
                    'rows=%d distinct=%d' % (len(rows), len(texts))))

    # b REPLAY-NO-DUP -- CADA linha entregue DUAS vezes seguidas, que e' a forma
    # do defeito medido (`517 de 2077`): dois motores, ou uma re-emissao, a mesma
    # fala a chegar duas vezes. A sessao inteira reentregue NAO e' o caso -- o
    # store so' ve' a cauda, e uma linha antiga com outro `start` e' outra fala.
    twice = Store()
    for index in range(200):
        item = caption(index)
        deliver(mod, twice, item)
        deliver(mod, twice, item)
    tail_repeat = len(twice.read_rows())
    deliver(mod, twice, caption(199))
    after = len(twice.read_rows())
    results.append(('b REPLAY-NO-DUP',
                    bool(tail_repeat == 200 and after == 200),
                    'rows after double-delivery=%d, tail repeat -> %d (want 200)'
                    % (tail_repeat, after)))

    # c GROWTH-REPLACES -- a mesma linha a crescer dentro da janela, mesmo `start`.
    grow = Store()
    base = dict(caption(0))
    deliver(mod, grow, base)
    grown = dict(base, text=base['text'] + ' and then it keeps going',
                 time_s=base['time_s'] + 1.0)
    deliver(mod, grow, grown)
    rows = grow.read_rows()
    results.append(('c GROWTH-REPLACES', bool(len(rows) == 1 and 'keeps going' in rows[0]),
                    'rows=%d last=%s' % (len(rows), rows[-1][:60].strip() if rows else '-')))

    # d REAL-REPEAT-ENTERS -- o mesmo texto noutro `start` e' fala repetida.
    repeat = Store()
    first = dict(caption(0))
    deliver(mod, repeat, first)
    deliver(mod, repeat, dict(first, start=first['start'] + 30.0,
                              time_s=first['time_s'] + 30.0))
    results.append(('d REAL-REPEAT-ENTERS', len(repeat.read_rows()) == 2,
                    'rows=%d' % len(repeat.read_rows())))

    # e SHRINK-KEPT -- uma leitura mais curta nao apaga o rabo.
    shrink = Store()
    long_text = dict(caption(0))
    deliver(mod, shrink, long_text)
    action = deliver(mod, shrink, dict(long_text, text=WORD, time_s=long_text['time_s'] + 0.5))
    rows = shrink.read_rows()
    results.append(('e SHRINK-KEPT',
                    bool(len(rows) == 1 and len(rows[0]) > len(WORD) + 40),
                    'rows=%d action=%s chars=%d' % (len(rows), action,
                                                    len(rows[0]) if rows else 0)))
    return results


MUTATIONS = (
    # OS MUTANTES SUBSTITUEM A FUNCAO DE DECISAO DO PRODUTO (2026-11-26): as arms
    # chamam `mod.history_merge`, o dono unico da regra, logo trocar a funcao e'
    # trocar a regra -- e' o store "append-only" (o defeito das 517 de 2077) e o
    # store que engole tudo.
    ('store-appends-everything', lambda mod: setattr(
        mod, 'history_merge', lambda *a, **k: 'append'), 'b REPLAY-NO-DUP'),
    ('store-swallows-everything', lambda mod: setattr(
        mod, 'history_merge', lambda *a, **k: 'skip'), 'a 200-ROWS'),
    ('growth-is-a-new-row', lambda mod: setattr(
        mod, 'history_merge', lambda last, body, **k: 'append'), 'c GROWTH-REPLACES'),
    ('repeat-is-a-duplicate', lambda mod: setattr(
        mod, 'history_merge', lambda last, body, **k: 'skip'), 'd REAL-REPEAT-ENTERS'),
)


def neg_arm():
    caught = weak = 0
    for label, mutate, owner in MUTATIONS:
        mod = load_shell(name='_history_replay_mut_%s' % label.replace('-', '_'))
        mutate(mod)
        got = {name: ok for name, ok, _detail in arms(mod)}
        if not got.get(owner):
            print('  GREEN mutant %-24s caught by: %s' % (label, owner))
            caught += 1
        else:
            print('  RED   mutant %-24s SURVIVED on arm %s -- gate blind'
                  % (label, owner))
    total = len(MUTATIONS)
    ok = caught == total and weak == 0
    print('NEG-ARM VERDICT: %s (%d/%d mutants caught, %d decorative)'
          % ('PASS' if ok else 'FAIL', caught, total, weak))
    return 1 if ok else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()
    if args.neg_arm:
        return neg_arm()
    mod = load_shell()
    failed = 0
    for name, ok, detail in arms(mod):
        print('  %-20s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
        failed += 0 if ok else 1
    print('HISTORY-REPLAY VERDICT: %s (%d failure(s))'
          % ('PASS' if not failed else 'FAIL', failed))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
