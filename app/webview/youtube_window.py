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



#: O QUE O YOUTUBE DESENHA A FRENTE DE UMA FALA. E' dele, e o dono PEDIU a
#: copia 1:1: no ecra dele a linha e' `&gt;&gt; Nossa.`, por isso o marcador sai do
#: que NOS pintamos e o texto fica -- ver `painted_lines`.
_SPEAKER_MARKERS = (">>", "&gt;&gt;", "\u203a\u203a")


def painted_lines(words):
    """AS LINHAS que o player esta' a pintar, na ordem, INTEIRAS -- 1:1.

    O DEFEITO QUE ISTO CURA (medido nas imagens do dono, 2026-11-02, verbatim:
    *"sotto devia ta copiando 1:1 sem truncar palavras"* e *"essa legenda foi
    construindo ao longo do tempo, inves de dar display no mesmo timing que a do
    youtube"*). O caminho pintado passava por `paint_line` (que JUNTA tudo numa
    linha) e depois por `window_by_paint` (que re-quebra a partir do track e corta
    em `cap = min(pintado, relogio_de_palavra)`). As duas coisas erram de formas
    que ele viu no ecra:

      * duas linhas do player viram uma so', que o overlay volta a quebrar onde
        quer -- e o `>>` de uma linha do meio fica no meio do texto;
      * o `cap` corta no numero de palavras, portanto `... a Yamato ja' do` sai
        `... a Yamato ja' d` (meia palavra);
      * o `cap` cresce com o relogio, portanto a linha CONSTR OI-se ao longo do
        cue em vez de aparecer quando o YouTube a mostra;
      * e quando o alinhamento falha, nao se pinta NADA -- a terceira imagem,
        com o player a mostrar duas linhas e o Sotto calado.

    A REGRA, aqui e em uma linha: o texto que o player desenha E' a legenda. Nao
    se quebra, nao se corta, nao se completa com o track e nao se atrasa; sai como
    esta', no instante em que muda. `painted_words` ja' devolve os filhos da
    janela de legenda EM ORDEM DE LEITURA, um por linha quando o YouTube usa a
    faixa manual (medido: `['&gt;&gt; Nossa.', '&gt;&gt; ta' segurando essa wave,']`).

    O QUE FICA DE FORA, e por que:
      * marcador de fala (`>>`): e' do PLAYER, nao e' fala; pinta-lo no nosso
        overlay duplica um simbolo que ja' esta' na tela do video;
      * linhas vazias: nada a pintar;
      * repeticoes CONSECUTIVAS iguais: o leitor de UIA pode apanhar o mesmo
        elemento duas vezes na troca de cue, e duas linhas iguais e' o "coisa
        duplicada" que ele ja' reclamou.

    Devolve `[]` -- nunca texto inventado -- quando nao ha nada pintado.
    """
    if not words:
        return []
    if isinstance(words, str):
        words = [words]
    out = []
    for raw in words:
        text = " ".join(str(raw or "").split())
        for marker in _SPEAKER_MARKERS:
            while text.startswith(marker):
                text = text[len(marker):].strip()
        if not text:
            continue
        if out and out[-1] == text:
            continue
        out.append(text)
    return out


def track_words(cues, t=None, window=30.0):
    """As palavras da FAIXA servida -- todas, ou so' as de uma janela de `t`.

    Sem `t` custa um varrimento da faixa inteira (1436 cues no video medido a
    2026-11-02); com `t` custa as cues de +/-`window` segundos. O chamador guarda
    o resultado por faixa (`sotto_webview` faz isso em `_yt_words_pool`).
    """
    pool = set()
    for cue in cues or ():
        try:
            start = float(cue.get("start"))
            end = float(cue.get("end"))
        except (TypeError, ValueError):
            start = end = None
        if t is not None and start is not None:
            if end is not None and end < float(t) - window:
                continue
            if start > float(t) + window:
                continue
        for word in str(cue.get("text") or "").lower().replace("\n", " ").split():
            pool.add(word.strip(".,!?;:\"'()[]"))
    pool.discard("")
    return pool


def match_ratio(lines, pool, ratio_min=0.5):
    """As linhas pintadas pertencem a faixa servida? -> {"ok", "ratio", "words"}.

    POR QUE ISTO EXISTE, e nao bastava devolver as linhas: a politica do dono e'
    `nunca traduzido` (`docs/politica-youtube.md`), e o rodape' do player pode estar
    numa faixa TRADUZIDA. Espelhar sem perguntar poria uma traducao na tela. A
    regra e' a do que ele ve: se >= `ratio_min` das palavras pintadas existem na
    faixa ORIGINAL que servimos, entao o player esta' a pintar a NOSSA faixa e a
    copia directa vale; se nao, o caminho do relogio (que desenha a faixa original)
    continua a mandar.
    """
    words = []
    for line in lines or ():
        words.extend(str(line or "").lower().split())
    words = [w.strip(".,!?;:\"'()[]") for w in words]
    words = [w for w in words if w]
    if not words:
        return {"ok": False, "ratio": 0.0, "words": 0}
    hits = sum(1 for w in words if w in (pool or ()))
    ratio = hits / float(len(words))
    return {"ok": ratio >= ratio_min, "ratio": ratio, "words": len(words)}


def _strip_markers(text):
    """Uma linha sem o marcador de fala do player (`>>`, `&gt;&gt;`, `››`)."""
    out = " ".join(str(text or "").split())
    for marker in _SPEAKER_MARKERS:
        while out.startswith(marker):
            out = out[len(marker):].strip()
    return out


#: As linhas que a caixa do player mostra de cada vez (medido: 2).
ROWS_CAP = 2


def painted_rows(words, items=None):
    """As LINHAS a desenhar a partir do que a janela de legenda entrega.

    O leitor de UIA devolve os filhos da janela, e o YouTube muda de FORMA entre
    faixas: a faixa MANUAL entrega LINHAS (`['>> Nossa.', '>> ta segurando essa
    wave,']`) e a AUTOMATICA entrega PALAVRAS (`['>> Nossa.', '>> ta', 'segurando',
    'essa', 'wave,']` -- medido nesta box, 2026-11-02 22:19:36).

    Nos dois casos o numero de linhas e' do PLAYER, nao nosso:

      * se algum filho tem espaco, ele e' uma linha e as linhas sao os filhos;
      * se sao palavras soltas, o player esta' a escrever UMA linha -- e a linha e'
        essas palavras juntas, na ordem, ate onde ele ja' escreveu.

    Nao se completa com o track, nao se corta em `cap`, nao se atrasa pelo relogio:
    e' o que esta' no ecra dele. Marcadores de fala saem (`>>`), duplicadas
    consecutivas tambem -- as mesmas regras de `painted_lines`.
    """
    # O RECT MANDA, QUANDO EXISTE (2026-11-02): e' ele que diz em que linha cada
    # palavra caiu no ecra do player -- a quebra de linha 1:1.
    by_rect = rows_from_items(items) if items else []
    if by_rect:
        out = []
        for line in by_rect:
            text = _strip_markers(line)
            if text and (not out or out[-1] != text):
                out.append(text)
        if out:
            # A CAIXA DO PLAYER TEM DUAS LINHAS E NOS DESENHAVAMOS TRES
            # (2026-11-03). MEDIDO na sessao do dono:
            #   `EXTERNAL_CAPTION_DRAWN rows=3 lines=['estao tendo um
            #    desempenho melhor.', 'Talvez, eh, uma boa', 'estrategia...']`
            # nos instantes em que a pintura trazia tres linhas (a que esta' a
            # sair, a actual e a que entra). O YouTube mostra DUAS; a terceira
            # e' conteudo que ele JA' empurrou para fora da caixa, e desenha-la
            # poe o Sotto a mostrar a linha seguinte antes do player -- que e'
            # exactamente o *'ta fora de sync'* dele. Fica com as DUAS ultimas,
            # que sao as que o roll-up deixa no ecra.
            return out[-ROWS_CAP:] if len(out) > ROWS_CAP else out
    # SEM RECTS: o marcador de fala diz onde cada LINHA do player COMECA (medido
    # 2026-11-02 22:19:36: `['>> Nossa.', '>> ta', 'segurando', 'essa', 'wave,']`
    # -- o `>>` abre a linha 2 e `segurando` continua a mesma linha). Sem marcador
    # nenhum e' uma linha so', como na legenda automatica corrida.
    if isinstance(words, str):
        words = [words]
    out = []
    pending = False
    for raw in (words or ()):
        text = " ".join(str(raw or "").split())
        if not text:
            continue
        started = any(text.startswith(m) for m in _SPEAKER_MARKERS)
        text = _strip_markers(text)
        if not text:
            # UM MARCADOR SOZINHO TAMBEM ABRE LINHA (medido 2026-11-02: o leitor
            # de UIA entrega `'>>'` como filho proprio em algumas faixas). Sem
            # isto a palavra seguinte colava-se a' linha anterior.
            if started:
                pending = True
            continue
        if started or pending or not out:
            out.append(text)
            pending = False
        else:
            out[-1] = (out[-1] + " " + text).strip()
    return out


def rows_from_items(items):
    """Agrupa os filhos pintados nas LINHAS que o player desenhou.

    Cada item tem `text` e o rectangulo (`left/top/right/bottom`). Duas palavras
    estao na MESMA linha quando os centros verticais caem dentro de metade da
    menor altura -- criterio que nao depende de fonte nem de zoom, porque compara
    uma altura com uma distancia em pixels da mesma janela.

    Devolve as linhas por ordem de cima para baixo, e dentro de cada linha por
    ordem da esquerda para a direita: a ordem de leitura do ecra. Sem rects
    utilizaveis (`bottom == top`) devolve `[]` e quem chama usa as palavras soltas.
    """
    rows = []
    for item in items or ():
        text = " ".join(str(item.get("text") or "").split())
        if not text:
            continue
        top = int(item.get("top") or 0)
        bottom = int(item.get("bottom") or 0)
        left = int(item.get("left") or 0)
        if bottom <= top:
            return []
        rows.append({"text": text, "top": top, "bottom": bottom, "left": left,
                     "mid": (top + bottom) / 2.0, "h": bottom - top})
    if not rows:
        return []
    rows.sort(key=lambda r: (r["mid"], r["left"]))
    lines = []
    for row in rows:
        placed = False
        for line in lines:
            tol = max(1.0, min(line["h"], row["h"]) / 2.0)
            if abs(line["mid"] - row["mid"]) <= tol:
                line["items"].append(row)
                line["h"] = min(line["h"], row["h"])
                placed = True
                break
        if not placed:
            lines.append({"mid": row["mid"], "h": row["h"], "items": [row]})
    out = []
    for line in lines:
        line["items"].sort(key=lambda r: r["left"])
        text = " ".join(r["text"] for r in line["items"])
        text = " ".join(text.split())
        if text:
            out.append(text)
    return out
