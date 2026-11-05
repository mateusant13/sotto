"""CPU POR FIO da shell VIVA, com o NOME de cada fio -- de fora do processo.

Analogo ao `py-spy top`, e existe porque o `py-spy` NAO consegue anexar-se a esta
shell: ela corre em integridade `high` (o desktop do dono) e esta pane em
`medium`, e `py-spy record --pid <shell>` devolve `Acesso negado (os error 5)`.
MEDIDO 2026-11-05. O que o Windows oferece sem privilegio nenhum:

  * `Toolhelp32Snapshot(TH32CS_SNAPTHREAD)` -- os fios do processo;
  * `OpenThread(THREAD_QUERY_LIMITED_INFORMATION)` -- alca de consulta;
  * `GetThreadTimes` -- CPU (user+kernel) de CADA fio, exato, acumulado;
  * `GetThreadDescription` -- o nome que `app/webview/thread_names.py` escreve.

O QUE ISTO RESPONDEU (primeira corrida real, pid da shell do dono em 2026-11-05):
o fio que queimava o nucleo tinha nome, e o numero deixou de ser uma suspeita.

USO
    python _main/shell-thread-cpu.py <pid> [--seconds 8] [--top 12]
    python _main/shell-thread-cpu.py --neg-arm
"""
from __future__ import annotations

import ctypes
import sys
import time

TH32CS_SNAPTHREAD = 0x00000004
THREAD_QUERY_LIMITED_INFORMATION = 0x0800
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class THREADENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_ulong),
                ('cntUsage', ctypes.c_ulong),
                ('th32ThreadID', ctypes.c_ulong),
                ('th32OwnerProcessID', ctypes.c_ulong),
                ('tpBasePri', ctypes.c_long),
                ('tpDeltaPri', ctypes.c_long),
                ('dwFlags', ctypes.c_ulong)]


class FILETIME(ctypes.Structure):
    _fields_ = [('dwLowDateTime', ctypes.c_ulong),
                ('dwHighDateTime', ctypes.c_ulong)]


def _u64(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def sample(pid: int) -> dict:
    """{tid: (cpu_seconds, name)} de um processo, lido agora."""
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snap == INVALID_HANDLE_VALUE:
        return {}
    out = {}
    entry = THREADENTRY32()
    entry.dwSize = ctypes.sizeof(THREADENTRY32)
    ok = k.Thread32First(snap, ctypes.byref(entry))
    while ok:
        if entry.th32OwnerProcessID == pid:
            tid = int(entry.th32ThreadID)
            h = k.OpenThread(THREAD_QUERY_LIMITED_INFORMATION, False, tid)
            if h:
                try:
                    c, e, ku, ke = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                    got = k.GetThreadTimes(ctypes.c_void_p(h), ctypes.byref(c),
                                           ctypes.byref(e), ctypes.byref(ku),
                                           ctypes.byref(ke))
                    cpu = (((_u64(ku) + _u64(ke)) / 1e7)
                           if got else 0.0)
                    name = ''
                    fn = getattr(k, 'GetThreadDescription', None)
                    if fn is not None:
                        buf = ctypes.c_void_p()
                        try:
                            fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
                            fn.restype = ctypes.c_long
                            if int(fn(ctypes.c_void_p(h), ctypes.byref(buf))) >= 0 and buf.value:
                                name = ctypes.wstring_at(buf.value)
                                k.LocalFree(ctypes.c_void_p(buf.value))
                        except Exception:            # noqa: BLE001
                            name = ''
                    out[tid] = (cpu, name)
                finally:
                    k.CloseHandle(ctypes.c_void_p(h))
        ok = k.Thread32Next(snap, ctypes.byref(entry))
    k.CloseHandle(ctypes.c_void_p(snap))
    return out


def rank(before: dict, after: dict, elapsed: float) -> list:
    """[(pct, cpu_s, tid, name)] ordenado -- funcao PURA (o oraculo julga-a)."""
    rows = []
    for tid, (cpu1, name) in after.items():
        cpu0 = before.get(tid, (cpu1, name))[0]
        used = cpu1 - cpu0
        if used <= 0:
            continue
        pct = (used / elapsed * 100.0) if elapsed > 0 else 0.0
        rows.append((pct, used, tid, name or '(sem nome)'))
    rows.sort(key=lambda r: (-r[0], r[2]))
    return rows


def main(argv):
    if '--neg-arm' in argv:
        return _neg_arm()
    if not argv or not argv[0].isdigit():
        print('uso: shell-thread-cpu.py <pid> [--seconds N] [--top N]')
        return 2
    pid = int(argv[0])
    seconds = 8.0
    top = 14
    for i, a in enumerate(argv):
        if a == '--seconds' and i + 1 < len(argv):
            seconds = float(argv[i + 1])
        if a == '--top' and i + 1 < len(argv):
            top = int(argv[i + 1])
    before = sample(pid)
    if not before:
        print('sem fios para o pid %d (processo fechado ou sem permissao)' % pid)
        return 3
    t0 = time.monotonic()
    time.sleep(seconds)
    after = sample(pid)
    elapsed = time.monotonic() - t0
    rows = rank(before, after, elapsed)
    total = sum(r[0] for r in rows)
    print('pid %d: %d fios, %.1f s de janela, %.1f%% de um nucleo no total'
          % (pid, len(after), elapsed, total))
    print('%8s %8s %7s  %s' % ('pct', 'cpu_s', 'tid', 'nome'))
    for pct, used, tid, name in rows[:top]:
        print('%7.1f%% %8.2f %7d  %s' % (pct, used, tid, name))
    return 0


def _neg_arm():
    """Controlo PURO do juiz: nenhum processo, nenhum pixel na tela dele."""
    before = {1: (1.00, 'sotto-yt'), 2: (5.00, 'sotto-worker-wait'), 3: (0.50, '')}
    after = {1: (2.00, 'sotto-yt'), 2: (5.10, 'sotto-worker-wait'), 3: (0.50, '')}
    rows = rank(before, after, 2.0)
    cases = []

    def add(ok, title):
        cases.append(ok)
        print(('PASS ' if ok else 'FAIL ') + title)

    add(len(rows) == 2, 'N1 so o fio que GASTOU CPU aparece (o parado sai)')
    add(rows and rows[0][3] == 'sotto-yt',
        'N2 o mais quente vem primeiro e com o nome do fio')
    add(rows and abs(rows[0][0] - 50.0) < 0.01,
        'N3 a percentagem e a variacao sobre a janela (1 s em 2 s = 50%)')
    add(rows and rows[0][2] == 1, 'N4 o tid identifica o fio')
    zero = rank(before, after, 0.0)
    add(zero and all(r[0] == 0.0 for r in zero),
        'N5 janela de zero segundos nao divide por zero')
    print('\nNEG-ARM check=%d/%d' % (sum(1 for c in cases if c), len(cases)))
    caught = sum(1 for c in cases if c) != len(cases)
    print('NEG-ARM %s' % ('PASS' if not caught else 'FAIL'))
    return 1 if not caught else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
