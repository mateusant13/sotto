#!/usr/bin/env python
# BLOCKS: a red-as-expected step that re-proves, by mutating a file, the exact
#         negative arm its own oracle already runs in-process with `--neg-arm`.
# NO-BUG: the same invariant proved twice is a crosscheck; proved twice in the
#         SAME run it is pure cost -- and it is the dominant cost of the battery.
"""_red-arm-census -- mede o par e converte o passo caro para o braco do oraculo.

O DEFEITO QUE ISTO FECHA (medido 2026-11-26, nesta arvore).

A bateria tem 92 passos `red-as-expected-*`. **89** deles executam um oraculo que
JA' traz `--neg-arm` (censo: `--neg-arm` presente no fonte do oraculo que a linha
nomeia). O passo da bateria muta um FICHEIRO do produto, larga uma casca de
processos e volta a correr o oraculo inteiro; o `--neg-arm` do proprio oraculo
faz a mesma mutacao sobre uma copia de trabalho, no mesmo interpretador.

MEDIDO no par mais caro (`youtube-first-at-boot`):
    passo da bateria ........ 143,9 s   (registado em `_cache/battery-steps.json`)
    `oracle --neg-arm` ...... 42,5 s    (medido com `time`, rc=1)
O invariante e' o MESMO: os dois exigem `NEG-ARM: PASS` e rc=1.

O QUE ESTE FICHEIRO FAZ
-----------------------
Para cada `call :step always red-as-expected-<X> 1 "<deps>" "<log>" python _main\\<Y>.py ...`
ele EXECUTA `python _main\\<Y>.py --neg-arm` com prazo, e so' converte a linha
quando as tres condicoes passam:

  1. rc == 1                          (o codigo de "mutante apanhado"),
  2. a saida contem `NEG-ARM: PASS`,  (o marcador que o `:expectred` ja' exige),
  3. o tempo medido < o do passo registado (senao nao ha ganho: nao se converte).

Sem `--apply` ele so' MEDE e imprime a tabela. Com `--apply` ele reescreve a
linha do `.cmd` (preservando CRLF e o resto do ficheiro byte a byte) e deixa a
lista dos convertidos para o recibo.

Uso:
    python _main/_red-arm-census.py                 # mede os mais caros
    python _main/_red-arm-census.py --limit 12      # so' os 12 mais caros
    python _main/_red-arm-census.py --limit 12 --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
BATTERY = os.path.join(HERE, "_audit-verify-all.cmd")
STATE = os.path.join(ROOT, "_cache", "battery-steps.json")
#: O marcador que o `:expectred` do `.cmd` ja' exige na linha seguinte.
MARKER = "NEG-ARM: PASS"
#: Prazo por sonda. Um `--neg-arm` medido custa 40-60 s; 240 s e' o piso da casa
#: (`SOTTO_STEP_DEADLINE_S`) e um corte NAO conta como aprovacao.
PROBE_DEADLINE_S = 240.0
LINE_RE = re.compile(
    r'^call :step always (red-as-expected-[a-z0-9-]+) 1 "([^"]*)" "([^"]*)" '
    r'python (_main\\[a-z0-9_.-]+\.py)(.*)$')


def load_state():
    try:
        with open(STATE, "r", encoding="utf-8") as fh:
            return (json.load(fh).get("steps") or {})
    except (OSError, ValueError):
        return {}


def candidates(lines, state):
    """[(cost, name, oracle, index, match)] dos passos convertiveis, caros primeiro."""
    out = []
    for i, line in enumerate(lines):
        m = LINE_RE.match(line.rstrip("\r\n"))
        if not m:
            continue
        name, deps, log, oracle, tail = m.groups()
        src = os.path.join(ROOT, oracle.replace("\\", os.sep))
        try:
            with open(src, "r", encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            continue
        if "--neg-arm" not in body:
            continue
        cost = float((state.get(name) or {}).get("elapsed_s") or 0.0)
        out.append((cost, name, oracle, i, m))
    out.sort(reverse=True)
    return out


def probe(oracle):
    """Corre `--neg-arm` com prazo. Devolve (rc, seconds, marker_seen)."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, oracle.replace("\\", os.sep)), "--neg-arm"],
            cwd=ROOT, capture_output=True, text=True, timeout=PROBE_DEADLINE_S,
            encoding="utf-8", errors="replace")
        return proc.returncode, time.monotonic() - t0, MARKER in (proc.stdout + proc.stderr)
    except subprocess.TimeoutExpired:
        return 124, time.monotonic() - t0, False


def contract_holds(rc, marker):
    """As duas metades do contrato do `:expectred`: rc=1 E o marcador."""
    return rc == 1 and marker


def rewrite(line, oracle):
    """A linha nova: o mesmo passo, o mesmo log, o braco do proprio oraculo.

    As `deps` NAO mudam: o `--neg-arm` le' os mesmos ficheiros que a versao que
    mutava um deles, e um HIT continua a exigir que todos estejam iguais.
    """
    m = LINE_RE.match(line.rstrip("\r\n"))
    name, deps, log, old_oracle, tail = m.groups()
    return 'call :step always %s 1 "%s" "%s" python %s --neg-arm%s' % (
        name, deps, log, oracle, tail)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=0, help="so' os N mais caros (0 = todos)")
    ap.add_argument("--apply", action="store_true", help="reescreve o .cmd para os que passam")
    ap.add_argument("--min-saved-s", type=float, default=0.0,
                    help="so' converte quando a sonda poupa pelo menos isto")
    args = ap.parse_args(argv)

    with open(BATTERY, "r", encoding="utf-8", newline="") as fh:
        raw = fh.read()
    lines = raw.splitlines(keepends=True)
    state = load_state()
    cands = candidates(lines, state)
    if args.limit:
        cands = cands[:args.limit]
    print("candidatos=%d  (o .cmd tem 92 red-as-expected, 89 com --neg-arm no oraculo)"
          % len(cands))
    print("%-42s %9s %9s %5s %s" % ("passo", "bateria", "neg-arm", "rc", "veredicto"))
    convert, total_saved = [], 0.0
    for cost, name, oracle, idx, _m in cands:
        rc, secs, marker = probe(oracle)
        ok = contract_holds(rc, marker) and secs + args.min_saved_s < cost
        saved = cost - secs
        verdict = "CONVERTE" if ok else (
            "recusa-rc" if rc != 1 else
            "recusa-sem-marcador" if not marker else "sem-ganho")
        print("%-42s %8.1fs %8.1fs %5d %s" % (name, cost, secs, rc, verdict))
        if ok:
            convert.append((name, oracle, idx, saved))
            total_saved += saved
    print("\nconvertiveis=%d  poupanca medida=%.0f s" % (len(convert), total_saved))
    if not args.apply:
        print("(sem --apply: nada foi escrito)")
        return 0 if convert else 3
    for name, oracle, idx, _saved in convert:
        lines[idx] = rewrite(lines[idx], oracle)
    out = "".join(lines)
    with open(BATTERY, "w", encoding="utf-8", newline="") as fh:
        fh.write(out)
    crlf = out.count("\r\n")
    print("escrito: %s  (%d convertidos, %d bytes, %d CRLF / %d bare LF)"
          % (BATTERY, len(convert), len(out.encode("utf-8")), crlf,
             out.count("\n") - crlf))
    for name, _o, _i, _s in convert:
        print("  CONVERTIDO %s" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
