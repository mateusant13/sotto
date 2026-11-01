"""A JANELA DE DUAS LINHAS -- o display do YouTube, como ele o define.

O DONO, 2026-10-22, verbatim:
    *"e tambem ter o display 1:1. e pra surgir palavras, quebrar linhas, usar o
    timing de nova linha ou nao, igual o youtube."*
    *"a legenda do youtube ta completamente bugada"* -- dito de um historico com a
    mesma linha seis vezes e frases partidas ao meio.

O QUE O PAYLOAD DO YOUTUBE DIZ, medido neste repo (`_main/youtube-1to1-probe.py`,
video `WdaHAGRBB6s`, 2026-10-22):

  * `wpWinPositions[1]` traz `rcRows: 2` e `ccCols: 40`: uma janela de DUAS linhas
    de quarenta colunas. Nao e uma linha que se substitui -- sao duas que rolam.
  * cada linha e um evento sem `aAppend`; cada separador e um evento `aAppend: 1`
    cujo unico segmento e `"\\n"`. O separador NAO e texto.
  * `tStartMs` e `dDurationMs` de cada linha dizem QUANDO ela esta viva. Duas
    linhas ficam vivas ao mesmo tempo durante **94 %** do video medido (32,0 s de
    33,8 s); o `cue_at` que a app usava devolve UMA, logo deitava a segunda fora
    em nove decimos do tempo.

ESTE MODULO NAO SUBSTITUI `youtube_captions.cue_at` -- nao pode: `cue_at` tem
oraculo proprio e um contrato de um cue. Ele da o que falta: AS LINHAS QUE O
YOUTUBE DESENHA num instante, na ordem em que estao no ecra (a mais antiga em
cima), e uma chave estavel para o chamador so emitir quando a janela MUDA.

A regra, em duas linhas de codigo, e a que o proprio payload descreve:

    vivas(t)  = [c for c in cues if c.start <= t < c.end]
    desenho(t) = vivas(t)[-2:]          # a capacidade que o rcRows declara

Porque `[-2:]` e nao `[:2]`: a janela ROLA. A linha nova entra em baixo e a mais
antiga sai por cima quando a terceira chega; o que fica no ecra sao sempre as duas
ULTIMAS que comecaram.
"""
from __future__ import annotations

import re

#: As linhas que o YouTube desenha ao mesmo tempo. Vem de `rcRows` no payload; o
#: numero fica aqui como DEFAULT porque um payload sem `wpWinPositions` nao pode
#: deixar a legenda sem janela.
CAPACITY = 2

#: O separador da chave. Um caractere que nao aparece num texto de legenda, para
#: `["a", "b"]` e `["a\\x1fb"]` nao darem a mesma chave.
_SEP = "\x1f"


def live_lines(cues, t, capacity=CAPACITY):
    """As linhas que o YouTube desenha no instante `t`, da mais antiga para a nova.

    Um cue cobre `[start, end)`. Quando mais de `capacity` estao vivas -- e a track
    automatica faz isso, porque a duracao de uma linha atravessa a seguinte -- so as
    `capacity` que COMECARAM POR ULTIMO ficam: e a janela a rolar.

    Devolve `[]` sem instante, sem cues, ou num buraco entre cues: buraco e um
    facto (o YouTube nao desenha nada), nao um erro.
    """
    if t is None:
        return []
    return [str(cue.get("text") or "") for cue in _live_cues(cues, t, capacity)]


def _live_cues(cues, t, capacity=CAPACITY):
    """A JANELA no instante `t` -- os proprios cues, nao o texto deles.

    `live_lines` devolve o texto (o desenho); `revealed_lines` precisa do cue
    INTEIRO, porque a revelacao de cada linha depende do relogio dela. As duas
    passam por aqui para a janela ter UMA definicao so.
    """
    if t is None:
        return []
    try:
        t = float(t)
    except (TypeError, ValueError):
        return []
    live = []
    for cue in cues or ():
        if not isinstance(cue, dict):
            continue
        try:
            start = float(cue.get("start"))
            end = float(cue.get("end"))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        if start <= t < end:
            live.append((start, cue))
    if not live:
        return []
    live.sort(key=lambda pair: pair[0])
    return [cue for _start, cue in live[-max(1, int(capacity)):]]


def revealed_text(cue, t):
    """O texto do cue ATE `t`, palavra a palavra -- a revelacao do YouTube.

    O DONO, 2026-10-22: *"e pra surgir palavras, quebrar linhas, usar o timing de
    nova linha ou nao, igual o youtube."* MEDIDO 2026-10-26 no payload de
    `WdaHAGRBB6s`: 69 dos 106 segmentos trazem `tOffsetMs`, e o player revela
    `Have` em 0, ` you` em 240 ms, ` ever` em 400 ms. Sem isto o Sotto pintava a
    linha inteira de uma vez: palavras, quebras e timing batiam, a revelacao nao.

    Regras, cada uma com o seu porque:

      * um cue SEM palavras devolve o texto inteiro -- o comportamento antigo, e o
        unico honesto quando o payload nao declarou relogio nenhum;
      * a revelacao e sempre um PREFIXO do texto do cue. Se a concatenacao das
        palavras nao for prefixo (payload estranho, ou pontuacao absorvida), devolve
        o texto inteiro em vez de inventar um meio-caminho;
      * nenhuma palavra aparece antes do instante dela -- e o que impede o Sotto de
        mostrar mais do que o YouTube mostra;
      * o instante ilegivel devolve o texto inteiro: um relogio que nao se le nao
        pode esconder a legenda.
    """
    text = str((cue or {}).get("text") or "")
    words = (cue or {}).get("words")
    if not words:
        return text
    try:
        t = float(t)
    except (TypeError, ValueError):
        return text
    shown = []
    for word in words:
        if not isinstance(word, dict):
            continue
        try:
            if float(word.get("start")) <= t + 1e-9:
                shown.append(str(word.get("text") or ""))
        except (TypeError, ValueError):
            continue
    out = "".join(shown).strip()
    if not out:
        return ""
    return out if text.startswith(out) else text


def revealed_lines(cues, t, capacity=CAPACITY):
    """A janela de `live_lines`, com cada linha revelada ate `t`.

    O chamador vivo (`sotto_webview._yt_lines`) usa esta em vez de `live_lines`:
    a janela e a mesma, o que muda e que cada linha chega a crescer com o relogio
    do proprio YouTube em vez de aparecer inteira.
    """
    return [revealed_text(cue, t) for cue in _live_cues(cues, t, capacity)]


def collapse_growth(lines):
    """A MESMA FRASE NAO ENTRA DUAS VEZES -- o B5 do dono, verbatim:

        *"coisa duplicada"*, *"a frase era maior, foi sumindo"*

    Medido no historico dele em 2026-10-24 (`_main/caption-dup-repro.py`, 10 ficheiros, 2077 linhas):
    **79 iguais consecutivas**, **0** de crescimento por prefixo, **6** de sobreposicao (a janela
    deslizante do ASR). O numero antigo "517 de 2077" nao se reproduz com nenhuma destas tres
    relacoes e fica **retirado** -- o que a regra abaixo continua a servir e o caso
    `'O radio'` -> `'O radio Segunda'` -> `'O radio Segunda Os'`, que e crescimento por prefixo.

    A regra e ESTREITA de proposito: colapsa so quando a linha nova e IGUAL a
    anterior ou COMECA POR ELA (o crescimento medido). Duas linhas vivas
    diferentes nao se tocam -- `'What?'` e `'>> What?'` ficam as duas, porque a
    segunda nao comeca pela primeira. Fica sempre a MAIOR, e uma so vez.

    Vive aqui, e nao no `sotto_webview.py`, por duas razoes: e testavel sem
    levantar a app, e aquele ficheiro tem um ratchet de tamanho (`_main/
    code-health-oracle.py`) que nao perdoa crescimento.
    """
    out = []
    for line in lines or ():
        line = str(line).strip()
        if not line:
            continue
        if out and (line == out[-1] or line.startswith(out[-1])):
            if len(line) > len(out[-1]):
                out[-1] = line
            continue
        out.append(line)
    return out


def window_key(lines):
    """Uma chave estavel para a janela desenhada.

    O chamador compara a chave desta poll com a da poll anterior e so emite quando
    ela muda -- e o que impede a MESMA linha de entrar no historico seis vezes. A
    chave leva a ORDEM, porque `["a", "b"]` e `["b", "a"]` sao desenhos diferentes.
    """
    return _SEP.join(str(line) for line in (lines or ()))


def history_line(lines):
    """A janela como UMA linha de historico, sem repetir o que ja esta la.

    As duas linhas do ecra sao DOIS PEDACOS da mesma frase a rolar, por isso o
    historico recebe-as juntas -- mas um pedaco que aparece nas duas linhas (o
    YouTube repete a ultima palavra ao rolar) entra uma vez so, e um pedaco que ja
    acabou na linha anterior nao volta.
    """
    parts = []
    for line in lines or ():
        text = " ".join(str(line).split())
        if not text:
            continue
        if parts and text == parts[-1]:
            continue
        parts.append(text)
    return " ".join(parts)

def paint_line(words):
    """A LINHA QUE O PROPRIO PLAYER ESTA A PINTAR -- a legenda antes do track chegar.

    O DONO, 2026-10-22 09:35, verbatim: *"tu so viu carregar a pagina depois de varios
    segundos de ja ter carregado? arruma isso."*

    O QUE ACONTECIA, e porque e um defeito de DESENHO e nao de velocidade: o caminho
    vivo lia as palavras que o player pinta (UI Automation, de graca) e so as mostrava
    DEPOIS de o track do YouTube chegar, porque a linha vinha do track e nao das
    palavras. Enquanto o track nao chegava (o extract mede segundos, e um video novo
    invalida a cache) a funcao devolvia `track-pending` e a legenda ficava VAZIA --
    apesar de as palavras exatas que o dono ve no YouTube ja estarem lidas.

    Estas palavras NAO sao uma aproximacao: sao o texto que o player esta a desenhar
    naquele instante, portanto sao 1:1 por construcao. O track (com a janela de duas
    linhas e o timing) substitui-as quando chega.

    Devolve `""` quando nao ha nada para pintar -- o chamador distingue "nao sei" de
    "nao ha" pela lista vazia, nunca por esta funcao inventar texto.
    """
    if not words:
        return ""
    if isinstance(words, str):
        words = [words]
    # Uma quebra de linha dentro de uma palavra NAO pode virar duas linhas: a
    # legenda viva e UMA linha (a janela de duas linhas vem do track, nao daqui).
    parts = [" ".join(str(w).split()) for w in words]
    parts = [w for w in parts if w]
    return " ".join(parts)

