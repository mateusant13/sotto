import re
raw = open(r'H:\sotto\_main\ab-input.txt', encoding='utf-8').read()
t = ' '.join(raw.split())

def arm_a(t):
    t = re.sub(r'\s+([,.;:!?%])', r'\1', t)
    t = re.sub(r' {2,}', ' ', t)
    tails = {'s','d','g','e','n','y','r','ed','ing','es','ly','er','al','ck','ty','ts','ps','ss'}
    keep = {'a','i','to','of','on','in','at','as','is','it','we','me','us','he','so','do','go','no','up','my','an','or','be','if','by'}
    toks = t.split(' ')
    out = []
    for w in toks:
        wl = w.lower()
        if out and wl in tails and len(out[-1]) >= 3 and out[-1][-1].isalpha():
            out[-1] = out[-1] + w
        elif out and len(w) == 1 and w.isalpha() and w.islower() and len(out[-1]) >= 4 and wl not in keep and out[-1].lower() not in keep:
            out[-1] = out[-1] + w
        else:
            out.append(w)
    return ' '.join(out)

a = arm_a(t)
open(r'H:\sotto\_main\ab-arm-a.txt', 'w', encoding='utf-8').write(a)
print('A words:', len(a.split()))
print('A head:', a[:300])

def arm_b(a):
    parts = re.split(r'(?<=[.!?])\s+', a)
    out = []
    for p in parts:
        while len(p) > 120:
            m = re.search(r'\s(but|so|because|and|which|that|where|when|if|even|also)\s', p[40:])
            if not m:
                break
            cut = 40 + m.start() + 1
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        out.append(p.strip())
    sents = []
    for s in out:
        s = s.strip()
        if not s:
            continue
        s = s[0].upper() + s[1:]
        if s[-1] not in '.!?':
            s = s + '.'
        s = re.sub(r'\s+([,.;:!?%])', r'\1', s)
        sents.append(s)
    return sents

b = arm_b(a)
open(r'H:\sotto\_main\ab-arm-b.txt', 'w', encoding='utf-8').write('\n'.join(b))
print('B sents:', len(b))
for s in b[:8]:
    print('-', s)
