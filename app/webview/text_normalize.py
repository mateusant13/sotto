"""A repeticao que o MOTOR inventou, medida no arquivo do dono -- e a que ele nao toca.

── O DEFEITO ──────────────────────────────────────────────────────────────
Dono, 2026-11-11: *"a merda da normalizacao de texto e frases ta HORRIVEL"*.
MEDIDO no arquivo dele (`history/2026-11-*`, 22 ficheiros, **1302** linhas; o
prefixo de hora e o comentario de proveniencia removidos antes de contar):

| defeito | linhas | % |
|---|---|---|
| `Mmm`/`Umm` e' a linha INTEIRA | 121 | 9,3 % |
| palavra identica adjacente | 122 | 9,4 % |
| linha sem marca terminal | 168 | 12,9 % |

Dentro da segunda, a distribuicao decide a cura: **64** linhas (4,9 %) carregam
uma CORRIDA de 3 ou mais palavras iguais -- `come come come come come come come
come come come come, come domain expansion`, `Watch just watch watch watch watch
watch everybody ...`. Uma corrida dessas nao e' fala: e' o laco em que o
decodificador entra repetindo. As outras **58** sao pares (`what what`, `I i`,
`to to`), e num par adjacente o caso legitimo existe (`super super`).

── A REGRA, E POR QUE ELA E' ESTREITA ─────────────────────────────────────
1. Corrida de **3 ou mais** palavras identicas, separadas so' por ESPACO, vira
   uma. Nenhuma das 64 ocorrencias do arquivo dele e' fala.
2. Corrida de **2** so' cai quando a palavra NAO esta' em `EMPHASIS`, e a mesma
   palavra precisa de **4** para cair quando esta'. `No no` e `super super` sao
   DIALOGO: uma cura que os apaga troca um defeito visivel por um erro invisivel.
3. **A pontuacao quebra a corrida.** `Nao, nao, nao.` e `Yeah. Yeah.` nao se
   tocam -- a virgula e o ponto sao a prova de que a fala foi separada por quem a
   disse. O ponto FINAL da linha nao quebra nada: ele e' do fim, nao da juncao.
4. A caixa e a pontuacao do sobrevivente sao as da PRIMEIRA ocorrencia: a
   primeira e' a que o motor acertou antes de entrar no laco.

── ONDE ISTO CORRE ────────────────────────────────────────────────────────
Dois sitios, e nos dois o texto ja' existe inteiro -- nada espera:
  * a legenda AO VIVO (`push_caption_to_window`, so' o caminho do ASR: as linhas
    do PLAYER sao do YouTube e vao para o ecra 1:1, sem reescrita);
  * a LEITURA do historico (`_history_entries`), ao lado de `prose_punct`; o
    ficheiro em disco continua o registo CRU do que o motor disse.

Puro stdlib, sem I/O e sem estado.
"""
from __future__ import annotations

import re

__all__ = ['MIN_RUN', 'EMPHASIS', 'collapse_runs', 'is_filler_line']

#: A corrida que NAO e' fala. Medido: 64 linhas do arquivo do dono em 1302.
MIN_RUN = 3

#: Reduplicacao que a fala usa como ENFASE. Uma destas precisa de 4 para cair.
#: pt-BR, en, es -- o arquivo dele e' bilingue na mesma hora (medido).
EMPHASIS = frozenset("super very really too mucho mucha muy tanto tanto".split())

#: Uma palavra com o espaco que a antecede. `\S+` porque a palavra repetida pode
#: ser `I'm`, `don't` ou `ca'`.
_WORD = re.compile(r'(\s*)(\S+)')

#: Pontuacao que QUEBRA a corrida entre duas ocorrencias iguais.
_BREAKS = re.compile(r'[,;:!?\u2026\u2014-]')

#: O que nao e' letra nas bordas de uma palavra, para comparar sem caixa.
#:
#: A MESMA tabela de `worker/fusion.py:_EDGE`, e a igualdade e' um PORTAO
#: (`_main/text-normalize-oracle.py`, arm A18), nao um comentario: medido em
#: 2026-11-15 que as duas listas discordavam em `{}`/`\u00ab\u00bb`/`\u2013`, e a
#: mesma linha era uma corrida de repeticao para um modulo e tres palavras para
#: o outro. As duas vivem em arvores de PROCESSO diferentes (a shell e o worker),
#: por isso nao ha um import que as una -- ha um literal e uma arm que o prova.
_EDGE = '.,;:!?"\'()[]{}\u00ab\u00bb\u2026\u2014-\u2013'


def _bare(word: str) -> str:
    return word.strip(_EDGE)


def _same(a: str, b: str) -> bool:
    return _bare(a).casefold() == _bare(b).casefold()


def _broken(left: str, right: str) -> bool:
    """A juncao entre `left` e `right` tem pontuacao de fala?

    A cauda do token da ESQUERDA e a cabeca do token da DIREITA contam; a cauda
    do token da direita nao, porque ela pertence ao fim da palavra seguinte (ou
    ao fim da linha)."""
    tail = left[len(_bare(left)):]
    return bool(_BREAKS.search(tail)) or right[:1] in ',;:'


def collapse_runs(text: str) -> str:
    """Devolve `text` sem as corridas que o decodificador inventou.

    Sem corrida devolve o MESMO objecto (`text is resultado`), para o caminho
    vivo nao pagar uma copia por quadro quando nao ha' nada a fazer.
    """
    if not text:
        return text
    parts = _WORD.findall(text)
    if len(parts) < MIN_RUN:
        return text
    out = []
    i = 0
    changed = False
    while i < len(parts):
        word = parts[i][1]
        j = i
        while j + 1 < len(parts):
            nxt = parts[j + 1][1]
            if _broken(parts[j][1], nxt) or not _same(word, nxt):
                break
            j += 1
        run = j - i + 1
        limit = 4 if _bare(word).casefold() in EMPHASIS else MIN_RUN
        if run >= limit:
            # A pontuacao de CAUDA do ultimo token da corrida vem com o
            # sobrevivente: `Come come come come.` tem de virar `Come.`, e nao
            # `Come` -- sem isto a cura comia o ponto final da linha.
            last = parts[j][1]
            out.append((parts[i][0], parts[i][1] + last[len(_bare(last)):]))
            changed = True
        else:
            out.extend(parts[i:j + 1])
        i = j + 1
    if not changed:
        return text
    return ''.join(space + word for space, word in out)

#: A LINHA QUE E' SO' PREENCHIMENTO (2026-11-11): 121 das 1302 linhas do arquivo
#: dele (9,3 %) sao `Mmm`/`Mmm Mmm.` e nada mais. O predicado e' o MESMO do motor
#: (`worker/caption_noise.py:_NOISE_WORD`), repetido aqui porque o app nao importa
#: o pacote do worker -- e o oraculo exige que os dois padroes sejam identicos,
#: que e' o que impede as duas regras de divergirem em silencio.
_FILLER = re.compile(r'(?:m+|hm+|mhm+)[.,!?…]*', re.IGNORECASE)


def is_filler_line(text: str) -> bool:
    """True so' quando a linha INTEIRA e' preenchimento nao lexical.

    A unidade e' a LINHA, como no motor: um `Mmm` ao lado de uma palavra real e'
    fala (`Mmm, mas eu vou.`) e fica. `fullmatch` torna o requisito atomico.
    """
    words = str(text or '').split()
    return bool(words) and all(_FILLER.fullmatch(word) for word in words)
