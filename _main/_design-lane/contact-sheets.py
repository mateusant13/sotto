"""Build the contact sheets for the 2026-10-21 design audit.

READ-ONLY over the shots: this script never launches the app, the worker or a
browser. It is a PIL index over files that already exist.

Usage:
  python _main/_design-lane/contact-sheets.py
"""
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'docs', 'design-audit-20261021')
OUT = os.path.join(ROOT, 'contact-sheets')
BG = (11, 13, 16)
INK = (226, 232, 240)
DIM = (148, 163, 184)
ACCENT = (125, 211, 252)


def font(size):
    for path in (r'C:\Windows\Fonts\segoeui.ttf',
                 r'C:\Windows\Fonts\arial.ttf'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def label(draw, xy, text, fill=INK, size=13):
    draw.text(xy, text, font=font(size), fill=fill)


def sheet(title, items, cols, cell_w, cell_h, label_h, out_path):
    """items: [(label, image_path), ...]; image is contained in the cell."""
    rows = max(1, (len(items) + cols - 1) // cols)
    pad = 10
    head = 42
    width = cols * (cell_w + pad) + pad
    height = head + rows * (cell_h + label_h + pad) + pad
    canvas = Image.new('RGB', (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    label(draw, (pad, 10), title, INK, 18)
    label(draw, (pad, 30), '%d images  |  %s' % (len(items), os.path.basename(ROOT)),
          DIM, 11)
    for i, (name, path) in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad)
        y = head + r * (cell_h + label_h + pad)
        if path and os.path.exists(path):
            try:
                img = Image.open(path).convert('RGB')
                img.thumbnail((cell_w, cell_h), Image.LANCZOS)
                canvas.paste(img, (x + (cell_w - img.width) // 2,
                                   y + (cell_h - img.height) // 2))
            except Exception as exc:  # noqa: BLE001 -- a broken shot is labelled
                label(draw, (x + 4, y + 4), 'BROKEN: %s' % exc, (248, 113, 113), 10)
        else:
            label(draw, (x + 4, y + 4), 'MISSING', (248, 113, 113), 10)
        label(draw, (x + 2, y + cell_h + 2), name, INK, 12)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path)
    print('%6d x %-5d  %s' % (width, height, out_path))


def product():
    themes = sorted(os.path.splitext(os.path.basename(p))[0]
                    for p in glob.glob(os.path.join(ROOT, 'product', 'panel', '*.png')))
    specs = (
        ('panel', 'PRODUCT PANELS - 380 x 900 (all 45 themes)', 9, 144, 342, 18),
        ('strip', 'PRODUCT STRIP - 1040 x 40 (all 45 themes)', 2, 500, 20, 18),
        ('strip-float', 'PRODUCT STRIP + FLOAT - 1040 x 220 (all 45 themes)',
         3, 500, 106, 18),
    )
    for view, title, cols, cw, ch, lh in specs:
        items = [(t, os.path.join(ROOT, 'product', view, t + '.png'))
                 for t in themes]
        sheet(title, items, cols, cw, ch, lh,
              os.path.join(OUT, 'product-%s.png' % view))
    native = [(t, os.path.join(ROOT, 'native', t + '.png')) for t in themes]
    sheet('NATIVE CAPTION OVERLAY - the real GDI+ renderer (all 45 themes)',
          native, 4, 480, 170, 18,
          os.path.join(OUT, 'native-overlay.png'))


def demos():
    for group in sorted(glob.glob(os.path.join(ROOT, 'demos', '*'))):
        if not os.path.isdir(group):
            continue
        name = os.path.basename(group)
        apps, panels = [], []
        for d in sorted(glob.glob(os.path.join(group, '*'))):
            if not os.path.isdir(d):
                continue
            label_name = os.path.basename(d)
            apps.append((label_name, os.path.join(d, 'app.png')))
            panels.append((label_name, os.path.join(d, 'panel.png')))
        if apps:
            sheet('%s - APP (zip demo, fresh)' % name, apps, 5, 300, 188, 18,
                  os.path.join(OUT, 'demos-%s-app.png' % name))
        if panels:
            sheet('%s - PANEL (zip demo, clipped at the demo panel)' % name,
                  panels, 10, 128, 303, 16,
                  os.path.join(OUT, 'demos-%s-panel.png' % name))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    product()
    demos()
