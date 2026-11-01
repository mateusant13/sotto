#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# NO-BUG: e o registo E o portao dos bugs; nao corrige nenhum, impede que "fixed" passe por "verified"
"""BUG-LEDGER ORACLE -- "fixed" nunca pode ser apresentado como "verified".

A LEI (manager, `state/research/bug-hunt-workflow-approaches.md`, 2026-10-23):
*"Suggested states: `reported -> reproduced -> cause isolated -> fixed ->
independently verified -> recurrence watch`. 'Reported' and 'fixed' must never be
presented as 'verified'."* E a mesma nota: *"If a report cannot be reproduced,
improve its evidence or mark it unknown rather than inventing a fix."*

PORQUE UM FICHEIRO E UM PORTAO, E NAO UMA TABELA NUM DOCUMENTO. Uma tabela de
estados escrita a mao e uma opiniao: ninguem a impede de dizer `verified` sem
ninguem ter verificado. Este portao exige, para CADA estado alcancado:

  reported          data + as palavras do dono (verbatim)
  reproduced        um FICHEIRO-fonte e a evidencia textual que tem de estar la
                    (a reproducao e um facto verificavel, nao uma frase)
  cause-isolated    a causa E uma capsula de incidente que existe no disco
  fixed             um passo da BATERIA (regression.gate) e o seu braco negativo
                    (regression.neg_arm) -- ambos nomeados em
                    `_main/_audit-verify-all.cmd`, logo um "fixed" nao pode
                    apontar para um portao que nao existe ou que nao corre
  verified          data, instrumento, e QUEM verificou -- que nao pode ser o
                    autor (uma lane nao se auto-verifica)
  recurrence-watch  instrumento E janela (uma vigia sem janela e uma promessa)

O estado `fixed` IMPRIME "FIXED, NOT VERIFIED" em letras grandes: e o estado
honesto deste repositorio hoje, porque nao ha uma segunda lane a verificar nem
uma corrida real da app depois da cura.

    python _main/bug-ledger-oracle.py            # rc=0 verde, rc=2 vermelho
    python _main/bug-ledger-oracle.py --neg-arm  # rc=1 POR DESENHO

NAO lanca nada: le o ledger, os ficheiros que ele cita, e a bateria. Pode entrar
na bateria.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LEDGER = os.path.join(HERE, 'bug-ledger.json')
BATTERY = os.path.join(HERE, '_audit-verify-all.cmd')
STATES = ['reported', 'reproduced', 'cause-isolated', 'fixed', 'verified',
          'recurrence-watch']


def _read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def load(path=LEDGER):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def battery_has_step(battery_text, name):
    """O passo existe na bateria E e registado (record ou expectred)."""
    if not name:
        return False
    stepped = re.search(r'call :step [^\r\n]*?\b%s\b' % re.escape(name),
                        battery_text) is not None
    recorded = ('call :record %s' % name) in battery_text \
        or ('call :expectred %s' % name) in battery_text
    return stepped and recorded


REGRESSION_STYLES = ('example', 'property', 'stateful', 'differential',
                     'replay')
SIBLING_VERDICTS = ('clean', 'benign', 'fixed', 'unproven')
SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _days(a, b):
    """(b - a) em dias, ou None se alguma data nao for AAAA-MM-DD."""
    from datetime import date
    try:
        ya, ma, da = (int(x) for x in a.split('-'))
        yb, mb, db = (int(x) for x in b.split('-'))
        return (date(yb, mb, db) - date(ya, ma, da)).days
    except (AttributeError, ValueError):
        return None


def check_bug(bug, states, author, battery_text, repo=REPO):
    """(falhas, estado, avisos) para UM bug. Campos v2 sao OBRIGATORIOS.

    A terceira nota (`bug-hunting-workflow-findings.md`, consultgpt, 2026-10-23
    20:33) chama ao metodo um *\"hypothetico-deductive loop: observe, form one
    hypothesis, predict an observation, and falsify it\"*. Uma hipotese sem um
    falsificador escrito nao e uma hipotese: e uma narrativa. Por isso o campo
    `falsifier` e exigido, e nao e opcional nem quando a causa parece obvia.
    """
    fails = []
    state = bug.get('state')

    # `unknown` e um estado LEGITIMO e nao um buraco: a nota diz \"If a report
    # cannot be reproduced, improve its evidence or mark it unknown rather than
    # inventing a fix\". Exige o proximo passo falsificavel, e mais nada.
    if state == 'unknown':
        rep = bug.get('reported') or {}
        if not rep.get('date') or not rep.get('verbatim'):
            fails.append('unknown sem as palavras do dono (o que se reportou?)')
        if not bug.get('next_step'):
            fails.append('unknown sem `next_step`: desconhecido sem proximo '
                         'passo e uma promessa, nao um estado')
        return fails, state, ['UNKNOWN -- nao reproduzido; nao e defeito provado']

    if state not in states:
        return ['estado %r nao esta na lista declarada' % (state,)], state, []
    idx = states.index(state)

    def reached(s):
        return s in states and states.index(s) <= idx

    if not bug.get('class'):
        fails.append('sem `class`: sem a CLASSE do defeito nao ha inquerito de '
                     'irmaos possivel')

    rep = bug.get('reported') or {}
    if not rep.get('date') or not rep.get('verbatim'):
        fails.append('reported sem data ou sem as palavras do dono')

    if reached('reproduced'):
        r = bug.get('reproduced') or {}
        src = r.get('source')
        ev = r.get('evidence')
        if not src or not ev:
            fails.append('reproduced sem ficheiro-fonte ou sem evidencia')
        else:
            path = os.path.join(repo, *src.replace('/', os.sep).split(os.sep))
            if not os.path.isfile(path):
                fails.append('reproduced cita um ficheiro que nao existe: %s' % src)
            elif ev not in _read(path):
                fails.append('reproduced: a evidencia nao esta em %s: %r'
                             % (src, ev[:60]))
        # AMBIENTE e REVISAO: a nota lista-os como campos da capsula. Sem eles
        # uma reproducao nao se repete noutra maquina nem se compara entre dias.
        if not r.get('environment'):
            fails.append('reproduced sem `environment` (em que maquina/config?)')
        if not r.get('revision'):
            fails.append('reproduced sem `revision` (em que revisao do codigo?)')
        sha = r.get('artifact_sha')
        if not sha:
            fails.append('reproduced sem `artifact_sha`: o artefacto do defeito '
                         'nao tem identidade')
        elif sha != 'unrecorded' and not SHA256.match(sha):
            fails.append('artifact_sha nao e um sha256 de 64 hex: %r' % (sha,))
        elif sha == 'unrecorded' and not r.get('artifact_sha_note'):
            fails.append('artifact_sha=unrecorded sem `artifact_sha_note`: '
                         'dizer PORQUE nao foi guardado')

    if reached('cause-isolated'):
        if not bug.get('cause'):
            fails.append('cause-isolated sem causa escrita')
        if not bug.get('hypothesis'):
            fails.append('cause-isolated sem `hypothesis`')
        if not bug.get('falsifier'):
            fails.append('cause-isolated sem `falsifier`: uma hipotese sem o '
                         'que a refutaria nao e uma hipotese')
        if not bug.get('minimal_repro'):
            fails.append('cause-isolated sem `minimal_repro` (delta debugging: '
                         'a reproducao foi minimizada?)')
        cap = bug.get('capsule')
        if not cap:
            fails.append('cause-isolated sem capsula de incidente')
        else:
            path = os.path.join(repo, *cap.replace('/', os.sep).split(os.sep))
            if not os.path.isfile(path):
                fails.append('a capsula nao existe: %s' % cap)

    if reached('fixed'):
        reg = bug.get('regression') or {}
        for key in ('gate', 'neg_arm'):
            if not reg.get(key):
                fails.append('fixed sem regression.%s' % key)
            elif not battery_has_step(battery_text, reg[key]):
                fails.append('regression.%s=%r nao e um passo da bateria'
                             % (key, reg[key]))
        style = reg.get('style')
        if not style:
            fails.append('fixed sem regression.style')
        elif style not in REGRESSION_STYLES:
            fails.append('regression.style=%r nao esta em %r'
                         % (style, list(REGRESSION_STYLES)))
        cov = bug.get('coverage_gate')
        if cov and not battery_has_step(battery_text, cov):
            fails.append('coverage_gate=%r nao e um passo da bateria' % (cov,))
        # IRMAOS: \"fix the defect class and mechanically inspect siblings (same
        # probe on every instance)\". A lista tem de existir e cada veredicto
        # tem de ser um dos declarados -- `unproven` e permitido e IMPRESSO.
        sib = bug.get('siblings')
        if not isinstance(sib, list) or not sib:
            fails.append('fixed sem `siblings`: corrigiu a instancia, nao a '
                         'classe (a nota exige a mesma sonda em cada instancia)')
        else:
            for i, s in enumerate(sib):
                if not s.get('instance') or not s.get('probe'):
                    fails.append('siblings[%d] sem instancia ou sem sonda' % i)
                v = s.get('verdict')
                if v not in SIBLING_VERDICTS:
                    fails.append('siblings[%d].verdict=%r nao esta em %r'
                                 % (i, v, list(SIBLING_VERDICTS)))
                elif not s.get('why'):
                    fails.append('siblings[%d] (%s) sem `why`' % (i, v))

    if reached('verified'):
        v = bug.get('verified') or {}
        if not (v.get('date') and v.get('instrument') and v.get('by')):
            fails.append('verified sem data/instrumento/quem')
        elif v.get('by') == author:
            fails.append('verified por quem corrigiu (%r): uma lane nao se '
                         'auto-verifica' % (v.get('by'),))

    if reached('recurrence-watch'):
        w = bug.get('recurrence_watch') or {}
        if not (w.get('instrument') and w.get('window')):
            fails.append('recurrence-watch sem instrumento ou sem janela')

    notes = []
    if state == 'fixed':
        notes.append('FIXED, NOT VERIFIED -- ninguem independente o verificou')
    elif state == 'reported':
        notes.append('REPORTED -- nao reproduzido, nao e defeito provado')
    # Um irmao `unproven` e um ACHADO ABERTO, nao um detalhe: e a instancia da
    # mesma classe que foi olhada e NAO ficou provada. Imprime-se para nao
    # poder ser lido como fecho.
    for s in (bug.get('siblings') or []):
        if isinstance(s, dict) and s.get('verdict') == 'unproven':
            notes.append('IRMAO NAO PROVADO: %s -- %s'
                         % (s.get('instance', '?'), s.get('why', '?')))
    return fails, state, notes


def run(ledger):
    states = ledger.get('states') or STATES
    if states != STATES:
        return ['a lista de estados declarada foi alterada: %r' % (states,)], []
    author = ledger.get('author') or ''
    battery_text = _read(BATTERY)
    out = []
    for bug in ledger.get('bugs') or []:
        fails, state, notes = check_bug(bug, states, author, battery_text)
        out.append((bug.get('id'), bug.get('title') or '', state, fails, notes))
    return out, []


def verdict(rows, ledger):
    ok = True
    for bug_id, title, state, fails, notes in rows:
        mark = 'GREEN' if not fails else 'RED  '
        print('%s %-16s state=%-16s %s' % (mark, bug_id, state, title[:60]))
        for note in notes:
            print('       %s' % note)
        for f in fails:
            print('       FAIL: %s' % f)
            ok = False
    states = [r[2] for r in rows]
    print('bugs: %d | estados: %s' % (len(rows),
                                      ', '.join('%s=%d' % (s, states.count(s))
                                                for s in STATES if s in states)))
    # METRICAS que a nota do manager pede, computadas do ledger e nao escritas a
    # mao: tempo-ate-reproducao, e a fraccao de correccoes cujo detector tem um
    # braco negativo NA BATERIA (\"the share of fixes with a regression check
    # proven red before repair\").
    bugs = ledger.get('bugs') or []
    tt = []
    for b in bugs:
        rep = b.get('reported') or {}
        rr = b.get('reproduced') or {}
        d = _days(rep.get('date'), rr.get('date'))
        if d is not None:
            tt.append(d)
    if tt:
        print('metrica: tempo-ate-reproducao (dias) = %s | media %.1f'
              % (tt, sum(tt) / float(len(tt))))
    fixed = [b for b in bugs if b.get('state') in
             ('fixed', 'verified', 'recurrence-watch')]
    proven = [b for b in fixed
              if battery_has_step(_read(BATTERY),
                                  ((b.get('regression') or {}).get('neg_arm')))]
    if fixed:
        print('metrica: correccoes com braco negativo NA BATERIA = %d/%d'
              % (len(proven), len(fixed)))
    unproven = [(b.get('id'), s.get('instance'))
                for b in bugs for s in (b.get('siblings') or [])
                if isinstance(s, dict) and s.get('verdict') == 'unproven']
    print('metrica: irmaos NAO PROVADOS = %d%s'
          % (len(unproven),
             ''.join('\n         %s: %s' % u for u in unproven)))
    print('populacao: %s' % (ledger.get('population', '?')))
    print('janela: %s' % (ledger.get('window', '?')))
    return ok


def neg_arm(ledger):
    base = json.loads(json.dumps(ledger))
    mutants = []

    def jump_verified(led):
        b = led['bugs'][0]
        b['state'] = 'verified'
        b['verified'] = None
        return led
    mutants.append(('M1 salta para verified sem ninguem verificar', jump_verified))

    def gate_not_in_battery(led):
        led['bugs'][0]['regression']['gate'] = 'input-path-typo'
        return led
    mutants.append(('M2 o regression.gate nao e um passo da bateria',
                    gate_not_in_battery))

    def fixed_without_reproduced(led):
        b = led['bugs'][0]
        b.pop('reproduced', None)
        return led
    mutants.append(('M3 chega a fixed sem reproducao', fixed_without_reproduced))

    def missing_capsule(led):
        led['bugs'][0]['capsule'] = '_main/incidents/nao-existe.md'
        return led
    mutants.append(('M4 a capsula de incidente nao existe', missing_capsule))

    def self_verified(led):
        b = led['bugs'][0]
        b['state'] = 'verified'
        b['verified'] = {'date': '2026-10-23', 'instrument': 'eu',
                         'by': led['author']}
        return led
    mutants.append(('M5 o autor verifica o proprio trabalho', self_verified))

    def no_falsifier(led):
        led['bugs'][0].pop('falsifier', None)
        return led
    mutants.append(('M6 hipotese sem falsificador', no_falsifier))

    def bad_sibling(led):
        led['bugs'][0]['siblings'].append(
            {'instance': 'qualquer', 'probe': 'olhei', 'verdict': 'acho-que-nao',
             'why': 'sem sonda'})
        return led
    mutants.append(('M7 irmao com veredicto inventado', bad_sibling))

    def unknown_no_next(led):
        led['bugs'][0]['state'] = 'unknown'
        return led
    mutants.append(('M8 unknown sem proximo passo', unknown_no_next))

    def no_artifact_sha(led):
        led['bugs'][0]['reproduced'].pop('artifact_sha', None)
        return led
    mutants.append(('M9 reproducao sem identidade do artefacto', no_artifact_sha))

    caught = 0
    for name, make in mutants:
        try:
            rows, _ = run(make(json.loads(json.dumps(base))))
            ok = verdict(rows, make(json.loads(json.dumps(base))))
        except Exception as exc:  # noqa: BLE001
            ok = False
            print('       (o mutante rebentou: %r)' % (exc,))
        if not ok:
            print('NEG-ARM %-52s RED as expected' % name)
            caught += 1
        else:
            print('NEG-ARM %-52s ** INERT **' % name)
    print('NEG-ARM %d of %d mutant(s) caught' % (caught, len(mutants)))
    if caught == len(mutants):
        print('NEG-ARM PASS')
        return 1
    print('VERDICT: FAIL -- %d mutante(s) do ledger passaram'
          % (len(mutants) - caught))
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true',
                    help='muta o LEDGER: os cinco tem de ficar VERMELHOS')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    ledger = load()
    if args.neg_arm:
        return neg_arm(ledger)
    rows, _ = run(ledger)
    ok = verdict(rows, ledger)
    print('BUG-LEDGER VERDICT %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
