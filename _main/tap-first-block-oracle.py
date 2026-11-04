#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: o primeiro bloco de audio esperava a escada do silencio e custava 44 s -- trabalho de CAPACIDADE pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""O CANDIDATO MORTO CAI AOS 2 s, NAO AOS 44.

ORDEM DO DONO (2026-11-04), verbatim: *"agora apareceu. por que demorou pra
caralho? nao e pra demorar. e' pra ser possivel em ate 3 segundos assim que
sotto abrir"*.

MEDIDO no arranque dele (`H:/sotto/_main/webview-run.log`, pid 32540):

    09:57:24.322  SHELL_STARTUP_STAGE pid=32540 stage=pre-lock
    09:57:32.943  BRIDGE_LOAD_MS ms=8531          <- o modelo leva 8,5 s, ok
    09:57:41.711  STATUS_APPLIED "capture-started" <- o tap abriu
    09:58:25.255  STATUS_APPLIED "device-rotated (flat)"  <- 44 s depois, ZERO
    09:58:26.356  BRIDGE_METER count=1 blocks=1.0
    09:58:29.337  primeiro CAPTION_IN             <- +3 s do primeiro bloco

O endpoint abriu e nao entregou UM callback durante 44 s. `window_ended` /
`silent_desktop_hold` existem para o desktop PARADO (impedir 12 clientes WASAPI
em 3 minutos), e um endpoint ABERTO e mudo nao e' um desktop parado: e' um
candidato morto. A regra nova (`first_block_decided`) pergunta isso ANTES da
escada do silencio e so' enquanto nenhum bloco chegou.

O QUE ESTE ORACULO EXECUTA (a funcao REAL de `worker/sotto_worker.py`):

  A1 dentro do piso   -- 1,9 s sem bloco: espera.
  A2 piso estourado   -- 2,0 s sem bloco: rotaciona, `waited_ms` >= 2000.
  A3 bloco chegou     -- com `blocks=1` nunca rotaciona (a politica antiga
                         continua a mandar depois do primeiro bloco).
  A4 constante        -- o piso e' 2,0 s, e nao 6/12/24/44.
  A5 lixo             -- `None`/texto no lugar dos numeros nao rotaciona.
  A6 fiacao           -- o laco do worker chama a regra antes de `window_ended`
                         e publica `TAP_DEAD_ENDPOINT`/`TAP_FIRST_BLOCK`.

`--neg-arm`: muta uma COPIA do worker de duas formas -- (1) o piso vira 60 s
(o comportamento medido), (2) a regra rotaciona mesmo DEPOIS do primeiro bloco
-- e exige as arms correspondentes a VERMELHO.
"""
import importlib.util
import io
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
sys.path.insert(0, os.path.join(ROOT, 'worker'))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def arms(worker_path=WORKER):
    mod = load(worker_path, 'sotto_worker_under_test')
    decide = mod.first_block_decided
    out = []
    rotate, waited = decide(0.0, 0, 1.9)
    out.append(('a1-dentro-do-piso-espera', rotate is False, 'rotate=%s' % rotate))
    rotate, waited = decide(0.0, 0, 44.0)
    out.append(('a2-piso-estourado-rotaciona',
                rotate is True and waited >= 2000, 'rotate=%s waited_ms=%d'
                % (rotate, waited)))
    rotate, _w = decide(0.0, 1, 44.0)
    out.append(('a3-com-bloco-nao-rotaciona', rotate is False, 'rotate=%s' % rotate))
    out.append(('a4-piso-e-2-s', float(getattr(mod, 'TAP_FIRST_BLOCK_MAX_S', 0)) == 2.0,
                'piso=%r' % getattr(mod, 'TAP_FIRST_BLOCK_MAX_S', None)))
    rotate, _w = decide(None, 'x', 'y')
    out.append(('a5-lixo-nao-rotaciona', rotate is False, 'rotate=%s' % rotate))
    src = io.open(worker_path, encoding='utf-8', errors='replace').read()
    wired = ('first_block_decided(' in src
             and src.index('first_block_decided(') < src.index('window_ended(now, dev')
             and 'TAP_DEAD_ENDPOINT' in src and 'TAP_FIRST_BLOCK ' in src)
    out.append(('a6-fiacao-no-laco', wired, 'wired=%s' % wired))
    return out


MUTANTS = {
    'm1-piso-de-60s': ('TAP_FIRST_BLOCK_MAX_S = 2.0', 'TAP_FIRST_BLOCK_MAX_S = 60.0'),
    'm2-rotaciona-sempre': (
        '    if blocks > 0:\n        return False, 0',
        '    if False:\n        return False, 0'),
}


def neg_arm():
    src = io.open(WORKER, encoding='utf-8', errors='replace').read()
    tmp = tempfile.mkdtemp(prefix='first-block-neg-')
    caught = total = 0
    for name, (old, new) in MUTANTS.items():
        total += 1
        if old not in src:
            print('NEG-ARM IMPOSSIVEL %s: o padrao nao esta no ficheiro' % name)
            continue
        copy = os.path.join(tmp, name.replace('-', '_') + '.py')
        with io.open(copy, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(old, new, 1))
        rows = dict((n, ok) for n, ok, _ in arms(copy))
        bad = [n for n, ok in rows.items() if not ok]
        if bad:
            caught += 1
            print('ok  %s -> RED: %s' % (name, ','.join(bad)))
        else:
            print('NOT-CAUGHT %s: nenhum arm vermelho' % name)
    print('NEG-ARM %s mutants %d/%d'
          % ('PASS' if caught == total else 'FAIL', caught, total))
    return 1 if caught == total else 0


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    rows = arms()
    bad = [r for r in rows if not r[1]]
    for name, ok, note in rows:
        print('%-32s %s  %s' % (name, 'PASS' if ok else 'FAIL', note))
    print('VERDICT: %s arms %d/%d'
          % ('FAIL' if bad else 'PASS', len(rows) - len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
