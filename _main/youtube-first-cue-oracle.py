#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NO-BUG: Oracle de LATENCIA da primeira cue do YouTube (troca de aba/video). Nao
# corresponde a nenhum id de `_main/bug-ledger.json`: e' trabalho pedido pela
# medicao de 2026-11-11 (o dono, verbatim: *"eu abri um video no youtube, e levou
# 3 segundos pra aparecer a legenda. inves de ser INSTANTANEO"*).
"""Oracle: a primeira cue da aba NOVA chega sem pagar damp, prazo triplo nem pausa.

A MEDICAO DE ONDE ISTO NASCE (sessao viva pid 49180, `_main/webview-run.log`,
11/11 17:35 -- a troca de aba das 45.193):

    17:35:45.193 YOUTUBE_CDP_TAB_SWITCH from=4D2C... to=D6FD... vid=BeWzp3cYY3Q
    17:35:45.296 YOUTUBE_TARGET_REBIND_ARMED confirm_s=1.5
    17:35:46.837 YOUTUBE_TARGET_REBOUND confirmed=true        <- 1,541 s de damp
    17:35:47.914 YOUTUBE_CDP_SOURCE state=slow (WebSocketTimeoutException)
    17:35:54.018 YOUTUBE_CDP_SOURCE state=slow-dead (3 prazos) <- 6,104 s
    17:35:56.396 YOUTUBE_CDP_ATTACH_OK attempt=2 ms=375 pick=BeWzp3cYY3Q
    17:36:02.259 YOUTUBE_TRACK_READY cues=1480
    17:36:02.367 YT_FRAME rows=2
    17:36:02.422 EXTERNAL_CAPTION_SENT  <- 17,2 s depois da troca

E a segunda janela (17:46, mesma sessao), onde a queda de socket virou TROCA DE
VIDEO com sete abas abertas:

    17:46:02.951 YOUTUBE_CDP_SOURCE state=slow (ConnectionAbortedError)
    17:46:03.003 YOUTUBE_CDP_SOURCE state=reconnect (ConnectionAbortedError)
    17:46:03.513 YOUTUBE_TARGET pick=JM1gEnmaUao why=paused-loaded declared=zEgthOmOrc0
    17:46:05.039 YOUTUBE_CDP_SOURCE state=adopted:zEgthOmOrc0->JM1gEnmaUao
    17:46:05.108 CAPTION_WINDOW_BLANKED reason=video-changed / YOUTUBE_VIDEO_CHANGED
    17:46:05.822 CAPTION_IN ... (o ASR pinta a hipotese dele)

AS QUATRO REGRAS QUE ESTE ORACULO JULGA (todas em `youtube_cdp_source.py`):

  A. O damp de `confirm_s` nao pode segurar um alvo cujas LINHAS ja' existem:
     `rebind_verdict(..., snap)` devolve `adopt/rows-ready` com a primeira foto
     que traz `rows` do candidato -- 1,541 s -> 0 ms.
  B. Uma troca de aba INVALIDA o socket (nao e' uma pagina lenta): `_adopt_tab`
     fecha-o com o martelo (`abort`, que acorda o `recv` -- `close` de outro fio
     nao acorda); o primeiro prazo ja' fecha e re-liga se o epoch mudou; e, quando
     o epoch NAO mudou, o primeiro prazo pergunta a' LISTA (`_recheck_target`) se
     a aba escolhida ainda e' a que o socket serve. Sem `slow-dead`, sem
     `RETRY_S`, e nenhuma foto de um socket abandonado e' publicada. O prazo do
     PRIMEIRO pedido de cada ligacao nova e' 0,5 s (o handshake ja' provou a
     porta; uma pagina viva responde em 10 ms) -- e' o que limita o estrago
     quando nem `abort` nem `close` acordam o `recv`.
  C. O passo de leitura nao estaciona um epoch novo: nada de `PAUSED_POLL_S`
     (0,5 s) em cima de uma aba que acabou de mudar.
  D. `keep-declared`: com o video DECLARADO aberto e a sonda sem o ver, o picker
     nao adota outra aba (`choose_target`), e a evidencia de troca de video so'
     e' `same-tab` quando o id novo apareceu na MESMA aba (`video_change_evidence`).

COMO (as funcoes sao as REAIS, extraidas por `ast`): o modulo e' lido, as
funcoes/constantes/classes sao levantadas por `ast.get_source_segment` e
executadas num namespace proprio; `_run` corre contra um `websocket` falso, um
relogio VIRTUAL (so' `wait`/`recv`/`attach` o movem) e uma lista de abas falsa.
Nada abre socket, nada abre janela, nada toca em audio.

  py -3 _main/youtube-first-cue-oracle.py             # PASS, rc=0

AS ARMS (cada uma e' uma classe de cura, e cada mutante do braco negativo
derruba a arm que a mede):

  A1-DAMP-ROWS        com `rows` do candidato, adota na 1a leitura
  A2-KEEP-DECLARED    o declarado ABERTO nao perde o pick para `paused-loaded`
  A3-PAUSED-NO-BEAT   `paused-loaded` nunca passa a' frente de um `playing`
  B1-SWITCH-HEALTHY   troca com socket saudavel -> 1a foto <= 1000 ms
  B2-FROZEN-3-PRAZOS  pagina congelada (sem troca) mantem os 3 prazos + RETRY_S
  B3-DEAD+SWITCH-1    troca conhecida -> o martelo acorda o `recv` (0 prazos)
  B3b-GUARD-ONLY      sem martelo no transporte -> 1 prazo (o do 1o pedido)
  B4-RECHECK-LIST     epoch igual, lista diferente -> o 1o prazo pergunta e muda
  C-PACED-HOLD        o passo pausado nao estaciona um epoch novo
  D-CHANGE-EVIDENCE   `tab-switch` nao e' `same-tab` na evidencia da shell
  py -3 _main/youtube-first-cue-oracle.py --neg-arm   # 8 mutantes, rc=1
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import shutil
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
APP = os.path.join(ROOT, 'app', 'webview')
SOURCE = os.path.join(APP, 'youtube_cdp_source.py')
WINDOW = os.path.join(APP, 'youtube_window.py')

A_VID = 'JM1gEnmaUao'          # o declarado na janela de 17:35
B_VID = 'BeWzp3cYY3Q'          # a aba escolhida as 45.193 (1480 cues)
Z_VID = 'zEgthOmOrc0'          # o declarado na janela de 17:46
P_VID = 'JM1gEnmaUao'          # a aba escolhida por `paused-loaded` as 03.513
Q_VID = '7ZUD9H431FE'          # a outra pausada da lista de 7 abas

#: O CUSTO DE UM ATTACH, MEDIDO: `YOUTUBE_CDP_ATTACH_OK attempt=2 ... ms=375`
#: (17:35:56.396). O `/json/list` desta maquina ja' mediu 3,2 ms de mediana (ver
#: o comentario de `PROBE_TIMEOUT_S`); o resto e' o handshake + a escolha.
ATTACH_MS = 375.0
LIST_MS = 3.2
HANDSHAKE_MS = ATTACH_MS - LIST_MS
#: Uma ida e volta com `Runtime.evaluate` (medido ~10 ms, ver `POLL_S`).
EVAL_MS = 10.0
#: O prazo do socket que `_connect` arma (`conn.settimeout(3.0)`).
DEADLINE_S = 3.0
#: O prazo do PRIMEIRO pedido de uma ligacao nova (`FIRST_READ_TIMEOUT_S` no
#: modulo real).'
FIRST_READ_S = 0.5

#: OS NUMEROS DO LOG, ao milissegundo (fixture; as horas sao o mesmo dia).
T35_SWITCH = 45.193
T35_ARMED = 45.296
T35_REBOUND = 46.837
T35_SLOW1 = 47.914
T35_SLOW_DEAD = 54.018
T35_ATTACH = 56.396
T35_TRACK = 62.259
T35_FRAME = 62.367
T35_SENT = 62.422
T46_SLOW = 12.043
T46_WRONG = 13.067
T46_ATTACH = 13.283
T46_REBOUND = 10.205
T46_TRACK = 18.474
T46_FRAME = 18.547


def ms(t0, t1):
    """Milissegundos entre dois instantes de relogio de parede (`ss.mmm`)."""
    return (t1 - t0) * 1000.0


def read(path):
    with io.open(path, encoding='utf-8', newline='') as fh:
        return fh.read()


def lift(path=SOURCE):
    """As funcoes/constantes/classes REAIS do ficheiro, por `ast`.

    O QUE FICA DE FORA, e por que': os `import` do modulo (o namespace traz o
    `json`/`os`/`threading`/`time` que as funcoes usam) e o Assign de
    `strip_speaker_markers`, que carrega o irmao POR CAMINHO -- aqui o irmao e'
    carregado por `spec` uma vez e injectado, para uma COPIA do modulo (o braco
    negativo) nao precisar de um `youtube_window.py` ao lado.
    """
    src = read(path)
    tree = ast.parse(src)
    ns = {'__name__': 'youtube_cdp_lifted'}
    ns['strip_speaker_markers'] = _window_module().strip_speaker_markers
    kept = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if 'strip_speaker_markers' in names:
                continue
            kept.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            kept.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            kept.append(node)
    module = ast.Module(body=kept, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, os.path.basename(path), 'exec'), ns)
    return ns


_window_cache = []


def _window_module():
    if not _window_cache:
        import importlib.util
        spec = importlib.util.spec_from_file_location('sotto_yw_lifted', WINDOW)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _window_cache.append(mod)
    return _window_cache[0]


# ---------------------------------------------------------------- relogio falso
class Clock(object):
    """Relogio VIRTUAL: so' `wait`/`recv`/`attach` o movem. Nada dorme a serio."""

    def __init__(self, t0=1000.0):
        self.t = float(t0)

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.t += max(0.0, float(seconds or 0.0))


class Stop(object):
    """O `_stop` da fonte: `wait(d)` avanca o relogio e fica registado."""

    def __init__(self, clock, horizon_s=40.0, max_calls=20000):
        self.clock = clock
        self.horizon = clock.t + float(horizon_s)
        self.max_calls = int(max_calls)
        self.calls = 0
        self.flag = False
        self.waits = []

    def is_set(self):
        self.calls += 1
        if self.calls > self.max_calls:
            return True
        return self.flag or self.clock.t >= self.horizon

    def set(self):
        self.flag = True

    def clear(self):
        self.flag = False

    def wait(self, seconds):
        seconds = max(0.0, float(seconds or 0.0))
        self.waits.append((self.clock.t, seconds))
        self.clock.t += seconds
        return self.is_set()


class WebSocketTimeoutException(Exception):
    """O nome que `_run` publica em `state=slow (...)`."""


class WebSocketConnectionClosedException(Exception):
    """O nome real do websocket-client quando outro fio fecha o socket.

    E' o que `_adopt_tab` provoca ao fechar a ligacao da aba antiga (ver o
    comentario la'): o `recv` preso levanta JÁ, em vez de esperar o prazo.
    """


class ProbeDead(object):
    """Um alvo que nao responde a' sonda de "quem toca" (aba congelada)."""

    def settimeout(self, _s):
        pass

    def send(self, _raw):
        raise WebSocketTimeoutException('yt-probe')

    def recv(self):
        raise WebSocketTimeoutException('yt-probe')

    def close(self):
        pass


class ProbeSock(object):
    """Um alvo que responde a' sonda: duas leituras de `currentTime`."""

    def __init__(self, data, advance):
        self.data = dict(data)
        self.advance = float(advance)
        self._want = 0
        self._reads = 0

    def settimeout(self, _s):
        pass

    def send(self, raw):
        self._want = json.loads(raw).get('id')

    def recv(self):
        body = dict(self.data)
        body['t'] = float(self.data.get('t') or 0.0) + self.advance * self._reads
        self._reads += 1
        return json.dumps({'id': self._want,
                           'result': {'result': {'value': json.dumps(body)}}})

    def close(self):
        pass


class Sock(object):
    """Um socket CDP falso com prazo VIRTUAL e um guiao por leitura.

    `mode(k)` diz se a leitura `k` e' respondida (`True`) ou estoura o prazo
    (`False`); `hook(k)` corre DENTRO do `recv`, que e' onde a troca de aba
    acontece na vida real (o refrescador muda a aba enquanto o `_run` espera).
    """

    def __init__(self, clock, vid, rows, paused=False, mode=None, hook=None,
                 ignore_close=False, abort_missing=False, on_send=None):
        self.clock = clock
        self.vid = vid
        self.rows = list(rows or ())
        self.paused = bool(paused)
        self.mode = mode or (lambda _k: True)
        self.hook = hook
        self.timeout = DEADLINE_S
        self.sent = 0
        self.closed = False
        #: Um socket ENCALHADO: `close()` volta e o `recv` continua preso nele --
        #: o modelo do canal de fecho a falhar (ver B3b).
        self.ignore_close = bool(ignore_close)
        #: Um cliente/transporte SEM o martelo (`abort`): so' ha' `close()`.
        self.abort_missing = bool(abort_missing)
        self.on_send = on_send
        self.close_calls = 0
        self.abort_calls = 0
        #: Quantas vezes o PRAZO estourou neste socket -- o numero que o log
        #: publica em `slow-dead (3 prazos)`.
        self.timeouts = 0
        self._want = 0

    def settimeout(self, seconds):
        self.timeout = float(seconds)

    def send(self, raw):
        try:
            self._want = json.loads(raw).get('id')
        except (TypeError, ValueError):
            self._want = 0
        self.sent += 1
        if self.on_send is not None:
            self.on_send(self.sent)

    def recv(self):
        if self.hook is not None:
            self.hook(self.sent)
        if self.closed:
            raise WebSocketConnectionClosedException('fechado pelo refrescador')
        if not self.mode(self.sent):
            self.timeouts += 1
            self.clock.t += self.timeout
            raise WebSocketTimeoutException('deadline')
        self.clock.t += EVAL_MS / 1000.0
        value = json.dumps(payload(self.vid, self.rows, self.paused))
        return json.dumps({'id': self._want,
                           'result': {'result': {'value': value}}})

    def close(self):
        self.close_calls += 1
        if not self.ignore_close:
            self.closed = True

    def abort(self):
        """O martelo do websocket-client: ACORDA o `recv` preso.

        `abort_missing` e' o cliente antigo/sem martelo: levanta como o
        websocket-client levantaria num transporte que nao o suporta, e o
        `_hard_close` cai no `close()` (ver B3b).
        """
        if self.abort_missing:
            raise AttributeError('abort')
        self.abort_calls += 1
        self.closed = True


class FakeWebsocket(object):
    """O `websocket` do `_run`: `create_connection` devolve o socket do guiao."""

    def __init__(self, clock):
        self.clock = clock
        self.factory = None
        self.urls = []
        self.socks = []

    def create_connection(self, url, timeout=None):      # noqa: ARG002
        if threading.current_thread().name == 'yt-probe':
            return ProbeDead()
        self.clock.t += HANDSHAKE_MS / 1000.0
        sock = self.factory(url)
        self.urls.append(url)
        self.socks.append(sock)
        return sock


class _FakeWSModule(object):
    """O modulo que `_default_connect` importa (`import websocket`)."""

    def __init__(self, fake):
        self._fake = fake

    def create_connection(self, url, timeout=None):
        return self._fake.create_connection(url, timeout=timeout)


class FakeWSContext(object):
    """`sys.modules['websocket']` trocado durante um braco (nada abre socket)."""

    def __init__(self, fake):
        self.module = _FakeWSModule(fake)

    def __enter__(self):
        self.saved = sys.modules.get('websocket')
        sys.modules['websocket'] = self.module
        return self.module

    def __exit__(self, *_exc):
        if self.saved is None:
            sys.modules.pop('websocket', None)
        else:
            sys.modules['websocket'] = self.saved
        return False


# ------------------------------------------------------------------- fixtures
def payload(vid, rows, paused=False, t=12.0):
    """A resposta JSON que a pagina devolveria ao `EXTRACT_JS`."""
    return {"videoId": vid, "title": 'Video %s - YouTube' % vid,
            "t": float(t), "paused": bool(paused), "rate": 1.0, "rs": 4,
            "why": 'painted' if rows else 'no-painted-caption', "segs": [],
            "rows": [{"text": str(text),
                      "items": [{"text": str(text), "left": 1, "top": 2,
                                 "right": 40, "bottom": 20}]}
                     for text in (rows or ())]}


def tab(vid, title=None):
    return {'type': 'page', 'id': vid,
            'url': 'https://www.youtube.com/watch?v=' + vid,
            'title': title or ('Video %s - YouTube' % vid),
            'webSocketDebuggerUrl': 'ws://127.0.0.1:1/devtools/page/' + vid}


def probe(vid, t, advancing=False, paused=None, title=None, focused=False,
          visible='visible'):
    """Um dicionario de sonda, no formato que `probe_tabs` devolve."""
    return {'videoId': vid, 'paused': bool(paused) if paused is not None else not advancing,
            'ended': False, 't0': float(t), 't1': float(t) + (0.5 if advancing else 0.0),
            'advance': 0.5 if advancing else 0.0, 'dur': None, 'rs': 4,
            'visible': visible, 'focused': focused, 'tab': tab(vid, title)}


def gap_ms(t0, t1):
    return round((t1 - t0) * 1000.0, 1)


# ------------------------------------------------------------------ o motor
class Run(object):
    """Uma conducao de `_run` com relogio virtual; devolve o que importa."""

    def __init__(self, ns, horizon_s=40.0):
        self.ns = ns
        self.clock = Clock()
        self.stop = Stop(self.clock, horizon_s)
        self.ws = FakeWebsocket(self.clock)
        self.logs = []
        self.published = []
        self.tabs_now = []
        self.src = ns['CdpCaptionSource'](port=0,
                                          log=lambda m: self.logs.append(
                                              (self.clock.t, m)))
        self.src._stop = self.stop
        self.src._last_use = self.clock.t
        self._real_publish = self.src._publish
        self.src._publish = self._publish
        ns['time'] = self.clock

        def _list(port=None, timeout=3.0):              # noqa: ARG001
            self.clock.t += LIST_MS / 1000.0
            return [dict(t) for t in self.tabs_now], 0

        self.ns['list_targets'] = _list
        #: A SONDA DE "QUEM TOCA" NAO PODE COMER AS LEITURAS DO LACO: o `_choose`
        #: passa por `pick_playing`, que abre as SUAS ligacoes. O seam e' o
        #: `_probe_connect` que a propria classe ja' consulta.
        self.src._probe_connect = lambda url, timeout=None: ProbeDead()

    def _publish(self, snap, note=None):
        self._real_publish(snap, note)
        if snap is not None:
            self.published.append({'t': self.clock.t,
                                   'vid': str(snap.get('videoId') or ''),
                                   'selected': self.src.selected_video_id(),
                                   'tab': self.src._tab_key})

    # -- utilidades ------------------------------------------------------
    def lines(self, prefix, since=0.0):
        return [(t, m) for t, m in self.logs
                if m.startswith(prefix) and t >= since]

    def first_publish(self, vid, since=0.0):
        for row in self.published:
            if row['vid'] == vid and row['t'] >= since:
                return row
        return None

    def run(self):
        with FakeWSContext(self.ws):
            self.src._run()
        return self

    def source(self):
        return self.src


# --------------------------------------------------------------------- bracos
def arm_roundtrip(ns):
    """A1 -- o damp de `confirm_s` nao paga sobre um alvo com linhas.

    O relogio do log: ARMED 45.296 -> REBOUND 46.837 = **1,541 s**, com doze
    `REBIND_DAMPED` no meio. A regra nova: a primeira leitura que traz `rows` do
    candidato ADOTA. E o damp continua a existir para a oscilacao de duas abas
    (2026-11-09), que nao traz linhas -- a arm mede as duas metades.
    """
    rows_for = ns['rows_for']
    verdict = ns['rebind_verdict']
    snap_rows = {'videoId': B_VID, 'rows': ["So, let's pour ourselves a cup of tea,"]}
    snap_bare = {'videoId': B_VID, 'rows': []}
    # (a) com linhas: adota na PRIMEIRA leitura, sem esperar o `confirm_s`
    got = verdict(A_VID, B_VID, '', 0.0, 1.5, snap_rows)
    same = ns['rows_for'](snap_rows, B_VID)
    no_rows = rows_for(snap_bare, B_VID)
    other = rows_for({'videoId': A_VID, 'rows': ['x']}, B_VID)
    # (b) sem linhas (a oscilacao de duas abas): arma, espera, so' confirma
    damped_ms = None
    armed = verdict(A_VID, B_VID, '', 0.0, 1.5, snap_bare)
    # os doze `REBIND_DAMPED` do log, aos 108..1.436 ms, e o primeiro instante em
    # que a idade passa de `confirm_s`: 1,5 s -- o piso que a oscilacao de duas
    # abas ainda paga, e que a medicao de 17:35 pagou em dobro (1,541 s).
    ages = [108, 218, 327, 452, 561, 671, 781, 889, 1000, 1108, 1218, 1327, 1436,
            1500, 1541]
    for age in ages:
        act, why = verdict(A_VID, B_VID, B_VID, age / 1000.0, 1.5, snap_bare)
        if act == 'adopt':
            damped_ms = age
            break
    # (c) o candidato e' o proprio declarado: o damp desarma
    cleared = verdict(A_VID, A_VID, B_VID, 9.0, 1.5, snap_rows)
    ok = (got == ('adopt', 'rows-ready') and same and not no_rows and not other
          and armed == ('armed', 'new-candidate') and damped_ms == 1500
          and cleared == ('clear', 'no-candidate'))
    before = ms(T35_ARMED, T35_REBOUND)
    return ok, ('com-linhas=%r antes=%.0fms depois=0ms | sem-linhas=%r confirma_em=%sms '
                '| limpa=%r' % (got, before, armed, damped_ms, cleared[0])), {
        'antes_ms': round(before, 1), 'depois_ms': 0.0}


def arm_keep_declared(ns):
    """A2 -- uma queda de socket NAO e' evidencia de troca de video.

    O log: `17:46:03.513 pick=JM1gEnmaUao why=paused-loaded declared=zEgthOmOrc0
    tabs=7` com o declarado ABERTO. A regra: o picker devolve o DECLARADO
    (`keep-declared`), e a aba vem da LISTA -- a sonda nao a viu.
    """
    choose = ns['choose_target']
    pick = ns['pick_playing']
    tabs = [tab(Z_VID), tab(P_VID), tab(Q_VID)]
    probes = [probe(P_VID, 381.84), probe(Q_VID, 20.0)]
    keep = choose(probes, '', '', Z_VID, declared_open=True)
    # o mesmo, com a aba do declarado FECHADA: adotar e' legitimo (a cura de 11-04)
    old = choose(probes, '', '', Z_VID, declared_open=False)
    # e o picker inteiro: so' a aba pausada responde a' sonda
    table = {'ws://127.0.0.1:1/devtools/page/%s' % P_VID: (P_VID, 381.84, True),
             'ws://127.0.0.1:1/devtools/page/%s' % Q_VID: (Q_VID, 20.0, True)}

    def connect(url, timeout=None):                     # noqa: ARG001
        got = table.get(url)
        if got is None:
            return ProbeDead()
        return ProbeSock({'videoId': got[0], 'paused': got[2], 't': got[1],
                          'ended': False, 'dur': None, 'rs': 4,
                          'vis': 'visible', 'focus': False}, 0.0)

    named_tab, named_vid, why = pick(tabs, '', connect=connect, timeout=0.05,
                                     gap_s=0.0, declared=Z_VID)
    ok = (keep == (Z_VID, 'keep-declared')
          and old == (P_VID, 'paused-loaded')
          and named_tab is not None
          and str(named_tab.get('id')) == Z_VID
          and named_vid == Z_VID and why == 'keep-declared')
    line = ('YOUTUBE_TARGET pick=%s why=%s declared=%s tabs=%d'
            % (named_vid or '-', why, Z_VID, len(tabs)))
    return ok, ('keep=%r aberto=True | fechado=%r (o degrau antigo) | pick=(%s,%s) | %r'
                % (keep, old, named_vid, why, line)), {'pick': line}


def arm_paused_never_beats_playing(ns):
    """A3 -- `paused-loaded` nunca passa a' frente de um video a TOCAR."""
    choose = ns['choose_target']
    playing = probe('PLAYING1111', 20.7, advancing=True, paused=False)
    paused = probe('PAUSED11111', 900.0, paused=True)
    got = choose([paused, playing], '', '', 'CLOSED11111', declared_open=False)
    got_title = choose([paused, playing], '', 'Video PAUSED11111 - YouTube',
                       'CLOSED11111', declared_open=False)
    ok = got == ('PLAYING1111', 'playing')
    return ok, ('sem-titulo=%r | titulo-em-primeiro-plano=%r (o foco manda, e isso e'
                ' desenho)' % (got, got_title)), {}


def _setup_arm(ns, tabs, sock_factory, declared, horizon_s=40.0, after_publish=None,
               before_run=None):
    run = Run(ns, horizon_s)
    run.tabs_now = list(tabs)
    run.ws.factory = sock_factory(run)
    run.src.set_video_id(declared)
    if before_run is not None:
        before_run(run)
    if after_publish is not None:
        base = run._publish

        def _publish(snap, note=None):
            base(snap, note)
            if snap is not None:
                after_publish(run)
        run.src._publish = _publish
    return run


def arm_tab_switch_healthy(ns):
    """B1 -- LIGACAO saudavel + troca de aba: a 1a foto nova <= 1000 ms.

    E' a forma do log de 17:35: a ligacao estava de pe' e o PEDIDO EM VOO e' que
    nao respondeu (`state=slow` 2,7 s depois da troca). O socket nao se deixa
    acordar por `close()` (o modelo do Windows) -- quem o acorda e' o `abort()`
    do `_hard_close`. Mede-se: (i) troca -> primeira foto do alvo novo;
    (ii) nenhuma foto publicada de uma aba que ja' nao era a escolhida.
    """
    state = {'switched_at': None}

    def factory(run):
        def make(url):
            if url.endswith(A_VID):
                def hook(k):
                    if k == 3 and state['switched_at'] is None:
                        state['switched_at'] = run.clock.t
                        run.tabs_now[:] = [tab(B_VID)]
                        run.src._adopt_tab(tab(B_VID), B_VID)
                # `ignore_close=True` e' o modelo do que se MEDE no Windows: o
                # `close()` de outro fio volta e o `recv` preso continua preso.
                # Quem o acorda e' o `abort()` do `_hard_close`.
                # o `revc` EM VOO quando a troca chega NAO responde (e' o que o
                # log mede: `state=slow` 2,7 s depois da troca) -- nao ha' foto
                # nenhuma para a guarda de foto velha apanhar.
                return Sock(run.clock, A_VID, ['old line one', 'old line two'],
                            mode=lambda k: k < 3, hook=hook, ignore_close=True)
            return Sock(run.clock, B_VID, ["So, let's pour ourselves a cup of tea,"])
        return make

    run = _setup_arm(ns, [tab(A_VID)], factory, A_VID).run()
    hit = run.first_publish(B_VID, since=state['switched_at'] or 0.0)
    took = gap_ms(state['switched_at'], hit['t']) if hit else None
    attach = run.lines('YOUTUBE_CDP_ATTACH_OK')
    stale_pub = [p for p in run.published
                 if state['switched_at'] is not None and p['t'] > state['switched_at']
                 and p['vid'] != B_VID]
    ok = (hit is not None and took is not None and took <= 1000.0
          and not stale_pub and run.source().snap_vid() == B_VID)
    detail = ('troca->1a-foto=%.1fms (alvo 1000) fotos-de-aba-abandonada=%d '
              'attach_ms=%s snap_vid=%s'
              % (took or -1, len(stale_pub),
                 (attach[-1][1].split('ms=')[-1].split()[0] if attach else '-'),
                 run.source().snap_vid()))
    return ok, detail, {'depois_ms': took}


def arm_slow_dead_keeps_three(ns):
    """B2 -- pagina CONGELADA (sem troca de aba): os 3 prazos e o `RETRY_S` ficam.

    Esta e' a arm que impede a cura de virar histerese: um `recv` que nao responde
    com a MESMA aba nao e' um socket invalido, e' uma pagina lenta (medido
    2026-11-03: re-ligar a cada prazo nunca publicava foto). O replay tem de
    reproduzir o `slow-dead` do log -- 6,104 s entre o 1o e o 3o prazo.
    """
    def factory(run):
        return lambda _url: Sock(run.clock, A_VID, ['line one'],
                                 mode=lambda k: k <= 1)
    run = _setup_arm(ns, [tab(A_VID)], factory, A_VID,
                     horizon_s=13.0).run()
    slow = run.lines('YOUTUBE_CDP_SOURCE state=slow (')
    dead = run.lines('YOUTUBE_CDP_SOURCE state=slow-dead')
    retry = [w for w in run.stop.waits if abs(w[1] - 2.0) < 1e-6]
    deadlines = sum(s.timeouts for s in run.ws.socks)
    first_sock = run.ws.socks[0]
    ok = (bool(dead) and len(retry) == 1 and first_sock.closed
          and bool(slow) and retry[0][0] == dead[0][0]
          and 6.0 < dead[0][0] - slow[0][0] < 6.2)
    took = (dead[0][0] - slow[0][0]) * 1000.0 if (dead and slow) else None
    log_ms = ms(T35_SLOW1, T35_SLOW_DEAD)
    return ok, ('slow->slow-dead=%.0fms (log=%.0fms) retry_s=%d prazos=%d'
                % (took or -1, log_ms, len(retry),
                   run.ws.socks[0].timeouts)), {
        'antes_ms': round(log_ms, 1), 'depois_ms': round(took or -1, 1)}


def arm_slow_dead_tab_changed(ns):
    """B3 -- socket MORTO + aba TROCADA: re-liga no PRIMEIRO prazo.

    O log: 47.914 (1o prazo) -> 54.018 (`slow-dead`, 3o) -> 56.396 (`ATTACH_OK`,
    depois de `RETRY_S`) = **8,482 s** do primeiro prazo ao attach. A regra nova:
    o mesmo prazo ja' sabe que a aba mudou, fecha e re-liga -- sem `slow-dead` e
    sem `RETRY_S`.
    """
    state = {'switched_at': None}

    def factory(run):
        def make(url):
            def hook(k):
                if k == 2 and state['switched_at'] is None:
                    state['switched_at'] = run.clock.t
                    run.tabs_now[:] = [tab(B_VID)]
                    run.src._adopt_tab(tab(B_VID), B_VID)
            if url.endswith(A_VID):
                return Sock(run.clock, A_VID, ['old line one'],
                            mode=lambda k: k <= 1, hook=hook)
            return Sock(run.clock, B_VID, ["So, let's pour ourselves a cup of tea,"])
        return make

    run = _setup_arm(ns, [tab(A_VID)], factory, A_VID).run()
    hit = run.first_publish(B_VID, since=state['switched_at'] or 0.0)
    dead = run.lines('YOUTUBE_CDP_SOURCE state=slow-dead')
    stale = run.lines('YOUTUBE_CDP_SOURCE state=tab-stale')
    first_sock = run.ws.socks[0]
    deadlines = sum(s.timeouts for s in run.ws.socks)
    retry = [w for w in run.stop.waits if abs(w[1] - 2.0) < 1e-6]
    took = gap_ms(state['switched_at'], hit['t']) if hit else None
    ok = (hit is not None and took is not None and took <= 600.0
          and not dead and bool(stale) and not retry and deadlines == 0)
    before = ms(T35_SWITCH, T35_ATTACH)
    return ok, ('troca->1a-foto=%.0fms (alvo 600: attach 375 + leitura; o prazo seria'
                ' 500+375) prazos=%d slow-dead=%d retry_s=%d abort=%d'
                ' | antes(troca->attach)=%.0fms'
                % (took or -1, deadlines, len(dead), len(retry),
                   first_sock.abort_calls, before)), {
        'antes_ms': round(before, 1), 'depois_ms': round(took or -1, 1)}


def arm_slow_dead_guard_only(ns):
    """B3b -- a troca conhecida, mas o refrescador NAO tem o socket em maos.

    O canal de `close()` e' o primeiro; quando ele falha (o campo `_conn` nao e'
    a ligacao viva), resta o epoch comparado no primeiro prazo. O numero a bater:
    **um** prazo + attach, nunca tres + `RETRY_S` (8,482 s no log).
    """
    state = {'switched_at': None}

    def factory(run):
        def make(url):
            def on_send(k):
                # a troca chega DEPOIS do attach e ANTES da primeira leitura --
                # a corrida mais estreita que existe, e a que custa os 3 s.
                if k == 1 and state['switched_at'] is None:
                    state['switched_at'] = run.clock.t
                    run.tabs_now[:] = [tab(B_VID)]
                    run.src._adopt_tab(tab(B_VID), B_VID)
            if url.endswith(A_VID):
                # nem `abort` (cliente antigo) nem `close` acordam o `recv`: so'
                # o prazo do PRIMEIRO pedido limita o estrago.
                return Sock(run.clock, A_VID, ['old line one'],
                            mode=lambda k: False, on_send=on_send,
                            ignore_close=True, abort_missing=True)
            return Sock(run.clock, B_VID, ["So, let's pour ourselves a cup of tea,"])
        return make

    run = _setup_arm(ns, [tab(A_VID)], factory, A_VID).run()
    hit = run.first_publish(B_VID, since=state['switched_at'] or 0.0)
    dead = run.lines('YOUTUBE_CDP_SOURCE state=slow-dead')
    stale = run.lines('YOUTUBE_CDP_SOURCE state=tab-stale')
    retry = [w for w in run.stop.waits if abs(w[1] - 2.0) < 1e-6]
    deadlines = sum(s.timeouts for s in run.ws.socks)
    took = gap_ms(state['switched_at'], hit['t']) if hit else None
    first_deadline = FIRST_READ_S
    ok = (hit is not None and took is not None
          and run.ws.socks[0].close_calls >= 1 and run.ws.socks[0].abort_calls == 0
          and took <= 1000.0
          and not dead and bool(stale) and not retry and deadlines == 1)
    before = ms(T35_SLOW1, T35_ATTACH)
    return ok, ('troca->1a-foto=%.0fms (1o prazo %.1fs + attach) slow-dead=%d retry_s=%d'
                ' | antes(1o prazo->attach)=%.0fms'
                % (took or -1, first_deadline, len(dead), len(retry), before)), {
        'antes_ms': round(before, 1), 'depois_ms': round(took or -1, 1),
        'prazos': str(deadlines)}


def arm_recheck_list(ns):
    """B4 -- o epoch nao muda, mas a LISTA mudou: o 1o prazo decide.

    O refrescador nao ve' todas as trocas (duas abas `watch` do mesmo canal, o
    mesmo titulo de janela). Sem esta pergunta, um socket que nao responde custa
    os tres prazos do `slow-dead` mais `RETRY_S` -- 8,482 s no log. Com ela, um
    prazo (o curto, 0,5 s) + `/json/list` + attach.
    """
    state = {'switched_at': None}

    def factory(run):
        def make(url):
            if url.endswith(A_VID):
                def on_send(k):
                    # a lista muda e NINGUEM adota a aba nova: o epoch fica como
                    # esta, e so' a pergunta a' lista pode salvar a volta.
                    if k == 1 and state['switched_at'] is None:
                        state['switched_at'] = run.clock.t
                        run.tabs_now[:] = [tab(B_VID)]
                return Sock(run.clock, A_VID, ['old line one'],
                            mode=lambda k: False, on_send=on_send)
            return Sock(run.clock, B_VID, ["So, let's pour ourselves a cup of tea,"])
        return make

    run = _setup_arm(ns, [tab(A_VID)], factory, A_VID).run()
    hit = run.first_publish(B_VID, since=state['switched_at'] or 0.0)
    moved = run.lines('YOUTUBE_CDP_SOURCE state=target-moved')
    dead = run.lines('YOUTUBE_CDP_SOURCE state=slow-dead')
    took = gap_ms(state['switched_at'], hit['t']) if hit else None
    ok = (hit is not None and took is not None and took <= 1000.0
          and bool(moved) and not dead
          and run.ws.socks[0].timeouts == 1)
    return ok, ('troca->1a-foto=%.0fms (alvo 1000) target-moved=%d slow-dead=%d'
                ' prazos=%d | antes(3 prazos)=%.0fms'
                % (took or -1, len(moved), len(dead),
                   run.ws.socks[0].timeouts, ms(T35_SLOW1, T35_ATTACH))), {
        'antes_ms': round(ms(T35_SLOW1, T35_ATTACH), 1),
        'depois_ms': round(took or -1, 1)}


def arm_paced_hold(ns):
    """C -- o passo PAUSADO nao estaciona um epoch novo por 0,5 s.

    A troca chega DEPOIS da publicacao e antes do `wait` (e' uma corrida real: o
    refrescador corre a 0,5 s, o fundo da volta a 10 ms). O passo da foto era
    `PAUSED_POLL_S` (0,5 s) sobre um alvo que ja' nao existe -- a volta que fecha
    e re-liga nao pode esperar por ele.
    """
    state = {'switched_at': None}

    def after_publish(run):
        if state['switched_at'] is None and run.source().snap_vid() == A_VID:
            state['switched_at'] = run.clock.t
            run.tabs_now[:] = [tab(B_VID)]
            run.source()._adopt_tab(tab(B_VID), B_VID)

    def factory(run):
        def make(url):
            if url.endswith(A_VID):
                return Sock(run.clock, A_VID, ['paused line'], paused=True)
            return Sock(run.clock, B_VID, ['new line'])
        return make

    run = _setup_arm(ns, [tab(A_VID)], factory, A_VID,
                     after_publish=after_publish).run()
    hit = run.first_publish(B_VID, since=state['switched_at'] or 0.0)
    held = [w for w in run.stop.waits
            if state['switched_at'] is not None and w[0] >= state['switched_at']
            and w[0] <= (hit['t'] if hit else 0.0) and w[1] >= 0.4]
    took = gap_ms(state['switched_at'], hit['t']) if hit else None
    ok = (hit is not None and not held and took is not None
          and took <= 1000.0)
    return ok, ('troca->1a-foto=%.0fms esperas>=0,4s=%d (pausado=%s)'
                % (took or -1, len(held),
                   'pausado' if hit else '-')), {
        'antes_ms': round(max([w[1] for w in held] or [0.0]) * 1000.0 or 500.0, 1),
        'depois_ms': 0.0}


def arm_change_evidence(ns):
    """D -- `tab-switch` NAO e' `same-tab`: a shell so' fala de troca no segundo.

    `YOUTUBE_VIDEO_CHANGED` saiu do log como CONSEQUENCIA de uma adocao de aba
    (17:46:05.039 -> 05.108). A evidencia fica aqui: o id anterior foi lido na
    MESMA aba (`_tab_key`) ou noutra.
    """
    run = Run(ns, 5.0)
    src = run.source()
    parse = ns['parse_snapshot']
    src._tab_key = tab(A_VID)['webSocketDebuggerUrl']
    src._publish(parse(json.dumps(payload(A_VID, ['one'])), now=0.0), 'attached')
    src._publish(parse(json.dumps(payload(B_VID, ['two'])), now=0.0), 'attached')
    same = src.video_change_evidence(B_VID)
    # agora a MESMA pergunta depois de uma troca de aba
    src._adopt_tab(tab(Q_VID), Q_VID)
    src._publish(parse(json.dumps(payload(Q_VID, ['three'])), now=0.0), 'attached')
    switched = src.video_change_evidence(Q_VID)
    unknown = src.video_change_evidence('NAOEXISTE12')
    ok = same == 'same-tab' and switched == 'tab-switch' and unknown == 'none'
    return ok, ('mesma-aba=%r troca-de-aba=%r desconhecido=%r' % (same, switched,
                                                                 unknown)), {}


ARMS = (
    ('A1-DAMP-ROWS', arm_roundtrip),
    ('A2-KEEP-DECLARED', arm_keep_declared),
    ('A3-PAUSED-NO-BEAT', arm_paused_never_beats_playing),
    ('B1-SWITCH-HEALTHY', arm_tab_switch_healthy),
    ('B2-FROZEN-3-PRAZOS', arm_slow_dead_keeps_three),
    ('B3-DEAD+SWITCH-1', arm_slow_dead_tab_changed),
    ('B3b-GUARD-ONLY', arm_slow_dead_guard_only),
    ('B4-RECHECK-LIST', arm_recheck_list),
    ('C-PACED-HOLD', arm_paced_hold),
    ('D-CHANGE-EVIDENCE', arm_change_evidence),
)


def run_arms(ns, quiet=False):
    rows = []
    table = {}
    for name, fn in ARMS:
        try:
            ok, detail, numbers = fn(ns)
        except Exception as exc:                        # noqa: BLE001
            print('%-20s FAIL  excecao %s: %s'
                  % (name, type(exc).__name__, exc))
            rows.append((name, False, str(exc)))
            continue
        if not (quiet and ok):
            print('%-20s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
        rows.append((name, bool(ok), detail))
        if numbers:
            table[name] = numbers
    return rows, table


def print_table(table, extra):
    """A tabela ANTES/DEPOIS por segmento, em ms, com a fonte de cada numero."""
    def row(label, before, after, source):
        print('  %-36s %8s %8s   %s'
              % (label, ('%.0f' % before) if before is not None else 'n/d',
                 ('%.0f' % after) if after is not None else 'n/d', source))
    a1 = table.get('A1-DAMP-ROWS', {})
    b4 = table.get('B4-RECHECK-LIST', {})
    b1 = table.get('B1-SWITCH-HEALTHY', {})
    b3 = table.get('B3-DEAD+SWITCH-1', {})
    b3b = table.get('B3b-GUARD-ONLY', {})
    c = table.get('C-PACED-HOLD', {})
    print('\nSEGMENTO (ms)                            antes   depois   fonte')
    row('rebind damp (17:35 ARMED->REBOUND)', a1.get('antes_ms'),
        a1.get('depois_ms'), 'log vs. rebind_verdict (A1)')
    row('rebind damp com aba a oscilar', 1500, 1500,
        'confirm_s, sem `rows` do candidato (A1)')
    row('troca->1a foto, socket abandonado', b3.get('antes_ms'),
        b3.get('depois_ms'), 'log 45.193->56.396 vs. _run (B3)')
    row('troca->1a foto, socket saudavel', None, b1.get('depois_ms'),
        'oraculo (B1), alvo 1000')
    row('morto: 1o prazo->1a foto (martelo)', b3b.get('antes_ms'),
        b3.get('depois_ms'), 'log 47.914->56.396 vs. _run (B3)')
    row('morto: 1o prazo->1a foto (sem martelo)', b3b.get('antes_ms'),
        b3b.get('depois_ms'), 'log vs. oraculo (B3b), prazo 0,5 s')
    row('lista mudou, epoch nao (1 prazo)', b4.get('antes_ms'),
        b4.get('depois_ms'), 'log 47.914->56.396 vs. _run (B4)')
    row('espera do passo pausado (epoch novo)', c.get('antes_ms'),
        c.get('depois_ms'), 'PAUSED_POLL_S vs. _run (C)')
    row('track-list (shell, NAO meu)', gap_ms(T46_ATTACH, T46_TRACK),
        gap_ms(T46_ATTACH, T46_TRACK), 'log 17:46:13.283->18.474')
    row('first paint (track->overlay)', gap_ms(T35_TRACK, T35_SENT),
        gap_ms(T35_TRACK, T35_SENT), 'log 17:36:02.259->02.422')
    before = gap_ms(T46_REBOUND, T46_FRAME)
    after = ((b1.get('depois_ms') or 0.0) + gap_ms(T46_ATTACH, T46_TRACK)
             + gap_ms(T46_TRACK, T46_FRAME))
    row('alvo assente->1a linha', before, after,
        'log 17:46:10.205->18.547 vs. B1 + track')
    for name, value in extra.items():
        print('  %-36s %8s %8s   %s' % (name, '-', value, 'log'))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)

    if not args.neg_arm:
        ns = lift(SOURCE)
        rows, table = run_arms(ns)
        print_table(table, {})
        fails = [r for r in rows if not r[1]]
        print('\nVERDICT: %s (%d/%d)'
              % ('PASS' if not fails else 'FAIL', len(rows) - len(fails),
                 len(rows)))
        return 0 if not fails else 1

    # -- o braco negativo: um mutante por classe de cura --------------------
    original = read(SOURCE)
    mutants = (
        # (rotulo, ancora, mutante, braco que tem de cair)
        ('damp-rows',
         "    if rows_for(snap, candidate):\n"
         "        return 'adopt', 'rows-ready'\n",
         "    if False:\n        return 'adopt', 'rows-ready'\n",
         'A1-DAMP-ROWS'),
        ('keep-declared',
         "    if declared and declared_open:\n"
         "        return str(declared), 'keep-declared'\n",
         "    if False:\n        return str(declared), 'keep-declared'\n",
         'A2-KEEP-DECLARED'),
        ('stale-socket',
         "        return int(getattr(self, '_sock_epoch', 0) or 0) != int(\n"
         "            getattr(self, '_epoch', 0) or 0)",
         "        return False",
         'B1-SWITCH-HEALTHY'),
        ('hard-close-abort',
         "        abort = getattr(conn, 'abort', None)\n",
         "        abort = None\n",
         'B1-SWITCH-HEALTHY'),
        ('recheck-target',
         "                            and self._recheck_target()):\n",
         "                            and False):\n",
         'B4-RECHECK-LIST'),
        ('adopt-close',
         "            self._hard_close(_conn)\n",
         "            pass\n",
         'B3-DEAD+SWITCH-1'),
        ('first-read-prazo',
         "FIRST_READ_TIMEOUT_S = 0.5\n",
         "FIRST_READ_TIMEOUT_S = 3.0\n",
         'B3b-GUARD-ONLY'),
        ('paced-hold',
         "                _wait = 0.0\n",
         "                pass\n",
         'C-PACED-HOLD'),
    )
    tmpdir = tempfile.mkdtemp(prefix='yt-first-cue-neg-')
    caught = 0
    verdict = True
    try:
        for label, old, new, want in mutants:
            if original.count(old) != 1:
                print('NEG-ARM IMPOSSIVEL: ancora de %r com %d ocorrencias'
                      % (label, original.count(old)))
                return 2
            path = os.path.join(tmpdir, 'src_%s.py' % label.replace('-', '_'))
            with io.open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(original.replace(old, new, 1))
            print('== mutante %s: %s tem de cair' % (label, want))
            ns = lift(path)
            rows, _table = run_arms(ns, quiet=True)
            hit = dict((name, ok) for name, ok, _d in rows).get(want)
            red = hit is False
            caught += 1 if red else 0
            verdict = verdict and red
            print('   %s -> %s' % (want, 'RED' if red else 'SOBREVIVEU'))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print('\nNEG-ARM: %s (%d/%d)'
          % ('PASS' if verdict else 'FAIL', caught, len(mutants)))
    return 1 if verdict else 0


if __name__ == '__main__':
    sys.exit(main())
