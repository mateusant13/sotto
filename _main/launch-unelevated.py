#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# NO-BUG: ferramenta de largada (duplica o token do Explorer); o defeito que serve ainda nao tem id no ledger
"""LAUNCH-UNELEVATED -- lancar um comando com o token NAO ELEVADO do Explorer.

O PROBLEMA, MEDIDO 2026-10-23 nesta maquina, tres mecanismos e tres avarias:

  1. pane -> `schtasks /it`:  `TRAY_ICON_ADD ok=true` e `HOTKEY_REGISTERED`, e a app
     ficou **SURDA** -- o dono pressionou Alt+C e o log nao teve uma unica linha de
     hotkey.
  2. pane -> `Shell.Application.ShellExecute`: mutex ok, hotkey ok,
     `TRAY_ICON_ADD ok=false winerror=5` e
     `WEBVIEW2_INIT_FAILED 0x80010108 RPC_E_DISCONNECTED`.
  3. o dono a lancar: tudo verde.

A CAUSA, e nao e politica: **o WebView2 nao corre num processo elevado.** Esta pane
esta elevada (`IsInRole(Administrator) = True`), toda a crianca herda o token, e o
painel nunca desenha. Nenhuma flag do `sotto_webview.py` cura isto -- o token tem de
ser outro.

A CURA: `explorer.exe` e o processo do dono que corre **nao elevado** (integridade
media). Duplicar o token dele (`OpenProcessToken` + `DuplicateTokenEx`) e arrancar a
crianca com `CreateProcessWithTokenW` poe o processo na mesma integridade do desktop,
onde o WebView2 funciona. Se `CreateProcessWithTokenW` falhar por privilegio, cai para
`CreateProcessAsUserW` -- e diz qual usou.

NAO e um bypass de seguranca: o comando continua a correr como o MESMO utilizador
(Administrador), so com a integridade de quem esta a usar a maquina. E o equivalente a
o dono fazer duplo-clique.

    python _main\\launch-unelevated.py --selftest
    python _main\\launch-unelevated.py -- "<pythonw>" "<shell>" --log "<log>"

Codigos: 0 = lancado e o filho arrancou; 2 = falhou (diz onde); 1 = reservado para
`--neg-arm` por desenho.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)

MAXIMUM_ALLOWED = 0x02000000
TOKEN_DUPLICATE = 0x0002
TOKEN_ASSIGN_PRIMARY = 0x0001
TOKEN_QUERY = 0x0008
TOKEN_IMPERSONATE = 0x0004
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SecurityImpersonation = 2
TokenPrimary = 1
CREATE_UNICODE_ENVIRONMENT = 0x00000004
LOGON_WITH_PROFILE = 0x00000001


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ('cb', wt.DWORD), ('lpReserved', wt.LPWSTR), ('lpDesktop', wt.LPWSTR),
        ('lpTitle', wt.LPWSTR), ('dwX', wt.DWORD), ('dwY', wt.DWORD),
        ('dwXSize', wt.DWORD), ('dwYSize', wt.DWORD),
        ('dwXCountChars', wt.DWORD), ('dwYCountChars', wt.DWORD),
        ('dwFillAttribute', wt.DWORD), ('dwFlags', wt.DWORD),
        ('wShowWindow', wt.WORD), ('cbReserved2', wt.WORD),
        ('lpReserved2', ctypes.POINTER(ctypes.c_byte)),
        ('hStdInput', wt.HANDLE), ('hStdOutput', wt.HANDLE),
        ('hStdError', wt.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [('hProcess', wt.HANDLE), ('hThread', wt.HANDLE),
                ('dwProcessId', wt.DWORD), ('dwThreadId', wt.DWORD)]


advapi32.OpenProcessToken.argtypes = [wt.HANDLE, wt.DWORD,
                                      ctypes.POINTER(wt.HANDLE)]
advapi32.DuplicateTokenEx.argtypes = [wt.HANDLE, wt.DWORD, ctypes.c_void_p,
                                      ctypes.c_int, ctypes.c_int,
                                      ctypes.POINTER(wt.HANDLE)]
advapi32.CreateProcessWithTokenW.argtypes = [
    wt.HANDLE, wt.DWORD, wt.LPCWSTR, wt.LPWSTR, wt.DWORD, ctypes.c_void_p,
    wt.LPCWSTR, ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION)]
advapi32.CreateProcessAsUserW.argtypes = [
    wt.HANDLE, wt.LPCWSTR, wt.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
    wt.LPCWSTR, ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION)]


# ── INTEGRIDADE LIDA DO SID, NAO DO TEXTO ────────────────────────────────────
# A primeira versao deste selftest fazia grep ao `whoami /groups` e devolvia
# 'unknown' nesta maquina (o Windows do dono nao imprime "Mandatory Label" em
# ingles). Um instrumento que depende da lingua do SO mede o SO, nao o token.
# `TokenIntegrityLevel` (25) devolve um TOKEN_MANDATORY_LABEL cujo SID tem o
# nivel no ULTIMO sub-authority: 0x1000 low, 0x2000 medium, 0x3000 high.
TokenIntegrityLevel = 25
INTEGRITY_NAMES = {0x0000: 'untrusted', 0x1000: 'low', 0x2000: 'medium',
                   0x3000: 'high', 0x4000: 'system'}

advapi32.GetTokenInformation.argtypes = [wt.HANDLE, ctypes.c_int,
                                         ctypes.c_void_p, wt.DWORD,
                                         ctypes.POINTER(wt.DWORD)]
advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wt.DWORD]
advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wt.DWORD)
kernel32.GetCurrentProcess.restype = wt.HANDLE


def token_integrity(token):
    """('medium'|'high'|..., motivo) lido do SID do token."""
    size = wt.DWORD(0)
    advapi32.GetTokenInformation(token, TokenIntegrityLevel, None, 0,
                                 ctypes.byref(size))
    if not size.value:
        return 'unknown', 'err=%d' % ctypes.get_last_error()
    buf = ctypes.create_string_buffer(size.value)
    if not advapi32.GetTokenInformation(token, TokenIntegrityLevel, buf, size,
                                        ctypes.byref(size)):
        return 'unknown', 'err=%d' % ctypes.get_last_error()
    sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
    if not sid:
        return 'unknown', 'sid nulo'
    count = advapi32.GetSidSubAuthorityCount(sid)[0]
    if not count:
        return 'unknown', 'sem sub-authority'
    rid = advapi32.GetSidSubAuthority(sid, count - 1)[0]
    return INTEGRITY_NAMES.get(rid, '0x%x' % rid), ''


def self_integrity():
    tok = wt.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY,
                                     ctypes.byref(tok)):
        return 'unknown', 'err=%d' % ctypes.get_last_error()
    lvl, why = token_integrity(tok)
    kernel32.CloseHandle(tok)
    return lvl, why


def process_integrity(pid):
    """A integridade do TOKEN DE OUTRO PROCESSO -- e a prova ponta-a-ponta."""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return 'unknown', 'OpenProcess err=%d' % ctypes.get_last_error()
    tok = wt.HANDLE()
    if not advapi32.OpenProcessToken(h, TOKEN_QUERY, ctypes.byref(tok)):
        why = 'OpenProcessToken err=%d' % ctypes.get_last_error()
        kernel32.CloseHandle(h)
        return 'unknown', why
    lvl, why = token_integrity(tok)
    kernel32.CloseHandle(tok)
    kernel32.CloseHandle(h)
    return lvl, why


def explorer_pids():
    """Os `explorer.exe` da NOSSA sessao, do mais antigo para o mais novo."""
    try:
        import psutil
    except ImportError:
        return []
    out = []
    for p in psutil.process_iter(['pid', 'name', 'create_time', 'username']):
        try:
            if (p.info['name'] or '').lower() != 'explorer.exe':
                continue
        except Exception:  # noqa: BLE001
            continue
        out.append((p.info.get('create_time') or 0, p.info['pid']))
    out.sort()
    pids = [pid for _t, pid in out]
    if not pids:
        return []
    # A sessao do Explorer e a do desktop; se `psutil.Process(pid)` falhar, tenta
    # todos (o primeiro que abrir token e o que serve).
    return pids


def dup_explorer_token():
    """(handle, pid) do token primario do Explorer, ou (None, motivo)."""
    last = 'nenhum explorer.exe encontrado'
    for pid in explorer_pids():
        hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not hproc:
            last = 'OpenProcess falhou pid=%d err=%d' % (pid, ctypes.get_last_error())
            continue
        tok = wt.HANDLE()
        if not advapi32.OpenProcessToken(hproc, MAXIMUM_ALLOWED, ctypes.byref(tok)):
            last = 'OpenProcessToken falhou pid=%d err=%d' % (pid, ctypes.get_last_error())
            kernel32.CloseHandle(hproc)
            continue
        dup = wt.HANDLE()
        if not advapi32.DuplicateTokenEx(tok, MAXIMUM_ALLOWED, None,
                                         SecurityImpersonation, TokenPrimary,
                                         ctypes.byref(dup)):
            last = 'DuplicateTokenEx falhou pid=%d err=%d' % (pid, ctypes.get_last_error())
            kernel32.CloseHandle(tok)
            kernel32.CloseHandle(hproc)
            continue
        kernel32.CloseHandle(tok)
        kernel32.CloseHandle(hproc)
        return dup, pid
    return None, last


def launch(cmdline, cwd=None):
    """(ok, metodo, pid, erro) -- duplica o token do Explorer e arranca."""
    token, info = dup_explorer_token()
    if not token:
        return False, '-', 0, 'sem token do Explorer: %s' % info
    si = STARTUPINFO()
    si.cb = ctypes.sizeof(STARTUPINFO)
    pi = PROCESS_INFORMATION()
    cwd_v = ctypes.c_wchar_p(cwd) if cwd else None
    ok = advapi32.CreateProcessWithTokenW(
        token, LOGON_WITH_PROFILE, None, ctypes.c_wchar_p(cmdline),
        CREATE_UNICODE_ENVIRONMENT, None, cwd_v, ctypes.byref(si), ctypes.byref(pi))
    method = 'CreateProcessWithTokenW'
    if not ok:
        err = ctypes.get_last_error()
        ok = advapi32.CreateProcessAsUserW(
            token, None, ctypes.c_wchar_p(cmdline), None, None,
            CREATE_UNICODE_ENVIRONMENT, None, cwd_v, ctypes.byref(si),
            ctypes.byref(pi))
        method = 'CreateProcessAsUserW (fallback; WithTokenW err=%d)' % err
    if not ok:
        return False, method, 0, 'ambas falharam, err=%d' % ctypes.get_last_error()
    pid = pi.dwProcessId
    kernel32.CloseHandle(pi.hThread)
    kernel32.CloseHandle(pi.hProcess)
    kernel32.CloseHandle(token)
    return True, method, pid, ''


def _pythonw():
    exe = sys.executable
    cand = os.path.join(os.path.dirname(exe), 'pythonw.exe')
    return cand if os.path.exists(cand) else exe


def selftest():
    """Prova, por TOKEN e ponta-a-ponta, que o filho fica em integridade MEDIA.

    Tres factos, todos lidos do SID (nao do texto que o SO imprime):
      1. a integridade desta pane;
      2. a integridade do TOKEN que vou usar (duplicado do Explorer);
      3. a integridade do TOKEN do filho que esse token arrancou.
    O (3) e o unico que fecha a questao: prova que a crianca herdou o token
    duplicado, e nao o desta pane.
    """
    me, me_why = self_integrity()
    ready, info = dup_explorer_token()
    if not ready:
        print('pane=%s | SEM TOKEN do Explorer: %s' % (me, info))
        print('SOTTO-UNELEVATED SELFTEST FAIL')
        return 2
    dup, dup_why = token_integrity(ready)
    kernel32.CloseHandle(ready)
    cmdline = subprocess.list2cmdline(
        [_pythonw(), '-c', 'import time; time.sleep(10)'])
    ok, method, pid, err = launch(cmdline)
    print('pane=%s%s | token-explorer=%s%s | metodo=%s | pid=%s | %s' % (
        me, (' (%s)' % me_why) if me_why else '',
        dup, (' (%s)' % dup_why) if dup_why else '',
        method, pid, err or 'lancado'))
    if not ok:
        print('SOTTO-UNELEVATED SELFTEST FAIL')
        return 2
    child, why = 'unknown', 'nao abriu a tempo'
    for _ in range(40):
        child, why = process_integrity(pid)
        if child != 'unknown':
            break
        time.sleep(0.1)
    try:
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    except OSError:
        pass
    print('integralidade do filho = %s%s' % (child, (' (%s)' % why) if why else ''))

    # ── A INTEGRIDADE NAO CHEGA: UM FILHO PODE EXISTIR E NUNCA CORRER ────────
    # Medido 2026-10-23 nesta maquina: um filho `high` arrancado com o token do
    # Explorer ficou com **1 thread e 2 MB** e nunca escreveu uma linha -- a app
    # parecia "lancada" e nao executava codigo nenhum. Um selftest que so olha
    # para o token dava PASS a um processo que nunca acordou.
    proof = os.path.join(os.environ.get('TMPDIR') or r'I:\cc-tmp', 'unelev-proof.txt')
    try:
        os.remove(proof)
    except OSError:
        pass
    code = "open(r'%s','w').write('ran')" % proof
    ok2, _m2, pid2, _e2 = launch(
        subprocess.list2cmdline([_pythonw(), '-c', code]))
    ran = False
    for _ in range(60):
        time.sleep(0.2)
        if os.path.exists(proof):
            ran = True
            break
    if pid2:
        try:
            subprocess.run(['taskkill', '/PID', str(pid2), '/F'], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
        except OSError:
            pass
    print('o filho EXECUTOU codigo = %s' % ran)
    ok_all = child == dup and ran
    print('SOTTO-UNELEVATED SELFTEST %s%s' % (
        'PASS' if ok_all else 'FAIL',
        '' if ok_all else ' (este token nao serve nesta maquina)'))
    return 0 if ok_all else 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--cwd', default=None)
    ap.add_argument('cmd', nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    if args.selftest:
        return selftest()
    cmd = [c for c in args.cmd if c != '--']
    if not cmd:
        print('falta o comando: -- "<exe>" <args...>')
        return 2
    cmdline = subprocess.list2cmdline(cmd)
    ok, method, pid, err = launch(cmdline, args.cwd)
    print('metodo=%s pid=%s %s' % (method, pid, err or 'lancado'))
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
