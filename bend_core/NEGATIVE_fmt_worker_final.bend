# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 7.
#
# THE FALSE CLAIM: the worker's `final:true` vote does not decide the route.
#
# `routeFor(reason)` reads `bufferFinal` FIRST: a line the worker CLOSED is
# `final` whatever the panel's reason was. Here the vote is ignored and only
# `saw_final`/`reason` decide, so a genuinely closed line is downgraded to the
# live caption's route whenever the panel's own timer closed the buffer.
#
# `Fmt.worker_final_vote_is_final` is false at every `panel_closed = True{}`.

import Base

# THE MUTATION: `bufferFinal` is never read.
def Fmt.is_final(buffer_final: Bool, saw_final: Bool, panel_closed: Bool) -> Bool:
  match saw_final:
    case True{}:
      False{}
    case False{}:
      Bool.not(panel_closed)

law Fmt.worker_final_vote_is_final:
  for saw_final: Bool
  for panel_closed: Bool
  {Fmt.is_final(True{}, saw_final, panel_closed) == True{} : Bool}

def Fmt.worker_final_vote_is_final(saw_final, panel_closed):
  {==}
