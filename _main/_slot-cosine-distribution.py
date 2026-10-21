"""A separacao REAL do coseno entre vozes, no audio da call do dono.

PORQUE ISTO EXISTE
------------------
O pyannote (paper "pyannote.audio 2.1 speaker diarization pipeline: principle,
benchmark, and recipe") NAO casa janelas por tempo. Ele agrupa porjanela e
depois faz CLUSTERING GLOBAL AGLOMERATIVO sobre os CENTROIDES dos clusters
locais. E' essa segunda etapa que segura a identidade ao longo do ficheiro.

A correccao que tenho hoje (`StableSpeakerSlots`) casa por TEMPO FALADO
PARTILHADO entre janelas consecutivas. Funciona, e esta medido (cru 70,2 % ->
87,7 %), mas e' mais fraca: so consegue casar o que se sobrepoe, e nao funde
duas slots que o diarizador partiu.

O sherpa tem as pecas: `SpeakerEmbeddingExtractor.compute(stream)` devolve o
embedding, e `FastClustering` e' o aglomerativo. Falta uma coisa antes de
escrever a segunda etapa: **QUAL limiar de coseno**. A documentacao do fornecedor
nao diz, e um limiar chutado seria uma constante sem medida -- exactamente o que
este repo nao aceita.

ESTE INSTRUMENTO MEDE A DISTRIBUICAO. Nada de limiar aqui: so numeros.
"""
import argparse
import os
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                    # noqa: E402
import sherpa_onnx                    # noqa: E402

import speaker_sidecar as S           # noqa: E402


def read_wav(path):
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def extractor(threads=2):
    return sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=S.DEFAULT_EMB_MODEL, num_threads=threads, provider="cpu"))


def embed(ex, samples):
    """Embedding (L2-normalised) de um troco de audio 16 kHz.

    MEASURED: `OnlineStream.accept_waveform` takes `(sample_rate, waveform)` --
    two arguments, sample rate FIRST. Calling it with the waveform alone raises
    `TypeError: incompatible function arguments` and prints the whole signature.
    The same shape of mistake as the diarizer config one: the pybind signature,
    not the Python intuition.
    """
    if len(samples) < int(0.5 * S.DEFAULT_RATE):
        return None
    st = ex.create_stream()
    st.accept_waveform(float(S.DEFAULT_RATE), samples)
    finished = getattr(st, "input_finished", None)
    if callable(finished):
        try:
            finished()
        except TypeError:
            finished(samples)
    v = np.asarray(ex.compute(st), dtype=np.float32)
    n = float(np.linalg.norm(v))
    if n <= 0:
        return None
    return v / n


def cos(a, b):
    return float(np.dot(a, b))


def centroid(ex, audio, spans):
    """Embedding medio dos segmentos, normalizado -- o 'centroide local'."""
    vs = [embed(ex, audio[int(s * S.DEFAULT_RATE):int(e * S.DEFAULT_RATE)])
          for s, e in spans]
    vs = [v for v in vs if v is not None]
    if not vs:
        return None, 0
    m = np.mean(np.stack(vs), axis=0)
    n = float(np.linalg.norm(m))
    return (m / n if n > 0 else None), len(vs)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--window-s", type=float, default=S.DEFAULT_WINDOW_S)
    ap.add_argument("--step-s", type=float, default=S.DEFAULT_EVERY_S)
    args = ap.parse_args(argv)

    audio = read_wav(args.audio)
    dur = len(audio) / S.DEFAULT_RATE
    print("audio %.1f s  threshold %.2f" % (dur, args.threshold))

    sdk = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                  threads=args.threads, threshold=args.threshold)
    ex = extractor(args.threads)

    # (A) UMA PASSAGEM: a verdade-terra ESTRUTURAL -- quem é quem no ficheiro
    ref = [(float(s.start), float(s.end), int(s.speaker))
           for s in sdk.process(audio).sort_by_start_time()]
    by_spk = {}
    for s, e, l in ref:
        by_spk.setdefault(l, []).append((s, e))
    print("\n[A] UMA PASSAGEM: %d segmentos, %d vozes -> %s"
          % (len(ref), len(by_spk), sorted(by_spk)))
    ref_vec = {}
    for l, spans in sorted(by_spk.items()):
        c, n = centroid(ex, audio, spans)
        if c is not None:
            ref_vec[l] = c
            print("   voz %d: %d segmentos, %d embeddings, |v|=%.3f"
                  % (l, len(spans), n, float(np.linalg.norm(c))))
    labs = sorted(ref_vec)
    print("\n    coseno ENTRE vozes (a verdade-terra do ficheiro inteiro):")
    for i in range(len(labs)):
        for j in range(i + 1, len(labs)):
            print("      cos(voz%d, voz%d) = %+.3f"
                  % (labs[i], labs[j], cos(ref_vec[labs[i]], ref_vec[labs[j]])))

    # (B) CADA JANELA: os centroides LOCAIS, que e' o que a 2a etapa vera
    win = int(args.window_s * S.DEFAULT_RATE)
    step = int(args.step_s * S.DEFAULT_RATE)
    print("\n[B] CENTROIDES POR JANELA (o que o clustering global receberia):")
    rows = []
    for a0 in range(0, max(1, len(audio) - win + 1), step):
        t0 = a0 / S.DEFAULT_RATE
        segs = [(float(s.start) + t0, float(s.end) + t0, int(s.speaker))
                for s in sdk.process(audio[a0:a0 + win]).sort_by_start_time()]
        loc = {}
        for s, e, l in segs:
            loc.setdefault(l, []).append((s, e))
        vecs = {}
        for l, spans in sorted(loc.items()):
            c, n = centroid(ex, audio, spans)
            if c is not None:
                vecs[l] = c
        if not vecs:
            print("   janela %5.1f..%5.1f  (sem fala)" % (t0, t0 + args.window_s))
            continue
        # qual a voz REAL de cada cluster local, pelo tempo partilhado com [A]
        truth = {}
        for l in vecs:
            ov = {}
            for rl, spans in by_spk.items():
                lo = sum(max(0.0, min(e, re) - max(s, rs))
                         for s, e in spans for rs, re in by_spk[rl])
                ov[rl] = lo
            truth[l] = max(ov, key=lambda k: (ov[k], -k))
        pairs = [(cos(vecs[i], vecs[j]), truth[i], truth[j])
                 for i in sorted(vecs) for j in sorted(vecs) if i < j]
        same = [c for c, a, b in pairs if a == b]
        diff = [c for c, a, b in pairs if a != b]
        print("   janela %5.1f..%5.1f  %d clusters  (mesma voz: %s)"
              % (t0, t0 + args.window_s, len(vecs),
                 ", ".join("%+.3f" % c for c in same) or "-"))
        rows.extend(same)
        rows.extend(diff)
        # imprime a matriz de coseno com a verdade ao lado
        for i in sorted(vecs):
            for j in sorted(vecs):
                if i < j:
                    print("      local %d(voz %d) x local %d(voz %d) = %+.3f"
                          % (i, truth[i], j, truth[j], cos(vecs[i], vecs[j])))

    if rows:
        rows = np.array(rows)
        print("\n  cosenos de PARES DENTRO de janelas: min %+.3f  max %+.3f  "
              "n=%d" % (float(rows.min()), float(rows.max()), len(rows)))

    # (C) NIVEL SEGMENTO, nao centroide. O bloco [B] compara CENTROIDES de
    # cluster, que sao a media de muitos segmentos -- e uma media borra. A
    # pergunta honesta e' se o METODO falha ou se e' o atalho do centroide que
    # falha, e so se responde a esta: embedding POR SEGMENTO, do mesmo diarizador
    # de uma passagem so, com a verdade ao lado.
    print("\n[C] EMBEDDING POR SEGMENTO (sem centr):")
    vecs, labs_ = [], []
    for s, e, l in ref:
        v = embed(ex, audio[int(s * S.DEFAULT_RATE):int(e * S.DEFAULT_RATE)])
        if v is not None:
            vecs.append(v)
            labs_.append(l)
    same, diff = [], []
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            c = cos(vecs[i], vecs[j])
            (same if labs_[i] == labs_[j] else diff).append(c)
    print("   MESMA pessoa  : n=%2d  min %+.3f  max %+.3f  mediana %+.3f"
          % (len(same), min(same), max(same), float(np.median(same))))
    print("   PESSOAS DIFERENTES: n=%2d  min %+.3f  max %+.3f  mediana %+.3f"
          % (len(diff), min(diff), max(diff), float(np.median(diff))))
    if same and diff:
        gap = min(same) - max(diff)
        separates = gap > 0
        print("   SEPARACAO: min(mesma)=%+.3f  max(diferente)=%+.3f  folga %+.3f"
              % (min(same), max(diff), gap))
        if separates:
            print("   VEREDITO: SEPARA. O unico limiar com folga e' qualquer valor "
                  "em (%.3f, %.3f), e o meio e' %.3f."
                  % (max(diff), min(same), (max(diff) + min(same)) / 2.0))
        else:
            # A primeira versao desta linha imprimia "limiar viavel: qualquer
            # valor em (%.3f, %.3f)" com max(diferente) > min(mesma) -- ou seja,
            # um intervalo VAZIO apresentado como uma opcao. Um numero que se
            # le como caminho quando nao e' caminho e' pior do que nao imprimir.
            print("   VEREDITO: NAO SEPARA. min(mesma)=%+.3f esta ABAIXO de "
                  "max(diferente)=%+.3f: o intervalo de um limiar seria "
                  "(%.3f, %.3f), que esta VAZIO."
                  % (min(same), max(diff), max(diff), min(same)))
            print("   Ou seja: NAO EXISTE limiar de coseno que funcione neste "
                  "audio com este modelo. O clustering global do pyannote por "
                  "similaridade e' uma via MEDIDA como impraticavel aqui.")

    print("\nVERDICT: isto NAO fixa um limiar. E' a distribuicao; o limiar vem "
          "depois de ver SAME vs DIFFERENT separados, e nao de um numero encontrado "
          "numa pagina.")
    return 0


if __name__ == "__main__":
    sys.exit(main())