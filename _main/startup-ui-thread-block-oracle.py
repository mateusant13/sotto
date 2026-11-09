"""startup-ui-thread-block-oracle.py -- o DISCO nunca corre na thread da janela.

NASCIDO DE UM HANG MEDIDO (2026-11-08 18:57, pid 9628). O dono tem o autostart
numa tarefa (`\\Sotto`); `run.cmd` espera o ficheiro de prontidao e publica
`HANG rc=4` quando ele nao aparece. Aquela largada deu HANG -- e o dump que a
propria app tira (`_main/_startup-stacks.log`) mostrou a thread da UI presa:

    os.makedirs <- batch_queue.py:218 <- load_shedding.py:1093
    <- _start_slow_read_monitor <- _start_ui_watchdog <- _on_before_show
    <- webview/platforms/winforms.py:775 create

`_on_before_show` roda DENTRO do `create` do pywebview: e' a thread que mapeia a
janela. Construir a fila do batch ali (que faz `os.makedirs` e varre o
directorio) nao atrasa um widget -- IMPEDE a app de subir. A cura move esse
trabalho para uma thread propria e o que este oraculo julga e' isso mesmo:

  A1 a CHAMADA volta depressa (a UI nao espera o disco)
  A2 o trabalho ACONTECE (a accao e a fila ficam abertas, e o log diz)
  A3 uma segunda chamada nao abre uma segunda fila
  A4 sem `SOTTO_LOAD_SHED=0` nao ha fila nenhuma (o interruptor continua a valer)

O `--neg-arm` repoe a forma ANTIGA no texto do ficheiro (chamada directa, sem
thread) e exige A1 vermelha -- e mata a thread com a forma NOVA e exige A2
vermelha. Um oraculo que nao pode falhar nao e' um oraculo.

Como corre: `python _main/startup-ui-thread-block-oracle.py [--neg-arm]`.
Exits 0 com `VERDICT: PASS`, 1 quando apanha o defeito (a convencao da casa: o
`--neg-arm` devolve 1 QUANDO APANHA).
"""

from __future__ import annotations

import ast
import io
import os
import sys
import textwrap
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')

OPEN_SLEEP_S = 0.40          # o "disco" falso: a abertura da fila custa isto
CALL_BUDGET_S = 0.15         # a UI nao pode esperar mais do que isto


def read(path):
    with io.open(path, encoding='utf-8', newline='') as f:
        return f.read()


def methods_of(source_text, names):
    """Os METHOD nodes REAIS, por nome (nunca uma copia mantida aqui)."""
    tree = ast.parse(source_text)
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            found[node.name] = node
    missing = [n for n in names if n not in found]
    return found, missing


def build_harness(source_text, names):
    """Compila as funcoes reais numa classe falsa, com os fakes do mundo.

    Copiar o corpo para o oraculo seria julgar uma copia. Aqui o texto vem do
    FICHEIRO que embarca, e so' o `self` e' falso.
    """
    nodes, missing = methods_of(source_text, names)
    if missing:
        return None, missing, [], []
    lines = []
    for name in names:
        seg = ast.get_source_segment(source_text, nodes[name])
        if not seg:
            return None, [name + ' (sem segmento de codigo)'], []
        lines.append(textwrap.indent(textwrap.dedent(seg), '    '))
    src = 'class FakeShell:\n' + '\n'.join(lines) + '\n'

    calls = []
    logs = []

    class LoadSheddingMonitor:
        INTERVAL_S = 5.0

        def __init__(self, shell):
            self.shell = shell

    class Action:
        def as_dict(self):
            return {'armed': False, 'floor_s': 45.0, 'samples_required': 3,
                    'batch': {'queue': {'dir': 'H:/fake/queue'}}}

    class Shed:
        def open_action(self, shell, monitor=None, log_fn=None):
            calls.append(('open_action', time.monotonic()))
            time.sleep(OPEN_SLEEP_S)          # o `os.makedirs` medido
            return Action()

    ns = {
        'threading': threading,
        'time': time,
        'os': os,
        'log': lambda message: logs.append(message),
        'LoadSheddingMonitor': LoadSheddingMonitor,
        'load_shedding': lambda: Shed(),
        '__name__': 'sotto_webview_fake',
    }
    try:
        exec(compile(src, '<sotto_webview:extracted>', 'exec'), ns)
    except SyntaxError as exc:
        return None, ['SyntaxError: %r' % (exc,)], calls, logs
    FakeShell = ns['FakeShell']

    class Shell(FakeShell):
        _slow_read_thread = None
        external_caption_watcher = None

        def _start_thread_cpu_census(self, every_s=30.0):
            return None

        def _dump_thread_stacks(self, reason, force=False):
            return None

    return Shell(), [], calls, logs


def judge(shell, calls, logs, label):
    """Os quatro bracos. Devolve (ok, detalhe)."""
    lines = []

    # A1 -- a CHAMADA nao espera o disco.
    t0 = time.monotonic()
    shell._start_slow_read_monitor()
    took = time.monotonic() - t0
    a1 = took < CALL_BUDGET_S
    lines.append('A1 chamada=%.3fs budget=%.3fs %s'
                 % (took, CALL_BUDGET_S, 'ok' if a1 else 'RED (a UI esperou o disco)'))

    # A2 -- o trabalho ACONTECE (e o log diz).
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not calls:
        time.sleep(0.01)
    opened = bool(calls)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not getattr(shell, '_load_action', None):
        time.sleep(0.01)
    happened = bool(getattr(shell, '_load_action', None)) and any(
        str(m).startswith('LOAD_ACTION_STARTED') for m in logs)
    a2 = opened and happened
    lines.append('A2 open_action=%s load_action=%s LOAD_ACTION_STARTED=%s %s'
                 % (opened, bool(getattr(shell, '_load_action', None)),
                    any(str(m).startswith('LOAD_ACTION_STARTED') for m in logs),
                    'ok' if a2 else 'RED (o trabalho nunca aconteceu)'))

    # A3 -- uma segunda chamada nao abre uma segunda fila.
    before = len(calls)
    shell._start_slow_read_monitor()
    time.sleep(0.05)
    a3 = len(calls) == before
    lines.append('A3 chamadas antes=%d depois=%d %s'
                 % (before, len(calls), 'ok' if a3 else 'RED (fila duplicada)'))

    # A4 -- o interruptor continua a valer.
    old = os.environ.get('SOTTO_LOAD_SHED')
    os.environ['SOTTO_LOAD_SHED'] = '0'
    try:
        fresh, _missing, fresh_calls, _fresh_logs = build_harness(SOURCE, NAMES)
        fresh._start_slow_read_monitor()
        time.sleep(OPEN_SLEEP_S + 0.15)
        a4 = len(fresh_calls) == 0 and not getattr(fresh, '_load_action', None)
        lines.append('A4 SOTTO_LOAD_SHED=0 open_action=%d %s'
                     % (len(fresh_calls), 'ok' if a4 else 'RED (interruptor ignorado)'))
    finally:
        if old is None:
            os.environ.pop('SOTTO_LOAD_SHED', None)
        else:
            os.environ['SOTTO_LOAD_SHED'] = old

    ok = a1 and a2 and a3 and a4
    return ok, '%s | %s' % (label, ' | '.join(lines))


NAMES = ['_start_slow_read_monitor', '_open_load_action']
SOURCE = read(SHELL)


def run_positive():
    shell, missing, calls, logs = build_harness(SOURCE, NAMES)
    if shell is None:
        return False, 'nao consegui extrair as funcoes: %s' % (missing,)
    ok, detail = judge(shell, calls, logs, 'AS-SHIPPED')
    print(detail)
    return ok, detail


def run_neg_arm():
    """Duas mutacoes no TEXTO do ficheiro; cada uma tem de derrubar O SEU braco."""
    caught = []

    # M1 -- a forma ANTIGA: a chamada directa, sem thread.
    old = """            threading.Thread(target=self._open_load_action,
                             name='sotto-load-shed-start', daemon=True).start()"""
    new = """            self._open_load_action()"""
    if old in SOURCE:
        mutated = SOURCE.replace(old, new, 1)
        shell, missing, calls, logs = build_harness(mutated, NAMES)
        if shell is not None:
            ok, detail = judge(shell, calls, logs, 'M1-inline')
            if not ok:
                caught.append('M1 (a chamada directa volta a prender a UI): ' + detail)

    # M2 -- a thread existe e nunca arranca: o trabalho desaparece em silencio.
    new2 = """            _t = threading.Thread(target=self._open_load_action,
                                  name='sotto-load-shed-start', daemon=True)"""
    if old in SOURCE:
        mutated2 = SOURCE.replace(old, new2, 1)
        shell2, _m, calls2, logs2 = build_harness(mutated2, NAMES)
        if shell2 is not None:
            ok2, detail2 = judge(shell2, calls2, logs2, 'M2-never-started')
            if not ok2:
                caught.append('M2 (a thread nunca arranca): ' + detail2)

    for line in caught:
        print('CAUGHT ' + line)
    print('NEG-ARM: %s -- %d/2 mutantes apanhados'
          % ('PASS' if len(caught) == 2 else 'FAIL', len(caught)))
    return len(caught) == 2


def main(argv):
    if '--neg-arm' in argv:
        return 1 if run_neg_arm() else 0
    ok, _detail = run_positive()
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
