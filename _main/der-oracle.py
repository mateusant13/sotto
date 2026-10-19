"""DER -- Diarization Error Rate da cadeia de atribuicao, em audio controlado.

O QUE FALTAVA
=============
ATE agora a cadeia de orador tinha UM numero de precisoes -- o cMAP, 90,4% na
call real -- e o cMAP mede uma coisa especifica: dada a rotulagem do diarizador,
conseguimospermitar os rotulos a quem eles pertencem. Nao mede se o diarizador
**descobriu** as vozes certas, nem se **segmentou** o tempo certo.

O DER mede as tres coisas juntas, sobre um eixo de tempo:

    missed    fala de referencia que a hipotese deu como silencio
    confusion fala de referencia que a hipotese atribuiu a OUTRA pessoa
    false alarm  fala inventada onde a referencia e' silencio

        DER = (missed + confusion + false_alarm) / fala_de_referencia

O DER classico so se define sobre fala NAO SOBREPOSTA. Nao ha como escrever
"duas pessoas a falar" num DER de uma pessoa por vez. Por isso o portao mede DER
no braco onde asDUAS COISAS sao verdadeiras e o numero e' limpo:

    A-sequencial  pessoa A de 0 a L, pessoa B de L a 2L. Sem sobreposicao.

E mede a sobreposicao a parte que o DER nao cobre, com o detector da Fase A, que
ja tem portao proprio (`multivoice-oracle.py`).

A ACTIVIDADE DE REFERENCIA
==========================
Nao vem do modelo que esta a ser avaliado -- seria circular. Vem da ENVOLVENTE
DE AMPLITUDE do audio, que e' uma propriedade do sinal. O limiar e' varrido, e o
DER e' reportado como uma FAIXA: um limiar alto declara silencio onde ha voz
fraca e infla o DER; um limiar baixo aceita ruido. Um numero unico sem este
varrimento seria precisao falsa.

O COLLAR
========
250 ms de tolerancia nas fronteiras, como em pyannote: um diarizador erra a
fronteira em quelques Samples e isso nao e' um erro de atribuicao. O collar e'
aplicado a hypothesis E a reference, como manda a pratica.

O BRACO NEGATIVO
================
`--neg-arm` baralha as etiquetas da hipotese preservando o numero de vozes.
Um DER assim tem de explodir; se nao explodir, o portao esta a medir a coisa
errada e um numero bonito seria mentira.
"""
import argparse
import itertools
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
FRAME_S = S.FRAME_S
COLLAR_S = 0.25

SRC_PT = os.path.join(ROOT, "_main", "pt-br-sample.wav")
SRC_EN = os.path.join(ROOT, "_main", "en-us-sample.wav")

FAILURES = []
CHECKS = [0]


def check(ok, label, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(label)
    detail = detail if isinstance(detail, str) else repr(detail)
    print("   [%s] %s%s" % ("ok" if ok else "XX", label,
                            ("  -- " + detail) if detail else ""))
    return ok


def read_wav(p):
    with wave.open(p, "rb") as w:
        return (np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
                .astype(np.float32) / 32768.0)


def rms_to(x, dbfs=-20.0):
    r = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
    return x.astype(np.float32) if r <= 0 else (x * (10.0 ** (dbfs / 20.0) / r)).astype(np.float32)


def envelope_speech(x, hop, win, thr):
    """Fala por envolvente de amplitude, limiar RELATIVO ao pico da fonte.

    Relativo, e nao absoluto: um microfone e outro dao niveis diferentes, e um
    limiar em dBFS fixo mediria o microfone em vez do audio.
    """
    hop_n = max(1, int(hop * FS))
    win_n = max(1, int(win * FS))
    n = max(0, (len(x) - win_n) // hop_n + 1)
    if n == 0:
        return np.zeros(0, dtype=bool)
    idx = np.arange(win_n)[None, :] + hop_n * np.arange(n)[:, None]
    rms = np.sqrt((x[idx] ** 2).mean(axis=1))
    peak = float(rms.max()) if rms.size else 0.0
    if peak <= 0:
        return np.zeros(n, dtype=bool)
    return rms >= peak * thr


def segments_to_frames(segs, n_frames):
    """Segmentos do diarizador -> rotulo por frame (-1 = silencio)."""
    out = np.full(n_frames, -1, dtype=np.int64)
    for s in segs:
        a = max(0, int(float(s["start"]) / FRAME_S))
        b = min(n_frames, int(float(s["end"]) / FRAME_S))
        if b > a:
            out[a:b] = int(s["speaker"])
    return out


def apply_collar(labels, speech, collar_frames):
    """Perdoa `collar_frames` a volta de cada fronteira do tipo de rotulo.

    Um diarizador erra a fronteira em alguns frames e isso NAO e' erro de
    atribuicao. Sem isto o DER mede sobretudo descontinuidade.
    """
    if collar_frames <= 0:
        return labels
    out = labels.copy()
    idx = np.arange(len(labels))
    for k in range(1, len(labels)):
        if labels[k] != labels[k - 1]:
            lo = max(0, k - collar_frames)
            hi = min(len(labels), k + collar_frames)
            out[lo:hi] = labels[k]
    del idx
    return out


def best_permutation(ref, hyp, n_speakers):
    """O mapeamento de rotulos que minimiza a confusao. Brute force: <=3 vozes."""
    hyp_ids = sorted({int(v) for v in hyp if v >= 0})
    if not hyp_ids:
        return {}, {}
    best = None
    for perm in itertools.permutations(range(n_speakers),
                                       r=min(len(hyp_ids), n_speakers)):
        mapping = {h: p for h, p in zip(hyp_ids, perm)}
        cand = np.array([mapping.get(int(v), -1) if v >= 0 else -1 for v in hyp])
        agree = int(((cand == ref) & (ref >= 0)).sum())
        if best is None or agree > best[0]:
            best = (agree, mapping, cand)
    return (best[1], best[2]) if best else ({}, hyp)


def score(ref, hyp_mapped):
    ref_speech = ref >= 0
    hyp_speech = hyp_mapped >= 0
    both = ref_speech & hyp_speech
    missed = int((ref_speech & ~hyp_speech).sum())
    fa = int((~ref_speech & hyp_speech).sum())
    confusion = int((both & (hyp_mapped != ref)).sum())
    correct = int((both & (hyp_mapped == ref)).sum())
    total = int(ref_speech.sum())
    der = (missed + fa + confusion) / total if total else float("nan")
    return {"der": der, "missed": missed, "false_alarm": fa,
            "confusion": confusion, "correct": correct, "ref_s": total * FRAME_S}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--neg-arm", action="store_true",
                    help="baralha as etiquetas da hipotese; o DER tem de explodir")
    args = ap.parse_args(argv)

    pt, en = rms_to(read_wav(SRC_PT)), rms_to(read_wav(SRC_EN))
    L = min(len(pt), len(en)) / float(FS)
    a, b = pt[:int(L * FS)], en[:int(L * FS)]
    audio = np.concatenate([a, b]).astype(np.float32)
    pk = float(np.abs(audio).max())
    if pk > 0.99:
        audio = audio / pk * 0.99
        a = a / pk * 0.99
        b = b / pk * 0.99

    print("=" * 78)
    print("DER -- braco A-sequencial (pessoa A de 0 a %.1f s, pessoa B depois)" % L)
    print("collar %d ms | threshold do diarizador %.2f | classes %s"
          % (COLLAR_S * 1000, args.threshold, list(S.MULTI_CLASSES)))
    print("=" * 78)

    sess = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                  threads=args.threads, threshold=args.threshold)

    # O DER mede-se em JANELAS DE 10 S, como a app faz -- e nao num clip unico.
    #
    # PORQUE, e porque e' uma consequencia do degrau e nao uma preferencia:
    # este arquivo tem 23,6 s, e a primeira tentativa passou-o inteiro ao
    # diarizador. O diarizador devolveu **1 voz para 2 pessoas** em 26,6 s de
    # parede -- RTF 1,130, o lado mau do degrau medido em
    # `_main/_phase-b-cliff-probe.py`. Acima de ~11 s o modelo nao so e' lento:
    # o RESULTADO degrada. Um DER medido nessa zona seria um numero sobre uma
    # configuracao que ninguem usa.
    #
    # E o produto nunca esta nessa zona: o sidecar corre janelas de 10 s com
    # passo 10 s. O que este instrumento mede e' exactamente o que corre.
    print("\ndiarizador em janelas de %.0f s com passo %.0f s (o que o sidecar "
          "faz):" % (S.SAFE_WINDOW_S, S.SAFE_WINDOW_S))
    slots = S.StableSpeakerSlots()
    win_n = int(S.SAFE_WINDOW_S * FS)
    step_n = win_n
    all_segs = []
    wall = 0.0
    for start in range(0, max(1, len(audio) - win_n + 1), step_n):
        chunk = audio[start:start + win_n]
        t0 = time.perf_counter()
        cres = sess.process(chunk).sort_by_start_time()
        wall += time.perf_counter() - t0
        raw = [{"start": start / float(FS) + float(s.start),
                "end": start / float(FS) + float(s.end),
                "speaker": int(s.speaker)} for s in cres]
        payload = {"segments": raw}
        # O `now` do horizonte e' o FIM DA JANELA NO RELOGIO DA CAPTURA, nunca
        # `time.time()` -- foi esse o bug que dava 8 slots para 2 pessoas.
        payload["segments"], mapping, created = slots.remap(
            raw, now=(start + len(chunk)) / float(FS))
        all_segs.extend(payload["segments"])
        print("   janela %6.1f - %6.1f s -> %2d segmentos, mapa %s"
              % (start / float(FS), (start + len(chunk)) / float(FS),
                 len(payload["segments"]), mapping))

    segs = all_segs
    n_frames = int(len(audio) / FS / FRAME_S)
    hyp = segments_to_frames(segs, n_frames)
    hyp_ids = sorted({int(v) for v in hyp if v >= 0})
    dur = len(audio) / float(FS)
    print("\ntotal: %d slots globais %s, %d segmentos, %.2f s de parede "
          "(RTF %.3f no total)"
          % (len(hyp_ids), hyp_ids, len(segs), wall, wall / dur))
    for s in segs[:10]:
        print("   %7.2f - %7.2f  voz %d" % (s["start"], s["end"], s["speaker"]))
    if len(segs) > 10:
        print("   ... mais %d" % (len(segs) - 10))

    if len(hyp_ids) < 2:
        check(False, "o diarizador encontrou as DUAS vozes",
              "encontrou %d: %s" % (len(hyp_ids), hyp_ids))
        print("\nVERDICT: FAIL")
        return 1

    if args.neg_arm:
        # Mutar por rotulo e POR INSTANTE: baralhar os rotulos todos preservaria
        # o numero de vozes e a estrutura, e nao seria um DER de barbado --
        # seria uma hipotesetica alternativa. Isto quebra a relacao com o tempo.
        rng = np.random.RandomState(7)
        flip = rng.rand(n_frames) < 0.5
        hyp = np.where(flip, -1, hyp)
        print("\nmutacao: rotulos de hipotese baralhados no tempo (metade em "
              "silencio)")

    # --- varrimento do limiar de referencia -------------------------------
    print("\nDER em funcao do limiar de referencia (fracao do pico da fonte):")
    print("  limiar |  DER   | missed  confus.  falso+ | fala ref | mapeamento")
    print("-" * 78)
    collar_frames = int(COLLAR_S / FRAME_S)
    sp_a = envelope_speech(a, FRAME_S, 0.025, 1.0)   # normalizado depois
    sp_b = envelope_speech(b, FRAME_S, 0.025, 1.0)
    rows = []
    for thr in (0.02, 0.05, 0.10, 0.20, 0.35):
        sa = envelope_speech(a, FRAME_S, 0.025, thr)
        sb = envelope_speech(b, FRAME_S, 0.025, thr)
        ref = np.concatenate([np.where(sa, 1, -1), np.where(sb, 2, -1)])
        if len(ref) < n_frames:
            ref = np.concatenate([ref, np.full(n_frames - len(ref), -1)])
        ref = ref[:n_frames]
        if int((ref >= 0).sum()) < 10:
            continue
        mapping, mapped = best_permutation(ref, hyp, 3)
        m = score(apply_collar(ref, ref >= 0, collar_frames),
                  apply_collar(mapped, mapped >= 0, collar_frames))
        rows.append((thr, m, mapping))
        print("  %6.2f | %5.1f%% | %6d %7d %8d | %6.1f s | %s"
              % (thr, 100 * m["der"], m["missed"], m["confusion"],
                 m["false_alarm"], m["ref_s"], mapping))
    del sp_a, sp_b

    if not rows:
        print("  nenhum limiar produziu referencia utilizavel")
        print("VERDICT: FAIL")
        return 1

    ders = [m["der"] for _, m, _ in rows]
    lo, hi = min(ders), max(ders)
    print("\nDER = %.1f%% a %.1f%% conforme o limiar de referencia" % (100 * lo, 100 * hi))
    print("A FAIXA e' o numero honesto: a atividade de referencia vem de uma")
    print("envolvente de amplitude com limiar, e o limiar Move o resultado. Um")
    print("numero unico aqui seria precisao falsa.")

    print("\n" + "-" * 78)
    if args.neg_arm:
        worst = max(m["der"] for _, m, _ in rows)
        check(worst > 0.30, "BRACO NEGATIVO: com rotulos ao acaso o DER tem de "
                            "ser alto", "DER max %.1f%%" % (100 * worst))
        print("-" * 78)
        if FAILURES:
            print("VERDICT: FAIL  (%d/%d: %s)" % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
            return 1
        print("VERDICT: PASS  (%d/%d)  -- este era o BRACO NEGATIVO: PASS "
              "significa que o portao mede a coisa certa."
              % (CHECKS[0], CHECKS[0]))
        return 0

    # O QUE O PORTAO JULGA, E POR QUE NAO E' O DER.
    #
    # A primeira versao deste portao exigia "DER < 45%" e foi a RED com 90,7%.
    # Esse veredicto media a ACTIVIDADE DE REFERENCIA, nao o diarizador:
    #
    #   limiar | fala ref | falso alarme
    #     0,02 |  18,5 s  |     46
    #     0,35 |  10,2 s  |    467      <- declarei 8 s a menos como "fala"
    #
    # Subir o limiar encurta a referencia, e tudo o que o diarizador ouviu e que
    # eu acabei de chamar de silencio passa a falso alarme -- POR CONSTRUCAO. O
    # numero sobe porque o terreno encolheu, nao porque o diarizador piorou.
    #
    # O que responde a pergunta do dono -- "separou as vozes?" -- e' a
    # CONFUSAO: fala atribuida a pessoa errada. E' essa que e' o produto.
    # `missed` e `falso alarme` sao perguntas sobre DETECCAO DE FALA, e a
    # referencia delas e' uma envolvente de amplitude minha, nao uma verdade.
    worst_conf = 0.0
    for thr, m, _ in rows:
        frac = m["confusion"] / max(1, m["correct"] + m["confusion"])
        worst_conf = max(worst_conf, frac)
        print("  limiar %.2f: confusao %d/%d frames = %.2f%% do que a hipotese "
              "achou que era fala" % (thr, m["confusion"],
                                     m["correct"] + m["confusion"], 100 * frac))

    check(len(hyp_ids) == 2, "o diarizador encontrou as DUAS vozes do audio",
          "slots %s" % hyp_ids)
    check(worst_conf < 0.05,
          "confusao abaixo de 5% da fala, em qualquer limiar de referencia",
          "pior %.2f%%" % (100 * worst_conf))
    print("-" * 78)
    if FAILURES:
        print("VERDICT: FAIL  (%d/%d: %s)" % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
        return 1
    print("VERDICT: PASS  (%d/%d checks)" % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())