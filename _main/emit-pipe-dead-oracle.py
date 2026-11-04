#!/usr/bin/env python
# NO-BUG: UM CANO MORTO NAO E' UM CRASH -- o `emit` do worker julgado por execucao. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""UM CANO MORTO NAO E' UM CRASH -- o `emit` do worker julgado por execucao.

O DEFEITO MEDIDO (log do dono, 2026-11-04 01:13:40):

    BRIDGE_EXIT pid=37404 rc=1 killed=False ... stderr_tail=[
      '    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\\n")',
      'OSError: [Errno 22] Invalid argument']
    BRIDGE_DEATH_CAUSE OSError: [Errno 22] Invalid argument
    BRIDGE_DEATH rc=1 deaths=1 kind=error

O pai tinha fechado o cano de leitura no meio de uma recarga; o worker levou um
traceback por escrever onde ninguem le', saiu 1, e a shell publicou a morte como
ERRO (`kind=error`) e pagou a recarga. Um traceback aqui e' um diagnostico
falso: nao houve erro nenhum, o leitor e' que foi-se embora.

Este oraculo NAO le o texto do fonte: importa o worker REAL, substitui o
`sys.stdout` por um que levanta `OSError(22)` e `os._exit` por um que levanta
uma sentinela, e exige o comportamento:

  arm 1  `emit` NAO deixa a excecao escapar (o defeito era `OSError` a subir)
  arm 2  escreve `EMIT_PIPE_DEAD` no stderr (a razao sobrevive para o pai ler)
  arm 3  sai com codigo 0 (`os._exit(0)`), nunca 1
  arm 4  o caminho SAUDAVEL continua igual: um payload cheio vai para o stdout,
         uma linha, com `\\n`, e nada sai no stderr
  arm 5  um segundo `emit` depois do primeiro cano morto nao tenta escrever
         outra vez (o processo ja esta' a caminho de sair)

`--neg-arm`: repoe a escrita crua numa COPIA do worker e exige que as arms 1-3
caiam. Sem esse lado, um `emit` que nunca escreve nada tambem passaria.
"""
from __future__ import annotations

import importlib.util
import io
import os
import shutil
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(os.path.dirname(HERE), 'worker', 'sotto_worker.py')


class _Exit(Exception):
    def __init__(self, code):
        self.code = code


def _load(path):
    spec = importlib.util.spec_from_file_location('sotto_worker_probe', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['sotto_worker_probe'] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(mod):
    """[(nome, ok, detalhe)] das cinco arms, sobre o modulo dado."""
    out = []

    class Dead(io.StringIO):
        def write(self, s):
            raise OSError(22, 'Invalid argument')

        def flush(self):
            pass

    class Healthy(io.StringIO):
        pass

    err = Healthy()
    real_stdout, real_stderr, real_exit = sys.stdout, sys.stderr, mod.os._exit
    codes = []
    sys.stderr = err
    sys.stdout = Dead()
    mod.os._exit = lambda c: (_ for _ in ()).throw(_Exit(c))
    escaped = None
    try:
        mod.emit(type='caption', text='ola')
    except _Exit as e:
        codes.append(e.code)
    except BaseException as e:                # noqa: BLE001
        escaped = e
    out.append(('arm1 nao deixa OSError escapar', escaped is None,
                'escapou %r' % (escaped,) if escaped else 'ok'))
    out.append(('arm2 stderr diz EMIT_PIPE_DEAD', 'EMIT_PIPE_DEAD' in err.getvalue(),
                err.getvalue().strip()[:60] or 'stderr vazio'))
    out.append(('arm3 sai 0, nunca 1', codes == [0], 'codigos=%r' % (codes,)))

    # arm 5: um segundo emit depois do cano morto nao escreve outra vez
    before = len(err.getvalue())
    wrote = False

    class Spy(Healthy):
        def write(self, s):
            nonlocal wrote
            wrote = True
            return super().write(s)

    spy = Spy()
    sys.stdout = spy
    codes2 = []
    try:
        mod.emit(type='caption', text='de novo')
    except _Exit as e:
        codes2.append(e.code)
    sys.stdout = spy
    out.append(('arm5 segundo emit nao escreve e sai 0',
                (not wrote) and codes2 == [0],
                'escreveu=%s codigos=%r' % (wrote, codes2)))

    # arm 4: o caminho saudavel (stdout fresco, sem cano morto)
    fresh = Healthy()
    err2 = Healthy()
    sys.stdout, sys.stderr = fresh, err2
    mod._PIPE_DEAD = False
    codes3 = []
    try:
        mod.emit(type='caption', text='linha')
    except _Exit as e:
        codes3.append(e.code)
    body = fresh.getvalue()
    out.append(('arm4 payload saudavel: uma linha JSON, sem exit, stderr limpo',
                body == '{"type": "caption", "text": "linha"}\n'
                and not codes3 and not err2.getvalue(),
                'stdout=%r exit=%r stderr=%r' % (body[:60], codes3, err2.getvalue()[:40])))

    sys.stdout, sys.stderr, mod.os._exit = real_stdout, real_stderr, real_exit
    mod._PIPE_DEAD = False
    return out


def main(argv):
    neg = '--neg-arm' in argv
    path = WORKER
    tmpdir = None
    if neg:
        # o mutante: a escrita crua, sem o `try`. Numa COPIA.
        # a COPIA vive ao lado do original: o worker importa os irmaos
        # (`engine_switch`, `redux_batch`, ...) por caminho relativo ao ficheiro,
        # e uma copia em %TEMP% nao os encontra (medido: ModuleNotFoundError).
        tmpdir = None
        copy = os.path.join(os.path.dirname(WORKER), '_emit-neg-%d.py' % os.getpid())
        shutil.copyfile(WORKER, copy)
        src = io.open(copy, encoding='utf-8', errors='replace').read()
        start = src.find('    try:\n        sys.stdout.write(')
        if start < 0:
            print('NEG-ARM IMPOSSIVEL -- o `try` do emit nao foi encontrado')
            return 2
        end = src.find('        os._exit(0)', start)
        if end < 0:
            print('NEG-ARM IMPOSSIVEL -- o `os._exit(0)` do emit nao foi encontrado')
            return 2
        end += len('        os._exit(0)')
        mutant = ('    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\\n")\n'
                  '    sys.stdout.flush()')
        io.open(copy, 'w', encoding='utf-8', newline='\n').write(
            src[:start] + mutant + src[end:])
        path = copy

    try:
        mod = _load(path)
    except Exception:                          # noqa: BLE001
        traceback.print_exc()
        print('EMIT-PIPE VERDICT FAIL -- o worker nao carregou')
        return 1
    finally:
        if neg:
            try:
                os.remove(path)
            except OSError:
                pass
    rows = _run(mod)
    for name, ok, detail in rows:
        print('  %s %-52s %s' % ('ok  ' if ok else 'RED ', name, detail))
    bad = [n for n, ok, _ in rows if not ok]
    if neg:
        # o negativo tem de APANHAR o mutante: as arms 1-3 tem de cair
        caught = len(bad) >= 2 and any(n.startswith('arm1') for n in bad) \
            and any(n.startswith('arm3') for n in bad)
        print('NEG-ARM %s -- arms vermelhas=%d (%s)'
              % ('PASS (o mutante cru foi apanhado)' if caught else 'FAIL',
                 len(bad), ','.join(n[:5] for n in bad)))
        return 1 if caught else 0
    print('EMIT-PIPE VERDICT %s -- %d arm(s) vermelha(s)'
          % ('FAIL' if bad else 'PASS', len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
