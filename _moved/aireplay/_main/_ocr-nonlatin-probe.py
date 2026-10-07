import json
import numpy as np
from PIL import Image
from rapidocr import RapidOCR
e = RapidOCR()
gt = json.load(open(r"H:\aireplay\_main\ocr-frames\_ground_truth.json", encoding="utf-8"))
out = {}
for name in ("06-subtitle_cjk.png", "07-subtitle_cyrillic.png"):
    arr = np.array(Image.open(r"H:\aireplay\_main\ocr-frames" + "\\" + name).convert("RGB"))
    r = e(arr)
    out[name] = {"n": len(r.txts or []), "texts": list(r.txts or []), "scores": [round(float(s),4) for s in (r.scores or [])], "gt_subtitle": gt[name][-1]}
    print(name, json.dumps(out[name], ensure_ascii=False))
json.dump(out, open(r"H:\aireplay\_main\ocr-nonlatin-02.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
