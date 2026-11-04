#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: a linha que o worker FECHOU esperava o prazo de 1500 ms para chegar ao ecra -- trabalho de CAPACIDADE pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""A LINHA QUE O WORKER FECHOU NAO ESPERA O PRAZO.

MEDIDO na sessao do dono (`_main/webview-run.log`, pid 4992):

    17:32:17.978  CAPTION_IN ... final=false text="RAP tool server sends a"
    17:32:19.481  CAPTION_APPLIED ... queue_ms=1503 over=true
    17:32:19.481  CAPTION_BUDGET_BLOWN audio_ms=1503 budget_ms=1500 queue_ms=1503

O 1503 e' `COMMIT_MAX_HOLD_MS` (1500, `caption-formulation.js`) -- o prazo que
existe para o caso em que o motor NAO tem resposta e precisa de uma segunda
hipotese (LocalAgreement-2) para confirmar a cauda. Quando o proprio fragmento
chega com `final=true`, o worker JA' fechou a linha: nao ha' segunda hipotese a
esperar, e o prazo so' acrescenta 1,5 s de atraso a um texto que ja' esta'
decidido. A cura (`commit('line-closed')` dentro de `ingest`) usa o MESMO
caminho do `expireHold`, por isso a rota continua `final`/`worker-stamped`.

O QUE ESTE ORACULO EXECUTA (o motor REAL, por `node`, sem painel e sem janela):

  A1 `final=true`   -- commit IMEDIATO no proprio `ingest`, rota `final`,
                       `routeSource=worker-stamped`, sem esperar prazo nenhum.
  A2 `final=false`  -- NADA e' commitado no `ingest` (a cauda continua em hold).
  A3 `expireHold`   -- sem `final`, o prazo continua a fechar a linha (o caminho
                       antigo nao foi perdido).
  A4 sem flag       -- um fragmento SEM `final` tambem nao commita sozinho.
  A5 rota nao cai para o fallback -- `routeSource` e' `worker-stamped`, nunca
                       `fallback` (a linha tem voto do worker).
  A6 constante      -- `COMMIT_MAX_HOLD_MS` continua 1500: a cura e' nao esperar
                       QUANDO HA' RESPOSTA, nao encurtar a regua de todo mundo.

`--neg-arm`: muta uma COPIA do motor (1: remove a chamada nova, 2: commita
mesmo com `final=false`) e exige A1 (e A2) a VERMELHO.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, 'app', 'panel', 'caption-formulation.js')

DRIVER = r'''
const path = process.argv[2];
const m = require(path);
const out = { commits: [], provisional: 0, hold: m.COMMIT_MAX_HOLD_MS };
function engine() {
  return m.createEngine({
    onCommit: (line, reason, meta) => out.commits.push({ line, reason, meta }),
    onProvisional: () => { out.provisional += 1; },
  });
}
// A1 -- final=true
let e = engine();
out.commits = [];
e.ingest('hello there my friend', { start: 0, end: 2, final: true });
out.a1 = out.commits.length;
out.a1_line = out.commits[0] ? out.commits[0].line : null;
out.a1_route = out.commits[0] ? out.commits[0].meta.route : null;
out.a1_src = out.commits[0] ? out.commits[0].meta.routeSource : null;
// A2 -- final=false: nao commita no ingest
e = engine();
out.commits = [];
e.ingest('hello there my friend', { start: 0, end: 2, final: false });
out.a2 = out.commits.length;
// A3 -- o prazo continua a fechar a linha
out.a3 = e.expireHold() ? 1 : 0;
out.a3_reason = out.commits.length ? out.commits[out.commits.length - 1].reason : null;
// A4 -- sem flag nenhuma
e = engine();
out.commits = [];
e.ingest('no flag at all here', { start: 0, end: 1 });
out.a4 = out.commits.length;
// A5 -- a rota de uma linha fechada nunca e' fallback
e = engine();
out.commits = [];
e.ingest('closing line test', { start: 0, end: 1, final: true });
out.a5_src = out.commits[0] ? out.commits[0].meta.routeSource : null;
console.log(JSON.stringify(out));
'''


def probe(engine_path):
    tmp = tempfile.mkdtemp(prefix='line-closed-')
    drv = os.path.join(tmp, 'drv.js')
    with open(drv, 'w', encoding='utf-8') as fh:
        fh.write(DRIVER)
    res = subprocess.run(['node', drv, engine_path], capture_output=True,
                         text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError('node falhou: %s' % (res.stderr or res.stdout)[-400:])
    return json.loads(res.stdout.strip().splitlines()[-1])


def arms(engine_path=ENGINE):
    d = probe(engine_path)
    rows = [
        ('a1-final-commita-ja', d['a1'] >= 1,
         'commits=%d line=%r' % (d['a1'], d['a1_line'])),
        ('a2-sem-final-nao-commita', d['a2'] == 0, 'commits=%d' % d['a2']),
        ('a3-expireHold-fecha-a-linha', d['a3'] == 1,
         'closed=%d reason=%r' % (d['a3'], d['a3_reason'])),
        ('a4-sem-flag-nao-commita', d['a4'] == 0, 'commits=%d' % d['a4']),
        ('a5-rota-worker-stamped', d['a5_src'] == 'worker-stamped',
         'routeSource=%r' % d['a5_src']),
        ('a6-prazo-continua-1500', int(d['hold']) == 1500, 'hold=%r' % d['hold']),
    ]
    return rows


MUTANTS = {
    'm1-sem-a-cura': (
        "    if (tailClosed && provisional.length) {\n      commit('line-closed');\n    }\n",
        ""),
    'm2-commita-sempre': (
        "    if (tailClosed && provisional.length) {",
        "    if (provisional.length) {"),
}


def neg_arm():
    src = open(ENGINE, encoding='utf-8', errors='replace').read()
    tmp = tempfile.mkdtemp(prefix='line-closed-mut-')
    caught = total = 0
    for name, (old, new) in MUTANTS.items():
        total += 1
        if old not in src:
            print('NEG-ARM IMPOSSIVEL %s: padrao ausente' % name)
            continue
        copy = os.path.join(tmp, name.replace('-', '_') + '.js')
        with open(copy, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(old, new, 1))
        rows = dict((n, ok) for n, ok, _ in arms(copy))
        bad = [n for n, ok in rows.items() if not ok]
        if bad:
            caught += 1
            print('ok  %s -> RED: %s' % (name, ','.join(bad)))
        else:
            print('NOT-CAUGHT %s: nenhum arm vermelho' % name)
    shutil.rmtree(tmp, ignore_errors=True)
    print('NEG-ARM %s mutants %d/%d'
          % ('PASS' if caught == total else 'FAIL', caught, total))
    return 1 if caught == total else 0


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    rows = arms()
    bad = [r for r in rows if not r[1]]
    for name, ok, note in rows:
        print('%-30s %s  %s' % (name, 'PASS' if ok else 'FAIL', note))
    print('VERDICT: %s arms %d/%d'
          % ('FAIL' if bad else 'PASS', len(rows) - len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
