"""The exit contract of `app/webview/run.cmd` -- asserted on both colours.

WHAT WAS MEASURED, AND BY WHOM (lane SottoRunCmdEntry, 2026-10-06; re-found
nowhere -- this oracle GATES it, it does not re-derive it)
    `run.cmd --bogus-flag` -> rc=0, stdout empty, NO log bytes, NO shell line,
    NO leftover process. argparse rejects the flag and exits 2 on pythonw.exe
    (which has no stdout), `start` reports only its OWN success, so the
    interpreter's status never reaches the caller: a failure answering as
    success.

THE FIX THIS GATES
    run.cmd PRE-FLIGHTS the argument list with the shell's OWN parser
    (`sotto_webview.py --check-args`, hidden from `--help`) and spawns the app
    only when that parse returns 0. `start` is kept, because a wrapper that
    waited for the app would hold the caller's console open for the whole
    session; the child's status is taken in the pre-flight run, which starts
    nothing. There is no second flag table in batch to drift from argparse.

ARMS (each asserts the rc, and the rc alone is not enough evidence for any of
them -- each arm carries a second, independent observation)
    1 bogus          `--bogus-flag`  -> rc 2 (the child's own argparse status,
                                       passed through), wrapper says REFUSED,
                                       a receipt line lands in the run log,
                                       and no shell line and no process appear:
                                       the log proves the app never started.
    2 help           `--help`        -> rc 0, the FULL usage on stdout (every
                                       `add_argument` the shell source declares
                                       is required to appear -- drift-free, and
                                       `--check-args` must NOT appear: the
                                       pre-flight stays hidden).
    3 start-logged   `--log <tmp>`   -> rc 0 and the app really started: the
    4 start-default  (no `--log`)      pid is read from the app's OWN first log
                                       line, that pid must be a live process,
                                       the run must reach its own `SHELL_EXIT`,
                                       and the pid must be GONE at the end.
                                       Armed 3 and 4 cover the wrapper's two
                                       normal branches (explicit `--log` and the
                                       default log).

THE LINE ARMS 3/4 KEY ON (the readiness line a handshake would use)
    `sotto: shell=webview2 pywebview=<v> python=<v> pid=<N>`
    It is the shell's FIRST line, written before any window exists, and it
    carries the pid -- so it is both "the app started" and "which pid to kill".

KILL DISCIPLINE
    Only the pid parsed out of that log line is ever killed (`taskkill /PID`),
    and only if the app has not already exited by itself. NEVER an image name:
    a filter on the generic word has already killed unrelated processes on this
    box (AGENTS.md). `LockDown_Dom.exe` is a FOREIGN process here and is not
    touched -- this oracle never enumerates by name, it only walks ITS OWN pid
    tree. `wmic` is absent on this box, so parentage comes from
    `CreateToolhelp32Snapshot` (th32ParentProcessID), not from wmic.

WINDOWS
    The census samples at our own cadence (the house census samples once per
    60 s and can only prove PRESENCE -- AGENTS.md). The census primitives are
    the ones this repo already measured (`_main/_armE-window-census.py`),
    imported by path. The tracked pid set is MONOTONE and additionally seeded
    from the app's own log line, because the plain tree walk CANNOT see this
    app: the wrapper detaches with `start`, so the app's recorded parent is the
    short-lived cmd.exe that ran run.cmd -- once that exits, a walk of the LIVE
    process table cannot reach the app at all, and a census that only re-walked
    would report "0 visible samples" while the panel was on the screen. Every
    child here is spawned with CREATE_NO_WINDOW.

NEGATIVE ARM (`--neg-arm`)
    Builds a COPY of the tree whose ONLY difference is the wrapper: run.cmd is
    restored from a saved pre-fix copy (`_main/run-cmd-prefix-20261006.cmd`,
    the bytes of the wrapper the defect was measured on), every other file is
    the one under test. All four arms then run against the copy and the verdict
    is INVERTED for arm 1 only: arm 1 must go RED in the copy and arms 2/3/4
    must stay green. If the pre-fix file already carries the pre-flight (or is
    byte-identical to the wrapper under test) the control is DEAD and the
    oracle refuses instead of reporting a green it did not earn.

GAP ARMS (G1..G4, from docs/audit/launch-entry.md §2; lane SottoRunCmdGaps)
    Each gap is asserted as a PAIR against copies of the tree: the FIXED tree
    (AFTER) and a tree whose shell AND wrapper are the saved pre-fix bytes
    (BEFORE), every other file identical. An arm that cannot show the BEFORE
    reading it claims to have fixed is not evidence, so BEFORE is asserted too
    -- it must read 0 (the failure answering as success) where AFTER is
    non-zero. The four levers, and the scripts that produce them:
      G1 panel absent     the copy's app/electron/panel.html is not written;
                          AFTER rc 3, BEFORE 0 (and BEFORE's own app log
                          carries PANEL_MISSING, so the 0 was a lie).
      G2 pywebview gone   a `webview.py` that raises ImportError is shadowed in
                          on PYTHONPATH; AFTER rc 1, BEFORE 0 (and a DIRECT run
                          of the pre-fix shell measures the 1 the wrapper hid).
      G3 hang             the copy's shell is a stub that logs STAGING_LOADED
                          and sleeps forever, never touching the ready file;
                          AFTER rc 4 (HANG) after the bounded wait, BEFORE 0.
      G4 no pythonw       `py` is shadowed to resolve a fake python.exe with NO
                          pythonw.exe beside it; AFTER rc 3 and names the
                          refusal, BEFORE 0 (the console fallback fires).
    SOTTO_READY_BOUND=5 keeps the G3 arm at ~5 s instead of the shipped 30 s.
    Every detached child the arms start is killed by the pid in its OWN log
    line (_kill_log_pid), never by image name.

USAGE
    py -3 _main/run-cmd-exit-oracle.py                 # the wrapper under test
    py -3 _main/run-cmd-exit-oracle.py --neg-arm       # revert-in-a-COPY, RED
    py -3 _main/run-cmd-exit-oracle.py --run-cmd X.cmd # an explicit wrapper
    py -3 _main/run-cmd-exit-oracle.py --no-gaps       # skip the G1..G4 pairs
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
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOTTO = os.path.dirname(HERE)
RUN_CMD = os.path.join(SOTTO, 'app', 'webview', 'run.cmd')
CENSUS_INSTRUMENT = os.path.join(HERE, '_armE-window-census.py')
NEG_SRC = os.path.join(HERE, 'run-cmd-prefix-20261006.cmd')
#: The PRE-FIX shell, saved verbatim from app/webview/sotto_webview.py BEFORE
#: the G1/G2 edits (sha256 45f37917d3e49f8cb92ecc39cc2695832ff84899f9e5164969b498e4c7a3da03).
#: The gap arms need to run the defect, not describe it: G1/G2 live in the
#: SHELL, so the control tree gets this file and the live one is the fixed arm.
PRE_FIX_SHELL = os.path.join(HERE, 'sotto-webview-prefix-20261006.py')
PRE_FIX_WRAPPER = NEG_SRC
#: G3's bound for the arm: SOTTO_READY_BOUND, so the hang arm costs ~5 s not 30.
GAP_BOUND_S = '5'
#: G4's fake interpreter dir: a python.exe (a copy of where.exe: a real exe that
#: exits at once and opens NO window) and NO pythonw.exe beside it.
FAKE_PY_SOURCE = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                              'System32', 'where.exe')
#: A stub "app" that logs the first line, then HANGS before the panel navigation
#: completes -- the exact 2026-10-06 shape (launch-entry.md §3/§4). It never
#: touches the ready file, so the fixed wrapper must time out.
HANG_STUB = '''\
import os
import sys
import time

argv = sys.argv[1:]
log = None
for i, a in enumerate(argv):
    if a == '--log' and i + 1 < len(argv):
        log = argv[i + 1]

# run.cmd calls the SAME file for its bounded readiness poll (`--wait-ready`),
# so a faithful stand-in for the shell must answer that mode too -- without
# this the stub would sleep instead of the wrapper's bound expiring, and run.cmd
# would block for the whole stub sleep (measured: the arm timed out at 120 s).
if '--wait-ready' in argv:
    k = argv.index('--wait-ready')
    path = argv[k + 1] if k + 1 < len(argv) else None
    try:
        bound = float(os.environ.get('SOTTO_READY_BOUND', '30'))
    except ValueError:
        bound = 30.0
    deadline = time.time() + bound
    while True:
        if path and os.path.exists(path):
            sys.exit(0)
        if time.time() >= deadline:
            sys.exit(4)
        time.sleep(0.1)
if '--check-args' in argv:
    sys.exit(0)


def w(line):
    if log:
        d = os.path.dirname(os.path.abspath(log))
        if d:
            os.makedirs(d, exist_ok=True)
        with open(log, 'a', encoding='utf-8') as f:
            f.write(line + '\\n')


w('sotto: shell=webview2 pywebview=stub python=stub pid=%d' % os.getpid())
w('sotto: STAGING_LOADED core=yes -> navigating to panel (G3 STUB never-ready)')
time.sleep(600)
'''

CREATE_NO_WINDOW = 0x08000000
PREFLIGHT_MARK = '--check-args'
RUN_ID = time.strftime('%H%M%S')
#: The shell's first line, and the only source of the pid this oracle kills.
READY_RE = re.compile(r'shell=webview2[^\n]*?\bpid=(\d+)')
SHELL_EXIT_RE = re.compile(r'SHELL_EXIT rc=(-?\d+)')
#: run.cmd's refusal receipt. It was `ARGS_REJECTED` while the pre-flight could
#: only see the argv; G1/G2 make it refuse a MISSING PANEL / MISSING PYWEBVIEW
#: too, so the token now names the event, not the cause.
PREFLIGHT_REFUSED_RE = re.compile(r'sotto: PREFLIGHT_REFUSED rc=(\d+)')
#: run.cmd's HANG receipt (G3).
HANG_RE = re.compile(r'sotto: HANG rc=(\d+)')
#: The readiness boundary the app crosses: the panel navigation completed.
READY_BOUNDARY_RE = re.compile(r'PRELOAD_ACTIVE hasSotto=(?:true|false)')
FLAG_RE = re.compile(r"add_argument\('(--[a-z0-9-]+)'")
#: Flags that must PRINT, and so never reach the pre-flight in run.cmd. They
#: are the reason arm 2 runs the console interpreter at all. The three SUPPRESS
#: flags are the wrapper's own modes: they must stay OUT of `--help`.
HIDDEN_FLAGS = {'--check-args', '--ready-file', '--wait-ready'}


# --------------------------------------------------------------------------
# small file/process helpers
# --------------------------------------------------------------------------
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def text_of(path: str) -> str:
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        return f.read().decode('utf-8', 'replace')


def size_of(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def tail_from(path: str, offset: int) -> str:
    """Only what THIS run appended: the log is shared and a stale line from a
    previous launch must never be mistaken for this one's."""
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        f.seek(offset)
        return f.read().decode('utf-8', 'replace')


def wait_for(path: str, offset: int, pattern, timeout: float):
    """Poll the appended region for `pattern` at our own cadence."""
    deadline = time.time() + timeout
    txt = ''
    while True:
        txt = tail_from(path, offset)
        m = pattern.search(txt)
        if m:
            return m, txt
        if time.time() >= deadline:
            return None, txt
        time.sleep(0.04)


def run_wrapper(run_cmd: str, extra, timeout: float = 120.0,
                capture: bool = True, env: dict | None = None) -> dict:
    """Run the wrapper the way the owner runs it: `cmd /c run.cmd <args>`,
    windowless.

    `capture=False` is REQUIRED for the arms that detach, and the reason is a
    measured one: the detached app INHERITS the wrapper's stdout/stderr handles,
    so a PIPE stays open until the app exits and `subprocess.run` would block
    for the app's whole life -- which then reads as "the wrapper waited for the
    app" when it never did (measured: wrapper_ms=11852 for an 8 s app). With
    DEVNULL there is no pipe to hold, and the call ends when cmd.exe does, so
    `ms` is the wrapper's own wall time.

    `env` is how the gap arms hand the copy a shadowed PATH (G4) or PYTHONPATH
    (G2), and how they shorten G3's bound. Default: the caller's environment.
    """
    argv = ['cmd', '/c', run_cmd] + [str(x) for x in extra]
    sink = subprocess.DEVNULL if not capture else subprocess.PIPE
    t0 = time.time()
    p = subprocess.run(argv, stdout=sink, stderr=sink, text=True,
                       errors='replace', creationflags=CREATE_NO_WINDOW,
                       timeout=timeout, cwd=os.path.dirname(run_cmd),
                       env=env)
    return {'args': [str(x) for x in extra], 'rc': p.returncode,
            'stdout': p.stdout or '', 'stderr': p.stderr or '',
            'ms': int((time.time() - t0) * 1000)}


def load_census_primitives():
    """The census primitives this repo already measured, imported by path (the
    file name has dashes). Imported, never edited: a second implementation
    would be a second answer to "was a window visible"."""
    spec = importlib.util.spec_from_file_location('_sotto_census',
                                                 CENSUS_INSTRUMENT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Census(threading.Thread):
    """Visible top-level windows owned by THIS run's process tree."""

    def __init__(self, root_pid: int, primitives, cadence_s: float):
        super().__init__(daemon=True)
        self.root = root_pid
        self.pr = primitives
        self.cadence = cadence_s
        self.tracked = {root_pid}
        self.samples = 0
        self.visible_samples = 0
        self.hits: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._stop_ev = threading.Event()

    def track(self, pid) -> None:
        if pid:
            with self._lock:
                self.tracked.add(int(pid))

    def snapshot(self) -> dict:
        with self._lock:
            return {'samples': self.samples,
                    'visible_samples': self.visible_samples,
                    'tracked': sorted(self.tracked),
                    'hits': dict(self.hits)}

    def reset_counters(self) -> dict:
        """Zero the counters and the hit table, keep the tracked pids, and
        return what was cleared.

        This exists to separate the ARMS phase (the FIXED app under the FIXED
        wrapper -- a window here is an app defect) from the GAP phase, which
        deliberately runs DEFECTIVE copies: the G4 BEFORE arm starts the app
        under a console interpreter and a console window is the DEFECT working,
        not a regression. Folding the two into one count made the census RED
        read as "the wrapper put a window up" when the arm meant the opposite.
        """
        with self._lock:
            snap = {'samples': self.samples,
                    'visible_samples': self.visible_samples,
                    'tracked': sorted(self.tracked),
                    'hits': dict(self.hits)}
            self.samples = 0
            self.visible_samples = 0
            self.hits = {}
            return snap

    def run(self) -> None:
        while not self._stop_ev.is_set():
            try:
                pids = self.pr.tree(self.root)
            except Exception:  # noqa: BLE001 -- a census must not kill the run
                pids = set()
            with self._lock:
                self.tracked |= pids
                tracked = set(self.tracked)
            wins = [w for w in self.pr.visible_windows() if w[0] in tracked]
            with self._lock:
                self.samples += 1
                if wins:
                    self.visible_samples += 1
                    for pid, hwnd, title, cls in wins:
                        key = f'{pid}:{hwnd}'
                        row = self.hits.setdefault(
                            key, {'pid': pid, 'hwnd': hwnd,
                                  'title': title, 'class': cls, 'n': 0})
                        row['n'] += 1
            time.sleep(self.cadence)

    def stop(self) -> None:
        self._stop_ev.set()
        self.join(timeout=5)


def pid_alive(pr, pid: int) -> bool:
    return any(p == pid for p, _ppid, _exe in pr.process_table())


def pids_in_tree(pr, root: int) -> set:
    return set(pr.tree(root))


def wait_gone(pr, pid: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_alive(pr, pid):
            return True
        time.sleep(0.1)
    return not pid_alive(pr, pid)


def kill_by_pid(pid: int) -> tuple:
    """Kill EXACTLY the pid the app published about itself."""
    out = subprocess.run(['taskkill', '/PID', str(pid), '/F'],
                         capture_output=True, text=True, errors='replace',
                         creationflags=CREATE_NO_WINDOW)
    return out.returncode, ((out.stdout or '') + (out.stderr or '')).strip()


# --------------------------------------------------------------------------
# the arms
# --------------------------------------------------------------------------
def default_log_for(run_cmd: str) -> str:
    """Where the wrapper writes a receipt when the user passed no `--log`:
    `<root>\\_main\\webview-run.log` (`run.cmd`, the `PASSED_LOG` branch)."""
    web = os.path.dirname(os.path.abspath(run_cmd))          # <root>/app/webview
    root = os.path.dirname(os.path.dirname(web))             # <root>
    return os.path.join(root, '_main', 'webview-run.log')


def arm_argv(run_cmd, pr, census, notes) -> dict:
    """THE regression guard for the new gate: every argv set the repo ACTUALLY
    uses must still be accepted by the pre-flight.

    This is the only way the fix can hurt: the pre-flight refuses what argparse
    refuses, so a call site that passes a flag the shell does not know would now
    FAIL where it used to "work" (rc 0, nothing started). Each set below cites
    where it comes from:

      []                             run.cmd with no args (double-click)
      --show --with-worker           app/webview/README.md
      --selftest --log <f>           docs/webview-app-20261006.md
      --exit-after 25                docs/webview-app-20261006.md
      --with-worker --log <f> --no-hotkey --no-hot-reload --exit-after 60
                                     _main/runcmd-entry-driver.py (ARM caption)
      --dump-dom --log <f>           the shell's own measurement path (run.cmd
                                     sends it to python.exe, which never
                                     pre-flights -- asserted here all the same)
      --memory / --opaque            the shell's own flags, same reason
    """
    dummy = os.path.join(HERE, f'_runcmd-argv-arm-{RUN_ID}.log')
    sets = [
        (['no args (double-click)'], []),
        (['README.md: --show --with-worker'], ['--show', '--with-worker']),
        (['webview-app-20261006.md: --selftest --log'],
         ['--selftest', '--log', dummy]),
        (['webview-app-20261006.md: --exit-after 25'],
         ['--exit-after', '25']),
        (['runcmd-entry-driver.py ARM caption'],
         ['--with-worker', '--log', dummy, '--no-hotkey', '--no-hot-reload',
          '--exit-after', '60']),
        (['the --dump-dom measurement path'],
         ['--dump-dom', '--log', dummy]),
        (['the --memory / --opaque flags'], ['--memory']),
        (['the --memory / --opaque flags'], ['--opaque']),
    ]
    checks = []
    rcs = []
    for label, argv in sets:
        res = run_wrapper(run_cmd, ['--check-args'] + argv)
        rcs.append(res['rc'])
        checks.append((f'{label} -> accepted by the pre-flight', res['rc'] == 0,
                       f'rc={res["rc"]} argv={argv}'))
    # A REAL rc, not a synthesis: the first non-zero status any set produced,
    # else 0. `rc` is what the wrapper returned, so it must be a measurement.
    rc = next((r for r in rcs if r != 0), 0)
    return {'name': 'argv', 'args': ['--check-args', 'x8 call sites'],
            'rc': rc, 'expect_rc': 0, 'ms': 0, 'checks': checks}


def arm_bogus(run_cmd, pr, census, notes) -> dict:
    """A rejected flag must NOT answer as success."""
    log = default_log_for(run_cmd)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    before = size_of(log)
    res = run_wrapper(run_cmd, ['--bogus-flag'])
    checks = [('rc == 2 (the child\'s own argparse status, passed through)',
               res['rc'] == 2, f"rc={res['rc']}")]
    console = (res['stdout'] + res['stderr']).strip()
    checks.append(('the wrapper says so on its own console',
                   'REFUSED' in console,
                   console.splitlines()[0] if console else '(no output)'))
    appended = tail_from(log, before)
    m = PREFLIGHT_REFUSED_RE.search(appended)
    checks.append(('a receipt line is appended to the run log '
                   '(before the fix this arm appended NO bytes at all)',
                   bool(m), repr(appended.strip()[:160]) or '(nothing appended)'))
    checks.append(('nothing was started: no `shell=webview2` line appended',
                   'shell=webview2' not in appended,
                   f'appended_bytes={len(appended)}'))
    time.sleep(1.0)
    leftovers = pids_in_tree(pr, os.getpid()) - {os.getpid()}
    checks.append(('no process is left behind in this tree',
                   not leftovers, f'leftovers={sorted(leftovers)}'))
    return {'name': 'bogus', 'args': res['args'], 'rc': res['rc'],
            'expect_rc': 2, 'ms': res['ms'], 'checks': checks,
            'log': log, 'log_appended': appended.strip()[:400]}


def arm_help(run_cmd, pr, census, notes) -> dict:
    """`--help` must still PRINT, and print EVERYTHING."""
    shell = os.path.join(os.path.dirname(os.path.abspath(run_cmd)),
                         'sotto_webview.py')
    declared = sorted(set(FLAG_RE.findall(text_of(shell))))
    visible = [f for f in declared if f not in HIDDEN_FLAGS]
    res = run_wrapper(run_cmd, ['--help'])
    out = res['stdout'] + res['stderr']
    checks = [('rc == 0', res['rc'] == 0, f"rc={res['rc']}")]
    checks.append(('the console interpreter printed the usage header',
                   'usage: sotto-webview' in out,
                   [l for l in out.splitlines() if l.startswith('usage:')][:1]
                   or '(no usage line)'))
    missing = [f for f in visible if f not in out]
    checks.append((f'every flag the shell declares is in the usage '
                   f'({len(visible) - len(missing)}/{len(visible)})',
                   not missing, f'missing={missing}' if missing else 'none missing'))
    leaked = [f for f in declared if f in HIDDEN_FLAGS and f in out]
    checks.append(('the pre-flight switch stays OUT of --help',
                   not leaked, f'leaked={leaked}' if leaked else 'hidden'))
    time.sleep(0.5)
    leftovers = pids_in_tree(pr, os.getpid()) - {os.getpid()}
    checks.append(('no process is left behind in this tree',
                   not leftovers, f'leftovers={sorted(leftovers)}'))
    return {'name': 'help', 'args': res['args'], 'rc': res['rc'],
            'expect_rc': 0, 'ms': res['ms'], 'checks': checks,
            'stdout_bytes': len(out)}


def arm_start(run_cmd, pr, census, notes, name, log, extra, exit_after) -> dict:
    """A normal detached start: rc 0 AND the app really came up, AND it ends
    without a leftover."""
    os.makedirs(os.path.dirname(log), exist_ok=True)
    before = size_of(log)
    res = run_wrapper(run_cmd, extra, capture=False)
    checks = [('rc == 0', res['rc'] == 0, f"rc={res['rc']}")]
    # G3 changed what a launch waits for: the wrapper now waits for READINESS
    # (the bounded handshake), NOT for the app to exit. So the honest bound is
    # "returned before the app's own lifetime elapsed" -- the old "< half the
    # life" bar was written when the wrapper returned instantly. Measured with
    # NO pipe held open by the detached child.
    budget_ms = int(exit_after * 1000)
    checks.append((f'the wrapper returned BEFORE the app exited (the wait is the '
                   f'bounded READINESS handshake, not the {exit_after}s lifetime)',
                   res['ms'] < budget_ms, f"wrapper_ms={res['ms']} "
                   f"app_lives={exit_after}s"))
    m, _txt = wait_for(log, before, READY_RE, timeout=15.0)
    pid = int(m.group(1)) if m else None
    if pid:
        census.track(pid)
    checks.append(('the app\'s OWN first line is in the run log, with its pid',
                   pid is not None,
                   m.group(0)[:120] if m else '(no `shell=webview2 ... pid=` line)'))
    if pid is None:
        return {'name': name, 'args': res['args'], 'rc': res['rc'],
                'expect_rc': 0, 'ms': res['ms'], 'checks': checks, 'log': log,
                'pid': None}
    alive = False
    deadline = time.time() + 5.0
    while time.time() < deadline and not alive:
        alive = pid_alive(pr, pid)
        if not alive:
            time.sleep(0.05)
    checks.append((f'the published pid ({pid}) was a real, running process',
                   alive, f'pid={pid} alive={alive}'))
    em, _ = wait_for(log, before, SHELL_EXIT_RE, timeout=exit_after + 12.0)
    checks.append(('the app reached its own clean exit (SHELL_EXIT line)',
                   em is not None, em.group(0) if em else '(no SHELL_EXIT line)'))
    # The boundary run.cmd's G3 handshake waits on: the wrapper returned only
    # after the app crossed it, so a normal launch cannot time out as a HANG.
    ready_m = READY_BOUNDARY_RE.search(tail_from(log, before))
    checks.append(('the READINESS boundary (PRELOAD_ACTIVE -- what the G3 '
                   'handshake keys on) was crossed in the log',
                   ready_m is not None,
                   ready_m.group(0) if ready_m else '(no PRELOAD_ACTIVE)'))
    gone = wait_gone(pr, pid, timeout=exit_after + 10.0)
    kill_note = ''
    if not gone:
        rc, out = kill_by_pid(pid)
        kill_note = f'(it was still running; taskkill /PID {pid} /F -> rc={rc} {out})'
        gone = wait_gone(pr, pid, 5.0)
    checks.append(('no leftover: the published pid is gone',
                   gone, f'pid={pid} gone={gone} {kill_note}'))
    return {'name': name, 'args': res['args'], 'rc': res['rc'], 'expect_rc': 0,
            'ms': res['ms'], 'checks': checks, 'log': log, 'pid': pid,
            'killed_by_pid': kill_note}


# --------------------------------------------------------------------------
# the gap arms (G1..G4 from docs/audit/launch-entry.md §2)
#
# Each gap is asserted with a PAIR: the FIXED tree (AFTER) and the PRE-FIX tree
# (BEFORE), every other file identical, so the difference between the two is the
# arm's lever and nothing else. An arm that cannot show the BEFORE reading it
# claims to have fixed is not evidence.
# --------------------------------------------------------------------------
PANEL_FILES = ('panel.html', 'panel.css', 'panel.js', 'caption-formulation.js')


def build_tree(notes, variant, shell_src=None, wrapper_src=None,
               drop_panel=False, shadow_webview=False, fake_pythonw=False,
               hang_stub=False):
    """A COPY of the tree for one gap arm, plus the environment that arm needs.

    The copy lives under _main so a failing arm can be inspected, and so a run
    never writes the live tree. The copy's own `_main\\webview-run.log` is its
    receipt (run.cmd's relative default), which is why every arm reads the log
    of ITS copy and never the live one.
    """
    root = tempfile.mkdtemp(prefix=f'_gaps-{variant}-', dir=HERE)
    web = os.path.join(root, 'app', 'webview')
    elec = os.path.join(root, 'app', 'electron')
    for d in (web, elec, os.path.join(root, '_main')):
        os.makedirs(d, exist_ok=True)
    src_web = os.path.join(SOTTO, 'app', 'webview')
    for name in ('hot_reload.py', 'stage.html'):
        shutil.copy2(os.path.join(src_web, name), os.path.join(web, name))
    shutil.copy2(shell_src or os.path.join(src_web, 'sotto_webview.py'),
                 os.path.join(web, 'sotto_webview.py'))
    shutil.copy2(wrapper_src or RUN_CMD, os.path.join(web, 'run.cmd'))
    for name in PANEL_FILES:
        if drop_panel and name == 'panel.html':
            continue
        src = os.path.join(SOTTO, 'app', 'electron', name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(elec, name))
    if hang_stub:
        with open(os.path.join(web, 'sotto_webview.py'), 'w',
                  encoding='utf-8') as f:
            f.write(HANG_STUB)
    env = dict(os.environ)
    env['SOTTO_READY_BOUND'] = GAP_BOUND_S
    if shadow_webview:
        shadow = os.path.join(root, 'shadow')
        os.makedirs(shadow, exist_ok=True)
        with open(os.path.join(shadow, 'webview.py'), 'w',
                  encoding='utf-8') as f:
            f.write('raise ImportError("pywebview is not installed '
                    '(gaps oracle G2)")\n')
        env['PYTHONPATH'] = shadow + os.pathsep + env.get('PYTHONPATH', '')
    if fake_pythonw:
        # A python.exe (a real exe that exits at once and opens NO window) and
        # NO pythonw.exe beside it: the exact state G4's fallback was reachable
        # in, without touching the machine's Python install.
        fake = os.path.join(root, 'fakepy')
        os.makedirs(fake, exist_ok=True)
        shutil.copy2(FAKE_PY_SOURCE, os.path.join(fake, 'python.exe'))
        with open(os.path.join(fake, 'py.cmd'), 'w', encoding='ascii') as f:
            f.write('@echo off\r\necho ' + os.path.join(fake, 'python.exe')
                    + '\r\n')
        env['PATH'] = fake + os.pathsep + env.get('PATH', '')
    notes.append(f'{variant} copy={root}')
    return os.path.join(web, 'run.cmd'), env


def gap_pair(notes, gap, **kw):
    """(AFTER, BEFORE) for one gap: (cmd, env) of the fixed tree and of the
    pre-fix tree (pre-fix shell AND pre-fix wrapper), all else identical."""
    after = build_tree(notes, f'{gap}-after', **kw)
    before_kw = dict(kw)
    before_kw['shell_src'] = PRE_FIX_SHELL
    before_kw['wrapper_src'] = PRE_FIX_WRAPPER
    before = build_tree(notes, f'{gap}-before', **before_kw)
    return after, before


def _app_pid(log: str, timeout: float = 10.0):
    m, _ = wait_for(log, 0, READY_RE, timeout=timeout)
    return int(m.group(1)) if m else None


def arm_gap_panel(notes) -> dict:
    """G1: with app/electron/panel.html absent, `run.cmd --show` must REFUSE."""
    (acmd, aenv), (bcmd, benv) = gap_pair(notes, 'g1', drop_panel=True)
    after = run_wrapper(acmd, ['--show'], env=aenv)
    before = run_wrapper(bcmd, ['--show'], capture=False, env=benv)
    alog, blog = default_log_for(acmd), default_log_for(bcmd)
    _m, btxt = wait_for(blog, 0, re.compile(r'PANEL_MISSING'), timeout=10.0)
    checks = [
        ('AFTER: run.cmd REFUSES the launch (non-zero)',
         after['rc'] != 0, f"rc={after['rc']}"),
        ('AFTER: the refusal is rc 3 -- the SAME status the app exits with',
         after['rc'] == 3,
         f"rc={after['rc']} want=3 stdout={after['stdout'].strip()[:160]!r}"),
        ('AFTER: nothing was started (no shell line in this copy\'s log)',
         'shell=webview2' not in text_of(alog),
         f"log_bytes={size_of(alog)}"),
        ('BEFORE: the pre-fix wrapper answered 0 -- the failure AS SUCCESS',
         before['rc'] == 0, f"rc={before['rc']}"),
        ('BEFORE: the app really did fail (its own log carries PANEL_MISSING)',
         'PANEL_MISSING' in btxt,
         [l for l in btxt.splitlines() if 'PANEL_MISSING' in l][:1]
         or repr(btxt[-160:])),
    ]
    return {'gap': 'G1 panel-absent', 'want': 'non-zero (3); before=0',
            'after': after, 'before': before, 'checks': checks}


def arm_gap_pywebview(notes) -> dict:
    """G2: with `import webview` impossible, `run.cmd --show` must REFUSE."""
    (acmd, aenv), (bcmd, benv) = gap_pair(notes, 'g2', shadow_webview=True)
    after = run_wrapper(acmd, ['--show'], env=aenv)
    before = run_wrapper(bcmd, ['--show'], capture=False, env=benv)
    alog, blog = default_log_for(acmd), default_log_for(bcmd)
    _m, btxt = wait_for(blog, 0, READY_RE, timeout=10.0)
    # What the PRE-FIX shell does with no pywebview, measured DIRECTLY (the
    # traceback is discarded under pythonw, so the wrapper could never see it).
    pre_shell = os.path.join(os.path.dirname(bcmd), 'sotto_webview.py')
    direct = subprocess.run([sys.executable, pre_shell, '--show'],
                            capture_output=True, text=True, errors='replace',
                            creationflags=CREATE_NO_WINDOW, env=benv,
                            timeout=60)
    checks = [
        ('AFTER: run.cmd REFUSES the launch (non-zero)',
         after['rc'] != 0, f"rc={after['rc']}"),
        ('AFTER: the refusal is rc 1 -- the status the app would exit with',
         after['rc'] == 1,
         f"rc={after['rc']} want=1 stdout={after['stdout'].strip()[:160]!r}"),
        ('AFTER: nothing was started (no shell line in this copy\'s log)',
         'shell=webview2' not in text_of(alog),
         f"log_bytes={size_of(alog)}"),
        ('BEFORE: the pre-fix wrapper answered 0 -- the failure AS SUCCESS',
         before['rc'] == 0, f"rc={before['rc']}"),
        ('BEFORE: the app started anyway (pre-fix shell logged its first line)',
         'shell=webview2' in btxt,
         [l for l in btxt.splitlines() if 'shell=webview2' in l][:1] or '(none)'),
        ('BEFORE: the PRE-FIX SHELL exits 1 with no pywebview (measured direct)',
         direct.returncode == 1,
         f"rc={direct.returncode} err_tail="
         f"{direct.stderr.strip().splitlines()[-1:] or ['']}"),
    ]
    return {'gap': 'G2 pywebview-absent', 'want': 'non-zero (1); before=0',
            'after': after, 'before': before, 'checks': checks,
            'direct_pre_fix_shell_rc': direct.returncode}


def _kill_log_pid(log: str) -> str:
    pid = _app_pid(log, timeout=3.0)
    if pid is None:
        return '(no pid in log)'
    rc, out = kill_by_pid(pid)
    return f'taskkill /PID {pid} /F -> rc={rc}'


def active_lines(text: str) -> list:
    """The non-REM, non-blank lines of a batch file.

    A needle quoted inside a COMMENT is not code: this lane's run.cmd quotes the
    REMOVED fallback line in a REM, so a plain substring test on the whole file
    would report the fix absent while it is present and the comment is only
    explaining it.
    """
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().upper().startswith('REM')]


def arm_gap_hang(notes) -> dict:
    """G3: an app that never comes up must report a HANG, not 0."""
    (acmd, aenv), (bcmd, benv) = gap_pair(notes, 'g3', hang_stub=True)
    after = run_wrapper(acmd, ['--show'], capture=False, env=aenv)
    alog, blog = default_log_for(acmd), default_log_for(bcmd)
    # The wrapper appends its HANG receipt right before it returns; wait for it
    # rather than racing the read.
    wait_for(alog, 0, re.compile(r'HANG rc=4'), timeout=5.0)
    atxt = text_of(alog)
    hang_note = _kill_log_pid(alog)
    before = run_wrapper(bcmd, ['--show'], capture=False, env=benv)
    # The stub is DETACHED, so its line is NOT in the log when the wrapper
    # returns: wait for it. (The first version of this arm read at once and saw
    # an empty log -- the BEFORE check went red for a read race, not a defect.)
    wait_for(blog, 0, re.compile(r'STAGING_LOADED'), timeout=10.0)
    btxt = text_of(blog)
    before_note = _kill_log_pid(blog)
    hang_line = [l for l in atxt.splitlines() if HANG_RE.search(l)][:1]
    checks = [
        ('AFTER: run.cmd reports a HANG -- rc 4, not 0',
         after['rc'] == 4, f"rc={after['rc']} want=4 ms={after['ms']}"),
        ('AFTER: the wrapper wrote its OWN HANG receipt to the run log',
         bool(hang_line), hang_line or '(no HANG receipt)'),
        ('AFTER: the app really had been started and never came up '
         '(STAGING_LOADED, no ready file, no PRELOAD_ACTIVE)',
         'STAGING_LOADED' in atxt and 'PRELOAD_ACTIVE' not in atxt,
         repr([l for l in atxt.splitlines() if 'STAGING_LOADED' in l][:1])),
        ('BEFORE: the pre-fix wrapper answered 0 for the SAME hang',
         before['rc'] == 0, f"rc={before['rc']}"),
        ('BEFORE: the same stub had been started and never came up',
         'STAGING_LOADED' in btxt,
         repr([l for l in btxt.splitlines() if 'STAGING_LOADED' in l][:1])
         or '(stub never logged)'),
    ]
    return {'gap': 'G3 hang', 'want': 'non-zero (4); before=0',
            'after': after, 'before': before, 'checks': checks,
            'killed': [hang_note, before_note]}


def arm_gap_console(notes) -> dict:
    """G4: with no pythonw.exe, run.cmd must refuse -- never fall back to a
    console interpreter."""
    (acmd, aenv), (bcmd, benv) = gap_pair(notes, 'g4', fake_pythonw=True)
    after = run_wrapper(acmd, ['--show'], env=aenv)
    before = run_wrapper(bcmd, ['--show'], capture=False, env=benv)
    atxt, btxt = text_of(acmd), text_of(bcmd)
    alog = default_log_for(acmd)
    checks = [
        ('AFTER: run.cmd exits 3 when pythonw.exe is absent',
         after['rc'] == 3,
         f"rc={after['rc']} want=3 ms={after['ms']}"),
        ('AFTER: it NAMES the refusal, so the owner is not left guessing',
         'no pythonw' in after['stdout'] and 'console' in after['stdout'],
         after['stdout'].strip().splitlines()[:2] or '(no output)'),
        ('AFTER: nothing was started (no shell line in this copy\'s log)',
         'shell=webview2' not in text_of(alog),
         f"log_bytes={size_of(alog)}"),
        ('AFTER: the fallback assignment is GONE from the wrapper under test '
         '(checked on the ACTIVE lines -- a REM quoting it does not count)',
         'set "PYW=%PYEXE%"' not in active_lines(atxt),
         'absent' if 'set "PYW=%PYEXE%"' not in active_lines(atxt)
         else 'STILL PRESENT as code'),
        ('BEFORE: the pre-fix wrapper still carries the console fallback',
         'if not exist "%PYW%" set "PYW=%PYEXE%"' in btxt,
         'present (the defect)' if 'if not exist "%PYW%" set "PYW=%PYEXE%"'
         in btxt else 'MISSING -- control is dead'),
        ('BEFORE: it proceeded past the missing pythonw and answered 0',
         before['rc'] == 0, f"rc={before['rc']}"),
    ]
    return {'gap': 'G4 console-fallback', 'want': 'non-zero (3); before=0',
            'after': after, 'before': before, 'checks': checks}


def print_gaps(gaps) -> None:
    for g in gaps:
        ok = all(c[1] for c in g['checks'])
        print(f'GAP {g["gap"]:<22} {"PASS" if ok else "FAIL"} want={g["want"]}')
        for side in ('after', 'before'):
            r = g[side]
            print(f'  {side:<6} rc={r["rc"]} ms={r["ms"]} args={r["args"]}')
        for name, cok, ev in g['checks']:
            print(f'    [{"ok" if cok else "NO"}] {name} :: {ev}')


# --------------------------------------------------------------------------
# the negative arm: revert the wrapper in a COPY
# --------------------------------------------------------------------------
def build_reverted_copy(neg_src: str, notes: list) -> str:
    """A copy of the tree whose ONLY difference is the wrapper.

    Every other file is the one under test, so an arm that goes RED in the copy
    went red because of the reverted wrapper and nothing else -- which is the
    whole point of a negative control. The bytes of run.cmd are copied
    verbatim (no re-encode), and a control that has stopped being a control is
    REFUSED rather than run.
    """
    if not os.path.exists(neg_src):
        raise SystemExit(f'NEGATIVE ARM: --neg-src {neg_src} does not exist')
    reverted = text_of(neg_src)
    fixed = text_of(RUN_CMD)
    if PREFLIGHT_MARK in reverted:
        raise SystemExit(f'NEGATIVE ARM: CONTROL DEAD -- {neg_src} already '
                         f'contains {PREFLIGHT_MARK}; it is not the pre-fix '
                         f'wrapper, so its arm 1 could not go RED')
    if reverted == fixed:
        raise SystemExit('NEGATIVE ARM: CONTROL DEAD -- the copy would be '
                         'byte-identical to the wrapper under test')
    root = tempfile.mkdtemp(prefix='sotto-runcmd-neg-')
    web = os.path.join(root, 'app', 'webview')
    elec = os.path.join(root, 'app', 'electron')
    for d in (web, elec, os.path.join(root, '_main')):
        os.makedirs(d, exist_ok=True)
    for name in ('sotto_webview.py', 'hot_reload.py', 'stage.html'):
        shutil.copy2(os.path.join(SOTTO, 'app', 'webview', name),
                     os.path.join(web, name))
    for name in ('panel.html', 'panel.css', 'panel.js', 'caption-formulation.js'):
        shutil.copy2(os.path.join(SOTTO, 'app', 'electron', name),
                     os.path.join(elec, name))
    shutil.copyfile(neg_src, os.path.join(web, 'run.cmd'))
    notes.append(f'copy={root}')
    notes.append(f'copy_run_cmd_sha256={sha256(os.path.join(web, "run.cmd"))}')
    notes.append(f'neg_src={neg_src}')
    notes.append(f'neg_src_sha256={sha256(neg_src)}')
    return os.path.join(web, 'run.cmd')


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description='Assert run.cmd\'s exit contract on both colours.')
    ap.add_argument('--run-cmd', default=RUN_CMD,
                    help='wrapper under test (default: the live app entry)')
    ap.add_argument('--label', default=None)
    ap.add_argument('--neg-arm', action='store_true',
                    help='revert the wrapper in a COPY and require arm 1 RED')
    ap.add_argument('--neg-src', default=NEG_SRC,
                    help='the pre-fix wrapper the copy is built from')
    ap.add_argument('--exit-after', type=float, default=8.0,
                    help='seconds each normal-start arm lets the app live')
    ap.add_argument('--cadence-ms', type=int, default=100)
    ap.add_argument('--json', default=None, help='receipt path')
    ap.add_argument('--no-gaps', action='store_true',
                    help='skip the G1..G4 before/after arms')
    a = ap.parse_args()

    notes: list = []
    label = a.label or ('neg-arm' if a.neg_arm else 'fixed')
    run_cmd = os.path.abspath(a.run_cmd)
    if a.neg_arm:
        run_cmd = build_reverted_copy(a.neg_src, notes)
    if not os.path.exists(run_cmd):
        print(f'VERDICT FAIL  wrapper not found: {run_cmd}')
        return 1

    pr = load_census_primitives()
    census = Census(os.getpid(), pr, a.cadence_ms / 1000.0)
    census.start()

    print(f'RUN-CMD EXIT ORACLE label={label} pid={os.getpid()}')
    print(f'RUN-CMD run_cmd={run_cmd}')
    print(f'RUN-CMD run_cmd_sha256={sha256(run_cmd)}')
    print(f'RUN-CMD under_test_sha256={sha256(RUN_CMD)}'
          f' (the live wrapper; equal means "the fix is under test")')
    for n in notes:
        print(f'RUN-CMD {n}')
    print(f'RUN-CMD preflight_in_under_test='
          f'{PREFLIGHT_MARK in text_of(run_cmd)}')
    # The census conjunct is about the APP, not the wrapper, so the APP's own
    # bytes are pinned here too: a census RED that cannot name the shell it
    # measured is an accusation nobody can refute.
    shell = os.path.join(os.path.dirname(run_cmd), 'sotto_webview.py')
    print(f'RUN-CMD shell_sha256={sha256(shell) if os.path.exists(shell) else "(absent)"}'
          f' shell_mtime={int(os.path.getmtime(shell)) if os.path.exists(shell) else 0}')

    shared_log = default_log_for(run_cmd)
    arm_log = os.path.join(os.path.dirname(shared_log),
                           f'run-cmd-exit-oracle-{label}-{RUN_ID}.log')

    arms = []
    arms.append(arm_argv(run_cmd, pr, census, notes))
    for arm in arms:
        _print_arm(arm)
    arms.append(arm_bogus(run_cmd, pr, census, notes))
    _print_arm(arms[-1])
    arms.append(arm_help(run_cmd, pr, census, notes))
    _print_arm(arms[-1])
    arms.append(arm_start(run_cmd, pr, census, notes, 'start-logged', arm_log,
                          ['--log', arm_log, '--no-hotkey', '--no-hot-reload',
                           '--exit-after', a.exit_after], a.exit_after))
    _print_arm(arms[-1])
    arms.append(arm_start(run_cmd, pr, census, notes, 'start-default', shared_log,
                          ['--no-hotkey', '--no-hot-reload',
                           '--exit-after', a.exit_after], a.exit_after))
    _print_arm(arms[-1])

    # The ARMS are done. The census so far is the app-under-the-FIXED-wrapper's
    # own window behaviour, so snapshot it HERE, before the gap arms
    # deliberately run DEFECTIVE copies (G4's BEFORE starts the app under a
    # console interpreter; a console window there is the defect working).
    time.sleep(0.5)
    snap_arms = census.snapshot()
    census.reset_counters()

    # ---- the four gap arms (each with a BEFORE, in a pre-fix copy) ---------
    gaps: list = []
    if not a.no_gaps:
        print('GAPS the before/after pairs of docs/audit/launch-entry.md §2 '
              '(BEFORE = a copy whose shell+wrapper are the pre-fix bytes)')
        for fn in (arm_gap_panel, arm_gap_pywebview, arm_gap_hang,
                   arm_gap_console):
            g = fn(notes)
            gaps.append(g)
            print_gaps([g])

    time.sleep(0.5)
    snap_gaps = census.snapshot()
    census.stop()

    print(f'CENSUS cadence_ms={a.cadence_ms} samples={snap_arms["samples"]} '
          f'visible_samples={snap_arms["visible_samples"]} '
          f'tracked_pids={len(snap_arms["tracked"])}')
    for key, row in snap_arms['hits'].items():
        print(f'CENSUS ALERTA-JANELA {key} pid={row["pid"]} hwnd={row["hwnd"]} '
              f'title={row["title"]!r} class={row["class"]!r} n={row["n"]}')
    census_ok = snap_arms['visible_samples'] == 0 and snap_arms['samples'] > 0
    print(f'CENSUS-GAPS samples={snap_gaps["samples"]} '
          f'visible_samples={snap_gaps["visible_samples"]} '
          f'(the gap phase, where a window is the DEFECT being demonstrated)')
    for key, row in snap_gaps['hits'].items():
        print(f'CENSUS-GAPS ALERTA-JANELA {key} pid={row["pid"]} '
              f'hwnd={row["hwnd"]} title={row["title"]!r} '
              f'class={row["class"]!r} n={row["n"]}')
    if snap_gaps['visible_samples']:
        print('CENSUS-GAPS NOTE: a window in THIS phase is the G4 BEFORE arm '
              'working -- it starts the app under a CONSOLE interpreter, and '
              'the console window is exactly the defect G4 removes. The AFTER '
              'arms must show none.')

    results = {arm['name']: arm for arm in arms}
    failed = [n for n, arm in results.items()
              if not all(ok for _nm, ok, _ev in arm['checks'])]
    if census_ok:
        print(f'CENSUS OK: no visible window in {snap_arms["samples"]} samples '
              f'of this run\'s own pids during the ARMS phase (the census '
              f'primitives are the repo\'s)')
    else:
        print(f'CENSUS RED: {snap_arms["visible_samples"]} of '
              f'{snap_arms["samples"]} samples had a VISIBLE window in this '
              f'run\'s tree during the ARMS phase')

    # The two conjuncts are reported SEPARATELY, and the verdict names the one
    # that failed. They fail for different reasons and a reader must never take
    # one for the other: the arms are this wrapper's exit contract, while a
    # census RED is the APP putting its panel on the screen for ~1 sample
    # (measured 2026-10-06: 2 of 5 starts, ~50 ms, at +0.8 s after the app's
    # first line -- an app-side startup race, not a wrapper behaviour).
    if a.neg_arm:
        fired = 'bogus' in failed
        others_ok = not [n for n in failed if n != 'bogus']
        arms_ok = fired and others_ok
        arms_reason = (f'arm1(bogus) RED-as-expected={fired} '
                       f'arms2-4-still-green={others_ok} '
                       f'failed={sorted(failed)}')
    else:
        arms_ok = not failed
        arms_reason = ('all 4 arms green' if arms_ok
                       else f'failed arms={sorted(failed)}')
    census_reason = (f'{snap_arms["samples"]} samples, '
                     f'{snap_arms["visible_samples"]} with a visible window')
    gaps_failed = [g['gap'] for g in gaps
                   if not all(c[1] for c in g['checks'])]
    gaps_ok = not gaps_failed
    gaps_reason = ('all 4 gaps green (AFTER non-zero, BEFORE 0)' if gaps_ok
                   else f'failed gaps={gaps_failed}')
    print(f'ARM-VERDICT    {"PASS" if arms_ok else "FAIL"}  {arms_reason}')
    if a.neg_arm and PREFLIGHT_MARK not in text_of(run_cmd):
        print('ARM-NOTE       the argv arm is VACUOUS in this copy: the pre-fix '
              'wrapper has no pre-flight, so no argv set can be refused by it '
              '(that is what the fix adds). Only arm 1 carries the signal here.')
    if gaps:
        print(f'GAP-VERDICT    {"PASS" if gaps_ok else "FAIL"}  {gaps_reason}')
    print(f'CENSUS-VERDICT {"PASS" if census_ok else "FAIL"}  {census_reason}')
    print(f'ARM-RCS ' + ' '.join(
        f'{n}={results[n]["rc"]}(want {results[n]["expect_rc"]})'
        for n in ('bogus', 'help', 'start-logged', 'start-default',
                  'argv')))
    for g in gaps:
        print(f'GAP-RCS {g["gap"]:<22} after={g["after"]["rc"]} '
              f'before={g["before"]["rc"]}')
    verdict_ok = arms_ok and census_ok and gaps_ok
    why = ('all conjuncts green' if verdict_ok else
           'arms=' + ('PASS' if arms_ok else 'FAIL') +
           ' gaps=' + ('PASS' if gaps_ok else 'FAIL') +
           ' census=' + ('PASS' if census_ok else 'FAIL') +
           ' -> ' + ('a VISIBLE window was measured (app-side, see CENSUS '
                     'ALERTA-JANELA above)' if not census_ok else
                     'the arms/gaps failed (see the [NO] lines above)'))
    print(f'VERDICT {"PASS" if verdict_ok else "FAIL"}  {why}')

    receipt_path = a.json or os.path.join(
        HERE, f'run-cmd-exit-oracle-{label}.json')
    with open(receipt_path, 'w', encoding='utf-8') as f:
        json.dump({'label': label, 'run_cmd': run_cmd,
                   'run_cmd_sha256': sha256(run_cmd),
                   'under_test_sha256': sha256(RUN_CMD),
                   'preflight_in_under_test': PREFLIGHT_MARK in text_of(run_cmd),
                   'notes': notes, 'arms': arms, 'gaps': gaps,
                   'census': snap_arms, 'census_gaps': snap_gaps,
                   'arms_ok': arms_ok, 'gaps_ok': gaps_ok, 'census_ok': census_ok,
                   'arm_verdict': 'PASS' if arms_ok else 'FAIL',
                   'gap_verdict': 'PASS' if gaps_ok else 'FAIL',
                   'census_verdict': 'PASS' if census_ok else 'FAIL',
                   'verdict': 'PASS' if verdict_ok else 'FAIL',
                   'reason': why}, f, indent=2)
    print(f'RECEIPT {receipt_path}')
    return 0 if verdict_ok else 1


def _print_arm(arm: dict) -> None:
    ok = all(c[1] for c in arm['checks'])
    head = (f'ARM {arm["name"]:<13} rc={arm["rc"]} '
            f'want={arm["expect_rc"]} ms={arm["ms"]} '
            f'{"PASS" if ok else "FAIL"}')
    if arm.get('pid'):
        head += f' pid={arm["pid"]}'
    print(head)
    for name, cok, ev in arm['checks']:
        print(f'    [{"ok" if cok else "NO"}] {name} :: {ev}')


if __name__ == '__main__':
    sys.exit(main())
