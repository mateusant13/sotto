import io

EDITS = {
    r'app\panel\panel.html': [
        ('`data-surface="strip"` is what Alt+C opens: the live captions and four',
         '`data-surface="strip"` is what the app\u2019s one control opens: the live captions and four'),
        ('p\u00e1g. 1`, `SOTTO / \u00b7 ao vivo \u00b7`, `ON / ALT+C`.',
         'p\u00e1g. 1`, `SOTTO / \u00b7 ao vivo \u00b7`, `ON / STBY`.'),
        ('<!-- \u2500\u2500 STRIP SURFACE ONLY: the whole control row Alt+C now opens \u2500\u2500\u2500\u2500\u2500\u2500',
         '<!-- \u2500\u2500 STRIP SURFACE ONLY: the short control row the app\u2019s one control opens \u2500\u2500'),
    ],
    r'app\panel\panel.js': [
        ('// Owner, 2026-10-08: Alt+C opens the LIVE CAPTIONS ONLY \u2014 a short strip \u2014 and the',
         '// Owner, 2026-10-08: the global hotkey opens the LIVE CAPTIONS ONLY \u2014 a short strip \u2014 and the'),
        ('// F7 \u2014 THE APP COULD NOT BE CLOSED. Alt+C hides, `run.cmd` starts a detached',
         '// F7 \u2014 THE APP COULD NOT BE CLOSED. The hotkey hides, `run.cmd` starts a detached'),
    ],
    r'app\panel\panel.css': [
        ('dot and the Alt+C hint are unchanged. */',
         'dot is unchanged; the hint that named the key is gone. */'),
        ('`body[data-surface="strip"]` is what Alt+C opens: the live captions and four',
         '`body[data-surface="strip"]` is what the app\u2019s one control opens: the live captions and four'),
        ('/* -------------------------------------------------- the strip surface (Alt+C) */',
         '/* ---------------------------------------------- the strip surface (the short one) */'),
        ('without this the owner could not change the theme on the surface Alt+C opens',
         'without this the owner could not change the theme on the surface the key opens'),
    ],
    r'app\panel\surface.js': [
        ('* THE PRODUCT DECISION (owner, 2026-10-08): Alt+C must NOT open the whole',
         '* THE PRODUCT DECISION (owner, 2026-10-08): the global hotkey must NOT open the whole'),
    ],
}

for path, pairs in EDITS.items():
    t = io.open(path, encoding='utf-8', newline='').read()
    for a, b in pairs:
        n = t.count(a)
        if n != 1:
            print('MISS %-30s count=%d  %r' % (path, n, a[:60]))
            continue
        t = t.replace(a, b)
    io.open(path, 'w', encoding='utf-8', newline='').write(t)
    print('ok   %s' % path)
