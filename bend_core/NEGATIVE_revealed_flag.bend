# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_revealed_flag.bend` FAILS and names the law it was written to
# falsify. If this file ever prints ALL PROOFS CHECK, the gate is broken and
# the laws in LAWS.bend mean nothing.
#
# THE FALSE CLAIM: the "the word has arrived" indicator is zero or one.
#
# Here the indicator returns the DIFFERENCE (`t_ms - at_ms`) instead of the
# boolean -- a word at 240 ms with the instant at 1000 ms gives 760 instead of
# 1. That is the "the caption counts words by elapsed time" bug: the count
# would be a number of milliseconds, not a number of words.
#
# The law `Nat.revealed_flag_is_zero_or_one` requires the indicator to be at
# most 1, which this model violates on every input where the word arrived more
# than one millisecond before the instant.
#
# A NOTE ON WHY THIS FILE IS STANDALONE: the kernel stops at the FIRST
# failing law, so a file with two false claims would only ever exercise the
# first. Every control lives in its own file, one false claim each.

import Base

def Nat.revealed_flag(due: Bool) -> Nat:
  # O MODELO FALSO: devolve 2 em vez de 1 -- "a palavra conta duas vezes".
  # A lei `Nat.revealed_flag_is_zero_or_one` exige `<= 1`, e 2 viola-a.
  Bool.pick(Nat, due, 2n, 0n)

law Nat.revealed_flag_is_zero_or_one:
  for due: Bool
  {Nat.is_le(Nat.revealed_flag(due), 1n) == True{} : Bool}

def Nat.revealed_flag_is_zero_or_one(due):
  match due:
    case True{}:
      {==}
    case False{}:
      {==}
