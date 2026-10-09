#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_main/focus-timeline-oracle.py -- veredicto sobre as corridas do probe de foco.

Le os JSONL/summary das armas e responde as perguntas da lane, cada uma com as
DUAS CORES: o resultado e o controlado que TEM de ficar vermelho.

  G1 eventos-nao-amostras   hook_transicoes vs o MESMO periodo lido por um
                            amostrador de 1 s (o controlado vermelho)
  G2 latencia-do-hook       contra dwmsEventTime; controlado = a latencia
                            imposta por uma cadencia de amostragem
  G3 filtro-de-fantasmas    fila filtrada (verde) vs fila crua (vermelho)
  G4 app-do-dono excluida   janela do Sotto na fila
  G5 x->y->x                a sequencia real com tempos
  G6 custo                  CPU%, RSS, threads, ms por evento
  G7 titulo (duas vias)     GetWindowTextW vs SendMessageTimeoutW(WM_GETTEXT)
  G8 contrato da narrativa  juncao com o audio -> "audio continua"; controlado
                            = juncao desligada (nao pode dizer "continua")

Uso (analysis-only, nao cria janela nenhuma):
  py -3 _main\\focus-timeline-oracle.py --live <jsonl> --live-summary <json> \\
      --nofilter <jsonl> --pollonly <jsonl> --title <jsonl> --census <json> \\
      --report _main\\focus-timeline-oracle.json
"""

import argparse
import difflib
import json
import os
import sys

# --------------------------------------------------------------------------
# utilidades
# --------------------------------------------------------------------------

def load_jsonl(path):
    recs = []
    if not path or not os.path.exists(path):
        return recs
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    return recs


def load_json(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def hw(r):
    f = r.get("focus") or {}
    return f.get("hwnd")


def app_of(r):
    f = r.get("focus") or {}
    return {"pid": f.get("pid"), "exe": f.get("exe"), "title": f.get("title"),
            "class": f.get("class"), "hwnd": f.get("hwnd")}


def short(exe):
    if not exe:
        return "?"
    return os.path.basename(exe)


def dedup_seq(recs, sources):
    seq = []
    for r in sorted(recs, key=lambda x: x.get("t", 0)):
        if r.get("source") not in sources:
            continue
        if "focus" not in r:
            continue
        h = hw(r)
        if not seq or seq[-1][1] != h:
            seq.append((r, h))
    return seq


def subsample_states(recs, cadence_s, t0, t1, sources):
    """Simula um amostrador de `cadence_s` sobre a MESMA actividade:
    em cada fronteira le o ultimo estado conhecido."""
    ev = [r for r in recs
          if r.get("source") in sources and "focus" in r and r.get("t") is not None]
    ev.sort(key=lambda r: r["t"])
    if not ev:
        return []
    out = []
    last = None
    i = 0
    t = t0
    while t <= t1:
        while i < len(ev) and ev[i]["t"] <= t:
            last = ev[i]
            i += 1
        if last is not None:
            h = hw(last)
            if not out or out[-1][1] != h:
                out.append((last, h))
        t += cadence_s
    return out


def stats(v):
    if not v:
        return None
    s = sorted(v)
    return {"n": len(s), "min": s[0], "p50": s[len(s) // 2],
            "p95": s[min(len(s) - 1, int(len(s) * 0.95))], "max": s[-1],
            "mean": round(sum(s) / len(s), 3)}


def segments_from(recs, t_end):
    """Segmentos de foco a partir da linha do tempo (arm-start + eventos hook)."""
    seq = dedup_seq(recs, {"hook", "probe", "poll"})
    seq = [(r, h) for (r, h) in seq if h]
    segs = []
    for i, (r, h) in enumerate(seq):
        t0 = r["t"]
        t1 = seq[i + 1][0]["t"] if i + 1 < len(seq) else t_end
        segs.append({
            "i": i, "t0": round(t0, 4), "t1": round(t1, 4),
            "dwell_s": round(t1 - t0, 4),
            "hwnd": h, "key": h,
            "focus": app_of(r),
            "queue": [{"z": q.get("z"), "hwnd": q.get("hwnd"), "pid": q.get("pid"),
                       "exe": q.get("exe"), "title": q.get("title"),
                       "ghost_why": q.get("ghost_why")}
                      for q in (r.get("queue") or [])],
            "reason": r.get("reason"),
        })
    return segs


def find_xyx_hwnd(segs, min_dwell=0.0):
    """x->y->x pela IDENTIDADE da janela (nao pelo exe/titulo).

    `min_dwell` filtra a EXCURSAO (o segmento y): uma ida e volta que dura 10 ms
    e um flap de janela a aparecer, nao "o utilizador foi a outra app".
    """
    out = []
    for i in range(len(segs) - 2):
        a, b, c = segs[i], segs[i + 1], segs[i + 2]
        ka, kb, kc = a.get("key"), b.get("key"), c.get("key")
        if ka == kc and ka != kb and b["dwell_s"] >= min_dwell:
            out.append({"i": i, "x": a, "y": b, "back": c})
    return out


PANEL_CLASS_PREFIX = "WindowsForms10.Window.8.app"


def collapse_to_app(segs):
    """Funde segmentos consecutivos do MESMO processo.

    A pergunta do produto e "que APP estava em foco", nao "que janela": o Chrome
    com tres janelas abertas tem tres hwnds e UM pid, e sem esta fusao a
    narrativa enche-se de "focou no app chrome.exe" tres vezes seguidas -- e o
    x->y->x deixa de ser legivel. O nivel-janela fica no relatorio.
    """
    out = []
    for s in segs:
        pid = (s.get("focus") or {}).get("pid")
        if out and (out[-1].get("focus") or {}).get("pid") == pid and pid is not None:
            out[-1]["t1"] = s["t1"]
            out[-1]["dwell_s"] = round(out[-1]["t1"] - out[-1]["t0"], 4)
            out[-1]["merged_windows"] = out[-1].get("merged_windows", 1) + 1
            out[-1]["titles"] = sorted(set(out[-1].get("titles", []) + [s["focus"].get("title")]))
            continue
        s = dict(s)
        s["merged_windows"] = 1
        s["titles"] = [s["focus"].get("title")]
        s["key"] = pid
        out.append(s)
    for i, s in enumerate(out):
        s["i"] = i
    return out


def app_seq_from_events(recs, cadence_s=None):
    """Sequencia de APPS (pid) a partir da linha do tempo de eventos, e a mesma
    janela re-lida por um amostrador de `cadence_s` (None = sem amostragem)."""
    ev = [r for r in recs if r.get("source") in ("hook", "probe") and "focus" in r]
    ev.sort(key=lambda r: r["t"])
    if not ev:
        return [], []
    h2p = {}
    for r in recs:
        f = r.get("focus") or {}
        if f.get("hwnd"):
            h2p[f["hwnd"]] = f.get("pid")

    def seq_of(rows):
        out = []
        for r in rows:
            f = r.get("focus") or {}
            if f.get("hwnd") is None:
                continue
            p = h2p.get(f["hwnd"])
            if not out or out[-1] != p:
                out.append(p)
        return out

    real = seq_of(ev)
    if cadence_s is None:
        return real, []
    t0, t1 = ev[0]["t"], ev[-1]["t"]
    sampled = []
    i = 0
    last = None
    t = t0
    while t <= t1:
        while i < len(ev) and ev[i]["t"] <= t:
            last = ev[i]
            i += 1
        if last is not None:
            p = h2p.get((last.get("focus") or {}).get("hwnd"))
            if not sampled or sampled[-1] != p:
                sampled.append(p)
        t += cadence_s
    return real, sampled


def is_panel(d):
    return bool(d) and d.get("title") == "Sotto" and \
        str(d.get("class", "")).startswith(PANEL_CLASS_PREFIX)


def drop_panel_segments(segs):
    """Tira os segmentos de foco que sao a JANELA DO PAINEL do Sotto.

    O painel e um artefacto de medicao (outra lane a abrir o shell), nao uma app
    do dono; deixa-lo dentro da narrativa poe "usuario focou no app pythonw.exe"
    entre cada par de apps reais.
    """
    kept, dropped = [], []
    for s in segs:
        f = s["focus"]
        if is_panel({"title": f.get("title"), "class": f.get("class")}):
            dropped.append(s)
        else:
            kept.append(s)
    # reencadeia os tempos: o segmento seguinte herda o t0 do que caiu
    for i in range(len(kept) - 1):
        kept[i]["t1"] = kept[i + 1]["t0"]
        kept[i]["dwell_s"] = round(kept[i]["t1"] - kept[i]["t0"], 4)
    for i, s in enumerate(kept):
        s["i"] = i
    return kept, dropped


# --------------------------------------------------------------------------
# contrato da narrativa
# --------------------------------------------------------------------------

def build_narrative(segments, audio_segments, join=True):
    """Renderiza a narrativa do dono, verbatim na forma:
    'usuario esta no foco do app x: audio com falas tocando...:usuario focou no
     app y: audio continua... usuario voltou pro x: audio continua...'
    A juncao com o audio e CONTENCAO TEMPORAL: um segmento de audio cobre um
    instante de foco se audio.start <= t < audio.end.
    """
    def audio_at(t):
        for a in audio_segments or []:
            if a["start"] <= t < a["end"]:
                return a
        return None

    def name(app):
        base = short(app.get("exe"))
        ttl = app.get("title") or ""
        return "%s(%s)" % (base, ttl) if ttl else base

    if not segments:
        return "", []
    parts = []
    links = []
    seen = {}
    first = segments[0]
    a0 = audio_at(first["t0"]) if join else None
    parts.append("usuario esta no foco do app %s" % name(first["focus"]))
    if a0:
        parts.append(": audio com falas tocando")
    seen[first["focus"].get("exe")] = True
    for i in range(1, len(segments)):
        s = segments[i]
        prev = segments[i - 1]
        a = audio_at(s["t0"]) if join else None
        back = bool(seen.get(s["focus"].get("exe"))) and s["focus"].get("exe") != prev["focus"].get("exe")
        if back:
            parts.append("... usuario voltou pro %s" % name(s["focus"]))
        else:
            parts.append("... usuario focou no app %s" % name(s["focus"]))
        if a:
            parts.append(": audio continua")
        seen[s["focus"].get("exe")] = True
        links.append({
            "t": s["t0"], "from": prev["focus"], "to": s["focus"],
            "queue_at_transition": s.get("queue"),
            "audio_segment_id": a.get("id") if a else None,
            "audio_continues": bool(a),
        })
    return " ".join(parts), links


def contract_doc():
    return {
        "schema": "sotto.focus-timeline/1",
        "event": {
            "t": "epoch UTC (float, s) -- quando o evento foi ENTREGUE",
            "t_mono_ms": "GetTickCount64() no momento da entrega",
            "source": "hook | poll | probe",
            "reason": "foreground-event | poll-detect | arm-start | arm-stop",
            "latency_ms": "hook: piso de GetTickCount64() - dwmsEventTime (ms)",
            "latency_hi_ms": "hook: limite superior do mesmo intervalo (piso+1)",
            "event_time_ms": "dwmsEventTime que o proprio WinEventProc entregou",
            "focus": "{hwnd,pid,tid,exe,title,title_len,class}",
            "prev": "o mesmo dicionario para o foco anterior (null no arranque)",
            "focus_changed": "bool",
            "queue": "[{z,hwnd,pid,tid,exe,title,class,passes_filter,ghost_why}]"
                     " -- as N janelas SEGUINTES na ordem Z, ja filtradas",
            "raw_walked": "quantas janelas a caminhada crua percorreu",
            "filtered_n": "quantas passaram o filtro",
            "ghost_in_top_slots": "quantas das N primeiras posicoes CRUAS o filtro rejeita",
            "ghosts": "[{...,why}] amostra das rejeitadas, com o filtro que rejeitou",
            "ghost_filter": "bool -- false = COR DA CORRECCAO DESLIGADA",
            "stale": "hook: o foco ja tinha mudado outra vez quando tratamos",
            "handle_ms": "custo de tratar este evento na thread do message loop",
        },
        "narrative": {
            "join_key": "contensao temporal: audio.start <= foco.t < audio.end",
            "segments": "[{i,t0,t1,dwell_s,focus,queue,reason}]",
            "transitions": "[{t,from,to,queue_at_transition,audio_segment_id,audio_continues}]",
            "text": "a frase do dono, montada dos segmentos + os segmentos de audio",
            "audio_continues": "true enquanto o MESMO segmento de audio cobre a transicao",
        },
        "ownership": {
            "this_lane": "app em foco (pid/exe/titulo) + fila de foco + sequencia",
            "other_lane": "qual app produz o som e o titulo da aba do navegador",
        },
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--live", default=r"H:\sotto\_main\focus-timeline-A-live.jsonl")
    p.add_argument("--live-summary", default=r"H:\sotto\_main\focus-timeline-A-live-summary.json")
    p.add_argument("--nofilter", default=r"H:\sotto\_main\focus-timeline-C-nofilter.jsonl")
    p.add_argument("--nofilter-summary", default=r"H:\sotto\_main\focus-timeline-C-nofilter-summary.json")
    p.add_argument("--pollonly", default=r"H:\sotto\_main\focus-timeline-B-poll1s.jsonl")
    p.add_argument("--pollonly-summary", default=r"H:\sotto\_main\focus-timeline-B-poll1s-summary.json")
    p.add_argument("--title", default=r"H:\sotto\_main\focus-timeline-D-title.jsonl")
    p.add_argument("--title-summary", default=r"H:\sotto\_main\focus-timeline-D-title-summary.json")
    p.add_argument("--census", default=r"H:\sotto\_main\focus-timeline-A-census.json")
    p.add_argument("--cloak-census", default=r"H:\sotto\_main\focus-cloak-census.json")
    p.add_argument("--thread-baseline", default=r"H:\sotto\_main\focus-thread-baseline.json")
    p.add_argument("--thread-diag", default=r"H:\sotto\_main\focus-thread-diag.json")
    p.add_argument("--title-oracle", default=r"H:\sotto\_main\focus-title-oracle.json")
    p.add_argument("--live2", default=r"H:\sotto\_main\focus-timeline-A2-live.jsonl")
    p.add_argument("--live2-summary", default=r"H:\sotto\_main\focus-timeline-A2-live-summary.json")
    p.add_argument("--census2", default=r"H:\sotto\_main\focus-timeline-A2-census.json")
    p.add_argument("--reasons-summary", default=r"H:\sotto\_main\focus-timeline-E-reasons-summary.json")
    p.add_argument("--report", default=r"H:\sotto\_main\focus-timeline-oracle.json")
    p.add_argument("--sampler-cadence-s", type=float, default=1.0)
    a = p.parse_args(argv)

    gates = []
    rep = {"schema": "sotto.focus-timeline-oracle/1", "contract": contract_doc()}

    def gate(name, ok, detail, ctrl_ok, ctrl_detail):
        gates.append({"name": name, "ok": bool(ok), "detail": detail,
                      "control_ok": bool(ctrl_ok), "control_detail": ctrl_detail})

    live = load_jsonl(a.live)
    live_sum = load_json(a.live_summary)
    live2 = load_jsonl(a.live2)
    live2_sum = load_json(a.live2_summary)

    # ---------------- G1: eventos, nao amostras -------------------------
    def g1_for(recs, label):
        hook = [r for r in recs if r.get("source") == "hook"]
        poll = [r for r in recs if r.get("source") == "poll"]
        if not recs:
            return None
        t0 = min(r["t"] for r in recs)
        t1 = max(r["t"] for r in recs)
        hook_seq = dedup_seq(recs, {"hook"})
        poll_seq = dedup_seq(recs, {"poll"})
        # A verdade-terreno das transicoes e a PROPRIA linha do tempo de eventos
        # (hook + estado de arranque). A poller independente serve de contra-prova
        # de que a sequencia do hook nao tem transicoes inventadas.
        sub_seq = subsample_states(recs, a.sampler_cadence_s, t0, t1, {"hook", "probe"})
        hs = [h for _r, h in hook_seq]
        ps = [h for _r, h in poll_seq]
        ss = [h for _r, h in sub_seq]
        sm = difflib.SequenceMatcher(a=ps, b=hs, autojunk=False)
        hook_missed = sum(len(ps[i1:i2]) for tag, i1, i2, _j1, _j2 in sm.get_opcodes()
                          if tag in ("delete", "replace"))
        return {
            "label": label, "window_s": round(t1 - t0, 3),
            "hook_events_raw": len(hook), "poll_events_raw": len(poll),
            "hook_transitions": len(hs), "poll15_transitions": len(ps),
            "sampled_transitions_at_cadence": len(ss),
            "sampler_cadence_s": a.sampler_cadence_s,
            "hook_missed_vs_independent_poller": hook_missed,
            "sampler_missed_vs_events": max(0, len(hs) - len(ss)),
            "hook_sequence": hs, "poll15_sequence": ps, "sampled_sequence": ss,
        }

    g1a = g1_for(live, "A (poller a partilhar last_fg com o hook -- INVALIDO)")
    g1b = g1_for(live2, "A2 (poller INDEPENDENTE -- valido)")
    app_real_a, app_samp_a = app_seq_from_events(live, a.sampler_cadence_s)
    app_real_b, app_samp_b = app_seq_from_events(live2, a.sampler_cadence_s)
    rep["G1_app_level"] = {
        "arm_A_apps_events": app_real_a, "arm_A_apps_sampled_1s": app_samp_a,
        "arm_A_app_transitions": len(app_real_a), "arm_A_app_sampled": len(app_samp_a),
        "arm_A2_apps_events": app_real_b, "arm_A2_apps_sampled_1s": app_samp_b,
    }
    rep["G1"] = {"armA_entangled": g1a, "armA2_independent": g1b,
                 "instrument_bug_found": (
                     "Na arm A a poller comparava com o MESMO `last_fg` que o hook "
                     "actualizava, portanto o hook consumia a mudanca primeiro e a poller "
                     "nunca a via: 38 transicoes de hook contra 9 da poller na MESMA "
                     "janela. A poller passou a ter o seu proprio ultimo-foco (arm A2) e a "
                     "comparacao passou a ser entre duas vias independentes.")}
    src = g1a or g1b
    if src:
        # a contagem de eventos/amostras vem da janela longa (arm A, 300s); a
        # contra-prova de que o hook nao inventa transicoes vem do arm A2, cuja
        # poller e INDEPENDENTE (na arm A a poller partilhava last_fg com o hook)
        missed = ((g1b or {}).get("hook_missed_vs_independent_poller")
                  if g1b else src["hook_missed_vs_independent_poller"])
        ok = (missed == 0 and src["hook_transitions"] > 0
              and src["sampled_transitions_at_cadence"] < src["hook_transitions"])
        gate("G1 eventos-nao-amostras", ok,
             "[%s] %d transicoes de JANELA em %ss; um amostrador de %gs da %d. Ao nivel da "
             "APP (pid): %d transicoes contra %d amostradas. Contra-prova (arm A2, poller "
             "independente): o hook perdeu %d das que a poller viu"
             % (src["label"], src["hook_transitions"], src["window_s"],
                a.sampler_cadence_s, src["sampled_transitions_at_cadence"],
                len(app_real_a), len(app_samp_a), missed),
             src["sampled_transitions_at_cadence"] < src["hook_transitions"],
             "CONTROLADO(vermelho): amostrar de %gs em %gs perde %d de %d transicoes de "
             "janela que existiram de facto na mesma janela (%d de %d ao nivel da app)"
             % (a.sampler_cadence_s, a.sampler_cadence_s,
                src["sampler_missed_vs_events"], src["hook_transitions"],
                len(app_real_a) - len(app_samp_a), len(app_real_a)))
    else:
        gate("G1 eventos-nao-amostras", False, "SKIP: sem arm A/A2", False, "SKIP")

    # ---------------- G2: latencia do hook ------------------------------
    # A amostra MAIOR manda: com n=6 o "p95" e o proprio maximo, e um unico
    # evento lento moveria o veredicto. Ambas as corridas ficam no relatorio.
    cands = [s for s in (live_sum, live2_sum)
             if s and (s.get("latency_ms") or {}).get("n")]
    prim_sum = max(cands, key=lambda s: s["latency_ms"]["n"]) if cands else None
    if prim_sum and prim_sum.get("latency_ms"):
        L = prim_sum["latency_ms"]
        H = prim_sum.get("latency_hi_ms") or {}
        frac0 = prim_sum.get("latency_zero_frac")
        cad = a.sampler_cadence_s
        other = live_sum if prim_sum is live2_sum else live2_sum
        rep["G2"] = {"arm_used": prim_sum.get("label"),
                     "latency_floor_ms": L, "latency_upper_ms": H,
                     "frac_under_1ms": frac0,
                     "other_arm": (other or {}).get("label"),
                     "other_arm_latency_ms": (other or {}).get("latency_ms"),
                     "other_arm_frac_under_1ms": (other or {}).get("latency_zero_frac"),
                     "sampler_latency_mean_ms": cad * 500.0,
                     "sampler_latency_max_ms": cad * 1000.0}
        ok = L["p95"] <= 5
        gate("G2 latencia-do-hook", ok,
             "[%s] piso p50=%sms p95=%sms max=%sms; fraccao <1ms=%s (n=%d). [%s]: p50=%sms "
             "p95=%sms max=%sms frac<1ms=%s (n=%s)"
             % (prim_sum.get("label"), L["p50"], L["p95"], L["max"], frac0, L["n"],
                (other or {}).get("label"),
                ((other or {}).get("latency_ms") or {}).get("p50"),
                ((other or {}).get("latency_ms") or {}).get("p95"),
                ((other or {}).get("latency_ms") or {}).get("max"),
                (other or {}).get("latency_zero_frac"),
                ((other or {}).get("latency_ms") or {}).get("n")),
             (cad * 500.0) > L["p95"],
             "CONTROLADO(vermelho): amostrador@%gs tem latencia media %.0f ms / max %.0f ms"
             % (cad, cad * 500.0, cad * 1000.0))
    else:
        gate("G2 latencia-do-hook", False, "SKIP: sem latencias", False, "SKIP")

    # ---------------- G3: filtro de fantasmas ---------------------------
    if live and live_sum:
        ev = [r for r in live if r.get("queue") is not None]
        ghosts_in_fg_queue = sum(1 for r in ev for q in (r.get("queue") or [])
                                 if q.get("ghost_why"))
        ghost_top_total = sum(int(r.get("ghost_in_top_slots") or 0) for r in ev)
        ev_with_ghosts = sum(1 for r in ev if int(r.get("ghost_in_top_slots") or 0) > 0)
        reasons = {}
        for r in ev:
            for g in (r.get("ghosts") or []):
                reasons[g.get("why")] = reasons.get(g.get("why"), 0) + 1
        nf = load_jsonl(a.nofilter)
        nf_ghosts = sum(1 for r in nf for q in (r.get("queue") or []) if q.get("ghost_why"))
        nf_ev = sum(1 for r in nf if any(q.get("ghost_why") for q in (r.get("queue") or [])))
        rep["G3"] = {
            "events_with_queue": len(ev),
            "ghosts_in_filtered_queue": ghosts_in_fg_queue,
            "ghost_in_top_slots_total": ghost_top_total,
            "events_where_filter_removed_something": ev_with_ghosts,
            "rejection_reasons": reasons,
            "nofilter_events": len([r for r in nf if r.get("queue") is not None]),
            "nofilter_ghosts_in_queue": nf_ghosts,
            "nofilter_events_polluted": nf_ev,
        }
        ok = (ghosts_in_fg_queue == 0 and ghost_top_total > 0)
        cc = load_json(a.cloak_census) or {}
        rep["G3_cloak_positive_control"] = cc
        er = load_json(a.reasons_summary) or {}
        rep["G3_reasons_whole_walk"] = er.get("ghost_reasons_total")
        clo_live = int((er.get("ghost_reasons_total") or {}).get("cloaked(2)") or 0)
        # o filtro cloaked so decide quando a janela e VISIVEL e NAO e toolwindow:
        # as outras ja foram rejeitadas antes. O censo de uma passagem nomeia-as.
        clo_only = [r for r in (cc.get("cloaked_examples") or [])
                    if r.get("visible") and not r.get("toolwindow")]
        gate("G3 filtro-de-fantasmas", ok,
             "fila filtrada com %d fantasmas; o filtro rejeitou %d janelas em %d eventos; "
             "razoes nas 8 primeiras=%s" % (ghosts_in_fg_queue, ghost_top_total,
                                            ev_with_ghosts, reasons),
             nf_ghosts > 0,
             "CONTROLADO(vermelho): filtro DESLIGADO -> %d fantasmas na fila, em %d eventos. "
             "Sub-filtro DWMWA_CLOAKED: %s janela(s) cloaked no censo de uma passagem (de %s "
             "top-level), das quais %s sao VISIVEIS e nao-toolwindow -- so o cloaked as "
             "rejeita (ex.: %s); e o mesmo filtro decidiu AO VIVO %d vez(es) na arm E, "
             "contando a caminhada INTEIRA e nao so as 8 primeiras rejeicoes "
             "(razoes=%s)"
             % (nf_ghosts, nf_ev, cc.get("cloaked_any"), cc.get("top_level_windows_walked"),
                len(clo_only),
                (clo_only[0].get("exe") if clo_only else "nenhuma"),
                clo_live, er.get("ghost_reasons_total")))
    else:
        gate("G3 filtro-de-fantasmas", False, "SKIP: sem arm A", False, "SKIP")

    # ---------------- G4: app do dono fora da fila ----------------------
    if live_sum:
        sp = {int(k): v for k, v in (live_sum.get("sotto_pids") or {}).items()}
        sw = live_sum.get("sotto_windows") or []

        def is_panel_rule(d):
            return bool(d) and d.get("title") == "Sotto" and \
                str(d.get("class", "")).startswith("WindowsForms10.Window.8.app")

        rule_hits = {}       # pid -> n de eventos em que a regra titulo+classe o viu
        in_raw = 0
        in_queue = 0
        in_focus = 0
        focus_pids = {}
        for r in live:
            for g in (r.get("ghosts") or []):
                if g.get("pid") in sp:
                    in_raw += 1
            for q in (r.get("queue") or []):
                if q.get("pid") in sp:
                    in_queue += 1
            f = r.get("focus") or {}
            if is_panel_rule(f):
                rule_hits[f["pid"]] = rule_hits.get(f["pid"], 0) + 1
                in_focus += 1
                focus_pids[f["pid"]] = f.get("class")
            for q in (r.get("queue") or []):
                if is_panel_rule(q):
                    rule_hits[q["pid"]] = rule_hits.get(q["pid"], 0) + 1
            if is_panel_rule(r.get("prev")):
                rule_hits[r["prev"]["pid"]] = rule_hits.get(r["prev"]["pid"], 0) + 1
        leaked = {p: c for p, c in rule_hits.items() if p not in sp}
        rep["G4"] = {
            "sotto_pids_from_startup_scan": sp,
            "sotto_pid_source": live_sum.get("sotto_pid_source"),
            "sotto_windows_found_at_startup": sw,
            "sotto_in_raw_or_ghosts": in_raw,
            "sotto_in_filtered_queue": in_queue,
            "sotto_panel_rule_hits_by_pid": rule_hits,
            "sotto_panel_in_focus_events": in_focus,
            "sotto_focus_pids": focus_pids,
            "pids_seen_by_rule_but_MISSING_from_startup_scan": leaked,
        }
        if not rule_hits:
            gate("G4 app-do-dono-fora-da-fila", False,
                 "SKIP: nenhuma janela do Sotto observada (pid source=%s)"
                 % live_sum.get("sotto_pid_source"), in_queue == 0, "queue=%d" % in_queue)
        else:
            # a fila filtrada tem de estar limpa E o resultado tem de mostrar que
            # a lista de pids do arranque NAO e suficiente (a cor vermelha)
            gate("G4 app-do-dono-fora-da-fila", in_queue == 0,
                 "regra titulo+classe viu %d pid(s) do painel; na fila filtrada=%d"
                 % (len(rule_hits), in_queue), len(leaked) > 0,
                 "CONTROLADO(vermelho): a varredura de pids SO no arranque perdeu %s"
                 % (leaked if leaked else "nenhum (nao houve shell novo nesta janela)"))
    else:
        gate("G4 app-do-dono-fora-da-fila", False, "SKIP: sem summary", False, "SKIP")

    # ---------------- G5: x -> y -> x -----------------------------------
    if live:
        t1 = max(r["t"] for r in live)
        segs = segments_from(live, t1)
        xyx = find_xyx_hwnd(segs)
        segs_np, segs_panel = drop_panel_segments(segs)
        segs_app = collapse_to_app(segs_np)
        xyx_app = find_xyx_hwnd(segs_app, min_dwell=0.5)
        rep["G5"] = {"segments_window": len(segs),
                     "segments_app": len(segs_app),
                     "panel_segments_dropped": len(segs_panel),
                     "panel_pids_dropped": sorted({s["focus"]["pid"] for s in segs_panel}),
                     "xyx_window_raw": len(xyx),
                     "xyx_app_min_dwell_0.5s": len(xyx_app),
                     "patterns_app": xyx_app[:10],
                     "patterns_window": xyx[:10],
                     "segments_detail_window": segs,
                     "segments_detail_app": segs_app}
        if xyx_app:
            z = max(xyx_app, key=lambda p: p["y"]["dwell_s"])
            gate("G5 x->y->x", True,
                 "%d padrao(oes) A->B->A ao nivel da APP (pid) com a excurso >=0.5s, de %d "
                 "segmentos de app (o nivel-janela da %d crus); o mais longo: %s -> %s -> %s "
                 "com %.2fs/%.2fs/%.2fs"
                 % (len(xyx_app), len(segs_app), len(xyx), short(z["x"]["focus"]["exe"]),
                    short(z["y"]["focus"]["exe"]), short(z["back"]["focus"]["exe"]),
                    z["x"]["dwell_s"], z["y"]["dwell_s"], z["back"]["dwell_s"]),
                 len(segs_app) >= 3,
                 "CONTROLADO: a sequencia tem de ter 3 segmentos distintos de APP (tem %d); "
                 "%d segmento(s) do painel do Sotto cairam da narrativa (pids %s)"
                 % (len(segs_app), len(segs_panel),
                    sorted({s["focus"]["pid"] for s in segs_panel})))
        else:
            gate("G5 x->y->x", False,
                 "SKIP: %d segmentos de app, nenhum A->B->A com excurso >=0.5s"
                 % len(segs_app), False, "nao aplicavel sem padrao")
    else:
        gate("G5 x->y->x", False, "SKIP: sem arm A", False, "SKIP")

    # ---------------- G6: custo -----------------------------------------
    g6_sum = live2_sum or live_sum
    if g6_sum:
        base = load_json(a.thread_baseline) or {}
        diag = load_json(a.thread_diag) or {}
        added = g6_sum.get("threads_added_by_lane")
        rep["G6"] = {k: g6_sum.get(k) for k in (
            "label", "cpu_pct_of_one_core", "wall_s", "rss_mb", "peak_wset_mb", "threads",
            "thread_ids", "threads_at_start", "threads_before_poller",
            "threads_with_poller", "threads_added_by_lane", "handle_ms",
            "openprocess_calls", "dwm_calls", "poll_ms")}
        rep["G6"]["arm_A_cpu_pct"] = (live_sum or {}).get("cpu_pct_of_one_core")
        rep["G6"]["arm_A_rss_mb"] = (live_sum or {}).get("rss_mb")
        rep["G6"]["arm_A_handle_ms"] = (live_sum or {}).get("handle_ms")
        rep["G6"]["arm_A_openprocess_calls"] = (live_sum or {}).get("openprocess_calls")
        rep["G6"]["arm_A_dwm_calls"] = (live_sum or {}).get("dwm_calls")
        rep["G6"]["interpreter_thread_baseline"] = base.get("threads_after_psutil_import")
        rep["G6"]["thread_diag_steps"] = diag.get("steps")
        ok = (added is not None and added <= 1)
        gate("G6 custo", ok,
             "[%s] CPU=%s%% de um core (arm A: %s%%), RSS=%sMB, ms por evento p50=%sms "
             "p95=%sms; threads: %s antes da poller -> %s com a poller (a lane acrescenta %s)"
             % (g6_sum.get("label"), g6_sum.get("cpu_pct_of_one_core"),
                (live_sum or {}).get("cpu_pct_of_one_core"), g6_sum.get("rss_mb"),
                (g6_sum.get("handle_ms") or {}).get("p50"),
                (g6_sum.get("handle_ms") or {}).get("p95"),
                g6_sum.get("threads_before_poller"), g6_sum.get("threads_with_poller"),
                added),
             base.get("threads_after_psutil_import") is not None,
             "CONTROLADO: o pythonw.exe SOZINHO ja traz %s threads (medido, "
             "focus-thread-baseline.json) -- o orcamento de 2 e do instrumento, "
             "nao do interpretador" % base.get("threads_after_psutil_import"))
    else:
        gate("G6 custo", False, "SKIP", False, "SKIP")

    # ---------------- G7: titulo por duas vias --------------------------
    tt = load_jsonl(a.title)
    to = load_json(a.title_oracle) or {}
    if tt or to:
        cc = [r["title_crosscheck"] for r in tt if r.get("title_crosscheck")]
        agree = sum(1 for c in cc if c["agree"])
        disagree = len(cc) - agree
        gwt_empty = sum(1 for c in cc if not c["gwt"])
        wm_empty = sum(1 for c in cc if not c["wm_gettext"])
        tv = to.get("top_level_visible") or {}
        ca = to.get("children_all_visible") or {}
        rep["G7"] = {"arm_D_n": len(cc), "arm_D_agree": agree, "arm_D_disagree": disagree,
                     "arm_D_gwt_empty": gwt_empty, "arm_D_wm_empty": wm_empty,
                     "examples_arm_D": cc[:6],
                     "one_shot_top_level": to.get("top_level"),
                     "one_shot_top_level_visible": tv,
                     "one_shot_children_all_visible": ca,
                     "statement": (to.get("verdict") or {}).get("statement")}
        # verde: nas janelas que PODEM estar em foco (top-level visiveis) as duas
        # vias concordam sempre. vermelho: um controlo FILHO de outro processo
        # onde GetWindowText fica cego e WM_GETTEXT tem o texto.
        ok = (disagree == 0 and len(cc) > 0) and (tv.get("disagree", 1) == 0)
        gate("G7 titulo-duas-vias", ok,
             "foco em arm D: %d/%d concordam; janelas de topo VISIVEIS: %d/%d concordam"
             % (agree, len(cc), tv.get("agree"), tv.get("n")),
             (ca.get("gwt_blind_wm_has_text") or 0) > 0,
             "CONTROLADO(vermelho): %d controlo(s) FILHO de outro processo onde "
             "GetWindowText devolve vazio e WM_GETTEXT devolve o texto (%s) -- a "
             "confiabilidade vale para a janela de TOPO, nao para os filhos"
             % (ca.get("gwt_blind_wm_has_text") or 0,
                ", ".join(sorted({r.get("class", "") for r in
                                  (ca.get("examples_gwt_blind") or [])}))))
    else:
        gate("G7 titulo-duas-vias", False, "SKIP: sem arm D", False, "SKIP")

    # ---------------- G8: contrato da narrativa -------------------------
    demo_segs = [
        {"i": 0, "t0": 100.0, "t1": 130.0, "dwell_s": 30.0,
         "focus": {"pid": 1, "exe": r"C:\jogo\game.exe", "title": "Meu Jogo"},
         "queue": [{"z": 1, "pid": 2, "exe": r"C:\discord\Discord.exe", "title": "Discord"}]},
        {"i": 1, "t0": 130.0, "t1": 145.0, "dwell_s": 15.0,
         "focus": {"pid": 2, "exe": r"C:\discord\Discord.exe", "title": "Discord"},
         "queue": [{"z": 1, "pid": 1, "exe": r"C:\jogo\game.exe", "title": "Meu Jogo"}]},
        {"i": 2, "t0": 145.0, "t1": 180.0, "dwell_s": 35.0,
         "focus": {"pid": 1, "exe": r"C:\jogo\game.exe", "title": "Meu Jogo"},
         "queue": [{"z": 1, "pid": 2, "exe": r"C:\discord\Discord.exe", "title": "Discord"}]},
    ]
    demo_audio = [{"id": "aud-1", "start": 110.0, "end": 170.0, "text": "audio com falas"}]
    text_on, links_on = build_narrative(demo_segs, demo_audio, join=True)
    text_off, _ = build_narrative(demo_segs, demo_audio, join=False)
    ok = ("audio continua" in text_on) and ("voltou pro" in text_on) and ("audio continua" not in text_off)
    rep["G8"] = {"narrative_join_on": text_on, "narrative_join_off": text_off,
                 "links": links_on}
    gate("G8 contrato-da-narrativa", ok,
         "juncao ligada -> %r" % text_on, "audio continua" not in text_off,
         "CONTROLADO(vermelho): juncao desligada -> %r" % text_off)

    # ---------------- G10: o que o titulo do navegador da -----------------
    if live:
        BROWSER = ("Chrome_WidgetWin_1",)
        bf = [r for r in live if (r.get("focus") or {}).get("class") in BROWSER]
        bf_titles = sorted({(r["focus"].get("title") or "") for r in bf})
        q_titles = set()
        q_windows = 0
        for r in live:
            for q in (r.get("queue") or []):
                if q.get("class") in BROWSER:
                    q_windows += 1
                    q_titles.add(q.get("title") or "")
        other = sorted(q_titles - set(bf_titles))
        rep["G10"] = {
            "browser_focus_events": len(bf),
            "browser_focus_distinct_titles": bf_titles[:8],
            "browser_windows_in_queue": q_windows,
            "browser_queue_distinct_titles": sorted(q_titles)[:12],
            "browser_queue_titles_NOT_the_focused_tab": other[:12],
        }
        if bf and q_windows:
            gate("G10 titulo-do-navegador", True,
                 "titulo do foco (classe Chrome_WidgetWin_1) = aba activa: %r"
                 % (bf_titles[0] if bf_titles else ""),
                 len(other) > 0,
                 "LIMITE (nao prometo o resto): %d janela(s) do navegador na fila com "
                 "%d titulo(s) DIFERENTES do foco -- o titulo e POR JANELA e nao diz "
                 "qual delas toca som" % (q_windows, len(other)))
        else:
            gate("G10 titulo-do-navegador", False,
                 "SKIP: %d eventos de foco em navegador, %d janelas de navegador na fila"
                 % (len(bf), q_windows), False, "nao aplicavel")

    # ---------------- censo de janelas ----------------------------------
    cen = load_json(a.census2) or load_json(a.census)
    cen_a = load_json(a.census)
    if cen:
        rep["census"] = cen
        rep["census_arm_A"] = cen_a
        wv = cen.get("watch_visible_samples") or {}
        cv = cen.get("control_visible_samples") or {}
        fv = cen.get("foreground_visible_samples")
        gate("G9 censo-de-janelas-do-probe",
             all(v == 0 for v in wv.values()) and (any(v > 0 for v in cv.values()) or (fv or 0) > 0),
             "probe visivel em %s de %d amostras @%sms (arm A: %s de %s)"
             % (sum(wv.values()), cen.get("samples"), cen.get("cadence_ms"),
                sum((cen_a or {}).get("watch_visible_samples", {}).values()),
                (cen_a or {}).get("samples")),
             (any(v > 0 for v in cv.values()) or (fv or 0) > 0),
             "CONTROLADO: pid em foco visivel em %s amostras (o instrumento nao esta cego)" % fv)

    # ---------------- narrativa REAL (arm A) ----------------------------
    if live:
        t1 = max(r["t"] for r in live)
        segs = rep.get("G5", {}).get("segments_detail_window") or segments_from(live, t1)
        segs_np = drop_panel_segments(segs)[0]
        segs_app = collapse_to_app(segs_np)
        audio = [{"id": "synthetic-span", "start": min(s["t0"] for s in segs_app),
                  "end": t1, "text": "segmento sintetico (a lane de audio nao forneceu segmentos)"}]
        txt, links = build_narrative(segs_app, audio, join=True)
        txt_win, _ = build_narrative(segs, audio, join=True)
        rep["narrative_real"] = {
            "audio_source": "synthetic-span -- a lane do audio nao forneceu segmentos",
            "level": "APP (pid)",
            "panel_segments_removed": len(segs) - len(segs_np),
            "window_segments": len(segs), "app_segments": len(segs_app),
            "text": txt, "text_at_window_level": txt_win,
            "transitions": links[:20],
        }

    # ---------------- arm A2: os mesmos numeros, poller independente ------
    if live2:
        t1b = max(r["t"] for r in live2)
        segs2 = segments_from(live2, t1b)
        segs2_np = drop_panel_segments(segs2)[0]
        segs2_app = collapse_to_app(segs2_np)
        xyx2 = find_xyx_hwnd(segs2_app, min_dwell=0.5)
        rep["armA2"] = {
            "segments_window": len(segs2), "segments_app": len(segs2_app),
            "panel_segments_dropped": len(segs2) - len(segs2_np),
            "xyx_app": len(xyx2), "patterns": xyx2[:5],
            "ghosts_in_filtered_queue": sum(
                1 for r in live2 for q in (r.get("queue") or []) if q.get("ghost_why")),
            "ghost_in_top_slots_total": sum(
                int(r.get("ghost_in_top_slots") or 0)
                for r in live2 if r.get("queue") is not None),
            "narrative": build_narrative(
                segs2_app, [{"id": "synthetic-span", "start": min(s["t0"] for s in segs2_app),
                             "end": t1b, "text": "sintetico"}], join=True)[0] if segs2_app else "",
        }

    n_ok = sum(1 for g in gates if g["ok"])
    verdict = "GREEN" if n_ok == len(gates) else "RED"
    rep["gates"] = gates
    rep["verdict"] = {"verdict": verdict, "passed": n_ok, "total": len(gates),
                      "failed": [g["name"] for g in gates if not g["ok"]]}

    lines = []
    for g in gates:
        lines.append("GATE %-34s %-5s %s" % (g["name"], "GREEN" if g["ok"] else "RED", g["detail"]))
        lines.append("     %-34s       %s" % ("", g["control_detail"]))
    lines.append("VERDICT: %s  (%d/%d)" % (verdict, n_ok, len(gates)))
    txt = "\n".join(lines)
    print(txt)
    with open(a.report, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    with open(a.report.replace(".json", ".txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
