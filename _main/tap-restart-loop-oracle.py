"""Does the shell still KILL a worker that is quiet because the MACHINE is quiet?

The defect (owner card, measured): `sotto_webview.py` kills and respawns the
worker 15 s after the last CAPTION. An IDLE DESKTOP produces digital silence BY
DESIGN -- this repo's own idle-floor probe measured `peak=0.000000` over three
independent 6 s captures of the default render endpoint's loopback
(`_main/sdr_idlefloor.out`) -- so no caption can EVER arrive to lift the timer.
The loop cannot converge, and every respawn reloads a ~2.4 GB model.

MEASURED BEFORE (`_main/_live_owner3.log`, one live run on this box):
`BRIDGE_SILENT` x9 with `spawns=55` across the file, and in the single log the
owner's card cites: 24 `device-rotated (flat)`, 8 `BRIDGE_SILENT`, `spawns=10`.

CHANGE UNDER TEST: `_on_silence` now reads the WORKER'S OWN VERDICT about the
audio (`WORKER_NO_AUDIO_STATES` / `WORKER_NO_AUDIO_VERDICTS`, plus the ladder's
per-candidate `device-rotated reason=flat` row, which is what an idle desktop
produces). Verdict present -> the silence is the CORRECT behaviour of a quiet
machine: name the state (`no-audio`), DO NOT kill, re-arm the timer. No verdict
-> the watchdog still fires and still restarts.

ARMS (a green you cannot turn red is not green, so the RED arm is mandatory and
its failure is the oracle's own failure):

  GREEN idle            the idle-desktop transcript, child alive + quiet
                        -> respawns == 0, `no-audio` painted, no silent restart
  GREEN verdict-quiet   the same plus the worker's real TERMINAL verdict lines
                        -> respawns == 0, `no-audio` painted
  ANOMALY no-verdict    the stream opens and nothing follows, ever
                        -> respawns >= 1 and BRIDGE_RESTART reason=silent
  ANOMALY signal-quiet  a caption came out and then the child went mute
                        -> respawns >= 1 (the tap declared signal, then stopped)
  RED idle (pre-fix)    a COPY of today's shell with the verdict guard disabled
                        -> respawns >= 2 and `no-audio` NEVER painted

The RED copy is built from TODAY's bytes by the oracle itself; if the revert
pattern is not found the run is REFUSED (rc=2) rather than reported green.

Run: py -3 _main/tap-restart-loop-oracle.py [--json report.json]
No WebView2, no device, no model, no audio: the only process is the fixture
`_main/_tap-restart-fake-worker.py`, spawned with CREATE_NO_WINDOW by the shell
under test, so no window can appear.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
FAKE = os.path.join(HERE, '_tap-restart-fake-worker.py')
MUTANT = os.path.join(HERE, '_tap-restart-prefix-mutant.py')

#: The guard under test, and the exact revert that reproduces the pre-fix shell.
#: Two-line form: a second `if self.no_audio:` exists in `_consume` (the
#: caption-lift, 2026-10-08), so the bare one-liner matches 2x and the control
#: cannot be built from it. The `# BENIGN` comment is unique to `_on_silence`.
#: Single-line revert (no newline): the control must change exactly one line.
GUARD = 'if self.no_audio:  # __TAP_RESTART_GUARD__'
REVERT = 'if False:  # NEG-ARM: the pre-fix shell killed on silence, unconditionally'

SILENCE_MS = 600          # 15 s in the field; 0.6 s is the same decision
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
    """Rebuild the pre-fix shell from TODAY's bytes, or refuse to run.

    Returns (ok, detail). The control is only a control if it differs from the
    live shell by EXACTLY the guard, so the difference is counted, not assumed.
    """
    with open(SHELL, encoding='utf-8') as fh:
        src = fh.read()
    if src.count(GUARD) != 1:
        return False, (f'the guard {GUARD!r} occurs {src.count(GUARD)}x in '
                       f'{SHELL} -- the control cannot be built from these bytes')
    if "_kill_and_restart('silent')" not in src:
        return False, 'the pre-fix kill is not in the source: wrong subject'
    mutant = src.replace(GUARD, REVERT, 1)
    if mutant == src:
        return False, 'the revert changed nothing -- control is dead'
    # FIDELITY, counted: one line removed, one line added, nothing else moved.
    old = src.splitlines()
    new = mutant.splitlines()
    if len(old) != len(new):
        return False, f'the revert changed the line count ({len(old)} -> {len(new)})'
    changed = [i for i, (a, b) in enumerate(zip(old, new), 1) if a != b]
    if len(changed) != 1:
        return False, f'the revert moved {len(changed)} lines, expected exactly 1'
    if GUARD not in old[changed[0] - 1]:
        return False, (f'line {changed[0]} is not the guard line: '
                       f'{old[changed[0] - 1]!r}')
    with open(MUTANT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(mutant)
    return True, f'{MUTANT} (line {changed[0]}: {GUARD} -> {REVERT})'


def lines_of(text: str, needle: str) -> list[str]:
    return [ln for ln in text.splitlines() if needle in ln]


def run_arm(mod, mode: str, seconds: float, arm: str, mutate=None) -> dict:
    """Drive the REAL WorkerBridge against the fixture worker for `seconds`.

    `arm` is the LABEL the checks dispatch on; `mode` is what the fixture child
    is told to write. They differ for the RED arm, which runs the SAME fixture
    (`idle`) through the pre-fix copy and must be judged as the pre-fix copy.
    `mutate(bridge)` runs once after `start()`, for state the fixture cannot
    produce on its own (the death already on screen).
    """
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
    bridge = mod.WorkerBridge(
        command=sys.executable, worker_path=FAKE, log=log_lines.append,
        on_status=status_stub, on_caption=caption_stub,
        silence_ms=SILENCE_MS, backoff_base=BACKOFF_BASE, backoff_max=BACKOFF_MAX)
    started = bridge.start()
    if not started:
        return {'arm': arm, 'mode': mode, 'error': 'bridge.start() refused'}
    if mutate is not None:
        mutate(bridge)
    try:
        time.sleep(seconds)
        joined = '\n'.join(log_lines)
        snapshot = {
            'arm': arm,
            'mode': mode,
            'spawns': bridge.spawns,
            'respawns': bridge.spawns - 1,
            'restarts': bridge.restarts,
            'captions': bridge.captions,
            'statuses': bridge.statuses,
            'state': bridge.state,
            'no_audio_flag': bool(getattr(bridge, 'no_audio', False)),
            'no_audio_evidence': getattr(bridge, 'no_audio_evidence', None),
            'named_no_audio_painted': any(
                p.get('title') == 'No audio to transcribe' for p in painted),
            'silent_greens': len(lines_of(joined, 'BRIDGE_SILENT_BENIGN')),
            'silent_benign_painted': joined.count('BRIDGE_SILENT_BENIGN ms='),
            'silent_benign_held': joined.count('BRIDGE_SILENT_BENIGN_HELD'),
            'no_audio_logged': joined.count('state=no-audio'),
            'silent_reds': len(lines_of(joined, 'BRIDGE_SILENT ms=')),
            'reason_silent_restarts': len(lines_of(
                joined, 'BRIDGE_RESTART reason=silent')),
            'painted_titles': [p.get('title') for p in painted][-6:],
        }
    finally:
        bridge.stop('oracle')
        child = bridge.child
        if child is not None:
            try:
                child.kill()
            except Exception:
                pass
    return snapshot


def arm_checks(snapshot: dict) -> tuple[list[str], list[str]]:
    """(failures, notes) for one arm, dispatched on the ARM LABEL."""
    arm = snapshot['arm']
    fails: list[str] = []
    notes = [f"{arm}: spawns={snapshot['spawns']} "
             f"respawns={snapshot['respawns']} restarts={snapshot['restarts']} "
             f"state={snapshot['state']!r} "
             f"no_audio_benign={snapshot['silent_greens']} "
             f"silent_kills={snapshot['silent_reds']}"]
    if arm == 'GREEN idle-under-death':
        # A death is already on screen. The benign path must still not kill --
        # and it must NOT paint its status over the death, which is the swallow
        # the rest of this bridge fights (`pending_error`, held warm-ups).
        if snapshot['respawns'] != 0:
            fails.append(f'{arm}: the shell respawned the worker '
                         f"{snapshot['respawns']}x")
        if snapshot['silent_benign_held'] < 1:
            fails.append(f'{arm}: no BRIDGE_SILENT_BENIGN_HELD -- the benign '
                         'path did not take the under-death branch')
        if snapshot['named_no_audio_painted']:
            fails.append(f'{arm}: the no-audio status was PAINTED OVER a death '
                         'the panel was still showing')
        if snapshot['no_audio_logged'] < 1:
            fails.append(f'{arm}: the named state was not even logged')
        if snapshot['reason_silent_restarts'] != 0:
            fails.append(f'{arm}: a silence RESTART still happened')
    elif arm.startswith('GREEN'):
        if snapshot['respawns'] != 0:
            fails.append(f"{arm}: the shell respawned the worker "
                         f"{snapshot['respawns']}x (spawns={snapshot['spawns']})")
        if not snapshot['named_no_audio_painted']:
            fails.append(f'{arm}: the named state was never painted '
                         '(no "No audio to transcribe")')
        if snapshot['state'] != 'no-audio':
            fails.append(f"{arm}: bridge state is {snapshot['state']!r}, "
                         "not 'no-audio'")
        if snapshot['silent_greens'] < 1:
            fails.append(f'{arm}: the watchdog never fired at all -- the arm '
                         'proves nothing (it must re-arm and re-fire)')
        if snapshot['reason_silent_restarts'] != 0:
            fails.append(f'{arm}: a silence RESTART still happened')
    elif arm == 'ANOMALY no-verdict':
        if snapshot['respawns'] < 1:
            fails.append('ANOMALY no-verdict: the watchdog did NOT restart a '
                         'worker that opened a stream and said nothing')
        if snapshot['reason_silent_restarts'] < 1:
            fails.append('ANOMALY no-verdict: no BRIDGE_RESTART reason=silent')
        if snapshot['named_no_audio_painted']:
            fails.append('ANOMALY no-verdict: a no-audio state was painted for '
                         'a silence the worker never explained')
    elif arm == 'ANOMALY signal-quiet':
        if snapshot['respawns'] < 1:
            fails.append('ANOMALY signal-quiet: the tap declared signal (a '
                         'caption) and then went mute, and was NOT restarted')
        if snapshot['named_no_audio_painted']:
            fails.append('ANOMALY signal-quiet: a no-audio state was painted '
                         'for a tap that had already produced a caption')
    elif arm == 'RED idle':
        if snapshot['respawns'] < 2:
            fails.append(f"RED idle: the pre-fix copy respawned only "
                         f"{snapshot['respawns']}x -- the defect did not "
                         'reproduce, so the green arms prove nothing')
        if snapshot['named_no_audio_painted']:
            fails.append('RED idle: the pre-fix copy painted the new state, so '
                         'it is not the pre-fix copy')
    else:
        fails.append(f'unknown arm {arm!r}: no checks ran')
    return fails, notes


def static_checks(mod) -> list[str]:
    """The guard's own vocabulary must be the WORKER's, not the shell's invention.

    A verdict string this shell invented would never match, and the guard would
    then be a green that cannot fire: the silence would keep being called
    anomalous and the 2.4 GB churn would continue with every arm still passing.
    So the sets are read against worker/sotto_worker.py itself.
    """
    import re
    fails: list[str] = []
    with open(os.path.join(ROOT, 'worker', 'sotto_worker.py'),
              encoding='utf-8') as fh:
        worker = fh.read()
    states = set(re.findall(r'state="([a-z0-9\-]+)"', worker))
    verdicts = set(re.findall(r'verdict\s*=\s*"([a-z0-9\-]+)"', worker))
    for s in sorted(mod.WORKER_NO_AUDIO_STATES):
        if s not in states:
            fails.append(f'vocabulary: {s!r} is in WORKER_NO_AUDIO_STATES but '
                         'the worker never emits it as a state=')
    for v in sorted(mod.WORKER_NO_AUDIO_VERDICTS):
        if v not in verdicts:
            fails.append(f'vocabulary: {v!r} is in WORKER_NO_AUDIO_VERDICTS '
                         'but the worker never emits it as a verdict=')
    if 'captions-emitted' in mod.WORKER_NO_AUDIO_VERDICTS:
        fails.append('vocabulary: captions-emitted is the ONE verdict that says '
                     'speech came out and must never mean "no audio"')
    # The named state must survive `_status`, which rewrites any text matching
    # FALSE_AUDIO_ABSENT_RE into CAPTURE_NOT_STARTED/busy.
    painted = 'Audio tap silent - nothing to transcribe'
    if mod.FALSE_AUDIO_ABSENT_RE.search(painted):
        fails.append('vocabulary: the painted text trips FALSE_AUDIO_ABSENT_RE '
                     'and would be rewritten to CAPTURE_NOT_STARTED')
    if mod.NO_AUDIO_STATE != 'no-audio':
        fails.append(f'vocabulary: the named UI state is '
                     f'{mod.NO_AUDIO_STATE!r}, expected no-audio')
    return fails


def main() -> int:
    report: dict = {'shell': SHELL, 'fake_worker': FAKE,
                    'silence_ms': SILENCE_MS, 'seconds': SECONDS, 'arms': {}}
    ok, detail = build_neg_mutant()
    report['neg_arm'] = {'built': ok, 'detail': detail}
    if not ok:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f'VERDICT: REFUSED -- the control could not be built: {detail}')
        return 2

    fixed = _load_module(SHELL, 'sotto_shell_fixed')
    mutant = _load_module(MUTANT, 'sotto_shell_prefix')

    plan = [
        ('GREEN idle', 'idle'),
        ('GREEN verdict-quiet', 'verdict-quiet'),
        ('GREEN idle-under-death', 'idle'),
        ('ANOMALY no-verdict', 'no-verdict'),
        ('ANOMALY signal-quiet', 'signal-quiet'),
        ('RED idle', 'red-idle'),
    ]
    failures: list[str] = []
    vocab = static_checks(fixed)
    report['static_checks'] = {'failures': vocab}
    print(f'  STATIC vocabulary      {len(vocab)} failing check(s)')
    for f in vocab:
        print(f'  STATIC vocabulary      FAIL: {f}')
    failures.extend(vocab)

    def plant_death(bridge):
        """Put a real exit-3 death on screen, exactly as `_wait` leaves it."""
        bridge.pending_error = {'state': 'exit', 'text': 'worker exit 3',
                                'body': ''}

    for label, mode in plan:
        if mode == 'red-idle':
            mod, run_mode, mutate = mutant, 'idle', None
        elif label == 'GREEN idle-under-death':
            mod, run_mode, mutate = fixed, mode, plant_death
        else:
            mod, run_mode, mutate = fixed, mode, None
        snap = run_arm(mod, run_mode, SECONDS, label, mutate)
        fails, notes = arm_checks(snap)
        report['arms'][label] = {'snapshot': snap, 'failures': fails}
        for line in notes:
            print(f'  {label:22s} {line}')
        for f in fails:
            print(f'  {label:22s} FAIL: {f}')
        failures.extend(fails)

    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        with open(out, 'w', encoding='utf-8') as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f'  report written to {out}')

    print(f"  REFUSED-IF-DEAD: control built={ok} ({detail})")
    print(f'VERDICT: {"PASS" if not failures else "FAIL"} '
          f'({len(failures)} failing check(s))')
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
