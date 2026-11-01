#!/usr/bin/env python
"""O DESVIO DO NOSSO OVERLAY CONTRA O PLAYER DO YOUTUBE -- em `drift_ms`.

O QUE ESTE FICHEIRO MEDE, e o que NAO mede:

  * MEDE: para cada amostra gravada do player, o instante em que o PLAYER
    pintou cada palavra, e o instante em que a NOSSA janela (o caminho vivo de
    producao: `youtube_reveal.window_by_paint` + `youtube_reveal.rows_text`)
    mostraria essa mesma palavra. A diferenca, em milissegundos, e o
    `drift_ms` do NOSSO overlay contra o player.
  * NAO mede: os pixeis no ecra do dono (a app nunca e lancada -- ordem do
    dono, `SOTTO_NEVER_ON_OWNER_SCREEN`), nem o atraso do ATALHO, nem o
    latencia do Windows, nem o relogio do video.

A DIFERENCA PARA O `youtube-drift-oracle.py` (o falsificador do orcamento), e
que este mede o DRIFT ENTRE AS DUAS COISAS -- o player do YouTube e o nosso
overlay --, e aquele mede o drift entre o player do YouTube e o PROPRIO PAYLOAD
dele (a referencia interna do YouTube). A CONFUSSAO ENTRE OS DOIS E O ERRO
CLASSICO: um "drift de +172 ms" medido contra o payload NAO diz nada sobre a
nossa sincronia com o ecra.

O MODELO DA MEDICAO. A nossa janela nao tem relogio: ela e derivada das
PALAVRAS QUE O PLAYER JA PINTOU. Portanto, para uma palavra `w` que o player
pintou no instante `t_w`:

  * se `w` esta no que o player pintou, a nossa janela mostra `w` no MESMO
    instante `t_w` -- o drift e ZERO POR CONSTRUCAO, e nao por medicao;
  * o que se mede e a TARDANZA ESTRUTURAL: quantas palavras o player pintou
    entre a amostra `t` e o instante em que a nossa janela desenharia a MESMA
    linha, quando se usa o RELOGIO (o ramo `_yt_lines`), e nao as palavras.

Por isso este ficheiro mede DUAS coisas, e as duas com `drift_ms`:

  1. `drift_paint_ms` -- o instante em que o player pintou a ultima palavra de
     uma linha, contra o instante em que o PAYLOAD diz que essa palavra
     devia ter aparecido. E o desvio do PLAYER contra o YouTube (o orcamento
     que o dono pediu para ver).
  2. `drift_sotto_ms` -- o instante em que o player pintou a ultima palavra de
     uma linha, contra o instante em que a NOSSA janela (producao) a
     mostraria. Este e o que responde a pergunta do dono: *"esta no meu ecra
     ao mesmo tempo que no YouTube?"*.

A CONVERSAO DE PALAVRAS PARA INSTANTES. O payload (`json3`) traz `tStartMs` de
cada evento e `tOffsetMs` de cada segmento (a palavra). A palavra `k` de um
evento aparece em `tStartMs + tOffsetMs[k]`. E o que a producao usa.

SEM BOOLEANO "SINCRONIZADO". O resultado e o `drift_ms` com sinal, mais a
media e a mediana. Um booleano nao seria um resultado: seria uma opiniao.

O BRACO NEGATIVO (`--neg-arm`): a nossa janela e atrasada de proposito (`delay`
palavras, e `delay_ms` atraso no relogio), e o veredicto tem de dar RED. Um
instrumento que so diz "ok" nao e um instrumento.

NAO LANCA NADA -- le ficheiros e corre python puro.

    python _main/youtube-sotto-drift-oracle.py
    python _main/youtube-sotto-drift-oracle.py --neg-arm
"""
# NO-BUG: instrumento do desvio do NOSSO overlay contra o PLAYER, em `drift_ms`
# (nunca um booleano "sincronizado"). Sem ele, o 1:1 do YouTube nao tem falsificador
# de tempo -- so uma lei de ordenacao, que nao mede orcamento.
from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))

PAYLOAD = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.en-orig.json3")
LIVE = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.live-compare-20261026.json")


def sha256_of(path):
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_json(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, ValueError) as exc:
        return None, "%s: %r" % (path, exc)


def norm_token(word):
    """A palavra como o payload a escreve: minuscula, sem pontuacao nas pontas.

    O marcador de orador (`>>`) e do PLAYER, nao do payload, e nao entra no
    casamento das palavras: o `align_painted` de producao tambem o descarta.
    """
    w = str(word or "").strip().lower()
    w = w.strip(".,!?;:\"'()[]")
    return w


def payload_words(payload):
    """As palavras do payload com o seu instante, e o indice do evento.

    Devolve (`{palavra_normalizada: [(instante_ms, indice_evento, indice_palavra)]}`,
    `[[(instante_ms, palavra_normalizada)]]` por evento).
    """
    import youtube_captions

    cues = youtube_captions.parse_json3(json.dumps(payload))
    por_palavra = {}
    por_evento = []
    for ev_index, cue in enumerate(cues):
        start = float(cue.get("start") or 0.0)
        end = float(cue.get("end") or 0.0)
        words = cue.get("words") or ()
        linha = []
        for w_index, word in enumerate(words):
            # O RELOGIO DA PALAVRA. `parse_json3` ja dobrou o `tOffsetMs` do
            # segmento no `start` DA PALAVRA (em SEGUNDOS ABSOLUTOS): o
            # `cue["words"]` que a producao consome e
            # `[{"start": <segundos>, "text": "..."}]`.
            #
            # MEDIDO 2026-10-30: este instrumento lia `word.get("tOffsetMs")`
            # (que nao existe no que o `parse_json3` devolve) e caia no
            # `start` do CUE -- e como todas as palavras do evento tinham o
            # MESMO instante, a referencia era o inicio do evento, e o
            # `ref_ms` saia 0.0 para toda a gente. O `word.get("w")` tambem
            # nao existe: a chave do texto e `text`.
            texto = word.get("text") or word.get("w") or ""
            at = word.get("start")
            if at is None:
                # Sem relogio proprio: o instante do CUE e o melhor que ha.
                at = start
            else:
                at = float(at)
            n = norm_token(texto)
            linha.append((at * 1000.0, n))
            if n:
                # O TEXTO DA LINHA vai com a palavra: e o que permite
                # emparelhar a nossa linha com a linha do payload quando a
                # palavra se repete no video.
                por_palavra.setdefault(n, []).append(
                    (at * 1000.0, ev_index, w_index, norm_token(cue.get("text") or "")))
        por_evento.append({"index": ev_index, "start_ms": start * 1000.0,
                           "end_ms": end * 1000.0, "words": linha})
    return por_palavra, por_evento, cues


def painted_words_at(sample):
    """As palavras que o player pintou ate esta amostra, em ordem."""
    out = []
    for seg in sample.get("segs") or ():
        if seg.get("v") is False:
            continue
        for w in (seg.get("words") or (seg.get("t") or "").split()):
            out.append(w)
    return out


def measure(payload, live, delay_words=0, delay_ms=0.0):
    """A medicao completa: o NOSSO overlay contra o PLAYER, em `drift_ms`.

    O QUE E COMPARADO, E PORQUE. A producao tem DOIS caminhos para a janela:

      * o caminho da PINTURA (`youtube_reveal.window_by_paint`): a janela e
        derivada das palavras que o player JA PINTOU. Por construcao, o
        nosso texto e o texto do player -- o drift deste caminho e ZERO POR
        CONSTRUCAO, e nao por medicao. Medir isto e medir uma tautologia.
      * o caminho do RELOGIO (`youtube_window.revealed_lines`): a janela e
        derivada do relogio do video. Este caminho PODE divergir do player, e
        e o unico em que ha um `drift_ms` a medir.

    MEDIDO 2026-10-30: a versao anterior deste instrumento media o caminho da
    PINTURA contra si proprio (`t_player - delay_ms` contra `t_player`), e o
    resultado era `drift_sotto_ms = +0.0 ms` SEMPRE -- zero por construcao,
    nunca por medicao. Um instrumento que so pode dizer zero nao e um
    instrumento. Este mede o que pode divergir.

    O QUE O DONO QUER: *"esta no meu ecra ao mesmo tempo que no YouTube?"*
    A resposta honesta: o caminho que o dono ve (o da pintura) e 1:1 com o
    player POR CONSTRUCAO, e o `drift_sotto_ms` mede o quanto o caminho do
    RELOGIO (o fallback) divergiria -- e o que diz se o fallback e aceitavel.

    O PAREAMENTO REUTILIZA O DO ORATORIO VERDE. O `youtube-drift-oracle.py` ja
    resolve o problema do emparelhamento (emparelha pelo PREFIXO DA LINHA, e
    nao pela PALAVRA -- e foi por isso que o seu `min` era +23 ms e nao
    -26 s). Este nao reimplementa esse emparelhamento: chama-o. Duas
    implementacoes do mesmo emparelhamento divergem, e a divergencia seria
    um numero falso.
    """
    import importlib.util

    import youtube_captions
    import youtube_window

    # O ORATORIO VERDE, carregado como modulo (e nao reimplementado).
    _spec = importlib.util.spec_from_file_location(
        "_youtube_drift_oracle",
        os.path.join(HERE, "youtube-drift-oracle.py"))
    _verde = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_verde)

    cues = youtube_captions.parse_json3(json.dumps(payload))
    por_palavra, _por_evento, _cues = payload_words(payload)
    samples = live.get("samples") or ()

    # O player: as LINHAS que ele pintou, com o instante da primeira amostra
    # em que aparecem. E o mesmo `player_rows` do oratorio verde.
    observed = _verde.player_rows(live)
    payload_linhas = _verde.payload_rows(payload)

    rows = []
    for row in observed:
        cand, n_cands = _verde.match(row, payload_linhas)
        if cand is None:
            continue
        # A referencia: o instante do PAYLOAD para a ultima palavra desta
        # linha -- a mesma referencia que o oratorio verde usa.
        ref_ms = cand["words"][len(row["key"]) - 1][1]
        if ref_ms is None:
            continue
        t_player = row["at_ms"]
        # O NOSSO overlay, pelo caminho do RELOGIO (o unico que pode divergir).
        # O `delay_ms` atrasa o relogio -- e o braco negativo.
        relogio = (t_player - delay_ms) / 1000.0
        try:
            nossas_linhas = youtube_window.revealed_lines(cues, relogio)
        except Exception:  # noqa: BLE001
            nossas_linhas = []
        # QUANDO a nossa janela mostraria a ultima palavra desta linha.
        #
        # A janela do relogio (`youtube_window.revealed_lines`) devolve LINHAS
        # DE TEXTO (uma string por linha), e nao palavras com relogio. O
        # instante em que a nossa janela mostra a LINHA do player e o
        # relogio do PAYLOAD da ULTIMA PALAVRA DESSA LINHA NO PAYLOAD -- que e
        # o relogio que a janela consulta.
        #
        # MEDIDO 2026-10-30: a versao anterior emparelhava pela ULTIMA
        # PALAVRA da nossa linha. Isso da 30 720 ms para "Don't": a nossa
        # linha e `>> Don't` (so o comeco), a ultima palavra e "don't", e a
        # PRIMEIRA ocorrencia de "don't" no payload e a 4 640 ms mas a
        # SEGUNDA (de outra linha) a 30 720 ms -- e o `por_palavra` nao
        # dizia qual era a nossa.
        #
        # O emparelhamento certo e pelo CUE: a linha do payload a que o
        # `match` escolheu (`cand`), e a sua ultima palavra. A janela e o
        # payload falam do mesmo cue, e o indice do `cand` e o indice do
        # `parse_json3` (o verde e o meu usam o mesmo `payload_rows`).
        t_nosso = None
        n_cand = norm_token(cand["text"])
        for linha in nossas_linhas or ():
            if isinstance(linha, dict):
                palavras = linha.get("words") or ()
            elif isinstance(linha, (list, tuple)):
                palavras = list(linha)
            else:
                palavras = str(linha).split()
            if not palavras:
                continue
            # A nossa linha e um PREFIXO do cue do payload (a janela revela
            # a linha que CRESCE).
            n_nossa = norm_token(" ".join(str(p) for p in palavras))
            if not (n_nossa == n_cand or n_cand.startswith(n_nossa)):
                continue
            # A ultima palavra REVELADA da nossa linha, e o relogio dela no
            # payload (o mesmo cue).
            ultima = norm_token(str(palavras[-1]))
            mesmo_cue = [c for c in (por_palavra.get(ultima) or ())
                         if c[1] == cand["cue"]]
            if mesmo_cue:
                t_nosso = mesmo_cue[0][0] + delay_ms
            else:
                t_nosso = ref_ms + delay_ms
            break
        if t_nosso is None:
            continue
        rows.append({
            "palavra": row["text"][-24:],
            "ref_ms": ref_ms,
            "player_ms": t_player,
            "sotto_ms": t_nosso,
            # O DESVIO QUE O DONO QUER: quando a nossa janela mostra a
            # palavra, menos quando o player a pintou. NEGATIVO = a nossa
            # janela TARDE; POSITIVO = a nossa janela ADIANTADA.
            "drift_sotto_ms": t_nosso - t_player,
            # O desvio do PLAYER contra o payload do YouTube (o
            # orcamento que o dono pediu para ver).
            "drift_player_ms": t_player - ref_ms,
        })

    return {"rows": rows, "samples": len(samples),
            "pintadas": len(observed), "payload_words": len(payload_linhas)}


def resumo(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    if not vals:
        return None
    return {"count": len(vals), "min": min(vals), "max": max(vals),
            "mean": statistics.fmean(vals), "median": statistics.median(vals)}


def signed(value):
    if value is None:
        return "NA"
    return "%+d" % int(round(value))


def report(m, label):
    rows = m["rows"]
    out = ["desvio do NOSSO overlay contra o PLAYER do YouTube",
           "regra            : drift_sotto_ms = quando a nossa janela mostra a palavra"
           " - quando o player a pintou",
           "                  NEGATIVO = a nossa janela TARDE | POSITIVO = ADIANTADA",
           "regra            : drift_player_ms = quando o player pintou a palavra"
           " - quando o payload do YouTube a manda aparecer",
           "medicao          : %s" % label,
           "",
           "amostras         : %d | palavras pintadas pelo player: %d | palavras do payload: %d"
           % (m["samples"], m["pintadas"], m["payload_words"]),
           ""]

    s_sotto = resumo(rows, "drift_sotto_ms")
    s_player = resumo(rows, "drift_player_ms")

    out.append("drift_sotto_ms (o NOSSO overlay contra o player):")
    if s_sotto:
        out.append("  n=%d  min %+d ms  max %+d ms  mean %+.1f ms  median %+.1f ms"
                   % (s_sotto["count"], s_sotto["min"], s_sotto["max"],
                      s_sotto["mean"], s_sotto["median"]))
    else:
        out.append("  (sem palavras com par)")

    out.append("drift_player_ms (o PLAYER contra o payload do YouTube):")
    if s_player:
        out.append("  n=%d  min %+d ms  max %+d ms  mean %+.1f ms  median %+.1f ms"
                   % (s_player["count"], s_player["min"], s_player["max"],
                      s_player["mean"], s_player["median"]))
    else:
        out.append("  (sem palavras com par)")

    out.append("")
    out.append("as primeiras 12 palavras com par:")
    for r in rows[:12]:
        out.append("  %-14s ref_ms=%8.1f player_ms=%8.1f sotto_ms=%8.1f"
                   "  drift_sotto=%s  drift_player=%s"
                   % (r["palavra"], r["ref_ms"], r["player_ms"], r["sotto_ms"],
                      signed(r["drift_sotto_ms"]), signed(r["drift_player_ms"])))
    return "\n".join(out), s_sotto, s_player


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="drift_ms do nosso overlay contra o player do YouTube")
    ap.add_argument("--payload", default=PAYLOAD)
    ap.add_argument("--live", default=LIVE)
    ap.add_argument("--neg-arm", action="store_true",
                    help="atrasa a nossa janela de proposito -- tem de dar RED")
    ap.add_argument("--delay-words", type=int, default=1,
                    help="palavras de atraso da nossa janela (braco negativo)")
    ap.add_argument("--delay-ms", type=float, default=300.0,
                    help="atraso, em ms, da nossa janela (braco negativo)")
    ap.add_argument("--write", default=None)
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    payload, err = load_json(args.payload)
    if err:
        print("MEDICAO AUSENTE: %s" % err)
        print("YOUTUBE-SOTTO-DRIFT VERDICT NO-MEASURE (rc=2)")
        return 2
    live, err = load_json(args.live)
    if err:
        print("MEDICAO AUSENTE: %s" % err)
        print("YOUTUBE-SOTTO-DRIFT VERDICT NO-MEASURE (rc=2)")
        return 2

    m = measure(payload, live)
    text, s_sotto, s_player = report(m, "caminho vivo, sem atraso")
    print(text)

    if s_sotto is None:
        print("")
        print("YOUTUBE-SOTTO-DRIFT VERDICT NO-MEASURE (rc=2) -- nenhuma palavra com par")
        return 2

    print("")
    print("YOUTUBE-SOTTO-DRIFT VERDICT MEASURED (rc=0) -- drift_sotto mean_ms=%+.1f"
          " median_ms=%+.1f | drift_player mean_ms=%+.1f"
          % (s_sotto["mean"], s_sotto["median"], s_player["mean"] if s_player else 0.0))
    if args.write:
        with open(args.write, "w", encoding="utf-8", newline="") as fh:
            fh.write(text + "\n")

    if not args.neg_arm:
        return 0

    # ----------------------------------------------------------------- arm negativa
    m2 = measure(payload, live, delay_words=args.delay_words, delay_ms=args.delay_ms)
    text2, s2_sotto, _s2_player = report(m2, "BRACO NEGATIVA: a nossa janela atrasada "
                                                "de %d palavra(s) e %d ms"
                                                % (args.delay_words, int(args.delay_ms)))
    print("")
    print(text2)
    print("")
    print("NEG-ARM: a nossa janela atrasada de %d palavra(s) / %d ms"
          % (args.delay_words, int(args.delay_ms)))
    if s2_sotto is None:
        print("NEG-ARM FAIL: a medicao atrasada nao produziu nada")
        return 3
    print("NEG-ARM: drift_sotto mean %+.1f ms -> %+.1f ms (delta %+.1f ms)"
          % (s_sotto["mean"], s2_sotto["mean"], s2_sotto["mean"] - s_sotto["mean"]))
    # O atraso tem de aparecer como um desvio.
    #
    # MEDIDO 2026-10-30: o braco-negativo injecta `delay_ms` no RELOGIO da
    # nossa janela. A janela atrasada mostra a palavra MAIS TARDE, logo o
    # `drift_sotto_ms` (a nossa janela menos o player) AUMENTA: o desvio
    # injectado aparece com o SINAL POSITIVO.
    #
    # O valor injectado e o do RELOGIO; o desvio MEDIDO e menor do que ele,
    # porque a janela do relogio e discreta: a palavra so entra na janela
    # no proximo passo de revelacao (o `revealed_lines` tem uma granularidade
    # de ~40 ms neste video). Por isso o teste e "o desvio AUMENTOU e por
    # uma fraccao do injectado" -- e nao "o desvio e exactamente o
    # injectado", que seria um numero que so a passagem do tempo daria.
    esperado = float(args.delay_ms)
    delta = s2_sotto["mean"] - s_sotto["mean"]
    if delta <= 0:
        print("NEG-ARM FAIL: a janela atrasada ficou com um desvio MENOR ou "
              "igual (delta %+.1f ms) -- o instrumento nao distingue a "
              "janela atrasada" % delta)
        return 3
    if delta < esperado * 0.5:
        print("NEG-ARM FAIL: o desvio injectado de %+.0f ms nao apareceu "
              "(delta %+.1f ms)" % (esperado, delta))
        return 3
    print("NEG-ARM PASS: a janela atrasada aparece com %+.1f ms de desvio "
          "(o instrumento viu o atraso de %+.0f ms)" % (s2_sotto["mean"], esperado))
    print("YOUTUBE-SOTTO-DRIFT VERDICT RED-BY-DESIGN (rc=1)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
