"""audio-ring-oracle - o ring de 12 h tem de estar LIGADO ao caminho da legenda.

ORDEM DO DONO (2026-11-11): *"MANTENHA o audio INTEIRO das ultimas 12 horas pra
benchmark/replay"*. Um modulo que grava audio e ninguem chama e' a doenca que
esta casa ja' pagou tres vezes (instrumento sem passo, instrumento sem chamador).
Este portao julga as quatro emendas:

  A1 `worker/audio_ring.py` existe e o `--selftest` do leitor passa (o modulo E o
     corte por linha, contra uma senoide conhecida).
  A2 `sotto_worker.main()` CONSTROI o ring, e so' no caminho de captura viva
     (`--selftest`/`--audio` nao tem tap: guardar o fixture seria audio de teste
     a passar por audio do dono).
  A3 `on_block` EMPURRA cada bloco: e' o unico ponto por onde todo o bloco do
     tap passa. Um ring que so' ve metade do audio responde errado ao benchmark.
  A4 a linha FECHADA escreve a ancora (`append_line_anchor`) e o ring FECHA no
     fim da corrida -- sem o `close()` o ultimo segmento fica sem linha no
     indice e o replay perde exactamente o audio mais recente.

Os arms A2-A4 leem o FONTE por AST (a emenda e' estrutura, nao texto de
comentario), e o `--neg-arm` muta uma COPIA do worker e exige as quatro
vermelhas.
"""
from __future__ import annotations

import argparse
import ast
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
RING = os.path.join(ROOT, 'worker', 'audio_ring.py')
REPLAY = os.path.join(HERE, 'audio-replay.py')


def _parse(path):
    with io.open(path, encoding='utf-8') as fh:
        return ast.parse(fh.read(), filename=path)


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _calls(node, dotted):
    """Os nomes chamados dentro de `node`, na forma `a.b.c`."""
    out = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        f = sub.func
        parts = []
        while isinstance(f, ast.Attribute):
            parts.append(f.attr)
            f = f.value
        if isinstance(f, ast.Name):
            parts.append(f.id)
            out.add('.'.join(reversed(parts)))
    return out


def _mentions(node, name):
    return name in {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def judge(worker_src):
    """As tres emendas de FONTE. Devolve [(arm, ok, detail)]."""
    arms = []
    tree = _parse(worker_src)
    main = _func(tree, 'main')
    on_block = _func(tree, 'on_block')

    # A2 -- o ring nasce em main(), guardado pelo caminho de captura viva.
    ok_a2 = False
    detail_a2 = 'main nao encontrada'
    if main is not None:
        ctor = any(c.endswith('audio_ring.AudioRing') or c == 'audio_ring.AudioRing'
                   for c in _calls(main, 'x') | _raw_calls(main))
        guard = False
        for sub in ast.walk(main):
            if isinstance(sub, ast.If):
                text = ast.dump(sub.test)
                if ('selftest' in text and 'audio' in text
                        and 'audio_ring' in ast.dump(sub)):
                    guard = True
        ok_a2 = bool(ctor and guard and _mentions(main, '_AUDIO_RING'))
        detail_a2 = 'ctor=%s guard=%s global=%s' % (ctor, guard, _mentions(main, '_AUDIO_RING'))
    arms.append(('A2-ring-nasce-na-captura-viva', ok_a2, detail_a2))

    # A3 -- on_block empurra.
    ok_a3 = False
    detail_a3 = 'on_block nao encontrada'
    if on_block is not None:
        calls = _raw_calls(on_block)
        ok_a3 = any(c.endswith('.push') for c in calls) and _mentions(on_block, '_AUDIO_RING')
        detail_a3 = 'push=%s' % sorted(c for c in calls if c.endswith('.push'))
    arms.append(('A3-on_block-empurra', ok_a3, detail_a3))

    # A4 -- a ancora da linha e o close no finally.
    a4_line = _func(tree, '_event')
    anchors = sorted(c for c in _raw_calls(a4_line) if c.endswith('append_line_anchor')) if a4_line else []
    closes = sorted(c for c in _raw_calls(main) if c.endswith('.close')) if main is not None else []
    # O `close()` tem de ser chamado NO `_AUDIO_RING`, nao apenas mencionado:
    # a arm anterior media a MENCAO do global em `main()` e o mutante que
    # apagava a chamada passava (medido: M4 NOT-CAUGHT).
    ring_closes = sorted(a for a in _ring_attr_calls(main) if a == 'close')
    ok_a4 = bool(anchors) and bool(ring_closes)
    arms.append(('A4-ancora-e-close', ok_a4,
                 'anchor=%s ring_close=%s other=%d' % (anchors, ring_closes, len(closes))))
    return arms


def _ring_attr_calls(node):
    """Os metodos chamados LITERALMENTE sobre `_AUDIO_RING` dentro de `node`."""
    out = set()
    if node is None:
        return out
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            base = sub.func.value
            if isinstance(base, ast.Name) and base.id == '_AUDIO_RING':
                out.add(sub.func.attr)
    return out


def _raw_calls(node):
    out = set()
    if node is None:
        return out
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        f = sub.func
        parts = []
        while isinstance(f, ast.Attribute):
            parts.append(f.attr)
            f = f.value
        if isinstance(f, ast.Name):
            parts.append(f.id)
        if parts:
            out.add('.'.join(reversed(parts)))
    return out


def run_selftest():
    try:
        # O PAR, NAO O BIT (`_main/console-window-audit.py` recusa um
        # `creationflags` sozinho): medido 2026-11-04, o bit so' esconde a
        # janela quando o pai TEM consola, e o pai desta frota nunca tem.
        proc = subprocess.run([sys.executable, REPLAY, '--selftest'],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=180,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                              startupinfo=subprocess.STARTUPINFO(
                                  dwFlags=subprocess.STARTF_USESHOWWINDOW,
                                  wShowWindow=0))
    except Exception as exc:  # noqa: BLE001
        return False, 'selftest nao correu: %r' % (exc,), ''
    out = proc.stdout.decode('utf-8', 'replace')
    return proc.returncode == 0 and 'RING-SELFTEST PASS' in out, \
        'rc=%d' % proc.returncode, out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)

    if not os.path.exists(RING):
        print('AUDIO-RING VERDICT: FAIL -- worker/audio_ring.py ausente')
        return 1

    ok_a1, detail_a1, text = run_selftest()
    arms = [('A1-modulo-e-corte', ok_a1, detail_a1)]
    arms += judge(WORKER)

    for name, ok, detail in arms:
        print('%s %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if text:
        for line in text.strip().splitlines()[-7:]:
            print('   | ' + line)
    bad = [a for a in arms if not a[1]]
    print('AUDIO-RING VERDICT: %s -- %d/%d'
          % ('PASS' if not bad else 'FAIL', len(arms) - len(bad), len(arms)))

    if args.neg_arm:
        return _neg_arm()

    return 0 if not bad else 1


def _neg_arm():
    """Muta uma COPIA do worker em quatro sitios, um por arm, e exige 4/4."""
    src = io.open(WORKER, encoding='utf-8', newline='').read()
    muts = [
        # M1: o ring deixa de nascer
        ("            _AUDIO_RING = audio_ring.AudioRing(os.path.dirname(HERE))",
         "            pass"),
        # M2: on_block deixa de empurrar
        ("            _AUDIO_RING.push(block)", "            pass"),
        # M3: a ancora da linha desaparece
        ("                audio_ring.append_line_anchor(",
         "                (lambda *a, **k: None)("),
        # M4: o close desaparece
        ("                _AUDIO_RING.close()", "                pass"),
    ]
    caught = 0
    tmp = tempfile.mkdtemp(prefix='ring-neg-')
    try:
        for i, (old, new) in enumerate(muts, start=1):
            if old not in src:
                print('M%d ANCORA NAO ENCONTRADA -- mutacao impossivel' % i)
                continue
            p = os.path.join(tmp, 'worker_m%d.py' % i)
            io.open(p, 'w', encoding='utf-8', newline='').write(src.replace(old, new, 1))
            broken = [a for a in judge(p) if not a[1]]
            if broken:
                caught += 1
                print('M%d CAUGHT by %s' % (i, ','.join(b[0] for b in broken)))
            else:
                print('M%d NOT-CAUGHT' % i)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('NEG-ARM: %s -- %d/%d' % ('PASS' if caught == len(muts) else 'FAIL',
                                    caught, len(muts)))
    return 1 if caught == len(muts) else 0


if __name__ == '__main__':
    raise SystemExit(main())
