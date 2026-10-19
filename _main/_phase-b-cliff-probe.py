"""O degrau de RTF esta na SEGMENTACAO ou nos EMBEDDINGS?

MEDIDO: a pipeline completa salta de RTF 0,0084 aos 10 s para RTF 0,478 aos
12 s -- 57x -- e continua a subir (RTF 1,66 aos 20 s). Isto importa porque a
Fase A e' so segmentacao e a Fase B e' segmentacao + embeddings + clustering.
Se o degrau estiver na segmentacao, a Fase A tambem o tem e a janela de 10 s
so porque e' segura e' um facto, nao uma coincidencia. Se estiver nos
embeddings, so a Fase B paga, e a Fase A pode windows mais compridos de graca.

Este mede as DUAS metades nos mesmos comprimentos, no mesmo processo.

Ja medido noutro sitio que refuta a hipotese do aquecimento: a 1a passagem e a
5a sao iguais (0,031 s vs 0,032 s aos 5 s). E o que muda e' o comprimento.

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
LENGTHS = (4.0, 8.0, 10.0, 11.0, 12.0, 14.0, 16.0, 20.0)


def load(path):
    with wave.open(path, "rb") as f:
        return (np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
                .astype(np.float32) / 32768.0)


def fit(src, seconds):
    need = int(seconds * FS)
    if need <= len(src):
        return src[:need]
    return np.tile(src, int(np.ceil(need / float(len(src)))))[:need]


def best_of(fn, audio, reps=3):
    best = None
    for _ in range(reps):
        t = time.perf_counter()
        fn(audio)
        el = time.perf_counter() - t
        best = el if best is None else min(best, el)
    return best


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args(argv)

    speech = load(os.path.join(ROOT, "_main", "pt-br-sample.wav"))

    import onnxruntime                                  # noqa: PLC0415
    o = onnxruntime.SessionOptions()
    o.log_severity_level = 3
    o.intra_op_num_threads = args.threads
    seg_sess = onnxruntime.InferenceSession(S.DEFAULT_SEG_MODEL, o)
    full = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                   threads=args.threads, threshold=0.9)

    def seg_only(x):
        seg_sess.run(None, {"x": np.ascontiguousarray(x)[None, None, :]})

    def full_run(x):
        full.process(x)

    print("%-7s %14s %10s %14s %10s %9s"
          % ("clip", "so segmentacao", "RTF", "pipeline completa", "RTF", "razao"))
    print("-" * 74)
    rows = []
    for sec in LENGTHS:
        audio = fit(speech, sec)
        ts = best_of(seg_only, audio)
        if sec > 11.5:
            print("      (a pipeline completa vai custar %.0f s a este "
                  "comprimento...)" % (sec * 1.0))
        tf = best_of(full_run, audio, reps=1 if sec > 11.5 else 2)
        rows.append((sec, ts, tf))
        print("%-7.0f %13.3f s %10.4f %13.3f s %10.4f %9.0fx"
              % (sec, ts, ts / sec, tf, tf / sec, tf / ts if ts else 0))

    print("\nONDE CADA METADE DA DEGRAU")
    for name, col in (("so segmentacao", 1), ("pipeline completa", 2)):
        jump = None
        for i in range(1, len(rows)):
            a, b = rows[i - 1], rows[i]
            ra, rb = a[col] / a[0], b[col] / b[0]
            if rb > max(ra * 10, 0.05):
                jump = (a[0], ra, b[0], rb, rb / ra if ra else 0)
                break
        if jump:
            print("  %-20s salta entre %.0f s (RTF %.4f) e %.0f s (RTF %.4f): x%.0f"
                  % (name, jump[0], jump[1], jump[2], jump[3], jump[4]))
        else:
            print("  %-20s SEM degrau em todo o intervalo medido" % name)

    print("\nCONSEQUENCIA PARA O DESENHO:")
    last_ok = max((r[0] for r in rows if r[2] / r[0] < 0.05), default=0)
    print("  a ultima janela com RTF < 0,05 na pipeline completa foi %.0f s" % last_ok)
    print("  a janela do sidecar sao 10 s -- dentro do lado bom, por pouco.")
    _quality(args)
    return 0


def _quality(args):
    """O degrau so atrasa, ou tambem ESTRAGA?

    MEDIDO: os MESMOS 23,6 s de duas pessoas em sequencia.
      como um clip unico de 23,6 s : 26,6 s de parede, **1 voz**  (RTF 1,130)
      como tres janelas de 10 s   :  0,06 s de parede, **2 vozes** (RTF 0,003)

    Nao e' so lentidao. Acima de ~11 s o diarizador da a RESPOSTA ERRADA: uma
    pessoa onde havia duas. Por isso `SAFE_WINDOW_S` nao e' uma preferencia de
    performance -- e' um limite de CORRECTIDADE, e por isso fica no codigo com
    um AVISO e nao num comentario.
    """
    import wave as wv
    with wv.open(os.path.join(ROOT, "_main", "pt-br-sample.wav"), "rb") as f:
        pt = (np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
              .astype(np.float32) / 32768.0)
    with wv.open(os.path.join(ROOT, "_main", "en-us-sample.wav"), "rb") as f:
        en = (np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
              .astype(np.float32) / 32768.0)

    def norm(x):
        r = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
        return x.astype(np.float32) if r <= 0 else (x * (10 ** (-20 / 20.0) / r)).astype(np.float32)

    n = min(len(pt), len(en))
    audio = np.concatenate([pt[:n], en[:n]]).astype(np.float32)
    pk = float(np.abs(audio).max())
    if pk > 0.99:
        audio = audio / pk * 0.99

    full = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                  threads=args.threads, threshold=0.9)
    dur = len(audio) / float(FS)

    print("\n" + "=" * 78)
    print("O DEGRAU ESTRAGA O RESULTADO, OU SO ATRASA? (2 pessoas em sequencia)")
    print("=" * 78)

    t = time.perf_counter()
    res = full.process(audio).sort_by_start_time()
    wall = time.perf_counter() - t
    nv = len({int(s.speaker) for s in res})
    print("  clip unico de %.1f s   : %6.2f s (RTF %.3f) -> %d voz(es)"
          % (dur, wall, wall / dur, nv))

    win_n = int(10.0 * FS)
    step_n = win_n
    slots = S.StableSpeakerSlots()
    tw = 0.0
    ids = set()
    for start in range(0, max(1, len(audio) - win_n + 1), step_n):
        chunk = audio[start:start + win_n]
        t = time.perf_counter()
        cres = full.process(chunk).sort_by_start_time()
        tw += time.perf_counter() - t
        raw = [{"start": start / float(FS) + float(s.start),
                "end": start / float(FS) + float(s.end),
                "speaker": int(s.speaker)} for s in cres]
        segs, mapping, _ = slots.remap(raw, now=(start + len(chunk)) / float(FS))
        ids.update(int(s["speaker"]) for s in segs)
    print("  tres janelas de 10 s  : %6.2f s (RTF %.3f) -> %d slot(s) %s"
          % (tw, tw / dur, len(ids), sorted(ids)))
    print("\n  o mesmo audio, o mesmo modelo, o mesmo threshold: %.0fx mais "
          "rapido" % ((wall / tw) if tw else float("inf")))
    print("  e a resposta passa de %d voz para %d. %s"
          % (nv, len(ids),
             "A janela de 10 s nao e' uma escolha: e' o que separa uma resposta "
             "certa de uma errada." if (nv == 1 and len(ids) == 2)
             else "(as duas formas deram o mesmo numero de vozes)"))


if __name__ == "__main__":
    sys.exit(main())