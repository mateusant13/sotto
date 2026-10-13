import collections, os, re
P = r'H:/sotto/_main/webview-run.log'
size = os.path.getsize(P)
print('tamanho: %.1f MB' % (size / 1048576.0))
cnt = collections.Counter()
bytes_by = collections.Counter()
lines = 0
noise_lines = 0
rx = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:.]+ sotto: ([A-Za-z_\-]+)')
with open(P, 'r', encoding='utf-8', errors='replace') as fh:
    for ln in fh:
        lines += 1
        m = rx.match(ln)
        if m:
            k = m.group(1)
        else:
            k = "<NO-TOKEN>"
            noise_lines += 1
        cnt[k] += 1
        bytes_by[k] += len(ln)
print('linhas: %d   sem token: %d' % (lines, noise_lines))
print('')
print('%-28s %10s %12s' % ('EVENTO', 'LINHAS', 'MB'))
for k, n in cnt.most_common(14):
    print('%-28s %10d %12.1f' % (k, n, bytes_by[k] / 1048576.0))