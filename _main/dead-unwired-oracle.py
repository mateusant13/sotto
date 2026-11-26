# NO-BUG: Oracle: the two "kept but unwired" modules are wired by NOTHING, and the
#        prose that says so names the right count. Capacidade/observabilidade
#        pedida pelo dono (varredura de codigo morto); nao ha id de
#        `_main/bug-ledger.json` para isto, e o id nao se inventa.
"""Oracle: `history-store.js` and `discord_streams.py` are WIRED BY NOTHING.

THE DECISION THIS EXISTS FOR (measured 2026-11-26 by the dead-wiring sweep):
both files are load-bearing evidence of a design that is not on the live path,
and both must be KEPT -- `app/panel/package.json:4` forbids deleting the Node
twin, and `run.cmd --worker worker\\discord_streams.py` reaches the Discord
reader as an alternate subprocess. Keeping dead code is only honest while the
statement "nothing calls it" stays TRUE: the day a page script tag or an
`import` appears, the twin becomes a second owner of the same rule and the
prose in `sotto_webview.py` starts lying.

ARMS
  a. NO-PAGE-REF   -- no `app/**/*.html` `<script src=...>` names `history-store.js`;
  b. NO-IMPORTER   -- no `*.py` in the tree imports `discord_streams`;
  c. SCRIPT-COUNT  -- `panel.html`'s `<script src>` count equals the number the
                      shell's own comment states (`loads N page scripts`), so the
                      "not on the shipped page" claim cannot silently drift;
  d. PRESENT       -- both modules still exist and are non-empty (a gate about
                      dead code is vacuous once the code is gone).

Each arm is graded by a PURE function over a tree root; the negative arm builds
a throwaway tree with the defect injected and requires the SAME function to go
RED. A gate that only greps the live tree cannot be shown to fail.

Usage:
  py -3 _main/dead-unwired-oracle.py            # rc 0 = PASS
  py -3 _main/dead-unwired-oracle.py --neg-arm  # rc 1 = every mutant CAUGHT
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))

#: The two modules that are KEPT and WIRED BY NOTHING (the sweep's finding).
NODE_TWIN = 'history-store.js'
PY_TWIN = 'discord_streams.py'

SCRIPT_SRC = re.compile(r'<script[^>]*\bsrc\s*=\s*["\']([^"\']+)', re.I)
#: `from x import discord_streams` / `import worker.discord_streams as d` /
#: `importlib.import_module('discord_streams')` -- a module reached by NAME too.
IMPORT_LINE = re.compile(r'^\s*(?:import\s+\S*?\bdiscord_streams\b'
                         r'|from\s+\S+\s+import\s+[^\n#]*\bdiscord_streams\b)', re.M)
IMPORT_BY_NAME = re.compile(r'import_module\(\s*[fbru]*[\'"]\S*discord_streams', re.M)
#: The shell states the count; the count is what these arms keep TRUE.
SCRIPT_CLAIM = re.compile(r'loads\s+(\d+)\s+page scripts')
SHELL_COMMENT = 'app/webview/sotto_webview.py'
PANEL = 'app/panel/panel.html'


def _iter_files(root, suffix, skip_dirs=('.git', '_legacy-electron', 'node_modules')):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if name.endswith(suffix):
                yield os.path.join(base, name)


def _read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def page_refs(root):
    """Every `<script src>` target in every page, as (relpath, line, ref)."""
    out = []
    for path in _iter_files(root, '.html'):
        text = _read(path)
        for m in SCRIPT_SRC.finditer(text):
            line = text.count('\n', 0, m.start()) + 1
            out.append((os.path.relpath(path, root).replace('\\', '/'), line,
                        m.group(1).strip()))
    return out


def importers(root):
    """Every `import`/`from` line that names the Discord reader, minus this file."""
    me = os.path.basename(__file__)
    out = []
    for path in _iter_files(root, '.py'):
        if os.path.basename(path) == me:
            continue
        text = _read(path)
        for rx in (IMPORT_LINE, IMPORT_BY_NAME):
            for m in rx.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                out.append((os.path.relpath(path, root).replace('\\', '/'),
                            line, m.group(0).strip()[:80]))
    return out


def claimed_count(root):
    """The number the shell's own comment states, or None when absent."""
    path = os.path.join(root, SHELL_COMMENT)
    if not os.path.exists(path):
        return None
    m = SCRIPT_CLAIM.search(_read(path))
    return int(m.group(1)) if m else None


def analyse(root):
    """The whole rule, as a pure function of the tree (this is what mutants hit)."""
    refs = page_refs(root)
    dead_ref = [r for r in refs if os.path.basename(r[2]) == NODE_TWIN]
    dead_imp = importers(root)
    claim = claimed_count(root)
    panel = os.path.join(root, PANEL)
    # A CONTAGEM E' A DA PAGINA SERVIDA, nao de toda copia chamada `panel.html`
    # (a arvore tem fixtures com o mesmo nome: 33 refs contra as 12 da pagina).
    count = (len([r for r in refs if r[0] == PANEL.replace(os.sep, '/')])
             if os.path.exists(panel) else None)
    twins = {}
    for rel in (os.path.join('app', 'panel', NODE_TWIN),
                os.path.join('worker', PY_TWIN)):
        p = os.path.join(root, rel)
        twins[rel.replace('\\', '/')] = os.path.getsize(p) if os.path.exists(p) else 0
    return {
        'a': (not dead_ref, 'page-refs=%d dead=%r' % (len(refs), dead_ref[:2])),
        'b': (not dead_imp, 'importers=%d dead=%r' % (len(importers(root)), dead_imp[:2])),
        'c': (claim is not None and count is not None and claim == count,
              'claim=%r panel_scripts=%r' % (claim, count)),
        'd': (all(v > 0 for v in twins.values()), 'twins=%r' % twins),
    }


ARMS = (('a', 'NO-PAGE-REF: nothing on a page loads the Node twin'),
        ('b', 'NO-IMPORTER: no Python file imports the Discord reader'),
        ('c', 'SCRIPT-COUNT: the shell comment names the real script count'),
        ('d', 'PRESENT: both kept modules exist'))


def _fixture(root):
    """A minimal tree that SATISFIES the rule, so each mutant breaks exactly one arm."""
    os.makedirs(os.path.join(root, 'app', 'panel'), exist_ok=True)
    os.makedirs(os.path.join(root, 'app', 'webview'), exist_ok=True)
    os.makedirs(os.path.join(root, 'worker'), exist_ok=True)
    scripts = ''.join('<script src="app-%d.js"></script>\n' % i for i in range(3))
    with open(os.path.join(root, PANEL), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('<html><body>\n%s</body></html>\n' % scripts)
    with open(os.path.join(root, SHELL_COMMENT), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('#: the twin is NOT on the shipped page: `panel.html` loads 3 page '
                 'scripts and none of\n#: them is `history-store.js`.\n')
    with open(os.path.join(root, 'app', 'panel', NODE_TWIN), 'w', encoding='utf-8') as fh:
        fh.write('module.exports = {};\n')
    with open(os.path.join(root, 'worker', PY_TWIN), 'w', encoding='utf-8') as fh:
        fh.write('def main():\n    return 0\n')
    with open(os.path.join(root, 'worker', 'sotto_worker.py'), 'w', encoding='utf-8') as fh:
        fh.write('import os\n')


#: (label, arm the mutation must break, mutation applied to the fixture tree)
MUTANTS = (
    ('page-loads-the-twin', 'a',
     lambda root: _append(os.path.join(root, PANEL),
                          '<script src="app/panel/history-store.js"></script>\n')),
    ('py-imports-the-reader', 'b',
     lambda root: _append(os.path.join(root, 'worker', 'sotto_worker.py'),
                          'from worker import discord_streams\n')),
    ('comment-count-drifts', 'c',
     lambda root: _append(os.path.join(root, PANEL),
                          '<script src="app-9.js"></script>\n')),
    ('twin-deleted', 'd',
     lambda root: os.remove(os.path.join(root, 'worker', PY_TWIN))),
)


def _append(path, text):
    with open(path, 'a', encoding='utf-8', newline='') as fh:
        fh.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    live = analyse(args.root)
    if not args.neg_arm:
        bad = []
        for key, title in ARMS:
            ok, detail = live[key]
            print('%-8s %s  %s' % (key.upper(), 'PASS' if ok else 'FAIL', title))
            print('         %s' % detail)
            if not ok:
                bad.append(key)
        print('VERDICT: %s (arms=%d fail=%d)'
              % ('PASS' if not bad else 'FAIL', len(ARMS), len(bad)))
        return 0 if not bad else 1

    tmp = tempfile.mkdtemp(prefix='dead-unwired-')
    caught = weak = 0
    try:
        base = os.path.join(tmp, 'base')
        _fixture(base)
        priors = analyse(base)
        for key, (ok, detail) in priors.items():
            if not ok:
                print('  RED   fixture violates its own rule: %s %s' % (key, detail))
                weak += 1
        for label, owner, mutate in MUTANTS:
            tree = os.path.join(tmp, label)
            shutil.copytree(base, tree)
            try:
                mutate(tree)
            except OSError as exc:
                print('  RED   mutant %-24s COULD NOT APPLY (%s)' % (label, exc))
                weak += 1
                continue
            got = analyse(tree)
            broken = [k for k, (ok, _d) in got.items() if not ok]
            if owner in broken:
                print('  GREEN mutant %-24s caught by: %s (%s)'
                      % (label, owner, got[owner][1]))
                caught += 1
            else:
                print('  RED   mutant %-24s SURVIVED on arm %s -- the gate is blind here'
                      % (label, owner))
        total = len(MUTANTS)
        ok = caught == total and weak == 0
        print('NEG-ARM VERDICT: %s (%d/%d mutants caught, %d decorative)'
              % ('PASS' if ok else 'FAIL', caught, total, weak))
        # House convention: a control that caught every injected defect exits 1.
        return 1 if ok else 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
