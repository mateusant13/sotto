#!/usr/bin/env python3
"""A PROVA DE FIM A FIM DA REGRA DO DONO, numa passage.

    "os audios sao guardados ate serem processados pelo modelo bom. depois,
     audios sao excluidos. os audios nao podem ser pesados. ... mas nao e o
     nemotron."

Cinco factos medidos, nesta ordem, sobre audio de fala REAL
(`_main/pt-br-sample.wav`, 15 s), passado pelo MESMO gravador e pelo MESMO
consumidor que o produto usa:

  E1  o gravador escreveu um segmento e ele estava em disco
  E2  o segmento e LEVE: FLAC, nao WAV, e lossless (erro 0,0 contra o PCM de
      origem)
  E3  o consumidor RECUSA o caminho do nemotron sem abrir nada
  E4  o Parakeet transcreveu o segmento e devolveu texto
  E5  o audio foi APAGADO e o que ficou foi o TEXTO em `results.jsonl`
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'worker'))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from audio_recorder import AudioRecorder  # noqa: E402
import audio_queue_consumer as consumer  # noqa: E402

SAMPLE = os.path.join(HERE, '_main', 'pt-br-sample.wav')
ONNX_DIR = os.path.join(HERE, 'worker', 'models', 'parakeet-redux-onnx-int4')


def main():
    if not os.path.exists(SAMPLE):
        print('FALTA a amostra de voz real: %s' % SAMPLE)
        return 2
    root = tempfile.mkdtemp(prefix='sotto-e2e-')
    queue = os.path.join(root, 'fila')
    results = []
    try:
        # ── E1 / E2: gravar voz real como o worker faria ────────────────────
        audio, rate = sf.read(SAMPLE, dtype='float32', always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        k = int(round(rate / 16000.0))          # 22 050 -> 16 000 por media
        usable = (audio.size // k) * k
        pcm16 = np.ascontiguousarray(
            audio[:usable].reshape(-1, k).mean(axis=1).astype(np.float32))

        rec = AudioRecorder(queue, segment_s=60.0, log=lambda m: None)
        step = 8960
        for i in range(0, pcm16.size, step):
            rec.accept(pcm16[i:i + step])
        rec.close()

        pending = rec.pending()
        results.append(('E1 o segmento foi escrito e esta em disco',
                        len(pending) == 1,
                        '%d segmento(s), %d B, %s'
                        % (len(pending),
                           pending[0]['bytes'] if pending else 0,
                           pending[0]['file'] if pending else '-')))
        if not pending:
            return report(results)
        row = pending[0]

        wav_bytes = len(pcm16) * 2
        back, back_sr = sf.read(row['path'], dtype='float32')
        results.append(('E2 o ficheiro e LEVE (FLAC) e o audio e o que o worker ouviu',
                        row['file'].endswith('.flac')
                        and row['bytes'] < wav_bytes
                        and back_sr == 16000
                        and abs(len(back) - len(pcm16)) <= 1
                        and float(np.abs(back[:len(pcm16)] - pcm16).max()) < 3e-4,
                        'FLAC %d B contra %d B de PCM16 = %.1f%% (%.1fx menor); '
                        'sr=%d amostras %d vs %d; erro maximo %.2e (a quantizacao '
                        'int16, e nao a compressao)'
                        % (row['bytes'], wav_bytes,
                           100.0 * row['bytes'] / wav_bytes,
                           wav_bytes / float(row['bytes']),
                           back_sr, len(back), len(pcm16),
                           float(np.abs(back[:len(pcm16)] - pcm16).max()))))

        # ── E3: a lei do modelo, antes de qualquer carga ───────────────────
        nemotron = os.path.join(HERE, 'worker', 'models',
                                'nemotron-3.5-asr-ptbr-onnx-int4')
        try:
            consumer.refuse_if_wrong_model(nemotron)
            refused = False
        except SystemExit:
            refused = True
        results.append(('E3 o consumidor RECUSA o nemotron sem abrir nada',
                        refused, 'nemotron recusado=%s' % refused))

        # ── E4 / E5: o bom modelo le, e o audio desaparece ─────────────────
        c = consumer.Consumer(queue, ONNX_DIR, log=lambda m: results.append(
            ('log', True, m)))
        text, state = c.transcribe(row['path'])
        results.append(('E4 o Parakeet transcreveu o segmento',
                        bool(text), 'state=%s texto=%r' % (state, text[:64])))

        deleted = rec.mark_processed(row, transcript=text,
                                     model='parakeet-redux-onnx', state=state)
        gone = not os.path.exists(row['path'])
        results.append(('E5 o audio foi APAGADO e o TEXTO ficou',
                        deleted and gone and os.path.exists(rec.results_path),
                        'ficheiro existe=%s, results.jsonl existe=%s'
                        % (os.path.exists(row['path']),
                           os.path.exists(rec.results_path))))
        with open(rec.results_path, encoding='utf-8') as fh:
            last = json.loads(fh.readlines()[-1])
        results.append(('E5b a linha final tem o texto e diz que o audio foi',
                        last.get('text') == text and last.get('audio_deleted')
                        and last.get('model') == 'parakeet-redux-onnx',
                        'model=%s state=%s audio_deleted=%s %d caracteres'
                        % (last.get('model'), last.get('state'),
                           last.get('audio_deleted'), len(last.get('text') or ''))))
        results.append(('E6 a fila ficou VAZIA depois de processar',
                        not rec.pending(), 'pending=%d' % len(rec.pending())))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return report(results)


def report(results):
    print()
    width = max(len(a) for a, _, _ in results if a != 'log')
    bad = 0
    for arm, good, detail in results:
        if arm == 'log':
            print('      . %s' % detail)
            continue
        print('  %-5s %-*s  %s' % ('GREEN' if good else 'RED', width, arm, detail))
        if not good:
            bad += 1
    print()
    print('VERDICT: %s' % ('GREEN -- guardado ate processar, apagado depois'
                           if not bad else 'RED -- %d de %d' % (bad, len(results))))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())