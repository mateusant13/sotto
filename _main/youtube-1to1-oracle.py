#!/usr/bin/env python
"""YOUTUBE 1:1 -- o que o PLAYER desenha contra o que o SOTTO serve, no mesmo instante.

O DONO, e e esta a frase que manda no ficheiro:

    *"tem que bater timing, linha/quebra de linha e etc, 1:1."*
    *"e pra surgir palavras, quebrar linhas, usar o timing de nova linha ou nao, igual o youtube."*

O QUE JULGA, e o que NAO julga:

  * JULGA os elementos que o dono nomeou -- PALAVRAS, QUEBRA DE LINHA, TIMING e REVELACAO
    PALAVRA-A-PALAVRA -- contra o payload do proprio YouTube, instante a instante. As duas
    pontas ficam guardadas: o payload cru (sha256) e os cues que a app serve.
  * NAO julga os pixeis no ecra do dono. Essa metade e `_main/yt-1to1-live-compare.py`, que le
    a janela de legendas do player a correr por CDP; precisa do relay vivo
    (`127.0.0.1:9224`) e de uma aba com o video, e quando nao ha relay sai 2 -- medicao
    ausente NAO e veredicto.

A FONTE E O TRACK DO YOUTUBE, e prova-se por igualdade, nao por afirmacao: os cues servidos
tem de ser exactamente o que `youtube_captions.parse_json3` tira do payload do player, e o
payload tem de trazer `events` + `wpWinPositions` + `wireMagic` (o documento do player, nao
uma transcricao nossa). Nenhum modelo de fala entra neste caminho.

O LADO DO SOTTO E O QUE A APP SERVE (`_cache/youtube-captions/<video>.jsonl`), nao o parse
fresco: comparar o parse fresco com o payload seria comparar o payload consigo proprio e daria
verde mesmo com a cache velha. `--cues parsed` existe para o contrario -- isolar a regra da
cache.

A JANELA DO YOUTUBE VEM DO PAYLOAD (`rcRows`), e o Sotto desenha a que QUISER -- sao duas
coisas diferentes de proposito. Se as duas usassem o mesmo numero, o mutante da janela nao
podia ser apanhado, e um teste que nao distingue os dois lados nao mede fidelidade nenhuma.

O RELOGIO DA REVELACAO (2026-10-26). O payload traz `tOffsetMs` nos segmentos -- o player
revela a linha palavra a palavra -- e o cue tem de carregar o mesmo relogio, senao o Sotto
mostra a linha inteira de uma vez. Esta arm compara o PREFIXO REVELADO dos dois lados em cada
instante amostrado: nao a existencia do campo, o desenho.

    python _main\\youtube-1to1-oracle.py                     # as arms, veredicto
    python _main\\youtube-1to1-oracle.py --cues parsed        # a regra, sem a cache
    python _main\\youtube-1to1-oracle.py --path single-cue    # o defeito historico: UM cue
    python _main\\youtube-1to1-oracle.py --neg-arm            # mutantes; rc=1 POR DESENHO
    python _main\\youtube-1to1-oracle.py --write _main\\_audit-verify\\youtube-1to1-report.md

Exit: 0 tudo verde, 1 alguma arm vermelha, 2 nao foi possivel medir (payload ausente).
"""
# NO-BUG: check do objectivo do dono de 2026-10-26 (brief 20261026-sotto-objective): mede
# palavras, quebras, timing e revelacao da legenda do YouTube contra o payload do player.
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))

VIDEO = "WdaHAGRBB6s"
FIXTURE = os.path.join(HERE, "fixtures", "yt-%s.en-orig.json3" % VIDEO)
STEP = 0.05
TIMING_TOL = 0.05


# ----------------------------------------------------------------- as duas pontas


def player_rows(doc):
    """As LINHAS que o player desenha, do payload dele, com o relogio de cada palavra.

    Um evento `aAppend: 1` com `"\\n"` e o separador da janela, nao uma linha. Um evento
    sem `segs`, ou de texto vazio, tambem nao. O `\\n` DENTRO de uma linha fica: e uma
    quebra que o player desenha.

    Cada linha leva `segs` = `[(tOffsetMs ou None, utf8)]`, que e o que permite revelar
    a linha como o player a revela.
    """
    out = []
    for ev in doc.get("events") or ():
        if not isinstance(ev, dict) or ev.get("aAppend"):
            continue
        segs = ev.get("segs") or ()
        text = "".join((s.get("utf8") or "") for s in segs if isinstance(s, dict))
        if not text.strip():
            continue
        relogio = []
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            off = seg.get("tOffsetMs")
            relogio.append((float(off) if isinstance(off, (int, float)) else None,
                            str(seg.get("utf8") or "")))
        out.append({
            "start": round(float(ev.get("tStartMs") or 0) / 1000.0, 3),
            "dur": round(float(ev.get("dDurationMs") or 0) / 1000.0, 3),
            "text": text,
            "segs": relogio,
        })
    return out


def payload_capacity(doc):
    for pos in doc.get("wpWinPositions") or ():
        if isinstance(pos, dict) and pos.get("rcRows"):
            return int(pos["rcRows"])
    return None


def drawn(parts):
    """As linhas DESENHADAS: `\\n` separa, espaco normaliza, vazio nao conta."""
    out = []
    for part in parts:
        for line in str(part).split("\n"):
            line = " ".join(line.split())
            if line:
                out.append(line)
    return out


def revealed_row(row, t):
    """O texto que o PLAYER ja revelou dessa linha em `t` (relogio do payload).

    O instante e arredondado ao microssegundo: `(8.2 - 7.84) * 1000` da
    `359.9999999999995` e um segmento de 360 ms ficava de fora por erro de virgula
    flutuante -- um falso vermelho de milionesimo de segundo, nao um desenho diferente.
    """
    elapsed_ms = round((float(t) - float(row["start"])) * 1000.0, 6)
    out = ""
    for off, piece in row["segs"]:
        if off is None or off <= elapsed_ms:
            out += piece
    return out


def player_at(rows, t, capacity, reveal=False):
    live = [r for r in rows if r["start"] <= t < r["start"] + r["dur"]]
    live = live[-capacity:]
    if reveal:
        return drawn([revealed_row(r, t) for r in live])
    return drawn([r["text"] for r in live])


def transicoes(series):
    """Os instantes em que o desenho MUDA -- o timing das quebras de linha.

    A primeira amostra nao conta: ela e o estado inicial, e nao uma mudanca.
    """
    out = []
    prev = None
    for t, desenho in series:
        if prev is not None and desenho != prev:
            out.append(round(t, 3))
        prev = desenho
    return out


#: As ancoras do CAMINHO VIVO. Sem elas a revelacao seria uma funcao bonita que ninguem
#: chama -- medido: o defeito de 2026-10-22 era exactamente esse, `_yt_lines` devolvia o texto
#: inteiro do cue e o `reveal` existia so no ramo `painted-untracked`.
WIRING = (
    ("a janela revelada e a que o caminho vivo usa",
     "youtube_window.revealed_lines(cues, t, 2)"),
    ("o poll do YouTube entrega o prefixo ja revelado",
     "instant=bool(yt_mode)"),
    ("o external_caption transporta o instant e as linhas",
     "push_caption_to_window(text, instant=instant, rows=rows)"),
    ("a janela da legenda pinta o prefixo sem voltar a sproutar",
     "ov.set_text(new_text, new_prev, instant)"),
)


def shell_src():
    """O caminho vivo, lido do ficheiro -- a ancoragem nao se afirma, le-se."""
    path = os.path.join(REPO, "app", "webview", "sotto_webview.py")
    try:
        return io.open(path, encoding="utf-8").read()
    except OSError:
        return ""


def wiring_faltas(src):
    """As ancoras ausentes (vazio = o caminho vivo esta ligado)."""
    return [nome for nome, agulha in WIRING if agulha not in (src or "")]


def offset_words(doc):
    """Os segmentos com `tOffsetMs` -- a revelacao palavra a palavra do payload."""
    n = 0
    for ev in doc.get("events") or ():
        if not isinstance(ev, dict) or ev.get("aAppend"):
            continue
        for seg in ev.get("segs") or ():
            if isinstance(seg, dict) and isinstance(seg.get("tOffsetMs"), (int, float)):
                if str(seg.get("utf8") or "").strip():
                    n += 1
    return n


# ----------------------------------------------------------------- o que o Sotto serve


def sotto_at(cues, t, capacity, path, reveal=False):
    import youtube_window
    if path == "single-cue":
        # O DEFEITO HISTORICO, reproduzido de proposito: `cue_at` devolve UM cue.
        import youtube_captions
        cue = youtube_captions.cue_at(cues, t)
        lines = [cue["text"]] if cue and str(cue.get("text") or "").strip() else []
        if reveal and lines:
            lines = [youtube_window.revealed_text(cue, t)]
    elif reveal:
        lines = youtube_window.revealed_lines(cues, t, capacity)
    else:
        lines = youtube_window.live_lines(cues, t, capacity)
    return drawn(youtube_window.collapse_growth(lines))[-capacity:]


def cue_words(cues):
    """Os cues carregam revelacao palavra a palavra? (offset por segmento)"""
    n = 0
    for cue in cues or ():
        for w in cue.get("words") or ():
            if isinstance(w, dict) and isinstance(w.get("tStartMs", w.get("start")), (int, float)):
                n += 1
    return n


def served_cues():
    """Os cues que a app serve, e a proveniencia deles."""
    import youtube_captions
    path = youtube_captions._cache_path(VIDEO)
    if not os.path.isfile(path):
        return None, {"path": path, "missing": True}
    served = json.loads(io.open(path, encoding="utf-8").read())
    return served.get("cues") or [], {"path": path, "lang": served.get("lang"),
                                     "fetched_at": served.get("fetched_at"),
                                     "rebuilt_from": served.get("rebuilt_from"),
                                     "player_source": served.get("player_source")}


# ----------------------------------------------------------------- a medicao


def medir(fixture_path, path,  # noqa: PLR0913
          mutate_cues=None, serve_cues=None, capacity_override=None,
          cues_from="served", wiring_override=None):
    import youtube_captions

    raw = io.open(fixture_path, encoding="utf-8").read()
    doc = json.loads(raw)
    rows = player_rows(doc)
    base_cues = youtube_captions.parse_json3(raw)

    served, cache = served_cues()
    if cues_from == "served" and served is not None:
        cues = served
    else:
        cues = base_cues
    if mutate_cues is not None:
        cues = mutate_cues(cues)

    cap_yt = payload_capacity(doc) or 2
    cap_sotto = capacity_override or cap_yt

    end = max((r["start"] + r["dur"] for r in rows), default=0.0)
    series_player, series_sotto = [], []
    series_player_revealed, series_sotto_revealed = [], []
    t = 0.0
    while t < end:
        series_player.append((round(t, 3), player_at(rows, t, cap_yt)))
        series_sotto.append((round(t, 3), sotto_at(cues, t, cap_sotto, path)))
        series_player_revealed.append((round(t, 3), player_at(rows, t, cap_yt, reveal=True)))
        series_sotto_revealed.append((round(t, 3),
                                       sotto_at(cues, t, cap_sotto, path, reveal=True)))
        t = round(t + STEP, 3)

    words_bad = [i for i, (a, b) in enumerate(zip(series_player, series_sotto)) if a[1] != b[1]]
    breaks_bad = [i for i, (a, b) in enumerate(zip(series_player, series_sotto))
                  if len(a[1]) != len(b[1])]
    reveal_bad = [i for i, (a, b) in enumerate(zip(series_player_revealed,
                                                   series_sotto_revealed)) if a[1] != b[1]]
    t_player = transicoes(series_player)
    t_sotto = transicoes(series_sotto)
    timing_bad = [x for x in t_player if not any(abs(x - y) <= TIMING_TOL for y in t_sotto)]
    timing_extra = [y for y in t_sotto if not any(abs(x - y) <= TIMING_TOL for x in t_player)]

    try:
        alvo = serve_cues(base_cues) if serve_cues else base_cues
        served_equal = (served == alvo) if served is not None else None
    except Exception:  # noqa: BLE001
        served_equal = None

    is_player_doc = bool(doc.get("events")) and bool(doc.get("wpWinPositions")) \
        and bool(doc.get("wireMagic"))

    return {
        "fixture": fixture_path,
        "fixture_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "video": VIDEO,
        "path": path,
        "cues_from": cues_from,
        "capacity_yt": cap_yt,
        "capacity_sotto": cap_sotto,
        "rows": len(rows),
        "cues": len(cues),
        "samples": len(series_player),
        "series_player": series_player,
        "series_sotto": series_sotto,
        "series_player_revealed": series_player_revealed,
        "series_sotto_revealed": series_sotto_revealed,
        "cache": cache,
        "served_equal": served_equal,
        "is_player_doc": is_player_doc,
        "words_bad": words_bad,
        "breaks_bad": breaks_bad,
        "reveal_bad": reveal_bad,
        "timing_bad": timing_bad,
        "timing_extra": timing_extra,
        "transitions_player": t_player,
        "transitions_sotto": t_sotto,
        "payload_words": offset_words(doc),
        "cue_words": cue_words(cues),
        "wiring_faltas": wiring_faltas(wiring_override if wiring_override is not None
                                       else shell_src()),
    }


def arms_of(m):
    """As arms do dono. Cada uma tem nome e um numero, nunca uma opiniao."""
    return [
        ("source-is-youtube",
         m["is_player_doc"] and m["served_equal"] is True,
         "payload do player (events+wpWinPositions+wireMagic)=%s | cues servidos == parse do payload=%s"
         % (m["is_player_doc"], m["served_equal"])),
        ("capacity-from-payload", m["capacity_yt"] >= 1,
         "rcRows=%d no payload | o Sotto desenha %d" % (m["capacity_yt"], m["capacity_sotto"])),
        ("words-1to1", not m["words_bad"],
         "amostras com texto diferente: %d/%d" % (len(m["words_bad"]), m["samples"])),
        ("linebreaks-1to1", not m["breaks_bad"],
         "amostras com numero de linhas diferente: %d/%d" % (len(m["breaks_bad"]), m["samples"])),
        ("timing-1to1", not m["timing_bad"] and not m["timing_extra"],
         "transicoes do player sem par: %d/%d | transicoes do Sotto a mais: %d/%d (tolerancia %.2fs)"
         % (len(m["timing_bad"]), len(m["transitions_player"]),
            len(m["timing_extra"]), len(m["transitions_sotto"]), TIMING_TOL)),
        ("word-reveal-1to1",
         (not m["reveal_bad"]) and (m["payload_words"] == 0 or m["cue_words"] > 0),
         "prefixo revelado diferente: %d/%d amostras | segmentos com tOffsetMs no payload: %d | "
         "palavras com relogio nos cues servidos: %d"
         % (len(m["reveal_bad"]), m["samples"], m["payload_words"], m["cue_words"])),
        ("reveal-wired",
         not m["wiring_faltas"],
         "ancoras do caminho vivo ausentes: %d/%d%s"
         % (len(m["wiring_faltas"]), len(WIRING),
            (": " + ", ".join(m["wiring_faltas"])) if m["wiring_faltas"] else "")),
    ]


# ----------------------------------------------------------------- mutantes
#: Cada mutante mexe UMA ponta. Mexer no payload movia as duas ao mesmo tempo e nao
#: media fidelidade nenhuma -- foi o que a primeira versao deste ficheiro fez.


def mut_shift_start(cues):
    """A linha nova do Sotto chega 400 ms tarde -- a arm do timing tem de a ver."""
    out = [dict(c) for c in cues]
    if out:
        out[0]["start"] = round(float(out[0]["start"]) + 0.4, 3)
    return out


def mut_mangle_word(cues):
    """Uma palavra a mais do lado do Sotto -- a arm das palavras tem de a ver."""
    out = [dict(c) for c in cues]
    if out:
        out[0]["text"] = str(out[0].get("text") or "") + " zz"
    return out


def mut_join_cues(cues):
    """Duas linhas do player fundidas numa so -- a arm das quebras tem de a ver."""
    out = [dict(c) for c in cues]
    if len(out) >= 2:
        a, b = out[0], out[1]
        merged = {"start": a["start"], "end": max(a["end"], b["end"]),
                  "text": str(a.get("text") or "") + " " + str(b.get("text") or "")}
        if a.get("words") or b.get("words"):
            merged["words"] = list(a.get("words") or []) + list(b.get("words") or [])
        out[0] = merged
        del out[1]
    return out


def mut_drop_offsets(cues):
    """O relogio da revelacao desaparece dos cues -- a arm do reveal tem de a ver."""
    out = []
    for c in cues:
        d = dict(c)
        d.pop("words", None)
        out.append(d)
    return out


def mut_flat_reveal(cues):
    """Todas as palavras ao mesmo tempo (o defeito de antes): o reveal tem de a ver."""
    out = []
    for c in cues:
        d = dict(c)
        if d.get("words"):
            d["words"] = [dict(w, start=d["start"]) for w in d["words"]]
        out.append(d)
    return out


def mut_stale_serve(cues):
    """Os cues servidos nao sao o parse deste payload: outra faixa."""
    out = [dict(c) for c in cues]
    if out:
        out[0]["text"] = str(out[0].get("text") or "") + " (outra faixa)"
    return out


def mut_unwired(wiring_src):
    """O caminho vivo volta a mostrar o cue inteiro: a arm da ancoragem tem de a ver."""
    return str(wiring_src or "").replace("youtube_window.revealed_lines(cues, t, 2)",
                                         "youtube_window.live_lines(cues, t, 2)")


MUTATIONS = (
    ("single-cue",       {"path": "single-cue"},                "linebreaks-1to1"),
    ("shift-cue-start",  {"mutate_cues": mut_shift_start},      "timing-1to1"),
    ("mangle-cue-word",  {"mutate_cues": mut_mangle_word},      "words-1to1"),
    ("join-cues",        {"mutate_cues": mut_join_cues},        "linebreaks-1to1"),
    ("one-line-window",  {"capacity_override": 1},              "linebreaks-1to1"),
    ("stale-served",     {"serve_cues": mut_stale_serve},       "source-is-youtube"),
    ("drop-offsets",     {"mutate_cues": mut_drop_offsets},     "word-reveal-1to1"),
    ("flat-reveal",      {"mutate_cues": mut_flat_reveal},      "word-reveal-1to1"),
    ("unwired-reveal",   {"wiring_drop": True},                 "reveal-wired"),
)


# ----------------------------------------------------------------- relatorio


def relatorio(m, arms):
    out = ["video            : %s" % m["video"],
           "payload do player: %s" % m["fixture"],
           "payload sha256   : %s" % m["fixture_sha256"],
           "cache servida    : %s" % ((m["cache"] or {}).get("path") or "-"),
           "cues comparados  : %s" % m["cues_from"],
           "linhas do player : %d  |  cues servidos: %d  |  amostras: %d  (passo %.2fs)"
           % (m["rows"], m["cues"], m["samples"], STEP),
           "janela           : rcRows=%d (YouTube) | %d (Sotto)" % (m["capacity_yt"], m["capacity_sotto"]),
           "caminho          : %s" % m["path"],
           "",
           "elemento                 veredicto  medicao"]
    for name, ok, detail in arms:
        out.append("%-24s %-9s  %s" % (name, "GREEN" if ok else "RED", detail))
    out.append("")
    vistos = 0
    for (t, a), (_t, b) in zip(m["series_player"], m["series_sotto"]):
        if a != b and vistos < 8:
            vistos += 1
            out.append("t=%6.2fs (linha inteira)" % t)
            out.append("   YOUTUBE: %r" % (a,))
            out.append("   SOTTO  : %r" % (b,))
    for (t, a), (_t, b) in zip(m["series_player_revealed"], m["series_sotto_revealed"]):
        if a != b and vistos < 16:
            vistos += 1
            out.append("t=%6.2fs (prefixo revelado)" % t)
            out.append("   YOUTUBE: %r" % (a,))
            out.append("   SOTTO  : %r" % (b,))
    if not vistos:
        out.append("(nenhuma divergencia de desenho em %d amostras)" % m["samples"])
    return "\n".join(out)


def main(argv=None):
    global VIDEO
    ap = argparse.ArgumentParser(description="YouTube 1:1: palavras, quebras, timing, revelacao")
    ap.add_argument("--video", default=VIDEO)
    ap.add_argument("--fixture", default=FIXTURE)
    ap.add_argument("--path", choices=("live-window", "single-cue"), default="live-window")
    ap.add_argument("--cues", choices=("served", "parsed"), default="served",
                    help="comparar com os cues que a app serve (default) ou com o parse fresco")
    ap.add_argument("--write", default=None, help="escrever o relatorio neste ficheiro")
    ap.add_argument("--neg-arm", action="store_true", help="todos os mutantes; rc=1 POR DESENHO")
    ap.add_argument("--mutation", default=None)
    ap.add_argument("--list-mutations", action="store_true")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    VIDEO = args.video

    if args.list_mutations:
        for name, _kw, arm in MUTATIONS:
            print("%-18s esperado: %s" % (name, arm))
        return 0

    if not os.path.isfile(args.fixture):
        print("MEDICAO AUSENTE: payload do player nao existe: %s" % args.fixture)
        print("VIDEO-1TO1 VERDICT NO-MEASURE (rc=2) -- ausencia de medicao nao e veredicto")
        return 2

    if args.neg_arm or args.mutation:
        chosen = [x for x in MUTATIONS if args.mutation in (None, x[0])]
        failed = 0
        for name, kw, arm in chosen:
            m = medir(args.fixture, kw.get("path", args.path),
                      mutate_cues=kw.get("mutate_cues"),
                      serve_cues=kw.get("serve_cues"),
                      capacity_override=kw.get("capacity_override"),
                      cues_from=args.cues,
                      wiring_override=(mut_unwired(shell_src())
                                       if kw.get("wiring_drop") else None))
            arms = dict((n, ok) for n, ok, _d in arms_of(m))
            caught = sorted(n for n, ok in arms.items() if not ok)
            named = (not arms.get(arm, True))
            print("MUTATION %-17s %s  [esperado: %s] recusou por: %s"
                  % (name, "NEG-ARM PASS" if named else "NEG-ARM FAIL", arm,
                     ", ".join(caught) or "-"))
            if not named:
                failed += 1
        print("NEG-ARM %s mutations=%d named-arm-fail=%d"
              % ("PASS" if not failed else "FAIL", len(chosen), failed))
        return 1

    m = medir(args.fixture, args.path, cues_from=args.cues)
    arms = arms_of(m)
    text = relatorio(m, arms)
    print(text)
    if args.write:
        io.open(args.write, "w", encoding="utf-8", newline="").write(text + "\n")
    bad = [n for n, ok, _d in arms if not ok]
    print("")
    print("SUMMARY elementos=%d vermelhos=%d%s" % (len(arms), len(bad),
                                                   (": " + ", ".join(bad)) if bad else ""))
    print("YOUTUBE-1TO1 VERDICT %s" % ("RED" if bad else "GREEN"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
