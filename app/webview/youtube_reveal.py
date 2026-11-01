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
    """
    if count <= 0:
        return ""
    left = int(count)
    out = []
    for line in str(text or "").splitlines():
        words = line.split()
        if not words:
            continue
        take = words[:left]
        left -= len(take)
        if take:
            out.append(" ".join(take))
        if left <= 0 or len(take) < len(words):
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
    """Quantas palavras do CUE o relogio do PROPRIO YouTube ja' revelou em `t`.

    DEVOLVE `None` QUANDO NAO HA' RELOGIO -- e um `None` aqui nao e um zero: um
    cue sem `words` nao revelou palavras nenhumas nem todas, simplesmente nao
    declarou o instante de cada uma, e quem chama tem de cair na outra regra.

    PORQUE E' QUE ISTO EXISTE (medido 2026-10-30 nos 16 quadros do artefacto
    `_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json`): o texto que o
    UIA entrega cresce por FRASES, nao por palavras -- em t=0,772 s ele ja' traz
    `"Have you ever had"` (quatro palavras) quando o player acabou de revelar a
    segunda. A acessibilidade do YouTube publica o texto da linha com a
    animacao CSS ja' aplicada por cima; a fronteira de PALAVRA nao esta' no
    texto, esta' no relogio de cada palavra (`tOffsetMs` no payload). Um prefixo
    contado em palavras sobre esse texto salta de tres em tres, e foi isso que o
    dono viu: *"o youtube mostra uma palavra por vez e o sotto mostra varias por
    vez"*.
    """
    words = (cue or {}).get("words")
    if not words or t is None:
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
            count += 1
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
    if 0 <= from_index <= hit_index < len(cues):
        wanted = painted_prefix_count(hit)
        out = []
        for index in range(from_index, hit_index + 1):
            cue = cues[index]
            if not isinstance(cue, dict):
                continue
            text = str(cue.get("text") or "")
            if index == hit_index:
                # A PALAVRA, NAO A FRASE (2026-10-30). Duas evidencias dizem
                # onde o player esta' dentro do cue:
                #   * a PINTURA, que e' o que o UIA entrega -- e que so' muda a
                #     cada FRASE (medido: t=0,77 s ja' traz 4 palavras);
                #   * o RELOGIO DE PALAVRA do payload (`words[].start`), que e'
                #     o mesmo que a animacao do YouTube usa.
                # Fica a MENOR das duas: nunca se mostra uma palavra que o
                # player ainda nao pintou (a pintura e' o teto), e nunca se
                # salta uma frase inteira de uma vez (o relogio e' o piso).
                # Com o relogio CONGELADO a pintura continua a subir, e o
                # `min` cresce com ela -- por isso esta combinacao nao regride
                # para o beco sem saida de 2026-10-23.
                clock = word_clock_count(cue, played_t)
                if clock is not None and wanted > 0:
                    wanted = min(wanted, clock)
                elif clock is not None:
                    wanted = clock
                if wanted > 0:
                    text = first_words(text, wanted)
            text = row_text(text)
            if not text:
                continue
            if out and out[-1] == text:
                continue
            out.append(text)
        # `capacity` e o numero de linhas VIVAS (`rcRows`); a que sai fica
        # mais `ROLLUP_ROWS` instantes, como no player (medido: 3 linhas).
        return out[-max(1, int(capacity) + ROLLUP_ROWS):]
    live = live_cues(cues, capacity)
    if not live:
        return []
    painted = painted_prefix_count(hit)
    out = []
    for index, cue in live:
        text = str(cue.get("text") or "")
        if index == hit_index and painted > 0:
            text = first_words(text, painted)
        text = row_text(text)
        if not text:
            continue
        if out and out[-1] == text:
            continue
        out.append(text)
    return out


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
