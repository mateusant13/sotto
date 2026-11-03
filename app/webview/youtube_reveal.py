"""A JANELA REVELADA PELAS PALAVRAS QUE O PLAYER JA PINTOU.

O DONO, 2026-10-22, verbatim:
    *"e pra surgir palavras, quebrar linhas, usar o timing de nova linha ou nao,
    igual o youtube."*

O PROBLEMA QUE ESTE MODULO RESOLVE, e a medicao que o produziu.

O payload do YouTube traz `tOffsetMs` em 69 dos 106 segmentos do video
`WdaHAGRBB6s` (`_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3`): o player revela a
linha PALAVRA A PALAVRA. O `parse_json3` carrega esse relogio para dentro dos cues
(`cue["words"]`), e `youtube_window.revealed_lines` sabe cortar a linha no
instante certo -- MEDIDO, o prefixo revelado bate com o do payload em 0/677
divergencias (`_main/youtube-1to1-oracle.py`, arm `word-reveal-1to1`).

MAS O CAMINHO VIVO NAO LIGAVA O RELOGIO CERTO. Em `sotto_webview._youtube`, no
ramo `painted` (o ramo COMUM: o player esta a pintar a faixa que servimos), a
janela era montada com

    self._yt_lines(track, float(hit.get('cue', {}).get('start') or 0.0) + 0.001)

isto e, o INICIO DO CUE, nao o instante actual. `revealed_lines(cues, t)` corta
cada linha pelos relogios das palavras dela, e `t = cue.start + 0.001` deixa
passar apenas a PRIMEIRA palavra de cada linha. MEDIDO 2026-10-29 neste repo, com
o payload real:

    revealed_lines(cues, cue0.start + 0.001) -> ['Have']
    revealed_lines(cues, cue0.start + 1.000) -> ['Have you ever had to kill']

Ou seja: a linha NUNCA crescia no ecra. O prefixo ficava colado na primeira
palavra enquanto o player escribia a frase toda. O `_main/youtube-1to1-oracle.py`
nao via este defeito porque a arm `reveal-wired` verifica que a CHAMADA existe
(`youtube_window.revealed_lines(cues, t, 2)`), nao que o relogio que lhe passa
seja o do player -- e o relogio do player, nesse ramo, nem era lido.

A CURA: O RELOGIO DO PLAYER, QUE JA ESTA NAS MAOS DA APP.

O caminho vivo le, por UI Automation, as palavras que o player esta a pintar
agora (`sotto_webview._youtube_painted` -> `youtube_captions.painted_words`).
Essas palavras SAO o prefixo revelado do cue que o player esta a escrever: o
`align_painted` devolve `aligned` (quantas palavras pintadas casaram com a
faixa) e `painted_from` (a partir de que palavra do CUE esse casamento comecou),
e a diferenca `aligned - painted_from` e o numero de palavras JA pintadas do
CUE que o player esta a escrever.

E isso o relogio da revelacao, sem reler o relogio do video: o player E a
fonte da verdade do que esta no ecra, e as palavras pintadas dizem ate onde ele
chegou. Sem relogio nenhum (o do video, ou o do relogio das palavras), a janela
cresce na MESMA ordem e no MESMO instante em que o player cresce.

O MODULO E NOVO, E NOVO POR UMA RAZAO CONCRETA: `youtube_window.py` e
`youtube_captions.py` estao debaixo do ratchet de `code-health` (bytes, linhas e
defs), que ja esta vermelho. Uma correccao nestes ficheiros pioraria esse
portao sem Necessidade; este modulo e novo, logo o ratchet nao o ve.

O QUE ESTE MODULO NAO FAZ:

  * nao decide QUE FAIXA servir (isso e `youtube_captions.fetch_track` e a
    politica de lingua);
  * nao inventa palavras: o prefixo e o prefixo do texto do CUE, cortado num
    numero de palavras que o player ja pintou;
  * nao mexe no relogio das palavras (`tOffsetMs`), que continua a ser a
    autoridade para o resto do caminho (o ramo do relogio do video).

A ESCOLHA ENTRE AS DUAS FONTES DE RELOGIO, e porque e esta:

  * o RELOGIO DO VIDEO (o ramo `has-cue`, `painted-other-track:clock`) serve
    quando nao ha alinhamento com o que o player pintou. E bom, mas MEDIDO
    2026-10-20: o relogio do player pode estar CONGELADO (+0,00 s em 8,35 s de
    relogio de parede), e o ramo `painted` foi desenhado para nao depender
    dele;
  * as PALAVRAS PINTADAS sao o que o player esta a mostrar AGORA, e mudam
    palavra a palavra. Sao 1:1 por construcao, que e o que o dono pediu.

O QUE FICA POR MEDIR, e esta escrito porque o proximo leitor vai pergunta-lo: o
`drift_ms` entre o instante em que o player pintou uma palavra e o instante em
que a nossa janela a mostra e medido pelo falsificador
`_main/youtube-drift-oracle.py` (o `--neg-arm` atrasa a pintura de proposito e
tem de dar RED). Um booleano "sincronizado" nao e um resultado.
"""
from __future__ import annotations

#: A janela do YouTube: DUAS linhas (`rcRows: 2` no payload). Vive aqui para o
#: modulo nao depender de outro ficheiro so por uma constante.
CAPACITY = 2

#: A linha que SAI ainda fica no ecra durante a transicao. MEDIDO no artefacto
#: `_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json`: em 4 das 16
#: amostras o player pinta TRES linhas visiveis -- as duas declaradas em
#: `rcRows: 2` mais a que esta a rolar para fora (a 6,884 s, a linha
#: `>> Then this sword is useless.` ja terminou aos 6,80 s e continua no ecra).
#: O Sotto tem de desenhar as mesmas linhas, logo a janela e `rcRows + 1`.
ROLLUP_ROWS = 1


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def painted_prefix_count(hit):
    """Quantas palavras do CUE que o player esta a pintar ja estao pintadas.

    `hit` e o que `youtube_captions.align_painted` devolve:

      * `aligned`     -- quantas palavras pintadas casaram com a faixa, no total;
      * `painted_from`-- a partir de que palavra do CUE o casamento comecou.

    A diferenca e o numero de palavras do CUE que o player ja escreveu. Um `hit`
    sem estes campos (ou com valores impossiveis) devolve 0: sem evidencia de
    que o player ja pintou alguma palavra, nao se pinta nenhuma.
    """
    if not hit:
        return 0
    aligned = _as_int(hit.get("aligned"), 0)
    painted_from = _as_int(hit.get("painted_from"), 0)
    return max(0, aligned - painted_from)


MARKER = ">>"


def speech_words(text):
    """As PALAVRAS de fala de um texto de legenda -- o `>>` nao e' uma delas.

    O DEFEITO MEDIDO (2026-11-03, `_main/youtube-reveal-oracle.py`, 8/16): o
    alinhamento do que o player PINTou conta as palavras com `_align_tokens`,
    que tira o marcador de mudanca de falante (`youtube_captions._align_tokens`:
    `">> No."` -> `["No."]`). O corte do texto, `first_words`, contava o `>>`
    como palavra -- entao numa linha que comeca pelo marcador o prefixo saia
    SEMPRE UMA PALAVRA ATRAS:

        first_words(">> No.", 1)          -> ">>"            (o "No." nunca vinha)
        first_words(">> Then this sword", 3) -> ">> then this" (faltava "sword")

    Um `>>` e um MARCADOR, nao uma palavra: ele fica no texto (o player desenha-o)
    mas nao gasta orcamento de revelacao. Esta e' a UNICA definicao de palavra
    usada por quem conta (`word_clock_count`) e por quem corta (`first_words`) --
    duas definicoes seriam o mesmo defeito a' espera.
    """
    out = []
    for token in str(text or "").split():
        body = token
        while body.startswith(MARKER):
            body = body[len(MARKER):]
        if body.strip():
            out.append(token)
    return out


def first_words(text, count):
    """As `count` primeiras palavras do texto, com as quebras internas intactas.

    O texto do cue e um texto de legenda: as palavras sao separadas por espaco.
    `count` <= 0 da texto vazio. A palavra `count`-esima e INCLUIDA (e a que o
    player acabou de pintar), porque e o prefixo que o ecra dele mostra.

    A QUEBRA (`'\\n'`) NAO E ESPACO (2026-10-29). `split()` achatava um cue de
    duas linhas numa so e o prefixo deixava de ter a quebra que o player
    desenhou. A contagem continua a ser em PALAVRAS -- a quebra e um separador
    de palavras que fica onde estava -- e o resultado de um texto de uma linha
    e identico ao de antes (`" ".join(words[:count])`).

    O MARCADOR `>>` NAO GASTA ORCAMENTO (2026-11-03): ele conta como zero e
    continua a sair. A definicao de palavra vive em `speech_words`, a mesma que
    `word_clock_count` usa.
    """
    if count <= 0:
        return ""
    left = int(count)
    out = []
    for line in str(text or "").splitlines():
        words = line.split()
        if not words:
            continue
        take = []
        stopped = False
        for token in words:
            if speech_words(token):
                if left <= 0:
                    stopped = True
                    break
                left -= 1
            take.append(token)
        if take:
            out.append(" ".join(take))
        if left <= 0 or stopped:
            break
    return "\n".join(out)


def row_text(text):
    """Uma linha do player com o espaco normalizado e a QUEBRA INTERNA intacta.

    `" ".join(text.split())` -- a forma antiga -- colapsa `'\\n'` e `'\\t'`: um
    `'\\n'` dentro do texto do cue E uma quebra que o player desenhou, e o canal
    do overlay (`rows_text` -> `caption_overlay._layout`) trata `'\\n'` como
    separador de linha. Colapsa-lo fundia duas linhas do player numa so antes
    de chegarem ao desenho.
    """
    lines = [" ".join(line.split()) for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if line)


def live_cues(cues, capacity=CAPACITY):
    """Os cues VIVOS no instante, como `(indice, cue)`, da mais antiga para a nova.

    A MESMA regra de `youtube_window._live_cues`: um cue cobre `[start, end)`, e
    quando mais de `capacity` cues estao vivos ficam os que COMECARAM POR ULTIMO
    -- e a janela a rolar. O indice vem junto porque o `hit` do alinhamento e um
    indice na lista de cues.
    """
    out = []
    for index, cue in enumerate(cues or ()):
        if not isinstance(cue, dict):
            continue
        start = _as_float(cue.get("start"), None)
        end = _as_float(cue.get("end"), None)
        if start is None or end is None or end <= start:
            continue
        out.append((index, cue))
    out.sort(key=lambda pair: _as_float(pair[1].get("start")))
    return out[-max(1, int(capacity)):]


def word_clock_count(cue, t):
    """Quantas PALAVRAS o relogio do proprio YouTube ja' revelou em `t`.

    DEVOLVE `None` QUANDO NAO HA' RELOGIO -- e um `None` aqui nao e' um zero: um
    cue sem `words` nao revelou palavras nenhumas nem todas, simplesmente nao
    declarou o instante de cada uma, e quem chama tem de cair na outra regra.

    A PALAVRA E' O TOKEN, NAO O SEGMENTO (corrigido 2026-11-01, medido). O payload
    declara o instante por SEGMENTO, e um segmento pode ter duas palavras: no
    evento `tStartMs: 1880` do video `WdaHAGRBB6s` o unico segmento e' `">> No."`,
    e o player desenha as duas palavras juntas
    (`_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json`, quadro t=2,059).
    Contar segmentos e cortar o texto por TOKENS (`first_words`) fazia o `">>"`
    aparecer sozinho e o `"No."` esperar por um instante que nunca chegava
    porque o segmento dele ja' tinha passado -- a linha nunca completava. O
    instante de um segmento vale para todas as palavras dele.

    A SEGUNDA METADE DA MEDICAO (e a correccao do que este docstring dizia): o
    texto que o UIA entrega NAO cresce por frases. Nos 16 quadros da captura, o
    texto pintado e' IGUAL ao texto que o relogio do payload revela em 15 deles,
    e no 16.o esta' UM segmento atras, 11 ms depois do instante desse segmento
    (`_main/sim/measure-youtube-captions.py`, `uia.agree` = 15/16). O que existe
    e' uma animacao de entrada do segmento, de dezenas de milissegundos -- nao
    uma publicacao por frase. O relogio de palavra continua a ser a autoridade
    porque e' o unico numero com resolucao abaixo de 100 ms.
    """
    if t is None:
        return None
    words = (cue or {}).get("words")
    if not words:
        return None
    try:
        limit = float(t)
    except (TypeError, ValueError):
        return None
    count = 0
    for word in words:
        if not isinstance(word, dict):
            continue
        try:
            start = float(word.get("start"))
        except (TypeError, ValueError):
            continue
        if start <= limit + 1e-9:
            count += len(speech_words(str(word.get("text") or "")))
    return count


def window_by_paint(cues, hit, capacity=CAPACITY, played_t=None):
    """A JANELA que o player esta a mostrar, neste instante.

    A regra, em uma linha: a linha que o player esta a Pintar aparece ate onde
    ele ja pintou; as linhas mais antigas aparecem inteiras (o player ja as
    terminou).

    O que torna isto 1:1 por construcao: NAO existe um relogio estimado nem um
    atraso guessed. O numero de palavras reveladas vem do que o player pintou.

    A JANELA E O TRECHO DE CUES QUE O ALINHAMENTO CASOU. `align_painted`
    devolve `from_index` (o primeiro cue cujas palavras estao pintadas),
    `index` (o cue que esta a ser pintado) e `painted_from` (o offset da
    ultima palavra casada dentro de `index`). Esses tres numeros sao o que o
    player tem no ecra: as linhas do meio inteiras, a ultima cortada em
    `aligned - painted_from` palavras. Nao ha re-quebra nenhuma: a linha e o
    texto do cue, no ponto em que o YouTube a quebrou.

    A DEDUPLICACAO (o B5 do dono: *"coisa duplicada"*) e feita aqui e nao por
    `youtube_window.collapse_growth`, porque as DUAS regras colidem: a janela a
    rolar tem a linha nova a crescer como PREFIXO da antiga em alguns casos, e
    `collapse_growth` -- que guarda sempre a MAIOR -- apagaria a linha que esta a
    crescer. Aqui a regra e a outra: duas linhas IGUAIS sao uma so, e a linha
    ANTIGA e apagada quando a nova e igual a ela (o que `collapse_growth` tambem
    faz, mas SO quando a nova nao esta a crescer).

    Um `hit` SEM `from_index` (chamadores antigos) cai na janela por
    `live_cues`, que e o comportamento anterior; o caminho vivo (2026-10-29)
    passa sempre o `hit` do `align_painted`, logo usa o trecho alinhado.
    """
    cues = cues or ()
    hit_index = _as_int((hit or {}).get("index"), -1)
    from_index = _as_int((hit or {}).get("from_index"), -1)
    wanted = painted_prefix_count(hit)
    if 0 <= from_index <= hit_index < len(cues):
        rows = [row for row in rows_from_cues(cues)
                if from_index <= row["index"] <= hit_index]
        if rows:
            # O TECTO DA LINHA PINTADA e' o que a pintura diz; o PISO e' o relogio
            # de palavra da linha -- e fica a MENOR das duas, que e' a regra do
            # `_reveal_text`: nunca se mostra uma palavra que o player ainda nao
            # pintou (a pintura e' o tecto) e nunca se salta uma frase inteira de
            # uma vez (o relogio e' o piso). Com o relogio CONGELADO a pintura
            # continua a subir, e o `min` cresce com ela.
            row = next((r for r in rows if r["index"] == hit_index), None)
            if row is not None:
                clock = word_clock_count(row, played_t)
                if clock is not None:
                    cap = (min(wanted, clock) if wanted > 0 else clock)
                else:
                    cap = wanted
                # Um zero NAO corta texto nenhum (`if wanted > 0`, o
                # comportamento de sempre): o cue aparece inteiro e o `min` fica
                # para a proxima leitura.
                row["cap"] = cap or None
        return _window(rows, None, capacity)
    live = live_cues(cues, capacity)
    if not live:
        return []
    painted = painted_prefix_count(hit)
    by_index = {row["index"]: row for row in rows_from_cues(cues)}
    rows = [by_index[index] for index, _cue in live if index in by_index]
    for row in rows:
        if row["index"] == hit_index and painted > 0:
            row["cap"] = painted
    return _window(rows, None, capacity)


# ══════════════════════════════════════════════════════════════════════════════
# O MOTOR: UMA COMPUTACAO DE DESENHO, DUAS FONTES DE LINHAS
#
# O DONO, 2026-11-01, verbatim: *"tu deve entender literalmente como funciona as
# legendas do youtube e o display e as animeacoes e as quebras de linha 1:1 e
# imitar no sotto ... mesmo quando é só transcricao em tempo real, deve imitar o
# comportamento da legenda do youtube."*
#
# Ate' aqui havia DUAS regras de desenho: o caminho do YouTube (`window_by_paint`
# + `youtube_window.revealed_lines`, com o relogio do payload) e o caminho do ASR
# ao vivo (o sprout de `caption_overlay`, uma palavra a cada 45 ms de RELOGIO DE
# PAREDE, sem janela de duas linhas e sem roll-up). O dono viu a diferenca.
#
# Agora ha' UMA: `frame(rows, t)` devolve o que esta' DESENHADO num instante --
# o prefixo revelado de cada linha, a janela a rolar, o alfa da linha que sai. As
# duas fontes so' produzem `rows`, e produzem-nas com a MESMA forma:
#
#   {"text": str, "words": [{"start": s, "text": w}], "start": s,
#    "end": s|None, "cap": int|None, "index": int}
#
#   * o YouTube produz as linhas do PAYLOAD (`rows_from_cues`): cada evento e'
#     uma linha, o `tOffsetMs` de cada segmento e' o relogio da palavra, e a
#     quebra de linha e' a que ele desenhou;
#   * o ASR produz linhas a crescer (`LiveRows`): as palavras entram com o
#     instante em que CHEGARAM, um lote que chega de uma vez entra ao compasso
#     medido do YouTube (`WORD_GAP_S`) e a linha e' quebrada pela regra da
#     industria que ele ja' usa (`caption_wrap.wrap`, <= 2 linhas, nunca parte
#     uma palavra).
#
# OS NUMEROS DESTE BLOCO SAO TODOS MEDIDOS, e o instrumento e'
# `_main/sim/measure-youtube-captions.py`; a tabela completa, com a chave de cada
# numero, esta' em `docs/youtube-caption-spec.md`.

#: `wpWinPositions[1].ccCols` do payload.
COLS = 40

#: A linha mais larga dos 19 eventos do payload (`lines.chars_per_row.max`): 42
#: caracteres. E' o mesmo numero que `caption_wrap.CHAR_CEILING`, medido por outra
#: estrada -- duas medidas independentes, um valor.
MAX_CHARS = 42

#: O intervalo MEDIANO entre duas palavras do payload (69 intervalos: min 0,04 s,
#: mediana 0,24 s, max 1,08 s). E' o compasso com que um lote de ASR entra: o
#: YouTube nunca mostra tres palavras no mesmo quadro, e o ASR entrega frases.
WORD_GAP_S = 0.24

#: O ATRASO MAXIMO que a revelacao de um lote pode acumular. Um lote de N
#: palavras entra em `min(WORD_GAP_S, MAX_LAG_S/N)` por palavra, logo o ultimo
#: entra no maximo 0,36 s depois do primeiro. Sem este tecto, um lote de oito
#: palavras 0,24 s depois de chegar: 1,7 s de atraso, e a legenda fica a falar do
#: que ja' passou.
MAX_LAG_S = 0.36

#: O tempo que a linha que SAI ainda e' desenhada. NAO e' escolhido: e' o unico
#: intervalo que reproduz os 16 quadros da captura do player
#: (`rollup.exit_s_bracket_s` = 0,424 .. 0,552 s) -- e o modelo reproduz os 16.
EXIT_S = 0.45


def rows_from_cues(cues):
    """O PRODUTOR DO YOUTUBE: os cues servidos como linhas do motor.

    Cada cue e' UMA linha do player: o texto ja' vem quebrado por ele (o `\\n`
    dentro do texto e' uma quebra dele e fica), o `words` e' o relogio de cada
    palavra, e `start`/`end` sao a vida da linha.

    `index` e' o indice do cue na lista de origem: o `hit` do alinhamento e' um
    indice, e e' por ele que a janela pintada se escolhe.
    """
    rows = []
    for index, cue in enumerate(cues or ()):
        if not isinstance(cue, dict):
            continue
        text = row_text(cue.get("text"))
        if not text:
            continue
        words = []
        for word in cue.get("words") or ():
            if not isinstance(word, dict):
                continue
            start = _as_float(word.get("start"), None)
            if start is None:
                continue
            words.append({"start": start, "text": str(word.get("text") or "")})
        rows.append({
            "index": index,
            "text": text,
            "words": words,
            "start": _as_float(cue.get("start"), 0.0),
            "end": _as_float(cue.get("end"), None),
            "cap": None,
        })
    return rows


def _reveal_text(row, t):
    """O texto que a linha ja' mostra em `t`: o prefixo que os relogios revelaram.

    Duas autoridades, e a MENOR: o relogio das palavras da linha (`words`, que e'
    o do payload no YouTube e o da chegada no ASR) e o `cap` que o chamador impoe
    (no caminho do YouTube, o numero de palavras que o player ja' PINTOU -- ele e'
    o tecto por construcao). Sem relogio e sem tecto, a linha aparece inteira.
    """
    text = str(row.get("text") or "")
    count = word_clock_count(row, t)
    cap = row.get("cap")
    if cap is not None:
        count = int(cap) if count is None else min(int(cap), int(count))
    if count is None:
        return text
    return first_words(text, count)


def _drawn(rows, t, capacity=CAPACITY, rollup=ROLLUP_ROWS, exit_s=EXIT_S):
    """As linhas DESENHADAS em `t`, da mais antiga para a nova.

    Tres regras, nenhuma inventada:

      * uma linha so' existe a partir do seu `start` -- `start <= t`;
      * uma linha que ACABOU (`end`) fica mais `exit_s`, a rolar para fora;
      * das que sobram ficam as ultimas `capacity + rollup`: a janela do player
        tem `rcRows` linhas mais a que esta' a sair (`rcRows=2` + 1, medido).
    """
    keep = []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        start = _as_float(row.get("start"), 0.0)
        if t is not None and start > float(t) + 1e-9:
            continue
        end = _as_float(row.get("end"), None)
        if end is not None and t is not None and float(t) >= end + float(exit_s):
            continue
        keep.append((start, row))
    keep.sort(key=lambda pair: pair[0])
    return [row for _start, row in keep[-max(1, int(capacity) + int(rollup)):]]


def frame(rows, t, capacity=CAPACITY, rollup=ROLLUP_ROWS, exit_s=EXIT_S):
    """O DESENHO num instante -- a unica computacao, para as duas fontes.

    Devolve `[{"text", "alpha", "exiting"}]`, de cima para baixo:

      * `text`    -- a linha reveleada ate' `t` (prefixo por relogio de palavra);
      * `alpha`   -- 255 numa linha da janela; na linha que esta' a SAIR desce de
                     255 a 0 ao longo de `exit_s` (`word_fade.alpha_out`), contado
                     do instante em que a linha que a empurrou comecou -- o
                     `start` da linha `capacity` posicoes a frente. O alfa e'
                     POR LINHA: e' o `SourceConstantAlpha` de cada desenho, nao o
                     da janela inteira;
      * `exiting` -- a linha ja' saiu da janela de `capacity` e esta' a rolar.

    Uma linha com alfa 0 nao entra: desenhar zero e' nao desenhar, e o motor nao
    entrega trabalho ao renderizador que nao produz pixel.
    """
    import word_fade
    shown = _drawn(rows, t, capacity, rollup, exit_s)
    marks = []
    for index, row in enumerate(shown):
        displacer = index + int(capacity)
        displaced_at = None
        if displacer < len(shown):
            displaced_at = _as_float(shown[displacer].get("start"), None)
        text = row_text(_reveal_text(row, t))
        alpha = word_fade.FULL
        if displaced_at is not None and t is not None:
            alpha = word_fade.alpha_out(float(t) - float(displaced_at), exit_s)
            if alpha <= 0:
                continue
        if not text:
            continue
        if marks and marks[-1]["text"] == text:
            continue
        marks.append({"text": text, "alpha": alpha,
                      "exiting": displaced_at is not None})
    return marks


def _window(rows, t, capacity=CAPACITY, rollup=ROLLUP_ROWS, exit_s=EXIT_S):
    """`frame` sem os alfas -- o canal de TEXTO (as duas linhas e a que sai)."""
    return [mark["text"] for mark in frame(rows, t, capacity, rollup, exit_s)]


def rows_at(cues, t, capacity=CAPACITY):
    """A janela do YouTube pelo RELOGIO DO PAYLOAD, sem pintura nenhuma.

    E' o caminho de recurso: quando o UIA nao entrega as palavras que o player
    pinta, quem escolhe onde a linha esta' e' o `tOffsetMs` de cada palavra -- o
    MESMO relogio que o player usa.
    """
    return _window(rows_from_cues(cues), t, capacity)


class LiveRows:
    """O PRODUTOR DO ASR: a transcricao ao vivo, nas linhas do YouTube.

    O QUE ENTRA, palavra a palavra. `push(text, at)` recebe a linha que CRESCE (o
    que o ASR ja' decodificou) e o instante em que ela chegou. As palavras que ja'
    estavam ficam com o relogio delas; as novas entram a' partir de `at`, ao
    compasso medido do YouTube (`WORD_GAP_S`), com o atraso de um lote limitado a
    `MAX_LAG_S`.

    PORQUE UM COMPASSO, e nao todas de uma vez: medido nos 16 quadros do player
    (`_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json`), a linha do
    YouTube nunca ganha tres palavras no mesmo quadro -- o payload declara o
    instante de cada uma (69 de 88 palavras com `tOffsetMs`, mediana 0,24 s). O
    ASR entrega frases inteiras; sem o compasso, o Sotto punha a frase toda no
    ecra de uma vez, que e' literalmente a queixa do dono
    (*"o youtube mostra uma palavra por vez e o sotto mostra varias por vez"*).

    PORQUE UM TECTO AO ATRASO: um lote de oito palavras a 0,24 s cada punha a
    ultima 1,7 s depois. `MAX_LAG_S` comprime o lote em vez de o atrasar -- a
    legenda nunca fala do que ja' passou.

    A QUEBRA DE LINHA e' a do `wrap` que o chamador injecta (no overlay,
    `caption_wrap.wrap` com a fonte e a largura reais): o mesmo numero de linhas,
    o mesmo "nunca parte uma palavra" e o mesmo tecto de 2 linhas que o caminho
    do YouTube ja' usa. `wrap` tem de devolver TODAS as linhas do texto -- a
    janela (2 + 1) e' escolha do motor, nao do wrap.

    E O QUE NAO ACONTECE AQUI: nao ha' sprout de relogio de parede, nao ha' um
    segundo tempo para o ASR, e nao ha' re-quebra as cegas -- o `text` de cada
    linha e' fixado quando ela e' construida, e a revelacao dentro dela e' so' o
    prefixo que os relogios deixam passar.
    """

    def __init__(self, capacity=CAPACITY, rollup=ROLLUP_ROWS, gap=WORD_GAP_S,
                 lag=MAX_LAG_S, wrap=None):
        self.capacity = max(1, int(capacity))
        self.rollup = max(0, int(rollup))
        self.gap = max(0.0, float(gap))
        self.lag = max(0.0, float(lag))
        self.wrap = wrap
        self.reset()

    def reset(self, at=None):
        """Linha nova, sem historico. `at` existe para o chamador poder dizer
        QUANDO -- o motor nao le' relogio nenhum."""
        self.tokens = []
        self.words = []
        self.closed = []
        self._rows = []

    def push(self, text, at):
        """A linha CRESCEU (ou comecou outra). Devolve True quando mudou.

        A CORRECCAO NAO REINVENTA O RELOGIO: as palavras que continuam iguais no
        prefixo mantem o instante em que chegaram -- senao o modelo a corrigir
        uma palavra no fim reiniciava o relogio da frase inteira e a linha
        inteira voltava a aparecer palavra a palavra.

        UMA LINHA NOVA (a primeira palavra mudou) FECHA A ANTERIOR: as linhas dela
        ficam `capacity` linhas depois do `end` que agora lhes e' dado, para
        rolarem para fora como as do YouTube.
        """
        tokens = str(text or "").split()
        at = float(at)
        if not tokens:
            self.reset(at)
            return True
        common = 0
        while (common < len(self.tokens) and common < len(tokens)
               and self.tokens[common] == tokens[common]):
            common += 1
        if self.tokens and common == 0:
            self._close(at)
        kept = self.words[:common]
        fresh = tokens[common:]
        step = min(self.gap, (self.lag / len(fresh)) if fresh else 0.0)
        for index, word in enumerate(fresh):
            kept.append({"text": word, "start": round(at + index * step, 3)})
        self.tokens = tokens
        self.words = kept
        self._rows = self._build()
        return True

    def _close(self, at):
        """A frase anterior SAI PELA JANELA, nao pelo relogio (`end` fica None).

        MEDIDO (`_main/sim/measure-youtube-captions.py`, `rollup.*`): duas linhas do
        YouTube estao vivas AO MESMO TEMPO durante 94 % do video, e a terceira so'
        aparece nos 7,66 s de transicoes -- ou seja, uma linha nao desaparece quando
        a seguinte comeca, desaparece quando e' EMPURRADA para fora da janela. Fechar
        pelo relogio (`end = at`) fazia o contrario no caminho do ASR: as frases
        chegam com mais de `EXIT_S` entre si, logo a linha anterior ja' tinha expirado
        quando a nova comecava e o Sotto nunca mostrava TRES linhas nem rolamento
        nenhum -- 0 quadros de 3 linhas no replay de `_main/sim/youtube-caption-sim.html`
        contra 453 do caminho do YouTube.

        `at` fica no registo do fecho (quem chamar sabe quando) mas nao vira vida: a
        vida aqui e' a PROPRIA janela, como no player.
        """
        for row in self._rows[-self.capacity:]:
            closed = dict(row)
            closed["end"] = None
            closed["closed_at"] = float(at)
            self.closed.append(closed)
        self.closed = self.closed[-self.capacity:]

    def _build(self):
        """As linhas da linha ACTUAL, com o relogio de cada palavra dentro delas.

        A quebra e' do `wrap` injectado; o relogio e' contado por PALAVRAS, que e'
        como o `wrap` move o texto (palavras inteiras, nunca letras).
        """
        if not self.words:
            return []
        text = " ".join(word["text"] for word in self.words)
        lines = self.wrap(text) if self.wrap else [text]
        rows, used = [], 0
        for line in lines or ():
            size = len(str(line).split())
            chunk = self.words[used:used + size]
            used += size
            if not chunk:
                continue
            rows.append({"text": str(line), "words": [dict(w) for w in chunk],
                         "start": chunk[0]["start"], "end": None, "cap": None})
        return rows

    def rows(self):
        return list(self.closed) + list(self._rows)

    def frame(self, t):
        return frame(self.rows(), t, self.capacity, self.rollup)

    def window(self, t):
        return _window(self.rows(), t, self.capacity, self.rollup)

    def next_clock(self, t):
        """O proximo instante em que uma palavra aparece -- o unico `Timer` certo.

        `None` quando nao ha' mais nada por revelar: o chamador para de agendar.
        """
        if t is None:
            return None
        now = float(t)
        ahead = [w["start"] for row in self._rows for w in row["words"]
                 if float(w["start"]) > now + 1e-6]
        return min(ahead) if ahead else None


#: O texto que atravessa o canal do overlay. Uma linha por linha do player e o
#: terminador no FIM, mesmo com UMA linha so: `caption_overlay._layout` usa a
#: presenca de '\n' para saber que este texto JA esta quebrado e nao pode
#: voltar ao `caption_wrap.wrap_tail` (que divide por espaco e re-quebra).
ROW_END = "\n"


def rows_text(rows):
    """As linhas do player no canal de texto do overlay, uma por linha.

    O terminador final e o MARCADOR do canal: sem ele, uma janela de uma linha
    so seria indistinguivel de uma legenda normal e `_layout` voltaria a
    re-quebrar uma linha larga. Devolve "" sem linhas (o overlay esconde).
    """
    return "".join(str(row) + ROW_END for row in (rows or ()) if str(row))


def history_of(lines):
    """A janela como UMA linha de historico, sem repetir o que ja esta la.

    Mesma regra de `youtube_window.history_line`: as duas linhas do ecra sao dois
    pedacos da mesma frase a rolar, e um pedaco repetido entra uma vez so.
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
