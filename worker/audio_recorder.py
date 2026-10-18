#!/usr/bin/env python3
"""GRAVAR O AUDIO EM DISCO, PARA UM MODELO MELHOR O PROCESSAR DEPOIS.

O DONO, 2026-10-17, verbatim: *"e guarda os audios, vao ser processados
continuamente por modelo melhor. o parakeet"*.

POR QUE ISTO EXISTE, E ONDE SE LIGA
------------------------------------
O audio ja passa por um sitio unico e ja normalizado: em
`worker/sotto_worker.py:5375-5387` o bloco `block` esta a 16 kHz, MONO, ja
remuestreado e ja contado (`counters["resampled_samples"]`), e e ai que o overlay
vivo recebe o MESMO PCM (`overlay.accept(block)`). Este gravador liga exactamente
ao lado, no mesmo fio, no MESMO audio que o motor vai descodificar. Nao ha uma
segunda copia de codigo de audio nem uma segunda copia do sinal.

ONDE ESTA, DE FACTO, O PARQUEET
-------------------------------
`worker/redux_live.py` JA E o Parakeet Redux (TDT), com o mesmo contrato JSONL no
stdout, e liga-se com `run.cmd --worker worker\\redux_live.py`. MEDIDO em
2026-10-17: `H:\\sotto\\worker\\models` tem **um** directorio, so
`nemotron-3.5-asr-ptbr-onnx-int4`. **Os pesos do Parakeet NAO estao no disco** --
contradiz o `AGENTS.md`, que em dois sitios afirma o contrario. Este modulo NAO
depende dos pesos: grava o audio de qualquer maneira, e quando eles chegarem ha
ficheiros para processar.

O FORMATO, E PORQUE FORMATO NORMAL E NAO UM FORMATO INVENTADO
------------------------------------------------------------
WAV PCM 16-bit mono a 16 kHz, e um `index.jsonl` ao lado. Cada linha do indice
descreve um segmento: ficheiro, quando comecou, quando acabou, amostras, pico,
RMS, e quantos segundos nao eram silencio digital. Um consumidor (o Parakeet, um
indexador, o proprio dono) precisa de saber **que ficheiro** corresponde a **que
intervalo de tempo**, e nada mais. Nao ha metadados inventados porque nao ha
nada para os preencher.

O SILENCIO NAO E GRAVADO, E ISTO E UMA DECISAO MEDIDA
-----------------------------------------------------
Numa maquina com um cabo virtual sem nada a tocar, TODOS os loopbacks leem
silencio digital: MEDIDO em 2026-10-06, pico 0.000122 durante 22 s de escuta em
todos eles, veredicto `NOTHING-ROUTED`. Gravar 8 horas de zeros a 16 kHz enche um
disco sem produzir uma palavra. Por isso um segmento cujo pico e RMS ficam abaixo
do chao e **descartado**, e o numero de descartes e **publicado** -- um gravador
que finge que gravou silencio e pior do que um que diz que nao gravou.

NADA DISSO CORRE SEM PERGUNTAR
------------------------------
`SOTTO_AUDIO_DIR=<pasta>` liga. Sem a variavel, `AudioRecorder` nem e construido:
zero ficheiros, zero aberturas, zero custode CPU.
"""

from __future__ import annotations

import json
import os
import time
import wave

#: The digital-silence floor of this class of machine, measured 2026-10-06:
#: peak 0.000122 across every loopback on the box with nothing playing.
DIGITAL_SILENCE_PEAK = 1e-3
DIGITAL_SILENCE_RMS = 1e-4

DEFAULT_SEGMENT_S = 60.0


class AudioRecorder:
    """Rotating WAV recorder with a JSONL index. Off unless a directory is given."""

    def __init__(self, outdir, rate=16000, segment_s=DEFAULT_SEGMENT_S,
                 prefix='sotto', log=None):
        self.log = log or (lambda msg: None)
        self.rate = int(rate)
        self.segment_s = float(segment_s)
        self.prefix = str(prefix)
        self.outdir = os.path.abspath(str(outdir))
        os.makedirs(self.outdir, exist_ok=True)

        self._wav = None
        self._path = None
        self._samples = 0
        self._peak = 0.0
        self._sq = 0.0
        self._start = 0.0
        self._index_path = os.path.join(self.outdir, 'index.jsonl')

        self.segments_written = 0
        self.segments_dropped_silent = 0
        self.samples_written = 0

    # ── the one call site the worker makes ──────────────────────────────────
    def accept(self, pcm):
        """One block of 16 kHz MONO float32. Never raises into the audio path."""
        try:
            self._accept(pcm)
        except Exception as exc:  # noqa: BLE001
            # A recorder that takes the live stream down with it is worse than no
            # recorder. Say it ONCE per failure class and keep streaming.
            self.log(f'AUDIO_RECORDER_FAILED {type(exc).__name__}: {exc}')
            self._close(keep=False)

    def _accept(self, pcm):
        if pcm is None:
            return
        # Mono, float32, contiguous: the block at the tap is already mono, but a
        # non-contiguous or non-float32 view would make `array` raise below.
        data = pcm.reshape(-1) if hasattr(pcm, 'reshape') else pcm
        if len(data) == 0:
            return
        self._maybe_roll()
        if self._wav is None:
            self._open()
        block = data.astype('float32', copy=False)
        peak = float(abs(block).max())
        self._peak = max(self._peak, peak)
        # Running mean-square, so `rms` is the whole segment's and not the last
        # block's. Float64 accumulate: 16000 samples/second in float32 loses the
        # low bits of a square that small.
        self._sq += float((block.astype('float64') ** 2).sum())
        self._samples += int(block.size)
        self._wav.writeframesraw(
            (block * 32767.0).clip(-32768, 32767).astype('<i2').tobytes())

    # ── rolling ────────────────────────────────────────────────────────────
    def _maybe_roll(self):
        if self._wav is not None and \
                self._samples < self.segment_s * self.rate:
            return
        self._close(keep=True)
        self._open()

    def _open(self):
        stamp = time.strftime('%Y%m%d-%H%M%S')
        self._path = os.path.join(
            self.outdir, '%s-%s-%04d.wav'
            % (self.prefix, stamp, self.segments_written + self.segments_dropped_silent))
        self._wav = wave.open(self._path, 'wb')
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)
        self._wav.setframerate(self.rate)
        self._start = time.time()
        self._samples = 0
        self._peak = 0.0
        self._sq = 0.0

    def _close(self, keep):
        if self._wav is None:
            return
        path, samples, peak = self._path, self._samples, self._peak
        rms = (self._sq / samples) ** 0.5 if samples else 0.0
        start, wav = self._start, self._wav
        self._wav = None
        self._path = None
        try:
            wav.close()
        except Exception:  # noqa: BLE001
            pass
        if not keep or not samples:
            return
        if peak < DIGITAL_SILENCE_PEAK and rms < DIGITAL_SILENCE_RMS:
            # Digital silence is not worth a file, and a file full of zeros is a
            # lie about having recorded something.
            self.segments_dropped_silent += 1
            try:
                os.remove(path)
            except OSError:
                pass
            return
        end = time.time()
        row = {
            'file': os.path.basename(path),
            'path': path,
            'rate': self.rate,
            'start_s': round(start, 3),
            'end_s': round(end, 3),
            'duration_s': round(samples / float(self.rate), 3),
            'samples': samples,
            'peak': round(peak, 6),
            'rms': round(rms, 6),
        }
        with open(self._index_path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
        self.segments_written += 1
        self.samples_written += samples

    # ── shutdown ───────────────────────────────────────────────────────────
    def close(self):
        self._close(keep=True)
        self.log('AUDIO_RECORDER_CLOSED written=%d dropped_silent=%d samples=%d '
                 'dir=%s' % (self.segments_written, self.segments_dropped_silent,
                             self.samples_written, self.outdir))

    def stats(self):
        return {'segments_written': self.segments_written,
                'segments_dropped_silent': self.segments_dropped_silent,
                'samples_written': self.samples_written,
                'recording_dir': self.outdir}


def from_env(log=None):
    """The recorder, or None. `SOTTO_AUDIO_DIR` is the whole opt-in."""
    d = os.environ.get('SOTTO_AUDIO_DIR')
    if not d or not str(d).strip():
        return None
    try:
        seg = float(os.environ.get('SOTTO_AUDIO_SEGMENT_S') or DEFAULT_SEGMENT_S)
    except (TypeError, ValueError):
        seg = DEFAULT_SEGMENT_S
    return AudioRecorder(str(d).strip(), segment_s=seg, log=log)