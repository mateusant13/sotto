"""Revive lifts the PUBLISHED park key, not only the in-memory latches (f:21367).

`_do_revive` used to set `_paused/_external_parked/_vram_parked = False` and
leave `panel-visibility.json:park='vram'` published. The worker kept shedding
the engine after a fresh worker had been started. Now the same owner as every
other path calls `set_engine_park(None)`.

  V1  revive clears the three latches, calls `set_engine_park(None)` exactly
      once, stops the old child with reason=revive and starts a new worker;
  V2  doing it twice does not republish anything (the key stays `None`).

INSTRUMENT, IN PROCESS. Fake bridge/policy, no subprocess, no window.

    python _main/revive-park-owner-oracle.py            # rc 0 green
    python _main/revive-park-owner-oracle.py --neg-arm  # rc 1 = mutant CAUGHT
"""
import importlib.util
import os
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.environ.get('SOTTO_REVIVE_PARK_SHELL') or os.path.join(
    REPO, 'app', 'webview', 'sotto_webview.py')
OLD = '            self.set_engine_park(None)\n            if bridge is not None:'
NEW = '            if bridge is not None:'


def load(path, name):
    for extra in (os.path.dirname(path), os.path.join(REPO, 'app', 'webview')):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Child(object):
    pid = 4242


class _Bridge(object):
    def __init__(self):
        self.child = _Child()
        self.stops = []
        self.pending_error = 'old-error'
        self.no_audio = True
        self.no_audio_evidence = 'old'
        self.no_audio_evidence_at = 1.0

    def stop(self, reason):
        self.stops.append(reason)
        self.child = None
        return True


def fake_shell():
    s = type('ReviveStub', (), {})()
    s.bridge = _Bridge()
    s._reload_policy = type('Policy', (), {'stop': lambda self: None})()
    s.old_bridge = s.bridge
    s._paused = True
    s._external_parked = True
    s._vram_parked = True
    s._engine_park = 'vram'
    s.parks = []
    s.starts = []
    s.logs = []
    s._revive_lock = threading.Lock()
    s._revive_thread = object()
    s.set_engine_park = lambda reason: (
        s.parks.append(reason), setattr(s, '_engine_park', reason), True)[2]
    def start_worker(reason):
        s.starts.append(reason)
        s.bridge = _Bridge()
        return True
    s.start_worker = start_worker
    return s


def arms(mod):
    mod.log = lambda message: None
    s = fake_shell()
    out = []
    mod.SottoShell._do_revive(s, 'oracle')
    ok1 = (s.parks == [None] and s._engine_park is None
           and not (s._paused or s._external_parked or s._vram_parked)
           and s.old_bridge.stops == ['revive'] and s.starts == ['revive'])
    out.append(('V1 revive levanta a chave publicada e reinicia', ok1,
                {'parks': list(s.parks), 'park': s._engine_park,
                 'latches': [s._paused, s._external_parked, s._vram_parked],
                 'stops': list(s.old_bridge.stops), 'starts': list(s.starts)}))
    mod.SottoShell._do_revive(s, 'oracle-again')
    ok2 = (s.parks == [None, None] and s._engine_park is None
           and s.starts == ['revive', 'revive'])
    out.append(('V2 um segundo revive nao republica', ok2,
                {'parks': list(s.parks), 'starts': list(s.starts)}))
    return out


def run(path=SHELL):
    ok_all = True
    for label, ok, detail in arms(load(path, 'revivepark_%d' % os.getpid())):
        print('%-52s %s %s' % (label, 'GREEN' if ok else 'RED', detail))
        ok_all = ok_all and ok
    print('VERDICT: ' + ('PASS' if ok_all else 'FAIL'))
    return 0 if ok_all else 1


def neg_arm():
    with open(SHELL, encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    if text.count(OLD) != 1:
        print('NEG-ARM: ancora encontrada %d vez(es)' % text.count(OLD))
        return 2
    tmp = tempfile.mkdtemp(prefix='revivepark-neg-')
    path = os.path.join(tmp, 'neg_shell.py')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text.replace(OLD, NEW))
    caught = 0
    for label, ok, detail in arms(load(path, 'revivepark_neg')):
        print('NEG-ARM %-46s %s %s'
              % (label, 'RED as expected' if not ok else '** INERT **', detail))
        caught += 0 if ok else 1
    print('NEG-ARM %d of 2 arm(s) caught' % caught)
    return 1 if caught == 2 else 0


if __name__ == '__main__':
    sys.exit(neg_arm() if '--neg-arm' in sys.argv[1:] else run())
