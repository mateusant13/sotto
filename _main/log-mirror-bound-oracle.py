"""The --log MIRROR is bounded and COUNTS what it drops (fixlist class f:2510).

Before the fix `sotto_webview.py:2510` built `queue.SimpleQueue()`: a stalled
`sotto-log` thread turned every `log()` line into resident memory for ever, with
no counter and no marker. The stdout sibling already had the right shape
(`_STDOUT_CAP`, `put_nowait`, `_STDOUT_DROPPED`, `LOG_STDOUT_SUPPLIED`); the
mirror now uses the same shape.

  L1  the mirror queue is a `queue.Queue` with a real `maxsize`;
  L2  a flood past the cap counts the loss and publishes a
      `LOG_MIRROR_SUPPLIED dropped=N` line when the file drains.

INSTRUMENT, IN PROCESS. No shell, no worker, no browser, no window. The writer
thread is stubbed so the queue stays full and the arms are deterministic.

    python _main/log-mirror-bound-oracle.py            # rc 0 green
    python _main/log-mirror-bound-oracle.py --neg-arm  # rc 1 = mutant CAUGHT
"""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.environ.get('SOTTO_LOG_ORACLE_SHELL') or os.path.join(
    REPO, 'app', 'webview', 'sotto_webview.py')
CAP = 8
OLD = '        _LOG_QUEUE = queue.Queue(maxsize=_LOG_CAP)'
MUTANT = '        _LOG_QUEUE = queue.SimpleQueue()'


class _NoThread(object):
    """The writer never runs: a full queue must stay full for the flood arm."""

    def start(self):
        return None

    def join(self, _timeout=None):
        return None

    def is_alive(self):
        return False


def load(path, name):
    for extra in (os.path.dirname(path), os.path.join(REPO, 'app', 'webview')):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def arms(mod):
    tmp = tempfile.mkdtemp(prefix='log-mirror-oracle-')
    path = os.path.join(tmp, 'mirror.log')
    mod._LOG_DROPPED = 0
    mod._LOG_WRITER = _NoThread()
    mod._STDOUT_WRITER = _NoThread()
    mod._STDOUT_SINK = {'dead': True, 'err': ''}
    mod._open_log(path)
    out = []
    q = mod._LOG_QUEUE
    size = getattr(q, 'maxsize', None)
    out.append(('L1 fila do espelho LIMITADA',
                size == CAP and hasattr(q, 'put_nowait'),
                {'type': type(q).__name__, 'maxsize': size}))
    try:
        for i in range(200):
            mod.log('FLOOD %03d' % i)
        dropped = mod._LOG_DROPPED
        # Faz espaço, depois uma linha nova PUBLICA a perda, como no stdout.
        mod._log_drain_inline()
        mod.log('AFTER_SUPPLY')
        mod._log_drain_inline()
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        supplied = [line for line in text.splitlines()
                    if 'LOG_MIRROR_SUPPLIED dropped=' in line]
        ok = (dropped > 0 and len(supplied) == 1
              and ('dropped=%d ' % dropped) in supplied[0]
              and 'AFTER_SUPPLY' in text)
        out.append(('L2 perda CONTADA e PUBLICADA no ficheiro', ok,
                    {'dropped': dropped, 'supplied': supplied[:1],
                     'queued': mod._LOG_QUEUE.qsize()}))
    finally:
        if mod._LOG_FILE is not None:
            mod._LOG_FILE.close()
            mod._LOG_FILE = None
    return out


def run(path=SHELL):
    mod = load(path, 'logmirror_%d' % os.getpid())
    mod._LOG_CAP = CAP
    ok_all = True
    for label, ok, detail in arms(mod):
        print('%-46s %s %s' % (label, 'GREEN' if ok else 'RED', detail))
        ok_all = ok_all and ok
    print('VERDICT: ' + ('PASS' if ok_all else 'FAIL'))
    return 0 if ok_all else 1


def neg_arm():
    with open(SHELL, encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    if text.count(OLD) != 1:
        print('NEG-ARM: ancora ausente (%d)' % text.count(OLD))
        return 2
    tmp = tempfile.mkdtemp(prefix='log-mirror-neg-')
    path = os.path.join(tmp, 'neg_shell.py')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text.replace(OLD, MUTANT))
    caught = 0
    for label, ok, detail in arms(load(path, 'logmirror_neg')):
        print('NEG-ARM %-38s %s %s'
              % (label, 'RED as expected' if not ok else '** INERT **', detail))
        caught += 0 if ok else 1
    print('NEG-ARM %d of 2 arm(s) caught' % caught)
    return 1 if caught == 2 else 0


if __name__ == '__main__':
    sys.exit(neg_arm() if '--neg-arm' in sys.argv[1:] else run())
