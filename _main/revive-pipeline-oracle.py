"""ORACLE for the owner's repair control: clicking the panel's status REVIVES the pipeline.

Owner's ruling, verbatim (2026-10-08): *"e o botao de error ou de idle sei que,
ao clicar, deve fazer a pipeline inteira ser revivida, se nao tiver funcionando"*.

THREE ARMS, both colours in ONE command:

  ARM P  the PANEL, in a real Chromium, over the REAL `app/panel/panel.html` and
         the REAL `panel.js`: the footer and the strip are wired (`role=button`,
         `tabindex=0`, `cursor:pointer`, a title that states the cost), ONE click
         calls `bridge.revive` exactly once and takes the sticky worker death off
         the screen in a NEUTRAL sentence, a second click does not stack a second
         respawn, Enter on the strip revives, and a shell with NO `bridge.revive`
         calls nothing and says so out loud.
  ARM S  the SHELL, in process, running the real `revive_worker`/`_do_revive`
         against fake collaborators: the old child is stopped with reason=revive,
         every latch that could outlive it is cleared, a fresh worker is started
         with reason=revive, and a SECOND call while the first is in flight is
         refused instead of stacking.
  ARM L  the LIVE shell with a REAL worker: `--probe-revive` asks the real page
         to press the real element, and the log must show the child's pid
         CHANGING and the new worker coming up afterwards.

The negative arm is built from TODAY'S files, ONE LINE each, never from a kept
copy (a kept copy goes stale the first time anyone touches the file), and the
hash is required to MOVE so a mutant that changed nothing cannot pass as a
control:

    py -3 _main/revive-pipeline-oracle.py            # rc=0
    py -3 _main/revive-pipeline-oracle.py --neg-arm   # rc=0 only if BOTH go RED

Usage:
    py -3 _main/revive-pipeline-oracle.py [--panel-only | --shell-only | --live-only]
    py -3 _main/revive-pipeline-oracle.py --neg-arm
    SOTTO_REVIVE_SHELL=<path> py -3 _main/revive-pipeline-oracle.py   # shell under test
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

SHELL = os.environ.get('SOTTO_REVIVE_SHELL') or os.path.join(
    REPO, 'app', 'webview', 'sotto_webview.py')
PANEL_HTML = os.path.join(REPO, 'app', 'panel', 'panel.html')
PANEL_JS = os.path.join(REPO, 'app', 'panel', 'panel.js')

RENDER_DIR = os.path.join(HERE, 'revive-panel-render-test')
ELECTRON = os.path.join(REPO, 'app', 'node_modules', 'electron', 'dist', 'electron.exe')
PAGE = os.path.join(RENDER_DIR, '_page.html')
PANEL_JS_UNDER_TEST = os.path.join(RENDER_DIR, '_panel-under-test.js')
LIVE_LOG = os.path.join(HERE, '_revive-live.log')

CREATE_NO_WINDOW = 0x08000000

#: What the panel posts as the caller of a revive (`panel.js` `revivePipeline`).
PANEL_CALLER = 'panel-status'


def sha256(path: str) -> str:
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read(path: str) -> str:
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def lines_from(path: str) -> list[str]:
    with open(path, encoding='utf-8', errors='replace') as fh:
        return [ln.rstrip('\n') for ln in fh]


def one(log: list[str], needle: str) -> str | None:
    for ln in log:
        if needle in ln:
            return ln
    return None


def indexes(log: list[str], needle: str) -> list[int]:
    return [i for i, ln in enumerate(log) if needle in ln]


def last_json(log: list[str], prefix: str) -> dict | None:
    got = None
    for ln in log:
        at = ln.find(prefix)
        if at < 0:
            continue
        try:
            got = json.loads(ln[at + len(prefix):].strip())
        except ValueError:
            continue
    return got


# ---------------------------------------------------------------------------
# ARM P — the panel, in a real Chromium, over the real document
# ---------------------------------------------------------------------------

def build_page(panel_js_source: str) -> str:
    """Build `_page.html` from the REAL `panel.html`, and copy the js under test.

    The page is REBUILT on every run from today's `panel.html` (never kept), with
    every relative asset rewritten to point back at `app/panel/`, so the document
    under test is the shipped markup with the shipped stylesheets — only the
    directory it is served from changes. Returns the sha256 of the js copy.
    """
    html = read(PANEL_HTML)

    def rewrite(match: re.Match) -> str:
        attr, value = match.group(1), match.group(2)
        if value.startswith(('http', '/', '#', 'data:')):
            return match.group(0)
        return f'{attr}="../../app/panel/{value}"'

    html = re.sub(r'(href|src)="([^"]+)"', rewrite, html)
    # The panel's own script is the file UNDER TEST (the shipped one, or a mutant).
    html = html.replace('src="../../app/panel/panel.js"',
                        'src="./_panel-under-test.js"')
    assert 'src="./_panel-under-test.js"' in html, \
        'the panel.js script tag was not found in panel.html'
    with open(PAGE, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)
    shutil.copyfile(panel_js_source, PANEL_JS_UNDER_TEST)
    return sha256(PANEL_JS_UNDER_TEST)


def run_panel_arm(panel_js_source: str, absent: bool = False) -> dict:
    """One Electron run. Returns {ok, failed, checks, observations, errors, rc}."""
    copied = build_page(panel_js_source)
    env = dict(os.environ)
    if absent:
        env['SOTTO_REVIVE_ABSENT'] = '1'
    else:
        env.pop('SOTTO_REVIVE_ABSENT', None)
    out_path = os.path.join(HERE, '_revive-panel.log')
    # A PROFILE OF ITS OWN, PER RUN, and this is not tidiness. Every Electron
    # instance defaults to the SAME userData directory, and this runner ends each
    # arm with `app.exit()`, which skips Chromium's teardown — so the SECOND arm
    # of a run found a half-written disk cache and died before the page loaded:
    # measured, `Gpu Cache Creation failed: -2`, `Unable to create cache`,
    # electron rc=-1, and every check null. That is an environment failure
    # wearing the costume of a wiring failure, which is the worst kind of red.
    profile = os.path.join(HERE, f'_electron-profile-{"absent" if absent else "panel"}')
    shutil.rmtree(profile, ignore_errors=True)
    with open(out_path, 'wb') as out:
        proc = subprocess.Popen(
            [ELECTRON, os.path.join(RENDER_DIR, 'main.js'), '--no-sandbox',
             f'--user-data-dir={profile}', '--disk-cache-size=1'],
            stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW, cwd=RENDER_DIR, env=env)
        rc = proc.wait(timeout=180)
    shutil.rmtree(profile, ignore_errors=True)
    text = read(out_path)
    report = None
    at = text.find('RESULT ')
    if at >= 0:
        try:
            report = json.loads(text[at + len('RESULT '):]
                                .split('\nVERDICT')[0].strip())
        except ValueError:
            report = None
    if report is None:
        return {'ok': False, 'rc': rc, 'failed': ['RESULT_MISSING'],
                'checks': {}, 'observations': {}, 'errors': [text[-400:]],
                'js_sha256': copied}
    report['rc'] = rc
    report['js_sha256'] = copied
    return report


def arm_panel_failures(absent: bool = False, js_source: str = PANEL_JS) -> list[str]:
    kind = 'ABSENT-BRIDGE' if absent else 'PANEL'
    report = run_panel_arm(js_source, absent=absent)
    checks = report.get('checks') or {}
    wanted = [
        'the_panel_markup_is_present',
        'the_footer_is_wired',
        'the_strip_is_wired',
        'the_title_states_the_cost',
        'the_panel_subscribed_to_status',
        'the_death_is_on_screen',
        'one_click_calls_revive_once',
        'the_click_names_itself',
        'the_repair_is_announced',
        'the_announcement_is_on_screen',
        'the_repair_is_not_painted_as_an_error',
        'the_death_is_gone_from_the_footer',
        'the_strip_says_it_too',
        'a_second_click_does_not_stack',
        'the_second_click_says_already',
        'enter_on_the_strip_revives',
    ]
    if absent:
        wanted = ['the_panel_markup_is_present', 'the_footer_is_wired',
                  'a_shell_without_revive_says_so', 'absent_revive_calls_nothing',
                  'absent_revive_says_so']
    bad = [f'ARM-P[{kind}] {k}={checks.get(k)!r}' for k in wanted
           if checks.get(k) is not True]
    for err in report.get('errors') or []:
        bad.append(f'ARM-P[{kind}] page error: {err}')
    if report.get('rc') != 0:
        bad.append(f'ARM-P[{kind}] electron rc={report.get("rc")}')
    return bad


# ---------------------------------------------------------------------------
# ARM S — the shell's own revive, in process
# ---------------------------------------------------------------------------

def load_shell(path: str):
    # The shell imports its SIBLINGS (`hot_reload`) from its own directory, so
    # that directory has to be importable before the module is executed — and
    # `import webview` is deliberately LATE inside the shell, which is what keeps
    # this import from creating a window.
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location('sotto_shell_revive_under_test', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeChild:
    def __init__(self, pid):
        self.pid = pid


class FakeBridge:
    """Stands in for `WorkerBridge`: records the stop, holds the latches."""

    def __init__(self, pid=4242, stop_delay=0.0):
        self.child = FakeChild(pid)
        self.spawns = 7
        self.stop_reason = None
        self.stop_delay = stop_delay
        # THE TWO LATCHES THE REVIVE MUST DROP. `pending_error` is the sticky
        # death the panel shows until a caption proves recovery; `no_audio` is
        # the worker's silence verdict, which is evidence about THIS child.
        self.pending_error = {'state': 'exit', 'text': 'silent-device', 'body': ''}
        self.no_audio = True
        self.no_audio_evidence = {'reason': 'device-rotated', 'peak': 0.0}

    def stop(self, reason='stop'):
        self.stop_reason = reason
        if self.stop_delay:
            time.sleep(self.stop_delay)
        return True


class FakeReloadPolicy:
    def __init__(self):
        self.stopped = 0

    def stop(self):
        self.stopped += 1


def shell_unit_failures() -> list[str]:
    mod = load_shell(SHELL)
    logs: list[str] = []
    painted: list[tuple] = []
    started: list[str] = []

    class FakeShell(mod.SottoShell):
        def __init__(self):
            self._revive_lock = threading.Lock()
            self._revive_thread = None
            self.bridge = FakeBridge(stop_delay=0.5)
            self._reload_policy = FakeReloadPolicy()
            self.first_bridge = self.bridge

        def apply_panel_state(self, text, kind='busy', info=None):
            painted.append((text, kind))
            return True

        def start_worker(self, reason):
            started.append(reason)
            if reason not in self.START_REASONS:
                return False
            self.bridge = FakeBridge(pid=5150)
            return True

    mod.log = lambda message: logs.append(str(message))

    bad: list[str] = []
    shell = FakeShell()

    # The reason must be spawnable at all: a `start_worker` that declines is the
    # silent failure this whole arm exists to catch.
    if 'revive' not in mod.SottoShell.START_REASONS:
        bad.append('ARM-S revive is not in START_REASONS: start_worker would decline')

    accepted = shell.revive_worker(PANEL_CALLER)
    if accepted is not True:
        bad.append(f'ARM-S revive_worker returned {accepted!r}, wanted True')

    # The immediate paint, BEFORE the thread: the panel must never look frozen.
    if not painted or painted[0][1] != 'busy':
        bad.append(f'ARM-S nothing was painted busy before the thread: {painted!r}')
    if painted and painted[0][0] != 'Restarting the pipeline…':
        bad.append(f'ARM-S painted {painted[0][0]!r}, wanted the restart sentence')

    # A SECOND CALL WHILE THE FIRST IS IN FLIGHT. The first bridge's `stop` is
    # held for 0.5 s on purpose, which is the window a double click lands in.
    second = shell.revive_worker(PANEL_CALLER)
    if second is not False:
        bad.append(f'ARM-S a second revive in flight returned {second!r}, wanted False')
    if not one(logs, 'REVIVE_REFUSED reason=already-in-flight'):
        bad.append('ARM-S the refusal was not logged')

    deadline = time.time() + 20
    while shell._revive_thread is not None and time.time() < deadline:
        time.sleep(0.05)

    requested = one(logs, 'REVIVE_REQUESTED')
    if not requested or 'had_bridge=true' not in requested or 'pid=4242' not in requested:
        bad.append(f'ARM-S REVIVE_REQUESTED wrong: {requested!r}')
    if shell.first_bridge.stop_reason != 'revive':
        bad.append(f'ARM-S the old child was stopped with '
                   f'{shell.first_bridge.stop_reason!r}, wanted "revive"')
    if shell.first_bridge.pending_error is not None:
        bad.append('ARM-S pending_error survived the revive: the old death would '
                   'keep being painted')
    if shell.first_bridge.no_audio:
        bad.append('ARM-S no_audio survived the revive: it is evidence about the '
                   'child that was just killed')
    if not one(logs, 'REVIVE_CLEARED pending_error='):
        bad.append('ARM-S dropping the latch was not logged')
    if started != ['revive']:
        bad.append(f'ARM-S start_worker was called {started!r}, wanted ["revive"]')
    if shell._reload_policy.stopped != 1:
        bad.append('ARM-S the hot-reload policy timers were not stopped first '
                   f'(stopped={shell._reload_policy.stopped})')
    done = one(logs, 'REVIVE_DONE')
    if not done or 'started=true' not in done or 'pid=5150' not in done:
        bad.append(f'ARM-S REVIVE_DONE wrong: {done!r}')
    if shell._revive_thread is not None:
        bad.append('ARM-S the in-flight flag was never released')
    # The refusal must not have stacked a second spawn.
    if len(started) != 1:
        bad.append(f'ARM-S the refused click spawned anyway: {started!r}')
    return bad


# ---------------------------------------------------------------------------
# ARM L — the live shell, with a real worker
# ---------------------------------------------------------------------------

def run_live(args: list[str]) -> tuple[list[str], int]:
    if os.path.exists(LIVE_LOG):
        os.remove(LIVE_LOG)
    cmd = [sys.executable, SHELL, '--no-hotkey', '--log', LIVE_LOG, *args]
    with open(os.path.join(HERE, '_revive-live.stdio.log'), 'wb') as out:
        proc = subprocess.Popen(
            cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW, cwd=os.path.dirname(SHELL))
        rc = proc.wait(timeout=400)
    return lines_from(LIVE_LOG), rc


def live_failures(log: list[str], want_revive: bool = True) -> list[str]:
    bad: list[str] = []
    probe = last_json(log, 'REVIVE_PROBE ')
    if not probe:
        return ['ARM-L the real page never reported a REVIVE_PROBE line: the click '
                'path was not measured at all']
    if probe.get('ok') is not True:
        bad.append(f'ARM-L the probe could not press the status: {probe!r}')
    if probe.get('hasRevive') is not True:
        bad.append('ARM-L the real page has no bridge.revive()')
    if 'button' not in json.dumps(probe.get('wired') or {}):
        bad.append(f'ARM-L the status was not wired as a button: {probe.get("wired")!r}')

    if not want_revive:
        # THE CONTROL: the dispatcher's one line is gone, so the page's own post
        # must be REFUSED by the shell. The probe above proves the click still
        # happened, which is what makes this discriminating.
        if not one(log, 'REVIVE_REQUESTED'):
            bad.append('ARM-L[CONTROL] the shell still revived without its dispatch '
                       'entry: the control proves nothing')
        return bad

    requested = one(log, 'REVIVE_REQUESTED')
    done = one(log, 'REVIVE_DONE')
    if not requested:
        bad.append('ARM-L no REVIVE_REQUESTED: the click never reached the shell')
    if not done:
        bad.append('ARM-L no REVIVE_DONE: the revive never finished')
    old = re.search(r'pid=(\d+|none)', requested or '')
    new = re.search(r'pid=(\d+|none)', done or '')
    if not old or not new:
        bad.append(f'ARM-L pid missing from the revive lines: {requested!r} {done!r}')
    else:
        if old.group(1) in ('none', '0'):
            bad.append(f'ARM-L there was no child to kill: {requested!r}')
        if new.group(1) in ('none', '0'):
            bad.append(f'ARM-L no new child after the revive: {done!r}')
        if old.group(1) == new.group(1):
            bad.append(f'ARM-L the pid did NOT change: {old.group(1)} -> '
                       f'{new.group(1)}. That is a no-op, not a revive')
    if 'started=true' not in (done or ''):
        bad.append(f'ARM-L the new worker did not start: {done!r}')

    at = indexes(log, 'REVIVE_DONE')
    req_at = indexes(log, 'REVIVE_REQUESTED')
    # `start_worker` logs its own line BEFORE `_do_revive` logs REVIVE_DONE, so
    # the respawn's proof sits between the two — searching only AFTER the
    # REVIVE_DONE line would look for it in the wrong half of the log.
    start_at = [i for i in indexes(log, 'WORKER_AUTOSTART=started reason=revive')
                if req_at and i > req_at[-1]]
    if not start_at:
        bad.append('ARM-L no WORKER_AUTOSTART=started reason=revive after the kill: '
                   'the respawn did not use the revive reason')
    after = log[(start_at[-1] if start_at else (at[-1] if at else 0)) + 1:]
    new_pid = new.group(1) if new else None
    # WHAT THE NEW CHILD PROVED. A caption is the strongest evidence and needs
    # audio to be playing, which is not something this oracle can arrange; the
    # brief names the fallback for exactly that case — the respawn's own reason
    # line (checked above) plus the worker's own statuses after the kill. The
    # lines that carry that here are the page's receipts (`STATUS_APPLIED`,
    # `PLACEHOLDER_APPLIED`), the bridge's own talk about the NEW pid
    # (`BRIDGE_EXIT pid=<new> ... statuses=<n>`), and the meter/device lines.
    captions_after = [ln for ln in after
                      if re.search(r'CAPTION_APPLIED|BRIDGE_CAPTION_SENT|'
                                   r'CAPTION_OBSERVED', ln)]
    spoke = [ln for ln in after
             if re.search(r'STATUS_APPLIED|PLACEHOLDER_APPLIED|WORKER_STATS|'
                          r'WORKER_STATUS|BRIDGE_STATUS|METER|DEVICE|'
                          r'CAPTURE_STARTED', ln)
             or (new_pid and f'pid={new_pid}' in ln)]
    if not captions_after and not spoke:
        bad.append('ARM-L the new child said nothing after the revive: '
                   f'{after[:6]!r}')
    return bad


def live_observations(log: list[str]) -> dict:
    """What the run actually showed, for the receipt — never a pass/fail."""
    at = indexes(log, 'REVIVE_DONE')
    after = log[at[-1] + 1:] if at else []
    return {
        'captions_after_the_revive': len([ln for ln in after
                                          if 'CAPTION_APPLIED' in ln
                                          or 'BRIDGE_CAPTION_SENT' in ln]),
        'note': 'a caption needs audio to be playing; with nothing routed the '
                'fallback in the brief is used (the respawn reason line plus the '
                'new child\'s own statuses)',
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--panel-only', action='store_true')
    ap.add_argument('--shell-only', action='store_true')
    ap.add_argument('--live-only', action='store_true')
    ap.add_argument('--live-wait', type=float, default=22.0)
    ap.add_argument('--live-exit-after', type=float, default=50.0)
    args = ap.parse_args()

    report: dict = {
        'shell': SHELL, 'shell_sha256': sha256(SHELL)[:16],
        'panel_html': PANEL_HTML, 'panel_sha256': sha256(PANEL_JS)[:16],
    }
    failures: list[str] = []

    if args.neg_arm:
        # (kept simple and loud: see `neg_arm` below)
        return neg_arm(report)

    print(f'shell  : {SHELL}  sha256 {report["shell_sha256"]}')
    print(f'panel  : {PANEL_JS}  sha256 {report["panel_sha256"]}')

    if not (args.shell_only or args.live_only):
        print('\n=== ARM P — the panel, real Chromium, real panel.html ===')
        got = arm_panel_failures()
        report['arm_panel'] = 'RED' if got else 'GREEN'
        failures += got
        print(f'  ARM P: {"RED" if got else "GREEN"}')
        for line in got:
            print('   ' + line)

        print('\n=== ARM P2 — a shell with NO bridge.revive (the honesty arm) ===')
        got = arm_panel_failures(absent=True)
        report['arm_panel_absent'] = 'RED' if got else 'GREEN'
        failures += got
        print(f'  ARM P2: {"RED" if got else "GREEN"}')
        for line in got:
            print('   ' + line)

    if not (args.panel_only or args.live_only):
        print('\n=== ARM S — the shell\'s revive_worker, in process ===')
        got = shell_unit_failures()
        report['arm_shell'] = 'RED' if got else 'GREEN'
        failures += got
        print(f'  ARM S: {"RED" if got else "GREEN"}')
        for line in got:
            print('   ' + line)

    if not (args.panel_only or args.shell_only):
        print(f'\n=== ARM L — the LIVE shell, a real worker, '
              f'press at {args.live_wait:.0f}s ===')
        log, rc = run_live(['--with-worker', '--probe-revive', str(args.live_wait),
                            '--exit-after', str(args.live_exit_after)])
        got = live_failures(log)
        report['arm_live'] = {'verdict': 'RED' if got else 'GREEN', 'rc': rc,
                              'lines': len(log)}
        failures += got
        print(f'  ARM L: {"RED" if got else "GREEN"}  (shell rc={rc}, '
              f'{len(log)} log lines)')
        for line in got:
            print('   ' + line)
        for needle in ('REVIVE_REQUESTED', 'REVIVE_DONE'):
            print(f'   {needle}: {one(log, needle)}')
        print(f'   {live_observations(log)}')

    print()
    print(f'ARMS: panel={report.get("arm_panel")} panel-absent='
          f'{report.get("arm_panel_absent")} shell={report.get("arm_shell")} '
          f'live={report.get("arm_live", {}).get("verdict") if isinstance(report.get("arm_live"), dict) else None}')
    print('VERDICT: ' + ('FAIL' if failures else 'PASS'))
    return 1 if failures else 0


def neg_arm(report: dict) -> int:
    """Both controls in one run: each must go RED on its own one-line mutant."""
    global SHELL
    print('=== NEGATIVE ARM — one line removed, per file, built from TODAY ===')
    failures: list[str] = []

    # CONTROL 1 — the panel: `wireRevive();` gone from panel.js. Everything the
    # panel arm checks about the wiring must then be RED.
    src = read(PANEL_JS)
    mutant_src = src.replace('  wireRevive();\n', '', 1)
    if mutant_src == src:
        print('  CONTROL-1: the panel mutant did not change — the line was not found')
        failures.append('CONTROL-1 the panel mutant did not change')
    else:
        mutant = os.path.join(HERE, '_panel-no-wire-revive.js')
        with open(mutant, 'w', encoding='utf-8', newline='') as fh:
            fh.write(mutant_src)
        if sha256(mutant) == sha256(PANEL_JS):
            failures.append('CONTROL-1 the panel mutant is byte-identical')
        got = arm_panel_failures(js_source=mutant)
        red = [line for line in got if 'the_footer_is_wired' in line
               or 'the_strip_is_wired' in line
               or 'one_click_calls_revive_once' in line]
        print(f'  CONTROL-1 panel minus `wireRevive();` -> '
              f'{"RED" if red else "STILL GREEN"} on {len(red)} check(s)')
        for line in red:
            print('    ' + line)
        if not red:
            failures.append('CONTROL-1 the panel mutant stayed GREEN: the arm '
                            'cannot say no')

    # CONTROL 2 — the shell: its dispatch entry gone. The page still posts (the
    # probe proves the click happened) and the shell must NOT revive.
    src = read(SHELL)
    mutant_shell = src.replace("            'revive': self._revive,\n", '', 1)
    if mutant_shell == src:
        print('  CONTROL-2: the shell mutant did not change — the line was not found')
        failures.append('CONTROL-2 the shell mutant did not change')
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(SHELL)),
                            '_revive-neg-shell.py')
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(mutant_shell)
        if sha256(path) == sha256(SHELL):
            failures.append('CONTROL-2 the shell mutant is byte-identical')
        keep, SHELL = SHELL, path
        try:
            log, rc = run_live(['--no-worker', '--probe-revive', '10',
                                '--exit-after', '30'])
        finally:
            SHELL = keep
            # The mutant lives BESIDE the shell on purpose: the shell imports
            # `hot_reload` from its own directory and builds its asset paths from
            # `__file__`, so a copy in `_main/` dies of ModuleNotFoundError before
            # it writes a single log line — measured, and it looks exactly like
            # "the control found nothing".
            try:
                os.remove(path)
            except OSError:
                pass
        probe = last_json(log, 'REVIVE_PROBE ')
        refused = one(log, "BRIDGE_UNKNOWN_KIND kind='revive'") \
            or one(log, 'BRIDGE_UNKNOWN_KIND kind="revive"')
        revived = one(log, 'REVIVE_REQUESTED')
        print(f'  CONTROL-2 shell minus its dispatch entry -> '
              f'probe_clicked={bool(probe and probe.get("ok"))} '
              f'unknown_kind={bool(refused)} revived={bool(revived)} (rc={rc})')
        if not (probe and probe.get('ok')):
            failures.append('CONTROL-2 the click never happened, so the control '
                            'proves nothing')
        if revived:
            failures.append('CONTROL-2 the shell revived WITHOUT its dispatch entry')
        if not refused:
            failures.append('CONTROL-2 the shell did not even refuse the kind: '
                            'the control is not measuring the dispatch')
        if not failures:
            print('  both controls RED as expected')

    print()
    print('VERDICT: ' + ('PASS' if not failures else 'FAIL'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
