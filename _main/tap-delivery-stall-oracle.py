#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: a tap de 2026-11-17 que entregou 630,3 s sem um bloco com o worker a transcrever silencio -- trabalho de CAPACIDADE/observabilidade sobre um defeito medido, sem id no `_main/bug-ledger.json`
"""tap-delivery-stall-oracle - uma tap que PARA de entregar tem de ser VISTA.

O DEFEITO JULGADO (medido 2026-11-16, chamada real: 5 h 22 de parede, 3 h 45 de
audio; `_main/webview-run.log` e `_main/audio-ring-coverage.py --day 2026-11-16`):

  * `EXTERNAL_CAPTIONS_ENGINE_PARKED source=external:youtube:track` as 16:55:44,
    `..._RESUMED` so' as 18:07:16 (1 h 11 m parqueado) e outra vez 18:07:44 ->
    19:08:39. O parque e' legitimo; o resume TAMBEM chegou;
  * nesse tempo o worker abriu 19 endpoints (um a cada ~7,7 min), `tap-engine-
    park-rescan` 12 vezes, e passou 630,3 s num `AG251F1WG2 (NVIDIA High
    Definition Audio)` com `blocks=0` -- o HDMI sem altifalantes;
  * `173532.24k.opus` declara 2 525 s de parede e guarda 200 s de som;
  * zero linhas com duracao: os `err()` do worker nao chegam ao log (a shell so'
    encaminha `ENGINE_VISIBLE_TAGS`) e o status `device-rotated (idle-rearm)` era
    deduplicado por texto.

A CAUSA, no fonte: com `parked` verdade, `window_ended` devolvia `now + grown`
sem NUNCA ler o medidor vivo -- e no tecto de 12 janelas so' re-varria a escada,
que escolhe por ORDEM e nao por quem esta' a renderizar. A tap settle so' tinha
`pump_exited` + `idle_s` como perguntas. "Sem blocos" nao era desambiguado.

AS ARMS (cada uma pode dizer NAO):

  A1  o censo: `{}` nao e' "sem sinal" (`unknown`), quieto e' `quiet`, som
      noutro endpoint e' `elsewhere`, som no NOSSO e' `here`.
  A2  a politica no INSTANTE medido: pump vivo, 630,3 s sem blocos, VoiceMeeter
      a 0,052 -> `signal-elsewhere` (muda de sitio JÁ'). Sem leitura, a MESMA
      chamada devolve `idle-rearm` -- a palavra que custou o buraco.
  A3a ANTES (forma que embarcou): a repeticao do laco com `parked` verdade e sem
      `stalled_s` leva ~630 s a rotacionar (o numero medido).
  A3b DEPOIS: com `stalled_s` e som a sair noutro endpoint, roda em <= 96 s.
  A3c DEPOIS, desktop CALADO: continua a esperar (nenhum churn inventado).
  A4  uma linha por episodio, com duracao, endpoint e pid.
  A5  o laco passa `stalled_s=`, a tap settle passa o censo, `on_block` carimba a
      ultima entrega, e o status existe nos DOIS caminhos.
  A6  `--neg-arm`: muta o PROPRIO texto e exige 3/3 vermelhas.

Usage:
  python _main/tap-delivery-stall-oracle.py
  python _main/tap-delivery-stall-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
DELIVERY = os.path.join(ROOT, 'worker', 'tap_delivery.py')
FUNCS = ('_flat_evidence_s', 'silent_desktop_hold', 'window_ended', 'tap_stall_reason')

#: O INSTANTE MEDIDO: 630,3 s sem um bloco no HDMI, com audio a sair no
#: VoiceMeeter (`NO_AUDIO_CLEARED ... peak=0.05202 from=VoiceMeeter Input`).
HOLE_S = 630.3
OWN = '{ag251f1}'      # o endpoint onde a tap estava
ELSEWHERE = '{voicemeeter}'


def read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def fn_source(text, name):
    """O `def` de topo com este nome, do texto que EMBARCA (nunca uma copia)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node)
    return None


def consts_of(text):
    ns = {}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ns
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            try:
                ns[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return ns


def namespace(wsrc, dsrc):
    """O worker e o modulo do censo, executados do FONTE. (ns, missing)."""
    ns = consts_of(wsrc)
    dns = {}
    exec(compile(dsrc, '<tap_delivery>', 'exec'), dns)
    ns.update({'os': os, 'time': time, 'LIVE': {},
               'tap_census_verdict': dns['tap_census_verdict'],
               'delivery_stall_line': dns['delivery_stall_line']})
    #: O medidor: o resultado que este oraculo DECIDE, nao o que esta' a tocar
    #: nesta maquina agora (`wasapi_loopback.live_render_peaks` custa 0,76 s e
    #: tornaria a arm dependente do dono estar a ouvir musica).
    exec(compile('def _live_render_peaks():\n    return dict(LIVE)\n', '<meter>', 'exec'), ns)
    for name in FUNCS:
        seg = fn_source(wsrc, name)
        if seg is None:
            return ns, name
        exec(compile(seg, '<worker:%s>' % name, 'exec'), ns)
    return ns, None


def park_loop(ns, stalled_from_blocks, quiet=False):
    """O laco REAL de `window_ended`, com o motor parqueado. Devolve (wall_s, n, emits).

    `stalled_from_blocks` = passa `stalled_s` (o laco de hoje) ou nao (a forma que
    embarcou). O relogio e' SIMULADO: a janela diz quanto tempo passou e o carimbo
    da ultima entrega acompanha -- nenhuma espera real.
    """
    ns['LIVE'] = {ELSEWHERE: 0.0 if quiet else 0.052} if not quiet else {ELSEWHERE: 0.0}
    dev = {'name': 'AG251F1WG2 (NVIDIA High Definition Audio)', 'endpoint_id': OWN}
    counters = {}
    emitted = []
    emit = lambda **kw: emitted.append(kw)               # noqa: E731
    last_block = 0.0
    now = 0.0
    for _ in range(400):
        kwargs = {'stalled_s': now - last_block} if stalled_from_blocks else {}
        extended = ns['window_ended'](
            now, dev, {'value': 0.0}, 0.002, 6.0, counters, emit,
            engine_parked=lambda: 'external:youtube:track', **kwargs)
        if extended is None:
            return now, emitted
        now = extended
    return now, emitted


def judge(wsrc, dsrc):
    """Todas as arms, sobre um par (worker, tap_delivery) de TEXTO. [(name, ok, det)]."""
    out = []

    def check(name, got, want):
        out.append((name, got == want, 'got=%r want=%r' % (got, want)))

    ns, missing = namespace(wsrc, dsrc)
    if missing is not None:
        return [('A0 instrument: %s ausente do fonte' % missing, False, 'ausente')]
    census = ns['tap_census_verdict']
    policy = ns['tap_stall_reason']
    line = ns['delivery_stall_line']

    # -- A1 o censo ---------------------------------------------------------
    check('A1.1 sem leitura NAO e sem sinal', census({}, OWN), 'unknown')
    check('A1.2 maquina calada', census({OWN: 0.0, ELSEWHERE: 0.0}, OWN), 'quiet')
    check('A1.3 som noutro endpoint', census({OWN: 0.0, ELSEWHERE: 0.052}, OWN), 'elsewhere')
    check('A1.4 som no NOSSO endpoint', census({OWN: 0.4, ELSEWHERE: 0.0}, OWN), 'here')
    check('A1.5 sem endpoint proprio nao localiza', census({ELSEWHERE: 0.4}, None), 'unknown')

    # -- A2 a politica no instante medido ----------------------------------
    check('A2.1 o audio mudou de sitio -> signal-elsewhere',
          policy(False, HOLE_S, 3, live={OWN: 0.0, ELSEWHERE: 0.052}, own=OWN),
          'signal-elsewhere')
    check('A2.2 o NOSSO endpoint renderiza -> client-starved',
          policy(False, HOLE_S, 3, live={OWN: 0.4}, own=OWN), 'client-starved')
    check('A2.3 desktop calado continua endpoint-idle (sem churn)',
          policy(False, 20.0, 3, live={OWN: 0.0, ELSEWHERE: 0.0}, own=OWN), 'endpoint-idle')
    check('A2.4 SEM leitura a resposta e a antiga (a palavra que custou o buraco)',
          policy(False, HOLE_S, 3), 'idle-rearm')

    # -- A3a a forma que embarcou: 12 janelas + rescan ----------------------
    wall, emitted = park_loop(ns, False)
    out.append(('A3a ANTES: parqueado e mudo leva ~630 s a rodar',
                HOLE_S - 60.0 <= wall <= HOLE_S + 60.0,
                'wall_s=%.1f (medido 630.3) emit=%s' % (wall, [e.get('state') for e in emitted])))

    # -- A3b a cura ---------------------------------------------------------
    wall2, emitted2 = park_loop(ns, True)
    out.append(('A3b DEPOIS: roda em <= 96 s',
                wall2 <= 96.0,
                'wall_s=%.1f emit=%s' % (wall2, [e.get('state') for e in emitted2])))
    out.append(('A3b.2 a linha nomeia o episodio',
                any(e.get('state') == 'tap-delivery-stalled' and 'stalled_s=' in str(e.get('reason'))
                    for e in emitted2),
                str([e.get('reason') for e in emitted2 if e.get('state') == 'tap-delivery-stalled'])))

    # -- A3c calado nao inventa churn --------------------------------------
    wall3, emitted3 = park_loop(ns, True, quiet=True)
    out.append(('A3c DEPOIS, desktop calado: guarda a espera e nao inventa churn',
                wall3 >= 600.0 and not any(e.get('state') == 'tap-delivery-stalled'
                                          for e in emitted3),
                'wall_s=%.1f emit=%s' % (wall3, [e.get('state') for e in emitted3])))

    # -- A4 uma linha por episodio -----------------------------------------
    counters = {'blocks': 0}
    first = line(counters, 'AG251F1WG2', HOLE_S, 'signal-elsewhere', 'VoiceMeeter')
    again = line(counters, 'AG251F1WG2', HOLE_S + 5, 'signal-elsewhere', 'VoiceMeeter')
    counters['blocks'] = 1
    third = line(counters, 'AG251F1WG2', HOLE_S, 'signal-elsewhere', 'VoiceMeeter')
    out.append(('A4.1 uma linha por episodio',
                bool(first) and again is None and bool(third), 'again=%r' % (again,)))
    out.append(('A4.2 a linha leva duracao, endpoint e pid',
                all(k in (first or '') for k in ('stalled_s=630.3', 'AG251F1WG2', 'pid=')),
                str(first)))

    # -- A5 a ligacao no fonte que embarca ---------------------------------
    for name, needle, want in (
            ('A5.1 o laco passa stalled_s a window_ended',
             'stalled_s=now - max(', 1),
            ('A5.2 on_block carimba a ultima entrega',
             'counters["last_block_at"] = time.time()', 1),
            ('A5.3 a tap settle le o censo',
             'live=_live_render_peaks(),', 1),
            ('A5.4 o parque le o censo', 'tap_census_verdict(_live_render_peaks(),', 1),
            ('A5.5 o status existe nos dois caminhos', 'state="tap-delivery-stalled"', 2),
            ('A5.6 o modulo do censo e importado', 'from tap_delivery import', 1)):
        check(name, wsrc.count(needle), want)
    return out


def report(arms, label):
    bad = [a for a in arms if not a[1]]
    for name, ok, detail in arms:
        print('%s %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    print('%s VERDICT: %s -- %d/%d' % (label, 'PASS' if not bad else 'FAIL',
                                       len(arms) - len(bad), len(arms)))
    return bad


MUTATIONS = (
    ('M1 o parque volta a nao perguntar nada (o defeito)',
     lambda w, d: (w.replace('            _stall = float(stalled_s or 0.0)\n'
                             '            if _stall >= TAP_STALL_MAX_S:\n'
                             '                _census = tap_census_verdict(_live_render_peaks(),\n'
                             "                                             dev.get('endpoint_id'), tap_floor)\n"
                             "                if _census in ('here', 'elsewhere'):\n"
                             "                    _line = delivery_stall_line(counters, dev.get('name'), _stall,\n"
                             '                                                _census, None)\n'
                             '                    if emit is not None and _line:\n'
                             '                        emit(type="status", state="tap-delivery-stalled",\n'
                             "                             device=dev.get('name'), reason=_line, parked=parked)\n"
                             "                    state['windows'] = 0\n"
                             '                    return None\n', ''), d),
     ('A3b',)),
    ('M2 a politica volta a nao desambiguar "sem blocos"',
     lambda w, d: (w.replace('    if live:\n'
                             '        _census = tap_census_verdict(live, own, floor)\n'
                             '        if _census == "elsewhere":\n'
                             '            return "signal-elsewhere"\n'
                             '        if _census == "here":\n'
                             '            return "client-starved"\n', ''), d),
     ('A2.1', 'A2.2')),
    ('M3 a linha fala sempre (deixa de ser um episodio)',
     lambda w, d: (w, d.replace("    if counters.get('delivery_said') == key:\n        return None\n", '')),
     ('A4.1',)),
)


def neg_arm(wsrc, dsrc):
    caught = 0
    for name, mutate, must_fail in MUTATIONS:
        mw, md = mutate(wsrc, dsrc)
        if (mw, md) == (wsrc, dsrc):
            print('%s NOT-APPLIED (a emenda nao existe no fonte)' % name)
            continue
        arms = judge(mw, md)
        broke = [a[0] for a in arms if not a[1] and any(a[0].startswith(p) for p in must_fail)]
        if broke:
            caught += 1
            print('%s CAUGHT by %s' % (name, ','.join(b.split(' ')[0] for b in broke)))
        else:
            print('%s NOT-CAUGHT' % name)
    print('NEG-ARM: %s -- %d/%d' % ('PASS' if caught == len(MUTATIONS) else 'FAIL',
                                    caught, len(MUTATIONS)))
    # HOUSE CONVENTION (measured across this tree): the negative arm returns 1
    # WHEN IT CATCHES, so a `call :expectred` step can only pass on a real catch.
    # MEASURED DEFECT: returning 0 here made `red-as-expected-tap-delivery-stall`
    # (declared rc=1) fail on a run that caught 3/3 -- a control that cannot pass.
    return 1 if caught == len(MUTATIONS) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--worker', default=WORKER)
    ap.add_argument('--delivery', default=DELIVERY)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    for path in (args.worker, args.delivery):
        if not os.path.exists(path):
            print('TAP-DELIVERY VERDICT: FAIL -- %s ausente' % path)
            return 1
    wsrc, dsrc = read(args.worker), read(args.delivery)
    arms = judge(wsrc, dsrc)
    bad = report(arms, 'TAP-DELIVERY')
    if args.neg_arm:
        return neg_arm(wsrc, dsrc)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
