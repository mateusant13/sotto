# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that
# `bend NEGATIVE_epoch_monotonic.bend --verdict` FAILS and names the law it was
# written to falsify.
#
# THE FALSE CLAIM: a new source does not take the source epoch forwards.
#
# Here `Cap.on_new_source` RESETS the epoch to 0 -- the plausible-looking
# implementation "recomecar a numeracao na fonte nova" (`self._source_epoch =
# 0` instead of `int(getattr(self, '_source_epoch', 0)) + 1`, the line that
# `start_worker` (:9514) and `_blank_caption_window` (:9719) both carry). It is
# wrong for exactly the reason the monotonicity law exists: the epoch is what
# tells a stamp of the previous source from the current one, so renumbering
# from zero can hand an OLD text the NEW epoch -- `Nat.no_cross_source_paint`
# keeps checking while the jumpscare comes back.
#
# The law `Cap.epoch_monotonic` in LAWS.bend is over `Evs.run` (a whole
# session). This file states the STEP of it -- the arm that carries the
# increment -- because a run only goes forwards if its steps do, and because
# written this way the failing def IS the law (`Location:
# Cap.epoch_monotonic`) and not a helper inside its proof.
#
# The body below is the body the TRUE model takes at this step: `le_1_r`
# proves `epoch <= 1 + epoch`, which is what `epoch(on_new_source(c))` becomes
# once the transition adds one. Against the reset there is nothing to apply it
# to, so the law def fails.

import Base

type Slot is Data:
  SlotIdle{}
  SlotHeld{stamp: Nat}

type Cap is Data:
  Cap{epoch: Nat, slot: Slot, shown: Bool}

def Cap.epoch(c: Cap) -> Nat:
  match c:
    case Cap{epoch, slot, shown}:
      epoch

def Cap.shown(c: Cap) -> Bool:
  match c:
    case Cap{epoch, slot, shown}:
      shown

# THE MUTATION: the epoch of a new source is ZERO, not the previous plus one.
def Cap.on_new_source(c: Cap) -> Cap:
  Cap{0n, SlotIdle{}, Cap.shown(c)}

def le_1_r(a: Nat) -> {Nat.is_le(a, Nat.add(1n, a)) == True{} : Bool}:
  match a:
    case 0n:
      {==}
    case 1n+ap:
      le_1_r(ap)

law Cap.epoch_monotonic:
  for c: Cap
  {Nat.is_le(Cap.epoch(c), Cap.epoch(Cap.on_new_source(c))) == True{} : Bool}

def Cap.epoch_monotonic(c):
  le_1_r(Cap.epoch(c))
