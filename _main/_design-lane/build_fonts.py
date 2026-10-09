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
    # (family, @fontsource package, normal weights, italic weights)
    #
    # EXTENDED 2026-10-08 (the owner's own instruction): *"eu gostei de todas as
    # fontes, entao inclua toda as fontes"*. The three `cinematic` design zips he
    # added name SIXTEEN families between them, so all sixteen are bundled and the
    # old five are a subset of this list. Weights are still only the ones a design
    # actually asks for, which is what keeps this at ~1.1 MB instead of the ~40 MB
    # of the sixteen whole packages; the packages are read from
    # `app/panel/_fonts/node_modules` and never vendored.
    #
    # THE ITALIC COLUMN IS NOT DECORATION. The designs italicise their reading
    # faces — a quote in a history panel, a serif caption drifting like a title
    # card (`cinematic-2` "Night Swim") — and with no italic face bundled the
    # browser SYNTHESISES an oblique, which is a sheared upright: measurably
    # different letterforms, and exactly the kind of "close enough" that makes a
    # design look wrong without anyone being able to say why. `()` means the
    # family has no italic in this bundle because no design asks for one.
    ('Barlow Condensed',    'barlow-condensed',    (400, 500, 600, 700), ()),
    ('IBM Plex Mono',       'ibm-plex-mono',       (400, 500, 600),      (400,)),
    ('Newsreader',          'newsreader',          (400, 500, 600),      (400, 500)),
    ('Fraunces',            'fraunces',            (400, 500, 600),      (400, 500)),
    ('Space Grotesk',       'space-grotesk',       (400, 500, 600, 700), ()),
    ('Inter',               'inter',               (300, 400, 500, 600), ()),
    ('Instrument Serif',    'instrument-serif',    (400,),               (400,)),
    ('Instrument Sans',     'instrument-sans',     (400, 500, 600),      (400,)),
    ('Lora',                'lora',                (400, 500, 600),      (400, 500)),
    ('Cormorant Garamond',  'cormorant-garamond',  (300, 400, 500),      (300, 400)),
    ('DM Mono',             'dm-mono',             (300, 400, 500),      (400,)),
    ('JetBrains Mono',      'jetbrains-mono',      (300, 400, 500),      ()),
    ('Bricolage Grotesque', 'bricolage-grotesque', (300, 400, 500, 600, 700, 800), ()),
    ('Jost',                'jost',                (300, 400, 500),      ()),
    ('Manrope',             'manrope',             (300, 400, 500, 600), ()),
    ('Outfit',              'outfit',              (300, 400, 500, 600), ()),
]

SUBSET = 'latin'


def source_file(pkg, weight, style='normal'):
    """The vendored `.woff2` for one family/weight/style, whatever its naming scheme.

    @fontsource is not consistent: most packages name the file
    `<pkg>-<subset>-<weight>-normal.woff2`, but this run of `ibm-plex-mono`
    shipped them as `<pkg>-<subset>-<weight>-normal.woff2` for SOME subsets and
    not others. So the name is searched, never assumed, and a miss is a LOUD
    failure instead of a silently missing font.
    """
    files = os.path.join(SIDE, pkg, 'files')
    if not os.path.isdir(files):
        return None
    want = '-%s-%d-%s.woff2' % (SUBSET, weight, style)
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
        hint = ('  cd app/panel/_fonts && npm install '
                + ' '.join('@fontsource/' + pkg for _, pkg, _, _ in FAMILIES)
                + ' --no-audit --no-fund')
        print('MISSING: %s \u2014 install the packs first:\n%s' % (SIDE, hint),
              file=sys.stderr)
        return 2

    os.makedirs(FONTS_OUT, exist_ok=True)
    os.makedirs(os.path.dirname(CSS_OUT), exist_ok=True)

    missing = []
    blocks = []
    total = 0
    for family, pkg, weights, italics in FAMILIES:
        rng = unicode_range(pkg)
        # One face per (weight, style): `normal` always, `italic` only where a
        # design asks for it. The family's `unicode-range` is read once and is
        # the same for every face of that family.
        faces = [(w, 'normal') for w in weights] + [(w, 'italic') for w in italics]
        for weight, style in faces:
            src = source_file(pkg, weight, style)
            if not src:
                missing.append('%s %d %s' % (family, weight, style))
                continue
            name = '%s-%s-%d-%s.woff2' % (pkg, SUBSET, weight, style)
            dst = os.path.join(FONTS_OUT, name)
            shutil.copyfile(src, dst)
            size = os.path.getsize(dst)
            total += size
            blocks.append(
                "/* %s %d %s \u2014 %s, %d B */\n"
                '@font-face {\n'
                "  font-family: '%s';\n"
                '  font-style: %s;\n'
                '  font-weight: %d;\n'
                '  font-display: swap;\n'
                "  src: url(../fonts/%s) format('woff2');\n"
                '  unicode-range: %s;\n'
                '}\n' % (family, weight, style, pkg, size, family, style, weight,
                          name, rng))

    if missing:
        print('MISSING font files: %s' % ', '.join(missing), file=sys.stderr)
        return 1

    header = (
        '/* Sotto \u2014 THE BUNDLED TYPEFACES OF THE DESIGN DIRECTIONS AND OF THE\n'
        ' * `cinematic` TEMPLATE SET.\n'
        ' *\n'
        ' * GENERATED by `_main/_design-lane/build_fonts.py`. Do not hand-edit.\n'
        ' *\n'
        ' * Linked by `panel.html` BEFORE `panel.css`, once for EVERY theme: an\n'
        ' * `@font-face` has no selector, paints nothing and declares no colour, so\n'
        ' * it cannot collide with a theme. Each theme then NAMES one of these\n'
        ' * families in its `--font-sans` / `--font-mono` token.\n'
        ' *\n'
        ' * THE OWNER ASKED FOR ALL OF THEM, verbatim (2026-10-08): *"eu gostei de\n'
        ' * todas as fontes, entao inclua toda as fontes"* \u2014 the sixteen families\n'
        ' * the design zips name. %d faces, %.1f KB, latin only (U+0000-00FF): that\n'
        ' * is where Portuguese lives, a/o/c with tilde/cedilla all below U+0100.\n'
        ' * Weight AND italic are bundled only where a design asks for them, which\n'
        ' * is what keeps this near 1 MB instead of the sixteen whole packages.\n'
        ' *\n'
        ' * LICENCES (all redistributable, all require attribution \u2014 see\n'
        ' * `fonts/LICENSE-NOTES.md`): all sixteen families are SIL OFL 1.1.\n'
        ' */\n\n' % (len(blocks), total / 1024.0))

    with open(CSS_OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(header + '\n'.join(blocks))

    for family, pkg, weights, italics in FAMILIES:
        print('%-20s normal=[%s] italic=[%s]'
              % (family, ' '.join(str(w) for w in weights),
                 ' '.join(str(w) for w in italics)))
    print('wrote %d @font-face block(s) -> %s' % (len(blocks), CSS_OUT))
    print('copied %d file(s), %.1f KB -> %s' % (len(blocks), total / 1024.0, FONTS_OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
