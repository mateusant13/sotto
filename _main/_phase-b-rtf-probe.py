"""RTF da pipeline completa em funcao do COMPRIMENTO. Onde esta o degrau?

O que me pôs a medir: `multivoice-offline.py` mediu RTF 0,004 num clip de 10 s,
e eu vinha a reportar 0,18 a 0,89. Suspeitei de aquecimento; essa suspeita esta
REFUTADA -- a 5 s e a 10 s a 1a passagem e a 5a sao iguais. O que muda e' o
COMPRIMENTO:

    5 s  -> 0,030 s  (RTF 0,006)
    10 s -> 0,033 s  (RTF 0,003)
    20 s -> 19,9 s   (RTF 0,99)   <- 600x mais por 2x o audio

Isso e' um degrau, nao uma curva. E tem consequencia directa no pedido do dono:
ele disse que separar as vozes em tempo real lhe pesa, e "pesado" pode ser
literalmente este degrau. A janela do sidecar e' de 10 s com passo 10 s, ou
seja ESTAVA NO LADO BOM DA CURVA -- e mudar a janela para 20 s, que "deveria"
dar mais contexto, punha-o no lado mau.

Este mede a curva com finura, e separa ashipoteses que explicam o degrau.

Instrumento. Nao abre dispositivo de audio, nao lanca o Sotto.
"""
import argparse
import os
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                     # noqa: E402

import speaker_sidecar as S            # noqa: E402

FS = 16000


def load(path):
    with wave.open(path, "rb") as f:
        return (np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
                .astype(np.float32) / 32768.0)


def fit(src, seconds):
    """Encolhe/copia `src` ate `seconds`, mantendo a voz e o silencio reais."""
    need = int(seconds * FS)
    if need <= len(src):
        return src[:need]
    return np.tile(src, int(np.ceil(need / float(len(src)))))[:need]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args(argv)

    speech = load(os.path.join(ROOT, "_main", "pt-br-sample.wav"))
    sess = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                  threads=args.threads, threshold=0.9)

    print("voz de origem: pt-br-sample, %.1f s\n" % (len(speech) / float(FS)))
    print("%-8s %12s %12s %12s %10s"
          % ("clip", "wall", "RTF", "wall por +1 s", "vozes"))
    print("-" * 62)
    rows = []
    prev = None
    for seconds in (4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0):
        audio = fit(speech, seconds)
        best = None
        for _ in range(3):
            t = time.perf_counter()
            res = sess.process(audio)
            el = time.perf_counter() - t
            best = el if best is None else min(best, el)
        try:
            nv = len({int(s.speaker) for s in res})
        except Exception:                                       # noqa: BLE001
            nv = -1
        delta = "-" if prev is None else "%.3f s" % (best - prev)
        rows.append((seconds, best, best / seconds, nv))
        print("%-8.0f %11.3f s %11.4f %12s %10d"
              % (seconds, best, best / seconds, delta, nv))
        prev = best
        if best > 90:
            print("   (parou: um degrau destes ja custou %.0f s de CPU)" % best)
            break

    print("\nONDE ESTA O DEGRAU")
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        if b[2] > a[2] * 20 and b[2] > 0.05:
            print("  entre %.0f s (RTF %.4f) e %.0f s (RTF %.4f): multiplica por %.0f"
                  % (a[0], a[2], b[0], b[2], b[2] / a[2] if a[2] else float("inf")))
    return 0


if __name__ == "__main__":
    sys.exit(main())