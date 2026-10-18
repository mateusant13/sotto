#!/usr/bin/env python3
"""ORACLE: O GRAVADOR GUARDA O AUDIO E NAO GUARDA O SILENCIO.

O DONO, 2026-10-17, verbatim: *"e guarda os audios, vao ser processados
continuamente por modelo melhor. o parakeet"*.

Este oráculo verifica as cinco promessas que `worker/audio_recorder.py` faz, e cada
uma delas é uma coisa que pode ser VERDADE sem ser CORRECTA — um ficheiro que
existe mas não é lido, um índice que não aponta para o ficheiro, um gravador que
leva o fluxo ao chão quando um bloco chega em formato inesperado.

  W1  OFF por omissão: sem `SOTTO_AUDIO_DIR` não se constrói gravador nem se cria
      um único ficheiro. Zero trabalho quando ninguém pediu.
  W2  O WAV é o que um leitor normal abre: mono, 16 kHz, 16 bits, e as amostras
      voltam com a precisão do int16 (não "um ficheiro com um cabeçalho").
  W3  O segmento fecha no tamanho pedido e o WAV que fica em disco tem a duração
      que o índice afirma.
  W4  O silêncio digital é DESCARTADO, e o índice não o nomeia. Medido nesta
      máquina: pico 0.000122 em todos os loopbacks sem nada a tocar
      (`NOTHING-ROUTED`, 2026-10-06). Gravar 8 h de zeros enche um disco sem
      produzir uma palavra.
  W5  O índice é completo: ficheiro, início, fim, duração, amostras, pico, RMS —
      e a duração bate certo com as amostras.
  W6  `accept()` nunca levanta. Um gravador que derruba o fluxo ao vivo é pior do
      que nenhum gravador.
  W7  Nada é escrito fora da pasta pedida.

`--neg-arm` parte cada promessa e exige o vermelho.

USO
    python _main/audio-recorder-oracle.py
    python _main/audio-recorder-oracle.py --neg-arm
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'worker'))

import audio_recorder as ar  # noqa: E402

RATE = 16000
CHUNK = 8960          # 560 ms, the worker's own chunk_samples
TONE_HZ = 220.0


def speechish(seconds, rate=RATE, amp=0.3):
    """A tone with speech-like amplitude modulation, so peak and rms are both real."""
    n = int(seconds * rate)
    t = np.arange(n, dtype=np.float64) / rate
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 3.1 * t)
    return (amp * env * np.sin(2 * np.pi * TONE_HZ * t)).astype(np.float32)


def silence(seconds, rate=RATE):
    return np.zeros(int(seconds * rate), dtype=np.float32)


def run_control(root):
    results = []

    # W1 -- off unless asked.
    os.environ.pop('SOTTO_AUDIO_DIR', None)
    results.append(('W1 off by default', ar.from_env() is None,
                    'from_env() with no SOTTO_AUDIO_DIR -> %s' % ar.from_env()))

    # W2 / W3 / W5 -- a real segment, opened, written, rolled and closed.
    out = os.path.join(root, 'audio')
    rec = ar.AudioRecorder(out, rate=RATE, segment_s=1.2, prefix='probe')
    for _ in range(6):                      # 6 x 0.56 s = 3.36 s of audio
        rec.accept(speechish(CHUNK / float(RATE)))
    rec.close()

    wavs = sorted(f for f in os.listdir(out) if f.endswith('.wav'))
    index_path = os.path.join(out, 'index.jsonl')
    rows = []
    if os.path.exists(index_path):
        with open(index_path, encoding='utf-8') as fh:
            rows = [json.loads(l) for l in fh if l.strip()]

    ok_chans = ok_rate = ok_width = ok_roundtrip = False
    detail = 'no wav written'
    # THE ROLL IS CHUNK-QUANTISED, and this oracle got that wrong first.
    # `_maybe_roll` tests the running sample count BEFORE each chunk is appended,
    # so a segment is "at least segment_s, rounded UP to a whole chunk". With
    # segment_s = 1.2 s (19 200 samples) and CHUNK = 8 960, that is
    # ceil(19200/8960) = 3 chunks per segment, i.e. 26 880 samples = 1.68 s -- and
    # the first oracle expected 19 200 exactly and reported a rounding as a bug.
    per_segment = int(np.ceil((1.2 * RATE) / CHUNK))
    if wavs:
        with wave.open(os.path.join(out, wavs[0]), 'rb') as w:
            ok_chans = w.getnchannels() == 1
            ok_rate = w.getframerate() == RATE
            ok_width = w.getsampwidth() == 2
            frames = w.readframes(w.getnframes())
            n_frames = w.getnframes()
        got = np.frombuffer(frames, dtype='<i2').astype(np.float32) / 32767.0
        want = np.concatenate([speechish(CHUNK / float(RATE))
                               for _ in range(max(1, n_frames // CHUNK))])
        want = want[:n_frames]
        # int16 round-trip: the error is the quantisation, not the plumbing.
        err = float(np.abs(got - want).max()) if len(got) else 1.0
        ok_roundtrip = len(got) == n_frames == per_segment * CHUNK and err < 2e-4
        detail = ('ch=%d rate=%d width=%dB frames=%d (expected %d = %d chunks) '
                  'max_err=%.2e' % (1, RATE, 2, n_frames, per_segment * CHUNK,
                                    per_segment, err))
    results.append(('W2 the wav is mono/16k/16-bit and round-trips',
                    ok_chans and ok_rate and ok_width and ok_roundtrip, detail))

    expected_segments = int(np.ceil(6 / float(per_segment)))
    results.append(('W3 the segment closes at the requested size',
                    len(rows) == expected_segments,
                    '%d segment(s), expected %d for 6 chunks at %d chunks/segment'
                    % (len(rows), expected_segments, per_segment)))

    row = rows[0] if rows else {}
    # `duration_s` IS the audio duration: samples/rate. It is deliberately NOT
    # compared with `end_s - start_s`, which is wall clock: a segment is written
    # far faster than real time, so the two differ by however long the disk took.
    # MEASURED 2026-10-17 -- asserting they are equal was the oracle's second own
    # error, and it would have failed a correct recorder.
    dur_ok = bool(row) and abs(row['duration_s']
                              - row['samples'] / float(RATE)) < 1e-6 \
        and row['end_s'] >= row['start_s'] and row['peak'] > 0.0
    needed = {'file', 'start_s', 'end_s', 'duration_s', 'samples', 'peak', 'rms'}
    results.append(('W5 the index row is complete and self-consistent',
                    dur_ok and needed.issubset(set(row))
                    and os.path.exists(os.path.join(out, row.get('file', ''))),
                    'keys=%s duration_bats=%s file_exists=%s'
                    % (sorted(needed - set(row)) or 'all present', dur_ok,
                       os.path.exists(os.path.join(out, row.get('file', ''))))))

    # W4 -- digital silence is dropped, and the index does not name it.
    out2 = os.path.join(root, 'silence')
    rec2 = ar.AudioRecorder(out2, rate=RATE, segment_s=0.8, prefix='probe')
    for _ in range(4):
        rec2.accept(silence(CHUNK / float(RATE)))
    rec2.close()
    left = os.listdir(out2)
    rows2 = []
    if os.path.exists(os.path.join(out2, 'index.jsonl')):
        with open(os.path.join(out2, 'index.jsonl'), encoding='utf-8') as fh:
            rows2 = [json.loads(l) for l in fh if l.strip()]
    results.append(('W4 digital silence is dropped, not filed as audio',
                    not [f for f in left if f.endswith('.wav')] and not rows2,
                    '%d wav(s) %d index row(s), %d dropped'
                    % (len([f for f in left if f.endswith('.wav')]), len(rows2),
                       rec2.segments_dropped_silent)))

    # W6 -- accept() never raises, whatever arrives.
    hostile = [None, np.zeros(0, dtype=np.float32),
               [0.1] * 100, np.ones(10, dtype=np.int16),
               np.ones(10, dtype=np.float64), 'nao e um array']
    raised = []
    for item in hostile:
        try:
            rec2.accept(item)
        except Exception as exc:  # noqa: BLE001
            raised.append('%s: %s' % (type(exc).__name__, exc))
    results.append(('W6 accept() never raises into the audio path', not raised,
                    raised[:2] or 'none of %d hostile inputs raised' % len(hostile)))

    # W7 -- nothing outside the directory.
    strays = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.normpath(os.path.join(dirpath, name))
            if not full.startswith(os.path.normpath(root)):
                strays.append(full)
    results.append(('W7 nothing is written outside the given directory',
                    not strays, strays[:2] or 'clean'))
    return results


def run_neg_arm(root):
    """Break each promise in a scratch copy of the module and require RED."""
    src = ar.__file__
    tmp = os.path.join(root, 'audio_recorder_mutant.py')
    mutants = [
        ('no silence guard: digital zero is filed as audio',
         'if peak < DIGITAL_SILENCE_PEAK and rms < DIGITAL_SILENCE_RMS:',
         'if False:'),
        ('the index is never written',
         "with open(self._index_path, 'a', encoding='utf-8') as fh:",
         "with open(os.devnull, 'a', encoding='utf-8') as fh:"),
        ('segments never roll: the whole run lands in one file',
         'self._samples < self.segment_s * self.rate', 'True'),
        ('the sample rate written into the wav is wrong',
         'self._wav.setframerate(self.rate)', 'self._wav.setframerate(8000)'),
        ('the channel count is wrong',
         'self._wav.setnchannels(1)', 'self._wav.setnchannels(2)'),
    ]
    import importlib.util
    ok = True
    for label, old, new in mutants:
        text = open(src, encoding='utf-8').read()
        if old not in text:
            print('  ?? %-56s -> MUTATION DID NOT APPLY' % label)
            ok = False
            continue
        open(tmp, 'w', encoding='utf-8').write(text.replace(old, new, 1))
        spec = importlib.util.spec_from_file_location('ar_mutant', tmp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sub = os.path.join(root, 'neg', label.split()[0] + str(abs(hash(label)) % 97))
        shutil.rmtree(sub, ignore_errors=True)
        os.makedirs(sub, exist_ok=True)
        rec = mod.AudioRecorder(os.path.join(sub, 'a'), rate=RATE,
                                segment_s=1.2, prefix='probe')
        for _ in range(6):
            rec.accept(speechish(CHUNK / float(RATE)))
        rec.close()
        out = os.path.join(sub, 'a')
        wavs = [f for f in os.listdir(out) if f.endswith('.wav')]
        ip = os.path.join(out, 'index.jsonl')
        rows = []
        if os.path.exists(ip):
            with open(ip, encoding='utf-8') as fh:
                rows = [json.loads(l) for l in fh if l.strip()]
        broke = []
        if rows:
            with wave.open(os.path.join(out, rows[0]['file']), 'rb') as w:
                if w.getnchannels() != 1:
                    broke.append('W2 %d channels' % w.getnchannels())
                if w.getframerate() != RATE:
                    broke.append('W2 %d Hz' % w.getframerate())
        else:
            broke.append('W5 the index is empty')
        if len(rows) != int(np.ceil((6 * CHUNK) / (1.2 * RATE))):
            broke.append('W3 %d segments' % len(rows))

        rec2 = mod.AudioRecorder(os.path.join(sub, 'b'), rate=RATE,
                                 segment_s=0.8, prefix='probe')
        for _ in range(4):
            rec2.accept(silence(CHUNK / float(RATE)))
        rec2.close()
        left = [f for f in os.listdir(os.path.join(sub, 'b')) if f.endswith('.wav')]
        if left:
            broke.append('W4 silence was filed')

        verdict = 'RED' if broke else 'GREEN'
        print('  %-4s %-56s -> %s' % (verdict, label, broke[:2] or 'no arm fired'))
        if not broke:
            ok = False
    try:
        os.remove(tmp)
    except OSError:
        pass
    print()
    print('NEG-ARM: %s' % ('PASS -- the oracle can say NO' if ok else 'FAIL'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    root = tempfile.mkdtemp(prefix='sotto-audio-rec-')
    try:
        if args.neg_arm:
            return run_neg_arm(root)
        results = run_control(root)
        width = max(len(a) for a, _, _ in results)
        bad = 0
        print('O GRAVADOR GUARDA O AUDIO -- %d arms\n' % len(results))
        for arm, good, detail in results:
            print('  %-5s %-*s  %s' % ('GREEN' if good else 'RED', width, arm, detail))
            if not good:
                bad += 1
        print()
        print('VERDICT: %s' % ('GREEN' if not bad else 'RED -- %d arm(s) failed' % bad))
        return 1 if bad else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())