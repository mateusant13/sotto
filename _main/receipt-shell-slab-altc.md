# RECEIPT — the solid slab, and Alt+C twice (shell, Lead-only)

Date 2026-10-12. Owner, verbatim, final message:

> "eu to vendo div com cor solida inves de invisivel"
> "o alt c apertado 2x nao ta abrindo o painel da direita"

Both are SHELL defects (`app/webview/sotto_webview.py`), which only the Lead
touches. Nothing was launched by this work; the owner instance (pid 8588 +
worker 22172) was left running.

## 1. The solid colour — the window was 1040 wide holding a ~400px pill

MEASURED, not inferred. `STRIP_WIDTH = 1040` (`sotto_webview.py:882`) sized the
strip WINDOW while `body[data-surface="strip"] .panel` is `width: max-content` —
a small pill. The shell gives the form the slab colour `#0B0F14` (`:3929`) and
that is exactly the colour the owner sees where the page does not paint. A
1040-wide window holding a small centred pill IS *"uma cor solida, uma div
inteira. no meio dela, tinha o painel de baixo"*.

The width now comes from the CONTENT, exactly as the height already did:

* `strip_width_from_dom()` measures the pill own rendered box through
  `getBoundingClientRect()`. `max-content` is INTRINSIC, so the measurement does
  not depend on the window width and cannot feed back into it.
* `strip_width_live()` / `refresh_strip_width()` mirror the height pair exactly —
  cached, so the geometry path never calls into the page, refreshed at the same
  three sites the height is (`hot-reload`, `place-*`, `surface-*`).
* `geometry_for("strip")` rewrites a saved rect width to the content width. A
  rect that WAS the slab (1040, or >=90% of the work area, or absent) is
  RE-CENTRED; a rect the owner placed by hand keeps its x and only takes the new
  width.
* Floated (`data-float="on"`) answers `None` ON PURPOSE: the floated caption is
  `left:0; right:0` inside the window and needs the room.

## 2. Alt+C twice — a double on a hidden panel was a no-op

MEASURED. The double branch read `if not live: ... return False` (`:5418-5423`),
a guard added on 2026-10-09 as "defect 3". It is only predictable if the press
pair always aligns with the user FIRST press, and it does not: a stale
`_last_hotkey_press` makes the owner first press the double, so the pair is
consumed doing nothing and his SECOND press lands as a single and only opens the
strip. Two presses therefore showed the strip and never the right panel — his
report, exactly.

A double with the panel down now calls `show_side("hotkey-double")`. The pair is
still consumed just above, so mashing Alt+C still alternates instead of pinning
anything open.

## 3. The gate — both colours, with a control that can say NO

`_main/strip-geometry-oracle.py` imports the shell and calls the REAL methods on
a fake object. It never launches anything.

| run | result |
|---|---|
| `py -3 _main/strip-geometry-oracle.py` | **VERDICT: PASS — 9 check(s), 0 fail**, rc=0 |
| `py -3 _main/strip-geometry-oracle.py --neg-arm` | **VERDICT: PASS — 12 check(s), 0 fail**, rc=0, 3/3 mutants RED |

Arms: A1 (1040 slab -> 420 content), A1b (re-centred to x=750), A2 (a hand
placement keeps its x), A3 (floated keeps the wide dock), A4 (a fresh install
with no saved rect is not a slab), B1/B4 (singles toggle the strip), B2 (**a
double from HIDDEN opens the RIGHT panel**), B3 (a double while on SIDE still
hides).

Mutants, each reverted in a COPY: `M1 hotkey-double-ignored` -> B2 RED;
`M2 saved-rect-width-not-content` -> A1 RED; `M3 owner-placement-recentred` ->
A2 RED.

### TWO OF MY OWN MUTANTS WERE INERT, AND THAT IS RECORDED, NOT HIDDEN

A mutant that changes nothing the arm can see is an ABSENT control, not a failed
one. Both times I had picked the wrong anchor:

1. `M2` first reverted the FALLBACK dock width. A1 exercises the SAVED-RECT
   correction, not the fallback, so nothing A1 could see moved. Re-aimed at the
   saved-rect block.
2. `M3` first reverted the same fallback and stayed inert for the same reason —
   and this one is inert BY CONSTRUCTION: the fallback is only reached when
   `strip_width_live()` answers `None`, which is exactly when there is no content
   width to pass. That path cannot carry a width at all, so no mutant on it can
   ever flip. Gating it would have been an absent control wearing a green tick.
   Replaced with `M3 owner-placement-recentred`, which gates a property that
   does exist.

## 4. House battery, after these edits

`node _main/instruments-battery.mjs` -> **79/79 rc=0, failed=0, launches=0**.

## 5. NOT MEASURED — stated plainly

* **The pixels.** The oracle proves the geometry the shell computes and the
  hotkey decision; it does NOT prove what WebView2 paints on the owner screen.
  The paint probe is the instrument for that and has not been re-run against
  these bytes.
* **The live effect.** `sotto_webview.py` is read at process start, so the owner
  running instance still runs the OLD code. This change needs a shell restart to
  be felt; that restart is the Lead call and had not been made when this receipt
  was written.
* **Dragging.** The owner also asked for the bottom panel to be movable. The
  shell half is now READY for it (a saved rect keeps an x that is not a slab
  re-centre), but the GESTURE is the panel lane work and is not in this receipt.
