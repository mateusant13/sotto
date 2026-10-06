"""CENSUS: BOUND the intermittent panel flash at shell startup.

Sibling lane `SottoErrorRecovery` caught a SUB-SAMPLE panel flash with its own
census, contradicting `AGENTS.md`'s "arm P 0 of 41":

    CENSUS-PID visible pid=36332 hwnd=6955742 title='Sotto' sample=4   (200 ms, 1/163)
    CENSUS-PID visible pid=32508 hwnd=82451080 title='Sotto' sample=168 (100 ms, 1/302)
    CENSUS-PID visible pid=1568  hwnd=1712882 class='WindowsForms10.Window.8.app.0.aec740_r16_ad1'
    negative: samples=164 visible=0  and  samples=767 visible=0

3 of 5 censuses caught it, each for ONE sample. This instrument does not argue
about it: it samples the shell's OWN pid tree at 25 ms over N >= 20 launches and
reports, per arm:

    catches / N launches, the longest visible episode in ms, and its PHASE
    (which of the shell's own log lines had been emitted when it was visible).

The phase is what names the mechanism: a visible sample that lands BEFORE
`PANEL_VISIBILITY_AT_STARTUP` is a different defect from one that lands AFTER
the first `PANEL_VISIBILITY_REASSERTED`.

ARMS (copies are BUILT from the live shell at run time, sha256 logged, and
deleted at the end, so a negative arm cannot silently go stale):

  precure  a COPY of the live shell with the navigation-start re-assert
           subscription REMOVED — the BEFORE half / the negative arm. Its
           catches must be >= 1 or this instrument is blind.
  real     the LIVE `app/webview/sotto_webview.py`, the real entry point
           `run.cmd` launches. Both the AFTER measurement and the thing the
           owner sees.
  opaque   a COPY of the live shell run with the app's own `--opaque`. If the
           flash goes to 0 here, that is a FINDING (the mechanism is the
           transparent Show-on-navigation), not a workaround.
  sync-off a COPY of the live shell with ONLY the synchronous re-assert removed
           (the posted half left in). Isolates the synchronous cure.

SAFETY. Launched with pythonw.exe (GUI subsystem: no console) and every child
spawned with CREATE_NO_WINDOW. Every copy arm is moved OFF-SCREEN (x=-10000);
POSITION does not change what is measured (IsWindowVisible / the main-window
predicate read no rect), which the house already measured. The `real` arm is the
real entry point and is the only arm that can put a window on the owner's desk —
so it is run only when the cure is expected to hold, and the launch count is
kept small in that case.

Usage:  py -3 _main/panel-startup-flash-census.py [--n 20] [--ms 25] [--secs 5]
                                                    [--arms precure,real]
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
VARIANT_DIR = os.path.dirname(SHELL)
LOG = os.path.join(HERE, 'panel-startup-flash-census.log')

CREATE_NO_WINDOW = 0x08000000
GW_OWNER = 4
DEFAULT_MS = 25.0
DEFAULT_SECS = 5.0
DEFAULT_N = 20

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_lines: list[str] = []


def log(msg: str) -> None:
    _lines.append(msg)
    with open(LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(_lines) + '\n')
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# process tree + window census  (same channels the house census and the prior
# oracle use — IsWindowVisible, and the unowned top-level window)
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


def window_text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, 512)
    return buf.value


def window_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    return buf.value


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x2


def layered_alpha(hwnd) -> int:
    """Constant alpha of a layered window, or -1 when it is not alpha-occluded.

    pywebview's `hidden=True` dance sets `Opacity=0` BEFORE `Show()`
    (winforms.py:778-780), so for that span the form is WS_VISIBLE but FULLY
    TRANSPARENT — a catch there is NOT a window the owner can see.
    `GetLayeredWindowAttributes` returns the constant alpha WinForms set, which
    is the only channel that tells the two apart from outside the process.
    -1 means "not a layered constant-alpha window" → treat as visible.
    """
    ex = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)
    if not (ex & WS_EX_LAYERED):
        return -1
    crkey = wintypes.DWORD(0)
    alpha = ctypes.c_ubyte(0)
    flags = wintypes.DWORD(0)
    ok = user32.GetLayeredWindowAttributes(wintypes.HWND(hwnd),
                                           ctypes.byref(crkey),
                                           ctypes.byref(alpha),
                                           ctypes.byref(flags))
    if not ok or not (flags.value & LWA_ALPHA):
        return -1
    return int(alpha.value)


MONITOR_DEFAULTTONULL = 0x00000000


def on_monitor(hwnd) -> bool:
    """True iff the window's rect intersects ANY monitor.

    The cure under measurement works by POSITION (the shell creates the window
    at -32000 during startup), so `IsWindowVisible` alone would call an
    off-screen window 'visible'. `MonitorFromWindow(MONITOR_DEFAULTTONULL)`
    returns NULL when the window is on no monitor — the only channel that
    separates 'the Show happened' from 'the owner can see it'.
    """
    return bool(user32.MonitorFromWindow(wintypes.HWND(hwnd),
                                         MONITOR_DEFAULTTONULL))


def visible_windows_of(pids: set) -> list:
    rows: list = []

    def cb(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        rows.append({
            'pid': int(pid.value),
            'hwnd': int(hwnd),
            'class': window_class(hwnd),
            'title': window_text(hwnd),
            'alpha': layered_alpha(hwnd),
            'on_screen': on_monitor(hwnd),
            'unowned': int(user32.GetWindow(hwnd, GW_OWNER) or 0) == 0,
        })
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return rows


class Sampler(threading.Thread):
    """Every `cadence` ms: the visible windows owned by the shell's pid tree,
    AND how many lines the shell's own log file already carried. Coupling the
    two in ONE loop iteration is what lets a catch be PHASED."""

    def __init__(self, root: int, logpath: str, cadence_s: float):
        super().__init__(daemon=True)
        self.root = root
        self.logpath = logpath
        self.cadence = cadence_s
        self.stop = threading.Event()
        self.samples: list = []
        self.pids_seen: dict = {}

    def run(self):
        t0 = time.perf_counter()
        lines: list = []
        while not self.stop.is_set():
            tree = descendants(self.root)
            self.pids_seen.update(tree)
            vis = visible_windows_of(set(tree))
            try:
                with open(self.logpath, encoding='utf-8', errors='replace') as f:
                    lines = [ln.rstrip('\n') for ln in f]
            except OSError:
                pass
            self.samples.append({
                't_ms': (time.perf_counter() - t0) * 1000.0,
                'vis': vis,
                'log_n': len(lines),
                'last': lines[-1] if lines else '',
            })
            self.stop.wait(self.cadence)

    def episodes(self):
        """Contiguous runs of visible samples -> (start_ms, end_ms, rows)."""
        eps: list = []
        cur = None
        for s in self.samples:
            if s['vis']:
                if cur is None:
                    cur = {'start': s['t_ms'], 'end': s['t_ms'],
                           'log_n': s['log_n'], 'last': s['last'],
                           'rows': list(s['vis'])}
                else:
                    cur['end'] = s['t_ms']
            else:
                if cur is not None:
                    eps.append(cur)
                    cur = None
        if cur is not None:
            eps.append(cur)
        return eps


# ---------------------------------------------------------------------------
# arms built from the live shell
# ---------------------------------------------------------------------------

#: OFF-SCREEN measurement copy. The window is parked at x=-10000 so NO copy
#: can put anything on the owner's desk; position is irrelevant to the
#: `mechanism` axis (WS_VISIBLE + not alpha-occluded), which is the axis the
#: negative arm moves.
OFFSCREEN = (
    ("        self.geometry = dock_right(self.display['workArea'])\n",
     "        self.geometry = dock_right(self.display['workArea'])\n"
     "        # OFF-SCREEN measurement copy (panel-startup-flash-census.py)\n"
     "        self.geometry['x'] = -10000\n"),
)
CURE_REMOVED = (
    ('        self.core.NavigationStarting += self._on_navigation_start\n', ''),
)
SYNC_REMOVED = (
    ("        self._reassert_hidden()\n        self._post(self._reassert_hidden)\n",
     "        self._post(self._reassert_hidden)\n"),
)
#: The FIX reverted in a COPY — the negative arm. The cure is subscribing the
#: re-assert to the SAME event pywebview subscribes (the control's
#: `NavigationStarting`), which makes the hide run right after the Show in one
#: dispatch. Reverting it to the CoreWebView2 event restores the ordering race,
#: so the window is left visible for a navigation. Its visible catches must be
#: >= 1 or this instrument is blind.
CURE_HOOK_REMOVED = (
    ('        self.webview2.NavigationStarting += self._on_navigation_start\n',
     '        self.core.NavigationStarting += self._on_navigation_start\n'),
)


def build_variant(path: str, edits: tuple) -> str:
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
    sha = hashlib.sha256(src.encode()).hexdigest()[:16]
    log(f'VARIANT path={os.path.basename(path)} sha256_live={sha} '
        f'edits={applied}')
    return sha


def pythonw() -> str:
    exe = sys.executable or ''
    if exe.lower().endswith('pythonw.exe'):
        return exe
    cand = exe.replace('python.exe', 'pythonw.exe')
    return cand if os.path.exists(cand) else exe


def launch(shell: str, extra: list, secs: float, cadence_s: float, idx: int,
           tag: str) -> dict:
    alog = os.path.join(HERE, f'_flash-{tag}-{idx}.log')
    if os.path.exists(alog):
        os.remove(alog)
    args = [pythonw(), shell, '--log', alog, '--no-hotkey', '--no-hot-reload',
            '--exit-after', str(secs), *extra]
    out = open(alog + '.stdout', 'wb')
    proc = subprocess.Popen(args, stdout=out, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                            cwd=os.path.dirname(shell),
                            creationflags=CREATE_NO_WINDOW)
    sampler = Sampler(proc.pid, alog, cadence_s)
    sampler.start()
    try:
        rc = proc.wait(timeout=secs + 60)
    except subprocess.TimeoutExpired:
        proc.kill()
        rc = -999
    out.close()
    sampler.stop.set()
    sampler.join(timeout=5)
    eps = sampler.episodes()
    catches = sum(1 for s in sampler.samples if s['vis'])
    # MECHANISM: the Show happened and is not alpha-occluded — position is
    # IGNORED. This is the axis the negative arm must move.
    caught_mech = sum(1 for s in sampler.samples
                      if any(r.get('alpha', -1) != 0 for r in s['vis']))
    # OWNER: the Show happened AND the window is on a monitor — the axis the
    # positional cure (create at -32000) moves.
    caught_owner = sum(1 for s in sampler.samples
                       if any(r.get('alpha', -1) != 0 and r.get('on_screen')
                              for r in s['vis']))
    caught_occluded = catches - caught_mech
    longest = max((e['end'] - e['start'] for e in eps
                   if any(r.get('alpha', -1) != 0 for r in e['rows'])),
                  default=0.0)
    longest_owner = max((e['end'] - e['start'] for e in eps
                         if any(r.get('alpha', -1) != 0 and r.get('on_screen')
                                for r in e['rows'])),
                        default=0.0)
    at = on = None
    atv = onv = None
    if os.path.exists(alog):
        for ln in open(alog, encoding='utf-8', errors='replace'):
            if 'PANEL_VISIBILITY_AT_STARTUP' in ln:
                at = ln.split('sotto: ', 1)[-1].strip()
                atv = 'visible=true' in at
            if 'PANEL_VISIBILITY_ON_SCREEN' in ln:
                on = ln.split('sotto: ', 1)[-1].strip()
                onv = 'visible=true' in on
    return {'idx': idx, 'rc': rc, 'samples': len(sampler.samples),
            'catches': catches, 'catches_mech': caught_mech,
            'catches_owner': caught_owner,
            'catches_occluded': caught_occluded, 'episodes': eps,
            'longest_ms': longest, 'longest_owner_ms': longest_owner,
            'at': at, 'on': on, 'at_visible': atv, 'on_visible': onv,
            'logpath': alog}


def run_arm(tag: str, shell: str, extra: list, n: int, secs: float,
            cadence_s: float, on_screen: bool) -> dict:
    log(f'=== ARM {tag} shell={os.path.basename(shell)} '
        f'on_screen={str(on_screen).lower()} n={n} '
        f'cadence_ms={cadence_s * 1000:.0f} secs={secs} extra={extra} ===')
    per = []
    for i in range(n):
        r = launch(shell, extra, secs, cadence_s, i, tag)
        r['tag'] = tag
        per.append(r)
        phased = ''
        if r['episodes']:
            e = r['episodes'][0]
            phased = (f" first_episode t={e['start']:.0f}-{e['end']:.0f} ms "
                      f"log_n={e['log_n']} last_line={e['last']!r}")
        log(f'LAUNCH {tag} {i}/{n} rc={r["rc"]} samples={r["samples"]} '
            f'mech={r["catches_mech"]} owner={r["catches_owner"]} '
            f'occluded={r["catches_occluded"]} '
            f'longest_mech_ms={r["longest_ms"]:.0f} '
            f'longest_owner_ms={r["longest_owner_ms"]:.0f} '
            f'at_startup={r["at_visible"]} on_screen={r["on_visible"]}{phased}')
    n_mech = sum(1 for r in per if r['catches_mech'] > 0)
    n_owner = sum(1 for r in per if r['catches_owner'] > 0)
    longest_mech = max((r['longest_ms'] for r in per), default=0.0)
    longest_owner = max((r['longest_owner_ms'] for r in per), default=0.0)
    total_samples = sum(r['samples'] for r in per)
    total_mech = sum(r['catches_mech'] for r in per)
    total_owner = sum(r['catches_owner'] for r in per)
    total_occluded = sum(r['catches_occluded'] for r in per)
    # phase histogram over every episode
    phases: dict = {}
    detail = []
    for r in per:
        for e in r['episodes']:
            key = phase_of(e['last'])
            phases.setdefault(key, []).append(e['last'])
            detail.append({'tag': tag, 'idx': r['idx'], 'start_ms': round(e['start'], 1),
                           'dur_ms': round(e['end'] - e['start'], 1),
                           'phase': key, 'last_line': e['last'],
                           'rows': e['rows']})
    log(f'ARM-SUMMARY {tag}: launched={n} launches_with_mech={n_mech}/{n} '
        f'launches_with_owner={n_owner}/{n} samples={total_samples} '
        f'mech_samples={total_mech} owner_samples={total_owner} '
        f'occluded_samples={total_occluded} '
        f'longest_mech_ms={longest_mech:.0f} '
        f'longest_owner_ms={longest_owner:.0f} phases={phases}')
    for d in detail:
        mech = any(r.get('alpha', -1) != 0 for r in d['rows'])
        owner = any(r.get('alpha', -1) != 0 and r.get('on_screen')
                    for r in d['rows'])
        log(f'FLASH {tag} launch={d["idx"]} at={d["start_ms"]}ms '
            f'dur~{d["dur_ms"]}ms mech={str(mech).lower()} '
            f'owner_visible={str(owner).lower()} '
            f'phase={d["phase"]} last_line={d["last_line"]!r} '
            f'rows={d["rows"]}')
    return {'tag': tag, 'n': n, 'launched_with_flash': n_mech,
            'samples': total_samples, 'visible_samples': total_mech,
            'mech_samples': total_mech, 'owner_samples': total_owner,
            'occluded_samples': total_occluded,
            'longest_ms': longest_mech, 'longest_owner_ms': longest_owner,
            'phases': phases, 'detail': detail, 'per': per}


def phase_of(last_line: str) -> str:
    if not last_line:
        return 'no-log-line-yet'
    if 'PANEL_VISIBILITY_ON_SCREEN' in last_line:
        return 'settled(after-on-screen)'
    if 'PANEL_VISIBILITY_REASSERTED' in last_line:
        return 'after-a-reassert'
    if 'PANEL_VISIBILITY_AT_STARTUP' in last_line:
        return 'at-startup-marker'
    if 'SHELL_EXIT' in last_line:
        return 'late'
    return 'before-startup-markers'


def main() -> int:
    a = sys.argv[1:]
    n = DEFAULT_N
    secs = DEFAULT_SECS
    cadence_ms = DEFAULT_MS
    arms = 'precure,real,opaque'
    if '--n' in a:
        n = int(a[a.index('--n') + 1])
    if '--secs' in a:
        secs = float(a[a.index('--secs') + 1])
    if '--ms' in a:
        cadence_ms = float(a[a.index('--ms') + 1])
    if '--arms' in a:
        arms = a[a.index('--arms') + 1]
    cadence_s = cadence_ms / 1000.0
    if cadence_ms > 30:
        log(f'REFUSED: cadence {cadence_ms} ms > 30 ms — the brief requires '
            f'<= 30 ms')
        return 3

    log(f'CENSUS panel-startup-flash start='
        f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} '
        f'pythonw={pythonw()} arms={arms} n={n} cadence_ms={cadence_ms} '
        f'secs={secs}')
    log(f'HOUSE-CENSUS note: the 60 s grid cannot see this defect; this '
        f'instrument samples at {cadence_ms:.0f} ms.')

    want = [x.strip() for x in arms.split(',') if x.strip()]
    if 'real' in want and '--allow-onscreen' not in a:
        log('REFUSED ARM real: it runs the shell ON-SCREEN and the owner must '
            'never be shown a window while measuring. Reproduce with `live` '
            '(the SAME shell code, only x moved off the desk; IsWindowVisible '
            'reads no rect). Override with --allow-onscreen only when the cure '
            'is already measured clean.')
        want.remove('real')
    variants = {}
    built = []
    try:
        if 'precure' in want or 'sync-off' in want or 'opaque' in want:
            off = os.path.join(VARIANT_DIR, '_flash-offscreen-sotto_webview.py')
            build_variant(off, OFFSCREEN)
            built.append(off)
            variants['offscreen'] = off
        if 'precure' in want:
            p = os.path.join(VARIANT_DIR, '_flash-precure-sotto_webview.py')
            build_variant(p, OFFSCREEN + CURE_REMOVED)
            built.append(p)
            variants['precure'] = p
        if 'sync-off' in want:
            p = os.path.join(VARIANT_DIR, '_flash-syncoff-sotto_webview.py')
            build_variant(p, OFFSCREEN + SYNC_REMOVED)
            built.append(p)
            variants['sync-off'] = p
        if 'opaque' in want:
            p = os.path.join(VARIANT_DIR, '_flash-opaque-sotto_webview.py')
            build_variant(p, OFFSCREEN)
            built.append(p)
            variants['opaque'] = p
        if 'live' in want:
            p = os.path.join(VARIANT_DIR, '_flash-live-sotto_webview.py')
            build_variant(p, OFFSCREEN)
            built.append(p)
            variants['live'] = p
        if 'nocure' in want:
            p = os.path.join(VARIANT_DIR, '_flash-nocure-sotto_webview.py')
            build_variant(p, OFFSCREEN + CURE_HOOK_REMOVED)
            built.append(p)
            variants['nocure'] = p
        if 'show' in want:
            p = os.path.join(VARIANT_DIR, '_flash-show-sotto_webview.py')
            build_variant(p, OFFSCREEN)
            built.append(p)
            variants['show'] = p

        results = {}
        if 'precure' in want:
            results['precure'] = run_arm('precure', variants['precure'], [],
                                         n, secs, cadence_s, False)
        if 'opaque' in want:
            results['opaque'] = run_arm('opaque', variants['opaque'],
                                        ['--opaque'], n, secs, cadence_s, False)
        if 'sync-off' in want:
            results['sync-off'] = run_arm('sync-off', variants['sync-off'], [],
                                          n, secs, cadence_s, False)
        if 'live' in want:
            results['live'] = run_arm('live', variants['live'], [],
                                      n, secs, cadence_s, False)
        if 'nocure' in want:
            results['nocure'] = run_arm('nocure', variants['nocure'], [],
                                        n, secs, cadence_s, False)
        if 'show' in want:
            results['show'] = run_arm('show', variants['show'], ['--show'],
                                      n, secs, cadence_s, False)
        if 'real' in want:
            results['real'] = run_arm('real', SHELL, [], n, secs, cadence_s, True)
    finally:
        for p in built:
            try:
                if os.path.exists(p):
                    os.remove(p)
                    log(f'CLEANUP removed={os.path.basename(p)}')
            except OSError as exc:
                log(f'CLEANUP FAILED {p} {exc}')

    log('=== VERDICT ===')
    log('mech = WS_VISIBLE & alpha!=0 (the Show happened; POSITION ignored)')
    log('owner = mech AND on a monitor (what the owner can actually see)')
    for tag, r in results.items():
        log(f'{tag}: launches_with_mech={r["launched_with_flash"]}/{r["n"]} '
            f'mech_samples={r["mech_samples"]} owner_samples={r["owner_samples"]} '
            f'occluded_samples={r["occluded_samples"]} '
            f'longest_mech_ms={r["longest_ms"]:.0f} '
            f'longest_owner_ms={r["longest_owner_ms"]:.0f}')
    # BLIND unless a copy with the fix reverted still SHOWS the window (mech>0).
    negatives = [r for t, r in results.items() if t in ('nocure', 'precure')]
    fixed = [r for t, r in results.items() if t in ('real', 'live')]
    neg_ok = (not negatives) or any(r['mech_samples'] > 0 for r in negatives)
    fix_ok = (not fixed) or all(r['owner_samples'] == 0 for r in fixed)
    ok = neg_ok and fix_ok
    log(f'NEGATIVE-ARM mechanism reproduces={str(bool(neg_ok)).lower()} '
        f'(neg arms present={len(negatives)}) | '
        f'FIXED arms owner-clean={str(bool(fix_ok)).lower()} '
        f'(fixed arms present={len(fixed)})')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
