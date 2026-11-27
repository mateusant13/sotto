"""The REDUX caption queue is bounded and COUNTS what it drops (fixlist f:851).

`ReduxHiddenSwitch.__init__` used `queue.Queue()`: a consumer that stops
(`drain_captions` on the ASR thread) grew the queue without limit while the
panel was hidden. The producers now go through `_put_caption`, which uses
`put_nowait`, increments `caption_drops`, and says so in the log and in
`REDUX_SWITCH_STOP`.

  R1  the constructor really builds a bounded queue, both producers call the
      guarded helper, and the summary publishes `caption_drops`;
  R2  the helper, compiled from the real source and driven with a 2-slot fake
      queue, never blocks, keeps exactly 2 lines and counts the 8 losses.

INSTRUMENT, IN PROCESS: no model, no runner, no subprocess, no window.

    python _main/redux-caption-bound-oracle.py            # rc 0 green
    python _main/redux-caption-bound-oracle.py --neg-arm  # rc 1 = 2 mutants CAUGHT
"""
import os
import queue
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SWITCH = os.environ.get('SOTTO_REDUX_ORACLE_SWITCH') or os.path.join(
    REPO, 'worker', 'engine_switch.py')

CTOR_OLD = '        self._captions = queue.Queue(maxsize=1024)'
CTOR_NEW = '        self._captions = queue.Queue()'
COUNT_OLD = '            self.caption_drops += 1'
COUNT_NEW = '            pass  # mutant: the loss is invisible'


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def put_helper(source):
    start = source.index('    def _put_caption(self, payload):')
    end = source.index('    def drain_captions(self):', start)
    ns = {'queue': queue}
    exec(compile(textwrap.dedent(source[start:end]), SWITCH, 'exec'), ns)
    return ns['_put_caption']


class _Stub(object):
    def __init__(self, cap=2):
        self._captions = queue.Queue(maxsize=cap)
        self.caption_drops = 0
        self.logs = []

    def log(self, message):
        self.logs.append(message)


def arms(source):
    out = []
    bounded = ('self._captions = queue.Queue(maxsize=' in source
               and source.count('self._put_caption({') == 2
               and 'caption_drops={self.caption_drops}' in source)
    out.append(('R1 construtor limitado, dois produtores, resumo publica',
                bounded,
                {'ctor': [ln.strip() for ln in source.splitlines()
                          if 'self._captions = queue.Queue(' in ln],
                 'producers': source.count('self._put_caption({')}))

    stub = _Stub()
    helper = put_helper(source)
    for i in range(10):
        helper(stub, {'type': 'caption', 'text': 'line-%d' % i})
    kept = stub._captions.qsize()
    drops = stub.caption_drops
    named = [m for m in stub.logs if m.startswith('REDUX_CAPTION_DROP ')]
    out.append(('R2 helper NAO bloqueia, retem 2 e CONTA 8',
                kept == 2 and drops == 8 and len(named) == 3
                and 'drops=1 cap=2' in named[0],
                {'kept': kept, 'drops': drops, 'named': named[:3]}))
    return out


def run(source=None):
    source = source if source is not None else read(SWITCH)
    ok_all = True
    for label, ok, detail in arms(source):
        print('%-52s %s %s' % (label, 'GREEN' if ok else 'RED', detail))
        ok_all = ok_all and ok
    print('VERDICT: ' + ('PASS' if ok_all else 'FAIL'))
    return 0 if ok_all else 1


def neg_arm():
    text = read(SWITCH)
    caught = 0
    for name, old, new, arm in (
            ('fila-sem-limite', CTOR_OLD, CTOR_NEW, 0),
            ('conta-apagada', COUNT_OLD, COUNT_NEW, 1)):
        if text.count(old) != 1:
            print('NEG-ARM %s: ancora encontrada %d vez(es)' % (name, text.count(old)))
            return 2
        ok = arms(text.replace(old, new))[arm][1]
        print('NEG-ARM %-18s %s' % (name, 'CAUGHT (arm RED)' if not ok else '** INERT **'))
        caught += 0 if ok else 1
    print('NEG-ARM %d of 2 mutant(s) caught' % caught)
    return 1 if caught == 2 else 0


if __name__ == '__main__':
    sys.exit(neg_arm() if '--neg-arm' in sys.argv[1:] else run())
