#!/usr/bin/env python
"""O MODELO DAS LEIS, em Python -- para maquinas sem Bend 2.

Este ficheiro NAO e o portao. O portao e `bend PROOF.bend --verdict`, dentro do
distro WSL `ubuntu-bend`, e e o kernel (Lean 4.34 via BendTT) que prova as
leis. Este ficheiro e o MESMO MODELO escrito em Python, para um host sem o
toolchain -- e, principalmente, para um LEITOR poder ver o que as leis dizem
sem instalar nada.

O QUE ESTE FICHEIRO FAZ, e o que ele NAO FAZ:

  FAZ: calcula as funcoes do modelo (`Nat.revealed_flag`, `Toks.count_due`,
  `Nat.live_flag`, `Nat.window_rows` e as da ORDEM DO EPOCH: `same_epoch`,
  `paint_flag`, `on_new_source`, `on_blank`, `on_push`, `on_drain`, `run`) e
  CHECA as leis sobre uma amostra EXPLICITA de entradas. E uma AMOSTRA, nao uma
  prova: o kernel prova para TODAS as entradas.

  NAO FAZ: nao substitui o portao. Um "verde" aqui diz "estas entradas
  concretas respeitam a lei" -- e nada mais. O `--selftest` deste ficheiro
  existe para ser ligado ao gate que o rodeia, e o gate e o `bend`.

A DIVISAO ENTRE MODELO E PROVA. `bend_core/LAWS.bend` tem as AFIRMACOES e o
modelo de que elas precisam; `bend_core/PROOF.bend` tem as PROVAS. Este
ficheiro e o modelo, em Python, e nada mais: nao tem afirmacoes, nao tem
provas, e nao substitui nenhuma das duas coisas.

O PORQUÊ DE EXISTIR. O guia (`docs/bend/BEND_LAW_GUIDE.md`) lista
`bend_core/model.py` como parte do paragrafo do toolchain: uma cópia do
modelo em Python para os hosts sem Bend. O owner precisa de conseguir ler o que
a lei afirma sem um toolchain detheorem prover -- e precisa de poder VERIFICAR
o numero que a lei restringe sem esperar pelo WSL.

O `--neg-arm` desta ferramenta tem de dar RED: e o que prova que o verificador
deteta um modelo quebrado. Um verificador que só diz "ok" nao é verificador.
"""
from __future__ import annotations

import argparse
import itertools
import sys


# ---------------------------------------------------------------------------
# O MODELO (a mesma forma de `bend_core/LAWS.bend`)
# ---------------------------------------------------------------------------


def of_bool(b):
    """`Nat.of_bool` -- o indicador, na forma `match`."""
    return 1 if b else 0


def revealed_flag(due):
    """`Nat.revealed_flag` -- o indicador, na forma `Bool.pick`."""
    return 1 if due else 0


def due(at_ms, t_ms):
    """`Tok.due` -- a palavra ja chegou?"""
    return at_ms <= t_ms


def count_due(toks, t_ms):
    """`Toks.count_due` -- quantas palavras ja chegaram."""
    return sum(revealed_flag(due(at, t_ms)) for at in toks)


def live_flag(started, ended):
    """`Nat.live_flag` -- a linha esta viva?"""
    return bool(started) and not bool(ended)


def window_rows(live_rows, capacity):
    """`Nat.window_rows` -- quantas linhas a janela mostra."""
    return min(capacity, live_rows)


# ---------------------------------------------------------------------------
# A ORDEM DO EPOCH DE FONTE (2026-10-30) -- `bend_core/LAWS.bend`, DECISAO 5.
#
# O estado e' um terno `(epoch, slot, shown)`: o epoch da fonte, o UNICO texto
# enfileirado (None, ou o carimbo do epoch com que foi enfileirado) e se ha
# pixeis no ecra. As transicoes sao os quatro sitios de
# `app/webview/sotto_webview.py`: `start_worker` (:9514),
# `_blank_caption_window` (:9719), `push_caption_to_window` (:9798) e `_drain`
# (:9812).
# ---------------------------------------------------------------------------

SLOT_IDLE = None

EVENTS = ("new_source", "blank", "push", "drain")


def slot_held(stamp):
    """`Slot.SlotHeld` -- um texto enfileirado, com o epoch do carimbo."""
    return ("held", int(stamp))


def is_idle(slot):
    """`Slot.is_idle`"""
    return slot is None


def cap(epoch, slot, shown):
    return (int(epoch), slot, bool(shown))


def cap_epoch(c):
    """`Cap.epoch`"""
    return c[0]


def cap_slot(c):
    """`Cap.slot`"""
    return c[1]


def cap_shown(c):
    """`Cap.shown`"""
    return c[2]


def same_epoch(a, b):
    """`Nat.same_epoch` -- a igualdade ESTRUTURAL do modelo."""
    return int(a) == int(b)


def paint_flag(stamp, cur):
    """`Nat.paint_flag` -- a decisao do `_drain`: 1 pinta, 0 larga."""
    return revealed_flag(same_epoch(stamp, cur))


def on_new_source(c):
    """`Cap.on_new_source` -- `start_worker`: epoch+1 e a fila limpa."""
    return cap(cap_epoch(c) + 1, SLOT_IDLE, cap_shown(c))


def on_blank(c):
    """`Cap.on_blank` -- `_blank_caption_window`: epoch+1, fila e pixeis limpos."""
    return cap(cap_epoch(c) + 1, SLOT_IDLE, False)


def on_push(c):
    """`Cap.on_push` -- `push_caption_to_window`: carimba o epoch CORRENTE."""
    return cap(cap_epoch(c), slot_held(cap_epoch(c)), cap_shown(c))


def slot_paints(slot, cur):
    """`Slot.paints` -- a guarda `epoch != cur`, do lado do slot."""
    if is_idle(slot):
        return False
    return same_epoch(slot[1], cur)


def on_drain(c):
    """`Cap.on_drain` -- `_drain`: o slot esvazia, os pixeis so mudam se pintar."""
    return cap(cap_epoch(c), SLOT_IDLE,
               cap_shown(c) or slot_paints(cap_slot(c), cap_epoch(c)))


def step(c, ev):
    """`Cap.step` -- despacha por NOME, para o `--neg-arm` poder trocar um."""
    if ev == "new_source":
        return on_new_source(c)
    if ev == "blank":
        return on_blank(c)
    if ev == "push":
        return on_push(c)
    if ev == "drain":
        return on_drain(c)
    raise AssertionError("unknown event %r" % (ev,))


def run(evs, c):
    """`Evs.run` -- uma sessao: os acontecimentos por ordem."""
    for ev in evs:
        c = step(c, ev)
    return c


# ---------------------------------------------------------------------------
# AS LEIS, como predicados sobre o modelo.
#
# Cada uma corresponde a uma `law` de `bend_core/LAWS.bend`. O `# REJECTS:` de
# cada lei esta la; aqui so a verificacao.
# ---------------------------------------------------------------------------


def law_revealed_flag_is_zero_or_one(due_value):
    """A lei e sobre o INDICADOR, que aqui e a funcao `revealed_flag`."""
    return revealed_flag(due_value) in (0, 1)


def law_of_bool_agrees_with_revealed_flag(due_value):
    return of_bool(due_value) == revealed_flag(due_value)


def law_count_due_counts_only_due_words(toks, t_ms):
    return count_due(toks, t_ms) <= len(toks)


def law_count_due_of_an_empty_line_is_zero(t_ms):
    return count_due((), t_ms) == 0


def law_count_due_of_one_word_is_its_flag(tok, t_ms):
    return count_due((tok,), t_ms) == revealed_flag(due(tok, t_ms))


def law_count_due_is_monotone_in_time(toks, t1_ms, t2_ms):
    if t1_ms > t2_ms:
        return True
    return count_due(toks, t1_ms) <= count_due(toks, t2_ms)


def law_live_flag_is_started_and_not_ended(started, ended):
    return live_flag(started, ended) == (bool(started) and not bool(ended))


def law_live_flag_is_false_before_the_line_starts(ended):
    return live_flag(False, ended) is False


def law_window_rows_is_the_minimum(live_rows, capacity):
    return window_rows(live_rows, capacity) == min(capacity, live_rows)


def law_window_rows_never_exceeds_the_capacity(live_rows, capacity):
    return window_rows(live_rows, capacity) <= capacity


def law_window_rows_never_exceeds_the_live_rows(live_rows, capacity):
    return window_rows(live_rows, capacity) <= live_rows


def law_epoch_monotonic(c, evs):
    """O epoch de fonte nunca decresce ao longo de uma sessao."""
    return cap_epoch(c) <= cap_epoch(run(evs, c))


def law_no_cross_source_paint(stamp, cur):
    """Pinta sse o carimbo e' o epoch corrente -- dos DOIS lados."""
    return paint_flag(stamp, cur) == of_bool(same_epoch(stamp, cur))


def law_display_clean_before_new_source(c):
    """O blank e' uma fonte nova, com a fila vazia e os pixeis limpos."""
    after = on_blank(c)
    return (not cap_shown(after)
            and is_idle(cap_slot(after))
            and same_epoch(cap_epoch(after), cap_epoch(c) + 1))


# ---------------------------------------------------------------------------
# DECISAO 6 -- QUEM PODE ESCREVER O HISTORICO (`app/panel/history-source.js`)
#
# As entradas sao as que `historyDecision(meta)` le: a rota declarada e o
# produtor declarado. `None` em `route` e' "sem rota"; `None` em `producer` e'
# "sem produtor declarado" (ausente, vazio, ou nao-string).
# ---------------------------------------------------------------------------

PRODUCERS = (None, "live", "redux", "other")
ROUTES = (None, "final", "provisional-draft", "weird")

#: Os motivos, exactamente os do ficheiro de producao.
REASON_PROVISIONAL = "provisional-draft"
REASON_UNKNOWN_ROUTE = "unknown-route"
REASON_NO_ROUTE_NO_PRODUCER = "no-route-no-producer"


def producer_is_canonical(producer):
    """`isCanonicalLine` -- o produtor e' o canonico (`'redux'`)."""
    return producer == "redux"


def hist_route_of(route, producer):
    """`historyDecision(meta).route` -- a rota que entra, ou None."""
    if route == "final":
        return "final"
    if route is not None:
        return None
    return "batch" if producer_is_canonical(producer) else None


def hist_accepted(route, producer):
    """A PORTA: aceita sse ha' uma rota."""
    return hist_route_of(route, producer) is not None


def hist_accepted_reference(route, producer):
    """A SEGUNDA FORMA da porta, escrita como a regra."""
    if route == "final":
        return True
    if route is not None:
        return False
    return producer == "redux"


def hist_reason_of(route, producer):
    """`historyDecision(meta).reason` -- o motivo, ou None."""
    if route == "final":
        return None
    if route is not None:
        return REASON_PROVISIONAL if route == "provisional-draft" else REASON_UNKNOWN_ROUTE
    if producer == "redux":
        return None
    return REASON_NO_ROUTE_NO_PRODUCER


def law_hist_final_route_is_accepted(producer):
    return hist_accepted("final", producer)


def law_hist_provisional_route_is_refused(producer):
    return not hist_accepted("provisional-draft", producer)


def law_hist_live_producer_is_never_canonical():
    return not hist_accepted(None, "live")


def law_hist_absent_claim_is_accepted_only_from_the_canonical_producer(producer):
    return hist_accepted(None, producer) == producer_is_canonical(producer)


def law_hist_unknown_route_is_refused(name, producer):
    return not hist_accepted("weird", producer)


def law_hist_canonical_producer_is_exactly_the_redux_code(producer):
    return producer_is_canonical(producer) == (producer == "redux")


def law_hist_accepted_agrees_with_its_two_forms(route, producer):
    return hist_accepted(route, producer) == hist_accepted_reference(route, producer)


def law_hist_refusal_names_itself(route, producer):
    return hist_accepted(route, producer) == (hist_reason_of(route, producer) is None)


# ---------------------------------------------------------------------------
# DECISAO 7 -- A VOTACAO DE ROTA (`app/panel/caption-formulation.js`)
# ---------------------------------------------------------------------------

#: O regex `PANEL_CLOSED_REASON` do ficheiro de producao: os motivos que sao o
#: fecho do PROPRIO painel (e que portanto nunca fabricam um `final`).
PANEL_CLOSED_PREFIXES = ("hold-timeout", "status-change", "flush", "stable")


def panel_closed_reason(reason):
    """`PANEL_CLOSED_REASON.test(reason)`."""
    return str(reason or "").startswith(PANEL_CLOSED_PREFIXES)


def fmt_is_final(buffer_final, saw_final, panel_closed):
    """`routeFor(reason) == 'final'`."""
    if buffer_final:
        return True
    if saw_final:
        return False
    return not panel_closed


def fmt_is_final_reference(buffer_final, saw_final, panel_closed):
    """A SEGUNDA FORMA -- o `Bool.pick` da producao, aqui escrito como cadeia."""
    return True if buffer_final else (False if saw_final else (not panel_closed))


def fmt_source(buffer_final, saw_final, has_producer, panel_closed):
    """`routeSourceFor(route)` -- o rotulo gravado no `meta.routeSource`."""
    if buffer_final or saw_final:
        return "worker-stamped"
    if has_producer:
        return "worker-stamped-producer"
    return "panel-deadline" if panel_closed else "fallback"


def law_fmt_worker_final_vote_is_final(saw_final, panel_closed):
    return fmt_is_final(True, saw_final, panel_closed)


def law_fmt_worker_partial_vote_is_never_final(panel_closed):
    return not fmt_is_final(False, True, panel_closed)


def law_fmt_panel_close_never_manufactures_final():
    return not fmt_is_final(False, False, True)


def law_fmt_audio_close_without_a_vote_is_final():
    return fmt_is_final(False, False, False)


def law_fmt_route_agrees_with_its_two_forms(buffer_final, saw_final, panel_closed):
    return (fmt_is_final(buffer_final, saw_final, panel_closed)
            == fmt_is_final_reference(buffer_final, saw_final, panel_closed))


def law_fmt_fallback_is_exactly_the_silent_default(buffer_final, saw_final, has_producer, panel_closed):
    return (fmt_source(buffer_final, saw_final, has_producer, panel_closed) == "fallback") == (
        not buffer_final and not saw_final and not has_producer and not panel_closed)


# ---------------------------------------------------------------------------
# A AMOSTRA
#
# Uma AMOSTRA explicita, nao um periodo vasto: o modelo e pequeno e as
# entradas sao（MILISSEGUNDOS, INSTANTES). A lista e pequena de proposito --
# um "exhaustive check" sobre um periodo arbitrario seria uma AMOSTRA com um
# nome maior.
# ---------------------------------------------------------------------------

TOK_TIMES = (0, 240, 400, 640, 800, 920, 1160, 1200)
INSTANTS = (0, 1, 239, 240, 241, 400, 639, 640, 800, 1000, 1200, 2000)
CAPACITIES = (0, 1, 2, 3)
LIVE_COUNTS = (0, 1, 2, 3, 5)
EPOCHS = (0, 1, 2, 3)

#: As sessoes da amostra. As tres ultimas sao o defeito do dono: um texto
#: enfileirado para uma fonte, e o epoch a mudar ANTES de o `_drain` correr.
EVENT_TRACES = (
    (),
    ("new_source",),
    ("blank",),
    ("push",),
    ("drain",),
    ("push", "drain"),
    ("push", "new_source", "drain"),
    ("push", "blank", "drain"),
    ("new_source", "blank", "push", "drain"),
    ("push", "new_source", "push", "drain", "blank", "drain"),
)


def _sample_word_lists():
    """As listas de palavras da amostra: a vazia, a de uma, e a de varias."""
    out = [()]
    out.append((TOK_TIMES[0],))
    out.append((TOK_TIMES[0], TOK_TIMES[1]))
    out.append(TOK_TIMES[:4])
    out.append(TOK_TIMES)
    return out


def _sample_caps():
    """Os estados do widget da amostra: fila vazia, fila de OUTRA fonte, ecra."""
    out = []
    for epoch in (0, 1, 2):
        out.append(cap(epoch, SLOT_IDLE, False))
        out.append(cap(epoch, SLOT_IDLE, True))
        out.append(cap(epoch, slot_held(epoch), True))
        out.append(cap(epoch, slot_held(max(0, epoch - 1)), True))
    return out


def check_all():
    """Corre as leis sobre a amostra. Devolve (violacoes, total_de_casos)."""
    violations = []
    total = 0

    def record(name, case, ok):
        nonlocal total
        total += 1
        if not ok:
            violations.append((name, case))

    for d in (True, False):
        record("Nat.revealed_flag_is_zero_or_one", (d,),
               law_revealed_flag_is_zero_or_one(d))
        record("Nat.of_bool_agrees_with_revealed_flag", (d,),
               law_of_bool_agrees_with_revealed_flag(d))

    for toks in _sample_word_lists():
        for t_ms in INSTANTS:
            record("Toks.count_due_counts_only_due_words", (toks, t_ms),
                   law_count_due_counts_only_due_words(toks, t_ms))
            record("Toks.count_due_of_an_empty_line_is_zero", (t_ms,),
                   law_count_due_of_an_empty_line_is_zero(t_ms))
        for tok in toks:
            for t_ms in INSTANTS:
                record("Toks.count_due_of_one_word_is_its_flag", (tok, t_ms),
                       law_count_due_of_one_word_is_its_flag(tok, t_ms))
        for t1_ms, t2_ms in itertools.product(INSTANTS, INSTANTS):
            record("Toks.count_due_is_monotone_in_time", (toks, t1_ms, t2_ms),
                   law_count_due_is_monotone_in_time(toks, t1_ms, t2_ms))

    for started, ended in itertools.product((True, False), repeat=2):
        record("Nat.live_flag_is_started_and_not_ended", (started, ended),
               law_live_flag_is_started_and_not_ended(started, ended))
    for ended in (True, False):
        record("Nat.live_flag_is_false_before_the_line_starts", (ended,),
               law_live_flag_is_false_before_the_line_starts(ended))

    for live, capacity in itertools.product(LIVE_COUNTS, CAPACITIES):
        record("Nat.window_rows_is_the_minimum", (live, capacity),
               law_window_rows_is_the_minimum(live, capacity))
        record("Nat.window_rows_never_exceeds_the_capacity", (live, capacity),
               law_window_rows_never_exceeds_the_capacity(live, capacity))
        record("Nat.window_rows_never_exceeds_the_live_rows", (live, capacity),
               law_window_rows_never_exceeds_the_live_rows(live, capacity))

    # A ORDEM DO EPOCH (2026-10-30).
    for c in _sample_caps():
        record("Cap.display_clean_before_new_source", (c,),
               law_display_clean_before_new_source(c))
        for trace in EVENT_TRACES:
            record("Cap.epoch_monotonic", (c, trace),
                   law_epoch_monotonic(c, trace))

    for stamp, cur in itertools.product(EPOCHS, EPOCHS):
        record("Nat.no_cross_source_paint", (stamp, cur),
               law_no_cross_source_paint(stamp, cur))

    # AS DUAS DECISOES (2026-11-08): o historico (DECISAO 6) e a votacao de
    # rota (DECISAO 7). O dominio e' EXAUSTIVO e pequeno -- quatro produtores,
    # quatro rotas, e os Bools -- por isso aqui a amostra e' o dominio inteiro.
    for producer in PRODUCERS:
        record("Hist.final_route_is_accepted", (producer,),
               law_hist_final_route_is_accepted(producer))
        record("Hist.provisional_route_is_refused", (producer,),
               law_hist_provisional_route_is_refused(producer))
        record("Hist.absent_claim_is_accepted_only_from_the_canonical_producer", (producer,),
               law_hist_absent_claim_is_accepted_only_from_the_canonical_producer(producer))
        record("Hist.canonical_producer_is_exactly_the_redux_code", (producer,),
               law_hist_canonical_producer_is_exactly_the_redux_code(producer))
    record("Hist.live_producer_is_never_canonical", (),
           law_hist_live_producer_is_never_canonical())

    for route, producer in itertools.product(ROUTES, PRODUCERS):
        record("Hist.unknown_route_is_refused", (route, producer),
               law_hist_unknown_route_is_refused("weird", producer))
        record("Hist.accepted_agrees_with_its_two_forms", (route, producer),
               law_hist_accepted_agrees_with_its_two_forms(route, producer))
        record("Hist.refusal_names_itself", (route, producer),
               law_hist_refusal_names_itself(route, producer))

    for bf, sf, pc in itertools.product((True, False), repeat=3):
        record("Fmt.worker_final_vote_is_final", (bf, sf, pc),
               law_fmt_worker_final_vote_is_final(sf, pc))
        record("Fmt.worker_partial_vote_is_never_final", (bf, sf, pc),
               law_fmt_worker_partial_vote_is_never_final(pc))
        record("Fmt.route_agrees_with_its_two_forms", (bf, sf, pc),
               law_fmt_route_agrees_with_its_two_forms(bf, sf, pc))
    record("Fmt.panel_close_never_manufactures_final", (),
           law_fmt_panel_close_never_manufactures_final())
    record("Fmt.audio_close_without_a_vote_is_final", (),
           law_fmt_audio_close_without_a_vote_is_final())
    for bf, sf, hp, pc in itertools.product((True, False), repeat=4):
        record("Fmt.fallback_is_exactly_the_silent_default", (bf, sf, hp, pc),
               law_fmt_fallback_is_exactly_the_silent_default(bf, sf, hp, pc))

    return violations, total


def self_test():
    """O `--neg-arm` tem de dar RED: um verificador que só diz "ok" nao é
    verificador. Aqui o modelo e TROCADO por um quebrado, e o verificador tem
    de apanhar."""
    broken = dict(
        revealed_flag=lambda due_value: 2 if due_value else 0,
        of_bool=lambda b: 0 if b else 1,
        live_flag=lambda started, ended: bool(started),
        # A FONTE NOVA RECOMECA A NUMERACAO -- o `+ 1` trocado por `0`
        # (o negativo `NEGATIVE_epoch_monotonic.bend`, em Bend).
        on_new_source=lambda c: cap(0, SLOT_IDLE, cap_shown(c)),
        # O BLANK ESQUECE-SE DA FILA -- `self._caption_pending = None`
        # apagado (o negativo `NEGATIVE_display_clean_before_new_source.bend`).
        on_blank=lambda c: cap(cap_epoch(c) + 1, cap_slot(c), False),
        # O DRAIN NAO COMPARA O CARIMBO -- a guarda `epoch != cur` apagada
        # (o negativo `NEGATIVE_no_cross_source_paint.bend`).
        paint_flag=lambda stamp, cur: 1,
        # A PORTA DO HISTORICO OLHA O PRODUTOR, NAO A ROTA -- a regra ANTERIOR
        # a 2026-11-05 (o negativo `NEGATIVE_hist_two_forms.bend`).
        hist_accepted=lambda route, producer: producer == "redux",
        # O FECHO DO PAINEL FABRICA UM `final` -- a confusao do
        # `status-change` de 2026-10-06 (o negativo
        # `NEGATIVE_fmt_panel_close.bend`).
        fmt_is_final=lambda bf, sf, pc: True if bf else (False if sf else pc),
    )

    saved = (revealed_flag, of_bool, live_flag, on_new_source, on_blank,
             paint_flag, hist_accepted, fmt_is_final)
    try:
        globals().update(broken)
        violations, total = check_all()
    finally:
        globals().update(zip(("revealed_flag", "of_bool", "live_flag",
                              "on_new_source", "on_blank", "paint_flag",
                              "hist_accepted", "fmt_is_final"),
                             saved))

    print("MODELO (model.py) -- amostra explicita")
    print("casos verificados: %d" % total)
    if not violations:
        print("NEG-ARM FAIL -- o verificador nao apanhou o modelo quebrado; "
              "esta ferramenta nao mede nada.")
        return 1
    names = sorted({name for name, _case in violations})
    print("NEG-ARM PASS: o modelo quebrado viola %d lei(s): %s"
          % (len(names), ", ".join(names)))
    print("YOUTUBE-LAWS-MODEL VERDICT RED-BY-DESIGN (rc=1)")
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true",
                        help="control: troca o modelo por um quebrado -- tem de dar RED")
    args = parser.parse_args(argv)

    if args.neg_arm:
        return self_test()

    violations, total = check_all()
    print("MODELO (model.py) -- a MESMA amostra, em Python")
    print("casos verificados: %d" % total)
    if violations:
        print("VIOLACOES (%d):" % len(violations))
        for name, case in violations[:10]:
            print("  %s %r" % (name, case))
        print("YOUTUBE-LAWS-MODEL VERDICT FAIL")
        return 1
    print("todas as leis da amostra respeitadas")
    print("NOTA: isto e uma AMOSTRA, nao uma prova. A prova e "
          "`bend PROOF.bend --verdict` (o kernel), e o portao e "
          "`bash tools/bend_verify.sh`.")
    print("YOUTUBE-LAWS-MODEL VERDICT GREEN (amostra)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
