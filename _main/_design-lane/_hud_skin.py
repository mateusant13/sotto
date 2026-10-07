import io, re

GEN = r'_main\_design-lane\gen_themes.py'
t = io.open(GEN, encoding='utf-8', newline='').read()
# The comment banner above these rules carries box-drawing dashes whose exact
# count I cannot retype reliably; anchor on the RULES, which are unambiguous.
pat = re.compile(
    r'(?:^[^\r\n]*the HUD: numbers[^\r\n]*\r\n)?'
    r'\{S\} \.hud\{\{ border-top-color: var\(--line\); \}\}\r\n'
    r'\{S\} \.hud__row dt\{\{[^\r\n]*\r\n'
    r'\{S\} \.hud__row dd\{\{[^\r\n]*\r\n'
    r'\{S\} \.hud__row--pending dt,\r\n'
    r'\{S\} \.hud__row--pending dd\{\{[^\r\n]*\r\n',
    re.M)
m = pat.search(t)
print('matched %d chars' % (len(m.group(0)) if m else 0))
if m:
    t = t[:m.start()] + t[m.end():]
    io.open(GEN, 'w', encoding='utf-8', newline='').write(t)
    print('removed the skin .hud rules')
left = [i + 1 for i, l in enumerate(t.split('\r\n')) if 'hud' in l.lower()]
print('remaining hud lines in the generator:', left)
