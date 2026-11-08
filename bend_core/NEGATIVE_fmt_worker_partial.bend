# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 7.
#
# THE FALSE CLAIM: the worker's `final:false` vote (the LIVE stream) does not
# stop the route from being `final`.
#
# `routeFor(reason)`: once `bufferSawFinal` is true and `bufferFinal` is false,
# the route is `provisional-draft` WHATEVER the reason -- the panel's own clock
# cannot promote the live caption into the history. Here the `saw_final` flag
# is not read, so a live line is promoted whenever the panel's timer fires.
#
# `Fmt.worker_partial_vote_is_never_final` is false at `panel_closed = True{}`.

import Base

# THE MUTATION: `saw_final` is never read.
def Fmt.is_final(buffer_final: Bool, saw_final: Bool, panel_closed: Bool) -> Bool:
  match buffer_final:
    case True{}:
      True{}
    case False{}:
      Bool.not(panel_closed)

law Fmt.worker_partial_vote_is_never_final:
  for panel_closed: Bool
  {Fmt.is_final(False{}, True{}, panel_closed) == False{} : Bool}

def Fmt.worker_partial_vote_is_never_final(panel_closed):
  {==}
