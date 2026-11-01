# NEGATIVE CONTROL for bend_core/LAWS.bend.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `_main/bend-laws-gate.py` requires that
# `bend NEGATIVE_display_clean_before_new_source.bend --verdict` FAILS and
# names the law it was written to falsify.
#
# THE FALSE CLAIM: a new source starts from a clean widget.
#
# Here `Cap.on_blank` bumps the epoch and clears the pixels but KEEPS THE QUEUE
# -- `_blank_caption_window` (:9719) with `self._caption_pending = None`
# deleted. The two lines sit adjacent in production, and without the second one
# the text of the PREVIOUS audio is still in the single slot when the new
# source starts: the window is clean for an instant and then the old line is
# put back on screen.
#
# The law `Cap.display_clean_before_new_source` requires THREE things of that
# transition -- nothing queued, nothing on screen, and the epoch exactly the
# next one -- and this model violates the first on every state whose slot is
# held.
#
# The body below is the body the TRUE model takes (`PROOF.bend`): with the slot
# cleared the two cleanliness facts collapse by computation, leaving the epoch
# equality `same_epoch(1 + epoch, 1 + epoch)`. With the slot kept, the first
# conjunct stays a neutral `Slot.is_idle(slot)` and the conjunction cannot
# collapse, so the law def fails.

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

def Cap.slot(c: Cap) -> Slot:
  match c:
    case Cap{epoch, slot, shown}:
      slot

def Cap.shown(c: Cap) -> Bool:
  match c:
    case Cap{epoch, slot, shown}:
      shown

def Slot.is_idle(slot: Slot) -> Bool:
  match slot:
    case SlotIdle{}:
      True{}
    case SlotHeld{stamp}:
      False{}

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

def same_epoch_refl(a: Nat) -> {Nat.same_epoch(a, a) == True{} : Bool}:
  match a:
    case 0n:
      {==}
    case 1n+ap:
      same_epoch_refl(ap)

# THE MUTATION: the epoch moves on and the pixels are cleared, but the queue is
# KEPT (`self._caption_pending = None` deleted).
def Cap.on_blank(+c: Cap) -> Cap:
  Cap{Nat.add(1n, Cap.epoch(c)), Cap.slot(c), False{}}

law Cap.display_clean_before_new_source:
  for +c: Cap
  {Bool.and(
     Bool.and(Bool.not(Cap.shown(Cap.on_blank(c))),
              Slot.is_idle(Cap.slot(Cap.on_blank(c)))),
     Nat.same_epoch(Cap.epoch(Cap.on_blank(c)),
                    Nat.add(1n, Cap.epoch(c)))) == True{} : Bool}

def Cap.display_clean_before_new_source(c):
  same_epoch_refl(Nat.add(1n, Cap.epoch(c)))
