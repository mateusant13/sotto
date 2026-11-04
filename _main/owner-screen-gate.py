#!/usr/bin/env python
# NO-BUG: O DONO VE' O QUE ELE PEDIU -- E MAIS NADA. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""O DONO VE' O QUE ELE PEDIU -- E MAIS NADA.

ORDEM DELE, 2026-11-04, verbatim: *"nao faz nenhum script existente ou novo
abrir coisa na minha tela tipo pop up"*. A regra irma ja' existia para o
FOREGROUND (`AGENTS.md`, ordem de 2026-11-02: nada de janela de consola a
piscar), e esta e' a irma' que faltava: um `webbrowser.open`, um `os.startfile`,
um `MessageBoxW`, um `window.open` ou um `tkinter.Tk()` no meio de um
instrumento abre uma janela na cara dele no momento em que ele esta' a usar o PC.

O QUE ESTE ORACAO LE', E SO' ISSO -- chamadas REAIS:

    Python (via `ast`, portanto comentario e docstring nao contam):
      webbrowser.open / open_new / open_new_tab
      os.startfile
      tkinter.*, Tk(), Toplevel()
      windll.user32.MessageBoxW / MessageBoxA  (e o nome solto `MessageBoxW`)
      subprocess.* cujo argv nomeie um ABRIDOR:
          "start", "explorer", "mshta", "rundll32", "control", "ms-settings:"
          ou um URL ("http://", "https://")
      powershell / pwsh SEM `-WindowStyle Hidden`

    JavaScript (comentario e string removidos primeiro):
      window.open(  alert(  confirm(  prompt(  shell.openExternal(

O QUE ESTE ORACAO *NAO* LE', DE PROPOSITO: a janela do PROPRIO Sotto (painel,
overlay, stage), que e' o produto. Um portao que recusasse o painel recusaria a
app.

A DEBITA ANTERIOR A REGRA FICA CONGELADA em `_main/owner-screen-baseline.json`
(a mesma forma do `console-window-gate` e do `lane-screen-gate`) e NAO PODE
CRESCER: um ficheiro novo que abra um pop-up e' RED na hora, e baixar a baseline
e' uma decisao que aparece no diff.

Uso:
    python _main/owner-screen-gate.py             # julga a arvore
    python _main/owner-screen-gate.py --update    # regrava a baseline (1x, com motivo)
    python _main/owner-screen-gate.py --neg-arm   # muta uma COPIA e exige RED
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASELINE = os.path.join(HERE, 'owner-screen-baseline.json')

#: Os directórios que NAO sao produto: registos de corrida, mutantes, copias de
#: braço negativo, bibliotecas de terceiros. Julgá-los seria julgar o passado.
SKIP_DIRS = ('_audit-verify', '_neg', 'runs', '_tmp', '__pycache__', '_libs',
             '_mutants', '_design-lane', '_legacy-electron', 'node_modules',
             '_redux-gate-mutants', '_cache', '_gaps-mutant', '_gaps-g4')
#: COPIAS DE UM DEFEITO ANTIGO NAO SAO PRODUTO (2026-11-04). Os mutantes do
#: console-window e os prefixes de worker sao ficheiros GIGANTES copiados para
#: provar uma cura; julgá-los seria julgar o passado, e cada um puxaria a
#: baseline para cima com um `MessageBoxW` que ja' nao esta' em caminho nenhum.
SKIP_FILE_RX = re.compile(r'(-mutant\w*\.py$|^_strip-|^_prefix_|^_neg-|'
                          r'^_scratch-|mutant-repro|_vis-live-|^_shell-no-revive|'
                          r'^_no-audio-lift|^_tap-restart|^_restart-30s-|^_s7-)')

PY_CALLS = {
    'webbrowser.open', 'webbrowser.open_new', 'webbrowser.open_new_tab',
    'os.startfile', 'tkinter.Tk', 'tkinter.Toplevel',
    'windll.user32.MessageBoxW', 'windll.user32.MessageBoxA',
    'ctypes.windll.user32.MessageBoxW', 'ctypes.windll.user32.MessageBoxA',
}
PY_BARE = {'MessageBoxW', 'MessageBoxA', 'Tk', 'Toplevel', 'ShellExecuteW',
           'ShellExecuteA', 'ShellExecute'}
LAUNCHERS = ('subprocess.Popen', 'subprocess.run', 'subprocess.call',
             'subprocess.check_call', 'subprocess.check_output',
             'subprocess.run', 'os.system', 'os.popen')
#: Os nomes que ABREM uma janela quando aparecem como o programa do argv.
OPENER_TOKENS = ('start', 'explorer', 'explorer.exe', 'mshta', 'mshta.exe',
                 'rundll32', 'rundll32.exe', 'control', 'control.exe',
                 'ms-settings:', 'microsoft-edge:', 'http://', 'https://')
JS_PATTERNS = (
    (re.compile(r'\bwindow\.open\s*\('), 'window.open'),
    (re.compile(r'(?<![\w.$])alert\s*\('), 'alert'),
    (re.compile(r'(?<![\w.$])confirm\s*\('), 'confirm'),
    (re.compile(r'(?<![\w.$])prompt\s*\('), 'prompt'),
    (re.compile(r'\bshell\.openExternal\s*\('), 'shell.openExternal'),
    (re.compile(r'\bpywebview\.create_(confirmation|file|folder)_dialog\s*\('),
     'pywebview dialogo modal'),
)


def _rel(path):
    return os.path.relpath(path, ROOT).replace('\\', '/')


def _walk():
    for base in ('app', 'worker', '_main'):
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, base)):
            d = _rel(dirpath)
            dirnames[:] = [x for x in dirnames
                           if x not in SKIP_DIRS and not x.startswith('_gaps-')]
            if any(x in d.split('/') for x in SKIP_DIRS):
                continue
            for name in filenames:
                if name.endswith(('.py', '.js', '.mjs')):
                    if SKIP_FILE_RX.search(name):
                        continue
                    yield os.path.join(dirpath, name)


def _dotted(node):
    """`a.b.c` for a Name/Attribute chain, '' for anything else."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    elif isinstance(cur, ast.Attribute):
        return ''
    return '.'.join(reversed(parts))


def _argv_strings(node):
    """Every literal string that could be the PROGRAM of a launch call."""
    out = []
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            out.append(arg.value)
        elif isinstance(arg, (ast.List, ast.Tuple)):
            for el in arg.elts:
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    out.append(el.value)
        elif isinstance(arg, ast.Name):
            # `argv` variable: cannot be read here, and that is said, not guessed
            out.append('<var>')
    return out


def _python_findings(path, src):
    findings = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        short = name.split('.')[-1]
        if name in PY_CALLS or (short in PY_BARE and not name.startswith('self.')):
            findings.append((node.lineno, name))
            continue
        if name in LAUNCHERS:
            # PALAVRAS, NAO SUBSTRINGS (2026-11-04). A primeira versao casava
            # `'control' in joined` e o achado saiu do acelerador
            # `--hotkey=Control+Alt+Shift+F9`: um falso positivo que so' custa
            # credibilidade ao portao.
            tokens = []
            for value in _argv_strings(node):
                tokens.extend(re.split(r'[\s,;=]+', str(value).lower()))
            tokens = [t.strip('"\'') for t in tokens if t.strip('"\'')]
            bare = [t[:-4] if t.endswith('.exe') else t for t in tokens]
            flags = ' '.join(
                str(k.arg).lower() for k in node.keywords if k.arg)
            for tok in OPENER_TOKENS:
                tok_bare = tok[:-4] if tok.endswith('.exe') else tok
                if tok_bare in bare or any(t.startswith(tok) for t in bare
                                           if tok.endswith(':')):
                    findings.append((node.lineno, '%s -> %r' % (name, tok)))
                    break
            if 'powershell' in bare or 'pwsh' in bare:
                # `-WindowStyle Hidden` OU `creationflags=CREATE_NO_WINDOW`:
                # as duas escondem, e a casa aceita as duas (a segunda e' a que
                # o `console-window-gate` exige dos `Popen`).
                hidden = ('-windowstyle' in tokens or
                          'nocreate' in flags or 'creationflags' in flags)
                if not hidden:
                    findings.append(
                        (node.lineno, '%s -> powershell sem -WindowStyle Hidden'
                         % name))
            if 'electron' in bare or any(t.endswith('electron.cmd') for t in bare):
                findings.append((node.lineno, '%s -> electron (app morta)'
                                 % name))
            continue
        if name.endswith('create_confirmation_dialog') or name.endswith(
                'create_file_dialog') or name.endswith('create_folder_dialog'):
            findings.append((node.lineno, name))
    return findings


_JS_STRIP = re.compile(
    r'//[^\n]*|/\*.*?\*/|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`',
    re.S)


def _js_findings(path, src):
    stripped = _JS_STRIP.sub('""', src)   # strings and comments out, one pass
    findings = []
    for rx, label in JS_PATTERNS:
        for m in rx.finditer(stripped):
            findings.append((stripped[:m.start()].count('\n') + 1, label))
    return findings


def judge():
    """-> {rel: [(line, what), ...]} for every file with a finding."""
    out = {}
    for path in _walk():
        rel = _rel(path)
        try:
            src = io.open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        found = (_js_findings(path, src) if path.endswith(('.js', '.mjs'))
                 else _python_findings(path, src))
        if found:
            out[rel] = sorted(set(found))
    return out


def _baseline():
    try:
        return json.load(io.open(BASELINE, encoding='utf-8'))
    except Exception:                     # noqa: BLE001 -- ausente = zero
        return {'ceiling': 0, 'files': {}}


def _mutant(make_red):
    """A COPIA onde o defeito existe, para o braco negativo ter o que apanhar."""
    tmpdir = tempfile.mkdtemp(prefix='owner-screen-neg-')
    try:
        src = os.path.join(ROOT, '_main', '_zz-negarm-browser-open.py')
        io.open(src, 'w', encoding='utf-8', newline='\\n').write(
            'import webbrowser\n\n\n'
            'def probe():\n'
            '    webbrowser.open("https://example.com")\n')
        return tmpdir, src
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main(argv):
    neg = '--neg-arm' in argv
    if neg:
        # O BRACO NEGATIVO NAO MUTA A ARVORE: escreve um ficheiro que ABRE um
        # pop-up dentro de `_main/`, exige que o `judge()` o apanhe, e apaga-o.
        src = os.path.join(ROOT, '_main', '_zz-negarm-browser-open.py')
        payload = ('import webbrowser\n\n\ndef probe():\n'
                   '    webbrowser.open("https://example.com")\n')
        io.open(src, 'w', encoding='utf-8', newline='\n').write(payload)
        try:
            got = judge()
            caught = [f for f in got if f.endswith('_zz-negarm-browser-open.py')]
        finally:
            try:
                os.remove(src)
            except OSError:
                pass
        if caught:
            print('NEG-ARM PASS (RED as designed) -- mutante derrubou: %s'
                  % ', '.join(caught))
            return 1
        print('NEG-ARM FAIL -- o mutante que abre um browser NAO foi apanhado')
        return 0

    if '--update' in argv:
        got = judge()
        io.open(BASELINE, 'w', encoding='utf-8').write(
            json.dumps({'ceiling': sum(len(v) for v in got.values()),
                        'files': got}, indent=2, sort_keys=True) + '\n')
        print('OWNER-SCREEN baseline gravada: %d achado(s) em %d ficheiro(s)'
              % (sum(len(v) for v in got.values()), len(got)))
        return 0

    base = _baseline()
    got = judge()
    total = sum(len(v) for v in got.values())
    ceiling = int(base.get('ceiling', 0) or 0)
    print('populacao: %d ficheiro(s) de produto; achados=%d baseline=%d'
          % (len(list(_walk())), total, ceiling))
    for rel in sorted(got):
        for line, what in got[rel]:
            print('  %s:%d  %s' % (rel, line, what))
    if total <= ceiling:
        print('OWNER-SCREEN VERDICT PASS -- nenhum script abre janela no ecra do '
              'dono (achados=%d <= baseline=%d)' % (total, ceiling))
        return 0
    print('OWNER-SCREEN VERDICT FAIL -- %d achado(s) acima da baseline de %d'
          % (total, ceiling))
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
