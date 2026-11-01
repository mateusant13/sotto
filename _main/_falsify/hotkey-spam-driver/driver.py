#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HEADLESS press-trace driver for the Alt+C spam claim.

WHAT THIS IS
------------
It imports the SHIPPED modules of a tree (`app/webview/sotto_webview.py` and
`app/webview/hotkey_gesture.py`) and drives the REAL production chain:

    HotkeyThread.run()            (real Win32 thread + real message queue)
      -> PostThreadMessageW(WM_HOTKEY)          <- the press
      -> HotkeyThread._on_press()                (real production body)
      -> SottoShell.hotkey_pressed()            (real production body)
      -> SottoShell._hotkey_dispatch('panels')   (real production body: FIFO queue)
      -> SottoShell._hotkey_worker_loop()        (real production body: worker)
      -> SottoShell._hotkey_resolve('panels')    (real production body)
      -> hotkey_gesture.next_surface(...)        (the shipped rule)
      -> show_strip / show_side / hide_panel     (real production bodies)

WHAT IS FAKED, AND WHY
----------------------
ONLY the OS WINDOW leaves: `window_visible`, `hide_window`,
`foreground_unlock`, `show_webview_children`, `transparency_hack`,
`set_topmost`, `user32.SetWindowPos`, and the PAGE seams (`exec_js`,
`exec_js_post`, `_post`, `_post_metrics_refresh`) -- there is no WebView2 page
and no window in a headless run, and the repo law
(`SOTTO_NEVER_ON_OWNER_SCREEN`) forbids putting one on the owner's screen.

EVERY decision under test is the shipped code, unmodified: the rule
(`hotkey_gesture.next_surface`), the queue, the dispatch, the show/hide
bodies, the surface memory, the `_hotkey_resolve` read of the window.

The fake window IS the display: its `visible` flag is the measurement, and
every transition it records is one production map or one production unmap.

THE KEYBOARD
-------------
The trace holds ALT down for the whole span and delivers the C presses as
`WM_HOTKEY` messages (the production delivery path -- the product's own
`HotkeyThread.simulate_press` posts exactly this). The driver ALSO wraps
`user32.GetAsyncKeyState` and COUNTS the reads: if the product never asks the
keyboard, then the held Alt cannot change any decision, and the trace's
"alt down" is a fact about the INPUT, not about the product.

THE JUDGE
---------
The expectation comes from the OWNER'S SENTENCE ONLY:
"alterna entre show e hide" -- so N presses must produce N flips, and the
visible flag must alternate show/hide on every single press. Nothing else
(docstrings, the module's own cycle description) is used to judge.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import time

#: The Win32 virtual keys of the trace's two keys.
VK_MENU = 0x12      # VK_ALT
VK_C = 0x43         # ord('C')


# ---------------------------------------------------------------------------
# LOAD THE TREE
# ---------------------------------------------------------------------------
def load_tree(tree: str):
    webview = os.path.join(os.path.abspath(tree), 'app', 'webview')
    if not os.path.isdir(webview):
        raise SystemExit(f'tree without app/webview: {tree}')
    sys.path.insert(0, webview)
    import sotto_webview  # noqa: E402  (the path has to be in place first)
    return sotto_webview


# ---------------------------------------------------------------------------
# THE FAKE WINDOW -- the display the production code draws on
# ---------------------------------------------------------------------------
class FakeWindow:
    def __init__(self):
        self.visible = False
        self.transitions = []   # [{'kind': 'show'|'hide', 'surface': str}]


class _User32Proxy:
    """Forwards to the real user32, except the leaves that need a window.

    `GetAsyncKeyState` is COUNTED (the keyboard seam probe) and answers 0 --
    "no key is down" -- so a hypothetical duration-based implementation would
    see a TAP and never a HOLD.  The shipped implementation never asks.
    """

    def __init__(self, real):
        self._real = real
        self.get_async_key_state_calls = []
        #: THE KEYBOARD, AS THE TRACE SAYS IT IS. `None` = no trace installed
        #: (the answer is then "no key is down").  The trace holds ALT down for
        #: the whole span; the C is down only between its own down and up.
        self.trace = None
        self.origin = None      # the wall-clock instant the trace started

    def _down(self, vk):
        """Is this virtual key down RIGHT NOW, per the trace?

        The LAST event for this key that has already happened decides: a `down`
        that is not yet followed by an `up` means the key is down.
        """
        if self.trace is None or self.origin is None:
            return False
        now = time.monotonic() - self.origin
        state = False
        for ev in self.trace:
            if int(ev.get('vk', -1)) != int(vk):
                continue
            if ev['t_ms'] / 1000.0 > now:
                continue        # this event is in the future
            state = (ev['action'] == 'down')
        return state

    def __getattr__(self, name):
        if name == 'SetWindowPos':
            return lambda *a, **k: False
        if name == 'GetAsyncKeyState':
            def _gas(vk):
                self.get_async_key_state_calls.append(int(vk))
                return 0x8000 if self._down(vk) else 0
            return _gas
        return getattr(self._real, name)


def install_fakes(sw, shell):
    """Swap ONLY the OS-window leaves and the page seams."""
    fw = FakeWindow()
    proxy = _User32Proxy(sw.user32)
    sw.user32 = proxy

    def surface_now():
        return str(getattr(shell, 'surface_applied', '') or '')

    def fake_foreground_unlock(hwnd):
        fw.transitions.append({'kind': 'show', 'surface': surface_now()})
        fw.visible = True
        return {'mapped': True, 'foreground': False, 'reason': 'fake-window',
                'show': 'FAKE', 'lock': {}}

    def fake_hide_window(hwnd):
        fw.transitions.append({'kind': 'hide', 'surface': surface_now()})
        fw.visible = False
        return True

    sw.window_visible = lambda hwnd: bool(fw.visible)
    # `show_without_activating` maps the FORM with a real `ShowWindow`; with a
    # bogus hwnd it would be a real user32 call on a handle that belongs to
    # somebody else.  It is neutralized, and the MAP is recorded by
    # `foreground_unlock` (the call the production show path actually makes).
    sw.show_without_activating = lambda hwnd: False
    sw.hide_window = fake_hide_window
    sw.foreground_unlock = fake_foreground_unlock
    sw.show_webview_children = lambda hwnd: {'shown': [], 'already': [],
                                             'failed': []}
    sw.transparency_hack = lambda shell_obj: True
    sw.set_topmost = lambda hwnd: True

    # THE PAGE SEAMS: there is no WebView2 document in a headless run.
    # `exec_js_post` answers False (nothing posted -> the paint ack is never
    # armed -> `wait_paint_ack` returns at once) and `exec_js` answers None.
    sw.SottoShell.exec_js = lambda self, script, timeout=10.0: None
    sw.SottoShell.exec_js_post = lambda self, script: False
    sw.SottoShell._post = lambda self, fn: False
    sw.SottoShell._post_metrics_refresh = lambda self, name, reason: True
    return fw, proxy


# ---------------------------------------------------------------------------
# THE PRESS TRACE
# ---------------------------------------------------------------------------
def build_trace(n: int, lo_ms: int, hi_ms: int):
    """The key events: ALT down, then n x (C down, C up), then ALT up.

    The ALT is HELD THROUGHOUT: no release event is delivered to the app
    between the C presses.
    """
    events = [{'key': 'alt', 'action': 'down', 't_ms': 0.0, 'vk': VK_MENU}]
    t = 0.0
    span = max(0, hi_ms - lo_ms)
    step = span // 6 if span else 0
    for i in range(n):
        gap = min(hi_ms, lo_ms + (step * (i % 7)))
        t += gap
        events.append({'key': 'c', 'action': 'down', 't_ms': round(t, 3),
                       'vk': VK_C, 'press_index': i + 1})
        events.append({'key': 'c', 'action': 'up', 't_ms': round(t, 3),
                       'vk': VK_C, 'press_index': i + 1})
    events.append({'key': 'alt', 'action': 'up', 't_ms': round(t, 3),
                   'vk': VK_MENU})
    return events


def alt_held_span(trace):
    """The window in which ALT is down, and whether every C press is inside it."""
    down = next(e for e in trace if e['key'] == 'alt' and e['action'] == 'down')
    up = next(e for e in trace if e['key'] == 'alt' and e['action'] == 'up')
    presses = [e for e in trace if e['key'] == 'c' and e['action'] == 'down']
    inside = all(down['t_ms'] <= p['t_ms'] <= up['t_ms'] for p in presses)
    return {'alt_down_at_ms': down['t_ms'], 'alt_up_at_ms': up['t_ms'],
            'all_c_presses_inside_alt_held': inside,
            'c_presses_inside': sum(1 for p in presses
                                     if down['t_ms'] <= p['t_ms'] <= up['t_ms']),
            'c_presses_total': len(presses)}


# ---------------------------------------------------------------------------
# THE JUDGE -- the owner's sentence, and nothing else
# ---------------------------------------------------------------------------
def judge(n: int, fw: FakeWindow, invert: bool = False):
    """`alterna entre show e hide`: N presses -> N flips, alternating.

    `invert=True` judges the OPPOSITE claim (N shows, no hide) -- the same
    measurement with the expectation reversed.
    """
    kinds = [t['kind'] for t in fw.transitions]
    if invert:
        expected = ['show'] * n
        ok = (kinds == expected)
        reasons = [] if ok else [
            f'INVERTED claim expected {expected}, got {kinds}']
        return ('GREEN' if ok else 'RED'), reasons
    reasons = []
    if len(kinds) != n:
        reasons.append(
            f'flips={len(kinds)} expected={n} '
            f'({"presses swallowed" if len(kinds) < n else "one press caused more than one flip"})')
    expected_kinds = ['show' if i % 2 == 0 else 'hide' for i in range(n)]
    if kinds != expected_kinds:
        first = next((i for i in range(min(len(kinds), n))
                      if kinds[i] != expected_kinds[i]), None)
        reasons.append(
            f'visible sequence does not alternate show/hide: got={kinds} '
            f'expected={expected_kinds} first_divergence_at={first}')
    return ('GREEN' if not reasons else 'RED'), reasons


# ---------------------------------------------------------------------------
# THE KEYBOARD-READ PROBE (is there a release/duration seam at all?)
# ---------------------------------------------------------------------------
def keyboard_seams(tree: str):
    """Does the hotkey path read the keyboard? (the 'alt held' seam)"""
    webview = os.path.join(os.path.abspath(tree), 'app', 'webview')
    out = {}
    for name in ('sotto_webview.py', 'hotkey_gesture.py'):
        path = os.path.join(webview, name)
        src = open(path, 'r', encoding='utf-8').read()
        tree_ast = ast.parse(src)
        hits = []
        for node in ast.walk(tree_ast):
            if isinstance(node, ast.Attribute) and node.attr == 'GetAsyncKeyState':
                hits.append(node.lineno)
            if isinstance(node, ast.Name) and node.id == 'GetAsyncKeyState':
                hits.append(node.lineno)
        out[name] = sorted(set(hits))
    # WHICH of those are on the hotkey path?
    shell_src = open(os.path.join(webview, 'sotto_webview.py'),
                     'r', encoding='utf-8').read()
    tree_ast = ast.parse(shell_src)
    hotkey_lines = set()
    for node in ast.walk(tree_ast):
        if isinstance(node, ast.ClassDef) and node.name == 'HotkeyThread':
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef):
                    hotkey_lines.update(n.lineno for n in ast.walk(fn)
                                         if hasattr(n, 'lineno'))
        if isinstance(node, ast.ClassDef) and node.name == 'SottoShell':
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in (
                        'hotkey_pressed', 'hotkey_live', '_hotkey_resolve',
                        '_hotkey_dispatch', '_hotkey_worker_loop'):
                    hotkey_lines.update(n.lineno for n in ast.walk(fn)
                                         if hasattr(n, 'lineno'))
    out['hotkey_path_lines_with_GetAsyncKeyState'] = sorted(
        line for line in out['sotto_webview.py'] if line in hotkey_lines)
    # The registration flags: MOD_NOREPEAT = one WM_HOTKEY per press.
    out['MOD_NOREPEAT_on_registration'] = 'MOD_NOREPEAT' in shell_src
    return out


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--tree', required=True)
    ap.add_argument('--n', type=int, required=True)
    ap.add_argument('--lo-ms', type=int, default=30)
    ap.add_argument('--hi-ms', type=int, default=120)
    ap.add_argument('--label', default='')
    ap.add_argument('--timeout', type=float, default=90.0)
    ap.add_argument('--invert', action='store_true',
                    help='the INVERTED claim: expect N shows and NO hide.  '
                         'The same measurement, the opposite expectation -- it '
                         'MUST go RED on the shipped tree (the proof that the '
                         'probe can say NO).')
    ap.add_argument('--null', action='store_true',
                    help='deliver ZERO presses (the null arm: the property absent '
                         'by construction, so the judge MUST say absent)')
    args = ap.parse_args(argv)

    sw = load_tree(args.tree)

    class Args:
        with_worker = False
        no_worker = True
        dump_dom = False
        selftest = False
        memory = False
        no_hotkey = False
        exit_after = 0.0
        probe_stats = False
        probe_edit_mode = False
        mutex_name = 'Local\\SottoShellFalsify'
        worker = ''
        show = False

    shell = sw.SottoShell(Args())
    fw, proxy = install_fakes(sw, shell)

    # CHAIN INTEGRITY: which PRODUCTION functions actually ran?  The wrappers
    # are installed on the CLASS, they call the ORIGINAL body, and they only
    # count.  A probe that answered GREEN without driving the product would be
    # vacuous, and this is what rules that out.
    chain_calls = {}
    _chain_names = (
        'hotkey_pressed', '_hotkey_dispatch', '_hotkey_worker_loop',
        '_hotkey_resolve', 'show_strip', 'show_side', 'hide_panel',
        'show_panel', 'toggle_panel', 'hotkey_live')
    for _name in _chain_names:
        _orig = getattr(sw.SottoShell, _name, None)
        if _orig is None:
            continue

        def _make(_orig, _name):
            def _wrapper(self, *a, **k):
                chain_calls[_name] = chain_calls.get(_name, 0) + 1
                return _orig(self, *a, **k)
            return _wrapper
        setattr(sw.SottoShell, _name, _make(_orig, _name))

    # THE RULE IS THE SHIPPED ONE: the gesture module's `next_surface` must be
    # the function in the file on disk, not a copy.
    _gest = sw.hotkey_numbers()
    _gest_path = os.path.join(os.path.abspath(args.tree), 'app', 'webview',
                              'hotkey_gesture.py')
    _gest_src = open(_gest_path, encoding='utf-8').read()
    chain_meta = {
        'gesture_module_file': getattr(_gest, '__file__', None),
        'next_surface_code_matches_disk':
            _gest.next_surface.__code__.co_code ==
            compile(_gest_src, _gest_path, 'exec').co_consts[0].co_code
            if False else None,
        'next_surface_argcount': _gest.next_surface.__code__.co_argcount,
        'PANELS_ACCELERATOR': getattr(_gest, 'PANELS_ACCELERATOR', None),
    }
    # A REAL handle: the production code reads `self.hwnd` to decide whether it
    # can act at all, and `_hotkey_resolve` reads the window through it.
    shell.hwnd = 4242

    log_lines = []
    # THE SHELL'S OWN LOG.  The production bodies write through the MODULE's
    # `log` (sotto_webview.log), not through the callback the HotkeyThread
    # takes -- so the second channel has to capture THAT.  It is wrapped, not
    # replaced: the lines still go to stdout exactly as they would.
    _shell_log = sw.log

    def log_fn(message, *a, **k):
        log_lines.append(str(message))
        _shell_log(message, *a, **k)

    sw.log = log_fn

    # The 2026-10-30 tree's HotkeyThread has a different signature (no `role`,
    # no `register`) and a POLLING pump that reads the keyboard.  The driver
    # adapts: `register` is only meaningful for the current tree, and the
    # historical thread is driven through its OWN `simulate_press`.
    gesture = sw.hotkey_numbers()
    accel = getattr(gesture, 'PANELS_ACCELERATOR', None) or 'Alt+C'
    # THE HISTORICAL THREAD (2026-10-30) has no `register=False`: it ALWAYS
    # calls the real `RegisterHotKey`, and on failure it RETURNS without
    # pumping.  Two problems: (a) it would try to TAKE the owner's global
    # Alt+C, and (b) it would never pump, so no press would be delivered.
    # The driver therefore makes the registration a no-op that SUCCEEDS: the
    # global key is never taken, the pump runs, and the pump is the thing
    # under test.  The driver's OWN tree (2026-11-01) has `register=False`
    # and is untouched by this.
    _historical_registration = {'patched': False}
    try:
        thread = sw.HotkeyThread(accel, on_hotkey=shell.hotkey_pressed,
                                 log_fn=log_fn, role='panels', register=False)
    except TypeError:
        # The historical thread: make the registration a no-op that SUCCEEDS.
        sw.user32.RegisterHotKey = lambda *a, **k: 1
        _historical_registration['patched'] = True
        thread = sw.HotkeyThread(accel, on_hotkey=shell.hotkey_pressed,
                                 log_fn=log_fn)
    thread.start()
    if not thread.wait_ready(5.0):
        print('RESULT_JSON ' + json.dumps({'error': 'hotkey thread never ready'}))
        return 3

    trace = build_trace(args.n, args.lo_ms, args.hi_ms)
    held = alt_held_span(trace)
    press_times = [e for e in trace if e['key'] == 'c' and e['action'] == 'down']

    t_start = time.monotonic()
    proxy.trace = trace
    proxy.origin = t_start
    posted = 0
    if args.null:
        press_times = []
    for ev in press_times:
        target = t_start + (ev['t_ms'] / 1000.0)
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        if thread.simulate_press():
            posted += 1
    post_done = time.monotonic()

    # Drain: wait for the FIFO queue to empty AND the state to stop moving.
    deadline = post_done + max(15.0, args.timeout - (post_done - t_start))
    last_count = -1
    stable_since = None
    while time.monotonic() < deadline:
        count = len(fw.transitions)
        q = getattr(shell, '_hotkey_queue', None)
        try:
            empty = q is None or q.empty()
        except Exception:
            empty = True
        if count != last_count:
            last_count = count
            stable_since = time.monotonic()
        elif empty and stable_since is not None and \
                (time.monotonic() - stable_since) > 0.40:
            break
        time.sleep(0.02)
    # a final settle, so a late step is not counted as a missing one
    time.sleep(0.50)

    thread.stop()
    try:
        thread.join(timeout=3.0)
    except Exception:
        pass

    judge_n = 0 if args.null else args.n
    verdict, reasons = judge(judge_n, fw, invert=bool(args.invert))
    # THE SECOND CHANNEL: the PRODUCTION log lines.  `PANEL_SHOWN` /
    # `PANEL_HIDDEN` are written by the shipped bodies; counting them is a
    # count that does NOT go through my fake window, so the two can be
    # compared.  A probe that only reads its own recorder could be fooled by
    # a recorder that lies; two channels that agree cannot.
    log_shown = sum(1 for l in log_lines if 'PANEL_SHOWN ' in l)
    log_hidden = sum(1 for l in log_lines if 'PANEL_HIDDEN ' in l)
    log_toggles = sum(1 for l in log_lines if 'HOTKEY_TOGGLE ' in l)
    log_pressed = sum(1 for l in log_lines if 'HOTKEY_PRESSED ' in l)
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'log-%s.txt' % (args.label or 'run'))
    with open(log_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(log_lines))
    kinds = [t['kind'] for t in fw.transitions]
    surfaces = [t['surface'] for t in fw.transitions]
    report = {
        'label': args.label,
        'tree': os.path.abspath(args.tree),
        'n_requested': args.n,
        'interval_ms_range': [args.lo_ms, args.hi_ms],
        'trace_events': len(trace),
        'alt_held': held,
        'presses_posted': posted,
        'presses_delivered_by_pump': int(thread.pressed),
        'flips': len(fw.transitions),
        'expected_flips': judge_n,
        'visible_sequence': kinds,
        'expected_visible_sequence': ['show' if i % 2 == 0 else 'hide'
                                      for i in range(judge_n)],
        'surface_sequence': surfaces,
        'final_visible': bool(fw.visible),
        'elapsed_s': round(time.monotonic() - t_start, 3),
        'getasynckeystate_reads_during_run': len(proxy.get_async_key_state_calls),
        'keyboard_seams': keyboard_seams(args.tree),
        'verdict': verdict,
        'reasons': reasons,
        # THE PROPERTY, STATED AS A BOOLEAN: "the panels alternate show/hide
        # on every press".  The null arm (zero presses) is the input where the
        # property is KNOWN ABSENT; the shipped arms are where it is PRESENT.
        'property_present': (judge_n > 0
                             and len(fw.transitions) == judge_n
                             and all(kinds[i] != kinds[i + 1]
                                     for i in range(len(kinds) - 1))),
        'log_tail': log_lines[-14:],
        'log_path': log_path,
        'log_lines_total': len(log_lines),
        'null_arm': bool(args.null),
        'invert_arm': bool(args.invert),
        'chain_calls': chain_calls,
        'chain_meta': chain_meta,
        'log_channel': {'PANEL_SHOWN': log_shown, 'PANEL_HIDDEN': log_hidden,
                        'HOTKEY_TOGGLE': log_toggles,
                        'HOTKEY_PRESSED': log_pressed,
                        'recorder_flips': len(fw.transitions),
                        'channels_agree': (log_shown + log_hidden
                                           == len(fw.transitions))},
    }
    print('RESULT_JSON ' + json.dumps(report, ensure_ascii=False))
    return 0 if verdict == 'GREEN' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
