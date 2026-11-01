# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that
# `bend NEGATIVE_no_cross_source_paint.bend --verdict` FAILS and names the law
# it was written to falsify.
#
# THE FALSE CLAIM: a paint carries the current epoch.
#
# Here the drain paints whatever is in the slot, without comparing the stamp
# with the current epoch. That is `_drain` BEFORE 2026-10-30 -- the guard
#
#     cur = int(getattr(self, '_source_epoch', 0))
#     if epoch != cur:
#         log(f'CAPTION_DROP_EPOCH enq={epoch} cur={cur} ...')
#         return
#
# with its `return` deleted, so a text enqueued for the previous audio is
# painted on the new one. That is the owner's report, verbatim: *"a legenda do
# audio anterior aparece no audio novo"*.
#
# The law `Nat.no_cross_source_paint` requires the paint indicator to be the
# epoch comparison in BOTH directions, so this model violates it on every pair
# with `stamp != cur` (it answers 1 where the comparison answers 0).
#
# The body below is the body the TRUE model takes (`PROOF.bend`): the model's
# structural equality agreeing with Base's `Cmp.is_eq(Nat.cmp(..))`, then the
# `of_bool`/`revealed_flag` bridge proved earlier in the same proof file. Only
# the model's `Nat.paint_flag` is mutated -- which is the whole point of a
# control: the SAME discharge, against a broken decision, must not check.

import Base

def Nat.revealed_flag(due: Bool) -> Nat:
  Bool.pick(Nat, due, 1n, 0n)

def Nat.of_bool(b: Bool) -> Nat:
  match b:
    case True{}:
      1n
    case False{}:
      0n

def Nat.of_bool_agrees_with_revealed_flag(due: Bool) -> {Nat.of_bool(due) == Nat.revealed_flag(due) : Nat}:
  match due:
    case True{}:
      {==}
    case False{}:
      {==}

def Nat.same_epoch(a: Nat, b: Nat) -> Bool:
  match a b:
    case 0n 0n:
      True{}
    case 0n 1n+bp:
      False{}
    case 1n+ap 0n:
      False{}
    case 1n+ap 1n+bp:
      Nat.same_epoch(ap, bp)

def same_epoch_agrees(a: Nat, b: Nat) -> {Nat.same_epoch(a, b) == Cmp.is_eq(Nat.cmp(a, b)) : Bool}:
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+bp:
      {==}
    case 1n+ap 0n:
      {==}
    case 1n+ap 1n+bp:
      same_epoch_agrees(ap, bp)

# THE MUTATION: paint always. The stamp and the current epoch are never
# compared -- the guard that makes one source's queue unpaintable in another.
def Nat.paint_flag(stamp: Nat, +cur: Nat) -> Nat:
  1n

law Nat.no_cross_source_paint:
  for +stamp: Nat
  for +cur: Nat
  {Nat.paint_flag(stamp, cur)
     == Nat.of_bool(Cmp.is_eq(Nat.cmp(stamp, cur))) : Nat}

def Nat.no_cross_source_paint(stamp, cur):
  Equal.trans(Nat, Nat.revealed_flag(Nat.same_epoch(stamp, cur)), Nat.revealed_flag(Cmp.is_eq(Nat.cmp(stamp, cur))), Nat.of_bool(Cmp.is_eq(Nat.cmp(stamp, cur))), Equal.cong(Bool, Nat, z => Nat.revealed_flag(z), Nat.same_epoch(stamp, cur), Cmp.is_eq(Nat.cmp(stamp, cur)), same_epoch_agrees(stamp, cur)), Equal.sym(Nat, Nat.of_bool(Cmp.is_eq(Nat.cmp(stamp, cur))), Nat.revealed_flag(Cmp.is_eq(Nat.cmp(stamp, cur))), Nat.of_bool_agrees_with_revealed_flag(Cmp.is_eq(Nat.cmp(stamp, cur)))))
