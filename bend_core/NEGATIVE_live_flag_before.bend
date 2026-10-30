# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_live_flag_before.bend` FAILS and names the law it was written to
# falsify.
#
# THE FALSE CLAIM: a line that has not started yet is NOT alive.
#
# Here the liveness looks only at the END (`live = not(ended)`): a line that
# has not started yet is already on screen. That is the "the caption appears
# before the video says it" bug -- the Sotto would show a line the YouTube has
# not reached.
#
# The law `Nat.live_flag_is_false_before_the_line_starts` requires
# `live_flag(False{}, ended) == False{}`, which this model violates for every
# `ended`.

import Base

def Nat.live_flag(started: Bool, ended: Bool) -> Bool:
  Bool.pick(Bool, ended, False{}, True{})

law Nat.live_flag_is_false_before_the_line_starts:
  for ended: Bool
  {Nat.live_flag(False{}, ended) == False{} : Bool}

def Nat.live_flag_is_false_before_the_line_starts(ended):
  match ended:
    case True{}:
      {==}
    case False{}:
      {==}
