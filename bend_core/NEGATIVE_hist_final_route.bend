# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 6.
#
# A proof gate that cannot fail is decoration. This file states ONE claim that
# must NOT check, and `tools/bend_verify.sh` requires that
# `bend --verdict NEGATIVE_hist_final_route.bend` FAILS and names the law it
# was written to falsify.
#
# THE FALSE CLAIM: a worker-CLOSED line (`route:'final'`) is refused because
# its producer is not the canonical one.
#
# That is the door BEFORE 2026-11-05 (`app/panel/history-source.js`): the only
# producer that passed was `'redux'`, the batch pass is off by default, and the
# owner's transcript had ZERO writers while 3830 `CAPTION_APPLIED` were on the
# log. The producer is PROVENANCE now, not the gate.
#
# Here `Hist.route_of` maps `InRouteFinal{}` to NO route, so the law
# `Hist.final_route_is_accepted` is false on every input.

import Base

type Prod is Data:
  ProdNone{}
  ProdLive{}
  ProdRedux{}
  ProdOther{tag: Nat}

type InRoute is Data:
  InRouteAbsent{}
  InRouteFinal{}
  InRouteProvisional{}
  InRouteOther{name: Nat}

type OutRoute is Data:
  OutNone{}
  OutFinal{}
  OutBatch{}

def OutRoute.is_none(r: OutRoute) -> Bool:
  match r:
    case OutNone{}:
      True{}
    case OutFinal{}:
      False{}
    case OutBatch{}:
      False{}

# THE MUTATION: the closed route is REFUSED.
def Hist.route_of(route: InRoute, producer: Prod) -> OutRoute:
  match route:
    case InRouteFinal{}:
      OutNone{}
    case InRouteProvisional{}:
      OutNone{}
    case InRouteOther{name}:
      OutNone{}
    case InRouteAbsent{}:
      match producer:
        case ProdRedux{}:
          OutBatch{}
        case ProdLive{}:
          OutNone{}
        case ProdNone{}:
          OutNone{}
        case ProdOther{tag}:
          OutNone{}

def Hist.accepted(route: InRoute, producer: Prod) -> Bool:
  Bool.not(OutRoute.is_none(Hist.route_of(route, producer)))

law Hist.final_route_is_accepted:
  for producer: Prod
  {Hist.accepted(InRouteFinal{}, producer) == True{} : Bool}

def Hist.final_route_is_accepted(producer):
  match producer:
    case ProdNone{}:
      {==}
    case ProdLive{}:
      {==}
    case ProdRedux{}:
      {==}
    case ProdOther{tag}:
      {==}
