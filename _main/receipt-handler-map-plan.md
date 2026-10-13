# PLAN — per-kind isolation in the handler map (NOT done, and why)

Date 2026-10-13. Written instead of executed, deliberately.

## The defect this closes

`SottoHost.dispatch` builds its handler map as a dict literal. A dict literal
evaluates EVERY value, so ONE entry naming a method the class does not have raises
`AttributeError` while BUILDING the map -- before `.get(kind)` -- and dispatch dies for
EVERY kind. MEASURED 2026-10-13: two and a half hours of a dead page-to-shell channel,
the deferred assets served as empty bodies, and the shell own log said NOTHING.

The guard committed in `9c8649f` turns that SILENCE into a `BRIDGE_HANDLER_MAP_FAILED`
log line, and a mutant proved it keeps `dispatch` alive. **What it does not do is
isolate the bad entry: the fallback is an empty map, so every kind still dies, loudly.**

## The two candidate fixes, and why NEITHER was done tonight

### (a) NAME -> NAME, resolved with `getattr`

Build `{kind: 'method_name'}` and resolve each in a loop, skipping (and logging) the
ones that do not resolve. TRUE per-kind isolation.

**Cost: a rewrite of ~40 entries.** Three of them are lambdas (`hide`, `toggle`, `quit`
call `self._shell`), so they need their own handling, and the rest each lose their
`self._` prefix. **I broke this file five times tonight with smaller edits**, and it is
the shell the owner app runs: a syntax error there is a dead app, not a red gate.

### (b) `__getattr__` returning a no-op for a missing `_`-prefixed name

Six lines, and it would give real per-kind isolation: the bad entry resolves to a
silent no-op, every other kind keeps working.

**REJECTED, AND THE REASON IS IN THE FILE.** `sotto_webview.py:3569-3573` records that
pywebview walks this object graph and that attributes whose name starts with `_` are
skipped BEFORE they are read -- that is exactly what stops
`maximum recursion depth exceeded ... shell.form.Controls.Owner.DefaultFont.FontFamily`
from happening. A `__getattr__` on `SottoHost` changes what EVERY missing attribute
does, for pywebview too. That is not a fix; it is a new class of surprise in the one
place the file already warns about.

## What IS in place, and what a future attempt has

* `_main/bridge-handler-map-oracle.py` calls the REAL `dispatch` with an unknown kind.
  Control PASS 3 checks; `--neg-arm` adds one bogus entry to a COPY and goes RED.
* It is IN the house battery: `instruments-battery.mjs`, both colours, **81/81 rc=0**
  since `11f9dce`.
* So fix (a) can be attempted with a net under it: **run the battery before and after**
  and the map either builds or it does not.

## The rule this leaves

A gate that turns a silent failure into a loud one is worth having. **A gate is not the
fix.** The empty-map fallback still kills every kind, and saying so in the comment -- as
`9c8649f` does -- is the difference between a known limit and a false claim.
