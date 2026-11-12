#!/usr/bin/env python3
"""exit-backstop-oracle -- o motor quente e' morto pelo PID, e o codigo dizia que nao (D-14)

O DEFEITO, medido por leitura 2026-11-12 e fechado no mesmo dia. `_exit_children`
devolvia o motor warm na lista de filhos quando `keep_warm` era falso (o
default), e o `_reap_children_for_exit` entao:

  * chamava `child.kill()` no shim `_WarmChild`, que LEVANTA de proposito
    (`RuntimeError('the shell does not own the warm engine')`) -> `EXIT_CHILD_KILL_FAILED`;
  * chamava `child.wait(...)`, que o shim NAO TEM -> `AttributeError` -> `EXIT_CHILD_STUCK`;
  * e o `exit_killer` matava o pid de qualquer maneira, que e' o que a `--help`
    promete ("closing Sotto is a request to stop paying 1.9 GB").

Duas linhas por saida a dizer que a shell tentou matar o que nunca possuiu, ao
lado de dois docstrings que diziam que o warm fica FORA do kill. A cura e' a
decisao ja' nomeada: DUAS listas -- `children` (matar + recolher, so' o que a
shell criou) e `backstop_pids` (so' o matador externo, o warm).

ARMS (nenhuma larga a app, nenhuma abre janela, nenhuma toca em audio):

  A1  as DUAS listas: o shim do warm nao entra em `children` e entra em
      `backstop_pids` -- e com `keep_warm` as duas ficam vazias
  A2  o worker e a sidecar continuam na lista de matar
  A3  estrutural: `_hard_exit` aceita `backstop_pids`, imprime-o em `EXIT_BEGIN`
      e passa `pids + backstop` ao matador
  A4  estrutural: `request_exit` le o backstop ANTES do `_hard_exit` e o entrega
  A5  VIVO, num processo filho: o `_hard_exit` REAL com um filho que a shell
      possui e um pid de backstop -- o log tem `EXIT_CHILD_REAPED` do primeiro,
      ZERO `EXIT_CHILD_KILL_FAILED`/`EXIT_CHILD_STUCK`, `EXIT_KILLER_ARMED` com
      os DOIS pids, o filho possuido MORTO e o de backstop VIVO depois da graca

`--neg-arm` corre quatro mutacoes, cada uma tem de cair pela SUA arm (rc=1 ao
apanhar).
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL_DIR = os.path.join(ROOT, "app", "webview")
SHELL = os.path.join(SHELL_DIR, "sotto_webview.py")
MUTANT = os.path.join(SHELL_DIR, "_exit_backstop_mutant.py")
CREATE_NO_WINDOW = 0x08000000
STARTUPINFO = subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW,
                                     wShowWindow=0)


def load_shell(path=SHELL, name="shell_under_exit_backstop"):
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Arms:
    def __init__(self):
        self.arms = []

    def arm(self, name, ok, detail=""):
        self.arms.append((name, bool(ok), detail))
        print("  %s %-64s %s" % ("PASS" if ok else "FAIL", name, detail))


def stub_shell(mod, child, keep_warm, sidecar=None):
    bridge = SimpleNamespace(child=child, keep_warm=keep_warm)
    return SimpleNamespace(bridge=bridge, _speaker_sidecar=sidecar,
                           _multivoice_watch=None)


class Owned:
    """Um filho de verdade, do lado do teste: `pid`, `kill`, `wait`."""

    def __init__(self, pid):
        self.pid = pid
        self.killed = 0
        self.waited = 0

    def kill(self):
        self.killed += 1

    def wait(self, timeout=None):
        self.waited += 1
        return 0


def run_lists(mod, arms):
    warm = mod._WarmChild(424242)
    owned = Owned(1234)
    sidecar = SimpleNamespace(child=Owned(5678))

    sh = stub_shell(mod, warm, False, sidecar=sidecar)
    kids = mod.SottoShell._exit_children(sh)
    back = mod.SottoShell._exit_backstop_pids(sh)
    arms.arm("A1a o shim do warm NAO entra na lista de matar",
             all(not isinstance(c, mod._WarmChild) for c in kids),
             "children=%r" % ([getattr(c, 'pid', None) for c in kids],))
    arms.arm("A1b o pid do warm entra no BACKSTOP",
             back == [424242], "backstop=%r" % (back,))
    sh_keep = stub_shell(mod, warm, True)
    arms.arm("A1c com keep_warm as duas listas ficam VAZIAS",
             mod.SottoShell._exit_children(sh_keep) == []
             and mod.SottoShell._exit_backstop_pids(sh_keep) == [],
             "children=%r backstop=%r"
             % (mod.SottoShell._exit_children(sh_keep),
                mod.SottoShell._exit_backstop_pids(sh_keep)))

    sh_owned = stub_shell(mod, owned, False, sidecar=sidecar)
    got = mod.SottoShell._exit_children(sh_owned)
    arms.arm("A2 worker e sidecar continuam na lista de matar",
             [c.pid for c in got] == [1234, 5678],
             "children=%r" % ([c.pid for c in got],))
    arms.arm("A2b um filho POSSUIDO nao vira backstop",
             mod.SottoShell._exit_backstop_pids(sh_owned) == [], "")


def shell_source(mod):
    with open(getattr(mod, "__file__", SHELL), encoding="utf-8", newline="") as fh:
        return fh.read()


def run_structure(mod, arms):
    text = shell_source(mod)
    tree = ast.parse(text)
    got = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                "_hard_exit", "_exit_backstop_pids"):
            got[node.name] = ast.get_source_segment(text, node) or ""
    hard = got.get("_hard_exit", "")
    req = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "request_exit":
            req = ast.get_source_segment(text, node) or ""
    req = req or ""
    arms.arm("A3 _hard_exit aceita backstop e o entrega ao matador",
             "backstop_pids=()" in hard
             and "_spawn_exit_killer(code, pids + backstop, say)" in hard
             and "backstop=%s" in hard,
             "sig=%s killer=%s" % ("backstop_pids=()" in hard,
                                   "_spawn_exit_killer(code, pids + backstop, say)" in hard))
    arms.arm("A4 request_exit le o backstop e o entrega",
             "_backstop = self._exit_backstop_pids()" in req
             and "backstop_pids=_backstop" in req
             and req.index("_exit_backstop_pids()") < req.index("_hard_exit("),
             "le=%s entrega=%s" % ("_exit_backstop_pids()" in req,
                                   "backstop_pids=_backstop" in req))


def pid_alive(pid):
    try:
        import psutil
        return bool(psutil.pid_exists(pid))
    except Exception:  # noqa: BLE001
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                             capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW,
                             startupinfo=STARTUPINFO)
        return str(pid) in (out.stdout or '')


KILLER_GRACE_S = 30.0


def run_live(arms):
    """A5: o `_hard_exit` REAL, num processo filho, com um pid de backstop."""
    run_dir = tempfile.mkdtemp(prefix="exit-backstop-")
    owned = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             creationflags=CREATE_NO_WINDOW, startupinfo=STARTUPINFO)
    warm = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=CREATE_NO_WINDOW, startupinfo=STARTUPINFO)
    try:
        child_script = os.path.join(run_dir, "child.py")
        with open(child_script, "w", encoding="utf-8") as fh:
            fh.write(CHILD_SOURCE)
        cfg = os.path.join(run_dir, "cfg.json")
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump({"shell": SHELL, "log": os.path.join(run_dir, "exit.log"),
                       "owned": owned.pid, "warm": warm.pid,
                       "grace": KILLER_GRACE_S}, fh)
        out = subprocess.run([sys.executable, child_script, cfg],
                             capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW, startupinfo=STARTUPINFO,
                             timeout=90)
        log_path = os.path.join(run_dir, "exit.log")
        text = ''
        if os.path.exists(log_path):
            with open(log_path, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        # O MATADOR ESCREVE ASSINCRONAMENTE no MESMO log: medido 2026-11-12, a
        # linha `EXIT_KILLER_ORPHAN` pode chegar centenas de ms depois de o shell
        # sair. Uma espera FIXA de 0,6 s lia "o warm sobreviveu" com o matador a
        # caminho -- a arm mediria o relogio do instrumento, nao o desfecho.
        # A LINHA E' O QUE SE ESPERA -- e nao a morte do pid: medido 2026-11-12,
        # o matador MATA primeiro e ESCREVE depois, logo sair do laco por
        # `pid morto` lia o log uma vez antes da linha e chamava-lhe ausencia.
        orphan_line = 'EXIT_KILLER_ORPHAN pid=%d' % warm.pid
        deadline = time.monotonic() + 8.0
        text = ''
        while time.monotonic() < deadline:
            with open(log_path, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
            if orphan_line in text:
                break
            time.sleep(0.1)
        owned_dead = not pid_alive(owned.pid)
        warm_alive = pid_alive(warm.pid)
        lines = [ln for ln in text.splitlines() if 'EXIT_' in ln]
        armed = next((ln for ln in lines if 'EXIT_KILLER_ARMED' in ln), '')
        arms.arm("A5a EXIT_BEGIN nomeia o backstop",
                 ('backstop=[%d]' % warm.pid) in text,
                 next((ln for ln in lines if 'EXIT_BEGIN' in ln), 'sem EXIT_BEGIN'))
        arms.arm("A5b zero EXIT_CHILD_KILL_FAILED / EXIT_CHILD_STUCK",
                 'EXIT_CHILD_KILL_FAILED' not in text and 'EXIT_CHILD_STUCK' not in text,
                 " ".join(ln.split(':', 2)[-1][:48] for ln in lines
                          if 'KILL_FAILED' in ln or 'STUCK' in ln) or 'nenhuma')
        arms.arm("A5c o filho POSSVIDO foi recolhido",
                 ('EXIT_CHILD_REAPED pid=%d' % owned.pid) in text,
                 next((ln for ln in lines if 'EXIT_CHILD_REAPED' in ln), ''))
        arms.arm("A5d o matador recebe os DOIS pids",
                 ('--child' not in armed) and ('children=[%d, %d]' % (owned.pid, warm.pid)) in armed,
                 armed[:110] or 'sem EXIT_KILLER_ARMED')
        # O MATADOR ENTREGA A PROMESSA, e e' por isso que o warm viaja como
        # backstop: depois de o shell sair, a VARREDURA dele mata qualquer filho
        # que sobreviva (`EXIT_KILLER_ORPHAN`). O que a lista unica estragava era
        # o REGISTO antes disso (`EXIT_CHILD_KILL_FAILED`/`EXIT_CHILD_STUCK` do
        # shim) -- medido aqui: o possuido morre pelo kill da shell, e o de
        # backstop morre pelo matador externo, nomeado.
        orphan = orphan_line in text
        arms.arm("A5e o matador externo mata o backstop e o NOMEIA",
                 owned_dead and (not warm_alive) and orphan,
                 "owned_dead=%s warm_alive=%s orphan=%s killer=%s"
                 % (owned_dead, warm_alive, orphan,
                    ' | '.join(ln.split('sotto: ')[-1][:54] for ln in text.splitlines()
                               if 'KILLER' in ln)))
    except subprocess.TimeoutExpired:
        arms.arm("A5 o filho do oraculo respondeu", False, 'timeout')
    finally:
        for proc in (owned, warm):
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
        for name in os.listdir(run_dir):
            try:
                os.unlink(os.path.join(run_dir, name))
            except OSError:
                pass
        try:
            os.rmdir(run_dir)
        except OSError:
            pass


def run_killer_skip(arms, killer_path=None):
    """A6: o shell ja' morreu antes de o matador abrir o handle -- e a varredura
    dos filhos ACONTECE mesmo assim (medido 2026-11-12: `no-handle` levava a
    varredura com ele num `return` cedo)."""
    run_dir = tempfile.mkdtemp(prefix="exit-killer-skip-")
    kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           creationflags=CREATE_NO_WINDOW, startupinfo=STARTUPINFO)
    try:
        sys.path.insert(0, SHELL_DIR)
        import importlib.util
        spec = importlib.util.spec_from_file_location("shell_identity", SHELL)
        shell = importlib.util.module_from_spec(spec)
        sys.modules["shell_identity"] = shell
        spec.loader.exec_module(shell)
        stamp = shell._proc_identity(kid.pid)
        log_path = os.path.join(run_dir, "killer.log")
        out = subprocess.run(
            [sys.executable, killer_path or os.path.join(SHELL_DIR, "exit_killer.py"),
             "--pid", "1", "--stamp", "", "--code", "0", "--grace-ms", "1000",
             "--log", log_path, "--child", "%d:%s" % (kid.pid, stamp)],
            capture_output=True, text=True, timeout=60,
            creationflags=CREATE_NO_WINDOW, startupinfo=STARTUPINFO)
        time.sleep(0.3)
        text = ''
        if os.path.exists(log_path):
            with open(log_path, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        killed = not pid_alive(kid.pid)
        arms.arm("A6 sem handle do shell a varredura dos filhos ACONTECE",
                 'EXIT_KILLER_SKIPPED' in text
                 and ('EXIT_KILLER_ORPHAN pid=%d' % kid.pid) in text and killed,
                 "rc=%s skipped=%s orphan=%s killed=%s"
                 % (out.returncode, 'EXIT_KILLER_SKIPPED' in text,
                    ('EXIT_KILLER_ORPHAN pid=%d' % kid.pid) in text, killed))
    except Exception as exc:  # noqa: BLE001
        arms.arm("A6 sem handle do shell a varredura dos filhos ACONTECE", False,
                 "erro=%r" % (exc,))
    finally:
        try:
            if kid.poll() is None:
                kid.kill()
                kid.wait(timeout=5)
        except Exception:  # noqa: BLE001
            pass
        for name in os.listdir(run_dir):
            try:
                os.unlink(os.path.join(run_dir, name))
            except OSError:
                pass
        try:
            os.rmdir(run_dir)
        except OSError:
            pass


CHILD_SOURCE = r'''
import importlib.util, json, os, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
sys.path.insert(0, os.path.dirname(cfg["shell"]))
spec = importlib.util.spec_from_file_location("shell_live_exit", cfg["shell"])
shell = importlib.util.module_from_spec(spec)
sys.modules["shell_live_exit"] = shell
spec.loader.exec_module(shell)
shell._open_log(cfg["log"])
shell.EXIT_ESCALATE_S = 2.0
shell.EXIT_KILLER_GRACE_S = float(cfg["grace"])
shell.EXIT_LOG_DRAIN_S = 0.2


class Owned:
    def __init__(self, pid):
        self.pid = pid

    def kill(self):
        import psutil
        try:
            psutil.Process(self.pid).kill()
        except Exception:
            pass

    def wait(self, timeout=None):
        import psutil, time
        end = time.monotonic() + (timeout or 5)
        while time.monotonic() < end:
            if not psutil.pid_exists(self.pid):
                return 0
            time.sleep(0.02)
        return 0


shell._exit_primary = lambda code: os._exit(0)
shell._hard_exit(7, "oracle:exit-backstop",
                 children=[Owned(cfg["owned"])], backstop_pids=[cfg["warm"]])
'''


def main(argv):
    neg = "--neg-arm" in argv
    mod = load_shell()
    arms = Arms()
    print("sotto: exit-backstop -- o warm e' morto pelo pid (D-14)")
    run_lists(mod, arms)
    run_structure(mod, arms)
    run_live(arms)
    run_killer_skip(arms)

    if neg:
        source = shell_source(mod)
        muts = [
            ("M1 o shim do warm volta a lista de matar", "A1a",
             lambda s: s.replace(
                 "                and not isinstance(child, _WarmChild)):",
                 "                ):", 1)),
            # Uma linha so', porque o fonte da shell tem regioes em CRLF e uma
            # mutacao que atravessa linhas com '\n' NAO APLICA (medido aqui: M2
            # saiu `MUTACAO-NAO-APLICOU` na primeira versao).
            ("M2 o pid do warm nunca entra no backstop", "A1b",
             lambda s: s.replace("                out.append(int(child.pid))",
                                 "                pass  # mutante: lista vazia", 1)),
            ("M3 o matador perde o backstop", "A3",
             lambda s: s.replace(
                 "    _spawn_exit_killer(code, pids + backstop, say)",
                 "    _spawn_exit_killer(code, pids, say)", 1)),
            ("M4 request_exit nao entrega o backstop", "A4",
             lambda s: s.replace(
                 "        _hard_exit(code, reason, children=_kids, backstop_pids=_backstop)",
                 "        _hard_exit(code, reason, children=_kids)", 1)),
        ]
        caught = 0
        for name, expected, mutate in muts:
            mutant = mutate(source)
            if mutant == source:
                print("  %-64s MUTACAO-NAO-APLICOU" % name)
                continue
            with open(MUTANT, "w", encoding="utf-8", newline="") as fh:
                fh.write(mutant)
            try:
                fresh = Arms()
                mmod = load_shell(MUTANT, name="shell_mutant_exit")
                run_lists(mmod, fresh)
                run_structure(mmod, fresh)
                red = [n for n, ok, _d in fresh.arms if not ok]
                hit = any(n.split()[0] == expected for n in red)
                caught += 1 if hit else 0
                print("  %-64s RED em %-6s %s"
                      % (name, expected, "caught" if hit else "NOT-CAUGHT red=%r" % (red,)))
            except Exception as exc:  # noqa: BLE001 -- fonte invalido == apanhado
                caught += 1
                print("  %-64s RED em %-6s caught (%r)" % (name, expected, exc))
            finally:
                try:
                    os.unlink(MUTANT)
                except OSError:
                    pass
        # M5 mora no MATADOR, nao na shell: o motor de mutacao acima so'
        # conhece a shell, por isso este e' explicito. Ele mede a classe do
        # defeito de 2026-11-12 -- a varredura que ia com o `return` cedo.
        killer = os.path.join(SHELL_DIR, "exit_killer.py")
        with open(killer, encoding="utf-8", newline="") as fh:
            ksrc = fh.read()
        kmut = ksrc.replace("    for spec in args.child or ():",
                            "    for spec in ():  # mutante: sem varredura", 1)
        if kmut == ksrc:
            # Um mutante que nao aplica NAO conta como apanhado: 4/5 e' FAIL.
            print("  %-64s MUTACAO-NAO-APLICOU" % "M5 a varredura nao olha filho nenhum")
        else:
            tmp_killer = os.path.join(tempfile.mkdtemp(prefix="exit-killer-mut-"),
                                      "exit_killer.py")
            try:
                with open(tmp_killer, "w", encoding="utf-8", newline="") as fh:
                    fh.write(kmut)
                fresh = Arms()
                run_killer_skip(fresh, tmp_killer)
                red = [n for n, ok, _d in fresh.arms if not ok]
                caught += 1 if red else 0
                print("  %-64s RED em %-6s %s"
                      % ("M5 a varredura nao olha filho nenhum", "A6",
                         "caught" if red else "NOT-CAUGHT red=%r" % (red,)))
            finally:
                shutil.rmtree(os.path.dirname(tmp_killer), ignore_errors=True)
        total = len(muts) + 1   # + M5, que mora no matador
        print("NEG-ARM: %s -- %d/%d mutantes apanhados"
              % ("PASS" if caught == total else "FAIL", caught, total))
        return 1 if caught == total else 0

    fails = [(n, d) for n, ok, d in arms.arms if not ok]
    print("VERDICT: arms=%d pass=%d fail=%d"
          % (len(arms.arms), len(arms.arms) - len(fails), len(fails)))
    print("VERDICT: %s" % ("PASS" if not fails else "FAIL"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
