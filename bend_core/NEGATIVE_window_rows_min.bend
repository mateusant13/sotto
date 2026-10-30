# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_window_rows_min.bend` FAILS and names the law it was written to
# falsify.
#
# THE FALSE CLAIM: the window is not the minimum of the live rows and the
# capacity.
#
# Here the window ALWAYS shows the capacity (`window = capacity`), even when
# fewer lines are alive -- a window that invents lines. That is the "the
# caption shows blank lines" bug: the YouTube shows two rows, and the Sotto
# would show two rows with the extra ones empty.
#
# The law `Nat.window_rows_is_the_minimum` requires
# `window_rows(live, capacity) == min(capacity, live)`, which this model
# violates whenever fewer lines are alive than the capacity.

import Base

def Nat.window_rows(+live_rows: Nat, +capacity: Nat) -> Nat:
  capacity

law Nat.window_rows_is_the_minimum:
  for live_rows: Nat
  for capacity: Nat
  {Nat.window_rows(live_rows, capacity) == Nat.min(capacity, live_rows) : Nat}

def Nat.window_rows_is_the_minimum(live_rows, capacity):
  match live_rows capacity:
    case 0n _:
      {==}
    case 1n+lp 0n:
      {==}
    case 1n+lp 1n+cp:
      {==}
