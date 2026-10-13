# ZIP B - built, rendered and VIEWED (2026-10-13)

Artefact `zip-B-themes.html` (287 262 B). Render 1280x800 with `--virtual-time-budget=25000`.

## What it is: a COMPLETE APP mockup, and its caption model is a DIFFERENT ONE

Unlike zip A (a directions explorer) and zip E (a bare panel), **zip B is a whole product
screen** -- a media player with a transcript library:

* Top bar: `Nocturne` + `LIVE CAPTIONS . TEN SCENES`, a clock `12:59`, a recording chip
  `REC 08:25`, a language chip `EN`, a scene stepper `01 / 10`, and icons.
* A left rail `SCENES` listing ten scenes (`01 Midnight Rain`, ...).
* A large backdrop image (a night city street).
* **A RIGHT PANEL `Transcripts` / `EVERYTHING THE NIGHT SAID`** with `NOW TRANSCRIBING 7/8
  LINES`, then the lines as **time + SPEAKER + text** (`02:41 AM MARA Tonight we are talking
  about the quiet hours...`), then a **search box**, then a `LIBRARY` of six recordings with
  duration and word counts.
* Bottom control row: pause, restart, `1x`, a `LIVE` meter.
* **AND THE LIVE CAPTION ITSELF: the SPEAKER NAME (`JONAS`) on one line, and under it ONE BIG
  LINE -- `Windows down, volume low. The good kind of alone.`**

## THE FINDING THAT MATTERS: the caption is NOT the same object in the two zips

| | zip E | zip B |
|---|---|---|
| where the live caption lives | a right-hand COLUMN of stacked, fading lines | ONE BIG LINE at the BOTTOM, full width |
| speaker | not shown | **the NAME sits above the line** |
| the history | the same column, older lines faded | a SEPARATE right panel, with time + speaker on every row |

**So "make it look like the zip" is not one target.** These are two different reading models,
and which one the product should have is a DESIGN DECISION -- it is not derivable from the
pixels, and choosing one silently would be inventing the requirement.

## What is NOT done

* **Zip C and zip D are built AND rendered but NOT yet LOOKED AT.** Their PNGs are in
  `docs/design-intake/rendered/`; nothing about their designs is known here.
* No mapping from any zip to our `pd-tele` / `pd-bcast` / `pd-mano` / `pd-cine` / `pd-instr`.
* The colours above are described from the render; no eyedropper was run, so no hex is quoted.
