#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: instrumento de medicao da quebra de linha do overlay nativo contra a do YouTube; nao corrige nada, mede o elemento que o dono nomeou
"""YT-BREAK-POSITION -- onde o overlay NATIVO quebra a linha, contra onde o YouTube quebra.

A PERGUNTA DO DONO, verbatim, e e ela que manda aqui:

    *"tem que bater timing, linha/quebra de linha e etc, 1:1."*
    *"e pra surgir palavras, quebrar linhas, usar o timing de nova linha ou nao, igual o youtube."*

`_main/youtube-1to1-oracle.py` compara o **numero** de linhas ("amostras com numero de linhas
diferente: 0/677"). Numero igual nao e quebra igual: duas linhas podem ter a fronteira noutra
palavra e o contador nao ve. Este ficheiro mede a FRONTEIRA.

E mede no sitio certo. O dono ve `app/webview/caption_overlay.py`, nao a pagina: o overlay
recebe UM `text` e chama `caption_wrap.wrap_tail(text, cur_w, budget)` com um orcamento em
PIXEIS (`caption_overlay._layout`). O modelo `youtube_window.live_lines` devolve uma string por
cue, ou seja a quebra do payload -- mas o overlay nao desenha isso, re-quebra.

    python _main\\yt-break-position-probe.py            # a tabela, rc=0 se todas batem
    python _main\\yt-break-position-probe.py --json out.json

rc 0 = cada amostra tem a fronteira do YouTube; 1 = alguma nao tem; 2 = nao foi possivel medir
(sem payload, sem fonte de medida). Uma medicao ausente nao e um veredicto.

NAO LANCA A APP e nao abre janela: usa a medida GDI+ do proprio overlay, em processo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEBVIEW = os.environ.get("SOTTO_PROBE_WEBVIEW") or os.path.join(ROOT, "app", "webview")
for _p in (ROOT, WEBVIEW):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FIXTURE = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.en-orig.json3")
LIVE = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.live-compare-20261026.json")

# A geometria com que o overlay mediu em 2026-10-17 (docstring de `_layout`): 1920 de area,
# 34 px, orcamento 727 px. E o numero REAL do sitio, nao um inventado para o teste.
WORK_WIDTH = 1920
SCALE = 1.0


def _sotto_lines(work_width=WORK_WIDTH):
    """A medida GDI+ do proprio overlay, ou None se o ambiente nao a der."""
    try:
        import caption_overlay as co
    except Exception as exc:  # noqa: BLE001
        return None, "import caption_overlay falhou: %r" % (exc,)
    try:
        def layout(text):
            res = co._layout(text, "", SCALE, work_width)
            return res[0], res[4] if len(res) > 4 else ""
        # prova de que a medida responde antes de confiar nela
        probe = layout("wwwwwwwwww")[0]
        if not probe:
            return None, "_layout devolveu vazio na sonda"
        return layout, ""
    except Exception as exc:  # noqa: BLE001
        return None, "GDI+/_layout indisponivel em processo: %r" % (exc,)


def _load_segments():
    """As linhas do YouTube por instante, do payload (segmentos do player)."""
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    out = []
    for ev in doc.get("events", []):
        segs = ev.get("segs") or []
        if not segs:
            continue
        words = [s.get("utf8") or "" for s in segs]
        text = "".join(words).strip()
        if not text:
            continue
        out.append({"t": ev.get("tStartMs", 0) / 1000.0, "text": text})
    return out


def _yt_break_from_cues():
    """A fronteira do YouTube tal como os cues servidos a trazem (uma linha por segmento)."""
    path = os.path.join(ROOT, "_cache", "youtube-captions", "WdaHAGRBB6s.jsonl")
    if not os.path.exists(path):
        return None
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Onde o overlay quebra, contra onde o YouTube quebra.")
    ap.add_argument("--json", default=None, help="escrever o relatorio neste ficheiro")
    ap.add_argument("--work-width", type=int, default=WORK_WIDTH,
                    help="largura da area de trabalho em px (1920 = a medida de 2026-10-17)")
    ap.add_argument("--live", default=LIVE, help="artefacto de comparacao (por omissao o de 2026-10-26)")
    args = ap.parse_args()

    layout, err = _sotto_lines(args.work_width)
    if layout is None:
        print("BREAK-POSITION NO-VERDICT -- %s" % err)
        print("(uma medicao ausente nao e um veredicto: rc=2)")
        return 2

    segs = _load_segments()
    if not segs:
        print("BREAK-POSITION NO-VERDICT -- payload sem segmentos de texto")
        return 2

    # As amostras em que o YOUTUBE desenha DUAS linhas: e onde a fronteira existe e pode divergir.
    two = []
    for s in segs:
        rows = s["text"].split("\n")
        if len(rows) >= 2:
            two.append(s)
    if not two:
        # O payload json3 nao traz '\n'; a fronteira vem da divisao por segmento nos cues servidos.
        cues = _yt_break_from_cues()
        if cues is None:
            print("BREAK-POSITION NO-VERDICT -- sem cache de cues servidos")
            return 2

    # Para cada amostra do artefacto LIVE (as 16 que o player pintou), comparar a fronteira.
    live = None
    if os.path.exists(args.live):
        with open(args.live, "r", encoding="utf-8") as fh:
            live = json.load(fh)

    # A FRONTEIRA DO YOUTUBE VIVE NOS `segs`, nao nos `lines`. O artefacto guarda
    # `lines` como o textContent do contentor -- UMA string, o texto todo junto, e por
    # isso o verde 16/16 de 2026-10-26 nao podia ver onde a quebra cai. `segs` sao os
    # segmentos que o player PINTA, um por linha; e a unica testemunha da fronteira.
    samples = (live or {}).get("samples") or []
    rows = []
    different = 0
    joined_different = 0
    for s in samples:
        yt_lines = [str(seg.get("t") or "") for seg in (s.get("segs") or [])]
        yt_lines = [x for x in yt_lines if x]
        if not yt_lines:
            continue
        text = " ".join(yt_lines)
        ours, scrolled = layout(text)
        ours = [x for x in ours if x]
        same = ours == yt_lines
        joined_same = " ".join(ours) == text
        different += 0 if same else 1
        joined_different += 0 if joined_same else 1
        rows.append({
            "t": s.get("t"),
            "youtube": yt_lines,
            "overlay": ours,
            "scrolled": scrolled,
            "same_break": same,
            "same_joined_text": joined_same,
        })

    if not rows:
        print("BREAK-POSITION NO-VERDICT -- nenhuma amostra do artefacto tem segmentos")
        return 2

    print("BREAK-POSITION overlay nativo vs YouTube, %d amostra(s)" % len(rows))
    print("geometria: work_width=%d scale=%.1f, medida GDI+ do proprio caption_overlay" % (args.work_width, SCALE))
    for r in rows:
        mark = "igual " if r["same_break"] else ("texto-junto-igual" if r["same_joined_text"] else "DIFERE")
        print("  t=%-8s %s" % (round(r["t"], 3) if r["t"] is not None else "?", mark))
        print("     youtube (%d): %r" % (len(r["youtube"]), r["youtube"]))
        print("     overlay (%d): %r" % (len(r["overlay"]), r["overlay"]))
        if r["scrolled"]:
            print("     scrolled off: %r" % (r["scrolled"],))
    print("SUMMARY amostras=%d fronteira_diferente=%d texto_junto_diferente=%d"
          % (len(rows), different, joined_different))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"geometry": {"work_width": args.work_width, "scale": SCALE},
                       "samples": rows, "different": different}, fh, ensure_ascii=False, indent=1)

    print("BREAK-POSITION %s" % ("MATCH" if not different else "DIVERGE"))
    return 0 if not different else 1


if __name__ == "__main__":
    sys.exit(main())
