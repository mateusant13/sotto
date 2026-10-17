"""Header alignment probe: vertical extent of painted glyphs per x-band.

Usage: header-probe.py <png> <out.txt> [x0 x1 label ...]
Prints, per band: first/last painted row, the painted centroid row, the painted
height, and the gap to the band's neighbours.  Bands default to the wordmark and
the control row of the 380x900 panel header.
"""
import sys
from PIL import Image


def band(im, x0, x1, y0, y1, thresh=60):
    """Rows in [y0,y1) that have at least one pixel brighter than the slab."""
    px = im.load()
    rows = {}
    for y in range(y0, y1):
        n = 0
        for x in range(x0, x1):
            r, g, b = px[x, y]
            if r > thresh or g > thresh or b > thresh:
                n += 1
        if n:
            rows[y] = n
    if not rows:
        return None
    ys = sorted(rows)
    total = sum(rows.values())
    centroid = sum(y * n for y, n in rows.items()) / float(total)
    # A glyph band is usually two clusters (e.g. name + tag). Report the gaps.
    clusters = []
    start = prev = ys[0]
    for y in ys[1:]:
        if y - prev > 1:
            clusters.append((start, prev))
            start = y
        prev = y
    clusters.append((start, prev))
    return {
        'top': ys[0], 'bottom': ys[-1],
        'centroid': round(centroid, 2),
        'height': ys[-1] - ys[0] + 1,
        'clusters': clusters,
    }


def main():
    src, dst = sys.argv[1], sys.argv[2]
    im = Image.open(src).convert('RGB')
    bands = []
    rest = sys.argv[3:]
    for i in range(0, len(rest), 3):
        bands.append((int(rest[i]), int(rest[i + 1]), rest[i + 2]))
    if not bands:
        bands = [(8, 70, 'wordmark'), (75, 250, 'controls-left'), (250, 380, 'controls-right')]
    lines = ['%s %dx%d' % (src, im.size[0], im.size[1])]
    for x0, x1, label in bands:
        r = band(im, x0, x1, 0, 80)
        lines.append('%-16s x[%3d,%3d)  %s' % (label, x0, x1, r))
    open(dst, 'w', encoding='utf-8').write('\n'.join(lines))


main()