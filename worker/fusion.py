# NO-BUG: modulo NOVO de decisao de texto (fusao stream/refinado); nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
# -*- coding: utf-8 -*-
"""FUSION CORE -- a decisao entre a hipotese RAPIDA (stream) e a do FINISHER (refined).

O QUE E' ISTO, E O QUE NAO E'. Duas hipoteses do MESMO audio: a que ja' esta'
a correr (stream, o modelo rapido) e a que o finisher devolve depois (refined,
segunda passagem). Este modulo ALINHA as duas ao nivel da PALAVRA e devolve
operacoes de edicao ordenadas mais um veredicto de estabilidade por palavra --
nada mais: sem audio, sem modelo, sem I/O, sem gravacao. NAO ha' deteccao de
falantes aqui e nao se acrescenta: a ordem do dono de 2026-11-04 e' *"nao
queremos a implementacao de detectar falantes ou algo assim. so' o core"*.

A TABELA DE DECISAO (a do plano, escrita como codigo em `decide_span`):

  modelos concordam                -> confirma a do stream (`confirmed`)
  discordam                        -> fica provisoria (`provisional`)
  o refined corrige o stream       -> actualiza ESE span (`replace [i:j] X`)
  a palavra JA' ESTA' NO ECRA      -> nao muda (estabilidade)
  a frase terminou                 -> revisao offline (`offline-review`)
  o finisher discorda dos DOIS     -> o audio decide (`needs-audio`, sem vencedor)

"Os dois" sao o STREAM e o que ja' esta' no ecra. Com tres candidatos
distintos, escolher um seria adivinhar -- e o modulo nao adivinha; marca o span
e deixa a decisao a quem tiver o audio.

A REGRA DA ESTABILIDADE, nomeada e com a razao: ver `REVEALED_REPLACE_RULE`.
Uma palavra revelada so' e' substituida quando o finisher DISCORDA do stream
nela E ambos os modelos nunca a confirmaram; quando os DOIS modelos concordam
contra o token que esta' no ecra, dois modelos independentes ganham ao ecra.

O GANCHO DE CONTEXTO (`vocab`): uma lista de termos que pode RE-ETIQUETAR um
span em que os modelos discordam como `needs-context` EM VEZ DE escolher. Nunca
inventa uma palavra que o audio nao sustentou: so' etiqueta candidatos que um
dos modelos produziu de facto.

    f = Fusion(vocab=['Sotto', 'nemotron'])
    r = f.feed('o sotto ta rodando', 'o chotto ta rodando')
    f.reveal()                      # o que ja' foi para o ecra
    r = f.feed('o sotto ta rodando', 'o sotto ta rodando')
    for op in r['ops']: ...          # {'op': 'replace'|'append', ...}

`feed` e' a API progressiva: chama-se outra vez com as hipoteses que existirem
e o resultado e' aplicavel por cima do que o store ja' tem (os `ops` sao um
diff contra o committed, logo um segundo `feed` identico devolve `ops == []`).
"""

from __future__ import annotations

import difflib

__all__ = [
    'Fusion', 'align_pair', 'tokenize', 'normalize', 'decide_span',
    'REVEALED_REPLACE_RULE', 'DECISIONS', 'STABILITY_STATES',
    'NEEDS_AUDIO', 'NEEDS_CONTEXT',
]

# -- A REGRA DA ESTABILIDADE, com o motivo escrito ao lado ------------------
REVEALED_REPLACE_RULE = (
    'REVEALED-REPLACE-ONLY-IF-FINISHER-DISAGREES-AND-NEVER-BOTH-CONFIRMED'
)
REVEALED_REPLACE_REASON = (
    "Uma palavra ja' revelada ao ecra so' e' substituida quando o finisher "
    "discorda do stream NELA e ambos os modelos nunca a confirmaram. Motivo: o "
    "dono le' a frase a meio e o texto a mudar debaixo dos olhos e' pior que "
    "uma palavra errada que a proxima passagem corrige; estabilidade vale mais "
    "que correccao tardia. A excepcao e' o caso de DOIS modelos: quando stream "
    "e refined concordam contra o token que esta' no ecra, ha' duas fontes "
    "independentes contra uma, e o ecra perde."
)

DECISIONS = ('agree', 'stream-only', 'refined-only', 'substitute')
STABILITY_STATES = ('confirmed', 'provisional', 'corrected',
                    'needs-audio', 'needs-context', 'offline-review')

NEEDS_AUDIO = 'needs-audio'
NEEDS_CONTEXT = 'needs-context'
OFFLINE_REVIEW = 'offline-review'

# Peso do alinhamento: uma substituicao (-1) custa MENOS que dois buracos
# (-2), ou seja, o DP prefere emparelhar uma palavra torta a apagar e inserir.
_MATCH, _MISS, _GAP = 2, -1, -1

# Pontuacao de borda que nao conta para a comparacao (o acento CONTA: `nao` e
# `nao` com til sao palavras diferentes e o pt-BR do dono depende disso).
_EDGE = '.,;:!?…"\'()[]{}«»—-–'


def tokenize(text):
    """Palavras na ordem, sem normalizar NADA (o ecra ve' o token cru)."""
    return [w for w in str(text or '').split() if w]


def normalize(word):
    """Forma de COMPARACAO: minuscula e sem pontuacao de borda. Acento fica."""
    return str(word or '').strip().strip(_EDGE).lower()


def _vocab_hit(word, vocab):
    nw = normalize(word)
    for term in vocab or ():
        if nw and normalize(term) == nw:
            return term
    return None


def align_pair(stream, refined):
    """Alinhamento de Needleman-Wunsch, deterministico.

    Devolve colunas `(kind, stream_index|None, refined_index|None)` na ordem do
    audio, com `kind` em `match`, `sub`, `stream-only`, `refined-only`.
    Empate resolve-se SEMPRE pelo mesmo lado (diagonal, depois idioma do
    stream), para que duas chamadas iguais deem o mesmo resultado -- sem isso a
    idempotencia do `feed` nao existe.
    """
    n, m = len(stream), len(refined)
    score = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] + _GAP
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] + _GAP
    for i in range(1, n + 1):
        si = normalize(stream[i - 1])
        for j in range(1, m + 1):
            if si == normalize(refined[j - 1]):
                diag = score[i - 1][j - 1] + _MATCH
            else:
                diag = score[i - 1][j - 1] + _MISS
            up = score[i - 1][j] + _GAP
            left = score[i][j - 1] + _GAP
            score[i][j] = max(diag, up, left)

    cols = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            if normalize(stream[i - 1]) == normalize(refined[j - 1]):
                diag = score[i - 1][j - 1] + _MATCH
                same = True
            else:
                diag = score[i - 1][j - 1] + _MISS
                same = False
            if score[i][j] == diag:
                cols.append(('match' if same else 'sub', i - 1, j - 1))
                i -= 1
                j -= 1
                continue
        if i > 0 and score[i][j] == score[i - 1][j] + _GAP:
            cols.append(('stream-only', i - 1, None))
            i -= 1
            continue
        cols.append(('refined-only', None, j - 1))
        j -= 1
    cols.reverse()
    return cols


def _rec(word, decision, stability, both_models=False, note=''):
    return {'word': word, 'decision': decision, 'stability': stability,
            'both_models': bool(both_models), 'note': note}


def decide_span(kind, stream_word, refined_word, shown=None, vocab=()):
    """A TABELA DE DECISAO, por coluna de alinhamento.

    `shown` e' o registo que o store ja' tem nessa posicao (None se a palavra e'
    nova) -- `both_models` = os dois modelos ja' produziram o mesmo token nela
    (a "confirmacao pelos dois" da regra) e `revealed` = ja' foi para o ecra.
    Devolve o registo alvo: `{word, decision, stability, both_models, note}`.
    Nunca levanta e nunca inventa um token.
    """
    shown_word = shown['word'] if shown else None
    shown_ok = bool(shown and shown.get('both_models'))
    shown_up = bool(shown and shown.get('revealed'))

    if kind == 'match':
        # Modelos concordam.
        if shown_word is not None and normalize(shown_word) != normalize(stream_word):
            # ... e ambos discordam do que esta' no ecra: dois contra um.
            return _rec(stream_word, 'substitute', 'corrected', both_models=True,
                        note='both-models-against-shown')
        return _rec(stream_word, 'agree', 'confirmed', both_models=True)

    if kind == 'refined-only':
        # O finisher ouviu uma palavra que o stream nao tem. A MERGA na linha
        # (insercao no meio de texto ja' no ecra) e' feita pelo `Fusion.feed`,
        # que conhece o que esta' pintado; aqui, uma coluna so' do finisher e'
        # uma palavra provisoria de que so' um modelo deu prova.
        return _rec(refined_word, 'refined-only', 'provisional',
                    note='finisher-only-word')

    if kind == 'stream-only':
        # O finisher nao tem a palavra do stream (talvez a tenha omitido).
        if shown_word is None:
            return _rec(stream_word, 'stream-only', 'provisional')
        if normalize(shown_word) == normalize(stream_word):
            return _rec(shown_word, 'stream-only',
                        (shown or {}).get('stability', 'provisional'))
        if shown_ok and shown_up:
            return _rec(shown_word, 'stream-only', 'confirmed',
                        note='stability-lock')
        return _rec(stream_word, 'stream-only', 'provisional',
                    note='stream-revision')

    # kind == 'sub': os modelos DISCORDAM.
    if (_vocab_hit(stream_word, vocab) or _vocab_hit(refined_word, vocab)):
        # Hipotese de vocabulario: nao se escolhe, etiqueta-se para o contexto.
        base = shown_word if shown_word is not None else stream_word
        return _rec(base, 'substitute', NEEDS_CONTEXT,
                    note='vocab-span-needs-context')

    if shown_word is None:
        # Nada no ecra ainda: o finisher corrige a hipotese rapida.
        return _rec(refined_word, 'substitute', 'corrected',
                    note='finisher-corrects')

    if normalize(shown_word) == normalize(refined_word):
        return _rec(shown_word, 'substitute', 'corrected',
                    note='already-corrected')
    if normalize(shown_word) == normalize(stream_word):
        if shown_ok and shown_up:
            # ESTABILIDADE: ja' confirmada pelos dois e ja' no ecra -> segura.
            return _rec(shown_word, 'substitute', 'confirmed',
                        note='stability-lock')
        # Revelada mas so' provisoria: a regra permite a correccao.
        return _rec(refined_word, 'substitute', 'corrected',
                    note='finisher-corrects-revealed' if shown_up
                    else 'finisher-corrects')
    # O ecra, o stream e o refined: TRES candidatos distintos. Nao se escolhe.
    return _rec(shown_word, 'substitute', NEEDS_AUDIO,
                note='three-way-disagreement')


def _diff_ops(committed, target):
    """Operacoes que levam o committed ao target, por `SequenceMatcher`.

    Um diff de prefixo/sufixo juntaria 5 edicoes dispersas numa unica
    `replace [7:199]`, que e' verdade sobre o texto e mentira sobre a decisao:
    quem aplica no store precisa do SPAN de cada correccao (A10). `delete` nunca
    produz op -- texto que ja' esta' no ecra nao se apaga.
    """
    old = [r['word'] for r in committed]
    new = [r['word'] for r in target]
    n = len(old)
    ops = []
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        text = ' '.join(new[j1:j2])
        if tag == 'delete':
            continue
        if tag == 'insert':
            if i1 == n and i2 == n:
                ops.append({'op': 'append', 'text': text})
            else:
                ops.append({'op': 'replace', 'span': [i1, i1], 'text': text})
            continue
        ops.append({'op': 'replace', 'span': [i1, i2], 'text': text})
    return ops


def _position(rec):
    """Onde o registo esta' na HIPOTESE (stream), nao na lista do texto."""
    if rec.get('src') is not None:
        return rec['src']
    if rec.get('boundary') is not None:
        return rec['boundary']
    return 1 << 30


def _revealed_tail(shown_list, boundaries):
    """`boundary -> True` quando algo DALI PARA A FRENTE ja' esta' no ecra."""
    return dict((b, any(rec.get('revealed') and _position(rec) >= b
                        for rec in shown_list))
                for b in boundaries)


def _changed_indexes(ops, n_old):
    """Indices do TARGET tocados por uma op (o que o store vai reescrever)."""
    changed = set()
    for op in ops:
        count = len(tokenize(op.get('text', '')))
        if op['op'] == 'append':
            changed.update(range(n_old, n_old + count))
        else:
            start = op['span'][0]
            changed.update(range(start, start + count))
    return changed


def _verdict(words):
    states = [w['stability'] for w in words]
    for state in (NEEDS_AUDIO, NEEDS_CONTEXT, OFFLINE_REVIEW, 'provisional',
                  'corrected'):
        if state in states:
            return state
    return 'confirmed'


class Fusion:
    """Estado minimo de uma faixa: o committed (o que esta' no ecra) e o vocab.

    `Fusion(vocab=[...])` liga o gancho de contexto; `feed` aceita `vocab=`
    para a chamada pontual. `reveal(upto=None)` marca como REVELADO o que ja'
    foi pintado -- e' isso que liga a regra da estabilidade.
    """

    def __init__(self, vocab=None):
        self.vocab = [t for t in (vocab or ()) if str(t).strip()]
        self._committed = []
        self.history = []

    # -- estado ---------------------------------------------------------
    def text(self):
        return ' '.join(r['word'] for r in self._committed)

    def words(self):
        return [dict(r) for r in self._committed]

    def reveal(self, upto=None):
        """Marca `upto` palavras (por omissao todas as conhecidas) como no ecra."""
        stop = len(self._committed) if upto is None else max(0, int(upto))
        for rec in self._committed[:stop]:
            rec['revealed'] = True
        return min(stop, len(self._committed))

    # -- a API progressiva ----------------------------------------------
    def feed(self, stream_text, refined_text, sentence_end=False, vocab=None):
        """Alinha as duas hipoteses e devolve `ops` + `stability` por palavra.

        Cada palavra do stream guarda o `src` (o indice no stream) para que a
        posicao no TEXTO nao seja confundida com a posicao na HIPOTESE: e' isso
        que deixa uma insercao do finisher entrar sem deslocar as decisoes
        seguintes (A13). As palavras que so' o finisher trouxe guardam o
        `boundary` (o proximo indice do stream) e sao re-montadas no mesmo sitio
        no `feed` seguinte -- sem isso a idempotencia partia-se na insercao.
        """
        terms = list(self.vocab if vocab is None else vocab)
        stream = tokenize(stream_text)
        refined = tokenize(refined_text)
        shown_list = self._committed
        columns = align_pair(stream, refined)

        by_src = {}
        insertions = {}
        for rec in shown_list:
            if rec.get('src') is None:
                insertions.setdefault(rec.get('boundary'), []).append(rec)
            else:
                by_src[rec['src']] = rec

        # Palavras SO' do finisher, agrupadas pelo limite onde entram (o proximo
        # indice do stream, ou o fim da hipotese).
        wanted = {}
        pending = []
        for kind, si, ri in columns:
            if kind == 'refined-only':
                pending.append(refined[ri])
                continue
            if pending:
                wanted[si] = list(pending)
                pending = []
        if pending:
            wanted[len(stream)] = list(pending)

        # O que ja' esta' no ecra manda: uma insercao so' entra se NADA dela foi
        # revelado, e uma insercao que ja' esta' la' nao se duplica.
        chosen = {}
        held = []
        boundaries = sorted(set(wanted) | set(insertions))
        tail_revealed = _revealed_tail(shown_list, boundaries)
        for boundary in boundaries:
            new = wanted.get(boundary, [])
            have = insertions.get(boundary, [])
            if [r['word'] for r in have] == new:
                chosen[boundary] = have
                continue
            # Inserir aqui EMPURRA para a frente tudo o que ja' esta' pintado
            # dali para a direita; se essa cauda esta' no ecra, a insercao e'
            # segurada (estabilidade vale mais que a palavra que falta).
            if have and any(r.get('revealed') for r in have):
                chosen[boundary] = have
                held.extend(new)
                continue
            if tail_revealed.get(boundary):
                chosen[boundary] = have
                held.extend(new)
                continue
            chosen[boundary] = [dict(_rec(w, 'refined-only', 'provisional',
                                          note='finisher-inserts'),
                                     src=None, boundary=boundary, revealed=False)
                                for w in new]

        target = []
        consumed = set()
        for kind, si, ri in columns:
            if si is None:
                continue                       # a insercao entra pelo `chosen`
            consumed.add(si)
            target.extend(chosen.pop(si, []))
            shown = by_src.get(si)
            rec = decide_span(kind, stream[si],
                              refined[ri] if ri is not None else '',
                              shown, terms)
            rec['src'] = si
            rec['revealed'] = bool(shown and shown.get('revealed'))
            target.append(rec)
        for boundary in sorted(chosen):
            target.extend(chosen[boundary])

        # O stream pode ter encolhido; o que ja' esta' no ecra fica.
        for rec in shown_list:
            if rec.get('src') is not None and rec['src'] not in consumed:
                keep = dict(rec)
                keep['decision'] = rec.get('decision', 'agree')
                keep['note'] = 'kept-beyond-hypothesis'
                target.append(keep)

        if sentence_end:
            # Frase terminada: o que nao fechou vai para revisao offline.
            for rec in target:
                if rec['stability'] in ('provisional', NEEDS_AUDIO,
                                        NEEDS_CONTEXT):
                    rec['stability'] = OFFLINE_REVIEW

        ops = _diff_ops(shown_list, target)
        changed = _changed_indexes(ops, len(shown_list))

        out_words = []
        for idx, rec in enumerate(target):
            out_words.append({
                'index': idx,
                'word': rec['word'],
                'decision': rec['decision'],
                'stability': rec['stability'],
                'both_models': rec['both_models'],
                'revealed': bool(rec.get('revealed')),
                'changed': idx in changed,
                'note': rec['note'],
            })

        result = {
            'ops': ops,
            'words': out_words,
            'text': ' '.join(r['word'] for r in target),
            'stability': _verdict(out_words),
            'review': bool(sentence_end),
            'needs_audio': [w['index'] for w in out_words
                            if w['stability'] == NEEDS_AUDIO],
            'needs_context': [w['index'] for w in out_words
                              if w['stability'] == NEEDS_CONTEXT],
            'held': held,
            'rule': REVEALED_REPLACE_RULE,
            'vocab': list(terms),
        }
        self._committed = [dict(rec) for rec in target]
        self.history.append({'ops': ops, 'stability': result['stability'],
                             'review': result['review']})
        return result
