# NO-BUG: mede o que o LOADER resolve e recusa um pin no codigo; nao move nenhum processo vivo para a versao nova -- um host que arrancou antes da actualizacao so troca de binario ao reiniciar, e isso e do dono.
"""O RUNTIME DE WEBVIEW2 QUE A APP CARREGA -- e a PROIBICAO de o fixar.

Ordem do dono, 2026-11-11, verbatim: *"WEBVIEW2 RUNTIME ORDER FROM THE OWNER (2026-11-11): use the
GREATER version. This is a measured inventory, not a preference - act on it in your tree."* As duas
regras que saem dela, e as duas sao o que este oraculo julga:

1. **NUNCA fixar** uma versao nem um caminho (`...\\Application\\157.0.4341.42\\msedgewebview2.exe`)
   em codigo, config, docs ou fixture. Um `BrowserExecutableFolder` apontado para uma pasta antiga e'
   a unica forma de a app acabar na .42.
2. **Quem responde "que versao estou eu a correr" e' o PROCESSO, nao o registo** -- um host que
   arrancou antes da atualizacao mantem o binario antigo mapeado ate' reiniciar. Este instrumento nao
   adivinha isso: ele mede o que o LOADER resolve agora, e diz que o processo vivo e' outra pergunta.

PORQUE ELE EXISTE, e nao um paragrafo: a regra 1 e' um invariante que ninguem ve' violar. Basta uma
lane escrever `BrowserExecutableFolder` com um caminho para "resolver" um problema de flash e a app
fica silenciosamente numa versao antiga, sem um unico sintoma -- a classe do pin que apodrece.

A MEDICAO E' A FUNCAO DO PROPRIO LOADER, sem janela e sem host: `GetAvailableCoreWebView2BrowserVersionString`
de `WebView2Loader.dll`, que e' o que o `pywebview` chama quando cria o ambiente. Medido nesta maquina
2026-11-11:

    com pasta NENHUMA (o default que a shell usa)  -> 157.0.4341.46
    com pasta fixada em ...\\157.0.4341.42        -> 157.0.4341.42
    com pasta fixada em ...\\157.0.4341.46        -> 157.0.4341.46

Isto prova as duas metades ao mesmo tempo: a resolucao por omissao JA' da' a maior, e uma pasta fixada
manda. Nenhum processo e' largado, nenhuma janela aparece, nenhum dispositivo de audio e' aberto.

O NUMERO NAO E' PORTADO. O oraculo NAO compara a versao resolvida com um literal -- isso seria ele
proprio o pin que ele proibe. Ele compara com a MAIOR das pastas instaladas, lida do disco na hora.

USO
  python _main/webview2-runtime-oracle.py            # positivo: 5 arms, rc=0 quando tudo se verifica
  python _main/webview2-runtime-oracle.py --neg-arm  # negativo: rc=1 QUANDO APANHA (convencao da casa)
"""
import ast
import ctypes
import ctypes.wintypes as wintypes
import glob
import io
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'app')

# A POPULACAO E' O QUE EMBARCA. `_main/_cache/` e `_main/_redux-gate-mutants/` guardam COPIA da shell
# (e logs com cmdlines, que sao evidencia) -- um censo que os soma conta o mesmo defeito duas vezes e
# acusa uma cura que ja' esta' no sitio. Ficam nomeados e FORA, nunca somados em silencio.
SKIP_DIRS = ('_cache', '_redux-gate-mutants', '_legacy-electron', 'node_modules', '.git',
             '__pycache__', '_scratch', 'history', 'models')
EXTS = ('.py', '.js', '.mjs', '.json', '.html', '.css', '.cmd', '.bat', '.ps1', '.yml', '.yaml')

PIN_PATTERNS = (
    ('BrowserExecutableFolder', re.compile(r'BrowserExecutableFolder', re.I)),
    ('WEBVIEW2_BROWSER_EXECUTABLE_FOLDER', re.compile(r'WEBVIEW2_BROWSER_EXECUTABLE_FOLDER')),
    # O TERCEIRO VETOR e' a knob do proprio pywebview, e foi MEDIDO a 2026-11-11: o
    # `edgechromium.py` dela' faz `props.BrowserExecutableFolder = runtime_path`. Um valor aqui
    # e' um pin, mesmo que o nosso codigo nao escreva a palavra `BrowserExecutableFolder`.
    ('pywebview WEBVIEW2_RUNTIME_PATH', re.compile(r'WEBVIEW2_RUNTIME_PATH')),
    # A FORMA DA VERSAO e' o segundo braco do mesmo pin: uma pasta com nome de versao so' entra no
    # codigo a mao, e o Edge usa quatro campos.
    ('versao-literal', re.compile(r'\b1[0-9]{2}\.[0-9]+\.[0-9]{4}\.[0-9]{1,3}\b')),
)

RUNTIME_ROOT = r'C:\Program Files (x86)\Microsoft\EdgeWebView\Application'


def walk_population(root=APP):
    """Todo ficheiro que EMBARCA, com o caminho relativo. Ordem estavel."""
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.lower().endswith(EXTS):
                out.append(os.path.join(base, name))
    return out


def scan_pins(paths):
    """[(rotulo, ficheiro, linha, texto)] -- a linha que fixa um runtime."""
    hits = []
    for path in paths:
        try:
            text = io.open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pat in PIN_PATTERNS:
                if pat.search(line):
                    # `relpath` atravessa unidades com um `ValueError` -- medido no primeiro uso
                    # (o `tempfile` desta maquina cai num volume diferente do repo, e o controle
                    # morria antes de dizer "nao apliquei", que e' a classe do instrumento que
                    # confunde crash com veredicto).
                    try:
                        shown = os.path.relpath(path, ROOT)
                    except ValueError:
                        shown = path
                    hits.append((label, shown, lineno, line.strip()[:120]))
    return hits


def installed_runtimes(root=RUNTIME_ROOT):
    """[(versao, pasta, exe_existe)] das pastas que tem cara de versao."""
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if not os.path.isdir(full):
            continue
        if not re.match(r'^\d+\.\d+\.\d+\.\d+$', name):
            continue
        exe = os.path.join(full, 'msedgewebview2.exe')
        out.append((name, full, os.path.isfile(exe)))
    return out


def version_key(text):
    return tuple(int(p) for p in text.split('.'))


def greatest(runts):
    """A MAIOR versao instalada, por comparacao NUMERICA -- nunca por ordem alfabetica."""
    best = None
    for name, _full, has_exe in runts:
        if not has_exe:
            continue
        key = version_key(name)
        if best is None or key > best[0]:
            best = (key, name)
    return best[1] if best else None


def loader_resolve(folder=None):
    """O que o LOADER resolve, chamando a funcao do proprio WebView2Loader.dll.

    Sem `folder` e' exatamente o caminho que o `pywebview` usa ao criar o ambiente. Devolve
    (versao|None, erro). Um `None` NUNCA e' "nao ha problema": e' CANNOT-MEASURE.
    """
    import importlib.util
    spec = importlib.util.find_spec('webview')
    if spec is None or not spec.origin:
        return None, 'pywebview ausente'
    base = os.path.dirname(spec.origin)
    dll = os.path.join(base, 'lib', 'runtimes', 'win-x64', 'native', 'WebView2Loader.dll')
    if not os.path.isfile(dll):
        return None, 'WebView2Loader.dll ausente em %s' % dll
    try:
        lib = ctypes.WinDLL(dll)
        fn = lib.GetAvailableCoreWebView2BrowserVersionString
        fn.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPWSTR)]
        fn.restype = ctypes.c_long
        out = wintypes.LPWSTR()
        hr = fn(folder, ctypes.byref(out))
    except (OSError, AttributeError) as exc:            # pragma: no cover - host sem loader
        return None, '%s: %s' % (type(exc).__name__, exc)
    if (hr & 0xFFFFFFFF) != 0:
        return None, 'HRESULT 0x%08X' % (hr & 0xFFFFFFFF)
    return (out.value or None), 'ok'


def shell_uses_the_loader():
    """A shell NAO passa pasta propria -- a unica forma de a resolucao ser a do loader.

    Julga o CODIGO, nao uma frase: le `app/webview/sotto_webview.py` por `ast` e exige que nenhuma
    chamada de `Socket`/`CoreWebView2Environment`/`create_window` receba um caminho de runtime. O
    que ele NAO faz e' proibir `browser_args` (o `--cdp-port` escopado e' outro invariante).
    """
    path = os.path.join(APP, 'webview', 'sotto_webview.py')
    if not os.path.isfile(path):
        return False, 'sotto_webview.py ausente'
    src = io.open(path, encoding='utf-8', errors='replace').read()
    tree = ast.parse(src)
    banned = ('BrowserExecutableFolder', 'browserExecutableFolder', 'RuntimePath', 'runtime_path')
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in getattr(node, 'keywords', []) or []:
            if kw.arg in banned:
                return False, 'chamada com %s= em %s' % (kw.arg, os.path.relpath(path, ROOT))
    return True, 'nenhuma chamada passa pasta de runtime'


def pywebview_knob():
    """O valor VIVO da knob do pywebview -- a pasta que ela passaria ao loader.

    Devolve (valor|None, erro). `None` com erro vazio significa "vazia", que e' o estado correto:
    sem ela o `props.BrowserExecutableFolder` fica por omissao e quem responde e' o loader.
    """
    try:
        import webview
    except Exception as exc:                            # noqa: BLE001
        return None, '%s: %s' % (type(exc).__name__, exc)
    try:
        return webview.settings.get('WEBVIEW2_RUNTIME_PATH'), ''
    except Exception as exc:                            # noqa: BLE001
        return None, '%s: %s' % (type(exc).__name__, exc)


def judge(pins, runts, resolved, greatest_v, uses_loader, knob=None, knob_err=''):
    """As cinco arms. Cada uma e' um invariante, nunca um numero de gosto."""
    arms = []

    def arm(name, ok, detail):
        arms.append((name, bool(ok), detail))

    arm('A1 nenhum pin de runtime embarca',
        not pins,
        '%d achado(s)' % len(pins) if pins else 'zero BrowserExecutableFolder / var / versao-literal')
    arm('A2 o inventario instalado e coerente',
        bool(runts) and all(has for _n, _f, has in runts),
        '%d pasta(s): %s' % (len(runts), ', '.join(n for n, _f, _h in runts) or '-'))
    arm('A3 o loader resolve (nao e CANNOT-MEASURE)',
        bool(resolved),
        'resolvido=%s' % resolved)
    arm('A4 o loader resolve a MAIOR instalada',
        bool(resolved) and resolved == greatest_v,
        'resolvido=%s maior=%s' % (resolved, greatest_v))
    arm('A5 a shell resolve pelo loader (nao passa pasta)',
        uses_loader,
        'ok' if uses_loader else 'a shell passa um caminho de runtime')
    # A6 NAO PROIBE a knob: a ordem do dono aceita-a desde que ela aponte para a MAIOR. Uma knob
    # fixada na .42 e' o unico caminho para a app acabar na versao antiga.
    if knob_err:
        arm('A6 a knob do pywebview esta vazia ou aponta a MAIOR', False,
            'nao medivel: %s' % knob_err)
    elif knob:
        arm('A6 a knob do pywebview esta vazia ou aponta a MAIOR', False,
            'WEBVIEW2_RUNTIME_PATH=%r (fixa o runtime a mao)' % knob)
    else:
        arm('A6 a knob do pywebview esta vazia ou aponta a MAIOR', True,
            'vazia -- o loader escolhe, e escolheu %s' % resolved)
    return arms


def main(argv):
    neg = '--neg-arm' in argv

    if neg:
        return neg_arm()

    paths = walk_population()
    pins = scan_pins(paths)
    runts = installed_runtimes()
    resolved, why = loader_resolve(None)
    greatest_v = greatest(runts)
    uses_loader, loader_detail = shell_uses_the_loader()
    knob, knob_err = pywebview_knob()

    print('WEBVIEW2-RUNTIME')
    print('  populacao: %d ficheiro(s) em app/ (%s fora por serem copia ou evidencia)'
          % (len(paths), ', '.join(SKIP_DIRS)))
    print('  instaladas: %s' % (', '.join('%s%s' % (n, '' if h else '(SEM EXE)')
                                          for n, _f, h in runts) or '-'))
    print('  loader: %s -> %s' % (why, resolved))
    print('  webview.settings[WEBVIEW2_RUNTIME_PATH]: %r%s'
          % (knob, ('  (erro: %s)' % knob_err) if knob_err else ''))
    if pins:
        print('  PINS:')
        for label, rel, lineno, text in pins:
            print('    %-34s %s:%d  %s' % (label, rel, lineno, text))
    arms = judge(pins, runts, resolved, greatest_v, uses_loader, knob, knob_err)
    print('')
    fails = []
    for name, ok, detail in arms:
        print('  %-46s %-5s %s' % (name, 'PASS' if ok else 'FAIL', detail))
        if not ok:
            fails.append(name)
    print('')
    if fails:
        print('VERDICT: FAIL -- %s' % '; '.join(fails))
        return 1
    print('VERDICT: PASS (%d/%d arm(s)) -- a shell herda a MAIOR instalada e nada a fixa'
          % (len(arms), len(arms)))
    return 0


def neg_arm():
    """O CONTROLO: um pin plantado tem de derrubar a arm A1, cada forma pela SUA arm.

    Nada aqui toca no repo: o mutante vive num ficheiro temporario que entra na populacao por
    `scan_pins`, e o "inventario" do segundo controle e' uma lista construida a mao. Um controle
    que escrevesse no repo provava o instrumento e estragava a arvore -- a licao que esta casa ja'
    pagou com um `cmd.exe` aberto na tela do dono.
    """
    print('WEBVIEW2-RUNTIME -- NEG-ARM')
    cases = []
    tmpdir = tempfile.mkdtemp(prefix='wv2-neg-')

    planted = {
        'pasta-fixada': 'os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = '
                        'r"C:\\Program Files (x86)\\Microsoft\\EdgeWebView\\Application\\1" + "57.0.4341.42"\n',
        'kwarg-do-loader': 'env = CoreWebView2Environment.CreateAsync(browserExecutableFolder='
                           'path, userDataFolder=udf)\n',
        'versao-literal-doc': 'O runtime desta maquina e\' 157.0.4341.42 e a app usa esse.\n',
        'knob-do-pywebview': "webview.settings['WEBVIEW2_RUNTIME_PATH'] = "
                             "r'C:\\EdgeWebView\\Application\\157.0.4341.42'\n",
    }
    for name, body in planted.items():
        path = os.path.join(tmpdir, name + '.py')
        io.open(path, 'w', encoding='utf-8').write(body)
        try:
            hits = scan_pins([path])
        except Exception as exc:                        # noqa: BLE001
            # UM CONTROLO QUE MORRE NAO APANHOU NADA. Antes desta guarda o `ValueError` do
            # `relpath` devolvia rc=1 e o `:expectred` lia-o como "o controlo apanhou" -- o
            # verde que se paga sozinho.
            print('  %-24s MORTO  %s: %s' % (name, type(exc).__name__, exc))
            cases.append(False)
            continue
        ok = bool(hits)
        print('  %-24s %s  %s' % (name, 'APANHADO' if ok else 'NAO-APANHADO',
                                  hits[0][0] if hits else 'o padrao nao pegou'))
        cases.append(ok)

    # O SEGUNDO CONTROLE E' O DO JUIZ, nao o do padrao: um inventario com duas pastas onde a MAIOR
    # nao e' a ultima em ordem alfabetica. Um `max()` de strings ou um `[-1]` da' a resposta errada.
    fake = [('157.0.4341.42', '/x/157.0.4341.42', True),
            ('157.0.4341.46', '/x/157.0.4341.46', True),
            ('99.0.4341.9', '/x/99.0.4341.9', True)]
    got = greatest(fake)
    ok = got == '157.0.4341.46'
    print('  %-24s %s  maior-de-tres=%s (a 99.0.4341.9 e\' a MENOR por numero)' %
          ('juiz-do-maior', 'APANHADO' if ok else 'NAO-APANHADO', got))
    cases.append(ok)

    # E o terceiro: uma pasta sem exe NAO pode ser escolhida.
    fake2 = [('157.0.4341.46', '/x/157.0.4341.46', False),
             ('157.0.4341.42', '/x/157.0.4341.42', True)]
    got2 = greatest(fake2)
    ok = got2 == '157.0.4341.42'
    print('  %-24s %s  pasta-sem-exe ignorada -> %s' %
          ('maior-exige-exe', 'APANHADO' if ok else 'NAO-APANHADO', got2))
    cases.append(ok)

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

    # O JUIZ DA KNOB: com ela FIXADA no mais antigo o veredicto tem de ser vermelho, e com ela
    # vazia verde -- uma arm que aceitasse as duas nao julga nada.
    fake_runts = [('157.0.4341.42', '/x', True), ('157.0.4341.46', '/x', True)]
    red = judge([], fake_runts, '157.0.4341.42', '157.0.4341.42', True,
                knob=r'C:\EdgeWebView\Application\157.0.4341.42', knob_err='')
    green = judge([], fake_runts, '157.0.4341.46', '157.0.4341.46', True, knob=None, knob_err='')
    red_a6 = [ok for name, ok, _d in red if name.startswith('A6')]
    green_a6 = [ok for name, ok, _d in green if name.startswith('A6')]
    ok = (red_a6 == [False]) and (green_a6 == [True])
    print('  %-24s %s  knob-fixa=vermelho knob-vazia=verde' %
          ('juiz-da-knob', 'APANHADO' if ok else 'NAO-APANHADO'))
    cases.append(ok)

    caught = sum(1 for c in cases if c)
    total = len(cases)
    print('NEG-ARM-TOTAL: %d/%d' % (caught, total))
    if caught == total:
        print('NEG-ARM: PASS -- %d/%d controles apanhados' % (caught, total))
        return 1
    print('NEG-ARM: FAIL -- %d/%d' % (caught, total))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
