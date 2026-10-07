"""ocr-bench-02c.py — MEASURE the two levers that decide shipping cost.

Lever 1: frame AREA.  OCR a full 1920x1080 frame vs the same frame cropped to a
single text region (a HUD corner / subtitle band).  RapidOCR's detector cost
scales with the pixels it must scan, and the shipped design can OCR one region
at a time instead of the whole screen.

Lever 2: the cheap TRIGGER.  On a 160x90 grayscale thumbnail, how long does a
change test take (abs-diff + mean), and does it actually fire when text appears
and stay quiet when nothing changes?  A synthetic 1-second text flash is used,
which is exactly what the brief asks about ("text that appears for a second").

Writes _main/ocr-bench-02c.json.  No downloads, no window, no screen capture.
"""
import json
import os
import time
import traceback

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ocr-bench-02c.json")
FRAME = os.path.join(HERE, "ocr-frames", "00-clean_hud.png")

res = {"frame": FRAME, "levers": {}}


def timed(fn, repeats=3):
    lat = []
    out = None
    for _ in range(repeats):
        t = time.perf_counter()
        out = fn()
        lat.append(time.perf_counter() - t)
    return out, lat


# ---------------- Lever 1: area -----------------
from rapidocr import RapidOCR  # noqa: E402

engine = RapidOCR()
png = Image.open(FRAME).convert("RGB")

regions = {
    "bottom_left_chat_640x140": (0, 1080 - 230, 640, 1080 - 90),
    "subtitle_band_1920x120": (0, 1080 - 350, 1920, 1080 - 270),
    "full_1920x1080": (0, 0, 1920, 1080),
}
res["levers"]["area"] = []
try:
    for name, box in regions.items():
        crop = np.array(png.crop(box))
        out, lat = timed(lambda c=crop: engine(c), repeats=2)
        texts = list(out.txts or []) if out is not None else []
        res["levers"]["area"].append({
            "region": name, "box": list(box), "shape": list(crop.shape),
            "latency_s": [round(x, 3) for x in lat],
            "latency_min_s": round(min(lat), 3),
            "n_boxes": len(texts),
            "texts": texts,
        })
        print("AREA", name, round(min(lat), 3), len(texts), flush=True)
except Exception:
    res["levers"]["area_error"] = traceback.format_exc()
    print("AREA ERROR", traceback.format_exc()[-400:], flush=True)

# ---------------- Lever 2: change trigger -----------------
res["levers"]["trigger"] = {}
try:
    # a 1-second text flash: subtitle appears on frame k, gone on frame k+N
    rng = np.random.default_rng(3)
    base = png.resize((160, 90), Image.BILINEAR).convert("L")
    # A 3 s clip at 30 fps.  The HUD text changes (a spray-count that ticks) on
    # every frame the scene is alive, and a big toast appears for 0.8 s.
    frames = []
    for i in range(90):  # 3 s at 30 fps
        f = base.copy()
        d = ImageDraw.Draw(f)
        d.rectangle([2, 2, 40, 12], fill=(i * 3) % 256)  # moving HUD element
        if 45 <= i < 69:  # the toast is on screen for 24 frames = 0.8 s
            d.rectangle([20, 60, 140, 80], fill=255)
            d.text((22, 62), "ELE TA DE AWP", fill=0)
        frames.append(np.asarray(f, dtype=np.int16))

    def hash8(a):
        return a[::4, ::4]  # 40x23 thumbnail, still int16 view

    def d_mean(a, b):
        return float(np.abs(a - b).mean())

    def d_hash(a, b):
        return int(np.abs(hash8(a) - hash8(b)).mean())

    def d_bits(a, b):
        ah = hash8(a) > hash8(a).mean()
        bh = hash8(b) > hash8(b).mean()
        return int(np.count_nonzero(ah != bh))

    for label, fn in (("mean_abs_160x90", d_mean), ("mean_abs_40x23", d_hash), ("dhash_bits_40x23", d_bits)):
        t = time.perf_counter()
        series = [fn(frames[i - 1], frames[i]) for i in range(1, len(frames))]
        dt = (time.perf_counter() - t) / max(1, len(series))
        # series[k] = |frame k+1 - frame k|.  The subtitle is ON in frames 45..59,
        # so onset = series[44], offset = series[59]; everything else is quiet.
        quiet = [series[i] for i in range(len(series)) if i not in (44, 59)]
        res["levers"]["trigger"][label] = {
            "per_frame_s": round(dt, 6),
            "quiet_max": max(quiet) if quiet else None,
            "onset": series[44] if len(series) > 44 else None,
            "offset": series[59] if len(series) > 59 else None,
            "nonzero_quiet_count": sum(1 for q in quiet if q > 0),
            "quiet_count": len(quiet),
            "separable": (max(quiet) < series[44]) if quiet and len(series) > 44 else None,
        }
        print("TRIGGER", label, res["levers"]["trigger"][label], flush=True)
except Exception:
    res["levers"]["trigger_error"] = traceback.format_exc()
    print("TRIGGER ERROR", traceback.format_exc()[-400:], flush=True)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(res, fh, ensure_ascii=False, indent=2)
print("WROTE", OUT)
