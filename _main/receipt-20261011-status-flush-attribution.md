# Status-flush attribution — the named gap was mis-worded (2026-10-11)

**Question.** The STEP 4 lane left this open: *"`wireStatus()` flushes EVERY engine on every non-empty
status payload (unattributed to a source) — two live sources cross-commit."* Is that true?

**Answer: NO. The words "cross-commit" are refuted.** One app's status can close the OTHER app's line
early — a split — but it can never put one app's words on the other app's line. Three facts, read off
the shipped bytes (nothing was launched: the owner stop order is in force):

1. `app/panel/panel.js:2452` — `for (const engine of engines.values()) engine.flush('status-change');`
   The comment above it (`:2450-2451`) already states the trade: *"EVERY source's engine (STEP 4), or
   one app's tail is stranded while the other's is closed."* So the broad flush is deliberate, not an
   oversight.
2. `app/panel/caption-formulation.js:741-743` — `flush(reason)` is `return commit(reason || 'flush')`.
   A status-forced close is THE SAME commit path as any other, and that path builds the meta from the
   ENGINE's own key: `:582-588`, `engineSource === null ? {route,start,routeSource}` /
   `{route,start,routeSource, source: engineSource}`, with the comment at `:577-581` — *"`source`
   (STEP 4) is the ENGINE's own key ... It is never read from the fragment: one engine per source is
   what separates two apps."* There is no code path by which a fragment's source can leak into another
   engine's commit.
3. The committed oracle `_main/panel-row-identity-oracle.js` already measures the consequence: ARM D
   replays 3 commits over 3 sources at the SAME `start = 0.0` and requires **3 rows, `replaced=0`, 3
   engines**, and it goes **RED** under the pre-change keying. ARM D drives `commit` directly, and
   `flush` IS `commit` (fact 2), so the attribution it proves holds for a status-forced close too.

**The real residual, stated correctly.** A status payload is not attributed to a source, so an app that
goes quiet closes the OTHER app's held tail at that instant: more, shorter lines (a sentence split),
never a wrong attribution. The cure — flush only the engine the status names — is **not implementable
on this revision**: `panel.js:2516-2524 statusPayload(payload)` reads ONLY `{text, kind}` (`text` as a
string, `kind` trimmed and lowercased), and the shell sends exactly that shape. Adding a speculative
`payload.source` read that nothing sends would be dead code, which this repo has already refused once
(see the housekeeping sweep, item 2). So the gap is **named, not patched**: it reopens the day the
status channel carries a source, and the one-line change is then `if (src === null || key === src)`.

## NOT MEASURED

- No two-source run exists, so this is a **code-path proof, not a runtime one**. What it refutes is the
  ATTRIBUTION claim; what it leaves untouched is how often a real run would split a line this way.
- The shell-side status payload was read, not driven: no launch.
