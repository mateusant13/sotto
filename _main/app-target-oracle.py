#!/usr/bin/env python3
"""STEP 5 -- is the worker's PER-APP tap REACHABLE FROM THE APP, and is it OPT-IN?

WHY THIS EXISTS. The worker can already tap ONE process tree
(`--target-pid` / `SOTTO_TARGET_PID`, `ProcessLoopbackTap`) and every caption
it emits carries the additive `source` = `proc:<pid>`. The APP could not ask for it:
`grep -n target_pid app/webview/sotto_webview.py` returned ZERO matches, so the capability
existed and was unreachable -- the same defect class as a factored rule that
nothing calls. This oracle asks the two questions that decide the STEP:

  1. does `--app-target` reach the worker's ENVIRONMENT, for ONE target, and
  2. is the shell UNCHANGED when the flag is ABSENT?

IT LAUNCHES NOTHING. No shell, no WebView2, no worker, no audio device, no
window, no visible console: every arm is an in-process call against the shell
module loaded from `app/webview` (the module only -- `import webview` is
deliberately late in the shell, so importing it creates nothing). Arm (g)
additionally counts THIS process's children in the kernel snapshot before and
after the refusal, which is the instrument that proves no child was created.

ARMS (each GREEN/RED on its own; every arm runs against the live shell AND
against two mutated COPIES):

  a  digits -> that pid; 0 / negative / empty / absent -> (None, [])
  b  a REAL live image name -> a pid that EXISTS and is a TREE ROOT (its parent
     is not the same image), EVERY candidate is a root, the LOWEST root wins,
     the match is case-insensitive; plus an INJECTED table that makes the rule
     deterministic (a lower-pid CHILD of a match must not win)
  c  a name that cannot exist -> (None, [])   (the `reason=no-process` line the
     caller logs for that case is asserted in arm g)
  d  `WorkerBridge(target_pid=4242)._child_env()` carries SOTTO_TARGET_PID=4242
  e  `WorkerBridge()._child_env()` does NOT contain SOTTO_TARGET_PID at all, and is
     byte-identical to the env this shell produced before the parameter existed
  f  flag > env > none (`app_target_request`, the factored precedence)
  g  an UNRESOLVED target REFUSES to start a worker: returns False, never
     constructs the bridge, logs the decline, paints the panel through the error
     path, and creates NO child process; the RESOLVED positive control passes
     the pid at the ONE construction site; the ENV fallback reaches the machine
  h  `--app-target` is NOT in the measurement-flag suppression set (a
     `--dump-dom --app-target X` run still suppresses the worker)
  i  the CLI contract: `--app-target` exists, takes ONE value, and its help says
     pid/image-name, TREE ROOT, and "without it, the endpoint mix"

--neg-arm: the same arms against two mutated copies, both made from TODAY's
shell by literal replacement (a kept copy goes stale -- the lesson of
`_main/_prefix-under-test.py`):
  M1  the ONE env line removed    -> arm d RED, every other arm GREEN
  M2  the TREE-ROOT rule removed  -> arm b RED, every other arm GREEN
The mutant files are written to %TEMP% (NOT to _main/): this lane's write scope
is exactly three repo paths.

Usage:
    py -3 _main/app-target-oracle.py              # live arms + both mutants, one command
    py -3 _main/app-target-oracle.py --neg-arm    # the mutant half only
    py -3 _main/app-target-oracle.py --verbose    # every sub-check line

Exit 0 when every arm has the colour it MUST have, 1 when one does not, 2 on a
setup error.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')

ARMS = ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i')
TITLES = {
    'a': 'digits -> pid, junk -> None',
    'b': 'live image name -> TREE ROOT',
    'c': 'impossible name -> None',
    'd': 'target_pid reaches the child env',
    'e': 'no target -> no SOTTO_TARGET_PID',
    'f': 'flag > env > none',
    'g': 'unresolved REFUSES to start a worker',
    'h': 'not in the suppression set',
    'i': 'CLI contract',
}

#: M1 -- the ONE env line that makes the per-app tap reachable from the app.
M1_OLD = ("        if self.target_pid is not None:\n"
          "            env['SOTTO_TARGET_PID'] = str(self.target_pid)\n")
M1_NEW = ""
#: M2 -- the TREE-ROOT rule, removed: every match becomes a candidate.
M2_OLD = ("    roots = sorted(pid for pid, parent in matches "
          "if parent not in matched_pids)\n")
M2_NEW = "    roots = sorted(pid for pid, _parent in matches)\n"

VERBOSE = False


def say(message):
    print(message, flush=True)


def detail(message):
    if VERBOSE:
        say('    ' + message)


def sha256_file(path):
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest().upper()


def load_shell(path, name):
    """Import the shell module from a FILE -- no launch, no window, no worker."""
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Arm:
    def __init__(self, name):
        self.name = name
        self.bad = []
        self.notes = []

    def check(self, condition, message):
        detail(('PASS ' if condition else 'FAIL ') + message)
        if not condition:
            self.bad.append(message)
        return bool(condition)

    def note(self, message):
        self.notes.append(message)
        detail('note ' + message)


class FakeShell:
    """Just enough SottoShell for the REAL `start_worker` to run in-process.

    The method under test is the shipped one (`types.MethodType` binds it to this
    object); this object supplies only the collaborators it touches -- the parsed
    args, a place to record the paint, and the four bridge callbacks. Nothing
    here opens a window, a device or a process.
    """

    def __init__(self, mod, args, painted):
        self.args = args
        self.bridge = None
        self.START_REASONS = mod.SottoShell.START_REASONS
        self._painted = painted
        self.on_worker_caption = lambda text, meta: None
        self.on_worker_status = lambda text, kind, info: None
        self.on_worker_stats = lambda parsed: None
        self.on_worker_meter = lambda sample: None

    def apply_panel_state(self, text, kind='busy', info=None):
        self._painted.append((text, kind, dict(info or {})))
        return True

    def code_state_log(self, reason):
        return None


def make_shell(mod, args, painted, logs):
    shell = FakeShell(mod, args, painted)
    shell.start_worker = types.MethodType(mod.SottoShell.start_worker, shell)
    return shell


def children_of_me(mod):
    me = os.getpid()
    return sorted(pid for pid, ppid, _exe in mod._process_table() if ppid == me)


def live_rows(mod):
    return list(mod._process_table())


def check_live_name(mod, arm, name):
    """One live image name: the chosen pid and EVERY candidate must be a ROOT."""
    rows = live_rows(mod)
    by_pid = {pid: (ppid, exe) for pid, ppid, exe in rows}
    pid, candidates = mod.resolve_app_target(name)
    if not arm.check(pid is not None, f'{name}: resolved to {pid!r}'):
        return
    arm.check(pid in by_pid, f'{name}: chosen pid {pid} exists in the live table')
    arm.check(candidates == sorted(candidates),
              f'{name}: candidates sorted {candidates}')
    arm.check(pid == candidates[0], f'{name}: chose the LOWEST root ({pid})')
    arm.check(pid in candidates, f'{name}: the chosen pid is one of the candidates')
    for candidate in candidates:
        parent = by_pid.get(candidate, (None, None))[0]
        parent_name = by_pid.get(parent, (None, ''))[1]
        arm.check(str(parent_name).casefold() != name.casefold(),
                  f'{name}: candidate {candidate} is a tree ROOT '
                  f'(parent {parent} is {parent_name!r})')
    swapped = mod.resolve_app_target(name.swapcase())
    arm.check(swapped[0] == pid,
              f'{name}: the match is case-insensitive '
              f'({name.swapcase()} -> {swapped[0]})')


def arm_a(mod, arm, ctx):
    for value, want in (('4242', (4242, [4242])),
                        ('7', (7, [7])),
                        ('00042', (42, [42])),
                        (1234, (1234, [1234])),
                        ('0', (None, [])),
                        ('-5', (None, [])),
                        ('', (None, [])),
                        ('   ', (None, [])),
                        (None, (None, []))):
        got = mod.resolve_app_target(value)
        arm.check(got == want, f'{value!r} -> {got!r} (wanted {want!r})')


def arm_b(mod, arm, ctx):
    check_live_name(mod, arm, os.path.basename(sys.executable))
    # The STRONGEST live case: an image that really has a same-image
    # parent-child pair on this box right now, if one exists.
    by_name = {}
    for pid, ppid, exe in live_rows(mod):
        by_name.setdefault(str(exe), []).append((pid, ppid))
    best, best_n = None, 0
    for name, entries in by_name.items():
        matched = {pid for pid, _ppid in entries}
        if any(ppid in matched for _pid, ppid in entries) and len(entries) > best_n:
            best, best_n = name, len(entries)
    if best is not None:
        arm.note(f'live same-image tree available: {best} x{best_n}')
        check_live_name(mod, arm, best)
    else:
        arm.note('no live image has a same-image parent-child pair at this instant')
    # The INJECTED table: deterministic, independent of what the box is running.
    # 90 is a CHILD of the match 100 and has a LOWER pid, so a rule without the
    # tree-root filter would choose 90 -- that is what M2 must turn RED.
    injected = [(100, 50, 'oracle-app.exe'),    # root: 50 is another image
                (90, 100, 'oracle-app.exe'),    # child of a match, LOWER pid
                (200, 100, 'oracle-app.exe'),   # child of a match
                (500, 999, 'oracle-app.exe'),   # second root
                (300, 100, 'other.exe')]
    real = mod._process_table
    mod._process_table = lambda: list(injected)
    try:
        pid, candidates = mod.resolve_app_target('ORACLE-APP.EXE')
    finally:
        mod._process_table = real
    arm.check(pid == 100, f'injected: chose the lowest ROOT 100, got {pid!r}')
    arm.check(candidates == [100, 500],
              f'injected: candidates are the roots [100, 500], got {candidates!r}')


def arm_c(mod, arm, ctx):
    name = 'sotto-no-such-image-xyz.exe'
    rows = live_rows(mod)
    arm.check(not any(str(exe).casefold() == name for _p, _pp, exe in rows),
              f'{name} really is absent from the live table')
    got = mod.resolve_app_target(name)
    arm.check(got == (None, []), f'{name} -> {got!r} (wanted (None, []))')
    got = mod.resolve_app_target(name.upper())
    arm.check(got == (None, []), f'the case variant -> {got!r} (wanted (None, []))')


def arm_d(mod, arm, ctx):
    bridge = mod.WorkerBridge(command=sys.executable, worker_path=WORKER,
                              target_pid=4242)
    env = bridge._child_env()
    arm.check(env.get('SOTTO_TARGET_PID') == '4242',
              f'SOTTO_TARGET_PID={env.get("SOTTO_TARGET_PID")!r} (wanted "4242")')
    arm.check(bridge.target_pid == 4242, f'bridge.target_pid={bridge.target_pid!r}')
    other = mod.WorkerBridge(command=sys.executable, worker_path=WORKER,
                             device='Some Device', target_pid=7)
    env2 = other._child_env()
    arm.check(env2.get('SOTTO_TARGET_PID') == '7'
              and env2.get('SOTTO_AUDIO_DEVICE') == 'Some Device',
              'the target travels WITH the device, both in the same env')
    textual = mod.WorkerBridge(command=sys.executable, worker_path=WORKER,
                               target_pid='1234')
    arm.check(textual._child_env().get('SOTTO_TARGET_PID') == '1234',
              'a string pid is written as given')


def arm_e(mod, arm, ctx):
    bridge = mod.WorkerBridge(command=sys.executable, worker_path=WORKER)
    env = bridge._child_env()
    arm.check(bridge.target_pid is None,
              f'bridge.target_pid is None, got {bridge.target_pid!r}')
    arm.check('SOTTO_TARGET_PID' not in env,
              'SOTTO_TARGET_PID is ABSENT (not empty: absent)')
    expected = dict(os.environ)
    expected['SOTTO_CAPTURE_MODE'] = bridge.capture_mode
    arm.check(env == expected,
              'the env is byte-identical to the pre-existing contract: '
              'os.environ + SOTTO_CAPTURE_MODE, nothing else')
    deviced = mod.WorkerBridge(command=sys.executable, worker_path=WORKER,
                               device='Dev')
    env2 = deviced._child_env()
    expected2 = dict(os.environ)
    expected2['SOTTO_CAPTURE_MODE'] = deviced.capture_mode
    expected2['SOTTO_AUDIO_DEVICE'] = 'Dev'
    arm.check(env2 == expected2,
              'with a device: still only the two keys this shell ever added')


def arm_f(mod, arm, ctx):
    cases = [
        (types.SimpleNamespace(app_target=None), {}, (None, None)),
        (types.SimpleNamespace(), {}, (None, None)),
        (types.SimpleNamespace(app_target=None),
         {'SOTTO_APP_TARGET': 'chrome.exe'}, ('chrome.exe', 'env')),
        (types.SimpleNamespace(app_target='1234'),
         {'SOTTO_APP_TARGET': 'chrome.exe'}, ('1234', 'flag')),
        (types.SimpleNamespace(app_target='  '),
         {'SOTTO_APP_TARGET': 'chrome.exe'}, ('chrome.exe', 'env')),
        (types.SimpleNamespace(app_target=None),
         {'SOTTO_APP_TARGET': '   '}, (None, None)),
        (types.SimpleNamespace(app_target=' chrome.exe '), {},
         ('chrome.exe', 'flag')),
        (types.SimpleNamespace(app_target='1234'), {}, ('1234', 'flag')),
    ]
    for args, env, want in cases:
        got = mod.app_target_request(args, env)
        arm.check(got == want,
                  f'flag={getattr(args, "app_target", "<absent>")!r} env={env!r} '
                  f'-> {got!r} (wanted {want!r})')


def arm_g(mod, arm, ctx):
    logs, painted = ctx['logs'], ctx['painted']
    missing = 'sotto-no-such-image-xyz.exe'
    args = types.SimpleNamespace(python=sys.executable, worker=WORKER,
                                 device=None, capture=None, app_target=missing)

    class FakeBridge:
        calls = []

        def __init__(self, **kwargs):
            FakeBridge.calls.append(kwargs)
            self.kwargs = kwargs

        def start(self, reason='start'):
            return True

    real_bridge, real_log = mod.WorkerBridge, mod.log
    mod.log = lambda message: logs.append(str(message))
    mod.WorkerBridge = FakeBridge
    try:
        # ── the REFUSAL: an unresolvable target must not fall back ─────────
        FakeBridge.calls.clear()
        logs.clear()
        painted.clear()
        shell = make_shell(mod, args, painted, logs)
        before = children_of_me(mod)
        returned = shell.start_worker('default')
        after = children_of_me(mod)
        arm.check(returned is False,
                  f'unresolved: start_worker returned {returned!r} (wanted False)')
        arm.check(FakeBridge.calls == [],
                  'no bridge was constructed (the construction site was never reached)')
        arm.check(shell.bridge is None, 'the shell has no bridge after the refusal')
        arm.check(before == after,
                  f'no child process was created (children before={before} after={after})')
        arm.check(any(f'APP_TARGET value="{missing}" source=flag' in line
                      for line in logs),
                  'APP_TARGET value=... source=flag was logged')
        arm.check(any(f'APP_TARGET_UNRESOLVED value="{missing}" reason=no-process'
                      in line for line in logs),
                  'APP_TARGET_UNRESOLVED ... reason=no-process was logged')
        arm.check(any('WORKER_AUTOSTART=declined reason=app-target-unresolved'
                      in line for line in logs),
                  'the refusal takes the WORKER_AUTOSTART=declined shape')
        arm.check(len(painted) == 1 and painted[0][1] == 'error',
                  f'the panel was painted through the error path: {painted!r}')
        arm.check(bool(painted)
                  and painted[0][0].startswith('App target not found'),
                  'the painted sentence names the missing target')

        # ── the POSITIVE CONTROL: a resolved target passes the pid ──────────
        own = os.path.basename(sys.executable)
        want_pid = mod.resolve_app_target(own)[0]
        args.app_target = own
        FakeBridge.calls.clear()
        logs.clear()
        painted.clear()
        shell2 = make_shell(mod, args, painted, logs)
        before2 = children_of_me(mod)
        returned2 = shell2.start_worker('default')
        after2 = children_of_me(mod)
        arm.check(returned2 is True,
                  f'resolved: start_worker returned {returned2!r} (wanted True)')
        arm.check(before2 == after2,
                  'the positive control created no child process either')
        arm.check(len(FakeBridge.calls) == 1,
                  f'the construction site ran exactly once: {len(FakeBridge.calls)}')
        got_pid = FakeBridge.calls[-1].get('target_pid') if FakeBridge.calls else None
        arm.check(got_pid == want_pid,
                  f'target_pid={got_pid!r} (wanted {want_pid!r}) at the ONE '
                  f'WorkerBridge construction site')
        arm.check(any(f'APP_TARGET_RESOLVED value="{own}" chose={want_pid}' in line
                      for line in logs),
                  'APP_TARGET_RESOLVED names the chosen pid')

        # ── the ENV fallback reaches the MACHINE, not just the helper ───────
        args.app_target = None
        os.environ['SOTTO_APP_TARGET'] = missing
        try:
            FakeBridge.calls.clear()
            logs.clear()
            painted.clear()
            shell3 = make_shell(mod, args, painted, logs)
            returned3 = shell3.start_worker('default')
        finally:
            del os.environ['SOTTO_APP_TARGET']
        arm.check(returned3 is False,
                  'an env-sourced target that cannot resolve also refuses')
        arm.check(any(f'APP_TARGET value="{missing}" source=env' in line
                      for line in logs),
                  'the env fallback reaches start_worker and is logged source=env')
    finally:
        mod.WorkerBridge, mod.log = real_bridge, real_log


def suppression_args(**overrides):
    args = types.SimpleNamespace(with_worker=False, no_worker=False, dump_dom=False,
                                 selftest=False, memory=False, no_hotkey=False,
                                 exit_after=0.0, probe_stats=False,
                                 probe_outside_click=False, probe_edit_mode=False,
                                 app_target=None)
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def arm_h(mod, arm, ctx):
    reason = mod.SottoShell._worker_autostart_reason(
        suppression_args(app_target='chrome.exe'), env={})
    arm.check(reason == 'default',
              f'a bare --app-target does NOT suppress the worker: reason={reason!r}')
    reason = mod.SottoShell._worker_autostart_reason(
        suppression_args(app_target='chrome.exe', dump_dom=True), env={})
    arm.check(reason == 'measurement-flag(--dump-dom)',
              f'--dump-dom --app-target X still suppresses by --dump-dom: '
              f'reason={reason!r}')
    reason = mod.SottoShell._worker_autostart_reason(
        suppression_args(app_target=None), env={'SOTTO_APP_TARGET': 'chrome.exe'})
    arm.check(reason == 'default',
              f'SOTTO_APP_TARGET alone does not suppress: reason={reason!r}')
    reason = mod.SottoShell._worker_autostart_reason(
        suppression_args(app_target='chrome.exe', selftest=True), env={})
    arm.check(reason == 'measurement-flag(--selftest)',
              f'--selftest --app-target X still suppresses by --selftest: '
              f'reason={reason!r}')


def arm_i(mod, arm, ctx):
    args = mod.parse_args([])
    got = getattr(args, 'app_target', '<missing>')
    arm.check(got is None, f'no flag -> app_target={got!r} (wanted None)')
    args = mod.parse_args(['--app-target', 'chrome.exe'])
    arm.check(args.app_target == 'chrome.exe',
              f'one image-name value: {args.app_target!r}')
    args = mod.parse_args(['--app-target', '4242'])
    arm.check(args.app_target == '4242', f'one pid value: {args.app_target!r}')
    args = mod.parse_args(['--app-target', 'chrome.exe', '--capture', 'file'])
    arm.check(args.app_target == 'chrome.exe' and args.capture == 'file',
              'it coexists with --capture, unchanged')
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        with contextlib.suppress(SystemExit):
            mod.parse_args(['--help'])
    helptext = buffer.getvalue()
    for needle in ('--app-target', 'PID|IMAGE', 'image name', 'TREE ROOT',
                   'endpoint mix', 'SOTTO_APP_TARGET'):
        arm.check(needle in helptext, f'--help mentions {needle!r}')


ARM_FUNCS = {'a': arm_a, 'b': arm_b, 'c': arm_c, 'd': arm_d, 'e': arm_e,
             'f': arm_f, 'g': arm_g, 'h': arm_h, 'i': arm_i}


def run_arms(mod):
    ctx = {'logs': [], 'painted': []}
    results = {}
    for name in ARMS:
        arm = Arm(name)
        try:
            ARM_FUNCS[name](mod, arm, ctx)
        except Exception as exc:  # a raised arm is a RED arm, never a crash
            arm.bad.append(f'{name}: raised {type(exc).__name__}: {exc}')
        results[name] = arm
    return results


def report(label, results, expected):
    say('')
    say(f'== {label}')
    matched = True
    for name in ARMS:
        arm = results[name]
        green = not arm.bad
        want_green = expected[name]
        same = green == want_green
        matched = matched and same
        say(f'  ARM {name}  [{"GREEN" if green else "RED "}]  '
            f'expected [{"GREEN" if want_green else "RED "}]  '
            f'{TITLES[name]}'
            + ('' if same else '   <-- WRONG COLOUR'))
        for note in arm.notes:
            say(f'      note: {note}')
        for bad in arm.bad:
            say(f'      FAIL: {bad}')
    return matched


def make_mutant(source, old, new, label, directory):
    """One literal replacement in TODAY's bytes, and nothing else.

    The anchors are written with @@BT@@\n@@BT@@; the file is CRLF, so the anchor is
    re-encoded to the file's OWN line ending before it is counted. That keeps the
    mutant byte-exact apart from the mutation -- a mutant that also changed every
    line ending would be a second, undeclared difference.
    """
    newline = '\r\n' if '\r\n' in source else '\n'
    old = old.replace('\n', newline)
    new = new.replace('\n', newline)
    count = source.count(old)
    if count != 1:
        say(f'SETUP ERROR: the {label} anchor appears {count} time(s) in '
            f'{SHELL} (wanted exactly 1) -- the mutation would not be the one '
            f'this oracle documents')
        raise SystemExit(2)
    path = os.path.join(directory, f'sotto_webview_{label}.py')
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(source.replace(old, new, 1))
    say(f'  {label}: 1 literal replacement, {len(old)} B -> {len(new)} B, '
        f'line endings preserved ({newline!r})')
    return path


def main(argv=None):
    global VERBOSE
    parser = argparse.ArgumentParser(
        description='Is the worker per-app tap reachable from the app, and is '
                    'it opt-in? (in-process; launches nothing)')
    parser.add_argument('--shell', default=SHELL, help='the shell under test')
    parser.add_argument('--neg-arm', action='store_true',
                        help='run the mutant half only')
    parser.add_argument('--verbose', action='store_true',
                        help='print every sub-check line')
    parsed = parser.parse_args(argv)
    VERBOSE = parsed.verbose
    shell_path = os.path.abspath(parsed.shell)

    say('app-target-oracle -- the per-app tap, reachable and opt-in')
    say(f'shell      : {shell_path}')
    say(f'bytes      : {os.path.getsize(shell_path)}')
    say(f'sha256     : {sha256_file(shell_path)}')
    say(f'worker env : SOTTO_TARGET_PID (worker/sotto_worker.py reads it; this '
        f'oracle never runs the worker)')
    say('launches   : NOTHING (no shell, no window, no worker, no device)')

    green_all = {name: True for name in ARMS}
    verdicts = []

    if not parsed.neg_arm:
        live = load_shell(shell_path, 'app_target_oracle_live')
        results = run_arms(live)
        ok = report('LIVE shell -- every arm must be GREEN', results, green_all)
        verdicts.append(('live', ok,
                         sum(1 for n in ARMS if not results[n].bad), len(ARMS)))

    # Read the BYTES (newline='') so the mutant keeps the file's own CRLF.
    with open(shell_path, encoding='utf-8', newline='') as handle:
        source = handle.read()
    directory = tempfile.mkdtemp(prefix='sotto-app-target-oracle-')
    say('')
    say(f'mutants    : {directory}')
    m1 = make_mutant(source, M1_OLD, M1_NEW, 'm1-env-line-removed', directory)
    m2 = make_mutant(source, M2_OLD, M2_NEW, 'm2-tree-root-removed', directory)
    for path in (m1, m2):
        say(f'  {os.path.basename(path)}  {os.path.getsize(path)} B  '
            f'sha256 {sha256_file(path)}')

    expect_m1 = {name: (name != 'd') for name in ARMS}
    expect_m2 = {name: (name != 'b') for name in ARMS}
    for path, expected, label in ((m1, expect_m1, 'M1 env line removed'),
                                  (m2, expect_m2, 'M2 tree-root rule removed')):
        module = load_shell(path, 'app_target_oracle_' + label.split()[0].lower())
        results = run_arms(module)
        ok = report(f'{label} -- exactly ONE arm must be RED', results, expected)
        reds = [n for n in ARMS if results[n].bad]
        verdicts.append((label, ok, reds, expected))

    say('')
    failed = [label for label, ok, _a, _b in verdicts if not ok]
    if failed:
        say(f'VERDICT: FAIL  ({len(verdicts) - len(failed)}/{len(verdicts)} '
            f'labels matched; wrong: {failed})')
        return 1
    parts = []
    for label, _ok, a, b in verdicts:
        if label == 'live':
            parts.append(f'{label}=GREEN({a}/{b})')
        else:
            parts.append(f'{label}=RED-as-expected({a})')
    say('VERDICT: PASS  ' + '  '.join(parts))
    return 0


if __name__ == '__main__':
    sys.exit(main())
