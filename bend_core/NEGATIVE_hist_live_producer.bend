# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 6.
#
# THE FALSE CLAIM: a line with NO route and `producer:'live'` enters the
# canonical transcript as `batch`.
#
# That is the owner's "NUNCA" (2026-10-07, verbatim): *"o historico nao e' pra
# ser NUNCA o historico do live nvidia. e' pra ser do parakeet redux"*. The
# live producer with no route is the streaming engine's own history, which is
# exactly what the separation forbids.
#
# Here `Hist.route_of` maps `(InRouteAbsent{}, ProdLive{})` to `OutBatch{}`, so
# the law `Hist.live_producer_is_never_canonical` is false.

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

# THE MUTATION: the live producer is treated as canonical.
def Hist.route_of(route: InRoute, producer: Prod) -> OutRoute:
  match route:
    case InRouteFinal{}:
      OutFinal{}
    case InRouteProvisional{}:
      OutNone{}
    case InRouteOther{name}:
      OutNone{}
    case InRouteAbsent{}:
      match producer:
        case ProdRedux{}:
          OutBatch{}
        case ProdLive{}:
          OutBatch{}
        case ProdNone{}:
          OutNone{}
        case ProdOther{tag}:
          OutNone{}

def Hist.accepted(route: InRoute, producer: Prod) -> Bool:
  Bool.not(OutRoute.is_none(Hist.route_of(route, producer)))

law Hist.live_producer_is_never_canonical:
  {Hist.accepted(InRouteAbsent{}, ProdLive{}) == False{} : Bool}

def Hist.live_producer_is_never_canonical():
  {==}
