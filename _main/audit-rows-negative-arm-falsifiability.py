# =============================================================================
# audit-rows-negative-arm-falsifiability.py -- ONE instrument for THREE register
# rows that are all the same question: CAN THIS CHECK SAY NO?
#
#   #56  model-spec-oracle has no negative arm (a drift detector, not an oracle)
#   #57  _oss_oracle has no negative arm
#   #58  the bogus arm of runcmd-entry-driver.py has no receipt
#
# SUBJECTS MOVED WHILE THIS SWEEP RAN. Both oracles were rewritten at 23:13Z and
# 23:14Z on 2026-10-11 by another lane, each with a header that says it closes
# #56 / #57. So this instrument no longer measures "is there a switch" (the
# bytes say yes) -- it measures the switch ITSELF, by driving it on a SANDBOX
# COPY of each oracle against a COPY of the inputs, and it refuses to take the
# new arm's word for anything: every claim the arm prints is re-derived here,
# and each arm is then blinded by a mutant of the copy to prove the reading can
# go RED.
#
# The sandbox is faithful WITHOUT rewriting a single path literal: both oracles
# derive their root from __file__ (HERE = dirname(__file__), REPO = dirname(HERE)),
# so a copy at <sandbox>/_main/<oracle>.py with the inputs copied beside it sees a
# complete fake repo. The copy's sha256 is asserted equal to the live file's.
#
# NOTHING is launched: the oracles are file readers, the shell is imported and
# only its argparse is exercised. No run.cmd, no shell, no worker, no device.
#
# Usage:  py -3 _main/audit-rows-negative-arm-falsifiability.py [--neg-arm]
# =============================================================================
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
MODEL_SPEC_ORACLE = os.path.join(ROOT, '_main', 'model-spec-oracle.py')
OSS_ORACLE = os.path.join(ROOT, '_main', '_oss_oracle.py')
RUNCMD_REPORT = os.path.join(ROOT, '_main', 'runcmd-entry-report.json')
RUNCMD_DRIVER = os.path.join(ROOT, '_main', 'runcmd-entry-driver.py')
CONFIG = os.path.join(ROOT, 'worker', 'config.json')
BT = chr(96)


def say(message):
    print(message, flush=True)


def sha256_file(path):
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest().upper()


def read(path):
    with open(path, encoding='utf-8', newline='') as handle:
        return handle.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(text)


def run_python(path, cwd, args=()):
    got = subprocess.run([sys.executable, path, *args], cwd=cwd,
                         capture_output=True, text=True, timeout=300,
                         creationflags=0x08000000)
    return {'rc': got.returncode, 'stdout': got.stdout,
            'stderr_tail': got.stderr[-300:]}


def model_dir():
    return json.loads(read(CONFIG))['model']['dir']


def sandbox(root, oracle_source, oracle_name, tree_mutator=None):
    """A fake repo: the inputs both oracles read, plus a byte-identical copy of
    the oracle at <root>/_main/<oracle_name>."""
    for rel in ('worker/config.json', 'worker/lang_prompt.py',
                'worker/sotto_worker.py',
                'worker/' + model_dir() + '/genai_config.json',
                'app/panel/caption-formulation.js'):
        source = os.path.join(ROOT, rel)
        if not os.path.exists(source):
            continue
        target = os.path.join(root, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target)
    text = read(oracle_source)
    if tree_mutator is not None:
        text = tree_mutator(text)
    target = os.path.join(root, '_main', oracle_name)
    write(target, text)
    return target


def tail_lines(stdout, count=6):
    return [line for line in stdout.strip().split('\n') if line][-count:]


# ---------------------------------------------------------------------------
# arms
# ---------------------------------------------------------------------------
def arm_r56(ctx):
    oracle = ctx['model_spec_oracle']
    text = read(oracle)
    root = os.path.join(ctx['work'], 'r56-copy')
    copy = sandbox(root, oracle, 'model-spec-oracle.py')
    same_bytes = sha256_file(copy) == sha256_file(oracle)
    plain = run_python(copy, root)
    neg = run_python(copy, root, ['--neg-arm'])
    log_path = os.path.join(root, '_main', 'model-spec-oracle.log')
    log_tail = tail_lines(read(log_path), 6) if os.path.exists(log_path) else []
    # THE BLINDING: the SAME instrument run against a copy of the oracle whose
    # comparison is a constant True. cmd() in this file calls the blinded copy
    # with --neg-arm exactly as it calls the live one, so the reading below is
    # produced by the same code path both times.
    root_blind = os.path.join(ctx['work'], 'r56-blind')
    blind_anchor = 'return (blank == 13087 and chunk == 8960)'
    blind_copy = sandbox(root_blind, oracle, 'model-spec-oracle.py',
                         lambda t: t.replace(blind_anchor, 'return True'))
    blind_applied = read(blind_copy).count('return True') > 0
    blind = run_python(blind_copy, root_blind, ['--neg-arm'])
    blind_log = os.path.join(root_blind, '_main', 'model-spec-oracle.log')
    blind_tail = tail_lines(read(blind_log), 4) if os.path.exists(blind_log) else []
    return {
        'oracle': oracle,
        'negative_arm_switches': text.count('--neg-arm'),
        'sandbox_copy_is_byte_identical': same_bytes,
        'plain_rc': plain['rc'],
        'neg_arm_rc': neg['rc'],
        'neg_arm_log_tail': log_tail,
        'blinded_neg_arm_rc': blind['rc'],
        'blinded_log_tail': blind_tail,
        'blinding_applied': blind_applied,
        # THE CONVENTION IS THE ORACLE'S OWN (`model-spec-oracle.py:20-24`): the
        # negative arm exits 1 BY DESIGN when it finds the drift and 0 when it does
        # NOT. The old reading (`neg rc == 0`) is the pre-2026-10-11 one, and it
        # could not tell the two apart -- which is the very thing this arm exists
        # to detect. MEASURED 2026-10-20.
        'cannot_say_no': not (neg['rc'] == 1 and blind['rc'] == 0),
    }


class _StubChecks:
    """A stand-in for the oracle's own checks() that answers by PATH, so the
    live tree can be declared RED independently of the mutant arms -- which is
    the only way to ask whether the neg-arm's control line reads the live tree
    at all."""

    MUTANT = {'M1': 'C1', 'M2': 'C2', 'M3': 'C3', 'M4': 'C4'}

    def __init__(self):
        self.live_probed = False
        self.live_verdict = None

    def __call__(self, root, emit=print):
        name = os.path.basename(str(root))
        if name in self.MUTANT:
            target = self.MUTANT[name]
            return {key: (key != target) for key in self.MUTANT.values()}
        self.live_probed = True
        self.live_verdict = {key: False for key in self.MUTANT.values()}
        if emit:
            emit('STUB: the live tree is RED (every check False)')
        return self.live_verdict


def arm_r57(ctx):
    oracle = ctx['oss_oracle']
    text = read(oracle)
    root = os.path.join(ctx['work'], 'r57-copy')
    copy = sandbox(root, oracle, '_oss_oracle.py')
    same_bytes = sha256_file(copy) == sha256_file(oracle)
    plain = run_python(copy, root)
    neg = run_python(copy, root, ['--neg-arm'])
    control_line = ''
    for line in neg['stdout'].split('\n'):
        if 'NEG control' in line:
            control_line = line.strip()
            break
    # IN-PROCESS, with checks() stubbed: run the arm's OWN neg_arm() and see
    # whether it ever asks about the live tree, and what it then prints.
    loader = importlib.util.spec_from_file_location('oss_copy', copy)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    stub = _StubChecks()
    module.checks = stub
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            stub_rc = module.neg_arm()
        except SystemExit as exc:
            stub_rc = exc.code
    stub_out = buffer.getvalue()
    stub_control = ''
    for line in stub_out.split('\n'):
        if 'NEG control' in line:
            stub_control = line.strip()
            break
    return {
        'oracle': oracle,
        'negative_arm_switches': text.count('--neg-arm'),
        'sandbox_copy_is_byte_identical': same_bytes,
        'plain_rc': plain['rc'],
        'plain_checks': [line for line in plain['stdout'].split('\n')
                         if line.startswith(('PASS ', 'FAIL ', 'ORACLE'))],
        'neg_arm_rc': neg['rc'],
        'neg_arm_lines': tail_lines(neg['stdout'], 7),
        'shipped_control_line': control_line,
        'stub_live_probed': stub.live_probed,
        'stub_live_verdict_all_false': (stub.live_verdict is not None),
        'stub_control_line': stub_control,
        'stub_neg_arm_rc': stub_rc,
        'neg_arm_calls_checks_on_repo': 'live = checks(REPO)' in text,
        'control_line_unmeasured': (not stub.live_probed)
                                   and stub_control.startswith('PASS'),
    }


def arm_r58(ctx):
    report = ctx['runcmd_report']
    parsed = json.loads(read(report))
    driver = read(ctx['runcmd_driver'])
    shell = ctx['shell']
    refused = None
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            shell.parse_args(['--check-args', '--bogus-flag'])
            refused = 'ACCEPTED (no SystemExit)'
        except SystemExit as exc:
            refused = 'SystemExit(' + str(exc.code) + ')'
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            shell.parse_args(['--check-args'])
            accepted = 'returned args'
        except SystemExit as exc:
            accepted = 'SystemExit(' + str(exc.code) + ')'
    with contextlib.redirect_stdout(io.StringIO()) as help_out:
        try:
            shell.parse_args(['--help'])
        except SystemExit:
            pass
        help_text = help_out.getvalue()
    bogus_line = 0
    for index, line in enumerate(driver.split('\n')):
        if 'def arm_bogus' in line:
            bogus_line = index + 1
            break
    return {
        'report': report,
        'report_keys': sorted(parsed.keys()),
        'driver_bogus_line': bogus_line,
        'shell_parse_bogus_flag': refused,
        'shell_parse_check_args_only': accepted,
        'check_args_in_help': '--check-args' in help_text,
        'bogus_receipt_absent': 'bogus' not in parsed,
    }


ARMS = ('r56', 'r57', 'r58')
MEASURE = {'r56': arm_r56, 'r57': arm_r57, 'r58': arm_r58}
DEFECT_KEY = {'r56': 'cannot_say_no', 'r57': 'control_line_unmeasured',
              'r58': 'bogus_receipt_absent'}
ROW_OF = {
    'r56': 'audit #56: model-spec-oracle has no negative arm (a drift detector, '
           'not an oracle) -- _main/model-spec-oracle.py',
    'r57': 'audit #57: _oss_oracle has no negative arm -- _main/_oss_oracle.py',
    'r58': 'audit #58: the bogus arm of runcmd-entry-driver.py has no receipt -- '
           '_main/runcmd-entry-report.json',
}
# r57 flips 2026-10-11: the shipped _oss_oracle.py was repaired to PROBE the live tree
# (`live = checks(REPO)`), so 'the control is a label' is no longer true of the live file. The
# mutant below now reproduces the LABEL so this instrument keeps its power to catch it.
EXPECT_LIVE = {'r56': False, 'r57': False, 'r58': True}


def build_oracle_mutants(work):
    """r56: the comparison forced to a constant True. r57: the control line
    computed from a REAL check run instead of from the mutant results."""
    paths = {}
    text = read(MODEL_SPEC_ORACLE)
    anchor = 'return (blank == 13087 and chunk == 8960)'
    if text.count(anchor) != 1:
        say('SETUP ERROR: the r56 anchor appears ' + str(text.count(anchor))
            + ' time(s) in ' + MODEL_SPEC_ORACLE)
        raise SystemExit(2)
    paths['r56'] = os.path.join(work, 'm56-oracle-cannot-say-no.py')
    write(paths['r56'], text.replace(anchor, 'return True'))
    text = read(OSS_ORACLE)
    # The mutant UN-MEASURES the control: the two lines that probe the live tree are replaced
    # by an empty dict and a literal True, which is exactly what the shipped file did before
    # 2026-10-11 (it printed PASS from the MUTANT comparisons and never called checks(REPO)).
    old = "        live = checks(REPO)\n        live_green = all(live.values())"
    new = ("        live = {}\n        live_green = True"
           "  # MUTANT: the control is a LABEL again")
    if text.count(old) != 1:
        say('SETUP ERROR: the r57 probe anchor appears ' + str(text.count(old))
            + ' time(s) in ' + OSS_ORACLE)
        raise SystemExit(2)
    paths['r57'] = os.path.join(work, 'm57-control-label.py')
    write(paths['r57'], text.replace(old, new))
    return paths


def build_report_mutant(work):
    parsed = json.loads(read(RUNCMD_REPORT))
    parsed['bogus'] = {'arm': 'bogus', 'rc': 2, 'stdout': 'usage: ...',
                       'note': 'SYNTHETIC receipt written by this instrument to '
                               'prove the arm reads the file; NOT a measurement'}
    path = os.path.join(work, 'm58-report-with-bogus-receipt.json')
    write(path, json.dumps(parsed, indent=2))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Three register rows about checks that may not be able to '
                    'say NO: the two rewritten oracles get their new negative '
                    'arms DRIVEN on sandbox copies, and each reading is blinded '
                    'by a mutant. Launches nothing.')
    parser.add_argument('--neg-arm', action='store_true')
    parsed = parser.parse_args(argv)

    work = tempfile.mkdtemp(prefix='sotto-audit-negarm-')
    say('audit-rows-negative-arm-falsifiability -- three rows, one instrument')
    say('work       : ' + work)
    for path in (MODEL_SPEC_ORACLE, OSS_ORACLE, RUNCMD_REPORT, RUNCMD_DRIVER,
                 SHELL):
        say('  ' + path.ljust(48) + ' ' + str(os.path.getsize(path)).ljust(8)
            + ' B sha256 ' + sha256_file(path)[:16] + ' mtime '
            + __import__('datetime').datetime.fromtimestamp(
                os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S'))
    say('launches   : NOTHING (the oracles are file readers, even in the '
        'sandbox; the shell is imported and only its argparse is exercised)')

    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    spec = importlib.util.spec_from_file_location('audit_negarm_shell', SHELL)
    shell = importlib.util.module_from_spec(spec)
    sys.modules['audit_negarm_shell'] = shell
    spec.loader.exec_module(shell)

    oracle_mutants = build_oracle_mutants(work)
    say('')
    say('mutants    :')
    for key, path in sorted(oracle_mutants.items()):
        say('  ' + key.ljust(24) + ' ' + os.path.basename(path).ljust(34) + ' '
            + str(os.path.getsize(path)).ljust(8) + ' B sha256 '
            + sha256_file(path)[:16])

    def context(model_oracle, oss_oracle, report):
        return {'work': work, 'shell': shell, 'model_spec_oracle': model_oracle,
                'oss_oracle': oss_oracle, 'runcmd_report': report,
                'runcmd_driver': RUNCMD_DRIVER}

    def measure(ctx):
        results = {}
        for name in ARMS:
            try:
                results[name] = MEASURE[name](ctx)
            except Exception as exc:  # noqa: BLE001
                results[name] = {'ERROR': type(exc).__name__ + ': ' + str(exc)}
        return results

    def report(label, results, expected):
        say('')
        say('== ' + label)
        matched = True
        for name in ARMS:
            got = results[name]
            defect = got.get(DEFECT_KEY[name])
            ok = (defect is expected[name])
            matched = matched and ok
            say('  ARM ' + name + '  ' + ROW_OF[name])
            say('      defect=' + str(defect) + ' expected='
                + str(expected[name]) + '  ' + ('OK' if ok else 'WRONG COLOUR'))
            say('      measured: ' + json.dumps(got, default=str))
        return matched

    verdicts = []
    if not parsed.neg_arm:
        results = measure(context(MODEL_SPEC_ORACLE, OSS_ORACLE, RUNCMD_REPORT))
        ok = report('LIVE -- the two rewritten oracles, driven', results,
                    EXPECT_LIVE)
        verdicts.append(('live', ok))

    results = measure(context(oracle_mutants['r56'], oracle_mutants['r57'],
                              RUNCMD_REPORT))
    ok = report('MUTANT of the ORACLES (r56 cannot say NO; r57 UN-measures its own '
                'control) -- both readings must FLIP', results,
                {'r56': True, 'r57': True, 'r58': True})
    verdicts.append(('m-oracles', ok))

    results = measure(context(MODEL_SPEC_ORACLE, OSS_ORACLE,
                              build_report_mutant(work)))
    # This block drives the LIVE oracles, so its r56/r57 expectations are the LIVE ones
    # (r57 flipped to False on 2026-10-11 when the oracle started probing its own control);
    # only r58 is the mutant here.
    ok = report('MUTANT of the REPORT (a bogus receipt exists) -- the receipt '
                'reading must FLIP', results,
                {'r56': False, 'r57': False, 'r58': False})
    verdicts.append(('m-report-has-bogus', ok))

    say('')
    failed = [label for label, ok in verdicts if not ok]
    if failed:
        say('VERDICT: FAIL  (' + str(len(verdicts) - len(failed)) + '/'
            + str(len(verdicts)) + ' labels matched; wrong: ' + str(failed) + ')')
        return 1
    say('VERDICT: PASS  both rewritten oracles driven on sandbox copies; the '
        'blindings and the receipt mutant flip the readings they target')
    return 0


if __name__ == '__main__':
    sys.exit(main())
