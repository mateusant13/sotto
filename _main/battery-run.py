"""Corre a bateria inteira, escondida, e deixa o stdout num log.

Porta unica: `_main/hidden-launch.py` (CREATE_NO_WINDOW). O `.cmd` ja' se
re-cerca sozinho em `watcher run --cpu 40` antes do primeiro passo; este
ficheiro nao acrescenta tecto nenhum, so' tira a janela e guarda os bytes.

TECTO DECLARADO ANTES DO TRABALHO (regra de 2026-11-11): um trabalho pesado,
CPU limitada a 40 % de um nucleo pelo Job Object do watcher, os ~500 passos
declarados, total esperado ~2 140 s. Depois comparam-se os dois numeros.

PORQUE O rc E O VEREDICTO SAO JULGADOS AQUI TAMBEM (medido 2026-11-12): uma
corrida com `BATTERY-VERDICT: RED - 2 step(s) failed` e 'child exit code 1'
chegou a este largador como `rc=0` -- o `%ERRORLEVEL%` dentro do bloco do cage
era lido ANTES de o cage correr (curado em `_audit-verify-all.cmd`, subrotina
`:__battery_cage`). O `judge()` deste ficheiro e' o mesmo invariante visto do
OUTRO lado: se o rc e o veredicto discordarem, a corrida NAO conta e o processo
sai **3**, um codigo que nenhum passo devolve por acidente. O `--selftest` corre
o juiz sobre os tres casos (e o `--neg-arm` sobre o mutante), sem largar a
bateria -- e' por isso que ele serve de passo.

    python _main/battery-run.py               -> corre a bateria, rc = o veredicto
    python _main/battery-run.py --selftest    -> julga o juiz, rc 0 = passou
    python _main/battery-run.py --neg-arm     -> rc 1 ao apanhar a mutacao
"""
import io
import os
import subprocess
import sys
import time
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location(
    'hidden_launch', os.path.join(ROOT, '_main', 'hidden-launch.py'))
hl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hl)

SUMMARY = os.path.join(ROOT, '_main', '_audit-verify', '_battery-summary.txt')
TOO_OLD = '(sumario mais velho -- nao contado)'
NO_SUMMARY = '(sem sumario)'
DISAGREE_RC = 3
BUSY_RC = 4          # nenhum passo devolve este codigo por acidente
LOCK = os.path.join(ROOT, '_main', '_cache', 'battery-run.lock')


def read_verdict(summary, started_at):
    """O veredicto do sumario DESTA corrida, ou a razao de nao haver um.

    Um sumario mais velho que a corrida e' o caso que a casa ja' pagou: a corrida
    aborta antes do fim e o sumario ANTERIOR fica no disco a ler-se como o de agora.
    """
    try:
        if os.path.getmtime(summary) < started_at - 1.0:
            return TOO_OLD
        for line in io.open(summary, encoding='utf-8', errors='replace').read().splitlines():
            if line.startswith('BATTERY-VERDICT:'):
                return line.split(':', 1)[1].strip()
    except OSError:
        pass
    return NO_SUMMARY


def judge(rc, verdict):
    """-> (agrees, motivo). `agrees` e' None quando nao ha veredicto para comparar."""
    if verdict in (TOO_OLD, NO_SUMMARY):
        return None, verdict
    green = verdict.upper().startswith('GREEN')
    return (rc == 0) == green, verdict


def _proc_stamp(pid):
    """-> (pid, create_time|None). O carimbo existe para um pid RECICLADO nao herdar um cadeado."""
    try:
        import psutil
        return int(pid), float(psutil.Process(int(pid)).create_time())
    except Exception:
        return int(pid), None


def _holder_alive(text):
    """Um pid vivo e' o que torna o bloqueio real; um pid morto e' um cadeado esquecido."""
    parts = str(text or '').split()
    if not parts:
        return False
    try:
        pid = int(parts[0])
    except ValueError:
        return False
    stamp = None
    if len(parts) > 1:
        try:
            stamp = float(parts[1])
        except ValueError:
            stamp = None
    try:
        import psutil
        proc = psutil.Process(pid)
        if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
            return False
        if stamp is not None:
            return abs(proc.create_time() - stamp) < 1.0
        return True
    except Exception:
        pass
    try:
        os.kill(pid, 0)
        return True
    except OSError as exc:
        # winerror 5 = existe mas e' de outro utilizador; 87/22 = nao existe.
        return getattr(exc, 'winerror', None) == 5
    except Exception:
        return False


def acquire_lock(path=LOCK):
    """-> fh quando ESTA corrida fica dona do cadeado, None quando outra o tem.

    `O_CREAT|O_EXCL` e' a unica forma atomica aqui: dois largadores que perguntam
    "existe?" antes de criar ganham os dois. Um cadeado de um pid morto e' tomado,
    porque um cadeado esquecido nao pode bloquear a casa -- e no Windows um unlink
    sobre o ficheiro que o dono VIVO tem aberto levanta, o que faz do sistema de
    ficheiros uma segunda testemunha a favor da recusa.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    for attempt in (1, 2):
        try:
            fh = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                held = io.open(path, encoding='utf-8', errors='replace').read().strip()
            except OSError:
                held = ''
            if _holder_alive(held):
                return None
            if attempt == 2:
                return None
            print("BATTERY-LOCK stale pid=%s -- o dono do cadeado ja' nao existe; a toma-lo"
                  % (held.split()[0] if held.split() else '?'))
            try:
                os.unlink(path)
            except OSError:
                return None
            continue
        pid, stamp = _proc_stamp(os.getpid())
        line = '%d %s\n' % (pid, ('%.3f' % stamp) if stamp else '')
        os.write(fh, line.encode('ascii'))
        return fh
    return None


def release_lock(fh, path=LOCK):
    """Fecha e apaga -- nesta ordem, senao o unlink do Windows falha com o handle aberto."""
    if fh is None:
        return
    try:
        os.close(fh)
    except OSError:
        pass
    try:
        os.unlink(path)
    except OSError:
        pass


def run_battery():
    # O TRANSCRITO da corrida tem de comecar por `_`: a regra do `skip-verdict-guard`
    # diz que todo artefacto que a bateria escreve e' `_`-prefixado, e um transcript sem
    # o `_` e' lido como LOG DE PASSO -- foi exactamente esse o RED falso de 2026-11-12.
    lock = acquire_lock()
    if lock is None:
        try:
            held = io.open(LOCK, encoding='utf-8', errors='replace').read().strip()
        except OSError:
            held = ''
        print("BATTERY-BUSY pid=%s -- outra corrida e' dona de _main/_audit-verify; esta e' "
              "recusada (uma segunda corrida trunca os logs de passo e o sumario da primeira)"
              % (held.split()[0] if held.split() else '?'))
        return BUSY_RC
    try:
        log_path = os.path.join(ROOT, '_main', '_audit-verify',
                                '_battery-run-%s.log' % time.strftime('%Y%m%d-%H%M%S'))
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        t0 = time.time()
        with io.open(log_path, 'w', encoding='utf-8', newline='') as fh:
            proc = hl.popen(['cmd', '/c', r'_main\_audit-verify-all.cmd'],
                            cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
            rc = proc.wait()
    finally:
        release_lock(lock)
    agrees, verdict = judge(rc, read_verdict(SUMMARY, t0))
    print('battery rc=%s agrees=%s verdict=%s log=%s' % (rc, agrees, verdict, log_path))
    if agrees is False:
        print('BATTERY-RC/DISAGREE -- o rc e o veredicto nao podem discordar; a corrida NAO conta')
        return DISAGREE_RC
    return rc


def selftest(mutate):
    """Julga o JUIZ. Nenhuma bateria e' largada: so' aritmetica sobre os tres casos."""
    cases = [
        ('C1 rc=0 com veredicto RED e DISCORDANCIA', 0, 'RED - 2 step(s) failed', False),
        ('C2 rc=1 com veredicto RED concorda', 1, 'RED - 2 step(s) failed', True),
        ('C3 rc=0 com veredicto GREEN concorda', 0, 'GREEN WITH 24 SKIPPED', True),
        ('C4 rc=1 e sumario VELHO nao e veredicto', 1, TOO_OLD, None),
    ]
    if mutate:
        # A mutacao troca o caso que prova o defeito: o juiz passa a achar que 0 com RED
        # concorda. Uma tabela de casos que nao pode falhar nao e' um controlo.
        cases[0] = ('C1 MUTADO', 0, 'RED - 2 step(s) failed', True)
    ok = True
    # O CADEADO tem de ser julgado aqui: uma corrida dupla torna o veredicto da primeira
    # ilegivel (medido 2026-11-23: os dois logs de passo e o sumario truncados), e um guarda
    # que nunca recusa e' o mesmo defeito ao contrario.
    lock_path = os.path.join(ROOT, '_main', '_cache', 'battery-run-selftest.lock')
    try:
        os.unlink(lock_path)
    except OSError:
        pass
    if mutate:
        # A mutacao faz um pid MORTO ser lido como vivo: e' o ramo que a L3 julga -- com ele,
        # um cadeado esquecido bloqueia a casa para sempre.
        globals()['_holder_alive'] = lambda text: True
    l1 = acquire_lock(lock_path)
    ok_lock = l1 is not None
    print('  [%s] L1 adquire o cadeado' % ('PASS' if ok_lock else 'FAIL'))
    l2 = acquire_lock(lock_path)
    ok_lock = ok_lock and (l2 is None)
    print("  [%s] L2 a segunda corrida e' RECUSADA" % ('PASS' if l2 is None else 'FAIL'))
    if l2 is not None:
        release_lock(l2, lock_path)
    release_lock(l1, lock_path)
    with io.open(lock_path, 'w', encoding='utf-8', newline='') as fh:
        fh.write('999999 0\n')
    l3 = acquire_lock(lock_path)
    ok_lock = ok_lock and (l3 is not None)
    print('  [%s] L3 um pid morto nao bloqueia a casa (cadeado tomado)'
          % ('PASS' if l3 is not None else 'FAIL'))
    release_lock(l3, lock_path)
    ok_lock = ok_lock and not os.path.exists(lock_path)
    print('  [%s] L4 libertar apaga o cadeado' % ('PASS' if not os.path.exists(lock_path) else 'FAIL'))
    ok = ok and ok_lock
    try:                      # o mutante deixa o cadeado em disco: nao se sai de um selftest sujo
        os.unlink(lock_path)
    except OSError:
        pass
    if mutate and not ok_lock:
        print('BATTERY-RUN NEG-ARM: PASS -- a mutacao do cadeado foi apanhada')
        return 1
    for name, rc, verdict, want in cases:
        got, _ = judge(rc, verdict)
        good = got is want if want is None else got == want
        ok = ok and good
        print('  [%s] %s -- agrees=%s esperado=%s' % ('PASS' if good else 'FAIL', name, got, want))
    if mutate:
        if not ok:
            print('NEG-ARM: PASS -- a mutacao foi apanhada (%d/%d casos)' % (0, len(cases)))
            return 1
        print('NEG-ARM: FAIL -- a mutacao passou')
        return 0
    print('BATTERY-RUN SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main(argv):
    if '--selftest' in argv:
        return selftest(mutate=False)
    if '--neg-arm' in argv:
        return selftest(mutate=True)
    return run_battery()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
