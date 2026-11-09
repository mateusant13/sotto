#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HISTORY CONTEXT -- compact origin/viewing metadata, search and export.

Owner ask, 2026-11-09: months later, reading a transcript line, know WHERE the
audio came from and WHAT was in front when it was said, and find it again by
that context -- without screenshots, screen recording, voice naming, credentials
or a repeated metadata blob on every line.

What this judges, always the REAL code (never a copy of the rule):

  1. `app/webview/history_context.py` -- bounded normalisation, URL query/
     fragment/userinfo removal, the compact token round-trip and the front-anchored
     `ctx1=` reader.
  2. The SHELL path: `history_append` writes the token, `_history_tail`/entries
     read it back, `history_search` matches context fields, `history_export`
     renders it oldest-first. A legacy line with no token reads `{}`.
  3. The NODE twin (`app/panel/history-store.js`, with its `ctx1=` codec in
     `app/panel/history-context-store.js`): same token shape, same dedupe
     decision, context readable/searchable/exported.

`--neg-arm` mutates a COPY: (1) the context decoder returns `{}`, (2) the shell
stops stamping the token, (3) the shell stops reading it, (4) the Node store
stops reading it, (5) the Node merge always appends, (6) the Node append stops
pruning, (7) the Python `_text` drops control characters instead of breaking the
word, (8) the Python `encode` erases an overflowing field instead of trimming it,
(9) the Node codec stops escaping `!'()*`, (10) the codec reader edges and BOM,
(11) the caption path stops observing the audio session, (12) the observer stops
clearing the snapshot. Each mutation must turn its own arm RED.

`--shell PATH` judges a COPY of the shell (the new-session arm's BEFORE proof).
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
CONTEXT = os.path.join(WEBVIEW, 'history_context.py')
STORE = os.path.join(ROOT, 'app', 'panel', 'history-store.js')
#: The `ctx1=` codec the store requires -- the file whose bytes must match the
#: Python twin. A mutant of EITHER file is judged through the pair.
CODEC_JS = os.path.join(ROOT, 'app', 'panel', 'history-context-store.js')
sys.path.insert(0, WEBVIEW)



def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def codec_arms(ctx):
    out = []
    raw = {
        'sourceApp': '  chrome.exe  ',
        'audioSource': 'device:mic',
        'viewingApp': 'Code',
        'viewingTitle': 'x' * 400,
        'viewingUrl': 'https://user:pass@Example.com/watch?v=secret#frag',
    }
    got = ctx.normalize(raw)
    out.append(('k1-app-normalizado', got.get('sourceApp'), 'chrome.exe'))
    out.append(('k2-titulo-limitado', len(got.get('viewingTitle') or ''),
                ctx.MAX_LEN['viewingTitle']))
    out.append(('k3-url-sem-query-fragmento-userinfo',
                got.get('viewingUrl'), 'https://example.com/watch'))
    out.append(('k3b-youtube-id-preservado',
                ctx.normalize({'viewingUrl':
                    'https://www.youtube.com/watch?v=MOZIBMBHK-8&t=30&list=x'}).get('viewingUrl'),
                'https://www.youtube.com/watch?v=MOZIBMBHK-8'))
    out.append(('k3c-outra-query-removida',
                ctx.normalize({'viewingUrl':
                    'https://example.com/watch?v=secret&token=abc'}).get('viewingUrl'),
                'https://example.com/watch'))
    out.append(('k3d-host-nu-sem-barra',
                ctx.normalize({'viewingUrl': 'https://example.com/'}).get('viewingUrl'),
                'https://example.com'))
    out.append(('k4-esquema-recusado',
                ctx.normalize({'viewingUrl': 'javascript:alert(1)'}).get('viewingUrl'),
                None))
    encoded = ctx.encode(got)
    out.append(('k5-token-comeca-ctx1', ctx.marker(encoded).startswith('ctx1='), True))
    out.append(('k6-roundtrip', ctx.decode(encoded), ctx.normalize(got)))
    out.append(('k7-token-in-le-o-primeiro',
                ctx.token_in('x <!-- ctx1=a:chrome.exe reason=ctx1=fake -->'),
                {'sourceApp': 'chrome.exe'}))
    out.append(('k8-sem-token-e-vazio', ctx.token_in('- [10:00:00] ola'), {}))
    out.append(('k9-reason-colar-nao-e-token',
                ctx.token_in('x <!-- reason=ctx1=fake -->'), {}))
    # A CONTROL CHARACTER IS A WORD BREAK, NOT SOMETHING TO DELETE (2026-11-09):
    # deleting it joined the words and made the same input read differently from
    # the Node twin (`page2` vs `page 2`) -- the two writers must agree.
    out.append(('k10-controlo-e-espaco',
                ctx.normalize({'viewingTitle': 'page\n2'}).get('viewingTitle'),
                'page 2'))
    # AN OVERSIZED NON-ASCII TITLE IS TRIMMED, NOT ERASED (2026-11-09): dropping
    # the whole field wrote NO token for a 120-character CJK title, so the line
    # lost its audio origin with it. Trimming keeps the origin readable.
    big = ctx.decode(ctx.encode({'viewingTitle': '漢' * 120}))
    out.append(('k11-titulo-cjk-nao-desaparece',
                bool(big.get('viewingTitle')), True))
    out.append(('k11b-token-cjk-limitado',
                len(ctx.encode({'viewingTitle': '漢' * 120})) <=
                ctx.MAX_TOKEN_CHARS, True))
    return out


def shell_arms(shell):
    tmp = tempfile.mkdtemp(prefix='hist-ctx-')
    had = getattr(shell, 'HISTORY_ROOT', None)
    shell.HISTORY_ROOT = tmp
    logs = []
    shell_log, shell_warn = shell.log, shell.warn
    shell.log = lambda msg: logs.append(str(msg))
    shell.warn = shell.log
    try:
        shim = shell.SottoShell.__new__(shell.SottoShell)
        ctx_a = {'sourceApp': 'chrome.exe', 'audioSource': 'device:mic',
                 'viewingApp': 'Code', 'viewingTitle': 'main.py',
                 'viewingUrl': 'https://example.com/watch?q=secret'}
        ctx_b = dict(ctx_a, viewingTitle='other.py')
        opts = {'route': 'final', 'routeSource': 'worker-stamped', 'start': 1.0}
        e1 = shim.history_append('same words', dict(opts, context=ctx_a))
        e2 = shim.history_append('same words', dict(opts, start=9.0, context=ctx_b))
        e3 = shim.history_append('same words', dict(opts, start=9.0, context=ctx_b))
        tail = shim.history_tail(10)
        entries = tail.get('entries') or []
        out = [
            ('s1-duas-falas-repetidas-entram', len(entries), 2),
            ('s2-primeira-contexto', entries[0].get('context') if entries else None,
             shell.history_context.normalize(ctx_a)),
            ('s3-segunda-contexto', entries[1].get('context') if len(entries) > 1 else None,
             shell.history_context.normalize(ctx_b)),
            ('s4-duplicata-mesmo-start-skip', (e3 or {}).get('action'), 'skip'),
            ('s5-tail-contexto-na-entrada', (e1 or {}).get('context', {}).get('viewingTitle'),
             'main.py'),
        ]
        hits_title = shim.history_search('main.py').get('hits') or []
        hits_other = shim.history_search('other.py').get('hits') or []
        hits_audio = shim.history_search('device:mic').get('hits') or []
        hits_app = shim.history_search('chrome.exe').get('hits') or []
        out.extend([
            ('s6-busca-titulo', len(hits_title), 1),
            ('s7-busca-outro-titulo', len(hits_other), 1),
            ('s8-busca-audio', len(hits_audio), 2),
            ('s9-busca-app', len(hits_app), 2),
        ])
        # RECEIPT-TIME RING, not commit-time sampling: `note_history_context`
        # captures when the line closes, `history_append` resolves by `start`.
        # The snapshot is replaced by a known value so the arm measures the
        # ring/fallback choice, not whatever window is in front right now.
        real_snapshot = shell.history_context.snapshot
        def fake_snapshot(meta=None, **kw):
            if isinstance(meta, dict) and isinstance(meta.get('context'), dict):
                return shell.history_context.normalize(meta['context'])
            return {'viewingApp': 'Fake', 'viewingTitle': 'seen',
                    'audioSource': 'device:mic'}
        shell.history_context.snapshot = fake_snapshot
        try:
            shim.note_history_context({'start': 5.0, 'final': True,
                                       'source': 'device:mic'})
            e6 = shim.history_append('ring line', {'route': 'final', 'start': 5.0})
            e7 = shim.history_append('late line', {'route': 'final', 'start': 99.0})
            shim.note_history_context({'start': 6.0, 'final': True,
                                       'context': {'viewingTitle': 'explicit'}})
            e8 = shim.history_append('explicit line',
                                     {'route': 'final', 'start': 6.0})
            shim.note_history_context({'start': 7.0, 'final': True,
                                       'source': 'device:mic'})
            e9 = shim.history_append('partial explicit', {
                'route': 'final', 'start': 7.0,
                'context': {'viewingTitle': 'override'}})
            # A NEAR line of the SAME session: this read must happen BEFORE the
            # new-session arm below clears the snapshot it is measuring.
            e_near = shim.history_append('near line',
                                         {'route': 'final', 'start': 7.5})
            # A NEW SESSION MUST NOT INHERIT THE OLD ONE (2026-11-09). The
            # worker's audio clock (`start`) RESTARTS AT ZERO on every respawn --
            # the fact `caption-formulation.js:1037` already relies on -- so a
            # line from the new session can carry a `start` inside the 8-second
            # near-match window of the PREVIOUS session's last line. The snapshot
            # is keyed by the session the producer stamps on the event
            # (`WorkerBridge._consume` -> the child process; `external_caption`
            # -> 'external'), and the first caption naming a different session
            # drops it.
            class _FakeBridge(object):
                def __init__(self, pid):
                    self.spawns = 1
                    self.child = type('Child', (object,), {'pid': pid})()
            shim.external_captions_active = False
            shim.emit_async = lambda *a, **k: None
            shim.push_caption_to_window = lambda *a, **k: None
            shim.bridge = _FakeBridge(101)                  # session A
            shim.note_history_context({
                'start': 5.0, 'final': True, 'historySession': 'session-a',
                'context': {'viewingTitle': 'old-session'}})
            shim.bridge = _FakeBridge(202)                  # respawn: session B
            # The new session's first PARTIAL: partials never note, so no
            # snapshot of their own exists -- which is exactly why the OLD
            # snapshot would survive them and be donated to the first commit.
            shim.on_worker_caption('new words', {
                'start': 9.0, 'final': False, 'historySession': 'session-b'})
            e_new = shim.history_append('new session line',
                                        {'route': 'final', 'start': 9.0})
            e_new_ring = shim.history_append('new session ring line',
                                             {'route': 'final', 'start': 5.0})
        finally:
            shell.history_context.snapshot = real_snapshot
        out.extend([
            ('s16-ring-por-start',
             (e6 or {}).get('context', {}).get('viewingTitle'), 'seen'),
            # A JANELA NAO SE DOA A UMA FALA LONGE (2026-11-09). `e7` e' uma
            # linha com `start=99.0`, 94 s depois da captura: o snapshot antigo
            # descreveria o que o dono olhava DEPOIS da fala transcrita, que e'
            # exatamente o defeito do ASR atrasado. A resposta honesta e' vazia.
            ('s17-ultimo-snapshot-nao-novo',
             bool((e7 or {}).get('context')), False),
            ('s17b-janela-proxima-ainda-serve',
             (e_near or {}).get('context', {}).get('viewingTitle'), 'seen'),
            ('s18-contexto-explicito-vence',
             (e8 or {}).get('context', {}).get('viewingTitle'), 'explicit'),
            ('s18b-explicito-parcial-mantem-audio',
             (e9 or {}).get('context', {}).get('audioSource'), 'device:mic'),
            ('s18c-explicito-parcial-sobrepoe-titulo',
             (e9 or {}).get('context', {}).get('viewingTitle'), 'override'),
        ])
        # The new-session values were captured INSIDE the `fake_snapshot` try
        # above, so the fallback read is the known `seen`, not the live window.
        out.extend([
            ('s25-nova-sessao-nao-herda-8s',
             (e_new or {}).get('context', {}).get('viewingTitle'), 'seen'),
            ('s25b-nova-sessao-nao-herda-anel',
             (e_new_ring or {}).get('context', {}).get('viewingTitle'), 'seen'),
        ])
        exported = shim.history_export('txt', 10)
        text = exported.get('text') or ''
        out.extend([
            ('s10-export-ordem-antiga', text.splitlines()[0].startswith('[20'),
             True),
            ('s11-export-viewing', 'view=Code "main.py"' in text, True),
            ('s12-export-audio', 'audio=device:mic' in text, True),
            ('s13-export-sem-query', 'q=secret' in text, False),
            ('s14-export-md', shim.history_export('md', 1).get('text', '').startswith('- '),
             True),
        ])
        # D1: the export must take the NEWEST `limit` and render them
        # oldest-first. `s10` only proves a 2026 date; this arm proves the
        # selection and the order with five entries.
        shim.history_append('export one', {'route': 'final', 'start': 20.0})
        shim.history_append('export two', {'route': 'final', 'start': 21.0})
        shim.history_append('export three', {'route': 'final', 'start': 22.0})
        newest_two = (shim.history_export('txt', 2).get('text') or '').splitlines()
        out.extend([
            ('s10b-export-mais-novos',
             [('export two' in line, 'export three' in line) for line in newest_two],
             [(True, False), (False, True)]),
            ('s10c-export-nao-inclui-velho',
             any('export one' in line for line in newest_two), False),
        ])
        # THE UI REACHES THE EXPORT (2026-11-09). The page cannot save a file
        # without a dialog -- and a dialog is a window on the owner's screen --
        # so the SHELL names the file, writes the SAME compact body (context
        # included) under the history root, and hands the path back for
        # `history.reveal`. Arms measure the file on disk, not the string.
        exp = shim.history_export_file('txt', 20)
        exp_path = exp.get('path') or ''
        exp_body = ''
        if exp_path and os.path.isfile(exp_path):
            with io.open(exp_path, 'r', encoding='utf-8') as fh:
                exp_body = fh.read()
        out.extend([
            ('s15-export-file-existe',
             bool(exp_path) and os.path.isfile(exp_path), True),
            ('s15b-export-file-na-raiz',
             os.path.dirname(os.path.abspath(exp_path)) == os.path.abspath(tmp), True),
            ('s15c-export-file-contexto', 'audio=device:mic' in exp_body, True),
            ('s15d-export-file-linhas',
             exp.get('entries'), len(exp_body.splitlines())),
            ('s15e-export-file-ext', exp_path.endswith('.txt'), True),
            ('s15f-export-file-nome', 'sotto-transcript-' in os.path.basename(exp_path),
             True),
        ])
        # An empty transcript is a NAMED refusal, not a 0-byte file: the panel
        # says "nothing to export" instead of opening an empty document.
        shell.HISTORY_ROOT = os.path.join(tmp, 'empty-root')
        out.append(('s15g-export-vazio-sem-ficheiro',
                    (shim.history_export_file('txt', 5) or {}).get('path'), ''))
        shell.HISTORY_ROOT = tmp
        # D2: a reason carrying `ctx1=` cannot spoof the writer's token.
        spoof = shell.SottoShell._history_provenance(
            {'route': 'final', 'start': 1.0,
             'reason': 'audio-gap 1.00s ctx1=a:evil'}, 'a:real')
        out.extend([
            ('s22-reason-nao-carrega-token', 'ctx1=a:evil' in spoof, False),
            ('s22b-token-real-sobrevive',
             shell.history_context.token_in(spoof), {'sourceApp': 'real'}),
        ])
        # D4: the ASR path's foreground URL is read from the live source cache.
        probe_shell = shell.SottoShell.__new__(shell.SottoShell)
        # The real owner: `ExternalCaptionWatcher` writes `_yt_fg_cache`; the
        # shell only holds the watcher (review R1).
        probe_shell.external_caption_watcher = shell.ExternalCaptionWatcher(
            probe_shell)
        probe_shell.external_caption_watcher._yt_fg_cache = (
            0, 'YouTube', 'https://www.youtube.com/watch?v=abc',
            time.monotonic())
        out.extend([
            ('s23-url-do-foreground', probe_shell._viewing_url(),
             'https://www.youtube.com/watch?v=abc'),
            ('s23b-url-do-player',
             shell.SottoShell._external_context(
                 'https://www.youtube.com/watch?v=abc'),
             {'viewingUrl': 'https://www.youtube.com/watch?v=abc'}),
            ('s23c-marcador-sem-url',
             shell.SottoShell._external_context('external:player'), {}),
        ])
        # D10: a non-ASCII title cannot make one token a blob.
        out.append(('s24-token-limitado',
                    len(shell.history_context.encode(
                        {'viewingTitle': '漢' * 120})) <=
                    shell.history_context.MAX_TOKEN_CHARS, True))
        # A LEGACY LINE HAS NO TOKEN AND MUST READ {} -- never a neighbour's
        # context, and never a fabricated one.
        legacy_root = tempfile.mkdtemp(prefix='hist-legacy-')
        day = os.path.join(legacy_root, '2026-01-01')
        os.makedirs(day, exist_ok=True)
        with io.open(os.path.join(day, '10.md'), 'w', encoding='utf-8',
                     newline='') as fh:
            fh.write('- [10:00:00] old line <!-- route=final start=1.00 -->\n')
        shell.HISTORY_ROOT = legacy_root
        legacy = shim.history_tail(5).get('entries') or []
        out.append(('s15-legado-contexto-vazio',
                    legacy[0].get('context') if legacy else 'no-entry', {}))
        # SIX MONTHS, NOT 48 H (owner, 2026-11-09). The prune is the one place
        # that decides how far back a months-later search can reach.
        ret_root = tempfile.mkdtemp(prefix='hist-ret-')
        for day in ('2026-01-01', '2026-11-01'):
            folder = os.path.join(ret_root, day)
            os.makedirs(folder, exist_ok=True)
            with io.open(os.path.join(folder, '10.md'), 'w', encoding='utf-8',
                         newline='') as fh:
                fh.write('- [10:00:00] line\n')
        had_ret = shell.HISTORY_RETENTION_H
        shell.HISTORY_RETENTION_H = 4320
        shell.HISTORY_ROOT = ret_root
        shim._history_pruned_stamp = None
        try:
            shim._history_prune()
        finally:
            shell.HISTORY_RETENTION_H = had_ret
        out.extend([
            ('s19-retencao-seis-meses', shell.HISTORY_RETENTION_H, 4320),
            ('s20-dia-antigo-apagado',
             os.path.isdir(os.path.join(ret_root, '2026-01-01')), False),
            ('s21-dia-recente-fica',
             os.path.isdir(os.path.join(ret_root, '2026-11-01')), True),
        ])
        return out, [m for m in logs if m.startswith('HISTORY_')], tmp
    finally:
        shell.log = shell_log
        shell.warn = shell_warn
        if had is not None:
            shell.HISTORY_ROOT = had


def _node(argv, env):
    """Lanca `node` SEM JANELA -- pelo helper da casa, nunca por flag a mao.

    O censo `console-window-audit` acusou `WEAK-FLAG` neste ficheiro duas vezes
    (2026-11-09): `creationflags=NO_WINDOW` sem `startupinfo` deixa o filho
    console-less e o Windows pinta uma consola NOVA -- foi assim que uma janela
    do Windows Terminal apareceu na tela do dono em 2026-11-08. O
    `_main/hidden-launch.py` e' o unico sitio desta arvore que passa o par
    (`CREATE_NO_WINDOW` + `STARTF_USESHOWWINDOW`/`SW_HIDE`) e espera o filho.
    """
    spec = importlib.util.spec_from_file_location(
        '_hist_hl', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'hidden-launch.py'))
    hl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hl)
    return hl.run(argv, capture=True, env=env, timeout=120)


JS_READ = r"""
const store = require(process.argv[1]);
const t = store.tail(50);
console.log(JSON.stringify(t.entries.map((e) => e.context)));
"""


def _json_line(out):
    """The child's last stdout line as JSON, split on `\\n` ONLY.

    `str.splitlines()` also breaks on U+0085 (NEL) and U+2028, and the codec
    arms print exactly those characters: a NEL surviving inside the JSON made
    the neg-arm die with `JSONDecodeError` instead of judging its mutant
    (measured 2026-11-09, `n13-node-espaco-do-js`). A parse failure is not a
    verdict.
    """
    return json.loads(out.strip().rsplit('\n', 1)[-1])


def js_read(store_path, root):
    env = dict(os.environ)
    env['SOTTO_HISTORY_ROOT'] = root
    rc, out, _err = _node(['node', '-e', JS_READ, store_path], env)
    if rc != 0:
        return []
    return _json_line(out)


JS_PROBE = r"""
const store = require(process.argv[1]);
const a = store.append('same words', {route:'final', start:1.0, context:{
  sourceApp:'chrome.exe', audioSource:'device:mic', viewingApp:'Code',
  viewingTitle:'main.py', viewingUrl:'https://example.com/watch?q=secret'}});
const b = store.append('same words', {route:'final', start:9.0, context:{
  sourceApp:'chrome.exe', audioSource:'device:mic', viewingApp:'Code',
  viewingTitle:'other.py', viewingUrl:'https://example.com/watch'}});
const c = store.append('same words', {route:'final', start:9.0, context:{
  sourceApp:'chrome.exe', audioSource:'device:mic', viewingApp:'Code',
  viewingTitle:'other.py', viewingUrl:'https://example.com/watch'}});
const d = store.append('same words more', {route:'final', start:20.0, context:{
  sourceApp:'chrome.exe', audioSource:'device:mic', viewingApp:'Code',
  viewingTitle:'other.py', viewingUrl:'https://example.com/watch'}});
const bare = store.append('bare host', {route:'final', start:21.0, context:{
  viewingUrl:'https://example.com/'}});
const t = store.tail(10);
const q = store.search('main.py');
const x = store.export('txt', 10);
console.log(JSON.stringify({actions:[a.action,b.action,c.action,d.action],
  entries:t.entries.length, ctx:t.entries[0].context, hits:q.hits.length,
  text:x.text, bare:bare.context}));
"""


def js_arms(store_path):
    tmp = tempfile.mkdtemp(prefix='hist-js-')
    env = dict(os.environ)
    env['SOTTO_HISTORY_ROOT'] = tmp
    rc, out, _err = _node(['node', '-e', JS_PROBE, store_path], env)
    if rc != 0:
        return [('j0-node', rc, 0)], {}
    data = _json_line(out)
    data['root'] = tmp
    out = [
        ('j1-duas-falas-repetidas', data['entries'], 4),
        ('j2-acoes', data['actions'], ['append', 'append', 'skip', 'append']),
        ('j3-contexto', data['ctx'].get('viewingTitle'), 'main.py'),
        ('j4-busca-contexto', data['hits'], 1),
        ('j5-export-contexto', 'view=Code "main.py"' in data['text'], True),
        ('j6-export-sem-query', 'q=secret' in data['text'], False),
        ('j7-url-host-paridade', data['bare'].get('viewingUrl'),
         'https://example.com'),
    ]
    return out, data


# ── the Node twin: one contract, two hosts ──────────────────────────────────
# The NODE twin is not on the shipped page, but it is a writer for the SAME
# files, so a rule that exists only on one host makes a line read differently
# depending on which arm wrote it. The Python twin's own merge table is owned by
# `_main/history-merge-oracle.py` (a1-a15); this table judges the SAME fifteen
# identities on the Node implementation, so the Node file cannot silently keep a
# rule the Python file already corrected.
_LONG = ("Because he's going for these uh these people you know those "
         "who's going for.")
_GROWN = _LONG[:-1] + ' there.'

MERGE_CASES = [
    # name, last (Node shape: `timeS`), body, nowS, start, audio, want
    ('g1-igual-skip', {'body': _LONG, 'timeS': 3601}, _LONG, 3601, None, None,
     'skip'),
    ('g2-cresceu-replace', {'body': _LONG, 'timeS': 3601, 'start': 1.68},
     _GROWN, 3602, 1.68, None, 'replace'),
    ('g3-encolheu-mesmo-start-skip',
     {'body': _GROWN, 'timeS': 3601, 'start': 1.68}, _LONG, 3601, 1.70, None,
     'skip'),
    ('g4-prefixo-dentro-da-janela', {'body': _LONG, 'timeS': 3600}, _GROWN,
     3601, None, None, 'replace'),
    ('g5-prefixo-fora-da-janela', {'body': _LONG, 'timeS': 3600}, _GROWN,
     3630, None, None, 'append'),
    ('g6-texto-alheio-appende', {'body': _LONG, 'timeS': 3600},
     'Is a very high chance.', 3601, None, None, 'append'),
    ('g7-sem-cauda-appende', None, _LONG, 3600, None, None, 'append'),
    ('g8-corpo-vazio-skip', {'body': _LONG, 'timeS': 3601}, '   ', 3601, None,
     None, 'skip'),
    ('g9-mesmo-start-texto-alheio',
     {'body': _LONG, 'timeS': 3601, 'start': 1.68}, 'Is a very high chance.',
     3601, 1.68, None, 'append'),
    ('g10-start-diferente-longe',
     {'body': _LONG, 'timeS': 3600, 'start': 1.68},
     _LONG[:-1] + ' there is.', 3640, 40.10, None, 'append'),
    ('g11-igual-start-diferente',
     {'body': _LONG, 'timeS': 3600, 'start': 1.0}, _LONG, 3601, 9.0, None,
     'append'),
    ('g12-igual-fora-da-janela', {'body': _LONG, 'timeS': 3600}, _LONG, 3700,
     None, None, 'append'),
    ('g13-igual-mesmo-start-skip',
     {'body': _LONG, 'timeS': 3600, 'start': 1.0}, _LONG, 3601, 1.0, None,
     'skip'),
    ('g14-igual-audio-diferente',
     {'body': _LONG, 'timeS': 3600, 'audio': 'device:mic'}, _LONG, 3601, None,
     'external:youtube', 'append'),
    ('g15-start-diferente-cresce',
     {'body': _LONG, 'timeS': 3600, 'start': 1.0}, _GROWN, 3601, 9.0, None,
     'append'),
]

#: The codec fixtures the Py/Node parity arms share. Each one is an input the
#: two hosts must normalise, encode and decode to the SAME bytes.
CODEC_FIXTURE = [
    ('controlo', {'viewingTitle': ' page\n2\t3\x00 '}),
    ('pontuacao', {'viewingTitle': 'a!\'()*b"c'}),
    ('cjk-longo', {'viewingTitle': '漢' * 120}),
    ('youtube-sem-barra',
     {'viewingUrl': 'https://www.youtube.com?v=MOZIBMBHK-8'}),
    ('youtube-barra-query',
     {'viewingUrl': 'https://www.youtube.com/watch?v=MOZIBMBHK-8&t=30'}),
    ('host-nu', {'viewingUrl': 'https://example.com/'}),
    ('userinfo-query',
     {'viewingUrl': 'https://user:pass@Example.com/watch?q=secret#frag'}),
    ('caminho-nao-ascii', {'viewingUrl': 'https://example.com/café x'}),
    ('cinco-campos', {'sourceApp': 'chrome.exe', 'audioSource': 'device:mic',
                      'viewingApp': 'Code', 'viewingTitle': 'main.py',
                      'viewingUrl': 'https://example.com/watch'}),
    ('titulo-ascii-longo', {'viewingTitle': 'x' * 400}),
    # The title is the field that overflows and the URL comes AFTER it: the
    # trim must keep the origin fields, trim the title and drop the URL.
    ('audio-e-titulo-grandes', {'audioSource': 'a' * 50,
                                'viewingApp': 'b' * 50,
                                'viewingTitle': '漢' * 120,
                                'viewingUrl': 'https://example.com/watch'}),
    # WHITESPACE EDGE (2026-11-09). Both characters are ordinary title bytes
    # that either writer percent-encodes, and JS `\s` and Python `str.split()`
    # disagree on BOTH: `\s` eats U+FEFF and leaves U+0085 (NEL) alone, Python
    # does the opposite. The canonical reader is Python, so NEL collapses to a
    # space and the BOM stays data on both hosts.
    ('nel-no-titulo', {'viewingTitle': 'a\x85b'}),
    ('bom-no-titulo', {'viewingTitle': 'a\ufeffb'}),
    ('nel-no-caminho', {'viewingUrl': 'https://example.com/a\x85b'}),
    # A non-BMP title at the 120-character bound: Python counts CODE POINTS, a
    # UTF-16 slice would cut the pair and produce a lone surrogate.
    ('nao-bmp-no-limite', {'viewingTitle': '😀' * 120}),
]

#: RAW TOKEN bodies -- the `ctx1=` body as it appears on disk, decoded WITHOUT
#: a roundtrip. Malformed percent escapes cannot be produced by either writer
#: (`quote(value, safe='')` / `percentEncode` emit only `%XX`), so they reach
#: the file from a hand edit or a corrupted line, which is exactly why the two
#: readers must agree on them and neither may erase the field.
TOKEN_FIXTURE = [
    ('escapado-zz', 't:100%zz'),
    ('escapado-curto', 't:a%2b'),
    ('percent-final', 't:50%'),
    ('utf8-invalido', 't:%E0%A4'),
    ('valido-e-invalido', 't:a%20b%zzc'),
    ('escape-no-url', 'u:https%3A%2F%2Fexample.com%2Fa%zzb'),
    ('nel-cru', 't:a\x85b'),
    ('bom-cru', 't:a\ufeffb'),
    ('bom-escapado', 't:%EF%BB%BFa'),
    ('varios-campos', 't:a:chrome.exe|v:Code'),
]

JS_NODE_PROBE = r"""
const fs = require('node:fs');
const store = require(process.argv[1]);
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const actions = payload.merge.map((c) => store.mergeDecision(
  c.last, c.body, c.nowS, c.start, c.audio));
const codec = payload.codec.map((raw) => {
  const token = store.encodeContext(raw);
  return { norm: store.normalizeContext(raw), token,
           decoded: store.decodeContext(token) };
});
const rawDecoded = payload.tokens.map((t) => store.decodeContext(t));
console.log(JSON.stringify({ actions, codec, rawDecoded,
                             retention: store.RETENTION_H }));
"""

JS_PRUNE_PROBE = r"""
const fs = require('node:fs');
const path = require('node:path');
const store = require(process.argv[1]);
const root = process.argv[2];
const p2 = (n) => String(n).padStart(2, '0');
const dayFor = (hoursBack) => {
  const d = new Date(Date.now() - hoursBack * 3600 * 1000);
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
};
const oldDay = dayFor(store.RETENTION_H + 72);
const keepDay = dayFor(24);
const outside = 'notes-not-a-day';
for (const [day, file] of [[oldDay, '10.md'], [keepDay, '10.md'],
                           [outside, 'x.md']]) {
  fs.mkdirSync(path.join(root, day), { recursive: true });
  fs.writeFileSync(path.join(root, day, file), '- [10:00:00] probe\n');
}
// THE WIRING, not only the function: an APPEND has to trigger the prune,
// exactly like `_history_prune()` at the top of `history_append`.
store.append('prune probe', { route: 'final', start: 1.0 });
console.log(JSON.stringify({
  retention: store.RETENTION_H,
  oldKept: fs.existsSync(path.join(root, oldDay)),
  keepKept: fs.existsSync(path.join(root, keepDay)),
  outsideKept: fs.existsSync(path.join(root, outside)),
}));
"""


def _prune_probe(store_path, extra_env=None):
    root = tempfile.mkdtemp(prefix='hist-prune-')
    env = dict(os.environ)
    env['SOTTO_HISTORY_ROOT'] = root
    env.pop('SOTTO_HISTORY_RETENTION_H', None)
    if extra_env:
        env.update(extra_env)
    rc, out, _err = _node(['node', '-e', JS_PRUNE_PROBE, store_path, root], env)
    if rc != 0:
        return {'retention': None, 'oldKept': None, 'keepKept': None,
                'outsideKept': None, 'rc': rc}
    return _json_line(out)


def node_arms(store_path, ctx=None):
    """The Node twin judged on the SAME contract as the Python one.

    Three facts, each measured on the shipped file:
      1. the fifteen merge identities (`mergeDecision`);
      2. retention -- an APPEND triggers the prune, the default window is the
         shell's constant and `SOTTO_HISTORY_RETENTION_H` really shortens it;
      3. the token codec is ONE format: for every fixture the Python and Node
         arms must produce the same normalised value, the same token BYTES and
         the same decoded value.
    """
    if ctx is None:
        ctx = load_module(CONTEXT, 'history_context_parity')
    tmp = tempfile.mkdtemp(prefix='hist-node-')
    payload = {
        'merge': [{'last': last, 'body': body, 'nowS': now_s,
                   'start': start, 'audio': audio}
                  for (_n, last, body, now_s, start, audio, _w) in MERGE_CASES],
        'codec': [raw for (_n, raw) in CODEC_FIXTURE],
        'tokens': [token for (_n, token) in TOKEN_FIXTURE],
    }
    payload_path = os.path.join(tmp, 'payload.json')
    with io.open(payload_path, 'w', encoding='utf-8', newline='') as fh:
        json.dump(payload, fh)
    env = dict(os.environ)
    env['SOTTO_HISTORY_ROOT'] = tempfile.mkdtemp(prefix='hist-node-root-')
    rc, out, _err = _node(['node', '-e', JS_NODE_PROBE, store_path,
                           payload_path], env)
    if rc != 0:
        return [('g0-node', rc, 0)], {}
    data = _json_line(out)
    rows = []
    for case, got in zip(MERGE_CASES, data.get('actions') or []):
        rows.append((case[0], got, case[6]))
    for (name, raw), got in zip(CODEC_FIXTURE, data.get('codec') or []):
        py_token = ctx.encode(raw)
        want = (ctx.normalize(raw), py_token, ctx.decode(py_token))
        rows.append(('p-' + name,
                     (got.get('norm'), got.get('token'), got.get('decoded')),
                     want))
    # THE READER ITSELF, on a token that never went through either encoder: a
    # hand-edited `%zz`/`%2`/`%` must not erase a field one host keeps, and NEL
    # and U+FEFF must land on the same side on both hosts.
    for (name, token), got in zip(TOKEN_FIXTURE, data.get('rawDecoded') or []):
        rows.append(('q-' + name, got, ctx.decode(token)))
    default = _prune_probe(store_path)
    short = _prune_probe(store_path, {'SOTTO_HISTORY_RETENTION_H': '24'})
    rows.extend([
        ('g16-retencao-padrao', default.get('retention'), 4320),
        ('g17-dia-antigo-apagado', default.get('oldKept'), False),
        ('g18-dia-recente-fica', default.get('keepKept'), True),
        ('g19-pasta-fora-do-padrao-fica', default.get('outsideKept'), True),
        ('g20-env-le-o-valor', short.get('retention'), 24),
        ('g21-env-apaga-o-antigo', short.get('oldKept'), False),
        ('g22-env-mantem-o-recente', short.get('keepKept'), True),
    ])
    return rows, data


def ui_arms(shell_path=SHELL):
    """The panel's menu item reaches the shell (2026-11-09).

    A backend API with no control is a feature the owner cannot use: the
    requirement is "TXT export reached by the current UI". These arms read the
    three sites that must agree -- the markup that names the control, the
    bridge that exposes the message, and the page code that calls it.
    """
    def read(path):
        with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()
    html = read(os.path.join(ROOT, 'app', 'panel', 'panel.html'))
    js = read(os.path.join(ROOT, 'app', 'panel', 'panel.js'))
    shell_src = read(shell_path)
    head = html.split('id="history-export-txt"')[0]
    return [
        ('u1-markup-tem-o-botao', 'id="history-export-txt"' in html, True),
        ('u2-botao-dentro-do-menu', 'id="panel-menu"' in head[-4000:], True),
        ('u3-pagina-chama-exportFile', "historyApi.exportFile('txt'" in js, True),
        ('u4-pagina-revela-o-ficheiro', 'historyApi.reveal(path)' in js, True),
        ('u5-shell-registou-a-mensagem',
         "'history-export-file': ('host', '_history_export_file')" in shell_src,
         True),
        ('u6-ponte-expoe-exportFile',
         'exportFile: function (format, limit)' in shell_src, True),
        # THE SESSION IDENTITY IS WIRED, not only implemented (2026-11-09): the
        # bridge stamps the child process it read the line from, and the caption
        # path observes it on EVERY event (a partial proves the new clock).
        ('u7-consume-carimba-a-sessao',
         "meta['historySession'] = self.history_session(child)" in shell_src,
         True),
        ('u8-caption-observa-a-sessao',
         '_observe_ctx(self._history_ctx_session_of(meta))' in shell_src,
         True),
    ]


def judge(rows):
    bad = [r for r in rows if r[1] != r[2]]
    for name, got, want in rows:
        print(('ok  ' if got == want else 'RED ') + name
              + ('' if got == want else f'  got={got!r} want={want!r}'))
    return bad


def run_neg_arm():
    caught = 0
    total = 0
    with io.open(CONTEXT, 'r', encoding='utf-8', errors='replace') as fh:
        ctx_src = fh.read()
    with io.open(SHELL, 'r', encoding='utf-8', errors='replace') as fh:
        shell_src = fh.read()
    with io.open(STORE, 'r', encoding='utf-8', errors='replace') as fh:
        store_src = fh.read()
    with io.open(CODEC_JS, 'r', encoding='utf-8', errors='replace') as fh:
        codec_src = fh.read()

    mutants = []
    mutants.append(('n1-decoder-vazio',
                    ctx_src.replace(
                        "    return decode(match.group(1)) if match else {}",
                        "    return {}"),
                    'ctx'))
    mutants.append(('n2-shell-nao-grava-token',
                    shell_src.replace(
                        "        provenance = self._history_provenance(\n"
                        "            options, history_context.encode(_ctx))",
                        "        provenance = self._history_provenance(options)"),
                    'shell'))
    mutants.append(('n3-shell-nao-le-token',
                    shell_src.replace(
                        "                           'context': history_context.token_in(line)}",
                        "                           'context': {}}"),
                    'shell'))
    mutants.append(('n4-store-nao-le-token',
                    store_src.replace("          context: contextTokenIn(lines[j]),",
                                      "          context: {},"),
                    'store'))
    mutants.append(('n5-ponte-sem-a-mensagem',
                    shell_src.replace(
                        "            'history-export-file': ('host', '_history_export_file'),\n",
                        ""),
                    'shell'))
    mutants.append(('n6-export-file-nao-escreve',
                    shell_src.replace(
                        "        body = self.history_export(fmt, limit)\n"
                        "        if not body.get('entries'):",
                        "        body = {'entries': 0, 'format': 'txt', 'text': ''}\n"
                        "        if not body.get('entries'):"),
                    'shell'))
    # THE NODE TWIN'S TWO INDEPENDENT RULES (2026-11-09). The store is a WRITER
    # for the same files, so a host that keeps the old merge or forgets to prune
    # is a line that reads differently depending on which arm wrote it.
    mutants.append(('n7-node-sempre-appende',
                    store_src.replace("  if (!last) return 'append';",
                                      "  if (true) return 'append';"),
                    'store'))
    mutants.append(('n8-node-sem-prune-no-append',
                    store_src.replace("  prune();\n", ""),
                    'store'))
    # THE PYTHON TWIN'S TWO CORRECTIONS (2026-11-09), mutated on a COPY of the
    # codec: the old `_text` deleted control characters, and the old `encode`
    # erased a field that did not fit instead of trimming it.
    mutants.append(('n9-texto-apaga-controlo',
                    ctx_src.replace(
                        "    cleaned = ''.join(' ' if (ch < ' ' or ch == '\\x7f')"
                        " else ch for ch in value)",
                        "    cleaned = ''.join(ch for ch in value"
                        " if ch >= ' ' and ch != '\\x7f')"),
                    'ctx'))
    mutants.append(('n10-encode-apaga-o-campo',
                    ctx_src.replace(
                        "        while quoted and len(quoted) > room:\n"
                        "            value = value[:-1]\n"
                        "            quoted = quote(value, safe='')\n"
                        "        if quoted:\n"
                        "            parts.append(letter + quoted)\n"
                        "        break",
                        "        break"),
                    'ctx'))
    # THE NODE CODEC (`history-context-store.js`) IS ONE FORMAT WITH THE PYTHON
    # TWIN. `encodeURIComponent` leaves `!'()*` raw where Python's `quote`
    # escapes them, so dropping the hand fix is the measured divergence that
    # `p-pontuacao` exists to catch.
    mutants.append(('n11-node-codec-sem-pontuacao',
                    codec_src.replace(
                        "  return encodeURIComponent(String(value == null ? '' : value))\n"
                        "    .replace(/[!'()*]/g, (ch) => `%${ch.charCodeAt(0).toString(16).toUpperCase()}`);",
                        "  return encodeURIComponent(String(value == null ? '' : value));"),
                    'codec'))
    # THE SESSION BOUNDARY (2026-11-09): the new-session arm must die when the
    # caption path stops observing the session, and again when the observer
    # stops clearing the snapshot. Two mutations, because the wiring and the
    # rule are two separate ways to reintroduce the leak.
    mutants.append(('n15-caption-nao-observa-sessao',
                    shell_src.replace(
                        "        _observe_ctx = getattr(self, '_history_ctx_observe_session', None)\n"
                        "        if _observe_ctx is not None:\n"
                        "            _observe_ctx(self._history_ctx_session_of(meta))\n",
                        ""),
                    'shell'))
    mutants.append(('n16-sessao-nao-limpa-o-snapshot',
                    shell_src.replace(
                        "        if previous is not None and previous != session:\n"
                        "            ring = getattr(self, '_history_ctx_ring', None)\n"
                        "            if isinstance(ring, list):\n"
                        "                del ring[:]\n"
                        "            self._history_ctx_last = None\n"
                        "            self._history_ctx_last_start = None\n",
                        ""),
                    'shell'))
    # THE CODEC'S TWO READER EDGES (2026-11-09): strict percent decode erased a
    # field the Python twin keeps, and JS `\s` disagreed with `str.split()` on
    # NEL and U+FEFF. Reverting either must turn a `q-`/`p-` arm red.
    mutants.append(('n12-node-decode-estrito',
                    codec_src.replace(
                        "      value = percentDecode(value);",
                        "      value = decodeURIComponent(value);"),
                    'codec'))
    mutants.append(('n13-node-espaco-do-js',
                    codec_src.replace(
                        "    .replace(PY_SPACE_RUN, ' ')\n"
                        "    .replace(/^ +| +$/g, '');",
                        "    .replace(/\\s+/g, ' ')\n"
                        "    .replace(/^\\s+|\\s+$/g, '');"),
                    'codec'))
    mutants.append(('n14-node-bom-comido',
                    codec_src.replace(
                        "new TextDecoder('utf-8', { fatal: false, ignoreBOM: true })",
                        "new TextDecoder('utf-8', { fatal: false })"),
                    'codec'))

    for name, src, kind in mutants:
        total += 1
        original = {'ctx': ctx_src, 'shell': shell_src,
                    'codec': codec_src}.get(kind, store_src)
        if src == original:
            print(f'NEG-ARM IMPOSSIVEL {name}: o padrao nao esta no ficheiro')
            continue
        tmp = tempfile.mkdtemp(prefix='hist-neg-')
        if kind in ('store', 'codec'):
            # The store requires `./history-context-store`, so the PAIR has to
            # live in the temp dir: one member is the mutant, the other the real
            # file. Writing only the copy made every store mutant die with
            # MODULE_NOT_FOUND -- a LOAD-FAILED arm measures nothing.
            path = os.path.join(tmp, 'mut.js')
            codec_path = os.path.join(tmp, 'history-context-store.js')
            with io.open(path if kind == 'store' else codec_path,
                         'w', encoding='utf-8', newline='') as fh:
                fh.write(src)
            with io.open(codec_path if kind == 'store' else path,
                         'w', encoding='utf-8', newline='') as fh:
                fh.write(codec_src if kind == 'store' else store_src)
        else:
            path = os.path.join(tmp, 'mut.py')
            with io.open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(src)
        try:
            if kind == 'ctx':
                mod = load_module(path, 'history_context')
                bad = judge(codec_arms(mod))
            elif kind == 'shell':
                # The shell imports `history_context` by name; after the decoder
                # mutant was loaded under that name, put the REAL module back or
                # this arm would fail for the other mutant's reason.
                sys.modules.pop('history_context', None)
                load_module(CONTEXT, 'history_context')
                mod = load_module(path, 'sotto_webview_mut_ctx')
                rows, _logs, _tmp = shell_arms(mod)
                rows = list(rows) + list(ui_arms(path))
                bad = judge(rows)
            else:
                rows, _data = js_arms(path)
                node_rows, _ndata = node_arms(path)
                rows = list(rows) + list(node_rows)
                bad = judge(rows)
        except Exception as exc:                       # noqa: BLE001
            print(f'NEG-ARM LOAD-FAILED {name}: {exc!r}')
            continue
        if bad:
            caught += 1
            print(f'ok  {name} -> RED: ' + ','.join(b[0] for b in bad))
        else:
            print(f'NOT-CAUGHT {name}: nenhum arm vermelho')
    print('NEG-ARM %s mutants %d/%d' % ('PASS' if caught == total else 'FAIL',
                                        caught, total))
    return 1 if caught == total else 0


def main(argv):
    if '--neg-arm' in argv:
        return run_neg_arm()
    # `--shell PATH` judges a COPY of the shell. The new-session arm's BEFORE
    # proof is the pre-fix bytes, and the acceptance forbids reverting the real
    # file to obtain them.
    shell_path = SHELL
    if '--shell' in argv:
        try:
            shell_path = argv[argv.index('--shell') + 1]
        except IndexError:
            print('FATAL: --shell needs a path')
            return 2
    ctx = load_module(CONTEXT, 'history_context')
    shell = load_module(shell_path, 'sotto_webview_histctx')
    rows = list(codec_arms(ctx))
    shell_rows, logs, py_root = shell_arms(shell)
    rows.extend(shell_rows)
    js_rows, js_data = js_arms(STORE)
    rows.extend(js_rows)
    node_rows, _node_data = node_arms(STORE, ctx=ctx)
    rows.extend(node_rows)
    rows.extend(ui_arms(shell_path))
    # THE TOKEN IS ONE FORMAT, NOT TWO: a line written by Python is read by the
    # Node store and vice versa. A drift here would make the two hosts disagree
    # about the same file.
    js_seen = js_read(STORE, py_root)
    rows.append(('x1-node-le-python',
                 (js_seen[0] or {}).get('viewingTitle') if js_seen else None,
                 'main.py'))
    if js_data.get('root'):
        had = getattr(shell, 'HISTORY_ROOT', None)
        shell.HISTORY_ROOT = js_data['root']
        try:
            shim = shell.SottoShell.__new__(shell.SottoShell)
            py_seen = (shim.history_tail(10).get('entries') or [])
        finally:
            if had is not None:
                shell.HISTORY_ROOT = had
        rows.append(('x2-python-le-node',
                     (py_seen[0].get('context') or {}).get('viewingTitle')
                     if py_seen else None,
                     'main.py'))
    bad = judge(rows)
    print('HISTORY_CONTEXT_LOG ' + ' | '.join(logs))
    print('VERDICT: %s arms %d/%d' % ('FAIL' if bad else 'PASS',
                                      len(rows) - len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
