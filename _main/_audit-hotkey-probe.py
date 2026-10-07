#!/usr/bin/env python3
"""Can THIS box register Alt+C right now — and which accelerators are free?

WHY: Alt+C is the app's ONLY control. `HotkeyThread.run` calls
`RegisterHotKey(NULL, id, MOD_ALT | MOD_NOREPEAT, 'C')` and, when that fails,
logs `HOTKEY_REGISTER_FAILED` and RETURNS — so the app is running, hidden, and
answers nothing. The owner sees a dead app with no message, because the whole
design is "nothing appears on screen until you ask". "Alt+C does nothing" is
therefore most likely this single call failing against a hotkey another program
already owns, and that is measurable in milliseconds.

WHAT IT DOES: for each candidate accelerator, register it on this thread exactly
the way the shell does (`hWnd=NULL`, `MOD_NOREPEAT`), record the result and
`GetLastError`, then UNREGISTER IMMEDIATELY. Nothing is left registered, no window
is created, no audio device is opened, and the whole run is a few hundred ms — the
only side effect is that the key is grabbed for microseconds at a time.

    cmd /c "python _main\\_audit-hotkey-probe.py > _main\\_audit-probe\\hotkey.log 2>&1"

Exit 0 always: this is a measurement. Read the table.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, '_audit-probe', 'hotkey.log')

user32 = ctypes.WinDLL('user32', use_last_error=True)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
_HOTKEY_ID = 0x534F  # 'SO' — the shell's own id

#: `(label, modifiers, virtual-key)` — the shipped one first, then the fallbacks
#: a fix could take. Alt+Shift+<key> and Ctrl+Alt+<key> are the conventional
#: choices precisely because vendors grab the plain ones.
CANDIDATES = (
    ('Alt+C (SHIPPED)', MOD_ALT, ord('C')),
    ('Alt+Shift+C', MOD_ALT | MOD_SHIFT, ord('C')),
    ('Ctrl+Alt+C', MOD_CONTROL | MOD_ALT, ord('C')),
    ('Ctrl+Shift+C', MOD_CONTROL | MOD_SHIFT, ord('C')),
    ('Alt+S', MOD_ALT, ord('S')),
    ('Alt+Shift+S', MOD_ALT | MOD_SHIFT, ord('S')),
    ('Ctrl+Alt+S', MOD_CONTROL | MOD_ALT, ord('S')),
    ('Alt+F9', MOD_ALT, 0x78),
    ('Alt+Shift+F9', MOD_ALT | MOD_SHIFT, 0x78),
    ('Ctrl+Alt+L', MOD_CONTROL | MOD_ALT, ord('L')),
)

ERROR_ALREADY_REGISTERED = 1409

lines: list[str] = []


def say(msg: str) -> None:
    lines.append(msg)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(msg, flush=True)


def describe(err: int) -> str:
    if err == 0:
        return 'ok'
    if err == ERROR_ALREADY_REGISTERED:
        return 'ALREADY REGISTERED by another program (1409)'
    if err == 5:
        return 'ACCESS DENIED (5) — a lower-integrity or higher-integrity holder'
    if err == 1400:
        return 'INVALID WINDOW HANDLE (1400) — hWnd is not NULL here'
    return f'error {err}'


def main() -> int:
    # The shell forces a message queue into existence before registering
    # (`PeekMessageW` on a thread that has never pumped is refused), so this probe
    # does the same or it would measure a different call.
    class MSG(ctypes.Structure):
        _fields_ = [('hwnd', wt.HWND), ('message', wt.UINT),
                    ('wParam', wt.WPARAM), ('lParam', wt.LPARAM),
                    ('time', wt.DWORD), ('pt_x', wt.LONG), ('pt_y', wt.LONG)]

    msg = MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

    say('accelerator             register  GetLastError / meaning')
    say('----------------------  --------  -----------------------------')
    results = {}
    for label, mods, vk in CANDIDATES:
        ctypes.set_last_error(0)
        ok = bool(user32.RegisterHotKey(None, _HOTKEY_ID, mods | MOD_NOREPEAT, vk))
        err = ctypes.get_last_error()
        results[label] = ok
        say(f'{label:22s}  {"YES" if ok else "NO ":8s}  {describe(err)}')
        if ok:
            time.sleep(0.02)
            user32.UnregisterHotKey(None, _HOTKEY_ID)

    say('')
    shipped = results.get('Alt+C (SHIPPED)', False)
    if shipped:
        say('VERDICT: Alt+C IS REGISTRABLE on this box right now.')
        say('  So a dead Alt+C is NOT a taken key. Look next at the panel path:')
        say('  HOTKEY_REGISTERED in the log, PANEL_SHOWN on the keypress, and')
        say('  PANEL_VISIBILITY_* to see whether the window is ever MAPPED.')
    else:
        free = [k for k, v in results.items() if v and 'SHIPPED' not in k]
        say('VERDICT: Alt+C IS TAKEN — another program owns MOD_ALT + C.')
        say('  THE APP CANNOT WORK AS SHIPPED ON THIS BOX: `HotkeyThread.run` logs')
        say('  HOTKEY_REGISTER_FAILED and returns, so Alt+C answers nothing and the')
        say('  owner is shown no message at all (the panel is hidden by design).')
        say(f'  Free alternatives measured just now: {free if free else "(none)"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
