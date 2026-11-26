"""A LEGENDA NAO RECUA NO TEMPO -- o instrumento da queixa de 2026-10-30.

A queixa do dono, verbatim: *"a legenda nao ta sincronizada direito. e parece
que repete a legenda de instantes atras no ao vivo, depois desbuga, e mostra ao
vivo"*.

O que este oraculo mede, e nada mais:

  ARMS DE REGRA (puros, sem app): `youtube_monotonic.decide` nunca serve um
  instante atras do chao, e `advance` so' desce o chao num seek a serio.

  ARM DE REPLAY (o log real): as linhas `YOUTUBE_CAPTION` de
  `_main/webview-run.log` sao corridas pela regra. A regra ANTIGA (servir
  sempre a leitura do relogio) tem de produzir recuos; a regra NOVA tem de
  produzir ZERO. Os dois numeros sao re-medidos a cada corrida -- nenhum e'
  citado de memoria.

  ARM DE LIGACAO (o codigo vivo): `sotto_webview.py` e' lido por AST -- os
  dois ramos que escolhem a cue por um relogio tem de passar por `_yt_decide`
  ANTES de `cue_at`, e os tres pontos de servico tem de subir o chao. Um
  comentario que diga a regra nao conta.

Exit: 0 = o que a ordem pede esta' medido; 1 = recua; 2 = nao ha medicao.
"""
# NO-BUG: instrumento da queixa do dono de 2026-10-30 (*"a legenda ... repete a
# legenda de instantes atras no ao vivo"*). MEDIDO no log dele: 129 das 2126
# linhas `YOUTUBE_CAPTION` serviam uma cue ANTERIOR a anterior, ate' 359 s
# atras, e a cue `start=34.239` foi servida tres vezes em 24 s. A regra antiga
# nesta mesma arvore recua 157 vezes (pior 310,68 s); a nova recua 0. Sem este
# braco, "a legenda nao recua" seria uma afirmacao e nao uma medicao.
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WEBVIEW = os.path.join(REPO, "app", "webview")
MONO = os.path.join(WEBVIEW, "youtube_monotonic.py")
SHELL = os.path.join(WEBVIEW, "sotto_webview.py")
LOG = os.path.join(HERE, "webview-run.log")

#: Quantas vezes a regra ANTIGA tem de recuar para a arm8 ter dentes. O numero
#: e' o que separa "a regra nova nao recua porque nao tem o que recuar" de "a
#: regra nova nao recua porque a regra antiga recuava e ela nao" -- e por isso
#: e' medido no corpus COMMITADO: o log do dono roda e um piso lido de um
#: ficheiro que roda fica vermelho por rotacao (medido 2026-11-05: 3 recuos
#: contra os 157 do corpus commitado).
TEETH_FLOOR = 10

if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

#: `cue=<start> t=<clock>` -- so' o ramo painted-other-track poe a cue START e a
#: leitura do RELOGIO em campos separados. O ramo `hit` poe o INDICE em `cue` e
#: o inicio da cue em `t`; sao duas formas e nao uma.
OTHER = re.compile(
    r"^(\S+ \S+) sotto: YOUTUBE_CAPTION video_id=(\S+) cue=([\d.]+) "
    r"t=([\d.]+) track=\S+ text=.*why=painted-other-track$")
HIT = re.compile(
    r"^(\S+ \S+) sotto: YOUTUBE_CAPTION video_id=(\S+) cue=\S+ "
    r"t=([\d.]+) track=\S+ words=\d+ text=")


def _load_module(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ARM 1..6 -- a regra pura
# --------------------------------------------------------------------------
def arm_rule(mono):
    out = []
    # 1. nada servido ainda: serve a leitura tal e qual.
    s, f = mono.decide(10.0, None)
    out.append(("arm1-nothing-served", s == 10.0 and f == 10.0,
                "decide(10,None)=(%r,%r)" % (s, f)))
    # 2. adiantado: serve e o chao sobe.
    s, f = mono.decide(50.0, 40.0)
    out.append(("arm2-forward", s == 50.0 and f == 50.0,
                "decide(50,40)=(%r,%r)" % (s, f)))
    # 3. RELOGIO CONGELADO/ATRASADO: a leitura esta' atras do chao. Este e' o
    #    defeito do dono e nunca pode servir o valor atrasado.
    s, f = mono.decide(34.2, 74.7)
    out.append(("arm3-behind-floor-held", s == 74.7,
                "decide(34.2, floor=74.7) serviu %r (esperado 74.7)" % (s,)))
    # 4. O JITTER MEDIDO do relogio: salto de 5 s para tras (1175 -> 1170) com
    #    o video em ~1170 -- NAO e' seek, e' leitura. Tem de segurar o chao.
    s, f = mono.decide(1170.0, 1175.0)
    out.append(("arm4-clock-jitter-held", s == 1175.0,
                "decide(1170, floor=1175) serviu %r (o jitter de 5 s medido "
                "no log)" % (s,)))
    # 5. A PINTURA num seek a serio (salta 60 s para tras) DESCE o chao.
    f = mono.advance(74.7, 10.0)
    out.append(("arm5-paint-seek-descends", f == 10.0,
                "advance(74.7, 10.0)=%r (esperado 10.0)" % (f,)))
    # 6. A PINTURA a repetir um cue um pouco atras NAO desce o chao.
    f = mono.advance(74.7, 73.0)
    out.append(("arm6-paint-jitter-holds", f == 74.7,
                "advance(74.7, 73.0)=%r (esperado 74.7)" % (f,)))
    # 7. A PINTURA a avancar sobe o chao.
    f = mono.advance(40.0, 50.0)
    out.append(("arm7-paint-advances", f == 50.0,
                "advance(40,50)=%r" % (f,)))
    return out


# --------------------------------------------------------------------------
# ARM 10..15 -- O SEEK SEM PINTURA (2026-11-16, a sessao do dono)
# --------------------------------------------------------------------------
def arm_seek(mono):
    """A PROVA do seek que NAO precisa de uma linha pintada.

    A SEQUENCIA E' A MEDIDA, nao uma invencao: a sessao do dono de 2026-11-16
    (video `hYIymEMB9x4`, legenda do YouTube DESLIGADA, 785 cues na faixa
    automatica) publicou `YOUTUBE_CLOCK_HELD t=505.05 served=515.03
    floor=515.03` oito vezes, com o `video.currentTime` da CDP a andar de
    505,05 para 505,56 -- ou seja o chao ficou 10 s a' frente do player para
    sempre, porque `advance` so' desce com a PINTURA e nao havia pintura
    nenhuma. As tres leituras 511,43 / 512,93 / 505,59 sao as da sessao.

    Cada braco conduz a MESMA ordem do shell: `SeekWitness.observe` (o par
    t+stamp) e, quando ele declara, `advance` + `decide` -- a lei do relogio
    continua a ser uma so' (`decide` nunca recua por leitura).
    """
    out = []

    def run(seq, floor, vid='hYIymEMB9x4'):
        w = mono.SeekWitness()
        served = floor
        logs = []
        verdicts = []
        for t, stamp, v in seq:
            verdict = w.observe(t, stamp, v if v is not None else vid)
            verdicts.append(verdict)
            if verdict['seek']:
                floor = mono.advance(floor, verdict['now'])
                if verdict['log']:
                    logs.append(verdict)
            served, floor = mono.decide(t, floor)
        return served, floor, verdicts, logs

    # 10. O RECUO MEDIDO (10 s) E' SEGUIDO no tick em que a 2a leitura chega.
    seq = [(511.43, 1000.000, None), (512.93, 1009.000, None),
           (505.59, 1023.000, None)]
    served, floor, verdicts, logs = run(seq, 515.03)
    out.append(("arm10-seek-rewind-followed", served == 505.59
                and abs(floor - 505.59) < 1e-6
                and verdicts[-1]['why'] == 'back',
                "511.43 -> 512.93 -> 505.59 (chao 515.03): servido %r, chao %r, "
                "why=%r (o defeito servia 515.03 para sempre)"
                % (served, floor, verdicts[-1]['why'])))
    # 11. A DECISAO FICA ESCRITA UMA VEZ, e nao uma por tick.
    out.append(("arm11-seek-logged-once", len(logs) == 1,
                "%d linha(s) de YOUTUBE_SEEK_RESYNC para um seek de 3 leituras"
                % len(logs)))
    # 12. O JITTER DE LEITURA NAO MEXE NO CHAO. 1,5 s e' o jitter medido da
    #     leitura UIA (2026-11-04); a histerese do seek e' `SEEK_BACK_S`.
    for jump in (1.5, 1.99):
        served, floor, verdicts, logs = run(
            [(100.0, 10.000, None), (100.0 - jump, 10.500, None)], 100.0)
        out.append(("arm12-jitter-%ss-not-a-seek" % jump,
                    served == 100.0 and floor == 100.0
                    and not verdicts[-1]['seek'] and not logs,
                    "recuo de %.2f s em 0,5 s de parede: servido %r, chao %r "
                    "(o ecra nao pode recuar por leitura)"
                    % (jump, served, floor)))
    # 13. UM SALTO PARA A FRENTE SO' E' SEEK QUANDO EXCEDE O QUE O PLAYER
    #     EXPLICARIA. 60 s em 0,2 s de parede (60 s de video em 0,2 de parede =
    #     300x, acima dos 2x do menu) e' seek; 1,2 s em 1,0 s e' o video.
    served, floor, verdicts, logs = run(
        [(500.0, 20.000, None), (560.0, 20.200, None)], 500.0)
    fwd_seek = (verdicts[-1]['seek'] and verdicts[-1]['why'] == 'forward')
    served2, floor2, verdicts2, logs2 = run(
        [(500.0, 30.000, None), (501.2, 31.000, None)], 500.0)
    fwd_video = not verdicts2[-1]['seek']
    out.append(("arm13-forward-seek-vs-video", fwd_seek and fwd_video,
                "60 s em 0,2 s de parede: seek=%s; 1,2 s em 1,0 s: seek=%s"
                % (verdicts[-1]['seek'], verdicts2[-1]['seek'])))
    # 14. A MESMA FOTO (o cache de 1,2 s da CDP) NAO E' MEDIDA NOVA: sem esta
    #     regra duas chamadas no mesmo tick comparariam a leitura com ela
    #     propria e um stamp repetido nunca seria dado como repetido.
    w = mono.SeekWitness()
    w.observe(515.0, 40.000, 'v')
    repeated = w.observe(515.0, 40.000, 'v')
    out.append(("arm14-same-snapshot-not-a-measure",
                not repeated['seek'] and repeated['why'] == 'same-snapshot',
                "duas leituras do MESMO stamp: why=%r" % (repeated['why'],)))
    # 15. TROCAR DE VIDEO NAO E' RECUAR: o video novo comeca em t=0 e um recuo
    #     de 300 s para 5 s e' outra linha temporal. Sem este braco todo o
    #     alt-tab declarava seek e o chao caia para 5 s.
    served, floor, verdicts, _logs = run(
        [(300.0, 50.000, 'A'), (5.0, 50.200, 'B')], 300.0)
    out.append(("arm15-video-change-not-a-seek",
                not verdicts[-1]['seek'] and served == 300.0,
                "video A t=300 -> video B t=5: seek=%s servido=%r"
                % (verdicts[-1]['seek'], served)))
    # 16. A LEI ANTIGA CONTINUA DE PE': sem testemunha de seek, `decide` NAO
    #     recua. Este braco existe para a prova nova nao abrir a porta que as
    #     129 linhas do cabecalho fecharam.
    s, f = mono.decide(505.59, 515.03)
    out.append(("arm16-clock-alone-still-cannot-rewind", s == 515.03,
                "decide(505.59, chao=515.03) serviu %r (o NUMERO do defeito; "
                "so' um seek PROVADO o faz descer)" % (s,)))
    return out


# --------------------------------------------------------------------------
# ARM 17..19 -- O WIRING REAL: `_yt_cdp_snapshot` com a serie medida
# --------------------------------------------------------------------------
class _Clock:
    """`time.monotonic()` que o braco move a mao (o mesmo truque do stutter)."""

    now = 100.0

    def monotonic(self):
        return _Clock.now


def _literal(source, name):
    """O literal de `NAME = ...` (modulo ou corpo de classe), por AST."""
    tree = ast.parse(source)
    scopes = [tree.body]
    scopes += [node.body for node in tree.body if isinstance(node, ast.ClassDef)]
    for body in scopes:
        for node in body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == name:
                        return ast.literal_eval(node.value)
    raise SystemExit('ORACLE-BROKEN: %s nao define %s' % (SHELL, name))


def _bodies(source, names):
    """Os corpos dos metodos `names`, por AST -- a classe que os tiver."""
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        found = {}
        for sub in node.body:
            if isinstance(sub, ast.FunctionDef) and sub.name in names:
                found[sub.name] = ast.get_source_segment(source, sub)
        if found:
            return found
    return {}


class _Source:
    """A foto da CDP: uma de cada vez, do mesmo video, sem linhas pintadas."""

    def __init__(self, snap):
        self.snap = snap

    def set_video_id(self, _vid):
        return None

    def snapshot(self, max_age=None):
        return dict(self.snap) if self.snap else None

    def selected_video_id(self):
        return (self.snap or {}).get('videoId') or ''

    def snapshot_age(self):
        return 0.0


class _Shell:
    """A shell que a borda da pausa chama -- os apagares ficam contados."""

    _caption_window_shown = True
    _caption_wanted = True

    def __init__(self):
        self.blanks = []
        self.pushes = []
        self.yt_source_paused = False
        self.yt_source_ended = False

    def _blank_caption_window(self, reason):
        self.blanks.append(reason)

    def push_caption_to_window(self, text, **kw):
        self.pushes.append((text, kw))


class _Player:
    """So' o estado que o `_yt_cdp_snapshot` real le'/escreve."""

    def __init__(self, source):
        self._yt_cdp_source = source
        self._yt_diag = None
        self._yt_rate = None
        self.yt_video_id = 'hYIymEMB9x4'
        self.yt_cdp_clock = None
        self.yt_cdp_rate = 1.0
        self.yt_cdp_paused = False
        self.yt_cdp_ended = False
        self.yt_cdp_playing = None
        self.yt_serve_floor = None
        self.yt_held_logged = None
        self._yt_anchor = None
        # O ALINHAMENTO DA LINHA TEMPORAL ANTIGA: e' o que `_yt_clock_agrees`
        # compara com o relogio, e o que o seek tem de desmentir.
        self.yt_hit = {'cue': {'start': 514.0, 'end': 517.0},
                       'text': 'the old line'}
        self._yt_was_paused = False
        self._yt_pause_epoch = 0
        self._yt_pause_since = None
        self._yt_frame_at = 0.0
        self.last_line = 'the theme hotkey?'
        self.last_rows = ['the theme hotkey?']
        self.shell = _Shell()

    def _yt_cdp_ensure(self, *_a):
        return self._yt_cdp_source

    def _yt_rate_tick(self, _snap, _source):
        return None

    def _yt_cue_payload(self):
        return None


def arm_shell_wiring(mono, shell_path=SHELL):
    """O WIRING do seek e da pausa, conduzido nos METODOS REAIS do shell.

    As arms 10..16 medem a REGRA; esta mede a LIGACAO, que e' o que falhou na
    sessao do dono. Tres perguntas, cada uma com a sua testemunha:

      * 17 -- o recuo medido (515,19 -> 505,05 com a bandeira `paused=True` no
        MESMO instante) poe o chao e a ancora em 505,05 no tick da prova, e a
        leitura seguinte serve 505,05 (o defeito servia 515,03);
      * 18 -- e NAO apaga o ecra: `_yt_pause_epoch` fica em 0 com quatro
        amostras `paused=True` e o relogio a andar (o defeito apagou as 16:39:34
        e o ecra ficou 60 s vazio);
      * 19 -- o controle POSITIVO: o mesmo caminho, com a posicao PARADA de
        verdade (o mesmo `t` em carimbos distintos por 2,5 s), APAGA. Sem este
        braco, "nao apagou" seria indistinguivel de "a borda nunca correu".
    """
    with io.open(shell_path, encoding="utf-8") as fh:
        src = fh.read()
    names = ("_yt_cdp_snapshot", "_yt_clock_moving", "_yt_clock_static",
             "_yt_pause_edge", "_yt_decide")
    bodies = _bodies(src, names)
    missing = [n for n in names if n not in bodies]
    if missing:
        return [("arm17-wiring-extract", False,
                 "metodos ausentes no shell: %s" % ", ".join(missing))]
    logs = []
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    ns = {"log": lambda m: logs.append(str(m)), "time": _Clock(), "os": os,
          "_yt_mark": lambda *_a, **_k: None,
          "_YT_RATE_LOG_S": 5.0}
    # O MODULO REAL DA PAUSA (2026-11-26): `_yt_cdp_snapshot` deriva
    # `_paused_proven` de `youtube_clock.pause_proven`, o dono unico da regra
    # "uma pausa que a medida desmentiu nao e' pausa". O metodo extraido corre
    # aqui com o modulo VIVO, nunca com uma copia -- uma paridade de copia
    # mediria a copia.
    try:
        import youtube_clock as _yt_clock_live
    except Exception as _exc:                          # noqa: BLE001
        raise SystemExit('youtube_clock nao importavel de %s: %r'
                         % (WEBVIEW, _exc))
    ns["youtube_clock"] = _yt_clock_live
    for const in ("CLOCK_STATIC_PAUSE_S", "CLOCK_STATIC_PAUSE_FLAG_S",
                  "CLOCK_MOVING_MIN_RATE",
                  "PAUSE_BLANK_DWELL_S"):
        ns["_" + const] = _literal(src, const)
    for name, body in bodies.items():
        module = ast.Module(body=[ast.parse(body).body[0]], type_ignores=[])
        exec(compile(module, "<%s>" % name, "exec"), ns)

    def build(snap):
        player = _Player(_Source(snap))
        for name in names:
            setattr(player, name, ns[name].__get__(player, type(player)))
        for const in ("CLOCK_STATIC_PAUSE_S", "CLOCK_STATIC_PAUSE_FLAG_S",
                  "CLOCK_MOVING_MIN_RATE",
                      "PAUSE_BLANK_DWELL_S"):
            setattr(player, const, ns["_" + const])
        return player

    def drive(player, series):
        """`(servido, chao_no_tick, ancora_no_tick)` -- um tick de cada vez.

        O chao e a ancora sao lidos DEPOIS do snapshot e ANTES da leitura
        seguinte: `_yt_decide` sobe o chao (regra normal), e o que a arm17
        mede e' o que o tick da PROVA deixou escrito, nao o acumulado.
        """
        served, floors, anchors = [], [], []
        for t, stamp, paused in series:
            player._yt_cdp_source.snap = {
                "videoId": 'hYIymEMB9x4', "t": t, "stamp": stamp,
                "paused": paused, "ended": False, "rate": 1.0,
                "rows": [], "items": [], "title": 'x', "why": 'no-painted-caption'}
            _Clock.now = stamp
            player._yt_cdp_snapshot(None, None, None, declared='hYIymEMB9x4')
            floors.append(player.yt_serve_floor)
            anchors.append(player._yt_anchor)
            served.append(player._yt_decide(t))
        return served, floors, anchors

    # 17/18 -- A SERIE MEDIDA (2026-11-16): o recuo de 10 s e a bandeira presa.
    del logs[:]
    p = build(None)
    served, floors, anchors = drive(
        p, [(515.19, 100.00, False), (505.05, 100.15, True),
            (505.55, 101.00, True), (506.05, 101.50, True)])
    out = []
    out.append(("arm17-seek-resync-wired",
                abs(float(floors[1]) - 505.05) < 1e-6
                and served[1] == 505.05 and served[3] == 506.05
                and abs(float(anchors[1][0]) - 505.05) < 1e-6
                and p.yt_hit is None,
                "chao_no_tick=%r ancora=%r servido=%r alinhamento=%r (o defeito "
                "servia 515.03 e o chao ficava la')"
                % ([None if f is None else round(float(f), 2) for f in floors],
                   [None if a is None else (round(float(a[0]), 2),
                                            round(float(a[1]), 2))
                    for a in anchors],
                   [round(s, 2) for s in served], p.yt_hit)))
    out.append(("arm17-seek-log-once",
                sum(1 for m in logs if m.startswith('YOUTUBE_SEEK_RESYNC')) == 1,
                "%d linha(s) YOUTUBE_SEEK_RESYNC: %r"
                % (sum(1 for m in logs if m.startswith('YOUTUBE_SEEK_RESYNC')),
                   [m for m in logs if m.startswith('YOUTUBE_SEEK')][:2])))
    out.append(("arm18-paused-flag-alone-does-not-blank",
                not p.shell.blanks and int(p._yt_pause_epoch) == 0,
                "4 amostras paused=True com o relogio a andar: blanks=%r "
                "epoch=%d (o defeito apagou e ficou 60 s vazio)"
                % (p.shell.blanks, p._yt_pause_epoch)))
    out.append(("arm18-disagree-named",
                any(m.startswith('YOUTUBE_PAUSE_DISAGREED') for m in logs),
                "o desmentido tem nome: %r"
                % ([m for m in logs if m.startswith('YOUTUBE_PAUSE')][:2],)))
    # 19 -- O CONTROLE: a posicao PARADA de verdade (mesmo `t`, carimbos
    # distintos por 2,5 s) tem de apagar. `_yt_frame_at` fica no passado para o
    # portao do desenho nao adiar o que se quer medir aqui.
    del logs[:]
    q = build(None)
    drive_static = [(600.0, 200.0, True), (600.0, 201.0, True),
                    (600.0, 202.5, True), (600.0, 204.5, True)]
    for t, stamp, paused in drive_static:
        q._yt_cdp_source.snap = {
            "videoId": 'hYIymEMB9x4', "t": t, "stamp": stamp, "paused": paused,
            "ended": False, "rate": 1.0, "rows": [], "items": [],
            "title": 'x', "why": 'no-painted-caption'}
        _Clock.now = stamp
        q._yt_cdp_snapshot(None, None, None, declared='hYIymEMB9x4')
    out.append(("arm19-static-pause-still-blanks",
                q.shell.blanks == ['youtube-paused']
                and int(q._yt_pause_epoch) == 1,
                "posicao parada 2,5 s em carimbos distintos: blanks=%r epoch=%d"
                % (q.shell.blanks, q._yt_pause_epoch)))
    out.append(("arm19-proven-named",
                sum(1 for m in logs if m.startswith('YOUTUBE_PAUSE_PROVEN')) == 1,
                "%r" % ([m for m in logs if m.startswith('YOUTUBE_PAUSE')][:3],)))
    # 19-bis -- A FOTO EM CACHE NAO DESARMA A PAUSA PROVADA: entre duas
    # publicacoes da CDP (~0,5 s com o video parado) a shell le o MESMO carimbo;
    # o veredicto tem de ser o ultimo MEDIDO, senao a borda de retoma repinta o
    # ecra a cada leitura repetida -- um piscar a 4-15 Hz durante a pausa.
    del logs[:]
    for _ in range(4):
        _Clock.now += 0.25
        q._yt_cdp_snapshot(None, None, None, declared='hYIymEMB9x4')
    out.append(("arm19b-cached-read-keeps-pause",
                q.shell.blanks == ['youtube-paused']
                and int(q._yt_pause_epoch) == 1
                and not any(m.startswith('YOUTUBE_PAUSE_RESUMED') for m in logs),
                "4 leituras do MESMO carimbo com a pausa provada: blanks=%r "
                "epoch=%d resumed=%r"
                % (q.shell.blanks, q._yt_pause_epoch,
                   [m for m in logs if m.startswith('YOUTUBE_PAUSE_RESUMED')][:2])))
    # 20 -- A MESMA FOTO NAO CONFIRMA PAUSA: com o cache de 1,2 s da CDP o mesmo
    # `stamp` repetido nao pode valer como duas medidas.
    del logs[:]
    r = build(None)
    for _ in range(4):
        r._yt_cdp_source.snap = {
            "videoId": 'hYIymEMB9x4', "t": 700.0, "stamp": 300.0,
            "paused": True, "ended": False, "rate": 1.0, "rows": [], "items": [],
            "title": 'x', "why": 'no-painted-caption'}
        _Clock.now = 310.0
        r._yt_cdp_snapshot(None, None, None, declared='hYIymEMB9x4')
    out.append(("arm20-cached-snapshot-is-not-a-second-measure",
                not r.shell.blanks and int(r._yt_pause_epoch) == 0,
                "4 chamadas com o MESMO carimbo e 10 s de parede: blanks=%r "
                "epoch=%d" % (r.shell.blanks, r._yt_pause_epoch)))
    return out


# --------------------------------------------------------------------------
# ARM 8 -- replay do LOG REAL, com as duas regras
# --------------------------------------------------------------------------
def read_log(path):
    """`([(video_id, kind, a, b)], censo)` na ordem do ficheiro.

    `kind="clock"` -> `a` e' o INICIO da cue servida, `b` a leitura do relogio.
    `kind="paint"` -> `a` e' o inicio da cue que o player pinta, `b` None.

    O `video_id` viaja porque o log cobre MUITOS videos: cada um recomeca em
    t=0, e reiniciar o tempo de um video novo nao e' um recuo -- e' uma nova
    linha temporal. Sem esta coluna o instrumento acusava 47 "recuos" que
    eram so' mudancas de video.
    """
    rows = []
    census = {"caption_lines": 0, "clock": 0, "paint": 0, "unusable": {}}
    try:
        fh = io.open(path, encoding="utf-8", errors="replace")
    except OSError:
        return rows, census
    with fh:
        for line in fh:
            line = line.rstrip("\n")
            if "YOUTUBE_CAPTION" not in line:
                continue
            census["caption_lines"] += 1
            m = OTHER.match(line)
            if m:
                rows.append((m.group(2), "clock", float(m.group(3)),
                             float(m.group(4))))
                census["clock"] += 1
                continue
            m = HIT.match(line)
            if m:
                rows.append((m.group(2), "paint", float(m.group(3)), None))
                census["paint"] += 1
                continue
            # AS LINHAS QUE O REPLAY NAO USA, NOMEADAS -- e nao descartadas em
            # silencio (2026-11-04). MEDIDO: das 8 711 linhas `YOUTUBE_CAPTION`
            # do log do dono, 3 035 sao `why=painted-lines` / `why=cdp-lines` --
            # o ramo PINTADO, que serve as linhas do player e loga `lines=` e
            # `ratio=`, sem instante nenhum. Sao 35 % do log e nao alimentam
            # nenhuma das duas regras de relogio; o numero fica escrito para que
            # ninguem leia este replay como cobertura total.
            why = "?"
            tail = line.rsplit("why=", 1)
            if len(tail) == 2:
                why = tail[1].strip() or "?"
            census["unusable"][why] = census["unusable"].get(why, 0) + 1
    return rows, census


#: O CORPUS COMMITADO (2026-11-04). `_main/webview-run.log` e um artefacto de
#: RUNTIME: numa worktree limpa nao existe, e o oraculo respondia NO-VERDICT
#: (rc=2) -- inclusive no `--neg-arm`. A lei "a legenda nao recua" ficava sem
#: medicao nenhuma numa arvore limpa, que e' o contrario de uma lei medida. Este
#: ficheiro e o log do dono reduzido as linhas que o replay usa, com o censo das
#: que ficam de fora.
FIXTURE = os.path.join(HERE, "fixtures", "yt-caption-clock-replay-20261104.json")


def read_fixture(path=FIXTURE):
    """`(rows, censo)` do corpus commitado -- a MESMA forma de `read_log`."""
    try:
        with io.open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return [], {"caption_lines": 0, "clock": 0, "paint": 0, "unusable": {}}
    rows = []
    for row in doc.get("rows_data") or ():
        vid, kind, a, b = row
        rows.append((str(vid), str(kind), float(a),
                     None if b is None else float(b)))
    census = {"caption_lines": int(doc.get("caption_lines") or 0),
              "clock": int(doc.get("shapes", {}).get("clock(painted-other-track)") or 0),
              "paint": int(doc.get("shapes", {}).get("paint(has-cue)") or 0),
              "unusable": {k.split(":", 1)[1]: v for k, v in
                           (doc.get("shapes") or {}).items()
                           if k.startswith("skipped:")}}
    census["fixture"] = os.path.basename(path)
    census["source"] = doc.get("source")
    census["source_bytes"] = doc.get("source_bytes")
    return rows, census


def replay(rows, mono, rule, seek_back=2.0):
    """Conta os recuos das duas regras sobre as MESMAS linhas.

    `rule="old"`  -- o que `sotto_webview.py` fazia: servir sempre a leitura.
    `rule="new"`  -- `youtube_monotonic.decide`.

    Devolve `(back_via_clock, back_via_paint, seeks, served, worst)`.

    `back_via_clock` e' o defeito: o ecra recua por causa de uma LEITURA do
    relogio. Tem de ser 0 na regra nova. `back_via_paint` sao recuos
    declarados pela PINTURA -- um seek a serio -- e sao legitimos; contam-se
    para o relatorio, nunca como falha.
    """
    floor = None
    shown = None
    vid = None
    back_clock = back_paint = seeks = served = 0
    worst = 0.0
    for row_vid, kind, a, b in rows:
        if row_vid != vid:
            vid = row_vid
            floor = shown = None
        if kind == "paint":
            if shown is not None and a < shown - seek_back:
                # A PINTURA recuou de vez: o ecra VAI para tras, e e' um seek
                # a serio. `shown` tem de descer com ele -- senao as leituras
                # seguintes nessa linha temporal contavam como recuo do
                # relogio, que e' uma classe diferente e nao e' o defeito.
                seeks += 1
                back_paint += 1
                shown = a
            else:
                shown = a if shown is None else max(shown, a)
            floor = mono.advance(floor, a)
            continue
        if rule == "new":
            used, floor = mono.decide(b, floor)
        else:
            used = b
            floor = mono.advance(floor, used)
        served += 1
        if shown is not None and used < shown - 0.05:
            back_clock += 1
            worst = max(worst, shown - used)
        shown = used if shown is None else max(shown, used)
    return back_clock, back_paint, seeks, served, worst


# --------------------------------------------------------------------------
# ARM 9 -- a LIGACAO no codigo vivo, por AST
# --------------------------------------------------------------------------
def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def arm_wiring(path):
    """As ancoras do wiring, lidas da ARVORE INTEIRA e nao de `_youtube`.

    MEDIDO 2026-11-03: este arm procurava `self._yt_decide` e `self._yt_advance`
    DENTRO de `_youtube`, e nenhum dos dois nomes existe la' desde que o
    `_youtube` foi partido em helpers (`_yt_clock`, `_yt_advance`,
    `_yt_clock_lines`...): o arm dizia RED 3 vezes sobre um caminho que estava
    ligado -- um detector preso a' FORMA da funcao mede a forma, nao a regra.
    O que a regra exige, e o que se passa a medir aqui:
      * `youtube_monotonic.decide(` chamado no shell (o relogio passa pela lei);
      * `self._yt_advance(` chamado 3 vezes (pintado / outra faixa / com cue);
      * uma chamada a `cue_at(` DEPOIS de uma decisao (o relogio manda na cue).
    """
    with io.open(path, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            calls.append((getattr(node, "lineno", 0), _dotted(node.func)))
    if not calls:
        return [("arm9-wiring", False, "nenhuma chamada em %s" % path)]
    decides = [ln for ln, name in calls
               if name == "youtube_monotonic.decide" or name.endswith("._yt_decide")]
    advances = [ln for ln, name in calls if name == "self._yt_advance"]
    cueat = [ln for ln, name in calls if name.endswith("cue_at")]
    out = []
    out.append(("arm9-decide-wired", len(decides) >= 1,
                "youtube_monotonic.decide no shell: %d chamada(s)"
                % len(decides)))
    out.append(("arm9-advance-called-thrice", len(advances) >= 3,
                "self._yt_advance: %d chamada(s) (pintado, "
                "painted-other-track, has-cue)" % len(advances)))
    ok = False
    why = "nenhum cue_at depois de uma decisao do relogio"
    if decides and cueat:
        first = min(decides)
        for ln in cueat:
            if ln > first:
                ok = True
                why = "decide@%d antes de cue_at@%d" % (first, ln)
                break
    out.append(("arm9-decide-precedes-cue", ok, why))
    out.append(("arm9-module-imported", "youtube_monotonic" in src,
                "sotto_webview.py importa youtube_monotonic: %s"
                % ("sim" if "youtube_monotonic" in src else "NAO")))
    return out


# --------------------------------------------------------------------------
# O MUTANTE do braco negativo: a regra ANTIGA, escrita de proposito.
# --------------------------------------------------------------------------
MUTANT = '''\
FREEZE_EPS_S = 0.05
SEEK_BACK_S = 2.0


def decide(now_t, floor, freeze_eps=FREEZE_EPS_S):
    """A REGRA ANTIGA: serve a leitura do relogio, aconteca o que acontecer."""
    if now_t is None:
        return None, floor
    return float(now_t), float(now_t)


def advance(floor, position, seek_back=SEEK_BACK_S):
    if position is None:
        return floor
    try:
        pos = float(position)
    except (TypeError, ValueError):
        return floor
    if floor is None or pos > float(floor):
        return pos
    return floor
'''


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--neg-arm", action="store_true",
                    help="prova que o instrumento APANHA o defeito: com a "
                         "regra antiga o replay TEM de acusar recuos. "
                         "rc 1 e' o PASS aqui.")
    ap.add_argument("--log", default=LOG)
    args = ap.parse_args(argv)

    for path in (MONO, SHELL):
        if not os.path.exists(path):
            print("YOUTUBE-MONOTONIC NO-VERDICT -- falta %s" % path)
            return 2

    # O CORPUS: o log VIVO quando ele existe (e' o do dono, o mais fresco), e o
    # corpus commitado quando nao existe -- uma worktree limpa nao tem
    # `webview-run.log`, e o oraculo respondia NO-VERDICT a tudo, `--neg-arm`
    # incluido. O nome e o censo do que FICOU DE FORA saem sempre: 3 035 das
    # 8 711 linhas sao o ramo pintado, que nao carrega instante nenhum.
    rows, census = read_log(args.log)
    corpus = os.path.basename(args.log)
    if not rows:
        rows, census = read_fixture()
        corpus = census.get("fixture") or "?"
    if not rows:
        print("YOUTUBE-MONOTONIC NO-VERDICT -- nem %s nem %s tem linhas "
              "YOUTUBE_CAPTION" % (os.path.basename(args.log),
                                   os.path.basename(FIXTURE)))
        return 2
    print("YOUTUBE-MONOTONIC corpus=%s linhas=%d (relogio %d, pintura %d) | "
          "fora do replay: %s"
          % (corpus, len(rows), census["clock"], census["paint"],
             ", ".join("%s=%d" % kv for kv in sorted(census["unusable"].items()))
             or "nenhuma"))

    if args.neg_arm:
        tmpd = tempfile.mkdtemp(prefix="ytmono-",
                                dir=os.environ.get("TMPDIR") or None)
        try:
            mpath = os.path.join(tmpd, "youtube_monotonic_old.py")
            with io.open(mpath, "w", encoding="utf-8") as fh:
                fh.write(MUTANT)
            old = _load_module(mpath, "youtube_monotonic_old")
            b_clock, _, _, n, worst = replay(rows, old, "old")
            if b_clock <= 0:
                # O MESMO PISO DE DENTES DO ARM8: o log do dono roda, e um
                # negativo lido de um ficheiro que roda fica "nao apanhei nada"
                # por falta de populacao -- que e' o pior veredicto possivel
                # aqui, porque e' indistinguivel de um instrumento sem dentes.
                frows, _f = read_fixture()
                if frows:
                    b_clock, _, _, n, worst = replay(frows, old, "old")
            if b_clock <= 0:
                # CONTRATO DA CASA: rc 1 = apanhou o mutante, rc 0 = nao
                # apanhou. Ate' 2026-11-04 este ramo saia 1 nos dois casos.
                print("NEG-ARM FAIL -- a regra ANTIGA nao produziu recuo "
                      "nenhum em %d linha(s): o instrumento nao tem dentes"
                      % n)
                return 0
            print("NEG-ARM PASS -- RED as designed: a regra ANTIGA recuou o "
                  "ecra %d vez(es) em %d linha(s), pior %.2f s"
                  % (b_clock, n, worst))
            return 1
        finally:
            shutil.rmtree(tmpd, ignore_errors=True)

    mono = _load_module(MONO, "youtube_monotonic_live")
    results = arm_rule(mono)
    results += arm_seek(mono)
    results += arm_shell_wiring(mono, SHELL)
    results += arm_wiring(SHELL)

    def _measure(rows_, name):
        b_old_, _, _, n_, worst_old_ = replay(rows_, mono, "old")
        b_new_, b_paint_, _, _, worst_new_ = replay(rows_, mono, "new")
        return {"name": name, "n": n_, "b_old": b_old_, "b_new": b_new_,
                "b_paint": b_paint_, "worst_old": worst_old_,
                "worst_new": worst_new_}

    live = _measure(rows, corpus)
    # O PISO DE DENTES NAO PODE DEPENDER DO CORPUS VIVO (medido 2026-11-05).
    # O log do dono roda e trunca: depois do incidente das 06:57 o replay vivo
    # ficou com 3 recuos da regra antiga e a arm8 vermelha -- nao porque o
    # instrumento perdeu os dentes, mas porque a POPULACAO mudou. Uma arm cujo
    # veredito depende de um ficheiro que roda e' decorativa ao contrario: fica
    # vermelha por rotacao e verde por sorte. A questao da arm8 e' sobre o
    # INSTRUMENTO, e mede-se no corpus COMMITADO; o corpus vivo continua a ser
    # o que prova `b_new == 0` (frescura), e quando ele tem dentes tambem serve
    # de segunda testemunha.
    teeth = live
    teeth_note = ""
    if live["b_old"] < TEETH_FLOOR:
        frows, _fcensus = read_fixture()
        fx = _measure(frows, os.path.basename(FIXTURE)) if frows else None
        if fx and fx["b_old"] >= TEETH_FLOOR:
            teeth = fx
            teeth_note = (" | PISO: o corpus vivo recuou %d (<%d) e o "
                          "commitado recuou %d em %d linha(s) -- a arm8 mede o "
                          "INSTRUMENTO no corpus COMMITADO"
                          % (live["b_old"], TEETH_FLOOR, fx["b_old"], fx["n"]))
        else:
            teeth_note = (" | PISO: NEM o corpus vivo (%d) NEM o commitado "
                          "(%s) chegam a %d recuos da regra antiga -- a arm8 "
                          "nao tem dentes"
                          % (live["b_old"],
                             fx["b_old"] if fx else "ilegivel", TEETH_FLOOR))
    results.append(("arm8-replay-no-clock-recoil", live["b_new"] == 0,
                    "replay de %d linha(s) (%s): regra ANTIGA recua %d (pior "
                    "%.2f s), regra NOVA recua %d%s%s"
                    % (live["n"], live["name"], live["b_old"],
                       live["worst_old"], live["b_new"],
                       (" (pior %.2f s)" % live["worst_new"])
                       if live["b_new"] else "", teeth_note)))
    results.append(("arm8-old-rule-did-recoil", teeth["b_old"] >= TEETH_FLOOR,
                    "a regra antiga tem de recuar em >=%d linhas (%s) para a "
                    "arm8 valer: recuou %d"
                    % (TEETH_FLOOR, teeth["name"], teeth["b_old"])))
    results.append(("arm8-seeks-kept", live["b_paint"] >= 0,
                    "recuos declarados pela PINTURA (seeks, legitimos): %d"
                    % live["b_paint"]))

    failed = 0
    for name, ok, detail in results:
        print("%-4s %-38s %s" % ("PASS" if ok else "FAIL", name, detail))
        if not ok:
            failed += 1
    total = len(results)
    if failed:
        print("YOUTUBE-MONOTONIC VERDICT RED -- %d PASS / %d FAIL"
              % (total - failed, failed))
        return 1
    print("YOUTUBE-MONOTONIC VERDICT GREEN -- %d PASS / 0 FAIL "
          "(recuos do relogio: antiga %d, nova %d; seeks pela pintura: %d)"
          % (total, live["b_old"], live["b_new"], live["b_paint"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
