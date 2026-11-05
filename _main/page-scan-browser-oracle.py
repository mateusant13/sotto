"""A VARREDURA DA PAGINA NAO CORRE NUM BROWSER -- e o log tem de mostrar isso.

DEFEITO MEDIDO, 2026-11-05, na instancia VIVA do dono (pid 62492, log
`_main/webview-run.log`), com o video do YouTube PAUSADO:

    EXTERNAL_CAPTIONS_READ_MS ms=1593.0 phases={'import': 0.0, 'target': 0.0,
                                                'source': 0.0, 'end': 1593.0}
    EXTERNAL_CAPTIONS_READ_MS ms=1547.0 ...
    EXTERNAL_CAPTIONS_READ_MS ms=1812.0 ...

Toda a leitura dentro da varredura UIA da janela do Chrome inteira, uma vez a
cada 5 s (o tecto da rede), para concluir que uma pagina parada nao tem legenda.
A varredura existe por UMA razao -- players que PINTAM a legenda na propria
pagina (Stremio/Electron). Um browser com barra de endereco e' lido pela CDP
(`youtube_cdp_source`) ou pela arvore da legenda; nunca por pintura de pagina.

O QUE ESTE ORACULO EXECUTA (nao julga texto)

  A1  `_is_browser` sobre os processos que pintam legenda na pagina: Electron,
      Stremio, VLC, mpv  ->  False (a varredura TEM de correr para eles).
  A2  `_is_browser` sobre os browsers: chrome, msedge, firefox, brave
      ->  True (a varredura NAO corre).
  A3  A guarda existe DENTRO de `_read_inner`, num sitio que precede a chamada
      a `external_subs.caption_lines` -- lida por `ast`, nao por regex, e na
      ordem em que o codigo corre.
  A4  A guarda le a IDENTIDADE da janela (`_process_name`) e nao o silencio da
      leitura anterior: uma leitura vazia nao e' prova de que a janela nao pinta.

BRAÇO NEGATIVO (`--neg-arm`): muta o `_is_browser` da guarda para `lambda hwnd:
False`, numa COPIA do shell, e exige que A3 caia (a guarda deixa de estar la').

USO
    python _main/page-scan-browser-oracle.py [--neg-arm]
"""
from __future__ import annotations

import ast
import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
SUBS = os.path.join(ROOT, 'app', 'webview', 'external_subs.py')

ROWS = []


def add(ok, title, detail=''):
    ROWS.append((bool(ok), title, str(detail)[:160]))
    print(('PASS ' if ok else 'FAIL ') + title + (('   [' + str(detail)[:160] + ']') if detail and not ok else ''))


def _src(path):
    raw = io.open(path, 'rb').read()
    return raw.decode('utf-8').replace('\r\n', '\n')


def _find_inner(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _walk_calls(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            label = ''
            if isinstance(f, ast.Attribute):
                label = f.attr
            elif isinstance(f, ast.Name):
                label = f.id
            yield sub, label


def arms():
    sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
    import external_subs

    # A1: quem PINTA a legenda na pagina
    page_painters = ['electron.exe', 'Stremio.exe', 'vlc.exe', 'mpv.exe']
    bad = [p for p in page_painters if external_subs._is_browser(p)]
    add(not bad, 'A1 quem pinta na pagina nao e browser (a varredura corre para ele)',
        'chamados de browser por engano: %r' % bad)

    # A2: browsers de verdade
    browsers = ['chrome.exe', 'msedge.exe', 'firefox.exe', 'brave.exe']
    miss = [p for p in browsers if not external_subs._is_browser(p)]
    add(not miss, 'A2 o browser e nomeado como browser', 'nao reconhecidos: %r' % miss)

    # A3: a guarda esta' DENTRO de _read_inner e ANTES da varredura
    tree = ast.parse(_src(SHELL))
    fn = _find_inner(tree, '_read_inner')
    if fn is None:
        add(False, 'A3 a guarda precede a varredura em _read_inner', 'funcao ausente')
        return
    guard_line = None
    scan_line = None
    for sub, label in _walk_calls(fn):
        if label == '_is_browser' and guard_line is None:
            guard_line = sub.lineno
        if label == 'caption_lines' and scan_line is None:
            scan_line = sub.lineno
    ok = guard_line is not None and scan_line is not None and guard_line < scan_line
    add(ok, 'A3 a guarda precede a varredura em _read_inner',
        'guarda=%r varredura=%r' % (guard_line, scan_line))

    # A4: a guarda le a IDENTIDADE da janela
    body = ast.get_source_segment(_src(SHELL), fn) or ''
    add('_process_name' in body, 'A4 a guarda le a identidade da janela (_process_name)',
        'a guarda nao nomeia o processo')


def neg_arm():
    global SHELL
    src = _src(SHELL)
    # A guarda vira `False`: nada e' browser, a varredura corre sempre.
    mutated = re.sub(r'external_subs\._is_browser\(external_subs\._process_name\(hwnd\)\)',
                     'False', src, count=1)
    if mutated == src:
        print('NEG-ARM IMPOSSIVEL -- a guarda nao foi encontrada para mutar')
        return 2
    tmp = os.path.join(tempfile.mkdtemp(prefix='neg-page-scan-'), 'sotto_webview.py')
    io.open(tmp, 'w', encoding='utf-8', newline='').write(mutated)
    real = SHELL
    SHELL = tmp
    try:
        ROWS.clear()
        print('=== NEG-ARM: a guarda desarmada numa COPIA')
        arms()
        red = [r for r in ROWS if not r[0]]
        ok = any('A3' in r[1] for r in red)
        print('NEG-ARM %s -- %d arm(s) RED, A3 entre elas=%s'
              % ('PASS' if ok else 'FAIL', len(red), ok))
        # THE HOUSE CONVENTION FOR AN EXPECT-RED STEP (2026-11-05): catching the
        # injected defect EXITS 1, because that is what `:expectred` in
        # `_main/_audit-verify-all.cmd` requires (`rc=0 means the control did NOT
        # go red`). Returning 0 here made the battery record the arm as a plain
        # gate that could never fail -- a control answering as a pass.
        return 1 if ok else 0
    finally:
        SHELL = real
        try:
            os.remove(tmp)
            os.rmdir(os.path.dirname(tmp))
        except OSError:
            pass


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    arms()
    bad = [r for r in ROWS if not r[0]]
    print('\n%d/%d arms green' % (len(ROWS) - len(bad), len(ROWS)))
    print('VERDICT: ' + ('PASS' if not bad else 'FAIL'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
