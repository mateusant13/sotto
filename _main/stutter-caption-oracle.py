# NO-BUG: alimenta as funcoes reais com uma fonte CDP FALSA que para 3-5 s; nao apanha um stutter verdadeiro da maquina nem a app viva.
"""A LEGENDA DO YOUTUBE ATRAVESSA UM STUTTER DA MAQUINA -- e este mede-a.

A ORDEM DO DONO, verbatim (2026-11-07): *"e ridiculo o fato que um stutter
qualquer do meu pc, faca a legenda dessincronizar ou nao funcionar mais ou
demorar pra voltar a ficar certa. sendo que o mecanismo do YOUTUBE devia ser
extremamente facil de implementar na legenda ao vivo e extremamente responsivo,
entao nao devia se afetar. se a porra da legenda do youtube ta se movendo, mesmo
com o stutter acontecendo, a NOSSA legenda que pegamos do youtube, TAMBEM."*

O QUE ESTE ORACULO EXECUTA -- as funcoes REAIS de `app/webview/sotto_webview.py`
(`_youtube_time`, `_yt_decide`, `yt_live_frame`, `_yt_lines`), extraidas por AST
do ficheiro que embarca e ligadas a um observador falso com uma fonte CDP falsa.
A fonte publica `video.currentTime` a 80 ms (o passo medido da fonte real) e
PARA durante a janela de stutter, enquanto o relogio do video continua a andar --
que e' exactamente a condicao do dono (o player anda, a nossa leitura nao).

  A1  stutter de 3 s: o instante com que a linha e' revelada fica a <= 150 ms do
      relogio do player em TODOS os quadros, no stutter e depois dele.
  A2  stutter de 5 s: o mesmo.
  A3  A METADE DO TEXTO: durante o stutter as palavras ja' conhecidas continuam
      a aparecer, ao ritmo do relogio de palavra do proprio payload -- o maior
      intervalo sem texto novo nao passa do maior espaco entre palavras do
      payload (+150 ms). A regra antiga esperava o snapshot seguinte e ficava
      4,5 s com o mesmo texto.
  A4  PAUSA DENTRO DA JANELA: o player publicou `paused` e a leitura morreu; a
      nossa legenda NAO anda um milissegundo (e, quando a amostra volta, o que
      nos adiantamos e' desfeito -- sem isso ela ficava a' frente para sempre).
  A5  ESTADO DESCONHECIDO: nenhuma bandeira publicada; nao se anda por inercia,
      serve-se a ultima amostra. (No app vivo o `paused` vem sempre no payload;
      a arm fixa a REGRA, nao um caminho que ele use todos os dias.)

  B1  O ESTADO PUBLICADO E' DO VIDEO QUE ELE DESCREVE -- a nossa aba esta'
      PARADA em 42,0 s e a fonte tem a OUTRA aba a tocar em 7,0 s: a legenda
      nao pode andar (e nao pode saltar para o 7,0 da outra).
  B2  O mesmo do outro lado: a nossa aba TOCA e a outra esta' parada -- o
      `paused` dela nao pode parar a nossa (nem disparar a BORDA que congela a
      pintura). O dono, verbatim (2026-11-08): *"quando eu deixo o video
      pausado, a legenda fica ao vivo, quando eu pauso, ela volta e fica
      travada em outro momento"*.
      Estas duas arms correm o `_yt_cdp_snapshot` REAL -- o sitio que publica
      `yt_cdp_clock`/`yt_cdp_paused`/`_yt_pause_epoch` -- contra uma fonte
      falsa que devolve a foto de OUTRO video (o caso medido em
      `_main/fixtures/yt-pause-foreign-state-20261108.txt`).

O ANTES e' medido, nao citado: o mesmo probe corre sobre uma COPIA do shell com
a regra antiga (`--neg-arm`, mutante M1) e sobre uma copia com o teto de 3 s na
revelacao (M2). `--neg-arm` sai 1 quando os dois mutantes caem (a convencao
`red-as-expected` desta bateria).

    python _main/stutter-caption-oracle.py            # rc 0 verde / rc 1 vermelho
    python _main/stutter-caption-oracle.py --neg-arm   # rc 1 = apanhou os mutantes
    python _main/stutter-caption-oracle.py --drift     # re-mede a deriva do relogio
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("SOTTO_ROOT")
            or Path(__file__).resolve().parent.parent).resolve()
WEBVIEW = ROOT / "app" / "webview"
SHELL = WEBVIEW / "sotto_webview.py"
PAYLOAD = ROOT / "_main" / "fixtures" / "yt-WdaHAGRBB6s.en-orig.json3"
DRIFT_FIXTURE = ROOT / "_main" / "fixtures" / "yt-paint-freeze-20261104.json"

#: O passo do desenho e o passo da leitura, os do laco vivo (`INTERVAL_S`/
#: `RENDER_S` do `ExternalCaptionWatcher`).
RENDER_S = 0.06
TICK_S = 0.30
#: O passo da fonte CDP (medido: ~12 Hz).
PUBLISH_S = 0.08
#: O orcamento do dono, e o que este ficheiro exige de cada quadro.
BUDGET_S = 0.15
#: Onde a verdade comeca na faixa (um sitio denso em palavras, sem buraco).
T_START = 7.84
#: Quanto da graca real se usa (stutter de 5 s + aquecimento + recuperacao).
REAL_SPAN_S = 11.0
#: Aquecimento antes do stutter (o laco tem de estar estavel para o medir).
WARMUP_S = 2.0

rows = []


def add(ok, name, detail=""):
    rows.append((bool(ok), name, str(detail)[:220]))


# --------------------------------------------------------------------------
# A deriva MEDIDA do relogio do player -- e o numero que justifica o teto
# --------------------------------------------------------------------------
def measure_drift(path=DRIFT_FIXTURE, windows=((3.0, 5.0), (5.0, 8.0))):
    """`{janela: (n, mediana, p95, maximo)}` do erro de extrapolar o relogio.

    Cada par de amostras reais a uma distancia na janela da' `dt_video - dt_wall`
    (os saltos > 0,5 s sao seeks/pausas e ficam de fora -- o que se mede e' a
    PRECISAO de contar, nao a de adivinhar um seek).
    """
    out = {}
    try:
        doc = json.load(io.open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return out
    samples = doc.get("samples") or []
    for lo, hi in windows:
        errs = []
        for i in range(len(samples)):
            wi, ti = samples[i]["wall"], samples[i]["t"]
            for j in range(i + 1, len(samples)):
                dw = samples[j]["wall"] - wi
                if dw < lo:
                    continue
                if dw > hi:
                    break
                e = (samples[j]["t"] - ti) - dw
                if abs(e) <= 0.5:
                    errs.append(abs(e))
        if errs:
            errs.sort()
            out[(lo, hi)] = (len(errs), statistics.median(errs),
                             errs[int(0.95 * (len(errs) - 1))], errs[-1])
    return out


# --------------------------------------------------------------------------
# A VERDADE: o relogio REAL do player, gravado da Chrome do dono
# --------------------------------------------------------------------------
def real_clock(path=DRIFT_FIXTURE, span=REAL_SPAN_S):
    """`[(wall_rel, t_rel)]` de um trecho CONTINUO de reproducao real.

    A verdade deste oraculo NAO e' `t0 + (agora - t0)`: seria a nossa propria
    formula, e a arm passaria por construcao. Sao as 745 amostras de
    `video.currentTime` + relogio de parede gravadas na Chrome do dono
    (2026-11-04), onde o relogio do player tem a sua propria deriva de 1-34 ms.
    """
    try:
        doc = json.load(io.open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return []
    samples = doc.get("samples") or []
    series = []
    for sample in samples:
        if sample.get("paused"):
            break
        if series:
            step = sample["wall"] - series[-1][0]
            if step <= 0:
                continue
            # O desvio e' ACUMULADO: o seek aparece como um salto em relacao a'
            # parede desde o inicio do trecho, nao em relacao ao passo anterior.
            if abs((sample["t"] - series[0][1])
                   - (sample["wall"] - series[0][0])) > 0.5:
                break

        series.append((float(sample["wall"]) - float(samples[0]["wall"]),
                       float(sample["t"])))
        if series[-1][0] >= span:
            break
    if len(series) < 10 or series[-1][0] < span * 0.8:
        return []
    base = series[0][1]
    return [(w, t - base) for w, t in series]


def at(series, x):
    """`t` do relogio real em `x` segundos de parede, por interpolacao."""
    if not series:
        return x
    if x <= series[0][0]:
        return series[0][1]
    for (w0, t0), (w1, t1) in zip(series, series[1:]):
        if w0 <= x <= w1:
            if w1 <= w0:
                return t1
            return t0 + (t1 - t0) * (x - w0) / (w1 - w0)
    w1, t1 = series[-1]
    return t1 + (x - w1)


# --------------------------------------------------------------------------
# O observador falso e a fonte CDP falsa
# --------------------------------------------------------------------------
class Clock:
    """`time.monotonic()` que o probe move a mao."""

    now = 100.0

    def monotonic(self):
        return Clock.now

    def sleep(self, _s):
        return None


#: UMA instancia: os metodos extraidos chamam `time.monotonic()`.
CLOCK = Clock()

LOGS = []


def _log(msg):
    LOGS.append(str(msg))


class Player:
    """O estado que o `_yt_cdp_snapshot` real escreve, e nada mais.

    `playing` e' o campo novo: `None` = o payload nao falou de pausa.
    """

    YT_ANCHOR_MAX_S = 3.0
    RENDER_S = RENDER_S
    INTERVAL_S = TICK_S

    def __init__(self, track):
        self.yt_cdp_clock = None
        self.yt_cdp_rate = 1.0
        self.yt_cdp_paused = False
        self.yt_cdp_ended = False
        self.yt_cdp_playing = None
        self.yt_serve_floor = None
        self.yt_held_logged = None
        self._yt_guess_s = 0.0
        self._yt_clock_last = None
        self._yt_clock_prev = None
        self._yt_clock_dur = None
        self._yt_anchor = None
        self._yt_track = track
        self._yt_stall_logged = None
        # O QUE O `_yt_cdp_snapshot` REAL CHAMA (2026-11-12). O `_yt_clock_moving`
        # entrou no shell para desmentir a bandeira `paused` com o relogio a andar,
        # e o `_yt_cdp_snapshot` passou a chama-lo -- o corpo e' extraido do fonte
        # REAL no `main()` deste oraculo, logo a linha `fn_snap(...)` chamava um
        # metodo que este stub nao tinha: `AttributeError: 'ForeignPlayer' object
        # has no attribute '_yt_clock_moving'`. Um stub que so' tem os campos que a
        # versao anterior do chamador usava e' um stub que apodrece a cada cura do
        # chamador (a classe do `FakeReader` sem `shed()`).
        self._yt_mv = None
        self._yt_mv_logged = False
        self._yt_pause_epoch_seen = 0
        self._yt_mv_now = 0.0

    def _yt_clock_moving(self, snap, now=None):
        """A leitura de MOVIMENTO, `(andou, rate)` -- o contrato REAL do shell."""
        prev = self._yt_mv
        now_v = self._yt_mv_now if now is None else float(now)
        mov = 0.0
        if snap.get('t') is not None:
            mov = float(snap.get('t') or 0.0)
        if prev is None:
            self._yt_mv = (mov, now_v)
            return False, 0.0
        dt = now_v - float(prev[1])
        delta = mov - float(prev[0] or 0.0)
        self._yt_mv = (mov, now_v)
        if dt <= 0.0 or delta < 0.0:
            return False, 0.0
        rate = delta / dt
        return rate >= 0.05, rate

    def _yt_prof(self, *_a, **_k):
        return None


def extract(source, names):
    """Os corpos de `names` no ficheiro, por AST (a classe e' a que os tiver)."""
    tree = ast.parse(source)
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for sub in node.body:
            if isinstance(sub, ast.FunctionDef) and sub.name in names:
                found[sub.name] = ast.get_source_segment(source, sub)
        if found:
            return found
    return found


#: Os metodos REAIS que o `build` extrai -- a fonte UNICA do que o observador
#: falso sabe fazer. O `_yt_cdp_snapshot` chama este conjunto no objecto (e so'
#: este), e a lista cresceu com o caminho, cada entrada nascida de um
#: `AttributeError` MEDIDO dentro de um braco:
#:   2026-11-10 `_yt_clock_static`/`_yt_pause_edge` (o relogio parado e a borda
#:              da pausa passaram a ser publicados pelo snapshot),
#:   2026-11-11 `_yt_rate_tick` (a telemetria do `YOUTUBE_LOOP_HZ`).
#: As duas ultimas so' correm quando o snapshot PUBLICA o estado (`declared`
#: casa com a foto); o B1/B2 positivo nunca as alcança, mas o mutante M3 -- que
#: e' exactamente "publica o estado de qualquer foto" -- alcanca, e era ali que
#: o mutante era dado por apanhado por um CRASH em vez de por um numero errado.
EXTRACTED = ("_youtube_time", "_yt_decide", "yt_live_frame", "_yt_lines",
             "_yt_rate_tick", "_yt_cdp_snapshot",
             "_yt_clock_static", "_yt_pause_edge")

#: As constantes de CLASSE que os corpos extraidos leem em `self`. Vao para o
#: objecto pelo `bind`, com o valor lido do ficheiro: o duplo nao pode medir um
#: limiar que a producao ja' mudou (`CLOCK_STATIC_PAUSE_S` decide o "relogio
#: parado" e um 3,0 s copiado aqui mediria outra regra em silencio).
#: As constantes de CLASSE que o observador falso tem de ter. Cada entrada nasceu
#: de um `AttributeError` medido dentro de um braco -- a mesma classe do `_yt_clock_moving`
#: no `Player`, agora do lado dos literais:
#:   2026-11-15 `PAUSE_BLANK_DWELL_S`: o dwell da pausa passou a ser lido por
#:              `self.PAUSE_BLANK_DWELL_S` no corpo REAL do `_yt_pause_edge`, e o
#:              `ForeignPlayer` do braco B1/B2 nao o tinha -- o mutante M3 era dado
#:              por apanhado por um CRASH (`AttributeError`) em vez de por um numero
#:              errado, que e' exactamente a doenca que o comentario do `EXTRACTED`
#:              descreve. O positivo nunca o alcançava: so' o M3 conduz essa borda.
CLASS_CONSTS = ("CLOCK_STATIC_PAUSE_S", "PAUSE_BLANK_DWELL_S")


def _literal(source, name):
    """O literal de `NAME = ...`, de modulo OU de corpo de classe, por AST."""
    tree = ast.parse(source)
    scopes = [tree.body]
    scopes += [node.body for node in tree.body if isinstance(node, ast.ClassDef)]
    for body in scopes:
        for node in body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == name:
                        try:
                            return ast.literal_eval(node.value)
                        except ValueError:
                            break
    raise SystemExit('ORACLE-BROKEN: %s nao define %s' % (SHELL.name, name))


def bind(ns, player):
    """Liga ao observador os metodos REAIS extraidos -- num so' sitio.

    Devolve o mesmo objecto, para o chamador encadear. Um nome que o `build` nao
    extraiu fica AUSENTE de proposito: o braco tem de morrer alto, e nao herdar
    um `0` que finge de metodo.
    """
    for name in EXTRACTED:
        fn = ns.get(name)
        if fn is not None:
            setattr(player, name, fn.__get__(player, type(player)))
    for name in CLASS_CONSTS:
        setattr(player, name, ns['_' + name])
    return player


def build(source):
    """O namespace com `time`/`log` e as funcoes REAIS ligadas ao observador."""
    if str(WEBVIEW) not in sys.path:
        sys.path.insert(0, str(WEBVIEW))
    bodies = extract(source, EXTRACTED)
    ns = {"time": Clock, "log": _log, "os": os,
          # `_yt_mark` e' um helper de MODULO (perfil de fase); aqui so' precisa
          # de nao rebentar, nao de medir nada.
          "_yt_mark": lambda *_a, **_k: None,
          # A JANELA DO `YOUTUBE_LOOP_HZ` E' DESTE NUMERO (2026-11-11). O corpo
          # REAL do `_yt_rate_tick` fecha a janela do log com ele; sem a
          # constante o `NameError` cairia no `except` do proprio metodo e a
          # telemetria ficaria MUDA -- indistinguivel de um duplo que nao corre.
          # Vem do ficheiro por AST, nao de um literal copiado para aqui.
          "_YT_RATE_LOG_S": _literal(source, "_YT_RATE_LOG_S")}
    for name in CLASS_CONSTS:
        ns['_' + name] = _literal(source, name)
    for name, body in bodies.items():
        module = ast.Module(body=[ast.parse(body).body[0]], type_ignores=[])
        exec(compile(module, "<%s>" % name, "exec"), ns)
    return ns, bodies


class FakeSource:
    """A fonte CDP falsa: UMA foto, sempre a mesma, de UM video.

    `selected_video_id` devolve o MESMO id da foto: e' assim que o app vivo se
    comporta (medido -- 2 recusas `refused=video-mismatch` em toda a historia
    do log, ambas em 2026-11-03), portanto o snapshot NAO e' recusado e o que
    se mede e' o estado que ele publica.
    """

    def __init__(self, video_id, t, paused, rate=1.0):
        self.video_id = video_id
        self.snap = {"videoId": video_id, "t": t, "paused": paused,
                     "ended": False, "rate": rate, "rows": ["uma linha"],
                     "items": [{"text": "uma linha"}], "stamp": 0.0,
                     "why": "painted"}

    def snapshot(self, max_age=None):
        return dict(self.snap)

    def selected_video_id(self):
        return self.video_id


class ForeignPlayer(Player):
    """O observador com o que o `_yt_cdp_snapshot` real precisa de ter ao lado."""

    def __init__(self, track, declared, source):
        Player.__init__(self, track)
        self.yt_video_id = declared
        self._yt_cdp_source = source
        self._yt_diag = None
        self._yt_rate = None
        self.yt_cdp_mismatch_logged = None
        self._yt_pause_epoch = 0
        self._yt_was_paused = False
        self.shell = None

    def _yt_cdp_ensure(self, *_a):
        return self._yt_cdp_source

    def _yt_mark(self, *_a):
        return None


def foreign_state_arm(ns, track):
    """B1/B2 -- `_yt_cdp_snapshot` REAL contra a foto de OUTRO video.

    Devolve as duas medidas; a arm julga-as em `arms()`.
    """
    fn_snap = ns["_yt_cdp_snapshot"].__get__
    fn_time = ns["_youtube_time"].__get__

    # B1 -- a NOSSA aba publicou PARADO em 42,0 e a fonte tem a OUTRA a tocar.
    Clock.now = 300.0
    p = bind(ns, ForeignPlayer(track, "OURS", FakeSource("OTHER", t=7.0, paused=False)))
    p.yt_cdp_clock = (42.0, Clock.now)
    p.yt_cdp_paused = True
    p.yt_cdp_ended = False
    p.yt_cdp_playing = False
    fn_snap(p, ForeignPlayer)(None, None, None, declared="OURS")
    Clock.now = 301.0
    b1_t = fn_time(p, ForeignPlayer)(None, None, None, None)
    b1 = {"t": b1_t, "paused": bool(p.yt_cdp_paused),
          "clock_t": (p.yt_cdp_clock or (None,))[0]}

    # B2 -- a NOSSA aba TOCA em 42,0 e a fonte tem a OUTRA parada em 7,0.
    Clock.now = 400.0
    q = bind(ns, ForeignPlayer(track, "OURS", FakeSource("OTHER", t=7.0, paused=True)))
    q.yt_cdp_clock = (42.0, Clock.now)
    q.yt_cdp_paused = False
    q.yt_cdp_ended = False
    q.yt_cdp_playing = True
    fn_snap(q, ForeignPlayer)(None, None, None, declared="OURS")
    Clock.now = 401.0
    b2_t = fn_time(q, ForeignPlayer)(None, None, None, None)
    b2 = {"t": b2_t, "paused": bool(q.yt_cdp_paused),
          "epoch": int(getattr(q, "_yt_pause_epoch", 0)),
          "clock_t": (q.yt_cdp_clock or (None,))[0]}
    return b1, b2


# --------------------------------------------------------------------------
# O probe: um stutter de `stall_s` segundos, medido quadro a quadro
# --------------------------------------------------------------------------
def probe(ns, track, stall_s, *, paused=False, unknown=False, mutate=None,
          series=None):
    """Corre o laco e devolve as medidas do stutter.

    `paused`  -- o player publica `paused=True` no instante em que pausa (a
                 amostra e' a ULTIMA que a fonte entrega);
    `unknown` -- nenhuma bandeira e' publicada (nem `paused`);
    `mutate`  -- `fn(t_used, elapsed)` aplicado ao instante do quadro: e' por
                 aqui que os mutantes reintroduzem o teto antigo.
    """
    if series is None:
        series = real_clock()
    Clock.now = 100.0
    del LOGS[:]
    ns["time"] = CLOCK
    player = bind(ns, Player(track))
    fn_time = ns["_youtube_time"].__get__(player, Player)
    fn_decide = ns["_yt_decide"].__get__(player, Player)
    fn_live = ns["yt_live_frame"].__get__(player, Player)
    real_lines = ns["_yt_lines"].__get__(player, Player)
    seen = {}

    def spy(track_, t):
        seen["t"] = t
        return real_lines(track_, t)

    player._yt_lines = spy
    mono0 = Clock.now
    stall_at = mono0 + WARMUP_S
    stall_end = stall_at + stall_s

    def truth(now):
        # O RELOGIO DO PLAYER: o gravado. Parado quando o player pausou.
        x = (stall_at if (paused and now >= stall_at) else now) - mono0
        return T_START + at(series, min(max(0.0, x), series[-1][0]))

    next_pub = mono0
    next_tick = mono0 + TICK_S
    next_frame = mono0 + RENDER_S
    frames, ticks = [], []
    none_after = 0
    now = mono0
    while now <= stall_end + 2.0:
        Clock.now = now
        in_stall = stall_at < now < stall_end
        if now >= next_pub and not in_stall:
            player.yt_cdp_clock = (truth(now), now)
            player.yt_cdp_paused = bool(paused and now >= stall_at - 0.02)
            player.yt_cdp_ended = False
            player.yt_cdp_playing = (None if unknown
                                     else not player.yt_cdp_paused)
            next_pub = now + PUBLISH_S
        if now >= next_tick:
            served = fn_decide(fn_time(None, None, None, None))
            if served is not None:
                player._yt_anchor = (float(served), now)
                ticks.append((now, float(served), truth(now)))
            next_tick = now + TICK_S
        if now >= next_frame:
            frame = fn_live()
            if frame is None:
                if now - stall_at > player.YT_ANCHOR_MAX_S:
                    none_after += 1
            elif "t" in seen:
                t_used = float(seen["t"])
                if mutate is not None:
                    t_used = mutate(t_used, now - player._yt_anchor[1])
                text = "\x1f".join(str(x) for x in (frame[1] or ()))
                frames.append((now, t_used, truth(now), text))
            next_frame = now + RENDER_S
        now = round(now + 0.02, 4)

    def worst(lo, hi):
        vals = [abs(t - tr) for (n, t, tr, _x) in frames if lo <= n < hi]
        return max(vals) if vals else 0.0

    # O avanco conta a partir de UM tick depois da borda: e' a cadencia do laco
    # (300 ms), nao um numero escolhido -- antes disso a amostra de pausa ainda
    # nao foi lida por ninguem.
    inside = [(n, t, tr, x) for (n, t, tr, x) in frames
              if stall_at + TICK_S <= n < stall_end]
    advance = (max(t for (_n, t, _tr, _x) in inside)
               - min(t for (_n, t, _tr, _x) in inside)) if inside else 0.0
    texts = [(n, x) for (n, _t, _tr, x) in inside]
    gap, last = 0.0, None
    for n, x in texts:
        if last is None:
            gap = max(gap, n - stall_at)
            last = (n, x)
        elif x != last[1]:
            gap = max(gap, n - last[0])
            last = (n, x)
    if last is not None:
        gap = max(gap, min(stall_end, stall_end) - last[0])
    changes = sum(1 for (a, b) in zip(texts, texts[1:]) if a[1] != b[1])
    live = [abs(t - tr) for (_n, t, tr, _x) in frames]
    tick = [abs(sv - tr) for (_n, sv, tr) in ticks]
    return {
        "stall_s": stall_s,
        "max_live_err": max(live) if live else 0.0,
        "max_tick_err": max(tick) if tick else 0.0,
        "stall_err": worst(stall_at, stall_end),
        # A recuperacao conta a partir de UM tick depois da borda: antes disso a
        # amostra nova ainda nao foi lida por ninguem, e o laco tem 300 ms.
        "recovery_err": worst(stall_end + TICK_S, stall_end + 2.0),
        "advance_stall": advance,
        "frames": len(frames),
        "none_after_3s": none_after,
        "text_gap_s": gap,
        "text_changes": changes,
        "text_at_end": texts[-1][1] if texts else "",
    }


def anchor_arm(ns, track):
    """As duas metades da regra do ancora, sem laco: 4 s depois da leitura."""
    player = bind(ns, Player(track))
    fn_live = ns["yt_live_frame"].__get__(player, Player)
    player._yt_lines = ns["_yt_lines"].__get__(player, Player)
    Clock.now = 200.0
    base = T_START + 9.0
    player._yt_anchor = (base, Clock.now)
    player.yt_cdp_paused = False
    player.yt_cdp_ended = False
    player.yt_cdp_playing = True
    fresh = fn_live()
    player._yt_anchor = (base, Clock.now - 4.0)
    playing = fn_live()
    player.yt_cdp_playing = None
    unknown = fn_live()

    def words(frame):
        return len(" ".join(str(x) for x in (frame or (None, []))[1] or ()).split())

    return {"fresh_words": words(fresh), "playing_words": words(playing),
            "playing_frame": playing, "unknown_frame": unknown}


def payload_max_word_gap(track, lo, hi):
    """O maior espaco entre duas palavras do PAYLOAD na janela `[lo, hi]`."""
    starts = sorted(float(w["start"]) for cue in track.get("cues") or ()
                    for w in (cue.get("words") or ()))
    inside = [s for s in starts if lo <= s <= hi]
    if len(inside) < 2:
        return float(hi - lo)
    return max(b - a for a, b in zip(inside, inside[1:]))


# --------------------------------------------------------------------------
# A tabela e as arms
# --------------------------------------------------------------------------
def row_line(tag, r):
    return ("  %-8s stutter=%.0fs  erro_max_quadro=%.3fs  erro_tick=%.3fs  "
            "erro_fim=%.3fs  erro_recuperacao=%.3fs  avancou=%.2fs  "
            "texto_mudo=%.2fs  mudancas=%d" % (tag, r["stall_s"],
                                                r["max_live_err"],
                                                r["max_tick_err"],
                                                r["stall_err"],
                                                r["recovery_err"],
                                                r["advance_stall"],
                                                r["text_gap_s"],
                                                r["text_changes"]))


def arms(ns, track, old_ns):
    out = []
    for stall_s in (3.0, 5.0):
        r = probe(ns, track, stall_s)
        out.append(r)
    # A1/A2 -- o relogio
    for r in out:
        tag = "A%d" % (1 if r["stall_s"] == 3.0 else 2)
        add(r["max_live_err"] <= BUDGET_S and r["max_tick_err"] <= BUDGET_S,
            "%s stutter de %.0f s: o instante da legenda fica a <= %d ms do "
            "player" % (tag, r["stall_s"], int(BUDGET_S * 1000)),
            "quadro=%.0f ms tick=%.0f ms" % (1000 * r["max_live_err"],
                                             1000 * r["max_tick_err"]))
        add(r["stall_err"] <= BUDGET_S and r["recovery_err"] <= BUDGET_S,
            "%s sem periodo de recuperacao (fim=%.3fs, +2s=%.3fs)"
            % (tag, r["stall_err"], r["recovery_err"]), "")
    # A3 -- o texto
    r5 = out[-1]
    lo = T_START + WARMUP_S
    bound = payload_max_word_gap(track, lo, lo + 5.0) + BUDGET_S
    add(r5["text_gap_s"] <= bound and r5["text_changes"] >= 4,
        "A3 durante o stutter de 5 s o texto CONTINUA a revelar",
        "maior pausa %.2f s (limite %.2f s = espaco de palavra do payload) "
        "mudancas=%d" % (r5["text_gap_s"], bound, r5["text_changes"]))

    # A4 -- pausa dentro da janela
    p = probe(ns, track, 3.0, paused=True)
    add(p["advance_stall"] <= 0.001,
        "A4 player pausou: a legenda nao anda um milissegundo",
        "andou %.3f s durante o stutter (texto=%r)"
        % (p["advance_stall"], p["text_at_end"][-40:]))
    add(p["text_changes"] == 0,
        "A4 e nao revela palavra nenhuma com o video parado",
        "mudancas=%d" % (p["text_changes"],))

    # A5 -- estado desconhecido (a regra: nao se adivinha)
    u = probe(ns, track, 5.0, unknown=True)
    add(u["advance_stall"] <= 0.001,
        "A5 sem bandeira publicada: serve a ultima amostra, nao adivinha",
        "andou %.3f s durante o stutter" % (u["advance_stall"],))
    add(u["text_changes"] == 0,
        "A5 e sem resposta a linha nao cresce por inercia",
        "mudancas=%d" % (u["text_changes"],))

    # A6 -- a regra do ancora, chamada directamente nas duas metades
    a = anchor_arm(ns, track)
    add(a["playing_frame"] is not None and a["playing_words"] > a["fresh_words"],
        "A6 'a andar': passados 4 s a revelacao AVANCOU (o ancora conta)",
        "palavras %d -> %d" % (a["fresh_words"], a["playing_words"]))
    add(a["unknown_frame"] is None,
        "A6 'sem resposta': o ancora expira e a linha nao e' recomposta",
        repr(a["unknown_frame"])[:80])

    # B1/B2 -- o estado publicado tem de ser do video que ele descreve
    b1, b2 = foreign_state_arm(ns, track)
    add(b1["t"] is not None and abs(b1["t"] - 42.0) <= 0.001,
        "B1 a NOSSA aba esta' parada: a foto da OUTRA (a tocar) nao move "
        "a nossa legenda",
        "t=%.2f (esperado 42.00) paused_publicado=%s clock=%.2f"
        % (b1["t"] if b1["t"] is not None else -1.0, b1["paused"],
           b1["clock_t"] if b1["clock_t"] is not None else -1.0))
    add(b2["t"] is not None and abs(b2["t"] - 43.0) <= 0.001,
        "B2 a NOSSA aba toca: a foto da OUTRA (parada) nao congela nem "
        "salta a nossa",
        "t=%.2f (esperado 43.00) paused_publicado=%s epoch=%d clock=%.2f"
        % (b2["t"] if b2["t"] is not None else -1.0, b2["paused"],
           b2["epoch"], b2["clock_t"] if b2["clock_t"] is not None else -1.0))
    add(b2["epoch"] == 0 and not b2["paused"],
        "B2 e a pausa da OUTRA aba nao dispara a BORDA que congela a "
        "pintura",
        "epoch=%d paused=%s" % (b2["epoch"], b2["paused"]))

    # O ANTES, medido com a regra antiga -- e o que prova que as arms tem dentes
    before = [probe(old_ns, track, s) for s in (3.0, 5.0)]
    for r in before:
        add(r["max_live_err"] > BUDGET_S,
            "ANTES medido: a regra antiga estoura o orcamento num stutter de "
            "%.0f s" % (r["stall_s"],),
            "erro=%.2f s texto_mudo=%.2f s" % (r["max_live_err"], r["text_gap_s"]))
    add(before[-1]["text_gap_s"] > bound,
        "ANTES medido: o texto espera pelo snapshot (mudo %.2f s)"
        % (before[-1]["text_gap_s"],), "")
    return out, before


def _load_track():
    import importlib.util as ilu
    if str(WEBVIEW) not in sys.path:
        sys.path.insert(0, str(WEBVIEW))
    spec = ilu.spec_from_file_location("yc_oracle_stutter",
                                       str(WEBVIEW / "youtube_captions.py"))
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cues = mod.parse_json3(io.open(PAYLOAD, encoding="utf-8").read())
    return {"cues": cues, "lang": "en-orig", "duration": cues[-1]["end"]}


OLD_INSTANT = '''
def _old_instant(player, base_t, age, rate=None, hold=None):
    """A REGRA ANTIGA, palavra por palavra: `base_t + min(age, 0.5)`.

    E' o teto plano que a ordem do dono nomeia. Nao reproduz a segunda metade
    antiga (a queda para o relogio do UIA quando a amostra tinha mais de 2 s) --
    essa precisa do UIA inteiro, e no cenario do dono (stutter da maquina) o UIA
    tambem nao responde. O que se mede aqui e' o TETO.
    """
    if base_t is None:
        return None, False
    return float(base_t) + min(max(0.0, float(age)), 0.5), False
'''


def neg_arm(source, track):
    """Os tres mutantes, cada um numa COPIA do ficheiro. rc 1 = os tres caem.

    M1 -- o teto plano de 0,5 s no lugar da regra (a metade do RELOGIO).
    M2 -- a linha lida na ultima AMOSTRA em vez do relogio extrapolado: e' o
          "espera o snapshot seguinte" da metade do TEXTO.
    M3 -- o `_yt_cdp_snapshot` de ANTES de 2026-11-08: publica
          `yt_cdp_clock`/`yt_cdp_paused`/`_yt_pause_epoch` de qualquer foto,
          inclusive a de OUTRO video (B1/B2).
    """
    bound = payload_max_word_gap(track, T_START + WARMUP_S,
                                 T_START + WARMUP_S + 5.0) + BUDGET_S

    def run(mutant, tag):
        if mutant == source:
            print("NEG-ARM %s: NAO MUTOU -- a string do mutante nao existe no "
                  "shell; o braco nao mediu nada" % tag)
            return []
        ns, _bodies = build(mutant)
        ns.update({"time": CLOCK, "log": _log})
        if "_old_instant(" in mutant:
            exec(compile(OLD_INSTANT, "<old-instant>", "exec"), ns)
        red = []
        for stall_s in (3.0, 5.0):
            r = probe(ns, track, stall_s)
            tag_arm = "A%d" % (1 if stall_s == 3.0 else 2)
            if r["max_live_err"] > BUDGET_S or r["max_tick_err"] > BUDGET_S:
                red.append("%s(erro=%.2fs)" % (tag_arm, r["max_live_err"]))
            if r["text_gap_s"] > bound:
                red.append("A3 texto mudo %.2fs no stutter de %.0f s"
                           % (r["text_gap_s"], stall_s))
        rp = probe(ns, track, 3.0, paused=True)
        if rp["advance_stall"] > 0.001 or rp["text_changes"] > 0:
            red.append("A4(andou=%.2fs, mudancas=%d)"
                       % (rp["advance_stall"], rp["text_changes"]))
        ru = probe(ns, track, 5.0, unknown=True)
        if ru["advance_stall"] > 0.001:
            red.append("A5(andou=%.2fs)" % (ru["advance_stall"],))
        b1, b2 = foreign_state_arm(ns, track)
        if b1["t"] is None or abs(b1["t"] - 42.0) > 0.001:
            red.append("B1(andou para t=%s com a NOSSA aba parada)"
                       % (("%.2f" % b1["t"]) if b1["t"] is not None else "None"))
        if b2["t"] is None or abs(b2["t"] - 43.0) > 0.001:
            red.append("B2(t=%s em vez de 43.00)"
                       % (("%.2f" % b2["t"]) if b2["t"] is not None else "None"))
        if b2["epoch"] != 0 or b2["paused"]:
            red.append("B2(borda falsa epoch=%d paused=%s)"
                       % (b2["epoch"], b2["paused"]))
        print("NEG-ARM %s: %s" % (tag, ", ".join(red) or "NADA VERMELHO"))
        return red

    red1 = run(source.replace("youtube_clock.sample_instant(", "_old_instant("),
               "M1 teto plano de 0,5 s")
    red2 = run(source.replace(
        "lines = self._yt_lines(track, t)",
        "lines = self._yt_lines(track, (getattr(self, 'yt_cdp_clock', None)"
        " or (t,))[0])"), "M2 a linha espera o snapshot")
    red3 = run(source.replace(
        "if not (declared and seen and seen != declared):",
        "if True:  # M3: publica o estado de qualquer foto"),
        "M3 estado publicado de OUTRO video")
    if red1 and red2 and red3:
        print("NEG-ARM PASS -- RED as designed:\n  M1: %s\n  M2: %s\n  M3: %s"
              % (", ".join(red1), ", ".join(red2), ", ".join(red3)))
        return 1
    print("NEG-ARM FAIL -- um dos mutantes sobreviveu: o instrumento nao tem "
          "dentes para todas as arms")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--neg-arm", action="store_true",
                    help="muta uma COPIA do shell e exige as arms RED (rc 1).")
    ap.add_argument("--drift", action="store_true",
                    help="re-mede a deriva do relogio do player e sai.")
    args = ap.parse_args(argv)

    drift = measure_drift()
    if drift:
        print("DERIVA MEDIDA do relogio do player (%s, %d amostras reais):"
              % (DRIFT_FIXTURE.name,
                 len(json.load(io.open(DRIFT_FIXTURE, encoding="utf-8"))
                     .get("samples") or ())))
        for (lo, hi), (n, med, p95, mx) in drift.items():
            print("  janela %.0f-%.0f s: n=%d  |erro| mediana %.1f ms  p95 "
                  "%.1f ms  maximo %.1f ms" % (lo, hi, n, 1000 * med,
                                                1000 * p95, 1000 * mx))
    if args.drift:
        return 0 if drift else 2
    if not SHELL.exists() or not PAYLOAD.exists():
        print("STUTTER-CAPTION NO-VERDICT -- falta %s ou %s"
              % (SHELL, PAYLOAD))
        return 2
    source = io.open(SHELL, encoding="utf-8").read()
    track = _load_track()
    if args.neg_arm:
        return neg_arm(source, track)

    ns, bodies = build(source)
    missing = [n for n in ("_youtube_time", "_yt_decide", "yt_live_frame",
                           "_yt_lines", "_yt_cdp_snapshot") if n not in bodies]
    if missing:
        print("STUTTER-CAPTION NO-VERDICT -- nao extraidas de %s: %s"
              % (SHELL.name, ", ".join(missing)))
        return 2

    # O estado da arte da regra, lido do modulo que decide (nada citado de memoria)
    if str(WEBVIEW) not in sys.path:
        sys.path.insert(0, str(WEBVIEW))
    import youtube_clock
    print("REGRA: hold=%.1f s (contrato: o stutter de 5 s x 1,6) | deriva "
          "medida=%.0f ms em %.0f s -> o relogio sozinho permitiria %.0f s | "
          "orcamento=%.0f ms"
          % (youtube_clock.HOLD_S, 1000 * youtube_clock.DRIFT_MEASURED_S,
             youtube_clock.DRIFT_WINDOW_S, youtube_clock.MAX_HOLD_BY_DRIFT_S,
             1000 * youtube_clock.BUDGET_S))

    old_ns, _ = build(source.replace("youtube_clock.sample_instant(",
                                     "_old_instant("))
    old_ns.update({"time": CLOCK, "log": _log})
    exec(compile(OLD_INSTANT, "<old-instant>", "exec"), old_ns)

    after, before = arms(ns, track, old_ns)
    print("\nANTES (regra do teto plano de 0,5 s / revelacao presa ao snapshot):")
    for r in before:
        print(row_line("antigo", r))
    print("DEPOIS (o estado publicado decide a tolerancia):")
    for r in after:
        print(row_line("novo", r))

    failed = [n for ok, n, _d in rows if not ok]
    for ok, name, detail in rows:
        print("%s %s%s" % ("PASS" if ok else "FAIL", name,
                           ("   [" + detail + "]") if detail and not ok else ""))
    print("\nSTUTTER-CAPTION %s -- arms=%d pass=%d fail=%d (rc=%d)"
          % ("GREEN" if not failed else "VERMELHO", len(rows),
             len(rows) - len(failed), len(failed), 1 if failed else 0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
