"""A BATERIA CORRE UMA VEZ -- o cabecalho do cage nao pode CAIR no corpo.

MEDIDO 2026-11-12 18:1x, na corrida de `steps=501`: um unico `python _main/battery-run.py`
produziu **dois** planos (`PLAN steps=501` nas linhas 6 e 575), **dois** sumarios e
**1002** beacons de passo para 501 passos declarados -- a lista inteira correu duas
vezes, a segunda SEM o Job Object e a dizer `caged : ON`.

A causa vive no cabecalho. A cura de 2026-11-12 contra o `%ERRORLEVEL%` expandido
trocou o bloco por uma subrotina e deixou:

    call :__battery_cage
    if errorlevel 1 exit /b 1
    setlocal EnableDelayedExpansion   <- o CORPO comeca aqui

O `exit` so' acontece quando o filho FALHA: um filho caged que sai 0 atravessa o
`if` e o ficheiro cai no corpo, que entao corre na MESMA invocacao, sem tecto. Foi por
isso que a corrida RED de 14:34 teve um plano so' (rc=1 saia no `if`) e a corrida
GREEN das 15:12 teve dois -- o defeito e' invisivel exactamente no caso em que ele
mais custa.

A forma curada poe o corpo atras de um rotulo e manda-o para la' por `goto`, logo o
cabecalho NUNCA cai nele:

    if "%~1"=="--caged" goto :__battery_body
    if not defined SOTTO_BATTERY_NOCAGE if exist "...\\watcher\\__init__.py" goto :__battery_cage_outer
    :__battery_body
    setlocal EnableDelayedExpansion
    ...
    :__battery_cage_outer
    call :__battery_cage
    if errorlevel 1 exit /b 1
    exit /b 0

Este oraculo julga a SEMANTICA no cmd real desta maquina, com os dois bracos a largarem
o MESMO ficheiro como filho (`call "%~f0" --caged`), que e' a forma da bateria:

    A1  a forma ANTIGA corre o corpo DUAS vezes (o defeito e' real, e o instrumento ve')
    A2  a forma CURADA corre o corpo UMA vez
    A3  a forma CURADA devolve rc=1 quando o filho falha (o rc atravessa)

Nenhum braco abre janela, audio, modelo ou a app: o filho e' o proprio fixture de tres
linhas. `--neg-arm` repoe a forma antiga numa COPIA e exige A2 vermelha.

    python _main/cage-once-oracle.py             -> rc 0, tres arms verdes
    python _main/cage-once-oracle.py --neg-arm   -> rc 1 ao apanhar a mutacao
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, 'fixtures', 'cage-once')
OLD = os.path.join(FIXTURES, 'old.cmd')
NEW = os.path.join(FIXTURES, 'new.cmd')
FAILING = os.path.join(FIXTURES, 'fail.cmd')

_spec = importlib.util.spec_from_file_location(
    'sotto_hidden_launch', os.path.join(HERE, 'hidden-launch.py'))
_hl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hl)

BODY = 'BODY-RAN'


def run_fixture(path):
    """Corre o fixture no cmd real e devolve (rc, quantas vezes o corpo correu)."""
    rc, out, _err = _hl.run(['cmd', '/c', path], capture=True)
    return rc, (out or '').count(BODY)


def judge(old, new, failing):
    old_rc, old_body = old
    new_rc, new_body = new
    fail_rc, _fail_body = failing
    arms = [
        ('A1 a forma ANTIGA corre o corpo DUAS vezes (o defeito e real)',
         old_body == 2, 'corpo correu %d vez(es), rc=%s' % (old_body, old_rc)),
        ('A2 a forma CURADA corre o corpo UMA vez',
         new_body == 1, 'corpo correu %d vez(es), rc=%s' % (new_body, new_rc)),
        ('A3 a forma CURADA devolve o rc do filho que falha',
         fail_rc == 1, 'rc=%s (esperado 1)' % (fail_rc,)),
    ]
    return arms


def main():
    neg = '--neg-arm' in sys.argv
    missing = [p for p in (OLD, NEW, FAILING) if not os.path.exists(p)]
    if missing:
        print('CAGE-ONCE UNMEASURED -- fixtures ausentes: %s' % ', '.join(missing))
        return 2
    new_path = NEW
    tmpdir = None
    if neg:
        # MUTACAO: a forma curada volta a cair no corpo. O A2 TEM de a apanhar.
        tmpdir = tempfile.mkdtemp(prefix='cage-once-mut-')
        new_path = os.path.join(tmpdir, 'new-mutated.cmd')
        text = io.open(OLD, encoding='ascii', newline='').read()
        io.open(new_path, 'w', encoding='ascii', newline='').write(text)

    old = run_fixture(OLD)
    new = run_fixture(new_path)
    failing = run_fixture(FAILING)
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)

    arms = judge(old, new, failing)
    for name, ok, detail in arms:
        print('  [%s] %s -- %s' % ('PASS' if ok else 'FAIL', name, detail))
    good = all(ok for _, ok, _ in arms)
    if neg:
        # A convencao da casa: o negativo devolve 1 QUANDO APANHA.
        if not good:
            print('NEG-ARM: PASS -- a mutacao foi apanhada (corpo x%s)' % new[1])
            return 1
        print('NEG-ARM: FAIL -- a mutacao passou (corpo x%s)' % new[1])
        return 0
    print('CAGE-ONCE VERDICT: %s (%d/%d arms)' % ('PASS' if good else 'FAIL',
                                                  sum(1 for _, ok, _ in arms if ok),
                                                  len(arms)))
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
