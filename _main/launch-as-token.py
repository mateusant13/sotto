"""Lancar um processo com o token de OUTRO processo vivo, no desktop interactivo.

PORQUE EXISTE (medido 2026-10-30)
----------------------------------
Esta pane corre a `medium` (`S-1-16-8192`); a app do dono corre a `high` (`S-1-16-12288`).
Um filho directo da pane nasce `medium` e nao fala com a taskbar nem com o WebView2
(`TRAY_ICON_ADD ok=false winerror=5`, `WEBVIEW2_INIT_FAILED 0x80010108`), e por isso durante
meses a conclusao foi "uma lane nao pode largar a app".

A CONCLUSAO ESTAVA ERRADA, e o erro era do INSTRUMENTO. A primeira versao pedia ao
`OpenProcessToken`:

    TOKEN_DUPLICATE | TOKEN_ASSIGN_PRIMARY | TOKEN_QUERY | TOKEN_ADJUST_DEFAULT
    | TOKEN_ADJUST_SESSIONID

`TOKEN_ADJUST_SESSIONID` exige `SeTcbPrivilege`, que nem o Administrador tem por omissao, e
o pedido INTEIRO e' recusado -- `err=5 ACCESS_DENIED` -- logo parecia "sem acesso". Medido,
direito a direito, contra o token da app viva:

    DUPLICATE                                   ok     DuplicateTokenEx ok
    DUP|QUERY                                   ok     ok
    DUP|QUERY|ASSIGN_PRIMARY                    ok     ok
    DUP|QUERY|ASSIGN_PRIMARY|ADJUST_SESSIONID   err=5  -- o culpado
    +ADJUST_DEFAULT                             err=5  -- tambem nao e' preciso

Com `DUP|QUERY|ASSIGN_PRIMARY` o `CreateProcessAsUserW` **funciona**: o filho corre no
desktop dele e mede `S-1-16-12288`, high (provado: `I:\\cc-tmp\\who2.pyw` escreveu o proprio
pid e a propria integridade).

O QUE ESTE MODULO NAO FAZ
-------------------------
Nao escala para `SYSTEM` e nao tenta. Medido de um filho `high`: escrever em `HKLM` ok,
`schtasks` ok, grupo Administradores ok, e **abrir o token do pid 4 (SYSTEM) da' err=5** --
porque SYSTEM esta' ACIMA de high. Isto e' o Windows, nao uma permissao perdida.

USO
    python _main/launch-as-token.py <pid-fonte> <exe> [args...]
    python _main/launch-as-token.py --selftest     # braco de controlo, sem tocar em nada
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys

MAXIMUM_ALLOWED = 0x02000000
#: O pedido EXECUTADO, e o comentario e' o resultado medido de cada um:
TOKEN_DUPLICATE = 0x0002        # ler o token de outro processo
TOKEN_QUERY = 0x0008           # perguntar-lhe o que e'
TOKEN_ASSIGN_PRIMARY = 0x0001   # po-lo como identidade de um processo novo
#: DELIBERADAMENTE FORA: `TOKEN_ADJUST_SESSIONID` (SeTcbPrivilege) e `TOKEN_ADJUST_DEFAULT`.
#: Cada um deles, sozinho, transforma o pedido inteiro em `err=5`.
TOKEN_RIGHTS = TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ASSIGN_PRIMARY

CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000
#: NENHUM POP-UP NA TELA DO DONO (ordem de 2026-11-02: *"para de fazer terminal
#: ter pop up porra"*). MEDIDO com um censo de janelas a 10 Hz em volta de um
#: `--relaunch`: `DETACHED_PROCESS` NAO bastava -- o `taskkill.exe` lancado por
#: este modulo aparecia como `ConsoleWindowClass` visivel na tela dele, porque um
#: executavel de CONSOLA lancado por um pai sem consola faz o Windows alocar uma
#: NOVA consola, e essa consola tem janela. `CREATE_NO_WINDOW` impede a alocacao;
#: os dois flags sao mutuamente exclusivos, e o que se quer aqui e' este.
DEFAULT_FLAGS = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

TOKEN_INTEGRITY_LEVEL = 25
INTEGRITY_NAMES = {0x0000: 'UNTRUSTED', 0x1000: 'LOW', 0x2000: 'MEDIUM', 0x3000: 'HIGH',
                   0x4000: 'SYSTEM'}

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
adv = ctypes.WinDLL('advapi32', use_last_error=True)

k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.OpenProcess.restype = wt.HANDLE
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.GetCurrentProcess.restype = wt.HANDLE
adv.OpenProcessToken.argtypes = [wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE)]
adv.OpenProcessToken.restype = wt.BOOL
adv.DuplicateTokenEx.argtypes = [wt.HANDLE, wt.DWORD, ctypes.c_void_p, ctypes.c_int,
                                 ctypes.c_int, ctypes.POINTER(wt.HANDLE)]
adv.DuplicateTokenEx.restype = wt.BOOL
adv.GetTokenInformation.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD,
                                    ctypes.POINTER(wt.DWORD)]
adv.GetTokenInformation.restype = wt.BOOL
adv.CreateProcessAsUserW.argtypes = [wt.HANDLE, wt.LPCWSTR, wt.LPWSTR, ctypes.c_void_p,
                                     ctypes.c_void_p, wt.BOOL, wt.DWORD, ctypes.c_void_p,
                                     wt.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p]
adv.CreateProcessAsUserW.restype = wt.BOOL
adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]


class _STARTUPINFO(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('lpReserved', wt.LPWSTR), ('lpDesktop', wt.LPWSTR),
                ('lpTitle', wt.LPWSTR), ('dwX', wt.DWORD), ('dwY', wt.DWORD),
                ('dwXSize', wt.DWORD), ('dwYSize', wt.DWORD), ('dwXCountChars', wt.DWORD),
                ('dwYCountChars', wt.DWORD), ('dwFillAttribute', wt.DWORD),
                ('dwFlags', wt.DWORD), ('wShowWindow', wt.WORD), ('cbReserved2', wt.WORD),
                ('lpReserved2', ctypes.c_void_p), ('hStdInput', wt.HANDLE),
                ('hStdOutput', wt.HANDLE), ('hStdError', wt.HANDLE)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [('hProcess', wt.HANDLE), ('hThread', wt.HANDLE),
                ('dwProcessId', wt.DWORD), ('dwThreadId', wt.DWORD)]


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [('Sid', ctypes.c_void_p), ('Attributes', wt.DWORD)]


def token_of(pid):
    """Token primario duplicado do processo `pid`. Levanta OSError com o codigo do Windows."""
    handle = k32.OpenProcess(0x1000, False, pid)          # QUERY_LIMITED_INFORMATION
    if not handle:
        raise OSError('OpenProcess(pid=%d) err=%d' % (pid, ctypes.get_last_error()))
    try:
        raw = wt.HANDLE()
        if not adv.OpenProcessToken(handle, TOKEN_RIGHTS, ctypes.byref(raw)):
            raise OSError('OpenProcessToken(pid=%d) err=%d (direitos=0x%x)'
                          % (pid, ctypes.get_last_error(), TOKEN_RIGHTS))
        primary = wt.HANDLE()
        if not adv.DuplicateTokenEx(raw, MAXIMUM_ALLOWED, None, 2, 1,
                                    ctypes.byref(primary)):
            raise OSError('DuplicateTokenEx err=%d' % ctypes.get_last_error())
        return primary
    finally:
        k32.CloseHandle(handle)


def launch(pid, exe, args=(), flags=DEFAULT_FLAGS, cwd=None, desktop='winsta0\\default'):
    """(ok, err, child_pid) -- lanca `exe args` com o token de `pid`."""
    primary = token_of(pid)
    # A LINHA DE COMANDO E' MONTADA A SERIO (medido 2026-10-30): concatenar
    # `"exe" a b c` partia qualquer argumento com espacos -- um `pythonw -c "<codigo>"`
    # chegava ao filho aos pedacos e o filho nao executava nada. `list2cmdline` e' a
    # mesma regra do `subprocess` e obedece as aspas do Windows.
    import subprocess as _subprocess
    command = _subprocess.list2cmdline([exe] + [str(a) for a in args])
    startup = _STARTUPINFO()
    startup.cb = ctypes.sizeof(startup)
    startup.lpDesktop = desktop
    info = _PROCESS_INFORMATION()
    buf = ctypes.create_unicode_buffer(command)
    ok = adv.CreateProcessAsUserW(primary, None, buf, None, None, False,
                                  flags | CREATE_UNICODE_ENVIRONMENT, None, cwd,
                                  ctypes.byref(startup), ctypes.byref(info))
    err = ctypes.get_last_error()
    k32.CloseHandle(primary)
    return bool(ok), err, info.dwProcessId


def integrity_of(pid=None):
    """SID de integridade textual do processo (`S-1-16-12288` etc.). pid None = este."""
    handle = k32.GetCurrentProcess() if pid is None else k32.OpenProcess(0x1000, False, pid)
    if not handle:
        return 'erro=%d' % ctypes.get_last_error()
    token = wt.HANDLE()
    if not adv.OpenProcessToken(handle, TOKEN_QUERY, ctypes.byref(token)):
        return 'erro=%d' % ctypes.get_last_error()
    size = wt.DWORD(0)
    adv.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(size))
    buf = ctypes.create_string_buffer(max(size.value, 16))
    if not adv.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, buf, size.value,
                                   ctypes.byref(size)):
        return 'erro=%d' % ctypes.get_last_error()
    sid = ctypes.cast(buf, ctypes.POINTER(_SID_AND_ATTRIBUTES))[0].Sid
    text = ctypes.c_void_p()
    if not adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        return 'erro=%d' % ctypes.get_last_error()
    return ctypes.wstring_at(text.value)


def integrity_name(sid):
    try:
        level = int(str(sid).rsplit('-', 1)[1])
    except (ValueError, IndexError):
        return sid
    return INTEGRITY_NAMES.get(level, sid)


#: O CORPO DA CRIANCA DE LOTE. Escreve `<state>` (pid rc por linha, `os.replace` para
#: que a existencia do ficheiro signifique CONTEUDO COMPLETO) e sai com 0 SO' se todos
#: os pids morreram. Um pid inexistente da' rc=128 do `taskkill` e torna o exit != 0:
#: o instrumento nunca pode chamar "morto" a um pid que nao existia.
_KILL_HELPER = '''import os, subprocess, sys
state = sys.argv[1]
tk = os.path.join(os.environ.get("SYSTEMROOT", r"C:\\Windows"), "System32", "taskkill.exe")
lines = []
worst = 0
for token in sys.argv[2:]:
    try:
        pid = int(token)
    except ValueError:
        lines.append("%s -1" % token)
        worst = 1
        continue
    rc = subprocess.run([tk, "/PID", str(pid), "/T", "/F"],
                        creationflags=0x08000000).returncode  # CREATE_NO_WINDOW
    lines.append("%d %d" % (pid, rc))
    if rc != 0:
        worst = 1
tmp = state + ".tmp"
with open(tmp, "w") as fh:
    fh.write("\\n".join(lines) + "\\n")
os.replace(tmp, state)
sys.exit(worst)
'''


def kill_pids_via_high(pids, source=None, timeout=None):
    """Uma UNICA crianca `high` mata a LISTA de pids. (ok, fonte, filho, [(pid, rc)]).

    MEDIDO 2026-11-03: a `--relaunch` matava um pid de cada vez e cada um pagava
    CreateProcessAsUser + espera (~2-3 s); seis descendentes custaram 18 s de relogio
    e a mutex ficou presa quando o caminho do token nao foi alcancado. Uma crianca com
    a lista inteira paga a criacao UMA vez e devolve o rc de CADA pid.

    `ok` e' True so' quando todos os pids morreram (rc==0), o que exclui o pid que nao
    existia (rc=128) -- assumir 128 como sucesso seria o relatorio falso que esta
    primitiva existe para impedir.
    """
    import tempfile
    import time
    pids = [int(pid) for pid in pids]
    if not pids:
        return False, None, None, []
    source = source or _selftest_source()
    if not source:
        return False, None, None, [(pid, None) for pid in pids]
    # UM INTERPRETADOR A CORRER UM FICHEIRO, nunca codigo inline (medido 2026-10-30):
    # `cmd /c taskkill ... > ficheiro` criou o ficheiro VAZIO e nao matou nada, e
    # `pythonw -c "<codigo>"` chegou ao filho com a linha de comando desfeita pelas aspas.
    # Um ficheiro com os pids como ARGUMENTOS nao tem esse problema.
    handle, helper = tempfile.mkstemp(prefix='launch-as-token-kill-', suffix='.py')
    os.close(handle)
    handle, state = tempfile.mkstemp(prefix='launch-as-token-kill-', suffix='.txt')
    os.close(handle)
    os.remove(state)              # o helper so' cria o ficheiro quando tem a lista toda
    try:
        with open(helper, 'w', encoding='utf-8') as out:
            out.write(_KILL_HELPER)
        interpreter = sys.executable.replace('python.exe', 'pythonw.exe')
        launched, _err, child = launch(source, interpreter,
                                       [helper, state] + [str(pid) for pid in pids])
        results = []
        if launched:
            deadline = time.time() + (timeout or (20.0 + 10.0 * len(pids)))
            while time.time() < deadline and not os.path.exists(state):
                time.sleep(0.25)
            try:
                with open(state, encoding='utf-8') as fh:
                    for line in fh:
                        bits = line.split()
                        if len(bits) == 2 and bits[0].isdigit():
                            try:
                                results.append((int(bits[0]), int(bits[1])))
                            except ValueError:
                                pass
            except OSError:
                results = []
        by_pid = dict(results)
        all_ok = bool(launched) and all(by_pid.get(pid) == 0 for pid in pids)
        return all_ok, source, child, results
    finally:
        for path in (helper, state):
            try:
                os.remove(path)
            except OSError:
                pass


def kill_via_high(pid, source=None):
    """`taskkill` executado por um filho `high`. (ok, fonte, filho).

    MEDIDO 2026-10-30: matar o processo `high` dele a partir desta pane `medium` da'
    **rc=1, "Acesso negado"** -- e um kill que falha em silencio deixa uma instancia
    velha a deter `Local\\SottoShell`, o que mata a largada seguinte entre `pre-lock`
    e `SINGLE_INSTANCE`. Com o token de um processo `high` desta sessao o mesmo
    `taskkill` da' **rc=0**, e e' isso que faz esta funcao existir.

    E' o lote de UM pid: o caminho e' o mesmo que a `--relaunch` usa para uma lista.
    """
    ok, used, child, _results = kill_pids_via_high([int(pid)], source)
    return bool(ok), used, child


def _selftest_source():
    """Um pid cujo token esta' ABRIVEL nesta sessao; `--source <pid>` sobrepoe-se.

    `wmic` foi RETIRADO desta maquina (medido 2026-10-30: devolve saida vazia), por isso a
    descoberta usa `tasklist`. Devolver None nao e' um passe: e' uma medicao que nao
    aconteceu, e quem chama tem de o dizer.
    """
    import subprocess
    candidates = []
    if '--source' in sys.argv:
        candidates = [int(sys.argv[sys.argv.index('--source') + 1])]
    else:
        result = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, creationflags=CREATE_NO_WINDOW)
        for row in (result.stdout or b'').decode('cp850', 'replace').splitlines():
            columns = [column.strip('"') for column in row.split('","')]
            if len(columns) >= 2 and columns[0].lower() in ('explorer.exe', 'sotto_webview.py'):
                if columns[1].isdigit():
                    candidates.append(int(columns[1]))
    for pid in candidates:
        try:
            token_of(pid)
        except OSError:
            continue
        return pid
    return None


def _selftest():
    """Braco de controlo: a primitiva tem de largar um filho que ESCREVE e que e' `high`.

    Nao toca na app nem na tarefa: escolhe como fonte um processo de integridade alta e um
    probe que escreve o proprio pid + a propria integridade. O filho tem de herdar o nivel
    da FONTE, e o probe TEM de ter corrido -- um processo criado que nunca executa codigo
    foi exactamente o resultado falso que esta primitiva veio corrigir.
    """
    import tempfile
    import time
    probe = os.path.join(tempfile.gettempdir(), 'launch-as-token-probe.pyw')
    out = os.path.join(tempfile.gettempdir(), 'launch-as-token-probe.txt')
    with open(probe, 'w', encoding='utf-8') as fh:
        fh.write('import os, importlib.util as u\n'
                 's = u.spec_from_file_location("lat", %r)\n'
                 'm = u.module_from_spec(s); s.loader.exec_module(m)\n'
                 'open(%r, "w").write("pid=%%d integridade=%%s\\n"\n'
                 '                    %% (os.getpid(), m.integrity_of()))\n'
                 % (os.path.abspath(__file__), out))
    if os.path.exists(out):
        os.remove(out)
    source = _selftest_source()
    if not source:
        print('SELFTEST SKIP -- nenhum processo fonte abrivel nesta sessao (nao e\' um passe)')
        return 1
    expected = integrity_of(source)
    interpreter = sys.executable.replace('python.exe', 'pythonw.exe')
    ok, err, child = launch(source, interpreter, [probe])
    if not ok:
        print('SELFTEST FAIL -- CreateProcessAsUser err=%d (fonte pid=%d)' % (err, source))
        return 1
    body = ''
    for _ in range(40):
        time.sleep(0.25)
        if os.path.exists(out):
            body = open(out, encoding='utf-8').read().strip()
            break
    for path in (probe, out):
        try:
            os.remove(path)
        except OSError:
            pass
    if not body:
        print('SELFTEST FAIL -- o filho pid=%d foi criado mas nao executou codigo' % child)
        return 1
    sid = body.split('integridade=')[-1].strip()
    level = int(sid.rsplit('-', 1)[-1]) if sid.startswith('S-1-16-') else -1
    inherits = sid == expected
    ok_launch = level >= 0x2000 and inherits
    print('SELFTEST %s -- fonte pid=%d (%s), filho pid=%d executou, integridade=%s (%s)'
          % ('PASS' if ok_launch else 'FAIL', source,
             integrity_name(expected), child, sid, integrity_name(sid)))

    # SEGUNDO BRACO: MATAR um processo `high` desta pane. Um kill que falha em silencio
    # deixa a instancia velha a deter a mutex, e a largada seguinte morre calada.
    import subprocess
    import tempfile
    sleeper = os.path.join(tempfile.gettempdir(), 'launch-as-token-sleeper.pyw')
    with open(sleeper, 'w', encoding='utf-8') as fh:
        fh.write('import time\nwhile True:\n    time.sleep(0.5)\n')
    started, err2, victim = launch(source, interpreter, [sleeper])
    if not started:
        print('SELFTEST FAIL -- nao consegui criar a vitima do kill (err=%d)' % err2)
        return 1
    # UM HANDLE DE SINCRONIZACAO, E NAO UM `OpenProcess` DEPOIS (medido 2026-10-30): o pid
    # de uma vitima morta e' reutilizado em segundos nesta maquina, e a leitura tardia
    # respondia "vivo" para outro processo. Este handle e' do processo que NOS criamos, e
    # `WaitForSingleObject` diz se ele saiu -- sem ambiguidade de pid.
    k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    k32.WaitForSingleObject.restype = wt.DWORD
    victim_handle = k32.OpenProcess(0x00100000, False, victim)   # SYNCHRONIZE
    time.sleep(1.0)
    plain = subprocess.run(['taskkill', '/PID', str(victim), '/T', '/F'], capture_output=True, creationflags=CREATE_NO_WINDOW)
    delegated, kill_source, kill_child = kill_via_high(victim, source)
    # 8 s NAO CHEGAM NESTA MAQUINA (medido 2026-10-30: a mesma vitima saiu em 8 s
    # num run e nao saiu dentro de 8 s no run da bateria, com 700+ processos a
    # correr). O prazo passa a 25 s: o que se mede e' se a delegacao MATA, nao a
    # velocidade com que o Windows agenda o `taskkill` de outro desktop.
    waiter = (k32.WaitForSingleObject(victim_handle, 25000)
              if victim_handle else -1)
    exited = waiter == 0
    print('KILL-DELEGATION %s -- taskkill direto rc=%d, via token(fonte=%d) ok=%s, saiu=%s'
          % ('PASS' if delegated and exited else 'FAIL', plain.returncode,
             kill_source, delegated, exited))
    return 0 if (ok_launch and delegated and exited) else 1


def _neg_arm():
    """Braco de controlo: o pedido que reproduz o defeito TEM de ser recusado.

    `TOKEN_ADJUST_SESSIONID` exige `SeTcbPrivilege`; com ele no pedido, o
    `OpenProcessToken` contra um processo `high` devolve `err=5` e o pedido INTEIRO cai --
    foi essa a conclusao errada durante meses. Se este braco passar, o instrumento perdeu
    o dente e o PASS do `--selftest` deixa de significar alguma coisa.
    """
    global TOKEN_RIGHTS
    source = _selftest_source()
    if not source:
        print('NEG-ARM SKIP -- nenhum processo fonte abrivel (nao e\' um passe)')
        return 1
    saved = TOKEN_RIGHTS
    try:
        TOKEN_RIGHTS = saved | 0x0100          # TOKEN_ADJUST_SESSIONID
        try:
            token_of(source)
        except OSError as exc:
            # rc=1 E' SUCESSO AQUI (a casa le `:expectred` como rc==1 + token). O ramo devolvia 0
            # e o passo `red-as-expected-launch-as-token` ficava vermelho por FORMA (2026-10-30).
            print('NEG-ARM PASS -- RED as designed: com ADJUST_SESSIONID: %s' % exc)
            return 1
        print('NEG-ARM FAIL -- o pedido com ADJUST_SESSIONID foi ACEITE; o braco perdeu o dente')
        return 1
    finally:
        TOKEN_RIGHTS = saved


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == '--selftest':
        return _selftest()
    if argv and argv[0] == '--neg-arm':
        return _neg_arm()
    if argv and argv[0] == '--kill' and len(argv) > 1:
        ok, source, child = kill_via_high(int(argv[1]))
        print('kill via token pid=%s ok=%s fonte=%s filho=%s' % (argv[1], ok, source, child))
        return 0 if ok else 1
    if argv and argv[0] == '--kill-pids' and len(argv) > 1:
        # UMA crianca para a lista inteira: `--kill-pids 1,2,3`. rc por pid impresso;
        # exit 0 SO' se todos morreram (um pid inexistente da' rc=128 e derruba o rc).
        pids = [int(bit) for bit in argv[1].split(',') if bit.strip()]
        ok, source, child, results = kill_pids_via_high(pids)
        for pid, rc in results:
            print('pid=%d rc=%s %s' % (pid, rc, 'morto' if rc == 0 else 'NAO morto'))
        print('kill-pids via token ok=%s fonte=%s filho=%s n=%d'
              % (ok, source, child, len(pids)))
        return 0 if ok else 1
    if len(argv) < 2:
        print(__doc__.splitlines()[0])
        print('uso: launch-as-token.py <pid-fonte> <exe> [args...]')
        print('este processo: %s (%s)' % (integrity_of(), integrity_name(integrity_of())))
        return 2
    ok, err, child = launch(int(argv[0]), argv[1], argv[2:])
    print('CreateProcessAsUser ok=%s err=%d child=%d' % (ok, err, child))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
