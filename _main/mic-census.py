#!/usr/bin/env python3
"""MEDIR OS MICROFONES DESTA MAQUINA. (2026-10-17)

POR QUE ISTO EXISTE. O dono, verbatim: *"faz pegar o meu mic tambem"*. A escada de
captura do worker (`worker/sotto_worker.py`, `device_candidates`) oferece: rung C
(nome explicito), rung P (um pid), rung A (loopback WASAPI de cada endpoint de
render) e rung B (entradas cujo NOME casa com cable/virtual/stereo mix/voicemeeter/
...). Nenhum desses alcanca um microfone: a lista de nomes e feita de cabos
virtuais, nao de microfones. MEDIDO em `_main/device-names.log` desta mesma
maquina: existem **29 entradas**, das quais **6 sao microfones** e **nenhuma** casa
com a heuristica.

A ESCADA ESTA CORRECTA E ISTO NAO E UM BUG DELA -- e a razao pela qual o microfone
precisa de uma rung nova e nao de um nome novo na lista de cabos.

O QUE ESTE SCRIPT MEDE, POR DISPOSITIVO, EM CADA HOST API:
    peak        o maior |amostra| do buffer
    rms         a raiz da media quadrada
    blocks      quantos blocos chegaram
    digital?    peak < 1e-3 E rms < 1e-4  -> silencio digital (a linha de base
                desta maquina, medida em 2026-10-06: 0.000122)

O QUE O DONO TEM DE FAZER: falar durante ~20 s. Sem ruido humano um microfone
ligado tem um chao de ruido, e um microfone desligado tem exactamente zero -- e
esses dois numeros é que separam "ligado" de "nao ligado".

USO
    python _main/mic-census.py            # 2.0 s por dispositivo
    python _main/mic-census.py --seconds 6
    python _main/mic-census.py --names Quadcast,Broadcast    # so estes
"""

from __future__ import annotations

import argparse
import json
import sys
import time

# O que conta como microfone. MEDIDO contra as 29 entradas desta maquina:
#   entradas que NAO sao: 'Mapeador de som da Microsoft - Input',
#   'VoiceMeeter Output' x3, 'CABLE Output' x3, 'Driver de captura de som
#   primario', 'Mixagem estereo (Realtek ... Stereo input)',
#   'Entrada (Realtek HD Audio Line input)'.
MIC_WORDS = ('microfone', 'microphone', 'mic input', 'headset', 'headphone',
             'hands-free', 'chat', 'line input')

# ...e o que exclui, porque estes NAO sao microfones mesmo com o nome a enganar.
NOT_MIC_WORDS = ('voicemeeter', 'cable', 'cable output', 'estereo',
                 'stereo mix', 'mixagem', 'primario', 'primary sound',
                 'loopback', 'line input', 'entrada', 'microsoft sound mapper')

SILENT_PEAK = 1e-3
SILENT_RMS = 1e-4


def is_mic(name):
    low = name.lower()
    if any(bad in low for bad in NOT_MIC_WORDS):
        return False
    return any(w in low for w in MIC_WORDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=2.0)
    ap.add_argument('--names', default='')
    ap.add_argument('--json-out', default='')
    args = ap.parse_args()

    import numpy as np
    import sounddevice as sd

    only = [n.strip().lower() for n in args.names.split(',') if n.strip()]
    apis = sd.query_hostapis()
    devs = sd.query_devices()

    rows = []
    print('FALA durante %.0f s.\n' % args.seconds)
    for i, d in enumerate(devs):
        name = d['name']
        if d['max_input_channels'] <= 0:
            continue
        if only and not any(o in name.lower() for o in only):
            continue
        if not only and not is_mic(name):
            continue
        rate = int(round(d['default_samplerate']))
        ch = min(2, int(d['max_input_channels']))
        rec = []
        try:
            with sd.InputStream(device=i, channels=ch, samplerate=rate,
                                dtype='float32') as st:
                t0 = time.time()
                while time.time() - t0 < args.seconds:
                    data, _ = st.read(int(rate * 0.1))
                    rec.append(np.abs(data).max())
                    rec[-1] = max(rec[-1], float(np.sqrt((data.astype('float64') ** 2).mean())))
            peak = float(max(rec[0::2])) if rec else 0.0
            rms = float(max(rec[1::2])) if rec else 0.0
            err = ''
        except Exception as exc:  # noqa: BLE001
            peak = rms = 0.0
            err = '%s: %s' % (type(exc).__name__, exc)
        silent = (peak < SILENT_PEAK and rms < SILENT_RMS)
        rows.append({
            'id': i, 'name': name, 'api': apis[d['hostapi']]['name'],
            'channels': ch, 'rate': rate,
            'peak': peak, 'rms': rms,
            'digital_silence': bool(silent), 'error': err,
        })
        print('id=%-3d %-22s ch=%d %6d Hz  peak=%.6f rms=%.6f  %s%s'
              % (i, apis[d['hostapi']]['name'][:22], ch, rate, peak, rms,
                 'SILENCIO DIGITAL' if silent else 'SINAL',
                 ('  ' + err) if err else ''))
        print('        %r' % name)

    print()
    talking = [r for r in rows if not r['digital_silence'] and not r['error']]
    print('RESUMO: %d candidato(s) a microfone, %d com sinal.'
          % (len(rows), len(talking)))
    if talking:
        print('O PRIMEIRO COM SINAL E O QUE A ESCADA DEVERIA PEGAR:')
        for r in talking[:6]:
            print('  id=%-3d %-22s %r' % (r['id'], r['api'], r['name']))
    else:
        print('Nenhum microfone entregou sinal. OU nao havia ruido humano durante a')
        print('medida, OU o microfone que o dono quer nao e um destes. Nao se inventa:')
        print('pergunta-se. A linha de base do silencio digital nesta maquina e')
        print('peak 0.000122 (medido 2026-10-06), e o limiar aqui e %.0e.' % SILENT_PEAK)

    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=2)
        print('receita: %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())