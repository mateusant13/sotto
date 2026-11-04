#!/usr/bin/env python
"""FECHA CADA SITIO DO CENSO DE CONSOLAS -- transformacao mecanica, por AST.

ORDEM DO DONO (2026-11-04): nenhum script deste repo pode abrir terminal na
cara dele. O censo (`_main/console-window-audit.py`) aponta os sitios; este
ficheiro aplica a cura em cada um, sem executar nada.

  Python   `subprocess.Popen([...])`            -> `..., creationflags=<NO_WINDOW>)`
           `subprocess.run(cmd, shell=True)`    -> acrescenta `creationflags=`
           `os.system(cmd)`                     -> `subprocess.run(cmd, shell=True,
                                                     creationflags=<NO_WINDOW>)`
           `os.popen(cmd)`                      -> `subprocess.Popen(cmd, shell=True,
                                                     stdout=subprocess.PIPE,
                                                     creationflags=<NO_WINDOW>)`
  JS       `exec(cmd)`                          -> `exec(cmd, { windowsHide: true })`
           `exec(cmd, {...})`                   -> acrescenta `windowsHide: true`
           `exec(cmd, opts)`                    -> `{ ...opts, windowsHide: true }`

<NO_WINDOW> e' o `NO_WINDOW` que o modulo JA' define, quando existe; senao
`subprocess.CREATE_NO_WINDOW`. Nada mais e' tocado: o comando, os argumentos e
a ordem dos mesmos ficam exactamente como estao.

As edicoes de um ficheiro aplicam-se de tras para a frente, sobre o texto
ORIGINAL, para que os offsets do `ast` continuem validos.
"""
from __future__ import annotations

import ast
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBPROC = {"Popen", "run", "call", "check_call", "check_output"}
OS_SYS = {"system", "popen"}
JS_CALLS = ("execSync", "execFileSync", "execFile", "spawnSync", "spawn", "exec")


def _offset(src, lineno, col):
    """Offset absoluto de (lineno, col) 1-based/0-based como o `ast` os da'."""
    lines = src.splitlines(keepends=True)
    return sum(len(x) for x in lines[:lineno - 1]) + col


def _no_window_expr(src):
    for name in ("NO_WINDOW_FLAGS", "NO_WINDOW", "CREATE_NO_WINDOW"):
        if re.search(r'^\s*%s\s*=' % name, src, re.M):
            return name
    return "subprocess.CREATE_NO_WINDOW"


def _has_guard(call, segment):
    for kw in call.keywords:
        if kw.arg in ("creationflags", "flags", "startupinfo"):
            return True
    return False


def _call_kind(node):
    fn = node.func
    if not isinstance(fn, ast.Attribute):
        return None
    base = fn.value
    if isinstance(base, ast.Name) and base.id == "subprocess" and fn.attr in SUBPROC:
        return "subprocess"
    if isinstance(base, ast.Name) and base.id == "os" and fn.attr in OS_SYS:
        return "os." + fn.attr
    return None


def transform_py(path):
    src = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [], "PARSE"
    nowin = _no_window_expr(src)
    edits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = _call_kind(node)
        if not kind:
            continue
        # TODA a chamada sem guarda leva a guarda. Julgar pelo NOME do programa
        # deixou 38 sitios de fora (os de programa dinamico, `STRING`, e os que
        # o censo nao classificou); um `CREATE_NO_WINDOW` num filho de consola
        # e' inofensivo e num filho GUI e' inerte, por isso a regra e' total.
        segment = ast.get_source_segment(src, node) or ""
        if _has_guard(node, segment):
            continue
        end = _offset(src, node.end_lineno, node.end_col_offset)
        if end - 1 >= len(src) or src[end - 1] != ")":
            return [], "END-NOT-PAREN@%d" % node.lineno
        if kind == "subprocess":
            body = src[_offset(src, node.lineno, node.col_offset):end - 1]
            inner = body[body.find("(") + 1:]
            sep = "" if inner.rstrip().endswith(",") or not inner.strip() else ", "
            edits.append((end - 1, end - 1,
                          "%screationflags=%s" % (sep, nowin)))
            continue
        # os.system / os.popen -> subprocess com shell e sem consola
        start = _offset(src, node.lineno, node.col_offset)
        inner = segment[segment.find("(") + 1:segment.rfind(")")]
        if kind == "os.system":
            new = ("subprocess.run(%s, shell=True, creationflags=%s)"
                   % (inner, nowin))
        else:
            new = ("subprocess.Popen(%s, shell=True, stdout=subprocess.PIPE, "
                   "creationflags=%s)" % (inner, nowin))
        edits.append((start, end, new))
    if not edits:
        return [], "OK"
    out = src
    for a, b, c in sorted(edits, key=lambda e: -e[0]):
        out = out[:a] + c + out[b:]
    # O `import subprocess` entra DEPOIS de as edicoes estarem aplicadas: fazer
    # a conta de deslocamento em paralelo com as edicoes ja' custou uma versao
    # deste ficheiro que corrompia offsets.
    if re.search(r'\bsubprocess\.', out) and not re.search(
            r'^\s*import\s+subprocess\b|^\s*from\s+subprocess\s+import', out, re.M):
        lines = out.splitlines(keepends=True)
        last = 0
        for i, line in enumerate(lines[:220]):
            if re.match(r'^(import |from )', line):
                last = i + 1
        lines.insert(last, "import subprocess\n")
        out = "".join(lines)
    if out == src:
        return [], "OK"
    io.open(path, "w", encoding="utf-8", newline="").write(out)
    return edits, "EDITED:%d" % len(edits)


def _scan_parens(src, start):
    """Index do ')' que fecha o '(' em `start`, saltando strings e comentarios."""
    depth = 0
    i = start
    n = len(src)
    quote = None
    while i < n:
        ch = src[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"`":
            quote = ch
            i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i)
            i = n if j < 0 else j + 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


JS_RX = re.compile(r'\b(?:child_process\.)?(execSync|execFileSync|execFile|'
                   r'spawnSync|spawn|exec)\s*\(')


def _js_child_process_names(src):
    """Os nomes que NESTE ficheiro vem de `child_process`.

    MEDIDO (2026-11-04): a primeira versao casava `exec(` em QUALQUER JS e
    reescreveu `SOTTO_VOICE_RE.exec(source)` para
    `SOTTO_VOICE_RE.exec(source, { windowsHide: true })` no `app/panel/panel.js`
    do produto -- `RegExp.exec` nao aceita opcoes e devolve `null`. Um `exec`
    so' e' do Node quando o ficheiro o importa de `child_process`.
    """
    fecho = r"""(['"])"""
    destr = re.compile(r"\b(?:const|let|var)\s*\{([^}]*)\}\s*=\s*require\(\s*['\"](?:node:)?child_process['\"]\s*\)")
    ns = re.compile(r"\b(?:const|let|var)\s*([A-Za-z_$][\w$]*)\s*=\s*require\(\s*['\"](?:node:)?child_process['\"]\s*\)")
    esm = re.compile(r"\bimport\s*\{([^}]*)\}\s*from\s*['\"](?:node:)?child_process['\"]")
    names, spaces = set(), set()
    for rx in (destr, esm):
        for m in rx.finditer(src):
            for part in m.group(1).split(','):
                part = part.strip()
                if not part:
                    continue
                name = part.split(' as ')[-1].split(':')[-1].strip()
                if name:
                    names.add(name)
    for m in ns.finditer(src):
        spaces.add(m.group(1))
    return names, spaces


def _split_args(inner):
    """Corta a lista de argumentos ao nivel do topo (strings e brackets contam)."""
    out, depth, quote, cur = [], 0, None, []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            cur.append(ch)
            if ch == '\\':
                if i + 1 < len(inner):
                    cur.append(inner[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"`":
            quote = ch
            cur.append(ch)
        elif ch in '([{':
            depth += 1
            cur.append(ch)
        elif ch in ')]}':
            depth -= 1
            cur.append(ch)
        elif ch == ',' and depth == 0:
            out.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    tail = ''.join(cur)
    if tail.strip() or out:
        out.append(tail)
    return out


def transform_js(path):
    src = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    if "child_process" not in src:
        return 0
    names, spaces = _js_child_process_names(src)
    if not names and not spaces:
        return 0
    alt = ''.join('|' + re.escape(x) for x in sorted(spaces))
    ns_rx = re.compile(r'(?:^|[^\w$.])(?:child_process%s)\\.$' % alt)
    edits = []
    for m in JS_RX.finditer(src):
        fn = m.group(1)
        head = src[max(0, m.start() - 60):m.start()]
        is_ns = bool(ns_rx.search(head))
        # `head` e o texto ANTES do nome da funcao, por isso comparar
        # `head.endswith(fn)` nunca podia dar True (bug da primeira versao).
        # O que interessa e' o caracter imediatamente antes do nome: um nome
        # solto (`exec(`) e' a funcao importada; `re.exec(` ja' tem um ponto e
        # cai fora.
        prev = src[m.start() - 1] if m.start() else ''
        is_bare = fn in names and not re.match(r'[\w$.]', prev)
        if not (is_ns or is_bare):
            continue
        open_idx = m.end() - 1
        close_idx = _scan_parens(src, open_idx)
        if close_idx < 0:
            continue
        inner = src[open_idx + 1:close_idx]
        if 'windowsHide' in inner:
            continue
        args = _split_args(inner)
        if len(args) == 1:
            edits.append((close_idx, close_idx, ", { windowsHide: true }"))
            continue
        opts = args[-1].strip()
        if opts.startswith('{') and opts.endswith('}'):
            at = open_idx + 1 + inner.rfind('{') + 1
            edits.append((at, at, " windowsHide: true,"))
        elif opts.startswith('['):
            edits.append((close_idx, close_idx, ", { windowsHide: true }"))
        elif re.fullmatch(r'[A-Za-z_$][\w$.]*', opts):
            at = open_idx + 1 + inner.rfind(opts)
            edits.append((at, at + len(opts), "{ ...%s, windowsHide: true }" % opts))
        # qualquer outra forma (chamada, template) fica para o censo apontar
    if not edits:
        return 0
    out = src
    for a, b, c in sorted(edits, key=lambda e: -e[0]):
        out = out[:a] + c + out[b:]
    io.open(path, "w", encoding="utf-8", newline="").write(out)
    return len(edits)


def main(argv):
    only = [a for a in argv if not a.startswith("-")]
    files = []
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "node_modules", "__pycache__", "_cache", "_libs",
                    "dist", "target", "models", "history", ".codeintel",
                    ".agent-work", ".pi", "docs")]
        for name in names:
            if name.endswith((".py", ".js", ".mjs", ".cjs")):
                files.append(os.path.join(base, name))
    if only:
        files = [f for f in files
                 if any(o.replace("\\", "/") in f.replace("\\", "/") for o in only)]
    total_py = total_js = 0
    for path in sorted(files):
        try:
            if path.endswith(".py"):
                edits, status = transform_py(path)
                if edits:
                    total_py += len(edits)
                    print("py %-62s %s" % (os.path.relpath(path, ROOT), status))
            elif path.endswith((".js", ".mjs", ".cjs")):
                n = transform_js(path)
                if n:
                    total_js += n
                    print("js %-62s EDITED:%d" % (os.path.relpath(path, ROOT), n))
        except Exception as exc:               # noqa: BLE001
            print("!! %-62s %r" % (os.path.relpath(path, ROOT), exc))
    print("TOTAL py_edits=%d js_edits=%d" % (total_py, total_js))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
