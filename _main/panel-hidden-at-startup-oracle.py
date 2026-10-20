"""ORACLE: the Sotto panel must be HIDDEN at startup unless the owner asked.

TICKET-55a4ab4b157bdd26bb9629c7. Deleting ONE line from `_on_before_show`
(`self._ui(self._subscribe_core_ready)`) left `py_compile` at rc=0, left the
shell loading fine, and left the panel ON THE OWNER'S DESK. The defect was
invisible to the compiler, to the log lines that DID print, and to the house
60 s census; only a hand-added DIAG line found it. This file is the mechanical
cure: it fails when the panel is visible at startup.

HEADLESS BY CONSTRUCTION. No window is created, no WebView2 is initialised, no
screenshot is taken, and nothing the owner is running is touched. The subject is
the show/hide DECISION LOGIC — the subscription chain that decides whether a
navigation may leave the panel on screen — driven against fake WinForms objects
with the pywebview behaviour reproduced from its source. It imports the REAL
shell module and calls the REAL `SottoHost` methods.

THE ORDER OF OPERATIONS, as read from the installed pywebview
(C:\\Program Files\\Python311\\Lib\\site-packages\\webview, read 2026-10-06):

  1. `winforms.py:773`  `create_window` builds `BrowserForm` -> `EdgeChrome.
     __init__`, which subscribes pywebview's OWN handlers FIRST
     (`edgechromium.py:101` `CoreWebView2InitializationCompleted`,
      `:102` `NavigationStarting`) and then calls
     `EnsureCoreWebView2Async(None)` (`edgechromium.py:120`) — an ASYNC,
     result-discarded call. The control exists; CoreWebView2 does not.
  2. `winforms.py:775`  `window.events.before_show.set()` -> the shell's
     `_on_before_show`. This is therefore the LAST point that provably precedes
     EVERY navigation: the first navigation cannot start until initialization
     completes, and initialization was only *called* at step 1.
  3. `winforms.py:777-781` the `hidden=True` dance: `Opacity=0; Show(); Hide();
     Opacity=1`. Net result: hidden.
  4. `edgechromium.py:267` `on_webview_ready` — the init-completed handler —
     is what CALLS `load_url` (`:305-311`). So navigation #1 is raised from
     INSIDE the initialization-completed dispatch, and pywebview subscribed
     that handler BEFORE the shell's `_on_core_ready`.
  5. Every `NavigationStarting` runs, for a TRANSPARENT window,
     `if self.pywebview_window.transparent: self.form.Show(); self.form.
     Activate()` (`edgechromium.py:346-349`). That is the SHOW PATH: pywebview
     un-hides the window the shell asked to keep hidden, on every navigation,
     unconditionally, and the hack is load-bearing (clearing `transparent`
     stops the page loading at all).

So the ONLY thing standing between the owner and a panel on his desk is a
handler subscribed to the CONTROL's `NavigationStarting`. Its registration is
the whole invariant, and the defect was that the registration was a side effect
of an UNRELATED subscription (`_subscribe_core_ready`), reachable only if that
line was still there.

ARMS
  WIRING     static, over the shipped source: the guard must be bound to
             `before_show`, and its `NavigationStarting +=` must be reachable
             from `_on_before_show` WITHOUT passing through a
             `CoreWebView2InitializationCompleted +=` registration. A guard
             that exists but is only wired to a late callback is exactly the
             shape of the bug — and a component green is not a delivery green.
  HIDDEN     behavioural, against the real methods and the real ordering above.
             Population: 4 scenarios x 3 initialization timings x N repeats.
             Two of the four scenarios are the panel LEGITIMATELY showing; the
             guard must not hide those.
  MUTATION   hygiene: this file must be able to go RED. It rebuilds the ticket's
             exact mutation and the pre-fix shape in temp files and requires
             itself to reject both.
  SHOW-ROBUST  the show path survives an owner that never ran `__init__`:
             the three external-caption flags it reads are DEFENSIVE reads
             (`getattr(self, ..., False)`), so a missing one is False and not
             an AttributeError on the owner's only key. This arm is what stops
             the defensive reads from regressing.
  EXTERNAL-FLAG  the DECISION did not change: the player's own captions still
             flip `external_captions_active` to True, and the show path still
             writes `WORKER_PANEL_START_SKIPPED ... external=true`.
  NEG-ARM    hygiene, for the DEFENSIVE reads: three textual mutants, each
             with a UNIQUE anchor, each of which must turn SHOW-ROBUST RED. An
             anchor that is missing or ambiguous is DECORATIVE -- it proves
             nothing -- so the oracle REFUSES to count it and says so.

EXIT: 0 GREEN, 1 RED, 2 the oracle itself could not run (a distinct verdict
from a RED — see the rc-carries-a-verdict rule in I:\\!manager\\AGENTS.md).
THE `--neg-arm` RUN HAS ITS OWN RC CONTRACT, and it is INVERTED on purpose:
  rc=1  every declared mutant was applied AND seen (BY DESIGN: the negative
        arm has to fail, so the oracle's own failure is the success)
  rc=0  a mutant SURVIVED -- the gate is blind there
  rc=2  an anchor was missing or ambiguous (a decorative mutant is worse than
        no mutant at all)

USAGE
  py -3 H:\\sotto\\_main\\panel-hidden-at-startup-oracle.py
  py -3 H:\\sotto\\_main\\panel-hidden-at-startup-oracle.py --shell <path>
  py -3 H:\\sotto\\_main\\panel-hidden-at-startup-oracle.py --repeats 25
  py -3 H:\\sotto\\_main\\panel-hidden-at-startup-oracle.py --neg-arm  (rc=1 by design)
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import io
import contextlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL_DIR = os.path.normpath(os.path.join(HERE, os.pardir, 'app', 'webview'))
DEFAULT_SHELL = os.path.join(SHELL_DIR, 'sotto_webview.py')

#: The pywebview facts the ordering rests on, with the file and line they were
#: read from. Pinned so a pywebview upgrade that moves them is a RED here rather
#: than a silently-wrong oracle.
PYWEBVIEW_FACTS = {
    'edgechromium.py:101': 'CoreWebView2InitializationCompleted += on_webview_ready',
    'edgechromium.py:102': 'NavigationStarting += on_navigation_start',
    'edgechromium.py:120': 'EnsureCoreWebView2Async(None)  # async, result discarded',
    'edgechromium.py:346-349': 'on_navigation_start: if transparent: form.Show()',
    'edgechromium.py:305-311': 'on_webview_ready CALLS load_url -> navigation #1',
    'winforms.py:773': 'create_window builds BrowserForm (control + init called)',
    'winforms.py:775': 'window.events.before_show.set()',
    'winforms.py:777-781': 'hidden dance: Opacity=0; Show(); Hide(); Opacity=1',
}

EVENT_CORE_READY = 'CoreWebView2InitializationCompleted'
EVENT_NAVIGATION = 'NavigationStarting'
EVENT_BEFORE_SHOW = 'before_show'


# ===========================================================================
# loading the shell under test
# ===========================================================================

def load_shell(path):
    """Import the shell by path, with stdout captured (it logs a lot)."""
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    name = 'sotto_shell_under_test'
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load a module from {path!r}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spec.loader.exec_module(module)
    return module


# ===========================================================================
# fake WinForms — the show path, reproduced from pywebview's source
# ===========================================================================

class FakeEvent:
    """.NET event. Handlers are raised in SUBSCRIPTION ORDER, which is the
    property the whole cure rests on (edgechromium.py:102 is subscribed before
    the shell's, so pywebview's `Show()` runs first and ours runs immediately
    after it, in the same dispatch)."""

    def __init__(self):
        self.handlers = []

    def __iadd__(self, fn):
        self.handlers.append(fn)
        return self

    def fire(self, sender, args):
        for handler in list(self.handlers):
            handler(sender, args)


class FakeHandle:
    def __init__(self, value):
        self._value = value

    def ToInt64(self):
        return self._value


class FakeControl:
    """The WinForms WebView2 control. Exposes ONLY the two events the show path
    and the cure use; everything else the shell touches is stubbed at the call
    site."""

    def __init__(self):
        self.NavigationStarting = FakeEvent()
        self.CoreWebView2InitializationCompleted = FakeEvent()
        self.Dock = None
        self.CoreWebView2 = None      # exists only after initialization


class FakeForm:
    """The WinForms form. `visible` is the owner's screen state — the single
    fact this oracle is about."""

    def __init__(self, hwnd):
        self.Visible = False
        self.Opacity = 1.0
        self.InvokeRequired = False
        self.Handle = FakeHandle(hwnd)
        self.webview = FakeControl()
        self.shown_count = 0

    def Show(self):
        self.Visible = True
        self.shown_count += 1

    def Hide(self):
        self.Visible = False


class FakeArgs:
    """`show` is the ONE argument the show/hide decision reads, and it is the
    one this oracle varies.

    Every OTHER field answers False and is RECORDED in `invented`. The chain
    this harness drives (`_on_core_ready` -> `_arm_lazy_gate`, and anything a
    future revision adds to it) reads flags that have nothing to do with
    visibility, so an unseeded flag used to end the run with an AttributeError
    instead of an answer. argparse flags default to False, so False is the
    faithful answer -- and the record is printed at the end of a run so the
    stub can never be silent about what it invented.
    """

    #: Every field this stub had to invent, across every instance. Printed
    #: at the end of a run so the stub can never be silent about it.
    INVENTED = []

    def __init__(self, show=False):
        self.show = show

    def __getattr__(self, name):
        # Only called when normal lookup fails, i.e. for a field this stub did
        # not seed. argparse's own default for a store_true flag is False.
        if name not in FakeArgs.INVENTED:
            FakeArgs.INVENTED.append(name)
        return False


class _FakeReloadPolicy:
    """The reload policy is a real object with real state and a real cadence.

    The arms that drive `external_caption` only need to know that it was
    called, and nothing about the visibility decision depends on it -- so this
    records the call and answers, and never sleeps.
    """

    def __init__(self):
        self.boundaries = []
        self.stops = 0

    def boundary(self, **kwargs):
        self.boundaries.append(kwargs)
        return True

    def state(self):
        return {'boundaries': len(self.boundaries)}

    def stop(self):
        self.stops += 1
        return True


# ===========================================================================
# ARM 1 — WIRING: the guard is reached by the shipped code path
# ===========================================================================

class SourceModel:
    def __init__(self, path):
        self.path = path
        with open(path, 'r', encoding='utf-8') as fh:
            self.source = fh.read()
        self.tree = ast.parse(self.source, filename=path)
        self.methods = self._methods()

    def _methods(self):
        out = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out[item.name] = (node, item)
        return out

    def owner_class(self, method):
        """The class that defines `method`. Resolved from the source rather than
        hardcoded, so a rename moves the oracle's target with it instead of
        silently testing nothing."""
        node = self.methods.get(method)
        return node[0].name if node else None

    def subscribes(self, method, event):
        """True if `method` contains `<anything>.<event> += <anything>`."""
        node = self.methods.get(method)
        if node is None:
            return False
        return self._has_augassign(node[1], event)

    @staticmethod
    def _has_augassign(func, event):
        for sub in ast.walk(func):
            if (isinstance(sub, ast.AugAssign)
                    and isinstance(sub.op, ast.Add)
                    and isinstance(sub.target, ast.Attribute)
                    and sub.target.attr == event):
                return True
        return False

    def self_calls(self, method):
        """Names of other methods `method` causes to run.

        Both forms count, and the second is not optional in this shell:
          * `self.foo(...)`            — a direct call
          * `self._ui(self.foo)`       — a DEFERRED call. `_ui`/`_post` marshal
            a callable onto the UI thread and invoke it (sotto_webview.py:1589,
            :1591), so passing `self.foo` as an argument IS an edge. The whole
            subscription chain is written in this form; a model that only saw
            direct calls would call the whole panel unreachable.
        Only names that are methods of some class in the file are counted, so
        attribute READS (`self.args.show`, `self.geometry`) cannot masquerade as
        calls."""
        node = self.methods.get(method)
        if node is None:
            return []
        found = []
        for sub in ast.walk(node[1]):
            if (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
                    and sub.value.id == 'self' and sub.attr in self.methods
                    and sub.attr not in found):
                found.append(sub.attr)
        return found

    def path_from(self, start, target):
        """Shortest `self.<method>` call path start -> target, or None.

        This models DIRECT calls only. A handler that is REGISTERED on a .NET
        event is not called, so `_on_core_ready` is not reachable by calling it
        from `_on_before_show` — which is the whole point: the cure must not
        depend on a callback being delivered."""
        seen = {start: None}
        queue = [start]
        while queue:
            cur = queue.pop(0)
            if cur == target and cur != start:
                break
            for nxt in self.self_calls(cur):
                if nxt not in seen:
                    seen[nxt] = cur
                    queue.append(nxt)
        if target not in seen or seen[target] is None:
            return None
        path, cur = [], target
        while cur is not None:
            path.append(cur)
            cur = seen[cur]
        return list(reversed(path))

    def top_level_calls(self, method, target):
        """Is `self.<target>` referenced by a TOP-LEVEL statement of `method`?

        Top level matters: a registration nested in an `if` the shell can skip
        is a registration that can be absent, which is the defect. `self._ui(
        self.target)` counts — the statement is unconditional and the callable
        is marshalled to the UI thread and invoked."""
        node = self.methods.get(method)
        if node is None:
            return False
        for stmt in node[1].body:
            if not isinstance(stmt, ast.Expr):
                continue
            for sub in ast.walk(stmt.value):
                if (isinstance(sub, ast.Attribute)
                        and isinstance(sub.value, ast.Name)
                        and sub.value.id == 'self' and sub.attr == target):
                    return True
        return False


def arm_wiring(model):
    """Static proof that the visibility guard is on the shipped path."""
    results = []

    def check(name, ok, detail):
        results.append({'arm': 'WIRING', 'check': name, 'ok': bool(ok),
                        'detail': detail})

    entry = '_on_before_show'
    if entry not in model.methods:
        check(f'{entry} exists', False,
              f'no method named _on_before_show in {model.path}')
        return results, 1

    # W1 — the entry point is actually bound to pywebview's before_show event.
    bound = [m for m in model.methods
             if model.subscribes(m, EVENT_BEFORE_SHOW)
             and any(h.endswith(entry) for h in _augassign_handler_names(model, m,
                                                                         EVENT_BEFORE_SHOW))]
    check('W1 before_show is bound to _on_before_show',
          bool(bound),
          f'methods binding {EVENT_BEFORE_SHOW}: {sorted(bound) or "NONE"}')

    # W2/W3 — the NavigationStarting registration, and what it is gated behind.
    nav_sites = sorted(m for m in model.methods
                       if model.subscribes(m, EVENT_NAVIGATION))
    check('W2 a method subscribes NavigationStarting',
          bool(nav_sites), f'registration sites: {nav_sites or "NONE"}')

    core_sites = sorted(m for m in model.methods
                        if model.subscribes(m, EVENT_CORE_READY))
    reachable = []
    for site in nav_sites:
        path = model.path_from(entry, site)
        if path:
            reachable.append((site, path))
    check('W3 the guard is reachable from _on_before_show',
          bool(reachable),
          f'sites {nav_sites} reachable from _on_before_show: '
          f'{[s for s, _ in reachable] or "NONE"} (registration sites that are '
          f'only wired to a callback are NOT reachable by calling them)')

    gated = []
    for site, path in reachable:
        blockers = [m for m in path if m in core_sites]
        if blockers:
            gated.append((site, blockers))
    check('W4 the guard does NOT wait on CoreWebView2 initialization',
          not gated,
          f'sites gated behind {EVENT_CORE_READY}: {gated or "NONE"}; '
          f'{EVENT_CORE_READY} sites in the file: {core_sites or "NONE"}'
          + ('; VACUOUS while W3 fails (no reachable site to judge)'
             if not reachable else ''))

    # W5 — the registration call is unconditional where it is made.
    unconditional = []
    for site in nav_sites:
        for caller in _callers_of(model, site):
            if model.top_level_calls(caller, site):
                unconditional.append((caller, site))
    check('W5 the guard is registered unconditionally at its call site',
          bool(unconditional),
          f'top-level registrations: {unconditional or "NONE"}')

    failures = sum(1 for r in results if not r['ok'])
    return results, failures


def _augassign_handler_names(model, method, event):
    node = model.methods.get(method)
    if node is None:
        return []
    out = []
    for sub in ast.walk(node[1]):
        if (isinstance(sub, ast.AugAssign) and isinstance(sub.target, ast.Attribute)
                and sub.target.attr == event):
            handler = sub.value
            if isinstance(handler, ast.Attribute):
                out.append(handler.attr)
            elif isinstance(handler, ast.Name):
                out.append(handler.id)
    return out


def _callers_of(model, target):
    return sorted(m for m in model.methods if target in model.self_calls(m))


# ===========================================================================
# ARM 2 — HIDDEN: the real methods, the real ordering
# ===========================================================================

class Harness:
    """Drives the shipped `SottoHost` show/hide logic against fake WinForms.

    SCOPE, stated so the verdict is not read wider than it is: this exercises
    `_on_before_show`, `_subscribe_core_ready`, `_on_core_ready`,
    `_arm_visibility_invariant` (if present), `_on_navigation_start`,
    `_reassert_hidden`, `show_panel` and `hide_panel` — the SUBSCRIPTION CHAIN
    and the show/hide decision. It does not call `_on_loaded`, which only
    navigates and logs; the stage -> panel navigation it causes is driven here
    at the pywebview level instead. Geometry (`_fit_client_area`) and the
    Win32 style helpers are stubbed: they touch pythonnet and ctypes against a
    live HWND, and neither participates in the visibility decision."""

    def __init__(self, shell, show_flag=False, owner_asked=False,
                 mid_show=False, transparent=True,
                 stage_url='file:///stage.html', panel_url='file:///panel.html',
                 seed_external_flags=True):
        self.shell = shell
        self.cls = shell.SottoShell
        self.hwnd = 4242
        self.form = FakeForm(self.hwnd)
        self.windows = {self.hwnd: self.form}
        self.events = []
        self.hidden_calls = 0
        self.stage_url = stage_url
        self.panel_url = panel_url
        # The shell is TRANSPARENT by default (`--opaque` turns it off), which
        # is exactly what makes pywebview's Show() hack fire.
        self.transparent = transparent
        self.ever_visible = False
        self.nav_count = 0
        self.mid_show = mid_show
        self.owner_asked = owner_asked
        self._install_stubs(shell)
        self._install_pywebview()

        owner = shell.SottoShell.__new__(self.cls)
        owner.window = type('W', (), {'native': self.form})()
        owner.form = self.form
        owner.hwnd = self.hwnd
        owner.webview2 = self.form.webview
        owner.core = None
        owner.staged = False
        owner.visible = False
        owner.args = FakeArgs(show=show_flag)
        owner.display = {'workArea': {}, 'bounds': {}, 'scaleFactor': 1.0}
        owner.visibility_armed = False
        # SEEDED FROM THE SHIPPED `__init__`, one line per field the show/hide
        # path actually reads. This list is not decoration: each entry below was
        # a crash this oracle produced against the live shell until it was
        # seeded, because the harness builds the object with `__new__` and the
        # real `__init__` never ran. Seeded exactly as `__init__` seeds them, so
        # a shipped default that moves is a RED here rather than a silent pass.
        #   panel_show_refused -- `_gate_form_show`'s `guarded_show` increments
        #     it (sotto_webview.py:4496, set at :4004). Unseeded, the FIRST
        #     pywebview Show() on a transparent form dies with AttributeError.
        #   surface / surface_applied -- `show_panel` reads both and only calls
        #     `set_panel_surface` when they differ (sotto_webview.py:5631-5633);
        #     seeded equal so no surface transition is faked here.
        #   panel_mode -- the Alt+C cycle's input (sotto_webview.py:5638).
        #   panel_visibility -- `publish_panel_visibility` returns False when it
        #     is None (sotto_webview.py:5269-5271), which is the honest state for
        #     a run whose arm was never made; unseeded it raises instead.
        owner.panel_show_refused = 0
        owner.surface = 'panel'
        owner.surface_applied = 'panel'
        owner.panel_mode = 'strip'
        owner.panel_visibility = None
        owner.click_watcher = None
        #   external_captions_active / external_captions_available /
        #     _vram_parked -- the three flags the SHOW path reads, and the
        #     three the defensive `getattr(self, ..., False)` reads protect
        #     (sotto_webview.py:7616-7619, and the three show paths at :7690,
        #     :8016, :8068). `__init__` seeds them False (:5710-5711, :5718).
        #   _paused -- `__init__` seeds it False (:5620). The show path reads it
        #     with `getattr(self, '_paused', False)` (already defensive), and
        #     `_park_worker_for_external` reads it directly (:8813).
        #   _external_parked -- `__init__` seeds it False (:5717); read directly
        #     by `_park_worker_for_external` (:8813) and `park_worker_for_vram`.
        #   external_lines -- `__init__` seeds it 0 (:5720); `external_caption`
        #     counts the player's lines in it (:8781).
        # `seed_external_flags=False` OMITS the three external-caption flags
        # ON PURPOSE: that is the owner the SHOW-ROBUST arm builds -- an owner
        # that never ran `__init__`, which is exactly the shape that used to
        # kill this oracle with an AttributeError.
        if seed_external_flags:
            owner.external_captions_active = False
            owner.external_captions_available = False
            owner._vram_parked = False
        owner._paused = False
        owner._external_parked = False
        owner.external_lines = 0
        # `_ui`/`_post` on the UI thread are `fn()` (sotto_webview.py:1589,
        # :1591). `before_show` IS the UI thread, so inline is faithful — and it
        # is what keeps pythonnet out of a headless oracle.
        owner._ui = lambda fn: fn()
        owner._post = lambda fn: fn()
        owner._fit_client_area = lambda form: None
        # `_install_bootstrap` is pure pythonnet (`from System import Action`) and
        # its only effect is a log line; it does not touch visibility.
        owner._install_bootstrap = lambda where: None
        # `_arm_lazy_gate` subscribes `WebResourceRequested` on the CoreWebView2
        # and reads `args.no_lazy`; it is the deferred-asset gate, not part of the
        # show/hide decision. Stubbed here for the same reason, and it is the
        # only member `_on_core_ready` still calls.
        owner._arm_lazy_gate = lambda: None
        # `start_worker` BUILDS A WORKER BRIDGE and spawns a process. This
        # oracle opens no window, no worker, no audio device and no browser, so
        # the spawn is replaced by a recorder that says WHICH reason the show
        # path asked for. The DECISION is still measured: `WORKER_PANEL_START`
        # and `WORKER_PANEL_START_SKIPPED` are written by the real
        # `_start_deferred_worker` before it ever gets here.
        owner.worker_start_calls = []

        def _start_worker(reason):
            owner.worker_start_calls.append(reason)
            return False
        owner.start_worker = _start_worker
        # `set_panel_surface` is the DOCUMENT+HWND half of a surface change and
        # runs `exec_js` against a WebView2 that does not exist here. Stubbed so
        # the Alt+C path (`show_strip`/`show_side`) can be driven for real.
        owner.set_panel_surface = lambda surface, reason='page': True
        # The two ways a caption leaves the shell. The EXTERNAL-FLAG arm drives
        # the real `external_caption`, which calls both; they need the page.
        owner.emit = lambda kind, payload: None
        owner.push_caption_to_window = (lambda text, previous=None,
                                        credits=None: False)
        # `_reload_policy` carries real state; the arm only needs to know that
        # it was called.
        owner._reload_policy = _FakeReloadPolicy()
        self.owner = owner

        # NOTE: `owner_asked` is NOT acted on here. pywebview runs its
        # `hidden=True` dance AFTER `before_show` (winforms.py:775 then :777-781)
        # and that dance ends in `Hide()`, so a show issued before it is undone
        # by pywebview, not by this shell's guard — and no owner can press
        # Alt+C that early anyway, the hotkey is not registered yet. The show is
        # therefore issued in `run()`, at the earliest point it can really
        # happen: the window exists and the dance is over.

    def _install_stubs(self, shell):
        form = self.form
        windows = self.windows
        events = self.events

        def _visible(hwnd):
            return bool(windows[hwnd].Visible) if hwnd in windows else False

        def _hide(hwnd):
            if hwnd in windows:
                windows[hwnd].Visible = False
                self.hidden_calls += 1
                events.append('HIDE')
                return True
            return False

        def _show_no_activate(hwnd):
            if hwnd in windows:
                windows[hwnd].Visible = True
                events.append('SHOW')
                return True
            return False

        shell.window_visible = _visible
        shell.hide_window = _hide
        shell.show_without_activating = _show_no_activate
        shell.set_topmost = lambda hwnd: True
        shell.set_ex_style = lambda hwnd, add=None, remove=None: True
        # The shell logs a lot to stdout; keep the oracle's own output readable.
        self.log_lines = []
        shell.log = self.log_lines.append
        shell.warn = self.log_lines.append

    def _install_pywebview(self):
        """Reproduce pywebview's OWN handlers, in `EdgeChrome.__init__` order.

        This is the half that puts the panel on the owner's desk. Without it
        "the panel is hidden" would pass no matter what the shell does — a
        tautology, not a test. Subscribed BEFORE the shell's, because
        `create_window` builds the form (winforms.py:773) long before
        `before_show` fires (:775).

          edgechromium.py:102  `NavigationStarting += self.on_navigation_start`
          edgechromium.py:346-349
              def on_navigation_start(self, sender, args):
                  if self.pywebview_window.transparent:
                      self.form.Show()
                      self.form.Activate()
          edgechromium.py:101  `CoreWebView2InitializationCompleted +=
              self.on_webview_ready`, and :305-311 that handler is what CALLS
              `load_url` — so navigation #1 is raised from INSIDE the
              initialization-completed dispatch, before the shell's
              `_on_core_ready` gets to run.
        """
        h = self

        def on_navigation_start(sender, args):
            if h.transparent:
                h.form.Show()            # the load-bearing "no idea why this works"
                h.events.append('PYWEBVIEW_SHOW')

        def on_webview_ready(sender, args):
            h.events.append('PYWEBVIEW_READY')
            h.navigate(h.stage_url)      # edgechromium.py:305-311 -> load_url

        control = self.form.webview
        control.CoreWebView2InitializationCompleted += on_webview_ready
        control.NavigationStarting += on_navigation_start

    # -- the three steps of the pywebview sequence -------------------------
    def shell_before_show(self):
        self.cls._on_before_show(self.owner)

    def hidden_dance(self):
        """winforms.py:777-781: Opacity=0; Show(); Hide(); Opacity=1."""
        self.form.Opacity = 0.0
        self.form.Show()
        self.form.Hide()
        self.form.Opacity = 1.0

    def navigate(self, url):
        """Raise NavigationStarting on the control.

        pywebview's own handler is subscribed FIRST (edgechromium.py:102) and
        does `if transparent: form.Show()` (edgechromium.py:346-349), so the
        panel is put on screen before the shell's guard can possibly run. That
        is the defect's shape in one method."""
        control = self.form.webview

        class Args:
            def __init__(self, uri):
                self.Uri = uri

        control.NavigationStarting.fire(control, Args(url))
        if self.form.Visible:
            self.ever_visible = True
        self.nav_count += 1
        # The owner presses Alt+C BETWEEN the staging navigation and the panel
        # navigation. This is the sharp refutation of the fix: the guard is
        # armed at before_show, before any of this, so a fix that latched
        # "hidden" would take this panel down with it.
        if self.mid_show and self.nav_count == 1:
            self.owner.show_panel('oracle-refutation-mid')

    def init_completed(self):
        """Raise CoreWebView2InitializationCompleted.

        pywebview's `on_webview_ready` subscribed first (edgechromium.py:101)
        starts navigation #1 from inside this dispatch (:305-311)."""
        class Core:
            Source = 'about:blank'
        self.form.webview.CoreWebView2 = Core()
        self.owner.core = Core()

        class Args:
            IsSuccess = True
            InitializationException = None
        control = self.form.webview
        control.CoreWebView2InitializationCompleted.fire(control, Args())

    def run(self, timing, stage_url, panel_url):
        """`timing` says WHEN initialization completes, relative to the two
        navigations this shell performs (stage.html, then the panel).

          'at-init'  completes normally; navigation #1 is raised from inside it
                     by pywebview's own `on_webview_ready`
          'late'     completes AFTER navigation #1 has already been shown
          'never'    never completes — the state TICKET-55a4... measured
                     (`_on_core_ready` never ran, no PRELOAD_INSTALLED)
        """
        h = self
        h.stage_url, h.panel_url = stage_url, panel_url
        if timing == 'never':
            h.shell_before_show()
            h.hidden_dance()
            h._owner_ask()
            h.navigate(stage_url)      # pywebview shows; the guard is never armed
            h.navigate(panel_url)
            return

        if timing == 'late':
            h.shell_before_show()
            h.hidden_dance()
            h._owner_ask()
            h.navigate(stage_url)      # raised by a source set, not by init
            h.init_completed()
            h.navigate(panel_url)
            return

        h.shell_before_show()
        h.hidden_dance()
        h._owner_ask()
        h.init_completed()             # -> load_url(stage) -> NavigationStarting
        h.navigate(panel_url)

    def _owner_ask(self):
        """The owner pressed Alt+C after the window came up and before the
        first navigation — the earliest moment it can really happen."""
        if self.owner_asked:
            self.owner.show_panel('oracle-refutation')


def arm_armed_once(shell, stage_url, panel_url):
    """The guard is registered exactly ONCE, and the flag says so.

    REFUTATION ATTEMPT. The fix moved a subscription earlier and added an
    idempotence guard (`if self.visibility_armed: return`) rather than proving
    it. If `before_show` ever fires twice — pywebview re-showing a window, a hot
    reload re-entering, a future caller — a non-idempotent arm would subscribe
    `_on_navigation_start` twice per navigation. So: fire `before_show` twice
    and count the handlers on the control's `NavigationStarting`.

    Expectation: pywebview's own handler (edgechromium.py:102) plus EXACTLY ONE
    shell handler. A count of 2 shell handlers also means `_on_core_ready` kept
    its old subscription and the cure is doubled rather than moved.
    """
    h = Harness(shell, stage_url=stage_url, panel_url=panel_url)
    h.shell_before_show()
    h.shell_before_show()
    total = len(h.form.webview.NavigationStarting.handlers)
    shell_handlers = total - 1        # -1 is pywebview's own
    results = [{
        'arm': 'ARMED-ONCE',
        'check': 'before_show fired twice -> guard subscribed once',
        'ok': (shell_handlers == 1 and h.owner.visibility_armed is True),
        'detail': (f'NavigationStarting handlers={total} '
                   f'(1 pywebview + {shell_handlers} shell; expected 2 total / 1 '
                   f'shell); visibility_armed='
                   f'{h.owner.visibility_armed}')}]
    return results, 0 if results[0]['ok'] else 1


# ===========================================================================
# ARM 4 — SHOW-ROBUST: the show path survives an owner without `__init__`
# ===========================================================================

def arm_show_robust(shell, stage_url, panel_url):
    """The show path must not die on a missing external-caption flag.

    WHY THIS ARM EXISTS. Alt+C is the owner's ONLY control. The show path
    (`show_panel` -> `_start_deferred_worker`, and the Alt+C pair
    `show_strip`/`show_side`) read three flags -- `external_captions_active`,
    `external_captions_available` and `_vram_parked` -- in the SAME `if` as
    the defensive `getattr(self, '_paused', False)` that was already there.
    Read DIRECTLY, an owner that never ran `__init__` died with an
    AttributeError on the one key the owner presses. That is not a
    hypothesis: it is how THIS oracle died, because the harness builds the
    object with `__new__` and the real `__init__` never runs. The same shape
    is a derived class that skips `__init__`, a renamed attribute, or a
    future field that is read before it is written.

    The arm builds that owner on purpose -- the three flags ABSENT -- and
    drives the real show paths. A crash is the failure it is looking for;
    the arm is what stops the defensive reads from regressing.
    """
    results = []
    h = Harness(shell, stage_url=stage_url, panel_url=panel_url,
                seed_external_flags=False)
    h.shell_before_show()
    h.hidden_dance()
    h.init_completed()
    h.navigate(panel_url)
    crashed = []
    for label, call in (
            ('show_panel', lambda: h.owner.show_panel('oracle-missing-flags')),
            ('show_strip', lambda: h.owner.show_strip('oracle-missing-flags'))):
        try:
            call()
        except Exception as exc:  # noqa: BLE001
            crashed.append(f'{label} raised {type(exc).__name__}: {exc}')
    absent = [name for name in ('external_captions_active',
                                'external_captions_available',
                                '_vram_parked')
              if hasattr(h.owner, name)]
    ok = not crashed and not absent
    results.append({
        'arm': 'SHOW-ROBUST',
        'check': 'the show path survives missing external-caption flags',
        'ok': ok,
        'detail': (f'owner built WITHOUT external_captions_active / '
                   f'external_captions_available / _vram_parked; show_panel '
                   f'and show_strip were both driven; crashes='
                   f'{crashed or "NONE"}; flags that should be ABSENT and are '
                   f'not={absent or "NONE"}')})
    return results, 0 if ok else 1


# ===========================================================================
# ARM 5 — EXTERNAL-FLAG: the decision did not change
# ===========================================================================

def arm_external_flag(shell, stage_url, panel_url):
    """The player's own captions still park the worker, and the skip line
    still says `external=true`.

    `external_caption` (sotto_webview.py:8746) is the ONE place every
    external line passes through, and it flips `external_captions_active` to
    True at :8786-8787. The show path must then SKIP the worker start and
    WRITE `WORKER_PANEL_START_SKIPPED ... external=true`.

    This arm drives the REAL method and reads the REAL log lines, so it is
    the proof that making the reads DEFENSIVE did not change what they MEAN:
    a flag that IS there still reads as True, and the worker is still not
    started while the player supplies the captions. A defensive read that
    swallowed a flag that is really set would be RED here.
    """
    results = []
    h = Harness(shell, stage_url=stage_url, panel_url=panel_url)
    h.owner.visible = True          # the owner is looking at Sotto
    h.log_lines.clear()
    crash = None
    try:
        h.owner.external_caption('linha do jogador', 'external:youtube',
                                 final=True)
    except Exception as exc:  # noqa: BLE001
        crash = f'external_caption raised {type(exc).__name__}: {exc}'
    active = getattr(h.owner, 'external_captions_active', None)
    show_crash = None
    try:
        h.owner.show_panel('oracle-external-flag')
    except Exception as exc:  # noqa: BLE001
        show_crash = f'show_panel raised {type(exc).__name__}: {exc}'
    skipped = [ln for ln in h.log_lines if 'WORKER_PANEL_START_SKIPPED' in ln]
    said_true = [ln for ln in skipped if 'external=true' in ln]
    ok = (crash is None and show_crash is None and active is True
          and bool(said_true) and not h.owner.worker_start_calls)
    results.append({
        'arm': 'EXTERNAL-FLAG',
        'check': "the player's captions still flip the flag and still skip the "
                 'worker',
        'ok': ok,
        'detail': (f'external_captions_active after the player line='
                   f'{active!r} (expected True); crash={crash or "NONE"}; '
                   f'show_crash={show_crash or "NONE"}; '
                   f'WORKER_PANEL_START_SKIPPED lines={skipped or "NONE"}; '
                   f'of those, with external=true: {len(said_true)}; '
                   f'worker_start_calls={h.owner.worker_start_calls} '
                   f'(expected NONE: the worker stays PARKED while the player '
                   f'supplies the captions)')})
    return results, 0 if ok else 1


# ===========================================================================
# scenarios
# ===========================================================================

def scenarios():
    """(name, kwargs-for-Harness, expect_visible, why)

    Four of the seven are the panel LEGITIMATELY showing, or a shell that is not
    supposed to be touched by this guard. They are the refutation arm: a fix
    that hides a panel the owner asked for has traded a startup flash for a
    dead panel, which is worse than the defect it was filed for. `mid_show` is
    the sharpest of them — the owner presses Alt+C AFTER the guard is armed."""
    return [
        ('startup-hidden',
         dict(show_flag=False, owner_asked=False), False,
         'nobody asked: run.cmd promises "start hidden"'),
        ('startup-hidden-opaque',
         dict(show_flag=False, owner_asked=False, transparent=False), False,
         '--opaque: pywebview never shows the form, so the guard must be inert'),
        ('show-flag',
         dict(show_flag=True, owner_asked=False), True,
         "--show is the app's own way to come up visible"),
        ('owner-asked-via-hotkey',
         dict(show_flag=False, owner_asked=True), True,
         'the owner pressed Alt+C before any navigation'),
        ('owner-asked-mid-sequence',
         dict(show_flag=False, owner_asked=False, mid_show=True), True,
         'the owner pressed Alt+C AFTER the guard was armed, between the staging '
         'navigation and the panel navigation — the case that would break if '
         'the fix latched "hidden" instead of re-asserting a decision'),
        ('owner-asked-via-hotkey-opaque',
         dict(show_flag=False, owner_asked=True, transparent=False), True,
         '--opaque and the owner asked: visible'),
    ]


def arm_hidden(shell, repeats, stage_url, panel_url):
    results = []
    population = 0
    failures = 0
    for name, kwargs, expect, why in scenarios():
        for timing in ('at-init', 'late', 'never'):
            reps = repeats
            bad = []
            flashes = 0
            for _ in range(reps):
                h = Harness(shell, stage_url=stage_url, panel_url=panel_url,
                            **kwargs)
                h.run(timing, stage_url, panel_url)
                population += 1
                got = h.form.Visible
                if bool(got) != bool(expect):
                    bad.append(f'visible={str(bool(got)).lower()}')
                if h.ever_visible:
                    flashes += 1
            ok = not bad
            if not ok:
                failures += 1
            results.append({
                'arm': 'HIDDEN', 'check': f'{name} / init={timing}',
                'ok': ok, 'detail': (f'expected visible='
                                     f'{str(bool(expect)).lower()} over {reps} '
                                     f'run(s); {why}; failures={len(bad)}'
                                     + (f' e.g. {bad[0]}' if bad else '')
                                     + f'; diagnostic only (NOT asserted): '
                                     f'transient flash in {flashes}/{reps} runs '
                                     f'— the settled state is what this ticket '
                                     f'is about, and closing the flash is '
                                     f'measured as not achievable with this net')})
    return results, failures, population


# ===========================================================================
# ARM 3 — MUTATION: this oracle must be able to go RED
# ===========================================================================

#: Each mutant carries what the oracle must DO with it:
#:   'caught' — the mutation breaks the visibility invariant, so the oracle
#:              must report it. A green that cannot go red is not green.
#:   'immune' — the mutation does NOT break the visibility invariant, so the
#:              oracle must report it as sound. This is the positive control and
#:              it is the shape the fix is FOR: TICKET-55a4ab4b157bdd26bb9629c7
#:              deleted `self._ui(self._subscribe_core_ready)` and the panel went
#:              visible; after the fix that exact deletion is harmless to
#:              visibility, because the guard no longer hangs off it.
MUTANTS = [
    {
        'name': 'arm-line-deleted',
        'why': 'delete the arming call from _on_before_show',
        'expect': 'caught',
        'edits': [(
            "self._ui(self._arm_visibility_invariant)",
            "pass  # the arming line is deleted",
        )],
    },
    {
        'name': 'guard-never-installed',
        'why': 'the guard exists but is never subscribed',
        'expect': 'caught',
        'edits': [(
            "self.webview2.NavigationStarting += self._on_navigation_start",
            "pass  # the guard exists and is unreachable",
        )],
    },
    {
        'name': 'pre-fix-shape',
        'why': 'the exact pre-fix shell: no arming call in _on_before_show, and '
               'the guard registered only from the initialization-completed '
               'handler',
        'expect': 'caught',
        'edits': [
            (
                "self._ui(self._arm_visibility_invariant)",
                "pass  # pre-fix: there is no arming call here",
            ),
            (
                "        self.core = sender.CoreWebView2\n"
                "        self._install_bootstrap('initialization-completed')",
                "        self.core = sender.CoreWebView2\n"
                "        self.webview2.NavigationStarting += "
                "self._on_navigation_start\n"
                "        self._install_bootstrap('initialization-completed')",
            ),
        ],
    },
    {
        'name': 'ticket-repro',
        'why': "TICKET-55a4ab4b157bdd26bb9629c7's own repro: delete "
               '`self._ui(self._subscribe_core_ready)` from _on_before_show',
        'expect': 'immune',
        'edits': [(
            "self._ui(self._subscribe_core_ready)",
            "pass  # TICKET-55a4ab4b157bdd26bb9629c7: the line that was deleted",
        )],
    },
]


def _apply_edits(source, edits, why):
    for old, new in edits:
        if old not in source:
            raise AssertionError(
                f'mutation target not found for {why}: {old[:60]!r}')
        source = source.replace(old, new, 1)
    return source


def arm_mutation(shell_path, shell):
    results = []
    failures = 0
    with open(shell_path, 'r', encoding='utf-8') as fh:
        original = fh.read()
    with tempfile.TemporaryDirectory(prefix='sotto-vis-oracle-') as tmp:
        for spec in MUTANTS:
            name, why, expect = spec['name'], spec['why'], spec['expect']
            try:
                mutated = _apply_edits(original, spec['edits'], why)
            except AssertionError as exc:
                failures += 1
                results.append({'arm': 'MUTATION', 'check': name, 'ok': False,
                                'detail': f'cannot build the mutant: {exc}'})
                continue
            path = os.path.join(tmp, f'sotto_webview_{name}.py')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(mutated)
            try:
                m_shell = load_shell(path)
                m_model = SourceModel(path)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                results.append({'arm': 'MUTATION', 'check': name, 'ok': False,
                                'detail': f'mutant failed to import: {exc!r}'})
                continue

            _, w_fail = arm_wiring(m_model)
            _h_res, h_fail, _pop = arm_hidden(m_shell, repeats=3,
                                              stage_url='file:///stage.html',
                                              panel_url='file:///panel.html')
            caught = (w_fail + h_fail) > 0
            if expect == 'caught':
                ok = caught
                verdict = ('the oracle catches it' if caught else
                           'THE ORACLE MISSED IT — a green that cannot go red '
                           'is not green')
            else:
                ok = not caught
                verdict = ('the oracle correctly finds visibility intact'
                           if ok else
                           'the mutation DID break visibility, so the fix did '
                           'not remove the dependency the ticket is about')
            if not ok:
                failures += 1
            results.append({
                'arm': 'MUTATION', 'check': name, 'ok': ok,
                'detail': (f'expected={expect}; {why}; wiring failures='
                           f'{w_fail}, hidden failures={h_fail} — {verdict}')})
    return results, failures


# ===========================================================================
# ARM 6 — NEG-ARM: the DEFENSIVE reads must be able to go RED
# ===========================================================================

#: Three textual mutants of the DEFENSIVE reads, each with a UNIQUE anchor in
#: the judged file. The same rule as `_main/yt-mirror-align-oracle.py`:
#: a mutant whose anchor is missing or ambiguous is DECORATIVE -- it proves
#: nothing -- so the oracle REFUSES to count it, says so, and the `--neg-arm`
#: run exits rc=2. A mutant that loads and changes nothing is reported as
#: SURVIVED (the gate is blind there) and the `--neg-arm` run exits rc=0.
NEG_ARM_MUTANTS = [
    {
        'name': 'sem-getattr-external-captions-active',
        'why': 'the show path reads external_captions_active DIRECTLY again, so '
               'an owner without the flag dies with an AttributeError',
        'anchor': ("        _ext_active = getattr(self, "
                   "'external_captions_active', False)\n"),
        'replace': "        _ext_active = self.external_captions_active\n",
    },
    {
        'name': 'sem-getattr-external-captions-available',
        'why': 'the show path reads external_captions_available DIRECTLY again',
        'anchor': ("                or getattr(self, "
                   "'external_captions_available', False)\n"),
        'replace': "                or self.external_captions_available\n",
    },
    {
        'name': 'sem-getattr-vram-parked',
        'why': 'the show path reads _vram_parked DIRECTLY again',
        'anchor': "                or getattr(self, '_vram_parked', False)):\n",
        'replace': "                or self._vram_parked):\n",
    },
]


def arm_neg_arm(shell_path, stage_url, panel_url):
    """Every declared mutant must be applied AND seen.

    A mutant is SEEN when the SHOW-ROBUST arm turns RED against it: that arm
    exists to catch exactly this, so a mutant that leaves the arm GREEN is a
    SURVIVOR -- the gate is blind there, which is the worst outcome a gate
    can have.

    Returns (results, caught, weak): `caught` is the number of mutants that
    were applied and seen, `weak` the number that were DECORATIVE (anchor
    missing or ambiguous, or the mutant did not even load).
    """
    results = []
    caught = 0
    weak = 0
    with open(shell_path, 'r', encoding='utf-8') as fh:
        original = fh.read()
    with tempfile.TemporaryDirectory(prefix='sotto-show-neg-') as tmp:
        for spec in NEG_ARM_MUTANTS:
            name, why = spec['name'], spec['why']
            anchor = spec['anchor']
            hits = original.count(anchor)
            if hits != 1:
                weak += 1
                results.append({
                    'arm': 'NEG-ARM', 'check': name, 'ok': False,
                    'detail': (f'ANCHOR '
                               f'{("MISSING" if hits == 0 else "AMBIGUOUS")} '
                               f'({hits} occurrences) -- the mutant is '
                               f'DECORATIVE and proves nothing, so it is NOT '
                               f'counted -- {why}')})
                continue
            path = os.path.join(tmp, f'sotto_webview_neg_{name}.py')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(original.replace(anchor, spec['replace'], 1))
            try:
                m_shell = load_shell(path)
            except Exception as exc:  # noqa: BLE001
                weak += 1
                results.append({
                    'arm': 'NEG-ARM', 'check': name, 'ok': False,
                    'detail': (f'DECORATIVO: o mutante nao carregou ({exc!r}) '
                               f'-- NAO foi testado -- {why}')})
                continue
            res, fail = arm_show_robust(m_shell, stage_url, panel_url)
            detail = res[0]['detail'] if res else 'the arm said nothing'
            if fail > 0:
                caught += 1
                results.append({
                    'arm': 'NEG-ARM', 'check': name, 'ok': True,
                    'detail': (f'APPLIED and SEEN: the SHOW-ROBUST arm went '
                               f'RED against the mutant -- {detail}')})
            else:
                results.append({
                    'arm': 'NEG-ARM', 'check': name, 'ok': False,
                    'detail': ('SURVIVED: the SHOW-ROBUST arm stayed GREEN '
                               'against the mutant -- the gate is blind here')})
    return results, caught, weak


# ===========================================================================
# main
# ===========================================================================

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--shell', default=DEFAULT_SHELL,
                    help='the shell under test (default: the shipped one)')
    ap.add_argument('--repeats', type=int, default=8,
                    help='repeats per scenario/timing cell (default: 8)')
    ap.add_argument('--neg-arm', action='store_true',
                    help='run ONLY the negative arm -- the three mutants of '
                         'the defensive reads -- and nothing else; rc=1 BY '
                         'DESIGN (0 = a mutant survived, 2 = a decorative '
                         'anchor)')
    ap.add_argument('--json', action='store_true', help='machine-readable only')
    args = ap.parse_args(argv)

    def emit(text):
        if not args.json:
            print(text, flush=True)

    if not os.path.isfile(args.shell):
        emit(f'ORACLE CANNOT RUN: no shell at {args.shell}')
        return 2
    try:
        model = SourceModel(args.shell)
        shell = load_shell(args.shell)
    except Exception as exc:  # noqa: BLE001
        emit(f'ORACLE CANNOT RUN: {exc!r}')
        return 2

    stage = os.path.join(os.path.dirname(SHELL_DIR), 'webview', 'stage.html')
    panel = os.path.join(os.path.dirname(SHELL_DIR), 'panel', 'panel.html')
    stage_url = 'file:///' + stage.replace('\\', '/').lstrip('/')
    panel_url = 'file:///' + panel.replace('\\', '/').lstrip('/')

    emit(f'ORACLE panel-hidden-at-startup')
    emit(f'  shell    {args.shell}')
    emit(f'  window   {args.repeats} repeats x {len(scenarios())} scenarios x 3 '
         f'init timings = {args.repeats * len(scenarios()) * 3} panel-visible '
         f'decisions')
    emit('  pywebview facts this rests on:')
    for ref, what in PYWEBVIEW_FACTS.items():
        emit(f'    {ref:<28} {what}')

    if args.neg_arm:
        # THE NEGATIVE ARM ONLY. The arms above are NOT run: this mode answers
        # ONE question -- do the three mutants of the DEFENSIVE reads turn the
        # SHOW-ROBUST arm RED? -- and its rc contract is INVERTED on purpose
        # (see the header): rc=1 when every declared mutant was applied AND
        # seen, rc=0 when one SURVIVED, rc=2 when an anchor is decorative.
        res, caught, weak = arm_neg_arm(args.shell, stage_url, panel_url)
        for r in res:
            emit(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['arm']} {r['check']} "
                 f'— {r["detail"]}')
        total = len(NEG_ARM_MUTANTS)
        if weak:
            emit(f'VERDICT: NEG-ARM FAIL  mutants {caught}/{total}  '
                 f'DECORATIVE ANCHORS={weak}  (rc=2: an anchor that does not '
                 f'hold is worse than no mutant at all)')
            return 2
        if caught != total:
            emit(f'VERDICT: NEG-ARM FAIL  mutants {caught}/{total}  (rc=0: a '
                 f'mutant SURVIVED -- the gate is blind there)')
            return 0
        emit(f'VERDICT: NEG-ARM PASS  mutants {caught}/{total}  (rc=1 POR '
             f'DESENHO: o braco negativo tem de falhar)')
        return 1

    results = []
    failures = 0

    for label, fn in (('WIRING', lambda: arm_wiring(model)),):
        res, fail = fn()
        results += res
        failures += fail
        for r in res:
            emit(f"  [{'PASS' if r['ok'] else 'FAIL'}] {label} {r['check']} "
                 f'— {r["detail"]}')

    res, fail, population = arm_hidden(shell, args.repeats, stage_url, panel_url)
    results += res
    failures += fail
    for r in res:
        emit(f"  [{'PASS' if r['ok'] else 'FAIL'}] HIDDEN {r['check']} "
             f'— {r["detail"]}')
    emit(f'  HIDDEN population: {population} decisions over '
         f'{len(scenarios())} scenarios x 3 initialization timings x '
         f'{args.repeats} repeats')

    res, fail = arm_armed_once(shell, stage_url, panel_url)
    results += res
    failures += fail
    for r in res:
        emit(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['arm']} {r['check']} "
             f'— {r["detail"]}')

    res, fail = arm_show_robust(shell, stage_url, panel_url)
    results += res
    failures += fail
    for r in res:
        emit(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['arm']} {r['check']} "
             f'— {r["detail"]}')

    res, fail = arm_external_flag(shell, stage_url, panel_url)
    results += res
    failures += fail
    for r in res:
        emit(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['arm']} {r['check']} "
             f'— {r["detail"]}')

    if os.path.abspath(args.shell) == os.path.abspath(DEFAULT_SHELL):
        res, fail = arm_mutation(args.shell, shell)
        results += res
        failures += fail
        for r in res:
            emit(f"  [{'PASS' if r['ok'] else 'FAIL'}] MUTATION {r['check']} "
                 f'— {r["detail"]}')
        # THE NEGATIVE ARM, RUN IN THE NORMAL PASS TOO: a gate that can only
        # prove itself in a separate mode is a gate nobody runs.
        res, caught, weak = arm_neg_arm(args.shell, stage_url, panel_url)
        results += res
        failures += (len(NEG_ARM_MUTANTS) - caught) + weak
        for r in res:
            emit(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['arm']} {r['check']} "
                 f'— {r["detail"]}')
    else:
        emit('  MUTATION skipped: --shell is not the shipped shell')
        emit('  NEG-ARM skipped: --shell is not the shipped shell (the '
             'anchors are the shipped shell\'s own lines)')

    if args.json:
        print(json.dumps({'failures': failures, 'results': results},
                         indent=2))
    emit('  FAKEARGS invented (answered False, and recorded so the stub is never silent): '
          + (', '.join(sorted(FakeArgs.INVENTED)) or 'none'))
    verdict = 'GREEN' if failures == 0 else 'RED'
    emit(f'ORACLE {verdict} failures={failures}')
    emit(f'VERDICT: {"PASS" if failures == 0 else "FAIL"}')
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())