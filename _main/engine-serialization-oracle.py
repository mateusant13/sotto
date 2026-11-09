#!/usr/bin/env python.exe
# -*- coding: utf-8 -*-
# NO-BUG: orcamento de CPU de ASR (capacidade, nao um id do `_main/bug-ledger.json`)
"""UM ORCAMENTO DE ASR PARA O PROCESSO -- e dois passes que nunca o gastam juntos.

O QUE ESTE ORACULO JULGA, e porque existia o defeito.

MEDIDO 2026-11-09 nesta caixa, com o instrumento da casa:

  * no WORKER vivo (`python _main/shell-thread-cpu.py 37112 --seconds 10
    --top 8`, janela da DM do watcher): 89,2 % de um nucleo, e os fios do topo
    eram as sessoes do motor AO VIVO -- `session-9-intra-op-0` 27,2 %,
    `session-10-intra-op-0` 14,1 %, `session-8-intra-op-0` 7,4 %;
  * no motor de LOTE real (parakeet ONNX int4, uma janela de 3 s, duas
    sessoes no mesmo processo de sonda `pid 42992`, `_main/shell-thread-cpu.py`):
    dois passes a decodificar AO MESMO TEMPO = **dois pools de 2 fios**, e uma
    janela de 3 s leva **2,40 s** de parede a threads=2.

O DEFEITO E' DE ORCAMENTO, e sao dois:

  D1 DOIS ORCAMENTOS NUM PROCESSO. O ao vivo lia `--threads` (encoder 2 +
  decoder 1 + joint 1) e o motor de fundo tinha o SEU numero
  (`REDUX_LIVE_THREADS = 2`). Cada motor respondia por si; ninguem respondia
  pelo processo.

  D2 NENHUM PORTAO ENTRE OS PASSES. `ReduxHiddenSwitch.flush_pending` corre nos
  DOIS modos -- e' assim de proposito ("the tail is the point") -- por isso a
  RETOMA (`load-resume`, quando a carga liberta) e a CAUDA (`stream-end`)
  comecavam um passe do parakeet com o motor AO VIVO a decodificar. Uma janela
  do lote leva 2,40 s e o chunk do stream leva 0,56 s: durante todo o dreno do
  backlog os dois queimavam nucleo ao mesmo tempo. E' a rajada que o watcher
  mediu (`5,3 nucleos` num episodio).

A CURA, e o que este ficheiro executa (nunca procura texto no fonte: extrai as
funcoes REAIS por `ast` e corre-as):

  A1 `asr_budget(2)` -> live 2 / small 1 / batch 2, e
     `max(live, small, batch) <= total`: UM numero, dividido uma vez.
  A2 a parte do lote NAO escala com o `--threads` (o lote nao e' o caminho de
     latencia): `asr_budget(9)['batch']` continua a ser o numero MEDIDO (2), e
     `asr_budget(1)` encolhe tudo para 1.
  A3 as sessoes do stream saem do MESMO orcamento (`StreamAsr.__init__`:
     `_share = asr_budget(_threads)` e `session_options(..., _share[...])`).
  A4 o passe AO VIVO NUNCA ESPERA: `asr_admit('live', ...)` e' `grant` em todos
     os estados (prazo da legenda).
  A5 o LOTE CEDE enquanto o ao vivo decodifica -- pelo `mode` E pelo BATIMENTO
     medido (`live_age_s < ASR_LIVE_FRESH_S`).
  A6 o LOTE CORRE quando o ao vivo parou (idade velha ou nenhum decode ainda).
  A7 uma CAUDA (`stream-end`) nao e' adiada (nao tem tick seguinte).
  A8 o batimento MEDE: `note_live_decode(now=...)` + `live_decode_age(now=...)`.
  A9 `ReduxHiddenSwitch._batch_admission` (a funcao REAL) decide pelo portao.
  A10 `flush_pending` (a funcao REAL) RECUSA arrancar um passe com o ao vivo a
      decodificar, e ARRANCA quando ele parou -- com o audio intacto na fila.
  A11 o worker passa o orcamento do PROCESSO ao interruptor, e o motor de fundo
      recebe a parte do orcamento (nao um numero proprio).
  A12 `StreamAsr.run_chunk` MARCA o batimento (o sinal esta' ligado ao sitio
      que decodifica, nao so' definido).
  A13 a linha de arranque DIZ o orcamento (um numero que governa a CPU do dono
      tem de ser legivel no log).
  A14 `ReduxHiddenSwitch._park` EXISTE e devolve o audio de um passe falhado:
      `engine_policy.run_engine_pass` chama-a no `except` que existe para nao
      perder audio, e o metodo nunca existia -- o handler levantava
      `AttributeError`/`TypeError` e os segundos daquele passe ficavam no vazio.

BRACO NEGATIVO (`--neg-arm`): dez mutacoes, cada uma numa COPIA (nunca em HEAD),
cada uma tem de derrubar O SEU braco. A convencao da casa: rc=1 quando APANHA
todos, rc=0 quando algum sobrevive, rc=2 em erro de setup.

USO
    python _main/engine-serialization-oracle.py
    python _main/engine-serialization-oracle.py --neg-arm
"""
from __future__ import annotations

import ast
import importlib.util
import io
import os
import re
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER_DIR = os.path.join(ROOT, 'worker')
ENGINE = os.path.join(WORKER_DIR, 'engine_switch.py')
WORKER = os.path.join(WORKER_DIR, 'sotto_worker.py')

ROWS = []
_LOADS = [0]


def add(ok, title, detail=''):
    ROWS.append((bool(ok), title, str(detail)[:200]))
    print(('PASS ' if ok else 'FAIL ') + title
          + (('   [' + str(detail)[:200] + ']') if detail and not ok else ''))
    return bool(ok)


def _src(path):
    raw = io.open(path, 'rb').read()
    return raw.decode('utf-8').replace('\r\n', '\n')


def load(path, prefix='engine_under_test'):
    """O modulo POR CAMINHO, com um nome novo a cada carga.

    `worker/` no `sys.path` para os irmaos (`engine_policy`, `live_queue`) que o
    modulo importa por NOME: e' a mesma via do `_main/ort-spin-idle.py`.
    """
    if WORKER_DIR not in sys.path:
        sys.path.insert(0, WORKER_DIR)
    _LOADS[0] += 1
    name = '%s_%d' % (prefix, _LOADS[0])
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def method_node(src, cls_name, fn_name):
    """O `FunctionDef` REAL de um metodo, do texto que embarca."""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == fn_name:
                    return sub
    return None


def bind(mod, nodes, path):
    """Liga os metodos extraidos a um objecto, com os globais do MODULO real."""
    ns = dict(mod.__dict__)
    exec(compile(ast.Module(body=list(nodes), type_ignores=[]), path, 'exec'), ns)

    class _Stub:
        pass

    obj = _Stub()
    for node in nodes:
        setattr(obj, node.name, types.MethodType(ns[node.name], obj))
    return obj


# ── A1/A2: o orcamento ──────────────────────────────────────────────────────

def arms_budget(mod):
    b = mod.asr_budget(2)
    add(b['total'] == 2 and b['live'] == 2 and b['small'] == 1
        and b['batch'] == mod.REDUX_LIVE_THREADS
        and max(b['live'], b['small'], b['batch']) <= b['total'],
        'A1 um orcamento para o processo (asr_budget(2))', b)
    b9 = mod.asr_budget(9)
    b1 = mod.asr_budget(1)
    add(b9['batch'] == mod.REDUX_LIVE_THREADS and b9['live'] == 9
        and b9['batch'] < b9['live']
        and b1['total'] == 1 and b1['live'] == 1 and b1['small'] == 1
        and b1['batch'] == 1,
        'A2 a parte do lote NAO escala com o --threads (e o piso e 1)',
        'b9=%r b1=%r' % (b9, b1))
    return b


# ── A3: as sessoes do stream saem do mesmo orcamento ────────────────────────

def arms_live_sessions(worker_path):
    src = _src(worker_path)
    tree = ast.parse(src)
    share_assign = False
    fed = 0
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'StreamAsr':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign) and len(sub.targets) == 1 \
                        and getattr(sub.targets[0], 'id', None) == '_share' \
                        and isinstance(sub.value, ast.Call) \
                        and getattr(sub.value.func, 'id', None) == 'asr_budget':
                    share_assign = True
                if isinstance(sub, ast.Call) \
                        and getattr(sub.func, 'id', None) == 'session_options':
                    for arg in sub.args:
                        if isinstance(arg, ast.Subscript) \
                                and isinstance(arg.value, ast.Name) \
                                and arg.value.id == '_share':
                            fed += 1
    add(share_assign and fed >= 2,
        'A3 o stream abre as sessoes com a parte DELE do orcamento',
        'assign=%s session_options_fed_by_share=%d' % (share_assign, fed))


# ── A4..A8: a decisao pura e o batimento ────────────────────────────────────

def arms_admit(mod):
    live_states = [
        (0.0, True, False), (0.0, False, False), (None, True, False),
        (None, False, False), (0.0, True, True), (99.0, False, True),
        (2.999, True, False), (3600.0, True, False),
    ]
    bad = [(a, m, f) for a, m, f in live_states
           if mod.asr_admit(mod.ASR_LIVE, a, m, f) != 'grant']
    add(not bad, 'A4 o passe AO VIVO nunca espera (grant em todos os estados)',
        'deferred=%r' % (bad,))

    hot = [
        (0.2, True, False), (0.2, False, False), (2.999, False, False),
        (0.0, True, False),
    ]
    missed = [(a, m, f) for a, m, f in hot
              if mod.asr_admit(mod.ASR_BATCH, a, m, f) != 'defer']
    add(not missed,
        'A5 o lote CEDE com o ao vivo a decodificar (mode OU batimento)',
        'granted=%r' % (missed,))

    cold = [(None, False, False), (3.0, False, False), (40.0, False, False)]
    wrong = [(a, m, f) for a, m, f in cold
             if mod.asr_admit(mod.ASR_BATCH, a, m, f) != 'grant']
    add(not wrong, 'A6 o lote CORRE quando o ao vivo parou', 'deferred=%r' % (wrong,))

    add(mod.asr_admit(mod.ASR_BATCH, 0.0, True, True) == 'grant',
        'A7 uma CAUDA nao e adiada (nao tem tick seguinte)')

    mod.note_live_decode(now=100.0)
    first = mod.live_decode_age(now=100.5)
    mod.note_live_decode(now=101.0)
    add(abs((first or -1) - 0.5) < 1e-9
        and abs(mod._LIVE_CLOCK['last_gap_s'] - 1.0) < 1e-9
        and mod._LIVE_CLOCK['decodes'] >= 2,
        'A8 o batimento MEDE (note_live_decode -> live_decode_age)',
        'age=%.3f gap=%.3f decodes=%d' % (first or -1,
                                          mod._LIVE_CLOCK['last_gap_s'],
                                          mod._LIVE_CLOCK['decodes']))


def arms_heartbeat_wired(worker_path):
    src = _src(worker_path)
    node = method_node(src, 'StreamAsr', 'run_chunk')
    if node is None:
        add(False, 'A12 run_chunk marca o batimento', 'run_chunk ausente')
        return
    called = [sub for sub in ast.walk(node)
              if isinstance(sub, ast.Call)
              and getattr(sub.func, 'id', None) == 'note_live_decode']
    add(bool(called), 'A12 run_chunk MARCA o batimento do passe ao vivo',
        'calls=%d' % len(called))


# ── A9/A10: as funcoes REAIS do interruptor ────────────────────────────────

def _switch_stub(mod, engine_path):
    src = _src(engine_path)
    adm = method_node(src, 'ReduxHiddenSwitch', '_batch_admission')
    defer = method_node(src, 'ReduxHiddenSwitch', '_defer_for_live')
    flush = method_node(src, 'ReduxHiddenSwitch', 'flush_pending')
    park = method_node(src, 'ReduxHiddenSwitch', '_park')
    wait = method_node(src, 'ReduxHiddenSwitch', '_wait_for_live')
    if adm is None or defer is None or flush is None or park is None or wait is None:
        return None, None, None
    obj = bind(mod, [adm, defer, flush, park, wait], engine_path)
    obj.armed = True
    obj.mode = 'stream'
    obj.engine_waits = 0
    obj.engine_wait_s = 0.0
    obj.waits_expired = 0
    obj._inflight = None
    obj._backoff_until = 0.0
    obj.batch_kind = 'parakeet'
    obj.deferred = 0
    obj.runner_failures = 0
    obj.min_free_mb = 0.0
    obj.engine_min_free_mb = 0.0
    obj.lines = []
    obj.log = obj.lines.append
    obj.pending_seconds = lambda: 5.0
    obj.started = []

    class _Eng:
        dir = '<oracle>'
        loads = 0

        def reload_floor_left(self):
            return 0.0

        def name(self):
            return 'onnx'

    class _Pend:
        def __init__(self):
            self.requeued = []

        def requeue(self, held):
            self.requeued.append(list(held))

    obj.engine = _Eng()
    obj.pending = _Pend()
    obj.take_pending = lambda: ([object()], 5 * mod.TARGET_SR)
    obj._start_pass = lambda held, samples, reason: obj.started.append(
        (samples, reason)) or True
    return obj, adm, park


def arms_switch(mod, engine_path):
    obj, adm, park = _switch_stub(mod, engine_path)
    if obj is None:
        add(False, 'A9 _batch_admission existe e decide', 'metodo ausente')
        add(False, 'A10 flush_pending respeita o portao', 'flush_pending ausente')
        return
    mod.note_live_decode(now=time.monotonic())      # ao vivo a decodificar AGORA
    hot = obj._batch_admission('interval', True)
    tail = obj._batch_admission('stream-end', False)
    mod.note_live_decode(now=time.monotonic() - 30.0)   # o ao vivo parou
    obj.mode = 'batch'
    cold = obj._batch_admission('interval', True)
    add(hot[0] is False and hot[1] == 'defer' and tail[1] == 'grant'
        and cold[0] is True and cold[1] == 'grant',
        'A9 _batch_admission decide pelo portao (quente cede, cauda passa, frio corre)',
        'hot=%r tail=%r cold=%r' % (hot, tail, cold))

    # A10: a funcao REAL, ponta a ponta. Quente -> recusa, nada arrancado.
    obj.mode = 'stream'
    obj.deferred = 0
    obj.started = []
    mod.note_live_decode(now=time.monotonic())
    started_hot = obj.flush_pending('interval', True)
    hot_started = list(obj.started)
    hot_deferred = obj.deferred
    deferred_logged = any('reason=defer' in line for line in obj.lines)
    # Frio -> arranca, com o audio TODO (5 s) e sem perder um bloco.
    mod.note_live_decode(now=time.monotonic() - 30.0)
    obj.mode = 'batch'
    started_cold = obj.flush_pending('interval', True)
    add(started_hot is False and not hot_started and hot_deferred == 1
        and deferred_logged
        and started_cold is True and obj.started
        and obj.started[0][0] == 5 * mod.TARGET_SR,
        'A10 flush_pending recusa com o ao vivo a decodificar e arranca depois',
        'hot=%r started=%r deferred=%r logged=%s cold=%r started=%r'
        % (started_hot, hot_started, hot_deferred, deferred_logged, started_cold,
           obj.started))


# ── A11/A13: a fiacao no worker e a linha de arranque ─────────────────────

def arms_wiring(mod, worker_path, engine_path):
    src = _src(worker_path)
    wired = None
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) \
                and getattr(node.func, 'id', None) == 'ReduxHiddenSwitch':
            for kw in node.keywords:
                if kw.arg == 'asr_threads' and isinstance(kw.value, ast.Call) \
                        and getattr(kw.value.func, 'id', None) == 'current_threads':
                    wired = True
    add(bool(wired), 'A11 o worker passa o orcamento do PROCESSO ao interruptor',
        'asr_threads=current_threads() encontrado=%r' % (wired,))

    class _Reader:
        path = '<oracle>'

        def read(self):
            return True, 'oracle', None

        def shed(self):
            return 'leve'

        def park(self):
            return None

    logs = []
    sw = mod.ReduxHiddenSwitch(enabled=False, reader=_Reader(), runner='nope',
                               log_fn=logs.append, engine_threads=2,
                               asr_threads=1)
    legacy = mod.ReduxHiddenSwitch(enabled=False, reader=_Reader(),
                                   runner='nope', log_fn=logs.append,
                                   engine_threads=2)
    budget = getattr(sw, 'asr_budget', None) or {}
    add(getattr(sw.engine, 'threads', None) == 1
        and budget.get('batch') == 1
        and getattr(legacy.engine, 'threads', None) == 2,
        'A11-bis o motor de fundo recebe a parte do orcamento, nao um numero proprio',
        'threads(asr_threads=1)=%r budget=%r legacy=%r'
        % (getattr(sw.engine, 'threads', None), budget,
           getattr(legacy.engine, 'threads', None)))

    logs2 = []

    class _FakeEngine:
        available = True
        missing = []
        dir = '<oracle>/parakeet-redux-onnx-int4'
        threads = 2

        def name(self):
            return 'onnx'

        def load(self):
            return self

        def release(self, reason='idle'):
            return False

    sw2 = mod.ReduxHiddenSwitch(enabled=True, reader=_Reader(), runner='nope',
                                log_fn=logs2.append, engine_threads=2,
                                asr_threads=2, engine=_FakeEngine())
    sw2.boot_line()
    line = next((one for one in logs2 if one.startswith('REDUX_BATCH_ENGINE')), '')
    add('asr_budget=live=2,small=1,batch=2,total=2' in line
        and 'asr_threads=2' in line,
        'A13 a linha de arranque DIZ o orcamento', line[:160])


# ── A14: o `_park` que devolve o audio de um passe falhado ─────────────────

def arms_wait(mod, engine_path):
    """A16: a JANELA do lote espera a vez no ultimo instante (0,0 % de CPU).

    O portao de `flush_pending` decide o INICIO de um passe; um passe ja'
    comecado continua quando o ao vivo comeca a decodificar -- medido a 336,4 %
    de um nucleo na sonda (as sessoes do lote quentes ao lado das do ao vivo,
    com 465 recusas do portao). `AsrSerializedEngine` fecha esse buraco: o
    `transcribe` do lote chama `_wait_for_live` e DORME ate' o ao vivo calar.
    """
    obj, adm, park = _switch_stub(mod, engine_path)
    if obj is None:
        add(False, 'A16 a janela do lote espera a vez', 'extracao falhou')
        return
    # (1) com o ao vivo FRESCO, `_wait_for_live` espera e toca o limite.
    mod.note_live_decode()
    t0 = time.monotonic()
    ok = obj._wait_for_live(None, cap_s=0.12)
    waited = time.monotonic() - t0
    add((ok is False) and waited >= 0.10 and obj.waits_expired == 1,
        'A16-a com o ao vivo a decodificar, o lote DORME ate o limite',
        'ok=%r waited=%.2f expired=%r' % (ok, waited, obj.waits_expired))
    # (2) com o ao vivo parado, a vez e' imediata.
    mod._LIVE_CLOCK['at'] = None
    obj.mode = 'batch'
    t1 = time.monotonic()
    ok2 = obj._wait_for_live(None, cap_s=0.12)
    fast = time.monotonic() - t1
    add((ok2 is True) and fast < 0.05 and obj.engine_waits == 0,
        "A16-b com o ao vivo parado, a vez e' imediata",
        'ok=%r fast=%.3f waits=%r' % (ok2, fast, obj.engine_waits))
    # (3) o PROXY real: `transcribe` passa pela espera e devolve o motor.
    order = []

    class _Inner:
        dir = '<oracle>/inner'

        def transcribe(self, pcm):
            order.append('transcribe')
            return 'linha'

    proxy = mod.AsrSerializedEngine(_Inner(), lambda eng: order.append('wait'))
    got = proxy.transcribe(None)
    add(got == 'linha' and order == ['wait', 'transcribe'],
        "A16-c o motor de lote so' decodifica DEPOIS da espera",
        'order=%r got=%r' % (order, got))


def arms_pass_failure(mod, engine_path):
    """A15: o caminho de FALHA do passe REAL devolve o audio (nao o perde).

    `engine_policy.run_engine_pass` chama `sw._park(...)` dentro do
    `except BaseException` que existe para devolver as janelas ainda NAO
    transcritas. O metodo nunca existia: o handler levantava `AttributeError`
    (ou `TypeError`, com `_park` ja' a string do estacionamento), o thread
    `redux-batch` morria, e `take_pending` ja' tinha LIMPADO a fila -- o audio
    daquele passe ficava no vazio. MEDIDO no log do dono (pid 37112, 18:59-20:36):
    CINCO `REDUX_BATCH_KICK` e ZERO `REDUX_ENGINE_DONE`, com o pendente a cair de
    566,8 s para 170,9 s. Este braco corre a funcao REAL com um motor que estoura.
    """
    pol = getattr(mod, '_policy', None)
    if pol is None or not hasattr(pol, 'run_engine_pass'):
        add(False, 'A15 o passe que falha devolve o audio', 'engine_policy ausente')
        return
    try:
        import numpy as np
    except Exception:                                   # noqa: BLE001
        add(False, 'A15 o passe que falha devolve o audio', 'numpy ausente')
        return

    src = _src(engine_path)
    park_node = method_node(src, 'ReduxHiddenSwitch', '_park')
    rel_node = method_node(src, 'ReduxHiddenSwitch', '_release_engine')
    if park_node is None or rel_node is None:
        add(False, 'A15 o passe que falha devolve o audio', '_park/_release_engine ausente')
        return

    # QUATRO janelas de 1 s: o passe estoura na PRIMEIRA de 3 s, e o que nao
    # foi consumido (a quarta) tem de voltar para a espera.
    held = [np.zeros(16000, dtype=np.float32) for _ in range(4)]

    class _Boom:
        dir = '<oracle>/parakeet-redux-onnx-int4'
        loads = 0
        load_s = 0.0

        def load(self):
            return self

        def name(self):
            return 'onnx'

        def transcribe(self, pcm):
            raise RuntimeError('boom no motor')

        def release(self, reason='idle'):
            return False

    class _Pend:
        def __init__(self):
            self.requeued = []

        def requeue(self, blocks):
            self.requeued.append(list(blocks))

    class _Captions:
        def put(self, row):
            pass

    obj = bind(mod, [park_node, rel_node], engine_path)
    obj.mode = 'batch'
    obj.batch_kind = 'parakeet'
    obj._release_gate = None
    obj.rate = mod.TARGET_SR
    obj.producer = mod.REDUX_PRODUCER
    obj.engine_window_s = 3.0
    obj.engine = _Boom()
    obj.pending = _Pend()
    obj._captions = _Captions()
    obj.segments = 0
    obj.segment_lines = 0
    obj.runner_failures = 0
    obj._backoff_until = 0.0
    obj.lines = []
    obj.log = obj.lines.append
    obj.rss = lambda: 0.0
    obj.pending_seconds = lambda: 2.0
    escaped = None
    try:
        pol.run_engine_pass(obj, held, sum(int(b.size) for b in held), 'oracle')
    except BaseException as exc:                        # noqa: BLE001
        escaped = '%s: %s' % (type(exc).__name__, exc)
    rest = getattr(pol, '_slice_blocks')(held, 48000)
    add(escaped is None and obj.pending.requeued
        and obj.pending.requeued[0] == rest
        and obj.runner_failures == 1
        and any('REDUX_BATCH_FAILED' in line for line in obj.lines),
        'A15 o passe que falha devolve o audio e NAO morre em silencio',
        'escaped=%r requeued=%r failures=%r lines=%r'
        % (escaped, [len(x) for x in obj.pending.requeued],
           obj.runner_failures, [l[:60] for l in obj.lines]))


def arms_park(mod, engine_path):
    obj, adm, park = _switch_stub(mod, engine_path)
    if park is None:
        add(False, 'A14 _park devolve o audio de um passe falhado', 'metodo ausente')
        return
    blocks = ['bloco-1', 'bloco-2']
    ok = obj._park(blocks, 'engine-Boom', extra='windows=1')
    pend = getattr(obj, 'pending', None)
    add(ok is True and pend is not None and pend.requeued
        and pend.requeued[0] == blocks
        and getattr(obj, 'runner_failures', 0) == 1,
        'A14 _park EXISTE e devolve o audio de um passe falhado',
        'ok=%r requeued=%r failures=%r'
        % (ok, getattr(pend, 'requeued', None), getattr(obj, 'runner_failures', None)))


# ── o conjunto ─────────────────────────────────────────────────────────────

def arms(engine_path=ENGINE, worker_path=WORKER):
    mod = load(engine_path)
    arms_budget(mod)
    arms_live_sessions(worker_path)
    arms_admit(mod)
    arms_heartbeat_wired(worker_path)
    arms_switch(mod, engine_path)
    arms_wiring(mod, worker_path, engine_path)
    arms_park(mod, engine_path)
    arms_pass_failure(mod, engine_path)
    arms_wait(mod, engine_path)


def bad_rows():
    return [row for row in ROWS if not row[0]]


# ── o braco negativo ──────────────────────────────────────────────────────

MUTANTS = (
    # (slug, alvo, ficheiro, find, replace)
    ('M1 lote com numero proprio', 'A2', 'engine',
     "'batch': min(REDUX_LIVE_THREADS, total),", "'batch': total,"),
    ('M2 o batimento desarmado', 'A5', 'engine',
     'ASR_LIVE_FRESH_S = 3.0', 'ASR_LIVE_FRESH_S = 0.0'),
    ('M3 o ao vivo deixa de ter prioridade', 'A4', 'engine',
     '    if who == ASR_LIVE:\n        return "grant"',
     '    if who == ASR_LIVE:\n        return "defer"'),
    ('M4 a cauda e adiada', 'A7', 'engine',
     '    if final:\n        return "grant"', '    if final:\n        return "defer"'),
    ('M5 o motor recebe um numero proprio', 'A11-bis', 'engine',
     "            return min(engine_threads, self.asr_budget['batch'])",
     '            return REDUX_LIVE_THREADS'),
    ('M6 o worker nao passa o orcamento', 'A11 ', 'worker',
     '            asr_threads=current_threads(),\n', ''),
    ('M7 run_chunk deixa de marcar', 'A12', 'worker',
     '        note_live_decode()\n', ''),
    ('M8 flush_pending ignora o portao', 'A10', 'engine',
     'admitted, why, live_age = self._batch_admission(reason, respect_memory_floor)',
     "admitted, why, live_age = True, 'grant', None"),
    ('M9 o stream divide por si', 'A3', 'worker',
     '        _share = asr_budget(_threads)',
     "        _share = {'live': _threads, 'small': _threads,"
     " 'batch': _threads, 'total': _threads}"),
    ('M10 a cauda fura o portao', 'A9', 'engine',
     'final=not deferrable)', 'final=True)'),
    ('M12 o proxy deixa de esperar', 'A16', 'engine',
     '    def transcribe(self, pcm):\n        self._wait(self)\n'
     '        return self._inner.transcribe(pcm)',
     '    def transcribe(self, pcm):\n'
     '        return self._inner.transcribe(pcm)'),
    ('M13 o limite de espera e zero', 'A16', 'engine',
     'cap = ASR_LIVE_WAIT_S if cap_s is None else float(cap_s)',
     'cap = 0.0'),
    ('M11 o `_park` deixa de devolver o audio', 'A15', 'engine',
     '        if _policy is None:\n            return False\n'
     '        _policy.park_pass(self, held, why, extra=extra)\n'
     '        return True',
     '        return False'),
)


def neg_arm():
    base_engine, base_worker = _src(ENGINE), _src(WORKER)
    tmpdir = tempfile.mkdtemp(prefix='neg-engine-serial-')
    caught = []
    survived = []
    try:
        for slug, target, where, find, replace in MUTANTS:
            text = base_engine if where == 'engine' else base_worker
            if find not in text:
                print('NEG-ARM SETUP: %s -- a ancora nao existe no ficheiro REAL: %r'
                      % (slug, find))
                return 2
            mutated = text.replace(find, replace, 1)
            if mutated == text:
                print('NEG-ARM SETUP: %s -- a mutacao nao mudou nada' % slug)
                return 2
            # UM DIRECTORIO POR MUTANTE, e o `__pycache__` desligado: o loader
            # do CPython valida o `.pyc` por (mtime inteiro, tamanho), e duas
            # mutacoes do MESMO tamanho escritas no mesmo segundo reutilizavam o
            # bytecode da anterior -- medido neste oraculo: o M3 (grant->defer,
            # mesmo tamanho do M2) correu contra o modulo do M2 e o braco certo
            # disse PASS. Um controlo que le um ficheiro que ja' nao e' o dele
            # certifica o mutante errado.
            one = os.path.join(tmpdir, slug.split()[0])
            os.makedirs(one, exist_ok=True)
            engine_path = os.path.join(one, 'engine_switch.py')
            worker_path = os.path.join(one, 'sotto_worker.py')
            io.open(engine_path, 'w', encoding='utf-8', newline='').write(
                mutated if where == 'engine' else base_engine)
            io.open(worker_path, 'w', encoding='utf-8', newline='').write(
                mutated if where == 'worker' else base_worker)
            ROWS.clear()
            print('=== NEG-ARM %s (%s)' % (slug, target))
            arms(engine_path, worker_path)
            red = bad_rows()
            hit = any(row[1].startswith(target) for row in red)
            print('NEG-ARM %s %s -- %d arm(s) RED, %s entre elas=%s'
                  % (slug, 'PASS' if hit else 'FAIL', len(red), target, hit))
            (caught if hit else survived).append(slug)
    finally:
        for slug, _t, _w, _f, _r in MUTANTS:
            one = os.path.join(tmpdir, slug.split()[0])
            for name in ('engine_switch.py', 'sotto_worker.py'):
                try:
                    os.remove(os.path.join(one, name))
                except OSError:
                    pass
            try:
                os.rmdir(one)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
    print('\nNEG-ARM: %d/%d mutantes apanhados' % (len(caught), len(MUTANTS)))
    if survived:
        print('SOBREVIVERAM: ' + '; '.join(survived))
    # A CONVENCAO DA CASA: rc=1 quando APANHA (o passo vizinho e' `:expectred 1`).
    return 1 if not survived else 0


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    arms()
    bad = bad_rows()
    print('\n%d/%d arms green' % (len(ROWS) - len(bad), len(ROWS)))
    print('VERDICT: ' + ('PASS' if not bad else 'FAIL'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
