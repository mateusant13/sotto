# Receipt — the `--dump-dom` window floor, and which arm of this lane it invalidated

**Measured 2026-10-09, this session.** A repair of `rects.py` and `geom.py` turned up a
measurement floor that invalidates ONE arm of the lane's own inventory. Recorded here
because those numbers are already on disk.

## The floor

Headless Edge clamps the LAYOUT VIEWPORT at **492 px** (a window width of 516) in
`--dump-dom` mode only:

    rects.py --theme theme-1 --surface panel
    inner=492x900  dpr=1  theme=theme-1 surface=panel  window=404x992
       <-- CLAMPED: asked 380x900, Edge rendered 492x900

every request at or under 515 renders 492 inner whatever was asked -- MEASURED
380 / 404 / 410 / 440 / 480 / 500 / 510 / 515 -> **492** -- and from 516 up the
-24 arithmetic holds exactly (516 -> 492, 520 -> 496, 700 -> 676).

**It is a `--dump-dom` artefact, not a browser minimum.** `shot.py` measures the same
flag with `--screenshot` and there is no floor at all — its marker document (pure
`#ff0000` page, the panel forced to a pure `#00ff00` 380 px block docked right) gives
`--window-size=380,900 -> PNG 380x900`, and even `150x400 -> 150x400`
(`shot.py:16-24` for the marker, `:40-46` for the re-measurement). With `--screenshot`
the PNG **is** the viewport; with `--dump-dom` the viewport is the request **minus 24 px
wide and minus 92 px tall**, and anything at or under ~516 wide is clamped to 492.

The shipped sizes, read live from the shell rather than from either probe's prose:

| constant | value | where |
|---|---|---|
| `PANEL_WIDTH` / `PANEL_HEIGHT` | 380 / 900 | `app/webview/sotto_webview.py:84-85` |
| `STRIP_WIDTH` / `STRIP_HEIGHT` | 1040 / 150 | `app/webview/sotto_webview.py:605-606` |

## Which arm of the lane survives

- **strip arm — VALID.** `--size 1040x150` is above the floor, so `inner=1040x150`
  (verified this session, both themes) is the real strip at `STRIP_WIDTH` x
  `STRIP_HEIGHT`. Quote the strip rows of `_rects-20261009-inventory.txt`.
- **panel arm — MEASURED AT 492, NOT AT THE SHIPPED 380.** Every box in the panel half
  of `_rects-20261009-inventory.txt` (line 82 onward: `MAIN panel w=492`, the header
  row out to x=417, ...) is a **492 px wide** layout. Those numbers are NOT the app's
  panel layout and must not be quoted as such. The header line already said
  `inner=492x900 (asked viewport 380x900)` — the value was honest, the labels around
  it were not.

**`template-plan.md` is unaffected.** Its 380 is the shipped `PANEL_WIDTH`, and every
number it quotes is an upstream STAGE value (52–68ch, 700–760px, `1.5–2.3rem`) which it
explicitly re-derives for a 380 px column (`:5`, `:213`). It never depends on the 492
measurement. Its "380 px rule" blocks stay as written.

## The gap this leaves

**No instrument in this lane can report DOM boxes at the panel's true 380 px width.**
`--screenshot` produces the 380 px PNG but returns no DOM; `--dump-dom` returns the DOM
but cannot get below 492. Until that exists:

- ink geometry at 380 -> `shot.py` PNGs (the `panel5` preset = `PANEL_SIZE`),
- live panel DOM at its real size -> the shell's own `PANEL_STATE_PROBE` /
  `_main/panel-state.json` (needs the app running, not headless Edge),
- 492 px DOM boxes -> `rects.py`, labelled as 492.

## The two repairs that surfaced it (both verified running)

1. **`rects.py` and `geom.py` died before printing anything on the panel arm** —
   `print()` of theme-1's glyphs (arrows, quotes) on a cp1252 stdout, fixed with
   `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` guarded by
   `(AttributeError, ValueError)`.
2. **The panel header reported the arithmetic, not the measurement** — it printed
   `(asked viewport 380x900)` beside a measured 492. Both probes now print
   `window=<W>x<H>` from the request plus a `<-- CLAMPED: asked AxB, Edge rendered Cxd`
   note whenever the measured inner size disagrees, and both docstrings carry the floor
   above the `DEFAULT_SIZES` they explain.

Gate, all four arms:

    python rects.py --theme theme-1 --surface strip   # inner=1040x150  (no note)
    python rects.py --theme theme-1 --surface panel   # inner=492x900 ... CLAMPED note
    python geom.py  --surface panel                    # viewport=492x900
    python geom.py  --surface strip                   # viewport=1040x150
