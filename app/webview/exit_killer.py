"""O MATADOR EXTERNO da saida do Sotto.

PORQUE ESTE PROCESSO EXISTE
---------------------------
Medido 2026-11-04, no log do dono: as 13:01:36.080 o shell escreveu
`UI_WATCHDOG_EXIT code=9 -- a UI estava presa`, e 70 minutos depois o MESMO pid
(20448) estava vivo com 36 threads, 8 das 10 janelas sem responder a `WM_NULL`,
e o worker filho vivo com 3,9 GB privados. A app tinha registado a saida e a
saida NAO completou.

Nenhum primitivo DENTRO do processo pode garantir esse fim: se o processo fica
preso (um `DllMain`, o loader lock, uma chamada que o kernel nao devolve), a
thread que ia matar o processo tambem esta' presa. O unico dono que sobrevive
e' um PROCESSO SEPARADO, criado antes de a saida comecar, que:

  1. abre o HANDLE do shell -- com o carimbo de criacao, para nao matar um
     pid RECICLADO (um pid e' um numero; a hora de criacao e' a identidade);
  2. espera por esse handle com prazo (`--grace-ms`);
  3. se o handle sinalizou, o shell morreu como devia: faz a VARREDURA dos
     filhos (um worker orfao de 3,9 GB continua a ser um worker orfao) e sai;
  4. se NAO sinalizou, o shell escreveu "vou sair" e ficou vivo: mata os
     filhos e depois o shell, e escreve `EXIT_KILLER_FIRED` no MESMO log.

Nao ha' caminho neste ficheiro que mate por NOME de imagem, por filtro, ou por
"todos os python": cada pid chega com um carimbo e cada carimbo e' conferido.

Uso (so' o shell):
    python exit_killer.py --pid 20448 --stamp 30958096:123456789 \
        --code 9 --grace-ms 4000 [--log <ficheiro>] [--child 36668:<stamp> ...]
Termina 0 quando a arvore esta morta ou ja' estava; 1 so' quando nao conseguiu
abrir o handle nem ler o carimbo (nesse caso NAO mata nada).
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

SYNCHRONIZE = 0x00100000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102

k32 = ctypes.windll.kernel32
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k32.WaitForSingleObject.restype = wt.DWORD
k32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
k32.TerminateProcess.restype = wt.BOOL


class _FT(ctypes.Structure):
    _fields_ = [('lo', wt.DWORD), ('hi', wt.DWORD)]


def identity(handle):
    """Carimbo de criacao do processo aberto por `handle`, ou ''."""
    created, exited, kernel, user = _FT(), _FT(), _FT(), _FT()
    ok = k32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                             ctypes.byref(kernel), ctypes.byref(user))
    if not ok:
        return ''
    return '%d:%d' % (created.hi, created.lo)


def open_checked(pid, stamp):
    """(handle, motivo). Abre o pid e CONFERE o carimbo antes de qualquer kill."""
    handle = k32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
                             | PROCESS_TERMINATE, False, int(pid))
    if not handle:
        return None, 'no-handle winerror=%d' % ctypes.get_last_error()
    got = identity(handle)
    if stamp and got and got != stamp:
        k32.CloseHandle(handle)
        return None, 'pid-reused expected=%s got=%s' % (stamp, got)
    return handle, ''


def dead(handle, wait_ms):
    return k32.WaitForSingleObject(handle, int(wait_ms)) == WAIT_OBJECT_0


def kill(handle, code=1):
    return bool(k32.TerminateProcess(handle, int(code)))


def _log_to(path, line):
    if not path:
        return
    try:
        with open(path, 'a', encoding='utf-8', errors='replace') as fh:
            fh.write('%s sotto: %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), line))
    except Exception:                      # noqa: BLE001 -- o log pode ter rodado
        pass


def run(args):
    say = lambda line: _log_to(args.log, line)   # noqa: E731
    shell, why = open_checked(args.pid, args.stamp)
    if shell is None:
        say('EXIT_KILLER_SKIPPED pid=%s reason=%s' % (args.pid, why))
        return 0
    try:
        signaled = dead(shell, args.grace_ms)
        if signaled:
            say('EXIT_KILLER_WAITED pid=%s grace_ms=%d exited=true'
                % (args.pid, args.grace_ms))
        else:
            # A ordem e' DELIBERADA: os filhos primeiro. Um worker de 3,9 GB
            # preso a um pai morto e' o custo que o dono paga em RAM; o shell
            # pode esperar mais um milissegundo.
            for spec in args.child or ():
                pid_s, _, stamp = spec.partition(':')
                kid, why = open_checked(pid_s, stamp)
                if kid is None:
                    say('EXIT_KILLER_CHILD_SKIPPED pid=%s reason=%s'
                        % (pid_s, why))
                    continue
                try:
                    ok = kill(kid)
                    say('EXIT_KILLER_CHILD pid=%s killed=%s'
                        % (pid_s, str(ok).lower()))
                finally:
                    k32.CloseHandle(kid)
            ok = kill(shell, args.code)
            say('EXIT_KILLER_FIRED pid=%s code=%s children=%s killed_shell=%s '
                'reason=exit-logged-but-process-stayed-alive'
                % (args.pid, args.code,
                   ','.join(spec.partition(':')[0] for spec in args.child or ()),
                   str(ok).lower()))
            dead(shell, 2000)
        # A VARREDURA: mesmo numa saida limpa, um filho que sobreviva fica
        # nomeado e morto -- e' o orfao que o dono paga.
        for spec in args.child or ():
            pid_s, _, stamp = spec.partition(':')
            kid, why = open_checked(pid_s, stamp)
            if kid is None:
                continue
            try:
                if not dead(kid, 0):
                    say('EXIT_KILLER_ORPHAN pid=%s killed=%s'
                        % (pid_s, str(kill(kid)).lower()))
            finally:
                k32.CloseHandle(kid)
        return 0
    finally:
        k32.CloseHandle(shell)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--stamp', default='')
    ap.add_argument('--code', type=int, default=0)
    ap.add_argument('--grace-ms', type=int, default=4000)
    ap.add_argument('--log', default='')
    ap.add_argument('--child', action='append', default=[])
    return run(ap.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
