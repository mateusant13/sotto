"""Does a process spawned by THIS harness shell get a VISIBLE console window?

The house rule is "never leave a visible console window on the owner's screen",
and the measured facts in AGENTS.md are about `hidden-spawn.py` (hwnd=0) versus
`Shell.Run(..., 0)` (hwnd!=0). Neither says what THIS harness shell does when it
spawns `py -3`, so it is measured here instead of assumed.

The claim under test is about the WINDOW, not the console: `GetConsoleWindow()`
returns a handle even for a console nobody can see, so the probe reports BOTH
the handle and `IsWindowVisible()` on it -- an allocated-but-invisible console
is not a window on the owner's screen, and `hwnd != 0` alone would confuse the
two (that is the exact mistake `hidden-spawn.py` documents in its header).

    py -3 _main/_runcmd-console-probe.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import subprocess
import sys

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)

CREATE_NO_WINDOW = 0x08000000


def console_state(label: str) -> None:
    hwnd = kernel32.GetConsoleWindow()
    if hwnd:
        visible = bool(user32.IsWindowVisible(wintypes.HWND(hwnd)))
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(wintypes.HWND(hwnd), cls, 256)
        cls_name = cls.value
    else:
        visible, cls_name = False, ''
    print(f'{label} pid={__import__("os").getpid()} '
          f'GetConsoleWindow={hwnd} IsWindowVisible={visible} class={cls_name!r}',
          flush=True)


def main() -> int:
    console_state('SELF')

    # a child spawned the way this harness spawns one: no creationflags
    bare = subprocess.run(
        [sys.executable, '-c',
         'import ctypes,os;'
         'h=ctypes.WinDLL("kernel32").GetConsoleWindow();'
         'v=ctypes.WinDLL("user32").IsWindowVisible(ctypes.c_void_p(h)) if h else False;'
         'print(f"CHILD_BARE hwnd={h} visible={bool(v)}")'],
        capture_output=True, text=True)
    print(bare.stdout.strip() or f'CHILD_BARE rc={bare.returncode} '
                                f'stderr={bare.stderr.strip()!r}', flush=True)

    # the sanctioned form
    try:
        sys.path.insert(0, r'I:\!manager\scripts')
        import spawn_hidden  # noqa: E402
        got = spawn_hidden.run_hidden(
            [sys.executable, '-c',
             'import ctypes;'
             'h=ctypes.WinDLL("kernel32").GetConsoleWindow();'
             'print(f"CHILD_HIDDEN hwnd={h}")'])
        print((got.stdout or '').strip() or f'CHILD_HIDDEN rc={got.returncode} '
                                            f'stderr={(got.stderr or "").strip()!r}',
              flush=True)
    except Exception as exc:  # noqa: BLE001 -- the probe reports, never raises
        print(f'CHILD_HIDDEN unavailable: {exc!r}', flush=True)

    return 0


if __name__ == '__main__':
    sys.exit(main())
