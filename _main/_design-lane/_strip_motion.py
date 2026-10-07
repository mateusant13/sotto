import io, re
p = r'H:\sotto\_main\_design-lane\gen_themes.py'
t = io.open(p, encoding='utf-8', newline='').read()
nl = '\r\n' if '\r\n' in t else '\n'
print('newline:', repr(nl), 'len', len(t))
pat = re.compile(r'\r?\n@media \(prefers-reduced-motion: reduce\)\{\r?\n(?:  @[SB]@ [^\r\n]*\r?\n)+\}\r?\n', re.M)
found = pat.findall(t)
print('blocks found:', len(found))
for f in found:
    print('---')
    print(f.replace('\r', '').strip())
t2 = pat.sub(nl, t)
io.open(p, 'w', encoding='utf-8', newline='').write(t2)
print('before', len(t), 'after', len(t2))
