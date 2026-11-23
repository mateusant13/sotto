# NO-BUG: o arranque de 2026-11-16 que morria em `AttributeError: 'GamingWatcher' object has no attribute 'owns_space_now'` sem deixar recibo -- trabalho de CAPACIDADE/observabilidade; o ledger nao lhe da' id
"""O OBJETO QUE A SHELL GUARDA TEM DE SABER RESPONDER -- e uma morte sem stderr tem recibo.

Nascido de um defeito MEDIDO a 2026-11-16, reportado pelo dono como "tentei abrir o
sotto e nao abriu": o arranque morria em

    AttributeError: 'GamingWatcher' object has no attribute 'owns_space_now'
      sotto_webview.py:10805 em arm_hotkey_role  <- main():27210

O metodo existia so' no `GamingDetector`; a shell guarda o WATCHER em `shell.gaming` e
pergunta-lhe `owns_space_now()`. E como a largada e' `pythonw.exe` (sem stderr), o log
terminava em `HOTKEY_REGISTERED`, o processo sumia com rc=1 e na tela do dono nao havia
app nem motivo: o unico sinal era "nao abriu".

Duas metades, cada uma com a SUA arm:

  * a SUPERFICIE -- toda pergunta que a shell faz ao objeto de gaming tem de existir na
    classe que a shell realmente guarda (e a delegacao tem de ATRAVESSAR ate' ao
    detector, senao um stub que devolve `None` passaria);
  * o RECIBO -- uma excecao que sobe do `main()` escreve `SHELL_CRASH` no `--log` da
    largada, porque `pythonw` nao tem stderr para onde sangrar.

Nao importa a shell: 27 mil linhas, pywebview e WebView2. Le' o AST, executa a funcao
REAL extraida por `ast` e o objeto REAL de `gaming_mode` (que e' leve).

  python _main/gaming-watcher-surface-oracle.py            -> VERDICT: PASS (n/n) rc=0
  python _main/gaming-watcher-surface-oracle.py --neg-arm   -> NEG-ARM: PASS rc=1
"""
import ast
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
GAMING = os.path.join(ROOT, 'app', 'webview', 'gaming_mode.py')

#: Os nomes por onde a shell alcanca o objeto de gaming. Uma pergunta feita por
#: qualquer OUTRO caminho nao e' deste portao -- e e' de proposito: um portao que
#: tenta adivinhar todo alias acusa quem esta' certo (a licao do censo de consolas).
GAMING_ALIASES = ('_gaming', 'gaming')


def _tree(path):
    with open(path, 'rb') as fh:
        return ast.parse(fh.read(), filename=path)


def _method_names(tree, class_name):
    """Os metodos definidos NA classe, sem herdar nada de `Thread`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
    return set()


def _shell_questions(tree):
    """`_gaming.metodo(...)` e `shell.gaming.metodo(...)` -- os dois caminhos da shell."""
    asked = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        name = getattr(owner, 'id', None)
        if name in GAMING_ALIASES:
            asked.add(node.func.attr)
        elif (isinstance(owner, ast.Attribute) and owner.attr == 'gaming'):
            asked.add(node.func.attr)
    return asked


def _remove_watcher_method(src, method):
    """Arranca `method` da classe GamingWatcher pelo intervalo de LINHAS do AST.

    Uma ancora de texto morre em duas frentes que ja custaram uma rodada: o
    checkout e' CRLF (uma ancora `"\\n"` nao casa) e o corpo tem docstring (uma
    regex de indentacao corta a meio). O AST sabe onde o metodo comeca e acaba;
    o que sobra e' o ficheiro com o metodo a menos e o MESMO EOL.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'GamingWatcher':
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == method:
                    lines = src.splitlines(keepends=True)
                    start = child.lineno - 1
                    end = child.end_lineno
                    if start > 0 and not lines[start - 1].strip():
                        start -= 1
                    return ''.join(lines[:start] + lines[end:])
    return None


def _crash_arm(shell_path):
    """Executa a `_crash_receipt` REAL e exige o recibo no `--log` da largada."""
    src = open(shell_path, 'r', encoding='utf-8').read()
    tree = ast.parse(src, filename=shell_path)
    body = None
    wraps = False
    for node in tree.body:
        if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'":
            segment = ast.get_source_segment(src, node)
            wraps = '_crash_receipt' in (segment or '')
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == '_crash_receipt':
            body = ast.get_source_segment(src, node)
    if not body:
        return False, 'sem _crash_receipt'
    if not wraps:
        return False, 'o bloco __main__ nao chama _crash_receipt'
    import os as _os
    import sys as _sys
    import time as _time
    namespace = {'os': _os, 'sys': _sys, 'time': _time, '__file__': shell_path}
    exec(compile(body, shell_path, 'exec'), namespace)  # noqa: S102 -- a funcao que embarca
    tmpdir = tempfile.mkdtemp(prefix='crasharm-')
    logpath = _os.path.join(tmpdir, 'launch.log')
    saved = _sys.argv
    try:
        _sys.argv = ['sotto_webview.py', '--log', logpath]
        namespace['_crash_receipt']('Traceback (most recent call last):\n'
                                    'AttributeError: exemplo de morte\n')
    finally:
        _sys.argv = saved
    if not _os.path.exists(logpath):
        return False, 'nada escrito no --log'
    text = open(logpath, 'r', encoding='utf-8').read()
    ok = 'SHELL_CRASH' in text and 'AttributeError: exemplo de morte' in text
    return ok, ('SHELL_CRASH no --log' if ok else 'o --log nao recebeu SHELL_CRASH')


def judge(gaming_path, shell_path):
    """O juiz inteiro numa funcao, para a arm negativa exercitar os MESMOS bracos."""
    arms = []
    gm_src = open(gaming_path, 'r', encoding='utf-8').read()
    gm = ast.parse(gm_src, filename=gaming_path)
    sh = _tree(shell_path)

    watcher = _method_names(gm, 'GamingWatcher')
    detector = _method_names(gm, 'GamingDetector')
    asked = _shell_questions(sh)

    arms.append(('perguntas-encontradas', bool(asked), 'a shell nao faz pergunta nenhuma ao objeto de gaming'))
    missing_w = sorted(asked - watcher)
    missing_d = sorted(asked - detector)
    arms.append(('surface-no-watcher', not missing_w, 'GamingWatcher nao responde %r' % (missing_w,)))
    arms.append(('surface-no-detector', not missing_d, 'GamingDetector nao responde %r' % (missing_d,)))

    # O objeto REAL: a delegacao tem de ATRAVESSAR ate' ao detector.
    sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
    import gaming_mode  # noqa: PLC0415 -- o modulo que embarca, importado de proposito
    seen = []

    class FakeDetector(object):
        def owns_space_now(self):
            seen.append('owns_space_now')
            return True

        def is_gaming(self):
            seen.append('is_gaming')
            return False

    watcher_obj = gaming_mode.GamingWatcher(log=lambda *a, **k: None, detector=FakeDetector())
    reached = []
    try:
        for name in sorted(asked):
            if name == 'owns_space_now':
                got = watcher_obj.owns_space_now()
                reached.append((name, got is True))
            elif name == 'is_gaming':
                got = watcher_obj.is_gaming()
                reached.append((name, got is False))
            else:
                reached.append((name, hasattr(watcher_obj, name)))
    except AttributeError as exc:
        reached.append(('attribute', False, repr(exc)))
    arms.append(('delegacao-atravesa', bool(reached) and all(r[1] for r in reached),
                 'a delegacao nao chegou ao detector: %r' % (reached,)))

    crash_ok, crash_why = _crash_arm(shell_path)
    arms.append(('recibo-de-morte', crash_ok, crash_why))

    return arms


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    arms = judge(GAMING, SHELL)
    bad = [a for a in arms if not a[1]]
    for name, ok, why in arms:
        print('%s %s%s' % ('arm' if ok else 'ARM', name, ('' if ok else ' -- ' + why)))
    if bad:
        print('VERDICT: FAIL (%d/%d)' % (len(arms) - len(bad), len(arms)))
        return 1
    print('VERDICT: PASS (%d/%d)' % (len(arms), len(arms)))
    return 0


def neg_arm():
    """Planta os DOIS defeitos numa copia e exige os dois vermelhos."""
    import shutil
    caught = 0
    total = 0
    tmp = tempfile.mkdtemp(prefix='gaming-neg-')
    try:
        # M1: o metodo arrancado do WATCHER (o defeito de 2026-11-16).
        g1 = os.path.join(tmp, 'gaming_mode.py')
        src = _read_source(GAMING)
        broken = _remove_watcher_method(src, 'owns_space_now')
        if broken is None or broken == src:
            print('NEG-ARM: IMPOSSIVEL (a ancora do M1 nao existe)')
            return 2
        with open(g1, 'w', encoding='utf-8', newline='') as fh:
            fh.write(broken)
        total += 1
        arms = judge(g1, SHELL)
        hit = [a for a in arms if not a[1]]
        if hit:
            caught += 1
            print('M1 caught: %s' % ', '.join(a[0] for a in hit))
        else:
            print('M1 NOT-CAUGHT')
        # M2: o bloco __main__ deixa de pedir o recibo.
        s1 = os.path.join(tmp, 'sotto_webview.py')
        shell_src = _read_source(SHELL)
        mutated = shell_src.replace("        _crash_receipt(traceback.format_exc())", "        pass")
        if mutated == shell_src:
            print('NEG-ARM: IMPOSSIVEL (a ancora do M2 nao existe)')
            return 2
        with open(s1, 'w', encoding='utf-8', newline='') as fh:
            fh.write(mutated)
        total += 1
        arms = judge(GAMING, s1)
        hit = [a for a in arms if not a[1]]
        if hit:
            caught += 1
            print('M2 caught: %s' % ', '.join(a[0] for a in hit))
        else:
            print('M2 NOT-CAUGHT')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if caught == total:
        print('NEG-ARM: PASS -- %d/%d mutante(s) apanhado(s)' % (caught, total))
        return 1
    print('NEG-ARM: FAIL -- %d/%d' % (caught, total))
    return 0


def _read_source(path):
    """Le o fonte preservando CRLF: a mutacao de uma linha so' nao pode reescrever EOL."""
    with open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
