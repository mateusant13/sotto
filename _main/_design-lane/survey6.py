import numpy as np
from PIL import Image
from collections import Counter
def hx(c): return '#%02X%02X%02X' % (int(round(c[0])), int(round(c[1])), int(round(c[2])))
RAMP = ' .:-=+*#%@'
for i in range(1, 6):
    a = np.array(Image.open(r'H:\sotto\docs\design\incoming\design-%d.png' % i).convert('RGB')).astype(np.int16)
    h, w, _ = a.shape
    lum = a.mean(axis=2); sat = a.max(axis=2)-a.min(axis=2)
    print('=' * 100); print('design-%d' % i)
    for (nm, x0, x1) in (('LEFT x0-836', 0, 836), ('RIGHT x836-1672', 836, 1672)):
        reg = a[:, x0:x1]; rl = lum[:, x0:x1]; rs = sat[:, x0:x1]
        fam = {
            'near-black (lum<40,sat<18)': (rl < 40) & (rs < 18),
            'dark warm (lum<40,sat>=18)': (rl < 40) & (rs >= 18),
            'mid grey (40-100,sat<18)': (rl >= 40) & (rl < 100) & (rs < 18),
            'mid colour (40-100,sat>=18)': (rl >= 40) & (rl < 100) & (rs >= 18),
            'light grey (>=100,sat<18)': (rl >= 100) & (rs < 18),
            'light colour (>=100,sat>=18)': (rl >= 100) & (rs >= 18),
        }
        tot = rl.size
        s = '   '.join('%s=%.1f%%' % (k.split(' ')[0], 100.0*v.sum()/tot) for k, v in fam.items())
        print('  %s : %s' % (nm, s))
        for k, m in fam.items():
            if m.sum() > 2000 and 'lum<40' not in k:
                c = Counter(hx((v//8)*8) for v in reg[m])
                print('      %-32s top: %s' % (k, ', '.join('%s:%d' % (kk, nn) for kk, nn in c.most_common(4))))
    # ASCII of the four densest left-half blocks
    left = a[:, :900]; ll = left.mean(axis=2)
    T = 8; gh, gw = h//T, 900//T
    G = ll[:gh*T, :gw*T].reshape(gh, T, gw, T).mean(axis=(1,3))
    thr = np.percentile(G, 97)
    seen = np.zeros_like(G, bool); boxes = []
    for r in range(gh):
        for c in range(gw):
            if G[r, c] >= thr and not seen[r, c]:
                st=[(r,c)]; seen[r,c]=True; mem=[]
                while st:
                    rr,cc = st.pop(); mem.append((rr,cc))
                    for dr in (-1,0,1):
                        for dc in (-1,0,1):
                            nr,nc = rr+dr, cc+dc
                            if 0<=nr<gh and 0<=nc<gw and not seen[nr,nc] and G[nr,nc]>=thr:
                                seen[nr,nc]=True; st.append((nr,nc))
                if len(mem) >= 10:
                    rs=[m[0] for m in mem]; cs=[m[1] for m in mem]
                    boxes.append((min(rs)*T, max(rs)*T+T, min(cs)*T, max(cs)*T+T, len(mem)))
    boxes.sort(key=lambda b: -b[4])
    print('  LEFT-half graphic blocks (top 4 by density):')
    for b in boxes[:4]:
        print('     y %d..%d x %d..%d tiles=%d' % b)
    if boxes:
        b = boxes[0]
        y0, y1, x0, x1 = b[0], b[1], b[2], b[3]
        cw, ch = 118, 40
        im = Image.fromarray(ll[max(0,y0-6):y1+6, max(0,x0-6):x1+6].astype(np.uint8)).resize((cw, ch), Image.BOX)
        m = np.array(im).astype(np.float32)
        lo, hi = m.min(), max(m.max(), 1)
        n = np.clip((m-lo)/max(hi-lo,1), 0, 1)
        idx = (n*(len(RAMP)-1)+0.5).astype(int)
        print('     ASCII of that block (y %d..%d x %d..%d):' % (y0, y1, x0, x1))
        for r in range(ch):
            print('       ' + ''.join(RAMP[v] for v in idx[r]))
