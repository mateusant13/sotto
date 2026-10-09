#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_main/_focus-thread-baseline.py -- quantas threads traz o pythonw.exe SOZINHO.

Nao importa ctypes, nao importa psutil, nao cria thread nenhuma: se o numero for
>1, o orcamento de threads desta lane nao pode ser lido como "o processo inteiro
tem <=2 threads" -- o interpretador ja gastou as suas antes de a lane acordar.

  pythonw.exe _main\\_focus-thread-baseline.py
"""
import json
import os
import subprocess
import sys

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "focus-thread-baseline.json")
res = {"pid": os.getpid(), "python": sys.version}
# via 1: psutil (importado DEPOIS do instantaneo? nao -- medimos antes e depois)
res["threads_before_psutil_import"] = None
try:
    import psutil
    res["threads_after_psutil_import"] = psutil.Process(os.getpid()).num_threads()
except Exception as exc:
    res["psutil_error"] = repr(exc)
# via 2: tasklist, um processo EXTERNO, para nao depender de psutil
try:
    r = subprocess.run(["tasklist", "/FI", "PID eq %d" % os.getpid(), "/FO", "CSV", "/NH"],
                       capture_output=True, text=True, timeout=20)
    res["tasklist"] = r.stdout.strip()
except Exception as exc:
    res["tasklist_error"] = repr(exc)
with open(out, "w", encoding="utf-8", newline="\n") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
