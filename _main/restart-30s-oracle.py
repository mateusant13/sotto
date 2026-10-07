"""Does the shell still KILL a worker whose only periodic signal is its HEARTBEAT?

THE DEFECT (owner card, 2026-10-06T13:47Z; `_main/webview-run.log`, pids 4312
and 47056): the shell called the worker silent every ~30 s and restarted it, so
the ASR model reloaded (~2.4 GB, `rss_mb=2415`) and the hypothesis context was
thrown away, while the worker was demonstrably working — 31 captions in the
killed run, `peak=0.383783` with `nonzero_blocks=92/92`, and the shell itself
lifting its own death state on the next caption (`BRIDGE_DEATH_LIFTED
reason=caption captions=29`).

WHO DECIDES, and WHAT SIGNAL IT EXPECTED (measured, not deduced):

  * `app/webview/sotto_webview.py`, `WorkerBridge._arm_silence()` arms a
    `threading.Timer(self.silence_ms / 1000.0, self._on_silence)`.
  * `_pump` re-arms it for EVERY line read from **stdout**, i.e. on `caption`
    and `status` JSONL. The **stderr** branch `continue`s BEFORE that call
    (sotto_webview.py, the `if name == 'stderr':` arm).
  * `worker/sotto_worker.py` publishes its one PERIODIC signal on STDERR:
    `WORKER_STATS tag=tick … blocks=<N>` every `--stats-interval` (default
    10 s, `worker/sotto_worker.py:1798-1803`), with `blocks` ADVANCING — the
    worker's own proof it is still consuming audio.
  * So the watchdog was armed on CAPTIONS ONLY, against a worker whose real
    cadence of proof is a 10 s heartbeat on the stream it was ignoring. 15 s
    without a caption (`silence_ms` default 15000; NOTE: `in_ms=30000` in the
    owner's log is the RESTART BACKOFF cap, `backoff_max`, not the window)
    killed it and charged a full model reload.

THE CURE UNDER TEST: the heartbeat counts as PROGRESS. `_pump` calls
`_note_progress(parsed)` on a `WORKER_STATS` line, which re-arms the watchdog
when — and only when — `blocks` ADVANCES, and the window is raised to 3x the
heartbeat (`WORKER_SILENCE_MS = 30000`).

ARMS (a green you cannot turn red is not green, so the RED arm is mandatory and
its failure is this oracle's own failure):

  GREEN heartbeat        the measured shape: warm-up, ONE caption, then nothing
                         on stdout while the heartbeat ticks with `blocks`
                         advancing. SAME app.
                         -> respawns == 0, no `BRIDGE_SILENT`, counter advancing
  RED   heartbeat        a COPY of today's shell with exactly ONE line reverted
    (pre-fix copy)       (`self._note_progress(parsed)` -> `pass`), driven by
                         the SAME fixture. -> respawns >= 1, `BRIDGE_RESTART
                         reason=silent`
  ANOMALY wedge          the same shell as GREEN, a fixture that ticks ONCE and
                         then goes mute on BOTH streams -> respawns >= 1. The
                         cure must not have disarmed the watchdog.

The RED copy is built from TODAY's bytes by this oracle; if the revert pattern
is not found, or the copy differs by more than that one line, the run is
REFUSED (rc=2) rather than reported green.

`--field <log>` prints the BEFORE numbers off the owner's own log, in a
declared window, so the before/after pair does not rest on the fixture's clock.

Run: py -3 _main/restart-30s-oracle.py [--json report.json] [--field LOG]
No WebView2, no device, no model, no audio, no window: the only process is the
fixture `_main/_restart-30s-fake-worker.py`, spawned with CREATE_NO_WINDOW by
the shell under test.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
FAKE = os.path.join(HERE, '_restart-30s-fake-worker.py')
MUTANT = os.path.join(HERE, '_restart-30s-prefix-mutant.py')

#: The cure, and the exact one-line revert that reproduces the pre-fix shell.
GUARD = 'self._note_progress(parsed)'
REVERT = 'pass  # NEG-ARM: the pre-fix shell never counted the heartbeat'

SILENCE_MS = 600          # 30 s in the field; 0.6 s is the same decision
TICK_MS = 150             # 10 s in the field; the RATIO (4x) is what is tested
SECONDS = 3.0             # observation window per arm
BACKOFF_BASE = 100
BACKOFF_MAX = 200


def _load_module(path: str, name: str):
    """Import a shell (the live one, or the reverted COPY) from an explicit path."""
    sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_neg_mutant() -> tuple[bool, str]:
    """Rebuild the pre-fix shell from TODAY's bytes, or refuse to run."""
    with open(SHELL, encoding='utf-8') as fh:
        src = fh.read()
    if src.count(GUARD) != 1:
        return False, (f'the cure {GUARD!r} occurs {src.count(GUARD)}x in '
                       f'{SHELL} -- the control cannot be built from these bytes')
    if "self._arm_silence()" not in src:
        return False, 'the watchdog arming is not in the source: wrong subject'
    mutant = src.replace(GUARD, REVERT, 1)
    if mutant == src:
        return False, 'the revert changed nothing -- control is dead'
    old = src.splitlines()
    new = mutant.splitlines()
    if len(old) != len(new):
        return False, f'the revert changed the line count ({len(old)} -> {len(new)})'
    changed = [i for i, (a, b) in enumerate(zip(old, new), 1) if a != b]
    if len(changed) != 1:
        return False, f'the revert moved {len(changed)} lines, expected exactly 1'
    if GUARD not in old[changed[0] - 1]:
        return False, (f'line {changed[0]} is not the cure line: '
                       f'{old[changed[0] - 1]!r}')
    if mutant.count(GUARD) != 0:
        return False, f'{GUARD} is still called after the revert'
    with open(MUTANT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(mutant)
    return True, f'{MUTANT} (line {changed[0]}: {GUARD} -> pass)'


def lines_of(text: str, needle: str) -> list[str]:
    return [ln for ln in text.splitlines() if needle in ln]


def run_arm(mod, mode: str, seconds: float, arm: str) -> dict:
    """Drive the REAL WorkerBridge against the fixture for `seconds`."""
    log_lines: list[str] = []
    painted: list[dict] = []

    def status_stub(text, kind, info):
        info = info or {}
        painted.append({'footer': str(text), 'kind': kind,
                        'title': info.get('title')})

    def caption_stub(text, meta):
        painted.append({'footer': 'Receiving captions', 'kind': 'live',
                        'title': '', 'text': str(text)})

    os.environ['SOTTO_FAKE_MODE'] = mode
    os.environ['SOTTO_FAKE_TICK_MS'] = str(TICK_MS)
    bridge = mod.WorkerBridge(
        command=sys.executable, worker_path=FAKE, log=log_lines.append,
        on_status=status_stub, on_caption=caption_stub,
        silence_ms=SILENCE_MS, backoff_base=BACKOFF_BASE, backoff_max=BACKOFF_MAX)
    if not bridge.start():
        return {'arm': arm, 'mode': mode, 'error': 'bridge.start() refused'}
    # The panel shows a death from the moment the child exits until a caption
    # lifts it (`BRIDGE_DEATH_LIFTED`), so a single reading at t=end can miss
    # the defect entirely. Sample continuously and keep the WORST observed
    # panel state -- that is the state the owner was looking at.
    samples: list[dict] = []
    stop = threading.Event()

    def _sample():
        while not stop.is_set():
            try:
                samples.append(bridge.snapshot())
            except Exception:
                pass
            time.sleep(0.05)

    sampler = threading.Thread(target=_sample, daemon=True)
    sampler.start()
    try:
        time.sleep(seconds)
        stop.set()
        sampler.join(1.0)
        joined = '\n'.join(log_lines)
        worst = None
        for s in samples:
            if (s.get('pendingError') or {}).get('state'):
                worst = s
        final = samples[-1] if samples else bridge.snapshot()
        return {
            'arm': arm,
            'mode': mode,
            'spawns': bridge.spawns,
            'respawns': bridge.spawns - 1,
            'restarts': bridge.restarts,
            'captions': bridge.captions,
            'statuses': bridge.statuses,
            'malformed': bridge.malformed,
            'child_alive': bridge.child is not None,
            'progress_blocks': getattr(bridge, '_progress_blocks', None),
            'silent_kills': len(lines_of(joined, 'BRIDGE_SILENT ms=')),
            'reason_silent_restarts': len(lines_of(
                joined, 'BRIDGE_RESTART reason=silent')),
            'reason_exit_restarts': len(lines_of(
                joined, 'BRIDGE_RESTART reason=exit')),
            'worker_stats_lines': len(lines_of(joined, 'WORKER_STATS')),
            'exit_lines': len(lines_of(joined, 'BRIDGE_EXIT')),
            'bridge_state': worst or final,
            'bridge_state_final': final,
            'pending_error_samples': sum(
                1 for s in samples if (s.get('pendingError') or {}).get('state')),
            'samples': len(samples),
            'last_painted': painted[-1] if painted else None,
            'painted_kinds': [p.get('kind') for p in painted],
        }
    finally:
        stop.set()
        bridge.stop('oracle')
        child = bridge.child
        if child is not None:
            try:
                child.kill()
            except Exception:
                pass


def arm_checks(snapshot: dict) -> tuple[list[str], list[str]]:
    """(failures, notes) for one arm, dispatched on the ARM LABEL."""
    arm = snapshot['arm']
    fails: list[str] = []
    notes = [f"{arm}: spawns={snapshot['spawns']} respawns={snapshot['respawns']} "
             f"silent_kills={snapshot['silent_kills']} "
             f"reason_silent={snapshot['reason_silent_restarts']} "
             f"progress_blocks={snapshot['progress_blocks']} "
             f"captions={snapshot['captions']}"]
    if arm == 'GREEN heartbeat':
        if snapshot['respawns'] != 0:
            fails.append(f"{arm}: the shell RESTARTED a worker whose heartbeat "
                         f"was advancing ({snapshot['respawns']}x)")
        if snapshot['silent_kills'] != 0:
            fails.append(f'{arm}: BRIDGE_SILENT fired on a working worker')
        if snapshot['reason_silent_restarts'] != 0:
            fails.append(f'{arm}: BRIDGE_RESTART reason=silent on a working '
                         'worker')
        if not snapshot['progress_blocks']:
            fails.append(f"{arm}: the heartbeat never reached the watchdog "
                         f"(progress_blocks={snapshot['progress_blocks']!r}) -- "
                         'the arm proves nothing')
        if snapshot['captions'] < 1:
            fails.append(f"{arm}: the fixture's caption never arrived "
                         f"(captions={snapshot['captions']})")
        if snapshot['malformed'] != 0:
            fails.append(f"{arm}: {snapshot['malformed']} malformed line(s)")
        if snapshot.get('pending_error_samples', 0) != 0:
            fails.append(f"{arm}: the panel showed a DEATH for "
                         f"{snapshot['pending_error_samples']} sample(s) while "
                         'the worker was working')
        if 'error' in (snapshot.get('painted_kinds') or []):
            fails.append(f'{arm}: an ERROR status was painted while the worker '
                         'was working')
    elif arm == 'RED heartbeat (pre-fix copy)':
        if snapshot['respawns'] < 1:
            fails.append(f"{arm}: the pre-fix copy did NOT restart a worker "
                         'whose only periodic signal was the heartbeat -- the '
                         'defect did not reproduce, so the green arm proves '
                         'nothing')
        if snapshot['reason_silent_restarts'] < 1:
            fails.append(f'{arm}: no BRIDGE_RESTART reason=silent')
        if snapshot['progress_blocks'] is not None:
            fails.append(f"{arm}: the pre-fix copy counted the heartbeat "
                         f"(progress_blocks={snapshot['progress_blocks']}) -- "
                         'it is not the pre-fix copy')
    elif arm == 'ANOMALY wedge':
        if snapshot['respawns'] < 1:
            fails.append(f'{arm}: the watchdog did NOT restart a worker that '
                         'ticked once and then went mute on BOTH streams -- the '
                         'cure disarmed the watchdog')
        if snapshot['reason_silent_restarts'] < 1:
            fails.append(f'{arm}: no BRIDGE_RESTART reason=silent')
    else:
        fails.append(f'unknown arm {arm!r}: no checks ran')
    return fails, notes


def static_checks(mod) -> tuple[list[str], list[str]]:
    """The numbers live in TWO files; nothing else keeps them in step.

    If someone raises the worker's `--stats-interval` above half the watchdog
    window, the heartbeat can no longer shield the worker and the 2.4 GB churn
    returns with every arm still passing. So the relation is asserted here,
    against the WORKER's source, not against the shell's own constant.
    """
    fails: list[str] = []
    notes: list[str] = []
    with open(WORKER, encoding='utf-8') as fh:
        worker_src = fh.read()
    m = re.search(r'"--stats-interval",\s*type=float,\s*default=([\d.]+)',
                  worker_src)
    if not m:
        fails.append('vocabulary: --stats-interval default not found in '
                     f'{WORKER} -- the heartbeat cadence is unverifiable')
        return fails, notes
    worker_default_s = float(m.group(1))
    notes.append(f'worker --stats-interval default={worker_default_s}s '
                 f'shell WORKER_STATS_INTERVAL_S={mod.WORKER_STATS_INTERVAL_S}s '
                 f'shell WORKER_SILENCE_MS={mod.WORKER_SILENCE_MS}ms')
    if mod.WORKER_STATS_INTERVAL_S != worker_default_s:
        fails.append(f'vocabulary: WORKER_STATS_INTERVAL_S='
                     f'{mod.WORKER_STATS_INTERVAL_S} is not the worker\'s own '
                     f'--stats-interval default ({worker_default_s})')
    if mod.WORKER_SILENCE_MS < 2 * worker_default_s * 1000:
        fails.append(f'relation: WORKER_SILENCE_MS={mod.WORKER_SILENCE_MS}ms is '
                     f'less than 2x the heartbeat '
                     f'({2 * worker_default_s * 1000:.0f}ms) -- a single late '
                     'tick would kill a working worker')
    with open(SHELL, encoding='utf-8') as fh:
        shell_src = fh.read()
    if 'silence_ms=WORKER_SILENCE_MS' not in shell_src:
        fails.append('wiring: WorkerBridge does not default its silence window '
                     'to WORKER_SILENCE_MS')
    if shell_src.count('self._note_progress(parsed)') != 1:
        fails.append('wiring: _note_progress is not called exactly once on the '
                     'stderr heartbeat path')
    if '_progress_blocks = None' not in shell_src:
        fails.append('wiring: _progress_blocks is never reset')
    return fails, notes


def field_numbers(log_path: str) -> dict:
    """The BEFORE numbers, off the owner's own log, in a DECLARED window.

    The log carries no per-line wall clock except the line-commit line
    (`HISTORY_APPEND ... time=HH:MM:SS`, written when a caption is committed to
    history). That is the only clock available, so the window is declared as
    the span of the last N commits and every restart inside that span is
    counted against it.
    """
    with open(log_path, encoding='utf-8', errors='replace') as fh:
        lines = fh.read().splitlines()
    commits = []
    for i, ln in enumerate(lines):
        m = re.search(r'HISTORY_APPEND .* time=(\d\d):(\d\d):(\d\d)', ln)
        if m:
            h, mi, s = (int(x) for x in m.groups())
            commits.append((i, h * 3600 + mi * 60 + s, f'{h:02d}:{mi:02d}:{s:02d}'))
    if len(commits) < 2:
        return {'error': 'fewer than two HISTORY_APPEND commits in the log'}
    tail = commits[-5:]
    lo_i, lo_t, lo_h = tail[0]
    hi_i, hi_t, hi_h = tail[-1]
    elapsed = hi_t - lo_t
    span = lines[lo_i:hi_i + 1]
    silent = sum(1 for ln in span if 'BRIDGE_RESTART reason=silent' in ln)
    exits = sum(1 for ln in span if 'BRIDGE_RESTART reason=exit' in ln)
    spawns = sum(1 for ln in span if 'BRIDGE_SPAWNED' in ln)
    captions = sum(1 for ln in span if 'BRIDGE_CAPTION_SENT' in ln)
    gaps = [b[1] - a[1] for a, b in zip(tail, tail[1:])]
    return {
        'log': log_path,
        'window': {'from': lo_h, 'to': hi_h, 'seconds': elapsed,
                   'declared_as': 'last 5 HISTORY_APPEND commit stamps'},
        'commit_gaps_s': gaps,
        'restart_silent': silent,
        'restart_exit': exits,
        'restarts_per_min': round((silent + exits) / max(elapsed, 1) * 60, 2),
        'silent_per_min': round(silent / max(elapsed, 1) * 60, 2),
        'spawns_in_window': spawns,
        'captions_in_window': captions,
        'whole_file_restart_silent': sum(
            1 for ln in lines if 'BRIDGE_RESTART reason=silent' in ln),
        'whole_file_spawned': sum(1 for ln in lines if 'BRIDGE_SPAWNED' in ln),
    }


def panel_state_pair(mod, green: dict, red: dict) -> tuple[dict, list[str]]:
    """The ACCEPTANCE, composed by the SHIPPED precedence function.

    `SottoShell._named_panel_state(worker, panel_status)` is the function that
    decides `namedState` in `_main/panel-state.json`; `panel_status` is the
    footer the PAGE writes, and `panel.js` writes `Receiving captions` the
    moment a caption commits. No precedence is re-implemented here.
    """
    out: dict = {}
    fails: list[str] = []
    for arm, snapshot in (('GREEN heartbeat', green), ('RED heartbeat (pre-fix copy)', red)):
        worker = snapshot.get('bridge_state') or {}
        out[arm] = {
            'namedState_if_caption_committed':
                mod.SottoShell._named_panel_state(worker, 'Receiving captions'),
            'namedState_with_no_footer':
                mod.SottoShell._named_panel_state(worker, None),
            'pendingError': worker.get('pendingError'),
            'last_painted': snapshot.get('last_painted'),
            'restarts': snapshot.get('restarts'),
        }
    g = out['GREEN heartbeat']
    r = out['RED heartbeat (pre-fix copy)']
    if g['namedState_if_caption_committed'] == 'exit':
        fails.append('panel-state: GREEN namedState is "exit" while captions '
                     'are arriving -- the acceptance is not met')
    if g['pendingError']:
        fails.append(f"panel-state: GREEN carries pendingError="
                     f"{g['pendingError']!r}")
    if (g['last_painted'] or {}).get('kind') == 'error':
        fails.append(f"panel-state: GREEN painted an ERROR status: "
                     f"{g['last_painted']!r}")
    if r['namedState_with_no_footer'] != 'exit':
        fails.append(f"panel-state: the pre-fix copy does NOT end at "
                     f"namedState='exit' (got "
                     f"{r['namedState_with_no_footer']!r}) -- the red arm is "
                     'not the recorded defect')
    return out, fails


def main() -> int:
    argv = sys.argv[1:]
    report: dict = {'shell': SHELL, 'fixture': FAKE, 'silence_ms': SILENCE_MS,
                    'tick_ms': TICK_MS, 'seconds': SECONDS, 'arms': {},
                    'static': {}}

    field_log = None
    out_path = None
    if '--field' in argv:
        field_log = argv[argv.index('--field') + 1]
    if '--json' in argv:
        out_path = argv[argv.index('--json') + 1]

    if field_log:
        report['field'] = field_numbers(field_log)
        print(json.dumps(report['field'], indent=2, ensure_ascii=False))

    if os.environ.get('RESTART30S_FIELD_ONLY') == '1' and field_log:
        if out_path:
            with open(out_path, 'w', encoding='utf-8') as fh:
                json.dump(report, fh, indent=2, ensure_ascii=False)
        return 0

    if '--selftest' in argv:
        # A green that cannot be turned red is not a green. Run the GREEN arm's
        # OWN checks against the pre-fix COPY: if they pass there too, they are
        # not measuring the cure.
        ok, detail = build_neg_mutant()
        print(f'selftest: {detail}')
        if not ok:
            return 2
        mutant = _load_module(MUTANT, 'sotto_shell_prefix_selftest')
        snapshot = run_arm(mutant, 'heartbeat', SECONDS, 'GREEN heartbeat')
        fails, notes = arm_checks(snapshot)
        for n in notes:
            print(n)
        for f in fails:
            print(f'  selftest FAIL (expected) {f}')
        if not fails:
            print('selftest: RED NOT DETECTED -- the GREEN checks pass against '
                  'the pre-fix shell, so they measure nothing. rc=3')
            return 3
        print(f'selftest: rc=0 -- the GREEN checks went RED on the pre-fix copy '
              f'({len(fails)} failure(s))')
        return 0

    fixed_src = open(SHELL, encoding='utf-8').read()
    ok, detail = build_neg_mutant()
    report['neg_arm'] = {'built': ok, 'detail': detail}
    if not ok:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f'VERDICT: REFUSED -- the control could not be built: {detail}')
        return 2

    fixed = _load_module(SHELL, 'sotto_shell_fixed')
    mutant = _load_module(MUTANT, 'sotto_shell_prefix')
    assert open(SHELL, encoding='utf-8').read() == fixed_src, SHELL + ' moved'

    s_fails, s_notes = static_checks(fixed)
    report['static'] = {'failures': s_fails, 'notes': s_notes}

    plan = [
        ('GREEN heartbeat', fixed, 'heartbeat'),
        ('RED heartbeat (pre-fix copy)', mutant, 'heartbeat'),
        ('ANOMALY wedge', fixed, 'wedge'),
    ]
    failures: list[str] = []
    for arm, mod, mode in plan:
        snapshot = run_arm(mod, mode, SECONDS, arm)
        report['arms'][arm] = snapshot
        if 'error' in snapshot:
            failures.append(f"{arm}: {snapshot['error']}")
            continue
        fails, notes = arm_checks(snapshot)
        failures.extend(fails)
        report['arms'][arm]['failures'] = fails
        for n in notes + [f'  FAIL {f}' for f in fails]:
            print(n)

    failures.extend(f'static: {f}' for f in s_fails)
    for n in s_notes:
        print(f'static: {n}')

    if 'GREEN heartbeat' in report['arms'] and \
            'RED heartbeat (pre-fix copy)' in report['arms']:
        pair, p_fails = panel_state_pair(
            fixed, report['arms']['GREEN heartbeat'],
            report['arms']['RED heartbeat (pre-fix copy)'])
        report['panel_state'] = pair
        failures.extend(p_fails)
        for arm, row in pair.items():
            print(f"panel-state {arm}: namedState(live)="
                  f"{row['namedState_if_caption_committed']!r} "
                  f"namedState(no footer)={row['namedState_with_no_footer']!r} "
                  f"pendingError={(row['pendingError'] or {}).get('state')!r} "
                  f"last_painted={row['last_painted']}")

    report['failures'] = failures
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f'report -> {out_path}')
    if failures:
        print('\nVERDICT: RED')
        for f in failures:
            print(f'  - {f}')
        return 1
    print('\nVERDICT: GREEN -- heartbeat counts as progress (0 restarts); the '
          'pre-fix copy still loops; a wedged worker is still restarted.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
