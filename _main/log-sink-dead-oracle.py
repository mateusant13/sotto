#!/usr/bin/env python
"""O RELATADOR NAO MORRE COM O CANO -- `log()` executa-se contra um stdout morto.

A CLASSE, e a RETRATACAO da historia que eu primeiro escrevi.

O que esta' MEDIDO: a instancia do dono (pid 42572, arrancada 04:01:44 local, fechada por ele
as 05:02:30 com `SHELL_EXIT rc=0 reason=tray-quit`) custava **100 % de um nucleo**, com o fio
`sotto-caption-tick` a **93,6 %** e depois a 78,5 % (`_main/shell-thread-cpu.py`, duas amostras) --
isso e' o stutter, e tem dono na lei do custo. Tambem medido: `Process.parent()` do shell e'
**None** (o largador sai por desenho).

O que eu PRIMEIRO escrevi aqui e esta' ERRADO: que o `log()` tinha morrido as 04:57:13 e que a app
ficou tres horas muda. O log tinha 04:57 como ultimo carimbo porque eu li a hora LOCAL como se
fosse UTC -- o processo vivo naquele instante, e o ficheiro continuou a crescer ate' 54 082 341 B
as 05:02. **Nao houve silencio nenhum**, logo nenhum `OSError 22` foi observado nesta instancia.
("o grep deu ZERO tem prazo de validade", e uma leitura de hora tambem.)

A CLASSE e' real e nao depende do incidente: `log()` fazia `print(line, flush=True)` sem guarda, e
um `print` num cano morto levanta. Esta casa JA' pagou isso do lado do WORKER (`emit` com cano
partido -> `BRIDGE_DEATH_CAUSE OSError 22`, passo `emit-pipe-dead`, 2026-11-04); do lado da shell
nao havia cura. O custo de a ter e' de duas linhas; o custo de nao a ter, quando o largador morre,
e' a app deixar de falar sem deixar de correr -- e doze instrumentos leem esse log para julgar
custo, legenda e hotkey.

O QUE ESTE ORACULO EXECUTA. O `log()` REAL de `app/webview/sotto_webview.py`,
importado, contra um `sys.stdout` que LEVANTA (o cano partido) e uma fila que
CONTA (o ficheiro). Nada de leitura de texto: um `grep` diria que o `try` existe
mesmo num caminho que nunca corre.

AS ARMS

  A1  stdout vivo -> a linha chega ao stdout e a fila do ficheiro recebe-a.
  A2  stdout MORTO (`OSError 22`) -> `log()` NAO levanta, e a linha AINDA chega a
      fila do ficheiro (o ficheiro e' o artefacto de aceitacao).
  A3  a deteccao e' UMA vez: duas chamadas com o cano morto tentam o `print` uma
      so' vez (o `print` num cano morto custa uma syscall falhada por linha, para
      sempre, num processo que escreve milhares de linhas por hora).
  A4  o facto e' DECLARADO no ficheiro: `LOG_STDOUT_DEAD` com a excepcao, uma vez.
  A5  `warn()` passa pelo mesmo caminho e tambem sobrevive (e' o que carrega o
      prefixo; uma cura so' no `log()` deixaria o `warn()` a matar).
  A6  stdout que levanta `AttributeError` (o caso do `pythonw` sem stdout) tem o
      mesmo tratamento: a classe da excepcao nao decide nada.

`--neg-arm` escreve uma COPIA do modulo com o `print` directo de volta (o estado
medido hoje) e exige A2, A3, A4 e A5 vermelhas. O codigo de "apanhado" e' 1.
"""
import argparse
import io
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')


def _shell_module(path=None):
    """THE REAL module, imported once. `path` lets the neg-arm load a COPY."""
    real = os.path.dirname(SHELL)
    if real not in sys.path:
        sys.path.insert(0, real)            # os irmaos (`hot_reload`, `youtube_window`)
    directory = os.path.dirname(path or SHELL)
    # APPEND: a copia mutante vive num tmp sem os irmaos, e o nome dela e' unico
    sys.path.append(directory)
    name = 'sotto_webview' if path is None else 'sotto_webview_mutant_log'
    return __import__(name)


class DeadPipe(object):
    """Um stdout cujo consumidor morreu -- o que o dono tinha as 04:57."""

    def __init__(self, exc_factory=None):
        self.writes = 0
        self.exc_factory = exc_factory or (lambda: OSError(22, 'Invalid argument'))

    def write(self, _text):
        self.writes += 1
        raise self.exc_factory()

    def flush(self):
        raise self.exc_factory()


class LivePipe(object):
    def __init__(self):
        self.buf = []

    def write(self, text):
        self.buf.append(text)

    def flush(self):
        pass


class FileQueue(object):
    """A fila do ficheiro: conta as linhas que o escritor receberia."""

    def __init__(self):
        self.lines = []

    def put(self, line):
        self.lines.append(line)


class Arm(object):
    def __init__(self, module):
        self.module = module

    def reset(self, stdout):
        self.module._STDOUT_SINK['dead'] = False
        self.module._STDOUT_SINK['err'] = ''
        self.module._LOG_FILE = object()          # ha' espelho
        self.queue = FileQueue()
        self.module._LOG_QUEUE = self.queue
        self.saved = sys.stdout
        sys.stdout = stdout
        return stdout

    def restore(self):
        sys.stdout = self.saved


def _drain(module, timeout=2.0):
    """Espera o fio do stdout escoar a fila (2026-11-09).

    O `log()` deixou de escrever no stdout no fio do chamador: a linha vai para
    `_STDOUT_QUEUE` e um fio unico a escreve (`sotto-stdout`), porque um cano
    lento parava o `_pump` do worker e o cao de guarda matava um worker vivo
    (medido: `BRIDGE_SILENT` + `age_ms=39657` + `BRIDGE_LOAD_MS ms=61781`). As
    arms deste oraculo perguntam pelo EFEITO (`print` tentado, marcador no
    ficheiro), logo tem de esperar o fio -- sem isto mediam a fila, nao o
    desfecho. Sem fio (mutante antigo) devolve imediatamente.
    """
    q = getattr(module, '_STDOUT_QUEUE', None)
    t0 = time.time()
    while q is not None and q.qsize() and (time.time() - t0) < timeout:
        time.sleep(0.005)
    time.sleep(0.02)


def _call(arm, text):
    """Uma chamada REAL, com a excepcao capturada como facto."""
    try:
        arm.module.log(text)
        return None
    except BaseException as exc:                  # noqa: BLE001
        return exc


def arm_a1(module):
    arm = Arm(module)
    live = arm.reset(LivePipe())
    try:
        err = _call(arm, 'A1 normal')
        _drain(module)
        out = ''.join(live.buf)
    finally:
        arm.restore()
    return (err is None and 'A1 normal' in out and len(arm.queue.lines) == 1,
            'err=%r stdout_tem=%r fila=%d' % (err, 'A1 normal' in out, len(arm.queue.lines)))


def arm_a2(module):
    arm = Arm(module)
    arm.reset(DeadPipe())
    try:
        err = _call(arm, 'A2 cano morto')
        _drain(module)
        lines = list(arm.queue.lines)
    finally:
        arm.restore()
    mirrored = any('A2 cano morto' in ln for ln in lines)
    return (err is None and mirrored, 'err=%r espelho=%r fila=%d' % (err, mirrored, len(lines)))


def arm_a3(module):
    arm = Arm(module)
    dead = arm.reset(DeadPipe())
    try:
        e1 = _call(arm, 'A3 um')
        e2 = _call(arm, 'A3 dois')
        _drain(module)
        tries = dead.writes
    finally:
        arm.restore()
    # UMA tentativa: o cano morto nao se re-tenta linha a linha, para sempre
    return (e1 is None and e2 is None and tries == 1,
            'err1=%r err2=%r tentativas=%d' % (e1, e2, tries))


def arm_a4(module):
    arm = Arm(module)
    arm.reset(DeadPipe())
    try:
        _call(arm, 'A4 primeiro')
        _call(arm, 'A4 segundo')
        _drain(module)
        markers = [ln for ln in arm.queue.lines if 'LOG_STDOUT_DEAD' in ln]
        other = [ln for ln in arm.queue.lines if 'A4 ' in ln]
    finally:
        arm.restore()
    # O facto vai para o ficheiro, uma vez, com a excepcao nomeada
    ok = (len(markers) == 1 and 'OSError' in markers[0] and len(other) == 2)
    return (ok, 'marcadores=%d outros=%d marcador=%r' % (len(markers), len(other),
                                                         markers[0][-70:] if markers else ''))


def arm_a5(module):
    arm = Arm(module)
    arm.reset(DeadPipe())
    try:
        try:
            module.warn('A5 aviso')
            err = None
        except BaseException as exc:              # noqa: BLE001
            err = exc
        lines = list(arm.queue.lines)
    finally:
        arm.restore()
    return (err is None and any('WARN A5 aviso' in ln for ln in lines),
            'err=%r fila=%d' % (err, len(lines)))


def arm_a6(module):
    arm = Arm(module)
    arm.reset(DeadPipe(lambda: AttributeError("'NoneType' object has no attribute 'write'")))
    try:
        err = _call(arm, 'A6 pythonw')
    finally:
        arm.restore()
    return (err is None, 'err=%r' % (err,))


ARMS = [
    ('A1 stdout vivo: linha ao stdout E ao ficheiro', arm_a1),
    ('A2 cano morto: log() NAO levanta e o ficheiro recebe', arm_a2),
    ('A3 a deteccao e UMA tentativa, nao uma por linha', arm_a3),
    ('A4 LOG_STDOUT_DEAD declarado no ficheiro, com a excepcao', arm_a4),
    ('A5 warn() sobrevive pelo mesmo caminho', arm_a5),
    ('A6 AttributeError (pythonw sem stdout) idem', arm_a6),
]


MUTANTS = [
    ('print-directo-de-volta', '''
def _write_stdout(line):
    print(line, flush=True)
'''),
    ('deteccao-sem-memoria', '''
def _write_stdout(line):
    try:
        print(line, flush=True)
    except Exception as exc:
        _STDOUT_SINK['dead'] = False
        _STDOUT_SINK['err'] = f'{type(exc).__name__}: {exc}'
'''),
    ('marcador-sem-o-facto', '''
def _write_stdout(line):
    if _STDOUT_SINK['dead']:
        return
    try:
        print(line, flush=True)
    except Exception as exc:
        _STDOUT_SINK['dead'] = True
        _STDOUT_SINK['err'] = f'{type(exc).__name__}: {exc}'
'''),
]


def _start_of(module_name):
    """(inicio, fim) do corpo de `_write_stdout` no FONTE, para a mutacao."""
    text = io.open(SHELL, encoding='utf-8', newline='').read()
    start = text.index('def _write_stdout(line: str) -> None:')
    end = text.index('def log(message: str) -> None:', start)
    return text, start, end


def run(module, label):
    ok = 0
    print(f'--- {label} ---')
    for name, fn in ARMS:
        try:
            good, detail = fn(module)
        except BaseException as exc:              # noqa: BLE001
            good, detail = False, 'excepcao no braco: %r' % (exc,)
        ok += 1 if good else 0
        print('%-52s %s   %s' % (name, 'PASS' if good else 'FAIL', detail))
    print('VERDICT: %s (%d/%d)' % ('PASS' if ok == len(ARMS) else 'FAIL', ok, len(ARMS)))
    return ok == len(ARMS)


def neg_arm(tmp):
    text, start, end = _start_of('log')
    caught = 0
    for label, body in MUTANTS:
        body_lines = body.rstrip('\n') + '\n\n\n'
        mutated = text[:start] + body_lines + text[end:]
        path = os.path.join(tmp, 'app', 'webview', 'sotto_webview_mutant_log.py')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(mutated)
        module = _shell_module(path)
        print(f'--- MUTANTE {label} ---')
        good = run(module, label)
        print('MUTANT %s %s' % (label, 'CAUGHT' if not good else 'NOT-CAUGHT'))
        caught += 0 if good else 1
    print('NEG-ARM check=%d/%d' % (caught, len(MUTANTS)))
    # A FRASE E' CONTRATO: o passo `red-as-expected-log-sink-dead` da' `:expectred`
    # com o texto `NEG-ARM: PASS` (com os dois pontos). Um `NEG-ARM PASS` sem eles e'
    # rc=1 com a frase ausente, que e' o passo vermelho por causa de um caractere.
    print('NEG-ARM: %s' % ('PASS' if caught == len(MUTANTS) else 'FAIL'))
    # CONVENCAO DA CASA: o braco negativo devolve 1 QUANDO APANHA -- e' o que o
    # `:expectred` da bateria exige. A primeira versao devolvia 0 e o passo
    # `red-as-expected-log-sink-dead` falhou na corrida completa com `=0`.
    return 1 if caught == len(MUTANTS) else 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--neg-arm', action='store_true')
    args = parser.parse_args(argv[1:])
    if args.neg_arm:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            return neg_arm(tmp)
    return 0 if run(_shell_module(), 'app/webview/sotto_webview.py (o ficheiro que embarca)') else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
