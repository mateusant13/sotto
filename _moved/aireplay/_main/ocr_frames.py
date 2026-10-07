"""ocr_frames.py — shared synthetic game-frame generator for the OCR lane.

Frames deliberately imitate the four things the product must read off a screen:
HUD (corner, stroked), PT-BR objective, chat lines (low contrast), an error
toast, and a centred subtitle on a translucent bar.  Background is synthetic
"game graphics" (gradient + noise + blobs + bright geometry) so the OCR engine
faces real clutter, not a blank page.  No screen capture, no downloads.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080


def font(size, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf", "tahoma.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def game_background(rng, busy=True):
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    sky = np.concatenate([(60 + 90 * y), (90 + 70 * y), (140 + 60 * y)], axis=1)
    bg = np.repeat(sky[:, None, :], W, axis=1)
    noise = rng.normal(0, 26, size=(H, W, 3)).astype(np.float32)
    img = np.clip(bg + noise, 0, 255).astype(np.uint8)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    if busy:
        for _ in range(14):
            x0 = int(rng.integers(-300, W))
            y0 = int(rng.integers(H // 3, H))
            d.polygon([(x0, y0), (x0 + 420, y0 - 180), (x0 + 700, y0), (x0 + 200, y0 + 90)],
                      fill=(int(rng.integers(10, 90)), int(rng.integers(20, 120)), int(rng.integers(10, 70))))
        for _ in range(600):
            x = int(rng.integers(0, W)); yy = int(rng.integers(0, H)); s = int(rng.integers(2, 11))
            v = int(rng.integers(120, 255))
            d.rectangle([x, yy, x + s, yy + s], fill=(v, v, v))
    return im


def draw_hud(im, font_scale=1.0, contrast="normal", latin="latin"):
    d = ImageDraw.Draw(im, "RGBA")
    f_hud = font(int(28 * font_scale), bold=True)
    f_small = font(int(22 * font_scale), bold=False)
    f_sub = font(int(40 * font_scale), bold=True)
    gt = []

    txt = "HP 87/100   AMMO 24/90"
    d.text((40, 30), txt, font=f_hud, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 200))
    gt.append(txt)

    txt = "OBJETIVO: PLANTAR A BOMBA"
    w = d.textlength(txt, font=f_hud)
    d.text((W - 40 - w, 30), txt, font=f_hud, fill=(255, 220, 60, 255), stroke_width=2, stroke_fill=(0, 0, 0, 220))
    gt.append(txt)

    fill = (215, 215, 215, 255) if contrast != "low" else (150, 150, 150, 255)
    for i, t in enumerate(["[Joao] ele ta de awp", "[voce] recuando B", "[Maria] gg wp"]):
        d.text((40, H - 200 + i * 30), t, font=f_small, fill=fill)
        gt.append(t)

    txt = "ERRO 0x80070005: ACESSO NEGADO"
    w = d.textlength(txt, font=f_small)
    d.text((W - 40 - w, H - 60), txt, font=f_small, fill=(255, 120, 120, 255))
    gt.append(txt)

    if latin == "latin":
        sub = "ELE TÁ DE AWP, NÃO SOBE A RAMP"
    elif latin == "cjk":
        sub = "敵が丘の上にいる"
    else:
        sub = "Он на холме, не поднимайся"
    w = d.textlength(sub, font=f_sub)
    x0 = (W - w) / 2
    y0 = H - 330
    d.rectangle([x0 - 18, y0 - 10, x0 + w + 18, y0 + 52], fill=(0, 0, 0, 170))
    d.text((x0, y0), sub, font=f_sub, fill=(255, 255, 255, 255))
    gt.append(sub)
    return gt


ARMS = [
    ("clean_hud", dict(font_scale=1.0, contrast="normal", latin="latin"), 0.0, 1.0),
    ("low_contrast_chat", dict(font_scale=1.0, contrast="low", latin="latin"), 0.0, 1.0),
    ("small_text_0.7", dict(font_scale=0.7, contrast="normal", latin="latin"), 0.0, 1.0),
    ("motion_blur_2px", dict(font_scale=1.0, contrast="normal", latin="latin"), 2.0, 1.0),
    ("motion_blur_4px", dict(font_scale=1.0, contrast="normal", latin="latin"), 4.0, 1.0),
    ("subtitle_fade_50pct", dict(font_scale=1.0, contrast="normal", latin="latin"), 0.0, 0.5),
    ("subtitle_cjk", dict(font_scale=1.0, contrast="normal", latin="cjk"), 0.0, 1.0),
    ("subtitle_cyrillic", dict(font_scale=1.0, contrast="normal", latin="other"), 0.0, 1.0),
]


def build(arm_index=0, seed=7):
    name, kw, blur_radius, fade = ARMS[arm_index]
    rng = np.random.default_rng(seed + arm_index * 11)
    im = game_background(rng)
    gt = draw_hud(im, **kw)
    if fade != 1.0:
        im = Image.blend(im, Image.new("RGB", im.size, (0, 0, 0)), 1.0 - fade)
    if blur_radius:
        im = im.filter(ImageFilter.GaussianBlur(blur_radius))
    return name, im, gt


def frame_saving_loop():
    import os, sys
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr-frames")
    os.makedirs(out_dir, exist_ok=True)
    for p in os.listdir(out_dir):
        if p.endswith(".png") or p.endswith(".json"):
            os.remove(os.path.join(out_dir, p))
    import json
    index = {}
    for i, (name, _, _, _) in enumerate(ARMS):
        _n, im, gt = build(i)
        im.save(os.path.join(out_dir, f"{i:02d}-{name}.png"))
        index[f"{i:02d}-{name}.png"] = gt
        print("WROTE", name, flush=True)
    with open(os.path.join(out_dir, "_ground_truth.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)
    print("GT", out_dir)


if __name__ == "__main__":
    frame_saving_loop()
