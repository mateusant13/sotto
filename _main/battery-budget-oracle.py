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
#: O HISTORICO DO PROPRIO PASSO, para o ratchet julgar uma AMOSTRA e nao um
#: pico. MEDIDO 2026-11-08: `stutter-caption-oracle --neg-arm` custa **4,4 / 4,4 /
#: 4,7 s** em tres execucoes seguidas e apareceu com **26,8 s** dentro da corrida
#: caged; `console-window-audit` mediu 36,8 / 23,8 / 20,9 s. Uma regua de 20 % sobre
#: UMA leitura reprova o agendador, nao o passo. O juiz passa a usar a MEDIANA das
#: ultimas `HISTORY_N` leituras do mesmo passo (a de agora incluida); com uma so'
#: leitura o numero e' o mesmo de antes, logo o portao nao nasce mais frouxo.
HISTORY = os.path.join(ROOT, '_cache', 'battery-budget-history.json')
HISTORY_N = 3
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
#: E A FOLGA ABSOLUTA, porque uma RAZAO sozinha transforma jitter em regressao
#: (medido 2026-11-08, corrida caged): `red-as-expected-stutter-caption` custou
#: **4,4 / 4,4 / 4,7 s** em tres execucoes seguidas e apareceu com **26,8 s** na
#: corrida; `console-window-audit` **36,8 / 23,8 / 20,9 s** contra um baseline de
#: 21,6 s. Nenhum dos dois e' regressao -- sao picos de agendamento. A regressao que
#: este portao existe para apanhar e' outra escala (224 s -> 1 364 s, +1 140 s), e
#: +30 s de folga continua muito abaixo do prazo de 240 s e do tecto do total.
PER_STEP_SLACK_S = 30.0


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


def load_history(path=HISTORY):
    if not os.path.exists(path):
        return {}
    try:
        data = json.load(io.open(path, encoding='utf-8'))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_history(history, path=HISTORY):
    try:
        with io.open(path, 'w', encoding='utf-8', newline='') as handle:
            json.dump(history, handle, ensure_ascii=False, sort_keys=True)
    except OSError:
        pass  # o historico e' uma ajuda, nunca um portao: falhar a escreve-lo nao muda o veredicto


#: UM CORTE NO PRAZO NAO E' UMA DURACAO (medido 2026-11-11). O `:step` mata o job
#: em `SOTTO_STEP_DEADLINE_S` e o que fica registado e' o PRAZO, nao o custo do
#: passo: `red-as-expected-load-shedding` apareceu com **240,476 s** duas vezes
#: (deadline de 240 s) enquanto o MESMO controlo custa **40,3 s** medido. Com o
#: prazo dentro da janela de tres leituras, a mediana dizia 240,476 e o portao
#: chamava "regressao de +504 %" a um numero produzido pelo proprio cortador.
#: A banda e' de 1 s: um passo cujo custo real caia a menos de 1 s do prazo nao
#: existe nesta populacao (o mais caro legitimo medido e' 168 s), e mesmo que
#: existisse ele continua a ser julgado pela regra de `over-deadline`, que usa a
#: leitura deste corrida -- o que este filtro tira e' so' o PESO dela na mediana.
KILL_BAND_S = 1.0

#: As amostras descartadas por `smooth` nesta invocacao (nome, valor), impressas.
KILL_SAMPLES: list[tuple[str, float]] = []


def _is_kill_sample(value, deadline_s):
    """True quando a leitura e' o PRAZO, e nao o custo: o job foi cortado."""
    return deadline_s and abs(float(value) - float(deadline_s)) <= KILL_BAND_S


def _estimate(series):
    """O estimador do custo de um passo: o MENOR valor observado, nunca a mediana.

    MEDIDO 2026-11-11, e esta e' a correccao da correccao. A historia de
    `panel-commit-stable` era `[65,696, 25,771]`: 65,7 s numa corrida que
    partilhou a maquina com o hook de commit de outra lane, 25,771 s medidos
    sozinho (e 24,6 s numa terceira medicao independente). Com a MEDIANA, a serie
    de dois elementos escolhe o de CIMA -- 65,696 -- e o portao chamou regressao
    de 2x a um passo que nunca custou isso, o que custou DUAS corridas inteiras
    (~50 min) para provar um verde que ja' era verdade.

    Contencao so' ACRESCENTA tempo; nenhum agente torna um passo mais rapido por
    estar a competir com ele. Logo o menor dos ultimos `HISTORY_N` valores e' a
    estimativa sem contencao, e uma regressao REAL sobrevive a ela: as N amostras
    sobem juntas, a antiga sai da janela e o minimo sobe com elas.
    """
    series = [float(x) for x in series]
    return min(series) if series else 0.0


def _old_median(series):
    """A REGRA ANTIGA, mantida so' para o controlo: mediana da serie.

    Nao e' codigo morto: o `--neg-arm` corre-a sobre a MESMA serie e exige que ela
    reprove o passo que a regra de hoje aprova. Sem isso, "o estimador novo e'
    melhor" seria [INFERENCE].
    """
    series = sorted(float(x) for x in series)
    return series[len(series) // 2] if series else 0.0


def _hist_pairs(hist):
    """A serie como pares (carimbo, segundos). Aceita o formato antigo (float puro).

    O CARIMBO E' O QUE TORNA A GRAVACAO IDEMPOTENTE. Medido 2026-11-11: o mesmo
    registo de corrida foi julgado duas vezes (o passo da bateria e uma invocacao
    manual do oraculo) e a serie ficou `[65,696, 25,771, 25,771]` -- a leitura
    repetida pesou duas vezes e a mediana ainda apontou o numero contendido. Uma
    leitura nova so' entra quando o carimbo do registo mudou; repetir o julgamento
    do MESMO registo substitui a ultima amostra em vez de a duplicar.
    """
    out = []
    for item in hist or []:
        if isinstance(item, dict):
            out.append((str(item.get('ts') or ''), float(item.get('s') or 0.0)))
        elif isinstance(item, (int, float)):
            out.append(('', float(item)))
    return out


def smooth(rows, history, policy=None, record=True, deadline_s=None):
    """Troca o `elapsed_s` de cada passo pela estimativa sem contencao da serie.

    `record=False` (o braco negativo) julga o numero CRU: um mutante somado a uma
    estimativa historica podia ser diluido e o controlo deixaria de apanhar.

    Amostras HISTORICAS que sao um corte no prazo (`_is_kill_sample`) saem da
    serie, e cada uma e' impressa (`KILL-SAMPLE`) -- um filtro mudo seria a mesma
    doenca do passo saltado contado como verde. A leitura DESTA corrida NUNCA
    sai: um corte de hoje tem de continuar a reprovar hoje.
    """
    out = []
    for row in rows:
        name = row['name']
        pairs = []
        for ts, value in _hist_pairs(history.get(name)):
            if _is_kill_sample(value, deadline_s):
                KILL_SAMPLES.append((name, value))
                continue
            # AMOSTRA ANTIGA REPETIDA E' UMA AMOSTRA (medido 2026-11-11). O formato
            # antigo nao guardava carimbo, e o defeito que esta correccao cura
            # gravou a MESMA leitura duas vezes (`[29,932, 103,674, 103,674]`).
            # Duas medicoes independentes darem o mesmo valor com tres decimais
            # num passo de segundos nao acontece, logo um valor antigo igual ao
            # anterior e' a leitura repetida e conta uma vez. O corte no prazo fica
            # FORA desta regra: duas mortes no prazo sao duas mortes e o filtro
            # informa as duas (`KILL-SAMPLE`), que e' o numero que os bracos S1-S3
            # exigem.
            if out_prev := (pairs[-1] if pairs else None):
                if out_prev[0] == '' and ts == '' and abs(out_prev[1] - value) < 1e-9:
                    continue
            pairs.append((ts, value))
        # Toda a serie historica sendo corte deixa a lista vazia: a leitura de
        # agora fica SOZINHA (nunca "0 s por falta de dados").
        ts_now = str(row.get('timestamp') or '')
        now = float(row['elapsed_s'])
        if record and pairs and ts_now and pairs[-1][0] == ts_now:
            pairs[-1] = (ts_now, now)      # re-julgar o MESMO registo nao duplica
        else:
            pairs.append((ts_now, now))
        pairs = pairs[-HISTORY_N:]
        if record and (row.get('policy') or None) == (policy or None):
            # So' grava leituras da MESMA politica: uma serie que mistura cap40 com
            # corridas sem tecto compararia precos diferentes (a mesma armadilha que
            # o `measure` ja' evita).
            history[name] = [{'ts': t, 's': round(v, 3)} for t, v in pairs]
        merged = dict(row)
        merged['elapsed_s'] = round(_estimate([v for _, v in pairs]), 3)
        merged['raw_s'] = now
        merged['series'] = [round(v, 3) for _, v in pairs]
        out.append(merged)
    return out


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
            if secs > before * PER_STEP_PCT and (secs - before) > PER_STEP_SLACK_S:
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


def smooth_arms():
    """OS BRACOS DO FILTRO DE CORTE, puros: nenhum le' disco, nenhum escreve historico.

    Nasceram do defeito MEDIDO na corrida de 2026-11-11: a historia de
    `red-as-expected-load-shedding` era `[240,476, 240,476, 40,256]` -- duas
    mortes no prazo de 240 s e o custo real do controlo -- e a mediana (240,476)
    fez o portao chamar "regressao de +504 %" a um numero que o proprio cortador
    escreveu. O filtro novo tira da serie as amostras historicas que sao o PRAZO,
    e estes bracos existem porque um filtro sem controlo e' o mesmo que nenhum.
    """
    arms = []

    def arm(name, hist, current, want_med, want_dropped, deadline_s=240.0):
        saved = list(KILL_SAMPLES)
        KILL_SAMPLES.clear()
        rows = [{'name': 'x', 'elapsed_s': float(current)}]
        out = smooth(rows, {'x': list(hist)}, None, record=False,
                     deadline_s=deadline_s)
        dropped = list(KILL_SAMPLES)
        KILL_SAMPLES[:] = saved
        med = out[0]['elapsed_s']
        good = (abs(med - want_med) < 0.01) and (len(dropped) == want_dropped)
        arms.append({'arm': name, 'ok': good,
                     'detail': 'mediana=%.3f (want %.3f); descartadas=%d (want %d)'
                               % (med, want_med, len(dropped), want_dropped)})

    arm('S1 duas mortes no prazo nao fazem a mediana do controlo (o caso medido)',
        [240.476, 240.476, 40.256], 40.256, 40.256, 2)
    # S2: com a historia sendo SO' cortes, a leitura de agora e' a unica medida --
    # se o filtro comesse tambem a de hoje, a mediana cairia para o valor antigo e
    # um passo morto no prazo passaria a "rapido". O valor esperado e' o de HOJE.
    arm('S2 a leitura DESTA corrida nunca e\' filtrada: um corte de hoje reprova hoje',
        [240.476, 240.476], 240.4, 240.4, 2)
    arm('S3 so\' cortes na historia: a leitura de agora fica sozinha',
        [240.476, 240.476], 62.0, 62.0, 2)
    # S4: a mediana de uma serie PAR e' o elemento de cima (comportamento antigo,
    # nao tocado por este filtro); o que a arm prova e' `descartadas=0` -- um custo
    # legitimo de 100 s nao e' confundido com um corte no prazo.
    arm('S4 um custo legitimo de 100 s nao e\' descartado (a estimativa e o menor)',
        [100.0], 110.0, 100.0, 0)
    arm('S5 historia vazia continua devolvendo a leitura de agora',
        [], 5.0, 5.0, 0)
    # S6 O CASO MEDIDO DE 2026-11-11, que custou duas corridas inteiras: uma
    # leitura contendida (65,696 s, a maquina a partilhar com o hook de commit de
    # outra lane) ao lado da leitura quieta (25,771 s, e 24,6 s numa terceira
    # medicao). A mediana escolhia 65,696 e reprovava; o menor da' a verdade.
    arm('S6 uma corrida contendida nao engorda um passo que nunca custou isso',
        [65.696, 25.771], 25.771, 25.771, 0)
    # S7 ... e uma regressao REAL sobrevive: todas as leituras da janela subiram.
    # Aqui a serie gravada E' a janela (record=True), porque o que se mede e' a
    # ESTIMATIVA, nao a leitura de agora -- `record=False` julga o numero cru.
    arms.append({'arm': 'S7 regressao real: todas as leituras da janela subiram',
                 'ok': abs(_estimate([70.0, 72.0, 71.0]) - 70.0) < 0.01,
                 'detail': 'estimativa=%.3f (want 70.000, todas acima do baseline)'
                           % _estimate([70.0, 72.0, 71.0])})
    return arms


def smooth_idempotent_arms():
    """O HISTORICO NAO DUPLICA quando o MESMO registo e' julgado duas vezes.

    Medido 2026-11-11: o passo `battery-budget` corre dentro da bateria e o mesmo
    oraculo foi invocado a mao logo depois; a serie de `red-as-expected-battery-plan`
    ficou `[29,932, 103,674, 103,674]` -- a leitura repetida pesou duas vezes, e
    uma unica corrida contendida passou a valer como duas. A gravacao passa a ser
    idempotente pelo carimbo do registo, e estes bracos provam as duas metades.
    """
    arms = []
    # I1: o mesmo carimbo gravado duas vezes deixa a serie com UMA amostra.
    hist = {}
    for _ in range(2):
        smooth([{'name': 'x', 'elapsed_s': 103.674, 'policy': 'cap40',
                'timestamp': '2026-11-11T18:40'}],
               hist, 'cap40', True, 240.0)
    series = [p['s'] for p in hist.get('x') or []]
    arms.append({'arm': 'I1 re-julgar o mesmo registo nao duplica a amostra',
                 'ok': len(series) == 1,
                 'detail': 'serie=%r (want 1 amostra)' % (series,)})
    # I2: um carimbo NOVO entra e a serie cresce ate' `HISTORY_N`, e o valor
    # antigo continua na janela (o minimo veio dele).
    for ts in ('2026-11-11T19:00', '2026-11-11T19:20', '2026-11-11T19:40'):
        smooth([{'name': 'x', 'elapsed_s': 25.771, 'policy': 'cap40',
                'timestamp': ts}], hist, 'cap40',
               True, 240.0)
    series = [p['s'] for p in hist.get('x') or []]
    arms.append({'arm': 'I2 carimbo novo entra e a janela fica em HISTORY_N',
                 'ok': len(series) == HISTORY_N and 103.674 not in series,
                 'detail': 'serie=%r (want %d amostras, sem a antiga)'
                           % (series, HISTORY_N)})
    # I3: o OLD (formato float puro) continua a ser lido -- um historico gravado
    # pela versao anterior nao pode virar "sem dados" e apagar a smoothed serie.
    rows = smooth([{'name': 'x', 'elapsed_s': 30.0, 'timestamp': 'T'}],
                  {'x': [65.696, 25.771]}, None, False, 240.0)
    arms.append({'arm': 'I3 serie no formato antigo (floats) continua a ser lida',
                 'ok': abs(rows[0]['elapsed_s'] - 25.771) < 0.01,
                 'detail': 'estimativa=%.3f (want 25.771)' % rows[0]['elapsed_s']})
    # I4 O FALSIFICADOR DO ESTIMADOR: sobre a MESMA serie do S6, a regra ANTIGA
    # (mediana) tem de REPROVAR o passo e a de hoje tem de o aprovar. Sem esta
    # metade, "o menor e' melhor" seria [INFERENCE] -- e foi exactamente essa a
    # conclusao errada que custou duas corridas de 20 min.
    series = [65.696, 25.771]
    old = _old_median(series)
    new = _estimate(series)
    arms.append({'arm': 'I4 a regra antiga (mediana) reprova o caso que a de hoje aprova',
                 'ok': old > 25.771 * 1.2 and new <= 25.771 * 1.2,
                 'detail': 'mediana=%.3f (RED) vs menor=%.3f (GREEN)' % (old, new)})
    return arms


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
    arm('A2 um passo +117% (30 -> 65 s) reprova e o NOMEIA',
        m({'a': 65.0, 'b': 35, 'c': 3, 'tiny': 0.3}), False, 'a 30.0s -> 65.0s')
    arm('A3 total IGUAL e um passo 30->65 reprova (o caso que passava)',
        m({'a': 65.0, 'b': 20.0, 'c': 15.0, 'tiny': 0.3}, total=100.3), False,
        'a 30.0s -> 65.0s')
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
    # A10 e' o caso MEDIDO que obrigou a folga absoluta: 3,7 s -> 26,8 s (+23,1 s)
    # NAO pode reprovar -- o passo tem 4,5 s de custo real e o pico e' do agendador.
    arm('A10 pico de 3,7s -> 26,8s nao reprova (folga absoluta de 30s)',
        m({'a': 20, 'b': 40, 'c': 0, 'tiny': 0.3, 'peak': 26.8}), True)
    # A11 impede que a folga vire isencao: +31 s acima do piso continua a reprovar.
    arm('A11 +31s acima do piso (40 -> 71 s) reprova e o NOMEIA',
        m({'a': 5, 'b': 71, 'c': 20, 'tiny': 0.3}, total=96.3), False,
        'b 40.0s -> 71.0s')
    return arms


def ratchet_named(why):
    """Os NOMES que a razao do ratchet POR PASSO cita.

    Nao e' um `in` sobre a razao inteira: o total e o prazo tambem nomeiam passos,
    e a M2 tem de ser apanhada PELO RATCHET, nao por um RED que ja' existia.
    """
    names = set()
    for line in why:
        if 'engordaram alem do ratchet' not in line:
            continue
        tail = line.split(':', 1)[1] if ':' in line else ''
        for part in tail.split('|'):
            word = part.strip().split(' ')[0]
            if word:
                names.add(word)
    return names


def rebase_growth(old_per_step, new_per_step, allowed=()):
    """Os passos que engordaram, pela MESMA regua do `judge`.

    Nasceu de um defeito medido 2026-11-11: o `--baseline` julgava com
    `before * 1.05` sobre TUDO, sem piso nem folga, e recusou um rebaseline
    legitimo citando dezoito passos de sub-segundo (`claims-date 0.3 -> 0.8`,
    `panel-deps 0.3 -> 0.7`, `live-code-freshness 0.4 -> 0.5`). Um rebaseline
    mais estrito do que o portao que ele serve nunca passa, e o trabalho que ele
    existe para registar fica bloqueado por ruido de arranque.

    A regua e' a do `judge`, linha por linha: piso `PER_STEP_FLOOR_S` sobre o
    MAIOR dos dois lados (um passo que nasceu pequeno e engordou nao se esconde
    atras do proprio passado), `PER_STEP_PCT` sobre o valor anterior e a folga
    ABSOLUTA `PER_STEP_SLACK_S`. Nomear o passo em `allowed` e' a declaracao de
    que o crescimento e' resultado de uma mudanca deliberada.
    """
    allowed = {n for n in (allowed or ()) if n}
    grew = []
    for name, secs in sorted((new_per_step or {}).items()):
        before = (old_per_step or {}).get(name)
        if not before or name in allowed:
            continue
        if max(before, secs) < PER_STEP_FLOOR_S:
            continue
        if secs > before * PER_STEP_PCT and (secs - before) > PER_STEP_SLACK_S:
            grew.append('%s %.1fs -> %.1fs' % (name, before, secs))
    return grew


def rebase_arms():
    """OS BRACOS DO REBASELINE, puros: nenhum le' o disco.

    Nasceram com a cura de 2026-11-11. Sem eles, o rebaseline podia voltar a
    julgar com uma regua propria e nenhum braco caia -- a doenca que a cura
    fechou e' exactamente a de um instrumento sem controlo.
    """
    arms = []

    def arm(name, old, new, allowed, want):
        got = rebase_growth(old, new, allowed)
        good = bool(got) == bool(want) and (not want or any(want in g for g in got))
        arms.append({'arm': name, 'ok': good,
                     'detail': 'grew=%r (want %r)' % (got, want)})

    # A12 e' o caso MEDIDO: dezoito passos de sub-segundo recusaram um rebaseline
    # legitimo. Ruido de arranque abaixo do piso nao bloqueia nada.
    arm('A12 rebaseline: sub-segundo (0,3 -> 0,8 s) nao bloqueia',
        {'claims-date': 0.3, 'panel-deps': 0.3, 'live-code-freshness': 0.4},
        {'claims-date': 0.8, 'panel-deps': 0.7, 'live-code-freshness': 0.5},
        (), None)
    # A13 impede a isencao total: um passo acima do piso que engordou 2x TEM de
    # ser nomeado, senao o rebaseline assina em silencio o proprio aumento.
    arm('A13 rebaseline: 30 -> 65 s acima do piso e\' nomeado',
        {'paint-live-show': 30.0}, {'paint-live-show': 65.0}, (), 'paint-live-show')
    # A14: nomear o passo e' a declaracao que o `--accept-growth` carrega.
    arm('A14 rebaseline: o mesmo 30 -> 65 s NOMEADO e\' aceite',
        {'paint-live-show': 30.0}, {'paint-live-show': 65.0},
        ('paint-live-show',), None)
    # A15: a folga absoluta tambem vale aqui -- 3,7 -> 26,8 s e' pico de agendador.
    arm('A15 rebaseline: pico de 3,7 -> 26,8 s nao bloqueia (folga de 30 s)',
        {'peak': 3.7}, {'peak': 26.8}, (), None)
    # A16: um passo QUE NASCEU pequeno e engordou para 200 s e' julgado, nunca
    # isento pelo proprio passado (o piso e' sobre o MAIOR dos dois lados).
    arm('A16 rebaseline: passo que nasceu em 4,9 s e foi a 200 s e\' nomeado',
        {'tiny': 4.9}, {'tiny': 200.0}, (), 'tiny')
    # A17: passo novo (sem valor anterior) nao e' crescimento -- e' populacao.
    arm('A17 rebaseline: passo novo nao e\' crescimento',
        {}, {'brand-new': 102.7}, (), None)
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

    O candidato da M2 e' escolhido por ARITMETICA, nao por nome: o passo de maior
    custo (fora o da M1) cujo `+folga+10 s` ainda caiba no prazo.

    MEDIDO 2026-11-11 (corrida da bateria): `red-as-expected-load-shedding` morreu
    no prazo de 240 s, o total ficou ACIMA do tecto, e a condicao antiga da M2
    (`total + folga + 10 s < tecto`) deixou de ter candidato -- o controlo saia
    `CANNOT-MEASURE` (rc 2) exactamente na corrida em que o gate estava RED e o
    controlo era mais necessario. A cura tem duas metades: o candidato da M2 deixa
    de exigir folga no TOTAL (a folga que ele precisa e' no PRAZO, porque o
    mutante nao pode virar `over_deadline`), e a testemunha da M2 passa a ser a
    razao do ratchet POR PASSO que nomeia o passo -- nao "alguma coisa vermelha",
    que num gate ja' RED seria verdade sem o ratchet existir.
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
    real = measure(rows, deadline(), (base.get('policy') or None))
    declared = set(base.get('over_deadline') or ())
    per_base = base.get('per_step') or {}
    # O CONTROLO JULGA UMA BASE LIMPA, NAO A CORRIDA DE HOJE (medido 2026-11-11).
    # O `neg_arm` lia a corrida que acabou de correr, e essa corrida e' uma
    # AMOSTRA: numa maquina partilhada ela chega 3-8x mais cara e o `judge`
    # reprova ANTES de qualquer mutacao -- o controlo entao dizia
    # `CANNOT-MEASURE` (rc 2) e o passo virava RED numa corrida em que o codigo
    # estava certo. Duas corridas inteiras (~50 min) foram gastas assim hoje.
    # A pergunta do controlo e' "o juiz NOMEIA um passo que engordou?", nao
    # "esta' a maquina calma?": a base sintetica e' o baseline -- o proprio
    # numero que o ratchet compara --, logo o controlo mede o juiz e mais nada.
    # A corrida real continua a ser publicada, como INFORMACAO.
    print('NEG-ARM base: sintetica (per_step do baseline); corrida real: total=%.1fs '
          'steps=%d (informativo)' % (real['total_s'], real['steps']))
    measured = {'policy': (base.get('policy') or None), 'steps': len(per_base),
                'total_s': round(sum(per_base.values()), 1),
                'policy_skipped': 0, 'policy_skipped_names': [],
                'over_deadline': [], 'per_step': dict(per_base),
                'slowest': sorted(((n, v) for n, v in per_base.items()),
                                  key=lambda kv: -kv[1])[:10]}
    clean = [{'name': n, 'elapsed_s': v} for n, v in per_base.items()
             if v < deadline() and v >= PER_STEP_FLOOR_S]
    if not clean:
        print('NEG-ARM IMPOSSIVEL -- baseline sem passo utilizavel')
        return 1
    worst = max(clean, key=lambda r: r['elapsed_s'])
    # O CANDIDATO DA M2 TEM DE ATRAVESSAR O RATCHET POR PASSO, nao so' caber no
    # prazo: medido 2026-11-08, a M2 escolhia o passo mais caro que cabia e o
    # mutante ficava ABAIXO do `baseline * 1.20` daquele passo (93 s -> 121 s contra
    # um baseline de 219 s), logo o judge nao o nomeava e o controlo dizia
    # `FAIL (1/2)` sem que o juiz tivesse defeito nenhum. A seleccao passa a exigir
    # a travessia; quando nenhum passo a atravessa, e' `CANNOT-MEASURE`, nunca PASS.
    per_base = base.get('per_step') or {}
    # A ISOLACAO DA M2 NAO PODE DEPENDER DE O GATE ESTAR VERDE. Medido 2026-11-11:
    # com `red-as-expected-load-shedding` morto no prazo (240,5 s), o total da
    # corrida ja' estava ACIMA do tecto, a condicao antiga
    # (`total + folga + 10 < tecto`) era falsa para TODOS os passos e o controlo
    # saia `CANNOT-MEASURE` (rc 2) exactamente quando o gate estava vermelho --
    # isto e', o controlo ficava cego no unico momento em que era preciso. O que
    # prova o isolamento passa a ser o NOME do passo na razao do ratchet POR PASSO
    # (`witness` abaixo), nao a ausencia do RED do total.
    # A M2 CRESCE EM SEGUNDOS, nao em percentagem: com a folga absoluta de 30 s a
    # regra so' dispara acima dela, logo um mutante de +30% num passo de 60 s
    # (18 s) ficaria INVISIVEL e o controlo diria `PASSOU` sem o juiz ter defeito.
    # O mutante passa a `+FOLGA+10 s`, que e' exactamente o limiar que a regra usa.
    #
    # E O CANDIDATO TEM DE ATRAVESSAR O RATCHET CONTRA O BASELINE DO PASSO, medido
    # 2026-11-11: o comentario acima ja' dizia "exige a travessia" mas o codigo so'
    # verificava prazo/tecto, e o primeiro candidato escolhido (`...youtube-cdp-
    # source`, 82,8 s -> 122,9 s) ficou ABAIXO do `baseline * 1.20` dele -- o
    # mutante nao era nomeado e o controlo dizia `PASSOU` sem o juiz ter defeito.
    def _m2_growth(o):
        return o + PER_STEP_SLACK_S + 10.1

    crossing = [r for r in clean
                if r is not worst
                and r['name'] in per_base
                and _m2_growth(r['elapsed_s']) < deadline()
                and _m2_growth(r['elapsed_s']) > per_base[r['name']] * PER_STEP_PCT
                and (_m2_growth(r['elapsed_s']) - per_base[r['name']])
                > PER_STEP_SLACK_S]
    second = max(crossing, key=lambda r: r['elapsed_s']) if crossing else None
    if second is None:
        print('NEG-ARM CANNOT-MEASURE -- nenhum passo ATRAVESSA o ratchet por passo '
              '(+folga+10 s) cabendo no prazo; a M2 nao teria como isolar o ratchet '
              'por passo')
        return 2
    plan = [(worst, 'M1 x10 (prazo + total)',
             lambda o: max(o * 10.0, deadline() * 1.5), 'any'),
            (second, 'M2 +folga+10s (so o ratchet por passo)',
             _m2_growth, 'ratchet')]
    base_ok, base_why, _ = judge(measured, base)
    # UM JUIZ QUE JA' REPROVA NAO JULGA MUTANTE (medido 2026-11-11). A testemunha
    # da M1/M2 e' "o mutante NOMEIA o passo, e o passo nao estava nomeado antes".
    # Com a corrida ja' vermelha -- naquele dia, porque outra lane media na mesma
    # maquina e TODO passo apareceu 3-8x mais caro --, `named_before` e' verdadeiro
    # para os dois e o controlo conta 2/4, devolve 0, e o passo diz `CONTROL
    # FAILED: rc=0`, que se le' como "o controlo nao pegou" quando o que ha' e' um
    # instrumento sem base para medir. A resposta honesta e' `CANNOT-MEASURE`, e o
    # rc=2 e' exatamente a convencao da casa para isso (erro de SETUP, nunca verde).
    if not base_ok:
        print('NEG-ARM CANNOT-MEASURE -- o juiz ja\' reprova ANTES de qualquer '
              'mutacao, logo a testemunha da M1/M2 nao distingue o mutante de um '
              'RED pre-existente:')
        for line in base_why:
            print('    RED', line)
        print('  (a BASE sintetica e\' o proprio baseline e tem de passar o juiz; '
              'se nao passa, o defeito e\' do baseline, nao da maquina -- '
              'uma maquina ocupada deixou de poder cegar este controlo)')
        return 2
    caught = 0
    for row, label, mut, witness in plan:
        original = row['elapsed_s']
        # A TESTEMUNHA DA M2 E' A RAZAO DO RATCHET POR PASSO, e nao "alguma coisa
        # ficou vermelha": com o total ja' acima do tecto (o caso medido hoje), o
        # `not ok_after` sozinho nao distingue o mutante de um RED pre-existente.
        def names(why, want_ratchet=(witness == 'ratchet')):
            hit = []
            for line in why:
                if want_ratchet:
                    if row['name'] in ratchet_named([line]):
                        hit.append(line)
                elif row['name'] in line:
                    hit.append(line)
            return hit
        named_before = names(base_why)
        row['elapsed_s'] = mut(original)
        # O MUTANTE TEM DE ATRAVESSAR O MESMO CAMINHO QUE O JUIZ LE' (medido
        # 2026-11-11): a versao anterior mutava a linha e chamava `measure(rows)`
        # -- que reconstroi tudo a partir do CACHE REAL e deitava a mutacao fora.
        # Enquanto a base do controlo era a corrida de hoje isso passava por
        # coincidencia (a linha vinha do mesmo `rows`); com a base sintetica a
        # mutacao caia no vazio e a M2 dizia `PASSOU` sem o juiz ter defeito.
        mutated = dict(measured)
        mutated['per_step'] = dict(measured['per_step'])
        mutated['per_step'][row['name']] = round(row['elapsed_s'], 1)
        mutated['total_s'] = round(sum(mutated['per_step'].values()), 1)
        mutated['over_deadline'] = sorted(
            set(base.get('over_deadline') or ())
            | {n for n, v in mutated['per_step'].items() if v >= deadline()})
        mutated['slowest'] = sorted(mutated['per_step'].items(),
                                    key=lambda kv: -kv[1])[:10]
        ok_after, why_after, _ = judge(mutated, base)
        named_after = names(why_after)
        ok = bool(named_after) and not named_before and not ok_after
        caught += 1 if ok else 0
        print('NEG-ARM %-14s %-32s %s %.2fs -> %.2fs'
              % (row['name'], label, 'APANHADO' if ok else 'PASSOU', original,
                 row['elapsed_s']))
        for line in why_after:
            print('    RED', line)
        row['elapsed_s'] = original
    # M3: o FILTRO DE CORTE. Desligar a banda (0 s) e' a mutacao do filtro, e o
    # braco S1 tem de cair -- senao o filtro novo entrava na casa sem controlo.
    global KILL_BAND_S
    saved_band = KILL_BAND_S
    KILL_BAND_S = 0.0
    try:
        m3 = [a for a in smooth_arms() if a['arm'].startswith('S1')][0]
    finally:
        KILL_BAND_S = saved_band
    m3_ok = not m3['ok']
    caught += 1 if m3_ok else 0
    print('NEG-ARM %-14s %-32s %s %s'
          % ('KILL_BAND=0', 'M3 filtro de corte desligado',
             'APANHADO' if m3_ok else 'PASSOU', m3['detail']))
    # M4: A REGUA DO REBASELINE. A mutacao devolve `before * 1.05` sobre TUDO --
    # a forma que recusou dezoito passos de sub-segundo -- e o A12 tem de cair.
    # Sem este braco, alguem reintroduz a regua propria e nenhuma arm se mexe.
    saved_pct, saved_floor, saved_slack = (PER_STEP_PCT, PER_STEP_FLOOR_S,
                                           PER_STEP_SLACK_S)
    globals()['PER_STEP_PCT'] = 1.05
    globals()['PER_STEP_FLOOR_S'] = 0.0
    globals()['PER_STEP_SLACK_S'] = 0.0
    try:
        m4 = [a for a in rebase_arms() if a['arm'].startswith('A12')][0]
    finally:
        globals()['PER_STEP_PCT'] = saved_pct
        globals()['PER_STEP_FLOOR_S'] = saved_floor
        globals()['PER_STEP_SLACK_S'] = saved_slack
    m4_ok = not m4['ok']
    caught += 1 if m4_ok else 0
    print('NEG-ARM %-14s %-32s %s %s'
          % ('REBASE 1.05', 'M4 regua propria do rebaseline',
             'APANHADO' if m4_ok else 'PASSOU', m4['detail']))
    # M5: O ESTIMADOR. Repor a MEDIANA (a regra que custou duas corridas de 20 min
    # em 2026-11-11) no lugar do menor e exigir que a I4 caia. Sem este braco,
    # alguem devolve a mediana e nenhuma arm se mexe -- foi exatamente assim que a
    # correccao de 2026-11-11 nasceu ja' errada.
    saved_est = globals()['_estimate']
    globals()['_estimate'] = _old_median
    try:
        m5 = [a for a in smooth_idempotent_arms() if a['arm'].startswith('I4')][0]
    finally:
        globals()['_estimate'] = saved_est
    m5_ok = not m5['ok']
    caught += 1 if m5_ok else 0
    print('NEG-ARM %-14s %-32s %s %s'
          % ('ESTIMADOR', 'M5 mediana no lugar do menor',
             'APANHADO' if m5_ok else 'PASSOU', m5['detail']))
    # M6: A GRAVACAO IDEMPOTENTE. Desligar a comparacao de carimbo (ts sempre
    # diferente) faz a serie duplicar a mesma leitura e a I1 cai.
    global _hist_pairs
    saved_pairs = _hist_pairs
    def _no_ts(hist):
        return [(str(i), s) for i, (_, s) in enumerate(saved_pairs(hist))]
    globals()['_hist_pairs'] = _no_ts
    try:
        m6 = [a for a in smooth_idempotent_arms() if a['arm'].startswith('I1')][0]
    finally:
        globals()['_hist_pairs'] = saved_pairs
    m6_ok = not m6['ok']
    caught += 1 if m6_ok else 0
    print('NEG-ARM %-14s %-32s %s %s'
          % ('SEM DEDUPE', 'M6 carimbo sempre novo (serie duplica)',
             'APANHADO' if m6_ok else 'PASSOU', m6['detail']))
    plan_n = len(plan) + 4
    total_ok = caught == plan_n
    print('NEG-ARM: %s (%d/%d mutantes apanhados; juiz antes: %s)'
          % ('PASS' if total_ok else 'FAIL', caught, plan_n, base_ok))
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
        # O REBASELINE JULGA COM A MESMA REGUA DO PORTAO (medido 2026-11-11). A
        # primeira forma usava `before * 1.05` sobre TUDO, sem piso nem folga, e
        # recusou um rebaseline legitimo citando dezoito passos de sub-segundo
        # (`claims-date 0.3 -> 0.8`, `panel-deps 0.3 -> 0.7`, `live-code-freshness
        # 0.4 -> 0.5`): um rebaseline mais estrito do que o portao que ele serve
        # nunca passa, e o trabalho que ele existe para registar fica bloqueado.
        # A regua e' a do `judge`: piso de `PER_STEP_FLOOR_S`, `PER_STEP_PCT` e a
        # folga absoluta de `PER_STEP_SLACK_S`.
        grew = rebase_growth(old.get('per_step') or {}, measured['per_step'],
                             allowed)
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
    history = load_history()
    rows = smooth(rows, history, policy, deadline_s=deadline())
    save_history(history)
    for name, value in KILL_SAMPLES:
        print('KILL-SAMPLE dropped step=%s s=%.3f prazo=%.0fs -- o registo era o '
              'CORTE, nao o custo do passo' % (name, value, deadline()))
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
    arms = judge_arms() + smooth_arms() + smooth_idempotent_arms() + rebase_arms()
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
