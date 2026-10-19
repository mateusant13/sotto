"""ONDE SE TRAÇA A LINHA: a porta de densidade de fala.

O que as duas alavancas deram, medido em `call180.wav` (89 % de nao-fala):
    auto (hoje)              12 slots | 21,1 s de fala
    num-speakers=2           12 slots | 21,1 s   -- NAO FAZ NADA, e 3,7x mais lento
    min_on 1,0 s              9 slots | 17,4 s
    min_on 2,0 s              4 slots |  8,9 s   -- deitou fora 58 % da fala

`num-speakers` nao ajuda porque a fragmentacao esta ao nivel do SEGMENTO: cada
janela tem os seus clusters locais e o `StableSpeakerSlots` nunca os junta. E
`min_on` alto nao e' um CURATIVO: e' apagar metade do que a pessoa disse.

A RESPOSTA HONESTA E' A QUE A FILOSOFIA DO PROJECTO JA DIZ: uma legenda sem voz
e' melhor do que uma legenda com a voz errada. Logo a porta nao e' umparametro
do diarizador -- e' uma **porta de densidade**: quando a janela tem pouco fala
para merecer identidade, o certo e' NAO atribuir.

ONDE FICA A PORTA
=================
Este mede, janela a janela, as DUAS gravacoes:
    - que fracao de fala cada janela tem (classe 0 do modelo = nao-fala);
    - se essa janela criou slots novos ou casou com os existentes.

A gravacao densa (79 % de fala) deu 2 slots. A esparsa (12 %) deu 12. Se houver
separacao, ha uma linha; se nao houver, a porta e' arbitraria e tem de ser
dita assim.

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

import numpy as np                      # noqa: E402

import speaker_sidecar as S             # noqa: E402

FS = 16000


def read_wav(p):
    with wave.open(p, "rb") as w:
        return (np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
                .astype(np.float32) / 32768.0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--window-s", type=float, default=10.0)
    ap.add_argument("--every-s", type=float, default=10.0)
    args = ap.parse_args(argv)

    import onnxruntime                                  # noqa: PLC0415
    o = onnxruntime.SessionOptions()
    o.log_severity_level = 3
    o.intra_op_num_threads = args.threads
    seg_sess = onnxruntime.InferenceSession(S.DEFAULT_SEG_MODEL, o)
    full = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                   threads=args.threads, threshold=args.threshold)

    print("=" * 78)
    print("A PORTA DE DENSIDADE -- janela %0.f s, passo %0.f s"
          % (args.window_s, args.every_s))
    print("=" * 78)

    win = int(args.window_s * FS)
    step = int(args.every_s * FS)
    t0 = 1_800_000_000.0
    rows = []
    for path in (r"I:\cc-tmp\call.wav", r"I:\cc-tmp\call180.wav"):
        if not os.path.exists(path):
            continue
        audio = read_wav(path)
        buf = S.RingBuffer(rate=FS, window_s=args.window_s)
        slots = S.StableSpeakerSlots()
        print("\n%s  (%.0f s)" % (os.path.basename(path), len(audio) / float(FS)))
        print("   fala%   janela | slots criados | rotulos | segmentos")
        for start in range(0, max(1, len(audio) - win + 1), step):
            buf.push(audio[start:start + step].tolist(), t0 + start / float(FS))
            if len(buf) < win:
                continue
            samples = np.asarray(buf.window(), dtype=np.float32)
            classes = S.powerset_windows(seg_sess, samples)
            speech = 1.0 - float((classes == 0).sum()) / max(1, len(classes))
            raw = [{"start": float(s.start), "end": float(s.end),
                    "speaker": int(s.speaker)}
                   for s in full.process(samples).sort_by_start_time()]
            segs, mapping, created = slots.remap(
                raw, now=buf.start_t + len(samples) / float(FS))
            after = len({int(s["speaker"]) for s in segs})
            rows.append({"file": os.path.basename(path), "speech": speech,
                         "created": len(created or ()), "segments": len(segs),
                         "labels": after})
            print("   %5.1f   %6.1f-%6.1f | criaram %d     | %6d | %d"
                  % (100 * speech, buf.start_t - t0,
                     buf.start_t - t0 + len(samples) / float(FS),
                     len(created or ()), after, len(segs)))

    if not rows:
        return 3

    print("\n" + "=" * 78)
    print("SEPARACAO ENTRE 'FALA' E 'NAO FALA'")
    print("=" * 78)
    print("%-16s %9s %9s %9s" % ("gravacao", "fala%", "criou", "janelas"))
    for f in sorted({r["file"] for r in rows}):
        sub = [r for r in rows if r["file"] == f]
        print("%-16s %8.1f%% %9d %9d"
              % (f, 100 * sum(r["speech"] for r in sub) / len(sub),
                 sum(r["created"] for r in sub), len(sub)))

    creating = [r for r in rows if r["created"] > 0]
    quiet = [r for r in rows if r["created"] == 0]
    if quiet and creating:
        print("\n  janelas que NAO criaram slot: fala media %.1f%% (max %.1f%%)"
              % (100 * sum(r["speech"] for r in quiet) / len(quiet),
                 100 * max(r["speech"] for r in quiet)))
        print("  janelas que criaram:      fala media %.1f%% (min %.1f%%)"
              % (100 * sum(r["speech"] for r in creating) / len(creating),
                 100 * min(r["speech"] for r in creating)))
        overlap = [r for r in quiet if r["speech"] >= min(x["speech"] for x in creating)]
        if not overlap:
            print("\n  SEPARACAO LIMPA: nenhuma janela com fala igual a de uma "
                  "janela que cria slot deixou de criar.")
            print("  Uma porta por DENSIDADE e' justificada pelos dados, e nao e' "
                  "um numero Inventado.")
        else:
            print("\n  Ha sobreposicao (%d janelas): a densidade sozinha nao "
                  "separa. A porta tem de ser escrita como tal." % len(overlap))
    return 0


if __name__ == "__main__":
    sys.exit(main())