"""O oraculo do RELANCADOR: um vencedor novo, mesmo quando o PID e' RECICLADO.

O DEFEITO QUE ELE JULGA, medido nesta arvore a 2026-11-08 00:09:

    ... CreateProcessAsUser(fonte=14016) ok=True err=0 filho=22232
    2026-11-08 00:10:47 FALHA (via token): nenhuma instancia nova em 90s

A instancia nova ganhou a mutex **1 segundo** depois da largada -- o log tem
`SHELL_STARTUP_STAGE ... SINGLE_INSTANCE already_running=false` as 00:09:18. O
laco chamou-lhe "nenhuma instancia": chaveava o vencedor pelo **PID**, e o pid
19896 ja' aparecia num log de **2026-11-03**. O Windows recicla pids; a chave
tem de ser `(pid, carimbo do log)` e o carimbo tem de ser POSTERIOR a largada.

Um relancador que diz FALHA depois de ter MATADO a app e' a pior frase desta
arvore: quem a le' mata outra vez.

Os bracos, contra o codigo REAL (`wait_ready` importado do ficheiro):

  A1  mesmo pid, carimbo NOVO              -> devolve o pid (a vida nova)
  A2  so' carimbos ANTIGOS                 -> None (nao aceita vida passada)
  A3  carimbo novo mas `already_running=true` -> None (a mutex recusou)
  A4  arranque sem `SINGLE_INSTANCE`       -> None (perdedor silencioso)
  A5  sem `since`, o mesmo pid novo e' INVISIVEL -> None (a armadilha, documentada)
  A6  a frase de falha NOMEIA o ultimo carimbo visto (mensagem util)

`--neg-arm` repoe a chave por PID numa COPIA e exige A1 vermelho.
"""
import argparse
import importlib.util
import io
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, 'sotto-relaunch.py')

OLD = ('2026-11-03 11:42:17.579 sotto: SHELL_STARTUP_STAGE pid=19896 stage=pre-lock '
       'python=C:\\Program Files\\Python311\\python.EXE panel=true\n'
       '2026-11-03 11:42:17.586 sotto: SINGLE_INSTANCE name=Local\\SottoShell '
       'already_running=false\n')
NEW = ('2026-11-08 00:09:18.696 sotto: SHELL_STARTUP_STAGE pid=19896 stage=pre-lock '
       'python=C:\\Program Files\\Python311\\python.EXE panel=true\n'
       '2026-11-08 00:09:18.715 sotto: SHELL_CODE_ID sha256=CE4098871454 files=99\n'
       '2026-11-08 00:09:18.720 sotto: SINGLE_INSTANCE name=Local\\SottoShell '
       'already_running=false\n')
LOST = ('2026-11-08 00:09:18.696 sotto: SHELL_STARTUP_STAGE pid=4242 stage=pre-lock '
        'python=C:\\Program Files\\Python311\\python.EXE panel=true\n'
        '2026-11-08 00:09:18.720 sotto: SINGLE_INSTANCE name=Local\\SottoShell '
        'already_running=true\n')
SILENT = ('2026-11-08 00:09:18.696 sotto: SHELL_STARTUP_STAGE pid=777 stage=pre-lock '
          'python=C:\\Program Files\\Python311\\python.EXE panel=true\n')


def load(path, name='relauncher'):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def with_log(module, text, fn):
    """Troca a fonte do log pelo texto do braco (nenhum processo e' tocado)."""
    real = module.log_text
    module.log_text = lambda: text
    try:
        return fn()
    finally:
        module.log_text = real


def run(module, label, tmpdir):
    results = []

    def arm(name, ok, detail=''):
        results.append((name, bool(ok), detail))

    since = time.mktime(time.strptime('2026-11-08 00:08:00', '%Y-%m-%d %H:%M:%S'))

    # A1: mesmo pid, carimbo novo -- o caso medido. O que se exige NAO e' so' o pid:
    # e' o CARIMBO ACEITO, porque aceitar o pid com o carimbo de 2026-11-03 e' o
    # defeito de volta (o vencedor seria a vida antiga).
    buf = io.StringIO()
    real_stdout, sys.stdout = sys.stdout, buf
    try:
        pid = with_log(module, OLD + NEW,
                       lambda: module.wait_ready({19896}, since, timeout=1.5))
    finally:
        sys.stdout = real_stdout
    saida = buf.getvalue()
    arm('A1 mesmo pid, vencedor com carimbo NOVO',
        pid == 19896 and '2026-11-08 00:09:18' in saida, saida.strip()[-60:] or 'sem frase')

    # A2: so' a vida antiga.
    pid = with_log(module, OLD,
                   lambda: module.wait_ready({19896}, since, timeout=1.5))
    arm('A2 vida anterior nao e` aceita', pid is None, 'pid=%r' % (pid,))

    # A3: a mutex recusou.
    pid = with_log(module, LOST,
                   lambda: module.wait_ready(set(), since, timeout=1.5))
    arm('A3 already_running=true nao e` vencedor', pid is None, 'pid=%r' % (pid,))

    # A4: arranque sem SINGLE_INSTANCE (perdedor silencioso).
    pid = with_log(module, SILENT,
                   lambda: module.wait_ready(set(), since, timeout=1.5))
    arm('A4 sem SINGLE_INSTANCE nao e` vencedor', pid is None, 'pid=%r' % (pid,))

    # A5: `since` no FUTURO -- nada nasceu depois dele, entao a resposta e' None.
    pid = with_log(module, OLD + NEW,
                   lambda: module.wait_ready({19896}, time.time() + 3600, timeout=1.5))
    arm('A5 since no futuro -> nenhum vencedor', pid is None, 'pid=%r' % (pid,))

    # A6: a frase de falha nomeia o ultimo carimbo visto.
    buf = io.StringIO()
    real_stdout, sys.stdout = sys.stdout, buf
    try:
        with_log(module, OLD, lambda: module.wait_ready({19896}, since, timeout=1.2))
    finally:
        sys.stdout = real_stdout
    saida = buf.getvalue()
    arm('A6 a falha nomeia o ultimo carimbo', '2026-11-03 11:42:17' in saida,
        saida.strip().splitlines()[-1][:70] if saida.strip() else 'sem frase')

    for name, ok, detail in results:
        print('  %s %-46s %s' % ('OK  ' if ok else 'FAIL', name, detail))
    bad = [r for r in results if not r[1]]
    return len(results) - len(bad), len(results)


def neg_arm(tmpdir):
    """Chave por PID de volta, numa COPIA: A1 TEM de cair."""
    src = io.open(TOOL, encoding='utf-8').read()
    mutated = src.replace(
        "            if stamp is not None and stamp < since:\n"
        "                continue          # linha de uma vida ANTERIOR do mesmo numero\n",
        "", 1)
    if mutated == src:
        print('  ?    a mutacao NAO pegou (ancora mudou)')
        print('NEG-ARM: FAIL -- 0/1 mutantes apanhados')
        return 0
    case = os.path.join(tmpdir, 'relauncher_mutant.py')
    io.open(case, 'w', encoding='utf-8').write(mutated)
    module = load(case, 'relauncher_mutant')
    good, total = run(module, 'MUTANT', tmpdir)
    caught = good < total
    print('NEG-ARM: %s -- %d/%d mutantes apanhados' % ('PASS' if caught else 'FAIL', 1 if caught else 0, 1))
    return 1 if caught else 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--neg-arm', action='store_true')
    args = parser.parse_args(argv)
    tmpdir = tempfile.mkdtemp(prefix='relaunch-ready-')
    if args.neg_arm:
        return neg_arm(tmpdir)
    module = load(TOOL)
    ok, total = run(module, 'VERDICT', tmpdir)
    print('VERDICT: %s -- %d/%d arm(s)' % ('PASS' if ok == total else 'FAIL', ok, total))
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main())
