#!/usr/bin/env python
# NO-BUG: battery-budget -- o TECTO da corrida, como portao com ratchet.
"""battery-budget -- o TECTO da corrida, como portao com ratchet.

A LEI QUE ISTO ENFORCA (AGENTS.md, 2026-11-05, ordem do dono: *"por que e' completamente BURRO
voce levar mais que um minuto pra rodar COISAS JA GARANTIDAS EM VARIOS LUGARES DA BATERIA"*).
A bateria registra `elapsed_s` por passo em `_cache\\battery-steps.json`. Medido em 2026-11-05:
**5 801,2 s** no total, **86,0 % em 20 passos**, o pior **3 781,6 s**, e os 254 passos abaixo de
5 s somando **277,8 s (4,8 %)**. Uma corrida assim e' um custo que se paga em cada volta do
laco de trabalho, e nada a impedia de crescer -- nenhum portao olhava para o RELOGIO.

DUAS METADES, e a diferenca importa:

  * TARGET (a lei): `DEFAULT_TARGET_S = 60` -- a corrida default, a quente, cabe em 60 s. Isto
    e' o NUMERO A ATINGIR e a ferramenta diz a distancia; nao e' um veredicto de hoje.
  * RATCHET (o portao): o total registrado nao pode crescer mais de `RATCHET_PCT` sobre o
    baseline, e nenhum passo pode aparecer acima de `SOTTO_STEP_DEADLINE_S` (240 s) sem estar
    declarado como divida no baseline. Um numero que so' piora e' divida; um numero que sobe
    sem ninguem decidir e' regressao.

Uso:
    python _main\\battery-budget-oracle.py            -> ratchet: rc 0 verde, 1 RED
    python _main\\battery-budget-oracle.py --report   -> a tabela, nunca muda rc
    python _main\\battery-budget-oracle.py --neg-arm  -> muta uma LEITURA e exige o RED
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, '_cache', 'battery-steps.json')
BASELINE = os.path.join(HERE, 'battery-budget-baseline.json')
DEFAULT_TARGET_S = 60.0
RATCHET_PCT = 1.05


def read_steps(path):
    data = json.load(io.open(path, encoding='utf-8'))
    steps = data.get('steps', data)
    rows = []
    for name, rec in steps.items():
        if not isinstance(rec, dict):
            continue
        rows.append({
            'name': name,
            'elapsed_s': float(rec.get('elapsed_s') or 0.0),
            'rc': rec.get('rc'),
            'timestamp': rec.get('timestamp') or '',
        })
    return rows


def measure(rows, deadline_s):
    total = sum(r['elapsed_s'] for r in rows)
    over = [r for r in rows if r['elapsed_s'] >= deadline_s]
    slow = sorted(rows, key=lambda r: -r['elapsed_s'])[:10]
    return {'total_s': round(total, 1), 'steps': len(rows),
            'over_deadline': sorted(r['name'] for r in over),
            'slowest': [(r['name'], round(r['elapsed_s'], 1)) for r in slow]}


def load_baseline(path=BASELINE):
    if not os.path.exists(path):
        return None
    return json.load(io.open(path, encoding='utf-8'))


def judge(measured, baseline, target=DEFAULT_TARGET_S, pct=RATCHET_PCT):
    """O veredicto, puro: recebe numeros, devolve (ok, razoes, glow)."""
    reasons = []
    ok = True
    if baseline is None:
        return False, ['baseline ausente: sem baseline nao ha ratchet'], 0.0
    ceiling = float(baseline['total_s']) * pct
    if measured['total_s'] > ceiling:
        ok = False
        reasons.append('total %.1fs acima do tecto %.1fs (baseline %.1fs x %.2f)'
                       % (measured['total_s'], ceiling, baseline['total_s'], pct))
    declared = set(baseline.get('over_deadline', []))
    new_over = [n for n in measured['over_deadline'] if n not in declared]
    if new_over:
        ok = False
        reasons.append('passo(s) acima do prazo sem divida declarada: %s'
                       % ','.join(new_over))
    gone = sorted(declared - set(measured['over_deadline']))
    gap = round(measured['total_s'] - target, 1)
    return ok, reasons, gap


def report(measured, baseline, gap):
    print('BATTERY-BUDGET steps=%d total=%.1fs target=%.0fs gap=%.1fs'
          % (measured['steps'], measured['total_s'], DEFAULT_TARGET_S, gap))
    for name, secs in measured['slowest']:
        print('  slow %-46s %9.1fs' % (name, secs))
    if measured['over_deadline']:
        print('  over-deadline(>=%ds): %s' % (int(deadline()), ','.join(measured['over_deadline'])))
    if baseline:
        print('  baseline total=%.1fs x %.2f -> ceiling=%.1fs'
              % (baseline['total_s'], RATCHET_PCT, baseline['total_s'] * RATCHET_PCT))


def deadline():
    try:
        return float(os.environ.get('SOTTO_STEP_DEADLINE_S') or 240)
    except ValueError:
        return 240.0


def neg_arm():
    """MUTA a LEITURA (nao o codigo): infla um passo 10x e exige o RED do mesmo `judge`."""
    rows = read_steps(CACHE)
    measured = measure(rows, deadline())
    base = load_baseline()
    if base is None:
        print('NEG-ARM IMPOSSIVEL -- baseline ausente')
        return 1
    ok_before, _, _ = judge(measured, base)
    # O MUTANTE NAO PODE SER UM PASSO QUE A DIVIDA JA' DECLARA (medido
    # 2026-11-05): inflar o passo MAIS LENTO, quando ele e' exactamente o que o
    # baseline congela em `over_deadline`, deixa `new_over` VAZIO -- o
    # `--neg-arm` publicava FAIL com o juiz a funcionar. A mutacao morde um
    # passo que a divida NAO cobre.
    _declared = set(base.get('over_deadline') or ())
    # O CANDIDATO TEM DE ESTAR LIMPO HOJE (medido 2026-11-05): inflar o passo
    # mais lento quando ele JA' passa do prazo nao mede nada -- o juiz ja' o
    # nomeava antes do mutante. E a arm nao pode exigir um baseline verde: com um
    # passo real acima do prazo, `ok_before` era False e o `--neg-arm` publicava
    # FAIL com o juiz a funcionar (medido: `bend-laws 240,4 s`).
    _cand = [r for r in rows
             if r['name'] not in _declared and r['elapsed_s'] < deadline()] or rows
    worst = max(_cand, key=lambda r: r['elapsed_s']) if _cand else None
    if worst is None:
        print('NEG-ARM IMPOSSIVEL -- cache sem passos')
        return 1
    worst['elapsed_s'] = max(worst['elapsed_s'] * 10.0, deadline() * 1.5)
    mutant = measure(rows, deadline())
    ok_after, why_after, _ = judge(mutant, base)
    _, why_before, _ = judge(measured, base)
    named_before = any(worst['name'] in w for w in why_before)
    named_after = any(worst['name'] in w for w in why_after)
    caught = named_after and not named_before
    print('NEG-ARM leitura mutada: %s %.1fs -> %.1fs' % (worst['name'], worst['elapsed_s'] / 10.0,
                                                         worst['elapsed_s']))
    for line in why_after:
        print('  RED', line)
    print('NEG-ARM: %s (%s)' % ('PASS' if caught else 'FAIL',
                                'o mutante foi APANHADO' if caught else 'o mutante passou'))
    print('NEG-ARM nomeado antes=%s depois=%s (juiz virou RED: %s -> %s)'
          % (named_before, named_after, ok_before, ok_after))
    return 1 if caught else 0


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    if '--baseline' in argv:
        rows = read_steps(CACHE)
        measured = measure(rows, deadline())
        out = {'total_s': measured['total_s'], 'steps': measured['steps'],
               'over_deadline': measured['over_deadline'],
               'target_s': DEFAULT_TARGET_S,
               'measured': '2026-11-05'}
        io.open(BASELINE, 'w', encoding='utf-8', newline='\n').write(
            json.dumps(out, indent=2, sort_keys=True) + '\n')
        print('baseline escrito: %s total_s=%.1f over=%d'
              % (BASELINE, out['total_s'], len(out['over_deadline'])))
        return 0
    if not os.path.exists(CACHE):
        print('BATTERY-BUDGET CANNOT-MEASURE -- sem %s' % CACHE)
        return 2
    rows = read_steps(CACHE)
    measured = measure(rows, deadline())
    base = load_baseline()
    ok, why, gap = judge(measured, base)
    if '--report' in argv:
        report(measured, base, gap)
        return 0
    report(measured, base, gap)
    for line in why:
        print('  RED', line)
    # O veredicto NOMEIA o ratchet. Um `PASS` ao lado de um gap de 5 741 s seria
    # exactamente o verde que nao mede nada: rc 0 aqui significa "nao piorou", e a
    # linha diz em voz alta que o TARGET nao foi atingido.
    verdict = ('RATCHET-OK' if ok else 'RED')
    tail = ('TARGET NOT MET (gap %.1fs de %.0fs)' % (gap, DEFAULT_TARGET_S)
            if gap > 0 else 'TARGET MET')
    print('BATTERY-BUDGET VERDICT %s -- steps=%d total=%.1fs %s'
          % (verdict, measured['steps'], measured['total_s'], tail))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
