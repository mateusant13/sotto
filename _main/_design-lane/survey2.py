import numpy as np
from PIL import Image
def load(i):
    return np.array(Image.open(r'H:\sotto\docs\design\incoming\design-%d.png' % i).convert('RGB')).astype(np.int16)
for i in range(1, 6):
    a = load(i); h, w, _ = a.shape
    print('=' * 100); print('design-%d' % i)
    mx = a.max(axis=2); mn = a.min(axis=2); sat = mx - mn; lum = a.mean(axis=2)
    T = 8; gh, gw = h // T, w // T
    satt = sat[:gh*T, :gw*T].reshape(gh, T, gw, T).mean(axis=(1, 3))
    lumt = lum[:gh*T, :gw*T].reshape(gh, T, gw, T).mean(axis=(1, 3))
    for name, m in (('sat', satt), ('lum', lumt)):
        bands = np.array_split(np.arange(gw), 16)
        prof = [m[:, b].mean() for b in bands]
        print('  %s /16 width: ' % name + ' '.join('%5.1f' % p for p in prof))
    rows = np.array_split(np.arange(gh), 20)
    prof = [lumt[r, :].mean() for r in rows]
    print('  lum /20 height: ' + ' '.join('%5.1f' % p for p in prof))
    flat = a.reshape(-1, 3); br = flat.mean(axis=1)
    thr = np.percentile(br, 99.7); hi = flat[br >= thr]
    m = hi.mean(axis=0).astype(int)
    print('  brightest 0.3%%: #%02X%02X%02X  thr=%.0f  n=%d' % (m[0], m[1], m[2], thr, len(hi)))
    sthr = np.percentile(sat.reshape(-1), 99.9)
    hs = flat[(sat.reshape(-1) >= sthr) & (br > 60)]
    if len(hs):
        m = hs.mean(axis=0).astype(int)
        print('  most saturated: #%02X%02X%02X n=%d' % (m[0], m[1], m[2], len(hs)))
    # where the brightest pixels live
    ys, xs = np.where(br.reshape(h, w) >= thr)
    print('  bright px extent: x %d..%d  y %d..%d' % (xs.min(), xs.max(), ys.min(), ys.max()))
