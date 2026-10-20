#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ORACLE: a BUSY UI THREAD CANNOT FREEZE THE SHELL, AND A STALL SAYS SO.

INSTRUMENT, IN PROCESS. It never launches the shell, the worker, a browser or
an audio device: it imports `app/webview/sotto_webview.py`, builds a shell
with `object.__new__` (no `__init__`, no window, no locks) and stubs the only
things the paths under test touch -- the WinForms `form` (a `BeginInvoke` that
records the delegate and NEVER runs it: a UI thread busy for longer than any
budget), the WebView2 control and the script core.

THE MEASUREMENT THIS GATE IS BUILT ON (the owner's own log,
`I:\\cc-tmp\\sotto-012524.log`, the app launched at 01:25:24):

    WARN UI_THREAD_STALL begin-invoke not run in 10 s fn=_run    93 occurrences
    WARN exec_js TIMEOUT after 10.0s script='window.__sotto_stats("sNNNN"...)'
                                                                     68 occurrences

ALL of them inside ONE 50 s window (01:55:30 -> 01:56:20), while a design lane
was rendering 45 themes with headless Edge. The LOAD is the TRIGGER; the CODE
is the FREEZE, and the code has to hold under load.

THE CHAIN, read in the code:

    panel.js  -> getStats() every 1000 ms
              -> _stats()            (the shell's message dispatch)
              -> reply_stats()      -> exec_js(...)   SYNCHRONOUS, 10 s budget
              -> _ui(_run)          -> form.BeginInvoke(...) + done.wait(10)

A busy UI thread therefore did not only delay the stats: it HELD the PUMP
thread -- the one that carries the captions -- for 10 s at a time, 93 times.
And `exec_js` waited TWICE (10 s inside `_ui`, then the caller's own budget
again), so one stalled pull cost up to 20 s of a caption-carrying thread.

WHAT THIS GATE PROVES (the live shell must hold every arm):

  ARM 1  the stats reply does NOT hold its caller when the UI thread is busy
  ARM 2  N replies with a busy UI leave AT MOST ONE posted callable (measured)
  ARM 3  after the UI drains, EVERY id is answered -- the panel's Promise
         resolves; an unanswered id would hang it FOREVER
  ARM 4  a stall is DISTINGUISHABLE from a legitimate `None`, and it carries
         the reason and what was asked; a legitimate null answer is still None
  ARM 5  `emit_async`'s latch (2026-10-11) still holds: N pushes -> 1 callable,
         carrying the NEWEST payload
  ARM 6  the panel-state DUMP (a diagnostic, every 2 s) does not block and does
         not grow the WinForms queue

AND THE NEGATIVE ARM IS EXECUTED, not described: FOUR broken copies of today's
shell are built and run against the same arms, and each one has to turn RED on
its OWN claim. A gate that cannot say NO is decoration.

  M1 sync-reply       `reply_stats` back to the SYNCHRONOUS `exec_js` -> it
                      BLOCKS the caller -> RED on ARM 1
  M2 unbounded-reply  one posted callable per reply -> RED on ARM 2
  M3 silent-stall     the stall answers a bare `None`, with no reason -> RED on
                      ARM 4
  M4 emit-latch-off   `emit_async`'s coalescing guard removed -> RED on ARM 5

WHAT IT DOES NOT PROVE (read this before quoting it):

  * the UI thread here is a FAKE one. The real WinForms message loop, the
    real WebView2 and the real load that caused the 93 stalls are NOT in this
    process. What is measured is the shell's REACTION to a UI thread that does
    not drain, which is the half the shell owns;
  * the TRIGGER of the incident was a design lane rendering 45 themes with
    headless Edge at the same time. This gate reproduces the CONSEQUENCE (a UI
    thread that does not drain), not the load;
  * no caption latency is measured here. The claim is structural: the reply no
    longer waits on the UI thread, so it cannot hold the pump thread.

Usage:
  py -3 _main/ui-stall-oracle.py     # the live shell + the four mutants
"""
import argparse
import importlib.util
import io
import os
import sys
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
SHELL_DIR = os.path.dirname(SHELL)

#: The reply must not hold its caller for longer than this. The budget is
#: deliberately generous: the claim is "bounded", not "instant".
REPLY_BUDGET_S = 2.0
#: How many replies the bounded-post arm makes.
REPLY_CALLS = 50
#: The budget the diagnostic dump gets.
DUMP_BUDGET_S = 1.0


# ---------------------------------------------------------------------------
# the .NET stubs
# ---------------------------------------------------------------------------
class FakeGeneric(object):
    """Stands in for Func[Object] / Action[Task[String]] -- subscript AND call."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, fn=None):
        self.fn = fn

    def __call__(self, *a, **k):
        return self.fn(*a, **k)


def install_system_fakes():
    """The shell imports `System` INSIDE the methods; feed it fakes."""
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
    """The script core: it remembers every script it was asked to run."""

    def __init__(self, result='null'):
        self.scripts = []
        self.result = result

    def ExecuteScriptAsync(self, script):
        self.scripts.append(script)
        core = self

        class T(object):
            IsFaulted = False

            def ContinueWith(self, cb):
                cb(self)

            @property
            def Result(self):
                return core.result

        return T()


class FakeWV2(object):
    def Invoke(self, fn):
        return fn()


class BusyForm(object):
    """The WinForms form with a UI thread that NEVER DRAINS.

    `BeginInvoke` records the delegate and returns. That is exactly what a UI
    thread busy for longer than any budget looks like to the caller -- and it
    is the state the owner's app was in for 50 s.
    """

    def __init__(self):
        self.pending = []   # the callables the UI thread has NOT run
        self.count = 0      # how many were EVER posted
        self.InvokeRequired = True

    def BeginInvoke(self, delegate):
        self.count += 1
        self.pending.append(delegate)

    def drain(self):
        pending, self.pending = self.pending, []
        for delegate in pending:
            delegate()
        return len(pending)


class HealthyForm(BusyForm):
    """The same form with a UI thread that answers IMMEDIATELY."""

    def BeginInvoke(self, delegate):
        self.count += 1
        delegate()


def load_shell(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # The SHELL's own directory goes on the path (the shell imports
    # `hot_reload` and `panel_state` from beside it), NOT the mutant's.
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    spec.loader.exec_module(mod)
    return mod


def make_shell(mod, form, core=None):
    """A shell with no `__init__`, no window and no bridge."""
    shell = object.__new__(mod.SottoShell)
    shell.form = form
    shell.webview2 = FakeWV2()
    shell.core = core if core is not None else FakeCore()
    shell.stats_replies = 0
    shell.stats_pushes = 0
    shell.meter_pushes = 0
    shell.stats_logged = 0
    shell.stats_logged_at = 0.0
    # the panel-state dump's own state
    shell.bridge = None
    shell.args = types.SimpleNamespace(hotkey='alt+c',
                                      worker='worker/sotto_worker.py')
    shell.visible = False
    shell.renderer_ready = threading.Event()
    shell.bridge_installed = True
    shell.last_status = ''
    shell.caption_log = []
    shell.reload_count = 0
    shell.panel_visibility = None
    shell.hot_reload = None
    shell._reload_policy = types.SimpleNamespace(state=lambda: {})
    return shell


# ---------------------------------------------------------------------------
# the arms
# ---------------------------------------------------------------------------
def arm_reply_not_blocking(mod):
    """ARM 1: with the UI thread BUSY, the reply does NOT hold its caller.

    The call runs on its own thread and the arm WAITS for it with a budget: a
    reply that waits on the UI thread cannot be interrupted, so the thread is
    simply left behind (it is a daemon) and the arm says so.
    """
    failures = []
    form = BusyForm()
    shell = make_shell(mod, form)
    done = threading.Event()

    def call():
        try:
            shell.reply_stats('s1', {'peak': 0.25, 'blocks': 7})
        finally:
            done.set()

    worker = threading.Thread(target=call, daemon=True)
    started = time.monotonic()
    worker.start()
    finished = done.wait(REPLY_BUDGET_S)
    elapsed = time.monotonic() - started
    if not finished:
        failures.append('ARM1 the reply HELD its caller for more than %.1fs '
                        'while the UI thread was busy' % REPLY_BUDGET_S)
        return failures, True
    if elapsed > REPLY_BUDGET_S:
        failures.append('ARM1 the reply took %.3fs (budget %.1fs)'
                        % (elapsed, REPLY_BUDGET_S))
    return failures, False


def arm_reply_one_post(mod):
    """ARM 2: N replies with a busy UI leave AT MOST ONE posted callable."""
    failures = []
    form = BusyForm()
    shell = make_shell(mod, form)
    for i in range(REPLY_CALLS):
        shell.reply_stats('s%d' % i, {'peak': 0.25, 'blocks': i})
    if form.count != 1:
        failures.append('ARM2 %d replies posted %d callable(s); the bound is 1'
                        % (REPLY_CALLS, form.count))
    return failures


def arm_reply_resolves(mod):
    """ARM 3: after the UI drains, EVERY id is answered.

    An unanswered id leaves the panel's Promise pending FOREVER -- the
    shell's own injected JS resolves ONE id per `__sotto_stats` call.
    """
    failures = []
    form = BusyForm()
    shell = make_shell(mod, form)
    for i in range(REPLY_CALLS):
        shell.reply_stats('s%d' % i, {'peak': 0.25, 'blocks': i})
    form.drain()
    answered = set()
    for script in shell.core.scripts:
        for i in range(REPLY_CALLS):
            if 'window.__sotto_stats("s%d"' % i in script:
                answered.add('s%d' % i)
    missing = ['s%d' % i for i in range(REPLY_CALLS)
               if 's%d' % i not in answered]
    if missing:
        failures.append("ARM3 %d of %d ids were NEVER answered (the panel's "
                        "Promise would hang forever): %s"
                        % (len(missing), REPLY_CALLS, missing[:5]))
    return failures


def arm_stall_is_distinguishable(mod):
    """ARM 4: a stall is NOT the same observation as a legitimate `None`."""
    failures = []
    form = BusyForm()
    shell = make_shell(mod, form)
    value = shell._ui(lambda: None, timeout=0.2)
    if value is None:
        failures.append('ARM4 _ui answered a stall with None: the caller cannot '
                        'tell "the value is None" from "nothing ran"')
    elif not isinstance(value, mod.NoAnswer):
        failures.append('ARM4 _ui answered a stall with %r, not a NoAnswer'
                        % (value,))
    elif value.get('reason') != 'ui-thread-stall':
        failures.append('ARM4 the stall carries no reason: %r' % (dict(value),))
    elif value.get('requested') is None:
        failures.append('ARM4 the stall does not say WHAT was asked: %r'
                        % (dict(value),))

    js = shell.exec_js('window.__sotto_stats("s1","{}")', timeout=0.2)
    if js is None:
        failures.append('ARM4 exec_js answered a stall with None -- that is the '
                        'PANEL_STATS_PROBE null with no reason')
    elif not isinstance(js, mod.NoAnswer):
        failures.append('ARM4 exec_js answered a stall with %r, not a NoAnswer'
                        % (js,))
    elif not js.get('reason'):
        failures.append('ARM4 exec_js answered a stall with no reason: %r'
                        % (dict(js),))

    # THE OTHER HALF: a LEGITIMATE null answer is still None. The sentinel
    # must not swallow the value the page really sent.
    healthy = HealthyForm()
    shell2 = make_shell(mod, healthy, core=FakeCore(result='null'))
    ok = shell2.exec_js('null', timeout=1.0)
    if ok is not None:
        failures.append('ARM4 a LEGITIMATE null answer came back as %r, not None'
                        % (ok,))
    return failures


def arm_emit_latch(mod):
    """ARM 5: `emit_async`'s latch (2026-10-11) still holds."""
    failures = []
    form = BusyForm()
    shell = make_shell(mod, form)
    for i in range(100):
        shell.emit_async('stats', {'marker': 'M%d' % i})
    if form.count != 1:
        failures.append('ARM5 100 undrained pushes posted %d callable(s), '
                        'expected 1' % form.count)
    form.drain()
    if len(shell.core.scripts) != 1:
        failures.append('ARM5 draining the posted callable sent %d script(s), '
                        'expected 1' % len(shell.core.scripts))
    else:
        script = shell.core.scripts[0]
        if 'M99' not in script:
            failures.append('ARM5 the script does not carry the NEWEST payload '
                            '(M99): %r' % script[-80:])
        if 'M98' in script:
            failures.append('ARM5 the script carries a STALE payload (M98)')
    return failures


def arm_dump_does_not_block(mod):
    """ARM 6: the DIAGNOSTIC dump does not block and cannot grow the queue."""
    failures = []
    form = BusyForm()
    shell = make_shell(mod, form)
    started = time.monotonic()
    state = shell.panel_state_snapshot('oracle')
    elapsed = time.monotonic() - started
    if elapsed > DUMP_BUDGET_S:
        failures.append('ARM6 the dump took %.3fs with a busy UI thread '
                        '(budget %.1fs)' % (elapsed, DUMP_BUDGET_S))
    if not isinstance(state, dict):
        failures.append('ARM6 the dump did not return a dict: %r' % (state,))
    elif 'panelDom' not in state:
        failures.append('ARM6 the dump does not say WHY its DOM half is what it '
                        'is (no panelDom block)')
    if form.count != 1:
        failures.append('ARM6 the dump posted %d callables, expected 1'
                        % form.count)
    shell.panel_state_snapshot('oracle')
    if form.count != 1:
        failures.append('ARM6 a second dump posted another callable (%d in '
                        'total): the diagnostic grows the WinForms queue'
                        % form.count)
    return failures


ARMS = [
    ('ARM1 the reply does not hold its caller', arm_reply_not_blocking),
    ('ARM2 N replies leave at most ONE posted callable', arm_reply_one_post),
    ('ARM3 every id is answered', arm_reply_resolves),
    ('ARM4 a stall is distinguishable from None', arm_stall_is_distinguishable),
    ('ARM5 emit_async\'s latch still holds', arm_emit_latch),
    ('ARM6 the dump does not block', arm_dump_does_not_block),
]


def run_arms(mod, label):
    """Every arm, in order. Returns (failures, passed, total, blocked).

    AN ARM THAT FOUND A BLOCK STOPS THE RUN. A shell whose reply blocks for
    10 s would make every LATER arm pay 10 s per call -- 500 s for the 50
    calls of ARM 2 -- and a control that takes eight minutes to prove a point
    is a control nobody runs. The block IS the finding: the arms after it
    would only measure the same broken shell again.
    """
    failures = []
    passed = 0
    blocked = False
    for name, fn in ARMS:
        got = fn(mod)
        if isinstance(got, tuple):
            got, was_blocked = got
            blocked = blocked or was_blocked
        if got:
            for line in got:
                failures.append('%s: %s' % (label, line))
        else:
            passed += 1
        if blocked:
            print('   (the remaining arms were SKIPPED: the reply already '
                  'blocked, and every later arm would pay the same wait)')
            break
    return failures, passed, len(ARMS), blocked


# ---------------------------------------------------------------------------
# the mutants
# ---------------------------------------------------------------------------
#: (name, what it breaks, the text it replaces, the text it replaces it with)
MUTANTS = [
    (
        'sync-reply',
        'reply_stats back to the SYNCHRONOUS exec_js (it blocks the caller)',
        """            queued = self._post(self._drain_stats_replies)
""",
        """            self.exec_js('window.__sotto_stats(' + json.dumps(stats_id)
                         + ',' + json.dumps(json.dumps(payload)) + ')')
            queued = False
""",
    ),
    (
        'unbounded-reply',
        'one posted callable per reply (the bound is gone)',
        """        if already:
            # A POST IS ALREADY PENDING and it will carry this id too. Nothing
            # new is posted: THAT is the bound.
            return True
""",
        """        if already:
            already = False
""",
    ),
    (
        'silent-stall',
        'the stall answers a bare None, with no reason attached',
        """                return NoAnswer('ui-thread-stall', name, timeout)
""",
        """                return None
""",
    ),
    (
        'emit-latch-off',
        "emit_async's coalescing guard removed (one callable per push)",
        """        if already:
            return
""",
        """        if already:
            pass
""",
    ),
]


def crlf(text):
    """The shell is CRLF-PURE, so the text that breaks it is CRLF too."""
    return text.replace('\r\n', '\n').replace('\n', '\r\n')


def build_mutant(text, name, old, new):
    """Write the broken copy next to the shell and import it."""
    old = crlf(old)
    new = crlf(new)
    count = text.count(old)
    if count != 1:
        raise RuntimeError('%s: the text to break matched %d times (expected 1)'
                           % (name, count))
    path = os.path.join(SHELL_DIR, '_stall-neg-%s.py' % name)
    with io.open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(text.replace(old, new, 1))
    return path


def clean_mutants():
    """Remove a stale mutant copy from an interrupted run."""
    try:
        names = os.listdir(SHELL_DIR)
    except OSError:
        return
    for name in names:
        if name.startswith('_stall-neg-') and name.endswith('.py'):
            try:
                os.remove(os.path.join(SHELL_DIR, name))
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true',
                    help='the mutants only (the same four, in isolation)')
    args = ap.parse_args()
    install_system_fakes()
    print('shell : %s' % SHELL)
    print('bytes : %d' % os.path.getsize(SHELL))

    with io.open(SHELL, 'r', encoding='utf-8', newline='') as handle:
        text = handle.read()

    clean_mutants()

    # -- the LIVE shell -----------------------------------------------------
    live_failures = []
    if not args.neg_arm:
        mod = load_shell(SHELL, 'sotto_shell_ui_stall_live')
        live_failures, passed, total, _ = run_arms(mod, 'LIVE')
        for line in live_failures:
            print('   FAIL ' + line)
        print('ARMS: %d/%d' % (passed, total))

    # -- the FOUR mutants ---------------------------------------------------
    mutant_failures = []
    setup_errors = []
    reds = 0
    for name, what, old, new in MUTANTS:
        path = None
        got = None
        try:
            path = build_mutant(text, name, old, new)
            mod = load_shell(path, 'sotto_shell_ui_stall_mut_%s' % name)
            got, _passed, _total, _ = run_arms(mod, 'MUTANT-%s' % name)
        except Exception as exc:  # noqa: BLE001
            # A COPY THAT COULD NOT BE BUILT IS A SETUP ERROR, NOT A RED.
            # Counting it as a control that "went red" is the vacuity this
            # repo keeps fighting: a control that fails for the WRONG reason
            # is not a control.
            setup_errors.append('MUTANT-%s: the broken copy could not be '
                                 'built/run: %r' % (name, exc))
        finally:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        if got is None:
            print('   SETUP-ERROR %-16s %s' % (name, what))
            continue
        if got:
            reds += 1
            print('   RED  %-16s %s' % (name, what))
            for line in got:
                print('        ' + line)
        else:
            mutant_failures.append('the mutant %s stayed GREEN -- the oracle '
                                    'cannot say no' % name)
            print('   GREEN %-16s %s' % (name, what))
    print('MUTANTS: %d/%d red on their own claim'
          % (reds, len(MUTANTS)))

    failures = list(live_failures) + list(mutant_failures) + list(setup_errors)
    for line in setup_errors:
        print('   SETUP-ERROR ' + line)
    print('VERDICT: ' + ('FAIL' if failures else 'PASS'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
