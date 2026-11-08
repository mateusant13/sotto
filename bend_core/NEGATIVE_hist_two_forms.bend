# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 6.
#
# THE FALSE CLAIM: the accepted predicate and its written rule disagree.
#
# F-6b: a `Bool`-returning model def that is never compared to a SECOND form
# can go constant and every implication-shaped law still checks. Here the
# mutation is the exact pre-fix projection: `accepted` answers from the
# PRODUCER alone, ignoring the route -- so a worker-CLOSED line from the live
# producer would be refused while the route says it was closed.
#
# `Hist.accepted_reference` keeps the true rule, so
# `Hist.accepted_agrees_with_its_two_forms` is false at
# `(InRouteFinal{}, ProdLive{})`.

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

# THE MUTATION: the door looks at the producer only.
def Hist.accepted(route: InRoute, producer: Prod) -> Bool:
  match producer:
    case ProdRedux{}:
      True{}
    case ProdLive{}:
      False{}
    case ProdNone{}:
      False{}
    case ProdOther{tag}:
      False{}

# The true rule, kept as the second form.
def Hist.accepted_reference(route: InRoute, producer: Prod) -> Bool:
  match route:
    case InRouteFinal{}:
      True{}
    case InRouteProvisional{}:
      False{}
    case InRouteOther{name}:
      False{}
    case InRouteAbsent{}:
      match producer:
        case ProdRedux{}:
          True{}
        case ProdLive{}:
          False{}
        case ProdNone{}:
          False{}
        case ProdOther{tag}:
          False{}

law Hist.accepted_agrees_with_its_two_forms:
  for route: InRoute
  for producer: Prod
  {Hist.accepted(route, producer)
     == Hist.accepted_reference(route, producer) : Bool}

def Hist.accepted_agrees_with_its_two_forms(route, producer):
  match route:
    case InRouteFinal{}:
      match producer:
        case ProdNone{}:
          {==}
        case ProdLive{}:
          {==}
        case ProdRedux{}:
          {==}
        case ProdOther{tag}:
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
