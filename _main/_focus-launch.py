#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_main/_focus-launch.py -- arranca o probe sob pythonw.exe e guarda a
excecao num ficheiro (pythonw nao tem stderr, logo um traceback seria invisivel).

  pythonw.exe _main\\_focus-launch.py <log-de-erros> <script.py> [args...]
"""
import os
import runpy
import sys
import traceback

log = sys.argv[1]
script = sys.argv[2]
sys.argv = [script] + sys.argv[3:]
try:
    runpy.run_path(script, run_name="__main__")
except SystemExit as exc:
    with open(log, "a", encoding="utf-8") as f:
        f.write("SystemExit: %r\n" % (exc.code,))
except BaseException:
    with open(log, "a", encoding="utf-8") as f:
        f.write("cwd=%s\n" % os.getcwd())
        f.write(traceback.format_exc())
