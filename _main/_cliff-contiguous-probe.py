"""O DEGRAU DEPENDE DO AUDIO SER CONTIGUO? -- a contradicao que falta resolver.

A contradicao
=============
  `_phase-b-cliff-probe.py` mediu, num audio de 23,5 s de DUAS pessoas em
  sobreposicao CONTINUA, que o clip unico devolve **1 voz** e as tres janelas de
  10 s devolvem **2**. Daqui veio `SAFE_WINDOW_S = 10,0`.

  Mas o sidecar corre janelas de 20 s (`DEFAULT_WINDOW_S`) e em `call.wav`, que
  tem 29 % de silencio e falas separadas, deu os **2 slots correctos**.

Duas leituras possiveis, e elas pedem decisoes opostas:
  A. O degrau e' do COMPRIMENTO. Entao 20 s de janela e' perigoso e o default
     de producao tem de mudar.
  B. O degrau e' do AUDIO CONTIGUO. Uma janela longa de audio COM pausas tem
     pausas que sao pausas, e o diarizador nao se perde. Entao 20 s esta bem e
     mudar o default seria reagir a uma medicao que nao descreve a producao.

Este mede as DUAS: janela de 20 s contra janela de 10 s, na MESMA gravacao real
(a que tem 29 % de silencio) e num audio CONTIGUO sintetico, e diz quantas vozes
cada uma encontra.

Nao muda nada sozinho. Muda o que se pode afirmar com honestidade.
"""
import argparse
import os
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                      # noqa: E402

import speaker_sidecar as S             # noqa: E402

FS = 16000


def read_wav(p):
    with wave.open(p, "rb") as w:
        return (np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
                .astype(np.float32) / 32768.0)


def rms_to(x, dbfs=-20.0):
    r = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
    return x.astype(np.float32) if r <= 0 else (x * (10 ** (dbfs / 20.0) / r)).astype(np.float32)


def contiguous_two_people(seconds):
    """Duas pessoas uma APOS A OUTRA, sem pausa: o pior caso do degrau."""
    pt = rms_to(read_wav(os.path.join(ROOT, "_main", "pt-br-sample.wav")))
    en = rms_to(read_wav(os.path.join(ROOT, "_main", "en-us-sample.wav")))
    need = int(seconds * FS)
    a = pt[:need] if len(pt) >= need else np.tile(pt, int(np.ceil(need / len(pt))))[:need]
    b = en[:need] if len(en) >= need else np.tile(en, int(np.ceil(need / len(en))))[:need]
    out = np.concatenate([a, b]).astype(np.float32)
    pk = float(np.abs(out).max())
    return out / pk * 0.99 if pk > 0.99 else out


def speakers_in(sess, x):
    rows = sess.process(np.asarray(x, dtype=np.float32)).sort_by_start_time()
    segs = [(float(s.start), float(s.end), int(s.speaker)) for s in rows]
    return sorted({l for _, _, l in segs}), segs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.9)
    args = ap.parse_args(argv)

    sess = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                   threads=args.threads, threshold=args.threshold)

    real = r"I:\cc-tmp\call.wav"
    print("=" * 78)
    print("O DEGRAU DEPENDE DE O AUDIO SER CONTIGUO? (2 pessoas = certo e' 2)")
    print("=" * 78)

    if os.path.exists(real):
        audio = read_wav(real)
        print("\nA) AUDIO REAL COM PAUSAS  (%s, %.0f s, 29%% de silencio)"
              % (os.path.basename(real), len(audio) / float(FS)))
        for w in (10.0, 20.0):
            seg_len = int(w * FS)
            if len(audio) < seg_len:
                continue
            chunk = audio[:seg_len]
            t = time.perf_counter()
            spk, segs = speakers_in(sess, chunk)
            print("   janela %2.0f s -> %d voz(es) %s | %d segmentos | %.1f s "
                  "de fala | RTF %.3f"
                  % (w, len(spk), spk, len(segs),
                     sum(max(0, b - a) for a, b, _ in segs),
                     (time.perf_counter() - t) / w))
    else:
        print("\nA) AUDIO REAL AUSENTE: %s" % real)

    print("\nB) AUDIO SINTETICO CONTIGUO (duas pessoas sem pausa)")
    for secs in (10.0, 15.0, 20.0):
        x = contiguous_two_people(secs)
        t = time.perf_counter()
        spk, segs = speakers_in(sess, x)
        wall = time.perf_counter() - t
        print("   janela %2.0f s -> %d voz(es) %s | %d segmentos | RTF %.3f"
              % (secs, len(spk), spk, len(segs), wall / secs))

    print("\n" + "=" * 78)
    print("LEITURA")
    print("=" * 78)
    print("  Se o audio real der 2 vozes em 20 s E o sintetico der 1, o degrau")
    print("  e' do audio CONTIGUO: falta-lhe respiracao, e uma janela de 20 s de")
    print("  audio real -- que tem pausas -- nao esta no lado mau.")
    print("  Se AMBOS derem mal, o degrau e' do comprimento e o default tem de mudar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())