import io
p = r'app\panel\panel.js'
lines = io.open(p, encoding='utf-8', newline='').read().split('\n')
for a, b in ((34, 47), (196, 208), (1412, 1418), (1808, 1822), (1944, 1958), (1200, 1208), (1120, 1130)):
    print('--- %d..%d ---' % (a, b))
    for j in range(a - 1, b):
        print('%4d| %s' % (j + 1, lines[j]))
