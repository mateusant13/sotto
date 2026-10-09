#!/usr/bin/env python3
"""HOT RELOAD, against a REAL worker process — the defect the owner forbade.

THE DEFECT (measured on his own app, 2026-10-08): **20 QUEUED / 20 DEFERRED /
0 APPLIED / 0 respawns** since the worker started at 08:01:56. `WorkerReloadPolicy`
held every edit to `worker/sotto_worker.py` waiting for `is_capturing()` to go
false — and that only happens when the worker STOPS, which never happens while
there is audio. So he ran hours-old code and reported bugs that were already
fixed. His order: *"e tu estás a correr código antigo nao faça isso acontecer de
novo, entao. hot reload ao maximo"*.

FIVE arms, every one of them against a REAL `WorkerBridge` and a REAL child
process (`_main/_strip-stats-worker.py`, which opens NO audio device):

  A. HELD-VISIBLY   a capture is open, the ceiling is far away: the request stays
                    held, the child's PID is UNCHANGED, and the log says how long
                    it has waited, the ceiling, and whether the code on disk is
                    still what the process loaded.
  B. STALENESS      the same bridge pointed at a COPY of the worker file: the
                    query says `stale=false`, then one byte is appended to the
                    copy and it says `stale=true` with both hashes. This is the
                    difference between a QUERY and a discovery.
  C. CLOSED-LINE    the child emits a `caption` with `final:true` (the line the
                    WORKER closed) and the held reload APPLIES — a NEW pid, while
                    the worker is still capturing. This is the fix, end to end
                    through the REAL `SottoShell.on_worker_caption`.
  D. CEILING        no boundary ever arrives and the ceiling is short: the reload
                    applies ANYWAY and the log says FORCED. An unbounded deferral
                    is a broken promise.
  E. FLOOR          the ceiling has elapsed but the owner's floor has not:
                    COOLDOWN, PID unchanged, request still held. The floor bounds
                    the RATE even when a boundary or the ceiling says "now".
  F. THE WAVE       a real child publishing `{"type":"meter",...}` at 20 Hz: the
                    payload the panel receives is the WINDOW peak (oscillating),
                    NOT the stderr running maximum, the push count is in the tens,
                    and the log grows by ONE line (the old unknown-kind path
                    logged 35 B per sample = ~20.5 KB/min, forever).

Nothing here touches `worker/sotto_worker.py`: the file under the watcher is a
TEMP COPY, and the child is a stand-in that opens no device.

    pythonw.exe _main/_strip-reload-probe.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WEBVIEW = os.path.join(os.path.dirname(HERE), 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
STANDIN = os.path.join(HERE, '_strip-stats-worker.py')
REPORT = os.path.join(HERE, '_strip-reload-probe.json')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') \
    else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')

if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

report = {'arms': {}, 'checks': [], 'verdict': None, 'traceback': None}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check(what, ok, detail=None):
    row = {'what': what, 'ok': bool(ok)}
    if detail is not None:
        row['detail'] = detail
    report['checks'].append(row)
    return bool(ok)


class Harness:
    """A REAL bridge on a REAL child, with the REAL shell methods wired to it.

    `SottoShell.__new__` is used deliberately: the production METHODS are what is
    under test (`on_worker_caption` -> `boundary(closed=True)`, `on_worker_meter`
    -> `emit_async`, `stats()`), and only the three seams that need a WebView2
    (`emit`, `emit_async`, and the window) are stood in for.
    """

    def __init__(self, module, worker_path, env=None, **policy_kwargs):
        self.module = module
        self.lines = []
        self.emitted = []
        self.worker_path = worker_path
        self.shell = module.SottoShell.__new__(module.SottoShell)
        self.shell.emit = lambda kind, payload: self.emitted.append((kind, payload))
        self.shell.emit_async = lambda kind, payload: self.emitted.append((kind, payload))
        # The PANEL-PAINT half of `on_worker_status` needs a live WebView2
        # (`apply_panel_state` -> `exec_js` -> pythonnet). It is not the subject
        # here: the subject is the `boundary(why='status')` call that follows it,
        # which is the real one and stays real.
        self.shell.apply_panel_state = lambda *a, **k: None
        self.shell.meter_pushes = 0
        self.shell.stats_pushes = 0
        self.shell.stats_replies = 0
        self.shell.stats_logged = 0
        self.shell.stats_logged_at = 0.0
        self.policy = module.WorkerReloadPolicy(
            log_fn=self.log, get_bridge=lambda: self.bridge,
            restart=self.restart, **policy_kwargs)
        self.shell._reload_policy = self.policy
        self.restarts = []
        self.saved_env = {}
        self.env = env or {}

    def log(self, line):
        self.lines.append(str(line))

    def start(self):
        module = self.module
        self.bridge = module.WorkerBridge(
            command=PYW, worker_path=self.worker_path,
            on_caption=self.shell.on_worker_caption,
            on_status=self.shell.on_worker_status,
            on_stats=self.shell.on_worker_stats,
            on_meter=self.shell.on_worker_meter,
            log=self.log)
        self.shell.bridge = self.bridge
        for key, value in self.env.items():
            self.saved_env[key] = os.environ.get(key)
            os.environ[key] = str(value)
        try:
            self.bridge.start('reload-probe')
        finally:
            for key, value in self.saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        return self

    def restart(self, files):
        self.restarts.append(list(files))
        self.bridge.stop('probe-restart')
        self.bridge = self.module.WorkerBridge(
            command=PYW, worker_path=self.worker_path,
            on_caption=self.shell.on_worker_caption,
            on_status=self.shell.on_worker_status,
            on_stats=self.shell.on_worker_stats,
            on_meter=self.shell.on_worker_meter,
            log=self.log)
        self.shell.bridge = self.bridge
        for key, value in self.env.items():
            self.saved_env[key] = os.environ.get(key)
            os.environ[key] = str(value)
        try:
            self.bridge.start('reload-probe-restart')
        finally:
            for key, value in self.saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        return True

    def pid(self):
        child = getattr(self.bridge, 'child', None)
        return getattr(child, 'pid', None)

    def has(self, needle):
        return [line for line in self.lines if needle in line]

    def close(self):
        try:
            self.policy.stop()
        except Exception:
            pass
        try:
            if self.bridge is not None:
                self.bridge.stop('probe-done')
        except Exception:
            pass


def wait_for(fn, timeout, step=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fn():
            return True
        time.sleep(step)
    return bool(fn())


def arm_a_and_b(module, tmp):
    """A. the request is held VISIBLY. B. the staleness query is real."""
    copy = os.path.join(tmp, 'sotto_worker_copy.py')
    shutil.copyfile(STANDIN, copy)
    harness = Harness(module, copy, env={'SOTTO_STANDIN_HZ': '0.5',
                                         'SOTTO_STANDIN_SECS': '30'},
                      debounce_ms=0, min_interval_ms=0,
                      max_defer_ms=600000, defer_recheck_ms=5000).start()
    wait_for(lambda: harness.bridge.is_capturing(), 6)
    pid0 = harness.pid()
    capturing = harness.bridge.is_capturing()
    state0 = harness.policy.state()
    harness.policy.request([copy])
    wait_for(lambda: harness.has('HOT_RELOAD_WORKER_DEFERRED'), 4)
    deferred = harness.has('HOT_RELOAD_WORKER_DEFERRED')
    line = deferred[0] if deferred else ''
    held_state = harness.policy.state()
    report['arms']['A_held'] = {
        'capturing': capturing, 'pid_before': pid0, 'pid_after': harness.pid(),
        'restarts': len(harness.restarts), 'deferred_line': line,
        'pending_ms': held_state['pending_ms'],
        'stale_before_edit': state0['worker']['stale'],
    }
    check('A: the child is really capturing (the guard is not vacuous)',
          capturing, {'pid': pid0})
    check('A: the reload is HELD, not applied, while capturing',
          harness.pid() == pid0 and not harness.restarts,
          {'pid': harness.pid(), 'restarts': len(harness.restarts)})
    check('A: the hold is VISIBLE with the reason, the wait and the ceiling',
          'reason=capturing' in line and 'waited_ms=' in line
          and 'max_defer_ms=600000' in line and 'code_is_stale=' in line
          and 'sha256_disk=' in line and 'sha256_at_spawn=' in line, line)
    check('A: the wait is BOUNDED (a ceiling is declared)',
          harness.policy.max_defer_ms == 600000
          and held_state['pending_ms'] is not None)

    # ── B. the staleness query, both colours, on the SAME bridge ────────────
    before = harness.policy.state()['worker']
    with open(copy, 'a', encoding='utf-8') as fh:
        fh.write('\n# one byte more\n')
    after = harness.policy.state()['worker']
    report['arms']['B_staleness'] = {'before': before, 'after': after}
    check('B: the query says CURRENT while the disk matches the spawn',
          before['stale'] is False and before['disk'] == before['loaded'],
          before)
    check('B: the query says STALE after one byte changes on disk',
          after['stale'] is True and after['disk'] != after['loaded'],
          after)
    check('B: both hashes are named (disk vs what the process loaded)',
          isinstance(after['disk'], str) and len(after['disk']) == 16
          and isinstance(after['loaded'], str) and len(after['loaded']) == 16,
          after)
    harness.close()
    return harness


def arm_c(module):
    """C. the CLOSED LINE applies the held reload, with the worker capturing."""
    harness = Harness(module, STANDIN, env={'SOTTO_STANDIN_HZ': '0.5',
                                            'SOTTO_STANDIN_SECS': '30',
                                            'SOTTO_STANDIN_CLOSED_AT': '1.5'},
                      debounce_ms=0, min_interval_ms=0,
                      max_defer_ms=600000, defer_recheck_ms=5000).start()
    wait_for(lambda: harness.bridge.is_capturing(), 6)
    pid0 = harness.pid()
    harness.policy.request([STANDIN])
    wait_for(lambda: harness.has('HOT_RELOAD_WORKER_DEFERRED'), 4)
    held_pid = harness.pid()
    # SNAPSHOT, not a live read: the checks below run after the boundary has
    # already fired, so `harness.restarts` would be non-empty by then and the
    # assertion would fail for the wrong reason (measured once).
    held_restarts = len(harness.restarts)
    # the child closes a line at ~1.5 s; nothing else drives the boundary
    applied = wait_for(lambda: bool(harness.restarts), 8)
    # The restart runs on the policy's TIMER thread: wait for the NEW child to be
    # up AND to have declared its own capture, or both reads below are a race.
    wait_for(lambda: harness.pid() not in (None, pid0)
             and harness.bridge.is_capturing(), 10)
    pid1 = harness.pid()
    report['arms']['C_closed_line'] = {
        'pid_before': pid0, 'pid_while_held': held_pid, 'pid_after': pid1,
        'restarts_while_held': held_restarts,
        'restarts': len(harness.restarts),
        'boundary_lines': harness.has('HOT_RELOAD_WORKER_BOUNDARY'),
        'applied_lines': harness.has('HOT_RELOAD_WORKER_BOUNDARY_APPLIED'),
        'captions': [p for k, p in harness.emitted if k == 'caption'],
        'still_capturing_after': harness.bridge.is_capturing(),
    }
    check('C: the held request is not applied before the boundary',
          held_pid == pid0 and held_restarts == 0,
          {'pid_while_held': held_pid, 'restarts_while_held': held_restarts})
    check('C: the REAL child closed a line and the shell saw it as the boundary',
          bool(harness.has('HOT_RELOAD_WORKER_BOUNDARY reason=closed-line')),
          harness.has('HOT_RELOAD_WORKER_BOUNDARY'))
    check('C: the held reload APPLIED on the closed line (a NEW pid)',
          applied and pid1 != pid0 and pid1 is not None,
          {'pid_before': pid0, 'pid_after': pid1})
    check('C: it applied while the worker was still capturing (not on a stop)',
          bool(harness.has('HOT_RELOAD_WORKER_BOUNDARY_APPLIED'))
          and harness.bridge.is_capturing())
    check('C: the closed line reached the panel as a caption',
          any(isinstance(p, dict) and p.get('meta', {}).get('final') is True
              for _k, p in harness.emitted if _k == 'caption'),
          report['arms']['C_closed_line']['captions'])
    harness.close()


def arm_d_and_e(module):
    """D. the ceiling applies with no boundary. E. the floor still bounds."""
    harness = Harness(module, STANDIN, env={'SOTTO_STANDIN_HZ': '0.5',
                                            'SOTTO_STANDIN_SECS': '30'},
                      debounce_ms=0, min_interval_ms=0,
                      max_defer_ms=600, defer_recheck_ms=100).start()
    wait_for(lambda: harness.bridge.is_capturing(), 6)
    pid0 = harness.pid()
    harness.policy.request([STANDIN])
    forced = wait_for(lambda: bool(harness.restarts), 6)
    # The restart runs on the policy's TIMER thread, so `restarts` can be
    # recorded before the new bridge exists. Wait for the NEW child to be up and
    # to have declared its own capture, or the pid read is a race (measured: a
    # `pid_after=None` from reading the old, stopped bridge).
    wait_for(lambda: harness.pid() not in (None, pid0)
             and harness.bridge.is_capturing(), 10)
    pid1 = harness.pid()
    report['arms']['D_ceiling'] = {
        'pid_before': pid0, 'pid_after': pid1,
        'forced_lines': harness.has('HOT_RELOAD_WORKER_FORCED'),
        'reload_lines': harness.has('HOT_RELOAD_WORKER_'),
        'restarts': len(harness.restarts),
        'still_capturing': harness.bridge.is_capturing(),
    }
    check('D: with NO boundary the ceiling applies the reload anyway',
          forced and pid1 != pid0, {'pid_before': pid0, 'pid_after': pid1})
    check('D: the log says it FORCED, with the reason and the wait',
          any('HOT_RELOAD_WORKER_FORCED' in line
              and 'reason=no-boundary-in-600ms' in line
              and 'waited_ms=' in line
              for line in report['arms']['D_ceiling']['forced_lines']),
          report['arms']['D_ceiling']['forced_lines'])
    check('D: nothing is left pending after the ceiling applied',
          harness.policy.pending is None)
    harness.close()

    harness = Harness(module, STANDIN, env={'SOTTO_STANDIN_HZ': '0.5',
                                            'SOTTO_STANDIN_SECS': '30'},
                      debounce_ms=0, min_interval_ms=60000,
                      max_defer_ms=400, defer_recheck_ms=100).start()
    wait_for(lambda: harness.bridge.is_capturing(), 6)
    pid0 = harness.pid()
    harness.policy.request([STANDIN])
    time.sleep(1.5)                      # > the 400 ms ceiling, << the floor
    report['arms']['E_floor'] = {
        'pid_before': pid0, 'pid_after': harness.pid(),
        'restarts': len(harness.restarts),
        'cooldown_lines': harness.has('HOT_RELOAD_WORKER_COOLDOWN'),
        'pending_held': harness.policy.pending is not None,
    }
    check('E: the owner\'s floor bounds the RATE even after the ceiling',
          harness.pid() == pid0 and not harness.restarts
          and harness.policy.pending is not None,
          {'pid': harness.pid(), 'restarts': len(harness.restarts)})
    check('E: the cooldown names how long is left and that the code is stale',
          bool(harness.has('HOT_RELOAD_WORKER_COOLDOWN'))
          and 'left_ms=' in (harness.has('HOT_RELOAD_WORKER_COOLDOWN') or [''])[0]
          and 'applies_when=floor-elapses'
          in (harness.has('HOT_RELOAD_WORKER_COOLDOWN') or [''])[0],
          harness.has('HOT_RELOAD_WORKER_COOLDOWN'))
    harness.close()


def arm_f(module):
    """F. THE WAVE: the window peak, at the meter's cadence, one log line."""
    harness = Harness(module, STANDIN, env={'SOTTO_STANDIN_HZ': '0.5',
                                            'SOTTO_STANDIN_SECS': '30',
                                            'SOTTO_STANDIN_METER_HZ': '20'},
                      debounce_ms=0, min_interval_ms=0,
                      max_defer_ms=600000, defer_recheck_ms=5000).start()
    wait_for(lambda: harness.bridge.meters >= 40, 8)
    time.sleep(0.4)
    peaks = [p.get('peak') for k, p in harness.emitted
             if k == 'stats' and isinstance(p, dict)]
    distinct = sorted({p for p in peaks if p is not None})
    stats_now = harness.shell.stats()
    report['arms']['F_wave'] = {
        'meters': harness.bridge.meters,
        'meter_pushes': harness.shell.meter_pushes,
        'distinct_peaks': distinct,
        'stats_now': stats_now,
        'meter_log_lines': len(harness.has('BRIDGE_METER ')),
        'unknown_lines': len(harness.has('BRIDGE_UNKNOWN')),
        'stderr_peak': '0.443448',
    }
    check('F: the meter events arrive at the worker\'s own cadence',
          harness.bridge.meters >= 40, {'meters': harness.bridge.meters})
    check('F: every meter event was PUSHED to the page (no throttling of data)',
          harness.shell.meter_pushes == harness.bridge.meters,
          {'pushed': harness.shell.meter_pushes,
           'meters': harness.bridge.meters})
    # The FIRST push can legitimately carry the stderr running maximum: it is
    # emitted the instant the worker prints its first `WORKER_STATS` line, which
    # is BEFORE the first meter window closes. What must never happen is the
    # running maximum AFTER the meter is live — that is the staircase the owner
    # reported. So the warm-up is BOUNDED to one sample by the assertion itself,
    # rather than excluded by a positional guess (which was flaky: the number of
    # pre-meter pushes depends on timing).
    warmup = [p for p in peaks if p == 0.443448]
    live_distinct = sorted({p for p in peaks if p is not None and p != 0.443448})
    report['arms']['F_wave']['live_distinct'] = live_distinct
    report['arms']['F_wave']['warmup'] = warmup
    check('F: the payload is the WINDOW peak, not the stderr running maximum',
          len(live_distinct) >= 4 and len(warmup) <= 1
          and stats_now.get('peak') != 0.443448,
          {'live_distinct': live_distinct, 'warmup': warmup,
           'stats_now': stats_now})
    check('F: `stats()` agrees with the pushed payload (one shape, one value)',
          stats_now.get('peak') in live_distinct and 'blocks' in stats_now,
          stats_now)
    check('F: the log grew by ONE line, not one per sample',
          len(harness.has('BRIDGE_METER ')) <= 2,
          {'lines': len(harness.has('BRIDGE_METER '))})
    check('F: the unknown-kind path no longer sees a meter sample',
          len(harness.has('BRIDGE_UNKNOWN')) == 0,
          {'unknown': len(harness.has('BRIDGE_UNKNOWN'))})
    harness.close()

    # ── the OTHER colour: no meter at all -> the stderr running maximum ─────
    harness = Harness(module, STANDIN, env={'SOTTO_STANDIN_HZ': '2',
                                            'SOTTO_STANDIN_SECS': '20',
                                            'SOTTO_STANDIN_METER_HZ': '0'},
                      debounce_ms=0, min_interval_ms=0,
                      max_defer_ms=600000, defer_recheck_ms=5000).start()
    wait_for(lambda: harness.bridge.last_worker_stats is not None, 6)
    time.sleep(0.3)
    report['arms']['F_wave_nometer'] = {
        'meters': harness.bridge.meters,
        'meter_pushes': harness.shell.meter_pushes,
        'stats': harness.shell.stats(),
    }
    check('F(no meter): no meter push happens, and the fallback is the stats line',
          harness.bridge.meters == 0 and harness.shell.meter_pushes == 0
          and harness.shell.stats().get('peak') == 0.443448,
          report['arms']['F_wave_nometer'])
    harness.close()


def main():
    module = load(SHELL, 'sotto_reload_probe_shell')
    tmp = tempfile.mkdtemp(prefix='sotto-reload-probe-')
    try:
        arm_a_and_b(module, tmp)
        arm_c(module)
        arm_d_and_e(module)
        arm_f(module)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [c['what'] for c in report['checks'] if not c['ok']]
    report['failed'] = failed
    report['verdict'] = 'GREEN' if not failed else 'RED'
    return 0 if not failed else 3


if __name__ == '__main__':
    try:
        code = main()
    except Exception:
        import traceback
        report['traceback'] = traceback.format_exc()
        report['verdict'] = 'CRASH'
        code = 3
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
    print(f'VERDICT: {report["verdict"]}')
    for row in report['checks']:
        print(('ok   ' if row['ok'] else 'FAIL ') + row['what'])
    if report.get('traceback'):
        print(report['traceback'])
    sys.exit(code)
