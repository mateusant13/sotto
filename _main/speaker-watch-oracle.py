"""PORTAO do modo watch da Fase A (`worker/speaker_sidecar.py --watch-only`).

O QUE ESTE PORTAO PROVA
======================
Que `watch_tick` -- a funcao de produto -- faz o que o desenho em duas fases
promete, com o pipeline REAL: o `RingBuffer` de produto, o modelo de segmentacao
real, a escrita atomica real, e o payload de produto.

Nao e' um teste de unidade sobre a funcao `multivoice_spans`: e' o caminho que
o processo vivo percorre.

O QUE ELE NAO DEIXA PASSAR
==========================
1. Um payload de watch NAO pode parecer um payload de fala.
   `speaker_bridge.payload_if_fresh` exige `segments` e devolve `None` sem essa
   chave. Se um dia alguem adicionar `segments: []` ao payload de watch, o painel
   passa a ver "zero vozes" como se fosse a MEDIDA, e nao como a ausencia de
   medicao. Esta e' a propriedade que mantem a Fase A inofensiva.
2. As janelas tem de cair DENTRO da sobreposicao verdadeira, que aqui e'
   construida por deslocamentos conhecidos -- nao herdada de outro modelo.
3. O filtro de hold tem de existir: sem ele, os 2 frames de ruido que o modelo
   emite viram um alarme.
4. A MESMA voz em duas camadas nao pode disparar.

O BRACO NEGATIVO
================
`--neg-arm` estreita `speaker_sidecar.MULTI_CLASSES` para `(6,)` -- a mutacao
FIEL, porque foi ela que motivou este portao: com so a classe 6 o braco de 100 %
de sobreposicao dispara 0,00 s e a classe 4 nao conta. O portao tem de reprovar.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                      # noqa: E402

import speaker_sidecar as S             # noqa: E402
import speaker_bridge                    # noqa: E402

SRC_PT = os.path.join(ROOT, "_main", "pt-br-sample.wav")
SRC_EN = os.path.join(ROOT, "_main", "en-us-sample.wav")
FS = 16000

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


def read_wav(path):
    with wave.open(path, "rb") as w:
        return (np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
                .astype(np.float32) / 32768.0)


def rms_to(x, dbfs=-20.0):
    r = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
    if r <= 0:
        return x.astype(np.float32)
    return (x * (10.0 ** (dbfs / 20.0) / r)).astype(np.float32)


def build(parts, total_s):
    """-> audio, e os intervalos [t0,t1) onde COBERTURA >= 2 (a verdade)."""
    n = int(round(total_s * FS))
    out = np.zeros(n, dtype=np.float32)
    cover = np.zeros(n, dtype=np.int16)
    for x, off in parts:
        a = int(round(off * FS))
        b = min(n, a + len(x))
        if b > a:
            out[a:b] += x[: b - a]
            cover[a:b] += 1
    pk = float(np.abs(out).max()) if out.size else 0.0
    if pk > 0.99:
        out = out / pk * 0.99
    runs = []
    i = 0
    while i < n:
        if cover[i] < 2:
            i += 1
            continue
        j = i
        while j < n and cover[j] >= 2:
            j += 1
        runs.append((i / float(FS), j / float(FS)))
        i = j
    return out, runs


def push_window(buf, audio, start_abs, step_s, window_s):
    """Empurra o audio em passos de `step_s`, como o laco vivo faria.

    Devolve o numero de passos dados. `watch_tick` le o instante do buffer
    (`buf.start_t`), que e' o relogio da CAPTURA -- por isso empurrar com
    `start_abs` e' o que torna as janelas comparaveis com a verdade.
    """
    step = int(round(step_s * FS))
    t = 0
    n_steps = 0
    while t + step <= len(audio):
        buf.push(audio[t:t + step].tolist(), start_abs + t / float(FS))
        t += step
        n_steps += 1
    return n_steps


def overlaps(a, b):
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    return hi > lo


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--neg-arm", action="store_true",
                    help="estreita MULTI_CLASSES para (6,) -- tem de reprovar")
    args = ap.parse_args(argv)

    neg = bool(args.neg_arm)
    print("=" * 78)
    print("PORTAO -- modo watch da Fase A (--watch-only)")
    print("classes powerset em uso: %s%s"
          % (list(S.MULTI_CLASSES), "   (BRACO NEGATIVO -- tem de reprovar)"
             if neg else ""))
    print("=" * 78)
    if neg:
        S.MULTI_CLASSES = (6,)
        print("mutacao aplicada: speaker_sidecar.MULTI_CLASSES = (6,)")

    tmp = tempfile.mkdtemp(prefix="watch-oracle-", dir="I:\\cc-tmp")
    try:
        return _run(args, neg, tmp)
    finally:
        # I:\\cc-tmp is a scratch DRIVE, not a museum. Every run of this gate
        # used to leave a watch-oracle-* directory behind for ever, and a gate
        # that fills a disk on the box the owner works on is its own defect.
        shutil.rmtree(tmp, ignore_errors=True)


def _run(args, neg, tmp):
    pt = rms_to(read_wav(SRC_PT))
    en = rms_to(read_wav(SRC_EN))
    L = min(len(pt), len(en)) / float(FS)
    n = int(round(L * FS))

    print("\nCARREGANDO o modelo de produto (so segmentacao)")
    sess = S._load_powerset(S.DEFAULT_SEG_MODEL, args.threads)
    check(True, "modelo de segmentacao carregado sem sherpa nem embeddings",
          "%s" % S.DEFAULT_SEG_MODEL)

    cases = [
        ("A-forte  100%% sobreposicao", [(pt[:n], 0.0), (en[:n], 0.0)], L, True),
        ("A-metade  50%%", [(pt[:n], 0.0), (en[:n], L / 2.0)], L * 1.5, True),
        ("A-seq     0%%", [(pt[:n], 0.0), (en[:n], L)], 2 * L, False),
        ("A-mesma   mesma voz x2", [(pt[:n], 0.0), (pt[:n], 0.0)], L, False),
    ]

    window_s, step_s = 10.0, 10.0        # Fase A nao precisa de sobreposicao
    results = {}
    for name, parts, total_s, should_fire in cases:
        audio, truth_runs = build(parts, total_s)
        out_path = os.path.join(tmp, name.split()[0] + ".json")
        buf = S.RingBuffer(rate=FS, window_s=window_s)
        t0 = time.time()
        push_window(buf, audio, t0, step_s, window_s)
        st = S.watch_tick(buf, sess, out_path, S.DEFAULT_WATCH_HOLD)
        first = (st, json.load(open(out_path, encoding="utf-8"))) \
            if st.get("state") == "written" else None
        check(first is not None, "%s produziu payload" % name.strip())
        if first is None:
            continue
        st, pay = first
        spans = [(s["start"] - t0, s["end"] - t0) for s in pay["multivoice"]]
        inside = [s for s in spans if any(overlaps(s, r) for r in truth_runs)]
        fired_s = sum(e - s for s, e in spans)
        truth_s = sum(r[1] - r[0] for r in truth_runs)
        results[name.split()[0]] = (fired_s, truth_s, out_path, spans)

        print("\n  %s  janela %.0f s passo %.0f s (SEM sobreposicao entre janelas)"
              % (name.strip(), window_s, step_s))
        print("     sobreposicao verdadeira %.2f s | watch disparou %.2f s em %d span(s)"
              % (truth_s, fired_s, len(spans)))
        for s in spans[:4]:
            hit = [r for r in truth_runs if overlaps(s, r)]
            print("        span %.2f-%.2f s -> %s"
                  % (s[0], s[1], ("dentro de %.2f-%.2f" % (hit[0][0], hit[0][1]))
                     if hit else "FORA da sobreposicao"))
        if spans:
            check(all(any(overlaps(s, r) for r in truth_runs) for s in spans),
                  "%s: todos os spans caem dentro da sobreposicao" % name.strip())

        # --- a propriedade que mantem a Fase A inofensiva -----------------
        check("segments" not in pay,
              "%s: o payload de watch NAO tem `segments`" % name.strip(),
              "tem as chaves %s" % sorted(pay))
        got = speaker_bridge.payload_if_fresh(out_path, max_age_s=3600)
        check(got is None,
              "%s: speaker_bridge descarta o payload de watch" % name.strip(),
              "devolveu %r" % (got if got is None else "um payload!"))

        if should_fire:
            check(fired_s > 0.30, "%s: DISPARA" % name.strip(),
                  "disparou %.2f s" % fired_s)
        else:
            check(fired_s <= 0.10, "%s: NAO dispara" % name.strip(),
                  "disparou %.2f s" % fired_s)

    # --- o filtro de hold ------------------------------------------------
    print("\nFILTRO DE HOLD")
    noise = np.zeros(S.DEFAULT_WATCH_HOLD - 1, dtype=np.int64)
    noise[0] = S.MULTI_CLASSES[0]
    long_run = np.zeros(S.DEFAULT_WATCH_HOLD + 2, dtype=np.int64)
    long_run[:] = S.MULTI_CLASSES[0]
    check(S.multivoice_spans(noise, S.DEFAULT_WATCH_HOLD) == [],
          "uma corrida de %d frames e' descartada" % (S.DEFAULT_WATCH_HOLD - 1),
          str(S.multivoice_spans(noise, S.DEFAULT_WATCH_HOLD)))
    check(len(S.multivoice_spans(long_run, S.DEFAULT_WATCH_HOLD)) == 1,
          "uma corrida de %d frames passa" % (S.DEFAULT_WATCH_HOLD + 2))
    check(len(S.multivoice_spans(np.array([], dtype=np.int64), 3)) == 0,
          "janela vazia nao da spans")

    # --- classe unica errada --------------------------------------------
    print("\nO MODELO USA AS 7 CLASSES, NAO UMA SO")
    hist = {}
    audio, _ = build([(pt[:n], 0.0), (en[:n], 0.0)], L)
    win = S.powerset_windows(sess, audio)
    for c in range(7):
        hist[c] = int((win == c).sum())
    print("     distribuicao no braco de 100%%: %s"
          % {k: v for k, v in hist.items() if v})
    if neg:
        check(hist.get(6, 0) == 0,
              "BRACO NEGATIVO: a classe 6 sozinha devia perder a classe 4",
              "classe 6 tem %d frames, classe 4 tem %d"
              % (hist.get(6, 0), hist.get(4, 0)))

    # --- O CONSUMIDOR ------------------------------------------------------
    # Sem isto, `--speakers-cheap` escreve um ficheiro que ninguem le: um sinal
    # sem consumidor nao decide nada. Estas arms sao sobre o LEITOR.
    print("\nO CONSUMIDOR (speaker_bridge + MultiVoiceWatch da shell)")
    watch_path = os.path.join(tmp, "consumer.json")
    pay = json.load(open(results["A-forte"][2], encoding="utf-8"))
    with open(watch_path, "w", encoding="utf-8") as fh:
        json.dump(pay, fh)
    check(speaker_bridge.watch_payload_if_fresh(watch_path, max_age_s=3600) is not None,
          "o leitor aceita o payload de watch", "%s" % results["A-forte"][2])
    st = speaker_bridge.multivoice(speaker_bridge.watch_payload_if_fresh(watch_path, 3600))
    check(st.get("measured") is True and st.get("multivoice") is True,
          "o leitor diz que houve multiplas vozes", json.dumps(st)[:160])

    # A garantia estrutural, nos dois sentidos.
    live_path = os.path.join(tmp, "diar-live-like.json")
    with open(live_path, "w", encoding="utf-8") as fh:
        json.dump({"segments": [{"start": 0, "end": 1, "speaker": 0}],
                   "written_at": time.time()}, fh)
    check(speaker_bridge.payload_if_fresh(watch_path, 3600) is None,
          "o leitor de FALA recusa o payload de watch")
    check(speaker_bridge.watch_payload_if_fresh(live_path, 3600) is None,
          "o leitor de WATCH recusa um payload de fala")

    check(speaker_bridge.multivoice(None)["measured"] is False,
          "sem ficheiro, o leitor diz 'nao medido', nunca 'zero vozes'")
    empty = {"multivoice": [], "written_at": time.time()}
    with open(watch_path, "w", encoding="utf-8") as fh:
        json.dump(empty, fh)
    st0 = speaker_bridge.multivoice(speaker_bridge.watch_payload_if_fresh(watch_path, 3600))
    check(st0["measured"] is True and st0["multivoice"] is False,
          "zero spans e' 'medido e nada visto', diferente de 'nao medido'",
          json.dumps(st0)[:120])

    sys.path.insert(0, os.path.join(ROOT, "app", "webview"))
    import sotto_webview as W                                       # noqa: PLC0415
    lines = []
    watcher = W.MultiVoiceWatch(path=watch_path, poll_s=0.01,
                                log=lambda m: lines.append(m))
    with open(watch_path, "w", encoding="utf-8") as fh:
        json.dump(pay, fh)
    watcher.poll_once()
    watcher.poll_once()
    fired = [m for m in lines if "WATCH_MULTIVOICE" in m]
    check(len(fired) == 1,
          "o watcher regista UMA vez e nao a cada poll",
          "linhas: %s" % [m[:60] for m in lines])
    check(any("spans=" in m for m in fired), "a linha regista os spans",
          fired[0][:90] if fired else "(nenhuma)")

    with open(watch_path, "w", encoding="utf-8") as fh:
        json.dump(empty, fh)
    lines.clear()
    watcher.poll_once()
    check(not [m for m in lines if "WATCH_MULTIVOICE" in m],
          "uma janela sem sobreposicao nao e' registada como alarme")

    # --- O DONO FICA A SABER QUE O AUDIO FOI PERDIDO? ----------------------
    # A retencao passou a publicar `clips_evicted` no payload (a fila FIFO
    # conta o que apaga). Se o watcher o IGNORA, o audio do dono continua a
    # desaparecer em silencio -- agora com um campo correcto num ficheiro que
    # ninguem le. O log do watcher e' a UNICA superficie que o dono tem.
    lost = dict(pay)
    lost["clips_saved"] = 1
    lost["clips_evicted"] = 4
    lines3 = []
    w3 = W.MultiVoiceWatch(path=watch_path, poll_s=0.01,
                           log=lambda m: lines3.append(m))
    with open(watch_path, "w", encoding="utf-8") as fh:
        json.dump(lost, fh)
    w3.poll_once()
    fired3 = [m for m in lines3 if "WATCH_MULTIVOICE" in m]
    check(len(fired3) == 1 and "AUDIO_PERDIDO=4" in fired3[0],
          "o watcher DIZ que a fila apagou audio do dono",
          fired3[0][:100] if fired3 else repr(lines3))
    check(fired3 and "spans=" in fired3[0],
          "e a mesma linha continua a dizer quantas vozes houve",
          fired3[0][:100] if fired3 else "-")

    # O caso normal nao pode engordar a linha: uma janela sem eviccao e' o
    # que acontece em quase todas, e um aviso a mais e' um aviso a menos lido.
    lines4 = []
    w4 = W.MultiVoiceWatch(path=watch_path, poll_s=0.01,
                           log=lambda m: lines4.append(m))
    calm = dict(pay)
    calm["clips_saved"] = 2
    calm["clips_evicted"] = 0
    with open(watch_path, "w", encoding="utf-8") as fh:
        json.dump(calm, fh)
    w4.poll_once()
    fired4 = [m for m in lines4 if "WATCH_MULTIVOICE" in m]
    check(len(fired4) == 1 and "AUDIO_PERDIDO" not in fired4[0],
          "e sem eviccao a linha fica igual ao que era",
          fired4[0][:100] if fired4 else repr(lines4))

    # Devolver `watch_path` ao estado quieto: as arms acima escreveram nele
    # payloads COM spans, e o teste seguinte (`WATCH_ALIVE`) e' sobre a
    # primeira leitura de uma janela sem sobreposicao. Sem isto, eu partia duas
    # arms alheias a um teste meu — que é como um gate deixa de ser lido a
    # sério e passa a ser lido só pelo que passa.
    with open(watch_path, "w", encoding="utf-8") as fh:
        json.dump(empty, fh)

    # Uma NOVA instancia, porque `WATCH_ALIVE` e' a PRIMEIRA leitura: o watcher
    # acima ja leu e por isso ja tem uma chave anterior. Testar com ele seria
    # testar outra coisa e dar um falso negativo.
    lines2 = []
    fresh = W.MultiVoiceWatch(path=watch_path, poll_s=0.01,
                              log=lambda m: lines2.append(m))
    fresh.poll_once()
    check(any("WATCH_ALIVE" in m for m in lines2),
          "a primeira leitura QUIETA diz que o detector esta vivo",
          repr([m[:70] for m in lines2]))
    check(not [m for m in lines2 if "WATCH_MULTIVOICE" in m],
          "e NAO dispara alarme nessa mesma leitura")

    check(W.speaker_watch_payload_path() != os.path.normpath(
        os.path.join(ROOT, "_main", "diar-live.json")),
          "o payload de watch e' um ficheiro DIFERente do de fala")

    print("\n" + "-" * 78)
    if FAILURES:
        print("VERDICT: FAIL  (%d/%d checks falharam: %s)"
              % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
        return 1
    if neg:
        print("VERDICT: PASS  (%d/%d checks)  -- este era o BRACO NEGATIVO: PASS "
              "significa que a mutacao foi REJEITADA." % (CHECKS[0], CHECKS[0]))
        return 0
    print("VERDICT: PASS  (%d/%d checks)" % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())