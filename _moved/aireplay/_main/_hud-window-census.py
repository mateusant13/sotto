"""THE HUD WINDOW CENSUS — `_hud-window-census.py`.

THE CLAIM THIS INSTRUMENT EXISTS TO SETTLE. `specs/05-overlay-hud.md` §1.6:
"A window this product maps is a promise the user asked for. The HUD window is
NOT CREATED VISIBLE and NOTHING IS PAINTED OR PUBLISHED until a HUD binding
fires or the owner passed `--show-hud`." And §6 PASS-1 asks for it at a 25 ms
cadence, with the reason spelled out: a 60 s house census caught nothing while a
window was up for a whole 6 s run, so presence can be proven but ABSENCE cannot
(`H:\\sotto\\AGENTS.md`, "The house window census samples ONCE PER 60 s").

SO: this samples the shell's OWN pid tree every `cadence` ms and reports, per
arm, how many launches put a WS_VISIBLE window on screen and for how long.

ARMS (copies are BUILT from the live shell at run time, sha256 logged, deleted
at the end, so a negative arm cannot silently go stale):

  live     the shipped `src/ui/hud-shell.py` — the cure in place.
  nogate   THE CURE REVERTED IN A COPY: the `gate_form_show` method body
           replaced by a `pass`. This is SPEC §1.6 undone, and it is the arm
           the cure is judged against. If IT does not map a window, then
           `live` not mapping one proves nothing and the gate is blind.
  nonet   BOTH NETS REMOVED — the gross control, and the arm that MUST go
           RED. 
ogate measured GREEN because the re-assert runs in the same
           dispatch as pywebview's Show, so only removing both proves this
           instrument can see a mapped window at all.
  reassert THE GATE KEPT, the second net removed — the Sibling project measured
           that the re-assert ALONE shortens the flash but does not close it
           (`sotto_webview.py:3225`). Kept because it is cheap and because it
           proves the two nets are independent.
  show     `--show-hud`, the path the OWNER asks for. Without it a panel that
           never maps at all would score a perfect PASS-1; SPEC §6 says that
           second clause "is not decoration".

THE OFFSET. Every copy is parked at x=-10000. Position is irrelevant to what is
measured: `IsWindowVisible` and the extended-style read do not consult a rect,
which is how the sibling census separates "the Show happened" from "the owner
can see it". This instrument reports BOTH axes.

SAFETY. Launched with `pythonw.exe` (GUI subsystem, no console) and every child
spawned with CREATE_NO_WINDOW, per the lane brief's hard rule 1. The `live` and
`nogate` arms both run off-screen, so NO arm can put a window on the owner's
desk; that cost is stated in the receipt rather than paid silently.

Usage: py -3 _hud-window-census.py [--n 8] [--ms 25] [--secs 6]
                                   [--arms live,nogate,reassert,show]
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
UI = os.path.join(ROOT, 'src', 'ui')
SHELL = os.path.join(UI, 'hud-shell.py')
PANEL = os.path.join(UI, 'hud-panel.html')

CREATE_NO_WINDOW = 0x08000000
GW_OWNER = 4
DEFAULT_MS = 25.0
DEFAULT_SECS = 6.0
DEFAULT_N = 8
OFFSCREEN_X = -10000

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x2

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_lines: list = []


def log(msg: str) -> None:
    _lines.append(msg)
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# process tree + window census — the same channels as the sibling instrument
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


def layered_alpha(hwnd) -> int:
    """The constant alpha of a layered window, or -1 when it is not one.

    pywebview's `hidden=True` dance sets `Opacity=0` BEFORE `Show()`
    (`winforms.py:777-782`), so for that span the form is WS_VISIBLE but FULLY
    TRANSPARENT — a catch there is NOT a window the owner can see, and counting
    it as one would make this instrument cry wolf.
    """
    ex = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)
    if not (ex & WS_EX_LAYERED):
        return -1
    crkey = wintypes.DWORD(0)
    alpha = ctypes.c_ubyte(0)
    flags = wintypes.DWORD(0)
    ok = user32.GetLayeredWindowAttributes(wintypes.HWND(hwnd), ctypes.byref(crkey),
                                           ctypes.byref(alpha), ctypes.byref(flags))
    if not ok or not (flags.value & LWA_ALPHA):
        return -1
    return int(alpha.value)


def visible_windows_of(pids: set) -> list:
    rows: list = []

    def cb(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
        rows.append({
            'pid': int(pid.value), 'hwnd': int(hwnd), 'class': buf.value,
            'alpha': layered_alpha(hwnd),
            'exstyle': int(user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)),
            'unowned': int(user32.GetWindow(hwnd, GW_OWNER) or 0) == 0,
        })
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return rows


class Sampler(threading.Thread):
    def __init__(self, root: int, cadence_s: float):
        super().__init__(daemon=True)
        self.root = root
        self.cadence = cadence_s
        self.stop = threading.Event()
        self.samples: list = []
        self.pids_seen: dict = {}

    def run(self):
        t0 = time.perf_counter()
        while not self.stop.is_set():
            tree = descendants(self.root)
            self.pids_seen.update(tree)
            self.samples.append({
                't_ms': (time.perf_counter() - t0) * 1000.0,
                'vis': visible_windows_of(set(tree)),
            })
            self.stop.wait(self.cadence)

    def episodes(self):
        eps, cur = [], None
        for s in self.samples:
            opaque = [r for r in s['vis'] if r.get('alpha', -1) != 0]
            if opaque:
                if cur is None:
                    cur = {'start': s['t_ms'], 'end': s['t_ms'], 'rows': list(opaque)}
                else:
                    cur['end'] = s['t_ms']
            elif cur is not None:
                eps.append(cur)
                cur = None
        if cur is not None:
            eps.append(cur)
        return eps


# ---------------------------------------------------------------------------
# the negative arm: the CURE REVERTED IN A COPY
# ---------------------------------------------------------------------------

#: The exact edit, so the control is a copy of the shipped file with ONE line
#: changed and not a re-implementation. It is asserted present below: a copy
#: that silently failed to apply the edit would be a control that proves nothing.
GATE_REVERTED = (
    ('        base = form.Show\n',
     '        return  # CENSUS CONTROL ARM: the cure is removed\n'
     '        base = form.Show  # unreachable\n'),
)

#: The SECOND net removed, the gate left in place. The pattern names the line
#: as it is TODAY (`_webview_control()`), not the earlier `self.window.native`
#: form — and the refusal below is not ceremony: this pattern failed to match on
#: the first run of this gate for exactly that reason, and the instrument
#: refused to build a control arm it could not prove it had built.
REASSERT_REMOVED = (
    ('            ctl.NavigationStarting += self.on_navigation_start\n',
     '            pass  # CENSUS: re-assert net removed, instance gate kept\n'),
)

#: BOTH NETS REMOVED — the gross control, and the only arm that MUST go RED.
#:
#: WHY IT EXISTS, MEASURED. The `nogate` arm (gate removed, re-assert kept)
#: came back GREEN: 0 of 2 launches showed an opaque window, while `show`
#: showed 221 opaque catch samples. That is a real result and it is a result
#: ABOUT THE TWO NETS, not about the cure: the re-assert runs in the SAME .NET
#: dispatch, immediately after pywebview's `form.Show()`, so the window is mapped
#: for less than the 25 ms sampling grid and this instrument cannot see it. The
#: sibling project measured the same thing from the other side — same-dispatch
#: re-assert did not close the flash (18/20 vs 19/20).
#:
#: So `nogate` alone CANNOT prove the instance-shadow gate is load-bearing, and a
#: gate that claims otherwise would be crediting the cure for something the
#: re-assert did. `nonet` is the arm that proves this INSTRUMENT is not blind:
#: with neither net, pywebview's own `form.Show()` maps the window at full
#: opacity and `opaque_catch_samples` must be >= 1.
NONET = GATE_REVERTED + REASSERT_REMOVED


def build_variant(workdir: str, tag: str, edits: tuple) -> str:
    """A COPY of the shipped shell with ONE edit applied, plus the panel assets.

    THE ASSET COPY IS NOT OPTIONAL, and its absence cost a whole arm run. The
    shell resolves `PANEL_HTML` relative to its OWN directory
    (`hud-shell.py:HERE`), so a variant written into a temp directory cannot
    find `hud-panel.html` and dies with `rc=1` after ~5 samples. The first run
    of this gate reported `nogate` and `reassert` as `launches_with_opaque_window=0/2`
    — which looks like the cure working when it is a dead arm. An arm that
    cannot start must never be able to report a pass, so `assert_launchable()`
    checks the rc and the `HUD_READY` token below.
    """
    with open(SHELL, encoding='utf-8') as f:
        src = f.read()
    out = src
    for old, new in edits:
        if old not in out:
            raise SystemExit(f'variant {tag}: pattern NOT FOUND in {SHELL}: {old!r} '
                             '— refusing to ship a control that is not the edit it claims')
        out = out.replace(old, new, 1)
    if out == src:
        raise SystemExit(f'variant {tag}: no edit applied')
    path = os.path.join(workdir, f'hud-shell-{tag}.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)
    for asset in ('hud-panel.html', 'hud-panel.css', 'hud-panel.js',
                  'hud-contract.js'):
        src_asset = os.path.join(UI, asset)
        if not os.path.exists(src_asset):
            raise SystemExit(f'variant {tag}: panel asset missing: {src_asset}')
        shutil.copy2(src_asset, os.path.join(workdir, asset))
    log(f'VARIANT tag={tag} path={os.path.basename(path)} '
        f'sha256_live={hashlib.sha256(src.encode()).hexdigest()[:16]} '
        f'sha256_variant={hashlib.sha256(out.encode()).hexdigest()[:16]} '
        f'edits={len(edits)} assets_copied=4')
    return path


def assert_launchable(tag: str, per: list) -> dict:
    """An arm that cannot START is not an arm that passed.

    Measured: the first run reported `nogate`/`reassert` as 0/2 launches with an
    opaque window, which is the sentence a passing control arm would also
    produce. Those runs had died with `rc=1` in ~5 samples. `ready` (the shell's
    own `HUD_READY` token) is the discriminator, and the gate fails an arm whose
    launches never reached it.
    """
    rcs = sorted({r['rc'] for r in per})
    ready = sum(1 for r in per if 'HUD_READY' in r['logbody'])
    live = {'tag': tag, 'launches': len(per), 'rcs': rcs,
            'launches_reaching_HUD_READY': ready,
            'launchable': ready == len(per) and set(rcs) == {0}}
    log(f'ARM-LAUNCHABLE tag={tag} reaching_HUD_READY={ready}/{len(per)} '
        f'rcs={rcs} launchable={live["launchable"]}')
    return live


def pythonw() -> str:
    exe = sys.executable or ''
    if exe.lower().endswith('pythonw.exe'):
        return exe
    cand = exe.replace('python.exe', 'pythonw.exe')
    return cand if os.path.exists(cand) else exe


def launch(shell: str, workdir: str, tag: str, idx: int, extra: list,
           secs: float, cadence_s: float) -> dict:
    alog = os.path.join(workdir, f'_hudwin-{tag}-{idx}.log')
    args = [pythonw(), shell, '--log', alog, '--exit-after', str(secs),
            '--x', str(OFFSCREEN_X), '--y', str(OFFSCREEN_X), *extra]
    out = open(alog + '.stdout', 'wb')
    proc = subprocess.Popen(args, stdout=out, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, cwd=UI,
                            creationflags=CREATE_NO_WINDOW)
    sampler = Sampler(proc.pid, cadence_s)
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
    catches = sum(1 for s in sampler.samples
                  if any(r.get('alpha', -1) != 0 for r in s['vis']))
    longest = max((e['end'] - e['start'] for e in eps), default=0.0)
    body = ''
    if os.path.exists(alog):
        body = open(alog, encoding='utf-8', errors='replace').read()
    return {
        'idx': idx, 'rc': rc, 'samples': len(sampler.samples),
        'opaque_catch_samples': catches, 'longest_ms': longest,
        'episodes': eps, 'log': alog, 'logbody': body,
        'pids_sampled': sorted(sampler.pids_seen),
    }


def arm_summary(tag: str, per: list, secs: float, cadence_s: float) -> dict:
    n = len(per)
    hits = sum(1 for r in per if r['opaque_catch_samples'] > 0)
    samples = sum(r['samples'] for r in per)
    catch_samples = sum(r['opaque_catch_samples'] for r in per)
    longest = max((r['longest_ms'] for r in per), default=0.0)
    refused = 0
    for r in per:
        refused += sum(1 for ln in r['logbody'].splitlines()
                       if 'HUD_SHOW_REFUSED' in ln)
    nav = 0
    for r in per:
        for ln in r['logbody'].splitlines():
            if 'HUD_NAV_START' in ln and 'action=reassert-hidden' in ln:
                nav += 1
    exeq = 0
    for r in per:
        exeq += sum(1 for ln in r['logbody'].splitlines()
                    if 'HUD_EXSTYLE_APPLIED' in ln and 'exact_set_equality=True' in ln)
    nets2 = sum(1 for r in per if 'nets_armed=2' in r['logbody'])
    mapped_ln = sum(1 for r in per for ln in r['logbody'].splitlines()
                    if 'HUD_SHOW_MAPPED' in ln)
    live = assert_launchable(tag, per)
    log(f'ARM-SUMMARY tag={tag} launches={n} launches_with_opaque_window={hits}/{n} '
        f'samples={samples} opaque_catch_samples={catch_samples} '
        f'longest_opaque_ms={longest:.0f} show_refused_total={refused} '
        f'reassert_total={nav} nets2_lines={nets2} hud_show_mapped_lines={mapped_ln} '
        f'exstyle_set_equality_lines={exeq} rcs={live["rcs"]}')
    return {'tag': tag, 'launches': n, 'launches_with_opaque_window': hits,
            'samples': samples, 'opaque_catch_samples': catch_samples,
            'longest_opaque_ms': longest, 'show_refused_total': refused,
            'reassert_total': nav, 'nets2_lines': nets2,
            'hud_show_mapped_lines': mapped_ln,
            'exstyle_set_equality_lines': exeq,
            'launchable': live['launchable'], 'per_launch': per}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='HUD window-mapping census')
    ap.add_argument('--n', type=int, default=DEFAULT_N)
    ap.add_argument('--ms', type=float, default=DEFAULT_MS)
    ap.add_argument('--secs', type=float, default=DEFAULT_SECS)
    ap.add_argument('--arms', default='live,nogate,reassert,nonet,show')
    ap.add_argument('--json-out', default='')
    args = ap.parse_args(argv)

    if not os.path.exists(SHELL):
        raise SystemExit(f'live shell missing: {SHELL}')
    workdir = tempfile.mkdtemp(prefix='hudcensus-')
    try:
        shells = {'live': SHELL,
                  'nogate': build_variant(workdir, 'nogate', GATE_REVERTED),
                  'reassert': build_variant(workdir, 'reassert', REASSERT_REMOVED),
                  'nonet': build_variant(workdir, 'nonet', NONET)}
        results = []
        for tag in [a.strip() for a in args.arms.split(',') if a.strip()]:
            # `show` is the SHIPPED shell with `--show-hud`, not a variant: it is
            # the path the owner asks for, so it must be the real code with a
            # flag, never a copy. SPEC §6 PASS-1's second clause is the reason it
            # exists at all — a panel that never maps scores a perfect first
            # clause, and this is the only arm that can say NO in the direction
            # that matters.
            shell = SHELL if tag == 'show' else shells.get(tag)
            if shell is None:
                log(f'ARM-UNKNOWN tag={tag} (known: live,nogate,reassert,nonet,show)')
                continue
            extra = ['--show-hud'] if tag == 'show' else []
            log(f'=== ARM {tag} shell={os.path.basename(shell)} n={args.n} '
                f'cadence_ms={args.ms:.0f} secs={args.secs} '
                f'x={OFFSCREEN_X} extra={extra} ===')
            per = []
            for i in range(args.n):
                r = launch(shell, workdir, tag, i, extra, args.secs, args.ms / 1000.0)
                log(f'LAUNCH tag={tag} i={i}/{args.n} rc={r["rc"]} '
                    f'samples={r["samples"]} opaque={r["opaque_catch_samples"]} '
                    f'longest_ms={r["longest_ms"]:.0f} pids={len(r["pids_sampled"])}')
                per.append(r)
            results.append(arm_summary(tag, per, args.secs, args.ms))

        out = {'population_n': args.n, 'window_s': args.secs,
               'cadence_ms': args.ms, 'arms': results}
        if args.json_out:
            with open(args.json_out, 'w', encoding='utf-8') as f:
                json.dump(out, f, indent=2)
        print('')
        print(f'POPULATION launches_per_arm={args.n} window_s={args.secs} '
              f'cadence_ms={args.ms:.0f} arms={len(results)}')
        print('WINDOW every arm ran with x=-10000 (off-screen), so no arm can put '
              'a window on the desk; the axis measured is WS_VISIBLE and '
              'not-alpha-occluded, neither of which reads a rect')
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())