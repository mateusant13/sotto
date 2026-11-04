#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: P3.3 do roadmap de observabilidade (capacidade): mede quanto do custo do cache da bateria e arranque de processo e quanto e o resolvedor, para o corte poder ser medido em vez de achado
"""STEPCACHE COST PROBE -- quanto custa o cache da bateria, e quanto disso e arranque.

A LINHA (roadmap de observabilidade, P3.3, 2026-10-23): *"Custo do cache da bateria: 33 s com
100/115 em cache ~ 0,33 s por passo so para o resolver; medir quanto e arranque de processo e
cortar"*. Nenhum dos tres numeros dessa frase tinha instrumento ao lado, e por isso esta sonda
existe: ela nao "optimiza" nada, mede primeiro.

O QUE MEDE, e cada peca com o seu porque:

    startup     `python -c "pass"` -- o preco de ARRANCAR um interpretador. E o piso de cada
                chamada a `_main/_stepcache.py check`, porque a bateria o invoca por processo
                (o `for /f ... in ('python _main/_stepcache.py check ...')` da `.cmd`).
    resolver    o custo REAL de uma verificacao de cache, medida por dentro: carregar o motor,
                ler o estado e calcular o fingerprint das deps de um passo. E isto que sobra
                depois de o arranque ser pago, e e o que um corte teria de atacar.
    end-to-end  `python _main/_stepcache.py check ...` num passo real, por processo -- a soma
                que a bateria paga hoje.

AS DEPS SAO AS VERDADEIRAS (lidas do estado), nao um fixture: uma sonda que mede um passo de
brinquedo mede o brinquedo. E por isso que este ficheiro le `_cache/battery-steps.json`.

FALSIFICADOR (o que a recusa): com um estado inexistente ou ilegivel, a sonda imprime
`NO-VERDICT` e rc=2 -- nunca um numero. `--neg-arm` exercita exactamente esse braco, mais um
estado vazio e um passo que nao existe, e imprime `NEG-ARM PASS` com rc=1 por desenho.

    python _main\\stepcache-cost-probe.py            # tabela + PROBE-VERDICT (rc=0 medido)
    python _main\\stepcache-cost-probe.py --neg-arm  # rc=1 POR DESENHO
    python _main\\stepcache-cost-probe.py --json

Sem rede. Le o estado e as deps; nao escreve nada no repo. NAO esta na bateria ainda: enquanto
nao tiver passo proprio e pin, o item P3.3 esta MEDIDO, nao entregue.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)
ENGINE_REL = os.path.join("_main", "_stepcache.py")
STATE_REL = os.path.join("_cache", "battery-steps.json")
LOG_DIR_REL = os.path.join("_main", "_audit-verify")
SAMPLES = 5


def _load_engine(root):
    path = os.path.join(root, ENGINE_REL)
    spec = importlib.util.spec_from_file_location("_cost_probe_stepcache", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.REPO = os.path.abspath(root)
    return module


def _median(values):
    return statistics.median(values) if values else None


def measure_startup(python="python"):
    times = []
    for _ in range(SAMPLES):
        t0 = time.perf_counter()
        subprocess.run([python, "-c", "pass"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        times.append(time.perf_counter() - t0)
    return _median(times), times


def measure_resolver(root, steps, samples=SAMPLES):
    """O custo por dentro: motor + estado + fingerprint de um passo, `samples` vezes."""
    engine = _load_engine(root)
    state = json.loads(open(os.path.join(root, STATE_REL), "rb").read().decode("utf-8"))["steps"]
    per_step = {}
    for name in steps:
        entry = state.get(name) or {}
        deps = entry.get("deps") or []
        if not deps:
            per_step[name] = None
            continue
        times = []
        for _ in range(samples):
            t0 = time.perf_counter()
            engine.fingerprint(deps)
            times.append(time.perf_counter() - t0)
        per_step[name] = _median(times)
    return per_step


def measure_end_to_end(root, steps, python="python"):
    out = {}
    for name in steps:
        entry = (json.loads(open(os.path.join(root, STATE_REL), "rb").read().decode("utf-8"))
                 ["steps"].get(name) or {})
        deps = entry.get("deps") or []
        if not deps:
            out[name] = None
            continue
        log = os.path.join(root, LOG_DIR_REL, os.path.basename(str(entry.get("log") or "")))
        argv = [python, os.path.join(root, ENGINE_REL), "check", "--step", name,
                "--expect-rc", str(entry.get("expect_rc", 0)),
                "--deps", ";".join(deps), "--log", log,
                "--state", os.path.join(root, STATE_REL)]
        t0 = time.perf_counter()
        subprocess.run(argv, check=False, cwd=root,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        out[name] = time.perf_counter() - t0
    return out


def pick_steps(root, limit):
    """Passos reais com deps, tirados do estado -- os primeiros `limit` em ordem de nome."""
    payload = json.loads(open(os.path.join(root, STATE_REL), "rb").read().decode("utf-8"))
    steps = payload.get("steps") or {}
    chosen = [name for name in sorted(steps) if (steps[name] or {}).get("deps")]
    return chosen[:limit]


def run(root, limit):
    if not os.path.isfile(os.path.join(root, STATE_REL)):
        return None, "estado ausente: %s" % STATE_REL
    try:
        steps = pick_steps(root, limit)
    except (OSError, ValueError) as exc:
        return None, "estado ilegivel: %s" % exc
    if not steps:
        return None, "nenhum passo com deps no estado"
    startup, startup_all = measure_startup()
    resolver = measure_resolver(root, steps)
    e2e = measure_end_to_end(root, steps)
    return {
        "steps": steps,
        "startup_s": startup,
        "startup_samples": startup_all,
        "resolver_s": resolver,
        "end_to_end_s": e2e,
    }, None


def summarise(report):
    steps = report["steps"]
    startup = report["startup_s"]
    resolver = [v for v in report["resolver_s"].values() if v is not None]
    e2e = [v for v in report["end_to_end_s"].values() if v is not None]
    med_resolver = _median(resolver)
    med_e2e = _median(e2e)
    overhead = (med_resolver / med_e2e) if (med_resolver and med_e2e) else None
    return {
        "sampled": len(steps),
        "startup_ms": None if startup is None else startup * 1000.0,
        "resolver_ms": None if med_resolver is None else med_resolver * 1000.0,
        "end_to_end_ms": None if med_e2e is None else med_e2e * 1000.0,
        "resolver_share": overhead,
        "projected_100": None if med_e2e is None else med_e2e * 100.0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="custo do cache da bateria: arranque vs resolvedor")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--limit", type=int, default=8,
                        help="quantos passos reais medir (default 8)")
    parser.add_argument("--neg-arm", action="store_true", help="rc=1 POR DESENHO")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    root = os.path.abspath(args.root)

    if args.neg_arm:
        arms = []
        # braco 1: estado ausente -> NO-VERDICT, nunca um numero
        report, error = run(os.path.join(root, "nao-existe"), args.limit)
        arms.append(("missing-state", report is None and bool(error), error or "deu um numero"))
        # braco 2: estado ilegivel -> NO-VERDICT
        bogus = os.path.join(os.environ.get("TMPDIR") or os.path.dirname(root), "probe-bogus-root")
        os.makedirs(os.path.join(bogus, "_cache"), exist_ok=True)
        with open(os.path.join(bogus, "_cache", "battery-steps.json"), "wb") as fh:
            fh.write(b"{not json")
        report, error = run(bogus, args.limit)
        arms.append(("corrupt-state", report is None and bool(error), error or "deu um numero"))
        # braco 3: estado valido mas vazio -> NO-VERDICT ("nenhum passo")
        empty = os.path.join(os.environ.get("TMPDIR") or os.path.dirname(root), "probe-empty-root")
        os.makedirs(os.path.join(empty, "_cache"), exist_ok=True)
        with open(os.path.join(empty, "_cache", "battery-steps.json"), "wb") as fh:
            fh.write(b'{"version": 1, "steps": {}}\n')
        report, error = run(empty, args.limit)
        arms.append(("empty-state", report is None and bool(error), error or "deu um numero"))
        for name, ok, detail in arms:
            print("ARM %-16s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
        failed = sum(1 for _, ok, _ in arms if not ok)
        print("NEG-ARM %s arms=%d fail=%d"
              % ("PASS" if failed == 0 else "FAIL", len(arms), failed))
        return 1

    report, error = run(root, args.limit)
    if error is not None:
        print("STEPCACHE-COST: NO-VERDICT %s" % error)
        return 2
    summary = summarise(report)
    if args.json:
        print(json.dumps({"summary": summary, "report": report}, indent=2, ensure_ascii=False))
        return 0
    print("passos medidos: %d (%s)" % (summary["sampled"], ", ".join(report["steps"])))
    print("startup      : %.1f ms  (%d amostras, mediana)"
          % (summary["startup_ms"], len(report["startup_samples"])))
    print("resolver     : %.1f ms  (motor+estado+fingerprint, por dentro)" % summary["resolver_ms"])
    print("end-to-end   : %.1f ms  (um `_stepcache.py check` por processo)" % summary["end_to_end_ms"])
    print("resolver/share: %s" % ("n/a" if summary["resolver_share"] is None
                                  else "%.1f %%" % (summary["resolver_share"] * 100.0)))
    print("projected 100 passos (cache hit): %.1f s" % summary["projected_100"])
    print("PROBE-VERDICT measured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
