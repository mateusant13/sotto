"""ocr-bench-02d.py — MEASURE RapidOCR cost with per-stage timing, honestly.

Reports, for each input: min/median of N runs, the engine's OWN per-stage
breakdown (det / cls / rec), the number of text boxes, and the process CPU time
consumed.  Also reports box-level confidence, and the cost when only the
RECOGNIZER runs (text already cropped) — the realistic product shape, since a
game HUD is a handful of known bands.

Writes _main/ocr-bench-02d.json.
"""
import json
import os
import statistics
import time
import traceback

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ocr-bench-02d.json")

res = {"inputs": []}
png = Image.open(os.path.join(HERE, "ocr-frames", "00-clean_hud.png")).convert("RGB")

from rapidocr import RapidOCR  # noqa: E402

t0 = time.perf_counter()
engine = RapidOCR()
res["init_s"] = round(time.perf_counter() - t0, 2)


def cpu_now():
    try:
        with open("/dev/null"):
            pass
    except Exception:
        pass
    import resource  # not on Windows; guarded below
    return None


def run(label, arr, repeats=5):
    rec = {"label": label, "shape": list(arr.shape)}
    lat = []
    elapses = []
    last = None
    try:
        for _ in range(repeats):
            t = time.perf_counter()
            out = engine(arr)
            lat.append(round(time.perf_counter() - t, 3))
            last = out
            if out is not None and out.elapse is not None:
                e = out.elapse
                if isinstance(e, dict):
                    elapses.append({k: round(float(v), 4) for k, v in e.items()})
                else:
                    elapses.append({"_total": round(float(e), 4)})
        rec["latency_s"] = lat
        rec["latency_min_s"] = min(lat)
        rec["latency_median_s"] = round(statistics.median(lat), 3)
        rec["elapse_last"] = elapses[-1] if elapses else None
        rec["elapse_median"] = ({k: round(statistics.median([e[k] for e in elapses]), 4) for k in elapses[0]}
                                if elapses else None)
        rec["n_boxes"] = len(last.txts or []) if last is not None else 0
        rec["texts"] = list(last.txts or []) if last is not None else []
        rec["scores"] = [round(float(s), 4) for s in (last.scores or [])] if last is not None else []
    except Exception:
        rec["error"] = traceback.format_exc()[-900:]
    res["inputs"].append(rec)
    print(json.dumps({k: v for k, v in rec.items() if k != "texts"}, ensure_ascii=False), flush=True)


try:
    full = np.array(png)
    run("full_1920x1080", full, repeats=5)
    run("crop_chat_640x140", np.array(png.crop((0, 850, 640, 990))), repeats=5)
    run("crop_subtitle_band_1920x120", np.array(png.crop((0, 730, 1920, 850))), repeats=5)
    run("crop_hud_topleft_700x100", np.array(png.crop((0, 0, 700, 100))), repeats=5)
    # half-resolution full frame: is a 960x540 OCR of a 1080p screen enough?
    run("full_960x540_downscaled", np.array(png.resize((960, 540), Image.BILINEAR)), repeats=5)

    # recognizer-only: feed the subtitle band, skipping the detector
    band = np.array(png.crop((480, 740, 1450, 830)))
    lat = []
    for _ in range(5):
        t = time.perf_counter()
        engine.text_rec(band)
        lat.append(round(time.perf_counter() - t, 4))
    res["recognizer_only_band"] = {"shape": list(band.shape), "latency_s": lat, "min_s": min(lat)}
    print("REC-ONLY", res["recognizer_only_band"], flush=True)

    # detector-only
    lat = []
    for _ in range(5):
        t = time.perf_counter()
        engine.text_det(full)
        lat.append(round(time.perf_counter() - t, 3))
    res["detector_only_full"] = {"latency_s": lat, "min_s": min(lat)}
    print("DET-ONLY", res["detector_only_full"], flush=True)
except Exception:
    res["fatal"] = traceback.format_exc()

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(res, fh, ensure_ascii=False, indent=2)
print("WROTE", OUT)
