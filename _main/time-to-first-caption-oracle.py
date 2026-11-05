#!/usr/bin/env python
# NO-BUG: INSTRUMENTO de arranque -- mede os segundos entre o arranque do shell e a PRIMEIRA legenda pintada, e nada mais. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""A PRIMEIRA LEGENDA: quantos ms depois de o shell arrancar e' que ela aparece.

O DEFEITO QUE ISTO MEDE (dono, 2026-11-04). O log dele, verbatim:

    SHELL_STARTUP_STAGE 09:57:24.323
    CAPTION_PAINT       09:58:29.360   <-- a primeira legenda

65 s de aplicacao aberta sem uma legenda. A aceitacao dele e' outra: **uma
legenda ate' 3 s depois de a app estar de pe'**. Este oraculo e' o instrumento
dessa aceitacao: le' o log VIVO (`_main/webview-run.log`), acha a ULTIMA
`SHELL_STARTUP_STAGE` (o arranque em julgamento), acha a PRIMEIRA legenda
pintada depois dela, e imprime a diferenca em ms. PASS so' abaixo de 3000 ms.

O QUE CONTA COMO "LEGENDA PINTADA" -- e por que nao e' qualquer `CAPTION_PAINT`.
O shell pinta o overlay com textos de ESTADO (`carregando modelo...`,
`Starting worker...`) nas primeiras centenas de ms. Esses NAO sao legendas; um
oraculo que os aceitasse daria PASS a uma app que nunca transcreveu nada. A
lista de placeholders esta' em `PLACEHOLDER_PREFIXES`, e a linha que foi
descartada fica no relatorio para se poder julgar a lista.

`CAPTION_PAINT_LAG` NAO E' `CAPTION_PAINT`: e' a linha de orcamento de atraso
que acompanha cada pintura. O regex exige um espaco depois do token, e `_LAG`
nao casa, portanto as duas nunca se confundem.

A TABELA DE FASES (`--stage-table`, ligada por omissao no texto) e' a outra
metade: 65 s sem dizer ONDE nao e' uma medicao. As marcas, todas ja' no log:

    SHELL_STARTUP_STAGE   t0 -- o processo do shell comecou
    BRIDGE_SPAWNED        o worker foi largado (argv+pid no log)
    WORKER_PROVIDERS      a sessao do encoder existe e diz que EP usa
    BRIDGE_LOAD_MS        o shell LEU `model-loaded` (spawn -> grafo carregado)
    STATUS_APPLIED capture-started   o tap abriu (o worker tem audio)
    BRIDGE_METER          o primeiro bloco de audio chegou ao worker
    CAPTION_IN            o worker decodificou a primeira linha
    CAPTION_PAINT         o overlay pintou-a  <-- o fim do relogio

`YT_FRAME` e' a fonte EXTERNA (YouTube) -- medida em paralelo e NAO somada: e'
a unica rota que pode chegar aos 3 s sem esperar pelo grafo, e um relatorio que
a esconde descreve mal a app.

A PRIMEIRA LEGENDA CONTA POR QUALQUER ROTA (2026-11-05). Ate' aqui o relogio
somava so' `CAPTION_PAINT` (a rota do ASR) e imprimia `YT_FRAME` ao lado como
informacao: a aceitacao do dono -- *"legenda do youtube aparece na hora"* -- nao
tinha portao nenhum, e o numero que ele ve' na app e' o da rota que o oraculo
nao somava. Agora o veredicto e' o da PRIMEIRA das duas e a linha diz `route=`.
A marca da rota externa e' `YOUTUBE_TRACK_PAINT` **com `painted_words` > 0**:
a mesma linha sai com `painted_words=0 source=no-player-window` de 30 em 30 s
(medido nesta arvore), e aceita-la por existir seria PASS a uma app que nao
pintou nada.

CODIGOS DE SAIDA
  0  PASS      -- legenda pintada em < LIMIAR_MS, por qualquer das duas rotas
  0  SKIPPED   -- o arranque em julgamento ainda nao tem legenda pintada (a app
                  pode estar a arrancar, ou nao havia audio nem jogador). Nao e'
                  um portao que passou: a bateria conta-o em `skipped=`.
  1  FAIL      -- legenda pintada em >= LIMIAR_MS (a aceitacao nao foi cumprida)
  2  SEM DADOS -- o ficheiro existe mas nao tem `SHELL_STARTUP_STAGE`, ou existe e
                  nao se consegue ler. Um ficheiro ABSENTE e' SKIPPED (rc=0), nao
                  SEM DADOS: numa worktree ou numa maquina onde a app nunca correu
                  nao ha' o que medir, e um passo skip-capable nao reprova a bateria.

`--neg-arm` prova o instrumento contra si proprio, em memoria, sem abrir nada e
sem processo nenhum: constroi um log sintetico no formato real com a primeira
legenda aos 1,2 s (tem de dar PASS), um com ela aos 9 s (tem de dar rc=1), um
onde o arranque em julgamento e' o SEGUNDO (o anterior nao pode ser lido como
este) e um onde a unica pintura e' um placeholder (tem de dar SKIPPED, nunca
PASS). Um mutante que sobreviva e' um furo do oraculo.

Uso:
  python _main/time-to-first-caption-oracle.py
  python _main/time-to-first-caption-oracle.py --log _main/webview-run.log --json
  python _main/time-to-first-caption-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG = os.path.join(HERE, "webview-run.log")

#: A ACEITACAO DO DONO, em ms. 3000 ms depois de a app estar de pe'.
LIMIAR_MS = 3000

#: Prefixos de texto que o overlay pinta como ESTADO e nao como legenda. Comparados
#: no texto cru da linha (o log escreve `\\u2026`, nao o caracter), por isso as duas
#: formas estao aqui.
PLACEHOLDER_PREFIXES = (
    "carregando modelo",
    "Loading",
    "Starting the worker",
    "Starting worker",
    "Waiting for audio",
)

_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
_START = re.compile(r"SHELL_STARTUP_STAGE pid=(\d+)")
_SPAWN = re.compile(r"BRIDGE_SPAWNED pid=(\d+)")
_PROVIDERS = re.compile(r"WORKER_PROVIDERS selected=")
_LOAD = re.compile(r"BRIDGE_LOAD_MS ms=(\d+)")
_CAPTURE = re.compile(r'STATUS_APPLIED text="capture-started"')
_METER = re.compile(r'BRIDGE_METER\b.*?"blocks":([\d.]+)')
_YT = re.compile(r"YT_FRAME\b")
_CAP_IN = re.compile(r"CAPTION_IN\b")
#: `CAPTION_PAINT` seguido de espaco: `CAPTION_PAINT_LAG` nao casa (underscore
#: e' caracter de palavra, logo `\s` falha onde ele esta').
_PAINT = re.compile(r"CAPTION_PAINT\s+.*?text=(.*)$")
#: A ROTA EXTERNA TAMBEM E' UMA LEGENDA NO ECRA (2026-11-05). `YOUTUBE_TRACK_PAINT`
#: e' a linha que diz que o cro que veio do player foi PINTADO, e ela carrega a
#: contagem em `painted_words=`. MEDIDO nesta arvore: a mesma linha sai com
#: `painted_words=0 source=no-player-window` a cada 30 s quando nao ha jogador --
#: aceita-la por existir daria PASS a uma app que nao pintou nada, que e' o mesmo
#: erro de aceitar um placeholder. So' conta com `painted_words` > 0.
_YT_PAINT = re.compile(r"YOUTUBE_TRACK_PAINT\b.*?painted_words=(\d+)")

#: A ordem em que a tabela e' impressa. As chaves sao as que o `--json` publica.
STAGES = (
    ("spawn", "BRIDGE_SPAWNED"),
    ("providers", "WORKER_PROVIDERS"),
    ("load", "BRIDGE_LOAD_MS"),
    ("capture", "capture-started"),
    ("block", "BRIDGE_METER"),
    ("caption_in", "CAPTION_IN"),
    ("paint", "CAPTION_PAINT"),
    ("yt_frame", "YT_FRAME (fonte externa, nao somada)"),
    ("yt_paint", "YOUTUBE_TRACK_PAINT painted_words>0 (rota externa no ecra)"),
)


def _parse_ts(token):
    return datetime.strptime(token, "%Y-%m-%d %H:%M:%S.%f")


def _is_placeholder(text):
    t = text.strip().strip('"')
    # O log escreve os caracteres nao-ASCII como escapes JSON.
    t = t.replace("\\u2026", "\u2026")
    return any(t.startswith(p) for p in PLACEHOLDER_PREFIXES)


def measure(lines, pid=None):
    """Le' as linhas e devolve a medicao do ULTIMO arranque (ou do `pid` dado).

    Duas passagens sobre uma lista ja' em memoria: a primeira acha os arranques, a
    segunda colhe as marcas DENTRO do arranque escolhido. Colher numa passagem so'
    exigiria adivinhar o fim do arranque antes de o ver.
    """
    starts = []
    for idx, line in enumerate(lines):
        m = _START.search(line)
        if not m:
            continue
        ts = _TS.match(line)
        if not ts:
            continue
        starts.append((idx, int(m.group(1)), _parse_ts(ts.group(1))))
    if not starts:
        return {"error": "no SHELL_STARTUP_STAGE"}

    if pid is not None:
        chosen = [s for s in starts if s[1] == pid]
        if not chosen:
            return {"error": "no SHELL_STARTUP_STAGE for pid=%d" % pid}
        begin, shell_pid, t0 = chosen[-1]
        end = len(lines)
        for idx, _, _ in starts:
            if idx > begin:
                end = idx
                break
    else:
        begin, shell_pid, t0 = starts[-1]
        end = len(lines)

    marks = {}
    first_paint = None
    first_yt_paint = None
    yt_zero = None
    discarded = None
    for line in lines[begin + 1:end]:
        ts = _TS.match(line)
        if not ts:
            continue
        at = _parse_ts(ts.group(1))
        # UM `if` POR MARCA, NAO UMA CADEIA `elif`. Uma cadeia fica PRESA na marca
        # que ainda nao apareceu: enquanto `BRIDGE_METER` nao chegasse, todas as
        # linhas caiam no ramo dele e `CAPTION_IN`/`YT_FRAME` nunca eram testados
        # -- medido neste proprio arranque (o primeiro `YT_FRAME` do pid 32540 e'
        # +6,2 s e a cadeia reportava +82,6 s, o primeiro que passou por ela).
        if "spawn" not in marks and _SPAWN.search(line):
            marks["spawn"] = at
        if "providers" not in marks and _PROVIDERS.search(line):
            marks["providers"] = at
        if "load" not in marks and _LOAD.search(line):
            marks["load"] = at
        if "capture" not in marks and _CAPTURE.search(line):
            marks["capture"] = at
        if "block" not in marks:
            m = _METER.search(line)
            if m:
                try:
                    if float(m.group(1)) >= 1.0:
                        marks["block"] = at
                except ValueError:
                    pass
        if "caption_in" not in marks and _CAP_IN.search(line):
            marks["caption_in"] = at
        if "yt_frame" not in marks and _YT.search(line):
            marks["yt_frame"] = at
        if first_paint is None:
            m = _PAINT.search(line)
            if m:
                text = m.group(1).strip()
                clean = text.strip().strip('"')
                if _is_placeholder(text):
                    if discarded is None:
                        discarded = (at, clean)
                else:
                    first_paint = (at, clean)
                    marks["paint"] = at
        if first_yt_paint is None:
            m = _YT_PAINT.search(line)
            if m:
                try:
                    words = int(m.group(1))
                except ValueError:
                    words = 0
                if words > 0:
                    first_yt_paint = (at, words)
                    marks["yt_paint"] = at
                elif yt_zero is None:
                    yt_zero = (at, line.strip())

    stages = {name: marks.get(name) for name, _ in STAGES}
    # A PRIMEIRA LEGENDA E' A PRIMEIRA QUE CHEGOU AO ECRA, POR QUALQUER ROTA
    # (2026-11-05). A ordem de dono e' *"legenda do youtube aparece na hora, com a
    # legenda do sotto ativa"*: um oraculo que so' somasse a rota do ASR media a
    # rota lenta e escondia a rapida -- e a app que ele julga mostra a rapida.
    candidates = []
    if first_paint:
        candidates.append(("asr", first_paint[0], first_paint[1]))
    if first_yt_paint:
        candidates.append(("youtube", first_yt_paint[0], first_yt_paint[1]))
    candidates.sort(key=lambda c: c[1])
    first = candidates[0] if candidates else None
    out = {
        "shell_pid": shell_pid,
        "start": t0,
        "first_paint": first[1] if first else None,
        "first_paint_text": ("%d words from the player" % first[2]
                             if first and first[0] == "youtube" else first[2] if first else None),
        "first_paint_route": first[0] if first else None,
        "first_paint_asr": first_paint[0] if first_paint else None,
        "first_paint_youtube": first_yt_paint[0] if first_yt_paint else None,
        "youtube_paint_without_words": yt_zero,
        "discarded_placeholder": discarded,
        "stages": stages,
        "limit_ms": LIMIAR_MS,
    }
    out["elapsed_ms"] = (
        int(round((first[1] - t0).total_seconds() * 1000))
        if first else None)
    out["stage_ms"] = {
        name: (int(round((at - t0).total_seconds() * 1000)) if at else None)
        for name, at in stages.items()
    }
    return out


def verdict_of(result):
    """(verdict, rc) do resultado -- um so' lugar, para o `--neg-arm` julgar o MESMO codigo."""
    if result.get("error"):
        return "SEM DADOS", 2
    if result["elapsed_ms"] is None:
        return "SKIPPED", 0
    if result["elapsed_ms"] < LIMIAR_MS:
        return "PASS", 0
    return "FAIL", 1


def _fmt(ms):
    return "    -" if ms is None else "%5d" % ms


def report(result):
    lines = []
    if result.get("error"):
        lines.append("TIME-TO-FIRST-CAPTION: %s" % result["error"])
        lines.append("TIME-TO-FIRST-CAPTION VERDICT: SEM DADOS")
        return "\n".join(lines)
    verdict, _rc = verdict_of(result)
    d = result
    lines.append("run under test : shell pid=%d started %s"
                 % (d["shell_pid"], d["start"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]))
    if d["first_paint"] is None:
        lines.append("first caption  : NONE painted in this run yet")
    else:
        lines.append('first caption  : %s  +%d ms  route=%s  text="%s"'
                     % (d["first_paint"].strftime("%H:%M:%S.%f")[:-3],
                        d["elapsed_ms"], d["first_paint_route"],
                        d["first_paint_text"]))
        other = (d.get("first_paint_asr") if d["first_paint_route"] == "youtube"
                 else d.get("first_paint_youtube"))
        if other is not None:
            lines.append("other route    : +%d ms (%s)"
                         % (int(round((other - d["start"]).total_seconds() * 1000)),
                            "asr" if d["first_paint_route"] == "youtube" else "youtube"))
    if d.get("youtube_paint_without_words"):
        at, text = d["youtube_paint_without_words"]
        lines.append("  (not a caption: %s %s)"
                     % (at.strftime("%H:%M:%S.%f")[:-3], text[:110]))
    lines.append("")
    lines.append("  +ms   stage")
    lines.append("  ----- ----")
    for name, label in STAGES:
        lines.append("  %s   %s" % (_fmt(d["stage_ms"].get(name)), label))
    if d["discarded_placeholder"]:
        at, text = d["discarded_placeholder"]
        lines.append("  (discarded as placeholder: %s text=%s)"
                     % (at.strftime("%H:%M:%S.%f")[:-3], text))
    lines.append("")
    lines.append("limit          : %d ms (owner: a caption within 3 s of the app being up)"
                 % LIMIAR_MS)
    lines.append("TIME-TO-FIRST-CAPTION VERDICT: %s" % verdict)
    return "\n".join(lines)


# ── the negative arm: the instrument judged against itself, in memory ────────
def _synthetic(caption_at_ms, prefix_lines=None, extra_start_before=False,
               placeholder_only=False):
    base = datetime(2026, 11, 4, 9, 57, 24, 323000)

    def ts(ms):
        from datetime import timedelta
        t = base + timedelta(milliseconds=ms)
        return t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    out = []
    if extra_start_before:
        # Um arranque ANTERIOR, com a sua propria legenda a 1 s -- se o oraculo
        # ler deste, mede 1 s e da' PASS a uma app que demorou o que o de baixo diz.
        out.append("%s sotto: SHELL_STARTUP_STAGE pid=1111 stage=pre-lock" % ts(-600000))
        out.append('%s sotto: CAPTION_PAINT instant=false hwnd=1 text="old run"' % ts(-599000))
    out.append("%s sotto: SHELL_STARTUP_STAGE pid=4242 stage=pre-lock" % ts(0))
    out.extend(prefix_lines or [])
    if placeholder_only:
        out.append('%s sotto: CAPTION_PAINT instant=false hwnd=9 text="carregando modelo\\u2026"' % ts(900))
    elif caption_at_ms is not None:
        out.append('%s sotto: CAPTION_PAINT_LAG audio_ms=60 queue_ms=0 budget_ms=1500 over=false coalesced=0 text="audience"' % ts(caption_at_ms))
        out.append('%s sotto: CAPTION_PAINT instant=false hwnd=9 text="audience"' % ts(caption_at_ms))
    return out


REAL_PREFIX = [
    '%s sotto: BRIDGE_SPAWNED pid=52388 argv=["py"] SOTTO_CAPTURE_MODE=callback SOTTO_AUDIO_DEVICE=(unset)',
    '%s sotto: WORKER_PROVIDERS selected=CUDAExecutionProvider,CPUExecutionProvider',
    '%s sotto: BRIDGE_LOAD_MS ms=8531 pid=52388 worker_load_s=8.12',
    '%s sotto: STATUS_APPLIED text="capture-started"',
    '%s sotto: BRIDGE_METER count=1 in_window_s=0.0 sample={"peak":0.1377,"blocks":1.0,"childPid":52388}',
    '%s sotto: CAPTION_IN start=1.68 end=2.24 final=false text="audience"',
]


def _with_prefix(caption_at_ms, **kw):
    base = datetime(2026, 11, 4, 9, 57, 24, 323000)

    def ts(ms):
        from datetime import timedelta
        return (base + timedelta(milliseconds=ms)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    offs = (100, 8120, 8531, 17400, 17420, 17900)
    return _synthetic(caption_at_ms,
                      ["%s" % (p % ts(o)) for p, o in zip(REAL_PREFIX, offs)],
                      **kw)


def neg_arm():
    cases = []

    #: AS MARCAS que a TABELA tem de achar, por caso. Um oraculo que acerta no
    #: veredicto e devolve uma tabela vazia mede metade do que promete. Duas
    #: armadilhas ja' custaram este teste: o formato real e' `"blocks":1.0` (JSON
    #: do payload) e nao `blocks=1.0`, e uma cadeia `elif` fica presa na marca que
    #: falta (ver `measure`).
    base_stages = ("spawn", "providers", "load", "capture", "block", "caption_in")

    # (nome, linhas, rc esperado, verdict esperado, marcas exigidas)
    green = _with_prefix(1200)
    cases = [("green-1.2s", green, 0, "PASS", base_stages)]

    red = _with_prefix(9000)
    cases.append(("red-9s", red, 1, "FAIL", ()))

    at_limit = _with_prefix(LIMIAR_MS)
    cases.append(("red-at-3000ms", at_limit, 1, "FAIL", ()))

    stale = _with_prefix(9000, extra_start_before=True)
    cases.append(("stale-earlier-run-win", stale, 1, "FAIL", ()))

    placeholder = _with_prefix(None, placeholder_only=True)
    cases.append(("placeholder-is-not-a-caption", placeholder, 0, "SKIPPED", ()))

    nothing = _with_prefix(None)
    cases.append(("no-caption-yet", nothing, 0, "SKIPPED", ()))

    # Sem `BRIDGE_METER` nenhum: `CAPTION_IN` e `YT_FRAME` tem de ser achados na
    # mesma. E' o mutante que a cadeia `elif` nao passava.
    base = datetime(2026, 11, 4, 9, 57, 24, 323000)

    def _t(ms):
        from datetime import timedelta
        return (base + timedelta(milliseconds=ms)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    starved = [
        "%s sotto: SHELL_STARTUP_STAGE pid=4242 stage=pre-lock" % _t(0),
        "%s sotto: BRIDGE_SPAWNED pid=52388 argv=[\"py\"]" % _t(100),
        "%s sotto: YT_FRAME src=external:youtube rows=2 lines=['a']" % _t(4500),
        "%s sotto: CAPTION_IN start=1.68 end=2.24 text=\"audience\"" % _t(9000),
        '%s sotto: CAPTION_PAINT instant=false hwnd=9 text="audience"' % _t(1200),
    ]
    cases.append(("no-meter-marks-not-starved", starved, 0, "PASS",
                  ("spawn", "caption_in", "yt_frame")))

    cases.append(("no-start-stamp", ['%s sotto: CAPTION_PAINT instant=false hwnd=9 text="x"' % _t(0)],
                  2, "SEM DADOS", ()))

    # A ROTA EXTERNA E' UMA LEGENDA (2026-11-05). Com o ASR a 9 s e o player a
    # pintar 3 palavras a 1,2 s, a PRIMEIRA legenda no ecra foi a do YouTube: um
    # oraculo que somasse so' o ASR chamaria a isto FAIL e a aceitacao do dono
    # (a legenda do YouTube aparece na hora) ficava sem portao nenhum.
    yt_wins = [
        "%s sotto: SHELL_STARTUP_STAGE pid=4242 stage=pre-lock" % _t(0),
        "%s sotto: YOUTUBE_TRACK_PAINT video_id=abc source=player window cue=- match=1 painted_words=3" % _t(1200),
        '%s sotto: CAPTION_PAINT instant=false hwnd=9 text="audience"' % _t(9000),
    ]
    cases.append(("youtube-route-beats-slow-asr", yt_wins, 0, "PASS", ("yt_paint",)))

    # ... E UMA PINTURA SEM PALAVRAS NAO E' LEGENDA. Medido nesta arvore: a linha sai
    # `painted_words=0 source=no-player-window` de 30 em 30 s com a app aberta e
    # nenhum jogador. Aceita-la por existir seria PASS a uma app que nao pintou nada.
    yt_zero = [
        "%s sotto: SHELL_STARTUP_STAGE pid=4242 stage=pre-lock" % _t(0),
        "%s sotto: YOUTUBE_TRACK_PAINT video_id=abc source=no-player-window cue=- match=0 painted_words=0" % _t(800),
    ]
    cases.append(("youtube-zero-words-is-not-a-caption", yt_zero, 0, "SKIPPED", ()))

    # UM LOG QUE NAO EXISTE NAO REPROVA A BATERIA: `:skipped` le' um rc diferente de
    # zero como FALHA, e uma worktree (ou uma maquina onde a app nunca correu) nao tem
    # `_main/webview-run.log`. Exige-se SKIPPED com rc=0 -- o mesmo que o no-data.
    missing_log = os.path.join(HERE, "__no_such_log__.log")
    if os.path.exists(missing_log):
        raise SystemExit("neg-arm: %s exists, cannot test the missing-file arm" % missing_log)
    # A SAIDA DA CHAMADA E' CAPTURADA (2026-11-04). Ela imprimia a linha
    # `TIME-TO-FIRST-CAPTION VERDICT: SKIPPED` dentro do log DESTE passo, e o
    # `_skip-verdict-guard.py` le esse byte-string em qualquer posicao: o braco
    # negativo passava a ser contado como um passo que se saltou a si proprio
    # (`SKIP-VERDICT IN THE LOG OF A STEP THAT IS NOT DECLARED SKIP-CAPABLE`).
    # O QUE o caso mede e' o rc, nao o texto -- capturar e' mais honesto do que
    # declarar o log ao guarda.
    import contextlib
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf):
        rc_missing = main(["--log", missing_log, "--json"])
    # NEM COMO TEXTO CITADO: o guarda le bytes, entao a linha capturada fica
    # capturada. Publica-se a FORMA (quantas linhas e que rc ela acompanhou).
    _quoted = _buf.getvalue().strip().splitlines()
    print("  missing-log-skips captured=%d line(s), rc=%d" % (len(_quoted), rc_missing))
    missing_ok = (rc_missing == 0)

    bad = []
    for name, lines, want_rc, want_verdict, need in cases:
        result = measure(lines)
        verdict, rc = verdict_of(result)
        ok = (rc == want_rc and verdict == want_verdict)
        if ok and need:
            missing = [m for m in need if result.get("stage_ms", {}).get(m) is None]
            if missing:
                ok = False
                name = "%s missing=%s" % (name, ",".join(missing))
        bad.append((name, ok, rc, verdict, want_rc, want_verdict))
    bad.append(("missing-log-skips", missing_ok, rc_missing, "SKIPPED", 0, "SKIPPED"))
    failed = [b for b in bad if not b[1]]
    for name, ok, rc, verdict, want_rc, want_verdict in bad:
        print("  %-30s rc=%d %-9s (want rc=%d %s) %s"
              % (name, rc, verdict, want_rc, want_verdict,
                 "ok" if ok else "MISMATCH"))
    if failed:
        print("NEG-ARM: FAIL -- %d of %d cases did not match" % (len(failed), len(bad)))
        return 1
    print("NEG-ARM: PASS -- %d/%d cases" % (len(bad), len(bad)))
    # A CONVENCAO DA BATERIA (2026-11-03, repetida 2026-11-04): um passo
    # `red-as-expected` declara rc=1. Devolver 0 aqui fazia o `:expectred`
    # publicar o passo em `failed` -- medido neste proprio ficheiro antes desta
    # linha existir -- e um braco que passa a ser contado como falha acaba
    # desligado por cansaco, nao por prova.
    return 1


def _live_staleness(log_text):
    """(stale, reason) do processo cujo arranque este log carrega.

    NASCIDO DE UMA MEDICAO (2026-11-04): a instancia viva (pid 42548, 10:06:36)
    e' ANTERIOR ao codigo que este passo julga -- `live-code-freshness-oracle
    --strict` rc=3, a etiqueta do processo nao e' a do disco. Julgar os 65 037 ms
    dela seria atribuir ao codigo de hoje um comportamento de ontem. O passo
    passa a dizer SKIPPED com a razao, e NAO verde: `skip` nao e' `pass`.
    """
    import importlib.util
    path = os.path.join(HERE, "live-code-freshness-oracle.py")
    if not os.path.exists(path):
        return (False, "live-code-freshness-oracle.py ausente")
    spec = importlib.util.spec_from_file_location("_live_code_freshness", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        shell_mod = mod.load_shell()
        verdict, detail = mod.judge(shell_mod, log_text)
    except Exception as exc:            # noqa: BLE001 -- frescura indisponivel nao e' prova
        return (False, "frescura indisponivel: %r" % (exc,))
    if verdict == "STALE":
        return (True, detail.get("why") or "STALE")
    return (False, verdict)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", default=DEFAULT_LOG, help="log to read (default: " + DEFAULT_LOG + ")")
    ap.add_argument("--pid", type=int, default=None,
                    help="judge the SHELL_STARTUP_STAGE of this shell pid instead of the last one")
    ap.add_argument("--json", action="store_true", help="emit the measurement as JSON")
    ap.add_argument("--stale-skips", action="store_true",
                    help="quando a instancia viva e' ANTERIOR ao disco, o veredicto e' "
                         "SKIPPED (rc=0) em vez de FAIL -- e o log diz por que")
    ap.add_argument("--neg-arm", action="store_true",
                    help="judge the instrument itself on synthetic logs (never touches the live file)")
    args = ap.parse_args(argv)

    if args.neg_arm:
        return neg_arm()

    try:
        with open(args.log, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        # SEM FICHEIRO NAO E' UM PORTAO QUE REPROVOU: numa maquina onde a app nunca
        # correu (ou numa worktree, que nao tem o log da sessao viva) nao ha' o que
        # medir, e o passo da bateria conta-o em `skipped=`. Um ficheiro que EXISTE e
        # nao se consegue ler continua a ser SEM DADOS (rc=2): isso e' um defeito.
        print("TIME-TO-FIRST-CAPTION: %s does not exist -- nothing to measure" % args.log)
        print("TIME-TO-FIRST-CAPTION VERDICT: SKIPPED")
        return 0
    except OSError as exc:
        print("TIME-TO-FIRST-CAPTION: cannot read %s (%s)" % (args.log, exc))
        print("TIME-TO-FIRST-CAPTION VERDICT: SEM DADOS")
        return 2

    result = measure(lines, pid=args.pid)
    if args.json:
        payload = dict(result)
        for key in ("start", "first_paint"):
            if payload.get(key) is not None:
                payload[key] = payload[key].isoformat(sep=" ")
        if payload.get("discarded_placeholder"):
            at, text = payload["discarded_placeholder"]
            payload["discarded_placeholder"] = [at.isoformat(sep=" "), text]
        payload["stages"] = {k: (v.isoformat(sep=" ") if v else None)
                             for k, v in payload.get("stages", {}).items()}
        verdict, _ = verdict_of(result)
        payload["verdict"] = verdict
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return verdict_of(result)[1]

    body = report(result)
    verdict, rc = verdict_of(result)
    if rc != 0 and args.stale_skips:
        stale, why = _live_staleness("".join(lines))
        if stale:
            body += ("\nLIVE_CODE STALE: %s\n"
                     "  o que corre nao e' este codigo -- a medicao nao julga o produto"
                     % why)
            verdict, rc = "SKIPPED", 0
            body = body.replace("TIME-TO-FIRST-CAPTION VERDICT: FAIL",
                                "TIME-TO-FIRST-CAPTION VERDICT: SKIPPED")
    print(body)
    return rc


if __name__ == "__main__":
    sys.exit(main())
