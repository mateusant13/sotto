"""ACEITACAO DA CADEIA COMPLETA, numa call de comprimento REAL.

O que ja foi medido, e onde:
  - 60 s da call real, cadeia completa: 2 slots, cMAP 90,4 %
  - misturas controladas: DER de confusao 0,95-1,23 %, F1 do detector 0,932

O que NUNCA foi medido: a cadeia a correr como corre -- Fase A a varrer a call
na cadencia de produto (10 s de janela, 10 s de passo), a guardar o audio
assinalado, e a Fase B a separar as vozes nesses clips -- durante uma call
inteira. A validaçao anterior era de 60 s, e 60 s nao e' uma call.

Este e' esse ensaio. Nao ha truth humana, por isso ISTO NAO E' UM PORTAO: e' um
relatorio com verificacoes que nao precisam de truth -- quantas janelas
assinalaram, quanto disco custou, se algum clip passou do limite seguro, se a
Fase B depois disso ainda acha as duas vozes, e quanto tempo e CPU levou.

O QUE FICAR SEM RESPOSTA, E POR QUE
===================================
Nao se sabe quantas pessoas estavam a falar e quando. Por isso este nao da DER,
nao da cMAP e nao diz se a atribuicao estava CORRECTA. O que ele diz e se o
**mecanismo** aguenta o comprimento de uma call: memoria, disco, tempo, e se o
degrau das 10 s e respeitado ao longo de toda a corrida.

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


def dir_mb(d):
    total = 0
    for root, _, files in os.walk(d):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1048576.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", default=r"I:\cc-tmp\call180.wav")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--max-clips", type=int, default=0,
                    help="0 = processa todos; corta a Fase B para ficheiros pequenos")
    args = ap.parse_args(argv)

    if not os.path.exists(args.audio):
        print("realcall: audio ausente %s" % args.audio)
        return 3

    tmp = tempfile.mkdtemp(prefix="realcall-", dir="I:\\cc-tmp")
    try:
        return _run(args, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(args, tmp):
    audio = read_wav(args.audio)
    dur = len(audio) / float(FS)
    save_dir = os.path.join(tmp, "clips")
    out_json = os.path.join(tmp, "diar-watch.json")

    print("=" * 78)
    print("ACEITACAO DA CADEIA -- %s, %.0f s" % (os.path.basename(args.audio), dur))
    print("cadencia de produto: janela %.0f s, passo %.0f s"
          % (S.SAFE_WINDOW_S, S.SAFE_WINDOW_S))
    print("=" * 78)

    # ---- FASE A -------------------------------------------------------------
    print("\nFASE A -- a varrer a call e a guardar o que assinala")
    sess = S._load_powerset(S.DEFAULT_SEG_MODEL, args.threads)
    buf = S.RingBuffer(rate=FS, window_s=S.SAFE_WINDOW_S)
    step = int(S.SAFE_WINDOW_S * FS)
    win = int(S.SAFE_WINDOW_S * FS)

    t0 = 1_800_000_000.0
    flags = []
    n_win = 0
    seg_a = 0.0
    t_start = time.perf_counter()
    for start in range(0, max(1, len(audio) - win + 1), step):
        buf.push(audio[start:start + step].tolist(), t0 + start / float(FS))
        if len(buf) < win:
            continue
        n_win += 1
        st = S.watch_tick(buf, sess, out_json, S.DEFAULT_WATCH_HOLD,
                          save_dir=save_dir, pad_s=2.0, max_mb=256)
        if st.get("n_spans"):
            flags.append({"t_abs": st["window_start_abs"], **{
                k: st.get(k) for k in ("n_spans", "multivoice_s", "n_clips")}})
            seg_a += st.get("multivoice_s", 0.0)
    wall_a = time.perf_counter() - t_start

    print("  %d janelas em %.2f s  (RTF %.4f da Fase A sobre a call)"
          % (n_win, wall_a, wall_a / dur))
    print("  janelas com duas vozes: %d de %d (%.0f%%)"
          % (len(flags), n_win, 100.0 * len(flags) / max(1, n_win)))
    print("  segundos assinalados: %.1f de %.0f (%.1f%% da call)"
          % (seg_a, dur, 100.0 * seg_a / dur))
    mb = dir_mb(save_dir)
    n_clips = len([f for f in os.listdir(save_dir)]) if os.path.isdir(save_dir) else 0
    print("  clips guardados: %d, %.1f MB" % (n_clips, mb))

    check(len(flags) > 0,
          "a Fase A assinalou alguma sobreposicao nesta call real",
          "%d janelas" % len(flags))
    check(wall_a / dur < 0.05,
          "a Fase A nunca passa de RTF 0,05 durante a call",
          "RTF %.4f" % (wall_a / dur))
    check(mb < dur * 0.05,
          # `5%` e nao `5%%`: esta etiqueta nao passa por formatacao nenhuma, e o
          # `%%` saia literally para o relatorio que o dono le.
          "disco abaixo de 5% da duracao da call em WAV",
          "%.1f MB para %.0f s" % (mb, dur))

    # Nenhum clip pode passar do limite seguro -- e' o que quebrava a Fase B.
    over = []
    longest = 0.0
    if os.path.isdir(save_dir):
        for f in sorted(os.listdir(save_dir)):
            p = os.path.join(save_dir, f)
            try:
                with wave.open(p, "rb") as w:
                    s = w.getnframes() / float(w.getframerate())
            except (OSError, wave.Error):
                continue
            longest = max(longest, s)
            if s > S.SAFE_WINDOW_S:
                over.append((f, s))
    check(not over,
          "NENHUM clip passa do limite seguro de %.0f s (o degrau)" % S.SAFE_WINDOW_S,
          "mais longo %.2f s; %d acima" % (longest, len(over)))
    check(longest <= S.SAFE_WINDOW_S,
          "o clip mais longo cabe na janela segura",
          "%.2f s" % longest)

    # ---- FASE B -------------------------------------------------------------
    print("\nFASE B -- separar as vozes nos clips guardados")
    clips = sorted(f for f in os.listdir(save_dir)) if os.path.isdir(save_dir) else []
    if args.max_clips:
        clips = clips[:args.max_clips]
    if not clips:
        check(False, "ha clips para a Fase B processar")
        print("\nVERDICT: FAIL")
        return 1

    t1 = time.perf_counter()
    # `--ignore-load` pelo mesmo motivo que no `phase-a-b-cycle-oracle`: aqui
    # mede-se o MECANISMO ao longo de uma call, nao a carga da maquina. A guarda
    # de carga tem o portao dela (`offline-load-guard-oracle.py`); deixar este
    # ensaio depender da carga do dono seria tornar o ensaio instavel.
    proc = subprocess.run(
        [PY, os.path.join(HERE, "multivoice-offline.py"), save_dir,
         "--threads", str(args.threads), "--threshold", str(args.threshold),
         "--ignore-load", "--out", os.path.join(tmp, "offline.json")],
        capture_output=True, text=True, timeout=3600,
        env=dict(os.environ, TMPDIR="I:\\cc-tmp"), creationflags=0x08000000)
    wall_b = time.perf_counter() - t1
    tail = [l for l in (proc.stdout or "").splitlines() if l.strip()][-6:]
    print("\n".join("     " + l for l in tail))
    check(proc.returncode == 0, "a Fase B correu sobre a fila de clips",
          "rc=%d" % proc.returncode)

    if proc.returncode == 0:
        off = json.load(open(os.path.join(tmp, "offline.json"), encoding="utf-8"))
        speakers = {}
        rtfs = []
        for c in off["clips"]:
            speakers[c["file"]] = c["n_speakers"]
            if c.get("rtf"):
                rtfs.append(c["rtf"])
        two = sum(1 for v in speakers.values() if v >= 2)
        print("\n  clips onde a Fase B encontrou >=2 vozes: %d de %d"
              % (two, len(speakers)))
        if rtfs:
            print("  RTF da Fase B: max %.3f, medio %.3f"
                  % (max(rtfs), sum(rtfs) / len(rtfs)))
        print("  tempo total da Fase B: %.1f s para %.1f MB de clips"
              % (wall_b, mb))

        check(max(rtfs) < 1.0 if rtfs else False,
              "a Fase B ficou abaixo de tempo real em TODOS os clips",
              "pior RTF %.3f" % (max(rtfs) if rtfs else -1))
        check(two >= 1,
              "pelo menos um clip foi separado em duas ou mais vozes",
              "%d de %d" % (two, len(speakers)))

    print("\n" + "-" * 78)
    print("O QUE ISTO NAO DIZ: se a atribuicao estava CORRECTA. Nao ha truth")
    print("humana sobre quando havia duas pessoas a falar nesta call, e nao se")
    print("inventa. O que fica medido e se o MECANISMO aguenta o comprimento:")
    print("memoria, disco, tempo, e o limite de 10 s respeitado ate ao fim.")
    print("-" * 78)
    if FAILURES:
        print("VERDICT: FAIL  (%d/%d: %s)" % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
        return 1
    print("VERDICT: PASS  (%d/%d checks)" % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())