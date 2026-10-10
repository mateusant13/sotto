#!/usr/bin/env python3
"""Render a PNG as ASCII so an agent WITHOUT image input can look at a layout.

WHY THIS EXISTS. The panel's whole product surface is a picture, and this
session's model cannot read images. Screenshots were still required: the owner
asked for them. So the same pixels are printed two more ways here --
  * a luminance ASCII grid (RAMP ' .:-=+*#%@'), so geometry, borders, alignment
    of blocks and the vertical position of the caption are readable;
  * a colour census with the top saturated colours, so "which accent did this
    theme paint" and "is the background flat or composited" are numbers.
"""
import os
import sys
import numpy as np
from PIL import Image

RAMP = ' .:-=+*#%@'


def art(path, cw=None, ch=None):
    im = Image.open(path)
    if im.mode not in ('RGB', 'RGBA', 'L'):
        im = im.convert('RGB')
    rgba = im.convert('RGBA')
    w, h = im.size
    # composite over black: the strip is transparent in places, and a transparent
    # pixel must not read as white in a luminance ramp.
    bg = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    bg.alpha_composite(rgba)
    flat = np.array(bg.convert('RGB')).astype(np.float32)
    alpha = np.array(rgba)[:, :, 3].astype(np.float32)
    lum = (0.2126 * flat[:, :, 0] + 0.7152 * flat[:, :, 1] + 0.0722 * flat[:, :, 2])
    lum = lum * (alpha / 255.0)
    if cw is None:
        cw = min(160, w)
    if ch is None:
        ch = max(20, min(60, int(h * cw / w / 2.1)))
    small = Image.fromarray(lum.astype(np.uint8)).resize((cw, ch), Image.BOX)
    m = np.array(small).astype(np.float32)
    lo, hi = np.percentile(m, 3), max(np.percentile(m, 99.5), np.percentile(m, 3) + 1.0)
    n = np.clip((m - lo) / (hi - lo), 0, 1)
    idx = (n * (len(RAMP) - 1) + 0.5).astype(int)
    print('=' * (cw + 6))
    print('%s   %dx%d  ascii %dx%d  lum p3=%.0f p99.5=%.0f' % (os.path.basename(path), w, h, cw, ch, lo, hi))
    print('     ' + ''.join(('|' if c % 10 == 0 else ' ') for c in range(cw)))
    for r in range(ch):
        print('%4d ' % int(r * h / ch) + ''.join(RAMP[v] for v in idx[r]))
    # ---- colour census: the accent and the flatness ----
    px = np.asarray(flat).reshape(-1, 3).astype(np.uint32)
    hexed = (px[:, 0] << 16) | (px[:, 1] << 8) | px[:, 2]
    vals, counts = np.unique(hexed, return_counts=True)
    order = np.argsort(-counts)
    print('   distinct colours: %d over %d px  (1 = flat frame, 80+ = UI)' % (len(vals), len(px)))
    for i in order[:8]:
        v = int(vals[i])
        print('      #%06x  %6.2f%%' % (v, 100.0 * counts[i] / len(px)))
    print()


if __name__ == '__main__':
    for p in sys.argv[1:]:
        if os.path.isfile(p):
            art(p)
        else:
            print('missing ' + p)
