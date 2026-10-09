import sys, wave, numpy as np
sys.path.insert(0, r"H:\sotto\_moved\aireplay\src")
from asr.segment import segments_silence
from asr.level import events_from_array

w = wave.open(r"H:\sotto\_moved\aireplay\_main\_hl07-synth-16k.wav","rb")
n = w.getnframes(); sr = w.getframerate()
x = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32)/32768.0
print(f"sr={sr} n={n} dur_s={n/sr:.2f}")
segs = segments_silence(x, sample_rate=sr)
print(f"segments={len(segs)}")
if segs:
    d=[b-a for a,b in segs]
    print(f"seg_min={min(d):.2f} seg_med={sorted(d)[len(d)//2]:.2f} seg_max={max(d):.2f} seg_total={sum(d):.2f}")
    print(f"coverage={100*sum(d)/(n/sr):.1f}% of the clip")
ev = events_from_array(x, sample_rate=sr)
p = np.array([e["p"] for e in ev]); r=np.array([e["r"] for e in ev])
print(f"level_events={len(ev)} hz={len(ev)/(n/sr):.2f}")
print(f"peak: min={p.min():.4f} med={np.median(p):.4f} max={p.max():.4f}")
print(f"rms : min={r.min():.5f} med={np.median(r):.5f} max={r.max():.5f}")
# how many distinct "loud" seconds would a naive peak highlighter fire on?
thr = float(np.percentile(p, 95))
hot = p >= thr
print(f"p95_thr={thr:.4f} windows_at_or_above={hot.sum()}/{len(p)} ({100*hot.mean():.1f}%)")
