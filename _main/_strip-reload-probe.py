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

WHAT THIS PROBE IS CALIBRATED TO, AND WHAT IT DOES WHEN THE SHELL LACKS IT.
Every arm above reads a surface of `WorkerReloadPolicy` / `WorkerBridge` /
`SottoShell`: `max_defer_ms` and `defer_recheck_ms` (the CEILING on a held
reload and its recheck timer), `policy.state()` (the staleness QUERY), a closed-line
boundary, and a meter/stats path. Those are read from the LIVE objects, never
assumed from a docstring or a line number written down earlier. A keyword the
live `__init__` accepts is forwarded UNCHANGED; one it does not accept is recorded
in `report["mapping"]` as UNMAPPED with the live signature as its evidence, and the
arm that needed it fails RED with that evidence attached. Nothing is invented,
and no missing rule is renamed onto a different one: a CEILING is not a FLOOR
(`min_interval_ms` bounds the reload RATE, counted from the initial load -- the
opposite direction), and `on_stats`/`on_meter` are not `on_status`/`on_caption`. A probe that
guessed its way to GREEN would be the defect this lane exists to kill.

    pythonw.exe _main/_strip-reload-probe.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
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


# ── THE MAPPING ─────────────────────────────────────────────────────────────
# Every arm below was written against a RICHER policy / bridge / shell than the
# one this repo carries today. The live signature is READ, never assumed: a
# keyword it accepts is forwarded UNCHANGED, and a keyword it does not accept is
# recorded as UNMAPPED with the live signature as its evidence -- never
# invented, never renamed onto a different rule, never silently dropped. The
# arms that needed the missing rule then fail RED with that evidence attached.
MAPPING = {}
SURFACES = {}


def sha256(path):
    """The file's own bytes, or None when it cannot be read."""
    try:
        digest = hashlib.sha256()
        with open(path, 'rb') as fh:
            for block in iter(lambda: fh.read(1 << 20), b''):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def where(obj, label=None):
    """file:line (+ the file's sha256) of a LIVE object, read from the object."""
    name = label or getattr(obj, '__name__', type(obj).__name__)
    try:
        path = inspect.getsourcefile(obj) or SHELL
        line = inspect.getsourcelines(obj)[1]
    except (OSError, TypeError) as exc:
        return {'file': os.path.basename(SHELL), 'line': None, 'name': name,
                'error': f'{type(exc).__name__}: {exc}'}
    return {'file': os.path.basename(path), 'line': line, 'name': name,
            'sha256': sha256(path)}


class Absent:
    """A surface the LOADED shell does not carry. Evidence, never a value.

    Falsy, empty, unindexable, uncallable and unequal to everything, so a check
    written for the real thing turns RED -- the honest answer -- instead of
    raising a TypeError or passing on a number nobody measured.
    """

    def __init__(self, what, evidence):
        object.__setattr__(self, 'what', what)
        object.__setattr__(self, 'evidence', evidence)

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __iter__(self):
        return iter(())

    def __contains__(self, _item):
        return False

    def __getitem__(self, _key):
        return self

    def __getattr__(self, name):
        return Absent(f'{self.what}.{name}', self.evidence)

    def __call__(self, *_args, **_kwargs):
        return self

    def __eq__(self, _other):
        return False

    def __ne__(self, _other):
        return True

    def __hash__(self):
        return hash(('absent', self.what))

    def __repr__(self):
        return f'ABSENT({self.what})'


def jsonable(value):
    """Report-ready: an `Absent` becomes its evidence, and anything json cannot
    hold becomes its repr -- the report must never fail to write."""
    if isinstance(value, Absent):
        return {'absent': value.what, 'evidence': value.evidence}
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return repr(value)
    return value


def safe(value):
    """A json-holdable stand-in for a value that is not one (callables)."""
    if isinstance(value, Absent):
        return f'ABSENT({value.what})'
    if callable(value):
        return 'callable:' + getattr(value, '__name__', type(value).__name__)
    return value


def surface_evidence(key, why=None, error=None):
    """Where a surface the arms read lives -- or why the loaded shell has none."""
    row = dict(SURFACES.get(key) or {'surface': key})
    if why:
        row['why'] = why
    if error:
        row['error'] = error
    return row


def absent(key, why=None, error=None):
    """An `Absent` carrying the evidence for one missing surface."""
    return Absent((SURFACES.get(key) or {}).get('name', key),
                  surface_evidence(key, why, error))


def attr(obj, field, key=None):
    """A live attribute read, or `Absent` with the evidence when it is missing."""
    try:
        return getattr(obj, field)
    except Exception as exc:
        return absent(key or field, error=f'{type(exc).__name__}: {exc}')


def real(fn, key):
    """A live call, or `Absent` when the loaded object has no such callable."""
    try:
        value = fn()
    except Exception as exc:
        return absent(key, error=f'{type(exc).__name__}: {exc}')
    if value is None:
        return absent(key, why='the live call returned None')
    return value


def as_int(value):
    """A real number, or None -- a count nobody measured is not zero."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def bridge_meters(harness):
    """`WorkerBridge.meters` as a number, or 0 when the bridge has no count."""
    return as_int(attr(harness.bridge, 'meters')) or 0


def meter_pushes(harness):
    """The meter push count -- ABSENT when the shell carries no meter path.

    The probe seeds this counter on the shell instance, and on a shell with no
    `on_worker_meter` nothing can ever increment it: 0 == 0 would read as a green
    that measured nothing. The HANDLER is what makes the number mean something,
    so its absence is reported instead of the zero.
    """
    if getattr(harness.module.SottoShell, 'on_worker_meter', None) is None:
        return absent('meter_pushes',
                      why='SottoShell.on_worker_meter is absent, so the meter '
                          'push counter can never leave its seeded 0')
    return attr(harness.shell, 'meter_pushes', 'meter_pushes')


def policy_state(harness):
    """`WorkerReloadPolicy.state()` -- the live answer, or an Absent surface."""
    return real(lambda: harness.policy.state(), 'state')


def shell_stats(harness):
    """`SottoShell.stats()` -- the live answer, or an Absent surface."""
    return real(lambda: harness.shell.stats(), 'stats')


def map_kwargs(cls, want, key):
    """Route every requested keyword onto the LIVE `__init__` signature.

    `want` is what the arm asks for; the live signature decides what is real. An
    accepted keyword is forwarded UNCHANGED. An unaccepted one is recorded as
    UNMAPPED with the live signature as its evidence and is NOT forwarded --
    `max_defer_ms` is a CEILING (force a held reload after N ms with no boundary)
    and `min_interval_ms` is a FLOOR (bound the reload RATE, counted from the
    initial load): the opposite direction, never a substitute.
    """
    row = {'want': {k: safe(v) for k, v in want.items()},
           'at': SURFACES.get(key, {})}
    try:
        sig = inspect.signature(cls.__init__)
        row['signature'] = f'{cls.__name__}{sig}'
        row['parameters'] = [n for n in sig.parameters if n != 'self']
        row['var_keyword'] = any(p.kind is inspect.Parameter.VAR_KEYWORD
                                 for p in sig.parameters.values())
    except (TypeError, ValueError) as exc:
        row.update(signature=f'unreadable ({type(exc).__name__}: {exc})',
                   parameters=[], var_keyword=False)
    accepted, unmapped = {}, []
    for name, value in want.items():
        if name in row['parameters'] or row['var_keyword']:
            accepted[name] = value
            continue
        unmapped.append({'name': name, 'wanted': safe(value),
                         'why': f'not a parameter of the live {row["signature"]}',
                         'surface': SURFACES.get(name, {})})
    row['accepted'] = {k: safe(v) for k, v in accepted.items()}
    row['unmapped'] = unmapped
    MAPPING[key] = row
    return accepted


def build_policy(module, harness, want):
    """The REAL policy, built with only what the REAL signature accepts."""
    cls = module.WorkerReloadPolicy
    accepted = map_kwargs(cls, want, 'policy.__init__')
    policy = cls(log_fn=harness.log, get_bridge=lambda: harness.bridge,
                 restart=harness.restart, **accepted)
    MAPPING['policy.__init__']['constructed'] = (
        f'{cls.__name__}(log_fn=..., get_bridge=..., restart=..., '
        f'**{sorted(accepted)})')
    return policy


def build_bridge(module, harness, reason):
    """The REAL bridge, with the callback slots the LIVE signature declares.

    `on_stats`/`on_meter` are slots this shell's `WorkerBridge.__init__` does not
    declare: they are recorded as UNMAPPED instead of raising, and the slots it
    DOES declare are wired to the REAL shell methods.
    """
    cls = module.WorkerBridge
    want = {'command': PYW, 'worker_path': harness.worker_path,
            'on_caption': harness.shell.on_worker_caption,
            'on_status': harness.shell.on_worker_status,
            'on_stats': getattr(harness.shell, 'on_worker_stats', None),
            'on_meter': getattr(harness.shell, 'on_worker_meter', None),
            'log': harness.log}
    accepted = map_kwargs(cls, want, 'bridge.__init__')
    row = MAPPING['bridge.__init__']
    row['handler_absent'] = [s for s in ('on_stats', 'on_meter')
                             if want.get(s) is None]
    row['dropped'] = [s for s in ('on_stats', 'on_meter')
                      if s in accepted and accepted[s] is None]
    for slot in row['dropped']:
        accepted.pop(slot)
    row['constructed'] = f'{cls.__name__}(**{sorted(accepted)}) reason={reason}'
    return cls(**accepted)


def note_vacuous(what, why):
    """A check that passed while the surface it measures is ABSENT.

    The green is real but it measures nothing -- it is labelled here and printed
    as VACUOUS in the run output, never counted silently as a green.
    """
    report.setdefault('vacuous', []).append({'check': what, 'why': why})


def survey(module):
    """Where each surface the arms read lives in the shell ACTUALLY loaded.

    EVERY row is measured against the live module at run time: the first group
    locates the object (file:line + the file sha256), the second group MEASURES
    whether the member or the log line exists and reports it as
    present_in_loaded_shell. Nothing here is assumed from a docstring or a line
    number written down earlier -- the rows that used to ASSERT absence (they
    said "the live shell has no stats() reading" while stats() was right there)
    are now evidence, and the why text is carried only when the thing is really
    absent.
    """
    SURFACES.clear()
    for key, label, obj in (
            ('policy', 'WorkerReloadPolicy (the class the arms drive)',
             module.WorkerReloadPolicy),
            ('policy.__init__', 'WorkerReloadPolicy.__init__ (the keywords)',
             module.WorkerReloadPolicy.__init__),
            ('boundary', 'WorkerReloadPolicy.boundary (the boundary signal)',
             module.WorkerReloadPolicy.boundary),
            ('fire', 'WorkerReloadPolicy._fire (where a hold is decided)',
             module.WorkerReloadPolicy._fire),
            ('bridge.__init__', 'WorkerBridge.__init__ (the callback slots)',
             module.WorkerBridge.__init__),
            ('on_worker_caption', 'SottoShell.on_worker_caption (the closed line)',
             module.SottoShell.on_worker_caption),
            ('on_worker_status', 'SottoShell.on_worker_status (the status boundary)',
             module.SottoShell.on_worker_status)):
        SURFACES[key] = dict(where(obj, label), surface=key)
    def _attr(owner, attr):
        return getattr(getattr(module, owner, None), attr, None)

    def _srcline(text):
        """file:line (+ sha256) of the FIRST module line carrying `text`, or None."""
        try:
            src_lines, start = inspect.getsourcelines(module)
        except OSError:
            return None
        for offset, line in enumerate(src_lines):
            if text in line:
                return {'file': os.path.basename(SHELL), 'line': start + offset,
                        'name': text, 'sha256': sha256(SHELL)}
        return None

    for key, label, find, why in (
            ('state', 'WorkerReloadPolicy.state()',
             lambda: _attr('WorkerReloadPolicy', 'state'),
             'the staleness QUERY (stale/disk/loaded + pending_ms) is not a '
             'method of the live policy; arms A and B read it'),
            ('max_defer_ms', 'WorkerReloadPolicy.max_defer_ms',
             lambda: _attr('WorkerReloadPolicy', 'max_defer_ms'),
             'the CEILING on a held reload is not a policy parameter; arm D '
             'needs it and arm A asserts it'),
            ('defer_recheck_ms', 'WorkerReloadPolicy.defer_recheck_ms',
             lambda: _attr('WorkerReloadPolicy', 'defer_recheck_ms'),
             'the guard has no recheck timer: _fire returns WITHOUT re-arming '
             'while the child is capturing, so a held reload waits for a '
             'boundary that may never come'),
            ('boundary_closed',
             'boundary(closed=True) / HOT_RELOAD_WORKER_BOUNDARY',
             lambda: _srcline('HOT_RELOAD_WORKER_BOUNDARY'),
             'the live boundary() takes no argument and the shell emits no '
             'HOT_RELOAD_WORKER_BOUNDARY line; arm C needs the closed-line '
             'boundary, and on_worker_caption does not call it'),
            ('forced', 'HOT_RELOAD_WORKER_FORCED',
             lambda: _srcline('HOT_RELOAD_WORKER_FORCED'),
             'no forced-apply line exists; arm D needs it'),
            ('meters', 'WorkerBridge.meters',
             lambda: _attr('WorkerBridge', 'meters'),
             'the live bridge counts no meter frames; a meter line reaches the '
             'unknown-kind branch and is logged as BRIDGE_UNKNOWN'),
            ('meter_pushes', 'SottoShell.meter_pushes',
             lambda: _srcline('meter_pushes'),
             'the live shell has no meter push path'),
            ('stats', 'SottoShell.stats()',
             lambda: _attr('SottoShell', 'stats'),
             'the live shell has no stats() reading'),
            ('on_worker_meter', 'SottoShell.on_worker_meter',
             lambda: _attr('SottoShell', 'on_worker_meter'),
             'the live shell has no meter handler'),
            ('on_worker_stats', 'SottoShell.on_worker_stats',
             lambda: _attr('SottoShell', 'on_worker_stats'),
             'the live shell has no stats handler')):
        found = find()
        if found:
            row = dict(found if isinstance(found, dict) else where(found, label))
            row.update({'surface': key, 'present_in_loaded_shell': True,
                        'why': ('PRESENT in the loaded shell at this run: this row '
                                'is a MEASUREMENT, not an assertion of absence')})
        else:
            row = {'surface': key, 'name': label,
                   'searched': 'the loaded shell module, at run time',
                   'present_in_loaded_shell': False, 'why': why}
        SURFACES[key] = row
    return SURFACES


class Harness:
    """A REAL bridge on a REAL child, with the REAL shell methods wired to it.

    `SottoShell.__new__` is used deliberately: the production METHODS are what is
    under test, and only the seams that need a live WebView2 (`emit`,
    `emit_async`, and the window) are stood in for.

    WHICH production methods those are is READ FROM THE LOADED SHELL, not
    assumed: `on_worker_caption` and `on_worker_status` exist and stay real, and
    a method this shell does not carry (`on_worker_meter`, `on_worker_stats`,
    `stats()`) is reported ABSENT in the SURFACE table instead of being faked
    here -- a stand-in handler would let an arm pass on a path the app does not
    have.
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
        # The REAL policy, built from the REAL signature: every keyword the arm
        # asked for is either forwarded unchanged or recorded as UNMAPPED (see
        # build_policy / map_kwargs). Nothing is invented here.
        self.policy = build_policy(module, self, policy_kwargs)
        self.shell._reload_policy = self.policy
        self.restarts = []
        self.saved_env = {}
        self.env = env or {}

    def log(self, line):
        self.lines.append(str(line))

    def start(self):
        module = self.module
        self.bridge = build_bridge(self.module, self, 'reload-probe')
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
        self.bridge = build_bridge(self.module, self, 'reload-probe-restart')
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
    state0 = policy_state(harness)
    harness.policy.request([copy])
    wait_for(lambda: harness.has('HOT_RELOAD_WORKER_DEFERRED'), 4)
    deferred = harness.has('HOT_RELOAD_WORKER_DEFERRED')
    line = deferred[0] if deferred else ''
    held_state = policy_state(harness)
    report['arms']['A_held'] = {
        'capturing': capturing, 'pid_before': pid0, 'pid_after': harness.pid(),
        'restarts': len(harness.restarts), 'deferred_line': line,
        'pending_ms': held_state['pending_ms'],
        'stale_before_edit': state0['worker']['stale'],
        # The policy's own record of the hold, plus the fields the arms read
        # that the LOADED shell may not carry at all.
        'policy_lines': harness.has('HOT_RELOAD_WORKER_'),
        'policy_pending': attr(harness.policy, 'pending'),
        'max_defer_ms': attr(harness.policy, 'max_defer_ms'),
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
          attr(harness.policy, 'max_defer_ms') == 600000
          and held_state['pending_ms'] is not None)

    # ── B. the staleness query, both colours, on the SAME bridge ────────────
    # The probe's OWN hashes of the very file the child loaded, taken either
    # side of the edit: the same two numbers state() is asked to publish, so the
    # report carries the measurement even when the query is absent.
    sha_before_edit = sha256(copy)
    before = policy_state(harness)['worker']
    with open(copy, 'a', encoding='utf-8') as fh:
        fh.write('\n# one byte more\n')
    sha_after_edit = sha256(copy)
    after = policy_state(harness)['worker']
    report['arms']['B_staleness'] = {
        'before': before, 'after': after,
        'probe_sha256_before_edit': sha_before_edit,
        'probe_sha256_after_edit': sha_after_edit,
        'probe_bytes': os.path.getsize(copy),
        'probe_changed': sha_before_edit != sha_after_edit,
    }
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
        # What the REAL shell emitted around the boundary, so the report carries
        # the measurement even where the closed-line rule is absent.
        'policy_lines': harness.has('HOT_RELOAD_WORKER_'),
        'caption_lines': len(harness.has('BRIDGE_CAPTION_SENT')),
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
        'policy_pending': attr(harness.policy, 'pending'),
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
        'policy_lines': harness.has('HOT_RELOAD_WORKER_'),
        'pending': attr(harness.policy, 'pending'),
    }
    if getattr(module.WorkerReloadPolicy, 'max_defer_ms', None) is None:
        # The reload really is still held -- but nothing here can attribute that
        # to the FLOOR: with no ceiling in the shell, the capturing GUARD is
        # what is holding it, and the floor was never reached. The green is real
        # and its CLAIM is not, so it is labelled.
        note_vacuous("E: the owner's floor bounds the RATE even after the ceiling",
                     'the shell carries no ceiling to survive: the request is '
                     'still held by the capturing GUARD, so the floor is not '
                     'what bounded it')
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
    # Every read below goes through the LIVE surface: a count the loaded bridge
    # does not keep comes back as 0 and a reading the loaded shell cannot give
    # comes back ABSENT, so these checks answer RED with the evidence attached
    # rather than raising a TypeError.
    wait_for(lambda: bridge_meters(harness) >= 40, 8)
    time.sleep(0.4)
    peaks = [p.get('peak') for k, p in harness.emitted
             if k == 'stats' and isinstance(p, dict)]
    distinct = sorted({p for p in peaks if p is not None})
    meters = bridge_meters(harness)
    pushes = meter_pushes(harness)
    stats_now = shell_stats(harness)
    stats_peak = stats_now.get('peak') if isinstance(stats_now, dict) else None
    report['arms']['F_wave'] = {
        'meters': meters,
        'meter_pushes': pushes,
        'distinct_peaks': distinct,
        'stats_now': stats_now,
        'stats_peak': stats_peak,
        'meter_log_lines': len(harness.has('BRIDGE_METER ')),
        'unknown_lines': len(harness.has('BRIDGE_UNKNOWN')),
        'stderr_peak': '0.443448',
    }
    check('F: the meter events arrive at the worker\'s own cadence',
          meters >= 40, {'meters': meters})
    check('F: every meter event was PUSHED to the page (no throttling of data)',
          pushes == meters,
          {'pushed': safe(pushes), 'meters': meters})
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
          and stats_peak != 0.443448,
          {'live_distinct': live_distinct, 'warmup': warmup,
           'stats_now': stats_now})
    check('F: `stats()` agrees with the pushed payload (one shape, one value)',
          stats_peak in live_distinct and 'blocks' in stats_now,
          stats_now)
    meter_lines = len(harness.has('BRIDGE_METER '))
    if not harness.has('BRIDGE_METER ') and meters == 0:
        # The budget below is met by a log that never grew because the meter
        # path does not exist. The green is real and it measures NOTHING: it is
        # labelled here and printed as VACUOUS, never counted as a green.
        note_vacuous('F: the log grew by ONE line, not one per sample',
                     'no BRIDGE_METER line exists on this shell and the bridge '
                     'counts no meter frames, so the one-line budget is met '
                     'vacuously')
    check('F: the log grew by ONE line, not one per sample',
          meter_lines <= 2, {'lines': meter_lines})
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
    stats_now = shell_stats(harness)
    report['arms']['F_wave_nometer'] = {
        'meters': bridge_meters(harness),
        'meter_pushes': meter_pushes(harness),
        'stats': stats_now,
        # The stderr running maximum DOES arrive on this shell -- it is the
        # fallback the arm is about, and it is measured here even where stats()
        # is absent.
        'last_worker_stats': attr(harness.bridge, 'last_worker_stats'),
    }
    check('F(no meter): no meter push happens, and the fallback is the stats line',
          bridge_meters(harness) == 0
          and meter_pushes(harness) == 0
          and (stats_now.get('peak') if isinstance(stats_now, dict) else None)
          == 0.443448,
          report['arms']['F_wave_nometer'])
    harness.close()


def main():
    module = load(SHELL, 'sotto_reload_probe_shell')
    # FIRST: where every surface the arms read actually lives in THIS shell, read
    # from the loaded module -- so the report says which rule is missing before
    # an arm fails on it.
    report['surface'] = survey(module)
    tmp = tempfile.mkdtemp(prefix='sotto-reload-probe-')
    try:
        arm_a_and_b(module, tmp)
        arm_c(module)
        arm_d_and_e(module)
        arm_f(module)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    report['mapping'] = MAPPING
    report['vacuous'] = report.get('vacuous', [])
    report['shell_sha256'] = sha256(SHELL)
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
        json.dump(jsonable(report), fh, indent=1, sort_keys=True)
    print(f'VERDICT: {report["verdict"]}')
    print(f'SHELL: {os.path.basename(SHELL)} sha256={sha256(SHELL)}')
    for row in report['checks']:
        print(('ok   ' if row['ok'] else 'FAIL ') + row['what'])
    print('')
    print('SURFACE -- where each thing the arms read lives in the shell LOADED')
    for key in sorted(report.get('surface') or {}):
        row = report['surface'][key]
        at = (f'{row.get("file")}:{row.get("line")}' if row.get('line')
              else 'ABSENT')
        print(f'  {key:18} {at:32} {row.get("name") or ""}')
        if row.get('why'):
            print(f'  {"":18} why: {row["why"]}')
    print('')
    print('MAPPING -- every keyword an arm asked for, against the LIVE signature')
    for key in sorted(report.get('mapping') or {}):
        row = report['mapping'][key]
        print(f'  {key}: {row.get("signature")}')
        print(f'    parameters : {", ".join(row.get("parameters") or [])}')
        print(f'    accepted   : {json.dumps(row.get("accepted"))}')
        for item in row.get('unmapped') or []:
            print(f'    UNMAPPED   : {item["name"]}={item["wanted"]}'
                  f' -- {item["why"]}')
        if row.get('constructed'):
            print(f'    constructed: {row["constructed"]}')
    for row in report.get('vacuous') or []:
        print(f'VACUOUS: {row["check"]} -- {row["why"]}')
    if report.get('traceback'):
        print(report['traceback'])
    sys.exit(code)
