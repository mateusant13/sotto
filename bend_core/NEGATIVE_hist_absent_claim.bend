# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 6.
#
# THE FALSE CLAIM: a line with NO route and NO producer declaration enters the
# transcript.
#
# That is the permissive default the panel carried before 2026-10-06: a commit
# that declared nothing reached `recordHistory` with `route` ABSENT and the
# `|| 'final'` default let the whole live caption in. The door is FAIL-CLOSED:
# a line that does not SAY it is canonical is not the canonical transcript.
#
# Here `Hist.route_of` maps `(InRouteAbsent{}, ProdNone{})` to `OutBatch{}`, so
# the law `Hist.absent_claim_is_accepted_only_from_the_canonical_producer` is
# false at `ProdNone{}` and true elsewhere.

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

# THE MUTATION: an undeclared line is accepted.
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
          OutBatch{}
        case ProdOther{tag}:
          OutNone{}

def Hist.accepted(route: InRoute, producer: Prod) -> Bool:
  Bool.not(OutRoute.is_none(Hist.route_of(route, producer)))

def Hist.producer_is_canonical(producer: Prod) -> Bool:
  match producer:
    case ProdRedux{}:
      True{}
    case ProdLive{}:
      False{}
    case ProdNone{}:
      False{}
    case ProdOther{tag}:
      False{}

law Hist.absent_claim_is_accepted_only_from_the_canonical_producer:
  for producer: Prod
  {Hist.accepted(InRouteAbsent{}, producer)
     == Hist.producer_is_canonical(producer) : Bool}

def Hist.absent_claim_is_accepted_only_from_the_canonical_producer(producer):
  match producer:
    case ProdNone{}:
      {==}
    case ProdLive{}:
      {==}
    case ProdRedux{}:
      {==}
    case ProdOther{tag}:
      {==}
