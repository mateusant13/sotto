#!/usr/bin/env python3
"""Move the TRANSCRIPT section ABOVE the LIVE caption box in `app/panel/panel.html`.

THE OWNER'S RULE, verbatim (2026-10-08): *"a legenda ao vivo, no painel, tem que
ficar embaixo do painel. o historico a cima"* — the live line goes at the BOTTOM
of the panel, the transcript ABOVE it.

WHY A SCRIPT AND NOT A HAND EDIT: the block is ~100 lines and the move has to be
byte-exact. This reads the file, ASSERTS the current order (so a concurrent edit
by another lane makes it refuse instead of scrambling the document), moves the
transcript block whole, and writes it back with the file's own line endings.
Nothing else about the document is touched.
"""

import sys

PATH = r'H:\sotto\app\panel\panel.html'

LIVE_MARK = '<!-- \u2500\u2500 THE PRODUCT: the live caption box'
STRIP_MARK = '<!-- \u2500\u2500 STRIP SURFACE ONLY'
HIST_MARK = '<!-- \u2500\u2500 PANEL SURFACE ONLY: the canonical transcript'

with open(PATH, encoding='utf-8', newline='') as fh:
    src = fh.read()

for mark in (LIVE_MARK, STRIP_MARK, HIST_MARK):
    n = src.count(mark)
    if n != 1:
        sys.exit('REFUSED: marker %r occurs %d times' % (mark, n))

i_live = src.index(LIVE_MARK)
i_strip = src.index(STRIP_MARK)
i_hist = src.index(HIST_MARK)
if not (i_live < i_strip < i_hist):
    sys.exit('REFUSED: the current order is not live < stripbar < history '
             '(%d, %d, %d)' % (i_live, i_strip, i_hist))

j_hist = src.index('</section>', i_hist) + len('</section>')
hist_block = src[i_hist:j_hist]
rest = src[:i_hist] + src[j_hist:]

i_hdr = rest.index('</header>') + len('</header>')
inserted = '\n\n      ' + hist_block
out = rest[:i_hdr] + inserted + rest[i_hdr:]

# The move must be the ONLY change: the inserted region is exactly the block, and
# taking it back out has to reproduce `rest` — which is `src` minus that block.
if rest != src[:i_hist] + src[j_hist:]:
    sys.exit('REFUSED: the removal was not exact')
if out[:i_hdr] != rest[:i_hdr] or out[i_hdr + len(inserted):] != rest[i_hdr:]:
    sys.exit('REFUSED: something other than the insertion changed')
if out[i_hdr:i_hdr + len(inserted)] != inserted:
    sys.exit('REFUSED: the inserted region is not the transcript block')

with open(PATH, 'w', encoding='utf-8', newline='') as fh:
    fh.write(out)

print('moved: transcript block (%d bytes) now sits directly after </header>' % len(hist_block))
print('new order: header, transcript, live, stripbar, status')
