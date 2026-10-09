"""Read `src/themes.ts` for the FACTS the freeze needs, one row per design.

This is deliberately a parser and not an inventory summary: the ids, the display numbers,
the names, the fonts and the wallpaper ids all come out of the vendor's own source file.
The wallpaper URL is the one `px()` builds, because that is what the built bundle carries.

Usage:  py -3 _main/_skin-lane/collect-walls.py [--download]
"""
import io
import json
import os
import re
import subprocess
import sys

ZIP = r'H:\sotto\_main\_design-lane\zips\cinematic-2'
SRC = os.path.join(ZIP, 'src', 'themes.ts')
OUT_DIR = r'H:\sotto\app\panel\skins\cinematic-2'
WALL_DIR = os.path.join(OUT_DIR, 'img')
JSON_OUT = r'H:\sotto\_main\_skin-lane\walls.json'
BACKDROPS = r'H:\sotto\app\panel\themes\backdrops'

RECORD = re.compile(
    r'n:\s*"(\d+)"\s*,\s*'
    r'id:\s*"([a-z0-9-]+)"\s*,\s*'
    r'name:\s*"([^"]+)"\s*,\s*'
    r'mood:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
    r'scene:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
    r'sceneNote:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
    r'wall:\s*px\(\s*"(\d+)"(?:\s*,\s*"([a-z]+)")?\s*\)',
    re.S)


def main(argv):
    with io.open(SRC, encoding='utf-8') as fh:
        src = fh.read()

    rows = []
    for m in RECORD.finditer(src):
        n, did, name, mood, scene, note, photo, ext = m.groups()
        ext = ext or 'jpeg'
        base = ('https://images.pexels.com/photos/%s/pexels-photo-%s.%s'
                '?auto=compress&cs=tinysrgb' % (photo, photo, ext))
        rows.append({
            'n': n, 'id': did, 'name': name, 'photo': photo, 'ext': ext,
            'wall_src': base + '&fit=crop&h=900&w=1600',
            'wall_local': 'img/%s.%s' % (photo, 'jpg' if ext == 'jpeg' else ext),
            'mood': mood, 'scene': scene, 'scene_note': note,
        })

    # Every design must appear exactly once: a parser that silently drops records would
    # otherwise "prove" a smaller freeze than the vendor ships.
    ids = [r['id'] for r in rows]
    print('designs parsed: %d  unique: %d' % (len(ids), len(set(ids))))
    expected = re.search(r'export const THEMES: Theme\[\] = \[', src)
    if not expected:
        sys.stderr.write('the THEMES array literal was not found — parse is untrustworthy\n')
        return 1
    if len(ids) != len(set(ids)):
        sys.stderr.write('DUPLICATE ids: %s\n' % [i for i in ids if ids.count(i) > 1])
        return 1

    # The FOUR BRANCHES each design selects, which is what decides its element tree
    # (analysis §4: the tree, not just the colours, changes per design). Read from the
    # same record, by splitting the array into record blocks rather than by one regex.
    byxid = {r['id']: r for r in rows}
    arr = src[src.index('export const THEMES: Theme[] = ['):]
    for block in re.split(r'\n  \{\n', arr)[1:]:
        mid = re.search(r'id:\s*"([a-z0-9-]+)"', block)
        if not mid or mid.group(1) not in byxid:
            continue
        r = byxid[mid.group(1)]
        cap = re.search(r'caption:\s*\{[^}]*?style:\s*"([a-z]+)"', block, re.S)
        pan = re.search(r'panel:\s*\{\s*style:\s*"([a-z]+)"', block, re.S)
        chr_ = re.search(r'chrome:\s*"([A-Za-z]+)"', block)
        par = re.search(r'particle:\s*"([a-z]+)"', block)
        r['branch'] = {
            'caption': cap.group(1) if cap else None,
            'panel': pan.group(1) if pan else None,
            'chrome': chr_.group(1) if chr_ else None,
            'particle': par.group(1) if par else None,
        }
    miss = [r['id'] for r in rows if not r.get('branch') or not all(r['branch'].values())]
    if miss:
        sys.stderr.write('REFUSING: no complete branch tuple for %s\n' % miss)
        return 1
    print('branch tuples: all %d read' % len(rows))
    combos = {}
    for r in rows:
        key = tuple(r['branch'][k] for k in ('caption', 'panel', 'chrome', 'particle'))
        combos.setdefault(key, []).append(r['id'])
    print('distinct (caption,panel,chrome,particle) tuples: %d' % len(combos))
    for key, who in sorted(combos.items()):
        print('   %-34s %s' % ('/'.join(key), ', '.join(who) if len(who) < 5 else '%d designs' % len(who)))

    # The fonts each design asks for, so a missing bundled face is a REPORTED fact
    # rather than a silent fallback at paint time.
    families = set()
    for m in re.finditer(r'fonts:\s*\{([^}]*)\}', src):
        # The values are `ui: '"Manrope", sans-serif'` — a single-quoted TS string whose
        # FIRST character is a double quote, so looking for `: "` finds nothing at all.
        for f in re.findall(r"""(?:ui|display|caption):\s*(?:"([^"]+)"|'([^']+)')""",
                            m.group(1)):
            families.add(f[0] or f[1])
    primary = {}
    for stack in families:
        first = stack.split(',')[0].strip().strip('"\'')
        primary[first] = primary.get(first, 0) + 1
    print('font families named by the designs: %d' % len(primary))
    for fam, count in sorted(primary.items()):
        print('   %-24s %d design(s)' % (fam, count))

    with io.open(JSON_OUT, 'w', encoding='utf-8', newline='') as fh:
        fh.write(json.dumps(rows, indent=1, ensure_ascii=False))
    print('wrote %s (%d bytes)' % (JSON_OUT, os.path.getsize(JSON_OUT)))

    if '--download' in argv:
        os.makedirs(WALL_DIR, exist_ok=True)
        ok = bad = skipped = 0
        for r in rows:
            dest = os.path.join(OUT_DIR, r['wall_local'].replace('/', os.sep))
            if os.path.isfile(dest) and os.path.getsize(dest) > 8192:
                skipped += 1
                continue
            # Python's TLS stack cannot verify these hosts on this box (measured: the
            # certificate chain fails), so the download goes through curl.exe.
            p = subprocess.run(['curl.exe', '-sSL', '--fail', '--max-time', '30',
                                '-o', dest, r['wall_src']],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            good = False
            if p.returncode == 0 and os.path.isfile(dest):
                with io.open(dest, 'rb') as fh:
                    magic = fh.read(8)
                # NOT every Pexels photo is a JPEG: `glasshouse` resolves to a .png
                # (`pexels-photo-38663879.png`, 2 557 215 B). A JPEG-only magic test
                # reported that design as a FAILED download while the bytes on disk were
                # a perfectly valid image — a check that was wrong about the world.
                good = (magic[:3] == b'\xff\xd8\xff' or magic[:8] == b'\x89PNG\r\n\x1a\n') \
                    and os.path.getsize(dest) > 8192
            if good:
                ok += 1
                print('  OK   %-16s %8d B  %s' % (r['id'], os.path.getsize(dest),
                                                  os.path.basename(dest)))
            else:
                bad += 1
                print('  FAIL %-16s rc=%s %s' % (r['id'], p.returncode,
                                                 p.stderr.decode('utf-8', 'replace')[:90]))
        print('walls: ok=%d skipped=%d FAILED=%d' % (ok, skipped, bad))

        # Cross-check against the photos the PREVIOUS lane downloaded for the six designs
        # it themed. It reached the same Pexels ids from the same source file, so a
        # byte-identical file is independent evidence that this URL->design mapping is
        # right; a size match with a different hash would mean one of the two is wrong.
        import hashlib
        theirs = {}
        if os.path.isdir(BACKDROPS):
            for name in os.listdir(BACKDROPS):
                if name.lower().endswith('.jpg'):
                    p = os.path.join(BACKDROPS, name)
                    with io.open(p, 'rb') as fh:
                        theirs[hashlib.sha256(fh.read()).hexdigest()] = name
        same = diff = 0
        for r in rows:
            p = os.path.join(OUT_DIR, r['wall_local'].replace('/', os.sep))
            if not os.path.isfile(p):
                continue
            with io.open(p, 'rb') as fh:
                h = hashlib.sha256(fh.read()).hexdigest()
            if h in theirs:
                same += 1
                print('  CROSS-CHECK identical to backdrops/%s  (%s)'
                      % (theirs[h], r['id']))
            else:
                diff += 1
        print('cross-check: %d of %d wallpapers are byte-identical to a backdrops/ file'
              % (same, same + diff))
        if bad:
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
