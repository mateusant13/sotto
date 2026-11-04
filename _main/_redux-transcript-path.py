#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sotto — CAN a parakeet line ever reach the disk transcript? (2026-11-01)

THE DEFECT THIS JUDGES, measured before it was written. The batch engine emits

    {"type": "caption", "text": ..., "start": ..., "end": ..., "producer": "redux"}

(`worker/redux_batch.py:185-197`) — **no `route`, no `final` flag** — and the
panel's choke point refused such a line one statement BEFORE the producer guard
that exists to accept it:

    const route = meta && meta.route;
    if (route !== 'final') return;          // <- refused FIRST
    if (!isCanonicalLine(meta)) return;

`caption-formulation.commit` derives `route` from the worker's `final` flag
(`routeFor`), so a batch line carried `provisional-draft` or nothing, and
`recordHistory` returned before the guard. Measured over the whole store the
same day: 2084 lines, of which the 502 without a `route=` suffix are ALL from
2026-10-06 or earlier, i.e. from before the provenance suffix existed. Since
2026-10-07 every line on disk has a `route=`, and **not one** says the batch
pass produced it. The owner said it himself, verbatim:

    "o historico simplesmente mostra a legenda ao vivo, inves de mostrar a
     versao processada pelo redux" (2026-10-06)

WHAT IS MEASURED HERE — both halves of the write, on the SHIPPED files:

  JS   `app/panel/history-source.js:transcriptRoute(meta)` decides the route at
       the panel's choke point. Arms: the batch shape (producer, no route) now
       yields `batch`; a closed worker line keeps `final`; a provisional draft
       is refused; a live line (no producer) is refused; an UNKNOWN route on a
       canonical line is refused rather than relabelled.
  PY   `app/webview/sotto_webview.py:_history_provenance` — extracted with
       `ast` and executed against stubs, so this oracle never imports the
       13k-line shell — must WRITE `route=batch` for that line, and must still
       refuse a route outside `HISTORY_ROUTES`.

THE NEGATIVE ARM (`--neg-arm`) mutates COPIES of both files back to the BEFORE
shape — the old `if (route !== 'final') return;` refusal, and a `HISTORY_ROUTES`
tuple without `batch` — and requires the batch arms to go RED. A detector that
still passes on the defective tree is not a detector; the live files are read,
never written.

    python _main/_redux-transcript-path.py
    python _main/_redux-transcript-path.py --neg-arm
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE_JS = os.path.join(ROOT, 'app', 'panel', 'history-source.js')
PANEL_JS = os.path.join(ROOT, 'app', 'panel', 'panel.js')
SHELL_PY = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')

# ---------------------------------------------------------------- JS half ----

JS_HARNESS = r"""
const modPath = process.argv[2];
const mod = require(modPath);
const cases = [
  ['batch-no-route',     {producer: 'redux'},                          'batch'],
  ['batch-unknown-route',{producer: 'redux', route: 'nonsense'},       null],
  ['worker-closed',      {producer: 'redux', route: 'final'},          'final'],
  ['provisional',        {producer: 'redux', route: 'provisional-draft'}, null],
  ['live-no-producer',   {route: 'final'},                             null],
  ['live-provisional',   {route: 'provisional-draft'},                 null],
  ['no-meta',            null,                                         null],
];
const out = cases.map(function (c) {
  const got = mod.transcriptRoute(c[1]);
  return {name: c[0], want: c[2], got: got, ok: got === c[2]};
});
process.stdout.write(JSON.stringify(out));
"""


def js_arms(source_path):
    """Run the shipped decision module (or a mutant copy) under node."""
    harness = os.path.join(HERE, '_redux-transcript-path-harness.js')
    with open(harness, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(JS_HARNESS)
    try:
        proc = subprocess.run(
            ['node', harness, source_path],
            capture_output=True, text=True, timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        try:
            os.unlink(harness)
        except OSError:
            pass
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or 'node failed').strip()[:400]
    try:
        return json.loads(proc.stdout), None
    except ValueError:
        return None, 'non-JSON: ' + proc.stdout[:200]


# -------------------------------------------------------------- PY half ----

def py_provenance_callable(shell_path, routes_override=None):
    """Extract `_history_provenance` with `ast` and bind it against stubs.

    The shell is 13k lines with import-time side effects; this oracle judges the
    ONE function that writes the suffix, so it reads the source text, keeps the
    module-level constants the function reads, and execs only that.
    """
    with open(shell_path, 'r', encoding='utf-8', newline='') as fh:
        src = fh.read()
    tree = ast.parse(src)
    keep = {}
    wanted_consts = {'HISTORY_ROUTES', 'HISTORY_ROUTE_SOURCES'}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id in wanted_consts:
                    keep[tgt.id] = ast.get_source_segment(src, node)
    if 'HISTORY_ROUTES' not in keep:
        raise SystemExit('FATAL: HISTORY_ROUTES nao encontrado em ' + shell_path)
    if routes_override is not None:
        keep['HISTORY_ROUTES'] = 'HISTORY_ROUTES = (' + ', '.join(
            repr(r) for r in routes_override) + ',)'
    fn_src = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == '_history_provenance':
                    fn_src = ast.get_source_segment(src, sub)
    if fn_src is None:
        raise SystemExit('FATAL: _history_provenance nao encontrada em ' + shell_path)

    ns = {}
    header = '\n'.join(keep[k] for k in ('HISTORY_ROUTES', 'HISTORY_ROUTE_SOURCES') if k in keep)
    body = (
        'import re\n'
        + header + '\n'
        + 'class Shell:\n'
        + '\n'.join('    ' + ln for ln in fn_src.splitlines()) + '\n'
        + '_call = Shell._history_provenance\n'
    )
    exec(compile(body, shell_path + ':extracted', 'exec'), ns)
    return ns['_call']


PY_ARMS = [
    # (name, options, expected substring or None for 'the write is refused')
    ('batch-line', {'route': 'batch', 'start': 12.5, 'reason': 'batch-pass'}, 'route=batch'),
    ('batch-line-start', {'route': 'batch', 'start': 12.5}, 'start=12.50'),
    ('route-outside-tuple', {'route': 'invented', 'start': 1.0}, None),
    ('no-route-at-all', {'start': 1.0}, None),
    ('provisional-line', {'route': 'provisional-draft', 'start': 3.0}, 'route=provisional-draft'),
]


def py_arms(shell_path, routes_override=None):
    call = py_provenance_callable(shell_path, routes_override)
    out = []
    for name, options, want in PY_ARMS:
        try:
            got = call(dict(options)) or ''
        except Exception as exc:  # noqa: BLE001 — an exception IS a failure of the arm
            out.append({'name': name, 'want': want, 'got': '<raised ' + type(exc).__name__ + '>',
                        'ok': False})
            continue
        ok = (want in got) if want else (got == '')
        out.append({'name': name, 'want': want, 'got': got, 'ok': bool(ok)})
    return out


# ------------------------------------------------------------- panel half ----

#: The REAL `recordHistory` executed against stubs. This is the CALL SITE, not a
#: copy of it: the function body is lifted out of `app/panel/panel.js` by brace
#: matching at run time, so a change to that body is judged by this arm too.
JS_PANEL_HARNESS = r"""
const fs = require('fs');
const panelPath = process.argv[2];
const sourcePath = process.argv[3];
const src = fs.readFileSync(panelPath, 'utf8');
const head = 'function recordHistory(text, reason, meta) {';
const at = src.indexOf(head);
if (at < 0) { process.stdout.write(JSON.stringify({error: 'recordHistory nao encontrada'})); process.exit(0); }
let i = at + head.length, depth = 1;
while (i < src.length && depth > 0) {
  const ch = src[i];
  if (ch === '{') depth += 1;
  else if (ch === '}') depth -= 1;
  else if (ch === "'" || ch === '"' || ch === '`') {   // skip string literals
    const quote = ch; i += 1;
    while (i < src.length && src[i] !== quote) { if (src[i] === '\\') i += 1; i += 1; }
  } else if (ch === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i += 1; }
  i += 1;
}
if (depth !== 0) { process.stdout.write(JSON.stringify({error: 'corpo desbalanceado'})); process.exit(0); }
const body = src.slice(at, i);

const prelude = `
  const sent = [];
  const MAX_HISTORY = 100;
  const historyEntries = [];
  let searchQuery = '';
  function pushEntry(e) { historyEntries.push(e); }
  function setHistoryNote(m) { notes.push(m); }
  const notes = [];
  function clockTime() { return '00:00:00'; }
  function errorText(e) { return String(e && e.message ? e.message : e); }
  function matches() { return false; }
  function renderSearchResults() {}
  function appendFeedRow() {}
  function galleryApi() { return null; }
  function renderGallery() {}
  let historyApi = null;
  let galleryPick = null;
  const window = { SottoHistorySource: require(sourcePath) };
`;
const call = `
  const results = [];
  function arm(name, meta, txt) {
    sent.length = 0;
    historyApi = { append: (t, o) => { sent.push({text: t, opts: o}); return Promise.resolve({entry: null}); } };
    recordHistory(txt || 'linha', 'batch-pass', meta);
    results.push({name: name, calls: sent.length, route: sent.length ? sent[0].opts.route : null});
  }
  arm('batch-no-route', {producer: 'redux', start: 12.5});
  arm('worker-closed',  {producer: 'redux', route: 'final', start: 3});
  arm('live-line',      {route: 'final', start: 4});
  arm('provisional',    {producer: 'redux', route: 'provisional-draft'});
  process.stdout.write(JSON.stringify({arms: results}));
`;
new Function('require', 'sourcePath', prelude + '\n' + body + '\n' + call)(require, sourcePath);
"""


def panel_arms(source_path=None):
    """Execute the shipped `recordHistory` and read what it hands the store."""
    harness = os.path.join(HERE, '_redux-transcript-path-panel.js')
    with open(harness, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(JS_PANEL_HARNESS)
    try:
        proc = subprocess.run(['node', harness, PANEL_JS, source_path or SOURCE_JS],
                              capture_output=True, text=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        try:
            os.unlink(harness)
        except OSError:
            pass
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or 'node failed').strip()[:400]
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return None, 'non-JSON: ' + proc.stdout[:200]
    if 'error' in data:
        return None, data['error']
    want = {
        'batch-no-route': (1, 'batch'),
        'worker-closed': (1, 'final'),
        'live-line': (0, None),
        'provisional': (0, None),
    }
    out = []
    for arm in data['arms']:
        w = want.get(arm['name'])
        if w is None:
            continue
        ok = (arm['calls'], arm['route']) == w
        out.append({'name': 'panel:' + arm['name'], 'want': str(w),
                    'got': 'calls=%d route=%r' % (arm['calls'], arm['route']), 'ok': ok})
    return out, None


# ------------------------------------------------------------- mutation ----

BEFORE_JS = """function transcriptRoute(meta) {
  const route = meta && meta.route;
  if (route !== 'final') return null;
  if (!isCanonicalLine(meta)) return null;
  return route;
}"""


def mutant_js(tmpdir):
    """A copy of the shipped module carrying the BEFORE refusal."""
    with open(SOURCE_JS, 'r', encoding='utf-8', newline='') as fh:
        # THE MUTANT IS WRITTEN WITH LF ON PURPOSE: the live file is CRLF (the panel
        # oracle refuses a pure-LF `panel.js`), and searching it for LF anchors
        # silently found nothing once -- the arm failed with `substring not found`
        # instead of proving a defect. Normalise the COPY, never the source.
        src = fh.read().replace('\r\n', '\n')
    start = src.index('function transcriptRoute(meta) {')
    end = src.index('\n}\n', start) + 3
    mutated = src[:start] + BEFORE_JS + '\n' + src[end:]
    if mutated == src:
        raise SystemExit('FATAL: a mutacao nao mudou o ficheiro JS')
    path = os.path.join(tmpdir, 'history-source-before.js')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(mutated)
    return path


def mutant_py(tmpdir):
    """A copy of the shell carrying the BEFORE tuple (no `batch`)."""
    with open(SHELL_PY, 'r', encoding='utf-8', newline='') as fh:
        src = fh.read()
    old = "HISTORY_ROUTES = ('final', 'provisional-draft', 'batch')"
    new = "HISTORY_ROUTES = ('final', 'provisional-draft')"
    if old not in src:
        raise SystemExit('FATAL: a tupla viva nao tem a forma esperada; mutacao impossivel')
    path = os.path.join(tmpdir, 'sotto_webview-before.py')
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(src.replace(old, new, 1))
    return path


def report(title, arms):
    bad = [a for a in arms if not a['ok']]
    for a in arms:
        mark = 'ok  ' if a['ok'] else 'FAIL'
        print('  %s %-22s want=%-22r got=%r' % (mark, a['name'], a['want'], a['got']))
    print('  %s: %d/%d' % (title, len(arms) - len(bad), len(arms)))
    return not bad


def main(argv):
    neg_arm = '--neg-arm' in argv
    print('=' * 78)
    print('O CAMINHO DO BATCH ATE O DISCO — %s' % ('NEG-ARM (mutantes)' if neg_arm else 'FICHEIROS VIVOS'))
    print('=' * 78)

    if not neg_arm:
        js, err = js_arms(SOURCE_JS)
        if js is None:
            print('RED  JS half: ' + err)
            return 1
        ok_js = report('JS transcriptRoute', js)
        py = py_arms(SHELL_PY)
        ok_py = report('PY _history_provenance', py)
        pan, perr = panel_arms()
        if pan is None:
            print('RED  panel half: ' + perr)
            return 1
        ok_pan = report('JS recordHistory (call site)', pan)
        print()
        if ok_js and ok_py and ok_pan:
            print('VERDICT: PASS — a batch line (producer=redux, no route) is ACCEPTED and'
                  ' recorded as route=batch; the live caption and unknown routes are refused')
            return 0
        print('VERDICT: FAIL')
        return 1

    with tempfile.TemporaryDirectory(prefix='redux-transcript-') as tmp:
        js_mut, err = js_arms(mutant_js(tmp))
        if js_mut is None:
            print('RED  the mutant did not even load: ' + err)
            return 1
        # The mutant MUST fail the batch arms; the refusals legitimately still hold.
        batch_arms = [a for a in js_mut if a['name'] == 'batch-no-route']
        caught_js = batch_arms and not batch_arms[0]['ok']
        report('JS mutant (old refusal)', js_mut)
        js_mut_src = mutant_js(tmp)
        pan_mut, pan_err = panel_arms(js_mut_src)
        if pan_mut is None:
            print('RED  the panel mutant did not load: ' + pan_err)
            return 1
        pan_batch = [a for a in pan_mut if a['name'] == 'panel:batch-no-route']
        caught_pan = bool(pan_batch) and not pan_batch[0]['ok']
        report('JS panel mutant (old refusal)', pan_mut)
        py_mut = py_arms(mutant_py(tmp))
        py_batch = [a for a in py_mut if a['name'] in ('batch-line', 'batch-line-start')]
        caught_py = bool(py_batch) and not any(a['ok'] for a in py_batch)
        report('PY mutant (tuple without batch)', py_mut)
        print()
        if caught_js and caught_py and caught_pan:
            print('NEG-ARM: PASS — all three mutants go RED on exactly the batch arms'
                  ' (1 JS arm, 1 panel arm, %d PY arms caught)' % len(py_batch))
            # HOUSE CONVENTION: a `red-as-expected-*` step declares rc **1** as the
            # expected value, because what the step proves is that the tree CAN go
            # red. Same code as its siblings so the `.cmd` line reads like theirs.
            return 1
        print('NEG-ARM: FAIL — a mutant still passed; the detector does not detect')
        return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
