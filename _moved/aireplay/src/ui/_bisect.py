#!/usr/bin/env python3
"""SCRATCH: build single-change COPIES of `hud-shell.py` to bisect why the panel
never reaches `on_loaded`. Each copy is the live file with ONE textual change, so
a variant that loads names the line that mattered.

Not a gate. It writes into `src/ui/_bisect/` and is deleted by the receipt step.
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'hud-shell.py')
OUT = os.path.join(HERE, '_bisect')

VARIANTS = {
    # The copies live one directory down, and `PANEL_HTML` is derived from
    # `HERE`, so every copy is re-pointed at the real panel/asset directory first.
    'minimal': [
        (r"HERE = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)",
         "HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # BISECT"),
        (r"        self\.gate_form_show\(form\)\n", "        pass  # BISECT: gate removed\n"),
        (r"            ctl\.NavigationStarting \+= self\.on_navigation_start\n",
         "            pass  # BISECT: nav hook removed\n"),
        (r"        self\.exstyle_ok = apply_hud_styles\(self\.hwnd\)\n",
         "        self.exstyle_ok = True  # BISECT: exstyles removed\n"),
        (r"        self\.exstyle_ok = apply_hud_styles\(self\.hwnd\)\n",
         "        self.exstyle_ok = True  # BISECT: exstyles removed\n"),
    ],
    # Everything kept except the ex-style writes.
    'noexstyle': [
        (r"HERE = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)",
         "HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # BISECT"),
        (r"        self\.exstyle_ok = apply_hud_styles\(self\.hwnd\)\n",
         "        self.exstyle_ok = True  # BISECT: exstyles removed\n"),
        (r"        self\.exstyle_ok = apply_hud_styles\(self\.hwnd\)\n",
         "        self.exstyle_ok = True  # BISECT: exstyles removed\n"),
    ],
    # Everything kept except the navigation re-assert (the Hide on nav start).
    'nonet': [
        (r"HERE = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)",
         "HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # BISECT"),
        (r"        self\.gate_form_show\(form\)\n", "        pass  # BISECT: gate removed\n"),
        (r"            ctl\.NavigationStarting \+= self\.on_navigation_start\n",
         "            pass  # BISECT: nav hook removed\n"),
    ],
    # STAGING BOUNCE: open the empty stage page, then navigate to the panel.
    'stage': [
        (r"HERE = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)",
         "HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # BISECT"),
        (r"            url=PANEL_HTML,", "            url=STAGE_HTML,  # BISECT"),
        (r"    def on_loaded\(self\):\n",
         "    def on_loaded(self):\n"
         "        if not getattr(self, 'staged', False):  # BISECT: staging bounce\n"
         "            self.staged = True\n"
         "            self.window.load_url(PANEL_HTML)\n"
         "            return\n"),
    ],
    # Same as live, except the window is NOT frameless.
    'noframe': [
        (r"HERE = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)",
         "HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # BISECT"),
        (r"            frameless=True,", "            frameless=False,  # BISECT"),
    ],
}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    with open(SRC, encoding='utf-8') as f:
        text = f.read()
    for name, subs in VARIANTS.items():
        out = text
        for pat, rep in subs:
            new, n = re.subn(pat, rep, out)
            if n == 0:
                print(f'{name}: PATTERN DID NOT MATCH -> {pat[:48]}')
            out = new
        path = os.path.join(OUT, f'hud-shell-{name}.py')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(out)
        print(f'{name}: {path} ({len(out)} B)')
    return 0


if __name__ == '__main__':
    sys.exit(main())