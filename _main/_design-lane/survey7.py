import numpy as np
from PIL import Image
def load(i):
    return np.array(Image.open(r'H:\sotto\docs\design\incoming\design-%d.png' % i).convert('RGB')).astype(np.int16)

def med(band, m):
    v = band[m]
    return np.median(v, axis=0)

for i in range(1, 6):
    a = load(i); h, w, _ = a.shape
    print('=' * 90); print('design-%d' % i)
    # Panel region: median colour of the rows just above the first text row, and of the whole right column
    sub = a[:, 1120:1672]; lum = sub.mean(axis=2); sat = sub.max(axis=2)-sub.min(axis=2)
    # rows with no text (no pixel > 60 lum and not a big coloured field)
    txt = (lum >= 60)
    dense = txt.mean(axis=1)
    quiet = np.where(dense < 0.005)[0]
    print('  quiet rows (dense<0.5%%): %d of %d' % (len(quiet), h))
    if len(quiet):
        q = sub[quiet]
        dark = q[q.mean(axis=2) < 45]
        if len(dark):
            m = np.median(dark, axis=0)
            print('  QUIET DARK background (panel slab), median: #%02X%02X%02X  n=%d' % (int(m[0]), int(m[1]), int(m[2]), len(dark)))
    # sub-colours: split bright pixels by luminance tier
    flat = sub.reshape(-1, 3); fl = lum.reshape(-1); fs = sat.reshape(-1)
    for lo, hi, tag in ((60, 110, 'tier-A dim'), (110, 200, 'tier-B mid'), (200, 256, 'tier-C brightest')):
        m = (fl >= lo) & (fl < hi) & (fs < 12)
        if m.sum() > 400:
            med_c = np.median(flat[m], axis=0)
            print('  %-14s (lum %3d-%3d, near-grey) n=%6d median #%02X%02X%02X   p90 lum=%.0f'
                  % (tag, lo, hi, m.sum(), int(med_c[0]), int(med_c[1]), int(med_c[2]), np.percentile(fl[m], 90)))
    # accent inside panel: chromatic bright
    m = (fl >= 110) & (fs >= 35)
    if m.sum() > 100:
        med_c = np.median(flat[m], axis=0)
        ys = np.where(m.reshape(sub.shape[:2]).any(axis=1))[0]
        print('  PANEL ACCENT  (lum>=110, sat>=35) n=%6d median #%02X%02X%02X   rows y %d..%d'
              % (m.sum(), int(med_c[0]), int(med_c[1]), int(med_c[2]), ys.min(), ys.max()))
    # line pitch: distance between successive text-row starts in the right column
    rows = (lum >= 105).sum(axis=1); runs = []; inr = False
    for y in range(h):
        if rows[y] >= 4 and not inr: inr = True; y0 = y
        elif rows[y] < 4 and inr:
            inr = False
            if y - y0 >= 6: runs.append(y0)
    if len(runs) > 3:
        d = np.diff(runs)
        print('  text-row starts: %s' % runs)
        print('  pitch diffs:     %s   median=%d px' % (list(d), int(np.median(d))))
