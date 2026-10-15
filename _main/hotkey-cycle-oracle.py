#!/usr/bin/env python3
"""hotkey-cycle-oracle -- the Alt+C three-state cycle, on the REAL class.

WHY IT EXISTS, and the owner's own words (2026-10-13): *"o alt c ta meio ruim.
quando o segundo painel aparece, o proximo alt c deve fazer ele sumir. ai, o
proximo, independente do tempo, deve fazer o painel de baixo aparecer."* The
contract that answers it is ONE press = ONE step of a fixed cycle, with NO clock:

    HIDDEN -> STRIP    (the bottom panel: the app's only control)
    STRIP  -> SIDE     (the right panel: history, folder, details)
    SIDE   -> HIDDEN

WHAT IS MEASURED, and how. The REAL `SottoShell` class is imported from
`app/webview/sotto_webview.py` and INSTANTIATED (`object.__new__`, exactly the
technique `_main/emit-queue-bound-oracle.py` already proved on this same file: no
`__init__`, no pywebview window, no lock, nothing launched), and then the cycle is
driven through the REAL `hotkey_pressed` -> `show_strip` / `show_side` /
`hide_panel` methods. Only the collaborators are stubbed, and each stub is named
below. The window state is NOT a variable this oracle sets per press: the fake
`hide_window` / `foreground_unlock` / `window_visible` move a shared fake HWND, so
the branch `hotkey_pressed` takes is decided by the state the SHELL's own calls
left behind -- the same thing a real window does.

  ARM 1  THE CYCLE. Six presses from hidden, in order, produce exactly
          strip -> side -> HIDE -> strip -> side -> HIDE. The owner's complaint
          was that press three repainted the side panel instead of hiding.
  ARM 2  THE FIELD IS WRITTEN. `panel_mode` is 'strip' after the first press,
          'side' after the second, and the cycle reads it back on the third. The
          2026-10-09 P0 refactor left `place_panel` as its only writer with ZERO
          call sites, so the field was never written at all -- the owner measured
          ten presses, ten `PANEL_SHOWN ... mode=side`, ONE `PANEL_HIDDEN`.
  ARM 3  THE SURFACE NAME IS A REAL ONE. `set_panel_surface` is called with
          'strip' then 'panel' -- never the literal 'side', which
          `normalise_surface_name` refuses (`SURFACE_NAMES = ('strip','panel')`).
          That is the 2026-10-12 defect that shipped: the side panel passed
          'side', every double-press logged `PANEL_SURFACE_REFUSED surface="side"`,
          and the owner saw a strip twice and no right panel at all.
  ARM 4  NO CLOCK. `_last_hotkey_press` and the HOTKEY_DOUBLE vocabulary are not
          live anywhere: what the next press does must not depend on how fast the
          last one was.
  ARM 5  THE OTHER WAY IN. `toggle_panel` decides from the LIVE window
          (`window_visible`) and not from a cached flag.

THE CONTROL IS THREE MUTANTS, NOT A COMMENT (`--neg-arm`). Each is a COPY of the
real shell written to `$TMPDIR` with ONE half of the mechanism reverted, and the
arm that owns it has to go RED:

  M1  THE OLD DEFECT, EXACTLY: `panel_mode` is never written on either show
      (`show_strip` and `show_side`) -- the field-never-written state measured
      above, which is what made press 3 repaint the side panel.
  M2  the side show passes the literal surface name again (2026-10-12 back).
  M3  the cycle's third arm is made unreachable, so the panel can never hide.

NOTHING IS LAUNCHED. No shell, no worker, no WebView2, no browser, no window:
import, `object.__new__`, call. `TMPDIR` is honoured.

Usage:
  py -3 _main/hotkey-cycle-oracle.py             the live shell
  py -3 _main/hotkey-cycle-oracle.py --neg-arm   the three controls, must be RED
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')

# The mutants, as CRLF-exact anchors in the shipped file. Each is verified to
# occur exactly ONCE; a count other than 1 makes the oracle say so and fail,
# rather than silently patching the wrong line (rule N2).
MUTANTS = [
    ('M1 panel_mode never written (the 2026-10-09 defect)',
     "        # records WHICH surface is up, on the show itself.\r\n"
     "        self.panel_mode = 'strip'",
     "        # records WHICH surface is up, on the show itself.\r\n"
     "        pass  # MUTANT M1: panel_mode no longer written by show_strip",
     "        # cycle stops.\r\n"
     "        self.panel_mode = 'side'",
     "        # cycle stops.\r\n"
     "        pass  # MUTANT M1: panel_mode no longer written by show_side"),
    ('M2 the side show passes the literal surface name again',
     "        self.set_panel_surface('panel', reason)",
     "        self.set_panel_surface('side', reason)  # MUTANT M2",
     None, None),
    ('M3 the third arm of the cycle is unreachable',
     "        if self.panel_mode == 'side':\r\n"
     "            return self.hide_panel('hotkey')",
     "        if False:  # MUTANT M3: the cycle can no longer hide\r\n"
     "            return self.hide_panel('hotkey')",
     None, None),
]


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


def make_shell(mod, win, sink):
    """A REAL SottoShell instance with only the window collaborators stubbed.

    `sink` collects ('surface', name, reason) for every set_panel_surface call,
    so an arm can read the sequence the cycle actually produced.
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

    def set_panel_surface(name, reason):
        sink.append(('surface', name, reason))

    def publish_panel_visibility(reason):
        sink.append(('visibility', reason))

    shell.set_panel_surface = set_panel_surface
    shell.publish_panel_visibility = publish_panel_visibility

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


def capture(mod):
    """Replace the module's `log` with a recorder and return the list."""
    lines = []
    mod.log = lambda message: lines.append(str(message))
    return lines


def arm_cycle(mod):
    """ARM 1/2/3: drive the real cycle and read what it produced."""
    fails = []
    win = FakeWindow()
    sink = []
    lines = capture(mod)
    shell = make_shell(mod, win, sink)

    modes = []
    for press in range(6):
        shell.hotkey_pressed()
        modes.append(shell.panel_mode)
        if press == 2:
            if win.visible:
                fails.append('press 3 left the window VISIBLE -- the cycle cannot '
                             'hide (panel_mode=%r)' % shell.panel_mode)
            if win.hides != 1:
                fails.append('press 3 called hide_window %d time(s), expected 1'
                             % win.hides)
        if press in (0, 3) and not win.visible:
            fails.append('press %d did not map the window' % (press + 1))

    # panel_mode is what each SHOW leaves behind; a hide writes nothing, so the
    # third and sixth entries repeat the previous value while the window is down.
    want = ['strip', 'side', 'side', 'strip', 'side', 'side']
    if modes != want:
        fails.append('panel_mode after 6 presses = %r, expected %r' % (modes, want))

    order = []
    for l in lines:
        if 'PANEL_SHOWN' in l:
            order.append('strip' if 'mode=strip' in l else 'side')
        elif 'PANEL_HIDDEN' in l:
            order.append('hide')
    if order != ['strip', 'side', 'hide', 'strip', 'side', 'hide']:
        fails.append('the painted order is %r, expected strip,side,hide,strip,'
                     'side,hide' % (order,))

    surfaces = [s[1] for s in sink if s[0] == 'surface']
    if surfaces != ['strip', 'panel', 'strip', 'panel']:
        fails.append('set_panel_surface was called with %r, expected '
                     "['strip','panel','strip','panel']" % (surfaces,))
    for name in surfaces:
        if name not in ('strip', 'panel'):
            fails.append('the cycle asked for the surface name %r, which '
                         'normalise_surface_name refuses' % name)
        elif mod.normalise_surface_name(name) != name:
            fails.append('normalise_surface_name(%r) returned %r -- the name the '
                         'cycle uses is not a real one'
                         % (name, mod.normalise_surface_name(name)))
    if mod.normalise_surface_name('side') is not None:
        fails.append("normalise_surface_name('side') returned %r; the 2026-10-12 "
                     'defect was exactly this literal'
                     % (mod.normalise_surface_name('side'),))
    return fails


def arm_no_clock(mod):
    """ARM 4: no CODE in the cycle ties a press to a clock.

    Measured on the AST of the FOUR CYCLE METHODS, not on a grep and not over the
    whole file: the words survive in the file's docstrings where they explain
    what was deleted (house style, and the right place for them), and the shell
    reads clocks in a dozen legitimate places. What must not exist is a clock
    read or a double-press stamp INSIDE the cycle. A docstring is an
    `ast.Expr(Constant)`, so walking the function bodies skips prose for free.
    """
    import ast
    fails = []
    with open(SHELL, encoding='utf-8', errors='replace') as fh:
        tree = ast.parse(fh.read())
    wanted = {'hotkey_pressed', 'show_strip', 'show_side', 'hide_panel',
              'toggle_panel'}
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'SottoShell':
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name in wanted:
                    found[sub.name] = sub
    for name in sorted(wanted):
        fn = found.get(name)
        if fn is None:
            fails.append('SottoShell lost its %s() method' % name)
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and node.attr == '_last_hotkey_press':
                fails.append('%s() reads self._last_hotkey_press at line %d'
                             % (name, node.lineno))
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ('time', 'monotonic', 'perf_counter')):
                fails.append('%s() reads a clock (%s) at line %d'
                             % (name, node.func.attr, node.lineno))
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ('log', 'warn')):
                for arg in node.args:
                    if (isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                            and arg.value.startswith('HOTKEY_DOUBLE')):
                        fails.append('%s() logs a HOTKEY_DOUBLE line at line %d'
                                     % (name, node.lineno))
    return fails

def arm_toggle(mod):
    """ARM 5: the other way in decides from the LIVE window, not a stale cache."""
    fails = []
    win = FakeWindow()
    sink = []
    shell = make_shell(mod, win, sink)
    shell.hotkey_pressed()               # HIDDEN -> STRIP
    if not win.visible:
        fails.append('toggle path: the window is not up after one press')
    # A stale cache: shell.visible says down while the LIVE window says up.
    shell.visible = False
    win.visible = True
    shell.toggle_panel('tray')
    if win.visible:
        fails.append('toggle_panel did not hide a window the LIVE window says is up '
                     '(it decided from the stale cache)')
    return fails


ARMS = (arm_cycle, arm_no_clock, arm_toggle)


def run_arm(mod):
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

    if not args.neg_arm:
        mod = load_shell(SHELL, 'sotto_shell_hotkey_live')
        fails = run_arm(mod)
        for line in fails:
            print('   FAIL ' + line)
        print('VERDICT: ' + ('FAIL' if fails else 'PASS'))
        return 1 if fails else 0

    # The negative arms. Every anchor must occur exactly once, or the control is
    # DEAD and the run says so instead of patching the wrong line.
    overall = True
    scratch = os.path.join(os.environ.get('TMPDIR') or os.environ.get('TEMP') or HERE,
                           '_hotkey-cycle-mutant.py')
    for label, a1, b1, a2, b2 in MUTANTS:
        for anchor in (a1, a2):
            if anchor is not None and text.count(anchor) != 1:
                print('NEG-ARM %-52s CONTROL IS DEAD (anchor count=%d)'
                      % (label, text.count(anchor)))
                overall = False
        out = text.replace(a1, b1, 1)
        if a2 is not None:
            out = out.replace(a2, b2, 1)
        if out == text:
            continue
        with open(scratch, 'w', encoding='utf-8', newline='') as fh:
            fh.write(out)
        try:
            mod = load_shell(scratch, 'sotto_shell_hotkey_mutant')
            got = run_arm(mod)
        finally:
            try:
                os.remove(scratch)
            except OSError:
                pass
        red = bool(got)
        overall = overall and red
        print('NEG-ARM %-52s %s' % (label, 'RED as expected' if red
                                    else 'STILL GREEN -- the oracle cannot say no'))
        for line in got[:6]:
            print('        ' + line[:160])
    print('VERDICT: ' + ('PASS' if overall else 'FAIL'))
    return 0 if overall else 1


if __name__ == '__main__':
    sys.exit(main())
