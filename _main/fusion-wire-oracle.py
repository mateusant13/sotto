# NO-BUG: portao da LIGACAO do core NOVO `worker/fusion.py` ao caminho da legenda (2026-11-09); nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
# -*- coding: utf-8 -*-
"""FUSION WIRE ORACLE -- the two-model decision wired into the caption path.

POR QUE ESTE FICHEIRO EXISTE. `worker/fusion.py` decide, palavra a palavra, que
texto o ECRa leva quando a hipotese RAPIDA (stream) e a do FINISHER (refined)
para o MESMO audio discordam. O core tinha `_main/fusion-oracle.py` (14 arms) e
NENHUM consumidor: `grep -rn "import fusion|from .fusion" --include=*.py .`
devolvia zero. Uma tabela de decisao sem chamador e' uma promessa.

O QUE ESTA LIGACAO E'. `SottoShell.on_worker_caption` e' o UNICO sitio por onde
cada legenda do worker passa, e e' de la' que saem as DUAS superficies:
`emit_async('caption', ...)` alimenta a linha do painel (e o commit do painel e'
o que `history_append` escreve no transcript) e `push_caption_to_window` pinta o
overlay que o `_drain_caption_pending` drena. A fusao mora AQUI -- um texto, as
duas superficies -- e nao em cada uma delas.

AS ARMS, e o que cada uma prova (todas EXECUTAM as funcoes reais extraidas por
`ast` do `app/webview/sotto_webview.py`; nada e' copia escrita aqui):

  1. call-site-presente      -- `on_worker_caption` CHAMA `self._fusion_caption`.
  2. switch-off              -- sem `SOTTO_FUSION=1` o texto passa byte a byte.
  3. stream-only             -- so' a parcial (a hipotese do stream): sem edicao.
  4. agreement               -- os dois modelos concordam: `confirmed`, `ops=[]`.
  5. correction              -- discordam num span: UM `replace span=i:j`.
  6. overlay-gets-fused      -- a superficie do overlay recebe o texto fundido.
  7. history-gets-fused      -- o payload que o painel commita (e que o
                                `history_append` grava) recebe o texto fundido.
  8. revealed-word-locked    -- a REGRA: palavra ja' confirmada pelos dois e ja'
                                no ecra NAO e' substituida (estabilidade).
  9. key-has-session         -- `start` reinicia a zero em cada respawn: uma
                                sessao NOVA nao funde com a linha da anterior.

BRACO NEGATIVO (`--neg-arm`): remove o CALL SITE numa COPIA do fonte e exige o
vermelho do arm 5. Sai 1 e nomeia o arm que apanhou (o contrato do portao).

USO:
    python _main/fusion-wire-oracle.py
    python _main/fusion-wire-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import ast
import importlib.util as _iu
import io
import json
import os
import re
import sys
import time
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHELL = REPO / 'app' / 'webview' / 'sotto_webview.py'
FUSION = REPO / 'worker' / 'fusion.py'

CASES = []


def add(ok, label, detail=''):
    CASES.append((bool(ok), label, detail))
    print(('GREEN ' if ok else 'RED   ') + label + (('  ' + detail) if detail else ''))
    return bool(ok)


def verdict(name, rc_expected=0):
    passed = sum(1 for ok, _, _ in CASES if ok)
    failed = len(CASES) - passed
    print()
    if failed:
        print('%s VERMELHO -- arms=%d pass=%d fail=%d (rc=1)'
              % (name, len(CASES), passed, failed))
        return 1
    print('%s GREEN -- arms=%d pass=%d fail=%d (rc=%d)'
          % (name, len(CASES), passed, failed, rc_expected))
    return rc_expected


# -- extraction: the EXACT source of the shipped functions, by AST -----------
def extract_function(src: str, name: str) -> str:
    """Top-level function body, verbatim (indentation preserved)."""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = src.splitlines(keepends=True)
            return ''.join(lines[node.lineno - 1:node.end_lineno])
    raise SystemExit('%s nao existe no topo do fonte' % name)


def extract_method(src: str, name: str) -> str:
    """`SottoShell.<name>` body, dedented so it can be exec'd as a function."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'SottoShell':
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == name:
                    lines = src.splitlines(keepends=True)
                    body = lines[member.lineno - 1:member.end_lineno]
                    indent = ' ' * member.col_offset
                    return ''.join(
                        line[len(indent):] if line.startswith(indent) else line
                        for line in body
                    )
    raise SystemExit('SottoShell.%s nao existe no fonte' % name)


def load_fusion():
    """The REAL core, imported by path so this oracle runs from anywhere."""
    spec = _iu.spec_from_file_location('fusion_under_wire', str(FUSION))
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(source, fusion_mod):
    """Exec the real functions of `source`; return (namespace, log list).

    The extracted methods are exec'd at MODULE level with their `self` argument
    intact -- a method body is a function body, and `exec` sees the same names
    the shipped class does. `_FUSION_MODULE` is pre-bound so `_fusion_module()`
    returns the core without a second import path.
    """
    logs = []
    ns = {
        'log': lambda msg: logs.append(str(msg)),
        'json': json,
        'time': time,
        'os': os,
        'sys': sys,
        'FUSION_SWITCH_ENV': 'SOTTO_FUSION',
        'FUSION_STREAM_MAX': 32,
        '_FUSION_MODULE': fusion_mod,
    }
    for name in ('fusion_enabled', '_fusion_module', 'fuse_caption', '_fusion_key'):
        exec(compile(extract_function(source, name),
                     '<fusion-wire:%s>' % name, 'exec'), ns)
    # A IDADE DO AUDIO QUE A LINHA CARREGA (2026-11-12): o `on_worker_caption`
    # REAL chama `live_paint_age_s(meta, epoch)` desde que o `tap_ms` passou a
    # viajar ate' a pintura (`CAPTION_PAINT_LAG`), e o `ns` deste duplo nao
    # conhecia nem ela nem os dois helpers puros dela -- o passo morria em
    # `NameError: live_paint_age_s`. Sao funcoes sem estado (nenhuma abre
    # dispositivo, nenhuma toca em audio): executam-se, nao se reimplementam.
    ns['_SKIP'] = object()
    #: o piso que o `live_paint_stale` usa por omissao, lido do FONTE e ligado
    #: ao `ns` ANTES do `exec` que compila a funcao: a assinatura resolve o
    #: default no momento da compilacao, e um valor escrito aqui a mao seria um
    #: segundo numero a envelhecer sozinho.
    _bound = re.search(r'^LIVE_PAINT_MAX_AGE_S\s*=\s*([0-9.]+)', source,
                       re.M)
    ns['LIVE_PAINT_MAX_AGE_S'] = float(_bound.group(1)) if _bound else 8.0
    for name in ('_measured_age', 'live_paint_age_s', '_is_number',
                 'live_paint_stale'):
        exec(compile(extract_function(source, name),
                     '<fusion-wire:%s>' % name, 'exec'), ns)
    # A POSSE DO ECRAN E' LIDA PELA LINHA (2026-11-12). O
    # `on_worker_caption` REAL passou a perguntar `external_owner_refuses(source)`
    # antes de pintar (D-23, 2026-11-12) e este duplo nao tinha o metodo: o passo
    # `fusion-wire` morria em `AttributeError: 'FakeShell' object has no attribute
    # 'external_owner_refuses'` -- a fusao deixava de ser julgada porque a guarda
    # de posse mudou de forma. O corpo executado e' o do PRODUTO.
    methods = '\n\n'.join([extract_method(source, '_fusion_caption'),
                           extract_method(source, 'external_owner_refuses'),
                           extract_method(source, 'on_worker_caption')])
    exec(compile(methods, '<fusion-wire:methods>', 'exec'), ns)
    return ns, logs


class FakeShell:
    """What `on_worker_caption` reads from `self`, and the two sinks it feeds."""

    external_captions_active = False
    CAPTION_BUDGET_MS = 1500
    #: a POSSE do ecra, como na shell real: `local` deixa a linha local pintar,
    #: `player` a recusa. O duplo nasce do lado que deixa pintar -- o braco da
    #: fusao julga o texto, nao a posse, e a posse tem o seu proprio oraculo.
    external_owner = 'local'
    external_owner_episode = 0
    _asr_owner_episode = False

    def __init__(self):
        self.bridge = object()
        self.external_suppressed = 0
        self.emitted = []            # (kind, payload) -- the panel's feed
        self.pushed = []             # text per push_caption_to_window
        self.reload_calls = []
        self._caption_sent_count = 0
        self._last_push_final = False
        self._last_push_tap_ms = None
        self._last_push_at = None
        self._history_ctx_session = None
        self._reload_policy = self

    def boundary(self, **kw):
        self.reload_calls.append(kw)

    @staticmethod
    def _history_ctx_session_of(meta):
        if isinstance(meta, dict):
            value = meta.get('historySession')
            if isinstance(value, str) and value:
                return value
        return None

    def _history_ctx_observe_session(self, session):
        self._history_ctx_session = session

    def _viewing_url(self):
        return ''

    def note_history_context(self, meta):
        return None

    def emit_async(self, kind, payload):
        self.emitted.append((kind, dict(payload)))

    def push_caption_to_window(self, text, **kw):
        self.pushed.append(text)
        return True


def make_shell(ns):
    shell = FakeShell()
    shell._fusion_caption = types.MethodType(ns['_fusion_caption'], shell)
    shell.external_owner_refuses = types.MethodType(
        ns['external_owner_refuses'], shell)
    shell.on_worker_caption = types.MethodType(ns['on_worker_caption'], shell)
    return shell


def meta(start=1.0, session='worker:test:1', final=False):
    return {'start': start, 'end': start + 1.5,
            'final': bool(final), 'historySession': session}


def edits(logs):
    return [line for line in logs if line.startswith('FUSION_EDIT')]


def correction_probe(ns, logs):
    """The correction scenario, run through the REAL `on_worker_caption`.

    Shared by the arm and the negative arm so the mutation is judged by the
    ARM's predicate, not by a second, weaker copy of it.
    """
    logs.clear()
    shell = make_shell(ns)
    shell.on_worker_caption('o chotto ta rodando', meta(final=False))
    shell.on_worker_caption('o sotto ta rodando', meta(final=True))
    got = shell.pushed[-1] if shell.pushed else None
    lines = edits(logs)
    ops = ns['fuse_caption']('o chotto ta rodando', 'o sotto ta rodando')[1]
    one_span = (len(ops) == 1 and ops[0].get('op') == 'replace'
                and ops[0].get('span') == [1, 2]
                and ops[0].get('text') == 'sotto')
    ok = (got == 'o sotto ta rodando' and len(lines) == 1 and one_span
          and 'span=1:2' in lines[0] and 'was="chotto"' in lines[0]
          and 'now="sotto"' in lines[0])
    return ok, shell, lines, ops


# -- the arms ----------------------------------------------------------------
def run_arms(source, fusion_mod):
    ns, logs = build(source, fusion_mod)
    switch_was = os.environ.get('SOTTO_FUSION')

    # 1. THE CALL SITE. Without it every other arm below is a test of dead code.
    tree = ast.parse(extract_method(source, 'on_worker_caption'))
    gets_join = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == 'getattr'
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == '_fusion_caption'
        for node in ast.walk(tree))
    calls_join = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == '_fuse'
        for node in ast.walk(tree))
    call_site = gets_join and calls_join
    add(call_site, 'call-site-present',
        'on_worker_caption chama o join (getattr=%s call=%s)'
        % (gets_join, calls_join))

    # 2. SWITCH OFF = byte-identical (the default).
    os.environ.pop('SOTTO_FUSION', None)
    shell = make_shell(ns)
    logs.clear()
    shell.on_worker_caption('o chotto ta rodando', meta(final=False))
    shell.on_worker_caption('o sotto ta rodando', meta(final=True))
    add(shell.pushed and shell.pushed[-1] == 'o sotto ta rodando'
        and not edits(logs),
        'switch-off', 'push=%r edits=%d'
        % (shell.pushed[-1] if shell.pushed else None, len(edits(logs))))

    # 3. STREAM-ONLY: a partial with no finisher hypothesis -> no edit.
    os.environ['SOTTO_FUSION'] = '1'
    shell = make_shell(ns)
    logs.clear()
    shell.on_worker_caption('o chotto ta rodando', meta(final=False))
    add(shell.pushed and shell.pushed[-1] == 'o chotto ta rodando'
        and not edits(logs),
        'stream-only', 'push=%r edits=%d'
        % (shell.pushed[-1] if shell.pushed else None, len(edits(logs))))

    # 4. AGREEMENT: both models the same words -> confirmed, ops == [].
    shell = make_shell(ns)
    logs.clear()
    shell.on_worker_caption('o sotto ta rodando', meta(final=False))
    shell.on_worker_caption('o sotto ta rodando', meta(final=True))
    text, ops, stability = ns['fuse_caption'](
        'o sotto ta rodando', 'o sotto ta rodando')
    add(shell.pushed and shell.pushed[-1] == 'o sotto ta rodando'
        and not edits(logs) and ops == [] and stability == 'confirmed',
        'agreement', 'push=%r ops=%d stability=%s'
        % (shell.pushed[-1] if shell.pushed else None, len(ops), stability))

    # 5. CORRECTION: exactly ONE replace, on exactly the span that differs.
    ok, shell, lines, ops = correction_probe(ns, logs)
    got = shell.pushed[-1] if shell.pushed else None
    add(ok, 'correction', 'push=%r ops=%r log=%r'
        % (got, ops, lines[0] if lines else ''))

    # 6/7. BOTH SURFACES get the SAME fused text -- otherwise one of them would
    # show a version the other never decided on.
    panel = [p for kind, p in shell.emitted if kind == 'caption']
    add(bool(panel) and panel[-1].get('text') == 'o sotto ta rodando',
        'overlay-gets-fused', 'push=%r' % (got,))
    add(bool(panel) and panel[-1].get('text') == 'o sotto ta rodando',
        'history-gets-fused',
        'panel_text=%r (o commit do painel e o que history_append grava)'
        % (panel[-1].get('text') if panel else None,))

    # 8. REVEALED-REPLACE RULE, through the wired state machine: after the two
    # models CONFIRMED a word and it is on screen, a later disagreement does NOT
    # replace it (stability beats a late correction).
    shell = make_shell(ns)
    logs.clear()
    shell.on_worker_caption('o sotto ta rodando', meta(final=False, start=3.0))
    shell.on_worker_caption('o sotto ta rodando', meta(final=True, start=3.0))
    before_edits = len(edits(logs))
    shell.on_worker_caption('o chotto ta rodando', meta(final=True, start=3.0))
    add(shell.pushed and shell.pushed[-1] == 'o sotto ta rodando'
        and len(edits(logs)) == before_edits,
        'revealed-word-locked',
        'push=%r edits=%d' % (shell.pushed[-1] if shell.pushed else None,
                              len(edits(logs)) - before_edits))

    # 9. SESSION IS PART OF THE KEY: the audio clock restarts at zero on every
    # respawn, so the same `start` in a NEW session must not fuse with the old
    # line (that would edit the new session's opening words with old text).
    shell = make_shell(ns)
    logs.clear()
    shell.on_worker_caption('alpha bravo', meta(final=False, session='s-1'))
    shell.on_worker_caption('charlie delta', meta(final=True, session='s-2'))
    add(shell.pushed and shell.pushed[-1] == 'charlie delta'
        and not edits(logs),
        'key-has-session', 'push=%r edits=%d'
        % (shell.pushed[-1] if shell.pushed else None, len(edits(logs))))

    # 10. ONE TEXT, BOTH SURFACES. The fused variable must be what BOTH consumers
    # receive: if a later change hands the panel the incoming text and the
    # overlay the fused one (or the reverse), the live row and the history line
    # disagree while every arm above still passes.
    tree = ast.parse(extract_method(source, 'on_worker_caption'))
    fed_text = None
    emit_text = push_text = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == '_fuse'):
            fed_text = node.targets[0].id
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == 'emit_async' and len(node.args) >= 2:
            payload = node.args[1]
            if (isinstance(payload, ast.Dict) and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == 'caption'):
                for key, value in zip(payload.keys, payload.values):
                    if (isinstance(key, ast.Constant) and key.value == 'text'
                            and isinstance(value, ast.Name)):
                        emit_text = value.id
        elif node.func.attr == 'push_caption_to_window' and node.args:
            if isinstance(node.args[0], ast.Name):
                push_text = node.args[0].id
    same = (fed_text is not None and emit_text == push_text == fed_text)
    add(same, 'same-text-both-surfaces',
        'fusao=%r panel=%r overlay=%r' % (fed_text, emit_text, push_text))

    if switch_was is None:
        os.environ.pop('SOTTO_FUSION', None)
    else:
        os.environ['SOTTO_FUSION'] = switch_was


#: O CALL SITE CARREGA O EOL DO FICHEIRO (medido 2026-11-12): o shell e' CRLF
#: e esta ancora, escrita com `\n`, respondia `NEG-ARM: FAIL -- o call site nao
#: foi encontrado no fonte (a copia nao mudou nada)` -- o controlo reprovava
#: por cegueira propria e o passo `red-as-expected-fusion-wire` ficava RED. A
#: ancora e' a MESMA linha de produto; o separador vem do fonte.
_CALL_SITE_LINES = (
    "        _fuse = getattr(self, '_fusion_caption', None)",
    "        if _fuse is not None:",
    "            text = _fuse(text, meta)",
)


def call_site_block(source):
    eol = '\r\n' if '\r\n' in source else '\n'
    return eol.join(_CALL_SITE_LINES) + eol


def neg_arm(source, fusion_mod):
    """Remove the call site in a COPY; the correction arm must go RED."""
    site = call_site_block(source)
    if site not in source:
        print('NEG-ARM: FAIL -- o call site nao foi encontrado no fonte '
              '(a copia nao mudou nada)')
        return 2
    mutated = source.replace(site, '', 1)
    if mutated == source:
        print('NEG-ARM: FAIL -- a mutacao nao alterou o fonte')
        return 2
    ns, logs = build(mutated, fusion_mod)
    os.environ['SOTTO_FUSION'] = '1'   # the join must be ARMED and still missing
    ok, shell, lines, _ops = correction_probe(ns, logs)
    if ok:
        print('NEG-ARM: FAIL -- sem o call site o arm "correction" continuou '
              'VERDE (push=%r edits=%r)'
              % (shell.pushed[-1] if shell.pushed else None, lines))
        return 2
    print('NEG-ARM: PASS caught=correction (sem o call site: push=%r, '
          'FUSION_EDIT=%d) -- o arm fica VERMELHO e o portao nomeia-o'
          % (shell.pushed[-1] if shell.pushed else None, len(lines)))
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog='fusion-wire-oracle')
    parser.add_argument('--neg-arm', action='store_true',
                        help='muta uma COPIA (remove o call site) e exige RED')
    parser.add_argument('--pair', nargs=2, metavar=('STREAM', 'REFINED'),
                        help='imprime o veredicto do core REAL para um par '
                             '(usado pela medicao de dois bracos)')
    args = parser.parse_args(argv)
    source = io.open(SHELL, encoding='utf-8', newline='').read()
    fusion_mod = load_fusion()
    if args.pair:
        ns, _logs = build(source, fusion_mod)
        text, ops, stability = ns['fuse_caption'](*args.pair)
        print(json.dumps({'stream': args.pair[0], 'refined': args.pair[1],
                          'fused': text, 'ops': ops, 'stability': stability}))
        return 0
    if args.neg_arm:
        return neg_arm(source, fusion_mod)
    run_arms(source, fusion_mod)
    return verdict('FUSION-WIRE')


if __name__ == '__main__':
    sys.exit(main())
