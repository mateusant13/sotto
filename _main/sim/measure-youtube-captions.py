#!/usr/bin/env python
"""AS MEDIDAS QUE `docs/youtube-caption-spec.md` CITA -- uma linha por numero.

O QUE ESTE FICHEIRO E'. O unico instrumento que produz os numeros da especificacao
da legenda do YouTube (`docs/youtube-caption-spec.md`). Cada linha daquela tabela
aponta para uma chave deste ficheiro. Sem ele, a tabela seria uma citacao; com ele,
qualquer pessoa re-corre o comando e obtem o mesmo numero (ou uma divergencia).

AS FONTES, e porque cada uma serve:

  * `_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3` -- o payload do PROPRIO player
    (`wireMagic: pb3`, `events`, `wpWinPositions`). E' o documento que o YouTube
    consome: `rcRows`, `ccCols`, o `tStartMs`/`dDurationMs` de cada linha e o
    `tOffsetMs` de cada palavra.
  * `_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json` -- 16 quadros do
    player lidos por CDP (`Runtime.evaluate` sobre `.ytp-caption-segment`,
    `_main/yt-1to1-live-compare.py`). E' a unica fonte que diz o que o player
    DESENHA: quantas linhas tem, quais estao dentro da caixa, e a opacidade de
    cada uma. Os instantes sao `getCurrentTime()` do proprio player, com o video
    PAUSADO no instante pedido -- o texto lido E' o texto daquele instante.
  * `_main/fixtures/yt-WdaHAGRBB6s.break-position-20261026.json` -- 16 quadros que
    comparam as linhas do player com o que o overlay desenhava. Serve para UMA
    coisa: provar que a quebra de linha do YouTube e' a do payload e nao uma
    re-quebra nossa.

AS TRES MEDIDAS QUE SO' A UIA DA'. O payload nao diz o que o player desenha:

  1. quantas linhas estao no ecra durante uma transicao (`rcRows=2` + a que rola
     para fora) -- medido 1, 2 ou 3, e o modelo de `EXIT_S` reproduz os 16 quadros;
  2. se a linha que sai ainda esta' dentro da caixa (medido: 1 das 16 amostras tem
     uma linha FORA da caixa, com `opacity` ainda a 1 -- e' um rolamento, nao um
     apagamento instantaneo);
  3. se a revelacao do player e' o relogio de palavra do payload -- comparado por
     IGUALDADE DE TEXTO, nao por contagem: `">> No."` e' UM segmento com dois
     espacos dentro, e contar palavras por espaco media outra coisa.

O QUE ELE NAO MEDE, e diz que nao mede: a duracao e a curva do FADE. Nao ha
instrumento nesta maquina que leia a animacao CSS do player sem uma sessao viva
(a captura le a opacidade a ~0,65 s por quadro e o fade dura menos que isso). Essas
linhas da especificacao ficam marcadas `[INFERENCE]`, com o numero que o Sotto usa.

    python _main\\sim\\measure-youtube-captions.py                 # a tabela
    python _main\\sim\\measure-youtube-captions.py --write         # reescreve o .json
    python _main\\sim\\measure-youtube-captions.py --json out.json

Exit: 0 medido, 2 fixture ausente (ausencia de medicao nao e' medicao).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.dirname(HERE)
FIX = os.path.join(MAIN, "fixtures")
PAYLOAD = os.path.join(FIX, "yt-WdaHAGRBB6s.en-orig.json3")
LIVE = os.path.join(FIX, "yt-WdaHAGRBB6s.live-compare-20261026.json")
BREAKS = os.path.join(FIX, "yt-WdaHAGRBB6s.break-position-20261026.json")
OUT = os.path.join(HERE, "youtube-caption-metrics.json")

#: O passo da varredura do payload. 10 ms e' 4x mais fino que o menor intervalo
#: entre duas palavras do payload (medido: 40 ms).
STEP_S = 0.01

#: O TEMPO QUE UMA LINHA PRONTA AINDA E' DESENHADA depois do seu `dDurationMs`.
#: NAO e' escolhido: e' o UNICO intervalo que reproduz os 16 quadros da captura,
#: e o proprio instrumento re-deriva os limites a cada corrida
#: (`rollup.exit_s_bracket_s`). Aqui fica o valor usado pelo modelo, para o
#: numero aparecer num sitio so'.
EXIT_S = 0.45


# ----------------------------------------------------------------- o payload


def read(path):
    return json.loads(io.open(path, encoding="utf-8").read())


def payload_rows(doc):
    """As linhas do payload, com o relogio ABSOLUTO de cada palavra.

    Um evento `aAppend: 1` e' o separador da janela (`"\\n"`), nao uma linha. Um
    segmento sem `tOffsetMs` entra no instante do evento -- medido: e' sempre o
    PRIMEIRO segmento da linha, e o `tOffsetMs` conta a partir do `tStartMs`.
    """
    rows = []
    separators = 0
    for ev in doc.get("events") or ():
        if not isinstance(ev, dict):
            continue
        if ev.get("aAppend"):
            if any(str((s or {}).get("utf8") or "") == "\n"
                   for s in ev.get("segs") or () if isinstance(s, dict)):
                separators += 1
            continue
        if "wpWinPosId" in ev:
            continue
        segs = [s for s in (ev.get("segs") or ()) if isinstance(s, dict)]
        text = "".join(str(s.get("utf8") or "") for s in segs)
        if not text.strip():
            continue
        start = float(ev.get("tStartMs") or 0) / 1000.0
        words = []
        for seg in segs:
            off = seg.get("tOffsetMs")
            off_s = float(off) / 1000.0 if isinstance(off, (int, float)) else 0.0
            words.append({"start": round(start + off_s, 3),
                          "text": str(seg.get("utf8") or "")})
        rows.append({
            "start": round(start, 3),
            "end": round(start + float(ev.get("dDurationMs") or 0) / 1000.0, 3),
            "text": text,
            "words": words,
        })
    return rows, separators


def window_declared(doc):
    for pos in doc.get("wpWinPositions") or ():
        if isinstance(pos, dict) and pos.get("rcRows"):
            return int(pos["rcRows"]), int(pos.get("ccCols") or 0)
    return None, None


def stats(values):
    if not values:
        return None
    vals = sorted(values)
    n = len(vals)
    return {"n": n,
            "min": round(vals[0], 3),
            "median": round(vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2.0, 3),
            "max": round(vals[-1], 3)}


def word_gaps(rows):
    """Os intervalos entre as PALAVRAS de uma linha (segmentos consecutivos)."""
    gaps = []
    for row in rows:
        starts = [w["start"] for w in row["words"]]
        gaps += [round(b - a, 3) for a, b in zip(starts, starts[1:])]
    return gaps


def revealed(row, t):
    """O texto que a linha ja' revelou em `t` -- o relogio de cada segmento."""
    out = ""
    for w in row["words"]:
        if w["start"] <= t + 1e-9:
            out += w["text"]
    return out


def drawn_rows(rows, t, capacity, exit_s=EXIT_S):
    """As linhas DESENHADAS em `t`, da mais antiga para a nova.

    A regra, com as duas metades medidas uma a uma: uma linha entra em `start` e
    NAO sai em `end` -- fica mais `exit_s` (a que sai ainda e' desenhada enquanto
    rola). Das que sobram ficam as ultimas `capacity + 1`: a janela do player tem
    `rcRows` linhas mais a que esta' a sair.
    """
    live = [r for r in rows if r["start"] <= t < r["end"] + exit_s]
    live.sort(key=lambda r: r["start"])
    return live[-(capacity + 1):] if live else []


def rows_over_time(rows, capacity, exit_s, end, step=STEP_S):
    tally = {}
    t = 0.0
    while t < end:
        n = len(drawn_rows(rows, t, capacity, exit_s))
        tally[n] = round(tally.get(n, 0.0) + step, 3)
        t = round(t + step, 3)
    return {str(k): v for k, v in sorted(tally.items())}


def overlaps(rows):
    """Uma linha nova comeca ANTES de a anterior acabar de revelar?

    `novo.start - ultima_palavra.start` da linha anterior. Negativo seria DUAS
    linhas a crescer ao mesmo tempo -- o caso que a regra do "so' uma cresce"
    recusa.
    """
    out = []
    for a, b in zip(rows, rows[1:]):
        last = a["words"][-1]["start"] if a["words"] else a["start"]
        out.append({"at": a["start"], "next_at": b["start"],
                    "delta": round(b["start"] - last, 3)})
    return out


def hold(rows):
    """Quanto tempo uma linha PRONTA fica no ecra antes de sair da janela."""
    return [round(r["end"] - (r["words"][-1]["start"] if r["words"] else r["start"]), 3)
            for r in rows]


def chars_per_row(rows):
    return [len(r["text"]) for r in rows]


def split_words(rows):
    """Linhas que PARTEM uma palavra -- medido pelo payload, nao por opiniao.

    A unica forma de uma linha partir uma palavra dentro de UM payload e' a
    palavra ser cortada entre dois `segs` da mesma linha (dois segmentos
    encostados, o primeiro a acabar em letra e o segundo a comecar em letra). Um
    corte ENTRE linhas e' o separador: o payload nao tem como distinguir "acabou a
    palavra" de "acabou a linha", e por isso essa metade mede-se no DESENHO
    (`_main/caption-native-wrap-oracle.py`, arm 4: a palavra comprida e' entregue
    inteira).
    """
    out = []
    for row in rows:
        for a, b in zip(row["words"], row["words"][1:]):
            left, right = a["text"], b["text"]
            if (left[-1:].isalpha() and right[:1].isalpha()
                    and not right[:1].isspace()):
                out.append({"row": row["start"], "left": left, "right": right})
    return out


# ------------------------------------------------------------------- a UIA


def uia_samples(path):
    return read(path).get("samples") or []


def uia_rows(sample):
    """As linhas que o player DESENHA naquele quadro, na ordem do DOM.

    `v` (visivel) e' o que esta' DENTRO da caixa da janela -- uma linha fora dela
    esta' a rolar para fora. `o` e' a opacidade computada (1.0 = opaca).
    """
    return [{"text": seg.get("t") or "", "opacity": seg.get("o"),
             "visible": bool(seg.get("v")), "lang": seg.get("l")}
            for seg in sample.get("segs") or ()]


def match_row(rows, painted, t):
    """A linha do payload que o player esta' a DESENHAR: a que comeca pelo texto.

    Casa por PREFIXO porque a linha cresce: em t=0,77 s o player pinta
    `"Have you ever had"` e a linha do payload e' `"Have you ever had to kill a
    man?"`. Empate resolvido pela linha VIVA em `t`.
    """
    painted = " ".join(str(painted or "").split())
    cands = [r for r in rows if " ".join(r["text"].split()).startswith(painted)]
    if not cands:
        return None
    live = [r for r in cands if r["start"] <= t <= r["end"] + EXIT_S]
    return (live or cands)[0]


def uia_vs_clock(rows, samples):
    """O texto que o player PINTA contra o texto que o relogio do payload revela.

    IGUALDADE, nao contagem. Contar palavras por espaco mediria `">> No."` como
    duas palavras quando o payload declara UM segmento.
    """
    agree, disagree, unmatched = [], [], []
    for sample in samples:
        drawn = uia_rows(sample)
        if not drawn:
            continue
        t = round(float(sample.get("t") or 0.0), 3)
        target = drawn[-1]["text"]
        row = match_row(rows, target, t)
        if row is None:
            unmatched.append({"t": t, "text": target})
            continue
        painted = " ".join(target.split())
        clock = " ".join(revealed(row, t).split())
        rec = {"t": t, "row_start": row["start"], "painted": painted,
               "clock": clock}
        (agree if painted == clock else disagree).append(rec)
    return agree, disagree, unmatched


def early(rows, samples):
    """A CUE QUE CHEGA ADIANTADA: uma linha desenhada ANTES do seu proprio `start`.

    O motor do Sotto (`youtube_reveal._drawn`) so' desenha `start <= t`, e a
    alternativa -- pintar um cue que ainda nao comecou -- seria a legenda a falar
    do futuro. Este numero diz se a regra e' uma invencao nossa ou o que o player
    faz: quantas linhas o PLAYER desenha antes do instante que o payload lhe da'.
    Zero e' a resposta certa; um numero maior obrigaria a regra a mudar.
    """
    ahead = []
    for sample in samples:
        t = round(float(sample.get("t") or 0.0), 3)
        for row in uia_rows(sample):
            hit = match_row(rows, row["text"], t)
            if hit is not None and float(hit["start"]) > t + 1e-6:
                ahead.append({"t": t, "row_start": hit["start"],
                              "text": row["text"]})
    return {"frames": len(samples), "rows_drawn_before_start": ahead}


def uia_shape(samples, rows, capacity):
    """Como a janela aparece nos quadros: linhas, fora-da-caixa, opacidade."""
    per = {}
    outside, translucent = [], []
    model_ok = 0
    for sample in samples:
        drawn = uia_rows(sample)
        n = len(drawn)
        per[n] = per.get(n, 0) + 1
        t = round(float(sample.get("t") or 0.0), 3)
        if n == len(drawn_rows(rows, t, capacity)):
            model_ok += 1
        for row in drawn:
            if not row["visible"]:
                outside.append({"t": t, "text": row["text"]})
            if row["opacity"] is not None and float(row["opacity"]) < 1.0:
                translucent.append({"t": t, "text": row["text"],
                                    "opacity": row["opacity"]})
    return {"samples": len(samples),
            "rows_per_sample": {str(k): v for k, v in sorted(per.items())},
            "max_rows": max(per) if per else 0,
            "model_reproduces_row_count": model_ok,
            "outside_box": outside,
            "opacity_below_1": translucent}


def exit_bracket(rows, samples):
    """O intervalo de `exit_s` que reproduz TODOS os quadros.

    Cada quadro diz, para cada linha que ja' acabou: "esta' desenhada" ->
    `exit_s > t - end`; "nao esta'" -> `exit_s <= t - end`. A interseccao destas
    condicoes e' o intervalo. Nao ha aqui nenhum numero escolhido a mao: 0,45 e'
    so' o valor dentro do intervalo que o modelo usa.
    """
    lo, hi = 0.0, 10.0
    for sample in samples:
        t = float(sample.get("t") or 0.0)
        drawn = [" ".join(row["text"].split()) for row in uia_rows(sample)]
        for row in rows:
            if row["start"] > t or row["end"] >= t:
                continue
            whole = " ".join(row["text"].split())
            inside = any(d == whole or whole.startswith(d) for d in drawn if d)
            if inside:
                lo = max(lo, round(t - row["end"], 3) + 1e-6)
            else:
                hi = min(hi, round(t - row["end"], 3))
    return {"min_s": round(lo, 3), "max_s": round(hi, 3), "used_s": EXIT_S,
            "reproduces_all_samples": lo < EXIT_S <= hi}


def breaks_evidence(path):
    doc = read(path)
    samples = doc.get("samples") or []
    return {"samples": len(samples),
            "same_break": sum(1 for s in samples if s.get("same_break")),
            "same_joined_text": sum(1 for s in samples if s.get("same_joined_text")),
            "youtube_rows_max": max((len(s.get("youtube") or ()) for s in samples),
                                    default=0),
            "overlay_lines_max": max((len(s.get("overlay") or ()) for s in samples),
                                     default=0)}


# --------------------------------------------------------------------- main


def measure():
    doc = read(PAYLOAD)
    rows, separators = payload_rows(doc)
    cap, cols = window_declared(doc)
    cap = cap or 2
    end = max((r["end"] for r in rows), default=0.0)
    gaps = word_gaps(rows)
    samples = uia_samples(LIVE)
    agree, disagree, unmatched = uia_vs_clock(rows, samples)
    bracket = exit_bracket(rows, samples)
    shape = uia_shape(samples, rows, cap)
    early_evidence = early(rows, samples)
    marks = [w for r in rows for w in r["words"]]
    deltas = [o["delta"] for o in overlaps(rows)]
    return {
        "schema": "sotto-youtube-caption-metrics/1",
        "sources": {
            "payload": os.path.relpath(PAYLOAD, MAIN).replace("\\", "/"),
            "live_compare": os.path.relpath(LIVE, MAIN).replace("\\", "/"),
            "break_position": os.path.relpath(BREAKS, MAIN).replace("\\", "/"),
            "payload_rows": len(rows),
            "payload_words": len(marks),
            "words_with_offset_declared": sum(
                1 for ev in doc.get("events") or ()
                if isinstance(ev, dict) and not ev.get("aAppend")
                for s in (ev.get("segs") or ())
                if isinstance(s, dict) and isinstance(s.get("tOffsetMs"), (int, float))
                and str(s.get("utf8") or "").strip()),
            "separators": separators,
            "media_end_s": round(end, 3),
        },
        "window": {"rcRows": cap, "ccCols": cols},
        "word_clock": {
            "origin": "tStartMs of the row; a segment's own tOffsetMs is added to it",
            "first_segment_offset_ms": 0,
            "gaps_s": stats(gaps),
            "gaps_at_or_below_120ms": sum(1 for g in gaps if g <= 0.12),
            "gaps_at_or_below_40ms": sum(1 for g in gaps if g <= 0.041),
            "words_per_row": stats([len(r["words"]) for r in rows]),
        },
        "lines": {
            "chars_per_row": stats(chars_per_row(rows)),
            "rows_over_ccCols": sum(1 for n in chars_per_row(rows) if cols and n > cols),
            "split_words_inside_a_row": split_words(rows),
        },
        "rollup": {
            "exit_s_bracket_s": bracket,
            "drawn_rows_over_time": rows_over_time(rows, cap, EXIT_S, end),
            "drawn_rows_over_time_without_exit": rows_over_time(rows, cap, 0.0, end),
            "new_row_before_previous_reveal_done": [
                o for o in overlaps(rows) if o["delta"] < 0],
            "new_row_delta_from_previous_last_word_s": stats(deltas),
        },
        "hold_s": stats(hold(rows)),
        "early": early_evidence,
        "uia": {
            "agree": len(agree),
            "disagree": len(disagree),
            "unmatched": unmatched,
            "disagree_samples": disagree,
            "first_agree": agree[:3],
            "shape": shape,
        },
        "break_position": breaks_evidence(BREAKS),
        "fade": {
            "in_s": None,
            "out_s": None,
            "curve": None,
            "confidence": "INFERENCE",
            "why": "a captura le a opacidade a ~0,65 s por quadro e o fade dura "
                   "menos que isso; a animacao CSS do player so' se le numa sessao "
                   "viva (CDP getComputedStyle), que este instrumento nao abre",
            "smallest_resolvable_s": 0.65,
            "sotto_uses": {"in_s": 0.12, "out_s": 0.45,
                           "curve": "1-(1-t)^2  (ease-out quadratico)",
                           "module": "app/webview/word_fade.py"},
        },
    }


def table(m):
    s = m["sources"]
    w = m["window"]
    wc = m["word_clock"]
    ln = m["lines"]
    ru = m["rollup"]
    uia = m["uia"]
    lines = [
        ("rcRows (linhas declaradas)", w["rcRows"]),
        ("ccCols (colunas declaradas)", w["ccCols"]),
        ("caracteres por linha", ln["chars_per_row"]),
        ("linhas acima de ccCols", ln["rows_over_ccCols"]),
        ("palavras partidas dentro de uma linha", len(ln["split_words_inside_a_row"])),
        ("palavras por linha (segmentos)", wc["words_per_row"]),
        ("intervalo entre palavras (s)", wc["gaps_s"]),
        ("intervalos <= 120 ms / <= 40 ms",
         "%d / %d" % (wc["gaps_at_or_below_120ms"], wc["gaps_at_or_below_40ms"])),
        ("hold de uma linha pronta (s)", m["hold_s"]),
        ("delta linha nova vs ultima palavra (s)", ru["new_row_delta_from_previous_last_word_s"]),
        ("linhas novas antes do fim da revelacao anterior",
         len(ru["new_row_before_previous_reveal_done"])),
        ("exit_s medido (s)", "%s .. %s (modelo usa %s)" % (
            ru["exit_s_bracket_s"]["min_s"], ru["exit_s_bracket_s"]["max_s"],
            ru["exit_s_bracket_s"]["used_s"])),
        ("linhas desenhadas ao longo do video (com exit)",
         ru["drawn_rows_over_time"]),
        ("linhas desenhadas ao longo do video (sem exit)",
         ru["drawn_rows_over_time_without_exit"]),
        ("quadros UIA", uia["shape"]["samples"]),
        ("linhas por quadro UIA", uia["shape"]["rows_per_sample"]),
        ("o modelo de exit reproduz os quadros",
         "%d/%d" % (uia["shape"]["model_reproduces_row_count"], uia["shape"]["samples"])),
        ("UIA pinta == relogio de palavra (texto)",
         "%d/%d" % (uia["agree"], uia["agree"] + uia["disagree"])),
        ("cue adiantada: linhas pintadas antes do start", "%d/%d" % (
            len(m["early"]["rows_drawn_before_start"]), m["early"]["frames"])),
        ("linhas fora da caixa (a rolar para fora)", len(uia["shape"]["outside_box"])),
        ("opacidade < 1 nos quadros", len(uia["shape"]["opacity_below_1"])),
        ("break-position: mesma quebra", "%d/%d" % (m["break_position"]["same_break"],
                                                    m["break_position"]["samples"])),
        ("payload: linhas / palavras / offsets / separadores",
         "%d / %d / %d / %d" % (s["payload_rows"], s["payload_words"],
                                s["words_with_offset_declared"], s["separators"])),
    ]
    out = ["%-50s %s" % ("MEDIDA", "VALOR"), "-" * 78]
    for name, value in lines:
        out.append("%-50s %s" % (name, value if not isinstance(value, dict) else
                                 json.dumps(value, ensure_ascii=False)))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="as medidas da legenda do YouTube")
    ap.add_argument("--json", default=None, help="escrever o JSON neste ficheiro")
    ap.add_argument("--write", action="store_true", help="reescrever %s" % OUT)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    for path in (PAYLOAD, LIVE, BREAKS):
        if not os.path.isfile(path):
            print("MEDICAO AUSENTE: %s" % path)
            return 2

    m = measure()
    text = json.dumps(m, ensure_ascii=False, indent=1) + "\n"
    if args.json:
        io.open(args.json, "w", encoding="utf-8", newline="\n").write(text)
    if args.write:
        io.open(OUT, "w", encoding="utf-8", newline="\n").write(text)
        print("escrito: %s" % OUT)
    print(table(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
