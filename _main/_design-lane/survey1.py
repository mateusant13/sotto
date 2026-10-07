import numpy as np, sys
from PIL import Image

def load(i):
    p = r'H:\sotto\docs\design\incoming\design-%d.png' % i
    return np.array(Image.open(p).convert('RGB'))

def quant(a, q=24):
    return (a // q) * q

for i in range(1, 6):
    a = load(i)
    h, w, _ = a.shape
    print('=' * 90)
    print('design-%d  %dx%d' % (i, w, h))
    q = quant(a.reshape(-1, 3), 16)
    # count unique quantized colours
    uniq, counts = np.unique(q, axis=0, return_counts=True)
    order = np.argsort(-counts)
    tot = q.shape[0]
    print('  distinct quantized colours: %d ; top 14:' % len(uniq))
    for k in order[:14]:
        c = uniq[k]
        print('    #%02X%02X%02X  %6.2f%%  (%d px)' % (c[0], c[1], c[2], 100.0*counts[k]/tot, counts[k]))
    # structure: columns where colour changes
    colvar = a.astype(np.int16).std(axis=(0, 2))
    rowvar = a.astype(np.int16).std(axis=(1, 2))
    # find vertical seams: columns with high mean brightness difference from neighbours
    colmean = a.mean(axis=(0, 2))
    dcol = np.abs(np.diff(colmean))
    seams = [int(x) for x in np.argsort(-dcol)[:40]]
    seams.sort()
    # merge
    merged = []
    for s in seams:
        if merged and s - merged[-1][-1] <= 6: merged[-1].append(s)
        else: merged.append([s])
    print('  column seams (strong vertical edges x):', [m[0] for m in merged])
    rowmean = a.mean(axis=(1, 2))
    drow = np.abs(np.diff(rowmean))
    rs = [int(x) for x in np.argsort(-drow)[:40]]; rs.sort()
    m2 = []
    for s in rs:
        if m2 and s - m2[-1][-1] <= 4: m2[-1].append(s)
        else: m2.append([s])
    print('  row seams (strong horizontal edges y):', [m[0] for m in m2])
