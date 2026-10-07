import io, re

t = io.open(r'_main\_design-lane\gen_themes.py', encoding='utf-8').read()
for m in re.finditer(r"'n':\s*(\d+)", t):
    s = t[m.start():m.start() + 2000]

    def g(k):
        mm = re.search(r"'" + k + r"':\s*'([^']*)'", s)
        return mm.group(1) if mm else '?'

    print('theme-%s %-14s surface=%-9s accent=%-9s accent_from=%-9s text=%-9s'
          % (g('n'), g('label'), g('surface'), g('accent'), g('accent_from'), g('text')))
