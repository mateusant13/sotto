#!/usr/bin/env python3
"""first-capture-fast-oracle -- a PRIMEIRA legenda depois de um arranque, medida nas DECISOES.

O DEFEITO, medido no arranque dele (2026-11-04, `_main/webview-run.log`, pid 13904):

    12:15:15.887  BRIDGE_SPAWNED pid=13904
    12:15:31.059  STATUS_APPLIED text="capture-started"      (+15,2 s: modelo 6,2 s + gate 4,6 s
                                                              + ESCADA 3,8 s)
    12:15:33.774  BRIDGE_STATUS_ERROR state="tap-dead-endpoint"  (+2,0 s sem um bloco)
    12:15:34.368  BRIDGE_DEATH rc=3 kind=no-audio
    12:15:34.369  BRIDGE_RESTART reason=exit ladder=no-audio in_ms=15000
    12:15:49.377  BRIDGE_SPAWNED pid=56188                  (+15 s de ESPERA)
    12:16:03.721  CAPTION_PAINT "the tip"                   (+48,4 s do arranque)

Tres custos empilhados, e cada um tem uma decisao propria:

  (a) ESCOLHER O ENDPOINT QUE ESTA' A TOCAR NA PRIMEIRA PICAGEM. A escada abriu
      `VoiceMeeter Input` (zero callbacks) enquanto o audio saia noutro sitio. A
      decisao e' `signal_ranked_next(..., peaks=...)` -- a MESMA que ja' existia
      para a rotacao, agora executada ANTES da primeira janela e com o numero
      publicado (`CAPTURE_FIRST_PICK ... probe_ms=`).
  (b) DECLARAR MORTO MAIS DEPRESSA: `first_block_decided` (piso de 2 s), e --
      o que importa -- NAO confundir "candidato morto" com "maquina calada"
      (`dead_first_block_plan`: sem som em endpoint nenhum a tap FICA aberta, e
      a espera do desktop parado governa como sempre).
  (c) NAO DORMIR 15 s POR UMA MORTE DE DISPOSITIVO: `device_death_delay`, a
      decisao que `_schedule_restart` passou a usar -- troca de endpoint em
      250 ms quando ha' som a sair, com um tecto de duas trocas, e o backoff
      inteiro quando trocar nao pode arranjar nada.

O QUE ESTE FICHEIRO EXECUTA (nao copia): `signal_ranked_next`, `first_block_decided`,
`dead_first_block_plan`, `silent_desktop_hold` e `device_death_delay` REAIS, mais o
`WorkerBridge._schedule_restart` REAL com um `threading.Timer` FALSO. Nenhum
dispositivo e' aberto para ESCRITA, nada e' silenciado, e a app NAO e' lancada: a
unica leitura de dispositivo e' o medidor (`IAudioMeterInformation`, so' leitura),
usada para publicar o custo real da sonda nesta maquina.

Uso:  python _main/first-capture-fast-oracle.py [--neg-arm]
rc=0  GREEN  (ou, no --neg-arm, os 4 mutantes apanhados -> rc=1, que e' o que
      `:expectred` da bateria exige)
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
WASAPI = os.path.join(ROOT, 'worker', 'wasapi_loopback.py')

for _d in (os.path.join(ROOT, 'app', 'webview'), os.path.join(ROOT, 'worker')):
    if _d not in sys.path:
        sys.path.insert(0, _d)

FLOOR = 0.002
WINDOW_S = 6.0
HOLD_CAP_S = 60.0
#: A aceitacao da troca: uma troca de endpoint nao pode custar mais que isto.
#: 250 ms e' o atraso pedido; 1000 ms e' o tecto do que ainda se chama "sem espera".
SWITCH_BUDGET_MS = 1000


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeTimer:
    """Um `threading.Timer` que nao dispara: so' registra o intervalo ARMADO."""

    armed = []

    def __init__(self, interval, function, args=None, kwargs=None):
        self.interval = interval
        self.function = function
        FakeTimer.armed.append(interval)

    def start(self):
        pass

    def cancel(self):
        pass


def bridge_stub(mod, sink, **attrs):
    """Um `WorkerBridge` sem `__init__`: os atributos que `_schedule_restart` le'."""
    b = object.__new__(mod.WorkerBridge)
    b.stopped = False
    b.restarts = 0
    b.no_audio_restarts = 0
    b.backoff_base = 1000
    b.backoff_max = 30000
    b.no_audio_backoff_base = 15000
    b.no_audio_backoff_max = 300000
    b.no_audio_restart_cap = 3
    b._restart_timer = None
    b._restart = lambda: None
    b._arm_audio_resume = lambda *a, **k: None
    b.captions = 0
    b.last_device_status = None
    b.log = sink
    for key, value in attrs.items():
        setattr(b, key, value)
    return b


class FakeAudioPlaying:
    """`audio_playing` FALSO: a unica coisa que `_schedule_restart` lhe pergunta."""

    PEAK_FLOOR = 0.002

    def __init__(self, name='', peak=0.0):
        self._row = (name, float(peak))

    def loudest(self, peaks=None):  # noqa: D401 - assinatura do modulo real
        return self._row


def with_audio_playing(fake):
    """Poe o modulo FALSO em `sys.modules` e devolve o que la' estava."""
    previous = sys.modules.get('audio_playing')
    sys.modules['audio_playing'] = fake
    return previous


def restore_audio_playing(previous):
    if previous is None:
        sys.modules.pop('audio_playing', None)
    else:
        sys.modules['audio_playing'] = previous


def cand(name, endpoint_id, rung='a'):
    return {'name': 'WASAPI loopback: %s' % name, 'endpoint_id': endpoint_id,
            'index': None, 'rung': rung, 'meter_peak': None}


def counting_reader(payload, sleep_s=0.0):
    """Um medidor FALSO que conta as leituras -- e cobra o tempo que ele custou."""
    calls = []

    def read():
        calls.append(time.monotonic())
        if sleep_s:
            time.sleep(sleep_s)
        return dict(payload)

    return read, calls


def arms(shell_mod, worker_mod, wasapi_mod):
    """[(nome, ok, detalhe)] -- `ok` e' o resultado das funcoes REAIS."""
    out = []

    def check(name, ok, detail):
        out.append((name, bool(ok), detail))

    dead = cand('VoiceMeeter Input', 'ep-dead')
    live = cand('CABLE Input', 'ep-live')

    # -- 1: a PRIMEIRA PICAGEM segue o medidor (o custo que valia 15 s) --------
    ladder = [dict(dead), dict(live)]
    reader, calls = counting_reader({'ep-dead': 0.0, 'ep-live': 0.44})
    t0 = time.monotonic()
    picked = worker_mod.signal_ranked_next(ladder, 0, FLOOR, peaks=reader)
    pick_ms = int((time.monotonic() - t0) * 1000.0)
    delay, ladder_name, why = shell_mod.device_death_delay(True, 0, True)
    check('1-dead-first-pick-switches-fast',
          picked.get('endpoint_id') == 'ep-live' and ladder[0].get('endpoint_id') == 'ep-live'
          and delay <= SWITCH_BUDGET_MS and int(delay) != 15000,
          {'chosen': picked.get('name'), 'slot0': ladder[0].get('name'),
           'reads': len(calls), 'pick_ms': pick_ms,
           'switch_delay_ms': delay, 'ladder': ladder_name, 'why': why})

    # -- 2: quando o primeiro JA' e' o que toca, a picagem nao custa mais ------
    ladder2 = [dict(live), dict(dead)]
    reader2, calls2 = counting_reader({'ep-dead': 0.0, 'ep-live': 0.44}, sleep_s=0.05)
    t0 = time.monotonic()
    picked2 = worker_mod.signal_ranked_next(ladder2, 0, FLOOR, peaks=reader2)
    probe_ms = int((time.monotonic() - t0) * 1000.0)
    # E o custo REAL da sonda nesta maquina, medido uma vez (so' medidores).
    t0 = time.monotonic()
    real = wasapi_mod.live_endpoint_order()
    real_ms = int((time.monotonic() - t0) * 1000.0)
    check('2-live-first-pick-costs-one-read',
          picked2.get('endpoint_id') == 'ep-live' and ladder2[0].get('endpoint_id') == 'ep-live'
          and len(calls2) == 1 and probe_ms >= 40 and real_ms < 5000,
          {'slot0': ladder2[0].get('name'), 'reads': len(calls2),
           'fake_probe_ms': probe_ms, 'real_meter_endpoints': len(real),
           'real_meter_ms': real_ms})

    # -- 3: a morte por dispositivo reinicia em 250 ms, NAO em 15 s -----------
    FakeTimer.armed = []
    shell_mod.threading.Timer = FakeTimer
    logs = []
    previous = with_audio_playing(FakeAudioPlaying('CABLE Input', 0.44))
    try:
        b = bridge_stub(shell_mod, logs.append)
        b._schedule_restart('exit', no_audio=True)
    finally:
        restore_audio_playing(previous)
    armed_ms = FakeTimer.armed[-1] * 1000.0 if FakeTimer.armed else None
    joined = '\n'.join(logs)
    check('3-device-death-restarts-in-250ms',
          armed_ms == float(shell_mod.DEVICE_SWITCH_DELAY_MS)
          and armed_ms <= SWITCH_BUDGET_MS
          and 'ENDPOINT_SWITCH reason=device-death-switch' in joined
          and 'ladder=device-switch' in joined and 'in_ms=15000' not in joined,
          {'armed_ms': armed_ms, 'log': joined.strip().splitlines()[:3]})

    # -- 4: o tecto de DUAS trocas, e depois o backoff inteiro ----------------
    FakeTimer.armed = []
    logs = []
    previous = with_audio_playing(FakeAudioPlaying('CABLE Input', 0.44))
    try:
        b = bridge_stub(shell_mod, logs.append, device_switches=shell_mod.DEVICE_SWITCH_FREE)
        b._schedule_restart('exit', no_audio=True)
    finally:
        restore_audio_playing(previous)
    armed_ms = FakeTimer.armed[-1] * 1000.0 if FakeTimer.armed else None
    joined = '\n'.join(logs)
    check('4-device-switch-is-bounded',
          armed_ms == 15000.0 and 'device-switch-budget-spent' in joined,
          {'armed_ms': armed_ms, 'budget': shell_mod.DEVICE_SWITCH_FREE,
           'log': joined.strip().splitlines()[:2]})

    # -- 5: maquina calada (nada a renderizar) nao ganha troca -- o backoff fica
    FakeTimer.armed = []
    logs = []
    previous = with_audio_playing(FakeAudioPlaying('VoiceMeeter Input', 0.0))
    try:
        b = bridge_stub(shell_mod, logs.append)
        b._schedule_restart('exit', no_audio=True)
    finally:
        restore_audio_playing(previous)
    armed_ms = FakeTimer.armed[-1] * 1000.0 if FakeTimer.armed else None
    joined = '\n'.join(logs)
    check('5-quiet-machine-keeps-the-backoff',
          armed_ms == 15000.0
          and 'nothing-is-rendering-a-switch-cannot-help' in joined,
          {'armed_ms': armed_ms, 'log': joined.strip().splitlines()[:2]})

    # -- 6: um CRASH (rc=1) continua a ser respondido em 1 s ------------------
    FakeTimer.armed = []
    logs = []
    previous = with_audio_playing(FakeAudioPlaying('CABLE Input', 0.44))
    try:
        b = bridge_stub(shell_mod, logs.append)
        b._schedule_restart('exit', no_audio=False)
    finally:
        restore_audio_playing(previous)
    armed_ms = FakeTimer.armed[-1] * 1000.0 if FakeTimer.armed else None
    joined = '\n'.join(logs)
    check('6-crash-death-keeps-the-backoff',
          armed_ms == 1000.0 and 'ladder=retry' in joined and 'ENDPOINT_SWITCH' not in joined,
          {'armed_ms': armed_ms, 'log': joined.strip().splitlines()[-1:]})

    # -- 7: o piso de 2 s nao corta um endpoint BOM ---------------------------
    # MEDIDO (pid 56188): a primeira legenda chegou 1 940 ms depois de
    # `capture-started`, portanto o primeiro BLOCO chegou antes disso. O piso
    # tem de estar ACIMA desse numero e abaixo da espera do desktop parado.
    rotate_1940, _ = worker_mod.first_block_decided(0.0, 0, 1.94)
    rotate_2000, waited = worker_mod.first_block_decided(0.0, 0, 2.0)
    rotate_after_block, _ = worker_mod.first_block_decided(0.0, 1, 2.0)
    check('7-dead-deadline-2s-does-not-clip-a-live-endpoint',
          not rotate_1940 and rotate_2000 and not rotate_after_block
          and waited == 2000
          and worker_mod.TAP_FIRST_BLOCK_MAX_S < worker_mod.TAP_SILENT_DESKTOP_MAX_S,
          {'at_1940ms_rotates': rotate_1940, 'at_2000ms_rotates': rotate_2000,
           'waited_ms': waited, 'budget_s': worker_mod.TAP_FIRST_BLOCK_MAX_S,
           'silent_hold_cap_s': worker_mod.TAP_SILENT_DESKTOP_MAX_S})

    # -- 8: A ARM QUE MAIS IMPORTA -- a maquina calada NAO e' um candidato morto
    quiet_plan = worker_mod.dead_first_block_plan(
        [dict(dead), dict(live)], 0, dead, {'ep-dead': 0.0, 'ep-live': 0.0}, FLOOR)
    hold_0 = worker_mod.silent_desktop_hold(0.0, FLOOR, {'ep-dead': 0.0, 'ep-live': 0.0},
                                            WINDOW_S, 0, HOLD_CAP_S)
    hold_1 = worker_mod.silent_desktop_hold(0.0, FLOOR, {'ep-dead': 0.0}, WINDOW_S, 1, HOLD_CAP_S)
    unreadable = worker_mod.dead_first_block_plan(
        [dict(dead), dict(live)], 0, dead, {}, FLOOR)
    check('8-desktop-quiet-is-not-a-dead-endpoint',
          quiet_plan['action'] == 'wait' and str(quiet_plan['why']) == 'desktop-quiet'
          and hold_0 == 12.0 and hold_1 == 24.0
          and unreadable['action'] == 'dead',
          {'plan': quiet_plan['action'], 'why': quiet_plan['why'],
           'hold_window_0_s': hold_0, 'hold_window_1_s': hold_1,
           'unreadable_meter': unreadable['action']})

    # -- 9: com som NOUTRO endpoint a troca e' feita AQUI (sem morrer) --------
    plan = worker_mod.dead_first_block_plan(
        [dict(dead), dict(live)], 0, dead, {'ep-dead': 0.0, 'ep-live': 0.44}, FLOOR)
    spent = worker_mod.dead_first_block_plan(
        [dict(dead), dict(live)], 0, dead, {'ep-dead': 0.0, 'ep-live': 0.44}, FLOOR,
        switches=worker_mod.TAP_DEAD_SWITCH_MAX)
    check('9-signal-elsewhere-rotates-in-process',
          plan['action'] == 'rotate' and plan['next_index'] == 1
          and plan['next'] and plan['next'].get('endpoint_id') == 'ep-live'
          and spent['action'] == 'dead',
          {'action': plan['action'], 'next_index': plan['next_index'],
           'why': plan['why'], 'after_budget': spent['action'],
           'budget': worker_mod.TAP_DEAD_SWITCH_MAX})

    # -- 10: fiacao -- as decisoes estao LIGADAS onde a corrida as usa --------
    worker_src = open(WORKER, encoding='utf-8', newline='').read()
    shell_src = open(SHELL, encoding='utf-8', newline='').read()
    wasapi_src = open(WASAPI, encoding='utf-8', newline='').read()
    wiring = {
        'rung-a-le-menos-o-medidor': 'live = wasapi_loopback.live_endpoint_order()' in worker_src,
        'nenhum-cliente-por-endpoint-na-escada':
            'wasapi_loopback.loopback_device_specs()' not in worker_src,
        'capture-first-pick-publicado': 'CAPTURE_FIRST_PICK' in worker_src,
        'a-picagem-pergunta-ao-medidor': 'signal_ranked_next(candidates, 0, tap_floor)' in worker_src,
        'tap-dead-fast-publicado': 'TAP_DEAD_FAST' in worker_src,
        'tap-quiet-publicado': 'TAP_QUIET_DESKTOP' in worker_src,
        'a-escada-consulta-o-plano': 'dead_first_block_plan(' in worker_src,
        'a-espera-rearma-a-pergunta': "counters.pop('quiet', None)" in worker_src,
        'a-shell-registra-a-troca': 'ENDPOINT_SWITCH reason=' in shell_src,
        'a-shell-usa-a-decisao': 'device_death_delay(' in shell_src,
        'o-medidor-da-shell-e-so-leitura': 'audio_playing.loudest()' in shell_src,
    }
    check('10-wiring', all(wiring.values()), wiring)

    return out


def report(results):
    ok = True
    for name, passed, detail in results:
        print('ARM %-52s %s' % (name, 'PASS' if passed else 'FAIL'))
        if not passed:
            print('    %r' % (detail,))
        ok = ok and passed
    return ok


def run(worker_path, shell_path, wasapi_path, label='', verbose=True):
    worker_mod = load(worker_path, 'sotto_worker_under_test')
    shell_mod = load(shell_path, 'sotto_webview_under_test')
    wasapi_mod = load(wasapi_path, 'wasapi_loopback_under_test')
    results = arms(shell_mod, worker_mod, wasapi_mod)
    if verbose:
        print('-- %s' % (label or 'arvore'))
        report(results)
    return results


#: Os quatro mutantes que o `--neg-arm` tem de apanhar, nomeados pelo que
#: REINTRODUZEM (nao pela linha que mexem): cada um e' um defeito medido.
MUTANTS = (
    ('m1-a-espera-do-desktop-parado-removida', 'worker',
     ('    plan.update(action="wait", why="desktop-quiet")',
      '    plan.update(action="dead", why="desktop-quiet")  # MUTANTE'),
     '8-desktop-quiet-is-not-a-dead-endpoint'),
    ('m2-o-piso-do-candidato-morto-volta-a-espera-inteira', 'worker',
     ('TAP_FIRST_BLOCK_MAX_S = 2.0', 'TAP_FIRST_BLOCK_MAX_S = 60.0  # MUTANTE'),
     '7-dead-deadline-2s-does-not-clip-a-live-endpoint'),
    ('m3-a-primeira-picagem-salta-o-medidor', 'worker',
     ('    if k >= len(candidates):\n        return None',
      '    if k >= len(candidates):\n        return None\n'
      '    return candidates[k]  # MUTANTE: a primeira picagem nao pergunta nada'),
     '1-dead-first-pick-switches-fast'),
    ('m4-o-backoff-de-15s-volta-para-a-morte-de-dispositivo', 'shell',
     ('DEVICE_SWITCH_FREE = 2', 'DEVICE_SWITCH_FREE = 0  # MUTANTE'),
     '3-device-death-restarts-in-250ms'),
)


def mutate(path, needle, replacement):
    """Escreve uma COPIA ao lado do original, com `needle` trocado. Devolve o caminho."""
    text = open(path, encoding='utf-8', newline='').read()
    if needle not in text:
        return None
    head, tail = os.path.split(os.path.abspath(path))
    copy = os.path.join(head, '_mutant-first-capture-%d.py' % os.getpid())
    shutil.copyfile(path, copy)
    with open(copy, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text.replace(needle, replacement, 1))
    return copy


def neg_arm(worker_path, shell_path, wasapi_path):
    """Muta uma COPIA por defeito e exige que o braco DAQUELE mutante fique RED."""
    caught = 0
    for name, which, (needle, replacement), target in MUTANTS:
        original = worker_path if which == 'worker' else shell_path
        # O ficheiro CRLF: a ancora tem de seguir o separador que ele usa.
        text = open(original, encoding='utf-8', newline='').read()
        if '\r\n' in text:
            needle = needle.replace('\n', '\r\n')
            replacement = replacement.replace('\n', '\r\n')
        copy = mutate(original, needle, replacement)
        if copy is None:
            print('NEG-ARM %-52s ANCORA AUSENTE -- o oraculo precisa de ser revisto' % name)
            continue
        try:
            results = run(worker_path if which != 'worker' else copy,
                          shell_path if which != 'shell' else copy,
                          wasapi_path, label=name, verbose=False)
        finally:
            try:
                os.remove(copy)
            except OSError:
                pass
        reds = [arm for arm, passed, _ in results if not passed]
        hit = target in reds
        print('NEG-ARM %-52s %s  (%s; red=%s)'
              % (name, 'PASS' if hit else 'FAIL', target, ','.join(reds) or 'nenhum'))
        caught += 1 if hit else 0
    print('NEG-ARM: %s -- %d/%d mutante(s) apanhado(s)'
          % ('PASS' if caught == len(MUTANTS) else 'FAIL', caught, len(MUTANTS)))
    return caught == len(MUTANTS)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--worker', default=WORKER)
    ap.add_argument('--shell', default=SHELL)
    ap.add_argument('--wasapi', default=WASAPI)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    worker = os.path.abspath(args.worker)
    shell = os.path.abspath(args.shell)
    wasapi = os.path.abspath(args.wasapi)
    if args.neg_arm:
        ok = neg_arm(worker, shell, wasapi)
        # `:expectred` NA BATERIA: um controlo que APANHA os mutantes sai 1, e 0
        # quando nao apanha -- a mesma polaridade dos outros `red-as-expected-*`.
        return 1 if ok else 0
    results = run(worker, shell, wasapi, verbose=False)
    ok = report(results)
    print('VERDICT: %s arms=%d fail=%d'
          % ('GREEN' if ok else 'RED', len(results),
             sum(1 for _, passed, _ in results if not passed)))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
