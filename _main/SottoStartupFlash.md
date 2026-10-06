# SottoStartupFlash — the intermittent startup flash, BOUNDED and (not) closed

Ticket: bound the sub-sample panel flash at shell startup, fix it, prove a
negative arm, correct AGENTS.md's "arm P 0 of 41".

## 1. The instrument

`_main/panel-startup-flash-census.py` — samples the shell's OWN pid tree every
**25 ms** over N launches and reports, per arm:

- **mech** = a top-level window in the tree is `WS_VISIBLE` **and not
  alpha-occluded** (`GetLayeredWindowAttributes` alpha != 0). Position-ignored:
  this is "did the `Show()` happen and is it not the invisible `Opacity=0`
  creation dance".
- **owner** = mech **AND on a monitor** (`MonitorFromWindow(...,
  MONITOR_DEFAULTTONULL)`). This is "can the owner actually see it".

Arms: `live` (current shell), `nocure` (the fix reverted in a COPY),
`precure`/`opaque`/`sync-off`/`show`. Copies are built from the live shell at
run time, sha logged, deleted after. **All measurement copies run at
`x=-10000`** so nothing appears on the owner's desk.

## 2. BOUND — the numbers (25 ms cadence)

| when | arm | N | mech launches | mech samples | longest mech | phase |
|---|---|---|---|---|---|---|
| BEFORE (sync+posted re-assert only) | `live` @x=-10000 | 20 | 11/20 | 15/3417 | **57.7 ms** | `AT_STARTUP` + `STAGING_LOADED` |
| AFTER (control-event subscription) | `live` @x=-10000 | 20 | 18/20 | 24/3005 | **63 ms** | `AT_STARTUP` + `STAGING_LOADED` |
| NEGATIVE (fix reverted → `.core`) | `nocure` @x=-10000 | 20 | 19/20 | 29/3005 | **68 ms** | same |

**The negative arm reproduces (mech > 0 ⇒ not blind). The fix does NOT move the
count.** Subscribing the re-assert to the SAME event pywebview subscribes (the
control's `NavigationStarting`) left 18/20 vs the un-fixed 19/20 — the
`Show()`→`Hide()` gap survives same-dispatch subscription.

## 3. Mechanism — which of the three it is

**pywebview's transparent Show-on-navigation-start** (`edgechromium.py:347`,
`if self.pywebview_window.transparent: self.form.Show()`), triggered on the
stage.html→panel.html navigation. NOT the `hidden=True` dance by itself (that
dance leaves `alpha=0` in the arms where it is caught in isolation).

## 4. FIX — what closed it, and what did NOT (all measured)

- ❌ **`self.window.transparent = False` after create** — MEASURED WRONG:
  pywebview's navigation `Show()` is what makes a transparent WebView2 *load*;
  clearing the flag makes the panel navigation never complete → `_on_loaded`
  never fires → the shell **HANGS** (`_main/_flash-live-0.log` stops at
  `STAGING_LOADED`, rc=-999, no `PANEL_VISIBILITY_ON_SCREEN`).
- ❌ **Create the window at `OFFSCREEN = -32000` and move it in later** (a
  sibling lane's attempt) — MEASURED WRONG, identical hang: WebView2 does not
  complete the navigation for a window parked at -32000. Reproduced with NO
  `--exit-after` (9 s, log stops at `STAGING_LOADED`, no `PRELOAD_ACTIVE`, no
  `RECEIVER_READY`). **Reverted** in `create_window` (now `x=geometry['x']`).
- ❌ **Subscribe the control event** (§2) — no change.
- ✅ **`--opaque`** (transparent=False from CREATION): the visible flash drops
  to **3/20 and every catch is `alpha=0`** — i.e. the invisible `Opacity=0`
  creation dance, not a flash. **This is a FINDING, not a workaround.** COST:
  the panel loses its transparent background / rounded-corner look
  (`DefaultBackgroundColor` becomes the opaque `#0b0f14`).

**So: with the panel's transparency ON, the ≤~63 ms startup flash is NOT closed
by any re-assert.** It is closed only by giving up the transparent look.

## 5. What the owner would see

With transparency on: a **sub-frame-to-~63 ms** appearance of the panel at the
real position on roughly **18 of 20 starts** — a "pisca" at every launch, not a
persistent window. With `--opaque`: nothing.

## 6. AGENTS.md

The "arm P 0 of 41 samples" claim is **corrected by measurement** (200 ms grid
cannot see a ≤63 ms event; a 25 ms grid catches it in ~18/20 launches).

## 7. A REGRESSION I CAUSED AND FIXED (disclosed)

An earlier edit of mine deleted the line `self._ui(self._subscribe_core_ready)`
from `_on_before_show`; my revert of that edit did not restore it. Result:
`_on_core_ready` never ran → no `NavigationStarting` subscription → the panel
was left VISIBLE at startup (3/3 direct launches). Restored; verified 3/3
`PANEL_VISIBILITY_ON_SCREEN visible=false` and `RECEIVER_READY` present.

## 8. Safety

All measurement copies ran at `x=-10000`. The on-screen `real` arm is now
**refused by default** (`--allow-onscreen` required). The one on-screen phase
that put the panel on the desk was an earlier broken fix; its launchers were
killed (`_main/_kill-my-probes.ps1`, filter `sotto_webview\.py` /
`panel-startup-flash-census\.py` only — never a generic word).
