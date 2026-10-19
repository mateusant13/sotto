"""FASE A -- o detector BARATO de "ha mais de uma voz?".

O QUE O DONO DECIDIU (2026-10-18)
---------------------------------
*"se em tempo real for pesado para o usuario separar as vozes, devemos fazer isso
depois apenas. mas precisamos detectar que sao multiplas vozes, para decidir isso
pra processar depois quando e seguro e nao travar o pc do usuario."*

A MEDICA QUE JA DEU CONTRA O DESENHO EM TEMPO REAL
---------------------------------------------------
RSS do sidecar com o modelo real: **207 MB em regime**, ~1,5 nucleos. E a
sobreposicao de janelas -- que faz cada segundo de audio ser diarizado duas
vezes -- e' a que sustenta a identidade: passo 10 s da **2 slots**, passo 20 s da
**4 slots** para as mesmas 2 pessoas.

POR QUE A FASE A E' BARATA, E O QUE ESTE INSTRUMENTO MEDE
---------------------------------------------------------
A Fase A nao pergunta QUEM E' QUEM. Pergunta **HOUVE DUAS VOZES AO MESMO TEMPO**.
E essa pergunta e' uma propriedade do modelo de **segmentacao** (5,7 MB), que nao
precisa do modelo de **embeddings** (37,8 MB), nem de clustering, nem de
identidade entre janelas -- logo nao precisa da sobreposicao, que e' o que custa.

CORRECAO 2026-10-18 -- O INPUT NAO E' FBANK. E' A ONDA CRUA.
-----------------------------------------------------------
A primeira versao deste probe calculava um fbank Kaldi em Python e alimentava o
modelo. Todas as tentativas de forma falharam (`Invalid input shape: {80}`,
`invalid dimensions for input: x`). O grafo ONNX diz porquê:

    input  x: [N, 1, T]                      <- T = AMOSTRAS a 16 kHz
      /sincnet/wav_norm1d/InstanceNormalization
      /sincnet/conv1d.0/Conv     filtros [80, 1, 251], stride 10
      /sincnet/Abs                          -> [N, 80, floor(T/10-251/10)+1]
      /sincnet/pool1d.0/MaxPool   stride 3  -> [N, 80, .../3...]
      /sincnet/norm1d.0/InstanceNormalization
      /sincnet/LeakyRelu                   -> primeiro Conv profundo
    output y: [N, frames, 7]                   7 classes powerset

O **filterbank e' a primeira camada do proprio modelo** (SincNet). Nao ha fbank
para calcular em Python, e portanto o blocker "provar que o meu fbank e' igual ao
do C++ do sherpa" **deixa de existir** -- o unico consumidor do audio e' o proprio
modelo. Instrumento: `I:\\cc-tmp\\trace-x.py`, 50 nos, 153 value_info.

O QUE ESTE PORTAO FAZ
---------------------
  1. corre `model.onnx` sobre a onda crua;
  2. mede QUANTO CUSTA (o numero que decide a Fase A);
  3. deriva a frames->segundo por via ANALITICA e confere-a com a observada;
  4. imprime qual das 7 classes powerset ganha em cada frame, e durante quanto;
  5. CRUZA com o que a pipeline COMPLETA (sherpa, com embeddings) ja mediu no
     mesmo audio -- 2 vozes, 2,5 s de fala sobreposta.

Se o detector disser "nunca houve duas vozes" onde a pipeline completa mediu
sobreposicao, ele esta ERRADO -- e diz-se.
"""
import argparse
import os
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                    # noqa: E402

import speaker_sidecar as S           # noqa: E402

SEG_MODEL = os.path.join(S.REPO, "_main", "diar-models",
                         "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx")
FS = 16000

# 1 frame = 270 amostras = 16,875 ms.
#
# DERIVACAO ARQUITECTURAL, nao transcricao do grafo: o sinc conv do SincNet
# corre com stride 10, e depois ha TRES MaxPool de stride 3. Logo cada frame
# avanca 10 * 3 * 3 * 3 = 270 amostras. O output declarado pelo grafo
#     y: [N, floor(floor(floor(floor(T/10 - 251/10)/3 - 2/3)/3)/3 - 8/3) + 1, 7]
# e' a versao com edges desta mesma razao -- mas transcreve-la em Python exige
# adivinhar a precisao com que o runtime avalia cada `floor`, e adivinhar mal da
# um off-by-one que parece uma divergencia e nao e'. MEDIDO: as tres variacoes
# (float64, float32, float64+epsilon) erram +1 em 4 de 7 comprimentos
# (`I:\\cc-tmp\\frame-formula.py`). Por isso o mapa frame->tempo vem da
# arquitectura e e' conferido contra 7 comprimentos medidos, não de uma formula.
MS_PER_FRAME = 1000.0 * 270 / FS


def read_wav(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise SystemExit("WAV de %d bytes/amostra -- este leitor so faz 16 bit"
                             % w.getsampwidth() * 8)
        raw = w.readframes(w.getnframes())
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fase A: powerset sobre a onda crua")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--window-s", type=float, default=0.0,
                    help="se >0, mede o custo por janela deste tamanho")
    ap.add_argument("--skip-cross", action="store_true",
                    help="nao chama a pipeline completa do sherpa")
    args = ap.parse_args(argv)

    import onnxruntime                                  # noqa: PLC0415

    audio = read_wav(args.audio)
    dur = len(audio) / float(FS)
    print("audio %.1f s   modelo de segmentacao %.2f MB"
          % (dur, os.path.getsize(SEG_MODEL) / 1048576.0))

    opts = onnxruntime.SessionOptions()
    opts.log_severity_level = 3
    opts.intra_op_num_threads = args.threads
    sess = onnxruntime.InferenceSession(SEG_MODEL, opts)
    print("inputs : %s" % [(i.name, i.shape) for i in sess.get_inputs()])
    print("outputs: %s" % [(o.name, o.shape) for o in sess.get_outputs()])

    # ---- 1. corre sobre a onda CRUA -----------------------------------------
    t0 = time.perf_counter()
    out = sess.run(None, {"x": audio[None, None, :]})[0]
    warm = time.perf_counter() - t0
    print("\nsaida y: %s   (corrida %.2f s para %.1f s de audio)"
          % (out.shape, warm, dur))

    frames = out.shape[1]
    ms_per_frame = dur * 1000.0 / max(1, frames)
    print("frames %d  |  1 frame medida = %.4f ms  |  arquitectura = %.4f ms "
          "|  desvio %+.4f ms (%.1f frame em %d)"
          % (frames, ms_per_frame, MS_PER_FRAME,
             ms_per_frame - MS_PER_FRAME,
             (ms_per_frame - MS_PER_FRAME) / MS_PER_FRAME, frames))
    print("   o desvio vem das bordas (campo receptivo ~1230 amostras), nao do "
          "passo: passo = 1/%.2f frames/s" % (1000.0 / ms_per_frame))
    ms_per_frame = MS_PER_FRAME      # a partir daqui, o mapa arquitectural

    # ---- 2. QUANTO CUSTA -- o numero que decide a Fase A --------------------
    if args.window_s > 0:
        n = int(round(args.window_s * FS))
        wav = np.ascontiguousarray(audio[:n])[None, None, :]
        sess.run(None, {"x": wav})                        # aquece
        reps = 5
        t0 = time.perf_counter()
        for _ in range(reps):
            sess.run(None, {"x": wav})
        per = (time.perf_counter() - t0) / reps
        print("\nCUSTO por janela de %.0f s: %.1f ms de CPU  (RTF %.4f)"
              % (args.window_s, per * 1000.0, per / args.window_s))
        print("   1 h de audio = %.0f s de CPU;  o dobro (sobreposicao) = %.0f s"
              % (per * 3600, per * 2 * 3600))

    # ---- 3. as 7 classes powerset -------------------------------------------
    win = out[0].argmax(axis=1)
    counts = {int(c): int((win == c).sum()) for c in range(out.shape[2])}
    print("\nclasses que ganham (de %d frames):" % frames)
    for c, k in sorted(counts.items()):
        print("   classe %d: %5d frames  (%.2f s)" % (c, k, k * ms_per_frame / 1000.0))

    if args.skip_cross:
        print("\n(--skip-cross: sem VERDADE-TERRA da pipeline completa)")
        return 0

    # ---- 4. CRUZAMENTO com o que a pipeline COMPLETA mediu ------------------
    # `call.wav`: 2 vozes, 15 segmentos, 47,3 s de fala, **2,5 s sobrepostos**.
    ref = [(float(s.start), float(s.end), int(s.speaker))
           for s in S._load_sherpa_diarizer(
               S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL, threads=args.threads,
               threshold=0.9).process(audio).sort_by_start_time()]
    overlaps = 0.0
    spans = []
    for i in range(len(ref)):
        for j in range(i + 1, len(ref)):
            lo = max(ref[i][0], ref[j][0])
            hi = min(ref[i][1], ref[j][1])
            if hi > lo:
                overlaps += hi - lo
                spans.append((lo, hi))
    print("\nVERDADE-TERRA da pipeline completa (com embeddings):")
    print("   vozes %d, segmentos %d, fala sobreposta %.1f s"
          % (len({l for _, _, l in ref}), len(ref), overlaps))

    if not spans:
        print("   este audio nao tem sobreposicao -- nao ha com que comparar")
        return 0

    idx = np.zeros(frames, dtype=bool)
    for lo, hi in spans:
        i0, i1 = int(lo / (ms_per_frame / 1000.0)), int(hi / (ms_per_frame / 1000.0))
        idx[max(0, i0):min(frames, i1)] = True
    in_ov = win[idx]
    out_ov = win[~idx]
    ci = np.bincount(in_ov, minlength=out.shape[2])
    co = np.bincount(out_ov, minlength=out.shape[2])
    top_in = int(ci.argmax()) if in_ov.size else -1
    top_out = int(co.argmax()) if out_ov.size else -1
    print("   classe que domina DENTRO da sobreposicao : %d (%d frames)"
          % (top_in, in_ov.size))
    print("   classe que domina FORA da sobreposicao   : %d (%d frames)"
          % (top_out, out_ov.size))
    print("   Inside : %s" % {int(c): int(v) for c, v in enumerate(ci) if v})
    print("   Outside: %s" % {int(c): int(v) for c, v in enumerate(co) if v})
    print("\n   %s" % ("DISTINTAS -- o detector tem sinal onde ha duas vozes"
                      if top_in != top_out else
                      "IDENTICAS -- o detector NAO distingue; a Fase A "
                      "como esta, nao serve"))
    return 0


if __name__ == "__main__":
    sys.exit(main())