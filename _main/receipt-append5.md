

## 2026-10-06 05:25Z — THE PANEL IS FIXED (measured), AND TWO INSTRUMENT FAULTS OF MINE ARE RECORDED

### The renderer fix, verified by me and not taken from the lane's word
Lane `SottoPanelSurface` owns panel.html/panel.css. Its instrument `app/electron/dom-probe.js` (NEW,
605 lines) loads panel.html in the REAL window options WITH the real preload.js and asserts three
states — idle, live (2 captions over real IPC), cleared (the Clear button actually clicked) — with the
contract enforced BOTH ways: required-visible elements must render, out-of-contract elements must NOT.
It also computes WCAG contrast against the paint composited behind each text element.

    BEFORE (lane): rc=1  ok=False failures=32
    AFTER  (me):   rc=0  ok=True  failures=0        <- I ran it myself; not the lane's claim

Defects it named with numbers, all now fixed:
- `.wordmark__name` color rgba(0,0,0,0), contrast 1.09 (background-clip:text only) — the Sotto title
  was invisible unless the clip painted.
- `#caption-list` hidden=FALSE in the IDLE state — the empty list rendered when it should not.
- headerAlignmentDeltaY = 3.34 (tolerance 2).
- `.status__hint` contrast 4.04 at 10.5px — under WCAG AA 4.5.

### Pixel proof, before vs after, against the owner's own screenshot
10 bands of 38px, % of pixels differing from the slab colour, left to right
(`_main/panel-transparent.png` is now the AFTER render — see the collision note):

    OWNER screenshot (broken)   56.7 37.3 33.0 28.4 25.7 25.4 25.5 26.5 29.1 34.8
    ELECTRON before the fix     53.8 18.3 15.5 12.6 13.1 13.0 11.9 11.2 18.5 55.9
    ELECTRON after the fix      25.3 14.0  9.7  7.9  7.9  7.8  8.0  9.4 19.2 22.3

The heavy EDGE artifacts are gone: left 53.8 -> 25.3, right 55.9 -> 22.3. The owner's profile sits
closest to the BROKEN arm, which is what he was looking at.

### TWO INSTRUMENT FAULTS OF MINE, recorded rather than buried
1. **A 48x44 ASCII map of a 380x900 capture is too coarse to read a layout from.** I called a
   left-column collapse in the owner's screenshot; the band profile refutes it — content spans every
   band in all three images. Orientation only, never a verdict. (Row `instrument-granularity-20261006`.)
2. **`--dump-dom` names its capture by ARM only (`panel-<transparent|opaque>.png`), so a second run
   SILENTLY OVERWRITES the first.** I lost the before-fix PNG to the after-fix run and only noticed
   because the band numbers changed under the same filename. The fix is a `--tag` in the filename;
   until then, copy the file between runs. The before-fix numbers survive in this table.

### Still open, stated plainly
- Owner pressing Alt+C: registration is proven, the toggle is not.
- Text accuracy: lane `SottoAccuracyInt4` (in flight) owns the int4-vs-best-precision comparison.
- WebView swap: lane `SottoWebViewShell` (in flight) owns it. NOT done.
