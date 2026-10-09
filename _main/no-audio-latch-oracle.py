"""Sotto — the oracle for the NO-AUDIO LATCH (`WorkerBridge.no_audio`).

Run:  py -3 _main/no-audio-latch-oracle.py

THE DEFECT THIS GATES, measured on the owner's own live run on 2026-10-08 before
the cure existed. `_main/panel-state.json` published

    "noAudio": true, "noAudioEvidence": "device-rotated reason=flat peak=0.0 floor=0.002"
    "captions": 21295, "state": "capture-started"

i.e. the shell's own name for the panel state was `no-audio` while the worker had
produced 21 295 captions on the same child, and the evidence sentence named a
candidate the ladder had already moved AWAY from. `no_audio` was set by
`_no_audio_evidence` and cleared only in `_spawn`, so ONE flat window latched it
for the LIFE OF THE CHILD. Two consequences, both real, both gated below:

  * THE WATCHDOG WENT BLIND. `_on_silence` returns early whenever `no_audio` is
    true, so after one flat window every later quiet was BENIGN — a worker that
    wedged afterwards could never be caught, which is the opposite of what that
    branch was written for (its own comment: "it must still catch a child that
    wedges AFTER saying this").
  * THE PANEL WAS TOLD "No audio to transcribe" over a working transcript, which
    is the owner's report, verbatim: *"nao ta ao vivo. algo ta bugado."*

THE CURE (the claim this file gates): a CAPTION is proof about the audio measured
on the endpoint the tap IS on, so it lifts the no-audio verdict with the same
force it already lifted a death — in the `type == 'caption'` branch of
`_consume`, logged as `BRIDGE_NO_AUDIO_LIFTED reason=caption`.

ARMS, and what each one would catch:
  ARM 1  a flat rotation raises the verdict AND the published name becomes
         `no-audio` (the detection still works — the cure must not disable it).
  ARM 2  a caption LIFTS it: flag false, evidence cleared, the lift is LOGGED,
         and the published name is no longer `no-audio`.
  ARM 3  a warm-up status does NOT lift it on its own (only a caption may), so a
         quiet machine is still named honestly.
  ARM 4  THE PAYOFF, as behaviour: with the verdict up, `_on_silence` takes the
         benign branch and kills nothing; after a caption, the SAME silence takes
         the anomalous branch. This is the arm that says the watchdog is
         un-blinded, and it is why the flag matters at all.
  CONTROL (always run, on a mutant built from TODAY's shell with only the lift
         block deleted): ARM 2 must go RED there, and ARM 1/3/4's benign half must
         not. A gate that cannot fail is not a gate.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.environ.get('PANEL_ORACLE_SHELL') or os.path.join(
    ROOT, 'app', 'webview', 'sotto_webview.py')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
MUTANT = os.path.join(ROOT, '_main', '_no-audio-lift-mutant.py')

#: The cure, matched by TEXT and COUNTED: a shell that has drifted away from this
#: shape makes the control REFUSE rather than mutate the wrong thing.
LIFT_RE = re.compile(
    r"\n            if self\.no_audio:\n"
    r"                self\.log\(f'BRIDGE_NO_AUDIO_LIFTED reason=caption '"
    r".*?"
    r"\n                self\.no_audio = False\n"
    r"                self\.no_audio_evidence = None",
    re.S)


def load_shell(path: str, name: str):
    """Import a shell revision as a module, so the arms drive the REAL class."""
    sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def named_state_fn(module):
    """The shell's own `_named_panel_state`, found by SHAPE, not by class name.

    Hard-coding the class would make this oracle fail the day the class is
    renamed, for a reason that has nothing to do with the defect.
    """
    for obj in vars(module).values():
        if isinstance(obj, type) and hasattr(obj, '_named_panel_state'):
            return obj._named_panel_state
    return None


class _Child:
    """A stand-in process handle: `_on_silence` reads `.pid`, nothing else."""

    pid = 4321


def new_bridge(module, log_lines, painted, killed=None, armed=None):
    b = module.WorkerBridge(
        command=sys.executable, worker_path=WORKER, log=log_lines.append,
        on_status=lambda t, k, i: painted.append((t, k, dict(i))),
        on_caption=lambda t, m: painted.append(('caption:' + t, 'live', dict(m))),
        backoff_base=600000, backoff_max=600000)
    b.child = _Child()
    # INSTANCE-LEVEL SHADOWS, and they are declared as such: this arm is about
    # WHICH BRANCH `_on_silence` takes, so the timer, the kill and the paint are
    # recorded instead of performed -- no process is spawned, no status is sent.
    b._arm_silence = lambda: (armed.append(1) if armed is not None else None)
    b._kill_and_restart = lambda reason: (killed.append(reason) if killed is not None else None)
    b._bridge_status = lambda text, kind, info=None, state=None: painted.append(
        (text, kind, dict(info or {})))
    return b


FLAT_ROTATION = json.dumps({'type': 'status', 'state': 'device-rotated',
                            'reason': 'flat', 'peak': 0.0, 'peak_floor': 0.002})
CAPTION = json.dumps({'type': 'caption', 'text': 'bom dia', 'start': 0.0})


def arms(module, expect_lift: bool):
    """The shared arm bodies. `expect_lift=False` is the mutant's run.

    Returns `(failures, evidence)` so the caller can tell a RED-on-the-mutant
    from a RED-on-the-real-shell.
    """
    failures: list[str] = []
    seen: dict = {}
    named = named_state_fn(module)
    if named is None:
        return ['the shell exposes no `_named_panel_state` to ask what the panel '
                'is called'], seen
    no_audio_state = getattr(module, 'NO_AUDIO_STATE', 'no-audio')

    # ── ARM 1: the detection still works, and it is what names the panel ──────
    log_lines: list[str] = []
    painted: list[tuple] = []
    b = new_bridge(module, log_lines, painted)
    b._consume(FLAT_ROTATION)
    seen['arm1_no_audio'] = b.no_audio
    seen['arm1_evidence'] = b.no_audio_evidence
    if not b.no_audio:
        failures.append('ARM 1: a flat rotation did NOT raise the no-audio verdict '
                        '(the cure would then be indistinguishable from deleting '
                        'the detection)')
    if not b.no_audio_evidence:
        failures.append('ARM 1: the verdict was raised with NO evidence sentence, '
                        'so the log could not say why')
    named_before = named({'noAudio': bool(b.no_audio), 'state': b.state}, 'Idle')
    seen['arm1_named_state'] = named_before
    if b.no_audio and named_before != no_audio_state:
        failures.append(f'ARM 1: with the verdict up the panel is named '
                        f'{named_before!r}, expected {no_audio_state!r}')
    b.stop('arm1')

    # ── ARM 3: only a CAPTION may lift it ────────────────────────────────────
    b._consume(json.dumps({'type': 'status', 'state': 'model-loading'}))
    if expect_lift and not b.no_audio:
        failures.append('ARM 3: a warm-up status lifted the verdict — only a '
                        'caption may, or a quiet machine stops being named')
    seen['arm3_held_through_warmup'] = bool(b.no_audio)

    # ── ARM 2: the caption lifts it ──────────────────────────────────────────
    b._consume(CAPTION)
    seen['arm2_no_audio'] = b.no_audio
    seen['arm2_evidence'] = b.no_audio_evidence
    lifted = any('BRIDGE_NO_AUDIO_LIFTED' in ln for ln in log_lines)
    seen['arm2_logged'] = lifted
    named_after = named({'noAudio': bool(b.no_audio), 'state': b.state}, 'Idle')
    seen['arm2_named_state'] = named_after

    if expect_lift:
        if b.no_audio:
            failures.append('ARM 2: a caption did NOT lift the no-audio verdict — '
                            'the latch survives, the watchdog stays blind and the '
                            'panel keeps being told there is no audio')
        if b.no_audio_evidence is not None:
            failures.append(f'ARM 2: the evidence survived the lift: '
                            f'{b.no_audio_evidence!r}')
        if not lifted:
            failures.append('ARM 2: the lift happened silently — no '
                            'BRIDGE_NO_AUDIO_LIFTED line, so nobody can tell the '
                            'verdict moved')
        if named_after == no_audio_state:
            failures.append('ARM 2: the panel is STILL named '
                            f'{no_audio_state!r} after a caption')
    b.stop('arm2')

    # ── ARM 4: the payoff — the watchdog branch, before and after ────────────
    log4: list[str] = []
    painted4: list[tuple] = []
    killed4: list[str] = []
    armed4: list[int] = []
    b4 = new_bridge(module, log4, painted4, killed4, armed4)
    b4._consume(FLAT_ROTATION)
    b4._on_silence()
    benign = any('BRIDGE_SILENT_BENIGN' in ln for ln in log4)
    anomalous = any(re.match(r'BRIDGE_SILENT ms=', ln) for ln in log4)
    seen['arm4_with_verdict'] = {'benign': benign, 'anomalous': anomalous,
                                 'killed': list(killed4)}
    if not benign or anomalous or killed4:
        failures.append('ARM 4: with the verdict up, a silence was NOT treated as '
                        f'benign (benign={benign} anomalous={anomalous} '
                        f'killed={killed4})')

    log4.clear()
    killed4.clear()
    b4._consume(CAPTION)
    b4._on_silence()
    benign_after = any('BRIDGE_SILENT_BENIGN' in ln for ln in log4)
    anomalous_after = any(re.match(r'BRIDGE_SILENT ms=', ln) for ln in log4)
    seen['arm4_after_caption'] = {'benign': benign_after,
                                  'anomalous': anomalous_after,
                                  'killed': list(killed4)}
    if expect_lift:
        if benign_after or not anomalous_after:
            failures.append('ARM 4: after a caption the SAME silence was still '
                            'treated as benign — the watchdog is still blind '
                            f'(benign={benign_after} anomalous={anomalous_after})')
        if killed4 != ['silent']:
            failures.append(f'ARM 4: the anomalous branch did not act on the jam: '
                            f'killed={killed4}')
    b4.stop('arm4')
    return failures, seen


def build_mutant() -> tuple[bool, str, dict]:
    """A COPY of TODAY's shell with ONLY the caption lift block deleted."""
    with open(SHELL, encoding='utf-8') as f:
        src = f.read()
    n = len(LIFT_RE.findall(src))
    if n != 1:
        return False, (f'the lift block matches {n} times in {SHELL} '
                       f'(expected exactly 1) — the shell has drifted away from '
                       f'the shape this control knows how to revert'), {}
    out = LIFT_RE.sub('', src, count=1)
    if out == src:
        return False, 'the mutant is byte-identical to the source', {}
    with open(MUTANT, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    digest = lambda b: hashlib.sha256(b).hexdigest()[:16]
    info = {'mutant': MUTANT, 'src_sha16': digest(src.encode('utf-8')),
            'mutant_sha16': digest(out.encode('utf-8'))}
    if info['src_sha16'] == info['mutant_sha16']:
        return False, 'the mutation did not move the artefact hash', info
    return True, '', info


def main() -> int:
    report: dict = {'shell': SHELL}
    failures: list[str] = []

    module = load_shell(SHELL, 'sotto_webview_no_audio_arm')
    real_failures, real_seen = arms(module, expect_lift=True)
    report['arms'] = real_seen
    failures.extend(real_failures)

    # ── THE CONTROL: the same arms on the lift-less shell ────────────────────
    ok, reason, info = build_mutant()
    report['control'] = dict(info)
    if not ok:
        failures.append(f'CONTROL: cannot build the mutant: {reason}')
    else:
        try:
            mutant = load_shell(MUTANT, 'sotto_webview_no_audio_mutant')
            mutant_failures, mutant_seen = arms(mutant, expect_lift=True)
        except SyntaxError as exc:
            mutant_failures, mutant_seen = [f'the mutant does not compile: {exc}'], {}
        report['control']['arms'] = mutant_seen
        report['control']['failures'] = mutant_failures
        report['control']['red_as_expected'] = bool(mutant_failures)
        if not mutant_failures:
            failures.append('CONTROL: the lift-less shell stayed GREEN — ARM 2 '
                            'cannot fail, so it proves nothing')
        elif not any('ARM 2' in f for f in mutant_failures):
            failures.append('CONTROL: the mutant went red for the WRONG reason — no '
                            f'ARM 2 failure: {mutant_failures}')
        # ARM 1 and ARM 4's benign half must NOT move: the revert touches only the
        # lift, so a mutant that broke those would be a mutant of something else.
        for other in ('ARM 1', 'ARM 4: with the verdict up'):
            if any(other in f for f in mutant_failures):
                failures.append(f'CONTROL: the mutant also broke {other!r}, which '
                                'deleting the lift must NOT touch')
        # And the mutant must really have latched: the verdict stayed up.
        if mutant_seen.get('arm2_no_audio') is not True:
            failures.append('CONTROL: the lift-less shell did not even latch the '
                            f'verdict (arm2_no_audio={mutant_seen.get("arm2_no_audio")!r})')

    report['failures'] = failures
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print('')
    print(f'ARMS: 4  (1 raise / 3 lift / 2 lift / 4 watchdog)  '
          f'CONTROL: {"RED as expected" if report.get("control", {}).get("red_as_expected") else "not red"}')
    print('VERDICT: ' + ('PASS' if not failures else f'FAIL ({len(failures)})'))
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
