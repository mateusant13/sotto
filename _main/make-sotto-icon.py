#!/usr/bin/env python3
"""Generate `app/webview/sotto.ico` — the panel's face.

WHY THIS FILE EXISTS: the repo had NO Sotto icon. The only `.ico` in the tree is
`app/src-tauri/icons/icon.ico`, which is the **stock Tauri scaffold icon** (the
Tauri logo) belonging to a shell that is not the app. Copying it would have
replaced one lie ("this is Python") with another ("this is Tauri"), so a MINIMAL
mark was generated instead and that is stated plainly in the receipt. It is not a
brand: it is the panel's own accent, drawn.

The accent is the panel's, read out of `app/panel/panel.css:19-22` (READ ONLY —
that directory belongs to another lane):
    --accent-from: #7dd3fc;  --accent-to: #a78bfa;
    --accent-gradient: linear-gradient(135deg, from 0%, to 100%)
and the window's own background is the shell's `background_color` `#0b0f14`.

Run:  python _main/make-sotto-icon.py
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'app', 'webview', 'sotto.ico')

BG = (11, 15, 20, 255)          # the shell's `background_color` #0b0f14
FROM = (0x7d, 0xd3, 0xfc)       # panel.css:19 --accent-from
TO = (0xa7, 0x8b, 0xfa)         # panel.css:20 --accent-to
SIZES = (16, 32, 48, 64, 128, 256)


def gradient(size: int) -> Image.Image:
    """135deg linear gradient, from -> to, matching the panel's accent."""
    img = Image.new('RGBA', (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1)) if size > 1 else 0.0
            px[x, y] = (
                round(FROM[0] + (TO[0] - FROM[0]) * t),
                round(FROM[1] + (TO[1] - FROM[1]) * t),
                round(FROM[2] + (TO[2] - FROM[2]) * t),
                255,
            )
    return img


def frame(size: int) -> Image.Image:
    # Rounded dark plate, so the mark reads on a light taskbar too.
    base = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    inset = max(1, round(size * 0.03))
    radius = max(2, round(size * 0.22))
    d.rounded_rectangle([inset, inset, size - 1 - inset, size - 1 - inset],
                        radius=radius, fill=BG)

    grad = gradient(size)
    # Three caption bars, the live-box shape: decreasing width, top to bottom.
    bar_h = max(2, round(size * 0.10))
    gap = max(1, round(size * 0.075))
    left = round(size * 0.20)
    total = 3 * bar_h + 2 * gap
    top = (size - total) // 2
    widths = (0.60, 0.42, 0.52)
    mask = Image.new('L', (size, size), 0)
    md = ImageDraw.Draw(mask)
    for i, frac in enumerate(widths):
        y0 = top + i * (bar_h + gap)
        md.rounded_rectangle([left, y0, left + round(size * frac), y0 + bar_h],
                             radius=max(1, bar_h // 2), fill=255)
    base.paste(grad, (0, 0), mask)
    return base


def main() -> int:
    # Pillow's ICO writer resizes ONE base image into every requested size
    # (`IcoImagePlugin._save`); it has no per-size image channel, so the base is
    # drawn at 256 and the small frames are LANCZOS reductions of it.
    frame(256).save(OUT, format='ICO', sizes=[(s, s) for s in SIZES])
    print(f'wrote {OUT} ({os.path.getsize(OUT)} B) sizes={SIZES}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
