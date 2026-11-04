# RECEIPT — Ctrl+Space never turned the caption OFF after a blank (2026-11-04)

## The observation, verbatim from the owner's own log (`_main/webview-run.log`)

    04:49:43.434 HOTKEY_PRESSED role=live count=292 source=observed via=latched
    04:49:43.435 HOTKEY_LIVE_STEP caption_on=true shown=false wanted=true
    04:49:43.437 LIVE_ENABLED on=true wanted=true panel_closed=false
    04:49:50.374 HOTKEY_PRESSED role=live count=293 source=observed via=latched
    04:49:50.374 HOTKEY_LIVE_STEP caption_on=true shown=false wanted=true
    04:49:50.376 LIVE_ENABLED on=true wanted=true panel_closed=false

Two presses, seven seconds apart, BOTH "on". The key did not toggle.

## The cause, in the same log

    04:48:06.763 CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s epoch=39 wanted=true

`_blank_caption_window` is the silence watchdog: it takes the PIXELS away and, by
its own contract, does NOT touch the owner's switch ("a proxima legenda volta a
escreve-lo sem tocar em nada"). It calls `ov.hide()` + `ov.show(False)`, so the
native window is UNMAPPED and `window_visible(hwnd)` reads False.

The hotkey step read `shown` (`window_visible` of the overlay) to decide the next
state, so after any blank the state it read was permanently "off" and every press
computed `on = True`. The switch could no longer be turned off.

That reading was itself the cure for the PREVIOUS defect (2026-11-03): the step
used to read `_caption_wanted`, and a switch restored `on=true` at startup with
the window never shown made the owner's first press HIDE a legend he could not
see (*"to apertando control espaco e nao ta ligando"*).

## The rule that satisfies both measurements

1. The KEY toggles `_caption_wanted` — the switch the owner owns. Blanking is a
   fact about pixels, not about the switch.
2. The STARTUP LIE moves to where it is born: `_caption_wanted_restored()` now
   sets `_caption_show_pending = True` when the switch comes back on, and the
   existing `CAPTION_WINDOW_DEFERRED_APPLIED` path shows the window the moment
   the overlay exists. So a restored `on=true` is no longer "on in a file, off on
   the screen": the screen follows the file at startup.
3. `shown` stays in the `HOTKEY_LIVE_STEP` line as DIAGNOSTIC.

## Instrument

`_main/hotkey-live-toggle-oracle.py` — 32 arms, and the two arms that encoded the
old rule were REWRITTEN, not deleted, with the evidence above in their comment:

* arm (a): `wanted=true` + window blanked → the press TURNS IT OFF; plus a
  structural arm that the startup restore requests the window
  (`self._caption_show_pending = True` guarded by `if self._caption_wanted:`).
* arm (c): `shown=false, wanted=true` (blanked) → OFF, and the overlay receives
  `show(False)`; the mirror case (`wanted=false`) → ON + `show(True)`, so the arm
  is not tautological.

    python _main/hotkey-live-toggle-oracle.py            -> GREEN arms=32 pass=32 fail=0
    python _main/hotkey-live-toggle-oracle.py --neg-arm  -> NEG-ARM PASS, 3 mutants,
                                                            each dropping its own arms

Sibling instruments, re-run after the change, all green:
`hotkey-live-edge-oracle.py` 3/3 + its `--neg-arm`; `altc-gesture-oracle.py` 86/86
(the panel cycle under spam); `hotkey-observed-oracle.py` 7/7 + its `--neg-arm`;
`_strip-reload-probe.py` GREEN (it was RED before this session's own fix, see the
commit before this one).

## What is NOT claimed

* No live app run was made by this lane: `verified` needs the owner's own session.
  The two lines above are the field evidence, and the fix is proven against them
  by the oracle executing the real bodies.
* `code-health` PASSES without raising its ratchet: the shell is 999 929 B against
  a pin of 1 000 322 B — the stale block that documented the superseded rule was
  replaced, not extended.

## The other defect measured in the same log window (NOT fixed here)

    CAPTION_ARRIVAL_BLOWN age_ms=114723 budget_ms=1500
    CAPTION_LAG_STATS n=200 p50=240 p90=4622 max=168564 over=99

The Sotto ASR line was ~115 s behind the audio it transcribed. Cause is visible in
`WORKER_STATS` (`queue_evicted` 4..8): the worker's audio queue overflows and the
ASR falls behind. It is a separate lane's subject (worker throughput/queue policy),
not the hotkey, and it is NOT fixed by this receipt.
