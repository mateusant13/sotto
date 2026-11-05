"""O PORTAO DA SAIDA: uma saida que escreveu no log TERMINA?

O DEFEITO (medido 2026-11-04). `_main/webview-run.log`:
    13:01:36.080 UI_WATCHDOG_STRIKE strike=3 hwnd=15281090 err=0
    13:01:36.080 UI_HUNG reason=ui-thread-not-responding threads=30 compact=true
    13:01:36.080 UI_WATCHDOG_EXIT code=9 -- a UI estava presa; a sair para ...
    (13:01:36.082, .087, .575 -- mais tres linhas, e o ficheiro ACABA)
A 14:12 o pid 20448 estava VIVO: 36 threads, 8/10 janelas com
`IsHungAppWindow=1` (medido agora, `WM_NULL` sem resposta em 600 ms), 2,6 % de um
nucleo, e o filho pid 36668 com 3,9 GB privados. A saida foi REGISTADA e NAO
COMPLETOU.

O QUE ESTE FICHEIRO PROVA, e cada arme e' uma ASSERTION DE ESTADO, nunca texto:
  A birth              o caminho normal sai com o codigo pedido e o filho morre
  B primary-hangs      o PRIMITIVO de saida nao volta (injecao) -> o escalador
                       mata o processo na mesma
  C all-in-process-hang o primitivo E o escalador nao voltam -> o MATADOR
                       EXTERNO mata o shell E um filho que ignorou o kill
  D stuck-child        um filho que recusa `kill`/`wait` fica NOMEADO
                       (`EXIT_CHILD_STUCK`) e a saida nao espera por ele
  E mutant-red         a COPY com o escalador e o matador desarmados mostra o
                       defeito de volta: o processo FICA VIVO (RED)

Uso:
    python _main/dead-app-exit-oracle.py            # armes A-E + veredicto
    python _main/dead-app-exit-oracle.py --static   # so' os armes de fonte
Nenhuma janela, nenhum audio, um segundo Sotto NAO arranca: cada arme e' um
processo Python separado que importa o shell headless (como
`_main/tray-menu-oracle.py`) e so' corre `_hard_exit`.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL_DIR = os.path.join(os.path.dirname(HERE), 'app', 'webview')
SHELL = os.path.join(SHELL_DIR, 'sotto_webview.py')
SELF = os.path.abspath(__file__)
RUN = os.path.join(HERE, '_deadexit')
MUTANT = os.path.join(SHELL_DIR, 'sotto_webview__mutant_exit.py')
CREATE_NO_WINDOW = 0x08000000
SETTLE_S = 8.0

#: Arme -> (cfg, expected). `cfg` viaja para o filho; `expected` e' o que o pai
#: exige do ESTADO.
ARMS = {
    'birth': dict(primary_blocks=False, escalate_s=1.0, grace_s=1.5,
                  stuck_child=False, module=SHELL),
    'primary-hangs': dict(primary_blocks=True, escalate_s=1.0, grace_s=600.0,
                          stuck_child=False, module=SHELL),
    'all-in-process-hang': dict(primary_blocks=True, escalate_s=600.0,
                                grace_s=1.5, stuck_child=True, module=SHELL),
    'stuck-child': dict(primary_blocks=False, escalate_s=1.0, grace_s=1.5,
                        stuck_child=True, module=SHELL),
    'mutant-red': dict(primary_blocks=True, escalate_s=600.0, grace_s=600.0,
                       stuck_child=False, module=MUTANT),
}


# ─── helpers ────────────────────────────────────────────────────────────────
def pid_alive(pid):
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    h = k32.OpenProcess(0x1000, False, int(pid))
    if not h:
        return False
    try:
        code = ctypes.c_uint32(0)
        if not k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code)):
            return False
        return code.value == 259            # STILL_ACTIVE
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


def kill_own(pid):
    """Mata SO' um pid que este harness lancou (nunca um pid do dono)."""
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    h = k32.OpenProcess(0x0001, False, int(pid))
    if h:
        k32.TerminateProcess(ctypes.c_void_p(h), 1)
        k32.CloseHandle(ctypes.c_void_p(h))


def wait_dead(pid, timeout_s):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        if not pid_alive(pid):
            return round((time.monotonic() - t0) * 1000.0, 1)
        time.sleep(0.05)
    return None


def read_log(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


# ─── the child: imports the REAL shell headless and exits through it ───────
class StuckChild:
    """Um filho que RECUSA morrer: `kill` e `wait` levantam como um deadlock."""

    def __init__(self, pid):
        self.pid = pid

    def kill(self):
        raise OSError('refused to die (injected)')

    def wait(self, timeout=None):
        raise TimeoutError('wait refused (injected)')


def child_main(cfg_path):
    cfg = json.load(open(cfg_path, encoding='utf-8'))
    os.makedirs(cfg['run'], exist_ok=True)
    log_path = os.path.join(cfg['run'], 'shell.log')
    sys.path.insert(0, SHELL_DIR)
    import importlib.util
    spec = importlib.util.spec_from_file_location('shell_under_exit',
                                                  cfg['module'])
    shell = importlib.util.module_from_spec(spec)
    sys.modules['shell_under_exit'] = shell
    spec.loader.exec_module(shell)
    shell._open_log(log_path)
    shell.EXIT_ESCALATE_S = cfg['escalate_s']
    shell.EXIT_KILLER_GRACE_S = cfg['grace_s']
    shell.EXIT_LOG_DRAIN_S = 0.2

    worker = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,
                              creationflags=CREATE_NO_WINDOW,
                              startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    with open(os.path.join(cfg['run'], 'worker.pid'), 'w') as fh:
        fh.write(str(worker.pid))
    child = StuckChild(worker.pid) if cfg['stuck_child'] else worker

    if cfg['primary_blocks']:
        # A INJECCAO: o primitivo de saida NAO VOLTA -- o comportamento medido
        # de `os._exit` no shell do dono. Nao se injeta um bloqueio de kernel;
        # injeta-se o facto observavel: a chamada nao retorna.
        def _blocks(code):
            time.sleep(600)
        shell._exit_primary = _blocks
    shell._hard_exit(7, 'oracle:' + os.path.basename(cfg['module']),
                     children=[child])


def run_child(cfg, run_dir):
    cfg = dict(cfg)
    cfg['run'] = run_dir
    cfg_path = os.path.join(run_dir, 'cfg.json')
    with open(cfg_path, 'w', encoding='utf-8') as fh:
        json.dump(cfg, fh)
    proc = subprocess.Popen([sys.executable, SELF, '--child', cfg_path],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE,
                            creationflags=CREATE_NO_WINDOW,
                            startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    worker_file = os.path.join(run_dir, 'worker.pid')
    worker_pid = None
    t0 = time.monotonic()
    while time.monotonic() - t0 < SETTLE_S:
        if proc.poll() is not None:
            break
        if worker_pid is None and os.path.exists(worker_file):
            txt = open(worker_file).read().strip()
            worker_pid = int(txt) if txt.isdigit() else None
        time.sleep(0.05)
    rc = proc.poll()
    waited_shell = None if rc is None else round((time.monotonic() - t0) * 1000.0, 1)
    if worker_pid is None and os.path.exists(worker_file):
        txt = open(worker_file).read().strip()
        worker_pid = int(txt) if txt.isdigit() else None
    # the shell may still run while the worker dies; give it the same settle
    shell_dead = wait_dead(proc.pid, SETTLE_S) if rc is None else 0.0
    worker_dead_at = wait_dead(worker_pid, SETTLE_S) if worker_pid else None
    log_text = read_log(os.path.join(run_dir, 'shell.log'))
    if rc is None:                       # only for the RED arm / a hang
        kill_own(proc.pid)
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    if worker_pid and pid_alive(worker_pid):
        kill_own(worker_pid)
    err = ''
    try:
        err = (proc.stderr.read() or b'').decode('utf-8', 'replace')[-400:]
    except Exception:
        pass
    return {
        'rc': rc,
        'shell_pid': proc.pid,
        'shell_dead_ms': shell_dead,
        'worker_pid': worker_pid,
        'worker_dead_ms': worker_dead_at,
        'worker_still_alive': bool(worker_pid and pid_alive(worker_pid)),
        'log': log_text,
        'stdout_tail': err,
        'settled_ms': waited_shell,
    }


def judge_run(name, res):
    """(ok, detail) por arme -- estado, nunca texto solto."""
    log = res['log']
    has = lambda tag: tag in log                                        # noqa: E731
    terminal = has('EXIT_TERMINATE')
    if name == 'birth':
        ok = (res['rc'] == 7 and not res['worker_still_alive'] and terminal
              and has('EXIT_CHILD_REAPED'))
        return ok, dict(rc=res['rc'], terminal=terminal,
                        worker_still_alive=res['worker_still_alive'])
    if name in ('primary-hangs', 'all-in-process-hang'):
        saved_by = ('EXIT_ESCALATED_SELF' if has('EXIT_ESCALATED_SELF') else '') \
            + ('+EXIT_KILLER_FIRED' if has('EXIT_KILLER_FIRED') else '')
        if name == 'primary-hangs':
            want = 'EXIT_ESCALATED_SELF'
            ok = res['rc'] == 7 and saved_by.startswith(want)
        else:
            # NENHUM primitivo in-process volta: SO' o matador externo pode.
            ok = res['rc'] == 7 and has('EXIT_KILLER_FIRED')
        ok = ok and not res['worker_still_alive'] and terminal
        return ok, dict(rc=res['rc'], saved_by=saved_by or 'NONE',
                        terminal=terminal,
                        worker_still_alive=res['worker_still_alive'])
    if name == 'stuck-child':
        ok = (res['rc'] == 7 and has('EXIT_CHILD_STUCK') and terminal
              and not res['worker_still_alive'])
        return ok, dict(rc=res['rc'], stuck_named=has('EXIT_CHILD_STUCK'),
                        terminal=terminal,
                        worker_still_alive=res['worker_still_alive'])
    if name == 'mutant-red':
        # O ARME RED: com os dois donos desarmados o processo TEM de ficar vivo.
        # Se este arme "passasse", o portao nao estava a medir nada.
        hung = res['rc'] is None
        return hung, dict(hung=hung, shell_pid=res['shell_pid'],
                          rc=res['rc'])
    return False, dict(reason='unknown-arm')


# ─── static arms: the source must carry no unbounded exit path ─────────────
STATIC_ARMS = (
    ('no_of_exit_outside_primitive',
     lambda src: len(re.findall(r'^\s*os\._exit\(', src, re.M)) == 1),
    ('watchdog_uses_hard_exit',
     lambda src: "_hard_exit(9, 'ui-watchdog'" in src),
    ('exit_dump_not_compacted',
     lambda src: "_dump_thread_stacks('ui-thread-not-responding', force=True)" in src),
    ('request_exit_uses_hard_exit',
     lambda src: "_hard_exit(code, reason, children=_kids)" in src),
    ('emit_iterates_snapshot',
     lambda src: 'for _kind, _payload in list(q.items()):' in src),
    ('killer_script_present',
     lambda src: os.path.exists(os.path.join(SHELL_DIR, 'exit_killer.py'))),
)


def static_arms():
    src = open(SHELL, encoding='utf-8').read()
    out = []
    for name, fn in STATIC_ARMS:
        try:
            ok = bool(fn(src))
        except Exception as exc:                            # noqa: BLE001
            ok = False
            print(f'STATIC {name}: ERROR {exc!r}')
        out.append((name, ok))
    return out


def build_mutant():
    """O arme RED: uma COPY com o escalador e o matador DESARMADOS."""
    src = open(SHELL, encoding='utf-8', newline='').read()
    crlf = '\r\n' in src
    body = src.replace('\r\n', '\n')
    edits = [
        ("        if _EXIT_STATE['escalated'].wait(EXIT_ESCALATE_S):\n",
         "        if True:  # RED ARM: escalador desarmado\n"),
        ("    _spawn_exit_killer(code, pids, say)\n",
         "    pass  # RED ARM: matador externo desarmado\n"),
    ]
    applied = 0
    for before, after in edits:
        if before not in body:
            print(f'MUTANT ANCHOR ABSENT: {before!r}')
            continue
        body = body.replace(before, after, 1)
        applied += 1
    if crlf:
        body = body.replace('\n', '\r\n')
    with open(MUTANT, 'w', encoding='utf-8', newline='') as fh:
        fh.write(body)
    return applied == len(edits)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--child' in argv:
        child_main(argv[argv.index('--child') + 1])
        return 0
    only_static = '--static' in argv
    os.makedirs(RUN, exist_ok=True)
    verdicts = []
    if not only_static:
        for name in ('birth', 'primary-hangs', 'all-in-process-hang',
                     'stuck-child'):
            run_dir = os.path.join(RUN, name)
            shutil.rmtree(run_dir, ignore_errors=True)
            os.makedirs(run_dir, exist_ok=True)
            res = run_child(ARMS[name], run_dir)
            ok, detail = judge_run(name, res)
            verdicts.append((name, ok, detail))
            print(f'ARM {"PASS" if ok else "FAIL"} {name} {json.dumps(detail)}')
        # RED
        if build_mutant():
            run_dir = os.path.join(RUN, 'mutant-red')
            shutil.rmtree(run_dir, ignore_errors=True)
            os.makedirs(run_dir, exist_ok=True)
            res = run_child(ARMS['mutant-red'], run_dir)
            ok, detail = judge_run('mutant-red', res)
            verdicts.append(('mutant-red(HUNG=caught)', ok, detail))
            print(f'ARM {"CAUGHT" if ok else "NOT-CAUGHT"} mutant-red '
                  f'{json.dumps(detail)}')
            try:
                os.remove(MUTANT)
            except OSError:
                pass
        else:
            verdicts.append(('mutant-red', False, {'reason': 'mutant-not-built'}))
    for name, ok in static_arms():
        verdicts.append(('static:' + name, ok, {}))
        print(f'STATIC {"PASS" if ok else "FAIL"} {name}')
    failed = [v for v in verdicts if not v[1]]
    print(f'CHECK arms={len(verdicts)} failed={len(failed)}')
    print('VERDICT: PASS' if not failed else 'VERDICT: FAIL')
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
