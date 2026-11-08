# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 7.
#
# THE FALSE CLAIM: a line closed by the AUDIO, with no worker vote and no panel
# close, is not `final`.
#
# That default is DELIBERATE (`routeFor`'s else-half, 2026-11-04): the live
# worker is the pre-cure snapshot whose `_event` never stamps `final`, so
# removing the fallback would blank the owner's transcript. The fallback is
# allowed to exist; it is NOT allowed to be silent (that is the `fallback`
# label, DECISAO 7's last law).
#
# Here the else-half returns `False{}`, so
# `Fmt.audio_close_without_a_vote_is_final` is false at its only input.

import Base

# THE MUTATION: nobody manufactures `final` any more.
def Fmt.is_final(buffer_final: Bool, saw_final: Bool, panel_closed: Bool) -> Bool:
  match buffer_final:
    case True{}:
      True{}
    case False{}:
      match saw_final:
        case True{}:
          False{}
        case False{}:
          False{}

law Fmt.audio_close_without_a_vote_is_final:
  {Fmt.is_final(False{}, False{}, False{}) == True{} : Bool}

def Fmt.audio_close_without_a_vote_is_final():
  {==}
