#!/usr/bin/env python
# NO-BUG: stepcache-skip-record -- o custo de um passo SKIP-SLOW fica no registo do ratchet.
"""stepcache-skip-record -- a linha de um passo SALTADO diz o que custou e por que.

O DEFEITO (audit #2, 2026-11-27, `_main/_stepcache.py:652`). O modo rapido lia
`elapsed_s` e decidia SKIP-SLOW, mas nao escrevia NADA: a linha do passo ficava
com o timestamp da ultima corrida REAL e sem razao nenhuma. `panel-themes`
(154,942 s) era adiado para sempre com o mesmo numero velho, e quem lesse a
linha nao conseguia dizer "correu e foi rapido" de "nao correu porque e' caro".
O SKIP e' legitimo; o silencio e' que nao era.

A cura escreve no MESMO dict que `record()` usa -- o que o
`battery-budget-oracle` le -- tres camadas: `elapsed_s` (o custo), `skip_reason`
(a razao) e `skipped=True` (para `check()` recusar um HIT a essa linha). O
passo continua a poder ser saltado; um passo saltado e' contado como SKIPPED,
nunca como um portao verde.

ARMS (estado sintetico, num temp dir; o estado real da bateria nunca e' tocado)
    1  `skip` com um elapsed de entrada -> `elapsed_s` PRESENTE e IGUAL ao input
    2  o `battery-budget-oracle` le essa MESMA linha e ve o custo
    3  `check()` normal recusa a linha como HIT (nao maquilha de passo rapido)
    4  `check()` com SOTTO_BATTERY_FAST=1 -> SKIP-SLOW e grava razao + custo

NEGATIVE ARM (`--neg-arm`)
    Copia de `_stepcache.py` com a UNICA linha que grava `elapsed_s` removida.
    O mesmo teste tem de ficar RED exactamente por `elapsed_s` ausente. O
    mutante APANHADO devolve rc 1 e imprime `NEG-ARM: PASS`; um mutante que
    sobrevive e' rc 0 e o `:expectred` da bateria reprova o passo. Uma ancora
    ausente ou ambigua e' CANNOT-MEASURE (rc 2), nunca um controlo verde.

Uso:
    python _main\\_stepcache-skip-record-oracle.py           -> VERDICT: PASS, rc 0
    python _main\\_stepcache-skip-record-oracle.py --neg-arm -> NEG-ARM: PASS, rc 1

Nao abre janela, audio, rede nem o Chrome do dono: so' ficheiros no temp dir.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENGINE = os.path.join(HERE, "_stepcache.py")
BUDGET = os.path.join(HERE, "battery-budget-oracle.py")

ELAPSED = 154.942
REASON = "SKIP-SLOW threshold=20.000"
STEP = "panel-themes"
MUTANT_OLD = '    entry["elapsed_s"] = round(value, 3)  # SKIP-RECORD-ELAPSED'
MUTANT_NEW = '    pass  # SKIP-RECORD-ELAPSED (removido: o mutante nao grava o custo)'

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_REFUSAL = 2


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def run_cli(engine, args, root, tag, env=None):
    """stdout/stderr para FICHEIROS, nunca pipes; sem janela (CREATE_NO_WINDOW)."""
    out = os.path.join(root, tag + ".out")
    err = os.path.join(root, tag + ".err")
    with open(out, "wb") as fo, open(err, "wb") as fe:
        proc = subprocess.run(
            [sys.executable, engine] + list(args), stdout=fo, stderr=fe,
            env=env if env is not None else os.environ.copy(),
            creationflags=0x08000000,
            startupinfo=subprocess.STARTUPINFO(
                dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    return (proc.returncode,
            io.open(out, encoding="utf-8", errors="replace").read(),
            io.open(err, encoding="utf-8", errors="replace").read())


def workdir_root():
    base = os.environ.get("TMPDIR") or r"I:\cc-tmp"
    if not os.path.isdir(base):
        base = tempfile.gettempdir()
    path = os.path.join(base, "stepcache-skip-record-%d" % os.getpid())
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
    return path


def fixture(sc, root, tag, with_elapsed):
    """Uma linha de cache com deps e log validos, SEM campos de skip."""
    dep = os.path.join(root, tag + "-dep.txt")
    log = os.path.join(root, tag + "-step.log")
    state = os.path.join(root, tag + "-state.json")
    write(dep, "A\n")
    write(log, "log line 1\n")
    fp, _missing = sc.fingerprint([dep])
    row = {
        "fingerprint": fp,
        "rc": 0,
        "exit_code": 0,
        "expect_rc": 0,
        "timestamp": "2026-11-26T18:26:13-0300",
        "deps": [dep],
        "log": log,
        "log_sha256": sc.sha256_file(log),
    }
    if with_elapsed:
        row["elapsed_s"] = ELAPSED
    write(state, json.dumps({"version": 1, "steps": {STEP: row}},
                            indent=2, sort_keys=True) + "\n")
    return dep, log, state


def probe(engine, root, tag):
    """(ok, problemas, linha gravada). O MESMO teste para o engine e o mutante."""
    problems = []
    sc = load(engine, "skip_record_engine_" + tag)
    dep, log, state = fixture(sc, root, tag + "-skip", with_elapsed=False)

    # 1 -- a entrada e' o numero do chamador; a linha TEM de a devolver.
    rc, out, err = run_cli(engine, [
        "skip", "--step", STEP, "--elapsed", str(ELAPSED),
        "--reason", REASON, "--state", state], root, tag + "-cli")
    if rc != 0 or not out.startswith("SKIP-RECORDED"):
        problems.append("1 CLI skip rc=%d out=%r err=%r" % (rc, out[:80], err[:80]))
    try:
        data = json.load(io.open(state, encoding="utf-8"))
        row = (data.get("steps") or {}).get(STEP) or {}
    except (OSError, ValueError) as exc:
        problems.append("1 estado ilegivel: %s" % exc)
        row = {}
    if row.get("elapsed_s") != ELAPSED:
        problems.append("1 elapsed_s=%r (input=%r) -- o custo nao foi gravado"
                        % (row.get("elapsed_s"), ELAPSED))
    if REASON not in str(row.get("skip_reason") or ""):
        problems.append("1 skip_reason=%r -- a razao nao foi gravada"
                        % (row.get("skip_reason"),))
    if row.get("skipped") is not True:
        problems.append("1 skipped=%r -- a linha pode maquilhar-se de passo rapido"
                        % (row.get("skipped"),))

    # 2 -- o ratchet le EXACTAMENTE esta linha deste ficheiro.
    budget = load(BUDGET, "skip_record_budget_" + tag)
    rows = budget.read_steps(state)
    seen = [r for r in rows if r["name"] == STEP]
    if len(seen) != 1 or seen[0]["elapsed_s"] != ELAPSED:
        problems.append("2 ratchet ve %r -- o custo saltado nao chega ao oraculo"
                        % (seen[:1],))

    # 3 -- um skip nao e' um portao que passou.
    hit, _rc, why = sc.check(STEP, [dep], 0, log=log, state_path=state)
    if hit or "skipped" not in str(why or ""):
        problems.append("3 check() hit=%s reason=%r -- skip maquilhou-se de HIT"
                        % (hit, why))

    # 4 -- o caminho REAL: `check()` sob fast mode deve gravar razao e custo.
    dep2, log2, state2 = fixture(sc, root, tag + "-check", with_elapsed=True)
    env = os.environ.copy()
    env["SOTTO_BATTERY_FAST"] = "1"
    env["SOTTO_BATTERY_FAST_S"] = "20"
    rc2, out2, err2 = run_cli(engine, [
        "check", "--step", STEP, "--deps", dep2, "--log", log2,
        "--state", state2], root, tag + "-fast", env=env)
    if rc2 != 2 or not out2.startswith("SKIP-SLOW\n"):
        problems.append("4 CLI check rc=%d out=%r err=%r -- o SKIP deixou de saltar"
                        % (rc2, out2[:80], err2[:80]))
    try:
        row2 = ((json.load(io.open(state2, encoding="utf-8"))).get("steps") or {}).get(STEP) or {}
    except (OSError, ValueError) as exc:
        problems.append("4 estado ilegivel: %s" % exc)
        row2 = {}
    if (row2.get("elapsed_s") != ELAPSED
            or "SKIP-SLOW" not in str(row2.get("skip_reason") or "")
            or row2.get("skipped") is not True):
        problems.append("4 check() nao gravou custo/razao: %r" % (row2,))

    return (not problems), problems, row


def neg_arm():
    try:
        source = io.open(ENGINE, "r", encoding="utf-8", newline="").read()
    except OSError as exc:
        print("NEG-ARM CANNOT-MEASURE -- _stepcache.py nao leu: %s" % exc)
        return EXIT_REFUSAL
    hits = source.count(MUTANT_OLD)
    if hits != 1:
        print("NEG-ARM CANNOT-MEASURE -- ancora %s (%d ocorrencias); o controlo "
              "nao pode provar nada" % ("ausente" if not hits else "ambigua", hits))
        return EXIT_REFUSAL
    root = workdir_root()
    try:
        mutant = os.path.join(root, "mutant_stepcache.py")
        write(mutant, source.replace(MUTANT_OLD, MUTANT_NEW, 1))
        ok, problems, row = probe(mutant, root, "neg")
        elapsed_visible = any("elapsed_s" in p for p in problems)
        if not ok and elapsed_visible:
            print("NEG-ARM: PASS -- mutante apanhado: %s" % problems[0])
            print("  linha mutante: elapsed_s=%r skip_reason=%r"
                  % (row.get("elapsed_s"), row.get("skip_reason")))
            return EXIT_FAIL
        print("NEG-ARM: FAIL -- o mutante sobreviveu (ok=%s, problemas=%r)"
              % (ok, problems))
        return EXIT_PASS
    except Exception as exc:                                   # noqa: BLE001
        print("NEG-ARM CANNOT-MEASURE -- control rebentou: %s: %s"
              % (type(exc).__name__, exc))
        return EXIT_REFUSAL
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass
    if "--neg-arm" in argv:
        return neg_arm()
    if not os.path.isfile(ENGINE) or not os.path.isfile(BUDGET):
        print("VERDICT: CANNOT-MEASURE -- engine ou ratchet ausente")
        return EXIT_REFUSAL
    root = workdir_root()
    try:
        ok, problems, row = probe(ENGINE, root, "pos")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    for p in problems:
        print("  RED %s" % p)
    print("VERDICT: %s -- elapsed_s=%r reason=%r skipped=%r (%d armas)"
          % ("PASS" if ok else "FAIL", row.get("elapsed_s"),
             row.get("skip_reason"), row.get("skipped"), 4 - len(problems)))
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
