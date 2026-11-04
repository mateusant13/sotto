#!/usr/bin/env python3
# NO-BUG: UM KILL DO PROPRIO SHELL NAO E' UMA MORTE DO WORKER -- e o lote conta como vida. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""UM KILL DO PROPRIO SHELL NAO E' UMA MORTE DO WORKER -- e o lote conta como vida.

O DEFEITO MEDIDO (log do dono, `_main/webview-run.log`): das 10 `BRIDGE_SILENT`
anomalas do ficheiro, **9** sao seguidas, no mesmo pid e em menos de uma linha de
log, de um `BRIDGE_EXIT rc=1`. O `rc=1` nao e' a sentenca do worker: e' o
`TerminateProcess` do Windows, disparado pelo `_kill_and_restart` do shell. E o
`_wait` publicava-o como `BRIDGE_DEATH kind=error` -- painel vermelho e uma
recarga inteira contada como falha -- num worker que estava a transcrever.

O caso que doi' e' o das 19:36:40: `BRIDGE_CAPTION_SENT` as 19:36:38.389 e
`CAPTION_APPLIED count=200` as 19:36:39.901, e a janela de 30 s disparou na
mesma. A razao e' o `_note_progress`: so' `WORKER_STATS` com `blocks` a AVANCAR
re-arma o cao de guarda, e durante um lote longo (parakeet, `redux_mode=batch`)
o laco paralisa e o `blocks` congela.

ARMS
  1  `_kill_and_restart` MARCA o filho como morto pelo shell
  2  `_wait` depois disso publica `BRIDGE_EXIT ... killed=true` + `BRIDGE_KILLED`,
     NAO publica `BRIDGE_DEATH` e NAO conta a morte
  3  um crash a serio continua a publicar `BRIDGE_DEATH` e a contar (controlo)
  4  `REDUX_ENGINE_DONE`/`REDUX_BATCH_KICK`/`REDUX_MODE` re-armam o cao de guarda
  5  uma linha de stderr qualquer NAO re-arma (controlo: um laco atolado que
     reimprime nao compra vida eterna)

BRACO NEGATIVO (`--neg-arm`): duas copias da shell -- uma sem a marca do kill,
outra sem as `PROGRESS_TAGS` -- e as arms 2 e 4 tem de ficar RED em cada uma.
"""
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(HERE, "..", "app", "webview", "sotto_webview.py")


def load_module(path, name):
    if os.path.dirname(path) not in sys.path:
        sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Fake(object):
    def __init__(self):
        self.logs = []
        self.stderr_tail = []
        self.child = None
        self.last_exit = None
        self.spawns = 1
        self.captions = 0
        self.statuses = 0
        self.malformed = 0
        self.capturing = True
        self.stopped = False
        self.deaths = 0
        self.killed = False
        self._rss_at = 0.0
        self.armed = 0
        self.pending_error = {'state': 'exit', 'text': 'x', 'body': ''}
        # NAO remova: um `__getattr__` permissivo devolve uma FUNCAO para um nome
        # desconhecido, e `self.last_error or ...` ficava com essa funcao.
        self.last_error = None
        self.last_no_audio = None

    def log(self, msg):
        self.logs.append(str(msg))

    def _arm_silence(self):
        self.armed += 1

    def __getattr__(self, name):
        return lambda *a, **k: None


class Child(object):
    def __init__(self, rc):
        self.pid = 4242
        self._rc = rc
        self.terminated = 0

    def wait(self):
        return self._rc

    def terminate(self):
        self.terminated += 1

    def kill(self):
        self.terminated += 1


def run_arms(path, tag):
    mod = load_module(path, "shell_%s" % tag)
    cls = mod.WorkerBridge
    res = {}

    # ARM 1 -- o kill marca
    f = Fake()
    ch = Child(1)
    f.child = ch
    cls._kill_and_restart(f, "silent")
    res["1"] = bool(f.killed) and ch.terminated == 1
    print("ARM 1  killed=%s terminate=%d  %s"
          % (f.killed, ch.terminated, "PASS" if res["1"] else "FAIL"))

    # ARM 2 -- o kill nao vira morte
    f2 = Fake()
    f2.killed = True
    f2.child = Child(1)
    f2.stderr_tail = ["REDUX_ENGINE_DONE reason=interval engine=onnx"]
    before = f2.deaths
    cls._wait(f2)
    joined = "\n".join(f2.logs)
    res["2"] = ("killed=True" in joined and "BRIDGE_KILLED" in joined
                and "BRIDGE_DEATH" not in joined and f2.deaths == before)
    print("ARM 2  %s  %s" % (
        "killed=True + BRIDGE_KILLED, sem BRIDGE_DEATH" if res["2"]
        else ("DEATH publicado: %s" % [m for m in f2.logs if "BRIDGE_" in m][:2]),
        "PASS" if res["2"] else "FAIL"))

    # ARM 3 -- um crash a serio continua a ser morte (controlo)
    f3 = Fake()
    f3.child = Child(1)          # sem kill: morreu sozinho
    cls._wait(f3)
    j3 = "\n".join(f3.logs)
    res["3"] = "killed=False" in j3 and f3.deaths == 1 and "BRIDGE_KILLED" not in j3
    print("ARM 3  killed=false deaths=%d  %s"
          % (f3.deaths, "PASS" if res["3"] else "FAIL"))

    # ARM 4 -- o lote re-arma; ARM 5 -- stderr qualquer nao
    import io
    f4 = Fake()
    cls._pump(f4, io.StringIO("REDUX_ENGINE_DONE reason=interval\n"), "stderr")
    armed_batch = f4.armed
    f5 = Fake()
    cls._pump(f5, io.StringIO("qualquer coisa sem significado\n"), "stderr")
    armed_junk = f5.armed
    f6 = Fake()
    cls._pump(f6, io.StringIO("WORKER_STATS tag=tick blocks=9\n"
                              "REDUX_BATCH_KICK reason=interval\n"), "stderr")
    res["4"] = armed_batch == 1 and f6.armed == 1
    res["5"] = armed_junk == 0
    print("ARM 4  armaram: lote=%d (stats+batch=%d)  %s"
          % (armed_batch, f6.armed, "PASS" if res["4"] else "FAIL"))
    print("ARM 5  armaram com stderr inerte=%d  %s"
          % (armed_junk, "PASS" if res["5"] else "FAIL"))
    return res


def _mutant(needle, repl, name):
    # A shell e' CRLF: normalizar para `\n` e' o que faz as ancoras baterem (medido:
    # uma ancora terminada em `\n` nao casa com `\r\n`, e o braco negativo dizia
    # "ancora encontrada 0 vez(es)" em vez de provar o mutante).
    text = open(SHELL, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    if text.count(needle) != 1:
        print("NEG-ARM FAIL: ancora %r encontrada %d vez(es)" % (needle, text.count(needle)))
        return None
    path = os.path.join(os.path.dirname(SHELL), "_mutant_%s.py" % name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text.replace(needle, repl, 1))
    return path


def neg_arm():
    ok = True
    for name, needle, repl, must_fail in (
            ("kill", "        self.killed = child is not None\n", "        self.killed = False\n", "1"),
            ("tags", "                    if line.startswith(PROGRESS_TAGS):\n",
             "                    if False:\n", "4")):
        path = _mutant(needle, repl, name)
        if path is None:
            return 1
        try:
            proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--shell", path],
                                  capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        out = proc.stdout or ""
        failed = [ln for ln in out.splitlines() if ln.rstrip().endswith("FAIL")]
        caught = proc.returncode != 0 and any(
            ln.startswith("ARM %s " % must_fail) for ln in failed)
        print("NEG-ARM(%s) rc=%d arm_%s_red=%s  %s"
              % (name, proc.returncode, must_fail, caught, "PASS" if caught else "FAIL"))
        ok = ok and caught
    print("NEG-ARM PASS" if ok else "NEG-ARM FAIL")
    # RED as designed: um braco negativo que FUNCIONA sai 1, para o `:expectred`
    # da bateria exigir rc=1 E a frase `NEG-ARM PASS` no log.
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
    r = run_arms(shell, os.path.basename(shell).replace(".", "_"))
    ok = all(r.values())
    print("VERDICT:", "GREEN" if ok else "RED")
    raise SystemExit(0 if ok else 1)
