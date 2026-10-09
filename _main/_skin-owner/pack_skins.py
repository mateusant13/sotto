"""Pack the freeze lane's artifacts into the ONE script the panel loads.

WHAT IT READS (owned by the freeze lane, `_main/_skin-lane/`)
    app/panel/skins/<zip>/index.json          designs, per-design CSS variables, bindings
    app/panel/skins/<zip>/<design>.stage.html   the mockup's own markup, frozen, one fragment each
    app/panel/skins/<zip>/<design>.chrome.html
    app/panel/skins/<zip>/<design>.caption.html
    app/panel/skins/<zip>/<design>.panel.html
    app/panel/skins/<zip>/app.css             the mockup's own compiled CSS, `html/body/#root` rewritten

WHAT IT WRITES
    app/panel/skins/skins.js   `window.SOTTO_SKINS` + `window.SOTTO_SKIN_HTML`

WHY A SCRIPT AND NOT JSON: the panel is a `file://` document and `fetch()` of a
`file://` URL is refused by Chromium (the same reason `themes/themes.js` is a
script). It is loaded right after `themes/themes.js`, because it also APPENDS the
designs our theme manifest does not carry yet: the freeze lane froze all twenty
designs of the newest zip and the previous lane had shipped six of them, and the
owner asked for *"cada painel dos .zip"*, not for a sixth of them.

THE MUTE LIST. A mockup's chrome is full of numbers it invented — a confidence, a
word rate, a speaker count, a fake clock, eleven fake speaker names. This panel
measures none of them, so they are not translated into ours and not printed: the
host blanks those leaves (the design keeps the slot, the design loses the fiction)
and rewrites the mockup's product name to `sotto`. The vocabulary comes from the
mockup's own `src/lib/scripts.ts`, read here, so it cannot drift from the words the
frozen markup actually contains.
"""
import io
import json
import os
import re

PANEL = r'H:\sotto\app\panel'
SKINS = os.path.join(PANEL, 'skins')
ZIPS = r'H:\sotto\_main\_design-lane\zips'
OUT = os.path.join(SKINS, 'skins.js')
MANIFEST = os.path.join(PANEL, 'themes', 'themes.js')

#: Extra words the mockup prints that are not in its script data: session labels,
#: the product's own name, the note words under the caption plate.
EXTRA_MUTE = [
    'Mumble', 'Late Shift Radio', 'late-radio', 'studio condenser · 48 kHz',
    'last line', 'transcribing', 'on-device · 240 ms', 'live track',
    'This afternoon', 'Late morning', 'Tonight', 'Earlier', 'Yesterday',
    'Transcript history', 'Hide', 'Export .txt', 'Follow on', 'Clear',
    'Search this transcript…', 'everyone', 'in progress',
]

#: THE MOCKUP'S NUMBERS. Every one of these is a figure the mockup invented about a
#: simulated room; this panel measures none of them, so none of them is printed. The
#: patterns are anchored and narrow on purpose: the host applies them to a LEAF whose
#: WHOLE text matches, so a design's own label ("12") cannot be caught by accident.
MUTE_PATTERNS = [
    r'^\d+%$',
    r'^\d+\s*wpm$',
    r'^\d+\s*lines?$',
    r'^\d+\s*speakers?$',
    r'^\d+:\d{2}$',
    r'^\d{2}:\d{2}:\d{2}$',
    r'^\d+\s*ms$',
    r'^transcribing\b.*$',
    r'^on-device\b.*$',
    r'^conf\b.*$',
    r'^last line$',
    r'^\d{2}\s*·.*$',
]


def read(path):
    with io.open(path, 'r', encoding='utf-8', errors='replace') as handle:
        return handle.read()


def design_names(zip_name):
    """`{id: 'Human Name'}` straight out of the mockup's own theme table."""
    path = os.path.join(ZIPS, zip_name, 'src', 'themes.ts')
    if not os.path.exists(path):
        return {}
    text = read(path)
    ids = re.findall(r"id:\s*'([^']+)'", text)
    names = re.findall(r"name:\s*'([^']+)'", text)
    return dict(zip(ids, names))


def mock_vocabulary(zip_name):
    """Every human-readable string the mockup's script plays, plus the extras."""
    words = set(w.lower() for w in EXTRA_MUTE)
    for rel in (('src', 'lib', 'scripts.ts'), ('src', 'data', 'scenes.ts')):
        path = os.path.join(ZIPS, zip_name, *rel)
        if not os.path.exists(path):
            continue
        text = read(path)
        # Quoted and backticked literals; sentences are long, so keep them all and
        # let the host match on the LEAF's whole text, never on a substring.
        for pattern in (r'"([^"\\\n]{3,80})"', r"'([^'\\\n]{3,80})'", r'`([^`\\\n]{3,80})`'):
            for value in re.findall(pattern, text):
                words.add(value.strip().lower())
        # AND THE SPEAKER TABLE'S OWN KEYS, which are UNQUOTED in the mockup's
        # TypeScript (`June: {...}`). The first version of this function only read
        # quoted literals, so the speaker names survived into the frozen panel and
        # the render instrument caught one on screen ("SOFIA", a filter chip).
        for value in re.findall(r'(?m)^\s*([A-Z][A-Za-z]{2,20}):\s*\{', text):
            words.add(value.strip().lower())
        # AND THE SHORT FORM of a name the mockup stores with a qualifier:
        # `"Sofia (caller)"` is printed as `Sofia` by the mockup's own `short()`,
        # which is the string that must be muted — the exact-match rule could never
        # see it, and the render instrument found it on screen.
        for value in re.findall(r'"([A-Z][A-Za-z]{2,20}) \([^"]*\)"', text):
            words.add(value.strip().lower())
    return sorted(w for w in words if w)


def pack(zip_name):
    root = os.path.join(SKINS, zip_name)
    index = json.loads(read(os.path.join(root, 'index.json')))
    names = design_names(zip_name)
    designs = index.get('frozen') or list((index.get('vars') or {}).keys())
    themes = {}
    fragments = {}
    missing = []
    for design in designs:
        wanted = {}
        for kind in ('stage', 'chrome', 'caption', 'panel'):
            path = os.path.join(root, '%s.%s.html' % (design, kind))
            if not os.path.exists(path):
                missing.append('%s.%s' % (design, kind))
                continue
            wanted[kind] = read(path)
        if 'caption' not in wanted and 'panel' not in wanted:
            missing.append('%s(no-caption-no-panel)' % design)
            continue
        variables = (index.get('vars') or {}).get(design) or {}
        label = names.get(design) or design.replace('-', ' ').title()
        theme_id = 'cine-' + design
        themes[theme_id] = {
            'zip': zip_name,
            'design': design,
            'name': label,
            'label': label,
            'swatch': variables.get('--accent') or '',
            'vars': variables,
            'bindings': (index.get('bindings') or {}).get(design) or {},
        }
        fragments['%s/%s' % (zip_name, design)] = wanted
    return themes, fragments, missing


def manifest_names():
    text = read(MANIFEST)
    return set(re.findall(r"name:\s*'([^']+)'", text))


def js_object(value):
    """JSON is a subset of JS object literals here: no functions, no undefined."""
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def main():
    zips = {}
    themes = {}
    fragments = {}
    notes = []
    for zip_name in sorted(os.listdir(SKINS)):
        root = os.path.join(SKINS, zip_name)
        if not os.path.isdir(root) or not os.path.exists(os.path.join(root, 'index.json')):
            continue
        packed_themes, packed_fragments, missing = pack(zip_name)
        if not packed_themes:
            notes.append('%s: NOTHING PACKED' % zip_name)
            continue
        zips[zip_name] = {
            'css': 'skins/%s/app.css' % zip_name,
            'viewport': [380, 900],
            'mute': mock_vocabulary(zip_name),
            'mutePatterns': MUTE_PATTERNS,
            'brandFrom': 'Mumble',
            'brandTo': 'sotto',
        }
        themes.update(packed_themes)
        fragments.update(packed_fragments)
        notes.append('%s: %d design(s) packed, %d fragment(s) missing'
                     % (zip_name, len(packed_themes), len(missing)))
        if missing:
            notes.append('   missing: %s' % ', '.join(sorted(set(missing))))

    have = manifest_names()
    fresh = []
    for theme_id, entry in sorted(themes.items()):
        if theme_id not in have:
            fresh.append({
                'name': theme_id,
                'label': entry['label'],
                'file': None,
                'swatch': entry['swatch'] or '#8fa0aa',
                'skin': entry['zip'] + '/' + entry['design'],
            })
    for entry in fresh:
        have.add(entry['name'])

    header = (
        '/* GENERATED by _main/_skin-owner/pack_skins.py — do not hand-edit.\n'
        ' *\n'
        ' * The frozen-skin manifest. Loaded right after `themes/themes.js` because it\n'
        ' * APPENDS the designs our theme manifest does not carry yet: %d of %d packed\n'
        ' * theme(s) were already in it. See the generator for what a skin is and why the\n'
        ' * mockup\'s invented numbers are muted rather than translated.\n'
        ' */\n' % (len(themes) - len(fresh), len(themes))
    )
    body = []
    body.append('window.SOTTO_SKINS = {version:1,zips:%s,themes:%s};'
                % (js_object(zips), js_object(themes)))
    body.append('window.SOTTO_SKIN_HTML = %s;' % js_object(fragments))
    if fresh:
        body.append(
            '/* THE DESIGNS THE MANIFEST DID NOT HAVE. Appended here, before\n'
            ' * `theme-switcher.js` loads, so the picker lists them like any other theme.\n'
            ' * They carry no `themes/*.css` of their own: their whole look is the skin. */\n'
            '(function () {\n'
            '  var manifest = window.SottoThemeManifest;\n'
            '  if (!manifest || !manifest.themes) return;\n'
            '  var extra = %s;\n'
            '  for (var i = 0; i < extra.length; i += 1) manifest.themes.push(extra[i]);\n'
            '}());\n' % js_object(fresh))
    text = header + '\n'.join(body) + '\n'
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)

    print('skins.js  %d B' % len(text.encode('utf-8')))
    print('themes    %d packed, %d appended to the manifest' % (len(themes), len(fresh)))
    print('fragments %d design(s)' % len(fragments))
    for note in notes:
        print('  ' + note)
    big = sorted(((len(json.dumps(v, ensure_ascii=False)), k) for k, v in fragments.items()),
                 reverse=True)[:3]
    for size, key in big:
        print('  largest fragment set: %s (%d B)' % (key, size))


if __name__ == '__main__':
    main()
