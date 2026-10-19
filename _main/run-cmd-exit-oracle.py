"""The exit contract of `app/webview/run.cmd` -- asserted on both colours.

WHAT WAS MEASURED, AND BY WHOM (lane SottoRunCmdEntry, 2026-10-06; re-found
nowhere -- this oracle GATES it, it does not re-derive it)
    `run.cmd --bogus-flag` -> rc=0, stdout empty, NO log bytes, NO shell line,
    NO leftover process. argparse rejects the flag and exits 2 on pythonw.exe
    (which has no stdout), `start` reports only its OWN success, so the
    interpreter's status never reaches the caller: a failure answering as
    success.

THE FIX THIS GATES
    run.cmd PRE-FLIGHTS the argument list with the shell's OWN parser
    (`sotto_webview.py --check-args`, hidden from `--help`) and spawns the app
    only when that parse returns 0. `start` is kept, because a wrapper that
    waited for the app would hold the caller's console open for the whole
    session; the child's status is taken in the pre-flight run, which starts
    nothing. There is no second flag table in batch to drift from argparse.

ARMS (each asserts the rc, and the rc alone is not enough evidence for any of
them -- each arm carries a second, independent observation)
    1 bogus          `--bogus-flag`  -> rc 2 (the child's own argparse status,
                                       passed through), wrapper says REFUSED,
                                       a receipt line lands in the run log,
                                       and no shell line and no process appear:
                                       the log proves the app never started.
    2 help           `--help`        -> rc 0, the FULL usage on stdout (every
                                       `add_argument` the shell source declares
                                       is required to appear -- drift-free, and
                                       `--check-args` must NOT appear: the
                                       pre-flight stays hidden).
    3 start-logged   `--log <tmp>`   -> rc 0 and the app really started: the
    4 start-default  (no `--log`)      pid is read from the app's OWN first log
                                       line, that pid must be a live process,
                                       the run must reach its own `SHELL_EXIT`,
                                       and the pid must be GONE at the end.
                                       Armed 3 and 4 cover the wrapper's two
                                       normal branches (explicit `--log` and the
                                       default log).
                                       BOTH carry the G3 contract, in two
                                       independent measurements:
                                         (a) the app was STILL RUNNING when
                                             the wrapper returned -- so the
                                             wrapper returned on the READINESS
                                             handshake, not on the app's death;
                                         (b) the MARGIN between the wrapper's
                                             return and the app's own exit,
                                             read from the log's own
                                             timestamps. The app's life is
                                             counted from the READINESS moment
                                             (the `--exit-after` timer is armed
                                             in the navigation-completed
                                             callback, sotto_webview.py:6044),
                                             which is why the margin does not
                                             depend on how loaded the machine
                                             is.

THE LINE ARMS 3/4 KEY ON (the readiness line a handshake would use)
    `sotto: shell=webview2 pywebview=<v> python=<v> pid=<N>`
    It is the shell's FIRST line, written before any window exists, and it
    carries the pid -- so it is both "the app started" and "which pid to kill".

KILL DISCIPLINE
    Only the pid parsed out of that log line is ever killed (`taskkill /PID`),
    and only if the app has not already exited by itself. NEVER an image name:
    a filter on the generic word has already killed unrelated processes on this
    box (AGENTS.md). `LockDown_Dom.exe` is a FOREIGN process here and is not
    touched -- this oracle never enumerates by name, it only walks ITS OWN pid
    tree. `wmic` is absent on this box, so parentage comes from
    `CreateToolhelp32Snapshot` (th32ParentProcessID), not from wmic.

WINDOWS
    The census samples at our own cadence (the house census samples once per
    60 s and can only prove PRESENCE -- AGENTS.md). The census primitives are
    the ones this repo already measured (`_main/_armE-window-census.py`),
    imported by path. The tracked pid set is MONOTONE and additionally seeded
    from the app's own log line, because the plain tree walk CANNOT see this
    app: the wrapper detaches with `start`, so the app's recorded parent is the
    short-lived cmd.exe that ran run.cmd -- once that exits, a walk of the LIVE
    process table cannot reach the app at all, and a census that only re-walked
    would report "0 visible samples" while the panel was on the screen. Every
    child here is spawned with CREATE_NO_WINDOW.

NEGATIVE ARM (`--neg-arm`)
    Builds a COPY of the tree whose ONLY difference is the wrapper: run.cmd is
    restored from a saved pre-fix copy (`_main/run-cmd-prefix-20261006.cmd`,
    the bytes of the wrapper the defect was measured on), every other file is
    the one under test. All four arms then run against the copy and the verdict
    is INVERTED for arm 1 only: arm 1 must go RED in the copy and arms 2/3/4
    must stay green. If the pre-fix file already carries the pre-flight (or is
    byte-identical to the wrapper under test) the control is DEAD and the
    oracle refuses instead of reporting a green it did not earn.

GAP ARMS (G1..G4, from docs/audit/launch-entry.md §2; lane SottoRunCmdGaps)
    Each gap is asserted as a PAIR against copies of the tree: the FIXED tree
    (AFTER) and a tree whose shell AND wrapper are the saved pre-fix bytes
    (BEFORE), every other file identical. An arm that cannot show the BEFORE
    reading it claims to have fixed is not evidence, so BEFORE is asserted too
    -- it must read 0 (the failure answering as success) where AFTER is
    non-zero. The four levers, and the scripts that produce them:
      G1 panel absent     the copy's app/panel/panel.html is not written;
                          AFTER rc 3, BEFORE 0 (and BEFORE's own app log
                          carries PANEL_MISSING, so the 0 was a lie).
      G2 pywebview gone   a `webview.py` that raises ImportError is shadowed in
                          on PYTHONPATH; AFTER rc 1, BEFORE 0 (and a DIRECT run
                          of the pre-fix shell measures the 1 the wrapper hid).
      G3 hang             the copy's shell is a stub that logs STAGING_LOADED
                          and sleeps forever, never touching the ready file;
                          AFTER rc 4 (HANG) after the bounded wait, BEFORE 0.
      G4 no pythonw       `py` is shadowed to resolve a fake python.exe with NO
                          pythonw.exe beside it; AFTER rc 3 and names the
                          refusal, BEFORE 0 (the console fallback fires).
    SOTTO_READY_BOUND=5 keeps the G3 arm at ~5 s instead of the shipped 30 s.
    Every detached child the arms start is killed by the pid in its OWN log
    line (_kill_log_pid), never by image name.

MUTANT PHASE (the teeth of the G3 contract)
    The two G3 measurements above are only worth something if they CAN go
    RED. The MUTANT is the app that only gets ready once it is DEAD: the
    wrapper then returns with the app already gone, and the checks must say
    NO. The CONTROL is the same stub with the opposite polarity -- it gets
    ready and STAYS ALIVE -- so a RED control means the instrument is broken
    and the mutant proves nothing. The wrapper under test is the real
    run.cmd, byte for byte; only the shell is the stub, and the stub is
    plain Python: no WebView2, no model, no window -- a few seconds, and the
    owner's machine does not feel it.

USAGE
    py -3 _main/run-cmd-exit-oracle.py                 # the wrapper under test
    py -3 _main/run-cmd-exit-oracle.py --neg-arm       # revert-in-a-COPY, RED
    py -3 _main/run-cmd-exit-oracle.py --run-cmd X.cmd # an explicit wrapper
    py -3 _main/run-cmd-exit-oracle.py --no-gaps       # skip the G1..G4 pairs
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOTTO = os.path.dirname(HERE)
RUN_CMD = os.path.join(SOTTO, 'app', 'webview', 'run.cmd')
CENSUS_INSTRUMENT = os.path.join(HERE, '_armE-window-census.py')
NEG_SRC = os.path.join(HERE, 'run-cmd-prefix-20261006.cmd')
#: The PRE-FIX shell, saved verbatim from app/webview/sotto_webview.py BEFORE
#: the G1/G2 edits (sha256 45f37917d3e49f8cb92ecc39cc2695832ff84899f9e5164969b498e4c7a3da03).
#: The gap arms need to run the defect, not describe it: G1/G2 live in the
#: SHELL, so the control tree gets this file and the live one is the fixed arm.
PRE_FIX_SHELL = os.path.join(HERE, 'sotto-webview-prefix-20261006.py')
PRE_FIX_WRAPPER = NEG_SRC
#: G3's bound for the arm: SOTTO_READY_BOUND, so the hang arm costs ~5 s not 30.
GAP_BOUND_S = '5'
#: G4's fake interpreter dir: a python.exe (a copy of where.exe: a real exe that
#: exits at once and opens NO window) and NO pythonw.exe beside it.
FAKE_PY_SOURCE = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                              'System32', 'where.exe')
#: A stub "app" that logs the first line, then HANGS before the panel navigation
#: completes -- the exact 2026-10-06 shape (launch-entry.md §3/§4). It never
#: touches the ready file, so the fixed wrapper must time out.
HANG_STUB = '''\
import os
import sys
import time

argv = sys.argv[1:]
log = None
for i, a in enumerate(argv):
    if a == '--log' and i + 1 < len(argv):
        log = argv[i + 1]

# run.cmd calls the SAME file for its bounded readiness poll (`--wait-ready`),
# so a faithful stand-in for the shell must answer that mode too -- without
# this the stub would sleep instead of the wrapper's bound expiring, and run.cmd
# would block for the whole stub sleep (measured: the arm timed out at 120 s).
if '--wait-ready' in argv:
    k = argv.index('--wait-ready')
    path = argv[k + 1] if k + 1 < len(argv) else None
    try:
        bound = float(os.environ.get('SOTTO_READY_BOUND', '30'))
    except ValueError:
        bound = 30.0
    deadline = time.time() + bound
    while True:
        if path and os.path.exists(path):
            sys.exit(0)
        if time.time() >= deadline:
            sys.exit(4)
        time.sleep(0.1)
if '--check-args' in argv:
    sys.exit(0)


def w(line):
    if log:
        d = os.path.dirname(os.path.abspath(log))
        if d:
            os.makedirs(d, exist_ok=True)
        with open(log, 'a', encoding='utf-8') as f:
            f.write(line + '\\n')


w('sotto: shell=webview2 pywebview=stub python=stub pid=%d' % os.getpid())
w('sotto: STAGING_LOADED core=yes -> navigating to panel (G3 STUB never-ready)')
time.sleep(600)
'''

#: O MUTANTE DO CONTRATO G3 (2026-10-19). A app de mentira cuja PRONTIDAO
#: chega no MESMO INSTANTE EM QUE MORRE -- a forma exacta do defeito que o
#: check "a app estava VIVA quando o wrapper voltou" tem de apanhar: um
#: wrapper que esperou pela MORTE e devolveu 0 como se fosse a PRONTIDAO.
#:
#: O stub e' a MESMA shell nos dois polos; so o ENV muda:
#:   SOTTO_STUB_READY_AFTER_DEATH=1 -> a metade `--wait-ready` so resolve
#:   DEPOIS do marcador de morte (o mutante);
#:   sem a variavel -> resolve assim que o ready-file existe (o CONTROLE, em
#:   que a app fica pronta e CONTINUA VIVA).
#:
#: E' um stub em Python: sem WebView2, sem modelo, sem janela, alguns segundos.
#: O custo nao se sente no PC do dono -- ao contrario de um mutante que lance
#: a app de verdade. E o wrapper (`run.cmd`) e' o de VERDADE, byte a byte.
MUTANT_STUB = '''\
import datetime
import os
import sys
import time

argv = sys.argv[1:]
log = None
ready = None
life = 2.0
alive_after = 3.0
for i, a in enumerate(argv):
    if a == '--log' and i + 1 < len(argv):
        log = argv[i + 1]
    if a == '--ready-file' and i + 1 < len(argv):
        ready = argv[i + 1]
    if a == '--stub-life' and i + 1 < len(argv):
        life = float(argv[i + 1])
    if a == '--stub-alive-after' and i + 1 < len(argv):
        alive_after = float(argv[i + 1])

# O wrapper chama a MESMA shell com `--wait-ready` para a espera limitada.
# Esta metade e' a que decide QUANDO o wrapper volta.
if '--wait-ready' in argv:
    k = argv.index('--wait-ready')
    path = argv[k + 1] if k + 1 < len(argv) else None
    try:
        bound = float(os.environ.get('SOTTO_READY_BOUND', '30'))
    except ValueError:
        bound = 30.0
    deadline = time.time() + bound
    while True:
        if path and os.path.exists(path):
            if os.environ.get('SOTTO_STUB_READY_AFTER_DEATH') == '1':
                # O MUTANTE: a prontidao so conta DEPOIS da app estar morta.
                marker = path + '.dead'
                while not os.path.exists(marker):
                    if time.time() >= deadline:
                        sys.exit(4)
                    time.sleep(0.02)
                # A app escreve o marcador e morre logo a seguir; este
                # intervalo e' o que torna a morte DETERMINISTA antes do
                # wrapper voltar (a app ja nao existe quando ele retorna).
                time.sleep(0.25)
            sys.exit(0)
        if time.time() >= deadline:
            sys.exit(4)
        time.sleep(0.1)
if '--check-args' in argv:
    sys.exit(0)


def stamp():
    now = datetime.datetime.now()
    return now.strftime('%Y-%m-%d %H:%M:%S.') + '%03d' % (now.microsecond // 1000)


def w(line):
    if not log:
        return
    d = os.path.dirname(os.path.abspath(log))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(log, 'a', encoding='utf-8') as f:
        f.write(stamp() + ' ' + line + '\\n')


w('sotto: shell=webview2 pywebview=stub python=stub pid=%d' % os.getpid())
time.sleep(life)
if ready:
    with open(ready, 'w') as f:
        f.write('ready\\n')
if alive_after > 0:
    time.sleep(alive_after)
w('sotto: SHELL_EXIT rc=0 reason=requested statsPushes=0')
if ready:
    with open(ready + '.dead', 'w') as f:
        f.write('dead\\n')
sys.exit(0)
'''

CREATE_NO_WINDOW = 0x08000000
PREFLIGHT_MARK = '--check-args'
RUN_ID = time.strftime('%H%M%S')
#: Quando este run comecou. Um residuo nosso tem de ter sido criado DEPOIS
#: disto -- um processo que ja estava a correr antes do oraculo comecar nunca
#: foi resíduo deste run. Ver `leftover_of_ours`.
RUN_STARTED_ISO = time.strftime('%Y-%m-%dT%H:%M:%S')
#: The shell's first line, and the only source of the pid this oracle kills.
READY_RE = re.compile(r'shell=webview2[^\n]*?\bpid=(\d+)')
SHELL_EXIT_RE = re.compile(r'SHELL_EXIT rc=(-?\d+)')
#: run.cmd's refusal receipt. It was `ARGS_REJECTED` while the pre-flight could
#: only see the argv; G1/G2 make it refuse a MISSING PANEL / MISSING PYWEBVIEW
#: too, so the token now names the event, not the cause.
PREFLIGHT_REFUSED_RE = re.compile(r'sotto: PREFLIGHT_REFUSED rc=(\d+)')
#: run.cmd's HANG receipt (G3).
HANG_RE = re.compile(r'sotto: HANG rc=(\d+)')
#: The readiness boundary the app crosses: the panel navigation completed.
READY_BOUNDARY_RE = re.compile(r'PRELOAD_ACTIVE hasSotto=(?:true|false)')
#: O carimbo que a shell poe a cada linha do log: `2026-10-19 14:04:34.873`.
#: A shell carimba com `datetime.now()` em milissegundos (sotto_webview.py:1143-1144),
#: e esse carimbo e' o unico RELOGIO que o oraculo e' a app partilham. A margem
#: real do contrato G3 -- o wrapper voltou ANTES da app sair -- le-se assim: o
#: instante da MORTE (o carimbo da linha SHELL_EXIT) contra o instante do
#: RETORNO do wrapper. As duas leituras sao conservadoras (o carimbo e' anterior
#: a morte real; o retorno e' posterior ao retorno real), logo uma margem
#: negativa e' mesmo negativa.
LOG_STAMP_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s')
FLAG_RE = re.compile(r"add_argument\('(--[a-z0-9-]+)'")
#: Flags that must PRINT, and so never reach the pre-flight in run.cmd. They
#: are the reason arm 2 runs the console interpreter at all. The three SUPPRESS
#: flags are the wrapper's own modes: they must stay OUT of `--help`.
# EIGHT SUPPRESS flags, not three. MEASURED 2026-10-14: the oracle failed arm `help` with
# `missing=['--probe-stats', '--probe-stats-wait', '--probe-outside-click', '--probe-edit-mode', '--mutex-name']` -- five flags the shell declares with `help=argparse.SUPPRESS` (sotto_webview.py:9366, :9368, :9384, :9386, :9412) and which therefore CANNOT appear in `--help`. The set below had three, so those five were treated as VISIBLE and required in the usage, and the failure was the oracle's expectation and not the product. The other three are the wrapper's own modes and must stay out of `--help`; these five are the shell's own probe/measurement switches and are suppressed for the same reason.
HIDDEN_FLAGS = {'--check-args', '--ready-file', '--wait-ready',
                '--probe-stats', '--probe-stats-wait', '--probe-outside-click',
                '--probe-edit-mode', '--mutex-name'}


# --------------------------------------------------------------------------
# small file/process helpers
# --------------------------------------------------------------------------
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def text_of(path: str) -> str:
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        return f.read().decode('utf-8', 'replace')


def size_of(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def tail_from(path: str, offset: int) -> str:
    """Only what THIS run appended: the log is shared and a stale line from a
    previous launch must never be mistaken for this one's."""
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        f.seek(offset)
        return f.read().decode('utf-8', 'replace')


def line_of(txt: str, pattern) -> str:
    """A linha INTEIRA que contem o match do pattern -- com o carimbo que a
    shell poe a frente dela. `m.group(0)` da so o trecho casado."""
    m = pattern.search(txt or '')
    if not m:
        return ''
    start = txt.rfind('\n', 0, m.start()) + 1
    end = txt.find('\n', m.end())
    if end == -1:
        end = len(txt)
    return txt[start:end]


def parse_log_stamp(line: str):
    """O instante (epoch local) do carimbo de uma linha do log, ou None.

    O carimbo e' o mesmo relogio do `time.time()` do oraculo: a shell escreve
    `datetime.now()` em milissegundos (sotto_webview.py:1143-1144) e o
    `datetime` sem fuso, convertido com `.timestamp()`, e' o epoch local -- o
    mesmo numero que `time.time()` devolve. None quando a linha nao tem
    carimbo legivel: e' melhor um "nao medido" do que um zero inventado.
    """
    if not line:
        return None
    m = LOG_STAMP_RE.match(line.strip())
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1),
                                          '%Y-%m-%d %H:%M:%S.%f').timestamp()
    except ValueError:
        return None


def wait_for(path: str, offset: int, pattern, timeout: float):
    """Poll the appended region for `pattern` at our own cadence."""
    deadline = time.time() + timeout
    txt = ''
    while True:
        txt = tail_from(path, offset)
        m = pattern.search(txt)
        if m:
            return m, txt
        if time.time() >= deadline:
            return None, txt
        time.sleep(0.04)


def run_wrapper(run_cmd: str, extra, timeout: float = 120.0,
                capture: bool = True, env: dict | None = None) -> dict:
    """Run the wrapper the way the owner runs it: `cmd /c run.cmd <args>`,
    windowless.

    `capture=False` is REQUIRED for the arms that detach, and the reason is a
    measured one: the detached app INHERITS the wrapper's stdout/stderr handles,
    so a PIPE stays open until the app exits and `subprocess.run` would block
    for the app's whole life -- which then reads as "the wrapper waited for the
    app" when it never did (measured: wrapper_ms=11852 for an 8 s app). With
    DEVNULL there is no pipe to hold, and the call ends when cmd.exe does, so
    `ms` is the wrapper's own wall time.

    `env` is how the gap arms hand the copy a shadowed PATH (G4) or PYTHONPATH
    (G2), and how they shorten G3's bound. Default: the caller's environment.
    """
    argv = ['cmd', '/c', run_cmd] + [str(x) for x in extra]
    sink = subprocess.DEVNULL if not capture else subprocess.PIPE
    t0 = time.time()
    p = subprocess.run(argv, stdout=sink, stderr=sink, text=True,
                       errors='replace', creationflags=CREATE_NO_WINDOW,
                       timeout=timeout, cwd=os.path.dirname(run_cmd),
                       env=env)
    return {'args': [str(x) for x in extra], 'rc': p.returncode,
            'stdout': p.stdout or '', 'stderr': p.stderr or '',
            'ms': int((time.time() - t0) * 1000)}


def load_census_primitives():
    """The census primitives this repo already measured, imported by path (the
    file name has dashes). Imported, never edited: a second implementation
    would be a second answer to "was a window visible"."""
    spec = importlib.util.spec_from_file_location('_sotto_census',
                                                 CENSUS_INSTRUMENT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Census(threading.Thread):
    """Visible top-level windows owned by THIS run's process tree."""

    def __init__(self, root_pid: int, primitives, cadence_s: float):
        super().__init__(daemon=True)
        self.root = root_pid
        self.pr = primitives
        self.cadence = cadence_s
        self.tracked = {root_pid}
        self.samples = 0
        self.visible_samples = 0
        self.hits: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._stop_ev = threading.Event()

    def track(self, pid) -> None:
        if pid:
            with self._lock:
                self.tracked.add(int(pid))

    def snapshot(self) -> dict:
        with self._lock:
            return {'samples': self.samples,
                    'visible_samples': self.visible_samples,
                    'tracked': sorted(self.tracked),
                    'hits': dict(self.hits)}

    def reset_counters(self) -> dict:
        """Zero the counters and the hit table, keep the tracked pids, and
        return what was cleared.

        This exists to separate the ARMS phase (the FIXED app under the FIXED
        wrapper -- a window here is an app defect) from the GAP phase, which
        deliberately runs DEFECTIVE copies: the G4 BEFORE arm starts the app
        under a console interpreter and a console window is the DEFECT working,
        not a regression. Folding the two into one count made the census RED
        read as "the wrapper put a window up" when the arm meant the opposite.
        """
        with self._lock:
            snap = {'samples': self.samples,
                    'visible_samples': self.visible_samples,
                    'tracked': sorted(self.tracked),
                    'hits': dict(self.hits)}
            self.samples = 0
            self.visible_samples = 0
            self.hits = {}
            return snap

    def run(self) -> None:
        while not self._stop_ev.is_set():
            try:
                pids = self.pr.tree(self.root)
            except Exception:  # noqa: BLE001 -- a census must not kill the run
                pids = set()
            with self._lock:
                self.tracked |= pids
                tracked = set(self.tracked)
            wins = [w for w in self.pr.visible_windows() if w[0] in tracked]
            with self._lock:
                self.samples += 1
                if wins:
                    self.visible_samples += 1
                    for pid, hwnd, title, cls in wins:
                        key = f'{pid}:{hwnd}'
                        row = self.hits.setdefault(
                            key, {'pid': pid, 'hwnd': hwnd,
                                  'title': title, 'class': cls, 'n': 0})
                        row['n'] += 1
            time.sleep(self.cadence)

    def stop(self) -> None:
        self._stop_ev.set()
        self.join(timeout=5)


def pid_alive(pr, pid: int) -> bool:
    return any(p == pid for p, _ppid, _exe in pr.process_table())


def pids_in_tree(pr, root: int) -> set:
    return set(pr.tree(root))


#: Os ARTEFACTOS DELE. A regra do repo, escrita: *"A kill filter names the
#: ARTIFACT, never a generic word."* Este check de "sobrou algum processo" nao a
#: seguia, e o resultado foi MEDIDO 2026-10-19: `tree()` anda a arvore pelo
#: PARENT PID, e o Windows RECICLA pids -- um `LuaTools.exe` de dois dias antes,
#: cujo ParentProcessId guardado era o pid que o oraculo tem hoje, foi adoptado
#: como filho e acusado como resíduo. O portao acusou uma aplicacao do dono
#: que nunca foi dele. Um gate que acusa o dono e' pior do que um gate calado.
OUR_ARTEFACTS = ('sotto_webview.py', 'sotto_worker.py', 'speaker_sidecar.py',
                  'run.cmd', 'speaker_bridge.py')

#: Os exe's que o NOSSO wrapper pode deixar para tras. So se usa quando o WMI
#: nao responde -- e nesse caso o check diz que foi mais fraco.
OUR_RUNTIMES = ('python.exe', 'pythonw.exe', 'cmd.exe', 'conhost.exe',
                 'msedgewebview2.exe')


def wmi_process_info(pids, since_iso: str) -> dict:
    """{pid: (cmdline, criado_depois_de_since)} para os pids dados.

    A tabela de processos do censo (`_armE-window-census.py`) da o NOME DO
    EXE, nao a linha de comando -- e a linha de comando e' o que a regra do repo
    pede. Uma chamada so ao WMI, sem janela, e' o preco.

    Devolve {} se o WMI nao responder: o chamador entao diz que o check foi
    mais fraco, em vez de fingir que viu o que nao viu.
    """
    if not pids:
        return {}
    ids = ','.join(str(int(p)) for p in pids)
    script = (
        "$ids=@(%s); $since=[datetime]::Parse('%s'); "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $ids -contains $_.ProcessId } | "
        "ForEach-Object { "
        "\"$($_.ProcessId)`t$($_.CreationDate -gt $since)`t$($_.CommandLine)\" }"
        % (ids, since_iso))
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True, text=True, errors='replace',
            creationflags=CREATE_NO_WINDOW, timeout=60)
    except Exception:
        return {}
    rows = {}
    for line in (out.stdout or '').splitlines():
        parts = line.split('\t', 2)
        if len(parts) == 3 and parts[0].strip().isdigit():
            rows[int(parts[0])] = (parts[2].strip(), parts[1].strip().lower() == 'true')
    return rows


def leftover_of_ours(pr, root: int, since_iso: str):
    """(nossos, alheios_ignorados) -- os processos que sao MESMOS residuo nosso.

    Um residuo nosso tem de ser NOSSO e tem de ser DESTE RUN:

      * **nosso** -- a linha de comando nomeia um artefacto do produto
        (`sotto_webview.py`, `run.cmd`, ...);
      * **deste run** -- foi criado depois de o oraculo comecar. Um processo de
        dois dias atras nao pode ser o que este run deixou para tras.

    A arvore por parent-pid fica como o que e: uma lista de CANDIDATOS. A
    decisao e' da linha de comando.
    """
    tree = pids_in_tree(pr, root) - {root}
    if not tree:
        return set(), []
    rows = wmi_process_info(tree, since_iso)
    if not rows:
        # O WMI nao respondeu: nao se pode afirmar nada pela linha de comando,
        # e nao se vai inventar. Fica o filtro pelo nome do exe, e diz-se.
        table = {p: exe for p, _pp, exe in pr.process_table()}
        ours = {p for p in tree
                if table.get(p, '').lower() in OUR_RUNTIMES}
        return ours, [(p, table.get(p, '?')) for p in tree if p not in ours]
    ours, others = set(), []
    for pid in tree:
        cmdline, _born_after = rows.get(pid, ('', False))
        low = cmdline.lower()
        if any(a in low for a in OUR_ARTEFACTS):
            ours.add(pid)
        else:
            others.append((pid, cmdline[:70] or '(sem linha de comando)'))
    return ours, others


def leftover_check(pr, root: int, since_iso: str) -> tuple:
    """(ok, detalhe) do check 'nao sobrou nada nosso'."""
    ours, others = leftover_of_ours(pr, root, since_iso)
    detail = 'leftovers=%s' % sorted(ours)
    if others:
        detail += ('  (ignorados %d processo(s) alheios da arvore: %s)'
                   % (len(others), others[:2]))
    return not ours, detail


def wait_gone(pr, pid: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_alive(pr, pid):
            return True
        time.sleep(0.1)
    return not pid_alive(pr, pid)


def kill_by_pid(pid: int) -> tuple:
    """Kill EXACTLY the pid the app published about itself."""
    out = subprocess.run(['taskkill', '/PID', str(pid), '/F'],
                         capture_output=True, text=True, errors='replace',
                         creationflags=CREATE_NO_WINDOW)
    return out.returncode, ((out.stdout or '') + (out.stderr or '')).strip()


# --------------------------------------------------------------------------
# the arms
# --------------------------------------------------------------------------
def default_log_for(run_cmd: str) -> str:
    """Where the wrapper writes a receipt when the user passed no `--log`:
    `<root>\\_main\\webview-run.log` (`run.cmd`, the `PASSED_LOG` branch)."""
    web = os.path.dirname(os.path.abspath(run_cmd))          # <root>/app/webview
    root = os.path.dirname(os.path.dirname(web))             # <root>
    return os.path.join(root, '_main', 'webview-run.log')


#: The refusal capture, and the rc 120 defect it closes. MEASURED 2026-10-14: the
#: SAME command with the SAME interpreter answered **rc 120** when the capture was
#: redirected into the system %TEMP% (`2>G:\Temp\sotto-preflight-refusal.txt`) and
#: **rc 2** with the argparse text present when it went to a writable path. rc 120 is
#: what cmd answers when it cannot give the child the redirect it was told to give it,
#: so a machine whose TEMP is full, read-only or on a drive that refuses the write got
#: a wrapper that REFUSED A GOOD LAUNCH and printed nothing the caller could act on.
#: The cure moved the capture BESIDE THE LOG it is a receipt for (`run.cmd:157`).
REFUSAL_RE = re.compile(r'set "REFUSAL=([^"]*)"', re.I)
TEMP_REDIRECT_RE = re.compile(r'2>\s*"%?%TEMP%', re.I)


def temp_target_checks(run_cmd: str) -> list:
    """STATIC -- launches nothing. Where does the wrapper AIM its refusal capture?

    Three checks, and the second is the one the defect failed: a wrapper that aims
    the capture at %TEMP% is a wrapper that can refuse a good launch on someone
    else's machine, which is exactly what the owner's brief calls out ("this program
    is going to be used by thousands of people and %TEMP% is a property of THEIR
    machine, not of ours").
    """
    text = text_of(run_cmd)
    m = REFUSAL_RE.search(text)
    value = m.group(1) if m else None
    aimed_at_temp = bool(value) and '%TEMP%' in value.upper()
    found = TEMP_REDIRECT_RE.search(text)
    return [('the wrapper DEFINES the refusal capture (the cure is present)',
             value is not None,
             f'REFUSAL={value if value is not None else "(not set)"}'),
            ('the capture is NOT aimed at the system %TEMP% (rc 120, measured 2026-10-14)',
             value is not None and not aimed_at_temp, f'REFUSAL={value}'),
            ('no `2>"%TEMP%..."` redirect survives anywhere in the wrapper',
             not found, 'a redirect into TEMP is still there' if found else 'none')]


def temp_arm(label) -> int:
    """The rc 120 defect restored in a COPY. STATIC: no process is started at all."""
    live = text_of(RUN_CMD)
    m = REFUSAL_RE.search(live)
    if not m:
        print('TEMP-ARM REFUSED: the live wrapper defines no refusal capture, so there is '
              'nothing to mutate and no control to build.')
        return 1
    mutant_text = live.replace(
        m.group(0), 'set "REFUSAL=%TEMP%\\sotto-preflight-refusal.txt"', 1)
    if mutant_text == live:
        print('TEMP-ARM REFUSED: the mutation changed nothing -- the control is DEAD')
        return 1
    path = os.path.join(tempfile.gettempdir(), f'run-cmd-temp-mutant-{RUN_ID}.cmd')
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(mutant_text)
    print(f'TEMP-ARM label={label} -- the rc 120 defect restored in a COPY (static)')
    print(f'TEMP-ARM live={RUN_CMD}')
    print(f'TEMP-ARM mutant={path} ({len(mutant_text)} chars, the target is the ONLY difference)')
    live_checks = temp_target_checks(RUN_CMD)
    for name, ok, ev in live_checks:
        print(f'    [{"ok" if ok else "NO"}] LIVE   {name} :: {ev}')
    checks = temp_target_checks(path)
    for name, ok, ev in checks:
        print(f'    [{"ok" if ok else "NO"}] MUTANT {name} :: {ev}')
    live_ok = all(c[1] for c in live_checks)
    red = any(not c[1] for c in checks)
    try:
        os.remove(path)
    except OSError:
        pass
    ok = live_ok and red
    print(f'TEMP-ARM: live green={live_ok}  mutant RED-as-expected={red}')
    print('NEG-ARM ' + ('PASS' if ok else 'FAIL')
          + (': the %TEMP% target is refused by the check, and the live wrapper is clean'
             if ok else ': the check did not separate the two colours'))
    return 0 if ok else 1


def arm_argv(run_cmd, pr, census, notes) -> dict:
    """THE regression guard for the new gate: every argv set the repo ACTUALLY
    uses must still be accepted by the pre-flight.

    This is the only way the fix can hurt: the pre-flight refuses what argparse
    refuses, so a call site that passes a flag the shell does not know would now
    FAIL where it used to "work" (rc 0, nothing started). Each set below cites
    where it comes from:

      []                             run.cmd with no args (double-click)
      --show --with-worker           app/webview/README.md
      --selftest --log <f>           docs/webview-app-20261006.md
      --exit-after 25                docs/webview-app-20261006.md
      --with-worker --log <f> --no-hotkey --no-hot-reload --exit-after 60
                                     _main/runcmd-entry-driver.py (ARM caption)
      --dump-dom --log <f>           the shell's own measurement path (run.cmd
                                     sends it to python.exe, which never
                                     pre-flights -- asserted here all the same)
      --memory / --opaque            the shell's own flags, same reason
    """
    dummy = os.path.join(HERE, f'_runcmd-argv-arm-{RUN_ID}.log')
    sets = [
        (['no args (double-click)'], []),
        (['README.md: --show --with-worker'], ['--show', '--with-worker']),
        (['webview-app-20261006.md: --selftest --log'],
         ['--selftest', '--log', dummy]),
        (['webview-app-20261006.md: --exit-after 25'],
         ['--exit-after', '25']),
        (['runcmd-entry-driver.py ARM caption'],
         ['--with-worker', '--log', dummy, '--no-hotkey', '--no-hot-reload',
          '--exit-after', '60']),
        (['the --dump-dom measurement path'],
         ['--dump-dom', '--log', dummy]),
        (['the --memory / --opaque flags'], ['--memory']),
        (['the --memory / --opaque flags'], ['--opaque']),
    ]
    checks = []
    rcs = []
    for label, argv in sets:
        res = run_wrapper(run_cmd, ['--check-args'] + argv)
        rcs.append(res['rc'])
        checks.append((f'{label} -> accepted by the pre-flight', res['rc'] == 0,
                       f'rc={res["rc"]} argv={argv}'))
    # A REAL rc, not a synthesis: the first non-zero status any set produced,
    # else 0. `rc` is what the wrapper returned, so it must be a measurement.
    rc = next((r for r in rcs if r != 0), 0)
    return {'name': 'argv', 'args': ['--check-args', 'x8 call sites'],
            'rc': rc, 'expect_rc': 0, 'ms': 0, 'checks': checks}


def arm_bogus(run_cmd, pr, census, notes) -> dict:
    """A rejected flag must NOT answer as success."""
    log = default_log_for(run_cmd)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    before = size_of(log)
    res = run_wrapper(run_cmd, ['--bogus-flag'])
    checks = [('rc == 2 (the child\'s own argparse status, passed through)',
               res['rc'] == 2, f"rc={res['rc']}")]
    console = (res['stdout'] + res['stderr']).strip()
    checks.append(('the wrapper says so on its own console',
                   'REFUSED' in console,
                   console.splitlines()[0] if console else '(no output)'))
    appended = tail_from(log, before)
    m = PREFLIGHT_REFUSED_RE.search(appended)
    checks.append(('a receipt line is appended to the run log '
                   '(before the fix this arm appended NO bytes at all)',
                   bool(m), repr(appended.strip()[:160]) or '(nothing appended)'))
    checks.append(('nothing was started: no `shell=webview2` line appended',
                   'shell=webview2' not in appended,
                   f'appended_bytes={len(appended)}'))
    time.sleep(1.0)
    ok, detail = leftover_check(pr, os.getpid(), RUN_STARTED_ISO)
    checks.append(('no process is left behind in this tree', ok, detail))
    return {'name': 'bogus', 'args': res['args'], 'rc': res['rc'],
            'expect_rc': 2, 'ms': res['ms'], 'checks': checks,
            'log': log, 'log_appended': appended.strip()[:400]}


def arm_help(run_cmd, pr, census, notes) -> dict:
    """`--help` must still PRINT, and print EVERYTHING."""
    shell = os.path.join(os.path.dirname(os.path.abspath(run_cmd)),
                         'sotto_webview.py')
    declared = sorted(set(FLAG_RE.findall(text_of(shell))))
    visible = [f for f in declared if f not in HIDDEN_FLAGS]
    res = run_wrapper(run_cmd, ['--help'])
    out = res['stdout'] + res['stderr']
    checks = [('rc == 0', res['rc'] == 0, f"rc={res['rc']}")]
    checks.append(('the console interpreter printed the usage header',
                   'usage: sotto-webview' in out,
                   [l for l in out.splitlines() if l.startswith('usage:')][:1]
                   or '(no usage line)'))
    missing = [f for f in visible if f not in out]
    checks.append((f'every flag the shell declares is in the usage '
                   f'({len(visible) - len(missing)}/{len(visible)})',
                   not missing, f'missing={missing}' if missing else 'none missing'))
    leaked = [f for f in declared if f in HIDDEN_FLAGS and f in out]
    checks.append(('the pre-flight switch stays OUT of --help',
                   not leaked, f'leaked={leaked}' if leaked else 'hidden'))
    time.sleep(0.5)
    ok, detail = leftover_check(pr, os.getpid(), RUN_STARTED_ISO)
    checks.append(('no process is left behind in this tree', ok, detail))
    return {'name': 'help', 'args': res['args'], 'rc': res['rc'],
            'expect_rc': 0, 'ms': res['ms'], 'checks': checks,
            'stdout_bytes': len(out)}


def arm_start(run_cmd, pr, census, notes, name, log, extra, exit_after,
              env=None) -> dict:
    """A normal detached start: rc 0 AND the app really came up, AND it ends
    without a leftover."""
    os.makedirs(os.path.dirname(log), exist_ok=True)
    before = size_of(log)
    res = run_wrapper(run_cmd, extra, capture=False, env=env)
    t_return = time.time()
    checks = [('rc == 0', res['rc'] == 0, f"rc={res['rc']}")]
    # ---- O CONTRATO G3, MEDIDO ---------------------------------------------
    # run.cmd espera a PRONTIDAO da app -- o ficheiro --ready-file que a app
    # toca DEPOIS de PRELOAD_ACTIVE -- e essa espera e' LIMITADA
    # (SOTTO_READY_BOUND, 30 s por omissao na shell, :12565). O wrapper NAO
    # espera pela saida da app.
    #
    # A MEDIDA QUE PROVA "voltou pela PRONTIDAO e nao pela MORTE" e' pontual:
    # no instante em que o wrapper voltou, a app ainda estava VIVA.
    #
    # POR QUE O CHECK ANTIGO REPROVAVA (medido 2026-10-19, bateria g):
    #   wrapper_ms=8198 contra app_lives=8.0s, com a app SAUDAVEL no log
    #   (PRELOAD_ACTIVE hasSotto=true e SHELL_EXIT rc=0). O check comparava o
    #   retorno do wrapper com o TEMPO DE VIDA PEDIDO (8 s) contados desde o
    #   ARRANQUE. Mas o timer de --exit-after e' armado na shell DEPOIS da
    #   navegacao completar (sotto_webview.py:6044, no callback que chama
    #   mark_launch_ready em :5882): a vida da app comeca em T_ready, nao no
    #   arranque. A app morre em T_ready + 8 s; o wrapper volta em T_ready +
    #   ~0.1 s. A margem real e' de ~11 s e NAO depende da carga da maquina --
    #   e o check antigo media essa margem como se a vida comecasse no
    #   arranque, por isso reprovava uma app perfeitamente saudavel.
    #   A margem passa a ser lida do PROPRIO LOG (o carimbo da linha
    #   SHELL_EXIT) e comparada com o instante do retorno do wrapper.
    m, _txt = wait_for(log, before, READY_RE, timeout=15.0)
    pid = int(m.group(1)) if m else None
    if pid:
        census.track(pid)
    checks.append(('the app\'s OWN first line is in the run log, with its pid',
                   pid is not None,
                   m.group(0)[:120] if m else '(no `shell=webview2 ... pid=` line)'))
    alive_at_return = False
    seen_after_ms = -1
    if pid is not None:
        alive_at_return = pid_alive(pr, pid)
        seen_after_ms = int((time.time() - t_return) * 1000)
    checks.append(('the app was STILL RUNNING when the wrapper returned -- so '
                   'the wrapper returned on the READINESS handshake, not on '
                   'the app\'s death',
                   alive_at_return,
                   f'pid={pid} alive={alive_at_return} '
                   f'observed_{seen_after_ms}ms_after_the_return'))
    if pid is None:
        return {'name': name, 'args': res['args'], 'rc': res['rc'],
                'expect_rc': 0, 'ms': res['ms'], 'checks': checks, 'log': log,
                'pid': None}
    alive = False
    deadline = time.time() + 5.0
    while time.time() < deadline and not alive:
        alive = pid_alive(pr, pid)
        if not alive:
            time.sleep(0.05)
    checks.append((f'the published pid ({pid}) was a real, running process',
                   alive, f'pid={pid} alive={alive}'))
    em, etxt = wait_for(log, before, SHELL_EXIT_RE, timeout=exit_after + 12.0)
    checks.append(('the app reached its own clean exit (SHELL_EXIT line)',
                   em is not None, em.group(0) if em else '(no SHELL_EXIT line)'))
    # A MARGEM REAL, lida do proprio log: o instante da MORTE (o carimbo da
    # linha SHELL_EXIT) contra o instante do RETORNO do wrapper. Os dois
    # relogios sao o mesmo relogio desta maquina, e as duas leituras sao
    # conservadoras -- o carimbo e' anterior a morte real e o retorno e'
    # posterior ao retorno real -- logo uma margem negativa e' mesmo negativa.
    exit_at = parse_log_stamp(line_of(etxt, SHELL_EXIT_RE))
    margin_ms = int((exit_at - t_return) * 1000) if exit_at is not None else None
    if em is None:
        margin_ev = '(no SHELL_EXIT line to read a timestamp from)'
    elif margin_ms is None:
        margin_ev = '(the SHELL_EXIT line carries no parsable timestamp)'
    else:
        margin_ev = (f'margin={margin_ms}ms wrapper_ms={res["ms"]} '
                     + ('(the wrapper returned BEFORE the app died)'
                        if margin_ms > 0 else
                        '(the wrapper returned AFTER the app died -- the G3 '
                        'contract is broken)'))
    checks.append(('the wrapper returned BEFORE the app exited (the margin is '
                   'read from the log\'s own timestamps, not from the '
                   'requested lifetime)',
                   margin_ms is not None and margin_ms > 0,
                   margin_ev))
    # The boundary run.cmd's G3 handshake waits on: the wrapper returned only
    # after the app crossed it, so a normal launch cannot time out as a HANG.
    ready_m = READY_BOUNDARY_RE.search(tail_from(log, before))
    checks.append(('the READINESS boundary (PRELOAD_ACTIVE -- what the G3 '
                   'handshake keys on) was crossed in the log',
                   ready_m is not None,
                   ready_m.group(0) if ready_m else '(no PRELOAD_ACTIVE)'))
    gone = wait_gone(pr, pid, timeout=exit_after + 10.0)
    kill_note = ''
    if not gone:
        rc, out = kill_by_pid(pid)
        kill_note = f'(it was still running; taskkill /PID {pid} /F -> rc={rc} {out})'
        gone = wait_gone(pr, pid, 5.0)
    checks.append(('no leftover: the published pid is gone',
                   gone, f'pid={pid} gone={gone} {kill_note}'))
    return {'name': name, 'args': res['args'], 'rc': res['rc'], 'expect_rc': 0,
            'ms': res['ms'], 'checks': checks, 'log': log, 'pid': pid,
            'killed_by_pid': kill_note}


# --------------------------------------------------------------------------
# the gap arms (G1..G4 from docs/audit/launch-entry.md §2)
#
# Each gap is asserted with a PAIR: the FIXED tree (AFTER) and the PRE-FIX tree
# (BEFORE), every other file identical, so the difference between the two is the
# arm's lever and nothing else. An arm that cannot show the BEFORE reading it
# claims to have fixed is not evidence.
# --------------------------------------------------------------------------
PANEL_FILES = ('panel.html', 'panel.css', 'panel.js', 'caption-formulation.js')


def build_tree(notes, variant, shell_src=None, wrapper_src=None,
               drop_panel=False, shadow_webview=False, fake_pythonw=False,
               hang_stub=False, stub_text=None, env_extra=None):
    """A COPY of the tree for one gap arm, plus the environment that arm needs.

    The copy lives under _main so a failing arm can be inspected, and so a run
    never writes the live tree. The copy's own `_main\\webview-run.log` is its
    receipt (run.cmd's relative default), which is why every arm reads the log
    of ITS copy and never the live one.
    """
    root = tempfile.mkdtemp(prefix=f'_gaps-{variant}-', dir=HERE)
    web = os.path.join(root, 'app', 'webview')
    elec = os.path.join(root, 'app', 'panel')
    for d in (web, elec, os.path.join(root, '_main')):
        os.makedirs(d, exist_ok=True)
    src_web = os.path.join(SOTTO, 'app', 'webview')
    # The copy must carry the shell's IMPORT CLOSURE, not a hand-listed pair.
    # The old `('hot_reload.py', 'stage.html')` list drifted the moment the
    # shell grew `import panel_state` (sotto_webview.py:54): every gap copy
    # then died with `ModuleNotFoundError: No module named 'panel_state'` -> the
    # interpreter's rc 1 -- BEFORE it could reach the check under test. Measured
    # 2026-10-07 (lane SottoRunCmdExit): G1's rc-3 expectation read rc 1, and
    # G2's rc-1 expectation passed for the WRONG reason (that same import crash,
    # not the shadowed pywebview). Copy every `.py` sibling so a new module is
    # carried automatically; `shell_src` overwrites the shell itself below.
    for name in sorted(os.listdir(src_web)):
        if name.endswith('.py') or name == 'stage.html':
            shutil.copy2(os.path.join(src_web, name), os.path.join(web, name))
    shutil.copy2(shell_src or os.path.join(src_web, 'sotto_webview.py'),
                 os.path.join(web, 'sotto_webview.py'))
    shutil.copy2(wrapper_src or RUN_CMD, os.path.join(web, 'run.cmd'))
    for name in PANEL_FILES:
        if drop_panel and name == 'panel.html':
            continue
        src = os.path.join(SOTTO, 'app', 'panel', name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(elec, name))
    if hang_stub or stub_text:
        with open(os.path.join(web, 'sotto_webview.py'), 'w',
                  encoding='utf-8') as f:
            f.write(stub_text if stub_text else HANG_STUB)
    env = dict(os.environ)
    env['SOTTO_READY_BOUND'] = GAP_BOUND_S
    for _k, _v in (env_extra or {}).items():
        env[_k] = _v
    if shadow_webview:
        shadow = os.path.join(root, 'shadow')
        os.makedirs(shadow, exist_ok=True)
        with open(os.path.join(shadow, 'webview.py'), 'w',
                  encoding='utf-8') as f:
            f.write('raise ImportError("pywebview is not installed '
                    '(gaps oracle G2)")\n')
        env['PYTHONPATH'] = shadow + os.pathsep + env.get('PYTHONPATH', '')
    if fake_pythonw:
        # A python.exe (a real exe that exits at once and opens NO window) and
        # NO pythonw.exe beside it: the exact state G4's fallback was reachable
        # in, without touching the machine's Python install.
        fake = os.path.join(root, 'fakepy')
        os.makedirs(fake, exist_ok=True)
        shutil.copy2(FAKE_PY_SOURCE, os.path.join(fake, 'python.exe'))
        with open(os.path.join(fake, 'py.cmd'), 'w', encoding='ascii') as f:
            f.write('@echo off\r\necho ' + os.path.join(fake, 'python.exe')
                    + '\r\n')
        env['PATH'] = fake + os.pathsep + env.get('PATH', '')
    notes.append(f'{variant} copy={root}')
    return os.path.join(web, 'run.cmd'), env


def gap_pair(notes, gap, **kw):
    """(AFTER, BEFORE) for one gap: (cmd, env) of the fixed tree and of the
    pre-fix tree (pre-fix shell AND pre-fix wrapper), all else identical."""
    after = build_tree(notes, f'{gap}-after', **kw)
    before_kw = dict(kw)
    before_kw['shell_src'] = PRE_FIX_SHELL
    before_kw['wrapper_src'] = PRE_FIX_WRAPPER
    before = build_tree(notes, f'{gap}-before', **before_kw)
    return after, before


def _app_pid(log: str, timeout: float = 10.0):
    m, _ = wait_for(log, 0, READY_RE, timeout=timeout)
    return int(m.group(1)) if m else None


def arm_gap_panel(notes) -> dict:
    """G1: with app/panel/panel.html absent, `run.cmd --show` must REFUSE."""
    (acmd, aenv), (bcmd, benv) = gap_pair(notes, 'g1', drop_panel=True)
    after = run_wrapper(acmd, ['--show'], env=aenv)
    before = run_wrapper(bcmd, ['--show'], capture=False, env=benv)
    alog, blog = default_log_for(acmd), default_log_for(bcmd)
    _m, btxt = wait_for(blog, 0, re.compile(r'PANEL_MISSING'), timeout=10.0)
    checks = [
        ('AFTER: run.cmd REFUSES the launch (non-zero)',
         after['rc'] != 0, f"rc={after['rc']}"),
        ('AFTER: the refusal is rc 3 -- the SAME status the app exits with',
         after['rc'] == 3,
         f"rc={after['rc']} want=3 stdout={after['stdout'].strip()[:160]!r}"),
        ('AFTER: nothing was started (no shell line in this copy\'s log)',
         'shell=webview2' not in text_of(alog),
         f"log_bytes={size_of(alog)}"),
        ('BEFORE: the pre-fix wrapper answered 0 -- the failure AS SUCCESS',
         before['rc'] == 0, f"rc={before['rc']}"),
        ('BEFORE: the app really did fail (its own log carries PANEL_MISSING)',
         'PANEL_MISSING' in btxt,
         [l for l in btxt.splitlines() if 'PANEL_MISSING' in l][:1]
         or repr(btxt[-160:])),
    ]
    return {'gap': 'G1 panel-absent', 'want': 'non-zero (3); before=0',
            'after': after, 'before': before, 'checks': checks}


def arm_gap_pywebview(notes) -> dict:
    """G2: with `import webview` impossible, `run.cmd --show` must REFUSE."""
    (acmd, aenv), (bcmd, benv) = gap_pair(notes, 'g2', shadow_webview=True)
    after = run_wrapper(acmd, ['--show'], env=aenv)
    before = run_wrapper(bcmd, ['--show'], capture=False, env=benv)
    alog, blog = default_log_for(acmd), default_log_for(bcmd)
    _m, btxt = wait_for(blog, 0, READY_RE, timeout=10.0)
    # What the PRE-FIX shell does with no pywebview, measured DIRECTLY (the
    # traceback is discarded under pythonw, so the wrapper could never see it).
    pre_shell = os.path.join(os.path.dirname(bcmd), 'sotto_webview.py')
    direct = subprocess.run([sys.executable, pre_shell, '--show'],
                            capture_output=True, text=True, errors='replace',
                            creationflags=CREATE_NO_WINDOW, env=benv,
                            timeout=60)
    checks = [
        ('AFTER: run.cmd REFUSES the launch (non-zero)',
         after['rc'] != 0, f"rc={after['rc']}"),
        ('AFTER: the refusal is rc 1 -- the status the app would exit with',
         after['rc'] == 1,
         f"rc={after['rc']} want=1 stdout={after['stdout'].strip()[:160]!r}"),
        ('AFTER: nothing was started (no shell line in this copy\'s log)',
         'shell=webview2' not in text_of(alog),
         f"log_bytes={size_of(alog)}"),
        ('BEFORE: the pre-fix wrapper answered 0 -- the failure AS SUCCESS',
         before['rc'] == 0, f"rc={before['rc']}"),
        ('BEFORE: the app started anyway (pre-fix shell logged its first line)',
         'shell=webview2' in btxt,
         [l for l in btxt.splitlines() if 'shell=webview2' in l][:1] or '(none)'),
        ('BEFORE: the PRE-FIX SHELL exits 1 with no pywebview (measured direct)',
         direct.returncode == 1,
         f"rc={direct.returncode} err_tail="
         f"{direct.stderr.strip().splitlines()[-1:] or ['']}"),
    ]
    return {'gap': 'G2 pywebview-absent', 'want': 'non-zero (1); before=0',
            'after': after, 'before': before, 'checks': checks,
            'direct_pre_fix_shell_rc': direct.returncode}


def _kill_log_pid(log: str) -> str:
    pid = _app_pid(log, timeout=3.0)
    if pid is None:
        return '(no pid in log)'
    rc, out = kill_by_pid(pid)
    return f'taskkill /PID {pid} /F -> rc={rc}'


def active_lines(text: str) -> list:
    """The non-REM, non-blank lines of a batch file.

    A needle quoted inside a COMMENT is not code: this lane's run.cmd quotes the
    REMOVED fallback line in a REM, so a plain substring test on the whole file
    would report the fix absent while it is present and the comment is only
    explaining it.
    """
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().upper().startswith('REM')]


def arm_gap_hang(notes) -> dict:
    """G3: an app that never comes up must report a HANG, not 0."""
    (acmd, aenv), (bcmd, benv) = gap_pair(notes, 'g3', hang_stub=True)
    after = run_wrapper(acmd, ['--show'], capture=False, env=aenv)
    alog, blog = default_log_for(acmd), default_log_for(bcmd)
    # The wrapper appends its HANG receipt right before it returns; wait for it
    # rather than racing the read.
    wait_for(alog, 0, re.compile(r'HANG rc=4'), timeout=5.0)
    atxt = text_of(alog)
    hang_note = _kill_log_pid(alog)
    before = run_wrapper(bcmd, ['--show'], capture=False, env=benv)
    # The stub is DETACHED, so its line is NOT in the log when the wrapper
    # returns: wait for it. (The first version of this arm read at once and saw
    # an empty log -- the BEFORE check went red for a read race, not a defect.)
    wait_for(blog, 0, re.compile(r'STAGING_LOADED'), timeout=10.0)
    btxt = text_of(blog)
    before_note = _kill_log_pid(blog)
    hang_line = [l for l in atxt.splitlines() if HANG_RE.search(l)][:1]
    checks = [
        ('AFTER: run.cmd reports a HANG -- rc 4, not 0',
         after['rc'] == 4, f"rc={after['rc']} want=4 ms={after['ms']}"),
        ('AFTER: the wrapper wrote its OWN HANG receipt to the run log',
         bool(hang_line), hang_line or '(no HANG receipt)'),
        ('AFTER: the app really had been started and never came up '
         '(STAGING_LOADED, no ready file, no PRELOAD_ACTIVE)',
         'STAGING_LOADED' in atxt and 'PRELOAD_ACTIVE' not in atxt,
         repr([l for l in atxt.splitlines() if 'STAGING_LOADED' in l][:1])),
        ('BEFORE: the pre-fix wrapper answered 0 for the SAME hang',
         before['rc'] == 0, f"rc={before['rc']}"),
        ('BEFORE: the same stub had been started and never came up',
         'STAGING_LOADED' in btxt,
         repr([l for l in btxt.splitlines() if 'STAGING_LOADED' in l][:1])
         or '(stub never logged)'),
    ]
    return {'gap': 'G3 hang', 'want': 'non-zero (4); before=0',
            'after': after, 'before': before, 'checks': checks,
            'killed': [hang_note, before_note]}


def arm_gap_console(notes) -> dict:
    """G4: with no pythonw.exe, run.cmd must refuse -- never fall back to a
    console interpreter."""
    (acmd, aenv), (bcmd, benv) = gap_pair(notes, 'g4', fake_pythonw=True)
    after = run_wrapper(acmd, ['--show'], env=aenv)
    before = run_wrapper(bcmd, ['--show'], capture=False, env=benv)
    atxt, btxt = text_of(acmd), text_of(bcmd)
    alog = default_log_for(acmd)
    checks = [
        ('AFTER: run.cmd exits 3 when pythonw.exe is absent',
         after['rc'] == 3,
         f"rc={after['rc']} want=3 ms={after['ms']}"),
        ('AFTER: it NAMES the refusal, so the owner is not left guessing',
         'no pythonw' in after['stdout'] and 'console' in after['stdout'],
         after['stdout'].strip().splitlines()[:2] or '(no output)'),
        ('AFTER: nothing was started (no shell line in this copy\'s log)',
         'shell=webview2' not in text_of(alog),
         f"log_bytes={size_of(alog)}"),
        ('AFTER: the fallback assignment is GONE from the wrapper under test '
         '(checked on the ACTIVE lines -- a REM quoting it does not count)',
         'set "PYW=%PYEXE%"' not in active_lines(atxt),
         'absent' if 'set "PYW=%PYEXE%"' not in active_lines(atxt)
         else 'STILL PRESENT as code'),
        ('BEFORE: the pre-fix wrapper still carries the console fallback',
         'if not exist "%PYW%" set "PYW=%PYEXE%"' in btxt,
         'present (the defect)' if 'if not exist "%PYW%" set "PYW=%PYEXE%"'
         in btxt else 'MISSING -- control is dead'),
        ('BEFORE: it proceeded past the missing pythonw and answered 0',
         before['rc'] == 0, f"rc={before['rc']}"),
    ]
    return {'gap': 'G4 console-fallback', 'want': 'non-zero (3); before=0',
            'after': after, 'before': before, 'checks': checks}


def print_gaps(gaps) -> None:
    for g in gaps:
        ok = all(c[1] for c in g['checks'])
        print(f'GAP {g["gap"]:<22} {"PASS" if ok else "FAIL"} want={g["want"]}')
        for side in ('after', 'before'):
            r = g[side]
            print(f'  {side:<6} rc={r["rc"]} ms={r["ms"]} args={r["args"]}')
        for name, cok, ev in g['checks']:
            print(f'    [{"ok" if cok else "NO"}] {name} :: {ev}')


# --------------------------------------------------------------------------
# the MUTANT of the G3 contract, with its CONTROL at its side
# --------------------------------------------------------------------------

def check_of(arm: dict, needle: str):
    """(ok, evidence) do check cujo nome contem `needle`.

    (None, ...) quando nao existe tal check: um check que desapareceu tem de
    ser um VERMELHO nomeado, nunca um verde silencioso.
    """
    for name, ok, ev in arm.get('checks', []):
        if needle in name:
            return ok, ev
    return None, f'(no check in this arm mentions {needle!r})'


def arm_mutant(notes, pr, census) -> dict:
    """O MUTANTE do contrato G3, com o CONTROLE ao lado.

    A PERGUNTA que o check novo tem de responder: "um wrapper que voltou
    quando a app JA TINHA MORRIDO conta como pronto?". A resposta tem de ser
    NAO.

    O CONTROLE e' a MESMA app de mentira com a OUTRA polaridade: ela fica
    PRONTA e CONTINUA VIVA, e o wrapper tem de voltar com a app viva. Se o
    controle for vermelho, o instrumento esta partido e o mutante nao prova
    nada -- o mesmo principio do ramo `--neg-arm`: um mutante que nao pode
    ficar verde nao e' evidencia.

    O wrapper e' o de VERDADE (byte a byte) numa COPIA da arvore; so a shell e'
    o stub. O stub e' Python puro: sem WebView2, sem modelo, sem janela -- o
    custo sao alguns segundos e o PC do dono nao sente nada.
    """
    # ---- o CONTROLE: a app fica pronta e CONTINUA VIVA ----------------------
    ccmd, cenv = build_tree(notes, 'mutant-control', stub_text=MUTANT_STUB)
    clog = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(ccmd))),
                        '_main', 'mutant-control.log')
    control = arm_start(ccmd, pr, census, notes, 'mutant-control', clog,
                        ['--log', clog, '--stub-life', '2.0',
                         '--stub-alive-after', '3.0'], 8.0, env=cenv)
    # ---- o MUTANTE: a app so fica pronta quando JA MORREU ------------------
    mcmd, menv = build_tree(notes, 'mutant-ready-at-death',
                            stub_text=MUTANT_STUB,
                            env_extra={'SOTTO_STUB_READY_AFTER_DEATH': '1'})
    mlog = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(mcmd))),
                        '_main', 'mutant-ready-at-death.log')
    mutant = arm_start(mcmd, pr, census, notes, 'mutant-ready-at-death', mlog,
                       ['--log', mlog, '--stub-life', '2.0',
                        '--stub-alive-after', '0'], 8.0, env=menv)
    c_alive, c_alive_ev = check_of(control, 'STILL RUNNING when the wrapper returned')
    c_margin, c_margin_ev = check_of(control, 'the wrapper returned BEFORE the app exited')
    m_alive, m_alive_ev = check_of(mutant, 'STILL RUNNING when the wrapper returned')
    m_margin, m_margin_ev = check_of(mutant, 'the wrapper returned BEFORE the app exited')
    checks = [
        ('CONTROL: the wrapper returned while the app was STILL ALIVE (the '
         'instrument is not always-red)',
         c_alive is True, c_alive_ev),
        ('CONTROL: the margin is positive (the wrapper returned before the app '
         'exited)',
         c_margin is True, c_margin_ev),
        ('MUTANT: the wrapper returned with the app DEAD -> the check says NO',
         m_alive is False, m_alive_ev),
        ('MUTANT: the margin is not positive -> the check says NO',
         m_margin is False, m_margin_ev),
    ]
    return {'name': 'mutant-ready-at-death', 'checks': checks,
            'control': control, 'mutant': mutant}


def print_mutant(m: dict) -> None:
    ok = all(c[1] for c in m['checks'])
    print(f'MUTANT {m["name"]:<22} {"PASS" if ok else "FAIL"} '
          f'(the CONTROL green AND the MUTANT red on the two new checks)')
    for name, cok, ev in m['checks']:
        print(f'    [{"ok" if cok else "NO"}] {name} :: {ev}')
    for side in ('control', 'mutant'):
        r = m[side]
        print(f'  {side:<8} rc={r["rc"]} ms={r["ms"]} pid={r.get("pid")} '
              f'log={os.path.basename(r.get("log", ""))}')


# --------------------------------------------------------------------------
# the negative arm: revert the wrapper in a COPY
# --------------------------------------------------------------------------
def build_reverted_copy(neg_src: str, notes: list) -> str:
    """A copy of the tree whose ONLY difference is the wrapper.

    Every other file is the one under test, so an arm that goes RED in the copy
    went red because of the reverted wrapper and nothing else -- which is the
    whole point of a negative control. The bytes of run.cmd are copied
    verbatim (no re-encode), and a control that has stopped being a control is
    REFUSED rather than run.
    """
    if not os.path.exists(neg_src):
        raise SystemExit(f'NEGATIVE ARM: --neg-src {neg_src} does not exist')
    reverted = text_of(neg_src)
    fixed = text_of(RUN_CMD)
    if PREFLIGHT_MARK in reverted:
        raise SystemExit(f'NEGATIVE ARM: CONTROL DEAD -- {neg_src} already '
                         f'contains {PREFLIGHT_MARK}; it is not the pre-fix '
                         f'wrapper, so its arm 1 could not go RED')
    if reverted == fixed:
        raise SystemExit('NEGATIVE ARM: CONTROL DEAD -- the copy would be '
                         'byte-identical to the wrapper under test')
    root = tempfile.mkdtemp(prefix='sotto-runcmd-neg-')
    web = os.path.join(root, 'app', 'webview')
    elec = os.path.join(root, 'app', 'panel')
    for d in (web, elec, os.path.join(root, '_main')):
        os.makedirs(d, exist_ok=True)
    # Same IMPORT-CLOSURE rule as build_tree (see its comment): copy every
    # `.py` sibling, not a hand-listed trio. The trio missed `panel_state.py`
    # (sotto_webview.py:54), so the reverted copy's shell died at import with
    # rc 1 and arms 3/4 read "the app's OWN first line is in the run log :: (no
    # shell=webview2 ... pid= line)" -- the CONTROL failed for a reason that
    # has nothing to do with the wrapper it reverts. Measured 2026-10-07.
    src_web = os.path.join(SOTTO, 'app', 'webview')
    for name in sorted(os.listdir(src_web)):
        if name.endswith('.py') or name == 'stage.html':
            shutil.copy2(os.path.join(src_web, name), os.path.join(web, name))
    for name in ('panel.html', 'panel.css', 'panel.js', 'caption-formulation.js'):
        shutil.copy2(os.path.join(SOTTO, 'app', 'panel', name),
                     os.path.join(elec, name))
    shutil.copyfile(neg_src, os.path.join(web, 'run.cmd'))
    notes.append(f'copy={root}')
    notes.append(f'copy_run_cmd_sha256={sha256(os.path.join(web, "run.cmd"))}')
    notes.append(f'neg_src={neg_src}')
    notes.append(f'neg_src_sha256={sha256(neg_src)}')
    return os.path.join(web, 'run.cmd')


# --------------------------------------------------------------------------
def verdict_from(arms_ok, gaps_ok, census_ok, mutant_ok=True):
    """(exit_ok, why) for the WRAPPER's exit contract. PURE: no I/O, no state.

    AUDIT ROWS #30 / #C: this oracle prints THREE verdicts because they are three different claims,
    and then used to AND them into one exit code -- so a VISIBLE window measured by the census (an
    APP-side fact, which AGENTS.md says must never be read as "the wrapper failed") turned this
    wrapper test RED. The receipt run-cmd-exit-oracle-after.json records exactly that:
    verdict FAIL, reason "a VISIBLE window was measured (app-side...)".

    The exit code now carries what this oracle exists to test: the wrapper's own exit contract
    (arms + gaps). The census stays a REPORTED result with its own word, its own line and its own
    key in the receipt -- and when it is RED the reason says so in capitals, because dropping it
    silently would be the opposite defect: a number that stops being reported.
    """
    contract_ok = bool(arms_ok) and bool(gaps_ok) and bool(mutant_ok)
    why = ("the wrapper's exit contract is GREEN" if contract_ok else
           "arms=" + ("PASS" if arms_ok else "FAIL") +
           " gaps=" + ("PASS" if gaps_ok else "FAIL") +
           " mutant=" + ("PASS" if mutant_ok else "FAIL") +
           " -> the arms/gaps/mutant failed (see the [NO] lines above)")
    if not census_ok:
        why += (" | NOTE, NOT carried by this exit code: this run ALSO measured a VISIBLE window"
                " (app-side, rows #4/#46) -- see CENSUS-VERDICT above")
    return contract_ok, why

def self_test(pr) -> int:
    """Prova que o filtro de "sobrou algum processo nosso" tem DENTES e nao
    dispara em falso.

    MEDIDO 2026-10-19: o filtro original (arvore por parent-pid) acusou um
    `LuaTools.exe` de dois dias antes, cujo ParentProcessId guardado coincidia
    com o pid do oraculo. A correccao filtra por LINHA DE COMANDO e por HORA DE
    CRIACAO -- mas um filtro que nunca dispara tambem e' um filtro que nao prova
    nada, e um filtro que dispara sempre e' um filtro que acusa o dono.

    Este self-test cria DOIS filhos REAIS do oraculo:
      * um cuja linha de comando nomeia `sotto_webview.py`  -> tem de ser NOSSO;
      * um com uma linha de comando neutra                   -> tem de ser ALHEIO.

    Se qualquer um dos dois for classificado ao contrario, o self-test falha.
    E' um oraculo sobre o proprio oraculo -- que e' a unica forma de provar
    que a correccao nao estragou o check.
    """
    sleepy = 'import time; time.sleep(30)'
    ours = subprocess.Popen([sys.executable, '-c', sleepy, 'sotto_webview.py'],
                             creationflags=CREATE_NO_WINDOW)
    theirs = subprocess.Popen([sys.executable, '-c', sleepy, 'unrelated-thing.py'],
                               creationflags=CREATE_NO_WINDOW)
    try:
        time.sleep(1.5)
        found, ignored = leftover_of_ours(pr, os.getpid(), RUN_STARTED_ISO)
        ours_in = ours.pid in found
        theirs_in = theirs.pid in found
        theirs_listed = any(p == theirs.pid for p, _ in ignored)
    finally:
        for proc in (ours, theirs):
            try:
                proc.kill()
            except Exception:
                pass
    print('SELF-TEST o filtro de residuos:')
    print('  %-6s um filho com `sotto_webview.py` na linha de comando tem de ser '
          'NOSSO -> %s (pid %d)'
          % ('[ok]' if ours_in else '[NO]', ours_in, ours.pid))
    print('  %-6s um filho com linha de comando neutra tem de ser ALHEIO -> %s '
          '(pid %d)'
          % ('[ok]' if (not theirs_in and theirs_listed) else '[NO]',
             not theirs_in and theirs_listed, theirs.pid))
    ok = ours_in and not theirs_in and theirs_listed
    print('\nSELF-TEST %s -- o filtro distingue o nosso do alheio'
          % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description='Assert run.cmd\'s exit contract on both colours.')
    ap.add_argument('--run-cmd', default=RUN_CMD,
                    help='wrapper under test (default: the live app entry)')
    ap.add_argument('--label', default=None)
    ap.add_argument('--neg-arm', action='store_true',
                    help='revert the wrapper in a COPY and require arm 1 RED')
    ap.add_argument('--self-test', action='store_true',
                    help='prova que o filtro de "sobrou processo nosso" tem dentes '
                         'E nao dispara em falso (cria dois filhos reais)')
    ap.add_argument('--neg-src', default=NEG_SRC,
                    help='the pre-fix wrapper the copy is built from')
    ap.add_argument('--exit-after', type=float, default=8.0,
                    help='seconds each normal-start arm lets the app live')
    ap.add_argument('--cadence-ms', type=int, default=100)
    ap.add_argument('--json', default=None, help='receipt path')
    ap.add_argument('--no-gaps', action='store_true',
                    help='skip the G1..G4 before/after arms')
    # WHICH ARMS RUN (lane B, 2026-10-15). The battery must be able to gate this
    # wrapper's exit contract WITHOUT starting the app, because 'launches=0' is a
    # MEASURED property of the battery and not a hope (F5: only the Lead launches).
    # The four arms are NOT equal in what they start:
    #   argv   'run.cmd --check-args <set>' -- the pre-flight IS the action, so the
    #          wrapper returns the parser's status and starts NOTHING (live wrapper).
    #   bogus  'run.cmd --bogus-flag'      -- refused by the pre-flight, starts nothing.
    #   help   'run.cmd --help'            -- argparse answers and exits.
    #   start  'run.cmd [--log ...]'       -- THE APP IS LAUNCHED (both normal branches).
    # The DEFAULT is every arm, so a bare run is the behaviour this oracle always
    # had; selecting a subset is additive. '--arms bogus,help' is the launch-free
    # subset the battery registers, and it carries BOTH COLOURS: on the live wrapper
    # both arms are green, and on the pre-fix copy ('--neg-arm') arm 1 goes RED while
    # '--help' stays green, which is what makes it a control.
    ap.add_argument('--arms', default='argv,bogus,help,start',
                    help='comma subset of {argv,bogus,help,start} (default: all four)')
    # THE rc 120 DEFECT'S OWN CONTROL (lane B, 2026-10-15). The refusal capture used
    # to be redirected into the SYSTEM %TEMP%; MEASURED 2026-10-14, the same command
    # with the same interpreter answered rc 120 (and refused a GOOD launch) with
    # `2>G:\Temp\...` and rc 2 with the argparse text on a writable path. This flag
    # restores exactly that target in a COPY and requires the check to go RED.
    ap.add_argument('--temp-arm', action='store_true',
                    help='restore the %%TEMP%% capture target in a COPY -> must go RED')
    a = ap.parse_args()

    if a.temp_arm:
        return temp_arm(a.label or 'temp-arm')

    if a.self_test:
        # LANCA-NADA: o self-test cria dois filhos `python -c ...` e NEM
        # LANCA O APP. E' o unico ramo deste oraculo que nao toca no produto.
        return self_test(load_census_primitives())

    notes: list = []
    label = a.label or ('neg-arm' if a.neg_arm else 'fixed')
    run_cmd = os.path.abspath(a.run_cmd)
    if a.neg_arm:
        run_cmd = build_reverted_copy(a.neg_src, notes)
    if not os.path.exists(run_cmd):
        print(f'VERDICT FAIL  wrapper not found: {run_cmd}')
        return 1

    pr = load_census_primitives()
    census = Census(os.getpid(), pr, a.cadence_ms / 1000.0)
    census.start()

    print(f'RUN-CMD EXIT ORACLE label={label} pid={os.getpid()}')
    print(f'RUN-CMD run_cmd={run_cmd}')
    print(f'RUN-CMD run_cmd_sha256={sha256(run_cmd)}')
    print(f'RUN-CMD under_test_sha256={sha256(RUN_CMD)}'
          f' (the live wrapper; equal means "the fix is under test")')
    for n in notes:
        print(f'RUN-CMD {n}')
    print(f'RUN-CMD preflight_in_under_test='
          f'{PREFLIGHT_MARK in text_of(run_cmd)}')
    # The census conjunct is about the APP, not the wrapper, so the APP's own
    # bytes are pinned here too: a census RED that cannot name the shell it
    # measured is an accusation nobody can refute.
    shell = os.path.join(os.path.dirname(run_cmd), 'sotto_webview.py')
    print(f'RUN-CMD shell_sha256={sha256(shell) if os.path.exists(shell) else "(absent)"}'
          f' shell_mtime={int(os.path.getmtime(shell)) if os.path.exists(shell) else 0}')

    shared_log = default_log_for(run_cmd)
    arm_log = os.path.join(os.path.dirname(shared_log),
                           f'run-cmd-exit-oracle-{label}-{RUN_ID}.log')

    # THE ARM SELECTION (see --arms above). An unknown name is a REFUSAL, not
    # a silent skip: a typo that dropped arm 1 would turn the negative arm vacuous,
    # and this oracle's whole value is that it can say no.
    want = [n.strip() for n in str(a.arms).split(',') if n.strip()]
    ARM_NAMES = ('argv', 'bogus', 'help', 'start')
    unknown = sorted(set(want) - set(ARM_NAMES))
    if unknown:
        print(f'VERDICT FAIL  --arms names arm(s) that do not exist: {unknown} '
              f'(known: {", ".join(ARM_NAMES)})')
        return 1
    if not want:
        print('VERDICT FAIL  --arms selected no arm at all')
        return 1
    if a.neg_arm and 'bogus' not in want:
        print('NEG-ARM REFUSED: the control is arm 1 (bogus). Without it the run '
              'cannot go RED, so it is not a negative arm.')
        return 1
    print(f'ARM-SELECT {",".join(want)}'
          + ('   (LAUNCH-FREE: nothing below reaches the launch path)'
             if 'start' not in want else '   (the start arms LAUNCH the app)'))

    arms = []
    if 'argv' in want:
        arms.append(arm_argv(run_cmd, pr, census, notes))
        _print_arm(arms[-1])
    if 'bogus' in want:
        arms.append(arm_bogus(run_cmd, pr, census, notes))
        _print_arm(arms[-1])
    if 'help' in want:
        arms.append(arm_help(run_cmd, pr, census, notes))
        _print_arm(arms[-1])
    if 'start' in want:
        arms.append(arm_start(run_cmd, pr, census, notes, 'start-logged', arm_log,
                              ['--log', arm_log, '--no-hotkey', '--no-hot-reload',
                               '--exit-after', a.exit_after], a.exit_after))
        _print_arm(arms[-1])
        arms.append(arm_start(run_cmd, pr, census, notes, 'start-default', shared_log,
                              ['--no-hotkey', '--no-hot-reload',
                               '--exit-after', a.exit_after], a.exit_after))
        _print_arm(arms[-1])

    # THE rc 120 CONTRACT, statically (see temp_arm above). SKIPPED in the neg-arm
    # run, and the reason is a fact about the control and not a convenience: the
    # pre-fix wrapper predates the pre-flight entirely, so it has no capture to aim
    # anywhere and cannot control for this cure. The defect has its OWN control,
    # `--temp-arm`, which restores the %TEMP% target in a copy.
    temp_checks: list = []
    if not a.neg_arm:
        temp_checks = temp_target_checks(run_cmd)
        print('ARM temp-target   (the refusal capture is not aimed at the system %TEMP%)')
        for name, ok, ev in temp_checks:
            print(f'    [{"ok" if ok else "NO"}] {name} :: {ev}')
    else:
        print('ARM temp-target   SKIPPED in the neg-arm copy: the pre-fix wrapper has no'
              ' pre-flight and no capture, so it cannot control for this cure (the rc 120'
              ' defect is gated by --temp-arm instead)')

    # The ARMS are done. The census so far is the app-under-the-FIXED-wrapper's
    # own window behaviour, so snapshot it HERE, before the gap arms
    # deliberately run DEFECTIVE copies (G4's BEFORE starts the app under a
    # console interpreter; a console window there is the defect working).
    time.sleep(0.5)
    snap_arms = census.snapshot()
    census.reset_counters()

    # ---- the four gap arms (each with a BEFORE, in a pre-fix copy) ---------
    gaps: list = []
    if not a.no_gaps:
        print('GAPS the before/after pairs of docs/audit/launch-entry.md §2 '
              '(BEFORE = a copy whose shell+wrapper are the pre-fix bytes)')
        for fn in (arm_gap_panel, arm_gap_pywebview, arm_gap_hang,
                   arm_gap_console):
            g = fn(notes)
            gaps.append(g)
            print_gaps([g])

    # ---- o MUTANTE do contrato G3, com o CONTROLE ao lado ------------------
    # O mutante e' o que da DENTES aos checks novos: sem ele, "a app estava
    # VIVA quando o wrapper voltou" e' um check que nunca foi posto a
    # falhar. O CONTROLE (a app fica pronta e VIVA) garante que o
    # instrumento nao e' sempre-vermelho -- um mutante que nao pode ficar
    # verde nao e' evidencia.
    mutants: list = []
    if not a.no_gaps:
        print('MUTANT the G3 contract, with its control: the CONTROL app gets '
              'ready and STAYS ALIVE; the MUTANT app only gets ready once it '
              'is DEAD')
        m = arm_mutant(notes, pr, census)
        mutants.append(m)
        print_mutant(m)

    time.sleep(0.5)
    snap_gaps = census.snapshot()
    census.stop()

    print(f'CENSUS cadence_ms={a.cadence_ms} samples={snap_arms["samples"]} '
          f'visible_samples={snap_arms["visible_samples"]} '
          f'tracked_pids={len(snap_arms["tracked"])}')
    for key, row in snap_arms['hits'].items():
        print(f'CENSUS ALERTA-JANELA {key} pid={row["pid"]} hwnd={row["hwnd"]} '
              f'title={row["title"]!r} class={row["class"]!r} n={row["n"]}')
    census_ok = snap_arms['visible_samples'] == 0 and snap_arms['samples'] > 0
    print(f'CENSUS-GAPS samples={snap_gaps["samples"]} '
          f'visible_samples={snap_gaps["visible_samples"]} '
          f'(the gap phase, where a window is the DEFECT being demonstrated)')
    for key, row in snap_gaps['hits'].items():
        print(f'CENSUS-GAPS ALERTA-JANELA {key} pid={row["pid"]} '
              f'hwnd={row["hwnd"]} title={row["title"]!r} '
              f'class={row["class"]!r} n={row["n"]}')
    if snap_gaps['visible_samples']:
        print('CENSUS-GAPS NOTE: a window in THIS phase is the G4 BEFORE arm '
              'working -- it starts the app under a CONSOLE interpreter, and '
              'the console window is exactly the defect G4 removes. The AFTER '
              'arms must show none.')

    results = {arm['name']: arm for arm in arms}
    failed = [n for n, arm in results.items()
              if not all(ok for _nm, ok, _ev in arm['checks'])]
    failed += [c[0] for c in temp_checks if not c[1]]
    if census_ok:
        print(f'CENSUS OK: no visible window in {snap_arms["samples"]} samples '
              f'of this run\'s own pids during the ARMS phase (the census '
              f'primitives are the repo\'s)')
    else:
        print(f'CENSUS RED: {snap_arms["visible_samples"]} of '
              f'{snap_arms["samples"]} samples had a VISIBLE window in this '
              f'run\'s tree during the ARMS phase')

    # The two conjuncts are reported SEPARATELY, and the verdict names the one
    # that failed. They fail for different reasons and a reader must never take
    # one for the other: the arms are this wrapper's exit contract, while a
    # census RED is the APP putting its panel on the screen for ~1 sample
    # (measured 2026-10-06: 2 of 5 starts, ~50 ms, at +0.8 s after the app's
    # first line -- an app-side startup race, not a wrapper behaviour).
    if a.neg_arm:
        fired = 'bogus' in failed
        others_ok = not [n for n in failed if n != 'bogus']
        arms_ok = fired and others_ok
        arms_reason = (f'arm1(bogus) RED-as-expected={fired} '
                       f'arms2-4-still-green={others_ok} '
                       f'failed={sorted(failed)}')
    else:
        arms_ok = not failed
        arms_reason = (f'all {len(arms)} arm(s) green' if arms_ok
                       else f'failed arms={sorted(failed)}')

    census_reason = (f'{snap_arms["samples"]} samples, '
                     f'{snap_arms["visible_samples"]} with a visible window')
    gaps_failed = [g['gap'] for g in gaps
                   if not all(c[1] for c in g['checks'])]
    gaps_ok = not gaps_failed
    gaps_reason = ('all 4 gaps green (AFTER non-zero, BEFORE 0)' if gaps_ok
                   else f'failed gaps={gaps_failed}')
    mutants_failed = [m['name'] for m in mutants
                      if not all(c[1] for c in m['checks'])]
    mutant_ok = not mutants_failed
    mutant_reason = ('the MUTANT is red on the two new checks and the CONTROL '
                     'is green' if mutant_ok
                     else f'failed mutants={mutants_failed}')
    print(f'ARM-VERDICT    {"PASS" if arms_ok else "FAIL"}  {arms_reason}')
    if a.neg_arm and PREFLIGHT_MARK not in text_of(run_cmd):
        print('ARM-NOTE       the argv arm is VACUOUS in this copy: the pre-fix '
              'wrapper has no pre-flight, so no argv set can be refused by it '
              '(that is what the fix adds). Only arm 1 carries the signal here.')
    if gaps:
        print(f'GAP-VERDICT    {"PASS" if gaps_ok else "FAIL"}  {gaps_reason}')
    if mutants:
        print(f'MUTANT-VERDICT {"PASS" if mutant_ok else "FAIL"}  {mutant_reason}')
    print(f'CENSUS-VERDICT {"PASS" if census_ok else "FAIL"}  {census_reason}')
    # ONLY THE ARMS THAT RAN. The literal tuple this used to print indexed
    # results[n], which KeyERRORED the moment a subset was selected -- a
    # launch-free battery row would have crashed instead of reporting. This is
    # the crash the first version of the --arms patch produced, caught by running it.
    print('ARM-RCS ' + ' '.join(
        f'{arm["name"]}={arm["rc"]}(want {arm["expect_rc"]})' for arm in arms))
    for g in gaps:
        print(f'GAP-RCS {g["gap"]:<22} after={g["after"]["rc"]} '
              f'before={g["before"]["rc"]}')
    verdict_ok, why = verdict_from(arms_ok, gaps_ok, census_ok, mutant_ok)
    print(f'VERDICT {"PASS" if verdict_ok else "FAIL"}  {why}')
    print('VERDICT-CARRIES the wrapper exit contract (arms+gaps+mutant). The census is reported above'
          ' and is NOT part of this exit code: a visible window is an APP-side fact (rows'
          ' #4/#46), and reading it as "the wrapper failed" is the confusion this oracle was'
          ' indicted for.')

    receipt_path = a.json or os.path.join(
        HERE, f'run-cmd-exit-oracle-{label}.json')
    with open(receipt_path, 'w', encoding='utf-8') as f:
        json.dump({'label': label, 'run_cmd': run_cmd,
                   'run_cmd_sha256': sha256(run_cmd),
                   'under_test_sha256': sha256(RUN_CMD),
                   'preflight_in_under_test': PREFLIGHT_MARK in text_of(run_cmd),
                   'notes': notes, 'arms': arms, 'gaps': gaps,
                   'mutants': mutants,
                   'temp_target': temp_checks,
                   'census': snap_arms, 'census_gaps': snap_gaps,
                   'arms_ok': arms_ok, 'gaps_ok': gaps_ok, 'census_ok': census_ok,
                   'mutant_ok': mutant_ok,
                   'arm_verdict': 'PASS' if arms_ok else 'FAIL',
                   'gap_verdict': 'PASS' if gaps_ok else 'FAIL',
                   'mutant_verdict': 'PASS' if mutant_ok else 'FAIL',
                   'census_verdict': 'PASS' if census_ok else 'FAIL',
                   'verdict': 'PASS' if verdict_ok else 'FAIL',
                   'verdict_carries': 'arms+gaps+mutant (the wrapper exit contract)',
                   'reason': why}, f, indent=2)
    print(f'RECEIPT {receipt_path}')
    return 0 if verdict_ok else 1


def _print_arm(arm: dict) -> None:
    ok = all(c[1] for c in arm['checks'])
    head = (f'ARM {arm["name"]:<13} rc={arm["rc"]} '
            f'want={arm["expect_rc"]} ms={arm["ms"]} '
            f'{"PASS" if ok else "FAIL"}')
    if arm.get('pid'):
        head += f' pid={arm["pid"]}'
    print(head)
    for name, cok, ev in arm['checks']:
        print(f'    [{"ok" if cok else "NO"}] {name} :: {ev}')


if __name__ == '__main__':
    sys.exit(main())
