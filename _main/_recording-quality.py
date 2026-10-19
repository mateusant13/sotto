"""QUE AUDIO E' ISTO? Caracteriza as gravacoes antes de as usar como prova.

Por que isto vem primeiro
=========================
Os 180 s de `call180.wav` deram 13 slots para 2 pessoas pela cadeia de produto,
e 22 com mais sobreposicao -- mais evidencia, mais fragmentos, o oposto do que a
hipotese previa. Antes de mexer em `StableSpeakerSlots`, a pergunta obvia e' se
a GRAVACAO serve como prova.

`gather-rule.py` ja mediu, na mesma gravacao, que a classe 0 do modelo de
segmentacao -- "ninguem" -- ocupa 9486 frames de 10663. Sao **89 % de nao-fala**.
E o pipeline completo encontrou so 15 segmentos em 180 s.

Se o audio e' maioritariamente silencio, entao "13 slots" pode ser o
comportamento honesto de um diarizador a receber silência: nao ha fala para casar,
`min_duration_off` parte o resto em micro-segmentos, e o casamento por tempo
falado partilhado -- que e' o que `StableSpeakerSlots` faz -- nao tem nada com
que trabalhar.

Este mede as duas gravacoes lado a lado, para se ver se sao comparaveis.
Recordar: `call.wav` (60 s) deu 2 slots; `call180.wav` (180 s) deu 13.

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


def describe(sess, name, x):
    dur = len(x) / float(FS)
    peak = float(np.abs(x).max()) if x.size else 0.0
    rms = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0

    # Janelas de 10 s, como a app. A classe 0 do modelo e' "ninguem".
    win = int(10.0 * FS)
    n_win = max(1, len(x) // win)
    non_speech = 0
    speech_windows = 0
    total_frames = 0
    for i in range(n_win):
        chunk = x[i * win:(i + 1) * win]
        if len(chunk) < win // 2:
            continue
        classes = S.powerset_windows(sess, chunk)
        total_frames += len(classes)
        k = int((classes == 0).sum())
        non_speech += k
        if k < len(classes):
            speech_windows += 1

    # Quantos segmentos o diarizador cheio extrai, e de que tamanho.
    seg = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                 threads=2, threshold=0.9)
    out = seg.process(x).sort_by_start_time()
    rows = [(float(s.start), float(s.end), int(s.speaker)) for s in out]
    speech_s = sum(max(0.0, b - a) for a, b, _ in rows)
    spk = sorted({l for _, _, l in rows})

    print("\n%s" % name)
    print("  duracao %.1f s | peak %.4f | rms %.5f (%.1f dBFS)"
          % (dur, peak, rms, 20 * np.log10(rms + 1e-12)))
    print("  classe 0 (ninguem): %d de %d frames = %.1f%% nao-fala"
          % (non_speech, total_frames,
             100.0 * non_speech / max(1, total_frames)))
    print("  janelas de 10 s com alguma fala: %d de %d"
          % (speech_windows, n_win))
    print("  pipeline completa: %d voz(es) %s | %d segmentos | %.1f s de fala "
          "= %.1f%% da gravacao"
          % (len(spk), spk, len(rows), speech_s, 100.0 * speech_s / max(1e-9, dur)))
    if rows:
        lens = sorted(b - a for a, b, _ in rows)
        print("  duracao dos segmentos: min %.2f s | mediana %.2f s | max %.2f s"
              % (lens[0], lens[len(lens) // 2], lens[-1]))
    return {"name": name, "dur": dur, "nonspeech_pct": 100.0 * non_speech / max(1, total_frames),
            "speech_s": speech_s, "segments": len(rows), "speakers": len(spk)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pairs", default=r"I:\cc-tmp\call.wav,I:\cc-tmp\call180.wav")
    args = ap.parse_args(argv)

    print("=" * 78)
    print("AS DUAS GRAVACOES SAO COMPARAVEIS? (a de 60 s deu 2 slots, a de 180 s deu 13)")
    print("=" * 78)

    import onnxruntime                                  # noqa: PLC0415
    o = onnxruntime.SessionOptions()
    o.log_severity_level = 3
    o.intra_op_num_threads = 2
    sess = onnxruntime.InferenceSession(S.DEFAULT_SEG_MODEL, o)

    out = []
    for p in args.pairs.split(","):
        p = p.strip()
        if not p or not os.path.exists(p):
            print("\n%s AUSENTE" % p)
            continue
        out.append(describe(sess, os.path.basename(p), read_wav(p)))

    if len(out) == 2:
        a, b = out
        print("\n" + "=" * 78)
        print("COMPARACAO")
        print("=" * 78)
        print("  %-18s %10s %12s %10s" % ("gravacao", "nao-fala", "fala", "segmentos"))
        for r in out:
            print("  %-18s %9.1f%% %10.1f s %10d"
                  % (r["name"], r["nonspeech_pct"], r["speech_s"], r["segments"]))
        if abs(a["nonspeech_pct"] - b["nonspeech_pct"]) > 25:
            print("\n  SAO DE QUALIDADES MUITO DIFERENTES. A de 180 s tem "
                  "%.0f%% de nao-fala contra %.0f%% da de 60 s."
                  % (b["nonspeech_pct"], a["nonspeech_pct"]))
            print("  Usar a mais silenciosa para julgar a estabilidade da "
                  "identidade e' usar o caso adverso -- o que e' bom, se o")
            print("  produto tem de sobreviver a uma call com pausas. Mas entao")
            print("  o numero '13 slots' tem de ser lido como '13 slots num "
                  "audio com")
            print("  %.0f%% de silencio', e nao como '13 slots numa call'."
                  % b["nonspeech_pct"])
    return 0


if __name__ == "__main__":
    sys.exit(main())