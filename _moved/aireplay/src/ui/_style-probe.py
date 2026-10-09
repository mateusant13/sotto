#!/usr/bin/env python3
"""SCRATCH: why does WS_EX_WINDOWEDGE (0x100) come back after SetWindowLongW?

Prints the ex-style after each step, on a plain WinForms form created the way
pywebview creates one (no frameless). Run with pythonw.exe + `--out` so no
console can appear on the owner's screen.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes

GWL_EXSTYLE = -20
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
REQUIRED = 0x080800A8

user32 = ctypes.WinDLL('user32', use_last_error=True)


def hwnd_of(form) -> int:
    h = getattr(form, 'Handle', None)
    for attr in ('ToInt64', 'ToInt32'):
        fn = getattr(h, attr, None)
        if fn is not None:
            return int(fn())
    return int(h)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    lines = []

    def say(tag, v):
        lines.append(f'{tag:38s} 0x{(v & 0xFFFFFFFF):08X}')

    import clr
    clr.AddReference('System.Windows.Forms')
    from System.Windows.Forms import Application, Form
    app = Application()
    form = Form()
    form.Opacity = 0.0
    form.Show()
    form.Hide()
    form.Opacity = 1.0
    hwnd = hwnd_of(form)
    lines.append(f'hwnd={hwnd}')

    say('0 as-created', user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE))
    user32.SetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE, REQUIRED)
    say('1 after write', user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE))
    user32.SetWindowPos(wintypes.HWND(hwnd), 0, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER |
                        SWP_NOACTIVATE | SWP_FRAMECHANGED)
    say('2 after FRAMECHANGED', user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE))
    user32.SetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE, REQUIRED)
    say('3 after rewrite', user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE))
    # THE OTHER ORDER: frame change FIRST, then a single style write.
    form2 = Form()
    form2.Opacity = 0.0
    form2.Show()
    form2.Hide()
    form2.Opacity = 1.0
    h2 = hwnd_of(form2)
    say('4 second form as-created', user32.GetWindowLongW(wintypes.HWND(h2), GWL_EXSTYLE))
    user32.SetWindowPos(wintypes.HWND(h2), 0, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER |
                        SWP_NOACTIVATE | SWP_FRAMECHANGED)
    user32.SetWindowLongW(wintypes.HWND(h2), GWL_EXSTYLE, REQUIRED)
    say('5 framechange-then-write', user32.GetWindowLongW(wintypes.HWND(h2), GWL_EXSTYLE))
    form.Dispose()
    form2.Dispose()
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as _exc:  # pythonw has no stderr: write it instead
        import traceback
        import sys as _sys
        out = _sys.argv[_sys.argv.index('--out') + 1]
        with open(out, 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
        raise SystemExit(1)
