import io, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

GEN = r'_main\_design-lane\gen_themes.py'
lines = io.open(GEN, encoding='utf-8', newline='').read().split('\r\n')

# 1. the live line's clock: a TRUE YELLOW, except where the accent already is one.
#    (owner, 2026-10-08: *"ate tempo, que é amarelo o atual e cinza os que ficaram
#    pra tras"* — and the same breath's rule: if a theme's accent is already
#    yellow, use it.)
YELLOW = '#FFD24A'
for ln in (108, 197, 278):          # theme-1, theme-3, theme-5
    i = ln - 1
    assert "time_live='var(--text-muted)'" in lines[i] or "time_live='var(--accent)'" in lines[i], lines[i]
    lines[i] = "  time_live='%s'," % YELLOW
    print('theme at line %d -> %s' % (ln, YELLOW))
i = 156 - 1                        # theme-2: accent is #FF6A55, a red
assert "time_live='var(--accent)'" in lines[i], lines[i]
lines[i] = "  time_live='%s'," % YELLOW
print('theme-2 (line 156) -> %s' % YELLOW)
print('theme-4 (line 238) KEPT as var(--accent): #E4B363 is already gold')

t = '\r\n'.join(lines)

# 2. a PAST line is grey, all of it. `.caption--latest` is still a past line — the
#    binary the owner asked for is "the current one" vs "the ones left behind".
old = '{B} .caption--latest .caption__time{{ color: var(--text-secondary); }}'
new = ('/* A past line is GREY, all of them. `.caption--latest` is the newest CLOSED\n'
       '   line — still past, so still grey: the owner\'s rule is binary ("o atual"\n'
       '   vs "os que ficaram pra tras"), and a third colour would blur it. */\n'
       '{B} .caption--latest .caption__time{{ color: var(--text-muted); }}')
assert t.count(old) == 1, t.count(old)
t = t.replace(old, new)

# 3. the same rule, said in the base stylesheet, so the two agree. The THEME file
#    is the one that wins (same specificity, later in the document), which is why
#    the value lives there — but panel.css is where a reader looks first.
io.open(GEN, 'w', encoding='utf-8', newline='').write(t)
print('generator written')
