# NO-BUG: Does the shell log the panel's paint row? The seam the eye leg runs through.
"""Does the shell log the panel's paint row? The seam the eye leg runs through.

The panel has produced `CAPTION_PROVISIONAL_PAINT` since the PanelCommitOnStable lane: the row is the
ONLY measurement of the moment the caption reaches the eye (`push -> paint`), and `commit` -- which the
shell logged -- is the END of what the eye already saw. Measured by that lane: push->paint p50 0 ms,
paint->commit p50 839 / p95 1500 ms. The row existed for DOM probes only because the shell installed no
`SottoPaintSink`; two lines close it (`BOOTSTRAP_JS` installs the hook, the handler table routes
`paint-row` to `_paint_row`).

This gate proves the three halves against the shipped file, and refuses to be green when any of them is
disarmed -- a seam gate that only greps for a name is decoration:

  python _main/paint-row-seam-oracle.py
  python _main/paint-row-seam-oracle.py --neg-arm
"""
from __future__ import annotations

import io
import os
import re
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
PANEL = os.path.join(ROOT, 'app', 'panel', 'panel.js')


def read(path):
    if not os.path.isfile(path):
        return None
    return io.open(path, encoding='utf-8', errors='replace').read()


def arms(src, panel):
    res = {}
    if src is None or panel is None:
        return {'shell_and_panel_exist': False}

    # 1. the panel still emits the row and calls the hook
    res['panel_emits_row'] = ("'CAPTION_PROVISIONAL_PAINT'" in panel
                              and 'SottoPaintSink(row)' in panel)
    # 2. the bootstrap installs the hook, and it uses the panel's own formatter
    res['bootstrap_installs_sink'] = (
        'window.SottoPaintSink = function' in src
        and "post('paint-row'" in src
        and 'window.SottoPaintLine(row)' in src)
    # 3. the handler table routes the kind, and the handler logs it
    res['handler_routed'] = ("'paint-row': ('host', '_paint_row')" in src
                             and 'def _paint_row(self, payload)' in src)
    m = re.search(r'def _paint_row\(self, payload\):(.*?)\n    def ', src, re.S)
    body = m.group(1) if m else ''
    res['handler_logs_and_caps'] = ('log(line)' in body and '[:400]' in body
                                    and "startswith('CAPTION_PROVISIONAL_PAINT')" in body)
    return res


def behavioural(src):
    """Drive the REAL handler: a good row logs, junk is refused, long is capped."""
    if src is None:
        return {'handler_behaves': False}, 'no shell file'
    ns = {}
    m = re.search(r'^def log\(.*?(?=^def )', src, re.S | re.M)
    logged = []
    ns['log'] = lambda msg, *a, **k: logged.append(msg)
    m = re.search(r'    def _paint_row\(self, payload\):.*?(?=\n    def )', src, re.S)
    if not m:
        return {'handler_behaves': False}, 'no _paint_row'
    exec(compile('class H(object):\n' + m.group(0), SHELL, 'exec'), ns)
    h = ns['H']()
    h._paint_row({'line': 'CAPTION_PROVISIONAL_PAINT n=1 at=2 id="x" src=- '
                          'conf=t prov=t text="oi"'})
    h._paint_row({'line': 'PANEL_SOMETHING n=1'})
    h._paint_row({})
    h._paint_row({'line': 'CAPTION_PROVISIONAL_PAINT ' + 'x' * 900})
    detail = (f'logged={len(logged)} longest={max((len(x) for x in logged), default=0)}')
    ok = (len(logged) == 2 and all(x.startswith('CAPTION_PROVISIONAL_PAINT')
                                  for x in logged)
          and max((len(x) for x in logged), default=0) <= 400)
    return {'handler_behaves': ok}, detail


def main(argv=None):
    argv = argv or sys.argv[1:]
    src, panel = read(SHELL), read(PANEL)
    res = arms(src, panel)
    for name, ok in res.items():
        print(f'CHECK {name} {"PASS" if ok else "FAIL"}')
    beh, detail = behavioural(src)
    res.update(beh)
    print(f'CHECK handler_behaves {"PASS" if beh["handler_behaves"] else "FAIL"} {detail}')
    if '--neg-arm' in argv:
        import tempfile
        # `TMPDIR` nao esta' sempre definido numa shell desta casa, e um fallback
        # de `'.'` deixou DOIS diretorios `paintrow-*` na raiz do repo (medido
        # 2026-11-04). `gettempdir()` e' o que responde quando a variavel falta.
        tmp = tempfile.mkdtemp(prefix='paintrow-',
                               dir=os.environ.get('TMPDIR')
                               or tempfile.gettempdir())
        mutants = {
            'sink_removed': src.replace('window.SottoPaintSink = function',
                                        'window.__dead_sink = function', 1),
            'route_removed': src.replace("'paint-row': ('host', '_paint_row')",
                                         "'paint-row-disabled': ('host', "
                                         "'_paint_row')", 1),
            # The FIRST `[:400]` in the file is not necessarily the handler's:
            # a mutation that lands elsewhere proves nothing about the cap.
            'cap_removed': re.sub(r"(def _paint_row\(self, payload\):.*?)\[:400\]",
                                  r"\1[:100000]", src, count=1, flags=re.S),
        }
        caught = 0
        for name, text in mutants.items():
            path = os.path.join(tmp, name + '.py')
            io.open(path, 'w', encoding='utf-8').write(text)
            r = arms(text, panel)
            ok = not all(r.values())
            if name == 'cap_removed':
                beh2, _ = behavioural(text)
                ok = (not beh2['handler_behaves']) or ok
            caught += int(ok)
            print(f'MUTANT {name}: {"CAUGHT" if ok else "NOT-CAUGHT"}')
        print(f'NEG-ARM SUMMARY cases={len(mutants)} caught={caught}')
        print('NEG-ARM: PASS' if caught == len(mutants) else 'NEG-ARM: FAIL')
        # rc=1 POR DESENHO quando o braco passa (a convencao desta arvore, escrita
        # em `_main/_audit-verify-all.cmd:1261`: "o negativo responde rc=1 quando
        # apanha os mutantes, e 0 quando um escapa"). O `:expectred` declara rc=1
        # e a frase `NEG-ARM: PASS`; este ficheiro respondia 0 ao apanhar os tres,
        # logo o passo ficou vermelho a fazer tudo certo -- medido na bateria de
        # 2026-11-05: `red-as-expected-paint-row-seam=0` com `caught=3` no log.
        return 1 if caught == len(mutants) else 0
    bad = [k for k, v in res.items() if not v]
    print('VERDICT:', 'PASS' if not bad else 'FAIL ' + ' '.join(bad))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
