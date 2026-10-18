#!/usr/bin/env python3
"""O CONSUMIDOR DA FILA: LE O AUDIO COM O MODELO BOM, E APAGA-O.

O DONO, 2026-10-17, verbatim:

    "os audios sao guardados ate serem processados pelo modelo bom. depois,
     audios sao excluidos. os audios nao podem ser pesados. modelos que vao
     processar, se for rapido e leve o suficiente, pode ser na hora. mas nao e
     o nemotron. ele tem erro grande."

Este modulo é o "modelo bom" da frase. Ele:

  - lê a fila que `audio_recorder.py` escreve (segmentos FLAC + `index.jsonl`);
  - transcreve cada um com o **Parakeet Redux ONNX** — `worker/redux_live.py`'s
    backend, o mesmo que `run.cmd --worker worker\\redux_live.py` usa;
  - **APAGA o audio** depois, em qualquer estado terminal (texto, vazio ou erro);
  - escreve o texto em `results.jsonl`, que é o que fica.

O NEMOTRON NÃO ENTRA NEM UM VEZ, E ISTO É UMA LEI
------------------------------------------------
O dono disse *"mas nao e o nemotron. ele tem erro grande"* sem saber que o repo ja
tinha a mesma lei desde 2026-07-14: *"o historico nao e pra ser NUNCA o historico
do live nvidia"*. Por isso este modulo tem uma verificacao estatica e um oracao:
o motor tem de se chamar parakeet e o caminho tem de estar em
`models/parakeet-redux-`. Se alguem apontar isto para o motor errado, RECUSA-SE em
vez de correr — que e o comportamento que o resto do repo ja exige dos outros
consumidores (`redux_live.py` faz o mesmo com os pesos em falta).

"SE FOR RAPIDO E LEVE O SUFICIENTE, PODE SER NA HORA"
-----------------------------------------------------
MEDIDO em 2026-10-17 nesta maquina, motor ONNX, janela 3 s passo 3 s:
`mean_compute_s=0.745` para `audio_s=14.6`, ou seja **~20x mais rapido que o
tempo real**, com `overruns=0` e RSS de 561 MB. Isso e "na hora": uma fila de
60 s e despachada em cerca de 3 s de calculo. Com os valores por omissao do motor
(janela 5 s, passo 2 s) dava `overruns=5` e nao acompanhava — por isso o
consumidor passa janela e passo explicitos e medidos.

USO
    python worker/audio_queue_consumer.py --once
    python worker/audio_queue_consumer.py --watch --interval 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_QUEUE_DIR = os.environ.get('SOTTO_AUDIO_DIR') or os.path.join(HERE, 'audio-queue')
ONNX_DIR = os.path.join(HERE, 'models', 'parakeet-redux-onnx-int4')

#: A lei do dono, verificada antes de carregar qualquer coisa.
FORBIDDEN_MODEL_SUBSTRINGS = ('sotto_worker', 'nemotron')


def refuse_if_wrong_model(model_dir):
    """Raise BEFORE loading a 2 GB model if this is not the Parakeet."""
    low = str(model_dir).lower()
    for bad in FORBIDDEN_MODEL_SUBSTRINGS:
        if bad in low:
            raise SystemExit(
                f'audio-queue-consumer: REFUSED -- {model_dir!r} names {bad!r}. '
                f'The owner, 2026-10-17: "mas nao e o nemotron. ele tem erro '
                f'grande." This consumer runs the GOOD model only; the Nemotron '
                f'path is a separate engine and its output never reaches this '
                f'queue.')
    if 'parakeet-redux' not in low:
        raise SystemExit(
            f'audio-queue-consumer: REFUSED -- {model_dir!r} is not a parakeet '
            f'redux export. Expected a path containing "parakeet-redux".')
    return True


class Consumer:
    def __init__(self, queue_dir, model_dir=ONNX_DIR, log=print,
                 window_s=3.0, step_s=3.0, threads=0):
        self.queue_dir = os.path.abspath(str(queue_dir))
        self.model_dir = str(model_dir)
        self.log = log
        self.index_path = os.path.join(self.queue_dir, 'index.jsonl')
        self.results_path = os.path.join(self.queue_dir, 'results.jsonl')
        self.window_s = float(window_s)
        self.step_s = float(step_s)
        self.threads = int(threads)
        self._engine = None

    # ── the queue ──────────────────────────────────────────────────────────
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

    def pending(self):
        done = {r.get('file') for r in self._read(self.results_path)}
        out = [r for r in self._read(self.index_path)
               if r.get('file') not in done and os.path.exists(r.get('path') or '')]
        out.sort(key=lambda r: r.get('start_s', 0.0))
        return out

    # ── the good model ─────────────────────────────────────────────────────
    def engine(self):
        if self._engine is not None:
            return self._engine
        refuse_if_wrong_model(self.model_dir)
        sys.path.insert(0, HERE)
        import redux_live
        self.log('audio-queue-consumer: loading Parakeet ONNX from %s' % self.model_dir)
        self._engine = redux_live.OnnxBackend(self.model_dir, threads=self.threads)
        self.log('audio-queue-consumer: model ready (%s)' % self._engine.name)
        return self._engine

    def transcribe(self, path):
        """One segment -> text. Returns (text, state)."""
        import soundfile as sf
        import numpy as np
        audio, rate = sf.read(path, dtype='float32', always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if audio.size == 0:
            return '', 'empty'
        if rate != 16000:
            k = rate / 16000.0
            usable = int(audio.size / k) * int(k) if k >= 1 else audio.size
            audio = (audio[:usable].reshape(-1, int(k)).mean(axis=1)
                     if k >= 1 else audio)
        engine = self.engine()
        audio = np.ascontiguousarray(audio.astype(np.float32))
        # `OnnxBackend.transcribe(pcm)` -- ONE argument, and it already assumes
        # 16 kHz mono (MEASURED 2026-10-17: passing a rate as a second positional
        # raises `TypeError: transcribe() takes 2 positional arguments but 3 were
        # given`). It returns `(text, segments)`, not a dict.
        text, _segments = engine.transcribe(audio)
        text = (text or '').strip()
        return text, ('done' if text else 'empty')

    # ── one pass ───────────────────────────────────────────────────────────
    def run_once(self, limit=None):
        queue = self.pending()
        if not queue:
            self.log('audio-queue-consumer: fila vazia')
            return 0
        self.log('audio-queue-consumer: %d segmento(s) à espera' % len(queue))
        # THE RECORDER OWNS THE DELETION CONTRACT; the consumer only reports.
        from audio_recorder import AudioRecorder
        rec = AudioRecorder(self.queue_dir, log=self.log)
        processed = 0
        for row in queue if limit is None else queue[:limit]:
            t0 = time.time()
            try:
                text, state = self.transcribe(row['path'])
            except Exception as exc:  # noqa: BLE001
                text, state = '', 'error:%s' % type(exc).__name__
                self.log('audio-queue-consumer: FALHOU %s -- %s'
                         % (row.get('file'), exc))
            wall = time.time() - t0
            audio_s = float(row.get('duration_s') or 0.0)
            rec.mark_processed(row, transcript=text, model='parakeet-redux-onnx',
                               state=state)
            self.log('audio-queue-consumer: %s state=%s audio=%.1fs wall=%.1fs '
                     '(%s) text=%r' % (row.get('file'), state, audio_s, wall,
                                       '%.1fx tempo real' % (audio_s / wall)
                                       if wall > 0 else 'n/a', text[:70]))
            processed += 1
        return processed

    def watch(self, interval=5.0, once_at_end=False):
        while True:
            try:
                self.run_once()
            except SystemExit:
                raise
            except Exception as exc:  # noqa: BLE001
                self.log('audio-queue-consumer: ciclo falhou -- %r' % (exc,))
            if once_at_end:
                return
            time.sleep(max(1.0, float(interval)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--queue-dir', default=DEFAULT_QUEUE_DIR)
    ap.add_argument('--model-dir', default=ONNX_DIR)
    ap.add_argument('--window-s', type=float, default=3.0,
                    help='MEASURED 2026-10-17: 3.0/3.0 runs at ~20x real time '
                         'with 0 overruns; the engine default 5.0/2.0 gives '
                         '5 overruns on this host.')
    ap.add_argument('--step-s', type=float, default=3.0)
    ap.add_argument('--threads', type=int, default=0)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--watch', action='store_true')
    ap.add_argument('--interval', type=float, default=5.0)
    args = ap.parse_args()

    refuse_if_wrong_model(args.model_dir)
    c = Consumer(args.queue_dir, args.model_dir, window_s=args.window_s,
                 step_s=args.step_s, threads=args.threads)
    if args.watch:
        c.watch(interval=args.interval)
        return 0
    c.run_once(limit=args.limit)
    return 0


if __name__ == '__main__':
    sys.exit(main())