"""O relogio do player NUNCA faz a legenda recuar.

A QUEIXA DO DONO, verbatim (2026-10-30): *"a legenda nao ta sincronizada
direito. e parece que repete a legenda de instantes atras no ao vivo, depois
desbuga, e mostra ao vivo"*.

O QUE FOI MEDIDO (`_main/webview-run.log`, 2126 linhas `YOUTUBE_CAPTION`):
**129** linhas sao um cue cujo INICIO e' anterior ao da linha servida antes --
37,6 s atras, 40,4 s atras, e uma 359,0 s atras. A cue `start=34.239`
(`"economista formada pela USP,"`) foi servida **tres vezes em 24 s** enquanto
a faixa servida avancava 50 s -> 74 s. Nao era lentidao: era um **relogio
congelado** que o ramo `painted-other-track` confia e usa para escolher a cue.

A CAUSA, no codigo (`sotto_webview.py`): o ramo aceita a leitura enquanto
`moved or key == self.yt_foreign_key`. A segunda metade e' o buraco -- quando a
pintura E o relogio estao os dois parados, `key` e' igual e o ramo serve a
MESMA cue antiga para sempre. A intencao escrita no comentario ao lado (*"a
prova do congelamento e' uma pintura que MUDA com o relogio parado"*) e' o
inverso do que a condicao faz.

## A regra

Duas fontes de tempo, e uma so' pode recuar:

*  O **RELIGIO** (o UIA do player) so' tem licenca para ANDAR PARA A FRENTE.
   Ele e' grosso: le casas inteiras (`t=1206.0`), atrasa-se, e mediu-se a
   SALTAR PARA TRAS em 1 s, 4 s e 5 s -- jitter de leitura, nao seeks (o video
   estava em ~1170 e a leitura fez 1175 -> 1170 -> 1171). Nunca escolhe uma
   cue atras do chao.
*  A **PINTURA** (as palavras que o player esta' a desenhar agora) e' o
   relogio mais adiantado que existe, e e' tambem o UNICO sinal capaz de
   provar um seek a serio: o player a desenhar palavras de outro sitio E' o
   facto. Ela sobe o chao sempre, e so' o DESCE quando salta para tras o
   bastante para nao ser um cue repetido (`SEEK_BACK_S`).

Assim o relogio nunca arrasta o ecra para tras, e um seek a serio continua a
funcionar -- porque quem o declara e' a pintura e nao a leitura.

A regra e' do TEMPO: nao le nenhum dicionario e nao depende da lingua.
"""
from __future__ import annotations

#: Abaixo disto o relogio esta' PARADO (o player le a mesma casa decimal).
FREEZE_EPS_S = 0.05

#: Um salto para tras da PINTURA maior que isto e' um seek, nao um cue repetido.
SEEK_BACK_S = 2.0


def decide(now_t, floor, freeze_eps=FREEZE_EPS_S):
    """A decisao inteira do RELOGIO: `(instante a servir, chao novo)`.

    `floor` -- o inicio da cue mais avancada ja' servida (None = nada).

    `(None, floor)` quando nao ha leitura nenhuma. Fora disso o instante
    servido nunca fica atras do chao -- e' o defeito do dono, e por isso aqui
    nao ha excepcao nenhuma: o relogio NAO tem voto sobre recuar.
    """
    if now_t is None:
        return None, floor
    t = float(now_t)
    if floor is None:
        return t, t
    base = float(floor)
    if t >= base - freeze_eps:
        return t, (t if t > base else base)
    return base, base


def advance(floor, position, seek_back=SEEK_BACK_S):
    """O chao depois de a PINTURA servir em `position`.

    Sobe sempre que a pintura esteja' a frente. Desce apenas quando a pintura
    salta para tras mais do que `seek_back` -- ai e' um seek a serio, e o chao
    tem de descer com ele, senao a legenda ficava presa no ponto antigo para
    sempre (o mesmo defeito ao contrario).
    """
    if position is None:
        return floor
    try:
        pos = float(position)
    except (TypeError, ValueError):
        return floor
    if floor is None:
        return pos
    base = float(floor)
    if pos > base:
        return pos
    if base - pos > seek_back:
        return pos
    return base
