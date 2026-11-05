#!/usr/bin/env pythonw.exe
# NO-BUG: ORACLE: a navigation that never comes back must not take the app with it.
# -*- coding: utf-8 -*-
"""ORACLE: a navigation that never comes back must not take the app with it.

MEASURED LESION (2026-11-05, two launches in a row): the form was created
(`PANEL_SHOW_GATE installed`, `UI_WATCHDOG_STARTED hwnd=..`) and from that
moment NO document ever loaded -- `STARTUP_NOT_READY s=15/30/60` and not one
line naming the browser. The shell sat there with no `PANEL_STATE_WRITER`
(every instrument reads that file and said `STALE`), no captions on screen and
nothing to restart it.

TWO DEFECTS behind it, both in `_arm_panel_stall_watch`:

  D1 -- the guard was ARMED FROM THE LOAD HANDLER (`STAGING_LOADED`), so the
  one state it exists for (no document ever loads) was the one state where it
  was never armed. Cure: it arms when the FORM exists, which is the last
  instant the shell knows there is something to watch.

  D2 -- the retry called `load_url` INLINE, and that call does not return when
  the browser is not alive. A guard whose own recovery step can hang is a guard
  that cannot fire: the 25 s `_complete_startup` (the whole point: captions do
  not depend on the panel page) would never run. Cure: the retry runs on its
  own thread so the completion is unconditional.

WHAT THIS FILE MEASURES. Not the wiring (that is `battery-wiring`'s job) and
not a copy: it binds the REAL `SottoShell._arm_panel_stall_watch` to a stub
host, makes `time.sleep` instant, and drives the two properties as ORDER, not
as timing:

  A1  with `load_url` blocking forever, `_complete_startup` still runs;
  A2  the stall line NAMES the state (`core=no`) instead of staying silent.

Negative control (the mutation): the same arm against a COPY of the shell with
the retry inlined (D2 restored) must show the completion never happening --
that copy is the defect, reproduced, and it must be RECUSED.

    python _main\\panel-nav-stall-oracle.py             # rc=0 green
    python _main\\panel-nav-stall-oracle.py --neg-arm   # rc=1 when it catches the mutant

HEADLESS: no window, no WebView2, no audio, nothing on the owner's screen.
"""
import contextlib
import importlib.util
import io
import os
import re
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')

failures = []


def check(name, ok, detail=''):
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           (' — ' + detail) if detail else ''))
    if not ok:
        failures.append(name)


# ---------------------------------------------------------------------------
# the shell under test, loaded by path (it logs a lot; stdout is swallowed)
# ---------------------------------------------------------------------------
def load_shell(path, name):
    shell_dir = os.path.join(REPO, 'app', 'webview')
    if shell_dir not in sys.path:
        sys.path.insert(0, shell_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError('cannot load a module from %r' % (path,))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spec.loader.exec_module(module)
    return module


class FastTime:
    """`time` with an instant `sleep`: the watch sleeps 12 s and 13 s."""

    def __init__(self):
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def __getattr__(self, name):
        return getattr(time, name)


class ThreadShim:
    """Records what the code asks to run in a thread; nothing is started."""

    def __init__(self):
        self.asked = []

    def __call__(self, target=None, name=None, daemon=None, args=(), kwargs=None):
        rec = types.SimpleNamespace(target=target, name=name, args=args,
                                   kwargs=kwargs or {})
        self.asked.append(rec)

        class _Handle:
            def start(self_inner):
                pass

        return _Handle()


def make_host(module, log_lines, complete_calls, load_url):
    host = types.SimpleNamespace()
    host.args = types.SimpleNamespace(ready_file=None)
    host.core = None
    host._panel_stall_armed = False
    host.window = types.SimpleNamespace(
        get_current_url=lambda: (_ for _ in ()).throw(RuntimeError('no core')),
        load_url=load_url,
    )
    host._complete_startup = lambda: complete_calls.append(time.monotonic())
    host._log = log_lines.append
    return host


def drive(module, host, clock):
    """Bind the REAL method and run the watch arm it spawns, inline."""
    module.log = host._log
    module.time = clock
    shim = ThreadShim()
    module.threading = types.SimpleNamespace(Thread=shim)
    module.startup_is_ready = lambda path: False
    module.SottoShell._arm_panel_stall_watch(host)
    watch = [r for r in shim.asked if r.name == 'sotto-panel-stall']
    if len(watch) != 1:
        raise AssertionError('expected one watch thread, got %d' % len(watch))
    watch[0].target()
    # O RETRY SO' EXISTE DEPOIS DE O VIGIA CORRER: filtrar antes de o correr
    # mede a lista vazia e o instrumento mente (medido nesta mesma noite).
    return [r for r in shim.asked if r.name == 'sotto-panel-nav-retry']


# ---------------------------------------------------------------------------
# arm A: the shipped shell, with a `load_url` that never returns
# ---------------------------------------------------------------------------
def arm_shipped():
    print('ARM 1 — shipped shell, a navigation that never returns')
    module = load_shell(SHELL, 'sotto_nav_stall_shipped')
    log_lines, complete_calls, url_calls = [], [], []
    hang = threading.Event()

    def blocking_load_url(url):
        url_calls.append(url)
        hang.wait(10.0)

    host = make_host(module, log_lines, complete_calls, blocking_load_url)
    clock = FastTime()
    retry = drive(module, host, clock)

    check('A1 the watch sleeps the two documented marks (12 s, 13 s)',
          clock.sleeps == [12.0, 13.0], 'sleeps=%r' % (clock.sleeps,))
    check('A2 load_url is NOT called on the watch thread (it would hang it)',
          url_calls == [], 'calls=%r' % (url_calls,))
    check('A3 _complete_startup runs even though the retry never returns',
          len(complete_calls) == 1, 'calls=%d' % len(complete_calls))
    check('A4 the retry is on its own thread', len(retry) == 1,
          'threads=%d' % len(retry))
    stall = [l for l in log_lines if l.startswith('PANEL_NAV_STALL')]
    final = [l for l in stall if 'PANEL_NAV_STALL_FINAL' in l]
    check('A5 the stall line names the state (core=no)',
          bool(final) and 'core=no' in final[0], 'lines=%r' % (final[:1],))
    return True


# ---------------------------------------------------------------------------
# arm B (negative control): the defect, restored in a COPY
# ---------------------------------------------------------------------------
def arm_mutant():
    print('ARM 2 (negative control) — the retry INLINED, as it shipped before the cure')
    src = open(SHELL, encoding='utf-8').read()
    marker = '            _push_nav()'
    if marker not in src:
        raise AssertionError('anchor for the mutation is gone; re-derive it')
    mutated = src.replace(
        marker,
        '            self.window.load_url(file_url(PANEL_HTML))', 1)
    tmp = os.path.join(tempfile.gettempdir(), 'sotto_nav_stall_mutant.py')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(mutated)
    module = load_shell(tmp, 'sotto_nav_stall_mutant')
    log_lines, complete_calls, url_calls = [], [], []
    hang = threading.Event()

    def blocking_load_url(url):
        url_calls.append(url)
        hang.wait(10.0)

    host = make_host(module, log_lines, complete_calls, blocking_load_url)
    clock = FastTime()
    # The mutant hangs on the WATCH thread, so the drive has to be bounded.
    box = {}

    def run():
        try:
            drive(module, host, clock)
        except BaseException as exc:          # noqa: BLE001
            box['error'] = repr(exc)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(2.0)
    # A FOTOGRAFIA E' TIRADA ANTES DE LIBERTAR O `load_url`: depois disso o
    # mutante TERMINA a sua espera e completa o arranque, e um detalhe lido
    # tarde descreveria o oposto do veredicto.
    stuck_after_2s = t.is_alive()
    done_by_then = len(complete_calls)
    caught = stuck_after_2s and not done_by_then
    hang.set()
    t.join(2.0)
    check('B1 the mutant reproduces the defect (completion held hostage by '
          'load_url)', caught,
          'watch_stuck_at_2s=%s complete_calls_at_2s=%d url_calls=%d'
          % (stuck_after_2s, done_by_then, len(url_calls)))
    return caught


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:                         # noqa: BLE001
        pass
    argv = sys.argv[1:] if argv is None else argv
    neg = '--neg-arm' in argv
    if neg:
        caught = arm_mutant()
        print()
        if caught:
            print('NEG-ARM PASS — the mutant that inlines the retry is caught')
            return 1
        print('NEG-ARM FAIL — the mutant survived; this oracle proves nothing')
        return 2
    arm_shipped()
    print()
    if failures:
        print('VERDICT: FAIL (%d)' % len(failures))
        return 2
    print('VERDICT: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
