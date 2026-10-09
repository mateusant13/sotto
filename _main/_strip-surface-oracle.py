#!/usr/bin/env python3
"""Oracle for the STRIP SURFACE contract — the member this shell owed the panel.

Owner's lane brief, 2026-10-08: `app/panel/panel.js:1239-1243` calls
`bridge.setPanelSurface(surface, reason)` and NOTHING implemented it in the shell
(`grep surface|strip` over `sotto_webview.py` returned 37 matches, none of them an
implementation), so the strip's own "Open panel" button fell through to
`panel.js:1245-1247` and the window stayed strip-sized.

TWO COLOURS IN ONE COMMAND, the house rule: the same checks run against the REAL
shell and against a COPY of it with the member textually removed
(`_strip-mutant-sotto_webview.py`, deleted after the run). The oracle is GREEN
only when the real file passes AND the mutant FAILS on the member it is missing.

Writes one JSON report next to itself; run it with `pythonw.exe` so no console
ever appears on the owner's screen:

    pythonw.exe _main/_strip-surface-oracle.py
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WEBVIEW = os.path.join(os.path.dirname(HERE), 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
MUTANT = os.path.join(WEBVIEW, '_strip-mutant_sotto_webview.py')
REPORT = os.path.join(HERE, '_strip-surface-oracle.json')

if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# the checks — ONE list, run against whichever module is handed in
# ---------------------------------------------------------------------------
def check(module):
    """-> (failures, facts). Every failure is a sentence a reader can act on."""
    failures = []
    facts = {}

    def want(label, got, expected):
        facts[label] = got
        if got != expected:
            failures.append(f'{label}: got {got!r}, expected {expected!r}')

    # -- 1. THE GEOMETRY, in numbers (the box the strip was measured on) -----
    work = {'x': 0, 'y': 0, 'width': 1920, 'height': 1032}
    g = module.strip_geometry(work)
    want('strip.width@1920', g['width'], 1040)
    want('strip.height-fallback', g['height'], module.STRIP_HEIGHT_FALLBACK)
    want('strip.x@1920', g['x'], 440)
    want('strip.y@1920', g['y'], 836)
    want('strip.docked', g['docked'], 'bottom-centre')
    want('strip.work', (g['workX'], g['workY'], g['workWidth'], g['workHeight']),
         (0, 0, 1920, 1032))
    # The number the STYLESHEET carries (`panel.css:52` `--strip-height: 150px`),
    # fed in explicitly: the same formula must produce the band the CSS draws.
    g_css = module.strip_geometry(work, 150)
    want('strip.height@css150', g_css['height'], 150)
    want('strip.y@css150', g_css['y'], 834)

    g2 = module.strip_geometry({'x': 0, 'y': 0, 'width': 1280, 'height': 720})
    want('strip.width@1280', g2['width'], 794)
    want('strip.x@1280', g2['x'], 243)
    want('strip.y@1280', g2['y'], 524)

    # Containment, including a work area smaller than the band.
    for label, wk in (('tiny', {'x': 0, 'y': 0, 'width': 300, 'height': 100}),
                      ('short', {'x': -1920, 'y': 100, 'width': 1920,
                                 'height': 90})):
        gx = module.strip_geometry(wk)
        inside = (gx['x'] >= wk['x'] and gx['y'] >= wk['y']
                  and gx['x'] + gx['width'] <= wk['x'] + wk['width']
                  and gx['y'] + gx['height'] <= wk['y'] + wk['height'])
        facts[f'contained.{label}'] = gx
        if not inside:
            failures.append(f'contained.{label}: {gx} escapes work {wk}')

    # The height is RUNTIME state, not a constant: the function takes it.
    g3 = module.strip_geometry(work, 220)
    want('strip.height.runtime', g3['height'], 220)
    want('strip.y.runtime', g3['y'], 1032 - 220 - 48)

    # The docked panel is UNCHANGED (this lane must not move it).
    d = module.dock_right(work)
    want('panel.width', d['width'], 380)
    want('panel.height', d['height'], 900)
    want('panel.pos', (d['x'], d['y']), (1528, 66))

    # -- 2. THE CLAMP (a saved rect into the CURRENT work area) --------------
    clamped, moved = module.clamp_geometry(
        {'x': -500, 'y': 9000, 'width': 1040, 'height': 148}, work)
    want('clamp.moved', moved, True)
    want('clamp.x', clamped['x'], 0)
    want('clamp.y', clamped['y'], 884)
    fitted, moved2 = module.clamp_geometry(
        {'x': 440, 'y': 836, 'width': 1040, 'height': 148}, work)
    want('clamp.noop.moved', moved2, False)
    want('clamp.noop.x', fitted['x'], 440)

    # -- 3. THE SURFACE NAME, refused rather than guessed --------------------
    for sent, expected in (('strip', 'strip'), ('panel', 'panel'),
                           ('  STRIP ', 'strip'), ('surface--strip', 'strip'),
                           ('surface-panel', 'panel'), ('bogus', None),
                           (None, None), ('', None)):
        want(f'surface_name({sent!r})', module.normalise_surface_name(sent),
             expected)

    # -- 4. THE BRIDGE MEMBER the panel calls --------------------------------
    js = module.BOOTSTRAP_JS
    for needle in ('setPanelSurface:', 'getStats:', 'onStats:',
                   '__sotto_stats', "'panel-surface'", "'stats'",
                   'stats: []'):
        facts[f'js.{needle}'] = needle in js
        if needle not in js:
            failures.append(f'the injected bridge has no {needle!r}')
    if not re.search(r'setPanelSurface:\s*function\s*\(surface,\s*reason\)', js):
        failures.append('setPanelSurface does not take (surface, reason) — '
                        'panel.js:1242 calls it with exactly those two')

    # -- 5. THE HOST HANDLERS, DRIVEN (not grepped) --------------------------
    # A text check would pass on a dict entry that no code can reach. This calls
    # the REAL `dispatch` with the REAL wire string the page's `post()` builds,
    # against a stand-in shell that records what it was asked to do — the same
    # idiom `_main/panel-exit3-oracle.py` uses for the page's own handlers.
    class FakeShell:
        def __init__(self):
            self.calls = []

        def set_panel_surface(self, surface, reason):
            self.calls.append(('set_panel_surface', surface, reason))
            return True

        def stats(self):
            self.calls.append(('stats',))
            return {'peak': 0.5, 'blocks': 12.0}

        def reply_stats(self, stats_id, payload):
            self.calls.append(('reply_stats', stats_id, payload))

    fake = FakeShell()
    host = module.SottoHost(fake)
    host.dispatch(json.dumps({'kind': 'panel-surface',
                              'payload': {'surface': 'panel',
                                          'reason': 'strip-open'}}))
    host.dispatch(json.dumps({'kind': 'stats', 'payload': {'id': 's1'}}))
    facts['dispatch.calls'] = fake.calls
    facts['dispatch.source_tail'] = inspect.getsource(
        module.SottoHost.dispatch)[-420:]
    if ('set_panel_surface', 'panel', 'strip-open') not in fake.calls:
        failures.append("dispatch does not route 'panel-surface' to "
                        'set_panel_surface(surface, reason) — the member '
                        'panel.js:1242 calls would still be a no-op')
    if ('reply_stats', 's1', {'peak': 0.5, 'blocks': 12.0}) not in fake.calls:
        failures.append("dispatch does not route 'stats' to "
                        'reply_stats(id, payload)')
    for name in ('_panel_surface', '_stats'):
        facts[f'host.{name}'] = hasattr(module.SottoHost, name)
        if not hasattr(module.SottoHost, name):
            failures.append(f'SottoHost.{name} is missing')

    # -- 6. THE SHELL METHODS -------------------------------------------------
    for name in ('set_panel_surface', 'stats', 'reply_stats', 'on_worker_stats',
                 'set_edit_mode', 'edit_drag_to', 'set_strip_height',
                 'geometry_for', 'geometry_snapshot', 'restore_saved_geometry',
                 'work_area', '_apply_window_geometry'):
        facts[f'shell.{name}'] = hasattr(module.SottoShell, name)
        if not hasattr(module.SottoShell, name):
            failures.append(f'SottoShell.{name} is missing')

    sig = inspect.signature(module.SottoShell.show_panel)
    facts['show_panel.params'] = list(sig.parameters)
    if 'surface' not in sig.parameters:
        failures.append('show_panel takes no `surface` override, so --show and '
                        'the tray cannot ask for the full panel')
    if 'on_stats' not in inspect.signature(module.WorkerBridge.__init__).parameters:
        failures.append('WorkerBridge takes no `on_stats` callback')

    # -- 7. THE TRAY ITEM that is the edit mode's only door -------------------
    menu_src = inspect.getsource(module.TrayIcon._build_menu)
    facts['tray.menu_src'] = menu_src
    for needle in ('Edit caption position', 'ID_TRAY_EDIT'):
        if needle not in menu_src:
            failures.append(f'the tray menu has no {needle!r}')
    facts['tray.edit_id'] = getattr(module, 'ID_TRAY_EDIT', None)

    # -- 8. THE PERSISTED KEY, in the file that already exists ---------------
    writer_sig = inspect.signature(module.PanelVisibilityWriter.__init__)
    facts['writer.params'] = list(writer_sig.parameters)
    if 'extra' not in writer_sig.parameters:
        failures.append('PanelVisibilityWriter cannot carry the `geometry` key, '
                        'so an edit could not be persisted in the one file')
    write_src = inspect.getsource(module.PanelVisibilityWriter.write)
    if "'geometry'" not in write_src:
        failures.append("PanelVisibilityWriter.write never writes 'geometry'")
    facts['writer.path'] = module.PANEL_VISIBILITY_PATH
    if os.path.basename(module.PANEL_VISIBILITY_PATH) != 'panel-visibility.json':
        failures.append('the geometry is not persisted in '
                        'panel-visibility.json — a SECOND file is forbidden')

    # -- 9. THE STATS PAYLOAD, against the panel's own whitelist -------------
    shell = module.SottoShell.__new__(module.SottoShell)

    class FakeBridge:
        last_worker_stats = {'tag': 'tick', 'fields': {'peak': '0.443448',
                                                       'blocks': '812',
                                                       'nonzero_blocks': '800',
                                                       'queue_drops': '0'},
                             'line': 'WORKER_STATS tag=tick ...'}

    shell.bridge = FakeBridge()
    stats = shell.stats()
    want('stats.payload', stats, {'peak': 0.443448, 'blocks': 812.0})
    if 'nonzero_blocks' in stats or 'queue_drops' in stats:
        failures.append('stats() leaks fields the panel does not read')

    class EmptyBridge:
        last_worker_stats = None

    shell.bridge = EmptyBridge()
    want('stats.empty', shell.stats(), {})

    class PartialBridge:
        last_worker_stats = {'tag': 'tick', 'fields': {'blocks': '3'}, 'line': ''}

    shell.bridge = PartialBridge()
    want('stats.partial', shell.stats(), {'blocks': 3.0})

    # -- 10. THE RESTORE path reads ONE file and CLAMPS ----------------------
    shell2 = module.SottoShell.__new__(module.SottoShell)
    shell2.display = {'workArea': work, 'scaleFactor': 1.0}
    shell2.strip_height = module.STRIP_HEIGHT_FALLBACK
    shell2.saved_geometry = {'surface': 'strip', 'x': -100, 'y': 99999,
                             'width': 1040, 'height': 148, 'docked': 'edited'}
    got = shell2.geometry_for('strip')
    want('geometry_for.clamped', (got['x'], got['y'], got['width'],
                                  got['height']), (0, 884, 1040, 148))
    shell2.saved_geometry = None
    got2 = shell2.geometry_for('strip')
    want('geometry_for.default', (got2['x'], got2['y'], got2['width'],
                                 got2['height']), (440, 836, 1040, 148))

    # -- 11. THE SURFACE LABEL in the persisted rect -------------------------
    shell3 = module.SottoShell.__new__(module.SottoShell)
    shell3.geometry = dict(g)
    shell3.surface = 'strip'
    shell3.surface_applied = 'panel'
    want('geometry_snapshot.surface',
         shell3.geometry_snapshot()['surface'], 'panel')

    # -- 12. `--show` STILL MEANS THE FULL PANEL -----------------------------
    # The strip is what Alt+C opens. `--show` is the developer's "panel up now"
    # and is the flag every existing measurement arm passes, so it must keep
    # asking for the FULL panel explicitly — not inherit the strip default.
    with open(module.__file__, encoding='utf-8') as fh:
        src = fh.read()
    facts['show_call'] = "self.show_panel('startup', surface='panel')" in src
    if not facts['show_call']:
        failures.append('the --show path no longer asks for the full panel '
                        "(expected self.show_panel('startup', surface='panel'))")

    # -- 13. THE FIX THAT COST A REAL DEFECT --------------------------------
    # `SetWindowPos` without argtypes marshals `HWND_TOPMOST` (-1) as a 32-bit int
    # and the call FAILS with 1400 while still applying the size — measured, see
    # `_main/_strip-surface-probe.py`. The declared signature is the fix, so it is
    # asserted here rather than trusted.
    argtypes = getattr(module.user32.SetWindowPos, 'argtypes', None)
    facts['SetWindowPos.argtypes'] = [str(a) for a in (argtypes or [])]
    if not argtypes or len(argtypes) != 7:
        failures.append('user32.SetWindowPos has no 7-argument signature — '
                        'HWND_TOPMOST will be marshalled as a 32-bit int and the '
                        'move will fail with 1400')

    # -- 14. ALT+C IS PINNED TO THE STRIP ------------------------------------
    if "surface='strip' if reason == 'hotkey' else None" not in src:
        failures.append('the hotkey no longer pins the STRIP: after opening the '
                        'full panel from the strip, Alt+C would reopen the panel')

    # -- 15. A MEASUREMENT MODE MUST NOT BE ABLE TO HANG ---------------------
    # An exception escaping a `threading.Timer` callback dies on a stderr pythonw
    # does not have, leaving a hidden shell alive forever (measured: one 70 s
    # hang). The exit is therefore in a `finally`.
    for probe, marker in (('run_edit_mode_probe',
                           "self.request_exit(0, reason='probe-edit-mode')"),
                          ('run_stats_probe',
                           "self.request_exit(0, reason='probe-stats')")):
        body = inspect.getsource(getattr(module.SottoShell, probe))
        facts[f'{probe}.exits'] = marker in body
        if marker not in body:
            failures.append(f'{probe} does not guarantee its own exit')

    # -- 16. THE MEASUREMENT FLAGS STAY INVISIBLE IN --help ------------------
    for flag in ('--probe-edit-mode', '--probe-stats', '--probe-stats-wait'):
        if f"'{flag}', action='store_true',\n                        help=argparse.SUPPRESS" not in src \
                and f"'{flag}', type=float, default=8.0,\n                        help=argparse.SUPPRESS" not in src:
            failures.append(f'{flag} is not SUPPRESSed: run.cmd --help would change')

    # -- 17. THE HEIGHT COMES FROM THE STYLESHEET, NOT FROM THIS FILE ---------
    # The panel lane measured the strip and put the ONE number in `:root`
    # (`panel.css:52` `--strip-height: 150px`). A second copy in the shell would
    # let a theme edit leave the shell lying about the window it sized, so the
    # read is DRIVEN here against a stand-in page: the shell must ADOPT what the
    # stylesheet says, and must say so when the page cannot answer.
    want('strip.css_var', module.STRIP_HEIGHT_CSS_VAR, '--strip-height')

    class Page:
        def __init__(self, value):
            self.value = value
            self.scripts = []

        def exec_js(self, script, timeout=10.0):
            self.scripts.append(script)
            return self.value

    def probe_shell(page_value):
        s = module.SottoShell.__new__(module.SottoShell)
        s.strip_height_css = None
        s.strip_height_extra = 0
        s.strip_height = module.STRIP_HEIGHT_FALLBACK
        # 'panel' so `set_strip_height` does not try to re-apply the strip (that
        # path needs a window this stand-in deliberately does not have).
        s.surface = 'panel'
        s.exec_js = Page(page_value).exec_js
        return s

    fed = probe_shell('150px')
    moved = fed.refresh_strip_height('oracle')
    want('strip.css.adopted', (moved, fed.strip_height, fed.strip_height_css),
         (True, 150, 150))
    # Idempotent: reading the same number twice must not log a second move.
    want('strip.css.idempotent', fed.refresh_strip_height('oracle'), False)
    # A whitespace-padded, uppercase value is the same value.
    padded = probe_shell(' 150PX ')
    want('strip.css.padded', (padded.refresh_strip_height('oracle'),
                              padded.strip_height), (True, 150))
    # And the runtime ADDITION rides on top of the stylesheet's base.
    fed.set_strip_height(190, 'oracle-hover')
    want('strip.override', (fed.strip_height, fed.strip_height_extra), (190, 40))
    # A page that cannot answer leaves the fallback, and it must be reported as a
    # fallback — the one thing worse than a default is a default that looks read.
    for label, value in (('empty', ''), ('null', None), ('garbage', 'auto'),
                         ('zero', '0px'), ('negative', '-4px')):
        s = probe_shell(value)
        want(f'strip.css.fallback.{label}',
             (s.refresh_strip_height('oracle'), s.strip_height,
              s.strip_height_css),
             (False, module.STRIP_HEIGHT_FALLBACK, None))

    # -- 18. THE FEED MUST NOT PAY FOR THE LOG -------------------------------
    # The meter is a per-sample feed and `on_worker_stats` fires once per sample.
    # A line per sample is an unbounded log, and an unbounded log is how the
    # meter got switched OFF once. So: 500 samples must produce ONE line, the
    # panel must still be fed 500 times, and the push must not block the pump
    # thread that carries the captions.
    if not isinstance(getattr(module, 'STATS_LOG_INTERVAL_S', None), float) \
            or module.STATS_LOG_INTERVAL_S < 5:
        failures.append('STATS_LOG_INTERVAL_S is missing or absurdly small')
    on_stats_src = inspect.getsource(module.SottoShell.on_worker_stats)
    if 'self._stats_log_maybe(payload)' not in on_stats_src:
        failures.append('on_worker_stats does not aggregate its log line')
    if 'self.emit_async(' not in on_stats_src:
        failures.append('on_worker_stats does not use emit_async: a per-sample '
                        'round trip would stall the pump thread that carries '
                        'the captions')

    collected = []
    real_log = module.log
    module.log = lambda message: collected.append(str(message))
    try:
        logbudget = module.SottoShell.__new__(module.SottoShell)
        logbudget.stats_pushes = 0
        logbudget.stats_logged = 0
        logbudget.stats_logged_at = 0.0

        # The bridge holds the parsed line, exactly as `WorkerBridge._pump` does
        # before it calls `on_stats` — `stats()` reads it from there, so the push
        # and the pull cannot disagree about one measurement.
        class OneBridge:
            last_worker_stats = {'tag': 'tick',
                                 'fields': {'peak': '0.5', 'blocks': '3'},
                                 'line': ''}

        logbudget.bridge = OneBridge()
        emitted = []
        logbudget.emit_async = lambda kind, payload: emitted.append((kind, payload))
        for _ in range(500):
            logbudget.on_worker_stats({'tag': 'tick',
                                       'fields': {'peak': '0.5', 'blocks': '3'},
                                       'line': ''})
    finally:
        module.log = real_log
    push_lines = [c for c in collected if c.startswith('BRIDGE_STATS_PUSH')]
    facts['stats.log_budget'] = {'samples': logbudget.stats_pushes,
                                 'log_lines': len(push_lines),
                                 'emitted': len(emitted)}
    want('stats.log.500-samples-1-line', len(push_lines), 1)
    want('stats.log.feed-not-throttled', len(emitted), 500)
    want('stats.log.payload-shape', emitted[0][1] if emitted else None,
         {'peak': 0.5, 'blocks': 3.0})

    # -- 19. THE RELOAD CONTRACT (the owner's order: never old code again) ----
    # Driven, not grepped: a stand-in bridge that stays CAPTURING, so the guard,
    # the boundary, the ceiling and the floor are all exercised as CODE.
    class CapturingBridge:
        child = object()
        loaded_sha256 = 'deadbeefdeadbeef'

        def __init__(self, path):
            self.worker_path = path
            self.capturing = True
            self.spawned_at = time.monotonic() - 5.0

        def is_capturing(self):
            return self.capturing

    reload_facts = {}
    facts['reload'] = reload_facts

    def policy_for(br, **kwargs):
        lines = []
        restarts = []
        policy = module.WorkerReloadPolicy(
            log_fn=lines.append, get_bridge=lambda: br,
            restart=lambda files: restarts.append(list(files)), **kwargs)
        return policy, lines, restarts

    def settle(seconds=0.45):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            time.sleep(0.02)

    # (a) the boundary is the CLOSED LINE, and it passes the capture guard.
    br = CapturingBridge(module.SHELL_PATH)
    policy, lines, restarts = policy_for(br, debounce_ms=0, min_interval_ms=0,
                                         max_defer_ms=600000,
                                         defer_recheck_ms=5000)
    policy.request(['worker/sotto_worker.py'])
    settle()
    reload_facts['deferred_while_capturing'] = {
        'restarts': len(restarts),
        'deferred': [ln for ln in lines if 'DEFERRED' in ln],
        'pending': policy.pending is not None,
    }
    want('reload.capture-guard.holds', len(restarts), 0)
    want('reload.capture-guard.visible',
         len([ln for ln in lines if 'HOT_RELOAD_WORKER_DEFERRED' in ln]), 1)
    want('reload.capture-guard.deferral-is-bounded-and-named', any(
        'max_defer_ms=' in ln and 'waited_ms=' in ln and 'sha256_disk=' in ln
        and 'sha256_at_spawn=' in ln for ln in lines), True)
    policy.boundary(why='status')          # a status while capturing is NOT one
    settle(0.3)
    want('reload.status-line-is-not-a-boundary-while-capturing',
         len(restarts), 0)
    policy.boundary(closed=True, why='closed-line')
    settle(0.6)
    reload_facts['closed_line'] = {'restarts': len(restarts),
                                   'lines': [ln for ln in lines
                                             if 'BOUNDARY' in ln]}
    want('reload.closed-line-applies-while-capturing', len(restarts), 1)
    want('reload.closed-line-is-named',
         any('reason=closed-line' in ln for ln in lines), True)
    policy.stop()

    # (b) the CEILING: no boundary ever, and it still applies — loudly.
    br = CapturingBridge(module.SHELL_PATH)
    policy, lines, restarts = policy_for(br, debounce_ms=0, min_interval_ms=0,
                                         max_defer_ms=250, defer_recheck_ms=50)
    policy.request(['worker/sotto_worker.py'])
    settle(1.0)
    reload_facts['ceiling'] = {'restarts': len(restarts),
                               'forced': [ln for ln in lines if 'FORCED' in ln],
                               'pending': policy.pending is not None}
    want('reload.ceiling-applies-with-no-boundary', len(restarts), 1)
    want('reload.ceiling-says-so', any(
        'HOT_RELOAD_WORKER_FORCED' in ln and 'reason=no-boundary-in-250ms' in ln
        for ln in lines), True)
    want('reload.ceiling-leaves-nothing-pending', policy.pending, None)
    policy.stop()

    # (c) the FLOOR still bounds the rate — and the `>` that makes it work.
    br = CapturingBridge(module.SHELL_PATH)
    br.spawned_at = time.monotonic()   # the SAME clock tick as the request
    policy, lines, restarts = policy_for(br, debounce_ms=0,
                                         min_interval_ms=60000,
                                         max_defer_ms=150, defer_recheck_ms=50)
    policy.request(['worker/sotto_worker.py'])
    settle(0.9)
    reload_facts['floor'] = {'restarts': len(restarts),
                             'cooldown': [ln for ln in lines if 'COOLDOWN' in ln],
                             'pending': policy.pending is not None}
    want('reload.floor-bounds-the-rate', len(restarts), 0)
    want('reload.floor-keeps-the-request', policy.pending is not None, True)
    # THE COARSE-CLOCK BUG: a spawn recorded in the SAME `time.monotonic()` tick
    # as the request must NOT be read as "a respawn happened after the request".
    # With `>=` it was, and the held reload was silently declared satisfied —
    # the owner back on old code, which is the defect being repaired. Measured:
    # two consecutive `time.monotonic()` calls compare EQUAL on this box.
    want('reload.clock-equal-is-not-a-respawn',
         any('APPLIED_AT_BOUNDARY' in ln for ln in lines), False)
    policy.stop()

    # -- 20. THE WAVE: `type:"meter"` has its own branch, with a log budget ---
    collected_meter = []
    bridge = module.WorkerBridge.__new__(module.WorkerBridge)
    bridge.log = lambda message: collected_meter.append(str(message))
    bridge.malformed = 0
    bridge.meters = 0
    bridge.last_meter = None
    bridge._meter_logged = 0
    bridge._meter_logged_at = 0.0
    bridge.child = None
    bridge.last_worker_stats = {'tag': 'tick',
                                'fields': {'peak': '0.443448', 'blocks': '812'},
                                'line': ''}
    meter_samples = []
    bridge.on_meter = meter_samples.append
    for index in range(500):
        bridge._consume(json.dumps({'type': 'meter',
                                    'peak': 0.1 + (index % 7) / 100.0,
                                    'blocks': 12}))
    facts['meter'] = {'samples': bridge.meters,
                      'log_lines': len([c for c in collected_meter
                                        if c.startswith('BRIDGE_METER')]),
                      'unknown_lines': len([c for c in collected_meter
                                            if c.startswith('BRIDGE_UNKNOWN')]),
                      'delivered': len(meter_samples)}
    want('meter.branch-exists', bridge.meters, 500)
    want('meter.delivered-to-the-page-callback', len(meter_samples), 500)
    want('meter.unknown-kind-path-not-taken', facts['meter']['unknown_lines'], 0)
    want('meter.log-aggregated-to-one-line', facts['meter']['log_lines'], 1)
    want('meter.sample-shape', sorted(meter_samples[0].keys() - {'at'}),
         ['blocks', 'peak'])

    # the WINDOW value WINS over the stderr running maximum, and the two are
    # never mixed; with no fresh meter the stats line is the fallback.
    wave_shell = module.SottoShell.__new__(module.SottoShell)
    wave_shell.bridge = bridge
    facts['meter.stats_payload'] = wave_shell.stats()
    want('meter.stats-prefers-the-window-peak', wave_shell.stats(),
         {'peak': 0.1 + (499 % 7) / 100.0, 'blocks': 12.0})
    bridge.last_meter = {'at': time.monotonic() - (module.METER_FRESH_S + 1.0),
                         'peak': 0.99, 'blocks': 99.0}
    facts['meter.stats_fallback'] = wave_shell.stats()
    want('meter.stats-falls-back-to-the-running-maximum-when-stale',
         wave_shell.stats(), {'peak': 0.443448, 'blocks': 812.0})

    return failures, facts


def main():
    report = {'shell': SHELL, 'arms': {}}
    real_failures, real_facts = check(load(SHELL, 'sotto_real'))

    # The NEGATIVE CONTROL: the same file with the member removed. Built by a
    # literal textual revert, so what changes is exactly one thing.
    shutil.copyfile(SHELL, MUTANT)
    with open(MUTANT, encoding='utf-8') as fh:
        src = fh.read()
    reverted = re.sub(
        r'\n    setPanelSurface: function \(surface, reason\) \{.*?\n    \},\n',
        '\n', src, count=1, flags=re.S)
    reverted = reverted.replace("'setPanelSurface', 'getStats', 'onStats']",
                                "'getStats', 'onStats']")
    if reverted == src:
        raise SystemExit('the negative control could not be built: the member '
                         'text was not found verbatim')
    with open(MUTANT, 'w', encoding='utf-8') as fh:
        fh.write(reverted)
    try:
        mut_failures, _ = check(load(MUTANT, 'sotto_mutant'))
    finally:
        try:
            os.remove(MUTANT)
        except OSError:
            pass

    member_failures = [f for f in mut_failures
                       if 'setPanelSurface' in f or 'panel-surface' in f]

    # The SECOND control, and it is what keeps the DRIVEN dispatch arm honest: a
    # dict entry removed from the routing table must make that arm RED, or the
    # arm was passing on something other than the wiring.
    shutil.copyfile(SHELL, MUTANT)
    with open(MUTANT, encoding='utf-8') as fh:
        src2 = fh.read()
    reverted2 = src2.replace("            'stats': self._stats,\n", '')
    reverted2 = reverted2.replace(
        "            'panel-surface': self._panel_surface,\n", '')
    if reverted2 == src2:
        raise SystemExit('the second negative control could not be built: the '
                         'dispatch entries were not found verbatim')
    with open(MUTANT, 'w', encoding='utf-8') as fh:
        fh.write(reverted2)
    try:
        mut2_failures, _ = check(load(MUTANT, 'sotto_mutant2'))
    finally:
        try:
            os.remove(MUTANT)
        except OSError:
            pass
    routed_failures = [f for f in mut2_failures
                       if 'dispatch does not route' in f]

    # The THIRD control, for the panel lane's rule: the strip's height has ONE
    # home (`panel.css:52`) and the shell must READ it. A copy of today's shell
    # that keeps its own number instead must go RED on the stylesheet arms — which
    # is the exact defect "if the value appears in two places, the next person to
    # touch the theme leaves the shell lying about the window it sized".
    shutil.copyfile(SHELL, MUTANT)
    with open(MUTANT, encoding='utf-8') as fh:
        src3 = fh.read()
    reverted3 = src3.replace(
        "        value = self.strip_height_from_css()\n",
        "        return False  # MUTANT: the stylesheet is not read\n"
        "        value = self.strip_height_from_css()\n", 1)
    if reverted3 == src3:
        raise SystemExit('the third negative control could not be built: '
                         'refresh_strip_height does not read the CSS verbatim')
    with open(MUTANT, 'w', encoding='utf-8') as fh:
        fh.write(reverted3)
    try:
        mut3_failures, _ = check(load(MUTANT, 'sotto_mutant3'))
    finally:
        try:
            os.remove(MUTANT)
        except OSError:
            pass
    css_failures = [f for f in mut3_failures if 'strip.css' in f]

    # The FOURTH control: the log budget, reverted to one line per sample. The
    # 500-samples arm must go RED, and NOTHING else should move — that is what
    # makes it a control rather than a second subject.
    shutil.copyfile(SHELL, MUTANT)
    with open(MUTANT, encoding='utf-8') as fh:
        src4 = fh.read()
    reverted4 = src4.replace(
        "        self._stats_log_maybe(payload)\n",
        "        log('BRIDGE_STATS_PUSH count=' + str(self.stats_pushes) + ' '\n"
        "            'payload=' + json.dumps(payload, separators=(',', ':')))\n", 1)
    if reverted4 == src4:
        raise SystemExit('the fourth negative control could not be built: '
                         '`self._stats_log_maybe(payload)` was not found verbatim')
    with open(MUTANT, 'w', encoding='utf-8') as fh:
        fh.write(reverted4)
    try:
        mut4_failures, _ = check(load(MUTANT, 'sotto_mutant4'))
    finally:
        try:
            os.remove(MUTANT)
        except OSError:
            pass
    logbudget_failures = [f for f in mut4_failures if 'stats.log' in f]

    report['arms']['real'] = {'failures': real_failures, 'facts': real_facts}
    report['arms']['mutant'] = {
        'failures': mut_failures,
        'red_on_the_member': bool(member_failures),
        'control_failures': member_failures,
    }
    report['arms']['mutant2'] = {
        'failures': mut2_failures,
        'red_on_the_routing': bool(routed_failures),
        'control_failures': routed_failures,
    }
    report['arms']['mutant3'] = {
        'failures': mut3_failures,
        'red_on_the_css_height': bool(css_failures),
        'control_failures': css_failures,
    }
    report['arms']['mutant4'] = {
        'failures': mut4_failures,
        'red_on_the_log_budget': bool(logbudget_failures),
        'control_failures': logbudget_failures,
    }
    green = ((not real_failures) and bool(member_failures)
             and bool(routed_failures) and bool(css_failures)
             and bool(logbudget_failures))
    report['verdict'] = 'GREEN' if green else 'RED'
    report['reason'] = (
        'the real shell passes every arm; the member-removed COPY goes RED on '
        'the member it is missing, the routing-removed COPY goes RED on the '
        'driven dispatch arm, the CSS-blind COPY goes RED on the stylesheet '
        'height, and the per-sample-log COPY goes RED on the log budget'
        if green else
        f'real failures={len(real_failures)} '
        f'mutant red-on-member={bool(member_failures)} '
        f'mutant2 red-on-routing={bool(routed_failures)} '
        f'mutant3 red-on-css-height={bool(css_failures)} '
        f'mutant4 red-on-log-budget={bool(logbudget_failures)}')
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(report['verdict'], '--', report['reason'])
    for line in real_failures:
        print('  REAL-FAIL', line)
    for line in member_failures:
        print('  MUTANT-FAIL (expected)', line)
    for line in routed_failures:
        print('  MUTANT2-FAIL (expected)', line)
    for line in css_failures:
        print('  MUTANT3-FAIL (expected)', line)
    for line in logbudget_failures:
        print('  MUTANT4-FAIL (expected)', line)
    if green:
        # THE CONTROL VERDICT the battery's `:control` kind demands: rc=0 alone
        # is not enough, because an oracle that never built its broken copies
        # would also exit 0.
        print(f'STRIP-ORACLE CONTROL PASS broken-copies-red=4 '
              f'arms={len(real_facts)}')
    return 0 if green else 3


if __name__ == '__main__':
    # A CRASH MUST NOT LOOK LIKE A STALE PASS. `pythonw` has no stdout, so an
    # uncaught exception leaves the PREVIOUS report on disk and an rc the caller
    # may not read — measured: this oracle printed `rc=1` beside a stale
    # `GREEN`. The traceback goes into the report file instead.
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        import traceback
        with open(REPORT, 'w', encoding='utf-8') as fh:
            json.dump({'verdict': 'CRASH', 'reason': 'the oracle raised',
                       'traceback': traceback.format_exc()}, fh, indent=2)
        sys.exit(3)
