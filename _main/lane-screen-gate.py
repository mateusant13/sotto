#!/usr/bin/env python.exe
# -*- coding: utf-8 -*-
# NO-BUG: este ficheiro e o portao de uma REGRA, nao uma correccao de codigo.
"""LANE-SCREEN-GATE -- o dono nunca mais ve o Sotto na tela dele por causa de uma lane.

A ORDEM, verbatim (2026-10-23, e a segunda vez que ele a deu):

    *"para de abrir essa merda na minha tela. tu vai resolver no teu ambiente
    ai sem encher o meu saco"*

    e, quando lhe expliquei que a app tem seams proprios:

    *"entao nunca mais faz isso. faz gates ou agents.md"*

## Porque e que isto e um portao e nao uma promessa

A falha nao foi nao saber. Foi nao haver nada que me impedisse de repetir. Em
2026-10-23 23:23 a app subiu com `--show` e o painel ficou no ecra dele
(`PANEL_VISIBILITY_ON_SCREEN visible=true`) enquanto ele trabalhava. Antes
disso, `_main/press-alt-c.py` disparou `keybd_event` quatro vezes a pensar que
isso era um teste -- e nao era: os quatro `err=0` provam que o WINDOWS aceitou
as teclas, e as **zero** linhas no log da app provam que o SOTTO nunca as viu.
Um instrumento que mede o sistema operativo, com o nome de teste da app, e o
instrumento errado; foi assim que gastei o tempo dele.

## Os tres bracos

1. `synthetic-input` -- nenhum instrumento de lane (`_main/*.py` de nivel 1)
   ADICIONA `keybd_event`, `SendInput`, `mouse_event`, `SendKeys` ou
   `BlockInput`. Um evento sintetico nao e evidencia sobre a app: e evidencia
   sobre o Windows.

2. `lane-launcher-visible` -- um HARNESS de lane (nome `keepalive*`, `*lane*`,
   `launch*`, `press*`) nunca pede `--show`. `--show` e a bandeira que faz o
   painel nascer no ecra do dono.

3. `agents-rule` -- a lei tem de estar ESCRITA onde e auto-carregada. O braco
   exige o marcador `SOTTO_NEVER_ON_OWNER_SCREEN` em `AGENTS.md`. E o mesmo
   idioma dos pins deste repo.

## O BASELINE, e porque ele existe

A regra e de 2026-10-23; **21 instrumentos anteriores a ela** usam input
sintetico (`alt-c-e2e-probe.py`, `hotkey-paint-probe.py`, `strip-*`, ...). Nao
os apago: sao a arqueologia que explica decisoes medidas do app, e apaga-los
seria reescrever a historia para o portao ficar bonito.

O `_main/lane-screen-baseline.json` CONGELA essa divida -- nome e contagem -- e
o portao fica vermelho:

  * se aparecer um ficheiro que nao esta no baseline  (instrumento NOVO), e
  * se um ficheiro do baseline CRESCER                (mais um sitio a injectar).

E assim que a regra se cumpre sem mentir sobre o passado: o que existe fica
contado, o que vier a seguir tem de nascer sem tocar no ecra do dono.

## Uso

    python _main\\lane-screen-gate.py            # rc=0 PASS, rc=1 FAIL
    python _main\\lane-screen-gate.py --neg-arm  # rc=1 BY DESIGN (e controlo)

O braco negativo e obrigatorio: um detector que nunca foi visto a ficar
vermelho nao e um detector, e uma funcao que devolve texto.
"""
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
MAIN = os.path.join(ROOT, '_main')
AGENTS = os.path.join(ROOT, 'AGENTS.md')
BASELINE = os.path.join(MAIN, 'lane-screen-baseline.json')

#: Este ficheiro DECLARA os padroes; olhar para ele seria o detetor a morder-se.
SELF_NAME = 'lane-screen-gate.py'

#: Chamadas que INJECTAM input no sistema. Ver o cabecalho: medem o Windows.
SYNTHETIC = re.compile(
    r'\b(keybd_event|SendInput|mouse_event|BlockInput|SendKeys)\b')

#: Os MESMOS nomes como conjunto, para o censo por `ast` dos `.py` (uma CHAMADA
#: injecta; um literal que os nomeia, nao).
SYNTHETIC_NAMES = frozenset(('keybd_event', 'SendInput', 'mouse_event',
                             'BlockInput', 'SendKeys'))

#: Nomes de ficheiro que sao HARNESS de lane, nao oraculo de painel.
LANE_HARNESS = re.compile(r'(keepalive|launch|lane|press)', re.I)

#: A bandeira que faz o painel nascer visivel.
SHOW_FLAG = '--show'

#: O marcador da lei em AGENTS.md.
RULE_MARKER = 'SOTTO_NEVER_ON_OWNER_SCREEN'

EXTENSIONS = ('.py', '.cmd', '.bat', '.ps1')


def _depth_one_files(main_dir):
    """So o nivel 1 de `_main`: os instrumentos de lane vivem aqui.

    Os subdirectorios `_gaps-*` e `_redux-gate-mutants` sao copias MUTANTES do
    proprio `sotto_webview.py` -- usam `keybd_event` e `--show` por heranca do
    app, e olhar para dentro deles era punir o portao por existir.
    """
    out = []
    try:
        names = sorted(os.listdir(main_dir))
    except OSError:
        return out
    for name in names:
        path = os.path.join(main_dir, name)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(name)[1].lower() in EXTENSIONS:
            out.append(path)
    return out


def _read(path):
    try:
        with io.open(path, 'r', encoding='utf-8', errors='replace') as handle:
            return handle.read()
    except OSError:
        return ''


def _cut_inline(line, marker):
    """Corta um comentario no fim da linha, sem tocar dentro de aspas."""
    quote = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char == marker:
            return line[:index]
    return line


def code_lines(text, ext):
    """So as linhas de CODIGO -- comentarios e docstrings ficam de fora.

    O `keepalive.py` diz, num comentario, a regra "nunca `--show`". Se o detector
    contasse comentarios, punha vermelho exactamente o ficheiro que cumpre a lei,
    e o baseline ficava a perdoar duas chamadas que nao existem. Quem documenta a
    regra nao pode ser tratado como quem a quebra.
    """
    in_triple = None
    for raw in text.splitlines():
        line = raw.strip()
        if in_triple:
            if in_triple in line:
                in_triple = None
            continue
        opened = None
        for token in ('"""', "'''"):
            if line.startswith(token):
                if line.count(token) % 2 == 1:
                    opened = token
                break
        if opened:
            in_triple = opened
            continue
        if ext in ('.cmd', '.bat', '.ps1'):
            if (line.upper().startswith('REM') or line.startswith('::')
                    or line.startswith('#')):
                continue
            yield _cut_inline(raw, '#')
        else:
            if line.startswith('#'):
                continue
            yield _cut_inline(raw, '#')


def _synthetic_calls_py(path):
    """As CHAMADAS de input sintetico num `.py` -- por `ast`, nao por texto.

    MEDIDO 2026-11-04: um ORACULO que NOMEIA as APIs para as proibir
    (`KEY_EATING = ('RegisterHotKey', 'keybd_event', ...)`) era acusado de as
    CHAMAR -- a regex lia o literal de uma string como se fosse uma chamada, e o
    portao punha vermelho o ficheiro que existe para provar a ausencia delas. Um
    literal nao injecta nada: so' uma CHAMADA injecta. O texto continua a ser o
    caminho para `.cmd/.bat/.ps1` (onde nao ha' AST) e para um `.py` que nao
    parseia.
    """
    try:
        tree = ast.parse(_read(path))
    except (SyntaxError, ValueError):
        return None
    found = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (func.attr if isinstance(func, ast.Attribute)
                else func.id if isinstance(func, ast.Name) else '')
        if name in SYNTHETIC_NAMES:
            found += 1
    return found


def counts(main_dir):
    """{nome: n} para cada classe de violacao, medido AGORA, so em codigo."""
    synth, show = {}, {}
    for path in _depth_one_files(main_dir):
        name = os.path.basename(path)
        if name == SELF_NAME:
            continue
        ext = os.path.splitext(name)[1].lower()
        code = '\n'.join(code_lines(_read(path), ext))
        found = None
        if ext == '.py':
            found = _synthetic_calls_py(path)
        if found is None:
            found = len(SYNTHETIC.findall(code))
        if found:
            synth[name] = found
        stem = os.path.splitext(name)[0]
        if LANE_HARNESS.search(stem):
            asked = code.count(SHOW_FLAG)
            if asked:
                show[name] = asked
    return synth, show


def load_baseline(path):
    try:
        with io.open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}, {}
    return (data.get('synthetic') or {}), (data.get('lane_show') or {})


def scan(main_dir, agents_path, baseline=None):
    """Devolve as falhas. Vazia == verde.

    `baseline=None` == modo ESTRITO (sem historia perdoada). O braco negativo
    usa-o para que os mutantes sejam apanhados mesmo com o baseline real cheio.
    """
    base_synth, base_show = (baseline
                             if baseline is not None
                             else (None, None))
    strict = baseline is None
    failures = []
    synth, show = counts(main_dir)

    for name, found in sorted(synth.items()):
        if strict:
            failures.append(
                'synthetic-input %s tem %d chamada(s) -- modo estrito, nenhuma e '
                'perdoada' % (name, found))
            continue
        allowed = (base_synth or {}).get(name)
        if allowed is None:
            failures.append(
                'synthetic-input %s tem %d chamada(s) e NAO esta no baseline -- '
                'instrumento novo de input sintetico' % (name, found))
        elif found > allowed:
            failures.append(
                'synthetic-input %s CRESCEU de %d para %d -- mais um sitio a '
                'injectar eventos' % (name, allowed, found))

    for name, found in sorted(show.items()):
        if strict:
            failures.append(
                'lane-launcher-visible %s pede %s -- modo estrito, nenhum pedido '
                'e perdoado' % (name, SHOW_FLAG))
            continue
        allowed = (base_show or {}).get(name)
        if allowed is None:
            failures.append(
                'lane-launcher-visible %s pede %s e NAO esta no baseline -- um '
                'harness novo a nascer no ecra do dono' % (name, SHOW_FLAG))
        elif found > allowed:
            failures.append(
                'lane-launcher-visible %s CRESCEU de %d para %d pedidos de %s'
                % (name, allowed, found, SHOW_FLAG))

    text = _read(agents_path)
    if RULE_MARKER not in text:
        failures.append(
            'agents-rule AGENTS.md nao contem o marcador %s -- a lei deixou de '
            'estar onde e auto-carregada' % RULE_MARKER)
    return failures


# --------------------------------------------------------------------------
# Braco negativo: mutantes que TEM de ficar vermelhos.
# --------------------------------------------------------------------------

CLEAN_PY = '''import subprocess
subprocess.Popen(['cmd.exe', '/c', 'Sotto.cmd'], cwd='H:/sotto')
'''

MUTANT_SYNTHETIC = '''import ctypes
user32 = ctypes.WinDLL('user32')
user32.keybd_event(0x12, 0, 0, 0)
'''

MUTANT_SHOW = '''import subprocess
subprocess.Popen(['cmd.exe', '/c', 'Sotto.cmd --show'], cwd='H:/sotto')
'''

MUTANT_GROWTH = '''import ctypes
user32 = ctypes.WinDLL('user32')
user32.keybd_event(0x12, 0, 0, 0)  # uma segunda chamada, num ficheiro ja contado
'''


def _write(path, text):
    with io.open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def run_neg_arm():
    tmp = tempfile.mkdtemp(prefix='lane-screen-gate-')
    caught = 0
    mutants = 0
    try:
        # Controlo: um harness limpo, com a lei escrita, TEM de passar.
        clean_main = os.path.join(tmp, 'clean', '_main')
        os.makedirs(clean_main)
        _write(os.path.join(clean_main, 'keepalive.py'), CLEAN_PY)
        clean_agents = os.path.join(tmp, 'clean', 'AGENTS.md')
        _write(clean_agents, 'regra: %s\n' % RULE_MARKER)
        control = scan(clean_main, clean_agents)
        print('control (limpo)                          -> %s'
              % ('VERDE' if not control else 'VERMELHO: %s' % control[0]))
        if control:
            print('NEG-ARM FAIL: o controlo limpo ficou vermelho')
            return 1

        cases = [
            ('M1 keybd_event num instrumento de nivel 1', 'press-alt-c.py',
             MUTANT_SYNTHETIC, None),
            ('M2 harness de lane a pedir --show', 'keepalive.py',
             MUTANT_SHOW, None),
            ('M3 AGENTS.md sem o marcador da lei', None,
             None, 'sem regra escrita'),
            ('M4 ficheiro do baseline a CRESCER', 'alt-c-e2e-probe.py',
             MUTANT_SYNTHETIC + MUTANT_GROWTH,
             {'synthetic': {'alt-c-e2e-probe.py': 1}, 'lane_show': {}}),
        ]
        for label, name, body, extra in cases:
            mutants += 1
            case_main = os.path.join(tmp, 'm%d' % mutants, '_main')
            os.makedirs(case_main)
            if name is None:
                _write(os.path.join(case_main, 'keepalive.py'), CLEAN_PY)
                agents = os.path.join(tmp, 'm%d' % mutants, 'AGENTS.md')
                _write(agents, 'nenhuma regra escrita aqui\n')
                found = scan(case_main, agents)
            else:
                _write(os.path.join(case_main, name), body)
                agents = os.path.join(tmp, 'm%d' % mutants, 'AGENTS.md')
                _write(agents, 'regra: %s\n' % RULE_MARKER)
                # O M4 traz um baseline PARCIAL de proposito: um ficheiro ja
                # contado nao pode crescer. Sem baseline, o modo e estrito.
                if isinstance(extra, dict):
                    base = (extra.get('synthetic') or {},
                            extra.get('lane_show') or {})
                else:
                    base = extra
                found = scan(case_main, agents, base)
            if found:
                caught += 1
                print('%-42s -> VERMELHO (%s)'
                      % (label, found[0].split(' -- ')[0]))
            else:
                print('%-42s -> VERDE (nao apanhado)' % label)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if caught != mutants:
        print('NEG-ARM FAIL: %d de %d mutantes apanhados' % (caught, mutants))
        return 1
    print('NEG-ARM PASS: %d mutantes, todos apanhados' % mutants)
    # rc=1 BY DESIGN: o braco negativo e um controlo; o `:expectred` da bateria
    # exige rc=1 e a linha acima.
    return 1


def main(argv):
    if '--neg-arm' in argv:
        return run_neg_arm()

    print('lane-screen-gate -- a app nunca no ecra do dono por causa de uma lane')
    baseline = load_baseline(BASELINE)
    failures = scan(MAIN, AGENTS, baseline)
    checks = 3
    for prefix, label in (('synthetic-input', '1 synthetic-input       '),
                          ('lane-launcher-visible', '2 lane-launcher-visible '),
                          ('agents-rule', '3 agents-rule           ')):
        red = any(item.startswith(prefix) for item in failures)
        print('  braco %s: %s' % (label, 'VERMELHO' if red else 'verde'))
    base_synth, base_show = baseline
    print('  baseline congelado: %d ficheiro(s) com input sintetico, '
          '%d harness(es) com %s (divida antiga, NAO pode crescer)'
          % (len(base_synth), len(base_show), SHOW_FLAG))
    for failure in failures:
        print('  FAIL ' + failure)
    if failures:
        print('VERDICT: FAIL -- %d falha(s)' % len(failures))
        print('BATTERY-VERDICT lane-screen-gate FAIL  checks=%d fail=%d'
              % (checks, len(failures)))
        return 1
    print('VERDICT: PASS')
    print('BATTERY-VERDICT lane-screen-gate PASS  checks=%d fail=0' % checks)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
