"""Diarizacao de AUDIO REAL DE CALL, com o modelo real, sem o dono a fazer nada.

Porquê este instrumento existe
------------------------------
O sidecar foi medido em janelas curtas e em dois processos juntos, mas nunca
sobre **a gravacao da call do dono**. E a pergunta que importa não é "quantos
segmentos saiu" -- sao **duas**:

  A) Quantas vozes distintas existem no audio real da call?
  B) Quando a janela desliza (os parametros que o sidecar USA), a MESMA voz
     mantem a MESMA etiqueta de uma janela para a seguinte?

(B) e o que parte a tela ao meio. A `source` do painel e a chave; se o
diarizador re-etiqueta a mesma voz a cada janela, uma pessoa vira duas linhas
que nunca se juntam -- e nenhum oráculo com diarizador falso pode ver isso,
porque um diarizador falso e ESTAVEL por construção.

A metrica
----------
`cMAP` (cluster mapping accuracy) sobre a regiao de SOBREPOSICAO entre duas
janelas consecutivas: matriz de confusao(labels_janela_k, labels_janela_k+1),
emparelhamento um-para-um guloso, e depois accao com o mapeamento aplicado.
Rotulos sao arbitrarios por janela -- a janela k pode chamar "a Ana" de 0 e a
k+1 de 1 -- e o emparelhamento e o que separa "muda o numero" de "muda de
pessoa". O alinhamento e obrigatorio, senao o instrumento mede nada.

Nao ha ground truth humano aqui, e isso e dito no relatorio: esta medicao diz
o que a CADENCIA CUSTA, nao a qualidade absoluta. A qualidade absoluta (DER)
precisa de rotulos de uma pessoa -- e e por isso que continua em aberto.

Braco negativo
--------------
`--neg-arm` desloca cada segmento da janela k+1 no TEMPO, preservando a
contagem, as etiquetas e as duracoes: destroi so a correspondencia temporal,
que e exactamente o que a metrica tem de apanhar. Se o cMAP nao cai a RED
neste braco, o cMAP nao mede nada. Ver `_jitter_time` para o mutante que
FALHOU na primeira versao e o que ele diz sobre mutantes decorativos.

`--dump` / `--from-dump`
------------------------
Grava os segmentos para JSON e reusa-os. Cada passage com o modelo custa
~90 s de CPU em 60 s de audio; iterar o mutante sem o pagar foi o que
permitiu descobrir que ele nao media nada.
"""
import argparse
import json
import os
import random
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if os.path.join(ROOT, "worker") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                    # noqa: E402

import speaker_sidecar as S           # noqa: E402  (o modulo vivo)

FRAME_S = 0.5                         # resolucao da comparacao
PASS_CMAP = 0.80                      # abaixo disto: a voz nao sobrevive a janela
#: Abaixo deste numero de frames a voz minoritaria NAO conta como medida.
#: MEDIDO: na primeira gravacao da call a voz menor aparece em 3 frames num unico
#: par de janelas, e o instrumento imprimia "voz menor 100,0 % -- PASS". Com 3
#: frames isso nao e uma medicao, e um numero que sobe porque o denominador e
#: zero. Um porta que passa sem medir o que diz e pior do que nao haver porta.
MIN_MINORITY_FRAMES = 30


def read_wav(path):
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise SystemExit("FAIL: expected 16-bit mono, got %d ch / %d B"
                             % (w.getnchannels(), w.getsampwidth()))
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return x, w.getframerate()


def _merged_duration(spans):
    """Duracao da UNIAO de intervalos.

    A primeira versao somava o overlap de cada par ADJACENTE: com tres vozes
    sobrepostas contava a mesma amostra duas vezes e ainda ignorava o par
    (0,2). `fala - soma_dos_pares` nao e a sobreposta -- e a uniao que e.
    """
    total = 0.0
    cur_s = cur_e = None
    for s, e in sorted(spans):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def seg_rows(result, t0=0.0):
    """[(start_abs, end_abs, label)] a partir do resultado do sherpa."""
    return [(float(s.start) + t0, float(s.end) + t0, int(s.speaker))
            for s in result]


def diarize(sdk, audio, t0=0.0):
    return seg_rows(sdk.process(audio).sort_by_start_time(), t0)


def label_frames(segs, t_from, t_to, step=FRAME_S):
    """Vector de etiquetas por frame de `step` sobre [t_from, t_to).

    A regiao maioritariamente silenciosa fica -1 (sem dono): comparar duas
    janelas em cima de silencio seria dar credito a quem cala.
    """
    n = max(0, int(round((t_to - t_from) / step)))
    frames = np.full(n, -1, dtype=np.int64)
    weight = np.zeros(n, dtype=np.float64)
    for s, e, lab in segs:
        i0 = max(0, int((s - t_from) / step))
        i1 = min(n, int(np.ceil((e - t_from) / step)))
        if i1 <= i0:
            continue
        # o segmento ocupa uma fracao deste frame: pondera
        for i in range(i0, i1):
            ov = min(e, t_from + (i + 1) * step) - max(s, t_from + i * step)
            if ov > 0:
                frames[i] = lab
                weight[i] += ov
    keep = weight > step * 0.5
    return frames, keep


def greedy_match(conf):
    """Emparelhamento 1-para-1 de labels_a -> labels_b pelo maximo de confusao."""
    pairs = sorted(((conf[a][b], a, b) for a in conf for b in conf[a]),
                   key=lambda t: (-t[0], t[1], t[2]))
    ma, mb, out = set(), set(), {}
    for _score, a, b in pairs:
        if a in ma or b in mb:
            continue
        ma.add(a)
        mb.add(b)
        out[a] = b
    return out


def cmap(segs_a, segs_b, ov_from, ov_to):
    """(acordo, n_frames, confusao, mapa, por_cluster) na regiao de sobreposicao.

    MEDIDO, e este return extra e o achado da medicao: o cMAP GLOBAL e'
    dominado pela voz maioritaria. Numa call real uma voz ocupa ~90 % dos
    frames, portanto mesmo com as etiquetas completamente baralhadas o acordo
    global so cai de 90,4 % para 85,4 %. Ou seja: o numero global diz sobretudo
    "a voz grande continua a ser a voz grande" -- que e' facil. O que parte a
    tela ao meio e' a voz PEQUENA deixar de ser a mesma pessoa a cada janela,
    e para isso `por_cluster` mede cada voz separadamente.
    """
    fa, ka = label_frames(segs_a, ov_from, ov_to)
    fb, kb = label_frames(segs_b, ov_from, ov_to)
    both = ka & kb
    if not both.any():
        return None, 0, {}, {}, {}
    xa, xb = fa[both], fb[both]
    conf = {}
    for x, y in zip(xa, xb):
        conf.setdefault(int(x), {}).setdefault(int(y), 0)
        conf[int(x)][int(y)] += 1
    m = greedy_match(conf)
    ok = sum(1 for x, y in zip(xa, xb) if m.get(int(x)) == int(y))
    per = {}
    for a in conf:
        sel = xa == a
        tot = int(sel.sum())
        if not tot:
            continue
        okc = sum(1 for x, y in zip(xa[sel], xb[sel])
                  if m.get(int(x)) == int(y))
        per[a] = (okc / tot, tot)
    return ok / int(xa.size), int(xa.size), conf, m, per


def _jitter_time(segs, seed=0, span_s=1.5, lo=0.0, hi=None):
    """DESTRUI "quem falava QUANDO", preservando tudo o resto.

    MEDIDO, e a primeira versao deste mutante era uma NENHUMA-OPERACAO: ela
    embaralhava a lista e depois a reordenava por `t[0]` -- o campo que ela nao
    tinha tocado --, devolvendo a lista na ordem original. O braco negativo
    imprimiu 90,4 %, exactamente igual ao braco positivo, e teria "passado".
    Segunda vez nesta sessao que um mutante decorativo quase compra um VERDICT
    falso (a primeira foi `(a,b,c)` como operador virgula em `MUTANTS`): um
    mutante decorativo e pior do que nenhum.

    O que esta versao preserva, propositamente, para o cMAP nao o resolver:
      - o numero de segmentos;
      - o numero e o multiconjunto de etiquetas (o cMAP alinha-as de proposito);
      - a duracao de cada segmento.
    O que destroi: a POSICAO de cada segmento dentro da janela -- que e o unico
    sinal de que o cMAP mede, portanto tem de ser ele a cair.
    """
    if not segs:
        return list(segs)
    if hi is None:
        hi = max(e for _, e, _ in segs)
    hi = max(hi, lo)
    r = random.Random(seed)
    out = []
    for s, e, lab in segs:
        d = max(1e-3, e - s)
        new_s = min(max(s + r.uniform(-span_s, span_s), lo), max(lo, hi - d))
        out.append((new_s, new_s + d, lab))
    return sorted(out, key=lambda t: t[0])


def _relabel(segs, seed=0):
    """DESTRUI A IDENTIDADE, preservando contagem, tempos e duracoes.

    MEDIDO: o mutante do TEMPO (`_jitter_time`) sozinho tira so 3,7 pontos
    (90,4 % -> 86,7 %) e o instrumento passa a Guadal. A razao esta no audio e'
    de uma call: uma voz dominante ocupa ~90 % dos frames, portanto deslocar
    turnos dentro da janela volta a atribuir a voz dominante a maioria dos
    frames, e o cMAP mantem-se alto. Perturbar o TEMPO mede a robustez do
    alinhamento; para medir se a metrica apanha a IDENTIDADE errada, a
    identidade e' que tem de ser trocada.
    """
    if not segs:
        return list(segs)
    labels = [l for _, _, l in segs]
    r = random.Random(seed + 977)
    return [(s, e, labels[r.randrange(len(labels))]) for s, e, _ in segs]


MUTANTS = ("time", "label", "both")


def _mutate(segs, mode, seed, span_s, lo, hi):
    if mode == "time":
        return _jitter_time(segs, seed=seed, span_s=span_s, lo=lo, hi=hi)
    if mode == "label":
        return _relabel(segs, seed=seed)
    if mode == "both":
        return _relabel(_jitter_time(segs, seed=seed, span_s=span_s,
                                     lo=lo, hi=hi), seed=seed)
    return list(segs)


def _report_a(ref, dur):
    speakers = sorted({lab for _, _, lab in ref})
    speech = sum(e - s for s, e, _ in ref)
    union = _merged_duration([(s, e) for s, e, _ in ref])
    overlap = max(0.0, speech - union)
    print("  vozes distintas : %d  -> %s" % (len(speakers), speakers))
    print("  segmentos      : %d" % len(ref))
    print("  fala           : %.1f s de %.1f s (%.0f%%)"
          % (speech, dur, 100.0 * speech / dur))
    print("  sobreposta     : %.1f s (%.0f%% da fala) -- gente a falar por cima"
          % (overlap, 100.0 * overlap / max(speech, 1e-9)))
    durs = sorted(e - s for s, e, _ in ref)
    print("  duracao/turno  : mediana %.2f s, min %.2f s, max %.2f s"
          % (durs[len(durs) // 2], durs[0], durs[-1]))


def measure_windows(windows, neg_mode=None, neg_span_s=1.5):
    agreements = []
    minority = []
    print("\n  cMAP entre janelas consecutivas (regiao de sobreposicao):")
    for i in range(len(windows) - 1):
        a0, a1, sa = windows[i]
        b0, b1, sb = windows[i + 1]
        ov_from, ov_to = max(a0, b0), min(a1, b1)
        if ov_to - ov_from < 2.0:
            continue
        # MEASURED: o deslocamento pertence ao braco NEGATIVO e so a ele. Na
        # primeira corrida estava FORA do `if`, e o braco normal comparava a
        # janela k com a k+1 deslocada de meia janela: nada se podia alinhar e
        # o instrumento imprimiu "sem fala na sobreposicao" em TODOS os pares,
        # com audio demonstradamente cheio de fala ali. O numero de cabecalho (2 vozes) continuava certo; a coluna do cMAP nao media nada.
        sb_used = (_mutate(sb, neg_mode, i, neg_span_s, ov_from, ov_to)
                   if neg_mode else sb)
        acc, n, _conf, _map, per = cmap(sa, sb_used, ov_from, ov_to)
        if acc is None:
            print("    %d->%d  sem fala na sobreposicao (%.1f s) -- ignorado"
                  % (i, i + 1, ov_to - ov_from))
            continue
        agreements.append(acc)
        detail = "  ".join("voz%d %5.1f%% (%d fr)" % (a, 100.0 * v[0], v[1])
                           for a, v in sorted(per.items()))
        print("    %d->%d  acordo %5.1f%%  (%d frames de %.1f s)   %s"
              % (i, i + 1, 100.0 * acc, n, ov_to - ov_from, detail))
        if len(per) >= 2:
            smallest = min(per.values(), key=lambda v: v[1])
            minority.append(smallest)
    return agreements, minority


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--window-s", type=float, default=S.DEFAULT_WINDOW_S)
    ap.add_argument("--step-s", type=float, default=S.DEFAULT_EVERY_S)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--num-speakers", type=int, default=-1)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--neg-arm", action="store_true",
                    help="atalho para --neg-mode both")
    ap.add_argument("--neg-mode", choices=MUTANTS, default=None)
    ap.add_argument("--neg-span-s", type=float, default=1.5)
    ap.add_argument("--dump", default=None)
    ap.add_argument("--from-dump", default=None)
    args = ap.parse_args(argv)
    if args.neg_arm and not args.neg_mode:
        args.neg_mode = "both"

    if args.from_dump:
        with open(args.from_dump, "r", encoding="utf-8") as fh:
            dump = json.load(fh)
        ref = [tuple(s) for s in dump["ref"]]
        windows = [(w[0], w[1], [tuple(s) for s in w[2]])
                   for w in dump["windows"]]
        dur = dump.get("dur", 0.0)
        print("reusando %s  (%.1f s, %d janelas) -- modelo NAO carregado"
              % (args.from_dump, dur, len(windows)))
    else:
        x, rate = read_wav(args.audio)
        if rate != S.DEFAULT_RATE:
            x = S.to_mono16k(x, rate, S.DEFAULT_RATE)
            rate = S.DEFAULT_RATE
        dur = len(x) / rate
        print("audio: %s  %.1f s  %d Hz  peak=%.4f"
              % (args.audio, dur, rate, float(np.abs(x).max())))
        if dur < 5.0:
            print("FAIL: %.1f s is too short to say anything about speakers" % dur)
            return 2
        t0 = time.time()
        sdk = S._load_sherpa_diarizer(
            S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL, threads=args.threads,
            num_clusters=args.num_speakers, threshold=args.threshold)
        print("model loaded in %.1f s" % (time.time() - t0))
        t0 = time.time()
        ref = diarize(sdk, x)
        print("\n[A] UMA PASSAGEM sobre %.1f s  (%.1f s de CPU)"
              % (dur, time.time() - t0))
        if not ref:
            print("  FAIL: nenhum segmento -- o audio esta em silencio ou o "
                  "modelo nao segmentou nada")
            return 3
        step = int(args.step_s * rate)
        win = int(args.window_s * rate)
        windows = []
        t_start = time.time()
        for a0 in range(0, max(1, len(x) - win + 1), step):
            windows.append((a0 / rate, (a0 + win) / rate,
                            diarize(sdk, x[a0:a0 + win], a0 / rate)))
        print("\n[B] CADENCIA DO SIDECAR: janela %.0f s, passo %.0f s"
              % (args.window_s, args.step_s))
        for n, (w0, w1, sg) in enumerate(windows):
            print("  janela %2d  [%5.1f..%5.1f]  %2d seg  vozes=%s"
                  % (n, w0, w1, len(sg), sorted({l for _, _, l in sg})))
        print("  %d janelas em %.1f s de CPU" % (len(windows), time.time() - t_start))
        if args.dump:
            with open(args.dump, "w", encoding="utf-8") as fh:
                json.dump({"audio": args.audio, "dur": dur,
                           "window_s": args.window_s, "step_s": args.step_s,
                           "ref": [list(s) for s in ref],
                           "windows": [[w[0], w[1], [list(s) for s in w[2]]]
                                       for w in windows]}, fh)
            print("  dump -> %s" % args.dump)

    print("\n[A] UMA PASSAGEM sobre %.1f s" % dur)
    _report_a(ref, dur)

    agreements, minority = measure_windows(windows, args.neg_mode, args.neg_span_s)
    if not agreements:
        print("\n  FAIL: nenhuma sobreposicao com fala -- o instrumento nao "
              "produziu numero nenhum")
        return 3
    mean_acc = sum(agreements) / len(agreements)
    print("\n  cMAP GLOBAL  = %.1f%%  em %d pares  (dominado pela voz maior)"
          % (100.0 * mean_acc, len(agreements)))
    min_frames = sum(v[1] for v in minority) if minority else 0
    if minority:
        min_acc = (sum(v[0] * v[1] for v in minority) / float(min_frames))
        print("  cMAP VOZ MENOR = %.1f%%  em %d pares, %d frames  "
              "<-- o numero que decide" % (100.0 * min_acc, len(minority), min_frames))
    else:
        min_acc = mean_acc
        min_frames = 0
        print("  cMAP VOZ MENOR = n/a (nenhum par teve duas vozes na "
              "sobreposicao) -- a metrica menor NAO foi exercitada")

    if min_frames < MIN_MINORITY_FRAMES:
        print("\nVERDICT: INSUFICIENTE -- a voz minoritaria so tem %d frames e o "
              "piso e %d. O cMAP GLOBAL (%.1f%%) mede sobretudo a voz maior, "
              "que e' a parte facil. Isto NAO e um PASS e nao se deve ler como "
              "tal: e' falta de amostra."
              % (min_frames, MIN_MINORITY_FRAMES, 100.0 * mean_acc))
        return 4
    passed = min_acc >= PASS_CMAP
    print("\nVERDICT: %s   (decide a voz menor: %.1f%% vs piso %.0f%%)"
          % ("PASS" if passed else "FAIL", 100.0 * min_acc, 100.0 * PASS_CMAP))
    if args.neg_mode:
        print("  braco NEGATIVO [%s] tem de CAIR abaixo do piso -- %s"
              % (args.neg_mode, "RED-OK" if not passed else "NAO CAIU (inerte)"))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())