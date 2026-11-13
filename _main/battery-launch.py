"""UMA LARGADA DA BATERIA, e as portas que a julgam -- num comando so.

Nasceu de uma sessao inteira a fumbar a largada certa (2026-11-12): o agente
tentou `python -m watcher run --cpu 40 -- cmd /c _main\\_audit-verify-all.cmd`
e levou `No module named watcher` (o `PYTHONPATH` do `I:\\!watcher` e' posto pelo
PROPRIO `.cmd`, nao pela shell); tentou um `_main/_cache/battery-run.py` que nao
existe; o `run-battery-hidden.py` que existe chama `subprocess.STDOUT` sem
importar `subprocess`. Cada uma dessas tentativas custou um turno e nenhuma
correu a bateria.

O QUE ESTE FICHEIRO FAZ
-----------------------
Uma invocacao:

    python _main/battery-launch.py                 # caged (o .cmd se encageia), hidden
    python _main/battery-launch.py --no-cage       # SOTTO_BATTERY_NOCAGE=1
    python _main/battery-launch.py --fast          # SOTTO_BATTERY_FAST=1
    python _main/battery-launch.py --heavy         # SOTTO_BATTERY_HEAVY=1
    python _main/battery-launch.py --verify        # so' as portas, sem corrida
    python _main/battery-launch.py --wait 1800     # tecto de parede do filho

`--verify` corre as CINCO portas que cada edicao desta casa obriga a re-medir --
pins, wiring, pairing, class, undefined-names -- e imprime um veredicto. Ele
existe porque a regra do AGENTS.md diz "re-check ... after the final .cmd edit" e
ate' hoje isso eram cinco comandos lembrados de cor.

O QUE ELE NAO FAZ
-----------------
Nao abre janela (o filho vem por `hidden-launch`, `CREATE_NO_WINDOW`), nao toca
em audio e nao decide nada sobre o veredicto: o veredicto e' o do `.cmd`
(`BATTERY-VERDICT` + exit code) e este programa so' o LE' e o imprime junto do
caminho do log. Uma corrida cortada por prazo sai com rc=124 e NUNCA como verde.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
BATTERY = os.path.join(HERE, '_audit-verify-all.cmd')
OUT = os.path.join(HERE, '_audit-verify')
PYTHON = sys.executable

#: As portas que uma edicao da `.cmd` obriga a re-medir, com o custo medido de
#: cada uma (2026-11-12, nesta arvore). O custo esta' aqui para o operador saber
#: o que vai pagar antes de largar; ele nao julga nada.
GATES = (
    ('pins', ['_main/agents-md-pins-oracle.py'], 0.6),
    ('wiring', ['_main/battery-wiring-oracle.py'], 1.2),
    ('pairing', ['_main/battery-record-pairing-oracle.py'], 0.5),
    ('class', ['_main/battery-class-oracle.py'], 0.6),
    ('undefined-names', ['_main/undefined-names-oracle.py'], 1.2),
)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass


def hidden_run(argv, env, timeout=None, log_path=None):
    """O filho nasce SEM consola: e' a lei desta casa, e vale para o agente."""
    hidden_launch = _load_hidden_launch()
    handle = io.open(log_path, 'w', encoding='utf-8', newline='') if log_path else None
    kwargs = {}
    if handle is not None:
        kwargs['stdout'] = handle
        kwargs['stderr'] = subprocess.STDOUT
    try:
        rc, out, err = hidden_launch.run(argv, cwd=ROOT, env=env,
                                        capture=False, timeout=timeout)
    finally:
        if handle is not None:
            handle.close()
    return rc


def _load_hidden_launch():
    """`hidden-launch.py` tem hifen no nome: importa-se por CAMINHO.

    Um `import hidden_launch` levanta `ModuleNotFoundError` -- e o `except` de um
    chamador que devolve `None` transformaria isso num "nao ha nada a medir",
    que e' a classe de defeito que esta casa ja' pagou varias vezes.
    """
    import importlib.util
    path = os.path.join(HERE, 'hidden-launch.py')
    spec = importlib.util.spec_from_file_location('hidden_launch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def launch(args):
    stamp = time.strftime('%Y%m%d-%H%M%S')
    log = os.path.join(OUT, f'_battery-run-{stamp}.log')
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    if args.no_cage:
        env['SOTTO_BATTERY_NOCAGE'] = '1'
        env.pop('SOTTO_BATTERY_CAGED', None)
    if args.fast:
        env['SOTTO_BATTERY_FAST'] = '1'
    if args.heavy:
        env['SOTTO_BATTERY_HEAVY'] = '1'
    argv = ['cmd', '/c', BATTERY]
    print(f'battery-launch  run={stamp}')
    print(f'  comando  {" ".join(argv)}   (hidden, cwd={ROOT})')
    print(f'  politica cage={"OFF" if args.no_cage else "ON (o .cmd se encageia)"}'
          f' fast={args.fast} heavy={args.heavy}')
    print(f'  log      {log}')
    module = _load_hidden_launch()
    handle = io.open(log, 'w', encoding='utf-8', newline='')
    started = time.time()
    try:
        proc = module.popen(argv, cwd=ROOT, env=env, stdout=handle,
                            stderr=subprocess.STDOUT)
        try:
            rc = proc.wait(timeout=args.wait or None)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = 124
    finally:
        handle.close()
    wall = time.time() - started
    verdict, counts = read_verdict(log)
    print(f'  parede   {wall:.1f}s  rc={rc}')
    if counts:
        print(f'  passos   {counts}')
    print(f'BATTERY-RUN: {"GREEN" if rc == 0 and verdict and verdict.startswith("GREEN") else "RED"}'
          f'  rc={rc}  verdict={verdict or "SEM SUMARIO"}')
    if rc == 124:
        print('  NOTA     rc=124 e\' o prazo do LARGADOR: a corrida nao terminou e '
              'nao ha veredicto -- um corte nao e\' um portao que passou.')
    return 0 if rc == 0 and (verdict or '').startswith('GREEN') else 1


def read_verdict(log):
    """Le' `BATTERY-VERDICT` e a linha `steps=`; um sumario velho nao serve."""
    if not os.path.exists(log):
        return None, None
    verdict = None
    counts = None
    with io.open(log, 'r', encoding='utf-8', errors='replace') as handle:
        for line in handle:
            if 'BATTERY-VERDICT' in line:
                verdict = line.split('BATTERY-VERDICT:', 1)[-1].strip()
            if re.match(r'^\s*steps=\d+', line):
                counts = line.strip()
    return verdict, counts


def verify(only=None):
    """As portas obrigatorias, uma a uma, com o rc de cada uma."""
    module = _load_hidden_launch()
    failures = []
    print('battery-launch --verify  (as portas que cada edicao da .cmd obriga a re-medir)')
    for name, argv, cost in GATES:
        if only and name not in only:
            continue
        path = os.path.join(ROOT, argv[0])
        if not os.path.exists(path):
            print(f'  {name:<16} MISSING  {argv[0]}')
            failures.append(name)
            continue
        started = time.time()
        rc, out, err = module.run([PYTHON] + argv, cwd=ROOT, capture=True,
                                  timeout=300,
                                  env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        wall = time.time() - started
        tail = ''
        for line in (out or '').splitlines() + (err or '').splitlines():
            if line.strip():
                tail = line.strip()
        state = 'PASS' if rc == 0 else 'FAIL'
        if rc != 0:
            failures.append(name)
        print(f'  {name:<16} {state}  rc={rc}  {wall:.1f}s (baseline {cost:.1f}s)  {tail[:110]}')
    print('VERIFY: ' + ('PASS' if not failures else 'FAIL ' + ','.join(failures)))
    return 0 if not failures else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Uma largada da bateria (hidden, caged) e as portas que a julgam.')
    parser.add_argument('--no-cage', action='store_true')
    parser.add_argument('--fast', action='store_true')
    parser.add_argument('--heavy', action='store_true')
    parser.add_argument('--wait', type=int, default=0,
                        help='tecto de parede do filho em segundos (0 = sem tecto)')
    parser.add_argument('--verify', action='store_true',
                        help='corre so as portas obrigatorias, sem corrida')
    parser.add_argument('--only', default='',
                        help='com --verify: lista de portas separada por virgula')
    parsed = parser.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    if parsed.verify:
        only = [item.strip() for item in parsed.only.split(',') if item.strip()]
        return verify(only)
    return launch(parsed)


if __name__ == '__main__':
    sys.exit(main())
