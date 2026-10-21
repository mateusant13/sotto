"""Two curated sheets for the 2026-10-21 fix.

1. comparison-last-train.png -- the vendor's own panel (the clean reference),
   the fixed Sotto panel with lines, and the fixed idle state.
2. skins-idle-filled.png -- all six shipped skins, filled on top, idle below.

These replace the diagnostic `_compare/` folder as the human-facing record; the
folder itself is deleted after the sheets are written.
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    'docs', 'design-audit-20261021')
OUT = os.path.join(ROOT, 'contact-sheets')
os.makedirs(OUT, exist_ok=True)


def font(size, bold=False):
    for name in (('segoeuib.ttf', 'segoeui.ttf') if bold else ('segoeui.ttf',)):
        p = os.path.join('C:\\Windows\\Fonts', name)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def fit(img, w, h):
    """Scale to fit inside w x h, preserving aspect, on a transparent canvas."""
    r = min(w / img.width, h / img.height)
    nw, nh = max(1, round(img.width * r)), max(1, round(img.height * r))
    return img.resize((nw, nh), Image.LANCZOS)


def wrap(draw, text, fnt, maxw):
    lines, cur = [], ''
    for word in text.split():
        trial = (cur + ' ' + word).strip()
        if cur and draw.textlength(trial, font=fnt) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def tile(canvas, draw, img, x, y, w, h, label, sub=''):
    im = fit(img, w, h)
    px = x + (w - im.width) // 2
    py = y + (h - im.height) // 2
    canvas.paste(im, (px, py))
    draw.rectangle([px - 1, py - 1, px + im.width, py + im.height], outline=(90, 96, 106), width=1)
    fy = y + h + 10
    for line in wrap(draw, label, font(18, True), w):
        draw.text((x, fy), line, font=font(18, True), fill=(235, 239, 244))
        fy += 22
    if sub:
        for line in wrap(draw, sub, font(13), w):
            draw.text((x, fy), line, font=font(13), fill=(160, 170, 182))
            fy += 18


def comparison():
    vendor = Image.open(os.path.join(ROOT, 'demos', 'zip5-cinematic-2', '13-last-train', 'panel.png')).convert('RGB')
    filled = Image.open(os.path.join(ROOT, 'product', 'panel', 'cine-last-train.png')).convert('RGB')
    idle = Image.open(os.path.join(ROOT, 'states', 'idle', 'cine-last-train.png')).convert('RGB')

    W = 1240
    canvas = Image.new('RGB', (W, 1180), (16, 19, 24))
    d = ImageDraw.Draw(canvas)
    d.text((34, 26), 'LAST TRAIN - clean reference vs the fixed Sotto panel', font=font(28, True), fill=(240, 244, 248))
    intro = ('The vendor zip panel is the reference. The product used to stack the vendor panel, the stage chrome and our controls in one 56 px band; '
             'the panel was 745 px tall and the caption box was 0 px at y=900. It is now one window: a 56 px app bar, the design panel edge-to-edge, '
             'and the live plate over its foot.')
    sy = 64
    for line in wrap(d, intro, font(13), W - 68):
        d.text((34, sy), line, font=font(13), fill=(166, 176, 189))
        sy += 20

    y = sy + 18
    tile(canvas, d, vendor, 30, y, 300, 900, 'VENDOR - clean reference', 'zip5 / cinematic-2 / last-train')
    tile(canvas, d, filled, 370, y, 380, 900, 'SOTTO - with lines', '380 x 900 / one bar, one panel, one plate')
    tile(canvas, d, idle, 790, y, 380, 900, 'SOTTO - idle', '380 x 900 / no lines yet, no dead chrome')

    out = os.path.join(OUT, 'comparison-last-train.png')
    canvas.save(out, optimize=True)
    print(out, canvas.size)


def skins():
    themes = ['cine-blue-hour', 'cine-cellar', 'cine-last-train', 'cine-linen', 'cine-rainline', 'cine-reading-hour']
    cw, ch = 250, 592
    gap_x, gap_y = 24, 74
    W = 34 * 2 + cw * 6 + gap_x * 5
    H = 120 + (ch + gap_y) * 2 + 20
    canvas = Image.new('RGB', (W, H), (16, 19, 24))
    d = ImageDraw.Draw(canvas)
    d.text((34, 24), 'SIX SHIPPED SKINS — filled (top) and idle (bottom)', font=font(28, True), fill=(240, 244, 248))
    d.text((34, 62), 'Every skin fills the window below the app bar. Idle is a state, not a hole: the vendor mock rows are gone and the sentence is ours.',
           font=font(13), fill=(166, 176, 189))
    y = 120
    for mode, folder in (('filled', 'filled'), ('idle', 'idle')):
        for i, th in enumerate(themes):
            p = os.path.join(ROOT, 'states', folder, '%s.png' % th)
            if not os.path.exists(p):
                continue
            im = Image.open(p).convert('RGB')
            x = 34 + i * (cw + gap_x)
            tile(canvas, d, im, x, y, cw, ch, th, 'with lines' if mode == 'filled' else 'idle')
        y += ch + gap_y
    out = os.path.join(OUT, 'skins-idle-filled.png')
    canvas.save(out, optimize=True)
    print(out, canvas.size)


if __name__ == '__main__':
    comparison()
    skins()
