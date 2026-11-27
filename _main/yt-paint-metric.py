#!/usr/bin/env python
"""O comando da metrica `e2e.yt_paint_worst_ms`, com UMA repeticao nomeada.

MEDIDO 2026-11-27: dentro da jaula (`--cpu 40 --io very-low`) a corrida do
`benchmark_history run --gate --blast-radius --verify-red` devolveu
`e2e.yt_paint_worst_ms: command exited 3762504530` = **0xE0434352**, a excepcao
de CLR do host .NET que desenha o bitmap GDI+. A MESMA arvore deu `VERDICT: PASS`
(12,133 ms) em duas corridas e a terceira morreu no carregamento do CLR **antes**
de qualquer amostra -- 1 em 4 hoje.

O que isto NAO autoriza: repetir um veredicto honesto. Um `VERDICT: FAIL` sai
INTACTO, rc 1, valor publicado; um `CANNOT-MEASURE` sai intacto, rc 3. So' o
codigo de spawn do host .NET e' repetido, UMA vez, e a repeticao imprime-se com
`retry=1 reason=clr-spawn-exception` para que o numero no `benchmarks/history.jsonl`
nunca se apresente como uma amostra unica quando nao foi.
"""
from __future__ import annotations

import subprocess
import sys

ORACLE = ["_main/yt-headless-paint-oracle.py"]
# 0xE0434352 = STATUS_CLR_EXCEPTION, o host .NET morreu antes de medir.
CLR_CODES = {0xE0434352, 0xE0434352 - 2**32}


def run() -> int:
    return subprocess.call([sys.executable] + ORACLE)


def main() -> int:
    rc = run()
    if rc in CLR_CODES:
        sys.stdout.write(f"PAINT-METRIC retry=1 reason=clr-spawn-exception first_rc={rc}\n")
        sys.stdout.flush()
        rc = run()
        if rc in CLR_CODES:
            sys.stdout.write("PAINT-METRIC CANNOT-MEASURE why=clr-spawn-exception twice\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
