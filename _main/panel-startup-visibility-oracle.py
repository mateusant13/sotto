"""ORACLE: is the Sotto panel ON THE OWNER'S SCREEN at startup?

The question, verbatim from the lane that could not close it
(`_main/SottoExit3Panel.md` §5.6):

    "ALERTA-JANELA ts=2026-10-06T06:54:22Z chave=6724:29693352 pid=6724
     nome=pythonw caiu DENTRO da janela de execucao do meu oracle ... o censo
     regista pid/hwnd/nome e NAO o titulo, o pid ja nao existia para
     interrogar ... Se aquela janela era o painel, entao o APP mostra o painel
     no arranque, contra o 'start hidden' do run.cmd."

This oracle does not argue about it. It runs the REAL entry point that
`app/webview/run.cmd` launches and reads the shell's own two measurements:

    PANEL_VISIBILITY_AT_STARTUP visible=<bool>   the instant the window exists
    PANEL_VISIBILITY_ON_SCREEN  visible=<bool>   once the startup sequence settled

FIVE ARMS, one command. Both colours of the same line come out of ONE
invocation, so a green cannot be a green-by-environment:

  ARM P  the real `app/webview/sotto_webview.py`, no flags that change
         visibility. Both lines must read `visible=false` — `run.cmd` promises
         "start hidden", and this is the arm that answers the brief.
  ARM B  the BEFORE half of the pair: the same file with the CURE taken out
         (the navigation-start re-assert, one line), off-screen. Its
         `PANEL_VISIBILITY_ON_SCREEN` line must read `visible=true`. This is
         the arm that would have caught the defect without a re-run.
  ARM S  a COPY of the live shell moved OFF-SCREEN (x=-10000), run with
         `--show`. POSITIVE CONTROL: the panel the owner explicitly asked for
         must still be visible, so a "fix" that hides the panel for ever is
         caught here. Off-screen only because the owner asked to never have a
         window on his desk; `--show` is otherwise the app's own flag.
  ARM N  a COPY with the hide REMOVED (`hidden=True` -> `hidden=False`), run
         with the app's own `--opaque`. Its `PANEL_VISIBILITY_AT_STARTUP` line
         must read `visible=true`, or the log is a constant and measures
         nothing. Also off-screen, for the same reason.
  ARM N2 the same copy WITHOUT `--opaque`, i.e. with pywebview's transparent
         branch (winforms.py:783-787) in the way. Reported because it is what
         tells "the hide was removed" apart from "pywebview's transparency hack
         hid it anyway"; N2 is why N needs `--opaque`, and it says so itself.

The copies are BUILT from the live shell at run time and their sha256 is
written to the log, so a negative arm cannot silently go stale. They MUST live
beside the live shell: `sotto_webview.py` resolves `hot_reload`, `stage.html`
and the panel from `os.path.dirname(__file__)`, so a copy elsewhere would not
be the same program. They are deleted at the end of the run.

EVERY arm is watched by TWO censuses at once:

  * the HOUSE census (`I:\!manager\scripts\window-census.ps1`) run with a
    PRIVATE log and state, so the shared log is not polluted and there is no
    race with the 60 s scheduled task. It names a pid only when a new pid
    brings a window — which is why the second instrument exists;
  * a per-pid window census over the shell's OWN pid and every descendant,
    sampling every 200 ms and printing the pid, the exe, the window CLASS and
    `visible`. The class is what the house census cannot report (it reads no
    class and no title) and it is what tells a WinForms panel apart from a
    dialog, a tooltip or a WebView2 helper. `main_hwnd` mirrors .NET's
    `Process.MainWindowHandle` — the first top-level window with a null owner
    AND `IsWindowVisible` — i.e. exactly the condition that raises
    ALERTA-JANELA.

SAFETY: launched with pythonw.exe (a GUI-subsystem binary: no console is
allocated) and every child is spawned with CREATE_NO_WINDOW. Every arm EXCEPT
ARM P runs a copy moved off-screen; ARM P is the real thing, and running it is
precisely how the defect under test is observed.
Usage:  pythonw.exe _main/panel-startup-visibility-oracle.py [arm-seconds]
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
#: Generated variants MUST sit beside the live shell (see the module docstring).
VARIANT_DIR = os.path.dirname(SHELL)
OFFSCREEN_SHELL = os.path.join(VARIANT_DIR, '_probe-offscreen-sotto_webview.py')
NEG_SHELL = os.path.join(VARIANT_DIR, '_probe-neg-arm-sotto_webview.py')
PRECURE_SHELL = os.path.join(VARIANT_DIR, '_probe-pre-cure-sotto_webview.py')
LOG = os.path.join(HERE, 'panel-startup-visibility.log')
CENSUS = r'I:\!manager\scripts\window-census.ps1'

CREATE_NO_WINDOW = 0x08000000
GW_OWNER = 4
SAMPLE_S = 0.2

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_lines: list[str] = []


def log(msg: str) -> None:
    _lines.append(msg)
    with open(LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(_lines) + '\n')


# ---------------------------------------------------------------------------
# process tree (Toolhelp32) — the shell spawns WebView2 helpers, and a helper's
# window is a window on the owner's screen too
# ---------------------------------------------------------------------------

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD),
                ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
                ('th32ModuleID', wintypes.DWORD),
                ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD),
                ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', wintypes.DWORD),
                ('szExeFile', ctypes.c_char * 260)]


def process_table() -> dict:
    """{pid: (parent_pid, exe_name)} for the whole box."""
    out: dict = {}
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return out
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = kernel32.Process32First(snap, ctypes.byref(entry))
        while ok:
            out[entry.th32ProcessID] = (entry.th32ParentProcessID,
                                        entry.szExeFile.decode('mbcs', 'replace'))
            ok = kernel32.Process32Next(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return out


def descendants(root: int) -> dict:
    """{pid: exe} for `root` and every descendant of it."""
    table = process_table()
    kids: dict = {}
    for pid, (parent, _exe) in table.items():
        kids.setdefault(parent, []).append(pid)
    seen: dict = {}
    frontier = [root]
    while frontier:
        pid = frontier.pop()
        if pid in seen:
            continue
        seen[pid] = table.get(pid, (0, '?'))[1]
        frontier.extend(kids.get(pid, ()))
    return seen


# ---------------------------------------------------------------------------
# the census channel: top-level windows, by pid
# ---------------------------------------------------------------------------

def window_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    return buf.value


def windows_of(pids: set) -> list:
    rows: list = []

    def cb(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids:
            return True
        rows.append({
            'pid': int(pid.value),
            'hwnd': int(hwnd),
            'class': window_class(hwnd),
            'visible': bool(user32.IsWindowVisible(hwnd)),
            'unowned': int(user32.GetWindow(hwnd, GW_OWNER) or 0) == 0,
        })
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return rows


class Sampler(threading.Thread):
    """The per-pid census: which windows does THIS pid tree own, and are any of
    them visible? Every sample names the pid and the window CLASS."""

    def __init__(self, root_pid: int, arm: str):
        super().__init__(daemon=True)
        self.root = root_pid
        self.arm = arm
        self.stop = threading.Event()
        self.samples = 0
        self.visible_rows: list = []
        self.main_by_pid: dict = {}
        self.names: dict = {}
        self._seen_keys: set = set()

    def run(self):
        while not self.stop.is_set():
            tree = descendants(self.root)
            self.names.update(tree)
            rows = windows_of(set(tree))
            self.samples += 1
            for row in rows:
                if not row['visible']:
                    continue
                if row['unowned']:
                    self.main_by_pid[row['pid']] = row['hwnd']
                self.visible_rows.append(row)
                key = (row['pid'], row['hwnd'], row['class'])
                if key not in self._seen_keys:
                    self._seen_keys.add(key)
                    log(f'CENSUS-VISIBLE arm={self.arm} pid={row["pid"]} '
                        f'hwnd={row["hwnd"]} class={row["class"]} '
                        f'unowned={str(row["unowned"]).lower()} '
                        f'exe={tree.get(row["pid"], "?")}')
            self.stop.wait(SAMPLE_S)

    def report(self):
        root_main = self.main_by_pid.get(self.root, 0)
        log(f'CENSUS-PID arm={self.arm} samples={self.samples} '
            f'pid={self.root} name={self.names.get(self.root, "?")} '
            f'main_hwnd={root_main} '
            f'visible_samples_over_tree={len(self.visible_rows)} '
            f'pids_in_tree={sorted(self.names)}')


# ---------------------------------------------------------------------------
# the house census, private log + private state
# ---------------------------------------------------------------------------

def house_census(arm: str, tag: str) -> None:
    clog = os.path.join(HERE, f'_census-{arm}-{tag}.log')
    # EVERY arm starts from a FRESH private log, so a row reported below can
    # only come from THIS run. Appending across arms is what would let a stale
    # `ALERTA-JANELA pid=…` from an earlier arm read as a live alarm — a green
    # (or a red) that passes by construction, which is the one thing the census
    # discipline here exists to prevent.
    if tag == 'baseline':
        for stale in os.listdir(HERE):
            if stale.startswith(f'_census-{arm}-'):
                os.remove(os.path.join(HERE, stale))
    # ONE state per ARM, shared by every tag of that arm: the baseline's job is
    # to register the desk as it already is, and the mid runs must READ that
    # baseline back (modo=medicao) for a new pid to be able to alarm. A state
    # file per TAG would make every mid run a fresh bootstrap — a sensor that
    # cannot alarm, printing `alarme=0` for ever.
    cstate = os.path.join(HERE, f'_census-{arm}-state.json')
    cmd = ['powershell.exe', '-NoProfile', '-NonInteractive',
           '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
           '-File', CENSUS, '-Log', clog, '-Estado', cstate]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                           creationflags=CREATE_NO_WINDOW)
        tail = (p.stdout or '').strip().replace('\r', '')
        log(f'CENSUS-HOUSE arm={arm} tag={tag} rc={p.returncode} out={tail}')
        if os.path.exists(clog):
            with open(clog, encoding='utf-8', errors='replace') as f:
                for ln in f:
                    if 'ALERTA-JANELA' in ln:
                        log(f'CENSUS-HOUSE-ALERT arm={arm} tag={tag} '
                            f'{ln.strip()}')
    except Exception as exc:  # a census that cannot run must say so
        log(f'CENSUS-HOUSE arm={arm} tag={tag} ERROR {exc}')


# ---------------------------------------------------------------------------
# the arms are BUILT from the live shell, so they cannot go stale
# ---------------------------------------------------------------------------

HIDE_REMOVED = (
    ('            hidden=True,\n', '            hidden=False,\n'),
)
#: The OTHER half of the before/after pair: the same program with the cure
#: taken out (the navigation-start re-assert), so BOTH colours of the one line
#: come out of a single invocation of this oracle.
CURE_REMOVED = (
    ('        self.core.NavigationStarting += self._on_navigation_start\n', ''),
)
OFFSCREEN = (
    ("        self.geometry = dock_right(self.display['workArea'])\n",
     "        self.geometry = dock_right(self.display['workArea'])\n"
     "        # PROBE SAFETY ONLY (built by panel-startup-visibility-oracle.py):\n"
     "        # this arm exists to put a visible window on screen, so it is\n"
     "        # moved off the owner's desktop. Position is not what the lines\n"
     "        # measure -- IsWindowVisible and MainWindowHandle read no rect.\n"
     "        self.geometry['x'] = -10000\n"),
)


def build_variant(path: str, edits: tuple) -> None:
    with open(SHELL, encoding='utf-8') as f:
        src = f.read()
    out = src
    applied = []
    for old, new in edits:
        if old not in out:
            raise SystemExit(f'variant {os.path.basename(path)}: pattern not '
                             f'found in {SHELL}: {old!r} — refusing to ship a '
                             f'copy that is not the edit it claims')
        out = out.replace(old, new, 1)
        applied.append(old.strip())
    if out == src:
        raise SystemExit(f'variant {os.path.basename(path)}: no edit applied')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)
    log(f'VARIANT path={path} '
        f'sha256_live={hashlib.sha256(src.encode()).hexdigest()[:16]} '
        f'sha256_variant={hashlib.sha256(out.encode()).hexdigest()[:16]} '
        f'edits={applied}')


def cleanup(paths) -> None:
    for p in paths:
        try:
            if os.path.exists(p):
                os.remove(p)
                log(f'CLEANUP removed={p}')
        except OSError as exc:
            log(f'CLEANUP FAILED path={p} error={exc}')


# ---------------------------------------------------------------------------

def pythonw() -> str:
    exe = sys.executable or ''
    if exe.lower().endswith('pythonw.exe'):
        return exe
    cand = exe.replace('python.exe', 'pythonw.exe')
    return cand if os.path.exists(cand) else exe


def shell_line(path: str, needle: str):
    """The shell's own line, verbatim, or None."""
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8', errors='replace') as f:
        for ln in f:
            if needle in ln:
                return ln.split('sotto: ', 1)[-1].strip()
    return None


def parse_visible(line):
    if not line or 'visible=' not in line:
        return None
    return line.split('visible=', 1)[1].split()[0] == 'true'


def run_arm(arm: str, shell: str, extra: list, seconds: float) -> dict:
    alog = os.path.join(HERE, f'panel-startup-visibility-arm{arm}.log')
    if os.path.exists(alog):
        os.remove(alog)
    args = [pythonw(), shell, '--log', alog, '--no-hotkey',
            '--no-hot-reload', '--exit-after', str(seconds), *extra]
    log(f'ARM {arm} spawn={args}')
    out = open(alog + '.stdout', 'wb')
    proc = subprocess.Popen(args, stdout=out, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                            cwd=os.path.dirname(shell),
                            creationflags=CREATE_NO_WINDOW)
    # BASELINE: the first census run of a fresh private state only registers
    # what is already on the desk, so a later run can alarm on the NEW pid.
    house_census(arm, 'baseline')
    time.sleep(0.2)
    sampler = Sampler(proc.pid, arm)
    sampler.start()
    for tag in ('mid1', 'mid2', 'mid3'):
        time.sleep(max(0.4, seconds / 4.0))
        house_census(arm, tag)
    rc = proc.wait(timeout=400)
    out.close()
    sampler.stop.set()
    sampler.join(timeout=5)
    sampler.report()
    at = shell_line(alog, 'PANEL_VISIBILITY_AT_STARTUP')
    on = shell_line(alog, 'PANEL_VISIBILITY_ON_SCREEN')
    log(f'ARM {arm} shell_rc={rc} at_startup={at!r} on_screen={on!r}')
    return {'arm': arm, 'rc': rc, 'pid': proc.pid, 'at_startup': at,
            'on_screen': on, 'at_visible': parse_visible(at),
            'on_visible': parse_visible(on)}


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    log(f'ORACLE panel-startup-visibility '
        f'start={time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} '
        f'pythonw={pythonw()} shell={SHELL} arm_seconds={seconds}')
    with open(CENSUS, 'rb') as f:
        log(f'HOUSE-CENSUS instrument={CENSUS} '
            f'sha256={hashlib.sha256(f.read()).hexdigest()[:16]}')

    variants = (OFFSCREEN_SHELL, NEG_SHELL, PRECURE_SHELL)
    try:
        build_variant(OFFSCREEN_SHELL, OFFSCREEN)
        build_variant(NEG_SHELL, OFFSCREEN + HIDE_REMOVED)
        build_variant(PRECURE_SHELL, OFFSCREEN + CURE_REMOVED)

        real = run_arm('P', SHELL, [], seconds)
        before = run_arm('B', PRECURE_SHELL, [], seconds)
        control = run_arm('S', OFFSCREEN_SHELL, ['--show'], seconds)
        neg = run_arm('N', NEG_SHELL, ['--opaque'], seconds)
        neg2 = run_arm('N2', NEG_SHELL, [], seconds)
    finally:
        cleanup(variants)

    checks = [
        ('B.on_screen  == true (cure removed -> still on screen)',
         before['on_visible'] is True),
        ('P.at_startup == false', real['at_visible'] is False),
        ('P.on_screen  == false (cure in place -> off screen)',
         real['on_visible'] is False),
        ('S.on_screen  == true (--show still shows the panel)',
         control['on_visible'] is True),
        ('N.at_startup == true (hide removed -> line flips)',
         neg['at_visible'] is True),
    ]
    for name, ok in checks:
        log(f'CHECK {name} -> {"PASS" if ok else "FAIL"}')
    ok = all(v for _n, v in checks)
    log(f'VERDICT {"PASS" if ok else "FAIL"} '
        f'on_screen_before={before["on_visible"]} '
        f'at_startup_real={real["at_visible"]} on_screen_real={real["on_visible"]} '
        f'on_screen_show={control["on_visible"]} at_startup_neg={neg["at_visible"]} '
        f'at_startup_neg2={neg2["at_visible"]}')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
