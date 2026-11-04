#!/usr/bin/env python
"""CENSO DE TUDO O QUE PODE ABRIR UMA CONSOLA NO ECRAN DO DONO.

ORDEM DELE, 2026-11-04, verbatim: *"tu vai fazer full audit de todos os
scripts existentes do sotto e todos tu vai parar de abrir terminal na minha
cara. agora."*

Este ficheiro NAO executa nada: le os scripts e diz, com ficheiro e linha, onde
cada um pode criar uma JANELA. A regra que ele aplica:

  Um processo filho abre uma janela nova em EXACTAMENTE tres casos:
    1. `shell=True` -- o Python larga um `cmd.exe`, que tem janela;
    2. `os.system` / `os.popen` -- idem, por baixo;
    3. o programa largado e' de subsistema CONSOLE (cmd, powershell, python,
       node, cscript, .cmd, .bat, .ps1) E o pai NAO tem consola -- caso tipico
       de um `pythonw.exe` (a app) ou de um processo com `DETACHED_PROCESS`.
  Um `subprocess` comum, lancado de um processo que JA' tem consola, herda-a e
  nao cria janela nenhuma: por isso o veredicto e' `inherits`, nao `window`.

O que fecha o caso 3 e' uma destas, na MESMA chamada:
    creationflags=CREATE_NO_WINDOW (0x08000000) | DETACHED_PROCESS (0x8) |
    STARTF_USESHOWWINDOW+wShowWindow=0 (startupinfo) | windowsHide: true (JS)
ou o programa ser de subsistema GUI (pythonw.exe, wscript.exe, electron.exe).

CLASSES
    WINDOW     abre janela por desenho (shell=True, os.system, `start`,
               explorer, mshta, um URL)                      -> FAIL, corrigir
    NO-FLAG    larga um programa de consola sem nenhuma guarda -> FAIL
    INHERITS   herda a consola do pai (guarda nao necessaria, mas aceita)
    GUARDED    tem CREATE_NO_WINDOW / DETACHED / STARTF / windowsHide
    GUI        o programa nao tem consola na consola (pythonw, wscript)
    STRING     o nome do programa e' dinamico -- nao se julga, reporta-se

Portao: `python _main/console-window-audit.py` -> rc=0 so' com WINDOW=0 e
NO-FLAG=0. `--neg-arm` escreve um ficheiro com um `os.system` e exige o FAIL.
"""
# BLOCKS: BUG-20261104-01 -- a janela de consola que o Windows aloca ao
# filho de um pai sem consola (`INC-20261104-01-console-window.md`).

from __future__ import annotations

import ast
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {
    '.git', 'node_modules', '__pycache__', '_cache', '.codeintel', '.agent-work',
    '.pi', '.venv', 'venv', 'dist', 'build', 'target', 'models', 'history',
    '_libs', 'docs', 'fixtures', '_audit-verify', 'runs', '_tmp', '.mypy_cache',
    '.pytest_cache', 'app-assets', 'themes', 'shots', 'rendered', 'demos',
}
#: Copias MORTAS: `app/_legacy-electron` esta' declarado morto no AGENTS.md
#: (o Electron nao corre nesta maquina) e os `_render-1710/{before,after}` e
#: `_tmp-panel-noreveal` sao SNAPSHOTS byte-exatos usados como fixture por
#: oraculos de comparacao -- edita-los seria quebrar o instrumento que os le',
#: e nenhum deles e' executado.
#: Copias CONGELADAS do worker e mutantes de oraculos (`_recovered/`,
#: `_main/denoise-frozen/`, `_main/thresh/`, `_main/_redux-gate-mutants/`,
#: `_main/_falsify/`) e `worker/_prefix_audioflag.py`: sao fotos de um ficheiro
#: com uma mutacao, nunca o ficheiro executado. Se um dia voltarem a ser
#: executaveis, o portao tem de os ver -- por isso a lista e' de PREFIXOS
#: exactos e nao um `*.py` solto.
SKIP_PREFIX = ('_gaps-', 'sotto-wt', 'install', '_render-1710',
               '_tmp-panel-noreveal', '_recovered', '_redux-gate-mutants',
               '_denoise-frozen', '_falsify', '_thresh')
SKIP_FILES = ('worker/_prefix_audioflag.py',)
SKIP_PATHS = ('app/_legacy-electron/',)

PY_EXT = ('.py',)
JS_EXT = ('.js', '.mjs', '.cjs', '.ts')
SH_EXT = ('.cmd', '.bat', '.ps1', '.vbs')

# programas que NAO tem consola (largar deles nunca abre janela)
GUI_EXES = {
    'pythonw', 'pythonw.exe', 'wscript', 'wscript.exe', 'electron',
    'electron.exe', 'msedgewebview2.exe', 'rundll32', 'rundll32.exe',
    'notepad', 'notepad.exe', 'explorer', 'explorer.exe',
}
# programas de consola: largar deles de um pai sem consola ABRE janela
CONSOLE_EXES = {
    'python', 'python.exe', 'py', 'py.exe', 'cmd', 'cmd.exe', 'powershell',
    'powershell.exe', 'pwsh', 'pwsh.exe', 'node', 'node.exe', 'npm', 'npm.cmd',
    'git', 'git.exe', 'cscript', 'cscript.exe', 'taskkill', 'taskkill.exe',
    'ffmpeg', 'ffmpeg.exe', 'ffprobe', 'ffprobe.exe', 'wsl', 'wsl.exe',
    'bash', 'bash.exe', 'conhost.exe', 'curl', 'curl.exe', 'yt-dlp',
    'yt-dlp.exe', 'mshta', 'mshta.exe', 'timeout', 'ping',
}
CONSOLE_SCRIPT_EXT = ('.cmd', '.bat', '.ps1', '.vbs')
NO_WINDOW_TOKENS = ('CREATE_NO_WINDOW', 'CREATE_NEW_CONSOLE_DISABLED',
                    'DETACHED_PROCESS', 'NO_WINDOW', 'NO_WINDOW_FLAGS',
                    'SW_HIDE', 'windowsHide', '0x08000000', '0x00000008')
#: mapa id(call) -> funcao, preenchido por ficheiro em `audit_python`
SCOPE = [{}]

SUBPROC_FUNCS = {'Popen', 'run', 'call', 'check_call', 'check_output',
                 'getoutput', 'getstatusoutput'}
OS_FUNCS = {'system', 'popen', 'spawnv', 'spawnve', 'spawnl', 'spawnle',
            'startfile', 'execv', 'execve'}


def _walk():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.startswith(SKIP_PREFIX)
                   and not d.startswith('_mutant') and not d.startswith('.')]
        for name in files:
            low = name.lower()
            full = os.path.join(base, name)
            if low.endswith(PY_EXT + JS_EXT + SH_EXT) and not _skip(full):
                yield full


def _skip(path):
    rel = os.path.relpath(path, ROOT).replace('\\', '/')
    if rel in SKIP_FILES:
        return True
    return any(rel.startswith(p) for p in SKIP_PATHS)


def _rel(path):
    return os.path.relpath(path, ROOT).replace('\\', '/')


def _literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return ''.join(v.value for v in node.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


def _argv_shape(call):
    """(programa, alvos) -- `alvos` sao os literais que parecem ficheiros."""
    prog, targets = None, []
    args = list(call.args)
    if args:
        first = args[0]
        if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
            prog = _literal(first.elts[0])
            for e in first.elts:
                lit = _literal(e)
                if lit:
                    targets.append(lit)
        else:
            prog = _literal(first)
            for e in args[1:]:
                lit = _literal(e)
                if lit:
                    targets.append(lit)
    for kw in call.keywords:
        if kw.arg in ('args', 'cmd', 'command', 'argv') and isinstance(
                kw.value, (ast.List, ast.Tuple)) and kw.value.elts:
            lit = _literal(kw.value.elts[0])
            if lit:
                prog = lit
            for e in kw.value.elts:
                t = _literal(e)
                if t:
                    targets.append(t)
        lit = _literal(kw.value)
        if kw.arg in ('args', 'cmd', 'command', 'argv') and lit:
            prog = prog or lit
            targets.append(lit)
    return prog, targets


def _module_flags(tree):
    """`NOME = ...` do topo do modulo, para resolver `creationflags=FLAGS`.

    MEDIDO: a primeira versao so' aceitava a guarda cujo VALOR e' literal, e
    deu 38 falsos positivos (`creationflags=FLAGS`, `creationflags=NO_WINDOW`)
    em ficheiros que ja' estavam certos -- um portao que acusa quem esta' certo
    perde a autoridade no dia seguinte.
    """
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    out[tgt.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = node.value
    return out


def _resolves_hidden(node, flags, depth=0):
    """O valor desta expressao contem uma flag que esconde a janela?"""
    if node is None or depth > 4:
        return False
    dump = ast.dump(node)
    for tok in ('CREATE_NO_WINDOW', 'DETACHED_PROCESS', 'CREATE_NEW_PROCESS_GROUP'):
        if tok in dump:
            return True
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return bool(node.value & (0x08000000 | 0x00000008))
    if isinstance(node, ast.IfExp):
        return (_resolves_hidden(node.body, flags, depth + 1)
                or _resolves_hidden(node.orelse, flags, depth + 1))
    if isinstance(node, ast.BoolOp):
        return any(_resolves_hidden(v, flags, depth + 1) for v in node.values)
    if isinstance(node, ast.BinOp):
        return (_resolves_hidden(node.left, flags, depth + 1)
                or _resolves_hidden(node.right, flags, depth + 1))
    if isinstance(node, ast.Name) and node.id in flags:
        return _resolves_hidden(flags[node.id], flags, depth + 1)
    return False


def _scope_map(tree):
    """(id(call) -> funcao que o contem) para resolver nomes locais."""
    owner = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(fn):
                owner[id(node)] = fn
    return owner


def _resolve_name(name, call, owner, module_flags, depth=0):
    """O valor de `name` no escopo visivel do call, ou None.

    MEDIDO 2026-11-04: 44 chamadas passam `creationflags=flags` / `=creationflags`
    de um PARAMETRO (`def _spawn(cmd, flags=NO_WINDOW)`). O censo dizia `STRING`
    e nao conseguia provar nada. Resolver o parametro/atribuicao do escopo
    imediato fecha a maioria sem analise entre funcoes.
    """
    if depth > 4:
        return None
    if name in module_flags:
        return module_flags[name]
    fn = owner.get(id(call))
    if fn is None:
        return None
    args = fn.args
    for n, default in zip(args.args[len(args.args) - len(args.defaults):],
                          args.defaults):
        if n.arg == name:
            return default
    for n, default in zip(args.kwonlyargs, args.kw_defaults):
        if n.arg == name and default is not None:
            return default
    found = None
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            found = node.value
        elif (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
              and node.target.id == name and node.value is not None):
            found = node.value
    return found


def _guards(call, src_segment, flags=None):
    """A guarda esta' nesta chamada? Devolve o nome da guarda ou None."""
    for kw in call.keywords:
        if kw.arg in ('creationflags', 'flags'):
            if _resolves_hidden(kw.value, flags or {}):
                return 'creationflags'
            if isinstance(kw.value, ast.Name):
                local = _resolve_name(kw.value.id, call, SCOPE[0], flags or {})
                if local is not None and ast.dump(local) != ast.dump(kw.value):
                    if _resolves_hidden(local, flags or {}):
                        return 'creationflags(%s)' % kw.value.id
                return 'GUARD-EXTERNAL' if local is None else None
            return None
            seg = ast.dump(kw.value)
            for tok in NO_WINDOW_TOKENS:
                if tok.lower() in seg.lower():
                    return 'creationflags'
            return None
        if kw.arg == 'startupinfo':
            return 'startupinfo'
    for tok in NO_WINDOW_TOKENS:
        if tok.lower() in (src_segment or '').lower():
            return tok
    return None


def _classify(prog, targets, guard, shell_true, os_func):
    if os_func in ('system', 'popen', 'getoutput', 'getstatusoutput'):
        return 'WINDOW', 'os.%s abre um cmd.exe' % os_func
    if os_func == 'startfile':
        return 'WINDOW', 'os.startfile abre o programa no ecran'
    # A GUARDA VEM PRIMEIRO (corrigido 2026-11-04): `shell=True` com
    # `creationflags=CREATE_NO_WINDOW` NAO abre janela nenhuma -- o cmd.exe
    # nasce sem consola. A ordem anterior acusava tres ficheiros que ja'
    # estavam certos, e um portao que acusa quem esta' certo perde a autoridade.
    if guard:
        return 'GUARDED', 'guarda %s' % guard
    if shell_true:
        return 'WINDOW', 'shell=True larga um cmd.exe'
    if prog is None:
        return 'STRING', 'programa dinamico (nao se julga pela string)'
    low = prog.lower().replace('\\', '/').rsplit('/', 1)[-1]
    if low in GUI_EXES:
        return 'GUI', 'programa sem consola (%s)' % low
    if low in ('start', 'explorer', 'mshta', 'control'):
        return 'WINDOW', '`%s` e um lancador de janela' % low
    if low.startswith(('http://', 'https://')):
        return 'WINDOW', 'abre um URL no browser'
    if low.endswith(CONSOLE_SCRIPT_EXT):
        return 'NO-FLAG', 'larga %s (consola) sem guarda' % low
    if low in CONSOLE_EXES:
        tgt = ' '.join(t for t in targets if t.lower().endswith(CONSOLE_SCRIPT_EXT))
        return 'NO-FLAG', 'larga %s sem guarda%s' % (low, (' -> ' + tgt) if tgt else '')
    return 'INHERITS', 'programa %s (herda a consola do pai)' % low


def audit_python(path):
    src = io.open(path, encoding='utf-8', errors='replace').read()
    segment = src.splitlines()
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [(_rel(path), exc.lineno or 0, 'PARSE', str(exc)[:60])]
    rows = []
    flags = _module_flags(tree)
    SCOPE[0] = _scope_map(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = None
        if isinstance(fn, ast.Attribute):
            name = fn.attr
            # `ast.dump(Name(id='os'))` termina em `ctx=Load())`, NAO em
            # `id='os')`: a comparacao anterior nunca casava e o censo ficou
            # CEGO a `os.system`/`os.popen` -- a classe mais directa de janela.
            # Medido 2026-11-04 com um ficheiro de um so' `os.system`: o censo
            # devolvia 0 achados.
            base_ok = isinstance(fn.value, ast.Name)
            base_id = fn.value.id if base_ok else None
            is_sub = base_id == 'subprocess'
            is_os = base_id == 'os'
        else:
            name = getattr(fn, 'id', None)
            is_sub = is_os = False
        if not ((is_sub and name in SUBPROC_FUNCS)
                or (is_os and name in OS_FUNCS)):
            continue
        line = node.lineno
        seg = '\n'.join(segment[max(0, line - 3):line + 12])
        shell_true = False
        for kw in node.keywords:
            if kw.arg == 'shell' and not (isinstance(kw.value, ast.Constant)
                                          and kw.value.value is False):
                shell_true = True
        prog, targets = _argv_shape(node)
        guard = _guards(node, seg, flags)
        if guard == 'GUARD-EXTERNAL':
            rows.append((_rel(path), line, 'GUARD-EXTERNAL',
                         'creationflags vem de um parametro/externo: %s'
                         % (_literal(node.keywords[0].value) if False else
                            (node.keywords[0].value.id
                             if isinstance(node.keywords[0].value, ast.Name) else '?'))))
            continue
        cls, why = _classify(prog, targets, guard, shell_true,
                             name if is_os else None)
        if cls in ('WINDOW', 'NO-FLAG', 'STRING', 'GUARD-EXTERNAL'):
            rows.append((_rel(path), line, cls, why))
    return rows


JS_RX = re.compile(r'(child_process\.)?(spawn|spawnSync|exec|execSync|execFile|execFileSync)\s*\(')
JS_PROG = re.compile(r"""['"]([^'"\n]{1,80})['"]""")


def _js_cp_names(src):
    """Nomes ligados a `child_process` neste ficheiro (namespace e destructuring).

    Sem isto o censo conta `SOTTO_VOICE_RE.exec(source)` como uma consola: um
    `RegExp.exec` nao larga processo nenhum. Medido 2026-11-04 no
    `app/panel/panel.js` do produto -- 8 falsos positivos num ficheiro que nem
    importa o `child_process`.
    """
    names, spaces = set(), set()
    for m in re.finditer(r"\b(?:const|let|var)\s*\{([^}]*)\}\s*=\s*"
                         r"require\(\s*['\"](?:node:)?child_process['\"]\s*\)", src):
        for part in m.group(1).split(','):
            part = part.strip()
            if part:
                names.add(part.split(' as ')[-1].split(':')[-1].strip())
    for m in re.finditer(r"\bimport\s*\{([^}]*)\}\s*from\s*"
                         r"['\"](?:node:)?child_process['\"]", src):
        for part in m.group(1).split(','):
            part = part.strip()
            if part:
                names.add(part.split(' as ')[-1].split(':')[-1].strip())
    for m in re.finditer(r"\b(?:const|let|var)\s*([A-Za-z_$][\w$]*)\s*=\s*"
                         r"require\(\s*['\"](?:node:)?child_process['\"]\s*\)", src):
        spaces.add(m.group(1))
    return names, spaces


def audit_js(path):
    src = io.open(path, encoding='utf-8', errors='replace').read()
    if 'child_process' not in src:
        return []
    names, spaces = _js_cp_names(src)
    if not names and not spaces:
        return []
    alt = ''.join('|' + re.escape(x) for x in sorted(spaces))
    ns_rx = re.compile(r'(?:^|[^\w$.])(?:child_process%s)\.$' % alt)
    rows = []
    for m in JS_RX.finditer(src):
        # `JS_RX` tem DOIS grupos: (1) o prefixo opcional `child_process.`,
        # (2) o nome da funcao. Ler o (1) dava `None` em todos os ficheiros que
        # chamam a funcao importada -- e o censo publicava `PARSE` para eles.
        fn = m.group(2)
        head = src[max(0, m.start() - 60):m.start()]
        prev = src[m.start() - 1] if m.start() else ''
        if not (ns_rx.search(head) or (fn in names and not re.match(r'[\w$.]', prev))):
            continue
        line = src.count('\n', 0, m.start()) + 1
        window = src[m.start():m.start() + 700]
        prog = None
        pm = JS_PROG.search(window[m.end() - m.start():])
        if pm:
            prog = pm.group(1)
        guarded = ('windowsHide' in window) or ('detached: true' in window)
        if fn.startswith('exec') and 'execFile' not in fn:
            if not guarded:
                rows.append((_rel(path), line, 'WINDOW',
                             'exec* passa pelo shell (cmd.exe) sem windowsHide'))
            continue
        low = (prog or '').lower().replace('\\', '/').rsplit('/', 1)[-1]
        # O "REVELAR NA PASTA" E' UM GESTO DO DONO (2026-11-04): o
        # `history-store.js` larga `explorer /select,<ficheiro>` com
        # `detached: true` e `stdio: 'ignore'` -- e' a acao de um CLIQUE dele no
        # painel, e abrir a janela E' o resultado pedido. O censo marca-a
        # `USER-GESTURE` (informacao) e nao a conta como janela de script.
        # `start`/`mshta` continuam WINDOW: nenhum deles e' uma acao do dono.
        gesture = (low == 'explorer' and 'detached: true' in window
                   and "stdio: 'ignore'" in window)
        if gesture:
            rows.append((_rel(path), line, 'USER-GESTURE',
                         'revelar na pasta, largado por um clique do dono'))
            continue
        if low in ('start', 'explorer', 'mshta') or low.startswith(('http://', 'https://')):
            rows.append((_rel(path), line, 'WINDOW', 'larga %s' % low))
        elif low in CONSOLE_EXES or low.endswith(CONSOLE_SCRIPT_EXT):
            if not guarded:
                rows.append((_rel(path), line, 'NO-FLAG',
                             'larga %s sem windowsHide' % low))
    return rows


SH_RX = re.compile(r'(^|[\s&|(])(start\s+\S|powershell|cmd\s+/c|cscript|'
                   r'python(\.exe)?\s|node\s)', re.I)


def audit_shell_script(path):
    """Um .cmd/.bat/.ps1/.vbs NAO se pode esconder a si mesmo.

    Estes ficheiros, quando largados por um pai SEM consola (a app, um
    `pythonw`), abrem uma janela. Nao ha' guarda possivel DENTRO do ficheiro:
    a unica cura e' quem o larga passar `CREATE_NO_WINDOW`. O censo lista-os
    como `SCRIPT` para que todo largador deles seja auditado do outro lado.
    """
    rows = []
    src = io.open(path, encoding='utf-8', errors='replace').read()
    for m in SH_RX.finditer(src):
        line = src.count('\n', 0, m.start()) + 1
        rows.append((_rel(path), line, 'SCRIPT',
                     'larga `%s` -- quem chamar este ficheiro tem de o fazer com CREATE_NO_WINDOW'
                     % m.group(2).strip()[:24]))
    return rows


def judge(rows):
    """O veredicto e' uma funcao pura das linhas, para o `--neg-arm` a mutar."""
    bad = [r for r in rows if r[2] in ('WINDOW', 'NO-FLAG')]
    return bad


def main(argv):
    neg = '--neg-arm' in argv
    if neg:
        # o mutante: um ficheiro NOVO com `os.system`, escrito ao lado e apagado.
        mutant = os.path.join(ROOT, '_main', '_zz_negarm_console.py')
        io.open(mutant, 'w', encoding='utf-8').write(
            'import os\nos.system("echo ola")\n')
        try:
            rows = audit_python(mutant)
        finally:
            os.remove(mutant)
        bad = judge(rows)
        ok = bool(bad) and bad[0][2] == 'WINDOW'
        print('NEG-ARM %s -- %d achado(s): %s'
              % ('PASS (o os.system foi apanhado)' if ok else 'FAIL',
                 len(bad), bad[:1]))
        return 1 if ok else 0

    rows = []
    files = 0
    for path in _walk():
        files += 1
        low = path.lower()
        try:
            if low.endswith(PY_EXT):
                rows.extend(audit_python(path))
            elif low.endswith(JS_EXT):
                rows.extend(audit_js(path))
            else:
                rows.extend(audit_shell_script(path))
        except Exception as exc:               # noqa: BLE001
            rows.append((_rel(path), 0, 'PARSE', repr(exc)[:70]))

    by = {}
    for r in rows:
        by[r[2]] = by.get(r[2], 0) + 1
    # o relatorio leva tudo o que precisa de olhos (WINDOW/NO-FLAG falham;
    # STRING e GUARD-EXTERNAL sao lista de trabalho, nao veredicto)
    targets = [r for r in rows if r[2] in ('WINDOW', 'NO-FLAG', 'STRING',
                                           'GUARD-EXTERNAL')]
    print('populacao: %d ficheiro(s) lidos' % files)
    for k in ('WINDOW', 'NO-FLAG', 'STRING', 'GUARD-EXTERNAL', 'SCRIPT',
              'USER-GESTURE', 'PARSE'):
        print('  %-8s %d' % (k, by.get(k, 0)))
    per_file = {}
    for f, line, cls, why in targets:
        per_file.setdefault(f, []).append((line, cls, why))
    print('\nficheiros a corrigir: %d' % len(per_file))
    for f in sorted(per_file, key=lambda k: -len(per_file[k]))[:25]:
        print('  %-58s %d sitio(s)' % (f, len(per_file[f])))
        for line, cls, why in per_file[f][:3]:
            print('       :%-5d %-8s %s' % (line, cls, why[:70]))
    out = os.path.join(ROOT, '_main', '_cache', 'console-window-audit.json')
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        io.open(out, 'w', encoding='utf-8').write(json.dumps(
            {'files': files, 'counts': by,
             'sites': [dict(file=f, line=l, cls=c, why=w) for f, l, c, w in targets],
             'unparsed': [dict(file=f, why=w) for f, _l, c, w in rows
                          if c == 'PARSE']},
            indent=1, ensure_ascii=False))
        print('\nrelatorio: %s' % _rel(out))
    except OSError:
        pass
    bad = judge(rows)
    print('CONSOLE-AUDIT VERDICT %s -- %d sitio(s) que abrem janela'
          % ('FAIL' if bad else 'PASS', len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
