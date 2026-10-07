import numpy as np
from PIL import Image
RAMP = ' .:-=+*#%@'
def art(i, cw=150, ch=52):
    a = np.array(Image.open(r'H:\sotto\docs\design\incoming\design-%d.png' % i).convert('L')).astype(np.float32)
    h, w = a.shape
    im = Image.fromarray(a.astype(np.uint8)).resize((cw, ch), Image.BOX)
    m = np.array(im).astype(np.float32)
    lo, hi = np.percentile(m, 2), np.percentile(m, 99.5)
    n = np.clip((m - lo) / max(hi - lo, 1), 0, 1)
    idx = (n * (len(RAMP) - 1) + 0.5).astype(int)
    print('=' * 152)
    print('design-%d   %dx%d  -> ascii %dx%d   lum p2=%.0f p99.5=%.0f' % (i, w, h, cw, ch, lo, hi))
    print('    ' + ''.join(('|' if c % 10 == 0 else ' ') for c in range(cw)))
    for r in range(ch):
        print('%3d ' % int(r * h / ch) + ''.join(RAMP[v] for v in idx[r]))
for i in range(1, 6):
    art(i)
