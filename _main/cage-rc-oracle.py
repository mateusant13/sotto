"""O rc de um bloco entre parenteses e' lido ANTES de o bloco correr.

MEDIDO 2026-11-12: uma corrida da bateria com `BATTERY-VERDICT: RED - 2 step(s) failed`
e `child exit code 1` chegou ao largador como `rc=0`. A causa vive no cabecalho de
`_main/_audit-verify-all.cmd`, no bloco do cage:

    if exist "...watcher\\__init__.py" (
      ...
      python -m watcher run --cpu 40 -- cmd /c ""%~f0" --caged"
      exit /b %ERRORLEVEL%          <- expandido quando o BLOCO e' LIDO
    )

`%ERRORLEVEL%` num bloco entre parenteses e' substituido quando o cmd LE o bloco inteiro,
ou seja antes de o cage correr: o `exit /b` devolve o codigo de ANTES. A forma curada
chama uma SUBROTINA (`call :__battery_cage`), cujas linhas sao relidas uma a uma, mais
`if errorlevel 1 exit /b 1`, que nao depende de expansao nenhuma.

Este oraculo julga as DUAS formas, executando-as no cmd real desta maquina, com o mesmo
filho a sair 1. A populacao e' minima de proposito: o que se mede e' a semantica do
interpretador, nao a bateria -- e nenhum dos dois bracos abre janela, audio ou modelo.

    python _main/cage-rc-oracle.py             -> rc 0, as duas arms verdes
    python _main/cage-rc-oracle.py --neg-arm   -> rc 1 ao apanhar a mutacao (a forma
                                                  curada trocada pela antiga)
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, 'fixtures', 'cage-rc')

# O FILHO ARRANCA PELO `hidden-launch`, nunca por um `subprocess.run` local: o censo
# `_main/console-window-audit.py` classificou a versao anterior como `WEAK-FLAG`
# (`creationflags` sem `startupinfo`) e a bateria ficou RED com razao -- a bandeira
# sozinha nao cobre um filho que ignora `CREATE_NO_WINDOW`. O helper carrega as duas
# guardas e e' o mesmo caminho que o resto desta arvore usa.
_spec = importlib.util.spec_from_file_location(
    'sotto_hidden_launch', os.path.join(HERE, 'hidden-launch.py'))
_hl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hl)
OLD = os.path.join(FIXTURES, 'old.cmd')
NEW = os.path.join(FIXTURES, 'new.cmd')
CHILD_RC = 1


def run_fixture(path):
    """Corre um fixture no cmd real e devolve o rc que ELE devolve."""
    rc, _out, _err = _hl.run(['cmd', '/c', path])
    return rc


def judge(old_rc, new_rc):
    arms = [
        ('A1 a forma antiga PERDE o rc do filho (o defeito e real)',
         old_rc == 0, 'rc antigo=%s (esperado 0: e o defeito)' % old_rc),
        ('A2 a subrotina DEVOLVE o rc do filho',
         new_rc == CHILD_RC, 'rc novo=%s (esperado %s)' % (new_rc, CHILD_RC)),
    ]
    return arms


def main():
    neg = '--neg-arm' in sys.argv
    if not (os.path.exists(OLD) and os.path.exists(NEW)):
        print('CAGE-RC UNMEASURED -- fixtures ausentes em %s' % FIXTURES)
        return 2
    old_rc = run_fixture(OLD)
    new_path = NEW
    tmpdir = None
    if neg:
        # MUTACAO: a forma curada volta a ser a antiga. O oraculo TEM de a apanhar.
        tmpdir = tempfile.mkdtemp(prefix='cage-rc-mut-')
        new_path = os.path.join(tmpdir, 'new-mutated.cmd')
        text = io.open(OLD, encoding='ascii', newline='').read()
        io.open(new_path, 'w', encoding='ascii', newline='').write(text)
    new_rc = run_fixture(new_path)
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)

    arms = judge(old_rc, new_rc)
    for name, ok, detail in arms:
        print('  [%s] %s -- %s' % ('PASS' if ok else 'FAIL', name, detail))
    good = all(ok for _, ok, _ in arms)
    if neg:
        # A convencao da casa: o negativo devolve 1 QUANDO APANHA.
        if not good:
            print('NEG-ARM: PASS -- a mutacao foi apanhada (old=%s new=%s)' % (old_rc, new_rc))
            return 1
        print('NEG-ARM: FAIL -- a mutacao passou (old=%s new=%s)' % (old_rc, new_rc))
        return 0
    print('CAGE-RC VERDICT: %s (%d/%d arms)' % ('PASS' if good else 'FAIL',
                                                sum(1 for _, ok, _ in arms if ok), len(arms)))
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
