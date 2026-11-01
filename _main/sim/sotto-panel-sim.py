"""O BANCO DE ENSAIO DO PAINEL, 1:1 com os ficheiros reais.

PORQUE ELE EXISTE (ordem do dono, 2026-11-01): *"se tu tiver dificuldade de usar o app, faz uma
simulacao quase que 1:1 num html dele funcionando."* A dificuldade e' medida, nao suposta: o painel
real so' nasce de um `map` de janela feito pelo shell, um `Alt+C` chega por `RegisterHotKey` do
Windows (e o input sintetico mede o Windows, nao a app -- AGENTS.md), e a janela do painel e' a tela
do dono. Nada disso pode ser dirigido de fora.

O QUE ESTE SERVIDOR **NAO** FAZ: nao copia o painel. Ele serve
`H:/sotto/app/panel/panel.html` LITERALMENTE, do disco, com os mesmos CSS/JS que a app carrega, e
injeta duas coisas antes do primeiro script da pagina:

  1. `BOOTSTRAP_JS`, extraido do proprio `sotto_webview.py` em tempo de servico -- e' o MESMO texto
     que o shell instala com `AddScriptToExecuteOnDocumentCreated`, nao uma segunda versao;
  2. um hospedeiro falso: `window.chrome.webview.postMessage` e `window.pywebview`
     (`_returnValuesCallbacks`, `api`) viram um registo em memoria, para a pagina poder falar.

O que dirige o painel e' o material real: `window.__sotto_emit(kind, payload)` -- o MESMO global que
o shell chama por `ExecuteScriptAsync`. Uma legenda simulada entra exactamente pelo caminho de uma
legenda real.

USO
    pythonw _main/sim/sotto-panel-sim.py            # serve em http://127.0.0.1:8123/
    python  _main/sim/sotto-panel-sim.py --check    # so' verifica que o painel e o bootstrap leem
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PANEL_DIR = os.path.join(ROOT, 'app', 'panel')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
SIM_HTML = os.path.join(HERE, 'panel-sim.html')

#: The page-side globals the shell calls. Kept as one list so the deck and the
#: audit read the same names (a renamed global must break one place, not two).
PAGE_GLOBALS = ('__sotto_emit', '__sotto_stats', '__sotto_info', '__sotto_history')


def bootstrap_js():
    """The shell's own BOOTSTRAP_JS, read out of the source at serve time."""
    with open(SHELL, 'r', encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    start = text.find('BOOTSTRAP_JS = r"""')
    if start < 0:
        raise SystemExit('BOOTSTRAP_JS not found in %s' % SHELL)
    start = text.index('"""', start) + 3
    end = text.find('"""', start)
    if end < 0:
        raise SystemExit('BOOTSTRAP_JS has no closing quotes')
    return text[start:end]


STUB = r"""
/* O HOSPEDEIRO FALSO -- pagina -> shell. Registar, nunca julgar. */
(function () {
  'use strict';
  window.__sim = { sent: [], ts: [], boot: performance.now() };
  var listeners = [];
  function record(kind, args) {
    var entry = { at: performance.now(), kind: kind, args: args };
    window.__sim.sent.push(entry);
    for (var i = 0; i < listeners.length; i++) { try { listeners[i](entry); } catch (e) {} }
  }
  function host(message) {
    /* O shell recebe [func, JSON.stringify([...]), valueId] (ver BOOTSTRAP_JS).
       Aqui so' se registam as chamadas; o deck as le. */
    var kind = 'raw';
    try {
      var payload = JSON.parse(message[1] || '[]');
      var inner = JSON.parse(payload[0] || '{}');
      kind = inner.kind || 'raw';
      record(kind, inner.payload);
    } catch (err) { record('unparsed', message); }
    /* pywebview responde sempre pelo `_returnValuesCallbacks[func][id]`; o
       bootstrap cria o slot que falta, por isso basta a funcao existir. */
    try {
      var slots = window.pywebview._returnValuesCallbacks;
      if (slots && slots.dispatch && typeof slots.dispatch['0'] === 'function') {
        slots.dispatch['0']({ isError: false });
      }
    } catch (err) {}
  }
  window.chrome = window.chrome || {};
  window.chrome.webview = window.chrome.webview || {};
  window.chrome.webview.postMessage = host;
  window.chrome.webview.addEventListener = function (_ev, fn) { listeners.push(fn); };
  window.chrome.webview.removeEventListener = function (_ev, fn) {
    var i = listeners.indexOf(fn); if (i >= 0) listeners.splice(i, 1);
  };
  var api = new Proxy({}, {
    get: function (_t, name) {
      return function () {
        var args = Array.prototype.slice.call(arguments);
        record('api.' + String(name), args);
        return Promise.resolve({ ok: true, sim: true });
      };
    },
  });
  window.pywebview = { api: api, _returnValuesCallbacks: {} };
})();
"""


def panel_html():
    """`panel.html`, byte-for-byte, with the two injections before its scripts."""
    with open(os.path.join(PANEL_DIR, 'panel.html'), 'r', encoding='utf-8',
              errors='replace') as fh:
        html = fh.read()
    inject = ('<script src="/sim-stub.js"></script>\n'
              '<script src="/sim-bootstrap.js"></script>\n')
    # BEFORE the first page script, so the bridge exists when the panel asks.
    marker = html.find('<script')
    if marker < 0:
        raise SystemExit('panel.html has no <script> tag to inject before')
    return html[:marker] + inject + html[marker:]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: A003 - http.server's own hook
        pass

    def _send(self, body, ctype='text/html; charset=utf-8', code=200):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - http.server's own name
        path = self.path.split('?')[0]
        if path in ('/', '/index.html', '/panel-sim.html'):
            with open(SIM_HTML, 'r', encoding='utf-8') as fh:
                return self._send(fh.read())
        if path == '/panel.html':
            return self._send(panel_html())
        if path == '/sim-bootstrap.js':
            return self._send(bootstrap_js(), 'application/javascript; charset=utf-8')
        if path == '/sim-stub.js':
            return self._send(STUB, 'application/javascript; charset=utf-8')
        # Everything else is the panel's own tree, untouched.
        rel = os.path.normpath(path.lstrip('/')).replace('/', os.sep)
        full = os.path.join(PANEL_DIR, rel)
        if not os.path.abspath(full).startswith(os.path.abspath(PANEL_DIR)):
            return self._send('forbidden', 'text/plain', 403)
        if not os.path.isfile(full):
            return self._send('not found', 'text/plain', 404)
        ctype = {
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.html': 'text/html; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.woff2': 'font/woff2',
            '.ico': 'image/x-icon',
        }.get(os.path.splitext(full)[1].lower(), 'application/octet-stream')
        with open(full, 'rb') as fh:
            return self._send(fh.read(), ctype)


def check():
    """Fail loudly rather than serving a bench that cannot load the panel."""
    boot = bootstrap_js()
    html = panel_html()
    problems = []
    if 'window.sotto' not in boot:
        problems.append('BOOTSTRAP_JS has no window.sotto')
    for name in PAGE_GLOBALS:
        if name not in boot:
            problems.append('%s not defined by the bootstrap' % name)
    if 'sim-stub.js' not in html or 'sim-bootstrap.js' not in html:
        problems.append('panel.html injection missing')
    for f in ('panel.css', 'panel.js'):
        if not os.path.isfile(os.path.join(PANEL_DIR, f)):
            problems.append('%s missing from app/panel' % f)
    print(json.dumps({'ok': not problems, 'problems': problems,
                      'bootstrap_bytes': len(boot), 'panel_bytes': len(html),
                      'globals': list(PAGE_GLOBALS)}, indent=1))
    return 0 if not problems else 2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8123)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    if args.check:
        return check()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    url = 'http://%s:%d/' % (args.host, args.port)
    print('sotto panel sim: %s  (panel.html served from %s)' % (url, PANEL_DIR))
    sys.stdout.flush()
    srv.serve_forever()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
