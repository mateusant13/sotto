#!/usr/bin/env python
"""step-deadline -- um PRAZO por passo da bateria, com a arvore morta no fim.

O DEFEITO QUE ISTO FECHA (medido 2026-11-05, nesta maquina).

`_main/youtube-cdp-boot-oracle.py` arrancou as 13:20:48 e ficou **21,6 minutos**
dentro de um processo cujo codigo tem esperas de 3-4 s; `_main/panel-hidden-at-
startup-oracle.py` gastou **3 781,6 s (63 min) num unico passo** na corrida de
01:06. Nenhum dos dois tem prazo, e nem o `.cmd` da bateria tem: `!S_CMD!` corre
ate' acabar. Um oraculo preso transforma-se em hora de parede, e o sumario dessa
corrida **nunca chega a existir** -- o ficheiro que fica no disco e' o da corrida
ANTERIOR, que se le' como se fosse o veredicto de agora.

O QUE ESTA FERRAMENTA FAZ. Corre o comando que lhe derem como FILHO (sem consola
visivel: o mesmo caminho de `_main/hidden-launch.py`), espera, e no prazo:

  * escreve `STEP-DEADLINE exceeded step=<nome> seconds=<N> killed=<pids>` na
    saida do passo (que a bateria ja' redireciona para o log dele),
  * mata a ARVORE pelos pids que ela propria criou (nunca por uma palavra
    generica -- a regra da casa),
  * devolve **rc=124**, que nenhum oraculo devolve por acidente e que o `:step`
    registra como falha. Um passo cortado NAO e' um passo que passou.

O rc do filho atravessa tal e qual quando ele termina a tempo: o wrapper nao
julga nada, so' poe o relogio.

Uso:
    python _main/step-deadline.py --seconds 240 -- python _main\algo.py --neg-arm
    python _main/step-deadline.py --seconds 5 -- <comando>      (prazo curto)
    python _main/step-deadline.py --selftest                    -> prova o proprio detector
"""
from __future__ import annotations

import ctypes
import io
import os
import runpy
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SECONDS = 240.0
#: O rc do corte. `timeout(1)` usa 124 e a convencao existe para o numero ser
#: reconhecivel no sumario sem ninguem consultar o codigo deste ficheiro.
DEADLINE_RC = 124

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_uint32),
                ('cntUsage', ctypes.c_uint32),
                ('th32ProcessID', ctypes.c_uint32),
                ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
                ('th32ModuleID', ctypes.c_uint32),
                ('cntThreads', ctypes.c_uint32),
                ('th32ParentProcessID', ctypes.c_uint32),
                ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', ctypes.c_uint32),
                ('szExeFile', ctypes.c_wchar * 260)]


def _children_map():
    """ppid -> [pid]. Uma enumeracao por chamada, nunca um `OpenProcess` por nos."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == -1:
        return {}
    out = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if k32.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                out.setdefault(int(entry.th32ParentProcessID), []).append(
                    (int(entry.th32ProcessID), entry.szExeFile))
                if not k32.Process32NextW(snap, ctypes.byref(entry)):
                    break
    finally:
        k32.CloseHandle(snap)
    return out


def _live_pids():
    """Quem AINDA existe, pela tabela do sistema (nao por um handle que fica de pe').

    MEDIDO no braco A2: um pid TERMINADO continuava a abrir handle
    (`OpenProcess(0x1000, ...)` devolvia um sem falhar), e o selftest acusava
    dois `ainda-vivos` depois de os ter matado. Um handle que abre nao e' prova
    de vida -- a lista de processos e'.
    """
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    alive = set()
    if not snap or snap == -1:
        return alive
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if k32.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                alive.add(int(entry.th32ProcessID))
                if not k32.Process32NextW(snap, ctypes.byref(entry)):
                    break
    finally:
        k32.CloseHandle(snap)
    return alive


def descendants(pid):
    table = _children_map()
    seen, stack, rows = set(), [int(pid)], []
    while stack:
        for child, name in table.get(stack.pop(), []):
            if child in seen:
                continue
            seen.add(child)
            rows.append((child, name))
            stack.append(child)
    return rows


JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [('ReadOperationCount', ctypes.c_ulonglong),
                ('WriteOperationCount', ctypes.c_ulonglong),
                ('OtherOperationCount', ctypes.c_ulonglong),
                ('ReadTransferCount', ctypes.c_ulonglong),
                ('WriteTransferCount', ctypes.c_ulonglong),
                ('OtherTransferCount', ctypes.c_ulonglong)]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                ('PerJobUserTimeLimit', ctypes.c_int64),
                ('LimitFlags', ctypes.c_uint32),
                ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', ctypes.c_uint32),
                ('Affinity', ctypes.c_size_t),
                ('PriorityClass', ctypes.c_uint32),
                ('SchedulingClass', ctypes.c_uint32)]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ('IoInfo', IO_COUNTERS),
                ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t),
                ('PeakJobMemoryUsed', ctypes.c_size_t)]


def job_create():
    """Um JOB com kill-on-close: o corte mata EXACTAMENTE quem esta' no job.

    A CAMINHADA PELA ARVORE FOI MEDIDA COMO ERRADA, e o erro matou processos
    alheios: `descendants()` le' ppid->filhos de uma fotografia GLOBAL, e um
    `conhost.exe` partilhado entrega como "filhos" processos que este instrumento
    nunca largou. Medido 2026-11-05: um corte de 2 s matou **dois cargo.exe** de
    outra lane. O job object nao pergunta a ninguem: so' contem o filho, os netos
    herdam-no, e `TerminateJobObject` nao alcanca nada fora dele.
    """
    k32.CreateJobObjectW.restype = ctypes.c_void_p
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    k32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                            ctypes.c_void_p, ctypes.c_uint32]
    ok = k32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                     ctypes.byref(info), ctypes.sizeof(info))
    return job if ok else None


def job_assign(job, pid):
    k32.OpenProcess.restype = ctypes.c_void_p
    h = k32.OpenProcess(0x0100 | 0x0001, False, int(pid))  # SET_QUOTA|TERMINATE
    if not h:
        return False
    k32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    ok = k32.AssignProcessToJobObject(job, h)
    k32.CloseHandle(h)
    return bool(ok)


def job_terminate(job, code=DEADLINE_RC):
    k32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    return bool(k32.TerminateJobObject(job, code))


def job_close(job):
    if job:
        k32.CloseHandle(job)


def run_with_deadline(argv, seconds=None, log=print):
    """Corre `argv`, corta-a no prazo, devolve (rc, killed)."""
    seconds = float(seconds or DEFAULT_SECONDS)
    ns = runpy.run_path(os.path.join(HERE, 'hidden-launch.py'))
    t0 = time.monotonic()
    # A SAIDA DO FILHO VAI PARA O NOSSO STDOUT -- a bateria redireciona-a para o
    # log do passo, e o log E' EVIDENCIA: devnull aqui apagava o veredicto de cada
    # oraculo (medido nesta sessao: o filho escreveu `ran` e o log ficou vazio).
    proc = ns['popen'](list(argv))
    job = job_create()
    in_job = bool(job) and job_assign(job, proc.pid)
    try:
        rc = proc.wait(timeout=seconds)
        return int(rc), []
    except subprocess.TimeoutExpired:
        before = {pid for pid, _ in descendants(proc.pid)} | {proc.pid}
        if in_job:
            job_terminate(job)
        else:
            # SEM JOB (raro: o processo ja' esta' num job que recusa heranca) so'
            # o FILHO e' morto por handle -- nunca uma caminhada de arvore, que ja'
            # matou processos alheios (ver `job_create`).
            try:
                k32.TerminateProcess(k32.OpenProcess(0x0001, False, proc.pid), 1)
            except Exception:  # noqa: BLE001 -- ja' morto
                pass
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001 -- o kill ja' foi ordenado
            pass
        time.sleep(0.15)
        live = _live_pids()
        killed = ['%d' % pid for pid in sorted(before) if pid not in live]
        spent = time.monotonic() - t0
        log('STEP-DEADLINE exceeded step=%s seconds=%.1f killed=%d%s job=%s'
            % (os.environ.get('SOTTO_STEP_NAME') or '<unnamed>', spent,
               len(killed), (':' + ','.join(killed)) if killed else '', 'yes' if in_job else 'no'))
        job_close(job)
        return DEADLINE_RC, killed


# ---------------------------------------------------------------------------
# SELFTEST -- o detector medido em quatro arms, com os filhos VISIVEIS
# ---------------------------------------------------------------------------
def selftest():
    ok = True
    py = sys.executable

    # A1: um filho rapido passa, e o rc dele chega intacto
    rc, killed = run_with_deadline([py, '-c', 'import sys; sys.exit(3)'],
                                   seconds=30)
    a1 = (rc == 3 and not killed)
    print('A1 filho rapido: rc=%s killed=%d -> %s' % (rc, len(killed),
                                                      'PASS' if a1 else 'FAIL'))
    ok &= a1

    # A2: o corte dispara, o rc e' 124 e o filho NAO existe mais
    rc, killed = run_with_deadline([py, '-c', 'import time; time.sleep(60)'],
                                   seconds=1.5)
    a2 = (rc == DEADLINE_RC and killed)
    live_now = _live_pids()
    alive = [int(item.split(':')[0]) for item in killed
             if int(item.split(':')[0]) in live_now]
    a2 = a2 and not alive
    print('A2 prazo de 1,5 s: rc=%s killed=%d ainda-vivos=%d -> %s'
          % (rc, len(killed), len(alive), 'PASS' if a2 else 'FAIL'))
    ok &= a2

    # A3: a ARVORE morre, nao so' o pai -- um neto que escreve um ficheiro
    import tempfile
    marker = os.path.join(tempfile.mkdtemp(prefix='sotto-deadline-'), 'neto.txt')
    inner = ('import time,sys\n'
             'time.sleep(3)\n'
             'open(sys.argv[1],"w").write("x")\n')
    code = ('import subprocess, sys, time\n'
            'subprocess.Popen([sys.executable, "-c", %r, %r])\n'
            'time.sleep(60)\n' % (inner, marker))
    rc, killed = run_with_deadline([py, '-c', code], seconds=1.5)
    time.sleep(4.5)
    grandchild_wrote = os.path.exists(marker)
    a3 = (rc == DEADLINE_RC and not grandchild_wrote)
    print('A3 neto morto com o pai: rc=%s neto_escreveu=%s -> %s'
          % (rc, str(grandchild_wrote).lower(), 'PASS' if a3 else 'FAIL'))
    ok &= a3

    # A4: um rc NAO-zero de um filho que termina a tempo nao e' confundido com 124
    rc, _ = run_with_deadline([py, '-c', 'import sys; sys.exit(1)'], seconds=30)
    a4 = (rc == 1)
    print('A4 rc=1 do filho a tempo: rc=%s -> %s' % (rc, 'PASS' if a4 else 'FAIL'))
    ok &= a4


    # A5: UM PROCESSO ALHEIO SOBREVIVE AO CORTE. Nascida de um defeito medido:
    # a caminhada pela arvore matou DOIS cargo.exe de outra lane porque um
    # `conhost.exe` partilhado entregava processos que este instrumento nunca
    # largou. O job object so' mata quem esta' dentro dele.
    alien = subprocess.Popen([py, '-c', 'import time; time.sleep(20)'])
    time.sleep(0.4)
    rc, killed = run_with_deadline([py, '-c', 'import time; time.sleep(60)'],
                                   seconds=1.2)
    time.sleep(0.2)
    alien_alive = alien.poll() is None
    a5 = (rc == DEADLINE_RC and alien_alive)
    print('A5 alheio sobrevive: rc=%s alheio_vivo=%s -> %s'
          % (rc, str(alien_alive).lower(), 'PASS' if a5 else 'FAIL'))
    ok &= a5
    try:
        alien.terminate()
        alien.wait(timeout=5)
    except Exception:  # noqa: BLE001 -- limpeza do proprio braco
        pass


    # A6: `--neg-arm` DO FILHO NAO E' DESTE WRAPPER. Nascida do defeito medido na
    # corrida de 2026-11-05: 90 passos vermelhos porque o argv do filho era lido
    # como se fosse o nosso e o wrapper corria o SEU neg-arm.
    import tempfile as _tf6
    marker6 = os.path.join(_tf6.mkdtemp(prefix='sotto-deadline-a6-'), 'filho.txt')
    rc, killed = run_with_deadline(
        [py, '-c', 'import sys; open(sys.argv[1],"w").write(" ".join(sys.argv[2:]))',
         marker6, '--neg-arm'], seconds=30)
    wrote = os.path.exists(marker6) and io.open(marker6, encoding='utf-8').read().strip() == '--neg-arm'
    a6 = (rc == 0 and wrote and not killed)
    print('A6 --neg-arm do filho chega ao filho: rc=%s filho_viu_o_flag=%s -> %s'
          % (rc, str(wrote).lower(), 'PASS' if a6 else 'FAIL'))
    ok &= a6

    print('STEP-DEADLINE SELFTEST: %s (6 arms)' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def neg_arm():
    """MUTA uma COPIA: sem o kill, o prazo deixa de cortar. O selftest tem de dar RED."""
    import shutil
    import subprocess
    import tempfile
    src = os.path.abspath(__file__)
    tmp = tempfile.mkdtemp(prefix='sotto-deadline-neg-')
    try:
        copy = os.path.join(tmp, 'step-deadline.py')
        shutil.copy2(src, copy)
        # A irma' `hidden-launch.py` tem de estar ao lado: o modulo a importa.
        shutil.copy2(os.path.join(HERE, 'hidden-launch.py'),
                     os.path.join(tmp, 'hidden-launch.py'))
        raw = io.open(copy, encoding='utf-8', newline='').read()
        old = '            job_terminate(job)'
        if old not in raw:
            print('NEG-ARM IMPOSSIVEL -- ancora ausente')
            return 1
        io.open(copy, 'w', encoding='utf-8', newline='').write(
            raw.replace(old, '            pass', 1))
        proc = subprocess.run([sys.executable, copy, '--selftest'],
                              capture_output=True, text=True, timeout=180)
        caught = proc.returncode != 0 and 'FAIL' in proc.stdout
        print(proc.stdout.strip())
        print('NEG-ARM: %s (o mutante sem kill foi %s)'
              % ('PASS' if caught else 'FAIL',
                 'APANHADO' if caught else 'NAO APANHADO'))
        return 1 if caught else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    # AS BANDEIRAS DESTE WRAPPER VIVEM SO' ANTES DO `--`. A primeira versao
    # procurava `--neg-arm` em TODO o argv -- e o argv inclui os tokens do FILHO,
    # logo um passo cujo comando e' `python _main\X-oracle.py --neg-arm` fazia o
    # WRAPPER correr o SEU proprio selftest e nunca o filho. Medido numa corrida
    # inteira (2026-11-05): 90 passos vermelhos, e todos os logs `*-neg.log` com a
    # saida do neg-arm DESTE ficheiro em vez da do oraculo. O braco A6 existe para
    # este defeito nao voltar.
    if '--' in argv:
        cut = argv.index('--')
        own, child = argv[:cut], argv[cut + 1:]
    else:
        own = list(argv)
        child = []
        if '--seconds' in own:
            i = own.index('--seconds')
            del own[i:i + 2]
    if '--neg-arm' in own:
        return neg_arm()
    if '--selftest' in own:
        return selftest()
    seconds = DEFAULT_SECONDS
    if '--seconds' in own:
        seconds = float(own[own.index('--seconds') + 1])
    if not child:
        sys.stderr.write('step-deadline: sem comando depois de `--`\n')
        return 1
    rc, _ = run_with_deadline(child, seconds=seconds)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
