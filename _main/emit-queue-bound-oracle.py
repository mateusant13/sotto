"""Oracle: the UI emit queue is BOUNDED -- one pending post per channel.

INSTRUMENT, IN PROCESS. It never launches the shell, the worker or a browser: it
imports app/webview/sotto_webview.py, builds a shell with object.__new__ (so no
__init__, no window, no locks) and stubs the only two things emit_async touches --
_post (the BeginInvoke) and the WebView2 core (ExecuteScriptAsync).

THE CLAIM, verbatim from emit_async's own contract: every payload is a WHOLE
state and the panel is a pure function of the last one it saw. So N pushes that
arrive while the UI thread has not drained must collapse into ONE script, and
that script must carry the NEWEST payload. The counter-claim is the defect the
owner's freeze report put on the table: one posted callable per push, unbounded
(43 pushes/s measured on the stats feed).

Usage:
  py -3 _main/emit-queue-bound-oracle.py             # the live shell
  py -3 _main/emit-queue-bound-oracle.py --neg-arm   # the coalescing guard
                                                     # removed -> must go RED
"""
import argparse
import importlib.util
import os
import sys
import threading
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
GUARD = '        if already:\n            return\n'
MUTANT = os.path.join(os.path.dirname(SHELL), '_emit-neg-shell.py')


class FakeGeneric(object):
    """Stands in for Func[Object] / Action[Task[String]] -- subscript AND call."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, fn=None):
        self.fn = fn

    def __call__(self, *a, **k):
        return self.fn(*a, **k)


def install_system_fakes():
    """emit_async does its .NET imports INSIDE the method; feed it fakes."""
    sysmod = types.ModuleType('System')
    sysmod.Func = FakeGeneric
    sysmod.Action = FakeGeneric
    sysmod.Object = object
    sysmod.String = str
    sysmod.Type = type
    thr = types.ModuleType('System.Threading')
    tasks = types.ModuleType('System.Threading.Tasks')
    tasks.Task = FakeGeneric
    thr.Tasks = tasks
    sysmod.Threading = thr
    sys.modules['System'] = sysmod
    sys.modules['System.Threading'] = thr
    sys.modules['System.Threading.Tasks'] = tasks


class FakeCore(object):
    def __init__(self):
        self.scripts = []

    def ExecuteScriptAsync(self, script):
        self.scripts.append(script)

        class T(object):
            IsFaulted = False

            def ContinueWith(self, cb):
                cb(self)

        return T()


class FakeWV2(object):
    def Invoke(self, fn):
        return fn()


def load_shell(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    d = os.path.dirname(os.path.abspath(path))
    if d not in sys.path:
        sys.path.insert(0, d)
    spec.loader.exec_module(mod)
    return mod


def make_shell(mod, posted):
    shell = object.__new__(mod.SottoShell)
    shell._post = lambda fn: posted.append(fn)
    shell.webview2 = FakeWV2()
    shell.core = FakeCore()
    return shell


def arm(mod, label):
    """Returns the list of FAILURES for one shell revision ([] == GREEN)."""
    failures = []

    posted = []
    s = make_shell(mod, posted)
    for i in range(100):
        s.emit_async('stats', {'marker': 'M%d' % i})
    if len(posted) != 1:
        failures.append('%s: 100 undrained pushes posted %d callable(s), expected 1'
                        % (label, len(posted)))
    for fn in posted:
        fn()
    if len(s.core.scripts) != 1:
        failures.append('%s: draining posted[0] sent %d script(s), expected 1'
                        % (label, len(s.core.scripts)))
    script = s.core.scripts[0] if s.core.scripts else ''
    if 'M99' not in script:
        failures.append('%s: the script does not carry the NEWEST payload (M99): %r'
                        % (label, script[-80:]))
    if 'M98' in script:
        failures.append('%s: the script carries a STALE payload (M98)' % label)

    before = len(posted)
    s.emit_async('stats', {'marker': 'M100'})
    if len(posted) != before + 1:
        failures.append('%s: after a drain the next push did not post a callable'
                        % label)

    posted2 = []
    s2 = make_shell(mod, posted2)
    s2.emit_async('stats', {'marker': 'A'})
    s2.emit_async('meter', {'marker': 'B'})
    if len(posted2) != 2:
        failures.append('%s: two channels shared one pending slot (%d post(s))'
                        % (label, len(posted2)))

    posted3 = []
    s3 = make_shell(mod, posted3)
    errs = []

    def hammer():
        try:
            for i in range(250):
                s3.emit_async('stats', {'marker': 'T%d' % i})
        except Exception as exc:  # noqa: BLE001
            errs.append(repr(exc))

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errs:
        failures.append('%s: concurrent pushes raised %s' % (label, errs[:2]))
    if len(posted3) != 1:
        failures.append('%s: 1000 concurrent pushes posted %d callable(s), expected 1'
                        % (label, len(posted3)))
    # THE DROP PATH. _post returns False when the form does not exist yet: the
    # callable was NOT queued. The latch must not stick on that answer -- a
    # channel that goes permanently silent is a worse failure than the queue this
    # bound exists to fix. Without the release this reads 1 of 3.
    posted4 = []

    def drop(fn):
        posted4.append(fn)
        return False

    s4 = make_shell(mod, posted4)
    s4._post = drop
    for i in range(3):
        s4.emit_async('stats', {'marker': 'D%d' % i})
    if len(posted4) != 3:
        failures.append('%s: a DROPPED post stuck the latch: %d of 3 pushes posted'
                        % (label, len(posted4)))
    return failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()
    install_system_fakes()
    print('shell : %s' % SHELL)
    print('bytes : %d' % os.path.getsize(SHELL))

    failures = []
    if args.neg_arm:
        with open(SHELL, encoding='utf-8') as fh:
            text = fh.read()
        mutant = text.replace(GUARD, GUARD.replace('return', 'pass'), 1)
        if mutant == text:
            print('NEG-ARM: the guard line was not found -- the control is DEAD')
            return 1
        with open(MUTANT, 'w', encoding='utf-8', newline='') as fh:
            fh.write(mutant)
        print('mutant: %s (%d B, guard replaced by pass)' % (MUTANT, os.path.getsize(MUTANT)))
        try:
            mod = load_shell(MUTANT, 'sotto_shell_emit_mutant')
            got = arm(mod, 'MUTANT')
        finally:
            try:
                os.remove(MUTANT)
            except OSError:
                pass
        red = bool(got)
        print('NEG-ARM: %s' % ('RED as expected' if red else 'STILL GREEN -- the oracle cannot say no'))
        for line in got:
            print('   ' + line)
        return 0 if red else 1

    mod = load_shell(SHELL, 'sotto_shell_emit_live')
    failures = arm(mod, 'LIVE')
    for line in failures:
        print('   FAIL ' + line)
    print('VERDICT: ' + ('FAIL' if failures else 'PASS'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
