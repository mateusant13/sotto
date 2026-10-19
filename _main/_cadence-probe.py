"""A CADENCIA DE PRODUCAO esta correcta? Medida sobre a call REAL.

O que encontrei
---------------
`DEFAULT_WINDOW_S = 20,0` e `DEFAULT_EVERY_S = 10,0`. Passar uma janela de 20 s
ao diarizador e um degrau comprovadamente errado (o degrau e' entre 10 s e 11 s:
RTF 3,019 e UMA voz onde havia duas). O default de producao esta do lado mau.

E, pior: os mesmos 180 s da call real, pela cadeia completa com
`StableSpeakerSlots`, dao **6 slots para 2 pessoas** -- o painel faria seis
pontos coloridos para duas pessoas, e a janela 17 ainda troca 5<->6. Com a call
de 60 s dao 2 slots. A identidade aguenta 60 s e parte-se depois.

AS HIPOTESES, e porque todas tem de ser testadas
------------------------------------------------
  A. A janela de 20 s esta no lado errado do degrau, e a resposta errada
     alimenta o casamento de slots.
  B. `StableSpeakerSlots` casa por TEMPO FALADO PARTILHADO. Com janela 10 s e
     passo 10 s as janelas nao tem audio em comum nenhum -- nao ha nada para
     casar. Com janela 20 s e passo 10 s ha 10 s de sobreposicao, e mesmo assim
     parte. Portanto ha um terceiro fator.
  C. A qualidade do cluster local piora com a janela, e slots novos nascem de
     clusters locais melhores do que os velhos.

Este mede as duas metades -- quantos slots globais, e quanto custou -- para uma
grelha de cadencias. E' a medicao que decide os defaults.

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


CADENCES = [
    # (janela, passo, rotulo)
    (20.0, 10.0, "DEFAULT DE HOJE (20/10)"),
    (10.0, 10.0, "10/10  sem sobreposicao"),
    (10.0, 5.0, "10/5   50% de sobreposicao"),
    (10.0, 3.0, "10/3   70% de sobreposicao"),
    (10.0, 2.0, "10/2   80% de sobreposicao"),
]


def run_cadence(sess, audio, window_s, every_s):
    """A cadeia de produto numa cadencia. Devolve (slots, segmentos, wall)."""
    buf = S.RingBuffer(rate=FS, window_s=window_s)
    slots = S.StableSpeakerSlots()
    win = int(window_s * FS)
    step = int(every_s * FS)
    seen = set()
    n_seg = 0
    t0 = 1_800_000_000.0
    t = time.perf_counter()
    ticks = 0
    for start in range(0, max(1, len(audio) - win + 1), step):
        buf.push(audio[start:start + step].tolist(), t0 + start / float(FS))
        if len(buf) < win:
            continue
        ticks += 1
        samples = np.asarray(buf.window(), dtype=np.float32)
        raw = [{"start": float(s.start), "end": float(s.end), "speaker": int(s.speaker)}
               for s in sess.process(samples).sort_by_start_time()]
        segs, mapping, _ = slots.remap(raw, now=buf.start_t + len(samples) / float(FS))
        seen.update(int(s["speaker"]) for s in segs)
        n_seg += len(segs)
    return seen, n_seg, time.perf_counter() - t, ticks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", default=r"I:\cc-tmp\call180.wav")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.9)
    args = ap.parse_args(argv)

    audio = read_wav(args.audio)
    dur = len(audio) / float(FS)
    print("=" * 78)
    print("CADENCIA DE PRODUCAO -- %s, %.0f s, 2 pessoas"
          % (os.path.basename(args.audio), dur))
    print("degrau medido: acima de %.0f s de janela a resposta fica errada"
          % S.SAFE_WINDOW_S)
    print("=" * 78)

    sess = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                  threads=args.threads, threshold=args.threshold)

    print("\n%-26s %8s %8s %9s %10s %8s"
          % ("cadencia", "janela", "passo", "slots", "wall", "RTF"))
    print("-" * 78)
    rows = []
    for window_s, every_s, label in CADENCES:
        seen, n_seg, wall, ticks = run_cadence(sess, audio, window_s, every_s)
        rtf = wall / dur
        rows.append((label, window_s, every_s, len(seen), wall, rtf, ticks))
        flag = "  <<< DEGRAU" if window_s > S.SAFE_WINDOW_S else ""
        print("%-26s %7.0f s %7.0f s %9d %9.2f s %8.3f%s"
              % (label, window_s, every_s, len(seen), wall, rtf, flag))

    print("\nLEITURA")
    best = min(rows, key=lambda r: (abs(r[3] - 2), r[5]))
    print("  o default de hoje da %d slots; o melhor da %d"
          % (rows[0][3], best[3]))
    over = [r for r in rows if r[1] > S.SAFE_WINDOW_S]
    if over:
        print("  %s" % over[0][0])
        print("    usa janela de %.0f s, ACIMA de %.0f s: do lado errado do degrau."
              % (over[0][1], S.SAFE_WINDOW_S))
    print("\n  quantos ticks cada cadencia precisou (custo real por call):")
    for r in rows:
        print("    %-26s %3d ticks" % (r[0], r[6]))
    return 0


if __name__ == "__main__":
    sys.exit(main())