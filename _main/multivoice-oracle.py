"""FASE A -- PORTAO do detector de multiplas vozes.

O QUE ESTE PORTAO PROVA, E O QUE ELE NAO PROVA
==============================================
O dono pediu (2026-10-18): *"precisamos detectar que sao multiplas vozes, pra
decidir isso pra processar depois quando e seguro e nao travar o pc do usuario."*

Este portao responde a **uma** pergunta: a classe powerset que significa
"duas ou mais vozes ao mesmo tempo" e' detectavel com precisao suficiente para
disparar um sinal?

O QUE ESTE PORTAO NAO FAZ
-------------------------
Nao atribui nomes, nao mantem identidade entre janelas, e nao mede DER. Mede
APENAS: "aqui havia duas vozes ao mesmo tempo, sim ou nao".

A VERDADE E' CONSTRUIDA, NAO INFERIDA
-------------------------------------
Nos clips `call*.wav` a verdade vem da pipeline completa (sherpa + embeddings) --
mesma familia de modelo que a Fase A quer substituir. Em `call180.wav` essa
pipeline deu **6 vozes para 2 pessoas**, ou seja, a verdade la e' suspecta.

Aqui a verdade e' **exacta por construcao**: dois clips de voz unica sao
misturados com deslocamentos conhecidos, e a mascara de sobreposicao e' a soma
literal dos deslocamentos. Nao ha inferencia, nao ha rotulo humano, nao ha
circularidade com a pipeline.

PRECONDICOES MEDIDAS, NAO ASSUMIDAS
-----------------------------------
Um portao sobre "duas pessoas" so vale se os clips forem mesmo de uma pessoa
so, e se as duas fontes forem mesmo pessoas diferentes. As tres sao MEDIDAS com a
pipeline completa antes de qualquer veredicto:

  P1  cada fonte sozinha        -> a pipeline diz 1 voz
  P2  as duas em SEQUENCIAL     -> a pipeline diz 2 vozes   (sao pessoas distintas)
  P3  a mesma fonte em DUAS CAMADAS -> a pipeline diz 1 voz   (um so orador)

P3 e' o contra-teste que torna o detector honesto: se a classe de duas vozes
disparar quando a MESMA pessoa fala duas vezes, entao ela mede volume, nao
pessoas, e o portao tem de reprovar.

O BRACO NEGATIVO
----------------
`--neg-arm` troca a classe testada por uma classe errada e exige que o
veredicto INVERTA. Um portao que nao sabe dizer NAO nao e' um portao.
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
import onnxruntime                      # noqa: E402

import speaker_sidecar as S              # noqa: E402

SEG_MODEL = os.path.join(S.REPO, "_main", "diar-models",
                         "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx")
FS = 16000
MS_PER_FRAME = 1000.0 * 270 / FS        # stride 10 do sinc conv x 3^3

SRC_PT = os.path.join(ROOT, "_main", "pt-br-sample.wav")     # 20,7 s, 1 voz
SRC_EN = os.path.join(ROOT, "_main", "en-us-sample.wav")     # 11,8 s, 1 voz

# AS 7 CLASSES PODERSET: 1 + 3 + 3, deduzido das distribuicoes medidas.
#
#   0        ninguem
#   1 2 3    UMA voz, em tres slots distintos
#   4 5 6    DUAS vozes simultaneas, em tres combinacoes de slots
#
# DEDUCAO, NAO ASSUNCAO -- cada linha e' uma distribuicao medida:
#   pt-br sozinha (1 voz) : {0:143, 2:1079}          -> so 0 e 2
#   en-us sozinho (1 voz) : {0:161, 2:534}           -> so 0 e 2
#   s5-stem0/1 (nao fala) : {0:3552}                 -> so 0
#   0-four-spk-zh (4 vozes, sobreposicao medida = 0 s): {0,1,2,3} -> NENHUMA de 4/5/6
#   call.wav   (2 vozes, 2,5 s de sobreposicao):      {0,2,3, 6:118} e as 118 caem DENTRO
#   call180.wav (2 vozes):                             {0,1,2,3, 6:15}  e as 15 caem DENTRO
#
# O clip de 4 vozes e' a LEITURA CRUCIAL: quatro pessoas, 16,5 s de fala, e ZERO
# frames de 4/5/6 -- porque nao ha sobreposicao. Se 4/5/6 fossem "muita gente a
# falar", teriam disparado la.
MULTI_CLASSES = (4, 5, 6)
SINGLE_CLASSES = (1, 2, 3)

# A classe usada pelo --neg-arm: domina o audio de UMA voz.
WRONG_CLASSES = (2,)

ARM = [""]
FAILURES = []
CHECKS = [0]


def set_arm(name):
    """O braço precisa de ser uma lista mutavel em scope de modulo.

    Um `arm = "mutante"` local dentro de `main()` e' um mutante INERTE: o
    `--neg-arm` contaria zero e o portao passaria sem exercitar nada.
    """
    ARM[0] = name


def check(ok, label, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(label)
    print("   [%s] %s%s" % ("ok" if ok else "XX", label,
                            ("  -- " + detail) if detail else ""))
    return ok


def read_wav(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise SystemExit("%s: so leio WAV de 16 bit" % path)
        return (np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
                .astype(np.float32) / 32768.0)


def rms_to(x, dbfs=-20.0):
    """Nivela por RMS, para que a mistura nao seja vencida por uma das vozes."""
    r = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
    if r <= 0:
        return x.astype(np.float32)
    return (x * (10.0 ** (dbfs / 20.0) / r)).astype(np.float32)


def mix(parts, total_s):
    """parts = [(audio, offset_s)] -> (audio, cobertura por amostra).

    A cobertura conta QUANTAS fontes falam em cada amostra. Sobreposicao e'
    cobertura >= 2. Usar "alguma fonte" daria a mascara ERRADA -- foi
    exactamente o que a primeira versao fez, e por isso reportou 23,5 s de
    sobreposicao num braco que, por construcao, tem zero.
    """
    n = int(round(total_s * FS))
    out = np.zeros(n, dtype=np.float32)
    cover = np.zeros(n, dtype=np.int16)
    for x, off in parts:
        a = int(round(off * FS))
        b = min(n, a + len(x))
        if b > a:
            out[a:b] += x[: b - a]
            cover[a:b] += 1
    return out, cover


def run_seg(sess, audio):
    t0 = time.perf_counter()
    out = sess.run(None, {"x": np.ascontiguousarray(audio)[None, None, :]})[0]
    return out[0].argmax(axis=1), time.perf_counter() - t0


def run_full(audio, threads, threshold=0.9):
    seg = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                  threads=threads, threshold=threshold)
    t0 = time.perf_counter()
    res = seg.process(audio).sort_by_start_time()
    el = time.perf_counter() - t0
    rows = [(float(s.start), float(s.end), int(s.speaker)) for s in res]
    return rows, len({l for _, _, l in rows}), el


def frames_of(cover, n_frames):
    """Cobertura por amostra -> "duas ou mais vozes" por frame do modelo."""
    step = FS * MS_PER_FRAME / 1000.0
    fm = np.zeros(n_frames, dtype=bool)
    i = 0
    while i < n_frames and i * step < len(cover):
        fm[i] = (cover[int(i * step):int((i + 1) * step)] >= 2).any()
        i += 1
    return fm


def score(pred_multivoice, truth):
    """precision / recall / F1 de 'havia >=2 vozes' por frame."""
    tp = int((pred_multivoice & truth).sum())
    fp = int((pred_multivoice & ~truth).sum())
    fn = int((~pred_multivoice & truth).sum())
    p = tp / float(tp + fp) if (tp + fp) else 0.0
    r = tp / float(tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1, tp, fp, fn


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--neg-arm", action="store_true",
                    help="usa a classe ERRADA; o veredicto tem de inverter")
    ap.add_argument("--json", default="")
    args = ap.parse_args(argv)

    set_arm("--neg-arm" if args.neg_arm else "")
    classes = WRONG_CLASSES if ARM[0] == "--neg-arm" else MULTI_CLASSES
    print("=" * 78)
    print("FASE A -- portao do detector de multiplas vozes")
    print("classes powerset em teste: %s%s"
          % (list(classes), "   (BRACO NEGATIVO -- tem de reprovar)"
             if classes == WRONG_CLASSES else ""))
    print("  0 = ninguem | 1,2,3 = UMA voz (3 slots) | 4,5,6 = DUAS vozes (3 pares)")
    print("1 frame = %.3f ms" % MS_PER_FRAME)
    print("=" * 78)

    o = onnxruntime.SessionOptions()
    o.log_severity_level = 3
    o.intra_op_num_threads = args.threads
    sess = onnxruntime.InferenceSession(SEG_MODEL, o)

    pt = rms_to(read_wav(SRC_PT))
    en = rms_to(read_wav(SRC_EN))
    L = min(len(pt), len(en)) / float(FS)          # janela mais curta que as duas

    # ---------------- PRECONDICOES -----------------------------------------
    print("\nPRECONDICOES (medidas com a pipeline completa)")
    for name, x in (("pt-br sozinha", pt), ("en-us sozinho", en)):
        _, spk, _ = run_full(x, args.threads)
        check(spk == 1, "P1 %s -> 1 voz" % name, "a pipeline disse %d" % spk)

    seq, _ = mix([(pt, 0.0), (en, L)], 2 * L)
    _, spk_seq, _ = run_full(seq, args.threads)
    check(spk_seq == 2, "P2 as duas em SEQUENCIAL -> 2 vozes",
          "a pipeline disse %d -- se disse 1, sao a MESMA pessoa e este "
          "portao nao mede duas pessoas" % spk_seq)

    self_mix, _ = mix([(pt[: int(L * FS)], 0.0), (pt[: int(L * FS)], 0.0)], L)
    self_mix = self_mix / np.abs(self_mix).max() * 0.9
    _, spk_self, _ = run_full(self_mix, args.threads)
    check(spk_self == 1, "P3 a mesma voz em DUAS CAMADAS -> 1 voz",
          "a pipeline disse %d" % spk_self)

    # P2 e' a precondicao que decide se o resto vale alguma coisa: sem duas
    # pessoas distintas nao ha "duas vozes" para detectar.
    if "P2 as duas em SEQUENCIAL -> 2 vozes" in FAILURES:
        print("\nPRECONDICAO P2 FALHOU: sem duas pessoas distintas nao ha o que "
              "detectar. O portao NAO se pronuncia.")
        return 3

    # ---------------- BRACOES ------------------------------------------------
    print("\nBRACOES (sobreposicao exacta por construcao)")
    arms = [
        ("A-seq    0%%       ", [(pt[: int(L * FS)], 0.0), (en[: int(L * FS)], L)], 2 * L),
        ("A-metade 50%%      ", [(pt[: int(L * FS)], 0.0), (en[: int(L * FS)], L / 2.0)], int(L * 1.5)),
        ("A-forte  100%%     ", [(pt[: int(L * FS)], 0.0), (en[: int(L * FS)], 0.0)], L),
        ("A-mesma  mesma voz", [(pt[: int(L * FS)], 0.0), (pt[: int(L * FS)], 0.0)], L),
    ]

    rows_out = []
    total_seg_s = total_full_s = total_audio_s = 0.0
    for name, parts, total_s in arms:
        audio, cover = mix(parts, total_s)
        pk = float(np.abs(audio).max()) if audio.size else 0.0
        if pk > 0.99:
            audio = audio / pk * 0.99
        win, seg_s = run_seg(sess, audio)
        truth = frames_of(cover, len(win))
        rows, spk, full_s = run_full(audio, args.threads)
        pred = np.isin(win, classes)
        p, r, f1, tp, fp, fn = score(pred, truth)
        total_seg_s += seg_s
        total_full_s += full_s
        total_audio_s += total_s

        hist = np.bincount(win, minlength=7)
        ovl_s = float(truth.sum()) * MS_PER_FRAME / 1000.0
        fired_s = float(pred.sum()) * MS_PER_FRAME / 1000.0
        rows_out.append({"arm": name.strip(), "speakers": spk,
                         "overlap_s": round(ovl_s, 2),
                         "fired_s": round(fired_s, 2),
                         "precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3),
                         "hist": [int(v) for v in hist]})
        print("\n  %s  dur %.1f s  vozes(medidas) %d" % (name, total_s, spk))
        print("     sobreposicao REAL %.2f s | classes %s dispararam %.2f s"
              % (ovl_s, list(classes), fired_s))
        print("     distribuicao: %s"
              % {i: int(v) for i, v in enumerate(hist) if v})
        if ovl_s > 0:
            print("     precision %.3f  recall %.3f  F1 %.3f   (tp %d fp %d fn %d)"
                  % (p, r, f1, tp, fp, fn))
        else:
            print("     (sem sobreposicao: so interessa NAO disparar, e' o que fez -- %.2f s)"
                  % fired_s)
        print("     so segmentacao %.3f s (RTF %.4f) | pipeline completa %.2f s (RTF %.3f)"
              % (seg_s, seg_s / total_s, full_s, full_s / total_s))

    print("\nCUSTO (soma dos bracos, %.1f s de audio)" % total_audio_s)
    print("   so segmentacao : %.2f s  RTF %.4f" % (total_seg_s, total_seg_s / total_audio_s))
    print("   pipeline completa: %.2f s  RTF %.3f  -> %.0fx mais cara"
          % (total_full_s, total_full_s / total_audio_s,
             total_full_s / total_seg_s if total_seg_s else 0))

    # ---------------- VEREDITO ----------------------------------------------
    print("\n" + "-" * 78)
    by = {r["arm"].split()[0]: r for r in rows_out}
    neg = classes == WRONG_CLASSES

    if not neg:
        # A regra tem de separar os bracos de PESSOAS dos de NAO-pessoas.
        check(by["A-forte"]["overlap_s"] > 5.0,
              "o braco de 100%% TEM sobreposicao a medir",
              "%.2f s -- se for 0, a mistura nao foi construida como pedido"
              % by["A-forte"]["overlap_s"])
        check(by["A-forte"]["fired_s"] > 0.5,
              "duas vozes simultaneas 100%% DISPARA o detector",
              "disparou %.2f s" % by["A-forte"]["fired_s"])
        check(by["A-forte"]["f1"] >= 0.60,
              "F1 na sobreposicao total >= 0,60",
              "F1 %.3f" % by["A-forte"]["f1"])
        check(by["A-metade"]["overlap_s"] > 2.0,
              "o braco de 50%% TEM sobreposicao a medir",
              "%.2f s" % by["A-metade"]["overlap_s"])
        check(by["A-metade"]["fired_s"] > 0.20,
              "sobreposicao de 50%% dispara", "disparou %.2f s" % by["A-metade"]["fired_s"])
        check(by["A-seq"]["fired_s"] <= 0.30,
              "duas vozes em SEQUENCIAL nao dispara", "disparou %.2f s" % by["A-seq"]["fired_s"])
        check(by["A-mesma"]["fired_s"] <= 0.30,
              "a MESMA voz em duas camadas nao dispara",
              "disparou %.2f s" % by["A-mesma"]["fired_s"])
        check(total_seg_s / total_audio_s < 0.05,
              "RTF da Fase A < 0,05 (custa pouco)",
              "RTF %.4f" % (total_seg_s / total_audio_s))
        check(total_full_s / max(1e-9, total_seg_s) >= 10.0,
              "a Fase A e' pelo menos 10x mais barata que a pipeline completa",
              "%.0fx" % (total_full_s / max(1e-9, total_seg_s)))
    else:
        # O braco negativo tem de FALHAR. Se a classe errada passar, o portao
        # esta a comprar a confianca de quem o le, e nao a dar um numero.
        strong = by["A-forte"]["fired_s"] > 0.5 and by["A-forte"]["f1"] >= 0.60
        quiet = by["A-seq"]["fired_s"] <= 0.30 and by["A-mesma"]["fired_s"] <= 0.30
        check(not (strong and quiet),
              "BRACO NEGATIVO: a classe %s tem de falhar a separacao" % list(classes),
              "forte %.2f s (F1 %.3f) vs sequencial %.2f s / mesma voz %.2f s"
              % (by["A-forte"]["fired_s"], by["A-forte"]["f1"],
                 by["A-seq"]["fired_s"], by["A-mesma"]["fired_s"]))

    print("-" * 78)
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"classes_tested": list(classes), "neg_arm": neg,
                       "checks": CHECKS[0], "failures": FAILURES, "arms": rows_out},
                      fh, indent=2, ensure_ascii=False)

    if FAILURES:
        print("VERDICT: FAIL  (%d/%d checks falharam: %s)"
              % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
        return 1
    if neg:
        print("VERDICT: PASS  (%d/%d checks)  -- este era o BRACO NEGATIVO: o "
              "veredicto PASS significa que a classe ERRADA foi rejeitada, e nao "
              "que o detector funciona." % (CHECKS[0], CHECKS[0]))
        return 0
    print("VERDICT: PASS  (%d/%d checks)" % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())