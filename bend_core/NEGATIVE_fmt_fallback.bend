# NEGATIVE CONTROL for bend_core/LAWS.bend -- DECISAO 7.
#
# THE FALSE CLAIM: a line the PANEL closed is labelled `fallback`.
#
# `routeSourceFor` reserves `'fallback'` for exactly one case: no worker vote,
# no declared producer, and the route `final` -- the silent default announcing
# itself (P1 `4fb5b25380cbc8269977e22e`). Labelling a panel-deadline commit
# `fallback` destroys the only signal that tells a de-landing from a normal
# line.
#
# Here `Src.is_fallback` also says YES to `SrcPanelDeadline{}`, so
# `Fmt.fallback_is_exactly_the_silent_default` is false at
# `(False{}, False{}, False{}, True{})`.

import Base

type Src is Data:
  SrcWorker{}
  SrcWorkerProducer{}
  SrcPanelDeadline{}
  SrcFallback{}

def Fmt.source(buffer_final: Bool, saw_final: Bool, has_producer: Bool, panel_closed: Bool) -> Src:
  match buffer_final:
    case True{}:
      SrcWorker{}
    case False{}:
      match saw_final:
        case True{}:
          SrcWorker{}
        case False{}:
          match has_producer:
            case True{}:
              SrcWorkerProducer{}
            case False{}:
              match panel_closed:
                case True{}:
                  SrcPanelDeadline{}
                case False{}:
                  SrcFallback{}

# THE MUTATION: the panel's own close is labelled `fallback`.
def Src.is_fallback(src: Src) -> Bool:
  match src:
    case SrcFallback{}:
      True{}
    case SrcPanelDeadline{}:
      True{}
    case SrcWorker{}:
      False{}
    case SrcWorkerProducer{}:
      False{}

def Fmt.is_fallback_reference(buffer_final: Bool, saw_final: Bool, has_producer: Bool, panel_closed: Bool) -> Bool:
  Bool.and(Bool.not(buffer_final),
    Bool.and(Bool.not(saw_final),
      Bool.and(Bool.not(has_producer), Bool.not(panel_closed))))

law Fmt.fallback_is_exactly_the_silent_default:
  for buffer_final: Bool
  for saw_final: Bool
  for has_producer: Bool
  for panel_closed: Bool
  {Src.is_fallback(Fmt.source(buffer_final, saw_final, has_producer, panel_closed))
     == Fmt.is_fallback_reference(buffer_final, saw_final, has_producer, panel_closed) : Bool}

def Fmt.fallback_is_exactly_the_silent_default(buffer_final, saw_final, has_producer, panel_closed):
  match buffer_final saw_final has_producer panel_closed:
    case True{} True{} True{} True{}:
      {==}
    case True{} True{} True{} False{}:
      {==}
    case True{} True{} False{} True{}:
      {==}
    case True{} True{} False{} False{}:
      {==}
    case True{} False{} True{} True{}:
      {==}
    case True{} False{} True{} False{}:
      {==}
    case True{} False{} False{} True{}:
      {==}
    case True{} False{} False{} False{}:
      {==}
    case False{} True{} True{} True{}:
      {==}
    case False{} True{} True{} False{}:
      {==}
    case False{} True{} False{} True{}:
      {==}
    case False{} True{} False{} False{}:
      {==}
    case False{} False{} True{} True{}:
      {==}
    case False{} False{} True{} False{}:
      {==}
    case False{} False{} False{} True{}:
      {==}
    case False{} False{} False{} False{}:
      {==}
