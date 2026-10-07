import io, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

GEN = r'_main\_design-lane\gen_themes.py'
t = io.open(GEN, encoding='utf-8', newline='').read()

old = ("@S@ .chrome--cine[data-chrome=\"head\"]{\r\n"
       "  display: flex;\r\n"
       "  align-items: baseline;\r\n"
       "  flex: 1;\r\n")
new = ("@S@ .chrome--cine[data-chrome=\"head\"]{\r\n"
       "  display: flex;\r\n"
       "  align-items: baseline;\r\n"
       "  /* `flex: 1 1 auto`, NOT `flex: 1`. MEASURED at the real 380x900 geometry\r\n"
       "     (`_main/_panel-chrome-arm.py`, which asserts `innerWidth === 380` from\r\n"
       "     inside the page): with `flex: 1` the basis is 0, so once the control row\r\n"
       "     is on the top row the direction's own header line is squeezed to\r\n"
       "     **width 0** — present in the DOM, invisible on screen, and nothing\r\n"
       "     errors. `auto` keeps the line at its content width. */\r\n"
       "  flex: 1 1 auto;\r\n")
print('count', t.count(old))
assert t.count(old) == 1
t = t.replace(old, new)
io.open(GEN, 'w', encoding='utf-8', newline='').write(t)
print('cine header fixed')
