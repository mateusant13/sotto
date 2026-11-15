#!/usr/bin/env python3
# NO-BUG: mede se a linha FECHADA chega ao historico (choke point de 2026-11-05); a classe nao tem id no leder
# -*- coding: utf-8 -*-
"""Sotto - does a CLOSED caption line actually REACH the transcript? (2026-11-05)

THE DEFECT THIS JUDGES. The owner, verbatim: *"e alias, o painel da direita fica
perdendo historico. nao sei se e' culpa sua."* MEASURED on his own running log
(`_main/webview-run.log`, 2026-11-05): 3830 `CAPTION_APPLIED` lines, ZERO
`HISTORY_APPEND`, and `history/2026-11-05/` does not exist. The panel painted
every caption and not ONE became a transcript line.

The choke point was two questions in two places (`panel.js recordHistory`):

    const route = sourceApi.transcriptRoute(meta);   // history-source.js
    if (!route) return;                               // <- silence
    if (!isCanonicalLine(meta)) return;               // <- producer === 'redux'

`isCanonicalLine` was the door that stayed shut: the ONLY producer it admits is
`'redux'`, which is the Parakeet batch pass (`worker/redux_batch.py`), and that
pass is OFF by default (`--redux-when-hidden`). Every other producer -- and the
live path declares NONE -- was dropped, and the drop was a bare `return` with no
line anywhere. A gate that cannot say no is not a gate.

THE CURE UNDER JUDGEMENT. One decision, in the DOM-free module, and provenance
instead of admission: a CLOSED line enters (`route=final` for the live worker's
closed line, `route=batch` for a Parakeet line) whichever pass closed it, a
`provisional-draft` never does, and the producer is written on the line as
`producer=` so the 2026-10-07 separation survives as a FACT. Every refusal is
reported (`HISTORY_REFUSED`), first occurrence and every 50th per signature.

ARMS (all over the REAL code, nothing re-implemented here):
  A  `history-source.js:historyDecision` -- the decision table.
  B  `history-source.js` + the REAL `recordHistory` lifted out of `panel.js` at
     run time -- does a live closed line reach `historyApi.append`? does a
     provisional one reach `bridge.historyRefused`? does the 50th repeat log?
  C  `sotto_webview.py:_history_provenance` -- is `producer=` written, and only
     from the declared vocabulary?
  D  `sotto_webview.py:history_append` (+ `history_merge`, `_history_tail`) on a
     TEMP root -- does a closed line land in `<root>/<date>/<hh>.md`, and does a
     provisional one leave the file untouched?

`--neg-arm` re-runs the arms against COPIES carrying the old refusal and
requires RED on exactly the closed-line arms. House convention: rc **1** is the
expected value of a `red-as-expected-*` step.
"""

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PANEL_JS = os.path.join(REPO, 'app', 'panel', 'panel.js')
SOURCE_JS = os.path.join(REPO, 'app', 'panel', 'history-source.js')
SHELL_PY = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')

_NO_WINDOW = dict(creationflags=subprocess.CREATE_NO_WINDOW,
                  startupinfo=subprocess.STARTUPINFO(
                      dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))


def run_node(script, *args):
    """Run a node one-liner / harness file; returns (stdout, error)."""
    try:
        proc = subprocess.run(['node', '-e', script] + list(args),
                              capture_output=True, text=True, timeout=120,
                              **_NO_WINDOW)
    except OSError as exc:  # noqa: BLE001 -- node missing IS a red
        return None, 'node nao arrancou: %r' % (exc,)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or 'node failed').strip()[:400]
    return proc.stdout, None


# ------------------------------------------------------- A: the decision ----

JS_DECISION = r"""
const m = require(process.argv[1]);
const cases = [
  ['live-closed',      {route:'final', start:13.2, source:'device:WASAPI loopback'}, 'final'],
  ['youtube-closed',   {route:'final', start:12.4, source:'external:youtube:track'}, 'final'],
  ['youtube-growing',  {route:'provisional-draft', start:12.4}, null],
  ['panel-deadline',   {route:'provisional-draft', start:3, reason:'hold-timeout'}, null],
  ['batch-redux',      {producer:'redux', start:9}, 'batch'],
  ['batch-with-route', {producer:'redux', route:'final', start:9}, 'final'],
  ['live-no-route',    {start:9}, null],
  ['unknown-route',    {route:'nonsense', start:1}, null],
  ['no-meta',          null, null],
];
const out = cases.map(function (c) {
  const route = m.transcriptRoute(c[1]);
  const refusal = m.historyRefusal(c[1]);
  return {name: c[0], want: c[2], got: route, refused: refusal ? refusal.reason : null,
          ok: route === c[2] && (route === null) === (refusal !== null)};
});
process.stdout.write(JSON.stringify(out));
"""


def decision_arms(source_path):
    stdout, err = run_node(JS_DECISION, source_path)
    if stdout is None:
        return None, err
    try:
        return json.loads(stdout), None
    except ValueError:
        return None, 'non-JSON: ' + stdout[:200]


# --------------------------------------------------- B: the call site ----

#: The REAL `recordHistory` AND `reportHistoryRefusal` lifted out of `panel.js`
#: by brace matching at run time. This is the CALL SITE, not a copy of it: a
#: change to those bodies is judged here too.
JS_PANEL = r"""
const fs = require('fs');
const panelPath = process.argv[1];
const sourcePath = process.argv[2];
const src = fs.readFileSync(panelPath, 'utf8').replace(/\r\n/g, '\n');
if (src.indexOf('let historyRefusals = 0;') < 0) {
  process.stdout.write(JSON.stringify({error: 'o contador `historyRefusals` desapareceu'}));
  process.exit(0);
}
function lift(head) {
  const at = src.indexOf(head);
  if (at < 0) return null;
  let i = at + head.length, depth = 1;
  while (i < src.length && depth > 0) {
    const ch = src[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') depth -= 1;
    else if (ch === "'" || ch === '"' || ch === '`') {
      const quote = ch; i += 1;
      while (i < src.length && src[i] !== quote) { if (src[i] === '\\') i += 1; i += 1; }
    } else if (ch === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i += 1; }
    i += 1;
  }
  if (depth !== 0) return null;
  return src.slice(at, i);
}
const rec = lift('function recordHistory(text, reason, meta) {');
const rep = lift('function reportHistoryRefusal(sourceApi, meta) {');
// `recordHistory` calls the panel's bounded `normaliseContext` (added with the
// context contract, 2026-11-09). It is a separate declaration, so lift it AND
// its field table into the same scope; without them the oracle reports a
// `ReferenceError` that belongs to the harness, not to the call site.
const ctxFields = (src.match(/const CONTEXT_FIELDS = \[[\s\S]*?\];/) || [''])[0];
const ctxFn = lift('function normaliseContext(meta) {');
if (!rec || !rep || !ctxFn || !ctxFields) {
  process.stdout.write(JSON.stringify({error: 'recordHistory/reportHistoryRefusal/normaliseContext nao encontrados'}));
  process.exit(0);
}

const prelude = `
  const sent = [];
  const refused = [];
  const MAX_HISTORY = 100;
  const historyEntries = [];
  let searchQuery = '';
  let historyRefusals = 0;
  const historyRefusalSeen = new Map();
  function pushEntry(e) { historyEntries.push(e); }
  const notes = [];
  function setHistoryNote(m) { notes.push(m); }
  function clockTime() { return '00:00:00'; }
  function errorText(e) { return String(e && e.message ? e.message : e); }
  function matches() { return false; }
  function renderSearchResults() {}
  function appendFeedRow() {}
  function galleryApi() { return null; }
  function renderGallery() {}
  let historyApi = null;
  let galleryPick = null;
  const bridge = { historyRefused: (p) => { refused.push(p); } };
  const window = { SottoHistorySource: require(sourcePath) };
`;
const call = `
  const results = [];
  function arm(name, meta, txt) {
    sent.length = 0; refused.length = 0;
    historyApi = { append: (t, o) => { sent.push({text: t, opts: o}); return Promise.resolve({entry: null}); } };
    recordHistory(txt || 'linha de teste', 'audio-gap 1.00s', meta);
    results.push({name: name, calls: sent.length,
                  route: sent.length ? sent[0].opts.route : null,
                  producer: sent.length ? sent[0].opts.producer : null,
                  refusals: refused.length,
                  reason: refused.length ? refused[0].reason : null,
                  where: refused.length ? refused[0].where : null,
                  final: refused.length ? refused[0].final : null});
  }
  arm('live-closed',     {route:'final', start:13.2, source:'device:WASAPI loopback'});
  arm('youtube-closed',  {route:'final', start:12.4, source:'external:youtube:track'});
  arm('batch-redux',     {producer:'redux', start:9});
  arm('provisional',     {route:'provisional-draft', start:3, reason:'hold-timeout'});
  arm('no-route',        {start:9});
  arm('producer-live',   {route:'final', start:4, producer:'live'});
  // THE 50TH REPEAT MUST LEAVE A LINE. The first provisional arm above already
  // logged once; 49 more of the SAME signature must produce exactly one more.
  refused.length = 0;
  for (let k = 0; k < 49; k += 1) {
    recordHistory('linha de teste', 'hold-timeout', {route:'provisional-draft', start:3});
  }
  const flood = {name: 'repeat-50th', calls: refused.length,
                 route: null, producer: null, refusals: refused.length,
                 reason: refused.length ? refused[0].reason : null,
                 where: refused.length ? refused[0].where : null,
                 final: refused.length ? refused[0].final : null};
  results.push(flood);
  // THE LOG LINE MUST NAME THE WHOLE CHAIN (2026-11-05, orchestrator): a reader
  // holding only the HISTORY_REFUSED line must see WHERE, the derived route, the
  // worker's own final vote, the producer and the reason -- no re-derivation.
  refused.length = 0;
  recordHistory('x', 'status-change',
    {route:'provisional-draft', start:3, final:false, producer:'live', source:'device:X'});
  const last = refused[0] || {};
  results.push({name: 'refusal-names-chain', calls: 0, route: null, producer: null,
                refusals: refused.length, reason: last.reason || null,
                where: last.where || null, final: last.final});
  process.stdout.write(JSON.stringify({arms: results}));
`;
if (src.indexOf('let historyRefusalSeen = new Map();') < 0) {
  process.stdout.write(JSON.stringify({error: 'historyRefusalSeen desapareceu'}));
  process.exit(0);
}
new Function('require', 'sourcePath', prelude + '\n' + ctxFields + '\n' + ctxFn + '\n' + rec + '\n' + rep + '\n' + call)(require, sourcePath);
"""

#: name -> (calls, route, producer, refusals, reason)
PANEL_WANT = {
    'live-closed': (1, 'final', None, 0, None, None, None),
    'youtube-closed': (1, 'final', None, 0, None, None, None),
    'batch-redux': (1, 'batch', 'redux', 0, None, None, None),
    'producer-live': (1, 'final', 'live', 0, None, None, None),
    'provisional': (0, None, None, 1, 'provisional-draft', 'panel/recordHistory', None),
    'no-route': (0, None, None, 1, 'no-route-no-producer', 'panel/recordHistory', None),
    'repeat-50th': (1, None, None, 1, 'provisional-draft', 'panel/recordHistory', None),
    'refusal-names-chain': (0, None, None, 1, 'provisional-draft', 'panel/recordHistory', False),
}


def panel_arms(source_path):
    stdout, err = run_node(JS_PANEL, PANEL_JS, source_path)
    if stdout is None:
        return None, err
    try:
        data = json.loads(stdout)
    except ValueError:
        return None, 'non-JSON: ' + stdout[:200]
    if 'error' in data:
        return None, data['error']
    out = []
    for arm in data['arms']:
        want = PANEL_WANT.get(arm['name'])
        if want is None:
            continue
        got = (arm['calls'], arm['route'], arm['producer'], arm['refusals'], arm['reason'],
               arm['where'], arm['final'])
        out.append({'name': 'panel:' + arm['name'], 'want': want, 'got': got,
                    'ok': got == want})
    return out, None


# --------------------------------------------------- C+D: the store --------

WANTED_CONSTS = ('HISTORY_ROUTES', 'HISTORY_ROUTE_SOURCES', 'HISTORY_PRODUCERS',
                 # `via=` (2026-11-09): os dois filtros do painel leem este campo,
                 # e sem a constante no namespace o `_history_provenance` extraido
                 # morre em `NameError` em vez de julgar o que escreve.
                 'HISTORY_VIAS',
                 'HISTORY_LINE_RE', 'HISTORY_DAY_RE', 'HISTORY_TAIL_RE',
                 'HISTORY_MERGE_WINDOW_S', 'HISTORY_RETENTION_H',
                 # `_history_context_for` le' esta janela desde 2026-11-09. O curto-
                 # circuito de `isinstance(last, dict)` a esconde no caminho comum,
                 # por isso a ausencia nao levantaria NameError -- e' pior: mediria a
                 # janela de OUTRO valor em silencio. Aqui ela vem do shell.
                 '_HISTORY_CTX_NEAR_S')
WANTED_FUNCS = ('history_merge', '_merge_key',
                # A ESCRITA ATOMICA DO FICHEIRO DA HORA (2026-11-15): as duas
                # acoes que REESCREVEM (`replace`, `replace_at`) passaram por ela
                # porque `open(path,'w')` truncava o ficheiro antes de escrever.
                # Sem ela no namespace, as arms do store morriam em NameError.
                'rewrite_lines_atomic')
WANTED_METHODS = ('history_append', '_history_tail', '_history_provenance',
                  '_history_path_for', '_history_prune',
                  '_history_context_for', '_history_app_target',
                  # A FUSAO DOS DOIS MOTORES (2026-11-09): `history_append`
                  # chama este metodo quando a linha nova traz `start=` e a acao
                  # e' `append`. Sem ele no namespace as arms do store morriam em
                  # `AttributeError` e o oraculo publicava FAIL no codigo de
                  # producao correcto -- um instrumento que cega o caminho comum.
                  '_history_find_start')


def store_namespace(shell_path):
    """Exec ONLY the store: the constants it reads and the functions it calls.

    The shell is 21k lines with import-time side effects; this arm judges the
    write path, so it reads the source text and keeps exactly that.
    """
    with open(shell_path, 'r', encoding='utf-8', newline='') as fh:
        src = fh.read()
    tree = ast.parse(src)
    consts = {}
    funcs = {}
    methods = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id in WANTED_CONSTS:
                    consts[tgt.id] = ast.get_source_segment(src, node)
        elif isinstance(node, ast.FunctionDef) and node.name in WANTED_FUNCS:
            funcs[node.name] = ast.get_source_segment(src, node)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name in WANTED_METHODS:
                    # `ast.get_source_segment` starts at `def`, NOT at the
                    # decorator, so `@staticmethod` would be lost and
                    # `self._history_tail(path)` would bind `self` as an
                    # argument. Put the decorators back explicitly.
                    seg = ast.get_source_segment(src, sub)
                    decos = '\n'.join('@' + ast.get_source_segment(src, d)
                                      for d in sub.decorator_list)
                    methods[sub.name] = (decos + '\n' + seg) if decos else seg
    missing = [n for n in WANTED_CONSTS if n not in consts]
    missing += [n for n in WANTED_FUNCS if n not in funcs]
    missing += [n for n in WANTED_METHODS if n not in methods]
    if missing:
        raise SystemExit('FATAL: nao encontrado em %s: %s' % (shell_path, ', '.join(missing)))
    body = (
        'import json, os, re, sys, threading, time\n'
        'sys.path.insert(0, %r)\n'
        'import history_context\n'
        'LOG = []\nWARN = []\n'
        'def log(*a, **k):\n    LOG.append(" ".join(str(x) for x in a))\n'
        'def warn(*a, **k):\n    WARN.append(" ".join(str(x) for x in a))\n'
        'HISTORY_ROOT = ""\n'
        'def app_target_request(args):\n    return None, None\n'
        % os.path.join(REPO, 'app', 'webview')
        + '\n'.join(consts[n] for n in WANTED_CONSTS) + '\n'
        + '\n'.join(funcs[n] for n in WANTED_FUNCS) + '\n'
        + 'class Shell:\n'
        + '\n'.join('    ' + ln for ln in '\n\n'.join(methods[n] for n in WANTED_METHODS).splitlines())
        + '\n'
    )
    ns = {}
    exec(compile(body, shell_path + ':extracted', 'exec'), ns)
    return ns


def disk_arms(shell_path):
    """The REAL `history_append` writing into a temp root."""
    ns = store_namespace(shell_path)
    shell_cls = ns['Shell']
    out = []

    def fresh():
        tmp = tempfile.mkdtemp(prefix='history-write-')
        ns['HISTORY_ROOT'] = tmp
        return tmp

    def files_under(root):
        found = []
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                found.append(os.path.join(dirpath, name))
        return found

    def lines(path):
        with open(path, 'r', encoding='utf-8') as fh:
            return [ln for ln in fh.read().splitlines() if ln.strip()]

    # (name, text, options, want_lines, want_substrings, want_absent)
    cases = [
        ('write-live-closed', 'What\'s crazy is that Astro at the highest.',
         {'route': 'final', 'start': 13.2, 'producer': None,
          'source': 'device:WASAPI loopback'}, 1, ['route=final'], ['producer=']),
        ('write-closed-producer', 'A second sentence the worker closed.',
         {'route': 'final', 'start': 44.0, 'producer': 'live'}, 1,
         ['route=final', 'producer=live', 'start=44.00'], []),
        ('write-batch-line', 'A parakeet line.',
         {'route': 'batch', 'start': 90.5, 'producer': 'redux'}, 1,
         ['route=batch', 'producer=redux'], []),
        ('refuse-provisional', 'the live caption',
         {'route': 'provisional-draft', 'start': 3}, 0, [], []),
        ('refuse-empty', '   ', {'route': 'final', 'start': 1}, 0, [], []),
    ]
    for name, text, options, want_n, want_subs, want_absent in cases:
        root = fresh()
        try:
            entry = shell_cls().history_append(text, dict(options))
        except Exception as exc:  # noqa: BLE001 -- an exception IS a red
            out.append({'name': 'store:' + name, 'want': 'no exception',
                        'got': '<raised %s: %s>' % (type(exc).__name__, exc), 'ok': False})
            continue
        names = files_under(root)
        got_lines = []
        for path in names:
            got_lines.extend(lines(path))
        problems = []
        if len(got_lines) != want_n:
            problems.append('lines=%d want=%d' % (len(got_lines), want_n))
        blob = '\n'.join(got_lines)
        for sub in want_subs:
            if sub not in blob:
                problems.append('missing %r' % sub)
        for sub in want_absent:
            if sub in blob:
                problems.append('unexpected %r' % sub)
        if want_n == 0 and entry is not None:
            problems.append('returned an entry for a refused line')
        if want_n == 1 and not entry:
            problems.append('returned None for a written line')
        out.append({'name': 'store:' + name, 'want': 'lines=%d %s' % (want_n, ' '.join(want_subs)),
                    'got': 'lines=%d' % len(got_lines) if not problems else '; '.join(problems),
                    'ok': not problems})
    # A REFUSAL MUST SAY WHY -- the store's own `HISTORY_REFUSED` line.
    refreshed = [ln for ln in ns['LOG'] if 'HISTORY_REFUSED' in ln]
    out.append({'name': 'store:refusal-logged', 'want': 'HISTORY_REFUSED reason=provisional-draft',
                'got': refreshed[0] if refreshed else '(nenhuma linha)',
                'ok': any('reason=provisional-draft' in ln for ln in refreshed)})

    # A ESCRITA E' ATOMICA, E ISSO PROVA-SE PELO TEMP, NAO PELA PROSA. O defeito
    # que estas arms fecham: `replace`/`replace_at` reescreviam com
    # `open(path,'w')`, que TRUNCA o alvo antes de escrever um byte. Um crash, um
    # corte de energia ou um disco cheio entre o truncate e o ultimo flush deixava
    # um ficheiro VAZIO -- e o historico e' a unica copia das palavras.
    # A arm A mede o EFEITO (o ficheiro da hora sobrevive intacto quando a
    # escrita falha a meio); a arm B mede o MECANISMO (o helper NAO abre o alvo em
    # 'w' e o temp e' um irmao com pid/tid no nome). Sem as duas, um `open(path,'w')`
    # posto de volta passaria a arm A num sistema de ficheiros que nunca falhou.
    atomic = ns['rewrite_lines_atomic']
    broot = tempfile.mkdtemp(prefix='history-atomic-')
    target = os.path.join(broot, '2026-11-15', '07.md')
    os.makedirs(os.path.dirname(target), exist_ok=True)
    original = ['- [07:00:01] the first line\n', '- [07:00:09] the second line\n']
    with open(target, 'w', encoding='utf-8', newline='') as fh:
        fh.writelines(original)
    try:
        # Force the failure AFTER the truncate would have happened: patch
        # os.replace for this one call. With `open(path,'w')` the target is
        # empty at this point and stays empty; with the temp+rename it is
        # untouched.
        real_replace = os.replace

        def explode(src, dst):
            raise OSError(28, 'No space left on device (planted)')

        os.replace = explode
        try:
            atomic(target, ['- [07:00:01] REPLACED\n'])
            raised = False
        except OSError:
            raised = True
        finally:
            os.replace = real_replace
        survivors = []
        if os.path.exists(target):
            with open(target, 'r', encoding='utf-8') as fh:
                survivors = fh.readlines()
        leftovers = [n for n in os.listdir(os.path.dirname(target)) if n != '07.md']
        ok = (raised and survivors == original and not leftovers)
        out.append({'name': 'store:atomic-keeps-file-on-failure',
                    'want': 'raise + file intact (%d lines) + no temp left' % len(original),
                    'got': '%s / %d line(s) / temp=%s'
                           % ('raised' if raised else 'NO RAISE',
                              len(survivors), leftovers or 'none'),
                    'ok': ok})
        # The successful path still writes, and leaves no temp behind.
        atomic(target, ['- [07:00:01] reposto\n'])
        with open(target, 'r', encoding='utf-8') as fh:
            written = fh.read()
        out.append({'name': 'store:atomic-writes-on-success',
                    'want': 'content replaced, no temp',
                    'got': json.dumps(written[:40]) + ' temp=%s'
                           % ([n for n in os.listdir(os.path.dirname(target)) if n != '07.md'] or 'none'),
                    'ok': written == '- [07:00:01] reposto\n'
                          and not [n for n in os.listdir(os.path.dirname(target)) if n != '07.md']})
        # The mechanism: the helper must not `open()` the TARGET in write mode.
        # Judged on the AST, never on the text: the docstring NAMES the bug
        # (`open(path, 'w')`) and a substring test declared the cure guilty of
        # the defect it documents -- measured, this arm went RED on correct code
        # before it was rewritten.
        helper_src = io.open(shell_path, encoding='utf-8', newline='').read()
        helper_node = next(n for n in ast.parse(helper_src).body
                           if isinstance(n, ast.FunctionDef)
                           and n.name == 'rewrite_lines_atomic')
        opens_target_w = False
        for node in ast.walk(helper_node):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'open'):
                continue
            first = node.args[0] if node.args else None
            targets_path = (isinstance(first, ast.Name) and first.id == 'path')
            if not targets_path:
                continue
            mode = None
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == 'mode' and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if isinstance(mode, str) and ('w' in mode or 'a' in mode):
                opens_target_w = True
        has_pid_tid = 'os.getpid()' in ast.get_source_segment(helper_src, helper_node) \
            and 'get_ident()' in ast.get_source_segment(helper_src, helper_node)
        out.append({'name': 'store:atomic-mechanism',
                    'want': "no open(path,write) + pid/tid temp name",
                    'got': "opens_target_for_write=%s pid_tid=%s" % (opens_target_w, has_pid_tid),
                    'ok': (not opens_target_w) and has_pid_tid})
        # A FIACAO, nao so' o helper (a classe do `panel-deps`): as duas acoes
        # que reescrevem vivem DENTRO de `history_append`, e uma cura que so'
        # existisse no helper deixaria os dois `open(path,'w')` la' dentro.
        # Julgado pelo AST do metodo real: conta as chamadas e exige que nenhum
        # `open()` do alvo sobreviva em modo de escrita.
        append_node = next(n for n in ast.walk(ast.parse(helper_src))
                           if isinstance(n, ast.FunctionDef) and n.name == 'history_append')
        calls_atomic = sum(
            1 for n in ast.walk(append_node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == 'rewrite_lines_atomic')
        target_writes = 0
        for n in ast.walk(append_node):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'open':
                if not n.args or not (isinstance(n.args[0], ast.Name) and n.args[0].id == 'path'):
                    continue
                mode = n.args[1].value if len(n.args) > 1 and isinstance(n.args[1], ast.Constant) else None
                for kw in n.keywords:
                    if kw.arg == 'mode' and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                # `a` (acrescentar) e' o caminho NORMAL e nao perde nada;
                # so' `w`/`w+`/`r+` truncam o que la' esta'.
                if isinstance(mode, str) and 'w' in mode:
                    target_writes += 1
        out.append({'name': 'store:atomic-wired',
                    'want': "history_append calls it twice, 0 target writes in w",
                    'got': "calls=%d target_writes_w=%d" % (calls_atomic, target_writes),
                    'ok': calls_atomic >= 2 and target_writes == 0})
    finally:
        for dirpath, _dirs, names in os.walk(broot, topdown=False):
            for name in names:
                try:
                    os.remove(os.path.join(dirpath, name))
                except OSError:
                    pass
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
    return out, None


def provenance_arms(shell_path):
    """The REAL `_history_provenance`: which markers may be written."""
    ns = store_namespace(shell_path)
    call = ns['Shell']._history_provenance
    cases = [
        ('prov-live', {'route': 'final', 'start': 1.5, 'producer': 'live'},
         ['route=final', 'producer=live', 'start=1.50']),
        ('prov-redux', {'route': 'batch', 'start': 2, 'producer': 'redux'},
         ['route=batch', 'producer=redux']),
        ('prov-unknown-producer', {'route': 'final', 'producer': 'invented'},
         ['route=final']),
        ('prov-no-producer', {'route': 'final', 'start': 3}, ['route=final']),
        # DE ONDE VEIO O SOM (2026-11-09): os dois filtros do painel so'
        # funcionam se o campo estiver ESCRITO na linha, e so' se ele nunca for
        # inventado a partir de um valor que o escritor nao conhece.
        ('prov-via-pc', {'route': 'final', 'start': 4, 'via': 'pc'},
         ['route=final', 'via=pc']),
        ('prov-via-youtube', {'route': 'final', 'via': 'youtube'},
         ['via=youtube']),
        ('prov-via-unknown', {'route': 'final', 'via': 'inventado'},
         ['route=final']),
    ]
    out = []
    for name, options, subs in cases:
        got = call(dict(options)) or ''
        ok = all(s in got for s in subs)
        if 'invented' in got or 'inventado' in got:
            ok = False
        out.append({'name': name, 'want': ' '.join(subs), 'got': got, 'ok': ok})
    return out, None


# ------------------------------------------------------------ mutation ----

BEFORE_JS = """function historyDecision(meta) {
  const route = meta && meta.route;
  if (!isCanonicalLine(meta)) return { route: null, reason: 'not-canonical' };
  if (route && route !== 'final') return { route: null, reason: 'unknown-route' };
  return { route: route === 'final' ? 'final' : BATCH_ROUTE, reason: '' };
}
"""


def mutant_js(tmpdir):
    """A copy of the module carrying the OLD refusal (the producer gate)."""
    with open(SOURCE_JS, 'r', encoding='utf-8', newline='') as fh:
        # LF ON PURPOSE, same rule as `_redux-transcript-path.py`: the live file
        # is CRLF and the anchor search below is LF-only. Normalise the COPY.
        src = fh.read().replace('\r\n', '\n')
    start = src.index('function historyDecision(meta) {')
    end = src.index('\n}\n', start) + 3
    mutated = src[:start] + BEFORE_JS + '\n' + src[end:]
    if mutated == src:
        raise SystemExit('FATAL: a mutacao nao mudou o ficheiro JS')
    path = os.path.join(tmpdir, 'history-source-before.js')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(mutated)
    return path


def mutant_py(tmpdir):
    """A copy of the shell whose provenance never writes `producer=`."""
    with open(SHELL_PY, 'r', encoding='utf-8', newline='') as fh:
        # LF ON PURPOSE, same rule as the JS mutant: the live file is CRLF and
        # the anchor below is LF. A CRLF copy left the anchor unmatched once and
        # the "mutant" was byte-identical to the source -- the arm then passed
        # vacuously, which is exactly what a neg-arm exists to catch.
        src = fh.read().replace('\r\n', '\n')
    anchor = ("        if producer in HISTORY_PRODUCERS:\n"
              "            parts.append(f'producer={producer}')\n")
    if anchor not in src:
        raise SystemExit('FATAL: o carimbo `producer=` nao tem a forma esperada')
    mutated = src.replace(anchor, '', 1)
    if mutated == src:
        raise SystemExit('FATAL: a mutacao nao mudou o ficheiro PY')
    path = os.path.join(tmpdir, 'sotto_webview-before.py')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(mutated)
    return path


def mutant_atomic(tmpdir):
    """A copy of the shell whose rewrite TRUNCATES the target (the old bug).

    Repõe exactamente o defeito: a escrita volta a ser `open(path,'w')` sobre o
    próprio alvo, sem temp nem rename. O corpo é o de `_history_append` antes de
    2026-11-15 (ler as linhas, escrever por cima).
    """
    with open(SHELL_PY, 'r', encoding='utf-8', newline='') as fh:
        src = fh.read().replace('\r\n', '\n')
    start = src.index('def rewrite_lines_atomic(path, rows, newline=\'\'):')
    end = src.index('\ndef _history_clock_s(', start)
    old = (
        "def rewrite_lines_atomic(path, rows, newline=''):\n"
        "    \"\"\"The OLD write: truncate the target, then write.\"\"\"\n"
        "    parent = os.path.dirname(os.path.abspath(path))\n"
        "    if parent:\n"
        "        os.makedirs(parent, exist_ok=True)\n"
        "    with open(path, 'w', encoding='utf-8', newline=newline) as handle:\n"
        "        handle.writelines(rows)\n"
    )
    mutated = src[:start] + old + src[end:]
    if mutated == src:
        raise SystemExit('FATAL: a mutacao atomica nao mudou o ficheiro PY')
    path = os.path.join(tmpdir, 'sotto_webview-truncating.py')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(mutated)
    return path


def mutant_wiring(tmpdir):
    """A copy of the shell where the CALL SITE goes back to the truncating write.

    `mutant_atomic` prova que o helper e' atómico; este prova que o `history_append`
    o CHAMA. Um verde de fiação sem mutante próprio e' um verde que não pode falhar.
    """
    with open(SHELL_PY, 'r', encoding='utf-8', newline='') as fh:
        src = fh.read().replace('\r\n', '\n')
    anchor = "                    rewrite_lines_atomic(path, rows)\n"
    if anchor not in src:
        raise SystemExit('FATAL: o call site `replace_at` nao tem a forma esperada')
    old = ("                    with open(path, 'w', encoding='utf-8', newline='') as handle:\n"
           "                        handle.writelines(rows)\n")
    mutated = src.replace(anchor, old, 1)
    if mutated == src:
        raise SystemExit('FATAL: a mutacao de fiacao nao mudou o ficheiro PY')
    path = os.path.join(tmpdir, 'sotto_webview-unwired.py')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(mutated)
    return path


def report(title, arms):
    bad = [a for a in arms if not a['ok']]
    for a in arms:
        print('  %s %-26s want=%-34r got=%r'
              % ('ok  ' if a['ok'] else 'FAIL', a['name'], a['want'], a['got']))
    print('  %s: %d/%d' % (title, len(arms) - len(bad), len(arms)))
    return not bad


def main(argv):
    neg_arm = '--neg-arm' in argv
    print('=' * 78)
    print('UMA LINHA FECHADA CHEGA AO TRANSCRIPT? — %s'
          % ('NEG-ARM (mutantes)' if neg_arm else 'FICHEIROS VIVOS'))
    print('=' * 78)

    if not neg_arm:
        js, err = decision_arms(SOURCE_JS)
        if js is None:
            print('RED  decisao: ' + err)
            return 1
        ok_a = report('A historyDecision', js)
        pan, perr = panel_arms(SOURCE_JS)
        if pan is None:
            print('RED  call site: ' + perr)
            return 1
        ok_b = report('B recordHistory (call site)', pan)
        prov, perr2 = provenance_arms(SHELL_PY)
        if prov is None:
            print('RED  provenance: ' + perr2)
            return 1
        ok_c = report('C _history_provenance', prov)
        disk, derr = disk_arms(SHELL_PY)
        if disk is None:
            print('RED  history_append: ' + derr)
            return 1
        ok_d = report('D history_append -> disco', disk)
        print()
        if ok_a and ok_b and ok_c and ok_d:
            print('VERDICT: PASS — a closed caption line (live or batch) reaches the')
            print('         transcript with its producer on the line; a provisional')
            print('         draft is refused AND says why.')
            return 0
        print('VERDICT: FAIL')
        return 1

    with tempfile.TemporaryDirectory(prefix='history-write-neg-') as tmp:
        mut = mutant_js(tmp)
        js_mut, err = decision_arms(mut)
        if js_mut is None:
            print('RED  o mutante nem carregou: ' + err)
            return 1
        caught_a = any(a['name'] in ('live-closed', 'youtube-closed') and not a['ok']
                       for a in js_mut)
        report('A mutante (porta do produtor)', js_mut)
        pan_mut, perr = panel_arms(mut)
        if pan_mut is None:
            print('RED  o call site mutante nem carregou: ' + perr)
            return 1
        caught_b = any(a['name'] == 'panel:live-closed' and not a['ok'] for a in pan_mut)
        report('B mutante (call site)', pan_mut)
        py_mut = mutant_py(tmp)
        prov_mut, _ = provenance_arms(py_mut)
        caught_c = any(a['name'] == 'prov-live' and not a['ok'] for a in prov_mut)
        report('C mutante (sem producer=)', prov_mut)
        # A ATOMICIDADE tem de cair sob o mutante que trunca o alvo. Sem esta
        # metade, o `open(path,'w')` podia voltar sem um passo vermelho.
        trunc_mut = mutant_atomic(tmp)
        disk_mut, _ = disk_arms(trunc_mut)
        caught_d = any(a['name'] == 'store:atomic-keeps-file-on-failure' and not a['ok']
                       for a in disk_mut)
        caught_e = any(a['name'] == 'store:atomic-mechanism' and not a['ok']
                       for a in disk_mut)
        report('D mutante (escrita que trunca)', disk_mut)
        wire_mut = mutant_wiring(tmp)
        wire_mut_arms, _ = disk_arms(wire_mut)
        caught_f = any(a['name'] == 'store:atomic-wired' and not a['ok']
                       for a in wire_mut_arms)
        report('E mutante (call site desligado)', wire_mut_arms)
        print()
        if caught_a and caught_b and caught_c and caught_d and caught_e and caught_f:
            print('NEG-ARM: PASS — the closed-line arms go RED under the old refusal')
            print('         and the atomicity arms go RED under the truncating write')
            print('         (A 2 arms, B 2 arms, C 1 arm, D 2 arms, E 1 arm). rc=1 is EXPECTED.')
            return 1
        print('NEG-ARM: FAIL — um mutante passou; o detector nao detecta')
        return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
