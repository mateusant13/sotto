#!/usr/bin/env python
# NO-BUG: A ARVORE MORRE COM A SHELL -- provado por execucao, nao por argumento. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""A ARVORE MORRE COM A SHELL -- provado por execucao, nao por argumento.

MEDIDO 2026-11-04 nesta maquina: `taskkill /PID <shell> /T /F` matava a app e
deixava **QUATRO** `msedgewebview2.exe` filhos a deter `Local\\SottoShell`, e
cada largada seguinte abortava em 20 s. Um filtro de kill por palavra ja' matou
processos alheios aqui, portanto o que salva o dia tem de ser o SISTEMA: um JOB
OBJECT com `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, atribuido a` shell no arranque.
O Windows mata o job inteiro quando o ultimo handle fecha -- inclusive num
`TerminateProcess`, quando nenhum codigo Python corre.

Este oraculo prova a primitiva, nao o argumento:

  POSITIVO   um pai com o job arma, larga um filho que dorme, e morre com
             `os._exit` (sem limpeza nenhuma). O filho tem de estar MORTO.
  NEGATIVO   o mesmo pai SEM o job (`--neg-arm`). O filho tem de estar VIVO --
             se morresse, o positivo nao provaria nada (o filho podia estar a
             morrer por outra razao) e o oraculo diria que sim, o que e' o pior
             dos mundos.

O pai corre num processo separado (`--role=parent`) para que a morte dele seja
uma morte de verdade, e o filho e' um `python -c "sleep"` com `CREATE_NO_WINDOW`
(nenhuma janela, ordem do dono de 2026-11-02).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
NO_WINDOW = 0x08000000
SLEEP_S = 90


def _job_arm():
    """(True, None) se o job kill-on-close ficou armado neste processo."""
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)

    class _IO(ctypes.Structure):
        _fields_ = [('ReadOperationCount', ctypes.c_ulonglong),
                    ('WriteOperationCount', ctypes.c_ulonglong),
                    ('OtherOperationCount', ctypes.c_ulonglong),
                    ('ReadTransferCount', ctypes.c_ulonglong),
                    ('WriteTransferCount', ctypes.c_ulonglong),
                    ('OtherTransferCount', ctypes.c_ulonglong)]

    class _BASIC(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                    ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', wt.DWORD),
                    ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t),
                    ('ActiveProcessLimit', wt.DWORD),
                    ('Affinity', ctypes.c_size_t),
                    ('PriorityClass', wt.DWORD),
                    ('SchedulingClass', wt.DWORD)]

    class _EXT(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', _BASIC),
                    ('IoInfo', _IO),
                    ('ProcessMemoryLimit', ctypes.c_size_t),
                    ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t),
                    ('PeakJobMemoryUsed', ctypes.c_size_t)]

    k32.CreateJobObjectW.restype = wt.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return False, 'CreateJobObjectW winerror=%d' % ctypes.get_last_error()
    info = _EXT()
    info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(wt.HANDLE(job), 9, ctypes.byref(info),
                                       ctypes.sizeof(info)):
        return False, 'SetInformationJobObject winerror=%d' % ctypes.get_last_error()
    k32.GetCurrentProcess.restype = wt.HANDLE
    k32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
    k32.AssignProcessToJobObject.restype = wt.BOOL
    if not k32.AssignProcessToJobObject(wt.HANDLE(job),
                                        wt.HANDLE(k32.GetCurrentProcess())):
        return False, 'AssignProcessToJobObject winerror=%d' % ctypes.get_last_error()
    globals()['_JOB_KEEP'] = job      # o handle tem de viver: fecha-lo mata o job
    return True, None


def _alive(pid):
    ps = ['powershell', '-NoProfile', '-WindowStyle', 'Hidden',
          '-NonInteractive', '-Command',
          'try { Get-Process -Id %d -ErrorAction Stop | Out-Null; "VIVO" } '
          'catch { "MORTO" }' % pid]
    out = subprocess.run(ps, capture_output=True, text=True,
                         creationflags=NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0), timeout=60).stdout
    return 'VIVO' in out


def _parent(arm, pidfile):
    ok, why = (_job_arm() if arm else (False, 'desarmado (--neg-arm)'))
    if arm and not ok:
        print('JOB_ARM_FAILED %s' % why)
    child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(%d)' % SLEEP_S],
                             creationflags=NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    open(pidfile, 'w').write('%d|%s' % (child.pid, 'armed' if ok else 'disarmed'))
    print('JOB_PARENT job=%s child=%d' % ('armed' if ok else 'disarmed', child.pid))
    time.sleep(0.5)
    os._exit(0)      # morte sem limpeza: nenhum finally, nenhum CloseHandle


def main(argv):
    if '--role=parent' in argv:
        arm = '--neg-arm' not in argv
        pidfile = argv[argv.index('--pidfile') + 1]
        _parent(arm, pidfile)
        return 0

    neg = '--neg-arm' in argv
    pidfile = os.path.join(HERE, '_tmp', '_job-oracle-child.txt')
    os.makedirs(os.path.dirname(pidfile), exist_ok=True)
    try:
        os.remove(pidfile)
    except OSError:
        pass
    cmd = [sys.executable, os.path.abspath(__file__), '--role=parent',
           '--pidfile', pidfile]
    if neg:
        cmd.append('--neg-arm')
    subprocess.run(cmd, creationflags=NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0), timeout=120)
    time.sleep(2.0)
    try:
        pid, mode = open(pidfile).read().split('|')
    except Exception:                     # noqa: BLE001
        print('JOB_ORACLE FAIL -- o pai nao escreveu o pid do filho')
        return 1
    pid = int(pid)
    alive = _alive(pid)
    try:
        subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True,
                       creationflags=NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    except Exception:                     # noqa: BLE001
        pass

    if neg:
        if alive:
            print('NEG-ARM PASS (filho SEM job sobreviveu ao pai, como deve)')
            return 1
        print('NEG-ARM FAIL -- o filho morreu SEM job: o positivo nao prova nada')
        return 0
    if not alive:
        print('JOB-OBJECT PASS -- o filho morreu quando o pai morreu '
              '(kill-on-close do job, sem /T)')
        return 0
    print('JOB-OBJECT FAIL -- o filho SOBREVIVEU ao pai com o job armado')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
