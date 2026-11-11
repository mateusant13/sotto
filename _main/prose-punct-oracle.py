#!/usr/bin/env python3
# NO-BUG: mede o FECHO de linha por prosa+pausa (2026-11-10); nao ha id no ledger para esta classe
# -*- coding: utf-8 -*-
"""Sotto -- a linha fechada ganha a marca que o motor nao deu? (2026-11-10)

── O DEFEITO QUE ISTO JULGA ────────────────────────────────────────────────
Dono, 2026-11-09: *"historicos desde as 15h de hoje: melhorar a qualidade da
transcricao a custo barato"*. MEDIDO no arquivo dele
(`history/2026-11-09/17.md`, 63 linhas): **37** `reason=stable`, **ZERO** com
marca terminal; 43 das 63 nao fecham. A causa e' a guarda de lingua do
restaurador (`worker/punctuation_model.py:supported_lang` -> so' `en*`) e o
modelo multilingue foi RECUSADO por medicao (2,4 GB + torch, `I:` a 4,8%).

── A CURA SOB JULGAMENTO ───────────────────────────────────────────────────
`app/webview/prose_punct.close_line(text, gap_s)` -- puro: `.` quando a linha
nao fecha, a ultima palavra nao e' conector, e a pausa ate' a linha SEGUINTE
alcanca o piso de frase que esta casa ja' mediu (`SENTENCE_MIN_MS = 600 ms`,
`worker/punctuation_prosody.py`). `?`/`!` NUNCA sao inventados (nenhuma fixture
tem pergunta; a direcao do F0 mediu 3 subidas / 2 descidas).

── AS ARMS (o codigo REAL, nada re-implementado) ───────────────────────────
  A  as armas da funcao pura: marca terminal, conector na cauda, pausa curta,
     pausa ausente, cauda a abrir parenteses, aspas a fechar, vazio.
  B  o piso e' o MESMO numero dos dois ficheiros (600 ms lidos por `ast` de
     `worker/punctuation_prosody.py`), senao o fecho e o modulo de prosodia
     passariam a discordar sobre o que e' uma pausa de frase.
  C  o stream REAL (`SottoShell._history_entries`, extraido por `ast`) sobre um
     root TEMPORARIO: a linha mais nova de um arquivo fica em IDENTIDADE (ainda
     nao ha' pausa medida), a linha anterior com pausa >= 600 ms ganha `.`, a que
     tem conector na cauda NAO ganha, e o texto lido do disco nao e' tocado.
  D  o arquivo em DISCO permanece o registo CRU: o fecho e' de leitura.

`--neg-arm` repoe, numa COPIA em memoria, a versao que fecha SEM olhar a pausa e
exige o vermelho da arm que protege a pausa. Convencao da casa: rc **1** e' o
valor esperado de um `red-as-expected-*`.
"""

import ast
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
APP = os.path.join(REPO, 'app', 'webview')
SHELL_PY = os.path.join(APP, 'sotto_webview.py')
PROSODY_PY = os.path.join(REPO, 'worker', 'punctuation_prosody.py')
PUNCT_PY = os.path.join(APP, 'prose_punct.py')

if APP not in sys.path:
    sys.path.insert(0, APP)

import prose_punct  # noqa: E402 -- depois do sys.path, de proposito
import text_normalize  # noqa: E402 -- o helper que o stream embarca le' hoje


class Arms:
    def __init__(self):
        self.rows = []

    def __call__(self, name, got, want):
        ok = got == want
        self.rows.append((name, ok, got, want))
        print('  %s %s\n      got=%r want=%r'
              % ('PASS' if ok else 'FAIL', name, got, want))

    def verdict(self):
        bad = [r for r in self.rows if not r[1]]
        print('\n%d arm(s), %d failure(s)' % (len(self.rows), len(bad)))
        return 0 if not bad else 1


def _load_module(path):
    with io.open(path, encoding='utf-8') as handle:
        src = handle.read()
    tree = ast.parse(src, filename=path)
    return src, tree


def _funcao(path, nome):
    src, tree = _load_module(path)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == nome:
            seg = ast.get_source_segment(src, node)
            ns = {'re': __import__('re')}
            exec(compile(seg, path, 'exec'), ns)  # noqa: S102 -- codigo do repo
            return ns[nome]
    raise SystemExit('ORACLE-BROKEN: %s nao tem %s' % (path, nome))


def _metodo(path, classe, nome):
    src, tree = _load_module(path)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == classe:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == nome:
                    seg = ast.get_source_segment(src, sub)
                    ns = {}
                    exec(compile(seg, path, 'exec'), ns)  # noqa: S102
                    return ns[nome]
    raise SystemExit('ORACLE-BROKEN: %s.%s.%s nao existe' % (path, classe, nome))


def arm_floor(arm):
    """B: o piso do fecho e' o piso medido da prosodia."""
    ns = {}
    src = io.open(PROSODY_PY, encoding='utf-8').read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == 'SENTENCE_MIN_MS':
                    ns['v'] = ast.literal_eval(node.value)
    want = ns.get('v')
    arm('B o piso de frase e o mesmo dos dois ficheiros',
        (want is not None and abs(prose_punct.SENTENCE_MIN_S * 1000.0 - float(want)) < 0.5),
        True)


def _escreve(root, day, hour, rows):
    folder = os.path.join(root, day)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, '%s.md' % hour)
    with io.open(path, 'w', encoding='utf-8', newline='') as handle:
        for stamp, text in rows:
            handle.write('- [%s] %s <!-- route=final producer=redux -->\n'
                         % (stamp, text))
    return path


def arm_stream(arm):
    """C: o stream REAL sobre um root temporario."""
    root = tempfile.mkdtemp(prefix='sotto-prose-')
    try:
        _escreve(root, '2026-11-10', '17', [
            ('17:00:00', 'primeira linha sem marca'),      # pausa 2 s -> ganha
            ('17:00:02', 'segunda linha com o'),           # conector -> identidade
            ('17:00:03', 'terceira linha curta'),          # pausa 1 s -> ganha
            ('17:00:04', 'ultima linha ainda a falar'),    # sem vizinho -> identidade
        ])
        metodo = _metodo(SHELL_PY, 'SottoShell', '_history_entries')
        clock = _funcao(SHELL_PY, '_history_clock_s')
        ns = {
            're': __import__('re'),
            'HISTORY_LINE_RE': __import__('re').compile(r'^-\s+\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$'),
            'HISTORY_TAIL_RE': __import__('re').compile(r'\s*<!--.*?-->\s*$'),
            'prose_punct': prose_punct,
            # A CORRIDA E O PREENCHIMENTO ENTRARAM NA LEITURA (2026-11-11):
            # `_history_entries` passou a chamar `text_normalize.collapse_runs`
            # e `text_normalize.is_filler_line` antes do `prose_punct`, para a
            # linha que e' so' `Mmm` nao chegar ao feed (121 das 1302 linhas do
            # arquivo do dono). O namespace deste braco e' FECHADO -- so' tem o
            # que esta' escrito aqui --, logo o helper que o modulo embarca
            # passou a ser uma dependencia da extracao: sem ele o stream morre
            # em `NameError` e o braco C/D mede a excepcao. E' o modulo REAL,
            # importado de `app/webview`, e nao uma copia.
            'text_normalize': text_normalize,
            '_history_clock_s': clock,
            'history_context': _STUB_CTX,
        }
        exec(compile(_src_of(SHELL_PY, '_history_entries'), SHELL_PY, 'exec'), ns)  # noqa: S102
        fn = ns['_history_entries']
        fake = type('Shell', (), {})()
        fake._history_files = lambda: [('2026-11-10', '17', os.path.join(root, '2026-11-10', '17.md'))]
        fake._history_read = lambda p: io.open(p, encoding='utf-8').read().splitlines()
        entries = list(fn(fake))
        del metodo
        by_time = {}
        for e in entries:
            by_time.setdefault(e['time'], []).append(e['text'])
        arm('C1 a linha com 2 s de pausa ganha o ponto',
            by_time['17:00:00'], ['primeira linha sem marca.'])
        arm('C2 a cauda num conector NAO ganha marca',
            by_time['17:00:02'], ['segunda linha com o'])
        arm('C3 a linha com 1 s ganha o ponto',
            by_time['17:00:03'], ['terceira linha curta.'])
        arm('C4 a MAIS NOVA fica em identidade (sem pausa medida)',
            by_time['17:00:04'], ['ultima linha ainda a falar'])
        # D: o disco nao foi tocado
        raw = io.open(os.path.join(root, '2026-11-10', '17.md'), encoding='utf-8').read()
        arm('D o arquivo em disco continua o registo CRU',
            'primeira linha sem marca <!--' in raw, True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


class _StubCtx:
    @staticmethod
    def token_in(_line):
        return {}


_STUB_CTX = _StubCtx()


def _src_of(path, nome):
    src, tree = _load_module(path)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'SottoShell':
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == nome:
                    return ast.get_source_segment(src, sub)
    raise SystemExit('ORACLE-BROKEN: %s.%s nao existe' % (path, nome))


def run(neg_arm=False):
    arm = Arms()
    print('== A: a funcao pura ==')
    if neg_arm:
        # MUTACAO: o fecho deixa de olhar a pausa (a versao que fecha sempre).
        original = prose_punct.close_line
        prose_punct.close_line = lambda text, gap_s: (
            text if prose_punct._TERMINAL.search(str(text or '')) else
            prose_punct._TRAILING_JUNK.sub('', str(text or '')) + '.')
    else:
        original = None
    arm('A1 marca terminal existente e identidade',
        prose_punct.close_line('Ja acabou.', 2.0), 'Ja acabou.')
    arm('A2 virgula na cauda e substituida pelo ponto',
        prose_punct.close_line('uma frase sem fim,', 2.0), 'uma frase sem fim.')
    arm('A3 pausa curta (300 ms) NAO inventa marca',
        prose_punct.close_line('uma frase sem fim', 0.3), 'uma frase sem fim')
    arm('A4 pausa ausente NAO inventa marca',
        prose_punct.close_line('uma frase sem fim', None), 'uma frase sem fim')
    arm('A5 conector na cauda NAO ganha marca',
        prose_punct.close_line('eu falei com o', 2.0), 'eu falei com o')
    arm('A6 conector ingles na cauda NAO ganha marca',
        prose_punct.close_line('I was talking to the', 2.0), 'I was talking to the')
    arm('A7 parenteses aberto no fim e identidade',
        prose_punct.close_line('ele disse (ontem', 2.0), 'ele disse (ontem')
    arm('A8 aspas a fechar: o ponto entra ENTRE a fala',
        prose_punct.close_line('ele disse "vamos', 2.0), 'ele disse "vamos.')
    arm('A9 vazio e identidade', prose_punct.close_line('', 2.0), '')
    arm('A10 pausa exatamente no piso (600 ms) ja fecha',
        prose_punct.close_line('no limite', 0.6), 'no limite.')
    arm_floor(arm)
    print('\n== C/D: o stream real sobre um root temporario ==')
    arm_stream(arm)
    if original is not None:
        prose_punct.close_line = original
    rc = arm.verdict()
    if neg_arm:
        # O NEGATIVO devolve 1 quando APANHA: a mutacao tem de derrubar A3/A4.
        caught = [r for r in arm.rows if not r[1]]
        names = [r[0] for r in caught]
        esperado = any(n.startswith('A3') or n.startswith('A4') for n in names)
        print('NEG-ARM: %s -- %d arm(s) vermelhas: %s'
              % ('PASS' if esperado else 'FAIL', len(caught), ', '.join(names) or '-'))
        return 1 if esperado else 0
    return rc


if __name__ == '__main__':
    sys.exit(run(neg_arm='--neg-arm' in sys.argv))
