"""Find where panel.js's braces/parens/brackets stop balancing.

Line-by-line running depth of (), {}, [] ignoring strings/comments would be
overkill; this walks the file with a tiny state machine that skips string
literals, template literals and comments, and prints the first line at which the
depth goes NEGATIVE (a stray closer) or the depth that remains at EOF.
"""
import io

src = io.open(r'app\panel\panel.js', encoding='utf-8').read()
depth = 0
i = 0
n = len(src)
line = 1
state = None          # None | "'" | '"' | '`' | '//' | '/*'
open_line = []
neg = []
while i < n:
    c = src[i]
    nxt = src[i + 1] if i + 1 < n else ''
    if c == '\n':
        line += 1
        if state == '//':
            state = None
        i += 1
        continue
    if state == '//':
        i += 1
        continue
    if state == '/*':
        if c == '*' and nxt == '/':
            state = None
            i += 2
            continue
        i += 1
        continue
    if state in ("'", '"', '`'):
        if c == '\\':
            i += 2
            continue
        if c == state:
            state = None
        i += 1
        continue
    if c == '/' and nxt == '/':
        state = '//'
        i += 2
        continue
    if c == '/' and nxt == '*':
        state = '/*'
        i += 2
        continue
    if c in ("'", '"', '`'):
        state = c
        i += 1
        continue
    if c in '({[':
        depth += 1
        open_line.append((c, line))
    elif c in ')}]':
        depth -= 1
        if open_line:
            open_line.pop()
        if depth < 0:
            neg.append(line)
            depth = 0
    i += 1

print('final depth (0 == balanced):', depth)
print('negative-depth lines:', neg[:10])
print('unclosed openers (innermost last):')
for c, l in open_line[-8:]:
    print('   %s opened at line %d' % (c, l))
