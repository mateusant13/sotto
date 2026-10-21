"""Print the REAL overlay bitmap, not the dead `caption.html`.

`app/webview/caption_overlay.py` paints a per-pixel-alpha Win32 layered window
with GDI+. This script calls the SAME `_layout` + `_premultiplied_bitmap` the
app calls, saves the PNG, and composites it over a neutral frame so the plate,
the rule and the ink can be judged. It never shows a window and never starts the
worker -- it is a still of the renderer.

Usage:
  python _main/_design-lane/native-caption-shot.py --out <png>            # default
  python _main/_design-lane/native-caption-shot.py --tokens <json> --out <png>
  python _main/_design-lane/native-caption-shot.py --from-json <probe.json> --out-dir <dir>

`--from-json` reads a panel probe (`product/panel/<theme>.json`) and uses its
`brand` object, i.e. the tokens MEASURED from the theme's own forming row.
"""
import argparse
import json
import os
import sys

WEBVIEW = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'app', 'webview')
if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

import caption_overlay as co  # noqa: E402

LIVE = 'A legenda nasce enquanto a frase ainda esta em formacao.'
PREV = 'Quando a frase fecha, ela ganha peso - e fica.'


def _composite(raw_path, out_path):
    """Put the transparent bitmap over a frame-like backdrop for inspection."""
    from PIL import Image
    img = Image.open(raw_path).convert('RGBA')
    w, h = img.size
    # A calm, slightly warm gradient: a caption is judged against video, not
    # against the checkerboard an alpha PNG shows in a viewer.
    canvas = Image.new('RGBA', (w, h), (24, 27, 33, 255))
    px = canvas.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(26 + 34 * t)
        g = int(31 + 26 * t)
        b = int(40 + 14 * t)
        for x in range(w):
            px[x, y] = (r, g, b, 255)
    # A soft light patch behind the centre, the way a face/key light sits
    # behind a real subtitle. It exists to make "white ink on white video"
    # failures visible instead of flattering the design.
    glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    gpx = glow.load()
    cx, cy = w * 0.62, h * 0.45
    rad = max(1.0, min(w, h) * 0.55)
    for y in range(h):
        for x in range(w):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / rad
            if d < 1.0:
                a = int(60 * (1.0 - d) ** 2)
                gpx[x, y] = (196, 178, 148, a)
    canvas.alpha_composite(glow)
    canvas.alpha_composite(img)
    canvas.convert('RGB').save(out_path)


def render(tokens, out_path, work_width=1920, scale=1.0, live=LIVE, prev=PREV):
    theme = co._normalise_theme(tokens)
    cur, prev_line, width, height, scrolled = co._layout(
        live, prev, scale, work_width, theme)
    bmp = co._premultiplied_bitmap(cur, prev_line, width, height, scale, theme)
    raw = out_path + '.raw.png'
    from System.Drawing.Imaging import ImageFormat
    try:
        bmp.Save(raw, ImageFormat.Png)
    finally:
        bmp.Dispose()
    _composite(raw, out_path)
    try:
        os.remove(raw)
    except OSError:
        pass
    return {
        'out': out_path,
        'theme': theme.get('theme'),
        'font': theme.get('fontFamily'),
        'livePx': round(theme.get('livePx'), 2),
        'prevPx': round(theme.get('prevPx'), 2),
        'plate': theme.get('plate'),
        'ruleW': round(theme.get('ruleW'), 2),
        'ruleColor': theme.get('ruleColor'),
        'led': theme.get('led'),
        'align': theme.get('align'),
        'size': [width, height],
        'lines': cur,
        'previous': prev_line,
        'scrolled': scrolled,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', help='PNG path for one render')
    ap.add_argument('--tokens', help='JSON file with one token object')
    ap.add_argument('--from-json', help='panel probe JSON (reads its `brand`)')
    ap.add_argument('--out-dir', help='directory for --from-json')
    ap.add_argument('--live', default=LIVE)
    ap.add_argument('--prev', default=PREV)
    args = ap.parse_args()

    if args.from_json:
        with open(args.from_json, encoding='utf-8') as fh:
            data = json.load(fh)
        brand = data.get('brand') or {}
        out_dir = args.out_dir or os.path.dirname(args.from_json)
        os.makedirs(out_dir, exist_ok=True)
        name = brand.get('theme') or os.path.splitext(
            os.path.basename(args.from_json))[0]
        out = os.path.join(out_dir, name + '.png')
        info = render(brand, out, live=args.live, prev=args.prev)
        print(json.dumps(info, ensure_ascii=False))
        return

    if not args.out:
        raise SystemExit('--out is required (or use --from-json)')
    tokens = {}
    if args.tokens:
        with open(args.tokens, encoding='utf-8') as fh:
            tokens = json.load(fh)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    info = render(tokens, args.out, live=args.live, prev=args.prev)
    print(json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    main()
