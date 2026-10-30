# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_of_bool_agrees.bend` FAILS and names the law it was written to
# falsify. If this file ever prints ALL PROOFS CHECK, the gate is broken and
# the laws in LAWS.bend mean nothing.
#
# THE FALSE CLAIM: the two shapes of the "the word has arrived" indicator do
# NOT agree.
#
# `Nat.of_bool` is the `match` shape (1 on True, 0 on False) and
# `Nat.revealed_flag` is the `Bool.pick` shape (1 on True, 0 on False). The
# law `Nat.of_bool_agrees_with_revealed_flag` says they compute the same
# thing. Here `of_bool` is INVERTED: it returns 0 on `True{}` and 1 on
# `False{}` -- the "the indicator is off when the word arrived" bug, which
# would show the word BEFORE YouTube shows it.
#
# The kernel stops at the FIRST failing law, so every control lives in its own
# file: one false claim each, so that every law family has a control that is
# actually EVALUATED rather than skipped behind an earlier failure.

import Base

def Nat.of_bool(b: Bool) -> Nat:
  match b:
    case True{}:
      0n
    case False{}:
      1n

def Nat.revealed_flag(due: Bool) -> Nat:
  Bool.pick(Nat, due, 1n, 0n)

law Nat.of_bool_agrees_with_revealed_flag:
  for due: Bool
  {Nat.of_bool(due) == Nat.revealed_flag(due) : Nat}

def Nat.of_bool_agrees_with_revealed_flag(due):
  match due:
    case True{}:
      {==}
    case False{}:
      {==}
