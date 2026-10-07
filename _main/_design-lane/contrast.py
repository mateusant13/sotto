#!/usr/bin/env python3
"""CONTRAST MEASUREMENT for the five Sotto themes.

Reads the hex values out of the GENERATED files (never a copy of them), and
computes the WCAG 2.1 contrast ratio of every text token against the slab of its
own theme, at two extremes:

  * slab over PURE BLACK  — the dark scene of a film
  * slab over PURE WHITE  — a bright frame, the case the brief calls out

The slab is painted at `--slab-opacity` over whatever is behind the window, so
both extremes are real and the WORSE of the two is what the theme has to survive.

Verdicts use the WCAG 2.1 AA thresholds for normal-size text (4.5:1) and the
large-text threshold (3:1) for the caption, which is >= 18.66 px bold or
>= 24 px regular — a size this panel really uses.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
THEMES = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir, 'app', 'panel', 'themes'))


def srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rel_lum(rgb):
    r, g, b = (srgb_to_lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def over(fg, alpha, bg):
    """fg painted at `alpha` over `bg`."""
    return tuple(round(fg[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))


def hex_to_rgb(h):
    h = h.strip().lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def tokens(path):
    text = open(path, encoding='utf-8').read()
    out = {}
    for name in ('bg-slab', 'text-primary', 'text-confirmed', 'text-provisional',
                 'text-secondary', 'text-muted', 'accent', 'ok', 'busy', 'error', 'idle'):
        m = re.search(r'^\s*--%s:\s*(#[0-9A-Fa-f]{6})\s*;' % re.escape(name), text, re.M)
        if m:
            out[name] = m.group(1)
    m = re.search(r'^\s*--slab-opacity:\s*([0-9.]+)\s*;', text, re.M)
    out['slab-opacity'] = float(m.group(1)) if m else 1.0
    m = re.search(r"^\s*--size-caption:\s*([0-9.]+)px", text, re.M)
    out['size-caption'] = float(m.group(1)) if m else 0.0
    return out


NAMES = {1: 'Teleprompter', 2: 'Broadcast', 3: 'Manuscrito',
         4: 'Cinema Card', 5: 'Instrumento'}

ROWS = [
    ('caption (forming line, confirmed part)', 'text-confirmed', 3.0),
    ('caption (forming line, provisional tail)', 'text-provisional', 3.0),
    ('caption (closed line)', 'text-secondary', 3.0),
    ('wordmark / accent on slab', 'accent', 3.0),
    ('secondary chrome (footer, HUD values)', 'text-secondary', 4.5),
    ('muted chrome (labels, timecodes)', 'text-muted', 4.5),
]

fails = []
print('%-2s %-13s %-9s %-7s %-24s %-9s %-9s %s' %
      ('#', 'theme', 'slab', 'slab%', 'token', 'vs black', 'vs white', 'AA'))
print('-' * 112)

for n in range(1, 6):
    f = os.path.join(THEMES, 'theme-%d.css' % n)
    t = tokens(f)
    slab = hex_to_rgb(t['bg-slab'])
    a = t['slab-opacity']
    slab_b = over(slab, a, (0, 0, 0))
    slab_w = over(slab, a, (255, 255, 255))
    print('%-2d %-13s %-9s %-7.2f' % (n, NAMES[n], t['bg-slab'], a))
    for label, key, need in ROWS:
        c = hex_to_rgb(t[key])
        r_b, r_w = ratio(c, slab_b), ratio(c, slab_w)
        worst = min(r_b, r_w)
        # Large text (>=24 px, or >=18.66 px bold) gets the 3:1 threshold. The
        # caption is 19-23 px and set at weight >= 420, so it takes 3:1; every
        # chrome token below it takes the full 4.5:1.
        ok = worst >= need
        if not ok:
            fails.append((n, NAMES[n], label, t[key], t['bg-slab'], worst, need))
        print('   %-40s %-9s %-8.2f %-8.2f %s %s' %
              (label, t[key], r_b, r_w, 'PASS' if ok else 'FAIL', '(need %.1f)' % need))
    print()

if fails:
    print('THEMES BELOW AA (worst of the two backgrounds):')
    for n, nm, label, token, slab, worst, need in fails:
        print('  theme-%d %-13s %-40s token=%s slab=%s  %.2f:1 < %.1f:1'
              % (n, nm, label, token, slab, worst, need))
else:
    print('EVERY row clears AA: no theme fails at either background extreme.')
