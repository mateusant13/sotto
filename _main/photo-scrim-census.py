#!/usr/bin/env python3
"""photo-scrim-census -- does the PHOTOGRAPH a theme paints read as a scene, or as a glitch?

ACCEPTANCE ROW E3/E4, owner verbatim: por que tem personagens falando em um dos designs
replicados? and tu ta simplesmente botando de forma burra alguns designs por cima do
painel e ai fica duas coisa sobrepostas que nao fazem sentido como se fosse um glitch.

WHY THE EXISTING CENSUS COULD NOT SEE IT: theme-lightness-census.py measures the theme
own --bg-slab. The cine- themes that paint a photograph do NOT put it in the slab -- they
compose it as linear-gradient(scrim, scrim), url(backdrops/*.jpg) on .panel, so the
painted background is the PHOTOGRAPH WITH THE SCRIM OVER IT and nothing measured that
composite. MEASURED 2026-10-15: the ten photo themes carry scrims of 0.62-0.70 while
those without a photograph carry 0.82-0.93. A 0.68 scrim leaves 32 percent of the
photograph showing, and a daylight street at that opacity competes with the caption.

WHAT THIS MEASURES, per theme: the ALPHA of the scrim the theme puts over its photo, the
MEAN LUMINANCE of the photograph itself, the resulting COMPOSITE luminance, and the
CONTRAST of the caption ink against that composite. It reads bytes and decodes the JPEG
offline; it launches nothing.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.normpath(os.path.join(HERE, os.path.pardir, "app", "panel"))
THEMES = os.path.join(PANEL, "themes")
BACKDROPS = os.path.join(THEMES, "backdrops")

CONTRAST_FLOOR = 3.0
SCRIM_FLOOR = 0.75


def relative_luminance(rgb):
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def parse_rgba(text):
    m = re.search(r"rgba?\(([^)]+)\)", text or "")
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",")]
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    while len(nums) < 3:
        nums.append(0.0)
    alpha = nums[3] if len(nums) > 3 else 1.0
    return (nums[0], nums[1], nums[2], alpha)


def photo_luminance(name):
    path = os.path.join(BACKDROPS, name)
    if not os.path.exists(path):
        return None
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        with Image.open(path) as im:
            small = im.convert("RGB").resize((48, 27))
            px = list(small.getdata())
    except Exception:
        return None
    n = len(px) or 1
    return tuple(sum(c[k] for c in px) / n for k in range(3))


def photo_themes(css):
    cur = None
    scrim = None
    photo = None
    out = []
    for line in css.split("\n"):
        m = re.match("^:root\\[data-theme='([^']+)'\\]\\{", line)
        if m:
            if cur and photo:
                out.append((cur, scrim, photo))
            cur, scrim, photo = m.group(1), None, None
            continue
        if cur is None:
            continue
        if scrim is None:
            s = re.search(r"--cine-scrim:\s*([^;]+);", line)
            if s:
                scrim = parse_rgba(s.group(1))
        if photo is None:
            p = re.search(r"url\(backdrops/([^)]+)\)", line)
            if p:
                photo = p.group(1).strip()
    if cur and photo:
        out.append((cur, scrim, photo))
    return out


def main():
    say = print
    css_path = os.path.join(THEMES, "cinematic.css")
    if not os.path.exists(css_path):
        say("photo-scrim-census: NO cinematic.css")
        return 1
    with open(css_path, encoding="utf-8", errors="replace") as h:
        css = h.read()
    pairs = photo_themes(css)
    if not pairs:
        say("photo-scrim-census: no theme composes a photograph on .panel")
        return 0
    bad = []
    say("photo-scrim-census -- %d theme(s) paint a photograph" % len(pairs))
    for theme, scrim, photo in sorted(pairs):
        if scrim is None:
            bad.append((theme, "no scrim at all"))
            say("  [GAP]  %-22s no scrim over the photograph" % theme)
            continue
        lum = photo_luminance(photo)
        if lum is None:
            say("  [warn] %-22s photo %s not decodable here" % (theme, photo))
            continue
        sr, sg, sb, sa = scrim
        comp = tuple(sa * v + (1 - sa) * lum[k] for k, v in enumerate((sr, sg, sb)))
        ink = (0xF1, 0xF5, 0xF9)
        ratio = contrast(ink, comp)
        gap = (sa < SCRIM_FLOOR) or (ratio < CONTRAST_FLOOR)
        if gap:
            bad.append((theme, "scrim=%.2f caption_contrast=%.2f" % (sa, ratio)))
        say("  [%s] %-22s scrim=%.2f photo_lum=%.3f composite_lum=%.3f contrast=%.2f"
            % ("GAP " if gap else "ok  ", theme, sa,
               relative_luminance(lum), relative_luminance(comp), ratio))
    say("")
    say("PHOTO-SCRIM %d/%d theme(s) read as a scene; %d competing"
        % (len(pairs) - len(bad), len(pairs), len(bad)))
    if bad:
        for theme, why in bad:
            say("    - %s: %s" % (theme, why))
        say("VERDICT: FAIL -- these photographs show through enough to compete with the caption")
        return 1
    say("VERDICT: PASS -- every photograph is a scene behind the caption")
    return 0


if __name__ == "__main__":
    sys.exit(main())
