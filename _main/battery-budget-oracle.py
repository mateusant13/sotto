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
#: O RATCHET POR PASSO USA OUTRO FATOR, e a razao esta' MEDIDA. O `1.05` do
#: total compara um numero SOMADO -- estavel, porque a contenda de um passo se
#: dilui nos 370. Um passo sozinho nao tem essa diluicao: medido 2026-11-08, o
#: MESMO oraculo custou 79,94 s sozinho e 219,1 s dentro da corrida -- fator de
#: contenda **2,7x**. Uma regua de 5 % por passo dispararia em ruido, e um portao
#: que grita em ruido e' desligado pela primeira pessoa que o vir vermelho. Daqui
#: 20 % (a mesma regua do `shell-thread-budget`) mais um PISO de 5 s: abaixo disso
#: nem o ruido nem o alvo de 60 s se importam com o passo.
#: O PISO PASSOU DE 5 s PARA 20 s POR MEDICAO, nao por gosto (2026-11-08, corrida
#: caged pos-reinicio): `lane-screen-gate` mediu **4,35 / 8,58 / 5,96 s** em tres
#: execucoes seguidas do MESMO binario -- **97 % de variacao** -- e `load-shedding`
#: **3,05 / 3,62 / 3,24 s** (19 %). Um ratchet de 20 % sobre um passo que varia 97 %
#: por conta propria reprova o relogio, nao o passo. A regressao que este portao
#: existe para apanhar e' outra escala (`lag-note-cost` 224 s -> 1 364 s x10), e ela
#: continua a ser apanhada pelo prazo, pelo tecto do total e pelo ratchet dos passos
#: acima do piso.
PER_STEP_PCT = 1.20
PER_STEP_FLOOR_S = 20.0


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
            # A POLITICA DE LARGADA sob a qual o numero foi medido (medido
            # 2026-11-08). Ausente = anterior ao campo, logo de uma corrida que
            # NAO declarava tecto -- tratado como `None`, nunca como a de agora.
            'policy': rec.get('policy'),
        })
    return rows


def measure(rows, deadline_s, policy=None):
    """So' julga o que foi medido sob a MESMA politica de largada.

    MEDIDO 2026-11-08: a primeira corrida sob o tecto de CPU comparou os seus tempos
    com um baseline medido SEM tecto e chamou de regressao o preco do proprio tecto
    (11 passos, 1,2x a 38x). Um tempo por passo de outra politica nao e' uma
    regressao -- e' uma comparacao que nao existe. Os passos de outra politica saem
    da populacao e o numero dos que sairam e' PUBLICADO: uma populacao que encolhe
    em silencio e' o mesmo defeito de um passo saltado contado como verde.
    """
    skipped = [r for r in rows if (r.get('policy') or None) != (policy or None)]
    rows = [r for r in rows if (r.get('policy') or None) == (policy or None)]
    total = sum(r['elapsed_s'] for r in rows)
    over = [r for r in rows if r['elapsed_s'] >= deadline_s]
    slow = sorted(rows, key=lambda r: -r['elapsed_s'])[:10]
    return {'total_s': round(total, 1), 'steps': len(rows),
            'policy': policy or None,
            'policy_skipped': len(skipped),
            'policy_skipped_names': sorted(r['name'] for r in skipped)[:20],
            'over_deadline': sorted(r['name'] for r in over),
            'per_step': {r['name']: round(r['elapsed_s'], 1) for r in rows},
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
    if (baseline.get('policy') or None) != (measured.get('policy') or None):
        # Duas politicas: os numeros nao sao comparaveis. Dizer "PASS" seria pior
        # que dizer "nao sei"; dizer "RED" seria culpar o tecto.
        return False, ['politica de largada diferente do baseline (baseline=%r, corrida=%r) '
                       '-- re-medir o baseline com `--baseline --policy %r --rebase-policy <razao>`'
                       % (baseline.get('policy'), measured.get('policy'),
                          measured.get('policy'))], 0.0
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
    # O RATCHET POR PASSO, que e' o que este portao devia ter desde o inicio.
    # MEDIDO 2026-11-08: o baseline era `total_s=5801,2` (de 2026-11-05) e a
    # corrida verde media `2102,0` em 370 passos -- o tecto de 6 091 s deixava
    # passar uma regressao de **2,9x** em silencio, porque UM numero somado
    # esconde o passo que engordou e um passo pesado que sai da populacao baixa
    # o total. A comparacao passo a passo nao tem esse buraco e NOMEIA o culpado.
    # Passo novo nao entra por aqui: o `new_over` acima ja' o julga pelo prazo.
    per_base = baseline.get('per_step') or {}
    per_now = measured.get('per_step') or {}
    if per_base:
        grew = []
        for name, secs in sorted(per_now.items()):
            before = per_base.get(name)
            if before is None or before <= 0:
                continue
            # O PISO E' SOBRE O QUE ESTA' SENDO JULGADO, NUNCA UMA ISENCAO: um
            # passo que NASCEU pequeno e engordou para 200 s passa a ser julgado
            # (medido nesta sessao: com `before < PISO: continue`, 4,9 s -> 200 s
            # ficava invisivel para o ratchet por passo, abaixo do prazo e abaixo
            # do tecto do total). Quem nunca chega ao piso nem ao prazo nem ao
            # total nao interessa a ninguem.
            if max(before, secs) < PER_STEP_FLOOR_S:
                continue
            if secs > before * PER_STEP_PCT:
                grew.append('%s %.1fs -> %.1fs (baseline %.1fs x %.2f = %.1fs)'
                            % (name, before, secs, before, PER_STEP_PCT,
                               before * PER_STEP_PCT))
        if grew:
            ok = False
            reasons.append('passo(s) que engordaram alem do ratchet: %s'
                           % ' | '.join(grew))
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


def judge_arms():
    """OS BRACOS DO JUIZ, puros: nenhum le' o disco, nenhum arranca processo.

    Nasceram do defeito medido 2026-11-08: com o baseline em 5801,2 s e a corrida
    a medir 2102,0 s, o tecto do total deixava passar uma regressao de 2,9x sem
    dizer nada. Um `judge` que nao consegue reprovar o caso que o motivou e' um
    portao decorativo, por isso os bracos correm em TODA invocacao normal (custo
    medido: microssegundos) e o veredicto do passo inclui o deles.
    """
    # COM O PISO EM 20 s, um fixture de 10 s deixou de poder testar o ratchet: o
    # A2 (12,6 s) passou a ser ISENTO pelo piso e o braco ficou vermelho contra a
    # propria cura. `a` vai para 30 s (acima do piso) e `b`/`c` fecham o total em
    # 100 s, que e' o que o tecto do total tem de continuar a ver.
    base = {'total_s': 100.0, 'over_deadline': [], 'target_s': 60.0,
            'per_step': {'a': 30.0, 'b': 40.0, 'c': 30.0, 'tiny': 0.3}}

    def m(per, total=None, over=()):
        return {'total_s': round(sum(per.values()), 1) if total is None else total,
                'steps': len(per), 'over_deadline': list(over),
                'per_step': dict(per), 'slowest': []}

    arms = []

    def arm(name, measured, want_ok, want_name=None, want_red_total=False):
        ok, why, _gap = judge(measured, base)
        named = (any(want_name in w for w in why) if want_name else True)
        total_red = any('acima do tecto' in w for w in why)
        good = (ok == want_ok) and named and (total_red == want_red_total)
        arms.append({'arm': name, 'ok': good,
                     'detail': 'ok=%s (want %s); named=%s; total-red=%s (want %s); %s'
                               % (ok, want_ok, named, total_red, want_red_total,
                                  ' | '.join(why) or '(sem razoes)')})

    arm('A1 um passo +10% passa (abaixo da regua de 20%)',
        m({'a': 33.0, 'b': 40, 'c': 30, 'tiny': 0.3}), True)
    arm('A2 um passo +26% reprova e o NOMEIA',
        m({'a': 38.0, 'b': 40, 'c': 26, 'tiny': 0.3}), False, 'a 30.0s -> 38.0s')
    arm('A3 total IGUAL e um passo 30->60 reprova (o caso que passava)',
        m({'a': 60.0, 'b': 40.0, 'c': 0.0, 'tiny': 0.3}, total=100.0), False,
        'a 30.0s -> 60.0s')
    # A arm A4 tambem derruba o TECTO DO TOTAL (400 s contra 105 s), e isso e'
    # esperado: o passo novo e' um passo que ninguem tinha medido, logo o total
    # sobe por construcao. O que ela prova e' que o `new_over` o NOMEIA.
    arm('A4 passo novo acima do prazo, sem divida declarada',
        m({'a': 30, 'b': 40, 'c': 30, 'tiny': 0.3, 'd': 300}, over=['d']), False, 'd',
        want_red_total=True)
    arm('A5 um passo que saiu da populacao nao reprova',
        m({'a': 30, 'b': 40, 'c': 30, 'tiny': 0.3}), True)
    # O PISO: um passo de 0,3 s que dobra para 0,9 s e' ruido, nao regressao --
    # a regua comeca em `PER_STEP_FLOOR_S`. Sem este braco, subir o piso para o
    # infinito (apagar o ratchet) continuaria verde em todos os outros.
    arm('A6 passo abaixo do piso (0,3s -> 0,9s) nao reprova',
        m({'a': 30, 'b': 40, 'c': 30, 'tiny': 0.9}), True)
    # O PISO NAO E' ISENCAO: 4,9 s (abaixo do piso) que engorda para 200 s tem de
    # ser julgado -- a versao anterior a este braco deixava-o invisivel para o
    # ratchet por passo, abaixo do prazo e abaixo do tecto do total.
    # (o fixture tambem derruba o tecto do total -- por construcao, 200 s num
    # total de 100 s; o que a arm isola e' o NOME do passo no ratchet por passo)
    arm('A7 passo que NASCEU abaixo do piso e engordou para 200s reprova',
        m({'a': 30, 'b': 40, 'c': 30, 'tiny': 200.0}), False, 'tiny 0.3s -> 200.0s',
        want_red_total=True)
    # A8 e' o caso MEDIDO que obrigou o piso a mudar: 5,5 s -> 12,1 s (2,2x) num passo
    # abaixo do piso NAO pode reprovar. Com o piso antigo (5 s) ele reprovava; com o
    # novo (20 s) fica isento pela regua, e o total (daqui 105 s) tambem nao se move.
    arm('A8 passo de 5,5s que vira 12,1s nao reprova (o caso que obrigou o piso)',
        m({'a': 30, 'b': 30, 'c': 28, 'tiny': 0.3, 'lane': 12.1}), True)
    # A9 impede a isencao total: um passo ACIMA do piso que dobra continua a reprovar.
    arm('A9 passo acima do piso (40s -> 90s) reprova e o NOMEIA',
        m({'a': 5, 'b': 90, 'c': 5, 'tiny': 0.3}), False, 'b 40.0s -> 90.0s')
    return arms


def neg_arm():
    """MUTA a LEITURA (nao o codigo) e exige que o MESMO `judge` nomeie o mutante.

    DOIS mutantes, porque o portao tem dois tectos e o segundo ficava sem controlo
    proprio (medido 2026-11-08):

      M1  10x no passo mais lento limpo -- cruza o prazo E o tecto do total.
      M2  +30% num passo cujo resultado CONTINUA abaixo do prazo e cujo acrescimo
          cabe no tecto do total -- logo o `new_over` nao pode disparar e o tecto
          do total nao pode disparar: **so** o ratchet por passo pode ve-lo. Sem
          esta segunda mutacao, apagar o ratchet por passo continuaria a dar
          `NEG-ARM: PASS` por causa da M1 (o mutante apanhado era sempre o mesmo
          tecto), que e' a classe "um controlo que prova outro portao".

    O candidato da M2 e' escolhido por ARITMETICA, nao por nome: o primeiro passo
    (por custo) cujo `x1.30` ainda caiba no prazo e no tecto do total.
    """
    rows = read_steps(CACHE)
    base = load_baseline()
    if base is None:
        print('NEG-ARM IMPOSSIVEL -- baseline ausente')
        return 1
    # A POPULACAO DO CONTROLO E' A DO BASELINE, nao a de omissao (medido
    # 2026-11-08): depois de o baseline passar a ser medido sob a politica
    # `cap40`, um controlo que medisse as linhas de OUTRA politica comparava
    # politicas diferentes, o `judge` respondia "politica diferente" em vez de
    # julgar o mutante e as duas mutacoes passavam a `FAIL (0/2)`. O controlo
    # tem de julgar o MESMO que o portao julga.
    measured = measure(rows, deadline(), (base.get('policy') or None))
    declared = set(base.get('over_deadline') or ())
    ceiling = float(base['total_s']) * RATCHET_PCT
    clean = [r for r in rows
             if r['name'] not in declared and r['elapsed_s'] < deadline()
             and r['elapsed_s'] >= PER_STEP_FLOOR_S] or rows
    if not clean:
        print('NEG-ARM IMPOSSIVEL -- cache sem passos')
        return 1
    worst = max(clean, key=lambda r: r['elapsed_s'])
    # O CANDIDATO DA M2 TEM DE ATRAVESSAR O RATCHET POR PASSO, nao so' caber no
    # prazo: medido 2026-11-08, a M2 escolhia o passo mais caro que cabia e o
    # mutante ficava ABAIXO do `baseline * 1.20` daquele passo (93 s -> 121 s contra
    # um baseline de 219 s), logo o judge nao o nomeava e o controlo dizia
    # `FAIL (1/2)` sem que o juiz tivesse defeito nenhum. A seleccao passa a exigir
    # a travessia; quando nenhum passo a atravessa, e' `CANNOT-MEASURE`, nunca PASS.
    per_base = base.get('per_step') or {}
    sub_deadline = [r for r in clean
                    if r is not worst
                    and r['name'] in per_base
                    and r['elapsed_s'] * 1.30 + 0.1 > per_base[r['name']] * PER_STEP_PCT
                    and r['elapsed_s'] * 1.30 < deadline()
                    and measured['total_s'] + r['elapsed_s'] * 0.30 < ceiling]
    second = max(sub_deadline, key=lambda r: r['elapsed_s']) if sub_deadline else None
    if second is None:
        print('NEG-ARM CANNOT-MEASURE -- nenhum passo ATRAVESSA o ratchet por passo '
              '(+30%) cabendo tambem no prazo E no tecto do total; a M2 nao teria '
              'como isolar o ratchet por passo')
        return 2
    plan = [(worst, 'M1 x10 (prazo + total)', lambda o: max(o * 10.0, deadline() * 1.5)),
            (second, 'M2 +30% (so o ratchet por passo)', lambda o: o * 1.30 + 0.1)]
    base_ok, base_why, _ = judge(measured, base)
    caught = 0
    for row, label, mut in plan:
        original = row['elapsed_s']
        named_before = any(row['name'] in w for w in base_why)
        row['elapsed_s'] = mut(original)
        mutated = measure(rows, deadline(), (base.get('policy') or None))
        ok_after, why_after, _ = judge(mutated, base)
        named_after = any(row['name'] in w for w in why_after)
        ok = named_after and not named_before and not ok_after
        caught += 1 if ok else 0
        print('NEG-ARM %-14s %-32s %s %.2fs -> %.2fs'
              % (row['name'], label, 'APANHADO' if ok else 'PASSOU', original,
                 row['elapsed_s']))
        for line in why_after:
            print('    RED', line)
        row['elapsed_s'] = original
    total_ok = caught == len(plan)
    print('NEG-ARM: %s (%d/%d mutantes apanhados; juiz antes: %s)'
          % ('PASS' if total_ok else 'FAIL', caught, len(plan), base_ok))
    return 1 if total_ok else 0


def _policy_arg(argv):
    for i, a in enumerate(argv):
        if a == '--policy' and i + 1 < len(argv):
            return None if argv[i + 1] in ('none', '') else argv[i + 1]
    return None


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    if '--baseline' in argv:
        rows = read_steps(CACHE)
        measured = measure(rows, deadline(), _policy_arg(argv))
        old = load_baseline() or {}
        accept = ''
        rebase = ''
        for i, a in enumerate(argv):
            if a == '--accept-growth' and i + 1 < len(argv):
                accept = argv[i + 1]
            if a == '--rebase-policy' and i + 1 < len(argv):
                rebase = argv[i + 1]
        allowed = {n for n in accept.split(',') if n}
        # UMA POLITICA NOVA NAO COMPARA COM A ANTIGA (medido 2026-11-08): comparar
        # uma corrida sob tecto de CPU com um baseline medido sem tecto chamava de
        # regressao o preco do tecto. Nesse caso o baseline e' RE-MEDIDO a partir
        # desta corrida e a razao tem de ser DITA (`--rebase-policy "<razao>"`):
        # um rebaseline mudo seria o ratchet a apagar a propria regua.
        old_policy = old.get('policy') or None
        policy = measured.get('policy') or None
        if old_policy != policy and not rebase:
            print('baseline RECUSADO -- a politica de largada mudou (%r -> %r) e um '
                  'rebaseline precisa de razao: --rebase-policy "<por que>"'
                  % (old_policy, policy))
            return 1
        # O BASELINE SO' APERTA POR OMISSAO. Um rebaseline que gravasse em
        # silencio um passo que engordou seria o ratchet a assinar o proprio
        # aumento -- o passo tem de nomear o que aceita em `--accept-growth`.
        grew = []
        for name, secs in sorted(measured['per_step'].items()):
            before = (old.get('per_step') or {}).get(name)
            if before and secs > before * RATCHET_PCT and name not in allowed:
                grew.append('%s %.1fs -> %.1fs' % (name, before, secs))
        if old_policy != policy:
            grew = []      # a regua antiga nao julga a politica nova; a razao foi dita
        if grew:
            print('baseline RECUSADO -- passo(s) engordaram e nao foram aceites: %s'
                  % ' | '.join(grew))
            print('  (nomeie cada um em `--accept-growth a,b,c` se o aumento for o'
                  ' resultado esperado de uma mudanca deliberada)')
            return 1
        notes = dict(old.get('notes') or {})
        if old_policy != policy and rebase:
            notes['rebase'] = ('politica %r -> %r em %s: %s'
                              % (old_policy, policy,
                                 __import__('datetime').date.today().isoformat(), rebase))
        out = {'total_s': measured['total_s'], 'steps': measured['steps'],
               'over_deadline': measured['over_deadline'],
               'per_step': measured['per_step'],
               'policy': policy,
               'notes': notes,
               'target_s': DEFAULT_TARGET_S,
               'measured': __import__('datetime').date.today().isoformat()}
        io.open(BASELINE, 'w', encoding='utf-8', newline='\n').write(
            json.dumps(out, indent=2, sort_keys=True) + '\n')
        print('baseline escrito: %s total_s=%.1f over=%d per_step=%d'
              % (BASELINE, out['total_s'], len(out['over_deadline']),
                 len(out['per_step'])))
        for name in sorted(allowed):
            print('  ACEITE (declarado): %s' % name)
        return 0
    if not os.path.exists(CACHE):
        print('BATTERY-BUDGET CANNOT-MEASURE -- sem %s' % CACHE)
        return 2
    rows = read_steps(CACHE)
    policy = _policy_arg(argv)
    measured = measure(rows, deadline(), policy)
    if not measured['steps']:
        # Populacao VAZIA sob esta politica: a comparacao nao existe, e um PASS
        # aqui seria o verde que nao mediu nada (a lei da casa para populacao zero).
        print('BATTERY-BUDGET CANNOT-MEASURE -- nenhum passo medido sob a politica %r '
              '(%d passo(s) registados sob outras)' % (policy, measured['policy_skipped']))
        return 2
    if measured['policy_skipped']:
        print('BATTERY-BUDGET policy=%r: %d passo(s) de OUTRA politica ficam de fora: %s'
              % (policy, measured['policy_skipped'],
                 ','.join(measured['policy_skipped_names'])))
    base = load_baseline()
    ok, why, gap = judge(measured, base)
    if '--report' in argv:
        report(measured, base, gap)
        return 0
    report(measured, base, gap)
    for line in why:
        print('  RED', line)
    arms = judge_arms()
    bad_arms = [a for a in arms if not a['ok']]
    for a in arms:
        print('  ARM %s %s -- %s' % ('ok  ' if a['ok'] else 'RED ', a['arm'], a['detail']))
    if bad_arms:
        ok = False
        why.append('braco(s) do JUIZ reprovados: %s'
                   % ','.join(a['arm'] for a in bad_arms))
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
