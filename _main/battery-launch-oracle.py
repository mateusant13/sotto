# NO-BUG: a corrida de 2026-11-12 que mediu 21 min com um export herdado a decidir a politica de largada -- integridade do INSTRUMENTO, sem id no `_main/bug-ledger.json`
"""battery-launch-oracle -- o que a corrida PROVA nao vem de um export esquecido.

Nasceu de um RED medido nesta arvore (2026-11-12). A bateria inteira correu 21 min
(`run=20261112-225705`) e o unico passo vermelho foi `battery-budget`:

    BATTERY-BUDGET VERDICT RED -- politica de largada diferente do baseline
    (baseline='cap40', corrida=None)
    caged    : OFF -- NO CPU cap on this run

A causa nao era contencao nem o passo: um `SOTTO_BATTERY_NOCAGE=1` esquecido na
shell do agente foi herdado pelo largador e desligou o cage EM SILENCIO. A linha
que o dizia estava na 568 de 568 -- e eu tinha lido a corrida anterior como
"contencao", que era um diagnostico errado sobre um defeito de fiacao.

A CLASSE e' a do `webview2-args-scope`: uma variavel de ambiente herdada muda o
que o processo mede, e nada no output do arranque o diz. Duas metades da cura,
as duas julgadas aqui:

  * `battery_launch.run_env` RETIRA as politicas do ambiente e NOMEIA cada uma
    que saiu; a politica da corrida vem do CLI (`--no-cage/--fast/--heavy`).
  * o `.cmd` imprime `politica : <P>` no ARRANQUE e passa a MESMA variavel ao
    `battery-budget`, que recusa julgar contra baseline de outra politica.

Nao larga nada: sem shell, sem janela, sem worker, sem dispositivo.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCH = os.path.join(HERE, 'battery-launch.py')
BATTERY = os.path.join(HERE, '_audit-verify-all.cmd')

ARMS = []


def arm(name, ok, detail=''):
    ARMS.append((name, bool(ok), detail))
    print('%s %-46s %s' % ('PASS' if ok else 'FAIL', name, detail))
    return ok


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


class Args(object):
    def __init__(self, no_cage=False, fast=False, heavy=False):
        self.no_cage = no_cage
        self.fast = fast
        self.heavy = heavy


def check_policy_scrub(mod):
    """As seis propriedades do ambiente do filho."""
    base = {
        'SOTTO_BATTERY_NOCAGE': '1',
        'SOTTO_BATTERY_CAGED': '1',
        'SOTTO_BATTERY_HEAVY': '1',
        'SOTTO_BATTERY_FAST': '1',
        'SOTTO_REDUX_LIVE': '1',
        'PATH': 'x',
    }

    env, scrubbed = mod.run_env(Args(), base)
    want = ['SOTTO_BATTERY_CAGED', 'SOTTO_BATTERY_FAST',
            'SOTTO_BATTERY_HEAVY', 'SOTTO_BATTERY_NOCAGE']
    arm('A1 o export esquecido sai do ambiente do filho',
        not any(k in env for k in want) and scrubbed == want,
        'sobrou=%r nomeadas=%r' % ([k for k in want if k in env], scrubbed))

    arm('A2 o que saiu e NOMEADO (a linha que faltava no log)',
        'SOTTO_BATTERY_NOCAGE' in scrubbed,
        'nomeadas=%r' % (scrubbed,))

    arm('A3 o resto do ambiente atravessa intacto',
        env.get('PATH') == 'x' and env.get('SOTTO_REDUX_LIVE') == '1',
        'PATH=%r redux=%r' % (env.get('PATH'), env.get('SOTTO_REDUX_LIVE')))

    env, _ = mod.run_env(Args(no_cage=True), base)
    arm('A4 `--no-cage` e a UNICA porta para o modo sem tecto',
        env.get('SOTTO_BATTERY_NOCAGE') == '1' and 'SOTTO_BATTERY_CAGED' not in env,
        'NOCAGE=%r CAGED=%r' % (env.get('SOTTO_BATTERY_NOCAGE'),
                                env.get('SOTTO_BATTERY_CAGED')))

    env, _ = mod.run_env(Args(heavy=True, fast=True), base)
    arm('A5 `--heavy`/`--fast` ligam pelo CLI, nunca pela heranca',
        env.get('SOTTO_BATTERY_HEAVY') == '1' and env.get('SOTTO_BATTERY_FAST') == '1',
        'HEAVY=%r FAST=%r' % (env.get('SOTTO_BATTERY_HEAVY'),
                              env.get('SOTTO_BATTERY_FAST')))

    env, _ = mod.run_env(Args(), {})
    arm('A6 stdout utf-8 em toda corrida (o glifo nao derruba um braco)',
        env.get('PYTHONIOENCODING') == 'utf-8', 'PYTHONIOENCODING=%r'
        % (env.get('PYTHONIOENCODING'),))
    return True


def check_cmd(src):
    """As tres propriedades do `.cmd`: diz a politica, no arranque, e a usa."""
    lines = src.splitlines()
    idx = {}
    for i, line in enumerate(lines):
        if 'set "CAGE_POLICY=cap40"' in line:
            idx.setdefault('policy_set', i)
        if re.search(r'^echo politica\s*:', line):
            idx.setdefault('policy_echo', i)
        if re.search(r'^if defined SOTTO_BATTERY_CAGED echo caged\s*:', line):
            idx.setdefault('summary', i)
        if 'battery-budget-oracle.py' in line and '--policy' in line:
            idx.setdefault('budget_step', i)
        if 'goto :__battery_cage_outer' in line:
            idx.setdefault('cage_gate', i)
        if line.strip() == 'setlocal EnableDelayedExpansion':
            idx.setdefault('setlocal', i)

    arm('A7 o `.cmd` imprime a politica de largada',
        'policy_echo' in idx and '!CAGE_POLICY!' in lines[idx['policy_echo']],
        'linha=%s' % (idx.get('policy_echo'),))

    arm('A8 ... no ARRANQUE, antes do sumario (21 min de silencio sao a licao)',
        idx.get('policy_echo') is not None and idx.get('summary') is not None
        and idx['policy_echo'] < idx['summary'],
        'echo=%s sumario=%s' % (idx.get('policy_echo'), idx.get('summary')))

    arm('A9 o `battery-budget` julga contra a MESMA politica',
        'budget_step' in idx and '"!CAGE_POLICY!"' in lines[idx['budget_step']],
        'linha=%s' % (idx.get('budget_step'),))

    arm('A10 o DESPACHO do cage vive ANTES do setlocal (o `!` de I:\\!watcher)',
        idx.get('cage_gate') is not None and idx.get('setlocal') is not None
        and idx['cage_gate'] < idx['setlocal']
        and 'I:\\!watcher' in lines[idx['cage_gate']],
        'gate=%s setlocal=%s' % (idx.get('cage_gate'), idx.get('setlocal')))
    return True


def run():
    mod = _load(LAUNCH, 'battery_launch_under_test')
    print('battery-launch-oracle -- a politica de largada nao vem do ambiente')
    print('launch : %s' % LAUNCH)
    print('battery: %s' % BATTERY)
    print('lancamentos: NENHUM (nem shell, nem janela, nem worker, nem dispositivo)')
    print('== run_env -- o ambiente do filho')
    check_policy_scrub(mod)
    print('== o `.cmd`')
    check_cmd(_read(BATTERY))
    failures = [n for n, ok, _ in ARMS if not ok]
    print('VERDICT: %s (%d/%d)' % ('FAIL' if failures else 'PASS',
                                   len(ARMS) - len(failures), len(ARMS)))
    if failures:
        print('  falhou: %s' % ', '.join(failures))
        return 1
    return 0


def run_neg_arm():
    """Muta a CURA numa copia e exige que o braco QUE A MEDE caia."""
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix='sotto-launch-neg-')
    caught = 0
    total = 0
    try:
        src = _read(LAUNCH)
        mutations = [
            ('M1 a retirada das politicas apagada',
             'scrubbed = sorted(k for k in POLICY_ENV if k in env)',
             'scrubbed = []'),
            ('M2 o no-cage deixa de ser a unica porta',
             "if getattr(args, 'no_cage', False):",
             'if True:'),
        ]
        for label, old, new in mutations:
            total += 1
            if old not in src:
                print('NEG-ARM %s IMPOSSIVEL (ancora ausente)' % label)
                continue
            path = os.path.join(tmp, 'battery-launch_mut.py')
            with io.open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(src.replace(old, new, 1))
            global ARMS
            saved, ARMS = ARMS, []
            buf = io.StringIO()
            keep, sys.stdout = sys.stdout, buf
            try:
                mod = _load(path, 'battery_launch_mutant')
                check_policy_scrub(mod)
            finally:
                sys.stdout = keep
                failed = [n for n, ok, _ in ARMS if not ok]
                ARMS = saved
            if failed:
                caught += 1
                print('NEG-ARM %s caught by %s' % (label, ','.join(failed)))
            else:
                print('NEG-ARM %s NOT-CAUGHT' % label)

        cmd = _read(BATTERY)
        cmd_mutations = [
            ('M3 a linha da politica arrancada do arranque',
             '\r\necho politica : !CAGE_POLICY!', '\r\nREM'),
            ('M4 o battery-budget volta a correr sem politica',
             '--policy "!CAGE_POLICY!"', ''),
            ('M5 o setlocal sobe por cima do despacho do cage',
             'if "%~1"=="--caged" goto :__battery_body',
             'setlocal EnableDelayedExpansion\r\nif "%~1"=="--caged" goto :__battery_body'),
        ]
        for label, old, new in cmd_mutations:
            total += 1
            if old not in cmd:
                print('NEG-ARM %s IMPOSSIVEL (ancora ausente)' % label)
                continue
            saved, ARMS = ARMS, []
            buf = io.StringIO()
            keep, sys.stdout = sys.stdout, buf
            try:
                check_cmd(cmd.replace(old, new, 1))
            finally:
                sys.stdout = keep
                failed = [n for n, ok, _ in ARMS if not ok]
                ARMS = saved
            if failed:
                caught += 1
                print('NEG-ARM %s caught by %s' % (label, ','.join(failed)))
            else:
                print('NEG-ARM %s NOT-CAUGHT' % label)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('NEG-ARM: %s -- %d/%d mutante(s) apanhado(s)'
          % ('PASS' if caught == total else 'FAIL', caught, total))
    return 1 if caught == total else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true',
                    help='muta a cura numa copia; tem de apanhar cada mutante')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    return run_neg_arm() if args.neg_arm else run()


if __name__ == '__main__':
    sys.exit(main())
