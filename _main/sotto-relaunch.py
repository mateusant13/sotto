"""Relaunch Sotto IN THE OWNER'S OWN SESSION, with no action and no approval from him.

WHY THIS FILE EXISTS (medido 2026-10-30, cinco caminhos)
--------------------------------------------------------
The panel this lane runs from is `medium`; the owner's desktop is `high`. Every path
that tries to start the app from HERE was measured, with a control arm that passes so
the failure is not a bug of the probe:

  1. a CHILD of this pane ................. starts `medium`; `TRAY_ICON_ADD ok=false
     winerror=5` and `WEBVIEW2_INIT_FAILED 0x80010108` (medido 2026-10-23, ainda vale:
     `hotkey-delivery` falha hoje com winerror=1409 porque a instancia DELE tem a tecla)
  2. `explorer.exe <ficheiro>` ............ NAO EXECUTA (0/3, 2026-10-30)
  3. token emprestado do Explorer ......... filho `high` mas nunca executa (2026-10-23)
  4. `CreateProcessAsUser` com o token do shell vivo .... **FUNCIONA** (refeito
     2026-10-30). O `err=5` que aqui estava era o pedido, nao o Windows: a primitiva pedia
     `TOKEN_ADJUST_SESSIONID` (SeTcbPrivilege) e `TOKEN_ADJUST_DEFAULT`, e cada um deles
     sozinho derruba o pedido INTEIRO. Com `DUPLICATE|QUERY|ASSIGN_PRIMARY` o filho corre
     no desktop dele e mede `S-1-16-12288` high -- provado pelo `--selftest` de
     `_main/launch-as-token.py` (SELFTEST PASS, filho executou codigo, HIGH).
  5. `schtasks /run /tn Sotto` ............ EXECUTA, `high`, na sessao dele (a tarefa
     `\Sotto` ja abriu a app a 2026-10-29 20:53 e a 2026-10-30 01:12)

So there are TWO launchers that work, and the order is now:

  * the live instance's own token (path 4, corrected) -- no task, no approval, and the
    child is `high` in his session. Used whenever an instance is alive to borrow from.
  * `schtasks /run /tn Sotto` (path 5) -- the fallback, and the ONLY option when the app
    is dead, because then there is no high token in this session to borrow.

WHAT THIS SCRIPT DOES (the order matters)
-----------------------------------------
Kill first, launch second. The app holds `Local\\SottoShell`; a second instance dies
SILENTLY between `SHELL_STARTUP_STAGE stage=pre-lock` and `SINGLE_INSTANCE` (medido nesta
sessao: pid 37072, zero stderr, porque `run.cmd` usa pythonw). So "start the new one and
let the old one exit" is not available: the old one has to go first, and only then is the
launcher's child health-checked.

IDENTITY, NEVER A NAME
----------------------
The pid is taken from the app's OWN log (`SHELL_STARTUP_STAGE ... already_running=false`
is the last line of a launch that actually WON the mutex) and confirmed alive. A process's
`CommandLine` on this box comes back EMPTY for foreign processes, so a name filter is what
killed two innocent processes once (AGENTS.md); this file never filters by name.

USAGE
    python _main/sotto-relaunch.py --check      # does not touch anything; prints the verdict
    python _main/sotto-relaunch.py --relaunch   # kill + launch + verify (the task action)
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, '_main', 'webview-run.log')
RELAUNCH_LOG = os.path.join(ROOT, '_main', 'shell-relaunch.log')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
MUTEX = 'Local\\SottoShell'
TASK = 'Sotto'

#: How long the successor is given to prove itself in the log. The app's own startup
#: (WebView2 + model preload) takes seconds on this degraded box (53-127 ms per start
#: measured, plus the worker spawn), so 90 s is a wall clock, not a guess tuned to pass.
READY_TIMEOUT_S = 90.0
#: The mutex must be free before the successor starts; the OS frees it when the owner dies,
#: but the worker teardown can lag by a moment.
MUTEX_WAIT_S = 20.0
POLL_S = 0.25

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.GetProcessTimes.restype = wt.BOOL
k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
k32.CreateMutexW.restype = wt.HANDLE
k32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
ERROR_ALREADY_EXISTS = 183


def w(msg):
    line = '%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    try:
        with open(RELAUNCH_LOG, 'a', encoding='utf-8') as fh:
            fh.write(line)
    except OSError:
        pass
    print(line.rstrip())


#: NENHUM POP-UP DE CONSOLA NA TELA DO DONO (ordem de 2026-11-02, verbatim:
#: *"para de fazer terminal ter pop up porra"*). MEDIDO com um censo de janelas
#: a 10 Hz durante um `--relaunch`: apareceram DOIS `ConsoleWindowClass` -- um
#: de `taskkill.exe` (utilitario de consola: uma pai sem consola faz o Windows
#: alocar uma NOVA, visivel) e um de `cmd.exe` do proprio `run.cmd`. O flag
#: `CREATE_NO_WINDOW` e' o que impede a alocacao em cada largada.
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW

def log_text():
    try:
        with open(LOG, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def live_shell_pid(text=None):
    """The pid of the instance that WON the mutex, or None.

    `already_running=false` is the only line that proves an instance owns the shell: a
    launch that lost the mutex logs nothing after `pre-lock` (measured), so it can never
    be mistaken for the live one.
    """
    text = log_text() if text is None else text
    won = re.findall(r'SHELL_STARTUP_STAGE pid=(\d+) stage=pre-lock[^\n]*\n(?:\d{4}-[^\n]*\n){0,3}'
                     r'[^\n]*SINGLE_INSTANCE[^\n]*already_running=false', text)
    if not won:
        won = re.findall(r'SHELL_STARTUP_STAGE pid=(\d+)[^\n]*\n(?:\d{4}-[^\n]*\n){0,3}'
                         r'[^\n]*SINGLE_INSTANCE[^\n]*already_running=false', text)
    for pid in reversed(won):
        pid = int(pid)
        if pid == os.getpid():
            continue
        if alive(pid) and created_near(pid, _stamp_before_pid(text, pid)):
            return pid
    return None


def _stamp_before_pid(text, pid):
    """The log time of the `SHELL_STARTUP_STAGE pid=<pid>` line, as epoch seconds."""
    rx = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+) sotto: SHELL_STARTUP_STAGE pid=%d\b'
                    % pid, re.M)
    found = None
    for m in rx.finditer(text):
        found = m.group(1)
    if not found:
        return None
    try:
        return time.mktime(time.strptime(found[:19], '%Y-%m-%d %H:%M:%S'))
    except ValueError:
        return None


def created_near(pid, when, tolerance_s=300.0):
    """Is `pid` the process that wrote that log line, or a REUSED pid?

    PORQUE EXISTE (medido 2026-11-01). `--check` respondeu `instancia viva : 43304`
    com `mutex livre : True` -- duas respostas que se contradizem. O pid vinha do
    log (o ultimo arranque que GANHOU a mutex, 09:51:35) e estava mesmo vivo: era um
    `chrome.exe --type=crashpad-handler` nascido as 10:02, onze minutos depois. O
    Windows reutiliza pids, e `alive()` sozinho responde a pergunta errada. Nada de
    nome nem de `CommandLine` (que vem VAZIO para processos alheios, e por isso um
    filtro de nome ja matou dois processos inocentes): a identidade prova-se pela
    HORA DE CRIACAO do processo, que `GetProcessTimes` da' com o direito
    `PROCESS_QUERY_LIMITED_INFORMATION` que `alive()` ja abre.
    """
    if when is None:
        return False
    handle = k32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        created = wt.FILETIME()
        exit_t = wt.FILETIME()
        kern = wt.FILETIME()
        user = wt.FILETIME()
        if not k32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exit_t),
                                   ctypes.byref(kern), ctypes.byref(user)):
            return False
        ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
        epoch = ticks / 1e7 - 11644473600.0
        return abs(epoch - when) <= tolerance_s
    finally:
        k32.CloseHandle(handle)


def alive(pid):
    handle = k32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = wt.DWORD()
        if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == 259  # STILL_ACTIVE
    finally:
        k32.CloseHandle(handle)


def mutex_free():
    handle = k32.CreateMutexW(None, False, MUTEX)
    if not handle:
        return False
    try:
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS
    finally:
        k32.CloseHandle(handle)


#: O QUE A APP LARGA E QUE SOBREVIVE A ELA. MEDIDO 2026-11-03 03:32: o
#: `taskkill /PID <app> /T /F` devolveu rc=0, a app morreu, e QUATRO
#: `msedgewebview2.exe` filhos dela (pids 47376/17224/43896/50940) continuaram
#: vivos a deter `Local\\SottoShell`: `--check` dizia `instancia viva: NENHUMA`
#: e `mutex livre: False`, e todas as largadas seguintes abortavam em 20 s. Matar
#: esses quatro libertou a mutex na hora. Identidade: o PID do filho + o NOME +
#: `ParentProcessId` == o pid da app (nunca um filtro por palavra).
LITTER_NAMES = ('msedgewebview2.exe', 'python.exe', 'pythonw.exe', 'cmd.exe')


def _children_of(pids):
    """[(pid, nome, ppid)] de todos os processos, para achar a descendencia."""
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-CimInstance Win32_Process | ForEach-Object { "$($_.ProcessId)|$($_.Name)|$($_.ParentProcessId)" }'],
            capture_output=True, text=True, creationflags=NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0), timeout=40)
    except Exception:                     # noqa: BLE001
        return []
    rows = []
    for line in (out.stdout or '').splitlines():
        bits = line.strip().split('|')
        if len(bits) != 3:
            continue
        try:
            rows.append((int(bits[0]), bits[1].lower(), int(bits[2])))
        except ValueError:
            continue
    return rows


def _kill_targets(root_pid, snapshot):
    """O pid que ganhou a mutex + os descendentes que a app larga (que sobrevivem a ela).

    A identidade e' o PID + o NOME + `ParentProcessId` == um pid ja' na lista (nunca um
    filtro por palavra), a mesma de 2026-11-03.
    """
    want = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, _name, ppid in snapshot:
            if ppid in want and pid not in want:
                want.add(pid)
                changed = True
    targets = [root_pid]
    for pid, name, _ppid in snapshot:
        if pid != root_pid and pid in want and name in LITTER_NAMES:
            targets.append(pid)
    return targets


def _live_pids(pids):
    """O subconjunto de `pids` que AINDA existe, por CENSO (Get-CimInstance).

    NAO usa `alive()` (2026-11-03): `alive()` faz `OpenProcess` e um alvo `high` recusa
    essa abertura a partir desta pane `medium` com err=5 -- o filtro declarava "morto"
    exactamente o processo que era preciso matar, e a varredura nao matava nada. O censo
    de processos nao pede acesso a cada processo, por isso ve' os dois niveis.
    """
    present = {pid for pid, _name, _ppid in _children_of([])}
    return [pid for pid in pids if pid in present]


def kill(pid, source=None):
    """Mata pelo PID que ganhou a mutex -- e, se este processo for `medium`, delega.

    MEDIDO 2026-10-30: `taskkill /PID <app>` chamado de uma pane `medium` contra o
    processo `high` dele devolve **rc=1, "Acesso negado"**, e quem nao olhasse o rc
    acharia que matou. A partir do filho `high` (token emprestado) o mesmo `taskkill`
    da' **rc=0**. Um kill que falha em silencio e' pior do que nenhum: a instancia
    antiga continua a deter `Local\\SottoShell` e a largada seguinte morre entre
    `pre-lock` e `SINGLE_INSTANCE`.

    MEDIDO 2026-11-03: um filho de token POR PID custava 18 s para seis descendentes e
    a `--relaunch` abortava com "a instancia antiga nao morreu" quando o caminho do
    token nao era alcancado. Agora o censo e' tirado ANTES da morte, a tentativa
    directa e' barata (binario nativo), e o caminho do token e' UM filho para o
    conjunto; um-a-um so' para os pids que o lote reportou como falhados.
    """
    w('kill pid=%d (identidade: o pid que GANHOU a mutex no log da propria app)' % pid)
    # A FONTE HIGH E' RESOLVIDA ANTES DA MORTE: o token da app morre com ela (2026-10-30).
    source = source or _token_launcher()._selftest_source()
    # A DESCENDENCIA E' APANHADA ANTES DA MORTE: depois dela o `ParentProcessId`
    # deixa de apontar para quem interessa.
    snapshot = _children_of([pid])
    targets = _kill_targets(pid, snapshot)
    w('kill pid=%d alvos=%d %s fonte=%s' % (pid, len(targets), targets, source))
    module = _token_launcher()
    # O CAMINHO BARATO SO' EXISTE SE ESTA PANE PUDER MATAR: `taskkill` directo e' um
    # binario nativo (nenhuma crianca de token), mas de uma pane `medium` contra um alvo
    # `high` cada chamada e' um `rc=1` garantido a ~0.5 s de custo (medido 2026-11-03).
    # Quando este processo ja' e' `high`, o loop e' o unico caminho necessario; quando e'
    # `medium`, todos os alvos ficam para o LOTE -- uma crianca, nao uma por pid.
    survivors = targets
    if is_high():
        for target in targets:
            result = subprocess.run(['taskkill', '/PID', str(target), '/T', '/F'],
                                    capture_output=True, close_fds=True,
                                    creationflags=NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
            w('kill directo pid=%d rc=%d' % (target, result.returncode))
        survivors = _live_pids(targets)
    # UM SO' FILHO DE TOKEN PARA O CONJUNTO. `ok` do lote so' e' True com rc==0 em TODOS
    # os pids, por isso 128 (pid inexistente) nao passa por morto; aqui, para a VARREdura,
    # um pid que o Windows diz nao existir ja' esta' no estado desejado.
    if survivors:
        ok, used, child, results = module.kill_pids_via_high(survivors, source)
        w('kill lote via token(fonte=%s) ok=%s filho=%s rc=%s' % (used, ok, child, results))
        by_pid = dict(results)
        failed = [target for target in survivors if by_pid.get(target) not in (0, 128)]
        if failed:
            # O rc do `taskkill` NAO e' a verdade final: um pid a sair devolve rc=1 e
            # desaparece 1 s depois (medido 2026-11-03 no lote). Quem decide e' o CENSO --
            # so' o pid que AINDA existe paga a segunda crianca.
            time.sleep(POLL_S)
            failed = _live_pids(failed)
        if failed:
            w('kill lote: %d pid(s) ainda vivos %s -- a repetir um a um' % (len(failed), failed))
            for target in failed:
                _kill_via_token(target, source)
    # SESSENTA SEGUNDOS, E UMA SEGUNDA TENTATIVA (2026-11-03, MEDIDO NA PROPRIA
    # SESSAO). Com 15 s o relancador dizia `ABORTA: a instancia antiga nao
    # morreu` e nao largava nada -- e a instancia morria 20-30 s depois, ou seja
    # o dono ficava SEM app e sem aviso, que e' o pior dos dois estados. A
    # desmontagem (WebView2 + worker) leva dezenas de segundos nesta maquina.
    # Aos 15 s o que resta leva o `taskkill` outra vez, e o desfecho e' o CENSO.
    deadline = time.time() + 60.0
    retried = False
    while time.time() < deadline:
        survivors = _live_pids(targets)
        if not survivors:
            w('kill pid=%d confirmado morto (alvos=%d)' % (pid, len(targets)))
            return True
        if not retried and time.time() > deadline - 45.0:
            retried = True
            w('kill pid=%d sem morrer aos 15 s; vivos=%s -- segunda tentativa'
              % (pid, survivors))
            for target in survivors:
                _kill_via_token(target, source)
        time.sleep(POLL_S)
    w('kill pid=%d NAO morreu em 60 s; vivos=%s' % (pid, survivors))
    return False


def _kill_via_token(pid, source=None):
    """O MESMO `taskkill`, com o token de um processo `high` desta sessao.

    O filho larga `taskkill /PID <pid> /F` e o pai espera o desfecho no ficheiro de
    estado do relancador; sem filho possivel, diz-se que nao matou em vez de se
    assumir que morreu.
    """
    module = _token_launcher()
    source = source or module._selftest_source()
    if not source:
        w('kill pid=%d: nenhum processo high para emprestar token -- NAO matei' % pid)
        return False
    ok, used, child = module.kill_via_high(pid, source)
    w('kill pid=%d via token(fonte=%s) ok=%s filho=%s' % (pid, used, ok, child))
    return bool(ok)


def wait_mutex_free(timeout=MUTEX_WAIT_S):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if mutex_free():
            return True
        time.sleep(POLL_S)
    return mutex_free()


def _token_launcher():
    """`_main/launch-as-token.py` carregado por caminho (o nome tem hifenes)."""
    import importlib.util
    path = os.path.join(ROOT, '_main', 'launch-as-token.py')
    spec = importlib.util.spec_from_file_location('launch_as_token', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def launch_via_task():
    """Fallback launcher: the task runs as HIM, in HIS session, `high`."""
    w('schtasks /run /tn %s' % TASK)
    result = subprocess.run(['schtasks', '/run', '/tn', TASK], capture_output=True,
                            close_fds=True, creationflags=NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    return result.returncode == 0


def launch_via_token(source_pid, runner=None, extra=None):
    """This pane cannot do it itself (medium); borrow the live instance's token.

    `runner` exists so a lane can exercise THIS function with a harmless payload
    (`python -c "import sotto_relaunch; sotto_relaunch.launch_via_token(pid, runner=...)`)
    instead of proposing a proof it never ran.
    """
    module = _token_launcher()
    cmd = os.path.join(os.environ.get('SYSTEMROOT', r'C:\Windows'), 'System32', 'cmd.exe')
    runner = runner or os.path.join(ROOT, 'app', 'webview', 'run.cmd')
    argv = ['/c', runner]
    # O AUTO-RELANCAMENTO DA SHELL FORA DA LARGADA DA LANE (2026-11-03).
    # MEDIDO: cada largada minha deixou DOIS `pythonw.exe` filhos do explorer
    # (pids 43032/48812 as 03:39) a deter `Local\\SottoShell`, e a largada
    # seguinte abortava em 20 s. O flag existe exactamente para isto
    # (`app/webview/shell_relaunch.py`), e a lane nao quer que a app se
    # relance sozinha por baixo dela.
    if extra:
        argv.extend(extra)
    ok, err, child = module.launch(source_pid, cmd, argv, cwd=ROOT,
                                flags=NO_WINDOW | 0x00000200)  # + CREATE_NEW_PROCESS_GROUP
    w('CreateProcessAsUser(fonte=%d) ok=%s err=%d filho=%s runner=%s'
      % (source_pid, ok, err, child, runner))
    return bool(ok)


def is_high():
    return _token_launcher().integrity_name(_token_launcher().integrity_of()) == 'HIGH'


def wait_ready(pid_before, timeout=READY_TIMEOUT_S):
    """Waits for a NEW winner in the log: `SHELL_STARTUP_STAGE` after our launch."""
    deadline = time.time() + timeout
    seen = set(pid_before)
    while time.time() < deadline:
        text = log_text()
        for pid in re.findall(r'SHELL_STARTUP_STAGE pid=(\d+) stage=pre-lock', text):
            pid = int(pid)
            if pid in seen:
                continue
            seen.add(pid)
            tail = text[text.rfind('SHELL_STARTUP_STAGE pid=%d' % pid):]
            if 'already_running=true' in tail[:2000]:
                w('pid %d RECUSADO pela mutex (a antiga ainda a tinha)' % pid)
                continue
            if 'SINGLE_INSTANCE' in tail[:2000] and 'already_running=false' in tail[:2000]:
                w('pid %d GANHOU a mutex' % pid)
                return pid
        time.sleep(POLL_S)
    return None


def health(pid):
    """What the log says about THIS pid, from its own startup lines."""
    text = log_text()
    start = text.rfind('SHELL_STARTUP_STAGE pid=%d' % pid)
    if start < 0:
        return {'log': False}
    window = text[start:start + 60000]
    out = {'log': True,
           'mutex': 'already_running=false' in window,
           'code_id': (re.search(r'SHELL_CODE_ID sha256=(\w+)', window) or [None, None])[1],
           'hotkey': bool(re.search(r'HOTKEY_REGISTERED', window)),
           'tray': bool(re.search(r'TRAY_ICON_ADD ok=true', window)),
           # NAO 'genuine': o log so' escreve WEBVIEW2_INIT quando a inicializacao
           # FALHA (WEBVIEW2_INIT_FAILED). Ler a existencia dessa linha como saude
           # invertia o sentido -- medido 2026-10-30 numa largada SAUDAVEL que
           # publicava genuine=False. O nome diz o que o predicado mede.
           'webview2_failed': bool(re.search(r'WEBVIEW2_INIT_FAILED', window))}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--check', action='store_true', help='nao toca em nada')
    ap.add_argument('--relaunch', action='store_true', help='mata a instancia viva e lanca')
    ap.add_argument('--tag', default='manual', help='quem pediu (vai para o log)')
    args = ap.parse_args(argv)

    pid = live_shell_pid()
    if args.check or not args.relaunch:
        print('instancia viva : %s' % (pid if pid else 'NENHUMA'))
        print('mutex livre    : %s' % mutex_free())
        if pid:
            print('saude          : %s' % health(pid))
        return 0 if pid else 1

    w('relaunch pedido tag=%s' % args.tag)
    before = set(int(p) for p in re.findall(r'SHELL_STARTUP_STAGE pid=(\d+)', log_text()))
    # QUEM MATA E' QUEM PODE: matar um processo `high` a partir de `medium` da' err=5, por
    # isso uma chamada de uma pane `medium` delega a um filho `high` com o token do shell
    # vivo (que e' high) e espera pelo veredicto dele. Sem instancia viva nao ha token para
    # emprestar: a tarefa e' o unico caminho, e e' ela que trata do kill.
    if not is_high() and pid:
        # A FONTE HIGH E' APANHADA ANTES DE MATAR: o token da app morre com ela, e era
        # esse o erro que deixava a largada a arrancar um `run.cmd` que morria calado na
        # mutex que a instancia velha ainda tinha (medido 2026-10-30: 90 s sem instancia).
        source = _token_launcher()._selftest_source()
        if not source:
            w('ABORTA: nenhum processo high nesta sessao para emprestar token')
            return 6
        # `kill` resolve a fonte high ANTES de matar (por dentro); a fonte acima ja'
        # provou que ela existe, e e' a mesma que a largada vai usar.
        if not kill(pid):
            w('ABORTA: a instancia antiga nao morreu; nao lanco nada')
            return 2
        if not wait_mutex_free():
            w('ABORTA: a mutex %s continua tomada depois de %ds' % (MUTEX, MUTEX_WAIT_S))
            return 3
        w('mutex livre; a largar com o token de %d' % source)
        if not launch_via_token(source, extra=['--no-self-relaunch']):
            w('ABORTA: nao consegui largar o filho high com o token de %d' % source)
            return 6
        new = wait_ready(before)
        if not new:
            w('FALHA (via token): nenhuma instancia nova em %.0fs' % READY_TIMEOUT_S)
            return 5
        info = health(new)
        w('saude do pid %d: %s' % (new, info))
        return 0 if info.get('mutex') else 5
    if pid:
        if not kill(pid):
            w('ABORTA: a instancia antiga nao morreu; nao lanco nada')
            return 2
    if not wait_mutex_free():
        w('ABORTA: a mutex %s continua tomada depois de %ds' % (MUTEX, MUTEX_WAIT_S))
        return 3
    w('mutex livre')
    # SEM INSTANCIA VIVA NAO HA TOKEN DA APP PARA EMPRESTAR -- mas o EMPRESTADOR nao
    # precisa de ser a app: qualquer processo `high` da sessao serve, e `explorer.exe`
    # esta' `high` (medido: S-1-16-12288, pids 13844 e 25928). Ate' 2026-10-30 esta
    # ramo caia directo na TAREFA, e a tarefa esta' partida: `schtasks /run /tn Sotto`
    # devolveu `-1073741510` (0xC000013A, STATUS_CONTROL_C_EXIT, medido 11:02:19) e
    # NAO largou nada -- o dono ficou sem app e o instrumento dizia "mutex livre".
    # A ordem agora e': token (de mim, se ja' sou `high`; senao de quem estiver) e SO'
    # DEPOIS a tarefa, com o motivo escrito quando nenhum dos dois existe.
    launched = False
    if is_high():
        launched = launch_via_token(os.getpid(), extra=['--no-self-relaunch'])
    else:
        source = _token_launcher()._selftest_source()
        if source:
            w('sem instancia viva; a largar com o token de %d' % source)
            launched = launch_via_token(source, extra=['--no-self-relaunch'])
        else:
            w('sem processo high para emprestar token; a cair na tarefa')
            launched = launch_via_task()
    if not launched:
        w('ABORTA: nenhum lancador funcionou (token e tarefa)')
        return 4
    new = wait_ready(before)
    if not new:
        w('FALHA: nenhuma instancia nova ganhou a mutex em %.0fs' % READY_TIMEOUT_S)
        return 5
    info = health(new)
    w('saude do pid %d: %s' % (new, info))
    if not info.get('mutex'):
        return 5
    if not info.get('hotkey'):
        w('AVISO: HOTKEY_REGISTERED nao apareceu ainda (a app pode registar depois do render)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
