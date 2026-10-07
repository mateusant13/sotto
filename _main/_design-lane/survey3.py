import numpy as np
from PIL import Image
from collections import Counter

def load(i):
    return np.array(Image.open(r'H:\sotto\docs\design\incoming\design-%d.png' % i).convert('RGB')).astype(np.int16)

HEXD = {}
def hx(c):
    return '#%02X%02X%02X' % (int(c[0]), int(c[1]), int(c[2]))

for i in range(1, 6):
    a = load(i); h, w, _ = a.shape
    print('=' * 100); print('design-%d  %dx%d' % (i, w, h))
    lum = a.mean(axis=2)
    mx = a.max(axis=2); mn = a.min(axis=2); sat = (mx - mn)
    # bright text pixels only
    br = lum >= 120
    ys, xs = np.where(br)
    print('  bright(>=120) pixels: %d ; x %d..%d  y %d..%d' % (len(ys), xs.min(), xs.max(), ys.min(), ys.max()))
    # cluster into connected bounding boxes on a coarse grid
    T = 6; gh, gw = h // T, w // T
    grid = np.zeros((gh, gw), np.float32)
    for y, x in zip(ys, xs):
        grid[y // T, x // T] += 1
    thr = max(grid.max() * 0.06, 1)
    seen = np.zeros_like(grid, bool)
    boxes = []
    for r in range(gh):
        for c in range(gw):
            if grid[r, c] >= thr and not seen[r, c]:
                st = [(r, c)]; seen[r, c] = True; members = []
                while st:
                    rr, cc = st.pop(); members.append((rr, cc))
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            nr, nc = rr + dr, cc + dc
                            if 0 <= nr < gh and 0 <= nc < gw and not seen[nr, nc] and grid[nr, nc] >= thr:
                                seen[nr, nc] = True; st.append((nr, nc))
                if len(members) >= 12:
                    rs = [m[0] for m in members]; cs = [m[1] for m in members]
                    boxes.append((min(rs)*T, max(rs)*T+T, min(cs)*T, max(cs)*T+T, len(members)))
    boxes.sort(key=lambda b: (b[0], b[2]))
    print('  text blocks (y0,y1,x0,x1, tiles) >=12 tiles, %d found:' % len(boxes))
    for b in boxes[:18]:
        print('     y %4d..%4d  x %4d..%4d  tiles=%d  w=%d h=%d' % (b[0], b[1], b[2], b[3], b[4], b[3]-b[2], b[1]-b[0]))
    # colour composition of bright pixels: top hex families
    hp = [hx(v) for v in a[br]]
    cnt = Counter()
    for v in a[br]:
        cnt[hx((v // 8) * 8)] += 1
    tot = sum(cnt.values())
    print('  bright-pixel colour modes (quantized 8):')
    for k, n in cnt.most_common(8):
        print('     %s  %5.1f%%  (%d)' % (k, 100.0*n/tot, n))
    # peak whites
    top = np.percentile(lum, 99.9)
    hp2 = a[lum >= top]
    m = hp2.mean(axis=0)
    print('  peak-0.1%% mean: %s  (thr %.0f, n=%d)' % (hx(m), top, len(hp2)))
    # most saturated coloured pixels
    sc = sat.copy().astype(np.float32) * (lum > 40)
    tc = np.percentile(sc, 99.9)
    cs = a[sc >= tc]
    if len(cs):
        m = cs.mean(axis=0); print('  saturated-peak mean: %s  n=%d  (sat<=%.0f)' % (hx(m), len(cs), tc))
        cc = Counter()
        for v in cs:
            cc[hx((v // 8) * 8)] += 1
        print('     top saturated colours: ' + ', '.join('%s(%d)' % (k, n) for k, n in cc.most_common(6)))
    # luminance histogram of the whole picture (to find slab vs frame)
    hist, edges = np.histogram(lum, bins=12, range=(0, 256))
    print('  lum histogram /12: ' + ' '.join('%4.1f%%' % (100.0*v/lum.size) for v in hist))
