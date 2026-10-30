# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_count_due_empty.bend` FAILS and names the law it was written to
# falsify.
#
# THE FALSE CLAIM: an empty line reveals nothing.
#
# Here the count of an empty line is 1 (instead of 0) -- the "the caption
# shows a phantom word" bug. This is the boundary that catches a model which
# counts everything: an empty line has no words, so its revealed count must be
# zero.
#
# The law `Toks.count_due_of_an_empty_line_is_zero` requires
# `count_due(ToksNil{}, t) == 0n`, which this model violates at every instant.

import Base

type Tok is Data:
  Tok{at_ms: Nat}

type Toks is Data:
  ToksNil{}
  ToksCon{head: Tok, tail: Toks}

def Tok.at_ms(tok: Tok) -> Nat:
  match tok:
    case Tok{at_ms}:
      at_ms

def Tok.due(tok: Tok, +t_ms: Nat) -> Bool:
  Nat.is_le(Tok.at_ms(tok), t_ms)

def Nat.revealed_flag(due: Bool) -> Nat:
  Bool.pick(Nat, due, 1n, 0n)

def Toks.count_due(toks: Toks, +t_ms: Nat) -> Nat:
  match toks:
    case ToksNil{}:
      1n
    case ToksCon{head, tail}:
      (Nat.revealed_flag(Tok.due(head, t_ms)) + Toks.count_due(tail, t_ms) : Nat)

law Toks.count_due_of_an_empty_line_is_zero:
  for t_ms: Nat
  {Toks.count_due(ToksNil{}, t_ms) == 0n : Nat}

def Toks.count_due_of_an_empty_line_is_zero(t_ms):
  {==}
