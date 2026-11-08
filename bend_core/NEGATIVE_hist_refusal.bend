# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 6.
#
# THE FALSE CLAIM: a refusal exists but does not name itself.
#
# `transcriptRoute(meta) === null` sse `historyRefusal(meta) !== null`: the
# panel reports a refused line as `HISTORY_REFUSED` with its reason. A refusal
# that returns `null` from BOTH surfaces is the silent drop this module was
# taught to stop committing.
#
# Here `Hist.reason_of` answers `ReasonNone{}` for the live caption's route
# while `Hist.accepted` still refuses it, so the law
# `Hist.refusal_names_itself` is false at `InRouteProvisional{}`.

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

type OutReason is Data:
  ReasonNone{}
  ReasonProvisional{}
  ReasonUnknownRoute{}
  ReasonNoRouteNoProducer{}

def OutRoute.is_none(r: OutRoute) -> Bool:
  match r:
    case OutNone{}:
      True{}
    case OutFinal{}:
      False{}
    case OutBatch{}:
      False{}

def OutReason.is_none(r: OutReason) -> Bool:
  match r:
    case ReasonNone{}:
      True{}
    case ReasonProvisional{}:
      False{}
    case ReasonUnknownRoute{}:
      False{}
    case ReasonNoRouteNoProducer{}:
      False{}

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
          OutNone{}
        case ProdNone{}:
          OutNone{}
        case ProdOther{tag}:
          OutNone{}

def Hist.accepted(route: InRoute, producer: Prod) -> Bool:
  Bool.not(OutRoute.is_none(Hist.route_of(route, producer)))

# THE MUTATION: the live caption is refused with NO reason to report.
def Hist.reason_of(route: InRoute, producer: Prod) -> OutReason:
  match route:
    case InRouteFinal{}:
      ReasonNone{}
    case InRouteProvisional{}:
      ReasonNone{}
    case InRouteOther{name}:
      ReasonUnknownRoute{}
    case InRouteAbsent{}:
      match producer:
        case ProdRedux{}:
          ReasonNone{}
        case ProdLive{}:
          ReasonNoRouteNoProducer{}
        case ProdNone{}:
          ReasonNoRouteNoProducer{}
        case ProdOther{tag}:
          ReasonNoRouteNoProducer{}

law Hist.refusal_names_itself:
  for route: InRoute
  for producer: Prod
  {Hist.accepted(route, producer)
     == OutReason.is_none(Hist.reason_of(route, producer)) : Bool}

def Hist.refusal_names_itself(route, producer):
  match route:
    case InRouteFinal{}:
      {==}
    case InRouteProvisional{}:
      {==}
    case InRouteOther{name}:
      {==}
    case InRouteAbsent{}:
      match producer:
        case ProdNone{}:
          {==}
        case ProdLive{}:
          {==}
        case ProdRedux{}:
          {==}
        case ProdOther{tag}:
          {==}
