#!/usr/bin/env python3
"""S7 - the silence window is a function of the PHASE, and the log carries the hour.

THE DEFECT (measured on the owner's own 2026-10-12 logon, _main/webview-run.log):
BRIDGE_SILENT ms=30000 pid=34980 fired between STATUS_APPLIED text="model-loading"
and model-loaded, and the worker it killed was still alive - its own model-loaded
line arrived AFTER the kill. The 30 s no-output window was armed from the moment of
the spawn, so on a cold boot it expired in the middle of the model load, killed a
healthy worker, and the automatic restart paid the whole load again. With the
Windows autostart task that is EVERY boot, and the app loaded the model TWICE in
the first minute after logon.

THE FIX: two windows, selected by the phase. Before model-loaded the worker is obliged
to be quiet - the load reads a gigabyte of weights and copies them to the VRAM and
says nothing while it does - so the watchdog owes it WORKER_LOAD_SILENCE_MS
(180 s, the owner's own bound: "faz o model sair de load apos 3 minutos"). After
model-loaded the worker is obliged to be WORKING and it gets WORKER_SILENCE_MS
(30 s) exactly as before. ONE longer window for both phases would either kill the
cold boot or let a jammed worker keep its caption channel for five minutes; the
phase is the only thing that tells the two apart. The ceiling is still enforced: a
load that never finishes is restarted, loudly, and the panel is told why.

ARMS (all in-process: no device, no model, no WebView2, no window, no process)
  S1  the stamp - hour, LEADING, and it is the clock
  L1  silence BEFORE model-loaded -> BRIDGE_SILENT_LOADING, re-arm, no kill, no paint
  L2  silence AFTER  model-loaded -> BRIDGE_LOAD_MS on the load, then the OLD jam path
  L4  a load that never finishes  -> BRIDGE_SILENT_LOAD_TIMEOUT + reason=load-timeout
  NEG two mutants, each SELECTIVE: the RE-ARM path removed (L1 must go red, L2/L4/S1
      stay green) and the CEILING removed (L4 must go red, L1/L2/S1 stay green)
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
SHELL = os.environ.get('S7_ORACLE_SHELL') or os.path.join(
    ROOT, 'app', 'webview', 'sotto_webview.py')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
CREATE_NO_WINDOW = 0x08000000

#: Small, so the timers fire inside the gate. THE RATIO IS THE CLAIM: a loading
#: child must be owed the LOAD CEILING, not the silence window.
LOAD_SILENCE_MS = 1500
SILENCE_MS = 250
#: Huge, so a restart an arm schedules cannot fire inside the arm.
FAR = 600000

STAMP_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) sotto: (.*)$')
TRAILING_RE = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}$')

MUTANT_REARM = os.path.join(HERE, '_s7-load-rearm-mutant.py')
MUTANT_CEILING = os.path.join(HERE, '_s7-ceiling-mutant.py')

#: The re-arm half of the load branch, verbatim from sotto_webview.py. Deleted whole
#: by mutant 1, so a loading child that goes quiet is killed by the fall-through.
REARM_BLOCK = (
    "            if elapsed_ms < self.load_silence_ms:\n"
    "                self.log(f'BRIDGE_SILENT_LOADING ms={round(elapsed_ms)} '\n"
    "                         f'pid={self.child.pid} '\n"
    "                         f'window_ms={self.load_silence_ms} '\n"
    "                         'because=model-not-loaded')\n"
    "                self._arm_silence()\n"
    "                return\n")
#: Mutant 2: the ceiling comparison replaced by a constant, so the timeout path
#: is unreachable and a load that never finishes is never restarted.
CEILING_LINE = "            if elapsed_ms < self.load_silence_ms:\n"
CEILING_MUTANT = "            if True:\n"

_MODULE = None


def _load_shell_module():
    """Import the shell as a module ONCE, so every arm drives the REAL bridge."""
    global _MODULE
    if _MODULE is None:
        sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
        spec = importlib.util.spec_from_file_location('sotto_webview_s7', SHELL)
        _MODULE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_MODULE)
    return _MODULE


class _Child:
    """A stand-in handle: _kill_and_restart terminates it, stop waits on it."""

    def __init__(self, pid=4242):
        self.pid = pid
        self.terminated = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminated = True


def _new_bridge(log_lines, painted):
    mod = _load_shell_module()
    return mod.WorkerBridge(
        command=sys.executable, worker_path=WORKER,
        log=log_lines.append,
        on_status=lambda t, k, i: painted.append((t, k, dict(i or {}))),
        on_caption=lambda t, m: painted.append(('caption:' + t, 'live',
                                                 dict(m or {}))),
        silence_ms=SILENCE_MS, load_silence_ms=LOAD_SILENCE_MS,
        backoff_base=FAR, backoff_max=FAR)


def _one(log_lines, needle):
    for ln in log_lines:
        if needle in ln:
            return ln
    return None


def _count(log_lines, needle):
    return sum(1 for ln in log_lines if needle in ln)


# --------------------------------------------------------------------------
# S1 - the stamp. Deliverable 2 of this front: the hour on every sotto: line.
# --------------------------------------------------------------------------

def arm_s1(report):
    """Every sotto: line now carries the hour, LEADING, and it is the clock.

    LEADING, not trailing, for two reasons. A log line reads time-first, which is
    what makes the file comparable with every other clock on this box (a shell
    line and a worker line taken tens of seconds apart). And the sotto: tag keeps
    its exact position and spelling: measured across _main/, app/ and worker/,
    7 consumers read these lines by substring or by split('sotto: ', 1)[-1] and
    none of them anchors a regex on the tag, so the tag keeps matching while the
    hour is added in front of it.
    """
    failures = []
    mod = _load_shell_module()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.log('ARM_S1_PROBE')
    line = buf.getvalue().rstrip('\n')
    m = STAMP_RE.match(line)
    if m is None:
        failures.append('ARM S1/stamp: the line does not start with '
                        + repr('<hour> sotto: ') + ': ' + repr(line))
    else:
        stamp, rest = m.group(1), m.group(2)
        if rest != 'ARM_S1_PROBE':
            failures.append('ARM S1/stamp: the message after the tag is '
                            + repr(rest) + ', expected ARM_S1_PROBE')
        try:
            when = time.mktime(time.strptime(stamp[:19], '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            when = None
        if when is None or abs(time.time() - when) > 120:
            failures.append('ARM S1/stamp: ' + repr(stamp)
                            + ' is not a readable hour')
    if TRAILING_RE.search(line):
        failures.append('ARM S1/stamp: the hour is TRAILING, not leading: '
                        + repr(line))
    # The stamp is added by _stamp() inside log(), which is the ONE function both
    # the stdout print and the --log mirror write through - so this arm proves the
    # file path too, without opening a second handle.
    report['arm_s1'] = {'line': line}
    return failures


# --------------------------------------------------------------------------
# L1 - silence BEFORE model-loaded is the LOAD, not a jam.
# --------------------------------------------------------------------------

def arm_l1(report):
    """A quiet worker that has not loaded yet is owed the load ceiling.

    Nothing is killed and nothing is painted: the panel is already showing
    model-loading, which is the truth. The watchdog RE-ARMS, so a child that wedges
    after the load is still caught. Measured on this box, the cold load outlives
    the old 30 s window; this arm is the whole defect.
    """
    failures = []
    log_lines, painted = [], []
    b = _new_bridge(log_lines, painted)
    child = _Child()
    b.child = child
    # 250 ms in: comfortably INSIDE the ceiling, so the branch under test is decided
    # by the PHASE and not by the boundary. (Letting the real timer run to its own
    # expiry races the comparison - the fire lands on the ceiling itself.)
    b.spawned_at = time.monotonic() - 0.25
    b._arm_silence()
    window = b._silence_window()
    want = (LOAD_SILENCE_MS - 250) / 1000.0
    if not window > SILENCE_MS / 1000.0:
        failures.append(f'ARM L1/window: a loading child is owed {window:.3f}s, which '
                        f'is NOT above the silence window '
                        f'{SILENCE_MS / 1000.0:.3f}s - the old defect is back')
    if abs(window - want) > 0.15:
        failures.append(f'ARM L1/window: {window:.3f}s, expected the load ceiling '
                        f'shrinking with the elapsed time, ~{want:.3f}s')
    armed = b._silence_timer
    if armed is None or not armed.is_alive():
        failures.append('ARM L1: the watchdog did not arm')
    b._on_silence()
    loading = _one(log_lines, 'BRIDGE_SILENT_LOADING')
    if loading is None:
        failures.append('ARM L1: no BRIDGE_SILENT_LOADING line - the quiet was not '
                        'named as a load')
    else:
        if 'because=model-not-loaded' not in loading:
            failures.append(f'ARM L1: the loading line does not say why: {loading!r}')
        if f'window_ms={LOAD_SILENCE_MS}' not in loading:
            failures.append(f'ARM L1: the loading line does not carry the ceiling: '
                            f'{loading!r}')
    # The re-armed timer must still be patient: half a second in, it has NOT
    # fired again. Together with the exact window above, that is the whole claim -
    # the child is owed the ceiling, not an instant re-kill.
    time.sleep(0.5)
    n_loading = _count(log_lines, 'BRIDGE_SILENT_LOADING')
    if n_loading != 1:
        failures.append(f'ARM L1: {n_loading} BRIDGE_SILENT_LOADING lines, expected '
                        'exactly 1 - the re-arm must not fire again at once')
    if _one(log_lines, 'BRIDGE_SILENT ms=') is not None:
        failures.append(f'ARM L1: the OLD anomalous path fired during the load: '
                        f'{_one(log_lines, "BRIDGE_SILENT ms=")!r}')
    if _one(log_lines, 'BRIDGE_RESTART') is not None:
        failures.append(f'ARM L1: a restart was scheduled during the load: '
                        f'{_one(log_lines, "BRIDGE_RESTART")!r}')
    if painted:
        failures.append(f'ARM L1: the panel was painted during the load: {painted!r}')
    if b.child is not child or child.terminated:
        failures.append('ARM L1: the loading child was killed')
    if b.restarts:
        failures.append(f'ARM L1: restarts={b.restarts}, expected 0')
    timer = b._silence_timer
    if timer is None or not timer.is_alive():
        failures.append('ARM L1: the watchdog did NOT re-arm after the loading '
                        'silence (no live timer)')
    b.stop('arm-l1')
    report['arm_l1'] = {'window_s': round(window, 3), 'log_tail': log_lines[-4:]}
    return failures


# --------------------------------------------------------------------------
# L2 - silence AFTER model-loaded is the jam, and the load was MEASURED.
# --------------------------------------------------------------------------

def arm_l2(report):
    """Once the worker has loaded, the old 30 s contract is back - and the load
    itself is now a number in the log.

    BRIDGE_LOAD_MS is the SHELL's measurement, from the spawn; load_s on the same
    line is the WORKER's own. One boot log therefore carries both, and the two can
    be compared instead of assumed equal - which is what makes the startup stutter
    (deliverable 3) attributable to a phase.
    """
    failures = []
    log_lines, painted = [], []
    b = _new_bridge(log_lines, painted)
    child = _Child()
    b.child = child
    b.spawned_at = time.monotonic() - 4.66
    b._consume(json.dumps({'type': 'status', 'state': 'model-loaded',
                           'load_s': 4.66, 'captions': 0}))
    if not b.loaded:
        failures.append('ARM L2: model-loaded did not set loaded')
    if not b.load_ms > 4000:
        failures.append(f'ARM L2: the shell measured load_ms={round(b.load_ms)}, '
                        f'expected ~4660 (spawn to model-loaded)')
    load_line = _one(log_lines, 'BRIDGE_LOAD_MS')
    if load_line is None:
        failures.append('ARM L2: no BRIDGE_LOAD_MS line - the load was not measured')
    else:
        if 'worker_load_s=4.66' not in load_line:
            failures.append(f'ARM L2: the worker own measurement is missing: '
                            f'{load_line!r}')
        if f'pid={child.pid}' not in load_line:
            failures.append(f'ARM L2: BRIDGE_LOAD_MS does not name the pid: '
                            f'{load_line!r}')
    window = b._silence_window()
    if abs(window - SILENCE_MS / 1000.0) > 0.05:
        failures.append(f'ARM L2/window: after the load the window is {window:.3f}s, '
                        f'expected the silence window {SILENCE_MS / 1000.0:.3f}s - the '
                        'load ceiling leaked into the working phase')
    b._arm_silence()
    time.sleep(SILENCE_MS / 1000.0 + 0.35)
    silent = _one(log_lines, 'BRIDGE_SILENT ms=')
    if silent is None:
        failures.append('ARM L2: no BRIDGE_SILENT line after the load - the jam '
                        'watchdog is gone')
    elif f'ms={SILENCE_MS}' not in silent:
        failures.append(f'ARM L2: the post-load window is not the silence window: '
                        f'{silent!r}')
    if not any(p[0] == 'Worker is running but has said nothing' and p[1] == 'error'
               for p in painted):
        failures.append(f'ARM L2: the jam was not painted: {painted!r}')
    if _one(log_lines, 'BRIDGE_RESTART reason=silent') is None:
        failures.append('ARM L2: no BRIDGE_RESTART reason=silent')
    if b.restarts != 1:
        failures.append(f'ARM L2: restarts={b.restarts}, expected 1')
    b.stop('arm-l2')
    report['arm_l2'] = {'shell_load_ms': round(b.load_ms, 1),
                        'window_s': round(window, 3), 'log_tail': log_lines[-4:]}
    return failures


# --------------------------------------------------------------------------
# L4 - the ceiling: a load that never finishes IS restarted, and the panel is
#         told why.
# --------------------------------------------------------------------------

def arm_l4(report):
    """The load window is a ceiling, not an infinite patience.

    Without this, the fix for the cold boot would trade a spurious kill for a
    worker that can hold its caption channel forever: model-loaded never arrives,
    nothing is wrong that a restart would fix, and the panel would sit on
    model-loading for the rest of the session. The owner bound is 180 s.
    """
    failures = []
    log_lines, painted = [], []
    b = _new_bridge(log_lines, painted)
    child = _Child()
    b.child = child
    b.spawned_at = time.monotonic() - (LOAD_SILENCE_MS / 1000.0 + 10.0)
    b._arm_silence()
    time.sleep(1.5)                     # _silence_window floors at 1.0 s
    timeout = _one(log_lines, 'BRIDGE_SILENT_LOAD_TIMEOUT')
    if timeout is None:
        failures.append('ARM L4: no BRIDGE_SILENT_LOAD_TIMEOUT - a load that never '
                        'finishes is not restarted')
    elif 'because=model-never-loaded' not in timeout:
        failures.append(f'ARM L4: the timeout line does not say why: {timeout!r}')
    if not any(p[0] == 'Worker is still loading the model' and p[1] == 'error'
               for p in painted):
        failures.append(f'ARM L4: the timeout was not painted: {painted!r}')
    if not any((p[2] or {}).get('title') == 'Model load timeout' for p in painted):
        failures.append(f'ARM L4: the placeholder title is not "Model load timeout": '
                        f'{painted!r}')
    if _one(log_lines, 'BRIDGE_RESTART reason=load-timeout') is None:
        failures.append('ARM L4: no BRIDGE_RESTART reason=load-timeout')
    if b.restarts != 1:
        failures.append(f'ARM L4: restarts={b.restarts}, expected 1')
    b.stop('arm-l4')
    report['arm_l4'] = {'log_tail': log_lines[-4:]}
    return failures


# --------------------------------------------------------------------------
# NEGATIVE ARMS - two mutants, each SELECTIVE.
# --------------------------------------------------------------------------

def _build_mutant(path, old, new, label):
    """A COPY of TODAY shell with one text block rewritten, never a kept copy.

    A kept copy goes stale the first time anyone touches the shell, and a stale
    negative arm reports on code nobody is running. The block is matched by TEXT
    and COUNTED: if it does not appear exactly once, the arm refuses to run rather
    than guess which site it means.
    """
    with open(SHELL, encoding='utf-8') as f:
        src = f.read()
    n = src.count(old)
    if n != 1:
        return False, (f'{label}: the block appears {n} times in {SHELL} '
                       f'(expected exactly 1)'), {}
    out = src.replace(old, new)
    if out == src:
        return False, f'{label}: the mutant is byte-identical to the source', {}
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    digest = lambda b: hashlib.sha256(b).hexdigest()[:16]
    info = {'mutant': path, 'src_sha16': digest(src.encode('utf-8')),
            'mutant_sha16': digest(out.encode('utf-8'))}
    if info['src_sha16'] == info['mutant_sha16']:
        return False, f'{label}: the mutation did not move the artefact hash', info
    return True, '', info


def _run_unit_against(mutant):
    env = dict(os.environ)
    env['S7_ORACLE_SHELL'] = mutant
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), '--unit'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, cwd=HERE, creationflags=CREATE_NO_WINDOW, timeout=300)
    text = proc.stdout.decode('utf-8', 'replace')
    try:
        return proc.returncode, json.loads(text), text
    except ValueError:
        return proc.returncode, None, text


def neg_arm(report):
    """Each mutant must go red on ITS arm and stay green on the others.

    Mutant 1 (RE-ARM removed): a quiet loading child falls through to the timeout
    and is killed, so L1 goes red. L2 (the jam path) and L4 (the ceiling) are
    untouched by that deletion and must stay green - a mutant that breaks
    everything, or that stays green, is not this lane negative arm.
    Mutant 2 (CEILING removed): the timeout becomes unreachable, so L4 goes red
    while L1 keeps re-arming.
    """
    failures = []

    ok, reason, info = _build_mutant(MUTANT_REARM, REARM_BLOCK, '', 're-arm')
    report['neg_arm_rearm'] = dict(info)
    if not ok:
        return ['NEGATIVE ARM (re-arm): cannot build the mutant: ' + reason]
    rc, child, text = _run_unit_against(MUTANT_REARM)
    report['neg_arm_rearm']['child_rc'] = rc
    child_failures = list((child or {}).get('failures') or [])
    report['neg_arm_rearm']['child_failures'] = child_failures
    if rc == 0:
        failures.append('NEGATIVE ARM (re-arm): the mutant stayed GREEN - a loading '
                        'child is still not killed, so the arm proves nothing')
    if not any(f.startswith('ARM L1') for f in child_failures):
        failures.append('NEGATIVE ARM (re-arm): the mutant went red for the WRONG '
                        f'reason - no ARM L1 failure: {child_failures}')
    for name in ('ARM L2', 'ARM L4', 'ARM S1'):
        if any(f.startswith(name) for f in child_failures):
            failures.append(f'NEGATIVE ARM (re-arm): the mutant also broke {name}, '
                            'which removing the re-arm must NOT touch')

    ok, reason, info = _build_mutant(MUTANT_CEILING, CEILING_LINE, CEILING_MUTANT,
                                     'ceiling')
    report['neg_arm_ceiling'] = dict(info)
    if not ok:
        return failures + ['NEGATIVE ARM (ceiling): cannot build the mutant: '
                           + reason]
    rc, child, text = _run_unit_against(MUTANT_CEILING)
    report['neg_arm_ceiling']['child_rc'] = rc
    child_failures = list((child or {}).get('failures') or [])
    report['neg_arm_ceiling']['child_failures'] = child_failures
    if rc == 0:
        failures.append('NEGATIVE ARM (ceiling): the mutant stayed GREEN - a load '
                        'that never finishes is still not restarted, so the arm '
                        'proves nothing')
    if not any(f.startswith('ARM L4') for f in child_failures):
        failures.append('NEGATIVE ARM (ceiling): the mutant went red for the WRONG '
                        f'reason - no ARM L4 failure: {child_failures}')
    for name in ('ARM L1', 'ARM L2', 'ARM S1'):
        if any(f.startswith(name) for f in child_failures):
            failures.append(f'NEGATIVE ARM (ceiling): the mutant also broke {name}, '
                            'which removing the ceiling must NOT touch')
    return failures


# --------------------------------------------------------------------------

def main() -> int:
    argv = sys.argv[1:]
    report = {}
    failures = []

    if '--unit' in argv or '--neg-arm' not in argv:
        for fn in (arm_s1, arm_l1, arm_l2, arm_l4):
            try:
                failures += fn(report)
            except Exception as exc:  # noqa: BLE001 - an arm that raises is a RED
                failures.append(f'{fn.__name__} raised {exc!r}')

    if '--neg-arm' in argv:
        try:
            failures += neg_arm(report)
        except Exception as exc:  # noqa: BLE001
            failures.append(f'neg_arm raised {exc!r}')

    report['verdict'] = 'PASS' if not failures else 'FAIL'
    report['failures'] = failures
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
