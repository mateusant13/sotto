"""Make the per-direction header layout independent of WHEN the surface is claimed.

MEASURED, and it is why the owner's own capture looked wrong: the renderer lane's
fixture (`H:\\aireplay\\_main\\panel-temas-fixture\\panel.html`) writes a bare
`<body>` — no `data-surface` at all — and `surface.js`, which is what sets it in
the real document, does not run there. So every theme rule scoped
`body[data-surface="panel"]` silently did NOT apply in the captures: the two
directions whose header layout is a GRID fell back to `panel.css`'s plain flex
row and their controls landed on a second line.

The real app is unaffected (`surface.js` sets the attribute before the panel
paints, and the probe asserts the layout at 380x900), but a layout that depends on
an attribute being present is fragile in exactly the way that costs a re-capture.
`body:not([data-surface="strip"])` says what is meant: the PANEL layout is the
DEFAULT, and only the strip opts out.
"""
import io, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

GEN = r'_main\_design-lane\gen_themes.py'
t = io.open(GEN, encoding='utf-8', newline='').read()

pairs = [
    ('@S@ body[data-surface="panel"] .panel__header{',
     '@S@ body:not([data-surface="strip"]) .panel__header{'),
    ('@S@ body[data-surface="panel"] .panel__controls{',
     '@S@ body:not([data-surface="strip"]) .panel__controls{'),
]
for a, b in pairs:
    n = t.count(a)
    print('%-70s count=%d' % (a[:66], n))
    t = t.replace(a, b)

# And the same reasoning in `panel.css`, where the header's own layout lives.
CSS = r'app\panel\panel.css'
c = io.open(CSS, encoding='utf-8', newline='').read()
# nothing to change there: `.panel__header` is shown and laid out by DEFAULT, and
# only the strip hides it. Recorded here so the next reader does not "fix" it.

io.open(GEN, 'w', encoding='utf-8', newline='').write(t)
print('generator written')
