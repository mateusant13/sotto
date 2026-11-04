"""Roda a bateria SEM UMA JANELA, e devolve o veredicto dela.

PORQUE ISTO EXISTE (medido 2026-11-04 na cara do dono). Lancar
`_main\\_audit-verify-all.cmd` de dentro de um agente por `Popen(...)` com
`creationflags=CREATE_NO_WINDOW` sozinho NAO esconde nada: o pai nao tem consola,
o filho aloca a sua, e o Windows mostra-a -- ele contou "50 terminal por
segundo". O par `CREATE_NO_WINDOW` + `STARTUPINFO`/`SW_HIDE` e' o que fecha o
caso, e `app/webview/no_console.py` ja' o tem; este lancador e' o uso dele para a
bateria.

    python _main/run-battery-hidden.py                 # corre, imprime o resumo
    python _main/run-battery-hidden.py --log G:\\Temp\\x.txt
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
from no_console import popen_kwargs                      # noqa: E402

BATTERY = os.path.join(ROOT, '_main', '_audit-verify-all.cmd')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--log', default=os.path.join(
        os.environ.get('TMPDIR') or os.environ.get('TEMP') or ROOT,
        'battery-hidden.log'))
    a = ap.parse_args(argv)
    with io.open(a.log, 'wb') as fh:
        proc = subprocess.Popen([BATTERY], cwd=ROOT, stdout=fh,
                                stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL,
                                **popen_kwargs())
        rc = proc.wait()
    text = io.open(a.log, encoding='utf-8', errors='replace').read()
    for line in text.splitlines():
        if line.startswith(('steps', 'failed', 'skipped', 'exit-code',
                            'BATTERY-VERDICT')):
            print(line)
    print('log: %s' % a.log)
    return rc


if __name__ == '__main__':
    sys.exit(main())
