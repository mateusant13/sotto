"""YOUTUBE 1:1 -- o que o YouTube desenha vs o que o Sotto retira.

O DONO, 2026-10-22, verbatim:
    *"tu vai pegar exatamente a transcricao do navegador/youtube desse video e
    comparar com o que aparece no transcript do sotto. ... a que retiramos do
    youtube, tem que bater timing, linha/~quebra de linha e etc, 1:1."*
    *"e tambem ter o display 1:1. e pra surgir palavras, quebrar linhas, usar o
    timing de nova linha ou nao, igual o youtube."*

O QUE ELE MEDE, e por que cada metade importa:
  * A COMPARAcaO -- as linhas do json3 que o player do YouTube consome, contra os
    cues que `youtube_captions.fetch_track` produz. Texto e `tStartMs` linha a
    linha. Se estes dois concordarem, a EXTRACcaO ja e 1:1 e o defeito que o dono
    ve nao esta aqui.
  * A JANELA -- o json3 traz `wpWinPositions[1].rcRows` e `ccCols`: o YouTube
    desenha uma janela de DUAS linhas, alimentada por eventos `aAppend: 1` cujo
    texto e `"\\n"` (o separador de linha). `cue_at` devolve UM cue, o que comecou
    por ultimo. Este oraculo imprime, em cada instante amostrado, quantas linhas
    o YouTube tem vivas ao mesmo tempo -- e portanto quantas o Sotto esta a
    perder.

O QUE ELE NAO PROVA: que o caminho VIVO (UIA a ler a legenda pintada,
`external_subs.caption_lines`) reproduz isto. Este ficheiro julga os DADOS, nao o
ecra. O ecra precisa do app, e lancar o app e do LEAD.

NAO LANCA NADA. Usa o yt-dlp ja usado pelo `youtube_captions` para buscar o
payload; nao abre browser nem worker.

    python _main\\youtube-1to1-probe.py --video WdaHAGRBB6s
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))


def load_module():
    import youtube_captions as yc
    return yc


def rows_of(doc):
    """As LINHAS que o player desenha, do json3.

    Um evento com `aAppend` e o separador de linha (`"\\n"`) e NAO e uma linha de
    legenda; um evento sem `segs`, ou cujo texto e so espaco, tambem nao.
    """
    out = []
    for ev in doc.get("events") or ():
        if not isinstance(ev, dict) or ev.get("aAppend"):
            continue
        segs = ev.get("segs") or ()
        text = "".join((s.get("utf8") or "") for s in segs if isinstance(s, dict))
        if not text.strip():
            continue
        out.append({
            "start": round(float(ev.get("tStartMs") or 0) / 1000.0, 3),
            "dur": round(float(ev.get("dDurationMs") or 0) / 1000.0, 3),
            "text": text,
        })
    return out


def window_of(doc):
    """`rcRows` e `ccCols` da janela de legendas: quantas linhas, quantas colunas."""
    rows = cols = None
    for pos in doc.get("wpWinPositions") or ():
        if isinstance(pos, dict) and pos.get("rcRows"):
            rows = int(pos["rcRows"])
            cols = int(pos.get("ccCols") or 0) or cols
    return rows, cols


def live_rows(rows, t, capacity):
    """As linhas que o YouTube tem vivas no instante `t`, no maximo `capacity`."""
    live = [r for r in rows if r["start"] <= t < r["start"] + r["dur"]]
    return live[-capacity:]


def main(argv=None):
    ap = argparse.ArgumentParser(description="YouTube 1:1: linhas do player vs cues do Sotto")
    ap.add_argument("--video", required=True, help="id do video")
    ap.add_argument("--save", default=None, help="guardar o json3 cru neste ficheiro")
    ap.add_argument("--samples", type=int, default=8, help="instantes amostrados na janela")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    yc = load_module()
    info = yc._extract_info(args.video, 90)
    track = yc.track_from_info(info)
    raw = yc._http_get(track["url"], 90)
    doc = json.loads(raw)
    if args.save:
        io.open(args.save, "w", encoding="utf-8", newline="").write(raw)

    rows = rows_of(doc)
    capacity, cols = window_of(doc)
    capacity = capacity or 2

    served = yc.fetch_track(args.video)
    cues = served.get("cues") or []

    print("video            : %s" % args.video)
    print("track do YouTube : %s (%s) %s" % (track.get("lang"), track.get("source"), track.get("name") or ""))
    print("janela do player : rcRows=%s ccCols=%s" % (capacity, cols))
    print("linhas do YouTube: %d   |   cues do Sotto: %d" % (len(rows), len(cues)))
    print("")

    same_text = same_start = 0
    print("%-3s %-16s %-16s %-6s %s" % ("i", "YOUTUBE", "SOTTO", "igual", "texto (YouTube)"))
    for i in range(max(len(rows), len(cues))):
        r = rows[i] if i < len(rows) else None
        c = cues[i] if i < len(cues) else None
        ys = "%.2f+%.2f" % (r["start"], r["dur"]) if r else "-"
        cs = "%.2f-%.2f" % (float(c.get("start", 0)), float(c.get("end", 0))) if c else "-"
        t_ok = bool(r and c and abs(r["start"] - float(c.get("start", -9))) < 0.002)
        x_ok = bool(r and c and r["text"].strip() == (c.get("text") or "").strip())
        same_start += 1 if t_ok else 0
        same_text += 1 if x_ok else 0
        print("%-3d %-16s %-16s %-6s %r" % (i, ys, cs,
                                            "SIM" if (t_ok and x_ok) else ("start" if x_ok else "nao"),
                                            (r or {}).get("text", "")[:52]))

    print("")
    print("IGUAIS no texto: %d/%d   |   IGUAIS no start: %d/%d"
          % (same_text, len(rows), same_start, len(rows)))

    # ---- a JANELA: quantas linhas o YouTube mostra e o Sotto mostra ----
    end = max((r["start"] + r["dur"] for r in rows), default=0.0)
    step = 0.1
    two_live = one_live = zero_live = 0
    n = 0
    t = 0.0
    while t < end:
        k = len(live_rows(rows, t, capacity))
        two_live += 1 if k >= 2 else 0
        one_live += 1 if k == 1 else 0
        zero_live += 1 if k == 0 else 0
        n += 1
        t += step
    print("")
    print("A JANELA ao longo de %.1f s (amostra a cada %.1f s, %d amostras):" % (end, step, n))
    print("  YouTube com DUAS linhas vivas : %5.1f s  (%.0f%%)" % (two_live * step, 100.0 * two_live / max(1, n)))
    print("  YouTube com UMA linha viva    : %5.1f s  (%.0f%%)" % (one_live * step, 100.0 * one_live / max(1, n)))
    print("  YouTube sem linha viva        : %5.1f s  (%.0f%%)" % (zero_live * step, 100.0 * zero_live / max(1, n)))
    print("  Sotto (cue_at) devolve SEMPRE UMA linha -- logo perde a segunda em %.0f%% do video."
          % (100.0 * two_live / max(1, n)))
    print("")
    print("--- o que o YouTube desenha em %d instantes ---" % args.samples)
    for i in range(args.samples):
        ts = round(end * (i + 0.5) / args.samples, 2)
        shown = live_rows(rows, ts, capacity)
        print("  t=%5.2f s  %d linha(s):" % (ts, len(shown)))
        for r in shown:
            print("      %r" % r["text"][:70])
    return 0


if __name__ == "__main__":
    sys.exit(main())
