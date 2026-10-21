"""Varrimento de `threshold` do FastClustering, com o modelo carregado UMA vez.

Porquê
------
MEDIDO: o sidecar corre `FastClusteringConfig(num_clusters=-1, threshold=0.9)`.
A assinatura da biblioteca, lida do modulo instalado
(`sherpa_onnx.lib._sherpa_onnx.FastClusteringConfig.__init__.__doc__`), e

    __init__(self, num_clusters: int = -1, threshold: float = 0.5)

Ou seja: **0,5 e' o omissao da biblioteca e 0,9 e' 1,8x mais estrito**. Com 0,9
sobre audio de call gravado (60 s) a resposta foi 2 vozes -- correcto. Sobre os
180 s seguintes, em que a fala e' esparsa (21,2 s em 180 s), a MESMA config
devolveu **6 vozes para 2 pessoas**. Cada cluster vira uma `source` diferente no
painel, portanto 6 clusters sao 6 linhas para 2 pessoas -- exactamente o que a
`source` por vozexists para impedir.

Este instrumento nao adivinha o valor certo: mede quantas vozes cada threshold
produz, nos dois audios, e diz qual se aproxima da verdade-terra.

O que conta como verdade-terra
-------------------------------
- `call.wav` (60 s, 79 % de fala): o dono estava numa call de duas pessoas ->
  **2 vozes**.
- `call180.wav` (180 s, 12 % de fala): mesma call, mais tarde -> **2 vozes**,
  muito pouca fala.

Cada audio e' processado com `num_clusters=-1` (auto), que e' o que o produto
usa hoje. O modo auto e' o que decide.
"""
import argparse
import os
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if os.path.join(ROOT, "worker") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                    # noqa: E402
import sherpa_onnx                    # noqa: E402

import speaker_sidecar as S           # noqa: E402


def read_wav(path):
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def build(threshold, num_clusters, threads):
    pyannote = sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
        model=S.DEFAULT_SEG_MODEL)
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=pyannote, num_threads=threads, provider="cpu"),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=S.DEFAULT_EMB_MODEL, num_threads=threads, provider="cpu"),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=num_clusters, threshold=threshold),
        min_duration_on=0.3, min_duration_off=0.5)
    return sherpa_onnx.OfflineSpeakerDiarization(cfg)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", action="append", required=True,
                    help="caminho:n_vozes_reais, repetivel")
    ap.add_argument("--thresholds", default="0.5,0.7,0.9")
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args(argv)

    print("omissao da biblioteca: FastClusteringConfig(threshold=0.5, "
          "num_clusters=-1)")
    print("o sidecar corre threshold=0.9\n")
    rows = []
    for spec in args.audio:
        path, _, truth = spec.rpartition(":")
        truth = int(truth) if truth.isdigit() else None
        x = read_wav(path)
        print("== %s  %.0f s  verdade-terra: %s vozes"
              % (os.path.basename(path), len(x) / 16000.0,
                 truth if truth else "?"))
        for th in [float(t) for t in args.thresholds.split(",")]:
            t0 = time.time()
            sdk = build(th, -1, args.threads)
            res = sdk.process(x)
            n = res.num_speakers            # a propria biblioteca conta
            segs = res.sort_by_start_time()
            speech = sum(float(s.end) - float(s.start) for s in segs)
            flag = ""
            if truth:
                d = n - truth
                flag = "  %+d" % d
            rows.append((os.path.basename(path), th, n, truth, len(segs),
                         speech, time.time() - t0))
            print("   threshold %.2f -> %d vozes%s   (%d seg, %.1f s de fala, "
                  "%.0f s CPU)" % (th, n, flag, len(segs), speech,
                                   time.time() - t0))
            del sdk
        print()

    print("%-14s %-9s %-6s %-9s %-5s" % ("audio", "threshold", "vozes",
                                         "verdade", "delta"))
    worst = 0
    for name, th, n, truth, nseg, speech, secs in rows:
        d = (n - truth) if truth else None
        if d is not None:
            worst = max(worst, abs(d))
        print("%-14s %-9.2f %-6d %-9s %-5s"
              % (name, th, n, truth if truth else "?", d if d is not None else "?"))
    print("\npior erro absoluto: %+d vozes" % worst)
    return 0


if __name__ == "__main__":
    sys.exit(main())