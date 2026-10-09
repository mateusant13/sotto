from PIL import Image, ImageChops
import hashlib

SHOTS = r'H:\sotto\_main\_skin-lane\shots'

def sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def band_stats(a_path, b_path, label):
    a = Image.open(a_path).convert('RGB')
    b = Image.open(b_path).convert('RGB')
    print(f'== {label} sizes {a.size} vs {b.size}')
    d = ImageChops.difference(a, b)
    print(f'   bbox={d.getbbox()}')
    import statistics
    for y0 in range(0, 900, 100):
        for half, x0 in (('L', 0), ('R', 190)):
            box = (x0, y0, x0 + 190, y0 + 100)
            da = d.crop(box).convert('L')
            px = list(da.getdata())
            print(f'   y{y0}-{y0+100} {half} meanabs={sum(px)/len(px):.1f} max={max(px)}')

band_stats(f'{SHOTS}\\cellar.iso-vendor-stage.png', f'{SHOTS}\\cellar.iso-frozen-stage.png',
           'STAGE-ONLY vendor vs frozen')
band_stats(f'{SHOTS}\\cellar.iso-vendor-wall.png', f'{SHOTS}\\cellar.iso-vendor-stage.png',
           'VENDOR wall-only vs stage-only (overlay contribution)')
for p in ('cellar.iso-vendor-stage.png', 'cellar.iso-frozen-stage.png', 'cellar.iso-vendor-wall.png'):
    im = Image.open(f'{SHOTS}\\{p}').convert('RGB')
    print(p, 'px(40,150)=', im.getpixel((40, 150)), 'px(190,450)=', im.getpixel((190, 450)),
          'px(40,850)=', im.getpixel((40, 850)))
