# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that `bend --verdict
# NEGATIVE_live_flag.bend` FAILS and names the law it was written to falsify.
#
# THE FALSE CLAIM: a line's liveness is not "started and not ended".
#
# Here the liveness IGNORES THE END (`live = started`): a line that has
# already finished stays on screen forever. That is the "the line never goes
# away" bug -- the caption would pile up instead of scrolling.
#
# The law `Nat.live_flag_is_started_and_not_ended` requires
# `live_flag(started, ended) == and(started, not(ended))`, which this model
# violates on every input where the line has ended.

import Base

def Nat.live_flag(started: Bool, ended: Bool) -> Bool:
  Bool.pick(Bool, started, True{}, False{})

law Nat.live_flag_is_started_and_not_ended:
  for started: Bool
  for ended: Bool
  {Nat.live_flag(started, ended) == Bool.and(started, Bool.not(ended)) : Bool}

def Nat.live_flag_is_started_and_not_ended(started, ended):
  match started ended:
    case True{} True{}:
      {==}
    case True{} False{}:
      {==}
    case False{} True{}:
      {==}
    case False{} False{}:
      {==}
