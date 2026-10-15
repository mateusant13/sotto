#!/usr/bin/env python3
"""theme-lightness-census -- THE PROOF THAT NO THEME SHIPS A WHITE PANEL.

WHY IT EXISTS. The owner's order of 2026-10-14, verbatim: *"e nao e pra ter tema
branco."* Before anything is changed, the question has to be answered with a NUMBER
per theme and not with an impression, because "there is no white theme" is exactly the
kind of claim that is true for 39 of 45 themes and false for six -- and the six are
the ones the owner actually switches to.

WHAT IT MEASURES, per theme, over the SHIPPED bytes:

  1. the theme's own token block (:root[data-theme='X']{...}) -- --bg-slab,
     --bg-slab-strong, --cine-scrim, and the three ink tokens;
  2. the theme's own .panel rule -- its background / background-color /
     background-image, INCLUDING the backdrop photograph and the scrim gradients
     painted on top of it, because a cine-* theme's panel is a PHOTOGRAPH graded
     by its own scrim and the photograph is most of what the eye sees;
  3. the COMPOSITED background colour (every layer in CSS order, first layer on top,
     over the shell's own opaque form colour when a layer is translucent);
  4. the WCAG 2.x relative luminance of that colour, and the contrast ratio of the
     theme's own caption ink, body ink and dim ink against it.

WHAT IT DOES NOT DO. It does not launch anything: no browser, no shell, no worker, no
WebView2. It reads bytes and decodes the bundled JPEGs with Pillow, offline. The
photograph measurement is the MEAN RGB of the file, which is a summary and not a
per-pixel map; a theme whose wallpaper is half white and half black is reported as
mid-grey here, and that limitation is stated rather than hidden.

THE THRESHOLD is 0.5 relative luminance -- the midpoint of the scale, and the SAME
threshold gen_cinematic.py panel_is_light() already uses to decide color-scheme
in the generated block. A census that used a different line from the generator would
disagree with the thing it measures for no reason.

USAGE
  py -3 _main/theme-lightness-census.py            the census, 45 rows, rc=0
  py -3 _main/theme-lightness-census.py --light    the light ones only, rc=0
  py -3 _main/theme-lightness-census.py --gate     rc=1 if ANY theme is light
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
PANEL = os.path.join(ROOT, 'app', 'panel')
THEMES = os.path.join(PANEL, 'themes')

# The shell paints the unpainted window with its own form colour; a translucent
# layer is composited over it, never over nothing.
# MEASURED 2026-10-06 and quoted all over AGENTS.md: rgba(11, 15, 20, 0.98).
FORM_RGB = (11, 15, 20)
FORM_ALPHA = 0.98

# The same threshold gen_cinematic.py:panel_is_light() uses.
LIGHT = 0.5

PHOTO_CACHE = {}


def parse_color(value):
    """#rgb, #rrggbb, rgb(), rgba() -> (r, g, b, a) or None."""
    if value is None:
        return None
    v = value.strip()
    m = re.fullmatch(r'#([0-9a-fA-F]{3})', v)
    if m:
        h = m.group(1)
        return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 1.0)
    m = re.fullmatch(r'#([0-9a-fA-F]{6})', v)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r'rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)'
                     r'(?:[\s,/]+([\d.]+%?))?\)', v)
    if m:
        a = m.group(4)
        if a is None:
            a = 1.0
        elif a.endswith('%'):
            a = float(a[:-1]) / 100.0
        else:
            a = float(a)
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)), a)
    return None


def over(fg, bg):
    """Composite fg over bg; both (r, g, b, a). Result is opaque."""
    a = fg[3]
    return (fg[0] * a + bg[0] * (1 - a),
            fg[1] * a + bg[1] * (1 - a),
            fg[2] * a + bg[2] * (1 - a),
            1.0)


def mix(a, b, pct):
    return (a[0] * pct + b[0] * (1 - pct),
            a[1] * pct + b[1] * (1 - pct),
            a[2] * pct + b[2] * (1 - pct),
            a[3] * pct + b[3] * (1 - pct))


def luminance(c):
    def f(x):
        x = x / 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hexs(c):
    return '#%02x%02x%02x' % tuple(int(round(x)) for x in c[:3])


def block_of(css, selector):
    """The body of 'selector { ... }', brace-matched, comments removed."""
    flat = re.sub(r'/\*[\s\S]*?\*/', '', css)
    for m in re.finditer(re.escape(selector) + r'\s*\{', flat):
        i = m.end()
        depth, start = 1, i
        while i < len(flat) and depth:
            if flat[i] == '{':
                depth += 1
            elif flat[i] == '}':
                depth -= 1
            i += 1
        return flat[start:i - 1]
    return None


def tokens_of(css, name):
    body = block_of(css, ":root[data-theme='%s']" % name)
    if body is None:
        return None
    out = {}
    for m in re.finditer(r'(--[\w-]+)\s*:\s*([^;]+);', body):
        out[m.group(1)] = m.group(2).strip()
    return out


def resolve(tokens, name, depth=0):
    if tokens is None or depth > 8:
        return None
    raw = tokens.get(name)
    if raw is None:
        return None
    v = raw.strip()
    m = re.fullmatch(r'var\((--[\w-]+)\)', v)
    if m:
        return resolve(tokens, m.group(1), depth + 1)
    m = re.fullmatch(r'color-mix\(\s*in\s+srgb\s*,\s*(.+?)\s+([\d.]+)%\s*,\s*(.+?)\s*\)', v)
    if m:
        a = resolve_value(tokens, m.group(1), depth + 1)
        b = resolve_value(tokens, m.group(3), depth + 1)
        if a and b:
            return mix(a, b, float(m.group(2)) / 100.0)
        return a or b
    return parse_color(v)


def resolve_value(tokens, text, depth=0):
    t = text.strip()
    m = re.fullmatch(r'var\((--[\w-]+)\)', t)
    if m:
        return resolve(tokens, m.group(1), depth + 1)
    c = parse_color(t)
    if c:
        return c
    if t == 'transparent':
        return (0, 0, 0, 0.0)
    return None


def photo_mean(path):
    """Mean RGB of a bundled backdrop photograph (offline decode)."""
    if path in PHOTO_CACHE:
        return PHOTO_CACHE[path]
    out = None
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert('RGB')
            small = im.resize((48, 27))
            px = list(small.getdata())
        n = float(len(px))
        out = tuple(sum(p[i] for p in px) / n for i in range(3)) + (1.0,)
    except Exception as exc:
        sys.stderr.write('photo not measured (%s): %s\n' % (os.path.basename(path), exc))
        out = None
    PHOTO_CACHE[path] = out
    return out


def gradient_stops(tokens, layer):
    """The average colour of one gradient layer, sampled across its stops."""
    stops = []
    for stop in re.finditer(r'(rgba?\([^)]*\)|#[0-9a-fA-F]{3,6}|var\(--[\w-]+\)|'
                            r'color-mix\([^)]*\)|transparent)\s*([\d.]+%)?', layer):
        col = resolve_value(tokens, stop.group(1))
        if col is None:
            continue
        stops.append(col)
    if not stops:
        return None
    n = len(stops)
    return tuple(sum(s[i] for s in stops) / n for i in range(4))


def split_layers(image):
    """Split a background-image layer list on top-level commas."""
    depth, cur, parts = 0, '', []
    for ch in image:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    parts.append(cur)
    return parts


def painted_background(css, tokens, name):
    """(colour, how) -- the composited .panel background of this theme."""
    body = block_of(css, ":root[data-theme='%s'] .panel" % name) or ''
    decls = dict(re.findall(r'(background(?:-color|-image)?)\s*:\s*([^;]+);', body))
    # LAYERS IN CSS ORDER: the FIRST is the TOP one. Getting this backwards paints
    # the photograph OVER its own scrim -- measured, that bug reported
    # cine-paper-moon as #5f6062 when the panel really paints #e6e7e4.
    layers = []
    how = []
    image = decls.get('background-image') or decls.get('background')
    if image:
        for part in split_layers(image):
            part = part.strip()
            m = re.search(r'url\(([^)]+)\)', part)
            if m:
                mean = photo_mean(os.path.join(THEMES, m.group(1)))
                if mean is not None:
                    layers.append(mean)
                    how.append('photo=%s mean #%02x%02x%02x'
                               % (os.path.basename(m.group(1)),
                                  int(mean[0]), int(mean[1]), int(mean[2])))
                continue
            if 'gradient(' in part:
                col = gradient_stops(tokens, part)
                if col is None:
                    continue
                layers.append(col)
                how.append('gradient mean #%02x%02x%02x a=%.2f'
                           % (int(col[0]), int(col[1]), int(col[2]), col[3]))
    # The BASE is background-color, and it paints UNDER every image layer.
    base = None
    for key in ('background-color', 'background'):
        if key in decls and 'gradient(' not in decls[key] and 'url(' not in decls[key]:
            base = resolve_value(tokens, decls[key])
            if base is not None:
                break
    if base is None:
        base = resolve(tokens, '--bg-slab') or (0, 0, 0, 0)
    how.insert(0, 'base #%02x%02x%02x a=%.2f'
                % (int(base[0]), int(base[1]), int(base[2]), base[3]))
    # Composite bottom-up: the shell form colour, the base, then every image layer
    # from the bottom-most to the top-most.
    colour = (FORM_RGB[0], FORM_RGB[1], FORM_RGB[2], FORM_ALPHA)
    colour = over(base, colour)
    for layer in reversed(layers):
        colour = over(layer, colour)
    return colour, '; '.join(how)


def registry():
    out = []
    manifest = io.open(os.path.join(THEMES, 'themes.js'), encoding='utf-8').read()
    for m in re.finditer(r"name:\s*'([^']+)',\s*\n\s*label:\s*'([^']+)',", manifest):
        n = m.group(1)
        out.append((n, m.group(2), 'themes/cinematic.css'
                    if n.startswith('cine-')
                    else 'themes/theme-%s.css' % n.split('-')[1]))
    for frag, css in (('panel-designs.js', 'themes/panel-designs.css'),
                      ('zipc-panels.js', 'themes/zipc-panels.css')):
        text = io.open(os.path.join(THEMES, frag), encoding='utf-8').read()
        for m in re.finditer(r"name:\s*'([^']+)',\s*\n\s*label:\s*'([^']+)',", text):
            out.append((m.group(1), m.group(2), css))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--light', action='store_true', help='the light themes only')
    ap.add_argument('--gate', action='store_true',
                    help='rc=1 when ANY theme measures light (the gate form)')
    args = ap.parse_args()

    rows = []
    for (name, label, css_file) in registry():
        path = os.path.join(PANEL, css_file)
        css = io.open(path, encoding='utf-8').read()
        tokens = tokens_of(css, name)
        if tokens is None:
            rows.append({'name': name, 'label': label, 'file': css_file,
                         'error': 'no token block'})
            continue
        colour, how = painted_background(css, tokens, name)
        ink = resolve(tokens, '--text-primary')
        dim = resolve(tokens, '--text-secondary')
        cap = resolve(tokens, '--text-confirmed') or ink
        rows.append({
            'name': name, 'label': label, 'file': css_file,
            'hex': hexs(colour), 'lum': luminance(colour),
            'light': luminance(colour) >= LIGHT,
            'ink_contrast': contrast(ink, colour) if ink else None,
            'dim_contrast': contrast(dim, colour) if dim else None,
            'caption_contrast': contrast(cap, colour) if cap else None,
            'how': how,
        })

    if args.light:
        rows = [r for r in rows if r.get('light')]

    print('%-22s %-22s %-26s %8s %7s  %-9s %-9s %s'
          % ('theme', 'label', 'painted background', 'lum', 'verdict',
             'ink', 'dim', 'caption ink'))
    print('-' * 128)
    for r in rows:
        if 'error' in r:
            print('%-22s %-22s %s' % (r['name'], r['label'], r['error']))
            continue
        print('%-22s %-22s %-26s %8.4f %7s  %-9s %-9s %s'
              % (r['name'], r['label'][:22], r['hex'], r['lum'],
                 'LIGHT' if r['light'] else 'dark',
                 '%.2f:1' % r['ink_contrast'] if r['ink_contrast'] else '-',
                 '%.2f:1' % r['dim_contrast'] if r['dim_contrast'] else '-',
                 '%.2f:1' % r['caption_contrast'] if r['caption_contrast'] else '-'))
    light = [r for r in rows if r.get('light')]
    print('')
    print('themes measured: %d' % len(rows))
    print('LIGHT (luminance >= %.2f): %d %s'
          % (LIGHT, len(light), [r['name'] for r in light] or ''))
    worst = sorted((r for r in rows if r.get('ink_contrast') is not None),
                   key=lambda r: r['ink_contrast'])[:5]
    print('weakest body ink over its own background: %s'
          % ', '.join('%s %.2f:1' % (r['name'], r['ink_contrast']) for r in worst))
    if args.gate and light:
        print('GATE: RED -- %d theme(s) still ship a light panel' % len(light))
        return 1
    if args.gate:
        print('GATE: GREEN -- no theme ships a light panel')
    return 0


if __name__ == '__main__':
    sys.exit(main())
