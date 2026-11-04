"""CODEMOD: STAMP THE CONSOLE PAIR ONTO EVERY `creationflags` SPAWN.

MEASURED 2026-11-04 on the owner's screen: `creationflags=CREATE_NO_WINDOW`
alone does NOT hide a console window when the PARENT has no console (a
`Popen(['cmd','/c','ping',...], 0x08000000)` painted a full `ping` window). The
half that was missing everywhere in this tree is the `STARTUPINFO` that says
`SW_HIDE`.

`_main/console-window-audit.py` now refuses a spawn with `creationflags` and no
`startupinfo` (class `WEAK-FLAG`) and freezes the existing debt in
`_main/console-weakflag-baseline.json`. This script is the burn-down: it inserts
`startupinfo=<mod>.STARTUPINFO(dwFlags=<mod>.STARTF_USESHOWWINDOW, wShowWindow=0)`
right after the `creationflags=` argument of every call that lacks it.

IT ONLY TOUCHES WHAT IT CAN PROVE: a call whose `creationflags` keyword is
already accompanied by `startupinfo`, or that splats `**kwargs`, is left alone
(that is what the baseline is for). It refuses to guess a module alias it cannot
see in the file.

    python _main/_console-pair-codemod.py            # dry run, prints counts
    python _main/_console-pair-codemod.py --apply    # writes the files
"""

from __future__ import annotations

import ast
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', '_cache', '_audit-verify', 'node_modules', '__pycache__',
             'skills', 'agents'}
#: A pasta `app/` e `worker/` FICARAM DE FORA de proposito: os seis sitios de
#: produto passam por `app/webview/no_console.py`, que e' a receita canonica.
AREAS = ('_main', 'probe', 'tools', 'docs')

SNIPPET = ('startupinfo=%s.STARTUPINFO(dwFlags=%s.STARTF_USESHOWWINDOW, '
           'wShowWindow=0)')


def _modname(src, tree):
    """O nome por que `subprocess` e' conhecido NESTE ficheiro, ou None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == 'subprocess':
                    return a.asname or 'subprocess'
    return None


def _iter_files():
    for area in AREAS:
        base = os.path.join(ROOT, area)
        for dirpath, dirnames, files in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in files:
                if f.endswith('.py'):
                    yield os.path.join(dirpath, f)


def _edits_for(path, src):
    """[(offset, text)] para inserir o par, ou [] quando nao ha' o que fazer."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [], 'unparsed'
    mod = _modname(src, tree)
    if mod is None:
        return [], 'no-import'
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kws = {k.arg: k for k in node.keywords if k.arg}
        if 'creationflags' not in kws or 'startupinfo' in kws:
            continue
        if any(k.arg is None for k in node.keywords):
            continue                      # `**kwargs`: nao se mexe
        val = kws['creationflags'].value
        end = _offset(src, val.end_lineno, val.end_col_offset)
        out.append((end, ', ' + (SNIPPET % (mod, mod))))
    return out, 'ok'


def _offset(src, lineno, col):
    """Offset absoluto de (linha, coluna) 1-based/0-based do ast."""
    line_starts = [0]
    for i, ch in enumerate(src):
        if ch == '\n':
            line_starts.append(i + 1)
    return line_starts[lineno - 1] + col


def main(argv):
    apply_ = '--apply' in argv
    touched = files = skipped = 0
    for path in _iter_files():
        raw = io.open(path, encoding='utf-8', newline='').read()
        crlf = '\r\n' in raw
        src = raw.replace('\r\n', '\n')
        edits, why = _edits_for(path, src)
        if why != 'ok':
            skipped += 1
            continue
        if not edits:
            continue
        files += 1
        touched += len(edits)
        print('%-52s %d sitio(s)' % (os.path.relpath(path, ROOT), len(edits)))
        if not apply_:
            continue
        for off, text in sorted(edits, reverse=True):
            src = src[:off] + text + src[off:]
        if crlf:
            src = src.replace('\n', '\r\n')
        io.open(path, 'w', encoding='utf-8', newline='').write(src)
    print('\n%s: %d ficheiro(s), %d sitio(s); %d ficheiro(s) sem import de '
          'subprocess (ficam no baseline)'
          % ('APPLIED' if apply_ else 'DRY RUN', files, touched, skipped))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
