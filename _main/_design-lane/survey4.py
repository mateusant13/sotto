import numpy as np
from PIL import Image
from collections import Counter
def hx(c): return '#%02X%02X%02X' % (int(round(c[0])), int(round(c[1])), int(round(c[2])))
for i in range(1, 6):
    a = np.array(Image.open(r'H:\sotto\docs\design\incoming\design-%d.png' % i).convert('RGB')).astype(np.int16)
    h, w, _ = a.shape
    lum = a.mean(axis=2); sat = a.max(axis=2) - a.min(axis=2)
    flat = a.reshape(-1, 3); fl = lum.reshape(-1); fs = sat.reshape(-1)
    print('=' * 96); print('design-%d  %dx%d' % (i, w, h))
    for lo, hi in ((80, 200), (120, 255), (160, 255)):
        m = (fl >= lo) & (fl <= hi) & (fs >= 30)
        if m.sum() > 50:
            c = Counter(hx((v // 8) * 8) for v in flat[m])
            print('  ACCENT(lum %3d-%3d, sat>=30) n=%6d  -> %s' % (lo, hi, m.sum(), ', '.join('%s:%d' % (k, n) for k, n in c.most_common(6))))
    # text-line detection in the right-hand 420 px (candidate panel) using row darkness profile
    print('  --- row profile of the brightest pixels, x 1150..1672 ---')
    sub = a[:, 1150:, :]; sl = sub.mean(axis=2)
    rows = (sl >= 110).sum(axis=1)
    runs = []
    inr = False
    for y in range(h):
        if rows[y] >= 6 and not inr: inr = True; y0 = y
        elif rows[y] < 6 and inr: inr = False; runs.append((y0, y, int(rows[y0:y].max())))
    for r in runs:
        band = sub[r[0]:r[1]]
        bl = band.mean(axis=2)
        pk = band[bl >= np.percentile(bl, 97)]
        print('     band y %4d..%4d h=%3d  peakcols=%3d  peakmean=%s' % (r[0], r[1], r[1]-r[0], r[2], hx(pk.mean(axis=0)) if len(pk) else '-'))
