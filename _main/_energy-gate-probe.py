"""A PORTA TEM DE FUNCIONAR SEM O MODELO. Envelope de energia vs classe 0.

O problema que isto resolve
===========================
A separacao medida e' lindissima -- 5,1-9,8 s de fala na gravacao densa,
0,3-3,2 s na esparsa, e uma porta em ~4 s separa as duas sem arbitrario. Mas
**mediu-se com a classe 0 do modelo de segmentacao**, e usar esse modelo para
vigiar o pipeline que o carrega custa os 90 MB que a Fase A existe para evitar.

A porta tem de ser barata E independente. O candidato e' a envolvente de
energia: RMS por janela, limiar RELATIVO ao pico da propria janela, zero
modelos, zero RAM. E independente por construcao -- o rms do audio nao sabe
nada sobre vozes.

O RISCO, dito antes de medir
============================
As duas gravacoes tem niveis muito diferentes: `call.wav` a -18,5 dBFS e
`call180.wav` a -32,5 dBFS. Um limiar ABSOLUTO mediria o ganho, nao o audio, e
daria um falso limiar limpo. Daqui o limiar ser relativo a cada janela. Este
instrumento mostra as DUAS versoes lado a lado para deixar ver qual separa.

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


def envelope_seconds(x, hop_s=0.020, win_s=0.040, thr=0.10):
    """Segundos de 'fala' por envolvente de energia, limiar RELATIVO ao pico.

    O limiar e' fracao do pico da propria janela, e nao dBFS: duas gravacoes
    com 14 dB de diferenca (medido) tem de dar numeros comparaveis.
    """
    hop = int(hop_s * FS)
    win = max(1, int(win_s * FS))
    n = max(0, (len(x) - win) // hop + 1)
    if n == 0:
        return 0.0
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    rms = np.sqrt((x[idx] ** 2).mean(axis=1))
    peak = float(rms.max()) if rms.size else 0.0
    if peak <= 0:
        return 0.0
    return float((rms >= peak * thr).sum()) * hop_s


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--window-s", type=float, default=10.0)
    ap.add_argument("--thresholds", default="0.05,0.10,0.20,0.30")
    args = ap.parse_args(argv)

    import onnxruntime                                  # noqa: PLC0415
    o = onnxruntime.SessionOptions()
    o.log_severity_level = 3
    o.intra_op_num_threads = args.threads
    seg_sess = onnxruntime.InferenceSession(S.DEFAULT_SEG_MODEL, o)

    win = int(args.window_s * FS)
    thrs = [float(t) for t in args.thresholds.split(",")]

    print("=" * 78)
    print("A PORTA SEM MODELO: envolvente de energia vs classe 0")
    print("janela %.0f s | gravacao densa deu 2 slots, a esparsa deu 12"
          % args.window_s)
    print("=" * 78)

    data = {}
    for path in (r"I:\cc-tmp\call.wav", r"I:\cc-tmp\call180.wav"):
        if not os.path.exists(path):
            continue
        audio = read_wav(path)
        model_s, env_s, rms_db = [], [], []
        for start in range(0, max(1, len(audio) - win + 1), win):
            chunk = np.asarray(audio[start:start + win], dtype=np.float32)
            if len(chunk) < win // 2:
                continue
            cls = S.powerset_windows(seg_sess, chunk)
            model_s.append((1.0 - float((cls == 0).sum()) / max(1, len(cls)))
                           * (len(chunk) / float(FS)))
            r = float(np.sqrt(np.mean(chunk ** 2))) if chunk.size else 0.0
            rms_db.append(20 * np.log10(r + 1e-12))
            env_s.append({t: envelope_seconds(chunk, thr=t) for t in thrs})
        data[os.path.basename(path)] = (model_s, env_s, rms_db)

    for name, (model_s, env_s, rms_db) in data.items():
        print("\n%s" % name)
        print("  rms por janela: %.1f a %.1f dBFS" % (min(rms_db), max(rms_db)))
        print("  fala pelo MODELO: %s" % ", ".join("%.1f" % s for s in model_s))
        for t in thrs:
            print("  fala pela ENVOLVIDE thr=%.2f: %s"
                  % (t, ", ".join("%.1f" % d[t] for d in env_s)))

    print("\n" + "=" * 78)
    print("QUAL LIMIAR SEPARA? (densa: min > esparsa: max)")
    print("=" * 78)
    names = list(data)
    if len(names) < 2:
        return 0
    dense = [s for s in data["call.wav"][0] if s > 0.05]
    sparse = [s for s in data["call180.wav"][0] if s > 0.05]
    if not dense or not sparse:
        print("  uma das gravacoes nao tem janelas com fala; nada a separar")
        return 0
    print("  pelo MODELO: densa >= %.1f s, esparsa <= %.1f s"
          % (min(dense), max(sparse)))
    for t in thrs:
        d = [x[t] for x in data["call.wav"][1]]
        s = [x[t] for x in data["call180.wav"][1]]
        d = [v for v in d if v > 0.05]
        s = [v for v in s if v > 0.05]
        if d and s:
            ok = min(d) > max(s)
            print("  pela ENVOLVIDE thr=%.2f: densa >= %.1f s, esparsa <= %.1f s  %s"
                  % (t, min(d), max(s), "SEPARADO" if ok else "sobreposto"))
    return 0


if __name__ == "__main__":
    sys.exit(main())