#!/usr/bin/env python3
"""Build the audit render harness from the LIVE panel files.

It does not paraphrase the panel: it reads `app/panel/panel.html`, rewrites
ONLY the asset URLs (so the page can be opened from this directory) and inserts
the two harness scripts around `panel.js`. `panel.css`,
`caption-formulation.js`, `history-source.js`, `surface.js` and `panel.js` are
loaded as the real files, so what renders is the shipped markup and styling.

SINCE 2026-10-08 THIS IS THE ONLY FILE A HUMAN NEEDS TO OPEN to see BOTH
surfaces: `?wired=1#strip`, `#strip-live` and `#pause-confirm` are the new
states, and they run the SAME `panel.js` the app runs. The states and what to
click are listed in `_main/receipt-panel-two-surfaces.md`.

── THE FIVE THEMES (theme lane, added on top of the above) ───────────────────
SINCE 2026-10-08 THE PANEL LINKS THE THEME FILES ITSELF — `panel.html` carries
`themes/fonts.css`, the five `themes/theme-N.css`, `themes/themes.js` and
`theme-switcher.js`, and `<html data-theme="theme-1">`. This generator used to
INJECT those, with an assertion that they were missing; it no longer does, because
a harness that adds a second copy of a stylesheet is a harness that no longer
measures the panel. It still rewrites every asset URL (now including the theme
files and the bundled fonts) so the page opens from this directory, and it still
adds `harness-themes.css`, which styles ONLY the toolbar and the iframes.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir, 'app', 'panel'))
OUT = os.path.join(HERE, 'panel-harness.html')
REL = '../../app/panel/'

with open(os.path.join(SRC, 'panel.html'), encoding='utf-8') as fh:
    html = fh.read()

ASSETS = ('panel.css', 'caption-formulation.js', 'history-source.js', 'surface.js',
          'panel.js', 'theme-switcher.js', 'themes/themes.js', 'themes/fonts.css',
          'themes/theme-1.css', 'themes/theme-2.css', 'themes/theme-3.css',
          'themes/theme-4.css', 'themes/theme-5.css')
for asset in ASSETS:
    if f'"{asset}"' not in html:
        raise SystemExit(f'panel.html no longer references {asset!r} - harness not built')
    html = html.replace(f'"{asset}"', f'"{REL}{asset}"')

# ONLY the harness chrome is injected now.
head_marker = f'<link rel="stylesheet" href="{REL}panel.css" />'
assert head_marker in html, 'panel.css tag not found'
html = html.replace(
    head_marker,
    head_marker
    + '\n    <!-- The HARNESS toolbar and iframe chrome. Not part of the panel and\n'
    + '         not one of the five theme files. -->\n'
    + '    <link rel="stylesheet" href="harness-themes.css" />'
)

marker = f'<script src="{REL}surface.js"></script>'
assert marker in html, 'surface.js tag not found'
# `stub.js` defines `window.sotto` and must run BEFORE panel.js parses (the same
# ordering the shell achieves with `stage.html`); `surface.js` keeps the position
# the panel gave it, because the surface the driver chose from the URL hash has to
# be in place when panel.js paints. `drive.js` runs last, after panel.js.
html = html.replace(marker, '<script src="stub.js"></script>\n    ' + marker)

marker = f'<script src="{REL}panel.js"></script>'
assert marker in html, 'panel.js tag not found'
html = html.replace(marker, marker + '\n    <script src="drive.js"></script>')

# The harness must not be mistaken for the panel: name it in the title.
html = html.replace('<title>Sotto</title>', '<title>Sotto (audit harness)</title>')

with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(html)

print('wrote', OUT, len(html.encode('utf-8')), 'bytes')
for tag in re.findall(r'<(?:script src|link rel="stylesheet" href)="[^"]+"', html):
    print('  ', tag)
