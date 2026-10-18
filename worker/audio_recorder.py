#!/usr/bin/env python3
"""GRAVAR O AUDIO, ESPERAR QUE O MODELO BOM O LEIA, E APAGAR.

O DONO, 2026-10-17, verbatim — esta é a ESPECIFICAÇÃO, não um pedido:

    "os audios sao guardados ate serem processados pelo modelo bom. depois,
     audios sao excluidos. os audios nao podem ser pesados. modelos que vao
     processar, se for rapido e leve o suficiente, pode ser na hora. mas nao e
     o nemotron. ele tem erro grande."

Traduzido em quatro regras que este modulo cumpre:

  1. **GUARDADO ATÉ SER PROCESSADO.** O ficheiro existe porque há um consumidor
     aribitrado. Não é um arquivo de gravação: é uma fila.
  2. **DEPOIS, EXCLUÍDO.** `mark_processed()` apaga o áudio e escreve a
     transcrição. O que fica é o TEXTO, que é o produto; o áudio era só o meio.
  3. **NÃO PODE SER PESADO.** FLAC em vez de WAV, e é **lossless**: medido em
     2026-10-17 sobre `_main/pt-br-sample.wav`, 2,2× menor com erro máximo
     **0,0** (`np.array_equal` True). Perder qualidade ANTES do modelo bom ver o
     audio seria exactamente o erro que o dono肯定不会 quer — e a compressão
     com perdas antes do melhor modelo é uma troca que se faz ao contrário.
  4. **NUNCA O NEMOTRON.** Nada aqui chama o motor principal. O consumidor é o
     Parakeet; e esta lei já é do repo desde 2026-07-14 ("o histórico nunca deve
     ser o do live nvidia"). O dono repetiu-a hoje sem saber que já estava lá.

ONDE SE LIGA
------------
Em `worker/sotto_worker.py:5388-5399`, ao lado de `overlay.accept(block)`: o
bloco já está a 16 kHz, mono, remuestreado e contado, e é o MESMO PCM que o
decodificador vai ver. O que fica em disco é o que o modelo ouviu, não uma
segunda captura da mesma sala que deriva.

INERTES SEM `SOTTO_AUDIO_DIR`
-----------------------------
Sem a variável, `from_env()` devolve None: nada é construído, nenhum ficheiro é
aberto, e o caminho ao vivo paga zero. `accept()` nunca levanta, e uma falha ao
gravar nunca derruba o fluxo de transcrição.
"""

from __future__ import annotations

import json
import os
import time

#: The digital-silence floor of this class of machine, measured 2026-10-06: peak
#: 0.000122 across every loopback with nothing playing.
DIGITAL_SILENCE_PEAK = 1e-3
DIGITAL_SILENCE_RMS = 1e-4

DEFAULT_SEGMENT_S = 60.0

#: How much UNPROCESSED audio may sit on disk before the oldest is given up.
#: Not a detail: a consumer that stops (no weights, no model, a crash) turns a
#: queue into a disk filler, and the owner's machine is the one that dies. When
#: the ceiling is reached the oldest unprocessed segment is DELETED and counted,
#: because a bounded loss that is reported beats an unbounded one that is not.
DEFAULT_MAX_PENDING_BYTES = 512 * 1024 * 1024


def _soundfile():
    """soundfile, or None. FLAC is a preference, never a requirement."""
    try:
        import soundfile
        return soundfile
    except Exception:  # noqa: BLE001
        return None


class AudioRecorder:
    """A queue of audio segments waiting for a model, with a bounded backlog."""

    def __init__(self, outdir, rate=16000, segment_s=DEFAULT_SEGMENT_S,
                 prefix='sotto', log=None, max_pending_bytes=DEFAULT_MAX_PENDING_BYTES):
        self.log = log or (lambda msg: None)
        self.rate = int(rate)
        self.segment_s = float(segment_s)
        self.prefix = str(prefix)
        self.max_pending_bytes = int(max_pending_bytes)
        self.outdir = os.path.abspath(str(outdir))
        os.makedirs(self.outdir, exist_ok=True)

        self._sf = _soundfile()
        self._path = None
        self._pending_pcm = []
        self._pending_n = 0
        self._peak = 0.0
        self._sq = 0.0
        self._start = 0.0
        self._seq = 0

        self.index_path = os.path.join(self.outdir, 'index.jsonl')
        self.results_path = os.path.join(self.outdir, 'results.jsonl')

        self.segments_written = 0
        self.segments_dropped_silent = 0
        self.segments_dropped_over_cap = 0
        self.samples_written = 0
        self.subtype = 'FLAC' if self._sf is not None else 'WAV'

    # ── the one call site the worker makes ──────────────────────────────────
    def accept(self, pcm):
        """One block of 16 kHz MONO float32. Never raises into the audio path."""
        try:
            self._accept(pcm)
        except Exception as exc:  # noqa: BLE001
            self.log(f'AUDIO_RECORDER_FAILED {type(exc).__name__}: {exc}')
            self._flush(keep=False)

    def _accept(self, pcm):
        if pcm is None:
            return
        data = pcm.reshape(-1) if hasattr(pcm, 'reshape') else pcm
        if len(data) == 0:
            return
        if self._pending_n and self._pending_n + len(data) > self.segment_s * self.rate:
            self._flush(keep=True)
        block = data.astype('float32', copy=False)
        self._pending_pcm.append(block)
        self._pending_n += int(block.size)
        self._peak = max(self._peak, float(abs(block).max()))
        # float64 accumulate: 16 000 amostras/segundo em float32 perde os bits
        # baixos de um quadrado pequeno.
        self._sq += float((block.astype('float64') ** 2).sum())

    # ── rolling ────────────────────────────────────────────────────────────
    def _flush(self, keep):
        if not self._pending_n:
            self._pending_pcm = []
            self._peak = 0.0
            self._sq = 0.0
            return
        samples, peak = self._pending_n, self._peak
        rms = (self._sq / samples) ** 0.5 if samples else 0.0
        audio = None
        if samples:
            audio = self._pending_pcm[0] if len(self._pending_pcm) == 1 else \
                __import__('numpy').concatenate(self._pending_pcm)
        self._pending_pcm = []
        self._pending_n = 0
        self._peak = 0.0
        self._sq = 0.0
        if not keep or samples == 0:
            return

        # Digital silence is not worth a file, and a file full of zeros is a lie
        # about having recorded something. Measured floor: see above.
        if peak < DIGITAL_SILENCE_PEAK and rms < DIGITAL_SILENCE_RMS:
            self.segments_dropped_silent += 1
            return

        self._seq += 1
        path = os.path.join(self.outdir, '%s-%s-%04d.flac'
                            % (self.prefix, time.strftime('%Y%m%d-%H%M%S'), self._seq))
        try:
            self._write(path, audio)
        except Exception as exc:  # noqa: BLE001
            self.log(f'AUDIO_RECORDER_WRITE_FAILED {type(exc).__name__}: {exc} '
                     f'path={path}')
            return
        end = time.time()
        row = {
            'file': os.path.basename(path),
            'path': path,
            'rate': self.rate,
            'format': self.subtype,
            'start_s': round(self._start, 3),
            'end_s': round(end, 3),
            'duration_s': round(samples / float(self.rate), 3),
            'samples': samples,
            'peak': round(peak, 6),
            'rms': round(rms, 6),
            'bytes': os.path.getsize(path),
        }
        self._append(self.index_path, row)
        self._start = end
        self.segments_written += 1
        self.samples_written += samples
        self._enforce_cap()

    def _write(self, path, audio):
        if self._sf is not None:
            try:
                self._sf.write(path, audio, self.rate, format='FLAC',
                               subtype='PCM_16')
                return
            except Exception as exc:  # noqa: BLE001
                self.log(f'AUDIO_RECORDER_FLAC_FAILED {type(exc).__name__}: {exc} '
                         f'-- falling back to WAV')
                self.subtype = 'WAV'
                path = os.path.splitext(path)[0] + '.wav'
        import wave
        wav = wave.open(path, 'wb')
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(self.rate)
        wav.writeframesraw((audio * 32767.0).clip(-32768, 32767).astype('<i2').tobytes())
        wav.close()
        self._path = path

    # ── the retention contract ─────────────────────────────────────────────
    def pending(self):
        """Every index row whose audio is still on disk, oldest first."""
        rows = self._read(self.index_path)
        done = {r.get('file') for r in self._read(self.results_path)}
        out = []
        for row in rows:
            if row.get('file') in done:
                continue
            if not os.path.exists(row.get('path') or ''):
                continue
            out.append(row)
        out.sort(key=lambda r: r.get('start_s', 0.0))
        return out

    def pending_bytes(self):
        total = 0
        for row in self.pending():
            try:
                total += int(row.get('bytes') or os.path.getsize(row['path']))
            except OSError:
                pass
        return total

    def mark_processed(self, row, transcript='', model='', state='done'):
        """THE OWNER'S RULE 2: the audio is DELETED once a model has read it.

        The transcript is what remains, in `results.jsonl`. The audio was only
        ever the means.

        Deleted on ANY terminal state — a transcription, an empty one, or an
        error — because the alternative is a file that no model will ever read
        again, and the owner's disk is what pays for it.
        """
        path = row.get('path')
        removed = False
        try:
            if path and os.path.exists(path):
                os.remove(path)
                removed = True
        except OSError as exc:
            self.log(f'AUDIO_DELETE_FAILED {path}: {exc}')
        out = dict(row)
        out.update({'state': state, 'model': model, 'text': transcript,
                    'audio_deleted': removed,
                    'processed_at_s': round(time.time(), 3)})
        self._append(self.results_path, out)
        if removed:
            self.log('AUDIO_DELETED_AFTER_PROCESSING file=%s bytes=%d state=%s '
                     'model=%s' % (row.get('file'), int(row.get('bytes') or 0),
                                   state, model or '-'))
        return removed

    def _enforce_cap(self):
        """Bounded backlog. A stalled consumer must not fill the disk."""
        while self.pending_bytes() > self.max_pending_bytes:
            queue = self.pending()
            if not queue:
                return
            oldest = queue[0]
            try:
                if oldest.get('path') and os.path.exists(oldest['path']):
                    os.remove(oldest['path'])
            except OSError:
                return
            self.segments_dropped_over_cap += 1
            out = dict(oldest)
            out.update({'state': 'dropped-over-cap', 'text': '',
                        'dropped_at_s': round(time.time(), 3)})
            self._append(self.results_path, out)
            self.log('AUDIO_DROPPED_OVER_CAP file=%s bytes=%d cap=%d '
                     '(a fila nao esta a ser processada)' % (
                         oldest.get('file'), int(oldest.get('bytes') or 0),
                         self.max_pending_bytes))

    @staticmethod
    def _read(path):
        rows = []
        try:
            with open(path, encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except ValueError:
                            pass
        except OSError:
            pass
        return rows

    @staticmethod
    def _append(path, row):
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')

    # ── shutdown ───────────────────────────────────────────────────────────
    def close(self):
        self._flush(keep=True)
        self.log('AUDIO_RECORDER_CLOSED written=%d silent_dropped=%d over_cap=%d '
                 'pending_bytes=%d dir=%s'
                 % (self.segments_written, self.segments_dropped_silent,
                    self.segments_dropped_over_cap, self.pending_bytes(),
                    self.outdir))

    def stats(self):
        return {'segments_written': self.segments_written,
                'segments_dropped_silent': self.segments_dropped_silent,
                'segments_dropped_over_cap': self.segments_dropped_over_cap,
                'pending_bytes': self.pending_bytes(),
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
    try:
        cap = int(os.environ.get('SOTTO_AUDIO_MAX_PENDING_MB') or 0) * 1024 * 1024
    except (TypeError, ValueError):
        cap = DEFAULT_MAX_PENDING_BYTES
    return AudioRecorder(str(d).strip(), segment_s=seg, log=log,
                         max_pending_bytes=cap or DEFAULT_MAX_PENDING_BYTES)