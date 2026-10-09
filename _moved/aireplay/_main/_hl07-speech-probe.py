import sys, wave, numpy as np
sys.path.insert(0, r"H:\sotto\_moved\aireplay\src")
from asr.segment import segments_silence
from asr.level import events_from_array

path=r"H:\sotto\_main\_redux-long\plain-3600s.wav"
w=wave.open(path,"rb"); sr=w.getframerate(); n=w.getnframes()
w.setpos(int(900*sr)); x=np.frombuffer(w.readframes(int(120*sr)),dtype="<i2").astype(np.float32)/32768.0
dur=len(x)/sr
print(f"SLICE=[900,1020) sr={sr} dur={dur:.2f}s")

segs=segments_silence(x,sample_rate=sr)
d=[b-a for a,b in segs]
print(f"A) segments={len(segs)} min={min(d):.2f} med={sorted(d)[len(d)//2]:.2f} max={max(d):.2f}")
print(f"   speech_coverage={100*sum(d)/dur:.1f}%  gaps={len(d)+1}")

ev=events_from_array(x,sample_rate=sr)
p=np.array([e["p"] for e in ev]); r=np.array([e["r"] for e in ev])
print(f"B) level_events={len(ev)} hz={len(ev)/dur:.2f}")
print(f"   peak p05={np.percentile(p,5):.4f} med={np.median(p):.4f} p95={np.percentile(p,95):.4f} max={p.max():.4f}")
print(f"   peak dynamic range max/med = {p.max()/max(np.median(p),1e-9):.2f}x")
thr=np.percentile(p,95)
print(f"C) NAIVE PEAK RULE (fire on windows >= p95={thr:.4f}): {100*(p>=thr).mean():.1f}% of all windows selected")
print(f"   -> {int((p>=thr).sum())*0.1:.1f} s of 'highlights' from a {dur:.0f} s clip")

# gap structure between speech segments -> what a pre-roll must span
gaps=[]
prev=segs[0][1] if segs else 0
for a,b in segs[1:]:
    gaps.append(a-prev); prev=b
if gaps:
    g=np.array(gaps)
    print(f"D) inter-segment gaps n={len(g)} med={np.median(g):.2f}s p90={np.percentile(g,90):.2f}s max={g.max():.2f}s")
    for L in (1.0,2.0,3.0,5.0):
        print(f"   gaps <= {L}s: {100*(g<=L).mean():.1f}%  (a {L}s pre-roll+tail would bridge them)")
else:
    print("D) no gaps measurable (0 or 1 segments)")
