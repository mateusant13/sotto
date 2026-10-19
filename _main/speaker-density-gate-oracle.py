"""PORTAO DA PORTA DE DENSIDADE.

O defeito que ela corrige, medido nas gravacoes REAIS da call do dono:

    `call.wav`     (60 s,  29 % de silencio) -> 2 slots. Correcto.
    `call180.wav` (180 s, 89 % de silencio) -> 12 slots para 2 pessoas.

    A cadeia de produto criava um slot NOVO por janela, e o painel faria 12
    pontos coloridos para duas pessoas. Nao e' um cMAP feio -- e' o painel a
    mentir sobre quantas pessoas estao a falar.

POR QUE A PORTA E' DE ENERGIA E NAO DE MODELO
============================================
    Zero RAM (e' o que a torna utilizavel na Fase A), e INDEPENDENTE -- o RMS do
    audio nao sabe nada sobre vozes. Usar a classe 0 do proprio modelo de
    segmentacao seria vigiar o modelo com ele proprio.

O LIMIAR
========
    fracao do pico da PROPRIA janela. As duas gravacoes medem -18,5 dBFS e
    -32,5 dBFS: 14 dB de diferenca. Um limiar em dBFS mediria o ganho.

O BRACO NEGATIVO
================
`--neg-arm` poe a porta a 0.0, que e' exactamente o estado de antes da
feature -- e tem de devolver a fragmentacao. Uma porta que nao sabe dizer NAO
esta a dar a sensacao de estar a resolver o problema.
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

FS = 16000
DENSE = r"I:\cc-tmp\call.wav"
SPARSE = r"I:\cc-tmp\call180.wav"

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


def run_chain(sess, audio, window_s, every_s, min_frac, out_path, threshold):
    """A cadeia de produto, com a porta, e o que o painel leria."""
    buf = S.RingBuffer(rate=FS, window_s=window_s)
    slots = S.StableSpeakerSlots()
    win = int(window_s * FS)
    step = int(every_s * FS)
    t0 = 1_900_000_000.0
    seen = set()
    n_declined = 0
    n_attributed = 0
    speech_s_attributed = 0.0
    states = {}
    read_fail = 0

    def diarize(samples, threshold=None, num_speakers=None):
        r = sess.process(np.asarray(samples, dtype=np.float32)).sort_by_start_time()
        # A FORMA E' UM DICT COM "segments", nao uma lista. MEDIDO em
        # `speaker_sidecar.py:1070` (`_make_live_diarizer`): `tick` entrega o
        # que `diarize` devolve a `to_absolute`, que le `payload["segments"]`.
        # Uma lista aqui dava um payload com `segments: []` sem erro nenhum --
        # o teste inteiro media zero sem dar um unico sintoma.
        return {"segments": [{"start": float(s.start), "end": float(s.end),
                              "speaker": int(s.speaker)} for s in r]}

    for start in range(0, max(1, len(audio) - win + 1), step):
        buf.push(audio[start:start + step].tolist(), t0 + start / float(FS))
        if len(buf) < win:
            continue
        st = S.tick(buf, diarize, out_path, threshold, slots=slots,
                    min_speech_fraction=min_frac)
        states[st.get("state")] = states.get(st.get("state"), 0) + 1
        if st.get("declined"):
            n_declined += 1
        else:
            n_attributed += 1
            try:
                pay = json.load(open(out_path, encoding="utf-8"))
            except (OSError, ValueError):
                read_fail += 1
                continue
            segs = pay.get("segments") or ()
            speech_s_attributed += sum(
                max(0.0, float(s["end"]) - float(s["start"])) for s in segs)
            seen.update(int(s["speaker"]) for s in segs)

    return seen, n_declined, n_attributed, speech_s_attributed, states, read_fail


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--window-s", type=float, default=20.0)
    ap.add_argument("--every-s", type=float, default=10.0)
    ap.add_argument("--neg-arm", action="store_true",
                    help="porta a 0,0 (estado anterior); a fragmentacao tem de "
                         "voltar e o portao tem de reprovar")
    args = ap.parse_args(argv)

    neg = bool(args.neg_arm)
    min_frac = 0.0 if neg else S.MIN_SPEECH_FRACTION

    tmp = tempfile.mkdtemp(prefix="gate-", dir="I:\\cc-tmp")
    try:
        return _run(args, min_frac, tmp, neg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(args, min_frac, tmp, neg):
    print("=" * 78)
    print("PORTAO DA PORTA DE DENSIDADE  (limiar %.2f%s)"
          % (min_frac, "   BRAACO NEGATIVO" if neg else ""))
    print("=" * 78)

    print("\nA FUNCAO DA PORTA, sem modelo nenhum")
    check(S.speech_fraction([0.0] * 16000) == 0.0,
          "silencio digital devolve 0,0 e nao um log de zero",
          "%r" % S.speech_fraction([0.0] * 16000))
    check(S.speech_fraction([0.1] * 16000) == 1.0,
          "uma janela constante conta-se como fala inteira",
          "%r" % S.speech_fraction([0.1] * 16000))
    rng = np.random.RandomState(3)
    noisy = (rng.randn(16000) * 0.001).astype(np.float32)
    check(S.speech_fraction(noisy.tolist()) <= 1.0,
          "ruido devolve uma fracao dentro de [0,1]",
          "%r" % S.speech_fraction(noisy.tolist()))

    # ---- O QUE A RECUSA FAZ AO QUE JA ESTAVA NO PAINEL --------------------
    # A porta escreve `segments: []`. O risco nao e' a porta estragar a
    # atribuicao -- e' APAGAR o `source` do dispositivo, que a legenda carregava
    # antes de a voz aparecer. Perder o dispositivo e' uma mentira pior do que
    # perder o nome: sem `source` nao se sabe sequer de que microfone veio.
    print("\nO QUE A RECUSA FAZ AS LEGENDAS")
    import time as _time
    lines = [{"text": "primeira", "start": 1.0, "end": 3.0},
             {"text": "segunda", "start": 4.0, "end": 6.0}]
    declined = {"state": "written", "written_at": _time.time(), "segments": [],
                "n_segments": 0, "attribution": "declined",
                "speech_fraction": 0.02, "min_speech_fraction": 0.30}
    out = speaker_bridge.apply_to_lines(lines, "device:mic", declined)
    check(all(l.get("source") == "device:mic" for l in out),
          "a recusa MANTEM o `source` do dispositivo",
          "%s" % [l.get("source") for l in out])
    check(all(l.get("speaker") is None for l in out),
          "e nao inventa uma voz", "%s" % [l.get("speaker") for l in out])
    v = speaker_bridge.voices(declined)
    check(v.get("n_speakers") == 0,
          "a barra de estado diz zero vozes, nao um erro",
          "%s" % v)

    voiced = {"state": "written", "written_at": _time.time(),
              "segments": [{"start": 0.0, "end": 20.0, "speaker": 1,
                            "source": "voice:speaker-1"}], "n_segments": 1}
    out2 = speaker_bridge.apply_to_lines(lines, "device:mic", voiced)
    check(any("voice:speaker-1" in (l.get("source") or "") for l in out2),
          "e o caminho normal continua a marcar a voz",
          "%s" % [l.get("source") for l in out2])

    sess = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                   threads=args.threads, threshold=args.threshold)

    results = {}
    for tag, path, want in (("densa", DENSE, 2), ("esparsa", SPARSE, 2)):
        if not os.path.exists(path):
            print("\n%s AUSENTE: %s" % (tag, path))
            continue
        audio = read_wav(path)
        out_path = os.path.join(tmp, "%s.json" % tag)
        t0 = time.perf_counter()
        seen, decl, attr, speech_s, states, read_fail = run_chain(
            sess, audio, args.window_s, args.every_s, min_frac, out_path,
            args.threshold)
        wall = time.perf_counter() - t0
        results[tag] = (seen, decl, attr, speech_s)
        print("\n  gravacao %s (%s, %.0f s)"
              % (tag, os.path.basename(path), len(audio) / float(FS)))
        print("     estados devolvidos por tick(): %s" % states)
        print("     janelas atribuidas %d | recusadas pela porta %d | leituras falhadas %d"
              % (attr, decl, read_fail))
        print("     SLOTS que o painel faria: %d %s" % (len(seen), sorted(seen)))
        print("     fala que chegou a ter voz: %.1f s" % speech_s)
        print("     %.2f s de parede" % wall)

    if len(results) < 2:
        print("\nVERDICT: FAIL (faltam gravacoes)")
        return 1

    print("\n" + "-" * 78)
    if neg:
        sparse = results["esparsa"][0]
        check(len(sparse) > 2,
              "BRACO NEGATIVO: sem a porta a fragmentacao VOLTA",
              "o painel faria %d pontos para 2 pessoas" % len(sparse))
    else:
        for tag in ("densa", "esparsa"):
            seen, decl, attr, speech_s = results[tag]
            check(len(seen) <= 2,
                  "gravacao %s: no maximo 2 slots para 2 pessoas" % tag,
                  "%d slots" % len(seen))
        seen, decl, attr, speech_s = results["densa"]
        check(attr > 0 and len(seen) == 2,
              "a gravacao DENSA continua a ser atribuida normalmente",
              "%d janelas atribuidas, %d slots" % (attr, len(seen)))
        check(speech_s > 10.0,
              "e nao se perde a fala dela",
              "%.1f s com voz" % speech_s)
        seen, decl, attr, speech_s = results["esparsa"]
        check(decl > 0,
              "a gravacao ESPARSA tem janelas recusadas, e nao slots inventados",
              "%d recusadas" % decl)
        check(not seen,
              "e nenhuma voz inventada nela",
              "slots %s" % sorted(seen))

    print("-" * 78)
    if FAILURES:
        print("VERDICT: FAIL  (%d/%d: %s)" % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
        return 1
    if neg:
        print("VERDICT: PASS  (%d/%d)  -- este era o BRACO NEGATIVO: PASS "
              "significa que a porta esta a FAZER ALGUMA COISA." % (CHECKS[0], CHECKS[0]))
        return 0
    print("VERDICT: PASS  (%d/%d checks)" % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())