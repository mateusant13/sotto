"""A cadeia COMPLETA do sidecar sobre audio REAL, sem modelo falso.

O que este instrumento fecha
----------------------------
A cadeia ja foi provada por partes, cada uma com o seu instrumento:

    captura WASAPI real ................ `worker/speaker_sidecar.py --capture-selftest`
    ponte -> worker ..................... `_main/_speaker-chain-live.py` (16/30 nomeadas)
    painel, 2 vozes -> 2 linhas ......... `_main/panel-two-voices-oracle.js`
    renumeracao das etiquetas ........... `_main/speaker-slots-oracle.py`

**Nenhuma** delas correu o `tick` de verdade, com o modelo de verdade, sobre audio
de verdade. Cada uma tinha um diarizador falso algures -- e um diarizador falso
e' ESTAVEL por construcao, que e' precisamente a propriedade que o defeito da
renumeracao ataca.

Este aqui empurra um WAV pela `RingBuffer` REAL, com a cadencia REAL, chama o
`tick` REAL com o `_load_sherpa_diarizer` REAL, e le o payload que foi
effectivamente publicado em disco -- o mesmo ficheiro que a ponte vai ler.

Nao dorme entre janelas: o tempo de parede e' irrelevante para o
`RingBuffer`, que so sabe quanto audio recebeu. Por isso o custo e' o do
modelo (~100 s de CPU), nao o do audio.

O que se mede
-------------
1. O payload tem `speaker_slots` e os `speaker` globais sao ESTAVEIS entre
   janelas: a MESMA pessoa nao pode trocar de slot.
2. Quantos slots distintos aparecem no fim -- que e' o numero de linhas que o
   painel faria para este audio.
3. A sequencia de slots e' reproduzivel: correr duas vezes da o mesmo.
"""
import argparse
import json
import os
import sys
import wave
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                    # noqa: E402

import speaker_sidecar as S           # noqa: E402


def read_wav(path):
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise SystemExit("FAIL: o WAV tem de ser 16-bit mono")
        raw = w.readframes(w.getnframes())
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0, \
            w.getframerate()


class Args(SimpleNamespace):
    pass


def run_once(audio_path, out_path, window_s, every_s, threshold, num_speakers,
             threads, use_slots):
    x, rate = read_wav(audio_path)
    if rate != S.DEFAULT_RATE:
        x = S.to_mono16k(x, rate, S.DEFAULT_RATE)
    buf = S.RingBuffer(rate=S.DEFAULT_RATE, window_s=window_s)
    slots = S.StableSpeakerSlots() if use_slots else None

    args = Args(seg_model=S.DEFAULT_SEG_MODEL, emb_model=S.DEFAULT_EMB_MODEL,
                threads=threads, num_speakers=num_speakers,
                threshold=threshold)
    diarize = S._make_live_diarizer(args)

    step = int(every_s * S.DEFAULT_RATE)
    win = int(window_s * S.DEFAULT_RATE)
    published = []
    t = 1_700_000_000.0            # um relogio fixo: a execucao tem de ser igual
    i = 0
    while i + step <= len(x):
        block = x[i:i + step]
        buf.push(block.tolist(), t)
        t += every_s
        i += step
        state = S.tick(buf, diarize, out_path, threshold=threshold,
                       num_speakers=num_speakers, slots=slots)
        if state.get("state") == "written" and os.path.isfile(out_path):
            with open(out_path, "r", encoding="utf-8") as fh:
                p = json.load(fh)
            published.append(p)
        yield {"state": state.get("state"), "n": state.get("n_segments"),
               "slots": sorted({s["speaker"] for s in p.get("segments", [])}),
               "n_slots_in_window": len(p.get("speaker_slots") or {}),
               "mapping": p.get("speaker_slots"),
               "created": p.get("speaker_slots_created"),
               "span": [round(min((s["start"] for s in p.get("segments", [])),
                                  default=0.0), 1),
                        round(max((s["end"] for s in p.get("segments", [])),
                                  default=0.0), 1)]}
    return published


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "_replay_payload.json"))
    ap.add_argument("--window-s", type=float, default=S.DEFAULT_WINDOW_S)
    ap.add_argument("--every-s", type=float, default=S.DEFAULT_EVERY_S)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--num-speakers", type=int, default=-1)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--no-slots", action="store_true")
    args = ap.parse_args(argv)

    print("audio %s   janela %.0f s  passo %.0f s  threshold %.2f  "
          "num_speakers %d  slots %s"
          % (args.audio, args.window_s, args.every_s, args.threshold,
             args.num_speakers, "OFF" if args.no_slots else "ON"))
    ticks = list(run_once(args.audio, args.out, args.window_s, args.every_s,
                          args.threshold, args.num_speakers, args.threads,
                          not args.no_slots))
    print("\n  %-4s %-9s %-5s %-28s %s" % ("#", "estado", "seg", "slots na janela",
                                           "mapa local->global"))
    for n, tk in enumerate(ticks):
        print("  %-4d %-9s %-5s %-28s %s"
              % (n, tk["state"], tk["n"], tk["slots"], tk["mapping"]))

    all_slots = sorted({s for tk in ticks for s in tk["slots"]})
    empties = [n for n, tk in enumerate(ticks) if tk["n"] == 0]
    print("\n  linhas que o painel faria com este audio: %d  (slots %s)"
          % (len(all_slots), all_slots))
    print("  janelas sem segmento: %s" % (empties or "nenhuma"))
    if args.no_slots:
        print("  (slots OFF: estes numeros sao os de ANTES da correccao)")
    return 0


if __name__ == "__main__":
    sys.exit(main())