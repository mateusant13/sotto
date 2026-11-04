#!/usr/bin/env python3
# NO-BUG: A MORTE DO WORKER TEM DE PUBLICAR A CAUSA -- nao tres linhas de stats. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""A MORTE DO WORKER TEM DE PUBLICAR A CAUSA -- nao tres linhas de stats.

O DEFEITO (medido 2026-11-02, na sessao do dono a jogar). O worker morreu DUAS
vezes com `rc=1` (19:22:29 e 19:36:40) e a cauda de stderr que o `BRIDGE_DEATH`
publicava tinha **tres** linhas:

    WORKER_STATS tag=tick blocks=7878 ... peak_out=1.000000 ...
    REDUX_BATCH_KICK reason=interval engine=parakeet audio_s=15.0 kicks=46

O traceback vem ANTES das linhas de stats, por isso ficou de fora -- e as duas
mortes ficaram indiagnosticaveis. Cada morte custa uma recarga de 14-26 s
(`BRIDGE_LOAD_MS` medido), ou seja, e' exactamente o "modelo carregando toda
hora" que o dono reporta.

A CORRECCAO: a cauda guarda `STDERR_TAIL_MAX` (40) linhas e a morte publica uma
linha `BRIDGE_DEATH_CAUSE <excecao>`, que NOMEIA o que matou o worker.

ARMS (com um FILHO REAL, nao um dicionario)
  A  `_pump` num stderr de 60 linhas guarda as ULTIMAS 40, inteiras
  B  a ultima linha guardada e' a excepcao do traceback
  C  `_wait` de um filho que saiu 1 publica `BRIDGE_DEATH_CAUSE RuntimeError: boom`
  D  uma cauda limpa (so' stats) NAO inventa uma causa (controlo)
  E  uma linha em WIDESTRING (o ONNX Runtime escreve assim) fica LEGIVEL -- medido
     19:00:24: a cauda do dono tinha `\u0000\u001b\u0000[\u00000\u0000;...`

BRACO NEGATIVO (`--neg-arm`): uma copia da shell com `STDERR_TAIL_MAX = 3` --
o valor de antes. A arm A e a C tem de ficar RED nessa copia.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(HERE, "..", "app", "webview", "sotto_webview.py")

CHILD = r'''
import sys
for i in range(60):
    sys.stderr.write("FILLER line %d\n" % i)
sys.stderr.write("Traceback (most recent call last):\n")
sys.stderr.write('  File "sotto_worker.py", line 1, in <module>\n')
sys.stderr.write("RuntimeError: boom\n")
sys.stderr.flush()
sys.exit(1)
'''


def load_module(path, name):
    if os.path.dirname(path) not in sys.path:
        sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Fake(object):
    """O `self` minimo do `WorkerBridge`: so' o que o `_pump`/`_wait` tocam."""

    def __init__(self):
        self.stderr_tail = []
        self.logs = []
        self.last_worker_stats = None
        self.child = None
        self.last_exit = None
        self.spawns = 1
        self.captions = 0
        self.statuses = 0
        self.malformed = 0
        self.capturing = True
        self.stopped = True      # a morte e' publicada; o resto do `_wait` nao corre
        self.deaths = 0

    def log(self, msg):
        self.logs.append(str(msg))

    def __getattr__(self, name):
        return lambda *a, **k: None


def run_arms(path, label):
    mod = load_module(path, "shell_%s" % label)
    cap = getattr(mod, "STDERR_TAIL_MAX", None)
    cls = mod.WorkerBridge
    fake = Fake()

    import io
    lines = "".join("FILLER line %d\n" % i for i in range(60))
    lines += ('Traceback (most recent call last):\n'
              '  File "sotto_worker.py", line 1, in <module>\n'
              "RuntimeError: boom\n")
    cls._pump(fake, io.StringIO(lines), "stderr")

    a_ok = cap == 40 and len(fake.stderr_tail) == 40
    b_ok = fake.stderr_tail[-1].strip() == "RuntimeError: boom"
    print("A  STDEER_TAIL_MAX=%r guardadas=%d  %s"
          % (cap, len(fake.stderr_tail), "PASS" if a_ok else "FAIL"))
    print("B  ultima=%r  %s" % (fake.stderr_tail[-1] if fake.stderr_tail else None,
                                "PASS" if b_ok else "FAIL"))

    # Um FILHO real: `_wait` chama `child.wait()` e le' `child.pid`, logo um
    # `CompletedProcess` nao serve (medido: `AttributeError: 'CompletedProcess'
    # object has no attribute 'wait'`).
    proc = subprocess.Popen([sys.executable, "-c", CHILD],
                            stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    err = proc.stderr.read()
    fake2 = Fake()
    fake2.child = proc
    fake2.stderr_tail = err.splitlines()
    if len(fake2.stderr_tail) > cap:
        fake2.stderr_tail = fake2.stderr_tail[-cap:]
    cls._wait(fake2)
    causes = [m for m in fake2.logs if m.startswith("BRIDGE_DEATH_CAUSE")]
    c_ok = bool(causes) and "RuntimeError: boom" in causes[0]
    print("C  %s  %s" % (causes[0] if causes else "(sem BRIDGE_DEATH_CAUSE)",
                         "PASS" if c_ok else "FAIL"))

    proc2 = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(1)"],
                             stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    fake3 = Fake()
    fake3.stderr_tail = ["WORKER_STATS tag=tick blocks=10 peak=0.5",
                         "REDUX_BATCH_KICK reason=interval engine=parakeet"]
    fake3.child = proc2
    cls._wait(fake3)
    d_ok = not [m for m in fake3.logs if m.startswith("BRIDGE_DEATH_CAUSE")]
    print("D  cauda limpa -> %s  %s"
          % ("sem causa (correcto)" if d_ok else "inventou uma causa",
             "PASS" if d_ok else "FAIL"))

    # E: o ONNX Runtime escreve widestring; lida byte a byte a linha fica ilegivel.
    # O que a shell VÊ: os bytes de um widestring lidos por um codec de 1 byte.
    mangled = "".join(c + "\x00" for c in "\x1b[0;93monnxruntime warning: fallback")
    fake4 = Fake()
    cls._pump(fake4, io.StringIO(mangled + "\n"), "stderr")
    e_line = fake4.stderr_tail[-1] if fake4.stderr_tail else ""
    e_ok = ("\x00" not in e_line) and ("onnxruntime" in e_line)
    print("E  %r  %s" % (e_line[:60], "PASS" if e_ok else "FAIL"))

    return [a_ok, b_ok, c_ok, d_ok, e_ok]


def neg_arm():
    text = open(SHELL, encoding="utf-8", newline="").read()
    needle = "STDERR_TAIL_MAX = 40"
    if needle not in text:
        print("NEG-ARM FAIL: a constante nao esta' na shell")
        return 1
    guard = "if '\\x00' in line:"
    if guard not in text:
        print("NEG-ARM FAIL: a guarda do widestring nao esta' na shell")
        return 1
    path = os.path.join(os.path.dirname(SHELL), "_mutant_tail3.py")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text.replace(needle, "STDERR_TAIL_MAX = 3", 1)
                     .replace(guard, "if False:", 1))
    try:
        proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--shell", path],
                              capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    out = proc.stdout or ""
    caught = proc.returncode != 0 and "A  STDEER_TAIL_MAX=3" in out and "A  " in out
    a_fail = "guardadas=3  FAIL" in out
    e_fail = any(ln.startswith("E  ") and ln.rstrip().endswith("FAIL")
                 for ln in out.splitlines())
    for ln in out.splitlines():
        if ln.startswith(("A ", "E ")):
            print("   ", ln)
    ok = caught and a_fail and e_fail
    print("NEG-ARM mutant rc=%d A_guarda_3=%s E_widestring=%s  %s"
          % (proc.returncode, a_fail, e_fail, "PASS" if ok else "FAIL"))
    print("NEG-ARM PASS" if ok else "NEG-ARM FAIL")
    # RED as designed: um braco negativo que APANHA o mutante sai 1, e 0 quando nao
    # apanha -- e' assim que o `:expectred` da bateria exige rc=1 E `NEG-ARM PASS`.
    return 1 if ok else 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--neg-arm" in argv:
        raise SystemExit(neg_arm())
    shell = SHELL
    for i, a in enumerate(argv):
        if a == "--shell":
            shell = argv[i + 1]
        elif a.startswith("--shell="):
            shell = a.split("=", 1)[1]
    res = run_arms(shell, os.path.basename(shell).replace(".", "_"))
    ok = all(res)
    print("VERDICT:", "GREEN" if ok else "RED")
    raise SystemExit(0 if ok else 1)
