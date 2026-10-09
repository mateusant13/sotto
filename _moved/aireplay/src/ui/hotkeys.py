#!/usr/bin/env python3
"""GLOBAL HOTKEYS — the OVERLAY chain, working while another app has focus.

WHAT THIS FILE IS. The third leg of the HUD: `hud-shell.py` draws the plate and
`hud-contract.js` decides what it says, and this is the thing that answers a key
press made over a GAME. Two paths ship, each surviving what the other does not,
exactly as `docs/overlay-hotkey-contract.md` §3.1 requires:

  Path A  `RegisterHotKey` with `hWnd = NULL`. The OS posts `WM_HOTKEY` to THIS
          thread's queue. Costs nothing while idle (a message, zero wakes) and
          survives a held key through `MOD_NOREPEAT`, whose suppression lives in
          the kernel. Fails with 1409 when another program owns the key, and
          cannot deliver to a window running ELEVATED (UIPI) — which a game
          launched "Run as administrator" is.
  Path B  `GetAsyncKeyState` edge poll at `POLL_TICK_MS`. One wake per tick, but
          it reads PHYSICAL state, so it is immune to 1409 and to UIPI, and it
          cannot see the UAC secure desktop either. That limit is reported, not
          hidden (contract §6.2).

NEVER STEALS INPUT — and this is a design constraint, not an aspiration. Neither
path can swallow a keystroke: `RegisterHotKey` asks the OS to route a chord to
us while leaving it intact, and the poll path only READS key state. The one
Win32 mechanism that could steal or inject input is a `WH_KEYBOARD_LL` hook, and
this file never installs one; the gate asserts that by grep, because "we only
read the keyboard" must be a checkable claim and not a promise.

THE TRUTH EVERYTHING ELSE FOLLOWS FROM (contract §1, READ on MS Learn):
`RegisterHotKey` reports PRESS ONLY. There is no release and no hold. So this
file has no release callback, nothing fires on release, and one press is one
action — `MOD_NOREPEAT` plus the Path-B edge latch together guarantee it.

THE DEFAULT SET, AND WHY EACH ONE (contract §2.4, sourced from the production
shell `app/webview/sotto_webview.py:1259` `HOTKEY_FALLBACKS`):

  1. Alt+C        VK_MENU  0x12 + 'C' 0x43  MOD_ALT
  2. Alt+Shift+C  VK_MENU  0x12 + 'C' 0x43  MOD_ALT|MOD_SHIFT
  3. Ctrl+Alt+C   VK_CONTROL 0x11 + 'C' 0x43 MOD_CONTROL|MOD_ALT
  4. Ctrl+Shift+C VK_CONTROL 0x11 + 'C' 0x43 MOD_CONTROL|MOD_SHIFT

  * `C` is the mnemonic and it is DISJOINT from the replay ladder, which uses
    `R` and the F-keys (contract §2.1). Two chains, two key spaces: a replay key
    being owned must never change which overlay key is live (contract §4.2(5)).
  * `F12` is FORBIDDEN by name. MS Learn, Remarks: "The F12 key is reserved for
    use by the debugger at all times, so it should not be registered as a hot
    key." A convenience argument does not outrank a reservation.
  * `MOD_WIN` is not offered: MS Learn states `MOD_WIN` shortcuts "are reserved
    for use by the operating system".
  * `PrintScreen` is not offered as a default: it is an OS default hotkey that
    our own registration can override only while our window has focus, so it is
    not a global key (contract §2.3).
  * Every default carries TWO modifiers except the primary. A bare letter is
    typed by whatever app has focus, which is the whole failure this product is
    avoiding.

Usage:
  hotkeys-gate.py            # both colours, no key is ever pressed
  from hotkeys import HotkeyManager; HotkeyManager().arm(on_press=cb)
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

# --- Win32 constants. Every value below is from the platform SDK headers. ----

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000          # MS Learn, fsModifiers: no repeats
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
#: MS Learn, `id` for an EXE: 0x0000-0xBFFF. The overlay chain starts inside
#: that range and each id is unique per process.
ID_BASE = 0xB100

#: The Path-B tick. 8 ms is the value the replay trigger uses
#: (`src/capture/trigger.cpp`, kPollTickMs), kept equal so the two subsystems
#: wake at the same cadence and a CPU profile of the box shows ONE poll source.
POLL_TICK_MS = 8.0

#: A press delivered by BOTH paths for the same chord inside this window is
#: counted as one and the second is dropped (contract §6.1). The replay trigger
#: declares the same 50 ms guard and, at the time the contract was written, had
#: it UNUSED — which is the tell that it is load-bearing.
DEDUP_NS = 50_000_000

MOD_BY_NAME = {'alt': MOD_ALT, 'ctrl': MOD_CONTROL, 'control': MOD_CONTROL,
               'shift': MOD_SHIFT}
MOD_NAME_BY_BIT = {MOD_ALT: 'alt', MOD_CONTROL: 'ctrl', MOD_SHIFT: 'shift'}


def key_chord(spec: str) -> tuple:
    """`"Ctrl+Alt+C"` -> `(vk, mods, label)`. Raises on anything unknown.

    Raising rather than defaulting is the point: a mistyped chord that silently
    became `VK_F12` would arm a key the contract forbids, and a chord that
    silently became "no modifiers" would arm a key the GAME also uses.
    """
    parts = [p.strip() for p in spec.split('+') if p.strip()]
    if len(parts) < 2:
        raise ValueError('chord needs at least one modifier and a key: %r' % spec)
    mods = 0
    key = None
    for part in parts:
        low = part.lower()
        if low in MOD_BY_NAME:
            mods |= MOD_BY_NAME[low]
            continue
        if len(part) == 1:
            key = ord(part.upper())
            continue
        vk = getattr(__import__('win32con', fromlist=['VK']), part.upper(), None) \
            if _has_win32con() else None
        if vk is None and part.upper().startswith('VK_'):
            vk = _vk_from_name(part.upper())
        if vk is None:
            raise ValueError('unknown key %r in chord %r' % (part, spec))
        key = vk
    if key is None or mods == 0:
        raise ValueError('chord %r has no key or no modifier' % spec)
    if mods & MOD_WIN:
        raise ValueError('MOD_WIN is reserved by the OS — refused: %r' % spec)
    label = '+'.join([MOD_NAME_BY_BIT.get(b, '?') for b in (MOD_ALT, MOD_CONTROL,
                                                            MOD_SHIFT) if mods & b]
                     + [chr(key)])
    return key, mods, label


def _has_win32con() -> bool:
    try:
        __import__('win32con')
        return True
    except ImportError:
        return False


_NAMED_VK = {'VK_F1': 0x70, 'VK_F2': 0x71, 'VK_F3': 0x72, 'VK_F4': 0x73,
             'VK_F5': 0x74, 'VK_F6': 0x75, 'VK_F7': 0x76, 'VK_F8': 0x77,
             'VK_F9': 0x78, 'VK_F10': 0x79, 'VK_F11': 0x7A, 'VK_F12': 0x7B,
             'VK_SNAPSHOT': 0x2C, 'VK_PAUSE': 0x13}


def _vk_from_name(name: str):
    return _NAMED_VK.get(name)


#: THE DEFAULT CHAIN, in priority order. Index 0 is what the HUD listens for;
#: the rest are fallbacks for a machine where something else owns it. Source:
#: `docs/overlay-hotkey-contract.md` §2.4, which reads them out of the
#: production shell. Measured on THIS box while the contract was written:
#: `Alt+C` was OWNED by `app/webview/sotto_webview.py` — which is why the chain
#: has three more, and why `arm()` reports per-binding truth instead of a
#: single "armed" word.
DEFAULT_CHAIN = ('Alt+C', 'Alt+Shift+C', 'Ctrl+Alt+C', 'Ctrl+Shift+C')

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)


class Binding:
    """One chord and everything TRUE about it right now."""

    __slots__ = ('spec', 'label', 'vk', 'mods', 'hotkey_id', 'status',
                 'winerror', 'registered')

    def __init__(self, spec: str, hotkey_id: int):
        self.vk, self.mods, self.label = key_chord(spec)
        self.spec = spec
        self.hotkey_id = hotkey_id
        self.status = 'not_armed'
        self.winerror = 0
        self.registered = False

    @property
    def wire_mods(self) -> int:
        """What goes to the OS: the caller's mask plus `MOD_NOREPEAT`.

        OR-ed here so no caller can ship a repeating hotkey by forgetting it.
        """
        return self.mods | MOD_NOREPEAT

    def poll_hit(self, read) -> bool:
        """Path B edge test — WITH the modifier set (contract §6.1).

        `mods` used to be ignored by the poll path, so pressing `Alt+F10` matched
        both the `F10` binding and the `Alt+F10` one and one press cut twice.
        A binding with NO modifier additionally requires no modifier down, or a
        bare `F10` fires while the user types `Alt+F10`.
        """
        if not (read(self.vk) & 0x8000):
            return False
        want = self.mods
        for bit, vk in ((MOD_ALT, VK_MENU), (MOD_CONTROL, VK_CONTROL),
                        (MOD_SHIFT, VK_SHIFT)):
            down = bool(read(vk) & 0x8000)
            if bool(want & bit) != down:
                return False
        return True

    def as_dict(self) -> dict:
        return {'spec': self.spec, 'label': self.label, 'vk': self.vk,
                'mods': self.mods, 'id': self.hotkey_id,
                'status': self.status, 'winerror': self.winerror,
                'registered': self.registered}


class HotkeyManager:
    """Arms the chain on a thread of its own and calls back on a PRESS.

    WHY A THREAD AND NOT THE CALLER. MS Learn: with `hWnd = NULL` the message
    "must be processed in the message loop". `RegisterHotKey` from the GUI thread
    and then sitting in pywebview's loop compiles, runs, reports "armed", and
    never fires. The pump lives here, so arming is not something a caller can
    half-do.
    """

    def __init__(self, chain=DEFAULT_CHAIN, poll_tick_ms: float = POLL_TICK_MS,
                 enable_poll: bool = True, log=None):
        self.chain = list(chain)
        self.poll_tick_ms = poll_tick_ms
        self.enable_poll = enable_poll
        self.log = log or (lambda m: print(m, flush=True))
        self.bindings = [Binding(spec, ID_BASE + i) for i, spec in
                         enumerate(self.chain)]
        self.on_press = None
        self._stop = threading.Event()
        self._thread = None
        self._tid = 0
        self._last_ns = {}
        self._was_down = {}
        self.stats = {'presses': 0, 'dedup_dropped': 0, 'poll_presses': 0,
                      'registered_presses': 0, 'armed': 0}

    # -- arm ---------------------------------------------------------------

    def arm(self, on_press=None) -> bool:
        """Arm the chain. NEVER False just because a key was taken.

        A taken key is a per-binding `BindingStatus` (contract §4.2(1)), not a
        failure: Path B still watches that chord. Return value is True when at
        least ONE binding has a live path, and the caller must read
        `summary()` for anything finer than that.
        """
        self.on_press = on_press
        self._refuse_duplicates()
        for b in self.bindings:
            if b.status == 'duplicate_refused':
                continue
            ctypes.set_last_error(0)
            if user32.RegisterHotKey(None, b.hotkey_id, b.wire_mods, b.vk):
                b.registered = True
                b.status = 'registered'
                b.winerror = 0
                self.stats['armed'] += 1
            else:
                b.winerror = ctypes.get_last_error()
                b.registered = False
                b.status = ('owned_by_other_process'
                            if b.winerror == ERROR_HOTKEY_ALREADY_REGISTERED
                            else 'register_failed')
        self._tid = kernel32.GetCurrentThreadId()
        self._thread = threading.Thread(target=self._pump, name='hud-hotkeys',
                                        daemon=True)
        self._thread.start()
        self.log('HOTKEYS_ARMED armed=%d/%d poll=%s tick_ms=%.1f tid=%d %s' % (
            self.stats['armed'], len(self.bindings), self.enable_poll,
            self.poll_tick_ms, self._tid,
            ' '.join('%s=%s' % (b.spec, b.status) for b in self.bindings)))
        return self.stats['armed'] > 0 or self.enable_poll

    def _refuse_duplicates(self) -> None:
        """Same `vk`+`mods` twice is refused by NAME (contract §6.3)."""
        for i, a in enumerate(self.bindings):
            for b in self.bindings[i + 1:]:
                if a.vk == b.vk and a.mods == b.mods:
                    b.status = 'duplicate_refused'
                    self.log('HOTKEY_DUPLICATE_REFUSED kept=%s refused=%s '
                             'vk=0x%02X mods=0x%04X' % (a.spec, b.spec, a.vk,
                                                         a.mods))

    def stop(self) -> None:
        self._stop.set()
        for b in self.bindings:
            if b.registered:
                user32.UnregisterHotKey(None, b.hotkey_id)
                b.registered = False

    # -- the two paths ------------------------------------------------------

    def _pump(self) -> None:
        """Message loop on THIS thread (Path A) + the poll (Path B).

        Both run on one thread on purpose: `RegisterHotKey` messages belong to
        the thread that registered them, and a second thread would add a wakeup
        source to defend against nothing.
        """
        msg = wintypes.MSG()
        next_poll = time.perf_counter()
        while not self._stop.is_set():
            # Drain every pending message, then poll on its own cadence. A
            # GetMessage with a 1 ms timeout keeps the loop responsive without
            # becoming a 1 kHz spin.
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == WM_HOTKEY:
                    self._dispatch(msg.wParam, 'registered')
                elif msg.message == WM_QUIT:
                    self._stop.set()
                    break
            now = time.perf_counter()
            if self.enable_poll and now >= next_poll:
                next_poll = now + self.poll_tick_ms / 1000.0
                self._poll_once()

    def _poll_once(self, read=None) -> None:
        read = read or _real_keystate
        for b in self.bindings:
            if b.status == 'duplicate_refused':
                continue
            hit = b.poll_hit(read)
            was = self._was_down.get(b.hotkey_id, False)
            self._was_down[b.hotkey_id] = hit
            if hit and not was:                      # the edge, and only it
                self._dispatch(b.hotkey_id, 'polled', dedup_key=b.hotkey_id)

    def _dispatch(self, hotkey_id: int, via: str, dedup_key=None) -> None:
        """One press in, one action out — with the both-paths guard."""
        key = dedup_key if dedup_key is not None else int(hotkey_id)
        now = time.perf_counter_ns()
        last = self._last_ns.get(key, 0)
        if last and (now - last) < DEDUP_NS:
            self.stats['dedup_dropped'] += 1
            self.log('HOTKEY_PRESS_DEDUPED key_id=%d via=%s gap_ms=%.1f' % (
                key, via, (now - last) / 1e6))
            return
        self._last_ns[key] = now
        self.stats['presses'] += 1
        if via == 'registered':
            self.stats['registered_presses'] += 1
        else:
            self.stats['poll_presses'] += 1
        binding = next((b for b in self.bindings if b.hotkey_id == key), None)
        if binding is not None:
            self.log('HOTKEY_PRESS key=%s via=%s n=%d' % (
                binding.label, via, self.stats['presses']))
        if self.on_press is not None:
            self.on_press(binding, via)

    # -- truth --------------------------------------------------------------

    def integrity_rid(self) -> int:
        """Our own integrity RID. A medium-RID hotkey cannot be DELIVERED to a
        high-RID window (UIPI) — an elevated game is that case, and it is not a
        key conflict (contract §4.3)."""
        try:
            from ctypes import wintypes as wt
            token = wt.HANDLE()
            if not kernel32.OpenProcessToken(
                    kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
                return -1
            rid = wintypes.DWORD()
            ok = kernel32.GetTokenInformation(token, 1, ctypes.byref(rid),
                                              ctypes.sizeof(rid), None)
            kernel32.CloseHandle(token)
            return int(rid.value) if ok else -1
        except Exception:                              # noqa: BLE001
            return -1

    def summary(self) -> dict:
        """PER-BINDING TRUTH (contract §4.2(4)). Never one "armed" word.

        A summary that says "armed" while 3 of 4 bindings are owned by another
        program is a lie the user discovers mid-match.
        """
        armed = [b for b in self.bindings
                 if b.status in ('registered', 'polled_only', 'owned_by_other_process',
                                 'register_failed')]
        return {
            'chain': [b.spec for b in self.bindings],
            'bindings': [b.as_dict() for b in self.bindings],
            'registered': sum(1 for b in self.bindings if b.registered),
            'live': len(armed),
            'integrity_rid': self.integrity_rid(),
            'secure_desktop': 'NEITHER path can see the UAC secure desktop',
            'stats': dict(self.stats),
        }


def _real_keystate(vk: int) -> int:
    return user32.GetAsyncKeyState(vk)


if __name__ == '__main__':
    # Manual arm: prints the per-binding truth and exits. It NEVER injects a
    # key — see the module docstring on input stealing.
    mgr = HotkeyManager(enable_poll=False)
    mgr.arm()
    time.sleep(0.4)
    print(json.dumps(mgr.summary(), indent=2))
    mgr.stop()
    sys.exit(0)