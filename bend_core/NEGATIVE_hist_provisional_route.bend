# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 6.
#
# THE FALSE CLAIM: the LIVE caption (`route:'provisional-draft'`) is accepted
# into the transcript.
#
# That is the defect the owner reported verbatim (2026-10-06): *"o historico
# simplesmente mostra a legenda ao vivo"*. `route:'provisional-draft'` is the
# line the panel's own hold deadline closed, NOT a line the worker closed, and
# the history may NEVER take it.
#
# Here `Hist.route_of` maps `InRouteProvisional{}` to `OutFinal{}`, so the law
# `Hist.provisional_route_is_refused` is false on every input.

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

# THE MUTATION: the live caption ENTERS as `final`.
def Hist.route_of(route: InRoute, producer: Prod) -> OutRoute:
  match route:
    case InRouteFinal{}:
      OutFinal{}
    case InRouteProvisional{}:
      OutFinal{}
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

law Hist.provisional_route_is_refused:
  for producer: Prod
  {Hist.accepted(InRouteProvisional{}, producer) == False{} : Bool}

def Hist.provisional_route_is_refused(producer):
  match producer:
    case ProdNone{}:
      {==}
    case ProdLive{}:
      {==}
    case ProdRedux{}:
      {==}
    case ProdOther{tag}:
      {==}
