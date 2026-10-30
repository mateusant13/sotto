# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_count_due_one_word.bend` FAILS and names the law it was written to
# falsify.
#
# THE FALSE CLAIM: a one-word line's revealed count is that word's indicator.
#
# Here the count of a one-word line is ALWAYS 1 (instead of the indicator):
# the "the caption shows the word before YouTube writes it" bug. This is the
# law that pins the count to the word's own clock -- the other two count laws
# (`counts_only_due_words` and `is_monotone_in_time`) are satisfied by a model
# that always returns 0 AND by a model that always returns 1, so neither of
# them can catch this one. That is why the three ship together.
#
# The law `Toks.count_due_of_one_word_is_its_flag` requires
# `count_due(ToksCon{tok, ToksNil{}}, t) == revealed_flag(is_le(at_ms(tok), t))`,
# which this model violates whenever the word has not arrived yet.

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
      0n
    case ToksCon{head, tail}:
      (1n + Toks.count_due(tail, t_ms) : Nat)

law Toks.count_due_of_one_word_is_its_flag:
  for tok: Tok
  for t_ms: Nat
  {Toks.count_due(ToksCon{tok, ToksNil{}}, t_ms)
     == Nat.revealed_flag(Nat.is_le(Tok.at_ms(tok), t_ms)) : Nat}

def Toks.count_due_of_one_word_is_its_flag(tok, t_ms):
  {==}
