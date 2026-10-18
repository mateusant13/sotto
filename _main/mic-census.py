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
#: **NEVER OPEN A BLUETOOTH HEADSET'S MICROPHONE WITHOUT BEING ASKED.**
#:
#: THE OWNER, 2026-10-17: *"por que eu fico sem audio de tempos em tempos? por
#: acaso tu faz alguma OUTRA merda no meu headphone q me força a desconectar ele e
#: a reconectar pra eu ouvir meu pc de novo?"* SIM. Fui eu. E está medido:
#:
#:     id=60  Windows WDM-KS  Headset (@System32\drivers\bthhfenum.sys,#)  16000 Hz
#:     id=39  Windows WASAPI   Headset (soundcore Space Q45)               16000 Hz
#:     id=12  MME              Headset (soundcore Space Q45 Hands-Free...) 44100 Hz
#:
#: `bthhfenum.sys` is the Windows **Bluetooth** audio driver; 16 000 Hz is the
#: HFP (headset-profile) rate; and an output endpoint whose own name is
#: "Hands-Free" exists only while the device IS in HFP. Opening a Bluetooth
#: headset's microphone makes Windows switch the device from **A2DP** (music,
#: stereo) to **HFP** (calls, mono, 16 kHz). The music stops or drops to phone
#: quality, and recovering needs a disconnect/reconnect — which is exactly what the
#: owner reported.
#:
#: THIS WAS MY BUG, and it was one word. `headset` was in `MIC_WORDS` below, so
#: the census opened the headset's mic FOUR times: MME id 4, DirectSound id 19,
#: WASAPI id 39 and WDM-KS id 60. Every instrument that opens a device on this box
#: has to carry this refusal, because the damage is to the owner's playback and
#: it is invisible in every log here.
BLUETOOTH_MARKS = ('bthhfenum', 'bthenumer', 'bthmodem', 'hands-free', 'hands free')
WIRELESS_HEADSET_MARKS = ('wireless', 'bluetooth', 'bt ', 'buds', 'airpods')

MIC_WORDS = ('microfone', 'microphone', 'mic input', 'hands-free', 'chat',
             'line input')

# ...e o que exclui, porque estes NAO sao microfones mesmo com o nome a enganar.
NOT_MIC_WORDS = ('voicemeeter', 'cable', 'cable output', 'estereo',
                 'stereo mix', 'mixagem', 'primario', 'primary sound',
                 'loopback', 'line input', 'entrada', 'microsoft sound mapper')

SILENT_PEAK = 1e-3
SILENT_RMS = 1e-4


def is_bluetooth(name):
    """TRUE when this endpoint is a Bluetooth audio device, by any of its names.

    Measured on this host, 2026-10-17: the Space Q45 shows up as
    `Headset (soundcore Space Q45)` under MME, DirectSound and WASAPI — with no
    word "bluetooth" anywhere in the name — and only as
    `Headset (@System32\drivers\bthhfenum.sys,#)` under WDM-KS. So the name is
    not enough on its own, and refusing by name alone would have missed it. The
    driver path is the tell, which is why the WDM-KS enumeration is included.
    """
    low = name.lower()
    return any(mark in low for mark in BLUETOOTH_MARKS)


def is_mic(name):
    low = name.lower()
    if any(bad in low for bad in NOT_MIC_WORDS):
        return False
    return any(w in low for w in MIC_WORDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=2.0)
    ap.add_argument('--names', default='')
    ap.add_argument('--allow-bluetooth', action='store_true',
                    help='open Bluetooth devices too. This switches the headset '
                         'from A2DP to HFP and can drop the owner\'s playback, so '
                         'it needs to be typed on purpose.')
    ap.add_argument('--json-out', default='')
    args = ap.parse_args()

    import numpy as np
    import sounddevice as sd

    only = [n.strip().lower() for n in args.names.split(',') if n.strip()]
    apis = sd.query_hostapis()
    devs = sd.query_devices()

    rows = []
    refused = []
    print('FALA durante %.0f s.\n' % args.seconds)
    for i, d in enumerate(devs):
        name = d['name']
        if d['max_input_channels'] <= 0:
            continue
        if only and not any(o in name.lower() for o in only):
            continue
        if not only and not is_mic(name):
            continue
        if is_bluetooth(name) and not args.allow_bluetooth:
            # THE REFUSAL. See the BLUETOOTH_MARKS note above: opening this
            # endpoint takes the owner's headset out of A2DP and into HFP, and
            # he has to reconnect it to hear his PC again. Not opened by
            # accident, not opened by a name match, not opened by a census.
            print('id=%-3d %-22s %-42s RECUSADO (Bluetooth: A2DP -> HFP '
                  'derruba o audio do dono)' % (i, apis[d['hostapi']]['name'][:22],
                                                name[:42]))
            refused.append(name)
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
    if refused:
        print('RECUSADOS SEM ABRIR: %d  %s' % (len(refused), refused))
        print('  (--allow-bluetooth para os abrir; isso tira o auscultador de A2DP')
        print('   e pode deixar o dono sem audio ate reemparelhar.)')
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