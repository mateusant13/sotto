"""SEGUNDOS DE FALA POR JANELA -- a unidade que separa os dois casos.

O paradoxo que a medicao anterior deixou aberto
===============================================
  call.wav    70,9 % de fala -> 2 slots   a 20/10, mas 8 slots a 10/10
  call180.wav 11,0 % de fala -> 12 slots  em qualquer cadencia

Duas coisas a aprender ao mesmo tempo:

1. **A SOBREPOSICAO E' NECESSARIA.** 10/10 nao tem audio em comum nenhum entre
   janelas, e a identidade parte-se mesmo numa gravacao densa (2 -> 8 slots).
   20/10 tem 10 s de sobreposicao e mantem 2.

2. **A SOBREPOSICAO NAO CHEGA QUANDO HA FALA.** Mais sobreposicao no audio
   esparso deu MAIS fragmentos, nao menos: 10/5 -> 22 slots, 10/3 -> 33,
   10/2 -> 49. Nao e' que o casamento esteja partido -- e' que 10 s de
   sobreposicao entre duas janelas de audio com 89 % de silencio NAO CONTEM
   FALA, e `StableSpeakerSlots` casa por tempo falado partilhado. Sem fala em
   comum nao ha o que casar, e cada janela nasce um slot novo.

A CONclusAO QUE FALTA E' ONDE ESTA A PORTA
==========================================
Percentagem e' a unidade errada. O que interessa e' quantos SEGUNDOS de fala a
janela contem, porque e' isso que o casamento precisa de ver. Este mede isso nas
duas gravacoes e procura a linha.

Instrumento. Nao abre dispositivo de audio, nao lanca o Sotto.
"""
import argparse
import os
import sys
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


def speech_seconds(seg_sess, x):
    """Segundos de fala na janela, pela classe 0 do modelo (= ninguem)."""
    classes = S.powerset_windows(seg_sess, x)
    return (1.0 - float((classes == 0).sum()) / max(1, len(classes))) * (len(x) / float(FS))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--window-s", type=float, default=10.0)
    args = ap.parse_args(argv)

    import onnxruntime                                  # noqa: PLC0415
    o = onnxruntime.SessionOptions()
    o.log_severity_level = 3
    o.intra_op_num_threads = args.threads
    seg_sess = onnxruntime.InferenceSession(S.DEFAULT_SEG_MODEL, o)

    win = int(args.window_s * FS)
    print("=" * 78)
    print("SEGUNDOS DE FALA POR JANELA DE %.0f s" % args.window_s)
    print("=" * 78)
    per_file = {}
    for path in (r"I:\cc-tmp\call.wav", r"I:\cc-tmp\call180.wav"):
        if not os.path.exists(path):
            continue
        audio = read_wav(path)
        secs = []
        for start in range(0, max(1, len(audio) - win + 1), win):
            chunk = audio[start:start + win]
            if len(chunk) < win // 2:
                continue
            secs.append(speech_seconds(seg_sess, np.asarray(chunk, dtype=np.float32)))
        per_file[os.path.basename(path)] = secs
        nz = [s for s in secs if s > 0.05]
        print("\n%s  (%.0f s, %d janelas)"
              % (os.path.basename(path), len(audio) / float(FS), len(secs)))
        print("   fala por janela: %s"
              % ", ".join("%.1f" % s for s in secs))
        if nz:
            print("   janelas com fala: min %.1f s | mediana %.1f s | max %.1f s"
                  % (min(nz), sorted(nz)[len(nz) // 2], max(nz)))
        else:
            print("   nenhuma janela com fala")

    if len(per_file) < 2:
        return 0

    dense = per_file.get("call.wav", [])
    sparse = per_file.get("call180.wav", [])
    print("\n" + "=" * 78)
    print("ONDE FICA A PORTA")
    print("=" * 78)
    ds = [s for s in dense if s > 0.05]
    ss = [s for s in sparse if s > 0.05]
    if ds and ss:
        print("  gravacao DENSA  (2 slots com sobreposicao): fala %.1f a %.1f s"
              % (min(ds), max(ds)))
        print("  gravacao ESPARSA (12 slots):                fala %.1f a %.1f s"
              % (min(ss), max(ss)))
        gap_lo, gap_hi = max(ss), min(ds)
        if gap_lo < gap_hi:
            print("\n  SEPARACAO LIMPA: nenhuma janela esparsa chega a %.1f s, e "
                  "nenhuma densa desce abaixo disso." % gap_hi)
            print("  Uma porta em %.1f s de fala por janela de %.0f s separa os "
                  "dois casos sem arbitrario."
                  % ((gap_lo + gap_hi) / 2.0, args.window_s))
            print("\n  E a leitura que importa: na gravacao esparsa o melhor "
                  "armamento")
            print("  dava 4 slots MAS deitava fora 58 %% da fala. Uma porta "
                  "declara")
            print("  'aqui nao ha voz para atribuir' e NAO inventa -- que e' a "
                  "mesma")
            print("  doutrina do resto do projecto: legenda sem voz melhor que "
                  "legenda com")
            print("  a voz errada.")
        else:
            print("\n  Ha sobreposicao entre as duas: nao ha uma porta limpa, e "
                  "a porta")
            print("  teria de ser arbitraria. Dito como tal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())