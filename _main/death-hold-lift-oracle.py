#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NO-BUG: a shell-ordered kill pins the death text over every warmup of the replacement until a caption arrives; a replacement that opens its own tap must lift it, and a real crash must still need a caption
"""A MORTE QUE A SHELL ORDENOU NAO PODE PRENDER O TEXTO PARA SEMPRE (medido 2026-11-28).

O DEFEITO. `_kill_and_restart` escreve `pending_error` (a shell e' a autora da
morte) e `_consume` HELDA todos os `WORKER_WARMUP_STATES` atras dele -- e so' uma
legenda levanta `pending_error`. Logo, um worker morto por SILENCIO num momento
em que as legendas locais sao recusadas (`ASR_PAINT_REFUSED owner=player`, porque
o YouTube e' o dono da faixa) deixava o texto de morte na tela para sempre.

  MEDIDO no log do dono (`_main/webview-run.log`, 2026-11-28):
  `02:10:38 BRIDGE_RESTART reason=silent`, e depois, um atras do outro,
  `02:10:42 BRIDGE_STATUS_HELD state="model-loading" behind="exit"`,
  `02:10:49 BRIDGE_STATUS_HELD state="boot" behind="exit"`,
  `02:10:49 BRIDGE_STATUS_HELD state="model-loaded" behind="exit"`,
  `02:10:52 BRIDGE_STATUS_HELD state="device" behind="exit"`,
  `02:10:55 BRIDGE_STATUS_HELD state="capture-started" behind="exit"`.
  O substituto ESTAVA a captar e tudo o que ele disse foi engolido.

A REGRA, e ela distingue os dois autores. Uma morte por `rc != 0` e' um veredicto
do WORKER e so' uma legenda a levanta (`_wait`). Uma morte ordenada pela PROPRIA
shell (silencio, timeout de carga) nao e' veredicto nenhum: o substituto a
publicar `capture-started` -- medido no filho que este bridge possui -- e' a prova
de que a troca vingou, e levanta o texto. A marca viaja no proprio dict
(`'lift': 'capture-started'`), por isso uma morte por `rc!=0` a seguir (que
reescreve o dict) perde-a.

AS TRES DIRECOES:

  * ARM `live-silencio-levanta` -- um FILHO REAL (subprocesso Python, o protocolo
    JSONL do worker, sem audio e sem modelo) e' morto pela shell por silencio e o
    substituto, a dizer `capture-started`, tem de produzir
    `BRIDGE_DEATH_LIFTED reason=capture-started` e `pending_error is None`. Exige
    tambem que o HELD tenha engatado ANTES (senao o braco mediria uma ausencia).
  * ARM `linha-do-filho-morto-nao-levanta` -- uma linha `capture-started` vinda do
    filho que morreu (nao e' `self.child`) nao pode levantar nada.
  * ARM `morte-por-rc-nao-levanta` -- um `pending_error` sem marca (o que o
    `_wait` escreve) NAO cai com `capture-started`; e' uma legenda que o levanta.

PORTEIRO `--neg-arm`: remove o ramo do lift (o codigo de ANTES) e exige que o
braco ao vivo fique VERMELHO (rc 1) -- uma guarda que nao sabe ficar vermelha nao
prova nada.

rc: 0 PASS, 1 FAIL (o lift nao acontece, ou o mutante nao morre), 3 CANNOT-MEASURE.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, "app", "webview", "sotto_webview.py")

#: O ramo do lift, exactamente como o produto o escreve. A mutacao apaga-o e
#: deixa o `elif` do HELD a seguir -- que e' o codigo de ANTES da cura.
LIFT_START = ("            elif (self.pending_error is not None\n"
              "                  and state == 'capture-started'")
LIFT_END = ("                self.pending_error = None\n"
            "            elif self.pending_error is not None and state in WORKER_WARMUP_STATES:")

#: O worker falso: fala o protocolo publico do worker (JSONL no stdout) e NAO
#: abre dispositivo nenhum, para que este oraculo nunca dispute audio com a app
#: do dono. Depois de `capture-started` fica calado de proposito -- e' a espera
#: que o cao de guarda de silencio existe para apanhar.
STUB = r'''import json, sys, time
def emit(**kw):
    sys.stdout.write(json.dumps(kw) + "\n")
    sys.stdout.flush()
for state in ("boot", "model-loading", "model-loaded", "capture-started"):
    emit(type="status", state=state)
while True:
    time.sleep(1.0)
'''


def _load(path, tag="hold"):
    sys.path.insert(0, os.path.join(REPO, "app", "webview"))
    spec = importlib.util.spec_from_file_location("sw_%s_%d" % (tag, os.getpid()), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_bridge(mod, stub_path, logs, statuses, silence_ms=1500):
    b = mod.WorkerBridge(
        command=sys.executable,
        worker_path=stub_path,
        log=lambda m: logs.append(m),
        on_status=lambda text, kind, info: statuses.append((text, kind)),
        silence_ms=silence_ms,
        load_silence_ms=2000,
        backoff_base=200,
        backoff_max=1000,
        no_audio_backoff_base=200,
        no_audio_backoff_max=1000,
    )
    return b


def _wait_for(pred, deadline_s):
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.1)
    return False


def arm_live_silence_lifts(mod, stub_path, deadline_s=40.0):
    """O FILHO REAL: silencio -> kill -> substituto abre o tap -> o texto cai."""
    logs, statuses = [], []
    b = _make_bridge(mod, stub_path, logs, statuses)
    ok = False
    try:
        b.start('start')
        killed = _wait_for(
            lambda: any('BRIDGE_KILL_NAMED' in l and 'why=silent' in l for l in logs),
            deadline_s)
        # A janela do lift e' curta de proposito: no positivo ele chega ~200 ms
        # depois do respawn, e no mutante esperar os 40 s inteiros so' paga uma
        # cadeia de restarts (medido: 15 restarts/60 HELD antes de o deadline
        # fechar a corrida). Um prazo por fase, nao um prazo para tudo.
        lifted = _wait_for(
            lambda: any('BRIDGE_DEATH_LIFTED reason=capture-started' in l for l in logs),
            min(deadline_s, 10.0))
        held = [l for l in logs if 'BRIDGE_STATUS_HELD' in l]
        after = [(t, k) for (t, k) in statuses
                 if 'has said nothing' not in t and 'stopped' not in t.lower()]
        ok = bool(killed and lifted and held and b.pending_error is None
                  and len(statuses) > 1 and after)
    finally:
        try:
            b.stop('oracle')
        except Exception:  # noqa: BLE001 -- um stop que rebenta nao muda o juizo
            pass
    print('  log: ' + ' | '.join(l for l in logs[-14:]))
    print('  statuses=%d held=%d pending_error=%r'
          % (len(statuses), len([l for l in logs if 'BRIDGE_STATUS_HELD' in l]),
             getattr(b, 'pending_error', 'MISSING')))
    if not ok:
        print('  FALHA: kill=%s lift=%s held=%d pending=%r'
              % (killed, lifted, len(held), getattr(b, 'pending_error', 'MISSING')))
    return ok


def _status_line(state):
    return json.dumps({'type': 'status', 'state': state})


def arm_stale_child_does_not_lift(mod, stub_path, logs=None):
    """Uma linha tardia do filho MORTO nao levanta a morte de quem esta' vivo."""
    logs = logs if logs is not None else []
    statuses = []
    b = _make_bridge(mod, stub_path, logs, statuses)
    b.pending_error = {'state': 'exit', 'text': 'worker killed by the shell (silent)',
                       'body': '', 'lift': 'capture-started'}
    dead = object()
    b.child = object()
    b._consume(_status_line('capture-started'), dead)
    still = b.pending_error is not None
    lifted_log = any('BRIDGE_DEATH_LIFTED' in l for l in logs)
    held_log = any('BRIDGE_STATUS_HELD' in l for l in logs)
    return bool(still and not lifted_log and held_log)


def arm_rc_death_keeps_the_hold(mod, stub_path):
    """O que o `_wait` escreve (sem marca) NAO cai com warmup; cai com legenda."""
    logs, statuses = [], []
    b = _make_bridge(mod, stub_path, logs, statuses)
    b.pending_error = {'state': 'exit', 'text': 'worker exit 1', 'body': ''}
    live = object()
    b.child = live
    b._consume(_status_line('capture-started'), live)
    held_after_warmup = b.pending_error is not None
    b.on_caption = lambda text, meta: None
    b._consume(json.dumps({'type': 'caption', 'text': 'ola'}), live)
    lifted_by_caption = b.pending_error is None
    return bool(held_after_warmup and lifted_by_caption)


def build_mutant(src):
    """Remove o ramo do lift; o HELD volta a engolir `capture-started`."""
    assert src.count(LIFT_START) == 1, 'ancora do lift ausente'
    start = src.index(LIFT_START)
    end = src.index(LIFT_END, start)
    head = src[:start]
    tail = src[end + len(LIFT_END) - len(
        "            elif self.pending_error is not None and state in WORKER_WARMUP_STATES:"):]
    return head + tail


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--neg-arm', action='store_true',
                    help='so o mutante: exige que o braco ao vivo fique vermelho')
    ap.add_argument('--deadline', type=float, default=40.0)
    ap.add_argument('--mutant-only', action='store_true')
    args = ap.parse_args(argv)

    src = open(SHELL, 'rb').read().decode('utf-8').replace('\r\n', '\n')

    tmp = tempfile.mkdtemp(prefix='hold-lift-', dir=os.environ.get('TMPDIR') or None)
    stub_path = os.path.join(tmp, 'stub_worker.py')
    with open(stub_path, 'wb') as fh:
        fh.write(STUB.encode('utf-8'))

    if args.neg_arm or args.mutant_only:
        mut_path = os.path.join(tmp, 'sotto_webview_mutant.py')
        with open(mut_path, 'wb') as fh:
            fh.write(build_mutant(src).encode('utf-8'))
        mod = _load(mut_path, 'mut')
        print('ARM mutante: o codigo de ANTES tem de ficar VERMELHO')
        red = arm_live_silence_lifts(mod, stub_path, args.deadline)
        if red:
            print('VERDICT: FAIL -- o mutante passou; o oraculo nao julga o lift')
            return 1
        print('NEG-ARM PASS: sem o lift o texto de morte fica preso (vermelho)')
        return 1 if args.neg_arm else 0

    mod = _load(SHELL, 'live')
    results = [
        ('live-silencio-levanta', arm_live_silence_lifts(mod, stub_path, args.deadline)),
        ('linha-do-filho-morto-nao-levanta', arm_stale_child_does_not_lift(mod, stub_path)),
        ('morte-por-rc-nao-levanta', arm_rc_death_keeps_the_hold(mod, stub_path)),
    ]
    fails = 0
    for name, ok in results:
        print('%s %s' % ('[PASS]' if ok else '[FAIL]', name))
        fails += 0 if ok else 1
    print('VERDICT: %s -- %d/%d arms' % ('PASS' if not fails else 'FAIL',
                                        len(results) - fails, len(results)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
