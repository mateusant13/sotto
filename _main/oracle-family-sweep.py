#!/usr/bin/env python3
"""UMA VARREDURA DE FAMILIA, COM TECTO E CACHE -- nao um laco de shell.

O DEFEITO QUE ISTO FECHA (medido 2026-11-27, DM `dm-3e2757b5705d76bcf5db`): uma
lane desta casa correu a familia do YouTube como um laco `for` em `bash`:

    for f in _main/*youtube*oracle*.py; do
        timeout 180 H:/Python311/python.exe "$f" > I:/cc-tmp/sweep_$base.out
    done

O watcher mediu o resultado e mandou o card: `python.exe(45980)` =
`_main/youtube-cdp-source-oracle.py --neg-arm`, **io 1.50425 MB/s**, veredicto
`disk.saturated` em H:. A atribuicao estava certa -- era o MEU laco --, e o custo
tinha DUAS causas que nenhum tecto consertava:

  1. **O shell de 1,5 MB era lido do disco por cada um dos 41 oraculos.** Nenhum
     deles consultava o cache por conteudo que ja' existe (`_main/_stepcache.py`),
     e o laco nao parava entre processos: 41 arranques de Python a ler o mesmo
     ficheiro, todos a 100 % de prioridade.
  2. **Nada declarava teto**: nem fios, nem prioridade, nem prazo, nem quanto do
     disco. O `timeout 180` de cada volta e' um prazo por PASSO, nunca um tecto.

AS TRES COISAS QUE ESTE FICHEIRO FAZ, e a ordem e' a da lei do custo:

  * **NAO REFAZER** -- o cache por conteudo decide antes de arrancar o filho
    (`_stepcache.py check`); um `HIT` imprime a linha e nao paga arranque nenhum.
  * **UM DE CADA VEZ** -- um filho por vez, e o filho herda `OMP/MKL/OPENBLAS/
    NUMEXPR/VECLIB=1` e `BELOW_NORMAL_PRIORITY_CLASS`: o trabalho COMPLETA, e a
    mao do dono nunca espera atras dele.
  * **DIZ O QUE FALTOU** -- no fim publica `ligados/sem_passo`, os que falharam, e
    o `MISS/HIT` de cada um. Um oraculo que nao corre nao e' um oraculo aprovado.

O QUE ELE NAO FAZ: nao julga o veredicto de um oraculo (isso e' do proprio oraculo,
pelo rc) e nao corre os passos `heavy`. Um `rc != esperado` e' reportado com o
nome, nunca escondido.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STEPCACHE = os.path.join(HERE, "_stepcache.py")
PYTHON = sys.executable or "python"

#: O FILHO NAO HERDA A MAQUINA INTEIRA (medido 2026-11-26 num mutante que subia um
#: WebView2: 300,2 % de um nucleo durante 7,1 s sem tecto nenhum). Uma biblioteca
#: de algebra por processo e' o que faz um oraculo parecer um benchmark.
CHILD_ENV_PINS = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}

#: `BELOW_NORMAL_PRIORITY_CLASS` -- o dono nunca espera atras de um gate.
BELOW_NORMAL = 0x00004000
CREATE_NO_WINDOW = 0x08000000


def _child_env():
    env = dict(os.environ)
    env.update(CHILD_ENV_PINS)
    return env


def _popen(cmd):
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = BELOW_NORMAL | CREATE_NO_WINDOW
    return subprocess.Popen(cmd, cwd=ROOT, env=_child_env(),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            **kw)


def discover(patterns, exclude=()):
    """Os oraculos da familia, ordenados, sem mutantes nem neg-arms."""
    found = []
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".py") or "oracle" not in name:
            continue
        if not any(fnmatch.fnmatch(name, p) for p in patterns):
            continue
        if any(x in name for x in ("mutant", "-neg")):
            continue
        if any(fnmatch.fnmatch(name, x) for x in exclude):
            continue
        found.append(name)
    return found


def deps_for(name):
    """As dependencias do passo: o proprio oraculo e o shell sob teste.

    O `_stepcache` recusa um passo sem deps (nada o invalida), logo a lista nunca
    e' vazia: o oraculo muda -> o passo muda.
    """
    deps = [os.path.join("_main", name)]
    for extra in ("app/webview/sotto_webview.py",
                  "app/webview/youtube_window.py",
                  "app/webview/youtube_reveal.py",
                  "app/webview/youtube_captions.py",
                  "app/webview/youtube_cdp_source.py"):
        if os.path.isfile(os.path.join(ROOT, extra)):
            deps.append(extra)
    return deps


def cache_check(step, deps, log):
    cmd = [PYTHON, STEPCACHE, "check", "--step", step,
           "--deps", ";".join(deps), "--expect-rc", "0"]
    if log and os.path.isfile(log):
        cmd += ["--log", log]
    try:
        out = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=60)
    except Exception:                        # noqa: BLE001 -- cache is optional
        return False, "no-cache"
    text = (out.stdout or b"").decode("utf-8", "replace")
    return text.lstrip().startswith("HIT"), text.strip().splitlines()[0] if text else ""


def cache_record(step, deps, rc, log):
    cmd = [PYTHON, STEPCACHE, "record", "--step", step, "--deps",
           ";".join(deps), "--rc", str(rc), "--expect-rc", "0"]
    if log:
        cmd += ["--log", log]
    try:
        subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=60)
    except Exception:                        # noqa: BLE001
        pass


def run_one(name, logdir, timeout_s):
    """Um oraculo, com prioridade baixa e prazo. Devolve (rc, wall_s, path)."""
    log = os.path.join(logdir, "sweep_%s.out" % name.replace(".py", ""))
    t0 = time.monotonic()
    try:
        proc = _popen([PYTHON, os.path.join("_main", name)])
        try:
            out, _ = proc.communicate(timeout=timeout_s)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
            rc = 124
    except Exception as exc:                 # noqa: BLE001
        out = ("<spawn failed: %r>" % (exc,)).encode()
        rc = 9020
    wall = time.monotonic() - t0
    try:
        os.makedirs(logdir, exist_ok=True)
        with open(log, "wb") as fh:
            fh.write(out or b"")
    except Exception:                        # noqa: BLE001
        log = ""
    return rc, wall, log


def main(argv=None):
    ap = argparse.ArgumentParser(description="varredura de uma familia de oraculos, com tecto e cache")
    ap.add_argument("--family", default="youtube",
                    help="a substring que nomeia a familia (ex.: youtube, yt-)")
    ap.add_argument("--logdir", default=os.path.join("I:", os.sep, "cc-tmp"))
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="prazo POR PASSO (nao e' um tecto de CPU)")
    ap.add_argument("--no-cache", action="store_true",
                    help="ignora o cache (mede o custo de uma corrida fria)")
    ap.add_argument("--only", default=None, help="substring extra para filtrar")
    args = ap.parse_args(argv)

    patterns = ["*%s*oracle*.py" % args.family, "%s*oracle*.py" % args.family]
    names = discover(patterns)
    if args.only:
        names = [n for n in names if args.only in n]
    if not names:
        print("FAMILY-SWEEP CANNOT-MEASURE why=no-oracles family=%s" % args.family)
        return 3

    print("FAMILY-SWEEP family=%s oracles=%d ceiling=1-child BELOW_NORMAL "
          "threads=1 timeout_s=%.0f cache=%s"
          % (args.family, len(names), args.timeout,
             "off" if args.no_cache else "on"))

    t_all = time.monotonic()
    hits, misses, fails, bad = 0, 0, 0, []
    total_wall = 0.0
    for name in names:
        step = name[:-3]
        deps = deps_for(name)
        log = os.path.join(args.logdir, "sweep_%s.out" % step)
        if not args.no_cache:
            hit, _why = cache_check(step, deps, log)
            if hit:
                hits += 1
                print("  HIT   %-42s cache" % step)
                continue
        misses += 1
        rc, wall, log = run_one(name, args.logdir, args.timeout)
        total_wall += wall
        cache_record(step, deps, rc, log)
        ok = (rc == 0)
        if not ok:
            fails += 1
            bad.append((step, rc))
        print("  %-5s %-42s rc=%d wall=%.1fs" % ("PASS" if ok else "FAIL", step, rc, wall))

    wall_all = time.monotonic() - t_all
    print("")
    print("SUMMARY oracles=%d hit=%d miss=%d fail=%d child_wall_s=%.1f total_wall_s=%.1f"
          % (len(names), hits, misses, fails, total_wall, wall_all))
    for step, rc in bad:
        print("  RED: %s rc=%d" % (step, rc))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
