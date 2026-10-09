import io, json, re, sys

t = io.open('app/panel/skins/skins.js', encoding='utf-8').read()
print('skins.js bytes:', len(t.encode('utf-8')))
low = t.lower()
for w in ('sofia', 'june', 'sotto', 'mumble'):
    print('contains %r: %s' % (w, w in low))

# Extract the mute array for cinematic-2 without a full JS parse:
# find '"mute":[' after '"cinematic-2"' and bracket-match.
anchor = t.find('"cinematic-2"')
seg = t[anchor:anchor + 200000]
mk = seg.find('"mute":[')
start = anchor + mk + len('"mute":[')
depth = 1
instr = False
esc = False
i = start
while i < len(t) and depth > 0:
    c = t[i]
    if instr:
        if esc:
            esc = False
        elif c == '\\':
            esc = True
        elif c == '"':
            instr = False
    else:
        if c == '"':
            instr = True
        elif c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
    i += 1
arr_text = '[' + t[start:i - 1] + ']'
mute = json.loads(arr_text)
print('cinematic-2 mute count:', len(mute))
for w in ('sofia', 'june', 'sofia (caller)', 'marlow', 'everyone'):
    print('mute has %r: %s' % (w, w in mute))
print('sofia-like:', [w for w in mute if 'sof' in w])
print('june-like:', [w for w in mute if 'june' in w])
