#!/usr/bin/env python
"""O MODELO DAS LEIS, em Python -- para maquinas sem Bend 2.

Este ficheiro NAO e o portao. O portao e `bend PROOF.bend --verdict`, dentro do
distro WSL `ubuntu-bend`, e e o kernel (Lean 4.34 via BendTT) que prova as
leis. Este ficheiro e o MESMO MODELO escrito em Python, para um host sem o
toolchain -- e, principalmente, para um LEITOR poder ver o que as leis dizem
sem instalar nada.

O QUE ESTE FICHEIRO FAZ, e o que ele NAO FAZ:

  FAZ: calcula as funcoes do modelo (`Nat.revealed_flag`, `Toks.count_due`,
  `Nat.live_flag`, `Nat.window_rows`) e CHECA as leis sobre uma amostra
  EXPLICITA de entradas. E uma AMOSTRA, nao uma prova: o kernel prova para
  TODAS as entradas.

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


def _sample_word_lists():
    """As listas de palavras da amostra: a vazia, a de uma, e a de varias."""
    out = [()]
    out.append((TOK_TIMES[0],))
    out.append((TOK_TIMES[0], TOK_TIMES[1]))
    out.append(TOK_TIMES[:4])
    out.append(TOK_TIMES)
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

    return violations, total


def self_test():
    """O `--neg-arm` tem de dar RED: um verificador que só diz "ok" nao é
    verificador. Aqui o modelo e TROCADO por um quebrado, e o verificador tem
    de apanhar."""
    broken = dict(
        revealed_flag=lambda due_value: 2 if due_value else 0,
        of_bool=lambda b: 0 if b else 1,
        live_flag=lambda started, ended: bool(started),
    )

    saved = (revealed_flag, of_bool, live_flag)
    try:
        globals()["revealed_flag"] = broken["revealed_flag"]
        globals()["of_bool"] = broken["of_bool"]
        globals()["live_flag"] = broken["live_flag"]
        violations, total = check_all()
    finally:
        globals()["revealed_flag"] = saved[0]
        globals()["of_bool"] = saved[1]
        globals()["live_flag"] = saved[2]

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
          "`_main/bend-laws-gate.py`.")
    print("YOUTUBE-LAWS-MODEL VERDICT GREEN (amostra)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
