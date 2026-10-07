#!/usr/bin/env python3
"""BUNDLE the five design directions' typefaces into the panel, locally.

WHY THIS FILE EXISTS. The five directions name five families — Barlow Condensed,
IBM Plex Mono, Newsreader, Fraunces, Space Grotesk. The design app in
`H:\\aireplay\\docs\\design\\sotto-app-design-directions` loads them from
`fonts.googleapis.com`, and THE PANEL CANNOT: it is a `file://` document under
`Content-Security-Policy: default-src 'none'` (panel.html), it must work with no
network at all, and this repo's rules forbid remote content in the panel. Without
a bundle, `font-family: "Barlow Condensed"` resolves to nothing on this box —
MEASURED 2026-10-08: the MACHINE-WIDE font directory `C:\\Windows\\Fonts` carries
NONE of the five (the owner's five installs are PER-USER, in
`%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts` registered under HKCU — verified there
2026-10-07) — and every theme would silently paint a system fallback, i.e. five
colour schemes pretending to be five designs. **The bundle is what makes the panel
independent of that installation either way**: the panel is a `file://` document
and it must paint correctly on a box where the owner installed nothing.

WHAT IT WRITES, and both paths are inside `app/panel/`:

  `fonts/<family>-latin-<weight>-normal.woff2`   14 files, ~239 KB total
  `themes/fonts.css`                             one `@font-face` per file

`themes/fonts.css` is linked by `panel.html` BEFORE `panel.css`, so all five
families are available to every theme and a theme only has to NAME one. It is a
plain stylesheet like the five theme files, and — unlike them — it is NOT scoped
to a theme: an `@font-face` has no selector and declares no colours, so it cannot
collide with anything. That is also why `theme-assert-lib.js` never sees it: the
assertion walks `theme-N.css` only, and `fonts.css` contains neither a selector
nor a `url()` that leaves the repo.

THE SUBSET. Only `latin` is shipped, and that is not a shortcut: the `latin`
subset is `U+0000-00FF` (plus punctuation), which is exactly where Portuguese
lives — `ã` U+00E3, `õ` U+00F5, `ç` U+00E7, `á` U+00E1, `é` U+00E9. Latin-ext
would add nothing the panel can display.

THE WEIGHTS. Only the weights the five themes actually set (400/500/600/700) are
copied, which is what keeps this at ~239 KB instead of the ~7 MB of the five
whole packages. The packages themselves are NOT vendored: this script reads them
from `app/panel/_fonts/node_modules` (an install scratch directory, removed from
the panel's runtime path) and copies out the bytes.

Run: `py -3 _main/_design-lane/build_fonts.py`
"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir, 'app', 'panel'))
FONTS_OUT = os.path.join(PANEL, 'fonts')
CSS_OUT = os.path.join(PANEL, 'themes', 'fonts.css')
SIDE = os.path.join(PANEL, '_fonts', 'node_modules', '@fontsource')

# family -> (package directory, the weights the five themes set)
#
# BARLOW CONDENSED CARRIES 400 AS WELL AS 700, and that second weight is a
# correction (2026-10-07, lane painel-cinco-direcoes). Theme 1 declares
# `--weight-caption: 700` for the forming line AND `--weight-closed: 400` for the
# settled history. With only the 700 file in the bundle, the history's
# `font-weight: 400` had no 400 face to match and the browser picked the 700 one
# (CSS font matching takes the nearest available face) — so the "history recedes"
# half of the Teleprompter direction was being carried by SIZE and HUE alone,
# with the settled column painting the same heavy strokes as the live line. The
# `400` file is 21 164 B; there is no reason to approximate a weight that is
# already vendored.
FAMILIES = [
    ('Barlow Condensed', 'barlow-condensed', (400, 700)),
    ('IBM Plex Mono',    'ibm-plex-mono',    (400, 500, 600, 700)),
    ('Newsreader',       'newsreader',       (400, 600)),
    ('Fraunces',         'fraunces',         (400, 500, 600)),
    ('Space Grotesk',    'space-grotesk',    (400, 500, 700)),
]

SUBSET = 'latin'


def source_file(pkg, weight):
    """The vendored `.woff2` for one family/weight, whatever its naming scheme.

    @fontsource is not consistent: most packages name the file
    `<pkg>-<subset>-<weight>-normal.woff2`, but this run of `ibm-plex-mono`
    shipped them as `<pkg>-<subset>-<weight>-normal.woff2` for SOME subsets and
    not others. So the name is searched, never assumed, and a miss is a LOUD
    failure instead of a silently missing font.
    """
    files = os.path.join(SIDE, pkg, 'files')
    if not os.path.isdir(files):
        return None
    want = '-%s-%d-normal.woff2' % (SUBSET, weight)
    hits = [f for f in os.listdir(files) if f.endswith(want)]
    if not hits:
        return None
    hits.sort()
    return os.path.join(files, hits[0])


def unicode_range(pkg):
    path = os.path.join(SIDE, pkg, 'unicode.json')
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)[SUBSET]


def main():
    if not os.path.isdir(SIDE):
        print('MISSING: %s — install the packs first:\n'
              '  cd app/panel/_fonts && npm install @fontsource/barlow-condensed '
              '@fontsource/ibm-plex-mono @fontsource/newsreader '
              '@fontsource/fraunces @fontsource/space-grotesk' % SIDE,
              file=sys.stderr)
        return 2

    os.makedirs(FONTS_OUT, exist_ok=True)
    os.makedirs(os.path.dirname(CSS_OUT), exist_ok=True)

    missing = []
    blocks = []
    total = 0
    for family, pkg, weights in FAMILIES:
        rng = unicode_range(pkg)
        for weight in weights:
            src = source_file(pkg, weight)
            if not src:
                missing.append('%s %d' % (family, weight))
                continue
            name = '%s-%s-%d-normal.woff2' % (pkg, SUBSET, weight)
            dst = os.path.join(FONTS_OUT, name)
            shutil.copyfile(src, dst)
            size = os.path.getsize(dst)
            total += size
            blocks.append(
                "/* %s %d — %s, %d B */\n"
                '@font-face {\n'
                "  font-family: '%s';\n"
                '  font-style: normal;\n'
                '  font-weight: %d;\n'
                '  font-display: swap;\n'
                '  src: url(../fonts/%s) format(\'woff2\');\n'
                '  unicode-range: %s;\n'
                '}\n' % (family, weight, pkg, size, family, weight, name, rng))

    if missing:
        print('MISSING font files: %s' % ', '.join(missing), file=sys.stderr)
        return 1

    header = (
        '/* Sotto — THE BUNDLED TYPEFACES OF THE FIVE DESIGN DIRECTIONS.\n'
        ' *\n'
        ' * GENERATED by `_main/_design-lane/build_fonts.py`. Do not hand-edit.\n'
        ' *\n'
        ' * Linked by `panel.html` BEFORE `panel.css`, once for ALL five themes:\n'
        ' * an `@font-face` has no selector, paints nothing and declares no colour,\n'
        ' * so it cannot collide with a theme. Each theme then NAMES one of these\n'
        ' * families in its `--font-sans` / `--font-mono` token.\n'
        ' *\n'
        ' * latin only (U+0000-00FF): that is where Portuguese lives — a, o, c with\n'
        ' * tilde/cedilla are all below U+0100. The files are the latin `.woff2`\n'
        ' * subsets of the @fontsource packages, %d in all, %.1f KB on disk.\n'
        ' *\n'
        ' * LICENCES (all redistributable, all require attribution — see\n'
        ' * `fonts/LICENSE-NOTES.md`): Barlow Condensed, Newsreader, Fraunces and\n'
        ' * Space Grotesk are SIL OFL 1.1; IBM Plex Mono is SIL OFL 1.1 as well.\n'
        ' */\n\n' % (len(blocks), total / 1024.0))

    with open(CSS_OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(header + '\n'.join(blocks))

    for family, pkg, weights in FAMILIES:
        print('%-18s %s' % (family, ' '.join(str(w) for w in weights)))
    print('wrote %d @font-face block(s) -> %s' % (len(blocks), CSS_OUT))
    print('copied %d file(s), %.1f KB -> %s' % (len(blocks), total / 1024.0, FONTS_OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
