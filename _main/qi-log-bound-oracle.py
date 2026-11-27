"""O registo do `QueryInterface` tem tecto, e o corte e' CONTADO.

`worker/sotto_worker.py` responde `QueryInterface` ao COM do Windows no caminho
do loopback por processo. A lista `qi_log` existia para a mensagem de erro de um
`ActivateCompleted` que nunca chega ("o handler respondeu a ...") e crescia a
cada pergunta: o MESMO IID volta a cada poll do player, dentro de um worker que
vive com o audio do dono. Uma lista sem tecto num processo de vida longa e'
memoria que ninguem devolve (medido 2026-11-27, triage row 10).

Agora a regra vive numa funcao pura -- `_plp_qi_record` -- e devolve
'new' | 'repeat' | 'dropped'. Distinguir 'ja perguntaram' de 'o tecto cortou' e'
o ponto: um corte confundido com repeticao e' o mesmo defeito com outro nome.

Este oraculo exercita a FUNCAO REAL do worker (importada, nao reescrita). Nao
precisa de WASAPI, de dispositivo, de audio nem de janela.

rc: 0 todos os bracos verdes; `--neg-arm` 1 quando todos os mutantes caem.
"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(ROOT, 'worker')
sys.path.insert(0, WORKER)

_LINE_CAP = 64


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def arm_cap_holds(rec):
    problems = []
    if rec._PLP_QI_LOG_CAP != _LINE_CAP:
        problems.append('the declared cap moved: %r (this oracle states 64)'
                        % (rec._PLP_QI_LOG_CAP,))
    log = []
    for i in range(rec._PLP_QI_LOG_CAP + 10):
        rec._plp_qi_record('iid-%03d' % i, log)
    if len(log) != rec._PLP_QI_LOG_CAP:
        problems.append('the log grew past its cap: %d entries' % len(log))
    return problems


def arm_drop_is_counted(rec):
    problems = []
    log = []
    verdicts = [rec._plp_qi_record('iid-%03d' % i, log)
                for i in range(rec._PLP_QI_LOG_CAP + 3)]
    if verdicts.count('dropped') != 3:
        problems.append('3 questions past the cap did not report 3 drops: %r'
                        % (verdicts[-5:],))
    if 'new' not in verdicts:
        problems.append('nothing was ever recorded')
    return problems


def arm_repeat_is_not_a_drop(rec):
    problems = []
    log = []
    if rec._plp_qi_record('iid-same', log) != 'new':
        problems.append('the FIRST question of an IID was not recorded as new')
    for _ in range(4):
        if rec._plp_qi_record('iid-same', log) != 'repeat':
            problems.append('the second question of the SAME IID was not a repeat')
            break
    for i in range(rec._PLP_QI_LOG_CAP + 5):
        rec._plp_qi_record('filler-%03d' % i, log)
    # A full log asked for an IID it ALREADY knows is still a repeat, never a
    # drop: the diagnostic already carries that interface.
    if rec._plp_qi_record('iid-same', log) != 'repeat':
        problems.append('a known IID in a FULL log is reported as a drop -- the '
                        'count then lies about which interface was missing')
    return problems


ARMS = (
    ('cap-holds', 'the log never exceeds the declared cap', arm_cap_holds),
    ('drop-is-counted', 'a question past the cap is counted, not swallowed', arm_drop_is_counted),
    ('repeat-is-not-a-drop', 'the same IID is a repeat, never a drop', arm_repeat_is_not_a_drop),
)


def run(mod):
    failures = []
    for name, what, fn in ARMS:
        try:
            problems = fn(mod)
        except Exception as exc:  # noqa: BLE001
            problems = ['the arm could not run: %r' % (exc,)]
        if problems:
            failures.append(name)
            print('   FAIL %-24s %s' % (name, what))
            for p in problems:
                print('        ' + p)
        else:
            print('   PASS %-24s %s' % (name, what))
    return failures


MUTANTS = (
    ('no-cap', '    if len(log) < _PLP_QI_LOG_CAP:\n        log.append(name)\n        return \'new\'\n',
     "    log.append(name)\n    return 'new'\n", 'cap-holds'),
    ('drop-counted-as-repeat', "    return 'dropped'\n", "    return 'repeat'\n", 'drop-is-counted'),
    ('repeat-counted-as-new', "    if name in log:\n        return 'repeat'\n", '', 'repeat-is-not-a-drop'),
)


def neg_arm(src):
    caught = 0
    for name, old, new, victim in MUTANTS:
        if src.count(old) != 1:
            print('   SETUP-ERROR %-24s anchor count=%d -- NOT counted as caught'
                  % (name, src.count(old)))
            continue
        path = os.path.join(_tmpdir(), 'mut_%s.py' % name.replace('-', '_'))
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(old, new))
        try:
            mod = load(path, 'sw_mut_qi_%s' % name.replace('-', '_'))
            arm_fn = {n: fn for n, _w, fn in ARMS}[victim]
            problems = arm_fn(mod)
        except Exception as exc:  # noqa: BLE001
            print('   SETUP-ERROR %-24s did not import: %r' % (name, exc))
            continue
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        if problems:
            caught += 1
            print('   RED   %-24s %s -> caught' % (name, victim))
        else:
            print('   GREEN %-24s %s stayed green -- the oracle cannot say no'
                  % (name, victim))
    print('MUTANTS: %d/%d caught' % (caught, len(MUTANTS)))
    return caught == len(MUTANTS)


def _tmpdir():
    import tempfile
    return tempfile.mkdtemp(prefix='sotto-qi-')


def main(argv):
    src = open(os.path.join(WORKER, 'sotto_worker.py'), encoding='utf-8').read()
    if '--neg-arm' in argv:
        ok = neg_arm(src)
        print('NEG-ARM: ' + ('PASS' if ok else 'FAIL'))
        return 1 if ok else 0
    try:
        mod = load(os.path.join(WORKER, 'sotto_worker.py'), 'sw_qi')
    except Exception as exc:  # noqa: BLE001
        print('IMPORT FALHOU: %r' % (exc,))
        return 2
    failures = run(mod)
    print('VERDICT: ' + ('FAIL' if failures else 'PASS'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
