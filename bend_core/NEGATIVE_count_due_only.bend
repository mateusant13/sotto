# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_count_due_only.bend` FAILS and names the law it was written to
# falsify.
#
# THE FALSE CLAIM: the number of revealed words never exceeds the number of
# words in the line.
#
# Here the count ADDS ONE to the real count (`count = real + 1`): the "the
# caption shows one word too many" bug -- the Sotto would show a word the
# YouTube has not written yet, which is precisely the "1:1" the owner asked
# for.
#
# The law `Toks.count_due_counts_only_due_words` requires
# `count_due(toks, t) <= length(toks)`, which this model violates on every
# non-empty line.

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

def Toks.length(toks: Toks) -> Nat:
  match toks:
    case ToksNil{}:
      0n
    case ToksCon{head, tail}:
      (1n + Toks.length(tail) : Nat)

def Tok.due(tok: Tok, +t_ms: Nat) -> Bool:
  Nat.is_le(Tok.at_ms(tok), t_ms)

def Nat.revealed_flag(due: Bool) -> Nat:
  Bool.pick(Nat, due, 1n, 0n)

def Toks.count_due(toks: Toks, +t_ms: Nat) -> Nat:
  match toks:
    case ToksNil{}:
      0n
    case ToksCon{head, tail}:
      (Nat.add(Nat.revealed_flag(Tok.due(head, t_ms)),
               Toks.count_due(tail, t_ms)) : Nat)

law Toks.count_due_counts_only_due_words:
  for toks: Toks
  for t_ms: Nat
  {Nat.is_le(Toks.count_due(toks, t_ms), Toks.length(toks)) == True{} : Bool}

def Toks.count_due_counts_only_due_words(toks, t_ms):
  match toks:
    case ToksNil{}:
      {==}
    case ToksCon{head, tail}:
      {==}
