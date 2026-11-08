# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 7.
#
# THE FALSE CLAIM: the two forms of the route decision disagree.
#
# `Fmt.is_final` (`match` on the flags) and `Fmt.is_final_reference`
# (`Bool.pick` chain) are two implementations of ONE decision; the extensional
# law is what stops either from drifting. Here the reference INVERTS the
# panel-closed arm, so `Fmt.route_agrees_with_its_two_forms` is false at
# `(False{}, False{}, True{})`.

import Base

def Fmt.is_final(buffer_final: Bool, saw_final: Bool, panel_closed: Bool) -> Bool:
  match buffer_final:
    case True{}:
      True{}
    case False{}:
      match saw_final:
        case True{}:
          False{}
        case False{}:
          Bool.not(panel_closed)

# THE MUTATION: the reference form has the panel-closed arm backwards.
def Fmt.is_final_reference(buffer_final: Bool, saw_final: Bool, panel_closed: Bool) -> Bool:
  Bool.pick(Bool, buffer_final, True{},
    Bool.pick(Bool, saw_final, False{},
      Bool.pick(Bool, panel_closed, True{}, False{})))

law Fmt.route_agrees_with_its_two_forms:
  for buffer_final: Bool
  for saw_final: Bool
  for panel_closed: Bool
  {Fmt.is_final(buffer_final, saw_final, panel_closed)
     == Fmt.is_final_reference(buffer_final, saw_final, panel_closed) : Bool}

def Fmt.route_agrees_with_its_two_forms(buffer_final, saw_final, panel_closed):
  match buffer_final saw_final panel_closed:
    case True{} True{} True{}:
      {==}
    case True{} True{} False{}:
      {==}
    case True{} False{} True{}:
      {==}
    case True{} False{} False{}:
      {==}
    case False{} True{} True{}:
      {==}
    case False{} True{} False{}:
      {==}
    case False{} False{} True{}:
      {==}
    case False{} False{} False{}:
      {==}
