"""Convert the panel's woff2 faces to TTF for the NATIVE caption overlay.

WHY THIS EXISTS. The live caption the owner sees is GDI+, not CSS; GDI+ cannot
open woff2. The panel's type is webfont-only, so without this converter the
overlay either falls back to Segoe UI (every design looks the same) or, worse,
uses a broken Windows-installed copy -- MEASURED 2026-10-21: the installed
`IBM Plex Mono` regular face on this box draws OBLIQUE, while the panel's
`ibm-plex-mono-latin-400-normal.woff2` draws upright. Same family name, two
different faces.

The conversion is a BUILD STEP, not a runtime one: `app/webview/fonts/` holds
the TTFs plus `manifest.json`, and `caption_overlay._make_font` resolves the
family/weight/italic through it. Re-run after adding a face to
`app/panel/fonts/`.

    python _main/_design-lane/make-overlay-fonts.py [--check]

`--check` reports what would change and exits 1 if the shipped TTFs are stale,
so a gate can hold it.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'app', 'panel', 'fonts')
DST = os.path.join(ROOT, 'app', 'webview', 'fonts')
MANIFEST = os.path.join(DST, 'manifest.json')
PATTERN = re.compile(r'^(?P<slug>.+)-latin-(?P<weight>\d{3})-(?P<style>normal|italic)\.woff2$')


def read_family(path):
    """The CSS family for one woff2, from `themes/fonts.css` -- not the name table.

    THE SUBSET'S OWN NAME LIES. MEASURED 2026-10-21: the 500 face of Barlow
    Condensed calls itself `Barlow Condensed Medium`, and a 600 Bricolage face
    calls itself `Bricolage Grotesque 96pt ExtraBold SemiBold`. The panel still
    uses ONE family name (`--font-sans: "Barlow Condensed"`), so the overlay has
    to resolve the file by the name the CSS uses. `fonts.css` is the generated
    declaration and is the only source that says it.
    """
    css = os.path.join(ROOT, 'app', 'panel', 'themes', 'fonts.css')
    global _FAMILY_BY_FILE
    try:
        _FAMILY_BY_FILE
    except NameError:
        _FAMILY_BY_FILE = {}
        text = open(css, encoding='utf-8').read()
        for m in re.finditer(
                r"font-family:\s*'([^']+)';.*?src:\s*url\([^)]*?/([^/)]+\.woff2)\)",
                text, re.S):
            _FAMILY_BY_FILE[m.group(2)] = m.group(1)
    family = _FAMILY_BY_FILE.get(os.path.basename(path))
    if family:
        return family
    from fontTools.ttLib import TTFont
    font = TTFont(path)
    try:
        name = font['name'].getDebugName(16) or font['name'].getDebugName(1) or ''
    finally:
        font.close()
    return name.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    os.makedirs(DST, exist_ok=True)
    manifest = {'families': {}}
    changed = []
    missing = []
    for name in sorted(os.listdir(SRC)):
        m = PATTERN.match(name)
        if not m:
            continue
        source = os.path.join(SRC, name)
        target_name = name[:-len('.woff2')] + '.ttf'
        target = os.path.join(DST, target_name)
        family = read_family(source)
        weight = int(m.group('weight'))
        italic = m.group('style') == 'italic'
        manifest['families'].setdefault(family, []).append({
            'weight': weight,
            'italic': italic,
            'file': target_name,
            'slug': m.group('slug'),
        })
        stale = (not os.path.exists(target)
                 or os.path.getmtime(target) < os.path.getmtime(source))
        if stale:
            changed.append(target_name)
            if not args.check:
                from fontTools.ttLib import TTFont
                font = TTFont(source)
                font.flavor = None
                font.save(target)
                font.close()
        if not os.path.exists(target):
            missing.append(target_name)

    for family in manifest['families']:
        manifest['families'][family].sort(
            key=lambda e: (e['weight'], e['italic']))
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'
    old = None
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding='utf-8') as fh:
            old = fh.read()
    if old != text:
        changed.append('manifest.json')
        if not args.check:
            with open(MANIFEST, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)

    print('woff2 -> ttf: %d face(s), %d famil(ies), %d changed'
          % (sum(len(v) for v in manifest['families'].values()),
             len(manifest['families']), len(changed)))
    for c in changed[:24]:
        print('  %s %s' % ('STALE' if args.check else 'wrote', c))
    if args.check and changed:
        print('OVERLAY-FONTS STALE: %d file(s) need rebuilding' % len(changed))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
