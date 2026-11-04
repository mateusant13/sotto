# NO-BUG: portao do modulo NOVO `worker/fusion.py` (decisao de texto stream/refinado, pedida pelo dono a 2026-11-04: *"implementa agora. testa, aprova, troca toda nossa stack por essa"*); nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
# -*- coding: utf-8 -*-
"""FUSION ORACLE -- as arms da tabela de decisao do FUSION CORE.

POR QUE ESTE FICHEIRO EXISTE. O `worker/fusion.py` decide QUE TEXTO vai para o
ecra quando o modelo rapido (stream) e o finisher (refined) discordam do mesmo
audio. Uma tabela de decisao escrita em prosa e' uma promessa; estas arms
EXECUTAM as funcoes reais do modulo e exigem a decisao:

  A1  identicas          -- duas hipoteses iguais: tudo `confirmed`, zero ops.
  A2  substituicao-fim   -- a troca e' a ULTIMA palavra.
  A3  substituicao-meio  -- a troca e' no meio: `replace [i:j]`, vizinhos intactos.
  A4  revelado           -- (a) confirmada pelos dois e ja' no ecra: NAO muda;
                            (b) revelada mas so' provisoria: o finisher corrige;
                            (c) os DOIS modelos contra o ecra: o ecra perde.
  A5  tres-candidatos    -- ecra, stream e refined todos diferentes: `needs-audio`,
                            nenhum vencedor escolhido, zero ops.
  A6  vocabulario        -- termo do `vocab` num span em que discordam:
                            `needs-context`, e nenhuma palavra inventada.
  A7  duplicadas         -- a classe `nao nao`: a repeticao sobrevive ao alinhamento.
  A8  vazio/curto        -- hipotese vazia, so' um lado, nada explode.
  A9  unicode            -- acentos pt-BR passam intactos; `nao` != `nao`+til.
  A10 duzentas           -- 200 palavras, 5 edicoes dispersas: ordem e idempotencia.
  A11 gap                -- palavra so' no stream nao desloca o resto (o alinhamento
                            e' o que segura isto; diff por indice erra).
  A12 fim-de-frase       -- `sentence_end`: o que nao fechou vai a revisao offline.
  A13 insercao           -- palavra SO' do finisher no meio da linha entra sem
                            deslocar as decisoes seguintes, e o `feed` seguinte
                            nao a duplica (idempotencia).
  A14 insercao-segurada  -- essa mesma insercao, com o texto ja' no ecra, e'
                            SEGURADA: nao se empurra para a frente o que o dono
                            esta' a ler; as correccoes atras dele continuam.

`--neg-arm` muta COPIES do modulo em quatro sitios (estabilidade; o refinado a
ganhar ao ecra; escolher um vencedor quando os dois estao errados; alinhamento
substituido por diff de indice) e exige que a arm DESIGNADA de cada mutante caia.
Convencao da casa (2026-11-03): o `--neg-arm` devolve rc=1 quando apanha todos --
e' esse o resultado VERMELHO que um `:expectred` exige -- e imprime `NEG-ARM: PASS`.
"""

from __future__ import annotations

import argparse
import importlib.util as _iu
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODULE = os.path.join(REPO, 'worker', 'fusion.py')


def _load(path, name='fusion_under_test'):
    spec = _iu.spec_from_file_location(name, path)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    with io.open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def _fresh(mod, *args, **kwargs):
    return mod.Fusion(*args, **kwargs)


def _words(result):
    return [(w['index'], w['word'], w['decision'], w['stability'])
            for w in result['words']]


def arms(module_path=MODULE):
    mod = _load(module_path)
    out = []

    # A1 -- hipoteses identicas
    f = _fresh(mod)
    r1 = f.feed('hoje o dia ta lindo', 'hoje o dia ta lindo')
    r2 = f.feed('hoje o dia ta lindo', 'hoje o dia ta lindo')
    a1 = (r1['text'] == 'hoje o dia ta lindo'
          and [w['decision'] for w in r1['words']] == ['agree'] * 5
          and all(w['stability'] == 'confirmed' for w in r1['words'])
          and r1['ops'] == [{'op': 'append', 'text': 'hoje o dia ta lindo'}]
          and r2['ops'] == []
          and r2['stability'] == 'confirmed')
    out.append(('identicas', a1,
                'texto=%r ops2=%d' % (r1['text'], len(r2['ops']))))

    # A2 -- substituicao na ULTIMA palavra
    f = _fresh(mod)
    f.feed('nao sei se ele vem', '')          # o stream primeiro
    r = f.feed('nao sei se ele vem', 'nao sei se ele vai')
    last = r['words'][-1]
    a2 = (r['text'] == 'nao sei se ele vai'
          and last['word'] == 'vai' and last['decision'] == 'substitute'
          and last['stability'] == 'corrected'
          and [w['word'] for w in r['words'][:-1]] ==
          ['nao', 'sei', 'se', 'ele'])
    out.append(('substituicao-fim', a2, 'texto=%r' % r['text']))

    # A3 -- substituicao no MEIO: replace do span, vizinhos intactos
    f = _fresh(mod)
    f.feed('a gente vai no mercado amanha', '')
    r = f.feed('a gente vai no mercado amanha',
               'a gente vai ao mercado amanha')
    ops = r['ops']
    a3 = (r['text'] == 'a gente vai ao mercado amanha'
          and len(ops) == 1 and ops[0]['op'] == 'replace'
          and ops[0]['span'] == [3, 4] and ops[0]['text'] == 'ao'
          and r['words'][3]['decision'] == 'substitute'
          and [w['word'] for w in r['words'] if w['index'] != 3] ==
          ['a', 'gente', 'vai', 'mercado', 'amanha'])
    out.append(('substituicao-meio', a3,
                'ops=%r' % (ops,)))

    # A4 -- palavra ja' REVELADA
    # (a) confirmada pelos DOIS e ja' no ecra -> NAO muda.
    f = _fresh(mod)
    f.feed('eu vi a casa', 'eu vi a casa')
    f.reveal()
    r = f.feed('eu vi a casa', 'eu vi a caza')
    word = r['words'][3]
    a4a = (r['text'] == 'eu vi a casa' and r['ops'] == []
           and word['word'] == 'casa' and word['note'] == 'stability-lock'
           and word['revealed'] is True)
    # (b) revelada mas so' provisoria (nunca confirmada pelos dois) -> corrige.
    f = _fresh(mod)
    f.feed('eu vi a caza amanha', 'eu vi a amanha')
    f.reveal()
    r = f.feed('eu vi a caza amanha', 'eu vi a casa amanha')
    word = r['words'][3]
    a4b = (r['text'] == 'eu vi a casa amanha'
           and r['ops'] == [{'op': 'replace', 'span': [3, 4], 'text': 'casa'}]
           and word['word'] == 'casa'
           and word['note'] == 'finisher-corrects-revealed'
           and word['revealed'] is True)
    # (c) os DOIS modelos contra o token do ecra -> o ecra perde.
    f = _fresh(mod)
    f.feed('eu vi a casa', 'eu vi a casa')
    f.reveal()
    r = f.feed('eu vi a caza', 'eu vi a caza')
    word = r['words'][3]
    a4c = (r['text'] == 'eu vi a caza'
           and r['ops'] == [{'op': 'replace', 'span': [3, 4], 'text': 'caza'}]
           and word['both_models'] is True
           and word['note'] == 'both-models-against-shown')
    a4 = a4a and a4b and a4c
    out.append(('revelado', a4,
                'a=%s b=%s c=%s' % (a4a, a4b, a4c)))

    # A5 -- tres candidatos distintos: o audio decide, nao o modulo
    f = _fresh(mod)
    f.feed('eu vi a casa', 'eu vi a casa')
    f.reveal()
    r = f.feed('eu vi a caza', 'eu vi a caca')
    word = r['words'][3]
    a5 = (r['ops'] == [] and r['text'] == 'eu vi a casa'
          and word['stability'] == 'needs-audio'
          and word['note'] == 'three-way-disagreement'
          and r['needs_audio'] == [3]
          and r['stability'] == 'needs-audio'
          and r['rule'] == mod.REVEALED_REPLACE_RULE)
    out.append(('tres-candidatos', a5, 'stability=%r' % r['stability']))

    # A6 -- gancho de vocabulario: etiqueta, nunca inventa
    f = _fresh(mod, vocab=['Sotto'])
    r = f.feed('o sotto ta rodando', 'o chotto ta rodando')
    a6a = (r['stability'] == 'needs-context'
           and r['needs_context'] == [1]
           and 'sotto' in r['text']
           and [w['word'] for w in r['words']][1] == 'sotto')
    # Um termo que NENHUM modelo produziu nunca aparece.
    f2 = _fresh(mod, vocab=['nemotron'])
    r2 = f2.feed('o chato ta rodando', 'o chato ta rodando')
    a6b = ('nemotron' not in r2['text']
           and r2['stability'] == 'confirmed')
    a6 = a6a and a6b
    out.append(('vocabulario', a6, 'context=%r score=%s'
                % (r['needs_context'], a6b)))

    # A7 -- duplicadas: `nao nao` sobrevive ao alinhamento
    f = _fresh(mod)
    r = f.feed('nao nao vou', 'nao nao vou')
    a7a = (r['text'] == 'nao nao vou' and len(r['words']) == 3
           and [w['word'] for w in r['words']] == ['nao', 'nao', 'vou'])
    f = _fresh(mod)
    f.feed('nao nao vou', 'nao nao vou')
    r = f.feed('nao nao vou', 'nao vou')     # o finisher omitiu uma repeticao
    a7b = (r['text'] == 'nao nao vou' and len(r['words']) == 3
           and [w['word'] for w in r['words']] == ['nao', 'nao', 'vou'])
    a7 = a7a and a7b
    out.append(('duplicadas', a7, 'texto=%r' % r['text']))

    # A8 -- vazio / curto
    f = _fresh(mod)
    r = f.feed('', '')
    a8a = (r['ops'] == [] and r['words'] == [] and r['text'] == '')
    f = _fresh(mod)
    r = f.feed('oi', '')
    a8b = (r['text'] == 'oi' and r['words'][0]['stability']
           == 'provisional' and r['ops'] == [{'op': 'append', 'text': 'oi'}])
    r = f.feed('', '')                       # o stream cala-se: nada e' apagado
    a8c = r['ops'] == [] and r['text'] == 'oi'
    f = _fresh(mod)
    r = f.feed('', 'tudo bem')
    a8d = (r['text'] == 'tudo bem'
           and [w['decision'] for w in r['words']] == ['refined-only'] * 2)
    a8 = a8a and a8b and a8c and a8d
    out.append(('vazio-curto', a8, 'a=%s b=%s c=%s d=%s'
                % (a8a, a8b, a8c, a8d)))

    # A9 -- unicode pt-BR: acentos intactos, e o acento CONTA
    f = _fresh(mod)
    r = f.feed('a reuniao comeca as tres', 'a reunião começa às três')
    a9a = (r['text'] == 'a reunião começa às três'
           and r['stability'] == 'corrected')
    f = _fresh(mod)
    r = f.feed('ele nao veio', 'ele não veio')
    a9b = (r['text'] == 'ele não veio'
           and r['words'][1]['decision'] == 'substitute')
    f = _fresh(mod)
    r = f.feed('coração de mãe', 'coração de mãe')
    a9c = (r['text'] == 'coração de mãe' and r['stability'] == 'confirmed')
    a9 = a9a and a9b and a9c
    out.append(('unicode', a9, 'texto=%r' % r['text']))

    # A10 -- 200 palavras com 5 edicoes dispersas: ordem e idempotencia
    base = ('o audio chegou limpo e o painel abriu em seguida a gente '
            'seguiu com a frase anterior e o motor nao perdeu o fio da '
            'conversa porque o buffer guarda o contexto a esquerda e o '
            'chunk seguinte continua a fala sem costura ').split()
    while len(base) < 200:
        base.extend(['palavra%d' % k for k in range(len(base), 200)])
    base = base[:200]
    edits = {7: 'audio', 43: 'painel', 99: 'contexto', 150: 'chunk',
             199: 'fim'}
    refined = list(base)
    for idx, victim in edits.items():
        stream_word = 'errado%d' % idx
        base[idx] = stream_word
        refined[idx] = victim
    f = _fresh(mod)
    f.feed(' '.join(base), '')                 # o stream sozinho primeiro
    r = f.feed(' '.join(base), ' '.join(refined))
    spans = [op['span'] for op in r['ops'] if op['op'] == 'replace']
    a10a = (len(r['words']) == 200 and len(spans) == 5
            and spans == sorted(spans)
            and [op['text'] for op in r['ops']] ==
            [edits[i] for i in sorted(edits)])
    for idx, victim in edits.items():
        a10a = a10a and r['words'][idx]['word'] == victim
    r2 = f.feed(' '.join(base), ' '.join(refined))
    a10b = (r2['ops'] == [] and r2['text'] == r['text'])
    a10 = a10a and a10b
    out.append(('duzentas', a10,
                'ops=%d spans_ordenados=%s idem=%s'
                % (len(r['ops']), spans == sorted(spans), a10b)))

    # A11 -- gap no meio: o resto nao desloca (o alinhamento segura isto)
    f = _fresh(mod)
    r = f.feed('eu vi ele ontem', 'eu vi ontem')
    a11 = (r['text'] == 'eu vi ele ontem'
           and [w['decision'] for w in r['words']] ==
           ['agree', 'agree', 'stream-only', 'agree']
           and r['words'][2]['stability'] == 'provisional'
           and r['words'][3]['word'] == 'ontem')
    out.append(('gap', a11, 'decisoes=%r'
                % [w['decision'] for w in r['words']]))

    # A12 -- frase terminada: o que nao fechou vai para revisao offline
    f = _fresh(mod)
    r = f.feed('eu vi ele ontem', 'eu vi ontem', sentence_end=True)
    a12 = (r['review'] is True and r['words'][2]['stability']
           == 'offline-review' and r['stability'] == 'offline-review')
    out.append(('fim-de-frase', a12,
                'stability=%r review=%s' % (r['stability'], r['review'])))

    # A13 / A14 -- insercao do finisher no meio da linha (o caso `rio` que o
    # nemotron derruba: a frase e' a do conjunto partilhado de 2026-11-04,
    # `_main/fixtures/stack-compare/reference.json`, com as duas hipoteses de
    # uma engine qualquer).
    ref = ('radio anunciou que a ponte sobre o rio vai ser interditada na '
           'proxima segunda-feira os moradores precisam de um caminho '
           'alternativo para chegar ao trabalho')
    hyp = ('radio anunciou que a ponte sobre vai ser interditada na proxima '
           'segunda-feira os moradores precisam de um caminho alternativo pra '
           'chegar ao trabalho')
    f = _fresh(mod)
    f.feed(hyp, '')
    r = f.feed(hyp, ref)
    a13 = (r['text'] == ref
           and {'op': 'replace', 'span': [6, 6], 'text': 'o rio'} in r['ops']
           and r['words'][6]['word'] == 'o'
           and r['words'][7]['word'] == 'rio'
           and r['words'][8]['word'] == 'vai'
           and r['words'][8]['decision'] == 'agree'
           and f.feed(hyp, ref)['ops'] == [])
    out.append(('insercao', a13,
                'ops=%r idem=%s' % (r['ops'], f.feed(hyp, ref)['ops'] == [])))

    f = _fresh(mod)
    f.feed(hyp, '')
    f.reveal()
    r = f.feed(hyp, ref)
    a14 = (r['ops'] == [{'op': 'replace', 'span': [19, 20], 'text': 'para'}]
           and 'o rio' not in r['text']
           and r['held'] == ['o', 'rio'])
    out.append(('insercao-segurada', a14,
                'ops=%r held=%r' % (r['ops'], r['held'])))

    return out


# -- mutacoes: cada uma numa COPIA do modulo -------------------------------
_INDEX_HELPER = '''

def _INDEX_COLUMNS(stream, refined):
    """Mutante: alinhamento trocado por diff de INDICE."""
    n = min(len(stream), len(refined))
    cols = []
    for k in range(n):
        same = normalize(stream[k]) == normalize(refined[k])
        cols.append(('match' if same else 'sub', k, k))
    for k in range(n, len(stream)):
        cols.append(('stream-only', k, None))
    for k in range(n, len(refined)):
        cols.append(('refined-only', None, k))
    return cols
'''


def _arm_map(path):
    """Mapa arm->ok de uma COPIA; um mutante que nem corre nao passa arm nenhuma."""
    try:
        return dict((n, ok) for n, ok, _ in arms(path))
    except Exception as exc:  # noqa: BLE001 -- o mutante nao executou
        return {'_error': repr(exc)}


def neg_arm(module_path=MODULE):
    """Quatro mutacoes em copias; cada uma tem de derrubar a SUA arm."""
    tmp = tempfile.mkdtemp(prefix='fusion-neg-')
    try:
        src = _read(module_path)
        results = []

        # M1 -- estabilidade removida: uma palavra confirmada pelos dois e ja'
        # no ecra passa a aceitar a correccao tardia do finisher.
        mut = os.path.join(tmp, 'sem_estabilidade.py')
        with io.open(mut, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(
                "        if shown_ok and shown_up:\n"
                "            # ESTABILIDADE: ja' confirmada pelos dois e ja' no ecra -> segura.\n"
                "            return _rec(shown_word, 'substitute', 'confirmed',\n"
                "                        note='stability-lock')",
                "        if False:\n"
                "            return _rec(shown_word, 'substitute', 'confirmed',\n"
                "                        note='stability-lock')", 1))
        got = _arm_map(mut)
        results.append(('estabilidade-removida', not got.get('revelado', False)))

        # M2 -- o refinado ganha ao ecra mesmo discordando dos dois.
        mut = os.path.join(tmp, 'refinado_ganha.py')
        with io.open(mut, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(
                "    return _rec(shown_word, 'substitute', NEEDS_AUDIO,\n"
                "                note='three-way-disagreement')",
                "    return _rec(refined_word, 'substitute', 'corrected',\n"
                "                note='three-way-disagreement')", 1))
        got = _arm_map(mut)
        results.append(('refinado-ganha-ao-ecra',
                        not got.get('tres-candidatos', True)))

        # M3 -- escolhe um vencedor quando os dois estao errados (span de vocab).
        mut = os.path.join(tmp, 'escolhe_vencedor.py')
        with io.open(mut, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(
                "        return _rec(base, 'substitute', NEEDS_CONTEXT,\n"
                "                    note='vocab-span-needs-context')",
                "        return _rec(refined_word, 'substitute', 'corrected',\n"
                "                    note='vocab-span-needs-context')", 1))
        got = _arm_map(mut)
        results.append(('escolhe-vencedor', not got.get('vocabulario', True)))

        # M4 -- sem alinhamento: diff por indice (o gap desloca tudo).
        mut = os.path.join(tmp, 'sem_alinhamento.py')
        body = src.replace(
            "        columns = align_pair(stream, refined)",
            "        columns = _INDEX_COLUMNS(stream, refined)", 1)
        with io.open(mut, 'w', encoding='utf-8') as fh:
            fh.write(body + _INDEX_HELPER)
        got = _arm_map(mut)
        results.append(('sem-alinhamento', not got.get('gap', True)))

        return results
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if args.neg_arm:
        results = neg_arm()
        bad = 0
        for name, caught in results:
            print('NEG-ARM %-24s %s'
                  % (name, 'CAUGHT' if caught else 'NOT-CAUGHT'))
            bad += 0 if caught else 1
        print('NEG-ARM VERDICT: %s (%d/%d)'
              % ('PASS' if not bad else 'FAIL',
                 len(results) - bad, len(results)))
        print('NEG-ARM: %s' % ('PASS' if not bad else 'FAIL'))
        # Convencao da casa: apanhar todos os mutantes E' o resultado
        # VERMELHO que um `:expectred` exige (rc=1); um mutante que escapa
        # devolve rc=0 e o passo fica vermelho de verdade.
        return 1 if not bad else 0
    bad = 0
    rows = arms()
    for name, ok, note in rows:
        print('%-22s %s  %s' % (name, 'PASS' if ok else 'FAIL', note))
        bad += 0 if ok else 1
    print('VERDICT: %s (%d/%d)'
          % ('PASS' if not bad else 'FAIL', len(rows) - bad, len(rows)))
    return 0 if not bad else 1


if __name__ == '__main__':
    raise SystemExit(main())
