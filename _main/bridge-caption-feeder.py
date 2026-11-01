#!/usr/bin/env python3
"""TRAFEGO DE LEGENDA para a instancia de MEDICAO -- um worker falso, minimo.

PORQUE EXISTE. A aceitacao desta lane e' um NUMERO: `exec_js TIMEOUT` depois de
10 minutos de trafego de legenda tem de ser 0. O microfone desta maquina esta'
mudo (o log do dono diz `BRIDGE_STATUS_NOAUDIO state="silent-device"`), portanto
uma instancia real nao produz legenda nenhuma e mediria um sistema OCIOSO, nao o
que o dono usa.

Este ficheiro escreve SO' as duas formas de linha que `worker/sotto_worker.py`
escreve -- `{"type":"caption",...}` e `{"type":"status",...}`, mais o
`{"type":"meter",...}` que alimenta o canal de stats -- para que o caminho do
shell que ele exercita seja o de PRODUCAO, sem um unico `if` de teste do lado do
shell (`WorkerBridge._consume`, `on_worker_caption`, `_status`).

OS DOIS CANAIS QUE IMPORTAM, e sao diferentes de proposito:

  caption  -> `on_worker_caption` -> `emit_async` (nao espera) -- o canal que
              tem de continuar vivo durante um stall;
  status   -> `on_worker_status` -> `apply_panel_state` -> `send_status`
              (`emit`, SINCRONO) + o placeholder (`exec_js`, SINCRONO).

O status e' o canal que o log do dono mostra a estourar 10 s
(`exec_js TIMEOUT ... window.__sotto_emit("status", ...)`, 2026-11-01 10:35:05),
portanto ele e' emitido a um ritmo realista e nao uma vez so'.

AMBIENTE
  SOTTO_FEED_INTERVAL_MS  intervalo entre legendas (300)
  SOTTO_FEED_STATUS_S     intervalo entre status (4.0)
  SOTTO_FEED_METER_S      intervalo entre amostras de meter (1.0)
  SOTTO_FEED_DURATION_S   duracao total, 0 = ate' ser morto (0)
"""
from __future__ import annotations

import json
import os
import sys
import time

INTERVAL_S = max(0.02, float(os.environ.get('SOTTO_FEED_INTERVAL_MS') or 300) / 1000.0)
STATUS_S = float(os.environ.get('SOTTO_FEED_STATUS_S') or 4.0)
METER_S = float(os.environ.get('SOTTO_FEED_METER_S') or 1.0)
DURATION_S = float(os.environ.get('SOTTO_FEED_DURATION_S') or 0.0)

#: Frases plausiveis: o painel mede o comprimento delas e o commit e' por linha
#: fechada, portanto um texto curto nao exercita o caminho que o dono usa.
SENTENCES = (
    'isto e uma linha de legenda medida',
    'o worker falso escreve ao ritmo do painel',
    'cada linha e uma hipotese que fecha',
    'o canal de status e o que estoura dez segundos',
    'a legenda nao pode parar quando o status espera',
)


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def main():
    t0 = time.monotonic()
    emit({'type': 'status', 'state': 'capture-started', 'device': 'feeder'})
    n = 0
    cap_at = t0
    st_at = t0 + STATUS_S
    me_at = t0 + METER_S
    while True:
        now = time.monotonic()
        if DURATION_S and now - t0 >= DURATION_S:
            emit({'type': 'status', 'state': 'done', 'captions': n})
            return 0
        if now >= cap_at:
            n += 1
            line = {
                'type': 'caption',
                'text': '%s %d' % (SENTENCES[n % len(SENTENCES)], n),
                'start': round(now - t0, 2),
                'end': round(now - t0 + INTERVAL_S, 2),
            }
            # Uma em cada oito e' FECHADA: e' o limite que a politica de reload
            # espera (`_reload_policy.boundary(closed=True)`), portanto o caminho
            # do reload tambem corre sem o forcar.
            if n % 8 == 0:
                line['final'] = True
            emit(line)
            cap_at = now + INTERVAL_S
        if now >= st_at:
            emit({'type': 'status', 'state': 'capture-started',
                  'captions': n, 'device': 'feeder'})
            st_at = now + STATUS_S
        if now >= me_at:
            emit({'type': 'meter', 'peak': 0.01 + (n % 7) * 0.001,
                  'blocks': n % 5, 'childPid': os.getpid()})
            me_at = now + METER_S
        # O passo e' curto para que os dois relogios nao se atrasem um ao outro.
        time.sleep(min(INTERVAL_S, max(0.005, min(cap_at, st_at, me_at) - now)))


if __name__ == '__main__':
    try:
        sys.exit(main() or 0)
    except (BrokenPipeError, KeyboardInterrupt):
        sys.exit(0)
