#!/usr/bin/env python3
"""hotkey-cycle-oracle -- the Alt+C contract AS IT IS TODAY: the 1/2/3 gesture.

WHAT THIS FILE USED TO MEASURE, and why it was re-anchored (2026-10-20).

It measured the THREE-STATE CYCLE: HIDDEN -> STRIP -> SIDE -> HIDDEN, one press =
one step, NO CLOCK. That was the owner's 2026-10-13 contract, verbatim: *"quando
o segundo painel aparece, o proximo alt c deve fazer ele sumir. ai, o proximo,
independente do tempo, deve fazer o painel de baixo aparecer."*

THE PRODUCT RETIRED THAT CONTRACT ON PURPOSE. The owner gave ONE press a meaning
of its own (the caption) and moved the panels to the double and the triple:

    app/webview/sotto_webview.py:7780  "THIS REPLACES the three-state cycle
                                       (2026-10-13: HIDDEN -> STRIP -> SIDE ->
                                       HIDDEN, one press one step, no clock)."
    app/webview/sotto_webview.py:7787  "WHAT IS DELIBERATELY GONE WITH IT:
                                       'independente do tempo'."

What replaced it is the 1/2/3 GESTURE inside a 250 ms window
(`HOTKEY_DOUBLE_MS = 250`, :1403):

    ONE press    -> the caption on/off
    TWO presses  -> the FIRST panel (the bottom strip)
    THREE        -> the RIGHT panel

So the arms below were re-anchored to THAT, and the old "NO CLOCK" arm was
INVERTED, not deleted: the gesture is time-bounded on purpose now, so the gate
REQUIRES the clock read and REQUIRES the window to be the real one -- measured
behaviourally (120 ms apart is ONE gesture, 400 ms apart is TWO), not by a grep.

WHAT IS MEASURED, and how. The REAL `SottoShell` class is imported from
`app/webview/sotto_webview.py` and INSTANTIATED (`object.__new__`, exactly the
technique `_main/emit-queue-bound-oracle.py` already proved on this same file: no
`__init__`, no pywebview window, no lock, nothing launched). The gesture is then
driven through the REAL `hotkey_pressed`, with TWO module globals replaced --
`time` (a clock the oracle advances by hand) and `threading` (a Timer that is
RECORDED, not started) -- because the product DEFERS the caption and the first
panel by `HOTKEY_DOUBLE_MS` and decides at RUN time. Everything else is shipped
code: `show_strip`, `show_side`, `hide_panel`, `toggle_panel`.

  ARM 1  THE GESTURE. One press = the caption and NO panel. Two presses inside
          the window = the FIRST panel and the caption does NOT move. Three
          presses = the RIGHT panel, and the strip NEVER appeared on the way.
          Four presses = the right panel and then a NEW gesture (a caption).
          Two SLOW presses = two captions -- the window is per press.
  ARM 2  THE WINDOW IS REAL (the inverted old arm). `HOTKEY_DOUBLE_MS` exists
          and is short; `hotkey_pressed` reads a clock and compares it against
          that constant; and the behaviour proves the window: 120 ms apart is
          ONE gesture, 400 ms apart is TWO, 900 ms apart is TWO captions.
  ARM 3  THE SURFACE NAMES ARE REAL. The strip asks for 'strip' and the right
          panel asks for 'panel' -- never the literal 'side', which
          `normalise_surface_name` refuses (`SURFACE_NAMES = ('strip','panel')`).
          That is the 2026-10-12 defect that shipped: the side panel passed
          'side', every double-press logged `PANEL_SURFACE_REFUSED surface="side"`,
          and the owner saw a strip twice and no right panel at all.
  ARM 4  THE OTHER WAY IN. `toggle_panel` (the tray) decides from the LIVE
          window (`window_visible`) and not from a cached flag.

THE CONTROL IS THREE MUTANTS, NOT A COMMENT (`--neg-arm`). Each is a COPY of the
real shell written to `$TMPDIR` with ONE half of the gesture reverted, and the
arm that owns it has to go RED. "RED" is not "the copy failed somehow": the
mutant's whole OBSERVATION MAP (scenario by scenario) has to DIFFER from the
live shell's, AND at least one arm has to notice. A mutant that changes nothing
is INERT and is reported as the failure it is -- a gate that cannot say no is
decoration, and an inert mutant is worse than a red one.

  M1  THE TRIPLE THRESHOLD DROPS TO TWO. `count >= 3` becomes `count >= 2`, so
      the DOUBLE paints the RIGHT panel (the 2026-10-13 defect's mirror image:
      the third step used to be unreachable).
  M2  THE TRIPLE PAINTS THE STRIP. `show_side` becomes `show_strip`, so the
      right panel is unreachable and the strip flashes on the way to it.
  M3  THE PENDING CAPTION IS NOT RETIRED. The token bump on `count >= 2` goes
      away, so a DOUBLE also enables the caption -- the owner's rule verbatim:
      *"caso double alt c, a legenda nao habilita"*.

THE EXIT CODE OF THE NEGATIVE ARM follows the HOUSE convention, not the old one:
`:expectred` in `_main/_audit-verify-all.cmd:1026` wants rc=1 (the defect was
found) AND the log to print "NEG-ARM PASS"; rc=0 means the control did NOT go
red and rc=2 is a setup error. So a green negative arm exits 1 BY DESIGN and
prints "NEG-ARM PASS"; a broken one exits 2 and prints "VERDICT: FAIL".

NOTHING IS LAUNCHED. No shell, no worker, no WebView2, no browser, no window:
import, `object.__new__`, call. The worker hook is stubbed, so no `show_strip`
can start one, and the caption window is never opened. `TMPDIR` is honoured.

Usage:
  py -3 _main/hotkey-cycle-oracle.py             the live shell
  py -3 _main/hotkey-cycle-oracle.py --neg-arm   the three controls, must be RED
                                                  (rc=1 BY DESIGN, "NEG-ARM PASS")
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')

# The window the gesture lives in. The product says 250 ms (:1403) and says WHY
# at :7787-7791. This gate checks the RANGE (the same one the green reference
# `_main/hotkey-triple-oracle.py` uses) and pins the BEHAVIOUR around it: two
# presses INSIDE_MS apart are ONE gesture, two presses OUTSIDE_MS apart are TWO.
WINDOW_MIN_MS = 100
WINDOW_MAX_MS = 400
INSIDE_MS = 120
OUTSIDE_MS = 400
FAR_MS = 900

# The mutants, as CRLF-exact anchors in the shipped file. Each is verified to
# occur exactly ONCE; a count other than 1 makes the oracle say so and fail,
# rather than silently patching the wrong line (rule N2).
MUTANTS = [
    ('M1 the triple threshold drops to two',
     "        if count >= 3:\r\n",
     "        if count >= 2:  # MUTANT M1\r\n",
     None, None),
    ('M2 the triple paints the strip',
     "            return self.show_side('hotkey-triple')\r\n",
     "            return self.show_strip('hotkey-triple')  # MUTANT M2\r\n",
     None, None),
    ('M3 the pending caption is not retired',
     "        if count >= 2:\r\n"
     "            self._hotkey_single_token = getattr(self, '_hotkey_single_token', 0) + 1\r\n",
     "        if count >= 2:  # MUTANT M3: the pending caption is NOT retired\r\n"
     "            pass\r\n",
     None, None),
]

# The scenarios: the gaps BETWEEN presses, in milliseconds (the first press is
# at t=0). `INSIDE` is inside the window, `OUTSIDE` is outside it, `FAR` is far
# outside it.
SCENARIOS = (
    ('one', ()),
    ('double', (INSIDE_MS,)),
    ('triple', (INSIDE_MS, INSIDE_MS)),
    ('quad', (INSIDE_MS, INSIDE_MS, INSIDE_MS)),
    ('slow', (FAR_MS,)),
)
# The window's own scenario: two presses just OUTSIDE the window are two
# gestures, not one. Kept apart from SCENARIOS because it is ARM 2's probe.
WIDE = ('wide', (OUTSIDE_MS,))

# What the owner SEES, scenario by scenario. ('surface', name, reason) is a
# panel being painted; ('caption', on, None) is the caption flipping.
EXPECTED = {
    'one': [('caption', True, None)],
    'double': [('surface', 'strip', 'hotkey-double')],
    'triple': [('surface', 'panel', 'hotkey-triple')],
    'quad': [('surface', 'panel', 'hotkey-triple'), ('caption', True, None)],
    'slow': [('caption', True, None), ('caption', False, None)],
}
EXPECTED_WIDE = [('caption', True, None), ('caption', False, None)]


class FakeGeneric(object):
    """Stands in for Func[Object] / Action[Task[String]] -- subscript AND call."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, fn=None):
        self.fn = fn

    def __call__(self, *a, **k):
        return self.fn(*a, **k)


def install_system_fakes():
    """The shell does its .NET imports INSIDE some methods; feed it fakes."""
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


def load_shell(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # The shell imports its own siblings (hot_reload, ...). A MUTANT copy lives in
    # $TMPDIR, so its own directory is not enough -- the product's app/webview has
    # to be on the path too, or the copy dies on an import the live file resolves
    # without thinking about it.
    for d in (os.path.dirname(os.path.abspath(path)), os.path.dirname(SHELL)):
        if d and d not in sys.path:
            sys.path.insert(0, d)
    spec.loader.exec_module(mod)
    # The shell logs a lot; the oracle keeps the lines so a failure can quote
    # them, and never prints them raw.
    mod._oracle_log = []
    mod.log = lambda *a, **k: mod._oracle_log.append(' '.join(str(x) for x in a))
    return mod


class _Ready(object):
    def is_set(self):
        return True


class FakeWindow(object):
    """One HWND's visibility, moved ONLY by the calls the shell itself makes."""

    def __init__(self):
        self.visible = False
        self.shows = 0
        self.hides = 0


class FakeClock(object):
    """Seconds, like `time.monotonic` -- and NOT starting at 0.0.

    The product keeps the last press in `self._last_hotkey_press` and decides
    with `if not (prev and (now - prev) * 1000.0 <= HOTKEY_DOUBLE_MS)`. A clock
    that starts at 0.0 makes `prev` FALSY, so the SECOND press would look like
    a brand new gesture and the double would never be a double. The green
    reference `_main/hotkey-triple-oracle.py` hit exactly this: a fake clock
    with the wrong starting point (and, in its first draft, the wrong UNIT) is
    worse than no fake clock.
    """

    def __init__(self):
        self.t = 1000.0

    def advance(self, ms):
        self.t += ms / 1000.0

    def monotonic(self):
        return self.t


class FakeTimer(object):
    """A `threading.Timer` that is RECORDED, not started.

    The product defers the caption and the first panel by `HOTKEY_DOUBLE_MS` and
    decides at RUN time, so the oracle has to fire the deferred handler ITSELF
    -- in the order it was armed, which is the order the owner would see.
    """

    def __init__(self, delay, fn, store):
        self.delay = delay
        self.fn = fn
        self.daemon = False
        self.started = False
        store.append(self)

    def start(self):
        self.started = True

    def fire(self):
        self.fn()


class FakeThreading(object):
    """The shell's `threading`, with a Timer that never touches a thread."""

    def __init__(self, timers, real):
        self._timers = timers
        self._real = real

    def Timer(self, delay, fn):
        return FakeTimer(delay, fn, self._timers)

    def __getattr__(self, name):
        return getattr(self._real, name)


class FakeTime(object):
    """The shell's `time`, with a `monotonic` the oracle drives."""

    def __init__(self, clock, real):
        self._clock = clock
        self._real = real

    def monotonic(self):
        return self._clock.monotonic()

    def __getattr__(self, name):
        return getattr(self._real, name)


def make_shell(mod, win, sink):
    """A REAL SottoShell instance with only the window collaborators stubbed.

    `sink` collects ('surface', name, reason) for every set_panel_surface call,
    ('caption', on) for every caption toggle, ('worker', source) for every
    worker hook and ('visibility', reason) for every publish_panel_visibility
    call, so an arm can read the sequence the gesture actually produced.
    """
    shell = object.__new__(mod.SottoShell)
    shell.hwnd = 0xB0F0B0F0
    # The fields `__init__` gives these paths before anything else happens.
    shell.panel_mode = 'strip'
    shell.visible = False
    shell.surface = 'strip'
    shell.surface_applied = 'strip'
    shell.geometry = {}
    shell.click_watcher = None
    shell.form = None
    shell.renderer_ready = _Ready()
    shell.strip_height = 150
    shell.strip_height_css = 150
    shell.strip_height_extra = 0
    shell.strip_width_dom = None
    shell._strip_dock_base = None
    shell._strip_moved_sent = False
    shell.display = None
    # The gesture's own state. The shell reads it with `getattr(..., default)`,
    # so a shell that never saw a press must still answer.
    shell._last_hotkey_press = 0.0
    shell._hotkey_press_count = 0
    shell._hotkey_single_token = 0
    shell._caption_wanted = False

    def set_panel_surface(name, reason):
        sink.append(('surface', name, reason))

    def publish_panel_visibility(reason):
        sink.append(('visibility', reason))

    def _set_live_enabled(payload):
        # The real one writes `self._caption_wanted` and then shows the NATIVE
        # caption window. Only the first half is reproduced here: that window
        # belongs to the OS and this oracle never opens one.
        on = bool((payload or {}).get('on'))
        shell._caption_wanted = on
        sink.append(('caption', on))
        return True

    def _start_deferred_worker(source):
        # The real one can START THE WORKER. This oracle never starts one, so
        # the hook is recorded and nothing else happens.
        sink.append(('worker', source))
        return False

    def _blank_caption_window(reason):
        sink.append(('blank', reason))
        return True

    shell.set_panel_surface = set_panel_surface
    shell.publish_panel_visibility = publish_panel_visibility
    shell._set_live_enabled = _set_live_enabled
    shell._start_deferred_worker = _start_deferred_worker
    shell._blank_caption_window = _blank_caption_window

    # ── the module-level collaborators, patched on the MODULE so the real
    # methods under test resolve them as globals. ──
    def _hide(hwnd):
        win.hides += 1
        win.visible = False
        return True

    def _show(hwnd):
        win.shows += 1
        win.visible = True
        return True

    mod.window_visible = lambda hwnd: win.visible
    mod.hide_window = _hide
    mod.foreground_unlock = _show
    mod.show_without_activating = _show
    mod.show_webview_children = lambda hwnd: {'shown': [], 'already': [], 'failed': []}
    mod.transparency_hack = lambda shell: None
    return shell


def observe(mod, gaps):
    """Press Alt+C (len(gaps)+1 times) and return what the owner SAW.

    The deferred handlers are fired by hand, in the order they were armed, so
    the measurement is deterministic and no thread is ever started.
    """
    win = FakeWindow()
    sink = []
    clock = FakeClock()
    timers = []
    shell = make_shell(mod, win, sink)
    real_time, real_threading = mod.time, mod.threading
    mod.time = FakeTime(clock, real_time)
    mod.threading = FakeThreading(timers, real_threading)
    try:
        # The FIRST press has no gap before it; every gap is the distance from
        # the previous press to the next one.
        shell.hotkey_pressed()
        for gap in gaps:
            clock.advance(gap)
            shell.hotkey_pressed()
        for timer in list(timers):
            if timer.started:
                timer.fire()
    finally:
        mod.time = real_time
        mod.threading = real_threading
    seen = []
    for entry in sink:
        if entry[0] == 'surface':
            seen.append(('surface', entry[1], entry[2]))
        elif entry[0] == 'caption':
            seen.append(('caption', entry[1], None))
    return seen


def measure(mod):
    """The whole observable map of the gesture, scenario by scenario."""
    out = {}
    for name, gaps in SCENARIOS + (WIDE,):
        out[name] = observe(mod, gaps)
    return out


def ast_facts(mod):
    """(reads_the_clock, compares_the_window, why_not).

    Read from the AST of the file THE MODULE CAME FROM -- the live file for the
    control, the COPY for a mutant. Reading the live file while judging a
    mutant is how an arm ends up measuring something the mutant cannot change.
    """
    path = getattr(mod, '__file__', None)
    if not path or not os.path.exists(path):
        return (False, False, 'the module has no readable source file')
    with open(path, encoding='utf-8', errors='replace', newline='') as fh:
        try:
            tree = ast.parse(fh.read())
        except SyntaxError as exc:
            return (False, False, 'the source does not parse: %s' % exc)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'SottoShell':
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == 'hotkey_pressed':
                    clock = False
                    window = False
                    for inner in ast.walk(sub):
                        if (isinstance(inner, ast.Call)
                                and isinstance(inner.func, ast.Attribute)
                                and inner.func.attr == 'monotonic'):
                            clock = True
                        if (isinstance(inner, ast.Name)
                                and inner.id == 'HOTKEY_DOUBLE_MS'):
                            window = True
                    return (clock, window, None)
    return (False, False, 'SottoShell has no hotkey_pressed() method')


def arm_gesture(mod):
    """ARM 1: the 1/2/3 gesture, exactly as the owner stated it."""
    fails = []
    got = measure(mod)
    for name, _gaps in SCENARIOS:
        if got[name] != EXPECTED[name]:
            fails.append('the %s gesture produced %r, expected %r'
                         % (name, got[name], EXPECTED[name]))
    return fails


def arm_window(mod):
    """ARM 2: the window is REAL -- the inverted old "no clock" arm.

    The old arm demanded that the cycle read NO clock, because the product used
    to promise *"independente do tempo"*. The owner took that promise back on
    2026-10-18, in writing (`sotto_webview.py:7787`), so the gate now demands
    the clock AND the comparison against the window -- and proves the window
    behaviourally, because a constant that is read but not honoured is a
    constant that does not exist.
    """
    fails = []
    win_ms = getattr(mod, 'HOTKEY_DOUBLE_MS', None)
    if not isinstance(win_ms, int):
        fails.append('HOTKEY_DOUBLE_MS is %r, not an int' % (win_ms,))
    elif not (WINDOW_MIN_MS <= win_ms <= WINDOW_MAX_MS):
        fails.append('HOTKEY_DOUBLE_MS is %d ms, outside %d..%d -- a window that '
                     'long is lag, not a double-click'
                     % (win_ms, WINDOW_MIN_MS, WINDOW_MAX_MS))
    clock, window, why = ast_facts(mod)
    if why:
        fails.append(why)
    if not clock:
        fails.append('hotkey_pressed() does not read a clock -- the gesture is '
                     'not time-bounded')
    if not window:
        fails.append('hotkey_pressed() does not compare against '
                     'HOTKEY_DOUBLE_MS -- the window is not the contract')
    got = measure(mod)
    if got['double'] != EXPECTED['double']:
        fails.append('two presses %d ms apart are not ONE gesture: %r'
                     % (INSIDE_MS, got['double']))
    if got['wide'] != EXPECTED_WIDE:
        fails.append('two presses %d ms apart are still ONE gesture: %r -- the '
                     'window is wider than %d ms'
                     % (OUTSIDE_MS, got['wide'], OUTSIDE_MS))
    if got['slow'] != EXPECTED['slow']:
        fails.append('two presses %d ms apart are not two captions: %r'
                     % (FAR_MS, got['slow']))
    return fails


def arm_surface(mod):
    """ARM 3: the surface names the gesture asks for are REAL ones."""
    fails = []
    got = measure(mod)
    for name, _gaps in SCENARIOS:
        for entry in got[name]:
            if entry[0] != 'surface':
                continue
            surface = entry[1]
            if surface not in ('strip', 'panel'):
                fails.append('the %s gesture asked for the surface name %r, which '
                             'normalise_surface_name refuses'
                             % (name, surface))
            elif mod.normalise_surface_name(surface) != surface:
                fails.append('normalise_surface_name(%r) returned %r -- the name '
                             'the gesture uses is not a real one'
                             % (surface, mod.normalise_surface_name(surface)))
    if mod.normalise_surface_name('side') is not None:
        fails.append("normalise_surface_name('side') returned %r; the 2026-10-12 "
                     'defect was exactly this literal'
                     % (mod.normalise_surface_name('side'),))
    return fails


def arm_toggle(mod):
    """ARM 4: the OTHER way in decides from the LIVE window, not a stale cache.

    The gesture no longer opens a panel with ONE press -- that is the caption
    now -- so the setup uses the real show path (`show_strip`, where the
    owner's double and triple end up) and then makes the CACHE stale on
    purpose. A stale `True` is what made the owner's first Alt+C a no-op HIDE
    of a panel he could not see.
    """
    fails = []
    win = FakeWindow()
    sink = []
    shell = make_shell(mod, win, sink)
    shell.show_strip('tray-setup')       # the real method: it MAPS the window
    if not win.visible:
        fails.append('the setup did not map the window')
    shell.visible = False                # a stale cache: the window says up
    win.visible = True
    shell.toggle_panel('tray')
    if win.visible:
        fails.append('toggle_panel did not hide a window the LIVE window says is '
                     'up (it decided from the stale cache)')
    if win.hides != 1:
        fails.append('toggle_panel called hide_window %d time(s), expected 1'
                     % win.hides)
    return fails


ARMS = (arm_gesture, arm_window, arm_surface, arm_toggle)


def run_arm(mod):
    """Run every arm against ONE module and collect what they found."""
    fails = []
    for fn in ARMS:
        try:
            got = fn(mod)
        except Exception as exc:  # noqa: BLE001 -- report, never crash the oracle
            fails.append('%s raised %s: %s' % (fn.__name__, type(exc).__name__, exc))
            continue
        for line in got:
            fails.append('[%s] %s' % (fn.__name__, line))
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()
    install_system_fakes()

    # newline='' is load-bearing: the shell is pure CRLF and every mutant anchor
    # below is CRLF-exact. Text mode would translate them to LF and the anchors
    # would silently miss -- a control that cannot find its own target is not a
    # control.
    with open(SHELL, encoding='utf-8', errors='replace', newline='') as fh:
        text = fh.read()
    print('shell : %s' % SHELL)
    print('bytes : %d' % os.path.getsize(SHELL))
    print('contract: the 1/2/3 gesture -- one press = the caption, two = the '
          'FIRST panel, three = the RIGHT panel -- inside a HOTKEY_DOUBLE_MS '
          'window')
    print('the retired contract: the three-state cycle (HIDDEN -> STRIP -> SIDE '
          '-> HIDDEN, one press one step, NO clock), replaced on purpose on '
          '2026-10-18 (sotto_webview.py:7780)')

    if not args.neg_arm:
        mod = load_shell(SHELL, 'sotto_shell_hotkey_live')
        fails = run_arm(mod)
        for line in fails:
            print('   FAIL ' + line)
        print('VERDICT: ' + ('FAIL' if fails else 'PASS'))
        return 1 if fails else 0

    # ── the negative arms ───────────────────────────────────────────────────
    # The CONTROL first: a negative arm that runs against a red control proves
    # nothing, and the old version of this file did exactly that -- it called
    # any failure "RED as expected", so a control that was already broken
    # turned every mutant into a pass.
    control = load_shell(SHELL, 'sotto_shell_hotkey_control')
    control_fails = run_arm(control)
    if control_fails:
        print('NEG-ARM FAIL -- the CONTROL is already red, so no mutant can be '
              'proven')
        for line in control_fails[:6]:
            print('        ' + line[:160])
        print('VERDICT: FAIL -- the control of the negative arm is broken')
        return 2
    control_map = measure(control)

    overall = True
    caught = 0
    inert = 0
    scratch_dir = (os.environ.get('TMPDIR') or os.environ.get('TEMP') or HERE)
    for index, (label, a1, b1, a2, b2) in enumerate(MUTANTS):
        for anchor in (a1, a2):
            if anchor is not None and text.count(anchor) != 1:
                print('NEG-ARM %-52s CONTROL IS DEAD (anchor count=%d)'
                      % (label, text.count(anchor)))
                overall = False
        out = text.replace(a1, b1, 1)
        if a2 is not None:
            out = out.replace(a2, b2, 1)
        if out == text:
            print('NEG-ARM %-52s CONTROL IS DEAD (the mutation changed nothing)'
                  % label)
            overall = False
            continue
        scratch = os.path.join(scratch_dir,
                               '_hotkey-cycle-mutant-%d.py' % index)
        with open(scratch, 'w', encoding='utf-8', newline='') as fh:
            fh.write(out)
        try:
            mod = load_shell(scratch, 'sotto_shell_hotkey_mutant')
            got = run_arm(mod)
            mutant_map = measure(mod)
        finally:
            try:
                os.remove(scratch)
            except OSError:
                pass
        changed = sorted(k for k in control_map
                          if mutant_map.get(k) != control_map.get(k))
        if not changed:
            inert += 1
            overall = False
            print('NEG-ARM %-52s INERT -- the behaviour did not change' % label)
            for name, _gaps in SCENARIOS + (WIDE,):
                print('        %-7s control=%r mutant=%r'
                      % (name, control_map[name], mutant_map.get(name)))
            continue
        if not got:
            inert += 1
            overall = False
            print('NEG-ARM %-52s THE BEHAVIOUR CHANGED AND NO ARM NOTICED'
                  % label)
            for name in changed:
                print('        %-7s control=%r mutant=%r'
                      % (name, control_map[name], mutant_map.get(name)))
            continue
        caught += 1
        print('NEG-ARM %-52s RED as expected' % label)
        for name in changed:
            print('        %-7s control=%r mutant=%r'
                  % (name, control_map[name], mutant_map.get(name)))
        for line in got[:4]:
            print('        ' + line[:160])
    if overall:
        print('NEG-ARM PASS -- %d/%d mutant(s) caught, %d inert (rc=1 BY DESIGN: '
              'the house :expectred contract wants rc=1 and this line)'
              % (caught, len(MUTANTS), inert))
        return 1
    print('VERDICT: FAIL -- %d of %d mutant(s) are inert or unnoticed'
          % (inert, len(MUTANTS)))
    return 2


if __name__ == '__main__':
    sys.exit(main())
