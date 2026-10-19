"""FASE A -- RSS: quanto custa ter o detector CHEIO ligado o tempo todo?

O dono (2026-10-18): *"precisamos detectar que sao multiplas vozes, pra decidir
isso pra processar depois quando e seguro e nao travar o pc do usuario."*

Para algo poder ficar sempre ligado, o custo que o dono sente nao e' o CPU --
e' a **RAM**. O RTF da Fase A ja foi medido (0,0097 vs 0,503 da pipeline
completa: 52x mais barata). Falta a memoria, e a comparacao tem de ser FEITA NA
MESMA CORRIDA: o 207 MB do sidecar completo foi medido noutro dia, noutras
condicoes, e comparar um numero de hoje com um de ontem nao e' medida.

Este probe lanca DOIS filhos, um de cada tipo, e mede o RSS dos dois com o mesmo
instrumento a 1 Hz:

  seg   -- carrega SO `model.onnx` (5,7 MB). E' a Fase A.
  full  -- carrega segmentacao + embeddings (37,8 MB) + clustering. E' o sidecar.

Instrumento. Nao lanca o Sotto, nao abre o painel, nao toca no produto.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"H:\sotto"
PY = sys.executable

CHILD = r'''
import os, sys, time, wave
import numpy as np
import psutil

mode = sys.argv[1]
segs = int(sys.argv[2])
root = r"H:\sotto"
sys.path.insert(0, os.path.join(root, "worker"))
SEG = os.path.join(root, "_main", "diar-models",
                   "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx")

proc = psutil.Process(os.getpid())
win = np.random.RandomState(0).randn(16000 * 10).astype(np.float32) * 0.05

def rss():
    return proc.memory_info().rss / 1048576.0

base = rss()
print("%.2f" % base, flush=True)

if mode == "seg":
    import onnxruntime
    o = onnxruntime.SessionOptions()
    o.log_severity_level = 3
    o.intra_op_num_threads = 2
    sess = onnxruntime.InferenceSession(SEG, o)
    for i in range(segs):
        sess.run(None, {"x": win[None, None, :]})
        print("%.2f" % rss(), flush=True)
else:
    import speaker_sidecar as S
    seg = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                  threads=2, threshold=0.9)
    for i in range(segs):
        seg.process(win)
        print("%.2f" % rss(), flush=True)
'''


def run(mode, segs, timeout_s):
    """Corre o filho e devolve (rss_inicial, rss_max, n_linhas)."""
    env = dict(os.environ, TMPDIR="I:\\cc-tmp", PYTHONUNBUFFERED="1")
    p = subprocess.Popen([PY, "-c", CHILD, mode, str(segs)], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, creationflags=0x08000000)
    series = []
    t0 = time.perf_counter()
    try:
        for line in p.stdout:
            line = line.strip()
            try:
                series.append(float(line))
            except ValueError:
                continue
            if time.perf_counter() - t0 > timeout_s:
                break
    finally:
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
    return series


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--segs", type=int, default=8)
    ap.add_argument("--timeout-s", type=float, default=240.0)
    args = ap.parse_args(argv)

    print("RSS em MB, mesma maquina, mesma corrida, 2 nucleos\n")
    out = {}
    for mode in ("seg", "full"):
        s = run(mode, args.segs, args.timeout_s)
        if not s:
            print("%-5s  NAO PRODUZIU NUMEROS" % mode)
            continue
        # O regime e' o ultimo terco: as primeiras amostras ainda sao o
        # carregador do modelo e o runtime a aquecer.
        tail = s[len(s) // 3:] if len(s) >= 3 else s
        out[mode] = (s[0], max(tail), s[-1])
        print("%-5s  amostras %2d | apos carregar %6.1f | maximo em regime %6.1f "
              "| ultimo %6.1f" % (mode, len(s), s[0], max(tail), s[-1]))

    if "seg" in out and "full" in out:
        d = out["full"][1] - out["seg"][1]
        print("\ndiferenca (full - seg) = %.0f MB" % d)
        print("o que a Fase A deixa de pagar = o modelo de embeddings "
              "(37,8 MB em ficheiro) e o runtime que o carrega")
    return 0


if __name__ == "__main__":
    sys.exit(main())