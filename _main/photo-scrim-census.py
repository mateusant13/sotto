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

WHAT CHANGED 2026-10-15 (LANE D -- receipt-20261015-a-cura-e-minha.md). The value was
never the defect; the FORM was. zips/cinematic/src/index.css:90-98 does not dim the
frame with one wash: it paints THREE reading scrims -- scrim-top
(rgba(0,0,0,0.5)->0), scrim-bottom (the theme's own --cine-scrim->0) and a vignette --
over the wallpaper (Backdrop.tsx:35-37), leaving the MIDDLE of the photograph showing
and darkening the bottom. A FLAT linear-gradient(--cine-scrim, --cine-scrim) over the
whole panel is the glitch: the frame is neither scene nor backdrop. The generators
were changed to the zip's own three layers, so the metric changed with them:

  1. THE PAINTING RULE, not the first one. An extra theme paints its own .panel rule
     AFTER the generator's default, so the census reads the LAST .panel rule of the
     theme that carries a backdrop. Measured: the old census reported cine-linen as a
     GAP by reading a rule that never paints -- its own rule carries the design's own
     gradient and always did.
  2. THE FORM (E4): the composition must be GRADIENTS over the photograph -- at least
     two of them, none flat (a layer that paints the same colour everywhere washes the
     frame), the photograph LAST, and background-size carrying ONE value per layer.
  3. THE CAPTION ZONE (E3, the receipt's metric): the LUMINANCE OF THE COMPOSITE in
     the caption zone -- the bottom third of the 380x900 panel, evaluated at its
     centre and at its weakest (top) point -- with the caption ink's contrast gated
     at CONTRAST_FLOOR. A flat alpha is not a metric this stylesheet has any more.
  4. THE MIDDLE, measured and REPORTED per theme: the same composite at the panel's
     middle, plus the share of the photograph that survives there. The flat scrim
     reported ~0.32 of the photograph everywhere; the zip's three layers leave the
     middle at ~0.50 while the caption zone drops to ~0.40. That recovery is the
     number the receipt carries.

It reads bytes and decodes the JPEGs offline with Pillow; it launches nothing. The
gradient evaluator below reads the SAME layers the browser would paint -- linear
gradients by direction, radial gradients by ellipse geometry -- and is deliberately
fail-closed: a layer it cannot read is a GAP, not a pass.
"""
from __future__ import annotations

import io
import math
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.normpath(os.path.join(HERE, os.path.pardir, "app", "panel"))
THEMES = os.path.join(PANEL, "themes")
BACKDROPS = os.path.join(THEMES, "backdrops")

# THE PANEL BOX. Measured: app/panel/surface.js calls it the 380x900 panel and
# panel.css:150-182 makes .panel fill the window, so the backdrop is cover-fitted
# into 380x900 and the caption lives in its bottom third.
PANEL_W, PANEL_H = 380.0, 900.0
# The caption zone: the bottom third, at its centre and at its WEAKEST point (the top
# edge of the zone). The gate reads the weakest point, so a caption line anywhere in
# the zone still wins.
CAPTION_Y = 2.0 / 3.0 * PANEL_H + PANEL_H / 6.0          # 750
CAPTION_WEAKEST_Y = 2.0 / 3.0 * PANEL_H                  # 600
MIDDLE_Y = 0.5 * PANEL_H                                 # 450
INK = (0xF1, 0xF5, 0xF9)      # the caption ink the panel paints
CONTRAST_FLOOR = 3.0          # the same floor the previous revision used


# ─── colour + luminance ────────────────────────────────────────────────────────

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
    """#rgb, #rrggbb, rgb(), rgba(), transparent -> (r, g, b, a) or None.

    `transparent` is NOT cosmetic here: the zip's own three layers are written
    with it (index.css:90-98), and a parser that dropped it read the vignette as
    NOTHING -- measured, the census then failed all four base themes whose rule
    carries it.
    """
    t = (text or "").strip()
    if t.lower() == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    m = re.fullmatch(r"#([0-9a-fA-F]{3})", t)
    if m:
        h = m.group(1)
        return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 1.0)
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", t)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.search(r"rgba?\(([^)]+)\)", t)
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


# ─── the CSS readers ──────────────────────────────────────────────────────────

def strip_comments(css):
    return re.sub(r"/\*[\s\S]*?\*/", "", css)


def blocks(flat, selector):
    """ALL bodies of 'selector { ... }', brace-matched, in file order.

    ALL, not the first: an extra theme emits the generator's default .panel rule and
    THEN its own, so the one that paints is the last.
    """
    out = []
    for m in re.finditer(re.escape(selector) + r"\s*\{", flat):
        i = m.end()
        depth, start = 1, i
        while i < len(flat) and depth:
            if flat[i] == "{":
                depth += 1
            elif flat[i] == "}":
                depth -= 1
            i += 1
        out.append(flat[start:i - 1])
    return out


def decls_of(body):
    return dict(re.findall(r"(background(?:-color|-image|-size|-position)?)\s*:\s*([^;]+);",
                           body))


def split_layers(image):
    """Split a background-image layer list on top-level commas."""
    depth, cur, parts = 0, "", []
    for ch in image:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def tokens_of(flat, name):
    """The theme's own token block (the canonical one, where --cine-scrim lives)."""
    for b in blocks(flat, ":root[data-theme='%s']" % name):
        out = {}
        for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", b):
            out[m.group(1)] = m.group(2).strip()
        if out:
            return out
    return {}


def resolve_token(tokens, text, depth=0):
    if depth > 8:
        return None
    t = (text or "").strip()
    m = re.fullmatch(r"var\((--[\w-]+)\)", t)
    if m:
        v = tokens.get(m.group(1)) if tokens else None
        return None if v is None else resolve_token(tokens, v, depth + 1)
    return parse_rgba(t)


def photo_themes(flat):
    """[(theme, rule_body)] for every cine- theme whose PAINTING .panel rule composes a photo."""
    names = []
    for m in re.finditer(r":root\[data-theme='(cine-[^']+)'\]", flat):
        if m.group(1) not in names:
            names.append(m.group(1))
    out = []
    for name in sorted(names):
        body = None
        for b in blocks(flat, ":root[data-theme='%s'] .panel" % name):
            if "url(" in b:
                body = b
        if body is not None:
            out.append((name, body))
    return out


def painting_ruleLayers(body):
    """(layers, photo_name, decls) of a .panel rule body.

    layers keeps the CSS order; the FIRST declared is the TOP one.
    """
    decls = decls_of(body)
    image = decls.get("background-image")
    if not image:
        return None, None, decls
    layers, photo = [], None
    for part in split_layers(image):
        part = part.strip()
        mu = re.search(r"url\(\s*backdrops/([^)\s]+)\s*\)", part)
        if mu:
            photo = mu.group(1)
            layers.append(("photo", mu.group(1)))
            continue
        if "gradient(" in part:
            layers.append(("gradient", part))
            continue
        layers.append(("other", part))
    return layers, photo, decls


# ─── the gradient evaluator (the same layers a browser would paint) ────────────

def _stops(layer, tokens):
    """(angle_or_radial_shape, [(position, rgba)]). None where it cannot read."""
    if "linear-gradient" in layer:
        m = re.match(r"\s*linear-gradient\(\s*(.*)$", layer, re.S)
        if not m:
            return None, None
        body, ang = m.group(1), "bottom"
        d = re.match(r"to\s+(top|bottom|left|right)\s*,", body)
        if d:
            ang, body = d.group(1), body[d.end():]
        else:
            d = re.match(r"([\d.]+)deg\s*,", body)
            if d:
                ang, body = float(d.group(1)), body[d.end():]
    elif "radial-gradient" in layer:
        m = re.search(r"radial-gradient\(\s*([\d.%\s]+?)\s+at\s+([\d.]+)%\s+([\d.]+)%\s*,", layer)
        if not m:
            return None, None
        body = layer[m.end():]
        ang = ("radial", [float(x) for x in m.group(1).replace("%", "").split()],
               float(m.group(2)), float(m.group(3)))
    else:
        return None, None
    stops = []
    for sm in re.finditer(r"(rgba?\([^)]*\)|#[0-9a-fA-F]{3,6}|var\(--[\w-]+\)|transparent)"
                          r"\s*([\d.]+%?)?", body):
        col = resolve_token(tokens, sm.group(1))
        if col is None:
            continue
        pos = sm.group(2)
        stops.append((None if pos is None else
                      (float(pos[:-1]) if pos.endswith("%") else float(pos)) / 100.0, col))
    if len(stops) < 2:
        return ang, None
    fixed = [s for s in stops if s[0] is not None]
    if not fixed:
        stops = [(i / (len(stops) - 1.0), c) for i, (_, c) in enumerate(stops)]
    else:
        # a stop with no position sits midway between its neighbours
        # (the ends default to 0 and 1)
        out, last = [], None
        for idx, (p, c) in enumerate(stops):
            if p is None:
                nxt = next((stops[j][0] for j in range(idx + 1, len(stops))
                            if stops[j][0] is not None), 1.0)
                p = ((last if last is not None else 0.0) + nxt) / 2.0
            out.append((p, c))
            last = p
        stops = out
    return ang, stops


def _sample(stops, t):
    if t <= stops[0][0]:
        return stops[0][1]
    if t >= stops[-1][0]:
        return stops[-1][1]
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            f = (t - p0) / (p1 - p0) if p1 != p0 else 1.0
            return tuple(c0[k] + (c1[k] - c0[k]) * f for k in range(4))
    return stops[-1][1]


def eval_layer(layer, tokens, px, py):
    """The colour of ONE gradient layer at (px, py) of the panel box."""
    ang, stops = _stops(layer, tokens)
    if stops is None:
        return None
    if isinstance(ang, tuple) and ang[0] == "radial":
        rx_pct, ry_pct = ang[1]
        cx = ang[2] / 100.0 * PANEL_W
        cy = ang[3] / 100.0 * PANEL_H
        rx, ry = rx_pct / 100.0 * PANEL_W, ry_pct / 100.0 * PANEL_H
        dx, dy = px - cx, py - cy
        if dx == 0 and dy == 0:
            t = 0.0
        else:
            # position along the gradient ray = distance to the ellipse's own edge in
            # that direction (the default farthest-corner ending shape)
            t = math.sqrt((ry * dx) ** 2 + (rx * dy) ** 2) / (rx * ry)
        return _sample(stops, t)
    if ang == "top":
        t = 1.0 - py / PANEL_H
    elif ang == "right":
        t = px / PANEL_W
    elif ang == "left":
        t = 1.0 - px / PANEL_W
    else:
        t = py / PANEL_H
    return _sample(stops, t)


# ─── the photograph, band by band (as background-size: cover shows it) ─────────

_BANDS = {}


def photo_band(name, band, themes_dir=None):
    """Mean RGB of the photo in one third of the panel's height, cover-fitted."""
    key = (themes_dir or THEMES, name, band)
    if key in _BANDS:
        return _BANDS[key]
    path = os.path.join(themes_dir or THEMES, "backdrops", name)
    out = None
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            s = max(PANEL_W / w, PANEL_H / h)
            sw, sh = w * s, h * s
            mx = (sw - PANEL_W) / 2.0 / s if sw > PANEL_W else 0.0
            my = (sh - PANEL_H) / 2.0 / s if sh > PANEL_H else 0.0
            x0, x1 = mx, w - mx
            y0, y1 = my, h - my
            if band == "caption":
                a, b = y0 + (y1 - y0) * (2.0 / 3.0), y1
            elif band == "middle":
                a, b = y0 + (y1 - y0) * (1.0 / 3.0), y0 + (y1 - y0) * (2.0 / 3.0)
            else:
                a, b = y0, y1
            crop = im.crop((int(x0), int(a), int(x1), int(b))).resize((24, 24))
            px = list(crop.getdata())
        n = float(len(px))
        out = tuple(sum(p[i] for p in px) / n for i in range(3))
    except Exception as exc:                                  # noqa: BLE001
        sys.stderr.write("photo not measured (%s, %s): %s\n" % (name, band, exc))
    _BANDS[key] = out
    return out


def composite_at(layers, tokens, photo, py, themes_dir=None):
    """The painted RGB at (panel_x, py): every gradient layer over the photo band."""
    band = photo_band(photo, "caption" if py >= CAPTION_WEAKEST_Y else "middle",
                      themes_dir)
    if band is None:
        return None
    cur = list(band)
    for kind, text in layers:
        if kind != "gradient":
            continue
        col = eval_layer(text, tokens, PANEL_W / 2.0, py)
        if col is None:
            return None
        a = col[3]
        cur = [col[0] * a + cur[0] * (1 - a),
               col[1] * a + cur[1] * (1 - a),
               col[2] * a + cur[2] * (1 - a)]
    return tuple(cur)


def mean8(rgb):
    return sum(rgb[:3]) / 3.0


def layer_is_flat(layer, tokens):
    """True when the layer paints the SAME colour everywhere in the panel.

    A flat layer is a wash: the photograph is dimmed (or brightened) as much in the
    middle as behind the caption, which is the E4 defect and what the receipt cured.
    """
    cols = []
    for py in (10.0, 175.0, 300.0, 450.0, 600.0, 750.0, 890.0):
        for px in (10.0, PANEL_W / 2.0, PANEL_W - 10.0):
            col = eval_layer(layer, tokens, px, py)
            if col is None:
                return False              # unreadable is handled by the caller
            cols.append(col)
    if all(abs(c[3] - cols[0][3]) < 1e-6 and
           all(abs(c[k] - cols[0][k]) < 0.5 for k in range(3)) for c in cols):
        return True                       # one colour everywhere: a wash
    if max(c[3] for c in cols) <= 1e-6:
        return True                       # transparent everywhere: it paints nothing
    return False


# ─── the measurement ──────────────────────────────────────────────────────────

def measure(flat, themes_dir=None):
    """[(theme, record)] with everything the gates need, per photo theme."""
    out = []
    for theme, body in photo_themes(flat):
        layers, photo, decls = painting_ruleLayers(body)
        if not layers or photo is None:
            out.append((theme, {"theme": theme, "photo": None, "why": "no photograph composed on .panel"}))
            continue
        tokens = tokens_of(flat, theme)
        grads = [t for k, t in layers if k == "gradient"]
        unreadable = [t for t in grads if eval_layer(t, tokens, PANEL_W / 2, 450.0) is None]
        flats = [t for t in grads if layer_is_flat(t, tokens)]
        photo_last = layers[-1][0] == "photo"
        sizes = [s.strip() for s in (decls.get("background-size") or "").split(",") if s.strip()]
        places = [s.strip() for s in (decls.get("background-position") or "").split(",") if s.strip()]
        cap = composite_at(layers, tokens, photo, CAPTION_Y, themes_dir)
        weak = composite_at(layers, tokens, photo, CAPTION_WEAKEST_Y, themes_dir)
        mid = composite_at(layers, tokens, photo, MIDDLE_Y, themes_dir)
        pcap = photo_band(photo, "caption", themes_dir)
        pmid = photo_band(photo, "middle", themes_dir)
        rec = {
            "theme": theme, "photo": photo, "layers": len(layers), "grads": len(grads),
            "unreadable": len(unreadable), "flat_grads": len(flats),
            "photo_last": photo_last, "sizes": sizes, "places": places,
            "cap_lum": None if cap is None else relative_luminance(cap),
            "cap_contrast": None if cap is None else contrast(INK, cap),
            "weak_lum": None if weak is None else relative_luminance(weak),
            "weak_contrast": None if weak is None else contrast(INK, weak),
            "mid_lum": None if mid is None else relative_luminance(mid),
            "mid_share": None if (mid is None or pmid is None or not mean8(pmid))
                         else mean8(mid) / mean8(pmid),
            "photo_cap_lum": None if pcap is None else relative_luminance(pcap),
            "photo_mid_lum": None if pmid is None else relative_luminance(pmid),
            "scrim": None,
        }
        t = tokens.get("--cine-scrim")
        if t:
            c = resolve_token(tokens, t)
            rec["scrim"] = None if c is None else c[3]
        out.append((theme, rec))
    return out


def gaps_of(rec):
    """The reasons THIS theme fails, or [] when it reads as a scene. Both colours."""
    why = []
    if rec.get("photo") is None:
        why.append(rec.get("why") or "no photograph composed on .panel")
        return why
    if rec["unreadable"]:
        why.append("%d gradient layer(s) this census cannot read" % rec["unreadable"])
    if not rec["grads"]:
        why.append("no gradient layer over the photograph at all")
    else:
        if not rec["photo_last"]:
            why.append("the photograph is NOT the last layer")
        if not rec["sizes"]:
            why.append("no background-size: one cover per layer is the contract")
        elif len(rec["sizes"]) != rec["layers"]:
            why.append("background-size has %d value(s) for %d layer(s)"
                       % (len(rec["sizes"]), rec["layers"]))
        elif any(s.strip().lower() != "cover" for s in rec["sizes"]):
            why.append("a background-size value is not 'cover': %s" % ",".join(rec["sizes"]))
        elif rec["places"] and len(rec["places"]) != rec["layers"]:
            why.append("background-position has %d value(s) for %d layer(s)"
                       % (len(rec["places"]), rec["layers"]))
    if rec["flat_grads"]:
        why.append("%d FLAT gradient layer(s): the photograph is washed everywhere,"
                   " not read as a scene" % rec["flat_grads"])
    if rec["cap_lum"] is None or rec["weak_lum"] is None:
        why.append("the caption-zone composite could not be measured")
    else:
        if rec["weak_contrast"] < CONTRAST_FLOOR:
            why.append("caption zone too bright at its weakest point: contrast %.2f < %.1f"
                       % (rec["weak_contrast"], CONTRAST_FLOOR))
        if rec["cap_contrast"] < CONTRAST_FLOOR:
            why.append("caption zone too bright at its centre: contrast %.2f < %.1f"
                       % (rec["cap_contrast"], CONTRAST_FLOOR))
    return why


def row(rec):
    if rec.get("photo") is None:
        return "  [GAP ] %-22s %s" % (rec["theme"], rec.get("why") or "no photo rule")
    def f(v, spec="%.4f"):
        return spec % v if v is not None else "n/a"
    return ("  [%s] %-22s layers=%d%-5s scrim=%-5s cap=%s(c=%s) weak=%s(c=%s)"
            " mid=%s mid_share=%s photoL cap=%s mid=%s"
            % ("GAP " if gaps_of(rec) else "ok  ", rec["theme"], rec["layers"],
               " FLAT" if rec["flat_grads"] else "",
               f(rec["scrim"], "%.2f"),
               f(rec["cap_lum"]), f(rec["cap_contrast"], "%.2f"),
               f(rec["weak_lum"]), f(rec["weak_contrast"], "%.2f"),
               f(rec["mid_lum"]), f(rec["mid_share"], "%.2f"),
               f(rec["photo_cap_lum"]), f(rec["photo_mid_lum"])))


def census(flat, say=print, themes_dir=None):
    """THE WHOLE MEASUREMENT against one parsed stylesheet. Returns (bad, total)."""
    measured = measure(flat, themes_dir)
    if not measured:
        say("photo-scrim-census: no theme composes a photograph on .panel")
        return [], 0
    say("photo-scrim-census -- %d theme(s) paint a photograph" % len(measured))
    bad = []
    for theme, rec in measured:
        for line in row(rec).split("\n"):
            say(line)
        why = gaps_of(rec)
        if why:
            bad.append((theme, "; ".join(why)))
    return bad, len(measured)


# ─── the controls: FOUR mutations, each on a COPY, each must go RED ────────────

def _read(path):
    with io.open(path, encoding="utf-8", errors="replace") as h:
        return h.read()


def _victim(flat):
    """The first photo theme whose painting rule this census can read."""
    for theme, rec in measure(flat):
        if rec.get("photo") and not gaps_of(rec):
            return theme
    return None


def _paint_body(flat, theme):
    body = None
    for b in blocks(flat, ":root[data-theme='%s'] .panel" % theme):
        if "url(" in b:
            body = b
    return body


def _mutate(flat, theme, image, sizes, places=None):
    """Rewrite the victim's PAINTING rule's image/size/position declarations."""
    body = _paint_body(flat, theme)
    if body is None:
        return None, None
    new_body = body
    for key, value in (("background-image", image), ("background-size", sizes),
                       ("background-position", places)):
        if value is None:
            continue
        m = re.search(r"(%s\s*:\s*)([^;]+)(;)" % key, new_body)
        if m:
            new_body = new_body[:m.start()] + m.group(1) + value + m.group(3) + new_body[m.end():]
        else:
            new_body = new_body.rstrip() + "\n  %s: %s;" % (key, value)
    return body, new_body


def caption_contrast(flat, theme, band):
    """The caption ink's contrast against the caption zone if the photo were `band`.

    Used by the M4 control to CHOOSE its victim by measurement, so the arm cannot be
    accused of picking a theme it was already sure about."""
    body = _paint_body(flat, theme)
    if body is None:
        return None
    layers, photo, _ = painting_ruleLayers(body)
    if not layers or photo is None:
        return None
    tokens = tokens_of(flat, theme)
    worst = None
    for py in (CAPTION_WEAKEST_Y, CAPTION_Y):
        cur = list(band)
        for kind, text in layers:
            if kind != "gradient":
                continue
            col = eval_layer(text, tokens, PANEL_W / 2.0, py)
            if col is None:
                return None
            a = col[3]
            cur = [col[0] * a + cur[0] * (1 - a),
                   col[1] * a + cur[1] * (1 - a),
                   col[2] * a + cur[2] * (1 - a)]
        c = contrast(INK, tuple(cur))
        worst = c if worst is None else min(worst, c)
    return worst

def neg_arm(say=print):
    """THE CONTROLS. A census that can only answer GREEN is not a gate.

    Four mutations, each applied to a COPY in a TemporaryDirectory, each of which
    must read RED for the theme it touched -- and the copy must ALSO not disturb
    the other 24:
      M1 FLATTEN     the painting rule back to the old flat wash (the E4 defect);
      M2 RAW PHOTO   every gradient stripped (the photograph fully exposed);
      M3 ZERO SCRIM  the theme's own --cine-scrim alpha taken to 0.0 -- the arm the
                     previous revision carried, kept so the battery's label holds;
      M4 BRIGHT      an intact composition over a photograph bright enough to beat
                     the caption ink (the E3 half).
    """
    css_path = os.path.join(THEMES, "cinematic.css")
    if not os.path.exists(css_path):
        say("NEG-ARM: no cinematic.css")
        return 1
    root = _read(css_path)
    flat = strip_comments(root)
    victim = _victim(flat)
    if victim is None:
        say("NEG-ARM: no photo theme passes -- the control is inert")
        return 1
    body = _paint_body(flat, victim)
    decls = decls_of(body)
    layers, photo, _ = painting_ruleLayers(body)
    say("NEG-ARM: victim=%s (the first GREEN photo theme in the file)" % victim)

    tmp = tempfile.mkdtemp(prefix="photo-scrim-neg-")
    try:
        os.makedirs(os.path.join(tmp, "backdrops"), exist_ok=True)
        for f in os.listdir(BACKDROPS):
            src = os.path.join(BACKDROPS, f)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(tmp, "backdrops", f))
        target = os.path.join(tmp, "cinematic.css")
        results = []

        # M1 -- the flat wash the owner saw.
        img = "linear-gradient(var(--cine-scrim), var(--cine-scrim)), url(backdrops/%s)" % photo
        old_b, new_b = _mutate(flat, victim, img, "cover, cover", "center, center")
        copy = flat.replace(old_b, new_b, 1)
        with io.open(target, "w", encoding="utf-8", newline="") as h:
            h.write(copy)
        bad, _ = census(copy, say=lambda _s: None, themes_dir=tmp)
        results.append(("M1 flat wash", [t for t, _ in bad] == [victim], [t for t, _ in bad]))

        # M2 -- the raw photograph.
        img = "url(backdrops/%s)" % photo
        old_b, new_b = _mutate(flat, victim, img, "cover", "center")
        copy = flat.replace(old_b, new_b, 1)
        with io.open(target, "w", encoding="utf-8", newline="") as h:
            h.write(copy)
        bad, _ = census(copy, say=lambda _s: None, themes_dir=tmp)
        results.append(("M2 raw photo", [t for t, _ in bad] == [victim], [t for t, _ in bad]))

        # M3 -- the zeroed scrim, the previous revision's own arm. The token is
        # per-theme, and only the themes that PAINT `var(--cine-scrim)` carry it into
        # their own rule -- the extras grade their photograph with literals, so the
        # mutation must pick a theme whose rule actually reads the token. MEASURED:
        # zeroing `cine-analog`'s token changed nothing (its rule never reads it), so
        # the arm was inert until the victim was chosen by the rule, not by order.
        scrim_victim = None
        for name, rec in measure(flat):
            if rec.get("photo") and not gaps_of(rec):
                b = _paint_body(flat, name) or ""
                if "var(--cine-scrim)" in b:
                    scrim_victim = name
                    break
        tok = tokens_of(flat, scrim_victim or "").get("--cine-scrim") or ""
        head = ":root[data-theme='%s']{" % (scrim_victim or "\x00")
        i = flat.find(head) if scrim_victim else -1
        if i < 0 or not tok:
            results.append(("M3 zeroed scrim", False, "no theme paints var(--cine-scrim)"))
        else:
            j = flat.find("}", i)
            seg2 = flat[i:j].replace(tok, _zero(tok), 1)
            copy = flat[:i] + seg2 + flat[j:]
            with io.open(target, "w", encoding="utf-8", newline="") as h:
                h.write(copy)
            bad, _ = census(copy, say=lambda _s: None, themes_dir=tmp)
            results.append(("M3 zeroed scrim", [t for t, _ in bad] == [scrim_victim],
                            [t for t, _ in bad]))

        # M4 -- a bright photograph under the SAME composition, the E3 half of the gate.
        # The victim is chosen BY MEASUREMENT, not by order: the theme whose caption zone
        # keeps the most light is the one a bright frame can actually beat. MEASURED over
        # a 238,238,238 frame, the weakest point of the zone falls to 2.56 (cine-ember,
        # whose own overlay is a warm pool) and 1.99 (cine-linen) -- both under the floor.
        bright = os.path.join(tmp, "backdrops", "neg-arm-bright.jpg")
        _write_bright(bright)
        ranked = []
        for name, rec in measure(flat):
            if rec.get("photo") and not gaps_of(rec):
                c = caption_contrast(flat, name, (238.0, 238.0, 238.0))
                if c is not None:
                    ranked.append((c, name))
        ranked.sort()
        if not ranked:
            results.append(("M4 bright photo", False, "no theme could be measured"))
        else:
            bright_victim = ranked[0][1]
            say("NEG-ARM M4 victim=%s (worst caption zone on a bright frame: %.2f)"
                % (bright_victim, ranked[0][0]))
            old_b = _paint_body(flat, bright_victim)
            _l, bp, _d = painting_ruleLayers(old_b)
            body2 = old_b.replace("url(backdrops/%s)" % bp,
                                  "url(backdrops/neg-arm-bright.jpg)", 1)
            copy = flat.replace(old_b, body2, 1)
            with io.open(target, "w", encoding="utf-8", newline="") as h:
                h.write(copy)
            bad, _ = census(copy, say=lambda _s: None, themes_dir=tmp)
            results.append(("M4 bright photo", [t for t, _ in bad] == [bright_victim],
                            [t for t, _ in bad]))

        ok = True
        for name, good, live in results:
            say("NEG-ARM %-16s RED=%-3s live_bad=%s"
                % (name, "yes" if good else "NO", live))
            ok = ok and good
        # THE CONTROL FOR THE CONTROL: the untouched copy must read the same GREEN.
        with io.open(target, "w", encoding="utf-8", newline="") as h:
            h.write(flat)
        bad, _ = census(flat, say=lambda _s: None)
        say("NEG-ARM copy untouched: %d bad (must equal the live %d)"
            % (len(bad), len(gaps_of(victim_rec(flat, victim)))))
        say("VERDICT: %s -- the census can say NO" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def victim_rec(flat, theme):
    for name, rec in measure(flat):
        if name == theme:
            return rec
    return {}


def _zero(rgba_text):
    m = re.search(r"\(([^)]*)\)", rgba_text)
    if not m:
        return rgba_text
    parts = [p.strip() for p in m.group(1).split(",")]
    if len(parts) < 4:
        parts.append("0.0")
    parts[3] = "0.0"
    return "rgba(" + ",".join(parts) + ")"


def _write_bright(path):
    """A photograph bright enough to beat the caption ink, for the M4 control."""
    try:
        from PIL import Image
        Image.new("RGB", (960, 540), (238, 238, 238)).save(path, "JPEG", quality=88)
    except Exception as exc:                                  # noqa: BLE001
        sys.stderr.write("NEG-ARM: could not write the bright photo: %s\n" % exc)


def main():
    css_path = os.path.join(THEMES, "cinematic.css")
    if not os.path.exists(css_path):
        print("photo-scrim-census: NO cinematic.css")
        return 1
    flat = strip_comments(_read(css_path))
    bad, total = census(flat)
    if not total:
        return 0
    say = print
    say("")
    say("PHOTO-SCRIM %d/%d theme(s) read as a scene; %d competing"
        % (total - len(bad), total, len(bad)))
    for theme, why in bad:
        say("    - %s: %s" % (theme, why))
    if bad:
        say("VERDICT: FAIL -- these photographs do not read as a scene behind the caption")
        return 1
    say("VERDICT: PASS -- every photograph is a scene behind the caption")
    return 0


if __name__ == "__main__":
    # --neg-arm is the control: four mutations on copies, each must read RED. A
    # census that cannot say NO is not a gate -- the sibling light census shipped a
    # white theme for months behind its green exactly because it had none.
    if "--neg-arm" in sys.argv:
        sys.exit(neg_arm())
    sys.exit(main())
