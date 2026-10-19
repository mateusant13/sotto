"""AS DUAS ALAVANCAS contra a fragmentacao. Medidas na gravacao adversa.

O problema, medido
==================
`call180.wav`: 180 s, **89 % de nao-fala**, 21,2 s de fala em 15 segmentos de
mediana 1,52 s. O proprio diarizador da **6 vozes** nesse audio; a cadeia de
produto com `StableSpeakerSlots` da **13 slots**. A gravacao de 60 s (29 % de
nao-fala, mediana 2,36 s) da 2 slots.

Ou seja: a fragmentacao NASCE A MONTANTE. `StableSpeakerSlots` casa por tempo
falado partilhado, e com 1,5 s de fala por janela partilhada nao ha quase nada
para casar. Nao e' que o casamento esteja partido -- e' que na ha o que casar.

AS DUAS ALAVANCAS QUE EXISTEM
=============================
A. `--num-speakers`: o clustering deixa de adivinhar e passa a saber. O dono
   sabe quantas pessoas estao na call; o modelo, nao.
B. `--min-on` / `--min-off`: o diarizador junta fragmentos curtos antes de
   clusterizar. 0,30 s de `min_duration_on` deixa passar falas de meio segundo.

Este mede as duas, e a combinacao, sobre a gravacao que parte. Instrumento.
Nao abre dispositivo de audio, nao lanca o Sotto.
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


ARMS = [
    # (rotulo, num_clusters, min_on, min_off)
    ("auto (o que corre hoje)", -1, 0.3, 0.5),
    ("num-speakers=2", 2, 0.3, 0.5),
    ("min_on 1,0 s", -1, 1.0, 0.8),
    ("min_on 1,0 s + num=2", 2, 1.0, 0.8),
    ("min_on 2,0 s", -1, 2.0, 1.0),
    ("min_on 2,0 s + num=2", 2, 2.0, 1.0),
]


def run(sess, audio, window_s, every_s, num_clusters, min_on, min_off):
    buf = S.RingBuffer(rate=FS, window_s=window_s)
    slots = S.StableSpeakerSlots()
    win = int(window_s * FS)
    step = int(every_s * FS)
    seen = set()
    n_seg = 0
    speech_s = 0.0
    t0 = 1_800_000_000.0
    t = time.perf_counter()
    for start in range(0, max(1, len(audio) - win + 1), step):
        buf.push(audio[start:start + step].tolist(), t0 + start / float(FS))
        if len(buf) < win:
            continue
        samples = np.asarray(buf.window(), dtype=np.float32)
        raw = [{"start": float(s.start), "end": float(s.end), "speaker": int(s.speaker)}
               for s in sess.process(samples).sort_by_start_time()]
        segs, mapping, _ = slots.remap(raw, now=buf.start_t + len(samples) / float(FS))
        seen.update(int(s["speaker"]) for s in segs)
        n_seg += len(segs)
        speech_s += sum(max(0.0, s["end"] - s["start"]) for s in segs)
    return seen, n_seg, speech_s, time.perf_counter() - t


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", default=r"I:\cc-tmp\call180.wav")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--window-s", type=float, default=10.0)
    ap.add_argument("--every-s", type=float, default=10.0)
    args = ap.parse_args(argv)

    audio = read_wav(args.audio)
    dur = len(audio) / float(FS)
    print("=" * 78)
    print("ALAVANCAS CONTRA A FRAGMENTACAO -- %s, %.0f s"
          % (os.path.basename(args.audio), dur))
    print("cadencia %0.f/%0.f s | threshold %.2f"
          % (args.window_s, args.every_s, args.threshold))
    print("=" * 78)
    print("\n%-24s %8s %9s %11s %9s"
          % ("braco", "slots", "segmentos", "fala (s)", "wall"))
    print("-" * 68)

    rows = []
    for label, nc, mo, mf in ARMS:
        sess = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                      threads=args.threads, provider="cpu",
                                      num_clusters=nc, threshold=args.threshold,
                                      min_on=mo, min_off=mf)
        seen, n_seg, speech_s, wall = run(sess, audio, args.window_s,
                                          args.every_s, nc, mo, mf)
        rows.append((label, len(seen), n_seg, speech_s, wall))
        print("%-24s %8d %9d %11.1f %8.2f s"
              % (label, len(seen), n_seg, speech_s, wall))
        del sess

    print("\nLEITURA")
    base = rows[0][1]
    print("  hoje: %d slots" % base)
    best = min(rows, key=lambda r: r[1])
    print("  melhor: %s -> %d slots" % (best[0], best[1]))
    if best[1] <= 2:
        print("\n  A ALAVANCA %s LEVA O CASO ADVERSO AO LUGAR CERTO." % best[0])
    else:
        print("\n  Nenhuma alavanca singly leva a 2 slots. Isto e' audio com")
        print("  89 %% de silencio e falas de 1,5 s: nao ha identity para manter,")
        print("  e a resposta honesta e' NAO atribuir, como mostra a leitura abaixo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())