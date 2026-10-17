"""Report every CSS rule in the panel tree whose selector targets the slab
(`html`, `body`, `.panel`) and whose body declares a `border` or a
`border-radius` -- the frame/radius facts, from the BYTES, not from a grep."""
import glob
import io
import os
import re

ROOT = r'H:\sotto\app\panel'
SEL = re.compile(r'(^|[\s,>])(html|body|\.panel)(\b|\s*[,{])')


def blocks(text):
    # strip comments, then split on { }
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    i = 0
    while True:
        j = text.find('{', i)
        if j < 0:
            return
        k = text.find('}', j)
        if k < 0:
            return
        yield text[i:j].strip(), text[j + 1:k]
        i = k + 1


def main():
    for path in sorted(glob.glob(os.path.join(ROOT, '*.css')) +
                       glob.glob(os.path.join(ROOT, 'themes', '*.css'))):
        text = io.open(path, encoding='utf-8', newline='').read()
        for sel, body in blocks(text):
            s = ' '.join(sel.split())
            if not s or len(s) > 200:
                continue
            if not SEL.search(' ' + s + ' '):
                continue
            if not re.search(r'\bborder(-radius)?\s*:', body):
                continue
            props = [d.strip() for d in body.split(';') if 'border' in d]
            print('%-24s %-58s %s' % (os.path.basename(path), s[:58],
                                      ' | '.join(props)[:110]))


main()