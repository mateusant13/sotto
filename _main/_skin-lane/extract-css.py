"""Extract the vendor's compiled CSS out of the single-file build, verbatim.

`vite.config.ts` uses `vite-plugin-singlefile`, so `dist/index.html` carries the whole
compiled Tailwind v4 bundle AND `src/index.css` inside ONE `<style>` element. The freeze
needs that CSS as a FILE, and it must be byte-for-byte what the vendor's build emitted —
this script only cuts the element out, it never reformats a single character.

Usage:  py -3 _main/_skin-lane/extract-css.py <zip-dir> <out.css>
"""
import io
import os
import re
import sys

MARK_OPEN = r'<style[^>]*>'
MARK_CLOSE = '</style>'


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 2
    zip_dir = os.path.abspath(argv[1])
    out = os.path.abspath(argv[2])
    index = os.path.join(zip_dir, 'dist', 'index.html')
    if not os.path.isfile(index):
        sys.stderr.write('no dist/index.html at %s\n' % index)
        return 2

    with io.open(index, encoding='utf-8') as fh:
        html = fh.read()

    # The build emits `<style rel="stylesheet" crossorigin>` — WITH attributes — so the
    # opener has to be matched as a shape, not as a literal. The FIRST attempt used the
    # literal `<style>` and reported "FOUND NO <style>" on a file that contains one.
    styles = [m for m in re.finditer(MARK_OPEN + '(.*?)' + re.escape(MARK_CLOSE), html, re.S)]
    if not styles:
        sys.stderr.write('FOUND NO <style> in %s\n' % index)
        return 1

    # The build inlines exactly one stylesheet. More than one means the assumption about
    # which bytes are "the vendor CSS" is no longer safe, so say so instead of guessing.
    print('style elements in dist/index.html: %d  sizes: %s'
          % (len(styles), [len(m.group(1)) for m in styles]))
    if len(styles) != 1:
        sys.stderr.write('REFUSING to guess which <style> is the vendor CSS\n')
        return 1

    css = styles[0].group(1)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, 'w', encoding='utf-8', newline='') as fh:
        fh.write(css)
    print('wrote %s  chars=%d  bytes=%d' % (out, len(css), os.path.getsize(out)))

    # What a shadow root does NOT have. Report every occurrence so the rewrite is complete
    # rather than "the ones I happened to notice".
    for pat in (r'(^|[},])\s*html\b', r'(^|[},])\s*body\b', r'(^|[},])\s*:root\b',
                r'#root\b', r'@font-face', r'url\(\s*[\'"]?https?:', r'::selection',
                r'::-webkit-scrollbar', r'position:\s*fixed'):
        hits = re.findall(pat, css)
        print('  occurrences of %-28s = %d' % (pat, len(hits)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
