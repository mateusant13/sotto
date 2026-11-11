# NO-BUG: executa o contrato real e os nove bracos da morte diagnosticavel; nao impede a morte do worker nem o `OSError 22` que a causa.
"""O oraculo da MORTE DIAGNOSTICAVEL do worker (medido 2026-11-07).

O DEFEITO QUE ELE JULGA, medido no log do dono (`_main/webview-run.log`):

    BRIDGE_DEATH rc=1 deaths=6
    last="Worker error at unhandled - OSError: [Errno 22] Invalid argument"
    stderr_tail=["REDUX_ENGINE_YIELD ...", "REDUX_ENGINE_RELEASED ..."]   # 2 linhas

Seis mortes num dia, todas a MESMA frase, cada uma comprada com uma recarga do
modelo (`BRIDGE_LOAD_MS` 11703 / 27015 / 33860 / 37157 ms) -- e **nenhuma** com o
traceback. Duas causas, as duas neste par de funcoes:

1. O RELATOR LEVANTAVA. `contract_guard` apanhava a excepcao e chamava
   `err_fn("sotto: UNHANDLED ...")`, que escreve no `sys.stderr`; com o handle
   invalido esse `write` fazia `EINVAL` e a saida 4 (com significado) virava uma
   saida 1 sem frase.
2. A FRASE IA SO' PARA O CANAL QUE FALHA. Nao havia segundo sitio.

O que ele EXECUTA e' o codigo real (`worker/sotto_worker.py`,
`worker/engine_switch.py`) -- nunca uma copia da verdade. Os nove bracos:

  A1  excepcao em `main`                -> devolve 4 (nunca escapa)
  A2  o ficheiro do traceback existe e nomeia a excepcao + a frame
  A3  `emit_fn` morto (cano partido)    -> continua a devolver 4
  A4  `err_fn` morto (stderr EINVAL)    -> continua a devolver 4
  A5  `err()` do engine_switch nao levanta num stderr invalido
  A6  o tecto de 256 KB: cria e recicla, e o bloco NOVO sobrevive
  A7  `KeyboardInterrupt` -> 130 (a semantica antiga, intacta)
  A8  `SystemExit(2)` atravessa (o codigo de uso NAO e' achatado em 4)
  A9  um `main` limpo -> 0, e nada escrito no ficheiro

`--neg-arm` muta uma COPIA do worker (tira a chamada do ficheiro, tira o
try/except do `err_fn`) e uma copia do `engine_switch` (repoe o write cru) e
exige que os bracos que dependem de cada cura fiquem VERMELHOS. Um oraculo que
nao cai com a cura arrancada nao e' um portao.
"""
import argparse
import io
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, 'worker')


def _load_worker(path_dir=WORKER, name='sotto_worker'):
    """O modulo REAL. `worker/` no sys.path porque os irmaos vivem la'."""
    for entry in (path_dir, WORKER):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    return __import__(name)


class DeadPipe:
    """Um escrevedor que morre como o stderr com o handle invalido (EINVAL)."""

    def write(self, _text):
        raise OSError(22, 'Invalid argument')

    def flush(self):
        raise OSError(22, 'Invalid argument')


def _collector(sink):
    def emit(**payload):
        sink.append(payload)
    return emit


def run(module, label, tmpdir):
    trace = os.path.join(tmpdir, 'trace.log')
    os.environ['SOTTO_WORKER_TRACEBACK_LOG'] = trace
    if os.path.exists(trace):
        os.remove(trace)
    results = []

    def arm(name, ok, detail=''):
        results.append((name, bool(ok), detail))

    # ── A1/A2: a excepcao de verdade ────────────────────────────────────────
    def boom():
        raise OSError(22, 'Invalid argument')

    events = []
    try:
        rc = module.contract_guard(boom, emit_fn=_collector(events), err_fn=lambda _m: None)
    except BaseException:
        rc = 'ESCAPOU'
    arm('A1 devolve 4 e nao escapa', rc == 4, 'rc=%r' % (rc,))
    status = [e for e in events if e.get('stage') == 'unhandled']
    arm('A1b o painel recebe a frase', len(status) == 1, '%d status' % len(status))
    body = io.open(trace, encoding='utf-8', errors='replace').read() if os.path.exists(trace) else ''
    arm('A2 o ficheiro nomeia a excepcao', 'OSError: [Errno 22] Invalid argument' in body,
        '%d B' % len(body))
    arm('A2b o ficheiro tem a frame (nao so a frase)', 'Traceback (most recent call last)' in body
        and 'boom' in body, 'linhas=%d' % body.count('\n'))

    # ── A3: o cano do painel morto ──────────────────────────────────────────
    def dead_emit(**_payload):
        raise OSError(22, 'Invalid argument')

    def boom2():
        raise ValueError('x')

    try:
        rc = module.contract_guard(boom2, emit_fn=dead_emit, err_fn=lambda _m: None)
    except BaseException:
        rc = 'ESCAPOU'
    arm('A3 emit_fn morto -> 4', rc == 4, 'rc=%r' % (rc,))

    # ── A4: o stderr invalido (o defeito medido) ────────────────────────────
    def dead_err(_msg):
        raise OSError(22, 'Invalid argument')

    try:
        rc = module.contract_guard(boom2, emit_fn=_collector([]), err_fn=dead_err)
    except BaseException:
        rc = 'ESCAPOU'
    arm('A4 err_fn morto -> 4', rc == 4, 'rc=%r' % (rc,))

    # ── A5: o `err` do engine_switch ────────────────────────────────────────
    engine_switch = sys.modules.get('engine_switch')
    if engine_switch is None:
        arm('A5 engine_switch importa', False, 'sem modulo')
    else:
        real = sys.stderr
        sys.stderr = DeadPipe()
        try:
            engine_switch.err('frase de diagnostico')
            arm('A5 err() nao levanta num stderr morto', True)
        except BaseException as exc:
            arm('A5 err() nao levanta num stderr morto', False, repr(exc))
        finally:
            sys.stderr = real

    # ── A6: o tecto do ficheiro ─────────────────────────────────────────────
    os.remove(trace) if os.path.exists(trace) else None
    filler = 'L' * 4000
    for i in range(400):                       # ~1,6 MB, muito acima do tecto
        module._death_trace('%04d %s' % (i, filler))
    size = os.path.getsize(trace) if os.path.exists(trace) else 0
    newest = io.open(trace, encoding='utf-8', errors='replace').read()[-5000:]
    arm('A6 o ficheiro tem tecto', 0 < size <= module.TRACEBACK_LOG_MAX,
        '%d B (tecto %d)' % (size, module.TRACEBACK_LOG_MAX))
    arm('A6b o bloco NOVO sobrevive a reciclagem', '0399' in newest, 'tail=%r' % newest[-12:])

    # ── A7/A8: as semanticas antigas ────────────────────────────────────────
    def interrupted():
        raise KeyboardInterrupt()

    try:
        rc = module.contract_guard(interrupted, emit_fn=_collector([]), err_fn=lambda _m: None)
    except BaseException:
        rc = 'ESCAPOU'
    arm('A7 KeyboardInterrupt -> 130', rc == 130, 'rc=%r' % (rc,))

    def usage():
        raise SystemExit(2)

    try:
        rc = module.contract_guard(usage, emit_fn=_collector([]), err_fn=lambda _m: None)
    except SystemExit as stop:
        rc = stop.code
    arm('A8 SystemExit(2) atravessa', rc == 2, 'rc=%r' % (rc,))

    # ── A9: um main limpo nao escreve nada ──────────────────────────────────
    os.remove(trace) if os.path.exists(trace) else None
    rc = module.contract_guard(lambda: 0, emit_fn=_collector([]), err_fn=lambda _m: None)
    arm('A9 main limpo -> 0 e ficheiro vazio', rc == 0 and not os.path.exists(trace),
        'rc=%r ficheiro=%s' % (rc, os.path.exists(trace)))

    for name, ok, detail in results:
        print('  %s %-48s %s' % ('OK  ' if ok else 'FAIL', name, detail))
    bad = [r for r in results if not r[1]]
    return len(results) - len(bad), len(results)


def mutate_dev_arms(tmpdir, ok, total):
    """`--neg-arm`: tira cada cura a um, numa COPIA, e exige o vermelho."""
    worker_src = io.open(os.path.join(WORKER, 'sotto_worker.py'), encoding='utf-8').read()
    switch_src = io.open(os.path.join(WORKER, 'engine_switch.py'), encoding='utf-8').read()
    caught = 0
    cases = 0

    # M1: a chamada que guarda o traceback deixa de existir.
    m1 = worker_src.replace(
        '        _death_trace("UNHANDLED %s\\n%s" % (detail, _tb.format_exc()))\n', '', 1)
    # M2: o relator volta a poder levantar.
    m2 = worker_src.replace(
        "        try:\n            err_fn(\"sotto: UNHANDLED \" + detail)\n"
        "            err_fn(_tb.format_exc())\n"
        "        except BaseException:      # noqa: BLE001 - idem\n            pass\n",
        "        err_fn(\"sotto: UNHANDLED \" + detail)\n", 1)
    # M3: o `err()` volta ao write cru.
    m3 = switch_src.replace(
        "    try:\n        sys.stderr.write(msg + \"\\n\")\n"
        "        sys.stderr.flush()\n"
        "    except (OSError, ValueError, AttributeError):\n        pass\n",
        "    sys.stderr.write(msg + \"\\n\")\n    sys.stderr.flush()\n", 1)

    for tag, target, source, mutated in (('M1 sem ficheiro', 'sotto_worker.py', worker_src, m1),
                                         ('M2 relator que levanta', 'sotto_worker.py', worker_src, m2),
                                         ('M3 err() cru', 'engine_switch.py', switch_src, m3)):
        cases += 1
        if mutated == source:
            print('  ?    %s: a mutacao NAO pegou (ancora mudou)' % tag)
            continue
        case_dir = tempfile.mkdtemp(prefix='death-arm-', dir=tmpdir)
        io.open(os.path.join(case_dir, 'sotto_worker.py'), 'w', encoding='utf-8').write(worker_src)
        io.open(os.path.join(case_dir, 'engine_switch.py'), 'w', encoding='utf-8').write(switch_src)
        io.open(os.path.join(case_dir, target), 'w', encoding='utf-8').write(mutated)
        sys.path.insert(0, case_dir)
        try:
            for stale in ('sotto_worker', 'engine_switch'):
                sys.modules.pop(stale, None)
            module = __import__('sotto_worker')
            good, tot = run(module, tag, case_dir)
        except BaseException:
            print('  !    %s: a copia nao importou\n%s' % (tag, traceback.format_exc()))
            good, tot = 0, 1
        finally:
            try:
                sys.path.remove(case_dir)
            except ValueError:
                pass
        if good < tot:
            caught += 1
            print('  CAUGHT %s -- %d/%d' % (tag, good, tot))
        else:
            print('  MISS   %s -- %d/%d' % (tag, good, tot))
    print('NEG-ARM: %s -- %d/%d mutantes apanhados' %
          ('PASS' if caught == cases else 'FAIL', caught, cases))
    # A CONVENCAO DA CASA: o negativo devolve **1** quando APANHA os mutantes (o
    # passo da bateria declara `:expectred` e exige rc=1 + a frase). Devolver 0
    # aqui faria dele um oraculo normal que nunca recusa nada.
    return 1 if caught == cases else 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--neg-arm', action='store_true')
    args = parser.parse_args(argv)
    tmpdir = tempfile.mkdtemp(prefix='death-trace-')
    module = _load_worker()
    ok, total = run(module, 'VERDICT', tmpdir)
    if args.neg_arm:
        return mutate_dev_arms(tmpdir, ok, total)
    print('VERDICT: %s -- %d/%d arm(s)' % ('PASS' if ok == total else 'FAIL', ok, total))
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main())
