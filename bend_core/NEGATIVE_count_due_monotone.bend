# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_count_due_monotone.bend` FAILS and names the law it was written to
# falsify.
#
# THE FALSE CLAIM: revealing more words later never reveals fewer.
#
# Here the indicator has the SIGN SWAPPED: the word counts as ARRIVED when
# its time is still in the future (`at_ms >= t_ms` instead of `at_ms <= t_ms`).
# The count then DECREASES as time passes -- the word appears and then
# disappears -- which is the "the caption flickers and loses words" bug the
# owner reported as *"a frase era maior, foi sumindo"*.
#
# The law `Toks.count_due_is_monotone_in_time` requires the count at t1 to be
# no greater than the count at t2 whenever t1 <= t2, which this model violates.

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
  Nat.is_le(t_ms, Tok.at_ms(tok))

def Nat.revealed_flag(due: Bool) -> Nat:
  Bool.pick(Nat, due, 1n, 0n)

def Toks.count_due(toks: Toks, +t_ms: Nat) -> Nat:
  match toks:
    case ToksNil{}:
      0n
    case ToksCon{head, tail}:
      (Nat.revealed_flag(Tok.due(head, t_ms)) + Toks.count_due(tail, t_ms) : Nat)

law Toks.count_due_is_monotone_in_time:
  for toks: Toks
  for t1_ms: Nat
  for t2_ms: Nat
  for h: {Nat.is_le(t1_ms, t2_ms) == True{} : Bool}
  {Nat.is_le(Toks.count_due(toks, t1_ms), Toks.count_due(toks, t2_ms)) == True{} : Bool}

def Toks.count_due_is_monotone_in_time(toks, t1_ms, t2_ms, h):
  match h:
    case True{}:
      {==}
    case False{}:
      {==}
