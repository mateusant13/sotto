# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_window_rows_capacity.bend` FAILS and names the law it was written to
# falsify.
#
# THE FALSE CLAIM: the window never exceeds the capacity.
#
# Here the window shows ONE MORE row than the capacity (`window = live + 1`):
# the classic off-by-one, which is exactly what the `ROLLUP_ROWS` constant in
# `app/webview/youtube_reveal.py` has to be careful about. With a capacity of 2
# the YouTube shows two rows, and this model shows three.
#
# The law `Nat.window_rows_never_exceeds_the_capacity` requires
# `window_rows(live, capacity) <= capacity`, which this model violates on every
# input.

import Base

def Nat.window_rows(+live_rows: Nat, +capacity: Nat) -> Nat:
  Nat.add(live_rows, 1n)

law Nat.window_rows_never_exceeds_the_capacity:
  for live_rows: Nat
  for capacity: Nat
  {Nat.is_le(Nat.window_rows(live_rows, capacity), capacity) == True{} : Bool}

def Nat.window_rows_never_exceeds_the_capacity(live_rows, capacity):
  match live_rows capacity:
    case 0n _:
      {==}
    case 1n+lp 0n:
      {==}
    case 1n+lp 1n+cp:
      {==}
