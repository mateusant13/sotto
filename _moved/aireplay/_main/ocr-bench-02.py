"""ocr-bench-02.py — MEASURE RapidOCR on synthetic game-like frames.

Writes: _main/ocr-bench-02.json
No downloads, no window, no screen capture. Frames are generated in memory
with synthetic game graphics behind the text (noise + gradients + shapes).
"""
import json
import os
import sys
import time
import traceback

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr-bench-02.json")

W, H = 1920, 1080


def font(size, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf", "tahoma.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def game_background(rng, busy=True):
    """Cheap synthetic 'game graphics': vertical gradient + heavy noise + blobs."""
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    sky = np.concatenate([
        (60 + 90 * y), (90 + 70 * y), (140 + 60 * y)
    ], axis=1)  # (H,3)
    bg = np.repeat(sky[:, None, :], W, axis=1)  # (H,W,3)
    noise = rng.normal(0, 26, size=(H, W, 3)).astype(np.float32)
    img = np.clip(bg + noise, 0, 255).astype(np.uint8)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    if busy:
        # fake scenery: dark hills, bright polygons, small geometry detail
        for i in range(14):
            x0 = rng.integers(-300, W)
            y0 = rng.integers(H // 3, H)
            d.polygon([(x0, y0), (x0 + 420, y0 - 180), (x0 + 700, y0), (x0 + 200, y0 + 90)],
                      fill=(int(rng.integers(10, 90)), int(rng.integers(20, 120)), int(rng.integers(10, 70))))
        for i in range(600):
            x = int(rng.integers(0, W)); yy = int(rng.integers(0, H)); s = int(rng.integers(2, 11))
            v = int(rng.integers(120, 255))
            d.rectangle([x, yy, x + s, yy + s], fill=(v, v, v))
    return im


def draw_hud(im, font_scale=1.0, contrast="normal"):
    """HUD in the four corners + a centred subtitle bar. Returns list of ground-truth strings."""
    d = ImageDraw.Draw(im, "RGBA")
    f_hud = font(int(28 * font_scale), bold=True)
    f_small = font(int(22 * font_scale), bold=False)
    f_sub = font(int(40 * font_scale), bold=True)
    gt = []

    # --- top-left: health/ammo HUD, white with faint shadow
    txt = "HP 87/100   AMMO 24/90"
    d.text((40, 30), txt, font=f_hud, fill=(255, 255, 255, 255),
           stroke_width=2, stroke_fill=(0, 0, 0, 200))
    gt.append(txt)

    # --- top-right: PT-BR objective, yellow
    txt = "OBJETIVO: PLANTAR A BOMBA"
    w = d.textlength(txt, font=f_hud)
    d.text((W - 40 - w, 30), txt, font=f_hud, fill=(255, 220, 60, 255),
           stroke_width=2, stroke_fill=(0, 0, 0, 220))
    gt.append(txt)

    # --- bottom-left: chat, low contrast (the hard case)
    fill = (215, 215, 215, 255) if contrast == "normal" else (150, 150, 150, 255)
    lines = ["[Joao] ele ta de awp", "[voce] recuando B", "[Maria] gg wp"]
    for i, t in enumerate(lines):
        d.text((40, H - 200 + i * 30), t, font=f_small, fill=fill)
        gt.append(t)

    # --- bottom-right: minimap label + error toast
    txt = "ERRO 0x80070005: ACESSO NEGADO"
    w = d.textlength(txt, font=f_small)
    d.text((W - 40 - w, H - 60), txt, font=f_small, fill=(255, 120, 120, 255))
    gt.append(txt)

    # --- centre-bottom: subtitle on a translucent bar (the fade case handled elsewhere)
    txt = "ELE TÁ DE AWP, NÃO SOBE A RAMP"
    w = d.textlength(txt, font=f_sub)
    x0 = (W - w) / 2
    y0 = H - 330
    d.rectangle([x0 - 18, y0 - 10, x0 + w + 18, y0 + 52], fill=(0, 0, 0, 170))
    d.text((x0, y0), txt, font=f_sub, fill=(255, 255, 255, 255))
    gt.append(txt)
    return gt


def blur(im, radius):
    from PIL import ImageFilter
    return im.filter(ImageFilter.GaussianBlur(radius))


def main():
    result = {"what": "RapidOCR on synthetic game-like frames", "frames": [], "errors": []}
    try:
        from rapidocr import RapidOCR
    except Exception:
        result["errors"].append("import rapidocr: " + traceback.format_exc())
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
        print(json.dumps(result, ensure_ascii=False))
        return

    t0 = time.perf_counter()
    engine = RapidOCR()
    result["engine_init_s"] = round(time.perf_counter() - t0, 2)
    try:
        result["params"] = {k: str(v) for k, v in engine.cfg.__dict__.items()} if hasattr(engine, "cfg") else {}
    except Exception:
        pass

    rng = np.random.default_rng(7)

    arms = [
        ("clean_hud", dict(font_scale=1.0, contrast="normal"), 0.0),
        ("low_contrast_chat", dict(font_scale=1.0, contrast="low"), 0.0),
        ("small_text_0.7", dict(font_scale=0.7, contrast="normal"), 0.0),
        ("motion_blur_2px", dict(font_scale=1.0, contrast="normal"), 2.0),
        ("motion_blur_4px", dict(font_scale=1.0, contrast="normal"), 4.0),
        ("subtitle_fade_50pct", dict(font_scale=1.0, contrast="normal"), 0.0),
    ]

    for name, kw, blur_radius in arms:
        frame_res = {"arm": name, "blur_px": blur_radius}
        try:
            im = game_background(rng)
            gt = draw_hud(im, **kw)
            if name == "subtitle_fade_50pct":
                im = Image.blend(im, Image.new("RGB", im.size, (0, 0, 0)), 0.5)
            if blur_radius:
                im = blur(im, blur_radius)
            arr = np.array(im)
            frame_res["shape"] = list(arr.shape)

            times = []
            for _ in range(1):
                t = time.perf_counter()
                out = engine(arr)
                times.append(time.perf_counter() - t)
            frame_res["latency_s"] = [round(x, 3) for x in times]
            frame_res["latency_min_s"] = round(min(times), 3)

            boxes, texts, scores = [], [], []
            if out is not None and getattr(out, "boxes", None) is not None:
                for box, tx, sc in zip(out.boxes, out.txts, out.scores):
                    boxes.append([[int(v) for v in pt] for pt in box])
                    texts.append(tx)
                    scores.append(round(float(sc), 4))
            frame_res["n_boxes"] = len(texts)
            frame_res["texts"] = texts
            frame_res["scores"] = scores
            frame_res["boxes"] = boxes
            frame_res["ground_truth"] = gt
            hit = sum(1 for t in gt if any(t.lower() == x.lower().strip() for x in texts))
            frame_res["exact_gt_hits"] = f"{hit}/{len(gt)}"
        except Exception:
            frame_res["error"] = traceback.format_exc()
        result["frames"].append(frame_res)
        print("ARM", name, "->", frame_res.get("exact_gt_hits"), frame_res.get("latency_min_s"),
              "boxes=", frame_res.get("n_boxes"), flush=True)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print("WROTE", OUT)


main()
