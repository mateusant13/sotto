import json, time
import numpy as np
from PIL import Image, ImageDraw
png = Image.open(r"H:\aireplay\_main\ocr-frames\00-clean_hud.png").convert("RGB")
base = png.resize((160, 90), Image.BILINEAR).convert("L")
frames = []
for i in range(90):
    f = base.copy(); d = ImageDraw.Draw(f)
    d.rectangle([2, 2, 40, 12], fill=(i * 3) % 256)
    if 45 <= i < 69:
        d.rectangle([20, 60, 140, 80], fill=255); d.text((22, 62), "ELE TA DE AWP", fill=0)
    frames.append(np.asarray(f, dtype=np.int16))
def hash8(a): return a[::4, ::4]
def d_mean(a,b): return float(np.abs(a-b).mean())
def d_hash(a,b): return float(np.abs(hash8(a)-hash8(b)).mean())
def d_bits(a,b):
    ah = hash8(a) > hash8(a).mean(); bh = hash8(b) > hash8(b).mean()
    return int(np.count_nonzero(ah != bh))
out={}
for label, fn in (("mean_abs_160x90", d_mean), ("mean_abs_40x23", d_hash), ("dhash_bits_40x23", d_bits)):
    t=time.perf_counter(); s=[fn(frames[i-1],frames[i]) for i in range(1,len(frames))]
    dt=(time.perf_counter()-t)/len(s)
    s=np.array(s)
    quiet_mask = ~((44 <= np.arange(len(s))) & (np.arange(len(s)) <= 68))
    out[label]={"per_frame_s":round(dt,6),"quiet_max":float(s[quiet_mask].max()),
                "onset_idx":44,"onset_value":float(s[44]),"offset_idx":68,"offset_value":float(s[68]),
                "first_at_or_above_quiet_max":int(np.argmax(s>=s[quiet_mask].max())),
                "quiet_mean":float(s[quiet_mask].mean()),"quiet_std":float(s[quiet_mask].std()),
                "n_above_quiet_max":int(np.count_nonzero(s>=s[quiet_mask].max()))}
    print(label, json.dumps(out[label]))
json.dump(out, open(r"H:\aireplay\_main\ocr-trigger-02c.json","w",encoding="utf-8"), indent=2)
