"""ocr-bench-02b.py — MEASURE RapidOCR CPU vs CUDA on ONE synthetic frame.

Reads H:\\aireplay\\_main\\ocr-frames\\00-clean_hud.png.
Writes _main/ocr-bench-02b.json
Overrides are passed the documented way (a YAML params file), because
`RapidOCR(**kwargs)` rejects dotted keys.
"""
import json
import os
import time
import traceback

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ocr-bench-02b.json")
FRAME = os.path.join(HERE, "ocr-frames", "00-clean_hud.png")
YAML = os.path.join(HERE, "_rapidocr-override.yaml")

res = {"frame": FRAME, "arms": []}
arr = np.array(Image.open(FRAME).convert("RGB"))
res["frame_shape"] = list(arr.shape)


def one(label, yaml_text, repeats=2):
    arm = {"label": label, "yaml": yaml_text}
    try:
        from rapidocr import RapidOCR
        kwargs = {}
        if yaml_text:
            with open(YAML, "w", encoding="utf-8") as fh:
                fh.write(yaml_text)
            kwargs["params"] = YAML
        t0 = time.perf_counter()
        engine = RapidOCR(**kwargs)
        arm["init_s"] = round(time.perf_counter() - t0, 2)
        arm["cfg"] = engine.cfg.to_dict() if hasattr(engine.cfg, "to_dict") else str(engine.cfg)
        lat = []
        last = None
        for _ in range(repeats):
            t = time.perf_counter()
            out = engine(arr)
            lat.append(round(time.perf_counter() - t, 3))
            last = out
        arm["latency_s"] = lat
        arm["latency_min_s"] = min(lat)
        arm["elapse"] = {k: (round(float(v), 4) if isinstance(v, (int, float)) else str(v))
                         for k, v in (last.elapse or {}).items()} if last is not None else None
        arm["texts"] = list(last.txts or []) if last is not None else []
        arm["scores"] = [round(float(s), 4) for s in (last.scores or [])] if last is not None else []
        arm["n_boxes"] = len(arm["texts"])
    except Exception:
        arm["error"] = traceback.format_exc()
    res["arms"].append(arm)
    print(json.dumps({k: v for k, v in arm.items() if k not in ("texts", "cfg")}, ensure_ascii=False), flush=True)


one("cpu_default", "", repeats=2)

try:
    import onnxruntime as ort
    res["ort_providers_available"] = ort.get_available_providers()
    res["ort_version"] = ort.__version__
except Exception:
    res["ort_providers_available"] = ["IMPORT-FAILED: " + traceback.format_exc()]

if "CUDAExecutionProvider" in (res.get("ort_providers_available") or []):
    one("cuda", "EngineConfig:\n  onnxruntime:\n    use_cuda: true\n", repeats=2)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(res, fh, ensure_ascii=False, indent=2)
print("WROTE", OUT)
