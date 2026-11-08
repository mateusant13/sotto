# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 6.
#
# THE FALSE CLAIM: the canonical-producer predicate is not exactly the `redux`
# code.
#
# `isCanonicalLine(meta)` is `producerOf(meta) === 'redux'` and nothing else.
# Without the extensional law this predicate could go constant `True{}` and the
# fail-closed door would still test green (F-6b: a `Bool` codomain hides a
# constant).
#
# Here `Hist.producer_is_canonical` also says YES to `ProdLive{}`, so the law
# `Hist.canonical_producer_is_exactly_the_redux_code` is false at that
# constructor.

import Base

type Prod is Data:
  ProdNone{}
  ProdLive{}
  ProdRedux{}
  ProdOther{tag: Nat}

def Nat.same_epoch(a: Nat, b: Nat) -> Bool:
  match a b:
    case 0n 0n:
      True{}
    case 0n 1n+bp:
      False{}
    case 1n+ap 0n:
      False{}
    case 1n+ap 1n+bp:
      Nat.same_epoch(ap, bp)

def Prod.code(producer: Prod) -> Nat:
  match producer:
    case ProdNone{}:
      0n
    case ProdLive{}:
      1n
    case ProdRedux{}:
      2n
    case ProdOther{tag}:
      3n

# THE MUTATION: the live producer is called canonical.
def Hist.producer_is_canonical(producer: Prod) -> Bool:
  match producer:
    case ProdRedux{}:
      True{}
    case ProdLive{}:
      True{}
    case ProdNone{}:
      False{}
    case ProdOther{tag}:
      False{}

law Hist.canonical_producer_is_exactly_the_redux_code:
  for producer: Prod
  {Hist.producer_is_canonical(producer)
     == Nat.same_epoch(Prod.code(producer), 2n) : Bool}

def Hist.canonical_producer_is_exactly_the_redux_code(producer):
  match producer:
    case ProdNone{}:
      {==}
    case ProdLive{}:
      {==}
    case ProdRedux{}:
      {==}
    case ProdOther{tag}:
      {==}
