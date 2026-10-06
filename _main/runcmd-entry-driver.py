"""Run `app/webview/run.cmd` the way the OWNER runs it, and assert against the
app's OWN log lines.

WHY THIS EXISTS
    Every lane so far ran the python entry point (`sotto_webview.py`) directly.
    `run.cmd` is the documented entry (`AGENTS.md:71`), it is a one-lane wrapper,
    and it was never executed end to end -- which is exactly where a quoting bug,
    a wrong interpreter or a lost flag hides. This driver runs the wrapper and
    its python control arm and DIFFS them, so a difference in the wrapper is
    visible instead of assumed away.

WHAT IT ASSERTS (from the app's own lines, never from an impression)
    PANEL_VISIBILITY_AT_STARTUP visible=<v>
    PANEL_VISIBILITY_ON_SCREEN  visible=<v>
    HOTKEY_REGISTERED accelerator=... register=... isRegistered=...
    plus, where asked for, BRIDGE_CAPTION_SENT / CAPTION_OBSERVED.

WINDOW CENSUS
    It samples its OWN pid tree every 0.2 s and names every visible top-level
    window. The house governor samples once per 60 s and cannot prove ABSENCE
    of a short-lived window (`AGENTS.md`, measured 2026-10-06) -- so the census
    here is at its own cadence, and the proof is a count of samples, not a
    missing alarm. The census primitives are imported from the existing
    `_main/panel-startup-visibility-oracle.py` rather than reinvented.

    py -3 _main/runcmd-entry-driver.py [--seconds N]
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOTTO = os.path.dirname(HERE)
RUNCMD = os.path.join(SOTTO, 'app', 'webview', 'run.cmd')
SHELL_PY = os.path.join(SOTTO, 'app', 'webview', 'sotto_webview.py')
DEFAULT_LOG = os.path.join(HERE, 'webview-run.log')
ORACLE = os.path.join(HERE, 'panel-startup-visibility-oracle.py')
REPORT_TXT = os.path.join(HERE, 'runcmd-entry-report.txt')
REPORT_JSON = os.path.join(HERE, 'runcmd-entry-report.json')

SAMPLE_S = 0.2
CREATE_NO_WINDOW = 0x08000000

#: Every arm writes its OWN log. A fixed name made a re-run fail with
#: `WinError 32` because the PREVIOUS attempt's detached shell still held the
#: file open (measured) -- a stale lock, not a defect in the wrapper.
RUN_ID = time.strftime('%H%M%S')

_lines: list[str] = []


def log(msg: str) -> None:
    _lines.append(msg)
    print(msg, flush=True)
    with open(REPORT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(_lines) + '\n')


def load_oracle():
    """The census primitives live in a file with dashes in its name, so it is
    loaded by path. It is imported, NOT edited: the instrument stays the one
    the repo already measured."""
    spec = importlib.util.spec_from_file_location('_sotto_vis_oracle', ORACLE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tail_from(path: str, offset: int) -> str:
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        f.seek(offset)
        return f.read().decode('utf-8', 'replace')


def shell_lines(text: str, needle: str) -> list[str]:
    return [ln.split('sotto: ', 1)[-1].strip()
            for ln in text.splitlines() if needle in ln]


def one(text: str, needle: str):
    got = shell_lines(text, needle)
    return got[-1] if got else None


def parse_visible(line):
    if not line or 'visible=' not in line:
        return None
    return line.split('visible=', 1)[1].split()[0] == 'true'


class Census(threading.Thread):
    """Per-pid window census at its OWN cadence (0.2 s), over a live pid set
    that can grow: the wrapper's `start` detaches the shell, so the shell pid
    is discovered from the log and added to the roots mid-flight."""

    def __init__(self, oracle):
        super().__init__(daemon=True)
        self.oracle = oracle
        self.roots = {os.getpid()}
        self.stop = threading.Event()
        self.samples = 0
        self.visible_rows: list = []
        self.names: dict = {}
        self._seen: set = set()
        self._per_key: dict = {}
        self._t0 = time.time()

    def add_root(self, pid: int) -> None:
        self.roots.add(pid)

    def run(self):
        while not self.stop.is_set():
            tree: dict = {}
            for root in list(self.roots):
                tree.update(self.oracle.descendants(root))
            self.names.update(tree)
            elapsed = time.time() - self._t0
            for row in self.oracle.windows_of(set(tree)):
                if row['visible']:
                    self.visible_rows.append(row)
                    key = (row['pid'], row['hwnd'], row['class'])
                    self._per_key[key] = self._per_key.get(key, 0) + 1
                    if key not in self._seen:
                        self._seen.add(key)
                        log(f'CENSUS-VISIBLE t=+{elapsed:.2f}s pid={row["pid"]} '
                            f'hwnd={row["hwnd"]} class={row["class"]!r} '
                            f'unowned={row["unowned"]} '
                            f'exe={tree.get(row["pid"], "?")}')
            self.samples += 1
            self.stop.wait(SAMPLE_S)

    def report(self, arm: str) -> dict:
        rows = sorted({(r['pid'], r['hwnd'], r['class'], r['unowned'])
                       for r in self.visible_rows})
        log(f'CENSUS arm={arm} samples={self.samples} '
            f'roots={sorted(self.roots)} pids_in_tree={sorted(self.names)} '
            f'visible_samples={len(self.visible_rows)} '
            f'visible_distinct={len(rows)} '
            f'rate={len(self.visible_rows)}/{self.samples}')
        for pid, hwnd, cls, unowned in rows:
            n = self._per_key.get((pid, hwnd, cls), 0)
            log(f'CENSUS arm={arm} VISIBLE pid={pid} hwnd={hwnd} '
                f'class={cls!r} unowned={unowned} samples_visible={n} '
                f'exe={self.names.get(pid, "?")}')
        return {'samples': self.samples, 'roots': sorted(self.roots),
                'pids_in_tree': sorted(self.names),
                'visible_samples': len(self.visible_rows),
                'visible_distinct': rows,
                'per_key_samples': {str(k): v for k, v in self._per_key.items()}}


def kill_tree(pid: int) -> str:
    """Kill by exact pid resolved from the shell's OWN log line, never by a
    generic word (`AGENTS.md`: a filter on the bare word `sotto` once killed two
    unrelated processes).

    `errors='replace'` is not cosmetic: `taskkill` writes in the OEM codepage on
    this pt-BR box, and a strict utf-8 decode raised INSIDE the reader thread
    and handed back `stdout=None` (measured, first run of this driver)."""
    try:
        got = subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                             capture_output=True, text=True, errors='replace',
                             creationflags=CREATE_NO_WINDOW, timeout=30)
        return ((got.stdout or '') + (got.stderr or '')).strip().replace('\n', ' | ')
    except Exception as exc:  # noqa: BLE001
        return f'ERROR {exc!r}'


#: PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE -- enough to ask "does this
#: pid exist", without the codepage of `tasklist` in the way.
QUERY_LIMITED = 0x1000
SYNCHRONIZE = 0x00100000
STILL_ACTIVE = 259


def alive(pid: int) -> bool:
    """Native, so no console tool and no codepage can turn a live pid into a
    decode error (measured failure mode of the `tasklist` version)."""
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    h = k32.OpenProcess(QUERY_LIMITED | SYNCHRONIZE, False, int(pid))
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code)):
            return code.value == STILL_ACTIVE
        return False
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


def terminate(pid: int) -> str:
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    h = k32.OpenProcess(0x0001, False, int(pid))  # PROCESS_TERMINATE
    if not h:
        return f'OpenProcess failed err={ctypes.get_last_error()}'
    try:
        ok = k32.TerminateProcess(ctypes.c_void_p(h), 1)
        return f'TerminateProcess ok={bool(ok)}'
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


def cmd_of(pid: int) -> str:
    """The command line of `pid`, read through a .ps1 FILE -- measured on this
    box: the inline `-Command` form of a process-list filter returns EMPTY
    stdout (`AGENTS.md`)."""
    ps = os.path.join(HERE, '_runcmd-cmdline.ps1')
    with open(ps, 'w', encoding='utf-8') as f:
        f.write(f'Get-CimInstance Win32_Process -Filter "ProcessId={pid}" | '
                f'Select-Object -ExpandProperty CommandLine\n')
    try:
        got = subprocess.run(['powershell', '-NoProfile', '-NonInteractive',
                              '-ExecutionPolicy', 'Bypass', '-File', ps],
                             capture_output=True, text=True, errors='replace',
                             creationflags=CREATE_NO_WINDOW, timeout=60)
        return (got.stdout or '').strip()
    except Exception as exc:  # noqa: BLE001
        return f'ERROR {exc!r}'


def arm_owner(oracle, seconds: float) -> dict:
    """THE OWNER'S INVOCATION: `run.cmd` with zero arguments. Exercises the
    DEFAULT branch of the wrapper -- including the quoted `--log` path that the
    header says was tried and REJECTED in normalised form."""
    log('=' * 74)
    log('ARM owner  cmd /c run.cmd   (no arguments -- what double-click does)')
    before = os.path.getsize(DEFAULT_LOG) if os.path.exists(DEFAULT_LOG) else 0
    # The census starts BEFORE the wrapper does: the shell's first log line
    # arrives only once pythonw is up, and the panel's window is created after
    # that, so rooting at discovery is still earlier than the window. Starting
    # it first removes any doubt about the first 300 ms.
    census = Census(oracle)
    census.start()
    started = time.time()
    # THE PIPE IS THE MEASUREMENT BUG, NOT THE WRAPPER'S. `start ""` gives the
    # detached GUI child the parent's handles, so a PIPE stdout stays open for
    # as long as the app runs and `communicate()` waits for EOF, not for exit --
    # measured on the first run of this driver: 60 s "timeout" on a wrapper that
    # had already returned. A FILE plus `wait()` asks the question that was
    # meant: does `run.cmd` RETURN.
    outpath = os.path.join(HERE, 'runcmd-entry-owner.stdout')
    with open(outpath, 'wb') as outfile:
        proc = subprocess.Popen(['cmd', '/c', RUNCMD],
                                cwd=os.path.dirname(RUNCMD),
                                stdout=outfile, stderr=subprocess.STDOUT,
                                creationflags=CREATE_NO_WINDOW)
        try:
            rc = proc.wait(timeout=30)
            returned = True
        except subprocess.TimeoutExpired:
            proc.kill()
            rc, returned = None, False
    out = open(outpath, encoding='utf-8', errors='replace').read()
    log(f'ARM owner run.cmd rc={rc} returned={returned} '
        f'wall={time.time()-started:.2f}s stdout={out.strip()!r}')

    log(f'ARM owner waiting {seconds}s for the shell to settle')
    deadline = time.time() + seconds
    shell_pid = None
    text = ''
    while time.time() < deadline:
        text = tail_from(DEFAULT_LOG, before)
        m = re.search(r'shell=webview2 .*?pid=(\d+)', text)
        if m:
            shell_pid = int(m.group(1))
            census.add_root(shell_pid)
            break
        time.sleep(0.25)
    if shell_pid is None:
        log('ARM owner NO shell line appeared in the default log -- the app '
            'did not start. tail_after_offset=%r' % text[-400:])
        census.stop.set()
        census.join(timeout=5)
        return {'arm': 'owner', 'rc': rc, 'shell_pid': None,
                'census': census.report('owner'), 'no_shell': True}

    log(f'ARM owner shell_pid={shell_pid} cmdline={cmd_of(shell_pid)!r}')
    log(f'ARM owner alive_at_discovery={alive(shell_pid)}')
    # let the panel paint and the navigations run
    remaining = max(0.0, deadline - time.time())
    time.sleep(remaining)
    text = tail_from(DEFAULT_LOG, before)
    at = one(text, 'PANEL_VISIBILITY_AT_STARTUP')
    on = one(text, 'PANEL_VISIBILITY_ON_SCREEN')
    hk = one(text, 'HOTKEY_REGISTERED')
    for name, ln in (('PANEL_VISIBILITY_AT_STARTUP', at),
                     ('PANEL_VISIBILITY_ON_SCREEN', on),
                     ('HOTKEY_REGISTERED', hk)):
        log(f'ARM owner LOG {name}: {ln}')
    log(f'ARM owner HOTKEY_DISABLED present={bool(one(text, "HOTKEY_DISABLED"))}')
    log(f'ARM owner PANEL_SHOWN lines={shell_lines(text, "PANEL_SHOWN")}')
    log(f'ARM owner CAPTION lines={shell_lines(text, "CAPTION")}')
    census_result = census.report('owner')
    census.stop.set()
    census.join(timeout=5)
    log(f'ARM owner killing pid={shell_pid} (resolved from its own log line): '
        f'{kill_tree(shell_pid)}')
    time.sleep(1.0)
    still = alive(shell_pid)
    if still:
        log(f'ARM owner STILL ALIVE after taskkill -> native fallback: '
            f'{terminate(shell_pid)}')
        time.sleep(0.5)
        still = alive(shell_pid)
    log(f'ARM owner shell_alive_after_kill={still}')
    return {'arm': 'owner', 'rc': rc, 'returned': returned,
            'shell_pid': shell_pid,
            'at_startup': at, 'on_screen': on, 'hotkey': hk,
            'at_visible': parse_visible(at), 'on_visible': parse_visible(on),
            'hotkey_registered': bool(hk and 'isRegistered=true' in hk),
            'census': census_result, 'stdout': out.strip(),
            'log_tail': text}


def arm_flagged(oracle, arm: str, argv: list, seconds: float,
                env_extra: dict | None = None) -> dict:
    """An arm whose command line is known, so the shell pid is the direct child
    -- and `--exit-after` makes it END BY ITSELF, which is the only way to see
    a clean exit and its code."""
    alog = os.path.join(HERE, f'runcmd-entry-{arm}-{RUN_ID}.log')
    if os.path.exists(alog):
        os.remove(alog)
    args = list(argv) + ['--log', alog, '--no-hotkey', '--no-hot-reload',
                         '--exit-after', str(seconds)]
    env = dict(os.environ)
    env.update(env_extra or {})
    log('=' * 74)
    log(f'ARM {arm} argv={args}')
    if env_extra:
        log(f'ARM {arm} env_extra={ {k: v for k, v in env_extra.items()} }')
    t0 = time.time()
    outfile = open(alog + '.stdout', 'wb')
    proc = subprocess.Popen(args, stdout=outfile, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=env,
                            cwd=os.path.dirname(RUNCMD),
                            creationflags=CREATE_NO_WINDOW)
    census = Census(oracle)
    census.add_root(proc.pid)
    census.start()
    # `cmd /c run.cmd` returns immediately and the shell it `start`s is
    # DETACHED, so it is not a descendant of this driver: the shell pid comes
    # from the shell's own first log line, exactly as in the owner arm.
    shell_pid = None
    rc = None
    deadline = time.time() + seconds + 240
    text = ''
    while time.time() < deadline:
        # The shell creates the log itself, a second or so in: reading it
        # unconditionally is a FileNotFoundError on the very first poll.
        text = (open(alog, encoding='utf-8', errors='replace').read()
                if os.path.exists(alog) else '')
        if shell_pid is None:
            m = re.search(r'shell=webview2 .*?pid=(\d+)', text)
            if m:
                shell_pid = int(m.group(1))
                census.add_root(shell_pid)
                log(f'ARM {arm} shell_pid={shell_pid} '
                    f'cmdline={cmd_of(shell_pid)!r}')
        if 'SHELL_EXIT' in text:
            break
        if proc.poll() is not None and 'shell=' in text:
            # run.cmd returned and its stdout is closed: nothing more is coming
            # unless the detached shell is still writing, so give it one more
            # poll before giving up.
            time.sleep(0.3)
            text = (open(alog, encoding='utf-8', errors='replace').read()
                    if os.path.exists(alog) else '')
            if 'SHELL_EXIT' in text or shell_pid is None:
                break
        time.sleep(0.25)
    wall = time.time() - t0
    rc = proc.poll()
    outfile.close()
    text = (open(alog, encoding='utf-8', errors='replace').read()
            if os.path.exists(alog) else '')
    rc_out = (open(alog + '.stdout', encoding='utf-8', errors='replace').read()
              if os.path.exists(alog + '.stdout') else '')
    if rc_out.strip():
        log(f'ARM {arm} run.cmd STDOUT: {rc_out.strip()!r}')
    at = one(text, 'PANEL_VISIBILITY_AT_STARTUP')
    on = one(text, 'PANEL_VISIBILITY_ON_SCREEN')
    hk = one(text, 'HOTKEY_REGISTERED')
    caps = shell_lines(text, 'BRIDGE_CAPTION_SENT')
    log(f'ARM {arm} rc={rc} wall={wall:.2f}s')
    log(f'ARM {arm} LOG PANEL_VISIBILITY_AT_STARTUP: {at}')
    log(f'ARM {arm} LOG PANEL_VISIBILITY_ON_SCREEN: {on}')
    log(f'ARM {arm} LOG HOTKEY_REGISTERED: {hk}')
    log(f'ARM {arm} LOG HOTKEY_DISABLED: '
        f'{one(text, "HOTKEY_DISABLED")}')
    log(f'ARM {arm} LOG SHELL_EXIT: {one(text, "SHELL_EXIT")}')
    log(f'ARM {arm} LOG WORKER_AUTOSTART: {one(text, "WORKER_AUTOSTART")}')
    log(f'ARM {arm} LOG BRIDGE_EXIT: {one(text, "BRIDGE_EXIT")}')
    log(f'ARM {arm} LOG RECEIVER_READY: {one(text, "RECEIVER_READY")}')
    log(f'ARM {arm} LOG STAGING_LOADED: {one(text, "STAGING_LOADED")}')
    log(f'ARM {arm} LOG CAPTIONS: n={len(caps)} {caps[:5]}')
    log(f'ARM {arm} LOG PANEL_SHOWN: {shell_lines(text, "PANEL_SHOWN")}')
    for cls in ('BRIDGE_DEATH_LIFTED', 'BRIDGE_STATUS', 'PLACEHOLDER_APPLIED',
                'BRIDGE_WORKER_MISSING'):
        log(f'ARM {arm} LOG {cls}: {shell_lines(text, cls)[:4]}')
    census_result = census.report(arm)
    census.stop.set()
    census.join(timeout=5)
    return {'arm': arm, 'rc': rc, 'wall': round(wall, 2),
            'at_startup': at, 'on_screen': on, 'hotkey': hk,
            'at_visible': parse_visible(at), 'on_visible': parse_visible(on),
            'hotkey_registered': bool(hk and 'isRegistered=true' in hk),
            'hotkey_disabled': one(text, 'HOTKEY_DISABLED'),
            'shell_exit': one(text, 'SHELL_EXIT'),
            'worker_autostart': one(text, 'WORKER_AUTOSTART'),
            'bridge_exit': one(text, 'BRIDGE_EXIT'),
            'captions': caps, 'census': census_result, 'log': text}


def ps_list(needle: str) -> str:
    """A process list, through a .ps1 FILE (the inline `-Command` form returns
    EMPTY stdout on this box)."""
    ps = os.path.join(HERE, '_runcmd-ps.ps1')
    try:
        got = subprocess.run(['powershell', '-NoProfile', '-NonInteractive',
                              '-ExecutionPolicy', 'Bypass', '-File', ps,
                              '-Needle', needle],
                             capture_output=True, text=True, errors='replace',
                             creationflags=CREATE_NO_WINDOW, timeout=60)
        return (got.stdout or '').strip()
    except Exception as exc:  # noqa: BLE001
        return f'ERROR {exc!r}'


def arm_bogus(oracle, seconds: float = 8.0) -> dict:
    """NEGATIVE ARM: an argument `sotto_webview.py` does NOT accept.

    The normal launch goes through pythonw.exe, which has NO stdout; argparse
    fails BEFORE `_open_log` is reached. If nothing surfaces, the documented
    entry point swallows the error entirely -- which is the failure class this
    whole lane exists to find."""
    log('=' * 74)
    log('ARM bogus  cmd /c run.cmd --bogus-flag  (an argument the shell rejects)')
    before = os.path.getsize(DEFAULT_LOG) if os.path.exists(DEFAULT_LOG) else 0
    outpath = os.path.join(HERE, 'runcmd-entry-bogus.stdout')
    with open(outpath, 'wb') as outfile:
        proc = subprocess.Popen(['cmd', '/c', RUNCMD, '--bogus-flag'],
                                cwd=os.path.dirname(RUNCMD),
                                stdout=outfile, stderr=subprocess.STDOUT,
                                creationflags=CREATE_NO_WINDOW)
        rc = proc.wait(timeout=30)
    out = open(outpath, encoding='utf-8', errors='replace').read()
    log(f'ARM bogus run.cmd rc={rc} stdout={out.strip()!r}')
    time.sleep(seconds)
    text = tail_from(DEFAULT_LOG, before)
    log(f'ARM bogus default-log bytes appended={len(text)}')
    log(f'ARM bogus shell line appeared={bool(shell_lines(text, "shell="))}')
    log(f'ARM bogus any text appended={text.strip()[:400]!r}')
    procs = ps_list('bogus-flag')
    log(f'ARM bogus leftover processes matching bogus-flag:\n{procs or "(none)"}')
    return {'arm': 'bogus', 'rc': rc, 'stdout': out.strip(),
            'log_bytes_appended': len(text),
            'shell_started': bool(shell_lines(text, 'shell=')),
            'leftover': procs}


def main() -> int:
    global SAMPLE_S
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=20.0)
    ap.add_argument('--sample', type=float, default=SAMPLE_S,
                    help='census cadence in seconds. The house governor samples '
                         'once per 60 s and cannot prove ABSENCE of a '
                         'short-lived window; a tighter cadence here is the '
                         'only way to size a flash.')
    ap.add_argument('--arms', default='owner,clean,control')
    ap.add_argument('--caption-seconds', type=float, default=90.0)
    args = ap.parse_args()
    SAMPLE_S = args.sample
    wanted = [a for a in args.arms.split(',') if a]

    oracle = load_oracle()
    log(f'RUNCMD-ENTRY driver start='
        f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} '
        f'pid={os.getpid()} python={sys.executable} cwd={os.getcwd()}')
    log(f'RUNCMD-ENTRY run_cmd={RUNCMD} exists={os.path.exists(RUNCMD)}')
    log(f'RUNCMD-ENTRY default_log={DEFAULT_LOG} '
        f'size={os.path.getsize(DEFAULT_LOG) if os.path.exists(DEFAULT_LOG) else None}')
    hwnd = ctypes.WinDLL('kernel32').GetConsoleWindow()
    log(f'RUNCMD-ENTRY driver GetConsoleWindow={hwnd} '
        f'(0 = this harness gives its children no console at all)')
    with open(RUNCMD, 'rb') as f:
        import hashlib
        log(f'RUNCMD-ENTRY run.cmd sha256='
            f'{hashlib.sha256(f.read()).hexdigest()[:16]}')

    results: dict = {}

    if 'help' in wanted:
        log('=' * 74)
        log('ARM help  cmd /c run.cmd --help  (the PRINTING branch -> python.exe)')
        got = subprocess.run(['cmd', '/c', RUNCMD, '--help'],
                             cwd=os.path.dirname(RUNCMD),
                             capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW, timeout=120)
        log(f'ARM help rc={got.returncode}')
        log(f'ARM help stdout>>>\n{got.stdout}')
        log(f'ARM help stderr>>>\n{got.stderr}')
        results['help'] = {'rc': got.returncode, 'stdout': got.stdout,
                           'stderr': got.stderr}

    if 'owner' in wanted:
        results['owner'] = arm_owner(oracle, args.seconds)

    if 'bogus' in wanted:
        results['bogus'] = arm_bogus(oracle)

    if 'clean' in wanted:
        results['clean'] = arm_flagged(
            oracle, 'clean', ['cmd', '/c', RUNCMD], args.seconds)

    if 'control' in wanted:
        results['control'] = arm_flagged(
            oracle, 'control', [sys.executable, SHELL_PY], args.seconds)

    if 'caption' in wanted:
        env_extra = {}
        wav = os.path.join(HERE, 'pt-br-sample.wav')
        if os.path.exists(wav):
            env_extra['SOTTO_AUDIO_FILE'] = wav
        results['caption'] = arm_flagged(
            oracle, 'caption', ['cmd', '/c', RUNCMD, '--with-worker'],
            args.caption_seconds, env_extra)

    log('=' * 74)
    log('DIFF wrapper-vs-python (the two commands must agree)')
    if 'clean' in results and 'control' in results:
        c, k = results['clean'], results['control']
        for field in ('at_visible', 'on_visible', 'rc'):
            same = c.get(field) == k.get(field)
            log(f'DIFF {field}: run.cmd={c.get(field)!r} '
                f'python={k.get(field)!r} -> {"SAME" if same else "DIFFERENT"}')
        log(f'DIFF shell_exit: run.cmd={c.get("shell_exit")!r} '
            f'python={k.get("shell_exit")!r}')

    with open(REPORT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    log(f'RUNCMD-ENTRY report written {REPORT_TXT} and {REPORT_JSON}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
