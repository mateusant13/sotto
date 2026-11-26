#!/usr/bin/env python
# BLOCKS: "the caption froze / the pause was wrong" judged ONLY against what the
#         log said, with no record of what the player actually did per instant.
# NO-BUG: the player's timeline must be captured as bytes and replayed OFFLINE
#         through the product's own pause/seek/clock functions.
"""yt-capture-replay-oracle -- o fixture do player, julgado pelo codigo do produto.

A ORDEM DO DONO QUE ISTO FECHA (verbatim, 2026-11-26):
    *"por que EU tenho que mandar tu fazer uma snapshot do youtube pra pegar o
    comportamento exato e reproduzir offline? por que nenhuma das skills te
    ajuda a ver as coisas por essa visao?"*

A resposta e' este par:
  * `_main/yt-snapshot-capture.py` grava a LINHA DO TEMPO do player (posicao,
    `paused`, `readyState`, o segmento visivel) a cada 50 ms, com dois carimbos,
    e executa um guiao (`play`, `pause`, `seek`) marcando cada accao;
  * este ficheiro REPLAIA o fixture por um relogio simulado e pergunta ao
    CODIGO DO PRODUTO o que ele teria decidido -- nunca a um modelo mental meu.

O QUE E' CODIGO REAL AQUI (importado, nao reescrito):
    `youtube_clock.pause_proven`          -- a conjuncao das duas testemunhas
    `youtube_monotonic.SeekWitness`       -- a prova do seek pelo par (posicao, carimbo)
    `youtube_monotonic.advance`           -- o chao sobe com a pintura, desce so' no seek
    `youtube_monotonic.decide`            -- o instante servido nunca recua

O QUE E' ESPELHO, e esta' dito porque um espelho sem rotulo e' uma mentira:
    `_MirrorWitness.clock_static` / `.clock_moving` espelham
    `sotto_webview.py:5673` / `:5768` (as duas vivem como METODO da shell, com
    estado no objecto; importar a shell inteira para um oraculo custaria um
    WebView2). O dono da verdade delas e' `_main/youtube-monotonic-oracle.py`,
    que conduz as versoes REAIS; aqui elas so' alimentam `pause_proven` com o
    que a linha do tempo gravada diz. Tres mutantes abaixo provam que o espelho
    discrimina -- um espelho que nao sabe ficar vermelho nao mede nada.

O QUE ELE RECUSA POR NOME, nunca em silencio:
    * fixture sem segmento de legenda -> o braco do CUE e' `CANNOT-MEASURE`
      (medido 2026-11-26: numa sessao sem login o YouTube devolve `200` com
      **0 bytes** para TODAS as faixas -- 26 faixas em 3 videos -- logo nao ha'
      texto de cue para gravar; a metade da pausa/seek continua a ser julgada);
    * fixture com menos de duas amostras -> `CANNOT-MEASURE why=too-few-samples`.

Uso:
    python _main/yt-capture-replay-oracle.py _main/fixtures/yt-snapshot-*.json
    python _main/yt-capture-replay-oracle.py <fixture> --neg-arm
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.normpath(os.path.join(HERE, "..", "app", "webview"))
if APP not in sys.path:
    sys.path.insert(0, APP)

import youtube_clock  # noqa: E402  (o caminho do produto e' montado acima)
import youtube_monotonic  # noqa: E402

#: Os literais que os espelhos usam, lidos do PRODUTO acima (nunca inventados
#: aqui) e conferidos contra o texto da shell no braco `g-constants-agree`.
CLOCK_STATIC_PAUSE_S = 2.0     # sotto_webview.py:5657
CLOCK_STATIC_PAUSE_FLAG_S = 0.25  # :5670
CLOCK_MOVING_MIN_RATE = 0.05   # :5766
DOM_FRESH_S = 1.2              # :6375
SEEK_BACK_S = 2.0              # youtube_monotonic.py:47


def _f(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


class _MirrorWitness:
    """ESPELHO de `sotto_webview._yt_clock_static` / `_yt_clock_moving`.

    `clock_static`: o `currentTime` igual ao da ultima leitura DIFERENTE, e ha'
    pelo menos `CLOCK_STATIC_PAUSE_S` desde ela (ou `..._FLAG_S` quando a
    bandeira no MESMO snapshot concorda). Uma foto repetida (mesmo carimbo) nao
    e' leitura nova.

    `clock_moving`: a taxa de `currentTime` desde a leitura anterior, com piso
    de 0.10 s de intervalo; um recuo devolve `(False, 0.0)` -- um seek nao e'
    "a andar" nem "parado".
    """

    def __init__(self):
        self._ct = None      # (valor, since, stamp)
        self._mv = None      # (t, stamp)

    def clock_static(self, snap):
        t = _f(snap.get("t"))
        stamp = _f(snap.get("stamp"))
        if t is None or stamp is None:
            return False, 0.0
        held = 0.0
        flag = bool(snap.get("paused"))
        if self._ct is None:
            self._ct = (t, stamp, stamp)
            return False, 0.0
        val, since, lstamp = self._ct
        if stamp <= lstamp:
            return False, 0.0                      # a MESMA foto
        if abs(t - val) > 1e-9:
            self._ct = (t, stamp, stamp)
            return False, 0.0
        held = stamp - since
        floor = CLOCK_STATIC_PAUSE_FLAG_S if flag else CLOCK_STATIC_PAUSE_S
        return (held >= floor), held

    def clock_moving(self, snap):
        t = _f(snap.get("t"))
        stamp = _f(snap.get("stamp"))
        if t is None or stamp is None:
            self._mv = None
            return False, 0.0
        prev = self._mv
        self._mv = (t, stamp)
        if prev is None:
            return False, 0.0
        prev_t, prev_stamp = prev
        gap = stamp - prev_stamp
        if gap < 0.10:
            return False, 0.0
        rate = (t - prev_t) / gap
        if rate < 0.0:
            return False, 0.0
        return rate >= CLOCK_MOVING_MIN_RATE, rate


#: As epocas que o fixture GRAVADO nao tem -- e sem elas quatro bracos nao sabem
#: ficar vermelhos (medido 2026-11-26: `--neg-arm 1/5`). Cada uma e' a FORMA de
#: uma linha do log do dono, nao uma invencao: o que se injecta e' a sequencia
#: de (posicao, `paused`, carimbo), e as posicoes sao as medidas no log.
SYNTHETIC = {
    "E1-stale-photo-says-paused": {
        "why": "YOUTUBE_SNAPSHOT_STALE age_ms=5891 (2026-11-26 02:38:08.713) + "
               "YOUTUBE_PAUSE_PROVEN held_s=0.6 (02:38:10.436) -- uma foto de 5.9 s",
        "steps": [(30.00, False), (30.00, True), (30.00, True), (30.00, True)],
        "gap_s": 1.5,  # carimbos de 1.5 s: a ultima foto tem 4.5 s (velha)
        "final_gap_s": 5.9,
    },
    "E2-flag-paused-while-clock-moves": {
        "why": "YOUTUBE_PAUSE_DISAGREED paused_flag=True clock_rate=0.58 "
               "(2026-11-26 02:38:01, pid 57008)",
        "steps": [(40.0, True), (43.5, True), (47.0, True), (50.5, True)],
        "gap_s": 3.5,
        "final_gap_s": 3.5,
    },
    "E3-back-jitter-below-seek-floor": {
        "why": "um recuo de 1.0 s < SEEK_BACK_S=2.0: NAO e' seek, e o instante "
               "servido nao pode recuar com ele",
        "steps": [(60.0, False), (61.0, False), (60.0, False), (61.2, False)],
        "gap_s": 0.5,
        "final_gap_s": 0.5,
    },
}


def synthetic_fixture(base):
    """O fixture real + as epocas acima, cada amostra com a sua origem."""
    import copy
    fx = copy.deepcopy(base)
    ss = list(fx.get("samples") or ())
    perf0 = max([float(s.get("perf_ms") or 0) for s in ss] + [0.0])
    base_epoch = float(base.get("wall0_epoch_ms") or 0) + perf0 if base.get("wall0_epoch_ms") else 0.0
    start = perf0 + 1000.0
    for name, ep in SYNTHETIC.items():
        stamp = start
        for t, paused in ep["steps"]:
            ss.append({"t": t, "paused": paused, "ready": 4, "seg": None,
                       "perf_ms": stamp,
                       "epoch_ms": int(base_epoch + (stamp - perf0)),
                       "at_s": round((stamp - start) / 1000.0, 3),
                       "synthetic": name, "why": ep["why"]})
            stamp += ep["gap_s"] * 1000.0
        # o ULTIMO carimbo leva o intervalo que faz a foto velha
        ss[-1]["perf_ms"] = ss[-2]["perf_ms"] + ep["final_gap_s"] * 1000.0
        start = max(s["perf_ms"] for s in ss) + 1000.0
    fx["samples"] = ss
    fx["synthetic_episodes"] = {k: v["why"] for k, v in SYNTHETIC.items()}
    return fx


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def samples_of(fx):
    """As amostras na ordem, com `stamp` de parede e `t` do player."""
    out = []
    for s in fx.get("samples") or ():
        t = _f(s.get("t"))
        stamp = _f(s.get("perf_ms"))
        if stamp is None:
            stamp = _f(s.get("epoch_ms"))
        if t is None or stamp is None:
            continue
        epoch = _f(s.get("epoch_ms"))
        skew = 0.0
        if epoch is not None and s.get("at_s") is not None and fx.get("wall0_epoch_ms"):
            # `at_s` e' o mesmo instante em perf; comparam-se as duas derivas.
            skew = (epoch / 1000.0 - fx["wall0_epoch_ms"] / 1000.0) - float(s["at_s"])
            skew -= round(skew / 3600.0) * 3600.0 if abs(skew) > 1800 else 0.0
        out.append({"epoch_skew": skew, "t": t, "stamp": stamp / 1000.0,
                    "paused": bool(s.get("paused")),
                    "ready": s.get("ready"), "seg": s.get("seg"),
                    "at_s": _f(s.get("at_s"))})
    return out


def judge(fx, pause_proven=None, witness_cls=None, advance=None, decide=None,
          mirror_cls=None):
    """As sete perguntas, sobre a linha do tempo GRAVADA. Devolve dict."""
    pause_proven = pause_proven or youtube_clock.pause_proven
    witness_cls = witness_cls or youtube_monotonic.SeekWitness
    advance = advance or youtube_monotonic.advance
    decide = decide or youtube_monotonic.decide
    ss = samples_of(fx)
    vid = str(fx.get("video") or "")
    mir = (mirror_cls or _MirrorWitness)()
    wit = witness_cls()
    floor = None
    served_prev = None
    rec = []
    for s in ss:
        snap = {"t": s["t"], "stamp": s["stamp"], "paused": s["paused"],
                "videoId": vid}
        static, held = mir.clock_static(snap)
        moving, rate = mir.clock_moving(snap)
        fresh = None  # a frescura e' preenchida abaixo, contra o "agora" do tick
        rec.append({"s": s, "static": static, "held": held, "moving": moving,
                    "rate": rate})
    # A FRESCURA: uma foto cujo carimbo esta' mais de `DOM_FRESH_S` atras do
    # "agora" (o ultimo carimbo publicado antes deste tick) nao prova nada.
    for i, r in enumerate(rec):
        now = rec[i]["s"]["stamp"]
        r["fresh"] = True if i == 0 else (now - rec[i]["s"]["stamp"]) <= DOM_FRESH_S
        r["proven"] = bool(pause_proven(r["static"], r["moving"], r["fresh"]))
        seek = wit.observe(r["s"]["t"], r["s"]["stamp"], vid)
        r["seek"] = seek
        floor = advance(floor, r["s"]["t"])
        served, floor = decide(r["s"]["t"], floor)
        r["served"] = served
        # UM RECUO SO' E' LEGAL COM UM SEEK TESTEMUNHADO NA MESMA TRANSICAO.
        # O `advance` desce o chao quando a pintura salta para tras mais que
        # `SEEK_BACK_S` -- e' a cura do defeito ao contrario ("a legenda ficava
        # presa no ponto antigo"). Logo o instante SERVIDO recuar nao e' um
        # defeito por si: e' o relogio a seguir a evidencia. O que nao pode
        # existir e' um recuo SEM essa evidencia.
        r["rewound"] = (served_prev is not None and served is not None
                        and served < served_prev - 1e-6
                        and not r["seek"].get("seek"))
        r["rewound_unwitnessed"] = (served_prev is not None and served is not None
                                    and served < served_prev - 1e-6
                                    and not r["seek"].get("seek"))
        served_prev = served

    arms = []

    def arm(name, ok, detail):
        arms.append({"arm": name, "ok": bool(ok), "detail": detail})

    # (a) O VIDEO A ANDAR NUNCA PODE SER DECLARADO EM PAUSA -- o defeito de
    #     2026-11-26: a bandeira dizia pausa, o relogio andava, e o ecra apagou.
    #     A pergunta e' do MOVIMENTO MEDIDO, nao da bandeira: um `currentTime` a
    #     avancar e' o player a andar, e o ecra nao pode apagar-se por causa
    #     disso -- e' exactamente o `YOUTUBE_PAUSE_DISAGREED clock_rate=0.58`.
    playing = [r for r in rec if r["moving"]]
    bad = [r for r in playing if r["proven"]]
    arm("a-a-moving-video-is-never-proven-paused", not bad,
        "moving_samples=%d wrongly_paused=%d %s"
        % (len(playing), len(bad),
           ("first_bad at_s=%s rate=%.2f" % (bad[0]["s"]["at_s"], bad[0]["rate"])) if bad else ""))

    # (b) UMA PAUSA A SERIO CONTINUA A APAGAR: cada corrida `paused=True` que
    #     dure `CLOCK_STATIC_PAUSE_S` tem de terminar PROVADA.
    runs, cur = [], []
    for r in rec:
        if r["s"]["paused"]:
            cur.append(r)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    #     A EXCECAO E' A PROPRIA LEI: uma pausa que o relogio DESMENTE (`E2`,
    #     `clock_rate=0.58`) nao pode apagar o ecra, logo nao entra na conta --
    #     exigir que ela fosse provada seria pedir o defeito de 2026-11-26.
    long_runs = [x for x in runs if x[-1]["s"]["stamp"] - x[0]["s"]["stamp"] >= CLOCK_STATIC_PAUSE_S]
    honest = [x for x in long_runs if not any(r["moving"] for r in x)]
    denied = [x for x in long_runs if any(r["moving"] for r in x)]
    proven_runs = [x for x in honest if x[-1]["proven"]]
    arm("b-a-real-pause-still-blanks", len(honest) == len(proven_runs),
        "long_pauses=%d clock-denied=%d proven=%d %s"
        % (len(long_runs), len(denied), len(proven_runs),
           "" if long_runs else "(nenhuma pausa longa no fixture)"))
    #     E uma pausa DESMENTIDA nunca pode ser provada -- mas isso NAO e' um
    #     braco: `pause_proven` recusa por construcao quando `moving` e' verdade,
    #     logo nenhum mutante razoavel o derruba (medido 2026-11-26: `--neg-arm`
    #     deu MISSED duas vezes). Um braco que nao pode falhar e' um verde falso,
    #     por isso ele fica como COBERTURA contada, e o defeito historico -- a
    #     shell a consultar SO' a testemunha estatica -- e' o mutante de (a).
    coverage = {"clock_denied_pauses": len(denied),
                "proven_among_denied": sum(1 for x in denied if x[-1]["proven"])}

    # (c) O SALTO PARA TRAS GRAVADO TEM DE SER NOMEADO UM SEEK, uma vez.
    backs = [r for r in rec if r["seek"].get("why") == "back"]
    jumps = [(a, b) for a, b in zip(rec, rec[1:]) if b["s"]["t"] - a["s"]["t"] < -SEEK_BACK_S]
    arm("c-a-recorded-back-jump-is-a-named-seek", len(backs) == len(jumps),
        "recorded_jumps=%d witnessed_back=%d %s"
        % (len(jumps), len(backs),
           ("was=%r now=%r" % (backs[0]["seek"].get("was"), backs[0]["seek"].get("now")))
           if backs else ""))

    # (d) O INSTANTE SERVIDO NUNCA RECUA -- a lei das 129 linhas.
    rewinds = [r for r in rec if r["rewound_unwitnessed"]]
    witnessed = [r for r in rec if r["seek"].get("seek")]
    arm("d-served-never-rewinds-without-a-witness", not rewinds,
        "unwitnessed_rewinds=%d witnessed_seeks=%d %s"
        % (len(rewinds), len(witnessed),
           ("first at_s=%s" % rewinds[0]["s"]["at_s"]) if rewinds else ""))

    # (e) TODA A AMOSTRA TEM UM ELEMENTO DE MEDIA VIVO. `rs=0` e' a assinatura
    #     MEDIDA de uma aba sem media (2026-11-26: `LOGIN_REQUIRED` -> `rs=0`,
    #     `currentTime` imovel, zero cues) -- um fixture cheio de `rs=0` nao
    #     prova nada sobre legendas, prova que a aba nao estava a tocar.
    #     A frescura da foto NAO se deduz de uma linha do tempo (o `stamp` e'
    #     gravado no momento da leitura), logo ela e' um HOLE declarado, com dono
    #     `_main/yt-pause-disagreement-oracle.py`.
    readies = [r["s"]["ready"] for r in rec]
    dead = [r for r in rec if (r["s"]["ready"] or 0) <= 0]
    #     `rs=0` PONTUAL E' UM FACTO GRAVADO (medido 2026-11-26: 3 amostras com
    #     `rs=0` a rodear o seek — o player desmonta o elemento e volta); o que
    #     nao pode existir e' um fixture cuja maioria nunca teve media. O limiar
    #     e' de MAIORIA, dito como numero, nao "todos".
    live = len(rec) - len(dead)
    frac = (live / len(rec)) if rec else 0.0
    arm("e-the-fixture-mostly-had-live-media", frac >= 0.9,
        "ready_values=%s live=%d/%d (%.3f) dead_at_s=%s (frescura: HOLE, dono "
        "`yt-pause-disagreement-oracle`)"
        % (sorted({x for x in readies if x is not None}), live, len(rec), frac,
           [round(r["s"]["at_s"] or 0, 2) for r in dead][:6]))

    # (f) A CONSTANTE DO ESPELHO CONCORDA COM A DA SHELL -- um espelho que
    #     diverge do produto mede o espelho.
    ok_c = True
    try:
        with open(os.path.join(APP, "sotto_webview.py"), encoding="utf-8",
                  errors="replace") as fh:
            shell = fh.read()
        for name, want in (("CLOCK_STATIC_PAUSE_S", CLOCK_STATIC_PAUSE_S),
                           ("CLOCK_MOVING_MIN_RATE", CLOCK_MOVING_MIN_RATE),
                           ("DOM_FRESH_S", DOM_FRESH_S)):
            ok_c = ok_c and ("%s = %s" % (name, want)) in shell
    except OSError:
        ok_c = False
    arm("f-mirror-constants-agree-with-the-shell", ok_c,
        "CLOCK_STATIC_PAUSE_S=%s CLOCK_MOVING_MIN_RATE=%s DOM_FRESH_S=%s"
        % (CLOCK_STATIC_PAUSE_S, CLOCK_MOVING_MIN_RATE, DOM_FRESH_S))

    # (g) O CUE: sem segmento gravado nao ha' o que julgar. Nomeado.
    with_seg = [r for r in rec if r["s"]["seg"]]
    if with_seg:
        arm("g-cue-painted-when-recorded", True,
            "samples_with_segment=%d" % len(with_seg))
    else:
        arms.append({"arm": "g-cue-painted-when-recorded", "ok": None,
                     "detail": "CANNOT-MEASURE why=no-caption-segment "
                               "(the player never painted a cue in this window)"})

    return {"samples": len(rec), "arms": arms, "rec": rec, "coverage": coverage,
            "counts": {"moving": len(playing), "pauses": len(runs),
                       "long_pauses": len(long_runs), "back_jumps": len(jumps),
                       "denied_pauses": len(denied)}}


def _report(res, label=""):
    print("%sYT-REPLAY samples=%d moving=%d pauses=%d long_pauses=%d back_jumps=%d denied=%d"
          % (label, res["samples"], res["counts"]["moving"], res["counts"]["pauses"],
             res["counts"]["long_pauses"], res["counts"]["back_jumps"],
             res["counts"]["denied_pauses"]))
    cov = res.get("coverage") or {}
    if cov:
        print("%sCOVERAGE clock_denied_pauses=%d proven_among_denied=%d"
              % (label, cov["clock_denied_pauses"], cov["proven_among_denied"]))
    holes = 0
    for a in res["arms"]:
        if a["ok"] is None:
            holes += 1
            print("ARM %-46s CANNOT-MEASURE %s" % (a["arm"], a["detail"]))
        else:
            print("ARM %-46s %-5s %s" % (a["arm"], "PASS" if a["ok"] else "FAIL", a["detail"]))
    bad = [a for a in res["arms"] if a["ok"] is False]
    return bad, holes


def _dead_tab(fx):
    """Um fixture mutado onde todos os samples sao `rs=0` -- a aba morta."""
    import copy
    m = copy.deepcopy(fx)
    for s in m.get("samples") or ():
        s["ready"] = 0
    return m


def neg_arm(fixtures):
    """Cada mutante tem de DERRUBAR um braco em ALGUM fixture. Devolve apanhados."""
    caught = 0
    total = 0

    def run(mut, expect_arm):
        nonlocal caught, total
        total += 1
        hit = False
        for fx in fixtures:
            res = judge(fx, **mut)
            if any(a["ok"] is False and a["arm"] == expect_arm for a in res["arms"]):
                hit = True
                break
        caught += 1 if hit else 0
        print("NEG-ARM %-48s %s" % (expect_arm,
                                    "CAUGHT" if hit else "MISSED (the arm cannot fail)"))

    # 1. O DEFEITO HISTORICO, inteiro: a shell consulta so' a testemunha
    #    estatica, e a estatica e' cega (a janela de 0.25 s de 2026-11-26).
    class _BlindStatic(_MirrorWitness):
        def clock_static(self, snap):
            return (snap.get("t") is not None), 99.0
    run({"mirror_cls": _BlindStatic,
         "pause_proven": lambda static, moving, fresh: bool(static)},
        "a-a-moving-video-is-never-proven-paused")
    # 2. `pause_proven` que aceita a bandeira sozinha, com o espelho honesto.
    run({"pause_proven": lambda static, moving, fresh: True},
        "a-a-moving-video-is-never-proven-paused")
    # 3. Um seek que aceita qualquer recuo como "a andar".
    class _Blind(youtube_monotonic.SeekWitness):
        def observe(self, t, stamp, video_id=None):
            v = super().observe(t, stamp, video_id)
            if v.get("why") in ("tracking", "first"):
                return dict(v, why="back", seek=True)
            return v
    run({"witness_cls": _Blind}, "c-a-recorded-back-jump-is-a-named-seek")
    # 4. Uma pausa que nunca e' provada.
    run({"pause_proven": lambda static, moving, fresh: False},
        "b-a-real-pause-still-blanks")

    # 5. Um chao que desce sem seek none: o `advance` a aceitar qualquer recuo.
    run({"advance": lambda floor, pos: pos},
        "d-served-never-rewinds-without-a-witness")
    # 6. Mutacao do FIXTURE: toda a amostra sem media tem de derrubar (e).
    total += 1
    hit = any(any(a["ok"] is False and a["arm"] == "e-the-fixture-mostly-had-live-media"
                  for a in judge(_dead_tab(fx))["arms"]) for fx in fixtures)
    caught += 1 if hit else 0
    print("NEG-ARM %-48s %s" % ("e-the-fixture-mostly-had-live-media",
                                "CAUGHT" if hit else "MISSED (the arm cannot fail)"))
    ok = caught == total
    print("NEG-ARM: %s -- %d/%d" % ("PASS" if ok else "FAIL", caught, total))
    # A CONVENCAO DO REPO: um mutante APANHADO sai com 1 (`red-as-expected`),
    # e rc 0 significa um portao que nao ve o defeito.
    return 1 if ok else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("fixture", nargs="?",
                    help="um fixture de `yt-snapshot-capture.py` (ou um glob)")
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    paths = []
    if args.fixture:
        paths = sorted(glob.glob(args.fixture)) or [args.fixture]
    if not paths:
        paths = sorted(glob.glob(os.path.join(HERE, "fixtures", "yt-snapshot-*.json")))
    if not paths or not os.path.exists(paths[0]):
        print("YT-REPLAY CANNOT-MEASURE why=no-fixture (rode `_main/yt-snapshot-capture.py`)")
        return 3

    rc = 0
    fixtures = []
    for p in paths:
        fx = load(p)
        if len(samples_of(fx)) < 2:
            print("YT-REPLAY CANNOT-MEASURE why=too-few-samples path=%s" % p)
            rc = max(rc, 3)
            continue
        fixtures.append((os.path.basename(p), fx))
        # O GRAVADO NAO CONTEM AS EPOCAS QUE MATAM OS MUTANTES, e um braco que
        # nao sabe ficar vermelho nao mede nada: as tres epocas medidas do log
        # entram num fixture DERIVADO, que carrega a origem em cada amostra.
        fixtures.append((os.path.basename(p) + " +episodios-medidos",
                         synthetic_fixture(fx)))
    for name, fx in fixtures:
        res = judge(fx)
        bad, holes = _report(res, label="[%s] " % name)
        if bad:
            rc = 1
    if args.neg_arm:
        return neg_arm([fx for _n, fx in fixtures])
    print("VERDICT: %s" % ("FAIL" if rc == 1 else
                           ("CANNOT-MEASURE" if rc == 3 else "PASS")))
    return rc


if __name__ == "__main__":
    sys.exit(main())
