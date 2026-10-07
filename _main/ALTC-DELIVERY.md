# Alt+C Hotkey Delivery — Evidence Receipt

**Status:** IN PROGRESS — investigation opened.

**Task:** Prove that the Alt+C hotkey registration actually delivers a signal to a
consumer, or prove that it cannot fire in this environment. A code path that exists
but was never observed firing is labelled SOURCE-ONLY.

**Method:**
1. Locate the registration call site (file:line, library, exact API).
2. Trace the destination of the emitted signal to a real consumer.
3. Fire the key and observe the receiving side change.
4. Record the real rc and real error for any step that fails.

**Rule applied:** every number carries population and window.

## Findings

(populated below as the investigation proceeds)