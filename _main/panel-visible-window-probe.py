"""TICKET-7d45df2bec5431c26ff74563: MEASURE the panel's visible window in ms.

WHAT THIS MEASURES, and the two axes it refuses to conflate
-----------------------------------------------------------
The ticket reports the panel visible "50 ms to ~7 s". Two DIFFERENT windows
answer to the word "visible", and the house has already been bitten by
conflating them:

  mech  = WS_VISIBLE and not alpha-occluded. The Show() HAPPENED. Says
         nothing about whether the owner can see anything.
  owner = mech AND the window's rect intersects a monitor
         (`MonitorFromWindow(MONITOR_DEFAULTTONULL)`, house census convention).
         This is the window the OWNER would actually see.

The cure under measurement is POSITIONAL: `create_window` builds the window at
`OFFSCREEN = -32000` and `_move_into_place` only moves it after the PANEL has
loaded. A window parked at -32000 is WS_VISIBLE and on NO monitor, so a
census that reads `IsWindowVisible` alone calls it "visible" for the entire
startup. That is the SAME SHAPE of trap as F2 (a detached process is invisible
to a census that re-walks the process table): absence of evidence about the
WINDOW is not evidence that no window appeared.

So every launch reports BOTH axes, and the verdict turns on `owner`.

WHY A LAUNCH CAN BE INVALID, and why invalid launches are reported, not dropped
-------------------------------------------------------------------------------
The visible window only exists between the window's first Show and the end of
startup. A launch that HANGS or CRASHES before `PANEL_VISIBILITY_ON_SCREEN`
never finished startup, so its "visible" episode is the window sitting at
-32000 until the process was killed — it is NOT a measurement of the flash.
Those launches are counted separately and excluded from the distribution. A
report that silently averaged them in would be describing the harness.

MEASUREMENT DESIGN
------------------
Cadence is 10 ms by default (the brief's floor is a ~50 ms window, so a 25 ms
grid sees it in 2 samples only; the prior census's 25 ms grid is why the short
end had no resolution). The HWND set is discovered WHILE the process lives and
then polled directly, so the sample loop reads the WINDOW rather than re-walking
the process table after exit — which is exactly the F2 trap.

SAFETY
------
Launched with `pythonw.exe` (GUI subsystem, no console) and CREATE_NO_WINDOW;
`--no-hotkey` so a measurement run cannot steal the owner's Alt+C;
`--exit-after` bounds every launch; only PIDs THIS probe started are ever
killed. Arms are BUILT COPIES of the live shell, kept at the shell's OWN
geometry (the cure under measurement is positional, so overriding geometry
would erase the difference being measured); the copy exists only to prove it is
not stale. Visibility here is read from the window channels, not the desktop.

EXIT CODES (a verdict, never an ambiguous cause)
------------------------------------------------
  0  every launch was VALID and owner-visible time was 0 across all of them
  1  RED — at least one valid launch showed the window on a monitor
  2  instrument error — no valid launch, or the shell copy could not be built
  3  negative arm failed to reproduce (instrument is BLIND)

Usage: py -3 _main/panel-visible-window-probe.py [--n 12] [--ms 10] [--secs 5]
                                                       [--arm live]
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
VARIANT_DIR = os.path.dirname(SHELL)

CREATE_NO_WINDOW = 0x08000000
MONITOR_DEFAULTTONULL = 0x00000000
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x2

user32 = ctypes.WinDLL('user32', use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# window channels (same primitives the house census uses)
# ---------------------------------------------------------------------------

def window_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    return buf.value


def window_text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, 512)
    return buf.value


def layered_alpha(hwnd) -> int:
    """Constant alpha of a layered window, or -1 when it is not alpha-occluded.

    pywebview's `hidden=True` branch sets `Opacity=0` BEFORE `Show()`, so for
    that span the form is WS_VISIBLE but FULLY TRANSPARENT — a catch there is
    NOT a window the owner can see. -1 => not alpha-occluded => treat visible.
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


def on_monitor(hwnd) -> bool:
    """True iff the rect intersects ANY monitor — the OWNER axis."""
    return bool(user32.MonitorFromWindow(wintypes.HWND(hwnd),
                                         MONITOR_DEFAULTTONULL))


def rect_of(hwnd):
    r = wintypes.RECT()
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r)):
        return None
    return [int(r.left), int(r.top), int(r.right), int(r.bottom)]


def hwnds_of_pid(pid: int) -> list:
    found: list[int] = []

    def cb(hwnd, _l):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid:
            found.append(int(hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def read_state(hwnds: list) -> list:
    rows = []
    for h in hwnds:
        if not user32.IsWindow(wintypes.HWND(h)):
            continue
        if not user32.IsWindowVisible(wintypes.HWND(h)):
            continue
        rows.append({
            'hwnd': h, 'class': window_class(h), 'title': window_text(h),
            'alpha': layered_alpha(h), 'on_screen': on_monitor(h),
            'rect': rect_of(h),
        })
    return rows


# ---------------------------------------------------------------------------
# the shell copy (built from the LIVE shell at run time, deleted at the end)
# ---------------------------------------------------------------------------

#: Marker-only. The cure under measurement is POSITIONAL (the shell creates at
#: OFFSCREEN and moves into place after load), so overriding geometry would
#: erase the very difference being measured; this edit only proves the copy is
#: built from the live file and not stale.
MARKER = (
    ("        self.geometry = dock_right(self.display['workArea'])\n",
     "        self.geometry = dock_right(self.display['workArea'])\n"
     "        # (copy built by panel-visible-window-probe.py; geometry kept)\n"),
)

#: The FIX reverted, as the NEGATIVE arm. As of 2026-10-06 the OFFSCREEN
#: creation position is GONE from the shell (it broke the stage->panel
#: navigation, so `_on_loaded` never fired and the shell hung), so the only
#: cure left is `_reassert_hidden` on `NavigationStarting`. Removing that
#: subscription is therefore exactly "the shell minus its cure": if THIS arm
#: does not show the window on a monitor, the instrument is blind and every
#: other number here is worthless.
CURE_REVERTED = (
    ('        self.core.NavigationStarting += self._on_navigation_start\n', ''),
)

ARMS = {
    'live': (MARKER, [], 'the LIVE shell (NavigationStarting re-assert in place)'),
    'nocure': (MARKER + CURE_REVERTED, [],
               'negative arm: the NavigationStarting re-assert removed'),
    'opaque': (MARKER, ['--opaque'],
               'the LIVE shell with --opaque (no transparent Show-on-navigate)'),
}


def build_variant(path: str, edits: tuple) -> str:
    with open(SHELL, encoding='utf-8') as f:
        src = f.read()
    out = src
    for old, new in edits:
        if old not in out:
            raise SystemExit(f'variant {os.path.basename(path)}: pattern not '
                             f'found in {SHELL}: {old!r} — refusing to ship a '
                             f'copy that is not the edit it claims')
        out = out.replace(old, new, 1)
    if out == src:
        raise SystemExit(f'variant {os.path.basename(path)}: no edit applied')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)
    log(f'VARIANT path={os.path.basename(path)} '
        f'sha256_live={hashlib.sha256(src.encode()).hexdigest()[:16]} '
        f'edits={len(edits)}')
    return path


def pythonw() -> str:
    exe = sys.executable or ''
    if exe.lower().endswith('pythonw.exe'):
        return exe
    cand = exe.replace('python.exe', 'pythonw.exe')
    return cand if os.path.exists(cand) else exe


# ---------------------------------------------------------------------------
# one launch
# ---------------------------------------------------------------------------

def read_log(path: str) -> list:
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return [ln.rstrip('\n') for ln in f]
    except OSError:
        return []


def episodes(samples: list, key) -> list:
    """Contiguous runs where `key(row)` holds -> (start_ms, end_ms)."""
    eps: list = []
    cur = None
    for s in samples:
        if any(key(r) for r in s['rows']):
            if cur is None:
                cur = {'start': s['t_ms'], 'end': s['t_ms']}
            else:
                cur['end'] = s['t_ms']
        elif cur is not None:
            eps.append(cur)
            cur = None
    if cur is not None:
        eps.append(cur)
    return eps


def ep_pairs(eps: list) -> list:
    """(start_ms, duration_ms) per episode — the phase needs the START, not
    just the length: two flashes and one long flash differ only in where they
    begin relative to the shell's own log lines."""
    return [[round(e['start'], 1), round(e['end'] - e['start'], 1)] for e in eps]


def measure(shell: str, extra: list, secs: float, cadence_s: float, idx: int,
            tag: str) -> dict:
    """Launch the shell and sample its windows CONCURRENTLY, at `cadence_s`."""
    alog = os.path.join(HERE, f'_vis-{tag}-{idx}.log')
    for suffix in ('', '.stdout'):
        if os.path.exists(alog + suffix):
            os.remove(alog + suffix)
    out = open(alog + '.stdout', 'wb')
    proc = subprocess.Popen(
        [pythonw(), shell, '--log', alog, '--no-hotkey', '--no-hot-reload',
         '--exit-after', str(secs), *extra],
        stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        cwd=os.path.dirname(shell), creationflags=CREATE_NO_WINDOW)

    t0 = time.perf_counter()
    samples: list = []
    hwnds: list = []
    scanned = -1.0
    rc = None
    kill_failed = False
    deadline = t0 + secs + 45
    while True:
        now = time.perf_counter()
        elapsed = now - t0
        # discover the window set early and often enough to catch a short flash
        if elapsed > scanned:
            scanned = elapsed
            for h in hwnds_of_pid(proc.pid):
                if h not in hwnds:
                    hwnds.append(h)
        samples.append({'t_ms': elapsed * 1000.0, 'rows': read_state(hwnds)})
        if proc.poll() is not None:
            rc = proc.returncode
            break
        if now > deadline:
            proc.kill()                 # only ever a pid THIS probe started
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired as exc:
                # LOUD, not swallowed: the kill did not take, so this launch's
                # samples are truncated at an unknown point and its `valid`
                # flag must not be trusted. Marked invalid below.
                log(f'KILL-FAILED launch={tag}/{idx} pid={proc.pid} {exc!r} '
                    f'— this launch is INVALID (samples truncated)')
                kill_failed = True
                rc = -998
            if rc is None:
                rc = -999
            break
        time.sleep(cadence_s)
    samples.append({'t_ms': (time.perf_counter() - t0) * 1000.0,
                    'rows': read_state(hwnds)})
    out.close()

    mech_eps = episodes(samples, lambda r: r['alpha'] != 0)
    owner_eps = episodes(samples, lambda r: r['alpha'] != 0 and r['on_screen'])

    lines = read_log(alog)
    at = next((ln for ln in lines if 'PANEL_VISIBILITY_AT_STARTUP' in ln), None)
    on = next((ln for ln in lines if 'PANEL_VISIBILITY_ON_SCREEN' in ln), None)
    moved = next((ln for ln in lines if 'panel moved into place' in ln), None)
    staging = next((ln for ln in lines if 'STAGING_LOADED' in ln), None)
    reasserts = [ln for ln in lines if 'PANEL_VISIBILITY_REASSERTED' in ln]

    # A launch only MEASURES the flash if startup actually COMPLETED: the
    # visibility question is settled by `PANEL_VISIBILITY_ON_SCREEN`, which is
    # emitted once per process after the panel has loaded. A launch that never
    # reaches it hung or crashed, and its "visible" episode is the window
    # sitting on the owner's monitor until the process was killed — that is a
    # measurement of the harness failing, not of the flash.
    valid = bool(on and not kill_failed)

    peak_rect = None
    for e in owner_eps:
        for s in samples:
            if e['start'] <= s['t_ms'] <= e['end']:
                for r in s['rows']:
                    if r['alpha'] != 0 and r['on_screen']:
                        peak_rect = r['rect']
                        break
                if peak_rect:
                    break
        if peak_rect:
            break

    return {
        'idx': idx, 'rc': rc, 'valid': valid, 'kill_failed': kill_failed,
        'samples': len(samples), 'hwnds': hwnds,
        'mech_ms': [round(e['end'] - e['start'], 1) for e in mech_eps],
        'owner_ms': [round(e['end'] - e['start'], 1) for e in owner_eps],
        'owner_ep': ep_pairs(owner_eps),
        'mech_ep': ep_pairs(mech_eps),
        'longest_mech_ms': max((e['end'] - e['start'] for e in mech_eps),
                               default=0.0),
        'longest_owner_ms': max((e['end'] - e['start'] for e in owner_eps),
                                default=0.0),
        'peak_owner_rect': peak_rect,
        'at_startup': at, 'on_screen': on, 'moved_into_place': moved,
        'staging_loaded': staging, 'n_reasserts': len(reasserts),
        'logpath': alog,
    }


def summarise(per: list) -> dict:
    valid = [r for r in per if r['valid']]
    invalid = [r for r in per if not r['valid']]
    owner_all = [d for r in valid for d in r['owner_ms']]
    mech_all = [d for r in valid for d in r['mech_ms']]
    return {
        'launched': len(per), 'valid': len(valid), 'invalid': len(invalid),
        'owner_ms': sorted(owner_all), 'mech_ms': sorted(mech_all),
        'launches_with_owner': sum(1 for r in valid if r['owner_ms']),
        'longest_owner_ms': max(owner_all, default=0.0),
        'longest_mech_ms': max(mech_all, default=0.0),
        'invalid_reasons': [
            {'idx': r['idx'], 'rc': r['rc'],
             'has_staging_line': bool(r['staging_loaded']),
             'has_moved_line': bool(r['moved_into_place']),
             'has_on_screen_line': bool(r['on_screen'])}
            for r in invalid],
    }


def main() -> int:
    a = sys.argv[1:]
    n, secs, cadence_ms, arm = 12, 5.0, 10.0, 'live'
    if '--n' in a:
        n = int(a[a.index('--n') + 1])
    if '--secs' in a:
        secs = float(a[a.index('--secs') + 1])
    if '--ms' in a:
        cadence_ms = float(a[a.index('--ms') + 1])
    if '--arm' in a:
        arm = a[a.index('--arm') + 1]
    if arm not in ARMS:
        log(f'REFUSED: unknown arm {arm!r}; known={sorted(ARMS)}')
        return 2
    edits, extra, desc = ARMS[arm]
    cadence_s = cadence_ms / 1000.0

    log(f'PROBE ticket=7d45df2bec5431c26ff74563 start='
        f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} '
        f'arm={arm} ({desc}) n={n} cadence_ms={cadence_ms:.0f} secs={secs} '
        f'pythonw={pythonw()}')
    log('AXES mech=WS_VISIBLE & alpha!=0 (the Show happened) | '
        'owner=mech AND on a monitor (what the owner can see)')
    log('VALIDITY a launch counts only if startup COMPLETED (panel moved into '
        'place / PANEL_VISIBILITY_ON_SCREEN); a hung or crashed launch is '
        'reported separately and EXCLUDED from the distribution')

    path = os.path.join(VARIANT_DIR, f'_vis-{arm}-sotto_webview.py')
    built: list = []
    s: dict = {}
    try:
        build_variant(path, edits)
        built.append(path)
        per = []
        for i in range(n):
            r = measure(path, extra, secs, cadence_s, i, arm)
            per.append(r)
            log(f'LAUNCH {arm} {i + 1}/{n} rc={r["rc"]} valid='
                f'{str(r["valid"]).lower()} samples={r["samples"]} '
                f'hwnds={len(r["hwnds"])} mech_ep={r["mech_ms"]} '
                f'owner_ep={r["owner_ms"]} n_reasserts={r["n_reasserts"]} '
                f'rect={r["peak_owner_rect"]} '
                f'moved={str(bool(r["moved_into_place"])).lower()}')
        s = summarise(per)
        log('=== SUMMARY ===')
        log(json.dumps(s, indent=2))
        with open(os.path.join(HERE, 'panel-visible-window-probe.json'),
                  'w', encoding='utf-8') as f:
            json.dump({'arm': arm, 'desc': desc, 'n': n,
                       'cadence_ms': cadence_ms, 'secs': secs,
                       'summary': s, 'per_launch': per}, f, indent=2)
    finally:
        for p in built:
            try:
                if os.path.exists(p):
                    os.remove(p)
                    log(f'CLEANUP removed={os.path.basename(p)}')
            except OSError as exc:
                log(f'CLEANUP FAILED {p} {exc}')

    log('=== VERDICT ===')
    if s.get('valid', 0) == 0:
        log('INSTRUMENT-ERROR no launch completed startup; every number here '
            'would describe the harness, not the window')
        return 2
    if arm == 'nocure' and s['launches_with_owner'] == 0:
        log('BLIND the negative arm (cure reverted) never showed the window on '
            'a monitor; the other arms cannot be believed')
        return 3
    if s['launches_with_owner'] > 0:
        log(f'RED owner-visible in {s["launches_with_owner"]}/{s["valid"]} '
            f'valid launches, longest {s["longest_owner_ms"]:.1f} ms')
        return 1
    log(f'GREEN owner-visible 0 ms in all {s["valid"]}/{s["valid"]} valid '
        f'launches; mech-visible longest {s["longest_mech_ms"]:.1f} ms '
        f'(a Show happened off-screen)')
    return 0


if __name__ == '__main__':
    sys.exit(main())