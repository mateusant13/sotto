"""O COMMIT PRIVADO que cada motor deixa atras -- medido por CICLO, nao por opiniao.

NASCEU DE UM DM DO WATCHER (2026-11-09): o worker elevado (pid 56316) tinha
`rss=1664 MiB` com `private=4615 MiB` (2,8x), e a leitura proposta foi "cada carga deixa
commit para tras" -- um ciclo carrega/descarrega que nunca devolve memoria, com 12
`BRIDGE_LOAD_MS` num dia como assinatura. Um numero de commit sem o CICLO ao lado nao
distingue tres coisas muito diferentes:

  a) o commit de UM modelo carregado   -> custo normal, devolvido quando ele sai;
  b) um residuo POR CICLO              -> fuga, e N cargas a multiplicam;
  c) um plato que o processo segura    -> arenas do ORT (BFC) e caches por stream; nao
                                          cresce com o tempo e NAO e' fuga.

Este instrumento responde (a) e (b) com os caminhos REAIS do produto:
`transcribe.OnnxParakeet` (as quatro sessoes do passe de fundo), `sotto_worker.session_options`
+ as tres sessoes ORT do nemotron, e `onnxruntime_genai.Model` do motor ao vivo. Cada braco
mede `WorkingSetSize` e `PrivateUsage` ANTES, CARREGADO e depois de SOLTAR (`del` + `gc`), e
publica a rampa por ciclo -- porque e' a rampa, nao o pico, que diz se ha fuga.

O INSTRUMENTO JULGA-SE A SI PROPRIO (`--neg-arm`): aloca 200 MiB e EXIGE que o commit suba
pelo menos 190 MiB. Sem esse braco, um `GetProcessMemoryInfo` mal declarado devolve 0 e o
relatorio imprime "0,0 MiB de fuga" -- que foi exactamente o que aconteceu na primeira
execucao desta sonda (argtypes/restype ausentes, todos os numeros a zero e nenhum aviso).
"""
import argparse
import ctypes
import gc
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER_DIR = os.path.join(ROOT, "worker")
MODELS = os.path.join(WORKER_DIR, "models")
PARAKEET = os.path.join(MODELS, "parakeet-redux-onnx-int4")
NEMOTRON = os.path.join(MODELS, "nemotron-3.5-asr-ptbr-onnx-int4")

MiB = 1048576.0


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t)]


def mem():
    """(rss, commit, pico_commit) em MiB. Zero NAO e' resposta: levanta."""
    k = ctypes.WinDLL('kernel32')
    psapi = ctypes.WinDLL('psapi')
    k.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC),
                                           wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    if not psapi.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise SystemExit('GetProcessMemoryInfo falhou (err=%d)'
                         % ctypes.get_last_error())
    if c.PrivateUsage == 0 or c.WorkingSetSize == 0:
        raise SystemExit('instrumento devolveu 0 (rss=%d commit=%d) -- a medicao nao '
                         'existe' % (c.WorkingSetSize, c.PrivateUsage))
    return (c.WorkingSetSize / MiB, c.PrivateUsage / MiB,
            c.PeakPagefileUsage / MiB)


def _imports():
    sys.path.insert(0, WORKER_DIR)
    sys.path.insert(0, PARAKEET)
    import onnxruntime as ort
    import transcribe
    import sotto_worker
    return ort, transcribe, sotto_worker


def arm_parakeet(cycles):
    """O passe de FUNDO: quatro sessoes, o mesmo construtor que o worker usa."""
    _ort, transcribe, _w = _imports()
    base = mem()
    print('  baseline                rss=%7.1f commit=%7.1f' % (base[0], base[1]))
    frees = []
    peak = 0.0
    for i in range(1, cycles + 1):
        t0 = time.perf_counter()
        obj = transcribe.OnnxParakeet(Path(PARAKEET))
        load_s = time.perf_counter() - t0
        loaded = mem()
        del obj
        gc.collect()
        time.sleep(0.3)
        freed = mem()
        frees.append(freed[1])
        peak = max(peak, loaded[1] - base[1])
        print('  ciclo %d  load %5.2fs  carregado rss=%7.1f commit=%7.1f  |  solto '
              'rss=%7.1f commit=%7.1f'
              % (i, load_s, loaded[0], loaded[1], freed[0], freed[1]))
    slope = (frees[-1] - frees[0]) / max(1, len(frees) - 1)
    print('  COMMIT DA CARGA: +%.1f MiB     RESIDUO POR CICLO: %.1f MiB'
          % (peak, slope))
    return peak, slope


def arm_nemotron_ort():
    """As TRES sessoes ORT do motor AO VIVO, com os `SessionOptions` do worker."""
    ort, _t, sw = _imports()
    base = mem()
    print('  baseline                rss=%7.1f commit=%7.1f' % (base[0], base[1]))
    kept = []
    for name, enc in (("encoder.onnx", True), ("decoder.onnx", False),
                      ("joint.onnx", False)):
        so = sw.session_options(ort, "", 2, enc)
        t0 = time.perf_counter()
        sess = ort.InferenceSession(os.path.join(NEMOTRON, name), so,
                                    providers=["CPUExecutionProvider"])
        dt = time.perf_counter() - t0
        kept.append(sess)
        now = mem()
        print('  %-14s %5.2fs  rss=%7.1f commit=%7.1f  (+%.1f commit)'
              % (name, dt, now[0], now[1], now[1] - base[1]))
    total = mem()[1] - base[1]
    del kept
    gc.collect()
    after = mem()
    print('  TRES SESSOES: +%.1f MiB commit  (depois de soltar: %.1f -> residuo %.1f)'
          % (total, after[1], after[1] - base[1]))
    return total


def arm_genai_model():
    """`onnxruntime_genai.Model` do motor ao vivo -- so as PESOS, sem sessao ORT."""
    import onnxruntime_genai as og
    base = mem()
    t0 = time.perf_counter()
    model = og.Model(NEMOTRON)
    dt = time.perf_counter() - t0
    now = mem()
    print('  og.Model %5.2fs  rss=%7.1f commit=%7.1f  (+%.1f commit, razao commit/rss '
          '%.2fx)' % (dt, now[0], now[1], now[1] - base[1],
                      (now[1] - base[1]) / max(0.1, now[0] - base[0])))
    del model
    gc.collect()
    return now[1] - base[1]


def run_neg_arm():
    """O INSTRUMENTO VE MEMORIA? Aloca 200 MiB e exige o commit a acompanhar."""
    blob = bytearray(200 * 1024 * 1024)
    for i in range(0, len(blob), 4096):
        blob[i] = 1
    before = mem()
    blob2 = bytearray(200 * 1024 * 1024)
    for i in range(0, len(blob2), 4096):
        blob2[i] = 1
    after = mem()
    delta = after[1] - before[1]
    ok = delta >= 190.0
    print('NEG-ARM: %s -- uma alocacao de 200 MiB moveu o commit em %.1f MiB'
          % ('PASS' if ok else 'FAIL', delta))
    del blob, blob2
    return ok


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--cycles', type=int, default=3)
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--only', default='')
    args = ap.parse_args(argv)

    if args.neg_arm:
        # A CONVENCAO DA CASA: o braco negativo devolve 1 quando APANHA. Um braco que
        # devolve 0 ao apanhar passa por instrumento normal e o `:expectred` fica a
        # espera de 1 para sempre -- a classe que ja' custou cinco passos nesta bateria.
        return 1 if run_neg_arm() else 0

    print('COMMIT POR CICLO -- %.0f MiB de baseline do interprete' % mem()[0])
    peaks, slopes = {}, {}
    if not args.only or args.only == 'parakeet':
        print('PARAKEET (passe de fundo)')
        peaks['parakeet'], slopes['parakeet'] = arm_parakeet(max(2, args.cycles))
    if not args.only or args.only == 'nemotron':
        print('NEMOTRON (motor ao vivo)')
        peaks['nemotron'] = arm_nemotron_ort()
    if not args.only or args.only == 'genai':
        print('GENAI (pesos do motor ao vivo)')
        peaks['genai'] = arm_genai_model()

    print('SUMARIO ' + ' '.join('%s=%.1fMiB' % (k, v) for k, v in peaks.items()))
    if 'parakeet' in slopes:
        print('RESIDUO POR CICLO parakeet=%.1f MiB  (12 ciclos -> %.0f MiB)'
              % (slopes['parakeet'], slopes['parakeet'] * 12))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
