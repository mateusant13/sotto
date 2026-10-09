import json
from PIL import Image, ImageChops

SHOTS = r'H:\sotto\_main\_skin-lane\shots'
r = json.load(open(r'H:\sotto\_main\_skin-lane\isolate-report.json'))
vp, fp = r['vendorPaint'], r['frozenPaint']
print(f'vendor rows={len(vp)} frozen rows={len(fp)}')
fl = {x['label']: x for x in fp}
for v in vp:
    f = fl.get(v['label'])
    if f is None:
        print(f"MISSING frozen label {v['label']}");
        continue
    diffs = [k for k in v if v[k] != f.get(k)]
    print(('SAME ' if not diffs else 'DIFF ' + ','.join(diffs) + ' ') + v['label'])

# wall-only band stats for the new frozen capture
a = Image.open(f'{SHOTS}\\cellar.iso-vendor-wall.png').convert('RGB')
b = Image.open(f'{SHOTS}\\cellar.iso-frozen-wall.png').convert('RGB')
d = ImageChops.difference(a, b)
print('WALL-ONLY bbox=', d.getbbox(), 'sizes', a.size, b.size)
for y0 in (100, 300, 500, 600, 700):
    for half, x0 in (('L', 0), ('R', 190)):
        px = list(d.crop((x0, y0, x0 + 190, y0 + 100)).convert('L').getdata())
        print(f'   y{y0}-{y0+100} {half} meanabs={sum(px)/len(px):.1f} max={max(px)}')
for p in ('cellar.iso-vendor-wall.png', 'cellar.iso-frozen-wall.png'):
    im = Image.open(f'{SHOTS}\\{p}').convert('RGB')
    print(p, 'px(40,150)=', im.getpixel((40, 150)), 'px(190,450)=', im.getpixel((190, 450)),
          'px(40,850)=', im.getpixel((40, 850)), 'px(200,650)=', im.getpixel((200, 650)))
