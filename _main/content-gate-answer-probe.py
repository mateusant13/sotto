"""O QUE O GATE DE CONTEUDO RECEBE DA PAGINA -- medido, nao lido.

O DEFEITO QUE ISTO MEDE. O log do dono tem duas linhas e ambas dizem o mesmo:

    PANEL_CONTENT surface=strip ack=false applied="None" style=false sized=false
    size=0x0 head="" vis= wait_ms=16.0 why=bad-answer order=before-map ...

`size=0x0 head="" vis=` SAO OS DEFAULTS do `out` do gate, logo o ramo do
dicionario nunca correu: o shell nao soube dizer o que a pagina respondera. Tres
candidatos, e esta sonda separa-os por MEDICAO:

  (a) a pagina ainda nao definiu a funcao / o JS lanca (a string seria um
      `TypeError: ... is not a function`);
  (b) outra excepcao JS qualquer (a string seria a mensagem dela);
  (c) `exec_js` devolveu a STRING do JSON, nao o objecto -- o script da pagina
      faz `return JSON.stringify(out)` e o `ExecuteScriptAsync` do WebView2 JA'
      serializa o valor de retorno em JSON, portanto `json.loads` entrega aqui
      uma `str`.

COMO ELE MEDE. Copia os ficheiros que o `app/panel/panel.html` REAL referencia
para `$TMPDIR`, acrescenta-lhe UM script externo (a CSP do painel e'
`script-src 'self'`, logo inline nao corre -- e o mesmo idioma do
`_main/_theme-probe-arm.py`) que avalia o `CONTENT_GATE_JS` SHIPPED e escreve no
DOM (1) o `typeof` do valor, (2) o proprio valor, (3) `JSON.stringify(valor)`,
que e' exactamente o contrato do `ExecuteScriptAsync`, e (4) o custo em ms. O
Edge corre em `--headless=new`, sem janela, e o `--dump-dom` traz o resultado.

Depois o julgamento e' do SHELL, nao desta sonda: o `gate_answer_payload` /
`gate_verdict` / `gate_probe` sao extraidos do `app/webview/sotto_webview.py`
(por `ast`, sem importar pywebview) e executados sobre a resposta medida -- o
oraculo do show usa a MESMA extracção, logo um mutante no shell muda os dois.

    py -3 _main\\content-gate-answer-probe.py
    py -3 _main\\content-gate-answer-probe.py --surface panel --viewport 520x900
"""
import argparse
import ast
import html as html_mod
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PANEL_DIR = os.path.join(REPO, 'app', 'panel')
SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')

EDGE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
CHROME_CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]
PROBE_DIV = 'data-gate-probe'


def find_browser():
    for c in EDGE_CANDIDATES + CHROME_CANDIDATES:
        if os.path.isfile(c):
            return c
    return None


# ── O SHELL, LIDO SEM O IMPORTAR ────────────────────────────────────────────
def shell_literal(source_text, name):
    """O valor de um literal de modulo (`CONTENT_GATE_JS`, ...) -- por `ast`."""
    for node in ast.parse(source_text).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
    raise SystemExit('literal %s nao encontrado no fonte do shell' % (name,))


GATE_NAMES = ('NoAnswer', 'gate_defaults', 'gate_answer_payload', 'gate_verdict',
              'gate_should_retry', 'gate_probe')
#: Os numeros do gate tambem sao lidos do shell: um mutante que mude o orcamento
#: ou o piso de repeticao tem de mudar o julgamento do oraculo.
GATE_CONSTANTS = ('CONTENT_GATE_TIMEOUT_MS', 'CONTENT_GATE_RETRY_MIN_S',
                  'CONTENT_GATE_RETRY_PAUSE_S', 'CONTENT_GATE_ERROR_MAX_CHARS')


def shell_functions(source_text, names=GATE_NAMES):
    """As funcoes/classe PURAS do gate, executadas num namespace proprio.

    Nada aqui importa pywebview: as funcoes do gate sao puras por desenho, e e'
    isso que permite ao oraculo executar o codigo SHIPPED em vez de uma copia.
    """
    tree = ast.parse(source_text)
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            found[node.name] = ast.get_source_segment(source_text, node)
    missing = [n for n in names if n not in found]
    if missing:
        raise SystemExit('fonte do shell sem %s -- o instrumento nao julga '
                         'uma copia' % (', '.join(missing),))
    ns = {'json': json, 'time': __import__('time')}
    for name in GATE_CONSTANTS:
        ns[name] = shell_literal(source_text, name)
    for name in names:               # a ordem declarada: NoAnswer primeiro
        exec(compile(found[name], '<%s>' % (name,), 'exec'), ns)  # noqa: S102
    return ns


# ── A PAGINA REAL, COPIADA, COM UMA SONDA EXTERNA ───────────────────────────
_REF = re.compile(r'(?:src|href)="([^"#:]+)"')


def copy_panel(root):
    """Os ficheiros que o `panel.html` REAL referencia (a CSP e' `'self'`)."""
    with open(os.path.join(PANEL_DIR, 'panel.html'), encoding='utf-8') as fh:
        text = fh.read()
    shutil.copy2(os.path.join(PANEL_DIR, 'panel.html'), os.path.join(root, 'panel.html'))
    seen = set()
    for rel in _REF.findall(text):
        if rel in seen:
            continue
        seen.add(rel)
        src = os.path.join(PANEL_DIR, rel.replace('/', os.sep))
        if not os.path.isfile(src):
            continue
        dst = os.path.join(root, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    return text


def build_page(root, surface, gate_js):
    """O `panel.html` copiado + UM script externo que pergunta e publica."""
    text = copy_panel(root)
    script = ('(function () {\n'
              '  var name = %s;\n'
              '  var t0 = performance.now();\n'
              '  var v = (%s);\n'
              '  var ms = performance.now() - t0;\n'
              '  var wire = "";\n'
              '  try { wire = JSON.stringify(v); } catch (e) { wire = "WIRE-FAIL: " + e; }\n'
              '  var el = document.createElement("div");\n'
              '  el.setAttribute("%s-type", typeof v);\n'
              '  el.setAttribute("%s-ms", String(Math.round(ms * 100) / 100));\n'
              '  el.setAttribute("%s-value", String(v));\n'
              '  el.setAttribute("%s-wire", wire);\n'
              '  el.setAttribute("%s-vw", String(window.innerWidth));\n'
              '  el.setAttribute("%s-vh", String(window.innerHeight));\n'
              '  document.documentElement.appendChild(el);\n'
              '})();\n'
              % (json.dumps(surface), gate_js.replace('__NAME__', json.dumps(surface)),
                 PROBE_DIV, PROBE_DIV, PROBE_DIV, PROBE_DIV,
                 PROBE_DIV, PROBE_DIV))
    with open(os.path.join(root, 'gate-replay.js'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(script)
    marker = '<script src="gate-replay.js"></script>'
    if '</body>' in text:
        text = text.replace('</body>', '  ' + marker + '\n  </body>', 1)
    else:
        text += marker
    with open(os.path.join(root, 'panel.html'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return root


def _attr(dom, key):
    m = re.search(r'%s-%s="([^"]*)"' % (PROBE_DIV, re.escape(key)), dom)
    return html_mod.unescape(m.group(1)) if m else None


def page_answer(surface='strip', viewport=(380, 40), source_text=None,
                browser=None, root=None):
    """-> dict com o que a PAGINA devolve e o que o WebView2 entregaria.

    `value` e' o valor de retorno do script (o que o `exec_js` recebe como
    objecto Python depois do `json.loads`), `wire` e' o JSON que atravessa o
    `ExecuteScriptAsync`. `None` = a sonda nao correu (sem navegador).
    """
    exe = browser or find_browser()
    if exe is None:
        return {'ok': False, 'why': 'sem navegador (nem Edge nem Chrome)'}
    source_text = source_text if source_text is not None else open(
        SHELL, encoding='utf-8').read()
    gate_js = shell_literal(source_text, 'CONTENT_GATE_JS')
    owned = root is None
    root = root or tempfile.mkdtemp(prefix='gate-probe-')
    try:
        build_page(root, surface, gate_js)
        url = 'file:///' + os.path.join(root, 'panel.html').replace('\\', '/')
        # O CLIENTE REAL DA FAIXA E' 380x40, E O EDGE HEADLESS NAO O ACEITA
        # (medido: `--window-size=380,40` da' `innerWidth=0`, porque o Windows
        # nao deixa a janela ser mais pequena do que ~492x56). Por isso o
        # tamanho e' uma DICA: abaixo do minimo a flag sai e o que conta e' o
        # viewport MEDIDO, publicado pela propria sonda.
        cmd = [exe, '--headless=new', '--disable-gpu', '--no-first-run',
               '--no-default-browser-check', '--allow-file-access-from-files']
        if viewport and viewport[0] >= 200 and viewport[1] >= 200:
            cmd.append('--window-size=%d,%d' % viewport)
        cmd += ['--virtual-time-budget=6000',
               '--user-data-dir=' + os.path.join(root, '_profile'),
               '--dump-dom', url]
        proc = subprocess.run(
            cmd, capture_output=True, timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            startupinfo=subprocess.STARTUPINFO(
                dwFlags=getattr(subprocess, 'STARTF_USESHOWWINDOW', 0), wShowWindow=0))
        dom = proc.stdout.decode('utf-8', 'replace')
        value = _attr(dom, 'value')
        wire = _attr(dom, 'wire')
        if value is None:
            return {'ok': False, 'why': 'a sonda nao publicou nada (rc=%s)' % (proc.returncode,),
                    'stderr': proc.stderr.decode('utf-8', 'replace')[:400]}
        try:
            answer = json.loads(wire)
        except (TypeError, ValueError):
            answer = wire
        return {'ok': True, 'value_type': _attr(dom, 'type'), 'value': value,
                'wire': wire, 'answer': answer, 'gate_ms': float(_attr(dom, 'ms') or 0.0),
                'viewport': '%sx%s' % (_attr(dom, 'vw'), _attr(dom, 'vh')),
                'asked_viewport': '%dx%d' % viewport, 'surface': surface,
                'url': url}
    finally:
        if owned:
            shutil.rmtree(root, ignore_errors=True)


# ── O JULGAMENTO: O SHELL SHIPPED, NUNCA UMA COPIA ──────────────────────────
def classify(source_text, measured, surface='strip'):
    """A resposta medida -> o `out` do gate, pelo LACO do SHELL (nao por uma copia).

    Corre o `gate_probe` SHIPPED com um `ask` que devolve a resposta MEDIDA: e'
    o mesmo laco que o show usa, logo o `attempts`, o `why` e o `wait_ms` que
    saem daqui sao os do produto. A primeira resposta vestida faz ack na
    primeira tentativa -- e' isso que o replay tem de mostrar.
    """
    ns = shell_functions(source_text)
    budget = ns['CONTENT_GATE_TIMEOUT_MS'] / 1000.0
    return ns['gate_probe'](surface, lambda left: measured['answer'], budget)


def judge_live_line(line):
    """A impressao digital de uma linha `PANEL_CONTENT` VIVA, so' pelo texto.

    Devolve `(branch, ok)`:
      dict    os campos tem valores REAIS (o ramo do dicionario correu)
      default os campos sao os DEFAULTS -- o ramo do dicionario NAO correu
    """
    def field(key):
        m = re.search(r'\b%s=(\S+)' % (re.escape(key),), line)
        # `head=""` chega aqui com as duas aspas: o log publica `json.dumps`.
        return (m.group(1).strip('"') if m else '')

    vis = field('vis')
    head = field('head')
    size = field('size')
    if vis and vis != '?':
        return 'dict', True
    if head or (size and size != '0x0'):
        return 'dict', True
    return 'default', False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--surface', default='strip')
    ap.add_argument('--viewport', default='380x40')
    ap.add_argument('--log', default=os.path.join(HERE, 'webview-run.log'))
    args = ap.parse_args(argv)
    vw, _, vh = args.viewport.partition('x')
    source_text = open(SHELL, encoding='utf-8').read()
    viewport = (int(vw), int(vh)) if vw and vh else None
    measured = page_answer(args.surface, viewport, source_text)
    print('PROBE surface=%s viewport=%s' % (args.surface, args.viewport))
    if not measured.get('ok'):
        print('PROBE UNMEASURED: %s' % (measured.get('why'),))
        return 2
    print('  page value typeof=%s' % (measured['value_type'],))
    print('  page value  = %s' % (measured['value'][:300],))
    print('  wire (JSON) = %s' % (measured['wire'][:300],))
    print('  exec_js would return type=%s' % (type(measured['answer']).__name__,))
    print('  gate cost inside the page = %.2f ms (viewport=%s, pedido=%s)'
          % (measured['gate_ms'], measured['viewport'], measured['asked_viewport']))

    # (a)/(b): um script que LANCA -- o valor de retorno nunca e' a mensagem
    # dela quando o proprio script a apanha. A sonda mostra a forma do que a
    # pagina devolve e o `catch` do gate transforma numa string JSON com
    # `error`, portanto (a) e (b) exigem que a string NAO comece por '{'.
    print('  starts with "{" (JSON object) = %s'
          % (str(measured['value'].lstrip().startswith('{')).lower(),))

    old_branch = 'dict' if isinstance(measured['answer'], dict) else 'bad-answer (any non-dict answer)'
    print('  OLD gate branch for this answer  = %s' % (old_branch,))
    out = classify(source_text, measured, args.surface)
    print('  NEW gate verdict = ack=%s why=%s applied=%s style=%s sized=%s '
          'size=%dx%d head=%s vis=%s error=%s'
          % (str(out['ack']).lower(), out['why'], json.dumps(str(out['applied'])),
             str(out['style']).lower(), str(out['sized']).lower(), out['w'], out['h'],
             json.dumps(out['head']), out['vis'], json.dumps(out['error'])))

    # ── O REPLAY DAS DUAS LINHAS VIVAS ─────────────────────────────────────
    if os.path.exists(args.log):
        live = [ln for ln in open(args.log, encoding='utf-8', errors='replace')
                if 'PANEL_CONTENT' in ln and 'acker' not in ln]
        print('PROBE live PANEL_CONTENT lines=%d' % (len(live),))
        for ln in live[-4:]:
            branch, ok = judge_live_line(ln)
            print('  %s -> branch=%s fields-are-real=%s'
                  % (ln.split('sotto: ')[-1].strip()[:150], branch, str(ok).lower()))
    return 0 if out['ack'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
