# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 7.
#
# THE FALSE CLAIM: the PANEL's own close manufactures a `final` route.
#
# `PANEL_CLOSED_REASON` (`hold-timeout`/`status-change`/`flush`/`stable`) is
# the panel's own clock, and `routeFor` answers `provisional-draft` for it.
# Promoting it to `final` is the measured 2026-10-06 defect: 10 of 10 lines the
# owner read as "the live caption" carried `reason=status-change` and reached
# the transcript.
#
# Here the panel-closed arm returns `True{}`, so
# `Fmt.panel_close_never_manufactures_final` is false at its only input.

import Base

# THE MUTATION: the panel's close IS a final route.
def Fmt.is_final(buffer_final: Bool, saw_final: Bool, panel_closed: Bool) -> Bool:
  match buffer_final:
    case True{}:
      True{}
    case False{}:
      match saw_final:
        case True{}:
          False{}
        case False{}:
          panel_closed

law Fmt.panel_close_never_manufactures_final:
  {Fmt.is_final(False{}, False{}, True{}) == False{} : Bool}

def Fmt.panel_close_never_manufactures_final():
  {==}
