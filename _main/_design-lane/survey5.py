import numpy as np
from PIL import Image
from collections import Counter
def hx(c): return '#%02X%02X%02X' % (int(round(c[0])), int(round(c[1])), int(round(c[2])))
for i in range(1, 6):
    a = np.array(Image.open(r'H:\sotto\docs\design\incoming\design-%d.png' % i).convert('RGB')).astype(np.int16)
    h, w, _ = a.shape
    lum = a.mean(axis=2); sat = a.max(axis=2) - a.min(axis=2)
    T = 10; gh, gw = h // T, w // T
    G = lum[:gh*T, :gw*T].reshape(gh, T, gw, T).mean(axis=(1, 3))
    S = sat[:gh*T, :gw*T].reshape(gh, T, gw, T).mean(axis=(1, 3))
    print('=' * 100); print('design-%d  %dx%d' % (i, w, h))
    best = None
    for c in range(gw):
        for c2 in range(c + 3, gw + 1):
            if c == 0 and c2 == gw: continue
            sub = G[:, c:c2]
            frac = (sub < 90).mean()
            if frac < 0.92: continue
            area = (c2 - c) * gh
            if best is None or area > best[0]:
                best = (area, c, c2, frac, S[:, c:c2].mean())
    if best:
        print('  largest uniform-DARK column band: x %d..%d (w=%d)  darkfrac=%.3f  meangrid-sat=%.1f  -> lum p50 in band=%.1f'
              % (best[1]*T, best[2]*T, (best[2]-best[1])*T, best[3], best[4], np.median(lum[:, best[1]*T:best[2]*T])))
    # per-side text rows
    for (x0, x1) in ((0, w//2), (w//2, w)):
        sub = a[:, x0:x1]; sl = sub.mean(axis=2); ss = sub.max(axis=2)-sub.min(axis=2)
        rows = (sl >= 105).sum(axis=1)
        runs = []; inr = False
        for y in range(h):
            if rows[y] >= 5 and not inr: inr = True; y0 = y
            elif rows[y] < 5 and inr:
                inr = False
                if y - y0 >= 5: runs.append((y0, y))
        if runs: print('  x %4d..%4d text rows: %d  total px=%d  y %d..%d' % (x0, x1, len(runs), int(rows.sum()), runs[0][0], runs[-1][1]))
        else: print('  x %4d..%4d text rows: NONE' % (x0, x1))
    # alignment of text rows inside x 1120..1672
    sub = a[:, 1120:]; sl = sub.mean(axis=2)
    print('  --- x1120..1672 rows (left-x, right-x, lum, sat) ---')
    rows = (sl >= 105).sum(axis=1); inr = False; runs = []
    for y in range(h):
        if rows[y] >= 4 and not inr: inr = True; y0 = y
        elif rows[y] < 4 and inr:
            inr = False
            if y - y0 >= 6: runs.append((y0, y))
    for (y0, y1) in runs:
        band = sub[y0:y1]; bl = band.mean(axis=2)
        m = bl >= 95
        if m.sum() < 20: continue
        xs = np.where(m.any(axis=0))[0]
        pk = band[bl >= np.percentile(bl, 98)]
        s = (band.max(axis=2)-band.min(axis=2))[m].mean()
        print('     y %4d..%4d  x %4d..%4d (w=%4d)  leftx=%4d rightx=%4d  mean=%s  pk=%s meanSat=%.0f'
              % (y0, y1, 1120+xs.min(), 1120+xs.max(), xs.max()-xs.min(), 1120+xs.min(), 1120+xs.max(),
                 hx(band[bl >= 105].mean(axis=0)) if (bl >= 105).sum() else '-', hx(pk.mean(axis=0)), s))
