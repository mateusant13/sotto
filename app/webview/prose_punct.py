"""Fecho de linha por PROSA + pausa: a marca que o motor nao deu e o silencio provou.

── O DEFEITO QUE ISTO JULGA ────────────────────────────────────────────────
Dono, 2026-11-09: *"historicos desde as 15h de hoje: melhorar a qualidade da
transcricao a custo barato"*. MEDIDO no proprio arquivo dele
(`history/2026-11-09/17.md`, 63 linhas): **37** linhas `reason=stable` e
**nenhuma** delas fecha com marca; 43 das 63 nao fecham. A causa esta' na guarda
de lingua do restaurador de pontuacao (`worker/punctuation_model.py`,
`supported_lang`: so' `en*`), e o modelo multilingue foi RECUSADO por medicao
(2,4 GB + torch, `I:` a 4,8% livre). Logo a marca tem de vir de outro lugar.

── DE ONDE ELA VEM, E O QUE **NAO** SE INVENTA ─────────────────────────────
Duas evidencias, as duas ja' medidas nesta casa:

1. **PROSA.** Uma linha que a politica FECHOU e' uma unidade fechada: o worker
   nao a corta a meio por gosto. Logo uma linha fechada sem marca ganha `.` no
   fim -- salvo quando a ultima palavra e' um CONECTOR (artigo, preposicao,
   conjuncao, auxiliar). `"like I'm just a"` + `.` seria mentira; essa linha
   fica como esta'. A lista e' pt-BR **e** ingles porque o arquivo do dono e'
   bilingue (medido: as duas linguas na mesma hora de transcricao).
2. **PAUSA, com o piso que a casa ja' mediu.** `worker/punctuation_prosody.py`
   mediu, em 6 fixtures limpos, que a menor pausa de fim de frase e' **773 ms** e
   a maior de fim de oracao **440 ms**; o piso de frase ficou em **600 ms**
   (`SENTENCE_MIN_MS`). Aqui o numero e' o MESMO, e ele e' o que separa "a fala
   parou" de "o modelo atrasou": sem pausa medida nao ha marca.

O que NUNCA se acrescenta: `?` e `!`. Nenhuma fixture desta casa tem pergunta, e
a direcao do F0 mediu 3 subidas / 2 descidas nas 5 pausas de oracao -- moeda ao
ar. Um `?` inventado e' o defeito que o dono chamou inadmissivel do outro lado
(uma marca a saltar de sitio).

── ONDE ISTO CORRE, E POR QUE NAO NA LEGENDA AO VIVO ──────────────────────
No caminho de LEITURA do historico (`_history_entries`), que alimenta o painel,
a busca e o export. Na legenda ao vivo seria preciso esperar a linha SEGUINTE
para saber a pausa -- e uma legenda que espera e' exatamente o atraso que o dono
proibe. O arquivo em disco continua sendo o registo CRU do que o motor disse: a
marca e' de leitura, e por isso tambem vale para as linhas ja' gravadas.

Puro stdlib, sem I/O, sem estado.
"""
from __future__ import annotations

import re

__all__ = ['SENTENCE_MIN_S', 'DANGLING', 'close_line', 'last_word']

#: O piso de PAUSA que separa fim de frase de fim de oracao. O numero e' o de
#: `worker/punctuation_prosody.SENTENCE_MIN_MS` (600 ms), medido em 2026-11-05
#: sobre 6 fixtures: a pausa de frase mais estreita mediu 773 ms, a de oracao
#: mais larga 440 ms. Repetido aqui (e nao importado) porque o app nao importa o
#: pacote do worker, e o oraculo exige que os dois numeros sejam o mesmo.
SENTENCE_MIN_S = 0.6

#: A cauda que NAO ganha ponto: uma linha que termina num conector foi cortada a
#: meio, e o ponto ali seria uma afirmacao que o audio nao fez. pt-BR + en.
DANGLING = frozenset("""
a o as os um uma uns umas de do da dos das em no na nos nas por para com sem
que e ou mas se como quando porque onde qual quais quem cujo cuja ao aos pelo
pela pelos pelas num numa nem ja ainda so muito pouco mais menos tambem
i you he she it we they me him her us them my your his its our their
the an of to in on at for with without and or but if because where which who
whom whose is are was were be been being am do does did have has had will
would can could shall should may might must not no very most less least just
also then than this these those there here what how
""".split())

#: Marca terminal que ja' esta' la'. `,`/`;`/`:` NAO contam: sao o artefacto que
#: o proprio `punctuation_prosody` remove ("a linha acaba ali por decisao do
#: corte, nao por a fala ter parado").
_TERMINAL = re.compile(r'[.!?\u2026]["\'\u201d\u2019)\]\u00bb]?\s*$')

#: O lixo de cauda que o ponto substitui.
_TRAILING_JUNK = re.compile(r'[\s,;:\u2014-]+$')

#: A cauda que pede identidade: abrir um parenteses/aspas e nao fechar e' corte.
_OPEN_TAIL = '"\'([\u201c\u2018-\u2014/'


def last_word(text: str) -> str:
    """A ultima palavra, sem pontuacao de cauda, em minusculas."""
    body = _TRAILING_JUNK.sub('', str(text or ''))
    for ch in '"\')\]\u201d\u2019\u00bb':
        if body.endswith(ch):
            body = body[:-1]
    parts = body.split()
    if not parts:
        return ''
    word = parts[-1].lower()
    for ch in '.,;:!?\u2026"\'()[]\u201c\u201d\u2018\u2019\u00ab\u00bb':
        word = word.strip(ch)
    return word


def close_line(text: str, gap_s) -> str:
    """Devolve `text` com `.` no fim quando a PROSA e a PAUSA o provam.

    Identidade (devolve a mesma string) em todos os casos sem evidencia:
    texto vazio, marca terminal ja' presente, cauda pendurada num conector,
    ultimo caracter a abrir um bloco, ou pausa ausente/curta.
    """
    body = str(text or '')
    if not body.strip():
        return text
    if _TERMINAL.search(body):
        return text
    stripped = _TRAILING_JUNK.sub('', body)
    if not stripped:
        return text
    if stripped[-1] in _OPEN_TAIL:
        return text
    # Um parenteses reto aberto e nao fechado e' o mesmo corte que uma virgula
    # pendurada: o ponto ali fecharia uma frase dentro de um bloco que continua.
    if stripped.count('(') != stripped.count(')'):
        return text
    if stripped.count('[') != stripped.count(']'):
        return text
    if last_word(stripped) in DANGLING:
        return text
    if gap_s is None:
        return text
    try:
        gap = float(gap_s)
    except (TypeError, ValueError):
        return text
    if gap < SENTENCE_MIN_S:
        return text
    return stripped + '.'
