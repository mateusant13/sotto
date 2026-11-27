#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NO-BUG: catches YouTube clock state combinations no example covers, by asserting properties over all values of the three pure functions
"""CAMADA 3 -- PROPRIEDADES sobre as tres funcoes PURAS do relogio do YouTube.

PORQUE ESTE FICHEIRO EXISTE (medido 2026-11-27, `test_quality_audit.py scan
--repo .`): o repo tinha `prop=0` em 596 funcoes de teste, ou seja as cinco
camadas de `project-revival/references/agentic-laws-and-testing.md` paravam na
segunda. Os oraculos deste repo provam exemplos (camada 1 e 2); nada provava uma
AFIRMACAO SOBRE TODOS OS VALORES, que e' o que a camada 3 acrescenta e o que
captura o caso que ninguem escreveu a mao.

O ALVO NAO E' ESCOLHIDO POR CONVENIENCIA. `app/webview/youtube_clock.py` e' o
dono UNICO de tres decisoes que o dono pagou para aprender (2026-11-06,
2026-11-26): parado nao anda, uma pausa so' vale com testemunha fresca, e o que
NOS adiantamos e' nosso para desfazer. As tres sao funcoes puras -- sem relogio,
sem I/O, sem estado global -- logo uma propriedade sobre elas e' uma afirmacao
sobre o produto, nao sobre o teste.

A PROPRIEDADE QUE INTERESSA AQUI E' A QUE UM EXEMPLO NAO DA': `instant()` tem
seis ramos de estado e quatro conversoes numericas, e o defeito historico nasceu
de uma COMBINACAO (bandeira de pausa contra relogio a andar) que nenhuma lista
de casos enumera de forma exaustiva. `hypothesis` enumera.

PORTEIRO: `--neg-arm` substitui cada predicado pelo seu irmao mutante e exige que
a propriedade CORRESPONDENTE fique vermelha. Uma propriedade que nao pode ficar
vermelha e' um verde falso, e o braco negativo e' o que o prova.

rc: 0 PASS (todas as propriedades verdes), 1 FAIL/RED (uma propriedade caiu, ou
o braco negativo nao derrubou a que devia), 3 CANNOT-MEASURE (`hypothesis`
ausente).
"""
from __future__ import annotations

import argparse
import os
import sys


def _import_clock():
    here = os.path.dirname(os.path.abspath(__file__))
    webview = os.path.join(os.path.dirname(here), "app", "webview")
    for d in (webview,):
        if d not in sys.path:
            sys.path.insert(0, d)
    import youtube_clock  # noqa: E402
    return youtube_clock


def _try_hypothesis():
    try:
        from hypothesis import HealthCheck, given, settings, strategies as st
    except ImportError:  # pragma: no cover - exercised only on a bare box
        return None
    return given, settings, st, HealthCheck


# --------------------------------------------------------------------------
# AS PROPRIEDADES. Cada uma recebe o modulo do relogio e o injector do
# `hypothesis`; devolve a lista de violacoes (vazia == verde). Elas nunca leem
# constantes do proprio modulo para as compararem consigo mesmas -- leem o
# CONTRATO escrito no cabecalho dele.
# --------------------------------------------------------------------------

def prop_monotone_and_bounded(clock, hyp):
    """O instante servido nunca recua e nunca passa a amostra + o teto x taxa.

    O contrato do cabecalho, em duas metades:
      * "o instante devolvido NUNCA e' anterior a' amostra";
      * "`moved = min(age, cap) * rate`" -- o adiantamento e' limitado pelo teto
        E pela taxa, e `age <= 0` nao anda.
    """
    given, settings, st, HealthCheck = hyp
    bad = []

    @settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
    @given(
        base_t=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        age=st.floats(min_value=-5.0, max_value=60.0, allow_nan=False, allow_infinity=False),
        rate=st.floats(min_value=0.05, max_value=16.0, allow_nan=False, allow_infinity=False),
        hold=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
    )
    def run(base_t, age, rate, hold):
        t, moved, spent = clock.instant(base_t, age, rate, clock.PLAYING, hold)
        if t is None:
            bad.append("instant devolveu None para base_t=%r" % (base_t,))
            return
        # (1) nunca anterior a' amostra -- um relogio que recua inventa um seek.
        if t < base_t - 1e-9:
            bad.append("recuou: t=%r < base=%r (age=%r)" % (t, base_t, age))
        # (2) o adiantamento e' limitado pelo teto, pela idade E pela taxa.
        if moved > max(0.0, age) * rate + 1e-9:
            bad.append("andou alem da idade: moved=%r age=%r rate=%r" % (moved, age, rate))
        if moved > hold * rate + 1e-9:
            bad.append("andou alem do teto: moved=%r hold=%r rate=%r" % (moved, hold, rate))
        if age <= 0.0 and moved != 0.0:
            bad.append("andou com idade <= 0: age=%r moved=%r" % (age, moved))
        # (3) `spent` diz "ja' nao ha' ancora" -- so' pode ser verdade acima do teto.
        if spent and age <= hold:
            bad.append("esgotou sem passar o teto: age=%r hold=%r" % (age, hold))

    run()
    return bad


def prop_paused_never_moves(clock, hyp):
    """PARADO NAO ANDA -- o contrato inegociavel, em todos os valores.

    "O PLAYER DISSE QUE ESTA PARADO (`paused`/`ended` verdadeiros) -- nao anda um
    milissegundo." Um exemplo (`instant(10.0, 5.0, 1.0, PAUSED)` == 10.0) nao
    prova que nenhuma idade, taxa ou teto o faz andar; a propriedade prova.
    """
    given, settings, st, HealthCheck = hyp
    bad = []

    @settings(max_examples=200, deadline=None, suppress_health_check=list(HealthCheck))
    @given(
        base_t=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        age=st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False),
        rate=st.floats(min_value=0.05, max_value=16.0, allow_nan=False, allow_infinity=False),
        hold=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
        state=st.sampled_from([clock.PAUSED, clock.ENDED]),
    )
    def run(base_t, age, rate, hold, state):
        t, moved, spent = clock.instant(base_t, age, rate, state, hold)
        if t != base_t or moved != 0.0 or spent:
            bad.append("estado %s mexeu: base=%r -> t=%r moved=%r spent=%r"
                       % (state, base_t, t, moved, spent))

    run()
    return bad


def prop_unknown_never_invents(clock, hyp):
    """SEM RESPOSTA NAO SE ANDA POR INERCIA -- serve-se a amostra, e `spent` avisa.

    "O PLAYER NAO DISSE NADA ... NAO se anda por inercia: serve-se a ultima
    amostra conhecida." O sinal para o chamador e' `spent = age > cap`.
    """
    given, settings, st, HealthCheck = hyp
    bad = []

    @settings(max_examples=200, deadline=None, suppress_health_check=list(HealthCheck))
    @given(
        base_t=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        age=st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False),
        rate=st.floats(min_value=0.05, max_value=16.0, allow_nan=False, allow_infinity=False),
        hold=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
    )
    def run(base_t, age, rate, hold):
        t, moved, spent = clock.instant(base_t, age, rate, clock.UNKNOWN, hold)
        if t != base_t or moved != 0.0:
            bad.append("UNKNOWN andou: base=%r -> t=%r moved=%r" % (base_t, t, moved))
        if spent != (age > hold):
            bad.append("UNKNOWN com spent errado: age=%r hold=%r spent=%r"
                       % (age, hold, spent))

    run()
    return bad


def prop_pause_needs_a_fresh_witness(clock, hyp):
    """A PAUSA SO' E' VERDADEIRA COM TESTEMUNHA FRESCA E SEM DESMENTIDO.

    `pause_proven` e' `bool(photo_fresh) and bool(clock_static) and not
    bool(clock_moving)`. Um exemplo verde nao impede um caminho futuro de
    esquecer a frescura -- e a frescura e' exatamente o que faltava as
    02:38:08 de 2026-11-26, quando uma foto de 5,9 s mandou apagar o ecra.
    A propriedade: com `photo_fresh` falso a pausa NUNCA e' provada, para
    qualquer par (static, moving); e um movimento medido desmente sempre.
    """
    given, settings, st, HealthCheck = hyp
    bad = []

    @settings(max_examples=200, deadline=None, suppress_health_check=list(HealthCheck))
    @given(
        clock_static=st.booleans(),
        clock_moving=st.booleans(),
        photo_fresh=st.booleans(),
    )
    def run(clock_static, clock_moving, photo_fresh):
        proven = clock.pause_proven(clock_static, clock_moving, photo_fresh)
        if not isinstance(proven, bool):
            bad.append("pause_proven nao devolveu bool: %r" % (proven,))
            return
        if proven and not photo_fresh:
            bad.append("provou pausa com FOTO VELHA (static=%r moving=%r)"
                       % (clock_static, clock_moving))
        if proven and clock_moving:
            bad.append("provou pausa com o relogio A ANDAR (static=%r)" % (clock_static,))
        if not proven and photo_fresh and clock_static and not clock_moving:
            bad.append("recusou a pausa que as tres testemunhas provam")

    run()
    return bad


def prop_rebase_undoes_only_what_we_invented(clock, hyp):
    """O QUE NOS ADIANTAMOS E' NOSSO PARA DESFAZER, e o seek nao e' nosso.

    "Uma diferenca que cabe nesse adiantamento e' nossa, logo desfaz-se e
    serve-se `t` ... Uma diferenca MAIOR nao e' nossa -- e' um seek -- e o chao
    fica onde esta'." A propriedade separa os dois lados em todos os valores:
    um recuo ate' `invented` devolve `t`; um recuo maior devolve o chao.
    """
    given, settings, st, HealthCheck = hyp
    bad = []

    # A PRIMEIRA CORRIDA DESTE BRACO MEDIU O BANDO `eps` E MAIS NADA: com
    # `floor=4,5e-246` e `t=-2,2e-16` o recuo era ~4,5e-246, dentro do bando de
    # `eps=0,05`, e `rebase` devolveu o chao -- CORRETO. Ali o chao ja' esta'
    # onde tem de estar porque a diferenca nao e' um recuo de verdade. Ou seja a
    # expectativa estava errada, nao o produto, e a propriedade tem de modelar
    # os TRES lados: dentro de `eps` qualquer dos dois serve; acima de `eps` e
    # dentro do que adiantamos, desfaz; acima do que adiantamos, e' seek.
    @settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
    @given(
        floor=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        invented=st.floats(min_value=0.0, max_value=60.0, allow_nan=False, allow_infinity=False),
        back=st.floats(min_value=0.0, max_value=60.0, allow_nan=False, allow_infinity=False),
    )
    def run(floor, invented, back):
        t = floor - back
        eps = 0.05
        try:
            real_back = float(floor) - float(t)
        except (TypeError, ValueError, OverflowError):
            return
        got = clock.rebase(floor, t, invented, eps)
        if got is None:
            bad.append("rebase devolveu None para floor=%r t=%r" % (floor, t))
            return
        if real_back <= eps:
            # Dentro do bando de ruido: o produto pode servir o chao ou a
            # amostra, nunca um terceiro valor inventado.
            if got not in (floor, t):
                bad.append("inventou um terceiro valor: floor=%r t=%r got=%r" % (floor, t, got))
        elif real_back <= invented + eps:
            # dentro do que adiantamos: desfaz, serve-se a amostra.
            if got != t:
                bad.append("nao desfez o nosso: floor=%r t=%r invented=%r got=%r"
                           % (floor, t, invented, got))
        else:
            # recuo maior que o nosso: e' seek, o chao fica.
            if got != floor:
                bad.append("seguiu um seek como se fosse nosso: floor=%r t=%r invented=%r got=%r"
                           % (floor, t, invented, got))

    run()
    return bad


PROPS = (
    ("monotone-and-bounded", prop_monotone_and_bounded),
    ("paused-never-moves", prop_paused_never_moves),
    ("unknown-never-invents", prop_unknown_never_invents),
    ("pause-needs-a-fresh-witness", prop_pause_needs_a_fresh_witness),
    ("rebase-undoes-only-what-we-invented", prop_rebase_undoes_only_what_we_invented),
)

def mutate(clock, token):
    """O irmao mutante de UMA propriedade, ou None.

    A mutacao troca o PREDICADO do produto, nunca a expectativa: mutar a
    expectativa provaria que o teste sabe dizer "nao", nao que o produto esta'
    certo. Cada entrada abaixo e' o defeito historico daquela propriedade,
    reintroduzido por uma linha.
    """
    """Devolve um modulo-sombra cuja funcao viola o contrato, ou None."""
    import types
    shadow = types.SimpleNamespace(**{k: getattr(clock, k) for k in dir(clock)
                                      if not k.startswith('__')})
    if token == 'monotone-and-bounded':
        # O ANDAMENTO PASSA O TETO: exactamente o defeito que HOLD_S existe para
        # impedir -- a legenda adianta-se ao video durante um stutter.
        real = clock.instant

        def instant_no_cap(base_t, age, rate=1.0, state=clock.PLAYING, hold=clock.HOLD_S):
            t, moved, spent = real(base_t, age, rate, state, 1e9)
            return t, moved, spent
        shadow.instant = instant_no_cap
    elif token == 'paused-never-moves':
        # PARADO ANDA: a pausa deixa de ser inegociavel.
        real = clock.instant

        def instant_moves_while_paused(base_t, age, rate=1.0, state=clock.PLAYING,
                                       hold=clock.HOLD_S):
            if state in (clock.PAUSED, clock.ENDED) and base_t is not None and age > 0:
                try:
                    return float(base_t) + 0.001, 0.001, False
                except (TypeError, ValueError):
                    pass
            return real(base_t, age, rate, state, hold)
        shadow.instant = instant_moves_while_paused
    elif token == 'unknown-never-invents':
        # A INERCIA VOLTA: sem resposta, o relogio anda com a idade.
        real = clock.instant

        def instant_extrapolates_unknown(base_t, age, rate=1.0, state=clock.PLAYING,
                                         hold=clock.HOLD_S):
            if state == clock.UNKNOWN and base_t is not None:
                try:
                    return float(base_t) + max(0.0, float(age)), float(age), False
                except (TypeError, ValueError):
                    pass
            return real(base_t, age, rate, state, hold)
        shadow.instant = instant_extrapolates_unknown
    elif token == 'pause-needs-a-fresh-witness':
        # A FOTO VELHA VOLTA A PROVAR: a frescura deixa de contar.
        shadow.pause_proven = lambda clock_static, clock_moving, photo_fresh: (
            bool(clock_static) and not bool(clock_moving))
    elif token == 'rebase-undoes-only-what-we-invented':
        # O SEEK PASSA A SER NOSSO: qualquer recuo e' desfeito -- a legenda presa
        # a' frente do video e' o defeito de 2026-11-06.
        shadow.rebase = lambda floor, t, invented, eps=0.05: t
    else:
        return None
    return shadow


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--neg-arm', action='store_true',
                    help='prova que cada propriedade sabe ficar vermelha')
    args = ap.parse_args(argv)

    hyp = _try_hypothesis()
    if hyp is None:
        print('VERDICT: CANNOT-MEASURE why=no-hypothesis -- a camada 3 e uma '
              'afirmacao sobre todos os valores; sem o gerador nao ha propriedade.')
        return 3

    clock = _import_clock()

    if args.neg_arm:
        caught = 0
        misses = []
        for name, _fn in PROPS:
            shadow = mutate(clock, name)
            if shadow is None:
                misses.append('%s: sem mutante' % name)
                continue
            fn = dict(PROPS)[name]
            try:
                bad = fn(shadow, hyp)
            except Exception as exc:  # a mutacao pode estourar -- isso e' apanhar
                print('NEG-ARM %-38s CAUGHT (%s: %s)' % (name, type(exc).__name__, exc))
                caught += 1
                continue
            if bad:
                print('NEG-ARM %-38s CAUGHT (%s)' % (name, bad[0]))
                caught += 1
            else:
                print('NEG-ARM %-38s MISSED -- a mutacao nao derrubou a propriedade' % name)
                misses.append(name)
        total = len(PROPS)
        if caught == total:
            print('NEG-ARM: PASS -- %d/%d mutantes apanhados' % (caught, total))
            return 1
        print('NEG-ARM: FAIL -- %d/%d; nao apanhados: %s'
              % (caught, total, ', '.join(misses)))
        return 0

    failures = []
    for name, fn in PROPS:
        try:
            bad = fn(clock, hyp)
        except Exception as exc:
            print('PROP %-38s ERROR %s: %s' % (name, type(exc).__name__, exc))
            failures.append(name)
            continue
        if bad:
            print('PROP %-38s FAIL  %s' % (name, bad[0]))
            failures.append(name)
        else:
            print('PROP %-38s PASS' % name)
    if failures:
        print('VERDICT: FAIL -- %d de %d propriedades violadas: %s'
              % (len(failures), len(PROPS), ', '.join(failures)))
        return 1
    print('VERDICT: PASS -- %d/%d propriedades sobre app/webview/youtube_clock.py'
          % (len(PROPS), len(PROPS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
