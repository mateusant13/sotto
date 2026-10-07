#!/usr/bin/env python3
"""Build the NEGATIVE ARM: today's shell with ONLY the icon/AUMID fix reverted.

This is the house control pattern (`--neg-arm`): the same file, one difference,
so the before/after pair is measured by the SAME instrument at the SAME moment
rather than by two different instruments. The instrument lines themselves are
kept, so the control arm reports `source=pythonw-fallback:` and
`set=false` from inside its own process.

Writes `app/webview/_negarm_sotto_webview.py` (a SIBLING of the shell, because
the shell imports `hot_reload`/`panel_state` from its own directory) and prints
the sha256 of both files. The copy is deleted by `--clean`.

Run:  python _main/make-no-icon-negarm.py [--clean]
"""
from __future__ import annotations

import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
NEG = os.path.join(ROOT, 'app', 'webview', '_negarm_sotto_webview.py')

REVERTS = (
    # 1. the icon never reaches pywebview
    ('    webview.start(icon=SOTTO_ICON)', '    webview.start()'),
    # 2. the form is never given an icon and no WM_SETICON is sent
    ("        _icon = apply_window_icon(form, self.hwnd)",
     "        _icon = {'applied': False, 'path': None, 'handle': None,\n"
     "                 'reason': 'neg-arm'}"),
    # 3. the process keeps whatever identity it was born with
    ('    _aumid_set = set_process_app_user_model_id()',
     "    _aumid_set = {'set': False, 'hr': None}"),
    # 4. the ex-style the shell asks for is left as WinForms wiped it
    ("        self.ex_style = reassert_taskbar_ex_style(hwnd, 'post-startup-dance')",
     "        self.ex_style = {'where': 'neg-arm'}"),
)


def main() -> int:
    if '--clean' in sys.argv:
        if os.path.exists(NEG):
            os.remove(NEG)
        print(f'removed {NEG}')
        return 0
    with open(SHELL, 'r', encoding='utf-8') as fh:
        src = fh.read()
    for old, new in REVERTS:
        if src.count(old) != 1:
            print(f'REFUSED: {old!r} occurs {src.count(old)} times')
            return 2
        src = src.replace(old, new)
    with open(NEG, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(src)
    for path in (SHELL, NEG):
        with open(path, 'rb') as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        print(f'{digest}  {os.path.getsize(path):>7} B  {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
