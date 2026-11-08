# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 6.
#
# THE FALSE CLAIM: a route the writer does NOT know enters the transcript as
# if it were `final`.
#
# `historyDecision` refuses every non-empty route other than `final` and
# `provisional-draft` (`unknown-route`): a writer that invents a route has not
# said the line ended, and guessing would manufacture history.
#
# Here `Hist.route_of` maps `InRouteOther{}` to `OutFinal{}`, so the law
# `Hist.unknown_route_is_refused` is false.

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

# THE MUTATION: an unknown route is accepted as `final`.
def Hist.route_of(route: InRoute, producer: Prod) -> OutRoute:
  match route:
    case InRouteFinal{}:
      OutFinal{}
    case InRouteProvisional{}:
      OutNone{}
    case InRouteOther{name}:
      OutFinal{}
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

law Hist.unknown_route_is_refused:
  for name: Nat
  for producer: Prod
  {Hist.accepted(InRouteOther{name}, producer) == False{} : Bool}

def Hist.unknown_route_is_refused(name, producer):
  {==}
