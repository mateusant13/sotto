# The per-app boundary: which named gaps are defects and which are architecture (2026-10-11)

Two entries in the STEP 4/5 register read like defects. Measured against the shipped bytes, one is a
BOUNDARY and the other is consistent behaviour. Nothing was launched (owner stop order in force).

## 1. "TWO APPS AT ONCE IS IMPOSSIBLE" — a boundary, not a bug

Proven, with anchors:

- **ONE worker.** `WorkerBridge(` is constructed exactly ONCE in the shell (`sotto_webview.py:5460`);
  the slot is `self.bridge = None` at `:3416` and is cleared at `:5540` and `:6432`. A second bridge
  has no place to live, so the shell drives one worker process at a time.
- **ONE live tap.** The ladder CLOSES the previous tap before opening the next: `def close_tap(t)` at
  `worker/sotto_worker.py:5010`, called at `:5104`, `:5232` and `:5264`. Sources in one run are therefore
  SEQUENTIAL (a rotation), never simultaneous.
- **ONE target.** `--app-target` / `SOTTO_APP_TARGET` resolves to a single pid at the single construction
  site (`target_pid=target_pid`, `:5470`).

So "two apps at once" needs a SECOND bridge, a SECOND worker and a SECOND target value: it is a new
feature, not a repair. **The panel is already ready for it**: `engines` is a Map keyed by source
(`engines.set(key, engine)` `panel.js:678`), `provisionalRows` is a Map (`:382`, `:776`), and rows are
keyed by `rowIdentity(source, start)` (`:326`). When the shell someday runs N workers, the caption list
needs no change.

## 2. "`SottoSkin.live(...)` IS ONE SURFACE (last painter wins)" — consistent, not a defect

`SottoSkin.live({ committed, provisional })` (`panel.js:843`) paints ONE themed live surface, and
`:863` clears it when a source retires. Given fact 1.2 above — at most one tap is live at a time in a
run — the last painter IS the live source, so the single surface is not fighting anything. The
per-source ROWS keep their own identity, so after a rotation the earlier source's lines stay in the
list under their own `data-source`.

It becomes a real gap only in the same hypothetical as fact 1: two simultaneous workers would need N
skin surfaces. Named here so the next reader does not "fix" a surface that is behaving correctly.

## What is still genuinely open

- **No live end-to-end per-app measurement.** No `source=proc:<pid>` has ever reached the panel from a
  real tap, because the owner's stop order forbids launching the shell or the worker. Every claim above
  is a code-path read, not a runtime one.

## NOT MEASURED

- Nothing was launched. The rotation behaviour (fact 1.2) is read from the call sites of `close_tap`,
  not observed in a run that actually rotated.
- The worker's own `device-rotated reason=per-app-tap-lost` event was not exercised.
