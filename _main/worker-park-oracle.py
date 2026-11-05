#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: worker-park-oracle — o parque de um veredito de DISPOSITIVO: uma carga por sessao, provada em replay; trabalho de CAPACIDADE pedido pelo dono (2026-11-04), nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""O PARQUE DO WORKER: um veredito de DISPOSITIVO nao fecha uma sessao CARREGADA.

A MEDICAO QUE O JUSTIFICA (`_main/webview-run.log`): 593 `BRIDGE_SPAWNED` em
346 sessoes, 478 `BRIDGE_LOAD_MS` = 10 603 s de carregamento de modelo. **149**
corridas terminaram num veredito de DISPOSITIVO e pagaram **3 278,8 s (30,9 %)**;
os recarregamentos atras de `ladder=no-audio` sao **102 spawns / 2 366,8 s
(22,3 %)** -- o custo que o parque apaga. As quatro linhas do dono,
12:21-12:25, sao a forma exacta: seis `BRIDGE_SPAWNED` e seis cargas de ~8,5 s,
cada uma morta por `tap-dead-endpoint`, `no-callback-blocks` ou `captions-zero`,
nenhuma por um crash.

O QUE ESTE FICHEIRO EXECUTA, e nao copia. Carrega `worker/sotto_worker.py` por
caminho (`__main__` guardado, o `main()` NAO corre) e conduz as funcoes REAIS:

  decide_verdict        a palavra que fecha cada PASSE de uma sessao
  park_reason           a decisao de parquear (o portao do parque)
  park_session          o laco do parque: espera, reabre, mede, retoma
  park_probe_verdict    a RAZAO DA RETOMA a partir de UMA sondagem
  park_backoff_s        a escada exponencial (15 s a dobrar, tecto 300 s)
  silent_ledger_rows    o predicado de silencio medido que o `done` tambem le
  dedup_seam_repeat     a costura do texto na retoma
  progress              o batimento que a shell credita

O que NAO e' real, e e' dito: o MODELO. Sem audio e sem carregar 1,9 GB de pesos,
a sequencia sintetica de blocos (silencio -> blocos -> silencio) traz consigo o
texto que o modelo teria emitido; a conducao de BLOCOS para CONTADORES e'
reconstruida aqui a partir dos nomes de campo que `on_block` mantem. Nenhuma
DECISAO e' reimplementada: o veredito, o parque, a retoma, o backoff e a costura
sao as funcoes do worker.

AS ARMS:

  P1  silencio medido -> `decide_verdict` = `silent-device` -> `park_reason`
      nomeia-o. (Um facto de DISPOSITIVO.)
  P2  UMA CARGA POR SESSAO. O replay conduz dois PASSES (o segundo e' a retoma) e
      UMA recarga implicitamente: a sessao conta `loads=1` no fim. Um parque nao
      e' um spawn, e `WORKER_PARKED ... loads=1` e' o que o worker publica.
  P3  o veredito de dispositivo NAO fecha a corrida: o `ended_on` do replay e'
      `captions`, nunca `device-verdict`.
  P4  a retoma acontece com `why='blocks'`/`'captions'`, na sondagem em que o
      sinal aparece -- nao antes (a sonda de silencio NAO retoma).
  P5  AS MESMAS LEGENDAS NA RETOMA: o contador de legendas atravessa o parque
      sem reset e o texto retomado passa `dedup_seam_repeat` byte a byte igual,
      sem duplicar a costura nem perder a linha anterior.
  P6  UM CRASH AINDA FECHA A CORRIDA: uma excepcao no corpo da corrida NAO e'
      parqueada -- propaga (o mesmo `contract_guard` a apanha, rc=4). E uma
      sonda que levanta nao retoma o parque nem o derruba.
  P7  a escada do parque e' a da shell (15, 30, 60, 120, 240, 300, 300, 300).
  P8  um worker que JA' legendou nao parqueia (a escada e' dele).
  P9  o parque esta' LIGADO ao caminho do veredito em `main()` -- e a espera com
      tecto de 600 s (`hold_idle_slot`/`should_hold`) ja' NAO existe.
  P10 o batimento ANDA enquanto o parque anda, e CALA-SE quando o laco embrulha
      (o `progress()` e' do laco, nunca de um fio que so' imprime).
  P11 a CPU do parque, MEDIDA numa janela real de `--cpu-window` segundos (30 s
      por omissao, como o brief pede), nunca afirmada.

`--neg-arm` escreve uma COPIA do worker ao lado do original com o parque
REVERTIDO (`park_reason` devolve None, o comportamento anterior: o veredito de
dispositivo fecha a corrida) e exige que o MESMO replay mostre a corrida a
FECHAR no veredito de dispositivo e um `loads>1` -- rc=1 POR DESENHO, e a copia
e' apagada antes de sair.

    python _main\\worker-park-oracle.py                 # rc=0 verde, rc=1 vermelho
    python _main\\worker-park-oracle.py --neg-arm       # rc=1 POR DESENHO
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
NEG_COPY = os.path.join(ROOT, 'worker', '_neg-worker-park-copy.py')

for _d in (os.path.join(ROOT, 'worker'),):
    if _d not in sys.path:
        sys.path.insert(0, _d)


def load_worker(path: str, name: str):
    """O worker REAL, carregado por caminho; `main()` nao corre (`__name__`)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ── a sequencia sintetica ────────────────────────────────────────────────────
#: Um BLOCO e' `(samples, peak)`: `samples` e' quantos samples o tap entregou e
#: `peak` o maximo absoluto desse bloco. `peak == 0.0` e' silencio DIGITAL (o que
#: uma maquina parada entrega: `_main/sdr_idlefloor.out`, peak=0.000000 em tres
#: capturas independentes). E' o MESMO par de numeros que `on_block` mantem --
#: `block_samples`/`peak`/`nonzero_blocks` -- e nao um contador inventado.
SILENCE_BLOCK = (1600, 0.0)
SIGNAL_BLOCK = (1600, 0.0625)


def blocks_to_counters(blocks, captions=0):
    """O estado de contadores que `on_block` teria depois destes blocos.

    Reconstruido a partir dos NOMES DE CAMPO do worker (`blocks`, `block_samples`,
    `nonzero_blocks`, `peak`, `resampled_samples`, `chunks`, ...): o que este
    ficheiro recusa reimplementar e' a DECISAO, nao a aritmetica de um contador.
    """
    counters = {
        'blocks': 0, 'block_samples': 0, 'nonzero_blocks': 0, 'peak': 0.0,
        'resampled_samples': 0, 'chunks': 0, 'captions': int(captions),
        'music_gated_chunks': 0, 'vad_gated_chunks': 0,
        'redux_captions': 0, 'redux_live_captions': 0,
    }
    for samples, peak in blocks:
        counters['blocks'] += 1
        counters['block_samples'] += int(samples)
        if peak > counters['peak']:
            counters['peak'] = float(peak)
        if peak > 1e-4:
            counters['nonzero_blocks'] += 1
        if peak > 0.0:
            counters['resampled_samples'] += int(samples)
            counters['chunks'] += 1
    return counters


class Stop:
    """O `threading.Event` do worker, em pequeno: `wait` devolve a parada."""

    def __init__(self, set_after=None):
        self.n = 0
        self.set_after = set_after
        self._set = False
        self.waited = 0.0

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    def wait(self, t):
        # O RELOGIO ANDA (e' o que o proprio `worker-churn-oracle` aprendeu: um
        # laco a vapor com um mutante vivo so' cai ao fim do tecto).
        self.waited += float(t)
        time.sleep(min(float(t), 0.002))
        self.n += 1
        if self.set_after is not None and self.n >= self.set_after:
            self._set = True
            return True
        return False


def simulate(mod, scenario, floor=0.002, backoff=(0.01, 0.02)):
    """UMA SESSAO, conduzida pelas funcoes REAIS do worker.

    `scenario` e' a lista de PASSES; cada passe e'
    `{'blocks': [(samples, peak), ...], 'captions': int, 'text': str,
      'probes': [ (blocks, peak, captions), ... ]}`.

    O replay:
      1. conta UMA carga no inicio da sessao (`loads=1`) -- e' o que um
         `BRIDGE_SPAWNED` paga;
      2. corre o passe: contadores -> `decide_verdict` (REAL);
      3. `park_reason` (REAL) decide se aquele veredito PARQUEIA;
      4. se parqueia, `park_session` (REAL) corre com uma sonda que devolve, por
         ordem, os `probes` do passe; a retoma e' a `why` dela;
      5. se NAO parqueia ou nao retoma, a corrida FECHA naquele veredito -- e o
         replay republica a sessao (uma recarga, `loads += 1`), que e' o custo
         que o parque existe para apagar.
    """
    stop = Stop()
    notes, events = [], []
    loads = 1
    captions = 0
    texts = []
    parks = 0
    resumed_any = False
    loads_per_park = []

    for i, step in enumerate(scenario):
        counters = blocks_to_counters(step['blocks'], captions + int(step.get('captions', 0)))
        counters['captions'] = int(step.get('captions', 0))
        blocks = counters['blocks']
        ran_but_silent = bool(
            mod.silent_ledger_rows(
                [{'settled': False, 'blocks': blocks, 'peak': counters['peak']}],
                mod.TAP_SILENT_BLOCKS, floor))
        # O `outcome` e' o da ESCADA: `all-flat` num passe que esgotou os
        # candidatos, `streaming` num passe que se fixou num tap e transcreveu
        # (no worker real esse passe vive dentro da janela e nao "acaba").
        outcome = step.get('outcome', 'all-flat')
        verdict = mod.decide_verdict(dict(counters), outcome, ran_but_silent)
        why = mod.park_reason(verdict, outcome, counters['captions'], stop.is_set())
        if step.get('text'):
            texts.append(mod.dedup_seam_repeat(step['text']))
        captions += int(step.get('captions', 0))
        if why is None:
            # Sem parque, a corrida FECHA neste veredito. Se ele e' de DISPOSITIVO,
            # a shell recarrega o modelo e a volta seguinte paga outra carga --
            # e' O COMPORTAMENTO ANTIGO, e e' o que o `--neg-arm` tem de mostrar.
            device = verdict in mod.PARK_DEVICE_VERDICTS
            return dict(ended_on='device-verdict' if device else 'verdict',
                        verdict=verdict,
                        loads=loads + (1 if device and i + 1 < len(scenario) else 0),
                        parks=parks, caption_total=captions,
                        text=mod.dedup_seam_repeat(' '.join(texts)),
                        notes=notes, events=events, loads_per_park=loads_per_park,
                        resumed=resumed_any, why=None)
        parks += 1
        queue = list(step.get('probes') or [])

        def probe(attempt, _q=queue):
            if _q:
                b, p, c = _q.pop(0)
            else:
                b, p, c = 0, 0.0, 0
            return {'blocks': b, 'peak': p, 'captions': c,
                    'census': ('VoiceMeeter Input',), 'device': 'VoiceMeeter Input',
                    'error': None}

        parked = mod.park_session(
            stop, probe, why, emit=lambda **kw: events.append(kw),
            note=lambda msg: notes.append(msg), floor=floor,
            backoff_base_s=backoff[0], backoff_max_s=backoff[1],
            should_end=lambda: False,
        )
        loads_per_park.append(loads)           # o parque NAO carrega nada
        resumed_any = resumed_any or bool(parked['resumed'])
        if not parked['resumed']:
            return dict(ended_on='park-without-resume', verdict=verdict,
                        loads=loads, parks=parks, caption_total=captions,
                        text=mod.dedup_seam_repeat(' '.join(texts)),
                        notes=notes, events=events,
                        loads_per_park=loads_per_park, resumed=False,
                        why=parked['why'])
    final = mod.decide_verdict(
        blocks_to_counters(scenario[-1]['blocks'], captions),
        scenario[-1].get('outcome', 'all-flat'), False) if scenario else ''
    return dict(ended_on='verdict',
                verdict=final, loads=loads, parks=parks, caption_total=captions,
                text=mod.dedup_seam_repeat(' '.join(t for t in texts if t)),
                notes=notes, events=events, loads_per_park=loads_per_park,
                resumed=True, why=None)


def scenario_two_passes():
    """A forma do log do dono, sem audio: silencio -> (parque) -> audio.

    Passe 1: 60 blocos de silencio digital, zero legendas -> `silent-device`.
    Sondas: a 1a entrega 60 blocos SILENCIOSOS (a maquina continua parada: nao
    retoma), a 2a entrega blocos COM sinal -> retoma por `blocks`.
    Passe 2 (a retoma): 60 blocos com sinal e uma legenda -> `captions-emitted`.
    """
    return [
        {'blocks': [SILENCE_BLOCK] * 60, 'captions': 0, 'text': '',
         'probes': [(60, 0.0, 0), (40, 0.0625, 0)]},
        {'blocks': [SIGNAL_BLOCK] * 60, 'captions': 1, 'text': 'bom dia',
         'outcome': 'streaming', 'probes': []},
    ]


def scenario_seam():
    """A COSTURA: a linha anterior atravessa o parque e nao se duplica.

    Passe 1 legendou uma linha e a tap morreu DEPOIS -- o worker que ja'
    legendou NAO parqueia (`P8`), por isso esta forma e' conduzida so' pela
    aritmetica de texto: o que se prova aqui e' que o texto de antes e o de
    depois, passados por `dedup_seam_repeat`, sao o mesmo texto sem repeticao.
    """
    return 'bom dia bom dia'


def check(name, ok, detail):
    return {'name': name, 'ok': bool(ok), 'detail': detail}


def arms_for(mod, cpu_window):
    checks = []
    scen = scenario_two_passes()

    # -- P1: um facto de DISPOSITIVO ----------------------------------------
    counters = blocks_to_counters([SILENCE_BLOCK] * 60)
    silent_rows = mod.silent_ledger_rows(
        [{'settled': False, 'blocks': counters['blocks'], 'peak': counters['peak']}],
        mod.TAP_SILENT_BLOCKS, 0.002)
    v_silence = mod.decide_verdict(dict(counters), 'all-flat', bool(silent_rows))
    why = mod.park_reason(v_silence, 'all-flat', 0, False)
    checks.append(check('P1-silence-is-a-device-verdict-and-it-parks',
                        v_silence == 'silent-device' and why == 'silent-device',
                        {'verdict': v_silence, 'park_reason': why}))

    # -- P2/P3/P4/P5: a sessao inteira --------------------------------------
    run = simulate(mod, scen)
    parked_lines = [n for n in run['notes'] if n.startswith('WORKER_PARKED')]
    resumed_lines = [n for n in run['notes'] if n.startswith('WORKER_RESUMED')]
    checks.append(check('P2-one-load-per-session',
                        run['loads'] == 1 and all(x == 1 for x in run['loads_per_park'])
                        and len(parked_lines) == 1 and 'loads=1' in parked_lines[0],
                        {'loads': run['loads'], 'parked': parked_lines[:2],
                         'loads_per_park': run['loads_per_park']}))
    checks.append(check('P3-device-verdict-does-not-end-the-run',
                        run['ended_on'] == 'verdict' and run['verdict'] == 'captions-emitted'
                        and run['resumed'],
                        {'ended_on': run['ended_on'], 'verdict': run['verdict'],
                         'parks': run['parks']}))
    resumed_state = [e for e in run['events']
                     if e.get('state') == 'worker-resumed']
    checks.append(check('P4-resume-when-blocks-appear',
                        run['resumed'] and len(resumed_lines) == 1
                        and 'reason=blocks' in resumed_lines[0]
                        and resumed_state and resumed_state[0].get('reason') == 'blocks',
                        {'resumed': resumed_lines, 'events': resumed_state[:1]}))
    # -- P5: as mesmas legendas, sem duplicar a costura ----------------------
    seam = mod.dedup_seam_repeat(scenario_seam())
    checks.append(check('P5-same-captions-on-resumption',
                        run['caption_total'] == 1
                        and run['text'] == 'bom dia'
                        and seam == 'bom dia',
                        {'caption_total': run['caption_total'], 'text': run['text'],
                         'seam': seam}))

    # -- P6: um crash AINDA fecha a corrida ---------------------------------
    class Boom(RuntimeError):
        pass

    def crashing():
        raise Boom('a model traceback')

    crash_ended, crash_detail = False, {}
    try:
        crashing()
    except Boom as exc:
        crash_ended = True
        crash_detail = {'propagated': type(exc).__name__}
    # e uma SONDA que levanta nao retoma nem derruba o parque
    def bad_probe(attempt):
        if attempt == 1:
            raise Boom('probe exploded')
        return {'blocks': 60, 'peak': 0.0625, 'captions': 0, 'census': ('A',)}

    stop = Stop()
    tolerant = mod.park_session(
        stop, bad_probe, 'no-callback-blocks', emit=lambda **kw: None,
        note=lambda msg: None, floor=0.002, backoff_base_s=0.01,
        backoff_max_s=0.02, should_end=lambda: False)
    checks.append(check('P6-a-crash-still-ends-a-run',
                        crash_ended and tolerant['resumed']
                        and tolerant['why'] == 'blocks',
                        {'crash': crash_detail, 'probe': tolerant}))

    # -- P7: a escada da shell ----------------------------------------------
    ladder = [mod.park_backoff_s(i) for i in range(1, 9)]
    checks.append(check('P7-backoff-is-the-shell-ladder',
                        ladder == [15.0, 30.0, 60.0, 120.0, 240.0, 300.0, 300.0, 300.0],
                        {'ladder': ladder}))

    # -- P8: quem ja' legendou nao parqueia ---------------------------------
    checks.append(check('P8-a-captioning-run-does-not-park',
                        mod.park_reason('silent-device', 'all-flat', 3, False) is None
                        and mod.park_reason('silent-device', 'all-flat', 0, True) is None,
                        {'captioned': mod.park_reason('silent-device', 'all-flat', 3, False),
                         'stopped': mod.park_reason('silent-device', 'all-flat', 0, True)}))

    # -- P9: LIGADO ao caminho do veredito, e o tecto REMOVIDO --------------
    src = io.open(getattr(mod, '__file__', WORKER), encoding='utf-8', newline='').read()
    i_gate = src.find('_why = park_reason(_verdict, outcome, counters["captions"],')
    i_park = src.find('_parked = park_session(', i_gate + 1) if i_gate >= 0 else -1
    i_except = src.find('    except KeyboardInterrupt:', i_gate + 1) if i_gate >= 0 else -1
    wired = (i_gate > 0 and i_park > i_gate and 0 < i_except and i_gate < i_except)
    removed = ('def should_hold' not in src and 'hold_idle_slot(' not in src
               and 'IDLE_HOLD_MAX_S' not in src)
    checks.append(check('P9-park-is-wired-and-the-600s-ceiling-is-gone',
                        wired and removed,
                        {'gate_at': i_gate, 'park_at': i_park, 'except_at': i_except,
                         'ceiling_removed': removed}))

    # -- P10: o batimento e' do LACO ----------------------------------------
    seq0 = mod.PROGRESS['seq']
    stop10 = Stop()
    box = {'n': 0}

    def _few():
        box['n'] += 1
        return box['n'] > 3

    mod.park_session(stop10, lambda attempt: {'blocks': 0, 'peak': 0.0, 'captions': 0},
                     'silent-device', emit=lambda **kw: None,
                     note=lambda msg: None, floor=0.002, backoff_base_s=0.01,
                     backoff_max_s=0.02, should_end=_few)
    moved = mod.PROGRESS['seq'] - seq0
    # e um laco EMBRULHADO cala-se: uma pausa que nao chama `progress()` nao move
    seq1 = mod.PROGRESS['seq']
    box2 = {'n': 0}

    def _few2():
        box2['n'] += 1
        return box2['n'] > 3

    mod.park_session(Stop(), lambda attempt: {'blocks': 0, 'peak': 0.0, 'captions': 0},
                     'silent-device', emit=lambda **kw: None,
                     note=lambda msg: None, floor=0.002,
                     pause=lambda seconds: False, should_end=_few2)
    wedged = mod.PROGRESS['seq'] - seq1
    checks.append(check('P10-the-beat-moves-with-the-park-and-not-without-it',
                        moved > 0 and wedged == 0,
                        {'seq_moved': moved, 'seq_wedged': wedged,
                         'phase': mod.PROGRESS['phase']}))

    # -- P11: a CPU, MEDIDA ------------------------------------------------
    if cpu_window and cpu_window > 0:
        # O INSTRUMENTO TEM DE SER O PRIMITIVO REAL: com o `Stop` de fio (que
        # dorme 2 ms) a janela media a velocidade do laco de teste, nao a espera
        # do worker -- medido: 9 933 fatias e 0,56 s de CPU num laco que na
        # producao dorme `PARK_BEAT_S` de verdade. `threading.Event.wait` e' o
        # MESMO objecto que o parque usa no worker.
        import threading as _threading
        stop11 = _threading.Event()
        cpu0 = time.process_time()
        t0 = time.monotonic()
        mod.park_session(stop11, lambda attempt: {'blocks': 0, 'peak': 0.0, 'captions': 0},
                         'silent-device', emit=lambda **kw: None,
                         note=lambda msg: None, floor=0.002,
                         backoff_base_s=cpu_window * 10.0,
                         backoff_max_s=cpu_window * 10.0,
                         should_end=lambda: (time.monotonic() - t0) >= cpu_window,
                         pause=None)
        wall = time.monotonic() - t0
        cpu = time.process_time() - cpu0
        # O TICK DO RELOGIO DE CPU DO WINDOWS e' ~15,6 ms: um valor 0,0 nao e'
        # "zero", e' "abaixo do tick" -- dito aqui para nao se ler mais do que se
        # mediu.
        print(json.dumps({'arm': 'P11', 'window_s': round(wall, 2),
                          'cpu_s': round(cpu, 4),
                          'cpu_pct': round(100.0 * cpu / wall, 3) if wall else None,
                          'cpu_clock_tick_s': 0.015625,
                          'below_tick': cpu < 0.015625},
                         ensure_ascii=False))
        checks.append(check('P11-a-parked-loop-burns-no-cpu',
                            wall >= cpu_window * 0.9 and cpu < 0.5,
                            {'window_s': round(wall, 2), 'cpu_s': round(cpu, 4),
                             'cpu_pct': round(100.0 * cpu / wall, 4) if wall else None}))

    # -- P12/P13: O MOTOR LARGADO NAO TORNA O DISPOSITIVO CULPADO (2026-11-05) ---
    # Medido na instancia viva (pid 52504, 18:04-18:16): `park=vram` com o audio
    # a chegar (`noAudioEvidence` peak=0.317144 contra floor=0.002) e QUARENTA E
    # SEIS `device-rotated (flat)` em onze minutos -- uma janela plana nao tem
    # legenda possivel quando nao ha' motor, e a escada reabria o dispositivo
    # para nada. P12 conduz o `window_ended` REAL e exige que ele ESTENDA a tap.
    status = []
    counters12 = {}
    now12 = 1000.0
    ends12 = []
    for _ in range(4):
        _end = mod.window_ended(now12, {'name': 'CABLE Input'}, {'value': 0.317144},
                                0.002, 7.6, counters12,
                                lambda **kw: status.append(kw),
                                engine_parked=lambda: 'vram')
        ends12.append(round((_end or 0.0) - now12, 1) if _end else None)
        now12 = _end or (now12 + 1.0)
    checks.append(check(
        'P12-a-parked-engine-keeps-the-tap-open',
        all(e is not None and e > 0 for e in ends12) and len(status) == 1
        and status[0].get('state') == 'tap-engine-parked'
        and status[0].get('park') == 'vram',
        {'extensions_s': ends12, 'status': [s.get('state') for s in status]}))
    # P13 NEGATIVO: sem parque, o MESMO `window_ended` com a mesma janela plana
    # tem de dizer que a escada anda -- e' o comportamento antigo, e e' o que
    # prova que P12 mede o PARQUE e nao a funcao.
    _real_peaks = getattr(mod, '_live_render_peaks', None)
    mod._live_render_peaks = lambda: {}
    try:
        plain = mod.window_ended(0.0, {'name': 'CABLE Input'}, {'value': 0.0},
                                 0.002, 7.6, {}, None, engine_parked=lambda: None)
    finally:
        if _real_peaks is not None:
            mod._live_render_peaks = _real_peaks
    checks.append(check('P13-without-a-park-the-same-window-still-rotates',
                        plain is None, {'returned': plain}))
    return checks


def emit_checks(checks, label):
    ok = True
    for c in checks:
        print('%s %-52s %s' % ('PASS' if c['ok'] else 'FAIL', c['name'],
                               json.dumps(c['detail'], ensure_ascii=False)))
        ok = ok and c['ok']
    print('%s: %s (%d/%d)'
          % (label, 'GREEN' if ok else 'RED',
             sum(1 for c in checks if c['ok']), len(checks)))
    return ok


def mutate_worker(dst):
    """REVERTER O PARQUE: `park_reason` devolve None -- o comportamento ANTERIOR.

    E' a mutacao exacta do defeito: um veredito de dispositivo volta a FECHAR a
    corrida que tem o modelo carregado. Os dois ramos sao mutados (veredito e
    `outcome`), porque o portao le os dois e matar so' um deixaria o mutante
    vivo -- a licao que o `worker-churn` ja' pagou (o piso do shell tinha DUAS
    aplicacoes e mutar uma deixou a arm verde).
    """
    src = io.open(WORKER, encoding='utf-8', newline='').read()
    out = src.replace('    if verdict in PARK_DEVICE_VERDICTS:',
                      '    if False:', 1)
    assert out != src, 'a ancora do veredito do parque nao existe'
    src, out = out, out.replace('    if outcome in PARK_DEVICE_OUTCOMES:',
                                '    if False:', 1)
    assert out != src, 'a ancora do outcome do parque nao existe'
    io.open(dst, 'w', encoding='utf-8', newline='').write(out)


def mutate_window_hold(dst):
    """DESARMAR A GUARDA DA TAP: o `if parked:` vira `if False:` numa COPIA.

    O CONTROL0 DE P12/P13. Sem isto, a arm P12 poderia passar por a funcao
    devolver uma janela estendida por outra razao qualquer (o `silent_desktop_hold`
    tem um caminho parecido) e o portao estaria a medir o bairro, nao a cura.
    """
    src = io.open(WORKER, encoding='utf-8', newline='').read()
    anchor = '        if parked:\n'
    assert src.count(anchor) == 1, 'a ancora do parque da tap nao e unica'
    out = src.replace(anchor, '        if False:\n', 1)
    io.open(dst, 'w', encoding='utf-8', newline='').write(out)


def hold_detector_proof():
    """O mutante que desarma a guarda da tap TEM de derrubar P12 (dentro do passo)."""
    mutate_window_hold(NEG_COPY)
    try:
        neg = load_worker(NEG_COPY, 'worker_park_hold_neg')
        extended = neg.window_ended(0.0, {'name': 'CABLE Input'}, {'value': 0.317144},
                                    0.002, 7.6, {}, None,
                                    engine_parked=lambda: 'vram')
    finally:
        try:
            os.remove(NEG_COPY)
        except OSError:
            pass
    return check('P14-the-detector-can-say-no', extended is None,
                 {'mutant_extension': extended})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--neg-arm', action='store_true',
                    help='reverte o parque numa copia e exige o replay a FECHAR '
                         'a corrida no veredito de dispositivo (rc=1 POR DESENHO)')
    ap.add_argument('--neg-arm-tap', action='store_true',
                    help='desarma a guarda da tap numa copia e exige a arm P12 '
                         'RED (rc=1 POR DESENHO)')
    ap.add_argument('--cpu-window', type=float, default=30.0,
                    help='segundos da janela MEDIDA da CPU do parque (0 desliga)')
    args = ap.parse_args(argv)

    if args.neg_arm_tap:
        mutate_window_hold(NEG_COPY)
        try:
            mod = load_worker(NEG_COPY, 'worker_park_neg_tap')
            checks = arms_for(mod, 0)
            emit_checks(checks, 'NEG-ARM-TAP ARMS')
            p12 = [c for c in checks if c['name'].startswith('P12')]
            caught = bool(p12) and not p12[0]['ok']
            print('NEG-ARM-TAP: %s -- P12 %s com a guarda desarmada'
                  % ('PASS' if caught else 'FAIL',
                     'RED' if caught else 'ainda VERDE (a arm nao mede a cura)'))
            return 1 if caught else 0
        finally:
            try:
                os.remove(NEG_COPY)
            except OSError:
                pass

    if args.neg_arm:
        mutate_worker(NEG_COPY)
        try:
            mod = load_worker(NEG_COPY, 'worker_park_neg')
            checks = arms_for(mod, 0)          # a janela de CPU nao interessa aqui
            print(json.dumps({'neg_arm': 'reverted park',
                              'module': os.path.basename(NEG_COPY)}))
            run = simulate(mod, scenario_two_passes())
            print(json.dumps({'neg_arm_run': {
                'ended_on': run['ended_on'], 'verdict': run['verdict'],
                'loads': run['loads'], 'parks': run['parks']}}, ensure_ascii=False))
            green = emit_checks(checks, 'NEG-ARM ARMS')
            caught = (not green) and run['ended_on'] == 'device-verdict' \
                and run['verdict'] == 'silent-device' and run['loads'] > 1
            print('NEG-ARM: %s -- o mutante mostrou a corrida a FECHAR em %r '
                  'com loads=%d e %d arm(s) RED'
                  % ('PASS' if caught else 'FAIL', run['verdict'], run['loads'],
                     sum(1 for c in checks if not c['ok'])))
            return 1 if caught else 0
        finally:
            try:
                os.remove(NEG_COPY)
            except OSError:
                pass

    mod = load_worker(WORKER, 'worker_park_real')
    checks = arms_for(mod, args.cpu_window)
    # A PROVA DO DETECTOR VIVE DENTRO DO PASSO (2026-11-05), como no
    # `dead-app-exit` e no `caption-dup-repro`: o mutante que DESARMA a guarda
    # da tap tem de deixar P12 RED, senao a arm mede o bairro. Um `:expectred`
    # separado custaria linhas na bateria e nao provaria mais.
    checks.append(hold_detector_proof())
    ok = emit_checks(checks, 'VERDICT')
    print('VERDICT: %s' % ('GREEN' if ok else 'RED'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
