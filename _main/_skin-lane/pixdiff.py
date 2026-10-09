"""Localize the vendor-vs-frozen pixel gap: band stats + ascii luminance maps."""
import hashlib
from PIL import Image, ImageChops

V = 'H:/sotto/_main/_skin-lane/shots/cellar.gate-vendor.png'
F = 'H:/sotto/_main/_skin-lane/shots/cellar.gate-frozen.png'
v = Image.open(V).convert('RGB')
f = Image.open(F).convert('RGB')
print('size', v.size, f.size)
d = ImageChops.difference(v, f)
print('bbox', d.getbbox())
dp = d.load()
vp = v.load()
fp = f.load()
W, H = v.size
# per-100px-horizontal-band mean abs diff, split left/right halves
for y0 in range(0, H, 100):
    for half, x0, x1 in (('L', 0, W // 2), ('R', W // 2, W)):
        s = n = 0
        for y in range(y0, min(y0 + 100, H), 4):
            for x in range(x0, x1, 4):
                a, b, c = dp[x, y]
                s += a + b + c
                n += 3
        print('band y%d-%d %s meanabs=%.1f' % (y0, min(y0 + 100, H), half, s / max(n, 1)))
# ascii luminance maps, 20px cells -> 19 cols x 45 rows; vendor then frozen
CH = ' .:-=+*#%@'
def cell(img, cx, cy):
    s = 0
    n = 0
    for y in range(cy * 20, min(cy * 20 + 20, H), 2):
        for x in range(cx * 20, min(cx * 20 + 20, W), 2):
            r, g, b = img.load()[x, y]
            s += (r * 3 + g * 6 + b) // 10
            n += 1
    return CH[min(9, s // max(n, 1) // 13)]
print('--- vendor ascii ---')
for cy in range(45):
    print(''.join(cell(v, cx, cy) for cx in range(19)))
print('--- frozen ascii ---')
for cy in range(45):
    print(''.join(cell(f, cx, cy) for cx in range(19)))
# sample a few concrete pixels: wallpaper mid-left, center, caption plate, bottom
for x, y in [(40, 150), (190, 150), (40, 450), (190, 450), (190, 650), (190, 800), (40, 850)]:
    print('px(%d,%d) v=%s f=%s' % (x, y, vp[x, y], fp[x, y]))
