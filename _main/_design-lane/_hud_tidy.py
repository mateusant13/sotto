import io
P = r'app\panel\panel.js'
t = io.open(P, encoding='utf-8', newline='').read()
pairs = [
    # 1. the state-block doc still names the deleted State row
    (' *   statusSnapshot   the last status the shell sent ({ text, kind }) \u2014 the HUD\'s\n'
     ' *                    State row and the strip\'s one-word status are both read from\n'
     ' *                    ONE place, so they can never disagree with each other.',
     ' *   statusSnapshot   the last status the shell sent ({ text, kind }). The strip\'s\n'
     ' *                    one-word status is read from it, so the word and the sentence\n'
     ' *                    below can never disagree with each other.'),
    # 2. the folder tooltip that only the HUD's button carried
    ('        if (dom.hudFolderButton) dom.hudFolderButton.title = `Open ${root} in the OS file manager`;\n',
     ''),
    # 3. the comment that named the deleted button
    ('  // ONE handler per pause control, bound from a class so the strip\'s button and\n'
     '  // the panel\'s HUD button cannot drift apart; `wirePause` owns the dialog.',
     '  // ONE handler per pause control, bound from a class so the strip\'s button and\n'
     '  // the panel\'s own button cannot drift apart; `wirePause` owns the dialog.'),
    # 4. the doc comment the HUD cut swallowed with revealPath's
    ('function revealPath(path) {',
     '/** Ask the OS file manager to open the entry\'s file, or the root when null.\n'
     ' *  THE ONLY "show in folder" AFFORDANCE NOW, on both surfaces: the transcript\n'
     ' *  bar\'s path button (`#history-root`) and the per-line button in the drawer\n'
     ' *  both call this. The deleted HUD\'s duplicate button called it too. */\n'
     'function revealPath(path) {'),
]
for a, b in pairs:
    n = t.count(a)
    print('%s count=%d' % ('ok  ' if n == 1 else 'MISS', n))
    if n == 1:
        t = t.replace(a, b)
io.open(P, 'w', encoding='utf-8', newline='').write(t)
left = [i + 1 for i, l in enumerate(t.split('\n')) if 'hud' in l.lower()]
print('remaining hud mentions:', left)
print('bytes:', len(t))
