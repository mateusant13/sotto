# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_window_rows_live.bend` FAILS and names the law it was written to
# falsify.
#
# THE FALSE CLAIM: the window never exceeds the live rows.
#
# Here the window shows the CAPACITY even when fewer lines are alive -- the
# window INVENTS lines that are not on the screen. That is the "the caption
# shows a line YouTube is not showing" bug.
#
# The law `Nat.window_rows_never_exceeds_the_live_rows` requires
# `window_rows(live, capacity) <= live`, which this model violates whenever
# the capacity is bigger than the number of live rows.

import Base

def Nat.window_rows(+live_rows: Nat, +capacity: Nat) -> Nat:
  capacity

law Nat.window_rows_never_exceeds_the_live_rows:
  for live_rows: Nat
  for capacity: Nat
  {Nat.is_le(Nat.window_rows(live_rows, capacity), live_rows) == True{} : Bool}

def Nat.window_rows_never_exceeds_the_live_rows(live_rows, capacity):
  match live_rows capacity:
    case 0n _:
      {==}
    case 1n+lp 0n:
      {==}
    case 1n+lp 1n+cp:
      {==}
