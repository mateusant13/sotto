#!/usr/bin/env python3
"""zip-fidelity-by-numbers -- E2 without eyes: is the SHIPPED panel the zip shape?

ACCEPTANCE ROW E2, owner verbatim: compara as prints das demos dos .zip com as prints
do que ta implementado atual. eu nao gostei dos atuais. e pra imitar mais os .zip.

The owner told me to compare the prints. I CAN see images now, but this session retracted
TWICE for believing my own reading of a print -- a cut that was a line break, and a wall
that was a capped list. So this instrument does not trust an eye: it measures STRUCTURE,
which is the part of a design that can be compared without taste.

WHAT IT MEASURES per image, deliberately coarse:
  1. the LUMINANCE PROFILE in thirds -- where the light lives;
  2. the DARK SHARE -- how much of the frame is below a luminance floor;
  3. the INK COLOUR the design types with, from the darkest decile;
  4. the EDGE ENERGY -- mean horizontal gradient, a proxy for structure.

It decodes the images with Pillow offline and launches nothing.
"""

from __future__ import annotations

import os
import sys

DEMO = os.environ.get("ZIP_DEMO", "I:/cc-tmp/zip-D-themes.png")
SHOT = os.environ.get("ZIP_SHOT", "I:/cc-tmp/shots5/panel-theme-1.png")


def profile(path):
    try:
        from PIL import Image
    except Exception:
        return None
    if not os.path.exists(path):
        return None
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        small = rgb.resize((48, 81))
        px = list(small.getdata())
        n = len(px) or 1
        lum = [0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] for p in px]
        cols = 48
        rows = 81
        thirds = []
        for t in range(3):
            lo = int(rows * t / 3)
            hi = int(rows * (t + 1) / 3)
            seg = lum[lo * cols:hi * cols]
            thirds.append(sum(seg) / (len(seg) or 1) / 255.0)
        dark = sum(1 for v in lum if v / 255.0 < 0.18) / float(n)
        srt = sorted(px, key=lambda p: p[0] + p[1] + p[2])
        ink = srt[int(n * 0.08)]
        edge = 0.0
        cnt = 0
        for r in range(rows - 1):
            for c in range(cols - 1):
                a = lum[r * cols + c]
                b = lum[(r + 1) * cols + c]
                edge += abs(a - b)
                cnt += 1
        edge = edge / (cnt or 1) / 255.0
    return {"thirds": thirds, "dark": dark, "ink": ink, "edge": edge, "size": (w, h)}


def show(tag, p):
    if p is None:
        print("  %-6s UNAVAILABLE" % tag)
        return
    t = p["thirds"]
    print("  %-6s %dx%d  top=%.3f mid=%.3f bot=%.3f  dark=%.2f  edge=%.3f  ink=%s"
          % (tag, p["size"][0], p["size"][1], t[0], t[1], t[2], p["dark"],
             p["edge"], p["ink"]))


def main() -> int:
    print("zip-fidelity-by-numbers -- the shipped panel against the zip demo, by bytes")
    demo = profile(DEMO)
    shot = profile(SHOT)
    show("demo", demo)
    show("shot", shot)
    print("")
    if demo is None or shot is None:
        missing = [p for p, v in ((DEMO, demo), (SHOT, shot)) if v is None]
        print("VERDICT: UNKNOWN -- cannot read %s" % ", ".join(missing))
        return 0
    d = [abs(a - b) for a, b in zip(demo["thirds"], shot["thirds"])]
    print("  DELTA thirds: top=%.3f mid=%.3f bot=%.3f mean=%.3f"
          % (d[0], d[1], d[2], sum(d) / 3.0))
    print("  DELTA dark=%.2f edge=%.3f"
          % (abs(demo["dark"] - shot["dark"]), abs(demo["edge"] - shot["edge"])))
    print("")
    print("WHAT THIS DOES NOT SAY: whether the shipped panel LOOKS like the demo. It says")
    print("where the light lives, how much is dark, how much structure there is and what")
    print("colour the design types with -- the four things a demo and a render can be")
    print("compared on without taste. A small delta is not a verdict of beauty; it is a")
    print("verdict that the STRUCTURE is in the same place.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
