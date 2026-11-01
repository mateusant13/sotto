#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: check do objectivo do dono "linha/quebra de linha 1:1": mede as LINHAS
# que o player pinta contra as linhas que o caminho vivo produz e desenha.
"""YOUTUBE-ROWS -- as LINHAS do player contra as linhas que o Sotto desenha.

O DONO, verbatim:

    *"tem que bater timing, linha/quebra de linha e etc, 1:1."*
    *"e pra surgir palavras, quebrar linhas, usar o timing de nova linha ou nao,
    igual o youtube."*

O ELEMENTO QUE FALHAVA, medido em 2026-10-26 por `yt-break-position-probe.py`:
em 12 das 16 amostras gravadas o overlay quebrava a linha numa palavra diferente
da do YouTube, e em uma (t=6,884 s) uma linha que o player mostrava nao existia
no ecra do Sotto. A causa nao era a medida: era o CANAL. `_tick` guardava
`lines[-1]`, o overlay recebia UM texto, e `caption_wrap.wrap_tail` dividia por
espaco -- a quebra do player era destruida antes de chegar ao desenho.

O QUE ESTE FICHEIRO MEDE, e com que funcoes de PRODUCAO:

  1. `youtube_captions.parse_json3` le o payload real (a faixa `en-orig` de
     `WdaHAGRBB6s`);
  2. as palavras que o player pintou sao as linhas visiveis gravadas no
     artefacto (`samples[].segs`, com `o`/`v`), exactamente como o UIA as leria;
  3. `youtube_captions.align_painted` alinha essas palavras com os cues e
     devolve o TRECHO (`from_index`, `index`, `painted_from`) -- a fonte da
     janela;
  4. `youtube_reveal.window_by_paint` monta as linhas do player (as do meio
     inteiras, a ultima ate onde ele pintou);
  5. `sotto_webview.clean_external_text` limpa o marcador `>>` de CADA linha,
     como o `external_caption` faz;
  6. `youtube_reveal.rows_text` leva-as pelo canal de texto do overlay;
  7. `caption_overlay._layout` -- o MESMO layout que `_premultiplied_bitmap`
     desenha -- devolve as linhas que vao para o ecra.

O veredicto por amostra tem QUATRO arms (as duas primeiras de 2026-10-29, as
duas ultimas da mesma data, por outra lane):

  * `rows` -- as linhas que `window_by_paint` produz contra as do player,
    alimentando a producao com as linhas VISIVEIS (o modelo da caixa);
  * `draw` -- as linhas que `_layout` desenha contra as do player (o modelo
    da caixa);
  * `dom` -- as linhas que a producao produz quando o que lhe chega sao TODOS
    os segmentos do DOM -- e o que o UIA entrega (`_painted_children` le os
    filhos do elemento desenhado, incluindo o segmento que rola para fora da
    caixa; nao ha filtro de `v` nem de opacidade);
  * `text` / `breaks` -- o TEXTO e a QUEBRA sao medidas em separado, na mesma
    janela: duas linhas podem ter as mesmas palavras e a quebra noutra palavra.

A arm `dom` e a que espelha o caminho VIVO: o `_tick` do overlay recebe o que
`window_by_paint(cues, hit)` devolveu com o `hit` do UIA. A arm `rows` (de
2026-10-29) alimenta a producao com menos linhas do que o UIA lhe da, e por
isso em 1 das 16 amostras (t=8,264 s) o resultado dela NAO e o que a app
desenha; fica como esta porque o numero dela (16/16) e o modelo da CAIXA
visivel, e as duas leituras dizem coisas diferentes de proposito.

Uma amostra pode passar a `rows` e falhar a `draw`: e o overlay a re-quebrar.
Pode falhar a `rows`: e a janela (o alinhamento/a capacidade) a perder linhas.

    python _main\\youtube-rows-oracle.py                 # rc 0 verde, 1 vermelho
    python _main\\youtube-rows-oracle.py --neg-arm       # rc 1 POR DESENHO
    python _main\\youtube-rows-oracle.py --neg-arm draw  # parte so a arm draw
    python _main\\youtube-rows-oracle.py --neg-arm drop-older  # deita fora a linha antiga
    python _main\\youtube-rows-oracle.py --neg-arm rewrap      # mesmas palavras, quebra movida
    python _main\\youtube-rows-oracle.py --neg-arm text        # uma palavra a menos
    python _main\\youtube-rows-oracle.py --neg-arm shape       # linhas passadas como palavras

O BRACO NEGATIVO faz o que o caminho antigo fazia: achata as linhas do player
numa string so (`history_of`) e deixa o `_layout` voltar a chamar o
`caption_wrap`. Se o instrumento continuasse verde com isso, nao media nada.

Os bracos `drop-older`, `rewrap` e `text` atacam a arm `dom` -- a entrada que o
caminho vivo tem -- e cada um tem de deixar VERMELHA a arm que nomeia:

  * `drop-older` -- o `_tick` antigo (`lines[-1]`): `dom` e a linha antiga caem;
  * `rewrap`     -- o `caption_wrap.wrap_tail`: o TEXTO fica igual (16/16) e SO
                    a quebra cai -- e a prova de que as duas arms sao medidas
                    em separado;
  * `text`       -- uma palavra a menos: cai o texto (e as quebras com ele);
  * `shape`      -- a FORMA da entrada: as linhas do player passadas como se
                    fossem palavras. `painted_words` devolve PALAVRAS, e o
                    alinhador trata cada item como uma palavra; a arm `shape`
                    existe para a entrada errada nao poder passar despercebida
                    (uma linha de uma palavra so e indistinguivel, e por isso
                    esse caso nao cai).

Um braco negativo que NAO consegue partir a arm que nomeia sai com rc 2, e nao
com o rc 1 do "RED as designed": um instrumento cego nao pode ser confundido
com um instrumento que viu.

NAO LANCA A APP, nao abre janela, nao toca no player: o GDI+ e chamado em
processo, como o `yt-break-position-probe.py` ja faz. NAO PROVA OS PIXEIS: prova
as linhas que o layout entrega ao bitmap; a composicao/efeitos do Windows e a
captura do ecra do dono ficam por medir.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WEBVIEW = os.path.join(REPO, "app", "webview")
for _path in (REPO, WEBVIEW):
    if _path not in sys.path:
        sys.path.insert(0, _path)

FIXTURE = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.en-orig.json3")
LIVE = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.live-compare-20261026.json")
SHELL = os.path.join(WEBVIEW, "sotto_webview.py")
OVERLAY = os.path.join(WEBVIEW, "caption_overlay.py")

#: A geometria do sitio onde o dono ve a legenda (a mesma de 2026-10-17 e do
#: `yt-break-position-probe.py`): area de 1920 px, escala 1.0, sem tema.
WORK_WIDTH = 1920
SCALE = 1.0

#: A mesma exclusao do `segs_text` de 2026-10-26: a linha que sai vai a 0 e a
#: que rola para fora fica fora do rect da janela. `v` ja e o teste do rect.
MIN_OPACITY = 0.05


def norm(text):
    """O texto como o ecra o mostra: espacos normalizados, marcador `>>` fora.

    O `>>` e o marcador do PLAYER (o "speaker" das legendas automaticas) e o
    shell tira-o antes de pintar (`clean_external_text`), logo a comparacao
    tem de o tirar dos dois lados -- senao a arm media o marcador, nao a linha.
    """
    out = re.sub(r"^\s*(?:[>\u00bb\u203a]+\s*)+", "", str(text or ""))
    return " ".join(out.split())


def visible_rows(sample):
    """As linhas que o player PINTA na amostra, na ordem do DOM.

    Uma leitura, tres exclusoes medidas (as mesmas de `segs_text`): opacidade
    <= 0,05 (a linha a sair), `v` falso (a linha que rola para fora do rect) e
    a janela de dica do CC, que nao tem `lang` (o filtro so vale quando alguma
    linha traz `l`, para uma mudanca do YouTube nao apagar a medicao inteira).
    """
    items = [it for it in (sample.get("segs") or ()) if isinstance(it, dict)]
    if any((it.get("l") or "") for it in items):
        items = [it for it in items if (it.get("l") or "")]
    rows = []
    for item in items:
        try:
            opacity = float(item.get("o") if item.get("o") is not None else 1.0)
        except (TypeError, ValueError):
            opacity = 1.0
        if opacity <= MIN_OPACITY:
            continue
        if item.get("v") is False:
            continue
        text = " ".join(str(item.get("t") or "").split())
        if text:
            rows.append(text)
    return rows


def dom_rows(sample):
    """TODOS os segmentos do DOM, na ordem em que o UIA os le.

    O `_painted_children` (`youtube_captions.py`) le o `CurrentName` dos filhos
    do elemento `caption-window` que esta a ser DESENHADO. Nao ha filtro de
    opacidade nem de rect: o segmento que o YouTube empurrou para fora da caixa
    continua a ser um filho e continua a chegar a app. Por isso esta e a entrada
    que espelha o caminho vivo -- e nao a `visible_rows`, que responde a outra
    pergunta ("o que cabe na caixa").

    O marcador `>>` fica aqui, como no UIA; a comparacao tira-o dos dois lados
    com `norm`.
    """
    out = []
    for item in sample.get("segs") or ():
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("t") or "").split())
        if text:
            out.append(text)
    return out


def joined(rows):
    """As linhas como um texto so, com as palavras na ordem do ecra."""
    return " ".join(" ".join(str(row).split()) for row in (rows or ()))


def break_offsets(rows):
    """ONDE a janela quebra: o numero de PALAVRAS antes de cada quebra.

    `['ab', 'cd ef']` -> `[1]`: a quebra cai depois da primeira palavra. Duas
    janelas com o mesmo texto e quebras diferentes (o caso que o
    `caption_wrap.wrap_tail` produzia) dao listas diferentes -- e e isso que a
    arm `breaks` mede, sem olhar ao texto (a arm `text` mede o texto).
    """
    offsets = []
    total = 0
    rows = [row for row in (rows or ()) if str(row).strip()]
    for row in rows[:-1]:
        total += len(str(row).split())
        offsets.append(total)
    return offsets


def rewrap(rows):
    """O braco negativo da QUEBRA: mesmas palavras, quebra noutra palavra.

    Parte a ULTIMA linha que tem mais de uma palavra em duas, sem mexer nas
    palavras nem no marcador `>>` (que so pode ficar no INICIO da primeira
    linha: move-lo mudava o TEXTO depois do `norm`, e o braco deixava de isolar
    a quebra). Devolve as linhas como estao quando nenhuma se pode partir.
    """
    rows = [str(row) for row in (rows or ())]
    for pos in range(len(rows) - 1, -1, -1):
        words = rows[pos].split()
        # O `>>` so pode ficar no inicio da linha: partir ANTES dele deixava
        # uma linha que o `norm` apagava e o texto mudava.
        start = 0
        while start < len(words) and set(words[start]) <= set(">\u00bb\u203a"):
            start += 1
        if len(words) - start < 2:
            continue
        cut = start + (len(words) - start) // 2
        return (rows[:pos] + [" ".join(words[:cut]), " ".join(words[cut:])]
                + rows[pos + 1:])
    return rows


def dropword(rows):
    """O braco negativo do TEXTO: tira uma palavra, sem lhe mexer nas quebras."""
    rows = [str(row) for row in (rows or ())]
    for pos in range(len(rows) - 1, -1, -1):
        words = rows[pos].split()
        start = 0
        while start < len(words) and set(words[start]) <= set(">\u00bb\u203a"):
            start += 1
        if len(words) - start < 2:
            continue
        words.pop()
        return rows[:pos] + [" ".join(words)] + rows[pos + 1:]
    return rows


def reconstructed_hit(cues, painted):
    """O `hit` do `align_painted` para a amostra que o limiar dele recusa.

    `align_painted` exige 3 palavras exactas (`_ALIGN_MIN_EXACT`); a primeira
    amostra do video (t=0,023 s) tem UMA palavra pintada ("Have") e por isso
    nao tem `hit` de producao. A evidencia continua a nomear a cue, e este
    construtor recupera `from_index`/`index`/`painted_from` do MESMO trecho
    achatado que o alinhador percorre. Nao e usado para as linhas: e o
    substituto da leitura UIA nessa amostra, e vai marcado como `reconstructed`
    no relatorio para nao se confundir com o alinhamento de producao.
    """
    low = [str(word).lower() for word in painted]
    flat = []
    for cue_index, cue in enumerate(cues or ()):
        for word_index, word in enumerate(str(cue.get("text") or "").split()):
            flat.append((cue_index, word_index, word.lower()))
    for start in range(0, len(flat) - len(low) + 1):
        if [item[2] for item in flat[start:start + len(low)]] != low:
            continue
        end = start + len(low) - 1
        first_cue = flat[start][0]
        last_cue = flat[end][0]
        take = 0
        for item in reversed(flat[start:end + 1]):
            if item[0] != last_cue:
                break
            take += 1
        cue = cues[last_cue]
        return {
            "index": last_cue,
            "from_index": first_cue,
            "painted_from": len(low) - take,
            "aligned": len(low),
            "exact": len(low),
            "partial": False,
            "cue": cue,
            "text": str((cue or {}).get("text") or "").strip(),
        }
    return None


def overlay_rows(rows, flatten=False):
    """As linhas que o overlay DESENHA, pelo caminho de producao do desenho.

    `flatten=True` e o braco negativo da arm `draw`: junta as linhas com um
    espaco (sem o terminador de linha) e deixa o `_layout` chamar o
    `caption_wrap` como antes do canal de linhas.
    """
    import caption_overlay
    import youtube_reveal
    import sotto_webview

    clean = [sotto_webview.clean_external_text(row) for row in (rows or ())]
    clean = [row for row in clean if row]
    text = " ".join(clean) if flatten else youtube_reveal.rows_text(clean)
    # O ESTADO DO `set_text(instant=True)`: a janela do player ja' vem revelada, logo
    # nao ha' prefixo nenhum a calcular. A `_display_text` e' chamada SEM janela (so
    # le' `text`), para a medicao passar pelo MESMO ponto que o `_update` usa antes do
    # `_layout`. O sprite de `_shown`/`_n` morreu em 2026-11-01 (o motor
    # `youtube_reveal.LiveRows` revela a linha AO VIVO); aqui ficou so' o texto.
    view = type("_View", (), {})()
    view.text = text
    shown = caption_overlay.NativeCaptionOverlay._display_text(view)
    cur_lines, _prev, width, height, scrolled = caption_overlay._layout(
        shown, "", SCALE, WORK_WIDTH)
    return {
        "rows": [line for line in cur_lines if line],
        "clean": clean,
        "text": shown,
        "width": width,
        "height": height,
        "scrolled": scrolled,
    }


def clipped_rows(rows):
    """As linhas que nao cabem na largura DESENHAVEL, com essa largura.

    O canal de linhas NAO re-quebra: uma linha mais larga do que a area da
    placa e cortada na borda direita pelo GDI+ (`StringFormatFlags.NoWrap` no
    rect do `_premultiplied_bitmap`). Isto diz QUAIS seriam cortadas -- o
    canal nunca as parte noutra palavra e chama a isso 1:1.
    """
    import caption_overlay

    geo = caption_overlay._geom(SCALE, None)
    max_text = max(1.0, WORK_WIDTH - geo["x_text"] - geo["pad_r"])
    face = caption_overlay._THEME_DEFAULT
    out = []
    for row in rows or ():
        measure = caption_overlay._measure(
            row, geo["cur_px"], caption_overlay._MEASURE_CACHE,
            face["fontFamily"], face["liveWeight"] >= 600, face["liveItalic"])
        if measure(row) > max_text:
            out.append(row)
    return out, max_text


def tick_arm():
    """O `_tick` do watcher entrega TODAS as linhas -- comportamento, nao texto.

    Constroi o watcher real (`ExternalCaptionWatcher`) com um shell de mentira e
    alimenta-o com a janela que `_youtube` devolve. O `lines[-1]` antigo dava um
    call com UMA linha; o canal novo tem de dar as duas, e o `final` da linha
    antiga tem de levar as linhas ANTIGAS (senao o ecra pisca uma linha so).
    Nao arranca a thread, nao le UIA, nao abre janela.
    """
    import sotto_webview

    calls = []

    class Shell:
        external_captions_available = False
        external_captions_active = False
        visible = True
        _caption_window_shown = False

        def external_caption(self, text, source, final=False, instant=False, rows=None):
            calls.append((text, bool(final), bool(instant), list(rows or ())))

    watcher = sotto_webview.ExternalCaptionWatcher(Shell())
    watcher._tick([("external:youtube:track", ["row one", "row two"])], True)
    got_new = calls[-1] if calls else None
    ok_new = got_new == ("row two", False, True, ["row one", "row two"])
    calls.clear()
    watcher._tick([("external:youtube:track", ["row one", "row two!"])], True)
    ok_final = (len(calls) == 2
                and calls[0] == ("row two", True, True, ["row one", "row two"])
                and calls[1] == ("row two!", False, True, ["row one", "row two!"]))
    calls.clear()
    watcher._tick([("external:page", ["page line"])], False)
    ok_page = (bool(calls) and calls[-1][0] == "page line"
               and calls[-1][3] == [])
    return ok_new and ok_final and ok_page, got_new, list(calls)


def _src(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def wiring_faltas():
    """As ancoras do caminho vivo: sem elas as linhas nao chegam ao desenho.

    Nao e o mesmo que o `reveal-wired` do `youtube-1to1-oracle.py` (que a
    chamada exista): aqui cada elo do canal e nomeado -- a janela, o `_tick`
    a entregar TODAS as linhas, o `rows_text` no push, e o `_layout`/
    `_display_text` do overlay a respeitarem o canal.
    """
    shell = _src(SHELL)
    overlay = _src(OVERLAY)
    checks = (
        ("a janela por pintura esta no ramo painted",
         "youtube_reveal.window_by_paint(", shell),
        ("o _tick entrega todas as linhas",
         "rows = list(lines) if (yt_mode and lines) else None", shell),
        ("o push leva as linhas pelo rows_text",
         "youtube_reveal.rows_text(rows)", shell),
        ("o _layout nao re-quebra o canal de linhas",
         "if _cw and '\\n' not in text:", overlay),
        ("o _display_text nao inventa um corte na janela do player",
         "return self.text", overlay),
    )
    return [name for name, needle, src in checks if needle not in (src or "")]


def hit_for(cues, painted):
    """O `hit` de producao, ou o reconstruido quando o limiar o recusa."""
    import youtube_captions

    try:
        hit = youtube_captions.align_painted(cues, painted)
    except Exception:  # noqa: BLE001 -- um hit ausente e NO-VERDICT, nao um verde
        hit = None
    if hit is not None:
        return hit, "align"
    return reconstructed_hit(cues, painted), "reconstructed"


def measure(cues, samples, neg=None):
    """Compara, amostra a amostra, as linhas do player com as do caminho vivo.

    Duas ENTRADAS de proposito: `visible` (o que cabe na caixa -- as arms de
    2026-10-29) e `dom` (todos os segmentos, como o UIA os entrega -- a arm
    `dom`, 2026-10-29b). As duas comparacoes ficam na mesma amostra porque a
    diferenca entre elas E um facto medido (1/16: a linha que rola para fora).
    """
    import youtube_captions
    import youtube_reveal

    results = []
    for sample in samples:
        visible = visible_rows(sample)
        dom = dom_rows(sample)
        if not visible and not dom:
            continue
        painted = " ".join(visible).split()
        hit, how = hit_for(cues, painted)
        result = {"t": sample.get("t"), "youtube": [norm(x) for x in visible],
                  "youtube_dom": [norm(x) for x in dom],
                  "hit": how, "scrolled": "", "clipped": [], "max_text": 0.0}
        if hit is None:
            result.update({"rows": [], "draw": [], "rows_ok": False,
                           "draw_ok": False, "verdict": "NO-HIT",
                           "dom": [], "dom_draw": [], "dom_hit": how,
                           "dom_ok": False, "dom_draw_ok": False,
                           "dom_verdict": "NO-HIT", "text_ok": False,
                           "breaks_ok": False, "shape_ok": True,
                           "older_ok": False,
                           "visible_ok": False})
            results.append(result)
            continue
        produced = youtube_reveal.window_by_paint(cues, hit)
        if neg == "rows":
            # O CAMINHO ANTIGO: as linhas certas achatadas numa string so.
            produced = [youtube_reveal.history_of(produced)] if produced else []
        drawn = overlay_rows(produced, flatten=(neg == "draw"))
        clipped, max_text = clipped_rows(drawn["clean"])
        want = result["youtube"]
        rows_ok = [norm(x) for x in produced] == want
        draw_ok = [norm(x) for x in drawn["rows"]] == want
        if rows_ok and draw_ok:
            verdict = "MATCH"
        elif not rows_ok:
            verdict = "ROWS-DIFF"
        else:
            verdict = "DRAW-DIFF"

        # ── A ARM `dom` (2026-10-29b): a producao alimentada como o UIA a
        # alimenta -- TODOS os segmentos, sem filtro de visibilidade. O que sai
        # daqui e o que o `_tick` entrega ao overlay na app a correr.
        want_dom = result["youtube_dom"]
        dom_painted = " ".join(dom).split()
        if neg == "shape":
            # A FORMA ERRADA da entrada: as LINHAS passadas como se fossem
            # palavras (`painted_words` devolve palavras, nao linhas).
            dom_painted = list(dom)
        shape_ok = all(" " not in word for word in dom_painted)
        dom_hit, dom_how = hit_for(cues, dom_painted)
        dom_produced = (youtube_reveal.window_by_paint(cues, dom_hit)
                        if dom_hit else [])
        if neg == "drop-older" and len(dom_produced) > 1:
            # O DEFEITO 1 do bilhete: a linha mais antiga deitada fora.
            dom_produced = list(dom_produced)[1:]
        elif neg == "rewrap":
            # O DEFEITO 2: mesmas palavras, quebra noutra palavra.
            dom_produced = rewrap(dom_produced)
        elif neg == "text":
            # Uma palavra a menos: e a arm do TEXTO que tem de ver isto.
            dom_produced = dropword(dom_produced)
        dom_drawn = overlay_rows(dom_produced)
        got_dom = [norm(x) for x in dom_produced]
        dom_ok = got_dom == want_dom
        dom_draw_ok = [norm(x) for x in dom_drawn["rows"]] == want_dom
        text_ok = joined(got_dom) == joined(want_dom)
        breaks_ok = (text_ok
                     and break_offsets(got_dom) == break_offsets(want_dom))
        older_applicable = len(want_dom) > 2
        older_ok = (not older_applicable
                    or (len(got_dom) == len(want_dom)
                        and got_dom[:1] == want_dom[:1]))
        result.update({
            "rows": [norm(x) for x in produced],
            "draw": [norm(x) for x in drawn["rows"]],
            "rows_ok": rows_ok,
            "draw_ok": draw_ok,
            "verdict": verdict,
            "scrolled": drawn["scrolled"],
            "clipped": [norm(x) for x in clipped],
            "max_text": max_text,
            "dom": got_dom,
            "dom_draw": [norm(x) for x in dom_drawn["rows"]],
            "dom_hit": dom_how,
            "dom_ok": dom_ok,
            "dom_draw_ok": dom_draw_ok,
            "dom_verdict": ("MATCH" if dom_ok and dom_draw_ok else
                            ("DOM-DIFF" if not dom_ok else "DOM-DRAW-DIFF")),
            "text_ok": text_ok,
            "breaks_ok": breaks_ok,
            "shape_ok": shape_ok,
            "older_ok": older_ok,
            "older_applicable": older_applicable,
            "visible_ok": got_dom == [norm(x) for x in visible],
        })
        results.append(result)
    return results


def report(results, neg=None):
    """A tabela por amostra e o resumo; devolve (linhas, rc)."""
    out = []
    add = out.append
    total = len(results)
    rows_ok = sum(1 for item in results if item["rows_ok"])
    draw_ok = sum(1 for item in results if item["draw_ok"])
    rows_diff = sum(1 for item in results if not item["rows_ok"])
    draw_diff = sum(1 for item in results if not item["draw_ok"])
    clipped = sum(1 for item in results if item["clipped"])

    add("amostras: %d (as linhas visiveis de %s)"
        % (total, os.path.basename(LIVE)))
    add("canal: python -> youtube_reveal.window_by_paint -> rows_text -> "
        "caption_overlay._layout")
    add("")
    for item in results:
        add("t=%-8s %-10s hit=%-12s rows=%d draw=%d"
            % (round(item["t"], 3) if item["t"] is not None else "?",
               item["verdict"], item["hit"], len(item["rows"]),
               len(item["draw"])))
        add("   youtube (%d): %s" % (len(item["youtube"]), item["youtube"]))
        add("   sotto   (%d): %s" % (len(item["rows"]), item["rows"]))
        if item["verdict"] != "MATCH":
            add("   desenho (%d): %s" % (len(item["draw"]), item["draw"]))
        if item["scrolled"]:
            add("   scrolled off: %r" % (item["scrolled"],))
        if item["clipped"]:
            add("   CLIPPED (wider than %.1f px, never re-broken): %s"
                % (item["max_text"], item["clipped"]))
        add("   dom      %-12s hit=%-12s lidas=%d texto=%s quebras=%s "
            "antiga=%s caixa=%s"
            % (item["dom_verdict"], item["dom_hit"], len(item["dom"]),
               "OK" if item["text_ok"] else "DIF",
               "OK" if item["breaks_ok"] else "DIF",
               "OK" if item["older_ok"] else "DIF",
               "OK" if item["visible_ok"] else "DIF"))
        if item["dom_verdict"] != "MATCH" or not item["visible_ok"]:
            add("   player DOM (%d): %s" % (len(item["youtube_dom"]),
                                            item["youtube_dom"]))
            add("   producao   (%d): %s" % (len(item["dom"]), item["dom"]))
            add("   desenho    (%d): %s" % (len(item["dom_draw"]),
                                            item["dom_draw"]))
    add("")
    add("SUMMARY samples=%d rows_match=%d/%d draw_match=%d/%d "
        "rows_different=%d draw_different=%d clipped=%d"
        % (total, rows_ok, total, draw_ok, total, rows_diff, draw_diff, clipped))
    add("BREAKS  samples=%d dom_match=%d/%d dom_draw_match=%d/%d "
        "text_match=%d/%d breaks_match=%d/%d older_row=%d/%d "
        "shape=%d/%d visible_box=%d/%d"
        % (total,
           sum(1 for item in results if item["dom_ok"]), total,
           sum(1 for item in results if item["dom_draw_ok"]), total,
           sum(1 for item in results if item["text_ok"]), total,
           sum(1 for item in results if item["breaks_ok"]), total,
           sum(1 for item in results
               if item["older_applicable"] and item["older_ok"]),
           sum(1 for item in results if item["older_applicable"]),
           sum(1 for item in results if item["shape_ok"]), total,
           sum(1 for item in results if item["visible_ok"]), total))
    add("        `shape` = a entrada da producao e uma lista de PALAVRAS (o que "
        "`painted_words` devolve); uma linha passada como uma palavra cai aqui.")
    add("        `older_row` so conta as amostras em que o player tem 3 linhas "
        "(as outras nao tem linha antiga para guardar).")
    add("        `visible_box` nao entra no veredicto: e a caixa de 2 linhas do "
        "player, com a linha que rola para fora ja fora do rect; o overlay "
        "desenha-a inteira (fronteira de `caption_overlay._layout`, congelado "
        "pelo ratchet).")

    wiring = wiring_faltas()
    if wiring:
        add("WIRING faltas: %s" % wiring)
    else:
        add("WIRING ok: a janela, o _tick, o push e o layout estao ligados")
    tick_ok, tick_got, tick_calls = tick_arm()
    if tick_ok:
        add("TICK ok: o _tick entrega as DUAS linhas (novo e final)")
    else:
        add("TICK faltas: got=%r calls=%r" % (tick_got, tick_calls))

    if neg == "rows":
        arm = "rows-from-player"
        broken = rows_diff
        add("NEG-ARM rows: as linhas do player achatadas numa string so "
            "(o caminho antigo)")
    elif neg == "draw":
        arm = "overlay-rows"
        broken = draw_diff
        add("NEG-ARM draw: linhas certas, overlay antigo a chamar o caption_wrap")
    elif neg == "drop-older":
        # O DEFEITO 1 do bilhete, na entrada que o caminho vivo tem.
        arm = "dom-oldest-row"
        broken = sum(1 for item in results if not item["dom_ok"])
        add("NEG-ARM drop-older: a linha MAIS ANTIGA deitada fora "
            "(o `_tick` antigo, `lines[-1]`)")
    elif neg == "rewrap":
        # O DEFEITO 2 do bilhete: mesmas palavras, quebra noutra palavra.
        arm = "breaks"
        broken = sum(1 for item in results if not item["breaks_ok"])
        add("NEG-ARM rewrap: mesmas palavras, quebra movida uma palavra "
            "(o `caption_wrap.wrap_tail`)")
        add("NEG-ARM rewrap: texto_match=%d/%d quebras_match=%d/%d "
            "-- o texto fica IGUAL e so a quebra cai: as duas arms medem "
            "coisas diferentes."
            % (sum(1 for item in results if item["text_ok"]), total,
               sum(1 for item in results if item["breaks_ok"]), total))
    elif neg == "text":
        arm = "text"
        broken = sum(1 for item in results if not item["text_ok"])
        add("NEG-ARM text: uma palavra a menos (o texto deixa de ser o do player)")
        add("NEG-ARM text: texto_match=%d/%d quebras_match=%d/%d"
            % (sum(1 for item in results if item["text_ok"]), total,
               sum(1 for item in results if item["breaks_ok"]), total))
    elif neg == "shape":
        # A FORMA da entrada, nao o desenho: as linhas passadas como palavras.
        arm = "input-shape"
        broken = sum(1 for item in results if not item["shape_ok"])
        add("NEG-ARM shape: as LINHAS do player passadas como se fossem "
            "palavras (`painted_words` devolve palavras)")
        add("NEG-ARM shape: shape=%d/%d dom_match=%d/%d"
            % (sum(1 for item in results if item["shape_ok"]), total,
               sum(1 for item in results if item["dom_ok"]), total))
    else:
        arm = ""

    if neg:
        add("NEG-ARM arm=%s broken_samples=%d/%d" % (arm, broken, total))
        if broken > 0:
            # A frase canonica e "NEG-ARM PASS": e o que o `:expectred` da
            # bateria procura no log. O `:expectred` exige rc=1 E a frase --
            # e uma frase que nao existe no log faz o passo VERMELHO sem
            # dizer porque.
            #
            # MEDIDO 2026-10-30: este instrumento escrevia "NEG-ARM RED as
            # designed", e o passo `red-as-expected-youtube-rows` da bateria
            # procurava "NEG-ARM PASS" -- o braco negativo estava VERMELHO na
            # bateria (rc=1, a letra certa) e o passo nao o reconhecia.
            add("NEG-ARM PASS -- RED as designed: the arm '%s' is broken on "
                "%d/%d samples" % (arm, broken, total))
            return out, 1
        add("NEG-ARM FAILED TO GO RED -- '%s' survived the neutralisation"
            % arm)
        return out, 2

    green = (total > 0 and rows_ok == total and draw_ok == total
             and sum(1 for item in results if item["dom_ok"]) == total
             and sum(1 for item in results if item["dom_draw_ok"]) == total
             and sum(1 for item in results if item["text_ok"]) == total
             and sum(1 for item in results if item["breaks_ok"]) == total
             and sum(1 for item in results if item["shape_ok"]) == total
             and sum(1 for item in results if item["older_ok"]) == total
             and not wiring and tick_ok)
    add("YOUTUBE-ROWS %s" % ("GREEN" if green else "RED"))
    return out, 0 if green else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Linhas e quebras do player contra as que o Sotto desenha.")
    ap.add_argument("--neg-arm", nargs="?", const="rows", default=None,
                    choices=("rows", "draw", "drop-older", "rewrap", "text", "shape"),
                    help="neutraliza o canal (rows), o overlay (draw), a linha "
                         "mais antiga (drop-older), a quebra (rewrap), uma "
                         "palavra (text) ou a forma da entrada (shape): rc 1")
    ap.add_argument("--write", default=None, help="escrever o relatorio neste ficheiro")
    args = ap.parse_args(argv)

    for path in (FIXTURE, LIVE):
        if not os.path.exists(path):
            print("YOUTUBE-ROWS NO-VERDICT -- falta %s" % os.path.basename(path))
            return 2
    try:
        import caption_overlay
        import youtube_captions
        _ = caption_overlay._layout("wwwwwwwwww", "", SCALE, WORK_WIDTH)
    except Exception as exc:  # noqa: BLE001
        print("YOUTUBE-ROWS NO-VERDICT -- GDI+/_layout indisponivel: %r" % (exc,))
        return 2

    with io.open(FIXTURE, encoding="utf-8") as fh:
        cues = youtube_captions.parse_json3(fh.read())
    with io.open(LIVE, encoding="utf-8") as fh:
        live = json.load(fh)
    samples = live.get("samples") or []
    if not cues or not samples:
        print("YOUTUBE-ROWS NO-VERDICT -- payload sem cues ou artefacto sem amostras")
        return 2

    results = measure(cues, samples, neg=args.neg_arm)
    if not results:
        print("YOUTUBE-ROWS NO-VERDICT -- nenhuma amostra com linhas visiveis")
        return 2
    lines, rc = report(results, neg=args.neg_arm)
    text = "\n".join(lines)
    print(text)
    if args.write:
        with io.open(args.write, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
