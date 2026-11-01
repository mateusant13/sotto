"""A PALAVRA QUE AINDA NAO ESTA PROVADA NAO VAI PARA O ECRA.

O DONO, 2026-10-30, verbatim:
    *"faz sotto identificar palavras que ainda nao estao completas e nao dar
    display. nunca vai dar display por exemplo em 'so' sem esperar virar 'sou'.
    em qualquer lingua"*

E, no mesmo dia, quando a primeira versao desta regra ficou a espera:
    *"'CAUS' QUANDO O FALANTE FALA 'CAUSE LIKE'. E AÍ DA DISPLAY NO 'CAUSE LIKE'
    SOMENTE APOS A PROXIMA PALAVRA DELE, QUE LEVOU UNS SEGUNDOS PRA ELE FALAR."*

O PROBLEMA, em duas metades.
  1. O `LineFormer` publica um PARCIAL de cada vez que a linha cresce. A ultima
     palavra desse parcial nao esta provada: o modelo pode te-la cortado a meio
     (`CAUS` | `E`), e o parcial ja foi para o ecra.
  2. A PARTIR DE 2026-10-30 a cura ingenua -- "esconde sempre a ultima palavra
     separada por espaco" -- passou a esconder a palavra que ja estava PROVADA,
     porque a prova chega com o token seguinte e a cura so olhava para o
     fragmento seguinte (outro chunk, outra palavra, segundos depois).

A REGRA, e ela e' do TOKENIZADOR e nao da lingua. O SentencePiece marca o inicio
de cada palavra com `▁`; a juncao dos fragmentos ja usa essa marca
(`join_fragments`). Logo:

  * a CAUDA ABERTA e' o texto que comeca no ULTIMO inicio de palavra da linha --
    tudo o que vem depois do ultimo separador da ULTIMA palavra conhecida;
  * se o ultimo fragmento CONTINUA a palavra anterior (`continues=True`), a
    cauda aberta comeca no fragmento ANTERIOR (a palavra atravessou a fronteira
    do chunk);
  * o que fica a esquerda dessa cauda esta PROVADO, porque um inicio de palavra
    veio depois dele -- e vai para o ecra IMEDIATAMENTE, sem esperar mais nada.

Assim `CAUSE LIKE` aparece no instante em que o `▁` de `LIKE` e' decodificado, e
`CAUS` nunca aparece sozinho. A espera maxima passa a ser um token, nao uma
palavra falada.

A PALAVRA FECHADA. Uma linha que fecha por SILENCIO ou por pontuacao tem a
palavra provada pelo proprio audio: publica-se inteira. Uma linha que fecha pelo
TETO de caracteres corta a meio -- a cauda nao provada TRANSPORTA-SE para a
linha seguinte, em vez de ser publicada ou perdida (ver `LineFormer._close`).

ISTO E INDEPENDENTE DA LINGUA. A regra nao conhece palavras, dicionarios nem
linguas: le a MARCA do tokenizer, que e' a mesma para qualquer lingua.
`so`/`sou` e `próx`/`próximo` seguem a MESMA regra.

O ORATORIO: `_main/incomplete-word-oracle.py`.
"""
from __future__ import annotations

#: A pontuacao que PROVA que a palavra anterior acabou. Nenhum token de
#: continuacao pode vir depois de um ponto final, de uma virgula ou de um
#: ponto-e-virgula: o tokenizer nao liga uma palavra a outra atraves de um
#: sinal.
CLOSING_MARKS = ".?!,;:"

#: A pontuacao que FECHA a frase. Uma linha terminada ninguem vai continuar.
TERMINAL_MARKS = ".!?…"


def open_word_start(frags):
    """Onde comeca a CAUDA ABERTA (a palavra nao provada), em `(offset, linha)`.

    `frags` sao os pares `(texto, continues)` do `LineFormer._words`, na ordem em
    que chegaram. A juncao e' a MESMA de `join_fragments` (glue quando
    `continues`, um espaco quando nao), e o offset e' o indice na string unida.

    Devolve `(offset, texto_unido)`; `offset == len(texto)` quando nao ha cauda
    (linha vazia ou a terminar em pontuacao de fecho).
    """
    text = ""
    spans = []          # (offset, texto, continues)
    for frag, cont in (frags or ()):
        piece = str(frag or "")
        if not piece:
            continue
        if not text:
            text = piece
        elif cont:
            text += piece
        else:
            text += " " + piece
        spans.append((len(text) - len(piece), piece, bool(cont)))
    if not spans:
        return 0, ""
    text = text.strip()
    if not text:
        return 0, ""
    if text[-1] in CLOSING_MARKS:
        # A pontuacao e' a prova: nada fica por provar.
        return len(text), text
    # A cauda comeca na ULTIMA palavra do ULTIMO fragmento...
    start, piece, cont = spans[-1]
    cut = piece.rfind(" ")
    if cut >= 0:
        return start + cut + 1, text
    # O ultimo fragmento nao tem separador: e' UMA palavra. Se ele CONTINUA a
    # palavra anterior, a cauda comeca no fragmento anterior e recua-se ate' um
    # separador; se nao continua, a cauda e' ele e so' ele.
    if not cont:
        return start, text
    tail_start = start
    for s, prev_piece, _ in reversed(spans[:-1]):
        prev_cut = prev_piece.rfind(" ")
        if prev_cut >= 0:
            tail_start = s + prev_cut + 1
            break
        tail_start = s
    return tail_start, text


def proven_text(frags):
    """`(texto_provado, cauda_aberta)` para os fragmentos de uma linha aberta.

    Tudo o que o dono ja pode ler, e o que ainda nao pode. A cauda e' sempre
    sufixo do texto unido; o provado e' sempre prefixo. Nada se perde: a cauda
    volta inteira no parcial seguinte, assim que o tokenizer a prove.
    """
    offset, text = open_word_start(frags)
    if offset >= len(text):
        return text, ""
    return text[:offset].rstrip(), text[offset:]


def stable_text(text):
    """COMPATIBILIDADE: o texto sem a ultima palavra separada por espaco.

    Mantido porque havia chamadores e oraculos a medir esta funcao; a regra que
    VALE e' `proven_text(frags)`, que prova por token e nao por espaco. Ao
    contratio da primeira versao, o texto e' `strip()`ado antes de ser cortado:
    um espaco final fazia `rfind(" ")` cair no proprio ultimo caracter e a
    funcao devolvia a linha INTEIRA -- medido no log vivo de 2026-10-30, onde o
    parcial `"éme boxes erops or"` saiu com a ultima palavra por provar.
    """
    if not text:
        return ""
    text = str(text).strip()
    if not text:
        return ""
    if text[-1] in CLOSING_MARKS:
        return text
    cut = text.rfind(" ")
    if cut <= 0:
        return ""
    return text[:cut].rstrip()


def close_parts(frags, carry):
    """`(texto_a_publicar, cauda_a_transportar)` no fecho de uma linha.

    `carry=False` (silencio, pontuacao, fim do stream): a ultima palavra esta
    provada pelo proprio audio, publica-se a linha inteira e nao se transporta
    nada -- devolve `(None, "")`, que e' o pedido para o chamador publicar
    `self.line()` como sempre.

    `carry=True` (o TETO de caracteres): corta onde calha. Publica-se o que esta
    provado e a cauda volta como primeiro fragmento da linha seguinte, para a
    palavra acabar onde pertence.
    """
    if not carry:
        return None, ""
    prov, tail = proven_text(frags)
    return prov, tail
