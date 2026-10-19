"""O CICLO INTEIRO: Fase A guarda -> Fase B consome. Medido, ponta a ponta.

Este e' o instrumento que diz se "processar depois" deixou de ser aspiracional.

Passos:
  1. mistura duas vozes com sobreposicao EXACTA e alimenta o `RingBuffer` real
     e o modelo de segmentacao real;
  2. `watch_tick` com `save_dir` -- o mesmo caminho de produto -- tem de GUARDAR
     um WAV, e esse WAV tem de ter o audio certo (o das duas vozes, no sitio
     certo, com a duracao certa);
  3. `_main/multivoice-offline.py`, o produto da Fase B, tem de CONSUMIR esse
     WAV e devolver as duas vozes.

O passo 3 e' o que fecha o pedido do dono. Sem ele, a Fase A e' um detector
bonito que guarda ficheiros que ninguem lera.

Instrumento. Nao abre dispositivo de audio, nao lanca o Sotto.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                      # noqa: E402

import speaker_sidecar as S             # noqa: E402

PY = sys.executable
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


def read_wav(p):
    with wave.open(p, "rb") as w:
        return (np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
                .astype(np.float32) / 32768.0)


def rms_to(x, dbfs=-20.0):
    r = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
    return x.astype(np.float32) if r <= 0 else (x * (10.0 ** (dbfs / 20.0) / r)).astype(np.float32)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--neg-arm", action="store_true",
                    help="NAO guarda o audio assinalado; a Fase B tem de ficar "
                         "sem nada para processar e o portao tem de reprovar")
    args = ap.parse_args(argv)

    tmp = tempfile.mkdtemp(prefix="cycle-", dir="I:\\cc-tmp")
    try:
        return _run(args, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(args, tmp):
    neg = bool(args.neg_arm)
    pt, en = rms_to(read_wav(SRC_PT)), rms_to(read_wav(SRC_EN))
    n = min(len(pt), len(en))
    mix = (pt[:n] + en[:n]).astype(np.float32)
    pk = float(np.abs(mix).max())
    if pk > 0.99:
        mix = mix / pk * 0.99
    dur = len(mix) / float(FS)

    save_dir = os.path.join(tmp, "clips")
    out_json = os.path.join(tmp, "diar-watch.json")

    print("=" * 78)
    print("CICLO FASE A -> FASE B")
    if neg:
        print("BRACO NEGATIVO: a Fase A NAO guarda o audio assinalado")
    print("=" * 78)

    # ---- 1. A Fase A guarda -----------------------------------------------
    print("\n1) Fase A -- ring buffer real, modelo real, --watch-save")
    sess = S._load_powerset(S.DEFAULT_SEG_MODEL, args.threads)
    buf = S.RingBuffer(rate=FS, window_s=10.0)
    t0 = 1_700_000_000.0
    buf.push(mix.tolist(), t0)
    st = S.watch_tick(buf, sess, out_json, S.DEFAULT_WATCH_HOLD,
                      save_dir=("" if neg else save_dir),
                      pad_s=2.0, max_mb=64)
    check(st.get("state") == "written", "a Fase A publicou o payload",
          json.dumps(st)[:140])
    check(st.get("n_spans", 0) > 0, "a Fase A assinalou duas vozes",
          "spans=%s multi=%.2fs" % (st.get("n_spans"), st.get("multivoice_s", 0)))

    if neg:
        # A mutacao e' a mais fiel que existe: e' o estado ANTERIOR desta
        # feature. A deteccao continua a funcionar -- ate melhor, por ser mais
        # leve -- e e' EXACTAMENTE por isso que um gate que so olhasse para o
        # detector passaria. O que falha e' a Fase B, que nao tem audio.
        check(st.get("n_clips", 0) == 0,
              "BRACO NEGATIVO: sem --watch-save nao ha clip nenhum",
              "n_clips=%s" % st.get("n_clips"))
        print("\n3) Fase B -- sem audio guardado")
        proc = subprocess.run(
            [PY, os.path.join(HERE, "multivoice-offline.py"), save_dir,
             "--threads", str(args.threads), "--ignore-load"],
            capture_output=True, text=True, timeout=600,
            env=dict(os.environ, TMPDIR="I:\\cc-tmp"), creationflags=0x08000000)
        check(proc.returncode != 0,
              "BRACO NEGATIVO: a Fase B recusa um directorio sem clips",
              "rc=%d" % proc.returncode)
        print("\n" + "-" * 78)
        if FAILURES:
            print("VERDICT: FAIL  (%d/%d: %s)" % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
            return 1
        print("VERDICT: PASS  (%d/%d checks)  -- este era o BRACO NEGATIVO: PASS "
              "significa que a falta de audio guardado foi REJEITADA."
              % (CHECKS[0], CHECKS[0]))
        return 0

    check(st.get("n_clips", 0) > 0, "e GUARDOU audio assinalado",
          "clips=%s" % st.get("n_clips"))

    clips = sorted(f for f in os.listdir(save_dir)) if os.path.isdir(save_dir) else []
    check(len(clips) == st.get("n_clips"), "os ficheiros estao no disco",
          str(clips))

    # ---- 2. O clip tem o audio certo --------------------------------------
    print("\n2) O clip guardado tem o audio certo?")
    if clips:
        path = os.path.join(save_dir, clips[0])
        with wave.open(path, "rb") as w:
            clip_rate, clip_ch, clip_w = w.getframerate(), w.getnchannels(), w.getsampwidth()
            clip = (np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
                    .astype(np.float32) / 32768.0)
        check(clip_rate == FS and clip_ch == 1 and clip_w == 2,
              "16 kHz mono 16 bit, como o resto da cadeia",
              "%d Hz %dch %d B" % (clip_rate, clip_ch, clip_w * 8))
        stem = os.path.basename(path)[3:-4]
        check(stem.isdigit(), "o nome carrega o instante absoluto", stem)
        base = int(stem) / 1000.0
        # `base` tem de ser o inicio do troco no relogio da chamada: dentro da
        # janela, nunca antes do seu inicio e nunca depois do seu fim.
        check(t0 - 0.5 <= base <= t0 + dur + 0.5,
              "o instante do nome cai dentro da janela que o originou",
              "base=%.3f, janela de %.3f a %.3f" % (base, t0, t0 + dur))
        check(float(np.abs(clip).max()) > 0.01, "o clip tem audio dentro",
              "peak %.4f" % float(np.abs(clip).max()))

        payload = json.load(open(out_json, encoding="utf-8"))
        sp = payload["multivoice"][0]
        # Onde o clip tem de estar, em segundos dentro da janela.
        want_lo = sp["start"] - payload["window_start_abs"] - 2.0
        want_hi = sp["end"] - payload["window_start_abs"] + 2.0
        got_s = len(clip) / float(FS)
        want_s = min(dur, want_hi) - max(0.0, want_lo)
        check(abs(got_s - want_s) <= 0.2,
              "o clip tem a duracao certa (span + 2 s de contexto)",
              "guardado %.2f s, esperado %.2f s" % (got_s, want_s))
    else:
        check(False, "havia um clip para inspecionar")

    # ---- 3. A Fase B consome ------------------------------------------------
    # `--ignore-load` de proposito. A Fase B passou a recusar quando nao ha um
    # nucleo livre (a guarda de carga), e essa guarda tem o portao dela
    # (`offline-load-guard-oracle.py`). Aqui estamos a medir o CICLO -- a Fase A
    # a guardar audio que a Fase B consome -- e nao a carga da maquina. Sem este
    # flag este gate ficava INSTAVEL: passava ou falhava conforme o que o dono
    # tivesse a fazer, que e' a pior propriedade que um portao pode ter.
    print("\n3) Fase B -- _main/multivoice-offline.py sobre o clip guardado")
    t1 = time.perf_counter()
    proc = subprocess.run(
        [PY, os.path.join(HERE, "multivoice-offline.py"), save_dir,
         "--threads", str(args.threads), "--ignore-load",
         "--out", os.path.join(tmp, "offline.json")],
        capture_output=True, text=True, timeout=900, env=dict(os.environ, TMPDIR="I:\\cc-tmp"),
        creationflags=0x08000000)
    wall = time.perf_counter() - t1
    tail = [l for l in (proc.stdout or "").splitlines()
            if l.strip()][-8:]
    print("\n".join("     " + l for l in tail))
    check(proc.returncode == 0, "a Fase B correu", "rc=%d" % proc.returncode)

    if proc.returncode == 0 and os.path.exists(os.path.join(tmp, "offline.json")):
        off = json.load(open(os.path.join(tmp, "offline.json"), encoding="utf-8"))
        check(isinstance(off.get("n_segments"), int), "payload com `segments`",
              json.dumps(off)[:120])
        first = off["clips"][0]
        check(first["n_speakers"] == 2,
              "a Fase B separou as DUAS vozes do clip guardado",
              "n_speakers=%d" % first["n_speakers"])
        check(first["clip_base_abs"] > 1_000_000,
              "e devolveu o clip ao relogio da chamada",
              "base=%.1f" % first["clip_base_abs"])
        print("\n     relacao de custo, no mesmo audio:")
        print("     Fase A (deteccao)  RTF medido 0,0097   |  este passo %.2f s"
              % wall)
        print("     Fase B (separacao) RTF %.3f" % first["rtf"])
    else:
        check(False, "a Fase B produziu payload", (proc.stderr or "")[-200:])

    print("\n" + "-" * 78)
    if FAILURES:
        print("VERDICT: FAIL  (%d/%d: %s)" % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
        return 1
    print("VERDICT: PASS  (%d/%d checks)" % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())